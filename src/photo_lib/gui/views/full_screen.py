from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QApplication, QMenuBar

from photo_lib.data_objects import MediaPaths
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.temp_new_wigets.new_zoomable_image import ZoomImage


class FullScreenView(QDialog):
    def __init__(self, model: UIModel, mp: MediaPaths, mbh: int):
        """
        The new variant of the BaseImage doesn't allow reusing the widget anymore. With every new MediaPaths a new
        object needs to be instantiated.

        PRECONDITION: The Parent exists in the database.

        :param mp: MediaPaths object to load the image from
        :param model: UIModel to use for the the config
        :param mbh: Menu bar height.
        """
        # Set up the dialog
        super().__init__()
        self.setModal(True)

        # Create the Image
        self.main_widget = ZoomImage(model=model, mp=mp)

        # Create the actions for the widget
        self.close_action = QAction("&Close", self)
        self.close_action.setToolTip("Close the full screen view of the image")
        self.close_action.triggered.connect(self.close)
        self.close_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))

        self.reset_action = QAction("&Reset", self)
        self.reset_action.setToolTip("Reset the zoom and position of the image")
        self.reset_action.triggered.connect(self.main_widget.reset_image)
        self.reset_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_R))

        # Populate the Menubar
        self.menu_bar = QMenuBar()
        self.menu_bar.setFixedHeight(mbh)

        self.view_menu = self.menu_bar.addMenu("&View")
        self.view_menu.addAction(self.close_action)
        self.view_menu.addAction(self.reset_action)

        # INFO: Don't set the parent of the layout
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.layout.addWidget(self.menu_bar)
        self.layout.addWidget(self.main_widget)
        self.setLayout(self.layout)

        self.resize(QApplication.primaryScreen().size())
