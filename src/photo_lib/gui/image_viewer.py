from PyQt6.QtWidgets import QVBoxLayout, QCheckBox, QPushButton, QWidget, QApplication, QHBoxLayout, QFrame, QLabel, QScrollArea, QSplitter, QMainWindow
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

from photo_lib.PhotoDatabase import FullImportTableEntry, TileInfo, MatchTypes
from photo_lib.gui.action_button import QActionButton
from photo_lib.gui.metdata_widget import DualMetadataWidget
from photo_lib.gui.model import Model
from photo_lib.gui.zoom_image import ZoomImage

from typing import Union
import sys
import json


# TODO bugfix, empty metadata when match not loaded
# TODO formatting broken. Fix it.

class ImportImageView(QFrame):

    # For config:
    # TODO move to config
    metadata_in_scroll_area: bool = False

    metadata_widget: Union[DualMetadataWidget, None] = None

    big_image: ZoomImage
    match_image: ZoomImage

    h_layout: QHBoxLayout

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
        # self.h_layout.setContentsMargins(0, 0, 0, 0)
        # self.h_layout.setSpacing(0)
        self.setLayout(self.h_layout)

        self.metadata_widget = DualMetadataWidget(model=model)
        self.metadata_area = self.metadata_widget
        if self.metadata_in_scroll_area:
            self.metadata_area = QScrollArea()
            self.metadata_area.setMinimumWidth(400)
            self.metadata_area.setWidgetResizable(True)
            self.metadata_area.setWidget(self.metadata_widget)

        self.big_image = ZoomImage()
        self.big_image.setMinimumSize(100, 100)
        # self.big_image.setFrameStyle(QFrame.Shape.Box)
        self.match_image = ZoomImage()
        self.match_image.setMinimumSize(100, 100)
        # self.match_image.setFrameStyle(QFrame.Shape.Box)
        self.global_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.global_splitter.setHandleWidth(5)

        self.open_metadata_action = QAction("Show Metadata")
        self.open_metadata_action.setToolTip("Show the metadata of the image (and match in database)")
        self.open_metadata_action.setCheckable(True)
        self.open_metadata_action.toggled.connect(self.update_show_metadata)

        self.open_match_action = QAction("Show Match")
        self.open_match_action.setToolTip("Show the match and its metadata if there exists one in the database.")
        self.open_match_action.setCheckable(True)
        self.open_match_action.toggled.connect(self.update_show_match)

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
                self.global_splitter.setStretchFactor(0, 1)
                self.global_splitter.setStretchFactor(1, 1)
                self.global_splitter.setStretchFactor(2, 1)
            else:
                self.h_layout.addWidget(self.global_splitter)
                self.global_splitter.addWidget(self.big_image)
                self.global_splitter.addWidget(self.metadata_area)
                self.global_splitter.setStretchFactor(0, 1)
                self.global_splitter.setStretchFactor(1, 1)
        else:
            if self.load_match:
                self.global_splitter.addWidget(self.match_image)
                self.global_splitter.addWidget(self.big_image)
                self.global_splitter.setStretchFactor(0, 1)
                self.global_splitter.setStretchFactor(1, 1)
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

    def update_show_match(self):
        """
        Performs update action after the show_match action was toggled
        :return:
        """
        self.metadata_widget.show_match = self.load_match = self.open_match_action.isChecked()
        if self.load_match:
            self.fetch_match()
        self.build_main_layout()

    def fetch_match(self):
        """
        Fetch information associated with match
        :return:
        """
        any_match_key = self.model.get_any_match(self.tile_info)
        if any_match_key is not None:
            self.match_image.file_path = self.model.get_any_image_of_key(any_match_key)

    def update_show_metadata(self):
        """
        Performs update action after the show_metadata action was toggled
        :return:
        """
        self.show_metadata = self.open_metadata_action.isChecked()
        self.build_main_layout()

    @property
    def tile_info(self):
        """
        Return the tile_info that's being currently displayed.
        :return:
        """
        return self.__tile_info

    @tile_info.setter
    def tile_info(self, value: TileInfo):
        """
        Set the tile info that's currently displayed and update the widgets.
        :param value:
        :return:
        """
        self.__tile_info = value
        self.metadata_widget.tile_info = value
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