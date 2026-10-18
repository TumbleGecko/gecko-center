"""Where Gecko Center keeps its files and the names of the units it installs."""

import os
from pathlib import Path


def xdg_directory(variable, fallback):
	return Path(os.environ.get(variable) or Path.home() / fallback)


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent.parent
LAUNCHER = ROOT / "gecko-center.sh"
# The shared gecko parts, a copy of the gecko-ui repository made by its sync.sh
GECKO_UI = ROOT / "gecko-ui"
ASSETS = GECKO_UI / "assets"
QML = ROOT / "qml"
LANG = ROOT / "lang"
ICON = ASSETS / "gecko.png"
# The white gecko for the tray, which sits beside the panel's other monochrome icons
TRAY_ICON = ASSETS / "gecko-symbolic.png"

APPLICATION_NAME = "Gecko Center"
DESKTOP_ID = "gecko-center"

STATE_DIRECTORY = xdg_directory("XDG_STATE_HOME", ".local/state") / "gecko-center"
UPDATES_FILE = STATE_DIRECTORY / "updates.json"
# The window's size when it last closed
WINDOW_SIZE_FILE = STATE_DIRECTORY / "window.ini"
# How many updates the last notification told about, so a restarted tray does not tell again
NOTIFIED_FILE = STATE_DIRECTORY / "notified-count"
# The newest news story the tray told about, so each story is told about once
NEWS_SEEN_FILE = STATE_DIRECTORY / "news-seen"
# Its presence turns on a notification for each new openSUSE news story, the switch is in Settings
NEWS_NOTIFY_FILE = xdg_directory("XDG_CONFIG_HOME", ".config") / "gecko-center" / "notify-news"
# A full path, a plain name would go in TMPDIR and the session and its services can differ there
WINDOW_SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "gecko-center-window"
USER_UNITS = xdg_directory("XDG_CONFIG_HOME", ".config") / "systemd" / "user"
# Each repository's changelog file, kept until the repository publishes a new one
CHANGELOG_CACHE = xdg_directory("XDG_CACHE_HOME", ".cache") / "gecko-center" / "changelogs"

CHECK_SERVICE = "gecko-center-check.service"
CHECK_TIMER = "gecko-center-check.timer"
TRAY_SERVICE = "gecko-center-tray.service"
REFRESH_SERVICE = "gecko-center-refresh.service"
SYSTEM_UNIT = Path("/etc/systemd/system") / REFRESH_SERVICE
POLKIT_RULE = Path("/etc/polkit-1/rules.d/50-gecko-center.rules")
UPDATE_PLAN = Path("/var/cache/gecko-center/update-plan.xml")

# The full path skips the TumbleGecko guard in /usr/local/bin, it only blocks update and patch
ZYPPER = "/usr/bin/zypper"
FLATHUB = "flathub"
FLATHUB_REPOSITORY = "https://dl.flathub.org/repo/flathub.flatpakrepo"
