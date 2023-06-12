from PyQt6.QtWidgets import QHBoxLayout, QLabel
from photo_lib.gui.action_button import QActionButton


class ButtonBar(QLabel):

    next_button: QActionButton
    commit_all: QActionButton
    commit_selected: QActionButton
    status: QLabel

    box_layout: QHBoxLayout

    def __init__(self):
        super().__init__()
        self.next_button = QActionButton("Next")
        self.next_button.setToolTip("Move to next duplicate cluster in database")
        self.next_button.setMaximumWidth(150)

        self.commit_all = QActionButton("Commit All")
        self.commit_all.setToolTip("Set the entry marked as main as the original, remove all other entries from the database")
        self.commit_all.setMaximumWidth(150)

        self.commit_selected = QActionButton("Commit Selected")
        self.commit_selected.setToolTip("Set the entry marked as main as the original, remove all as delete marked entries from the database")
        self.commit_selected.setMaximumWidth(150)

        self.status = QLabel("Remaining Duplicates: 0")

        self.box_layout = QHBoxLayout()
        self.setLayout(self.box_layout)

        self.box_layout.addWidget(self.status)
        self.box_layout.addWidget(self.commit_all)
        self.box_layout.addWidget(self.commit_selected)
        self.box_layout.addWidget(self.next_button)

        self.setFixedHeight(45)

        # m = self.box_layout.contentsMargins()
        # print(f"Margins: {m.left()} {m.top()} {m.right()} {m.bottom()}")
        # self.setGeometry(0, 0, 500, 50)
        # self.setStyleSheet("background-color: #000000; color: #ffffff;")