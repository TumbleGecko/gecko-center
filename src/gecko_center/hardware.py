"""Each part of the computer in groups, what each one is, the driver it uses, its firmware and its temperature.

All of it reads without root, from lspci, lscpu, lsblk, fwupd, kscreen-doctor and the files in /sys.
"""

import json
import math
import re
from pathlib import Path

from . import drivers, look

SYS = Path("/sys")
DMI = SYS / "class" / "dmi" / "id"
HWMON = SYS / "class" / "hwmon"
USB = SYS / "bus" / "usb" / "devices"
NETWORK = SYS / "class" / "net"
POWER = SYS / "class" / "power_supply"
DRM = SYS / "class" / "drm"
PCI = SYS / "bus" / "pci" / "devices"
I2C_DRIVERS = SYS / "bus" / "i2c" / "drivers"
MEMINFO = Path("/proc/meminfo")

# Makers put these in place of a product name on boards sold on their own
PLACEHOLDERS = {"", "system product name", "to be filled by o.e.m.", "default string", "not applicable"}
# The chassis types in the SMBIOS specification, grouped the way people talk about computers
CHASSIS = {3: "Desktop", 4: "Desktop", 6: "Tower", 7: "Tower", 8: "Laptop", 9: "Laptop", 10: "Laptop", 14: "Laptop",
	13: "All in one", 30: "Tablet", 31: "Convertible", 32: "Convertible", 35: "Mini PC", 36: "Mini PC"}
CPU_MAKERS = {"AuthenticAMD": "AMD", "GenuineIntel": "Intel"}
CPU_SENSORS = ("k10temp", "coretemp", "zenpower")

# Each memory module's SPD chip, by its driver, with where the maker code and part number sit, DDR5 then DDR4
SPD_LAYOUTS = {"spd5118": (512, 521, 551), "ee1004": (320, 329, 349)}
# JEDEC JEP106 maker codes as SPD stores them, the bank byte first with its parity bit
MEMORY_MAKERS = {"80ce": "Samsung", "80ad": "SK hynix", "802c": "Micron", "0198": "Kingston", "029e": "Corsair",
	"04cd": "G.Skill", "04cb": "ADATA", "04ef": "TeamGroup", "859b": "Crucial"}

# The PCI class code's first two digits, bridges are wiring, not parts, so they are not listed
PCI_GROUPS = {"03": "Graphics", "04": "Sound", "02": "Network", "0d": "Network"}
PCI_HIDDEN = ("06",)
# A USB device goes in the group of the first of these interface classes it has
USB_GROUPS = (("01", "Sound"), ("0e", "Cameras"), ("e0", "Network"), ("03", "Input"))
USB_HUB = "09"
USB_SPEEDS = {1.5: "USB 1", 12: "USB 1", 480: "USB 2", 5000: "USB 3", 10000: "USB 3", 20000: "USB 3", 40000: "USB 4"}

# The three letter maker code at the start of a screen's EDID
SCREEN_MAKERS = {"SAM": "Samsung", "DEL": "Dell", "GSM": "LG", "ACR": "Acer", "AUS": "ASUS", "BNQ": "BenQ",
	"AOC": "AOC", "PHL": "Philips", "LEN": "Lenovo", "HWP": "HP", "MSI": "MSI", "GBT": "Gigabyte", "VSC": "ViewSonic",
	"ENC": "EIZO", "SNY": "Sony", "AOU": "AU Optronics", "BOE": "BOE", "CMN": "Innolux", "SHP": "Sharp"}
EDID_NAME = 0xFC
CENTIMETRES_PER_INCH = 2.54
# kscreen-doctor waits for KDE's screen service, which does not answer outside a Plasma session
SCREEN_SECONDS = 5
# How lsblk names each connection, written the way the makers do
CONNECTIONS = {"NVME": "NVMe", "SATA": "SATA", "USB": "USB", "MMC": "SD card"}
# A flash disk is named by its connection, these connections are named on their own
DISK_KINDS = {"USB": "USB drive", "SD card": "SD card"}

# fwupd lists each Secure Boot certificate as a device, they are kept together as one entry
CERTIFICATE_PLUGINS = ("uefi_kek", "uefi_pk", "uefi_db", "uefi_dbx")

GROUP_ORDER = ("Computer", "Processor", "Memory", "Graphics", "Displays", "Storage", "Sound", "Network", "Input",
	"Cameras", "Batteries", "Other USB devices", "Controllers", "Firmware")


def _read(path):
	try:
		return Path(path).read_text(encoding="utf-8", errors="replace").strip()
	except OSError:
		return ""


def _resolved(path):
	try:
		return str(Path(path).resolve(strict=True))
	except OSError:
		return ""


def _device(key, group, name, kind, summary, facts):
	"""One entry of the page, its facts kept in order and the empty ones left out."""
	return {"key": key, "group": group, "name": name, "kind": kind, "summary": summary,
		"facts": [[label, value] for label, value in facts if value]}


def _bytes_text(count):
	"""Disk makers count in thousands, so a 2 TB disk reads 2 TB here too."""
	for unit, size in (("TB", 10 ** 12), ("GB", 10 ** 9), ("MB", 10 ** 6)):
		if count >= size:
			return f"{count / size:.1f} {unit}".replace(".0 ", " ")
	return f"{count} bytes"


def _maker(text):
	"""lspci adds the short name people know in brackets, such as AMD after Advanced Micro Devices, Inc."""
	short = re.search(r"\[([^\[\]]+)\]$", text)
	return short.group(1) if short else text


def _speed_text(megabits):
	if megabits >= 1000:
		return f"{megabits / 1000:g} Gbit/s"
	return f"{megabits:g} Mbit/s"


# Temperatures =================================================================


def _sensors():
	"""Each temperature sensor by the real path of the device it measures, with its name and degrees."""
	found = []
	for sensor in sorted(HWMON.glob("hwmon*")):
		reading = _read(sensor / "temp1_input")
		if reading.lstrip("-").isdigit():
			found.append((_resolved(sensor / "device"), _read(sensor / "name"), int(reading) / 1000))
	return found


def _temperature(sensors, device_path):
	"""The first sensor on the device or on a part of it, in degrees.

	A chip reached over the device's I2C bus, such as a memory module behind the SMBus, is a part of its own.
	"""
	for path, _name, degrees in sensors:
		if device_path and path.startswith(device_path) and "/i2c-" not in path[len(device_path):]:
			return f"{degrees:.0f} °C"
	return ""


# The computer, its processor and memory =======================================


def _computer(firmware):
	product = _read(DMI / "product_name")
	board = " ".join(part for part in (_read(DMI / "board_vendor"), _read(DMI / "board_name")) if part)
	known_product = product.lower() not in PLACEHOLDERS
	chassis = _read(DMI / "chassis_type")
	name = product if known_product else _read(DMI / "board_name") or "This computer"
	kind = CHASSIS.get(int(chassis), "Computer") if chassis.isdigit() else "Computer"
	system_firmware = next((item for item in firmware if item.get("Plugin") == "uefi_capsule"), {})
	return [_device("computer", "Computer", name, kind, board if known_product else _read(DMI / "sys_vendor"), [
		("Maker", _read(DMI / "sys_vendor")), ("Model", product if known_product else ""), ("Motherboard", board),
		("Firmware maker", _read(DMI / "bios_vendor")), ("Firmware version", _read(DMI / "bios_version")),
		("Firmware date", _read(DMI / "bios_date")), ("Firmware build", system_firmware.get("Version", "")),
	])]


def _processor(sensors, firmware):
	listing = look.run(["lscpu", "--json"])
	try:
		fields = {item["field"].rstrip(":"): item["data"] for item in json.loads(listing.stdout)["lscpu"]}
	except (ValueError, KeyError):
		return []
	threads = fields.get("CPU(s)", "")
	cores = ""
	if fields.get("Core(s) per socket", "").isdigit() and fields.get("Socket(s)", "").isdigit():
		cores = str(int(fields["Core(s) per socket"]) * int(fields["Socket(s)"]))
	fastest = fields.get("CPU max MHz", "").replace(",", ".")
	fastest = f"{float(fastest) / 1000:.1f} GHz" if re.fullmatch(r"[\d.]+", fastest) else ""
	sensor = next((path for path, name, _degrees in sensors if name in CPU_SENSORS), "")
	microcode = next((item.get("Version", "") for item in firmware if item.get("Plugin") == "cpu"), "")
	summary = ", ".join(part for part in (cores and look.plural(int(cores), "core"),
		threads and threads + " threads", fastest and "up to " + fastest) if part)
	return [_device("processor", "Processor", fields.get("Model name", "Processor"), "Processor", summary, [
		("Maker", CPU_MAKERS.get(fields.get("Vendor ID", ""), fields.get("Vendor ID", ""))), ("Cores", cores),
		("Threads", threads), ("Fastest speed", fastest), ("Cache", fields.get("L3 cache", "").split(" (")[0]),
		("Architecture", fields.get("Architecture", "")), ("Temperature", _temperature(sensors, sensor)),
		("Microcode", microcode),
	])]


def _memory_modules(sensors):
	"""Each memory module that shows its SPD chip, read as you since the chips are readable by everyone."""
	modules = []
	for driver, (maker_at, part_at, part_end) in SPD_LAYOUTS.items():
		for chip in sorted((I2C_DRIVERS / driver).glob("*-*")):
			try:
				data = (chip / "eeprom").read_bytes()
			except OSError:
				continue
			part = data[part_at:part_end].decode("ascii", errors="ignore").strip()
			maker = MEMORY_MAKERS.get(data[maker_at:maker_at + 2].hex(), "")
			slot = len(modules) + 1
			modules.append(_device(f"memory:{chip.name}", "Memory", part or f"Module {slot}", "Memory module",
				maker, [("Maker", maker), ("Part number", part), ("Kind", "DDR5" if driver == "spd5118" else "DDR4"),
					("Temperature", _temperature(sensors, _resolved(chip)))]))
	return modules


def _memory(sensors):
	found = re.search(r"MemTotal:\s+(\d+) kB", _read(MEMINFO))
	total = int(found.group(1)) * 1024 if found else 0
	modules = _memory_modules(sensors)
	# What Linux reports is a little below what the modules hold, since the firmware keeps a part for itself
	total_text = f"{total / 1024 ** 3:.0f} GB" if total else ""
	summary = total_text + (f" in {look.plural(len(modules), 'module')}" if modules else "")
	return [_device("memory", "Memory", "Memory", "All memory", summary, [
		("Usable", total_text), ("Modules", str(len(modules)) if modules else ""),
	])] + modules


# Parts on the PCI bus and USB ==================================================


def _pci_link(slot):
	"""How fast the part's slot runs now, and how fast it could."""
	device = PCI / slot
	now = _read(device / "current_link_speed").replace(" PCIe", "")
	width = _read(device / "current_link_width")
	if not now or now.startswith("Unknown") or width in ("", "0"):
		return ""
	best = _read(device / "max_link_speed").replace(" PCIe", "")
	best_width = _read(device / "max_link_width")
	if not best or (best, best_width) == (now, width):
		return f"{now} x{width}"
	# Cards and controllers slow their slot down while idle, so the lower speed now is normal
	return f"{now} x{width} now, up to {best} x{best_width}"


def _network_facts(slot):
	"""The connection the part gives, matched by the network interface on it."""
	for interface in sorted(NETWORK.iterdir()) if NETWORK.exists() else []:
		if _resolved(interface / "device") != _resolved(PCI / slot):
			continue
		speed = _read(interface / "speed")
		connected = _read(interface / "operstate") == "up"
		return [("Connection", interface.name), ("State", "Connected" if connected else "Not connected"),
			("Link speed", _speed_text(int(speed)) if connected and speed.isdigit() and int(speed) > 0 else "")]
	return []


def _pci_parts(sensors, cards):
	parts = []
	for fields in drivers.pci_devices():
		code = re.search(r"\[([0-9a-f]{4})\]$", fields.get("Class", ""))
		prefix = code.group(1)[:2] if code else ""
		if prefix in PCI_HIDDEN:
			continue
		slot = fields["Slot"]
		group = PCI_GROUPS.get(prefix, "Controllers")
		name = drivers.product_name(drivers.without_code(fields.get("Device", "")))
		maker = _maker(drivers.without_code(fields.get("Vendor", "")))
		kind = drivers.without_code(fields.get("Class", ""))
		driver = fields.get("Driver", "")
		card = next((item for item in cards if item["name"] == name), {}) if group == "Graphics" else {}
		facts = [("Maker", maker), ("Kind", kind), ("Driver", driver or "None in use"), ("About the driver",
			card.get("about", "")), ("Driver version", card.get("version", "")), ("Slot speed", _pci_link(slot))]
		if group == "Network":
			facts += _network_facts(slot)
		facts += [("Temperature", _temperature(sensors, _resolved(PCI / slot))), ("Address", slot)]
		parts.append(_device(f"pci:{slot}", group, name, kind, maker, facts))
	return parts


def _usb_group(device):
	classes = [_read(interface / "bInterfaceClass") for interface in sorted(device.glob(device.name + ":*"))]
	return next((group for code, group in USB_GROUPS if code in classes), "Other USB devices")


def _usb_parts():
	parts = []
	for device in sorted(USB.glob("*-*")) if USB.exists() else []:
		# Interfaces have a colon in their name, root hubs and hubs are wiring
		if ":" in device.name or _read(device / "bDeviceClass") == USB_HUB:
			continue
		name = _read(device / "product") or "USB device"
		maker = _read(device / "manufacturer")
		speed = _read(device / "speed")
		speed_text = ""
		# The device's own version is two binary coded decimal bytes, 0124 reads 1.24
		version = _read(device / "bcdDevice")
		version = f"{int(version[:2])}.{version[2:]}" if re.fullmatch(r"\d{4}", version) else version
		if re.fullmatch(r"[\d.]+", speed):
			megabits = float(speed)
			speed_text = _speed_text(megabits) + (f", {USB_SPEEDS[megabits]}" if megabits in USB_SPEEDS else "")
		used = sorted({(interface / "driver").resolve().name for interface in device.glob(device.name + ":*")
			if (interface / "driver").exists()})
		parts.append(_device(f"usb:{device.name}", _usb_group(device), name, "USB device", maker, [
			("Maker", maker), ("Connection", speed_text), ("Drivers", ", ".join(used) or "None in use"),
			("Firmware version", version), ("Port", device.name),
		]))
	return parts


# Displays, disks and batteries ================================================


def _edid_facts(data):
	"""The screen's own name, maker and size from its EDID, the serial number is left out."""
	if len(data) < 128:
		return "", "", ""
	letters = int.from_bytes(data[8:10], "big")
	code = "".join(chr(((letters >> shift) & 0x1F) + 64) for shift in (10, 5, 0))
	name = ""
	for start in range(54, 126, 18):
		block = data[start:start + 18]
		if block[0:2] == b"\0\0" and block[3] == EDID_NAME:
			name = block[5:18].split(b"\n")[0].decode("ascii", errors="ignore").strip()
	size = ""
	if data[21] and data[22]:
		inches = math.hypot(data[21], data[22]) / CENTIMETRES_PER_INCH
		size = f'{inches:.0f}" ({data[21]} × {data[22]} cm)'
	return name, SCREEN_MAKERS.get(code, code), size


def _screen_modes():
	"""What KDE runs each screen at, by its connector name."""
	listing = look.run(["kscreen-doctor", "--json"], SCREEN_SECONDS)
	try:
		outputs = json.loads(listing.stdout).get("outputs", [])
	except ValueError:
		return {}
	modes = {}
	for output in outputs:
		mode = next((item for item in output.get("modes", []) if item.get("id") == output.get("currentModeId")), None)
		if mode:
			size = mode.get("size", {})
			modes[output.get("name", "")] = (f"{size.get('width')} × {size.get('height')}",
				f"{mode.get('refreshRate', 0):.0f} Hz", output.get("scale", 1))
	return modes


def _displays():
	screens = []
	modes = _screen_modes()
	slots = {fields["Slot"]: fields for fields in drivers.pci_devices()}
	for connector in sorted(DRM.glob("card*-*")):
		if _read(connector / "status") != "connected":
			continue
		port = connector.name.split("-", 1)[1]
		try:
			name, maker, size = _edid_facts((connector / "edid").read_bytes())
		except OSError:
			name, maker, size = "", "", ""
		resolution, refresh, scale = modes.get(port, ("", "", 1))
		card_slot = Path(_resolved(connector / "device")).parent.parent.name
		card = slots.get(card_slot, {})
		card_name = drivers.product_name(drivers.without_code(card.get("Device", ""))) if card else ""
		summary = f"{resolution} at {refresh}" if resolution else port
		screens.append(_device(f"display:{connector.name}", "Displays", name or port, "Screen", summary, [
			("Maker", maker), ("Size", size), ("Resolution", resolution), ("Refresh rate", refresh),
			("Scale", f"{scale * 100:.0f} %" if resolution else ""), ("Port", port), ("Graphics", card_name),
		]))
	return screens


def _disks(sensors):
	listing = look.run(["lsblk", "--json", "--nodeps", "--bytes", "--output", "NAME,MODEL,SIZE,TRAN,ROTA,TYPE,REV"])
	try:
		blocks = json.loads(listing.stdout).get("blockdevices", [])
	except ValueError:
		return []
	disks = []
	for block in blocks:
		if block.get("type") != "disk" or not block.get("size"):
			continue
		connection = (block.get("tran") or "").upper()
		connection = CONNECTIONS.get(connection, connection)
		kind = "Hard disk" if block.get("rota") else DISK_KINDS.get(connection, f"{connection} SSD".strip())
		size = _bytes_text(int(block["size"]))
		device_path = _resolved(SYS / "block" / block["name"] / "device")
		disks.append(_device(f"disk:{block['name']}", "Storage", (block.get("model") or block["name"]).strip(), kind,
			f"{size} {kind}", [("Size", size), ("Kind", kind), ("Connection", connection),
				("Firmware version", (block.get("rev") or "").strip()),
				("Temperature", _temperature(sensors, device_path)), ("Name in the system", "/dev/" + block["name"])]))
	return disks


def _batteries():
	found = []
	for supply in sorted(POWER.iterdir()) if POWER.exists() else []:
		if _read(supply / "type") != "Battery":
			continue
		full, design = (_read(supply / "energy_full") or _read(supply / "charge_full"),
			_read(supply / "energy_full_design") or _read(supply / "charge_full_design"))
		health = f"{int(full) * 100 // int(design)} % of new" if full.isdigit() and design.isdigit() and int(design) else ""
		charge = _read(supply / "capacity")
		name = " ".join(part for part in (_read(supply / "manufacturer"), _read(supply / "model_name")) if part)
		found.append(_device(f"battery:{supply.name}", "Batteries", name or "Battery", "Battery",
			f"{charge} %" if charge else "", [("Charge", f"{charge} %" if charge else ""),
				("State", _read(supply / "status")), ("Health", health), ("Charge cycles", _read(supply / "cycle_count")),
				("Kind", _read(supply / "technology"))]))
	return found


# Firmware ======================================================================


def _fwupd_devices():
	listing = look.run(["fwupdmgr", "get-devices", "--json"])
	start = listing.stdout.find("{")
	try:
		return json.loads(listing.stdout[start:]).get("Devices", []) if start >= 0 else []
	except ValueError:
		return []


def _firmware(devices):
	entries = []
	certificates = []
	for item in devices:
		name = item.get("Name")
		if not name:
			continue
		if item.get("Plugin") in CERTIFICATE_PLUGINS:
			certificates.append((name + (f" ({item['Vendor']})" if item.get("Vendor") not in (None, "Unknown")
				else ""), item.get("Version") or "Present"))
			continue
		updatable = "updatable" in (item.get("Flags") or [])
		entries.append(_device(f"firmware:{item.get('DeviceId', name)}", "Firmware", name, "Firmware",
			"Version " + item["Version"] if item.get("Version") else "", [
				("Maker", item.get("Vendor", "")), ("Version", item.get("Version", "")),
				("Updates", "From the LVFS through fwupd" if updatable else "Not through fwupd"),
			]))
	if certificates:
		entries.append(_device("firmware:secure-boot", "Firmware", "Secure Boot keys", "Firmware",
			look.plural(len(certificates), "key"), certificates))
	return entries


def collect():
	sensors = _sensors()
	firmware = _fwupd_devices()
	cards = drivers.graphics_cards()
	found = (_computer(firmware) + _processor(sensors, firmware) + _memory(sensors) + _pci_parts(sensors, cards)
		+ _displays() + _disks(sensors) + _usb_parts() + _batteries() + _firmware(firmware))
	# One list in group order, the page puts a heading above each group
	return {"devices": sorted(found, key=lambda device: GROUP_ORDER.index(device["group"]))}
