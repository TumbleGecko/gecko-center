// A single row of filter chips that never wraps, the wheel scrolls it sideways and a fade shows there is more
import QtQuick
import GeckoUi

Item {
	id: row

	// Each choice is { value, name }, and current is the chosen value
	property var choices: []
	property string current: ""

	signal chosen(string value)

	implicitHeight: 38

	ListView {
		id: strip
		anchors.fill: parent
		orientation: ListView.Horizontal
		spacing: 8
		clip: true
		model: row.choices
		boundsBehavior: Flickable.StopAtBounds

		delegate: Chip {
			required property var modelData
			text: modelData.name
			checked: row.current === modelData.value
			onClicked: row.chosen(modelData.value)
		}

		// A mouse wheel only turns up and down, so here that moves the row left and right
		WheelHandler {
			acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
			onWheel: event => {
				const delta = event.pixelDelta.x || event.pixelDelta.y || event.angleDelta.y / 120 * 80
				const furthest = Math.max(0, strip.contentWidth - strip.width)
				strip.contentX = Math.max(0, Math.min(furthest, strip.contentX - delta))
			}
		}
	}

	Rectangle {
		visible: strip.contentX > 1
		anchors.left: parent.left
		width: 48
		height: parent.height
		gradient: Gradient {
			orientation: Gradient.Horizontal
			GradientStop { position: 0; color: Theme.ground }
			GradientStop { position: 1; color: "transparent" }
		}
	}

	Rectangle {
		visible: strip.contentX < strip.contentWidth - strip.width - 1
		anchors.right: parent.right
		width: 48
		height: parent.height
		gradient: Gradient {
			orientation: Gradient.Horizontal
			GradientStop { position: 0; color: "transparent" }
			GradientStop { position: 1; color: Theme.ground }
		}
	}
}
