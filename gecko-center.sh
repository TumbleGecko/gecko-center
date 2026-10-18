#!/usr/bin/env bash
# Start Gecko Center, the window by default, or the background check, tray icon or timer setup
#
# Opening the window first installs the packages it needs, writes its launcher and starts the tray, --install does only that

set -uo pipefail

readonly EXIT_SUCCESS=0
readonly EXIT_FAILURE=1

GECKO_CENTER_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
readonly GECKO_CENTER_ROOT

# What the window and tray need, named by capability so zypper picks the package for the installed Python
readonly BOOTSTRAP_PACKAGES=(python3-pyside6 ibm-plex-sans-fonts dejavu-fonts flatpak /usr/bin/notify-send /usr/bin/gio)
# The files and links the window opens, Discover handled them before the TumbleGecko update guard removed it
readonly HANDLED_TYPES=(application/x-rpm application/vnd.flatpak.ref x-scheme-handler/flatpak+https
	x-scheme-handler/appstream)


# Install the window's own packages from the openSUSE repositories when any are missing
bootstrap() {
	local package missing=()
	for package in "${BOOTSTRAP_PACKAGES[@]}"; do
		rpm -q --quiet --whatprovides "${package}" || missing+=("${package}")
	done
	(( ${#missing[@]} == 0 )) && return "${EXIT_SUCCESS}"

	printf 'Gecko Center needs %s first.\n' "${missing[*]}"
	as_root /usr/bin/zypper --non-interactive install "${missing[@]}"
}

# Run as root with what this start offers, an installer's askpass, a terminal's sudo or polkit's own dialog
as_root() {
	if sudo -n true 2>/dev/null; then
		sudo -n "$@"
	elif [[ -n "${SUDO_ASKPASS:-}" ]]; then
		sudo -A "$@"
	elif [[ -t 0 ]]; then
		sudo "$@"
	else
		pkexec "$@"
	fi
}

# The app menu entry, also the handler for package files and install links
# It is written on every start so it follows the folder if it moves
write_launcher() {
	local directory="${XDG_DATA_HOME:-${HOME}/.local/share}/applications" types type
	types="$(printf '%s;' "${HANDLED_TYPES[@]}")"
	mkdir -p "${directory}" || return "${EXIT_FAILURE}"
	cat > "${directory}/gecko-center.desktop" <<ENTRY
[Desktop Entry]
Type=Application
Name=Gecko Center
GenericName=System Center
Comment=Look after the system, its updates, software, snapshots and drivers
Exec="${GECKO_CENTER_ROOT}/gecko-center.sh" %u
Icon=${GECKO_CENTER_ROOT}/gecko-ui/assets/gecko.png
Terminal=false
Categories=System;Settings;PackageManager;
Keywords=update;install;software;flatpak;rpm;zypper;snapshot;driver;repository;help;
MimeType=${types}
ENTRY
	# A generated entry with MimeType would win these types anyway, so the default is written down
	# xdg-mime rejects an Exec path in quotes, so the KDE config tool writes mimeapps.list instead
	for type in "${HANDLED_TYPES[@]}"; do
		kwriteconfig6 --file mimeapps.list --group "Default Applications" --key "${type}" gecko-center.desktop \
			|| return "${EXIT_FAILURE}"
	done
	update-desktop-database "${directory}" 2>/dev/null
	return "${EXIT_SUCCESS}"
}

# The entry under System in KDE System Settings, which opens each file in this folder as an app
# Like the launcher it is written on each start so it follows the folder
write_settings_entry() {
	local directory="${XDG_DATA_HOME:-${HOME}/.local/share}/plasma/systemsettings/externalmodules"
	mkdir -p "${directory}" || return "${EXIT_FAILURE}"
	cat > "${directory}/gecko-center.desktop" <<ENTRY
[Desktop Entry]
Type=Service
X-KDE-ServiceTypes=SystemSettingsExternalApp
X-KDE-System-Settings-Parent-Category=system-administration
Name=Gecko Center
Comment=Updates, software, snapshots and drivers
Exec="${GECKO_CENTER_ROOT}/gecko-center.sh"
Icon=${GECKO_CENTER_ROOT}/gecko-ui/assets/gecko.png
X-KDE-Keywords=update,install,software,flatpak,rpm,zypper,snapshot,driver,repository
ENTRY
	# KDE wants an entry outside the app folders to be executable before it trusts it
	chmod +x "${directory}/gecko-center.desktop"
}

run_python() {
	PYTHONPATH="${GECKO_CENTER_ROOT}/src" exec python3 -m gecko_center "$@"
}

main() {
	case "${1:-}" in
		--check | --tray | --install-tray | --install-timer | --remove-timer | -h | --help)
			run_python "$@"
			;;
	esac
	bootstrap || return "${EXIT_FAILURE}"
	write_launcher || return "${EXIT_FAILURE}"
	write_settings_entry || return "${EXIT_FAILURE}"
	# A session without a user systemd still gets the window, only an installer needs the tray to succeed
	if ! PYTHONPATH="${GECKO_CENTER_ROOT}/src" python3 -m gecko_center --install-tray \
		&& [[ "${1:-}" == --install ]]; then
		return "${EXIT_FAILURE}"
	fi
	[[ "${1:-}" == --install ]] && return "${EXIT_SUCCESS}"
	mkdir -p "${GECKO_CENTER_ROOT}/logs"
	PYTHONPATH="${GECKO_CENTER_ROOT}/src" python3 -m gecko_center "$@" \
		2> >(tee -a "${GECKO_CENTER_ROOT}/logs/window.log" >&2)
}

# One line, so bash has read all of it before running and an edited file cannot break a long session
main "$@"; exit $?
