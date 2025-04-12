import datetime
from dataclasses import dataclass
from typing import Union, Optional, List

from photo_lib.custom_enum import *
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.flag_dataclasses import GenericTableFlags, MainFlags
from photo_lib.metadata_aggregator import DateTimeSource

"""
Dataclasses related to the backend of the photo library.
"""


@dataclass
class BaseTileInfo:
    key: int
    path: str

@dataclass
class ImportTileInfo(BaseTileInfo):
    allowed: bool
    imported: bool
    match_type: MatchTypes

    mark_for_import: bool = False


@dataclass
class LibraryTileInfo(BaseTileInfo):
    thumbnail_path: str


@dataclass
class Progress:
    type: ProcessComType
    value: Union[int, str]


@dataclass
class DatabaseEntry:
    key: int
    org_fname: str
    org_fpath: str
    metadata: dict
    google_fotos_metadata: dict
    naming_tag: str
    file_hash: str
    new_name: str
    datetime: datetime.datetime
    verify: int

# Not inheriting from the BaseEntry because the key is different and the paths and everything is not coherent.
@dataclass
class FullImportTableEntry:
    key: int
    org_fname: str
    org_fpath: str
    metadata: Union[None, dict]
    file_hash: Union[None, str]
    imported: bool
    allowed: bool
    message: Union[None, str]
    datetime: Union[None, datetime.datetime]
    naming_tag: Union[None, str]
    match: Union[int, None]
    match_type: Union[None, MatchTypes] = None
    import_key: Union[int, None] = None
    google_fotos_metadata: Union[dict, None] = None


@dataclass
class BaseEntry:
    key: int
    org_fname: str
    metadata: Union[None, dict]
    file_hash: str
    datetime: datetime.datetime
    original_google_metadata: GoogleFotosMetadataStatus
    google_fotos_metadata: Union[None, dict]


@dataclass
class FullDatabaseEntry(BaseEntry):
    org_fpath: str
    naming_tag: str
    new_name: str
    present: bool
    trashed: bool
    verify: bool
    # We're not adding the timestamp since it can be computed from the datetime object.

@dataclass
class FullReplacedEntry(BaseEntry):
    successor: Union[int, None]
    former_name: Union[str, None]

@dataclass
class ImportTableEntry:
    key: int
    root_path: str
    table_name: str
    table_desc: str


@dataclass
class GroupCount:
    count: int
    group_crit: GroupingCriterion
    start_date: Union[None, datetime.datetime]

@dataclass
class NewImportTableEntry:
    key: int
    root_path: str
    table_name: str
    table_desc: str
    flags: GenericTableFlags


class Selection:
    selection_type: SelectionType
    start: Optional[datetime.datetime] = None
    end: Optional[datetime.datetime] = None

    def __init__(self, selection_type: SelectionType,
                 start: Optional[datetime.datetime] = None,
                 end: Optional[datetime.datetime] = None,
                 duration: Optional[datetime.timedelta] = None):
        """
        Creates a selection object.
        """
        self.selection_type = selection_type

        if selection_type == SelectionType.SELECTION_A or selection_type == SelectionType.SELECTION_B:
            if start is not None or end is not None or duration is not None:
                raise ValueError("SELECTION_A and SELECTION_B don't need any other arguments.")

        elif selection_type == SelectionType.TIME_RANGE:
            if start is None:
                raise ValueError("TIME_RANGE selection requires a start datetime")

            if end is None and duration is None:
                raise ValueError("TIME_RANGE selection requires end or duration")
            elif end is not None and duration is not None:
                raise ValueError("TIME_RANGE selection requires end or duration not both")
            else:
                assert end is None or duration is None, "Unexpected state"

                if start.tzinfo is None:
                    raise TypeError("timezone aware start required")

                _end = start + duration if duration is not None else end
                if _end.tzinfo is None:
                    raise TypeError("timezone aware end required")

                self.start = start
                self.end = _end

        else:  # pragma: no cover
            raise ImplementationError("Unhandled Enum Case of SelectionType")


@dataclass
class MetadataRow:
    main_key: int
    original_dirname: str
    naming_tag: str
    datetime_source: DateTimeSource
    replaced: MediaType # can be  0, 1, 2

    db_local_dir: Optional[List[str]] = None
    gps_lat: Optional[float] = None
    gps_long: Optional[float] = None


@dataclass
class MainRow:
    key: int
    original_filename: str
    datetime: datetime.datetime
    db_name: str
    parent: int
    timezone: str
    flags: MainFlags

    metadata: Optional[str] = None
    google_metadata: Optional[str] = None


class MediaElement:
    key: int
    source_table: TargetViewTable
    target_import_table: Optional[str]

    def __init__(self, key: int, source_table: TargetViewTable, target_import_table: Optional[str] = None):
        """
        This object fully specifies the media element of the database we're operating on.

        If the source_table is IMPORT, a target_import_table must be provided.

        :param key: int Key in the targeted table
        :param source_table: source of the key (i.e. the table it is from)
        :param target_import_table: Target Import Table, needed when we have an IMPORT table
        """
        self.key = key
        self.source_table = source_table
        if source_table == TargetViewTable.IMPORT and target_import_table is None:
            raise ValueError("target_import_table table must be provided")

        self.target_import_table = target_import_table

    def __repr__(self):
        return (f"MediaElement(key={self.key}, "
                f"source_table={self.source_table}, target_import_table={self.target_import_table})")


class MediaPaths:
    element: MediaElement

    original_fp: Optional[str] = None
    thumbnail_fp: Optional[str] = None
    miniature_fp: Optional[str] = None

    parent: Optional[MediaElement] = None

    def __init__(self,
                 element: MediaElement,
                 original_fp: Optional[str] = None,
                 thumbnail_fp: Optional[str] = None,
                 miniature_fp: Optional[str] = None,
                 parent: Optional[MediaElement] = None):
        """
        Populate the data object and ensure correct population
        """
        if parent is not None:
            if element.source_table != TargetViewTable.MAIN:
                raise ValueError("Parent may only be provided with element from the MAIN table")

            if parent.source_table != TargetViewTable.MAIN:
                raise ValueError("Parent element must come from main table.")

        self.element = element

        self.original_fp = original_fp
        self.miniature_fp = miniature_fp
        self.thumbnail_fp = thumbnail_fp

        self.parent = parent

    def __repr__(self):
        return (f"MediaPaths(element={self.element}, "
                f"original_fp={self.original_fp}, "
                f"thumbnail_fp={self.thumbnail_fp}, "
                f"miniature_fp={self.miniature_fp}, "
                f"parent={self.parent})")