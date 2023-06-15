from kivy.properties import ObjectProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder
import os
from photo_lib.gui.root_widget_stub import RootWidgetStub


duplicate_location_loaded = False
if not duplicate_location_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), "duplicate_location.kv"))
    duplicate_location_loaded = True


class DuplicateLocation(Popup):
    my_float_ref: RootWidgetStub
    reuse_button = ObjectProperty(None)
    recompute_button = ObjectProperty(None)
    proc_sel = None

    def __init__(self, root_ref: RootWidgetStub, proc_select, **kwargs):
        super().__init__(**kwargs)
        self.my_float_ref = root_ref
        self.auto_dismiss = False
        self.reuse_button.bind(on_press=self.reuse)
        self.recompute_button.bind(on_press=self.recmp)
        self.proc_sel = proc_select

    def reuse(self, *args, **kwargs):
        self.dismiss()
        self.my_float_ref.load_entry()

    def recmp(self, *args, **kwargs):
        self.dismiss()
        self.proc_sel.open()