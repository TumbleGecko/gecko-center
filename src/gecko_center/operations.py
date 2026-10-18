"""Changes to the system, run step by step with a progress fraction and a plain line about what happens now."""

import re

from PySide6.QtCore import QObject, Signal

from . import paths, updates
from .commands import Command, run_as_root

EXIT_SUCCESS = 0
# zypper's exit codes from man zypper, the update finished but wants a reboot, or zypper updated itself first
ZYPPER_EXIT_REBOOT = 102
ZYPPER_EXIT_RUN_AGAIN = 103
ZYPPER_EXIT_SCRIPT_FAILED = 107
COUNTER = re.compile(r"\(\s*(\d+)/(\d+)\)")
PERCENT = re.compile(r"(\d{1,3})%")
ZYPPER_ACTIONS = {"Retrieving": "Downloading", "Installing": "Installing", "Removing": "Removing"}


class Step:
	"""One program run inside a job, as root or as you."""

	def __init__(self, title, arguments, root=False, kind="flatpak"):
		self.title = title
		self.arguments = arguments
		self.root = root
		self.kind = kind


def zypper_step(title, arguments):
	return Step(title, arguments, root=True, kind="zypper")


def system_update_steps(flatpak_installations):
	steps = [zypper_step("Updating the system", updates.UPDATE_ARGUMENTS)]
	for installation in flatpak_installations:
		steps.append(Step(f"Updating {installation} Flatpak apps",
			["flatpak", "update", f"--{installation}", "-y", "--noninteractive"]))
	return steps


def flatpak_update_steps(update):
	"""One Flatpak app or runtime on its own, named with its branch since runtimes keep several side by side."""
	reference = update["id"] + ("//" + update["branch"] if update.get("branch") else "")
	return [Step("Updating " + update["name"],
		["flatpak", "update", f"--{update['installation']}", "-y", "--noninteractive", reference])]


def install_steps(entry):
	kind = entry.get("kind")
	if kind == "file" and entry.get("format") == "rpm":
		# A package file has no repository behind it, the window already asked whether you trust it
		return [zypper_step("Installing " + entry["name"], [paths.ZYPPER, "--non-interactive", "install",
			"--auto-agree-with-licenses", "--allow-unsigned-rpm", entry["path"]])]
	if kind == "file":
		return [Step("Installing " + entry["name"],
			["flatpak", "install", "--user", "-y", "--noninteractive", "--from", entry["path"]])]
	if entry.get("source") == "Flathub":
		script = 'flatpak remote-add --user --if-not-exists "$1" "$2" && ' \
			'flatpak install --user -y --noninteractive "$1" "$3"'
		return [Step("Installing " + entry["name"],
			["/bin/sh", "-c", script, "sh", paths.FLATHUB, paths.FLATHUB_REPOSITORY, entry["package"]])]
	return [zypper_step("Installing " + entry["name"],
		[paths.ZYPPER, "--non-interactive", "install", "--auto-agree-with-licenses", "--", entry["package"]])]


def remove_steps(entry):
	if entry.get("source") == "Flathub":
		installation = entry.get("installation") or "user"
		return [Step("Removing " + entry["name"],
			["flatpak", "uninstall", f"--{installation}", "-y", "--noninteractive", entry["package"]])]
	return [zypper_step("Removing " + entry["name"],
		[paths.ZYPPER, "--non-interactive", "remove", "--", entry["package"]])]


def remove_packages_steps(names):
	"""Removes several packages in one go, such as everything one source gave."""
	packages = names.split()
	return [zypper_step("Removing " + ", ".join(packages), [paths.ZYPPER, "--non-interactive", "remove", "--", *packages])]


def preview_arguments(action, entry):
	"""A zypper dry run of the same change, so the window can say what else comes along before anything happens."""
	targets = [entry["path"]] if entry.get("kind") == "file" else entry.get("packages") or [entry["package"]]
	options = ["--auto-agree-with-licenses", "--allow-unsigned-rpm"] if action == "install" else []
	return [paths.ZYPPER, "--non-interactive", "--no-refresh", "--xmlout", action, "--dry-run", *options, "--", *targets]


class Job(QObject):
	"""Runs steps in order and stops at the first that fails."""

	progress = Signal(float, str)
	line = Signal(str)
	finished = Signal(bool, bool, str)

	def __init__(self, steps, root_access, parent=None):
		super().__init__(parent)
		self._steps = steps
		self._root = root_access
		self._index = -1
		self._step_fraction = 0.0
		self._downloading = True
		self._reboot = False
		self._ran_again = False
		self._last_line = ""

	def start(self):
		self._next()

	def _next(self):
		self._index += 1
		if self._index >= len(self._steps):
			self.progress.emit(1.0, "Finished")
			self.finished.emit(True, self._reboot, "")
			return
		self._run_current()

	def _run_current(self):
		step = self._steps[self._index]
		self._step_fraction = 0.0
		self._downloading = True
		# zypper first refreshes and works out the plan, its own lines take over once packages move
		self._emit_progress("Preparing…" if step.kind == "zypper" else step.title)
		command = run_as_root(self._root, step.arguments, self) if step.root else Command(step.arguments, parent=self)
		command.line.connect(self._read_line)
		command.finished.connect(self._step_finished)

	def _emit_progress(self, text):
		overall = (self._index + self._step_fraction) / len(self._steps)
		self.progress.emit(overall, text)

	def _read_line(self, text):
		self._last_line = text.strip()
		self.line.emit(text)
		step = self._steps[self._index]
		if step.kind == "zypper":
			self._read_zypper_line(text)
			return
		percent = PERCENT.search(text)
		if percent:
			self._step_fraction = min(int(percent.group(1)), 100) / 100
			self._emit_progress(step.title)

	def _read_zypper_line(self, text):
		"""zypper counts packages as (n/total), first while downloading and again while installing."""
		action = next((word for word in ZYPPER_ACTIONS if word + ":" in text), None)
		counter = COUNTER.search(text)
		if action is None or counter is None:
			return
		done, total = int(counter.group(1)), max(int(counter.group(2)), 1)
		self._downloading = action == "Retrieving"
		phase = 0.0 if self._downloading else 0.5
		self._step_fraction = phase + done / total * 0.5
		words = text.split(action + ":", 1)[1].split()
		package = words[0] if words else ""
		self._emit_progress(f"{ZYPPER_ACTIONS[action]} {package}  ({done} of {total})")

	def _step_finished(self, exit_code, output):
		step = self._steps[self._index]
		if step.kind == "zypper" and exit_code == ZYPPER_EXIT_RUN_AGAIN and not self._ran_again:
			# zypper updated itself and asks to be run again to finish the rest
			self._ran_again = True
			self._run_current()
			return
		if step.kind == "zypper" and exit_code == ZYPPER_EXIT_REBOOT:
			self._reboot = True
			exit_code = EXIT_SUCCESS
		if exit_code == ZYPPER_EXIT_SCRIPT_FAILED and step.kind == "zypper":
			self.line.emit("A package's own setup script failed. The rest of the update was installed.")
			exit_code = EXIT_SUCCESS
		if exit_code != EXIT_SUCCESS:
			self.finished.emit(False, self._reboot, self._last_line or output.strip()[-400:])
			return
		self._next()
