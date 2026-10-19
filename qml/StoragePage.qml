// How full the disks are and the leftovers that can go without losing anything
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.storage || null

	title: "Storage"
	scroller: scroll
	guideTopic: "storage"
	subtitle: "Free space, and leftovers that can go."
	busy: center.reading.includes("storage")
	empty: !report

	Component.onCompleted: center.read("storage")

	Flickable {
		id: scroll
		anchors.fill: parent
		clip: true
		contentHeight: column.implicitHeight
		boundsBehavior: Flickable.StopAtBounds
		ScrollBar.vertical: GeckoScrollBar {}

		FastWheel { flickable: scroll }

		ColumnLayout {
			id: column
			width: scroll.width - 16
			spacing: 16

			RowLayout {
				Layout.fillWidth: true
				spacing: 16

				Repeater {
					model: page.report ? page.report.places : []

					delegate: Rectangle {
						id: place
						required property var modelData
						readonly property real used: 1 - modelData.free / modelData.total
						Layout.fillWidth: true
						implicitHeight: 112
						radius: 16
						color: "#142019"
						border.color: Theme.lineStrong

						ColumnLayout {
							anchors.fill: parent
							anchors.margins: 22
							spacing: 10

							Text {
								Layout.fillWidth: true
								text: place.modelData.label + "  ·  " + place.modelData.freeText
									+ " free of " + place.modelData.totalText
								color: Theme.textStrong
								font.pixelSize: 19
								font.weight: Font.DemiBold
								elide: Text.ElideRight
							}

							Meter {
								Layout.fillWidth: true
								fraction: place.used
							}
						}
					}
				}
			}

			// Swap sits beside the free space, since it takes room on a disk too
			Rectangle {
				id: swap
				readonly property var info: page.report ? page.report.swap : null
				visible: !!info
				Layout.fillWidth: true
				implicitHeight: swapLines.implicitHeight + 44
				radius: 16
				color: "#142019"
				border.color: swap.info && !swap.info.adviceGood ? Theme.warningLine : Theme.lineStrong

				ColumnLayout {
					id: swapLines
					anchors.left: parent.left
					anchors.right: parent.right
					anchors.top: parent.top
					anchors.margins: 22
					spacing: 10

					RowLayout {
						Layout.fillWidth: true
						spacing: 16

						Text {
							Layout.fillWidth: true
							text: swap.info ? "Swap  ·  " + swap.info.usedText + " of " + swap.info.sizeText + " in use" : ""
							color: Theme.textStrong
							font.pixelSize: 19
							font.weight: Font.DemiBold
							elide: Text.ElideRight
						}

						GeckoButton {
							text: "About swap"
							onClicked: window.openDetail({ key: "device:disk:" + swap.info.disk, device: "disk:" + swap.info.disk })
						}
					}

					Meter {
						Layout.fillWidth: true
						fraction: swap.info && swap.info.size > 0 ? swap.info.used / swap.info.size : 0
					}

					Text {
						Layout.fillWidth: true
						text: swap.info ? Theme.lines(swap.info.about.split("\n")[0]) : ""
						color: Theme.muted
						wrapMode: Text.WordWrap
					}

					Text {
						Layout.fillWidth: true
						text: swap.info ? Theme.lines(swap.info.advice) : ""
						color: swap.info && swap.info.adviceGood ? Theme.accentHover : Theme.warning
						wrapMode: Text.WordWrap
					}
				}
			}

			// Snapshots take room as well, the system tidies them by itself and the month old ones can go sooner
			Rectangle {
				id: snapshotCard
				readonly property var info: center.info["old-snapshots"] || null
				readonly property bool reading: center.reading.includes("old-snapshots")
				readonly property bool found: !!info && info.known && info.count > 0
				Layout.fillWidth: true
				implicitHeight: snapshotLines.implicitHeight + 44
				radius: 16
				color: "#142019"
				border.color: Theme.lineStrong

				ColumnLayout {
					id: snapshotLines
					anchors.left: parent.left
					anchors.right: parent.right
					anchors.top: parent.top
					anchors.margins: 22
					spacing: 10

					RowLayout {
						Layout.fillWidth: true
						spacing: 16

						Text {
							Layout.fillWidth: true
							text: "Snapshots" + (!snapshotCard.info || !snapshotCard.info.known ? ""
								: snapshotCard.found ? "  ·  " + snapshotCard.info.count + " older than a month hold "
									+ Theme.size(snapshotCard.info.bytes)
								: "  ·  none older than a month")
							color: Theme.textStrong
							font.pixelSize: 19
							font.weight: Font.DemiBold
							elide: Text.ElideRight
						}

						GeckoButton {
							visible: !snapshotCard.found
							enabled: !snapshotCard.reading
							text: snapshotCard.reading ? "Looking, about half a minute…" : "Look for old snapshots"
							onClicked: window.withPassword(center.readNeedsPassword("old-snapshots"),
								"Reading the snapshots needs your password.", "Look", () => center.read("old-snapshots"))
						}

						GeckoButton {
							visible: snapshotCard.found
							danger: true
							enabled: !bridge.busy
							text: "Remove them"
							onClicked: removeSnapshots.open()
						}
					}

					Text {
						Layout.fillWidth: true
						text: Theme.lines("Each software change saves a snapshot, so it can be undone on the Snapshots page. "
							+ "The system keeps the newest ten and removes older ones on its own, and changes to the kernel "
							+ "are kept a little longer.")
						color: Theme.muted
						wrapMode: Text.WordWrap
					}

					Text {
						visible: snapshotCard.found
						Layout.fillWidth: true
						text: snapshotCard.found ? Theme.lines("The oldest is from "
							+ Qt.formatDateTime(new Date(snapshotCard.info.oldest.replace(" ", "T")), "d MMMM yyyy")
							+ ". Removing them frees at least " + Theme.size(snapshotCard.info.bytes)
							+ ". The running system and the newer snapshots stay.") : ""
						color: Theme.text
						wrapMode: Text.WordWrap
					}
				}
			}

			Repeater {
				model: page.report ? page.report.cleanups : []

				// How much each leftover frees comes first, it is what decides whether removing it is worth it
				delegate: Rectangle {
					id: leftover
					required property var modelData
					Layout.fillWidth: true
					implicitHeight: leftoverLines.implicitHeight + 32
					radius: 14
					color: Theme.rail
					border.color: Theme.line

					RowLayout {
						id: leftoverLines
						anchors.left: parent.left
						anchors.right: parent.right
						anchors.verticalCenter: parent.verticalCenter
						anchors.leftMargin: 20
						anchors.rightMargin: 16
						spacing: 20

						Text {
							Layout.preferredWidth: 100
							text: leftover.modelData.bytes > 0 ? Theme.size(leftover.modelData.bytes) : "–"
							color: Theme.textStrong
							font.pixelSize: 20
							font.weight: Font.DemiBold
						}

						ColumnLayout {
							Layout.fillWidth: true
							spacing: 2

							Text {
								Layout.fillWidth: true
								text: leftover.modelData.title
								color: Theme.textStrong
								elide: Text.ElideRight
							}

							Text {
								Layout.fillWidth: true
								text: leftover.modelData.about
								color: Theme.muted
								wrapMode: Text.WordWrap
							}
						}

						GeckoButton {
							text: "Remove"
							enabled: !bridge.busy
							onClicked: window.runSystem("storage", "clean", leftover.modelData.id,
								"Removing " + leftover.modelData.title.toLowerCase(), "Remove")
						}
					}
				}
			}
		}
	}

	QuestionDialog {
		id: removeSnapshots
		readonly property var info: center.info["old-snapshots"] || null
		question: "Remove " + (info ? info.count : 0) + " old snapshots?"
		explanation: "They are older than a month, so the system can no longer go back to how it was then. "
			+ "Your own files are not touched."
		confirmText: "Remove"
		danger: true
		onConfirmed: window.runSystem("old-snapshots", "snapshots-remove-old", info.numbers, "Removing old snapshots",
			"Remove")
	}
}
