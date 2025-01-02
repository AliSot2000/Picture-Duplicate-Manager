import sys

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QWidget, QGridLayout, QMainWindow, QLabel, QFrame


class TestTemp(QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.l = QGridLayout()
        self.use_frame = True
        self.dummy_widget = QWidget()
        self.setCentralWidget(self.dummy_widget)
        self.dummy_widget.setLayout(self.l)

        self.w = []

        roles = [
            QPalette.ColorRole.Window,
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Base,
            QPalette.ColorRole.AlternateBase,
            QPalette.ColorRole.ToolTipBase,
            QPalette.ColorRole.ToolTipText,
            QPalette.ColorRole.PlaceholderText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.Button,
            QPalette.ColorRole.ButtonText,
            QPalette.ColorRole.BrightText,
            QPalette.ColorRole.Light,
            QPalette.ColorRole.Midlight,
            QPalette.ColorRole.Dark,
            QPalette.ColorRole.Mid,
            QPalette.ColorRole.Shadow,
            QPalette.ColorRole.Highlight,
            QPalette.ColorRole.Accent,
            QPalette.ColorRole.HighlightedText,
            QPalette.ColorRole.Link,
            QPalette.ColorRole.LinkVisited
        ]

        groups = [
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
            QPalette.ColorGroup.Disabled
        ]

        for i in range(len(groups)):
            lbl = QLabel(str(groups[i]))
            self.l.addWidget(lbl, 0, i + 1)

        for i in range(len(roles)):
            widgets = []
            lbl = QLabel(str(roles[i]))
            self.l.addWidget(lbl, i + 1, 0)
            widgets.append(lbl)

            for j in range(len(groups)):
                col = self.palette().color(groups[j], roles[i])
                r = col.red()
                g = col.green()
                b = col.blue()
                styleSheet = f"background-color: rgba({r}, {g}, {b}, 1);"
                if self.use_frame:
                    w = QFrame()
                    w.setFrameStyle(QFrame.Shape.Box)
                else:
                    w = QWidget()
                w.setFixedSize(QSize(50, 20))
                w.setStyleSheet(styleSheet)

                self.l.addWidget(w, i + 1, j + 1)
                widgets.append(w)

            self.w.append(widgets)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestTemp()
    window.show()

    sys.exit(app.exec())