// Each graphics card with the driver it runs on, then every firmware with its version and any update for it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.drivers || null
	readonly property var cards: report ? report.cards : []
	readonly property var firmware: report ? report.allFirmware : []
	readonly property int updateCount: firmware.filter(device => device.update).length

	function updateFirmware(device) {
		window.runSystem("drivers", "firmware-update", device.id, "Updating " + device.name, "Update",
			device.update.restart)
	}

	title: "Drivers"
	guideTopic: "drivers"
	scroller: scroll
	subtitle: !report ? "" : cards.some(card => card.wantsNvidia) ? "The graphics card is missing its fast driver."
		: updateCount === 1 ? "One firmware update is ready."
		: updateCount > 1 ? updateCount + " firmware updates are ready."
		: "Everything has the driver and firmware it needs."
	busy: center.reading.includes("drivers")
	empty: !report

	Component.onCompleted: center.read("drivers")

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

			Heading { text: "Graphics"; Layout.topMargin: 0 }

			// A card's driver is what decides how fast games and video run, so each card gets the room to say so
			Repeater {
				model: page.cards

				delegate: Rectangle {
					id: card
					required property var modelData
					Layout.fillWidth: true
					implicitHeight: cardLines.implicitHeight + 44
					radius: 16
					color: modelData.wantsNvidia ? Theme.warningFill : "#142019"
					border.color: modelData.wantsNvidia ? Theme.warningLine : Theme.lineStrong

					RowLayout {
						id: cardLines
						anchors.left: parent.left
						anchors.right: parent.right
						anchors.verticalCenter: parent.verticalCenter
						anchors.margins: 22
						spacing: 20

						Text {
							Layout.alignment: Qt.AlignTop
							text: card.modelData.wantsNvidia ? "!" : "✓"
							color: card.modelData.wantsNvidia ? Theme.warning : Theme.accent
							font.pixelSize: 26
							font.weight: Font.DemiBold
						}

						ColumnLayout {
							Layout.fillWidth: true
							spacing: 4

							Text {
								text: card.modelData.maker
								color: Theme.muted
							}

							Text {
								Layout.fillWidth: true
								text: card.modelData.name.split(" (")[0]
								color: Theme.textStrong
								font.pixelSize: 22
								font.weight: Font.DemiBold
								elide: Text.ElideRight
							}

							Text {
								Layout.fillWidth: true
								text: card.modelData.wantsNvidia
									? "It runs on the basic driver, which is slow for games. NVIDIA's own driver makes it "
										+ "much faster, for GeForce 16, RTX 20 and newer."
									: (card.modelData.about || "Driver " + card.modelData.driver)
										+ (card.modelData.version ? " Version " + card.modelData.version + "." : "")
								color: Theme.text
								wrapMode: Text.WordWrap
							}
						}

						GeckoButton {
							visible: card.modelData.wantsNvidia
							primary: true
							text: "Install the NVIDIA driver"
							enabled: !bridge.busy
							onClicked: confirm.open()
						}
					}
				}
			}

			Heading { text: "Firmware" }

			Text {
				Layout.fillWidth: true
				text: "Firmware is the small program inside a part itself. Makers that publish updates for Linux "
					+ "offer them here, the rest update through the maker's own tool or not at all."
				color: Theme.muted
				wrapMode: Text.WordWrap
			}

			// Name, version and what can be done, one line per part like the label on a box
			Repeater {
				model: page.firmware

				delegate: Rectangle {
					id: row
					required property var modelData
					Layout.fillWidth: true
					implicitHeight: rowLines.implicitHeight + 28
					radius: 12
					color: modelData.update ? Theme.warningFill : Theme.rail
					border.color: modelData.update ? Theme.warningLine : Theme.line

					RowLayout {
						id: rowLines
						anchors.left: parent.left
						anchors.right: parent.right
						anchors.verticalCenter: parent.verticalCenter
						anchors.leftMargin: 18
						anchors.rightMargin: 14
						spacing: 16

						ColumnLayout {
							Layout.fillWidth: true
							spacing: 2

							Text {
								Layout.fillWidth: true
								text: row.modelData.name
								color: Theme.textStrong
								elide: Text.ElideRight
							}

							Text {
								Layout.fillWidth: true
								text: [row.modelData.vendor, "Version " + row.modelData.current]
									.filter(part => part).join("  ·  ")
								color: Theme.muted
								font.pixelSize: Theme.smallSize
								elide: Text.ElideRight
							}
						}

						Text {
							visible: !row.modelData.update
							text: row.modelData.updatable ? "✓  Up to date" : row.modelData.updatedBy
							color: row.modelData.updatable ? Theme.accentHover : Theme.muted
						}

						Text {
							visible: !!row.modelData.update && row.modelData.update.security
							text: "Security fix"
							color: Theme.warning
							font.weight: Font.DemiBold
						}

						GeckoButton {
							visible: !!row.modelData.update
							primary: true
							enabled: !bridge.busy
							text: row.modelData.update ? "Update to " + row.modelData.update.newest : ""
							onClicked: page.updateFirmware(row.modelData)
						}
					}
				}
			}

			Item { Layout.preferredHeight: 8 }
		}
	}

	component Heading: Text {
		Layout.topMargin: 16
		color: Theme.muted
		font.weight: Font.DemiBold
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
