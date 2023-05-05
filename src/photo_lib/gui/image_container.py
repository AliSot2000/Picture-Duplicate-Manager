from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class ResizingImage(QLabel):
    img_lbl: QLabel
    pxmap: QPixmap
    fpath: str

    def __init__(self, file_path: str):
        super().__init__()
        self.fpath = file_path
        self.pixmap = QPixmap(file_path)
        self.setPixmap(self.pixmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True) # Will scale the widget, undoing the keep aspect ratio.
        # self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)  # Image goes behind other widgets.

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setPixmap(self.pixmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True)

