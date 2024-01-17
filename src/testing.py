import sys
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGridLayout,
    QLabel,
    QScrollArea,
    QScroller,
    QWidget,
    QMainWindow,
    QScrollBar,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QPushButton
)
from PyQt6.QtGui import QPixmap, QPainter, QFont, QPixmapCache
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve
import random
import os
from photo_lib.gui.image_tile import IndexedTile
from photo_lib.gui.base_image import BaseImage


# class RootWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.sc = QScrollBar(Qt.Orientation.Horizontal)
#         self.sc.setRange(0, 1000)
#         self.sc.setParent(self)
#         self.sc.setFixedHeight(15)
#
#     def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
#         target = max(0, 1000 - self.width())
#         super().resizeEvent(a0)
#         self.sc.setFixedWidth(self.width())
#         self.sc.setRange(0, target)
#         print(self.width())
#
#
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     main_window = RootWindow()
#     main_window.show()
#     sys.exit(app.exec())

# class RootWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#
#         self.initUI()
#
#     def initUI(self):
#         self.setWindowTitle('Testing overlay')
#         self.setFixedWidth(400)
#         self.setFixedHeight(400)
#
#         overlay_widget = QLabel("Overlay", self)
#         central_widget = QWidget(self)
#         central_widget.setFixedHeight(600)
#         central_widget.setFixedWidth(600)
#         central_widget.move(-100, -100)
#         central_widget.setStyleSheet("background-color: rgba(0, 255, 0, 100);")
#
#         overlay_widget.setStyleSheet("background-color: rgba(255, 0, 0, 100);")
#         overlay_widget.setFixedSize(100, 100)
#         overlay_widget.move(150, 150)
#
#         # overlay_widget.move(100, 100)
#         # overlay_widget.move(150, 150)
#         # central_widget.setParent(None)
#         # central_widget.setParent(self)
#         overlay_widget.setParent(None)
#         overlay_widget.setParent(self)

# class RootWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.l = QGridLayout()
#         self.a = QLabel("Label A")
#         self.b = QLabel("Label B")
#         self.w = QWidget()
#         self.setCentralWidget(self.w)
#
#         self.w.setLayout(self.l)
#         self.l.addWidget(self.a, 0, 0)
#         self.l.addWidget(self.b, 0, 0)


# class RootWindow(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.dummy_widget = QWidget()
#         self.dummy_widget.setMinimumWidth(100)
#         self.dummy_widget.setMinimumHeight(500)
#
#         self.placeholder = QFrame()
#         self.placeholder.setFrameStyle(QFrame.Shape.Box)
#
#         self.indicator = QLabel("Indicator", self)
#         self.indicator.setVisible(False)
#         self.indicator.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
#
#         # self.sc = QScrollBar(Qt.Orientation.Horizontal)
#         self.sc = QScrollBar(Qt.Orientation.Vertical)
#         self.sc.setMaximum(1000)
#         self.sc.valueChanged.connect(self.value_reader)
#         self.sc.sliderReleased.connect(self.hide_indicator)
#         self.sc.sliderPressed.connect(self.show_indicator)
#         # self.sc.setFixedWidth(15)
#         self.sc.setPageStep(10)
#         style_sheet = """
#         QScrollBar:vertical {
#             border: 1px dashed black;
#             width: 15px;
#         }
#
#
#         QScrollBar::handle:vertical {
#             min-height: 50px;
#             max-height: 50px
#         }
#
#         """
#         # style_sheet = """
#         # QScrollBar:horizontal {
#         #     border: 2px solid green;
#         #     background: cyan;
#         #     height: 15px;
#         #     margin: 0px 40px 0 0px;
#         # }
#         #
#         # QScrollBar::handle:horizontal {
#         #     background: gray;
#         #     min-width: 20px;
#         # }
#         #
#         # QScrollBar::add-line:horizontal {
#         #     background: blue;
#         #     width: 16px;
#         #     subcontrol-position: right;
#         #     subcontrol-origin: margin;
#         #     border: 2px solid black;
#         # }
#         #
#         # QScrollBar::sub-line:horizontal {
#         #     background: magenta;
#         #     width: 16px;
#         #     subcontrol-position: top right;
#         #     subcontrol-origin: margin;
#         #     border: 2px solid black;
#         #     position: absolute;
#         #     right: 20px;
#         # }
#         #
#         # QScrollBar:left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
#         #     width: 3px;
#         #     height: 3px;
#         #     background: pink;
#         # }
#         #
#         # QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
#         #     background: none;
#         # }
#         # """
#         self.sc.setStyleSheet(style_sheet)
#
#         self.l = QHBoxLayout()
#         # self.l = QVBoxLayout()
#         self.dummy_widget.setLayout(self.l)
#
#         self.l.addWidget(self.placeholder)
#         self.l.addWidget(self.sc)
#
#         self.setCentralWidget(self.dummy_widget)
#
#     def show_indicator(self):
#         self.indicator.setVisible(True)
#         self.value_reader()
#
#     def hide_indicator(self):
#         self.indicator.setVisible(False)
#
#     def value_reader(self):
#         no_arrows = self.sc.height() - self.sc.width() * 2
#         relative = self.sc.value() / (self.sc.maximum() - self.sc.minimum())
#         # should be
#         # movement_range = no_arrows - 50
#         # is
#         self.indicator.setText(str(self.sc.value()))
#         movement_range = self.sc.height() - 50
#         self.indicator.move(self.width() - 15 - self.indicator.width(),
#                             int(relative * movement_range + 25 + 10 - self.indicator.height() / 2))
#         if self.sc.isSliderDown():
#             print(f"Slider is down")
#         else:
#             print(f"Slider is up")

class RootWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dummy_widget = QWidget()
        self.dummy_widget.setMinimumHeight(500)
        self.dummy_widget.setMinimumWidth(500)
        self.l = QVBoxLayout()
        self.dummy_widget.setLayout(self.l)

        self.placeholder = QPushButton("Click-me", self.dummy_widget)
        self.placeholder.clicked.connect(self.test_animation)

        self.change_btn = QPushButton("Change", self.dummy_widget)
        self.change_btn.move(QPoint(0, 100))
        self.change_btn.clicked.connect(self.change_dst)

        self.setCentralWidget(self.dummy_widget)
        self.anim = QPropertyAnimation(self.placeholder, b"pos")
        self.anim.finished.connect(self.reset_btn)

        self.it = os.walk("/home/alisot2000/Desktop")
        self.root = ""
        self.children = []

        self.widgets = []
        for i in range(100):
            # t = IndexedTile()
            t = BaseImage()
            t.setVisible(True)
            t.move(QPoint(0, 200))
            t.setParent(self)
            self.widgets.append(t)
        # self.l.addWidget(t)

    def test_animation(self):
        self.anim.setDuration(1000)
        self.anim.setStartValue(QPoint(0, 0))
        self.anim.setEndValue(QPoint(100, 100))
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.start()

        # a = "/home/alisot2000/Desktop/Faveo_ISC/WhatsApp Image 2023-03-13 at 20.00.53.jpeg"
        # b = "/home/alisot2000/Desktop/Faveo_ISC/WhatsApp Image 2023-03-13 at 20.00.54.jpeg"

        # for i in range(100):
            # if i % 2 == 0:
            #     path = a
            # else:
            #     path = b
            # pm = QPixmap(path)
            # self.t.file_path = path

        count = 100
        current_size = 0
        while count > 0:
            while len(self.children) == 0:
                r, d, f = next(self.it)
                self.root = r
                self.children = f

            path = os.path.join(self.root, self.children.pop())
            if ext := os.path.splitext(path)[1].lower() not in [".png", ".jpg", ".jpeg", ".gif"]:
                print(f"Skipping: {path}")
                continue

            current_size += os.stat(path).st_size
            self.widgets[100 - count].file_path = path
            count -= 1
        print(f"Accumulated size: {current_size / 1024 / 1024} MB")
        print("Done")

    def reset_btn(self):
        self.placeholder.move(QPoint(0, 0))

    def change_dst(self):
        # self.anim.stop()
        self.anim.setEndValue(QPoint(200, 200))
        # self.anim.start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    print(QPixmapCache.cacheLimit())
    QPixmapCache.setCacheLimit(1024)
    print(QPixmapCache.cacheLimit())

    ex = RootWindow()
    ex.show()
    sys.exit(app.exec())
