// One package from zypper search, its name, one line about it and whether it is installed
import QtQuick

ListRow {
	required property var modelData

	name: modelData.name
	summary: modelData.summary
	note: modelData.installed ? "✓ Installed" : ""
	onClicked: window.openPackagePage(modelData.name)
}
