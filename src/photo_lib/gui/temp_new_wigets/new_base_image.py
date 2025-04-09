import os
from typing import Optional

from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QFont, QPaintEvent, QImage, QPixmap
from PyQt6.QtWidgets import QFrame

import photo_lib.gui.util.fonts as font_utils
from photo_lib.custom_enum import TargetViewTable
from photo_lib.data_objects import MediaPaths
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.util.image_loader_manager import ImageLoaderManager


# TODO add scrolling text if it goes beyond the bounds.
class BaseImage(QFrame):
    pixmap: Optional[QPixmap] = None

    __media: MediaPaths

    width_div_height: float = 1.0

    # Background needed to
    filler_color = Qt.GlobalColor.darkGray

    # Currently loaded file path (needed to determine if we need to update the currently loaded image)
    file_path: Optional[str] = None

    def __init__(self, mp: MediaPaths, model: UIModel):
        """
        The new variant of the BaseImage doesn't allow reusing the widget anymore. With every new MediaPaths a new
        object needs to be instantiated.

        PRECONDITION: The Parent exists in the database.

        :param mp: MediaPaths object to load the image from
        :param model: UIModel to use for the the config
        """
        super().__init__()
        self.__media = mp
        self.model = model

        tgt_fp = self.determine_fp_to_use()
        if tgt_fp is None:
            return

        self.dispatch_load(tgt_fp)

    @property
    def media(self):
        return self.__media

    def determine_fp_to_use(self) -> str | None:
        """
        Determine which of the possible files to use to display the image
        """
        major_size = max(self.size().width(), self.size().height())

        # We're smaller than thumbnail, we're taking the thumbnail
        if self.model.ui_config.load_parent_automatically and self.media.parent is not None:
            # INFO: We need to reload the parent because it could have been moved/renamed/...
            parent = self.model.api.db.get_media(self.media.parent)

            if major_size < self.model.thumbnail_size:
                possible_paths = [self.media.thumbnail_fp, parent.thumbnail_fp,
                                  self.media.miniature_fp, parent.miniature_fp,
                                  self.media.original_fp, parent.original_fp]
            elif major_size < self.model.miniature_size:
                possible_paths = [self.media.miniature_fp, parent.miniature_fp,
                                  self.media.original_fp, parent.original_fp]
            elif major_size >= self.model.miniature_size:
                possible_paths = [self.media.original_fp, parent.original_fp]
            else:  # pragma: no cover
                raise ImplementationError("Tertiem non Datur. This case shouldn't be possible")

        else:
            if major_size < self.model.thumbnail_size:
                possible_paths = [self.media.thumbnail_fp, self.media.miniature_fp, self.media.original_fp]
            elif major_size < self.model.miniature_size:
                possible_paths = [self.media.miniature_fp, self.media.original_fp]
            elif major_size >= self.model.miniature_size:
                possible_paths = [self.media.original_fp]
            else:  # pragma: no cover
                raise ImplementationError("Tertiem non Datur. This case shouldn't be possible")

        # Get the first matching file path
        valid_paths = list(filter(lambda x: x is not None, possible_paths))

        # No valid path found, use empty painter.
        if len(valid_paths) == 0:
            self.pixmap = None
            return None

        assert len(valid_paths) > 0, "At least one valid path should exist."

        return valid_paths[0]

    def dispatch_load(self, fp: str):
        """
        Perform the loading of the image either in the current thread or with a QRunnable if the worker for that is started.
        """
        manager = ImageLoaderManager.get_instance()
        if manager is None:
            self.local_fetch_image(fp)
        else:
            manager.load_image(image_path=fp, widget=self)

    def local_fetch_image(self, fp: str):
        """
        Perform loading in this thread
        """
        assert os.path.exists(fp), "PRECONDITION violated: File Path is supposed to exist"

        image = QImage(fp)  # Load image safely
        pixmap = QPixmap.fromImage(image)  # Convert to pixmap

        scaled_pm = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)

        try:
            aspect_ratio = pixmap.width() / pixmap.height()
        except ZeroDivisionError:
            aspect_ratio = 1.0

        self.pixmap = scaled_pm
        self.width_div_height = aspect_ratio

    def sizeHint(self):
        """
        Custom implementation of the size hint depending on if the image is loaded or not.
        :return:
        """
        if self.pixmap and not self.pixmap.isNull():
            return self.pixmap.size()
        return QSize()

    def paintEvent(self, event: QPaintEvent):
        """
        Custom implementation of the paint event to rescale the image to fit.
        :param event:
        :return:
        """
        super().paintEvent(event)

        inner_size = QSize(max(0, self.size().width() - 2 * self.frameWidth()),
                           max(0, self.size().height() - 2 * self.frameWidth()))

        if self.pixmap is None or self.pixmap.isNull():
            self.empty_pixmap_painter()
            return

        r = QRect(QPoint(),
                  self.pixmap.size().scaled(inner_size, Qt.AspectRatioMode.KeepAspectRatio))
        r.moveCenter(self.rect().center())

        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)

    def empty_pixmap_painter(self):
        """
        In case there's no image loaded, paint a message on the widget.
        :return:
        """
        # Create a filler shape to indicate where the image is supposed to be.
        pt = QPainter(self)
        pt.fillRect(self.rect(), self.filler_color)

        # Draw the text in the middle of the widget
        if self.pixmap is None or (self.pixmap is not None and self.pixmap.isNull()):
            if self.media.element.source_table != TargetViewTable.IMPORT:
                text = f"Couldn't load {self.media.element.key} from {self.media.element.source_table.name}"
            else:
                text = f"Couldn't load {self.media.element.key} from {self.media.element.target_import_table}"
        else:
            text = "Empty file path"

        font = QFont("Arial", font_utils.get_h1_font_size(), QFont.Weight.Bold)
        pt.setFont(font)
        text_rect = pt.boundingRect(self.rect(), 0, text)
        text_position = self.rect().center() - text_rect.center()
        pt.drawText(text_position, text)

    def resizeEvent(self, a0):
        """
        Handle Resize Event differently:
        - If we're scaling down i.e. smaller, compute pixmap as a scaled down version of the current one
        - If we're scaling up, load the file again and recompute the smaller version.
        """
        tgt_path = self.determine_fp_to_use()
        if tgt_path is None:
            return

        # A different image is suitable. Schedule its load.
        if tgt_path != self.file_path:
            self.dispatch_load(tgt_path)


