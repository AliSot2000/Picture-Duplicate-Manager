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

# TODO Nice Scroll Sync
# TODO Scroll Horizontal


class MetadataScrollLabel(ScrollView):
    """
    Specific instance of ScrollLabel which has a callback which updates the scroll in every instance of
    MetadataScrollLabel
    """
    lbl = ObjectProperty(None)
    text = StringProperty("example content")
    last_scroll_x = 0.0
    last_scroll_y = 1.0

    def __init__(self, **kwargs):
        super(MetadataScrollLabel, self).__init__(**kwargs)
        self.bind(on_scroll_stop=self.update_compare_pane)
        # self.bind(on_scroll_start=self.update_compare_pane)

    def update_compare_pane(self, *args, **kwargs):
        if (self.last_scroll_x != self.scroll_x) or (self.last_scroll_y != self.scroll_y):
            self.parent.parent.update_scroll_metadata(x=self.scroll_x, y=self.scroll_y, caller=self)
            self.last_scroll_x = self.scroll_x
            self.last_scroll_y = self.scroll_y


class PathScrollLabel(ScrollView):
    """
    Specific instance of ScrollLabel which has a callback which updates the scroll in every instance of PathScrollLabel
    """
    lbl = ObjectProperty(None)
    text = StringProperty("example content")
    last_scroll_x = 0.0
    last_scroll_y = 1.0

    def __init__(self, **kwargs):
        super(PathScrollLabel, self).__init__(**kwargs)
        self.bind(on_scroll_stop=self.update_compare_pane)

    def update_compare_pane(self, *args, **kwargs):
        if (self.last_scroll_x != self.scroll_x) or (self.last_scroll_y != self.scroll_y):
            self.parent.parent.update_scroll_path(x=self.scroll_x, y=self.scroll_y, caller=self)
            self.last_scroll_x = self.scroll_x
            self.last_scroll_y = self.scroll_y


class ComparePane(Widget):
    image = ObjectProperty(None)
    dump = ObjectProperty(None)
    rename_file = ObjectProperty(None)
    l_ofname = ObjectProperty(None)
    l_ofpath = ObjectProperty(None)
    l_naming_tag = ObjectProperty(None)
    l_new_name = ObjectProperty(None)
    l_metadata = ObjectProperty(None)
    l_file_size = ObjectProperty
    obuton = ObjectProperty(None)
    mark_delete_button = ObjectProperty(None)

    database_entry: DatabaseEntry = None

    image_path = StringProperty("")
    org_fname = StringProperty("")
    org_fpath = StringProperty("")
    naming_tag = StringProperty("")
    new_name = StringProperty("")
    metadata = StringProperty("")
    file_size = StringProperty("")

    pl: PhotoDb
    __image_count = 1

    def __init__(self, db: DatabaseEntry, pictureLib: PhotoDb, **kwargs):
        super(ComparePane, self).__init__(**kwargs)
        self.database_entry = db
        self.pl = pictureLib
        self.load_from_database_entry()

    def open_image_popup(self):
        self.parent.open_image_popup(self.image_path)

    def load_from_database_entry(self):
        self.image_path = self.pl.path_from_datetime(self.database_entry.datetime, self.database_entry.new_name)

        # check trash
        if not os.path.exists(self.image_path):
            self.image_path = self.pl.trash_path(self.database_entry.new_name)

        # check thumbnails
        if not os.path.exists(self.image_path):
            self.image_path = self.pl.thumbnail_name(os.path.splitext(self.database_entry.new_name)[1],
                                                     self.database_entry.key)

        self.org_fname = self.database_entry.org_fname
        self.org_fpath = self.database_entry.org_fpath
        self.naming_tag = self.database_entry.naming_tag
        self.new_name = self.database_entry.new_name
        self.generate_metadata()

    def generate_metadata(self):
        keys = self.database_entry.metadata.keys()
        key_list = list(keys)
        key_list.sort()

        result = f"Number of Attributes: {len(key_list)}\n"

        for key in key_list:
            result += f"{key}: {self.database_entry.metadata.get(key)}\n"
            if key == "File:FileSize":
                self.file_size = f"File Size: {int(self.database_entry.metadata.get(key)):,}".replace(",", "'")

        self.metadata = result

    def update_scroll_metadata(self, *args, x: float, y: float, caller: MetadataScrollLabel, **kwargs):
        self.parent.update_scroll_meta(x=x, y=y, caller=caller)

    def update_scroll_path(self, *args, x: float, caller: PathScrollLabel, **kwargs):
        self.parent.update_scroll_path(x=x, caller=caller)

    def open_modal(self):
        self.parent.parent.parent.parent.open_modal(caller=self)

    def set_button_color(self):
        """
        Delete Button set color to red if set to down, otherwise green
        :return:
        """
        if self.mark_delete_button.state == "down":
            self.mark_delete_button.background_color = 1.0, 0.0, 0.0
            self.mark_delete_button.text = "to trash"
            self.obuton.state = "normal"
        else:
            self.mark_delete_button.background_color = 0.2, 0.6, 0.2
            self.mark_delete_button.text = "keep"

    def set_delete_on_main(self):
        """
        Cannot have 'Delete button' set as well as main.
        :return:
        """
        self.mark_delete_button.state = "normal"
        self.set_button_color()


class MyGrid(GridLayout):
    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))

    def update_scroll_meta(self, *args, x: float, y: float, caller: MetadataScrollLabel, **kwargs):
        """
        Updates the scroll value of all meta_data labels to the same value
        :param args: just for safety
        :param x: new target x
        :param y: new target y
        :param kwargs: just for safety
        :return:
        """
        for c in self.children:
            c: ComparePane
            if c.l_metadata == caller:
                continue
            c.l_metadata.scroll_x = x
            c.l_metadata.scroll_y = y
            c.l_metadata.last_scroll_x = x
            c.l_metadata.last_scroll_y = y

    def update_scroll_path(self, *args, x: float, caller: PathScrollLabel,  **kwargs):
        for c in self.children:
            c: ComparePane
            if c == caller:
                continue
            c.l_ofpath.scroll_x = x
            c.l_ofpath.last_scroll_x = x

    def open_image_popup(self, path: str):
        self.parent.parent.parent.open_image_popup(path)


class FlexibleBox(BoxLayout):
    def __init__(self, **kwargs):
        super(FlexibleBox, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))


class CompareScroller(ScrollView):
    flexbox = ObjectProperty(None)
    background_col = ColorProperty()


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


class CustomDateTag(TextInput):
    def __init__(self, **kwargs):
        super(CustomDateTag, self).__init__(**kwargs)
        self.bind(on_text_validate=self.parent_update)

    def parent_update(self, *args, **kwargs):
        self.parent.parent.text_content()


class SetDateModal(ModalView):
    customDateTag = ObjectProperty(None)
    customDateTimeInput = ObjectProperty(None)

    caller: ComparePane = None
    float_sibling: RootWidget
    # error_popup: NewDatetimeError

    def __init__(self, float_sibling, error_popup, **kwargs):
        super(SetDateModal, self).__init__(**kwargs)
        self.float_sibling = float_sibling
        self.error_popup = error_popup
        self.bind(on_dismiss=self.close)
        self.bind(on_open=self.load_current_tag)

    def text_content(self, *args, **kwargs):
        """
        Sets the Custom Datetime input to enabled when the sourceTag is Custom
        :param args: just for safety
        :param kwargs: just for safety
        :return:
        """
        text: str = self.customDateTag.text
        text = text.strip().capitalize()
        if text == "Custom":
            self.customDateTimeInput.disabled = False
            print(self.customDateTimeInput.disabled)
        else:
            self.customDateTimeInput.disabled = True
            print(self.customDateTimeInput.disabled)

    def load_current_tag(self, *args, **kwargs):
        self.customDateTag.text = self.caller.database_entry.naming_tag

    def close(self, *args, **kwargs):
        """
        Called when Close is called. Remove caller attribute and clear customDateTimeInput's text.
        :return:
        """
        self.caller = None
        self.customDateTimeInput.text = ""

    def apply(self):
        self.try_rename()
        self.dismiss()

    def try_rename(self):
        """
        Applies the new name to the selected comparePane,
        Closes the modal by removing the widget.
        :return:
        """
        naming_tag = self.customDateTag.text
        text = naming_tag.strip().capitalize()

        # parse custom
        if text == "Custom":
            try:
                new_datetime = datetime.datetime.strptime(self.ids.datetime_input.text, "%Y-%m-%d %H.%M.%S")
                naming_tag = text
            except Exception as e:
                self.error_popup.error_msg = f"Exception while parsing custom datetime:\n {e}"
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                return

        else:
            parse_func = key_lookup_dir.get(naming_tag)

            if parse_func is None:
                self.error_popup.error_msg = f"No Parsing function found for given Tag."
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                return

            new_datetime, key = parse_func(self.caller.database_entry.metadata)

        # if the datetime is identical, ignore
        if new_datetime == self.caller.database_entry.datetime:
            print("Date is equivalent")
            return

        print(new_datetime)
        # not identical, rename the file
        new_name = self.float_sibling.database.rename_file(self.caller.database_entry, new_datetime=new_datetime,
                                                           naming_tag=naming_tag)

        self.caller.database_entry.new_name = new_name
        self.caller.database_entry.datetime = new_datetime
        self.caller.database_entry.naming_tag = naming_tag
        self.caller.load_from_database_entry()

    def apply_close(self):
        self.try_rename()

        self.float_sibling.removeCompareWidget(self.caller)
        self.dismiss()


class PictureLibrary(App):
    def build(self):
        mf = RootWidget()
        return mf


if __name__ == "__main__":
    Config.set('input', 'mouse', 'mouse, disable_multitouch')
    PictureLibrary().run()
