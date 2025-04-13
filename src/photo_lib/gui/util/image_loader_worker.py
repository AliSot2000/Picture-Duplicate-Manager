from __future__ import annotations

import os
from dataclasses import dataclass

from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, QSize, Qt
from PyQt6.QtGui import QPixmap, QImage

from photo_lib.gui.widgets.base_image import BaseImage


@dataclass
class LoadingResult:
    # TODO local import might be needed

    pm: QPixmap
    wdh: float
    tgt_widget: "BaseImage"
    file_path: str


class SignalEmitter(QObject):
    finished = pyqtSignal(LoadingResult)


class ImageLoaderWorker(QRunnable):
    # TODO: Try local import here.
    def __init__(self,
                 image_path: str,
                 root_widget: "BaseMainWindow",
                 tgt_widget: BaseImage,
                 target_size: QSize = None):
        """
        Create a new worker instance

        :param image_path: path to image file that should be loaded
        :param root_widget: root widget that handles checking, if the target widget still exists, sets the data and
            issues a paint event
        :param target_size: the target size the images is supposed to be scaled to. No scaling happens if it is None
        :param tgt_widget: Widget to update afterward with the new pixmap.
        """
        super().__init__()
        self.image_path = image_path
        self.root_widget = root_widget
        self.target_widget = tgt_widget
        self.target_size = target_size

        self.emitter = SignalEmitter()

    # INFO: We cannot cover this function as it is executed in a different thread.
    def run(self):  # pragma: no cover
        """
        Run Method does:
        - Load Image
        - Scale Image
        - Emit a Signal for the Target Widget to Update
        """
        if os.path.exists(self.image_path):
            image = QImage(self.image_path)  # Load image safely
            pixmap = QPixmap.fromImage(image)  # Convert to pixmap

            try:
                aspect_ratio = pixmap.width() / pixmap.height()
            except ZeroDivisionError:
                aspect_ratio = 1.0

            # Compress the pixmap if desired.
            if self.target_size is not None:
                scaled_pm = pixmap.scaled(self.target_size, Qt.AspectRatioMode.KeepAspectRatio)
            else:
                scaled_pm = pixmap

            result = LoadingResult(
                tgt_widget=self.target_widget,
                pm=scaled_pm,
                wdh=aspect_ratio,
                file_path=self.image_path,
            )

            # Trigger repaint
            self.emitter.finished.connect(self.root_widget.set_pixmap)
            self.emitter.finished.emit(result)
            self.emitter.finished.disconnect(self.root_widget.set_pixmap)