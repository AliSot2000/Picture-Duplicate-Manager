from kivy.uix.label import Label
from kivy.lang import Builder
import os

traceback_widget_loaded = False
if not traceback_widget_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), 'traceback_widget.kv'))
    traceback_widget_loaded = True


class TracebackWidget(Label):
    pass
