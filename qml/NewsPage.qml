// What is new in openSUSE, and how far the system is behind the newest Tumbleweed snapshot
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.news || null
	readonly property var stories: report && report.stories ? report.stories : []
	readonly property string running: ((center.info.health || {}).machine || {}).snapshot || ""
	readonly property string newest: report && report.newest ? report.newest : ""

	function snapshotWords() {
		if (!newest || !running)
			return ""
		if (newest <= running)
			return "The system runs " + running + ", the newest Tumbleweed snapshot."
		return "The system runs " + running + ", and Tumbleweed has reached " + newest + "."
	}

	title: "News"
	guideTopic: "help"
	subtitle: snapshotWords() || "What is new in openSUSE."
	busy: center.reading.includes("news")
	empty: stories.length === 0

	Component.onCompleted: center.read("news")

	actions: [
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: page.newest > page.running && page.running !== ""
			primary: true
			text: "Show updates"
			onClicked: window.showPage("updates")
		}
	]

	CardList {
		id: list
		anchors.fill: parent
		model: page.stories

		delegate: StatusCard {
			required property var modelData
			width: list.cardWidth
			status: modelData.tumbleweed ? "note" : ""
			label: modelData.date + (modelData.tumbleweed ? "  ·  Tumbleweed" : "")
			heading: modelData.title
			details: modelData.summary
			actionText: "Read"
			actionPrimary: false
			actionEnabled: true
			onActed: Qt.openUrlExternally(modelData.link)
		}
	}
}
