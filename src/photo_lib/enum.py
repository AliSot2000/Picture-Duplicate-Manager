from enum import Enum


class GUICommandTypes(Enum):
    NONE = 0
    QUIT = 1

class ProcessComType(Enum):
    MAX = 1
    CURRENT = 2
    MESSAGE = 3


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