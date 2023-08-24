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
    messageg_label: QLabel = None
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

        self.messageg_label = QLabel("You have no database selected. \nPlease select a database.")
        self.messageg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.messageg_label.setStyleSheet(f"background: rgb(255, 200, 200); font-size: 20px;")

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
        self.stacked_layout.addWidget(self.messageg_label)
        self.stacked_layout.setCurrentWidget(self.messageg_label)
        self.stacked_layout.addWidget(self.import_table_list)
        self.__current_view = Views.Message_Label

        # Connecting the buttons of the modals

        # Misc setup of the window
        self.setWindowTitle("Picture Duplicate Manager")

        # Open folder select action.
        self.open_folder_select_modal_action = QAction("&Open Database Folder", self)
        self.open_folder_select_modal_action.triggered.connect(self.open_folder_select_modal)

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

        self.open_import_tables_view_action = QAction("Import &Tables", self)
        self.open_import_tables_view_action.triggered.connect(self.open_import_tables_view)
        self.open_import_tables_view_action.setToolTip("Open the import tables view.")
        self.open_import_tables_view_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_3))

        self.open_compare_view_action = QAction("&Compare View", self)
        self.open_compare_view_action.triggered.connect(self.open_compare_root)
        self.open_compare_view_action.setToolTip("Open the compare view.")
        self.open_compare_view_action.setShortcut(QKeySequence(Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_1))

        self.build_file_menu()
        self.build_view_submenu()

        # Open the Folder Select Modal
        self.open_folder_select_modal()

    def build_view_submenu(self):
        """
        Build the view submenu - Only add the possible views.
        :return:
        """
        # No view if no database is loaded.
        if not self.model.db_loaded():
            if self.view_submenu is not None:
                self.menuBar().removeAction(self.view_submenu.menuAction())

            return

        # The database is loaded
        # We remove the menu and rebuild it to make sure we cannot open the currently open view.
        if self.view_submenu is not None:
            self.menuBar().removeAction(self.view_submenu.menuAction())

        # We have an import in progress, we cannot open anything else.
        if self.current_view == Views.Import_Tile_View or self.current_view == Views.Import_Big_Screen_View:
            pass

        else:
            self.view_submenu = self.menuBar().addMenu("&View")
            if self.current_view != Views.Import_Tables_View:
                self.view_submenu.addAction(self.open_import_tables_view_action)
            if self.current_view != Views.Deduplicate_Compare:
                self.view_submenu.addAction(self.open_compare_view_action)


    def build_file_menu(self):
        """
        Build the file menu.
        :return:
        """
        if self.file_submenu is not None:
            self.menuBar().removeAction(self.file_submenu.menuAction())
            self.file_submenu.deleteLater()

        self.file_submenu = self.menuBar().addMenu("&File")
        self.file_submenu.addAction(self.open_folder_select_modal_action)

        if self.model.db_loaded():
            self.file_submenu.addSeparator()
            self.file_submenu.addAction(self.search_duplicates_action)
            self.file_submenu.addAction(self.open_import_dialog_action)

    def open_import_dialog(self):
        """
        Open the import dialog.
        :return:
        """
        # Don't open anything if no db is loaded.
        if not self.model.db_loaded():
            return

        while True:
            modal = PrepareImportDialog(model=self.model)
            ret_val = modal.exec()

            # Don't proceed if no accept was clicked.
            if ret_val == QDialog.DialogCode.Rejected:
                return

            # If the user clicked the close button, don't proceed.
            assert ret_val == QDialog.DialogCode.Accepted, "Unknown return value from PrepareImportDialog"

            allowed_ext_str = modal.extensions
            folder_path = modal.folder_label.text()
            description = modal.description_input.text()

            try:
                self.model.new_import(folder=folder_path, allowed_ext=allowed_ext_str, description=description)
                break
            except Exception as e:
                error = QMessageBox(QMessageBox.Icon.Critical,
                                    "Error",
                                    str(e),
                                    QMessageBox.StandardButton.Ok)
                error.exec()

        # Create modal for the import.
        self.progress_dialog = QProgressDialog("Importing...", "Cancel", 0, 100, self)
        self.progress_dialog.show()
        self.progress_dialog.canceled.connect(self.terminate_long_running_process)
        self.progress_updater = QTimer(self)
        self.progress_updater.timeout.connect(self.update_progress)
        self.progress_updater.start(200)

        # Waiting for the thing to stop
        self.long_running_process_type = LongRunningActions.PrepareImport

    def terminate_long_running_process(self):
        """
        If a long-running process is active, terminate it.
        :return:
        """
        if self.model.handle is not None and self.model.handle.is_alive():
            self.model.stop_process()
            self.progress_dialog.close()

    def long_process_exit_handler(self):
        """
        Handle the different type of long-running processes and open the appropriate view afterwards.
        :return:
        """
        if self.long_running_process_type is None:
            return

        abort = self.model.recover_long_running_process()
        self.long_running_process_type = None

        if self.long_running_process_type == LongRunningActions.Import_Images:
            if abort:
                self.open_import_tables_view()
                return
            self.build_import_views()

    def update_progress(self):
        """
        Update progress with the progress dialog.
        :return:
        """
        if self.model.gui_com.poll():
            msg: Progress = self.model.gui_com.recv()

            # Message, update the message
            if msg.type == ProcessComType.MESSAGE:
                self.progress_dialog.setLabelText(msg.value)

            if msg.type == ProcessComType.MAX:
                self.progress_dialog.setMaximum(msg.value)

            if msg.type == ProcessComType.CURRENT:
                self.progress_dialog.setValue(msg.value)

            if msg.type == ProcessComType.EXIT:
                self.progress_dialog.close()

        if not self.model.handle.is_alive():
            self.progress_updater.stop()
            self.progress_updater.deleteLater()
            self.progress_updater = None
            self.progress_dialog.close()

            self.long_process_exit_handler()

    def build_import_views(self):
        """
        Build the import views.
        :return:
        """
        # Add Submenu
        # Build Layouts
        # Connect the actions
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
                self.stacked_layout.setCurrentWidget(self.messageg_label)

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
        elif self.__current_view == Views.Import_Tables_View:
            self.close_import_tables_view()

        if target == Views.Deduplicate_Compare:
            self.stacked_layout.setCurrentWidget(self.compare_root)
        elif target == Views.Full_Screen_Image:
            self.stacked_layout.setCurrentWidget(self.full_screen_image)
        elif target == Views.Message_Label:
            self.stacked_layout.setCurrentWidget(self.messageg_label)
        elif target == Views.Import_Tables_View:
            self.stacked_layout.setCurrentWidget(self.import_table_list)

        self.__current_view = target
        self.build_view_submenu()
        self.build_file_menu()




    # ------------------------------------------------------------------------------------------------------------------
    # Opening handler functions - handle the opening of a specific view and add the associated submenus.
    # ------------------------------------------------------------------------------------------------------------------

    def open_message_label(self, text: str = None):
        """
        Opens the message label view.
        :return:
        """
        if text is None:
            text = "You have no database selected. \nPlease select a database."

        self.messageg_label.setText(text)
        self.set_view(Views.Message_Label)

    def open_compare_root(self):
        """
        Open the compare root.
        :return:
        """
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

    def open_image_in_full_screen(self, path: str):
        """
        Open an image in full screen mode.
        :param path: path to the image
        :return:
        """
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

    def open_import_tables_view(self):
        """
        Open the import tables view.
        (Add Submenus here)
        :return:
        """
        self.import_table_list.fetch_tables()
        self.set_view(Views.Import_Tables_View)

    # ------------------------------------------------------------------------------------------------------------------
    # Closing handler functions - handle the closing of a specific view and remove the associated submenus.
    # ------------------------------------------------------------------------------------------------------------------

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

    def close_message_label(self):
        """
        (Currently empty, use to remove submenus for the message label)
        :return:
        """
        pass

    def close_import_tables_view(self):
        """
        Close the import tables view. (Currently empty -  remove submenues here)
        :return:
        """
        pass