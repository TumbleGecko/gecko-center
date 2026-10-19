"""What was plugged in and out and when, read from the kernel's own messages in the system journal.

The kernel writes a line when a USB device arrives, with its product and maker after it, and one when it leaves.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from . import journal, look

# How far back the history reaches, older plugging rarely matters
SINCE = "-90d"
PATTERN = "New USB device found|USB disconnect|: Product: |: Manufacturer: "
# Every start lists what is already connected in its first moments, which is not a change
START_SECONDS = 60
# An unplug and plug of the same port this close together is one reconnect, such as a device restarting
RECONNECT_SECONDS = 3
LINE = re.compile(r"^usb (\S+): (.*)$")
MICROSECONDS = 1_000_000
USB_DEVICES = Path("/sys/bus/usb/devices")
USB_HUB_CLASS = "09"


def arguments():
	return ["journalctl", "_TRANSPORT=kernel", "--since", SINCE, "--grep", PATTERN, "--output", "json", "--no-pager"]


def _event(port, when, action, boot):
	return {"port": port, "when": when, "action": action, "boot": boot, "name": "", "maker": ""}


def events_from_json(text):
	"""Each plug, unplug and reconnect, newest first, named by the product the device gave when it arrived."""
	events = []
	arrivals = {}
	names = {}
	for line in (text or "").splitlines():
		try:
			entry = json.loads(line)
		except ValueError:
			continue
		found = LINE.match(entry.get("MESSAGE") or "")
		if not found:
			continue
		port, words = found.groups()
		boot = entry.get("_BOOT_ID", "")
		when = int(entry.get("__REALTIME_TIMESTAMP", "0"))
		since_start = int(entry.get("__MONOTONIC_TIMESTAMP", "0")) / MICROSECONDS
		key = (boot, port)
		if words.startswith("Product: "):
			names[key] = dict(names.get(key, {}), name=words[len("Product: "):].strip())
		elif words.startswith("Manufacturer: "):
			names[key] = dict(names.get(key, {}), maker=words[len("Manufacturer: "):].strip())
		elif words.startswith("New USB device found"):
			names[key] = {}
			last = events[-1] if events else None
			if last and last["action"] == "Unplugged" and last["port"] == port and last["boot"] == boot \
					and when - last["when"] <= RECONNECT_SECONDS * MICROSECONDS:
				last["action"] = "Reconnected"
				arrivals[key] = last
			elif since_start > START_SECONDS:
				events.append(_event(port, when, "Plugged in", boot))
				arrivals[key] = events[-1]
		elif words.startswith("USB disconnect"):
			events.append(dict(_event(port, when, "Unplugged", boot), **names.get(key, {})))
		# A device names itself right after it arrives, so its arrival takes the name as it comes
		if key in arrivals and key in names:
			arrivals[key].update(names[key])
	hubs = _hub_names()
	return [_finished(event) for event in reversed(events) if event.get("name") and event["name"] not in hubs]


def _hub_names():
	"""Hubs are wiring rather than things people plug in, many do not call themselves hubs, so their class tells."""
	names = set()
	for device in USB_DEVICES.glob("*"):
		try:
			if (device / "bDeviceClass").read_text().strip() == USB_HUB_CLASS:
				names.add((device / "product").read_text().strip())
		except OSError:
			continue
	return names


def _finished(event):
	moment = datetime.fromtimestamp(event["when"] / MICROSECONDS)
	return {"name": event["name"], "maker": event.get("maker", ""), "action": event["action"], "port": event["port"],
		"day": moment.strftime("%Y-%m-%d"), "time": moment.strftime("%H:%M"), "when": moment.isoformat(timespec="seconds")}


def collect():
	"""Read as you, which shows the kernel's lines once you may read the system journal."""
	if not journal.reads_system_journal():
		return {"readable": False, "events": []}
	return {"readable": True, "events": events_from_json(look.run(arguments()).stdout)}
