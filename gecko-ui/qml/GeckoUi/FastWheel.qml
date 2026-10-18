// Scrolls a list a comfortable distance per wheel step and glides there, Qt's own step is a few pixels
import QtQuick

WheelHandler {
	id: wheel

	required property Flickable flickable
	// Pixels per wheel notch, one notch is 120 units of angleDelta
	property real step: 120
	// How long one notch takes to glide, in milliseconds
	property int glideDuration: 220

	// Keeps a position inside the list, which starts at originY rather than 0 in some views
	function clamped(contentY) {
		const first = flickable.originY - flickable.topMargin
		const last = flickable.originY + flickable.contentHeight - flickable.height + flickable.bottomMargin
		return Math.max(first, Math.min(Math.max(first, last), contentY))
	}

	acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
	onWheel: event => {
		// A touchpad already reports smooth pixel movement, so it moves the list directly
		if (event.pixelDelta.y !== 0) {
			wheel.glide.stop()
			flickable.contentY = clamped(flickable.contentY - event.pixelDelta.y)
			return
		}
		// Notches during a glide add to where it was heading, so fast turns still travel the full distance
		const from = wheel.glide.running ? wheel.glide.to : flickable.contentY
		wheel.glide.stop()
		wheel.glide.to = clamped(from - event.angleDelta.y / 120 * step)
		wheel.glide.start()
	}

	// A pointer handler takes no children, so the animation is held in a property
	readonly property NumberAnimation glide: NumberAnimation {
		target: wheel.flickable
		property: "contentY"
		duration: wheel.glideDuration
		easing.type: Easing.OutCubic
	}
}
