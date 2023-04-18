from photo_lib.gui.main_window import RootWindow
import sys
from PyQt6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RootWindow()
    window.show()
    sys.exit(app.exec())
