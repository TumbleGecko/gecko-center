// One release or changelog entry, a short heading and the text below it
import QtQuick
import GeckoUi
import QtQuick.Layouts

ColumnLayout {
	property alias heading: title.text
	property alias body: text.text

	Layout.fillWidth: true
	spacing: 4

	Text {
		id: title
		Layout.fillWidth: true
		color: Theme.textStrong
		font.weight: Font.DemiBold
		elide: Text.ElideRight
	}

	Text {
		id: text
		Layout.fillWidth: true
		color: Theme.text
		wrapMode: Text.Wrap
		lineHeight: 1.25
	}
}
