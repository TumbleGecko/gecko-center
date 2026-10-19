// The computer at a glance, its main parts large, then disks, what is plugged in, firmware and the board's controllers
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.hardware || null
	readonly property var devices: report ? report.devices : []
	readonly property var computer: devices.find(device => device.group === "Computer") || null

	// The parts that decide how fast the computer is, each shown large
	readonly property var mainParts: devices.filter(device => device.key === "processor" || device.key === "memory"
		|| device.group === "Graphics" || device.group === "Displays")
	// Smaller things in the order people look for them, each kind under its own heading
	readonly property var smallGroups: ["Memory", "Sound", "Input", "Network", "Cameras", "Batteries",
		"Other USB devices"]

	function inGroup(group) {
		// The memory total is a main part, its modules are listed as small cards
		return devices.filter(device => device.group === group && device.key !== "memory")
	}

	// The installed size the memory tile shows too, so both say the same
	function moduleHeading() {
		const total = devices.find(device => device.key === "memory")
		return "Memory modules" + (total ? "  ·  " + total.short + " installed" : "")
	}

	function celsius(device) {
		return device.degrees === null || device.degrees === undefined ? "" : Math.round(device.degrees) + " °C"
	}

	function open(device) {
		window.openDetail({ key: "device:" + device.key, device: device.key })
	}

	title: "Hardware"
	guideTopic: "hardware"
	scroller: scroll
	subtitle: "Everything inside and plugged in."
	busy: center.reading.includes("hardware")
	empty: !report

	Component.onCompleted: {
		center.read("hardware")
		center.read("hardware-history")
	}

	readonly property var history: center.info["hardware-history"] || null

	function openHistory() {
		if (history && history.readable) {
			window.openDetail({ key: "hardware-history", hardwareHistory: true })
			return
		}
		window.withPassword(center.journalNeedsPassword(), "Reading what was plugged in needs your password.",
			"Show", () => center.readHardwareHistoryAsRoot())
	}

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

			// The board and its firmware, opening the computer's own page
			ListRow {
				visible: !!page.computer
				Layout.fillWidth: true
				name: page.computer ? page.computer.short + "  ·  " + page.computer.kind : ""
				summary: page.computer ? page.computer.detail : ""
				onClicked: page.open(page.computer)
			}

			// The newest plugging in and out, opening the whole history
			AbstractButton {
				id: historyBox
				visible: !!page.history
				Layout.fillWidth: true
				implicitHeight: historyLines.implicitHeight + 32
				hoverEnabled: true
				Accessible.name: "What was plugged in and out"
				onClicked: page.openHistory()

				background: Rectangle {
					radius: 12
					color: historyBox.down ? "#101712" : historyBox.hovered ? "#172219" : Theme.rail
					border.color: historyBox.hovered ? "#355040" : Theme.line
					Behavior on color { ColorAnimation { duration: Theme.quick } }
				}

				contentItem: RowLayout {
					spacing: 12

					ColumnLayout {
						id: historyLines
						Layout.leftMargin: 18
						Layout.fillWidth: true
						spacing: 4

						Text {
							text: "Plugged in and out"
							color: Theme.muted
						}

						Text {
							visible: !!page.history && (!page.history.readable || page.history.events.length === 0)
							Layout.fillWidth: true
							text: !page.history ? "" : !page.history.readable
								? "Shows after you log in again, or now with your password."
								: "Nothing was plugged in or out in the last three months."
							color: Theme.text
							wrapMode: Text.WordWrap
						}

						Repeater {
							model: page.history && page.history.readable ? page.history.events.slice(0, 3) : []

							delegate: HistoryLine {}
						}
					}

					MoreMark {
						Layout.rightMargin: 16
						lit: historyBox.hovered
					}
				}
			}

			GridLayout {
				Layout.fillWidth: true
				Layout.topMargin: 8
				columns: width >= 1000 ? 4 : 2
				columnSpacing: 12
				rowSpacing: 12

				Repeater {
					model: page.mainParts
					delegate: PartTile {}
				}
			}

			Heading { text: "Disks"; visible: page.inGroup("Storage").length > 0 }

			GridLayout {
				Layout.fillWidth: true
				columns: width >= 1000 ? 3 : 2
				columnSpacing: 12
				rowSpacing: 12

				Repeater {
					model: page.inGroup("Storage")
					delegate: PartTile {}
				}
			}

			Repeater {
				model: page.smallGroups.filter(group => page.inGroup(group).length > 0)

				delegate: ColumnLayout {
					id: section
					required property string modelData
					Layout.fillWidth: true
					spacing: 8

					Heading { text: section.modelData === "Memory" ? page.moduleHeading() : section.modelData }

					GridLayout {
						Layout.fillWidth: true
						columns: width >= 1000 ? 3 : 2
						columnSpacing: 8
						rowSpacing: 8

						Repeater {
							model: page.inGroup(section.modelData)
							delegate: SmallCard {}
						}
					}
				}
			}

			Heading { text: "Firmware"; visible: page.inGroup("Firmware").length > 0 }

			// Name and version side by side, like the label on the part
			Repeater {
				model: page.inGroup("Firmware")

				delegate: AbstractButton {
					id: firmwareRow
					required property var modelData
					Layout.fillWidth: true
					implicitHeight: 40
					hoverEnabled: true
					Accessible.name: modelData.name
					onClicked: page.open(modelData)

					background: Rectangle {
						radius: 8
						color: firmwareRow.down ? "#101712" : firmwareRow.hovered ? "#172219" : "transparent"
					}

					contentItem: RowLayout {
						spacing: 16

						Text {
							Layout.leftMargin: 12
							Layout.fillWidth: true
							text: firmwareRow.modelData.name
							color: Theme.text
							elide: Text.ElideRight
						}

						Text {
							text: firmwareRow.modelData.summary
							color: Theme.muted
						}

						MoreMark {
							Layout.rightMargin: 12
							font.pixelSize: 22
							lit: firmwareRow.hovered
						}
					}
				}
			}

			Heading { text: "On the motherboard"; visible: page.inGroup("Controllers").length > 0 }

			// The controllers matter least, so they sit last in plain two column text
			GridLayout {
				Layout.fillWidth: true
				Layout.bottomMargin: 8
				columns: 2
				columnSpacing: 8
				rowSpacing: 2

				Repeater {
					model: page.inGroup("Controllers")

					delegate: AbstractButton {
						id: controller
						required property var modelData
						Layout.fillWidth: true
						Layout.preferredWidth: 1
						implicitHeight: 34
						hoverEnabled: true
						Accessible.name: modelData.name
						onClicked: page.open(modelData)

						background: Rectangle {
							radius: 8
							color: controller.down ? "#101712" : controller.hovered ? "#172219" : "transparent"
						}

						contentItem: RowLayout {
							Text {
								Layout.leftMargin: 12
								Layout.fillWidth: true
								text: controller.modelData.short
								color: Theme.muted
								elide: Text.ElideRight
							}

							MoreMark {
								Layout.rightMargin: 12
								font.pixelSize: 22
								lit: controller.hovered
							}
						}
					}
				}
			}
		}
	}

	component Heading: Text {
		Layout.topMargin: 16
		color: Theme.muted
		font.weight: Font.DemiBold
	}

	// One main part large, its group, the name people know, its two key lines and how warm it is
	component PartTile: AbstractButton {
		id: tile
		required property var modelData
		Layout.fillWidth: true
		Layout.fillHeight: true
		Layout.preferredWidth: 1
		implicitHeight: inside.implicitHeight + 36
		hoverEnabled: true
		Accessible.name: modelData.name
		onClicked: page.open(modelData)

		background: Rectangle {
			radius: 16
			color: tile.down ? "#101712" : tile.hovered ? "#1a281f" : "#142019"
			border.color: tile.modelData.hot ? Theme.warningLine : tile.hovered ? "#355040" : Theme.lineStrong
			Behavior on color { ColorAnimation { duration: Theme.quick } }
		}

		ColumnLayout {
			id: inside
			anchors.left: parent.left
			anchors.right: parent.right
			anchors.top: parent.top
			anchors.margins: 18
			anchors.rightMargin: 44
			spacing: 4

			RowLayout {
				Layout.fillWidth: true

				Text {
					Layout.fillWidth: true
					text: tile.modelData.group === "Displays" ? "Screen" : tile.modelData.group === "Storage"
						? "Disk" : tile.modelData.group
					color: Theme.muted
					elide: Text.ElideRight
				}

				Text {
					text: page.celsius(tile.modelData)
					color: tile.modelData.hot ? Theme.warning : Theme.accentHover
					font.weight: Font.DemiBold
				}
			}

			Text {
				Layout.fillWidth: true
				Layout.topMargin: 4
				text: tile.modelData.short
				color: Theme.textStrong
				font.pixelSize: 22
				font.weight: Font.DemiBold
				elide: Text.ElideRight
			}

			Repeater {
				model: [tile.modelData.summary, tile.modelData.detail].filter(line => line && line !== tile.modelData.short)

				delegate: Text {
					required property string modelData
					Layout.fillWidth: true
					text: modelData
					color: Theme.muted
					wrapMode: Text.WordWrap
				}
			}
		}

		MoreMark {
			anchors.right: parent.right
			anchors.rightMargin: 18
			anchors.verticalCenter: parent.verticalCenter
			lit: tile.hovered
		}
	}

	// A plugged in or smaller part, its name with its maker and connection underneath
	component SmallCard: AbstractButton {
		id: card
		required property var modelData
		Layout.fillWidth: true
		Layout.preferredWidth: 1
		implicitHeight: 64
		hoverEnabled: true
		Accessible.name: modelData.name
		onClicked: page.open(modelData)

		background: Rectangle {
			radius: 12
			color: card.down ? "#101712" : card.hovered ? "#172219" : Theme.rail
			border.color: card.modelData.hot ? Theme.warningLine : card.hovered ? "#355040" : Theme.line
			Behavior on color { ColorAnimation { duration: Theme.quick } }
		}

		contentItem: RowLayout {
			spacing: 12

			ColumnLayout {
				Layout.leftMargin: 16
				Layout.fillWidth: true
				spacing: 2

				Text {
					Layout.fillWidth: true
					text: card.modelData.short
					color: Theme.textStrong
					elide: Text.ElideRight
				}

				Text {
					Layout.fillWidth: true
					text: [card.modelData.summary, card.modelData.detail].filter(line => line).join("  ·  ")
					color: Theme.muted
					font.pixelSize: Theme.smallSize
					elide: Text.ElideRight
				}
			}

			Text {
				visible: text !== ""
				text: page.celsius(card.modelData)
				color: card.modelData.hot ? Theme.warning : Theme.accentHover
			}

			MoreMark {
				Layout.rightMargin: 16
				lit: card.hovered
			}
		}
	}
}
