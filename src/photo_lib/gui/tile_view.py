from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QGridLayout, QScrollArea, QPushButton, QLabel, \
    QSplitter, QMainWindow, QScrollBar, QHBoxLayout
from PyQt6.QtCore import pyqtSlot, pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QResizeEvent, QKeyEvent
import sys
import datetime
import math
import numpy as np
from typing import Union, List, Tuple
from photo_lib.gui.named_picture_block import CheckNamedPictureBlock
from photo_lib.gui.image_tile import ImageTile
from photo_lib.gui.clickable_image import IndexedTile
from photo_lib.gui.model import Model, GroupCount, GroupingCriterion, TileBuffer
from photo_lib.PhotoDatabase import MatchTypes
from photo_lib.gui.gui_utils import general_wrapper
from photo_lib.data_objects import ImportTileInfo, BaseTileInfo


# TODO register clickable tiles to emmit the img_selected signal
class TileWidget(QFrame):
    # Backend objects
    model: Model
    buffer: TileBuffer

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
    # __current_index = 0
    # __current_tile_info: Union[BaseTileInfo, None] = None

    # Further properties that don't need to be set
    scroll_offset: int = 0

    focus_row_offset: int = 0
    focus_index: int = 0

    lowest_row: int = 0
    highest_row: int = 0

    # Layout
    # TODO config
    tile_size: int = 100  # Different tile size for year, month and day.
    preload_row_count: int = 5
    label_height: int = 30
    __margin: Tuple[int, int, int, int] = (10, 10, 10, 10)  # left, top, right, bottom
    # TODO font size

    # lookup tables
    group_infos: np.ndarray
    row_lut: np.ndarray  # Given a row -> gives the start index that are displayed there
    index_lut: np.ndarray  # given an index -> gives the row that contains this index

    widgets: List[IndexedTile] = None  # List of all widgets that are currently instantiated
    hidden_widgets: List[IndexedTile] = None  # Widgets that are currently hidden
    widget_rows: List[List[IndexedTile]] = None
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
    def number_of_visible_rows(self):
        return self.__number_of_visible_rows

    @number_of_visible_rows.setter
    def number_of_visible_rows(self, value: int):
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
        self.focus_row_changed.emit(self.__focus_row)

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
        self.num_of_rows_changed.emit(self.__number_of_rows)

    # ------------------------------------------------------------------------------------------------------------------
    # Read Properties
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def number_of_generated_rows(self):
        return self.__number_of_generated_rows

    # @property
    # def current_index(self):
    #     return self.__current_index

    # ------------------------------------------------------------------------------------------------------------------
    # Main Methods
    # ------------------------------------------------------------------------------------------------------------------

    def __init__(self, model: Model):
        super().__init__()
        self.model = model
        self.buffer = TileBuffer(model)

        self.group_infos = np.array([])
        self.row_lut = np.array([])
        self.index_lut = np.array([])

        self.widgets = []
        self.hidden_widgets = []
        self.widget_rows = []

        self.background_widget = QWidget(self)
        self.background_widget.move(QPoint(0, 0))
        self.background_widget.setStyleSheet("background-color: rgb(255, 255, 100);")

        self.background_layout = QGridLayout()
        self.background_layout.setContentsMargins(0, 0, 0, 0)
        self.background_layout.setSpacing(10)

        self.background_widget.setLayout(self.background_layout)

    def prep_dev(self):
        self.setMinimumWidth(1000)
        self.setMinimumHeight(1000)
        self.update_groups(GroupingCriterion.YEAR_MONTH_DAY)

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

        self.row_lut = np.array(row_lut, dtype=int)
        self.index_lut = np.array(index_lut, dtype=int)
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

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Capture resize event and trigger update of size
        """
        super().resizeEvent(a0)
        self.update_size()

    def update_size(self):
        """
        Update the sizing of the elements, triggered by resize or by adaptation of the content margins
        """
        margin = self.margin  # left, top, right, bottom
        rem_width = self.width() - margin[0] - margin[2]
        new_number_of_columns = max(1, rem_width // self.tile_size)
        self.background_widget.setFixedWidth(rem_width)

        new_number_of_visible_rows = math.ceil((self.height() - margin[1] - margin[3]) / self.tile_size)

        if (new_number_of_columns == self.number_of_columns and
                new_number_of_visible_rows == self.number_of_visible_rows):
            return

        self.number_of_columns = new_number_of_columns
        self.number_of_visible_rows = new_number_of_visible_rows
        self.build_lut()
        self.increase_widget_count()
        self.resize_layout()
        self.decrease_widget_count()

    def resize_layout(self):
        """
        Resize the layout to the correct size once a resize event is scheduled.
        """
        # TODO serialize the image tiles and rebuild them into rows.
        self.scroll_to_row(self.focus_row)

    def increase_widget_count(self):
        """
        Given the maximum number of widgets displayed at time, increase the number of widgets if resize requires it.
        """
        # Guard if it's less or equal
        print(f"Number of geneated rows: {self.number_of_generated_rows}, Number of columns: {self.number_of_columns}")
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
        for i in range(len(self.widget_rows)):
            for j in range(len(self.widget_rows[i])):
                t = self.widget_rows[i][j]
                self.background_layout.addWidget(t, i, j)
        self.place_background_widget()

    def place_background_widget(self):
        """
        Place the background widget such that the correct row is displayed.
        """
        y = (self.focus_row_offset * self.tile_size
             + max(0, self.focus_row_offset - 1) * self.background_layout.verticalSpacing()
             - self.margin[1])

        self.background_widget.move(QPoint(self.margin[0], -y + self.scroll_offset))

    def fetch_tile(self, index: int) -> BaseTileInfo:
        """
        Fetches a tile from the model.
        """
        return self.buffer.fetch_tile(index)

    def _generate_row(self, row: int) -> List[IndexedTile]:
        """
        Generates a row of widgets. This function does not perform layout.
        """
        if row == self.number_of_rows - 1:
            end = self.buffer.number_of_elements
        else:
            end = self.row_lut[row + 1]

        l = []
        for i in range(self.row_lut[row], end):
            tile = self.fetch_tile(i)
            w = self.get_hidden_widget()
            w.tile_info = tile
            w.index = i
            l.append(w)
        print(len(l))
        return l

    @pyqtSlot(int)
    def scroll_to_row(self, row: int):
        """
        Scroll to a given row.
        """
        assert row >= 0 and row < self.number_of_rows, f"Row out of bounds, [0, {self.number_of_rows}], {row}"
        for r in self.widget_rows:
            for w in r:
                self.move_to_hidden(w)

        self.focus_row = row
        self.focus_row_offset = 0
        self.focus_index = self.row_lut[row]

        # get row associated with focused index
        head_row = self.index_lut[self.focus_index]

        lowest_row = max(0, head_row - self.focus_row_offset)
        self.focus_row_offset = head_row - lowest_row

        self.widget_rows = []
        highest_row = min(self.number_of_rows - 1, head_row + self.number_of_visible_rows + self.preload_row_count - 1)
        for i in range(lowest_row, highest_row + 1):
            self.widget_rows.append(self._generate_row(i))

        self.layout_from_datastructure()

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
            pass
        elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            pass
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
        self.tiles.prep_dev()

        self.layout.addWidget(self.tiles)

        self.scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.scrollbar.setMaximum(self.tiles.number_of_rows)
        self.tiles.num_of_rows_changed.connect(self.set_max)
        self.tiles.focus_row_changed.connect(self.set_val)
        self.scrollbar.valueChanged.connect(self.tiles.scroll_to_row)

        self.layout.addWidget(self.scrollbar)
    def set_max(self, max: int):
        print(f"Max: {max}")
        self.scrollbar.setMaximum(max - 1)

    def set_val (self, val: int):
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
