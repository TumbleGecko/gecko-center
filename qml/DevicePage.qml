// One part of the computer in full, what a disk holds and why, then all the hardware page found about it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property string deviceKey
	readonly property var device: ((center.info.hardware || {}).devices || [])
		.find(item => item.key === deviceKey) || null

	title: device ? device.name : ""
	scroller: scroll
	subtitle: !device ? "" : device.group === device.kind ? device.group
		: device.group + "  ·  " + device.kind
	busy: center.reading.includes("hardware")
	empty: !device

	// Coming back through history can open this before the hardware page has read anything
	Component.onCompleted: if (!center.info.hardware) center.read("hardware")

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			text: "Look again"
			enabled: !page.busy
			onClicked: center.read("hardware")
		}
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

			Text {
				visible: !!page.device && page.device.uses.length > 0
				text: "What it holds"
				color: Theme.muted
				font.weight: Font.DemiBold
			}

			// Each part of a disk with how full it is, what it is for and what to do about it, if anything
			Repeater {
				model: page.device ? page.device.uses : []

				delegate: Rectangle {
					id: use
					required property var modelData
					Layout.fillWidth: true
					implicitHeight: holds.implicitHeight + 40
					radius: 16
					color: "#142019"
					border.color: !modelData.adviceGood
						? Theme.warningLine : Theme.lineStrong

					ColumnLayout {
						id: holds
						anchors.left: parent.left
						anchors.right: parent.right
						anchors.top: parent.top
						anchors.margins: 20
						spacing: 10

						RowLayout {
							Layout.fillWidth: true
							spacing: 16

							Text {
								Layout.fillWidth: true
								text: use.modelData.title
								color: Theme.textStrong
								font.pixelSize: 20
								font.weight: Font.DemiBold
								elide: Text.ElideRight
							}

							Text {
								text: use.modelData.used === null ? use.modelData.sizeText
									: use.modelData.usedText + " of " + use.modelData.sizeText + " in use"
								color: Theme.text
							}
						}

						Meter {
							visible: use.modelData.used !== null
							Layout.fillWidth: true
							fraction: use.modelData.size > 0 ? use.modelData.used / use.modelData.size : 0
						}

						Text {
							Layout.fillWidth: true
							text: Theme.lines(use.modelData.about)
							color: Theme.muted
							wrapMode: Text.WordWrap
							lineHeight: 1.25
						}

						Text {
							visible: use.modelData.advice !== ""
							Layout.fillWidth: true
							text: use.modelData.advice
							color: use.modelData.adviceGood ? Theme.accentHover : Theme.warning
							wrapMode: Text.WordWrap
						}
					}
				}
			}

			Text {
				visible: !!page.device && page.device.uses.length > 0
				Layout.topMargin: 12
				text: "Details"
				color: Theme.muted
				font.weight: Font.DemiBold
			}

			Repeater {
				model: page.device ? page.device.facts : []

				delegate: RowLayout {
					required property var modelData
					Layout.fillWidth: true
					spacing: 20

					Text {
						Layout.preferredWidth: 220
						Layout.alignment: Qt.AlignTop
						text: modelData[0]
						color: Theme.muted
						wrapMode: Text.WordWrap
					}

					// Selectable, so a part number or version can be copied into a search
					TextEdit {
						Layout.fillWidth: true
						text: modelData[1]
						color: Theme.text
						font.family: Theme.font
						font.pixelSize: Theme.bodySize
						readOnly: true
						selectByMouse: true
						wrapMode: Text.Wrap
					}
				}
			}

			Item { Layout.preferredHeight: 8 }
		}
	}
}
