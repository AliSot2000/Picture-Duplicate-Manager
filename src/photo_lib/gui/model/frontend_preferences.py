from typing import Optional

from pydantic import BaseModel


"""
Contains the last states the user left things in. E.g. for the session. Only provides the user with the clear cache
"""


class UIUserPreferences(BaseModel):
    """
    Contains shorthands (basically things the way the user left them so they are picked up correctly again.
    """
    # Preferences for Tiles.
    tile_size_main_main: Optional[int] = None
    tile_size_main_trash: Optional[int] = None
    tile_size_main_duplicates: Optional[int] = None
    tile_size_main_sel_a: Optional[int] = None
    tile_size_main_sel_b: Optional[int] = None
    tile_size_main_verify: Optional[int] = None

    tile_size_import: Optional[int] = None

    tile_size_relocate: Optional[int] = None

    tie_size_hash: Optional[int] = None

    tile_size_name: Optional[int] = None

    tile_size_presence : Optional[int] = None