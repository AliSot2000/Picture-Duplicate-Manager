from typing import Union, List

from pydantic import BaseModel, ConfigDict

from photo_lib.db_definitions import Version
from photo_lib.metadata_aggregator.config import DateTimeParser


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

    org_filename_append: bool = True
    thumbnail_target: int
    miniature_target: int

    add_safety_exif_tags: bool = True

    datetime_fmt: Union[DateTimeParser, None] = None
    fallback_tz: Union[str, None] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
