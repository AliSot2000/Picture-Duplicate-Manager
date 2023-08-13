from PyQt6.QtWidgets import QLabel, QScrollArea
from PyQt6.QtCore import Qt
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
        self.text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

        self.setWidget(self.text_label)

    def set_text(self, text: str):
        """
        Set the Text of the label and also compute the size of the label.
        :param text: Text to add to the label.
        :return:
        """
        lines = text.strip().count("\n")
        self.text_label.setText(text)
        width = 0

        for l in text.split("\n"):
            width = max(width, self.text_label.fontMetrics().boundingRect(l).width())

        height = self.text_label.fontMetrics().lineSpacing() * (lines + 1)
        self.text_label.setFixedWidth(width + 10)
        self.text_label.setFixedHeight(height + 10)

    # def resize(self, a0: QSize) -> None:
    #     super().resize(a0)
    #     print("Resizing TextScroller")
    #
    # def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
    #     super().resizeEvent(a0)
    #     print("Resizing EventTextScroller")

    def scroll_from_ratio(self, rx, ry) -> None:
        """
        Set the scroll form a ratio.

        :param rx: relative scroll x (0.0 - 1.0)
        :param ry: relative scroll y (0.0 - 1.0)
        :return:
        """
        self.call_share_scroll = False

        x_target = rx * self.horizontalScrollBar().maximum()
        y_target = ry * self.verticalScrollBar().maximum()

        self.horizontalScrollBar().setValue(x_target)
        self.verticalScrollBar().setValue(y_target)
        self.call_share_scroll = True

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        """
        Captures the scrolling and pass it from the scroll bar to the share_scroll function such that scrolling is
        synchronized.

        :param dx: px amount to scroll in x direction
        :param dy: px amount to scroll in y direction
        :return:
        """
        super().scrollContentsBy(dx, dy)
        if not self.call_share_scroll:
            return

        y = self.verticalScrollBar().value()
        x = self.horizontalScrollBar().value()

        y_ratio = y / self.verticalScrollBar().maximum() if self.verticalScrollBar().maximum() else 1.0
        x_ratio = x / self.horizontalScrollBar().maximum() if self.horizontalScrollBar().maximum() else 1.0

        # print(f"Scrolling Contents TextScroller      : {x}, {y}")
        # print(f"Scrolling Contents TextScroller Ratio: {x_ratio}, {y_ratio}")

        if self.share_scroll is not None:
            self.share_scroll(caller=self, rx=x_ratio, ry=y_ratio)

