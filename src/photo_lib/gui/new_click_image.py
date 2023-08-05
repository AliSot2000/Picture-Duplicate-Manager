from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
class ClickableImage(QWidget):
    clicked = pyqtSignal()
    pixmap = None
    def __init__(self, file_path: str):
        super().__init__()
        self.load_image(file_path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def load_image(self, file_path: str):
        self.fpath = file_path
        self.pixmap = QPixmap(file_path)
        self.updateGeometry()
        if not self.pixmap.isNull() and self.isVisible():
            self.update()

    def sizeHint(self):
        if self.pixmap and not self.pixmap.isNull():
            return self.pixmap.size()
        return QSize()

    def paintEvent(self, event):
        if not self.pixmap or self.pixmap.isNull():
            return
        if self.size() == self.pixmap.size():
            r = self.rect()
        else:
            r = QRect(QPoint(),
                self.pixmap.size().scaled(self.size(), Qt.KeepAspectRatio))
            r.moveCenter(self.rect().center())
        qp = QPainter(self)
        qp.drawPixmap(r, self.pixmap)

