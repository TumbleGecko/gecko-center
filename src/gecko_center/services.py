"""The services that run in the background, yours and the system's, those that stopped with an error first."""

import re
import time
from datetime import datetime

from . import look, operations

# Apps started from the menu run as transient units, one that exits badly is the app's business, not the system's
# D-Bus starts small helpers on demand under names like dbus-:1.1-org.kde.kdeconnect@0, nobody manages those by hand
TRANSIENT_UNIT = re.compile(r"^(app-|drkonqi-|dbus-:)")
LOG_LINES = 30
SYSTEM = "system"
USER = "user"
SCOPE_ARGUMENTS = {SYSTEM: [], USER: ["--user"]}
DETAIL_PROPERTIES = "Id,UnitFileState,ActiveEnterTimestamp,StateChangeTimestamp,Result"
MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR

# What kind of thing each service looks after, matched on its unit name, first match wins
# The marks all come from DejaVu Sans, the one symbol font the rail uses too
# None has a colour emoji form, Qt draws those from the emoji font whatever font the text asks for
KINDS = [
	("♪", r"pipewire|pulse|wireplumber|filter-chain|rtkit|alsa|audio|sound|arctis"),
	("⇄", r"network|modemmanager|wpa_|avahi|resolved|dhcp|nscd|sshd|obex|bluetooth|kdeconnect|samba|smb|nfs"),
	("◈", r"firewall|polkit|audit|apparmor|tpm|keyring|wallet|sssd|secret"),
	("⛁", r"udisks|smartd|btrfs|snapper|fstrim|lvm|mdmonitor|fsck|storage|gvfs|baloo"),
	("▣", r"display|sddm|kwin|plasma|kscreen|xdg-desktop|nvidia|getty|at-spi|kaccess|nighttime"),
	("↯", r"power|thermal|tuned|acpi|irqbalance|switcheroo"),
	("◷", r"chrony|ntp|timesync|cron"),
	("⟳", r"packagekit|zypp|update|flatpak|fwupd|purge-kernel|gecko-center"),
	("☰", r"cups|print"),
	("✉", r"dbus|akonadi|mail|postfix|dconf|kalendar"),
	("⌨", r"udev|input|ratbag|bolt|mcelog|logind|qmk|kameleon"),
]
OTHER_KIND = "⚙"

# Why a service stopped, by systemd's own result word
FAILURES = {
	"exit-code": "It stopped with an error",
	"signal": "It crashed",
	"core-dump": "It crashed",
	"timeout": "It took too long to start",
	"oom-kill": "It ran out of memory",
	"watchdog": "It stopped responding",
	"start-limit-hit": "It failed too often in a row and was given up on",
	"resources": "It could not get what it needs to start",
}
# Whether a service starts on its own, by its unit file state
STARTS = {
	"enabled": {SYSTEM: "Starts with the computer", USER: "Starts when you log in"},
	"enabled-runtime": {SYSTEM: "Starts with the computer", USER: "Starts when you log in"},
}
STARTED_WHEN_NEEDED = "Started when needed"


def _failed(scope):
	listing = look.run(["systemctl", *SCOPE_ARGUMENTS[scope], "--failed", "--plain", "--no-legend", "--no-pager"])
	units = []
	for line in listing.stdout.splitlines():
		name = line.split(maxsplit=1)[0] if line.strip() else ""
		if name and not TRANSIENT_UNIT.match(name):
			units.append(name)
	return units


def failed_units():
	"""The failed units by scope, the system ones need root to clear or start."""
	return {SYSTEM: _failed(SYSTEM), USER: _failed(USER)}


def _kind(unit):
	return next((mark for mark, pattern in KINDS if re.search(pattern, unit, re.IGNORECASE)), OTHER_KIND)


def _duration(seconds):
	"""A length of time in the largest whole unit, such as 3 days or 12 minutes."""
	for size, word in ((DAY, "day"), (HOUR, "hour"), (MINUTE, "minute")):
		if seconds >= size:
			return look.plural(int(seconds // size), word)
	return "a moment"


def _since(changed, failed):
	if not changed:
		return ""
	if failed:
		return "Failed " + datetime.fromtimestamp(changed).strftime("%Y-%m-%d at %H:%M")
	return "Running for " + _duration(time.time() - changed)


def _details(scope, units):
	"""When each service last changed, whether it starts on its own and why a failed one stopped, in one call."""
	if not units:
		return {}
	shown = look.run(["systemctl", *SCOPE_ARGUMENTS[scope], "show", "--timestamp=unix",
		"--property=" + DETAIL_PROPERTIES, "--", *units])
	details = {}
	for block in shown.stdout.split("\n\n"):
		fields = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
		if "Id" in fields:
			details[fields["Id"]] = fields
	return details


def _listed(scope):
	"""Each running or failed service in one systemctl call, apps and crash reports left out as above."""
	listing = look.run(["systemctl", *SCOPE_ARGUMENTS[scope], "list-units", "--type=service", "--all", "--plain",
		"--no-legend", "--no-pager"])
	found = []
	for line in listing.stdout.splitlines():
		fields = line.split(None, 4)
		if len(fields) < 4 or TRANSIENT_UNIT.match(fields[0]):
			continue
		unit, _load, active, sub = fields[:4]
		if active == "failed" or sub == "running":
			found.append({"unit": unit, "scope": scope, "failed": active == "failed",
				"description": fields[4].strip() if len(fields) > 4 else unit, "kind": _kind(unit)})
	details = _details(scope, [service["unit"] for service in found])
	for service in found:
		fields = details.get(service["unit"], {})
		# A reload also counts as a state change, so a running service is timed from when it started
		changed = int(fields.get("StateChangeTimestamp" if service["failed"] else "ActiveEnterTimestamp", "")
			.lstrip("@") or 0)
		starts = STARTS.get(fields.get("UnitFileState", ""), {}).get(scope, STARTED_WHEN_NEEDED)
		reason = FAILURES.get(fields.get("Result", ""), "") if service["failed"] else ""
		service["facts"] = [part for part in (reason, _since(changed, service["failed"]), starts) if part]
	return found


def collect():
	"""Failed ones first, then yours, then the system's, each by name."""
	found = _listed(USER) + _listed(SYSTEM)
	found.sort(key=lambda service: (not service["failed"], service["scope"] != USER, service["description"].lower()))
	return {"services": found, "failed": [service for service in found if service["failed"]]}


def log_arguments(scope, unit):
	"""Your own services' logs are yours to read, the system's need root."""
	return ["journalctl", *SCOPE_ARGUMENTS[scope], "--unit", unit, "--lines", str(LOG_LINES), "--no-pager",
		"--output", "short"]


def stop_steps(scope, unit):
	return [operations.Step("Stopping " + unit, ["systemctl", *SCOPE_ARGUMENTS[scope], "stop", "--", unit],
		root=scope == SYSTEM)]


def restart_steps(scope, unit):
	return [operations.Step("Starting " + unit + " again",
		["systemctl", *SCOPE_ARGUMENTS[scope], "restart", unit], root=scope == SYSTEM)]
