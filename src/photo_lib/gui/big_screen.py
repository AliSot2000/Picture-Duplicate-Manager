from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QSplitter, QApplication
from PyQt6.QtCore import Qt
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



if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = BigScreen(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.model.build_tiles_from_table()
    window.build_all()

    window.setWindowTitle("Big Screen")

    window.show()
    sys.exit(app.exec())