import time
from threading import Thread

from PyQt6.QtWidgets import QMainWindow, QScrollArea, QLabel, QMenu, QMenuBar, QStatusBar, QToolBar, QFileDialog, QHBoxLayout, QSizePolicy, QWidget, QStackedLayout, QVBoxLayout
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtCore import Qt, QSize
from photo_lib.gui.model import Model
from photo_lib.gui.compare_widget import CompareRoot
from photo_lib.gui.image_container import ResizingImage
from photo_lib.gui.modals import DateTimeModal, FolderSelectModal
from photo_lib.gui.media_pane import MediaPane
from photo_lib.gui.button_bar import ButtonBar
from typing import List

# TODO
#  - Session storage
#  - Config Storage
#  - Keyboard shortcuts
#  - File Selector for database
#  - Buttons for deduplication process.

# TODO Features
#  - Time line selection
#  - Images in windows needed at some point
#  - No import required, just list the images in folders
#  - Verify integrity of images
#  - Multi-database support... Future.


class RootWindow(QMainWindow):
    model:  Model
    dummy_center: QWidget
    stacked_layout: QStackedLayout

    # Fill Screen Image
    full_screen_image: ResizingImage = None

    compare_root: CompareRoot

    # Change Datetime Modal
    datetime_modal: DateTimeModal

    def __init__(self):
        super().__init__()

        # Object Instantiation
        self.model = Model()

        self.dummy_center = QWidget()
        self.stacked_layout = QStackedLayout()
        self.datetime_modal = DateTimeModal()
        self.compare_root = CompareRoot(self.model, open_image_fn=self.open_image,
                                        open_datetime_modal_fn=self.open_datetime_modal)

        # Generating the remaining widgets
        self.compare_root.load_elements()

        # Top down adding of widgets and layouts
        self.setCentralWidget(self.dummy_center)

        self.dummy_center.setLayout(self.stacked_layout)
        self.dummy_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # self.dummy_center.setStyleSheet("background-color: #000000; color: #ffffff;")

        self.stacked_layout.addWidget(self.compare_root)
        self.stacked_layout.setCurrentWidget(self.compare_root)

        # Connecting the buttons of the modals
        self.datetime_modal.close_button.clicked.connect(self.close_datetime_modal)
        self.datetime_modal.apply_button.clicked.connect(self.apply_datetime_modal)
        self.datetime_modal.apply_close_button.clicked.connect(self.apply_close_datetime_modal)

        # Misc setup of the window
        self.setWindowTitle("Picture Duplicate Manager")

    def open_image(self, path: str):
        """
        Open an image in full screen mode.
        :param path: path to the image
        :return:
        """
        if self.full_screen_image is None:
            self.full_screen_image = ResizingImage(path)
            self.full_screen_image.clicked.connect(self.close_image)
            self.stacked_layout.addWidget(self.full_screen_image)
        else:
            self.full_screen_image.load_image(path)

        self.stacked_layout.setCurrentWidget(self.full_screen_image)

    def close_image(self):
        """
        Close the full screen image.
        :return:
        """
        self.stacked_layout.setCurrentWidget(self.compare_root)

    def open_datetime_modal(self, media_pane: MediaPane):
        """
        Open the datetime modal.
        :param media_pane: Media pane to modify
        :return:
        """
        self.datetime_modal.media_pane = media_pane
        self.datetime_modal.show()

    def close_datetime_modal(self):
        """
        Hide the datetime modal again.
        :return:
        """
        self.datetime_modal.hide()

    def apply_datetime_modal(self):
        """
        Hide the modal, apply the new naming tag.
        :return:
        """
        try:
            self.model.try_rename_image(tag=self.datetime_modal.tag_input.text(), dbe=self.datetime_modal.media_pane.dbe,
                                        custom_datetime=self.datetime_modal.custom_datetime_input.text())
        except Exception as e:
            # self.error_popup.error_msg = f"Failed to update Datetime:\n {e}"
            # self.error_popup.open()
            print(f"Failed to update Datetime:\n {e}")

        # update the media pane from the database entry.
        self.datetime_modal.media_pane.update_file_naming()

        self.close_datetime_modal()

    def apply_close_datetime_modal(self):
        """
        Apply the new naming tag, close the modal and remove the pane from the compare view.
        :return:
        """
        self.apply_datetime_modal()
        self.compare_root.remove_media_pane(self.datetime_modal.media_pane)
