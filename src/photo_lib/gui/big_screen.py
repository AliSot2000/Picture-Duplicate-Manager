from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QSplitter, QApplication, QMainWindow
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImageReader
from photo_lib.gui.model import Model
from photo_lib.gui.carousell import Carousel
from photo_lib.gui.image_viewer import ImportImageView
import sys



class BigScreen(QSplitter):
    model: Model = None

    carousel: Carousel = None
    image_viewer: ImportImageView = None

    def __init__(self, model: Model):
        super().__init__(Qt.Orientation.Vertical)
        self.model = model

        self.carousel = Carousel(model=model)
        self.carousel.build_carousel()
        self.image_viewer = ImportImageView(model=model)

        self.addWidget(self.image_viewer)
        self.addWidget(self.carousel)

        self.setStretchFactor(0, 1)
        self.setStretchFactor(1, 0)

        self.carousel.image_changed.connect(self.update_image_view)

    def update_image_view(self):
        """
        Doing it like this because None somehow didn't work correctly.
        :return:
        """
        self.image_viewer.tile_info = self.carousel.current_select.tile_info

    # TODO actions next and previous image
    def build_all(self):
        """
        Builds all the child widgets from the current model.
        :return:
        """
        self.carousel.build_carousel()


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        h = QImageReader.setAllocationLimit(0)
        self.model = Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/")
        # self.model.current_import_table_name = "tbl_1998737548188488947"
        self.model.current_import_table_name = "tbl_2836637745918598915"
        self.model.build_tiles_from_table()

        self.setWindowTitle("BigScreen")
        self.big_screen = BigScreen(model=self.model)
        self.setCentralWidget(self.big_screen)

        self.show()

        submenu = self.menuBar().addMenu("Image Actions")
        submenu.addAction(self.big_screen.image_viewer.open_metadata_action)
        submenu.addAction(self.big_screen.image_viewer.open_match_action)

        self.big_screen.build_all()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = TestWindow()

    window.setWindowTitle("Big Screen")

    window.show()
    sys.exit(app.exec())