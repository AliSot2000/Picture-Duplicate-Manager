from pydantic import BaseModel, ConfigDict, Field


"""
Idea for this config - this is what you can modify from a settings pane
"""


class UIConfig(BaseModel):
    """
    Contains actually user configurable settings.
    """
    date_lookup_row_limit: int = Field(
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

    # TODO replace that with the one from the api
    thumbnail_size: int = 100
    miniature_size: int = 500