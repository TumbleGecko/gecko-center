"""Read only looks at the system, programs run with English output and their answers in plain words."""

import os
import subprocess


EXIT_TIMED_OUT = 124


def run(arguments, seconds=None):
	"""Run a program with English output, a missing program counts as one that printed nothing.

	With seconds given, a program still running after that long is stopped and counts as one that printed nothing.
	"""
	environment = dict(os.environ, LC_ALL="C.UTF-8")
	# The window's own Qt platform must not leak into the Qt programs it asks, such as plasmashell
	environment.pop("QT_QPA_PLATFORM", None)
	try:
		return subprocess.run(arguments, capture_output=True, text=True, check=False, env=environment, timeout=seconds)
	except FileNotFoundError:
		return subprocess.CompletedProcess(arguments, 127, "", "")
	except subprocess.TimeoutExpired:
		return subprocess.CompletedProcess(arguments, EXIT_TIMED_OUT, "", "")


def plural(count, word):
	return f"{count} {word}{'' if count == 1 else 's'}"


def folder_bytes(path):
	"""The size of a folder, zero when it is missing or cannot be read."""
	found = run(["du", "--summarize", "--bytes", str(path)])
	words = found.stdout.split()
	return int(words[0]) if words and words[0].isdigit() else 0
