// The pages down the left side in groups, with how many updates wait and how many checks need a look
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
	color: Theme.rail

	Rectangle {
		anchors.right: parent.right
		width: 1
		height: parent.height
		color: Theme.line
	}

	ColumnLayout {
		anchors.fill: parent
		anchors.margins: 20
		anchors.topMargin: 32
		spacing: 28

		Row {
			Layout.leftMargin: 4
			spacing: 12

			Image {
				width: 44
				height: 44
				source: assets + "gecko.png"
				sourceSize: Qt.size(88, 88)
				smooth: true
			}

			Text {
				anchors.verticalCenter: parent.verticalCenter
				text: "Gecko Center"
				color: Theme.text
				font.pixelSize: 21
				font.weight: Font.Bold
			}
		}

		Flickable {
			id: scroller
			Layout.fillWidth: true
			Layout.fillHeight: true
			clip: true
			contentHeight: entries.implicitHeight
			boundsBehavior: Flickable.StopAtBounds
			ScrollBar.vertical: GeckoScrollBar {}

			FastWheel { flickable: scroller }

			Column {
				id: entries
				width: scroller.width
				spacing: 2

				Repeater {
					model: [
						{ page: "news", name: "News", glyph: "≡" },
						{ page: "overview", name: "Overview", glyph: "♥" },
						{ heading: "Software" },
						{ page: "explore", name: "Explore", glyph: "⚲" },
						{ page: "installed", name: "Installed", glyph: "▤" },
						{ page: "updates", name: "Updates", glyph: "⟳" },
						{ page: "sources", name: "Sources", glyph: "⇣" },
						{ heading: "System" },
						{ page: "performance", name: "Performance", glyph: "↗" },
						{ page: "snapshots", name: "Snapshots", glyph: "⟲" },
						{ page: "hardware", name: "Hardware", glyph: "▦" },
						{ page: "drivers", name: "Drivers", glyph: "▣" },
						{ page: "storage", name: "Storage", glyph: "⛃" },
						{ page: "services", name: "Services", glyph: "⚑" },
						{ page: "journal", name: "Journal", glyph: "☰" },
						{ heading: "Help" },
						{ page: "guide", name: "Guide", glyph: "?" },
						{ page: "settings", name: "Settings", glyph: "⚙" }
					]

					// A group's name, or one of its pages
					delegate: Loader {
						id: row
						required property var modelData
						width: entries.width
						sourceComponent: modelData.heading ? groupName : pageButton

						Component {
							id: groupName

							Text {
								topPadding: 12
								bottomPadding: 6
								leftPadding: 14
								text: row.modelData.heading
								color: Theme.muted
								font.pixelSize: Theme.smallSize
								font.weight: Font.DemiBold
							}
						}

						Component {
							id: pageButton
							RailButton { modelData: row.modelData }
						}
					}
				}
			}
		}
	}
}
