// One snapshot in full, the Tumbleweed release and kernel it holds, how long it is kept and what its change did
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

GeckoPage {
	id: page

	property int number
	readonly property var snapshot: ((center.info.snapshots || {}).snapshots || [])
		.find(item => item.number === number) || null
	readonly property bool canRollBack: !!snapshot && !snapshot.running && !snapshot.next

	readonly property var machine: (center.info.health || {}).machine || {}
	// A version fact names the running version too, so a different one shows how it differs
	readonly property var facts: snapshot ? [
		["Tumbleweed", snapshot.release, machine.snapshot || ""],
		["Linux Kernel", snapshot.kernel, machine.kernel || ""], ["Kept", snapshot.kept, ""],
		["Change", snapshot.about, ""]
	].filter(fact => fact[1] !== "") : []

	// The search matches the package name, the list shows a heading where the kind of change shifts
	readonly property var changes: {
		const wanted = search.text.trim().toLowerCase()
		const order = { "Updated": 0, "Added": 1, "Removed": 2 }
		return (snapshot ? snapshot.changes : []).filter(change => change.name.toLowerCase().includes(wanted))
			.sort((first, second) => order[first.change] - order[second.change] || first.name.localeCompare(second.name))
	}

	// The full title is too long for the heading, so the heading names the number and the title goes below
	title: snapshot ? "Snapshot " + snapshot.number : ""
	scroller: list
	subtitle: snapshot ? snapshot.title : ""
	empty: !snapshot

	actions: [
		GeckoButton {
			text: "‹  Back"
			onClicked: window.goBack()
		},
		Item { Layout.fillWidth: true },
		GeckoButton {
			visible: page.canRollBack
			enabled: !bridge.busy
			primary: true
			text: "Roll back"
			onClicked: rollback.ask(page.snapshot)
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

					VersionChange {
						from: modelData[2]
						to: modelData[1]
						template: "%to  (Different than your %from)"
						color: Theme.text
					}
				}
			}
		}

		GeckoSearchField {
			id: search
			visible: !!page.snapshot && page.snapshot.changes.length > 0
			Layout.fillWidth: true
			Layout.topMargin: 8
			Layout.rightMargin: 16
			placeholderText: "Search the changed packages"
			Accessible.name: "Search the changed packages"
		}

		CardList {
			id: list
			Layout.fillWidth: true
			Layout.fillHeight: true
			spacing: 4
			model: page.changes
			section.property: "change"

			section.delegate: Text {
				required property string section
				width: list.cardWidth
				topPadding: 18
				bottomPadding: 8
				leftPadding: 4
				text: section
				color: Theme.muted
				font.weight: Font.DemiBold
			}

			delegate: Rectangle {
				id: row
				required property var modelData
				width: list.cardWidth
				implicitHeight: 48
				radius: 10
				color: Theme.rail

				RowLayout {
					anchors.fill: parent
					anchors.leftMargin: 20
					anchors.rightMargin: 20
					spacing: 16

					Text {
						Layout.fillWidth: true
						text: row.modelData.name
						color: Theme.textStrong
						elide: Text.ElideRight
					}

					VersionChange {
						from: row.modelData.from
						to: row.modelData.to
						elide: Text.ElideLeft
					}
				}
			}
		}
	}

	RollbackDialog { id: rollback }
}
