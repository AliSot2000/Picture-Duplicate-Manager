import os.path

from PyQt6.QtWidgets import QFrame, QWidget, QVBoxLayout, QLabel, QApplication
from PyQt6.QtCore import Qt

from photo_lib.custom_enum import ImportStatus, Allowed, TargetViewTable
from photo_lib.data_objects import MediaPaths
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.temp_new_wigets.clickable_image import ClickableImage


class NamedTile(QFrame):
    """
    A tile that contains a ClickableImage and a label. The tile is square and the image is centered in the tile.
    """
    # Layout that holds the QLabel and the ClickableImage
    layout: QVBoxLayout

    # Retain access to the Model
    model: UIModel

    # Text Widget
    text: QLabel

    # Image Widget
    image: ClickableImage

    __import_state: ImportStatus
    __allowed: Allowed

    @property
    def allowed(self):
        return self.__allowed

    @property
    def import_state(self):
        return self.__import_state

    @import_state.setter
    def import_state(self, value: ImportStatus):
        # Don't do anything if the file isn't allowed.
        if self.allowed != Allowed.ALLOWED:
            return

        # Return if the target state isn't valid
        if value in [ImportStatus.IMPORTED, ImportStatus.DELETED]:
            return

        # Don't do anything if the state is the same.
        if value == self.__import_state:
            return

        # Set the State of the image
        self.__import_state = value

        # Set the
        self.model.api.db.set_imported_status(key=self.image.media.element.key,
                                              tbl_name=self.image.media.element.target_import_table,
                                              status=value)

        if value == ImportStatus.IGNORE:
            self.marked_not_for_import()
        else:
            self.marked_for_import()

    def __init__(self, model: UIModel, mp: MediaPaths, parent: QWidget = None):
        """
        The new variant of the BaseImage doesn't allow reusing the widget anymore. With every new MediaPaths a new
        object needs to be instantiated.

        PRECONDITION: The Parent exists in the database.

        :param mp: MediaPaths object to load the image from
        :param model: UIModel to use for the the config
        :param parent: Parent widget
        """
        super().__init__(parent)
        assert mp.element.source_table == TargetViewTable.IMPORT, \
            "Unexpected MediaPaths object. NamedTile expects IMPORT"


        self.layout = QVBoxLayout()

        self.model = model
        self.media = mp

        self.text = QLabel(
            os.path.basename(model.api.db.get_path_from_import_table(
                key=mp.element.key,
                tbl=mp.element.target_import_table)
            )
        )
        self.image = ClickableImage(model=model, mp=mp)
        self.fetch_import_state()

        self.layout.addWidget(self.image, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.text, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(self.layout)

    def fetch_import_state(self):
        """
        Fetch the state of the key in the database. Needed when the user selects an entire block.
        """
        info = self.model.api.db.get_import_state(key=self.image.media.element.key,
                                                  tbl=self.image.media.element.target_import_table)
        assert info is not None, "PRECONDITION FAILED: File should exist in the database"
        self.__allowed, self.__import_state = info

        self.set_color()

    def heightForWidth(self, a0):
        """
        Make sure that we have a square tile.
        """
        return self.width()

    def set_imported(self):
        """
        Set the background color of the widget to indicate its state. For the state imported.
        """
        # Set color green
        cs = QApplication.styleHints().colorScheme()
        if cs == Qt.ColorScheme.Dark:
            color_name = self.model.ui_config.dark_color_name_success
        else:
            color_name = self.model.ui_config.bright_color_name_success

        self.setStyleSheet(f"background-color: {color_name};")

    def marked_for_import(self):
        """
        Set the background color of the widget to indicate its state. For the state marked for import.
        """
        cs = QApplication.styleHints().colorScheme()
        if cs == Qt.ColorScheme.Dark:
            color_name = self.model.ui_config.dark_color_name_select
        else:
            color_name = self.model.ui_config.bright_color_name_select

        self.setStyleSheet(f"background-color: {color_name};")

    def marked_not_for_import(self):
        """
        Set the background color of the widget to indicate its state. For the state marked not for import.
        """
        cs = QApplication.styleHints().colorScheme()
        if cs == Qt.ColorScheme.Dark:
            color_name = self.model.ui_config.dark_color_name_fail
        else:
            color_name = self.model.ui_config.bright_color_name_fail

        self.setStyleSheet(f"background-color: {color_name};")

    def set_color(self):
        """
        Set the color based of the attributes.
        """
        if self.allowed != Allowed.ALLOWED:
            self.marked_not_for_import()
            return

        # PRECONDITION: Is Allowed
        if self.import_state == ImportStatus.IMPORTED or self.import_state == ImportStatus.DELETED:
            self.set_imported()

        elif self.import_state == ImportStatus.MARKED:
            self.marked_for_import()

        elif self.import_state == ImportStatus.IGNORE:
            self.marked_not_for_import()
        else:  # pragma: no cover
            raise ImplementationError("Uncovered case of the import state. This should not be possible.")