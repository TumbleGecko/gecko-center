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

	// A warning or a problem waits for the person, a note or a good result does not
	function needsLook(check) {
		return check.state === "warning" || check.state === "problem"
	}

	function actionText(action) {
		return ({ "page:updates": "Show updates", "page:storage": "Make room", "page:snapshots": "Show snapshots",
			"page:services": "Show services", "page:sources": "Show sources", "page:drivers": "Show drivers",
			"restart": "Restart", "firewall-on": "Turn on" })[action] || ""
	}

	title: "Overview"
	scroller: scroll
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

	Flickable {
		id: scroll
		anchors.fill: parent
		clip: true
		contentHeight: column.implicitHeight
		boundsBehavior: Flickable.StopAtBounds
		ScrollBar.vertical: GeckoScrollBar {}

		FastWheel { flickable: scroll }

		ColumnLayout {
			id: column
			width: scroll.width - 16
			spacing: 12

			// The machine in a few words, opening Hardware for the rest
			AbstractButton {
				id: machineCard
				visible: !!page.machine
				Layout.fillWidth: true
				implicitHeight: facts.implicitHeight + 40
				hoverEnabled: true
				Accessible.name: "This computer"
				onClicked: window.showPage("hardware")

				background: Rectangle {
					radius: 16
					color: machineCard.down ? "#101712" : machineCard.hovered ? "#1a281f" : "#142019"
					border.color: machineCard.hovered ? "#355040" : Theme.lineStrong
					Behavior on color { ColorAnimation { duration: Theme.quick } }
				}

				GridLayout {
					id: facts
					anchors.left: parent.left
					anchors.right: parent.right
					anchors.top: parent.top
					anchors.margins: 20
					anchors.rightMargin: 52
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
							Layout.preferredWidth: 1
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

				MoreMark {
					anchors.right: parent.right
					anchors.rightMargin: 20
					anchors.verticalCenter: parent.verticalCenter
					lit: machineCard.hovered
				}
			}

			// What needs you comes first, large and with the button that deals with it
			Repeater {
				model: page.checks.filter(check => page.needsLook(check))

				delegate: StatusCard {
					required property var modelData
					Layout.fillWidth: true
					status: modelData.state
					label: modelData.title
					heading: modelData.summary
					details: modelData.details.join("\n")
					actionText: page.actionText(modelData.action)
					onActed: page.act(modelData.action)
				}
			}

			Text {
				visible: page.checks.some(check => !page.needsLook(check))
				Layout.topMargin: 12
				text: page.attention === 0 ? "Everything checked" : "The rest is fine"
				color: Theme.muted
				font.weight: Font.DemiBold
			}

			// Everything that is fine as small tiles, each opening the page that shows it in full
			GridLayout {
				Layout.fillWidth: true
				columns: width >= 1000 ? 3 : 2
				columnSpacing: 12
				rowSpacing: 12

				Repeater {
					model: page.checks.filter(check => !page.needsLook(check))

					delegate: AbstractButton {
						id: tile
						required property var modelData
						Layout.fillWidth: true
						Layout.fillHeight: true
						Layout.preferredWidth: 1
						implicitHeight: tileLines.implicitHeight + 36
						hoverEnabled: true
						enabled: modelData.page !== ""
						Accessible.name: modelData.title + ", " + modelData.summary
						onClicked: window.showPage(modelData.page)

						background: Rectangle {
							radius: 14
							color: tile.down ? "#101712" : tile.hovered ? "#172219" : Theme.rail
							border.color: tile.hovered ? "#355040" : Theme.line
							Behavior on color { ColorAnimation { duration: Theme.quick } }
						}

						contentItem: RowLayout {
							spacing: 14

							Text {
								Layout.leftMargin: 18
								Layout.alignment: Qt.AlignVCenter
								text: tile.modelData.state === "good" ? "✓" : "i"
								color: tile.modelData.state === "good" ? Theme.accent : Theme.muted
								font.pixelSize: 20
								font.weight: Font.DemiBold
							}

							ColumnLayout {
								id: tileLines
								Layout.fillWidth: true
								spacing: 2

								Text {
									Layout.fillWidth: true
									text: tile.modelData.title
									color: Theme.muted
									elide: Text.ElideRight
								}

								Text {
									Layout.fillWidth: true
									text: tile.modelData.summary
									color: Theme.textStrong
									wrapMode: Text.WordWrap
								}
							}

							MoreMark {
								visible: tile.enabled
								Layout.rightMargin: 16
								lit: tile.hovered
							}
						}
					}
				}
			}

			Item { Layout.preferredHeight: 8 }
		}
	}
}
