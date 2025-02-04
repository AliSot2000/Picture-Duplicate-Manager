import datetime
import filecmp
import json
import logging
import multiprocessing.connection as connection
import os.path
import shutil
import sys
from typing import Set, Dict, List, Union, Tuple, Optional
from zoneinfo import ZoneInfo

import cv2
import ffmpeg

import photo_lib.defaults as defaults
from photo_lib.custom_enum import GroupingCriterion, DBLocation, NewMatchTypes
from photo_lib.cache import Cache, nd
from photo_lib.config import Config
from photo_lib.db_definitions import current_version, history, StaticDeclaration, GenericDeclaration
from photo_lib.errors_and_warnings import ImplementationError, CorruptDatabase, RareOccurrence
from photo_lib.flag_dataclasses import MainFlags, ReplacedFlags
from photo_lib.metadata_aggregator.config import DoubleKey
from photo_lib.metadata_aggregator.enums import DateTimeSource
from photo_lib.metadata_aggregator.new_metadata_aggregator import NewMetadataAggregator
from photo_lib.sqlite_wrapper import BaseSQliteDB


class PhotoDB(BaseSQliteDB):
    __verified: bool = False
    config: Config

    root_path: str

    static_decls: Dict[str, StaticDeclaration]
    generic_decls: Dict[str, GenericDeclaration]

    __reserved_names: List[str] = ["<temp>"]

    # Redefining logger as mandatory
    main_logger_name: str = "PhotoDB"
    integrity_logger_name: str = "PhotoDB.integrity"
    metadata_aggregator_name: str = "PhotoDB.MetadataAggregator"
    metadata_aggregator_parsing_name: str = "PhotoDB.MetadataAggregator.Parsing"
    main_logger: logging.Logger
    integrity_logger: logging.Logger

    # Flags
    prune_fs_dir: bool = False

    mda: Optional[NewMetadataAggregator] = None

    # Caches
    filename_to_key_cache: Cache
    key_to_filepath_cache: Cache

    @property
    def reserved_names(self):
        return self.__reserved_names

    @property
    def temp_db_name(self):
        return self.__reserved_names[0]

    @property
    def current_version(self):
        return current_version.current_version

    def __init__(self,
                 root_path: str,
                 init: bool = False,
                 config: Config = None,
                 init_loggers: bool = True):
        """
        Construct a Database Object from a preexisting database file.
        """
        self.main_logger = logging.getLogger(self.main_logger_name)
        self.integrity_logger = logging.getLogger(self.integrity_logger_name)
        if init_loggers:
            self.set_logging_defaults()

        self.filename_to_key_cache = Cache(size=1024)
        self.key_to_filepath_cache = Cache(size=1024)

        self.build_definition_lookup()
        self.root_path = os.path.abspath(root_path)
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

            with open(os.path.abspath(cfg_path), "w") as f:
                f.write(config.model_dump_json())

            self.config = config

        assert hasattr(self, "config") and self.config is not None, "Config must be populated by now"

        # PRECONDITION: Config defined
        super().__init__(self.config.db_file)

        if init:
            self.init_db()
        else:
            self.verify_version()

    def reload_loggers(self):
        """
        Get the loggers from the class attributes

        attr: main_logger_name for main_logger
        attr: integrity_logger_name for integrity_logger
        """
        self.main_logger = logging.getLogger(self.main_logger_name)
        self.integrity_logger = logging.getLogger(self.integrity_logger_name)

    def set_logging_defaults(self):
        """
        Set Defaults of loggers.
        """
        # Level
        self.main_logger.setLevel(logging.DEBUG)
        self.integrity_logger.setLevel(logging.DEBUG)

        # Propagate
        self.integrity_logger.propagate = True
        self.main_logger.propagate = False

        # Define handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        self.main_logger.addHandler(handler)

    def cleanup(self):
        """
        Besides writing to file, perform some checks and pruning operations
        """
        if self.prune_fs_dir:
            self.prune_filesystem_directories()

        self.basic_integrity_check()
        self.cleanup()

    def add_default_metadata_aggregator(self):
        """
        Add a default metadata aggregator (user could provide a custom MDA if he so chooses)
        """
        self.mda = NewMetadataAggregator(
            logger=logging.getLogger("MetadataAggregator"),
            discover_logger=logging.getLogger("MetadataAggregator.Parsing"),
            use_dateutil=True,
            datetime_fmt=self.config.datetime_fmt
        )

    # ==================================================================================================================
    # Table Creation & Deletion & Modify Functions
    # ==================================================================================================================

    def init_db(self):
        """
        Create all tables from
        """
        self.main_logger.info("Initializing Database")

        for short_name, decl in self.static_decls.items():
            self.main_logger.info(f"Creating {short_name}")

            self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, decl.name))

        self.main_logger.info("Initialization Complete")

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

    def _add_import_table(self, root_path: str, name: str = None, description: str = None):
        """
        Add a new import table to the database.

        PRECONDITION: The table doesn't exist.

        :param root_path: dir_root from which to import
        :param name: The name of the table. Override, defaults to dirname(root_path) + hash(current_datetime)
        :param description: The description of the table. Override, defaults to None

        :raises sqlite.IntegrityError: if that import table already exists.
        """
        # Default Name
        if name is None:
            tbl_name = (os.path.dirname(os.path.abspath(root_path))
                        + str(hash(datetime.datetime.now(datetime.timezone.utc))))
        else:
            tbl_name = name

        # Check name Length
        if len(tbl_name) > 120:
            tbl_name = tbl_name[:120]
            self.main_logger.warning(f"Table Name longer than 120 characters. Truncating to: `{tbl_name}`")

        # Add the table to the generic lookup table
        self.debug_execute("INSERT INTO import_tables (root_path, table_name, table_description) VALUES (?, ?, ?)",
                           (root_path, tbl_name, description))

        # Actually creating table
        decl = self.generic_decls["import_table"]
        self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, tbl_name))
        self.commit()
        return tbl_name

    def import_table_exists(self, name: str = None) -> bool:
        """
        Check if a given name with root_path and name exists already.
        """
        self.debug_execute("SELECT key FROM import_tables WHERE  name = ?", ( name))
        return self.sq_cur.fetchone() is not None

    def remove_import_table(self, name: str = None) -> Tuple[bool, bool]:
        """
        Remove a specific import table from the database.

        :returns: True -> Successfully deleted table, successfully removed entry from generic lookup table
        """
        # Check if the table existed.
        self.debug_execute("SELECT sql FROM sqlite_master WHERE name IS ?", (name,))
        del_table = self.sq_cur.fetchone() is not None

        # Drop the table with "if exists" just to be sure
        self.debug_execute(f"DROP TABLE IF EXISTS `{name}`")

        self.debug_execute("SELECT key FROM import_tables WHERE table_name IS ?", (name,))
        del_row = self.sq_cur.fetchone() is not None

        self.debug_execute("DELETE FROM import_tables WHERE table_name IS ?", (name,))
        return del_table, del_row

    def mark_import_table_as_stale(self, key: int = None):
        """
        Update either single import table or all import tables (if no key is provided) as stale.

        Stale indicates that the references in the table to the main database are no longer guaranteed to hold, so a
        reference might have been moved tables, or moved to trash or forgotten.
        """
        if key is None:
            # The stale flags is bit 1,
            # And we only update the flags by adding a +1 if that flag hasn't already been set mod(flags, 2) == 0
            stmt = "UPDATE import_tables SET flags = flags + 1 WHERE key = ? AND mod(flags, 2) == 0"
            args = (key,)
        else:
            # Update all tables to be stale if they aren't already.
            stmt = "UPDATE import_tables SET flags = flags + 1 WHERE mod(flags, 2) == 0"
            args = tuple()

        self.debug_execute(stmt, args)
        self.commit()

    # ==================================================================================================================
    # Tabular Integrity checks
    # ==================================================================================================================

    def verify_version(self):
        """
        Check the version of the photo database. Raise Error, if it doesn't match and allow for conversion.
        """
        # Check the config
        self._check_config()

        # Check the tables
        self._verify_tables()

    def _check_config(self):
        """
        Check the config is valid and contains everything needed. Future proofing. Not needed at the moment.
        """
        # INFO: This function is a placeholder needed in case bigger changes to the config come and need to be
        #  accounted for. Cases like the config is updated and the db is not, or the other way around, ...
        pass

    def _verify_tables(self) -> bool:
        """
        Go through all tables and check their definitions

        INFO: Function will remove orphaned rows in the generic lookups table.

        :return: True if all tables were verified and have the correct definitions
        """
        for name, decl in self.static_decls.items():
            self.debug_execute("SELECT sql FROM sqlite_master WHERE name = ?", (decl.name,))
            result = self.sq_cur.fetchone()

            # No result found, return, do not update verified.
            if result is None:
                return False

            if not result[0] == decl.declaration_string.replace(decl.name_placeholder, decl.name):
                return False

        # INFO Poor convention: the key of the generic decls is also the name of a table which contains a list of all
        #  tables which follow the generic definition. The table who's name is the key, must have a column
        #  table_name and key
        for name, decl in self.generic_decls.items():
            self.debug_execute(f"SELECT key, table_name FROM `{name}`")
            results = self.sq_cur.fetchall()

            for key, table in results:
                self.debug_execute(f"SELECT sql FROM sqlite_master WHERE name = ?", (table,))
                result = self.sq_cur.fetchone()

                if result is None:
                    self.integrity_logger.warning(f"Found orphaned entry: {table} in the parent table: {name}. "
                                                  f"Deleting orphaned entry")

                    self.debug_execute(f"DELETE FROM `{name}` WHERE key = ?", (key,))

                if not result[0] == decl.declaration_string.replace(decl.name_placeholder, table):
                    return False

        self.__verified = True
        return True

    def build_definition_lookup(self):
        """
        Get all defined versions and build lookup of the versions.

        Use a sorted list of the previous declarations of the versions and walk backwards until all declarations names
        have an associated value.

        Populates the attr(static_decls) and attr(generic_decls)
        """
        temp_static: Dict[str, StaticDeclaration | None] = {key: None
                                                            for key in current_version.all_definitions}
        temp_generic: Dict[str, GenericDeclaration | None] = {key: None
                                                              for key in current_version.all_generic_definitions}

        # Build the table lookups from the current version.
        for key, value in current_version.definitions.items():
            temp_static[key] = value

        for key, value in current_version.generic_definitions.items():
            temp_generic[key] = value

        history_index = 0

        # check all values have been populated.
        while not all(list(temp_static.values()) + list(temp_generic.values())):
            db_declaration = history.history[history_index]

            empty_static = []
            empty_generic = []

            # Get the list of keys of empty keys in the temp variables
            for key, value in temp_static.items():
                if value is None:
                    empty_static.append(key)

            for key, value in temp_generic.items():
                if value is None:
                    empty_generic.append(key)

            # Try to populate from the currently selected historical version
            for key in empty_static:
                temp_static[key] = db_declaration.definitions.get(key)

            for key in empty_generic:
                temp_generic[key] = db_declaration.generic_definitions.get(key)

            # Update the Index after the current iteration.
            history_index += 1

        assert all(list(temp_static.values()) + list(temp_generic.values())), "All Declarations were filled."

        # Check that all generic decls have a table containing the list of the generic tables
        parent_tables = {key: False for key in current_version.all_generic_definitions}
        for key, value in temp_static.items():
            if value.name in parent_tables.keys():
                parent_tables[value.name] = True

        if not all(list(parent_tables.values())):
            raise ImplementationError("Not all generic tables have a parent table. Error in Table Definitions.")

        self.static_decls = temp_static
        self.generic_decls = temp_generic

    def basic_integrity_check(self):
        """
        Basic sanity checks on the db to ensure we don't get corrupt data.
        """

        # - Check that no key appears both in main and replaced
        # - Check that file_keys in the hash_assoz table have a matching entry in replaced or main
        # - Check that all entries in main and replaced have a hash
        # - Check no filename appears twice in replaced and main table
        # - Check no entries in main table with reserved db_name
        pass

    # ==================================================================================================================
    # DB Integrity checks and utility
    # ==================================================================================================================

    def update_hash_from_filename(self, fname: Dict[str, str]):
        """
        Updates the hash of the image file with the given file name.
        """
        ...

    def update_filename_from_hash(self, new_names: Dict[int, str]):
        """
        Update the names of files resolved through hash and filesize.
        """
        ...

    def update_trash_from_presence(self, from_select: bool = False):
        """
        Update the files which have aren't present to have been moved to the trash.

        :param from_select: Use the selection marker to only affect those files.
        """
        ...

    def check_presence(self, from_select: bool = False):
        """
        Go through db and check that all files in the db are present in the file system.

        :param from_select: Use selection marker of images to check changed hashes for those images.
        """
        ...

    def check_filenames(self, from_select: bool = False):
        """
        Check the file names by associating file hashes from files found in the db with files
        """
        ...

    def check_file_hashes(self, from_select: bool = False):
        """
        Check the file hashes based on the file names and add them to a list of table.s
        """
        ...

    def prune_hash(self) -> int:
        """
        Remove all rows in the hash table which are no longer referenced

        :return: Number of rows removed
        """
        self.debug_execute("SELECT COUNT(key) FROM hashes AS h WHERE h.key NOT IN (SELECT hash_key FROM hash_assoz)")
        count = self.sq_cur.fetchone()[0]

        self.debug_execute("DELETE FROM hashes WHERE key NOT IN (SELECT hash_key FROM hash_assoz)")
        if count > 0:
            self.main_logger.info(f"Pruned {count} rows in hash table")
        else:
            self.main_logger.debug("Call to prune_hash, no hashes pruned")
        return count

    def prune_gps(self) -> int:
        """
        Remove all rows in the gps table which are no longer referenced

        :return: Number of rows removed
        """
        self.debug_execute("SELECT COUNT(key) FROM gps_location WHERE key NOT IN (SELECT gps_location FROM main)")
        count = self.sq_cur.fetchone()[0]

        self.debug_execute("DELETE FROM gps_location WHERE key NOT IN (SELECT gps_location FROM main)")
        if count > 0:
            self.main_logger.info(f"Pruned {count} rows in gps table")
        else:
            self.main_logger.debug(f"Call to prune_gps, no rows pruned")
        return count

    def prune_dir(self) -> int:
        """
        Remove all entries and all directories form the database which are no longer referenced
        """
        self.debug_execute("SELECT key, db_local_dir FROM db_dir WHERE key NOT IN (SELECT db_dir FROM main)")
        # TODO Darktable

        # INFO: A db_local_dir can share a partial path with other directories, for example
        #   Assume you had an event spanning a weekend and it's in a given month, so what you want is to store it in
        #   root_dir/YYYY/MM/event-name/. Deleting the db_local_dir i.e. ['YYYY', 'MM', 'event-name'] will attempt to
        #   remove the lowest node tree and then go up and attempt to remove all upper nodes and remove those as well
        #   if they are empty.
        keys_to_delete = []
        for raw in self.sq_cur:
            ktd = raw[0]
            db_local_dir = self.parse_db_local_dir(raw[1])

            first = True
            for i in range(len(db_local_dir)):
                tgt_dir = os.path.join(self.root_path, *db_local_dir[:len(db_local_dir ) - i])
                if not os.path.exists(tgt_dir):
                    continue

                # path exists
                if os.listdir(tgt_dir):
                    if first:
                        self.integrity_logger.warning(f"Lowest Directory Not Empty: {tgt_dir}")
                        # Lowest child not empty, we break and don't remove that directory from the table
                    break

                # No guard triggered, we're deleting at least
                self.main_logger.debug(f"deleting directory: {tgt_dir}")
                shutil.rmtree(tgt_dir)
                if first:
                    keys_to_delete.append(ktd)
                    first = False

        # TODO in ? does work?
        self.debug_execute("DELETE FROM db_dir WHERE key IN ?",
                           (f"({', '.join(map(str, keys_to_delete))})",))
        if len(keys_to_delete) > 0:
            self.main_logger.info(f"Pruned {len(keys_to_delete)} rows in dir table")
        else:
            self.main_logger.debug(f"Call to prune_dir, no rows pruned")

        return len(keys_to_delete)

    def prune_filesystem_directories(self):
        """
        Walk through the file system and check for empty directories. Remove empty directories if they exist.
        """
        ...

    # ==================================================================================================================
    # DB functions (functions operating only on the DB - basically wrapper for multiple sql statements)
    # ==================================================================================================================

    # TODO move functions...

    # ==================================================================================================================
    # Importing
    # ==================================================================================================================

    # long-running action
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
        mda_set: bool = False
        if self.mda is None:
            self.add_default_metadata_aggregator()
            mda_set = True

        # Defaulting allowed_extensions
        if allowed_ext is None:
            allowed_ext = set(defaults.video_extensions + defaults.image_extensions)

        # INFO: Handling all cases between append and purge for ease of understanding of the logic
        if append and purge:
            raise ValueError("Cannot specify both append and purge at the same time")

        elif append and not purge:
            assert tbl_name is not None, "Table name needs to be specified for append"
            if not self.import_table_exists(name=tbl_name):
                raise ValueError("Table doesn't exist, cannot append")

        elif not append and purge:
            assert tbl_name is not None, "Table name needs to be specified for purge"

            if self.import_table_exists(name=tbl_name):
                self.main_logger.info(f"Purged {tbl_name}")
                self.remove_import_table(name=tbl_name)

            tbl_name = self._add_import_table(root_path=source_dir, name=tbl_name, description=desc)

        elif not append and not purge:
            if not self.import_table_exists(name=tbl_name):
                tbl_name = self._add_import_table(root_path=source_dir, name=tbl_name, description=desc)
            else:
                raise ValueError(f"Table with name {tbl_name} already exists")

        else:
            raise ImplementationError("Tertiem Non Datur")

        # Actually search the provided directory
        if recursive:
            for root, dirs, files in os.walk(source_dir):
                for f in files:
                    self._prepare_file_import(file_path=os.path.join(root, f),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=append)
        else:
            for entry in os.listdir(source_dir):
                if os.path.isfile(os.path.join(source_dir, entry)):
                    self._prepare_file_import(file_path=os.path.join(source_dir, entry),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=append)
        if mda_set:
            self.mda = None

        self.commit()
        return tbl_name

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

        self.add_extra_cursor("update_allowed")
        self.debug_execute(f"SELECT key, allowed, original_filename FROM `{tbl}` WHERE imported IN (0, 1)")
        for row in self.sq_cur:
            key, _a, original_filename = row
            allowed = bool(_a)

            # INFO: Need to update mark_for_import to 0, to ensure we don't get any accidental imports of not allowed
            #  files.
            if allowed and os.path.splitext(original_filename)[1] not in allowed_ext:
                now_disallowed += 1
                self.main_logger.debug(f"{key} is now disallowed")
                self.debug_execute(f"UPDATE `{tbl}` SET allowed = ?, imported = ? WHERE key = {key}",
                                   (0, 0, key),
                                   "update_allowed")

            elif not allowed and os.path.splitext(original_filename)[1] in allowed_ext:
                now_allowed += 1
                self.main_logger.debug(f"{key} is now allowed")
                self.debug_execute(f"UPDATE `{tbl}` SET allowed = ? WHERE key = {key}",
                                   (1, key),
                                   "update_allowed")

            else:
                same += 1
                self.main_logger.debug(f"{key} remains the same")

        self.find_match_for_import_table(tbl)
        self.main_logger.info(f"Updated Allowed {tbl}. {now_allowed} now allowed, {now_disallowed} now disallowed, "
                              f"{same} stayed the same")
        self.commit()
        return now_allowed, now_disallowed, same

    def find_match_for_import_table(self, tbl_name: str, recompute: bool = False) -> int:
        """
        Find matches for files in a given import table.

        :param tbl_name: Name of temporary table created for import.
        :param recompute: Recompute match for everything or only for files which have not matches are allowed and
            not imported

        :returns: int - number of files processed .
        """
        if not self.import_table_exists(name=tbl_name):
            raise ValueError(f"Table {tbl_name} doesn't exist")

        self.add_extra_cursor("match_cursor")
        if recompute:
            self.debug_execute(f"SELECT key, original_filename, original_dirname, file_size_bytes, file_hash "
                               f"FROM `{tbl_name}` WHERE imported IN (0, 1) AND allowed = 1",
                               cur="match_cursor")
        else:
            self.debug_execute(f"SELECT key, original_filename, original_dirname, file_size_bytes, file_hash "
                               f"FROM `{tbl_name}` WHERE imported IN (0, 1) AND allowed = 1 AND matches IS NULL",
                               cur="match_cursor")

        count = 0
        for row in self.get_cursor("match_cursor"):
            key, original_filename, original_dirname, file_size_bytes, file_hash = row
            target_fp = str(os.path.join(original_dirname, original_filename))
            assert os.path.exists(target_fp), "Import file needs to exist."

            keys, highest_key, highest_match = self._get_best_match_type(tgt_fp=target_fp,
                                                                         file_hash=file_hash,
                                                                         fsb=file_size_bytes)

            self.debug_execute(stmt=f"UPDATE `{tbl_name}` SET match_type = ?, highest_match = ?, matches = ? "
                                    f"WHERE key = {key}",
                               args=(highest_match.value, highest_match,
                                     json.dumps(keys).replace("'", "''"), key))
            count += 1

        self.main_logger.info(f"Found {count} matches for {tbl_name}")
        self.remove_extra_cursor("match_cursor")
        self.commit()
        return count

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

            if not dest_dir.startswith(self.root_path):
                raise ValueError(f"Destination directory {_dest_dir} doesn't exist must be within the database root.")

        if not self.import_table_exists(name=tbl_name):
            raise ValueError(f"Table {tbl_name} doesn't exist")

        added_mda = False
        if self.mda is None and add_safety_exif_tags:
            self.add_default_metadata_aggregator()
            added_mda = True

        self.add_extra_cursor("import_table")
        self.debug_execute(f"SELECT key, original_filename, original_dirname, metadata, google_metadata, file_hash, "
                           f"file_size_bytes, datetime, timezone, naming_tag, gps_latitude, gps_longitude, "
                           f"datetime_source, allowed, import_key FROM `{tbl_name}` WHERE imported = 1")
        count = 0
        for row in self.get_cursor("import_table"):
            # Handle the setting of all the rows needed into the main table.
            k, ofn, ofd, md, gfmd, fh, fsb, _dt, tz, nt, gps_lat, gps_long, _dts, _allowed, impk = row
            dt = datetime.datetime.fromisoformat(_dt)
            allowed = bool(_allowed)
            dts = DateTimeSource(_dts)
            default_flags = MainFlags.default()

            # Set verify on FILE_AWARE
            if dts == DateTimeSource.FILE_AWARE:
                default_flags.verify = True

            if not allowed:
                self.main_logger.warning(f"Found entry marked for import, that isn't allowed.")
                assert False, "Invariant broken, found element marked for import with allowed = 0"
                continue

            # Sanity check
            assert import_key is None, "File marked as not imported, shouldn't have a import_key set."

            # Insert into main table and add
            self.debug_execute(f"INSERT INTO main "
                               f"(original_filename, original_dirname, metadata, google_metadata, naming_tag, db_name,"
                               f" datetime, timezone, datetime_source, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (ofn, odn, md.replace("'", "''"), gfmd.replace("'", "''"), nt, self.temp_db_name,
                                _dt, tz, _dts, default_flags.to_int()))
            self.debug_execute("SELECT key FROM main WHERE db_name = ?", (self.temp_db_name,))
            kr = self.sq_cur.fetchone()
            assert kr is not None, "Key should exist after insert."
            insert_key = kr[0]

            # Handle GPS
            assert (gps_lat is not None and gps_long is not None) or (gps_lat is None and gps_long is None), \
                "gps_lat and gps_long unequally set."
            if gps_lat is not None and gps_long is not None:
                gps_key = self.insert_get_gps_loc(gps_lat=gps_lat, gps_long=gps_long)

                self.debug_execute("UPDATE main SET gps_location = ? WHERE key = ?", (gps_key, insert_key))

            # Handle hash
            assert fh is not None, "File Hash needs to be defined"
            self.check_add_file_hash(file_key=insert_key, file_hash=fh, file_size=fsb)

            self._import_file(original_filename=ofn,
                              original_dirname=ofd,
                              fdt=dt,
                              tgt_dir=dest_dir,
                              key=import_key,
                              add_tag=add_safety_exif_tags and default_flags.verify)

            # Finally update the import table
            self.debug_execute(f"UPDATE `{tbl_name}` SET import_key = ?, imported = 2 WHERE key = ?",
                               (insert_key, k))
            count += 1

        if added_mda:
            self.mda = None
        self.remove_extra_cursor("import_table")
        self.commit()
        return count

    def _prepare_file_import(self, file_path: str, tbl_name: str, allowed_ext: Set[str], append: bool):
        """
        Handle Import for a singular file.

        PRECONDITION:
        - Filepath exists
        - Table Exists
        - File not in table

        :raises ValueError: If not append and file in table.
        """
        dirname, filename = os.path.split(file_path)
        self.debug_execute(f"SELECT key FROM `{tbl_name}` WHERE original_filename = ? AND original_dirname = ? ",
                           (filename, dirname))

        # Ensure file not in table yet.
        if self.sq_cur.fetchone() is not None:
            if append:
                return
            else:
                raise ValueError(f"File {file_path} already exists in table {tbl_name}")

        pres = self.mda.handle_file(file_path)
        allowed = os.path.splitext(file_path)[1] in allowed_ext

        self.debug_execute(f"INSERT INTO `{tbl_name}` ("
                           f"original_filename, "
                           f"original_dirname, "
                           f"metadata, "
                           f"google_metadata, "
                           f"file_hash, "
                           f"file_size_bytes, "
                           f"allowed, "
                           f"datetime, "
                           f"timezone, "
                           f"naming_tag, "
                           f"gps_latitude, "
                           f"gps_longitude,"
                           f"datetime_source) "
                           f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           args=(
                               pres.filename,
                               pres.dirname,
                               None if pres.metadata is None \
                                   else json.dumps(pres.metadata).replace("'", "''"),
                               None if pres.google_photos_metadata is None \
                                   else json.dumps(pres.google_photos_metadata).replace("'", "''"),
                               pres.file_hash,
                               pres.file_size,
                               1 if allowed else 0,
                               pres.creation_date.isoformat(),
                               pres.tz_name if isinstance(pres.tz_name, str) else pres.tz_name.key,
                               pres.naming_tag,
                               pres.gps_lat,
                               pres.gps_long,
                               pres.source.value
                           ))

    def _import_file(self,
                     key: int,
                     original_filename: str,
                     original_dirname: str,
                     fdt: datetime.datetime,
                     tgt_dir: str = None,
                     add_tag: bool = False):
        """
        Import a given file into the database.

        PRECONDITION: the key exists in the database, and the file exists on disk.

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
            tgt_dir = os.path.join(self.root_path, self.dt_to_dir(fdt))
            if not os.path.exists(tgt_dir):
                os.makedirs(tgt_dir)
                self.main_logger.debug(f"Creating Directory: {self.dt_to_dir(fdt)}")
            dir_key = None

        db_name = self.db_name(original_filename=original_filename, fdt=fdt, key=key)

        # copy the file to the target location
        shutil.copy2(os.path.join(original_dirname, original_filename), os.path.join(tgt_dir, db_name))
        self.main_logger.debug(f"Imported File: {original_filename}")

        assert self.mda is not None, "Metadata Aggregator is needed for import file"
        if add_tag:
            # Add the tag
            self.mda.eth.set_tags(files=[os.path.join(tgt_dir, db_name)], tags=self.exif_tag_creator(fdt))

            # Get Size of File and new File Hash
            new_hash = self.mda.hash_file(os.path.join(tgt_dir, db_name))
            new_size = os.stat(os.path.join(tgt_dir, db_name)).st_size
            assert new_size is not None, "New Size needed for update."
            self.check_add_file_hash(file_key=key, file_hash=new_hash, file_size=new_size)

        self.debug_execute("UPDATE main SET db_dir = ?, db_name = ? WHERE key = ?",
                           (dir_key, db_name, key))


    def _find_hash_match_keys(self, target_hash: str, file_size: int, mode: str) -> List[int]:
        """
        Given a hash, finds all file_keys which share this hash.

        mode (case-insensitive):

        - EARLIEST, given a file_key, only take into account the earliest hash of that file (importing)
        - LATEST, given a file_key, only take into account the latest hash of that file (detecting changed filenames)
        - ANY, given a file_key, take into account all hashes the file has had (detecting duplicates)

        :param target_hash: Target hash to search for
        :param file_size: File size to search for
        :param mode: Mode to search for, can be EARLIEST, LATEST, ANY

        :returns: List[int] - list of matching file_keys
        """
        if mode.lower() not in ("earliest", "latest", "any"):
            raise ValueError(f"Unsupported mode: {mode.lower()}, allowed: [earliest, latest, any]")

        if mode.lower() == "earliest":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hash AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.hash_date IN "
                               "(SELECT MIN(datetime(hash_date)) FROM hash_assoz GROUP BY hash_key, file_key)",
                               (target_hash, file_size))

        elif mode.lower() == "latest":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hash AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.hash_date IN "
                               "(SELECT MAX(datetime(hash_date)) FROM hash_assoz GROUP BY hash_key, file_key)",
                               (target_hash, file_size))
        elif mode.lower() == "any":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hash AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ?",
                               (target_hash, file_size))
        else:
            raise ImplementationError("Shouldn't be able to get here.")

        return [r[0] for r in self.sq_cur.fetchall()]

    def get_newest_hash(self, key: int) -> str | None:
        """
        Get the newest hash of a given file. If the newest hash doesn't match, we don't perform binary comparison.

        :param key: File key to search for
        :returns: None -> key not found, str, newest hash of the given file
        """
        self.debug_execute("SELECT h.hash FROM hash AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE ha.file_key = ? AND ha.hash_date IN "
                           "(SELECT MAX(hash_date) FROM hash_assoz WHERE file_key = ?)",
                           (key, key))
        res = self.sq_cur.fetchone()
        if res is None:
            return None

        return res[0]

    def _get_best_match_type(self, tgt_fp: str, file_hash: str, fsb: int) \
            -> Tuple[List[int], int | None, NewMatchTypes]:
        """
        PRECONDITION: tgt_fp exists.

        Given a file_hash and file_size returns the lowest

        :param tgt_fp: Target file path of the image in the import table
        :param file_hash: File hash of the image
        :param fsb: File size of the image

        :returns List of all hash_matches, key of highest match, highest match value
        """
        match_keys = self._find_hash_match_keys(target_hash=file_hash, file_size=fsb, mode="EARLIEST")

        keys: Dict[int, NewMatchTypes] = {}
        for m_key in match_keys:
            # Resolve the matched key to the filepath
            match_path = self.resolve_key_to_path(key=m_key)
            binary_match = None

            if match_path is None:
                raise CorruptDatabase("Inconsistency between tables. File from hash_assoz not present in tables.")

            # Check the binary difference of the files if they exist
            if os.path.exists(match_path):
                binary_match = filecmp.cmp(tgt_fp, match_path, shallow=False)

            m_newest_hash = self.get_newest_hash(m_key)

            # Rare occurrence
            # TODO different logger
            if m_newest_hash == file_hash and not binary_match:
                self.main_logger.warning("Found files with matching hash and size but different binary.")
            elif m_newest_hash != file_hash and binary_match:
                self.main_logger.warning("Found files different hashes but match binary.")

            source = self.get_db_location(key=m_key)
            if source is None:
                raise CorruptDatabase("Matched key should exist main or replaced")

            # parse into NewMatchTypes
            if source == DBLocation.MAIN:
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

            elif source == DBLocation.TRASH:
                if m_newest_hash != file_hash:
                    keys[m_key] = NewMatchTypes.HASH_MATCH_TRASH
                else:
                    assert m_newest_hash == file_hash, "Unexpected outcome, hashes should match."
                    if binary_match:
                        keys[m_key] = NewMatchTypes.BINARY_MATCH_TRASH
                    else:
                        # INFO: Dito as for DBLocation.MAIN
                        keys[m_key] = NewMatchTypes.HASH_MATCH_TRASH
            elif source == DBLocation.REPLACED:
                if m_newest_hash != file_hash:
                    keys[m_key] = NewMatchTypes.HASH_MATCH_REPLACED
                else:
                    assert m_newest_hash == file_hash, "Unexpected outcome, hashes should match."
                    if binary_match:
                        keys[m_key] = NewMatchTypes.BINARY_MATCH_REPLACED
                    else:
                        # INFO: Dito as for DBLocation.MAIN
                        keys[m_key] = NewMatchTypes.HASH_MATCH_REPLACED
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
            return [], None, NewMatchTypes.NO_MATCH

        return list(keys.keys()), highest_match_key, highest_match

    def insert_get_gps_loc(self, gps_lat: float, gps_long: float):
        """
        Get the Key of a given pair of GPS coordinates. If it doesn't exist, add it to the GPS Table.
        """
        self.debug_execute("SELECT key FROM gps_location WHERE gps_latitude = ? AND gps_longitude = ?",
                           (gps_lat, gps_long))

        res = self.sq_cur.fetchone()
        if res is not None:
            return res[0]

        # PRECONDITION: GPS Location doesn't exist
        self.debug_execute("INSERT INTO gps_location (gps_latitude, gps_longitude) VALUES (?, ?)",
                           (gps_lat, gps_long))
        key = self.insert_get_gps_loc(gps_lat, gps_long)
        return key

    def check_add_file_hash(self, file_key: int, file_size: int, file_hash: str) -> bool:
        """
        Checks if a given row in the hash_assoz table exists provided a file_hash, a file_size and file_key.

        Adds the row if it doesn't exist.

        :param file_hash: The hash of the file to check.
        :param file_size: The size of the file to check.
        :param file_key: The key of the file to check.

        :return: True if the row exists, False if the rows were added.
        """
        self.debug_execute("SELECT ha.hash_key, ha.file_key "
                           "FROM hash AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE h.hash = ? AND ha.file_key = ? AND ha.file_size = ?",
                           (file_hash, file_key, file_size))

        # Result not None, the row exists, exit function.
        if self.sq_cur.fetchone() is not None:
            return True

        now = datetime.datetime.now(datetime.timezone.utc)
        hash_key = self.insert_get_file_hash_key(file_hash=file_hash)
        self.debug_execute("INSERT INTO hash_assoz (hash_key, file_key, file_size_bytes, hash_date) "
                           "VALUES (?, ?, ?, ?)",
                           (hash_key, file_key, file_size, now.isoformat()))
        return False

    def insert_get_file_hash_key(self, file_hash: str) -> int:
        """
        Get the Key of a given hash string in the hash table. If it doesn't exist, add it to the hash table.
        """
        self.debug_execute("SELECT key FROM hash WHERE hash = ?", (file_hash,))
        res = self.sq_cur.fetchone()

        if res is not None:
            return res[0]

        # PRECONDITION: Hash string doesn't exist
        self.debug_execute("INSERT INTO hash (hash) VALUES (?)", (file_hash,))
        key = self.insert_get_file_hash_key(file_hash)
        return key

    def _insert_get_dir(self, dir_name:  str) -> int:
        """
        PRECONDITION: dir_name is absolute
        PRECONDITION: dir_name is child of root_path
        PRECONDITION: dir_name separated by os.sep

        Get the key of a given custom directory.

        :param dir_name: The name of the directory to insert.
        """
        rel_path = dir_name.replace(self.root_path, "")
        rel_path_list = rel_path.split(os.sep)

        self.debug_execute("SELECT key FROM db_dir WHERE db_local_dir = ?",
                           (self.dump_db_local_dir(rel_path_list),))

        res = self.sq_cur.fetchone()
        if res is not None:
            assert os.path.exists(dir_name), "Directories in db_dir must exist."
            return res[0]

        # PRECONDITION: doesn't exist
        os.makedirs(dir_name, exist_ok=True)
        self.debug_execute("INSERT INTO db_dir (db_local_dir) VALUES (?)",
                           (self.dump_db_local_dir(rel_path_list),))
        self.main_logger.debug(f"Createad custom dir {rel_path}")
        return self._insert_get_dir(dir_name)

    # ==================================================================================================================
    # Deduplication
    # ==================================================================================================================

    def find_hash_based_duplicates(self):
        """
        Find any grouping of hashes which have the same file size, and hash.
        """
        ...

    def deduplicate_internal(self, scope: GroupingCriterion, com: connection.Connection = None):
        """
        Performs the action of deduplication within given scopes (Given by grouping criterion)

        :param scope: Grouping criterion to deduplicate
        :param com: Connection object to report progress to frontend
        """
        ...

    def deduplicate_partitions(self, a: str, b: str):
        """
        Perform a more specific deduplication.

        Partition can a time range(datetime, datetime)
        Partition can be selection from table (all rows which have the mark field set)
        Partition can be the entire table like import table
        """
        ...

    def add_default_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Moves a pair of duplicates into the known_duplicates table.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=False, add=True)

    def remove_default_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Removes a pair of duplicates from the known_duplicates table.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=False, add=False)

    def add_known_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Moves a pair of duplicates into the known_duplicates table.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=True, add=True)

    def remove_known_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Removes a pair of duplicates from the known_duplicates table.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=True, add=False)

    def _internal_modify_duplicates(self, key_a: int | List[int], key_b: int | List[int], known: bool, add: bool):
        """
        Internal Function to add or remove a duplicate tuple, parametrizes the table to modify and operation.

        :param key_a: First key of Tuple
        :param key_b: Second key of Tuple
        :param known: If true, will remove the tuple from the known_duplicates table else duplicates table.
        :param add: if true, will add the tuple to the table, else remove the tuple.
        """
        tbl = "known_duplicates" if known else "duplicates"

        if add:
            op = f"INSERT OR IGNORE INTO `{tbl}` (key_a, key_b) VALUES (?, ?)"
        else:
            op = f"DELETE FROM `{tbl}` WHERE key_a = ? AND key_b = ?"

        if isinstance(key_a, int) and isinstance(key_b, int):
            if key_b == key_a:
                raise ValueError("Identical Keys.")

            if key_a >= key_b:
                key_a, key_b = key_b, key_a

            self.debug_execute(op, (key_a, key_b))

        elif isinstance(key_a, list) and isinstance(key_b, list):
            if not len(key_a) == len(key_b):
                raise ValueError("key_a and key_b must have same length")

            args = []
            for ka, kb in zip(key_a, key_b):
                if ka == kb:
                    raise ValueError("Identical Keys.")

                args.append((kb, ka) if ka >= kb else (kb, ka))

            self.debug_execute_many(op, args)
        else:
            raise TypeError("key_a and key_b must be either both list or both int.")

    def remove_all_tuples_with_key(self, key: int, known: bool = False) -> int:
        """
        Removes all tuples either from the known_duplicates table or the duplicates table which contain the specified
        key.

        :param key: Key which needs to be contained for the tuple to be removed.
        :param known: If true, will remove the tuples from the known_duplicates table else duplicates table.

        :return: Number of removed tuples.
        """
        tbl = "known_duplicates" if known else "duplicates"

        self.debug_execute(f"SELECT COUNT(*) FROM {tbl} WHERE key_a = ? AND key_b = ?", (key, key))
        cnt = self.sq_cur.fetchone()[0]

        self.debug_execute(f"DELETE FROM {tbl} WHERE key_a = ? OR key_b = ?", (key, key))
        return cnt

    # ==================================================================================================================
    # UI
    # ==================================================================================================================

    def modify_timezone(self,
                        key: int,
                        _target_tz: ZoneInfo | str | datetime.timedelta,
                        rename: bool = True,
                        replace: bool = False):
        """
        Modify the timezone of a given file. File must be in the main table.

        If rename is set, the file will be renamed in the fs
        If replace is set, the timezone will be replaced (utc offset changes). Otherwise utc-offset and time change.

        :param key: key in db of file which needs to be modified.
        :param _target_tz: Target timezone of the file.
        :param rename: If true, will rename the file in the main table.
        :param replace: If true, will replace the file in the main table.
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
        _, dt, flags, db_local_dir, db_name, original_name = self._get_rename_data(key=key)

        new_dt = dt.replace(tzinfo=target_tz) if replace else dt.astimezone(tz=target_tz)
        new_name = self.db_name(original_filename=original_name, key=key, fdt=new_dt)

        if rename:
            # TODO update ExifMetadata with new datetime
            self._internal_rename(key=key,
                                  new_name=new_name,
                                  db_local_dir=db_local_dir,
                                  db_name=db_name,
                                  flags=flags,
                                  dt=dt)


            self.debug_execute("UPDATE main SET datetime = ?, timezone = ?, db_name = ? WHERE key = ?",
                               (new_dt.isoformat(), new_dt.tzname(), new_name, key))
        else:
            self.debug_execute("UPDATE main SET datetime = ?, timezone = ? WHERE key = ?",
                               (new_dt.isoformat(), new_dt.tzname(), key))
        self.commit()
        # TODO update caches.

    def change_datetime(self,
                        key: int,
                        tag: str | List[Union[str, int]] | DoubleKey,
                        dts: DateTimeSource,
                        new_dt: datetime.datetime = None,
                        rename: bool = True):
        """
        Change the datetime associated with the given image. Each image should have a filename string and a given
        datetime. By default, the file name will also b e changed. This is only available for images in main table.

        :param key: key of image to update
        :param new_dt: new datetime object. (should have an utc offset)
        :param tag: tag of image to use for update.
        :param dts: date time source (where the new datetime is coming from)
        :param rename: Rename image if True.
        """
        if new_dt.tzinfo is None:
            raise ValueError("new_dt must have a timezone")

        _, dt, flags, db_local_dir, db_name, original_name = self._get_rename_data(key=key)
        new_name = self.db_name(original_filename=original_name, key=key, fdt=new_dt)
        timezone = new_dt.tzname()
        assert timezone is not None, "Unexpected timezone of None"

        # Rename the file
        if rename:
            # TODO update ExifMetadata with new datetime
            self._internal_rename(key=key,
                                  dt=dt,
                                  flags=flags,
                                  db_local_dir=db_local_dir,
                                  db_name=db_name,
                                  new_name=new_name)

        self.debug_execute("UPDATE main "
                           "SET datetime = ?, db_name = ?, naming_tag = ?, timezone = ?, datetime_source = ? "
                           "WHERE key = ?", (new_dt.isoformat(), new_name,
                                             NewMetadataAggregator.serialize_key(tag), timezone, dts.value))

        self.commit()
        # TODO update caches.

    def change_filename(self, key: int, new_filename: str):
        """
        The function exists for the purpose of allowing the user to change file names however it is not recommended.

        Change the filename. Set a custom filename. The filename must be unique within the database.
        Also, the file must still be present.

        :param key: Key in main database to update with the new filename
        :param new_filename: The new file name to use. Sets the db_name column.
        """
        self.debug_execute("SELECT key FROM main WHERE db_name = ?", (new_filename,))
        if self.sq_cur.fetchone() is not None:
            raise ValueError("Filename already exists in main table.")

        self.debug_execute("SELECT key FROM replaced WHERE former_name = ?", (new_filename,))
        if self.sq_cur.fetchone() is not None:
            raise ValueError("Filename already exists in replaced table.")

        # PRECONDITION: Filename not present
        _, dt, flags, db_local_dir, db_name, _ = self._get_rename_data(key=key)
        self._internal_rename(key=key,
                              flags=flags,
                              db_name=db_name,
                              new_name=new_filename,
                              dt=dt,
                              db_local_dir=db_local_dir)

        # Update the database after renaming
        self.debug_execute("UPDATE main SET db_name = ?, naming_tag = ? WHERE key = ?",
                           (new_filename, "CUSTOM", key))

        # Last operation, clear lookup caches
        self.commit()
        # TODO update caches.

    def _get_rename_data(self, key: int) -> Tuple[int, datetime.datetime, MainFlags, str, str, str]:
        """
        Get the necessary data from the database to rename a file
        """
        # Get current row
        self.debug_execute("SELECT m.key, m.datetime, m.flags, d.db_local_dir, m.db_name, m.original_filename "
                           "FROM main AS m JOIN db_dir AS d ON m.db_dir = d.key "
                           "WHERE m.key = ?", (key,))

        row = self.sq_cur.fetchone()
        if row is None:
            raise ValueError(f"Key {key} does not exist in main table")

        key, _dt, _flags, db_local_dir, db_name, original_name = row
        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        return key, dt, flags, db_local_dir, db_name, original_name

    def _internal_rename(self, key: int, flags: MainFlags, db_name: str, new_name: str, dt: datetime.datetime,
                         db_local_dir: str = None):
        """
        Shared part of the function that all functions that rename a file use.

        Info: Sets the prune_fs_dir flag.

        :param key: key of image to rename
        :param db_name: current name of image to rename
        :param new_name: new name of image to rename
        :param dt: datetime object needed for path
        :param db_local_dir: directory to use for path
        """
        if flags.trashed:
            new_par_dir = par_dir = self.get_trash_dir()
        elif db_local_dir is not None:
            new_par_dir = par_dir = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir))
        else:
            assert db_local_dir is None, "Unexpected state in parent directory resolution"
            par_dir = os.path.join(self.root_path, self.dt_to_dir(dt))
            new_par_dir = os.path.join(self.root_path, self.dt_to_dir(dt))

            if not os.path.exists(new_par_dir):
                self.main_logger.debug(f"Creating New Directory: {new_par_dir}")
                os.makedirs(new_par_dir)

        self.check_flags(key=key, flags=flags, org_path=os.path.join(par_dir, db_name))
        if os.path.splitext(new_name)[1] != os.path.splitext(db_name)[1]:
            self.main_logger.warning("New file extension does not match DB file extension")

        if not os.path.exists(os.path.join(par_dir, db_name)):
            raise ValueError("Original File doesn't exist, cannot rename.")

        # PRECONDITION: File Exists, Filename not present
        os.rename(os.path.join(par_dir, db_name), os.path.join(new_par_dir, new_name))
        self.prune_fs_dir = True

    def build_import_table_lookup(self, target_table: str):
        """
        Build the row lookup table for a import table
        """
        # TODO implement

    def build_images_table_lookup(self, grouping: GroupingCriterion, trash: bool = None):
        """
        Build the row lookup table for the images table
        """
        # TODO immplement

    # TODO give smarter name
    def lookup_row_to_xxx(self, row: int, images_table: bool = True):
        """
        Resolve row to list of image metadata

        :param row: Row to resolve
        :param images_table: If true, resolve images table else import table
        """
        # TODO implement

    def lookup_key_to_row(self, key: int, images_table: bool = True):
        """
        Resolve a given key from the row table to the row in the ui

        :param key: Row to resolve
        :param images_table: If true, resolve images table else import table
        """
        # TODO implement

    # ==================================================================================================================
    # Utility
    # ==================================================================================================================

    # Long-running action
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

        self.debug_execute("SELECT m.key, m.datetime, m.db_name, d.db_local_dir, m.flags "
                           "FROM main AS m JOIN db_dir AS d ON main.db_dir = db_dir.key "
                           # Check present                 check trash
                           "WHERE mod(m.flags, 2) == 1 AND mod((m.flags >> 2), 2) == 0")

        missing: int = 0
        created: int = 0
        for row in self.sq_cur:
            key, _dt, dbn, _db_dir, _flags = row

            flags = MainFlags.from_int(_flags)
            dt = datetime.datetime.fromisoformat(_dt)
            par_dir = os.path.join(self.db_path, *self.parse_db_local_dir(_db_dir)) if _db_dir \
                else os.path.join(self.root_path, self.dt_to_dir(dt))

            # skip missing images or images in trash
            if not flags.present or flags.trashed:
                assert False, "Error in SQL Statement, should not find trash or not present files."
                continue

            # checking for missing file
            if not os.path.exists(os.path.join(par_dir, dbn)):

                # INFO we're not updating the presence in the db because it doesn't fit the scope of this function.
                self.integrity_logger.warning(f"File from DB is missing: {dbn}, in {par_dir}")
                missing += 1
                continue

            # Thumbnail: write if not exists or exists + overwrite
            if thumbnail:
                if (not os.path.exists(self.full_thumbnail_path(key))
                        or (os.path.exists(self.full_thumbnail_path(key)) and overwrite)):

                    flags.has_thumbnail = self._create_display_file(
                        in_path=os.path.join(par_dir, dbn),
                        out_path=self.full_thumbnail_path(key),
                        major_size=self.config.thumbnail_target)
                    created += 1

                else:
                    self.main_logger.debug(f"Thumbnail already exists for key: {key}")
                    flags.has_thumbnail = True

            # Miniature: write if not exists or exists + overwrite
            if miniature:
                if (not os.path.exists(self.full_miniature_path(key))
                        or (os.path.exists(self.full_miniature_path(key)) and overwrite)):

                    flags.has_miniature = self._create_display_file(
                        in_path=os.path.join(par_dir, dbn),
                        out_path=self.full_miniature_path(key),
                        major_size=self.config.thumbnail_target)
                    created += 1

                else:
                    self.main_logger.debug(f"Miniature already exists for key: {key}")
                    flags.has_miniature = True

            # Update the flags of the given key.
            self.debug_execute(stmt="UPDATE main SET flags = ? WHERE key = ?",
                               args=(flags.to_int(), key),
                               cur="update_thumbnails")

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
            self.main_logger.error(f"Failed to get time data from probe result of ffmpeg: {in_path}")
        except IndexError:
            self.main_logger.error("Failed to get time data from probe result of ffmpeg")
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
            raise ValueError("Parent Key doesn't exist in main table.")

        parent_flags = MainFlags.from_int(raw_parent[1])
        parent_google_metadata = raw_parent[2]

        self.debug_execute(stmt="SELECT m.key, m.db_name, m.original_filename, m.metadata, m.google_metadata, "
                                "m.datetime, m.timezone, m.flags, d.db_local_dir "
                                "FROM main AS m JOIN db_dir AS d ON main.db_dir = db_dir.key WHERE m.key = ?",
                           args=(child_key,))

        result = self.sq_cur.fetchone()
        if result is None:
            raise ValueError("Child Key not found in main table")

        # INFO: Warning User, shouldn't really be occurring, since trashed shouldn't be able to be deduplicated
        if parent_flags.trashed:
            self.main_logger.warning(f"Moving File to Replaced Table with Parent in Trash.")

        if not parent_flags.present:
            self.main_logger.warning("Moving File to Replaced Table without Parent file being present.")

        # Unpack result for ease of use
        key, db_name, original_filename, metadata, google_metadata, _dt, timezone, _flags, db_dir = result

        # Parse the datetime for folder
        dt = datetime.datetime.fromisoformat(_dt)
        main_flags = MainFlags.from_int(_flags)

        # Check children in replaced table
        self.debug_execute("SELECT COUNT(*) FROM replaced WHERE parent == ?", args=(child_key,))
        count = self.sq_cur.fetchone()[0]

        if count > 0:
            self.main_logger.info(f"Updating {count} children of this entry in the replaced table")

            self.debug_execute("UPDATE replaced SET parent = ? WHERE parent = ?", (child_key, parent_key))

        # Check Entries in duplicates table
        self._migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=False)

        # Check Entries in known_duplicates table
        self._migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=True)

        # First inserting the key into the replaced table
        self.debug_execute(stmt="INSERT OR REPLACE INTO replaced (key, original_filename, metadata, google_metadata, "
                                "datetime, former_name, parent, timezone, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                           args=(key, original_filename, metadata.replace("'", "''"),
                                 google_metadata.replace("'", "''"), dt.isoformat(), db_name, parent_key, timezone))

        # Update file system
        if db_dir is None:
            tgt_path = os.path.join(self.root_path, self.dt_to_dir(dt))
        else:
            tgt_path = os.path.join(self.root_path, *self.parse_db_local_dir(db_dir))

        # Checking consistency between FS and DB
        self.check_flags(key=key, flags=main_flags, miniature=True, thumbnail=True,
                         org_path=os.path.join(tgt_path, db_name))

        # Take care of three kinds of files.
        if os.path.exists(os.path.join(tgt_path, db_name)):
            self.main_logger.debug("Moving Original File to Trash")
            main_flags.present = True
            os.rename(os.path.join(tgt_path, db_name), os.path.join(self.get_trash_dir(), db_name))
        else:
            main_flags.present = os.path.exists(os.path.join(self.get_trash_dir(), db_name))

        # Updating the flags again
        self.debug_execute("UPDATE replaced SET flags = ? WHERE key = ?",
                           args=(child_key, ReplacedFlags.from_main_flags(main_flags).to_int()))

        # Remove Thumbnail
        if os.path.exists(self.full_thumbnail_path(key)):
            self.main_logger.debug(f"Deleting Thumbnail {self.thumbnail_name(key)}")
            os.remove(self.full_thumbnail_path(key))

        # Remove Miniature
        if os.path.exists(self.full_miniature_path(key)):
            self.main_logger.debug(f"Deleting Miniature {self.miniature_name(key)}")
            os.remove(self.full_miniature_path(key))

        if copy_google_metadata and parent_google_metadata is None and google_metadata is not None:
            parent_flags.org_google_metadata = False
            self.debug_execute("UPDATE main SET google_metadata = ?, flags = ? WHERE key = ?",
                               (google_metadata.replace("'", "''"), parent_flags.to_int(), parent_key))

        # TODO Darktable???
        self.debug_execute("DELETE FROM main WHERE key = ?", (child_key,))
        self.prune_dir()
        self.prune_gps()
        self.prune_fs_dir = True
        # TODO update caches.
        self.commit()

    def _migrate_parent_duplicate(self, child_key: int, parent_key: int, known: bool):
        """
        Update the duplicates tables. All tuples with child_key, some_key are replaced by tuples of parent_key, some_key

        :param child_key: Key to replace
        :param parent_key: Key to use for replacement
        :param known: True -> update known_duplicates table else duplicates
        """
        tbl = "known_duplicates" if known else "duplicates"

        # Check Entries in duplicates table
        self.debug_execute(f"SELECT key_a, key_b FROM {tbl} WHERE key_a = ? OR key_b = ?",
                           (child_key, child_key))

        results = self.sq_cur.fetchall()

        if len(results) > 0:
            self.main_logger.debug(f"Changing {len(results)} {tbl} entries to the new parent")

            args = []
            for result in results:
                if result[0] == child_key:
                    args.append((parent_key, result[1]))
                elif result[1] == child_key:
                    args.append((result[0], parent_key))
                else:
                    raise ImplementationError("Couldn't find targeted key. Erroneous SQL Statement?")

            # Remove tuple of kind (parent_key, parent_key)
            filtered_args = list(filter(lambda a: a[0] != a[1], args))
            self._internal_modify_duplicates(key_a=[a[0] for a in filtered_args],
                                             key_b=[a[1] for a in filtered_args],
                                             known=known,
                                             add=True)

            self._internal_modify_duplicates(key_a=[r[0] for r in results],
                                             key_b=[r[1] for r in results],
                                             known=known,
                                             add=False)

    def move_to_trash(self, key: int):
        """
        Move a given image to trash.

        - Checks the file exists
        - Creates Thumbnail and Miniature
        - Moves the original file to the trash
        - Updates the flags of the file.
        """
        self.debug_execute(stmt="SELECT m.key, m.db_name, m.datetime, m.flags, d.db_local_dir "
                                "FROM main AS m JOIN db_dir AS d ON main.db_dir = db_dir.key WHERE m.key = ?",
                           args=(key,))
        _raw_res = self.sq_cur.fetchone()

        if _raw_res is None:
            raise ValueError(f"Key {key} not found in main table.")

        # Parse the row
        k, dbn, _dt, _flags, db_dir = _raw_res
        dt = datetime.datetime.fromisoformat(_dt)
        main_flags = MainFlags.from_int(_flags)

        # Get the paths
        cur_path = os.path.join(self.root_path, self.dt_to_dir(dt)) if db_dir is None \
            else os.path.join(self.root_path, db_dir)
        sfp = os.path.join(cur_path, dbn)
        tfp = os.path.join(self.get_trash_dir(), dbn)

        # Store existence in flags
        main_flags.present = os.path.exists(sfp)

        # TODO darktable
        if main_flags.present:
            assert os.path.exists(sfp), "Upper Condition wrong"

            # Create thumbnail
            self.main_logger.debug("Creating Thumbnail for image going into Trash")
            main_flags.has_thumbnail = self._create_display_file(in_path=sfp,
                                                                 out_path=self.full_thumbnail_path(key),
                                                                 major_size=self.config.thumbnail_target)
            # Creating miniature
            self.main_logger.debug("Creating Miniature for image going into Trash")
            main_flags.has_miniature = self._create_display_file(in_path=sfp,
                                                                 out_path=self.full_miniature_path(key),
                                                                 major_size=self.config.miniature_target)
            # Attempt the move the file
            self.main_logger.debug(f"Moving {sfp} to {tfp}")
            os.rename(sfp, tfp)

        # Set the presence flag and trash flag.
        main_flags.present = os.path.exists(tfp)
        main_flags.trashed = True

        # All things done, update the flags and write the db
        self.debug_execute("UPDATE main SET flags = ?, db_dir = NULL WHERE key = ?",
                           (main_flags.to_int(), key))
        self.prune_dir()
        self.prune_fs_dir = True
        # TODO update caches.
        self.commit()

    def delete_trash_thumb(self, key: Union[List[int], int, None]) -> int:
        """
        Delete the remaining thumbnail of an image in the trash. For recognition purposes, the thumbnails of the
        trashed images are retained by default. Use this function with care.

        :param key: Key to delete, list of keys to delete, or delete all thumbnails of images in the trash with None
        """
        count: int = 0
        stmt = "SELECT key, flags FROM main "

        # Everything in the trash
        if key is None:
            stmt += " WHERE mod(flags >> 2, 2) == 1"
            args = tuple()
        elif isinstance(key, int):
            stmt += f" WHERE key = ?"
            args = (key, )
        elif isinstance(key, list):
            stmt += f" WHERE key IN ({', '.join(map(str, key))})"
            args = tuple()
        else:
            raise TypeError(f"Unexpected Type for Key: {type(key).__name__}")

        self.debug_execute(stmt, args)
        self.add_extra_cursor("del_trash_thumb")

        for row in self.sq_cur:
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
                               (flags.to_int(), key),
                               "del_trash_thumb")

        self.remove_extra_cursor("del_trash_thumb")
        self.commit()
        return count

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
        self.debug_execute("SELECT m.key, m.datetime, m.flags, m.db_name, d.db_local_dir "
                           "FROM main AS m JOIN db_idr AS d ON (m.db_dir = d.key) "
                           # Check present = 1,            Check trash = 0
                           "WHERE mod(m.flags, 2) == 1 AND mod(m.flags >> 2, 2) == 0")

        self.add_extra_cursor("rm_disp_media")
        for row in self.sq_cur:
            key, _dt, _flags, db_name, db_local_dir = row
            dt = datetime.datetime.fromisoformat(_dt)
            flags = MainFlags.from_int(_flags)

            assert flags.trashed is False, "SQL Error, Trashed should be false."

            # Get the parent directory in the db where the file resides
            par_dir = os.path.join(self.root_path, db_local_dir) if db_local_dir is not None \
                else os.path.join(self.root_path, self.dt_to_dir(dt))

            # Skip if the original is not present
            self.check_flags(key=key, flags=flags, miniature=True, thumbnail=True,
                             org_path=os.path.join(par_dir, db_name))
            if not os.path.exists(os.path.join(par_dir, db_name)):
                continue

            # PRECONDITION: The original file exists in the database.
            if os.path.exists(self.full_thumbnail_path(key)):
                self.main_logger.debug(f"Deleting '{self.thumbnail_name(key)}'")
                os.remove(self.full_miniature_path(key))
                flags.has_thumbnail = False
                count += 1

            if os.path.exists(self.full_miniature_path(key)):
                self.main_logger.debug(f"Deleting '{self.miniature_name(key)}'")
                os.remove(self.full_miniature_path(key))
                flags.has_miniature = False
                count += 1

            self.debug_execute("UPDATE main SET flags = ? WHERE key = ?",
                               (flags.to_int(), key),
                               "rm_disp_media")

        self.remove_extra_cursor("rm_disp_media")
        self.commit()
        self.main_logger.info(f"Finished Deleting {count} Display Media of existing images.")
        return count

    def empty_trash(self):
        """
        Removes all originals from the trash.
        """
        self.main_logger.info(f"Emptying all Trashed files...")
        trash = self._empty_trash(replaced=False)
        replaced = self._empty_trash(replaced=True)
        self.main_logger.info(f"Deleted a total of {trash + replaced} files from trash.")
        return trash + replaced

    def _empty_trash(self, replaced: bool) -> int:
        """
        Internal function to remove originals from one of two categories of files in the trash:
        - Files which are marked as 'trashed'
        - Files which are duplicates and the originals were moved to trash

        :param replaced: if true, delete files from replaced table else remove files marked as 'trashed'
        """
        count: int = 0
        if replaced:
            self.debug_execute("SELECT key, former_name, flags FROM replaced")
            update_stmt = "UPDATE replaced SET flags = ? WHERE key = ?"
        else:
            self.debug_execute("SELECT key, db_name, flags FROM main WHERE mod(flags >> 2, 2) == 1")
            update_stmt = f"UPDATE main SET flags = ? WHERE key = ?"

        self.main_logger.info(f"Deleting Originals from Files in {'Replaced' if replaced else 'Trash'}")
        self.add_extra_cursor("del_trash")

        # Remove originals from files marked as trash
        for row in self.sq_cur:
            key, db_name, _flags = row
            flags = ReplacedFlags.from_int(_flags) if replaced else  MainFlags.from_int(_flags)

            # TODO darktable
            if os.path.exists(os.path.join(self.get_trash_dir(), db_name)):
                self.main_logger.debug(f"Deleting {db_name} from trash")
                os.remove(os.path.join(self.get_trash_dir(), db_name))
                flags.present = False
                count += 1
                self.debug_execute(update_stmt, (flags.to_int(), key), "del_trash")

        self.main_logger.info(f"Finished Deleting {count} Originals {'Replaced' if replaced else 'Trash'}")
        self.remove_extra_cursor("del_trash")
        self.commit()
        return count

    def forget_image_from_replaced(self, key: int):
        """
        Forgets a image from the replaced table.
        """
        self.debug_execute("SELECT * FROM replaced WHERE key = ?", (key,))
        if self.sq_cur.fetchone() is None:
            raise ValueError(f"Key {key} not found in replaced table.")

        self._forget_children_in_replaced(key=key)
        self.mark_import_table_as_stale()
        self.prune_hash()
        self.prune_fs_dir = True
        self.commit()
        # TODO update caches.
        self.main_logger.info(f"Forgot {key} from replaced table")

    def forget_image_from_main(self, key: int):
        """
        Forgets the image in the main table:

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
        self.debug_execute("SELECT m.datetime, m.db_name, m.gps_location, d.db_local_dir, m.db_dir, m.flags FROM "
                           "main AS m JOIN db_dir AS d ON m.db_dir = d.key WHERE m.key = ?", (key, ))
        row = self.sq_cur.fetchone()
        if row is None:
            raise ValueError("Key not found in main table")

        # Removing all children in replaced
        self.debug_execute("SELECT key FROM replaced WHERE parent = ?", (key,))
        children = [r[0] for r in self.sq_cur.fetchall()]
        self._forget_children_in_replaced(key=children)

        # Parse the row
        _dt, db_name, gps_location, db_local_dir, db_dir_key, _flags = row
        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        # TODO darktable
        # Remove files
        if flags.trashed:
            org_p = os.path.join(self.get_trash_dir(), db_name)
            self.check_flags(flags=flags, key=key, miniature=True, thumbnail=True, org_path=org_p)
            if os.path.exists(org_p):
                self.main_logger.debug(f"Deleting {db_name} from trash")
                os.remove(os.path.join(self.get_trash_dir(), db_name))

        else:
            if db_local_dir is None:
                fp = os.path.join(self.root_path, self.dt_to_dir(dt), db_name)
            else:
                fp = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), db_name)

            self.check_flags(flags=flags, key=key, miniature=True, thumbnail=True, org_path=fp)
            if os.path.exists(fp):
                self.main_logger.debug(f"Deleting {db_name} from DB")
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
        if gps_location is not None:
            self.debug_execute("DELETE FROM gps_location WHERE key = ?", (gps_location,))
        if db_dir_key is not None:
            self.debug_execute("DELETE FROM db_dir WHERE key = ?", (db_dir_key,))

        # Removing files from duplicates table
        c_known = self.remove_all_tuples_with_key(key=key, known=True)
        self.main_logger.debug(f"Deleted {c_known} tuples from known_duplicates table")
        c_default = self.remove_all_tuples_with_key(key=key, known=False)
        self.main_logger.debug(f"Deleted {c_default} tuples from default table")

        # Finally deleting the main row
        self.debug_execute("DELETE FROM main WHERE key = ?", (key,))
        self.commit()

        # Prune dir, hash, gps
        self.mark_import_table_as_stale()
        self.prune_hash()
        self.prune_gps()
        self.prune_dir()
        self.prune_fs_dir = True
        self.commit()

        # TODO update caches.
        self.main_logger.info(f"Forgot {key} in main table and children successfully")

    def _forget_children_in_replaced(self, key: int | List[int]):
        """
        Forgets a duplicate from the replaced table.

        PRECONDITION: Rows exist in the replaced table.
        """
        if isinstance(key, int):
            key = [key]

        assert isinstance(key, list), f"Unexpected Type of key: {type(key).__name__}"

        key_tuples = [(k,) for k in key]

        # Delete all hash associations of that file
        # TODO test, does ? with in work
        self.debug_execute_many("DELETE FROM hash_assoz WHERE file_key = ?", key_tuples)

        self.debug_execute("SELECT key, former_name, flags FROM replaced WHERE key IN ?",
                           (f"({', '.join(map(str, key))})",))

        self.add_extra_cursor("forget_duplicate")
        # Removing all duplicates
        for row in self.sq_cur:
            key, former_name, _flags = row
            flags = ReplacedFlags.from_int(_flags)

            if os.path.exists(os.path.join(self.get_trash_dir(), former_name)):
                self.main_logger.debug(f"Deleting {former_name} from trash")
                os.remove(os.path.join(self.get_trash_dir(), former_name))
                flags.present = False

                # Update the flags in the replaced table
                self.debug_execute("UPDATE replaced SET flags = ? WHERE key = ?",
                                   (flags.to_int(), key),
                                   'forget_duplicate')

        # Deleting the rows from the replaced table to finish forgetting.
        # TODO update if in ? doesn't work!
        self.debug_execute("DELETE FROM replaced WHERE key IN ?", (f"({', '.join(map(str, key))})",))
        self.remove_extra_cursor("forget_duplicate")

    def check_and_update_thumbnails(self, from_select: bool = False):
        """
        Go through db and check the mark for thumbnail and a thumbnail existing are correct.

        :param from_select: Use selection marker of images to check changed hashes for those images.
        """
        ...
        # TODO implement

    def check_flags(self, key: int,
                    flags: MainFlags | ReplacedFlags,
                    miniature: bool = False,
                    thumbnail: bool = False,
                    org_path: str = None):
        """
        Check the flags, of a given image. Report issues to integrity_logger.

        INFO: miniature and thumbnail need to be none, if the key is from the replaced table.

        **Doesn't update the DB and doesn't update the flags object**
        """
        # Check the miniatures.
        if miniature:
            assert isinstance(flags, MainFlags), f"Unexpected Type of flags: {type(flags).__name__}"
            if os.path.exists(self.full_miniature_path(key)) and not flags.has_miniature:
                self.integrity_logger.warning(f"Miniature present, flags record not present.")
            elif not os.path.exists(self.full_miniature_path(key)) and flags.has_miniature:
                self.integrity_logger.warning(f"Miniature not present, flags record present.")

        if thumbnail:
            assert isinstance(flags, MainFlags), f"Unexpected Type of flags: {type(flags).__name__}"
            if os.path.exists(self.full_thumbnail_path(key)) and not flags.has_thumbnail:
                self.integrity_logger.warning(f"Thumbnail present, flags record not present.")
            elif not os.path.exists(self.full_thumbnail_path(key)) and flags.has_thumbnail:
                self.integrity_logger.warning(f"Thumbnail not present, flags record present.")

        if org_path is not None:
            if os.path.exists(org_path) and not flags.present:
                self.integrity_logger.warning(f"original present, flags record not present.")
            elif not os.path.exists(org_path) and flags.present:
                self.integrity_logger.warning(f"original present, flags record present.")

    # ==================================================================================================================
    # Lookup Methods
    # ==================================================================================================================

    def _db_resolve_key_to_original_path(self, key: int) -> str | None:
        """
        Resolves a given key to an absolute filepath. The filepath can not exist.

        :param key: The key to resolve.
        """
        self.debug_execute("SELECT m.key, m.db_name, d.db_local_dir, m.datetime, m.flags, 0 AS from_replaced "
                           "FROM main AS m JOIN db_dir AS d ON m.db_dir = d.key "
                           "WHERE m.key = ? "
                           "UNION ALL "
                           "SELECT key, former_name AS db_name, NULL AS db_local_dir, NULL AS datetime, flags, "
                           "1 AS from_replaced "
                           "FROM replaced "
                           "WHERE key = ?", (key, key))
        res = self.sq_cur.fetchall()
        if len(res) == 0:
            return None

        # Result is not None
        if len(res) > 1:
            raise CorruptDatabase(f"key {key} appears in main and replaced table. ")

        # PRECONDITION, len(res) == 1
        key, db_name, db_local_dir, _dt, _flags, _fr = res[0]
        from_replaced = bool(_fr)

        # in replaced => file is in trash
        if from_replaced:
            self.check_flags(key=key, flags=ReplacedFlags.from_int(_flags), miniature=False, thumbnail=False,
                             org_path=os.path.join(self.get_trash_dir(), db_name))
            return os.path.join(self.get_trash_dir(), db_name)

        # Ensure we're in the main table
        assert from_replaced is False, "Now in Main Table results"
        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        # Main table but in the trash
        if flags.trashed:
            path = os.path.join(self.get_trash_dir(), db_name)

        # Main table, specific directory
        elif db_local_dir is not None:
            path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), db_name)

        # Path from datetime
        else:
            assert _dt is not None, "Need datetime to resolve path from datetime"
            path = os.path.join(self.root_path, self.dt_to_dir(dt), db_name)

        self.check_flags(flags=flags, key=key, miniature=False, thumbnail=False, org_path=path)
        return path

    def get_db_location(self, key: int) -> DBLocation | None:
        """
        Check where a given key is from within the database.

        :returns: DBLocation for a given key, or None if the key didn't exist
        """
        self.debug_execute("SELECT key FROM replaced WHERE key = ?", (key,))
        if self.sq_cur.fetchone() is not None:
            return DBLocation.REPLACED

        self.debug_execute("SELECT key, flags FROM main WHERE key = ?", (key,))
        res = self.sq_cur.fetchone()
        if res is None:
            return None

        flags = MainFlags.from_int(res[1])
        if flags.trashed:
            return DBLocation.TRASH
        else:
            return DBLocation.MAIN

    def resolve_key_to_path(self, key: int) -> str | None:
        """
        Get the original filename for image

        :param key: The key to resolve.

        :returns: Path to the original file,
        """
        res = self.key_to_filepath_cache.get(key)

        # Path is not in cache, resolve using db, store in cache and return value
        if res is nd:
            path = self._db_resolve_key_to_original_path(key)
            self.key_to_filepath_cache.set(key, path)
            return path

        return res

    def filename_to_key(self, fname: str) -> int | None:
        """
        Resolve a filename to key
        """
        # TODO implement
        ...

    @staticmethod
    def dt_to_dir(dt: datetime.datetime) -> str:
        """
        Get path suffix for
        """
        return os.path.join(dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"))

    @staticmethod
    def thumbnail_name(key: int) -> str:
        """
        Given a key, get the thumbnail name
        """
        return f"thumb_{key:10000}.jpeg"

    @staticmethod
    def miniature_name(key: int) -> str:
        """
        Given a key, get the miniature name
        """
        return f"miniature_{key:10000}.jpeg"

    def full_thumbnail_path(self, key: int) -> str:
        """
        Get the path to the thumbnail directory concat with the thumbnail name.
        """
        return os.path.join(self.get_thumb_dir(), self.thumbnail_name(key))

    def full_miniature_path(self, key: int) -> str:
        """
        Get the path to the thumbnail directory concat with the miniature name.
        """
        return os.path.join(self.get_thumb_dir(), self.miniature_name(key))

    def temp_video_path(self) -> str:
        """
        For a video, give a temporary path, where the thumbnail for the video is extracted to.
        """
        return os.path.join(self.get_thumb_dir(), "video_temp.jeg")

    def get_thumb_dir(self) -> str:
        """
        Get folder where to store thumbnails. Is absolute path.
        """
        if os.path.isabs(self.config.thumbnail):
            return os.path.normpath(self.config.thumbnail)
        else:
            return os.path.join(self.root_path, self.config.thumbnail)

    def get_trash_dir(self) -> str:
        """
        Get folder where to store trash. Is absolute path.
        """
        if os.path.isabs(self.config.trash):
            return os.path.normpath(self.config.trash)
        else:
            return os.path.join(self.root_path, self.config.trash)

    def get_temp_dir(self):
        """
        Get folder where temporary files are located (dif results)
        """
        if os.path.isabs(self.config.temp_path):
            return self.config.temp_path
        else:
            return os.path.join(self.root_path, self.config.temp_path)

    def db_name(self, original_filename: str, key: int, fdt: datetime.datetime):
        """
        Generate the filename of a given file within the database.
        """
        base_name = fdt.strftime(format="%Y-%m-%dT%H-%M-%S") + f"_{key:10000}"
        ob, ext = os.path.splitext(original_filename)

        if self.config.org_filename_append:
            def_new_name = base_name + "_" + ob
            trunc_new_name = def_new_name[:120] + ext
        else:
            # Should technically not be possible but we truncate just to be sure.
            trunc_new_name = base_name[:120] + ext

        return trunc_new_name

    @staticmethod
    def parse_db_local_dir(db_local_dir: str) -> list:
        """
        Parse the json string from the database to aa list of strings.
        """
        res = json.loads(db_local_dir)
        assert isinstance(res, list), f"Unexpected type in db_local_dir {type(res).__name__}"
        return res

    @staticmethod
    def dump_db_local_dir(dir_names: List[str]) -> str:
        """
        Convert a list of dir names into a json list which can be inserted into the database.
        """
        return json.dumps(dir_names).replace("'", "''")
