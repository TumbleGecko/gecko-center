// A filter choice, a pill that shows a check mark while it is chosen so the state does not rest on color only
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic

AbstractButton {
	id: chip

	checkable: true
	hoverEnabled: true
	implicitHeight: 38
	implicitWidth: label.implicitWidth + 32
	font.family: Theme.font
	font.pixelSize: Theme.smallSize

	contentItem: Text {
		id: label
		text: (chip.checked ? "✓  " : "") + chip.text
		font: chip.font
		color: chip.checked ? Theme.textStrong : Theme.text
		horizontalAlignment: Text.AlignHCenter
		verticalAlignment: Text.AlignVCenter
	}

	background: Rectangle {
		radius: height / 2
		color: chip.checked ? Theme.doneFill : chip.down ? "#16201a" : chip.hovered ? "#1e2a22" : "transparent"
		border.color: chip.checked ? Theme.accent : Theme.lineStrong
		Behavior on color { ColorAnimation { duration: Theme.quick } }
	}
}
