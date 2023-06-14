from kivy.properties import ObjectProperty, ColorProperty
from kivy.uix.modalview import ModalView
from kivy.lang import Builder
import os
from typing import Union
from photo_lib.gui.root_widget_stub import RootWidgetStub


class FileCompareModal(ModalView):
    file_index_a: ObjectProperty(None)
    file_index_b: ObjectProperty(None)
    status_label = ObjectProperty(None)
    background_col = ColorProperty()

    root_widget: RootWidgetStub

    def __init__(self, root: RootWidgetStub, **kwargs):
        Builder.load_file(os.path.join(os.path.dirname(__file__), "file_compare_modal.kv"))
        super().__init__(**kwargs)
        self.root_widget = root
        self.bind(on_open=self.on_open_set_hint)
        self.update_status(success=None, message="   ")

    def on_open_set_hint(self, *args):
        self.file_index_a.hint_text = f"Enter Integer from 0 to {len(self.root_widget.compareWidgets) - 1}"
        self.file_index_b.hint_text = f"Enter Integer from 0 to {len(self.root_widget.compareWidgets) - 1}"

    def on_close_reset_status(self):
        self.update_status(success=None)

    def update_status(self, success: Union[bool, None], message: str = ""):
        self.status_label.text = message
        if success is None:
            self.background_col = [0.2, 0.2, 0.2, 1.0]
        elif success:
            self.background_col = [0.2, 0.5, 0.2, 1.0]
        else:
            self.background_col = [0.5, 0.2, 0.2, 1.0]

    def compare_files(self):
        # parse content
        a = self.file_index_a.text
        if a == "":
            self.update_status(success=None, message="Provide a valid Integer in base 10")
            return

        try:
            index_a = int(a)
        except ValueError:
            self.update_status(success=None, message="Provide a valid Integer in base 10")
            return

        b = self.file_index_b.text
        if b == "":
            self.update_status(success=None, message="Provide a valid Integer in base 10")
            return

        try:
            index_b = int(b)
        except ValueError:
            self.update_status(success=None, message="Provide a valid Integer in base 10")
            return

        if not 0 <= index_a < len(self.root_widget.compareWidgets):
            self.update_status(success=None, message="Index a is out of range")
            return

        if not 0 <= index_b <= len(self.root_widget.compareWidgets):
            self.update_status(success=None, message="Index b is out of range")
            return

        a_key = self.root_widget.compareWidgets[index_a].database_entry.key
        b_key = self.root_widget.compareWidgets[index_b].database_entry.key

        success, msg = self.root_widget.database.compare_files(a_key, b_key)
        self.update_status(success, message=msg)