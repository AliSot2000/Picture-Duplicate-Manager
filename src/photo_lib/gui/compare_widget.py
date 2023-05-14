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

class CompareRoot(QWidget):
    model: Model
    layout: QHBoxLayout
    media_panes: List[MediaPane]
    min_width: int = 300

    updating_buttons: bool = False
    main_buttons: List[QPushButton] = None

    def __init__(self, model: Model):
        super().__init__()
        self.main_buttons = []
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
        if self.layout.count() > 0:
            self.remove_all_elements()

        # Go through all DatabaseEntries, generate a MediaPane from each one and add the panes to the layout.
        for dbe in self.model.files:
            pane = MediaPane(self.model, dbe, self.synchronized_scroll)
            self.media_panes.append(pane)
            self.layout.addWidget(pane)
            # pane.show()

        # Attaching  Buttons
        for pane in self.media_panes:
            pane.main_button.clicked.connect(button_wrapper(pane.main_button, self.button_state))
            self.main_buttons.append(pane.main_button)

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
        self.main_buttons = []

    def remove_media_pane(self, media_pane: MediaPane):
        """
        Removes the given MediaPane from the layout and deletes it.

        :param media_pane: The MediaPane to remove.
        :return:
        """
        self.layout.removeWidget(media_pane)
        self.main_buttons.remove(media_pane.main_button)
        media_pane.deleteLater()
        self.media_panes.remove(media_pane)

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
            for b in self.main_buttons:
                if b != btn:
                    # Try except as idiot proofing to stop the program from crashing.
                    try:
                        b.setChecked(False)
                    except RuntimeError:
                        print("Runtime Error: Couldn't set button to unchecked. CHECK CODE!!!")
                        self.main_buttons.remove(b)
                        self.updating_buttons = False
                        self.button_state(btn)
        else:
            for b in self.main_buttons:
                # Try except as idiot proofing to stop the program from crashing.
                try:
                    b.setChecked(False)
                except RuntimeError:
                    print("Runtime Error: Couldn't set button to unchecked. CHECK CODE!!!")
                    self.main_buttons.remove(b)
                    self.updating_buttons = False
                    self.button_state(btn)

        self.updating_buttons = False