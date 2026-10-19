// One app, package or package file, what it is, where it comes from, and the button that installs or removes it
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property var entry
	readonly property bool installed: entry && entry.installation !== undefined && entry.installation !== ""
	readonly property bool ownJob: entry && window.jobOwner === entry.key
	readonly property bool running: ownJob && bridge.busy
	readonly property bool isFlatpak: entry && (entry.source === "Flathub" || entry.format === "flatpakref")

	// Plain words about a file that did not come from one of your software sources
	readonly property string trustText: {
		if (!entry || entry.kind !== "file")
			return ""
		return ({
			"signed": "This package file is signed by a key your computer already trusts.",
			"unknown-key": "This package file is signed with a key your computer does not know. "
				+ "Install it only if you trust where you got it.",
			"unsigned": "This package file is not signed. Install it only if you trust where you got it.",
			"flatpak": "This app comes from " + (entry.origin || "its own source") + ", not from Flathub. "
				+ "Install it only if you trust that source."
		})[entry.trust] || ""
	}

	// The sources this app comes from, shown as a choice only when there is more than one
	readonly property var choices: entry && entry.choices ? entry.choices : []

	// The lines zypper gives every package, shown empty while it reads so nothing below moves when they fill in
	readonly property var packageFacts: ["From", "Version", "Made by", "Size", "Installed"]

	readonly property var facts: {
		if (!entry)
			return []
		const where = isFlatpak ? (entry.installation === "user" ? ", for you" : ", for everyone") : ""
		const known = [
			["From", choices.length > 1 ? "" : entry.source || ""], ["Version", entry.version || ""],
			["Made by", entry.developer || ""],
			["License", entry.license || ""], ["Size", entry.size || ""],
			["Installed", installed ? "✓ Yes" + where : entry.problem || entry.loading ? "" : "No"]
		]
		if (entry.loading)
			return known.filter(fact => packageFacts.indexOf(fact[0]) >= 0)
		return known.filter(fact => fact[1] !== "")
	}

	// The technical tab reads a package or Flatpak id, which a package file does not have
	readonly property bool hasTechnical: !!entry && (entry.kind === "app" || entry.kind === "package")
		&& !!entry.package
	readonly property bool showsTechnical: hasTechnical && tabs.currentName === "Technical"
	property var technical: null
	property string technicalKey: ""

	// Each line of the technical tab, its facts first, then what needs it and what it needs
	readonly property var technicalRows: {
		if (!technical)
			return []
		const rows = technical.facts.map(fact => ({ kind: "fact", name: fact[0], value: fact[1] }))
		if (technical.permissions.length > 0) {
			rows.push({ kind: "header", name: "Sandbox", help: "What the app may reach outside its own sandbox." })
			technical.permissions.forEach(permission => rows.push({ kind: "fact", name: permission[0],
				value: permission[1] }))
		}
		if (!isFlatpak && technical.installed) {
			rows.push({ kind: "header", name: "Needed by  ·  " + technical.neededBy.length,
				help: "Installed packages that cannot work without this one. Removing it removes these too." })
			technical.neededBy.forEach(item => rows.push({ kind: "package", name: item.name, summary: item.summary }))
			if (technical.neededBy.length === 0)
				rows.push({ kind: "note", name: "No installed package needs it." })
		}
		if (!isFlatpak) {
			rows.push({ kind: "header", name: "Needs  ·  " + technical.needs.length,
				help: "Packages this one cannot work without. Installing it brings these along." })
			technical.needs.forEach(item => rows.push({ kind: "package", name: item.name, summary: item.summary }))
		}
		return rows
	}

	function readTechnical() {
		if (!showsTechnical || technicalKey === entry.key)
			return
		technical = null
		technicalKey = entry.key
		bridge.readTechnical(entry)
	}

	onShowsTechnicalChanged: readTechnical()

	// The update the last check found for this app, which turns the update tab on and tells it what to read
	readonly property var pendingUpdate: {
		if (!hasTechnical)
			return null
		const check = bridge.updates
		if (isFlatpak) {
			const found = (check.flatpak || []).find(update => update.id === entry.package)
			return found ? { kind: "flatpak", id: found.id, installation: found.installation, version: found.version,
				oldVersion: "", flatpak: found } : null
		}
		const sections = check.system && check.system.sections ? check.system.sections : {}
		for (const kind of ["upgrade", "downgrade", "change-vendor", "change-arch"]) {
			const found = (sections[kind] || []).find(update => update.name === entry.package)
			if (found)
				return { kind: "system", name: found.name, version: found.version, oldVersion: found.oldVersion,
					repository: found.repository }
		}
		return null
	}
	readonly property bool showsUpdate: !!pendingUpdate && tabs.currentName === "Update"
	property var updateNotes: null
	property string updateNotesKey: ""

	function readUpdateNotes() {
		if (!showsUpdate || updateNotesKey === entry.key)
			return
		updateNotes = null
		updateNotesKey = entry.key
		bridge.readUpdateNotes(entry.key, pendingUpdate, entry.releases || [])
	}

	onShowsUpdateChanged: readUpdateNotes()
	// The key whose starting tab was chosen, so reading the entry again does not move away from the tab you picked
	property string startTabKey: ""

	function chooseStartTab() {
		if (!entry || !entry.startTab || entry.key === startTabKey)
			return
		startTabKey = entry.key
		tabs.current = Math.max(tabs.names.indexOf(entry.startTab), 0)
	}

	Component.onCompleted: chooseStartTab()
	onEntryChanged: {
		chooseStartTab()
		readTechnical()
		readUpdateNotes()
	}

	// A Flatpak app updates on its own, the system only updates as a whole on the Updates page
	function updateFlatpak() {
		window.startJob(entry.key, "Updating " + entry.name)
		bridge.updateFlatpak(pendingUpdate.flatpak)
	}

	function change(action) {
		const words = action === "install" ? "Install" : "Remove"
		window.withPassword(bridge.changeNeedsPassword(entry),
			words + "ing system software needs your password.", words, () => {
				if (action === "install" && page.isFlatpak) {
					run(action)
					return
				}
				confirm.action = action
				confirm.plan = null
				confirm.open()
				bridge.preview(action, entry)
			})
	}

	function run(action) {
		window.startJob(entry.key, (action === "install" ? "Installing " : "Removing ") + entry.name)
		if (action === "install")
			bridge.install(entry)
		else
			bridge.remove(entry)
	}

	// The page shows the entry as it is after the change, read again from its source
	function reload() {
		technicalKey = ""
		updateNotesKey = ""
		if (entry.kind === "app")
			window.detail = apps.entry(entry.key, entry.source)
		else if (entry.kind === "package")
			bridge.openPackage(entry.package)
		else if (entry.format === "rpm")
			bridge.openTarget(entry.path)
	}

	title: entry ? entry.name || entry.path || "" : ""
	titleNote: entry ? entry.summary || "" : ""
	busy: !!entry && !!entry.loading

	Connections {
		target: bridge

		function onPreviewReady(plan) {
			confirm.plan = plan
		}

		function onTechnicalReady(key, found) {
			if (page.entry && key === page.entry.key)
				page.technical = found
		}

		function onUpdateNotesReady(key, notes) {
			if (page.entry && key === page.entry.key)
				page.updateNotes = notes
		}

		function onJobFinished(succeeded, reboot, message) {
			if (page.ownJob)
				page.reload()
		}
	}

	ConfirmDialog {
		id: confirm
		entry: page.entry
		onConfirmed: page.run(action)
	}

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: !!page.entry && !!page.entry.homepage
			text: "Website"
			onClicked: Qt.openUrlExternally(page.entry.homepage)
		},
		GeckoButton {
			visible: page.installed && bridge.canRun(page.entry)
			text: "Run"
			onClicked: bridge.runApp(page.entry)
		},
		GeckoButton {
			visible: page.installed && page.entry.kind !== "file"
			enabled: !bridge.busy
			danger: true
			text: "Remove"
			onClicked: page.change("remove")
		},
		GeckoButton {
			visible: !page.installed && page.entry && !page.entry.problem && !page.entry.loading
			enabled: !bridge.busy
			primary: true
			text: "Install"
			onClicked: page.change("install")
		}
	]

	ColumnLayout {
		anchors.fill: parent
		spacing: 20

		RowLayout {
			Layout.fillWidth: true
			spacing: 24

			AppIcon {
				Layout.alignment: Qt.AlignTop
				size: 96
				source: page.entry ? page.entry.icon || "" : ""
				name: page.entry ? page.entry.name || "" : ""
			}

			Column {
				Layout.fillWidth: true
				Layout.alignment: Qt.AlignTop
				spacing: 6

				Repeater {
					model: page.facts

					delegate: Row {
						required property var modelData
						spacing: 20

						Text {
							width: 100
							text: modelData[0]
							color: Theme.muted
						}

						Text {
							text: modelData[1]
							color: Theme.text
						}
					}
				}

				Row {
					visible: page.choices.length > 1
					spacing: 20

					Text {
						width: 100
						anchors.verticalCenter: parent.verticalCenter
						text: "Source"
						color: Theme.muted
					}

					Row {
						spacing: 8

						Repeater {
							model: page.choices

							delegate: Chip {
								required property var modelData
								text: modelData.source + (modelData.installed ? "  ·  installed" : "")
								checked: page.entry.source === modelData.source
								Accessible.name: "Use " + modelData.source
								onClicked: window.detail = apps.entry(page.entry.key, modelData.source)
							}
						}
					}
				}
			}
		}

		Rectangle {
			visible: page.trustText !== "" || !!(page.entry && page.entry.problem)
			Layout.fillWidth: true
			implicitHeight: trust.implicitHeight + 36
			radius: 14
			color: page.entry && page.entry.trust === "signed" ? Theme.doneFill : Theme.warningFill
			border.color: page.entry && page.entry.trust === "signed" ? Theme.lineStrong : Theme.warningLine

			Text {
				id: trust
				anchors.fill: parent
				anchors.margins: 18
				text: Theme.lines(page.entry && page.entry.problem ? page.entry.problem : page.trustText)
				color: page.entry && page.entry.trust === "signed" ? Theme.text : Theme.warning
				wrapMode: Text.WordWrap
				lineHeight: 1.25
			}
		}

		ProgressPanel {
			visible: page.ownJob && (page.running || !window.jobResult.succeeded)
			Layout.fillWidth: true
			Layout.preferredHeight: 300
		}

		Text {
			visible: page.ownJob && !page.running && window.jobResult !== null && window.jobResult.succeeded
			Layout.fillWidth: true
			text: "✓  Done."
			color: Theme.accentHover
			font.pixelSize: 20
			font.weight: Font.DemiBold
		}

		PageTabs {
			id: tabs
			visible: page.hasTechnical
			names: ["About", "Update", "Technical"]
			disabledNames: page.pendingUpdate ? [] : ["Update"]
		}

		// The tabs share one area that keeps its size while a tab is still reading
		Item {
			Layout.fillWidth: true
			Layout.fillHeight: true

			Spinner {
				anchors.horizontalCenter: parent.horizontalCenter
				y: 40
				running: (page.showsTechnical && !page.technical) || (page.showsUpdate && !page.updateNotes)
			}

			ListView {
				id: technicalList
				visible: page.showsTechnical && !!page.technical
				anchors.fill: parent
				clip: true
				model: page.technicalRows
				boundsBehavior: Flickable.StopAtBounds
				ScrollBar.vertical: GeckoScrollBar {}

				FastWheel { flickable: technicalList }

				delegate: AbstractButton {
					id: row

					required property var modelData
					readonly property bool isPackage: modelData.kind === "package"
					readonly property bool isHeader: modelData.kind === "header"

					width: technicalList.width - 16
					height: isHeader ? 52 : modelData.kind === "fact" ? factValue.implicitHeight + 10 : 36
					hoverEnabled: isPackage
					focusPolicy: isPackage ? Qt.StrongFocus : Qt.NoFocus
					Accessible.name: modelData.name
					onClicked: {
						if (isPackage)
							window.openPackage("openSUSE", modelData.name)
					}

					background: Rectangle {
						visible: row.isPackage
						radius: 8
						color: row.down ? "#101712" : row.hovered ? "#172219" : "transparent"
						Behavior on color { ColorAnimation { duration: Theme.quick } }
					}

					RowLayout {
						visible: row.modelData.kind !== "fact"
						anchors.left: parent.left
						anchors.right: parent.right
						anchors.leftMargin: 12
						anchors.rightMargin: 12
						anchors.bottom: parent.bottom
						anchors.bottomMargin: row.isHeader ? 6 : 4
						spacing: 12

						Text {
							Layout.maximumWidth: row.isPackage ? parent.width * 0.45 : Number.POSITIVE_INFINITY
							text: row.modelData.name
							color: row.isHeader ? Theme.accentHover : row.isPackage ? Theme.text : Theme.muted
							font.weight: row.isHeader ? Font.DemiBold : Font.Normal
							elide: Text.ElideRight
						}

						Text {
							visible: row.isPackage
							Layout.fillWidth: true
							text: row.modelData.summary || ""
							color: Theme.muted
							font.pixelSize: Theme.smallSize
							elide: Text.ElideRight
						}

						HelpMark {
							visible: row.isHeader
							text: row.modelData.help || ""
						}

						Item {
							visible: !row.isPackage
							Layout.fillWidth: true
						}

						MoreMark {
							visible: row.isPackage
							font.pixelSize: 22
							lit: row.hovered
						}
					}

					Row {
						visible: row.modelData.kind === "fact"
						x: 12
						y: 5
						spacing: 20

						Text {
							width: 140
							text: row.modelData.name
							color: Theme.muted
						}

						Text {
							id: factValue
							width: row.width - 172
							text: row.modelData.value || ""
							color: Theme.text
							wrapMode: Text.Wrap
						}
					}
				}
			}

			Flickable {
				id: updateView
				visible: page.showsUpdate && !!page.updateNotes
				anchors.fill: parent
				clip: true
				contentHeight: updateColumn.implicitHeight + 12
				boundsBehavior: Flickable.StopAtBounds
				ScrollBar.vertical: GeckoScrollBar {}

				FastWheel { flickable: updateView }

				ColumnLayout {
					id: updateColumn
					y: 12
					width: updateView.width - 20
					spacing: 12

					RowLayout {
						Layout.fillWidth: true
						spacing: 16

						VersionChange {
							Layout.fillWidth: true
							from: page.pendingUpdate ? page.pendingUpdate.oldVersion || "" : ""
							to: page.pendingUpdate ? page.pendingUpdate.version || "" : ""
							color: Theme.text
						}

						GeckoButton {
							visible: page.isFlatpak
							primary: true
							enabled: !bridge.busy && !bridge.checking
							text: "Update"
							onClicked: page.updateFlatpak()
						}

						GeckoButton {
							visible: !page.isFlatpak
							text: "Go to Updates"
							onClicked: window.showPage("updates")
						}
					}

					Text {
						visible: text !== ""
						Layout.fillWidth: true
						text: page.updateNotes ? page.updateNotes.subject || page.updateNotes.problem || "" : ""
						color: Theme.muted
						wrapMode: Text.WordWrap
					}

					Text {
						visible: !!page.updateNotes && page.updateNotes.rebuild
						Layout.fillWidth: true
						text: Theme.lines("The packagers listed no changes for this version. "
							+ "It is most likely rebuilt against newer parts of the system.")
						color: Theme.muted
						wrapMode: Text.WordWrap
					}

					NotesHeading {
						visible: !!page.updateNotes && page.updateNotes.releases.length > 0
						text: "Release notes"
						help: "What the makers of the app say is new."
					}

					Repeater {
						model: page.updateNotes ? page.updateNotes.releases : []

						delegate: NotesEntry {
							required property var modelData
							heading: "Version " + modelData.version + (modelData.date ? "  ·  " + modelData.date : "")
							body: modelData.notes
						}
					}

					NotesHeading {
						visible: !!page.updateNotes && page.updateNotes.changes.length > 0
						text: "Changelog"
						help: "What the openSUSE packagers changed in the package, newest first."
					}

					Repeater {
						model: page.updateNotes ? page.updateNotes.changes : []

						delegate: NotesEntry {
							required property var modelData
							heading: modelData.date + "  ·  " + modelData.author
							body: modelData.text
						}
					}
				}
			}

			Flickable {
				id: about
				visible: !page.showsTechnical && !page.showsUpdate
				anchors.fill: parent
				clip: true
				contentHeight: description.implicitHeight
				boundsBehavior: Flickable.StopAtBounds
				ScrollBar.vertical: GeckoScrollBar {}

				FastWheel { flickable: about }

				Text {
					id: description
					width: about.width - 20
					text: page.entry ? page.entry.description || "" : ""
					color: Theme.text
					wrapMode: Text.WordWrap
					lineHeight: 1.3
				}
			}
		}
	}
}
