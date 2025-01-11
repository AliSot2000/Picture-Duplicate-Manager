import datetime
import json
import logging
import multiprocessing as mp
import os
import zoneinfo
from typing import List, Union, Tuple, Optional, Dict, Any

import hashlib
import exiftool
import timezonefinder

from photo_lib.config import (InternalDateTimeParser, DateTimeParser, LookupSource, InternalStaticLookupSource,
                              DoubleKey, DoubleKeyFormat, InternalDoubleKeyStatic, Config, GoogleFotoDatetime)
from photo_lib.custom_enum import DateTimeCategory, DateTimeSource
from photo_lib.data_objects import DateTimeParsingResult, GPSParsingResult


# https://docs.python.org/3/howto/logging.html#logging-flow
# Flags, TZinfo, GPS + Datetime, Datetime NO TZ,  File TZ only,
class NewMetadataAggregator:
    eth: exiftool.ExifToolHelper
    tzf: timezonefinder.TimezoneFinder = timezonefinder.TimezoneFinder()
    dt_cfg: InternalDateTimeParser
    new_dt_cfg: Optional[InternalDateTimeParser] = None

    # Handling priority of where to get the utc offset from.
    default_tz: str
    tz_priority: List[DateTimeSource]

    # Set of keys to ignore when attempting to find new keys containing datetime information
    ignore_keys: List[str] = ["ICC_Profile:ProfileDateTime"]
    search_keys: List[str] = ["date", "time", "stamp"]
    found_keys: Dict[str, Any] = {}

    # Attempt to mew formats for existing keys
    discover: bool

    # Try to parse any key that contains any of the search_keys strings and which isn't contained in the igonre_keys
    search: bool

    # print status information about parsing
    __verbose: bool

    # Logger
    logger: logging.Logger = None
    index: Optional[int] = None
    logging_queue: mp.Queue

    # ==================================================================================================================
    # Util
    # ==================================================================================================================

    @property
    def verbose(self):
        return self.__verbose

    @verbose.setter
    def verbose(self, value):
        if value == self.__verbose:
            return

        self.__verbose = value
        if self.logger is None:
            return

        level = logging.DEBUG if self.__verbose else logging.INFO
        self.logger.setLevel(level)

    @staticmethod
    def build_internal_config(cfg: DateTimeParser) -> InternalDateTimeParser:
        """
        Ensure that all items in the config for unaware timezone have the same timezone within a given key.
        """
        internal_simple_unaware_known_tz = {}
        for key, fmts in cfg.simple_unaware_known_tz.items():
            format_list, tz = fmts.formats, fmts.tz
            new_fmts = [InternalStaticLookupSource(index=f.index, source=f.source, tz=tz) for f in format_list]
            internal_simple_unaware_known_tz[key] = new_fmts

        internal_double_unaware_known_tz = []
        for db_key_static in cfg.double_unaware_known_tz:
            format_list, tz = db_key_static.formats.formats, db_key_static.formats.tz
            new_fmts = [InternalStaticLookupSource(index=f.index, source=f.source, tz=tz) for f in format_list]
            internal_double_unaware_known_tz.append(InternalDoubleKeyStatic(first_key=db_key_static.first_key,
                                                                            second_key=db_key_static.second_key,
                                                                            formats=new_fmts))

        existing_json = cfg.model_dump()
        existing_json["internal_simple_unaware_known_tz"] = internal_simple_unaware_known_tz
        existing_json["internal_double_unaware_known_tz"] = internal_double_unaware_known_tz

        return InternalDateTimeParser.model_validate(existing_json)

    def export_discovered(self, tgt_path: str, config: Config):
        """
        Export the newly found things to config.
        """
        ...

    # ==================================================================================================================
    # General
    # ==================================================================================================================

    def __init__(self,
                 logger: logging.Logger,
                 path: str = None,
                 discover: bool = False,
                 search: bool = False,
                 verbose: bool = False,
                 ignore_keys: List[str] = None,
                 search_keys: List[str] = None,
                 default_tz: str = None,
                 tz_priority: List[DateTimeSource] = None):
        """
        Path to exiftool executable. Used as an override.
        """
        # loading the exiftool
        self.eth = exiftool.ExifToolHelper(executable=path)

        # Get the known formats from the config
        cfg_p = os.path.join(os.path.dirname(__file__), "datetime_fmt.json")
        if not os.path.exists(cfg_p):
            raise FileNotFoundError("Dependent config missing. Add the datetime_fmt.json again or create it from the "
                                    "human readable version.")

        with open(cfg_p, "r") as f:
            content = f.read()
        parser_config = DateTimeParser.model_validate_json(content)
        self.dt_cfg = self.build_internal_config(parser_config)

        # Setting values from args
        self.discover = discover
        self.__verbose = verbose
        self.search = search

        # Logging attrs
        self.logger = logger

        if default_tz is None:
            self.default_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()

        if tz_priority is not None:
            no_dup = set(tz_priority)

            if len(no_dup) != len(tz_priority):
                raise ValueError("Duplicate Key in Time Zone Priority")

            if len(no_dup) < len(DateTimeSource._member_names_):
                raise ValueError("Not Sources present, you must order all priorities first.")

            # INFO: Cannot use set, lose order.
            self.tz_priority = tz_priority

        else:
            self.tz_priority = [DateTimeSource.ANY_AWARE,
                                DateTimeSource.UNAWARE_GPS,
                                DateTimeSource.GOOGLE_PHOTOS_AWARE,
                                DateTimeSource.UNAWARE_DEFAULT,
                                DateTimeSource.GOOGLE_PHOTOS_UNAWARE,
                                DateTimeSource.DATE_OR_TIME,
                                DateTimeSource.FILE_AWARE]


        if ignore_keys is not None:
            self.ignore_keys = ignore_keys

        if search_keys is not None:
            self.search_keys = search_keys

        if self.discover or self.search:
            # We're clearing out the keys to be able to fill them later on.
            self.new_dt_cfg = InternalDateTimeParser.model_validate_json(self.dt_cfg.model_dump_json())
            self.new_dt_cfg.simple_keys = {}
            self.new_dt_cfg.double_keys = []
            self.new_dt_cfg.prefix_keys = {}
            self.new_dt_cfg.simple_unaware_known_tz = {}
            self.new_dt_cfg.double_unaware_known_tz = []
            self.new_dt_cfg.internal_simple_unaware_known_tz = {}
            self.new_dt_cfg.internal_double_unaware_known_tz = []

            # Not even strictly necessary
            self.new_dt_cfg.gps_multi_key = []
            self.new_dt_cfg.gps_composite_key = []
            self.new_dt_cfg.gps_prefix_composite_key = []

            # Clear google photos metadata keys
            self.new_dt_cfg.google_photos_datetime = []

    # ==================================================================================================================
    # Base Functions Datetime Parsing and Utility
    # ==================================================================================================================

    def _dt_parser(self, dt: str, fmt: int, source: DateTimeCategory) \
            -> Tuple[Union[datetime.datetime, None], DateTimeCategory]:
        """
        Parser to get the file creation time.

        Parser will:
        - get the format lookup from the dt_cfg object
        - use the fmt as the index in the lookup list
        - parse the datetime string against the format in the lookup.

        :param dt: Datetime String to Parse
        :param fmt: Index in the Format Lookup Tables
        :param source: Kind of Datetime we want to parse (May not be DateTimeCategory.NONE)

        :return: Tuple[Union[datetime.datetime, None], DateTimeCategory]
        In case of a timestamp, since unix time is tz aware, it'll return an AWARE not a TIMESTAMP
        """
        if source == DateTimeCategory.AWARE:
            lookup = self.dt_cfg.tz_aware_formats
        elif source == DateTimeCategory.UNAWARE:
            lookup = self.dt_cfg.tz_unaware_formats
        elif source == DateTimeCategory.DATE:
            lookup = self.dt_cfg.tz_date_formats
        elif source == DateTimeCategory.TIME:
            lookup = self.dt_cfg.tz_time_formats
        elif source == DateTimeCategory.TIMESTAMP:
            lookup = self.dt_cfg.tz_timestamp
        elif source == DateTimeCategory.NONE:
            raise ValueError("DateTimeCategory is used to indicate no valid format was found. Not a valid source.")
        else:
            raise ValueError(f"Unmatched Category: {source}")

        fmt_str = lookup[fmt]

        try:
            # We're not parsing a time stamp so use the strptime method for strings
            if source != DateTimeCategory.TIMESTAMP:
                return datetime.datetime.strptime(dt, fmt_str), source
            else:
                return datetime.datetime.fromtimestamp(float(dt)), DateTimeCategory.AWARE
        except ValueError:
            return None, DateTimeCategory.NONE

    def _coercing_dt_parser(self, dt: str, fmt: int, source: DateTimeCategory, tz: Union[str, None]) \
            -> Tuple[Union[datetime.datetime, None], DateTimeCategory]:
        """
        Same as _tz_parser, except will replace the timezone parsed with the one from the tz argument.

        :param dt: Datetime String to Parse
        :param fmt: Index in the Format Lookup Tables
        :param source: Kind of Datetime we want to parse (May not be DateTimeCategory.NONE)
        :parm tz: Timezone to parse, if None, defaults to UTC
        """
        dto, fmt = self._dt_parser(dt, fmt, source)

        # Parsing failed.
        if dto is None:
            return dto, fmt

        # Parsing successful, exchange the zone info.
        zone = zoneinfo.ZoneInfo(tz) if tz is not None else datetime.timezone.utc
        return dto.replace(tzinfo=zone), DateTimeCategory.AWARE

    def _dt_test_all(self, dt: Union[str, int], key: str) -> \
            Tuple[Union[datetime.datetime, None], DateTimeCategory, int]:
        """
        Test all found formats and check if they match

        :param dt: Datetime String to possibly find a matching format for.
        :param key: Needed for logging, writing which key has now new format or no format was found.

        :return: Tuple[Union[datetime.datetime, None], DateTimeCategory, int]
        If format was found successfully: datetime.datetime, DateTimeCategory, index
        IF format was not found, None, DateTimeCategory.NONE, -1
        """
        if isinstance(dt, int):
            try:
                r = datetime.datetime.fromtimestamp(float(dt))
                self.logger.debug(f"Found {dt} at in key {key} as timestamp")
                return r, DateTimeCategory.TIMESTAMP, 0
            except ValueError:
                pass
            return None, DateTimeCategory.NONE, -1

        # Build list of all sources.
        task_list = [
            (self.dt_cfg.tz_aware_formats, DateTimeCategory.AWARE),
            (self.dt_cfg.tz_unaware_formats, DateTimeCategory.UNAWARE),
            (self.dt_cfg.tz_time_formats, DateTimeCategory.TIME),
            (self.dt_cfg.tz_date_formats, DateTimeCategory.DATE)
        ]

        for fmt_list, source in task_list:
            for fmt in fmt_list:
                try:
                    # Attempt to parse format
                    res = datetime.datetime.strptime(dt, fmt)

                    # Get index for result and write information
                    fmt_idx = fmt_list.index(fmt)
                    self.logger.debug(f"Found: {dt} at in key: {key} with format index: {fmt_idx}, "
                                      f"DateTimeSource: {source.value}")
                    return res, source, fmt_idx
                except ValueError:
                    continue

        self.logger.debug(f"Didn't find valid format for key: {key} and datetime {dt}")
        return None, DateTimeCategory.NONE, -1

    @staticmethod
    def mal_formatted_parser(dt: Union[str, int]) -> bool:
        """
        Known mal formatted data detector. Prior to parsing, check if the string or int matches a known bad format

        :param dt: Datetime String to Parse
        :return: True if mal formatted data detected
        """
        if isinstance(dt, int):
            return False

        if dt == "0000:00:00 00:00:00":
            return True

        # if dt == "0000:01:01 00:00:00+00:00":
        #     return True

        if dt == "":
            return True

        # if dt == ':  :     :  :':
        #     return True
        #
        # try:
        #     if int(dt[17]) > 5:
        #         return True
        # except ValueError:
        #     pass
        # except IndexError:
        #     pass

        try:
            rmdt = dt[:10] + dt[11:]
            datetime.datetime.strptime(rmdt, "%Y:%m:%d %H:%M:%S.%f%z")
            return True
        except ValueError:
            pass

        try:
            rmdt = dt[:10] + dt[11:]
            datetime.datetime.strptime(rmdt, "%Y:%m:%d %H:%M:%S.%f")
            return True
        except ValueError:
            pass

        return False

    def _parse_raw_value(self, dt: Union[str, int, None],
                         formats: List[LookupSource] = None,
                         formats_dt: List[InternalStaticLookupSource] = None) \
        -> Union[None, List[Tuple[datetime.datetime, DateTimeCategory]]]:
        """
        Parse and sanitize the raw value and return a list of all valid parsed datetime objects.

        :param dt: Datetime String to Parse
        :param formats: List of tuples of (int, DateTimeCategory)

        :return: List of tuples of (int, DateTimeCategory) or return None if it's a known bad format.
        """
        if dt is None:
            return None

        if formats is not None and formats_dt is not None:
            raise ValueError("Provide either formats or formats_dt")
        elif formats_dt is None and formats is None:
            raise ValueError("Provide either formats or formats_dt")

        # Remove unnecessary stuff
        if isinstance(dt, str):
            dt = dt.strip()

        # Skip if we have mal-formatted data
        if self.mal_formatted_parser(dt):
            return None

        local_res = []
        if formats is not None:
            local_res = [self._dt_parser(dt, f.index, f.source) for f in formats]
        elif formats_dt is not None:
            local_res = [self._coercing_dt_parser(dt, f.index, f.source, f.tz) for f in formats_dt]

        return list(filter(lambda r: r[0] is not None, local_res))

    def build_key_union_simple_key(self,
                                   cur_dict: Dict[str, List[LookupSource]],
                                   new_dict: Dict[str, List[LookupSource]],
                                   ) -> Dict[str, List[Union[LookupSource, InternalStaticLookupSource]]]:
        """
        Build the union of the keys and formats from the dt_cfg and new_dt_cfg for the simple_key parsers.
        """
        if self.discover:
            # Build union of keys. We need to perform the union like this because we might have added keys with search mode
            uk = list(set(list(cur_dict.keys()) + list(new_dict.keys())))

            # Build the union of the formats
            simple_union = {}
            for key in uk:
                la = cur_dict.get(key) if cur_dict.get(key) is not None else []
                lb = new_dict.get(key) if new_dict.get(key) is not None else []

                simple_union[key] = la + lb

        else:
            simple_union = cur_dict

        return simple_union

    def build_key_union_double_key(self,
                                   cur_list: List[Union[DoubleKeyFormat, InternalDoubleKeyStatic]],
                                   new_list: List[Union[DoubleKeyFormat, InternalDoubleKeyStatic]]) \
            -> Tuple[List[DoubleKey], List[List[Union[LookupSource, InternalStaticLookupSource]]], List[DoubleKey]]:
        """
        Build the union of the two lookup tables and add lookup tables for key and format.

        :param cur_list: List of currently known double keys
        :param new_list: List of newly discovered double keys

        :return: Tuple of three Lists,
        Union of all keys (new and current),
        Union of all formats (new and current)
        List of New Keys (used for adding newly discovered formats)
        """
        # Build union of formats from dt_cfg and new_dt_cfg
        if self.discover:
            dt_keys = [DoubleKey.model_validate(l.model_dump()) for l in cur_list]
            dt_fmts = [l.formats for l in cur_list]

            new_dt_keys = [DoubleKey.model_validate(l.model_dump()) for l in new_list]
            new_dt_fmts = [l.formats for l in new_list]

            uk = []
            for double_key in dt_keys + new_dt_keys:
                if double_key not in uk:
                    uk.append(double_key)
            ufmt = [[] for _ in uk]

            # Setting the format and  key lookup lists
            for i in range(len(uk)):
                key = uk[i]
                la = dt_fmts[dt_keys.index(key)] if key in dt_keys else []
                lb = new_dt_fmts[new_dt_keys.index(key)] if key in new_dt_keys else []

                ufmt[i] = la + lb

        # use only dt_cfg because no discover
        else:
            uk = [DoubleKey.model_validate(l.model_dump()) for l in cur_list]
            ufmt = [l.formats for l in cur_list]

            # Needs to be defined for no issues with code inspection
            new_dt_keys = []

        return uk, ufmt, new_dt_keys

    @staticmethod
    def build_datetime_from_date_and_time(date: datetime.datetime, time: datetime.datetime) -> datetime.datetime:
        """
        Populate datetime object from date and time.

        :param date: datetime object to take the date from
        :param time: datetime object to take the time from

        :return: datetime object with joint values from date and time
        """
        return datetime.datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=time.hour,
            minute=time.minute,
            second=time.second,
            tzinfo=time.tzinfo,
        )

    @staticmethod
    def partition_datetime_results(dts: List[DateTimeParsingResult], gpr: List[DateTimeParsingResult] = None) -> Tuple[
        List[DateTimeParsingResult],
        List[DateTimeParsingResult],
        List[DateTimeParsingResult],
        List[DateTimeParsingResult],
        List[DateTimeParsingResult],
        List[DateTimeParsingResult],
        List[DateTimeParsingResult],
    ]:
        """
        Partition the Datetime parsing result into lists according to the DateTimeSource

        :param dts: List of DateTimeParsingResult objects to partition
        :param gpr: List of DateTimeParsingResult objects from google_photos to partition

        :return: five lists of DateTimeParsingResult objects, in the following order:
        - aware objects
        - unaware objects
        - date objects
        - time objects
        - file objects
        - google photos aware objects
        - google photos unaware objects
        """
        aware = []
        unaware = []
        date = []
        time = []
        file = []
        google_photos_aware = []
        google_photos_unaware = []

        # Partition the Datetime into separate lists
        for dtr in dts:
            assert dtr.src not in (DateTimeCategory.NONE, DateTimeCategory.TIMESTAMP), \
                f"Unsupported Result from parsing datetime {dtr.src}"

            if isinstance(dtr.key, str) and dtr.key.lower().startswith("file"):
                file.append(dtr)
            elif dtr.src == DateTimeCategory.AWARE:
                aware.append(dtr)
            elif dtr.src == DateTimeCategory.DATE:
                date.append(dtr)
            elif dtr.src == DateTimeCategory.TIME:
                time.append(dtr)
            elif dtr.src == DateTimeCategory.UNAWARE:
                unaware.append(dtr)
            else:
                raise Exception(f"Tertiem Non Datur. This option shouldn't be possible. {dtr.src}")

        if gpr is not None:
            for dtr in gpr:
                if dtr.src == DateTimeCategory.AWARE:
                    google_photos_aware.append(dtr)
                    google_photos_unaware.append(dtr)

        # Sort all the list of datetimes
        unaware = sorted(unaware, key=lambda x: x.dt)
        aware = sorted(aware, key=lambda x: x.dt)
        date = sorted(date, key=lambda x: x.dt)
        time = sorted(time, key=lambda x: x.dt)
        file = sorted(file, key=lambda x: x.dt)
        google_photos_aware = sorted(google_photos_aware, key=lambda x: x.dt)
        google_photos_unaware = sorted(google_photos_unaware, key=lambda x: x.dt)

        return unaware, aware, date, time, file, google_photos_aware, google_photos_unaware

    # ==================================================================================================================
    # Parse Functions
    # ==================================================================================================================

    def search_possible_new_keys(self):
        """
        Go through available metadata keys and search for keys which aren't already covered by the config. Only Simple Keys are
        """
        ...

    def metadata_to_datetime(self, md: dict, google_photos_result: List[DateTimeParsingResult] = None) -> Tuple[
        DateTimeParsingResult,
        DateTimeSource,
        Union[None, GPSParsingResult]
    ]:
        """
        Fully parse all datetime objects of the image. Also attempt to parse all GPS information.

        Precedence of Timezone:
        - Timezone Aware Datetime formats
        - Timezone unaware Format + GPS
        - Config Default Timezone
        - System Timezone

        :param md: Dictionary of metadata
        :param google_photos_result: List of DateTimeParsingResult objects
        """
        dts = []
        dts.extend(self.simple_key_parser(md))
        dts.extend(self.double_key_parse(md))
        dts.extend(self.simple_prefix_key_parser(md))
        dts.extend(self.simple_unaware_static_tz_parser(md))
        dts.extend(self.double_unaware_static_tz_parser(md))

        gps_rst = []
        gps_rst.extend(self.gps_composite_parser(md))
        gps_rst.extend(self.gps_prefix_composite_parser(md))
        gps_rst.extend(self.gps_multikey_parser(md))

        # For debugging purposes, we're checking the zones are all equal
        if __debug__:
            zones = []
            for res in gps_rst:
                zones.append(self.tzf.timezone_at(lat=res.lat, lng=res.long))

            for z in range(1, len(zones)):
                assert zones[z] == zones[z - 1]

        aware, unaware, date, time, file, google_photo_aware, google_photo_unaware = \
            self.partition_datetime_results(dts, google_photos_result)

        for prio in self.tz_priority:
            # Any aware, return the first key from the aware
            if prio == DateTimeSource.ANY_AWARE:
                # PRECONDITION: At least one element is aware
                if len(aware) > 0:
                    return aware[0], DateTimeSource.ANY_AWARE, None

            # Use unaware but add zone info from gps
            elif prio == DateTimeSource.UNAWARE_GPS:
                if len(unaware) > 0 and len(gps_rst) > 0:
                    # PRECONDITION: At least one unaware element is present and at least one gps element is present
                    # Parse the GPS Data
                    zones = []
                    valid_gps_results = []
                    for res in gps_rst:
                        r = self.tzf.timezone_at(lat=res.lat, lng=res.long)
                        if r is not None:
                            zones.append(r)
                            valid_gps_results.append(res)

                    # Check with the point was a timezone associated
                    if len(zones) == 0:
                        continue
                    tz = zoneinfo.ZoneInfo(zones[0])
                    new_dt = unaware[0].dt.replace(tzinfo=tz)
                    dt_pr = DateTimeParsingResult(key=unaware[0].key, dt=new_dt, src=unaware[0].src)
                    return dt_pr, DateTimeSource.UNAWARE_GPS, valid_gps_results[0]

            # Using Default Timezone from
            elif prio == DateTimeSource.UNAWARE_DEFAULT:
                if len(unaware) > 0:
                    # PRECONDITION: At least one unaware element is present
                    # We're using the default attribute for the timezone
                    new_dt = unaware[0].dt.replace(tzinfo=zoneinfo.ZoneInfo(self.default_tz))
                    dt_pr = DateTimeParsingResult(key=unaware[0].key, dt=new_dt, src=unaware[0].src)

                    return dt_pr, DateTimeSource.UNAWARE_DEFAULT, None

            # Using datetime from File Metadata
            elif prio == DateTimeSource.FILE_AWARE:
                if len(file) > 0:
                    # PRECONDITION: At least one file element is present
                    return file[0], DateTimeSource.FILE_AWARE, None
                else:
                    raise ValueError("There should always be file metadata")

            # Only partial results found
            elif prio == DateTimeSource.DATE_OR_TIME:
                # We have a date and a time, so we're combining them into a datetime, using the default timezone.
                if len(date) > 0 and len(time) > 0:
                    # PRECONDITION: At least one date and at least one time element is present
                    new_dt = self.build_datetime_from_date_and_time(date=date[0].dt, time=time[0].dt)
                    key = DoubleKey(first_key=date[0].key, second_key=time[0].key)
                    src = DateTimeCategory.AWARE if new_dt.tzinfo is not None else DateTimeCategory.UNAWARE

                # We only have a non-file date, joining this info with the file info
                elif len(date) > 0 and len(time) == 0:
                    # PRECONDITION: At least one date element is present
                    new_dt = self.build_datetime_from_date_and_time(date=date[0].dt, time=file[0].dt)
                    key = date[0].key
                    src = DateTimeCategory.DATE

                # We only have a non-file time, joining this info with the file info
                elif len(date) == 0 and len(time) > 0:
                    # PRECONDITION: At least one time element is present
                    new_dt = self.build_datetime_from_date_and_time(date=file[0].dt, time=time[0].dt)
                    key = time[0].key
                    src = DateTimeCategory.TIME
                else:
                    # Neither time nor date element present, ignore
                    continue

                # Adding default timezone if not provided
                if new_dt.tzinfo is None:
                    new_dt = new_dt.replace(tzinfo=zoneinfo.ZoneInfo(self.default_tz))

                res = DateTimeParsingResult(key=key, dt=new_dt, src=src), DateTimeSource.DATE_OR_TIME, None
                return res

            # Using Google Photos from aware
            elif prio == DateTimeSource.GOOGLE_PHOTOS_AWARE:
                if len(google_photo_aware) > 0:
                    return google_photo_aware[0], DateTimeSource.GOOGLE_PHOTOS_AWARE, None

            # Using Google Photos which aren't aware.
            elif prio == DateTimeSource.GOOGLE_PHOTOS_UNAWARE:
                if len(google_photo_unaware) > 0:
                    assert False, "Google Photos Unaware encountered!"
                    dt_new = google_photo_unaware[0].dt.replace(tzinfo=zoneinfo.ZoneInfo(self.default_tz))
                    prs = DateTimeParsingResult(key=google_photo_unaware[0].key,
                                                dt=dt_new,
                                                src=google_photo_unaware[0].src)
                    return prs, DateTimeSource.GOOGLE_PHOTOS_UNAWARE, None

            else:
                raise ValueError("Tertiem Non Datur")

        raise ValueError("Shouldn't be able to get here.")

    def simple_key_parser(self, md: dict) -> List[DateTimeParsingResult]:
        """
        Go through all simple keys of the config:

        - Check if they exist
        - Check if it is known bad format.
        - Parse with known formats
        - IF discover attribute is set and no known format matches, attempt to parse with all formats from the config.
        - If a new format is found, it will be stored in the new_dt_cfg.

        :param md: Metadata to parse
        :return: Tuple of (datetime, DateTimeCategory). If no valid format is found, return None
        """
        simple_union = self.build_key_union_simple_key(
            cur_dict=self.dt_cfg.simple_keys,
            new_dict=self.new_dt_cfg.simple_keys if self.new_dt_cfg is not None else {}
        )

        # Try to parse all keys from the given metadata
        results = []
        for key, fmt in simple_union.items():

            # Parse the content of the key
            valid_res = self._parse_raw_value(md.get(key), fmt)
            if valid_res is None:
                continue

            # No valid format found and attempt to find new formats.
            if len(valid_res) == 0 and self.discover:
                dt, dts, idx = self._dt_test_all(dt=md.get(key), key=key)

                # Successfully found a new format
                if dt is not None:
                    results.append(DateTimeParsingResult(key=key, dt=dt, src=dts))

                    if self.new_dt_cfg.simple_keys.get(key) is None:
                        self.new_dt_cfg.simple_keys[key] = []

                    # Add the newly discovered format to the simple key lookup with the index and the source.
                    self.new_dt_cfg.simple_keys[key].append(LookupSource(index=idx, source=dts))

            # Add valid result to the overall results.
            elif len(valid_res) > 0:
                assert len(valid_res) == 1, f"Found multiple valid formats for key {key}: {md.get(key)}"
                results.append(DateTimeParsingResult(key=key, dt=valid_res[0][0], src=valid_res[0][1]))

            else:
                self.logger.debug(f"No valid format found for key {key}: {md.get(key)}")

        return results

    def double_key_parse(self, md: dict) -> List[DateTimeParsingResult]:
        """
        Go through all double keys of the config:

        - Check if they exist
        - Check if it is known bad format.
        - Parse with known formats
        - IF discover attribute is set and no known format matches, attempt to parse with all formats from the config.
        - If a new format is found, it will be stored in the new_dt_cfg.

        :param md: Metadata to parse
        :return: Tuple of (datetime, DateTimeCategory). If no valid format is found, return None
        """
        uk, ufmt, new_dt_keys = self.build_key_union_double_key(
            cur_list=self.dt_cfg.double_keys,
            new_list=self.new_dt_cfg.double_keys if self.new_dt_cfg is not None else []
        )

        results = []
        for keys, formats in zip(uk, ufmt):
            dt_a = md.get(keys.first_key)
            dt_b = md.get(keys.second_key)

            # Keys need to be defined
            if dt_a is None or dt_b is None:
                continue

            # Build datetime string
            dt = dt_a + " " + dt_b

            valid_res = self._parse_raw_value(dt=dt, formats=formats)
            if valid_res is None:
                continue

            # Discover new formats for given double key
            if len(valid_res) == 0 and self.discover:
                dt, dts, idx = self._dt_test_all(dt=dt_a, key=f"{keys.first_key} + {keys.second_key}")
                if dt is not None:
                    results.append(DateTimeParsingResult(key=keys, dt=dt, src=dts))

                    if keys in new_dt_keys:
                        # The key exists, so we add the new format to it
                        self.new_dt_cfg.double_keys[new_dt_keys.index(keys)].formats.append(
                            LookupSource(index=idx, source=dts)
                        )
                    else:
                        # The key doesn't exist, so we add the key and the new format to the list
                        # INFO: Since we're looking at each key for the given metadata once, we don't have to worry
                        #  about updating the new_dt_keys or new_dt_formats.
                        self.new_dt_cfg.double_keys.append(
                            DoubleKeyFormat(first_key=keys.first_key,
                                            second_key=keys.second_key,
                                            formats=[LookupSource(index=idx, source=dts)]))

            elif len(valid_res) > 0:
                assert len(valid_res) == 1, (f"Found multiple valid formats for keys "
                                             f"{keys.first_key} + {keys.second_key}: {dt}")
                results.append(DateTimeParsingResult(key=keys, dt=valid_res[0][0], src=valid_res[0][1]))

            else:
                self.logger.debug(f"No valid format found for key {keys.first_key} + {keys.second_key}: {dt}")

        return results

    def simple_prefix_key_parser(self, md: dict) -> List[DateTimeParsingResult]:
        """
        Go through all prefix key of the config:

        - Search all keys if they match the prefix.
        - Check if the value is a known format.
        - Parse with known formats
        - If Discover attribute is set and no known format matches, attempt to parse with all formats from the config.
        - If a new format is found, it will be stored in the new_dt_cfg.

        :param md: Metadata to parse
        :return: Tuple of (datetime, DateTimeCategory). If no valid format is found, return None
        """
        simple_union = self.build_key_union_simple_key(
            cur_dict=self.dt_cfg.prefix_keys,
            new_dict=self.new_dt_cfg.prefix_keys if self.new_dt_cfg is not None else {}
        )

        results = []
        for prefix, formats in simple_union.items():
            # Build the list of all possible keys for a given prefix
            for key in md.keys():
                if not key.startswith(prefix):
                    continue

                # Parse the content of the key
                valid_res = self._parse_raw_value(dt=md.get(key), formats=formats)
                if valid_res is None:
                    continue

                # Perform discovery operation and associated updates
                if len(valid_res) == 0 and self.discover:
                    dt, dts, idx = self._dt_test_all(dt=md.get(key), key=key)
                    if dt is not None:
                        results.append(DateTimeParsingResult(key=key, dt=dt, src=dts))

                        if self.new_dt_cfg.prefix_keys.get(key) is None:
                            self.new_dt_cfg.prefix_keys[key] = []

                        # Add the new format to the prefix key in the config
                        self.new_dt_cfg.simple_keys[key].append(LookupSource(index=idx, source=dts))

                        # Also add the format to the simple unions. and the formats we're currently looking at.
                        simple_union[key].append(LookupSource(index=idx, source=dts))
                        formats.append(LookupSource(index=idx, source=dts))

                elif len(valid_res) > 0:
                    assert len(valid_res) == 1, f"Found multiple valid formats for key {key}, {md.get(key)}"
                    results.append(DateTimeParsingResult(key=key, dt=valid_res[0][0], src=valid_res[0][1]))

                else:
                    self.logger.debug(f"No valid format found for key {key}, {md.get(key)}")

        return results

    def simple_unaware_static_tz_parser(self, md: dict) -> List[DateTimeParsingResult]:
        """
        Parse simple keys which don't have a timezone in the value but whose timezone is defined in the standard of the
        key. E.G. GPS-DateTime is always in UTC but doesn't come with the Z at the end.

        - Search all keys if they match the prefix.
        - Check if the value is a known format.
        - Parse with known formats
        - Add timezone from config
        - IF discover attribute is set and no known format matches, attempt to parse with all formats from the config.
        - If a new format is found, it will be stored in the new_dt_cfg.

        :param md: Metadata to parse
        :return: Tuple of (datetime, DateTimeCategory). If no valid format is found, return None
        """
        simple_union = self.build_key_union_simple_key(
            cur_dict=self.dt_cfg.internal_simple_unaware_known_tz,
            new_dict=self.new_dt_cfg.internal_simple_unaware_known_tz if self.new_dt_cfg is not None else {}
        )

        results = []
        for key, formats in simple_union.items():
            # Parse the content of the key
            valid_res = self._parse_raw_value(dt=md.get(key), formats_dt=formats)
            if valid_res is None:
                continue

            if len(valid_res) == 0 and self.discover:
                dt, dts, idx = self._dt_test_all(md.get(key), key=key)

                if dt is not None:
                    zone = zoneinfo.ZoneInfo(formats[0].tz) if formats[0].tz is not None else datetime.timezone.utc
                    dt = dt.replace(tzinfo=zone)
                    results.append(DateTimeParsingResult(key=key, dt=dt, src=DateTimeCategory.AWARE))

                    if self.new_dt_cfg.internal_simple_unaware_known_tz.get(key) is None:
                        self.new_dt_cfg.internal_simple_unaware_known_tz[key] = []

                    self.new_dt_cfg.internal_simple_unaware_known_tz[key].append(
                        InternalStaticLookupSource(index=idx,
                                                   source=dts,
                                                   tz=formats[0].tz)
                    )
            elif len(valid_res) > 0:
                assert len(valid_res) == 1, f"Found multiple valid formats for key {key}, {md.get(key)}"
                results.append(DateTimeParsingResult(key=key, dt=valid_res[0][0], src=DateTimeCategory.AWARE))

            else:
                self.logger.debug(f"No valid format found for key {key}, {md.get(key)} (static)")

        return results

    def double_unaware_static_tz_parser(self, md: dict) -> List[DateTimeParsingResult]:
        """
        Parse double keys which don't have a timezone in the value but whose timezone is defined in the standard of the
        key. E.G. EXIF:GPSDateStamp, EXIF:GPSTimeStamp

        - Search all keys if they match the prefix.
        - Check if the value is a known format.
        - Parse with known formats
        - Add timezone from config
        - IF discover attribute is set and no known format matches, attempt to parse with all formats from the config.
        - If a new format is found, it will be stored in the new_dt_cfg.

        :param md: Metadata to parse
        :return: Tuple of (datetime, DateTimeCategory). If no valid format is found, return None
        """
        uk, ufmt, new_dt_keys = self.build_key_union_double_key(
            cur_list=self.dt_cfg.internal_double_unaware_known_tz,
            new_list=self.new_dt_cfg.internal_double_unaware_known_tz if self.new_dt_cfg is not None else [],
        )

        results = []
        for keys, formats in zip(uk, ufmt):
            dt_a = md.get(keys.first_key)
            dt_b = md.get(keys.second_key)

            if not (dt_a is not None and dt_b is not None):
                continue

            dt = dt_a + " " + dt_b

            valid_res = self._parse_raw_value(dt=dt, formats_dt=formats)
            if valid_res is None:
                continue

            if len(valid_res) == 0 and self.discover:
                dt, dts, idx = self._dt_test_all(dt=dt, key=f"{keys.first_key} + {keys.second_key}")

                if dt is not None:
                    zone = zoneinfo.ZoneInfo(formats[0].tz) if formats[0].tz is not None else datetime.timezone.utc
                    dt = dt.replace(tzinfo=zone)
                    results.append(DateTimeParsingResult(key=keys, dt=dt, src=DateTimeCategory.AWARE))

                    if keys in new_dt_keys:
                        self.new_dt_cfg.internal_double_unaware_known_tz[new_dt_keys.index(keys)].formats.append(
                            InternalStaticLookupSource(index=idx,
                                                       source=dts,
                                                       tz=formats[0].tz)

                        )

                    else:
                        self.new_dt_cfg.internal_double_unaware_known_tz.append(
                            InternalDoubleKeyStatic(
                                first_key=keys.first_key,
                                second_key=keys.second_key,
                                formats=[InternalStaticLookupSource(index=idx,
                                                                    source=dts,
                                                                    tz=formats[0].tz)]

                            ))
            elif len(valid_res) > 0:
                assert len(valid_res) == 1, (f"Found multiple valid formats for keys "
                                             f"{keys.first_key} + {keys.second_key}: {dt}")
                results.append(DateTimeParsingResult(key=keys, dt=valid_res[0][0], src=DateTimeCategory.AWARE))
            else:
                self.logger.debug(f"No valid format found for key {keys.first_key} + {keys.second_key}: {dt} (static")

        return results

    # ==================================================================================================================
    # GPS Parsers
    # ==================================================================================================================

    def _parse_gps_split(self, gps_str: str, key: str, sep: str = None) -> Union[GPSParsingResult, None]:
        """
        Parse Split Result into lat, long, [alt].

        :param gps_str: String to split. Order is assumed to be lat, long, alt
        :param key: Key, that got the value
        :parm sep: Separator to use between keys. Defaults to ' ' <- space

        :return: GPSParsingResult if parsing successful, else None
        """
        sep = " " if sep is None else sep
        split = gps_str.split(sep)
        if len(split) < 2:
            self.logger.warning(f"GPS Composite Tag with insufficient elements found."
                                f" Key: {key}, Value: {gps_str}")
            return None

        elif len(split) == 2:
            lat, long = split
            alt = None

        elif len(split) == 3:
            lat, long, alt = split

        else:
            self.logger.warning(f"GPS Composite Tag with too many elements found."
                                f" Key: {key}, Value: {gps_str}")
            return None

        # Attempt to parse the floats
        try:
            lat = float(lat)
        except ValueError:
            self.logger.error(f"Failed to Parse Latitude from GPS Composite Tag. "
                              f"Key: {key}, Value: {gps_str}")
            return None

        try:
            long = float(long)
        except ValueError:
            self.logger.error(f"Failed to Parse Longitude from GPS Composite Tag. "
                              f"Key: {key}, Value: {gps_str}")
            return None

        try:
            alt = float(alt) if alt is not None else None
        except ValueError:
            self.logger.error(f"Failed to Parse Altitude from GPS Composite Tag. "
                              f"Key: {key}, Value: {gps_str}")
            return None

        return GPSParsingResult(lat=lat, long=long, key=key, alt=alt)

    # INFO: Maybe the separator needs to be parametrized as well.
    def gps_composite_parser(self, md: dict) -> List[GPSParsingResult]:
        """
        Parse GPS Composite Keys. i.e. a key with lat, long, [alt].
        Values separated by spaces.
        """
        results = []
        for composite_key in self.dt_cfg.gps_composite_key:
            gps_value = md.get(composite_key)

            # Check we're having actually something
            if gps_value is None:
                continue

            local_res = self._parse_gps_split(gps_str=gps_value, key=composite_key)
            if local_res is not None:
                results.append(local_res)

        return results

    # INFO: Maybe the separator needs to be parametrized as well.
    def gps_prefix_composite_parser(self, md: dict) -> List[GPSParsingResult]:
        """
        Parse Prefix GPS Composite Keys. i.e. a key with lat, long, [alt]. and for which the key starts with a known
        prefix. E.G. prefix: 'QuickTime:GPSCoordinates' parses 'QuickTime:GPSCoordinates-deu-CH', ...

        Values separated by spaces.
        """
        results = []
        for gps_pf_k in self.dt_cfg.gps_prefix_composite_key:
            for key, value in md.items():
                if not key.startswith(gps_pf_k):
                    continue

                if value is None:
                    continue

                local_res = self._parse_gps_split(gps_str=value, key=key)
                if local_res is not None:
                    results.append(local_res)

        return results

    def gps_multikey_parser(self, md: dict) -> List[GPSParsingResult]:
        """
        Parse Multikey GPS Data.

        :param md: Metadata
        :return: list of GPSParsingResults
        """
        results = []
        for multikey in self.dt_cfg.gps_multi_key:
            lat_val = md.get(multikey.lat_val) if md.get(multikey.lat_val) is not None else None
            long_val = md.get(multikey.long_val) if md.get(multikey.long_val) is not None else None
            alt_val = md.get(multikey.alt_val) if md.get(multikey.alt_val) is not None else None

            lat_ref = md.get(multikey.lat_ref) if multikey.lat_ref is not None else None
            long_ref = md.get(multikey.long_ref) if multikey.long_ref is not None else None
            alt_ref = md.get(multikey.alt_ref) if multikey.alt_ref is not None else None

            # Not all necessary values present
            if lat_val is None or long_val is None:
                continue

            try:
                lat = float(lat_val)
            except ValueError:
                self.logger.error(f"Failed to Parse Latitude from GPS Multikey Tag. "
                                  f"Key: {multikey.lat_val}, Value: {lat_val}")
                continue

            try:
                long = float(long_val)
            except ValueError:
                self.logger.error(f"Failed to Parse Longitude from GPS Multikey Tag. "
                                  f"Key: {multikey.long_val}, Value: {long_val}")
                continue

            if lat_ref is not None:
                if lat_ref.lower().strip() not in ("n", "s"):
                    self.logger.warning(f"Failed to Parse Latitude Reference."
                                        f" Key: {multikey.lat_val}, Value: {lat_ref}")

                if lat_ref.lower().strip() == "s" and lat > 0:
                    self.logger.warning(f"Positive Latitude Value for South Latitude. Inverting Latitude."
                                        f" Key: {multikey.lat_val}, Value: {lat_ref}")
                    lat = -lat

            if long_ref is not None:
                if long_ref.lower().strip() not in ("e", "w"):
                    self.logger.warning(f"Failed to Parse Longitude Reference."
                                        f" Key: {multikey.long_val}, Value: {long_ref}")

                if long_ref.lower().strip() == "w" and long > 0:
                    self.logger.warning(f"Positive Longitude Value for West Longitude. Inverting Longitude."
                                        f" Key: {multikey.long_val}, Value: {long_ref}")
                    long = -long

            alt = None
            if alt_val is not None:
                try:
                    alt = float(alt_val)
                except ValueError:
                    self.logger.error(f"Failed to Parse Altitude from GPS Multikey Tag. "
                                      f" Key: {multikey.alt_val}, Value: {alt_val}")

                # Attempt to parse alt ref
                if alt is not None and alt_ref is not None:
                    if type(alt_ref) is str:
                        if alt_ref.lower().strip() not in ("0", "1"):
                            self.logger.warning(f"Unexpected Alt Ref Format: "
                                                f" Key: {multikey.alt_val}, Value: {alt_ref}")
                            palt_ref = None
                        else:
                            palt_ref = int(alt_ref)

                    elif type(alt_ref) is float or type(alt_ref) is int:
                        if not (alt_ref == 0 or alt_ref == 1):
                            self.logger.warning(f"Unexpected Alt Ref Format: "
                                                f" Key: {multikey.alt_val}, Value: {alt_ref}")
                            palt_ref = None
                        else:
                            palt_ref = alt_ref
                    else:
                        self.logger.warning(f"Unexpected Alt Ref Type: "
                                            f" Key: {multikey.alt_val}, Value: {alt_ref}")
                        palt_ref = None

                    # PRECONDITION: Because of the previous try except block it holds that alt is a float if it is not None
                    if palt_ref is not None and palt_ref == 1 and alt > 0:
                        self.logger.warning(f"Positive Altitude Value for below sea level (0). Inverting Altitude. "
                                            f"Key: {multikey.alt_val}, Value: {alt}")
                        alt = -alt

            results.append(GPSParsingResult(key=multikey, lat=lat, long=long, alt=alt))
        return results

    # ==================================================================================================================
    # File Utils
    # ==================================================================================================================

    @staticmethod
    def hash_file(path: str) -> str:
        """
        Hashes a file with sha256
        :param path: file_path to hash
        :return:
        """
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
            result = sha256_hash.hexdigest()
        return result

    def load_google_metadata(self, path: str) -> Union[dict, None]:
        """
        Load the metadata available from google photos.

        :param path: file_path to load metadata from
        """
        metadata_path = os.path.splitext(path)[0] + ".json"

        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    return metadata
            except json.decoder.JSONDecodeError:
                self.logger.error(f"Failed to Parse Google Photos Metadata. ")

        return None

    # ==================================================================================================================
    # Google Photos Metadata Parser
    # ==================================================================================================================

    def parse_google_photos_metadata(self, md: dict) -> List[DateTimeParsingResult]:
        """
        Parse the Datetime info from the Google Photos Metadata and return DateTimeResults

        :param md: Google Photos Metadata
        """
        results = []
        dt_keys = self.dt_cfg.google_photos_datetime + self.new_dt_cfg.google_photos_datetime

        for src in dt_keys:
            # Walk along the path to get to the final key
            outer_continue = False
            res = md
            for p in src.path:
                if isinstance(res, dict):
                    res = res.get(p)
                elif isinstance(res, list):
                    assert isinstance(p, int), "List Index needs to be an int"
                    try:
                        res = res[p]
                    except IndexError:
                        res = None

                elif res is None:
                    outer_continue = True
                    break
                else:
                    self.logger.warning(f"Failed to Parse Google Photos Metadata. ")
                    self.logger.debug(f"Path: {src.path} couldn't resolve in {json.dumps(md)}")

            # No result found, continue
            if outer_continue or res is None:
                continue

            # Check type of result
            assert isinstance(res, str) or isinstance(res, int), "String or Int for datetime or timestamp"
            dtr = self._parse_raw_value(dt=res, formats=src.formats)

            # Handle mal format and aborts
            if dtr is None:
                continue

            if len(dtr) == 0 and self.discover:
                dt, dts, idx = self._dt_test_all(dt=res, key=", ".join(src.path))

                # Found a new format
                if dt is not None:
                    results.append(DateTimeParsingResult(key=src.path, dt=dt, src=dts))

                    tgt_idx = -1
                    for i in range(len(self.new_dt_cfg.google_fotos_metadata)):
                        elm = self.new_dt_cfg.google_fotos_metadata[i]
                        if elm.path == src.path:
                            tgt_idx = i
                            break

                    if tgt_idx != -1:
                        self.new_dt_cfg.google_fotos_metadata[tgt_idx].formats.append(LookupSource(index=idx, source=dts))
                    else:
                        self.new_dt_cfg.google_fotos_metadata.append(
                            GoogleFotoDatetime(path=src.path, formats=[LookupSource(index=idx, source=dts)])
                        )

            elif len(dtr) > 0:
                assert len(dtr) == 1, f"Found multiple valid formats for key {src.path}: {res}"
                results.append(DateTimeParsingResult(key=src.path, dt=dtr[0][0], src=dtr[0][1]))

            else:
                self.logger.debug(f"No valid format found for key {src.path}: {res}")

        return results


if __name__ == "__main__":
    mda = NewMetadataAggregator(logging.getLogger("MetadataAggregator"))