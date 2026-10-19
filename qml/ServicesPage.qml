// Every running service and those that stopped with an error, how long each ran, and starting, stopping or reading one
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.services || null
	readonly property var failed: report ? report.failed : []
	readonly property var log: center.info.log || null

	function showLog(service) {
		window.withPassword(center.logNeedsPassword(service.scope), "Reading a system service's log needs your password.",
			"Show log", () => {
				logView.unit = service.unit
				logView.open()
				center.readLog(service.scope, service.unit)
			})
	}

	// Each service with the group it is listed under, so the list shows a heading where the group changes
	// The search matches the description or the unit name, whatever case it is typed in
	readonly property var services: (report ? report.services : [])
		.filter(service => [service.description, service.unit].some(text => text.toLowerCase()
			.includes(search.text.trim().toLowerCase())))
		.map(service => Object.assign({}, service, {
			group: service.failed ? "Stopped with an error" : service.scope === "user" ? "Yours" : "The system's"
		}))

	function change(service, action, title, buttonText) {
		window.runSystem("services", action, service.scope + ":" + service.unit, title + " " + service.description,
			buttonText)
	}

	title: "Services"
	scroller: list
	guideTopic: "services"
	subtitle: report === null ? "" : failed.length === 0 ? "Every service runs as it should."
		: failed.length === 1 ? "One stopped with an error." : failed.length + " stopped with an error."
	busy: center.reading.includes("services")
	empty: !report

	Component.onCompleted: center.read("services")

	ColumnLayout {
		anchors.fill: parent
		spacing: 16

		GeckoSearchField {
			id: search
			Layout.fillWidth: true
			Layout.rightMargin: 16
			placeholderText: "Search services"
			Accessible.name: "Search services"
		}

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			spacing: 4
			model: page.services
			section.property: "group"

			section.delegate: Text {
				required property string section
				width: list.cardWidth
				topPadding: 18
				bottomPadding: 8
				leftPadding: 4
				text: section
				color: section === "Stopped with an error" ? Theme.warning : Theme.muted
				font.weight: Font.DemiBold
			}

			delegate: Rectangle {
				id: row
				required property var modelData
				width: list.cardWidth
				implicitHeight: 68
				radius: 10
				color: modelData.failed ? Theme.warningFill : hover.hovered ? Theme.raised : Theme.rail
				border.color: modelData.failed ? Theme.warningLine : "transparent"

				HoverHandler { id: hover }

				// What kind of thing the service looks after, such as sound, the network or the disks
				Rectangle {
					id: kind
					anchors.left: parent.left
					anchors.leftMargin: 14
					anchors.verticalCenter: parent.verticalCenter
					width: 40
					height: 40
					radius: 10
					color: Theme.ground
					border.color: Theme.line

					Text {
						anchors.centerIn: parent
						text: row.modelData.kind
						color: row.modelData.failed ? Theme.warning : Theme.accent
						font.family: "DejaVu Sans"
						font.pixelSize: 20
					}
				}

				Column {
					anchors.left: kind.right
					anchors.right: hover.hovered || row.modelData.failed ? buttons.left : statusChip.left
					anchors.leftMargin: 16
					anchors.rightMargin: 16
					anchors.verticalCenter: parent.verticalCenter
					spacing: 2

					Text {
						width: parent.width
						text: row.modelData.description
						color: Theme.textStrong
						elide: Text.ElideRight
					}

					Text {
						width: parent.width
						// The unit name joins while hovered, it is what a guide or a helper asks for
						text: row.modelData.facts.concat(hover.hovered ? [row.modelData.unit] : []).join("  ·  ")
						color: Theme.muted
						font.pixelSize: Theme.smallSize
						elide: Text.ElideRight
					}
				}

				// Running or failed as a word and a mark, so the state does not rest on colour
				Rectangle {
					id: statusChip
					anchors.right: parent.right
					anchors.rightMargin: 16
					anchors.verticalCenter: parent.verticalCenter
					visible: !hover.hovered && !row.modelData.failed
					width: stateText.implicitWidth + 24
					height: 32
					radius: 16
					color: "transparent"
					border.color: Theme.line

					Text {
						id: stateText
						anchors.centerIn: parent
						text: "✓  Running"
						color: Theme.accent
						font.pixelSize: Theme.smallSize
					}
				}

				// A failed service offers to start again, a running one to restart or stop, both show their log
				Row {
					id: buttons
					anchors.right: parent.right
					anchors.rightMargin: 6
					anchors.verticalCenter: parent.verticalCenter
					spacing: 6
					visible: hover.hovered || row.modelData.failed

					GeckoButton {
						height: 40
						text: "Show log"
						onClicked: page.showLog(row.modelData)
					}

					GeckoButton {
						height: 40
						primary: row.modelData.failed
						enabled: !bridge.busy
						text: row.modelData.failed ? "Start again" : "Restart"
						onClicked: page.change(row.modelData, "restart-service", row.modelData.failed ? "Starting" : "Restarting",
							row.modelData.failed ? "Start" : "Restart")
					}

					GeckoButton {
						height: 40
						visible: !row.modelData.failed
						enabled: !bridge.busy
						text: "Stop"
						onClicked: {
							stopQuestion.service = row.modelData
							stopQuestion.open()
						}
					}
				}
			}
		}
	}

	QuestionDialog {
		id: stopQuestion

		property var service: null

		question: "Stop " + (service ? service.description : "") + "?"
		explanation: "It stays stopped until you start it again or restart the computer. "
			+ "Some services keep the desktop, the network or sound running. Only stop one when you know what it does."
		confirmText: "Stop"
		danger: true
		onConfirmed: page.change(service, "stop-service", "Stopping", "Stop")
	}

	Popup {
		id: logView

		property string unit

		parent: Overlay.overlay
		anchors.centerIn: parent
		width: Math.min(900, parent.width - 80)
		height: Math.min(600, parent.height - 80)
		modal: true
		focus: true
		padding: 28

		Overlay.modal: Rectangle { color: "#b0000000" }

		background: Rectangle {
			radius: 18
			color: Theme.surface
			border.color: Theme.lineStrong
		}

		contentItem: ColumnLayout {
			spacing: 16

			Text {
				Layout.fillWidth: true
				text: "The last lines " + logView.unit + " wrote"
				color: Theme.textStrong
				font.pixelSize: 24
				font.weight: Font.Bold
				elide: Text.ElideMiddle
			}

			Rectangle {
				Layout.fillWidth: true
				Layout.fillHeight: true
				radius: 10
				color: Theme.ground
				border.color: Theme.line

				Spinner {
					anchors.centerIn: parent
					running: !page.log || page.log.unit !== logView.unit
				}

				ScrollView {
					anchors.fill: parent
					visible: !!page.log && page.log.unit === logView.unit
					anchors.margins: 12
					ScrollBar.vertical: GeckoScrollBar {}

					TextArea {
						readOnly: true
						selectByMouse: true
						wrapMode: TextEdit.Wrap
						text: page.log && page.log.unit === logView.unit ? page.log.lines : ""
						color: Theme.text
						font.family: monospace
						font.pixelSize: Theme.smallSize
						background: null
					}
				}
			}

			RowLayout {
				Layout.fillWidth: true

				Item { Layout.fillWidth: true }

				GeckoButton {
					text: "Close"
					onClicked: logView.close()
				}
			}
		}
	}
}
