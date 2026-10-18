// One source in full, where it is, who builds it, what could go wrong and the installed software it gave
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property string sourceAlias
	readonly property var source: ((center.info.sources || {}).sources || [])
		.find(item => item.alias === sourceAlias) || null
	readonly property var report: center.info["source-packages"] || null
	readonly property var given: report ? report.packages[sourceAlias] || [] : []

	readonly property var facts: source ? [
		["Address", source.url], ["Builder", source.builder], ["Turned on", source.enabled ? "Yes" : "No"]
	] : []

	readonly property var packages: {
		const wanted = search.text.trim().toLowerCase()
		return given.filter(item => item.name.toLowerCase().includes(wanted) || item.summary.toLowerCase().includes(wanted))
	}

	title: source ? source.name : ""
	subtitle: source ? source.about : ""
	busy: center.reading.includes("source-packages")
	empty: !source

	// Everything this source gave, as one change the removal dialog can work out and list
	readonly property var software: source ? {
		key: "source-software-" + sourceAlias, kind: "package",
		name: given.length === 1 ? given[0].name : "the " + given.length + " packages from " + source.name,
		packages: given.map(item => item.name)
	} : null

	function removeSoftware() {
		window.withPassword(bridge.changeNeedsPassword(software), "Removing system software needs your password.",
			"Remove", () => {
				removal.plan = null
				removal.open()
				bridge.preview("remove", software)
			})
	}

	Component.onCompleted: center.read("source-packages")
	// A removed source has no page left, so this goes back to the list
	onSourceChanged: if (!source && sourceAlias !== "" && center.info.sources) window.goBack()

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: page.given.length > 0
			enabled: !bridge.busy
			danger: true
			text: "Remove software"
			onClicked: page.removeSoftware()
		},
		GeckoButton {
			visible: !!page.source
			enabled: !bridge.busy
			danger: true
			text: "Remove source"
			onClicked: confirm.open()
		}
	]

	ColumnLayout {
		anchors.fill: parent
		spacing: 16

		Column {
			Layout.fillWidth: true
			spacing: 6

			Repeater {
				model: page.facts

				delegate: Row {
					required property var modelData
					spacing: 20

					Text {
						width: 120
						text: modelData[0]
						color: Theme.muted
					}

					Text {
						text: modelData[1]
						color: Theme.text
					}
				}
			}
		}

		Repeater {
			model: page.source ? page.source.risks : []

			delegate: StatusCard {
				required property string modelData
				Layout.fillWidth: true
				Layout.rightMargin: 16
				status: "warning"
				heading: modelData
			}
		}

		Text {
			visible: !!page.report
			Layout.fillWidth: true
			text: page.given.length === 0 ? "No installed package is from this source."
				: page.given.length === 1 ? "1 installed package is from this source."
				: page.given.length + " installed packages are from this source."
			color: Theme.text
			wrapMode: Text.WordWrap
		}

		GeckoSearchField {
			id: search
			visible: page.given.length > 0
			Layout.fillWidth: true
			Layout.rightMargin: 16
			placeholderText: "Search these packages"
			Accessible.name: "Search these packages"
		}

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			spacing: 4
			model: page.packages

			delegate: PackageRow {
				width: list.cardWidth
			}
		}
	}

	QuestionDialog {
		id: confirm
		question: "Remove " + (page.source ? page.source.name : "") + "?"
		explanation: "Packages already installed from it stay, but they no longer get updates from it."
			+ " Remove software takes them away first."
		confirmText: "Remove"
		danger: true
		onConfirmed: window.runSystem("sources", "source-remove", page.sourceAlias, "Removing " + page.source.name,
			"Remove")
	}

	Connections {
		target: bridge

		function onPreviewReady(plan) {
			removal.plan = plan
		}
	}

	ConfirmDialog {
		id: removal
		entry: page.software
		action: "remove"
		onConfirmed: window.runSystem("source-packages", "packages-remove", page.software.packages.join(" "),
			"Removing " + page.software.name, "Remove")
	}
}
