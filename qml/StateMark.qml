// A state as a ringed mark, a tick for good, i for a note, ! for a warning and a cross for a problem
import QtQuick
import GeckoUi

Rectangle {
	id: mark

	// good, note, warning or problem, an empty state shows nothing
	property string status: ""
	// Each state has its own mark as well as its own colour
	readonly property var look: ({
		"good": { mark: "✓", color: Theme.accent },
		"note": { mark: "i", color: Theme.muted },
		"warning": { mark: "!", color: Theme.warning },
		"problem": { mark: "✕", color: Theme.danger }
	})[status] || null

	visible: look !== null
	implicitWidth: 36
	implicitHeight: 36
	radius: width / 2
	color: "transparent"
	border.color: look ? look.color : "transparent"
	border.width: 2

	Text {
		anchors.centerIn: parent
		text: mark.look ? mark.look.mark : ""
		color: mark.look ? mark.look.color : Theme.text
		font.pixelSize: mark.height / 2
		font.weight: Font.Bold
	}
}
