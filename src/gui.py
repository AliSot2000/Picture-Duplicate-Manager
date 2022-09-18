from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, NumericProperty, ObjectProperty, BooleanProperty
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
import os


class ComparePane(Widget):
    image = ObjectProperty(None)
    set_original = ObjectProperty(None)
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
    metadata = StringProperty("""
Composite:ImageSize: 2048 1536
Composite:Megapixels: 3.145728
ExifTool:ExifToolVersion: 12.44
File:Directory: /media/alisot2000/DumpStuff/Picture consolidation/Export Fotos Macbok archive 2/iptc/1. April 2018
File:FileAccessDate: 2022:09:12 18:34:46+02:00
File:FileInodeChangeDate: 2022:09:12 17:11:13+02:00
File:FileModifyDate: 2018:04:01 02:43:30+02:00
File:FileName: IMG_2130.PNG
File:FilePermissions: 100777
File:FileSize: 1912870
File:FileType: PNG
File:FileTypeExtension: PNG
File:MIMEType: image/png
PNG:BitDepth: 8
PNG:ColorType: 2
PNG:Compression: 0
PNG:Filter: 0
PNG:ImageHeight: 1536
PNG:ImageWidth: 2048
PNG:Interlace: 0
PNG:SRGBRendering: 0
SourceFile: /media/alisot2000/DumpStuff/Picture consolidation/Export Fotos Macbok archive 2/iptc/1. April 2018/IMG_2130.PNG
XMP:DateCreated: 2018:04:01 02:43:29
XMP:UserComment: Screenshot
XMP:XMPToolkit: XMP Core 5.4.0""")


class Dummy(Widget):
    # sourceA = StringProperty()
    # sourceB = StringProperty()
    # num_of_sources = NumericProperty(defaultvalue=3)
    #
    # index = 0
    #
    # img_a = ObjectProperty(None)
    # img_b = ObjectProperty(None)
    # img_c = ObjectProperty(None)
    # comp = ObjectProperty(None)

    def test(self, delta):
        print("Shit is being done")
        # path = "/home/alisot2000/Documents/06 ReposNCode/PictureMerger/test-images"
        # images = ['IMG_2158.JPG', 'IMG_2159.JPG', 'IMG_2160.PNG', 'IMG_2161.JPG', 'IMG_2162.JPG', 'IMG_2163.JPG', 'IMG_2164.JPG', 'IMG_2165.JPG', 'IMG_2166.JPG', 'IMG_2167.JPG', 'IMG_2168.PNG']
        # self.index = (self.index + 1) % len(images)
        #
        # self.img_a.image.source = os.path.join(path, images[self.index])
        # self.img_b.image.source = os.path.join(path, images[(self.index + 1) % len(images)])
        # self.img_c.image.source = os.path.join(path, images[(self.index + 2) % len(images)])

    # def some_shit(self):
    #     self.img_a.index = 0
    #     self.img_b.index = 1
    #     self.img_c.index = 2


class MyFloat(FloatLayout):
    pass


class PictureLibrary(App):
    def build(self):
        # d = Dummy()

        # d.some_shit()
        # d.test(1)
        # Clock.schedule_interval(d.test, 2.0)
        # root.add_widget(d)
        mf = MyFloat()
        return mf


if __name__ == "__main__":
    PictureLibrary().run()