from PyQt6.QtWidgets import QHBoxLayout, QWidget, QLabel, QPushButton, QButtonGroup
from photo_lib.gui.model import Model
from typing import List
from photo_lib.gui.media_pane import MediaPane
from photo_lib.gui.text_scroll_area import TextScroller
from typing import Callable


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

    :param pain: pain that calls the function
    :param func: methode to execute that needs to have the button as a parameter
    :return:
    """
    def wrapper():
        return func(media_pane=media_pane)
    return wrapper


class CompareRoot(QWidget):
    model: Model
    layout: QHBoxLayout
    media_panes: List[MediaPane]
    min_width: int = 300
    max_needed_width: int = 0
    min_height = 870

    updating_buttons: bool = False
    auto_load: bool = True
    open_image_fn: Callable
    open_datetime_modal_fn: Callable

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
        self.layout = QHBoxLayout()
        self.media_panes = []

        self.setMinimumHeight(860)
        self.setLayout(self.layout)
        self.load_elements()

    def load_elements(self):
        """
        Goes through the model and fetches all the present files. Adds all files to the view.

        :return:
        """
        self.max_needed_width = 10
        if self.layout.count() > 0:
            self.remove_all_elements()

        # Go through all DatabaseEntries, generate a MediaPane from each one and add the panes to the layout.
        for dbe in self.model.files:
            pane = MediaPane(self.model, dbe, self.synchronized_scroll)
            self.media_panes.append(pane)
            self.layout.addWidget(pane)

        # Attaching  Buttons
        for pane in self.media_panes:
            pane.main_button.clicked.connect(button_wrapper(pane.main_button, self.button_state))
            pane.remove_media_button.clicked.connect(pain_wrapper(pane, self.remove_media_pane))
            self.max_needed_width += pane.max_needed_width + 10  # TODO Better formula
            pane.media.clicked.connect(lambda : self.open_image_fn(pane.media.fpath))
            pane.change_tag_button.clicked.connect(lambda : self.open_datetime_modal_fn(pane))

        self.setMinimumWidth(len(self.model.files) * 300)

    def remove_all_elements(self):
        """
        Removes all the widgets from the layout and deletes them.

        :return:
        """
        for element in self.media_panes:
            self.layout.removeWidget(element)
            element.deleteLater()

        self.media_panes = []

    def remove_media_pane(self, media_pane: MediaPane):
        """
        Removes the given MediaPane from the layout and deletes it.

        :param media_pane: The MediaPane to remove.
        :return:
        """
        self.layout.removeWidget(media_pane)
        media_pane.deleteLater()
        self.media_panes.remove(media_pane)

        if len(self.media_panes) == 0 and self.auto_load:
            self.load_elements()

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
        if self.updating_buttons:
            return

        self.updating_buttons = True
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


        self.updating_buttons = False