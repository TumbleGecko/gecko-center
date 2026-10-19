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
							text: place.modelData.label + "  ·  " + Theme.size(place.modelData.free)
								+ " free of " + Theme.size(place.modelData.total)
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

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			model: page.report ? page.report.cleanups : []

			delegate: StatusCard {
				required property var modelData
				width: list.cardWidth
				label: modelData.bytes > 0 ? Theme.size(modelData.bytes) : ""
				heading: modelData.title
				details: modelData.about
				actionText: "Remove"
				onActed: window.runSystem("storage", "clean", modelData.id, "Removing " + modelData.title.toLowerCase(),
					"Remove")
			}
		}
	}
}
