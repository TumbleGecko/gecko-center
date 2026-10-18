"""The software sources zypper installs from, what each one is for and whether openSUSE builds it."""

import re
import xml.etree.ElementTree as ElementTree

from . import look, paths

# Hosts openSUSE builds the distribution on, its build service projects under /repositories/ are other people's
OPENSUSE_HOSTS = ("download.opensuse.org", "cdn.opensuse.org", "codecs.opensuse.org")
COMMUNITY_PATH = "/repositories/"
PERSONAL_PATH = "/repositories/home:"

OPENSUSE = "openSUSE"
VENDOR = "vendor"
COMMUNITY = "community"
OTHER = "other"

BUILDERS = {
	OPENSUSE: "Built by openSUSE", VENDOR: "Built by the maker of the software",
	COMMUNITY: "Built by a community project", OTHER: "Built by others",
}

# Plain words for the sources a Tumbleweed install or TumbleGecko adds, matched against the address
KNOWN_SOURCES = [
	(r"/tumbleweed/repo/oss", "The main openSUSE collection, almost everything on the system comes from here."),
	(r"/tumbleweed/repo/non-oss", "Free to use software from openSUSE whose source code is not open."),
	(r"/update/tumbleweed", "Urgent fixes between snapshots, usually empty."),
	(r"codecs\.opensuse\.org/openh264", "The video codec Cisco builds and pays the licence for, used for video calls."),
	(r"/debug/", "Extra files for reporting crashes. Only developers need them."),
	(r"/source/", "The source code of every package. Only developers need it."),
	(r"download\.nvidia\.com", "The NVIDIA graphics driver, built by NVIDIA for openSUSE."),
	(r"packman", "Media codecs openSUSE may not ship, built by the Packman volunteers."),
	(r"packages\.microsoft\.com", "Visual Studio Code and other Microsoft software, built by Microsoft."),
	(r"/repositories/home:", "A personal project on the openSUSE build service, built by one person."),
	(r"/repositories/", "A project on the openSUSE build service, built by its own team rather than openSUSE."),
]


# Why a turned on source could get in the way of updates, each with the test that finds it
RISKS = [
	(lambda source, others: PERSONAL_PATH in source["url"],
		"It can fall behind Tumbleweed and hold back updates."),
	(lambda source, others: source["kind"] == COMMUNITY and PERSONAL_PATH not in source["url"],
		"Its packages can replace openSUSE's own and hold back updates."),
	(lambda source, others: source["kind"] == OTHER and not source["about"],
		"Its builder is unknown, so there is no telling how well it follows Tumbleweed."),
	(lambda source, others: re.search(r"leap|sle_?\d|/1[56]\.\d", source["url"], re.IGNORECASE),
		"It is made for another openSUSE release, and its packages can break Tumbleweed."),
	(lambda source, others: not source["signed"],
		"Its packages are not checked for a signature, so anyone in between could change them."),
	(lambda source, others: any(other["url"].rstrip("/") == source["url"].rstrip("/") for other in others),
		"Another turned on source has the same address, so its packages are listed twice."),
]


def _kind(url):
	host = re.sub(r"^\w+://", "", url).split("/", 1)[0]
	if host in OPENSUSE_HOSTS and COMMUNITY_PATH not in url:
		return OPENSUSE
	if COMMUNITY_PATH in url:
		return COMMUNITY
	if "nvidia.com" in host or "microsoft.com" in host:
		return VENDOR
	return OTHER


def _about(url):
	return next((words for pattern, words in KNOWN_SOURCES if re.search(pattern, url)), "")


def read_sources():
	"""Every source with its alias, name, address, kind, description and risks, None when zypper cannot list them."""
	listing = look.run([paths.ZYPPER, "--no-refresh", "--xmlout", "repos", "--uri"])
	start = listing.stdout.find("<?xml")
	if start < 0:
		return None
	stream = ElementTree.fromstring(listing.stdout[start:])
	sources = []
	for repo in stream.iter("repo"):
		url = repo.findtext("url", "")
		sources.append({
			"alias": repo.get("alias", ""),
			"name": repo.get("name") or repo.get("alias", ""),
			"url": url,
			"enabled": repo.get("enabled") == "1",
			"kind": _kind(url),
			"builder": BUILDERS[_kind(url)],
			"about": _about(url),
			"signed": repo.get("gpgcheck") != "0",
		})
	for source in sources:
		others = [other for other in sources if other is not source and other["enabled"]]
		source["risks"] = [words for test, words in RISKS if test(source, others)] if source["enabled"] else []
	# Sources that could cause trouble first, then openSUSE's own, then the ones that are on, each group by name
	sources.sort(key=lambda source: (not source["risks"], source["kind"] != OPENSUSE, not source["enabled"],
		source["name"].lower()))
	return sources


def _summaries():
	listing = look.run(["rpm", "--query", "--all", "--queryformat", "%{NAME}\t%{SUMMARY}\n"])
	return dict(line.split("\t", 1) for line in listing.stdout.splitlines() if "\t" in line)


def installed_by_source():
	"""The installed packages each source gave, by source alias, each with a short description."""
	listing = look.run([paths.ZYPPER, "--no-refresh", "--xmlout", "search", "--installed-only", "--details"])
	start = listing.stdout.find("<?xml")
	if start < 0:
		return {}
	summaries = _summaries()
	found = {}
	# zypper names the source whose copy matches the installed version, a package can match more than one
	for solvable in ElementTree.fromstring(listing.stdout[start:]).iter("solvable"):
		if solvable.get("kind") != "package":
			continue
		name = solvable.get("name", "")
		found.setdefault(solvable.get("repository", ""), []).append({
			"name": name,
			"summary": summaries.get(name, ""),
			"installed": True,
		})
	for packages in found.values():
		packages.sort(key=lambda package: package["name"].lower())
	return found


def switch_arguments(alias, enabled):
	return [paths.ZYPPER, "--non-interactive", "modifyrepo", "--enable" if enabled else "--disable", "--", alias]


def remove_arguments(alias):
	return [paths.ZYPPER, "--non-interactive", "removerepo", "--", alias]
