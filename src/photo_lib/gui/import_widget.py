from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QFrame
from PyQt6.QtGui import QResizeEvent, QAction, QIcon, QKeySequence
from photo_lib.gui.model import Model

class ImportWidget(QFrame):
    model: Model
    container: QVBoxLayout

    button_dummy: QLabel
    button_layout: QHBoxLayout
    scroll_area: QScrollArea
    child_dummy: QLabel

    import_btn: QPushButton
    import_and_close: QPushButton
    close: QPushButton

    import_action: QAction

    def __init__(self, model: Model):
        super().__init__()
        self.model = model

        self.container = QVBoxLayout()
        self.button_layout = QHBoxLayout()
        self.scroll_area = QScrollArea()
        self.child_dummy = QLabel()
        self.button_dummy = QLabel()

        self.setLayout(self.container)

        self.container.addWidget(self.scroll_area)
        self.container.addWidget(self.button_dummy)

        self.scroll_area.setWidget(self.child_dummy)