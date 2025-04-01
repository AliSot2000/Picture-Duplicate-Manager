from enum import Enum


class GUICommandTypes(Enum):
    NONE = 0
    QUIT = 1

class ProcessComType(Enum):
    MAX = 1
    CURRENT = 2
    MESSAGE = 3
    # EXIT may only be sent in the function that is started as a process!!!
    EXIT = 4


class MatchTypes(Enum):
    """
    Enum to indicate the type of match found in the database.
    """
    No_Match = 0
    Binary_Match_Images = 1
    Binary_Match_Trash = 2
    Hash_Match_Trash = 3
    Binary_Match_Replaced = 4
    Hash_Match_Replaced = 5


class GoogleFotosMetadataStatus(Enum):
    No_Metadata = -1
    Copied_Metadata = 0
    Original_Metadata = 1


class SourceTable(Enum):
    Images = 0
    Replaced = 1
    Import_Tables = 2
    Last_Import = 3
    Any_Import_Tabel = 4
    Thumbnails = 5


class Views(Enum):
    Deduplicate_Compare = 0
    Message_Label = 1
    Full_Screen_Image = 2
    Import_Tile_View = 3
    Import_Big_Screen_View = 4
    Database_Big_Screen_View = 5
    Database_Tile_View = 6
    Import_Tables_View = 7


class LongRunningActions(Enum):
    PrepareImport = 1
    Deduplicate_With_Database = 2
    Deduplicate_Without_Database = 3
    Import_Images = 4


class GroupingCriterion(Enum):
    NONE = 0
    YEAR = 1
    YEAR_MONTH = 2
    YEAR_MONTH_DAY = 3


class NewMatchTypes(Enum):
    """
    Enum to indicate the type of match found in the database.
    """
    NO_MATCH = 0
    BINARY_MATCH_MAIN = 1
    HASH_MATCH_MAIN = 2
    BINARY_MATCH_TRASH = 3
    HASH_MATCH_TRASH = 4
    BINARY_MATCH_DUPLICATES = 5
    HASH_MATCH_DUPLICATES = 6


class ImportTableGrouping(Enum):
    """
    The Import table groups files based on their association.
    """
    NO_MATCH = 0
    BINARY_MATCH_MAIN = 1
    HASH_MATCH_MAIN = 2
    BINARY_MATCH_TRASH = 3
    HASH_MATCH_TRASH = 4
    BINARY_MATCH_REPLACED = 5
    HASH_MATCH_REPLACED = 6
    IMPORTED = 7
    NOW_ALLOWED = 8


# INFO, no table, add method selection from table in gui. Makes backend handling a lot easier. (Don't have to
#  duplicate the selection code every time we need a selection)
class SelectionType(Enum):
    SELECTION_A = 0
    SELECTION_B = 1
    TIME_RANGE = 2


class MediaType(Enum):
    MAIN = 0
    DUPLICATE = 1
    TRASH = 2


class Allowed(Enum):
    NOT_ALLOWED_EXT = 0
    ALLOWED = 1
    NOT_ALLOWED_ERR = 2


class ImportStatus(Enum):
    IGNORE = 0
    MARKED = 1
    IMPORTED = 2
    DELETED = 3


class UpdateStatus(Enum):
    READY_TO_UPDATE=0
    UPDATED=1
    FAILED=2


class MainTileView(Enum):
    """
    List of all possible views for the main tile view.
    """
    MAIN = 0
    TRASH = 1
    DUPLICATE = 2
    VERIFY = 3
    SEL_A = 4
    SEL_B = 5