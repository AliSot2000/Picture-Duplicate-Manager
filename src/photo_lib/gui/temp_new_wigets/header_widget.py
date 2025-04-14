"""
File contains a Header which is a QFrame containing a QHBoxLayout with a QCheckBox.
"""
from typing import Callable, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QWidget

from photo_lib.gui.util.fonts import get_h1_font_size


class HeaderWidget(QFrame):
    """
    Header widget that contains a QCheckBox and a QHBoxLayout.
    """
    # INFO: need to do the trick with the tuple cuz python would otherwise try to pass self as an argument to the
    #   function.
    font_size_getter: Tuple[Callable[[], int]] = (get_h1_font_size,)

    def __init__(self, text: str = None, parent: QWidget = None):
        """
        Create a new instance of a HeaderWidget.

        :param text: Text to display in the checkbox.
        :param parent: Parent widget.
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)

        self.check_box = QCheckBox()

        if text is not None:
            self.check_box.setText(text)

        self.check_box.setTristate(False)
        self.check_box.setCheckState(Qt.CheckState.PartiallyChecked)

        self.basic_layout = QHBoxLayout()
        self.basic_layout.addWidget(self.check_box)

        self.setLayout(self.basic_layout)

        self.update_font()

    def set_text(self, text: str, font_size: Callable[[], int] = None):
        """
        Set the text of the checkbox.

        :param text: Text to set.
        :param font_size: A function that returns an int with the font size. I.e. functions in  photo_lib.gui.util.fonts
        """
        if font_size is not None:
            self.font_size_getter = (font_size,)
            self.update_font()

        self.check_box.setText(text)

    def test(self):
        """
        Get the text of the checkbox.
        """
        return self.check_box.text()

    def update_font(self):
        """
        Update the font i.e. the font size using the font size getter.
        """
        font = QFont()
        clb = self.font_size_getter[0]

        font.setPointSize(clb())
        # self.check_box.setStyleSheet(f"QCheckBox::indicator {{width: {clb()}px; height: {clb()}px; }}")
        self.check_box.setFont(font)

    def update(self):
        """
        Update the widget.
        """
        self.update_font()
        super().update()
