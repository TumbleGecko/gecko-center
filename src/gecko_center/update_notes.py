"""What a pending update brings, from the makers' release notes, the packagers' changelog and Flatpak's commit.

zypper does not download changelogs, but each repository publishes them as its "other" metadata,
see https://en.opensuse.org/openSUSE:Standards_Rpm_Metadata
"""

import gzip
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path

from . import paths

REPOMD_NAMESPACE = "{http://linux.duke.edu/metadata/repo}"
DOWNLOAD_TIMEOUT = 60
# A package block in other.xml starts on one line that names it, so the file can be scanned without parsing it all
PACKAGE_START = re.compile(r'<package [^>]*name="([^"]+)"')
VERSION_PARTS = re.compile(r"\d+|[^\d.+~_-]+")


def repository_urls():
	"""Each zypper repository's alias with the address its metadata comes from."""
	listing = subprocess.run([paths.ZYPPER, "--non-interactive", "--no-refresh", "--xmlout", "repos"],
		capture_output=True, text=True, check=False, env={"LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"})
	start = listing.stdout.find("<?xml")
	if start < 0:
		return {}
	stream = ElementTree.fromstring(listing.stdout[start:])
	return {repository.get("alias"): (repository.findtext("url") or "").rstrip("/")
		for repository in stream.iter("repo")}


def _download(url):
	request = urllib.request.Request(url, headers={"User-Agent": paths.APPLICATION_NAME})
	with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
		return response.read()


def changelog_file(alias, base_url):
	"""The repository's changelog file, downloaded once for each version the repository publishes."""
	repomd = ElementTree.fromstring(_download(base_url + "/repodata/repomd.xml"))
	other = next((data for data in repomd.iter(REPOMD_NAMESPACE + "data") if data.get("type") == "other"), None)
	if other is None:
		return None
	href = other.find(REPOMD_NAMESPACE + "location").get("href", "")
	# Some repositories keep the same file name for each version, the checksum changes with each one
	checksum = (other.findtext(REPOMD_NAMESPACE + "checksum") or "").strip()
	folder = paths.CHANGELOG_CACHE / alias.replace("/", "_")
	cached = folder / (checksum + "".join(Path(href).suffixes[-2:]))
	if cached.exists():
		return cached
	folder.mkdir(parents=True, exist_ok=True)
	for older in folder.iterdir():
		older.unlink()
	temporary = cached.with_name(cached.name + ".part")
	temporary.write_bytes(_download(base_url + "/" + href))
	temporary.replace(cached)
	return cached


def _open_lines(path):
	"""The file's lines, openSUSE packs it with zstd, which this Python cannot read itself, others use gzip."""
	if path.suffix == ".zst":
		return subprocess.Popen(["zstd", "-dc", str(path)], stdout=subprocess.PIPE).stdout
	return gzip.open(path, "rb")


def _package_block(path, name, version):
	"""The other.xml block for this name and version, read line by line, the file is hundreds of megabytes."""
	lines = []
	with _open_lines(path) as stream:
		for raw in stream:
			line = raw.decode(errors="replace")
			if line.startswith("<package "):
				match = PACKAGE_START.match(line)
				lines = [line] if match and match.group(1) == name else []
				continue
			if not lines:
				continue
			lines.append(line)
			if line.startswith("</package>"):
				block = ElementTree.fromstring("".join(lines))
				edition = block.find("version")
				if edition is not None and edition.get("ver") + "-" + edition.get("rel") == version:
					return block
				lines = []
	return None


def installed_changelog_time(name):
	"""When the installed package's newest changelog entry was written, zero when it has none."""
	query = subprocess.run(["rpm", "-q", "--queryformat", "%{CHANGELOGTIME}", name], capture_output=True, text=True,
		check=False)
	return int(query.stdout) if query.returncode == 0 and query.stdout.isdigit() else 0


def changelog_since(path, name, version, since):
	"""The new version's changelog entries written after the installed version's newest one, newest first."""
	block = _package_block(path, name, version)
	if block is None:
		return None
	entries = []
	for change in block.iter("changelog"):
		written = int(change.get("date", "0"))
		if written > since:
			entries.append({"date": str(datetime.fromtimestamp(written).date()),
				"author": change.get("author", "").split(" <")[0], "text": (change.text or "").strip()})
	return sorted(entries, key=lambda entry: entry["date"], reverse=True)


def _version_key(version):
	return [(0, int(part)) if part.isdigit() else (-1, part) for part in VERSION_PARTS.findall(version)]


def releases_after(releases, installed_version):
	"""The described releases newer than the installed one, the release part after a dash is the packager's own."""
	installed = _version_key(installed_version.split("-")[0])
	return [release for release in releases if _version_key(release["version"]) > installed]


def flatpak_subject(app_id, installation):
	"""The one line the app's newest Flatpak build was published with, such as Update to v2.4.1."""
	origin = subprocess.run(["flatpak", "info", f"--{installation}", "--show-origin", app_id], capture_output=True,
		text=True, check=False).stdout.strip()
	if not origin:
		return ""
	remote = subprocess.run(["flatpak", "remote-info", f"--{installation}", origin, app_id], capture_output=True,
		text=True, check=False, env={"LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"})
	for line in remote.stdout.splitlines():
		key, separator, value = line.partition(":")
		if separator and key.strip() == "Subject":
			return value.strip()
	return ""


def flatpak_installed_version(app_id, installation):
	listing = subprocess.run(["flatpak", "info", f"--{installation}", app_id], capture_output=True, text=True,
		check=False, env={"LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"})
	for line in listing.stdout.splitlines():
		key, separator, value = line.partition(":")
		if separator and key.strip() == "Version":
			return value.strip()
	return ""


def read_notes(pending, releases):
	"""Everything the update tab shows, read in a thread since it can download a changelog file."""
	notes = {"releases": [], "changes": [], "rebuild": False, "subject": "", "problem": ""}
	if pending["kind"] == "flatpak":
		notes["subject"] = flatpak_subject(pending["id"], pending["installation"])
		installed = flatpak_installed_version(pending["id"], pending["installation"])
		notes["releases"] = releases_after(releases, installed) if installed else releases[:1]
		return notes
	notes["releases"] = releases_after(releases, pending["oldVersion"])
	base_url = repository_urls().get(pending["repository"], "")
	if not base_url.startswith(("http://", "https://")):
		notes["problem"] = "This package's source keeps no changelog Gecko Center can read."
		return notes
	try:
		path = changelog_file(pending["repository"], base_url)
	except OSError:
		notes["problem"] = "The changelog could not be downloaded."
		return notes
	changes = changelog_since(path, pending["name"], pending["version"], installed_changelog_time(pending["name"]))
	if changes is None:
		notes["problem"] = "The package's source has no changelog for this version."
		return notes
	notes["changes"] = changes
	notes["rebuild"] = not changes
	return notes
