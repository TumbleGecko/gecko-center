// The graphics cards and the driver each one uses, with the NVIDIA driver to install, and firmware updates
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.drivers || null

	// Each graphics card, then each device with newer firmware, or one line saying firmware is up to date
	readonly property var rows: {
		if (!report)
			return []
		const found = report.cards.map(card => ({
			status: card.wantsNvidia ? "warning" : "good", label: card.maker, heading: card.name,
			details: (card.about || card.driver) + (card.version ? "\nDriver version " + card.version : "")
				+ (card.wantsNvidia
				? "\nNVIDIA's own driver makes it much faster, for GeForce 16, RTX 20 and newer." : ""),
			actionText: card.wantsNvidia ? "Install the NVIDIA driver" : "", action: "nvidia-driver"
		}))
		const firmware = report.firmware
		firmware.devices.forEach(device => found.push({
			status: device.security ? "warning" : "note",
			label: "Firmware  ·  " + device.vendor + (device.security ? "  ·  Security fix" : ""),
			heading: device.name,
			details: device.about + "\nVersion " + device.current + " to " + device.newest
				+ (device.restart ? ", after a restart" : ""),
			actionText: "Update", action: "firmware-update", device: device
		}))
		if (firmware.devices.length === 0)
			found.push({ status: firmware.known ? "good" : "note", label: "Firmware",
				heading: firmware.known ? "Firmware is up to date." : firmware.problem, details: "", actionText: "" })
		return found
	}

	title: "Drivers"
	guideTopic: "drivers"
	subtitle: "Graphics and firmware."
	busy: center.reading.includes("drivers")
	empty: !report

	Component.onCompleted: center.read("drivers")

	CardList {
		id: list
		anchors.fill: parent
		model: page.rows

		delegate: StatusCard {
			required property var modelData
			width: list.cardWidth
			status: modelData.status
			label: modelData.label
			heading: modelData.heading
			details: modelData.details
			actionText: modelData.actionText
			actionPrimary: true
			onActed: {
				if (modelData.action === "nvidia-driver")
					confirm.open()
				else
					window.runSystem("drivers", "firmware-update", modelData.device.id,
						"Updating " + modelData.device.name, "Update", modelData.device.restart)
			}
		}
	}

	QuestionDialog {
		id: confirm

		question: "Install the NVIDIA driver?"
		explanation: "It adds NVIDIA's software source and installs its newest driver from there. "
			+ "The driver takes over after a restart. "
			+ "Cards older than the GeForce 16 series need an older driver this cannot install."
		confirmText: "Install"
		onConfirmed: window.runSystem("drivers", "nvidia-driver", "", "Installing the NVIDIA driver", "Install", true)
	}
}
