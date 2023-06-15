from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.scrollview import ScrollView


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