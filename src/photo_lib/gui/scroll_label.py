from kivy.properties import StringProperty, ObjectProperty, ColorProperty
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder
import os



class ScrollLabel(ScrollView):
    """
    Default Scroll Label
    """
    lbl = ObjectProperty(None)
    text = StringProperty("example content")
    background_col = ColorProperty()

    def __init__(self, **kwargs):
        # TODO get it working with the Builder
        # Builder.load_file(os.path.join(os.path.dirname(__file__), "scroll_label.kv"))
        super().__init__(**kwargs)
        self.background_col = [0.2, 0.2, 0.2, 1.0]