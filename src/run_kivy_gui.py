from kivy.config import Config
from photo_lib.k_gui import PictureLibrary


"""
Currently best implemented version of the app.
This version is no longer in development since I need to be able to scroll horizontally without a modifier key.
This however is currently not supported in kivy which is why I am currently working on a new version of the app.

The new version is now built using Qt6.
"""

if __name__ == "__main__":
    # Config.set_callback('input', 'mouse', 'mouse, disable_multitouch')
    PictureLibrary().run()
#
# BoxLayout:
# orientation: 'vertical'
# size_hint_x: None
# size_hint_y: None
# size_x: 1500