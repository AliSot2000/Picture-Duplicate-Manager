import warnings
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QGridLayout, QScrollArea, QPushButton, QLabel, \
    QSplitter, QMainWindow, QScrollBar, QHBoxLayout
from PyQt6.QtCore import pyqtSlot, pyqtSignal, Qt, QPoint, QTimer
from PyQt6.QtGui import QResizeEvent, QKeyEvent
import sys
import datetime
import math
import numpy as np
from typing import Union, List, Tuple
from photo_lib.gui.named_picture_block import CheckNamedPictureBlock
from photo_lib.gui.image_tile import ImageTile
from photo_lib.gui.image_tile import IndexedTile
from photo_lib.gui.model import Model, GroupCount, GroupingCriterion, TileBuffer
from photo_lib.PhotoDatabase import MatchTypes
from photo_lib.gui.gui_utils import general_wrapper
from photo_lib.data_objects import ImportTileInfo, BaseTileInfo


use_timers_resize = True
use_timers_scroll = False


# TODO register clickable tiles to emmit the img_selected signal
class TileWidget(QFrame):
    # Backend objects
    model: Model
    buffer: TileBuffer
    scroll_buffer: Union[int, None] = None

    # Signals
    num_of_rows_changed = pyqtSignal(int)
    # num_of_cols_changed = pyqtSignal(int)
    # img_selected = pyqtSignal()  # read the current_element from the object
    focus_row_changed = pyqtSignal(int)

    # Properties about the view, writable
    __number_of_visible_rows = 0
    __number_of_columns = 0
    __focus_row = 0
    __number_of_rows = 0

    # Properties about the view, read only
    __number_of_generated_rows = 0
    __focus_index: int = 0
    # __current_index = 0
    # __current_tile_info: Union[BaseTileInfo, None] = None

    # Further properties that don't need to be set
    scroll_offset: int = 0
    min_number_of_visible_rows: int = 0

    focus_row_offset: int = 0

    lowest_row: int = 0
    highest_row: int = 0

    # Layout
    # TODO config
    tile_size: int = 100  # Different tile size for year, month and day.
    preload_row_count: int = 5
    label_height: int = 30
    scroll_timeout: int = 300
    resize_timeout: int = 200
    header_height: int = 35
    __margin: Tuple[int, int, int, int] = (10, 10, 10, 10)  # left, top, right, bottom
    # TODO font size

    # lookup tables
    group_infos: np.ndarray
    row_to_index_lut: np.ndarray    # Given a row -> gives the start index that are displayed there
    index_to_row_lut: np.ndarray    # given an index -> gives the row that contains this index
    row_to_header_lut: np.array     # given a row -> gives the header for that row

    widgets: List[IndexedTile] = None  # List of all widgets that are currently instantiated
    hidden_widgets: List[IndexedTile] = None  # Widgets that are currently hidden
    widget_rows: List[List[IndexedTile]] = None
    layout_rows: List[Union[QFrame, List[IndexedTile]]] = None
    background_widget: QWidget = None
    background_layout: QGridLayout = None

    # ------------------------------------------------------------------------------------------------------------------
    # Read/Write Properties
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def margin(self):
        return self.__margin

    @margin.setter
    def margin(self, value: Tuple[int, int, int, int]):
        if value == self.__margin:
            return

        self.__margin = value
        self.update_size()

    @property
    def max_number_of_visible_rows(self):
        return self.__number_of_visible_rows

    @max_number_of_visible_rows.setter
    def max_number_of_visible_rows(self, value: int):
        assert value > 0, "Number of visible rows must be greater than 0"
        if value == self.__number_of_visible_rows:
            return

        self.__number_of_visible_rows = value
        self.__number_of_generated_rows = value + 2 * self.preload_row_count

    @property
    def number_of_columns(self):
        return self.__number_of_columns

    @number_of_columns.setter
    def number_of_columns(self, value: int):
        assert value > 0, "Number of elements per column must be greater than 0"
        if value == self.__number_of_columns:
            return

        self.__number_of_columns = value
        # self.num_of_cols_changed.emit(self.__number_of_columns)

    @property
    def focus_row(self):
        return self.__focus_row

    @focus_row.setter
    def focus_row(self, value: int):
        assert value >= 0, "Current row must be greater than or equal to 0"
        if value == self.__focus_row:
            return

        self.__focus_row = value
        self.__focus_index = self.row_to_index_lut[value]
        self.focus_row_changed.emit(value)

    # @property
    # def current_tile_info(self):
    #     return self.__current_tile_info
    #
    # @current_tile_info.setter
    # def current_tile_info(self, value: IndexedTile):
    #     if value.tile_info == self.__current_tile_info:
    #         return
    #
    #     self.__current_tile_info = value.tile_info
    #     self.__current_index = value.index
    #     self.img_selected.emit()

    @property
    def number_of_rows(self):
        return self.__number_of_rows

    @number_of_rows.setter
    def number_of_rows(self, value: int):
        assert value >= 0, "Number of rows must be greater than or equal to 0"
        if value == self.__number_of_rows:
            return

        self.__number_of_rows = value
        self.num_of_rows_changed.emit(value)

    # ------------------------------------------------------------------------------------------------------------------
    # Read Properties
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def number_of_generated_rows(self):
        return self.__number_of_generated_rows

    # @property
    # def current_index(self):
    #     return self.__current_index

    @property
    def focus_index(self):
        return self.__focus_index

    # ------------------------------------------------------------------------------------------------------------------
    # Main Methods
    # ------------------------------------------------------------------------------------------------------------------

    def __init__(self, model: Model):
        super().__init__()
        self.model = model
        self.buffer = TileBuffer(model)
        self.resizeEvent = self.__init_resize_event

        self.group_infos = np.array([])
        self.row_to_index_lut = np.array([])
        self.index_to_row_lut = np.array([])
        self.row_to_header_lut = np.array([])

        self.widgets = []
        self.hidden_widgets = []
        self.widget_rows = []
        self.layout_rows = []

        self.background_widget = QWidget(self)
        self.background_widget.move(QPoint(0, 0))
        self.background_widget.setStyleSheet("background-color: rgb(255, 255, 100);")

        self.background_layout = QGridLayout()
        self.background_layout.setContentsMargins(0, 0, 0, 0)
        self.background_layout.setVerticalSpacing(10)
        self.background_layout.setHorizontalSpacing(10)

        self.background_widget.setLayout(self.background_layout)

        global use_timers_resize
        global use_timers_scroll

        if use_timers_resize:
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.update_size)

        if use_timers_scroll:
            self.scroll_timer = QTimer()
            self.scroll_timer.setSingleShot(True)
            self.scroll_timer.timeout.connect(self.scroll_to_row)

    def prep_dev(self):
        self.setMinimumWidth(350)
        self.setMinimumHeight(350)
        self.update_groups(GroupingCriterion.YEAR_MONTH_DAY)
        self.update_size()
        # self.scroll_to_row(20)

    def update_groups(self, grouping: GroupingCriterion):
        """
        Update the grouping criterion and rebuild the lookup tables.
        """
        self.model.grouping = grouping
        self.group_infos = np.array(self.model.get_group_image_count(), dtype=GroupCount)

    def build_lut(self):
        """
        Build the lookup tables for the grouping criterion.
        :return:
        """
        start = datetime.datetime.now()
        row_lut = []
        index_lut = []
        header_lut = []
        index = 0
        row_count = 0
        cur_row = 0

        for i in range(len(self.group_infos)):
            cur_info = self.group_infos[i]
            img_count = cur_info.count

            while img_count > 0:
                new_index = index + (self.number_of_columns if self.number_of_columns < img_count else img_count)
                row_lut.append(index)

                for j in range(index, new_index):
                    index_lut.append(row_count)

                if index <= self.focus_index < new_index:
                    cur_row = row_count
                index = new_index
                row_count += 1
                header_lut.append(i)
                img_count -= self.number_of_columns

        self.row_to_header_lut = np.array(header_lut, dtype=int)
        self.row_to_index_lut = np.array(row_lut, dtype=int)
        self.index_to_row_lut = np.array(index_lut, dtype=int)
        self.number_of_rows = row_count
        self.focus_row = cur_row
        stop = datetime.datetime.now()
        print(f"Compute lut took: {(stop - start).total_seconds()}")
        print(f"Number of rows: {self.number_of_rows}")

    def move_to_hidden(self, t: IndexedTile):
        """
        Stores the widget in the hidden widgets list. Also hides the widget.
        """
        self.hidden_widgets.append(t)
        t.setVisible(False)

    def get_hidden_widget(self) -> IndexedTile:
        """
        Returns a hidden widget. Unhides it as well.
        """
        t = self.hidden_widgets.pop()
        t.setVisible(True)
        return t

    def update_size(self):
        """
        Update the sizing of the elements, triggered by resize or by adaptation of the content margins
        """
        margin = self.margin  # left, top, right, bottom
        rem_width = self.width() - margin[0] - margin[2]
        new_number_of_columns = max(1, rem_width // self.tile_size)
        self.background_widget.setFixedWidth(rem_width)

        max_new_number_of_visible_rows = math.ceil((self.height() - margin[1] - margin[3]) / self.tile_size)
        self.min_number_of_visible_rows = math.floor((self.height()
                                                     - margin[1]
                                                     - margin[3]) /
                                                    (self.tile_size
                                                     + self.header_height
                                                     + 2 * self.background_layout.verticalSpacing()))

        if (new_number_of_columns == self.number_of_columns and
                max_new_number_of_visible_rows == self.max_number_of_visible_rows):
            return

        self.number_of_columns = new_number_of_columns
        self.max_number_of_visible_rows = max_new_number_of_visible_rows

        self.build_lut()
        self.increase_widget_count()
        self.resize_layout()
        self.decrease_widget_count()

    def resize_layout(self):
        """
        Resize the layout to the correct size once a resize event is scheduled.
        """
        # TODO serialize the image tiles and rebuild them into rows.
        row = self.focus_row
        if row is None:
            return

        self._scroll_to_row(row)

    def increase_widget_count(self):
        """
        Given the maximum number of widgets displayed at time, increase the number of widgets if resize requires it.
        """
        # Guard if it's less or equal
        print(f"Number of generated rows: {self.number_of_generated_rows}, Number of columns: {self.number_of_columns}")
        if self.number_of_generated_rows * self.number_of_columns <= len(self.widgets):
            return

        add_count = self.number_of_generated_rows * self.number_of_columns - len(self.widgets)
        # Increase the number of widgets
        for i in range(add_count):
            t = IndexedTile()
            t.setParent(self)
            t.setFixedHeight(self.tile_size)
            t.setFixedWidth(self.tile_size)
            self.widgets.append(t)
            self.move_to_hidden(t)

        print(f"Added: {add_count} Widgets")

    def decrease_widget_count(self):
        """
        Given the maximum number of widgets displayed at time, decrease the number of widgets if resize requires it.
        """
        # Guard if it's greater or equal
        if self.number_of_columns * self.__number_of_columns >= len(self.widgets):
            return

        # Decrease the number of widgets
        number_of_widgets_to_remove = len(self.widgets) - self.number_of_generated_rows * self.number_of_columns
        assert len(self.hidden_widgets) >= number_of_widgets_to_remove, "Not enough hidden widgets to remove"
        for i in range(number_of_widgets_to_remove):
            t = self.get_hidden_widget()
            self.widgets.remove(t)
            t.deleteLater()

        print(f"Removed {number_of_widgets_to_remove} Widgets")

    def layout_from_datastructure(self):
        """
        Layout the widgets from the data structure.
        """
        while self.background_layout.count() > 0:
            self.background_layout.takeAt(0)

        for i in range(len(self.layout_rows)):
            # Placeholder for the header
            if type(self.layout_rows[i]) is QFrame:
                self.background_layout.addWidget(self.layout_rows[i], i, 0, 1, self.number_of_columns)
                continue

            # Row of widgets
            for j in range(len(self.layout_rows[i])):
                t = self.layout_rows[i][j]
                self.background_layout.addWidget(t, i, j)

        # for i in range(len(self.widget_rows)):
        #     for j in range(len(self.widget_rows[i])):
        #         t = self.widget_rows[i][j]
        #         self.background_layout.addWidget(t, i, j)

        # Make sure spacing in grid layout is consistent
        # self.background_layout.addWidget(self.layout_placeholder, len(self.widget_rows), 0, 1, self.number_of_columns)

    def place_background_widget(self):
        """
        Place the background widget such that the correct row is displayed.
        """
        # y = (self.focus_row_offset * (self.tile_size + self.background_layout.verticalSpacing())
        #      - self.margin[1])
        y = 0

        for i in range(len(self.layout_rows)):
            row = self.layout_rows[i]
            if type(row) is QFrame:
                y += self.header_height + self.background_layout.verticalSpacing()
            else:
                assert type(row) is list, "Row must be either a list of widgets or a header"
                y += self.tile_size + self.background_layout.verticalSpacing()

            if self.layout_rows[i + 1] is self.widget_rows[self.focus_row_offset]:
                if type(self.layout_rows[i]) is QFrame:
                    y -= self.header_height + self.background_layout.verticalSpacing()
                break

        y -= self.margin[1]
        # print(f"Background Widget Position: {self.margin[0], -y + self.scroll_offset}")
        self.background_widget.move(QPoint(self.margin[0], -y + self.scroll_offset))

        # Perform resizing of background widget manually.
        self.background_widget.updateGeometry()
        self.background_widget.update()

    def fetch_tile(self, index: int) -> BaseTileInfo:
        """
        Fetches a tile from the model.
        """
        return self.buffer.fetch_tile(index)

    def scroll_to_row(self, row: int = None):
        """
        Scroll to a given row.
        """
        # Fetch scroll from buffer if triggered by timer
        if row is None:
            row = self.scroll_buffer
            if row is None:
                return

        assert 0 <= row < self.number_of_rows, f"Row out of bounds, [0, {self.number_of_rows}], {row}"

        # Clamping to the maximum row
        cutoff = self.number_of_rows - self.min_number_of_visible_rows + 1
        if row > cutoff:
            print(f"Clamping")
            row = cutoff

        self._scroll_to_row(row)

        # guaranteed that the row is not the same
        if row == self.focus_row:
            return

        # Using build_up to get to the place if the row is already loaded but further up
        if self.lowest_row <= row < self.focus_row:
            while self.focus_row > row:
                self.build_up()
            return

        # Using build_down to get to the place if the row is already loaded but further down
        if self.highest_row >= row > self.focus_row:
            while self.focus_row < row:
                self.build_down()
            return

    def _scroll_to_row(self, row: int = None):
        """
        Scroll to row only with clamping.
        """
        for r in self.widget_rows:
            for w in r:
                self.move_to_hidden(w)

        self.focus_row = row

        self.lowest_row = max(0, self.focus_row - self.preload_row_count)
        self.focus_row_offset = self.focus_row - self.lowest_row

        self.widget_rows = []
        self.highest_row = min(self.number_of_rows - 1,
                               self.focus_row
                               + self.max_number_of_visible_rows
                               + self.preload_row_count
                               - 1)
        for i in range(self.lowest_row, self.highest_row + 1):
            self.widget_rows.append(self._generate_row(i))

        # Clear the leayout rows
        for row in self.layout_rows:
            if type(row) is QFrame:
                row.deleteLater()

        self.layout_rows = []

        # Insert first header
        if self.lowest_row == 0:
            self.layout_rows.append(self._generate_placeholder())

        # Add the rows
        for i in range(self.lowest_row, self.highest_row + 1):
            if i > self.lowest_row and self.row_to_header_lut[i] != self.row_to_header_lut[i - 1]:
                self.layout_rows.append(self._generate_placeholder())
            self.layout_rows.append(self.widget_rows[i - self.lowest_row])

        self.layout_from_datastructure()
        self.place_background_widget()
        self.scroll_buffer = None

    # ------------------------------------------------------------------------------------------------------------------
    # Helper functions which perform repeated tasks of building rows at bottom or top or delete row at bottom or top
    # ------------------------------------------------------------------------------------------------------------------

    def _generate_row(self, row: int) -> List[IndexedTile]:
        """
        Generates a row of widgets. This function does not perform layout.
        """
        if row == self.number_of_rows - 1:
            end = self.buffer.number_of_elements
        else:
            end = self.row_to_index_lut[row + 1]

        l = []
        for i in range(self.row_to_index_lut[row], end):
            tile = self.fetch_tile(i)
            w = self.get_hidden_widget()
            w.tile_info = tile
            w.index = i
            l.append(w)
        # print(f"Length of Row: {len(l)}")
        return l

    def _generate_placeholder(self):
        """
        Generate a placeholder for the moment
        """
        temp = QFrame(self)
        temp.setFixedHeight(self.header_height)
        temp.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        return temp

    def _add_row_bottom(self):
        """
        Add row to bottom of data structure, doesn't update the widgets!
        """
        assert self.highest_row < self.number_of_rows - 1, "Cannot add row at bottom, already at bottom"
        self.highest_row += 1
        widget_row = self._generate_row(self.highest_row)

        # Insert header if necessary
        if self.row_to_header_lut[self.highest_row - 1] != self.row_to_header_lut[self.highest_row]:
            self.layout_rows.append(self._generate_placeholder())
        self.layout_rows.append(widget_row)

        self.widget_rows.append(widget_row)

    def _add_row_top(self):
        """
        Add row to the top of data structure, doesn't update the widgets!
        """
        assert self.lowest_row > 0, "Cannot add row at top, already at top"
        self.lowest_row -= 1

        widget_row = self._generate_row(self.lowest_row)

        # Add placeholder for title if necessary
        if (self.row_to_header_lut[self.lowest_row + 1] != self.row_to_header_lut[self.lowest_row]
                and type(self.layout_rows[0]) is not QFrame):
            self.layout_rows.insert(0, self._generate_placeholder())

        # Insert the row generated
        self.layout_rows.insert(0, widget_row)

        # Insert first header if we're at the top
        if self.lowest_row == 0:
            self.layout_rows.insert(0, self._generate_placeholder())

        self.widget_rows.insert(0, widget_row)

    def _remove_row_bottom(self):
        """
        Removes a row at the bottom of the data structure, doesn't update the widgets!
        """
        assert self.highest_row > self.lowest_row, "To few rows to remove row"
        row = self.widget_rows.pop()
        self.highest_row -= 1

        # Store the widgets away so they can be reused
        for widget in row:
            self.move_to_hidden(widget)

        # Remove the row
        self.layout_rows.pop()

        # Remove the next row too, if it's a header
        if type(self.layout_rows[-1]) is QFrame:
            self.layout_rows.pop().deleteLater()

    def _remove_row_top(self):
        """
        Removes a row at the top of the data structure, doesn't update the widgets!
        """
        assert self.highest_row > self.lowest_row, "To few rows to remove row"
        row = self.widget_rows.pop(0)
        self.lowest_row += 1

        # Store the widgets away so they can be reused
        for widget in row:
            self.move_to_hidden(widget)

        row = self.layout_rows.pop(0)
        if type(row) is QFrame:
            row.deleteLater()
            row = self.layout_rows.pop(0)
            assert type(row) is list, "Row after header must be a header"

    def dump_widgets(self, layout: bool = True, widget: bool = False):
        """
        Helper function to dump the indexes of the widgets for debugging purposes
        """
        if widget or layout:
            print(f"-"*100)
        if widget:
            for row in self.widget_rows:
                indexes = [str(col.index) for col in row]
                print(", ".join(indexes))
            print(f"-" * 100)
        if layout:
            for row in self.layout_rows:
                if type(row) is QFrame:
                    print("Header")
                else:
                    indexes = [str(col.index) for col in row]
                    print(", ".join(indexes))
            print(f"-"*100)

    # ------------------------------------------------------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------------------------------------------------------

    @pyqtSlot(int)
    def scroll_to_index(self, index: int):
        """
        Scroll to a given index. Naive implementation
        """
        assert 0 <= index < self.buffer.number_of_elements, \
            f"Index out of bounds, [0, {self.buffer.number_of_elements}], {index}"

        row = self.index_to_row_lut[index]
        self.scroll_to_row(row)
        # self.dump_widgets()

    @pyqtSlot(int)
    def scroll_slot(self, row: int):
        if row == self.focus_row:
            return

        global use_timers_scroll
        if use_timers_scroll:
            self.scroll_buffer = row
            self.scroll_timer.start(self.scroll_timeout)
        else:
            self.scroll_to_row(row)

    @pyqtSlot()
    def build_down(self):
        """
        Build next row below the current lowest row. Does nothing if bottom is reached.
        """
        # we've reached the bottom, cannot build any further
        if self.highest_row == self.number_of_rows - 1:
            cutoff = self.number_of_rows - self.min_number_of_visible_rows + 1

            # we've crossed the threshold, clamp to the maximum row and replace the background widget
            if self.focus_row > cutoff:
                warnings.warn("Focus row bigger than cutoff, clamping")
                self.focus_row = cutoff
                self.focus_row_offset = self.focus_row - self.lowest_row
                self.place_background_widget()
                return

            elif self.focus_row == cutoff:
                print(f"Bottom reached")
                return

            # we've still got rows that aren't visible, changing the focus_row and focus_row_offset is enough
            self._remove_row_top()
            self.focus_row += 1
            self.layout_from_datastructure()
            self.place_background_widget()
            return

        # we're at the very top and we can go ahead an increase the number of rows without deleting one.
        if self.focus_row_offset < self.preload_row_count:
            self.focus_row_offset += 1
            self.focus_row += 1
            self._add_row_bottom()
            self.layout_from_datastructure()
            self.place_background_widget()
            return

        # we're somewhere in the middle, row offset is constant, widget placement is constant, only new rows need
        # to be added and removed
        self._remove_row_top()
        self._add_row_bottom()
        self.focus_row += 1
        self.layout_from_datastructure()

    def build_up(self):
        """
        Build next row above the current highest row. Does nothing if top is reached.
        """
        # we've reached the top, cannot build any further
        if self.lowest_row == 0:
            # we've crossed the threshold, clamp to the minimum row and replace the background widget
            if self.focus_row < 0:
                warnings.warn("Focus row smaller than 0, why is this possible?")
                self.focus_row = 0
                self.focus_row_offset = 0
                self.place_background_widget()
                return

            elif self.focus_row == 0:
                print(f"Top reached")
                return

            # we've still got rows that aren't visible, changing the focus_row and focus_row_offset and removing rows
            # at the bottom
            self.focus_row -= 1
            self.focus_row_offset -= 1
            self._remove_row_bottom()
            self.layout_from_datastructure()
            self.place_background_widget()
            return

        # we're at the very bottom and we can go ahead an increase the number of rows without deleting one.
        if self.highest_row == self.number_of_rows - 1 and len(self.widget_rows) < self.number_of_generated_rows:
            self.focus_row -= 1
            self._add_row_top()
            self.layout_from_datastructure()
            return

        # we're somewhere in the middle, row offset is constant, widget placement is constant, only new rows need
        # to be added and removed
        self._remove_row_bottom()
        self._add_row_top()
        self.focus_row -= 1
        self.layout_from_datastructure()

    # ------------------------------------------------------------------------------------------------------------------
    # Custom Event Overrides to capture and them or trigger custom actionis
    # ------------------------------------------------------------------------------------------------------------------

    def __init_resize_event(self, a0) -> None:
        self.update_size()
        self._scroll_to_row(0)
        super().resizeEvent(a0)
        self.resizeEvent = self.__normal_resize_event

    def __normal_resize_event(self, a0: QResizeEvent) -> None:
        """
        Capture resize event and trigger update of size
        """
        global use_timers_resize
        if use_timers_resize:
            self.resize_timer.start(self.resize_timeout)
        else:
            self.update_size()
        super().resizeEvent(a0)

    def paintEvent(self, a0):
        """
        Capture the paint event in order to update the widget sizing.
        """
        super().paintEvent(a0)
        self.background_widget.adjustSize()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """
        Catch keys from keyboard and move the carousel accordingly.
        :param a0:
        :return:
        """
        super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Up and a0.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.scroll_offset -= 10
            self.place_background_widget()
        elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.scroll_offset += 10
            self.place_background_widget()
        elif a0.key() == Qt.Key.Key_Up and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.build_up()
            self.dump_widgets()
        elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.build_down()
            self.dump_widgets()
        elif a0.key() == Qt.Key.Key_R and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.scroll_offset = 0
            self.place_background_widget()
        else:
            pass


class TempRoot(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dummy_widget = QWidget()
        self.setCentralWidget(self.dummy_widget)

        self.layout = QHBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.dummy_widget.setLayout(self.layout)

        self.model = Model(folder_path="/home/alisot2000/Desktop/New_DB/")
        self.model.current_import_table_name = "tbl_-1886740392237389744"
        self.tiles = TileWidget(self.model)

        self.layout.addWidget(self.tiles)

        self.scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.scrollbar.setMaximum(self.tiles.number_of_rows)
        self.tiles.num_of_rows_changed.connect(self.set_max)
        self.tiles.focus_row_changed.connect(self.set_val)
        self.scrollbar.valueChanged.connect(self.set_value)
        self.scrollbar.sliderReleased.connect(self.send_value)
        style_sheet = """
        QScrollBar:vertical {
            border: 1px dashed black;
            width: 15px;
        }  
        
        QScrollBar::handle:vertical {
            min-height: 50px;
        }
        """
        # self.scrollbar.setStyleSheet(style_sheet)

        # needs to happen here, so we capture the change event.
        self.tiles.prep_dev()

        self.layout.addWidget(self.scrollbar)

    def send_value(self):
        self.tiles.scroll_slot(self.scrollbar.value())

    def set_value(self, v: int):
                # Single button press, capture it and propagate it to the tile widget
        if not self.scrollbar.isSliderDown():
            self.tiles.scroll_slot(v)

    def keyPressEvent(self, a0):
        super().keyPressEvent(a0)
        self.tiles.keyPressEvent(a0)

    def keyReleaseEvent(self, a0):
        super().keyReleaseEvent(a0)
        self.tiles.keyReleaseEvent(a0)

    def set_max(self):
        # max = self.tiles.number_of_rows - self.tiles.min_number_of_visible_rows + 1
        print(f"Max: {self.tiles.number_of_rows}")
        self.scrollbar.setMaximum(self.tiles.number_of_rows - 1)

    def set_val(self, val: int):
        print(f"Val: {val}")
        self.scrollbar.setValue(val)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # m = Model(folder_path="/home/alisot2000/Desktop/New_DB/")
    # m.current_import_table_name = "tbl_-1886740392237389744"
    # w = TileWidget(m)
    # w.prep_dev()
    # w.show()
    w = TempRoot()
    w.show()

    sys.exit(app.exec())
