from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QMessageBox, QMainWindow, QApplication
from PyQt6.QtGui import QAction
from photo_lib.gui.gui_utils import general_wrapper
from photo_lib.gui.model import Model
from photo_lib.gui.modals import RenameTableModal
from photo_lib.data_objects import ImportTableEntry
from typing import List
from dataclasses import dataclass

# TODO add option for last_import table.

@dataclass
class ImportTableEntryWidgets:
    root_path: QLabel
    table_desc: QLabel
    delete_btn: QPushButton
    change_desc_btn: QPushButton
    key: int



class ImportTableList(QFrame):
    model: Model = None
    entries: List[ImportTableEntry]
    entry_widgets: List[ImportTableEntryWidgets] = None
    g_layout: QGridLayout

    def __init__(self, model: Model):
        """
        Create base widget for the import table list
        :param model:
        """
        super().__init__()
        self.model = model
        self.entries = []
        self.g_layout = QGridLayout()
        self.setLayout(self.g_layout)

        empty_table_label = QLabel("No Import Tables")
        self.g_layout.addWidget(empty_table_label, 0, 0)

        self.del_all_tables_action = QAction("Delete All Tables")
        self.del_all_tables_action.setToolTip("Removes all import tables from the database")
        self.del_all_tables_action.triggered.connect(self.del_all_tables)

    def del_all_tables(self):
        """
        Delete all tables from the model, future proofing
        :return:
        """
        msg_bx = QMessageBox()
        msg_bx.setWindowTitle("Delete All Tables")
        msg_bx.setText("Are you sure you want to delete all tables?")
        msg_bx.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_bx.setIcon(QMessageBox.Icon.Warning)
        res = msg_bx.exec()

        if res == 0:
            print("Delete all tables canceled")
            return

        self.model.remove_all_import_tables()
        self.entries = []
        self.build_table()

    def fetch_tables(self):
        """
        Fetch the tables from the model
        and builds the table
        :return:
        """
        self.entries = self.model.get_import_tables()
        self.build_table()

    def delete_table(self, btn_state: bool, entry: ImportTableEntry):
        """
        Delete a table from the model
        :param entry: entry to delete
        :param btn_state: state of the button, not used
        :return:
        """
        self.model.delete_import_table(entry.table_name)
        del_done = False
        w = []

        # Reusing the widgets
        for i in range(len(self.entry_widgets)):
            cur_entry = self.entry_widgets[i]

            if cur_entry.key == entry.key:
                cur_entry.table_desc.deleteLater()
                cur_entry.root_path.deleteLater()
                cur_entry.delete_btn.deleteLater()
                cur_entry.change_desc_btn.deleteLater()
                del_done = True
                continue

            # Needs to be placed here so we don't capture the cur_entry if it is the one we want to delete.
            w.append(cur_entry)
            # Delete done, move all widgets up by one.
            if del_done:
                self.g_layout.addWidget(cur_entry.root_path, i, 0)
                self.g_layout.addWidget(cur_entry.table_desc, i, 1)
                self.g_layout.addWidget(cur_entry.delete_btn, i, 2)
                self.g_layout.addWidget(cur_entry.change_desc_btn, i, 3)

        # Need to update entry widget and entries
        self.entry_widgets = w
        self.entries.remove(entry)
        if len(self.entry_widgets) == 0:
            self.build_table()

    def change_desc(self, btn_statet: bool, entry: ImportTableEntry):
        """
        Change the description of the table, performs the opening of the dialogs.
        :param entry: entry to change description of
        :param btn_statet: state of the button, not used
        :return:
        """
        success = False
        new_name = ""

        while not success:
            modal = RenameTableModal(entry.table_desc)
            res = modal.exec()

            # Reject, return
            if res == 0:
                return

            # Try to rename, on error, show error and open modal again
            try:
                new_name = modal.new_desc_input.text()
                self.model.change_import_table_description(entry.key, new_name)
                success = True
            except ValueError as e:
                msg_bx = QMessageBox(QMessageBox.Icon.Critical, "Error", str(e), QMessageBox.StandardButton.Ok)
                msg_bx.exec()
                continue

        entry.table_desc = new_name
        # Success, update the description.
        for row in self.entry_widgets:
            if row.key == entry.key:
                row.table_desc.setText(new_name)

    def build_table(self):
        """
        Build the table from the entries
        :return:
        """
        if len(self.entries) == 0:
            w = QLabel("No Import Tables")
            self.g_layout.addWidget(w, 0, 0)
            return

        # Remove all widgets, and delete them
        while self.g_layout.count() > 0:
            self.g_layout.takeAt(0).widget().deleteLater()

        # Add Headers
        r = QLabel("Root Path")
        r.setFixedHeight(20)
        d = QLabel("Description")
        d.setFixedHeight(20)
        self.g_layout.addWidget(r, 0, 0)
        self.g_layout.addWidget(d, 0, 1)

        # Add all entries
        self.entry_widgets = []
        for i in range(len(self.entries)):
            w = self.build_single_table(self.entries[i])
            self.entry_widgets.append(w)
            self.g_layout.addWidget(w.root_path, i + 1, 0)
            self.g_layout.addWidget(w.table_desc, i + 1, 1)
            self.g_layout.addWidget(w.delete_btn, i + 1, 2)
            self.g_layout.addWidget(w.change_desc_btn, i + 1, 3)

            w.delete_btn.clicked.connect(general_wrapper(self.delete_table, entry=self.entries[i]))
            w.change_desc_btn.clicked.connect(general_wrapper(self.change_desc, entry=self.entries[i]))

    @staticmethod
    def build_single_table(entry: ImportTableEntry) -> ImportTableEntryWidgets:
        """
        Build a single table entry and format it

        :param entry: to build widgets for.
        :return:
        """
        p = QLabel(entry.root_path)
        d = QLabel(entry.table_desc)
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("background-color: red;")
        change_desc_btn = QPushButton("Change Description")
        change_desc_btn.setStyleSheet("background-color: yellow;")

        return ImportTableEntryWidgets(
            root_path=p,
            table_desc=d,
            delete_btn=del_btn,
            change_desc_btn=change_desc_btn,
            key=entry.key
        )


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.model = Model(folder_path="/media/alisot2000/DumpStuff/work_dummy/")
        self.view = ImportTableList(model=self.model)
        self.view.fetch_tables()

        self.setCentralWidget(self.view)

        menu = self.menuBar().addMenu("Import Table Actions")
        menu.addAction(self.view.del_all_tables_action)


if __name__ == "__main__":
    app = QApplication([])
    mw = TestWindow()
    mw.show()
    app.exec()
