from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QFont
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
import sys
import os
from typing import Union
import warnings

# TODO font info from config.

class ClickableImage(QWidget):
    clicked = pyqtSignal()
    pixmap = None

    __file_path: str = None
    __image_loaded: bool = True
    width_div_height: float = 1.0

    filler_color = Qt.GlobalColor.darkGray

    def __init__(self, file_path: str = None):
        super().__init__()
        self.file_path = file_path

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
            self.__load_image()
        else:
            self.__unload_image()

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
            self.__load_image()

    def __load_image(self):
        """
        Load the image from the file path into ram and set the pixmap
        :return:
        """
        assert self.file_path is not None, "File path must be set before loading image."
        self.pixmap = QPixmap(self.file_path)

        if (ext := os.path.splitext(self.file_path)[1].lower()) not in [".png", ".jpg", ".jpeg", ".gif"]:
            warnings.warn(f"File must be an image. File Extension: {ext}")
        else:
            try:
                self.width_div_height = self.pixmap.width() / self.pixmap.height()
            except ZeroDivisionError:
                self.width_div_height = 1.0

        self.updateGeometry()
        if not self.pixmap.isNull() and self.isVisible():
            self.update()

    def __unload_image(self):
        """
        Removes the image from ram. The widget will draw a dark gray rectangle.
        :return:
        """
        self.pixmap = None
        self.updateGeometry()
        if self.isVisible():
            self.update()

    def sizeHint(self):
        """
        Custom implementation of the size hint depending on if the image is loaded or not.
        :return:
        """
        if self.pixmap and not self.pixmap.isNull():
            return self.pixmap.size()
        return QSize()

    def paintEvent(self, event):
        """
        Custom implementation of the paint event to rescale the image to fit.
        :param event:
        :return:
        """
        if not self.pixmap or self.pixmap.isNull():
            # Create a filler shape to indicate where the image is supposed to be.
            pt = QPainter(self)
            pt.fillRect(self.rect(), self.filler_color)

            if self.pixmap is not None and self.pixmap.isNull():

                # Draw the text in the middle of the widget
                text = "Couldn't load file"
                font = QFont("Arial", 12, QFont.Weight.Bold)
                pt.setFont(font)
                text_rect = pt.boundingRect(self.rect(), 0, text)
                text_position = self.rect().center() - text_rect.center()
                pt.drawText(text_position, text)

                # Attempt to reload the image.
                if self.file_path is not None:
                    self.__load_image()
            return

        # Draw when image is successfully loaded n stuffl.
        if self.size() == self.pixmap.size():
            r = self.rect()
        else:
            r = QRect(QPoint(),
                self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
            r.moveCenter(self.rect().center())
        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)

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