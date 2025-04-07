from __future__ import annotations

from typing import Type

import PyQt6.sip as sip
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QMainWindow, QWidget

from photo_lib.gui.util.image_loader_manager import ImageLoaderManager
from photo_lib.gui.util.image_loader_worker import LoadingResult


"""
File contains all custom instances of QMainWindow that are needed for this project.
"""


class BaseMainWindow(QMainWindow):
    """
    This QMainWindow is an extension of the original with the notable exception of being able to schedule the updating
    of a pixmap.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = ImageLoaderManager(root_widget=self)

    @pyqtSlot(LoadingResult)
    def set_pixmap(self, result: LoadingResult):
        """
        Update the targeted widget with the given pixmap.
        """
        # Check the image is not deleted
        if sip.isdeleted(result.tgt_widget):
            return

        result.tgt_widget.pixmap = result.pm
        result.tgt_widget.width_div_height = result.wdh
        result.tgt_widget.file_path = result.file_path
        result.tgt_widget.repaint()


class DeduplicatorMainWindow(BaseMainWindow):
    """
    Instance of the GUI started specifically intended only for the Fast-Image-Deduplicator.
    """
    # TODO implement


class PhotoLibMainWindow(BaseMainWindow):
    """
    Instance of the GUI started intended for the entire database.
    """
    last_view: Type[QWidget]

