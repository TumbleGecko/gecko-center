// Tabs that switch between views of one page, the current one is underlined so it does not rest on color only
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic

Row {
	id: tabs

	property var names: []
	// Tabs with no content for this page, they stay in place so the row does not shift
	property var disabledNames: []
	property int current: 0
	// A chosen tab that is turned off shows the first one instead, and comes back once it turns on again
	readonly property int shown: disabledNames.indexOf(names[current]) >= 0 ? 0 : current
	readonly property string currentName: names[shown] || ""

	spacing: 28

	Repeater {
		model: tabs.names

		delegate: AbstractButton {
			id: tab

			required property string modelData
			required property int index
			readonly property bool isCurrent: tabs.shown === index
			readonly property bool isDisabled: tabs.disabledNames.indexOf(modelData) >= 0

			implicitHeight: 40
			implicitWidth: label.implicitWidth
			enabled: !isDisabled
			hoverEnabled: true
			opacity: isDisabled ? 0.4 : 1
			Accessible.role: Accessible.PageTab
			Accessible.name: modelData
			onClicked: tabs.current = index

			contentItem: Text {
				id: label
				text: tab.modelData
				font.family: Theme.font
				font.pixelSize: Theme.bodySize
				font.weight: tab.isCurrent ? Font.DemiBold : Font.Normal
				color: tab.isCurrent ? Theme.textStrong : tab.hovered && !tab.down ? Theme.text : Theme.muted
				verticalAlignment: Text.AlignTop
			}

			Rectangle {
				anchors.left: parent.left
				anchors.right: parent.right
				anchors.bottom: parent.bottom
				height: 3
				radius: 2
				color: tab.isCurrent ? Theme.accent : tab.hovered ? Theme.lineStrong : "transparent"
			}
		}
	}
}
