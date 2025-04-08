from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QMenuBar


"""
File contains an abstract class that defines all methods that a view must implement to interface correctly with the 
MainWindow
"""


class BaseView(ABC):
    @abstractmethod
    def add_menus(self, menu_bar: QMenuBar):
        """
        If the view has actions located in Menus, this function will add the menus to the menu_bar provided.

        :parma menu_bar: menubar to which to add the menus.
        """
        pass

    @abstractmethod
    def remove_menus(self, menu_bar: QMenuBar):
        """
        If the view has actions located in Menus, this function will remove the menus from the menu_bar provided.

        :parma menu_bar: menubar to which to remove the menus.
        """
        pass
