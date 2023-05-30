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
    sla: QStackedLayout

    # Fill Screen Image
    full_screen_image: ResizingImage = None

    # Scrolling and CompareView
    sca: QScrollArea
    csl: CompareRoot

    # Change Datetime Modal
    dtm: DateTimeModal

    def __init__(self):
        super().__init__()
        self.model = Model()
        self.sca = QScrollArea()
        self.sla = QStackedLayout()
        self.dtm = DateTimeModal()

        self.csl = CompareRoot(self.model, open_image_fn=self.open_image,
                               open_datetime_modal_fn=self.open_datetime_modal)
        self.dummy_center = QWidget()
        self.dummy_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dummy_center.setStyleSheet("background-color: #000000; color: #ffffff;")
        self.setCentralWidget(self.dummy_center)

        self.dummy_center.setLayout(self.sla)

        self.sca.setWidget(self.csl)

        self.csl.load_elements()
        self.sla.addWidget(self.sca)
        self.sla.setCurrentWidget(self.sca)

        # Connecting the buttons of the modals
        self.dtm.close_button.clicked.connect(self.close_datetime_modal)
        self.dtm.apply_button.clicked.connect(self.apply_datetime_modal)
        self.dtm.apply_close_button.clicked.connect(self.apply_close_datetime_modal)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Propagate the resizing down even though there is a scroll view.
        :param a0: size event
        :return:
        """
        super().resizeEvent(a0)
        if a0.size().width() > self.csl.minimumWidth():
            self.csl.setMaximumWidth(a0.size().width())
        else:
            self.csl.setMaximumWidth(self.csl.minimumWidth())

        new_size = QSize(a0.size().width() - self.sca.verticalScrollBar().width(),
                         a0.size().height() - self.sca.horizontalScrollBar().height())

        self.csl.resize(new_size)
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
            self.sla.addWidget(self.full_screen_image)
        else:
            self.full_screen_image.load_image(path)

        self.sla.setCurrentWidget(self.full_screen_image)

    def close_image(self):
        """
        Close the full screen image.
        :return:
        """
        self.sla.setCurrentWidget(self.sca)

    def open_datetime_modal(self, media_pane: MediaPane):
        """
        Open the datetime modal.
        :param media_pane: Media pane to modify
        :return:
        """
        self.dtm.media_pane = media_pane
        self.dtm.show()

    def close_datetime_modal(self):
        """
        Hide the datetime modal again.
        :return:
        """
        self.dtm.hide()

    def apply_datetime_modal(self):
        """
        Hide the modal, apply the new naming tag.
        :return:
        """
        try:
            self.model.try_rename_image(tag=self.dtm.tag_input.text(), dbe=self.dtm.media_pane.dbe,
                                    custom_datetime=self.dtm.custom_datetime_input.text())
        except Exception as e:
            # self.error_popup.error_msg = f"Failed to update Datetime:\n {e}"
            # self.error_popup.open()
            print(f"Failed to update Datetime:\n {e}")

        self.close_datetime_modal()

    def apply_close_datetime_modal(self):
        """
        Apply the new naming tag, close the modal and remove the pane from the compare view.
        :return:
        """
        self.apply_datetime_modal()
        self.csl.remove_media_pane(self.dtm.media_pane)