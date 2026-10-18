"""The Gecko Center window and the bridge its QML calls for updates, installs and settings."""

import json
import os
import subprocess
import sys
import tempfile
import threading

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkRequest
from PySide6.QtQml import QQmlApplicationEngine

from . import background, packages, paths, technical, update_notes, updates

sys.path.insert(0, str(paths.GECKO_UI / "python"))
from gecko_ui.root_access import RootAccess  # noqa: E402
from .catalog import FLATHUB, AppModel
from .center import Center
from .commands import Command, run_as_root
from .operations import Job, flatpak_update_steps, install_steps, preview_arguments, remove_steps, system_update_steps

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
CONNECT_TIMEOUT = 500
# How often a running job's new output reaches the window, in milliseconds
JOB_OUTPUT_INTERVAL = 200
ACTIVATION_VARIABLE = "XDG_ACTIVATION_TOKEN"


class Bridge(QObject):
	"""What the QML calls, and the signals it listens to."""

	updatesChanged = Signal()
	checkingChanged = Signal()
	busyChanged = Signal()
	backgroundChanged = Signal()
	notifyNewsChanged = Signal()
	jobProgress = Signal(float, str)
	jobLines = Signal("QStringList")
	jobFinished = Signal(bool, bool, str)
	previewReady = Signal("QVariantMap")
	packagesFound = Signal(str, "QVariantList")
	packageReady = Signal("QVariantMap")
	technicalReady = Signal(str, "QVariantMap")
	updateNotesReady = Signal(str, "QVariantMap")
	targetReady = Signal("QVariantMap")
	pageRequested = Signal(str)
	forwardRequested = Signal()

	def __init__(self, apps, parent=None):
		super().__init__(parent)
		self._apps = apps
		self._job_lines = []
		self._job_progress = None
		self._job_output_timer = QTimer(self)
		self._job_output_timer.setInterval(JOB_OUTPUT_INTERVAL)
		self._job_output_timer.timeout.connect(self._pass_on_job_output)
		# The system pages run their sudo through the same password
		self.root_access = RootAccess(paths.DESKTOP_ID, self)
		self._state = updates.read_state()
		self._checking = False
		self._listing = False
		self._busy = False
		self._network = QNetworkAccessManager(self)
		# A link that comes in while the catalog is still being read waits for it
		self._waiting_target = ""
		apps.loaded.connect(self._open_waiting_target)

	# Updates ================================================================

	def _get_updates(self):
		return self._state

	def _get_checking(self):
		return self._checking

	def _set_checking(self, value):
		self._checking = value
		self.checkingChanged.emit()

	@Slot(result=bool)
	def checkNeedsPassword(self):
		"""The refresh unit needs no password, without it the check runs zypper through sudo."""
		return not updates.refresh_unit_installed() and self.root_access.needsPassword()

	@Slot(result=bool)
	def needsPassword(self):
		return self.root_access.needsPassword()

	@Slot(str, result=bool)
	def setPassword(self, password):
		return self.root_access.setPassword(password)

	@Slot()
	def checkUpdates(self):
		if self._checking or self._busy or self._listing:
			return
		self._set_checking(True)
		self._next_state = {"system": None, "flatpak": []}
		if updates.refresh_unit_installed():
			command = Command(["systemctl", "start", paths.REFRESH_SERVICE], parent=self)
			command.finished.connect(lambda code, output: self._plan_read(code, paths.UPDATE_PLAN.read_text()
				if code == EXIT_SUCCESS else output))
			return
		refresh = run_as_root(self.root_access, updates.REFRESH_ARGUMENTS, self)
		refresh.finished.connect(self._plan_after_refresh)

	def _plan_after_refresh(self, exit_code, output):
		if exit_code != EXIT_SUCCESS:
			self._plan_read(exit_code, output)
			return
		plan = run_as_root(self.root_access, updates.PLAN_ARGUMENTS, self)
		plan.finished.connect(lambda code, text: self._plan_read(EXIT_SUCCESS, text))

	def _plan_read(self, exit_code, text):
		if exit_code == EXIT_SUCCESS:
			self._next_state["system"] = updates.plan_from_xml(text)
		else:
			self._next_state["system"] = updates.unreachable_plan(text.strip()[-600:])
		self._list_flatpak_updates(list(updates.FLATPAK_INSTALLATIONS))

	def _list_flatpak_updates(self, remaining):
		# The page keeps showing the old list meanwhile, the new one replaces it in one step
		self._listing = True
		if not remaining:
			self._finish_check()
			return
		installation = remaining.pop(0)
		command = Command(updates.flatpak_update_arguments(installation), parent=self)
		command.finished.connect(lambda code, text: self._flatpak_listed(installation, text, remaining))

	def _flatpak_listed(self, installation, text, remaining):
		self._next_state["flatpak"] += updates.flatpak_updates_from_text(text, installation,
			updates.installed_flatpak_refs(installation))
		self._list_flatpak_updates(remaining)

	def _finish_check(self):
		self._listing = False
		updates.write_state(self._next_state)
		self._state = self._next_state
		self.updatesChanged.emit()
		self._set_checking(False)

	@Slot()
	def updateEverything(self):
		system = self._state.get("system") or {}
		installations = sorted({entry["installation"] for entry in self._state.get("flatpak") or []})
		# Only what the last look found is updated, so nothing runs that the page did not show
		steps = system_update_steps(installations)
		if not system.get("known") or system.get("count", 0) == 0 or system.get("problem"):
			steps = steps[1:]
		self.start_job(steps, recheck=self.checkUpdates)

	@Slot("QVariantMap")
	def updateFlatpak(self, update):
		"""Flatpak apps update one by one if you like, unlike the system, which Tumbleweed updates all at once."""
		self.start_job(flatpak_update_steps(update), recheck=self.refreshFlatpakUpdates)

	@Slot()
	def refreshFlatpakUpdates(self):
		"""Look at Flatpak again and keep the system plan, it is quick and needs no password.

		The page calls it whenever it shows, so an app removed since the last look drops off the list at once.
		"""
		if self._checking or self._busy or self._listing:
			return
		system = self._state.get("system")
		if system is not None:
			# A check saved before plans had their own date takes the date of the whole check
			system = dict(system, checked=system.get("checked") or self._state.get("checked", ""))
		self._next_state = {"system": system, "flatpak": []}
		self._list_flatpak_updates(list(updates.FLATPAK_INSTALLATIONS))

	# Installing and removing ================================================

	def _get_busy(self):
		return self._busy

	def start_job(self, steps, recheck=None):
		if self._busy or not steps:
			return
		self._busy = True
		self.busyChanged.emit()
		job = Job(steps, self.root_access, self)
		job.progress.connect(self._keep_progress)
		job.line.connect(self._keep_line)
		self._job_output_timer.start()
		job.finished.connect(lambda ok, reboot, message: self._job_finished(ok, reboot, message, recheck))
		job.start()

	def _keep_progress(self, fraction, text):
		self._job_progress = (fraction, text)

	# Each batch starts a new list, so the job adds to whichever list is current rather than the first one
	def _keep_line(self, text):
		self._job_lines.append(text)

	def _pass_on_job_output(self):
		"""A big update prints thousands of lines, the window takes them in batches so it stays smooth."""
		if self._job_progress is not None:
			self.jobProgress.emit(*self._job_progress)
			self._job_progress = None
		if self._job_lines:
			lines, self._job_lines = self._job_lines, []
			self.jobLines.emit(lines)

	def _job_finished(self, succeeded, reboot, message, recheck):
		self._job_output_timer.stop()
		self._pass_on_job_output()
		self._busy = False
		self.busyChanged.emit()
		self._apps.refreshInstalled()
		self.jobFinished.emit(succeeded, reboot, message)
		# Any install or removal can change what is left to update
		(recheck or self.refreshFlatpakUpdates)()

	@Slot("QVariantMap", result=bool)
	def changeNeedsPassword(self, entry):
		"""Repository packages and package files go through zypper as root, Flatpak apps install for your user only."""
		is_flatpak = entry.get("source") == FLATHUB or entry.get("format") == "flatpakref"
		return not is_flatpak and self.root_access.needsPassword()

	@Slot(str, "QVariantMap")
	def preview(self, action, entry):
		"""Say what else a change brings along, zypper works it out without changing anything."""
		if entry.get("source") == FLATHUB or entry.get("format") == "flatpakref":
			self.previewReady.emit({"known": True, "count": 1, "sections": {}, "problem": ""})
			return
		command = run_as_root(self.root_access, preview_arguments(action, entry), self)
		command.finished.connect(lambda code, text: self.previewReady.emit(updates.plan_from_xml(text)))

	@Slot("QVariantMap")
	def install(self, entry):
		self.start_job(install_steps(entry))

	@Slot("QVariantMap")
	def remove(self, entry):
		self.start_job(remove_steps(entry))

	# Packages, files and links ==============================================

	@Slot(str)
	def searchPackages(self, text):
		command = Command(packages.search_arguments(text), parent=self)
		command.finished.connect(lambda code, output: self.packagesFound.emit(text,
			packages.search_results_from_xml(output)))

	@Slot(str)
	def openPackage(self, name):
		command = Command(packages.info_arguments(name), parent=self)
		command.finished.connect(lambda code, output: self.packageReady.emit(packages.package_from_info(output, name)))

	@Slot("QVariantMap")
	def readTechnical(self, entry):
		"""The technical tab of an app page, read only when it is opened."""
		if entry.get("source") == FLATHUB:
			self._read_flatpak_technical(entry["key"], entry["package"], entry.get("installation", ""))
		else:
			self._read_package_technical(entry["key"], entry["package"])

	@Slot(str, "QVariantMap", "QVariantList")
	def readUpdateNotes(self, key, pending, releases):
		"""The update tab of an app page, read in a thread since it can download a changelog file."""
		def read():
			self.updateNotesReady.emit(key, update_notes.read_notes(pending, releases))
		threading.Thread(target=read, daemon=True).start()

	def _read_package_technical(self, key, name):
		"""zypper info, then what provides its requirements, then what installed needs it, one after another."""
		found = {"facts": [], "needs": [], "neededBy": [], "permissions": [], "installed": False}

		def take_needed_by(code, output):
			found["neededBy"] = technical.packages_from_searches([output], name)
			self.technicalReady.emit(key, found)

		def search_providers(searches, outputs):
			if searches:
				command = Command(searches[0], parent=self)
				command.finished.connect(lambda code, output: search_providers(searches[1:], outputs + [output]))
				return
			found["needs"] = technical.packages_from_searches(outputs, name)
			if not found["installed"]:
				self.technicalReady.emit(key, found)
				return
			Command(technical.needed_by_arguments(name), parent=self).finished.connect(take_needed_by)

		def take_info(code, output):
			info = technical.package_info(output)
			found["facts"] = info["facts"]
			found["installed"] = info["installed"]
			search_providers(technical.provider_searches(info["capabilities"], info["installed"]), [])

		Command(technical.requires_arguments(name), parent=self).finished.connect(take_info)

	def _read_flatpak_technical(self, key, app_id, installation):
		found = {"facts": [], "needs": [], "neededBy": [], "permissions": [], "installed": installation != ""}

		def take_permissions(code, output):
			found["permissions"] = technical.flatpak_permissions(output)
			self.technicalReady.emit(key, found)

		def take_info(code, output):
			found["facts"] = technical.flatpak_facts(output)
			if not installation:
				self.technicalReady.emit(key, found)
				return
			command = Command(technical.flatpak_permissions_arguments(app_id, installation), parent=self)
			command.finished.connect(take_permissions)

		Command(technical.flatpak_info_arguments(app_id, installation), parent=self).finished.connect(take_info)

	@Slot(str)
	def openTarget(self, argument):
		"""Show what a double-clicked file or a clicked install link contains, before anything is installed."""
		if not self._apps.ready:
			self._waiting_target = argument
			return
		target = packages.link_target(argument)
		kind = target["type"]
		if kind == "rpm":
			self.targetReady.emit(packages.rpm_file(target["path"]))
		elif kind in ("flathub", "appstream"):
			self._show_flathub_app(target["id"], {})
		elif kind == "flatpakref":
			with open(target["path"], encoding="utf-8") as reference_file:
				self._show_reference(packages.flatpak_reference(reference_file.read()), target["path"])
		elif kind == "remote-reference":
			reply = self._network.get(QNetworkRequest(QUrl(target["url"])))
			reply.finished.connect(lambda: self._reference_downloaded(reply, target["url"]))
		else:
			self.targetReady.emit({"kind": "file", "problem": "Gecko Center cannot install this kind of file.",
				"path": target["path"]})

	def _open_waiting_target(self):
		target, self._waiting_target = self._waiting_target, ""
		if target:
			self.openTarget(target)

	def _reference_downloaded(self, reply, url):
		text = bytes(reply.readAll()).decode(errors="replace")
		reply.deleteLater()
		self._show_reference(packages.flatpak_reference(text), url)

	def _show_reference(self, reference, location):
		fallback = {"kind": "file", "format": "flatpakref", "key": "file:" + location, "path": location,
			"id": reference["id"], "package": reference["id"], "name": reference["name"], "summary": "",
			"description": "", "source": "This file", "homepage": "", "developer": "", "license": "",
			"installation": "", "icon": "", "trust": "flatpak", "origin": reference["url"]}
		self._show_flathub_app(reference["id"], fallback)

	def _show_flathub_app(self, app_id, fallback):
		"""Open the app's full Flathub page when the catalog knows it."""
		key = self._apps.findKey(FLATHUB, app_id)
		if key:
			self.targetReady.emit(self._apps.entry(key, FLATHUB))
			return
		self.targetReady.emit(fallback or {"kind": "file", "problem": f"{app_id} is not on Flathub.", "path": app_id})

	# Background check =======================================================

	def _get_interval(self):
		return background.current_interval()

	def _get_unit_installed(self):
		return updates.refresh_unit_installed()

	def _get_notify_news(self):
		return paths.NEWS_NOTIFY_FILE.exists()

	@Slot(bool)
	def setNotifyNews(self, wanted):
		"""The tray reads the switch each time it looks at the feed, so nothing needs restarting."""
		if wanted:
			paths.NEWS_NOTIFY_FILE.parent.mkdir(parents=True, exist_ok=True)
			paths.NEWS_NOTIFY_FILE.touch()
		else:
			paths.NEWS_NOTIFY_FILE.unlink(missing_ok=True)
		self.notifyNewsChanged.emit()

	@Slot(str)
	def setBackground(self, interval):
		"""Turn the check on at an interval, or off with an empty string, root files only change when they must."""
		if interval:
			background.install_user_units(interval)
			if not updates.refresh_unit_installed():
				self._run_root_files(background.write_system_files)
		else:
			background.remove_user_units()
			if updates.refresh_unit_installed():
				self._run_root_files(lambda directory: background.remove_system_arguments())
		self.backgroundChanged.emit()

	def _run_root_files(self, arguments_for):
		directory = tempfile.TemporaryDirectory(prefix="gecko-center-")
		command = run_as_root(self.root_access, arguments_for(directory.name), self)
		command.finished.connect(lambda code, output: (directory.cleanup(), self.backgroundChanged.emit()))

	# Running apps ===========================================================

	def _desktop_file(self, entry):
		"""The installed .desktop file the AppStream entry names as its launcher, None when there is none."""
		desktop_id = entry.get("launchable") or ""
		if not desktop_id:
			return None
		desktop_id = desktop_id if desktop_id.endswith(".desktop") else desktop_id + ".desktop"
		data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
		data_dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
		for folder in [data_home, *data_dirs]:
			candidate = os.path.join(folder, "applications", desktop_id)
			if os.path.exists(candidate):
				return candidate
		return None

	@Slot("QVariantMap", result=bool)
	def canRun(self, entry):
		"""Flatpak apps always start with flatpak run, a package only when its launcher is installed."""
		if entry.get("kind") != "app" or not entry.get("installation"):
			return False
		return entry.get("source") == FLATHUB or self._desktop_file(entry) is not None

	@Slot("QVariantMap")
	def runApp(self, entry):
		if entry.get("source") == FLATHUB:
			arguments = ["flatpak", "run", entry["package"]]
		else:
			arguments = ["gio", "launch", self._desktop_file(entry)]
		subprocess.Popen(arguments, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

	# Session ================================================================

	@Slot()
	def reboot(self):
		subprocess.Popen(["qdbus6", "org.kde.LogoutPrompt", "/LogoutPrompt", "org.kde.LogoutPrompt.promptReboot"])

	@Slot()
	def updateInTerminal(self):
		"""When zypper needs a choice the window cannot make, it asks in your default terminal instead."""
		service = subprocess.run(["kreadconfig6", "--file", "kdeglobals", "--group", "General", "--key",
			"TerminalService"], capture_output=True, text=True, check=False).stdout.strip()
		terminal = service.removesuffix(".desktop").split(".")[-1] or "konsole"
		subprocess.Popen([terminal, "-e", "sudo", paths.ZYPPER, "dup"])

	updates = Property("QVariantMap", _get_updates, notify=updatesChanged)
	checking = Property(bool, _get_checking, notify=checkingChanged)
	busy = Property(bool, _get_busy, notify=busyChanged)
	backgroundInterval = Property(str, _get_interval, notify=backgroundChanged)
	refreshUnitInstalled = Property(bool, _get_unit_installed, notify=backgroundChanged)
	notifyNews = Property(bool, _get_notify_news, notify=notifyNewsChanged)


def _forward_to_running_window(arguments):
	"""A second start hands its page or file to the open window and quits."""
	socket = QLocalSocket()
	socket.connectToServer(str(paths.WINDOW_SOCKET))
	if not socket.waitForConnected(CONNECT_TIMEOUT):
		return False
	socket.write(json.dumps(arguments).encode() + b"\n")
	socket.waitForBytesWritten(CONNECT_TIMEOUT)
	socket.disconnectFromServer()
	return True


def _listen_for_later_starts(bridge):
	server = QLocalServer(bridge)
	QLocalServer.removeServer(str(paths.WINDOW_SOCKET))
	server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
	server.listen(str(paths.WINDOW_SOCKET))

	def take_connection():
		connection = server.nextPendingConnection()

		def read():
			if not connection.canReadLine():
				return
			_open_arguments(bridge, json.loads(bytes(connection.readLine()).decode()))
		connection.readyRead.connect(read)
	server.newConnection.connect(take_connection)


def _open_arguments(bridge, arguments):
	page, targets, token = arguments
	# Qt's Wayland window reads the token from the environment the next time it asks to be activated
	if token:
		os.environ[ACTIVATION_VARIABLE] = token
	if targets:
		bridge.openTarget(targets[0])
	elif page:
		bridge.pageRequested.emit(page)
	# Starting it again from the menu or System Settings means showing the open window
	bridge.forwardRequested.emit()


def main(page, targets):
	# Without a terminal Qt sends its warnings to the journal, which hides why the window failed
	os.environ.setdefault("QT_FORCE_STDERR_LOGGING", "1")
	# Vimix lists fallback icon themes that are not installed, KDE warns about each one and nothing is wrong
	logging_rules = [os.environ.get("QT_LOGGING_RULES"), "kf.iconthemes.warning=false"]
	os.environ["QT_LOGGING_RULES"] = ";".join(filter(None, logging_rules))
	application = QGuiApplication(sys.argv)
	application.setApplicationName(paths.APPLICATION_NAME)
	application.setDesktopFileName(paths.DESKTOP_ID)
	application.setWindowIcon(QIcon(str(paths.ICON)))
	if _forward_to_running_window([page, targets, os.environ.get(ACTIVATION_VARIABLE, "")]):
		return EXIT_SUCCESS

	apps = AppModel()
	bridge = Bridge(apps)
	center = Center(bridge, bridge.root_access, bridge)
	_listen_for_later_starts(bridge)
	interface = QQmlApplicationEngine()
	interface.addImportPath(str(paths.GECKO_UI / "qml"))
	context = interface.rootContext()
	context.setContextProperty("bridge", bridge)
	context.setContextProperty("apps", apps)
	context.setContextProperty("center", center)
	context.setContextProperty("assets", QUrl.fromLocalFile(str(paths.ASSETS) + "/"))
	context.setContextProperty("startPage", page or "")
	context.setContextProperty("windowSizeFile", QUrl.fromLocalFile(str(paths.WINDOW_SIZE_FILE)))
	context.setContextProperty("monospace", QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())
	interface.load(QUrl.fromLocalFile(str(paths.QML / "Main.qml")))
	if not interface.rootObjects():
		return EXIT_FAILURE
	apps.load()
	if targets:
		bridge.openTarget(targets[0])
	return application.exec()
