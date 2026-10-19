"""How much memory the computer has, its modules, and the one way every page writes a memory size.

Memory is sold in powers of two, so 32 GB here is 32 × 1024³ bytes, which is what the modules themselves report.
"""

import math
import re
from pathlib import Path

MEMINFO = Path("/proc/meminfo")
I2C_DRIVERS = Path("/sys/bus/i2c/drivers")
GIBIBYTE = 1024 ** 3
MEBIBYTE = 1024 ** 2
KIBIBYTE = 1024
# Each memory module's SPD chip, by its driver, with where the maker code and part number sit, DDR5 then DDR4
SPD_LAYOUTS = {"spd5118": (512, 521, 551), "ee1004": (320, 329, 349)}
# DDR5 SPD bytes for the module's size, from JEDEC JESD400-5, a die's density in Gb by its code
DDR5_DENSITY = {1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 32, 7: 48, 8: 64}
DDR5_DIES = {0: 1, 2: 2, 3: 4, 4: 8, 5: 16}
# JEDEC JEP106 maker codes as SPD stores them, the bank byte first with its parity bit
MEMORY_MAKERS = {"80ce": "Samsung", "80ad": "SK hynix", "802c": "Micron", "0198": "Kingston", "029e": "Corsair",
	"04cd": "G.Skill", "04cb": "ADATA", "04ef": "TeamGroup", "859b": "Crucial"}
# Memory is sold in steps of this many GB, so what can be used rounds up to the next one
INSTALLED_STEP = 2


def size_text(count):
	"""A memory size the way memory is sold, 9.7 GB below ten and whole GB above, 512 MB below one."""
	if count >= 10 * GIBIBYTE:
		return f"{round(count / GIBIBYTE)} GB"
	if count >= GIBIBYTE:
		return f"{count / GIBIBYTE:.1f} GB".replace(".0 ", " ")
	return f"{round(count / MEBIBYTE)} MB"


def usable_bytes():
	"""What Linux can use, a little below what is installed since the firmware keeps a part for itself."""
	try:
		found = re.search(r"MemTotal:\s+(\d+) kB", MEMINFO.read_text(encoding="utf-8"))
	except OSError:
		return 0
	return int(found.group(1)) * KIBIBYTE if found else 0


def _ddr5_bytes(data):
	"""The module's size from its SPD, channels times dies per channel times what each die holds."""
	density = DDR5_DENSITY.get(data[4] & 0x1F)
	dies = DDR5_DIES.get(data[4] >> 5)
	if not density or not dies:
		return 0
	width = 4 << ((data[6] >> 5) & 0x7)
	ranks = ((data[234] >> 3) & 0x7) + 1
	channels = ((data[235] >> 5) & 0x3) + 1
	bus = 8 << (data[235] & 0x7)
	return channels * bus // width * dies * density * ranks * GIBIBYTE // 8


def modules():
	"""Each module that shows its SPD chip, readable by everyone, with its chip's sysfs path for its sensor."""
	found = []
	for driver, (maker_at, part_at, part_end) in SPD_LAYOUTS.items():
		for chip in sorted((I2C_DRIVERS / driver).glob("*-*")):
			try:
				data = (chip / "eeprom").read_bytes()
			except OSError:
				continue
			kind = "DDR5" if driver == "spd5118" else "DDR4"
			found.append({"chip": chip, "part": data[part_at:part_end].decode("ascii", errors="ignore").strip(),
				"maker": MEMORY_MAKERS.get(data[maker_at:maker_at + 2].hex(), ""), "kind": kind,
				# Only the DDR5 layout is read for a size, DDR4 modules show without one
				"bytes": _ddr5_bytes(data) if kind == "DDR5" else 0})
	return found


def sold_bytes(usable):
	"""The size memory is sold as, from what can be used, which is a little less once the firmware takes its part."""
	step = INSTALLED_STEP * GIBIBYTE
	return math.ceil(usable / step) * step


def installed_bytes(found=None):
	"""What the modules hold together, or what Linux can use rounded up when a module does not say."""
	found = modules() if found is None else found
	if found and all(module["bytes"] for module in found):
		return sum(module["bytes"] for module in found)
	return sold_bytes(usable_bytes())
