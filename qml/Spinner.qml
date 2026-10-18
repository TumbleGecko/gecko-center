// A turning arc in the gecko green that says the app is working on something
import QtQuick
import GeckoUi

Item {
	id: spinner

	property real size: 28
	property bool running: true

	implicitWidth: size
	implicitHeight: size
	visible: running

	Canvas {
		id: arc
		anchors.fill: parent

		onPaint: {
			const context = getContext("2d")
			const line = Math.max(3, spinner.size / 9)
			context.reset()
			context.lineWidth = line
			context.lineCap = "round"
			context.strokeStyle = Theme.line
			context.beginPath()
			context.arc(width / 2, height / 2, width / 2 - line, 0, Math.PI * 2)
			context.stroke()
			context.strokeStyle = Theme.accent
			context.beginPath()
			context.arc(width / 2, height / 2, width / 2 - line, 0, Math.PI * 0.6)
			context.stroke()
		}

		RotationAnimator on rotation {
			from: 0
			to: 360
			duration: 900
			loops: Animation.Infinite
			running: spinner.running && spinner.visible
		}
	}
}
