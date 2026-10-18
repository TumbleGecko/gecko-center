// An app's icon, or its first letter on a tile when the catalog has no icon for it
import QtQuick
import GeckoUi

Item {
	id: tile

	property int size: 64
	property string source
	property string name

	implicitWidth: size
	implicitHeight: size

	Image {
		id: image
		anchors.fill: parent
		source: tile.source
		sourceSize: Qt.size(tile.size * 2, tile.size * 2)
		fillMode: Image.PreserveAspectFit
		asynchronous: true
		smooth: true
	}

	Rectangle {
		anchors.fill: parent
		visible: image.status !== Image.Ready
		radius: tile.size / 4
		color: Theme.raised
		border.color: Theme.lineStrong

		Text {
			anchors.centerIn: parent
			text: (tile.name || "?").charAt(0).toUpperCase()
			color: Theme.accentHover
			font.pixelSize: tile.size * 0.45
			font.weight: Font.Bold
		}
	}
}
