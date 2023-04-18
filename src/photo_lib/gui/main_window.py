from PyQt6.QtWidgets import QMainWindow, QScrollArea, QLabel, QMenu, QMenuBar, QStatusBar, QToolBar, QFileDialog, QHBoxLayout
from photo_lib.gui.model import Model
from photo_lib.gui.compare_widget import CompareRoot

class RootWindow(QMainWindow):
    model:  Model

    # Scrolling and CompareView
    sca: QScrollArea
    csl: CompareRoot

    def __init__(self):
        super().__init__()
        self.model = Model()
        self.sca = QScrollArea()
        self.csl = CompareRoot(self.model)

        self.sca.setWidget(self.csl)

        text = QLabel("Hello")
        self.setCentralWidget(self.csl)
        self.csl.load_elements()
        # self.setStatusBar(QStatusBar())


