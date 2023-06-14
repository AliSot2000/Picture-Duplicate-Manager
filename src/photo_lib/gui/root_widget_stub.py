from kivy.uix.floatlayout import FloatLayout
from photo_lib.PhotoDatabase import PhotoDb, DatabaseEntry


class RootWidgetStub(FloatLayout):
    filenameModal = None
    errorModal = None
    db_selector_widget = None
    db_duplicate_location = None
    db_dup_proc_sel = None
    file_compare_modal = None
    image_popup = None

    dup_fp: str = None
    database: PhotoDb = None

    compareWidgets = []
    loaded_row: int = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


    def set_compareWidget_size(self, window, width, height, *args, **kwargs):
        raise NotImplemented("Stub file, no implementations here")

    def open_image_popup(self, path: str):
        raise NotImplemented("Stub file, no implementations here")

    def remove_scroller(self):
        raise NotImplemented("Stub file, no implementations here")

    def add_scroller(self):
        raise NotImplemented("Stub file, no implementations here")

    def load_db(self):
        raise NotImplemented("Stub file, no implementations here")

    def open_modal(self, caller):
        raise NotImplemented("Stub file, no implementations here")

    def load_entry(self):
        raise NotImplemented("Stub file, no implementations here")

    def auto_set_buttons(self):
        raise NotImplemented("Stub file, no implementations here")

    def clear_compare_panes(self):
        raise NotImplemented("Stub file, no implementations here")

    def store_load_entry(self):
        raise NotImplemented("Stub file, no implementations here")

    def clean_up(self):
        raise NotImplemented("Stub file, no implementations here")

    def removeCompareWidget(self, wdt):
        raise NotImplemented("Stub file, no implementations here")
