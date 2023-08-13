from PyQt6.QtWidgets import QVBoxLayout, QCheckBox, QPushButton, QWidget, QApplication, QHBoxLayout, QFrame, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from photo_lib.PhotoDatabase import FullImportTableEntry, TileInfo, MatchTypes
from photo_lib.gui.text_scroll_area import TextScroller
from photo_lib.gui.model import Model

from typing import Union
import sys
import json


class ImportMetadataWidget(QFrame):
    """
    Widget to display the metadata of a single image.
    """
    # TODO config
    single_line_size: int = 20

    file_changed = pyqtSignal()
    model: Model

    _entry: Union[None, FullImportTableEntry] = None
    __tile_info: Union[None, TileInfo] = None

    v_layout: QVBoxLayout

    file_name_lbl: QLabel
    file_name_val: TextScroller

    file_path_lbl: QLabel
    file_path_val: TextScroller

    file_hash_lbl: QLabel
    file_hash_val: QLabel

    datetime_lbl: QLabel
    datetime_val: QLabel

    naming_tag_lbl: QLabel
    naming_tag_val: QLabel

    import_lbl: QLabel
    import_checkbox: QCheckBox
    allowed_label: QLabel
    match_type_label: QLabel

    info_hbox: QHBoxLayout

    metadata_lbl: QLabel
    metadata_val: TextScroller

    google_fotos_metadata_lbl: QLabel
    google_fotos_metadata_val: TextScroller

    def __init__(self, model: Model):
        super().__init__()
        self.model = model

        self.v_layout = QVBoxLayout()
        self.setLayout(self.v_layout)

        self.file_name_lbl = QLabel()
        self.file_name_lbl.setFixedHeight(self.single_line_size)
        self.file_name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.file_name_val = TextScroller()
        self.file_name_val.setFixedHeight(self.single_line_size)
        self.file_name_val.setWidgetResizable(True)
        self.file_name_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_name_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_name_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_name_val.setFrameStyle(QFrame.Shape.NoFrame)

        self.file_path_lbl = QLabel()
        self.file_path_lbl.setFixedHeight(self.single_line_size)
        self.file_path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.file_path_val = TextScroller()
        self.file_path_val.setFixedHeight(self.single_line_size)
        self.file_path_val.setWidgetResizable(True)
        self.file_path_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_path_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_path_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_path_val.setFrameStyle(QFrame.Shape.NoFrame)

        self.file_hash_lbl = QLabel()
        self.file_hash_lbl.setFixedHeight(self.single_line_size)
        self.file_hash_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.file_hash_val = QLabel()
        self.file_hash_val.setFixedHeight(self.single_line_size)
        self.file_hash_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.datetime_lbl = QLabel()
        self.datetime_lbl.setFixedHeight(self.single_line_size)
        self.datetime_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.datetime_val = QLabel()
        self.datetime_val.setFixedHeight(self.single_line_size)
        self.datetime_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.naming_tag_lbl = QLabel()
        self.naming_tag_lbl.setFixedHeight(self.single_line_size)
        self.naming_tag_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.naming_tag_val = QLabel()
        self.naming_tag_val.setFixedHeight(self.single_line_size)
        self.naming_tag_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.import_lbl = QLabel()
        self.import_lbl.setFixedHeight(self.single_line_size)
        self.import_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.import_checkbox = QCheckBox()

        self.allowed_label = QLabel()
        self.allowed_label.setFixedHeight(self.single_line_size)
        self.allowed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.match_type_label = QLabel()
        self.match_type_label.setFixedHeight(self.single_line_size)
        self.match_type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.dummy_widget = QWidget()
        self.info_hbox = QHBoxLayout()
        self.info_hbox.setContentsMargins(0, 0, 0, 0)
        self.dummy_widget.setLayout(self.info_hbox)

        self.metadata_lbl = QLabel()
        self.metadata_lbl.setFixedHeight(self.single_line_size)
        self.metadata_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.metadata_val = TextScroller()
        self.metadata_val.setWidgetResizable(True)
        self.metadata_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.google_fotos_metadata_lbl = QLabel()
        self.google_fotos_metadata_lbl.setFixedHeight(self.single_line_size)
        self.google_fotos_metadata_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.google_fotos_metadata_val = TextScroller()
        self.google_fotos_metadata_val.setWidgetResizable(True)
        self.google_fotos_metadata_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.init_names()

    def init_names(self):
        """
        Set the Values of the Labels which declare what the values are.
        :return:
        """
        self.file_name_lbl.setText("Original File Name:")
        self.file_path_lbl.setText("Original File Path:")
        self.file_hash_lbl.setText("File Hash:")
        self.datetime_lbl.setText("Date, Time of File:")
        self.naming_tag_lbl.setText("Naming Tag:")
        self.metadata_lbl.setText("Metadata:")
        self.google_fotos_metadata_lbl.setText("Google Fotos Metadata:")

    @property
    def tile_info(self):
        return self.__tile_info

    @tile_info.setter
    def tile_info(self, value: TileInfo):
        self.__tile_info = value
        self._entry = self.model.get_file_import_full_entry(value.key)
        self.build_metadata_widget()
        self.file_changed.emit()

    def build_metadata_widget(self):
        """
        Build the metadata widget from the current tile_info from the model.

        :return:
        """
        # Empty layout
        while self.v_layout.count() > 0:
            self.v_layout.takeAt(0)

        while self.info_hbox.count() > 0:
            self.info_hbox.takeAt(0)

        # btn = QPushButton("Import")
        # btn.clicked.connect(self.helper)
        # self.v_layout.addWidget(btn)

        # Set values
        self.file_name_val.text_label.setText(self._entry.org_fname)
        self.file_path_val.text_label.setText(self._entry.org_fpath)

        self.v_layout.addWidget(self.file_name_lbl)
        self.v_layout.addWidget(self.file_name_val)
        self.v_layout.addWidget(self.file_path_lbl)
        self.v_layout.addWidget(self.file_path_val)

        # build not allowed
        if not self._entry.allowed:
            self.v_layout.addWidget(self.dummy_widget)

            self.allowed_label.setText("Not Allowed")
            self.info_hbox.addWidget(self.allowed_label)

            # Might be we imported it at some point but now updated the allowed files.
            if self._entry.imported:
                self.import_lbl.setText("Imported")
                self.info_hbox.addWidget(self.import_lbl)

            if self._entry.match_type is not None:
                self.match_type_label.setText(self._entry.match_type.name.replace('_', ' ').title())
                self.info_hbox.addWidget(self.match_type_label)

            return

        # file is allowed
        self.file_hash_val.setText(self._entry.file_hash)
        self.datetime_val.setText(self._entry.datetime.strftime("%Y-%m-%d %H:%M:%S"))
        self.naming_tag_val.setText(self._entry.naming_tag)

        self.v_layout.addWidget(self.file_hash_lbl)
        self.v_layout.addWidget(self.file_hash_val)

        self.v_layout.addWidget(self.datetime_lbl)
        self.v_layout.addWidget(self.datetime_val)

        self.v_layout.addWidget(self.naming_tag_lbl)
        self.v_layout.addWidget(self.naming_tag_val)

        # Box about import, allowed and match type
        self.v_layout.addWidget(self.dummy_widget)
        self.allowed_label.setText("Allowed")
        self.info_hbox.addWidget(self.allowed_label)

        if self._entry.imported:
            self.import_lbl.setText("Imported")
            self.info_hbox.addWidget(self.import_lbl)
        else:
            self.import_checkbox.setText("Import File")
            self.import_checkbox.setCheckState(Qt.CheckState.Unchecked)
            self.info_hbox.addWidget(self.import_checkbox)

        # Should not be None technically
        if self._entry.match_type is not None:
            self.match_type_label.setText(self._entry.match_type.name.replace('_', ' ').title())
            self.info_hbox.addWidget(self.match_type_label)

        # Add the Metadata
        if self._entry.metadata is not None:
            self.metadata_val.text_label.setText(self.model.process_metadata(self._entry.metadata)[0])
            self.v_layout.addWidget(self.metadata_lbl)
            self.v_layout.addWidget(self.metadata_val)

        # Add the Google Fotos Metadata
        if self._entry.google_fotos_metadata is not None:
            self.google_fotos_metadata_val.text_label.setText(json.dumps(self._entry.google_fotos_metadata, indent=4))
            self.v_layout.addWidget(self.google_fotos_metadata_lbl)
            self.v_layout.addWidget(self.google_fotos_metadata_val)

    def helper(self):
        print(self._entry)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = ImportMetadataWidget(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.tile_info = TileInfo(
        key=1,
        path="",
        imported=False,
        allowed=False,
        match_type=MatchTypes.No_Match
    )



    window.show()
    sys.exit(app.exec())