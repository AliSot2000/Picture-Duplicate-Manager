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

class Views:
    Deduplicate_Compare = 0
    Message_Label = 1
    Full_Screen_Image = 2
    Import_Tile_View = 3
    Import_Big_Screen_View = 4
    Database_Big_Screen_View = 5
    Database_Tile_View = 6
    Import_Tables_View = 7

class LongRunningActions:
    PrepareImport= 1
    Deduplicate_With_Database = 2
    Deduplicate_Without_Database = 3
    Import_Images = 4