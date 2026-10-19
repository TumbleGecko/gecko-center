// One finding or item, its state as a mark and a colour, a heading, plain words below and an optional button
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
	id: card

	// good, note, warning or problem, an empty state shows no mark
	property string status: ""
	property string label
	property string heading
	property string details
	property string actionText
	property bool actionPrimary: status === "problem"
	property bool actionDanger: false
	property bool actionEnabled: !bridge.busy
	// Further controls, such as a switch, sit at the right end after the button
	default property alias extra: trailing.data
	readonly property bool attention: status === "problem" || status === "warning"


	signal acted()

	implicitHeight: body.implicitHeight + 40
	radius: 16
	color: attention ? Theme.warningFill : Theme.rail
	border.color: attention ? Theme.warningLine : Theme.line

	RowLayout {
		id: body
		anchors.left: parent.left
		anchors.right: parent.right
		anchors.top: parent.top
		anchors.margins: 20
		spacing: 18

		StateMark {
			Layout.alignment: Qt.AlignTop
			status: card.status
		}

		ColumnLayout {
			Layout.fillWidth: true
			spacing: 4

			Text {
				visible: card.label !== ""
				Layout.fillWidth: true
				text: card.label
				color: Theme.muted
				elide: Text.ElideRight
			}

			Text {
				Layout.fillWidth: true
				// Each sentence starts a line of its own, so a second one never wraps under the first
				text: Theme.lines(card.heading)
				color: Theme.textStrong
				font.pixelSize: 19
				font.weight: Font.DemiBold
				wrapMode: Text.WordWrap
			}

			Text {
				Layout.fillWidth: true
				Layout.topMargin: 4
				visible: card.details !== ""
				text: Theme.lines(card.details)
				color: Theme.muted
				wrapMode: Text.WordWrap
				lineHeight: 1.25
			}
		}

		GeckoButton {
			Layout.alignment: Qt.AlignVCenter
			visible: card.actionText !== ""
			primary: card.actionPrimary
			danger: card.actionDanger
			enabled: card.actionEnabled
			text: card.actionText
			onClicked: card.acted()
		}

		// A layout rather than a Row, so a switch and a taller button share one centre line
		RowLayout {
			id: trailing
			Layout.alignment: Qt.AlignVCenter
			visible: children.length > 0
			spacing: body.spacing
		}
	}
}
