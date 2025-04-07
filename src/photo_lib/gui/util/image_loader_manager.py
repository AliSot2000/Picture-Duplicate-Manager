from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool

from photo_lib.gui.widgets.base_image import BaseImage
from .image_loader_worker import ImageLoaderWorker
from ...errors_and_warnings import ImplementationError


class ImageLoaderManager(QObject):
    instance = None  # Singleton
    __initialized: bool = False

    # TODO test if it works with imports here.

    # INFO: Might need to switch with string
    root_widget: Optional["BaseMainWindow"] = None

    def __new__(cls, root_widget: "BaseMainWindow"):
        """
        New Method Needed to Handle the proper workings with a singleton
        """
        # Check that we haven't created a class yet.
        if not hasattr(cls, 'instance') or cls.instance is None:
            cls.instance = super(ImageLoaderManager, cls).__new__(cls)
        return cls.instance

    def __init__(self, root_widget: "BaseMainWindow"):
        """
        Constructor to associate ThreadPool with the Manager
        """
        if not self.__initialized:
            print("Init called.")
            super().__init__()
            self.thread_pool = QThreadPool().globalInstance()
            self.root_widget = root_widget
        else:
            raise ImplementationError("Attempting to reinitialize an already initialized manager")


    @classmethod
    def get_instance(cls) -> ImageLoaderManager:
        """
        Get the instance of the ImageLoader
        """
        return cls.instance

    def load_image(self, image_path: str, widget: BaseImage):
        """
        Schedule the loading of a given image.

        :param image_path: Path to the image to load
        :param widget: Widget to put the pixmap on
        """
        assert self.root_widget is not None, "Root Widget needs to exist."
        worker = ImageLoaderWorker(image_path, self.root_widget, widget, widget.size())
        self.thread_pool.start(worker)
