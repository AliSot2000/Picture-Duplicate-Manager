import math
import os
import sys
import warnings
from typing import Union

from PyQt6.QtCore import QRunnable, QObject, QThreadPool, pyqtSlot, QSize, QRect, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPaintEvent, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QScrollArea, QGridLayout
from PyQt6.QtWidgets import QFrame, QMainWindow

use_base = True


"""
INFO: You need to restructure the system. There should be a manager in the main thread responsible for creating the images.
"""

class SignalEmitter(QObject):
    finished = pyqtSignal()



class ImageLoaderManager(QObject):
    instance = None  # Singleton

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()

    @staticmethod
    def get_instance():
        if ImageLoaderManager.instance is None:
            ImageLoaderManager.instance = ImageLoaderManager()
        return ImageLoaderManager.instance

    def load_image(self, image_path: str, widget: "BaseImage"):
        worker = ImageLoaderWorker(image_path, widget, widget.size())
        self.thread_pool.start(worker)


class BaseImage(QFrame):
    __pixmap = None

    __file_path: str = None
    width_div_height: float = 1.0

    filler_color = Qt.GlobalColor.darkGray

    manager: ImageLoaderManager

    def __init__(self, manager: ImageLoaderManager, file_path: str = None):
        super().__init__()
        self.manager = manager
        self.file_path = file_path

    @property
    def pixmap(self):
        return self.__pixmap

    @pixmap.setter
    def pixmap(self, value: QPixmap):
        self.__pixmap = value


    @pyqtSlot()
    def pixmap_changed(self):
        self.repaint()

    @property
    def file_path(self):
        """
        Get the current file path of the image
        :return:
        """
        return self.__file_path

    @file_path.setter
    def file_path(self, value: Union[None, str]):
        """
        Set the file path of the image. This if the image is supposed to be loaded it will be loaded as well.
        The filepath can also be left empty to have a template.
        :param value:
        :return:
        """
        if value == self.__file_path:
            return

        # The file path is different, and we need to load the image
        self.__file_path = value
        if value is not None:
            self.load_image()
        else:
            self.repaint()

    def perform_load_image(self):
        """
        Fetches the file path, and loads it into ram. This is a blocking operation.
        """
        assert self.file_path is not None, "File path must be set before loading image."
        self.pixmap = QPixmap(self.file_path)

        if (ext := os.path.splitext(self.file_path)[1].lower()) not in [".png", ".jpg", ".jpeg", ".gif"]:
            warnings.warn(f"File must be an image. File Extension: {ext}")
        try:
            self.width_div_height = self.pixmap.width() / self.pixmap.height()
        except ZeroDivisionError:
            self.width_div_height = 1.0

        self.updateGeometry()
        if not self.pixmap.isNull() and self.isVisible():
            self.update()

    def load_image(self):
        """
        Base Implementation of loading image into RAM (might use multithreading in different instance).

        :return:
        """
        if use_base:
            self.perform_load_image()
        else:
            assert self.file_path is not None, "File path must be set before loading image."

            if (ext := os.path.splitext(self.file_path)[1].lower()) not in [".png", ".jpg", ".jpeg", ".gif"]:
                warnings.warn(f"File must be an image. File Extension: {ext}")

            self.manager.load_image(self.file_path, self)

    def unload_image(self):
        """
        Removes the image from ram. The widget will draw a dark gray rectangle.
        :return:
        """
        self.pixmap = None
        self.updateGeometry()
        if self.isVisible():
            self.update()

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
        if self.pixmap is None or self.pixmap.isNull():
            self.empty_pixmap_painter()
            return

        # Draw when image is successfully loaded n stuff.
        if self.size() == self.pixmap.size():
            r = self.rect()
        else:
            r = QRect(QPoint(),
                      self.pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio))
            r.moveCenter(self.rect().center())
        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)

        # rec = self.rect()
        # rec.setWidth(rec.width() - 1)
        # rec.setHeight(rec.height() - 1)
        # qp.drawRect(rec)

    def empty_pixmap_painter(self):
        """
        In case there's no image loaded, paint a message on the widget.
        :return:
        """
        # Create a filler shape to indicate where the image is supposed to be.
        pt = QPainter(self)
        pt.fillRect(self.rect(), self.filler_color)

        # Draw the text in the middle of the widget
        if self.file_path is not None:
            text = f"Couldn't load {os.path.basename(self.file_path)}"
        else:
            text = "Empty file path"
        # Use defaults for the font size
        font = QFont("Arial", 12, QFont.Weight.Bold)
        pt.setFont(font)
        text_rect = pt.boundingRect(self.rect(), 0, text)
        text_position = self.rect().center() - text_rect.center()
        pt.drawText(text_position, text)

        # Attempt to reload the image.
        if self.file_path is not None:
            self.load_image()


class ImageLoaderWorker(QRunnable):
    def __init__(self, image_path: str, tgt_widget: BaseImage, size: QSize):
        super().__init__()
        self.image_path = image_path
        self.target_widget = tgt_widget
        self.size = size

        self.emitter = SignalEmitter()

    def run(self):
        if os.path.exists(self.image_path):
            image = QImage(self.image_path)  # Load image safely
            pixmap = QPixmap.fromImage(image)  # Convert to pixmap
            scaled_pm = pixmap.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio)

            try:
                aspect_ratio = pixmap.width() / pixmap.height()
            except ZeroDivisionError:
                aspect_ratio = 1.0

            self.target_widget.pixmap = scaled_pm
            self.target_widget.width_div_height = aspect_ratio

            # Trigger repaint
            self.emitter.finished.connect(self.target_widget.pixmap_changed)
            self.emitter.finished.emit()
            self.emitter.finished.disconnect(self.target_widget.pixmap_changed)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.reload_state = True

        self.background_widget = QWidget()
        self.top_layout = QVBoxLayout()
        self.background_widget.setLayout(self.top_layout)

        # trigger button
        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.button_update)
        self.top_layout.addWidget(self.reload_button)

        # big_scroll_view
        self.sc = QScrollArea()
        self.top_layout.addWidget(self.sc)

        # Inner background Widget
        self.inner_background_widget = QWidget()
        self.sc.setWidget(self.inner_background_widget)

        # Add inner widget layout
        self.inner_layout = QGridLayout()
        self.inner_background_widget.setLayout(self.inner_layout)

        self.paths = []
        self.inner_widgets = []
        manager = ImageLoaderManager()

        root_path = "/home/alisot2000/Desktop/test-dirs/dir_b/"
        cos = 5
        rows = math.ceil(len(os.listdir(root_path)) / cos)
        img_size = 200

        for i, element in enumerate(os.listdir(root_path)):
            print(i, element)
            p = os.path.join(root_path, element)
            self.paths.append(p)

            widget = BaseImage(manager=manager, file_path=p)
            widget.setFixedSize(QSize(img_size, img_size))
            self.inner_widgets.append(widget)

            row = i // cos
            col = i % cos

            self.inner_layout.addWidget(widget, row, col)

        self.inner_background_widget.setFixedSize(QSize(cos * img_size + (cos + 1) * 10,
                                                        rows * img_size + (rows + 1) * 10))

        self.setCentralWidget(self.background_widget)
        print("INIT DONE")

    def button_update(self):
        """
        Update the widgets
        """
        for path, widget in zip(self.paths, self.inner_widgets):
            p = path if self.reload_state else None
            print(p)
            widget.pixmap = None
            widget.file_path = p

        self.reload_state = not self.reload_state


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
