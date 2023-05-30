from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QLabel, QApplication, QHBoxLayout, QFileDialog
import sys
from photo_lib.gui.media_pane import MediaPane
from typing import Union


class DateTimeModal(QWidget):
    tag_label: QLabel
    custom_datetime: QLabel
    tag_input: QLineEdit
    custom_datetime_input: QLineEdit

    form_layout: QFormLayout

    close_button: QPushButton
    apply_button: QPushButton
    apply_close_button: QPushButton

    button_box_layout: QHBoxLayout
    button_container: QWidget

    __media_pane: Union[MediaPane, None] = None

    def __init__(self):
        """
        Set up the form and everything.
        """

        super().__init__()
        self.setWindowTitle("Set the datetime of the picture to a specific datetime.")
        self.resize(500, 100)

        self.form_layout = QFormLayout()
        self.tag_label = QLabel("Tag:")
        self.custom_datetime = QLabel("Custom Datetime:")

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Enter custom to provide datetime manually")
        self.custom_datetime_input = QLineEdit()
        self.custom_datetime_input.setPlaceholderText("YYYY-MM-DD HH.MM.SS")
        self.custom_datetime_input.setDisabled(True)

        self.close_button = QPushButton("Close")
        self.apply_button = QPushButton("Apply")
        self.apply_close_button = QPushButton("Apply and Close")

        self.button_box_layout = QHBoxLayout()
        self.button_box_layout.addWidget(self.close_button)
        self.button_box_layout.addWidget(self.apply_button)
        self.button_box_layout.addWidget(self.apply_close_button)

        self.button_container = QWidget()
        self.button_container.setLayout(self.button_box_layout)

        self.form_layout.addRow(self.tag_label, self.tag_input)
        self.form_layout.addRow(self.custom_datetime, self.custom_datetime_input)
        self.form_layout.addRow(self.button_container)

        self.setLayout(self.form_layout)

        self.tag_input.textChanged.connect(self.update_datetime_input)

    def update_datetime_input(self):
        """
        Update the datetime input mask depending on the tag input.
        :return:
        """
        if self.tag_input.text().lower().strip() == "custom":
            self.custom_datetime_input.setDisabled(False)
            self.custom_datetime_input.setInputMask("9999-99-99 99.99.99")
        else:
            self.custom_datetime_input.setDisabled(True)
            self.custom_datetime_input.setInputMask("")

    @property
    def media_pane(self):
        return self.__media_pane

    @media_pane.setter
    def media_pane(self, value):
        self.__media_pane = value
        self.tag_input.setText(self.__media_pane.dbe.naming_tag)

class FolderSelectModal(QFileDialog):
    def __init__(self):
        """
        Set up the QFileDialog to select a folder since I'm lazy and it might need additional things.
        """
        super().__init__()
        self.setFileMode(QFileDialog.FileMode.Directory)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DateTimeModal()
    window.show()
    window2 = FolderSelectModal()
    window2.show()
    sys.exit(app.exec())
