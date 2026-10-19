// The guide to Linux and Tumbleweed, its topics as cards and the words it explains below them
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var guide: center.info.guide || { topics: [], words: [] }

	title: "Guide"
	scroller: list
	subtitle: "Everything about this computer in plain words. Pick a topic, or look up a word below."

	Component.onCompleted: center.read("guide")

	CardList {
		id: list
		anchors.fill: parent
		model: page.guide.topics

		delegate: AbstractButton {
			id: topic
			required property var modelData
			width: list.cardWidth
			implicitHeight: words.implicitHeight + 40
			hoverEnabled: true
			Accessible.name: modelData.title
			onClicked: window.openGuide(modelData.id)

			background: Rectangle {
				radius: 16
				color: topic.down ? "#16201a" : topic.hovered ? "#18221b" : Theme.rail
				border.color: topic.hovered ? Theme.lineStrong : Theme.line
				Behavior on color { ColorAnimation { duration: Theme.quick } }
			}

			contentItem: Item {}

			ColumnLayout {
				id: words
				anchors.left: parent.left
				anchors.right: parent.right
				anchors.top: parent.top
				anchors.margins: 20
				anchors.rightMargin: 56
				spacing: 4

				Text {
					Layout.fillWidth: true
					text: topic.modelData.title
					color: Theme.textStrong
					font.pixelSize: 19
					font.weight: Font.DemiBold
				}

				Text {
					Layout.fillWidth: true
					text: topic.modelData.summary
					color: Theme.muted
					wrapMode: Text.WordWrap
				}
			}

			MoreMark {
				anchors.right: parent.right
				anchors.rightMargin: 20
				anchors.verticalCenter: parent.verticalCenter
				lit: topic.hovered
			}
		}

		footer: ColumnLayout {
			width: list.cardWidth
			spacing: 10

			Text {
				Layout.topMargin: 28
				text: "Words"
				color: Theme.textStrong
				font.pixelSize: 24
				font.weight: Font.Bold
			}

			Repeater {
				model: page.guide.words

				delegate: RowLayout {
					required property var modelData
					Layout.fillWidth: true
					spacing: 16

					Text {
						Layout.preferredWidth: 180
						Layout.alignment: Qt.AlignTop
						text: modelData.word
						color: Theme.accent
						font.weight: Font.DemiBold
						wrapMode: Text.WordWrap
					}

					Text {
						Layout.fillWidth: true
						text: Theme.lines(modelData.meaning)
						color: Theme.text
						wrapMode: Text.WordWrap
						lineHeight: 1.25
					}
				}
			}

			Item { implicitHeight: 12 }
		}
	}
}
