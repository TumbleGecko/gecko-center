"""Where the disk space goes and the leftovers that can go without losing anything."""

import re
import shutil
from pathlib import Path

from . import look, operations, paths

PACKAGE_CACHE = Path("/var/cache/zypp/packages")
# Logs older than this are rarely read, a month still covers the last few updates
JOURNAL_KEEP = "4weeks"
JOURNAL_SIZE = re.compile(r"take up ([\d.]+)([KMGT]?)")
UNITS = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}


def thumbnail_folder():
	return Path(paths.xdg_directory("XDG_CACHE_HOME", ".cache")) / "thumbnails"


def _journal_bytes():
	found = JOURNAL_SIZE.search(look.run(["journalctl", "--disk-usage"]).stdout)
	return int(float(found.group(1)) * UNITS[found.group(2)]) if found else 0


def _device(path):
	"""Btrfs gives each subvolume its own device number, so the disk is told by its source minus the subvolume."""
	found = look.run(["findmnt", "--noheadings", "--output", "SOURCE", "--target", str(path)])
	return found.stdout.strip().split("[", 1)[0]


def places():
	"""The system disk, and home when it is a disk of its own."""
	found = [("System", Path("/"))]
	if _device(Path.home()) != _device("/"):
		found.append(("Home", Path.home()))
	return [{"label": label, "free": shutil.disk_usage(place).free, "total": shutil.disk_usage(place).total}
		for label, place in found]


# Each cleanup with its plain words, its size in bytes or None when it cannot be measured, and its steps
CLEANUPS = {
	"packages": ("Downloaded packages", "Packages zypper kept after installing them. It downloads them again if needed.",
		lambda: look.folder_bytes(PACKAGE_CACHE),
		lambda: [operations.zypper_step("Removing downloaded packages", [paths.ZYPPER, "--non-interactive", "clean",
			"--all"])]),
	"journal": ("System logs", "Messages the system writes as it runs, removing keeps the last four weeks.",
		_journal_bytes,
		lambda: [operations.Step("Removing old system logs", ["journalctl", "--vacuum-time=" + JOURNAL_KEEP],
			root=True)]),
	"thumbnails": ("Picture previews", "Small previews of your pictures and videos, made again when shown.",
		lambda: look.folder_bytes(thumbnail_folder()),
		lambda: [operations.Step("Removing picture previews", ["rm", "-rf", "--", str(thumbnail_folder())])]),
	"flatpak": ("Unused Flatpak parts", "Runtimes no installed Flatpak app needs any longer.", lambda: None,
		lambda: [operations.Step("Removing your unused Flatpak parts",
				["flatpak", "uninstall", "--user", "--unused", "-y", "--noninteractive"]),
			operations.Step("Removing unused Flatpak parts for everyone",
				["flatpak", "uninstall", "--system", "--unused", "-y", "--noninteractive"], root=True)]),
}


def cleanup_steps(cleanup_id):
	return CLEANUPS[cleanup_id][3]()


def collect():
	# A leftover that takes no space is not shown, one whose size cannot be measured is
	cleanups = [{"id": cleanup_id, "title": title, "about": about, "bytes": measure()}
		for cleanup_id, (title, about, measure, _steps) in CLEANUPS.items()]
	cleanups = [cleanup for cleanup in cleanups if cleanup["bytes"] is None or cleanup["bytes"] > 0]
	return {"places": places(), "cleanups": cleanups}
