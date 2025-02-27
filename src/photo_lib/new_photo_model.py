import datetime
import filecmp
import logging
import os.path
import shutil
import sys
from typing import Set, Dict, List, Union, Tuple, Optional
from zoneinfo import ZoneInfo

import cv2
import ffmpeg

import photo_lib.defaults as defaults
from photo_lib.cache import Cache, nd
from photo_lib.config import Config
from photo_lib.custom_enum import GroupingCriterion, NewMatchTypes, SelectionType, MediaType, Allowed, ImportStatus, \
    NameUpdateStatus
from photo_lib.data_objects import Selection
from photo_lib.db_definitions import current_version
from photo_lib.errors_and_warnings import ImplementationError, CorruptDatabase
from photo_lib.flag_dataclasses import MainFlags
from photo_lib.metadata_aggregator.config import DoubleKey
from photo_lib.metadata_aggregator.enums import DateTimeSource
from photo_lib.metadata_aggregator.new_metadata_aggregator import NewMetadataAggregator
from photo_lib.new_photo_db import PhotoDB


# https://docs.darktable.org/usermanual/development/en/overview/sidecar-files/sidecar-import/
# TODO: Rework Loggers, Integrity Logger needs to be present on
class PhotoModel:
    root_path: str

    config: Config
    db: PhotoDB

    # Redefining logger as mandatory
    main_logger_name: str = "PhotoDB"
    file_system_logger_name: str = "PhotoDB.FileSystem"
    metadata_aggregator_logger_name: str = "PhotoDB.MetadataAggregator"
    metadata_aggregator_parsing_logger_name: str = "PhotoDB.MetadataAggregator.Parsing"

    main_logger: logging.Logger
    file_system_logger: logging.Logger

    mda_logger: logging.Logger
    mda_parsing_logger: logging.Logger

    # Flags
    prune_fs_dir: bool = False
    opt_integrity_check: bool

    __mda: Optional[NewMetadataAggregator] = None
    __is_default_mda: bool = True

    # Caches
    filename_to_key_cache: Cache
    key_to_filepath_cache: Cache

    @property
    def current_version(self):
        return current_version.current_version

    def __init__(self,
                 root_path: str,
                 init: bool = False,
                 config: Config = None,
                 init_loggers: bool = True,
                 opt_integrity_check: bool = False):
        """
        Construct a Database Object from a preexisting database file.

        Database Initialization:

        - For initialization, you can provide the db with a custom config
        - Both the config and the db_file mustn't exist.

        :param root_path: Root path of the database
        :param init: If true, initialize the database.
        :param config: Override the default config during initialization. Ignored otherwise
        :param init_loggers: If true, initialize the loggers. Otherwise, Loggers must be defined externally.
        :param opt_integrity_check: Every time full file paths are computed and flags are present. Flags consistency
            with file system are checked.
        """
        self.main_logger = logging.getLogger(self.main_logger_name)
        self.file_system_logger = logging.getLogger(self.file_system_logger_name)
        self.mda_logger = logging.getLogger(self.metadata_aggregator_logger_name)
        self.mda_parsing_logger = logging.getLogger(self.metadata_aggregator_parsing_logger_name)

        if init_loggers:
            self.set_logging_defaults()

        self.filename_to_key_cache = Cache(size=1024)
        self.key_to_filepath_cache = Cache(size=1024)

        self.root_path = os.path.abspath(root_path)
        self.opt_integrity_check = opt_integrity_check

        cfg_path = defaults.config_path(self.root_path)

        # Prepping Config
        if not init:
            if not os.path.exists(os.path.abspath(cfg_path)):
                raise FileNotFoundError("Config File Not Found")

            # Set the config
            with open(os.path.abspath(cfg_path), "r") as f:
                self.config = Config.model_validate_json(f.read())

            if self.config.version != self.current_version:
                raise ValueError(f"Incompatible Version. "
                                 f"Expected: {self.current_version.major}.{self.current_version.minor}."
                                 f"{self.current_version.patch},"
                                 f"Got: {self.config.version.major}.{self.config.version.minor}.{self.config.version.patch}")

        else:
            # Create default config if not provided
            if config is None:
                config = self.build_default_config()

            if not os.path.exists(self.root_path):
                self.main_logger.info("Create Root Path")
                os.makedirs(self.root_path)

            # Checking existence of config path
            if os.path.exists(os.path.abspath(cfg_path)):
                raise FileExistsError("Config File Exists")

            # Checking existence of db file
            if os.path.exists(self.get_db_file_path(config)):
                raise FileExistsError("Database File Exists")

            with open(os.path.abspath(cfg_path), "w") as f:
                f.write(config.model_dump_json())

            self.config = config

        assert hasattr(self, "config") and self.config is not None, "Config must be populated by now"

        self.db = PhotoDB(db_path=self.get_db_file_path(),
                          root_path=self.root_path,
                          config=self.config,
                          init=init,
                          verify=True,
                          init_loggers=False)

        self.add_default_metadata_aggregator()

        self.check_create_default_dirs()
        # TODO empty presence, hash and name table.

    def reload_loggers(self):
        """
        Get the loggers from the class attributes

        attr: main_logger_name for main_logger
        attr: integrity_logger_name for integrity_logger
        """
        self.main_logger = logging.getLogger(self.main_logger_name)
        self.file_system_logger = logging.getLogger(self.file_system_logger_name)
        self.mda_logger = logging.getLogger(self.metadata_aggregator_logger_name)
        self.mda_parsing_logger = logging.getLogger(self.metadata_aggregator_parsing_logger_name)

    def set_logging_defaults(self):
        """
        Set Defaults of loggers.
        """
        # Level
        self.main_logger.setLevel(logging.DEBUG)
        self.file_system_logger.setLevel(logging.DEBUG)
        self.mda_logger.setLevel(logging.DEBUG)
        self.mda_parsing_logger.setLevel(logging.DEBUG)

        # Get Other DB's logger
        _photo_db_logger = logging.getLogger(PhotoDB.db_logger_name)
        _photo_db_integrity_logger = logging.getLogger(PhotoDB.integrity_logger_name)
        _photo_db_rare_occurrence_logger = logging.getLogger(PhotoDB.rare_occurrence_logger_name)

        # Set levels
        _photo_db_logger.setLevel(logging.DEBUG)
        _photo_db_integrity_logger.setLevel(logging.DEBUG)
        _photo_db_rare_occurrence_logger.setLevel(logging.DEBUG)

        # Set the propagate flags.
        _photo_db_logger.propagate = True
        _photo_db_integrity_logger.propagate = True
        _photo_db_rare_occurrence_logger.propagate = True

        # Propagate
        self.main_logger.propagate = False
        self.file_system_logger.propagate = True
        self.mda_logger.propagate = True
        self.mda_parsing_logger.propagate = True

        # Define handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        self.main_logger.addHandler(handler)

    def cleanup(self, fast: bool = False):
        """
        Besides writing to file, perform some checks and pruning operations
        """
        if self.prune_fs_dir and not fast:
            self.prune_filesystem_directories()

        self.db.cleanup(fast)

    def check_create_default_dirs(self):
        """
        Create default directories needed for the db.
        """
        if not os.path.exists(self.db.get_trash_dir()):
            self.main_logger.info(f"Created Trash Directory")
            os.makedirs(self.db.get_trash_dir())

        if not os.path.exists(self.db.get_thumb_dir()):
            self.main_logger.info(f"Created Thumbnail Directory")
            os.makedirs(self.db.get_thumb_dir())

        if not os.path.exists(self.db.get_temp_dir()):
            self.main_logger.info(f"Created Temp Directory")
            os.makedirs(self.db.get_temp_dir())

    # ==================================================================================================================
    # Metadata Aggregator calls
    # ==================================================================================================================

    @property
    def mda(self):
        return self.__mda

    @mda.setter
    def mda(self, value: NewMetadataAggregator):
        if value is None:
            self.__mda = None
            self.__is_default_mda = True

        else:
            self.__mda = value
            self.__is_default_mda = False

    def add_default_metadata_aggregator(self):
        """
        Add a default metadata aggregator (user could provide a custom MDA if he so chooses)
        """
        if self.__mda is None:
            self.__mda = NewMetadataAggregator(
                logger=logging.getLogger("MetadataAggregator"),
                discover_logger=logging.getLogger("MetadataAggregator.Parsing"),
                use_dateutil=True,
                datetime_fmt=self.config.datetime_fmt
            )
            self.__is_default_mda = True

    def _add_update_exif_tag(self, key: int, target_datetime: datetime.datetime, file_path: str):
        """
        Add the exif tag that the database uses to the file.

        PRECONDITION:

        - file_path exists
        - target_datetime different from current datetime
        - target_datetime is timezone aware.

        :param key: Key in main table of file to update or set the  exif-tag for
        :param target_datetime: New datetime to set
        """
        # Add the tag
        self.mda.eth.set_tags(files=[file_path], tags=self.exif_tag_creator(target_datetime))

        # Get Size of File and new File Hash
        new_hash = self.mda.hash_file(file_path)
        new_size = os.stat(file_path).st_size
        assert new_size is not None, "New Size needed for update."
        self.db.check_add_file_hash(file_key=key, file_hash=new_hash, file_size=new_size, initial=False)

    # ==================================================================================================================
    # Config
    # ==================================================================================================================

    @staticmethod
    def build_default_config() -> Config:
        """
        Create a new config with only defaults.
        """
        return Config(
            version=current_version.current_version,
            image_extensions=defaults.image_extensions,
            video_extensions=defaults.video_extensions,
            allowed_extensions=defaults.extensions,
            temp_path=defaults.temp_path,
            thumbnail=defaults.thumbnails_path,
            trash=defaults.trash_path,
            db_file=defaults.db_file,
            thumbnail_target=defaults.thumbnail_size,
            miniature_target=defaults.miniature_size,
        )

    # ==================================================================================================================
    # Importing and Internal Imports
    # ==================================================================================================================

    # INFO: long-running action
    def prepare_directory_for_import(self,
                                     source_dir: str,

                                     tbl_name: str = None,
                                     desc: str = None,

                                     allowed_ext: Set[str] = None,
                                     recursive: bool = True,

                                     append: bool = False,
                                     purge: bool = False) -> str:
        """
        Go through all files in the directory, and prepare the index for import.

        Directory may not be subdirectory of database.

        If no MetadataAggregator was set in the mda attribute, a new instance will be created.
        Using dateutil, with loggers logger="MetadataAggregator" and "MetadataAggregator.Parsing"

        :param source_dir: Directory to import into the db
        :param allowed_ext: Allowed extensions to import from. Defaults to None (Uses from Config)
        :param tbl_name: Name of temporary table created for import. Defaults to hash(datetime.now())
        :param recursive: Recursively index all subdirectories.
        :param desc: Description of the table. Defaults to None

        :param append: Files were added in the import directory. Add the new files to the table. Don't modify the data
            in the import table for the files already indexed.
        :param purge: Clear the import table and perform indexing again, retaining the table name.

        :returns: import table name. Will be the tbl_name is you provide it, otherwise the generated table name
        """
        if source_dir.startswith(self.root_path):
            raise ValueError("Cannot import database into itself")

        assert self.mda is not None, "MetadataAggregator needed for import preparation"

        # Defaulting allowed_extensions
        if allowed_ext is None:
            allowed_ext = set(defaults.video_extensions + defaults.image_extensions)

        # INFO: Handling all cases between append and purge for ease of understanding of the logic
        if append and purge:
            raise ValueError("Cannot specify both append and purge at the same time")

        elif append and not purge:
            assert tbl_name is not None, "Table name needs to be specified for append"
            if not self.db.import_table_exists(name=tbl_name):
                raise ValueError("Table doesn't exist, cannot append")

        elif not append and purge:
            assert tbl_name is not None, "Table name needs to be specified for purge"

            if self.db.import_table_exists(name=tbl_name):
                self.main_logger.info(f"Purging {tbl_name}")
                self.db.remove_import_table(name=tbl_name)

            tbl_name = self.db.add_import_table(root_path=source_dir, name=tbl_name, description=desc)

        elif not append and not purge:
            if not self.db.import_table_exists(name=tbl_name):
                tbl_name = self.db.add_import_table(root_path=source_dir, name=tbl_name, description=desc)
            else:
                raise ValueError(f"Table with name {tbl_name} already exists")

        else:
            raise ImplementationError("Tertiem Non Datur")

        # Actually search the provided directory
        if recursive:
            file_count = 0
            # Compute Number of files needed for progress bar
            for root, dirs, files in os.walk(source_dir):
                file_count += len(files)

            for root, dirs, files in os.walk(source_dir):
                for f in files:
                    self._prepare_file_import(file_path=os.path.join(root, f),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=append)
        else:
            file_count = len(os.listdir(source_dir))

            for entry in os.listdir(source_dir):
                if os.path.isfile(os.path.join(source_dir, entry)):
                    self._prepare_file_import(file_path=os.path.join(source_dir, entry),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=append)

        self.db.commit()
        return tbl_name

    # INFO: long-running action
    def search_db_for_new_files(self, allowed_ext: Set[str] = None) -> None | Tuple[str, int]:
        """
        Search the database folder itself for new files which were added by the user. Basically performs identical
        operation to import.

        Files are determined to be new, if the filename doesn't exist in the database. That means, if you remove a file
        with name n and add a different file with name n, this function will not detect the file as new and ignore it.

        :param allowed_ext: Allowed file extensions.

        :returns: None if no new files were detected. Tuple[import_table_name, new_file_count]
        """
        # Create import table
        tbl_name = self.db.add_import_table(root_path=self.root_path, internal=True,
                                            description="Internal Import, detect new files in db")

        if allowed_ext is None:
            allowed_ext = set(defaults.video_extensions + defaults.image_extensions)

        new_files = 0

        # Walk the directory
        for root, dirs, files in os.walk(self.root_path):
            if root.startswith(self.db.get_temp_dir()):
                continue

            if root.startswith(self.db.get_temp_dir()):
                continue

            if root.startswith(self.db.get_thumb_dir()):
                continue

            for file in files:
                key = self.db.db_resolve_filename_to_key(file)

                # Name not in db, importing file
                if key is None:
                    # USE self.add_file_to_import_table()
                    self._prepare_file_import(file_path=os.path.join(root, file),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=False)
                    new_files += 1

                # File exists
                else:
                    # Check that the file is in the correct directory.
                    path = self.db.db_resolve_key_to_abs_path(key)

                    if not path == os.path.join(root, file):
                        self.file_system_logger.warning(f"File {file} found in db but path mismatch:"
                                                        f"DB-Path: {path}, Discover Path: {os.path.join(root, file)}")

        if new_files == 0:
            self.main_logger.info("No new files in db were detected. Removing empty import table.")
            self.db.remove_import_table(tbl_name)
            return None

        self.db.commit()
        return tbl_name, new_files

    # INFO: long-running action
    def update_allowed(self, allowed_ext: Set[str], tbl: str) -> Tuple[int, int, int]:
        """
        Update the allowed extensions for a given

        :param allowed_ext: Allowed extensions to import from.
        :param tbl: Name of temporary table created for import.

        :returns: <number of files now allowed>, <number of files now excluded>, <number of files unaffected>
        """
        for ext in allowed_ext:
            if ext[0] != ".":
                raise ValueError(f"Allowed Extensions must start with a '.' {ext}")

        self.main_logger.info(f"Updating allowed extensions in {tbl} with {allowed_ext}")

        now_allowed = 0
        now_disallowed = 0
        same = 0

        for row in self.db.update_allowed_iterator(tbl):
            key, _a, original_filename = row
            allowed = bool(_a)

            # INFO: Need to update mark_for_import to 0, to ensure we don't get any accidental imports of not allowed
            #  files.
            if allowed and os.path.splitext(original_filename)[1] not in allowed_ext:
                now_disallowed += 1
                self.db.set_allowed(tbl_name=tbl, allowed=Allowed.NOT_ALLOWED_EXT, key=key)
                self.main_logger.debug(f"{key} is now disallowed")

            elif not allowed and os.path.splitext(original_filename)[1] in allowed_ext:
                now_allowed += 1
                self.main_logger.debug(f"{key} is now allowed")
                self.db.set_allowed(tbl_name=tbl, allowed=Allowed.ALLOWED, key=key)

            else:
                same += 1
                self.main_logger.debug(f"{key} remains the same")

        self.find_match_for_import_table(tbl)
        self.main_logger.info(f"Updated Allowed {tbl}. {now_allowed} now allowed, {now_disallowed} now disallowed, "
                              f"{same} stayed the same")
        self.db.commit()
        return now_allowed, now_disallowed, same

    # INFO: long-running action
    def find_match_for_import_table(self, tbl_name: str, recompute: bool = False) -> int:
        """
        Find matches for files in a given import table.

        :param tbl_name: Name of temporary table created for import.
        :param recompute: Recompute match for everything or only for files which have not matches are allowed and
            not imported

        :returns: int - number of files processed .
        """
        if not self.db.import_table_exists(name=tbl_name):
            raise ValueError(f"Table {tbl_name} doesn't exist")

        count = 0
        for row in self.db.find_import_match_iterator(tbl_name=tbl_name, recompute=recompute):
            key, original_filename, original_dirname, file_size_bytes, file_hash = row
            target_fp = str(os.path.join(original_dirname, original_filename))

            assert os.path.exists(target_fp), "Import file needs to exist."

            matches, highest_key, highest_match = self._get_import_best_match_type(tgt_fp=target_fp,
                                                                                   file_hash=file_hash,
                                                                                   fsb=file_size_bytes)

            self.db.set_match_type_import_table(tbl_name=tbl_name, key=key, matches=matches,
                                                best_match=highest_key, best_match_type=highest_match)

            count += 1

        self.main_logger.info(f"Found {count} matches for {tbl_name}")
        self.db.commit()
        return count

    # INFO: long-running action
    def perform_import(self, tbl_name: str, _dest_dir: str = None, add_safety_exif_tags: bool = None) -> int:
        """
        Imports all files from the given import table into the main database.
        - Files which are imported already will be ignored and
        - All disallowed files will not be imported.

        :param tbl_name: Name of the table to import from
        :param _dest_dir: Destination directory to create in within the database. Defaults to db/yyyy/mm/dd/
        :param add_safety_exif_tags: Add the datetime to exiftag if only filesystem datetime is available.
            (Override, default taken from config)

        :return: Number of imported files
        """
        # PRECONDITION: Reserved name not taken.
        if add_safety_exif_tags is None:
            add_safety_exif_tags = self.config.add_safety_exif_tags

        # Handle dest dir
        if _dest_dir is not None:
            if not os.path.isabs(_dest_dir):
                dest_dir = os.path.abspath(os.path.join(self.root_path, _dest_dir))
            else:
                dest_dir = os.path.abspath(_dest_dir)

            self.db.verify_custom_target_dir(dest_dir)

        if not self.db.import_table_exists(name=tbl_name):
            raise ValueError(f"Table {tbl_name} doesn't exist")

        if self.db.import_table_flags(tbl_name).internal:
            raise TypeError("cannot import internal import table with perform_import")

        assert self.mda is not None, "Metadata aggregator needed for perform import"

        count = 0
        for row in self.db.perform_import_iterator(tbl_name):
            # Handle the setting of all the rows needed into the main table.
            k, ofn, ofd, md, gfmd, fh, fsb, dt, tz, nt, gps_lat, gps_long, dts, allowed, impk = row
            default_flags = MainFlags.default()

            # Set verify on FILE_AWARE
            if dts == DateTimeSource.FILE_AWARE:
                default_flags.verify = True

            if allowed != Allowed.ALLOWED:
                self.main_logger.warning(f"Found entry marked for import, that isn't allowed.")
                assert False, "Invariant broken, found element marked for import with allowed = 0"
                continue

            # Sanity check
            assert import_key is None, "File marked as not imported, shouldn't have a import_key set."

            # Insert into main table and add
            self.db.insert_row_main_table(original_filename=ofn, db_name=self.db.reserved_temp_file_name, dt=dt,
                                          timezone=tz, flags=default_flags, google_metadata=gfmd, metadata=md)

            insert_key = self.db.db_resolve_filename_to_key(self.db.reserved_temp_file_name)
            assert insert_key is not None, "Key should exist after insert."

            # Handle metadata table
            self.db.insert_row_metadata_table(key=insert_key, original_dirname=ofd, naming_tag=nt, datetime_source=dts)

            # Handle GPS
            self._handle_gps_import(gps_lat=gps_lat, gps_long=gps_long, main_key=insert_key)

            # Handle hash
            assert fh is not None, "File Hash needs to be defined"
            self.db.check_add_file_hash(file_key=insert_key, file_hash=fh, file_size=fsb, initial=True)

            self._import_file(original_filename=ofn,
                              original_dirname=ofd,
                              fdt=dt,
                              tgt_dir=dest_dir,
                              key=import_key,
                              add_tag=add_safety_exif_tags and default_flags.verify)

            # Finally update the import table
            self.db.set_imported_status(tbl_name=tbl_name, key=k, status=ImportStatus.IMPORTED, import_key=insert_key)
            count += 1

        self.db.commit()
        return count

    # INFO: long-running action
    def import_internal_new_files(self, tbl: str, add_safety_exif_tags: bool = None,
                                  rename: bool = True, move: bool = True) -> Tuple[int, int]:
        """
        Import the files found within the database folder.
        Needs to add entries for db_dir with every file separately.

        :param tbl: Table name of the import table
        :param add_safety_exif_tags: Add safety exif tag, if the datetime source is from the file metadata,
            default from config
        :param rename: Rename the file to the db_name
        :param move: Move the file to the db_name

        :returns: number of files imported, number of files with name conflict.
        """
        name_conflict = 0
        count = 0

        if not self.db.import_table_exists(tbl):
            raise ValueError(f"Tabl {tbl} does not exist")

        if not self.db.import_table_flags(tbl).internal:
            raise ValueError("Cannot use this function with non-internal import table")

        if add_safety_exif_tags is None:
            add_safety_exif_tags = self.config.add_safety_exif_tags

        for row in self.db.perform_import_iterator(tbl):
            ik, ofn, ofd, md, gfmd, fh, fsb, dt, tz, nt, gps_lat, gps_long, dts, allowed, ipk = row

            assert dt.tzinfo is not None, "All datetime objects should have tz"

            # Check input
            assert ipk is None, "SQL Error, files which are imported shouldn't have imported = 1"

            # Check allowed
            if allowed != Allowed.ALLOWED:
                raise ImplementationError("Only Allowed Files may have the marked for import flag")

            # Define flags
            flags = MainFlags.default()
            if dts == DateTimeSource.FILE_AWARE:
                flags.verify = True

            # Check name ok and mark not allowed if necessary
            if not rename:
                if self.db.db_resolve_filename_to_key(ofn) is not None:
                    self.db.set_allowed(tbl_name=tbl, key=ik, allowed=Allowed.NOT_ALLOWED_ERR,
                                        message=f"Filename {ofn} already exists")
                    self.main_logger.info(f"Couldn't import file {ofn}, filename already used in db")
                    name_conflict += 1
                    continue

                db_name = ofn
            else:
                db_name = self.db.reserved_temp_file_name

            self.db.insert_row_main_table(original_filename=ofn, flags=flags, dt=dt, timezone=tz, db_name=db_name,
                                          metadata=md, google_metadata=gfmd)

            insert_key = self.db.db_resolve_filename_to_key(db_name)
            assert insert_key is not None, "Key should exist after insert."

            # Handle metadata table
            self.db.insert_row_metadata_table(key=insert_key, original_dirname=ofd, naming_tag=nt, datetime_source=dts)

            # Handle GPS
            self._handle_gps_import(gps_lat=gps_lat, gps_long=gps_long, main_key=insert_key)

            # Handle hash
            assert fh is not None, "File Hash needs to be defined"
            self.db.check_add_file_hash(file_key=insert_key, file_hash=fh, file_size=fsb, initial=True)

            target_path = self._handle_file_internal_import(rename=rename, move=move,
                                                            dt=dt, main_key=insert_key, ofn=ofn, ofd=ofd)

            # Update the name in the db
            if rename:
                name = self.db.db_name(original_filename=ofn, key=insert_key, fdt=dt)
                self.db.update_row_main_table(key=insert_key, db_name=name)

            if flags.verify and add_safety_exif_tags:
                self._add_update_exif_tag(key=insert_key, target_datetime=dt, file_path=target_path)

            self.db.set_imported_status(tbl_name=tbl, import_key=insert_key, status=ImportStatus.IMPORTED, key=ik)

            count += 1

        self.db.commit()
        return count, name_conflict

    def _handle_gps_import(self, gps_lat: float, gps_long: float, main_key: int):
        """
        Add and or get the key of the gps entry in the gps table, and add the gps key to the metadata row of the
        given key.

        :param gps_lat: GPS Latitutde in Degrees.decimal
        :param gps_long: GPS Longitude in Degrees.decimal
        :param main_key: Main key of the gps entry.
        """
        # Handle GPS
        assert (gps_lat is not None and gps_long is not None) or (gps_lat is None and gps_long is None), \
            "gps_lat and gps_long unequally set."

        if gps_lat is not None and gps_long is not None:
            gps_key = self.db.insert_get_gps_loc(gps_lat=gps_lat, gps_long=gps_long)

            self.db.update_row_metadata_table(key=main_key, gps_location=gps_key)

    def _prepare_file_import(self, file_path: str, tbl_name: str, allowed_ext: Set[str], append: bool):
        """
        Handle Import for a singular file.

        PRECONDITION:
        - Filepath exists
        - Table Exists
        - File not in table

        :raises ValueError: If not append and file in table.
        """
        # Ensure file not in table yet.
        if self.db.get_import_table_key_from_path(tbl_name=tbl_name, path=file_path) is not None:
            if append:
                return
            else:
                raise ValueError(f"File {file_path} already exists in table {tbl_name}")

        pres = self.mda.handle_file(file_path)

        self.db.add_file_to_import_table(tbl_name=tbl_name, allowed_ext=allowed_ext, parsing_result=pres)

    def _get_general_best_match_type(self, tgt_fp: str, file_hash: str, fsb: int, latest: bool = False) \
            -> Tuple[Dict[int, NewMatchTypes], int | None, NewMatchTypes]:
        """
        PRECONDITION: tgt_fp exists.

        Given a file_hash and file_size returns the lowest MatchType

        :param tgt_fp: Target file path of the image in the import table
        :param file_hash: File hash of the image
        :param fsb: File size of the image

        :returns Dict of all hash_matches with match type, key of highest match, highest match value
        """
        mode = "ANY" if not latest else "latest"
        match_keys = self.db.find_hash_match_keys(target_hash=file_hash, file_size=fsb, mode=mode)
        return self._get_best_match_type_common(tgt_fp=tgt_fp, file_hash=file_hash, match_keys=match_keys)

    def _get_import_best_match_type(self, tgt_fp: str, file_hash: str, fsb: int) \
            -> Tuple[Dict[int, NewMatchTypes], int | None, NewMatchTypes]:
        """
        PRECONDITION: tgt_fp exists.

        Given a file_hash and file_size returns the lowest MatchType

        :param tgt_fp: Target file path of the image in the import table
        :param file_hash: File hash of the image
        :param fsb: File size of the image

        :returns Dict of all hash_matches with match type, key of highest match, highest match value
        """
        match_keys = self.db.find_hash_match_keys(target_hash=file_hash, file_size=fsb, mode="INITIAL")
        return self._get_best_match_type_common(tgt_fp=tgt_fp, file_hash=file_hash, match_keys=match_keys)

    def _get_best_match_type_common(self, tgt_fp: str, file_hash: str, match_keys: List[int]) \
            -> Tuple[Dict[int, NewMatchTypes], int | None, NewMatchTypes]:
        """
        Common functionality of getting the match types as well as the best match type from the list of matches.

        PRECONDITION: tgt_fp exists.

        :param tgt_fp: Target file path of the image in the import table
        :param file_hash: File hash of the image
        :param match_keys: Files which matched the size and hash

        :returns Dict of all hash_matches with match type, key of highest match, highest match value
        """
        keys: Dict[int, NewMatchTypes] = {}
        for m_key in match_keys:
            # Resolve the matched key to the filepath
            match_path = self.db.db_resolve_key_to_abs_path(key=m_key)
            binary_match = None

            if match_path is None:
                raise CorruptDatabase("Inconsistency between tables. File from hash_assoz not present in tables.")

            # Check the binary difference of the files if they exist
            if os.path.exists(match_path):
                binary_match = filecmp.cmp(tgt_fp, match_path, shallow=False)

            m_newest_hash, _ = self.db.get_newest_hash(m_key)

            # Rare occurrence
            # TODO different logger
            if m_newest_hash == file_hash and not binary_match:
                self.main_logger.warning("Found files with matching hash and size but different binary.")
            elif m_newest_hash != file_hash and binary_match:
                self.main_logger.warning("Found files different hashes but match binary.")

            flags = self.db.get_main_flags(m_key)
            if flags is None:
                raise CorruptDatabase("Inconsistency between tables. File from hash_assoz not present in main tables.")

            # parse into NewMatchTypes
            if not (flags.trashed and not flags.duplicate):
                if m_newest_hash != file_hash:
                    keys[m_key] = NewMatchTypes.HASH_MATCH_MAIN
                else:
                    assert m_newest_hash == file_hash, "Unexpected outcome, hashes should match."
                    if binary_match:
                        keys[m_key] = NewMatchTypes.BINARY_MATCH_MAIN
                    else:
                        # INFO: relegating the case when the file was missing i.e. binary_match is None and not
                        #  binary_match as HASH_MATCH. The assumption is, that the files were modified by some
                        #  other software but the hash and file size used to determine the match were correct.
                        #  Or alternatively, the part of the library is mounted from some other other location and
                        #  the mount isn't currently done.
                        keys[m_key] = NewMatchTypes.HASH_MATCH_MAIN

            elif flags.trashed and not flags.duplicate:
                if m_newest_hash != file_hash:
                    keys[m_key] = NewMatchTypes.HASH_MATCH_TRASH
                else:
                    assert m_newest_hash == file_hash, "Unexpected outcome, hashes should match."
                    if binary_match:
                        keys[m_key] = NewMatchTypes.BINARY_MATCH_TRASH
                    else:
                        # INFO: Dito as for DBLocation.MAIN
                        keys[m_key] = NewMatchTypes.HASH_MATCH_TRASH

            elif not flags.trashed and flags.duplicate:
                if m_newest_hash != file_hash:
                    keys[m_key] = NewMatchTypes.HASH_MATCH_REPLACED
                else:
                    assert m_newest_hash == file_hash, "Unexpected outcome, hashes should match."
                    if binary_match:
                        keys[m_key] = NewMatchTypes.BINARY_MATCH_REPLACED
                    else:
                        # INFO: Dito as for DBLocation.MAIN
                        keys[m_key] = NewMatchTypes.HASH_MATCH_REPLACED

            elif flags.trashed and flags.duplicate:
                raise CorruptDatabase("Trashed and Duplicate are True")

            else:
                raise ImplementationError("DBLocation not covered")

        highest_match = None
        highest_match_key = None

        # Get highest quality match from all matches.
        for key, match in keys.items():
            if highest_match is None:
                highest_match = match
                highest_match_key = key

            else:
                if match.value < highest_match.value:
                    highest_match = match
                    highest_match_key = key

        if highest_match is None:
            return {}, None, NewMatchTypes.NO_MATCH

        return keys, highest_match_key, highest_match

    def _import_file(self,
                     key: int,
                     original_filename: str,
                     original_dirname: str,
                     fdt: datetime.datetime,
                     tgt_dir: str = None,
                     add_tag: bool = False):
        """
        Import a given file into the database.

        PRECONDITION:
        - The key exists in the database, and the file exists on disk.
        - The tgt_dir is an abs path

        :param key: key in main table
        :param original_filename: original filename prior to import
        :param original_dirname: original dirname prior to import
        :param fdt: datetime of
        :param tgt_dir: Target directory to import into if not default based on datetime
        :param add_tag: Add exiftag to file. (no conditional checking in function, if True, tag will be set.)
        """
        assert os.path.exists(os.path.join(original_dirname, original_filename)), "Source File doesn't exist"

        if tgt_dir is not None:
            dir_key = self._insert_get_dir(tgt_dir)
        else:
            tgt_dir = os.path.join(self.root_path, self.db.dt_to_dir(fdt))
            if not os.path.exists(tgt_dir):
                os.makedirs(tgt_dir)
                self.main_logger.debug(f"Creating Directory: {self.db.dt_to_dir(fdt)}")
            dir_key = None

        db_name = self.db.db_name(original_filename=original_filename, fdt=fdt, key=key)

        # copy the file to the target location
        shutil.copy2(os.path.join(original_dirname, original_filename), os.path.join(tgt_dir, db_name))
        self.main_logger.debug(f"Imported File: {original_filename}")

        assert self.mda is not None, "Metadata Aggregator is needed for import file"
        if add_tag:
            self._add_update_exif_tag(key=key, file_path=os.path.join(tgt_dir, db_name), target_datetime=fdt)

        self.db.update_row_main_table(key=key, db_name=db_name)
        self.db.update_row_metadata_table(key=key, db_dir=dir_key)

    def _insert_get_dir(self, dir_name: str) -> int:
        """
        PRECONDITION:

        - dir_name is absolute
        - dir_name is child of root_path
        - dir_name separated by os.sep

        Get the key of a given custom directory.

        :param dir_name: The name of the directory to insert.
        """
        rel_path = dir_name.removeprefix(self.root_path).removeprefix(os.sep)
        rel_path_list = rel_path.split(os.sep)

        dir_key = self.db.insert_get_dir(rel_path_list)

        if not os.path.exists(dir_name):
            self.main_logger.debug(f"Created custom dir {rel_path}")
            os.makedirs(dir_name)

        return dir_key

    def _handle_file_internal_import(self, rename: bool, move: bool,
                                     main_key: int, dt: datetime.datetime, ofn: str, ofd: str) -> str:
        """
        Handle a file from an internal import operation

        :param rename: Whether tho rename the file so it has a standardized filename
        :param move: Whether to move the file to the directory indicated by its datetime
        :param main_key: The key of the file in the main table
        :param dt: The datetime of the file
        :param ofn: The name of the file
        :param ofd: The name of the file

        :returns: file path of the file after import
        """
        if rename and move:
            target_path = os.path.join(self.root_path, self.db.dt_to_dir(dt),
                                       self.db.db_name(original_filename=ofn, key=main_key, fdt=dt))

            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            assert not os.path.exists(target_path), "Target path is not supposed to exist"
            os.rename(os.path.join(ofd, ofn), target_path)

        elif not rename and move:
            target_path = os.path.join(self.root_path, self.db.dt_to_dir(dt), ofn)

            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            if os.path.exists(target_path):
                # Remove rows inserted for the file before raising error.
                self.db.delete_row_main_table(key=main_key)
                self.db.delete_row_metadata_table(key=main_key)
                self.db.commit()
                raise FileExistsError(f"Couldn't import {ofn}, file already exists in {self.db.dt_to_dir(dt)}")

            os.rename(os.path.join(ofd, ofn), target_path)

        elif rename and not move:
            ofd: str
            assert ofd.startswith(self.root_path), "Erroneous import, original_dir_name should start with root_dir"
            target_path = os.path.join(ofd, self.db.db_name(original_filename=ofn, key=main_key, fdt=dt))

            # Check if the directory matches the datetime
            if os.path.dirname(target_path) != os.path.join(self.root_path, self.db.dt_to_dir(dt)):
                db_local_dir = os.path.dirname(target_path)
                dir_key = self._insert_get_dir(dir_name=db_local_dir)
                self.db.update_row_metadata_table(key=main_key, db_dir=dir_key)

            assert not os.path.exists(target_path), "Target path is not supposed to exist"
            os.rename(os.path.join(ofd, ofn), target_path)

        elif not rename and not move:
            target_path = os.path.join(ofd, ofn)
            dt_dir = os.path.join(self.root_path, self.db.dt_to_dir(dt))

            # Need to add a db_local_dir if the directory doesn't match the datetime of the image
            if ofd != dt_dir:
                dir_key = self._insert_get_dir(ofd)
                self.db.update_row_metadata_table(key=main_key, db_dir=dir_key)

        else:
            raise ImplementationError("Tertiem Non Datur")

        return target_path

    # ==================================================================================================================
    # DB Integrity Checks
    # ==================================================================================================================

    # INFO: long-running action,
    def check_presence(self, selection: Selection = None, m_type: MediaType = MediaType.MAIN):
        """
        Go through db and check that all files in the db are present in the file system.

        :param selection: Use selection marker of images to check changed hashes for those images.
        :param m_type: For which type of media to update the presence.
        """
        self.db.clear_presence_table()
        count = 0

        if m_type == MediaType.MAIN:
            dup_flag = False
            trash_flag = False
        elif m_type == MediaType.DUPLICATE:
            dup_flag = True
            trash_flag = False
        elif m_type == MediaType.TRASH:
            trash_flag = True
            dup_flag = False
        else:
            raise ImplementationError("Unknown MediaType")

        for key, flags in self.db.main_key_flags_iterator(allow_selection=True, selection=selection,
                                                          trashed=trash_flag, duplicate=dup_flag):

            # Internal checks for general sql statement integrity
            assert flags.trashed == trash_flag and flags.duplicate == dup_flag, \
                "SQL Error, no trashed or duplicate files allowed"

            # Check selection.
            if __debug__:
                if selection.selection_type == SelectionType.SELECTION_A and not flags.sel_a:
                    raise ImplementationError("Didn't receive Selection A")
                elif selection.selection_type == SelectionType.SELECTION_B and not flags.sel_b:
                    raise ImplementationError("Didn't receive Selection B")

            self.db.check_flags(key=key, flags=flags, miniature=True, thumbnail=True)
            # Don't want to fuck up cache.
            path = self.db.db_resolve_key_to_abs_path(key)

            if os.path.exists(path) and not flags.present:
                self.db.insert_row_presence_table(key)
                count += 1

            elif not os.path.exists(path) and flags.present:
                self.db.insert_row_presence_table(key)
                count += 1

        self.db.commit()

        self.main_logger.info(f"Detected {count} entries in main table with mismatched presence flag")
        return count

    # INFO: long-running action
    def check_filenames(self, only_latest: bool = False) -> int:
        """
        Check the file names by associating file hashes from files found in the db with files.

        The function checks the database. If a file is not known in the database, its hash, and file size are computed.

        The hashes and file size are then matched against the hash_assoz table to see if a file with this hash existed.
        By default, any hash a file has had over time will be considered. With only_latest, only the latest hashes are
        considered.

        The function returns the number of probably renamed files it found.
        """
        self.db.clear_filename_update_table()

        count = 0

        for root, dirs, files in os.walk(self.root_path):
            if root.startswith(self.db.get_temp_dir()):
                continue

            if root.startswith(self.db.get_temp_dir()):
                continue

            if root.startswith(self.db.get_thumb_dir()):
                continue

            for file in files:
                tgt_key = self.db.db_resolve_filename_to_key(file)

                if tgt_key is not None:
                    continue

                fsb = os.stat(os.path.join(root, file)).st_size
                fh = self.mda.hash_file(os.path.join(root, file))

                self.db.insert_row_name_update_table(filename=file, dirname=root, file_size=fsb, file_hash=fh)
                count += 1

        if count == 0:
            return 0

        for key, name, dir_name, fsb, fh in self.db.find_hash_match_iterator():
            name: str
            dir_name: str

            matches, best_match, best_match_type = \
                self._get_general_best_match_type(file_hash=fh,
                                                  fsb=fsb,
                                                  tgt_fp=os.path.join(dir_name, name),
                                                  latest=only_latest)

            self.db.set_match_data_name_update_table(key=key, matches=matches, best_match=best_match,
                                                  match_type=best_match_type)

        self.db.commit()
        return count

    # INFO: long-running action
    def check_file_hashes(self, selection: Selection = None) -> int:
        """
        Check the file hashes based on the file names.

        INFO: Only files which aren't duplicates and which aren't in the trash are considered

        :returns: Number of files with different hash
        """
        self.db.clear_hash_update_table()
        count = 0

        for key, flags in self.db.main_key_flags_iterator(allow_selection=True, selection=selection,
                                                          trashed=False, duplicate=False):

            org_path = self.db.db_resolve_key_to_abs_path(key)

            # Checks on path and flags
            assert org_path is not None, "Key in main table should resolve to path"
            self.db.check_flags(key=key, flags=flags, org_path=org_path, miniature=True, thumbnail=True)

            if __debug__ and (flags.trashed or flags.duplicate):
                raise ImplementationError("SQL Statement Error, shouldn't get duplicates or trashed files")

            # Cannot hash what doesn't exist
            if not os.path.exists(org_path):
                continue

            # Get current hash and file size
            new_hash = self.mda.hash_file(org_path)
            file_size_bytes = os.stat(org_path).st_size

            # Get the newest file hash of that file from the db
            h, fsb, fhdt = self.db.get_newest_hash(key)

            if (h, fsb, fhdt) == (None, None, None):
                raise CorruptDatabase(f"Couldn't get newest hash for key: {key}")

            # Different hash, update
            if new_hash != h:
                self.db.insert_row_hash_update_table(key=key, new_hash=new_hash, file_size=file_size_bytes)
                count += 1

            # Rare occurrence
            elif file_size_bytes != new_hash and new_hash == h:
                self.main_logger.info(f"Rare Occurrence: File Size changed but hash stayed the same: "
                                      f"{org_path}")

        self.db.commit()
        return count

    # INFO: long-running action
    def update_hash_from_filename_table(self) -> Tuple[int, int]:
        """
        Updates the hash of the image file with the given file name.

        # INFO: Because this function is a long running action, it isn't a database function
        #   (despite being only in the db)

        :return: number of new entries in hash_assoz table, number of hashes updated
        """
        if self.db.hash_update_table_size() == 0:
            raise ValueError("Hash table is empty")

        modified = 0
        added = 0
        for mk, nh, fsb in self.db.hash_update_iterator():
            added += int(not self.db.check_add_file_hash(file_hash=nh, file_key=mk, file_size=fsb))
            modified += 1

        self.main_logger.info(f"Updated {modified} file hashes. {added} of unseen hashes.")

        self.db.commit()
        return added, modified

    # INFO: long-running action,
    def update_filename_from_hash(self, move: bool):
        """
        Update the names of files resolved through hash and filesize.

        INFO: Update only possible for files which are neither a duplicate nor trashed.
        INFO: Given all MatchTypes, the function only considers HASH_MATCH_MAIN

        :parma move: move the file to the correct location based on it's datetime.
        """
        count = 0
        conflict = 0
        for key, name, dir_name, best_match in self.db.update_filename_from_hash_iterator():
            assert best_match is not None, "best_match shouldn't be None, SQL Error"

            # Try to get the parent's path
            tgt_path = self.db.db_resolve_key_to_abs_path(best_match)
            if tgt_path is None:
                # INFO: This case should be technically impossible. Can only happen if the name_update_table is
                #  generated, then a file is forgotten in the main table and then update_filename_from_hash is  called.
                self.db.set_updated_status_name_update_table(
                    key=key, status=NameUpdateStatus.FAILED, message="Matched key doesn't exist in main table")

                conflict += 1
                continue

            if os.path.exists(tgt_path):
                # INFO: Can occur if we don't match latest, the parent file exists but has a different newest_hash
                self.db.set_updated_status_name_update_table(
                    key=key, status=NameUpdateStatus.FAILED, message="Parent File is Present")

                conflict += 1
                continue

            # Determine target location
            if not move:
                dst_path = os.path.join(dir_name, name)
            else:
                dst_path = os.path.join(os.path.dirname(tgt_path), name)

            # Check if the destination exists, if it's different from the current path.
            if dst_path != os.path.join(dir_name, name) and os.path.exists(dst_path):
                self.db.set_updated_status_name_update_table(key=key, status=NameUpdateStatus.FAILED,
                                                             message="File exists at destination")

                conflict += 1
                continue

            flags = self.db.get_main_flags(best_match)
            assert flags is not None, "Flags should exist, if path resolved"

            if flags.trashed or flags.duplicate:
                self.db.set_updated_status_name_update_table(
                    key=key, status=NameUpdateStatus.FAILED,message=f"Parent is trash or duplicate, update not allowed")

                conflict += 1
                continue

            # Need to update
            dir_key = None
            if os.path.dirname(dst_path) != os.path.dirname(tgt_path):
                dir_key = self._insert_get_dir(os.path.dirname(dst_path))

            # Only need to move the file if the destination are actually different.
            if os.path.join(dir_name, name) != os.path.join(os.path.dirname(tgt_path), name):
                os.rename(os.path.join(dir_name, name), os.path.join(os.path.dirname(tgt_path), name))

            flags.present = True

            self.db.set_updated_status_name_update_table(key=key, status=NameUpdateStatus.UPDATED)
            self.db.update_row_main_table(key=best_match, db_name=name, flags=flags)

            if dir_key is not None:
                self.db.update_row_metadata_table(key=key, db_dir=dir_key)

            count += 1

        self.main_logger.info(f"Updated names of :{count} files. Couldn't rename: {conflict} files because of "
                              f"conflicts.")
        self.db.commit()
        return count, conflict

    def prune_db_dir(self) -> int:
        """
        Remove all entries and all directories form the database which are no longer referenced
        """
        # TODO Darktable

        # INFO: A db_local_dir can share a partial path with other directories, for example
        #   Assume you had an event spanning a weekend and it's in a given month, so what you want is to store it in
        #   root_dir/YYYY/MM/event-name/. Deleting the db_local_dir i.e. ['YYYY', 'MM', 'event-name'] will attempt to
        #   remove the lowest node tree and then go up and attempt to remove all upper nodes and remove those as well
        #   if they are empty.
        keys_to_delete = []
        for raw in self.db.prune_db_dir_iterator():
            ktd = raw[0]
            db_local_dir = raw[1]

            first = True
            for i in range(len(db_local_dir)):
                tgt_dir = os.path.join(self.root_path, *db_local_dir[:len(db_local_dir) - i])

                # Path doesn't exist => path empty => can be deleted.
                if not os.path.exists(tgt_dir):
                    if first:
                        keys_to_delete.append(ktd)
                        first = False
                    continue

                # path exists
                if os.listdir(str(tgt_dir)):
                    if first:
                        self.main_logger.warning(f"Lowest Directory Not Empty: {tgt_dir}")

                    # directory not empty, abort delete.
                    break

                # No guard triggered, we're deleting at last
                self.main_logger.debug(f"deleting directory: {tgt_dir}")
                shutil.rmtree(tgt_dir)

                if first:
                    keys_to_delete.append(ktd)
                    first = False

        self.db.delete_dir(keys_to_delete)

        if len(keys_to_delete) > 0:
            self.main_logger.info(f"Pruned {len(keys_to_delete)} rows in dir table")
        else:
            self.main_logger.debug(f"Call to prune_dir, no rows pruned")

        self.db.commit()
        return len(keys_to_delete)

    def prune_filesystem_directories(self) -> int:
        """
        Walk through the file system and check for empty directories. Remove empty directories if they exist.
        """
        count = 0
        current_count = self._internal_prune_fs_dir()

        # Call recursively
        while current_count > 0:
            count += current_count
            current_count = self._internal_prune_fs_dir()

        return count

    def _internal_prune_fs_dir(self) -> int:
        """
        Internal function to prune file system directories. Needs to be called recursively to check
        """
        dir_to_prune = []
        for root, dirs, files in os.walk(self.root_path, topdown=False):
            if root.startswith(self.db.get_temp_dir()):
                continue

            if root.startswith(self.db.get_temp_dir()):
                continue

            if root.startswith(self.db.get_thumb_dir()):
                continue

            if len(files) + len(dirs) == 0:
                dir_to_prune.append(root)

        # Early exit
        if len(dir_to_prune) == 0:
            return 0

        count = 0
        for d in dir_to_prune:
            local_path = d.removeprefix(self.root_path).removeprefix(os.sep)
            local_path_list = local_path.split(os.sep)

            # Got something from the db_dir table, continue.
            if self.db.get_dir_key(local_path_list) is not None:
                continue

            # PRECONDITION: Directory is empty and not listed in the db_dir table, deleting
            self.main_logger.debug(f"Pruned {count} rows in dir table")
            shutil.rmtree(d)
            count += 1

        return count

    # ==================================================================================================================
    # Deduplication
    # ==================================================================================================================

    # INFO: long-running action
    def find_hash_based_duplicates(self):
        """
        Find any grouping of hashes which have the same file size, and hash.
        """
        ...

    # INFO: long-running action
    def deduplicate_internal(self, scope: GroupingCriterion):
        """
        Performs the action of deduplication within given scopes (Given by grouping criterion)

        :param scope: Grouping criterion to deduplicate
        :param com: Connection object to report progress to frontend
        """
        ...

    # INFO: long-running action
    def deduplicate_partitions(self, a: Selection, b: Selection):
        """
        Perform a more specific deduplication.

        Partition can a time range(datetime, datetime)
        Partition can be selection from table (all rows which have the mark field set)
        Partition can be the entire table like import table
        """
        ...

    # ==================================================================================================================
    # UI Functions
    # ==================================================================================================================

    # TODO add gps option
    def modify_timezone(self,
                        key: int,
                        _target_tz: ZoneInfo | str | datetime.timedelta,
                        rename: bool = True,
                        replace: bool = False,
                        add_exif_tag: bool = None):
        """
        If a custom directory is set, the file isn't moved, if the file is in the default directory, the file is moved.

        Modify the timezone of a given file. File must be in the main table.

        If rename is set, the file will be renamed in the fs
        If replace is set, the timezone will be replaced (utc offset changes). Otherwise, utc-offset and time change.

        :param key: key in db of file which needs to be modified.
        :param _target_tz: Target timezone of the file.
        :param rename: If true, will rename the file in the main table.
        :param replace: If true, will replace the file in the main table.
        :param add_exif_tag: If true, will add exif_tag to the file. If None, default taken from config.
        """
        if isinstance(_target_tz, ZoneInfo):
            target_tz = _target_tz
        elif isinstance(_target_tz, str):
            target_tz = ZoneInfo(_target_tz)
        elif isinstance(_target_tz, datetime.timedelta):
            target_tz = datetime.timezone(_target_tz)
        else:
            raise TypeError("target_tz must be str, a ZoneInfo or datetime.timedelta.")

        # Get current row
        path_data = self.db.get_path_data(key=key)
        if path_data is None:
            raise ValueError(f"Couldn't find Path data for key: {key}")

        dt, flags, db_local_dir, db_name, original_name = path_data

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change datetime from files in trash, not present and duplicates")

        new_dt = dt.replace(tzinfo=target_tz) if replace else dt.astimezone(tz=target_tz)

        # Early exit, if the new datetime is equivalent to the old one.
        if new_dt == dt:
            # Only update the timezone
            self.db.update_row_main_table(key=key, timezone=new_dt.tzname())
            return

        if rename:
            new_name = self.db.db_name(original_filename=original_name, key=key, fdt=new_dt)

            # INFO: Updates the key_to_filepath_cache
            self._internal_rename(key=key, flags=flags, db_name=db_name, new_name=new_name, dt=dt, new_datetime=new_dt,
                                  db_local_dir=db_local_dir)

            self.db.update_row_main_table(key=key, datetime=new_dt, timezone=new_dt.tzname(), db_name=new_name)

        else:
            # INFO: Updates the key_to_filepath_cache
            self._internal_move_file(ndt=new_dt, key=key, flags=flags, dt=dt, db_local_dir=db_local_dir, dbn=db_name)

            self.db.update_row_main_table(key=key, datetime=new_dt, timezone=new_dt.tzname())

        if add_exif_tag or (add_exif_tag is None and self.config.add_safety_exif_tags):
            if dt != new_dt:
                self._add_update_exif_tag(key=key, target_datetime=new_dt, file_path=self.resolve_key_to_path(key))

        # Evicting lookup of old name to key
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        self.db.commit()

    # TODO params if selected from exif_parsing_results
    def change_datetime(self,
                        key: int,
                        tag: str | List[Union[str, int]] | DoubleKey,
                        dts: DateTimeSource,
                        new_dt: datetime.datetime = None,
                        rename: bool = True,
                        add_exif_tag: bool = None):
        """
        If a custom directory is set, the file isn't moved, if the file is in the default directory, the file is moved.

        Change the datetime associated with the given image. Each image should have a filename string and a given
        datetime. By default, the file name will also b e changed. This is only available for images in main table.

        :param key: key of image to update
        :param new_dt: new datetime object. (should have an utc offset)
        :param tag: tag of image to use for update.
        :param dts: date time source (where the new datetime is coming from)
        :param rename: Rename image if True.
        :param add_exif_tag: If true, will add exif_tag to the file. If None, default taken from config.
        """
        if new_dt.tzinfo is None:
            raise ValueError("new_dt must have a timezone")

        path_data = self.db.get_path_data(key=key)
        if path_data is None:
            raise ValueError(f"Couldn't find Path data for key: {key}")

        dt, flags, db_local_dir, db_name, original_name = path_data

        new_name = self.db.db_name(original_filename=original_name, key=key, fdt=new_dt)

        timezone = new_dt.tzname()
        assert timezone is not None, "Unexpected timezone of None"

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change datetime from files in trash, not present and duplicates")

        # INFO: no exit with dt == new_dt because we could be switching keys!!!
        if rename:
            # Rename the file
            self._internal_rename(key=key, flags=flags, db_name=db_name, new_name=new_name, dt=dt, new_datetime=new_dt,
                                  db_local_dir=db_local_dir)

        else:
            # Only move the file.
            self._internal_move_file(ndt=new_dt, key=key, flags=flags, dt=dt, db_local_dir=db_local_dir, dbn=db_name)

        self.db.update_row_main_table(key=key, datetime=new_dt, db_name=new_name, timezone=timezone)

        self.db.update_row_metadata_table(key=key,
                                          naming_tag=NewMetadataAggregator.serialize_key(tag),
                                          datetime_source=dts)

        if add_exif_tag or (add_exif_tag is None and self.config.add_safety_exif_tags):
            if dt != new_dt:
                self._add_update_exif_tag(key=key, target_datetime=new_dt, file_path=self.resolve_key_to_path(key))

        # Evicting lookup of old name to key
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        self.db.commit()

    def change_filename(self, key: int, new_filename: str):
        """
        INFO: Function keeps the file in the same directory of the database.

        The function exists for the purpose of allowing the user to change file names however it is not recommended.

        Change the filename. Set a custom filename. The filename must be unique within the database.
        Also, the file must still be present.

        :param key: Key in main database to update with the new filename
        :param new_filename: The new file name to use. Sets the db_name column.
        """
        # PRECONDITION: Filename not present
        path_data = self.db.get_path_data(key=key)
        if path_data is None:
            raise ValueError(f"Couldn't find Path data for key: {key}")

        dt, flags, db_local_dir, db_name, _ = path_data

        # Abort if the name is the same
        if db_name == new_filename:
            return

        if self.filename_to_key(new_filename):
            raise ValueError("Filename already exists in main table.")

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change name from files in trash, not present and duplicates")

        # INFO: Updates the key_to_filepath_cache
        self._internal_rename(key=key,
                              flags=flags,
                              db_name=db_name,
                              new_name=new_filename,
                              dt=dt,
                              db_local_dir=db_local_dir)

        # Update the database after renaming
        self.db.update_row_main_table(key=key, db_name=new_filename)
        self.db.update_row_metadata_table(key=key, naming_tag="CUSTOM")

        # Update cache
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        self.db.commit()

    def move_file(self, key: int, new_dir: str):
        """
        Move a file within the database. Option to set the db_dir later on
        """
        ...

        # TODO reset flags of hash, presence and filename tables

    def _internal_rename(self, key: int, flags: MainFlags, db_name: str, new_name: str, dt: datetime.datetime,
                         new_datetime: datetime.datetime = None, db_local_dir: str = None):
        """
        Shared part of the function that all functions that rename a file use.

        INFO: Sets the prune_fs_dir flag.

        :param key: key of image to rename
        :param db_name: current name of image to rename
        :param new_name: new name of image to rename
        :param flags: Flags of the current file needed to determine path
        :param dt: Datetime of the file
        :param new_datetime: New datetime of the file
        :param db_local_dir: Local path of current file if not standard.

        :raises FileNotFoundError: if the path where the file is currently supposed to be doesn't exist
        :raises FileExistsError: if the path where the file is supposed to be moved to does exist
        """
        # Parse the paths.
        ndt = dt if new_datetime is None else new_datetime

        if flags.trashed or flags.duplicate:
            current_path = os.path.join(self.db.get_trash_dir(), db_name)
            new_path = os.path.join(self.db.get_trash_dir(), new_name)
        elif db_local_dir is not None:
            current_path = os.path.join(self.root_path, *self.db.parse_db_local_dir(db_local_dir), db_name)
            new_path = os.path.join(self.root_path, *self.db.parse_db_local_dir(db_local_dir), new_name)
        else:
            assert db_local_dir is None and ndt is None, \
                f"Unexpected argument combination. db_local_dir {db_local_dir}, ndt: {ndt}"
            current_path = os.path.join(self.root_path, self.db.dt_to_dir(dt), db_name)
            new_path = os.path.join(self.root_path, self.db.dt_to_dir(ndt), new_name)

        self.db.check_flags(key=key, flags=flags, org_path=current_path)

        if new_path == current_path:
            return

        # Check the file extensions.
        if os.path.splitext(new_name)[1] != os.path.splitext(db_name)[1]:
            self.main_logger.warning("New file extension does not match DB file extension")

        # Ensure existence, raise error (cannot be fixed by good programming, so no assert)
        if not os.path.exists(current_path):
            raise FileNotFoundError("Original File doesn't exist, cannot rename.")

        if os.path.exists(new_path):
            raise FileExistsError("New path exists already.")

        # PRECONDITION: File Exists, Filename not present
        os.rename(current_path, new_path)

        self.key_to_filepath_cache.update(arg=key, value=new_path)
        self.prune_fs_dir = True

    def _internal_move_file(self, key: int, flags: MainFlags, dbn: str, dt: datetime.datetime,
                            ndt: datetime.datetime = None,
                            db_local_dir: str = None):
        """
        Internal function to move a file once its datetime has been updated. Movement needed because resolution of
        path from datetime wouldn't work otherwise.

        :param key: key of image to rename
        :param dbn: current name of image to rename
        :param flags: Flags of the current file needed to determine path
        :param dt: Datetime of current file
        :param ndt: New datetime of current file
        :param db_local_dir: Local path of current file if not standard.

        :raises FileNotFoundError: if the path where the file is currently supposed to be doesn't exist
        :raises FileExistsError: if the path where the file is supposed to be moved to does exist
        """
        # Parse the paths.
        if flags.trashed or flags.duplicate:
            current_path = os.path.join(self.get_trash_dir(), dbn)
            new_path = os.path.join(self.get_trash_dir(), dbn)
        elif db_local_dir is not None:
            current_path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), dbn)
            new_path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), dbn)
        elif ndt is not None:
            current_path = os.path.join(self.root_path, self.dt_to_dir(dt), dbn)
            new_path = os.path.join(self.root_path, self.dt_to_dir(ndt), dbn)
        else:
            assert db_local_dir is None and ndt is None, \
                f"Unexpected argument combination. db_local_dir {db_local_dir}, ndt: {ndt}"
            current_path = os.path.join(self.root_path, self.dt_to_dir(dt), dbn)
            new_path = os.path.join(self.root_path, self.dt_to_dir(dt), dbn)

        if current_path == new_path:
            return

        self.check_flags(key=key, flags=flags, org_path=current_path)

        # Ensure existence, raise error (cannot be fixed by good programming, so no assert)
        if not os.path.exists(current_path):
            raise FileNotFoundError("Original File doesn't exist, cannot rename.")

        if os.path.exists(new_path):
            raise FileExistsError("New Path exists already.")

        # PRECONDITION: File Exists, Filename not present
        os.rename(current_path, new_path)

        self.key_to_filepath_cache.update(arg=key, value=new_path)
        self.prune_fs_dir = True

    def get_media(self, key: int, strict: bool = False):
        """
        Returns a Dataclass which contains the thumbnail path, miniature path and original path.
        """
        # TODO implement

    def get_metadata(self, key: int):
        """
        Returns all metadata of a given key in a dataclass
        """
        # TODO implement

    def get_compare_data(self, key: int | List[int]):
        """
        Get all necessary information to compare images.
        """
        # TODO implement

    # ==================================================================================================================
    # Utility
    # ==================================================================================================================

    # INFO: long-running action
    def create_display_files(self,
                             miniature: bool = True,
                             thumbnail: bool = True,
                             overwrite: bool = False) \
            -> Tuple[int, int]:
        """
        Create thumbnails for all elements in the database.

        :param miniature: If true, create miniature images
        :param thumbnail: If true, create thumbnails images
        :param overwrite: If true, overwrite existing files.

        returns: <number of new files created> and <number of undetected missing files>
        """
        self.add_extra_cursor("update_thumbnails")

        self.debug_execute(stmt="SELECT m.key, m.db_name, m.flags FROM main AS m "
                           # Check present                 check trash                     check duplicate
                           "WHERE mod(m.flags, 2) == 1 AND mod((m.flags >> 2), 2) == 0 AND mod((m.flags >> 8), 2) == 0",
                           cur="update_thumbnails")

        missing: int = 0
        created: int = 0
        for row in self.get_cursor("update_thumbnails"):
            key, dbn, _flags = row

            flags = MainFlags.from_int(_flags)

            # skip missing images or images in trash
            if not flags.present or flags.trashed or flags.duplicate:
                if __debug__:
                    raise ImplementationError("Error in SQL Statement, should not find trash or not present files")
                continue

            fp = self.resolve_key_to_path(key)

            # checking for missing file
            if not os.path.exists(fp):
                # INFO we're not updating the presence in the db because it doesn't fit the scope of this function.
                self.integrity_logger.warning(f"File from DB is missing: {dbn}, in {os.path.dirname(fp)}")
                missing += 1
                continue

            # Thumbnail: write if not exists or exists + overwrite
            if thumbnail:
                if (not os.path.exists(self.full_thumbnail_path(key))
                        or (os.path.exists(self.full_thumbnail_path(key)) and overwrite)):

                    flags.has_thumbnail = self._create_display_file(
                        in_path=fp, out_path=self.full_thumbnail_path(key), major_size=self.config.thumbnail_target)
                    created += 1

                else:
                    self.main_logger.debug(f"Thumbnail already exists for key: {key}")
                    flags.has_thumbnail = True

            # Miniature: write if not exists or exists + overwrite
            if miniature:
                if (not os.path.exists(self.full_miniature_path(key))
                        or (os.path.exists(self.full_miniature_path(key)) and overwrite)):

                    flags.has_miniature = self._create_display_file(
                        in_path=fp, out_path=self.full_miniature_path(key), major_size=self.config.thumbnail_target)
                    created += 1

                else:
                    self.main_logger.debug(f"Miniature already exists for key: {key}")
                    flags.has_miniature = True

            # Update the flags of the given key.
            self.debug_execute(stmt="UPDATE main SET flags = ? WHERE key = ?",
                               args=(flags.to_int(), key))

        self.remove_extra_cursor("update_thumbnails")
        self.commit()
        self.main_logger.info(f"Created: {created} Display Files, found {missing} newly missing")

        missing: int
        created: int
        return created, missing

    def _create_display_file(self, in_path: str, out_path: str, major_size: int) -> bool:
        """
        Create the display file for a given file.

        INFO: File Extensions are treated as final. We do not attempt to cors-parse. We do attempt to generate
            thumbnails for unknown files tho

        :param in_path: Path to input file
        :param out_path: Path to output file
        :major_size: size in px of the larger side of the image.

        :return True if file was successfully created
        """
        # Handle Videos
        if os.path.splitext(in_path)[1] in self.config.video_extensions:
            extract_success = self._create_vid_thumbnails(in_path=in_path, out_path=self.temp_video_path())

            # No need for larger logging info, handled within the internal functions
            if not extract_success:
                return False

            # No need for larger logging info, handled within the internal functions
            suc = self._create_img_thumbnails(in_path=self.temp_video_path(), out_path=out_path, major_size=major_size)
            assert os.path.exists(self.temp_video_path()), "Video file missing despite successfully creating it?"
            os.remove(self.temp_video_path())
            return suc

        # Handle Images
        elif os.path.splitext(in_path)[1] in self.config.image_extensions:
            return self._create_img_thumbnails(in_path=in_path, out_path=out_path, major_size=major_size)

        # Haily Marry Handler
        else:
            self.main_logger.warning(f"Unknown extension: {in_path}. Attempting to to create display file anyway")

            extract_success = self._create_vid_thumbnails(in_path=in_path, out_path=self.temp_video_path())

            new_in_path = self.temp_video_path() if extract_success else in_path

            # No need for larger logging info, handled within the internal functions
            suc = self._create_img_thumbnails(in_path=new_in_path, out_path=out_path, major_size=major_size)

            if extract_success:
                assert os.path.exists(self.temp_video_path()), "Video file missing despite successfully creating it?"
                os.remove(self.temp_video_path())

            return suc

    def _create_img_thumbnails(self, in_path: str, out_path: str, major_size: int) -> bool:
        """
        Create thumbnails for images in the database.

        PRECONDITION: in_path exists
        PRECONDITION: in_path extension is correct.

        :param in_path: Path to the input file
        :param out_path: Path to the output file
        """
        assert os.path.exists(in_path), "Input Path doesnt' exist"

        try:
            # load image from disk, 1 means cv::IMREAD_COLOR
            img = cv2.imread(in_path, cv2.IMREAD_COLOR)

            # determine which axis is larger
            max_pix = max(img.shape[0], img.shape[1])

            # calculate new size
            if max_pix == img.shape[0]:
                py = major_size
                px = max(1, int(major_size / max_pix * img.shape[1]))
            else:
                px = major_size
                py = max(1, int(major_size / max_pix * img.shape[0]))

            img_reduced = cv2.resize(img, (py, px), interpolation=cv2.INTER_AREA)

            cv2.imwrite(out_path, img_reduced)

            return True

        except cv2.error as e:
            self.main_logger.exception(f"OpenCV encountered an error while generating the thumbnail for {in_path}",
                                       exc_info=e)
        except Exception as e:
            self.main_logger.exception(f"Unexpected Exception while generating thumbnail: {e}", exc_info=e)

        return False

    def _create_vid_thumbnails(self, in_path: str, out_path: str, target_time: int = 5):
        """
        Create thumbnails for the videos in the database.

        PRECONDITION: in_path exists
        PRECONDITION: in_path extension is correct.

        :param in_path: Path to the input file
        :param out_path: Path to the output file
        :param target_time: Target time when to take the thumbnail

        :returns: True -> if image was created successfully.
        """
        assert os.path.exists(in_path), "Input Path doesn't exist"
        width = None

        # Probe the file
        try:
            probe_res = ffmpeg.probe(in_path)
        except ffmpeg.Error as e:
            self.main_logger.exception(f"Error Probing File with FFMPEG: {in_path}, "
                                  f"stderr: {e.stderr.decode('utf-8')}, "
                                  f"stdout: {e.stdout.decode('utf-8')}", exc_info=e)
            return False

        except Exception as e:
            self.main_logger.exception(f"Unexpected Exception while Probing File: {in_path}", exc_info=e)
            return False

        # Get target time for the image.
        try:
            if probe_res["streams"][0]["duration"] < target_time:
                self.main_logger.warning("Video to short for default time point where to take thumbnail")
                target_time = probe_res["streams"][0]["duration"] // 2

            # Try to get the width of the stream
            for stream in probe_res["streams"]:
                width = stream.get("width")

                if width is not None:
                    break

        except KeyError:
            self.main_logger.error(f"KeyError: Failed to get time data from probe result of ffmpeg: {in_path}")
        except IndexError:
            self.main_logger.error(f"IndexError: Failed to get time data from probe result of ffmpeg: {in_path}")
        except Exception as e:
            self.main_logger.exception(f"Unexpected error {type(e).__name__}", exc_info=e)

        if width is None:
            self.main_logger.info(f"Failed to retrieve width of the input file: {in_path}, aborting")
            return False

        try:
            (
                ffmpeg
                .input(in_path, ss=target_time)
                .filter('scale', width, -1)
                .output(out_path, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            self.main_logger.exception(f"Error Exporting Thumbnail from video: {in_path}, "
                                  f"stderr: {e.stderr.decode('utf-8')}, "
                                  f"stdout: {e.stdout.decode('utf-8')}", exc_info=e)
            return False
        except Exception as e:
            self.main_logger.exception(f"Unexpected Exception while writing thumbnail: {type(e).__name__}", exc_info=e)
            return False

        return True

    def move_to_replaced(self, child_key: int, parent_key: int, copy_google_metadata: bool = True):
        """
        Move a duplicate into the replaced table.

        - Ensure no duplicate chaining
        - Original, Thumbnail, Miniature Deleted, can be taken from parent
        - Attributes are transferred into the replaced table.
        - Need to remove mentions in duplicates and known_duplicates table.

        :param child_key: The key of the entry in the main table which will become the child in the replaced table
        :param parent_key: The key of the file which will be newly the parent.
        :param copy_google_metadata: Copy the Google Metadata from the child to the parent if the parent doesn't have
            Google Metadata
        """
        # Ensure both keys exist.
        self.debug_execute("SELECT key, flags, google_metadata FROM main WHERE key = ?", (parent_key,))
        raw_parent = self.sq_cur.fetchone()

        if raw_parent is None:
            raise ValueError("Parent Key doesn't exist")

        parent_flags = MainFlags.from_int(raw_parent[1])
        parent_google_metadata = raw_parent[2]

        self.debug_execute(stmt="SELECT key, m.google_metadata, m.flags, m.db_name FROM main AS m WHERE m.key = ?",
                           args=(child_key,))

        result = self.sq_cur.fetchone()
        if result is None:
            raise ValueError("Child Key doesn't exist")

        # INFO: Warning User, shouldn't really be occurring, since trashed shouldn't be able to be deduplicated
        if parent_flags.trashed:
            self.main_logger.warning(f"Marking File as Duplicate with Parent in Trash")

        if not parent_flags.present:
            self.main_logger.warning("Marking File as Duplicate without Parent file being present")

        # Unpack result for ease of use
        _, _flags, google_metadata, db_name = result
        main_flags = MainFlags.from_int(_flags)

        # Cannot update if the file is already duplicate
        if main_flags.duplicate:
            raise ValueError("File is already duplicate")
        main_flags.duplicate = True

        # Check children in replaced table
        self.debug_execute("SELECT COUNT(*) FROM main WHERE parent = ?", args=(child_key,))
        count = self.sq_cur.fetchone()[0]

        if count > 0:
            self.main_logger.info(f"Updating {count} children of this entry")

            self.debug_execute("UPDATE main SET parent = ? WHERE parent = ?", (parent_key, child_key))

        # Check Entries in duplicates table and known_duplicates table
        self._migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=False)
        self._migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=True)

        # Marking row as duplicate in metadata table
        self.debug_execute("UPDATE metadata SET replaced = 2 WHERE key = ?", (child_key,))

        # Update file system
        fp = self.resolve_key_to_path(child_key)

        # Checking consistency between FS and DB
        self.check_flags(key=child_key, flags=main_flags, miniature=True, thumbnail=True, org_path=fp)

        # Take care of three kinds of files.
        if os.path.exists(fp):
            self.main_logger.debug("Moving Original File to Trash")
            os.rename(fp, os.path.join(self.get_trash_dir(), db_name))

        # Setting present flag based on path in trash
        main_flags.present = os.path.exists(os.path.join(self.get_trash_dir(), db_name))

        # Remove Thumbnail
        if os.path.exists(self.full_thumbnail_path(child_key)):
            self.main_logger.debug(f"Deleting Thumbnail {self.thumbnail_name(child_key)}")
            os.remove(self.full_thumbnail_path(child_key))

        # Remove Miniature
        if os.path.exists(self.full_miniature_path(child_key)):
            self.main_logger.debug(f"Deleting Miniature {self.miniature_name(child_key)}")
            os.remove(self.full_miniature_path(child_key))

        # Copy the Google photos metadata to the parent.
        if copy_google_metadata and parent_google_metadata is None and google_metadata is not None:
            parent_flags.org_google_metadata = False
            self.debug_execute("UPDATE main SET google_metadata = ?, flags = ? WHERE key = ?",
                               (google_metadata, parent_flags.to_int(), parent_key))

        self.debug_execute("UPDATE main SET parent = ? WHERE key = ?", (parent_key, child_key))

        # TODO Darktable???
        self.prune_db_dir()
        self.prune_gps()
        self.prune_fs_dir = True
        # TODO clear presence, hash, filename
        self.key_to_filepath_cache.update(arg=child_key, value=os.path.join(self.get_trash_dir(), db_name))

        self.clear_presence_table()
        self.commit()

    def move_to_trash(self, key: int):
        """
        Move a given image to trash.

        - Checks the file exists
        - Creates Thumbnail and Miniature
        - Moves the original file to the trash
        - Updates the flags of the file.
        """
        self.debug_execute(stmt="SELECT key, db_name, flags  FROM main WHERE key = ?",
                           args=(key,))
        _raw_res = self.sq_cur.fetchone()

        if _raw_res is None:
            raise ValueError(f"Key {key} not found in main table.")

        # Parse the row
        k, dbn, _flags = _raw_res
        main_flags = MainFlags.from_int(_flags)

        if main_flags.trashed:
            raise ValueError("File is already in Trash")

        if main_flags.duplicate:
            raise ValueError("File is Duplicate")

        # Get the paths
        current_path = self.resolve_key_to_path(key)
        target_path = os.path.join(self.get_trash_dir(), dbn)

        # Store existence in flags
        main_flags.present = os.path.exists(current_path)

        # TODO darktable
        if main_flags.present:
            assert os.path.exists(current_path), "Upper Condition wrong"

            # Create thumbnail
            self.main_logger.debug("Creating Thumbnail for image going into Trash")
            main_flags.has_thumbnail = self._create_display_file(in_path=current_path,
                                                                 out_path=self.full_thumbnail_path(key),
                                                                 major_size=self.config.thumbnail_target)
            # Creating miniature
            self.main_logger.debug("Creating Miniature for image going into Trash")
            main_flags.has_miniature = self._create_display_file(in_path=current_path,
                                                                 out_path=self.full_miniature_path(key),
                                                                 major_size=self.config.miniature_target)
            # Attempt the move the file
            self.main_logger.debug(f"Moving {current_path} to {target_path}")
            os.rename(current_path, target_path)

        # Set the presence flag and trash flag.
        main_flags.present = os.path.exists(target_path)
        main_flags.trashed = True

        # All things done, update the flags and write the db, update the metadata table.
        self.debug_execute("UPDATE main SET flags = ? WHERE key = ?", (main_flags.to_int(), key))
        self.debug_execute("UPDATE metadata SET replaced = 1, db_dir = NULL WHERE key = ?", (key,))

        self.prune_db_dir()
        self.prune_fs_dir = True

        self.key_to_filepath_cache.update(arg=key, value=target_path)

        # TODO clear presence, hash, filenaem
        self.clear_presence_table()
        self.commit()

    def restore_replaced(self, key: int, create_disp_filey: bool = True):
        """
        Moves file back to original location
        Updates the metadata table.

        Only works if delete_trash wasn't called already
        """
        # TODO implement

    def restore_trash(self, key: int, create_disp_filey: bool = True):
        """
        Move file back from trash to its original location
        Updates Metadata Table

        Only works if delete_trash wasn't called already
        """
        # TODO implement

    def delete_trash_thumb(self, key: Union[List[int], int, None]) -> int:
        """
        Delete the remaining thumbnail of an image in the trash. For recognition purposes, the thumbnails of the
        trashed images are retained by default. Use this function with care.

        :param key: Key to delete, list of keys to delete, or delete all thumbnails of images in the trash with None
        """
        count: int = 0

        self.add_extra_cursor("del_trash_thumb")
        # Everything in the trash
        if key is None:
            stmt = "SELECT key, flags FROM main WHERE mod(flags >> 2, 2) == 1"
            args = tuple()
        elif isinstance(key, int):
            stmt = f"SELECT key, flags FROM main  WHERE key = ? AND mod(flags >> 2, 2) == 1"
            args = (key, )
        elif isinstance(key, list):
            stmt = f"SELECT key, flags FROM main  WHERE key IN ? AND mod(flags >> 2, 2) == 1"
            args = (f"({', '.join(map(str, key))})", )
        else:
            raise TypeError(f"Unexpected Type for Key: {type(key).__name__}")

        self.debug_execute(stmt, args, "del_trash_thumb")

        for row in self.get_cursor("del_trash_thumb"):
            key, _flags = row
            flags = MainFlags.from_int(_flags)

            if os.path.exists(self.full_thumbnail_path(key)):
                self.main_logger.debug(f"Deleting Thumbnail for image in trash: {key}")
                os.remove(self.full_thumbnail_path(key))
                flags.has_thumbnail = False
                count += 1

            if os.path.exists(self.full_miniature_path(key)):
                self.main_logger.debug(f"Deleting Miniature for image in trash: {key}")
                os.remove(self.full_thumbnail_path(key))
                flags.has_miniature = False
                count += 1

            self.debug_execute("UPDATE main SET flags = ? WHERE key = ?",
                               (flags.to_int(), key))

        self.remove_extra_cursor("del_trash_thumb")
        self.commit()
        return count

    # INFO: long-running action
    def compress(self) -> int:
        """
        Remove all files which can be recomputed to save space. Removes all Thumbnails and all temporary files
        generated for deduplication.
        """
        count: int = 0
        self.main_logger.info("Compressing Database, deleting temp files.")

        # Remove temporary files, should they exist.
        content = os.listdir(self.get_temp_dir())
        for entry in content:
            if os.path.isdir(os.path.join(self.get_temp_dir(), entry)):
                self.main_logger.debug(f"Deleting {entry}")
                shutil.rmtree(os.path.join(self.get_temp_dir(), entry))

            else:
                self.main_logger.debug(f"Deleting {entry}")
                os.remove(os.path.join(self.get_temp_dir(), entry))

        # Remove display files:
        self.main_logger.info(f"Deleting Thumbnails of existing images.")
        self.add_extra_cursor("rm_disp_media")
        self.debug_execute("SELECT key, flags, db_name FROM main "
                           # Check present = 1,            Check trash = 0           check duplicate = 0
                           "WHERE mod(flags, 2) = 1 AND mod(flags >> 2, 2) = 0 AND mod(flags >> 8, 2) = 0",
                           cur="rm_disp_media")

        for row in self.get_cursor("rm_disp_media"):
            key, _flags, db_name = row
            flags = MainFlags.from_int(_flags)

            assert flags.trashed is False and flags.duplicate, "SQL Error, Trashed should be false."
            file_path = self.resolve_key_to_path(key)

            # Skip if the original is not present
            self.check_flags(key=key, flags=flags, miniature=True, thumbnail=True,
                             org_path=file_path)

            if not os.path.exists(file_path):
                continue

            # PRECONDITION: The original file exists in the database.
            if os.path.exists(self.full_thumbnail_path(key)):
                self.main_logger.debug(f"Deleting '{self.thumbnail_name(key)}'")
                os.remove(self.full_thumbnail_path(key))
                flags.has_thumbnail = False
                count += 1

            if os.path.exists(self.full_miniature_path(key)):
                self.main_logger.debug(f"Deleting '{self.miniature_name(key)}'")
                os.remove(self.full_miniature_path(key))
                flags.has_miniature = False
                count += 1

            self.debug_execute("UPDATE main SET flags = ? WHERE key = ?",
                               (flags.to_int(), key))

        self.remove_extra_cursor("rm_disp_media")
        self.commit()
        self.main_logger.info(f"Finished Deleting {count} Display Media of existing images.")
        return count

    def empty_trash(self):
        """
        Removes all originals from the trash.
        """
        self.main_logger.info(f"Emptying all Trashed files...")
        trash = self._empty_trash(duplicates=False)
        replaced = self._empty_trash(duplicates=True)
        self.main_logger.info(f"Deleted a total of {trash + replaced} files from trash.")
        return trash + replaced

    def _empty_trash(self, duplicates: bool) -> int:
        """
        Internal function to remove originals from one of two categories of files in the trash:
        - Files which are marked as 'trashed'
        - Files which are duplicates and the originals were moved to trash

        :param duplicates: if true, delete files from replaced table else remove files marked as 'trashed'
        """
        count: int = 0

        self.add_extra_cursor("del_trash")
        if duplicates:
            self.debug_execute(stmt="SELECT key, db_name, flags FROM main WHERE mod(flags >> 8, 2) = 1",
                               cur="del_trash")
            update_stmt = "UPDATE replaced SET flags = ? WHERE key = ? "
        else:
            self.debug_execute(stmt="SELECT key, db_name, flags FROM main WHERE mod(flags >> 2, 2) = 1",
                               cur="del_trash")
            update_stmt = f"UPDATE main SET flags = ? WHERE key = ?"

        self.main_logger.info(f"Deleting Originals from Files in {'Duplicates' if duplicates else 'Trash'}")

        # Remove originals from files marked as trash
        for row in self.get_cursor("del_trash"):
            key, db_name, _flags = row
            flags = MainFlags.from_int(_flags)

            # Check for consistency
            if __debug__:
                if duplicates and flags.duplicate is False:
                    raise ImplementationError("Didn't receive duplicate file despite call for it")
                if not duplicates and flags.trashed is False:
                    raise ImplementationError("Didn't receive trashed file despite call for it")

            # TODO darktable
            file_path = self.resolve_key_to_path(key)
            self.check_flags(key=key, flags=flags, org_path=file_path)

            if os.path.exists(file_path):
                self.main_logger.debug(f"Deleting {db_name} from trash")
                os.remove(file_path)
                count += 1
                self.debug_execute(update_stmt, (flags.to_int(), key))

            flags.present = False

            # Removing row in metadata table.
            self.debug_execute("DELETE FROM metadata WHERE main_key = ?", (key,))

        self.main_logger.info(f"Finished Deleting {count} Originals {'Duplicates' if duplicates else 'Trash'}")
        self.remove_extra_cursor("del_trash")
        self.commit()
        # INFO: Don't need to update the caches, the path isn't modified.
        return count

    def forget_file(self, key: int):
        """
        Forgets a given file.

        Removes it from all tables and removes all children. Images which are forgotten, will be not be detected
        upon import and will be reimported if the given image shows up again.

        Removes Hash association to duplicate children.
        Removes Hash association in parent in main table
        Removes GPS to main entry
        Removes thumbnails of main entry and children
        Removes miniatures of main entry and children
        Removes original of the main entry
        Removes entries from duplicates and known duplicates table
        Prunes empty hashes
        Prunes empty gps_locs
        Prunes empty db_dirs
        """
        self._internal_forget(key=key)

    def _internal_forget(self, key: int, rec: bool = False):
        """
                Forgets the image in  main table:

        Removes it from all tables and removes all children. Images which are forgotten, will be not be detected
        upon import and will be reimported if the given image shows up again.

        Removes Hash association to children in replaced table
        Removes Hash association in parent in main table
        Removes GPS to main entry
        Removes thumbnails to main or replaced
        Removes miniatures to main or replaced
        Removes original from main or replaced
        Removes entries from duplicates and known duplicates table
        Prunes empty hashes
        Prunes empty gps_locs
        Prunes empty db_dirs
        """
        self.debug_execute("SELECT m.db_name, m.flags FROM main AS m WHERE m.key = ?", (key, ))
        row = self.sq_cur.fetchone()
        if row is None:
            raise ValueError("Key not found in main table")

        # Removing all children in replaced
        self.debug_execute("SELECT key FROM main WHERE parent = ?", (key,))
        children = [r[0] for r in self.sq_cur.fetchall()]

        if rec and len(children) > 0:
            raise CorruptDatabase("Got Entry where the children have children.")

        # Remove children
        for k in children:
            self._internal_forget(key=k, rec=True)

        # Parse the row
        db_name, _flags = row
        flags = MainFlags.from_int(_flags)

        # TODO darktable
        # Remove files
        fp = self.resolve_key_to_path(key)
        self.check_flags(key=key, flags=flags, miniature=True, thumbnail=True, org_path=fp)

        if rec and not flags.duplicate:
            self.main_logger.warning("Child found who's duplicate flag wasn't set.")

        if os.path.exists(fp):
            # Logging message
            if flags.trashed or flags.duplicate:
                self.main_logger.debug(f"Deleting {db_name} from trash directory")
            else:
                self.main_logger.debug(f"Deleting {db_name} from main database")

            # Actually removing the file
            os.remove(fp)

        # PRECONDITION: The original has been deleted.
        # Deleting thumbnail and miniature if they exist.
        if os.path.exists(self.full_miniature_path(key)):
            self.main_logger.debug(f"Deleting {self.miniature_name(key)} from thumbnails")
            os.remove(self.full_miniature_path(key))

        if os.path.exists(self.full_thumbnail_path(key)):
            self.main_logger.debug(f"Deleting {self.thumbnail_name(key)} from thumbnails")
            os.remove(self.full_thumbnail_path(key))

        # Remove hashes of parent
        self.debug_execute("DELETE FROM hash_assoz WHERE file_key = ?", (key,))

        # Remove row from metadata
        self.debug_execute("DELETE FROM metadata WHERE main_key = ?", (key,))

        # Removing files from the duplicates table
        c_known = self.remove_all_tuples_with_key(key=key, known=True)
        self.main_logger.debug(f"Deleted {c_known} tuples from known_duplicates table")
        c_default = self.remove_all_tuples_with_key(key=key, known=False)
        self.main_logger.debug(f"Deleted {c_default} tuples from default table")

        # Finally deleting the main row
        self.debug_execute("DELETE FROM main WHERE key = ?", (key,))
        self.commit()

        # Doesn't make sense to call the same clean-up after every child.
        if not rec:
            # Prune dir, hash, gps
            self.mark_import_table_as_stale()
            self.prune_hash()
            self.prune_gps()
            self.prune_db_dir()
            self.prune_fs_dir = True
            self.commit()

        # Clearing Cache
        self.key_to_filepath_cache.evict(key)
        self.filename_to_key_cache.evict(db_name)

        # Print info
        if not rec:
            self.main_logger.info(f"Forgot {key} and children successfully")
        else:
            self.main_logger.info(f"Forgot duplicate {key} successfully")

    # INFO: long-running action
    def check_and_update_disp_files(self, selection: Selection = None) -> Tuple[int, int, int, int, int, int]:
        """
        Go through db and check the mark for thumbnail and a thumbnail existing are correct.

        About the return value:

        - Prefix 'missing' means, the flag specifies the file to be present but the file is missing on the file system.
        - Prefix 'present' means, the flag specifies the file to be absent but the file is present on the file system.
        - Prefix 'correct' means, the flag and the file system are consostent.

        :param selection: Use a given selection to check the consistency of the flags of thumbnails, otherwise check
            all thumbnails

        :returns: missing_thumbnails, present_thumbnails, correct_thumbnails, missing_miniatures, present_miniatures,
            correct_miniatures
        """
        missing_thumb = missing_min = present_thumb = present_min = correct_thumb = correct_min = 0
        self.add_extra_cursor("check_disp_files")
        if selection is not None:
            if selection.selection_type == SelectionType.SELECTION_A:
                self.debug_execute(stmt="SELECT key, flags FROM main WHERE mod(flags >> 4, 2) = 1",
                                   cur="check_disp_files")
            elif selection.selection_type == SelectionType.SELECTION_B:
                self.debug_execute(stmt="SELECT key, flags FROM main WHERE mod(flags >> 5, 2) = 1",
                                   cur="check_disp_files")
            elif selection.selection_type == SelectionType.TIME_RANGE:
                # TODO test
                self.debug_execute(stmt="SELECT key, flags FROM main "
                                        "WHERE datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?)",
                                   args=(selection.start.isoformat(), selection.end.isoformat()),
                                   cur="check_disp_files")
            else:
                raise ImplementationError("Uncovered Type of SelectionType")
        else:
              self.debug_execute(stmt="SELECT key, flags FROM main",
                                 cur="check_disp_files")

        for key, _flags in self.get_cursor("check_disp_files"):
            flags = MainFlags.from_int(_flags)
            update: bool = False

            self.check_flags(key=key, flags=flags, miniature=True, thumbnail=True)

            # Updating Thumbnail Flag
            if flags.has_thumbnail and not os.path.exists(self.full_thumbnail_path(key)):
                missing_thumb += 1
                flags.has_thumbnail = False
                update = True
            elif not flags.has_thumbnail and os.path.exists(self.full_thumbnail_path(key)):
                present_thumb += 1
                flags.has_thumbnail = True
                update = True
            else:
                correct_thumb += 1

            # Check Miniature Flag
            if flags.has_miniature and not os.path.exists(self.full_miniature_path(key)):
                missing_min += 1
                flags.has_miniature = False
                update = True
            elif not flags.has_miniature and os.path.exists(self.full_miniature_path(key)):
                present_min += 1
                flags.has_miniature = True
                update = True
            else:
                correct_min += 1

            # Update flags if they changed.
            if update:
                self.debug_execute("UPDATE main SET flags = ? WHERE key = ?", (flags.to_int(), key))

        self.main_logger.info(f"Found {missing_thumb} missing thumbnails and {present_thumb} present thumbnails.")
        self.main_logger.info(f"{correct_thumb} flags for thumbnails were correct")
        self.main_logger.info(f"Found {missing_min} missing miniatures and {present_min} present miniatures.")
        self.main_logger.info(f"{correct_min} miniatures for thumbnails were correct")

        self.remove_extra_cursor("check_disp_files")
        return missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min

    # ==================================================================================================================
    # Lookup Methods
    # ==================================================================================================================

    def resolve_key_to_path(self, key: int) -> str | None:
        """
        Get the original filepath for media file. Path doesn't need to exist.

        :param key: The key to resolve.

        :returns: Path to the original file,
        """
        res = self.key_to_filepath_cache.get(key)

        # Path is not in cache, resolve using db, store in cache and return value
        if res is nd:
            path = self._db_resolve_key_to_abs_path(key)
            self.key_to_filepath_cache.set(key, path)
            return path

        return res

    def filename_to_key(self, fname: str) -> int | None:
        """
        Resolve a filename to key
        """
        res = self.filename_to_key_cache.get(fname)

        # Key not in cache, resolve using db, store in cache and return value
        if res is nd:
            key = self._db_resolve_filename_to_key(fname)
            self.filename_to_key_cache.set(fname, key)
            return key

        return res

    @staticmethod
    def exif_tag_creator(dt: datetime.datetime) -> dict[str, str]:
        """
        Create a dict of
        """
        assert dt.tzinfo is not None, "Need a timezone aware object inside database"
        return {"EXIF:ModifyDate": dt.strftime("%Y:%m:%d %H:%M:%S"),
                "EXIF:OffsetTime": dt.strftime("%z")}

    def get_db_file_path(self, config: Config = None):
        """
        Resolve the db_file to an absolute path
        """
        config = self.config if config is None else config
        if os.path.isabs(config.db_file):
            return config.db_file
        else:
            return os.path.abspath(os.path.join(self.root_path, config.db_file))


class RemedyPhotoDB(PhotoModel):
    """
    A specific instance I need to migrate some remaining images, which are only available in older databases into this
    one.
    """

    def import_other_db(self):
        """
        Functionality needed because some images are only on older dbs including their metadata.
        """
        ...
