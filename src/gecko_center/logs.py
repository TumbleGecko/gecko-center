"""The errors in the journal for one start of the computer, grouped by kind and put in plain words.

Without root or the systemd-journal group the journal has only your own messages, else the system's too.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from . import look, performance

# The newest starts the page offers, an older one is rarely the one that matters
BOOT_COUNT = 8
# Each problem keeps its newest lines, enough to read what happened without holding thousands
KEPT_LINES = 30
LINE_LENGTH = 2000
# systemd-coredump marks each crash report with this message id, see systemd's catalog
CRASH_MESSAGE_ID = "fc2e22bc6ee647b6b90729ab34a250b1"
# Numbers, addresses and ids change between repeats of the same message
CHANGING = re.compile(r"0x[0-9a-f]+|[0-9a-f]{8,}|\d+", re.IGNORECASE)
KERNEL = "kernel"
# The system journal lives on disk, or only in memory on a system that keeps no logs across starts
JOURNAL_FOLDERS = (Path("/var/log/journal"), Path("/run/log/journal"))
# The system's own parts by the name they log under, said the way a person would
PART_NAMES = {"kernel": "Linux", "systemd": "System startup", "(sd-pam)": "Login", "sddm": "The login screen",
	"sddm-helper": "The login screen", "kwin_wayland": "The desktop", "kwin_x11": "The desktop",
	"plasmashell": "The desktop panel", "org_kde_powerdevil": "Power management", "powerdevil": "Power management",
	"pipewire": "Sound", "wireplumber": "Sound", "pipewire-pulse": "Sound", "NetworkManager": "The network",
	"bluetoothd": "Bluetooth", "kded6": "KDE background services", "ksmserver": "The desktop session",
	"polkitd": "Permissions", "sudo": "Administrator access", "udisksd": "Disks", "upowerd": "Power",
	"firewalld": "The firewall", "snapperd": "Snapshots", "zypper": "Software updates", "packagekitd": "Software updates",
	"xdg-desktop-portal": "App permissions", "dbus-broker": "System messaging", "busctl": "System messaging"}
# Some programs start each line with timers in brackets, which say nothing to a person
TIMER_PREFIX = re.compile(r"^(\[\s*[\d.]+\])+\s*")

# Messages people meet often, with a plain heading and what it means, {source} is the program that wrote it
EXPLAINED = (
	(r"segfault at", "{source} crashed",
		"It closed after reaching for memory it may not use, which is a fault in the program itself."),
	(r"out of memory|oom-kill|invoked oom-killer", "Memory ran out",
		"Linux stopped a program to free memory. Closing large apps keeps it from happening again."),
	(r"i/o error|ata\d+(\.\d+)?: (failed command|exception)|blk_update_request", "A disk had trouble reading or writing",
		"One read or write failed. If this repeats, back up important files and look at the disk on Hardware."),
	(r"direct firmware load for .* failed|firmware: failed to load", "A driver could not find its firmware",
		"The part may work with fewer features. The kernel-firmware packages supply most firmware."),
	(r"failed to start (.+?)\.?$", "{1} did not start",
		"The service stopped while starting. Its entry on Services shows its log and can start it again."),
	(r"acpi (bios )?error", "The motherboard firmware reported an error",
		"Many boards report these at every start without any effect. A firmware update can remove them."),
	(r"failed to initialize graphics backend|invalid framebuffer status", "{source} had trouble drawing",
		"This usually happens for a moment while a program starts or a screen changes."),
	(r"caller does not belong to any known session", "A program asked for a session it is not part of",
		"This happens when a program runs outside your desktop session, and is usually harmless."),
)
CRASH_HEADING = "{source} crashed"
CRASH_ABOUT = ("It closed unexpectedly and the system kept a crash report. "
	"A program that crashes again and again often needs an update.")
UNKNOWN_HEADING = "{source} reported a problem"


def boots_arguments():
	return ["journalctl", "--list-boots", "--output", "json", "--no-pager"]


def problems_arguments(boot):
	return ["journalctl", "--boot", str(boot), "--priority", "err", "--output", "json", "--no-pager"]


def _time(microseconds):
	return datetime.fromtimestamp(int(microseconds) / 1_000_000).isoformat(timespec="seconds")


def boots_from_json(text):
	"""The newest starts first, each with its index for journalctl and when it began and ended."""
	try:
		boots = json.loads(text or "[]")
	except ValueError:
		return []
	boots = sorted(boots, key=lambda boot: boot.get("index", 0), reverse=True)[:BOOT_COUNT]
	return [{"index": boot["index"], "start": _time(boot["first_entry"]), "end": _time(boot["last_entry"])}
		for boot in boots if "index" in boot and "first_entry" in boot and "last_entry" in boot]


def _message(entry):
	"""The journal stores a message with odd characters as a list of bytes."""
	message = entry.get("MESSAGE")
	if isinstance(message, list):
		message = bytes(message).decode("utf-8", errors="replace")
	return (message or "").strip()


def _source(entry, names):
	"""Who wrote the message, an app by its menu name and the system's parts by what they do."""
	if entry.get("_TRANSPORT") == KERNEL:
		return PART_NAMES[KERNEL]
	name = entry.get("COREDUMP_COMM") or entry.get("SYSLOG_IDENTIFIER") or entry.get("_COMM") or "Something"
	# The program that wrote the line, not the app that started it, a terminal starts many programs
	for desktop_id in (name, f"org.kde.{name}"):
		if names.name(desktop_id):
			return names.name(desktop_id)
	return PART_NAMES.get(name, name)


def _service(entry):
	"""The service that wrote the message, when Services can show it, with whose service it is."""
	for field, scope in (("_SYSTEMD_USER_UNIT", "user"), ("_SYSTEMD_UNIT", "system")):
		unit = entry.get(field, "")
		# A template instance such as user@1000.service, or an app the desktop started, is not a service to look at
		if unit.endswith(".service") and "@" not in unit and not unit.startswith("app-"):
			return unit, scope
	return "", ""


def _explained(entry, message, source):
	if entry.get("MESSAGE_ID") == CRASH_MESSAGE_ID:
		return "crash", CRASH_HEADING.format(source=source), CRASH_ABOUT
	for pattern, heading, about in EXPLAINED:
		found = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
		if found:
			# {1} in a heading is the pattern's first group, so the place before it holds the source
			heading = heading.format(source, *[part or "" for part in found.groups()], source=source)
			return "crash" if pattern == EXPLAINED[0][0] else "error", heading, about
	return "error", UNKNOWN_HEADING.format(source=source), ""


def problems_from_json(text):
	"""Each kind of problem once, with how often it happened, when, and its newest lines."""
	problems = {}
	names = performance.DesktopNames()
	for line in (text or "").splitlines():
		try:
			entry = json.loads(line)
		except ValueError:
			continue
		message = TIMER_PREFIX.sub("", _message(entry))
		if not message:
			continue
		source = _source(entry, names)
		kind, heading, about = _explained(entry, message, source)
		# A crash of one program is the same problem every time, other messages fold by their wording
		wording = "" if kind == "crash" else CHANGING.sub("#", message.splitlines()[0])
		key = hashlib.sha1(f"{source}\n{heading}\n{wording}".encode()).hexdigest()[:16]
		when = _time(entry.get("__REALTIME_TIMESTAMP", "0"))
		unit, scope = _service(entry)
		problem = problems.setdefault(key, {"key": key, "kind": kind, "heading": heading, "about": about,
			"source": source, "count": 0, "first": when, "last": when, "unit": unit, "scope": scope, "lines": []})
		problem["count"] += 1
		problem["last"] = when
		problem["lines"] = (problem["lines"] + [f"{when[5:10]} {when[11:]}  {message[:LINE_LENGTH]}"])[-KEPT_LINES:]
	# Crashes first, then what happened most, then what happened last
	return sorted(problems.values(), key=lambda problem: (problem["kind"] != "crash", -problem["count"],
		problem["last"]), reverse=False)


def reads_system_journal():
	"""Whether journalctl run as you sees the system's messages too, which needs the system journal readable."""
	return any(os.access(journal, os.R_OK) for folder in JOURNAL_FOLDERS for journal in folder.glob("*/system.journal"))


def collect(boot=0):
	"""What you may read without root, everyone's messages for a member of systemd-journal, else only yours."""
	boots = boots_from_json(look.run(boots_arguments()).stdout)
	return {"boot": boot, "everyone": reads_system_journal(), "boots": boots,
		"problems": problems_from_json(look.run(problems_arguments(boot)).stdout)}
