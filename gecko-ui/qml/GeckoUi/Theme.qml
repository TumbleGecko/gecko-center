// The gecko colors, type and motion, one place for every screen
pragma Singleton
import QtQuick

QtObject {
	readonly property color ground: "#0b0f0c"
	readonly property color rail: "#111813"
	readonly property color surface: "#131b16"
	readonly property color raised: "#1b261e"
	readonly property color line: "#223027"
	readonly property color lineStrong: "#2f4a35"
	readonly property color text: "#e8efe9"
	readonly property color textStrong: "#f2f7f2"
	readonly property color muted: "#a9b8ad"
	readonly property color accent: "#6cc070"
	readonly property color accentHover: "#8fd68f"
	readonly property color accentPressed: "#5fae63"
	readonly property color textOnAccent: "#0b140d"
	readonly property color doneFill: "#1c3020"
	readonly property color warning: "#f1d18a"
	readonly property color warningFill: "#1f1a12"
	readonly property color warningLine: "#4a3a1e"
	readonly property color danger: "#f0a39a"
	// The fill of a button that destroys something, such as Remove
	readonly property color dangerFill: "#c8463b"
	readonly property color dangerHover: "#dc5a4e"
	readonly property color dangerPressed: "#a8382f"
	readonly property color textOnDanger: "#fff4f2"

	readonly property string font: "IBM Plex Sans"
	readonly property int bodySize: 17
	readonly property int smallSize: 16
	readonly property int headingSize: 40

	// Put each sentence on its own line
	function lines(text) {
		return (text || "").replace(/([.!?]) (?=\S)/g, "$1\n")
	}

	// A byte count in the units people read, 969572490 becomes 970 MB
	function size(bytes) {
		const units = ["bytes", "kB", "MB", "GB"]
		let value = bytes
		let unit = 0
		while (value >= 1000 && unit < units.length - 1) {
			value /= 1000
			unit++
		}
		return (unit === 0 ? value : value.toFixed(value < 10 ? 1 : 0)) + " " + units[unit]
	}

	// Motion in milliseconds, with an ease that settles instead of stopping hard
	readonly property int quick: 160
	readonly property int calm: 450
	readonly property int easing: Easing.OutCubic
}
