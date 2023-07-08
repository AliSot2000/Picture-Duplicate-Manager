from PyQt6.QtWidgets import QPushButton


class QSquarePushButton(QPushButton):
    """
    Button that stays square - used for icons.
    """
    def heightForWidth(self, a0: int) -> int:
        return self.width()
