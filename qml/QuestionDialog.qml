// Asks once before a change that is hard to take back, in plain words, with Cancel and the change's own button
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
	id: dialog

	property string question
	property string explanation
	property string confirmText
	property bool danger: false

	signal confirmed()

	parent: Overlay.overlay
	anchors.centerIn: parent
	width: 600
	modal: true
	focus: true
	padding: 28

	Overlay.modal: Rectangle { color: "#b0000000" }

	background: Rectangle {
		radius: 18
		color: Theme.surface
		border.color: Theme.lineStrong
	}

	contentItem: ColumnLayout {
		spacing: 16

		Text {
			Layout.fillWidth: true
			text: dialog.question
			color: Theme.textStrong
			font.pixelSize: 24
			font.weight: Font.Bold
			wrapMode: Text.WordWrap
		}

		Text {
			Layout.fillWidth: true
			text: Theme.lines(dialog.explanation)
			color: Theme.muted
			wrapMode: Text.WordWrap
			lineHeight: 1.25
		}

		RowLayout {
			Layout.fillWidth: true

			Item { Layout.fillWidth: true }

			GeckoButton {
				text: "Cancel"
				onClicked: dialog.close()
			}

			GeckoButton {
				primary: !dialog.danger
				danger: dialog.danger
				text: dialog.confirmText
				onClicked: {
					dialog.close()
					dialog.confirmed()
				}
			}
		}
	}
}
