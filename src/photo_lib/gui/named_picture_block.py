import os
import sys
import math
from typing import List, Union
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QCheckBox, QApplication, QMainWindow, QScrollArea, QFrame, \
    QWidget
from PyQt6 import QtGui
from PyQt6.QtCore import QSize, Qt

from photo_lib.gui.image_tile import ImageTile
from photo_lib.PhotoDatabase import TileInfo, MatchTypes


class Row(QFrame):
    """
    Simple class to represent a single row of image tiles.
    """
    h_layout: QHBoxLayout

    def __init__(self, tiles: List[Union[QWidget, ImageTile]]):
        """
        Initialize and add a list of image tiles.

        :param tiles: List of ImageTiles and empty images.
        """
        super().__init__()
        self.h_layout = QHBoxLayout()
        # self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.h_layout)

        for i in range(len(tiles)):
            tile = tiles[i]
            self.h_layout.addWidget(tile)

            if i < len(tiles) -1:
                self.h_layout.addStretch()


class PictureBlock(QFrame):
    """
    Block of images that belong together. Class tries to layout the images in a way that maximizes the number
    of displayed images.
    """

    # TODO needs to go into config or something.
    tile_size: int = 200
    last_n_h_tiles: int = -1
    img_tiles: List[ImageTile] = None

    v_layout: QVBoxLayout

    def __init__(self, tile_infos: List[TileInfo] = None):
        """
        Provide a list of tiles to be displayed in a block
        :param tile_infos: List of TileInfo objects. These contain the relevant information tied to the database to
        display the images.
        """
        super().__init__()
        self.v_layout = QVBoxLayout()
        # self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.v_layout)

        self.setMinimumWidth(self.tile_size + 20)

        self.generate_tiles(tile_infos)
        self.layout_tiles()

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        """
        We need to relayout the tiles when the window is resized.

        :param a0: Resize evenet
        :return:
        """
        super().resizeEvent(a0)
        self.layout_tiles()

    def generate_tiles(self, tile_infos: List[TileInfo]):
        """
        Given a list of TileInfo objects, generate the tiles.

        :param tile_infos: List of TileInfo objects.
        :return:
        """
        self.img_tiles = []

        for tile_info in tile_infos:
            tile = ImageTile(tile_info)
            tile.setMaximumHeight(self.tile_size)
            tile.setMaximumWidth(self.tile_size)
            tile.b_layout.setContentsMargins(0, 0, 0, 0)
            self.img_tiles.append(tile)

    def layout_tiles(self):
        """
        Layout the tiles in the v_layout. This will remove all tiles from the layout and re-add them.

        This function will need to be overwritten if you have anything else in the layout

        :return:
        """
        n_h_tiles = math.ceil((self.width() - 10) / (self.tile_size + 10))

        if n_h_tiles == self.last_n_h_tiles:
            return

        self.last_n_h_tiles = n_h_tiles
        height = math.ceil(len(self.img_tiles) / n_h_tiles) * (self.tile_size + 10) + 10
        self.setMinimumHeight(height)

        # empty layout
        while self.v_layout.count():
            self.v_layout.takeAt(0)

        # Loop through rows
        for i in range(0, len(self.img_tiles), n_h_tiles):
            # Create a new horizontal layout for row
            tiles = self.img_tiles[i:i + n_h_tiles]

            # Padding last row.
            if len(tiles) < n_h_tiles:
                for _ in range(n_h_tiles - len(tiles)):
                    w = QWidget()
                    w.setFixedSize(QSize(self.tile_size, self.tile_size))
                    tiles.append(w)

            row = Row(tiles)
            row.h_layout.setContentsMargins(0, 0, 0, 0)

            # Add the row to the main layout.
            self.v_layout.addWidget(row)
            if i < len(self.img_tiles) - n_h_tiles:
                self.v_layout.addStretch()
        # for tile in self.img_tiles:
        #     self.v_layout.addWidget(QLabel("Test"))
        #     self.v_layout.addStretch()


class CheckNamedPictureBlock(QFrame):
    import_checkbox: QCheckBox
    match_type: MatchTypes = None
    picture_block: PictureBlock = None
    __global_marking: bool = True
    __all_imported: bool = False

    def __init__(self, mt: MatchTypes = None, tile_infos: List[TileInfo] = None, title: str = None):
        super().__init__()
        self.match_type = mt
        if title is None and mt is not None:
            title = f"Import: {mt.name.replace('_', ' ').title()}"
        self.import_checkbox = QCheckBox(title)
        self.import_checkbox.setStyleSheet("padding: 10px; "
                                           "border: 2px solid black;")

        self.v_layout = QVBoxLayout()
        self.v_layout.addWidget(self.import_checkbox)
        # self.v_layout.setContentsMargins(0, 0, 0, 0)

        self.picture_block = PictureBlock(tile_infos=tile_infos)
        self.picture_block.v_layout.setContentsMargins(0, 0, 0, 0)
        # self.picture_block.setFrameStyle(QFrame.Shape.Box)
        self.v_layout.addWidget(self.picture_block)

        self.setLayout(self.v_layout)

        self.import_checkbox.clicked.connect(self.update_colors)
        self.determine_global_marking()
        self.update_colors()

    def determine_global_marking(self):
        """
        Determine if all tiles are marked for import or not or are already imported..
        :return:
        """
        self.__global_marking = True
        initial_state = self.picture_block.img_tiles[0].tile_info.imported

        # Iterate through tiles and check if they are all the same.
        for tile in self.picture_block.img_tiles:
            if tile.tile_info.imported != initial_state:
                self.__global_marking = False
                return

        self.__all_imported = initial_state

    def tile_for_single_import(self, tile: TileInfo):
        """
        A single tile was marked for import.
        :param tile: tile info that needs to match for update.
        :return:
        """
        # TODO nothing special happens if you turn all tiles in a block to import
        #   Technically, you would have to set the global marking to true and then set the checkbox to checked.

        assert not tile.imported, "Tile was unmarked for import but was already imported."
        self.import_checkbox.setTristate(True)
        self.import_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)

        if self.__global_marking:
            self.__global_marking = False
            self.reset_mark()
            self.update_colors()
        else:
            self.update_tile_marking(tile)

    def update_tile_marking(self, tile: TileInfo):
        """
        Update the marking of a single tile
        :param tile: tile info that needs to match for update.
        :return:
        """
        for t in self.picture_block.img_tiles:
            if t.tile_info == tile:
                if tile.imported:
                    t.set_imported()
                elif tile.mark_for_import:
                    t.marked_for_import()
                else:
                    t.marked_not_for_import()

    def unmarked_tile_for_import(self, tile: TileInfo):
        """
        A single tile was unmarked for import. Check if now all tiles are unmarked.
        :return:
        """
        assert not tile.imported, "Tile was unmarked for import but was already imported."
        org_tile_mark = self.picture_block.img_tiles[0].tile_info.mark_for_import
        org_tile_imported = self.picture_block.img_tiles[0].tile_info.imported

        # Check if the imported state and the marked state are equivalent access everything.
        for t in self.picture_block.img_tiles:
            # As soon as a single tile is out of line, we only update the tile we got the signal from.
            if org_tile_mark != t.tile_info.mark_for_import:
                self.update_tile_marking(tile)
                return
            if org_tile_imported != t.tile_info.imported:
                self.update_tile_marking(tile)
                return

        # Everything is the same, set the global marking.
        self.__global_marking = True

        # Updating the tri state.
        self.import_checkbox.setTristate(False)
        state = Qt.CheckState.Checked if org_tile_mark else Qt.CheckState.Unchecked
        self.import_checkbox.setCheckState(state)

        # Removing mark on the image tile level.
        for t in self.picture_block.img_tiles:
            t.reset_mark()
        self.update_colors()

    def update_colors(self):
        """
        Update the colors of the block or on the level of single images.
        :return:
        """
        if self.__all_imported:
            self.set_imported()
            return

        if self.__global_marking:
            if self.import_checkbox.isChecked():
                self.marked_for_import()
            else:
                self.marked_not_for_import()
        else:
            if self.import_checkbox.checkState() == Qt.CheckState.PartiallyChecked:
                self.reset_mark()
                for tile in self.picture_block.img_tiles:
                    # If the tile is imported, we can't change it, set it to imported
                    if tile.tile_info.imported:
                        tile.set_imported()
                    # If we have the tile set to import or the checkbox is checked, mark it for import.
                    elif tile.tile_info.mark_for_import:
                        tile.marked_for_import()
                    # Otherwise, mark it not for import.
                    else:
                        tile.marked_not_for_import()
            else:
                if self.import_checkbox.isChecked():
                    self.marked_for_import()
                else:
                    self.marked_not_for_import()
                for tile in self.picture_block.img_tiles:
                    tile.reset_mark()
    def set_imported(self):
        """
        All files were imported. Set block state to imported.
        :return:
        """
        self.import_checkbox.setChecked(True)
        self.import_checkbox.setDisabled(True)
        # Set color green
        self.setStyleSheet("background-color: rgb(200, 255, 200);")

    def marked_for_import(self):
        """
        Mark the block for import.
        :return:
        """
        # Set color yellow
        self.setStyleSheet("background-color: rgb(255, 255, 200);")

    def marked_not_for_import(self):
        """
        Unmark the block for import.
        :return:
        """
        # Set color red
        self.setStyleSheet("background-color: rgb(255, 200, 200);")

    def reset_mark(self):
        """
        Remove the mark.
        :return:
        """
        self.setStyleSheet("")


class TempRoow(QMainWindow):
    def __init__(self):
        super().__init__()
        target = "/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images"
        images = os.listdir(target)
        sample_tiles = [TileInfo(key=1, path=os.path.join(target, image), imported=False, allowed=False,
                                 match_type=MatchTypes.No_Match) for image in images]

        self.sca = QScrollArea()
        self.sca.setWidgetResizable(True)
        self.sca.setWidget(CheckNamedPictureBlock(mt=MatchTypes.Hash_Match_Replaced, tile_infos=sample_tiles))
        self.setCentralWidget(self.sca)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    root = TempRoow()
    root.show()
    sys.exit(app.exec())