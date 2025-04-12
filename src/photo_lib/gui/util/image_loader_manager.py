from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool, QSize

from photo_lib.gui.widgets.base_image import BaseImage
from .image_loader_worker import ImageLoaderWorker
from ...errors_and_warnings import ImplementationError


class ImageLoaderManager(QObject):
    instance = None  # Singleton

    # INFO: Only forward reference works.
    root_widget: Optional["BaseMainWindow"] = None

    def __init__(self, root_widget: "BaseMainWindow"):
        """
        Create an instance of the ImageLoaderManager.

        INFO: Because we run into segfaults we don't do singletons by overloading __new__.
            If you attempt to call it twice, it will raise an ImplementationError. It is suggested that you use the
            get_instance() class method.

        :raises ImplementationError: If you attempt to call it twice.        """
        if self.instance is None:
            super().__init__()
            print("Init called.")
            self.thread_pool = QThreadPool().globalInstance()
            self.root_widget = root_widget
            ImageLoaderManager.instance = self
        else:
            raise ImplementationError("Attempting to reinitialize an already initialized manager")

    @classmethod
    def get_instance(cls) -> ImageLoaderManager  | None:
        """
        Get the instance of the ImageLoader
        """
        return cls.instance

    def load_image(self, image_path: str, widget: BaseImage, target_size: QSize = None):
        """
        Schedule the loading of a given image.

        :param image_path: Path to the image to load
        :param widget: Widget to put the pixmap on
        :param target_size: Target size of the image. If None, no scaling is done.
        """
        assert self.root_widget is not None, "Root Widget needs to exist."
        worker = ImageLoaderWorker(image_path, self.root_widget, widget, target_size)
        self.thread_pool.start(worker)
