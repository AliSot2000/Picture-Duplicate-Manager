"""
Contains the two base classes for all tile widgets.
"""
import math
from collections.abc import Callable
from logging import Logger
from typing import List, Dict, Optional, Hashable, Tuple

import numpy as np
from PyQt6.QtCore import pyqtSignal, QTimer, QPoint, pyqtSlot, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QResizeEvent, QPaintEvent
from PyQt6.QtWidgets import QFrame, QWidget, QGridLayout, QSpacerItem, QSizePolicy

from photo_lib.custom_enum import TargetViewTable, GroupingCriterion, MainTileView
from photo_lib.data_objects import MediaElement, MediaPaths
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.temp_new_wigets.clickable_tile import ClickableTile
from photo_lib.gui.temp_new_wigets.header_widget import CheckableHeaderWidget, HeaderWidget
from photo_lib.gui.temp_new_wigets.new_base_image import BaseImage
from photo_lib.gui.views.enums import FocusMoveY, FocusMoveX


# TODO:
#   - SELECTION
#   - Custom Context Menu
class BaseTileWidget(QFrame):
    """
    Basic Tile Widget. Doesn't contain Headers.
    Extensions:
    - Focused Tile
    - Headers
    - Animation
    """
    model: UIModel
    logger: Logger

    # Define the signals for other elements to work together.
    num_of_rows_changed = pyqtSignal(int)
    number_of_columns_changed = pyqtSignal(int)
    page_size_changed = pyqtSignal(int)
    current_row_changed = pyqtSignal(int)
    tile_size_changed = pyqtSignal(int)

    # Internal variables of properties. Needed to emit the signals when the values change.
    __number_of_rows: int
    __number_of_columns: int
    __max_visible_rows: int
    __min_visible_rows: int
    __tile_size: int
    __horizontal_spacing: int
    __vertical_spacing: int

    # Read only properties
    __target_table: TargetViewTable

    debug_offset: int = 0

    # UI State variables
    current_row: int = 0
    current_row_offset: int = 0
    lowest_row: int = 0
    highest_row: int = 0

    # UI Widgets
    widgets: Dict[int, ClickableTile]  # Dict of all widgets that are currently instantiated
    tile_rows: List[List[ClickableTile]]
    layout_rows: List[List[ClickableTile] | CheckableHeaderWidget | HeaderWidget]  # List of all rows that are currently instantiated

    horizontal_spacers: List[QSpacerItem]
    vertical_spacers: List[QSpacerItem]

    background_widget: QWidget
    background_layout: QGridLayout

    # Headers
    headers: Optional[Dict[Hashable, CheckableHeaderWidget | HeaderWidget]]
    header_lookup: Optional[np.ndarray[int] | np.ndarray[str]] = None
    __checkable_headers: bool
    __has_displayable_headers: bool
    __add_headers: bool
    _header_text_for_row: Optional[Callable[[int], str]] = None

    # Auxiliary items needed for view, resizing, movement animation,
    resize_timer: QTimer

    movement_animation: QPropertyAnimation
    new_current_row: Optional[int] = None

    widget_update_timer: QTimer

    # Focus
    # Contains the currently focused widget if it is present.
    __focused_widget: Optional[ClickableTile | CheckableHeaderWidget] = None

    # Contains the value of the key of the header (needed in the factories, will
    __focus_key_or_header: Optional[int | str] = None

    # first key of a image given a header that is selected
    __focus_target_key: Optional[int] = None

    # Contains the row index in the layout_widgets list
    focus_row: Optional[int] = None

    # Contains the column index in the layout_widgets list
    focus_col: Optional[int] = None

    # Contains the last column if the subsequent layout has less columns than the one before
    last_focus_col: Optional[int] = None

    # ==================================================================================================================
    # Properties
    # We use properties to get and set values. If the value differs from the current value, we emit a signal to notify
    # the all recipients.
    #
    # All properties only emit signals. They do not trigger an update of the UI.
    # This is to avoid infinite recursion.
    # The properties that are also slots, have a setProperty function which is decorated as a slot. The slot function
    # then calls the necessary update functions which set the property and also emit the signal, should this be
    # necessary.
    # ==================================================================================================================

    @property
    def number_of_rows(self) -> int:
        return self.__number_of_rows

    @number_of_rows.setter
    def number_of_rows(self, value: int):
        assert value > 0, "Number of rows must be greater than 0"
        if self.__number_of_rows != value:
            self.__number_of_rows = value
            self.num_of_rows_changed.emit(value)

    @property
    def number_of_columns(self) -> int:
        return self.__number_of_columns

    @number_of_columns.setter
    def number_of_columns(self, value: int):
        assert value > 0, "Number of columns must be greater than 0"
        if self.__number_of_columns != value:
            self.__number_of_columns = value
            self.number_of_columns_changed.emit(value)

    @property
    def max_visible_rows(self) -> int:
        return self.__max_visible_rows

    @max_visible_rows.setter
    def max_visible_rows(self, value: int):
        assert value > 0, "Maximum visible rows must be greater than 0"
        if self.__max_visible_rows != value:
            self.__max_visible_rows = value

    @property
    def min_visible_rows(self) -> int:
        return self.__min_visible_rows

    @min_visible_rows.setter
    def min_visible_rows(self, value: int):
        assert value > 0, "Minimum visible rows must be greater than 0"
        if self.__min_visible_rows != value:
            self.__min_visible_rows = value
            # Info we clamp to 1 in case we have a tiny window.
            self.page_size_changed.emit(max(1, value))

    @property
    def tile_size(self) -> int:
        return self.__tile_size

    @tile_size.setter
    def tile_size(self, value: int):
        assert value > 0, "Tile size must be greater than 0"
        if self.__tile_size != value:
            self.__tile_size = value
            self.tile_size_changed.emit(value)
            self.set_tile_size_preference()

            cm = self.background_layout.contentsMargins()
            self.setMinimumWidth(value + cm.left() + cm.right())
            self.setMinimumHeight(value + cm.top() + cm.bottom())

    @property
    def focused_widget(self):
        return self.__focused_widget
    
    @focused_widget.setter
    def focused_widget(self, value: ClickableTile | CheckableHeaderWidget):
        if self.__focused_widget == value:
            return

        # Unmark the current focused widget
        if self.__focused_widget is not None:
            self._unmark_focus_widget()
        
        self.__focused_widget = value

        # Mark the new focused widget
        if self.__focused_widget is not None:
            self._mark_focus_widget()

    # ==================================================================================================================
    # Read only properties
    # ==================================================================================================================

    @property
    def number_of_generated_rows(self) -> int:
        return min(self.number_of_rows,
                   self.max_visible_rows * (2 * self.model.ui_config.tile_page_preload_count + 1))

    @property
    def target_table(self):
        return self.__target_table

    @property
    def horizontal_spacing(self):
        return self.__horizontal_spacing

    @property
    def vertical_spacing(self):
        return self.__vertical_spacing

    @property
    def add_headers(self):
        return self._add_headers

    @property
    def has_displayable_headers(self):
        return self._has_displayable_headers

    @property
    def checkable_headers(self):
        return self._checkable_headers

    @property
    def focus_key_or_header(self):
        return self.__focus_key_or_header

    @property
    def focus_target_key(self):
        return self.__focus_target_key

    # ==================================================================================================================
    # Constructor
    # ==================================================================================================================

    def __init__(self, model: UIModel, target_table: TargetViewTable, logger: Logger, parent: QWidget = None):
        """
        Initialize the base tile widget. This is the base class for all tile widgets.
        :param model: The UIModel to use.
        :param parent: The parent widget.
        """
        # We add a logger to keep track of the function calls.
        self.logger = logger

        super().__init__(parent=parent)
        self.setStyleSheet("background-color: palette(base);")

        self.model = model
        self.__target_table = target_table

        self.resizeEvent = self._init_resize

        # Set the default values for the properties
        self.__number_of_rows = 0
        self.__number_of_columns = 0
        self.__max_visible_rows = 0
        self.__min_visible_rows = 0
        # TODO fetch from preferences.
        # TODO update widget min size
        self.__tile_size = self.model.ui_config.tile_size_default
        self.__vertical_spacing = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutVerticalSpacing)
        self.__horizontal_spacing = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutHorizontalSpacing)

        self.current_row = 0

        # Initialize the layout and widgets
        self.widgets = {}
        self.headers = {}
        self.tile_rows = []
        self.layout_rows = []

        self.horizontal_spacers = []
        self.vertical_spacers = []

        self.background_layout = QGridLayout()
        self.background_layout.setHorizontalSpacing(0)
        self.background_layout.setVerticalSpacing(0)

        self.background_widget = QWidget(self)
        self.background_widget.move(QPoint(0, 0))
        self.background_widget.setStyleSheet("background-color: palette(base);")
        self.background_widget.setLayout(self.background_layout)

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(self.model.ui_config.tile_resize_timeout_ms)
        self.resize_timer.timeout.connect(self.update_size)

        self.widget_update_timer = QTimer(self)
        self.widget_update_timer.setSingleShot(True)
        self.widget_update_timer.setInterval(10)
        self.widget_update_timer.timeout.connect(self.update_widget)

        self.movement_animation = QPropertyAnimation(self.background_widget, b"pos")
        self.movement_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.movement_animation.finished.connect(self.widget_update_timer.start)

        # Set header properties
        # TODO need to set these attributes in the child classes that implement this.
        self._checkable_headers: bool = True
        self._has_displayable_headers: bool = True
        self._add_headers: bool = True

        assert hasattr(self, "_checkable_headers"), "Checkable headers not set in child class"
        assert hasattr(self, "_has_displayable_headers"), "Has displayable headers not set in child class"
        assert hasattr(self, "_add_headers"), "Add headers not set in child class"

        # TODO move
        self.setMinimumWidth(200)
        self.setMinimumHeight(200)

        self._set_focus_target(264)

    # ==================================================================================================================
    # Slots
    # ==================================================================================================================

    @pyqtSlot(int)
    def set_current_row_from_key(self, key: int):
        """
        Given a key, set the current row to that.
        """
        # Get the row from the key.
        row = self.key_to_row(key)

        # Set the current row.
        self.set_current_row(row)

    @pyqtSlot(int)
    def set_current_row(self, row: int):
        """
        Set the current row. This is the top most visible row.

        :param row: THe new current row
        """
        # Perform same action as the property.
        assert self.number_of_rows > row >= 0, \
            f"Current row must be greater than or equal to 0 and less than {self.number_of_rows}"

        # INFO: scroll_animation handles updating of the current_row
        # Update the row.
        if self.scroll_animation(row):
            self.current_row_changed.emit(row)

        self.dump_focus_info()

    @pyqtSlot(int)
    def set_tile_size(self, size: int):
        """
        Slot to update the tile size.
        INFO: DO NOT CONNECT THE SIGNAL TO tile_size. It won't update the widgets

        :param size: The new tile size.
        """
        # Perform same action as the property.
        assert size > 0, "Tile size must be greater than 0"
        if self.__tile_size == size:
            return

        self.__tile_size = size
        self.tile_size_changed.emit(size)

        cm = self.background_layout.contentsMargins()
        self.setMinimumWidth(self.tile_size + cm.left() + cm.right())
        self.setMinimumHeight(self.tile_size + cm.top() + cm.bottom())

        # Update the size of all tiles.
        for tile in self.widgets.values():
            tile.setFixedWidth(self.tile_size)
            tile.setFixedHeight(self.tile_size)

        self.set_tile_size_preference()
        if not self.update_size():
            self.background_widget.move(self.compute_background_widget_offset())
            self.update()
            self.updateGeometry()

    @pyqtSlot(int)
    def set_horizontal_spacing(self, spacing: int):
        """
        Slot to update the horizontal spacing.
        INFO: DO NOT CONNECT THE SIGNAL TO horizontal_spacing. It won't update the widgets

        :param spacing: The new horizontal spacing.
        """
        # Perform same action as the property.
        assert spacing >= 0, "Horizontal spacing must be greater than or equal to 0"
        if self.__horizontal_spacing == spacing:
            return

        self.__horizontal_spacing = spacing

        # Need to update size anyway
        if not self.update_size():
            for spacer in self.horizontal_spacers:
                spacer.changeSize(self.__horizontal_spacing, 0,
                                  QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.background_widget.move(self.compute_background_widget_offset())
            self.update()
            self.updateGeometry()
            return
        else:
            # INFO: The update layout was triggered and the spacers were added and updated already.
            pass

    @pyqtSlot(int)
    def set_vertical_spacing(self, spacing: int):
        """
        Slot to update the vertical spacing.
        INFO: DO NOT CONNECT THE SIGNAL TO vertical_spacing. It won't update the widgets

        :param spacing: The new vertical spacing.
        """
        assert spacing >= 0, "Vertical spacing must be greater than or equal to 0"
        if self.__vertical_spacing == spacing:
            return

        self.__vertical_spacing = spacing

        # Update the vertical spacers.
        if not self.update_size():
            for spacer in self.vertical_spacers:
                spacer.changeSize(0, self.__vertical_spacing,
                                  QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            self.background_widget.move(self.compute_background_widget_offset())
            self.update()
            self.updateGeometry()
            return
        else:
            # INFO: The update layout was triggered and the spacers were added and updated already.
            pass

    def set_headers(self, add_headers: bool):
        """
        Set whether we are displaying headers or not.
        """
        if self._add_headers == add_headers:
            return

        self._add_headers = add_headers
        self.logger.debug(f"set_headers: {self.add_headers}")

        # Rebuild the layout
        if not self.update_header_available_and_type():
            raise ImplementationError("Attempting to set headers visible in a view that doesn't support it.")

        self.update_size()
        self.layout_from_data_structure()
        self.background_widget.move(self.compute_background_widget_offset())
        self.update()
        self.updateGeometry()

    # ==================================================================================================================
    # Focus Functions
    # ==================================================================================================================

    @pyqtSlot(int)
    def focus_key(self, target_key: int):
        """
        Set the focus to a specific key.

        PRECONDITION: The given key exists in the lot

        :param target_key: The key to focus on.
        """
        # Widget isn't loaded, scroll to its location.
        if self.widgets.get(target_key, None) is None:
            self._set_focus_target(focus=target_key)
            self.scroll_animation(self.key_to_row(target_key))
            return

        self._set_focus_target(target_key)
        self.focused_widget = self.widgets[target_key]
        abs_row = self.key_to_row(target_key)
        focused_tile_row = self.tile_rows[abs_row - self.lowest_row]

        # Determine the focus_row and focus_col
        self.focus_row = self.layout_rows.index(focused_tile_row)
        self.focus_col = focused_tile_row.index(self.focused_widget)

        # Unset the last_focused_col
        self.last_focus_col = None

        self._scroll_focused_widget_into_view()
        # INFO: Nothing is needed. All variable set

    # INFO:
    #   WRAP AROUND PROPERTIES:
    #       Y: NO
    #       x: yes
    #       direction: config
    @pyqtSlot()
    def move_focus_up(self):
        """
        Move the focus up by one row.
        """
        if self.focused_widget is None:
            self._set_focus_to_top_left()
            return

        # Check limit
        if self._focus_row_at_top():
            self.logger.debug("Focus at top, can't move up")
            return

        self._move_focus(x=FocusMoveX.NONE, y=FocusMoveY.UP)

    @pyqtSlot()
    def move_focus_down(self):
        """
        Move the focus down by one row.
        """
        if self.focused_widget is None:
            self._set_focus_to_top_left()
            return

        # Abort if we've reached thw bottom, no special determinations, the lowest row will never be a header
        if self._focus_row_at_bottom():
            self.logger.debug(f"Focus at bottom, can't move down")
            return

        self._move_focus(x=FocusMoveX.NONE, y=FocusMoveY.DOWN)
        self.dump_focus_info()
    
    @pyqtSlot()
    def move_focus_left(self):
        """
        Move the focus to the left by one column.
        """
        if self.focused_widget is None:
            self._set_focus_to_top_left()
            return

        if self.focus_col == 0:
            # Guard we're at the top and wrap up
            if self.model.ui_config.tile_wrap_around_x_down and self._focus_row_at_top():
                self.logger.debug("Move Left wrap around up and at top. Can't move left")
                return

            # Guard we're at the bottom and wrap down
            if not self.model.ui_config.tile_wrap_around_x_down and self._focus_row_at_bottom():
                self.logger.debug("Move Left wrap around down and at bottom. Can't move left")
                return

            # Move with Wrap
            self._move_focus(x=FocusMoveX.RIGHT_LIMIT,
                             y=FocusMoveY.UP if self.model.ui_config.tile_wrap_around_x_down else FocusMoveY.DOWN)
            self.dump_focus_info()
            return

        self._move_focus(x=FocusMoveX.LEFT, y=FocusMoveY.NONE)
        self.dump_focus_info()

    @pyqtSlot()
    def move_focus_right(self):
        """
        Move the focus to the right by one column.
        """
        if self.focused_widget is None:
            self._set_focus_to_top_left()
            return

        # We're at the right end
        focused_row = self.layout_rows[self.focus_row]
        focused_row_len = len(focused_row) if isinstance(focused_row, list) else 1
        if self.focus_col == focused_row_len - 1:

            # Guard, we're at the bottom and want to wrap down.
            if self.model.ui_config.tile_wrap_around_x_down and self._focus_row_at_bottom():
                self.logger.debug("Move Right wrap around down and at bottom. Can't move right")
                return

            # Guard we're at the top, and want to wrap up
            if not self.model.ui_config.tile_wrap_around_x_down and self._focus_row_at_top():
                self.logger.debug("Move Right wrap around up and at top. Can't move right")
                return

            # Move with wrap
            self._move_focus(x=FocusMoveX.LEFT_LIMIT,
                             y=FocusMoveY.DOWN if self.model.ui_config.tile_wrap_around_x_down else FocusMoveY.UP)
            self.dump_focus_info()
            return

        self._move_focus(x=FocusMoveX.RIGHT, y=FocusMoveY.NONE)
        self.dump_focus_info()
        
    def _set_focus_target(self, focus: int | str, target_key: int = None):
        """
        Set the focus to a specific widget.

        PRECONDITION: The key exists in the given ui lookup table

        :param focus: The key or header to focus on.
        :param target_key: The target key to focus on.
        """
        if isinstance(focus, str):
            assert target_key is not None, "Target key must be set if focus is a header."
            self.__focus_key_or_header = focus
            self.__focus_target_key = target_key
        elif isinstance(focus, int):
            self.__focus_key_or_header = focus
            self.__focus_target_key = None
        else:
            raise ImplementationError("Focus must be either a key or a header.")

    def _scroll_focused_widget_into_view(self) -> bool:
        """
        Check if the widget is currently outside the view.
        If yes, scroll to the widget such that it is in view.

        PRECONDITION: focused_widget is not None

        :returns: True -> Scroll took place, Widget not Visible, False -> No scroll took place. Widget visible.
        """
        # self.logger.debug(f"Focused Widget Top Left: {self.focused_widget.mapToGlobal(QPoint(0, 0))}, "
        #                   f"Tile Widget Top Left: {self.mapToGlobal(QPoint(0, 0))}")
        # self.logger.debug(f"Focused Widget Bottom Right: {self.focused_widget.mapToGlobal(self.focused_widget.rect().bottomRight())}, "
        #                   f"Tile Widget Bottom Right: {self.mapToGlobal(self.rect().bottomRight())}")
        #
        # self.logger.debug(f"Focus Top: {self.focused_widget.mapToGlobal(QPoint(0, 0)).y()}, "
        #                   f"Widget Top: {self.mapToGlobal(QPoint(0, 0)).y()}")
        # self.logger.debug(f"Focused Widget Bottom: {self.focused_widget.mapToGlobal(self.focused_widget.rect().bottomRight()).y()}, "
        #                   f"Widget Bottom: {self.mapToGlobal(self.rect().bottomRight()).y()}")

        # Test if widget is out of bounds at the top
        if self.focused_widget.mapToGlobal(QPoint(0, 0)).y() < self.mapToGlobal(QPoint(0, 0)).y():
            row = self.layout_rows[self.focus_row]

            if not isinstance(row, list):
                # PRECONDITION: we have a header
                row = self.layout_rows[self.focus_row + 1]
                assert isinstance(row, list), "PRECONDITION failed: no two headers after each other"

            # Get the index of that row
            target_row_offset = self.tile_rows.index(row)
            absolute_target_row = self.lowest_row + target_row_offset

            self.scroll_animation(absolute_target_row)
            return True

        elif self.mapToGlobal(self.rect().bottomRight()).y() < self.focused_widget.mapToGlobal(self.focused_widget.rect().bottomRight()).y():
            row = self.layout_rows[self.focus_row]

            if not isinstance(row, list):
                # PRECONDITION: we have a header
                # PRECONDITION: Last row is always a list
                row = self.layout_rows[self.focus_row + 1]
                assert isinstance(row, list), "PRECONDITION failed: no two headers after each other"

            target_row_offset = self.tile_rows.index(row)
            # Determine the absolute row such that we can scroll to it.
            self.scroll_animation(self._min_offset_for_visibility_of(target_row_offset))
            return True

        return False

    def _min_offset_for_visibility_of(self, target_offset: int) -> int:
        """
        Determine the current_row_offset such that the given target comes into view at the bottom.

        PRECONDITION: the rect().bottom() of the target row is greater than the self.rect().top().

        :param target_offset: The offset of the target row. in the self.tiles

        :returns: absolute row to scroll to for the given target offset to be in view (target offset in
        """
        target_widget = self.tile_rows[target_offset][0]
        target_y = target_widget.mapToGlobal(target_widget.rect().bottomRight()).y()
        current_y = self.background_widget.mapToGlobal(QPoint(0, 0)).y()
        cm = self.background_layout.contentsMargins()

        if self.add_headers:
            for i in range(len(self.layout_rows)):
                row = self.layout_rows[i]
                v_space = self.vertical_spacing if i > 0 else cm.top()

                if isinstance(row, list):
                    current_y += self.tile_size + v_space
                else:
                    assert isinstance(row, CheckableHeaderWidget) or isinstance(row, HeaderWidget), \
                        f"PRECONDITION FAILED: Unexpected row in self.layout_rows: {row}"
                    current_y += row.height() + v_space

                    # Continue, because we don't want to check the visibility if the current row is a header
                    continue

                # Abort condition, we've found the correct row
                if current_y + self.height() > target_y:
                    offset = self.tile_rows.index(row)
                    return self.lowest_row + offset + 1

        else:
            return self.lowest_row + max(0, target_offset - self.min_visible_rows)

    def _move_focus(self, x: FocusMoveX, y: FocusMoveY):
        """
        Move the focus to a specific widget AND scroll it into view.

        PRECONDITION:
        focus_row is not None
        focus_col is not None
        focus_widget is not None

        :param x: The x coordinate to move to.
        :param y: The y coordinate to move to.
        """
        assert self.focused_widget is not None, "Focused widget must be set before moving focus."

        # Simple left or right move
        if y == FocusMoveY.NONE:
            # We're having an explicit left or right move. Clear the last_focus_col
            self.last_focus_col = None

            # Handle case when we're simply moving left
            if x == FocusMoveX.LEFT:
                new_tgt_widget = self.layout_rows[self.focus_row][self.focus_col - 1]
                self.focused_widget = new_tgt_widget
                self.focus_col -= 1

            elif x == FocusMoveX.RIGHT:
                new_tgt_widget = self.layout_rows[self.focus_row][self.focus_col + 1]
                self.focused_widget = new_tgt_widget
                self.focus_col += 1
            else:
                raise ImplementationError("PRECONDITION Failed: FocusMoveX must be LEFT or RIGHT for FocusMoveY.NONE")

            self._scroll_focused_widget_into_view()
            return

        elif y == FocusMoveY.UP:
            assert x not in (FocusMoveX.LEFT, FocusMoveX.RIGHT), \
                "PRECONDITION failed: FocusMoveX must be NONE, LEFT_LIMIT or RIGHT_LIMIT for FocusMoveY.UP"
            if isinstance(self.focus_key_or_header, int):
                current_abs_focus_row = self.key_to_row(self.focus_key_or_header)
            else:
                current_abs_focus_row = self.key_to_row(self.focus_target_key)

            new_abs_focus_row = current_abs_focus_row - 1
            current_row = self.row_to_media_paths(current_abs_focus_row)
            new_row = self.row_to_media_paths(new_abs_focus_row)

            if self._move_focus_to_header(cur_abs_f_row=current_abs_focus_row,
                                          new_abs_f_row=new_abs_focus_row,
                                          target_key=current_row[0].element.key,
                                          up=True,
                                          top_override=new_abs_focus_row == -1):
                    return


            self._move_focus_vertical_to_image(row=new_row, x_action=x, new_abs_f_row=new_abs_focus_row)

        elif y == FocusMoveY.DOWN:
            assert x not in (FocusMoveX.LEFT, FocusMoveX.RIGHT), \
                "PRECONDITION failed: FocusMoveX must be NONE, LEFT_LIMIT or RIGHT_LIMIT for FocusMoveY.UP"

            if isinstance(self.focus_key_or_header, int):
                current_abs_focus_row = self.key_to_row(self.focus_key_or_header)
                new_abs_focus_row = current_abs_focus_row + 1
            else:
                current_abs_focus_row = self.key_to_row(self.focus_target_key)
                new_abs_focus_row = current_abs_focus_row

            new_row = self.row_to_media_paths(new_abs_focus_row)

            # Check if the next widget is supposed to be a header
            if self._move_focus_to_header(cur_abs_f_row=current_abs_focus_row,
                                          new_abs_f_row=new_abs_focus_row,
                                          target_key=new_row[0].element.key,
                                          up=False,
                                          top_override=False):
                    return

            self._move_focus_vertical_to_image(row=new_row, x_action=x, new_abs_f_row=new_abs_focus_row)

        else:  # pragma: no cover
            raise ImplementationError("Uncovered Case FocusMoveY")

    def _focus_row_at_top(self) -> bool:
        """
        Check if the focused widget is in the lowest possible row.
        """
        if self.lowest_row != 0:
            return False

        if self.add_headers:
            # Abort with checkable headers and we're at 0
            if self.checkable_headers and self.focus_row == 0:
                return True

            # Abort with not checkable headers, but headers present, and we're at 1
            if not self.checkable_headers and self.focus_row == 1:
                return True

        else:
            # PRECONDITION: no headers
            # Abort without headers and we're at 0
            if self.focus_row == 0:
                return True

        return False

    def _focus_row_at_bottom(self) -> bool:
        """
        Check if the focused widget is in the highest possible row.
        """
        return self.highest_row == self.number_of_rows - 1 and self.focus_row == len(self.layout_rows) - 1

    def _determine_focused_widget(self, row: List[MediaPaths]):
        """
        Given a list of media paths, determine the focused widget. Update the focus_row and focus_col if the given
        widget exists in the self.widgets

        :param row: The row in which to determine the focused widget based on focus_col and last_focus_col
        """
        if self.last_focus_col is not None:
            # The given column exists again, set focus to that column and unset the last_focus_col var
            if len(row) > self.last_focus_col:
                focused_mp = row[self.last_focus_col]
                self.last_focus_col = None

            else:
                # The given column doesn't exist. Take right most widget
                focused_mp = row[-1]

        else:
            # PRECONDITION: last_focus_col is None
            if len(row) <= self.focus_col:
                # The given focus column doesn't exist, take the right most widget
                focused_mp = row[-1]
                self.last_focus_col = self.focus_col

            else:
                # The given focus column exists, take that widget
                focused_mp = row[self.focus_col]

        self._set_focus_target(focus=focused_mp.element.key)

    def _move_focus_to_header(self, cur_abs_f_row: int, new_abs_f_row, target_key: int, up: bool, top_override: bool) \
            -> bool:
        """
        Given the current focus, attempt to move the focus to a header.

        :returns: True, if the next focused element is a header.
        """

        # Check if the next widget is supposed to be a header
        if self.add_headers and self.checkable_headers:

            # Get the header of the current row and of the next row
            current_header_text = self._header_text_for_row(cur_abs_f_row)
            new_header_text = None if top_override else self._header_text_for_row(new_abs_f_row)

            # If they are different, and we're in a row of images, set the header as next target.
            if (new_header_text != current_header_text and self.focus_target_key is None) or top_override:
                assert isinstance(self.focus_key_or_header, int), \
                    "PRECONDITION failed: focus_key_or_header must be an int"
                self._set_focus_target(focus=current_header_text if up else new_header_text, target_key=target_key)

                # Either scroll the given header into view or scroll to the new row
                if (widget := self.headers.get(self.focus_key_or_header, None)) is not None:
                    self.focused_widget = widget
                    self.focus_row = self.layout_rows.index(widget)

                    if self.last_focus_col is None and self.focus_col > 0:
                        self.last_focus_col = self.focus_col

                    self.focus_col = 0

                    self._scroll_focused_widget_into_view()
                else:
                    self.scroll_animation(new_abs_f_row)

                return True

        return False

    def _move_focus_vertical_to_image(self, row: List[MediaPaths], x_action: FocusMoveX, new_abs_f_row: int):
        """
        Deal with moving the focus up or down to an image.

        :param row: The MediaPaths of the row to move to.
        :param x_action: The action to take in the x direction.
        :param new_abs_f_row: The new absolute row to move to.
        """
        # PRECONDITION: we move the focus to a row of images
        if x_action == FocusMoveX.LEFT_LIMIT:
            self.last_focus_col = None
            self._set_focus_target(focus=row[0].element.key)
        elif x_action == FocusMoveX.RIGHT_LIMIT:
            self.last_focus_col = None
            self._set_focus_target(focus=row[-1].element.key)
        elif x_action == FocusMoveX.NONE:
            self._determine_focused_widget(row)
        else:
            raise ImplementationError("PRECONDITION Failed: "
                                      "FocusMoveX must be LEFT, RIGHT or NONE for FocusMoveY.UP")

        # Widget doesn't exist
        if (fw := self.widgets.get(self.focus_key_or_header, None)) is None:
            self.scroll_animation(new_abs_f_row)
            return

        # PRECONDITION: Widget of the focused key exists.
        self.focused_widget = fw
        tile_row = None

        # Determine the focus col and get the pointer to the focused row
        for i, r in enumerate(self.tile_rows):
            if self.focused_widget in r:
                tile_row = r
                self.focus_col = r.index(self.focused_widget)
                break

        # Determine  the focus row
        self.focus_row = self.layout_rows.index(tile_row)
        self._scroll_focused_widget_into_view()

    def _set_focus_to_top_left(self):
        """
        When focus operations are performed but the focused widget is not loaded, set the focus to the image in the top
        left.

        # PRECONDITION: We have more than row
        # PRECONDITION: Each row contains at least one widget.
        """
        self.logger.debug("Setting focus to top left")
        tgt_row = self.tile_rows[self.current_row_offset]
        tgt_widget = tgt_row[0]
        tgt_key = tgt_widget.media.element.key

        self._set_focus_target(focus=tgt_key)
        self.focused_widget = tgt_widget
        self.focus_col = 0
        self.focus_row = self.layout_rows.index(tgt_row)

    def update_focus_info(self, widget: ClickableTile | CheckableHeaderWidget | HeaderWidget, col: int):
        """
        Update the focus information, given that the focus_key_or_header is being constructed in a factory

        :param widget: The widget to update the focus information for.
        :param col: The column in the layout tables where we find the widget
        """
        self.focused_widget = widget
        self.focus_col = col

    def clear_focus_info(self):
        """
        Clear the focus information when the widget is unloaded.
        """
        self.focus_row = None
        self.focus_col = None
        self.last_focus_col = None
        self.focused_widget = None

    def _mark_focus_widget(self):
        """
        Mark the focus widget.

        PRECONDITION: self.focused_widget is not None
        """
        self.focused_widget.setLineWidth(3)
        self.focused_widget.setMidLineWidth(3)
        self.focused_widget.setFrameShape(QFrame.Shape.Box)
        self.focused_widget.setFrameShadow(QFrame.Shadow.Plain)

    def _unmark_focus_widget(self):
        """
        Unmarks the currently set focus widget.

        PRECONDITION: self.focused_widget is not None
        """
        self.focused_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.focused_widget.setFrameShadow(QFrame.Shadow.Plain)

    def dump_focus_info(self):
        self.logger.debug(f"Focused Widget: {self.focused_widget}, "
                          f"Focus Key or Header: {self.focus_key_or_header}, "
                          f"Focus Target: {self.focus_target_key}, "
                          f"Focus Row: {self.focus_row}, "
                          f"Focus Col: {self.focus_col}, "
                          f"Last Focus Col: {self.last_focus_col}")


    # ==================================================================================================================
    # Functions that need to be implemented differently for every view
    # ==================================================================================================================

    @pyqtSlot(CheckableHeaderWidget)
    def header_changed(self, header: CheckableHeaderWidget):
        """
        The value of a header changed, capture it here and update the associated tiles.
        """
        self.logger.debug(f"Header Changed: {header.text()}")

    @pyqtSlot(BaseImage)
    def click(self, tile: BaseImage):
        """
        Handle left click on tile.
        """
        self.logger.debug("Registered Left Click on: " + str(tile.media.element.key))

    @pyqtSlot(BaseImage)
    def double_click(self, tile: BaseImage):
        """
        Handle right click on tile.
        """
        self.logger.debug("Registered Double Click on: " + str(tile.media.element.key))

    def set_tile_size_preference(self):
        """
        Needs to be implemented in child view.
        """
        self.model.ui_preferences.tile_size_main_main = self.tile_size
        self.model.write_preferences()

    def rebuild_lookup_table(self):
        """
        Rebuild the table for the layout
        """
        print("Temporary implementation!!!")
        self.model.api.db.clear_ui_lookup_table(target_table=self.target_table)

        # This call should be changed.
        self.model.api.db.build_main_table_lookup(grouping=GroupingCriterion.YEAR,
                                                  partition=MainTileView.MAIN,
                                                  col_width=self.number_of_columns)

        self.number_of_rows = self.get_number_of_rows()

    def update_header_available_and_type(self) -> bool:
        """
        Determine if the given tiles we're rendering have displayable headers or not.

        :returns: bool -> To indicate whether the setting of the add_header state (and associated states) was successful
        """
        # TODO implement this function for all target views.
        print("Temporary Implementation!!!")
        # Update the has_displayable_headers (needed for label with scrollbar)
        if self.target_table == TargetViewTable.MAIN:
            if self.model.api.db.last_main_grouping_criterion == GroupingCriterion.NONE:
                self.__has_displayable_headers = True
                self.__checkable_headers = False
                self.__add_headers = False
            else:
                self.__has_displayable_headers = True
                self.__checkable_headers = True
                self.__add_headers = True
        elif self.target_table == TargetViewTable.IMPORT:
            self.__has_displayable_headers = True
            self.__checkable_headers = True
        elif self.target_table == TargetViewTable.PRESENCE:
            self.__has_displayable_headers = True
            self.__checkable_headers = False
        elif self.target_table == TargetViewTable.HASH:
            self.__has_displayable_headers = False
            self.__checkable_headers = False
        elif self.target_table == TargetViewTable.NAME:
            self.__has_displayable_headers = True
            self.__checkable_headers = False
        elif self.target_table == TargetViewTable.LOCATION:
            self.__has_displayable_headers = True
            self.__checkable_headers = False
        else:  # pragma: no cover
            raise ImplementationError("Uncovered Target View Table")

        # We attempted to make a layout with headers, but we don't have headers.
        if not self.has_displayable_headers and self.add_headers:
            self.logger.warning("Add Headers was True for ui which doens't have displayable headers")
            self.__add_headers = False
            return False

        return True

    # ==================================================================================================================
    # Main Functions
    # ==================================================================================================================$

    def update_widget(self):
        """
        Update the widget after the animation has finished.
        """
        # Abort if we don't have anything set
        if self.new_current_row is None:
            return

        # Update the current row
        self._scroll_to_row(self.new_current_row)
        self.new_current_row = None

        self.layout_from_data_structure()
        self.background_widget.move(self.compute_background_widget_offset())
        self.update()
        self.updateGeometry()
        self.current_row_changed.emit(self.current_row)

    def update_size(self) -> bool:
        """
        Performs:
        - Updates the size of the background widget
        - Updates the Lookup table for the ui
        - Rebuilds the layout
        - Moves the background widget to the correct position
        - Triggers update of geometry and update of the widget.

        :return: True if the layout was updated.
        """
        if not self._recompute_layout_vars():
            return False

        if self.has_displayable_headers:
            self.rebuild_header_lookup()

        # If block needed because of init. We don't know a priori what rows exist and which don't.
        if len(self.tile_rows) > 0:
            # Get the targeted key.
            target_key = self.tile_rows[self.current_row_offset][0].media.element.key
            self.current_row = self.key_to_row(target_key)
        else:
            self.current_row = 0

        self._build_around_row(True)
        self.sanity_check()

        self.layout_from_data_structure()
        self.background_widget.move(self.compute_background_widget_offset())
        self.update()
        self.updateGeometry()
        return True

    def scroll_animation(self, row: int) -> bool:
        """
        Perform the scroll animation.

        :param row: Row to scroll to (relative to abolute number of rows)
        """
        # Abort if we
        if row == self.current_row:
            return False

        # Abort if the animation is disabled
        if not self.model.ui_config.tile_animation:
            self._scroll_to_row(row)
            return True

        # Abort if we're out of bounds
        middle_cutoff = self.lowest_row + self.max_visible_rows * (self.model.ui_config.tile_page_preload_count * 2)
        if self.highest_row != self.number_of_rows - 1:
            if not self.lowest_row <= row <= middle_cutoff:
                self.movement_animation.stop()
                self.new_current_row = None
                self._scroll_to_row(row)
                return True

        else:
            # INFO: We're at the top row, use the full range to scroll
            if not self.lowest_row <= row <= self.highest_row:
                self.movement_animation.stop()
                self.new_current_row = None
                self._scroll_to_row(row)
                return True

        # Stop animation and restart with new value
        if self.movement_animation.state() == QPropertyAnimation.State.Running:
            self.movement_animation.stop()

        start = self.background_widget.pos()
        self.movement_animation.setDuration(self.model.ui_config.tile_animation_duration_ms)
        self.movement_animation.setStartValue(start)
        self.new_current_row = row

        end = self.compute_background_widget_offset(target_offset=self.current_row_offset + row - self.current_row)
        self.movement_animation.setEndValue(end)
        self.movement_animation.start()
        return False

    def rebuild_header_lookup(self):
        """
        Rebuild the header cache and set the get_header function.
        """
        if self.number_of_rows < self.model.ui_config.header_lookup_limit:
            all_headers = self.model.api.db.get_all_headers(self.target_table)

            # Cover TargetView Enum
            if self.target_table == TargetViewTable.MAIN:
                self.header_lookup = np.array(all_headers, dtype=str)
            elif self.target_table == TargetViewTable.IMPORT:
                self.header_lookup = np.array(all_headers, dtype=int)
            elif self.target_table == TargetViewTable.PRESENCE:
                self.header_lookup = np.array(all_headers, dtype=int)
            elif self.target_table == TargetViewTable.HASH:
                raise ImplementationError("Hash Table shouldn't have a header.")
            elif self.target_table == TargetViewTable.NAME:
                self.header_lookup = np.array(all_headers, dtype=int)
            elif self.target_table == TargetViewTable.LOCATION:
                self.header_lookup = np.array(all_headers, dtype=int)
            else:  # pragma: no cover
                raise ImplementationError("Uncovered Target View Table")

            self._header_text_for_row = self._header_text_from_cache

        else:
            # PRECONDITION: We have more rows than our lookup limit
            self._header_text_for_row = self._header_text_from_db

    def layout_from_data_structure(self):
        """
        Set the layout from the data structure.
        """
        # Empty layout
        while self.background_layout.count() > 0:
            self.background_layout.takeAt(0)

        # Bugfix, need to clear the spacers
        self.vertical_spacers = []
        self.horizontal_spacers = []

        # Populate layout again
        row_count = len(self.layout_rows) * 2 - 1
        max_col_count = self.number_of_columns * 2 - 1

        for i in range(row_count):
            if i % 2 == 1:
                # Add a vertical spacer
                spacer = QSpacerItem(0,
                                     self.vertical_spacing,
                                     QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
                self.vertical_spacers.append(spacer)
                self.background_layout.addItem(spacer, i, 0, 1, max_col_count, Qt.AlignmentFlag.AlignCenter)
            else:
                row = self.layout_rows[i // 2]

                # We have a list of ClickableTiles, we're only doing
                if isinstance(row, list):
                    # Add rows to the layout
                    number_of_elements = len(row) * 2 - 1
                    for j in range(number_of_elements):
                        if j % 2 == 1:
                            # Add a horizontal spacer
                            spacer = QSpacerItem(self.horizontal_spacing,
                                                 0,
                                                 QSizePolicy.Policy.Expanding,
                                                 QSizePolicy.Policy.Expanding)
                            self.horizontal_spacers.append(spacer)
                            self.background_layout.addItem(spacer,
                                                           i, j,
                                                           1, 1,
                                                           Qt.AlignmentFlag.AlignCenter)
                        else:
                            # Add the widget to the layout
                            widget = row[j // 2]
                            self.background_layout.addWidget(widget,
                                                             i, j,
                                                             1, 1,
                                                             Qt.AlignmentFlag.AlignCenter)

                    if number_of_elements < max_col_count:
                        # Add a horizontal spacer
                        spacer = QSpacerItem(self.horizontal_spacing,
                                             0,
                                             QSizePolicy.Policy.Expanding,
                                             QSizePolicy.Policy.Expanding)
                        self.horizontal_spacers.append(spacer)
                        self.background_layout.addItem(spacer,
                                                       i, number_of_elements,
                                                       1, max_col_count - number_of_elements,
                                                       Qt.AlignmentFlag.AlignCenter)
                else:
                    self.background_layout.addWidget(row, i, 0, 1, max_col_count)

    def compute_background_widget_offset(self, target_offset: int = None) -> QPoint:
        """
        Determine the position the background widget needs to be moved to, such that current_row is at the top

        :param target_offset: (If you want a different offset than the current_row_offset
        """
        offset = target_offset if target_offset is not None else self.current_row_offset
        cm = self.background_layout.contentsMargins()
        y = self.debug_offset

        if self.add_headers:
            if offset > 0:
                target_row = self.tile_rows[offset]

                for i in range(len(self.layout_rows)):
                    row = self.layout_rows[i]
                    v_space = self.vertical_spacing if i > 0 else cm.top()
                    if isinstance(row, list):
                        y += self.tile_size + v_space
                    else:
                        assert isinstance(row, CheckableHeaderWidget) or isinstance(row, HeaderWidget), \
                            f"PRECONDITION FAILED: Unexpected row in self.layout_rows: {row}"
                        y += row.height() + v_space

                    # Abort condition
                    if self.layout_rows[i + 1] == target_row:
                        # Checking not list bc we could have CheckableHeaderWidget or HEaderWidget
                        if not isinstance(self.layout_rows[i], list):
                            y -= (self.layout_rows[i].height() + v_space)

                        # Break in any case, we've reached our target row
                        break
            else:
                # PRECONDITION: We want row 0
                pass

        else:
            if offset > 0:
                y += cm.top() + self.tile_size

            y += max(0, (self.tile_size + self.vertical_spacing) * (offset - 1))

        self.logger.debug(f"compute_background_widget_offset: {y}, offset: {offset}")
        return QPoint(0, -y)

    def row_to_media_paths(self, row: int) -> List[MediaPaths]:
        """
        Get the keys for a row.

        :param row: The row to get the keys for.
        :return: The keys for the row.
        """
        print("Temporary implementation!!!")
        row = self.model.api.db.lookup_row_to_keys(row, target_view=self.target_table)

        # Get the media paths objects.
        media_paths = [self.model.api.db.get_media(MediaElement(key=i, source_table=self.target_table)) for i in row]

        return media_paths

    def key_to_row(self, key: int) -> int:
        """
        Get the row for a key.

        :param key: The key to get the row for.
        :return: The row for the key.
        """
        print("Temporary implementation!!!")
        return self.model.api.db.lookup_key_to_row(key=key, target_view=self.target_table)

    def get_number_of_rows(self):
        """
        Get the number of ui rows from the database.
        """
        return self.model.api.db.lookup_row_count(self.target_table)

    # ==================================================================================================================
    # Private Functions that only perform specific actions and need to be called in conjunction with each other
    # ==================================================================================================================

    def _header_text_from_cache(self, row: int) -> str:
        """
        Implementation of getting the header string from the lookup array and parsing the compressed value with the
        header parser of the database

        :param row: Row to get header for
        """
        assert 0 <= row < self.number_of_rows, "PRECONDITION FAILED: Row out of bounds"
        return self.model.api.db.parse_header(self.header_lookup[row], target_view=self.target_table)

    def _header_text_from_db(self, row: int) -> str:
        """
        Implementation of getting the header string from the database (which mey or may not have a cache for this)
        header parser of the database

        :param row: Row to get header for
        """
        assert 0 <= row < self.number_of_rows, "PRECONDITION FAILED: Row out of bounds"
        return self.model.api.db.lookup_row_to_header(row, target_view=self.target_table)

    def _scroll_to_row(self, row: int):
        """
        Scroll to a given row using either build or build around functions.

        PRECONDITION: row != self.current_row

        :param row: The row to scroll to.
        """
        # We update the layout_rows attribute and update the layout afterward.
        if self.lowest_row <= row <= self.highest_row:
            while self.current_row < row:
                self.logger.debug("scroll_to_row: Building Down")
                self._current_row_down()

            while self.current_row > row:
                self.logger.debug("scroll_to_row: Building Up")
                self._current_row_up()

        else:
            self.current_row = row
            # We're out of range, build the row around the current row.
            self._build_around_row(reuse=False)

        self.layout_from_data_structure()
        self.background_widget.move(self.compute_background_widget_offset())
        self.sanity_check()
        self.update()
        self.updateGeometry()

    def _recompute_layout_vars(self) -> bool:
        """
        Given:
        - the size of the widget,
        - the contentMargins of the layout,
        - the horizontal and vertical spacing and the
        - the tile size

        Computes:
        - number of columns
        - maximum number of visible rows
        - minimum number of visible rows
        - number of rows
        - rebuilds the lookup table

        :returns True if one of the layout variables changed
        (number of rows, number of columns, max visible rows, min visible rows)
        """
        # Update the background widget's size
        self.background_widget.setFixedWidth(self.width())

        layout_margin = self.background_layout.contentsMargins()

        rem_width = self.width() - layout_margin.right() - layout_margin.left()
        rem_height = self.height() - layout_margin.top() - layout_margin.bottom()

        # Determine the new maximum number of visible widgets
        max_visible_rows = math.ceil(rem_height / self.tile_size)

        # INFO:
        #   max(0, rem_width - self.tile_size) >= 0.
        #   => max(0, rem_width - self.tile_size) / (self.tile_size + self.horizontal_spacing) >= 0
        #   => math.floor(max(0, rem_width - self.tile_size) / (self.tile_size + self.horizontal_spacing)) >= 0
        number_of_columns = 1 + math.floor(max(0, rem_width - self.tile_size)
                                           / (self.tile_size + self.horizontal_spacing))

        if not self.add_headers:
            # Determine the minimum number of visible widgets (in this scenario slightly useless. We don't have headers.
            # INFO:
            #   max(0, rem_height - self.tile_size) >= 0.
            #   => max(0, rem_height - self.tile_size) / (self.tile_size + self.vertical_spacing) >= 0
            #   => math.floor(max(0, rem_height - self.tile_size) / (self.tile_size + self.vertical_spacing)) >= 0
            min_visible_rows = 1 + math.floor(max(0, rem_height - self.tile_size)
                                              / (self.tile_size + self.vertical_spacing))

        else:
            row_height = self.tile_size + self.vertical_spacing + CheckableHeaderWidget(text="Some Text").height()

            # INFO:
            #   max(0, rem_height - row_height) >= 0.
            #   => max(0, rem_height - row_height) / (row_height + self.vertical_spacing) >= 0
            #   => math.floor(max(0, rem_height - row_height) / (row_height + self.vertical_spacing)) >= 0
            min_visible_rows = 1 + math.floor(max(0, rem_height - row_height) / (row_height + self.vertical_spacing))

        # Abort if the values are the same.
        if self.max_visible_rows == max_visible_rows \
                and self.number_of_columns == number_of_columns \
                and self.min_visible_rows == min_visible_rows:
            return False

        # Update the number of rows and columns
        rebuild_table = self.number_of_columns != number_of_columns
        self.max_visible_rows = max_visible_rows
        self.min_visible_rows = min_visible_rows
        self.number_of_columns = number_of_columns

        # Optimized call, only rebuild tables if the number of columns changed
        if rebuild_table:
            self.rebuild_lookup_table()

        self.logger.debug(f"_recompute_layout_vars: "
                          f"Number of rows: {self.number_of_rows}, Number of columns: {self.number_of_columns}, "
                          f"Max visible rows: {self.max_visible_rows}, Min visible rows: {self.min_visible_rows}, "
                          f"Size: {self.size()}, hs: {self.horizontal_spacing}, vs: {self.vertical_spacing}, "
                          f"Tile Size: {self.tile_size}, "
                          f"max_widget_count: {self.number_of_generated_rows * self.number_of_columns}")

        return True

    def _build_around_row(self, reuse: bool = False):
        """
        Build the view / the rows around the current_row
        """
        bottom_cutoff = self.number_of_rows - (1 + self.model.ui_config.tile_page_preload_count) * self.max_visible_rows

        if self.current_row > bottom_cutoff:
            # We're at the very bottom and we need to calculate the highest row first and the nthe lowest row from that.
            self.highest_row = min(self.number_of_rows - 1,
                                   self.current_row
                                   + (self.max_visible_rows * self.model.ui_config.tile_page_preload_count) - 1)

            self.lowest_row = max(0, self.highest_row - self.number_of_generated_rows + 1)
        else:
            # Determine lowest row
            self.lowest_row = max(0, self.current_row -
                                  (self.max_visible_rows * self.model.ui_config.tile_page_preload_count))

            # Determine the highest row
            self.highest_row = min(self.number_of_rows - 1,
                                   self.lowest_row
                                   + (2 * self.model.ui_config.tile_page_preload_count + 1)
                                   * self.max_visible_rows
                                   - 1)

        self.current_row_offset = self.current_row - self.lowest_row

        self.logger.debug(f"_build_around_row: "
                          f"reuse: {reuse}, "
                          f"current_row: {self.current_row}, "
                          f"lowest_row: {self.lowest_row}, "
                          f"highest_row: {self.highest_row}, "
                          f"current_row_offset: {self.current_row_offset}, ")

        if self.add_headers:
            self._build_around_with_header(reuse=reuse)

        else:
            self._build_around_without_header(reuse=reuse)

    def _build_around_with_header(self, reuse: bool):
        """
        Build the rows when we have headers.

        PRECONDITION: No Headers
        PRECONDITION: self.lowest_row, self.highest_row, self.current_row_offset
        """
        # Create new variables.
        new_headers = {}
        new_widgets = {}
        self.tile_rows = []
        self.layout_rows = []

        # Special case when we're at the bottom (cannot query if the self.lowest_row -1 has a different header than
        # the current lowest row
        if self.lowest_row == 0:
            header, is_focus = self._header_factory(row=0, reuse=reuse)
            new_headers[header.text()] = header
            self.layout_rows.append(header)

            # Set focus row if needed
            self.focus_row = 0 if is_focus else self.focus_row

            first_row, is_focus = self._generate_row(row=0, reuse=reuse)

            self.focus_row = 1 if is_focus else self.focus_row

            # Add the row to the widgets
            for element in first_row:
                new_widgets[element.media.element.key] = element

            self.tile_rows.append(first_row)
            self.layout_rows.append(first_row)

            loop_lower_bound = 1
        else:
            loop_lower_bound = self.lowest_row

        # Build every subsequent row after the first one
        for i in range(loop_lower_bound, self.highest_row + 1):

            # Add headers if the rows are different
            if self._header_text_for_row(i - 1) != self._header_text_for_row(i):
                header, is_focus = self._header_factory(row=i, reuse=reuse)
                new_headers[header.text()] = header
                self.layout_rows.append(header)
                self.focus_row = len(self.layout_rows) - 1 if is_focus else self.focus_row

            # Generate the row
            row, is_focus = self._generate_row(row=i, reuse=reuse)

            # Add the row to the widget rows
            self.tile_rows.append(row)

            # Add the row to the layout rows
            self.layout_rows.append(row)

            self.focus_row = len(self.layout_rows) - 1 if is_focus else self.focus_row

            # Add the widgets to the dict
            for widget in row:
                new_widgets[widget.media.element.key] = widget

        # Get all the rows that aren't in the new rows
        to_delete_tiles = list(filter(lambda x: x not in new_widgets.values(), self.widgets.values()))
        for elm in to_delete_tiles:
            self._destroy_tile(elm)

        # Get all the headers that aren't in the new rows
        to_delete_headers = list(filter(lambda x: x not in new_headers.values(), self.headers.values()))
        for elm in to_delete_headers:
            self._destroy_header(elm)

        self.widgets = new_widgets
        self.headers = new_headers

    def _build_around_without_header(self, reuse: bool):
        """
        Build the rows when we don't have headers.

        PRECONDITION: No headers
        PRECONDITION: self.lowest_row, self.highest_row, self.current_row_offset
        """
        # Create new variables.
        new_widgets = {}
        self.tile_rows = []
        self.layout_rows = []

        # Build the new visible rows
        for i in range(self.lowest_row, self.highest_row + 1):
            # Generate the row
            row, is_focus = self._generate_row(row=i, reuse=reuse)

            # Add the row to the widget rows
            self.tile_rows.append(row)

            # Add the row to the layout rows
            self.layout_rows.append(row)

            self.focus_row = i if is_focus else self.focus_row

            # Add the widgets to the dict
            for widget in row:
                new_widgets[widget.media.element.key] = widget

        # Get all the rows that aren't in the new rows
        to_delete = list(filter(lambda x: x not in new_widgets.values(), self.widgets.values()))

        for elm in to_delete:
            self._destroy_tile(elm)

        self.widgets = new_widgets

    def _current_row_up(self):
        """
        We want to move the current row up. I.e. current row -= 1. Update the widgets and offsets to achieve this.
        that.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.
        """
        # We can not add rows anymore.
        if self.lowest_row == 0:
            # Sanity check done here, just in case
            if self.current_row < 0:  # pragma: no cover
                raise ImplementationError("PRECONDITION FAILED: Current row is less than 0.")

            elif self.current_row == 0:
                self.logger.debug("_current_row_up: TOP Reached")
                return

            # We can move up using the current_row_offset
            self.current_row -= 1
            self.current_row_offset -= 1
            self.logger.debug("_current_row_up: TOP, Moving up using offset.")
            return

        # We're at the very bottom, we move up first by changing the offset.
        if self.highest_row == self.number_of_rows - 1 \
            and self.current_row_offset != self.max_visible_rows * self.model.ui_config.tile_page_preload_count:
            self.current_row_offset -= 1
            self.current_row -= 1
            self.logger.debug("_current_row_up: BOTTOM, Moving up using offset.")
            return

        # We're somewhere in the middle. Add a row to the top and remove one at the bottom, keep the offsets the same
        self.current_row -= 1
        self._add_row_top()
        self._remove_row_bottom()
        self.logger.debug("_current_row_up: MIDDLE, Moving up by building.")

    def _current_row_down(self):
        """
        We want to move the current row down. I.e. current row -= 1. Update the widgets and offsets to achieve this.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.
        """
        # We cannot add rows to the bottom.
        if self.highest_row == self.number_of_rows - 1:
            # Sanity check done here, just in case
            if self.current_row >= self.number_of_rows:  # pragma: no cover
                raise ImplementationError("PRECONDITION FAILED: Current row is greater than number of rows.")

            elif self.current_row == self.number_of_rows - 1:
                self.logger.debug("_current_row_down: BOTTOM Reached")
                return

            # We can move down using the current_row_offset
            self.current_row_offset += 1
            self.current_row += 1
            self.logger.debug("_current_row_down: BOTTOM, Moving down using offset.")
            return

        # We're at the very top, we move down first by changing the offset.
        if self.lowest_row == 0 and self.current_row_offset != self.max_visible_rows:
            self.current_row_offset += 1
            self.current_row += 1
            self.logger.debug("_current_row_down: TOP, Moving down using offset.")
            return

        # We're somewhere in the middle. Add a row to the bottom and remove one at the top, keep the offsets the same
        self.current_row += 1
        self._add_row_bottom()
        self._remove_row_top()
        self.logger.debug("_current_row_down: MIDDLE, Moving down by building.")

    def _add_row_top(self):
        """
        Adds a row to the top of the layout structure.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.

        PRECONDITION: We aren't at the top.
        """
        assert self.lowest_row > 0, "PRECONDITION FAILED: Cannot build further up."

        self.lowest_row -= 1

        if self.add_headers \
                and self._header_text_for_row(self.lowest_row) != self._header_text_for_row(self.lowest_row + 1):
            # Add header between the current lowest row and the new lowest row if they have different headers.
            header, is_focus = self._header_factory(row=self.lowest_row + 1)
            self.headers[header.text()] = header
            self.layout_rows.insert(0, header)
            self.focus_row = 0 if is_focus else (self.focus_row - 1 if self.focus_row is not None else self.focus_row)

        # Add the row we want to generate
        row, is_focus = self._generate_row(row=self.lowest_row)
        self.focus_row = 0 if is_focus else (self.focus_row - 1 if self.focus_row is not None else self.focus_row)

        # Add the row to the layout.
        self.tile_rows.insert(0, row)
        self.layout_rows.insert(0, row)

        # Add the widget to the widget dict
        for widget in row:
            self.widgets[widget.media.element.key] = widget

        # Add the first header if we're at the top
        if self.add_headers and self.lowest_row == 0:
            header, is_focus = self._header_factory(row=0)
            self.headers[header.text()] = header
            self.layout_rows.insert(0, header)
            self.focus_row = 0 if is_focus else (self.focus_row - 1 if self.focus_row is not None else self.focus_row)

    def _add_row_bottom(self):
        """
        Adds a row to the bottom of the layout structure.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.

        PRECONDITION: We aren't at the bottom.
        """
        assert self.highest_row < self.number_of_rows, "PRECONDITION FAILED: Cannot build further down."
        self.highest_row += 1

        # Add header if necessary
        if self.add_headers and \
                self._header_text_for_row(self.highest_row) != self._header_text_for_row(self.highest_row - 1):
            header, is_focus = self._header_factory(row=self.highest_row)
            self.headers[header.text()] = header
            self.layout_rows.append(header)
            self.focus_row = len(self.layout_rows) - 1 if is_focus else self.focus_row

        row, is_focus = self._generate_row(row=self.highest_row)

        # Add the row to the layout.
        self.tile_rows.append(row)
        self.layout_rows.append(row)
        self.focus_row = len(self.layout_rows) - 1 if is_focus else self.focus_row

        # Add the widget to the widget dict
        for widget in row:
            self.widgets[widget.media.element.key] = widget

    def _remove_row_top(self):
        """
        Removes a row at the top.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.

        PRECONDITION: There's at least one row to remove..
        """
        assert self.lowest_row < self.highest_row, "PRECONDITION FAILED: No Row to Remove."
        self.lowest_row += 1

        row = self.layout_rows.pop(0)

        if isinstance(row, CheckableHeaderWidget):
            # Update focus row for a header
            self.focus_row = self.focus_row - 1 if self.focus_row is not None else self.focus_row
            self._destroy_header(row)
            row = self.layout_rows.pop(0)

        # Update focus row for a regular row
        self.focus_row = self.focus_row - 1 if self.focus_row is not None else self.focus_row
        assert isinstance(row, list), "PRECONDITION: At most one header between two rows of ClickableTiles"

        # Remove row from dict
        for widget in row:
            self._destroy_tile(widget)

        # Now remove the row from the layout
        self.tile_rows.pop(0)

    def _remove_row_bottom(self):
        """
        Removes a row at the bottom.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.

        PRECONDITION: There's at least one row to remove.
        """
        assert self.lowest_row < self.highest_row, "PRECONDITION FAILED: No Row to Remove."
        self.highest_row -= 1

        row = self.tile_rows.pop()

        # Remove row from dict
        for widget in row:
            self._destroy_tile(widget)

        # Now remove the row from the layout
        row = self.layout_rows.pop()
        assert isinstance(row, list), "PRECONDITION: Lowest row is ALWAYS a list of ClickableTiles"

        if isinstance(self.layout_rows[-1], CheckableHeaderWidget):
            header = self.layout_rows.pop()
            self._destroy_header(header)

    def _generate_row(self, row: int, reuse: bool = False) -> Tuple[List[ClickableTile], bool]:
        """
        Generate a row of widgets.

        :param reuse: We're resizing the layout and want to reuse the widgets.
        :param row: The row to generate.
        """
        media_paths = self.row_to_media_paths(row)

        # Try to get
        result = []
        focus_contained = False

        # INFO: Not putting if in the for loop for performance
        if reuse:
            for i, mp in enumerate(media_paths):
                if (widget := self.widgets.get(mp.element.key, None)) is not None:
                    self.logger.debug(f"Reusing Widget for: {widget}")
                else:
                    widget = self._tile_factory(mp)

                # Handle case when we've got the focus widget in the row
                if focus_contained := widget.media.element.key == self.focus_key_or_header:
                    self.update_focus_info(widget, i)

                result.append(widget)
        else:
            for i, mp in enumerate(media_paths):
                widget = self._tile_factory(mp)

                # Handle case when we've got the focus widget in the row
                if focus_contained := widget.media.element.key == self.focus_key_or_header:
                    self.update_focus_info(widget, i)

                result.append(widget)

        return result, focus_contained

    def _tile_factory(self, mp: MediaPaths) -> ClickableTile:
        """
        Factory method to create a tile. This is used to create the tiles for the layout and registers it's signals
        with the parent.

        INFO: Doesn't add to the widget dict.
        INFO: Doesn't take care of focus.

        :param mp: The media paths object to use.
        """
        ct = ClickableTile(mp=mp, model=self.model)
        ct.setFixedWidth(self.tile_size)
        ct.setFixedHeight(self.tile_size)

        # ct.setLineWidth(3)
        # ct.setMidLineWidth(3)
        # ct.setFrameShape(QFrame.Shape.Box)
        # ct.setFrameShadow(QFrame.Shadow.Sunken)

        # Register the signals
        ct.click.connect(self.click)
        ct.double_click.connect(self.double_click)

        # self.logger.debug(f"tile_factory: {ct} key: {ct.media.element.key}")

        return ct

    def _destroy_tile(self, tile: ClickableTile):
        """
        Handle destruction of tile and disconnect the signals.
        """
        # self.logger.debug(f"destroy_tile: {tile}, key: {tile.media.element.key}")

        # Remove the tile from the widget dict
        self.widgets.pop(tile.media.element.key)

        # We're destroying a tile that has the focus key, we need to reset the focus
        if tile.media.element.key == self.focus_key_or_header:
            self.clear_focus_info()

        # INFO: Disconnect the signals is done by destructor
        # self.click.disconnect(tile.click)
        # self.double_click.disconnect(tile.double_click)

        # Delete the tile
        tile.deleteLater()

    def _header_factory(self, row: int, reuse: bool = False) -> Tuple[CheckableHeaderWidget | HeaderWidget, bool]:
        """
        Produces the header associated with a given row. If reuse is True, attempt to find the header already existing.

        :param row: Row to generate header for
        :param reuse: Whether to attempt to reuse a header or not
        """
        header_text = self._header_text_for_row(row)

        if reuse:
            if (header_widget := self.headers.get(header_text, None)) is not None:
                self.logger.debug(f"Reusing Header: {header_text}")

                if __debug__:  # pragma: no cover
                    if self.checkable_headers:
                        assert isinstance(header_widget, CheckableHeaderWidget), \
                            "PRECONDITION FAILED: Unexpected type of widget"
                    else:
                        assert isinstance(header_widget, HeaderWidget), \
                            "PRECONDITION FAILED: Unexpected type of widget"

                if is_focus := header_text == self.focus_key_or_header:
                    self.update_focus_info(header_widget, 0)

                return header_widget, is_focus

        if self.checkable_headers:
            header_widget = CheckableHeaderWidget(header_text)

            # Connect the signal
            header_widget.box_changed.connect(self.header_changed)
        else:
            header_widget = HeaderWidget(header_text)

        # Deal with focus
        if is_focus := header_text == self.focus_key_or_header:
            self.update_focus_info(header_widget, 0)

        return header_widget, is_focus

    def _destroy_header(self, header: CheckableHeaderWidget):
        """
        Destroy a header and also remove it from the header dict (reuse dict)

        :param header: Header to destroy
        """
        self.logger.debug(f"destroy_header: {header}, text: {header.text()}")

        self.headers.pop(header.text())
        if header.text() == self.focus_key_or_header:
            self.clear_focus_info()

        # INFO: Disconnect the signals is done by destructor
        # self.header_changed.disconnect(header.box_changed)

        header.deleteLater()

    # ==================================================================================================================
    # Custom Event Handlers
    # ==================================================================================================================

    def paintEvent(self, a0: QPaintEvent):
        """
        Capture the paint event in order to update the widget sizing.
        """
        super().paintEvent(a0)
        self.background_widget.adjustSize()

    def resizeEvent(self, event: QResizeEvent):
        """
        Custom handler to do resizing. Schedules a timer instead of resizing immediately. Resizing is expensive and we
        want to minimize its calls
        """
        # INFO: Will be overwritten in init.
        ...

    def _init_resize(self, event: QResizeEvent):
        """
        This is called in the initial resize event, and we immediately want to produce a layout.

        :param event: The resize event.
        """
        super().resizeEvent(event)
        self.update_size()
        self.resizeEvent = self._regular_resize

        # Check the number of rows. If there are no rows, we don't want to create the view.
        if self.get_number_of_rows() == 0:  # pragma: no cover
            raise ImplementationError("View shouldn't be created if no rows are available.")

    def _regular_resize(self, event: QResizeEvent):
        """
        This is the regular resize event. We want to schedule a timer to do the resizing.
        """
        super().resizeEvent(event)
        self.resize_timer.start()

    # Might be useful for debugging.
    # def keyPressEvent(self, a0: QKeyEvent) -> None:
    #     """
    #     Catch keys from keyboard and move the carousel accordingly.
    #     :param a0:
    #     :return:
    #     """
    #     super().keyPressEvent(a0)
    #     if a0.key() == Qt.Key.Key_Up and a0.modifiers() == Qt.KeyboardModifier.NoModifier:
    #         self.scroll_offset -= 10
    #         self.place_background_widget()
    #     elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.NoModifier:
    #         self.scroll_offset += 10
    #         self.place_background_widget()
    #     elif a0.key() == Qt.Key.Key_Up and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
    #         self._d_up()
    #         # self.dump_widgets()
    #     elif a0.key() == Qt.Key.Key_Down and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
    #         self._build_down()
    #         # self.dump_widgets()
    #     elif a0.key() == Qt.Key.Key_R and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
    #         self.scroll_offset = 0
    #         self.place_background_widget()
    #     else:
    #         pass

    def sanity_check(self):
        """
        Ensure we have the correct number of widgets.
        """
        assert len(self.tile_rows) == self.number_of_generated_rows,\
            f"Number of rows is incorrect: {self.number_of_generated_rows} expected, got {len(self.tile_rows)}"

        assert self.highest_row - self.lowest_row == self.number_of_generated_rows - 1, \
            (f"Lowes and Highest row tracker incorrect. Expected: {self.number_of_generated_rows - 1}, "
             f"got: {self.highest_row - self.lowest_row}")

        assert self.lowest_row <= self.current_row <= self.highest_row, \
            (f"Current row is out of bounds: lowest_row: {self.lowest_row}, highest_row: {self.highest_row}, "
             f"current_row: {self.current_row}")

        assert self.number_of_generated_rows > self.current_row_offset >= 0, \
            f"Current row offset is out of bounds, max: {self.number_of_generated_rows}, got: {self.current_row_offset}"