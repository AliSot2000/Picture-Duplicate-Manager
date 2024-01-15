from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QGridLayout, QScrollArea, QPushButton, QLabel, QSplitter
from PyQt6.QtCore import pyqtSlot, pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QResizeEvent, QKeyEvent
import sys
import datetime
import math
import numpy as np
from typing import Union, List, Tuple
from photo_lib.gui.named_picture_block import CheckNamedPictureBlock
from photo_lib.gui.image_tile import NamedTile, IndexedTile
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

    image_clicked = pyqtSignal(NamedTile)
    tiles: List[NamedTile] = None

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

    def _tile_clicked(self, tile: NamedTile):
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    m = Model(folder_path="/home/alisot2000/Desktop/New_DB/")
    m.grouping = GroupingCriterion.YEAR_MONTH_DAY
    # window = ImportView(m)
    window = PhotosTile(m)
    window.setMinimumWidth(400)
    window.setMinimumHeight(400)
    window.move_to_row(1600)
    # window.model.current_import_table_name = "tbl_1998737548188488947"
    window.model.build_tiles_from_table()
    window.setWindowTitle("Import View")

    # window.build_import_view()
    window.show()
    sys.exit(app.exec())