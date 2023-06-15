from kivy.uix.gridlayout import GridLayout
from photo_lib.gui.compare_pane import ComparePane
from photo_lib.gui.metadata_scroll_label import MetadataScrollLabel
from photo_lib.gui.path_scroll_label import PathScrollLabel


class MyGrid(GridLayout):
    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.bind(minimum_width=self.setter('width'))

    def update_scroll_meta(self, *args, x: float, y: float, caller: MetadataScrollLabel, **kwargs):
        """
        Updates the scroll value of all meta_data labels to the same value
        :param args: just for safety
        :param x: new target x
        :param y: new target y
        :param kwargs: just for safety
        :return:
        """
        for c in self.children:
            c: ComparePane
            if c.l_metadata == caller:
                continue
            c.l_metadata.scroll_x = x
            c.l_metadata.scroll_y = y
            c.l_metadata.last_scroll_x = x
            c.l_metadata.last_scroll_y = y

    def update_scroll_path(self, *args, x: float, caller: PathScrollLabel,  **kwargs):
        for c in self.children:
            c: ComparePane
            if c == caller:
                continue
            c.l_ofpath.scroll_x = x
            c.l_ofpath.last_scroll_x = x

    def open_image_popup(self, path: str):
        self.parent.parent.parent.open_image_popup(path)
