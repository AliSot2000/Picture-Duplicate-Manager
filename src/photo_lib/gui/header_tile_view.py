from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QGridLayout, QScrollArea, QPushButton, QLabel, QSplitter
from PyQt6.QtCore import pyqtSlot, pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QResizeEvent, QKeyEvent
import sys
import datetime
import math
import numpy as np
from typing import Union, List, Tuple
from photo_lib.gui.named_picture_block import CheckNamedPictureBlock
from photo_lib.gui.image_tile import IndexedTile
from photo_lib.gui.model import Model, GroupCount, GroupingCriterion, TileBuffer
from photo_lib.PhotoDatabase import MatchTypes
from photo_lib.gui.gui_utils import general_wrapper
from photo_lib.data_objects import ImportTileInfo, BaseTileInfo


# TODO register clickable tiles to emmit the img_selected signal
class PhotosTile(QFrame):
    model: Model

    # signals
    num_of_rows_changed = pyqtSignal(int)
    elm_p_col_changed = pyqtSignal(int)
    img_selected = pyqtSignal()
    cur_row_changed = pyqtSignal(int)

    # Signal associated value
    __number_of_elements: int = 0
    __image_selected: int = 0
    __selected_tile: BaseTileInfo = None
    __current_row: int = 0

    # More (less open) values
    __elements_p_col: int = 1
    __max_num_vis_rows: int = 0
    __num_of_rows: int = 0

    # Data structure
    group_infos: np.ndarray
    row_lut: np.ndarray       # Given a row -> gives the start index that are displayed there
    index_lut: np.ndarray     # given an index -> gives the start and end row of that index
    header_lut: np.array      # given a row -> gives the header for that row
    buffer: TileBuffer

    # Layout
    # TODO config
    tile_size: int = 100  # Different tile size for year, month and day.
    preload_row_count: int = 5
    label_height: int = 30
    # TODO font size

    widgets: List[IndexedTile] = None
    hidden_widgets: List[IndexedTile] = None
    widget_rows: List[Union[List[IndexedTile], QWidget, QLabel]] = None
    current_header_widget: Union[None, QLabel] = None
    background_widget: QWidget = None
    background_layout: QGridLayout = None
    current_header_widget_placeholder: QWidget = None

    current_row_index: int = 0
    scroll_offset: int = 0
    lowest_row: int = 0
    highest_row: int = 0

    @property
    def max_num_vis_rows(self):
        return self.__max_num_vis_rows

    @max_num_vis_rows.setter
    def max_num_vis_rows(self, value: int):
        assert value > 0, "Max number of visible rows must be greater than 0"
        if self.__max_num_vis_rows == value:
            return

        self.__max_num_vis_rows = value

    @property
    def cur_row(self):
        return self.__current_row

    @cur_row.setter
    def cur_row(self, value: int):
        assert value >= 0, "Current row must be greater than 0"
        if value == self.__current_row:
            return

        self.__current_row = value
        self.cur_row_changed.emit(value)

    @property
    def selected_tile(self):
        return self.__selected_tile

    @property
    def number_of_elements(self):
        return self.__number_of_elements

    @number_of_elements.setter
    def number_of_elements(self, value: int):
        assert value > 0, "Number of elements must be greater than 0"
        self.__number_of_elements = value

    @property
    def image_selected(self):
        return self.__image_selected

    @image_selected.setter
    def image_selected(self, value: int):
        assert value >= 0, "Number of elements must be greater than 0"

        if value >= self.number_of_elements:
            raise ValueError("Image selected must be smaller than the number of elements")

        if value == self.__image_selected:
            return

        self.__image_selected = value
        self.__selected_tile = self.fetch_tile(value)
        self.img_selected.emit()

    @property
    def num_of_rows(self):
        return self.__num_of_rows

    @num_of_rows.setter
    def num_of_rows(self, value: int):
        assert value > 0, "Number of rows must be greater than 0"
        if self.__num_of_rows == value:
            return

        self.__num_of_rows = value
        self.num_of_rows_changed.emit(value)

    @property
    def elements_p_col(self):
        return self.__elements_p_col

    @elements_p_col.setter
    def elements_p_col(self, value: int):
        assert value > 0, "Number of elements per column must be greater than 0"
        if self.__elements_p_col == value:
            return

        self.__elements_p_col = value
        self.elm_p_col_changed.emit(value)

    def __init__(self, model: Model):
        super().__init__()

        self.model = model
        self.widgets = []
        self.group_infos = np.array([])
        self.row_lut = np.array([])
        self.index_lut = np.array([])
        self.header_lut = np.array([])
        self.hidden_widgets = []
        self.widget_rows = []

        # TODO remove
        self.setMinimumHeight(1200)
        self.setMinimumWidth(1200)
        self.__image_selected = 12

        self.current_header_widget_placeholder = QWidget()
        self.current_header_widget_placeholder.setFixedHeight(self.label_height)

        self.background_widget = QWidget(self)
        self.background_widget.move(QPoint(0, 0))

        self.background_layout = QGridLayout()
        self.background_layout.setContentsMargins(10, 10, 10, 10)
        self.background_layout.setSpacing(10)

        self.background_widget.setLayout(self.background_layout)
        self.buffer = TileBuffer(self.model)
        self._update_base_data()

        for i in range(100):
            t = IndexedTile()
            t.setParent(self)
            t.setVisible(False)
            t.setFixedWidth(self.tile_size)
            t.setFixedHeight(self.tile_size)
            self.widgets.append(t)
            self.hidden_widgets.append(t)

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

    def generate_header(self, index: int) -> QLabel:
        """
        Generates a Header Leabel with formatting for the given index.
        """
        gi = self.group_infos[index]
        text = self.generate_label_text(gi)
        l = QLabel(text)
        l.setFixedHeight(self.label_height)
        l.setStyleSheet("background-color: rgba(255, 255, 255, 200);")
        return l

    @staticmethod
    def generate_label_text(gi: GroupCount) -> str:
        """
        Given a GroupCount object, generate the header for it.
        """
        if gi.group_crit == GroupingCriterion.YEAR_MONTH_DAY:
            return gi.start_date.strftime("%A %d %B %Y")
        elif gi.group_crit == GroupingCriterion.YEAR_MONTH:
            return gi.start_date.strftime("%B %Y")
        elif gi.group_crit == GroupingCriterion.YEAR:
            return gi.start_date.strftime("%Y")
        else:
            return ""

    # TODO Implement scrolling with scroll wheel.
    # def wheelEvent(self, a0: QtGui.QWheelEvent) -> None:
    #     pass

    def _update_base_data(self):
        """
        Updates the group data and the number of elements.
        Updates the buffer and also the index lut.
        """
        self.number_of_elements = self.model.get_total_image_count()
        gi = self.model.get_group_image_count()
        self.group_infos = np.array(gi, dtype=GroupCount)
        self.buffer.update_number_of_elements()
        self.compute_lut()

    def fetch_tile(self, index: int) -> BaseTileInfo:
        """
        Fetches tile from buffer given the index in the chronological sorting.

        :param index: Index in chronological sorting
        """
        return self.buffer.fetch_tile(index)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        super().resizeEvent(a0)
        margin = self.background_layout.getContentsMargins()  # left, top, right, bottom
        rem_width = self.width() - margin[0] - margin[2] * 2
        new_epc = max(1, rem_width // self.tile_size)
        self.background_widget.setFixedWidth(self.width())

        new_mnvr = math.ceil((self.height() - margin[1] - margin[3] - self.label_height) / self.tile_size)

        # Move the header
        if self.current_header_widget is not None:
            self.current_header_widget.setFixedWidth(rem_width)

        if new_epc == self.elements_p_col and new_mnvr == self.max_num_vis_rows:
            return

        self.elements_p_col = new_epc
        self.max_num_vis_rows = new_mnvr
        self.compute_lut()
        self.update_widget_count()
        self.layout_elements()

    def update_widget_count(self):
        """
        Update the number of widgets that are loaded. Performs layout subsequently.
        """
        # TODO implement
        now = (self.max_num_vis_rows + self.preload_row_count * 2) * self.elements_p_col
        if now == len(self.widgets):
            return

        elif now < len(self.widgets):
            self.build_rows()
            assert len(self.hidden_widgets) >= now - len(self.widgets), \
                "The number of hidden widgets is smaller than the number of widgets that we want to remove"
            rm = self.hidden_widgets[:now - len(self.widgets)]
            self.hidden_widgets = self.hidden_widgets[now - len(self.widgets):]

            for w in rm:
                w.deleteLater()

        else:
            assert now > len(self.widgets), "We should have to add widgets now"
            widgets_to_add = now - len(self.widgets)
            for i in range(widgets_to_add):
                t = IndexedTile()
                self.widgets.append(t)
                self.hidden_widgets.append(t)
                t.setFixedHeight(self.tile_size)
                t.setFixedWidth(self.tile_size)
            self.build_rows()

    def compute_lut(self):
        """
        Computes the look up table for the rows and headers. Also updates the current row.

        Precondition: The number_or_cols and number_of_rows are set.
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
                new_index = index + (self.elements_p_col if self.elements_p_col < img_count else img_count)
                row_lut.append(index)

                for j in range(index, new_index):
                    index_lut.append(row_count)

                if index <= self.image_selected < new_index:
                    cur_row = row_count
                index = new_index
                row_count += 1
                header_lut.append(i)
                img_count -= self.elements_p_col

        self.header_lut = np.array(header_lut, dtype=int)
        self.row_lut = np.array(row_lut, dtype=int)
        self.index_lut = np.array(index_lut, dtype=int)
        self.num_of_rows = row_count
        self.cur_row = cur_row
        stop = datetime.datetime.now()
        print(f"Compute lut took: {(stop - start).total_seconds()}")
        print(f"Number of rows: {self.num_of_rows}")

    @pyqtSlot()
    def move_up(self):
        """
        Move the view up by one increment
        """
        # TODO implement
        self.scroll_offset -= 30
        self.background_widget.move(0, self.scroll_offset)

    @pyqtSlot()
    def move_down(self):
        """
        Move the view down by one increment
        """
        # TODO implement
        self.scroll_offset += 30
        self.background_widget.move(0, self.scroll_offset)

    def widget_offset(self):
        """
        Gets the number of rows excluding label to the current index.
        """
        c = 0
        for i in range(self.current_row_index):
            c += int(type(self.widget_rows[i]) is list)
        return c

    def build_up(self):
        """
        Goes up one row of images.
        """
        pass

    def build_down(self):
        """
        Goes down one row of images.
        """
        wo = self.widget_offset()
        print(wo)
        if wo == self.preload_row_count:

            # we have more space at the bottom and can load a new row:
            if self.cur_row + self.preload_row_count + self.max_num_vis_rows + 1 < self.num_of_rows:
                r = self.widget_rows.pop(0)

                if type(r) is QLabel:
                    print("Head is Label, deleting label")
                    r.deleteLater()
                    r = self.widget_rows.pop(0)
                    self.scroll_offset += self.label_height + self.background_layout.verticalSpacing()
                    self.current_row_index -= 1

                elif type(r) is QWidget:
                    print("Head is QWidget, ignoring")
                    r = self.widget_rows.pop(0)
                    self.scroll_offset += self.label_height + self.background_layout.verticalSpacing()
                    self.current_row_index -= 1

                assert type(r) is list, f"Row must be a list if it is not a Label, type is  {type(r)}"
                self.scroll_offset += self.tile_size + self.background_layout.verticalSpacing()
                for w in r:
                    self.move_to_hidden(w)

                self.lowest_row += 1

                # Need to decrement once for the removed element at the top, increment once since we are moving down.
                # self.current_row_index -= 1
                # self.current_row_index += 1

                while type(self.widget_rows[self.current_row_index]) is not list:
                    print("Updating")
                    self.current_row_index += 1

                # check if we need a header:
                if self.header_lut[self.highest_row] != self.header_lut[self.highest_row + 1]:
                    self.widget_rows.append(self.generate_header(self.header_lut[self.highest_row]))
                    print("Added a new header")

                self.widget_rows.append(self._generate_row(self.highest_row + 1))
                print("Added a new row")
                self.highest_row = self.highest_row + 1
                self.layout_elements()
                self.cur_row += 1
            else:
                self.current_row_index += 1
        elif wo < self.preload_row_count:
            print("Upper border")
            self.current_row_index += 1
        elif wo + 1 < len(self.widget_rows):
            print("Lower border")
            self.current_row_index += 1
        else:
            # We've reached the bottom of the view.
            print("Reached end")
            pass

    @pyqtSlot(int)
    def move_to_index(self, index: int):
        """
        Given an index in the time series. Move the view to that index is in view.
        """
        row = self.index_lut[index]
        self.move_to_row(row)

    @pyqtSlot(int)
    def move_to_row(self, row: int):
        """
        Given a row in the view, move the view to that row.
        """
        # TODO add handling if row is already loaded.

        # Create the Header
        self.current_header_widget = self.generate_header(self.header_lut[row])
        self.current_header_widget.setFixedHeight(self.label_height)

        self.hidden_widgets = [w for w in self.widgets]
        self.widget_rows = [self._generate_row(row)]
        r = self.widget_rows[0]
        self.lowest_row = max(-1, row - self.preload_row_count - 1)
        place_holder_put = False

        # Generate the rows abovef
        for i in range(row -1, self.lowest_row, -1):
            if place_holder_put:
                if self.header_lut[i] != self.header_lut[i+1]:
                    self.widget_rows.insert(0, self.generate_header(self.header_lut[i]))
                self.widget_rows.insert(0, self._generate_row(i))
            else:
                if self.header_lut[row] != self.header_lut[i]:
                    # We are immediately followed by our picture. Insert the Label directly
                    if i == row - 1:
                        self.widget_rows.insert(0, self.current_header_widget)
                        self.current_header_widget = None
                    else:
                        self.widget_rows.insert(0, self.current_header_widget_placeholder)
                    place_holder_put = True
                    self.widget_rows.insert(0, self._generate_row(i))
                else:
                    self.widget_rows.insert(0, self._generate_row(i))

        self.current_row_index = self.widget_rows.index(r)
        self.highest_row = min(row + self.preload_row_count + self.max_num_vis_rows + 1, self.num_of_rows)
        # Generate Rows down
        for i in range(row + 1, self.highest_row):
            if self.header_lut[i - 1] != self.header_lut[i]:
                self.widget_rows.append(self.generate_header(self.header_lut[i]))
            self.widget_rows.append(self._generate_row(i))

        self.cur_row = row
        self.layout_elements()

    def _generate_row(self, row: int) -> List[IndexedTile]:
        """
        Generates a row of widgets. This function does not perform layout.
        """
        if row == self.num_of_rows - 1:
            end = self.number_of_elements
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

    def build_rows(self):
        """
        Build the rows. Function used by resizing event. This function does not perform layout.
        """
        pass

    def layout_elements(self):
        """
        Layout the elements in the view.
        """
        # Empty layout
        while self.background_layout.count() > 0:
            self.background_layout.takeAt(0)

        for i in range(len(self.widget_rows)):
            r = self.widget_rows[i]

            if type(r) is QLabel or type(r) is QWidget:
                self.background_layout.addWidget(r, i, 0, 1, self.elements_p_col)
                r.setVisible(True)
            else:
                assert type(r) is list, f"Row must be a list if it is not a Label or Placeholder, type is  {type(r)}"
                assert len(r) <= self.elements_p_col, (f"Row must have less or equal tho number of elements per "
                                                       f"column, epc: {self.elements_p_col}, row: {len(r)}")
                # Inserting widgets
                for j in range(len(r)):
                    self.background_layout.addWidget(r[j], i, j, 1, 1)
                    r[j].setVisible(True)

        margin = self.background_layout.getContentsMargins()  # left, top, right, bottom
        # if self.current_header_widget is not None:
        #     self.background_widget.setParent(None)
        #     self.current_header_widget.setParent(None)
        #     self.background_widget.setParent(self)
        #     self.current_header_widget.setParent(self)
        #     self.current_header_widget.move(margin[0], margin[1])

        h = margin[1] + margin[3]
        for i in range(len(self.widget_rows)):
            if i > 0:
                h += self.background_layout.verticalSpacing()
            if type(self.widget_rows[i]) is list:
                h += self.tile_size
            else:
                h += self.label_height
            self.background_widget.setFixedHeight(h)

        # Compute position of background widget
        self.background_widget.move(0, self.scroll_offset)

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """
        Catch keys from keyboard and move the carousel accordingly.
        :param a0:
        :return:
        """
        super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Up and a0.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.move_up()
        elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.move_down()
        elif a0.key() == Qt.Key.Key_Up and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.build_up()
        elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.build_down()
        else:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    m = Model(folder_path="/home/alisot2000/Desktop/New_DB/")
    m.current_import_table_name = "tbl_-1886740392237389744"
    m.build_tiles_from_table()
    w = PhotosTile(m)
    w.show()
    sys.exit(app.exec())