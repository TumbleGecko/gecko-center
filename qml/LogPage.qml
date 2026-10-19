// One problem from the logs in full, what it means, when it happened and the lines the journal has for it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property string problemKey
	readonly property var problem: ((center.info.logs || {}).problems || [])
		.find(item => item.key === problemKey) || null

	function when(iso) {
		return Qt.formatDateTime(new Date(iso), "d MMM yyyy hh:mm:ss")
	}

	title: problem ? problem.heading : ""
	subtitle: !problem ? "" : problem.source + "  ·  " + (problem.count === 1 ? "once" : problem.count + " times")
	scroller: scroll
	empty: !problem

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: !!page.problem && page.problem.unit !== ""
			text: "Open Services"
			onClicked: window.showPage("services")
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
			spacing: 16

			StatusCard {
				visible: !!page.problem && page.problem.about !== ""
				Layout.fillWidth: true
				status: page.problem && page.problem.kind === "crash" ? "warning" : "note"
				heading: page.problem ? page.problem.about : ""
			}

			GridLayout {
				Layout.fillWidth: true
				columns: 2
				columnSpacing: 20
				rowSpacing: 6

				Repeater {
					model: page.problem ? [
						["Written by", page.problem.source],
						["First", page.when(page.problem.first)],
						["Last", page.when(page.problem.last)],
						["Service", page.problem.unit]
					].filter(fact => fact[1]) : []

					delegate: Text {
						required property var modelData
						required property int index
						Layout.row: index
						Layout.column: 0
						Layout.preferredWidth: 160
						text: modelData[0]
						color: Theme.muted
					}
				}

				Repeater {
					model: page.problem ? [page.problem.source, page.when(page.problem.first),
						page.when(page.problem.last), page.problem.unit].filter(value => value) : []

					delegate: Text {
						required property string modelData
						required property int index
						Layout.row: index
						Layout.column: 1
						Layout.fillWidth: true
						text: modelData
						color: Theme.text
						elide: Text.ElideRight
					}
				}
			}

			Text {
				Layout.topMargin: 8
				text: page.problem && page.problem.lines.length < page.problem.count
					? "The newest " + page.problem.lines.length + " messages" : "The messages"
				color: Theme.muted
				font.weight: Font.DemiBold
			}

			// The journal's own words, selectable so they can be copied into a search or a bug report
			Rectangle {
				Layout.fillWidth: true
				implicitHeight: raw.implicitHeight + 28
				radius: 12
				color: "#0b100d"
				border.color: Theme.line

				TextEdit {
					id: raw
					anchors.fill: parent
					anchors.margins: 14
					text: page.problem ? page.problem.lines.join("\n\n") : ""
					color: Theme.text
					font.family: monospace
					font.pixelSize: Theme.smallSize
					readOnly: true
					selectByMouse: true
					wrapMode: TextEdit.Wrap
				}
			}

			Item { Layout.preferredHeight: 8 }
		}
	}
}
