from PyQt6.QtGui import QPixmap
import os
import warnings
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from photo_lib.gui.base_image import BaseImage


def load_store_img(img: BaseImage):
    """
    Load the image and store the resulting pixmap in the pixmap attribute of the base image.

    # Precondition: img.file_path is not None

    :param img: Image to load.
    :return bool: True if the image was loaded, False if not.
    """
    img.pixmap = QPixmap(img.file_path)

    if (ext := os.path.splitext(img.file_path)[1].lower()) not in [".png", ".jpg", ".jpeg", ".gif"]:
        warnings.warn(f"File must be an image. File Extension: {ext}")
    try:
        img.width_div_height = img.pixmap.width() / img.pixmap.height()
    except ZeroDivisionError:
        img.width_div_height = 1.0

    img.updateGeometry()
    if not img.pixmap.isNull() and img.isVisible():
        img.update()


@dataclass
class ImageFuture:
    future: Future
    image: BaseImage


class ImageLoader:
    def __init__(self, max_workers: int = 16):
        self.images = []
        self.tp = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = []

    def register(self, img: BaseImage):
        """
        Register a new image with the image loader. An Image may only be registered once.

        :raises ValueError: If the image is already registered.
        :param img: Image to register.
        :return:
        """
        if img in self.images:
            raise ValueError("Image already registered.")
        self.images.append(img)

    def unregister(self, img: BaseImage):
        """
        Unregister an image from the image loader.

        :raises ValueError: If the image is not registered.
        :param img: Image to unregister.
        :return:
        """
        if img not in self.images:
            raise ValueError("Image not registered.")

        for future in self.futures:
            if future.image == img:
                future.future.cancel()
                self.futures.remove(future)
                break

        self.images.remove(img)

    def check_futures(self):
        """
        Go through all Futures and remove the ones that are done.
        """
        new_futures = []
        old_count = len(self.futures)
        for future in self.futures:
            if not future.future.done():
                new_futures.append(future)

        new_count = len(new_futures)
        self.futures = new_futures
        print(f"Previous Count: {old_count}, Current Count: {new_count}")

    def check_load(self, img: BaseImage = None):
        """
        Go through all images and check if they need to be reloaded.
        """
        if img is not None:
            if img.file_path is not None and img.load_image_flag:
                self.load_image(img, False)
            return

        for img in self.images:
            img: BaseImage
            if img.file_path is not None and img.load_image_flag:
                self.load_image(img, False)

    def load_image(self, img: BaseImage, cancel_existing: bool = True):
        """
        Schedule image for loading
        .
        :param img: Image to load.
        :param cancel_existing: Cancel Existing future to speed up processing
        :return:
        """
        if img.file_path is None:
            return

        if cancel_existing:
            for fut in self.futures:
                if fut.image == img:
                    fut.future.cancel()

        future = self.tp.submit(load_store_img, img)
        self.futures.append(ImageFuture(future, img))
