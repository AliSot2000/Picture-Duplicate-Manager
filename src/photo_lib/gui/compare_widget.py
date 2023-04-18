from PyQt6.QtWidgets import QHBoxLayout, QWidget, QLabel, QPushButton
from photo_lib.gui.model import Model
from typing import List
from photo_lib.gui.image_pane import MediaPane


class CompareRoot(QWidget):
    model: Model
    layout: QHBoxLayout
    media_panes: List[MediaPane]

    def __init__(self, model: Model):
        super().__init__()
        self.model = model
        self.layout = QHBoxLayout()
        self.media_panes = []

        self.setLayout(self.layout)

    def load_elements(self):
        """
        Goes through the model and fetches all the present files. Adds all files to the view.

        :return:
        """
        if self.layout.count() > 0:
            self.remove_all_elements()

        # Go through all DatabaseEntries, generate a MediaPane from each one and add the panes to the layout.
        for dbe in self.model.files:
            pane = MediaPane(self.model, dbe)
            self.media_panes.append(pane)
            self.layout.addWidget(pane)
            # pane.show()

    def remove_all_elements(self):
        """
        Removes all the widgets from the layout and deletes them.

        :return:
        """
        for element in self.media_panes:
            self.layout.removeWidget(element)
            element.deleteLater()

        self.media_panes = []


