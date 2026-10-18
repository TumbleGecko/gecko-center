"""The technical side of an app, what its package needs, what needs it, and what a Flatpak may reach."""

import configparser

from . import packages, paths

FLATHUB_REMOTE = "flathub"
# zypper info lines name these, the page shows them in plain words
PACKAGE_FACTS = [("Name", "Package"), ("Arch", "Architecture"), ("Repository", "Repository"),
	("Source package", "Source package")]
FLATPAK_FACTS = [("ID", "ID"), ("Branch", "Branch"), ("Arch", "Architecture"), ("Origin", "Origin"),
	("Runtime", "Runtime"), ("Sdk", "SDK")]
# Flatpak's metadata keys, see man flatpak-metadata
PERMISSION_NAMES = {"shared": "Shares", "sockets": "Sockets", "devices": "Devices", "filesystems": "Files",
	"features": "Features", "persistent": "Keeps folders", "Session Bus Policy": "Talks to",
	"System Bus Policy": "Talks to the system"}


def requires_arguments(name):
	return [paths.ZYPPER, "--non-interactive", "--no-refresh", "info", "--requires", "--", name]


def package_info(text):
	"""The facts the page shows, whether it is installed, and what it requires as zypper's capability strings."""
	fields = {}
	capabilities = []
	in_requires = False
	for line in text.splitlines():
		if in_requires and line.startswith(" "):
			capabilities.append(line.strip())
			continue
		in_requires = False
		key, separator, value = line.partition(" : ")
		if not separator:
			continue
		key = key.strip()
		in_requires = key == "Requires"
		fields[key] = value.strip()
	facts = [[label, fields[key]] for key, label in PACKAGE_FACTS if fields.get(key)]
	installed = fields.get("Installed", "No")
	if installed.startswith("Yes"):
		facts.append(["Installed", "Automatically, another package needed it" if "automatically" in installed
			else "By choice"])
	# rpmlib names features of rpm itself, no package provides them, and an exact search takes no version
	capabilities = list(dict.fromkeys(capability.split(" ")[0] for capability in capabilities
		if not capability.startswith("rpmlib(")))
	return {"facts": facts, "installed": installed.startswith("Yes"), "capabilities": capabilities}


def provider_searches(capabilities, installed_only):
	"""The searches for what provides a package's requirements, the installed providers when it is installed.

	One file path turns all of zypper's search into a file search, so paths get a search of their own.
	"""
	scope = ["--installed-only"] if installed_only else []
	paths_needed = [capability for capability in capabilities if capability.startswith("/")]
	names_needed = [capability for capability in capabilities if not capability.startswith("/")]
	return [[paths.ZYPPER, "--non-interactive", "--no-refresh", "--xmlout", "search", "--type", "package", *scope,
		"--provides", "--match-exact", "--", *group] for group in (names_needed, paths_needed) if group]


def needed_by_arguments(name):
	return [paths.ZYPPER, "--non-interactive", "--no-refresh", "--xmlout", "search", "--type", "package",
		"--installed-only", "--requires-pkg", "--", name]


def packages_from_searches(outputs, own_name):
	"""Each package once by name across the searches, without the package the page is about."""
	found = {}
	for result in (result for output in outputs for result in packages.search_results_from_xml(output)):
		if result["name"] != own_name:
			found.setdefault(result["name"], result)
	return sorted(found.values(), key=lambda result: result["name"].casefold())


def flatpak_info_arguments(app_id, installation):
	if installation:
		return ["flatpak", "info", f"--{installation}", app_id]
	return ["flatpak", "remote-info", "--system", FLATHUB_REMOTE, app_id]


def flatpak_permissions_arguments(app_id, installation):
	return ["flatpak", "info", f"--{installation}", "--show-permissions", app_id]


def flatpak_facts(text):
	fields = {}
	for line in text.splitlines():
		key, separator, value = line.partition(":")
		if separator:
			fields[key.strip()] = value.strip()
	return [[label, fields[key]] for key, label in FLATPAK_FACTS if fields.get(key)]


def flatpak_permissions(text):
	"""Each permission group with its values, the bus groups name each service the app may talk to."""
	metadata = configparser.ConfigParser(interpolation=None, delimiters=("=",))
	metadata.optionxform = str
	try:
		metadata.read_string(text)
	except configparser.Error:
		return []
	found = []
	for section in metadata.sections():
		values = metadata[section]
		if section == "Context":
			found += [[PERMISSION_NAMES.get(key, key), ", ".join(filter(None, value.split(";")))]
				for key, value in values.items()]
		else:
			found.append([PERMISSION_NAMES.get(section, section), ", ".join(f"{key} ({value})" for key, value in values.items())])
	return [permission for permission in found if permission[1]]
