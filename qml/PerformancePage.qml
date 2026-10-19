// How busy the machine is right now, the processor with each core, memory, each graphics card and the busiest apps
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.performance || null
	readonly property var gpus: report ? report.gpus : []

	// The list's columns, the one it is sorted by and which way, busiest first until a heading is clicked
	readonly property var columns: [
		{ key: "name", title: "App" }, { key: "cpu", title: "Processor" }, { key: "gpu", title: "Graphics" },
		{ key: "gpuMemory", title: "Video memory" }, { key: "memory", title: "Memory" }
	]
	property string sortKey: "cpu"
	property bool sortDescending: true
	readonly property var apps: {
		const wanted = search.text.trim().toLowerCase()
		const found = (report ? report.apps : []).filter(app => app.name.toLowerCase().includes(wanted)
			|| app.unit.toLowerCase().includes(wanted))
		const direction = sortDescending ? -1 : 1
		return found.sort((first, second) => {
			const a = first[sortKey]
			const b = second[sortKey]
			const order = sortKey === "name" ? a.localeCompare(b) : a - b
			return order !== 0 ? order * direction : first.name.localeCompare(second.name)
		})
	}

	// The rows change in place, so the list keeps its scroll place while the numbers update every second
	onAppsChanged: listHover.hovered ? updateInOrder() : updateSorted()

	function updateSorted() {
		apps.forEach((app, index) => {
			if (index < rows.count)
				rows.set(index, app)
			else
				rows.append(app)
		})
		if (rows.count > apps.length)
			rows.remove(apps.length, rows.count - apps.length)
	}

	// While the pointer is over the list its rows stay where they are, so the one about to be clicked does not move
	// Only the numbers change, a closed app leaves and a new one joins at the end
	function updateInOrder() {
		const byUnit = {}
		apps.forEach(app => byUnit[app.unit] = app)
		for (let index = rows.count - 1; index >= 0; index--) {
			const app = byUnit[rows.get(index).unit]
			if (app) {
				rows.set(index, app)
				delete byUnit[app.unit]
			} else {
				rows.remove(index)
			}
		}
		apps.filter(app => byUnit[app.unit]).forEach(app => rows.append(app))
	}

	ListModel { id: rows }

	// A second click on the same heading turns the order around, names start from A and numbers from the largest
	function sortBy(key) {
		if (key === sortKey) {
			sortDescending = !sortDescending
			return
		}
		sortKey = key
		sortDescending = key !== "name"
	}

	// A cell turns yellow when an app takes 70 % of what the machine has, and red from 90 %, like a heat map
	function heat(fraction) {
		if (fraction >= 0.9)
			return Qt.rgba(Theme.dangerFill.r, Theme.dangerFill.g, Theme.dangerFill.b, 0.45)
		if (fraction >= 0.7)
			return Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.22)
		return "transparent"
	}

	// The resource apps waited for longest over the last 10 seconds, the kernel's own measure of a slowdown
	readonly property string waitingWords: {
		const waiting = report ? report.waiting : null
		if (!waiting)
			return ""
		const names = { "cpu": "the processor", "memory": "memory", "io": "the disk" }
		const worst = Object.keys(names).reduce((found, key) => waiting[key] > waiting[found] ? key : found, "cpu")
		if (waiting[worst] < 10)
			return "Running smoothly."
		return "Apps are waiting for " + names[worst] + " " + Math.round(waiting[worst]) + " % of the time."
	}
	readonly property real graphicsMemory: gpus.reduce((total, card) => total + card.memoryTotal, 0)

	function speed(bytes) {
		return Theme.size(Math.round(bytes)) + "/s"
	}

	function percent(value) {
		return value === null || value === undefined ? "–" : Math.round(value) + " %"
	}

	title: "Performance"
	guideTopic: "performance"
	subtitle: waitingWords || "Right now, updated every second."
	busy: !report
	empty: !report
	busyText: "Measuring"

	Component.onCompleted: center.watchPerformance(true)
	Component.onDestruction: center.watchPerformance(false)

	ColumnLayout {
		anchors.fill: parent
		spacing: 16

		// Four tiles side by side on a wide window, two by two on a narrower one, so no text gets cut short
		GridLayout {
			id: tiles
			Layout.fillWidth: true
			// The tiles fill their row's height, which must not pass on to the page and stretch them
			Layout.fillHeight: false
			Layout.rightMargin: 16
			columns: width >= 1100 ? 4 : 2
			columnSpacing: 16
			rowSpacing: 16

			// The processor, all cores together and each core as its own small bar
			Tile {
				label: "Processor"
				value: page.percent(page.report ? page.report.cpu : null)

				Meter {
					Layout.fillWidth: true
					fraction: page.report ? page.report.cpu / 100 : 0
				}

				GridLayout {
					Layout.fillWidth: true
					Layout.topMargin: 6
					columns: 12
					columnSpacing: 4
					rowSpacing: 4

					Repeater {
						// A count rather than the list itself, so each update keeps the bars and they slide to the new value
						model: page.report ? page.report.cores.length : 0

						delegate: Rectangle {
							required property int index
							readonly property real modelData: page.report ? page.report.cores[index] || 0 : 0
							Layout.fillWidth: true
							implicitHeight: 16
							radius: 3
							color: Theme.raised

							Rectangle {
								anchors.bottom: parent.bottom
								width: parent.width
								height: parent.height * Math.min(1, modelData / 100)
								radius: 3
								color: modelData > 90 ? Theme.warning : Theme.accent
								Behavior on height { NumberAnimation { duration: Theme.calm; easing.type: Theme.easing } }
							}
						}
					}
				}
			}

			Tile {
				label: "Memory"
				value: page.report ? Theme.size(page.report.memoryUsed) + " of " + Theme.size(page.report.memoryTotal) : ""

				Meter {
					Layout.fillWidth: true
					fraction: page.report ? page.report.memoryUsed / page.report.memoryTotal : 0
				}

				Text {
					Layout.fillWidth: true
					visible: !!page.report && page.report.swapUsed > 0
					text: page.report ? Theme.size(page.report.swapUsed) + " moved to the disk" : ""
					color: Theme.muted
					elide: Text.ElideRight
				}
			}

			// How fast the disks and the network move data right now
			Tile {
				label: "Disk and network"
				value: ""

				// Each measure on its own row with its speed at the right edge, so the numbers line up and never wrap
				GridLayout {
					Layout.fillWidth: true
					columns: 2
					columnSpacing: 12
					rowSpacing: 4

					Repeater {
						model: ["Disk read", "Disk written", "Network in", "Network out"]

						delegate: Text {
							required property string modelData
							required property int index
							Layout.row: index
							Layout.column: 0
							text: modelData
							color: Theme.muted
						}
					}

					Repeater {
						model: page.report ? [page.report.diskRead, page.report.diskWrite, page.report.received,
							page.report.sent] : []

						delegate: Text {
							required property real modelData
							required property int index
							Layout.row: index
							Layout.column: 1
							Layout.fillWidth: true
							horizontalAlignment: Text.AlignRight
							text: page.speed(modelData)
							color: Theme.text
						}
					}
				}
			}

			Repeater {
				// A count again, so a card's tile and its bar stay between updates
				model: page.gpus.length

				delegate: Tile {
					required property int index
					readonly property var modelData: page.gpus[index] || {}
					label: modelData.name
					value: page.percent(modelData.usage)

					Meter {
						Layout.fillWidth: true
						fraction: (modelData.usage || 0) / 100
					}

					Text {
						Layout.fillWidth: true
						text: Theme.size(modelData.memoryUsed) + " of " + Theme.size(modelData.memoryTotal) + " memory"
						color: Theme.muted
						elide: Text.ElideRight
					}

					Text {
						Layout.fillWidth: true
						text: [modelData.temperature !== null ? Math.round(modelData.temperature) + " °C" : "",
							modelData.power !== null ? Math.round(modelData.power) + " W" : "",
							modelData.clock !== null ? Math.round(modelData.clock) + " MHz" : ""
						].filter(part => part !== "").join("  ·  ")
						color: Theme.muted
						elide: Text.ElideRight
					}
				}
			}
		}

		GeckoSearchField {
			id: search
			Layout.fillWidth: true
			Layout.rightMargin: 16
			placeholderText: "Search running apps"
			Accessible.name: "Search running apps"
		}

		// Every running app and what it takes of the whole machine, each heading sorts the list by its column
		RowLayout {
			Layout.fillWidth: true
			Layout.leftMargin: 20
			Layout.rightMargin: 36
			spacing: 16

			Repeater {
				model: page.columns

				delegate: AbstractButton {
					id: heading
					required property var modelData
					required property int index
					readonly property bool sorted: page.sortKey === modelData.key
					Layout.fillWidth: index === 0
					Layout.preferredWidth: index === 0 ? -1 : 130
					implicitHeight: 32
					hoverEnabled: true
					Accessible.name: "Sort by " + modelData.title
					onClicked: page.sortBy(modelData.key)

					contentItem: Text {
						// Lines up with the coloured cells below it
						rightPadding: heading.index === 0 ? 0 : 10
						horizontalAlignment: heading.index === 0 ? Text.AlignLeft : Text.AlignRight
						verticalAlignment: Text.AlignVCenter
						text: heading.modelData.title + (heading.sorted ? (page.sortDescending ? "  ▼" : "  ▲") : "")
						color: heading.sorted ? Theme.accent : heading.hovered ? Theme.text : Theme.muted
						font.weight: heading.sorted ? Font.DemiBold : Font.Normal
						elide: Text.ElideRight
					}

					background: Item {}
				}
			}
		}

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			spacing: 4
			model: rows

			HoverHandler {
				id: listHover
				// Leaving the list puts it back in order at once
				onHoveredChanged: {
					if (!hovered)
						page.updateSorted()
				}
			}

			delegate: Rectangle {
				id: row
				required property var model
				readonly property var modelData: model
				readonly property bool canEnd: modelData.kind !== "system"
				width: list.cardWidth
				implicitHeight: 48
				radius: 10
				color: hover.hovered ? Theme.raised : Theme.rail

				HoverHandler { id: hover }

				RowLayout {
					anchors.fill: parent
					anchors.leftMargin: 20
					anchors.rightMargin: 20
					spacing: 16

					// Each cell with what it takes of the whole machine, which sets its colour
					Repeater {
						model: [
							[row.modelData.name, true, 0],
							[page.percent(row.modelData.cpu), false, row.modelData.cpu / 100],
							[row.modelData.gpu > 0 ? page.percent(row.modelData.gpu) : "–", false, row.modelData.gpu / 100],
							[row.modelData.gpuMemory > 0 ? Theme.size(row.modelData.gpuMemory) : "–", false,
								page.graphicsMemory > 0 ? row.modelData.gpuMemory / page.graphicsMemory : 0],
							[Theme.size(row.modelData.memory), false,
								page.report ? row.modelData.memory / page.report.memoryTotal : 0]
						]

						delegate: Text {
							required property var modelData
							Layout.fillWidth: modelData[1]
							Layout.preferredWidth: modelData[1] ? -1 : 130
							Layout.fillHeight: true
							horizontalAlignment: modelData[1] ? Text.AlignLeft : Text.AlignRight
							verticalAlignment: Text.AlignVCenter
							rightPadding: modelData[1] ? 0 : 10

							Rectangle {
								anchors.fill: parent
								anchors.topMargin: 6
								anchors.bottomMargin: 6
								z: -1
								radius: 6
								color: page.heat(parent.modelData[2])
							}
							text: modelData[0]
							// Apps stand out, background services and the system read quieter
							color: modelData[1] && row.modelData.kind === "app" ? Theme.textStrong
								: modelData[1] ? Theme.muted : Theme.text
							elide: Text.ElideRight
							// The numbers make room for the buttons while the row is hovered
							opacity: !modelData[1] && hover.hovered && row.canEnd ? 0 : 1
						}
					}
				}

				// Hovering one of your apps offers to end it, the system's own services are left alone
				Row {
					anchors.right: parent.right
					anchors.rightMargin: 6
					anchors.verticalCenter: parent.verticalCenter
					spacing: 6
					visible: hover.hovered && row.canEnd

					GeckoButton {
						height: 36
						text: "End"
						onClicked: center.endApp(row.modelData.unit, false)
					}

					GeckoButton {
						height: 36
						danger: true
						text: "Force end"
						onClicked: {
							forceEnd.unit = row.modelData.unit
							forceEnd.name = row.modelData.name
							forceEnd.open()
						}
					}
				}
			}
		}
	}

	QuestionDialog {
		id: forceEnd

		property string unit
		property string name

		question: "Force " + name + " to end?"
		explanation: "It closes at once without a chance to save. Use End first, and this only when it does not respond."
		confirmText: "Force end"
		danger: true
		onConfirmed: center.endApp(unit, true)
	}

	// One measured part of the machine, its name, the number that matters and its bars
	component Tile: Rectangle {
		id: tile

		property string label
		property string value
		default property alias content: inside.data

		Layout.fillWidth: true
		// Every tile in the row is as tall as the tallest one
		Layout.fillHeight: true
		implicitHeight: inside.implicitHeight + 32
		radius: 16
		color: "#142019"
		border.color: Theme.lineStrong

		ColumnLayout {
			id: inside
			anchors.left: parent.left
			anchors.right: parent.right
			anchors.top: parent.top
			anchors.margins: 16
			spacing: 6

			Text {
				Layout.fillWidth: true
				text: tile.label
				color: Theme.muted
				elide: Text.ElideRight
			}

			Text {
				Layout.fillWidth: true
				visible: tile.value !== ""
				text: tile.value
				color: Theme.textStrong
				font.pixelSize: 22
				font.weight: Font.DemiBold
				elide: Text.ElideRight
			}
		}
	}
}
