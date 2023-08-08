import os
import sys
import math
from typing import List, Union
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QCheckBox, QApplication, QMainWindow, QScrollArea, QFrame, \
    QWidget
from PyQt6 import QtGui

from photo_lib.gui.image_tile import ImageTile
from photo_lib.PhotoDatabase import TileInfo, MatchTypes


class Row(QFrame):
    h_layout: QHBoxLayout

    def __init__(self, tiles: List[ImageTile]):
        super().__init__()
        self.h_layout = QHBoxLayout()
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.h_layout)

        self.h_layout.addStretch()
        for tile in tiles:
            self.h_layout.addWidget(tile)
            self.h_layout.addStretch()


class PictureBlock(QFrame):
    # TODO needs to go into config or something.
    tile_size: int = 200
    last_n_h_tiles: int = -1
    img_tiles: List[ImageTile] = None

    v_layout: QVBoxLayout

    def __init__(self, tile_infos: List[TileInfo] = None):
        super().__init__()
        # self.setText("Have some text here")
        self.v_layout = QVBoxLayout()
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
            tile.setFixedHeight(self.tile_size)
            tile.setFixedWidth(self.tile_size)
            self.img_tiles.append(tile)

    def layout_tiles(self):
        """
        Layout the tiles in the v_layout. This will remove all tiles from the layout and re-add them.

        This function will need to be overwritten if you have anything else in the layout

        :return:
        """
        n_h_tiles = (self.width() - 10) // (self.tile_size + 10)

        if n_h_tiles == self.last_n_h_tiles:
            return

        self.last_n_h_tiles = n_h_tiles
        height = math.ceil(len(self.img_tiles) / n_h_tiles) * (self.tile_size + 10) + 10
        self.setMinimumHeight(height)

        # empty layout
        while self.v_layout.count():
            self.v_layout.takeAt(0)

        self.v_layout.addStretch()

        # Loop through rows
        for i in range(0, len(self.img_tiles), n_h_tiles):
            # Create a new horizontal layout for row
            row = Row(self.img_tiles[i:i + n_h_tiles])

            # Add the row to the main layout.
            self.v_layout.addWidget(row)

            self.v_layout.addStretch()
        # for tile in self.img_tiles:
        #     self.v_layout.addWidget(QLabel("Test"))
        #     self.v_layout.addStretch()


class CheckableNamedPictureBlock(QLabel):
    import_checkbox: QCheckBox

    def __init__(self):
        super().__init__()
        self.import_checkbox = QCheckBox("Import Section")

        self.v_layout = QVBoxLayout()
        self.v_layout.addLayout(self.import_checkbox)

        self.setLayout(self.v_layout)

        self.import_checkbox.clicked.connect(self.update_colors)
        self.update_colors()

    def update_colors(self):
        if self.import_checkbox.isChecked():
            self.marked_for_import()
        else:
            self.marked_not_for_import()

    def set_imported(self):
        self.import_checkbox.setChecked(True)
        self.import_checkbox.setDisabled(True)
        self.setStyleSheet("background-color: rgb(200, 255, 200);")

    def marked_for_import(self):
        self.setStyleSheet("background-color: rgb(255, 255, 200);")

    def marked_not_for_import(self):
        self.setStyleSheet("background-color: rgb(255, 200, 200);")


class TempRoow(QMainWindow):
    def __init__(self):
        super().__init__()
        target = "/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images"
        images = os.listdir(target)
        sample_tiles = [TileInfo(key=1, path=os.path.join(target, image), table="TEST") for image in images]

        self.sca = QScrollArea()
        self.sca.setWidgetResizable(True)
        self.sca.setWidget(PictureBlock(tile_infos=sample_tiles))
        self.setCentralWidget(self.sca)

if __name__ == "__main__":

    app = QApplication(sys.argv)
    root = TempRoow()
    root.show()
    sys.exit(app.exec())