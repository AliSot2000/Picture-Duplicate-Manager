import exiftool
import json
import datetime
import os
import hashlib
from dataclasses import dataclass
from .tagsnshit import known  # find


def anti_utc(dt_str: str, fmt_str: str):
    """
    Merge UTC into the datetime.
    :param dt_str:
    :param fmt_str:
    :return:
    """
    dt_obj = datetime.datetime.strptime(dt_str, fmt_str)
    unaware = datetime.datetime.strptime(dt_obj.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
    return unaware + dt_obj.utcoffset()


def hash_file(path):
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


@dataclass
class FileMetaData:
    org_fname: str
    org_fpath: str  # without the filename
    metadata: dict
    naming_tag: str  # which is a key in the metadata dict
    file_hash: str
    datetime_object: datetime.datetime
    verify: bool = False
    google_fotos_metadata: dict = None


def general_parser(dt_str: str, preferred: str = None, retry: bool = True):
    """

    patterns:
    ':: ::z'
    ':: :: z'
    '-- :: z'
    '-- ::z'
    '--T::z'
    ':: :z'
    ':: ::.f'
    ':: ::'
    ':: ::Z'
    '-- ::'
    '--T::'
    '-- :'
    ':: ::pm'


    :param dt_str:
    :param preferred: pattern string
    :param retry:
    :return:
    :raises ValueError if the String didn't match any patterns
    :raise ValueError if the Parsing failed.
    """

    # format YYYY:MM:DD HH:MM:SS+HH:MM
    # format YYYY:MM:DD HH:MM:SS+HHMM
    if preferred is None or preferred == ":: ::z":
        try:
            return anti_utc(dt_str, "%Y:%m:%d %H:%M:%S%z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY:MM:DD HH:MM:SS +HH:MM
    # format YYYY:MM:DD HH:MM:SS +HHMM
    if preferred is None or preferred == ":: :: z":
        try:
            return anti_utc(dt_str, "%Y:%m:%d %H:%M:%S %z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY-MM-DD HH:MM:SS +HH:MM
    # format YYYY-MM-DD HH:MM:SS +HHMM
    if preferred is None or preferred == "-- :: z":
        try:
            return anti_utc(dt_str, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY-MM-DD HH:MM:SS+HH:MM
    # format YYYY-MM-DD HH:MM:SS+HHMM
    if preferred is None or preferred == "-- ::z":
        try:
            return anti_utc(dt_str, "%Y-%m-%d %H:%M:%S%z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY-MM-DDTHH:MM:SS+HH:MM
    # format YYYY-MM-DDTHH:MM:SS+HHMM
    if preferred is None or preferred == "--T::z":
        try:
            return anti_utc(dt_str, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY:MM:DD HH:MM+HH:MM
    # format YYYY:MM:DD HH:MM+HHMM
    if preferred is None or preferred == ":: :z":
        try:
            return anti_utc(dt_str, "%Y:%m:%d %H:%M%z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY:MM:DD HH:MM:SS.ssssss
    if preferred is None or preferred == ":: ::.f":
        try:
            return datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S.%f")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

        # format YYYY:MM:DD HH:MM:SS.ssssss
    if preferred is None or preferred == ":: ::.fz":
        try:
            return anti_utc(dt_str, "%Y:%m:%d %H:%M:%S.%f%z")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY:MM:DD HH:MM:SS
    if preferred is None or preferred == ":: ::":
        try:
            return datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY:MM:DD HH:MM:SSZ
    if preferred is None or preferred == ":: ::Z":
        try:
            return datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%SZ")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY-MM-DD HH:MM:SS
    if preferred is None or preferred == "-- ::":
        try:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY-MM-DDTHH:MM:SS
    if preferred is None or preferred == "--T::":
        try:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    # format YYYY:MM:DD HH:MM
    if preferred is None or preferred == "-- :":
        try:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None

    if preferred is None or preferred == ":: ::pm":
        try:
            return datetime.datetime.strptime(dt_str, "%Y:%m:%d %I:%M:%S%p")
        except ValueError:
            if preferred is not None:
                if retry:
                    return general_parser(dt_str)
                return None
            # if preferred is none, just try the next parser and see if it works.

    if preferred is not None:
        # return None
        raise ValueError(f"No valid preferred string given {preferred}, see doc string")
    else:
        if dt_str == "0000:00:00 00:00:00":
            return None
        raise ValueError(f"No matching date time parsing string found for {dt_str}")


def func_wrapper(key: str, start_pattern: str = None, ):
    def new_func(metadata: dict):
        dt_str = metadata.get(key)

        if dt_str is None:
            return None, key

        return general_parser(dt_str, preferred=start_pattern), key

    return new_func


def double_key_wrapper(date_key: str, time_key: str, start_pattern: str = None):
    def new_func(metadata: dict):
        date_str = metadata.get(date_key)
        time_str = metadata.get(time_key)

        if date_str is None or time_str is None:
            return None, ""

        return general_parser(f"{date_str} {time_str}", preferred=start_pattern), date_key

    return new_func


key_lookup_dir = {
    "File:FileModifyDate": func_wrapper("File:FileModifyDate", ":: ::z"),
    "File:FileAccessDate": func_wrapper("File:FileAccessDate", ":: ::z"),
    "File:FileInodeChangeDate": func_wrapper("File:FileInodeChangeDate", ":: ::z"),
    "EXIF:ModifyDate": func_wrapper("EXIF:ModifyDate", ":: ::z"),
    "EXIF:DateTimeOriginal": func_wrapper("EXIF:DateTimeOriginal", ":: ::z"),
    "EXIF:CreateDate": func_wrapper("EXIF:CreateDate", ":: ::z"),
    "Composite:SubSecCreateDate": func_wrapper("Composite:SubSecCreateDate", ":: ::.f"),
    "Composite:SubSecDateTimeOriginal": func_wrapper("Composite:SubSecDateTimeOriginal", ":: ::.f"),
    "XMP:DateCreated": func_wrapper("XMP:DateCreated", ":: ::.f"),
    "Composite:SubSecModifyDate": func_wrapper("Composite:SubSecModifyDate", ":: ::.f"),
    "Composite:DateTimeCreated": func_wrapper("Composite:DateTimeCreated", ":: ::z"),
    "Composite:DigitalCreationDateTime": func_wrapper("Composite:DigitalCreationDateTime", ":: ::z"),
    "IPTC:DateCreated": double_key_wrapper("IPTC:DateCreated", "IPTC:TimeCreated", ":: ::z"),
    "IPTC:DigitalCreationDate": double_key_wrapper("IPTC:DigitalCreationDate", "IPTC:DigitalCreationTime", ":: ::z"),
    "IPTC:TimeCreated": double_key_wrapper("IPTC:DateCreated", "IPTC:TimeCreated", ":: ::z"),
    "IPTC:DigitalCreationTime": double_key_wrapper("IPTC:DigitalCreationDate", "IPTC:DigitalCreationTime", ":: ::z"),
    "XMP:DateTimeOriginal": func_wrapper("XMP:DateTimeOriginal", ":: :z"),
    "XMP:DateTimeDigitized": func_wrapper("XMP:DateTimeDigitized", ":: :z"),
    "PNG:CreationTime": func_wrapper("PNG:CreationTime", ":: ::z"),
    "QuickTime:CreateDate": func_wrapper("QuickTime:CreateDate", ":: ::z"),
    "QuickTime:ModifyDate": func_wrapper("QuickTime:ModifyDate", ":: ::z"),
    "QuickTime:TrackCreateDate": func_wrapper("QuickTime:TrackCreateDate", ":: ::z"),
    "QuickTime:TrackModifyDate": func_wrapper("QuickTime:TrackModifyDate", ":: ::z"),
    "QuickTime:MediaCreateDate": func_wrapper("QuickTime:MediaCreateDate", ":: ::z"),
    "QuickTime:MediaModifyDate": func_wrapper("QuickTime:MediaModifyDate", ":: ::z"),
    "QuickTime:ContentCreateDate": func_wrapper("QuickTime:ContentCreateDate", ":: ::z"),
    "PNG:ModifyDate": func_wrapper("PNG:ModifyDate", ":: ::z"),
    "PNG:Datecreate": func_wrapper("PNG:Datecreate", "--T::z"),
    "PNG:Datemodify": func_wrapper("PNG:Datemodify", "--T::z"),
    "QuickTime:CreationDate": func_wrapper("QuickTime:CreationDate", ":: ::z"),
    "QuickTime:ContentCreateDate-un": func_wrapper("QuickTime:ContentCreateDate-un", ":: ::z"),
    "QuickTime:CreationDate-deu-CH": func_wrapper("QuickTime:CreationDate-deu-CH", ":: ::z"),
    "QuickTime:AppleProappsIngestDateDescription-deu-CH": func_wrapper(
        "QuickTime:AppleProappsIngestDateDescription-deu-CH", ":: :: z"),
    "QuickTime:AppleProappsIngestDateDescription": func_wrapper("QuickTime:AppleProappsIngestDateDescription",
                                                                ":: :: z"),
    "QuickTime:ContentCreateDate-deu": func_wrapper("QuickTime:ContentCreateDate-deu", ":: ::z"),
    "XMP:Date": func_wrapper("XMP:Date", ":: ::pm"),
    "QuickTime:DateAcquired": func_wrapper("QuickTime:DateAcquired", ":: ::"),
    "QuickTime:DateTimeOriginal": func_wrapper("QuickTime:DateTimeOriginal", ":: ::Z")
}

wrapper_collection = [
    func_wrapper("File:FileModifyDate", ":: ::z"),
    func_wrapper("File:FileAccessDate", ":: ::z"),
    func_wrapper("File:FileInodeChangeDate", ":: ::z"),
    func_wrapper("EXIF:ModifyDate", ":: ::z"),
    func_wrapper("EXIF:DateTimeOriginal", ":: ::z"),
    func_wrapper("EXIF:CreateDate", ":: ::z"),
    func_wrapper("Composite:SubSecCreateDate", ":: ::.f"),
    func_wrapper("Composite:SubSecDateTimeOriginal", ":: ::.f"),
    func_wrapper("XMP:DateCreated", ":: ::.f"),
    func_wrapper("Composite:SubSecModifyDate", ":: ::.f"),
    func_wrapper("Composite:DateTimeCreated", ":: ::z"),
    func_wrapper("Composite:DigitalCreationDateTime", ":: ::z"),
    double_key_wrapper("IPTC:DateCreated", "IPTC:TimeCreated", ":: ::z"),
    double_key_wrapper("IPTC:DigitalCreationDate", "IPTC:DigitalCreationTime", ":: ::z"),
    func_wrapper("XMP:DateTimeOriginal", ":: :z"),
    func_wrapper("XMP:DateTimeDigitized", ":: :z"),
    func_wrapper("PNG:CreationTime", ":: ::z"),
    func_wrapper("QuickTime:CreateDate", ":: ::z"),
    func_wrapper("QuickTime:ModifyDate", ":: ::z"),
    func_wrapper("QuickTime:TrackCreateDate", ":: ::z"),
    func_wrapper("QuickTime:TrackModifyDate", ":: ::z"),
    func_wrapper("QuickTime:MediaCreateDate", ":: ::z"),
    func_wrapper("QuickTime:MediaModifyDate", ":: ::z"),
    func_wrapper("QuickTime:ContentCreateDate", ":: ::z"),
    func_wrapper("PNG:ModifyDate", ":: ::z"),
    func_wrapper("PNG:Datecreate", "--T::z"),
    func_wrapper("PNG:Datemodify", "--T::z"),
    func_wrapper("QuickTime:CreationDate", ":: ::z"),
    func_wrapper("QuickTime:ContentCreateDate-un", ":: ::z"),
    func_wrapper("QuickTime:CreationDate-deu-CH", ":: ::z"),
    func_wrapper("QuickTime:AppleProappsIngestDateDescription-deu-CH", ":: :: z"),
    func_wrapper("QuickTime:AppleProappsIngestDateDescription", ":: :: z"),
    func_wrapper("QuickTime:ContentCreateDate-deu", ":: ::z"),
    func_wrapper("XMP:Date", ":: ::pm"),
    func_wrapper("QuickTime:DateAcquired", ":: ::"),
    func_wrapper("QuickTime:DateTimeOriginal", ":: ::Z")
]


class MetadataAggregator:
    ethp: exiftool.ExifToolHelper
    det_new_ks: bool

    func_collection = wrapper_collection

    # add more methodology for parsing. class or function
    def __init__(self, exiftool_path: str = None, detect_new_keys: bool = False):
        self.ethp = exiftool.ExifToolHelper(executable=exiftool_path)
        self.det_new_ks = detect_new_keys

    def process_file(self, path: str) -> FileMetaData:
        f_hash = hash_file(path)

        content = None
        cur_date: datetime.datetime = None
        cur_tag: str = ""

        metadata = self.ethp.get_metadata(path)[0]
        not_known = False
        not_parsed = False

        keys = []

        # try to load google fotos metadata
        if os.path.exists(f"{path}.json"):
            with open(f"{path}.json", "r") as gfjf:
                content = json.load(gfjf)

        # if self.det_new_ks, search for new matadata keys
        if self.det_new_ks:
            for key in metadata.keys():
                if "XMP:DocumentAncestors" in key:
                    continue
                if key not in known:
                    # fix this issue
                    print(f"{key}: {metadata[key]}")
                    keys.append(key)
                    not_known = True

        # determine date and time picture was taken
        for f in self.func_collection:
            res, key = f(metadata)
            if res is not None:
                if cur_date is None:
                    cur_date = res
                    cur_tag = key

                elif res < cur_date:
                    cur_date = res
                    cur_tag = key

        # output unknown keys if they are found.
        if not_known or not_parsed:
            print(json.dumps(keys, indent="  "))
            print(json.dumps(metadata, indent="  "))
            if not_known and not not_parsed:
                exit(100)
            elif not not_known and not_parsed:
                exit(200)
            else:
                exit(300)

        verify = False
        if cur_tag[0:4] == "File":
            verify = True

        ret_obj = FileMetaData(org_fname=os.path.basename(path),
                               org_fpath=os.path.dirname(path),
                               metadata=metadata,
                               naming_tag=cur_tag,
                               file_hash=f_hash,
                               datetime_object=cur_date,
                               verify=verify,
                               google_fotos_metadata=content
                               )

        return ret_obj
