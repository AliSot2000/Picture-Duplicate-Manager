from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QLabel

class ButtonBar(QWidget):

    next_button: QPushButton
    commit_all: QPushButton
    commit_selected: QPushButton
    status: QLabel

    box_layout: QHBoxLayout

    def __init__(self):
        super().__init__()
        self.next_button = QPushButton("Next")
        self.next_button.setToolTip("Move to next duplicate cluster in database")
        self.next_button.setMaximumWidth(150)

        self.commit_all = QPushButton("Commit All")
        self.commit_all.setToolTip("Set the entry marked as main as the original, remove all other entries from the database")
        self.commit_all.setMaximumWidth(150)

        self.commit_selected = QPushButton("Commit Selected")
        self.commit_selected.setToolTip("Set the entry marked as main as the original, remove all as delete marked entries from the database")
        self.commit_selected.setMaximumWidth(150)

        self.status = QLabel("Remaining Duplicates: 0")

        self.box_layout = QHBoxLayout()
        # self.box_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.box_layout)

        self.box_layout.addWidget(self.status)
        self.box_layout.addWidget(self.commit_all)
        self.box_layout.addWidget(self.commit_selected)
        self.box_layout.addWidget(self.next_button)

        self.setMaximumHeight(50)