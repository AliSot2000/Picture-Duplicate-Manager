from PyQt6.QtWidgets import QVBoxLayout, QCheckBox, QPushButton, QWidget, QApplication, QHBoxLayout, QFrame, QLabel, QScrollArea, QSplitter, QMainWindow
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from photo_lib.PhotoDatabase import FullImportTableEntry, TileInfo, MatchTypes
from photo_lib.gui.action_button import QActionButton
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

    open_metadata_btn: QActionButton

    open_metadata_action: QAction
    open_match_action: QAction

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

        self.open_metadata_action = QAction("Show Metadata")
        self.open_metadata_action.setToolTip("Show the metadata of the image (and match in database)")
        self.open_metadata_action.setCheckable(True)
        self.open_metadata_action.toggled.connect(self.update_show_metadata)

        self.open_match_action = QAction("Show Match")
        self.open_match_action.setToolTip("Show the match and its metadata if there exists one in the database.")
        self.open_match_action.setCheckable(True)
        self.open_metadata_action.toggled.connect(self.update_show_metadata)

        self.open_metadata_btn = QActionButton()
        self.open_metadata_btn.target_action = self.open_metadata_action

        self.build_main_layout()

    def build_main_layout(self):
        """
        Build up the layout of the widget
        :return:
        """
        # TODO update visibility

        # Empty splitter
        if self.global_splitter.layout() is not None:
            while self.global_splitter.layout().count() > 0:
                self.global_splitter.layout().takeAt(0)

        # Empty layout
        while self.h_layout.count() > 0:
            self.h_layout.takeAt(0)

        if self.show_metadata:
            if self.load_match:
                self.h_layout.addWidget(self.global_splitter)
                self.global_splitter.addWidget(self.match_image)
                self.global_splitter.addWidget(self.big_image)
                self.global_splitter.addWidget(self.metadata_area)
            else:
                self.h_layout.addWidget(self.global_splitter)
                self.global_splitter.addWidget(self.big_image)
                self.global_splitter.addWidget(self.metadata_area)
        else:
            if self.load_match:
                self.global_splitter.addWidget(self.match_image)
                self.global_splitter.addWidget(self.big_image)
                self.h_layout.addWidget(self.global_splitter)
                self.h_layout.addWidget(self.open_metadata_btn)
            else:
                self.h_layout.addWidget(self.big_image)
                self.h_layout.addWidget(self.open_metadata_btn)

        self.update_visibility()

    def update_visibility(self):
        """
        Update the visibility of the widgets.
        :return:
        """
        if self.show_metadata:
            self.open_metadata_btn.setVisible(False)
            if self.load_match:
                self.global_splitter.setVisible(True)
                self.metadata_area.setVisible(True)
                self.big_image.setVisible(True)
                self.match_image.setVisible(True)
            else:
                self.global_splitter.setVisible(True)
                self.metadata_area.setVisible(True)
                self.big_image.setVisible(True)
                self.match_image.setVisible(False)
        else:
            self.open_metadata_btn.setVisible(True)
            if self.load_match:
                self.global_splitter.setVisible(True)
                self.metadata_area.setVisible(False)
                self.big_image.setVisible(True)
                self.match_image.setVisible(True)
            else:
                self.global_splitter.setVisible(False)
                self.metadata_area.setVisible(False)
                self.big_image.setVisible(True)
                self.match_image.setVisible(False)

    def build_metadata_layout(self):
        """
        Fill the metadata layout according to self.load_match and update visibility.
        :return:
        """
        # TODO update visibility.

        # Empty layout
        while self.metadata_layout.count() > 0:
            self.metadata_layout.takeAt(0)

        # Add widgets again.
        if self.load_match:
            self.metadata_layout.addWidget(self.main_metadata_widget)
            self.metadata_layout.addWidget(self.match_metadata_widget)
            self.match_metadata_widget.setVisible(True)

        else:
            self.metadata_layout.addWidget(self.main_metadata_widget)
            self.match_metadata_widget.setVisible(False)

    def update_show_match(self):
        """
        Performs update action after the show_match action was toggled
        :return:
        """
        self.load_match = self.open_match_action.isChecked()
        if self.load_match:
            self.fetch_match()
        self.build_main_layout()
        self.build_metadata_layout()

    def fetch_match(self):
        """
        Fetch information associated with match
        :return:
        """
        pass
        # Get Metadata
        # Crate Metadata Widget
        # Load Image

    def update_show_metadata(self):
        """
        Performs update action after the show_metadata action was toggled
        :return:
        """
        self.show_metadata = self.open_metadata_action.isChecked()
        self.build_main_layout()
        self.build_metadata_layout()

    @property
    def tile_info(self):
        return self.__tile_info

    @tile_info.setter
    def tile_info(self, value: TileInfo):
        """
        Set the tile info that's currently displayed and update the widgets.
        :param value:
        :return:
        """
        self.__tile_info = value
        self.main_metadata_widget.tile_info = value
        if value is not None:
            self.big_image.file_path = value.path

            if self.load_match:
                self.fetch_match()

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/")
        self.model.current_import_table_name = "tbl_1998737548188488947"

        self.setWindowTitle("Import View")
        self.import_view = ImportImageView(model=self.model)
        self.setCentralWidget(self.import_view)

        self.import_view.tile_info = TileInfo(
            key=20,
            path="/media/alisot2000/DumpStuff/Test128/2022-09-01 02.35.18_000.jpg",
            imported=False,
            allowed=False,
            match_type=MatchTypes.No_Match
        )

        self.show()

        submenu = self.menuBar().addMenu("Image Actions")
        submenu.addAction(self.import_view.open_metadata_action)
        submenu.addAction(self.import_view.open_match_action)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = TestWindow()

    window.show()
    sys.exit(app.exec())