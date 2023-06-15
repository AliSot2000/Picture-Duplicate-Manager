from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.widget import Widget
from kivy.lang import Builder
import os
from photo_lib.PhotoDatabase import PhotoDb, DatabaseEntry
from photo_lib.gui.path_scroll_label import PathScrollLabel
from photo_lib.gui.metadata_scroll_label import MetadataScrollLabel

# Import for kivy lang
from photo_lib.gui.scroll_label import ScrollLabel
from photo_lib.gui.image_button import ImageButton

compare_pane_loaded = False
if not compare_pane_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), "compare_pane.kv"))
    compare_pane_loaded = True


class ComparePane(Widget):
    image = ObjectProperty(None)
    dump = ObjectProperty(None)
    rename_file = ObjectProperty(None)
    l_ofname = ObjectProperty(None)
    l_ofpath = ObjectProperty(None)
    l_naming_tag = ObjectProperty(None)
    l_new_name = ObjectProperty(None)
    l_metadata = ObjectProperty(None)
    l_file_size = ObjectProperty
    obuton = ObjectProperty(None)
    mark_delete_button = ObjectProperty(None)

    database_entry: DatabaseEntry = None

    image_path = StringProperty("")
    org_fname = StringProperty("")
    org_fpath = StringProperty("")
    naming_tag = StringProperty("")
    new_name = StringProperty("")
    metadata = StringProperty("")
    file_size = StringProperty("")

    pl: PhotoDb
    __image_count = 1

    def __init__(self, db: DatabaseEntry, pictureLib: PhotoDb, **kwargs):
        super(ComparePane, self).__init__(**kwargs)
        self.database_entry = db
        self.pl = pictureLib
        self.load_from_database_entry()

    def open_image_popup(self):
        self.parent.open_image_popup(self.image_path)

    def load_from_database_entry(self):
        self.image_path = self.pl.path_from_datetime(self.database_entry.datetime, self.database_entry.new_name)

        # check trash
        if not os.path.exists(self.image_path):
            self.image_path = self.pl.trash_path(self.database_entry.new_name)

        # check thumbnails
        if not os.path.exists(self.image_path):
            self.image_path = self.pl.thumbnail_name(os.path.splitext(self.database_entry.new_name)[1],
                                                     self.database_entry.key)

        self.org_fname = self.database_entry.org_fname
        self.org_fpath = self.database_entry.org_fpath
        self.naming_tag = self.database_entry.naming_tag
        self.new_name = self.database_entry.new_name
        self.generate_metadata()

    def generate_metadata(self):
        keys = self.database_entry.metadata.keys()
        key_list = list(keys)
        key_list.sort()

        result = f"Number of Attributes: {len(key_list)}\n"

        for key in key_list:
            result += f"{key}: {self.database_entry.metadata.get(key)}\n"
            if key == "File:FileSize":
                self.file_size = f"File Size: {int(self.database_entry.metadata.get(key)):,}".replace(",", "'")

        self.metadata = result

    def update_scroll_metadata(self, *args, x: float, y: float, caller: MetadataScrollLabel, **kwargs):
        self.parent.update_scroll_meta(x=x, y=y, caller=caller)

    def update_scroll_path(self, *args, x: float, caller: PathScrollLabel, **kwargs):
        self.parent.update_scroll_path(x=x, caller=caller)

    def open_modal(self):
        self.parent.parent.parent.parent.open_modal(caller=self)

    def set_button_color(self):
        """
        Delete Button set color to red if set to down, otherwise green
        :return:
        """
        if self.mark_delete_button.state == "down":
            self.mark_delete_button.background_color = 1.0, 0.0, 0.0
            self.mark_delete_button.text = "to trash"
            self.obuton.state = "normal"
        else:
            self.mark_delete_button.background_color = 0.2, 0.6, 0.2
            self.mark_delete_button.text = "keep"

    def set_delete_on_main(self):
        """
        Cannot have 'Delete button' set as well as main.
        :return:
        """
        self.mark_delete_button.state = "normal"
        self.set_button_color()