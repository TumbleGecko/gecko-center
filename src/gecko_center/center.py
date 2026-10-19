"""What the system pages read and change, from health, hardware and snapshots to drivers, storage, services and news.

Reading runs beside the window so it stays smooth, changes run as jobs through the main bridge with their progress.
"""

import shutil
import threading

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from . import (drivers, guide, hardware, hardware_history, health, journal, news, operations, performance, report,
	services, snapshots, sources, storage)
from .commands import Command, run_as_root

EXIT_SUCCESS = 0
# How often the performance page looks again, in milliseconds
PERFORMANCE_INTERVAL = 1000
# udev announces a plugged in or out USB device as one line, which the hardware pages follow while they show
USB_MONITOR_ARGUMENTS = ["udevadm", "monitor", "--udev", "--subsystem-match=usb/usb_device"]
# A device arriving brings a few lines at once, so the pages read again once they have stopped, in milliseconds
USB_SETTLE = 700

# Each look that needs no root, run on a thread of its own
COLLECTORS = {
	"health": health.collect,
	"sources": lambda: {"sources": sources.read_sources()},
	"source-packages": lambda: {"packages": sources.installed_by_source()},
	"report": report.share,
	"drivers": drivers.collect,
	"hardware": hardware.collect,
	"hardware-history": hardware_history.collect,
	"journal": journal.collect,
	"storage": storage.collect,
	"services": services.collect,
}

# Each change the pages can ask for, by name, with the steps it runs for its argument
ACTIONS = {
	"firewall-on": lambda _argument: [operations.Step("Turning on the firewall",
		["systemctl", "enable", "--now", "firewalld.service"], root=True)],
	"restart-service": lambda argument: services.restart_steps(*argument.split(":", 1)),
	"stop-service": lambda argument: services.stop_steps(*argument.split(":", 1)),
	"rollback": snapshots.rollback_steps,
	"snapshots-remove-old": snapshots.remove_steps,
	"source-on": lambda alias: [operations.zypper_step("Turning on " + alias, sources.switch_arguments(alias, True))],
	"source-off": lambda alias: [operations.zypper_step("Turning off " + alias, sources.switch_arguments(alias, False))],
	"packages-remove": operations.remove_packages_steps,
	"source-remove": lambda alias: [operations.zypper_step("Removing " + alias, sources.remove_arguments(alias))],
	"nvidia-driver": lambda _argument: drivers.nvidia_steps(),
	"firmware-update": drivers.firmware_steps,
	"clean": storage.cleanup_steps,
}


class Center(QObject):
	"""The system pages' bridge, each page reads its part of info by name and asks for changes by action name."""

	infoChanged = Signal()
	readingChanged = Signal()
	_collected = Signal(str, "QVariantMap")

	def __init__(self, bridge, root_access, parent=None):
		super().__init__(parent)
		self._bridge = bridge
		self._root = root_access
		self._info = {}
		self._reading = set()
		self._network = QNetworkAccessManager(self)
		self._collected.connect(self._store)
		self._sampler = performance.Sampler()
		self._performance_timer = QTimer(self)
		self._performance_timer.setInterval(PERFORMANCE_INTERVAL)
		self._performance_timer.timeout.connect(lambda: self.read("performance"))
		self._pmon = None
		self._usb_monitor = None
		self._usb_watchers = 0
		self._usb_settle = QTimer(self)
		self._usb_settle.setSingleShot(True)
		self._usb_settle.setInterval(USB_SETTLE)
		self._usb_settle.timeout.connect(self._usb_changed)

	def _store(self, kind, value):
		self._reading.discard(kind)
		self._info = dict(self._info, **{kind: value})
		self.infoChanged.emit()
		self.readingChanged.emit()

	def _get_info(self):
		return self._info

	def _get_reading(self):
		return sorted(self._reading)

	# Reading ================================================================

	@Slot(str)
	def read(self, kind):
		if kind in self._reading:
			return
		self._reading.add(kind)
		self.readingChanged.emit()
		if kind in COLLECTORS:
			threading.Thread(target=lambda: self._collected.emit(kind, COLLECTORS[kind]()), daemon=True).start()
		elif kind == "performance":
			threading.Thread(target=lambda: self._collected.emit(kind, self._sampler.sample()), daemon=True).start()
		elif kind == "snapshots":
			command = run_as_root(self._root, snapshots.LIST_ARGUMENTS, self)
			command.finished.connect(lambda code, text: self._store(kind, snapshots.snapshots_from_json(text)))
		elif kind == "news":
			self._read_news()
		elif kind == "old-snapshots":
			self._read_old_snapshots()
		elif kind == "guide":
			self._store(kind, guide.read_guide())

	@Slot(int, bool)
	def readJournal(self, boot, everyone):
		"""One start's problems, everyone's through sudo when asked, else only yours without a password."""
		if "journal" in self._reading:
			return
		self._reading.add("journal")
		self.readingChanged.emit()
		if not everyone:
			threading.Thread(target=lambda: self._collected.emit("journal", journal.collect(boot)), daemon=True).start()
			return
		shown = self._info.get("journal") or {"boot": boot, "everyone": False, "boots": [], "problems": []}

		def take(code, text):
			# A cancelled password keeps what the page showed rather than an empty list
			if code != EXIT_SUCCESS:
				self._store("journal", shown)
				return
			self._store("journal", dict(shown, boot=boot, everyone=True, problems=journal.problems_from_json(text)))
		run_as_root(self._root, journal.problems_arguments(boot), self).finished.connect(take)

	def _read_old_snapshots(self):
		"""How much the month old snapshots hold, read as root and only when asked, it takes about half a minute."""
		command = run_as_root(self._root, snapshots.SPACE_ARGUMENTS, self)
		command.finished.connect(lambda code, text: self._store("old-snapshots", snapshots.old_snapshots(text)
			if code == EXIT_SUCCESS else self._info.get("old-snapshots") or {"known": False}))

	@Slot()
	def readHardwareHistoryAsRoot(self):
		"""What was plugged in, through sudo, for when you may not read the system journal yourself yet."""
		if "hardware-history" in self._reading:
			return
		self._reading.add("hardware-history")
		self.readingChanged.emit()
		self._read_history_as_root()

	def _read_history_as_root(self):
		shown = self._info.get("hardware-history") or {"readable": False, "events": []}

		def take(code, text):
			if code != EXIT_SUCCESS:
				self._store("hardware-history", shown)
				return
			self._store("hardware-history", {"readable": True, "throughRoot": True, "checked": hardware_history.now(),
				"events": hardware_history.events_from_json(text)})
		run_as_root(self._root, hardware_history.arguments(), self).finished.connect(take)

	@Slot(result=bool)
	def journalNeedsPassword(self):
		return self._root.needsPassword()

	def _read_quietly(self, kind):
		"""Reads again without the busy spinner, for a page that follows changes while it shows."""
		threading.Thread(target=lambda: self._collected.emit(kind, COLLECTORS[kind]()), daemon=True).start()

	@Slot(bool)
	def watchHardware(self, watching):
		"""The hardware pages follow USB devices coming and going, each page that shows adds one watcher."""
		self._usb_watchers = max(0, self._usb_watchers + (1 if watching else -1))
		if self._usb_watchers and self._usb_monitor is None:
			self._usb_monitor = Command(USB_MONITOR_ARGUMENTS, parent=self, keep_output=False)
			self._usb_monitor.line.connect(self._usb_line)
			self._usb_monitor.finished.connect(lambda _code, _output: setattr(self, "_usb_monitor", None))
		elif not self._usb_watchers and self._usb_monitor is not None:
			self._usb_monitor.stop()
			self._usb_monitor = None

	def _usb_line(self, text):
		if " add " in text or " remove " in text:
			self._usb_settle.start()

	def _usb_changed(self):
		self._read_quietly("hardware")
		# A history read with the password is read the same way again, else it would fall back to unreadable
		if (self._info.get("hardware-history") or {}).get("throughRoot"):
			self._read_history_as_root()
		else:
			self._read_quietly("hardware-history")

	@Slot(bool)
	def watchPerformance(self, watching):
		"""The performance page reads every second while it shows, and nothing runs once it closes."""
		if watching:
			self.read("performance")
			self._performance_timer.start()
			self._start_pmon()
			return
		self._performance_timer.stop()
		if self._pmon is not None:
			self._pmon.stop()
			self._pmon = None

	def _start_pmon(self):
		"""Each app's share of an NVIDIA card comes from a pmon that runs as long as the page shows."""
		if self._pmon is not None or not shutil.which("nvidia-smi"):
			return
		self._pmon = Command(performance.PMON_ARGUMENTS, parent=self, keep_output=False)
		self._pmon.line.connect(self._take_pmon_line)
		self._pmon.finished.connect(lambda _code, _output: setattr(self, "_pmon", None))

	def _take_pmon_line(self, text):
		found = performance.pmon_line(text)
		if found:
			pid, usage, memory = found
			self._sampler.nvidia_usage[pid] = (usage, memory)

	@Slot(str, bool)
	def endApp(self, unit, force):
		"""Ending an app is your own business, so it runs at once without a password and the list looks again."""
		command = Command(performance.end_arguments(unit, force), parent=self)
		command.finished.connect(lambda _code, _output: self.read("performance"))

	@Slot(str, result=bool)
	def readNeedsPassword(self, kind):
		return kind in ("snapshots", "old-snapshots") and self._root.needsPassword()

	def _download(self, url, done):
		reply = self._network.get(QNetworkRequest(QUrl(url)))
		reply.finished.connect(lambda: (done(bytes(reply.readAll()).decode(errors="replace")), reply.deleteLater()))

	def _read_news(self):
		"""The feed and the newest snapshot come in on their own, the page fills in as each one arrives."""
		def take(key, value):
			self._store("news", dict(self._info.get("news") or {}, **{key: value}))
		self._download(news.NEWS_FEED, lambda text: take("stories", news.items_from_feed(text)))
		self._download(news.NEWEST_SNAPSHOT, lambda text: take("newest", news.snapshot_from_products(text)))

	@Slot(str, str)
	def readLog(self, scope, unit):
		arguments = services.log_arguments(scope, unit)
		if scope == services.SYSTEM:
			command = run_as_root(self._root, arguments, self)
		else:
			command = Command(arguments, parent=self)
		command.finished.connect(lambda code, text: self._store("log", {"unit": unit, "lines": text.strip()}))

	@Slot(str, result=bool)
	def logNeedsPassword(self, scope):
		return scope == services.SYSTEM and self._root.needsPassword()

	# Changing ===============================================================

	@Slot(str, str, result=bool)
	def needsPassword(self, action, argument):
		return any(step.root for step in ACTIONS[action](argument)) and self._root.needsPassword()

	@Slot(str, str, str)
	def run(self, kind, action, argument):
		"""Run the change as a job, then read the page that asked and the overview again."""
		def read_again():
			self.read(kind)
			if kind != "health":
				self.read("health")
		self._bridge.start_job(ACTIONS[action](argument), recheck=read_again)

	info = Property("QVariantMap", _get_info, notify=infoChanged)
	# The parts being read now, so each page can show that it is working
	reading = Property("QVariantList", _get_reading, notify=readingChanged)
