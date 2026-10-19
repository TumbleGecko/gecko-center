// Turns the mouse's back and forward side buttons into back and forward, wherever the pointer is in the window
// The app attaches gecko_ui.mouse_navigation.MouseNavigation, which sees the buttons before any item can take them
import QtQuick

QtObject {
	id: buttons

	signal back()
	signal forward()

	readonly property Connections link: Connections {
		target: geckoMouseNavigation

		function onBack() {
			buttons.back()
		}

		function onForward() {
			buttons.forward()
		}
	}
}
