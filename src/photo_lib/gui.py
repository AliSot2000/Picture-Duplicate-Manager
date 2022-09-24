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
from dataclasses import dataclass
import datetime
from .metadataagregator import key_lookup_dir
from kivy.uix.label import Label
import traceback
import time

@dataclass
class DatabaseEntry:
    key: int
    org_fname: str
    org_fpath: str
    metadata: dict
    google_fotos_metadata: dict
    naming_tag: str
    file_hash: str
    new_name: str
    datetime: str


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

    database_entry: DatabaseEntry
    modified: bool = False
    delete: bool = False

    image_path = StringProperty("/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images/IMG_2162.JPG")
    org_fname = StringProperty("IMG_2162.JPG")
    org_fpath = StringProperty("/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images")
    naming_tag = StringProperty("Create Date")
    new_name = StringProperty("2018-06-03 22.44.11_000.jpg")
    bin_comp = BooleanProperty(True)
    metadata = StringProperty(
        """Composite:ImageSize: 2048 1536\nComposite:Megapixels: 3.145728\nExifTool:ExifToolVersion: 12.44\nFile:Directory: /media/alisot2000/DumpStuff/Picture consolidation/Export Fotos Macbok archive 2/iptc/1. April 2018\nFile:FileAccessDate: 2022:09:12 18:34:46+02:00\nFile:FileInodeChangeDate: 2022:09:12 17:11:13+02:00\nFile:FileModifyDate: 2018:04:01 02:43:30+02:00\nFile:FileName: IMG_2130.PNG\nFile:FilePermissions: 100777\nFile:FileSize: 1912870\nFile:FileType: PNG\nFile:FileTypeExtension: PNG\nFile:MIMEType: image/png\nPNG:BitDepth: 8\nPNG:ColorType: 2\nPNG:Compression: 0\nPNG:Filter: 0\nPNG:ImageHeight: 1536\nPNG:ImageWidth: 2048\nPNG:Interlace: 0\nPNG:SRGBRendering: 0\nSourceFile: /media/alisot2000/DumpStuff/Picture consolidation/Export Fotos Macbok archive 2/iptc/1. April 2018/IMG_2130.PNG\nXMP:DateCreated: 2018:04:01 02:43:29\nXMP:UserComment: Screenshot\nXMP:XMPToolkit: XMP Core 5.4.0""")

    def update_scroll_metadata(self, *args, x: float, y: float, **kwargs):
        self.parent.update_scroll_meta(x=x, y=y)

    def update_scroll_path(self, *args, x: float, **kwargs):
        self.parent.update_scroll_path(x=x)

    def open_modal(self):
        self.parent.parent.parent.parent.open_modal(t_id=self)

    def set_button_color(self):
        if self.ids.dlt_btn.state == "down":
            self.ids.dlt_btn.background_color = 1.0, 0.0, 0.0
            self.ids.dlt_btn.text = "to trash"
        else:
            self.ids.dlt_btn.background_color = 0.2, 0.6, 0.2
            self.ids.dlt_btn.text = "keep"


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


class MyBox(BoxLayout):
    def __init__(self, **kwargs):
        super(MyBox, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))


class CompareScroller(ScrollView):
    pass


class MyFloat(FloatLayout):
    filenameModal = None
    errorModal = None
    db_selector_widget = None

    dup_fp: str = None

    cps: CompareScroller

    def __init__(self, fp: str = None, **kwargs):
        super(MyFloat, self).__init__(**kwargs)
        self.dup_fp = fp

        self.errorModal = ErrorPopup()
        self.filenameModal = SetDateModal(self, self.errorModal)
        self.db_selector_widget = DatabaseSelector(self)
        self.cps = CompareScroller()

        self.add_widget(self.cps, index=-1)

        if self.dup_fp is None:
            self.db_selector_widget.open()

    def remove_scroller(self):
        self.remove_widget(self.cps)

    def add_scroller(self):
        self.add_widget(self.cps, index=-1)

    def load_(self):
        pass

    def open_modal(self, t_id):
        self.filenameModal.caller = t_id
        self.filenameModal.open()


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
        pass

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
        print("Need to update value in ComparePane")

        target_key = self.ids.naming_tag_input
        text: str = self.customDateTag.text
        text = text.strip().capitalize()

        # parse custom
        if text == "Custom":
            try:
                new_datetime = datetime.datetime.strptime(self.ids.datetime_input.text, "%Y-%m-%d %H.%M.%S")
            except Exception as e:
                self.error_popup.error_msg = f"Exception while parsing custom datetime:\n {e}"
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                self.dismiss()
                return

        else:
            parse_func = key_lookup_dir.get(target_key)

            if parse_func is None:
                self.error_popup.error_msg = f"No Parsing function found for given Tag."
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                self.dismiss()

            new_datetime = parse_func(self.caller.database_entry.metadata)

        # set all the shit
        print("DO stuff")

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
            self.dismiss()
        else:
            self.ids.status.text = "No .photos.db file present. This is not a PhotoLibrary"


class PictureLibrary(App):
    def build(self):
        mf = MyFloat()
        return mf

