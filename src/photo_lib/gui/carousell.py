from PyQt6.QtWidgets import QWidget, QApplication, QScrollArea, QHBoxLayout, QFrame
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent, QResizeEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF, QTimer
import sys
import os
from typing import Union, List
import math
import warnings
from image_tile import ImageTile
from photo_lib.gui.clickable_image import ClickableImage

"""
Information:
This is the first implementation of a basic carousel widget. Features that are missing include:
- Animation
- Abstraction (if the images are outside the displayed area, they should be unloaded. Eventually a large swat of images
should be replaced by a single widget to free even more space.
"""

class Carousel(QScrollArea):
    """
    Carousel widget that displays a list of images and allows the user to scroll through them.
    """

    child_dummy: QWidget
    h_layout: QHBoxLayout
    images: List[ClickableImage]
    current_select: ClickableImage = None

    def __init__(self):
        super().__init__()

        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.child_dummy = QWidget()
        self.setWidget(self.child_dummy)

        self.h_layout = QHBoxLayout()
        self.child_dummy.setLayout(self.h_layout)

        self.images: List[ClickableImage] = []

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Perform resize and set the height of the child widget.
        :param a0:
        :return:
        """
        super().resizeEvent(a0)
        self.child_dummy.setMaximumHeight(a0.size().height())

    def set_image(self, image: ClickableImage):
        """
        Set the image to be displayed and add a Frame around it.
        :param image:
        :return:
        """
        self.ensureWidgetVisible(image)
        self.mark_image(image)

    def mark_image(self, image: ClickableImage):
        """
        Mark the image as selected.
        :param image:
        :return:
        """
        if self.current_select is not None:
            self.unmark_selected()

        self.current_select = image
        self.mark_selected()

    def mark_selected(self):
        """
        Adds a frame around the current_selected image
        :return:
        """
        self.current_select.setFrameStyle(QFrame.Shape.Box)

    def unmark_selected(self):
        """
        Removes the frame around the current_selected image
        :return:
        """
        self.current_select.setFrameStyle(QFrame.Shape.NoFrame)
