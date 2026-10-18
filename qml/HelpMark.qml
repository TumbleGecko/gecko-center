// A small question mark that explains the thing next to it while the pointer rests on it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic

Rectangle {
	id: mark

	property string text

	implicitWidth: 26
	implicitHeight: 26
	radius: width / 2
	color: hover.hovered ? "#1e2a22" : "transparent"
	border.color: Theme.lineStrong
	Accessible.role: Accessible.HelpBalloon
	Accessible.name: text

	Text {
		anchors.centerIn: parent
		text: "?"
		color: hover.hovered ? Theme.textStrong : Theme.muted
		font.family: Theme.font
		font.pixelSize: Theme.smallSize
	}

	HoverHandler {
		id: hover
	}

	ToolTip {
		visible: hover.hovered
		text: Theme.lines(mark.text)
		width: Math.min(implicitWidth, 460)
		font.family: Theme.font
		font.pixelSize: Theme.smallSize
	}
}
