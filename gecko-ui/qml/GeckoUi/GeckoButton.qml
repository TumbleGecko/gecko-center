// A button in the gecko style, filled green for the main action, filled red for one that destroys, outlined otherwise
import QtQuick
import QtQuick.Controls.Basic

Button {
	id: control

	property bool primary: false
	property bool danger: false
	readonly property bool filled: primary || danger

	implicitHeight: 48
	leftPadding: 24
	rightPadding: 24
	font.family: Theme.font
	font.pixelSize: Theme.bodySize
	font.weight: filled ? Font.DemiBold : Font.Normal
	hoverEnabled: true

	contentItem: Text {
		text: control.text
		font: control.font
		color: control.danger ? Theme.textOnDanger : control.primary ? Theme.textOnAccent : Theme.text
		opacity: control.enabled ? 1 : 0.45
		horizontalAlignment: Text.AlignHCenter
		verticalAlignment: Text.AlignVCenter
	}

	background: Rectangle {
		radius: 12
		color: {
			if (!control.filled)
				return control.down ? "#16201a" : control.hovered ? "#1e2a22" : "transparent"
			if (!control.enabled)
				return "#2c3a30"
			if (control.danger)
				return control.down ? Theme.dangerPressed : control.hovered ? Theme.dangerHover : Theme.dangerFill
			return control.down ? Theme.accentPressed : control.hovered ? Theme.accentHover : Theme.accent
		}
		border.width: control.filled ? 0 : 1
		border.color: "#2c3a30"
		Behavior on color { ColorAnimation { duration: Theme.quick } }
	}
}
