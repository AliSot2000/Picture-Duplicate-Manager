from kivy.uix.boxlayout import BoxLayout


class FlexibleBox(BoxLayout):
    def __init__(self, **kwargs):
        super(FlexibleBox, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))