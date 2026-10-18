"""A full report of the system as one Markdown file in ~/gecko-logs, shown in the file manager to send to a helper.

It has what the pages show, the computer, each check, updates, sources and their software, drivers, storage,
services and the errors since the last start, with your name and the computer's name left out.
"""

import getpass
import re
import socket
from datetime import datetime
from pathlib import Path

from . import drivers, health, look, services, sources, storage, updates

REPORT_FOLDER = Path.home() / "gecko-logs"
# Colons are left out of the name because some systems and chat apps reject them in file names
NAME_FORMAT = "%Y-%m-%d %H-%M-%S"
ERROR_MESSAGES = 60
GIGABYTE = 1024 ** 3

MARKS = {"good": "✅", "note": "ℹ️", "warning": "⚠️", "problem": "❌"}
MACHINE_FACTS = [("System", "system"), ("Snapshot", "snapshot"), ("Linux", "kernel"), ("Desktop", "desktop"),
	("Processor", "processor"), ("Graphics", "graphics"), ("Memory", "memory")]


def _cell(text):
	"""A table cell keeps its row together, so line breaks and bars become safe characters."""
	return str(text).replace("|", "\\|").replace("\n", " ")


def _table(headings, rows):
	lines = ["| " + " | ".join(headings) + " |", "|" + "---|" * len(headings)]
	lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
	return lines


def _size(count):
	return "unknown" if count is None else f"{count / GIGABYTE:.1f} GB"


def _when(moment):
	try:
		return datetime.fromisoformat(moment).strftime("%Y-%m-%d at %H:%M")
	except ValueError:
		return moment


def _code(text):
	return ["```text", text.rstrip() or "(empty)", "```"]


def _summary_lines(report):
	checks = report["checks"]
	attention = [check for check in checks if check["state"] in ("warning", "problem")]
	lines = ["## At a glance", ""]
	if not attention:
		lines.append("> ✅ Everything looks good.")
	else:
		lines.append("> ⚠️ One thing needs a look." if len(attention) == 1 else f"> ⚠️ {len(attention)} things need a look.")
	lines.append("")
	lines += _table(["", "Check", "Result"], [(MARKS[check["state"]], check["title"], check["summary"])
		for check in checks])
	return lines


def _machine_lines(machine):
	lines = ["## This computer", ""]
	return lines + _table(["", ""], [(label, machine.get(key) or "unknown") for label, key in MACHINE_FACTS])


def _check_lines(checks):
	lines = ["## Each check in detail"]
	for check in checks:
		lines += ["", f"### {MARKS[check['state']]} {check['title']}", "", f"**{check['summary']}**"]
		if check["details"]:
			lines += [""] + [f"- {detail}" for detail in check["details"]]
	return lines


def _update_lines():
	state = updates.read_state() or {}
	plan = state.get("system") or {}
	looked = f"Last looked for updates {_when(state['checked'])}." if state.get("checked") \
		else "Gecko Center has not looked for updates yet."
	lines = ["## Updates", "", looked, ""]
	if not plan.get("known"):
		lines.append("The last look could not work out the system update.")
		if plan.get("problem"):
			lines += [""] + _code(plan["problem"])
	elif plan.get("count", 0) == 0:
		lines.append("The system is up to date.")
	else:
		lines.append(f"{look.plural(plan['count'], 'package')} wait for the system update.")
		for section, packages in plan.get("sections", {}).items():
			lines += ["", f"<details><summary>To {section} ({len(packages)})</summary>", ""]
			lines += [f"- {package['name']} {package.get('version', '')}" for package in packages]
			lines += ["", "</details>"]
	flatpaks = state.get("flatpak") or []
	if flatpaks:
		lines += ["", f"{look.plural(len(flatpaks), 'Flatpak app')} can be updated too."]
	return lines


def _source_lines():
	found = sources.read_sources()
	if found is None:
		return ["## Software sources", "", "The software sources could not be read."]
	lines = ["## Software sources", ""]
	lines += _table(["", "Source", "Built by", "On", "Address"], [(
		"⚠️" if source["risks"] else "✅" if source["kind"] == sources.OPENSUSE else "",
		source["name"], source["builder"].removeprefix("Built by "), "yes" if source["enabled"] else "no",
		source["url"]) for source in found])
	risky = [source for source in found if source["risks"]]
	if risky:
		lines += ["", "### Sources that could cause trouble"]
		for source in risky:
			lines += ["", f"**{source['name']}**", ""] + [f"- {risk}" for risk in source["risks"]]
	given = sources.installed_by_source()
	outside = [source for source in found if source["kind"] != sources.OPENSUSE and given.get(source["alias"])]
	if outside:
		lines += ["", "### Software from outside openSUSE"]
		for source in outside:
			packages = given[source["alias"]]
			lines += ["", f"<details><summary>{source['name']} ({len(packages)})</summary>", ""]
			lines += [f"- **{package['name']}** {package['summary']}" for package in packages]
			lines += ["", "</details>"]
	leftover = given.get("(System Packages)") or []
	if leftover:
		lines += ["", "### Installed packages no source offers any longer", "",
			f"<details><summary>{len(leftover)} packages</summary>", ""]
		lines += [f"- **{package['name']}** {package['summary']}" for package in leftover]
		lines += ["", "</details>"]
	return lines


def _driver_lines():
	found = drivers.collect()
	lines = ["## Graphics and firmware", ""]
	lines += _table(["Card", "Maker", "Driver"], [(card["name"], card["maker"], card["driver"] or "none")
		for card in found["cards"]])
	firmware = found["firmware"]
	lines.append("")
	if not firmware.get("known"):
		lines.append("Firmware updates could not be checked. " + (firmware.get("problem") or ""))
	elif firmware.get("devices"):
		lines.append(f"{look.plural(len(firmware['devices']), 'device')} have a firmware update waiting.")
	else:
		lines.append("All firmware is up to date.")
	return lines


def _storage_lines():
	found = storage.collect()
	lines = ["## Storage", ""]
	lines += _table(["Place", "Free", "Size"], [(place["label"], _size(place["free"]), _size(place["total"]))
		for place in found["places"]])
	if found["cleanups"]:
		lines += ["", "### Room that could be made", ""]
		lines += [f"- **{cleanup['title']}** {_size(cleanup['bytes'])}" for cleanup in found["cleanups"]]
	return lines


def _service_lines():
	found = services.collect()
	failed = found["failed"]
	lines = ["## Services", "", f"{look.plural(len(found['services']), 'service')} known, "
		f"{len(failed)} stopped with an error."]
	for service in failed:
		lines += ["", f"### ❌ {service['description']}", "", f"`{service['unit']}` ({service['scope']})"]
		lines += [""] + [f"- {fact}" for fact in service["facts"]]
		# The system's own logs need root, so only what you may read already goes in
		log = look.run(services.log_arguments(service["scope"], service["unit"]))
		if log.returncode == 0 and log.stdout.strip():
			lines += ["", "<details><summary>Its last log lines</summary>", ""] + _code(log.stdout)
			lines += ["", "</details>"]
	return lines


def _error_lines():
	log = look.run(["journalctl", "--boot", "--priority", "err", "--lines", str(ERROR_MESSAGES), "--no-pager",
		"--no-hostname", "--output", "short-iso"])
	lines = ["## Errors since the last start", ""]
	if log.returncode != 0:
		return lines + ["The system log could not be read without a password."]
	# A crash message goes on with its backtrace indented below, and its first line names what crashed
	first_lines = "\n".join(line for line in log.stdout.splitlines() if line and not line[0].isspace())
	return lines + [f"<details><summary>The last {ERROR_MESSAGES} errors</summary>", ""] + _code(first_lines) \
		+ ["", "</details>"]


def _hide_names(text):
	"""Your user name, home folder and the computer's name stay on this computer."""
	text = text.replace(str(Path.home()), "~")
	for name, stand_in in ((getpass.getuser(), "user"), (socket.gethostname(), "computer")):
		if len(name) >= 3:
			text = re.sub(rf"\b{re.escape(name)}\b", stand_in, text)
	return text


def build(made):
	report = health.collect()
	machine = report["machine"]
	lines = ["# 🦎 Gecko Center report", "",
		f"*{machine['system']} {machine['snapshot']}, made {made.strftime('%Y-%m-%d at %H:%M')}*", ""]
	for part in (_summary_lines(report), _machine_lines(machine), _check_lines(report["checks"]), _update_lines(),
			_source_lines(), _driver_lines(), _storage_lines(), _service_lines(), _error_lines()):
		lines += part + [""]
	lines += ["---", "", "*Made by Gecko Center. Your user name and the computer's name are left out.*", ""]
	return _hide_names("\n".join(lines))


def show_in_file_manager(path):
	"""Open the folder with the report picked, so it can be dragged into a chat or mail."""
	shown = look.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.FileManager1",
		"--object-path", "/org/freedesktop/FileManager1", "--method", "org.freedesktop.FileManager1.ShowItems",
		f"['{path.as_uri()}']", ""])
	if shown.returncode != 0:
		look.run(["xdg-open", str(path.parent)])


def share():
	"""Write the report, show it and pass back where it went."""
	made = datetime.now()
	REPORT_FOLDER.mkdir(exist_ok=True)
	path = REPORT_FOLDER / (made.strftime(NAME_FORMAT) + ".md")
	path.write_text(build(made), encoding="utf-8")
	show_in_file_manager(path)
	return {"path": str(path)}
