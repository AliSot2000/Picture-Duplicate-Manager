from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QFrame
from PyQt6.QtGui import QResizeEvent, QAction, QIcon, QKeySequence
from PyQt6.QtCore import Qt
from photo_lib.gui.model import Model, NoDbException
from photo_lib.gui.media_pane import MediaPane
from photo_lib.gui.text_scroll_area import TextScroller
from photo_lib.gui.button_bar import ButtonBar
from photo_lib.gui.gui_utils import button_wrapper, pain_wrapper, path_wrapper

from typing import Callable, List
import warnings


class CompareRoot(QFrame):
    model: Model
    media_layout: QHBoxLayout
    media_panes: List[MediaPane]
    min_width: int = 300
    min_height = 870

    __updating_buttons: bool = False
    __message_set: bool = False
    auto_load: bool = True

    open_image_fn: Callable
    open_datetime_modal_fn: Callable

    scroll_area: QScrollArea
    media_panes_placeholder: QLabel
    compare_layout: QVBoxLayout
    button_bar: ButtonBar

    # Actions related to duplicate cluster.
    next_action: QAction
    commit_selected: QAction
    commit_all: QAction

    # Actions related to a single image
    set_main_action: QAction
    mark_delete_action: QAction
    change_tag_action: QAction
    remove_media_action: QAction

    # using ScrollView
    using_scroll_view: bool = True

    target_panes: List[MediaPane] = None

    message_label: QLabel = None

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
        self.media_panes = []

        # Instantiating the widgets
        self.media_panes_placeholder = QLabel()
        self.compare_layout = QVBoxLayout()
        self.media_layout = QHBoxLayout()
        self.scroll_area = QScrollArea()
        self.button_bar = ButtonBar()
        self.message_label = QLabel()

        # Creating the widget hierarchy
        self.setLayout(self.compare_layout)

        self.compare_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_layout.setSpacing(0)
        self.compare_layout.addWidget(self.scroll_area)
        self.compare_layout.addWidget(self.button_bar)

        self.scroll_area.setWidget(self.media_panes_placeholder)

        self.media_panes_placeholder.setLayout(self.media_layout)
        # self.media_panes_placeholder.setStyleSheet("background-color: darkGrey;")
        self.media_panes_placeholder.setContentsMargins(0, 0, 0, 0)

        # Actions, create actions and add them to the buttons.
        self.next_action = QAction("Next Cluster", self)
        self.commit_selected = QAction("Commit Selected", self)
        self.commit_all = QAction("Commit All", self)
        self.__init_commit_actions()

        self.mark_delete_action = QAction("Mark for Deletion", self)
        self.set_main_action = QAction("Set as Main", self)
        self.change_tag_action = QAction("Change Tag", self)
        self.remove_media_action = QAction("Remove from Cluster", self)
        self.move_left_action = QAction("Move the target pane to the left", self)
        self.move_right_action = QAction("Move the target pane to the right", self)
        self.__init_pane_actions()

        self.setMinimumHeight(500)
        self.setMinimumWidth(500)
        self.media_panes_placeholder.setMinimumHeight(870)
        self.update_duplicate_count()

        # Setting dimensions of message label
        self.message_label.setMinimumSize(300, 30)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def __init_commit_actions(self):
        """
        Set all necessary callbacks and attributes of the actions that commit or skip the current cluster.
        :return:
        """
        self.next_action.triggered.connect(self.skip_entry)
        self.next_action.triggered.connect(self.update_duplicate_count)
        self.next_action.setShortcut(QKeySequence("CTRL+D"))

        self.commit_selected.triggered.connect(lambda : self.mark_duplicates_from_gui(selected=True))
        self.commit_selected.triggered.connect(self.update_duplicate_count)
        self.commit_selected.setShortcut(QKeySequence("CTRL+S"))

        self.commit_all.triggered.connect(lambda : self.mark_duplicates_from_gui(selected=False))
        self.commit_all.triggered.connect(self.update_duplicate_count)
        self.commit_all.setShortcut(QKeySequence("CTRL+A"))

        # Adding the actions to the buttons.
        self.button_bar.next_button.target_action = self.next_action
        self.button_bar.commit_selected.target_action = self.commit_selected
        self.button_bar.commit_all.target_action = self.commit_all

    def __init_pane_actions(self):
        self.mark_delete_action.triggered.connect(self.mark_target_delete)
        self.mark_delete_action.setShortcut(QKeySequence("D"))

        self.set_main_action.triggered.connect(self.set_target_main)
        self.set_main_action.setShortcut(QKeySequence("S"))

        self.change_tag_action.triggered.connect(self.change_target_tag)
        self.change_tag_action.setShortcut(QKeySequence("C"))

        self.remove_media_action.triggered.connect(self.remove_target_from_cluster)
        self.remove_media_action.setShortcut(QKeySequence("X"))

        self.move_left_action.triggered.connect(self.move_left_action_handler)
        # self.move_left_action.setShortcut(QKeySequence(Qt.Key.Key_Left + Qt.Key.Key_Control))
        self.move_left_action.setShortcut(QKeySequence("W"))

        self.move_right_action.triggered.connect(self.move_right_action_handler)
        # self.move_right_action.setShortcut(QKeySequence(Qt.Key.Key_Right + Qt.Key.Key_Control))
        self.move_right_action.setShortcut(QKeySequence("E"))

    def mark_target_delete(self):
        """
        Go through target panes and trigger a click on the delete_button
        :return:
        """
        for target in self.target_panes:
            target: MediaPane
            target.delete_button.click()

    def set_target_main(self):
        """
        Go through target panes and trigger a click on the main_button
        :return:
        """
        to_del = []
        for target in self.target_panes:
            target: MediaPane
            try:
                target.main_button.click()
            except RuntimeError:
                to_del.append(target)

        for target in to_del:
            self.target_panes.remove(target)

    def change_target_tag(self):
        """
        Go through target panes and trigger a click on the change_tag_button
        :return:
        """
        to_del = []
        for target in self.target_panes:
            target: MediaPane
            try:
                target.change_tag_button.click()
            except RuntimeError:
                to_del.append(target)

        for target in to_del:
            self.target_panes.remove(target)

    def remove_target_from_cluster(self):
        """
        Go through target panes and trigger a click on the remove_media_button
        :return:
        """
        to_del = []
        for target in self.target_panes:
            target: MediaPane
            try:
                target.remove_media_button.click()
            except RuntimeError:
                to_del.append(target)

        for target in to_del:
            self.target_panes.remove(target)

    def load_elements(self) -> bool:
        """
        Goes through the model and fetches all the present files. Adds all files to the view.

        :return: (If duplicates were available to be loaded)
        """
        if self.media_layout.count() > 0:
            return False

        got_rows = self.model.fetch_duplicate_row()
        self.clear_message()


        # Query new files from the db.
        if not got_rows:
            self.set_empty_duplicates()
            return False

        # Go through all DatabaseEntries, generate a MediaPane from each one and add the panes to the layout.
        for dbe in self.model.files:
            pane = MediaPane(self.model, dbe, self.synchronized_scroll,
                             move_right=self.move_right,
                             move_left=self.move_left)
            self.media_panes.append(pane)
            self.media_layout.addWidget(pane)

        # Attaching  Buttons
        for pane in self.media_panes:
            pane.main_button.clicked.connect(button_wrapper(pane.main_button, self.button_state))
            pane.remove_media_button.clicked.connect(pain_wrapper(pane, self.remove_media_pane))
            pane.media.clicked.connect(path_wrapper(pane.media.file_path, self.open_image_fn))
            pane.change_tag_button.clicked.connect(pain_wrapper(pane, self.open_datetime_modal_fn))

            # Add functions for the adding and removing of the target.
            pane.set_callback = self.set_target
            pane.remove_callback = self.remove_target

        self.set_max_width_of_placeholder()
        self.maintain_visibility()

        self.set_arrow_enable(self.media_panes[0])
        self.set_arrow_enable(self.media_panes[-1])

        self.auto_set_buttons()
        self.color_widgets()
        self.update_duplicate_count()
        return True

    def set_max_width_of_placeholder(self):
        """
        Update the size of the media_panes_placeholder according to the number of files currently selected.
        :return:
        """
        self.media_panes_placeholder.setMinimumWidth(len(self.model.files) * 370 + 10)

    def remove_all_elements(self):
        """
        Removes all the widgets from the layout and deletes them.

        :return:
        """
        for element in self.media_panes:
            self.media_layout.removeWidget(element)
            element.deleteLater()

        self.target_panes = []
        self.media_panes = []
        try:
            self.model.clear_files()
        except NoDbException:
            pass
        self.maintain_visibility()

    def remove_media_pane(self, media_pane: MediaPane):
        """
        Removes the given MediaPane from the layout and deletes it.

        :param media_pane: The MediaPane to remove.
        :return:
        """
        self.media_layout.removeWidget(media_pane)
        media_pane.deleteLater()
        self.media_panes.remove(media_pane)
        self.model.remove_file(media_pane.dbe)

        if len(self.media_panes) == 0 and self.auto_load:
            self.model.clear_files()
            self.load_elements()

        self.remove_target(media_pane)
        self.maintain_visibility()
        self.set_max_width_of_placeholder()
        # Remove Media Pane may not call self.color_widgets() because the database is already updated while the gui
        # is not. The key is already removed from the table in the database but the gui still has it. This would
        # lead to an error in the compare files function.

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
        if self.__updating_buttons:
            return

        self.__updating_buttons = True
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

        self.__updating_buttons = False

    def auto_set_buttons(self):
        """
        Automatically sets the main buttons of the MediaPanes to the correct state.
        :return:
        """
        if len(self.media_panes) != 2:
            return

        widget_a: MediaPane = self.media_panes[0]
        widget_b: MediaPane = self.media_panes[1]
        fsize_a_type = type(widget_a.dbe.metadata.get("File:FileSize"))
        fsize_b_type = type(widget_b.dbe.metadata.get("File:FileSize"))
        assert fsize_a_type is int, f"FileSize of a not of expected type int but {fsize_a_type}"
        assert fsize_b_type is int, f"FileSize of b not of expected type int but {fsize_b_type}"

        # Two files differing only in file size
        if widget_a.dbe.metadata.get("File:FileSize")\
                > widget_b.dbe.metadata.get("File:FileSize"):
            widget_a.main_button.setChecked(True)
            widget_b.delete_button.setChecked(True)
        elif widget_a.dbe.metadata.get("File:FileSize")\
                < widget_b.dbe.metadata.get("File:FileSize"):
            widget_b.main_button.setChecked(True)
            widget_a.delete_button.setChecked(True)

        # Two files identical but different dates.
        elif widget_a.dbe.metadata.get("File:FileSize")\
                == widget_b.dbe.metadata.get("File:FileSize") and \
                widget_a.dbe.datetime < widget_b.dbe.datetime:
            widget_a.main_button.setChecked(True)
            widget_b.delete_button.setChecked(True)

        elif widget_a.dbe.metadata.get("File:FileSize")\
                == widget_b.dbe.metadata.get("File:FileSize") and \
                widget_a.dbe.datetime > widget_b.dbe.datetime:
            widget_b.main_button.setChecked(True)
            widget_a.delete_button.setChecked(True)

    def update_duplicate_count(self):
        """
        Update the duplicate count in the button bar.
        :return:
        """
        try:
            duplicates_to_go = self.model.pdb.get_duplicate_table_size()
        except AttributeError:
            duplicates_to_go = "?"
        self.button_bar.status.setText(f"Remaining Duplicates: {duplicates_to_go}")

    def mark_duplicates_from_gui(self, selected: bool = True):
        """
        Function to commit the selection of duplicates to the database.
        :param selected: if only the with delete selected images should be marked as duplicates or all elements.
        :return:
        """
        if len(self.media_panes) == 0:
            self.load_elements()
            return

        main_entry: MediaPane = None
        for_duplicates: List[MediaPane] = []

        for entry in self.media_panes:
            if entry.main_button.isChecked():
                main_entry = entry
            # Add the entry to the list of duplicates if the delete button is checked or if 'commit all' is called and
            # any other entry except the main is considered a duplicate.
            elif entry.delete_button.isChecked() or not selected:
                for_duplicates.append(entry)

        # remove all ComparePanes and repopulate
        if main_entry is None:
            warnings.warn("No main entry selected.")
            return

        # At least one duplicate to remove.
        if len(for_duplicates) == 0:
            return

        self.model.mark_duplicates(main_entry.dbe, [entry.dbe for entry in for_duplicates])

        # Remove the processed elements from the gui.
        self.remove_media_pane(main_entry)
        for entry in for_duplicates:
            self.remove_media_pane(entry)

        if self.model.current_row is not None:
            self.color_widgets()

    def skip_entry(self):
        """
        Skip the current duplicates cluster. For this, remove all elements and load the next cluster. Removing all
        elements already entails deleting the current row from the database.
        :return:
        """
        self.remove_all_elements()
        self.load_elements()

    def resizeEvent(self, a0: QResizeEvent) -> None:
        """
        Propagate the resizing down even though there is a scroll view.
        :param a0: size event
        :return:
        """
        super().resizeEvent(a0)
        if a0.size().width() > self.media_panes_placeholder.minimumWidth():
            self.media_panes_placeholder.setMaximumWidth(a0.size().width())
        else:
            self.media_panes_placeholder.setMaximumWidth(self.media_panes_placeholder.minimumWidth())

        if self.using_scroll_view:
            new_width = a0.size().width() - self.scroll_area.verticalScrollBar().width()
            new_height = a0.size().height() - 45 - self.scroll_area.horizontalScrollBar().height()
        else:
            new_width = a0.size().width()
            new_height = a0.size().height() - 45

        self.media_panes_placeholder.resize(new_width, new_height)
        self.message_label.resize(a0.size().width() - 5,
                                  a0.size().height() - 50)
        self.maintain_visibility()

    def maintain_visibility(self):
        """
        Function checks that the CompareRoot fits the screen. If not, a ScrollArea is added to contain the widgets.
        :return:
        """
        try:
            if self.size().width() > self.media_panes_placeholder.minimumWidth() \
                and self.size().height() - 70 > self.media_panes_placeholder.minimumHeight():

                # Check the scroll_area is in the stacked layout
                if self.using_scroll_view:
                    print("Removing scroll area")
                    self.compare_layout.removeWidget(self.scroll_area)
                    self.scroll_area.takeWidget()
                    self.compare_layout.insertWidget(0, self.media_panes_placeholder)
                    self.using_scroll_view = False

            else:
                # Check the compare_root is in the stacked layout
                if not self.using_scroll_view:
                    print("Removing compare root")
                    self.compare_layout.removeWidget(self.media_panes_placeholder)
                    self.compare_layout.insertWidget(0, self.scroll_area)
                    self.scroll_area.setWidget(self.media_panes_placeholder)
                    self.using_scroll_view = True
        except AttributeError as e:
            print(e)

    def color_widgets(self):
        """
        Give the widgets a color depending on if the values are identical or not.
        :return:
        """
        bin_ident, names, dt, fsize, avg_diff = self.model.compare_current_files()
        bg = f"background: rgb({'200, 255' if bin_ident else '255, 200'}, 200);"
        self.button_bar.setStyleSheet(bg)

        name_bg = f"background: rgb({'200, 255' if names else '255, 200'}, 200);"
        dt_bg = f"background: rgb({'200, 255' if dt else '255, 200'}, 200);"

        if fsize:
            fsize_bg = f"background: rgb(200, 255, 200);"
        elif avg_diff < 1000:
            fsize_bg = f"background: rgb(255, 255, 200);"
        else:
            fsize_bg = f"background: rgb(255, 200, 200);"

        for pane in self.media_panes:
            pane.original_name_lbl.setStyleSheet(name_bg)
            pane.new_name_lbl.setStyleSheet(dt_bg)
            pane.file_size_lbl.setStyleSheet(fsize_bg)

    def set_target(self, target: MediaPane):
        """
        Set the target pane for the current comparison. This is used so the QAction can update the buttons of the
        target pane.
        :param target: the MediaPane which the cursor is now hovering over.
        :return:
        """
        if target not in self.target_panes:
            self.target_panes.append(target)

    def remove_target(self, target: MediaPane):
        """
        Remove the target pane from the list of target panes. This is used so the QAction can update the buttons of the
        target pane.
        :param target: The MediaPane over which the cursor is no longer hovering over.
        :return:
        """

        if target in self.target_panes:
            self.target_panes.remove(target)

    def clear_message(self):
        """
        Clear the message in the CompareWidget if there's new widgets to be added.
        """
        if self.__message_set:
            self.scroll_area.takeWidget()
            self.scroll_area.setWidget(self.media_panes_placeholder)
            self.message_label.setStyleSheet(f"background: rgb(255, 255, 255); ")
            self.message_label.setText("")
            self.__set_enable_all_buttons(enable=True)

    def set_empty_duplicates(self):
        """
        Add a text informing that there's no duplicates.
        """
        self.scroll_area.takeWidget()
        self.scroll_area.setWidget(self.message_label)
        self.message_label.setStyleSheet(f"background: rgb(255, 255, 255); ")
        self.message_label.setText("There are no duplicates, search database to find duplicates.")
        self.__set_enable_all_buttons(enable=False)
        self.__message_set = True

    def __set_enable_all_buttons(self, enable: bool = True):
        """
        Enable or disable all actions that are associated with the compare pane.
        """
        self.next_action.setEnabled(enable)
        self.commit_all.setEnabled(enable)
        self.commit_selected.setEnabled(enable)

        self.set_main_action.setEnabled(enable)
        self.mark_delete_action.setEnabled(enable)
        self.change_tag_action.setEnabled(enable)
        self.remove_media_action.setEnabled(enable)

        self.move_left_action.setEnabled(enable)
        self.move_right_action.setEnabled(enable)

    def move_right_action_handler(self):
        """
        Send click to the move right button on the media pane the cursor is on.
        """
        print("Right Action")
        for target in self.target_panes:
            target: MediaPane
            target.right_button.click()

    def move_left_action_handler(self):
        """
        Send click to the move left button on the media pane the cursor is on.
        """
        print("Left Action")
        for target in self.target_panes:
            target: MediaPane
            target.right_button.click()

    def move_right(self, mp: MediaPane):
        """
        Takes the media pane and moves it one position to the right in the layout.

        :param mp: Media pane to move
        :returns:
        """
        temp_list = self.media_panes
        index = self.media_panes.index(mp)
        buddy = temp_list[index + 1]
        assert index < self.compare_layout.count() - 1, "Move left on left most image called."

        self.media_panes = temp_list[:index] + [temp_list[index+1]] + [temp_list[index]] + temp_list[index + 2:]

        for elm in self.media_panes:
            self.media_layout.removeWidget(elm)

        for elm in self.media_panes:
            self.media_layout.addWidget(elm)

        # update the button states.
        self.set_arrow_enable(mp)
        self.set_arrow_enable(buddy)

    def move_left(self, mp: MediaPane):
        """
        Takes the media pane and moves it one position to the left in the layout.

        :param mp: Widget to move left
        :returns:
        """
        temp_list = self.media_panes
        index = self.media_panes.index(mp)
        buddy = temp_list[index - 1]
        assert index > 0, "Move left on left most image called."

        self.media_panes = temp_list[:index - 1] + [temp_list[index]] + [temp_list[index - 1]] + temp_list[index + 1:]

        for elm in self.media_panes:
            self.media_layout.removeWidget(elm)

        for elm in self.media_panes:
            self.media_layout.addWidget(elm)

        # update the button states.
        self.set_arrow_enable(mp)
        self.set_arrow_enable(buddy)

    def set_arrow_enable(self, mp: MediaPane):
        """
        Takes a media pane, gets the index of it in the layout and determines if it lays at the edge and if buttons need
        to be disabled.

        :param mp: Meida pane to set the arrow enable states of

        :returns:
        """
        index = self.media_panes.index(mp)
        mp.left_button.setEnabled(index > 0)
        mp.right_button.setEnabled(index + 1 < len(self.media_panes))
