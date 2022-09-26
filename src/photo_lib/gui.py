import time
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
import os
import datetime
from .metadataagregator import key_lookup_dir, MetadataAggregator
from .runner import PhotoDb, DatabaseEntry
from kivy.uix.label import Label
import traceback
from multiprocessing.connection import Connection


class ScrollLabel(ScrollView):
    lbl = ObjectProperty(None)
    text = StringProperty("example content")

    def __init__(self, **kwargs):
        super(ScrollLabel, self).__init__(**kwargs)
        self.bind(on_scroll_stop=self.update_compare_pane)

    def update_compare_pane(self, *args, **kwargs):
        self.parent.parent.update_scroll_metadata(x=self.scroll_x, y=self.scroll_y)


class MetadataScrollLabel(ScrollView):
    lbl = ObjectProperty(None)
    text = StringProperty("example content")

    def __init__(self, **kwargs):
        super(MetadataScrollLabel, self).__init__(**kwargs)
        self.bind(on_scroll_stop=self.update_compare_pane)

    def update_compare_pane(self, *args, **kwargs):
        self.parent.parent.update_scroll_metadata(x=self.scroll_x, y=self.scroll_y)


class PathScrollLabel(ScrollView):
    lbl = ObjectProperty(None)
    text = StringProperty("example content")

    def __init__(self, **kwargs):
        super(PathScrollLabel, self).__init__(**kwargs)
        self.bind(on_scroll_stop=self.update_compare_pane)

    def update_compare_pane(self, *args, **kwargs):
        self.parent.parent.update_scroll_path(x=self.scroll_x)


class ComparePane(Widget):
    image = ObjectProperty(None)
    dump = ObjectProperty(None)
    rename_file = ObjectProperty(None)
    l_ofname = ObjectProperty(None)
    l_ofpath = ObjectProperty(None)
    l_naming_tag = ObjectProperty(None)
    l_new_name = ObjectProperty(None)
    l_metadata = ObjectProperty(None)
    obuton = ObjectProperty(None)
    mark_delete_button = ObjectProperty(None)

    database_entry: DatabaseEntry = None

    image_path = StringProperty("")
    org_fname = StringProperty("")
    org_fpath = StringProperty("")
    naming_tag = StringProperty("")
    new_name = StringProperty("")
    metadata = StringProperty("")

    pl: PhotoDb

    def __init__(self, db: DatabaseEntry, pictureLib: PhotoDb, **kwargs):
        super(ComparePane, self).__init__(**kwargs)
        self.database_entry = db
        self.pl = pictureLib
        self.load_from_database_entry()

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

        result = ""

        for key in key_list:
            result += f"{key}: {self.database_entry.metadata.get(key)}\n"

        self.metadata = result

    def update_scroll_metadata(self, *args, x: float, y: float, **kwargs):
        self.parent.update_scroll_meta(x=x, y=y)

    def update_scroll_path(self, *args, x: float, **kwargs):
        self.parent.update_scroll_path(x=x)

    def open_modal(self):
        self.parent.parent.parent.parent.open_modal(caller=self)

    def set_button_color(self):
        if self.mark_delete_button.state == "down":
            self.mark_delete_button.background_color = 1.0, 0.0, 0.0
            self.mark_delete_button.text = "to trash"
        else:
            self.mark_delete_button.background_color = 0.2, 0.6, 0.2
            self.mark_delete_button.text = "keep"

    def set_delete_on_main(self):
        self.mark_delete_button.state = "normal"
        self.set_button_color()



class MyGrid(GridLayout):
    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))

    def update_scroll_meta(self, *args, x: float, y: float, **kwargs):
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
            c.l_metadata.scroll_x = x
            c.l_metadata.scroll_y = y

    def update_scroll_path(self, *args, x: float, **kwargs):
        for c in self.children:
            c: ComparePane
            c.l_ofpath.scroll_x = x


class FlexibleBox(BoxLayout):
    def __init__(self, **kwargs):
        super(FlexibleBox, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))


class CompareScroller(ScrollView):
    flexbox = ObjectProperty(None)


class MyFloat(FloatLayout):
    filenameModal = None
    errorModal = None
    db_selector_widget = None
    db_duplicate_location = None
    db_dup_proc_sel = None

    dup_fp: str = None
    database: PhotoDb = None

    cps: CompareScroller
    compareWidgets = []
    loaded_row: int = None

    def __init__(self, fp: str = None, **kwargs):
        super(MyFloat, self).__init__(**kwargs)
        self.dup_fp = fp

        self.errorModal = ErrorPopup()
        self.filenameModal = SetDateModal(self, self.errorModal)
        self.db_selector_widget = DatabaseSelector(self)
        self.cps = CompareScroller()
        self.db_dup_proc_sel = DuplicateDetection(root_wdg=self)
        self.db_duplicate_location = DuplicateLocation(Root_Ref=self, proc_select=self.db_dup_proc_sel)

        self.add_widget(self.cps, index=-1)

        if self.dup_fp is None:
            self.db_selector_widget.open()

    def remove_scroller(self):
        self.remove_widget(self.cps)

    def add_scroller(self):
        self.add_widget(self.cps, index=-1)

    def load_db(self):
        self.database = PhotoDb(root_dir=self.dup_fp)
        mda = MetadataAggregator(exiftool_path="/usr/bin/Image-ExifTool-12.44/exiftool")
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
                cw = ComparePane(db=entry, pictureLib=self.database)
                self.compareWidgets.append(cw)
                self.cps.flexbox.add_widget(cw)

        self.ids.status.text = f"Number of duplicates in database: {self.database.get_duplicate_table_size()}"

    def store_load_entry(self):
        # TODO Implement
        pass


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
    float_sibling: MyFloat
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
            print("Set to false")
            print(self.customDateTimeInput.disabled)
        else:
            self.customDateTimeInput.disabled = True
            print("Set to true")
            print(self.customDateTimeInput.disabled)

    def load_current_tag(self, *_args, **kwargs):
        self.customDateTag.text = self.caller.database_entry.naming_tag

    def close(self, *args, **kwargs):
        """
        Called when Close is called. Remove caller attribute and clear customDateTimeInput's text.
        :return:
        """
        self.caller = None
        self.customDateTimeInput.text = ""

    def apply_close(self):
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
                new_datetime = text
            except Exception as e:
                self.error_popup.error_msg = f"Exception while parsing custom datetime:\n {e}"
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                self.dismiss()
                return

        else:
            parse_func = key_lookup_dir.get(naming_tag)

            if parse_func is None:
                self.error_popup.error_msg = f"No Parsing function found for given Tag."
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                self.dismiss()

            new_datetime, key = parse_func(self.caller.database_entry.metadata)

        # if the datetime is identical, ignore
        if new_datetime == self.caller.database_entry.datetime:
            print("Date is equivalent")
            self.dismiss()
            return

        print(new_datetime)
        # not identical, rename the file
        new_name = self.float_sibling.database.rename_file(self.caller.database_entry, new_datetime=new_datetime,
                                                naming_tag=naming_tag)

        self.caller.database_entry.new_name = new_name
        self.caller.database_entry.datetime = new_datetime
        self.caller.database_entry.naming_tag = naming_tag
        self.caller.load_from_database_entry()

        self.dismiss()  # resets caller already


class TracebackWidget(Label):
    pass


class ErrorPopup(Popup):
    error_msg = StringProperty("")
    traceback_string = StringProperty("")
    tbw: TracebackWidget = None
    
    def __init__(self, **kwargs):
        super(ErrorPopup, self).__init__(**kwargs)

    def show_traceback(self):
        l: BoxLayout = self.ids.layout

        self.tbw = TracebackWidget()
        self.tbw.text = self.traceback_string

        l.add_widget(self.tbw)

    def hide_traceback(self):
        l: BoxLayout = self.ids.layout
        l.remove_widget(self.tbw)

    def trigger_traceback(self, **kwargs):
        if self.ids.show_btn.state == "down":
            self.show_traceback()
            return

        self.hide_traceback()


class DatabaseSelector(Popup):
    fc = ObjectProperty(None)

    compareFloat: MyFloat

    def __init__(self, comp_flt: MyFloat, **kwargs):
        super(DatabaseSelector, self).__init__(**kwargs)
        self.compareFloat = comp_flt
        self.bind(on_dismiss=self.try_close)
        self.bind(on_open=self.hide_scroll)

    def hide_scroll(self, *args, **kwargs):
        self.compareFloat.remove_scroller()

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


class DuplicateLocation(Popup):
    my_float_ref: MyFloat
    reuse_button = ObjectProperty(None)
    recompute_button = ObjectProperty(None)
    proc_sel = None

    def __init__(self, Root_Ref: MyFloat, proc_select, **kwargs):
        super(DuplicateLocation, self).__init__(**kwargs)
        self.my_float_ref = Root_Ref
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


class DuplicateDetection(Popup):
    root: MyFloat

    def __init__(self, root_wdg: MyFloat, **kwargs):
        self.root = root_wdg
        super(DuplicateDetection, self).__init__(**kwargs)
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


class ProgressInfo(Popup):
    prog_bar = ObjectProperty(None)
    pipe: Connection = None

    def __init__(self, done_func, **kwargs):
        super(ProgressInfo, self).__init__(**kwargs)
        self.auto_dismiss = False
        self.done_callback = done_func

    def suck_on_pipe(self, *args, **kwargs):
        try:
            transmission = self.pipe.recv()
            print(f"Receiving {transmission}")
        except EOFError:
            time.sleep(1)
            return

        if transmission == "DONE":
            print("Stopping")
            Clock.unschedule(self.suck_on_pipe)
            self.pipe = None
            self.dismiss()
            self.done_callback()

        else:
            self.title = f"Total: {transmission[1]}; Done: {transmission[0]}"
            self.ids.prog_bar.value = transmission[0] / transmission[1] * 100


class PictureLibrary(App):
    def build(self):
        mf = MyFloat()
        return mf

