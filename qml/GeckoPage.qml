// The layout every page shares, a heading with its guide button, the page's own content and a row of actions
import QtQuick
import GeckoUi
import QtQuick.Layouts

Item {
	id: frame

	property string title
	property string subtitle
	// A short line beside the title, which can arrive later without moving anything below
	property string titleNote
	// The guide topic that explains this page in plain words, it adds a button to the heading
	property string guideTopic
	// Working on something, a spinner turns beside the title, or in the middle while there is nothing to show yet
	property bool busy: false
	property bool empty: false
	property string busyText
	default property alias content: body.data
	property alias headerExtra: extra.data
	property alias actions: footer.data
	// The row and its line show only while one of its buttons does, a spacer alone has no width of its own
	readonly property bool actionsVisible: Array.from(footer.children)
		.some(child => child.visible && child.implicitWidth > 0)

	ColumnLayout {
		anchors.fill: parent
		anchors.leftMargin: 56
		anchors.rightMargin: 56
		anchors.topMargin: 44
		anchors.bottomMargin: 28
		spacing: 24

		RowLayout {
			Layout.fillWidth: true
			spacing: 16

			ColumnLayout {
				Layout.fillWidth: true
				spacing: 8

				RowLayout {
					Layout.fillWidth: true
					spacing: 16

					Text {
						Layout.maximumWidth: frame.width - 400
						text: frame.title
						color: Theme.textStrong
						font.pixelSize: Theme.headingSize
						font.weight: Font.Bold
						elide: Text.ElideRight
					}

					Spinner {
						running: frame.busy && !frame.empty
					}

					Text {
						Layout.fillWidth: true
						Layout.alignment: Qt.AlignBaseline
						visible: frame.titleNote !== ""
						text: frame.titleNote
						color: Theme.muted
						font.pixelSize: 18
						elide: Text.ElideRight
					}

					Item {
						visible: frame.titleNote === ""
						Layout.fillWidth: true
					}
				}

				Text {
					Layout.fillWidth: true
					visible: frame.subtitle !== ""
					text: Theme.lines(frame.subtitle)
					color: Theme.muted
					font.pixelSize: 18
					lineHeight: 1.3
					wrapMode: Text.WordWrap
				}
			}

			Row {
				id: extra
				spacing: 8
				Layout.alignment: Qt.AlignBottom
			}

			GeckoButton {
				visible: frame.guideTopic !== ""
				Layout.alignment: Qt.AlignBottom
				text: "?  What is this"
				Accessible.name: "What is this page"
				onClicked: window.openGuide(frame.guideTopic)
			}
		}

		Item {
			id: body
			Layout.fillWidth: true
			Layout.fillHeight: true
			visible: !(frame.busy && frame.empty)
		}

		Column {
			visible: frame.busy && frame.empty
			Layout.fillWidth: true
			Layout.fillHeight: true
			topPadding: 120
			spacing: 18

			Spinner {
				anchors.horizontalCenter: parent.horizontalCenter
				size: 48
			}

			Text {
				anchors.horizontalCenter: parent.horizontalCenter
				text: frame.busyText
				color: Theme.muted
			}
		}

		Rectangle {
			visible: frame.actionsVisible
			Layout.fillWidth: true
			Layout.preferredHeight: 1
			color: Theme.line
		}

		// The row itself stays visible, so each button's own visibility can be read, it only takes no room when empty
		RowLayout {
			id: footer
			// A layout inside a layout fills the space by default, an empty footer would take half the page
			Layout.fillHeight: false
			Layout.preferredHeight: frame.actionsVisible ? implicitHeight : 0
			opacity: frame.actionsVisible ? 1 : 0
			Layout.fillWidth: true
			spacing: 12
		}
	}
}
