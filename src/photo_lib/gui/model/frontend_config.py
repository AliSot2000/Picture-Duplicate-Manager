from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


"""
Idea for this config - this is what you can modify from a settings pane
"""

# TODO, the settings here should be categorized by config and tunables.
class UIConfig(BaseModel):
    """
    Contains actually user configurable settings.
    """
    header_lookup_limit: int = Field(
        default=1048576,
        description="For performance, the headers of the rows are cached in ram. This only works for sufficiently "
                    "small db. At some point, the header resolution needs to happen via the db. This transition is set "
                    "via this config attribute.")

    load_parent_automatically: bool = Field(
        default=True,
        description="For Duplicate Images, all media is deleted. When asked to display an element that is marked as a "
                    "duplicate, by default the parent is used to provide images to display. It is possible to turn "
                    "this off and load the parent only on request."
    )

    minimum_width_for_compare_widget: int = Field(
        default=300,
        description="Minimum width for Panes in the CompareView."
    )

    key_cache_size: int = Field(
        default=16384,
        description="Maximum size of the key to row lookup cache."
    )

    object_cache_size: int = Field(
        default=1024,
        description="Maximum size of the object to row lookup and header lookup cache."
    )

    force_theme_dark: Optional[bool] = Field(
        default=None,
        description="Force the application to use dark mode if True, force to bright if False. "
                    "The override exists to deal with the case when the colorSchema from the system is unknown."
    )

    # TODO add validator to check if the color names are valid (also allow for rgb and hex)
    bright_color_name_success: str = Field(
        default="green",
        description="Color name for success in bright mode. Can be changed to account for disabilities."
    )
    bright_color_name_fail: str = Field(
        default="red",
        description="Color name for fail in bright mode. Can be changed to account for disabilities."
    )
    bright_color_name_select: str = Field(
        default="blue",
        description="Color name for select in bright mode. Can be changed to account for disabilities."
    )

    dark_color_name_success: str = Field(
        default="darkGreen",
        description="Color name for success in dark mode. Can be changed to account for disabilities."
    )
    dark_color_name_fail: str = Field(
        default="darkRed",
        description="Color name for fail in dark mode. Can be changed to account for disabilities."
    )
    dark_color_name_select: str = Field(
        default="darkBlue",
        description="Color name for select in dark mode. Can be changed to account for disabilities."
    )

    scale_down_trigger_ratio: float = Field(
        lt=1.0,
        gt=0.0,
        default=0.5,
        description="Ratio for the scale down trigger. If the ratio between the displayed size and the pixmap size is "
                    "less than this, the pixmap will be scaled down to save RAM. Value should be between (0, 1). The "
                    "smaller the value, the larger the RAM usage but the better the image quality."
    )
    scale_up_trigger_ratio: float = Field(
        gt=1,
        default=1.1,
        description="Ratio for the scale up trigger. If the ratio between the displayed size and the pixmap size is "
                    "greater than this, the pixmap will be reloaded to be able to display the image properly. "
                    "Value should be > 1 the larger the value, the smaller the RAM usage but the lower the image "
                    "quality."
    )

    tile_page_preload_count: int = Field(
        ge=1,
        default=1,
        description="Any tile view has always an entire page of tiles above and below loaded (if possible). "
                    "This number can be increased for more snappy performance, but it will also increase the RAM usage."
    )

    tile_size_default: int = Field(
        gt=10,
        default=100,
        description="Default tile size in pixels. (Value is taken, if no preference is set.)"
    )

    tile_resize_timeout_ms: int = Field(
        gt=0,
        default=200,
        description="Timeout for tiles resize in milliseconds."
    )

    tile_animation: bool = Field(
        default=True,
        description="Enable tile animation when loading images."
    )

    tile_animation_duration_ms: int = Field(
        gt=50,
        default=200,
        description="Duration of tile movement animation in milliseconds."
    )

    tile_wrap_around_y: bool = Field(
        default=True,
        description="Wrap around the tile view when scrolling vertically. (If you go beyond the highest row, it starts "
                    "back at the bottom"
    )

    tile_wrap_around_x: bool = Field(
        default=True,
        description="Warp around the tile view when scrolling horizontally. Observe that if it wraps around right down "
                    "or right up is determined by the wrap around direction."
    )

    tile_wrap_around_x_down: bool = Field(
        default=True,
        description="Wrap around to the next line further down when going go the right. Only has an effect if "
    )