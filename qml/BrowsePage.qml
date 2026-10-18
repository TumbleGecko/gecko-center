// Apps from openSUSE and Flathub to search and browse by group, or the system packages zypper knows
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property bool installedOnly: false
	readonly property string memoryKey: installedOnly ? "installed" : "explore"
	readonly property var memory: window.browseMemory[memoryKey] || {}
	property string source: memory.source || ""
	property string group: memory.group || ""
	readonly property bool packageMode: source === "packages"
	property var packageResults: memory.packageResults || []
	property bool searching: false

	function remember(extra) {
		const updated = Object.assign({}, window.browseMemory)
		updated[memoryKey] = Object.assign({ text: search.text, source: source, group: group,
			packageResults: packageResults, contentY: grid.contentY }, extra || {})
		window.browseMemory = updated
	}

	function applyFilter() {
		if (packageMode) {
			searching = search.text.trim().length >= 2
			typing.restart()
			return
		}
		apps.setFilter(search.text, source, group, installedOnly)
	}

	title: installedOnly ? "Installed" : "Explore"
	guideTopic: "software"
	busy: searching || !window.catalogReady
	subtitle: installedOnly ? "Apps on this computer from openSUSE and Flathub."
		: "Apps from openSUSE and Flathub."

	Component.onCompleted: {
		search.text = memory.text || ""
		applyFilter()
		grid.contentY = memory.contentY || 0
	}
	Component.onDestruction: remember()

	Connections {
		target: bridge

		function onPackagesFound(text, results) {
			if (text !== search.text.trim())
				return
			page.searching = false
			page.packageResults = results
		}
	}

	// zypper search takes a moment, so it waits until typing pauses
	Timer {
		id: typing
		interval: 400
		onTriggered: {
			const text = search.text.trim()
			if (text.length < 2) {
				page.packageResults = []
				return
			}
			page.searching = true
			bridge.searchPackages(text)
		}
	}

	ColumnLayout {
		anchors.fill: parent
		spacing: 16

		GeckoSearchField {
			id: search
			Layout.fillWidth: true
			placeholderText: page.packageMode ? "Search system packages, such as htop or a library" : "Search apps"
			Accessible.name: "Search"
			onTextChanged: page.applyFilter()
		}

		ChipRow {
			Layout.fillWidth: true
			current: page.source
			choices: [
				{ value: "", name: "All apps" }, { value: "openSUSE", name: "openSUSE" },
				{ value: "Flathub", name: "Flathub" }
			].concat(page.installedOnly ? [] : [{ value: "packages", name: "System packages" }])
			onChosen: value => {
				page.source = value
				page.applyFilter()
			}
		}

		ChipRow {
			visible: !page.packageMode
			Layout.fillWidth: true
			current: page.group
			choices: [{ value: "", name: "Every group" }].concat(apps.groups().map(name => ({ value: name, name: name })))
			onChosen: value => {
				page.group = value
				page.applyFilter()
			}
		}

		Item {
			Layout.fillWidth: true
			Layout.fillHeight: true

			GridView {
				id: grid

				readonly property int columns: Math.max(1, Math.floor(width / 330))

				visible: !page.packageMode
				anchors.fill: parent
				clip: true
				model: apps
				cellWidth: Math.floor(width / columns)
				cellHeight: 132
				boundsBehavior: Flickable.StopAtBounds
				ScrollBar.vertical: GeckoScrollBar {}

				FastWheel { flickable: grid }

				delegate: AppCard {
					width: grid.cellWidth - 14
					height: grid.cellHeight - 14
					onOpened: window.openDetail(apps.entry(key, ""))
				}
			}

			ListView {
				id: packageList
				visible: page.packageMode
				anchors.fill: parent
				clip: true
				spacing: 8
				model: page.packageResults
				boundsBehavior: Flickable.StopAtBounds
				ScrollBar.vertical: GeckoScrollBar {}

				FastWheel { flickable: packageList }

				delegate: PackageRow {
					width: packageList.width - 16
				}
			}

			Text {
				anchors.centerIn: parent
				width: parent.width * 0.7
				horizontalAlignment: Text.AlignHCenter
				wrapMode: Text.WordWrap
				color: Theme.muted
				font.pixelSize: 18
				visible: text !== ""
				text: {
					if (page.packageMode) {
						if (page.searching)
							return "Searching…"
						if (search.text.trim().length < 2)
							return "Type a package name to search the system packages in your software sources."
						return page.packageResults.length === 0 ? "No package matches." : ""
					}
					if (!window.catalogReady)
						return "Reading the app catalogs…"
					return apps.count === 0 ? "No app matches." : ""
				}
			}
		}
	}
}
