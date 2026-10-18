// A heading over a group of notes, with a question mark that explains where the notes come from
import QtQuick
import GeckoUi
import QtQuick.Layouts

RowLayout {
	property alias text: label.text
	property alias help: mark.text

	Layout.topMargin: 10
	spacing: 12

	Text {
		id: label
		color: Theme.accentHover
		font.weight: Font.DemiBold
	}

	HelpMark {
		id: mark
	}
}
