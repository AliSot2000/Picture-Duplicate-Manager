from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, pyqtSignal
import sys
from typing import Union
from base_image import BaseImage

# TODO font info from config.

class ClickableImage(BaseImage):
    clicked = pyqtSignal()
    __image_loaded: bool = True

    def mouseReleaseEvent(self, event):
        """
        Catch it when the mouse button is released on the image and emit the clicked signal.
        :param event: Click event
        :return:
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    @property
    def image_loaded(self):
        """
        Return if the image is loaded.
        :return:
        """
        return self.__image_loaded

    @image_loaded.setter
    def image_loaded(self, value: bool):
        """
        Set the image loaded variable. This also performs the loading and unloading of the image.
        :param value: True if the image should be loaded, False if not.
        :return:
        """
        self.__image_loaded = value
        if self.__image_loaded and self.file_path is not None:
            self._load_image()
        else:
            self._unload_image()

    @property
    def file_path(self):
        """
        Get the current file path of the image
        :return:
        """
        return self.__file_path

    @file_path.setter
    def file_path(self, value: Union[None, str]):
        """
        Set the file path of the image. This if the image is supposed to be loaded it will be loaded as well.
        The filepath can also be left empty to have a template.
        :param value:
        :return:
        """
        self.__file_path = value

        if self.__file_path is not None and self.image_loaded:
            self._load_image()


def helper():
    print("Helper called")

def invert(w: ClickableImage):
    print(f"Invert called : {w.image_loaded}")
    w.image_loaded = not w.image_loaded

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClickableImage()
    window.file_path = "/media/alisot2000/DumpStuff/Test128/2022-09-01 02.35.12_001.jpg"
    window.clicked.connect(helper)
    window.clicked.connect(lambda : invert(window))
    window.show()

    sys.exit(app.exec())