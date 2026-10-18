// How often the lazy background check looks for updates, or whether it looks at all, and news notifications
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property bool checkOn: bridge.backgroundInterval !== ""

	function setInterval(interval) {
		// Only the first time needs root, to place the refresh unit and the rule that lets you start it
		const needsRoot = interval !== "" ? !bridge.refreshUnitInstalled : bridge.refreshUnitInstalled
		window.withPassword(needsRoot && bridge.needsPassword(),
			"Setting up the background check places one system file that refreshes package lists, "
			+ "which needs your password.", "Continue", () => bridge.setBackground(interval))
	}

	title: "Settings"

	ColumnLayout {
		anchors.left: parent.left
		anchors.right: parent.right
		spacing: 16

		Rectangle {
			Layout.fillWidth: true
			implicitHeight: settings.implicitHeight + 48
			radius: 16
			color: Theme.rail
			border.color: Theme.line

			ColumnLayout {
				id: settings
				anchors.fill: parent
				anchors.margins: 24
				spacing: 18

				RowLayout {
					Layout.fillWidth: true
					spacing: 16

					ColumnLayout {
						Layout.fillWidth: true
						spacing: 6

						Text {
							text: "Look for updates in the background"
							color: Theme.textStrong
							font.pixelSize: 19
							font.weight: Font.DemiBold
						}

						Text {
							Layout.fillWidth: true
							text: Theme.lines("It only refreshes the package lists and never installs anything. "
								+ "When updates are ready, the gecko in the tray gets a green dot.")
							color: Theme.muted
							wrapMode: Text.WordWrap
							lineHeight: 1.25
						}
					}

					Toggle {
						checked: page.checkOn
						enabled: !bridge.busy
						Accessible.name: "Look for updates in the background"
						// The switch follows the timer file, a cancelled password keeps it where it was
						onToggled: {
							const wanted = checked
							checked = Qt.binding(() => page.checkOn)
							page.setInterval(wanted ? "weekly" : "")
						}
					}
				}

				Text {
					visible: page.checkOn
					text: "How often"
					color: Theme.muted
				}

				Row {
					visible: page.checkOn
					spacing: 8

					Repeater {
						model: [["daily", "Every day"], ["weekly", "Every week"], ["monthly", "Every month"]]

						delegate: Chip {
							required property var modelData
							text: modelData[1]
							checked: bridge.backgroundInterval === modelData[0]
							onClicked: page.setInterval(modelData[0])
						}
					}
				}
			}
		}

		Rectangle {
			Layout.fillWidth: true
			implicitHeight: newsSetting.implicitHeight + 48
			radius: 16
			color: Theme.rail
			border.color: Theme.line

			RowLayout {
				id: newsSetting
				anchors.fill: parent
				anchors.margins: 24
				spacing: 16

				ColumnLayout {
					Layout.fillWidth: true
					spacing: 6

					Text {
						text: "Notify on news"
						color: Theme.textStrong
						font.pixelSize: 19
						font.weight: Font.DemiBold
					}

					Text {
						Layout.fillWidth: true
						text: "A notification for each new openSUSE news story."
						color: Theme.muted
						wrapMode: Text.WordWrap
					}
				}

				Toggle {
					checked: bridge.notifyNews
					Accessible.name: "Notify on news"
					onToggled: bridge.setNotifyNews(checked)
				}
			}
		}
	}
}
