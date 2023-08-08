import sys
import os
from typing import Union
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QSizePolicy, QMainWindow, QFrame, QWidget
from PyQt6.QtCore import Qt
from photo_lib.gui.clickable_image import ClickableImage
from photo_lib.PhotoDatabase import TileInfo

class ImageTile(QFrame):

    tile_info: Union[TileInfo, None] = None

    file_name_lbl: QLabel
    clickable_image: ClickableImage
    b_layout: QVBoxLayout

    open_image_callback = None

    def __init__(self, info: TileInfo):
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

        self.clickable_image.clicked.connect(self.open_image)

    def open_image(self):
        """
        Calls the open_image_callback if it is not None. This should open a different view with one image centered and
        a lot of small windows at the bottom.

        :return:
        """
        if self.open_image_callback is not None:
            self.open_image_callback(self.tile_info)

    def heightForWidth(self, a0: int) -> int:
        """
        Override this function to make the image tile square.

        :param a0: default param, ignored.
        :return:
        """
        return self.width()



if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = ImageTile(TileInfo(1, '/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images/IMG_2159.JPG',
                                'None'))
    root = QMainWindow()
    root.setCentralWidget(widget)
    root.show()
    sys.exit(app.exec())