import sys
from typing import List

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QResizeEvent, QKeyEvent, QColor
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QScrollBar

from photo_lib.gui.model import Model


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

        # Remove the center widget, the center spacing and the margins
        remaining_width = max(self.width() - tile_size - 2 * self.center_spacing * tile_size, 0)

        # Divide to get only one side
        remaining_width /= 2

        # Number of widgets that fit one side
        self.__page_size = int(remaining_width / (tile_size + self.spacing))

        self.layout_widgets()

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
            last.index = first.index - 1
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
                self.widgets[i].index = self.widgets[i - 1].index + 1

            for i in range(self.center_widget - 1, -1, -1):
                self.widgets[i].index = self.widgets[i + 1].index - 1

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
            k = self.center_widget - i - 1
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
        now = int(self.page_size + self.wrapp_around_buffer) * 2 + 1
        if len(self.widgets) == now:
            return

        # Number of widgets needs to change
        if len(self.widgets) > now:
            # we are not at a threshold:
            if self.center_widget == len(self.widgets) // 2:
                self.widgets[0].deleteLater()
                self.widgets[-1].deleteLater()
                self.widgets = self.widgets[1:-1]
                self.center_widget = self.center_widget - 1
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


class CarouselView(QFrame):
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
    # m = Model(folder_path="/media/alisot2000/DumpStuff/work_dummy/")
    m = Model(folder_path="/home/alisot2000/Desktop/New_DB/")
    # m.current_import_table_name = "tbl_-3399138825726121575"
    m.build_tiles_from_table()
    window = CarouselView(m)
    # window = RecyclingCarousel(m)
    # window = TestingTamplatingCarousel(m)
    # window.build_carousel()
    window.setWindowTitle("Carousel Test")
    # window.image_changed.connect(lambda x: print(x))
    window.show()
    sys.exit(app.exec())
