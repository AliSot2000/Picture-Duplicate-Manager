from enum import Enum


class DateTimeCategory(str, Enum):
    NONE = "none"
    AWARE = "aware"
    UNAWARE = "unaware"
    DATE = "date"
    TIME = "time"
    TIMESTAMP = "timestamp"


class DateTimeSource(Enum):
    ANY_AWARE = 0
    FILE_AWARE = 1
    UNAWARE_GPS = 2
    UNAWARE_DEFAULT = 3
    DATE_OR_TIME = 4
    CUSTOM = 5
