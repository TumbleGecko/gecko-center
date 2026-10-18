// Asks for your password once, and the app keeps it in memory for every later change that needs root
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
	id: dialog

	// Why the password is needed now, and the button that goes ahead
	property string reason: ""
	property string actionText: "Continue"
	// The app's name, for the line saying how long it keeps the password
	property string appName: ""
	// A function that returns true when sudo accepted the password, such as RootAccess.setPassword
	property var checkPassword: password => false

	signal accepted()

	function tryPassword() {
		if (dialog.checkPassword(field.text)) {
			field.text = ""
			wrong.visible = false
			close()
			accepted()
		} else {
			wrong.visible = true
			field.selectAll()
		}
	}

	parent: Overlay.overlay
	anchors.centerIn: parent
	width: 460
	modal: true
	focus: true
	padding: 28
	onOpened: field.forceActiveFocus()

	Overlay.modal: Rectangle { color: "#b0000000" }

	background: Rectangle {
		radius: 18
		color: Theme.surface
		border.color: Theme.lineStrong
	}

	contentItem: ColumnLayout {
		spacing: 16

		Text {
			text: "Your password"
			color: Theme.textStrong
			font.pixelSize: 24
			font.weight: Font.Bold
		}

		Text {
			Layout.fillWidth: true
			text: Theme.lines(dialog.reason + " " + dialog.appName + " keeps it in memory only until you close it.")
			color: Theme.muted
			wrapMode: Text.WordWrap
		}

		TextField {
			id: field
			Layout.fillWidth: true
			implicitHeight: 48
			echoMode: TextInput.Password
			color: Theme.text
			font.pixelSize: Theme.bodySize
			placeholderText: "Password"
			placeholderTextColor: Theme.muted
			Accessible.name: "Password"
			onAccepted: dialog.tryPassword()

			background: Rectangle {
				radius: 10
				color: Theme.ground
				border.color: field.activeFocus ? Theme.accent : Theme.line
			}
		}

		Text {
			id: wrong
			visible: false
			text: "That password was not accepted, try again."
			color: Theme.danger
		}

		RowLayout {
			Layout.fillWidth: true

			Item { Layout.fillWidth: true }

			GeckoButton {
				text: "Cancel"
				onClicked: dialog.close()
			}

			GeckoButton {
				primary: true
				text: dialog.actionText
				enabled: field.text.length > 0
				onClicked: dialog.tryPassword()
			}
		}
	}
}
