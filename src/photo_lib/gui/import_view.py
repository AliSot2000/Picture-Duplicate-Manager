from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel
import sys
from photo_lib.gui.named_picture_block import CheckNamedPictureBlock
from photo_lib.gui.model import Model
from photo_lib.PhotoDatabase import MatchTypes


class ImportView(QFrame):
    model: Model
    scroll_area: QScrollArea

    dummy_widget: QWidget
    import_name: QLabel
    inner_layout: QVBoxLayout
    outer_layout: QVBoxLayout

    def __init__(self, model: Model):
        super().__init__()
        self.model = model

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.import_name = QLabel()

        self.outer_layout = QVBoxLayout()
        self.setLayout(self.outer_layout)

        self.inner_layout = QVBoxLayout()
        self.inner_layout.setContentsMargins(0, 0, 0, 0)

        self.dummy_widget = QWidget()
        self.dummy_widget.setLayout(self.inner_layout)

        self.outer_layout.addWidget(self.import_name)
        self.outer_layout.addWidget(self.scroll_area)
        self.scroll_area.setWidget(self.dummy_widget)


        self.build_import_view()

    def build_import_view(self):
        """
        Build the import view from the current tile_infos from the model.

        :return:
        """
        # Empty layout
        while self.inner_layout.count() > 0:
            self.inner_layout.takeAt(0)

        self.update_name()

        # Explicitly coding the different values for the match_types to allow for more verbose naming of subsections.
        if self.model.tile_infos is None:
            return

        # Add Block for no match
        if len(self.model.tile_infos[MatchTypes.No_Match.name.lower()]) > 0:
            w = CheckNamedPictureBlock(mt=MatchTypes.No_Match,
                                       tile_infos=self.model.tile_infos[MatchTypes.No_Match.name.lower()],
                                       title="Media Files without Match in the Database")
            self.inner_layout.addWidget(w)

        if len(self.model.tile_infos[MatchTypes.Binary_Match_Images.name.lower()]) > 0:
            w = CheckNamedPictureBlock(mt=MatchTypes.Binary_Match_Images,
                                       tile_infos=self.model.tile_infos[MatchTypes.Binary_Match_Images.name.lower()],
                                       title="Media Files with Binary Match in Database")
            self.inner_layout.addWidget(w)

        if len(self.model.tile_infos[MatchTypes.Binary_Match_Replaced.name.lower()]) > 0:
            w = CheckNamedPictureBlock(mt=MatchTypes.Binary_Match_Replaced,
                                       tile_infos=self.model.tile_infos[MatchTypes.Binary_Match_Replaced.name.lower()],
                                       title="Media Files with Binary Match in the known Duplicates")
            self.inner_layout.addWidget(w)

        if len(self.model.tile_infos[MatchTypes.Binary_Match_Trash.name.lower()]) > 0:
            w = CheckNamedPictureBlock(mt=MatchTypes.Binary_Match_Trash,
                                       tile_infos=self.model.tile_infos[MatchTypes.Binary_Match_Trash.name.lower()],
                                       title="Media Files with Binary Match in the Trash")
            self.inner_layout.addWidget(w)

        if len(self.model.tile_infos[MatchTypes.Hash_Match_Replaced.name.lower()]) > 0:
            w = CheckNamedPictureBlock(mt=MatchTypes.Hash_Match_Replaced,
                                        tile_infos=self.model.tile_infos[MatchTypes.Hash_Match_Replaced.name.lower()],
                                        title="Media Files with matching hash and filesize in the known Duplicates")
            self.inner_layout.addWidget(w)

        if len(self.model.tile_infos[MatchTypes.Hash_Match_Trash.name.lower()]) > 0:
            w = CheckNamedPictureBlock(mt=MatchTypes.Hash_Match_Trash,
                                        tile_infos=self.model.tile_infos[MatchTypes.Hash_Match_Trash.name.lower()],
                                        title="Media Files with matching hash and filesize in the Trash")
            self.inner_layout.addWidget(w)

        if len(self.model.tile_infos["not_allowed"]) > 0:
            w = CheckNamedPictureBlock(mt=None,
                                        tile_infos=self.model.tile_infos["not_allowed"],
                                        title="Media Files not allowed to be imported based on file extension")
            w.import_checkbox.setDisabled(True)
            self.inner_layout.addWidget(w)

    def update_name(self):
        """
        Updates the name of the current import.
        :return:
        """
        table_desc = self.model.get_current_import_table_name()
        if table_desc is not None:
            self.import_name.setText(table_desc)
        elif self.model.current_import_table_name is not None:
            self.import_name.setText(self.model.current_import_table_name)
        else:
            self.import_name.setText("Import Source Unknown")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = ImportView(Model(folder_path="/media/alisot2000/DumpStuff/dummy_db/"))
    window.model.current_import_table_name = "tbl_1998737548188488947"
    window.model.build_tiles_from_table()
    window.setWindowTitle("Import View")

    window.build_import_view()
    window.show()
    sys.exit(app.exec())