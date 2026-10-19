"""How healthy the system is, looked at with read only checks that need no password.

Each check gives a state, a sentence and the details behind it, and names the one action that helps, if any.
"""

import os
import platform
import re
from datetime import date, datetime
from pathlib import Path

from . import drivers, look, memory, paths, performance, services, sources, storage, updates

# The states from best to worst, the page shows the worst first
GOOD = "good"
NOTE = "note"
WARNING = "warning"
PROBLEM = "problem"
STATES = (GOOD, NOTE, WARNING, PROBLEM)

GIGABYTE = 1024 ** 3
# Below these a full Tumbleweed update with its snapshot may not fit
DISK_PROBLEM_BYTES = 5 * GIGABYTE
DISK_WARNING_BYTES = 15 * GIGABYTE
DISK_WARNING_SHARE = 0.10
# A snapshot older than this has fallen far behind, and big jumps are where updates go wrong
OLD_SNAPSHOT_DAYS = 30

OS_RELEASE = Path("/etc/os-release")
# The display server the session runs on, as logind names it in XDG_SESSION_TYPE
SESSION_NAMES = {"wayland": "Wayland", "x11": "X11"}
KERNEL_MODULES = Path("/usr/lib/modules")
SNAPPER_ROOT_CONFIG = Path("/etc/snapper/configs/root")
# Timers openSUSE enables to keep a Btrfs system and its snapshots healthy
MAINTENANCE_TIMERS = {
	"btrfs-scrub.timer": "Checking the disk for damaged data",
	"btrfs-balance.timer": "Keeping free space usable",
	"fstrim.timer": "Telling the SSD which blocks are free",
	"snapper-cleanup.timer": "Removing old snapshots",
}
BTRFS_ONLY = ("btrfs-scrub.timer", "btrfs-balance.timer", "snapper-cleanup.timer")
ZYPPER_EXIT_REBOOT_NEEDED = 102


# The page that shows each check in full, so a check that is fine still opens somewhere
CHECK_PAGES = {"updates": "updates", "restart": "updates", "disk": "storage", "snapshots": "snapshots",
	"services": "services", "sources": "sources", "graphics": "drivers", "maintenance": "services",
	"firewall": "services"}


def _check(check_id, title, state, summary, details=None, action=""):
	return {"id": check_id, "title": title, "state": state, "summary": summary, "details": details or [],
		"action": action, "page": CHECK_PAGES.get(check_id, "")}


def _os_release():
	values = {}
	if OS_RELEASE.exists():
		for line in OS_RELEASE.read_text().splitlines():
			key, _, value = line.partition("=")
			values[key] = value.strip().strip('"')
	return values


def _snapshot_date(release):
	"""Tumbleweed names each snapshot by its date, such as 20261009."""
	version = release.get("VERSION_ID", "")
	if not re.fullmatch(r"\d{8}", version):
		return None
	return datetime.strptime(version, "%Y%m%d").date()


def _version_key(name):
	return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def _filesystem(path, column):
	found = look.run(["findmnt", "--noheadings", "--output", column, "--target", str(path)])
	return found.stdout.strip()


# Checks ======================================================================


def check_updates(release):
	state = updates.read_state()
	pending = updates.pending_count(state)
	snapshot = _snapshot_date(release)
	details = []
	if snapshot:
		age = (date.today() - snapshot).days
		details.append(f"The system is snapshot {release['VERSION_ID']}, from {look.plural(age, 'day')} ago.")
	if state.get("checked"):
		details.append(f"Last looked for updates {state['checked'][:16].replace('T', ' at ')}.")

	if snapshot and (date.today() - snapshot).days > OLD_SNAPSHOT_DAYS:
		return _check("updates", "Updates", WARNING, "The system has not been updated in over a month.",
			details + ["Tumbleweed moves fast, and the further behind it falls the harder the next update gets."],
			"page:updates")
	if pending:
		return _check("updates", "Updates", NOTE, f"{look.plural(pending, 'update')} ready to install.", details,
			"page:updates")
	if not state.get("checked"):
		return _check("updates", "Updates", NOTE, "Not looked for updates yet.", details, "page:updates")
	return _check("updates", "Updates", GOOD, "Up to date.", details)


def check_restart():
	running = platform.release()
	kernels = sorted((entry.name for entry in KERNEL_MODULES.iterdir() if (entry / "vmlinuz").exists()),
		key=_version_key) if KERNEL_MODULES.exists() else []
	newest = kernels[-1] if kernels else running
	flagged = look.run([paths.ZYPPER, "needs-rebooting"]).returncode == ZYPPER_EXIT_REBOOT_NEEDED
	if newest != running:
		return _check("restart", "Restart", WARNING, "A newer Linux kernel waits for a restart.",
			[f"Running {running}, installed {newest}."], "restart")
	if flagged:
		return _check("restart", "Restart", WARNING, "An update changed core parts that start fresh after a restart.",
			[], "restart")
	return _check("restart", "Restart", GOOD, "No restart needed.", [f"Running Linux {running}."])


def check_disk():
	worst = GOOD
	details = []
	for place in storage.places():
		details.append(f"{place['label']}  {place['freeText']} free of {place['totalText']}")
		if place["free"] < DISK_PROBLEM_BYTES:
			worst = PROBLEM
		elif (place["free"] < DISK_WARNING_BYTES or place["free"] / place["total"] < DISK_WARNING_SHARE) \
				and worst == GOOD:
			worst = WARNING
	summary = {GOOD: "Plenty of free space.", WARNING: "Free space is running low.",
		PROBLEM: "The disk is almost full, updates may fail."}[worst]
	return _check("disk", "Disk space", worst, summary, details, "" if worst == GOOD else "page:storage")


def check_snapshots(root_type):
	if root_type != "btrfs":
		return _check("snapshots", "Snapshots", NOTE, "The system disk has no snapshots.",
			[f"The system disk uses {root_type or 'an unknown file system'}, snapshots need Btrfs."])
	if not SNAPPER_ROOT_CONFIG.exists():
		return _check("snapshots", "Snapshots", WARNING, "Snapshots are turned off.",
			["Without them an update that goes wrong cannot be undone."])
	return _check("snapshots", "Snapshots", GOOD, "Every update can be undone.",
		["A snapshot is saved before and after each software change."], "page:snapshots")


def check_services():
	failed = services.failed_units()
	count = len(failed[services.SYSTEM]) + len(failed[services.USER])
	if count == 0:
		return _check("services", "Services", GOOD, "Every service runs as it should.")
	details = [f"{name}  (system)" for name in failed[services.SYSTEM]] + [f"{name}  (yours)"
		for name in failed[services.USER]]
	return _check("services", "Services", WARNING, f"{look.plural(count, 'service')} failed.", details,
		"page:services")


def check_firewall():
	if look.run(["systemctl", "is-active", "--quiet", "firewalld.service"]).returncode == 0:
		return _check("firewall", "Firewall", GOOD, "The firewall is on.")
	return _check("firewall", "Firewall", PROBLEM, "The firewall is off.",
		["Other machines on the network can reach every open port."], "firewall-on")


def check_sources():
	found = sources.read_sources()
	if found is None:
		return _check("sources", "Software sources", WARNING, "The software sources could not be read.", [],
			"page:sources")
	enabled = [source for source in found if source["enabled"]]
	others = [source["name"] for source in enabled if source["kind"] != sources.OPENSUSE]
	if not any(source["kind"] == sources.OPENSUSE for source in enabled):
		return _check("sources", "Software sources", PROBLEM, "No openSUSE source is turned on.",
			["Without one the system cannot be updated."], "page:sources")
	if not others:
		return _check("sources", "Software sources", GOOD, "Everything comes from openSUSE.")
	risky = [source["name"] for source in enabled if source["risks"]]
	if risky:
		return _check("sources", "Software sources", WARNING,
			f"{look.plural(len(risky), 'source')} could cause trouble.", risky, "page:sources")
	return _check("sources", "Software sources", NOTE,
		f"{look.plural(len(others), 'source')} from outside openSUSE.",
		["They are built by others and are the most common cause of update conflicts."], "page:sources")


def check_graphics():
	cards = drivers.graphics_cards()
	missing = [card["name"] for card in cards if card["wantsNvidia"]]
	if missing:
		return _check("graphics", "Graphics", WARNING, "The NVIDIA driver is not installed.",
			["The card works without it, but slowly."] + missing, "page:drivers")
	return _check("graphics", "Graphics", GOOD, "The graphics driver is in place.",
		[f"{card['name']}  {card['driver'] or 'no driver'}" for card in cards])


def check_maintenance(root_type):
	wanted = [timer for timer in MAINTENANCE_TIMERS if root_type == "btrfs" or timer not in BTRFS_ONLY]
	states = look.run(["systemctl", "is-enabled", *wanted]).stdout.split()
	off = [timer for timer, state in zip(wanted, states) if state not in ("enabled", "static")]
	details = [f"{MAINTENANCE_TIMERS[timer]}  {'off' if timer in off else 'on'}" for timer in wanted]
	if off:
		return _check("maintenance", "Maintenance", WARNING, f"{look.plural(len(off), 'regular cleanup')} turned off.",
			details)
	return _check("maintenance", "Maintenance", GOOD, "Disk checks and cleanups run on their own.", details)


def _memory():
	return memory.size_text(memory.installed_bytes())


def _processor():
	for line in Path("/proc/cpuinfo").read_text().splitlines():
		if line.startswith("model name"):
			return line.split(":", 1)[1].strip()
	return platform.machine()


def _graphics():
	"""Each graphics card with its memory in the GB its box names and the NVIDIA driver version, otherwise the name lspci knows."""
	cards = performance.graphics_cards()
	if cards:
		version = drivers.nvidia_version()
		return "\n".join(f"{card['name']}  ·  {memory.size_text(memory.sold_bytes(card['memoryTotal']))}"
			+ (f"  ·  Driver {version}" if version and "NVIDIA" in card["name"] else "") for card in cards)
	return "\n".join(card["name"] for card in drivers.graphics_cards())


def describe_machine(release):
	desktop = look.run(["plasmashell", "--version"]).stdout.strip().replace("plasmashell", "KDE Plasma")
	session = SESSION_NAMES.get(os.environ.get("XDG_SESSION_TYPE", ""))
	if desktop and session:
		desktop += f" ({session})"
	return {
		"system": release.get("PRETTY_NAME") or release.get("NAME", "Linux"),
		"snapshot": release.get("VERSION_ID", ""),
		"kernel": platform.release(),
		"desktop": desktop,
		"graphics": _graphics(),
		"processor": _processor(),
		"memory": _memory(),
	}


def collect():
	"""Every check, worst first, and a short description of the machine."""
	release = _os_release()
	root_type = _filesystem("/", "FSTYPE")
	checks = [check_updates(release), check_restart(), check_disk(), check_snapshots(root_type), check_services(),
		check_firewall(), check_sources(), check_graphics(), check_maintenance(root_type)]
	checks.sort(key=lambda check: -STATES.index(check["state"]))
	return {"machine": describe_machine(release), "checks": checks, "checked": updates.now()}
