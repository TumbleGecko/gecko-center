// One app in the browser, its icon, name, one line about it and where it comes from
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
	id: card

	required property string key
	required property string name
	required property string summary
	required property string image
	required property string source
	required property bool installed

	signal opened()

	hoverEnabled: true
	Accessible.name: name
	onClicked: opened()

	background: Rectangle {
		radius: 16
		color: card.down ? "#101712" : card.hovered ? "#172219" : Theme.rail
		border.color: card.hovered ? "#355040" : Theme.line
		Behavior on color { ColorAnimation { duration: Theme.quick } }
		Behavior on border.color { ColorAnimation { duration: Theme.quick } }
	}

	contentItem: RowLayout {
		spacing: 16

		AppIcon {
			Layout.leftMargin: 18
			Layout.alignment: Qt.AlignVCenter
			size: 64
			source: card.image
			name: card.name
		}

		ColumnLayout {
			Layout.fillWidth: true
			Layout.rightMargin: 16
			Layout.alignment: Qt.AlignVCenter
			spacing: 4

			Text {
				Layout.fillWidth: true
				text: card.name
				color: Theme.textStrong
				font.pixelSize: 18
				font.weight: Font.DemiBold
				elide: Text.ElideRight
			}

			Text {
				Layout.fillWidth: true
				text: card.summary
				color: Theme.muted
				font.pixelSize: Theme.smallSize
				elide: Text.ElideRight
			}

			Text {
				Layout.fillWidth: true
				text: card.source
				color: card.installed ? Theme.accentHover : Theme.muted
				font.pixelSize: Theme.smallSize
				elide: Text.ElideRight
			}
		}
	}
}
