from photo_lib.gui.main_window import RootWindow
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImageReader


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # window = RootWindow()
    window = RootWindow(external_setup=True)
    window.model.set_folder_path("/media/alisot2000/DumpStuff/work_dummy/")
    window.model.current_import_table_name = "tbl_7656102139844435137"
    window.model.import_folder = "/media/alisot2000/DumpStuff/Panos"
    window.build_import_views()
    window.open_import_big_screen()
    h = QImageReader.setAllocationLimit(0)
    v = QPixmapCache.setCacheLimit(1024)
    window.show()
    sys.exit(app.exec())
