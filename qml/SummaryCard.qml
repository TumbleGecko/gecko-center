// One count with a line under it, such as how many packages an update changes
import QtQuick
import GeckoUi
import QtQuick.Layouts

Rectangle {
	id: card

	property string heading
	property string detail

	implicitHeight: 104
	radius: 16
	color: "#142019"
	border.color: Theme.lineStrong

	ColumnLayout {
		anchors.fill: parent
		anchors.margins: 22
		spacing: 6

		Text {
			Layout.fillWidth: true
			text: card.heading
			color: Theme.textStrong
			font.pixelSize: 24
			font.weight: Font.DemiBold
			elide: Text.ElideRight
		}

		Text {
			Layout.fillWidth: true
			text: card.detail
			color: Theme.muted
			elide: Text.ElideRight
		}
	}
}
