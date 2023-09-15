from PyQt6.QtGui import QPixmap, QPainter, QFont
from photo_lib.gui.base_image import BaseImage
from photo_lib.gui.ImageLoader import ImageLoader
from typing import Union


# Image loader for the base image class.
img_loader: Union[None, ImageLoader] = None


class LoadingBaseImage(BaseImage):
    def __init__(self):
        super().__init__()
        global img_loader

        if img_loader is None:
            img_loader = ImageLoader()

        img_loader.register(self)

    def _load_image(self):
        """
        Schedule the image to be loaded with the image loader
        """
        global img_loader
        img_loader.load_image(self)

    def __del__(self):
        global img_loader
        img_loader.unregister(self)
