from __future__ import annotations

from typing import Union

from photo_lib.gui.util.ImageLoader import ImageLoader
from photo_lib.gui.widgets.base_image import BaseImage

# Image loader for the base image class.
img_loader: Union[None, ImageLoader] = None


class LoadingBaseImage(BaseImage):
    def __init__(self, file_path: str = None):
        super().__init__()
        global img_loader

        if img_loader is None:
            img_loader = ImageLoader()

        img_loader.register(self)
        self.file_path = file_path

    def load_image(self):
        """
        Schedule the image to be loaded with the image loader
        """
        global img_loader
        # self.pixmap = None clearing if picture nees to be checked more precisely
        img_loader.load_image(self)
        img_loader.check_futures()

    def deleteLater(self):
        global img_loader
        img_loader.unregister(self)
        super().deleteLater()
        print(f"DEBUG: Deleted Later {self}")
