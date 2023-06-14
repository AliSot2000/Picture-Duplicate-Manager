from kivy.properties import StringProperty, ObjectProperty, ColorProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder
import os
from photo_lib.gui.root_widget_stub import RootWidgetStub

class DatabaseSelector(Popup):
    fc = ObjectProperty(None)

    compareFloat: RootWidgetStub

    def __init__(self, comp_flt: RootWidgetStub, **kwargs):
        Builder.load_file(os.path.join(os.path.dirname(__file__), "database_selector.kv"))
        super().__init__(**kwargs)
        self.compareFloat = comp_flt
        self.bind(on_dismiss=self.try_close)
        self.bind(on_open=self.hide_scroll)

    def hide_scroll(self, *args, **kwargs):
        self.compareFloat.remove_scroller()
        self.compareFloat.clear_compare_panes()

    def try_close(self, *args, **kwargs):
        self.compareFloat.add_scroller()
        if self.compareFloat.dup_fp is None:
            self.open()

    def apply_db(self):
        if os.path.exists(os.path.join(self.fc.path, ".photos.db")):
            self.compareFloat.dup_fp = self.fc.path
            self.compareFloat.load_db()
            self.dismiss()
        else:
            self.ids.status.text = "No .photos.db file present. This is not a PhotoLibrary"