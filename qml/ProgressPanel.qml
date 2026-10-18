// How far a running change got, what it does right now and the newest lines it printed
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
	id: panel

	radius: 16
	color: Theme.rail
	border.color: Theme.line

	ColumnLayout {
		anchors.fill: parent
		anchors.margins: 22
		spacing: 14

		RowLayout {
			Layout.fillWidth: true

			Text {
				Layout.fillWidth: true
				text: window.jobTitle
				color: Theme.textStrong
				font.pixelSize: 22
				font.weight: Font.DemiBold
				elide: Text.ElideRight
			}

			Text {
				text: Math.round(window.jobFraction * 100) + " %"
				color: Theme.muted
			}
		}

		Rectangle {
			Layout.fillWidth: true
			Layout.preferredHeight: 10
			radius: 5
			color: Theme.raised

			Rectangle {
				width: parent.width * window.jobFraction
				height: parent.height
				radius: 5
				color: Theme.accent
				Behavior on width { NumberAnimation { duration: Theme.calm; easing.type: Theme.easing } }
			}
		}

		Text {
			Layout.fillWidth: true
			text: window.jobText
			color: Theme.text
			elide: Text.ElideMiddle
		}

		Rectangle {
			Layout.fillWidth: true
			Layout.fillHeight: true
			radius: 10
			color: Theme.ground
			border.color: Theme.line

			ListView {
				id: log
				anchors.fill: parent
				anchors.margins: 12
				clip: true
				model: window.jobLog
				boundsBehavior: Flickable.StopAtBounds
				// Lines keep their full length and the log scrolls sideways to show them, nothing wraps or gets cut
				flickableDirection: Flickable.HorizontalAndVerticalFlick
				contentWidth: Math.max(width - 16, widest)
				property real widest: 0
				// Room under the last line for the sideways scrollbar
				bottomMargin: 14
				ScrollBar.vertical: GeckoScrollBar {}
				ScrollBar.horizontal: GeckoScrollBar { orientation: Qt.Horizontal }
				// The log follows new lines while it shows the end, scrolling up to read stops it until you scroll back down
				property bool following: true
				onMovementEnded: following = atYEnd

				FastWheel { flickable: log }

				// The log keeps a fixed number of lines, so new ones arrive without the count changing
				Connections {
					target: log.model

					function onRowsInserted() {
						if (log.following)
							log.positionViewAtEnd()
					}

					// A new job clears the log and starts following again
					function onRowsRemoved() {
						if (log.model.count === 0)
							log.following = true
					}
				}

				delegate: Text {
					required property string line
					text: line
					color: Theme.muted
					font.family: monospace
					font.pixelSize: Theme.smallSize
					Component.onCompleted: log.widest = Math.max(log.widest, implicitWidth)
				}
			}
		}
	}
}
