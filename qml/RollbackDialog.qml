// Asks before rolling back to a snapshot, the list and a snapshot's own page both open it
import QtQuick

QuestionDialog {
	id: dialog

	property var snapshot: null

	function ask(chosen) {
		snapshot = chosen
		open()
	}

	question: "Roll back to snapshot " + (snapshot ? snapshot.number : "") + "?"
	explanation: "After a restart the system is the way it was "
		+ (snapshot ? snapshot.date.replace(/:\d\d$/, "").replace(" ", " at ") : "")
		+ ". Your own files stay as they are. "
		+ "The system as it is now is saved first, so this can be undone the same way."
	confirmText: "Roll back"
	onConfirmed: window.runSystem("snapshots", "rollback", String(snapshot.number),
		"Rolling back to snapshot " + snapshot.number, "Roll back", true)
}
