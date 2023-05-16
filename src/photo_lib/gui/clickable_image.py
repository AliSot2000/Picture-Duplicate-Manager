from PyQt6.QtWidgets import QLabel, QPushButton
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt

class ClickableImage(QPushButton):
    img_lbl: QLabel
    pxmap: QPixmap
    fpath: str
    width_div_height: float

    def __init__(self, file_path: str):
        super().__init__()
        self.fpath = file_path
        self.pixmap = QPixmap(file_path)
        self.width_div_height = self.pixmap.width() / self.pixmap.height()
        self.setIcon(QIcon(self.pixmap))
        self.setIconSize(self.size())
        self.setStyleSheet("border: none;")
        # self.setPixmap(self.pixmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True) # Will scale the widget, undoing the keep aspect ratio.
        # self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)  # Image goes behind other widgets.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setIconSize(self.size())
        # self.setPixmap(self.pixmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True)

    def test_click(self):
        print("Image clicked")