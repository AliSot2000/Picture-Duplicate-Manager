from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from PyQt6.QtGui import QResizeEvent

from photo_lib.gui.model import Model
from photo_lib.gui.media_pane import MediaPane
from photo_lib.gui.text_scroll_area import TextScroller
from photo_lib.gui.button_bar import ButtonBar

from typing import Callable, List
import warnings


def button_wrapper(btn: QPushButton, func: Callable):
    """
    This function is used to wrap the button that calls the function into the function so that one function can be
    used for many different buttons. Because Slots in QT don't communicate the caller of the function.

    :param btn: button that calls the function
    :param func: methode to execute that needs to have the button as a parameter
    :return:
    """
    def wrapper():
        return func(btn=btn)
    return wrapper


def pain_wrapper(media_pane: MediaPane, func: Callable):
    """
    This function is used to wrap the media pain that calls the function into the function so that one function can be
    used for many different buttons. Because Slots in QT don't communicate the caller of the function.

    :param media_pane: pain that calls the function
    :param func: methode to execute that needs to have the button as a parameter
    :return:
    """
    def wrapper():
        return func(media_pane=media_pane)
    return wrapper


class CompareRoot(QWidget):
    model: Model
    media_layout: QHBoxLayout
    media_panes: List[MediaPane]
    min_width: int = 300
    max_needed_width: int = 0
    min_height = 870

    __updating_buttons: bool = False
    auto_load: bool = True

    open_image_fn: Callable
    open_datetime_modal_fn: Callable

    scroll_area: QScrollArea
    media_panes_placeholder: QLabel
    compare_layout: QVBoxLayout
    button_bar: ButtonBar

    # using ScrollView
    using_scroll_view: bool = True

    def __init__(self, model: Model, open_image_fn: Callable, open_datetime_modal_fn: Callable):
        """
        This widget is the root widget for the compare view. It holds all the MediaPanes and the buttons to control them.
        :param model: Object that contains everything related to the state.
        :param open_image_fn: Function to open a specific image in full view.
        """
        super().__init__()
        # self.setStyleSheet("background-color: darkGrey;")
        self.open_image_fn = open_image_fn
        self.open_datetime_modal_fn = open_datetime_modal_fn
        self.model = model
        self.media_panes = []

        # Instantiating the widgets
        self.media_panes_placeholder = QLabel()
        self.compare_layout = QVBoxLayout()
        self.media_layout = QHBoxLayout()
        self.scroll_area = QScrollArea()
        self.button_bar = ButtonBar()

        # Creating the widget hierarchy
        self.setLayout(self.compare_layout)

        self.compare_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_layout.setSpacing(0)
        self.compare_layout.addWidget(self.scroll_area)
        self.compare_layout.addWidget(self.button_bar)

        self.scroll_area.setWidget(self.media_panes_placeholder)

        self.media_panes_placeholder.setLayout(self.media_layout)
        self.media_panes_placeholder.setStyleSheet("background-color: darkGrey;")
        self.media_panes_placeholder.setContentsMargins(0, 0, 0, 0)

        self.button_bar.next_button.clicked.connect(self.skip_entry)
        self.button_bar.next_button.clicked.connect(self.update_duplicate_count)
        self.button_bar.commit_selected.clicked.connect(lambda : self.mark_duplicates_from_gui(selected=True))
        self.button_bar.commit_selected.clicked.connect(self.update_duplicate_count)
        self.button_bar.commit_all.clicked.connect(lambda : self.mark_duplicates_from_gui(selected=False))
        self.button_bar.commit_all.clicked.connect(self.update_duplicate_count)

        self.setMinimumHeight(500)
        self.setMinimumWidth(500)
        self.media_panes_placeholder.setMinimumHeight(870)
        self.update_duplicate_count()

    def load_elements(self) -> bool:
        """
        Goes through the model and fetches all the present files. Adds all files to the view.

        :return: (If duplicates were available to be loaded)
        """
        self.max_needed_width = 10
        if self.media_layout.count() > 0:
            return False

        # Query new files from the db.
        if not self.model.fetch_duplicate_row():
            warnings.warn("Load elements called with duplicates still present. Call to remove_all_elements() needed.")
            return False

        # Go through all DatabaseEntries, generate a MediaPane from each one and add the panes to the layout.
        for dbe in self.model.files:
            pane = MediaPane(self.model, dbe, self.synchronized_scroll)
            self.media_panes.append(pane)
            self.media_layout.addWidget(pane)

        # Attaching  Buttons
        for pane in self.media_panes:
            pane.main_button.clicked.connect(button_wrapper(pane.main_button, self.button_state))
            pane.remove_media_button.clicked.connect(pain_wrapper(pane, self.remove_media_pane))
            self.max_needed_width += pane.max_needed_width + 10  # TODO Better formula
            pane.media.clicked.connect(lambda : self.open_image_fn(pane.media.fpath))
            pane.change_tag_button.clicked.connect(lambda : self.open_datetime_modal_fn(pane))

        self.media_panes_placeholder.setMinimumWidth(len(self.model.files) * 310 + 10)
        if self.maintain_visibility is not None:
            self.maintain_visibility()

        self.auto_set_buttons()
        return True

    def remove_all_elements(self):
        """
        Removes all the widgets from the layout and deletes them.

        :return:
        """
        for element in self.media_panes:
            self.media_layout.removeWidget(element)
            element.deleteLater()

        self.media_panes = []
        self.model.clear_files()
        if self.maintain_visibility is not None:
            self.maintain_visibility()

    def remove_media_pane(self, media_pane: MediaPane):
        """
        Removes the given MediaPane from the layout and deletes it.

        :param media_pane: The MediaPane to remove.
        :return:
        """
        self.media_layout.removeWidget(media_pane)
        media_pane.deleteLater()
        self.media_panes.remove(media_pane)
        self.model.remove_file(media_pane.dbe)

        if len(self.media_panes) == 0 and self.auto_load:
            self.model.clear_files()
            self.load_elements()
        if self.maintain_visibility is not None:
            self.maintain_visibility()

    def synchronized_scroll(self, name: str, caller: TextScroller, rx: float, ry: float):
        """
        Iterate over all Media panes in the compare view and set the scroll amount to the same relative value indicated
        by rx and ry.

        The TextScrollers that are going to be affected are indicated by the name argument which specifies the
        attribute name of the TextScroller.

        The caller is needed to prevent a recursive self call with no termination.

        :param name: The name of the attribute to synchronize.
        :param caller: The TextScroller that called this function.
        :param rx: The relative x scroll value.
        :param ry: The relative y scroll value.
        """
        for mp in self.media_panes:
            try:
                element = getattr(mp, name)
            except AttributeError:
                print("Share Scroll Bug: Couldn't find attribute to share scroll value with.")
                exit(100)
            if element != caller:
                element.scroll_from_ratio(rx, ry)

    def button_state(self, btn: QPushButton):
        """
        This function is called when a main button is clicked. It makes sure that only one button is checked at a time.

        :param btn: button that was clicked
        :return:
        """
        if self.__updating_buttons:
            return

        self.__updating_buttons = True
        if btn.isChecked():
            for media_pane in self.media_panes:
                if media_pane.main_button != btn:
                    media_pane.main_button.setChecked(False)
                else:
                    media_pane.delete_button.setChecked(False)

        else:
            for media_pane in self.media_panes:
                # Try except as idiot proofing to stop the program from crashing.
                media_pane.main_button.setChecked(False)

        self.__updating_buttons = False

    def auto_set_buttons(self):
        """
        Automatically sets the main buttons of the MediaPanes to the correct state.
        :return:
        """
        if len(self.media_panes) != 2:
            return

        widget_a: MediaPane = self.media_panes[0]
        widget_b: MediaPane = self.media_panes[1]
        fsize_a_type = type(widget_a.dbe.metadata.get("File:FileSize"))
        fsize_b_type = type(widget_b.dbe.metadata.get("File:FileSize"))
        assert fsize_a_type is int, f"FileSize of a not of expected type int but {fsize_a_type}"
        assert fsize_b_type is int, f"FileSize of b not of expected type int but {fsize_b_type}"

        # Two files differing only in file size
        if widget_a.dbe.metadata.get("File:FileSize")\
                > widget_b.dbe.metadata.get("File:FileSize"):
            widget_a.main_button.setChecked(True)
            widget_b.delete_button.setChecked(True)
        elif widget_a.dbe.metadata.get("File:FileSize")\
                < widget_b.dbe.metadata.get("File:FileSize"):
            widget_b.main_button.setChecked(True)
            widget_a.delete_button.setChecked(True)

        # Two files identical but different dates.
        elif widget_a.dbe.metadata.get("File:FileSize")\
                == widget_b.dbe.metadata.get("File:FileSize") and \
                widget_a.dbe.datetime < widget_b.dbe.datetime:
            widget_a.main_button.setChecked(True)
            widget_b.delete_button.setChecked(True)

        elif widget_a.dbe.metadata.get("File:FileSize")\
                == widget_b.dbe.metadata.get("File:FileSize") and \
                widget_a.dbe.datetime > widget_b.dbe.datetime:
            widget_b.main_button.setChecked(True)
            widget_a.delete_button.setChecked(True)

    def update_duplicate_count(self):
        """
        Update the duplicate count in the button bar.
        :return:
        """
        duplicates_to_go = self.model.pdb.get_duplicate_table_size()
        self.button_bar.status.setText(f"Remaining Duplicates: {duplicates_to_go}")

    def skip_entry(self):
        pass

    def commit_selected(self):
        pass

    def commit_all(self):
        pass

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Propagate the resizing down even though there is a scroll view.
        :param a0: size event
        :return:
        """
        super().resizeEvent(a0)
        if a0.size().width() > self.media_panes_placeholder.minimumWidth():
            self.media_panes_placeholder.setMaximumWidth(a0.size().width())
        else:
            self.media_panes_placeholder.setMaximumWidth(self.media_panes_placeholder.minimumWidth())

        self.maintain_visibility()

    def maintain_visibility(self):
        """
        Function checks that the CompareRoot fits the screen. If not, a ScrollArea is added to contain the widgets.
        :return:
        """
        try:
            if self.size().width() > self.media_panes_placeholder.minimumWidth() \
                and self.size().height() - 70 > self.media_panes_placeholder.minimumHeight():

                # Check the scroll_area is in the stacked layout
                if self.using_scroll_view:
                    print("Removing scroll area")
                    self.compare_layout.removeWidget(self.scroll_area)
                    self.scroll_area.takeWidget()
                    self.compare_layout.insertWidget(0, self.media_panes_placeholder)
                    self.using_scroll_view = False

            else:
                # Check the compare_root is in the stacked layout
                if not self.using_scroll_view:
                    print("Removing compare root")
                    self.compare_layout.removeWidget(self.media_panes_placeholder)
                    self.compare_layout.insertWidget(0, self.scroll_area)
                    self.scroll_area.setWidget(self.media_panes_placeholder)
                    self.using_scroll_view = True
        except AttributeError as e:
            print(e)