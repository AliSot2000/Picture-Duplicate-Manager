from PyQt6.QtWidgets import QWidget, QApplication, QFrame
from PyQt6.QtGui import QPixmap, QPainter, QFont
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
import sys
import os
from typing import Union
import warnings


class BaseImage(QFrame):
    __pixmap = None
    __load_image_flg: bool = False

    __file_path: str = None
    width_div_height: float = 1.0

    filler_color = Qt.GlobalColor.darkGray

    def __init__(self, file_path: str = None):
        super().__init__()
        self.file_path = file_path

    @property
    def load_image_flag(self):
        return self.__load_image_flg

    @property
    def pixmap(self):
        return self.__pixmap

    @pixmap.setter
    def pixmap(self, value: QPixmap):
        self.__pixmap = value
        if self.pixmap is not None:
            self.__load_image_flg = False

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
        if value == self.__file_path:
            return

        # The file path is different and we need to laod the image
        self.__file_path = value
        if value is not None:
            self.__load_image_flg = True
            self.load_image()

    def _load_image(self):
        """
        Load the image from the file path into ram and set the pixmap

        :return:
        """
        assert self.file_path is not None, "File path must be set before loading image."
        self.pixmap = QPixmap(self.file_path)

        if (ext := os.path.splitext(self.file_path)[1].lower()) not in [".png", ".jpg", ".jpeg", ".gif"]:
            warnings.warn(f"File must be an image. File Extension: {ext}")
        try:
            self.width_div_height = self.pixmap.width() / self.pixmap.height()
        except ZeroDivisionError:
            self.width_div_height = 1.0

        self.updateGeometry()
        if not self.pixmap.isNull() and self.isVisible():
            self.update()

    def load_image(self):
    def unload_image(self):
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
        if self.pixmap is None or self.pixmap.isNull():
            self.empty_pixmap_painter()
            return

        # Draw when image is successfully loaded n stuff.
        if self.size() == self.pixmap.size():
            r = self.rect()
        else:
            r = QRect(QPoint(),
                      self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
            r.moveCenter(self.rect().center())
        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)

        # rec = self.rect()
        # rec.setWidth(rec.width() - 1)
        # rec.setHeight(rec.height() - 1)
        # qp.drawRect(rec)

    def empty_pixmap_painter(self):
        """
        In case there's no image loaded, paint a message on the widget.
        :return:
        """
        # Create a filler shape to indicate where the image is supposed to be.
        pt = QPainter(self)
        pt.fillRect(self.rect(), self.filler_color)

        # Draw the text in the middle of the widget
        if self.file_path is not None:
            text = f"Couldn't load {os.path.basename(self.file_path)}"
        else:
            text = "Empty file path"
        font = QFont("Arial", 12, QFont.Weight.Bold)
        pt.setFont(font)
        text_rect = pt.boundingRect(self.rect(), 0, text)
        text_position = self.rect().center() - text_rect.center()
        pt.drawText(text_position, text)

        # Attempt to reload the image.
        if self.file_path is not None:
            self.load_image()
