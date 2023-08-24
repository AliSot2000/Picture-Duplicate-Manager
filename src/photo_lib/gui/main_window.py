from PyQt6.QtWidgets import QMainWindow, QSizePolicy, QWidget, QStackedLayout, QDialog, QMenu, QProgressDialog, QLabel, QMessageBox
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtCore import Qt, QTimer

from photo_lib.gui.model import Model
from photo_lib.gui.compare_widget import CompareRoot
from photo_lib.gui.zoom_image import ZoomImage
from photo_lib.gui.big_screen import BigScreen
from photo_lib.gui.import_view import ImportView
from photo_lib.gui.modals import DateTimeModal, FolderSelectModal, TaskSelectModal, ButtonType, PrepareImportDialog
from photo_lib.gui.media_pane import MediaPane
from photo_lib.gui.import_table_view import ImportTableList
from photo_lib.data_objects import ProcessComType, Progress, Views, LongRunningActions
from typing import Union


# TODO
#  - Session storage
#  - Config Storage
#  - Logging

# TODO Features
#  - Time line selection
#  - Images in windows needed at some point
#  - No import required, just list the images in folders
#  - Verify integrity of images
#  - Multi-database support... Future.


class RootWindow(QMainWindow):
    model:  Model
    dummy_center: QWidget
    stacked_layout: QStackedLayout

    # Views
    __current_view: Views = None
    full_screen_image: ZoomImage = None
    compare_root: CompareRoot
    import_table_list: ImportTableList
    no_db_selected: QLabel = None
    import_tiles: ImportView
    import_big_screen: BigScreen

    # Menus and Submenus
    commit_submenu: Union[None, QMenu] = None
    mark_submenu: Union[None, QMenu] = None
    file_submenu: Union[None, QMenu] = None
    view_submenu: Union[None, QMenu] = None
    full_screen_image_menu: Union[None, QMenu] = None

    # Actions
    search_duplicates_action: QAction
    close_full_screen_image_action: QAction

    # View actions
    open_import_tables_view_action: QAction
    open_compare_view_action: QAction

    # Modal actions
    open_import_dialog_action: QAction
    open_folder_select_modal_action: QAction

    # Progress Dialog
    progress_dialog: Union[QProgressDialog, None] = None
    progress_updater: Union[QTimer, None] = None

    long_running_process_type: Union[LongRunningActions, None] = None

    @property
    def current_view(self):
        return self.__current_view

    def __init__(self):
        super().__init__()

        # Object Instantiation
        self.model = Model()

        self.dummy_center = QWidget()
        self.stacked_layout = QStackedLayout()
        self.compare_root = CompareRoot(self.model, open_image_fn=self.open_image_in_full_screen,
                                        open_datetime_modal_fn=self.open_datetime_modal)

        self.no_db_selected = QLabel("You have no database selected. Please select a database.")
        self.no_db_selected.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_db_selected.setStyleSheet(f"background: rgb(255, 200, 200); font-size: 20px;")

        self.import_tiles = ImportView(model=self.model)
        self.import_big_screen = BigScreen(model=self.model)
        self.import_table_list = ImportTableList(model=self.model)

        # TODO Need session storage for databases.
        # Top down adding of widgets and layouts
        self.setCentralWidget(self.dummy_center)

        self.dummy_center.setLayout(self.stacked_layout)
        self.dummy_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # self.dummy_center.setStyleSheet("background-color: #000000; color: #ffffff;")

        self.stacked_layout.addWidget(self.compare_root)
        self.stacked_layout.setCurrentWidget(self.compare_root)
        self.stacked_layout.addWidget(self.no_db_selected)
        self.stacked_layout.setCurrentWidget(self.no_db_selected)
        self.stacked_layout.addWidget(self.import_table_list)
        self.__current_view = Views.Message_Label

        # Connecting the buttons of the modals

        # Misc setup of the window
        self.setWindowTitle("Picture Duplicate Manager")

        # Open folder select action.
        self.open_folder_select_action = QAction("&Open Database Folder", self)
        self.open_folder_select_action.triggered.connect(self.open_folder_select_modal)

        self.search_duplicates_action = QAction("&Search Duplicates", self)
        self.search_duplicates_action.triggered.connect(self.search_duplicates)
        self.search_duplicates_action.setToolTip("Start search for duplicates in the currently selected database.")

        self.close_full_screen_image_action = QAction("&Close Image", self)
        self.close_full_screen_image_action.triggered.connect(self.open_compare_root)
        self.close_full_screen_image_action.setToolTip("Close full screen view of image")
        self.close_full_screen_image_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))

        self.open_import_dialog_action = QAction("&Import", self)
        self.open_import_dialog_action.triggered.connect(self.open_import_dialog)
        self.open_import_dialog_action.setToolTip("Open the import dialog.")
        self.open_import_dialog_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_I))

        self.build_file_menu()

        # Open the Folder Select Modal
        self.open_folder_select_modal()

    def build_file_menu(self):
        """
        Build the file menu.
        :return:
        """
        if self.file_submenu is not None:
            self.menuBar().removeAction(self.file_submenu.menuAction())
            self.file_submenu.deleteLater()

        self.file_submenu = self.menuBar().addMenu("&File")
        self.file_submenu.addAction(self.open_folder_select_action)

        if self.model.db_loaded():
            self.file_submenu.addSeparator()
            self.file_submenu.addAction(self.search_duplicates_action)
            self.file_submenu.addAction(self.open_import_dialog_action)

    def open_import_dialog(self):
        """
        Open the import dialog.
        :return:
        """
        pass

    def search_duplicates(self):
        """
        Search for duplicates in the currently selected database.
        :return:
        """
        modal = TaskSelectModal(model=self.model)
        ret_val = modal.exec()

        # if the val is 0 -> cancle was clicked.
        if ret_val == 0:
            return

        # There may not really be another type of return value.
        assert ret_val == 1, f"Unknown return value from TaskSelectModal of {ret_val}"

        success, pipe = self.model.search_duplicates()

        if not success:
            print("No success")
            return

        if pipe is None:
            self.open_compare_root()
            self.compare_root.load_elements()
            self.model.search_level = None

        else:
            pass
            # self.progress_dialog = QProgressDialog("Searching for duplicates...", "Cancel", 0, 0, self)
            # self.progress_dialog.setWindowModality(2)
            # self.progress_dialog.setCancelButton(None)
            # self.progress_dialog.show()
            #
            # pipe.progress.connect(self.progress_dialog.setValue)
            # pipe.finished.connect(self.search_finished)

    def open_image_in_full_screen(self, path: str):
        """
        Open an image in full screen mode.
        :param path: path to the image
        :return:
        """
        self.build_file_menu()
        if self.full_screen_image is None:
            self.full_screen_image = ZoomImage()
            self.full_screen_image.file_path = path
            self.stacked_layout.addWidget(self.full_screen_image)
        else:
            self.full_screen_image.file_path = path

        menu_bar = self.menuBar()
        if self.full_screen_image_menu is None:
            self.full_screen_image_menu = menu_bar.addMenu("&Image")
            self.full_screen_image_menu.addAction(self.close_full_screen_image_action)

        self.set_view(Views.Full_Screen_Image)

    def open_datetime_modal(self, media_pane: MediaPane):
        """
        Open the datetime modal.
        :param media_pane: Media pane to modify
        :return:
        """
        datetime_modal = DateTimeModal()
        datetime_modal.media_pane = media_pane
        print(media_pane.dbe.key)
        ret_val = datetime_modal.exec()

        if ret_val == 0 or datetime_modal.triggered_button == ButtonType.CLOSE:
            return

        assert ret_val == 1 and datetime_modal.triggered_button != ButtonType.NO_BUTTON, \
            "No button clicked but still accepted."

        # Apply or apply close button called -> apply the changes.
        assert datetime_modal.triggered_button in [ButtonType.APPLY, ButtonType.APPLY_CLOSE], \
            "Unknown button type button should be apply or apply close."
        try:
            self.model.try_rename_image(tag=datetime_modal.tag_input.text(), dbe=datetime_modal.media_pane.dbe,
                                        custom_datetime=datetime_modal.custom_datetime_input.text())
        except Exception as e:
            # self.error_popup.error_msg = f"Failed to update Datetime:\n {e}"
            # self.error_popup.open()
            print(f"Failed to update Datetime:\n {e}")

        media_pane.update_file_naming()

        if datetime_modal.triggered_button == ButtonType.APPLY_CLOSE:
            self.compare_root.remove_media_pane(datetime_modal.media_pane)

    def close_message_label(self):
        """
        Need to update the menu entries...
        :return:
        """
        pass

    def open_folder_select_modal(self):
        """
        Open the folder select modal.
        :return:
        """
        folder_select = FolderSelectModal()
        res = folder_select.exec()

        if res == QDialog.DialogCode.Accepted:
            self.model.set_folder_path(folder_select.selectedFiles()[0])

            if self.model.db_loaded():
                self.compare_root.remove_all_elements()
                self.compare_root.load_elements()
                self.open_compare_root()

            else:
                msg_bx = QMessageBox(QMessageBox.Icon.Critical, "Error", "The Folder you selected was not a valid database", QMessageBox.StandardButton.Ok)
                msg_bx.exec()
                self.stacked_layout.setCurrentWidget(self.no_db_selected)

    def set_view(self, target: Views):
        """
        Set the view to the target.
        :param target: Target to set the view to.
        :return:
        """
        if self.__current_view == Views.Deduplicate_Compare:
            self.close_compare_root()
        elif self.__current_view == Views.Full_Screen_Image:
            self.close_full_screen_image()
        elif self.__current_view == Views.Message_Label:
            self.close_message_label()

        if target == Views.Deduplicate_Compare:
            self.stacked_layout.setCurrentWidget(self.compare_root)
        elif target == Views.Full_Screen_Image:
            self.stacked_layout.setCurrentWidget(self.full_screen_image)
        elif target == Views.Message_Label:
            self.stacked_layout.setCurrentWidget(self.no_db_selected)

        self.__current_view = target

    def open_compare_root(self):
        """
        Open the compare root.
        :return:
        """
        self.build_file_menu()
        menu_bar = self.menuBar()
        if self.commit_submenu is None:
            self.commit_submenu = menu_bar.addMenu("&Commit")
            self.commit_submenu.addAction(self.compare_root.next_action)
            self.commit_submenu.addSeparator()
            self.commit_submenu.addAction(self.compare_root.commit_selected)
            self.commit_submenu.addAction(self.compare_root.commit_all)

        if self.mark_submenu is None:
            self.mark_submenu = menu_bar.addMenu("&Mark")
            self.mark_submenu.addAction(self.compare_root.mark_delete_action)
            self.mark_submenu.addAction(self.compare_root.set_main_action)
            self.mark_submenu.addAction(self.compare_root.change_tag_action)
            self.mark_submenu.addAction(self.compare_root.remove_media_action)
            self.mark_submenu.addAction(self.compare_root.move_left_action)
            self.mark_submenu.addAction(self.compare_root.move_right_action)

        self.set_view(Views.Deduplicate_Compare)

    def close_compare_root(self):
        """
        Close the compare root.
        :return:
        """
        menubar = self.menuBar()
        menubar.removeAction(self.commit_submenu.menuAction())
        menubar.removeAction(self.mark_submenu.menuAction())
        self.commit_submenu = None
        self.mark_submenu = None

    def close_full_screen_image(self):
        """
        Close the full screen image. If more needs to be changed other than just the view, this is the place to do it.
        :return:
        """

        menubar = self.menuBar()
        menubar.removeAction(self.full_screen_image_menu.menuAction())
        self.full_screen_image_menu = None