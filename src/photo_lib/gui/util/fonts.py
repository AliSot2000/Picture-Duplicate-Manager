"""
This file contains a small shorthand for fonts, We use the Fonts provided by QT (in order to follow in line with the
system.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont


def get_sys_font() -> QFont:
    """
    Wrapper that gets the system default font.
    """
    return QApplication.font()


def get_sys_font_size_float() -> float:
    """
    Gets the system default font size in points.
    """
    return QApplication.font().pointSizeF()


def get_sys_font_size_int() -> int:
    """
    Gets the system default font size in points.
    """
    return QApplication.font().pointSize()


def get_h1_font_size() -> int:
    """
    Get equivalent of H1 font size = 2x get_sys_font_size
    """
    return int(QApplication.font().pointSizeF() * 2)


def get_h2_font_size() -> int:
    """
    Get equivalent of H2 font size = 1.5x get_sys_font_size
    """
    return int(QApplication.font().pointSizeF() * 1.5)


def get_h3_font_size() -> int:
    """
    Get equivalent of H3 font size = 1.3x get_sys_font_size
    """
    return int(QApplication.font().pointSizeF() * 1.3)


def get_h4_font_size() -> int:
    """
    Get equivalent of H4 font size = 1x get_sys_font_size
    """
    return int(QApplication.font().pointSizeF() * 1)


def get_h5_font_size() -> int:
    """
    Get equivalent of H1 font size = 0.8x get_sys_font_size
    """
    return int(QApplication.font().pointSizeF() * 0.8)


def get_h6_font_size() -> int:
    """
    Get equivalent of H1 font size = 0.7x get_sys_font_size
    """
    return int(QApplication.font().pointSizeF() * 0.7)
