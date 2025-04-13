"""
Contains the two base classes for all tile widgets.
"""
import math
from logging import Logger
from typing import List, Union, Dict

from PyQt6.QtCore import pyqtSignal, QTimer, QPoint, pyqtSlot, Qt
from PyQt6.QtGui import QResizeEvent, QPaintEvent
from PyQt6.QtWidgets import QFrame, QWidget, QGridLayout, QSpacerItem, QSizePolicy

from photo_lib.custom_enum import TargetViewTable, GroupingCriterion, MainTileView
from photo_lib.data_objects import MediaElement, MediaPaths
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.gui.model.frontend_model import UIModel
from photo_lib.gui.temp_new_wigets.clickable_tile import ClickableTile
from photo_lib.gui.temp_new_wigets.new_base_image import BaseImage


# TODO:
#   - HEADER
#   - ANIMATION
#   - SELECTION
class BaseTileWidget(QFrame):
    """
    Basic Tile Widget. Doesn't contain Headers.
    Extensions:
    - Focused Tile
    - Headers
    - Animation
    """
    model: UIModel

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
    _horizontal_spacing: int
    _vertical_spacing: int

    # Read only properties
    __target_table: TargetViewTable

    debug_offset: int = 0

    # UI State variables
    current_row: int = 0
    current_row_offset: int = 0
    lowest_row: int = 0
    highest_row: int = 0

    widgets: Dict[int, ClickableTile]  # Dict of all widgets that are currently instantiated
    tile_rows: List[List[ClickableTile]]
    layout_rows: List[Union[List[Union[QWidget, QSpacerItem]], QSpacerItem]]

    horizontal_spacers: List[QSpacerItem]
    vertical_spacers: List[QSpacerItem]

    background_widget: QWidget
    background_layout: QGridLayout

    resize_timer: QTimer

    logger: Logger

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

        self.model = model
        self.__target_table = target_table

        self.resizeEvent = self._init_resize

        # Set the default values for the properties
        self.__number_of_rows = 0
        self.__number_of_columns = 0
        self.__max_visible_rows = 0
        self.__min_visible_rows = 0
        self.__tile_size = self.model.ui_config.default_tile_size # TODO fetch from preferences.
        self._vertical_spacing = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutVerticalSpacing)
        self._horizontal_spacing = self.style().pixelMetric(self.style().PixelMetric.PM_LayoutHorizontalSpacing)

        self.current_row = 0

        # Initialize the layout and widgets
        self.widgets = {}
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

    def prep_dev(self):
        print(f"INFO: CAll to prep_cev")
        self.setMinimumWidth(350)
        self.setMinimumHeight(350)

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
        INFO: DO NOT CONNECT THE SIGNAL TO current_row. It won't update the widgets

        :param row: THe new current row
        """
        # Perform same action as the property.
        assert self.number_of_rows > row >= 0, \
            f"Current row must be greater than or equal to 0 and less than {self.number_of_rows}"

        # INFO: _scroll_to_row handles updating of the current_row
        # Update the row.
        self._scroll_to_row(row)

        self.current_row_changed.emit(row)

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

        # Update the size of all tiles.
        for tile in self.widgets.values():
            tile.setFixedWidth(self.tile_size)
            tile.setFixedHeight(self.tile_size)

        self.set_tile_size_preference()
        self.update_size()

    @pyqtSlot(int)
    def set_horizontal_spacing(self, spacing: int):
        """
        Slot to update the horizontal spacing.
        INFO: DO NOT CONNECT THE SIGNAL TO horizontal_spacing. It won't update the widgets

        :param spacing: The new horizontal spacing.
        """
        # Perform same action as the property.
        assert spacing >= 0, "Horizontal spacing must be greater than or equal to 0"
        if self._horizontal_spacing == spacing:
            return

        self._horizontal_spacing = spacing

        # Need to update size anyway
        self.update_size()

    @pyqtSlot(int)
    def set_vertical_spacing(self, spacing: int):
        """
        Slot to update the vertical spacing.
        INFO: DO NOT CONNECT THE SIGNAL TO vertical_spacing. It won't update the widgets

        :param spacing: The new vertical spacing.
        """
        assert spacing >= 0, "Vertical spacing must be greater than or equal to 0"
        if self._vertical_spacing == spacing:
            return

        self._vertical_spacing = spacing

        # Update the vertical spacers.
        self.update_size()

    # ==================================================================================================================
    # Functions that need to be implemented differently for every view
    # ==================================================================================================================

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
        self.model.api.db.build_images_table_lookup(grouping=GroupingCriterion.NONE,
                                                    partition=MainTileView.MAIN,
                                                    col_width=self.number_of_columns)

        self.number_of_rows = self.get_number_of_rows()

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
                                     self._vertical_spacing,
                                     QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Expanding)
                self.vertical_spacers.append(spacer)
                self.background_layout.addItem(spacer, i, 0, 1, max_col_count, Qt.AlignmentFlag.AlignCenter)
            else:
                row = self.layout_rows[i // 2]

                # Add rows to the layout
                number_of_elements = len(row) * 2 - 1
                for j in range(number_of_elements):
                    if j % 2 == 1:
                        # Add a horizontal spacer
                        spacer = QSpacerItem(self._horizontal_spacing,
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
                    spacer = QSpacerItem(self._horizontal_spacing,
                                         0,
                                         QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Expanding)
                    self.horizontal_spacers.append(spacer)
                    self.background_layout.addItem(spacer,
                                                   i, number_of_elements,
                                                   1, max_col_count - number_of_elements,
                                                   Qt.AlignmentFlag.AlignCenter)

    def compute_background_widget_offset(self) -> QPoint:
        """
        Determine the position the background widget needs to be moved to, such that current_row is at the top
        """
        cm = self.background_layout.contentsMargins()
        y = 0

        if self.current_row_offset > 0:
            y += cm.top() + self.tile_size

        y += max(0, (self.tile_size + self._vertical_spacing) * (self.current_row_offset - 1))

        self.logger.debug(f"compute_background_widget_offset: {y}, current_row_offset: {self.current_row_offset}")
        return QPoint(0, -y)

    # ==================================================================================================================
    # Main Layout Functions
    # ==================================================================================================================$

    def resize_layout(self):
        """
        Resize the layout and rebuild the widgets.
        """
        # If block needed because of init. We don't know a priori what rows exist and which don't.
        if len(self.tile_rows) > 0:
            # Get the targeted key.
            target_key = self.tile_rows[self.current_row_offset][0].media.element.key
            self.current_row = self.key_to_row(target_key)
        else:
            self.current_row = 0

        self._build_around_row(True)
        self.sanity_check()

    def update_size(self):
        """
        update the size of the background widget and
        """
        if self._recompute_layout_vars():
            self.resize_layout()
            self.layout_from_data_structure()
            self.background_widget.move(self.compute_background_widget_offset())
            self.update()
            self.updateGeometry()

    # ==================================================================================================================
    # Private Functions that only perform specific actions and need to be called in conjunction with each other
    # ==================================================================================================================

    def _scroll_to_row(self, row: int):
        """
        Scroll to a given row using either build or build around functions.

        :param row: The row to scroll to.
        """
        # Abort if we set it to the same value
        if row == self.current_row:
            return

        # We update the layout_rows attribute and update the layout afterwards.
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

        # Determine the minimum number of visible widgets (in this scenario slightly useless. We don't have headers.
        # INFO: We're maxing with a 1, in case the rem_height - self.tile_size < 0,could lead to expression
        #  becoming -1 i.e. self.min_visible_rows = 0
        min_visible_rows = max(1,
                               1 + math.floor(max(0, rem_height - self.tile_size)
                                              / (self.tile_size + self._vertical_spacing)))

        # INFO: We're maxing with a 1, in case teh rem_width - self.tile_size < 0,could lead to expression
        #  becoming -1 i.e. self.min_visible_rows = 0
        number_of_columns = max(1,
                                1 + math.floor(max(0, rem_width - self.tile_size)
                                               / (self.tile_size + self._horizontal_spacing)))

        # Abort if the values are the same.
        if self.max_visible_rows == max_visible_rows \
                and self.number_of_columns == number_of_columns \
                and self.min_visible_rows == min_visible_rows:
            return False

        # Update the number of rows and columns
        self.max_visible_rows = max_visible_rows
        self.number_of_columns = number_of_columns

        self.rebuild_lookup_table()

        self.logger.debug(f"_recompute_layout_vars: "
                          f"Number of rows: {self.number_of_rows}, Number of columns: {self.number_of_columns}, "
                          f"Max visible rows: {self.max_visible_rows}, Min visible rows: {self.min_visible_rows}, "
                          f"Size: {self.size()}, hs: {self._horizontal_spacing}, vs: {self._vertical_spacing}, "
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
                          f"curernt_row_offset: {self.current_row_offset}, ")

        # Create new variables.
        new_widgets = {}
        self.tile_rows = []
        self.layout_rows = []

        # Build the new visible rows
        for i in range(self.lowest_row, self.highest_row + 1):
            # Generate the row
            row = self._generate_row(row=i, reuse=reuse)

            # Add the row to the widget rows
            self.tile_rows.append(row)

            # Add the row to the layout rows
            self.layout_rows.append(row)

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
        row = self._generate_row(row=self.lowest_row)

        # Add the row to the layout.
        self.tile_rows.insert(0, row)
        self.layout_rows.insert(0, row)

        # Add the widget to the widget dict
        for widget in row:
            self.widgets[widget.media.element.key] = widget

    def _add_row_bottom(self):
        """
        Adds a row to the bottom of the layout structure.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.

        PRECONDITION: We aren't at the bottom.
        """
        assert self.highest_row < self.number_of_rows, "PRECONDITION FAILED: Cannot build further down."

        self.highest_row += 1
        row = self._generate_row(row=self.highest_row)

        # Add the row to the layout.
        self.tile_rows.append(row)
        self.layout_rows.append(row)

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
        row = self.tile_rows.pop(0)
        self.lowest_row += 1

        # Remove row from dict
        for widget in row:
            self._destroy_tile(widget)

        # Now remove the row from the layout
        self.layout_rows.pop(0)

    def _remove_row_bottom(self):
        """
        Removes a row at the bottom.

        Doesn't update the widgets in the layout.
        Doesn't move the background widget.

        PRECONDITION: There's at least one row to remove.
        """
        assert self.lowest_row < self.highest_row, "PRECONDITION FAILED: No Row to Remove."

        row = self.tile_rows.pop()
        self.highest_row -= 1

        # Remove row from dict
        for widget in row:
            self._destroy_tile(widget)

        # Now remove the row from the layout
        self.layout_rows.pop()

    def _generate_row(self, row: int, reuse: bool = False) -> List[ClickableTile]:
        """
        Generate a row of widgets.

        :param reuse: We're resizing the layout and want to reuse the widgets.
        :param row: The row to generate.
        """
        media_paths = self.row_to_media_paths(row)

        # Try to get
        result = []

        # INFO: Not putting if in the for loop for performance
        if reuse:
            for mp in media_paths:
                preexisting_widget = self.widgets.get(mp.element.key, None)
                if preexisting_widget is not None:
                    self.logger.debug(f"Reusing Widget for: {preexisting_widget.media.element.key}")
                    result.append(preexisting_widget)
                else:
                    result.append(self._tile_factory(mp))

        else:
            for mp in media_paths:
                result.append(self._tile_factory(mp))

        return result

    def _tile_factory(self, mp: MediaPaths) -> ClickableTile:
        """
        Factory method to create a tile. This is used to create the tiles for the layout and registers it's signals
        with the parent.

        INFO: Doesn't add to the widget dict.

        :param mp: The media paths object to use.
        """
        ct = ClickableTile(mp=mp, model=self.model)
        ct.setFixedWidth(self.tile_size)
        ct.setFixedHeight(self.tile_size)

        # Register the signals
        ct.click.connect(self.click)
        ct.double_click.connect(self.double_click)

        self.logger.debug(f"tile_factory: {ct} key: {ct.media.element.key}")

        return ct

    def _destroy_tile(self, tile: ClickableTile):
        """
        Handle destruction of tile and disconnect the signals.
        """
        self.logger.debug(f"destroy_tile: {tile}, key: {tile.media.element.key}")

        # Remove the tile from the widget dict
        self.widgets.pop(tile.media.element.key)

        # INFO: Disconnect the signals is done by destructor
        # self.click.disconnect(tile.click)
        # self.double_click.disconnect(tile.double_click)

        # Delete the tile
        tile.deleteLater()

    # ==================================================================================================================
    # Custom Event Handlers
    # ==================================================================================================================

    def paintEvent(self, a0: QPaintEvent):
        """
        Capture the paint event in order to update the widget sizing.
        """
        super().paintEvent(a0)
        self.background_widget.adjustSize()
        print(f"Paint Event: ", self.background_widget.size())

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
        if self.get_number_of_rows() == 0:
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