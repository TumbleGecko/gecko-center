"""How busy the machine is right now, each processor core, memory, the graphics card and each running app.

NVIDIA cards are read through nvidia-smi, and a pmon that keeps running gives each app's share of the card.
pmon averages since its previous sample, so a single run has nothing to compare against and shows no usage.
AMD cards are read from the kernel, the card from sysfs and each app from the DRM counters in /proc/PID/fdinfo.
https://docs.kernel.org/gpu/drm-usage-stats.html
Apps are told apart by their systemd unit, https://systemd.io/DESKTOP_ENVIRONMENTS/
"""

import os
import re
import time
from pathlib import Path

from . import look

PROC = Path("/proc")
DRM = Path("/sys/class/drm")
BLOCK = Path("/sys/block")
NETWORK = Path("/sys/class/net")
# The kernel counts disk transfers in 512 byte sectors whatever the disk's own sector size
SECTOR_BYTES = 512
# How much of the last 10 seconds apps spent waiting for each resource, https://docs.kernel.org/accounting/psi.html
PRESSURE_RESOURCES = ("cpu", "memory", "io")
CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
PAGE_BYTES = os.sysconf("SC_PAGE_SIZE")
MEBIBYTE = 1024 ** 2
NVIDIA_FIELDS = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.gr"
# An app unit is app[-<launcher>]-<ApplicationID>[@<RANDOM>].service or app[-<launcher>]-<ApplicationID>-<RANDOM>.scope
APP_SERVICE = re.compile(r"^app-(.+?)(?:@[^.]*)?\.service$")
APP_SCOPE = re.compile(r"^app-(.+)-[^-]+\.scope$")
# The busy time an AMD client's engines report, and the card memory it holds in bytes, KiB or MiB
DRM_ENGINE = re.compile(r"^drm-engine-(\w+):\s*(\d+) ns", re.MULTILINE)
DRM_CAPACITY = re.compile(r"^drm-engine-capacity-(\w+):\s*(\d+)", re.MULTILINE)
DRM_VRAM = re.compile(r"^drm-(?:resident|memory)-vram:\s*(\d+)\s*(KiB|MiB)?", re.MULTILINE)
DRM_UNITS = {None: 1, "KiB": 1024, "MiB": MEBIBYTE}
SERVICE_UNIT = re.compile(r"^(.+)\.(?:scope|service)$")
SYSTEM = "System services"


def _read(path):
	try:
		return Path(path).read_text()
	except OSError:
		return ""


def _number(text):
	try:
		return float(text)
	except ValueError:
		return None


# Graphics cards ===============================================================


def _nvidia_cards():
	found = look.run(["nvidia-smi", f"--query-gpu={NVIDIA_FIELDS}", "--format=csv,noheader,nounits"])
	cards = []
	for line in found.stdout.splitlines():
		values = [value.strip() for value in line.split(",")]
		if len(values) < 8:
			continue
		name, usage, used, total, temperature, power, power_limit, clock = values[:8]
		cards.append({"name": name, "usage": _number(usage), "memoryUsed": (_number(used) or 0) * MEBIBYTE,
			"memoryTotal": (_number(total) or 0) * MEBIBYTE, "temperature": _number(temperature),
			"power": _number(power), "powerLimit": _number(power_limit), "clock": _number(clock)})
	return cards


def _amd_cards():
	"""amdgpu publishes its load and memory in sysfs and its temperature and power through hwmon."""
	cards = []
	for device in sorted(DRM.glob("card[0-9]*/device")):
		busy = _read(device / "gpu_busy_percent").strip()
		if not busy:
			continue
		hwmon = next(iter(sorted((device / "hwmon").glob("hwmon*"))), None)
		temperature = _number(_read(hwmon / "temp1_input").strip()) if hwmon else None
		power = _number(_read(hwmon / "power1_average").strip() or _read(hwmon / "power1_input").strip()) \
			if hwmon else None
		power_limit = _number(_read(hwmon / "power1_cap").strip()) if hwmon else None
		cards.append({"name": _amd_name(device), "usage": _number(busy),
			"memoryUsed": _number(_read(device / "mem_info_vram_used").strip()) or 0,
			"memoryTotal": _number(_read(device / "mem_info_vram_total").strip()) or 0,
			"temperature": temperature / 1000 if temperature is not None else None,
			"power": power / 1_000_000 if power is not None else None,
			"powerLimit": power_limit / 1_000_000 if power_limit is not None else None, "clock": None})
	return cards


def _amd_name(device):
	slot = Path(os.path.realpath(device)).name
	found = look.run(["lspci", "-s", slot, "-mm"]).stdout.split('"')
	return found[5] if len(found) > 5 else "AMD graphics"


def graphics_cards():
	return _nvidia_cards() + _amd_cards()


# Apps =========================================================================


class _DesktopNames:
	"""The name an app's menu entry gives it, looked up once per desktop id."""

	def __init__(self):
		data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
		data_dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
		self._folders = [Path(folder) / "applications" for folder in [data_home, *data_dirs]]
		self._names = {}
		self._descriptions = {}

	def description(self, unit):
		"""A background service's own description, such as KDE Window Manager, all of them read in one call."""
		if unit not in self._descriptions:
			listing = look.run(["systemctl", "--user", "list-units", "--all", "--plain", "--no-legend", "--no-pager"])
			for line in listing.stdout.splitlines():
				fields = line.split(None, 4)
				if len(fields) == 5:
					self._descriptions[fields[0]] = fields[4].strip()
			self._descriptions.setdefault(unit, "")
		return self._descriptions[unit]

	def name(self, desktop_id):
		if desktop_id not in self._names:
			self._names[desktop_id] = self._look_up(desktop_id)
		return self._names[desktop_id]

	def _look_up(self, desktop_id):
		for folder in self._folders:
			found = re.search(r"^Name=(.+)$", _read(folder / f"{desktop_id}.desktop"), re.MULTILINE)
			if found:
				return found.group(1).strip()
		return ""


def _unit(pid):
	"""The last part of the process's cgroup path, the unit systemd started it in."""
	return _read(PROC / str(pid) / "cgroup").strip().rsplit("/", 1)[-1]


def _unescape(unit):
	"""systemd writes a dash inside a name as \\x2d, and any other odd character the same way."""
	return re.sub(r"\\x([0-9a-f]{2})", lambda found: chr(int(found.group(1), 16)), unit)


def _group(unit, owner, names):
	"""Each of your units is one row, an app or a background service, everything of other users is the system."""
	if owner != os.getuid():
		return SYSTEM, SYSTEM, "system"
	app = APP_SERVICE.match(unit) or APP_SCOPE.match(unit)
	if app:
		return unit, _app_name(_unescape(app.group(1)), names), "app"
	service = SERVICE_UNIT.match(unit)
	name = _unescape(service.group(1)) if service else unit
	return unit, names.name(name) or names.description(unit) or name, "service"


def _app_name(launcher_and_id, names):
	"""The launcher part is optional and has no dots, so the id is tried whole and then without its first part."""
	launcher, _, rest = launcher_and_id.partition("-")
	candidates = [launcher_and_id] + ([rest] if rest and "." not in launcher else [])
	for desktop_id in candidates:
		name = names.name(desktop_id)
		if name:
			return name
	return candidates[-1].rsplit(".", 1)[-1]


def end_arguments(unit, force):
	"""Stopping the unit asks every process of the app to close, a forced end kills them at once."""
	if force:
		return ["systemctl", "--user", "kill", "--signal=SIGKILL", "--", unit]
	return ["systemctl", "--user", "stop", "--", unit]


def _process_times(pid):
	"""CPU ticks used so far and memory pages held, from /proc/PID/stat and statm."""
	stat = _read(PROC / str(pid) / "stat")
	fields = stat.rsplit(")", 1)[-1].split()
	if len(fields) < 13:
		return None
	statm = _read(PROC / str(pid) / "statm").split()
	resident = int(statm[1]) * PAGE_BYTES if len(statm) > 1 else 0
	return int(fields[11]) + int(fields[12]), resident


PMON_ARGUMENTS = ["nvidia-smi", "pmon", "-s", "um", "-d", "1"]


def pmon_line(text):
	"""One process line of pmon as its pid, its share of the card and the card memory it holds, None for headers."""
	values = text.split()
	if text.startswith("#") or len(values) < 10 or not values[1].isdigit():
		return None
	return int(values[1]), _number(values[3]) or 0, (_number(values[9]) or 0) * MEBIBYTE


def _amd_clients(pid):
	"""Each DRM client this process holds open, by device and client id, with its engine times and card memory.

	A client opened once and shared with a child shows up in both, the id keeps it from counting twice.
	"""
	clients = {}
	for fdinfo in (PROC / str(pid) / "fdinfo").glob("*"):
		text = _read(fdinfo)
		client = re.search(r"^drm-client-id:\s*(\d+)", text, re.MULTILINE)
		if not client:
			continue
		device = re.search(r"^drm-pdev:\s*(\S+)", text, re.MULTILINE)
		capacity = {engine: int(count) for engine, count in DRM_CAPACITY.findall(text)}
		engines = {engine: int(busy) / capacity.get(engine, 1) for engine, busy in DRM_ENGINE.findall(text)}
		memory = sum(int(amount) * DRM_UNITS[unit or None] for amount, unit in DRM_VRAM.findall(text))
		clients[(device.group(1) if device else "", client.group(1))] = (engines, memory)
	return clients


def _pressure():
	"""The share of the last 10 seconds in which some app had to wait, per resource."""
	waiting = {}
	for resource in PRESSURE_RESOURCES:
		found = re.search(r"^some avg10=([\d.]+)", _read(PROC / "pressure" / resource), re.MULTILINE)
		waiting[resource] = float(found.group(1)) if found else 0.0
	return waiting


def _disk_bytes():
	"""Bytes read and written so far by the real disks, partitions and loop devices left out."""
	disks = {path.name for path in BLOCK.iterdir() if (path / "device").exists()}
	read = written = 0
	for line in _read(PROC / "diskstats").splitlines():
		fields = line.split()
		if len(fields) > 9 and fields[2] in disks:
			read += int(fields[5]) * SECTOR_BYTES
			written += int(fields[9]) * SECTOR_BYTES
	return read, written


def _network_bytes():
	"""Bytes received and sent so far by the real network cards, virtual ones would count the same traffic twice."""
	cards = {path.name for path in NETWORK.iterdir() if (path / "device").exists()}
	received = sent = 0
	for line in _read(PROC / "net" / "dev").splitlines()[2:]:
		name, _, counters = line.partition(":")
		fields = counters.split()
		if name.strip() in cards and len(fields) > 8:
			received += int(fields[0])
			sent += int(fields[8])
	return received, sent


class Sampler:
	"""Keeps the last counts, since usage is the difference between two looks."""

	def __init__(self):
		self._names = _DesktopNames()
		self._last_cpu = None
		self._last_processes = {}
		self._last_amd = {}
		# The newest pmon line for each process, filled by the running pmon while the page shows
		self.nvidia_usage = {}
		self._last_time = None
		self._last_transfers = None

	def _cores(self):
		"""Busy share of each core and of all of them since the last look, from /proc/stat."""
		counts = {}
		for line in _read(PROC / "stat").splitlines():
			if line.startswith("cpu"):
				name, *values = line.split()
				numbers = [int(value) for value in values]
				# Only user to steal count, guest time is already part of user, idle and iowait are the time it rested
				counts[name] = (sum(numbers[:8]), numbers[3] + numbers[4])
		last, self._last_cpu = self._last_cpu, counts
		if last is None:
			return 0.0, [0.0] * (len(counts) - 1)
		shares = {}
		for name, (total, idle) in counts.items():
			total_change = total - last.get(name, (0, 0))[0]
			idle_change = idle - last.get(name, (0, 0))[1]
			# iowait can go down between two looks, so the share is kept within 0 and 100
			share = 100 * (1 - idle_change / total_change) if total_change > 0 else 0.0
			shares[name] = max(0.0, min(100.0, share))
		cores = [shares[name] for name in counts if name != "cpu"]
		return shares["cpu"], cores

	def _amd_usage(self, clients, elapsed):
		"""The busiest engine sets the client's share, a counter that steps back keeps its larger value."""
		usage = 0.0
		for key, (engines, _memory) in clients.items():
			last = self._last_amd.get(key, {})
			for engine, busy in engines.items():
				engines[engine] = max(busy, last.get(engine, 0))
				if elapsed and engine in last:
					usage = max(usage, 100 * (engines[engine] - last[engine]) / 1e9 / elapsed)
		return usage

	def _apps(self, elapsed, core_count, has_amd):
		# A copy, the window's thread adds pmon lines while this one reads
		nvidia = dict(self.nvidia_usage)
		groups = {}
		processes = {}
		amd = {}
		for entry in PROC.iterdir():
			if not entry.name.isdigit():
				continue
			pid = int(entry.name)
			times = _process_times(pid)
			if times is None:
				continue
			ticks, resident = times
			try:
				owner = entry.stat().st_uid
			except OSError:
				continue
			processes[pid] = ticks
			key, name, kind = _group(_unit(pid), owner, self._names)
			group = groups.setdefault(key, {"unit": key, "name": name, "kind": kind, "cpu": 0.0, "gpu": 0.0,
				"memory": 0, "gpuMemory": 0})
			if elapsed and pid in self._last_processes:
				used = (ticks - self._last_processes[pid]) / CLOCK_TICKS
				group["cpu"] += 100 * used / elapsed / core_count
			group["memory"] += resident
			if pid in nvidia:
				group["gpu"] += nvidia[pid][0]
				group["gpuMemory"] += nvidia[pid][1]
			elif has_amd and owner == os.getuid():
				clients = {key: value for key, value in _amd_clients(pid).items() if key not in amd}
				group["gpu"] += self._amd_usage(clients, elapsed)
				group["gpuMemory"] += sum(memory for _engines, memory in clients.values())
				amd.update({key: engines for key, (engines, _memory) in clients.items()})
		self._last_processes = processes
		self._last_amd = amd
		# Every app goes to the page, which sorts them the way its list is set to
		return list(groups.values())

	def _rates(self, elapsed):
		"""Disk and network speed in bytes a second since the last look."""
		transfers = (*_disk_bytes(), *_network_bytes())
		last, self._last_transfers = self._last_transfers, transfers
		if not last or not elapsed:
			return [0.0] * len(transfers)
		return [max(0.0, (now - before) / elapsed) for now, before in zip(transfers, last)]

	def sample(self):
		now = time.monotonic()
		elapsed = now - self._last_time if self._last_time else 0
		self._last_time = now
		overall, cores = self._cores()
		memory = {}
		for line in _read(PROC / "meminfo").splitlines():
			key, _, value = line.partition(":")
			memory[key] = int(value.split()[0]) * 1024 if value.split() else 0
		nvidia_cards = _nvidia_cards()
		amd_cards = _amd_cards()
		disk_read, disk_write, received, sent = self._rates(elapsed)
		return {
			"cpu": overall, "cores": cores,
			"memoryUsed": memory.get("MemTotal", 0) - memory.get("MemAvailable", 0),
			"memoryTotal": memory.get("MemTotal", 0),
			"swapUsed": memory.get("SwapTotal", 0) - memory.get("SwapFree", 0),
			"diskRead": disk_read, "diskWrite": disk_write, "received": received, "sent": sent,
			"waiting": _pressure(),
			"gpus": nvidia_cards + amd_cards,
			"apps": self._apps(elapsed, max(len(cores), 1), bool(amd_cards)),
		}
