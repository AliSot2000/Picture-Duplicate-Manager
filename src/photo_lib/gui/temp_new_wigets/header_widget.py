"""
File contains a Header which is a QFrame containing a QHBoxLayout with a QCheckBox.
"""
from typing import Callable, Tuple, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QWidget, QSizePolicy, QLabel

from photo_lib.gui.util.fonts import get_h1_font_size


class BaseHeaderWidget(QFrame):
    """
    This base class is needed to have a QWidget that I can emit as a signal.
    """
    # INFO: need to do the trick with the tuple cuz python would otherwise try to pass self as an argument to the
    #   function.
    font_size_getter: Tuple[Callable[[], int]] = (get_h1_font_size,)

    basic_layout: QHBoxLayout
    _check_box: Optional[QCheckBox] = None
    _label: Optional[QLabel] = None

    def set_text(self, text: str, font_size: Callable[[], int] = None):
        """
        Set the text of the checkbox.

        :param text: Text to set.
        :param font_size: A function that returns an int with the font size. I.e. functions in  photo_lib.gui.util.fonts
        """
        if font_size is not None:
            self.font_size_getter = (font_size,)
            self.update_font()

        if self._check_box is not None:
            self._check_box.setText(text)
        else:
            self._label.setText(text)

    def text(self):
        """
        Get the text of the checkbox.
        """
        return self._check_box.text()

    def update_font(self):
        """
        Update the font i.e. the font size using the font size getter.
        """
        font = QFont()
        clb = self.font_size_getter[0]

        font.setPointSize(clb())
        # self.check_box.setStyleSheet(f"QCheckBox::indicator {{width: {clb()}px; height: {clb()}px; }}")
        if self._check_box is not None:
            self._check_box.setFont(font)
        else:
            self._label.setFont(font)

    def update(self):
        """
        Update the widget.
        """
        self.update_font()
        super().update()


class CheckableHeaderWidget(BaseHeaderWidget):
    """
    Header widget that contains a QCheckBox and a QHBoxLayout.
    """
    box_changed = pyqtSignal(BaseHeaderWidget)

    def __init__(self, text: str = None, parent: QWidget = None):
        """
        Create a new instance of a HeaderWidget.

        :param text: Text to display in the checkbox.
        :param parent: Parent widget.
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)

        self._check_box = QCheckBox()

        if text is not None:
            self._check_box.setText(text)

        self.basic_layout = QHBoxLayout()
        self.basic_layout.addWidget(self._check_box)

        self.setLayout(self.basic_layout)

        self.update_font()

        # Connect functions to signals
        self._check_box.clicked.connect(self.emit_click)
        self._check_box.clicked.connect(self.update_state)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._check_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setStyleSheet("background-color: palette(alternate-base);")

    def update_state(self):
        """
        We want to default to not tristate, tri state is only set by the databse when not all elements are selected.
        """
        if self._check_box.checkState() == Qt.CheckState.Checked \
                or self._check_box.checkState() == Qt.CheckState.Unchecked:
            self._check_box.setTristate(False)

    def emit_click(self):
        """
        Emit signal, when checkbox is clicked
        """
        self.box_changed.emit(self)

    def click(self):
        """
        Wrapper function to dispatch a 'click' event to the nested checkbox
        """
        self.check_box.click()

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

    def text(self):
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

    def get_height(self):
        """
        Get the minimum height of the widget
        """
        font_height = self.font_size_getter[0]()
        return font_height \
            + self.style().pixelMetric(self.style().PixelMetric.PM_LayoutBottomMargin) \
            + self.style().pixelMetric(self.style().PixelMetric.PM_LayoutTopMargin) \
            + self.frameWidth() * 2
