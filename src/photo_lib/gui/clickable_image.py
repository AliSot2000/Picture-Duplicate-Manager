import os.path
import warnings
import sys
from PyQt6.QtWidgets import QLabel, QPushButton, QApplication
from PyQt6.QtGui import QPixmap, QIcon
from typing import Union

class ClickableImage(QPushButton):
    img_lbl: QLabel
    pixmap: Union[QPixmap, None]
    fpath: str
    width_div_height: float = 1.0
    count: int = 0

    not_loaded_icon: QIcon = None

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
        if os.path.splitext(file_path)[1].lower() not in [".png", ".jpg", ".jpeg", ".gif"]:
            warnings.warn("File must be an image.")
        else:
            try:
                self.width_div_height = self.pixmap.width() / self.pixmap.height()
            except ZeroDivisionError:
                self.width_div_height = 1.0
        self.setIcon(QIcon(self.pixmap))
        self.setIconSize(self.size())
        self.setStyleSheet("border: none;")
        self.setText("")

    def unload_image(self):
        """
        Remove Image (remove it from RAM), set either a empty image or set a custom nothing here - icon.
        :return:
        """
        self.pixmap = None
        if self.not_loaded_icon is None:
            self.setIcon(QIcon())
            self.setStyleSheet("border: 1px solid black;")
            self.setText("Media not Loaded...")
        else:
            self.setIcon(self.not_loaded_icon)
            self.setStyleSheet("border: none;")

    def reload_image(self):
        """
        Provided, the image was loaded before, reload it.
        :return:
        """
        if self.fpath is not None:
            self.load_image(self.fpath)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = ClickableImage('/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images/IMG_2159.JPG')
    widget.show()
    sys.exit(app.exec())