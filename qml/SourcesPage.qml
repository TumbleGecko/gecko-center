// The software sources, what each one is for, who builds it and a switch to turn it on or off
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	readonly property var report: center.info.sources || null
	readonly property var sources: report && report.sources ? report.sources : []

	function setEnabled(source, enabled) {
		if (enabled) {
			window.runSystem("sources", "source-on", source.alias, "Turning on " + source.name, "Turn on")
			return
		}
		confirm.source = source
		confirm.open()
	}

	title: "Sources"
	scroller: list
	guideTopic: "sources"
	subtitle: "Where software is downloaded from."
	busy: center.reading.includes("sources")
	empty: sources.length === 0

	Component.onCompleted: center.read("sources")

	CardList {
		id: list
		anchors.fill: parent
		model: page.sources

		delegate: StatusCard {
			id: card
			required property var modelData
			width: list.cardWidth
			status: modelData.risks.length > 0 ? "warning"
				: modelData.kind === "openSUSE" ? "good" : modelData.enabled ? "note" : ""
			label: modelData.kind === "openSUSE" ? "" : modelData.builder
			heading: modelData.name
			details: [modelData.about || modelData.url].concat(modelData.risks).join("\n")

			GeckoButton {
				text: "More info"
				onClicked: window.openDetail({ key: "source-" + card.modelData.alias, sourceAlias: card.modelData.alias })
			}

			Toggle {
				checked: card.modelData.enabled
				enabled: !bridge.busy
				Accessible.name: (card.modelData.enabled ? "Turn off " : "Turn on ") + card.modelData.name
				// The switch follows the source list, a cancelled change leaves it where it was
				onToggled: {
					const wanted = checked
					checked = Qt.binding(() => card.modelData.enabled)
					page.setEnabled(card.modelData, wanted)
				}
			}
		}
	}

	QuestionDialog {
		id: confirm

		property var source: null

		question: "Turn off " + (source ? source.name : "") + "?"
		explanation: source && source.kind === "openSUSE"
			? "The system gets its packages and updates from openSUSE's sources. Without this one updates may fail."
			: "Packages already installed from it stay, but they no longer get updates from it."
		confirmText: "Turn off"
		danger: !!source && source.kind === "openSUSE"
		onConfirmed: window.runSystem("sources", "source-off", source.alias, "Turning off " + source.name, "Turn off")
	}
}
