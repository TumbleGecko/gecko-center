// Shows what else an install or removal brings along before anything changes
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
	id: dialog

	property var entry
	property string action: "install"
	// zypper's dry run, null while it is worked out
	property var plan: null
	readonly property var others: {
		if (!plan || !plan.sections)
			return []
		const names = (plan.sections[action === "install" ? "install" : "remove"] || []).map(item => item.name)
		const chosen = entry ? entry.packages || [entry.name, entry.package] : []
		return names.filter(name => !chosen.includes(name))
	}

	signal confirmed()

	parent: Overlay.overlay
	anchors.centerIn: parent
	width: 560
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
			text: (dialog.action === "install" ? "Install " : "Remove ") + (dialog.entry ? dialog.entry.name : "") + "?"
			color: Theme.textStrong
			font.pixelSize: 24
			font.weight: Font.Bold
			wrapMode: Text.WordWrap
		}

		Text {
			Layout.fillWidth: true
			color: dialog.plan && dialog.plan.problem ? Theme.warning : Theme.muted
			wrapMode: Text.WordWrap
			lineHeight: 1.25
			text: {
				const plan = dialog.plan
				if (!plan)
					return "Checking what else would change…"
				if (plan.problem)
					return Theme.lines("zypper cannot do this on its own.") + "\n\n" + plan.problem
				let words = dialog.others.length === 0 ? "Nothing else changes."
					: (dialog.action === "install" ? "These packages will be installed as well."
						: "These packages depend on " + (dialog.entry && dialog.entry.packages ? "them" : "it")
							+ " and will be removed as well.")
				if (dialog.action === "install" && plan.download > 0)
					words += "\n" + Theme.size(plan.download) + " to download."
				return words
			}
		}

		Rectangle {
			visible: dialog.others.length > 0
			Layout.fillWidth: true
			Layout.preferredHeight: Math.min(200, others.contentHeight + 24)
			radius: 10
			color: Theme.ground
			border.color: dialog.action === "remove" ? Theme.warningLine : Theme.line

			ListView {
				id: others
				anchors.fill: parent
				anchors.margins: 12
				clip: true
				model: dialog.others
				boundsBehavior: Flickable.StopAtBounds
				ScrollBar.vertical: GeckoScrollBar {}

				FastWheel { flickable: others }

				delegate: Text {
					required property string modelData
					width: others.width - 16
					text: modelData
					color: Theme.text
					elide: Text.ElideRight
				}
			}
		}

		RowLayout {
			Layout.fillWidth: true

			Item { Layout.fillWidth: true }

			GeckoButton {
				text: "Cancel"
				onClicked: dialog.close()
			}

			GeckoButton {
				primary: dialog.action === "install"
				danger: dialog.action === "remove"
				enabled: dialog.plan !== null && !dialog.plan.problem
				text: dialog.action === "install" ? "Install" : "Remove"
				onClicked: {
					dialog.close()
					dialog.confirmed()
				}
			}
		}
	}
}
