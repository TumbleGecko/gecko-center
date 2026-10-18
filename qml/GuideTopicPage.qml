// One guide topic read in full, with a button to the page where it is done
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property string topicId
	readonly property var topic: ((center.info.guide || {}).topics || []).find(item => item.id === topicId) || null

	title: topic ? topic.title : ""
	subtitle: topic ? topic.summary : ""

	Component.onCompleted: center.read("guide")

	actions: [
		GeckoButton {
			text: "All topics"
			onClicked: window.showPage("guide")
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: !!page.topic && page.topic.page !== ""
			primary: true
			text: page.topic ? page.topic.action : ""
			onClicked: window.showPage(page.topic.page)
		}
	]

	Flickable {
		id: reader
		anchors.fill: parent
		clip: true
		contentHeight: paragraphs.implicitHeight
		boundsBehavior: Flickable.StopAtBounds
		ScrollBar.vertical: GeckoScrollBar {}

		FastWheel { flickable: reader }

		ColumnLayout {
			id: paragraphs
			width: Math.min(reader.width - 16, 900)
			spacing: 18

			Repeater {
				model: page.topic ? page.topic.body.split("\n") : []

				delegate: Text {
					required property string modelData
					Layout.fillWidth: true
					text: Theme.lines(modelData)
					color: Theme.text
					font.pixelSize: 19
					wrapMode: Text.WordWrap
					lineHeight: 1.35
				}
			}
		}
	}
}
