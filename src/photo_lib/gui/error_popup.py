from kivy.properties import StringProperty
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
import os
from photo_lib.gui.traceback_widget import TracebackWidget

error_popup_loaded = False
if not error_popup_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), 'error_popup.kv'))
    error_popup_loaded = True

class ErrorPopup(Popup):
    error_msg = StringProperty("")
    traceback_string = StringProperty("")
    tbw: TracebackWidget = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def show_traceback(self):
        l: BoxLayout = self.ids.layout

        self.tbw = TracebackWidget()
        self.tbw.text = self.traceback_string if self.traceback_string is not None else "<No Traceback>"

        l.add_widget(self.tbw)

    def hide_traceback(self):
        l: BoxLayout = self.ids.layout
        l.remove_widget(self.tbw)

    def trigger_traceback(self, **kwargs):
        if self.ids.show_btn.state == "down":
            self.show_traceback()
            return

        self.hide_traceback()