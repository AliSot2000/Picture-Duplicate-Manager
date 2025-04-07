from __future__ import annotations


import PyQt6.sip as sip
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QMainWindow

from .util.image_loader_worker import LoadingResult
from .util.image_loader_manager import ImageLoaderManager


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
        result.tgt_widget.repaint()

