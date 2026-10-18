"""The white gecko in the tray, always there, with a dot and one notification when updates wait or news arrives.

Plasma shows a QSystemTrayIcon as a StatusNotifierItem.
The notification comes from notify-send, Qt's own sends no default action so clicking it would do nothing.
"""

import os
import secrets
import subprocess
import sys

from PySide6.QtCore import QFileSystemWatcher, QPointF, QProcess, QProcessEnvironment, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import news, paths, updates

EXIT_SUCCESS = 0
ACTIVATION_VARIABLE = "XDG_ACTIVATION_TOKEN"
ICON_SIZE = 64
# The dot sits in the lower right corner, in the gecko green so it reads as news, not as an error
DOT_COLOR = "#6cc070"
DOT_RADIUS = 13
# How often the tray reads the news feed while news notifications are on, in milliseconds
NEWS_INTERVAL = 6 * 60 * 60 * 1000


def _describe(state):
	system = (state.get("system") or {}).get("count", 0)
	flatpaks = len(state.get("flatpak") or [])
	parts = []
	if system:
		parts.append(f"{system} system package{'s' if system != 1 else ''}")
	if flatpaks:
		parts.append(f"{flatpaks} Flatpak update{'s' if flatpaks != 1 else ''}")
	return " and ".join(parts) + " can be updated."


def _tooltip(state):
	if updates.pending_count(state) > 0:
		return "Updates are ready\n" + _describe(state)
	return "Gecko Center"


def _icon(pending):
	pixmap = QIcon(str(paths.TRAY_ICON)).pixmap(ICON_SIZE, ICON_SIZE)
	if not pending:
		return QIcon(pixmap)
	painter = QPainter(pixmap)
	painter.setRenderHint(QPainter.RenderHint.Antialiasing)
	painter.setPen(Qt.PenStyle.NoPen)
	painter.setBrush(QColor(DOT_COLOR))
	painter.drawEllipse(QPointF(ICON_SIZE - DOT_RADIUS, ICON_SIZE - DOT_RADIUS), DOT_RADIUS, DOT_RADIUS)
	painter.end()
	return QIcon(pixmap)


def _window_unit():
	"""The window runs in an app unit of its own, as the app menu would start it, not inside the tray's unit.

	Inside the tray's unit a restart of the tray would close the window too, and its use would count as the tray's.
	The name follows https://systemd.io/DESKTOP_ENVIRONMENTS/ with the dash in the id escaped the way systemd does.
	"""
	return "app-" + paths.DESKTOP_ID.replace("-", "\\x2d") + "-" + secrets.token_hex(8) + ".scope"


def _open_page(page, token=""):
	"""KWin only lets a window come to the front with the activation token the click produced, so it goes along."""
	environment = dict(os.environ)
	environment.pop(ACTIVATION_VARIABLE, None)
	if token:
		environment[ACTIVATION_VARIABLE] = token
	subprocess.Popen(["systemd-run", "--user", "--scope", "--collect", "--quiet", "--unit", _window_unit(), "--",
		str(paths.LAUNCHER), "--page", page], start_new_session=True, env=environment)


def _open_from_tray(page):
	"""Plasma hands the tray its click's token before the click itself, and Qt keeps it in the environment.

	KDE sets it in the process environment, and Python's os.environ copy does not follow such changes.
	"""
	token = QProcessEnvironment.systemEnvironment().value(ACTIVATION_VARIABLE)
	os.unsetenv(ACTIVATION_VARIABLE)
	_open_page(page, token)


def _notification_closed(output, page):
	"""notify-send prints the notification id, then the click's activation token, then the action."""
	lines = output.decode(errors="replace").splitlines()
	if "default" not in lines:
		return
	token = lines[1] if len(lines) > 2 and lines[1] != "default" else ""
	_open_page(page, token)


def _notify(parent, page, action, title, body):
	"""Clicking the notification opens the page, notify-send prints the action it was given."""
	notification = QProcess(parent)
	notification.finished.connect(lambda: _notification_closed(bytes(notification.readAllStandardOutput()), page))
	# The id comes first in the output, it names the notification for the logs and for tests
	notification.start("notify-send", ["--print-id", "--activation-token-fd", "1",
		"--app-name", paths.APPLICATION_NAME, "--icon", str(paths.ICON),
		"--hint", f"string:desktop-entry:{paths.DESKTOP_ID}", "--action", f"default={action}", title, body])
	return notification


def _new_stories(stories):
	"""The stories newer than the one told about last, none the first time so an old feed does not flood in."""
	try:
		seen = paths.NEWS_SEEN_FILE.read_text().strip()
	except OSError:
		seen = ""
	if not seen:
		return []
	links = [story["link"] for story in stories]
	# A story told about long ago may have left the feed, then only the newest is told about
	return stories[:links.index(seen)] if seen in links else stories[:1]


def _read_notified():
	try:
		return int(paths.NOTIFIED_FILE.read_text())
	except (OSError, ValueError):
		return 0


class Tray:
	"""The icon and its menu, following the saved check so it changes the moment a look or an update ends."""

	def __init__(self, application):
		self._application = application
		self._icon = QSystemTrayIcon()
		self._menu = QMenu()
		self._pending = 0
		self._fill_menu()
		self._icon.setContextMenu(self._menu)
		self._icon.activated.connect(self._clicked)
		# The folder is watched rather than the file, a save replaces the file and would end a file watch
		paths.STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
		self._watcher = QFileSystemWatcher([str(paths.STATE_DIRECTORY)])
		self._watcher.directoryChanged.connect(lambda _path: self._follow_state())
		self._follow_state()
		self._network = QNetworkAccessManager()
		self._news_timer = QTimer()
		self._news_timer.setInterval(NEWS_INTERVAL)
		self._news_timer.timeout.connect(self._read_news)
		self._news_timer.start()
		self._read_news()
		self._icon.show()

	def _fill_menu(self):
		entries = [("Show updates", lambda: _open_from_tray("updates")),
			("Open Gecko Center", lambda: _open_from_tray("overview")),
			("Find apps", lambda: _open_from_tray("explore")),
			("Look for updates now", self._look_now),
			("Hide until next login", self._application.quit)]
		for text, action in entries:
			item = QAction(text, self._menu)
			item.triggered.connect(action)
			self._menu.addAction(item)
		self._show_updates = self._menu.actions()[0]

	def _clicked(self, reason):
		if reason == QSystemTrayIcon.ActivationReason.Trigger:
			_open_from_tray("updates" if self._pending else "overview")

	def _look_now(self):
		subprocess.Popen([str(paths.LAUNCHER), "--check"], start_new_session=True, stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL)

	def _follow_state(self):
		"""A count that grows past the one told about last brings a notification, so each batch is told about once."""
		state = updates.read_state()
		pending = updates.pending_count(state)
		notified = _read_notified()
		if pending > notified:
			_notify(self._application, "updates", "Show updates", "Updates are ready", _describe(state))
		if pending != notified:
			paths.NOTIFIED_FILE.write_text(str(pending))
		self._pending = pending
		self._icon.setIcon(_icon(pending > 0))
		self._icon.setToolTip(_tooltip(state))
		self._show_updates.setVisible(pending > 0)


	def _read_news(self):
		if not paths.NEWS_NOTIFY_FILE.exists():
			return
		reply = self._network.get(QNetworkRequest(QUrl(news.NEWS_FEED)))
		reply.finished.connect(lambda: (self._tell_news(bytes(reply.readAll()).decode(errors="replace")),
			reply.deleteLater()))

	def _tell_news(self, text):
		"""The newest story names the notification, a count says when more came with it."""
		stories = news.items_from_feed(text)
		if not stories:
			return
		fresh = _new_stories(stories)
		if fresh:
			more = f"\n{len(fresh) - 1} more on the News page." if len(fresh) > 1 else ""
			_notify(self._application, "news", "Read news", "openSUSE news", fresh[0]["title"] + more)
		paths.STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
		paths.NEWS_SEEN_FILE.write_text(stories[0]["link"])


def main():
	application = QApplication(sys.argv)
	application.setApplicationName(paths.APPLICATION_NAME)
	application.setDesktopFileName(paths.DESKTOP_ID)
	application.setQuitOnLastWindowClosed(False)
	# The application holds the tray so it lives as long as the event loop
	application.tray = Tray(application)
	return application.exec()
