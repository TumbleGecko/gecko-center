"""What can be updated, read from zypper's update plan and Flatpak, and the saved result of the last check.

On Tumbleweed `zypper dup` is the only correct update, https://en.opensuse.org/System_Updates
"""

import json
import subprocess
import xml.etree.ElementTree as ElementTree
from datetime import datetime

from . import paths

EXIT_SUCCESS = 0
# zypper exits with 102 when the update wants a reboot, see the EXIT CODES section of man zypper
ZYPPER_EXIT_REBOOT = 102
ZYPPER_EXIT_RESTART_ZYPPER = 103
FLATPAK_INSTALLATIONS = ("user", "system")

# Arguments zypper takes to plan the update without changing anything, the refresh comes first
REFRESH_ARGUMENTS = [paths.ZYPPER, "--non-interactive", "--quiet", "refresh"]
PLAN_ARGUMENTS = [paths.ZYPPER, "--non-interactive", "--no-refresh", "--xmlout", "dup", "--dry-run"]
UPDATE_ARGUMENTS = [paths.ZYPPER, "--non-interactive", "dup", "--auto-agree-with-licenses"]


def plan_from_xml(text):
	"""Turn zypper's XML from dup --dry-run into the counts and package lists the window shows."""
	start = text.find("<?xml")
	plan = {"known": False, "count": 0, "download": 0, "reboot": False, "sections": {}, "problem": "", "checked": now()}
	if start < 0:
		plan["problem"] = text.strip()[-2000:]
		return plan
	stream = ElementTree.fromstring(text[start:])
	summary = stream.find("install-summary")
	plan["known"] = True
	if summary is None:
		plan["problem"] = _problem_text(stream)
		plan["known"] = plan["problem"] == ""
		return plan
	plan["count"] = int(summary.get("packages-to-change", "0"))
	plan["download"] = int(summary.get("download-size", "0"))
	plan["reboot"] = summary.get("need-reboot", "0") == "1"
	for section in summary:
		if not section.tag.startswith("to-"):
			continue
		plan["sections"][section.tag[3:]] = [_package(solvable) for solvable in section.iter("solvable")]
	return plan


def _package(solvable):
	return {
		"name": solvable.get("name", ""),
		"version": solvable.get("edition", ""),
		"oldVersion": solvable.get("edition-old", ""),
		"summary": solvable.get("summary", ""),
		"repository": solvable.get("repository", ""),
	}


def _problem_text(stream):
	"""The solver problem or error zypper reports when it cannot plan the update on its own."""
	lines = [message.text or "" for message in stream.iter("message") if message.get("type") == "error"]
	lines += [prompt.findtext("text", "") for prompt in stream.iter("prompt") if "Problem" in prompt.findtext("text", "")]
	return "\n".join(line.strip() for line in lines if line.strip())


def now():
	return datetime.now().isoformat(timespec="seconds")


def unreachable_plan(details=""):
	"""The plan when the package lists could not be refreshed, dated so the page can say how old it is."""
	return {"known": False, "count": 0, "problem": ("The software sources could not be refreshed.\n" + details).strip(),
		"checked": now()}


def installed_flatpak_refs(installation):
	"""Each installed app and runtime as id and branch, an update for anything else is left over from an older look."""
	listing = subprocess.run(["flatpak", "list", f"--{installation}", "--columns=application,branch"],
		capture_output=True, text=True, check=False)
	return {tuple(line.split("\t")[:2]) for line in listing.stdout.splitlines() if "\t" in line}


def flatpak_update_arguments(installation):
	return ["flatpak", "remote-ls", "--updates", f"--{installation}", "--columns=application,name,version,branch"]


def flatpak_updates_from_text(text, installation, installed):
	"""Each installed Flatpak app or runtime with a newer build, once per id and branch."""
	found = {}
	for line in text.splitlines():
		fields = line.split("\t")
		if len(fields) < 4:
			continue
		application, name, version, branch = fields[:4]
		if (application, branch) not in installed:
			continue
		found[(application, branch)] = {
			"id": application, "name": name or application, "version": version, "branch": branch,
			"installation": installation,
		}
	return list(found.values())


def read_state():
	try:
		return json.loads(paths.UPDATES_FILE.read_text())
	except (OSError, ValueError):
		return {"checked": "", "system": None, "flatpak": []}


def pending_count(state):
	system = state.get("system") or {}
	return system.get("count", 0) + len(state.get("flatpak") or [])


def write_state(state):
	"""Save the check, the tray watches this folder and follows it."""
	state["checked"] = now()
	paths.STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
	temporary = paths.UPDATES_FILE.with_suffix(".new")
	temporary.write_text(json.dumps(state, indent="\t"))
	temporary.replace(paths.UPDATES_FILE)


def refresh_unit_installed():
	"""The unit and its polkit rule go in together, and only root may read the rules folder."""
	return paths.SYSTEM_UNIT.exists()


def check_in_background():
	"""What the timer runs, refresh through the root unit polkit allows without a password, then save the plan."""
	state = {"system": None, "flatpak": []}
	if refresh_unit_installed():
		refresh = subprocess.run(["systemctl", "start", paths.REFRESH_SERVICE], capture_output=True, text=True,
			check=False)
		if refresh.returncode == EXIT_SUCCESS:
			state["system"] = plan_from_xml(paths.UPDATE_PLAN.read_text())
		else:
			state["system"] = unreachable_plan()
	for installation in FLATPAK_INSTALLATIONS:
		# The app catalog reads this AppStream data, so it is as fresh as the updates
		subprocess.run(["flatpak", "update", "--appstream", f"--{installation}"], capture_output=True, check=False)
		listing = subprocess.run(flatpak_update_arguments(installation), capture_output=True, text=True, check=False)
		state["flatpak"] += flatpak_updates_from_text(listing.stdout, installation, installed_flatpak_refs(installation))
	write_state(state)
	return EXIT_SUCCESS
