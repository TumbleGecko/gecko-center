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
	scroller: list
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

		// Each story as a card, the whole card opens it in the browser, which the arrow pointing out says
		delegate: AbstractButton {
			id: story
			required property var modelData
			width: list.cardWidth
			implicitHeight: storyLines.implicitHeight + 36
			hoverEnabled: true
			Accessible.name: modelData.title
			onClicked: Qt.openUrlExternally(modelData.link)

			background: Rectangle {
				radius: 16
				color: story.down ? "#101712" : story.hovered ? "#172219" : Theme.rail
				border.color: story.hovered ? "#355040" : Theme.line
				Behavior on color { ColorAnimation { duration: Theme.quick } }
			}

			contentItem: RowLayout {
				spacing: 20

				Text {
					Layout.leftMargin: 20
					Layout.preferredWidth: 84
					Layout.alignment: Qt.AlignTop
					text: Qt.formatDateTime(new Date(story.modelData.date), "d MMM")
					color: Theme.muted
					wrapMode: Text.WordWrap
				}

				ColumnLayout {
					id: storyLines
					Layout.fillWidth: true
					spacing: 6

					Text {
						visible: story.modelData.tumbleweed
						text: "Tumbleweed"
						color: Theme.accentHover
						font.pixelSize: Theme.smallSize
						font.weight: Font.DemiBold
					}

					Text {
						Layout.fillWidth: true
						text: story.modelData.title
						color: Theme.textStrong
						font.pixelSize: 19
						font.weight: Font.DemiBold
						wrapMode: Text.WordWrap
					}

					Text {
						Layout.fillWidth: true
						text: story.modelData.summary
						color: Theme.muted
						wrapMode: Text.WordWrap
						maximumLineCount: 3
						elide: Text.ElideRight
					}
				}

				MoreMark {
					Layout.rightMargin: 18
					text: "↗"
					font.pixelSize: 22
					lit: story.hovered
				}
			}
		}
	}
}
