"""The mouse's back and forward side buttons as back and forward, wherever the pointer is in the app"""

from PySide6.QtCore import QEvent, QObject, Qt, Signal

SIDE_BUTTONS = (Qt.MouseButton.BackButton, Qt.MouseButton.ForwardButton)
PRESS_AND_RELEASE = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick)


class MouseNavigation(QObject):
	"""Watches the whole app, since a card or text under the pointer would otherwise take the press first"""

	back = Signal()
	forward = Signal()

	def __init__(self, application, parent=None):
		super().__init__(parent)
		application.installEventFilter(self)

	def eventFilter(self, watched, event):
		if event.type() not in PRESS_AND_RELEASE or event.button() not in SIDE_BUTTONS:
			return False
		# The press steps once, the release and a quick second press are swallowed so nothing else reacts
		if event.type() == QEvent.Type.MouseButtonPress:
			(self.back if event.button() == Qt.MouseButton.BackButton else self.forward).emit()
		return True

	def attach(self, engine):
		"""Lets the MouseBack part in QML follow these buttons"""
		engine.rootContext().setContextProperty("geckoMouseNavigation", self)
