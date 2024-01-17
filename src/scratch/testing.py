import sys
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QMainWindow,
    QScrollBar,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
)
from PyQt6.QtGui import QPixmap, QPainter, QFont, QPixmapCache, QResizeEvent
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve
import random
import os
from photo_lib.gui.image_tile import IndexedTile
from photo_lib.gui.base_image import BaseImage


# https://stackoverflow.com/questions/17935691/stylesheet-on-qscrollbar-leaves-background-of-scrollbar-with-checkerboard-patter

class RootWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dummy_widget = QWidget()
        self.dummy_widget.setMinimumWidth(100)
        self.dummy_widget.setMinimumHeight(500)

        self.placeholder = QFrame()
        self.placeholder.setFrameStyle(QFrame.Shape.Box)

        self.indicator = QLabel("Indicator", self)
        self.indicator.setVisible(False)
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # self.sc = QScrollBar(Qt.Orientation.Horizontal)
        self.sc = QScrollBar(Qt.Orientation.Vertical)
        self.sc.setMaximum(20)
        self.sc.valueChanged.connect(self.value_reader)
        self.sc.sliderReleased.connect(self.hide_indicator)
        self.sc.sliderPressed.connect(self.show_indicator)
        # self.sc.setFixedWidth(15)
        self.sc.setPageStep(10)
        style_sheet = """
        QScrollBar:vertical {
            border: 1px solid black;
            width: 15px;
            color: green;
        }

        QScrollBar::handle {       
            min-height: 30px;
            max-height: 30px;
            padding: 15px, 0px, 15px, 0px;
        }    
        
        QScrollBar::down-arrow {
            /* No observable Effects: 
            min-width: 15px;
            min-height: 15px;
            color: red; 
            margin: 15px, 0px, 0px, 0px;
            outline: 1px solid black;
    
            */ 
            /* background-color: magenta; */
            padding: 5px;
        }
        """
        # style_sheet = """
        # QScrollBar:horizontal {
        #     border: 2px solid green;
        #     background: cyan;
        #     height: 15px;
        #     margin: 0px 40px 0 0px;
        # }
        #
        # QScrollBar::handle:horizontal {
        #     background: gray;
        #     min-width: 20px;
        # }
        #
        # QScrollBar::add-line:horizontal {
        #     background: blue;
        #     width: 16px;
        #     subcontrol-position: right;
        #     subcontrol-origin: margin;
        #     border: 2px solid black;
        # }
        #
        # QScrollBar::sub-line:horizontal {
        #     background: magenta;
        #     width: 16px;
        #     subcontrol-position: top right;
        #     subcontrol-origin: margin;
        #     border: 2px solid black;
        #     position: absolute;
        #     right: 20px;
        # }
        #
        # QScrollBar:left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
        #     width: 3px;
        #     height: 3px;
        #     background: pink;
        # }
        #
        # QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        #     background: none;
        # }
        # """
        self.sc.setStyleSheet(style_sheet)

        self.l = QHBoxLayout()
        # self.l = QVBoxLayout()
        self.dummy_widget.setLayout(self.l)

        self.l.addWidget(self.placeholder)
        self.l.addWidget(self.sc)

        self.setCentralWidget(self.dummy_widget)

    def show_indicator(self):
        self.indicator.setVisible(True)
        self.value_reader()

    def hide_indicator(self):
        self.indicator.setVisible(False)

    def value_reader(self):
        no_arrows = self.sc.height() - self.sc.width() * 2
        relative = self.sc.value() / (self.sc.maximum() - self.sc.minimum())
        # should be
        # movement_range = no_arrows - 50
        # is
        self.indicator.setText(str(self.sc.value()))
        movement_range = self.sc.height() - 50
        self.indicator.move(self.width() - 15 - self.indicator.width(),
                            int(relative * movement_range + 25 + 10 - self.indicator.height() / 2))
        if self.sc.isSliderDown():
            print(f"Slider is down")
        else:
            print(f"Slider is up")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    print(QPixmapCache.cacheLimit())
    QPixmapCache.setCacheLimit(1024)
    print(QPixmapCache.cacheLimit())

    ex = RootWindow()
    ex.show()
    sys.exit(app.exec())
