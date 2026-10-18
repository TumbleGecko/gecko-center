"""Single packages, found by zypper search, described by zypper info, or opened from a file or link."""

import configparser
import re
import subprocess
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import paths

FLATHUB_REFERENCE = re.compile(r"^https?://dl\.flathub\.org/repo/appstream/([A-Za-z0-9._-]+)\.flatpakref$")
RPM_FIELDS = ["NAME", "VERSION", "RELEASE", "ARCH", "SUMMARY", "URL", "VENDOR", "LICENSE", "DESCRIPTION"]
# Each field ends with a byte that never appears in package text
RPM_FIELD_END = "\x1f"


def search_arguments(text):
	return [paths.ZYPPER, "--non-interactive", "--no-refresh", "--xmlout", "search", "--type", "package", "--", text]


def search_results_from_xml(text):
	start = text.find("<?xml")
	if start < 0:
		return []
	stream = ElementTree.fromstring(text[start:])
	return [{
		"key": "package:" + solvable.get("name", ""),
		"name": solvable.get("name", ""),
		"summary": solvable.get("summary", ""),
		"installed": solvable.get("status") == "installed",
	} for solvable in stream.iter("solvable")]


def info_arguments(name):
	return [paths.ZYPPER, "--non-interactive", "--no-refresh", "info", "--", name]


def package_from_info(text, name):
	"""Read zypper info's "Key : value" lines, the description is the indented block after its key."""
	fields = {}
	description = []
	in_description = False
	for line in text.splitlines():
		if in_description:
			description.append(line.strip())
			continue
		key, separator, value = line.partition(" : ")
		if not separator:
			continue
		key = key.strip()
		if key == "Description":
			in_description = True
			continue
		fields[key] = value.strip()
	paragraphs = "\n".join(description).strip().split("\n\n")
	return {
		"kind": "package",
		"key": "package:" + name,
		"id": name,
		"package": name,
		"name": fields.get("Name", name),
		"summary": fields.get("Summary", ""),
		"description": "\n\n".join(" ".join(part.split()) for part in paragraphs),
		"version": fields.get("Version", ""),
		"source": fields.get("Repository", ""),
		"homepage": fields.get("Upstream URL", ""),
		"developer": fields.get("Vendor", ""),
		"license": "",
		"size": fields.get("Installed Size", ""),
		"installation": "system" if fields.get("Installed", "No").startswith("Yes") else "",
		"icon": "",
	}


def rpm_file(path):
	"""Describe a package file without installing it, and say in plain words whether its signature checks out."""
	query_format = RPM_FIELD_END.join(f"%{{{field}}}" for field in RPM_FIELDS)
	query = subprocess.run(["rpm", "-qp", "--queryformat", query_format, str(path)], capture_output=True, text=True,
		check=False, env={"LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"})
	if query.returncode != 0:
		return {"kind": "file", "problem": "This file is not a package that can be installed.", "path": str(path)}
	values = dict(zip(RPM_FIELDS, query.stdout.split(RPM_FIELD_END)))
	signature = subprocess.run(["rpm", "-K", str(path)], capture_output=True, text=True, check=False,
		env={"LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"}).stdout
	installed = subprocess.run(["rpm", "-q", values["NAME"]], capture_output=True, check=False).returncode == 0
	return {
		"kind": "file",
		"format": "rpm",
		"key": "file:" + str(path),
		"path": str(path),
		"id": values["NAME"],
		"package": str(path),
		"name": values["NAME"],
		"summary": values["SUMMARY"],
		"description": " ".join(values["DESCRIPTION"].split()),
		"version": f"{values['VERSION']}-{values['RELEASE']}",
		"source": "This file",
		"homepage": "" if values["URL"] == "(none)" else values["URL"],
		"developer": "" if values["VENDOR"] == "(none)" else values["VENDOR"],
		"license": values["LICENSE"],
		"trust": _trust(signature),
		"installation": "system" if installed else "",
		"icon": "",
	}


def _trust(signature):
	"""rpm -K prints "signatures OK" only when a key you already trust signed the file."""
	if "signatures OK" in signature:
		return "signed"
	if "NOKEY" in signature or "NOT OK" in signature:
		return "unknown-key"
	return "unsigned"


def flatpak_reference(text):
	"""The app id, name and remote address inside a .flatpakref file."""
	parser = configparser.ConfigParser(interpolation=None)
	parser.read_string(text)
	section = parser["Flatpak Ref"] if parser.has_section("Flatpak Ref") else {}
	return {
		"id": section.get("Name", ""),
		"name": section.get("Title", "") or section.get("Name", ""),
		"branch": section.get("Branch", ""),
		"url": section.get("Url", ""),
	}


def link_target(argument):
	"""Sort what the app was opened with into a local file, a Flathub app id, a remote .flatpakref or an AppStream id."""
	if argument.startswith(("appstream:", "appstream://")):
		return {"type": "appstream", "id": argument.split(":", 1)[1].lstrip("/").removesuffix(".desktop")}
	target = argument.removeprefix("flatpak+")
	match = FLATHUB_REFERENCE.match(target)
	if match:
		return {"type": "flathub", "id": match.group(1)}
	if target.startswith(("https://", "http://")):
		return {"type": "remote-reference", "url": target}
	path = Path(unquote(urlparse(target).path) if target.startswith("file://") else target).resolve()
	if path.suffix == ".rpm":
		return {"type": "rpm", "path": str(path)}
	if path.suffix == ".flatpakref":
		return {"type": "flatpakref", "path": str(path)}
	return {"type": "unknown", "path": str(path)}
