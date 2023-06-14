import os.path
import time
from kivy.clock import Clock
from kivy.properties import ObjectProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder
import multiprocessing.connection as conn


class ProgressInfo(Popup):
    prog_bar = ObjectProperty(None)
    pipe: conn.Connection = None

    def __init__(self, done_func, **kwargs):
        Builder.load_file(os.path.join(os.path.dirname(__file__), "progress_info.kv"))
        super().__init__(**kwargs)
        self.auto_dismiss = False
        self.done_callback = done_func

    def suck_on_pipe(self, *args, **kwargs):
        try:
            transmission = self.pipe.recv()
            print(f"Receiving {transmission}")
        except EOFError:
            time.sleep(1)
            return

        if transmission == "DONE":
            print("Stopping")
            Clock.unschedule(self.suck_on_pipe)
            self.pipe = None
            self.dismiss()
            self.done_callback()

        else:
            self.title = f"Total: {transmission[1]}; Done: {transmission[0]}"
            self.ids.prog_bar.value = transmission[0] / transmission[1] * 100