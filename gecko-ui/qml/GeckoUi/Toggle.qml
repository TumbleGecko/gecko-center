// An on and off switch whose knob springs across
import QtQuick
import QtQuick.Controls.Basic

AbstractButton {
	id: control

	checkable: true
	implicitWidth: 52
	implicitHeight: 44

	Rectangle {
		id: track
		anchors.verticalCenter: parent.verticalCenter
		width: 48
		height: 28
		radius: height / 2
		color: control.checked ? Theme.accent : "#2c3a30"
		Behavior on color { ColorAnimation { duration: Theme.quick } }

		Rectangle {
			width: 22
			height: 22
			radius: 11
			y: 3
			x: control.checked ? 23 : 3
			color: control.checked ? Theme.textOnAccent : Theme.muted
			Behavior on x { NumberAnimation { duration: 250; easing.type: Easing.OutBack } }
		}
	}
}
