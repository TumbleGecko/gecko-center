"""Keep the password sudo accepted and hand it to sudo through askpass, never on a command line"""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtNetwork import QLocalServer

EXIT_SUCCESS = 0
ASKPASS = Path(__file__).resolve().parent / "askpass.py"
SOCKET_VARIABLE = "GECKO_ASKPASS_SOCKET"


class RootAccess(QObject):
	"""Serves the password on a socket only this user can open, for the askpass helper sudo starts"""

	def __init__(self, name, parent=None):
		super().__init__(parent)
		self._password = b""
		self._server = QLocalServer(self)
		self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
		self._server.newConnection.connect(self._hand_out_password)
		self._server.listen(f"{name}-askpass-{os.getpid()}")

	def _hand_out_password(self):
		connection = self._server.nextPendingConnection()
		connection.write(self._password + b"\n")
		connection.flush()
		connection.disconnectFromServer()

	@Slot(result=bool)
	def needsPassword(self):
		return subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False).returncode != EXIT_SUCCESS

	@Slot(str, result=bool)
	def setPassword(self, password):
		"""Keep the password only when sudo accepts it"""
		check = subprocess.run(["sudo", "-k", "-S", "-p", "", "-v"], input=(password + "\n").encode(),
			capture_output=True, check=False)
		if check.returncode != EXIT_SUCCESS:
			return False
		self._password = password.encode()
		return True

	def add_to(self, environment):
		"""Let sudo started with this QProcessEnvironment ask this app for the password"""
		environment.insert("SUDO_ASKPASS", str(ASKPASS))
		environment.insert(SOCKET_VARIABLE, self._server.fullServerName())
		return environment
