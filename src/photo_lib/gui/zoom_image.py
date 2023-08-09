from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF
import sys
import os
from typing import Union
import math
import warnings


# TODO zoom relative to mouse position
# TODO zoom out, recentering of image.

class ZoomImage(QWidget):
    # zoom_in = pyqtSignal()
    # zoom_out = pyqtSignal()
    # move_left = pyqtSignal()
    # move_right = pyqtSignal()
    # move_up = pyqtSignal()
    # move_down = pyqtSignal()
    pixmap = None
    last_pos: Union[None , QPointF] = None

    __file_path: str = None
    __image_loaded: bool = True
    width_div_height: float = 1.0

    filler_color = Qt.GlobalColor.darkGray
    __capture = False

    __offset: QPointF = QPointF(0, 0)
    __scale_offset: int = 0

    def __init__(self, file_path: str = None):
        super().__init__()
        self.file_path = file_path

    def enterEvent(self, event: QEnterEvent) -> None:
        """
        Catch the enter event to set the focus on the widget.
        :param event:
        :return:
        """
        self.__capture = True
        super().enterEvent(event)

    def leaveEvent(self, a0: QEvent) -> None:
        """
        Catch the leave event to unset the focus on the widget.
        :param a0:
        :return:
        """
        self.__capture = False
        super().leaveEvent(a0)

    def wheelEvent(self, event):
        """
        Catch it when the mouse button is released on the image and emit the clicked signal.
        :param event: Click event
        :return:
        """
        print(event.position())
        print(self.size())
        if not self.__capture:
            event.ignore()
            return
        else:
            event.accept()

        # distinguish if we need to use pixelDelta or angelDelta
        if not event.pixelDelta().isNull():
            p = event.pixelDelta()
        else:
            p = event.angleDelta() / 8

        # Detect shift key
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            p /= 2

        # if CTRL is pressed, interpret as zoom
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if p.y() == 0:
                d = p.x()
            else:
                d = p.y()
            self.zoomImage(d, event.position())
        else:
            self.moveImage(p)

    def zoomImage(self, d: int, p: QPointF = None):
        """
        Changes the zoom of the image. + <=> zoom in.
        y scroll has precedence over x scroll.
        :param d: amount to increase absolute size of image
        :return:
        """
        if p is not None and not p.isNull():
            print(self.__offset)
            old_s = 2 ** (1 + self.__scale_offset / 100)
            new_s = 2 ** (1 + (self.__scale_offset + d) / 100)

            dtc = self.rect().center().toPointF() + p
            img_c = (dtc - self.__offset) * old_s / new_s
            self.__offset = img_c - dtc
            print(self.__offset)
            print(old_s)
            print(new_s)
        self.__scale_offset += d
        self.update()

    def moveImage(self, p: Union[QPoint, QPointF]):
        """
        Moves the image horizontally by d pixels.
        :param p: shift amt in pixels, + <=> move right.
        :return:
        """
        self.__offset += p.toPointF() if type(p) is QPoint else p
        self.update()

    def mousePressEvent(self, a0: QMouseEvent) -> None:
        """
        When mouse is clicked, take note of current position
        :param a0:
        :return:
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.last_pos = a0.globalPosition()

        super().mousePressEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.last_pos = None

        if a0.button() == Qt.MouseButton.RightButton:
            self.resetImage()
            self.update()

    def mouseMoveEvent(self, a0: QMouseEvent) -> None:
        if self.last_pos is not None:
            delta = a0.globalPosition() - self.last_pos
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.zoomImage(d=delta.toPoint().y())
            else:
                self.moveImage(p=delta / (2 ** (1 + self.__scale_offset / 100)))
        self.last_pos = a0.globalPosition()

    def resetImage(self):
        self.__offset = QPointF(0, 0)

        if self.pixmap.isNull():
            self.__scale_offset = 1
            return

        r = QRect(QPoint(),
                  self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
        self.__scale_offset = int((math.log2( r.height() / self.pixmap.height()) - 1) * 100)


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

        if self.__file_path is not None:
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
        self.resetImage()
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
            new_size = self.pixmap.size() * (2 ** (1 + self.__scale_offset / 100))
            r = QRect(QPoint(),
                self.pixmap.size().scaled(new_size, Qt.AspectRatioMode.KeepAspectRatio))
            r.moveCenter(self.rect().center() + self.__offset.toPoint() * (2 ** (1 + self.__scale_offset / 100)))
        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZoomImage()
    window.file_path = "/media/alisot2000/DumpStuff/Test128/2022-09-01 02.35.12_001.jpg"
    window.show()

    sys.exit(app.exec())