"""The temperature sensors Linux publishes in /sys/class/hwmon, by the device each one measures."""

from pathlib import Path

HWMON = Path("/sys/class/hwmon")
# The drivers that measure the processor itself, AMD's two and Intel's
PROCESSOR_SENSORS = ("k10temp", "zenpower", "coretemp")


def _read(path):
	try:
		return Path(path).read_text(encoding="utf-8").strip()
	except OSError:
		return ""


def read_sensors():
	"""Each sensor's device path, driver name and degrees, read as you since the files are readable by everyone."""
	found = []
	for sensor in sorted(HWMON.glob("hwmon*")):
		reading = _read(sensor / "temp1_input")
		if not reading.lstrip("-").isdigit():
			continue
		try:
			device = str((sensor / "device").resolve(strict=True))
		except OSError:
			device = ""
		found.append((device, _read(sensor / "name"), int(reading) / 1000))
	return found


def device_degrees(sensors, device_path):
	"""The first sensor on the device or on a part of it, None when it has none.

	A chip reached over the device's I2C bus, such as a memory module behind the SMBus, is a part of its own.
	"""
	for path, _name, degrees in sensors:
		if device_path and path.startswith(device_path) and "/i2c-" not in path[len(device_path):]:
			return degrees
	return None


def processor_degrees(sensors):
	return next((degrees for _path, name, degrees in sensors if name in PROCESSOR_SENSORS), None)
