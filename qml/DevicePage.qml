// One part of the computer in full, all the hardware page found about it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property string deviceKey
	readonly property var device: ((center.info.hardware || {}).devices || [])
		.find(item => item.key === deviceKey) || null

	title: device ? device.name : ""
	subtitle: !device ? "" : device.group === device.kind ? device.group
		: device.group + "  ·  " + device.kind
	busy: center.reading.includes("hardware")
	empty: !device

	// Coming back through history can open this before the hardware page has read anything
	Component.onCompleted: if (!center.info.hardware) center.read("hardware")

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			text: "Look again"
			enabled: !page.busy
			onClicked: center.read("hardware")
		}
	]

	CardList {
		id: list
		anchors.fill: parent
		spacing: 8
		model: page.device ? page.device.facts : []

		delegate: RowLayout {
			required property var modelData
			width: list.cardWidth
			spacing: 20

			Text {
				Layout.preferredWidth: 220
				Layout.alignment: Qt.AlignTop
				text: modelData[0]
				color: Theme.muted
				wrapMode: Text.WordWrap
			}

			// Selectable, so a part number or version can be copied into a search
			TextEdit {
				Layout.fillWidth: true
				text: modelData[1]
				color: Theme.text
				font.family: Theme.font
				font.pixelSize: Theme.bodySize
				readOnly: true
				selectByMouse: true
				wrapMode: Text.Wrap
			}
		}
	}
}
