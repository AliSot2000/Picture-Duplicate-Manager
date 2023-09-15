import math

from PyQt6.QtWidgets import QWidget, QApplication, QScrollArea, QGridLayout, QFrame, QLabel, QScrollBar, QVBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QFont, QEnterEvent, QMouseEvent, QResizeEvent, QWheelEvent, QKeyEvent, QColor
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent, pyqtSlot, QSize, QPointF, QTimer, pyqtSlot
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
    timer: QTimer = None

    movement_stop_timeout = 50

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.setSingleShot(True)

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

    child_dummy: QWidget
    g_layout: QGridLayout

    model = Model

    left_most_visible_index: int = -1
    right_most_visible_index: int = -1

    # Load 10 images to the left and right of current view.

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

        self.horizontalScrollBar().valueChanged.connect(self.schedule_update_load)
        self.horizontalScrollBar().sliderMoved.connect(self.schedule_update_load)

        self.timer.timeout.connect(self.vis_from_slider)
        self.schedule_update_load(2)

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
            img.image_loaded = False
            img.tile_info = tile

            # When clicked, set the image to the clicked image
            img.clicked.connect(image_wrapper(img, self.set_image))
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
            img.setMaximumHeight(self.height())
            img.setMinimumWidth(self.height())

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

        # Walk left
        last_left = target_image
        last_right = target_image
        print("------------------------------------------------")

        # Find left bound
        for i in range(target_image, -1, -1):
            if self.images[i].geometry().topLeft().isNull():
                return
            window_pos = self.images[i].mapTo(self, self.images[i].geometry().topLeft())
            r = QRect(window_pos, self.images[i].size())
            # print(f"Image {i:03}: {'Visible' if visible else 'Not Visible'}")
            if self.rect_vis(r):
                print(self.images[i].mapTo(self, self.images[i].geometry().topLeft()))
                print(self.images[i].mapTo(self, self.images[i].rect().topLeft()))
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
                print(self.images[i].mapTo(self, self.images[i].geometry().topLeft()))
                print(self.images[i].mapTo(self, self.images[i].rect().topLeft()))
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


class MyLabel(QLabel):
    __index: int = None

    @property
    def index(self):
        return self.__index

    @index.setter
    def index(self, value: int):
        if value == self.__index:
            return

        self.__index = value
        self.setText(f"Label: {self.__index} ")


class RecyclingCarousel(QFrame):
    spacing: int = 5
    center_spacing: float = 0.1
    wrapp_around_buffer: int = 2

    __number_of_elements: int = 100
    __current_element: int = 0
    __page_size: int = 0

    widgets: List[MyLabel] = None
    center_widget: int = 0

    model: Model

    # Signals
    image_changed = pyqtSignal(int)
    noe_changed = pyqtSignal(int)

    @property
    def page_size(self):
        return self.__page_size

    @property
    def current_element(self):
        return self.__current_element

    @current_element.setter
    def current_element(self, value: int):
        if self.__current_element == value:
            return

        assert value >= 0 or value < self.number_of_elements, f"Value out of bounds [0, {self.number_of_elements}]"
        self.__current_element = value
        self.image_changed.emit(value)

    @property
    def number_of_elements(self):
        return self.__number_of_elements

    @number_of_elements.setter
    def number_of_elements(self, value: int):
        if self.__number_of_elements == value:
            return

        assert value >= 0, "Number of elements must be positive"
        self.__number_of_elements = value
        self.noe_changed.emit(value)

    def __init__(self, model: Model):
        super().__init__()
        self.model = model
        self.widgets = []
        self.setMinimumHeight(100)

        w = MyLabel()
        w.index = 0
        col = QColor.fromHsvF(0.0, 1.0, 1.0)
        s = f"background-color: rgba{col.getRgb()}"
        w.setStyleSheet(s)
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setFixedWidth(100)
        w.setFixedHeight(100)
        self.widgets.append(w)
        w.setParent(self)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Updates the sizes of the widgets and the scrollbar
        """
        super().resizeEvent(a0)

        # Update number of visible tile
        self.update_widget_count()

        tile_size = self.height()
        for i in range(len(self.widgets)):
            self.widgets[i].setFixedHeight(tile_size)
            self.widgets[i].setFixedWidth(tile_size)

        self.layout_widgets()

    def number_of_widgets(self):
        """
        Compute the number of widgets that need to be present to fill the size of the widget..
        :return:
        """
        # Default tile size
        tile_size = self.height()

        # Remove the center widget, the center spacing and the margins
        remaining_width = max(self.width() - tile_size - 2 * self.center_spacing * tile_size, 0)

        # Divide to get only one side
        remaining_width /= 2

        # Number of widgets that fit one side
        widgets = remaining_width / (tile_size + self.spacing)
        return int(widgets + self.wrapp_around_buffer) * 2 + 1

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """
        Catch keys from keyboard and move the carousel accordingly.
        :param a0:
        :return:
        """
        super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Left:
            self.move_left()
            self.layout_widgets()
        elif a0.key() == Qt.Key.Key_Right:
            self.move_right()
            self.layout_widgets()

    @pyqtSlot()
    def move_left(self):
        """
        Moves images one to the left.
        :return:
        """
        last = self.widgets[-1]
        first = self.widgets[0]
        if self.center_widget != len(self.widgets) // 2:
            # we are at the right threshold
            if self.center_widget > len(self.widgets) // 2:
                self.center_widget -= 1
                # Needs to be assigned last - otherwise infinite recursion because of incomplete move
                self.current_element -= 1
                return
            # we're at the left threshold but not at the left most image
            elif 0 < self.center_widget < len(self.widgets) // 2:
                self.center_widget -= 1
                # Needs to be assigned last - otherwise infinite recursion because of incomplete move
                self.current_element -= 1
                return
            # We're at the left most image
            else:
                return

        # More images to load to the left
        if first.index > 0:
            last.index = first.index -1
            col = QColor.fromHsvF((last.index / self.number_of_elements), 1.0, 1.0)
            self.widgets = [last] + self.widgets[:-1]
            s = f"background-color: rgba{col.getRgb()}"
            last.setStyleSheet(s)
            # Needs to be assigned last - otherwise infinite recursion because of incomplete move
            self.current_element -= 1
            return

        # Nothing left to the left, asymmetric display.
        assert first.index == 0, "First index is not 0"
        assert self.center_widget == len(self.widgets) // 2, "Center widget is not in the middle"
        self.center_widget -= 1
        # Needs to be assigned last - otherwise infinite recursion because of incomplete move
        self.current_element -= 1

    @pyqtSlot()
    def move_right(self):
        """
        Moves images one to the right.
        :return:
        """
        last = self.widgets[-1]
        first = self.widgets[0]
        if self.center_widget != len(self.widgets) // 2:
            # we are at the right threshold but not at the right most image
            if len(self.widgets) - 1 > self.center_widget > len(self.widgets) // 2:
                self.center_widget += 1
                # Needs to be assigned last - otherwise infinite recursion because of incomplete move
                self.current_element += 1
                return
            # we're at the left threshold
            elif self.center_widget < len(self.widgets) // 2:
                self.center_widget += 1
                # Needs to be assigned last - otherwise infinite recursion because of incomplete move
                self.current_element += 1
                return
            # We're at the right most image
            else:
                return

        # More images to load to the left
        if last.index < self.number_of_elements - 1:
            first.index = last.index + 1
            col = QColor.fromHsvF((first.index / self.number_of_elements), 1.0, 1.0)
            s = f"background-color: rgba{col.getRgb()}"
            first.setStyleSheet(s)
            self.widgets = self.widgets[1:] + [first]
            # Needs to be assigned last - otherwise infinite recursion because of incomplete move
            self.current_element += 1
            return

        # Nothing left to the left, asymmetric display.
        assert last.index == self.number_of_elements - 1, "First index is not 0"
        assert self.center_widget == len(self.widgets) // 2, "Center widget is not in the middle"
        self.center_widget += 1
        # Needs to be assigned last - otherwise infinite recursion because of incomplete move
        self.current_element += 1

    @pyqtSlot(int)
    def move_to_specific_image(self, index: int):
        """
        Moves the carousel to a specific image.

        Warning This triggers the signals. DO NOT CONNECT THIS FUNCTION TO Another signal! Use the slots.
        :param index:
        :return:
        """
        if index < 0 or index > self.number_of_elements:
            raise ValueError(f"Index out of bounds [0, {self.number_of_elements}]")

        if self.widgets[self.center_widget].index == index:
            return
        elif self.widgets[self.center_widget].index == index + 1:
            self.move_left()
            self.layout_widgets()
        elif self.widgets[self.center_widget].index == index - 1:
            self.move_right()
            self.layout_widgets()

        # outside bounds
        if (self.widgets[self.center_widget].index < self.widgets[0].index or
                self.widgets[self.center_widget].index > self.widgets[-1].index):

            # Assign new values
            self.widgets[self.center_widget].index = index
            for i in range(self.center_widget + 1, len(self.widgets)):
                self.widgets[i].index = self.widgets[i-1].index + 1

            for i in range(self.center_widget - 1, -1, -1):
                self.widgets[i].index = self.widgets[i+1].index - 1

            # update colors
            for i in range(len(self.widgets)):
                ind = self.widgets[i].index
                col = QColor.fromHsvF(((ind) / self.number_of_elements), 1.0, 1.0)
                s = f"background-color: rgba{col.getRgb()}"
                self.widgets[i].setStyleSheet(s)

            # Needs to be assigned last - otherwise infinite recursion because of incomplete move
            self.current_element = index
            return

        # inside bounds
        if self.widgets[self.center_widget].index < index:
            while self.widgets[self.center_widget].index < index:
                self.move_right()
            self.layout_widgets()

        elif self.widgets[self.center_widget].index > index:
            while self.widgets[self.center_widget].index > index:
                self.move_left()
            self.layout_widgets()

    @pyqtSlot()
    def move_left_page(self):
        """
        Moves one page to the left. Sets the left most visible widget as the current center widget.
        """
        new_image = max(self.current_element - self.page_size, 0)
        self.move_to_specific_image(new_image)

    @pyqtSlot()
    def move_right_page(self):
        """
        Moves one page to the right. Sets the right most visible widget as the current center widget.
        """
        new_image = min(self.number_of_elements - 1, self.current_element + self.page_size)
        self.move_to_specific_image(new_image)

    @pyqtSlot()
    def move_to_right_limit(self):
        """
        Moves to the right limit.
        """
        self.move_to_specific_image(self.number_of_elements - 1)

    @pyqtSlot()
    def move_to_left_limit(self):
        """
        Moves to the left limit
        """
        self.move_to_specific_image(0)

    def layout_widgets(self):
        """
        Layout the widgets in the carousel.
        :return:
        """
        w = self.widgets[self.center_widget].width()
        self.widgets[self.center_widget].move(QPoint(self.width() // 2 - w // 2, 0))
        center = self.width() // 2

        for i in range(0, self.center_widget):
            k = self.center_widget - i -1
            x_l = center - w / 2 - self.spacing * k - w * (k + 1) - w * self.center_spacing
            self.widgets[i].move(QPoint(x_l, 0))

        for i in range(self.center_widget + 1, len(self.widgets)):
            k = i - self.center_widget - 1
            x_r = center + w / 2 + self.spacing * k + w * k + w * self.center_spacing
            self.widgets[i].move(QPoint(x_r, 0))

    def update_widget_count(self):
        """
        Updates the available widgets for recirculation if the number of widgets needs to change.
        :return:
        """
        now = self.number_of_widgets()
        if len(self.widgets) == now:
            return

        # Number of widgets needs to change
        if len(self.widgets) > now:
            # we are not at a threshold:
            if self.center_widget == len(self.widgets) // 2:
                self.widgets[0].deleteLater()
                self.widgets[-1].deleteLater()
                self.widgets = self.widgets[1:-1]
                self.center_widget = self.center_widget -1
                return

            # we're at a threshold and it's the left one
            if self.center_widget < len(self.widgets) // 2:
                self.widgets[-1].deleteLater()
                self.widgets[-2].deleteLater()
                self.widgets = self.widgets[:-2]
                return

            # we're at a threshold and it's the right one
            assert self.center_widget > len(self.widgets) // 2, "Center widget is not at a threshold"
            self.widgets[0].deleteLater()
            self.widgets[1].deleteLater()
            self.widgets = self.widgets[2:]
            return

        # Have as many widgets as we have elements
        if len(self.widgets) == self.number_of_elements:
            return

        c = self._add_widgets()
        if c == 2:
            self.center_widget += 1
        if c < 2 and len(self.widgets) < self.number_of_elements:
            c += self._add_widgets()
            assert c == 2, "Not enough widgets added"

    def _add_widgets(self):
        """
        Adds widgets to the carousel.
        :return:
        """
        count = 0
        if self.widgets[0].index > 0:
            w = MyLabel()
            w.setParent(self)
            col = QColor.fromHsvF(((self.widgets[0].index - 1) / self.number_of_elements), 1.0, 1.0)
            s = f"background-color: rgba{col.getRgb()}"
            w.setStyleSheet(s)
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w.setVisible(True)
            self.widgets = [w] + self.widgets
            self.widgets[0].index = self.widgets[1].index - 1
            count += 1

        if self.widgets[-1].index < self.number_of_elements - 1:
            w = MyLabel()
            w.setParent(self)
            col = QColor.fromHsvF(((self.widgets[-1].index + 1) / self.number_of_elements), 1.0, 1.0)
            s = f"background-color: rgba{col.getRgb()}"
            w.setStyleSheet(s)
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w.setVisible(True)
            self.widgets.append(w)
            self.widgets[-1].index = self.widgets[-2].index + 1
            count += 1

        return count


class PotentCarousel(QFrame):
    # TODO config
    margin: int = 10
    scrollbar_height: int = 15
    # wrap_around_buffer - number of images that are loaded to the left and the right of the view (outside fov)
    # Sensible values are 1-3

    sc: QScrollBar

    model: Model

    carouse_area: RecyclingCarousel

    __scrollbar_present: bool = True

    def __init__(self, model: Model):
        super().__init__()
        self.model = model

        self.carouse_area = RecyclingCarousel(model)
        self.carouse_area.setParent(self)

        self.sc = QScrollBar(Qt.Orientation.Horizontal)
        self.sc.setParent(self)
        self.sc.setRange(0, self.carouse_area.number_of_elements - 1)
        self._update_layout()
        self._initial_placement()
        self.sc.valueChanged.connect(self.carouse_area.move_to_specific_image)
        self.sc.valueChanged.connect(lambda x: print(x))
        self.carouse_area.image_changed.connect(self.sc.setValue)
        self.carouse_area.image_changed.connect(lambda x: print(x))

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """
        Catch keys from keyboard and move the carousel accordingly.
        :param a0:
        :return:
        """
        super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Left:
            self.carouse_area.move_left()
        elif a0.key() == Qt.Key.Key_Right:
            self.carouse_area.move_right()
        elif a0.key() == Qt.Key.Key_Up:
            self.carouse_area.move_to_right_limit()
        elif a0.key() == Qt.Key.Key_Down:
            self.carouse_area.move_to_left_limit()
        elif a0.key() == Qt.Key.Key_End:
            self.carouse_area.move_to_right_limit()
        elif a0.key() == Qt.Key.Key_Home:
            self.carouse_area.move_to_left_limit()
        elif a0.key() == Qt.Key.Key_PageUp:
            self.carouse_area.move_right_page()
        elif a0.key() == Qt.Key.Key_PageDown:
            self.carouse_area.move_left_page()
        else:
            pass
        self.carouse_area.layout_widgets()

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Updates the sizes of the widgets and the scrollbar
        """
        super().resizeEvent(a0)

        self.sc.setFixedWidth(self.width())
        # TODO update number of visible images.

        # Change, visibility of scrollbar and presence of it
        if self.__scrollbar_present and self.carouse_area.number_of_elements <= 1:
            self.sc.setVisible(False)
            self.__scrollbar_present = False

        # Change, visibility of scrollbar and presence of it
        if not self.__scrollbar_present and self.carouse_area.number_of_elements > 1:
            self.sc.setVisible(True)
            self.__scrollbar_present = True

        self._update_layout()

    def _update_layout(self):
        """
        Update the layout of all widgets which make up the carousel
        """
        # Scrollbar is present
        if self.__scrollbar_present:
            self.sc.move(QPoint(0, self.height() - self.scrollbar_height))

            tile_size = self.height() - self.margin * 2 - self.scrollbar_height

        # Scrollbar is not present
        else:
            tile_size = self.height() - self.margin * 2

        self.carouse_area.setFixedHeight(tile_size)
        self.carouse_area.setFixedWidth(self.width() - 2 * self.margin)

    def _initial_placement(self):
        """
        Placd the widgets in the default locations
        """
        self.carouse_area.move(QPoint(self.margin, self.margin))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    m = Model(folder_path="/media/alisot2000/DumpStuff/work_dummy/")
    # m.current_import_table_name = "tbl_-3399138825726121575"
    m.build_tiles_from_table()
    window = PotentCarousel(m)
    # window = RecyclingCarousel(m)
    # window = TestingTamplatingCarousel(m)
    # window.build_carousel()
    window.setWindowTitle("Carousel Test")
    # window.image_changed.connect(lambda x: print(x))
    window.show()
    sys.exit(app.exec())
