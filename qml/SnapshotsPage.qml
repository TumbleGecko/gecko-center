// The saved copies of the system, newest first, and rolling back to one of them
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.snapshots || null
	readonly property var snapshots: report ? report.snapshots : []
	// Snapper's list needs root, so the page waits for the password before it reads
	property bool asked: false

	function read() {
		window.withPassword(center.readNeedsPassword("snapshots"), "Reading the snapshots needs your password.",
			"Show snapshots", () => {
				page.asked = true
				center.read("snapshots")
			})
	}

	title: "Snapshots"
	scroller: list
	guideTopic: "snapshots"
	subtitle: "Roll back to how the system was before a change. Your own files stay as they are."
	busy: center.reading.includes("snapshots")
	empty: !report

	Component.onCompleted: {
		if (!center.readNeedsPassword("snapshots")) {
			asked = true
			center.read("snapshots")
		}
	}

	actions: [
		GeckoButton {
			text: page.asked ? "Read the snapshots again" : "Show snapshots"
			primary: !page.asked
			onClicked: page.read()
		},
		Item { Layout.fillWidth: true }
	]

	CardList {
		id: list
		anchors.fill: parent
		model: page.snapshots

		header: StatusCard {
			width: list.cardWidth
			visible: !!page.report && !page.report.known
			height: visible ? implicitHeight + 12 : 0
			status: "warning"
			heading: "The snapshots could not be read."
			details: page.report ? page.report.problem : ""
		}

		// A timeline, the day on the left, what changed in the middle and what can be done on the right
		delegate: AbstractButton {
			id: row
			required property var modelData
			readonly property bool current: modelData.running || modelData.next
			width: list.cardWidth
			implicitHeight: Math.max(day.implicitHeight, words.implicitHeight) + 32
			hoverEnabled: true
			Accessible.name: modelData.title
			onClicked: window.openDetail({ key: "snapshot-" + modelData.number, snapshot: modelData.number })

			background: Rectangle {
				radius: 14
				color: row.down ? "#101712" : row.hovered ? "#172219" : row.current ? "#142019" : Theme.rail
				border.color: row.current ? Theme.accent : row.hovered ? "#355040" : Theme.line
				Behavior on color { ColorAnimation { duration: Theme.quick } }
			}

			contentItem: RowLayout {
				spacing: 20

				ColumnLayout {
					id: day
					Layout.leftMargin: 20
					Layout.preferredWidth: 84
					Layout.alignment: Qt.AlignVCenter
					spacing: 0

					// The running system is now, its own date is when it was last restored and would look old
					Text {
						text: row.modelData.running ? "Now" : row.modelData.next ? "Next start"
							: Qt.formatDateTime(new Date(row.modelData.date.replace(" ", "T")), "d MMM")
						color: row.current ? Theme.accentHover : Theme.textStrong
						font.pixelSize: 19
						font.weight: Font.DemiBold
					}

					Text {
						visible: !row.current
						text: Qt.formatDateTime(new Date(row.modelData.date.replace(" ", "T")), "hh:mm")
						color: Theme.muted
					}
				}

				ColumnLayout {
					id: words
					Layout.fillWidth: true
					spacing: 2

					Text {
						Layout.fillWidth: true
						text: row.modelData.title
						color: Theme.textStrong
						font.weight: Font.DemiBold
						elide: Text.ElideRight
					}

					Text {
						Layout.fillWidth: true
						text: row.modelData.about
						color: Theme.muted
						wrapMode: Text.WordWrap
						maximumLineCount: 2
						elide: Text.ElideRight
					}
				}

				Text {
					visible: row.current
					text: row.modelData.running ? "✓  Running now" : "Starts next time"
					color: Theme.accentHover
				}

				GeckoButton {
					visible: !row.current
					text: "Roll back"
					enabled: !bridge.busy
					onClicked: rollback.ask(row.modelData)
				}

				MoreMark {
					Layout.rightMargin: 18
					lit: row.hovered
				}
			}
		}
	}

	Text {
		anchors.centerIn: parent
		visible: !page.asked
		text: "Show snapshots to see them."
		color: Theme.muted
	}

	RollbackDialog { id: rollback }
}
