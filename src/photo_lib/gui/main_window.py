import time
from threading import Thread

from PyQt6.QtWidgets import QMainWindow, QScrollArea, QLabel, QMenu, QMenuBar, QStatusBar, QToolBar, QFileDialog, QHBoxLayout, QSizePolicy, QWidget, QStackedLayout
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtCore import Qt, QSize
from photo_lib.gui.model import Model
from photo_lib.gui.compare_widget import CompareRoot
from photo_lib.gui.image_container import ResizingImage
from photo_lib.gui.modals import DateTimeModal, FolderSelectModal
from photo_lib.gui.media_pane import MediaPane
from typing import List

# TODO
#  - Add Button to go to next duplicate entry
#  - Add Button to commit only the selected main and delete to database
#  - Add Button to commit the selected main and delete everything else in database
#  - File Selector for database
#  - Buttons for deduplication process.
#  - Time line selection
#  - Images in windows needed at some point


class RootWindow(QMainWindow):
    model:  Model
    dummy_center: QWidget
    stacked_layout: QStackedLayout

    # Fill Screen Image
    full_screen_image: ResizingImage = None

    # Scrolling and CompareView
    scroll_area: QScrollArea
    compare_root: CompareRoot

    # Change Datetime Modal
    datetime_modal: DateTimeModal

    def __init__(self):
        super().__init__()
        self.model = Model()
        self.scroll_area = QScrollArea()
        self.stacked_layout = QStackedLayout()
        self.datetime_modal = DateTimeModal()

        self.compare_root = CompareRoot(self.model, open_image_fn=self.open_image,
                                        open_datetime_modal_fn=self.open_datetime_modal)
        self.dummy_center = QWidget()
        self.dummy_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # self.dummy_center.setStyleSheet("background-color: #000000; color: #ffffff;")
        self.setCentralWidget(self.dummy_center)

        self.dummy_center.setLayout(self.stacked_layout)

        self.scroll_area.setWidget(self.compare_root)

        self.compare_root.load_elements()
        self.stacked_layout.addWidget(self.scroll_area)
        self.stacked_layout.setCurrentWidget(self.scroll_area)

        # Connecting the buttons of the modals
        self.datetime_modal.close_button.clicked.connect(self.close_datetime_modal)
        self.datetime_modal.apply_button.clicked.connect(self.apply_datetime_modal)
        self.datetime_modal.apply_close_button.clicked.connect(self.apply_close_datetime_modal)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Propagate the resizing down even though there is a scroll view.
        :param a0: size event
        :return:
        """
        super().resizeEvent(a0)
        if a0.size().width() > self.compare_root.minimumWidth():
            self.compare_root.setMaximumWidth(a0.size().width())
        else:
            self.compare_root.setMaximumWidth(self.compare_root.minimumWidth())

        new_size = QSize(a0.size().width() - self.scroll_area.verticalScrollBar().width(),
                         a0.size().height() - self.scroll_area.horizontalScrollBar().height())

        self.compare_root.resize(new_size)
        # print(a0.size())

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
        self.stacked_layout.setCurrentWidget(self.scroll_area)

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