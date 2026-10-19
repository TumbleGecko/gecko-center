// The saved copies of the system, newest first, and rolling back to one of them
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.snapshots || null
	readonly property var snapshots: report ? report.snapshots : []
	// Snapper's list needs root, so the page waits for the password before it reads
	property bool asked: false

	function read() {
		window.withPassword(center.readNeedsPassword("snapshots"), "Reading the snapshots needs your password.",
			"Show snapshots", () => {
				page.asked = true
				center.read("snapshots")
			})
	}

	title: "Snapshots"
	scroller: list
	guideTopic: "snapshots"
	subtitle: "Roll back to how the system was before a change. Your own files stay as they are."
	busy: center.reading.includes("snapshots")
	empty: !report

	Component.onCompleted: {
		if (!center.readNeedsPassword("snapshots")) {
			asked = true
			center.read("snapshots")
		}
	}

	actions: [
		GeckoButton {
			text: page.asked ? "Look again" : "Show snapshots"
			primary: !page.asked
			onClicked: page.read()
		},
		Item { Layout.fillWidth: true }
	]

	CardList {
		id: list
		anchors.fill: parent
		model: page.snapshots

		header: StatusCard {
			width: list.cardWidth
			visible: !!page.report && !page.report.known
			height: visible ? implicitHeight + 12 : 0
			status: "warning"
			heading: "The snapshots could not be read."
			details: page.report ? page.report.problem : ""
		}

		delegate: StatusCard {
			required property var modelData
			width: list.cardWidth
			status: modelData.running ? "good" : modelData.next ? "note" : ""
			label: modelData.running || modelData.next ? "" : "#" + modelData.number
			heading: modelData.title
			details: modelData.about
			actionText: modelData.running || modelData.next ? "" : "Roll back"
			onActed: rollback.ask(modelData)

			GeckoButton {
				text: "More info"
				onClicked: window.openDetail({ key: "snapshot-" + modelData.number, snapshot: modelData.number })
			}
		}
	}

	Text {
		anchors.centerIn: parent
		visible: !page.asked
		text: "Show snapshots to see them."
		color: Theme.muted
	}

	RollbackDialog { id: rollback }
}
