// One page in the rail, its glyph, its name, a bar while it is the current page and an optional count
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

AbstractButton {
	id: item

	// page, name and glyph
	property var modelData
	readonly property bool current: window.page === modelData.page
	readonly property int badge: ({ "updates": window.pendingCount, "overview": window.healthAttention })[
		modelData.page] || 0

	height: 40
	hoverEnabled: true
	Accessible.name: modelData.name
	onClicked: window.showPage(modelData.page)

	background: Rectangle {
		radius: 10
		color: item.current ? Theme.raised : item.down ? "#16201a" : item.hovered ? "#18221b"
			: "transparent"
		Behavior on color { ColorAnimation { duration: Theme.quick } }

		Rectangle {
			anchors.left: parent.left
			anchors.verticalCenter: parent.verticalCenter
			width: 4
			height: item.current ? 24 : 0
			radius: 2
			color: Theme.accent
			Behavior on height { NumberAnimation { duration: Theme.quick; easing.type: Theme.easing } }
		}
	}

	contentItem: RowLayout {
		spacing: 14

		Text {
			Layout.leftMargin: 14
			Layout.preferredWidth: 22
			horizontalAlignment: Text.AlignHCenter
			text: item.modelData.glyph
			// One font for every symbol, mixed fallback fonts gave them different sizes and shapes
			font.family: "DejaVu Sans"
			color: item.current ? Theme.accent : Theme.muted
			font.pixelSize: 20
		}

		Text {
			Layout.fillWidth: true
			text: item.modelData.name
			color: item.current ? Theme.textStrong : Theme.text
			font.weight: item.current ? Font.DemiBold : Font.Normal
		}

		Rectangle {
			Layout.rightMargin: 10
			visible: item.badge > 0
			implicitWidth: Math.max(28, count.implicitWidth + 16)
			implicitHeight: 26
			radius: 13
			color: item.modelData.page === "overview" ? Theme.warning : Theme.accent

			Text {
				id: count
				anchors.centerIn: parent
				text: item.badge
				color: Theme.textOnAccent
				font.pixelSize: Theme.smallSize
				font.weight: Font.Bold
			}
		}
	}
}
