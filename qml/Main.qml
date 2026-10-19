// The Gecko Center window, a rail of pages on the left and the chosen page to its right
import QtCore
import QtQuick
import GeckoUi
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
	id: window

	// One of the rail's pages, and the app, package or guide topic open over it
	property string page: startPage || "overview"
	property var detail: null
	// Each browse page's search, filters and scroll place, so coming back from an app keeps them
	property var browseMemory: ({})
	property bool catalogReady: false

	// The change running now, which page or app it belongs to and how far it got
	property string jobOwner: ""
	property string jobTitle: ""
	property real jobFraction: 0
	property string jobText: ""
	// The newest lines the running change printed, at most jobLogLines of them
	property alias jobLog: jobLogModel
	property var jobResult: null

	readonly property int pendingCount: {
		const system = bridge.updates.system
		return (system ? system.count : 0) + (bridge.updates.flatpak || []).length
	}
	readonly property int healthAttention: ((center.info.health || {}).checks || [])
		.filter(check => check.state === "warning" || check.state === "problem").length

	width: windowSize.width
	height: windowSize.height
	minimumWidth: 940
	minimumHeight: 640
	visible: true
	title: "Gecko Center"
	color: Theme.ground
	font.family: Theme.font
	font.pixelSize: Theme.bodySize

	// Where you have been and where Back left from, so the mouse's side buttons can go both ways
	property var history: []
	property var future: []

	function go(name, entry) {
		if (name === page && entry === detail)
			return
		history = history.concat([{ page: page, detail: detail }])
		future = []
		page = name
		detail = entry
	}

	function showPage(name) {
		go(name, null)
	}

	function openDetail(entry) {
		// A page reading its own app again replaces itself instead of adding a step
		if (detail && entry && detail.key === entry.key) {
			detail = entry
			return
		}
		go(page, entry)
	}

	// A package opens as its app when the catalog knows it, else as the page zypper can describe
	// The tab it starts on is optional, the Updates list opens the update tab
	function openPackage(source, name, startTab) {
		const key = apps.findKey(source, name)
		if (key)
			openDetail(Object.assign({}, apps.entry(key, source), { startTab: startTab || "" }))
		else if (source === "openSUSE")
			openPackagePage(name, startTab)
	}

	// The page opens at once with the name, zypper fills in the rest when it has read it
	function openPackagePage(name, startTab) {
		openDetail({ kind: "package", key: "package:" + name, id: name, package: name, name: name, loading: true,
			startTab: startTab || "" })
		bridge.openPackage(name)
	}

	function goBack() {
		if (history.length === 0)
			return
		future = future.concat([{ page: page, detail: detail }])
		const previous = history[history.length - 1]
		history = history.slice(0, -1)
		page = previous.page
		detail = previous.detail
	}

	function goForward() {
		if (future.length === 0)
			return
		history = history.concat([{ page: page, detail: detail }])
		const next = future[future.length - 1]
		future = future.slice(0, -1)
		page = next.page
		detail = next.detail
	}

	// Runs the action now, or after the password dialog when sudo needs one first
	function withPassword(needed, reason, actionText, action) {
		if (!needed) {
			action()
			return
		}
		password.reason = reason
		password.actionText = actionText
		password.pending = action
		password.open()
	}

	function openGuide(topic) {
		go("guide", { guide: topic })
	}

	// Runs one of the system pages' changes in the job dialog, after the password when it needs one
	function runSystem(kind, action, argument, title, actionText, restartAfter) {
		withPassword(center.needsPassword(action, argument), title + " needs your password.", actionText, () => {
			startJob("system", title)
			jobDialog.restartAfter = restartAfter === true
			jobDialog.open()
			center.run(kind, action, argument)
		})
	}

	function startJob(owner, title) {
		jobOwner = owner
		jobTitle = title
		jobFraction = 0
		jobText = ""
		jobLogModel.clear()
		jobResult = null
	}

	function bringForward() {
		if (window.visibility === Window.Minimized)
			window.showNormal()
		window.show()
		window.raise()
		window.requestActivate()
	}

	Connections {
		target: bridge

		function onJobProgress(fraction, text) {
			window.jobFraction = fraction
			window.jobText = text
		}

		// Lines arrive in batches and are added to the end, the oldest go once there are too many
		function onJobLines(lines) {
			lines.slice(-window.jobLogLines).forEach(line => jobLogModel.append({ line: line }))
			if (jobLogModel.count > window.jobLogLines)
				jobLogModel.remove(0, jobLogModel.count - window.jobLogLines)
		}

		function onJobFinished(succeeded, reboot, message) {
			window.jobResult = { succeeded: succeeded, reboot: reboot, message: message }
		}

		function onPageRequested(name) {
			window.showPage(name)
		}

		function onForwardRequested() {
			window.bringForward()
		}

		function onTargetReady(entry) {
			window.openDetail(entry)
			window.bringForward()
		}

		// Someone who already went elsewhere is not pulled back to the package
		function onPackageReady(entry) {
			if (window.detail && window.detail.key === entry.key)
				window.detail = entry
		}
	}

	Component.onCompleted: {
		if (windowSize.maximized)
			window.showMaximized()
		center.read("health")
	}

	// The size the window last closed at, a maximized window keeps the size it had before
	Settings {
		id: windowSize
		location: windowSizeFile
		category: "window"
		property int width: 1200
		property int height: 800
		property bool maximized: false
	}

	onClosing: {
		windowSize.maximized = window.visibility === Window.Maximized
		if (!windowSize.maximized) {
			windowSize.width = window.width
			windowSize.height = window.height
		}
		windowSize.sync()
	}

	Connections {
		target: apps

		function onLoaded() {
			window.catalogReady = true
		}
	}

	JobDialog { id: jobDialog; objectName: "jobDialog" }

	readonly property int jobLogLines: 300

	ListModel { id: jobLogModel }

	PasswordDialog {
		id: password
		appName: "Gecko Center"
		checkPassword: entered => bridge.setPassword(entered)

		property var pending: null

		onAccepted: {
			const action = pending
			pending = null
			action()
		}
	}

	RowLayout {
		anchors.fill: parent
		spacing: 0

		MouseBack {
			onBack: window.goBack()
			onForward: window.goForward()
		}

		NavRail {
			Layout.fillHeight: true
			Layout.preferredWidth: 260
		}

		Loader {
			id: content

			readonly property var pages: ({
				"overview": overviewPage, "performance": performancePage, "explore": explorePage,
				"installed": installedPage, "updates": updatesPage, "snapshots": snapshotsPage, "sources": sourcesPage,
				"hardware": hardwarePage, "drivers": driversPage, "storage": storagePage,
				"services": servicesPage, "guide": guidePage, "news": newsPage, "settings": settingsPage
			})
			Layout.fillWidth: true
			Layout.fillHeight: true
			sourceComponent: {
				if (window.detail)
					return window.detail.guide ? guideTopicPage : window.detail.snapshot ? snapshotPage
						: window.detail.sourceAlias ? sourcePage : window.detail.device ? devicePage : detailPage
				return content.pages[window.page] || content.pages.overview
			}

			// Each new page slides in from the right and settles
			onLoaded: {
				item.opacity = 0
				item.x = 40
				enter.restart()
			}

			ParallelAnimation {
				id: enter
				NumberAnimation {
					target: content.item; property: "opacity"; to: 1; duration: Theme.calm; easing.type: Theme.easing
				}
				NumberAnimation {
					target: content.item; property: "x"; to: 0; duration: Theme.calm; easing.type: Theme.easing
				}
			}
		}
	}

	Component { id: overviewPage; OverviewPage {} }
	Component { id: explorePage; BrowsePage {} }
	Component { id: installedPage; BrowsePage { installedOnly: true } }
	Component { id: updatesPage; UpdatesPage {} }
	Component { id: performancePage; PerformancePage {} }
	Component { id: snapshotsPage; SnapshotsPage {} }
	Component { id: sourcesPage; SourcesPage {} }
	Component { id: hardwarePage; HardwarePage {} }
	Component { id: driversPage; DriversPage {} }
	Component { id: storagePage; StoragePage {} }
	Component { id: servicesPage; ServicesPage {} }
	Component { id: guidePage; GuidePage {} }
	Component { id: newsPage; NewsPage {} }
	Component { id: settingsPage; SettingsPage {} }
	Component { id: detailPage; AppPage { entry: window.detail } }
	Component { id: guideTopicPage; GuideTopicPage { topicId: window.detail.guide } }
	Component { id: snapshotPage; SnapshotPage { number: window.detail.snapshot } }
	Component { id: sourcePage; SourcePage { sourceAlias: window.detail.sourceAlias } }
	Component { id: devicePage; DevicePage { deviceKey: window.detail.device } }
}
