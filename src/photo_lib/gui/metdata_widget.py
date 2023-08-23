import time
import warnings
import threading as th
from PyQt6.QtWidgets import QVBoxLayout, QCheckBox, QPushButton, QWidget, QApplication, QHBoxLayout, QFrame, QLabel, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal

from photo_lib.PhotoDatabase import FullImportTableEntry, TileInfo, MatchTypes, FullReplacedEntry, FullDatabaseEntry
from photo_lib.custom_enum import GoogleFotosMetadataStatus
from photo_lib.gui.text_scroll_area import TextScroller
from photo_lib.gui.model import Model
from photo_lib.gui.gui_utils import bake_attribute

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
        self.dummy_widget.setFixedHeight(self.single_line_size)
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
        if value is not None:
            self._entry = self.model.get_file_import_full_entry(value.key)
        self.build_metadata_widget()
        self.file_changed.emit()

    def hide_widgets(self):
        self.file_name_lbl.setVisible(False)
        self.file_name_val.setVisible(False)

        self.file_path_lbl.setVisible(False)
        self.file_path_val.setVisible(False)

        self.file_hash_lbl.setVisible(False)
        self.file_hash_val.setVisible(False)

        self.datetime_lbl.setVisible(False)
        self.datetime_val.setVisible(False)

        self.naming_tag_lbl.setVisible(False)
        self.naming_tag_val.setVisible(False)

        self.import_lbl.setVisible(False)
        self.import_checkbox.setVisible(False)
        self.allowed_label.setVisible(False)
        self.match_type_label.setVisible(False)

        self.metadata_lbl.setVisible(False)
        self.metadata_val.setVisible(False)

        self.google_fotos_metadata_lbl.setVisible(False)
        self.google_fotos_metadata_val.setVisible(False)

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

        self.hide_widgets()
        # btn = QPushButton("Import")
        # btn.clicked.connect(self.helper)
        # self.v_layout.addWidget(btn)

        # Handle in case when we don't have a tile_info
        if self.tile_info is None:
            lbl = QLabel("No File Selected")
            lbl.setFixedHeight(self.single_line_size)
            self.v_layout.addWidget(lbl)
            return

        # Set values
        self.file_name_val.text_label.setText(self._entry.org_fname)
        self.file_path_val.text_label.setText(self._entry.org_fpath)

        self.file_name_lbl.setVisible(True)
        self.file_name_val.setVisible(True)
        self.file_path_lbl.setVisible(True)
        self.file_path_val.setVisible(True)
        self.v_layout.addWidget(self.file_name_lbl)
        self.v_layout.addWidget(self.file_name_val)
        self.v_layout.addWidget(self.file_path_lbl)
        self.v_layout.addWidget(self.file_path_val)

        # build not allowed
        if not self._entry.allowed:
            self.v_layout.addWidget(self.dummy_widget)

            self.allowed_label.setText("Not Allowed")
            self.allowed_label.setVisible(True)
            self.info_hbox.addWidget(self.allowed_label)

            # Might be we imported it at some point but now updated the allowed files.
            if self._entry.imported:
                self.import_lbl.setText("Imported")
                self.import_lbl.setVisible(True)
                self.info_hbox.addWidget(self.import_lbl)

            if self._entry.match_type is not None:
                self.match_type_label.setText(self._entry.match_type.name.replace('_', ' ').title())
                self.match_type_label.setVisible(True)
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

        self.file_hash_lbl.setVisible(True)
        self.file_hash_val.setVisible(True)
        self.datetime_lbl.setVisible(True)
        self.datetime_val.setVisible(True)
        self.naming_tag_lbl.setVisible(True)
        self.naming_tag_val.setVisible(True)

        # Box about import, allowed and match type
        self.v_layout.addWidget(self.dummy_widget)

        self.allowed_label.setText("Allowed")
        self.allowed_label.setVisible(True)
        self.info_hbox.addWidget(self.allowed_label)

        if self._entry.imported:
            self.import_lbl.setText("Imported")
            self.import_lbl.setVisible(True)
            self.info_hbox.addWidget(self.import_lbl)
        else:
            self.import_checkbox.setVisible(True)
            self.import_checkbox.setCheckState(Qt.CheckState.Unchecked)
            self.info_hbox.addWidget(self.import_checkbox)

        # Should not be None technically
        if self._entry.match_type is not None:
            self.match_type_label.setText(self._entry.match_type.name.replace('_', ' ').title())
            self.match_type_label.setVisible(True)
            self.info_hbox.addWidget(self.match_type_label)

        # Add the Metadata
        if self._entry.metadata is not None:
            self.metadata_val.text_label.setText(self.model.process_metadata(self._entry.metadata)[0])
            self.metadata_val.setVisible(True)
            self.v_layout.addWidget(self.metadata_lbl)
            self.v_layout.addWidget(self.metadata_val)

        # Add the Google Fotos Metadata
        if self._entry.google_fotos_metadata is not None:
            self.google_fotos_metadata_val.text_label.setText(json.dumps(self._entry.google_fotos_metadata, indent=4))
            self.google_fotos_metadata_val.setVisible(True)
            self.v_layout.addWidget(self.google_fotos_metadata_lbl)
            self.v_layout.addWidget(self.google_fotos_metadata_val)

    def helper(self):
        print(self._entry)


class DualMetadataWidget(QFrame):
    single_line_size: int = 20

    import_file_changed = pyqtSignal()
    show_file_changed  = pyqtSignal()

    _import_entry: Union[None, FullImportTableEntry] = None
    _match_entry: Union[None, FullReplacedEntry, FullDatabaseEntry] = None
    __tile_info: Union[None, TileInfo] = None

    __show_match: bool = False

    model: Model

    g_layout = QGridLayout()

    # Row headers:
    file_name_lbl: QLabel
    file_path_lbl: QLabel
    file_hash_lbl: QLabel
    datetime_lbl: QLabel
    naming_tag_lbl: QLabel
    options: QLabel
    metadata_lbl: QLabel
    google_fotos_metadata_lbl: QLabel
    new_file_lbl: QLabel
    successor_lbl: QLabel

    no_file_label: QLabel

    # Row values
    i_file_name_val: TextScroller
    i_file_path_val: TextScroller
    i_file_hash_val: TextScroller
    i_file_datetime_val: QLabel
    i_file_naming_tag_val: QLabel
    i_file_import_label: QLabel
    i_file_import_checkbox: QCheckBox
    i_file_allowed_label: QLabel
    i_file_match_type_label: QLabel
    i_file_metadata_val: TextScroller
    i_file_google_fotos_metadata_val: TextScroller

    m_file_org_name_val: TextScroller
    m_file_org_path_val: TextScroller
    m_file_hash_val: TextScroller
    m_file_datetime_val: QLabel
    m_file_naming_tag_val: QLabel
    m_file_present_val: QLabel
    m_file_trashed_val: QLabel
    m_file_verify_val: QLabel
    m_file_new_name_val: QLabel
    m_file_original_google_metadata_val: QLabel
    m_file_successor_val: QLabel
    m_file_metadata_val: TextScroller
    m_file_google_fotos_metadata_val: TextScroller

    # Column Headers
    import_file_lbl: QLabel
    match_file_lbl: QLabel

    @property
    def show_match(self):
        return self.__show_match

    @show_match.setter
    def show_match(self, value: bool):
        self.__show_match = value

        if self._import_entry is not None:
            if self._import_entry.match is not None:
                new_match = self.model.get_full_database_entry(key=self._import_entry.match)
            else:
                new_match = None
            self._match_entry = new_match

        self.build_metadata_widget()
        self.show_file_changed.emit()

    @property
    def tile_info(self):
        return self.__tile_info

    @tile_info.setter
    def tile_info(self, value: TileInfo):
        build = (value is not None and self.__tile_info is None) or (value is None and self.__tile_info is not None)
        self.__tile_info = value

        if value is not None:
            self._import_entry = self.model.get_file_import_full_entry(value.key)

        if self.show_match:
            if self._import_entry.match is not None:
                new_match = self.model.get_full_database_entry(key=self._import_entry.match)
            else:
                new_match = None
            build = build or type(new_match) is not type(self._match_entry)
            self._match_entry = new_match

        if build:
            self.build_metadata_widget()
        else:
            self._assign_import_file_texts()
            if self._match_entry is not None:
                self._assign_match_file_texts()

        self._assign_import_file_texts()
        self.import_file_changed.emit()

    def synchronized_scroll(self, name: str, caller: TextScroller, rx: float, ry: float):
        """
        Go to the respective match and import widget and set the scroll to the given ratio.

        The TextScrollers that are going to be affected are indicated by the name argument which specifies the
        attribute name of the TextScroller.

        The caller is needed to prevent a recursive self call with no termination.

        :param name: The name of the attribute to synchronize.
        :param caller: The TextScroller that called this function.
        :param rx: The relative x scroll value.
        :param ry: The relative y scroll value.
        """
        assert name in ("org_name", "org_path", "file_hash", "metadata", "google_fotos_metadata"), \
            f"Invalid share scroll target {name}"

        if name == "org_name":
            if caller is not self.i_file_name_val:
                self.i_file_name_val.scroll_from_ratio(rx, ry)
            if caller is not self.m_file_org_name_val:
                self.m_file_org_name_val.scroll_from_ratio(rx, ry)

        elif name == "org_path":
            if caller is not self.i_file_path_val.scroll_from_ratio(rx, ry):
                self.i_file_path_val.scroll_from_ratio(rx, ry)
            if caller is not self.m_file_org_path_val:
                self.m_file_org_path_val.scroll_from_ratio(rx, ry)

        elif name == "file_hash":
            if caller is not self.i_file_hash_val:
                self.i_file_hash_val.scroll_from_ratio(rx, ry)
            if caller is not self.m_file_hash_val:
                self.m_file_hash_val.scroll_from_ratio(rx, ry)

        elif name == "metadata":
            if caller is not self.i_file_metadata_val:
                self.i_file_metadata_val.scroll_from_ratio(rx, ry)
            if caller is not self.m_file_metadata_val:
                self.m_file_metadata_val.scroll_from_ratio(rx, ry)

        # Google fotos metadata
        else:
            if caller is not self.i_file_google_fotos_metadata_val:
                self.i_file_google_fotos_metadata_val.scroll_from_ratio(rx, ry)
            if caller is not self.m_file_google_fotos_metadata_val:
                self.m_file_google_fotos_metadata_val.scroll_from_ratio(rx, ry)

    def set_import_flag(self):
        """
        Propagate the checked state of the flag to the tile info.
        :return:
        """
        if self.tile_info is None:
            return
        self.tile_info.mark_for_import =  self.i_file_import_checkbox.isChecked()


    def __init__(self, model: Model):
        """
        Widget to display the metadata of a single image.
        Create all Subwidgets.

        :param model: Model Object.
        """
        super().__init__()
        self.model = model

        self.g_layout = QGridLayout()
        self.setLayout(self.g_layout)

        # Create headers
        self.file_name_lbl = QLabel()
        self.file_path_lbl = QLabel()
        self.file_hash_lbl = QLabel()
        self.datetime_lbl = QLabel()
        self.naming_tag_lbl = QLabel()
        self.options = QLabel()
        self.metadata_lbl = QLabel()
        self.google_fotos_metadata_lbl = QLabel()
        self.new_file_lbl = QLabel()
        self.successor_lbl = QLabel()

        self.no_file_label = QLabel()

        self.i_file_name_val = TextScroller()
        self.i_file_path_val = TextScroller()
        self.i_file_hash_val = TextScroller()
        self.i_file_datetime_val = QLabel()
        self.i_file_naming_tag_val = QLabel()
        self.i_file_import_label = QLabel()
        self.i_file_import_checkbox = QCheckBox()
        self.i_file_allowed_label = QLabel()
        self.i_file_match_type_label = QLabel()
        self.i_file_metadata_val = TextScroller()
        self.i_file_google_fotos_metadata_val = TextScroller()

        self.m_file_org_name_val = TextScroller()
        self.m_file_org_path_val = TextScroller()
        self.m_file_hash_val = TextScroller()
        self.m_file_datetime_val = QLabel()
        self.m_file_naming_tag_val = QLabel()
        self.m_file_present_val = QLabel()
        self.m_file_trashed_val = QLabel()
        self.m_file_verify_val = QLabel()
        self.m_file_successor_val = QLabel()
        self.m_file_metadata_val = TextScroller()
        self.m_file_new_name_val = QLabel()
        self.m_file_original_google_metadata_val = QLabel()
        self.m_file_google_fotos_metadata_val = TextScroller()

        self.import_file_lbl = QLabel()
        self.match_file_lbl = QLabel()

        self.i_file_import_checkbox.toggled.connect(self.set_import_flag)

        self._init_names()
        self._init_formatting()

    def _init_names(self):
        """
        Define the texts of all labels of which the value is known ahead of time.
        :return:
        """
        self.file_name_lbl.setText("Original File Name:")
        self.file_path_lbl.setText("Original File Path:")
        self.file_hash_lbl.setText("File Hash:")
        self.datetime_lbl.setText("Date, Time of File:")
        self.naming_tag_lbl.setText("Naming Tag:")
        self.metadata_lbl.setText("Metadata:")
        self.google_fotos_metadata_lbl.setText("Google Fotos Metadata:")
        self.options.setText("Options:")
        self.new_file_lbl.setText("New File Name:")
        self.successor_lbl.setText("Successor ID:")
        self.import_file_lbl.setText("Import File:")
        self.match_file_lbl.setText("Match:")

        self.i_file_import_checkbox.setText("Import File")
        self.no_file_label.setText("No File Selected")

    def _init_formatting(self):
        """
        Set the formatting of every widget.
        :return:
        """
        # Set the formatting of the Row Headers
        self.file_name_lbl.setFixedHeight(self.single_line_size)
        self.file_name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.file_path_lbl.setFixedHeight(self.single_line_size)
        self.file_path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.file_hash_lbl.setFixedHeight(self.single_line_size)
        self.file_hash_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.datetime_lbl.setFixedHeight(self.single_line_size)
        self.datetime_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.naming_tag_lbl.setFixedHeight(self.single_line_size)
        self.naming_tag_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.options.setFixedHeight(self.single_line_size)
        self.options.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.metadata_lbl.setFixedHeight(self.single_line_size)
        self.metadata_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.google_fotos_metadata_lbl.setFixedHeight(self.single_line_size)
        self.google_fotos_metadata_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.new_file_lbl.setFixedHeight(self.single_line_size)
        self.new_file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.successor_lbl.setFixedHeight(self.single_line_size)
        self.successor_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.no_file_label.setFixedHeight(self.single_line_size)
        self.no_file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Set the formatting of the Import Row Values
        self.i_file_name_val.setFixedHeight(self.single_line_size)
        self.i_file_name_val.setWidgetResizable(True)
        self.i_file_name_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.i_file_name_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.i_file_name_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.i_file_name_val.setFrameStyle(QFrame.Shape.NoFrame)
        self.i_file_name_val.share_scroll = bake_attribute(name="org_name", func=self.synchronized_scroll)

        self.i_file_path_val.setFixedHeight(self.single_line_size)
        self.i_file_path_val.setWidgetResizable(True)
        self.i_file_path_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.i_file_path_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.i_file_path_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.i_file_path_val.setFrameStyle(QFrame.Shape.NoFrame)
        self.i_file_name_val.share_scroll = bake_attribute(name="org_path", func=self.synchronized_scroll)

        self.i_file_hash_val.setFixedHeight(self.single_line_size)
        self.i_file_hash_val.setWidgetResizable(True)
        self.i_file_hash_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.i_file_hash_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.i_file_hash_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.i_file_hash_val.setFrameStyle(QFrame.Shape.NoFrame)
        self.i_file_hash_val.share_scroll = bake_attribute(name="file_hash", func=self.synchronized_scroll)

        self.i_file_datetime_val.setFixedHeight(self.single_line_size)
        self.i_file_datetime_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.i_file_naming_tag_val.setFixedHeight(self.single_line_size)
        self.i_file_naming_tag_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.i_file_import_label.setFixedHeight(self.single_line_size)
        self.i_file_import_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.i_file_allowed_label.setFixedHeight(self.single_line_size)
        self.i_file_allowed_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.i_file_match_type_label.setFixedHeight(self.single_line_size)
        self.i_file_match_type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.i_file_metadata_val.setWidgetResizable(True)
        self.i_file_metadata_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.i_file_metadata_val.share_scroll = bake_attribute(name="metadata", func=self.synchronized_scroll)

        self.i_file_google_fotos_metadata_val.setWidgetResizable(True)
        self.i_file_google_fotos_metadata_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.i_file_google_fotos_metadata_val.share_scroll = bake_attribute(name="google_fotos_metadata", func=self.synchronized_scroll)

        # Set the formatting of the Match Row Values
        self.m_file_org_name_val.setFixedHeight(self.single_line_size)
        self.m_file_org_name_val.setWidgetResizable(True)
        self.m_file_org_name_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.m_file_org_name_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.m_file_org_name_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.m_file_org_name_val.setFrameStyle(QFrame.Shape.NoFrame)
        self.m_file_org_name_val.share_scroll = bake_attribute(name="org_name", func=self.synchronized_scroll)

        self.m_file_org_path_val.setFixedHeight(self.single_line_size)
        self.m_file_org_path_val.setWidgetResizable(True)
        self.m_file_org_path_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.m_file_org_path_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.m_file_org_path_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.m_file_org_path_val.setFrameStyle(QFrame.Shape.NoFrame)
        self.m_file_org_path_val.share_scroll = bake_attribute(name="org_path", func=self.synchronized_scroll)

        self.m_file_hash_val.setFixedHeight(self.single_line_size)
        self.m_file_hash_val.setWidgetResizable(True)
        self.m_file_hash_val.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.m_file_hash_val.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.m_file_hash_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.m_file_hash_val.setFrameStyle(QFrame.Shape.NoFrame)
        self.m_file_hash_val.share_scroll = bake_attribute(name="file_hash", func=self.synchronized_scroll)

        self.m_file_datetime_val.setFixedHeight(self.single_line_size)
        self.m_file_datetime_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_naming_tag_val.setFixedHeight(self.single_line_size)
        self.m_file_naming_tag_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_present_val.setFixedHeight(self.single_line_size)
        self.m_file_present_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_trashed_val.setFixedHeight(self.single_line_size)
        self.m_file_trashed_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_verify_val.setFixedHeight(self.single_line_size)
        self.m_file_verify_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_successor_val.setFixedHeight(self.single_line_size)
        self.m_file_successor_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_metadata_val.setWidgetResizable(True)
        self.m_file_metadata_val.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.m_file_metadata_val.share_scroll = bake_attribute(name="metadata", func=self.synchronized_scroll)

        self.m_file_new_name_val.setFixedHeight(self.single_line_size)
        self.m_file_new_name_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_original_google_metadata_val.setFixedHeight(self.single_line_size)
        self.m_file_original_google_metadata_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.m_file_google_fotos_metadata_val.setWidgetResizable(True)
        self.m_file_google_fotos_metadata_val.text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.m_file_google_fotos_metadata_val.share_scroll = bake_attribute(name="google_fotos_metadata", func=self.synchronized_scroll)

        # Set the formatting of the Column Headers
        self.import_file_lbl.setFixedHeight(self.single_line_size)
        self.import_file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.match_file_lbl.setFixedHeight(self.single_line_size)
        self.match_file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def hide_all(self):
        """
        Hide all Widgets

        :return:
        """
        # Create headers
        self.file_name_lbl.setVisible(False)
        self.file_path_lbl.setVisible(False)
        self.file_hash_lbl.setVisible(False)
        self.datetime_lbl.setVisible(False)
        self.naming_tag_lbl.setVisible(False)
        self.options.setVisible(False)
        self.metadata_lbl.setVisible(False)
        self.google_fotos_metadata_lbl.setVisible(False)
        self.new_file_lbl.setVisible(False)
        self.successor_lbl.setVisible(False)

        self.no_file_label.setVisible(False)

        self.i_file_name_val.setVisible(False)
        self.i_file_path_val.setVisible(False)
        self.i_file_hash_val.setVisible(False)
        self.i_file_datetime_val.setVisible(False)
        self.i_file_naming_tag_val.setVisible(False)
        self.i_file_import_label.setVisible(False)
        self.i_file_import_checkbox.setVisible(False)
        self.i_file_allowed_label.setVisible(False)
        self.i_file_match_type_label.setVisible(False)
        self.i_file_metadata_val.setVisible(False)
        self.i_file_google_fotos_metadata_val.setVisible(False)

        self.m_file_org_name_val.setVisible(False)
        self.m_file_org_path_val.setVisible(False)
        self.m_file_hash_val.setVisible(False)
        self.m_file_datetime_val.setVisible(False)
        self.m_file_naming_tag_val.setVisible(False)
        self.m_file_present_val.setVisible(False)
        self.m_file_trashed_val.setVisible(False)
        self.m_file_verify_val.setVisible(False)
        self.m_file_metadata_val.setVisible(False)
        self.m_file_original_google_metadata_val.setVisible(False)
        self.m_file_google_fotos_metadata_val.setVisible(False)

        self.import_file_lbl.setVisible(False)
        self.match_file_lbl.setVisible(False)

    def build_metadata_widget(self):
        """
        Build the metadata widget from the current tile_info from the model. Fill the layout.
        :return:
        """
        # TODO update visibility of widgets
        # TODO update stretch of rows and cols.

        self.hide_all()

        # Empty entire layout
        while self.g_layout.layout().count() > 0:
            self.g_layout.takeAt(0)

        # Case, when we got no tile_info
        if self.tile_info is None:
            self.g_layout.addWidget(self.no_file_label, 0, 0)
            self.no_file_label.setVisible(True)
            return

        self._build_row_column_header()
        self._set_row_column_header_visibility()

        # Tile info but no match
        if not self.show_match or self._match_entry is None:
            self._build_layout_import_only()
            self._set_visibility_import()
            self._set_stretch_import_only()
        else:
            self._build_match_layout()
            self._set_match_visible()

            self._build_import_layout_match()
            self._set_visibility_import()

            self._set_stretch_match_layout()


    # ------------------------------------------------------------------------------------------------------------------
    # Building Match Only
    # ------------------------------------------------------------------------------------------------------------------

    def _set_stretch_import_only(self):
        """
        Set the stretch of all widgets if only the import metadata is visible

        Precondition: self._import_entry is not None

        :return:
        """
        self.g_layout.setColumnStretch(0, 0)
        self.g_layout.setColumnStretch(1, 1)
        self.g_layout.setColumnStretch(2, 1)
        self.g_layout.setColumnStretch(3, 1)

        self.g_layout.setRowStretch(0, 0)
        self.g_layout.setRowStretch(1, 0)
        self.g_layout.setRowStretch(2, 0)

        # File not allowed
        if not self._import_entry.allowed:
            self.g_layout.setRowStretch(3, 0)
            self.options.setVisible(True)
            return

        self.g_layout.setRowStretch(3, 0)
        self.g_layout.setRowStretch(4, 0)
        self.g_layout.setRowStretch(5, 0)
        self.g_layout.setRowStretch(6, 0)

        # Add the Metadata
        if self._import_entry.metadata is not None:
            self.g_layout.setRowStretch(7, 0)
            if self._import_entry.google_fotos_metadata is not None:
                self.g_layout.setRowStretch(8, 0)

        else:
            if self._import_entry.google_fotos_metadata is not None:
                self.g_layout.setRowStretch(7, 0)

    def _build_layout_import_only(self):
        """
        Build the layout if only the import file is shown.

        Precondition, that self._import_entry is not None.
        :return:
        """
        self._assign_import_file_texts()

        # Set Column Header
        self.g_layout.addWidget(self.import_file_lbl, 0, 1, 1, 3)

        # Add the labels so far to the layout
        self.g_layout.addWidget(self.i_file_name_val, 1, 1, 1, 3)
        self.g_layout.addWidget(self.i_file_path_val, 2, 1, 1, 3)

        # File not allowed
        if not self._import_entry.allowed:
            self.g_layout.addWidget(self.i_file_allowed_label, 3, 1)
            self.g_layout.addWidget(self.i_file_import_label, 3, 2)
            self.g_layout.addWidget(self.i_file_match_type_label, 3, 3)
            return

        # Set more Values that should be set if allowed
        self.g_layout.addWidget(self.i_file_hash_val, 3, 1, 1, 3)
        self.g_layout.addWidget(self.i_file_datetime_val, 4, 1, 1, 3)
        self.g_layout.addWidget(self.i_file_naming_tag_val, 5, 1, 1, 3)

        # Build options
        self.g_layout.addWidget(self.options, 6, 0)

        # File allowed
        self.g_layout.addWidget(self.i_file_allowed_label, 6, 1)

        # Import checkbox
        if self._import_entry.imported:
            self.g_layout.addWidget(self.i_file_import_label, 6, 2)
        else:
            self.i_file_import_checkbox.setCheckState(Qt.CheckState.Unchecked)
            self.g_layout.addWidget(self.i_file_import_checkbox, 6, 2)

        self.g_layout.addWidget(self.i_file_match_type_label, 6, 3)

        # Add the Metadata
        if self._import_entry.metadata is not None:
            self.g_layout.addWidget(self.i_file_metadata_val, 7, 1, 1, 3)

        if self._import_entry.google_fotos_metadata is not None:
            self.g_layout.addWidget(self.i_file_google_fotos_metadata_val, 8, 1, 1, 3)

    # ------------------------------------------------------------------------------------------------------------------
    # General functions concerning the import widgets
    # ------------------------------------------------------------------------------------------------------------------

    def _set_visibility_import(self):
        """
        Set the visibility of all import file widgets

        Precondition: self._import_entry is not None

        :return:
        """
        self.i_file_name_val.setVisible(True)
        self.i_file_path_val.setVisible(True)

        self.i_file_match_type_label.setVisible(True)
        self.i_file_allowed_label.setVisible(True)

        # File not allowed
        if not self._import_entry.allowed:
            self.i_file_import_label.setVisible(True)
            return

        # Set more Values that should be set if allowed
        self.i_file_hash_val.setVisible(True)
        self.i_file_datetime_val.setVisible(True)
        self.i_file_naming_tag_val.setVisible(True)

        # Import checkbox
        if self._import_entry.imported:
            self.i_file_import_label.setVisible(True)
        else:
            self.i_file_import_checkbox.setVisible(True)

        # Add the Metadata
        if self._import_entry.metadata is not None:
            self.i_file_metadata_val.setVisible(True)

        if self._import_entry.google_fotos_metadata is not None:
            self.i_file_google_fotos_metadata_val.setVisible(True)

    def _build_import_layout_match(self):
        """
        Build the import layout if the match is visible.

        :return:
        """
        self._assign_import_file_texts()

        self.g_layout.addWidget(self.i_file_name_val, 1, 5, 1, 3)
        self.g_layout.addWidget(self.i_file_path_val, 2, 5, 1, 3)

        if self._import_entry.allowed:
            self.g_layout.addWidget(self.i_file_hash_val, 3, 5, 1, 3)
            self.g_layout.addWidget(self.i_file_datetime_val, 4, 5, 1, 3)
            self.g_layout.addWidget(self.i_file_naming_tag_val, 5, 5, 1, 3)

        if type(self._match_entry) is FullDatabaseEntry:
            offset = 7
        # _match_entry is FullReplacedEntry
        else:
            offset = 8

        # Allow, import, matchtype
        self.g_layout.addWidget(self.i_file_allowed_label, offset, 5)
        self.g_layout.addWidget(self.i_file_match_type_label, offset, 7)

        # Adding imported widget or checkbox
        if not self._import_entry.allowed or self._import_entry.imported:
            self.g_layout.addWidget(self.i_file_import_label, offset, 6)
        else:
            self.i_file_import_checkbox.setCheckState(Qt.CheckState.Unchecked)
            self.g_layout.addWidget(self.i_file_import_checkbox, offset, 6)

        # Add the Metadata
        if self._match_entry.metadata is not None or self._import_entry.metadata is not None:
            offset += 1
            self.g_layout.addWidget(self.i_file_metadata_val, offset, 5, 1, 3)

        # Adding Google fotos Metadata
        if (self._import_entry.google_fotos_metadata is not None
                or self._match_entry.google_fotos_metadata is not None):
            offset += 1
            self.g_layout.addWidget(self.i_file_google_fotos_metadata_val, offset, 5, 1, 3)

    def _assign_import_file_texts(self):
        """
        Assign all possible values to the import_file.

        Precondition: self._import_entry is not None
        :return:
        """
        # Set values
        self.i_file_name_val.text_label.setText(self._import_entry.org_fname)
        self.i_file_path_val.text_label.setText(self._import_entry.org_fpath)

        # Set Match Type
        if self._import_entry.match_type is not None:
            match_text = self._import_entry.match_type.name.replace('_', ' ').title()
        else:
            match_text = "Not Matched"
        self.i_file_match_type_label.setText(match_text)

        # File not allowed
        if not self._import_entry.allowed:
            self.i_file_allowed_label.setText("Not Allowed")

            import_text = "Imported" if self._import_entry.imported else "Not Imported"
            self.i_file_import_label.setText(import_text)
            return

        state = Qt.CheckState.Checked if self.tile_info.mark_for_import else Qt.CheckState.Unchecked

        self.i_file_import_checkbox.setCheckState(state)
        # Set more Values that should be set if allowed
        self.i_file_hash_val.text_label.setText(self._import_entry.file_hash)
        self.i_file_datetime_val.setText(self._import_entry.datetime.strftime("%Y-%m-%d %H:%M:%S"))
        self.i_file_naming_tag_val.setText(self._import_entry.naming_tag)

        # File allowed
        self.i_file_allowed_label.setText("Allowed")

        # Add the Metadata
        if self._import_entry.metadata is not None:
            self.i_file_metadata_val.text_label.setText(self.model.process_metadata(self._import_entry.metadata)[0])
        else:
            self.i_file_metadata_val.text_label.setText("")

        # Add google fotos metadata
        if self._import_entry.google_fotos_metadata is not None:
            self.i_file_google_fotos_metadata_val.text_label.setText(
                json.dumps(self._import_entry.google_fotos_metadata, indent=4))
        else:
            self.i_file_google_fotos_metadata_val.text_label.setText("")

    # ------------------------------------------------------------------------------------------------------------------
    # Functions for the Part of the Table related to the match entry.
    # ------------------------------------------------------------------------------------------------------------------
    def _set_match_visible(self):
        """
        Set the visibility of all widgets if the match file is visible

        :return:
        """
        self.m_file_org_name_val.setVisible(True)
        self.m_file_datetime_val.setVisible(True)
        self.m_file_naming_tag_val.setVisible(True)
        self.m_file_hash_val.setVisible(True)
        self.m_file_new_name_val.setVisible(True)
        self.m_file_original_google_metadata_val.setVisible(True)

        # Set visibility that differs between the different layouts
        if type(self._match_entry) is FullReplacedEntry:
            self.m_file_successor_val.setVisible(True)

        else:
            self.m_file_org_path_val.setVisible(True)
            self.m_file_trashed_val.setVisible(True)
            self.m_file_present_val.setVisible(True)
            self.m_file_verify_val.setVisible(True)

        if self._match_entry.metadata is not None or self._import_entry.metadata is not None:
            self.m_file_metadata_val.setVisible(True)

        if (self._import_entry.google_fotos_metadata is not None
                or self._match_entry.google_fotos_metadata is not None):
            self.m_file_google_fotos_metadata_val.setVisible(True)

    def _assign_match_file_texts(self):
        """
        Assign all possible values to the match file.

        Precondition: self._match_entry is not None
        :return:
        """
        self.m_file_org_name_val.text_label.setText(self._match_entry.org_fname)
        self.m_file_hash_val.text_label.setText(self._match_entry.file_hash)
        self.m_file_datetime_val.setText(self._match_entry.datetime.strftime("%Y-%m-%d %H:%M:%S"))
        self.m_file_original_google_metadata_val.setText(
            self._match_entry.original_google_metadata.name.replace("_", " ").title())

        # Set the metadata values
        if self._match_entry.metadata is not None:
            self.m_file_metadata_val.text_label.setText(
                self.model.process_metadata(self._match_entry.metadata)[0])
        else:
            self.m_file_metadata_val.text_label.setText("")

        # Set the google fotos metadata values
        if self._match_entry.google_fotos_metadata is not None:
            self.m_file_google_fotos_metadata_val.text_label.setText(
                json.dumps(self._match_entry.google_fotos_metadata, indent=4))
        else:
            self.m_file_google_fotos_metadata_val.text_label.setText("")

        if type(self._match_entry) is FullReplacedEntry:
            # Build match values
            self.m_file_successor_val.setText(str(self._match_entry.successor))
            self.m_file_new_name_val.setText(self._match_entry.former_name)
        else:
            self.m_file_org_path_val.text_label.setText(self._match_entry.org_fpath)
            self.m_file_new_name_val.setText(self._match_entry.new_name)
            self.m_file_naming_tag_val.setText(self._match_entry.naming_tag)

            trash_text = "Trashed" if self._match_entry.trashed else "Not Trashed"
            present_text = "Present" if self._match_entry.present else "Not Present"
            verify_text = "Verified" if self._match_entry.verify else "Not Verified"

            self.m_file_trashed_val.setText(trash_text)
            self.m_file_present_val.setText(present_text)
            self.m_file_verify_val.setText(verify_text)

    def _build_match_layout(self):
        """
        Build all labels for the match file. Also add the files to the grid layout.

        Precondition: self._match_entry is not None
        :return:
        """
        self._assign_match_file_texts()

        # Those can be assigned already outside.
        self.g_layout.addWidget(self.m_file_org_name_val, 1, 1, 1, 4)
        self.g_layout.addWidget(self.m_file_hash_val, 3, 1, 1, 4)
        self.g_layout.addWidget(self.m_file_datetime_val, 4, 1, 1, 4)
        self.g_layout.addWidget(self.m_file_naming_tag_val, 5, 1, 1, 4)

        if type(self._match_entry) is FullReplacedEntry:
            # Add Match values to layout
            self.g_layout.addWidget(self.m_file_successor_val, 6, 1, 1, 4)
            self.g_layout.addWidget(self.m_file_new_name_val, 7, 1, 1, 4)
            self.g_layout.addWidget(self.m_file_original_google_metadata_val, 8, 4)

            offset = 8
        else:
            self.g_layout.addWidget(self.m_file_org_path_val, 2, 1, 1, 4)
            self.g_layout.addWidget(self.m_file_new_name_val, 6, 1, 1, 4)

            self.g_layout.addWidget(self.m_file_trashed_val, 7, 1)
            self.g_layout.addWidget(self.m_file_present_val, 7, 2)
            self.g_layout.addWidget(self.m_file_verify_val, 7, 3)
            self.g_layout.addWidget(self.m_file_original_google_metadata_val, 7, 4)
            offset = 7

        if self._match_entry.metadata is not None or self._import_entry.metadata is not None:
            offset += 1
            self.g_layout.addWidget(self.m_file_metadata_val, offset, 1, 1, 4)

        if (self._import_entry.google_fotos_metadata is not None
              or self._match_entry.google_fotos_metadata is not None):
            offset += 1
            self.g_layout.addWidget(self.m_file_google_fotos_metadata_val, offset, 1, 1, 4)

    # ------------------------------------------------------------------------------------------------------------------
    # Functions for Row and Column Headers
    # ------------------------------------------------------------------------------------------------------------------

    def _build_row_column_header(self):
        """
        Build the row and column headers of the layout.

        :return:
        """
        if self.show_match:
            # Set Column headers
            self.g_layout.addWidget(self.match_file_lbl, 0, 1, 1, 4)
            self.g_layout.addWidget(self.import_file_lbl, 0, 5, 1, 3)

            # Set Row Headers
            self.g_layout.addWidget(self.file_name_lbl, 1, 0)
            self.g_layout.addWidget(self.file_path_lbl, 2, 0)
            self.g_layout.addWidget(self.file_hash_lbl, 3, 0)
            self.g_layout.addWidget(self.datetime_lbl, 4, 0)
            self.g_layout.addWidget(self.naming_tag_lbl, 5, 0)

            # ----------------------------------------------------------------------------------------------------------
            # Case distinction for different rows for Replaced VS Database
            if type(self._match_entry) is FullReplacedEntry:

                self.g_layout.addWidget(self.successor_lbl, 6, 0)
                self.g_layout.addWidget(self.new_file_lbl, 7, 0)
                self.g_layout.addWidget(self.options, 8, 0)

                offset = 8

            # Otherwise FullDatabaseEntry
            else:
                self.g_layout.addWidget(self.new_file_lbl, 6, 0)
                self.g_layout.addWidget(self.options, 7, 0)

                offset = 7
            # ----------------------------------------------------------------------------------------------------------

            # Add Metadata
            if self._match_entry.metadata is not None or self._import_entry.metadata is not None:
                offset += 1
                self.g_layout.addWidget(self.metadata_lbl, offset, 0)

            # Add Google Fotos Metadata
            if (self._import_entry.google_fotos_metadata is not None
                  or self._match_entry.google_fotos_metadata is not None):
                offset += 1
                self.g_layout.addWidget(self.google_fotos_metadata_lbl, offset, 0)

        else:
            # We only show the import file
            # Set Column Header
            self.g_layout.addWidget(self.import_file_lbl, 0, 1, 1, 3)

            # Add the labels so far to the layout
            self.g_layout.addWidget(self.file_name_lbl, 1, 0)
            self.g_layout.addWidget(self.file_path_lbl, 2, 0)

            # File not allowed
            if not self._import_entry.allowed:
                self.g_layout.addWidget(self.options, 3, 0)
                return

            self.g_layout.addWidget(self.file_hash_lbl, 3, 0)
            self.g_layout.addWidget(self.datetime_lbl, 4, 0)
            self.g_layout.addWidget(self.naming_tag_lbl, 5, 0)
            self.g_layout.addWidget(self.options, 6, 0)

            # Add the Metadata
            if self._import_entry.metadata is not None:
                self.g_layout.addWidget(self.metadata_lbl, 7, 0)

            if self._import_entry.google_fotos_metadata is not None:
                self.g_layout.addWidget(self.google_fotos_metadata_lbl, 8, 0)

    def _set_row_column_header_visibility(self):
        """
        Set the visibility of the row and column headers.

        :return:
        """
        # Always visible
        self.import_file_lbl.setVisible(True)
        self.file_name_lbl.setVisible(True)
        self.file_path_lbl.setVisible(True)
        self.options.setVisible(True)

        if self.show_match:
            # Set Column headers
            self.match_file_lbl.setVisible(True)

            # Set Row Headers
            self.file_hash_lbl.setVisible(True)
            self.datetime_lbl.setVisible(True)
            self.naming_tag_lbl.setVisible(True)
            self.new_file_lbl.setVisible(True)

            if type(self._match_entry) is FullReplacedEntry:
                self.successor_lbl.setVisible(True)

            # Add Metadata
            if self._match_entry.metadata is not None or self._import_entry.metadata is not None:
                self.metadata_lbl.setVisible(True)

            # Add Google Fotos Metadata
            if (self._import_entry.google_fotos_metadata is not None
                    or self._match_entry.google_fotos_metadata is not None):
                self.google_fotos_metadata_lbl.setVisible(True)

        else:
            # File not allowed
            if self._import_entry.allowed:
                self.file_hash_lbl.setVisible(True)
                self.datetime_lbl.setVisible(True)
                self.naming_tag_lbl.setVisible(True)

                # Add the Metadata
                if self._import_entry.metadata is not None:
                    self.metadata_lbl.setVisible(True)

                # Add the Google Fotos Metadata
                if self._import_entry.google_fotos_metadata is not None:
                    self.google_fotos_metadata_lbl.setVisible(True)

    # ------------------------------------------------------------------------------------------------------------------
    # Setting Stretchs.
    # ------------------------------------------------------------------------------------------------------------------

    def _set_stretch_match_layout(self):
        """
        Set Column and Row stretch when we have the match view.
        :return:
        """
        # Set column stretch
        self.g_layout.setColumnStretch(0, 0)
        self.g_layout.setColumnStretch(1, 1)
        self.g_layout.setColumnStretch(2, 1)
        self.g_layout.setColumnStretch(3, 1)
        self.g_layout.setColumnStretch(4, 1)
        self.g_layout.setColumnStretch(5, 1)
        self.g_layout.setColumnStretch(6, 1)
        self.g_layout.setColumnStretch(7, 1)

        # Setting row stretch

        # Set Column headers
        self.g_layout.setRowStretch(0, 0)
        self.g_layout.setRowStretch(1, 0)
        self.g_layout.setRowStretch(2, 0)
        self.g_layout.setRowStretch(3, 0)
        self.g_layout.setRowStretch(4, 0)
        self.g_layout.setRowStretch(5, 0)
        self.g_layout.setRowStretch(6, 0)
        self.g_layout.setRowStretch(7, 0)
        offset = 7

        if type(self._match_entry) is FullReplacedEntry:
            self.g_layout.setRowStretch(8, 0)
            offset = 8

        # Add Metadata
        if self._match_entry.metadata is not None or self._import_entry.metadata is not None:
            offset += 1
            self.g_layout.setRowStretch(offset, 1)

        # Add Google Fotos Metadata
        if (self._import_entry.google_fotos_metadata is not None
              or self._match_entry.google_fotos_metadata is not None):
            offset += 1
            self.g_layout.setRowStretch(offset, 1)



def switcher(window, tiles):
    """
    Switcher function to switch between the different tiles.

    :param window:
    :param tiles:
    :return:
    """
    while True:
        window.show_match = not window.show_match
        for tile in tiles:
            window.tile_info = tile
            time.sleep(1)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # window = ImportMetadataWidget(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window = DualMetadataWidget(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.show_match = True
    window.model.current_import_table_name = "tbl_1998737548188488947"
    tiles = [TileInfo(
        key=20,
        path="",
        imported=False,
        allowed=False,
        match_type=MatchTypes.No_Match
    ),
    TileInfo(
            key=20,
            path="",
            imported=False,
            allowed=False,
            match_type=MatchTypes.No_Match
        ),
        TileInfo(
            key=72,
            path="",
            imported=False,
            allowed=False,
            match_type=MatchTypes.No_Match
        ),
        TileInfo(
            key=134,
            path="",
            imported=False,
            allowed=False,
            match_type=MatchTypes.No_Match
        ), TileInfo(
        key=10,
        path="",
        imported=False,
        allowed=False,
        match_type=MatchTypes.No_Match
    ),
    TileInfo(
        key=11,
        path="",
        imported=False,
        allowed=False,
        match_type=MatchTypes.No_Match
    )
    ]
    # thread = threading.Thread(target=switcher, args=(window, tiles))
    # thread.start()

    window.tile_info = tiles[0]
    window.tile_info = tiles[1]

    window.show()
    sys.exit(app.exec())