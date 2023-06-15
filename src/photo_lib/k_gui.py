from kivy.app import App
from kivy.config import Config
from photo_lib.gui.root_widget import RootWidget


class PictureLibrary(App):
    def build(self):
        mf = RootWidget()
        return mf


if __name__ == "__main__":
    Config.set('input', 'mouse', 'mouse, disable_multitouch')
    PictureLibrary().run()
