from PyQt6.QtWidgets import QLabel, QScrollArea
from PyQt6.QtCore import QSize, Qt
from PyQt6 import QtGui
from typing import Callable, Union


class TextScroller(QScrollArea):
    text_label: QLabel
    share_scroll: Union[None, Callable]
    call_share_scroll: bool = True

    def __init__(self, text: str = None, scroll_share: Callable = None):
        super().__init__()
        self.share_scroll = scroll_share
        self.text_label = QLabel()
        self.text_label.setText(text)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

        self.setWidget(self.text_label)

    def resize(self, a0: QSize) -> None:
        super().resize(a0)
        print("Resizing TextScroller")

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        super().resizeEvent(a0)
        print("Resizing EventTextScroller")

    def scroll_from_ratio(self, rx, ry) -> None:
        self.call_share_scroll = False

        x_target = rx * self.horizontalScrollBar().maximum()
        y_target = ry * self.verticalScrollBar().maximum()

        self.horizontalScrollBar().setValue(x_target)
        self.verticalScrollBar().setValue(y_target)
        self.call_share_scroll = True

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        y = self.verticalScrollBar().value()
        x = self.horizontalScrollBar().value()

        y_ratio = y / self.verticalScrollBar().maximum()
        x_ratio = x / self.horizontalScrollBar().maximum()

        print(f"Scrolling Contents TextScroller      : {x}, {y}")
        print(f"Scrolling Contents TextScroller Ratio: {x_ratio}, {y_ratio}")

        if self.call_share_scroll and self.share_scroll is not None:
            self.share_scroll(self, x_ratio, y_ratio)

