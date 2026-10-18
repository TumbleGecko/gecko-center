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

	// Each state has its own mark as well as its own colour
	readonly property var look: ({
		"good": { mark: "✓", color: Theme.accent },
		"note": { mark: "i", color: Theme.muted },
		"warning": { mark: "!", color: Theme.warning },
		"problem": { mark: "✕", color: Theme.danger }
	})[status] || null

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

		Rectangle {
			visible: card.look !== null
			Layout.alignment: Qt.AlignTop
			implicitWidth: 36
			implicitHeight: 36
			radius: 18
			color: "transparent"
			border.color: card.look ? card.look.color : "transparent"
			border.width: 2

			Text {
				anchors.centerIn: parent
				text: card.look ? card.look.mark : ""
				color: card.look ? card.look.color : Theme.text
				font.pixelSize: 18
				font.weight: Font.Bold
			}
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
				text: card.heading
				color: Theme.textStrong
				font.pixelSize: 19
				font.weight: Font.DemiBold
				wrapMode: Text.WordWrap
			}

			Text {
				Layout.fillWidth: true
				Layout.topMargin: 4
				visible: card.details !== ""
				text: card.details
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
