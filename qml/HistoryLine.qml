// One plugging in or out, when, what happened and to what, the same on Hardware and its history page
import QtQuick
import GeckoUi
import QtQuick.Layouts

RowLayout {
	required property var modelData
	// The history page groups lines by day, so it leaves the day out
	property bool showDay: true

	Layout.fillWidth: true
	spacing: 16

	Text {
		Layout.preferredWidth: parent.showDay ? 110 : 52
		text: (parent.showDay ? Qt.formatDate(new Date(modelData.when), "d MMM") + "  " : "") + modelData.time
		color: Theme.muted
	}

	Text {
		Layout.preferredWidth: 110
		text: modelData.action
		color: modelData.action === "Plugged in" ? Theme.accentHover : modelData.action === "Unplugged" ? Theme.warning
			: Theme.text
	}

	Text {
		Layout.fillWidth: true
		text: modelData.name + (modelData.maker ? "  ·  " + modelData.maker : "")
		color: Theme.textStrong
		elide: Text.ElideRight
	}
}
