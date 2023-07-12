from PyQt6.QtWidgets import QMainWindow, QSizePolicy, QWidget, QStackedLayout, QDialog, QMenu, QProgressDialog
from photo_lib.gui.model import Model
from photo_lib.gui.compare_widget import CompareRoot
from photo_lib.gui.image_container import ResizingImage
from photo_lib.gui.modals import DateTimeModal, FolderSelectModal, TaskSelectModal, ButtonType
from photo_lib.gui.media_pane import MediaPane
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from typing import Union


# TODO
#  - Session storage
#  - Config Storage
#  - Logging

# TODO Features
#  - Highlighting for the currently selected media-pane when shortcut is activated.
#  - Time line selection
#  - Images in windows needed at some point
#  - No import required, just list the images in folders
#  - Verify integrity of images
#  - Multi-database support... Future.


class RootWindow(QMainWindow):
    model:  Model
    dummy_center: QWidget
    stacked_layout: QStackedLayout

    # Fill Screen Image
    full_screen_image: ResizingImage = None

    # Compare stuff
    compare_root: CompareRoot

    # Folder Select Modal
    folder_select: Union[FolderSelectModal, None] = None

    # Change Datetime Modal
    datetime_modal: Union[None, DateTimeModal] = None

    commit_submenu: Union[None, QMenu] = None
    mark_submenu: Union[None, QMenu] = None

    # Actions
    open_folder_select_action: QAction
    search_duplicates_action: QAction

    progress_dialog: Union[QProgressDialog, None] = None

    def __init__(self):
        super().__init__()

        # Object Instantiation
        self.model = Model()

        self.dummy_center = QWidget()
        self.stacked_layout = QStackedLayout()
        self.compare_root = CompareRoot(self.model, open_image_fn=self.open_image,
                                        open_datetime_modal_fn=self.open_datetime_modal)

        # TODO Need session storage for databases.
        # Generating the remaining widgets
        self.compare_root.load_elements()

        # Top down adding of widgets and layouts
        self.setCentralWidget(self.dummy_center)

        self.dummy_center.setLayout(self.stacked_layout)
        self.dummy_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # self.dummy_center.setStyleSheet("background-color: #000000; color: #ffffff;")

        self.stacked_layout.addWidget(self.compare_root)
        self.stacked_layout.setCurrentWidget(self.compare_root)

        # Connecting the buttons of the modals

        # Misc setup of the window
        self.setWindowTitle("Picture Duplicate Manager")

        # Open the Folder Select Modal
        self.open_folder_select(init=True)

        # Open folder select action.
        self.open_folder_select_action = QAction("&Open Database Folder", self)
        self.open_folder_select_action.triggered.connect(self.open_folder_select)

        self.search_duplicates_action = QAction("&Search Duplicates", self)
        self.search_duplicates_action.triggered.connect(self.search_duplicates)
        self.search_duplicates_action.setToolTip("Start search for duplicates in the currently selected database.")

        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.open_folder_select_action)
        file_menu.addAction(self.search_duplicates_action)

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

    def open_image(self, path: str):
        """
        Open an image in full screen mode.
        :param path: path to the image
        :return:
        """
        if self.full_screen_image is None:
            self.full_screen_image = ResizingImage(path)
            self.full_screen_image.clicked.connect(self.open_compare_root)
            self.stacked_layout.addWidget(self.full_screen_image)
        else:
            self.full_screen_image.load_image(path)

        self.set_view(self.full_screen_image)

    def open_datetime_modal(self, media_pane: MediaPane):
        """
        Open the datetime modal.
        :param media_pane: Media pane to modify
        :return:
        """
        self.datetime_modal = DateTimeModal()
        self.datetime_modal.media_pane = media_pane
        print(media_pane.dbe.key)
        ret_val = self.datetime_modal.exec()

        if ret_val == 0 or self.datetime_modal.triggered_button == ButtonType.CLOSE:
            self.datetime_modal = None
            return

        assert ret_val == 1 and self.datetime_modal.triggered_button != ButtonType.NO_BUTTON, \
            "No button clicked but still accepted."

        # Apply or apply close button called -> apply the changes.
        assert self.datetime_modal.triggered_button in [ButtonType.APPLY, ButtonType.APPLY_CLOSE], \
            "Unknown button type button should be apply or apply close."
        try:
            self.model.try_rename_image(tag=self.datetime_modal.tag_input.text(), dbe=self.datetime_modal.media_pane.dbe,
                                        custom_datetime=self.datetime_modal.custom_datetime_input.text())
        except Exception as e:
            # self.error_popup.error_msg = f"Failed to update Datetime:\n {e}"
            # self.error_popup.open()
            print(f"Failed to update Datetime:\n {e}")

        media_pane.update_file_naming()

        if self.datetime_modal.triggered_button == ButtonType.APPLY_CLOSE:
            self.compare_root.remove_media_pane(self.datetime_modal.media_pane)

    def open_folder_select(self, init=False):
        """
        Open the folder select modal.
        :return:
        """
        self.folder_select = FolderSelectModal()

        # Connecting to the folder select modal
        self.folder_select.finished.connect(self.close_and_apply_folder)
        self.stacked_layout.addWidget(self.folder_select)

        if not init:
            self.set_view(self.folder_select)
        else:
            self.stacked_layout.setCurrentWidget(self.folder_select)

    def close_and_apply_folder(self, result):
        """
        Close the folder select modal and apply the new folder.
        :return:
        """
        # Load from new folder
        if result == QDialog.DialogCode.Accepted:
            self.compare_root.remove_all_elements()
            self.model.set_folder_path(self.folder_select.selectedFiles()[0])
            self.compare_root.load_elements()

        # elif result == QDialog.DialogCode.Rejected:
        #     pass

        self.open_compare_root()

    def set_view(self, target: Union[CompareRoot, FolderSelectModal, ResizingImage]):
        """
        Set the view to the target.
        :param target: Target to set the view to.
        :return:
        """
        current_view = self.stacked_layout.currentWidget()

        if type(current_view) is CompareRoot:
            self.close_compare_root()
        elif type(current_view) is FolderSelectModal:
            self.close_folder_select()
        elif type(current_view) is ResizingImage:
            self.close_full_screen_image()

        self.stacked_layout.setCurrentWidget(target)

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

        self.set_view(self.compare_root)

    def close_compare_root(self):
        """
        Close the compare root.
        :return:
        """
        print("Close")
        menubar = self.menuBar()
        menubar.removeAction(self.commit_submenu.menuAction())
        menubar.removeAction(self.mark_submenu.menuAction())
        self.commit_submenu = None
        self.mark_submenu = None

    def close_folder_select(self):
        """
        Close the folder select modal. Remove the current widget and add a new one. (In case of the Close button)
        :return:
        """

        # Clean up Folder Select
        self.stacked_layout.removeWidget(self.folder_select)
        self.folder_select.deleteLater()
        self.folder_select = None

    def close_full_screen_image(self):
        """
        Close the full screen image. If more needs to be changed other than just the view, this is the place to do it.
        :return:
        """
        pass