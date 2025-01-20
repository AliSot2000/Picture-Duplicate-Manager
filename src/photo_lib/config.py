import zoneinfo
from typing import Union, List, Dict, Annotated, Optional

from pydantic import BaseModel, Field, ConfigDict, AfterValidator

from photo_lib.custom_enum import PathSuffix, DateTimeCategory
from photo_lib.db_definitions import Version


def validate_zone_str(arg: str) -> str:
    """
    Try to parse a ZoneInfo object and return the string again
    """
    _ = zoneinfo.ZoneInfo(arg)
    return arg


PydanticTZStr = Annotated[str, AfterValidator(validate_zone_str)]


class LookupSource(BaseModel):
    """
    Lookup Source in the provided formats.
    - Index used to get the right element of the format list
    - Source used to determine which format list to use
    """
    index: int = Field(...,
                       description="Index in the Lookup Table")
    source: DateTimeCategory = Field(...,
                                     description="Lookup Table to use.")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class StaticLookupSource(BaseModel):
    """
    Static Lookup for the keys which have a statically known timezone and this don't contain the timezone info
    within the key.

    - Formats contains the list of known formats for that key
    - tz static timezone of that key. Like US/Pacific. Default None is UTC
    """
    formats: List[LookupSource] = Field(...,
        description="List of Known Lookup Formats")
    tz: Union[str, None] = Field(None,
                                 description="Timezone String (like US/Pacific) or None for UTC")


class InternalStaticLookupSource(LookupSource):
    """
    Internal Lookup Source. The timezone now moved into the Lookup Source.
    """

    tz: Union[str, None] = Field(None,
                                 description="Timezone String (like US/Pacific) or None for UTC")


class DoubleKey(BaseModel):
    """
    Object containing two keys which form a datetime object.
    """
    first_key: str = Field(...,
                           description="First Key for the Double Key")
    second_key: str = Field(...,
                            description="Second Key for the Double Key")


class DoubleKeyFormat(DoubleKey):
    """
    Object also containing the list of known formats that a given double key has.
    """
    formats: List[LookupSource] = Field(...,
                                        description="List of Known Lookup Formats")


class DoubleKeyStatic(DoubleKeyFormat):
    """
    Double Key Lookup with a statically known timezone. This is the format used in the config. H
    as only a single timezone.
    """
    formats: StaticLookupSource = Field(...,
                                        description="List of Known Lookup Formats")


class GoogleFotoDatetime(BaseModel):
    """
    Google Fotos Metadata kdy
    """
    path: List[Union[str, int]]
    formats: List[LookupSource] = Field(...,
        description="Google Fotos Metadata")

    model_config = ConfigDict(
        populate_by_name=True
    )


class GPSMultiKey(BaseModel):
    lat_val: str = Field(...,
                         description="Latitude Value")
    lat_ref: Optional[str] = Field(None,
                        description="Latitude Indicator can be N or S (case insensitive)")
    long_val: str = Field(...,
                          description="Longitude Value")
    long_ref: Optional[str] = Field(None,
                         description="Longitude Indicator can be W or E (case insensitive)")
    alt_val: str = Field(...,
                        description="Altitude Value")
    alt_ref: Optional[str] = Field(None,
                         description="Altitute Reference can be 0 or 1, 1 iff above sea level ")

    model_config = ConfigDict(
        populate_by_name=True,
    )

class InternalDoubleKeyStatic(DoubleKeyFormat):
    """
    Double Key Lookup with a statically known timezone. This is the format used internally to allow for easy iteration.
    """
    formats: List[InternalStaticLookupSource] = Field(...,
                                                      description="List of Known Double Keys")


class DateTimeParser(BaseModel):
    """
    This Config Model contains all necessary information for the metadata aggregator to parse a usable datetime for the
    image
    """
    # Parsing Formats
    tz_aware_formats: List[str] = Field(...,
                                        description="List of Datetime Formats which are Timezone aware. "
                                                    "Rule of Thumb: They contain %z or %Z")

    tz_unaware_formats: List[str] = Field(...,
                                          description="List of Datetime Formats which are Timezone aware. "
                                                      "Conversely, they don't contain %z or %Z")

    tz_date_formats: List[str] = Field(...,
                                       description="List of Formats which contain only the date.")

    tz_time_formats: List[str] = Field(...,
                                       description="List of Formats which contain only the time.")

    simple_keys: Dict[str, List[LookupSource]] = \
        Field(...,
              description="Dictionary of key-value pairs. The key is the key in the metadata dict returned by the "
                          "exiftool and the list is all known variants of the datetime format that can be in that key.")

    prefix_keys: Dict[str, List[LookupSource]] = \
        Field(...,
              description="Some Keys are available in multiple editions. Example: QuickTime:CreationDate shows up as "
                          "is but also as QuickTime:CreationDate-de QuickTime:CreationDate-fra and "
                          "QuickTime:CreationDate-un. To parse keys which share a common prefix, use this type.")

    double_keys: List[DoubleKeyFormat] = \
        Field(...,
              description="Datetime values are stretched across two key.s Example: IPTC:DateCreated, IPTC:TimeCreated "
                          "The first element of the tuple contains the two keys in the Date Time [Offset]. There are "
                          "also instances of Keys which contain a valid datetime and have another key containing the "
                          "timezone. Example: EXIF:ModifyDate, EXIF:OffsetTime"
              )

    simple_unaware_known_tz: Dict[str, StaticLookupSource] = \
        Field(...,
              description="Some simple keys contain a timezone unaware datetime but it is defined in the spec for this "
                          "key what timezone the key has (usually UTC).")

    double_unaware_known_tz: List[DoubleKeyStatic] = \
        Field(...,
              description="Some double keys contain a timezone unaware datetime but it is defined in the spec for these"
                          "keys what timezone the keys has (usually UTC).")

    google_photos_datetime: List[GoogleFotoDatetime] = \
        Field(...,
              description="List of paths in the Google Fotos Metadata Dict.")

    gps_composite_key: List[str] = \
        Field(...,
              description="List of keys containing composited gps info. two or three floats lat, long, [alt] ")

    gps_multi_key: List[GPSMultiKey] = \
        Field(...,
              description="List of GPSMultiKey objects containing GPS info across multiple metadata fields.")

    gps_prefix_composite_key: List[str] = \
        Field(...,
              description="Each string indicates a prefix of a key, that if matched contains composite data: "
                          "lat, long, [alt]")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class InternalDateTimeParser(DateTimeParser):
    tz_timestamp: List[str] = Field(default_factory=lambda: ["Placeholder"])

    internal_simple_unaware_known_tz: Dict[str, List[InternalStaticLookupSource]] = \
        Field(...,
              description="Some simple keys contain a timezone unaware datetime but it is defined in the spec for this "
                          "key what timezone the key has (usually UTC). For ease of use, the timezone is copied into "
                          "each format. However, within a key, the timezone must be the same.")

    internal_double_unaware_known_tz: List[InternalDoubleKeyStatic] = \
        Field(...,
              description="Some double keys contain a timezone unaware datetime but it is defined in the spec for these"
                          "keys what timezone the keys has (usually UTC). For ease of use, the timezone is copied into "
                          "each format. However, within a key, the timezone must be the same.")


# https://pypi.org/project/platformdirs/
class Config(BaseModel):
    allowed_extensions: List[str]
    image_extensions: List[str]
    video_extensions: List[str]

    version: Version

    exiftool: Union[str, None] = None

    db_file: str
    trash: str
    thumbnail: str
    temp_path: str

    path_suffix: PathSuffix = PathSuffix.NONE

    add_safety_exif_tags: bool = True

    datetime_fmt: Union[DateTimeParser, None] = None
    fallback_tz: Union[str, None] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
