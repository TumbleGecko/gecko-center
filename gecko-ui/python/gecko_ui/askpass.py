#!/usr/bin/python3 -I
"""Hand sudo the password a gecko app keeps, sudo runs this through SUDO_ASKPASS.

The app serves the password on a local socket only this user can open.
"""

import os
import socket
import sys

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
SOCKET_VARIABLE = "GECKO_ASKPASS_SOCKET"


def main():
	address = os.environ.get(SOCKET_VARIABLE)
	if not address:
		return EXIT_FAILURE
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
		connection.connect(address)
		password = b""
		while chunk := connection.recv(4096):
			password += chunk
	sys.stdout.buffer.write(password)
	return EXIT_SUCCESS


if __name__ == "__main__":
	sys.exit(main())
