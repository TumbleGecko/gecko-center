// What went wrong during one start of the computer, crashes first, each problem once with how often it happened
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.journal || null
	readonly property var problems: report ? report.problems : []
	readonly property var crashes: problems.filter(problem => problem.kind === "crash")
	readonly property var others: problems.filter(problem => problem.kind !== "crash")
	readonly property int boot: report ? report.boot : 0

	function when(iso) {
		return Qt.formatDateTime(new Date(iso), "d MMM hh:mm")
	}

	function times(count) {
		return count === 1 ? "Once" : count + " times"
	}

	// Each start named by when it began, the running one first
	readonly property var bootChoices: (report ? report.boots : []).map(start => ({
		value: String(start.index),
		name: start.index === 0 ? "Since " + when(start.start) : when(start.start) + " to " + when(start.end)
	}))

	function readBoot(boot, everyone) {
		if (!everyone) {
			center.readJournal(boot, false)
			return
		}
		window.withPassword(center.journalNeedsPassword(), "Reading the system's messages needs your password.",
			"Show system messages", () => center.readJournal(boot, true))
	}

	function open(problem) {
		window.openDetail({ key: "problem:" + problem.key, problem: problem.key })
	}

	title: "Journal"
	guideTopic: "journal"
	scroller: scroll
	subtitle: !report ? "" : problems.length === 0 ? "Nothing went wrong."
		: [crashes.length > 0 ? crashes.length + (crashes.length === 1 ? " program crashed" : " programs crashed") : "",
			others.length > 0 ? others.length + (others.length === 1 ? " other problem" : " other problems") : ""]
			.filter(part => part).join(", ") + "."
	busy: center.reading.includes("journal")
	empty: !report

	Component.onCompleted: if (!report) center.read("journal")

	actions: [
		GeckoButton {
			text: "Look again"
			enabled: !page.busy
			onClicked: page.readBoot(page.boot, !!page.report && page.report.everyone)
		}
	]

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
			spacing: 12

			ChipRow {
				Layout.fillWidth: true
				choices: page.bootChoices
				current: String(page.boot)
				onChosen: value => page.readBoot(Number(value), !!page.report && page.report.everyone)
			}

			StatusCard {
				visible: !!page.report && !page.report.everyone
				Layout.fillWidth: true
				status: "note"
				heading: "Only your own messages are shown."
				details: "The system and Linux itself write their messages where only an administrator can read them."
				actionText: "Show system messages"
				onActed: page.readBoot(page.boot, true)
			}

			Text {
				visible: !!page.report && page.problems.length === 0
				Layout.fillWidth: true
				Layout.topMargin: 24
				text: "✓  Nothing went wrong during this start."
				color: Theme.textStrong
				font.pixelSize: 22
				font.weight: Font.DemiBold
			}

			Heading { text: "Crashed"; visible: page.crashes.length > 0 }

			// A crash is the program's own fault, so each one is a card naming the program and how often
			GridLayout {
				Layout.fillWidth: true
				columns: width >= 1000 ? 3 : 2
				columnSpacing: 12
				rowSpacing: 12

				Repeater {
					model: page.crashes

					delegate: AbstractButton {
						id: crash
						required property var modelData
						Layout.fillWidth: true
						Layout.preferredWidth: 1
						implicitHeight: crashLines.implicitHeight + 36
						hoverEnabled: true
						Accessible.name: modelData.heading
						onClicked: page.open(modelData)

						background: Rectangle {
							radius: 14
							color: crash.down ? "#1a1610" : crash.hovered ? Qt.lighter(Theme.warningFill, 1.2)
								: Theme.warningFill
							border.color: Theme.warningLine
							Behavior on color { ColorAnimation { duration: Theme.quick } }
						}

						contentItem: RowLayout {
							ColumnLayout {
								id: crashLines
								Layout.fillWidth: true
								spacing: 4

								Text {
									Layout.leftMargin: 18
									Layout.rightMargin: 18
									Layout.fillWidth: true
									text: crash.modelData.source
									color: Theme.textStrong
									font.pixelSize: 20
									font.weight: Font.DemiBold
									elide: Text.ElideRight
								}

								Text {
									Layout.leftMargin: 18
									Layout.rightMargin: 18
									Layout.fillWidth: true
									text: page.times(crash.modelData.count) + ", last " + page.when(crash.modelData.last)
									color: Theme.warning
									elide: Text.ElideRight
								}
							}

							MoreMark {
								Layout.rightMargin: 18
								lit: crash.hovered
							}
						}
					}
				}
			}

			Heading { text: "Other problems"; visible: page.others.length > 0 }

			// Each problem in plain words, how often at the right edge so the busiest stand out
			Repeater {
				model: page.others

				delegate: AbstractButton {
					id: row
					required property var modelData
					Layout.fillWidth: true
					implicitHeight: lines.implicitHeight + 28
					hoverEnabled: true
					Accessible.name: modelData.heading
					onClicked: page.open(modelData)

					background: Rectangle {
						radius: 12
						color: row.down ? "#101712" : row.hovered ? "#172219" : Theme.rail
						border.color: row.hovered ? "#355040" : Theme.line
						Behavior on color { ColorAnimation { duration: Theme.quick } }
					}

					contentItem: RowLayout {
						spacing: 16

						ColumnLayout {
							id: lines
							Layout.leftMargin: 18
							Layout.fillWidth: true
							spacing: 2

							Text {
								Layout.fillWidth: true
								text: row.modelData.heading
								color: Theme.textStrong
								font.weight: Font.DemiBold
								elide: Text.ElideRight
							}

							Text {
								Layout.fillWidth: true
								text: row.modelData.about || row.modelData.lines[row.modelData.lines.length - 1]
									.replace(/^\S+ \S+\s+/, "")
								color: Theme.muted
								font.pixelSize: Theme.smallSize
								elide: Text.ElideRight
							}
						}

						ColumnLayout {
							spacing: 2

							Text {
								Layout.alignment: Qt.AlignRight
								text: page.times(row.modelData.count)
								color: Theme.text
							}

							Text {
								Layout.alignment: Qt.AlignRight
								text: "last " + page.when(row.modelData.last)
								color: Theme.muted
								font.pixelSize: Theme.smallSize
							}
						}

						MoreMark {
							Layout.rightMargin: 18
							lit: row.hovered
						}
					}
				}
			}

			Item { Layout.preferredHeight: 8 }
		}
	}

	component Heading: Text {
		Layout.topMargin: 16
		color: Theme.muted
		font.weight: Font.DemiBold
	}
}
