"""The apps you can browse, read from the AppStream data openSUSE and Flathub publish.

openSUSE's zypper plugin unpacks each repository's AppStream into /var/cache/swcatalog.
Flatpak keeps Flathub's next to its remote.
"""

import gzip
import multiprocessing
import platform
import subprocess
import threading
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, Qt, QUrl, Signal, Slot

from . import paths

REPOSITORY_CATALOGS = Path("/var/cache/swcatalog")
FLATPAK_INSTALLATIONS = {
	"user": Path.home() / ".local/share/flatpak",
	"system": Path("/var/lib/flatpak"),
}
APP_TYPES = {"desktop", "desktop-application", "console-application"}
XML_LANGUAGE = "{http://www.w3.org/XML/1998/namespace}lang"
# How many described releases each app keeps, more than an update usually spans
RELEASES_KEPT = 5
ICON_SIZES = ("128x128", "64x64")
OPENSUSE = "openSUSE"
FLATHUB = "Flathub"

# The groups the browser offers, each gathering the freedesktop main categories it covers
GROUPS = [
	("Games", {"Game"}),
	("Graphics", {"Graphics"}),
	("Audio and video", {"AudioVideo", "Audio", "Video"}),
	("Office", {"Office"}),
	("Internet", {"Network"}),
	("Development", {"Development"}),
	("Education", {"Education", "Science"}),
	("System", {"System", "Settings"}),
	("Utilities", {"Utility"}),
]


def _untranslated(element, tag):
	"""The text of the child in the default language, AppStream repeats each text once per translation."""
	for child in element.findall(tag):
		if XML_LANGUAGE not in child.attrib:
			return (child.text or "").strip()
	return ""


def _description(element):
	"""AppStream descriptions are small HTML, this keeps the paragraphs and list items as plain lines."""
	description = None
	for child in element.findall("description"):
		if XML_LANGUAGE not in child.attrib:
			description = child
			break
	if description is None:
		return ""
	lines = []
	for part in description:
		if XML_LANGUAGE in part.attrib:
			continue
		if part.tag == "p":
			lines.append(" ".join("".join(part.itertext()).split()))
		elif part.tag in ("ul", "ol"):
			lines += ["• " + " ".join("".join(item.itertext()).split()) for item in part if XML_LANGUAGE not in item.attrib]
	return "\n\n".join(line for line in lines if line)


def _releases(element):
	"""The newest releases the makers describe, newest first as AppStream lists them, to show what an update brings."""
	found = []
	for release in element.iter("release"):
		notes = _description(release)
		if not notes:
			continue
		timestamp = release.get("timestamp", "")
		date = release.get("date", "")[:10]
		if not date and timestamp.isdigit():
			date = str(datetime.fromtimestamp(int(timestamp)).date())
		found.append({"version": release.get("version", ""), "date": date, "notes": notes})
		if len(found) == RELEASES_KEPT:
			break
	return found


def _icon(element, icon_root):
	for icon in element.findall("icon"):
		if icon.get("type") != "cached" or not icon.text:
			continue
		for size in ICON_SIZES:
			candidate = icon_root / size / icon.text.strip()
			if candidate.exists():
				return QUrl.fromLocalFile(str(candidate)).toString()
	return ""


def _groups(element):
	categories = {category.text for category in element.iter("category")}
	return [name for name, members in GROUPS if categories & members]


def _entry(element, source, icon_root):
	homepage = next((url.text for url in element.findall("url") if url.get("type") == "homepage"), "")
	keywords = " ".join(keyword.text or "" for keyword in element.iter("keyword"))
	return {
		"id": (element.findtext("id") or "").strip(),
		"name": _untranslated(element, "name"),
		"summary": _untranslated(element, "summary"),
		"description": _description(element),
		"icon": _icon(element, icon_root),
		"source": source,
		"groups": _groups(element),
		"homepage": homepage or "",
		"developer": _untranslated(element, "developer_name") or (element.findtext("developer/name") or "").strip(),
		"license": (element.findtext("project_license") or "").strip(),
		"search": keywords.casefold(),
		"launchable": (element.findtext("launchable") or "").strip(),
		"releases": _releases(element),
	}


def _read_components(path):
	opener = gzip.open if path.suffix == ".gz" else open
	with opener(path, "rb") as stream:
		for _event, element in ElementTree.iterparse(stream):
			if element.tag != "component":
				continue
			if element.get("type") in APP_TYPES:
				yield element
			element.clear()


def _repository_entries():
	entries = []
	for catalog in sorted((REPOSITORY_CATALOGS / "xml").glob("*.xml.gz")):
		icon_root = REPOSITORY_CATALOGS / "icons" / catalog.name.removesuffix(".xml.gz")
		for element in _read_components(catalog):
			entry = _entry(element, OPENSUSE, icon_root)
			entry["package"] = (element.findtext("pkgname") or "").strip()
			if entry["package"] and entry["name"]:
				entries.append(entry)
	return entries


def flathub_appstream():
	"""Flathub's AppStream folder, from this user's remote when there is one, else the system's."""
	for root in FLATPAK_INSTALLATIONS.values():
		folder = root / "appstream" / paths.FLATHUB / platform.machine() / "active"
		if (folder / "appstream.xml").exists():
			return folder
	return None


def _flathub_entries():
	folder = flathub_appstream()
	if folder is None:
		return []
	entries = []
	for element in _read_components(folder / "appstream.xml"):
		entry = _entry(element, FLATHUB, folder / "icons")
		bundle = element.findtext("bundle") or ""
		# A bundle reads app/<id>/<arch>/<branch>, older entries only give the id with .desktop on the end
		entry["package"] = bundle.split("/")[1] if bundle.count("/") >= 3 else entry["id"].removesuffix(".desktop")
		if entry["name"]:
			entries.append(entry)
	return entries


def installed_packages():
	listing = subprocess.run(["rpm", "-qa", "--qf", "%{NAME}\n"], capture_output=True, text=True, check=False)
	return set(listing.stdout.split())


def installed_flatpaks():
	"""Each installed Flatpak app id and whether it is in the user or the system installation."""
	listing = subprocess.run(["flatpak", "list", "--app", "--columns=application,installation"],
		capture_output=True, text=True, check=False)
	found = {}
	for line in listing.stdout.splitlines():
		fields = line.split("\t")
		if len(fields) == 2:
			found[fields[0]] = fields[1]
	return found


def _match_keys(entry):
	"""What can tell two catalogs describe the same app, the AppStream id, its desktop id, then its name.

	A name by itself also matches unrelated apps, such as two different games called 2048, so it counts with the homepage.
	"""
	name = "".join(character for character in entry["name"].casefold() if character.isalnum())
	host = urlparse(entry["homepage"]).hostname or ""
	name_key = f"name:{name}@{host.removeprefix('www.')}" if host else ""
	ids = [entry["id"], entry["launchable"]]
	return [identifier.removesuffix(".desktop").casefold() for identifier in ids if identifier] + [name_key]


def _merge(repository, flathub):
	"""One app per id, desktop id or name, holding the openSUSE package and the Flathub app as its variants."""
	apps = [{"variants": [entry]} for entry in repository]
	index = {}
	for app in apps:
		for key in _match_keys(app["variants"][0]):
			if key:
				index.setdefault(key, app)
	for entry in flathub:
		match = next((index[key] for key in _match_keys(entry) if key and key in index), None)
		if match is not None and all(variant["source"] != FLATHUB for variant in match["variants"]):
			match["variants"].append(entry)
		else:
			apps.append({"variants": [entry]})
	for app in apps:
		first = app["variants"][0]
		app.update(key=first["source"] + ":" + first["id"], name=first["name"], summary=first["summary"],
			icon=next((variant["icon"] for variant in app["variants"] if variant["icon"]), ""),
			groups=sorted({group for variant in app["variants"] for group in variant["groups"]}),
			search=" ".join(" ".join((variant["summary"], variant["package"], variant["search"]))
				for variant in app["variants"]).casefold())
	return apps


def load_apps():
	apps = _merge(_repository_entries(), _flathub_entries())
	apps.sort(key=lambda app: app["name"].casefold())
	return apps


class AppModel(QAbstractListModel):
	"""Every app from both sources, filtered by search text, source, group and whether it is installed."""

	loaded = Signal()
	countChanged = Signal()
	_appsReady = Signal(object, object, object)

	ROLES = ["key", "name", "summary", "image", "source", "installed"]

	def __init__(self, parent=None):
		super().__init__(parent)
		self._apps = []
		self._by_key = {}
		self._key_by_package = {}
		self._shown = []
		self._packages = set()
		self._flatpaks = {}
		self._filter = ("", "", "", False)
		self.ready = False
		self._appsReady.connect(self._take_apps)

	def roleNames(self):
		return {Qt.ItemDataRole.UserRole + index: name.encode() for index, name in enumerate(self.ROLES)}

	def rowCount(self, parent=QModelIndex()):
		return 0 if parent.isValid() else len(self._shown)

	def data(self, index, role):
		if not index.isValid():
			return None
		app = self._shown[index.row()]
		name = self.ROLES[role - Qt.ItemDataRole.UserRole]
		if name == "image":
			return app["icon"]
		if name == "source":
			# A check mark names the source that is installed, so an app found in both shows which one you have
			return "  ·  ".join(("✓ " if self._installation(variant) else "") + variant["source"]
				for variant in self._listed_variants(app))
		if name == "installed":
			return any(self._installation(variant) for variant in app["variants"])
		return app[name]

	def _listed_variants(self, app):
		"""The Installed page names only the sources that are really installed."""
		installed = [variant for variant in app["variants"] if self._installation(variant)]
		return installed if self._filter[3] else app["variants"]

	def _installation(self, variant):
		"""Where this source of the app is installed, an empty string when it is not."""
		if variant["source"] == OPENSUSE:
			return "system" if variant["package"] in self._packages else ""
		return self._flatpaks.get(variant["package"], "")

	@Slot()
	def load(self):
		"""Read both catalogs in a process of their own, the Flathub one is about 50 MB of XML.

		A thread would hold Python's lock while it parses and leave the window stuck for seconds.
		The process is started fresh rather than forked, a fork of a running Qt program is not safe.
		"""
		def read():
			with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn")) as pool:
				apps = pool.submit(load_apps).result()
			self._appsReady.emit(apps, installed_packages(), installed_flatpaks())
		threading.Thread(target=read, daemon=True).start()

	@Slot()
	def refreshInstalled(self):
		self._packages = installed_packages()
		self._flatpaks = installed_flatpaks()
		self._apply_filter()

	def _take_apps(self, apps, packages, flatpaks):
		self._apps = apps
		self._by_key = {app["key"]: app for app in apps}
		self._key_by_package = {}
		for app in apps:
			for variant in app["variants"]:
				self._key_by_package.setdefault((variant["source"], variant["package"]), app["key"])
		self._packages = packages
		self._flatpaks = flatpaks
		self._apply_filter()
		self.ready = True
		self.loaded.emit()

	@Slot(str, str, str, bool)
	def setFilter(self, text, source, group, installed_only):
		self._filter = (text.strip().casefold(), source, group, installed_only)
		self._apply_filter()

	def _matches(self, app):
		text, source, group, _installed_only = self._filter
		variants = self._listed_variants(app)
		if not variants:
			return False
		if source and all(variant["source"] != source for variant in variants):
			return False
		if group and group not in app["groups"]:
			return False
		if not text:
			return True
		haystack = app["name"].casefold() + " " + app["search"]
		return all(word in haystack for word in text.split())

	def _apply_filter(self):
		self.beginResetModel()
		self._shown = [app for app in self._apps if self._matches(app)]
		text = self._filter[0]
		if text:
			# Names that start with the search come first, the rest keep their alphabetical order
			self._shown.sort(key=lambda app: not app["name"].casefold().startswith(text))
		self.endResetModel()
		self.countChanged.emit()

	def _get_count(self):
		return len(self._shown)

	@Slot(result="QStringList")
	def groups(self):
		return [name for name, _members in GROUPS]

	@Slot(str, str, result="QVariantMap")
	def entry(self, key, source):
		"""One source of an app for its page, the given one, else the installed one, else openSUSE."""
		app = self._by_key.get(key)
		if app is None:
			return {}
		variants = app["variants"]
		installed = [variant for variant in variants if self._installation(variant)]
		chosen = next((variant for variant in variants if variant["source"] == source), None)
		chosen = chosen or (installed[0] if len(installed) == 1 else variants[0])
		choices = [{"source": variant["source"], "installed": self._installation(variant) != ""}
			for variant in variants]
		return dict(chosen, key=key, installation=self._installation(chosen), kind="app", choices=choices)

	@Slot(str, str, result=str)
	def findKey(self, source, package):
		"""The key of the app a package or Flatpak id belongs to, so a link can open its page."""
		return self._key_by_package.get((source, package), "")

	count = Property(int, _get_count, notify=countChanged)
