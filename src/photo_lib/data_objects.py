from dataclasses import dataclass
from typing import Union
import datetime
from photo_lib.enum import *

"""
Dataclasses related to the backend of the phtoto library.
"""


@dataclass
class BaseTileInfo:
    key: int
    path: str

@dataclass
class TileInfo(BaseTileInfo):
    allowed: bool
    imported: bool
    match_type: MatchTypes

    mark_for_import: bool = False


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