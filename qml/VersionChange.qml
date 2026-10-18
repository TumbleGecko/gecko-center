// Two versions of one thing, where the parts of the new one that differ are green when newer and yellow when older
import QtQuick
import GeckoUi

Text {
	id: change

	property string from
	property string to
	// Where the two versions go, used when both are known and they differ
	property string template: "%from  →  %to"

	// Digits and the text between them, so 1.10 is read as newer than 1.9
	// A number next to a dash is usually a date or build count, so it is read digit by digit
	function parts(segment, isAfterDash, isBeforeDash) {
		const runs = segment.match(/\d+|\D+/g) || []
		const found = []
		runs.forEach((run, index) => {
			const isNextToDash = (isAfterDash && index === 0) || (isBeforeDash && index === runs.length - 1)
			found.push(...(/^\d+$/.test(run) && isNextToDash ? run.split("") : [run]))
		})
		return found
	}

	// Below zero when the first version is older, above zero when it is newer
	function compare(first, second) {
		const isNumber = /^\d+$/
		if (isNumber.test(first) && isNumber.test(second))
			return Number(first) - Number(second)
		return first < second ? -1 : first > second ? 1 : 0
	}

	function escaped(text) {
		return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
	}

	// Each part between dashes is compared on its own, so only the stretch that changed in it is coloured
	function marked(oldVersion, newVersion) {
		const oldSegments = oldVersion.split("-")
		const newSegments = newVersion.split("-")
		if (oldSegments.length !== newSegments.length) {
			oldSegments.splice(0, oldSegments.length, oldVersion)
			newSegments.splice(0, newSegments.length, newVersion)
		}
		const last = newSegments.length - 1
		const changes = newSegments.map((segment, index) => changedStretch(
			parts(oldSegments[index], index > 0, index < last), parts(segment, index > 0, index < last)))
		// The first change decides the colour, it tells whether the whole version went up or down
		const first = changes.find(stretch => stretch.direction !== 0)
		const colour = first && first.direction < 0 ? Theme.warning : Theme.accentHover
		return changes.map(stretch => escaped(stretch.before) + (stretch.changed === "" ? ""
			: "<font color=\"" + colour + "\">" + escaped(stretch.changed) + "</font>") + escaped(stretch.after))
			.join("-")
	}

	// The new parts split into what stays the same at the start and end and the changed stretch between them
	function changedStretch(oldParts, newParts) {
		let start = 0
		while (start < newParts.length && newParts[start] === oldParts[start])
			start++
		let end = newParts.length
		let oldEnd = oldParts.length
		while (end > start && oldEnd > start && newParts[end - 1] === oldParts[oldEnd - 1]) {
			end--
			oldEnd--
		}
		const isChanged = start < newParts.length || start < oldParts.length
		const direction = !isChanged ? 0 : start >= newParts.length ? -1 : start >= oldParts.length ? 1
			: compare(newParts[start], oldParts[start])
		return { before: newParts.slice(0, start).join(""), changed: newParts.slice(start, end).join(""),
			after: newParts.slice(end).join(""), direction: direction }
	}

	textFormat: Text.StyledText
	color: Theme.muted
	text: {
		if (!from || !to || from === to)
			return escaped(to || from)
		return template.replace("%from", escaped(from)).replace("%to", marked(from, to))
	}
}
