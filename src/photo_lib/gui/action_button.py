from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QAction
from typing import Union

class QActionButton(QPushButton):
    __target_action: Union[None, QAction] = None
    def __init__(self, *args, target_action: QAction = None, **kwargs):
        """
        Passes args and kwargs to QPushButton
        specific kwarg needed for the action button is target_action
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)

        self.target_action = target_action

    @property
    def target_action(self):
        return self.__target_action

    @target_action.setter
    def target_action(self, target_action: QAction):
        # if target_action is present,
        if self.__target_action is not None:
            self.target_action.changed.connect(self.update_button_from_action)
            self.clicked.disconnect(self.target_action.trigger)

        self.__target_action = target_action
        self.update_button_from_action()
        if self.__target_action is None:
            return

        self.target_action.changed.connect(self.update_button_from_action)
        self.clicked.connect(self.target_action.trigger)

    def update_button_from_action(self):
        """
        Copy the attributes relevante to the button from the action.
        :return:
        """

        if self.target_action is None:
            return

        self.setText(self.target_action.text())
        self.setStatusTip(self.target_action.statusTip())
        self.setToolTip(self.target_action.toolTip())
        self.setIcon(self.target_action.icon())
        self.setEnabled(self.target_action.isEnabled())
        self.setCheckable(self.target_action.isCheckable())
        self.setChecked(self.target_action.isChecked())
