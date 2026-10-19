"""Snapper's snapshots of the system disk, told in plain words, and rolling back to one of them.

Listing them needs root, since the root configuration allows no other users, and so does zypper's history.
Rolling back follows snapper rollback, https://doc.opensuse.org/documentation/leap/reference/html/book-reference/cha-snapper.html
"""

import json
import re
from datetime import datetime, timedelta

from . import look, operations

# One root run reads snapper's list, each snapshot's Tumbleweed release and kernels, and zypper's package history
# Sizes are left out, snapper works them out from Btrfs quotas and that takes half a minute
READ_SCRIPT = r"""
snapper --jsonout list --columns number,type,pre-number,date,description,default,active,cleanup,userdata
for snapshot in /.snapshots/*/snapshot; do
	number="${snapshot%/snapshot}"
	printf '@@snapshot %s\n' "${number##*/}"
	grep -h '^VERSION_ID=' "${snapshot}/usr/lib/os-release" 2>/dev/null
	ls "${snapshot}/usr/lib/modules" 2>/dev/null
done
printf '@@history\n'
grep -E '^[^|]*[|](install|remove )[|]' /var/log/zypp/history 2>/dev/null
"""
LIST_ARGUMENTS = ["sh", "-c", READ_SCRIPT]
# The sizes on their own, for Storage, read only when asked since snapper takes about half a minute for them
SPACE_ARGUMENTS = ["snapper", "--jsonout", "list", "--columns", "number,type,pre-number,date,default,active,used-space"]
# Snapshots older than this are offered for removal, a month covers going back after any recent update
OLD_DAYS = 30

# What made each snapshot, matched against snapper's own description
REASONS = [
	(r"^zypp\(", "the software change"),
	(r"^timeline$", "the hourly timeline"),
	(r"^after installation$", "the end of the installation"),
	(r"^first root filesystem$", "the first start"),
	(r"^rollback backup of #(\d+)$", "rolling back to snapshot {1}"),
	(r"^writable copy of #(\d+)$", "rolling back to snapshot {1}"),
]

# How long snapper keeps a snapshot, by its cleanup rule
KEPT = {
	"": "Until it is removed by hand",
	"number": "Until enough newer software changes replace it",
	"timeline": "Until it gets old",
}
IMPORTANT_KEPT = "Kept longer than most, because the change touched important parts such as the kernel"


def _when(date):
	return date[:16].replace(" ", " at ")


def _reason(description):
	for pattern, words in REASONS:
		found = re.match(pattern, description)
		if found:
			return words.replace("{1}", found.group(1)) if found.groups() else words
	return description or "a manual snapshot"


def _title(snapshot, pre):
	"""Before and after snapshots share the reason of the before one, snapper leaves the after one blank."""
	reason = _reason((pre or snapshot).get("description", ""))
	when = _when(snapshot.get("date", ""))
	if snapshot["type"] == "pre":
		return f"Before {reason} on {when}"
	if snapshot["type"] == "post":
		return f"After {reason} on {when}"
	return f"Made by {reason} on {when}"


def _describe(entry, by_number):
	"""The running and the waiting snapshot are named by what they are now, not by the old copy they came from.

	After a rollback the running system is a writable copy of an older snapshot, but everything since then counts too.
	"""
	rollback = re.match(r"^writable copy of #(\d+)$", entry.get("description", ""))
	day = entry.get("date", "")[:10]
	if entry.get("active"):
		return "Your system now", f"Last restored from snapshot {rollback.group(1)} on {day}" if rollback else ""
	if entry.get("default"):
		return "Your system after the next restart", "Restart to finish rolling back."
	return _title(entry, by_number.get(entry.get("pre-number"))), ""


def _version_key(name):
	"""Kernel names compared number by number, so 7.2.10 comes after 7.2.9."""
	return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def _read_parts(text):
	"""Snapper's own output, each snapshot's release and newest kernel by number, and zypper's history lines."""
	listing, *parts = re.split(r"^@@", text, flags=re.MULTILINE)
	contents = {}
	history = []
	for part in parts:
		heading, *lines = part.splitlines() or [""]
		if heading == "history":
			history = lines
			continue
		release = next((line.split("=", 1)[1].strip('"') for line in lines if line.startswith("VERSION_ID=")), "")
		kernels = sorted((line for line in lines if line and not line.startswith("VERSION_ID=")), key=_version_key)
		contents[int(heading.split()[1])] = {"release": release, "kernel": kernels[-1] if kernels else ""}
	return listing, contents, history


def _package_events(history):
	"""Every package change in zypper's history in order, with the version each update replaced.

	zypper writes an update as an install of the new version, so the old one comes from the line before it.
	"""
	installed = {}
	events = []
	for line in history:
		fields = line.split("|")
		if len(fields) < 4:
			continue
		date, action, name, version = fields[0], fields[1].strip(), fields[2], fields[3]
		previous = installed.get(name, "")
		if action == "remove":
			installed.pop(name, None)
			events.append((date, {"name": name, "change": "Removed", "from": version, "to": ""}))
			continue
		installed[name] = version
		if previous != version:
			events.append((date, {"name": name, "change": "Updated" if previous else "Added", "from": previous,
				"to": version}))
	return events


def _changes(events, start, end):
	"""What one software change did between its before and after snapshots, each package once, by name."""
	found = {event["name"]: event for date, event in events if start <= date <= end}
	return sorted(found.values(), key=lambda event: event["name"])


def _summary(changes, release, release_after):
	"""One line on what the change did, naming the new Tumbleweed release when it was an update to one."""
	if not changes:
		return ""
	count = look.plural(len(changes), "package") + " changed."
	if release and release_after and release != release_after:
		return f"Updated Tumbleweed {release} to {release_after}, {count}"
	return count


def _kept(entry):
	if (entry.get("userdata") or {}).get("important") == "yes":
		return IMPORTANT_KEPT
	cleanup = entry.get("cleanup", "")
	return KEPT.get(cleanup, cleanup)


def snapshots_from_json(text):
	"""Your system now first, then each snapshot to roll back to, newest first, each with what it holds.

	After snapshots are left out, the before snapshot of the next change is close to the same place.
	Number 0 stands for the running system itself.
	"""
	listing_text, contents, history = _read_parts(text)
	start = listing_text.find("{")
	if start < 0:
		return {"known": False, "problem": listing_text.strip()[-600:], "snapshots": []}
	listing = json.loads(listing_text[start:]).get("root", [])
	by_number = {entry["number"]: entry for entry in listing}
	after = {entry["pre-number"]: entry for entry in listing if entry["type"] == "post"}
	events = _package_events(history)
	snapshots = []
	for entry in listing:
		if entry["number"] == 0 or entry["type"] == "post" and not entry.get("active"):
			continue
		title, about = _describe(entry, by_number)
		finished = after.get(entry["number"])
		release = contents.get(entry["number"], {}).get("release", "")
		changes = _changes(events, entry["date"], finished["date"]) if finished else []
		release_after = contents.get(finished["number"], {}).get("release", "") if finished else ""
		snapshots.append({
			"number": entry["number"],
			"date": entry.get("date", ""),
			"title": title,
			"about": about or _summary(changes, release, release_after),
			"running": bool(entry.get("active")),
			"next": bool(entry.get("default")) and not entry.get("active"),
			"release": release,
			"kernel": contents.get(entry["number"], {}).get("kernel", ""),
			"kept": _kept(entry),
			"changes": changes,
		})
	snapshots.sort(key=lambda snapshot: (not snapshot["running"], not snapshot["next"], -snapshot["number"]))
	return {"known": True, "problem": "", "snapshots": snapshots}


def old_snapshots(text, now=None):
	"""Snapshots older than a month that can go, a before and after pair together, never the running or next one.

	Each one's size is what only it holds, so removing several frees at least their sum.
	"""
	start = (text or "").find("{")
	listing = json.loads(text[start:]).get("root", []) if start >= 0 else []
	limit = (now or datetime.now()) - timedelta(days=OLD_DAYS)
	by_number = {entry["number"]: entry for entry in listing}
	kept = {entry["number"] for entry in listing if entry["number"] == 0 or entry.get("active") or entry.get("default")}

	def started(entry):
		pre = by_number.get(entry.get("pre-number")) if entry.get("type") == "post" else None
		return datetime.fromisoformat((pre or entry)["date"]) if (pre or entry).get("date") else None

	old = [entry for entry in listing if entry["number"] not in kept and started(entry) and started(entry) < limit]
	# A pair goes together, so one whose other half must stay is kept too
	pairs = {entry["number"]: entry.get("pre-number") for entry in old if entry.get("type") == "post"}
	old = [entry for entry in old if entry["number"] not in pairs or pairs[entry["number"]] not in kept]
	return {"known": start >= 0, "count": len(old), "total": len([entry for entry in listing if entry["number"]]),
		"bytes": sum(entry.get("used-space") or 0 for entry in old),
		"numbers": " ".join(str(entry["number"]) for entry in old),
		"oldest": min((entry["date"] for entry in old), default="")}


def remove_steps(numbers):
	return [operations.Step("Removing old snapshots", ["snapper", "delete", *numbers.split()], root=True)]


def rollback_steps(number):
	"""Snapper keeps the running system as a snapshot first, so rolling back can itself be undone.

	Its own descriptions are kept, they mark the new snapshots for its automatic cleanup.
	"""
	return [operations.Step(f"Rolling back to snapshot {number}", ["snapper", "rollback", str(number)], root=True)]
