// A slim scrollbar, vertical or horizontal, that widens under the pointer, shown on every list that can scroll
import QtQuick
import QtQuick.Controls.Basic

ScrollBar {
	id: bar

	// How thick the bar is, it widens under the pointer, across for a vertical bar and down for a horizontal one
	readonly property real thickness: hovered || pressed ? 12 : 8

	policy: size < 1 ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
	implicitWidth: orientation === Qt.Vertical ? thickness : 0
	implicitHeight: orientation === Qt.Horizontal ? thickness : 0
	padding: 2
	Behavior on implicitWidth { NumberAnimation { duration: Theme.quick } }
	Behavior on implicitHeight { NumberAnimation { duration: Theme.quick } }

	contentItem: Rectangle {
		radius: width / 2
		color: bar.pressed ? Theme.accent : bar.hovered ? Theme.accentHover : "#3a4a3e"
		Behavior on color { ColorAnimation { duration: Theme.quick } }
	}
}
