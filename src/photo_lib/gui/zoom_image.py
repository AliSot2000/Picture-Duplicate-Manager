from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent, QResizeEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF, QTimer
import sys
import os
from typing import Union
import math
import warnings
from photo_lib.gui.base_image import BaseImage
from photo_lib.gui.base_image_loader import LoadingBaseImage


# TODO zoom out, recentering of image.

class ZoomImage(LoadingBaseImage):
    # zoom_in = pyqtSignal()
    # zoom_out = pyqtSignal()
    # move_left = pyqtSignal()
    # move_right = pyqtSignal()
    # move_up = pyqtSignal()
    # move_down = pyqtSignal()
    last_pos: Union[None , QPointF] = None

    __capture = False

    __offset: QPointF = QPointF(0, 0)
    __scale_offset: int = 0
    __fitting_scale: int = 0
    constrain_offset: bool = True

    def __init__(self, file_path: str = None):
        super().__init__()
        self.timer = QTimer(self)
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
        :param p: Point where zooming is starting from.
        :param d: amount to increase absolute size of image
        :return:
        """
        old_s = 2 ** (1 + self.__scale_offset / 100)
        new_s = 2 ** (1 + (self.__scale_offset + d) / 100)

        if p is not None and not p.isNull():
            # Post Condition - a different origin of scaling was provided.
            if not self.constrain_offset:
                # Different origin and we perform zoom with that origin regardless of image size.
                self._zoomOffsetHandler(p, old_s, new_s)
            else:
                # We perform zooming with different origin only if the image is larger than the screen area.
                if self.__fitting_scale > self.__scale_offset and d < 0:
                    # Zooming out and image is smaller than screen area.
                    r = QRect(QPoint(),
                              self.pixmap.size().scaled(self.pixmap.size() * new_s, Qt.AspectRatioMode.KeepAspectRatio))
                    r.moveCenter(self.rect().center() + self.__offset.toPoint() * old_s)
                    if r.topLeft().x() < 0:
                        self.__offset += QPointF(-r.topLeft().x(), 0) / old_s
                    if r.topLeft().y() < 0:
                        self.__offset += QPointF(0, -r.topLeft().y()) / old_s
                    if r.bottomRight().x() > self.width():
                        self.__offset -= QPointF(r.bottomRight().x() - self.width(), 0) / old_s
                    if r.bottomRight().y() > self.height():
                        self.__offset -= QPointF(0, r.bottomRight().y() - self.height()) / old_s
                else:
                    # Image is larger than screen area or we're zooming in.
                    self._zoomOffsetHandler(p, old_s, new_s)

        self.__scale_offset += d
        self.update()

    def _zoomOffsetHandler(self, p: QPointF, old_s: float, new_s: float):
        """
        Perform zoom with different origin of scaling.
        :param new_s: new zoom in exponent form
        :param old_s: old zoom in exponent form
        :param p: point in screen coordinates where to zoom to.
        :return:
        """
        mtc = self.rect().center().toPointF() - p
        current_t = mtc / old_s + self.__offset
        new_t = mtc / new_s + self.__offset
        self.__offset -= new_t - current_t


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
        """
        When mouse is released, reset the last position
        :param a0:
        :return:
        """
        if a0.button() == Qt.MouseButton.LeftButton:
            self.last_pos = None

        if a0.button() == Qt.MouseButton.RightButton:
            self.resetImage()
            self.update()

    def mouseMoveEvent(self, a0: QMouseEvent) -> None:
        """
        When mouse is moved, move the image accordingly
        :param a0:
        :return:
        """
        if self.last_pos is not None:
            delta = a0.globalPosition() - self.last_pos
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.zoomImage(d=delta.toPoint().y())
            else:
                self.moveImage(p=delta / (2 ** (1 + self.__scale_offset / 100)))
        self.last_pos = a0.globalPosition()

    def resetImage(self):
        """
        Reset Scale and Offset of image.
        :return:
        """
        self.__offset = QPointF(0, 0)

        if self.pixmap.isNull():
            self.__scale_offset = 1
            return

        r = QRect(QPoint(),
                  self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
        self.__scale_offset = int((math.log2( r.height() / self.pixmap.height()) - 1) * 100)
        self.__fitting_scale = self.__scale_offset
        self.update()


    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        When the widget is resized, recalculate the __fitting_scale
        :param a0:
        :return:
        """
        super().resizeEvent(a0)
        if self.pixmap is None or self.pixmap.isNull():
            return
        r = QRect(QPoint(),
                  self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
        try:
            self.__scale_offset = int((math.log2(r.height() / self.pixmap.height()) - 1) * 100)
        except ValueError:
            self.__scale_offset = 1

    def _load_image(self):
        """
        Load the image from the file path into ram and set the pixmap
        :return:
        """
        super()._load_image()
        self.timer.singleShot(100, self.resetImage)

    def paintEvent(self, event):
        """
        Custom implementation of the paint event to rescale the image to fit.
        :param event:
        :return:
        """
        if self.pixmap is None or self.pixmap.isNull():
            self.empty_pixmap_painter()
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