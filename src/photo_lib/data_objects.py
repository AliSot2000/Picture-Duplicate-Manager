from dataclasses import dataclass
from typing import Union, Optional, List, Tuple
import datetime
from photo_lib.custom_enum import *
from photo_lib.config import DoubleKey, GPSMultiKey

"""
Dataclasses related to the backend of the phtoto library.
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
class DateTimeParsingResult:
    key: Union[str, DoubleKey, List[Union[str, int]]]
    dt: Union[datetime.datetime, None]
    src: DateTimeCategory


@dataclass
class GPSParsingResult:
    lat: float
    long: float

    key: Union[str, GPSMultiKey]

    alt: Optional[float] = None


@dataclass
class MetadataParsingResult:
    filename: str
    dirname: str
    creation_date: datetime.datetime
    naming_tag: str
    file_hash: str

    metadata: Optional[dict] = None
    google_photos_metadata: Optional[dict] = None
    gps_lat: Optional[float] = None
    gps_long: Optional[float] = None
    tz_name: Optional[str] = None
    source: Optional[str] = None


