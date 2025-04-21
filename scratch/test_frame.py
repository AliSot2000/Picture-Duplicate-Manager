from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QWidget, QMainWindow, QApplication, QSlider, QLabel

import sys


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.bgw = QWidget()
        self.bgl = QGridLayout()
        self.bgw.setLayout(self.bgl)
        self.setCentralWidget(self.bgw)

        self.line_width = 3
        self.mid_line_width = 3

        self.frames = []

        # NoFrame
        self.frame_no_frame_plain = QFrame()
        self.frame_no_frame_plain.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_no_frame_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_no_frame_plain)

        self.frame_no_frame_raised = QFrame()
        self.frame_no_frame_raised.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_no_frame_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_no_frame_raised)

        self.frame_no_frame_sunken = QFrame()
        self.frame_no_frame_sunken.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_no_frame_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_no_frame_sunken)

        # Box
        self.frame_box_plain = QFrame()
        self.frame_box_plain.setFrameShape(QFrame.Shape.Box)
        self.frame_box_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_box_plain)

        self.frame_box_raised = QFrame()
        self.frame_box_raised.setFrameShape(QFrame.Shape.Box)
        self.frame_box_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_box_raised)

        self.frame_box_sunken = QFrame()
        self.frame_box_sunken.setFrameShape(QFrame.Shape.Box)
        self.frame_box_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_box_sunken)

        # Panel
        self.frame_panel_plain = QFrame()
        self.frame_panel_plain.setFrameShape(QFrame.Shape.Panel)
        self.frame_panel_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_panel_plain)

        self.frame_panel_raised = QFrame()
        self.frame_panel_raised.setFrameShape(QFrame.Shape.Panel)
        self.frame_panel_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_panel_raised)

        self.frame_panel_sunken = QFrame()
        self.frame_panel_sunken.setFrameShape(QFrame.Shape.Panel)
        self.frame_panel_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_panel_sunken)

        # StyledPanel
        self.frame_styled_panel_plain = QFrame()
        self.frame_styled_panel_plain.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_styled_panel_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_styled_panel_plain)

        self.frame_styled_panel_raised = QFrame()
        self.frame_styled_panel_raised.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_styled_panel_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_styled_panel_raised)

        self.frame_styled_panel_sunken = QFrame()
        self.frame_styled_panel_sunken.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_styled_panel_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_styled_panel_sunken)

        # HLine
        self.frame_hline_plain = QFrame()
        self.frame_hline_plain.setFrameShape(QFrame.Shape.HLine)
        self.frame_hline_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_hline_plain)

        self.frame_hline_raised = QFrame()
        self.frame_hline_raised.setFrameShape(QFrame.Shape.HLine)
        self.frame_hline_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_hline_raised)

        self.frame_hline_sunken = QFrame()
        self.frame_hline_sunken.setFrameShape(QFrame.Shape.HLine)
        self.frame_hline_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_hline_sunken)

        # VLine
        self.frame_vline_plain = QFrame()
        self.frame_vline_plain.setFrameShape(QFrame.Shape.VLine)
        self.frame_vline_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_vline_plain)

        self.frame_vline_raised = QFrame()
        self.frame_vline_raised.setFrameShape(QFrame.Shape.VLine)
        self.frame_vline_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_vline_raised)

        self.frame_vline_sunken = QFrame()
        self.frame_vline_sunken.setFrameShape(QFrame.Shape.VLine)
        self.frame_vline_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_vline_sunken)

        # WinPanel
        self.frame_win_panel_plain = QFrame()
        self.frame_win_panel_plain.setFrameShape(QFrame.Shape.WinPanel)
        self.frame_win_panel_plain.setFrameShadow(QFrame.Shadow.Plain)
        self.frames.append(self.frame_win_panel_plain)

        self.frame_win_panel_raised = QFrame()
        self.frame_win_panel_raised.setFrameShape(QFrame.Shape.WinPanel)
        self.frame_win_panel_raised.setFrameShadow(QFrame.Shadow.Raised)
        self.frames.append(self.frame_win_panel_raised)

        self.frame_win_panel_sunken = QFrame()
        self.frame_win_panel_sunken.setFrameShape(QFrame.Shape.WinPanel)
        self.frame_win_panel_sunken.setFrameShadow(QFrame.Shadow.Sunken)
        self.frames.append(self.frame_win_panel_sunken)

        # Add Sliders
        self.width_slider = QSlider()
        self.width_slider.setOrientation(Qt.Orientation.Horizontal)
        self.width_slider.setMinimum(0)
        self.width_slider.valueChanged.connect(self.set_frame_width)

        self.mid_width_slider = QSlider()
        self.mid_width_slider.setOrientation(Qt.Orientation.Horizontal)
        self.mid_width_slider.setMinimum(0)
        self.mid_width_slider.valueChanged.connect(self.set_mid_frame_width)

        # Add Labels
        self.width_label = QLabel("Frame Width")
        self.mid_line_width_label = QLabel("Mid Line Width")

        # Add Widgets to Layout
        self.bgl.addWidget(self.width_label, 0, 0)
        self.bgl.addWidget(self.width_slider, 0, 1)
        self.bgl.addWidget(self.mid_line_width_label, 0, 2)
        self.bgl.addWidget(self.mid_width_slider, 0, 3)

        # Frame Labels
        self.bgl.addWidget(QLabel("Plain"), 1, 1)
        self.bgl.addWidget(QLabel("Raised"), 1, 2)
        self.bgl.addWidget(QLabel("Sunken "), 1, 3)

        for i, widget in enumerate(self.frames):
            self.bgl.addWidget(widget, 2 + i // 3, 1 + i % 3)

        # Vertical Labels
        lbl = ["NoFrame", "Box", "Panel", "StyledPanel", "HLine", "VLine", "WinPanel"]

        for i, label in enumerate(lbl):
            self.bgl.addWidget(QLabel(label), 2 + i, 0)

    def set_frame_width(self, width: int):
        """
        Set the frame width for all frames.
        :param width: Width to set.
        """
        print(f"New LineWidth: {width}")
        self.line_width = width
        for frame in self.frames:
            frame.setLineWidth(width)

    def set_mid_frame_width(self, width: int):
        """
        Set the frame width for all frames.
        :param width: Width to set.
        """
        print(f"New MidLineWidth: {width}")
        self.mid_line_width = width
        for frame in self.frames:
            frame.setMidLineWidth(width)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())