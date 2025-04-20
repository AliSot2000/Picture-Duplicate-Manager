from enum import Enum


class FastDiffPyViews(Enum):
    # Show the files you selected to deduplicate (A, B, Both) Checkboxes
    TILE = 1

    # Show the files with file metadata, image and carousel
    BIG_SCREEN = 2

    # Deduplicate view (shows the clusters) HASH, Diff, Both
    DEDUP = 3

    # Show a single image in full screen
    FULL_SCREEN_IMAGE = 4

    # Show the difference between two images.
    DELTA = 5

# INFO: Deal with Full screen by creating a new window
class DatabaseViews(Enum):
    # Main Tile View (with sel_a, sel_b, verify, trash, duplicates, db)
    MAIN_TILE = 1
    # Big screen with image, metadata and carousel
    MAIN_BIG_SCREEN = 2
    # Open parent with all of its children in a compare view (no fwd and back)
    MAIN_COMPARE = 3
    # Open an image which has to be from the duplicate table together with its parent.
    MAIN_PARENT = 4
    # Open the compare view that connects to the duplicates and known_duplicates table
    COMPARE = 5

    # Show tiles of files that are to be imported.
    IMPORT_TILE = 11
    # Show the image, carousel, metadata with option to open match in main table.
    IMPORT_BIG_SCREEN = 12

    # Open a tile view of all files that need to be relocated or need to have their location updated
    RELOCATE_TILE = 21
    # Open a given image, with carousel and metadata (has current location and location according to db).
    # No Parent.
    RELOCATE_BIG_SCREEN = 22

    # Open a tile view of all files whose hash has changed
    HASH_UPDATE_TILE = 31
    # Open a given image, with carousel and metadata (has current hash and hash according to db).
    HASH_UPDATE_BIG_SCREEN = 32

    # Open a tile view of all files who's name has changed
    NAME_UPDATE_TILE = 41
    # Open a given image, with carousel and metadata (has current name and name according to db).
    # Using Thumbnails if possible
    NAME_UPDATE_BIG_SCREEN = 42

    # Open a tile view of all files who's presence has changed
    PRESENCE_UPDATE_TILE = 51
    # Open a given image, with carousel and metadata (has the same metadata like MAIN_BIG_SCREEN with an extra field
    # now present or now missing)
    PRESENCE_UPDATE_BIG_SCREEN = 52


class FocusMoveY(Enum):
    NONE = 0
    # Move the focus up
    UP = 1
    # Move the focus down
    DOWN = 2


class FocusMoveX(Enum):
    NONE = 0
    # Move the focus left
    LEFT = 1
    # Move the focus right
    RIGHT = 2
    # Wrapping Movements
    LEFT_LIMIT = 3
    RIGHT_LIMIT = 4