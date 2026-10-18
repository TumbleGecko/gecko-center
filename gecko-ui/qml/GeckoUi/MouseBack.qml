// Turns the mouse's back and forward side buttons into back and forward, wherever the pointer is in the window
import QtQuick

TapHandler {
	signal back()
	signal forward()

	acceptedButtons: Qt.BackButton | Qt.ForwardButton
	// Watch the buttons without taking the press from anything under the pointer
	gesturePolicy: TapHandler.DragThreshold
	grabPermissions: PointerHandler.TakeOverForbidden
	onTapped: (point, button) => button === Qt.BackButton ? back() : forward()
}
