from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.lang import Builder
import os
from photo_lib.gui.progress_info import ProgressInfo
from photo_lib.gui.root_widget_stub import RootWidgetStub


duplicate_detection_loaded = False
if not duplicate_detection_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), "duplicate_detection.kv"))
    duplicate_detection_loaded = True


class DuplicateDetection(Popup):
    root: RootWidgetStub

    def __init__(self, root_wdg: RootWidgetStub, **kwargs):
        self.root = root_wdg
        super().__init__(**kwargs)
        self.progressbar = ProgressInfo(self.root.load_entry)

    def hash_based(self, *args, **kwargs):
        self.root.database.delete_duplicates_table()
        self.root.database.duplicates_from_hash()
        self.dismiss()
        self.root.load_entry()

    def difpy_based(self, time_span: str, *args, **kwargs):
        self.root.database.delete_duplicates_table()
        pipe = self.root.database.img_ana_dup_search(level=time_span)
        self.dismiss()
        self.progressbar.pipe = pipe[1]
        Clock.schedule_interval(self.progressbar.suck_on_pipe, 1)
        self.progressbar.open()