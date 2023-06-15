from kivy.properties import StringProperty, ObjectProperty, ColorProperty
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder
import os


scroll_label_loaded = False
if not scroll_label_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), "scroll_label.kv"))
    scroll_label_loaded = True

class ScrollLabel(ScrollView):
    """
    Default Scroll Label
    """
    lbl = ObjectProperty(None)
    text = StringProperty("example content")
    background_col = ColorProperty()

    def __init__(self, **kwargs):
        # TODO get it working with the Builder
        super().__init__(**kwargs)
        self.background_col = [0.2, 0.2, 0.2, 1.0]