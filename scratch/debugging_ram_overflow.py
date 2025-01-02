import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QPushButton
)
from PyQt6.QtGui import  QPixmapCache
from PyQt6.QtCore import QPropertyAnimation, QPoint, QEasingCurve
import os
from photo_lib.gui.base_image import BaseImage


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
