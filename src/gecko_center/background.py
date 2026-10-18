"""The lazy background check, a user timer that wakes now and then, and the tray unit that starts with every login.

Refreshing package lists needs root, so one fixed system unit does it and a polkit rule lets this user start it.
The unit runs only zypper from /usr/bin, never a file the user can edit, so starting it grants nothing more.
"""

import getpass
import re
import subprocess
from pathlib import Path

from . import paths, updates

EXIT_SUCCESS = 0
INTERVALS = ("daily", "weekly", "monthly")
DEFAULT_INTERVAL = "weekly"


def _quoted(path):
	return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def refresh_unit():
	plan = paths.UPDATE_PLAN
	plan_command = " ".join(updates.PLAN_ARGUMENTS)
	return f"""[Unit]
Description=Refresh the package lists and plan the next update for Gecko Center
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
Nice=19
IOSchedulingClass=idle
UMask=0022
CacheDirectory={plan.parent.name}
ExecStart={" ".join(updates.REFRESH_ARGUMENTS)}
ExecStart=/bin/sh -c '{plan_command} > {plan}.new; mv {plan}.new {plan}'
"""


def polkit_rule(user):
	return f"""// Lets {user} start the Gecko Center refresh without a password, it only refreshes package lists
polkit.addRule(function(action, subject) {{
	if (action.id == "org.freedesktop.systemd1.manage-units"
		&& action.lookup("unit") == "{paths.REFRESH_SERVICE}"
		&& action.lookup("verb") == "start"
		&& subject.user == "{user}") {{
		return polkit.Result.YES;
	}}
}});
"""


def check_service():
	return f"""[Unit]
Description=Look for updates for Gecko Center

[Service]
Type=oneshot
Nice=19
ExecStart={_quoted(paths.LAUNCHER)} --check
"""


def check_timer(interval):
	return f"""[Unit]
Description=Look for updates for Gecko Center now and then

[Timer]
OnCalendar={interval}
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
"""


def tray_service():
	return f"""[Unit]
Description=Show the Gecko Center tray icon
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart={_quoted(paths.LAUNCHER)} --tray

[Install]
WantedBy=graphical-session.target
"""


def current_interval():
	"""The timer file is the one record of the interval, an empty string means the check is off."""
	timer = paths.USER_UNITS / paths.CHECK_TIMER
	if not timer.exists():
		return ""
	found = re.search(r"^OnCalendar=(\S+)", timer.read_text(), re.MULTILINE)
	return found.group(1) if found else DEFAULT_INTERVAL


def write_system_files(directory):
	"""Write the root files into a folder and return the arguments that install them as root."""
	directory = Path(directory)
	unit = directory / paths.SYSTEM_UNIT.name
	rule = directory / paths.POLKIT_RULE.name
	unit.write_text(refresh_unit())
	rule.write_text(polkit_rule(getpass.getuser()))
	script = 'install -D -m 0644 "$1" "$2" && install -D -m 0644 "$3" "$4" && systemctl daemon-reload'
	return ["/bin/sh", "-c", script, "sh", str(unit), str(paths.SYSTEM_UNIT), str(rule), str(paths.POLKIT_RULE)]


def remove_system_arguments():
	script = 'rm -f "$1" "$2" && systemctl daemon-reload'
	return ["/bin/sh", "-c", script, "sh", str(paths.SYSTEM_UNIT), str(paths.POLKIT_RULE)]


def _systemctl_user(*arguments):
	return subprocess.run(["systemctl", "--user", *arguments], capture_output=True, check=False).returncode


def install_user_units(interval):
	if interval not in INTERVALS:
		raise ValueError(f"interval must be one of {', '.join(INTERVALS)}")
	paths.USER_UNITS.mkdir(parents=True, exist_ok=True)
	(paths.USER_UNITS / paths.CHECK_SERVICE).write_text(check_service())
	(paths.USER_UNITS / paths.CHECK_TIMER).write_text(check_timer(interval))
	_systemctl_user("daemon-reload")
	return _systemctl_user("enable", "--now", paths.CHECK_TIMER)


def install_tray_unit():
	"""The tray starts with every login whether the background check is on or not, it is the way back to the window."""
	paths.USER_UNITS.mkdir(parents=True, exist_ok=True)
	unit = paths.USER_UNITS / paths.TRAY_SERVICE
	if unit.exists() and unit.read_text() == tray_service():
		return _systemctl_user("enable", "--now", paths.TRAY_SERVICE)
	unit.write_text(tray_service())
	_systemctl_user("daemon-reload")
	_systemctl_user("enable", paths.TRAY_SERVICE)
	# A tray already running from an older unit picks up the new one
	return _systemctl_user("restart", paths.TRAY_SERVICE)


def remove_user_units():
	_systemctl_user("disable", "--now", paths.CHECK_TIMER)
	for name in (paths.CHECK_SERVICE, paths.CHECK_TIMER):
		(paths.USER_UNITS / name).unlink(missing_ok=True)
	return _systemctl_user("daemon-reload")
