// The heart of the center, the machine at the top and every health check below it, worst first
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.health || {}
	readonly property var checks: report.checks || []
	readonly property var machine: report.machine || null
	readonly property int attention: window.healthAttention

	function act(action) {
		if (action.startsWith("page:"))
			window.showPage(action.slice(5))
		else if (action === "restart")
			bridge.reboot()
		else if (action === "firewall-on")
			window.runSystem("health", "firewall-on", "", "Turning on the firewall", "Turn on")
	}

	function actionText(action) {
		return ({ "page:updates": "Show updates", "page:storage": "Make room", "page:snapshots": "Show snapshots",
			"page:services": "Show services", "page:sources": "Show sources", "page:drivers": "Show drivers",
			"restart": "Restart", "firewall-on": "Turn on" })[action] || ""
	}

	title: "Overview"
	guideTopic: "tumbleweed"
	busy: center.reading.includes("health")
	empty: checks.length === 0
	busyText: "Looking the system over"
	subtitle: {
		if (checks.length === 0)
			return ""
		if (attention === 0)
			// A no-break space keeps the heart on the line, a plain one after "!" would start a new line
			return "Everything looks good!\u00a0❤️"
		return attention === 1 ? "One thing needs a look." : attention + " things need a look."
	}

	// A full report in ~/gecko-logs, shown in the file manager so it can be sent to someone who helps
	headerExtra: GeckoButton {
		readonly property bool writing: center.reading.includes("report")
		enabled: !writing
		text: writing ? "Writing the report…" : "Share"
		Accessible.name: "Share a report of this computer"
		onClicked: center.read("report")
	}

	Component.onCompleted: center.read("health")

	Connections {
		target: window

		function onActiveChanged() {
			if (window.active && !window.detail)
				center.read("health")
		}
	}

	actions: [
		GeckoButton {
			text: "Look again"
			onClicked: center.read("health")
		},
		Item { Layout.fillWidth: true }
	]

	ColumnLayout {
		anchors.fill: parent
		spacing: 16

		Rectangle {
			id: machineCard
			visible: !!page.machine
			Layout.fillWidth: true
			Layout.rightMargin: 16
			implicitHeight: facts.implicitHeight + 40
			radius: 16
			color: "#142019"
			border.color: Theme.lineStrong

			GridLayout {
				id: facts
				anchors.fill: parent
				anchors.margins: 20
				columns: 2
				columnSpacing: 32
				rowSpacing: 10

				Repeater {
					model: page.machine ? [
						["System", page.machine.system + (page.machine.snapshot ? "  " + page.machine.snapshot : "")],
						["Linux", page.machine.kernel],
						["Desktop", page.machine.desktop || "Unknown"],
						["Processor", page.machine.processor],
						["Graphics", page.machine.graphics || "Unknown"],
						["Memory", page.machine.memory]
					] : []

					delegate: RowLayout {
						required property var modelData
						Layout.fillWidth: true
						spacing: 12

						Text {
							Layout.preferredWidth: 96
							text: modelData[0]
							color: Theme.muted
						}

						Text {
							Layout.fillWidth: true
							text: modelData[1]
							color: Theme.textStrong
							elide: Text.ElideRight
						}
					}
				}
			}
		}

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			model: page.checks

			delegate: StatusCard {
				required property var modelData
				width: list.cardWidth
				status: modelData.state
				label: modelData.title
				heading: modelData.summary
				details: modelData.details.join("\n")
				actionText: page.actionText(modelData.action)
				onActed: page.act(modelData.action)
			}
		}
	}
}
