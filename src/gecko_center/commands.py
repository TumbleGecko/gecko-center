"""Run programs without blocking the window, and run them as root through sudo with the window's password."""

import re

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

EXIT_SUCCESS = 0
LINE_END = re.compile(rb"\r?\n")


def plain_environment():
	"""The session's environment with English output, so the text the app reads is the same everywhere."""
	environment = QProcessEnvironment.systemEnvironment()
	# The window's own Qt platform must not leak into the programs it starts
	environment.remove("QT_QPA_PLATFORM")
	environment.insert("LC_ALL", "C.UTF-8")
	return environment


class Command(QObject):
	"""One program run, its output passed on line by line and all of it at the end."""

	line = Signal(str)
	finished = Signal(int, str)

	def __init__(self, arguments, environment=None, parent=None, keep_output=True):
		super().__init__(parent)
		self._buffer = b""
		self._output = []
		# A program that keeps running, such as a monitor, only passes its lines on
		self._keep_output = keep_output
		self._process = QProcess(self)
		self._process.setProcessEnvironment(environment or plain_environment())
		self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
		self._process.readyReadStandardOutput.connect(self._read)
		self._process.finished.connect(self._finish)
		self._process.errorOccurred.connect(self._fail_to_start)
		self._process.start(arguments[0], arguments[1:])

	def _read(self):
		self._buffer += bytes(self._process.readAllStandardOutput())
		*lines, self._buffer = LINE_END.split(self._buffer)
		for raw in lines:
			# A progress bar redraws its line after a carriage return, only the last drawing stays, as in a terminal
			text = raw.rsplit(b"\r", 1)[-1].decode(errors="replace")
			if self._keep_output:
				self._output.append(text)
			if text.strip():
				self.line.emit(text)

	def _finish(self, exit_code):
		self._buffer += b"\n"
		self._read()
		self.finished.emit(exit_code, "\n".join(self._output))
		self.deleteLater()

	def stop(self):
		self._process.kill()

	def _fail_to_start(self, error):
		if error == QProcess.ProcessError.FailedToStart:
			self.finished.emit(127, f"Could not start {self._process.program()}")
			self.deleteLater()


def run_as_root(root_access, arguments, parent=None):
	"""Run through sudo, which asks the window for the password through the shared askpass helper."""
	return Command(["sudo", "-A", *arguments], root_access.add_to(plain_environment()), parent)
