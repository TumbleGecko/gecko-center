// Each part of the computer in groups, each one opens its own page with all that is known about it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.hardware || null

	// A temperature at the row's right edge, the one number that changes from look to look
	function temperature(device) {
		const found = device.facts.find(fact => fact[0] === "Temperature")
		return found ? found[1] : ""
	}

	title: "Hardware"
	subtitle: "Everything inside and plugged in."
	busy: center.reading.includes("hardware")
	empty: !report

	Component.onCompleted: center.read("hardware")

	CardList {
		id: list
		anchors.fill: parent
		spacing: 4
		model: page.report ? page.report.devices : []
		section.property: "group"

		section.delegate: Text {
			required property string section
			width: list.cardWidth
			topPadding: 18
			bottomPadding: 8
			leftPadding: 4
			text: section
			color: Theme.muted
			font.weight: Font.DemiBold
		}

		delegate: ListRow {
			required property var modelData
			width: list.cardWidth
			name: modelData.name
			summary: modelData.summary
			note: page.temperature(modelData)
			onClicked: window.openDetail({ key: "device:" + modelData.key, device: modelData.key })
		}
	}
}
