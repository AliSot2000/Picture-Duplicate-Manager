from kivy.properties import ObjectProperty, ColorProperty
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder
import os

# Import for kivy lang
from photo_lib.gui.my_grid import MyGrid
from photo_lib.gui.flexible_box import FlexibleBox

compare_scroller_loaded = False
if not compare_scroller_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), "compare_scroller.kv"))
    compare_scroller_loaded = True


class CompareScroller(ScrollView):
    flexbox = ObjectProperty(None)
    background_col = ColorProperty()