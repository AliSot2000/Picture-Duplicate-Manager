from PyQt6.QtWidgets import QLabel, QSizePolicy, QPushButton, QVBoxLayout
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class ResizingImage(QPushButton):
    img_lbl: QLabel
    pxmap: QPixmap
    fpath: str
    width_div_height: float

    def __init__(self, file_path: str):
        super().__init__()
        self.img_lbl = QLabel()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.img_lbl)
        # self.media.setScaledContents(True) # Will scale the widget, undoing the keep aspect ratio.
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)  # Image goes behind other widgets.
        self.load_image(file_path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pxmap is not None:
            self.img_lbl.setPixmap(self.pxmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
        # self.media.setScaledContents(True)

    def load_image(self, file_path: str):
        self.fpath = file_path
        self.pxmap = QPixmap(file_path)
        self.width_div_height = self.pxmap.width() / self.pxmap.height()
        self.img_lbl.setPixmap(self.pxmap.scaled(self.size(), aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))