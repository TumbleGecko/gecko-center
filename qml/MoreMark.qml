// The arrow at the right edge of anything that opens more, so it is clear at a glance that it can be clicked
import QtQuick
import GeckoUi

Text {
	// Brighter while the pointer is over what it belongs to
	property bool lit: false

	text: "›"
	color: lit ? Theme.textStrong : Theme.muted
	font.pixelSize: 28
	verticalAlignment: Text.AlignVCenter
	Accessible.ignored: true
	Behavior on color { ColorAnimation { duration: Theme.quick } }
}
