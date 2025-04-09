from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication

from photo_lib.data_objects import MediaPaths
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.temp_new_wigets.new_base_image import BaseImage


class ClickableImage(BaseImage):

    # Signals, we have signals for clicking and double-clicking the image.
    click  = pyqtSignal(BaseImage)
    double_click = pyqtSignal(BaseImage)

    cancel_next: bool

    def __init__(self, mp: MediaPaths, model: UIModel):
        """
        Set up the image. Additionally, adds a variable and a timer to intercept the two left click event that are
        captured by the class when a double click occurred.
        """

        super().__init__(mp=mp, model=model)

        # We set the timeout slightly higher than to make sure the double click is able to kill the timer.
        self.timer = QTimer(self)
        self.timer.setInterval(QApplication.doubleClickInterval())
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.emit_click)

        self.cancel_next = False

    def emit_click(self):
        """
        Trigger to emit a signal after
        """
        self.click.emit(self)

    def mouseReleaseEvent(self, a0: QMouseEvent):
        """
        Capture mouse release event (left click) to emit a clicked signal to the parent.
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            if self.cancel_next:
                a0.ignore()
                self.cancel_next = False
                return

            self.timer.start()

    def mouseDoubleClickEvent(self, a0: QMouseEvent):
        """
        Capture mouse double click event to submit a double click event
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.double_click.emit(self)
            self.timer.stop()
            self.cancel_next = True
