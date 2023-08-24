from PyQt6.QtWidgets import QWidget, QApplication, QScrollArea, QHBoxLayout, QFrame, QLabel
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent, QResizeEvent, QWheelEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF, QTimer
import sys
from typing import List
from photo_lib.PhotoDatabase import BaseTileInfo
from photo_lib.gui.clickable_image import ClickableTile
from photo_lib.gui.model import Model
from photo_lib.gui.gui_utils import image_wrapper

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

    # Todo config
    # Number of times the size of the scroll area to preload teh images for scrolling.
    eager_load_limit = 10
    movement_stop_timeout = 50


    child_dummy: QWidget
    h_layout: QHBoxLayout
    images: List[ClickableTile]
    current_select: ClickableTile = None
    image_changed = pyqtSignal()

    model = Model

    left_most_visible_index: int = -1
    right_most_visible_index: int = -1

    # Load 10 images to the left and right of current view.

    timer: QTimer = None

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
        self.vis_from_slider(0)

        self.horizontalScrollBar().valueChanged.connect(self.schedule_update_load)
        self.horizontalScrollBar().sliderMoved.connect(self.schedule_update_load)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.vis_from_slider)

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
            img.image_loaded = False
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

        # if len(self.images) > 0 and self.images is not None:
        #     print(self.images[0].mapTo(self,
        #                                self.images[0].rect().topLeft()))

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

    def schedule_update_load(self, val: int):
        """
        Schedule the update of the loaded images.

        :param val: needed to attach to signal
        :return:
        """
        self.timer.start(self.movement_stop_timeout)

    def vis_from_slider(self, val: int = None):
        """
        Update the visible images based on the slider position.
        :param val: could be used to pass the value of the slider.
        :return:
        """
        if val is None:
            val = self.horizontalScrollBar().value()

        if len(self.images) == 0 or self.images is None:
            return

        target_image = int(min(val / max(1, self.horizontalScrollBar().maximum() - self.horizontalScrollBar().minimum()) *
                        len(self.images), len(self.images) - 1))

        # print("------------------------------------------------")
        # Walk left
        last_left = target_image
        last_right = target_image

        # Find left bound
        for i in range(target_image, -1, -1):
            window_pos = self.images[i].mapTo(self, self.images[i].rect().topLeft())
            r = QRect(window_pos, self.images[i].size())
            # print(f"Image {i:03}: {'Visible' if visible else 'Not Visible'}")
            if self.rect_vis(r):
                last_left = i
            else:
                break

        # Find right bound
        for i in range(target_image, len(self.images)):
            window_pos = self.images[i].mapTo(self, self.images[i].rect().topLeft())
            r = QRect(window_pos, self.images[i].size())
            # print(f"Image {i:03}: {'Visible' if visible else 'Not Visible'}")
            if self.rect_vis(r):
                last_right = i
            else:
                break

        new_left = max(0, last_left - self.eager_load_limit)
        new_right = min(len(self.images), last_right + self.eager_load_limit)
        self.load_unload_visible(new_left, new_right)

    def rect_vis(self, r: QRect) -> bool:
        """
        Determine if a rect is within the visible area of the QSrollArea. The coordinates of QRect must be relative to
        origin of the QScrollArea
        :param r: Rect to determine Visibility of
        :return:
        """
        br = self.visibleRegion().boundingRect()
        return br.contains(r.topLeft()) or br.contains(r.bottomRight())

    # def wheelEvent(self, a0: QWheelEvent) -> None:
    #     # Todo placeholders.
    #     super().wheelEvent(a0)
    #     left_found = False
    #     new_left = 0
    #     new_right = 0
    #
    #     for i in range(self.left_most_visible_index, self.right_most_visible_index):
    #         if not left_found and self.visibleRegion().intersected(self.images[i].geometry()):
    #             left_found = True
    #             new_left = max(0, i - self.eager_load_limit)
    #
    #         if left_found and not self.visibleRegion().intersected(self.images[i].geometry()):
    #             new_right = min(len(self.images), i + self.eager_load_limit)
    #             break
    #
    #     self.load_unload_visible(new_left, new_right)

    def load_unload_visible(self, new_left: int, new_right: int):
        """
        Loads and unloads images that are visible and not visible.
        :return:
        """
        # unset right_most_index and left_most_index
        if self.left_most_visible_index == -1 or self.right_most_visible_index == -1:
            assert self.left_most_visible_index == -1 and self.right_most_visible_index == -1, "Uneven reset of indexes"
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True
            for i in range(0, new_left):
                self.images[i].image_loaded = False
            for i in range(new_right, len(self.images)):
                self.images[i].image_loaded = False

        # No intersection - unload all and load new
        elif new_left > self.right_most_visible_index or new_right < self.left_most_visible_index:
            for i in range(self.left_most_visible_index, self.right_most_visible_index):
                self.images[i].image_loaded = False
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True

        # Shift view to the right
        elif self.left_most_visible_index <= new_left <= self.right_most_visible_index:
            for i in range(self.left_most_visible_index, new_left):
                self.images[i].image_loaded = False
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True

        # Shift view to the left
        elif self.left_most_visible_index <= new_right <= self.right_most_visible_index:
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True
            for i in range(new_right, self.right_most_visible_index):
                self.images[i].image_loaded = False
        self.left_most_visible_index = new_left
        self.right_most_visible_index = new_right





    # Get the position of a widget relative to window origin:
    # widget_pos = label.mapTo(window, label.rect().topLeft())


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = Carousel(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.model.build_tiles_from_table()
    window.setWindowTitle("Carousel Test")
    window.build_carousel()
    # window.image_changed.connect(lambda x: print(x))
    window.show()
    sys.exit(app.exec())