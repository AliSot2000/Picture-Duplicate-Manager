import math
import sys
from typing import Union, Optional

from PyQt6.QtCore import Qt, QRect, QPoint, QEvent, QPointF, QTimer, pyqtSlot
from PyQt6.QtGui import QPainter, QEnterEvent, QMouseEvent, QResizeEvent, QPixmap
from PyQt6.QtWidgets import QApplication

from photo_lib.data_objects import MediaPaths
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.widgets.new_base_image import BaseImage


class ZoomImage(BaseImage):
    last_pos: Union[None , QPointF] = None

    __pixmap: Optional[QPixmap] = None

    __capture = False

    # The offset is in not scaled coordinates. (needed because everything from the ui comes in non scaled coordinates)
    __position_offset: QPointF = QPointF(0, 0)

    # Offset of scale of image relative to the original size of image in exponential form.
    # scaling = 2 ** (1 + self.__scaling_offset * 100)
    __scale_offset: int = 0

    # Threshold once the scale goes below, when the entire picture fits the widget.
    __fitting_scale: int = 0

    # Disable Constrained Scale Down: This feature re-centers the widget once you start scaling out and the image fits
    # inside the size of the image.
    constrain_offset: bool = True

    # INFO overwriting an attribute with a property in a child class works!
    @property
    def pixmap(self) -> QPixmap:
        return self.__pixmap

    @pixmap.setter
    def pixmap(self, value: QPixmap):
        self.__pixmap = value
        self.reset_image()

    def __init__(self, mp: MediaPaths, model: UIModel):
        super().__init__(mp=mp, model=model)
        self.timer = QTimer(self)

    def determine_fp_to_use(self) -> str | None:
        """
        Overwrite the filepath that is supposed to be used to always use in the following precedence order:

        1. original
        2. miniature
        3. thumbnail
        """
        order = [self.media.original_fp, self.media.miniature_fp, self.media.thumbnail_fp]

        valid_paths = list(filter(lambda x: x is not None, order))

        # No valid path found, use empty painter.
        if len(valid_paths) == 0:
            self.pixmap = None
            return None

        assert len(valid_paths) > 0, "At least one valid path should exist."

        return valid_paths[0]

    def enterEvent(self, event: QEnterEvent) -> None:
        """
        Catch the enter event to determine if we need to pay attention to the wheel events.

        :param event:
        :return:
        """
        self.__capture = True
        super().enterEvent(event)

    def leaveEvent(self, a0: QEvent) -> None:
        """
        Catch the leave event to determine if we need to pay attention to the wheel events.

        :param a0:
        :return:
        """
        self.__capture = False
        super().leaveEvent(a0)

    def wheelEvent(self, event):
        """
        Catch the mouse wheel event and either submit it to the zoom_image function as a zoom or as a movement.
        + CTRL -> Zoom (y amount has precedence over x)
        + <ANY> + SHIFT (Reduce the movement by 4 to allow for more precise movement)

        :param event: Wheel event.
        :return:
        """
        if not self.__capture:
            event.ignore()
            return
        else:
            event.accept()

        # distinguish if we need to use pixelDelta or angelDelta
        if not event.pixelDelta().isNull():
            p: QPoint = event.pixelDelta()
        else:
            p: QPoint = event.angleDelta() / 8

        # Detect shift key
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            # Divide both x and y.
            p /= 4

        # if CTRL is pressed, interpret as zoom
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if p.y() == 0:
                d = p.x()
            else:
                d = p.y()

            # INFO: We need to subtract the top left from the position to account for the global position of the event.
            self.zoom_image(d, event.position() - self.rect().topLeft().toPointF())
        else:
            self.move_image(p)

    @pyqtSlot(int)
    @pyqtSlot(int, QPointF)
    def zoom_image(self, d: int, p: QPointF = None):
        """
        INFO: Make sure you pass in a point relative to the widget origin. Don't put use global coordinates.
        (Relative to Root Widget origin)

        Changes the zoom of the image and, if provided use the point p as the origin for the scaling.

        :param p: Point where zooming is starting from. Default center of the widget.
        :param d: amount to increase absolute size of image. > 0 means zooming in
        :return:
        """
        old_s = 2 ** (1 + self.__scale_offset / 100)
        new_s = 2 ** (1 + (self.__scale_offset + d) / 100)

        if p is not None and not p.isNull():
            # Post Condition - a different origin of scaling was provided.
            if not self.constrain_offset:
                # Different origin and we perform zoom with that origin regardless of image size.
                self._zoom_offset_handler(p, old_s, new_s)
            else:
                # We perform zooming with different origin only if the image is larger than the screen area.
                if self.__fitting_scale > self.__scale_offset and d < 0:
                    # Zooming out and image is smaller than screen area.
                    r = QRect(QPoint(),
                              self.pixmap.size().scaled(self.pixmap.size() * new_s, Qt.AspectRatioMode.KeepAspectRatio))
                    r.moveCenter(self.rect().center() + self.__position_offset.toPoint() * old_s)
                    if r.topLeft().x() < 0:
                        self.__position_offset += QPointF(-r.topLeft().x(), 0) / old_s
                    if r.topLeft().y() < 0:
                        self.__position_offset += QPointF(0, -r.topLeft().y()) / old_s
                    if r.bottomRight().x() > self.width():
                        self.__position_offset -= QPointF(r.bottomRight().x() - self.width(), 0) / old_s
                    if r.bottomRight().y() > self.height():
                        self.__position_offset -= QPointF(0, r.bottomRight().y() - self.height()) / old_s
                else:
                    # Image is larger than screen area or we're zooming in.
                    self._zoom_offset_handler(p, old_s, new_s)

        self.__scale_offset += d
        self.update()

    def _zoom_offset_handler(self, p: QPointF, old_s: float, new_s: float):
        """
        Compute delta vector for the offset to account for the zooming origin being not the center of the widget.

        Function updates the offset with the vector.

        :param new_s: new zoom in exponent form
        :param old_s: old zoom in exponent form
        :param p: point in screen coordinates where to zoom to.

        :return:
        """
        mtc = self.rect().center().toPointF() - p
        current_t = mtc / old_s + self.__position_offset
        new_t = mtc / new_s + self.__position_offset
        self.__position_offset -= new_t - current_t

    @pyqtSlot(QPoint)
    @pyqtSlot(QPointF)
    def move_image(self, p: Union[QPoint, QPointF]):
        """
        Moves the image horizontally by d pixels.

        :param p: shift amt in pixels, + <=> move right.
        :return:
        """
        print(p.x(), p.y())
        self.__position_offset += p.toPointF() if type(p) is QPoint else p
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
            self.reset_image()
            self.update()

    def mouseMoveEvent(self, a0: QMouseEvent) -> None:
        """
        When mouse is moved, move the image accordingly

        :param a0: MouseEvent to extract the movement from.
        :return:
        """
        if self.last_pos is not None:
            delta = a0.globalPosition() - self.last_pos
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.zoom_image(d=delta.toPoint().y())
            else:
                self.move_image(p=delta / (2 ** (1 + self.__scale_offset / 100)))
        self.last_pos = a0.globalPosition()

    @pyqtSlot()
    def reset_image(self):
        """
        Reset Scale and Offset of image.

        :return:
        """
        self.__position_offset = QPointF(0, 0)

        self.recalculate_scale_fitting_scale()

        self.update()

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        When the widget is resized, recalculate the __fitting_scale and set the scale of the image to the fitting scale.

        INFO: Difference to reset_image: don't reset the position_offset
        :param a0:
        :return:
        """
        super().resizeEvent(a0)
        self.recalculate_scale_fitting_scale()

    def recalculate_scale_fitting_scale(self):
        """
        Recompute the __fitting_scale and __scale_offset determined from the size of the pixmap.
        """
        if self.pixmap is None or (self.pixmap is not None and self.pixmap.isNull()):
            self.__scale_offset = 1
            return

        r = QRect(QPoint(),
                  self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))

        try:
            self.__scale_offset = int((math.log2(r.height() / self.pixmap.height()) - 1) * 100)
        except ValueError:
            self.__fitting_scale = 1

        self.__scale_offset = self.__fitting_scale

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
            r.moveCenter(self.rect().center() + self.__position_offset.toPoint() * (2 ** (1 + self.__scale_offset / 100)))
        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)
