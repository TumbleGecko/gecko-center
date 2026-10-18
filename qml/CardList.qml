// A scrolling column of cards with the gecko scroll bar and fast wheel, the body of most system pages
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic

ListView {
	id: list

	clip: true
	spacing: 12
	boundsBehavior: Flickable.StopAtBounds
	ScrollBar.vertical: GeckoScrollBar {}
	// Room for the scroll bar beside the cards
	readonly property real cardWidth: width - 16

	FastWheel { flickable: list }
}
