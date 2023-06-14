from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.scrollview import ScrollView
from gestures4kivy import CommonGestures


sample_text = "OI"


class StupidScrollLabel(CommonGestures, ScrollView):
    lb = ObjectProperty(None)
    text = StringProperty(sample_text)

    def on_scroll_start(self, touch, check_children=True):
        ...

    def on_scroll_stop(self, touch, check_children=True):
        ...

    def on_scroll_move(self, touch):
        ...

    def cgb_scroll(self, touch, focus_x, focus_y, delta_y, velocity):
        # handle no child element
        if self.children is None or len(self.children) == 0:
            return

        dy = velocity * self.scroll_wheel_distance
        height = self.children[0].size[1]
        self.scroll_y = min(1.0, max(0, self.scroll_y + (dy / height)))

    def cgb_pan(self, touch, focus_x, focus_y, delta_x, velocity):
        if self.children is None or len(self.children) == 0:
            return

        dx = velocity * self.scroll_wheel_distance
        width = self.children[0].size[0]
        self.scroll_x = min(1.0, max(0, self.scroll_x + (dx / width)))

