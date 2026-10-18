"""Start Gecko Center, the window, the background check, the tray icon or the timer setup.

Each part is in its own module, this file only picks one.
"""

import argparse
import os
import subprocess
import sys
import tempfile

from . import background, updates

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
PAGES = ("overview", "performance", "explore", "installed", "updates", "snapshots", "sources", "drivers", "storage",
	"services", "guide", "news", "settings")


def _parse_arguments():
	parser = argparse.ArgumentParser(prog="gecko-center.sh", description="Look after openSUSE Tumbleweed, "
		"its updates, software, snapshots, drivers and health.")
	action = parser.add_mutually_exclusive_group()
	action.add_argument("--page", choices=PAGES, help="open the window on this page")
	action.add_argument("--install", action="store_true", help="install what it needs and its launcher, without opening")
	action.add_argument("--check", action="store_true", help="look for updates without installing, the timer runs this")
	action.add_argument("--tray", action="store_true", help="show the tray icon, the tray unit runs this")
	action.add_argument("--install-tray", action="store_true", help="start the tray icon now and with every login")
	action.add_argument("--install-timer", nargs="?", const=background.DEFAULT_INTERVAL, choices=background.INTERVALS,
		metavar="INTERVAL", help="look for updates in the background, daily, weekly (the default) or monthly")
	action.add_argument("--remove-timer", action="store_true", help="stop looking for updates in the background")
	parser.add_argument("targets", nargs="*", help="an .rpm or .flatpakref file or an install link to open")
	return parser.parse_args()


def _root_launcher():
	"""Run as root with what this start offers, an installer's askpass, a terminal's sudo or polkit's own dialog."""
	if subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False).returncode == EXIT_SUCCESS:
		return ["sudo", "-n"]
	if os.environ.get("SUDO_ASKPASS"):
		return ["sudo", "-A"]
	return ["sudo"] if sys.stdin.isatty() else ["pkexec"]


def _run_as_root(arguments):
	return subprocess.run([*_root_launcher(), *arguments], check=False).returncode


def _install_timer(interval):
	if not updates.refresh_unit_installed():
		with tempfile.TemporaryDirectory(prefix="gecko-center-") as directory:
			if _run_as_root(background.write_system_files(directory)) != EXIT_SUCCESS:
				return EXIT_FAILURE
	return background.install_user_units(interval)


def _remove_timer():
	background.remove_user_units()
	if updates.refresh_unit_installed():
		return _run_as_root(background.remove_system_arguments())
	return EXIT_SUCCESS


def main():
	arguments = _parse_arguments()
	if arguments.check:
		return updates.check_in_background()
	if arguments.tray:
		from . import tray
		return tray.main()
	if arguments.install_tray:
		return background.install_tray_unit()
	if arguments.install_timer:
		return _install_timer(arguments.install_timer)
	if arguments.remove_timer:
		return _remove_timer()
	from . import window
	return window.main(arguments.page or "", arguments.targets)


# The catalog reader starts fresh Python processes that import this module, they must not start the app again
if __name__ == "__main__":
	sys.exit(main())
