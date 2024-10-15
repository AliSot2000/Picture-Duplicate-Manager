import math
import sys
import time

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QMainWindow,
    QScrollBar,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QTextEdit,
    QGridLayout,
    QPushButton,
    QSlider,
    QStyle
)
from PyQt6.QtGui import QPixmap, QPainter, QFont, QPixmapCache, QResizeEvent
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve
# import random
# import os
# from photo_lib.gui.image_tile import IndexedTile
# from photo_lib.gui.base_image import BaseImage


# https://stackoverflow.com/questions/17935691/stylesheet-on-qscrollbar-leaves-background-of-scrollbar-with-checkerboard-patter

class RootWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.sc = QScrollBar(Qt.Orientation.Vertical)
        self.dummy_widget = QWidget()
        self.dummy_widget.setMinimumWidth(100)
        self.dummy_widget.setMinimumHeight(500)

        self.placeholder = QWidget()
        self.placeholder_layout = QGridLayout()
        self.placeholder_layout.setSpacing(10)
        self.placeholder.setLayout(self.placeholder_layout)
        self.placeholder_layout.setContentsMargins(0, 0, 0, 0)

        self.style_sheet_input = QTextEdit()
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.set_style_sheet)

        self.scroll_max = QSlider(Qt.Orientation.Horizontal)
        self.scroll_max.valueChanged.connect(self.max_set)
        self.scroll_max.setMaximum(1000)
        self.scroll_max.setMinimum(50)

        self.page_size = QSlider(Qt.Orientation.Horizontal)
        self.page_size.valueChanged.connect(self.page_set)
        self.page_size.setMaximum(50)
        self.page_size.setMinimum(10)

        self.do_shit_btn = QPushButton("Do-Shit")
        self.do_shit_btn.clicked.connect(self.do_shit)

        self.placeholder_layout.addWidget(self.style_sheet_input, 0, 0, 1, 4)
        self.placeholder_layout.addWidget(self.submit_btn, 1, 2)
        self.placeholder_layout.addWidget(self.scroll_max, 1, 0)
        self.placeholder_layout.addWidget(self.page_size, 1, 1)
        self.placeholder_layout.addWidget(self.do_shit_btn, 1, 3)

        # self.sc = QScrollBar(Qt.Orientation.Horizontal)
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
            color: red;
        }
        
        QScrollBar::up-arrow {
            padding: 5px;
            color: blue;
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
        # self.sc.setStyleSheet(style_sheet)

        self.l = QHBoxLayout()
        self.l.setContentsMargins(10, 10, 10, 10)
        self.l.setSpacing(10)
        # self.l = QVBoxLayout()
        self.dummy_widget.setLayout(self.l)

        self.l.addWidget(self.placeholder)
        self.l.addWidget(self.sc)

        self.setCentralWidget(self.dummy_widget)

        # Spacing
        self.upper_pad = QLabel("", self)
        self.upper_pad.setVisible(False)
        self.upper_pad.setStyleSheet("QLabel {background: rgba(255, 128, 0, 128);}")

        self.lower_pad = QLabel("", self)
        self.lower_pad.setVisible(False)
        self.lower_pad.setStyleSheet("QLabel {background: rgba(255, 128, 0, 128);}")

        # Arrows
        self.upper_arrow = QLabel("", self)
        self.upper_arrow.setVisible(False)
        self.upper_arrow.setStyleSheet("QLabel {background: rgba(128, 255, 0, 128);}")

        self.lower_arrow = QLabel("", self)
        self.lower_arrow.setVisible(False)
        self.lower_arrow.setStyleSheet("QLabel {background: rgba(128, 255, 0, 128);}")

        # Page
        self.upper_page = QLabel("", self)
        self.upper_page.setVisible(False)
        self.upper_page.setStyleSheet("QLabel {background: rgba(0, 255, 128, 128);}")

        self.lower_page = QLabel("", self)
        self.lower_page.setVisible(False)
        self.lower_page.setStyleSheet("QLabel {background: rgba(0, 255, 128, 128);}")

        # Scrollbar
        self.scrollbar = QLabel("", self)
        self.scrollbar.setVisible(False)
        self.scrollbar.setStyleSheet("QLabel {background: rgba(0, 128, 255, 128);}")

        self.indicator = QLabel("Indicator", self)
        self.indicator.setStyleSheet("QLabel {background: red;}")
        self.indicator.setVisible(True)
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.indicator.setFixedHeight(26)
        self.indicator.setFixedWidth(100)

    def do_shit(self, *args, **kwargs):
        print(f"Args {args}")
        print(f"Kwargs {kwargs}")
        self.indicator.setVisible(True)
        self.upper_pad.setVisible(True)
        self.lower_pad.setVisible(True)
        self.upper_arrow.setVisible(True)
        self.lower_arrow.setVisible(True)
        self.upper_page.setVisible(True)
        self.lower_page.setVisible(True)
        self.scrollbar.setVisible(True)



    def max_set(self, v: int):
        self.sc.setMaximum(v)
        self.sc.setValue(0)
        print(f"Max: {v}")

    def page_set(self, v: int):
        self.sc.setPageStep(v)
        self.sc.setValue(0)
        print(f"Page: {v}")

    def set_style_sheet(self):
        style_sheet = self.style_sheet_input.toPlainText()
        print(style_sheet)
        self.sc.setStyleSheet(style_sheet)

    def show_indicator(self):
        self.indicator.setVisible(True)
        self.upper_pad.setVisible(True)
        self.lower_pad.setVisible(True)
        self.upper_arrow.setVisible(True)
        self.lower_arrow.setVisible(True)
        self.upper_page.setVisible(True)
        self.lower_page.setVisible(True)
        self.scrollbar.setVisible(True)
        self.value_reader()

    def hide_indicator(self):
        self.indicator.setVisible(False)
        self.upper_pad.setVisible(False)
        self.lower_pad.setVisible(False)
        self.upper_arrow.setVisible(False)
        self.lower_arrow.setVisible(False)
        self.upper_page.setVisible(False)
        self.lower_page.setVisible(False)
        self.scrollbar.setVisible(False)

    def value_reader(self):
        print(f"Scrollbar Size:", self.sc.size())
        min_handle_height = self.sc.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarSliderMin)
        no_arrows = self.sc.height() - self.sc.width() * 2
        relative = self.sc.value() / (self.sc.maximum() - self.sc.minimum())

        # Height should be page step / document length
        bar_height_rel = self.sc.pageStep() / (self.sc.maximum() - self.sc.minimum() + self.sc.pageStep())
        bar_height_px = math.floor(bar_height_rel * no_arrows)
        handle_height = max(min_handle_height, bar_height_px)
        print(handle_height)

        # INFO
        #   => Need to keep track of height of separator?

        self.indicator.setText(str(self.sc.value()))
        movement_range = no_arrows - handle_height
        self.indicator.move(self.width() - self.sc.width() - 10 - self.indicator.width(),
                            int(relative * movement_range
                                + (handle_height / 2)
                                + 10
                                + self.sc.width()
                                - self.indicator.height() / 2))

        # Spacing
        self.lower_pad.setFixedWidth(self.width())
        self.lower_pad.setFixedHeight(10)
        self.lower_pad.move(0, self.height() - 10)

        self.upper_pad.setFixedWidth(self.width())
        self.upper_pad.setFixedHeight(10)
        self.upper_pad.move(0, 0)

        # Arrows
        self.lower_arrow.setFixedHeight(self.sc.width())
        self.lower_arrow.setFixedWidth(self.width())
        self.lower_arrow.move(0, self.height() - 10 - self.sc.width())

        self.upper_arrow.setFixedHeight(self.sc.width())
        self.upper_arrow.setFixedWidth(self.width())
        self.upper_arrow.move(0, 10)

        # Page
        self.lower_page.setFixedWidth(self.width())
        self.lower_page.setFixedHeight(int(math.ceil(movement_range * (1 - relative))))
        self.lower_page.move(0, 10 + self.sc.width() + int(movement_range * relative + handle_height))

        self.upper_page.setFixedWidth(self.width())
        self.upper_page.setFixedHeight(int(movement_range * relative))
        self.upper_page.move(0, 10 + self.sc.width())

        # Handle
        self.scrollbar.setFixedWidth(self.width())
        self.scrollbar.setFixedHeight(handle_height)
        self.scrollbar.move(0, 10 + self.sc.width() + int(relative * movement_range))

        # Getting position of
        # stl = self.style()
        # Doesn't work: v is empty QRect()
        # v = stl.subControlRect(stl.ComplexControl.CC_ScrollBar, None, stl.SubControl.SC_ScrollBarSlider, self.sc)
        # stl.subElement doesn't work because it has no scrollbar stuff


        if self.sc.isSliderDown():
            print(f"Slider is down")
        else:
            print(f"Slider is up")



if __name__ == '__main__':
    app = QApplication(sys.argv)
    x = app.style().pixelMetric(QApplication.style().PixelMetric.PM_ScrollBarExtent)
    print(x)
    print(QPixmapCache.cacheLimit())
    QPixmapCache.setCacheLimit(1024)
    print(QPixmapCache.cacheLimit())

    ex = RootWindow()
    ex.show()
    sys.exit(app.exec())
