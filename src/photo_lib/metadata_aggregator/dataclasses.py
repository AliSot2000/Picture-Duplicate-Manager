import datetime
from dataclasses import dataclass
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from photo_lib.metadata_aggregator.config import DoubleKey, GPSMultiKey
from photo_lib.metadata_aggregator.enums import DateTimeCategory, DateTimeSource


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
    file_size: int
    tz_name: Union[str, ZoneInfo]

    metadata: Optional[dict] = None
    google_photos_metadata: Optional[dict] = None
    gps_lat: Optional[float] = None
    gps_long: Optional[float] = None
    source: Optional[DateTimeSource] = None

