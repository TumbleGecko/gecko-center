// Everything plugged in and out in the last three months, newest first and grouped by day
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var history: center.info["hardware-history"] || null
	readonly property var events: history ? history.events.map(event => Object.assign({}, event, {
		dayName: Qt.formatDate(new Date(event.when), "dddd d MMMM")
	})) : []

	title: "Plugged in and out"
	subtitle: Theme.lines("USB devices from the last three months, newest first. It updates as soon as something is "
		+ "plugged in or out" + (history && history.checked ? ", last checked "
			+ Qt.formatDateTime(new Date(history.checked), "hh:mm:ss") : "") + ".")
	scroller: list
	busy: center.reading.includes("hardware-history")
	empty: !history

	Component.onCompleted: {
		if (!history)
			center.read("hardware-history")
		center.watchHardware(true)
	}
	Component.onDestruction: center.watchHardware(false)

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true }
	]

	CardList {
		id: list
		anchors.fill: parent
		spacing: 8
		model: page.events
		section.property: "dayName"

		section.delegate: Text {
			required property string section
			width: list.cardWidth
			topPadding: 18
			bottomPadding: 6
			text: section
			color: Theme.muted
			font.weight: Font.DemiBold
		}

		delegate: Item {
			required property var modelData
			width: list.cardWidth
			implicitHeight: line.implicitHeight

			HistoryLine {
				id: line
				anchors.left: parent.left
				anchors.right: parent.right
				modelData: parent.modelData
				showDay: false
			}
		}
	}
}
