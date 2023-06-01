from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QFrame, QSizePolicy, QHBoxLayout
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtGui import QPixmap, QFontMetrics
from PyQt6.QtCore import Qt

from photo_lib.gui.clickable_image import ClickableImage
from photo_lib.gui.text_scroll_area import TextScroller
from photo_lib.gui.model import Model
from photo_lib.PhotoDatabase import DatabaseEntry, PhotoDb
from typing import Union, Callable


# Rotate Image
# void MyWidget::rotateLabel()
# {
#     QPixmap pixmap(*my_label->pixmap());
#     QMatrix rm;
#     rm.rotate(90);
#     pixmap = pixmap.transformed(rm);
#     my_label->setPixmap(pixmap);
# }

def bake_attribute(name: str, func: Callable):
    def baked_attribute_func(*args, **kwargs):
        return func(*args, name=name,**kwargs)

    return baked_attribute_func


class MediaPane(QLabel):
    """
    This Widget holds a piece of media, and it's associated metadata.
    """
    # Communication and stuff
    model: Model
    dbe: DatabaseEntry
    layout: QVBoxLayout

    # Child Widgets, and associated attributes
    media: Union[ClickableImage, QMediaPlayer]
    pixmap: QPixmap = None
    original_name_lbl: TextScroller
    original_path_lbl: TextScroller
    tag_lbl: QLabel
    new_name_lbl: QLabel
    file_size_lbl: QLabel
    file_size: str = ""
    metadata_lbl: TextScroller
    metadata: str = ""

    button_widget: QWidget
    button_layout: QHBoxLayout
    main_button: QPushButton
    delete_button: QPushButton
    change_tag_button: QPushButton
    remove_media_button: QPushButton

    min_width:int = 300
    max_height:int = 540

    max_needed_width: int = 0

    share_scroll: Callable

    def __init__(self, model: Model, entry: DatabaseEntry, share_scroll: Callable):
        super().__init__()
        self.setMinimumHeight(860)
        self.share_scroll = share_scroll
        self.model = model
        self.dbe = entry
        self.layout = QVBoxLayout()

        self.setMinimumWidth(self.min_width)
        self.layout.setContentsMargins(0, 0, 0, 0)
        # self.setStyleSheet("background-color: #333333;")

        self.setLayout(self.layout)

        # prepare the metadata
        self.metadata, self.file_size = self.model.process_metadata(self.dbe.metadata)

        # Assuming default for the moment and just assuming that we get a picture.
        file_path = self.model.pdb.path_from_datetime(dt_obj=self.dbe.datetime, file_name=self.dbe.new_name)
        self.media = ClickableImage(file_path=file_path)

        # creating all the necessary labels
        self.original_name_lbl = TextScroller()
        self.original_name_lbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.original_name_lbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.original_name_lbl.setFixedHeight(30)
        self.original_name_lbl.setFrameShape(QFrame.Shape.NoFrame)
        self.original_name_lbl.set_text(self.dbe.org_fname)
        self.original_name_lbl.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # self.original_name_lbl.setStyleSheet("border: 1px solid red;")
        # Using Decorator to set the attribute fix and not having to mess around with the text scroller having to
        # know its attribute name in the parent.
        self.original_name_lbl.share_scroll = bake_attribute("original_name_lbl", self.share_scroll)
        self.max_needed_width = max(self.max_needed_width, self.original_name_lbl.text_label.width())


        self.original_path_lbl = TextScroller()
        self.original_path_lbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.original_path_lbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.original_path_lbl.setFixedHeight(30)
        self.original_path_lbl.setFrameShape(QFrame.Shape.NoFrame)
        self.original_path_lbl.set_text(self.dbe.org_fpath)
        self.original_path_lbl.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # self.original_path_lbl.setStyleSheet("border: 1px solid red;")
        # Dito self.original_name_lbl
        self.original_path_lbl.share_scroll = bake_attribute("original_path_lbl", self.share_scroll)
        self.max_needed_width = max(self.max_needed_width, self.original_path_lbl.text_label.width())

        # Buttons
        self.button_widget = QWidget()
        self.button_widget.setFixedHeight(30)
        self.button_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_widget.setLayout(self.button_layout)

        self.main_button = QPushButton("Original")
        self.main_button.setMinimumHeight(20)
        self.main_button.setCheckable(True)
        self.main_button.setStyleSheet("background-color: gray;")
        self.main_button.toggled.connect(self.update_main_color)

        self.delete_button = QPushButton("Keep")
        self.delete_button.setMinimumHeight(20)
        self.delete_button.setCheckable(True)
        self.delete_button.setStyleSheet("background-color: green;")
        self.delete_button.toggled.connect(self.update_delete_text)

        self.change_tag_button = QPushButton("Change Tag")
        self.change_tag_button.setMinimumWidth(self.change_tag_button.fontMetrics().boundingRect("Change Tag").width() + 10)
        self.change_tag_button.setMinimumHeight(20)

        self.remove_media_button = QPushButton("X")
        self.remove_media_button.setMinimumHeight(20)
        self.remove_media_button.setFixedWidth(20)

        self.button_layout.addWidget(self.main_button)
        self.button_layout.addWidget(self.delete_button)
        self.button_layout.addWidget(self.change_tag_button)
        self.button_layout.addWidget(self.remove_media_button)

        self.tag_lbl = QLabel()
        self.tag_lbl.setFixedHeight(30)
        self.tag_lbl.setText(self.dbe.naming_tag)
        self.tag_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.new_name_lbl = QLabel()
        self.new_name_lbl.setFixedHeight(30)
        self.new_name_lbl.setText(self.dbe.new_name)
        self.new_name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.file_size_lbl = QLabel()
        self.file_size_lbl.setFixedHeight(30)
        self.file_size_lbl.setText(self.file_size)
        self.file_size_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.metadata_lbl = TextScroller()
        self.metadata_lbl.set_text(self.metadata)
        self.metadata_lbl.setFrameShape(QFrame.Shape.NoFrame)
        self.metadata_lbl.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Dito self.original_name_lbl
        self.metadata_lbl.share_scroll = bake_attribute("metadata_lbl", self.share_scroll)
        self.metadata_lbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.metadata_lbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.max_needed_width = max(self.max_needed_width, self.metadata_lbl.text_label.width())

        # Adding all the widgets.
        self.layout.addWidget(self.media)
        self.layout.addWidget(self.original_name_lbl)
        self.layout.addWidget(self.original_path_lbl)
        self.layout.addWidget(self.button_widget)
        self.layout.addWidget(self.tag_lbl)
        self.layout.addWidget(self.new_name_lbl)
        self.layout.addWidget(self.file_size_lbl)
        self.layout.addWidget(self.metadata_lbl)

    def resizeEvent(self, event):
        """
        Pass Size to the Picture
        :param event:
        :return:
        """
        super().resizeEvent(event)
        self.media.setFixedWidth(self.width())
        self.media.setFixedHeight(min(self.max_height, int(self.width() / self.media.width_div_height)))
        # print(self.metadata_lbl.size())
        # self.media.setScaledContents(True)

    def update_delete_text(self):
        """
        Updating the Text of the Delete or Keep button
        :return:
        """
        if self.delete_button.isChecked():
            self.delete_button.setText("Delete")
            self.delete_button.setStyleSheet("background-color: red;")
            self.main_button.setChecked(False)
        else:
            self.delete_button.setText("Keep")
            self.delete_button.setStyleSheet("background-color: green;")

    def update_main_color(self):
        """
        Updating the Color of the Main Button
        :return:
        """
        if self.main_button.isChecked():
            self.main_button.setStyleSheet("background-color: blue;")
        else:
            self.main_button.setStyleSheet("background-color: gray;")

    def update_file_naming(self):
        self.tag_lbl.setText(self.dbe.naming_tag)
        self.new_name_lbl.setText(self.dbe.new_name)




