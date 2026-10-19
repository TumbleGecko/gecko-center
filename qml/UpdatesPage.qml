// What can be updated, and the one button that updates the system the way Tumbleweed needs
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var lastCheck: bridge.updates
	readonly property var system: lastCheck.system
	readonly property var flatpaks: lastCheck.flatpak || []
	readonly property bool ownJob: window.jobOwner === "updates"
	readonly property bool running: ownJob && bridge.busy
	// A job that went well gives the page back to the list, only a failure or a restart has more to say
	readonly property bool finished: ownJob && window.jobResult !== null && !bridge.busy
		&& (!window.jobResult.succeeded || window.jobResult.reboot)
	readonly property bool hasProblem: system !== null && system !== undefined && system.problem !== ""
	readonly property string view: {
		if (running)
			return "running"
		if (finished)
			return "finished"
		if (bridge.checking)
			return "checking"
		if (!lastCheck.checked)
			return "never"
		if (hasProblem)
			return "problem"
		return window.pendingCount > 0 ? "pending" : "current"
	}

	// Removals come first, they are the part of an update to read first
	readonly property var rows: {
		const sections = [
			["remove", "Removed", "These packages leave the system. A newer package usually takes their place, "
				+ "or nothing needs them any more."],
			["install", "New", "These packages are added because updated packages now need them."],
			["upgrade", "Updated", "These packages get a newer version."],
			["downgrade", "Downgraded", "These packages go back to an older version, "
				+ "usually because their source now offers that one."],
			["change-vendor", "Changing vendor", "These packages switch to the build from another software source."],
			["change-arch", "Changing architecture", "These packages switch to a build for another processor type."]
		]
		// Reading the count makes the names follow the app catalog once it has loaded
		apps.count
		const result = []
		// Flatpak comes first, each one can be updated on its own
		if (flatpaks.length > 0) {
			result.push({ header: true, name: "Flatpak  ·  " + flatpaks.length, warning: false,
				help: "Apps and the runtimes they use from Flathub. Each one can be updated on its own." })
			flatpaks.forEach(item => result.push({ header: false, name: item.name, packageName: "", flatpak: item,
				source: "Flathub", appKey: apps.findKey("Flathub", item.id),
				detail: (item.version ? item.version + "  ·  " : "") + (item.installation === "user" ? "for you"
					: "for everyone") }))
		}
		const found = system && system.sections ? system.sections : {}
		sections.forEach(section => {
			const items = found[section[0]] || []
			if (items.length === 0)
				return
			result.push({ header: true, name: section[1] + "  ·  " + items.length, warning: section[0] === "remove",
				help: section[2] })
			items.forEach(item => {
				const key = apps.findKey("openSUSE", item.name)
				// A removed package has no update to read, what needs it says more
				result.push({ header: false, name: friendlyName(item, key), packageName: item.name,
					source: "openSUSE", appKey: key, startTab: section[0] === "remove" ? "Technical" : "Update",
					oldVersion: item.oldVersion, version: item.version })
			})
		})
		return result
	}

	// The app's own name when the catalog knows the package, else what the package says it is
	function friendlyName(item, key) {
		if (key)
			return apps.entry(key, "openSUSE").name
		return (item.summary || item.name).replace(/\.$/, "")
	}

	// Flatpak is looked at every time the page shows, the system list comes from the last refresh of the package lists
	readonly property string systemChecked: system && system.checked ? system.checked : lastCheck.checked || ""
	readonly property bool systemStale: !systemChecked || Date.now() - new Date(systemChecked) > 24 * 3600 * 1000

	function age(iso) {
		const minutes = Math.floor((Date.now() - new Date(iso)) / 60000)
		if (minutes < 2)
			return "just now"
		if (minutes < 90)
			return minutes + " minutes ago"
		const hours = Math.round(minutes / 60)
		if (hours < 36)
			return hours + " hours ago"
		return Math.round(hours / 24) + " days ago"
	}

	function checkedText() {
		if (!systemChecked)
			return "Not checked yet."
		return "System packages checked " + age(systemChecked) + "."
	}

	function look() {
		window.withPassword(bridge.checkNeedsPassword(),
			"Looking for updates refreshes the package lists as root, which needs your password.",
			"Look for updates", bridge.checkUpdates)
	}

	function updateFlatpak(item) {
		window.startJob("updates", "Updating " + item.name)
		bridge.updateFlatpak(item)
	}

	function updateEverything() {
		const needsRoot = system && system.count > 0
		window.withPassword(needsRoot && bridge.needsPassword(), "Updating the system needs your password.",
			"Update now", () => {
				window.startJob("updates", "Updating everything")
				bridge.updateEverything()
			})
	}

	title: "Updates"
	guideTopic: "updates"
	busy: bridge.checking || page.running
	// While the update runs, only the update is on the page
	subtitle: view === "running" ? "" : checkedText()

	// The stored look may be days old, so the page always looks at Flatpak and, past a day, at the system too
	function refresh() {
		if (bridge.refreshUnitInstalled && systemStale)
			bridge.checkUpdates()
		else
			bridge.refreshFlatpakUpdates()
	}

	Component.onCompleted: refresh()

	Connections {
		target: window

		function onActiveChanged() {
			if (window.active && !window.detail)
				page.refresh()
		}
	}

	Connections {
		target: bridge

		function onPageRequested(name) {
			if (name === "updates")
				page.refresh()
		}
	}

	actions: [
		GeckoButton {
			visible: page.view !== "running"
			text: page.lastCheck.checked ? "Look again" : "Look for updates"
			primary: !page.lastCheck.checked
			enabled: !bridge.checking && !bridge.busy
			onClicked: page.look()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: page.view === "finished" && window.jobResult.reboot
			primary: true
			text: "Restart now"
			onClicked: bridge.reboot()
		},
		GeckoButton {
			visible: page.view === "pending"
			primary: true
			text: "Update all"
			onClicked: page.updateEverything()
		}
	]

	ColumnLayout {
		anchors.fill: parent
		spacing: 20

		// A short card for the states that need only a sentence or two
		Rectangle {
			visible: ["checking", "never", "current", "problem", "finished"].indexOf(page.view) >= 0
			Layout.fillWidth: true
			implicitHeight: message.implicitHeight + 48
			radius: 16
			color: page.view === "problem" || (page.view === "finished" && !window.jobResult.succeeded)
				? Theme.warningFill : Theme.rail
			border.color: page.view === "problem" ? Theme.warningLine : Theme.line

			ColumnLayout {
				id: message
				anchors.fill: parent
				anchors.margins: 24
				spacing: 10

				Text {
					Layout.fillWidth: true
					font.pixelSize: 24
					font.weight: Font.DemiBold
					color: Theme.textStrong
					wrapMode: Text.WordWrap
					text: ({
						"checking": "Looking for updates…",
						"never": "Look for updates to see what is new.",
						"current": "✓  Everything is up to date.",
						"problem": "This update needs a choice from you.",
						"finished": page.finished && window.jobResult.succeeded
							? "✓  The update is installed." : "The update stopped."
					})[page.view] || ""
				}

				Text {
					Layout.fillWidth: true
					visible: text !== ""
					color: Theme.muted
					wrapMode: Text.WordWrap
					lineHeight: 1.25
					text: {
						if (page.view === "problem")
							return Theme.lines("zypper found a conflict it cannot solve on its own. "
								+ "Update in a terminal to choose how to solve it.") + "\n\n" + page.system.problem
						if (page.view === "finished" && window.jobResult.reboot)
							return Theme.lines("Restart to finish. The new system parts start after a restart.")
						if (page.view === "finished" && !window.jobResult.succeeded)
							return window.jobResult.message
						return ""
					}
				}

				GeckoButton {
					visible: page.view === "problem" || (page.view === "finished" && !window.jobResult.succeeded)
					text: "Update in a terminal"
					onClicked: bridge.updateInTerminal()
				}
			}
		}

		// Counts first, then every package that changes
		RowLayout {
			visible: page.view === "pending"
			Layout.fillWidth: true
			spacing: 16

			SummaryCard {
				visible: !!page.system && page.system.count > 0
				Layout.fillWidth: true
				heading: page.system ? page.system.count + " system packages" : ""
				detail: page.system ? Theme.size(page.system.download) + " to download"
					+ (page.system.reboot ? ", then a restart" : "") : ""
			}

			SummaryCard {
				visible: page.flatpaks.length > 0
				Layout.fillWidth: true
				heading: page.flatpaks.length + " Flatpak " + (page.flatpaks.length === 1 ? "update" : "updates")
				detail: "Apps and the runtimes they use"
			}
		}

		Text {
			visible: page.view === "pending" && !!page.system && page.system.count > 0
			Layout.fillWidth: true
			text: "Tumbleweed updates the whole system together, so system updates cannot be picked one by one."
			color: Theme.muted
			wrapMode: Text.WordWrap
		}

		ListView {
			id: list
			visible: page.view === "pending"
			Layout.fillWidth: true
			Layout.fillHeight: true
			clip: true
			model: page.rows
			boundsBehavior: Flickable.StopAtBounds
			ScrollBar.vertical: GeckoScrollBar {}

			FastWheel { flickable: list }

			delegate: AbstractButton {
				id: row

				required property var modelData
				readonly property bool opensPage: !modelData.header && (!modelData.flatpak || modelData.appKey !== "")

				width: list.width - 16
				height: modelData.header ? 52 : modelData.flatpak ? 52 : 36
				hoverEnabled: opensPage
				focusPolicy: opensPage ? Qt.StrongFocus : Qt.NoFocus
				Accessible.name: modelData.name
				onClicked: {
					if (opensPage)
						window.openPackage(modelData.source,
							modelData.flatpak ? modelData.flatpak.id : modelData.packageName,
							modelData.startTab || "Update")
				}

				background: Rectangle {
					visible: row.opensPage
					radius: 8
					color: row.down ? "#101712" : row.hovered ? "#172219" : "transparent"
					Behavior on color { ColorAnimation { duration: Theme.quick } }
				}

				RowLayout {
					anchors.left: parent.left
					anchors.leftMargin: 12
					anchors.bottom: parent.bottom
					anchors.bottomMargin: row.modelData.header ? 6 : 4
					width: parent.width * 0.55
					spacing: 12

					Text {
						Layout.maximumWidth: row.modelData.header ? Number.POSITIVE_INFINITY : parent.width * 0.6
						text: row.modelData.name
						color: row.modelData.header ? (row.modelData.warning ? Theme.warning : Theme.accentHover)
							: Theme.text
						font.weight: row.modelData.header ? Font.DemiBold : Font.Normal
						elide: Text.ElideRight
					}

					Text {
						visible: !row.modelData.header && row.modelData.packageName !== ""
						Layout.fillWidth: true
						text: row.modelData.packageName || ""
						color: Theme.muted
						font.pixelSize: Theme.smallSize
						elide: Text.ElideRight
					}

					HelpMark {
						visible: row.modelData.header
						text: row.modelData.help || ""
					}

					Item {
						visible: row.modelData.header
						Layout.fillWidth: true
					}
				}

				VersionChange {
					visible: !row.modelData.header
					anchors.right: parent.right
					anchors.bottom: parent.bottom
					anchors.bottomMargin: 6
					anchors.rightMargin: row.modelData.flatpak ? update.width + 16 : 12
					width: parent.width * 0.43 - anchors.rightMargin
					horizontalAlignment: Text.AlignRight
					from: row.modelData.oldVersion || ""
					to: (row.modelData.flatpak ? row.modelData.detail : row.modelData.version) || ""
					font.pixelSize: Theme.smallSize
					elide: Text.ElideLeft
				}

				GeckoButton {
					id: update
					visible: !!row.modelData.flatpak
					anchors.right: parent.right
					anchors.verticalCenter: parent.verticalCenter
					implicitHeight: 40
					leftPadding: 18
					rightPadding: 18
					enabled: !bridge.busy && !bridge.checking
					text: "Update"
					Accessible.name: "Update " + row.modelData.name
					onClicked: page.updateFlatpak(row.modelData.flatpak)
				}
			}
		}

		ProgressPanel {
			visible: page.view === "running" || (page.view === "finished" && !window.jobResult.succeeded)
			Layout.fillWidth: true
			Layout.fillHeight: true
		}

		Item {
			visible: ["checking", "never", "current", "problem"].indexOf(page.view) >= 0
				|| (page.view === "finished" && window.jobResult.succeeded)
			Layout.fillHeight: true
		}
	}
}
