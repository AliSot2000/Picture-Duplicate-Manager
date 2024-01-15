import sys
import os
from typing import Union
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QSizePolicy, QMainWindow, QFrame, QWidget
from PyQt6.QtCore import Qt
from photo_lib.gui.clickable_image import ClickableImage
from photo_lib.PhotoDatabase import ImportTileInfo, MatchTypes, BaseTileInfo


class NamedTile(QFrame):
    """
    An always square image tile that can be clicked on to emit a signal. The tile also has a text label with the
    file name. The tile can also be colored to indicate if it is marked for import or not.
    """

    tile_info: Union[ImportTileInfo, None] = None

    file_name_lbl: QLabel
    clickable_image: ClickableImage
    b_layout: QVBoxLayout

    # open_image_callback = None

    def __init__(self, info: ImportTileInfo):
        super().__init__()
        self.tile_info = info

        self.setFrameStyle(QFrame.Shape.Box)

        self.file_nane_lbl = QLabel()
        self.b_layout = QVBoxLayout()
        self.clickable_image = ClickableImage(self.tile_info.path)

        self.file_nane_lbl.setText(os.path.basename(self.tile_info.path))
        self.file_nane_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clickable_image.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

        self.b_layout.addWidget(self.clickable_image)
        self.b_layout.addWidget(self.file_nane_lbl)
        # self.b_layout.setContentsMargins(0, 0, 0, 0)
        self.b_layout.setSpacing(5)
        self.setLayout(self.b_layout)

    def heightForWidth(self, a0: int) -> int:
        """
        Override this function to make the image tile square.

        :param a0: default param, ignored.
        :return:
        """
        return self.width()

    def set_imported(self):
        # Set color green
        self.setStyleSheet("background-color: rgb(200, 255, 200);")

    def marked_for_import(self):
        # Set color yellow
        self.setStyleSheet("background-color: rgb(255, 255, 200);")

    def marked_not_for_import(self):
        # Set color red
        self.setStyleSheet("background-color: rgb(255, 200, 200);")

    def reset_mark(self):
        self.setStyleSheet("")


# Class named patch because squareness not enforced
class ClickablePatch(ClickableImage):
    """
    Creates a clickable image which gets a tile_info dataclass to get the image instead of the file_path.
    """
    __tile_info: Union[BaseTileInfo, None] = None

    @property
    def tile_info(self):
        return self.__tile_info

    @tile_info.setter
    def tile_info(self, value: BaseTileInfo):
        self.__tile_info = value
        if self.__tile_info is not None:
            self.file_path = value.path
        else:
            self.file_path = None


class IndexedTile(ClickablePatch):
    """
    Has a index - to keep track of the index in the database (for display purposes).

    Also forces the aspect ratio to be square. -> Tile Name
    """
    index: int = -1

    def heightForWidth(self, a0: int) -> int:
        """
        Override this function to make the image tile square.

        :param a0: default param, ignored.
        :return:
        """
        return self.width()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = ImageTile(ImportTileInfo(1, '/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images/IMG_2159.JPG',
                                      False, False, MatchTypes.No_Match))
    root = QMainWindow()
    root.setCentralWidget(widget)
    root.show()
    sys.exit(app.exec())