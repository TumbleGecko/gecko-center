// One clickable line of a list, its name, one line about it and a short note at the right edge
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
	id: row

	property string name
	property string summary
	property string note

	implicitHeight: 72
	hoverEnabled: true
	Accessible.name: name

	background: Rectangle {
		radius: 12
		color: row.down ? "#101712" : row.hovered ? "#172219" : Theme.rail
		border.color: row.hovered ? "#355040" : Theme.line
		Behavior on color { ColorAnimation { duration: Theme.quick } }
	}

	contentItem: RowLayout {
		spacing: 16

		ColumnLayout {
			Layout.leftMargin: 18
			Layout.fillWidth: true
			spacing: 2

			Text {
				Layout.fillWidth: true
				text: row.name
				color: Theme.textStrong
				font.weight: Font.DemiBold
				elide: Text.ElideRight
			}

			Text {
				Layout.fillWidth: true
				text: row.summary
				color: Theme.muted
				font.pixelSize: Theme.smallSize
				elide: Text.ElideRight
			}
		}

		Text {
			Layout.rightMargin: 18
			visible: row.note !== ""
			text: row.note
			color: Theme.accentHover
			font.pixelSize: Theme.smallSize
		}
	}
}
