import datetime
import math
import sys
import warnings
from typing import Union, List, Tuple

import numpy as np
from PyQt6.QtCore import pyqtSlot, pyqtSignal, Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QResizeEvent, QKeyEvent, QPixmapCache, QFont, QFontMetrics
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QGridLayout, QLabel, \
    QMainWindow, QScrollBar, QHBoxLayout, QSlider, QSizePolicy

from photo_lib.data_objects import BaseTileInfo
from photo_lib.gui.widgets.image_tile import IndexedTile
from photo_lib.gui.old_model import Model, GroupCount, GroupingCriterion, TileBuffer

use_timers_resize = True

# TODO test the following bug:
#   - Scroll out of bounds
#   - Increase Tile Size to max
#   - Use scroll arrows
#   - Make are larger than image
#   - Scale down
# Main point seems to be, window is smaller than the displayed image.
# Error output:
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559090>
# Removed 87 Widgets
# Compute lut took: 0.001769
# Number of rows: 1643
# Number of generated rows: 22, Number of columns: 3, Number of Widgets: 66
# Added: 53 Widgets
# Removed 0 Widgets
# Compute lut took: 0.004081
# Number of rows: 4149
# Number of generated rows: 13, Number of columns: 1, Number of Widgets: 13
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a350>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a3f0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a490>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a530>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b610>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b570>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b4d0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b430>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b390>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b2f0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b250>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b1b0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b110>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155b070>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155afd0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155af30>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155ae90>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155adf0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155ad50>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155acb0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155ac10>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155ab70>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155aad0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155aa30>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a990>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a8f0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a850>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a7b0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a710>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a670>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b594155a5d0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559770>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415596d0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559630>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559590>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415594f0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559450>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415593b0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559310>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559270>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb430>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb390>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb2f0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb250>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb1b0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb110>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bb070>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bafd0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415baf30>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415bae90>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b59415591d0>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941559130>
# DEBUG: Deleted Later <photo_lib.gui.image_tile.IndexedTile object at 0x7b5941558e10>
# Removed 53 Widgets
# Traceback (most recent call last):
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 1115, in update_scroll_on_change
#     """
#
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 936, in scroll_slot
#     #     self.scroll_buffer = row
#     ^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 532, in scroll_animation
#     Start scroll animation and buffer the row into a temp variable
#         ^^^^^^^^^^^^^^^^^^^^^^^
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 595, in scroll_to_row
#     self.layout_from_datastructure()
# ^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 619, in _scroll_to_row
#     + self.preload_row_count
#          ^^^^^^^^^^^^^^^^^^^^
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 754, in _generate_row
#
#   File "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/src/photo_lib/gui/tile_view.py", line 356, in get_hidden_widget
#     def get_hidden_widget(self) -> IndexedTile:
#             ^^^^^^^^^^^^^^^^^^^^^^^^^
# IndexError: pop from empty list
# TODO register clickable tiles to emmit the img_selected signal
class TileWidget(QFrame):
    # Backend objects
    model: Model
    buffer: TileBuffer

    # Signals
    num_of_rows_changed = pyqtSignal(int)
    page_size_changed = pyqtSignal(int)
    # num_of_cols_changed = pyqtSignal(int)
    # img_selected = pyqtSignal()  # read the current_element from the object
    focus_row_changed = pyqtSignal(int)
    tile_size_changed = pyqtSignal(int)

    # Properties about the view, writable
    __max_number_of_visible_rows = 0
    __number_of_columns = 0
    __focus_row = 0
    __number_of_rows = 0
    __min_number_of_visible_rows: int = 0

    # Properties about the view, read only
    __number_of_generated_rows = 0
    __focus_index: int = 0
    # __current_index = 0
    # __current_tile_info: Union[BaseTileInfo, None] = None

    # Further properties that don't need to be set
    scroll_offset: int = 0

    focus_row_offset: int = 0

    new_focus_row: Union[int, None] = None
    new_focus_row_offset: Union[int, None] = None

    lowest_row: int = 0
    highest_row: int = 0

    # Layout
    # TODO config
    __tile_size: int = 100  # Different tile size for year, month and day.
    preload_row_count: int = 5
    resize_timeout: int = 200
    header_height: int = 35
    __content_margin: Tuple[int, int, int, int]  # left, top, right, bottom

    # lookup tables
    group_infos: np.ndarray
    row_to_index_lut: np.ndarray    # Given a row -> gives the start index that are displayed there
    index_to_row_lut: np.ndarray    # given an index -> gives the row that contains this index
    row_to_header_lut: np.array     # given a row -> gives the header for that row

    # Widgets and Layout structures
    widgets: List[IndexedTile] = None  # List of all widgets that are currently instantiated
    hidden_widgets: List[IndexedTile] = None  # Widgets that are currently hidden

    widget_rows: List[List[IndexedTile]] = None
    layout_rows: List[Union[QLabel, List[IndexedTile]]] = None

    background_widget: QWidget = None
    background_layout: QGridLayout = None

    movement_animation: QPropertyAnimation

    # ------------------------------------------------------------------------------------------------------------------
    # Read/Write Properties
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def tile_size(self):
        return self.__tile_size

    @tile_size.setter
    def tile_size(self, value: int):
        assert value > 0, "Tile size must be greater than 0"
        if value == self.__tile_size:
            return

        self.__tile_size = value

        self.update_size()
        self.update_tile_sizes()

        self.tile_size_changed.emit(value)

    @property
    def min_number_of_visible_rows(self):
        return self.__min_number_of_visible_rows

    @min_number_of_visible_rows.setter
    def min_number_of_visible_rows(self, value: int):
        assert value >= 0, "Minimum Number of Visible Rows needs to be greq zero"
        if value == self.__min_number_of_visible_rows:
            return

        temp = self.__min_number_of_visible_rows
        self.__min_number_of_visible_rows = value

        self.page_size_changed.emit(max(1, value))

    @property
    def content_margin(self):
        return self.__content_margin

    @content_margin.setter
    def content_margin(self, value: Tuple[int, int, int, int]):
        if value == self.__content_margin:
            return

        self.__content_margin = value
        self.update_size()

    @property
    def max_number_of_visible_rows(self):
        return self.__max_number_of_visible_rows

    @max_number_of_visible_rows.setter
    def max_number_of_visible_rows(self, value: int):
        assert value > 0, "Number of visible rows must be greater than 0"
        if value == self.__max_number_of_visible_rows:
            return

        self.__max_number_of_visible_rows = value
        self.__number_of_generated_rows = value + 2 * (self.preload_row_count + value)

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

        # Data structures for View
        self.widget_rows = []
        self.layout_rows = []

        self.background_widget = QWidget(self)
        self.background_widget.move(QPoint(0, 0))
        self.background_widget.setStyleSheet("background-color: palette(base);")

        self.background_layout = QGridLayout()
        # self.background_layout.setContentsMargins(0, 0, 0, 0)

        top = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutTopMargin)
        bottom = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutBottomMargin)
        left = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutLeftMargin)
        right = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutRightMargin)

        v_space = int((top + bottom) / 2)
        h_space = int((left + right) / 2)

        self.header_height = QFontMetrics(QFont()).height() + top + bottom

        self.background_layout.setVerticalSpacing(v_space)
        self.background_layout.setHorizontalSpacing(h_space)

        self.background_widget.setLayout(self.background_layout)

        self.movement_animation = QPropertyAnimation(self.background_widget, b"pos")
        self.movement_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.movement_animation.setDuration(200)
        self.movement_animation.finished.connect(self.update_widget)

        global use_timers_resize
        global use_timers_scroll

        # Setting our own content margins
        top = right = bottom = left = 0
        self.__content_margin = (left, top, right, bottom)

        if use_timers_resize:
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.update_size)

    def prep_dev(self):
        print(f"INFO: CAll to prep_cev")
        self.setMinimumWidth(350)
        self.setMinimumHeight(350)
        self.update_groups(GroupingCriterion.YEAR_MONTH_DAY)

    def update_tile_sizes(self):
        """
        Go through all tiles and seit their size
        """
        for w in self.widgets:
            w.setFixedHeight(self.tile_size)
            w.setFixedWidth(self.tile_size)

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
        Update the sizing of the elements, triggered by resize or by adaptation of the content margins,
        or a change in tile_size
        """
        # left, top, right, bottom
        margin_widget = self.content_margin
        margin_layout = self.background_layout.contentsMargins()

        # Remaining width minus margins
        rem_width = self.width() - margin_widget[0] - margin_widget[2] - margin_layout.left()  - margin_layout.right()
        background_remaining_width = self.width() - margin_widget[0] - margin_widget[2]

        # Number of columns that fit into the remaining width
        new_number_of_columns = max(1, rem_width // self.tile_size)

        # Set width of Background Widget
        if self.background_widget.width() != background_remaining_width:
            self.background_widget.setFixedWidth(background_remaining_width)
            # for l in self.layout_rows:
            #     if isinstance(l, QLabel):
            #         l.setFixedWidth(rem_width)

        # Compute new maximum number of visible rows
        max_new_number_of_visible_rows = math.ceil((self.height()
                                                    - margin_widget[1]
                                                    - margin_widget[3]
                                                    - margin_layout.top()
                                                    - margin_layout.bottom()) / self.tile_size)

        # Compute new minimum number of visible rows
        self.min_number_of_visible_rows = math.floor((self.height()
                                                      - margin_widget[1]
                                                      - margin_widget[3]
                                                      - margin_layout.top()
                                                      - margin_layout.bottom()) /
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
        print(f"Number of generated rows: {self.number_of_generated_rows}, "
              f"Number of columns: {self.number_of_columns}, "
              f"Number of Widgets: {self.number_of_generated_rows * self.number_of_columns}")

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
        # Empty the background layout
        while self.background_layout.count() > 0:
            self.background_layout.takeAt(0)

        for i in range(len(self.layout_rows)):
            # Placeholder for the header
            if type(self.layout_rows[i]) is QLabel:
                self.background_layout.addWidget(self.layout_rows[i], i, 0, 1, self.number_of_columns)
                continue

            # Row of widgets
            for j in range(len(self.layout_rows[i])):
                t = self.layout_rows[i][j]
                self.background_layout.addWidget(t, i, j)

    def place_background_widget(self, target_offset: int = None):
        """
        Place the background widget such that the correct row is displayed.
        """
        y = 0

        if target_offset is None:
            tos = self.focus_row_offset
        else:
            tos = target_offset

        for i in range(len(self.layout_rows)):
            row = self.layout_rows[i]
            if type(row) is QLabel:
                y += self.header_height + self.background_layout.verticalSpacing()
            else:
                assert type(row) is list, "Row must be either a list of widgets or a header"
                y += self.tile_size + self.background_layout.verticalSpacing()

            # TODO move into upper block
            if self.layout_rows[i + 1] is self.widget_rows[tos]:
                if type(self.layout_rows[i]) is QLabel:
                    y -= self.header_height + self.background_layout.verticalSpacing()
                break

        y -= self.content_margin[1]
        # print(f"Background Widget Position: {self.margin[0], -y + self.scroll_offset}")
        if target_offset is None:
            self.background_widget.move(QPoint(self.content_margin[0], -y + self.scroll_offset))

            # Perform resizing of background widget manually.
            self.background_widget.updateGeometry()
            self.background_widget.update()
        else:
            return QPoint(self.content_margin[0], -y + self.scroll_offset)

    def fetch_tile(self, index: int) -> BaseTileInfo:
        """
        Fetches a tile from the model.
        """
        return self.buffer.fetch_tile(index)

    def scroll_animation(self, row: int):
        """
        Start scroll animation and buffer the row into a temp variable
        """
        # We're beyond the top built row
        if row < self.lowest_row:
            self.scroll_to_row(row)
            return

        # +1 is a bit questionable
        if row > self.highest_row - self.max_number_of_visible_rows + 1:
            self.scroll_to_row(row)
            return

        self.new_focus_row = row
        self.new_focus_row_offset = self.focus_row_offset + (self.new_focus_row - self.focus_row)

        target = self.place_background_widget(self.new_focus_row_offset)
        self.movement_animation.setStartValue(self.background_widget.pos())
        self.movement_animation.setEndValue(target)
        self.movement_animation.start()

    def update_widget(self):
        """
        At the end of the animation, update the widget
        """
        if self.new_focus_row is None:
            return

        self.scroll_to_row(self.new_focus_row)
        self.new_focus_row = None

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

        # guaranteed that the row is not the same
        if row == self.focus_row:
            return

        # Using build_up to get to the place if the row is already loaded but further up
        if self.lowest_row <= row < self.focus_row:
            while self.focus_row > row:
                self._build_up(False)
            self.layout_from_datastructure()
            self.place_background_widget()
            return

        # Using build_down to get to the place if the row is already loaded but further down
        if self.highest_row >= row > self.focus_row:
            while self.focus_row < row:
                self._build_down(False)
            self.layout_from_datastructure()
            self.place_background_widget()
            return

        self._scroll_to_row(row)

    def _scroll_to_row(self, row: int = None):
        """
        Scroll to row only with clamping.
        """
        # INFO: Build WIDGET rows first
        for r in self.widget_rows:
            for w in r:
                self.move_to_hidden(w)

        self.focus_row = row

        self.lowest_row = max(0, self.focus_row - self.preload_row_count - self.max_number_of_visible_rows)
        self.focus_row_offset = self.focus_row - self.lowest_row

        self.widget_rows = []
        self.highest_row = min(self.number_of_rows - 1,
                               self.focus_row
                               + 2 * self.max_number_of_visible_rows
                               + self.preload_row_count
                               - 1)

        for i in range(self.lowest_row, self.highest_row + 1):
            self.widget_rows.append(self._generate_row(i))

        # INFO: Build LAYOUT rows
        # Clear the layout rows
        for row in self.layout_rows:
            if isinstance(row, QLabel):
                # row.setVisible(False)
                row.deleteLater()

        self.layout_rows = []

        # Insert first header
        if self.lowest_row == 0:
            self.layout_rows.append(self.generate_header(0))

        # Add the rows
        for i in range(self.lowest_row, self.highest_row + 1):
            if i > self.lowest_row and self.row_to_header_lut[i] != self.row_to_header_lut[i - 1]:
                self.layout_rows.append(self.generate_header(self.row_to_header_lut[i]))
            self.layout_rows.append(self.widget_rows[i - self.lowest_row])

        self.layout_from_datastructure()
        self.place_background_widget()

    def _build_down(self, layout: bool = True):
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
                if layout:
                    self.place_background_widget()
                return

            elif self.focus_row == cutoff:
                print(f"Bottom reached")
                return

            # we've still got rows that aren't visible, changing the focus_row and focus_row_offset is enough
            self._remove_row_top()
            self.focus_row += 1
            if layout:
                self.layout_from_datastructure()
                self.place_background_widget()
            return

        # we're at the very top and we can go ahead an increase the number of rows without deleting one.
        if self.focus_row_offset < self.preload_row_count:
            self.focus_row_offset += 1
            self.focus_row += 1
            self._add_row_bottom()
            if layout:
                self.layout_from_datastructure()
                self.place_background_widget()
            return

        # we're somewhere in the middle, row offset is constant, widget placement is constant, only new rows need
        # to be added and removed
        self._remove_row_top()
        self._add_row_bottom()
        self.focus_row += 1
        if layout:
            self.layout_from_datastructure()
            self.place_background_widget()

    def _build_up(self, layout: bool = True):
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
                if layout:
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
            if layout:
                self.layout_from_datastructure()
                self.place_background_widget()
            return

        # we're at the very bottom and we can go ahead an increase the number of rows without deleting one.
        if self.highest_row == self.number_of_rows - 1 and len(self.widget_rows) < self.number_of_generated_rows:
            self.focus_row -= 1
            self._add_row_top()
            if layout:
                self.layout_from_datastructure()
            return

        # we're somewhere in the middle, row offset is constant, widget placement is constant, only new rows need
        # to be added and removed
        self._remove_row_bottom()
        self._add_row_top()
        self.focus_row -= 1
        if layout:
            self.layout_from_datastructure()
            self.place_background_widget()

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

    def generate_header(self, index: int) -> QLabel:
        """
        Generates a Header Leabel with formatting for the given index.
        """
        gi = self.group_infos[index]
        text = self.generate_label_text(gi)
        l = QLabel(text)
        l.setFixedHeight(self.header_height)

        l.setStyleSheet("background-color: palette(alternate-base);")
        top = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutTopMargin)
        right = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutRightMargin)
        bottom = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutBottomMargin)
        left = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutLeftMargin)
        l.setContentsMargins(left, top, right, bottom)
        return l

    @staticmethod
    def generate_label_text(gi: GroupCount) -> str:
        """
        Given a GroupCount object, generate the header for it.
        """
        if gi.group_crit == GroupingCriterion.YEAR_MONTH_DAY:
            return gi.start_date.strftime("%A, %d %B %Y")
        elif gi.group_crit == GroupingCriterion.YEAR_MONTH:
            return gi.start_date.strftime("%B %Y")
        elif gi.group_crit == GroupingCriterion.YEAR:
            return gi.start_date.strftime("%Y")
        else:
            return ""

    def get_indicator_text(self, index: int) -> str:
        """
        Get the indicator text for the given index. Needed for the moving indicator that moves with the scrollbar.
        """
        gi = self.group_infos[self.row_to_header_lut[index]]
        return self.generate_label_text(gi)

    def _add_row_bottom(self):
        """
        Add row to bottom of data structure, doesn't update the widgets!
        """
        assert self.highest_row < self.number_of_rows - 1, "Cannot add row at bottom, already at bottom"
        self.highest_row += 1
        widget_row = self._generate_row(self.highest_row)

        # Insert header if necessary
        if self.row_to_header_lut[self.highest_row - 1] != self.row_to_header_lut[self.highest_row]:
            self.layout_rows.append(self.generate_header(self.row_to_header_lut[self.highest_row]))
        self.layout_rows.append(widget_row)

        self.widget_rows.append(widget_row)

    def _add_row_top(self):
        """
        Add row to the top of data structure, doesn't update the widgets!
        """
        # INFO: Update the LAYOUT rows
        assert self.lowest_row > 0, "Cannot add row at top, already at top"
        self.lowest_row -= 1

        widget_row = self._generate_row(self.lowest_row)

        # Add placeholder for title if necessary
        if (self.row_to_header_lut[self.lowest_row + 1] != self.row_to_header_lut[self.lowest_row]
                and type(self.layout_rows[0]) is not QLabel):
            self.layout_rows.insert(0, self.generate_header(self.row_to_header_lut[self.lowest_row]))

        # Insert the row generated
        self.layout_rows.insert(0, widget_row)

        # Insert first header if we're at the top
        if self.lowest_row == 0:
            self.layout_rows.insert(0, self.generate_header(0))

        # INFO: update the WIDGET rows
        self.widget_rows.insert(0, widget_row)

    def _remove_row_bottom(self):
        """
        Removes a row at the bottom of the view, doesn't update the widgets!
        """
        # INFO: Update the WIDGET rows
        assert self.highest_row > self.lowest_row, "To few rows to remove row"
        row = self.widget_rows.pop()
        self.highest_row -= 1

        # Store the widgets away so they can be reused
        for widget in row:
            self.move_to_hidden(widget)

        # INFO: Now update the LAYOUT rows
        # Remove the row
        self.layout_rows.pop()

        # Remove the next row too, if it's a header
        if isinstance(self.layout_rows[-1], QLabel):
            self.layout_rows.pop().deleteLater()

    def _remove_row_top(self):
        """
        Removes a row at the top of the view, doesn't update the widgets!
        """
        # INFO: Update the WIDGET rows
        assert self.highest_row > self.lowest_row, "To few rows to remove row"
        row = self.widget_rows.pop(0)
        self.lowest_row += 1

        # Store the widgets away so they can be reused
        for widget in row:
            self.move_to_hidden(widget)

        # INFO: Now update the LAYOUT rows
        row = self.layout_rows.pop(0)
        if isinstance(row, QLabel):
            row.deleteLater()
            row = self.layout_rows.pop(0)
            assert type(row) is list, "Row after header must be a header"

    def dump_widgets(self, layout: bool = True, widget: bool = False):
        """
        Helper function to dump the indexes of the widgets for debugging purposes
        """
        if widget or layout:
            print(f"-" * 100)
        if widget:
            for row in self.widget_rows:
                indexes = [str(col.index) for col in row]
                print(", ".join(indexes))
            print(f"-" * 100)
        if layout:
            for row in self.layout_rows:
                if type(row) is QLabel:
                    print("Header")
                else:
                    indexes = [str(col.index) for col in row]
                    print(", ".join(indexes))
            print(f"-" * 100)

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

        self.scroll_animation(row)

    # ------------------------------------------------------------------------------------------------------------------
    # Custom Event Overrides to capture and them or trigger custom actions
    # ------------------------------------------------------------------------------------------------------------------

    def __init_resize_event(self, a0) -> None:
        """
        Initial call to resize_event will execute this function. It is used to make sure that we have updated the size
        once so the initial layout is made.
        """
        self.update_size()
        # self._scroll_to_row(0)
        super().resizeEvent(a0)
        self.resizeEvent = self.__normal_resize_event

    def __normal_resize_event(self, a0: QResizeEvent) -> None:
        """
        Capture resize event and trigger update of size
        """
        super().resizeEvent(a0)
        global use_timers_resize
        if use_timers_resize:
            self.resize_timer.start(self.resize_timeout)
        else:
            self.update_size()

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
            self._build_up()
            # self.dump_widgets()
        elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._build_down()
            # self.dump_widgets()
        elif a0.key() == Qt.Key.Key_R and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.scroll_offset = 0
            self.place_background_widget()
        else:
            pass


class DatabaseTileView(QFrame):
    glayout: QGridLayout
    scrollbar: QScrollBar
    tiles: TileWidget

    header_label: QLabel
    header_slider: QSlider
    header_slider_value: QLabel

    indicator: QLabel

    # TODO config
    longest_possible_string_name = "Wednesday 31 September 9999"

    def __init__(self, model: Model):
        super().__init__()
        self.glayout = QGridLayout()
        self.glayout.setSpacing(0)
        self.glayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.glayout)

        top = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutTopMargin)
        right = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutRightMargin)
        bottom = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutBottomMargin)
        left = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutLeftMargin)

        header_height = QFontMetrics(QFont()).height() + top + bottom

        self.header_label = QLabel("Some sample text")
        self.header_label.setFixedHeight(header_height)
        self.header_label.setContentsMargins(left, top, right, bottom)
        self.header_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.header_slider = QSlider(Qt.Orientation.Horizontal)
        self.header_slider.setFixedWidth(100)
        self.header_slider.setMinimum(100)
        self.header_slider.setMaximum(500)
        # Connect signals to header_slider
        self.header_slider.valueChanged.connect(self.write_value_to_label)
        self.header_slider.sliderReleased.connect(self.update_tile_size)

        self.header_slider_value = QLabel("Tile Size: 100")
        self.header_slider_value.setFixedHeight(header_height)
        self.header_slider_value.setContentsMargins(left, top, 0, bottom)
        self.header_slider_value.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.scrollbar.sliderReleased.connect(self.update_scroll_on_release)
        self.scrollbar.valueChanged.connect(self.update_scroll_on_change)
        self.scrollbar.sliderPressed.connect(self.set_indicator_visible)

        self.tiles = TileWidget(model)
        self.tiles.prep_dev()
        self.tiles.num_of_rows_changed.connect(self.set_scrollbar_max)
        self.tiles.focus_row_changed.connect(self.scrollbar.setValue)
        self.tiles.page_size_changed.connect(self.scrollbar.setPageStep)

        self.glayout.addWidget(self.header_label, 0, 0, 1, 1)
        self.glayout.addWidget(self.header_slider, 0, 1, 1, 1)
        self.glayout.addWidget(self.header_slider_value, 0, 2, 1, 1)

        self.glayout.addWidget(self.tiles, 1, 0, 1, 3)

        self.glayout.addWidget(self.scrollbar, 1, 3, 1, 1)

        indicator_width = QFontMetrics(QFont()).boundingRect(self.longest_possible_string_name).width() + left + right

        self.indicator = QLabel("Indicator", self)
        self.indicator.setStyleSheet("background-color: palette(dark); color: palette(accent);")
        self.indicator.setContentsMargins(left, top, right, bottom)
        self.indicator.setVisible(False)
        self.indicator.setFixedHeight(header_height)
        self.indicator.setFixedWidth(indicator_width)

    def set_scrollbar_max(self, v: int):
        """
        Set the Maximum of the scrollbar. Needs to be 1 smaller than the actual value since it's inclusive for the
        scrollbar.

        :param v: new maximum value
        """
        self.scrollbar.setMaximum(v - 1)

    def write_value_to_label(self, v: int):
        """
        Function writes the current slider value to the slider label so the user knows about the tile size

        :param v: new value of the slider
        """
        self.header_slider_value.setText(f"Tile Size: {v}")

    def update_tile_size(self):
        """
        Once the slider is released, the slider value is written to the tiles widget which updates accordingly
        """
        self.tiles.tile_size = self.header_slider.value()

    def update_scroll_on_release(self):
        """
        Connection to forward the value of the scrollbar to the tile widget so it scrolls to the right position
        """
        self.tiles.scroll_slot(self.scrollbar.value())
        self.indicator.setVisible(False)

    def set_indicator_visible(self):
        """
        Set the indicator to be visible
        """
        self.indicator.setVisible(True)

    def update_scroll_on_change(self, v: int):
        """
        Update the tiles window when the value changed but the slider wasn't touched for that

        :param v: new value
        """
        # Single button press, capture it and propagate it to the tile widget
        self.update_indicator()
        if not self.scrollbar.isSliderDown():
            self.tiles.scroll_slot(v)


    def update_indicator(self):
        """
        Update the indicator position and text
        """
        min_handle_height = self.scrollbar.style().pixelMetric(self.style().PixelMetric.PM_ScrollBarSliderMin)
        no_arrows = (self.scrollbar.height() - self.scrollbar.width() * 2)
        relative = self.scrollbar.value() / (self.scrollbar.maximum() - self.scrollbar.minimum())

        # Height should be page step / document length
        bar_height_rel = (self.scrollbar.pageStep()
                          / (self.scrollbar.maximum() - self.scrollbar.minimum() + self.scrollbar.pageStep()))
        bar_height_px = math.floor(bar_height_rel * no_arrows)
        handle_height = max(min_handle_height, bar_height_px)

        movement_range = no_arrows - handle_height
        self.indicator.move(self.scrollbar.pos().x() - self.indicator.width(),
                            int(relative * movement_range
                                + (handle_height / 2)
                                + self.scrollbar.width()
                                - self.indicator.height() / 2
                                + self.scrollbar.pos().y()))

        self.indicator.setText(self.tiles.get_indicator_text(self.scrollbar.value()))




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
        self.tiles.page_size_changed.connect(self.scrollbar.setPageStep)
        self.scrollbar.valueChanged.connect(self.set_value)
        self.scrollbar.sliderReleased.connect(self.send_value)

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
    v = QPixmapCache.setCacheLimit(1024)
    # m = Model(folder_path="/home/alisot2000/Desktop/New_DB/")
    # m.current_import_table_name = "tbl_-1886740392237389744"
    # w = TileWidget(m)
    # w.prep_dev()
    # w.show()
    w = TempRoot()
    w.show()

    sys.exit(app.exec())
