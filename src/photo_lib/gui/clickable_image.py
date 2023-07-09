import os.path
import warnings

from PyQt6.QtWidgets import QLabel, QPushButton
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt
from typing import Union

class ClickableImage(QPushButton):
    img_lbl: QLabel
    pixmap: Union[QPixmap, None]
    fpath: str
    width_div_height: float = 1.0
    count: int = 0

    def __init__(self, file_path: str):
        super().__init__()
        self.pixmap = None
        self.load_image(file_path)

        # self.setPixmap(self.pixmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True) # Will scale the widget, undoing the keep aspect ratio.
        # self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)  # Image goes behind other widgets.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # self.setMaximumSize(event.size())
        self.setIconSize(event.size())
        # self.setPixmap(self.pixmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True)

    def load_image(self, file_path: str):
        self.fpath = file_path
        self.pixmap = QPixmap(file_path)
        if os.path.splitext(file_path)[1] not in [".png", ".jpg", ".jpeg", ".gif"]:
            warnings.warn("File must be an image.")
        else:
            try:
                self.width_div_height = self.pixmap.width() / self.pixmap.height()
            except ZeroDivisionError:
                self.width_div_height = 1.0
        self.setIcon(QIcon(self.pixmap))
        self.setIconSize(self.size())
        self.setStyleSheet("border: none;")