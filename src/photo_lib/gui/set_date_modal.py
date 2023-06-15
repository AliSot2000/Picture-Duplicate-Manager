from kivy.properties import ObjectProperty
from kivy.uix.modalview import ModalView
import datetime
from photo_lib.metadataagregator import key_lookup_dir
import traceback
from kivy.lang import Builder
import os
# from photo_lib.gui.compare_pane import ComparePane # TODO Compare Pane
from photo_lib.gui.error_popup import ErrorPopup
from photo_lib.gui.root_widget_stub import RootWidgetStub

# Import for kv lang.
from photo_lib.gui.custom_date_tag import CustomDateTag


set_date_modal_loaded = False
if not set_date_modal_loaded:
    Builder.load_file(os.path.join(os.path.dirname(__file__), 'set_date_modal.kv'))
    set_date_modal_loaded = True


class SetDateModal(ModalView):
    customDateTag = ObjectProperty(None)
    customDateTimeInput = ObjectProperty(None)

    # caller: ComparePane = None
    caller = None
    float_sibling: RootWidgetStub
    # error_popup: NewDatetimeError

    def __init__(self, float_sibling, error_popup: ErrorPopup, **kwargs):
        super().__init__(**kwargs)
        self.float_sibling = float_sibling
        self.error_popup = error_popup
        self.bind(on_dismiss=self.close)
        self.bind(on_open=self.load_current_tag)

    def text_content(self, *args, **kwargs):
        """
        Sets the Custom Datetime input to enabled when the sourceTag is Custom
        :param args: just for safety
        :param kwargs: just for safety
        :return:
        """
        text: str = self.customDateTag.text
        text = text.strip().capitalize()
        if text == "Custom":
            self.customDateTimeInput.disabled = False
            print(self.customDateTimeInput.disabled)
        else:
            self.customDateTimeInput.disabled = True
            print(self.customDateTimeInput.disabled)

    def load_current_tag(self, *args, **kwargs):
        self.customDateTag.text = self.caller.database_entry.naming_tag

    def close(self, *args, **kwargs):
        """
        Called when Close is called. Remove caller attribute and clear customDateTimeInput's text.
        :return:
        """
        self.caller = None
        self.customDateTimeInput.text = ""

    def apply(self):
        self.try_rename()
        self.dismiss()

    def try_rename(self):
        """
        Applies the new name to the selected comparePane,
        Closes the modal by removing the widget.
        :return:
        """
        naming_tag = self.customDateTag.text
        text = naming_tag.strip().capitalize()

        # parse custom
        if text == "Custom":
            try:
                new_datetime = datetime.datetime.strptime(self.ids.datetime_input.text, "%Y-%m-%d %H.%M.%S")
                naming_tag = text
            except Exception as e:
                self.error_popup.error_msg = f"Exception while parsing custom datetime:\n {e}"
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                return

        else:
            parse_func = key_lookup_dir.get(naming_tag)

            if parse_func is None:
                self.error_popup.error_msg = f"No Parsing function found for given Tag."
                self.error_popup.traceback_string = traceback.format_exc()
                self.error_popup.open()
                return

            new_datetime, key = parse_func(self.caller.database_entry.metadata)

        # if the datetime is identical, ignore
        if new_datetime == self.caller.database_entry.datetime:
            print("Date is equivalent")
            return

        print(new_datetime)
        # not identical, rename the file
        new_name = self.float_sibling.database.rename_file(self.caller.database_entry, new_datetime=new_datetime,
                                                           naming_tag=naming_tag)

        self.caller.database_entry.new_name = new_name
        self.caller.database_entry.datetime = new_datetime
        self.caller.database_entry.naming_tag = naming_tag
        self.caller.load_from_database_entry()

    def apply_close(self):
        self.try_rename()

        self.float_sibling.removeCompareWidget(self.caller)
        self.dismiss()