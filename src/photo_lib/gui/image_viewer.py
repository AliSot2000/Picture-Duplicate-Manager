from PyQt6.QtWidgets import QVBoxLayout, QCheckBox, QPushButton, QWidget, QApplication, QHBoxLayout, QFrame, QLabel, QScrollArea, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from photo_lib.PhotoDatabase import FullImportTableEntry, TileInfo, MatchTypes
from photo_lib.gui.metdata_widget import ImportMetadataWidget
from photo_lib.gui.model import Model
from photo_lib.gui.zoom_image import ZoomImage

from typing import Union
import sys
import json


class ImportImageView(QFrame):
    metadata_area: QScrollArea
    main_metadata_widget: ImportMetadataWidget = None
    match_metadata_widget: Union[None, ImportMetadataWidget] = None

    big_image: ZoomImage
    match_image: ZoomImage

    h_layout: QHBoxLayout

    metadata_dummy_widget: QWidget
    metadata_layout = QHBoxLayout

    model: Model = None
    __tile_info: TileInfo = None

    open_metadata_btn: QPushButton

    open_metadata_action: QAction

    load_match: bool = False
    show_metadata: bool = False

    global_splitter: QSplitter

    def __init__(self, model: Model):
        super().__init__()
        self.model = model

        self.h_layout = QHBoxLayout()
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(0)
        self.setLayout(self.h_layout)

        self.metadata_area = QScrollArea()
        self.metadata_area.setWidgetResizable(True)

        self.metadata_dummy_widget = QWidget()

        self.metadata_layout = QHBoxLayout()
        self.metadata_dummy_widget.setLayout(self.metadata_layout)

        self.main_metadata_widget = ImportMetadataWidget(model=model)
        self.main_metadata_widget = ImportMetadataWidget(model=model) # TODO needs to be different MetadataWidget

        self.big_image = ZoomImage()
        self.match_image = ZoomImage()

        self.global_splitter = QSplitter()

        self.build_layout()

    def build_layout(self):
        """
        Build up the layout of the widget
        :return:
        """
        if self.show_metadata:
            if self.load_match:
                pass
            else:
                pass
        else:
            if self.load_match:
                pass
            else:
                pass

    @property
    def tile_info(self):
        return self.__tile_info

    @tile_info.setter
    def tile_info(self, value: TileInfo):
        self.__tile_info = value
        if value is not None:
            self.metadata_area.setVisible(True)
            self.big_image.setVisible(True)

            self.main_metadata_widget.tile_info = value
            self.big_image.file_path = value.path

        else:
            self.metadata_area.setVisible(False)
            self.big_image.setVisible(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = ImportMetadataWidget(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.tile_info = TileInfo(
        key=20,
        path="",
        imported=False,
        allowed=False,
        match_type=MatchTypes.No_Match
    )



    window.show()
    sys.exit(app.exec())