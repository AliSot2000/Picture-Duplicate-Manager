import time
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, ObjectProperty, ColorProperty
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
import os
import datetime
from photo_lib.metadataagregator import key_lookup_dir, MetadataAggregator
from photo_lib.PhotoDatabase import PhotoDb, DatabaseEntry
from kivy.uix.label import Label
import traceback
from sqlite3 import Connection
from typing import Union
from kivy.config import Config
from gestures4kivy import CommonGestures
from photo_lib.gui.scroll_label import ScrollLabel
from photo_lib.gui.database_selector import DatabaseSelector
from photo_lib.gui.root_widget_stub import RootWidgetStub
from photo_lib.gui.file_compare_modal import FileCompareModal
from photo_lib.gui.picture_popup import PicturePopup
from photo_lib.gui.progress_info import ProgressInfo
from photo_lib.gui.duplicate_detection import DuplicateDetection
from photo_lib.gui.duplicate_location import DuplicateLocation
from photo_lib.gui.error_popup import ErrorPopup
from photo_lib.gui.set_date_modal import SetDateModal
from photo_lib.gui.metadata_scroll_label import MetadataScrollLabel
from photo_lib.gui.path_scroll_label import PathScrollLabel
from photo_lib.gui.compare_pane import ComparePane
from photo_lib.gui.my_grid import MyGrid
from photo_lib.gui.compare_scroller import CompareScroller


class RootWidget(RootWidgetStub):
    filenameModal = None
    errorModal = None
    db_selector_widget = None
    db_duplicate_location = None
    db_dup_proc_sel = None
    file_compare_modal = None
    image_popup = None

    dup_fp: str = None
    database: PhotoDb = None

    cps: CompareScroller
    compareWidgets = []
    loaded_row: int = None

    def __init__(self, fp: str = None, **kwargs):
        super(RootWidget, self).__init__(**kwargs)
        self.dup_fp = fp

        self.errorModal = ErrorPopup()
        self.filenameModal = SetDateModal(self, self.errorModal)
        self.db_selector_widget = DatabaseSelector(self)
        self.cps = CompareScroller()
        self.db_dup_proc_sel = DuplicateDetection(root_wdg=self)
        self.db_duplicate_location = DuplicateLocation(root_ref=self, proc_select=self.db_dup_proc_sel)
        self.file_compare_modal = FileCompareModal(root=self)
        self.image_popup = PicturePopup()
        Window.bind(on_resize=self.set_compareWidget_size)
        self.add_scroller()

        if self.dup_fp is None:
            self.db_selector_widget.open()

    def set_compareWidget_size(self, window, width, height, *args, **kwargs):
        if len(self.compareWidgets) == 0:
            return
        widget_width = 400 if (width / len(self.compareWidgets)) < 400 else width / len(self.compareWidgets)

        for compareWidget in self.compareWidgets:
            compareWidget: ComparePane
            compareWidget.width = widget_width

    def open_image_popup(self, path: str):
        self.image_popup.open_and_set(path)

    def remove_scroller(self):
        self.remove_widget(self.cps)

    def add_scroller(self):
        self.add_widget(self.cps, index=2)

    def load_db(self):
        self.database = PhotoDb(root_dir=self.dup_fp)
        # mda = MetadataAggregator(exiftool_path="/home/alisot2000/Documents/01_ReposNCode/exiftool/exiftool")
        mda = MetadataAggregator(exiftool_path="/usr/bin/exiftool")
        self.database.mda = mda
        if self.database.duplicate_table_exists():
            self.db_duplicate_location.open()
        else:
            self.db_dup_proc_sel.open()

    def open_modal(self, caller):
        self.filenameModal.caller = caller
        self.filenameModal.open()

    def load_entry(self):
        success, results, row_id = self.database.get_duplicate_entry()

        # table empty
        if not success:

            # clear table and open selector again
            self.database.delete_duplicates_table()
            self.db_selector_widget.open()
            return

        for entry in results:
            if entry is not None:
                entry: DatabaseEntry
                cw = ComparePane(db=entry, pictureLib=self.database)
                self.compareWidgets.append(cw)
                self.cps.flexbox.add_widget(cw)

        # compare the files
        all_identical = True
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if results[i] is not None and results[j] is not None:
                    suc, msg = self.database.compare_files(results[i].key, results[j].key)
                    all_identical = all_identical and suc

        if all_identical:
            self.cps.background_col = [0.2, 0.5, 0.2, 1.0]
        else:
            self.cps.background_col = [0.5, 0.2, 0.2, 1.0]

        # compare the filenames
        identical_names = True
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if results[i] is not None and results[j] is not None:
                    identical_names = identical_names and results[i].org_fname.lower() == results[j].org_fname.lower()

        if identical_names:
            for c in self.compareWidgets:
                if c is not None:
                    c: ComparePane
                    c.l_ofname.background_col = [0.2, 0.5, 0.2, 1.0]
        else:
            for c in self.compareWidgets:
                if c is not None:
                    c: ComparePane
                    c.l_ofname.background_col = [0.5, 0.2, 0.2, 1.0]

        identical_datetime = True
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if results[i] is not None and results[j] is not None:
                    identical_datetime = identical_datetime and results[i].datetime == results[j].datetime

        if identical_datetime:
            for c in self.compareWidgets:
                if c is not None:
                    c: ComparePane
                    c.l_new_name.background_col = [0.2, 0.5, 0.2, 1.0]
        else:
            for c in self.compareWidgets:
                if c is not None:
                    c: ComparePane
                    c.l_new_name.background_col = [0.5, 0.2, 0.2, 1.0]

        identical_file_size = True
        difference = 0
        count = 0
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if results[i] is not None and results[j] is not None:
                    identical_file_size = identical_file_size and \
                                         results[i].metadata.get("File:FileSize") \
                                         == results[j].metadata.get("File:FileSize")
                    difference += (results[i].metadata.get("File:FileSize")
                                   - results[j].metadata.get("File:FileSize"))**2
                    count += 1

        if count > 0:
            print(f"Average Difference {(difference ** 0.5) / count}")
            difference = (difference ** 0.5)/count

        if identical_file_size:
            for c in self.compareWidgets:
                c: ComparePane
                c.l_file_size.background_col = [0.2, 0.5, 0.2, 1.0]
        else:
            for c in self.compareWidgets:
                c: ComparePane
                if difference < 1000:
                    c.l_file_size.background_col = [0.5, 0.5, 0.2, 1.0]
                else:
                    c.l_file_size.background_col = [0.5, 0.2, 0.2, 1.0]

        # auto set main and delete
        self.auto_set_buttons()

        self.ids.status.text = f"Number of duplicates in database: {self.database.get_duplicate_table_size()}"
        self.loaded_row = row_id
        wd = self.get_root_window()
        self.set_compareWidget_size(wd, width=wd.width, height=wd.height)

    def auto_set_buttons(self):
        if len(self.compareWidgets) == 2:
            widget_a: ComparePane = self.compareWidgets[0]
            widget_b: ComparePane = self.compareWidgets[1]
            fsize_a_type = type(widget_a.database_entry.metadata.get("File:FileSize"))
            fsize_b_type = type(widget_b.database_entry.metadata.get("File:FileSize"))
            assert fsize_a_type is int, f"FileSize of a not of expected type int but {fsize_a_type}"
            assert fsize_b_type is int, f"FileSize of b not of expected type int but {fsize_b_type}"

            # Two files differing only in file size
            if widget_a.database_entry.metadata.get("File:FileSize")\
                    > widget_b.database_entry.metadata.get("File:FileSize"):
                widget_a.obuton.state = "down"
                widget_a.set_delete_on_main()
                widget_b.mark_delete_button.state = "down"
                widget_b.set_button_color()
            elif widget_a.database_entry.metadata.get("File:FileSize")\
                    < widget_b.database_entry.metadata.get("File:FileSize"):
                widget_b.obuton.state = "down"
                widget_b.set_delete_on_main()
                widget_a.mark_delete_button.state = "down"
                widget_a.set_button_color()

            # Two files identical but different dates.
            elif widget_a.database_entry.metadata.get("File:FileSize")\
                    == widget_b.database_entry.metadata.get("File:FileSize") and \
                    widget_a.database_entry.datetime < widget_b.database_entry.datetime:
                widget_a.obuton.state = "down"
                widget_a.set_delete_on_main()
                widget_b.mark_delete_button.state = "down"
                widget_b.set_button_color()

            elif widget_a.database_entry.metadata.get("File:FileSize")\
                    == widget_b.database_entry.metadata.get("File:FileSize") and \
                    widget_a.database_entry.datetime > widget_b.database_entry.datetime:
                widget_b.obuton.state = "down"
                widget_b.set_delete_on_main()
                widget_a.mark_delete_button.state = "down"
                widget_a.set_button_color()
    def clear_compare_panes(self):
        for p in self.compareWidgets:
            self.cps.flexbox.remove_widget(p)

        self.compareWidgets = []

    def store_load_entry(self):
        if len(self.compareWidgets) == 0:
            self.load_entry()

        main_entry: ComparePane = None
        for_duplicates = []

        for entry in self.compareWidgets:
            if entry.obuton.state == "down":
                main_entry = entry
            if entry.mark_delete_button.state == "down":
                for_duplicates.append(entry)

        # remove all ComparePanes and repopulate
        if main_entry is None:
            print("Main Entry none, cleaning up")
            self.clean_up()
            return

        main_key = main_entry.database_entry.key
        print(f"Keeping: {main_entry.new_name}")

        for marks in for_duplicates:
            print(f"Marking: {marks.new_name}")
            marks: ComparePane
            self.database.mark_duplicate(successor=main_key, duplicate_image_id=marks.database_entry.key, delete=False)

        self.clean_up()

    def clean_up(self):
        self.clear_compare_panes()
        self.database.delete_duplicate_row(self.loaded_row)
        self.loaded_row = None
        self.load_entry()

    def removeCompareWidget(self, wdg: ComparePane):
        self.float_sibling.cps.flexbox.remove_widget(wdg)
        self.float_sibling.compareWidgets.remove(wdg)

        for comparePane in self.compareWidgets:
            comparePane.image_count = len(self.compareWidgets)


class PictureLibrary(App):
    def build(self):
        mf = RootWidget()
        return mf


if __name__ == "__main__":
    Config.set('input', 'mouse', 'mouse, disable_multitouch')
    PictureLibrary().run()
