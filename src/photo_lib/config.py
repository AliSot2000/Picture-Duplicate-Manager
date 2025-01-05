import zoneinfo

from pydantic import BaseModel, Field, ConfigDict, AfterValidator
from typing import Union, List, Dict, Tuple, Annotated
from photo_lib.custom_enum import PathSuffix, DateTimeCategory

# TODO implement config
def validate_zone_str(arg: str) -> str:
    """
    Try to parse a ZoneInfo object and return the string again
    """
    _ = zoneinfo.ZoneInfo(arg)
    return arg



PydanticTZStr = Annotated[str,
                          AfterValidator(validate_zone_str)]


class Config(BaseModel):
    allowed_extensions: List[str]

    exiftool: Union[str, None]
    db_version: Union[str, None]

    trash: Union[str, None]
    thumbnail: Union[str, None]

    path_suffix: PathSuffix = PathSuffix.NONE

    add_safety_exif_tags: bool = True


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

    simple_keys: Dict[str, List[Tuple[int, DateTimeCategory]]] = \
        Field(...,
              description="Dictionary of key-value pairs. The key is the key in the metadata dict returned by the "
                          "exiftool and the list is all known variants of the datetime format that can be in that key.")

    prefix_keys: Dict[str, List[Tuple[int, DateTimeCategory]]] = \
        Field(...,
              description="Some Keys are available in multiple editions. Example: QuickTime:CreationDate shows up as "
                          "is but also as QuickTime:CreationDate-de QuickTime:CreationDate-fra and "
                          "QuickTime:CreationDate-un. To parse keys which share a common prefix, use this type.")

    double_keys: List[Tuple[List[str], List[Tuple[int, DateTimeCategory]]]] = \
        Field(...,
              description="Datetime values are stretched across two key.s Example: IPTC:DateCreated, IPTC:TimeCreated "
                          "The first element of the tuple contains the two keys in the Date Time [Offset]. There are "
                          "also instances of Keys which contain a valid datetime and have another key containing the "
                          "timezone. Example: EXIF:ModifyDate, EXIF:OffsetTime"
              )

    simple_unaware_known_tz: Dict[str, List[Tuple[int, DateTimeCategory, Union[str, None]]]] = \
        Field(...,
              description="Some simple keys contain a timezone unaware datetime but it is defined in the spec for this "
                          "key what timezone the key has (usually UTC)")

    double_unaware_known_tz: List[Tuple[List[str], List[Tuple[int, DateTimeCategory, Union[str, None]]]]] = \
        Field(...,
              description="Some double keys contain a timezone unaware datetime but it is defined in the spec for these"
                          "keys what timezone the keys has (usually UTC)")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

class InternalDateTimeParser(DateTimeParser):
    tz_timestamp: List[str] = Field(default_factory=lambda: ["Placeholder"])