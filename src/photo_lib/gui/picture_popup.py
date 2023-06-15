from kivy.properties import StringProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder
import os

# Import for kivy lang
from photo_lib.gui.image_button import ImageButton


picture_popup_loaded = False
if not picture_popup_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), "picture_popup.kv"))
    picture_popup_loaded = True


class PicturePopup(Popup):
    img_path = StringProperty("")

    def __init__(self):
        super().__init__()

    def open_and_set(self, path: str = ""):
        self.img_path = path
        self.open()