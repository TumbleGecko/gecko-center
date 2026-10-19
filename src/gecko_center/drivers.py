"""The graphics cards and the driver each one uses, the NVIDIA driver install, and firmware updates from fwupd.

The NVIDIA steps follow openSUSE's driver maintainer, https://sndirsch.github.io/nvidia/2025/07/16/nvidia-drivers.html
"""

import html
import json
import re

from . import look, operations, paths

NVIDIA_VENDOR = "10de"
DISPLAY_CLASS = re.compile(r"\[03[0-9a-f]{2}\]$")
# The open driver for GeForce 16, RTX 20 and newer, its generation number is looked up when it installs
NVIDIA_REPOSITORY_PACKAGE = "openSUSE-repos-Tumbleweed-NVIDIA"
NVIDIA_META_PATTERN = "nvidia-open-driver-G*-signed-kmp-meta"

# Plain words for the drivers a card can be using
DRIVERS = {
	"nvidia": "NVIDIA's own driver, the fast one for games.",
	"nouveau": "The basic open driver. It shows a picture but is slow for games.",
	"amdgpu": "The AMD driver built into Linux. There is nothing to install.",
	"radeon": "The driver built into Linux for older AMD cards.",
	"i915": "The Intel driver built into Linux. There is nothing to install.",
	"xe": "The Intel driver built into Linux. There is nothing to install.",
	"virtio-pci": "The driver for a virtual machine's screen.",
}


def without_code(text):
	"""lspci adds the numeric id in brackets after each name."""
	return re.sub(r"\s*\[[0-9a-f]{4}\]$", "", text).strip()


def product_name(text):
	"""lspci names a card as 'AD102 [GeForce RTX 4090]', the bracket holds the name people know and the chip goes after it."""
	named = re.fullmatch(r"(.*?)\s*\[([^\[\]]+)\]", text)
	return f"{named.group(2)} ({named.group(1)})" if named and named.group(1) else text


def nvidia_version():
	"""The version of the NVIDIA module the kernel has loaded, empty when it is not loaded."""
	try:
		with open("/sys/module/nvidia/version", encoding="utf-8") as source:
			return source.read().strip()
	except OSError:
		return ""


def pci_devices():
	"""Each PCI device as lspci names its fields, with its full address in Slot and its driver in Driver."""
	listing = look.run(["lspci", "-vmm", "-k", "-nn", "-D"])
	devices = []
	for record in listing.stdout.split("\n\n"):
		fields = {}
		for line in record.splitlines():
			key, _, value = line.partition(":\t")
			fields.setdefault(key, value)
		if fields.get("Slot"):
			devices.append(fields)
	return devices


def graphics_cards():
	cards = []
	for fields in pci_devices():
		if not DISPLAY_CLASS.search(fields.get("Class", "")):
			continue
		vendor = re.search(r"\[([0-9a-f]{4})\]$", fields.get("Vendor", ""))
		driver = fields.get("Driver", "")
		cards.append({
			"name": product_name(without_code(fields.get("Device", ""))),
			"maker": without_code(fields.get("Vendor", "")),
			"vendor": vendor.group(1) if vendor else "",
			"driver": driver,
			"about": DRIVERS.get(driver, "No driver is in use." if not driver else ""),
			"version": nvidia_version() if driver == "nvidia" else "",
			"wantsNvidia": vendor is not None and vendor.group(1) == NVIDIA_VENDOR and driver != "nvidia",
		})
	return cards


def nvidia_steps():
	"""Add NVIDIA's source the way the installer does, then the newest open driver generation it offers."""
	newest = (f"name=$({paths.ZYPPER} --quiet --no-refresh search --type package '{NVIDIA_META_PATTERN}'"
		" | awk -F'|' '{gsub(/ /, \"\", $2); print $2}' | grep '^nvidia-open-driver-G[0-9]*-signed-kmp-meta$'"
		f" | sort --version-sort | tail -n 1) && [ -n \"$name\" ] && {paths.ZYPPER} --non-interactive install"
		" --auto-agree-with-licenses \"$name\"")
	return [
		operations.zypper_step("Adding NVIDIA's software source", [paths.ZYPPER, "--non-interactive", "install",
			"--auto-agree-with-licenses", NVIDIA_REPOSITORY_PACKAGE]),
		operations.zypper_step("Reading NVIDIA's software source", [paths.ZYPPER, "--non-interactive", "refresh"]),
		operations.zypper_step("Installing the NVIDIA driver", ["/bin/sh", "-c", newest]),
	]


def _plain(text):
	return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


# fwupd lists each Secure Boot certificate as a device, they are not firmware a person updates
CERTIFICATE_PLUGINS = ("uefi_kek", "uefi_pk", "uefi_db", "uefi_dbx")
# How firmware that fwupd cannot update gets its updates, by the fwupd plugin that found it
UPDATED_BY = {"cpu": "With system updates", "pci_psp": "With the motherboard firmware",
	"tpm": "With the motherboard firmware"}
NOT_THROUGH_LINUX = "Not through Linux"
# What Hardware says about firmware the Drivers page can update, the same place a person goes for it
UPDATED_ON_PAGE = "On the Drivers page"


def updated_by(item):
	"""How firmware Drivers cannot update gets its updates, in the words both pages use."""
	return UPDATED_BY.get(item.get("Plugin", ""), NOT_THROUGH_LINUX)


def fwupd_devices():
	"""Every device fwupd knows, with its firmware version, read without root."""
	listing = look.run(["fwupdmgr", "get-devices", "--json"])
	start = listing.stdout.find("{")
	try:
		return json.loads(listing.stdout[start:]).get("Devices", []) if start >= 0 else []
	except ValueError:
		return []


def all_firmware(updates):
	"""Each device's firmware with its version, and the newer one when fwupd has it, updates first."""
	newer = {device["id"]: device for device in updates["devices"]}
	found = []
	for item in fwupd_devices():
		if not item.get("Name") or item.get("Plugin") in CERTIFICATE_PLUGINS:
			continue
		update = newer.get(item.get("DeviceId", ""))
		found.append({"id": item.get("DeviceId", ""), "name": item["Name"], "vendor": item.get("Vendor", ""),
			"current": item.get("Version", ""), "update": update,
			"updatable": "updatable" in (item.get("Flags") or []),
			"updatedBy": updated_by(item)})
	return sorted(found, key=lambda device: device["update"] is None)


def firmware_updates():
	"""Each device fwupd has newer firmware for, from the list it downloaded last from the LVFS, read without root."""
	listing = look.run(["fwupdmgr", "get-updates", "--json"])
	if listing.returncode == 127:
		return {"known": False, "problem": "fwupd is not installed.", "devices": []}
	start = listing.stdout.find("{")
	if start < 0:
		return {"known": True, "problem": "", "devices": []}
	devices = []
	for device in json.loads(listing.stdout[start:]).get("Devices", []):
		releases = device.get("Releases") or []
		if not releases:
			continue
		newest = releases[0]
		devices.append({
			"id": device.get("DeviceId", ""),
			"name": newest.get("Name") or device.get("Name", ""),
			"vendor": device.get("Vendor", ""),
			"current": device.get("Version", ""),
			"newest": newest.get("Version", ""),
			"about": _plain(newest.get("Description", "")) or newest.get("Summary", ""),
			"security": bool(newest.get("Issues")),
			"restart": "needs-reboot" in (device.get("Flags") or []),
		})
	return {"known": True, "problem": "", "devices": devices}


def firmware_steps(device_id):
	"""fwupd downloads the newest list from the LVFS first, then installs only the one device's firmware."""
	return [
		operations.Step("Reading the newest firmware list", ["fwupdmgr", "refresh", "--force"], root=True),
		operations.Step("Updating firmware", ["fwupdmgr", "update", "--assume-yes", "--no-reboot-check", device_id],
			root=True),
	]


def collect():
	updates = firmware_updates()
	return {"cards": graphics_cards(), "firmware": updates, "allFirmware": all_firmware(updates)}
