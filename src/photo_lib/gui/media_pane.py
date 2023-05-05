from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from photo_lib.gui.image_container import ResizingImage
from photo_lib.gui.model import Model
from photo_lib.PhotoDatabase import DatabaseEntry, PhotoDb
from typing import Union


# Rotate Image
# void MyWidget::rotateLabel()
# {
#     QPixmap pixmap(*my_label->pixmap());
#     QMatrix rm;
#     rm.rotate(90);
#     pixmap = pixmap.transformed(rm);
#     my_label->setPixmap(pixmap);
# }

class MediaPane(QWidget):
    """
    This Widget holds a piece of media, and it's associated metadata.
    """
    # Communication and stuff
    model: Model
    dbe: DatabaseEntry
    layout: QVBoxLayout

    # Child Widgets, and associated attributes
    media: Union[ResizingImage, QMediaPlayer]
    pixmap: QPixmap = None
    original_name_lbl: QLabel
    original_path_lbl: QLabel
    tag_lbl: QLabel
    new_name_lbl: QLabel
    file_size_lbl: QLabel
    file_size: str = ""
    metadata_lbl: QLabel
    metadata: str = ""

    main_button: QPushButton
    delete_button: QPushButton
    change_tag_button: QPushButton

    min_width:int = 200
    min_height:int = 600

    def __init__(self, model: Model, entry: DatabaseEntry):
        super().__init__()
        self.model = model
        self.dbe = entry
        self.layout = QVBoxLayout()

        self.setMinimumWidth(self.min_width)

        self.setLayout(self.layout)

        # prepare the metadata
        self.metadata, self.file_size = self.model.process_metadata(self.dbe.metadata)

        # Assuming default for the moment and just assuming that we get a picture.
        file_path = self.model.pdb.path_from_datetime(dt_obj=self.dbe.datetime, file_name=self.dbe.new_name)
        self.media = ResizingImage(file_path=file_path)
        self.media.setFixedHeight(self.min_height)
        self.media.setFixedWidth(self.min_width)

        # creating all the necessary labels
        self.original_name_lbl = QLabel()
        self.original_name_lbl.setText(self.dbe.org_fname)
        self.original_name_lbl.setFixedHeight(20)
        self.original_name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.original_path_lbl = QLabel()
        self.original_path_lbl.setText(self.dbe.org_fpath)
        self.original_path_lbl.setFixedHeight(20)
        self.original_path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.tag_lbl = QLabel()
        self.tag_lbl.setText(self.dbe.naming_tag)
        self.tag_lbl.setFixedHeight(20)
        self.tag_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.new_name_lbl = QLabel()
        self.new_name_lbl.setText(self.dbe.new_name)
        self.new_name_lbl.setFixedHeight(20)
        self.new_name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_size_lbl = QLabel()
        self.file_size_lbl.setText(self.file_size)
        self.file_size_lbl.setFixedHeight(20)
        self.file_size_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.metadata_lbl = QLabel()
        self.metadata_lbl.setText(self.metadata)
        self.metadata_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Adding all the widgets.
        self.layout.addWidget(self.media)
        self.layout.addWidget(self.original_name_lbl)
        self.layout.addWidget(self.original_path_lbl)
        self.layout.addWidget(self.tag_lbl)
        self.layout.addWidget(self.new_name_lbl)
        self.layout.addWidget(self.file_size_lbl)
        self.layout.addWidget(self.metadata_lbl)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.media.setFixedWidth(self.width())
        # self.media.setScaledContents(True)




