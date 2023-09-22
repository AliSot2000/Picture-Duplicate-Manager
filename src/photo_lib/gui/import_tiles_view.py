from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QGridLayout, QScrollArea, QPushButton, QLabel, QSplitter
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


class ImportView(QFrame):
    model: Model
    scroll_area: QScrollArea

    dummy_widget: QWidget
    import_name: QLabel
    inner_layout: QVBoxLayout
    outer_layout: QVBoxLayout

    no_match_block: Union[None, CheckNamedPictureBlock] = None
    binary_match_block: Union[None, CheckNamedPictureBlock] = None
    binary_match_replaced_block: Union[None, CheckNamedPictureBlock] = None
    binary_match_trash_block: Union[None, CheckNamedPictureBlock] = None
    hash_match_replaced_block: Union[None, CheckNamedPictureBlock] = None
    hash_match_trash_block: Union[None, CheckNamedPictureBlock] = None
    not_allowed_block: Union[None, CheckNamedPictureBlock] = None

    blocks: List[CheckNamedPictureBlock] = None

    image_clicked = pyqtSignal(ImageTile)
    tiles: List[ImageTile] = None

    def __init__(self, model: Model):
        """
        Create all layout and widgets needed for the import view.
        :param model: model that holds the data.
        """
        super().__init__()
        self.model = model

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.import_name = QLabel()

        self.outer_layout = QVBoxLayout()
        self.setLayout(self.outer_layout)

        self.inner_layout = QVBoxLayout()
        self.inner_layout.setContentsMargins(0, 0, 0, 0)

        self.dummy_widget = QWidget()
        self.dummy_widget.setLayout(self.inner_layout)

        self.outer_layout.addWidget(self.import_name)
        self.outer_layout.addWidget(self.scroll_area)
        self.scroll_area.setWidget(self.dummy_widget)

        self.build_import_view()
        self.tiles = []

    def get_selected(self) -> Tuple[List[MatchTypes], List[int]]:
        """
        Returns a list of the MatchTypes which are selected but not yet imported.
        :return:
        """
        marked_sections = []
        marked_keys = []
        for block in self.blocks:
            if block.import_checkbox.checkState() == Qt.CheckState.Checked:
                marked_sections.append(block.match_type)
            elif block.import_checkbox.checkState() == Qt.CheckState.PartiallyChecked:
                for tile in block.picture_block.img_tiles:
                    if tile.tile_info.mark_for_import:
                        marked_keys.append(tile.tile_info.key)

        return marked_sections, marked_keys

    def tile_marked_for_import(self, tile: ImportTileInfo, marked: bool):
        """
        Function that is called when a tile is marked for import.
        :param marked: if the tile was set to marked, or unmarked.
        :param tile: tile that was updated
        :return:
        """
        # Tile newly marked, need to set the import checkbox to half checked.
        if marked:
            if not tile.allowed:
                self.not_allowed_block.tile_for_single_import(tile)

            elif tile.match_type == MatchTypes.No_Match:
                self.no_match_block.tile_for_single_import(tile)

            elif tile.match_type == MatchTypes.Binary_Match_Images:
                self.binary_match_block.tile_for_single_import(tile)

            elif tile.match_type == MatchTypes.Binary_Match_Replaced:
                self.binary_match_replaced_block.tile_for_single_import(tile)

            elif tile.match_type == MatchTypes.Binary_Match_Trash:
                self.binary_match_trash_block.tile_for_single_import(tile)

            elif tile.match_type == MatchTypes.Hash_Match_Replaced:
                self.hash_match_replaced_block.tile_for_single_import(tile)

            elif tile.match_type == MatchTypes.Hash_Match_Trash:
                self.hash_match_trash_block.tile_for_single_import(tile)

            else:
                raise ValueError(f"Unknown match type: {tile.match_type}")
        else:
            # Tile newly unmarked, need to set the import checkbox to unchecked.
            if not tile.allowed:
                self.not_allowed_block.unmarked_tile_for_import(tile)

            elif tile.match_type == MatchTypes.No_Match:
                self.no_match_block.unmarked_tile_for_import(tile)

            elif tile.match_type == MatchTypes.Binary_Match_Images:
                self.binary_match_block.unmarked_tile_for_import(tile)

            elif tile.match_type == MatchTypes.Binary_Match_Replaced:
                self.binary_match_replaced_block.unmarked_tile_for_import(tile)

            elif tile.match_type == MatchTypes.Binary_Match_Trash:
                self.binary_match_trash_block.unmarked_tile_for_import(tile)

            elif tile.match_type == MatchTypes.Hash_Match_Replaced:
                self.hash_match_replaced_block.unmarked_tile_for_import(tile)

            elif tile.match_type == MatchTypes.Hash_Match_Trash:
                self.hash_match_trash_block.unmarked_tile_for_import(tile)

            else:
                raise ValueError(f"Unknown match type: {tile.match_type}")

    def focus_tile_from_tile_info(self, tile_info: ImportTileInfo):
        """
        When moving back to this layout, we can ensure the image we had currently open in the other view is currently
        viewable in the scroll area.
        :param tile_info:
        :return:
        """
        for t in self.tiles:
            if t.tile_info == tile_info:
                self.scroll_area.ensureWidgetVisible(t.clickable_image)
                break

    def _tile_clicked(self, tile: ImageTile):
        """
        Function that is called when an image tile is clicked. Emits the image_clicked signal.
        Do not call this function from outside the class.
        :param tile: tile that was clicked.
        :return:
        """
        self.image_clicked.emit(tile)

    def build_import_view(self):
        """
        Build the import view from the current tile_infos from the model.

        :return:
        """
        self.tiles = []
        self.blocks = []

        # Empty layout
        while self.inner_layout.count() > 0:
            self.inner_layout.takeAt(0).widget().deleteLater()

        self.update_name()

        # Explicitly coding the different values for the match_types to allow for more verbose naming of subsections.
        if len(self.model.tile_infos) == 0:
            return

        # Add Block for no match
        if len(self.model.get_import_no_match()) > 0:
            self.no_match_block = CheckNamedPictureBlock(mt=MatchTypes.No_Match,
                                       tile_infos=self.model.get_import_no_match(),
                                       title="Media Files without Match in the Database")
            self.inner_layout.addWidget(self.no_match_block)
            self.tiles.extend(self.no_match_block.picture_block.img_tiles)
            self.blocks.append(self.no_match_block)

        # Add block for binary match
        if len(self.model.get_import_binary_match()) > 0:
            self.binary_match_block= CheckNamedPictureBlock(mt=MatchTypes.Binary_Match_Images,
                                       tile_infos=self.model.get_import_binary_match(),
                                       title="Media Files with Binary Match in Database")
            self.inner_layout.addWidget(self.binary_match_block)
            self.tiles.extend(self.binary_match_block.picture_block.img_tiles)
            self.blocks.append(self.binary_match_block)

        # Add block for binary match in replaced
        if len(self.model.get_import_binary_match_replaced()) > 0:
            self.binary_match_replaced_block = CheckNamedPictureBlock(mt=MatchTypes.Binary_Match_Replaced,
                                       tile_infos=self.model.get_import_binary_match_replaced(),
                                       title="Media Files with Binary Match in the known Duplicates")
            self.inner_layout.addWidget(self.binary_match_replaced_block)
            self.tiles.extend(self.binary_match_replaced_block.picture_block.img_tiles)
            self.blocks.append(self.binary_match_replaced_block)

        # Add block for binary match in trash
        if len(self.model.get_import_binary_match_trash()) > 0:
            self.binary_match_trash_block = CheckNamedPictureBlock(mt=MatchTypes.Binary_Match_Trash,
                                       tile_infos=self.model.get_import_binary_match_trash(),
                                       title="Media Files with Binary Match in the Trash")
            self.inner_layout.addWidget(self.binary_match_trash_block)
            self.tiles.extend(self.binary_match_trash_block.picture_block.img_tiles)
            self.blocks.append(self.binary_match_trash_block)

        # Add block for hash match in replaced
        if len(self.model.get_import_hash_match_replaced()) > 0:
            self.hash_match_replaced_block = CheckNamedPictureBlock(mt=MatchTypes.Hash_Match_Replaced,
                                        tile_infos=self.model.get_import_hash_match_replaced(),
                                        title="Media Files with matching hash and filesize in the known Duplicates")
            self.inner_layout.addWidget(self.hash_match_replaced_block)
            self.tiles.extend(self.hash_match_replaced_block.picture_block.img_tiles)
            self.blocks.append(self.hash_match_replaced_block)

        # Add block for hash match in trash
        if len(self.model.get_import_hash_match_trash()) > 0:
            self.hash_match_trash_block = CheckNamedPictureBlock(mt=MatchTypes.Hash_Match_Trash,
                                        tile_infos=self.model.get_import_hash_match_trash(),
                                        title="Media Files with matching hash and filesize in the Trash")
            self.inner_layout.addWidget(self.hash_match_trash_block)
            self.tiles.extend(self.hash_match_trash_block.picture_block.img_tiles)
            self.blocks.append(self.hash_match_trash_block)

        # Add block for not allowed files.
        if len(self.model.get_import_not_allowed()) > 0:
            self.not_allowed_block = CheckNamedPictureBlock(mt=None,
                                        tile_infos=self.model.get_import_not_allowed(),
                                        title="Media Files not allowed to be imported based on file extension")
            self.not_allowed_block.import_checkbox.setDisabled(True)
            self.inner_layout.addWidget(self.not_allowed_block)
            self.tiles.extend(self.not_allowed_block.picture_block.img_tiles)
            self.blocks.append(self.not_allowed_block)

        for tile in self.tiles:
            tile.clickable_image.clicked.connect(general_wrapper(func=self._tile_clicked, tile=tile))

    def update_name(self):
        """
        Updates the name of the current import. Fetch it from the database.
        :return:
        """
        table_desc = self.model.get_current_import_table_name()
        if table_desc is not None:
            self.import_name.setText(table_desc)
        elif self.model.current_import_table_name is not None:
            self.import_name.setText(self.model.current_import_table_name)
        else:
            self.import_name.setText("Import Source Unknown")


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
    __elements_p_col: int = 5
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
    current_header_widget: Union[None, QLabel] = None
    background_widget: QWidget = None
    background_layout: QGridLayout = None
    widget_rows: List[Union[List[IndexedTile], QWidget, QLabel]] = None
    hidden_widgets: List[IndexedTile] = None
    current_header_widget_placeholder: QWidget = None
    current_row_index: int = 0
    scroll_offset: int = 0

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
            t.setFixedWidth(self.tile_size)
            t.setFixedHeight(self.tile_size)
            self.widgets.append(t)

        self.hidden_widgets = self.widgets

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
        self.group_infos = self.model.get_group_image_count()
        self.buffer.update_number_of_elements()
        index = 0
        self.index_lut = []
        for i in range(len(self.group_infos)):
            c = self.group_infos[i]
            self.index_lut.append((index, index + c.count))
            index += c.count

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
        self.background_widget.setFixedWidth(self.width())
        self.elements_p_col = max(1, rem_width // self.tile_size)
        self.compute_lut()
        self.update_widget_count()

    def update_widget_count(self):
        """
        Update the number of widgets that are loaded
        """
        # TODO implement
        return 100

    def compute_lut(self):
        """
        Computes the look up table for the rows and headers. Also updates the current row.

        Precondition: The number_or_cols and number_of_rows are set.
        """
        self.row_lut = []
        self.index_lut = []
        index = 0
        row_count = 0
        cur_row = 0

        for i in range(len(self.group_infos)):
            cur_info = self.group_infos[i]
            img_count = cur_info.count

            while img_count > 0:
                new_index = index + (self.elements_p_col if self.elements_p_col < img_count else img_count)
                if index <= self.image_selected < new_index:
                    cur_row = row_count
                index = new_index
                row_count += 1
                self.row_lut.append(i)
                img_count -= self.elements_p_col

        self.num_of_rows = row_count
        self.cur_row = cur_row

    @pyqtSlot()
    def move_up(self):
        """
        Move the view up by one increment
        """
        # TODO implement
        pass

    @pyqtSlot()
    def move_down(self):
        """
        Move the view down by one increment
        """
        # TODO implement
        pass

    pyqtSlot(int)
    def move_to_index(self, index: int):
        """
        Given an index in the time series. Move the view to that index is in view.
        """
        pass

    pyqtSlot(int)
    def move_to_row(self, index: int):
        """
        Given a row, scroll to that row.
        """
        pass

    def layout_elements(self):
        """
        Layout the elements in the view.
        """
        # TODO generate rows. Generate widgets. Generate headers. Generate placeholders.

        # Empty layout
        while self.background_layout.count() > 0:
            self.background_layout.takeAt(0)

        for i in range(len(self.widget_rows)):
            r = self.widget_rows[i]

            if type(r) is QLabel or type(r) is QWidget:
                self.background_layout.addWidget(r, i, 0, 1, self.elements_p_col)
            else:
                assert type(r) is List, "Row must be a list if it is not a Label or Placeholder"
                assert len(r) <= self.elements_p_col, "Row must have less or equal tho number of elements per column"
                # Inserting widgets
                for j in range(len(r)):
                    self.background_layout.addWidget(r[j], i, j, 1, 1)

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """
        Catch keys from keyboard and move the carousel accordingly.
        :param a0:
        :return:
        """
        super().keyPressEvent(a0)
        if a0.key() == Qt.Key.Key_Up:
            self.move_up()
        elif a0.key() == Qt.Key.Key_Down:
            self.move_down()
        else:
            pass
        self.layout_elements()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = ImportView(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.model.build_tiles_from_table()
    window.setWindowTitle("Import View")

    window.build_import_view()
    window.show()
    sys.exit(app.exec())