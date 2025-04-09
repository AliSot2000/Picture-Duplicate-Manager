from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QMouseEvent

from photo_lib.gui.temp_new_wigets.new_base_image import BaseImage


class ClickableImage(BaseImage):

    # Signals, we have signals for clicking and double-clicking the image.
    click  = pyqtSignal(BaseImage)
    double_click = pyqtSignal(BaseImage)

    def mouseReleaseEvent(self, a0: QMouseEvent):
        """
        Capture mouse release event (left click) to emit a clicked signal to the parent.
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.click.emit(self)

    def mouseDoubleClickEvent(self, a0: QMouseEvent):
        """
        Capture mouse double click event to submit a
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.double_click.emit(self)
