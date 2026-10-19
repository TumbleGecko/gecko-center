// How full the disks are and the leftovers that can go without losing anything
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.storage || null

	title: "Storage"
	scroller: list
	guideTopic: "storage"
	subtitle: "Free space, and leftovers that can go."
	busy: center.reading.includes("storage")
	empty: !report

	Component.onCompleted: center.read("storage")

	ColumnLayout {
		anchors.fill: parent
		spacing: 16

		RowLayout {
			Layout.fillWidth: true
			Layout.rightMargin: 16
			spacing: 16

			Repeater {
				model: page.report ? page.report.places : []

				delegate: Rectangle {
					id: place
					required property var modelData
					readonly property real used: 1 - modelData.free / modelData.total
					Layout.fillWidth: true
					implicitHeight: 112
					radius: 16
					color: "#142019"
					border.color: Theme.lineStrong

					ColumnLayout {
						anchors.fill: parent
						anchors.margins: 22
						spacing: 10

						Text {
							Layout.fillWidth: true
							text: place.modelData.label + "  ·  " + place.modelData.freeText
								+ " free of " + place.modelData.totalText
							color: Theme.textStrong
							font.pixelSize: 19
							font.weight: Font.DemiBold
							elide: Text.ElideRight
						}

						Meter {
							Layout.fillWidth: true
							fraction: place.used
						}
					}
				}
			}
		}

		// Swap sits beside the free space, since it takes room on a disk too
		Rectangle {
			id: swap
			readonly property var info: page.report ? page.report.swap : null
			visible: !!info
			Layout.fillWidth: true
			Layout.rightMargin: 16
			implicitHeight: swapLines.implicitHeight + 44
			radius: 16
			color: "#142019"
			border.color: swap.info && !swap.info.adviceGood ? Theme.warningLine : Theme.lineStrong

			ColumnLayout {
				id: swapLines
				anchors.left: parent.left
				anchors.right: parent.right
				anchors.top: parent.top
				anchors.margins: 22
				spacing: 10

				RowLayout {
					Layout.fillWidth: true
					spacing: 16

					Text {
						Layout.fillWidth: true
						text: swap.info ? "Swap  ·  " + swap.info.usedText + " of " + swap.info.sizeText + " in use" : ""
						color: Theme.textStrong
						font.pixelSize: 19
						font.weight: Font.DemiBold
						elide: Text.ElideRight
					}

					GeckoButton {
						text: "About swap"
						onClicked: window.openDetail({ key: "device:disk:" + swap.info.disk, device: "disk:" + swap.info.disk })
					}
				}

				Meter {
					Layout.fillWidth: true
					fraction: swap.info && swap.info.size > 0 ? swap.info.used / swap.info.size : 0
				}

				Text {
					Layout.fillWidth: true
					text: swap.info ? swap.info.about.split("\n")[0] : ""
					color: Theme.muted
					wrapMode: Text.WordWrap
				}

				Text {
					Layout.fillWidth: true
					text: swap.info ? swap.info.advice : ""
					color: swap.info && swap.info.adviceGood ? Theme.accentHover : Theme.warning
					wrapMode: Text.WordWrap
				}
			}
		}

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			model: page.report ? page.report.cleanups : []

			// How much each leftover frees comes first, it is what decides whether removing it is worth it
			delegate: Rectangle {
				id: leftover
				required property var modelData
				width: list.cardWidth
				implicitHeight: leftoverLines.implicitHeight + 32
				radius: 14
				color: Theme.rail
				border.color: Theme.line

				RowLayout {
					id: leftoverLines
					anchors.left: parent.left
					anchors.right: parent.right
					anchors.verticalCenter: parent.verticalCenter
					anchors.leftMargin: 20
					anchors.rightMargin: 16
					spacing: 20

					Text {
						Layout.preferredWidth: 100
						text: leftover.modelData.bytes > 0 ? Theme.size(leftover.modelData.bytes) : "–"
						color: Theme.textStrong
						font.pixelSize: 20
						font.weight: Font.DemiBold
					}

					ColumnLayout {
						Layout.fillWidth: true
						spacing: 2

						Text {
							Layout.fillWidth: true
							text: leftover.modelData.title
							color: Theme.textStrong
							elide: Text.ElideRight
						}

						Text {
							Layout.fillWidth: true
							text: leftover.modelData.about
							color: Theme.muted
							wrapMode: Text.WordWrap
						}
					}

					GeckoButton {
						text: "Remove"
						enabled: !bridge.busy
						onClicked: window.runSystem("storage", "clean", leftover.modelData.id,
							"Removing " + leftover.modelData.title.toLowerCase(), "Remove")
					}
				}
			}
		}
	}
}
