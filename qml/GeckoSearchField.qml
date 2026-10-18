// A search box in the gecko style
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic

TextField {
	id: field

	implicitHeight: 48
	leftPadding: 44
	color: Theme.text
	font.family: Theme.font
	font.pixelSize: Theme.bodySize
	placeholderTextColor: Theme.muted
	selectByMouse: true
	rightPadding: clear.visible ? 52 : 16
	Keys.onEscapePressed: field.clear()

	AbstractButton {
		id: clear
		visible: field.text !== ""
		anchors.right: parent.right
		anchors.rightMargin: 6
		anchors.verticalCenter: parent.verticalCenter
		width: 40
		height: 40
		hoverEnabled: true
		Accessible.name: "Clear the search"
		ToolTip.visible: hovered
		ToolTip.text: "Clear"
		onClicked: field.clear()

		background: Rectangle {
			radius: 10
			color: clear.down ? "#16201a" : clear.hovered ? "#1e2a22" : "transparent"
		}

		contentItem: Text {
			text: "✕"
			color: clear.hovered ? Theme.text : Theme.muted
			font.pixelSize: 18
			horizontalAlignment: Text.AlignHCenter
			verticalAlignment: Text.AlignVCenter
		}
	}

	background: Rectangle {
		radius: 12
		color: Theme.rail
		border.color: field.activeFocus ? Theme.accent : Theme.line
		Behavior on border.color { ColorAnimation { duration: Theme.quick } }

		Text {
			anchors.verticalCenter: parent.verticalCenter
			anchors.left: parent.left
			anchors.leftMargin: 16
			text: "⌕"
			color: Theme.muted
			font.pixelSize: 20
		}
	}
}
