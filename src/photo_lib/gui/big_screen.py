from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea
from photo_lib.gui.model import Model
from photo_lib.gui.carousell import Carousel
from photo_lib.gui.zoom_image import ZoomImage
from photo_lib.PhotoDatabase import BaseTileInfo, FullImportTableEntry


class BigScreen(QFrame):
    model: Model = None
    source_tile: BaseTileInfo = None
    full_info: FullImportTableEntry = None

    h_layout: QHBoxLayout
    main_image: ZoomImage

    metadata = QScrollArea
