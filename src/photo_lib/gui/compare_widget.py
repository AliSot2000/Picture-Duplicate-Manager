from PyQt6.QtWidgets import QHBoxLayout, QWidget, QLabel, QPushButton
from photo_lib.gui.model import Model
from typing import List
from photo_lib.gui.media_pane import MediaPane
from photo_lib.gui.text_scroll_area import TextScroller


class CompareRoot(QWidget):
    model: Model
    layout: QHBoxLayout
    media_panes: List[MediaPane]
    min_width: int = 300

    def __init__(self, model: Model):
        super().__init__()
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
