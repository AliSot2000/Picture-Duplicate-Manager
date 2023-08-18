from PyQt6.QtWidgets import QWidget, QApplication, QScrollArea, QHBoxLayout, QFrame, QLabel
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent, QResizeEvent, QWheelEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF, QTimer
import sys
import os
from typing import Union, List, Callable
import math
import warnings
from photo_lib.PhotoDatabase import BaseTileInfo
from photo_lib.gui.clickable_image import ClickableTile
from photo_lib.gui.model import Model

"""
Information:
This is the first implementation of a basic carousel widget. Features that are missing include:
- Animation
- Abstraction (if the images are outside the displayed area, they should be unloaded. Eventually a large swat of images
should be replaced by a single widget to free even more space.
"""

def image_wrapper(image: ClickableTile, fn: Callable):
    """
    Given a function and a tile, bake tile as argument into function call for signal.
    :param image: tile to bake in
    :param fn: function to call
    :return:
    """
    def wrapper():
        fn(image=image)
    return wrapper

class Carousel(QScrollArea):
    """
    Carousel widget that displays a list of images and allows the user to scroll through them.
    """

    # Todo config
    # Number of times the size of the scroll area to preload teh images for scrolling.
    preload_amount: int = 10

    child_dummy: QWidget
    h_layout: QHBoxLayout
    images: List[ClickableTile]
    current_select: ClickableTile = None
    image_changed = pyqtSignal()

    model = Model

    def __init__(self, model: Model):
        super().__init__()

        self.model = model
        self.images = []

        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.child_dummy = QWidget()
        self.setWidget(self.child_dummy)

        self.h_layout = QHBoxLayout()
        self.child_dummy.setLayout(self.h_layout)

    def build_carousel(self, target: BaseTileInfo = None):
        """
        Builds the carousel and sets the target image if provided. Otherwise, no image is set.
        :param target:
        :return:
        """
        # Fetch all tiles
        tiles = self.model.tile_infos
        target_i = None

        for i in range(len(tiles)):
        # for i in range(2):
            # Get info
            tile = tiles[i]

            # Create the Widget
            img = ClickableTile()
            img.setFixedHeight(100)
            img.setMinimumWidth(self.height())
            img.tile_info = tile

            # When clicked, set the image to the clicked image
            img.clicked.connect(image_wrapper(img, self.set_image))
            self.images.append(img)
            self.h_layout.addWidget(img)

            # Check for target, if the keys match keep track of the image
            if target is not None and target.key == tile.key:
                target_i = i

        if target_i is not None:
            self.set_image(self.images[target_i])

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Perform resize and set the height of the child widget.
        :param a0:
        :return:
        """
        super().resizeEvent(a0)
        self.child_dummy.setMaximumHeight(self.size().height())
        for img in self.images:
            img.setMinimumWidth(self.height())
            img.setMaximumHeight(self.height())

    def set_image(self, image: ClickableTile):
        """
        Set the image to be displayed and add a Frame around it.
        :param image:
        :return:
        """
        self.ensureWidgetVisible(image)
        self.mark_image(image)
        self.image_changed.emit()

    def mark_image(self, image: ClickableTile):
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
        self.current_select.setStyleSheet("padding: 10px; "
                                           "border: 2px solid black;")

    def unmark_selected(self):
        """
        Removes the frame around the current_selected image
        :return:
        """
        self.current_select.setStyleSheet("padding: 10px; ")

    def wheelEvent(self, a0: QWheelEvent) -> None:
        # TODO update the loaded images
        # Todo placeholders.
        super().wheelEvent(a0)
        print("Wheel event.")

    # Get the position of a widget relative to window origin:
    # widget_pos = label.mapTo(window, label.rect().topLeft())


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Carousel(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.model.build_tiles_from_table()
    window.setWindowTitle("Carousel Test")
    window.build_carousel()
    window.image_changed.connect(lambda x: print(x))
    window.show()
    sys.exit(app.exec())