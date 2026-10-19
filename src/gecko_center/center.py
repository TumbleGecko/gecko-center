"""What the system pages read and change, from health, hardware and snapshots to drivers, storage, services and news.

Reading runs beside the window so it stays smooth, changes run as jobs through the main bridge with their progress.
"""

import shutil
import threading

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from . import (drivers, guide, hardware, health, logs, news, operations, performance, report, services, snapshots,
	sources, storage)
from .commands import Command, run_as_root

EXIT_SUCCESS = 0
# How often the performance page looks again, in milliseconds
PERFORMANCE_INTERVAL = 1000

# Each look that needs no root, run on a thread of its own
COLLECTORS = {
	"health": health.collect,
	"sources": lambda: {"sources": sources.read_sources()},
	"source-packages": lambda: {"packages": sources.installed_by_source()},
	"report": report.share,
	"drivers": drivers.collect,
	"hardware": hardware.collect,
	"logs": logs.collect,
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
		elif kind == "guide":
			self._store(kind, guide.read_guide())

	@Slot(int, bool)
	def readLogs(self, boot, everyone):
		"""One start's problems, everyone's through sudo when asked, else only yours without a password."""
		if "logs" in self._reading:
			return
		self._reading.add("logs")
		self.readingChanged.emit()
		if not everyone:
			threading.Thread(target=lambda: self._collected.emit("logs", logs.collect(boot)), daemon=True).start()
			return
		shown = self._info.get("logs") or {"boot": boot, "everyone": False, "boots": [], "problems": []}

		def take(code, text):
			# A cancelled password keeps what the page showed rather than an empty list
			if code != EXIT_SUCCESS:
				self._store("logs", shown)
				return
			self._store("logs", dict(shown, boot=boot, everyone=True, problems=logs.problems_from_json(text)))
		run_as_root(self._root, logs.problems_arguments(boot), self).finished.connect(take)

	@Slot(result=bool)
	def logsNeedPassword(self):
		return self._root.needsPassword()

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
		return kind == "snapshots" and self._root.needsPassword()

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
