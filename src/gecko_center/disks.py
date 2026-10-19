"""What each part of each disk holds, in plain words, with what swap is for and how much of it this computer needs.

Everything here reads without root, from lsblk, /proc/swaps and the kernel's own settings.
"""

import json
import re
from pathlib import Path

from . import look

SWAPS = Path("/proc/swaps")
MEMINFO = Path("/proc/meminfo")
COMMAND_LINE = Path("/proc/cmdline")
SLEEP_STATES = Path("/sys/power/state")
LSBLK_ARGUMENTS = ["lsblk", "--json", "--bytes", "--output",
	"NAME,PATH,TYPE,SIZE,FSTYPE,UUID,MOUNTPOINTS,FSUSED,FSSIZE"]
KIBIBYTE = 1024
SWAP_MOUNT = "[SWAP]"
# Without hibernation a few GB of swap catches the odd memory peak, more than this mostly sits unused
SWAP_WITHOUT_HIBERNATION = 8 * 1024 ** 3
# Swap counts as far too large once it passes what the computer needs by this much
TOO_LARGE = 1.5
STARTUP_MOUNTS = ("/boot/efi", "/boot")
# File systems another system or a removable drive uses, which Linux leaves closed until it is asked
OTHER_SYSTEMS = {"ntfs": "Windows", "exfat": "a USB drive or camera card", "vfat": "a USB drive or another system"}

SYSTEM_ABOUT = ("Linux, your apps and their settings live here, and Snapshots keeps earlier versions of the "
	"system here too.")
FILES_ABOUT = "Your home folder, with your documents, downloads, pictures and the settings of your apps."
STARTUP_ABOUT = ("The small part the computer reads first when it turns on, so it can find and start Linux. "
	"It never needs changing by hand.")
SWAP_ABOUT = ("Swap is room on a disk that Linux uses as extra memory. When the {memory} of memory fills up, "
	"what has not been used for a while moves here, so no app has to close.")
SWAP_HIBERNATE = " Hibernating also saves everything in memory here, so the computer can turn off and carry on later."
SWAP_TRADE = ("Swap is much slower than memory, so a computer that swaps a lot feels slow. That is a sign it needs "
	"more memory, not that swap is bad. Without swap, an app that runs out of memory is closed at once.")
EMPTY_ABOUT = "Nothing uses this part of the disk. It could hold files once it gets a file system."


def _read(path):
	try:
		return Path(path).read_text(encoding="utf-8").strip()
	except OSError:
		return ""


def size_text(count):
	"""Disk makers count in thousands, so a 2 TB disk reads 2 TB here too."""
	for unit, size in (("TB", 10 ** 12), ("GB", 10 ** 9), ("MB", 10 ** 6)):
		if count >= size:
			return f"{count / size:.1f} {unit}".replace(".0 ", " ")
	return f"{count} bytes"


def memory_text():
	"""Memory in the same whole GB the Hardware page shows, memory is counted in powers of two."""
	return f"{round(memory_bytes() / 1024 ** 3)} GB"


def memory_bytes():
	found = re.search(r"MemTotal:\s+(\d+) kB", _read(MEMINFO))
	return int(found.group(1)) * KIBIBYTE if found else 0


def hibernates():
	"""Hibernation works when the kernel can sleep to disk and knows where to resume from."""
	return "disk" in _read(SLEEP_STATES).split() and "resume=" in _read(COMMAND_LINE)


def _swap_used():
	"""Bytes in use for each swap partition by its path, /proc/swaps counts in KiB."""
	used = {}
	for line in _read(SWAPS).splitlines()[1:]:
		fields = line.split()
		if len(fields) >= 4 and fields[3].isdigit():
			used[fields[0]] = int(fields[3]) * KIBIBYTE
	return used


def swap_advice(size):
	"""Whether this much swap suits the computer and what to know, from its memory and whether it hibernates."""
	memory = memory_bytes()
	needed = memory if hibernates() else SWAP_WITHOUT_HIBERNATION
	reason = f"hibernating needs about {memory_text()}" if hibernates() else "the computer does not hibernate"
	if size > needed * TOO_LARGE:
		return False, (f"This is much more than needed, since {reason}. About {round((size - needed) / 10 ** 9)} GB "
			"of it could hold files instead.")
	if hibernates() and size < memory:
		return False, f"This is too small to hibernate, which needs about {memory_text()}."
	return True, "This size suits this computer."


def _holding(part, mounts):
	"""What a part holds, its plain title and what it is for."""
	if "/" in mounts:
		return ("The system and your files" if "/home" in mounts else "The system",
			SYSTEM_ABOUT + (" " + FILES_ABOUT if "/home" in mounts else ""))
	if "/home" in mounts:
		return "Your files", FILES_ABOUT
	if any(mount in STARTUP_MOUNTS for mount in mounts):
		return "Start-up files", STARTUP_ABOUT
	if mounts:
		return "Files at " + mounts[0], f"Its files open at {mounts[0]} in the file manager."
	if part.get("fstype") in OTHER_SYSTEMS:
		return "Not opened", f"It looks like it belongs to {OTHER_SYSTEMS[part['fstype']]}. Linux leaves it closed."
	return "Empty space", EMPTY_ABOUT


def _use(part, swap_used):
	"""One part of a disk, what it holds in plain words, how full it is and what to know about it."""
	mounts = [mount for mount in part.get("mountpoints") or [] if mount]
	size = int(part.get("size") or 0)
	use = {"name": part.get("path", ""), "size": size, "sizeText": size_text(size), "advice": "", "adviceGood": True}
	if SWAP_MOUNT in mounts:
		good, advice = swap_advice(size)
		about = SWAP_ABOUT.format(memory=memory_text()) + (SWAP_HIBERNATE if hibernates() else "")
		use.update(title="Swap", used=swap_used.get(part.get("path", ""), 0), about=about + "\n" + SWAP_TRADE,
			advice=advice, adviceGood=good)
	else:
		title, about = _holding(part, mounts)
		use.update(title=title, about=about, used=int(part["fsused"]) if part.get("fsused") else None)
	use["usedText"] = size_text(use["used"]) if use["used"] is not None else ""
	return use


def disk_uses():
	"""Each disk by its name, with what each of its parts holds, the biggest part first."""
	listing = look.run(LSBLK_ARGUMENTS)
	try:
		blocks = json.loads(listing.stdout).get("blockdevices", [])
	except ValueError:
		return {}
	swap_used = _swap_used()
	found = {}
	for block in blocks:
		if block.get("type") != "disk":
			continue
		parts = block.get("children") or [block]
		uses = [_use(part, swap_used) for part in parts if part.get("type") in ("part", "disk", "crypt", "lvm")]
		found[block["name"]] = sorted(uses, key=lambda use: use["size"], reverse=True)
	return found


def use_line(use):
	"""A part's title with how full it is, such as Swap, 2.7 GB of 120 GB in use."""
	if use["used"] is None:
		return f"{use['title']}, {use['sizeText']}"
	return f"{use['title']}, {size_text(use['used'])} of {use['sizeText']} in use"


def swap_summary():
	"""All swap together for the Storage page, with the same words the disk's own page uses."""
	found = [(disk, use) for disk, uses in disk_uses().items() for use in uses if use["title"] == "Swap"]
	if not found:
		return None
	size = sum(use["size"] for _disk, use in found)
	used = sum(use["used"] for _disk, use in found)
	good, advice = swap_advice(size)
	return {"size": size, "used": used, "usedText": size_text(used), "sizeText": size_text(size),
		"about": found[0][1]["about"], "advice": advice, "adviceGood": good, "disk": found[0][0]}
