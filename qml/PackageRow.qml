// One package from zypper search, its name, one line about it and whether it is installed
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
	id: row

	required property var modelData

	implicitHeight: 72
	hoverEnabled: true
	Accessible.name: modelData.name
	onClicked: window.openPackagePage(modelData.name)

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
				text: row.modelData.name
				color: Theme.textStrong
				font.weight: Font.DemiBold
				elide: Text.ElideRight
			}

			Text {
				Layout.fillWidth: true
				text: row.modelData.summary
				color: Theme.muted
				font.pixelSize: Theme.smallSize
				elide: Text.ElideRight
			}
		}

		Text {
			Layout.rightMargin: 18
			visible: row.modelData.installed
			text: "✓ Installed"
			color: Theme.accentHover
			font.pixelSize: Theme.smallSize
		}
	}
}
