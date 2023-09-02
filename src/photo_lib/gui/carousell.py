import math

from PyQt6.QtWidgets import QWidget, QApplication, QScrollArea, QGridLayout, QFrame, QLabel
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent, QResizeEvent, QWheelEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF, QTimer
import sys
from typing import List, Union
from photo_lib.PhotoDatabase import BaseTileInfo
from photo_lib.gui.clickable_image import ClickableTile
from photo_lib.gui.model import Model
from photo_lib.gui.gui_utils import image_wrapper
from photo_lib.data_objects import ImportTileInfo
import datetime

"""
Information:
This is the first implementation of a basic carousel widget. Features that are missing include:
- Animation
- Abstraction (if the images are outside the displayed area, they should be unloaded. Eventually a large swat of images
should be replaced by a single widget to free even more space.
"""

class BaseCarousel(QScrollArea):
    image_changed = pyqtSignal()
    images: List[ClickableTile]
    current_select: Union[None, ClickableTile] = None

    def set_tile(self, tile_info: ImportTileInfo):
        """
        Set the currently selected image based on a tile_info object.
        :param tile_info:
        :return:
        """
        for img in self.images:
            if img.tile_info == tile_info:
                self.set_image(img)
                return

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


class Carousel(BaseCarousel):
    """
    Carousel widget that displays a list of images and allows the user to scroll through them.
    """

    # Todo config
    # Number of times the size of the scroll area to preload teh images for scrolling.
    eager_load_limit = 10
    movement_stop_timeout = 50


    child_dummy: QWidget
    g_layout: QGridLayout

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

        self.g_layout = QGridLayout()
        self.child_dummy.setLayout(self.g_layout)
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
        # Empty layout first.
        while self.g_layout.count() > 0:
            self.g_layout.takeAt(0).widget().deleteLater()

        self.current_select = None
        self.images = []

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
            self.g_layout.addWidget(img, 0, i)
            self.g_layout.setColumnStretch(i, 1)

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

    # TODO better datastructure to make this faster but ok for now.
    def vis_from_slider(self, val: int = None):
        """
        Update the visible images based on the slider position.
        :param val: could be used to pass the value of the slider.
        :return:
        """
        # print("Vis Started")
        # start = datetime.datetime.now()
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
            if self.images[i].geometry().topLeft().isNull():
                return
            window_pos = self.images[i].mapTo(self, self.images[i].geometry().topLeft())
            r = QRect(window_pos, self.images[i].size())
            # print(f"Image {i:03}: {'Visible' if visible else 'Not Visible'}")
            if self.rect_vis(r):
                last_left = i
            else:
                break

        # Find right bound
        for i in range(target_image, len(self.images)):
            if self.images[i].geometry().topLeft().isNull():
                return
            window_pos = self.images[i].mapTo(self, self.images[i].geometry().topLeft())
            r = QRect(window_pos, self.images[i].size())
            # print(f"Image {i:03}: {'Visible' if visible else 'Not Visible'}")
            if self.rect_vis(r):
                last_right = i
            else:
                break

        new_left = max(0, last_left - self.eager_load_limit)
        new_right = min(len(self.images), last_right + self.eager_load_limit)
        # end = datetime.datetime.now()
        # print(f"Time needed to compute upper and lower limit: {(end -start).total_seconds()}")
        self.load_unload_visible(new_left, new_right)
        # print("Vis Done")

    def rect_vis(self, r: QRect) -> bool:
        """
        Determine if a rect is within the visible area of the QSrollArea. The coordinates of QRect must be relative to
        origin of the QScrollArea
        :param r: Rect to determine Visibility of
        :return:
        """
        br = self.visibleRegion().boundingRect()
        return br.contains(r.topLeft()) or br.contains(r.bottomRight())

    def load_unload_visible(self, new_left: int, new_right: int):
        """
        Loads and unloads images that are visible and not visible.
        :return:
        """
        # start = datetime.datetime.now()
        # unset right_most_index and left_most_index
        if self.left_most_visible_index == -1 or self.right_most_visible_index == -1:
            # print(f"Load from scratch")
            assert self.left_most_visible_index == -1 and self.right_most_visible_index == -1, "Uneven reset of indexes"
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True
            for i in range(0, new_left):
                self.images[i].image_loaded = False
            for i in range(new_right, len(self.images)):
                self.images[i].image_loaded = False

        # No intersection - unload all and load new
        elif new_left > self.right_most_visible_index or new_right < self.left_most_visible_index:
            # print("Load no intersect")
            for i in range(self.left_most_visible_index, self.right_most_visible_index):
                self.images[i].image_loaded = False
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True

        # Shift view to the right
        elif self.left_most_visible_index <= new_left <= self.right_most_visible_index:
            # print(f"Load Left in middle")
            for i in range(self.left_most_visible_index, new_left):
                self.images[i].image_loaded = False
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True

        # Shift view to the left
        elif self.left_most_visible_index <= new_right <= self.right_most_visible_index:
            # print(f"Load Right in middle")
            for i in range(new_left, new_right):
                self.images[i].image_loaded = True
            for i in range(new_right, self.right_most_visible_index):
                self.images[i].image_loaded = False
        self.left_most_visible_index = new_left
        self.right_most_visible_index = new_right
        # end = datetime.datetime.now()
        # print(f"Time needed to load and unload images: {(end - start).total_seconds()}")




    # Get the position of a widget relative to window origin:
    # widget_pos = label.mapTo(window, label.rect().topLeft())

class TemplatingCarousel(BaseCarousel):
    """
    Carousel widget that displays a list of images and allows the user to scroll through them.
    """

    # Todo config
    # Number of times the size of the scroll area to preload the images for scrolling.
    __preload_count = 50
    movement_stop_timeout = 50
    total_image_count: int = 0
    current_select_ti: BaseTileInfo = None

    left_dummy: QWidget
    right_dummy: QWidget
    child_dummy: QWidget
    g_layout: QGridLayout

    model = Model

    timer: QTimer = None

    @property
    def preload_count(self):
        return self.__preload_count

    @preload_count.setter
    def preload_count(self, val):
        assert val > 0, "Preload count must be greater than 0"
        self.__preload_count = val
        self.vis_from_pos(rebuild=True)

    def __init__(self, model: Model):
        super().__init__()

        self.model = model
        self.images = []

        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.left_dummy = QWidget()
        self.right_dummy = QWidget()

        self.child_dummy = QWidget()
        self.setWidget(self.child_dummy)

        self.g_layout = QGridLayout()
        self.child_dummy.setLayout(self.g_layout)

        self.horizontalScrollBar().valueChanged.connect(self.schedule_update_load)
        self.horizontalScrollBar().sliderMoved.connect(self.schedule_update_load)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.vis_from_pos)
        self.init_widgets()

    def init_widgets(self):
        """
        Builds the carousel and sets the target image if provided. Otherwise, no image is set.
        :param target:
        :return:
        """
        self.update_image_count()

        self.images = []

        for i in range(self.preload_count * 2):
            # Create the Widget
            img = ClickableTile()
            img.setFixedHeight(self.height())
            img.setFixedWidth(self.height())

            # When clicked, set the image to the clicked image
            img.clicked.connect(image_wrapper(img, self.set_image))
            self.images.append(img)
            self.g_layout.addWidget(img, 0, i + 1)


    def update_image_count(self):
        self.total_image_count = self.model.get_total_image_count()

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Perform resize and set the height of the child widget.
        :param a0:
        :return:
        """
        super().resizeEvent(a0)
        self.child_dummy.setMaximumHeight(self.size().height())
        self.left_dummy.setMaximumHeight(self.size().height())
        self.right_dummy.setMaximumHeight(self.size().height())
        for img in self.images:
            img.setFixedHeight(self.height())
            img.setFixedWidth(self.height())

    def set_tile(self, tile_info: BaseTileInfo):
        """
        Set the currently selected image based on a tile_info object.
        :param tile_info:
        :return:
        """
        for img in self.images:
            if img.tile_info == tile_info:
                self.set_image(img)
                return
        self.current_select_ti = tile_info

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

    def schedule_update_load(self, val: int):
        """
        Schedule the update of the loaded images.

        :param val: needed to attach to signal
        :return:
        """
        self.timer.start(self.movement_stop_timeout)

    def vis_from_pos(self, rebuild: bool = False):
        """
        Compute visibility from position and update the images.

        :param rebuild: If true, generate new ClickableTiles for the iteration of the process.
        :return:
        """
        if self.g_layout.indexOf(self.left_dummy) != -1:
            left_most_x = self.left_dummy.mapTo(self, self.left_dummy.geometry().topLeft()).x()
        else:
            left_most_x = self.images[0].mapTo(self, self.images[0].geometry().topLeft()).x()

        x_spacing = self.g_layout.spacing()
        num_of_left_images = math.floor(-left_most_x / (self.height() + x_spacing))

        # Determine starting image, make sure it is not negative and loads still all images even if we are scrolled
        # maximal to the right
        right_most_start = self.total_image_count - 2*self.preload_count
        if right_most_start <= 0:
            start = max(num_of_left_images - self.preload_count, 0)
        else:
            left_most_start = max(num_of_left_images - self.preload_count, 0)
            if left_most_start > right_most_start:
                start = right_most_start
            else:
                start = left_most_start

        tiles = self.model.get_images_carousel(start=start, count=self.preload_count * 2)

        if self.current_select is not None:
            self.unmark_selected()

        # Not rebuiling, simply assign new values
        if not rebuild:
            self.current_select = None
            for i in range(len(tiles)):
                self.images[i].tile_info = tiles[i]
                if self.current_select_ti is not None and tiles[i].key == self.current_select_ti.key:
                    self.current_select = self.images[i]
        # Rebuilding, need to create new widgets
        else:
            for img in self.images:
                img.deleteLater()

            # Create new images
            for i in range(len(tiles)):
                img = ClickableTile()
                img.setFixedHeight(self.height())
                img.setFixedWidth(self.height())
                img.tile_info = tiles[i]
                img.clicked.connect(image_wrapper(img, self.set_image))
                self.images.append(img)
                if tiles[i].key == self.current_select_ti.key:
                    self.current_select = self.images[i]

        if self.current_select is not None:
            self.mark_selected()

        # TODO smart update, only update the layout completely if necessary
        # Empty layout
        while self.g_layout.count() > 0:
            self.g_layout.takeAt(0)

        # Add dummy if necessary
        if num_of_left_images - self.preload_count > 0:
            self.g_layout.addWidget(self.left_dummy, 0, 0)
            self.left_dummy.setFixedWidth(self.height() * (num_of_left_images - self.preload_count) + x_spacing * (num_of_left_images - self.preload_count - 1))

        # Add images
        for i in range(len(tiles)):
            self.g_layout.addWidget(self.images[i], 0, i + 1)
        pos = min(len(tiles) + 1, self.preload_count * 2 + 1)
        # Add right dummy if necessary
        if self.total_image_count - num_of_left_images - self.preload_count > 0:
            right_count = self.total_image_count - num_of_left_images - self.preload_count
            self.g_layout.addWidget(self.right_dummy, 0, pos)
            self.right_dummy.setFixedWidth(self.height() * right_count + x_spacing * (right_count - 1))
        print("Done")


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