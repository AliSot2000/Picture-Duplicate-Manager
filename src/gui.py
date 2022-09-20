from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, NumericProperty, ObjectProperty, BooleanProperty
from kivy.uix.scrollview import ScrollView
from kivy.uix.modalview import ModalView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
import os


class ScrollLabel(ScrollView):
    lbl = ObjectProperty(None)
    text = StringProperty("example content")

    def __init__(self, **kwargs):
        super(ScrollLabel, self).__init__(**kwargs)
        self.bind(on_scroll_stop=self.update_compare_pane)

    def update_compare_pane(self, *args,  **kwargs):
        self.parent.parent.update_global(x=self.scroll_x, y=self.scroll_y)


class ComparePane(Widget):
    image = ObjectProperty(None)
    dump = ObjectProperty(None)
    rename_file = ObjectProperty(None)
    l_ofname = ObjectProperty(None)
    l_ofpath = ObjectProperty(None)
    l_naming_tag = ObjectProperty(None)
    l_new_name = ObjectProperty(None)
    l_binary_comp = ObjectProperty(None)
    l_metadata = ObjectProperty(None)

    image_path = StringProperty("/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images/IMG_2162.JPG")
    org_fname = StringProperty("IMG_2162.JPG")
    org_fpath = StringProperty("/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images")
    naming_tag = StringProperty("Create Date")
    new_name = StringProperty("2018-06-03 22.44.11_000.jpg")
    bin_comp = BooleanProperty(True)
    metadata = StringProperty("""Composite:ImageSize: 2048 1536\nComposite:Megapixels: 3.145728\nExifTool:ExifToolVersion: 12.44\nFile:Directory: /media/alisot2000/DumpStuff/Picture consolidation/Export Fotos Macbok archive 2/iptc/1. April 2018\nFile:FileAccessDate: 2022:09:12 18:34:46+02:00\nFile:FileInodeChangeDate: 2022:09:12 17:11:13+02:00\nFile:FileModifyDate: 2018:04:01 02:43:30+02:00\nFile:FileName: IMG_2130.PNG\nFile:FilePermissions: 100777\nFile:FileSize: 1912870\nFile:FileType: PNG\nFile:FileTypeExtension: PNG\nFile:MIMEType: image/png\nPNG:BitDepth: 8\nPNG:ColorType: 2\nPNG:Compression: 0\nPNG:Filter: 0\nPNG:ImageHeight: 1536\nPNG:ImageWidth: 2048\nPNG:Interlace: 0\nPNG:SRGBRendering: 0\nSourceFile: /media/alisot2000/DumpStuff/Picture consolidation/Export Fotos Macbok archive 2/iptc/1. April 2018/IMG_2130.PNG\nXMP:DateCreated: 2018:04:01 02:43:29\nXMP:UserComment: Screenshot\nXMP:XMPToolkit: XMP Core 5.4.0""")

    def __init__(self, **kwargs):
        super(ComparePane, self).__init__(**kwargs)

    def update_global(self, *args, x: float, y: float,  **kwargs):
        self.parent.update_scroll_meta(x=x, y=y)

    def open_modal(self):
        self.parent.parent.parent.parent.open_modal(t_id=self)

class MyGrid(GridLayout):
    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))

    def update_scroll_meta(self, *args, x: float, y: float,  **kwargs):
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


class MyBox(BoxLayout):
    def __init__(self, **kwargs):
        super(MyBox, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))


class MyFloat(FloatLayout):
    compareGrid = ObjectProperty(None)
    filenameModal = ObjectProperty(None)

    def open_modal(self, t_id):
        fm = SetDateModal(target_id=t_id)
        self.filenameModal = ObjectProperty(fm)
        self.add_widget(fm)


class CustomDateTag(TextInput):
    def __init__(self, **kwargs):
        super(CustomDateTag, self).__init__(**kwargs)
        self.bind(on_text_validate=self.parent_update)

    def parent_update(self, *args, **kwargs):
        self.parent.parent.text_content()


class SetDateModal(ModalView):
    tagLabel = ObjectProperty(None)
    customDateTag = ObjectProperty(None)
    customDateTime = ObjectProperty(None)
    customDateTimeInput = ObjectProperty(None)

    caller = ObjectProperty(None)

    modify_id: str

    def __init__(self, target_id, **kwargs):
        super(SetDateModal, self).__init__(**kwargs)
        self.caller = ObjectProperty(target_id)

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


class PictureLibrary(App):
    def build(self):
        mf = MyFloat()
        # Clock.schedule_interval(mf.comparegrid.action, 2.0)
        return mf


if __name__ == "__main__":
    PictureLibrary().run()