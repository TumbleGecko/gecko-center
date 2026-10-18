// A thin bar filled to a share, green until it runs high and then in the warning colour
import QtQuick
import GeckoUi

Rectangle {
	id: meter

	// From 0 to 1
	property real fraction: 0
	property real high: 0.9

	implicitHeight: 10
	radius: height / 2
	color: Theme.raised

	Rectangle {
		width: parent.width * Math.max(0, Math.min(1, meter.fraction))
		height: parent.height
		radius: parent.radius
		color: meter.fraction > meter.high ? Theme.warning : Theme.accent
		Behavior on width { NumberAnimation { duration: Theme.calm; easing.type: Theme.easing } }
	}
}
