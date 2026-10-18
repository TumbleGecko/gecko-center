// A system change from one of the system pages while it runs, and how it ended, with a restart when it needs one
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
	id: dialog

	// Set before opening, a change such as rolling back to a snapshot only takes effect after a restart
	property bool restartAfter: false
	readonly property bool running: bridge.busy
	readonly property bool failed: window.jobResult !== null && !window.jobResult.succeeded
	readonly property bool succeeded: !running && window.jobResult !== null && window.jobResult.succeeded
	readonly property bool needsRestart: succeeded && (restartAfter || window.jobResult.reboot)

	parent: Overlay.overlay
	anchors.centerIn: parent
	width: Math.min(760, parent.width - 80)
	height: Math.min(560, parent.height - 80)
	modal: true
	focus: true
	padding: 28
	closePolicy: running ? Popup.NoAutoClose : Popup.CloseOnEscape

	Overlay.modal: Rectangle { color: "#b0000000" }

	background: Rectangle {
		radius: 18
		color: Theme.surface
		border.color: Theme.lineStrong
	}

	contentItem: ColumnLayout {
		spacing: 16

		ProgressPanel {
			Layout.fillWidth: true
			Layout.fillHeight: true
		}

		// A job that went well needs no words, because the green Done button says it
		Text {
			Layout.fillWidth: true
			visible: !dialog.running && (dialog.failed || dialog.needsRestart)
			text: dialog.failed ? Theme.lines("It did not finish. " + (window.jobResult.message || ""))
				: "It takes effect after a restart."
			color: dialog.failed ? Theme.warning : Theme.textStrong
			wrapMode: Text.WordWrap
		}

		RowLayout {
			Layout.fillWidth: true

			Item { Layout.fillWidth: true }

			GeckoButton {
				enabled: !dialog.running
				primary: dialog.succeeded && !dialog.needsRestart
				text: dialog.needsRestart ? "Later" : dialog.succeeded ? "Done" : "Close"
				onClicked: dialog.close()
			}

			GeckoButton {
				visible: dialog.needsRestart
				primary: true
				text: "Restart now"
				onClicked: bridge.reboot()
			}
		}
	}
}
