import datetime
import filecmp
import json
import logging
import os.path
import shutil
import sys
from typing import Set, Dict, List, Union, Tuple, Any, Iterator
from zoneinfo import ZoneInfo

import cv2
import ffmpeg

import photo_lib.defaults as defaults
from photo_lib.cache import nd
from photo_lib.config import Config
from photo_lib.custom_enum import GroupingCriterion, NewMatchTypes, SelectionType, MediaType, Allowed, ImportStatus
from photo_lib.data_objects import Selection, NewImportTableEntry
from photo_lib.db_definitions import current_version, history, StaticDeclaration, GenericDeclaration
from photo_lib.errors_and_warnings import ImplementationError, CorruptDatabase
from photo_lib.flag_dataclasses import MainFlags, GenericTableFlags
from photo_lib.metadata_aggregator import MetadataParsingResult
from photo_lib.metadata_aggregator.config import DoubleKey
from photo_lib.metadata_aggregator.enums import DateTimeSource
from photo_lib.metadata_aggregator.new_metadata_aggregator import NewMetadataAggregator
from photo_lib.sqlite_wrapper import BaseSQliteDB


# https://docs.darktable.org/usermanual/development/en/overview/sidecar-files/sidecar-import/
class PhotoDB(BaseSQliteDB):
    __verified: bool = False

    static_decls: Dict[str, StaticDeclaration]
    generic_decls: Dict[str, GenericDeclaration]

    __reserved_names: List[str] = ["<temp>"]

    # Redefining logger as mandatory
    db_logger_name: str = "PhotoDB.SQLiteDB"
    integrity_logger_name: str = "PhotoDB.SQLiteDB.Integrity"

    integrity_logger: logging.Logger

    # Flags
    opt_integrity_check: bool

    # ==================================================================================================================
    # Object Utility Function
    # - Classmethods
    # - Properties
    # - Dunder Methods
    # ... Basically what you need to create a usable object of type PhtosDB
    # ==================================================================================================================

    @property
    def reserved_named(self) -> List[str]:
        """
        Get all special names used in the db.
        """
        return self.__reserved_names

    @property
    def reserved_temp_file_name(self) -> str:
        """
                Temporary File Name used for import.
                """
        return self.__reserved_names[0]

    @property
    def verified(self) -> bool:
        """
        Whether the database was verified.
        """
        return self.__verified

    @classmethod
    def detach(cls, inst: "PhotoDB") -> "PhotoDB":
        """
        Create a new instance from another instance. (needed for long_running_actions)
        """
        # Copy the verify state from the inst over to this instance
        inst.cleanup(fast=True)

        new_inst = cls(db_path=inst.db_path,
                       init=False,
                       init_loggers=False,
                       verify=False,
                       opt_integrity_check=False),

        new_inst.__verified = inst.verified
        return new_inst

    def debug_execute(self, stmt: str, args: Union[tuple, dict, None] = None, cur: str = None):
        """
        Wrapper that blocks if the database isn't verified.

        :raises ImplementationError: If the database isn't verifeid.

        Original Doc String:
        --------------------

        Function executes statement in database and in case of an exception prints the offending statement.

        User ? for placeholder by index or :name for placeholder by name.

        :param stmt: Statement to execute
        :param args: Substitution arguments to pass to the statement
        :param cur: string to get an extra named cursor from the extra cursors.

        :return:
        """
        if not self.verified:
            raise ImplementationError("Cannot operate on Non-Verified Database")

        return super().debug_execute(stmt=stmt, args=args, cur=cur)

    def debug_execute_many(self, stmt: str, args: List[Union[tuple, dict]], cur: str = None):
        """
        Wrapper that blocks if the database isn't verified.

        :raises ImplementationError: If the database isn't verifeid.

        Original Doc String:
        --------------------

        Function executes statement with multiple arguments in database and in case of an exception prints the
        offending statement.

        User ? for placeholder by index or :name for placeholder by name.

        :param stmt: Statement to execute
        :param args: Substitution arguments to pass to the statement
        :param cur: string to get an extra named cursor from the extra cursors.

        :return:
        """
        if not self.verified:
            raise ImplementationError("Cannot operate on Non-Verified Database")

        return super().debug_execute_many(stmt=stmt, args=args, cur=cur)


    def __init__(self,
                 db_path: str,
                 init: bool = False,
                 verify: bool = True,
                 init_loggers: bool = True,
                 opt_integrity_check: bool = False):
        """
        Construct a Database Object from a preexisting database file.

        Database Initialization:

        - For initialization, you can provide the db with a custom config
        - Both the config and the db_file mustn't exist.

        :param db_path: Root path of the database
        :param init: If true, initialize the database.
        :param init_loggers: If true, initialize the loggers. Otherwise, Loggers must be defined externally.
        :param opt_integrity_check: Every time full file paths are computed and flags are present. Flags consistency
            with file system are checked.
        """
        self.logger = logging.getLogger(PhotoDB.db_logger_name)
        self.integrity_logger = logging.getLogger(PhotoDB.integrity_logger_name)

        if init_loggers:
            self.set_logging_defaults()

        self.build_definition_lookup()
        self.opt_integrity_check = opt_integrity_check

        # Prepping Config
        if not init:
            if not os.path.exists(db_path):
                raise FileNotFoundError("Config File Not Found")

        else:
            # Checking existence of db file
            if os.path.exists(db_path):
                raise FileExistsError("Database File Exists")

        super().__init__(db_path)

        if init:
            self.init_db()
        else:
            if verify:
                self.verify_tables()
                self.clear_filename_update_table()
                self.clear_hash_update_table()
                self.clear_presence_table()
                self.basic_integrity_check()

    def reload_loggers(self):
        """
        Get the loggers from the class attributes

        attr: main_logger_name for main_logger
        attr: integrity_logger_name for integrity_logger
        """
        self.logger = logging.getLogger(self.db_logger_name)
        self.integrity_logger = logging.getLogger(self.integrity_logger_name)

    def set_logging_defaults(self):
        """
        Set Defaults of loggers.
        """
        # Level
        self.logger.setLevel(logging.DEBUG)
        self.integrity_logger.setLevel(logging.DEBUG)

        # Propagate
        self.integrity_logger.propagate = True
        self.logger.propagate = False

        # Define handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        self.logger.addHandler(handler)

    def cleanup(self, fast: bool = False):
        """
        Besides writing to file, perform some checks and pruning operations

        :param fast: If true, skip any integrity checks.
        """
        if not fast:
            if self.prune_fs_dir:
                self.prune_filesystem_directories()

            self.basic_integrity_check()
        self.cleanup()

    def init_db(self):
        """
        Create all tables from db_definitions.py
        """
        self.logger.info("Initializing Database")

        for short_name, decl in self.static_decls.items():
            self.logger.info(f"Creating {short_name}")

            self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, decl.name))

        self.logger.info("Initialization Complete")

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

    # ==================================================================================================================
    # Table Integrity Checks
    # ==================================================================================================================

    def verify_tables(self) -> bool:
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

    def basic_integrity_check(self):
        """
        Basic sanity checks on the db to ensure we don't get corrupt data.
        """

        # - Check that file_keys in the hash_assoz table have a matching entry in replaced or main
        # - Check that all entries in main have a hash
        # - Check no entries in main table with reserved db_name
        # - Exactly one entry per file_key with initial flags hash_assoz.
        # - Check constraint on flags: either trashed OR duplicate but both.
        # - Check no duplicate chaining.
        pass

    # ==================================================================================================================
    # Import Table
    # ==================================================================================================================

    def add_import_table(self, root_path: str, name: str = None, description: str = None, internal: bool = False):
        """
        Add a new import table to the database.

        :param root_path: dir_root from which to import
        :param name: The name of the table. Override, defaults to dirname(root_path) + hash(current_datetime)
        :param description: The description of the table. Override, defaults to None
        :param internal: If we're checking if there are new files in the db we don't know yet.

        :raises ValueError: if that import table already exists.
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
            self.logger.warning(f"Table Name longer than 120 characters. Truncating to: `{tbl_name}`")

        if self.import_table_exists(tbl_name):
            raise ValueError(f"Table `{tbl_name}` already exists.")

        # Add the table to the generic lookup table
        flags = GenericTableFlags(stale=False, internal=internal)
        self.debug_execute(stmt="INSERT INTO import_tables (root_path, table_name, table_description, flags) "
                                "VALUES (?, ?, ?, ?)",
                           args=(root_path, tbl_name, description, flags.to_int()))

        # Actually creating table
        decl = self.generic_decls["import_table"]
        self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, tbl_name))
        self.commit()
        return tbl_name

    def import_table_flags(self, tbl_name: str) -> GenericTableFlags | None:
        """
        Return the Flags of an Import Table.

        """
        self.debug_execute("SELECT flags FROM import_tables WHERE table_name = ?", (tbl_name,))
        res = self.sq_cur.fetchone()

        if res is None:
            return None

        return GenericTableFlags.from_int(res[0])

    def import_table_exists(self, name: str = None) -> bool:
        """
        Check if a given name with root_path and name exists already.
        """
        self.debug_execute("SELECT key FROM import_tables WHERE  name = ?", (name,))
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

    def list_import_tables(self) -> Iterator[NewImportTableEntry]:
        """
        Return List of all Import Tables
        """
        self.add_extra_cursor("list_import_tables")
        self.debug_execute("SELECT key, root_path, table_name, table_name, flags FROM import_tables")
        for key, rp, tbl_name, tbl_desc, _flags in self.get_cursor("list_import_tables"):
            yield NewImportTableEntry(key, rp, tbl_name, tbl_desc, GenericTableFlags.from_int(_flags))

        self.remove_extra_cursor("list_import_tables")

    def get_import_table_key_from_path(self, tbl_name: str, path: str) -> int | None:
        """
        Check whether a given path is already present in the import table.

        :param tbl_name: Name of the table to search in
        :param path: Path of given file to search

        :returns: key of row given path in import table or none
        """
        dir_name, file_name = os.path.split(path)
        self.debug_execute(f"SELECT key FROM `{tbl_name}` WHERE original_filename = ? AND original_dirname = ? ",
                           (file_name, dir_name))

        res = self.sq_cur.fetchone()

        if res is None:
            return None

        return res[0]

    def add_file_to_import_table(self,
                                 tbl_name: str,
                                 parsing_result: MetadataParsingResult,
                                 allowed_ext: Set[str]):
        """
        Add file metadata to import table. Compute allowed state of file from filename

        :param tbl_name: Name of table to add the file to
        :param parsing_result: Parsing result of metadata aggregator
        :param allowed_ext: Allowed file extensions, to compute allowed field.


        :raises ValueError: If not append and file in table.
        :raises sqlite3.OperationalError: If the Import Table doesn't exist
        :raises sqlite3.IntegrityError: If the file path already exists
        """
        # Compute complex rows
        allowed = os.path.splitext(parsing_result.filename)[1] in allowed_ext
        md_str = json.dumps(parsing_result.metadata) if parsing_result.metadata else None
        gfmd_str = json.dumps(parsing_result.google_photos_metadata) if parsing_result.google_photos_metadata else None
        tz_str = parsing_result.tz_name if isinstance(parsing_result.tz_name, str) else parsing_result.tz_name.key

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
                               parsing_result.filename,
                               parsing_result.dirname,
                               md_str,
                               gfmd_str,
                               parsing_result.file_hash,
                               parsing_result.file_size,
                               1 if allowed else 0,
                               parsing_result.creation_date.isoformat(),
                               tz_str,
                               parsing_result.naming_tag,
                               parsing_result.gps_lat,
                               parsing_result.gps_long,
                               parsing_result.source.value
                           ))

    def update_allowed_iterator(self, tbl_name: str) -> Iterator[Tuple[int, bool, str]]:
        """
        Creates an iterator to update the allowed state of the files in the import table.
        """
        self.add_extra_cursor("update_allowed")
        self.debug_execute(stmt=f"SELECT key, allowed, original_filename FROM `{tbl_name}` WHERE imported IN (0, 1)")
        for key, _allowed, org_fname in self.get_cursor("update_allowed"):
            yield key, bool(_allowed), org_fname

        self.remove_extra_cursor("update_allowed")

    def set_allowed(self, tbl_name: str, key: int, allowed: Allowed, message: str = None):
        """
        Set the allowed flag of a given row of an import table.
        Can also set the message of the given row in the import table.

        PRECONDITION: Key exists in import table

        imported column is updated to 0, if the allowed is not ALLOWED

        :param tbl_name: import table to update
        :param key: key in table to update
        :param allowed: allowed flag allowed state to set
        :param message: error message to append

        :raises sqlite3.OperationalError: If the Import Table doesn't exist
        """
        if allowed == Allowed.ALLOWED:
            self.debug_execute(f"UPDATE `{tbl_name}` SET allowed = ?, message = ? WHERE key = ?",
                               (allowed.value, message, key))

        else:
            self.debug_execute(f"UPDATE `{tbl_name}` SET allowed = ?, message = ?, imported = 0 WHERE key = ?",
                               (allowed.value, message, key))
        assert self.sq_cur.rowcount == 1, f"Key {key} in {tbl_name} does not exist, PRECONDITION"

    def perform_import_iterator(self, tbl_name: str) -> Iterator[
        Tuple[int, str, str, str | None, str | None, str, int, datetime.datetime,
              str, str, float | None, float | None, DateTimeSource, Allowed, int | None]]:
        """
        Iterator to get all rows which can be imported from the import table.

        Tuple are in this sequence:

        - key: (key of row in import table)
        - original_filename
        - original_dirname
        - metadata_ json string or None if not present
        - google_metadata: json string or None if not present
        - file_hash: hash hex string
        - file_size: in bytes integer
        - datetime: (computed datetime when image was taken)
        - timezone: string of timezone where image was taken
        - naming_tag: string of metadata tag that was used to compute datetime
        - gps_latitude: or None
        - gps_longitude: or None
        - datetime_source: DateTimeSource Object (to determine the quality of the datetime judgement)
        - allowed: Allowed Enum of the file
        - import_key: key in main table as which the file was imported

        :param tbl_name: Import table to iterate over

        :raises sqlite3.OperationalError: If the Import Table doesn't exist
        """
        self.add_extra_cursor("import_cursor")
        self.debug_execute(stmt=f"SELECT key, original_filename, original_dirname, metadata, google_metadata, "
                                f"file_hash, file_size_bytes, datetime, timezone, naming_tag, gps_latitude, "
                                f"gps_longitude, datetime_source, allowed, import_key "
                                f"FROM `{tbl_name}` WHERE imported = 1",
                       cur="import_cursor")

        for row in self.get_cursor("import_cursor"):
            k, ofn, ofd, md, gfmd, fh, fsb, _dt, tz, nt, gps_lat, gps_long, _dts, _allowed, imp_key = row

            k: int
            ofn: str
            ofd: str
            md: str | None
            gfmd: str | None
            fh: str
            fsb: int
            tz: str
            nt: str
            gps_lat: float | None
            gps_long: float | None
            imp_key: int | None

            dt = datetime.datetime.fromisoformat(_dt)
            allowed = Allowed(_allowed)
            dts = DateTimeSource(_dts)

            yield k, ofn, ofd, md, gfmd, fh, fsb, dt, tz, nt, gps_lat, gps_long, dts, allowed, imp_key

        self.remove_extra_cursor("import_cursor")

    def set_imported_status(self, tbl_name: str, key: int, status: ImportStatus, import_key: int = None):
        """
        Set the imported status of a given row of an import table.

        :param tbl_name: import table to update
        :param key: key in table to update
        :param status: status to set
        :param import_key: key in main table as which the file was imported

        :raises sqlite3.OperationalError: If the Import Table doesn't exist
        """
        if status == ImportStatus.IGNORE:

            # PRECONDITION: Row wasn't imported
            # PRECONDITION: Key exists in table
            self.debug_execute(f"UPDATE `{tbl_name}` SET imported = ? WHERE key = ? AND imported != 2",
                               args=(0, key))
            assert self.sq_cur.rowcount == 1, \
                f"Failed to set imported = 0 in table {tbl_name}, key: {key}, PRECONDITION"

        elif status == ImportStatus.MARKED_FOR_IMPORT:

            # PRECONDITION: Row wasn't imported
            # PRECONDITION: Key exists in table
            # PRECONDITION: Key is allowed
            self.debug_execute(stmt=f"UPDATE `{tbl_name}` SET imported = ? "
                                    f"WHERE key = ? AND imported != 2 AND allowed = 1",
                               args=(1, key))
            assert self.sq_cur.rowcount == 1, \
                f"Failed to set imported = 1 in table {tbl_name}, key: {key},PRECONDITION"

        elif status == ImportStatus.IMPORTED:

            if import_key is None:
                raise ValueError("import_key must be specified for imported status IMPORTED")

            # PRECONDITION: Row marked for import
            # PRECONDITION: Key exists in table
            # PRECONDITION: Key is allowed
            self.debug_execute(stmt=f"UPDATE `{tbl_name}` SET imported = ?,  import_key = ? "
                                    f"WHERE key = ? AND imported = 1 AND allowed = 1",
                               args=(2, import_key, key))
            assert self.sq_cur.rowcount == 1, \
                f"Failed to set imported = 2 in table {tbl_name}, key: {key}, PRECONDITION"

        else:
            raise ImplementationError(f"Unknown ImportStatus {status.name}")

    # ==================================================================================================================
    # Presence Table
    # ==================================================================================================================

    def clear_presence_table(self):
        """
        Clear the content of the presence table.
        """
        self.debug_execute("DELETE FROM presence_table")
        self.debug_execute("UPDATE sqlite_sequence SET seq=0 WHERE NAME='presence_table'")

    def presence_table_size(self) -> int:
        """
        Get Number of Row of presence table (needed for gui)
        """
        self.debug_execute("SELECT COUNT(main_key) FROM presence_table")
        return self.sq_cur.fetchone()[0]

    def update_presence_from_table(self, missing: bool = True, mtype: MediaType = MediaType.MAIN) -> int:
        """
        Go through the main table and update the presence of the files from the given presence table.

        Files updated may not be marked as duplicates or trashed

        :param missing: True Perform update from present -> missing; False Perform Update from missing -> present.
        :param mtype: Which type of media to update

        :return: number of rows affected.
        """
        if self.presence_table_size() == 0:
            raise ValueError("Presence Table Empty, nothing to update.")

        if mtype == MediaType.MAIN:
            dup_flag = False
            trash_flag = False
        elif mtype == MediaType.DUPLICATE:
            dup_flag = True
            trash_flag = False
        elif mtype == MediaType.TRASH:
            trash_flag = True
            dup_flag = False
        else:
            raise ImplementationError("Unknown MediaType")

        if missing:
            self.debug_execute(f"SELECT COUNT(key) FROM main "
                               # Check key is in the table                            
                               f"WHERE key IN (SELECT main_key FROM presence_table) "
                               # Check present,             check not duplicate        check not trash
                               f"AND mod(flags, 2) = 1 AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)))
            count = self.sq_cur.fetchone()[0]

            self.debug_execute(f"UPDATE main SET flags = flags - 1 "
                               # Check key is in the table                            
                               f"WHERE key IN (SELECT main_key FROM presence_table) "
                               #     Check present,         check not duplicate        check not trash
                               f"AND mod(flags, 2) = 1 AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)))

        else:
            self.debug_execute(f"SELECT COUNT(key) FROM main "
                               # Check key is in the table                            
                               f"WHERE key IN (SELECT main_key FROM presence_table) "
                               #     Check present,         check not duplicate        check not trash
                               f"AND mod(flags, 2) = 0 AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)))
            count = self.sq_cur.fetchone()[0]

            self.debug_execute(f"UPDATE main SET flags = flags + 1 "
                               # Check key is in the table
                               f"WHERE key IN (SELECT main_key FROM presence_table) "
                               #     Check present,         check not duplicate        check not trash
                               f"AND mod(flags, 2) = 0 AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)))
        self.commit()
        return count

    def selection_from_presence_table(self,
                                      sel_a: bool = True,
                                      missing: bool = True) -> int:
        """
        Set the selection flags based on the images which are eina given table.

        INFO: Doesn't clear previously set flags. i.e. if you selected something before.

        Checks Presence Table Exists and Presence Table isn't stale.

        :param sel_a: Whether to set the sel_a flag or the sel_b flag
        :param missing: Whether to get the files which are missing but marked as present or get the files which are
        present but marked as missing

        :return: Number of rows affected.
        """
        if self.presence_table_size() == 0:
            raise ValueError("Presence Table Empty, nothing to update.")

        if missing and sel_a:
            # Set sel_a if file is missing but marked as presente
            self.debug_execute("UPDATE main SET flags = flags + 16 "
                               "WHERE key IN (SELECT main_key FROM presence_table) "
                               "AND mod(flags >> 4, 2) = 0 AND mod(flags, 2) = 1")

            return self.sq_cur.rowcount

        elif missing and not sel_a:
            # Set sel_b if file is missing but marked as presente
            self.debug_execute("UPDATE main SET flags = flags + 32 "
                               "WHERE key IN (SELECT main_key FROM presence_table) "
                               "AND mod(flags >> 5, 2) = 0 AND mod(flags, 2) = 1")

            return self.sq_cur.rowcount

        elif not missing and sel_a:
            # Set sel_a if file is present but marked as missing
            self.debug_execute("UPDATE main SET flags = flags + 16 "
                               "WHERE key IN (SELECT main_key FROM presence_table) "
                               "AND mod(flags >> 4, 2) = 0 AND mod(flags, 2) = 0")

            return self.sq_cur.rowcount

        elif not missing and not sel_a:
            # Set sel_b if file is present but marked as missing
            self.debug_execute("UPDATE main SET flags = flags + 32 "
                               "WHERE key IN (SELECT main_key FROM presence_table) "
                               "AND mod(flags >> 5, 2) = 0 AND mod(flags, 2) = 0")

            return self.sq_cur.rowcount

        else:
            raise ImplementationError("Tertiem Non Datur")

    # ==================================================================================================================
    # Hash Update Table
    # ==================================================================================================================

    def clear_hash_update_table(self):
        """
        Clear the content of the hash update table.
        """
        self.debug_execute("DELETE FROM hash_update_table")
        self.debug_execute("UPDATE sqlite_sequence SET seq=0 WHERE NAME='hash_update_table'")

    def hash_update_table_size(self) -> int:
        """
        Get the number of rows of the hash hash_updat_table
        """
        self.debug_execute("SELECT COUNT(main_key) FROM hash_update_table")
        return self.sq_cur.fetchone()[0]

    def get_newest_hash(self, key: int) -> Tuple[str, int] | Tuple[None, None]:
        """
        Get the newest hash of a given file. If the newest hash doesn't match, we don't perform binary comparison.

        :param key: File key to search for
        :returns: Tuple[None, None] -> key not found, Tuple[str, int] -> newest hash and file_size_bytes of that hash.
        """
        self.debug_execute("SELECT h.hash, ha.file_size_bytes "
                           "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE ha.file_key = ? AND ha.hash_date IN "
                           "(SELECT MAX(hash_date) FROM hash_assoz WHERE file_key = ?)",
                           (key, key))
        res = self.sq_cur.fetchone()
        if res is None:
            return None, None

        return res[0], res[1]

    # TODO move
    def update_hash_from_filename_table(self) -> Tuple[int, int]:
        """
        Updates the hash of the image file with the given file name.

        :return: number of new entries in hash_assoz table, number of hashes updated
        """
        if self.hash_update_table_size() == 0:
            raise ValueError("Hash table is empty")

        # Get the size of the hash assoz table
        current_size = self.get_size_of_hash_assoz_table()

        self.add_extra_cursor("update_hash")
        self.debug_execute(stmt="SELECT main_key, new_hash, file_size_bytes FROM hash_update_table",
                           cur="update_hash")

        count = 0
        for mk, nh, fsb in self.get_cursor("update_hash"):
            self.check_add_file_hash(file_hash=nh, file_key=mk, file_size=fsb)
            count += 1

        new_size = self.get_size_of_hash_assoz_table()

        self.logger.info(f"Updated {count} file hashes. {new_size - current_size} of unseen hashes.")

        self.remove_extra_cursor("update_hash")
        self.commit()
        return new_size - current_size, count

    # ==================================================================================================================
    # Name Update Table
    # ==================================================================================================================

    def clear_filename_update_table(self):
        """
        Clear the filename update table.
        """
        self.debug_execute("DELETE FROM name_update_table")
        self.debug_execute("UPDATE sqlite_sequence SET seq=0 WHERE NAME='name_update_table'")

    def filename_update_table_size(self) -> int:
        """
        Check whether the filename_update_table contains any entries.
        """
        self.debug_execute("SELECT COUNT(*) FROM name_update_table")
        return self.sq_cur.fetchone()[0]

    # ==================================================================================================================
    # Hash Table
    # ==================================================================================================================

    def get_hash_table_size(self) -> int:
        """
        Get number of unique file hashes
        """
        self.debug_execute("SELECT COUNT(key) FROM hashes")
        return self.sq_cur.fetchone()[0]

    def insert_get_hash_key(self, file_hash: str) -> int:
        """
        Get the Key of a given hash string in the hash table. If it doesn't exist, add it to the hash table.
        """
        self.debug_execute("SELECT key FROM hashes WHERE hash = ?", (file_hash,))
        res = self.sq_cur.fetchone()

        if res is not None:
            return res[0]

        # PRECONDITION: Hash string doesn't exist
        self.debug_execute("INSERT INTO hashes (hash) VALUES (?)", (file_hash,))
        key = self.insert_get_hash_key(file_hash)
        return key

    def prune_hash(self) -> int:
        """
        Remove all rows in the hash table which are no longer referenced

        :return: Number of rows removed
        """
        self.debug_execute("SELECT COUNT(key) FROM hashes AS h WHERE h.key NOT IN (SELECT hash_key FROM hash_assoz)")
        count = self.sq_cur.fetchone()[0]

        self.debug_execute("DELETE FROM hashes WHERE key NOT IN (SELECT hash_key FROM hash_assoz)")
        if count > 0:
            self.logger.info(f"Pruned {count} rows in hash table")
        else:
            self.logger.debug("Call to prune_hash, no hashes pruned")
        return count

    # ==================================================================================================================
    # GPS Table
    # ==================================================================================================================

    def get_gps_table_size(self) -> int:
        """
        Get number of unique file hashes
        """
        self.debug_execute("SELECT COUNT(key) FROM gps_location")
        return self.sq_cur.fetchone()[0]

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

    def prune_gps(self) -> int:
        """
        Remove all rows in the gps table which are no longer referenced

        :return: Number of rows removed
        """
        self.debug_execute("SELECT COUNT(key) FROM gps_location WHERE key NOT IN (SELECT gps_location FROM metadata)")
        count = self.sq_cur.fetchone()[0]

        self.debug_execute("DELETE FROM gps_location WHERE key NOT IN (SELECT gps_location FROM metadata)")
        if count > 0:
            self.logger.info(f"Pruned {count} rows in gps table")
        else:
            self.logger.debug(f"Call to prune_gps, no rows pruned")
        return count

    # ==================================================================================================================
    # Dir Table
    # ==================================================================================================================

    def get_db_dir_count(self):
        """
        Get number of rows of custom directories in the db_dir table
        """
        self.debug_execute("SELECT COUNT(key) FROM db_dir")
        return self.sq_cur.fetchone()[0]

    def get_dir_key(self, local_dir: List[str]) -> int | None:
        """
        Resolve local_dir to key or None if it doesn't exist
        """
        self.debug_execute("SELECT key FROM db_dir WHERE db_local_dir = ?",
                           (self.dump_db_local_dir(local_dir),))

        res = self.sq_cur.fetchone()
        if res is None:
            return None

        return res[0]

    def insert_get_dir(self, local_dir: List[str]) -> int:
        """
        Get the key of a given custom directory.

        :param local_dir: List of Directory names starting at the root_path from database model
        """
        # rel_path = dir_name.removeprefix(self.root_path).removeprefix(os.sep)
        # rel_path_list = rel_path.split(os.sep)

        key = self.get_dir_key(local_dir)
        if key is not None:
            return key

        self.debug_execute("INSERT INTO db_dir (db_local_dir) VALUES (?)",
                           (self.dump_db_local_dir(local_dir),))
        self.logger.debug(f"Added custom dir {os.path.join(*local_dir)}")
        return self.insert_get_dir(local_dir)

    def prune_db_dir_iterator(self) -> Iterator[Tuple[int, List[str]]]:
        """
        Get an iterator to all custom directories which are now empty.
        """
        self.add_extra_cursor("prune_db_dir")
        self.debug_execute("SELECT key, db_local_dir FROM db_dir WHERE key NOT IN (SELECT db_dir FROM metadata)")

        for row in self.get_cursor("prune_db_dir"):
            yield row[0], self.parse_db_local_dir(row[1])

        self.remove_extra_cursor("prune_db_dir")

    # ==================================================================================================================
    # Hash Assoz Table
    # ==================================================================================================================

    def get_size_of_hash_assoz_table(self) -> int:
        """
        Get the size of the hash_assoz table
        """
        self.debug_execute("SELECT COUNT(*) FROM hash_assoz")
        return self.sq_cur.fetchone()[0]

    def _find_hash_match_keys(self, target_hash: str, file_size: int, mode: str) -> List[int]:
        """
        Given a hash and file size, finds all file_keys which share this hash.

        mode (case-insensitive):

        - EARLIEST, given a file_key, only take into account the earliest hash of that file
        - LATEST, given a file_key, only take into account the latest hash of that file (detecting changed filenames)
        - ANY, given a file_key, take into account all hashes the file has had (detecting duplicates)
        - INITIAL, given a file_key, only look at initial hashes (importing)

        :param target_hash: Target hash to search for
        :param file_size: File size to search for
        :param mode: Mode to search for, can be EARLIEST, LATEST, ANY

        :returns: List[int] - list of matching file_keys
        """
        if mode.lower() not in ("earliest", "latest", "any", "initial"):
            raise ValueError(f"Unsupported mode: {mode.lower()}, allowed: [earliest, latest, any]")

        if mode.lower() == "earliest":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hashes AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.hash_date IN "
                               "(SELECT MIN(datetime(ha.hash_date)) "
                               "FROM hash_assoz AS ha JOIN hash ON hash.key = ha.hash_key "
                               "WHERE hash.hash = ? AND ha.file_size_bytes = ? GROUP BY hash_key, file_key)",
                               (target_hash, file_size, target_hash, file_size))

        elif mode.lower() == "latest":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hashes AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.hash_date IN "
                               "(SELECT MAX(datetime(ha.hash_date)) "
                               "FROM hash_assoz AS ha JOIN hash ON hash.key = ha.hash_key "
                               "WHERE hash.hash = ? AND ha.file_size_bytes = ? GROUP BY hash_key, file_key)",
                               (target_hash, file_size, target_hash, file_size))
        elif mode.lower() == "any":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hashes AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ?",
                               (target_hash, file_size))
        elif mode.lower() == "initial":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hashes AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.initial = 1")
        else:
            raise ImplementationError(f"Got unexpected mode {mode.lower()}")

        return [r[0] for r in self.sq_cur.fetchall()]

    # ==================================================================================================================
    # DB Integrity checks and utility
    # ==================================================================================================================

    def update_filename_from_hash(self, move: bool):
        """
        Update the names of files resolved through hash and filesize.

        # INFO: Update only possible for files which are neither a duplicate nor trashed.
        # INFO: Given all MatchTypes, the function only considers HASH_MATCH_MAIN

        :parma move: move the file to the correct location based on it's datetime.
        """
        self.add_extra_cursor("update_filename")
        self.debug_execute("SELECT key, name, dir_name, best_match FROM name_update_table "
                           # Ensure match is HASH_MATCH_MAIN
                           "WHERE best_match IS NOT NULL AND updated = 0 AND match_type = 2")

        count = 0
        conflict = 0
        for key, name, dir_name, best_match in self.get_cursor("name_update_table"):
            assert best_match is not None, "best_match shouldn't be None, SQL Error"

            # Try to get the parent's path
            tgt_path = self._db_resolve_key_to_abs_path(best_match)
            if tgt_path is None:
                self.debug_execute("UPDATE name_update_table SET updated = 2, message = ? WHERE key = ?",
                                   ("Matched key doesn't exist in main table", key))
                conflict += 1
                continue

            if os.path.exists(tgt_path):
                self.debug_execute("UPDATE name_update_table SET updated = 2, message = ? WHERE key = ?",
                                   ("Parent File is Present", key))
                conflict += 1
                continue

            # Determine target location
            if not move:
                dst_path = os.path.join(dir_name, name)
            else:
                dst_path = os.path.join(os.path.dirname(tgt_path), name)

            # Check if the destination exists.
            if os.path.exists(dst_path):
                self.debug_execute("UPDATE name_update_table SET updated = 2, message = ? WHERE key = ?",
                                   ("File exists at destination", key))
                conflict += 1
                continue

            flags = self.get_main_flags(best_match)
            assert flags is not None, "Flags should exist, if path resolved"

            if flags.trashed or flags.duplicate:
                self.debug_execute("UPDATE name_update_table SET updated = 2, message = ? WHERE key = ?",
                                   (f"Parent is trash or duplicate, not allowd to upadte. ", key))
                conflict += 1

            # Need to update
            dir_key = None
            if os.path.dirname(dst_path) != os.path.dirname(tgt_path):
                dir_key = self.insert_get_dir(os.path.dirname(dst_path))

            os.rename(os.path.join(dir_name, name), os.path.join(os.path.dirname(tgt_path), name))
            flags.present = True

            self.debug_execute("UPDATE name_update_table SET updated = 1 WHERE key = ?", (key,))
            self.debug_execute("UPDATE main SET db_name = ?, flags = ? WHERE key = ?",
                               (name, flags.to_int(), best_match))
            if dir_key is not None:
                self.debug_execute("UPDATE metadata SET db_dir = ? WHERE key = ?", (dir_key, key))

            count += 1

        self.commit()
        return count, conflict

    def update_trash_flag_from_selection(self, selection: Selection, target_value: bool):
        """
        Update the files which have aren't present to have been moved to the trash.

        :param selection: Selection of Files to update
        :param target_value: bool, whether to set the flag to True or False
        """
        if target_value:
            update_stmt = "UPDATE main SET flags = flags + 4 "
            args = tuple()

            # handle selection
            if selection.selection_type == SelectionType.SELECTION_A:
                where_stmt = "WHERE mod(flags >> 2, 2) = 0 AND mod(flags >> 4, 2) = 1"
            elif selection.selection_type == SelectionType.SELECTION_B:
                where_stmt = "WHERE mod(flags >> 2, 2) = 0 AND mod(flags >> 5, 2) = 1"
            elif selection.selection_type == SelectionType.TIME_RANGE:
                where_stmt = ("WHERE mod(flags >> 2, 2) = 0 "
                              "AND datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?)")
                args = (selection.start.isoformat(), selection.end.isoformat())
            else:
                raise ImplementationError("Unknown selection type")

            assert where_stmt is not None, "Where statement needed"

            # Get affected rows
            self.debug_execute(stmt="SELECT COUNT(key) FROM main " + where_stmt,
                               args=args)
            count = self.sq_cur.fetchone()[0]

            # Execute statement
            self.debug_execute(stmt=update_stmt + where_stmt, args=args)
        else:
            update_stmt = "UPDATE main SET flags = flags - 4 "
            args = tuple()

            # handle selection
            if selection.selection_type == SelectionType.SELECTION_A:
                where_stmt = "WHERE mod(flags >> 2, 2) = 1 AND mod(flags >> 4, 2) = 1"
            elif selection.selection_type == SelectionType.SELECTION_B:
                where_stmt = "WHERE mod(flags >> 2, 2) = 1 AND mod(flags >> 5, 2) = 1"
            elif selection.selection_type == SelectionType.TIME_RANGE:
                where_stmt = ("WHERE mod(flags >> 2, 2) = 1 "
                              "AND datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?)")
                args = (selection.start.isoformat(), selection.end.isoformat())
            else:
                raise ImplementationError("Unknown selection type")

            assert where_stmt is not None, "Where statement needed"

            # Get affected rows
            self.debug_execute(stmt="SELECT COUNT(key) FROM main " + where_stmt,
                               args=args)
            count = self.sq_cur.fetchone()[0]

            # Execute statement
            self.debug_execute(stmt=update_stmt + where_stmt, args=args)

        self.main_logger.debug(f"updated {count} entries in main table to have trash flag = {target_value} "
                               f"where selection type = {selection}")
        self.commit()
        return count

    # INFO: long-running action,
    def check_presence(self, selection: Selection = None, mtype: MediaType = MediaType.MAIN):
        """
        Go through db and check that all files in the db are present in the file system.

        :param selection: Use selection marker of images to check changed hashes for those images.
        :param mtype: For which type of media to update the presence.
        """
        self.clear_presence_table()
        count = 0

        self.add_extra_cursor("check_presence")

        if mtype == MediaType.MAIN:
            dup_flag = False
            trash_flag = False
        elif mtype == MediaType.DUPLICATE:
            dup_flag = True
            trash_flag = False
        elif mtype == MediaType.TRASH:
            trash_flag = True
            dup_flag = False
        else:
            raise ImplementationError("Unknown MediaType")

        if selection is None:
            self.debug_execute("SELECT key, flags FROM main "
                               # Check not duplicate             Check not trash
                               "WHERE mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)),
                               cur="check_presence")
        else:
            if selection.selection_type == SelectionType.SELECTION_A:
                self.debug_execute("SELECT key, flags FROM main "
                                   # Check not duplicate             Check not trash            Check selection A
                                   "WHERE mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ? AND mod(flags >> 4, 2) = 1",
                                   args=(int(dup_flag), int(trash_flag)),
                                   cur="check_presence")
            elif selection.selection_type == SelectionType.SELECTION_B:
                self.debug_execute("SELECT key, flags FROM main "
                                   # Check not duplicate             Check not trash            Check selection B
                                   "WHERE mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ? AND mod(flags >> 5, 2) = 1",
                                   args=(int(dup_flag), int(trash_flag)),
                                   cur="check_presence")
            elif selection.selection_type == SelectionType.TIME_RANGE:
                self.debug_execute(stmt="SELECT key, flags FROM main "
                                        "WHERE datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?) "
                # Check not duplicate             Check not trash
                                        "AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                                   args=(selection.start.isoformat(), selection.end.isoformat(),
                                         int(dup_flag), int(trash_flag)),
                                   cur="check_disp_files")
            else:
                raise ImplementationError("Missing Selection Type")

        # Go through all files and check if they exist.
        for key, _flags in self.get_cursor("check_presence"):
            flags = MainFlags.from_int(_flags)

            # Internal checks for general sql statement integrity
            assert flags.trashed == trash_flag and flags.duplicate ==  dup_flag, \
                "SQL Error, no trashed or duplicate files allowed"

            # Check selection.
            if __debug__:
                if selection.selection_type == SelectionType.SELECTION_A and not flags.sel_a:
                    raise ImplementationError("Didn't receive Selection A")
                elif selection.selection_type == SelectionType.SELECTION_B and not flags.sel_b:
                    raise ImplementationError("Didn't receive Selection B")

            # Don't want to fuck up cache.
            self.check_flags(key=key, flags=flags, miniature=True, thumbnail=True)
            path = self._db_resolve_key_to_abs_path(key)

            if os.path.exists(path) and not flags.present:
                self.debug_execute(f"INSERT INTO presence_table (main_key) VALUES (?)", (key,))
                count += 1

            elif not os.path.exists(path) and flags.present:
                self.debug_execute(f"INSERT INTO presence_table (main_key) VALUES (?)", (key,))
                count += 1

        self.remove_extra_cursor("check_presence")
        self.commit()

        self.main_logger.info(f"Detected {count} entries in main table with mismatched presence flag")
        return count

    # INFO: long-running action
    def check_filenames(self):
        """
        Check the file names by associating file hashes from files found in the db with files.

        The function checks whether the name is known in the db. If it is, it will be
        """
        self.clear_filename_update_table()

        count = 0
        add_mda = False
        if self.mda is None:
            self.add_default_metadata_aggregator()
            add_mda = True

        for root, dirs, files in os.walk(self.root_path):
            if root == self.get_temp_dir():
                continue

            if root == self.get_temp_dir():
                continue

            if root == self.get_thumb_dir():
                continue

            for file in files:
                tgt_key = self._db_resolve_filename_to_key(file)

                if tgt_key is not None:
                    continue

                fsb = os.stat(os.path.join(root, file)).st_size
                fh = self.mda.hash_file(os.path.join(root, file))

                self.debug_execute(stmt="INSERT INTO name_update_table (name, dir_name, file_size_bytes, hash) "
                                        "VALUES (?, ?, ?, ?)",
                                   args=(file, root, fsb, fh))
                count += 1

        if add_mda:
            self.mda = None

        if count == 0:
            return 0

        self.add_extra_cursor("update_names")
        self.debug_execute("SELECT key, name, dir_name, file_size_bytes, hash")

        for key, name, dir_name, fsb, fh in self.get_cursor("update_names"):
            name: str
            dir_name: str

            matches, best_match, best_match_type = \
                self._get_best_match_type(file_hash=fh, fsb=fsb, tgt_fp=os.path.join(dir_name, name))

            serializable_matches = {k: v.value for k, v in matches.items()}
            self.debug_execute(stmt="UPDATE name_update_table SET matches = ?, best_match = ?, best_match_type = ? "
                                    "WHERE key = ?",
                               args=(json.dumps(serializable_matches), matches, best_match, key))

        self.commit()
        return count

    # INFO: long-running action
    def check_file_hashes(self, selection: Selection = None):
        """
        Check the file hashes based on the file names.

        INFO: Only files which aren't duplicates and which aren't in the trash are considered
        """
        self.clear_hash_update_table()
        self.add_extra_cursor("check_file_hashes")
        count = 0

        added_mda = False
        if self.mda is None:
            self.add_default_metadata_aggregator()
            added_mda = True

        if selection is None:
            self.debug_execute("SELECT key, flags FROM main "
                               # Check not duplicate             Check not trash
                               "WHERE mod(flags >> 8, 2) = 0 AND mod(flags >> 2, 2) = 0",
                               cur="check_file_hashes")
        else:
            if selection.selection_type == SelectionType.SELECTION_A:
                self.debug_execute("SELECT key, flags FROM main "
                                   # Check not duplicate             Check not trash            Check selection A
                                   "WHERE mod(flags >> 8, 2) = 0 AND mod(flags >> 2, 2) = 0 AND mod(flags >> 4, 2) = 1",
                                   cur="check_file_hashes")
            elif selection.selection_type == SelectionType.SELECTION_B:
                self.debug_execute("SELECT key, flags FROM main "
                                   # Check not duplicate             Check not trash            Check selection B
                                   "WHERE mod(flags >> 8, 2) = 0 AND mod(flags >> 2, 2) = 0 AND mod(flags >> 5, 2) = 1",
                                   cur="check_file_hashes")
            elif selection.selection_type == SelectionType.TIME_RANGE:
                self.debug_execute(stmt="SELECT key, flags FROM main "
                # Check datetime range
                                        "WHERE datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?) "
                # Check not duplicate             Check not trash
                                        "AND mod(flags >> 8, 2) = 0 AND mod(flags >> 2, 2) = 0",
                                   args=(selection.start.isoformat(), selection.end.isoformat()),
                                   cur="check_file_hashes")
            else:
                raise ImplementationError("Missing Selection Type")

        for key, _flags in self.get_cursor("check_file_hashes"):
            flags = MainFlags.from_int(_flags)
            org_path = self._db_resolve_key_to_abs_path(key)

            # Checks on path and flags
            assert org_path is not None, "Key in main table should resolve to path"
            self.check_flags(key=key, flags=flags, org_path=org_path, miniature=True, thumbnail=True)

            if __debug__ and (flags.trashed or flags.duplicate):
                raise ImplementationError("SQL Statement Error, shouldn't get duplicates or trashed files")

            # Cannot hash what doesn't exist
            if not os.path.exists(org_path):
                continue

            # Get current hash and file size
            new_hash = self.mda.hash_file(org_path)
            file_size_bytes = os.stat(org_path).st_size

            # Get the newest file hash of that file from the db
            h, fsb = self.get_newest_hash(key)

            # Different hash, update
            if new_hash != h:
                self.debug_execute(stmt="INSERT INTO hash_update_table "
                                        "(main_key, new_hash, file_size_bytes)"
                                        "VALUES (?, ?, ?)",
                                   args=(key, new_hash, file_size_bytes))
                count += 1

            # Rare occurrence
            elif file_size_bytes != new_hash and new_hash == h:
                # TODO change logger
                self.main_logger.info(f"Rare Occurrence: File Size changed but hash stayed the same: {org_path}")

        self.remove_extra_cursor("check_file_hashes")
        self.commit()

        if added_mda:
            self.mda = None
        return count

    # INFO: long-running action
    def check_new_files(self, allowed_ext: Set[str] = None) -> None | Tuple[str, int]:
        """
        Search the database folder itself for new files which were added by the user. Basically performs identical
        operation to import.

        Files are determined to be new, if the filename doesn't exist in the database. That means, if you remove a file
        with name n and add a different file with name n, this function will not detect the file as new and ignore it.

        :param allowed_ext: Allowed file extensions.

        :returns: None if no new files were detected. Tuple[import_table_name, new_file_count]
        """
        # Create import table
        tbl_name = self._add_import_table(root_path=self.root_path,
                                          internal=True,
                                          description="Internal Import, detect new files in db")

        if allowed_ext is None:
            allowed_ext = set(defaults.video_extensions + defaults.image_extensions)

        new_files = 0

        # Walk the directory
        for root, dirs, files in os.walk(self.root_path):

            # We're not importing from temp
            if root == self.get_temp_dir():
                continue

            # We're not importing from thumbnails
            if root == self.get_thumb_dir():
                continue

            # We're not importing from trash
            if root == self.get_trash_dir():
                continue

            for file in files:
                key = self._db_resolve_filename_to_key(file)

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
                    path = self.resolve_key_to_path(key)

                    if not path == os.path.join(root, file):
                        self.integrity_logger.warning(f"File {file} found in db but path mismatch:"
                                                      f"DB-Path: {path}, Discover Path: {os.path.join(root, file)}")

        if new_files == 0:
            self.main_logger.info("No new files in db were detected. Removing empty import table.")
            self.remove_import_table(tbl_name)
            return None

        self.commit()
        return tbl_name, new_files

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

        if not self.import_table_exists(tbl):
            raise ValueError(f"Tabl {tbl} does not exist")

        if not self._import_table_flags(tbl).internal:
            raise ValueError("Cannot use this function with non-internal import table")

        if add_safety_exif_tags is None:
            add_safety_exif_tags = self.config.add_safety_exif_tags

        added_mda = False
        if self.mda is None and add_safety_exif_tags:
            self.add_default_metadata_aggregator()
            added_mda = True

        for row in self.perform_import_iterator(tbl):
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
                if self._db_resolve_filename_to_key(ofn) is not None:
                    self.set_allowed(tbl_name=tbl, key=ik, allowed=Allowed.NOT_ALLOWED_ERR,
                                     message=f"File {ofn} already exists")
                    self.main_logger.info(f"Couldn't import file {ofn}, filename already used in db")
                    name_conflict += 1
                    continue

                db_name = ofn
            else:
                db_name = self.temp_db_name

            # Add row in main table
            # TODO GFMD and MD can be None
            self.debug_execute(f"INSERT INTO main "
                               f"(original_filename, metadata, google_metadata, db_name,"
                               f" datetime, timezone, flags) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (ofn, md, gfmd, db_name, _dt, tz, flags.to_int()))

            insert_key = self._db_resolve_filename_to_key(self.temp_db_name)
            assert insert_key is not None, "Key should exist after insert."

            # Handle metadata table
            self.debug_execute("INSERT INTO metadata (main_key, original_dirname, naming_tag, datetime_source) "
                               "VALUES (?, ?, ?, ?)", args=(insert_key, ofd, nt, _dts))

            # Handle GPS
            assert (gps_lat is not None and gps_long is not None) or (gps_lat is None and gps_long is None), \
                "gps_lat and gps_long unequally set."
            if gps_lat is not None and gps_long is not None:
                gps_key = self.insert_get_gps_loc(gps_lat=gps_lat, gps_long=gps_long)

                self.debug_execute("UPDATE metadata SET gps_location = ? WHERE main_key = ?",
                                   (gps_key, insert_key))

            # Handle hash
            assert fh is not None, "File Hash needs to be defined"
            self.check_add_file_hash(file_key=insert_key, file_hash=fh, file_size=fsb, initial=True)

            target_path = self._handle_file_internal_import(rename=rename, move=move,
                                                            dt=dt, main_key=insert_key, ofn=ofn, ofd=ofd)

            # Update the name in the db
            if rename:
                self.debug_execute("UPDATE main SET db_name = ? WHERE key = ?",
                                   (self.db_name(original_filename=ofn, key=insert_key, fdt=dt), insert_key))

            if flags.verify and add_safety_exif_tags:
                self._add_update_exif_tag(key=insert_key, target_datetime=dt, file_path=target_path)

            self.set_imported_status(tbl_name=tbl, import_key=insert_key, status=ImportStatus.IMPORTED, key=ik)

            count += 1

        if added_mda:
            self.mda = None

        self.commit()
        return count, name_conflict

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
            target_path = os.path.join(self.root_path, self.dt_to_dir(dt),
                                       self.db_name(original_filename=ofn, key=main_key, fdt=dt))

            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            assert not os.path.exists(target_path), "Target path is not supposed to exist"
            os.rename(os.path.join(ofd, ofn), target_path)

        elif not rename and move:
            target_path = os.path.join(self.root_path, self.dt_to_dir(dt), ofn)

            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            if os.path.exists(target_path):
                # Remove rows inserted for the file before raising error.
                self.debug_execute("DELETE FROM main WHERE key = ?", (main_key,))
                self.debug_execute("DELETE FROM metadata WHERE main_key = ?", (main_key,))
                self.commit()
                raise FileExistsError(f"Couldn't import {ofn}, file already exists in {self.dt_to_dir(dt)}")

            os.rename(os.path.join(ofd, ofn), target_path)

        elif rename and not move:
            ofd: str
            assert ofd.startswith(self.root_path), "Erroneous import, original_dir_name should start with root_dir"
            target_path = os.path.join(ofd, self.db_name(original_filename=ofn, key=main_key, fdt=dt))

            # Check if the directory matches the datetime
            if os.path.dirname(target_path) != os.path.join(self.root_path, self.dt_to_dir(dt)):
                db_local_dir = os.path.dirname(target_path)
                dir_key = self.insert_get_dir(dir_name=db_local_dir)
                self.debug_execute("UPDATE metadata SET db_dir = ? WHERE main_key = ?", (dir_key, main_key))

            assert not os.path.exists(target_path), "Target path is not supposed to exist"
            os.rename(os.path.join(ofd, ofn), target_path)

        elif not rename and not move:
            target_path = os.path.join(ofd, ofn)
            dt_dir = os.path.join(self.root_path, self.dt_to_dir(dt))

            # Need to add a db_local_dir if the directory doesn't match the datetime of the image
            if ofd != dt_dir:
                dir_key = self.insert_get_dir(ofd)
                self.debug_execute("UPDATE metadata SET db_dir = ? WHERE main_key = ?", (dir_key, main_key))

        else:
            raise ImplementationError("Tertiem Non Datur")

        return target_path

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
        for raw in self.prune_db_dir_iterator():
            ktd = raw[0]
            db_local_dir = self.parse_db_local_dir(raw[1])

            first = True
            for i in range(len(db_local_dir)):
                tgt_dir = os.path.join(self.root_path, *db_local_dir[:len(db_local_dir) - i])
                if not os.path.exists(tgt_dir):
                    continue

                # path exists
                if os.listdir(tgt_dir):
                    if first:
                        self.integrity_logger.warning(f"Lowest Directory Not Empty: {tgt_dir}")

                    # directory not empty, abort delete.
                    break

                # No guard triggered, we're deleting at last
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

            # Skip if we're in the thumbnail directory
            if root == self.get_thumb_dir():
                continue

            # Skip if we're in the trash directory
            if root == self.get_trash_dir():
                continue

            # Skip if we're in the temp directory
            if root == self.get_temp_dir():
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
            if self.get_dir_key(local_path_list) is not None:
                continue

            # PRECONDITION: Directory is empty and not listed in the db_dir table, deleting
            self.main_logger.debug(f"Pruned {count} rows in dir table")
            shutil.rmtree(d)
            count += 1

        return count

    # ==================================================================================================================
    # DB functions (functions operating only on the DB - basically wrapper for multiple sql statements)
    # ==================================================================================================================

    # Get Functions
    # -------------
    def _get_rename_data(self, key: int) -> Tuple[int, datetime.datetime, MainFlags, str, str, str]:
        """
        Get the necessary data from the database to rename a file

        :param key: Key to query the db for

        :returns: Tuple(key, datetime, flags, db_local_dir, db_name, original_name)
        """
        # Get current row
        self.debug_execute("SELECT key, datetime, flags, db_name, original_filename FROM main WHERE m.key = ?",
                           (key,))

        row = self.sq_cur.fetchone()
        if row is None:
            raise ValueError(f"Key {key} does not exist in main table")

        self.debug_execute("SELECT m.main_key, d.db_local_dir "
                           "FROM metadata AS m LEFT OUTER JOIN db_dir AS d ON m.db_dir = d.key WHERE m.main_key = ?")

        db_dir_row = self.sq_cur.fetchone()
        if db_dir_row is None:
            raise ValueError(f"Key {key} does not exist in metadata table")

        metadata_key, db_local_dir = db_dir_row

        main_key, _dt, _flags, db_name, original_name = row
        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        return key, dt, flags, db_local_dir, db_name, original_name

    def get_main_flags(self, key: int) -> None | MainFlags:
        """
        Get the flags from any entry in the main table
        """
        self.debug_execute("SELECT flags FROM main WHERE key = ?", (key,))
        res = self.sq_cur.fetchone()
        if res is None:
            return None

        return MainFlags.from_int(res[0])

    # ==================================================================================================================
    # Importing
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
            file_count = 0
            # Compute Number of files needed for progress bar
            for root, dirs, files in os.walk(source_dir):
                file_count += len(files)

            for root, dirs, files in os.walk(source_dir):
                for f in files:
                    # USE self.add_file_to_import_table()
                    self._prepare_file_import(file_path=os.path.join(root, f),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=append)
        else:
            file_count = len(os.listdir(source_dir))

            for entry in os.listdir(source_dir):
                if os.path.isfile(os.path.join(source_dir, entry)):
                    # USE self.add_file_to_import_table()
                    self._prepare_file_import(file_path=os.path.join(source_dir, entry),
                                              tbl_name=tbl_name,
                                              allowed_ext=allowed_ext,
                                              append=append)
        if mda_set:
            self.mda = None

        self.commit()
        return tbl_name

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

        for row in self.update_allowed_iterator(tbl):
            key, _a, original_filename = row
            allowed = bool(_a)

            # INFO: Need to update mark_for_import to 0, to ensure we don't get any accidental imports of not allowed
            #  files.
            if allowed and os.path.splitext(original_filename)[1] not in allowed_ext:
                now_disallowed += 1
                self.set_allowed(tbl_name=tbl, allowed=Allowed.NOT_ALLOWED_EXT, key=key)
                self.main_logger.debug(f"{key} is now disallowed")

            elif not allowed and os.path.splitext(original_filename)[1] in allowed_ext:
                now_allowed += 1
                self.main_logger.debug(f"{key} is now allowed")
                self.set_allowed(tbl_name=tbl, allowed=Allowed.ALLOWED, key=key)


            else:
                same += 1
                self.main_logger.debug(f"{key} remains the same")

        self.find_match_for_import_table(tbl)
        self.main_logger.info(f"Updated Allowed {tbl}. {now_allowed} now allowed, {now_disallowed} now disallowed, "
                              f"{same} stayed the same")
        self.commit()
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

            matches, highest_key, highest_match = self._get_best_match_type(tgt_fp=target_fp,
                                                                            file_hash=file_hash,
                                                                            fsb=file_size_bytes)

            serializable_matches = {k: v.value for k, v in matches.items()}
            self.debug_execute(stmt=f"UPDATE `{tbl_name}` SET match_type = ?, highest_match = ?, matches = ? "
                                    f"WHERE key = {key}",
                               args=(highest_match.value, highest_match, json.dumps(serializable_matches), key))
            count += 1

        self.main_logger.info(f"Found {count} matches for {tbl_name}")
        self.remove_extra_cursor("match_cursor")
        self.commit()
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

            if not dest_dir.startswith(self.root_path):
                raise ValueError(f"Destination directory {_dest_dir} doesn't exist must be within the database")

        if not self.import_table_exists(name=tbl_name):
            raise ValueError(f"Table {tbl_name} doesn't exist")

        if self._import_table_flags(tbl_name).internal:
            raise TypeError("cannot import internal import table with perform_import")

        added_mda = False
        if self.mda is None and add_safety_exif_tags:
            self.add_default_metadata_aggregator()
            added_mda = True

        count = 0
        for row in self.perform_import_iterator(tbl_name):
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
            # TODO gfmd and md can be None
            self.debug_execute(f"INSERT INTO main "
                               f"(original_filename, metadata, google_metadata, db_name,"
                               f" datetime, timezone, flags) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (ofn, md.replace("'", "''"), gfmd.replace("'", "''"), self.temp_db_name,
                                _dt, tz, default_flags.to_int()))
            insert_key = self._db_resolve_filename_to_key(self.temp_db_name)
            assert insert_key is not None, "Key should exist after insert."

            # Handle metadata table
            self.debug_execute("INSERT INTO metadata (main_key, original_dirname, naming_tag, datetime_source) "
                               "VALUES (?, ?, ?, ?)", args=(insert_key, ofd, nt, _dts))

            # Handle GPS
            assert (gps_lat is not None and gps_long is not None) or (gps_lat is None and gps_long is None), \
                "gps_lat and gps_long unequally set."
            if gps_lat is not None and gps_long is not None:
                gps_key = self.insert_get_gps_loc(gps_lat=gps_lat, gps_long=gps_long)

                self.debug_execute("UPDATE metadata SET gps_location = ? WHERE main_key = ?",
                                   (gps_key, insert_key))

            # Handle hash
            assert fh is not None, "File Hash needs to be defined"
            self.check_add_file_hash(file_key=insert_key, file_hash=fh, file_size=fsb, initial=True)

            self._import_file(original_filename=ofn,
                              original_dirname=ofd,
                              fdt=dt,
                              tgt_dir=dest_dir,
                              key=import_key,
                              add_tag=add_safety_exif_tags and default_flags.verify)

            # Finally update the import table
            self.set_imported_status(tbl_name=tbl_name, key=k, status=ImportStatus.IMPORTED, import_key=insert_key)
            count += 1

        if added_mda:
            self.mda = None

        self.commit()
        return count

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
            dir_key = self.insert_get_dir(tgt_dir)
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
            self._add_update_exif_tag(key=key, file_path=os.path.join(tgt_dir, db_name), target_datetime=fdt)

        self.debug_execute("UPDATE main SET db_name = ? WHERE key = ?",
                           (db_name, key))
        self.debug_execute("UPDATE metadata SET db_dir = ? WHERE main_key = ?",
                           (dir_key, key))

    def _get_best_match_type(self, tgt_fp: str, file_hash: str, fsb: int) \
            -> Tuple[Dict[int, NewMatchTypes], int | None, NewMatchTypes]:
        """
        PRECONDITION: tgt_fp exists.

        Given a file_hash and file_size returns the lowest

        :param tgt_fp: Target file path of the image in the import table
        :param file_hash: File hash of the image
        :param fsb: File size of the image

        :returns List of all hash_matches, key of highest match, highest match value
        """
        match_keys = self._find_hash_match_keys(target_hash=file_hash, file_size=fsb, mode="INITIAL")

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

            m_newest_hash, _ = self.get_newest_hash(m_key)

            # Rare occurrence
            # TODO different logger
            if m_newest_hash == file_hash and not binary_match:
                self.main_logger.warning("Found files with matching hash and size but different binary.")
            elif m_newest_hash != file_hash and binary_match:
                self.main_logger.warning("Found files different hashes but match binary.")

            flags = self.get_main_flags(m_key)
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

    def check_add_file_hash(self, file_key: int,
                            file_size: int,
                            file_hash: str,
                            initial: bool = False) -> bool:
        """
        Checks if a given row in the hash_assoz table exists provided a file_hash, a file_size and file_key.

        Adds the row if it doesn't exist.

        :param file_hash: The hash of the file to check.
        :param file_size: The size of the file to check.
        :param file_key: The key of the file to check.
        :param initial: If this the hash gotten when hashing in the source directory of the import.

        :return: True if the row exists, False if the rows were added.
        """
        # Consider the hashes a set of all hashes the file had at a given point. The hash to check during import is the one marked with initial
        self.debug_execute("SELECT h.hash, ha.hash_key, ha.file_key "
                           "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE h.hash = ? AND ha.file_key = ? AND ha.file_size_bytes = ? AND ha.initial = ?",
                           (file_hash, file_key, file_size, int(initial)))

        res = self.sq_cur.fetchone()

        # Row not found, need to add a new one.
        if res is None:
            now = datetime.datetime.now(datetime.timezone.utc)
            hash_key = self.insert_get_hash_key(file_hash=file_hash)
            self.debug_execute("INSERT INTO hash_assoz (hash_key, file_key, file_size_bytes, hash_date, initial) "
                               "VALUES (?, ?, ?, ?, ?)",
                               (hash_key, file_key, file_size, now.isoformat(), int(initial)))
            return False

        # Parse the row and get the newest hash
        hash_str, hash_key, file_key = res
        newest_hash, _ = self.get_newest_hash(res[1])

        # Check the given hash is the newest hash of the file.
        if newest_hash != file_hash:
            ndt = datetime.datetime.now(datetime.timezone.utc)
            # Update the row to be the newest one.
            self.debug_execute(stmt="UPDATE hash_assoz "
                                    "SET hash_date = ? "
                                    "WHERE hash_key = ? AND file_key = ? AND file_size_bytes = ? AND initial = 0",
                               args=(ndt.isoformat(), hash_key, file_key, file_size))

        return True

    def _add_update_exif_tag(self, key: int, target_datetime: datetime.datetime, file_path: str):
        """
        Add the exif tag that the database uses to the file.

        PRECONDITION:

        - file_path exists
        - target_datetime different from current datetime
        - target_datetime is timezone aware.

        :param key: Key in main table of file to update exiftag for
        :param target_datetime: New datetime to set
        """
        # Add the tag
        self.mda.eth.set_tags(files=[file_path], tags=self.exif_tag_creator(target_datetime))

        # Get Size of File and new File Hash
        new_hash = self.mda.hash_file(file_path)
        new_size = os.stat(file_path).st_size
        assert new_size is not None, "New Size needed for update."
        self.check_add_file_hash(file_key=key, file_hash=new_hash, file_size=new_size, initial=False)

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

    def add_default_duplicate(self, key_a: int | List[int], key_b: int | List[int], delta: float | List[float] = None):
        """
        Add a pair into the duplicate table. If no delta is provided, a default of 0 is added.

        :param key_a: The key of the first media file.
        :param key_b: The key of the second media file.
        :param delta: The delta metric between the images.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=False, add=True, delta=delta)

    def remove_default_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Removes a pair of duplicates from the known_duplicates table.

        :param key_a: The key of the first media file.
        :param key_b: The key of the second media file.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=False, add=False)

    def add_known_duplicate(self, key_a: int | List[int], key_b: int | List[int], delta: float | List[float] = None):
        """
        Moves a pair of duplicates into the known_duplicates table.

        :param key_a: The key of the first media file.
        :param key_b: The key of the second media file.
        :param delta: The delta metric between the images.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=True, add=True, delta=delta)

    def remove_known_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Removes a pair of duplicates from the known_duplicates table.

        :param key_a: The key of the first media file.
        :param key_b: The key of the second media file.
        """
        self._internal_modify_duplicates(key_a=key_a, key_b=key_b, known=True, add=False)

    def _internal_modify_duplicates(self, key_a: int | List[int],
                                    key_b: int | List[int],
                                    known: bool,
                                    add: bool,
                                    delta: float | List[float] = None):
        """
        Internal Function to add or remove a duplicate tuple, parametrizes the table to modify and operation.

        :param key_a: First key of Tuple
        :param key_b: Second key of Tuple
        :param known: If true, will remove the tuple from the known_duplicates table else duplicates table.
        :param add: if true, will add the tuple to the table, else remove the tuple.
        :param delta: Delta metric to add for the duplicates. (Only affects add calls)
        """
        tbl = "known_duplicates" if known else "duplicates"

        if add:
            if delta is not None:
                op = f"INSERT OR IGNORE INTO `{tbl}` (key_a, key_b) VALUES (?, ?)"
            else:
                op = f"INSERT OR IGNORE INTO `{tbl}` (key_a, key_b, delta) VALUES (?, ?, ?)"
        else:
            op = f"DELETE FROM `{tbl}` WHERE key_a = ? AND key_b = ?"

        if isinstance(key_a, int) and isinstance(key_b, int):
            if delta is not None:
                if not isinstance(delta, float):
                    raise TypeError("float required if key_a and key_b are int")

            if key_b == key_a:
                raise ValueError("Identical Keys.")

            if key_a >= key_b:
                key_a, key_b = key_b, key_a

            args = (key_a, key_b) if delta is None else (key_a, key_b, delta)

            self.debug_execute(op, args)

        elif isinstance(key_a, list) and isinstance(key_b, list):
            if not len(key_a) == len(key_b):
                raise ValueError("key_a and key_b must have same length")

            if delta is not None:
                if not isinstance(delta, list):
                    raise TypeError("List[float] required if key_a and key_b are List[int]")

                if not len(key_a) == len(delta):
                    raise ValueError("delta and key_x must have the same length")

            args = []
            if delta is None:
                for ka, kb in zip(key_a, key_b):
                    if ka == kb:
                        raise ValueError("Identical Keys.")

                    args.append((kb, ka) if ka >= kb else (kb, ka))
            else:
                for ka, kb, dlt in zip(key_a, key_b, delta):
                    if ka == kb:
                        raise ValueError("Identical Keys.")

                    args.append((kb, ka, dlt) if ka >= kb else (kb, ka, dlt))

            self.debug_execute_many(op, args)
        else:
            raise TypeError("key_a and key_b must be either both list or both int.")

    def _migrate_parent_duplicate(self, child_key: int, parent_key: int, known: bool):
        """
        Update the duplicates tables. All tuples with child_key, some_key are replaced by tuples of parent_key, some_key

        :param child_key: Key to replace
        :param parent_key: Key to use for replacement
        :param known: True -> update known_duplicates table else duplicates
        """
        tbl = "known_duplicates" if known else "duplicates"

        # Check Entries in duplicates table
        self.debug_execute(f"SELECT key_a, key_b, delta FROM `{tbl}` WHERE key_a = ? OR key_b = ?",
                           (child_key, child_key))

        results = self.sq_cur.fetchall()

        if len(results) > 0:
            self.main_logger.debug(f"Changing {len(results)} `{tbl}` entries to the new parent")

            args = []
            for result in results:
                if result[0] == child_key:
                    args.append({"key_a": parent_key, "key_b": result[1], "delta": result[2]})
                elif result[1] == child_key:
                    args.append({"key_a": result[0], "key_b": parent_key, "delta": result[2]})
                else:
                    raise ImplementationError("Couldn't find targeted key. Erroneous SQL Statement?")

            # Remove tuple of kind (parent_key, parent_key)
            filtered_args = list(filter(lambda a: a["key_a"] != a["key_b"], args))
            self._internal_modify_duplicates(key_a=[a["key_a"] for a in filtered_args],
                                             key_b=[a["key_b"] for a in filtered_args],
                                             known=known,
                                             add=True,
                                             delta=[a["delta"] for a in filtered_args])

            self._internal_modify_duplicates(key_a=[r["key_a"] for r in results],
                                             key_b=[r["key_b"] for r in results],
                                             known=known,
                                             add=False,
                                             delta=[a["delta"] for a in results])

    def remove_all_tuples_with_key(self, key: int, known: bool = False) -> int:
        """
        Removes all tuples either from the known_duplicates table or the duplicates table which contain the specified
        key.

        :param key: Key which needs to be contained for the tuple to be removed.
        :param known: If true, will remove the tuples from the known_duplicates table else duplicates table.

        :return: Number of removed tuples.
        """
        tbl = "known_duplicates" if known else "duplicates"

        self.debug_execute(f"SELECT COUNT(*) FROM `{tbl}` WHERE key_a = ? AND key_b = ?", (key, key))
        cnt = self.sq_cur.fetchone()[0]

        self.debug_execute(f"DELETE FROM `{tbl}` WHERE key_a = ? OR key_b = ?", (key, key))
        return cnt

    # ==================================================================================================================
    # UI
    # ==================================================================================================================

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
        _, dt, flags, db_local_dir, db_name, original_name = self._get_rename_data(key=key)

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change datetime from files in trash, not present and duplicates")

        new_dt = dt.replace(tzinfo=target_tz) if replace else dt.astimezone(tz=target_tz)

        # Early exit, if the new datetime is equivalent to the old one.
        if new_dt == dt:
            return

        if rename:
            new_name = self.db_name(original_filename=original_name, key=key, fdt=new_dt)

            self._internal_rename(key=key,
                                  flags=flags,
                                  dbn=db_name,
                                  new_name=new_name,
                                  dt=dt,
                                  db_local_dir=db_local_dir,
                                  ndt=new_dt)

            self.debug_execute("UPDATE main SET datetime = ?, timezone = ?, db_name = ? WHERE key = ?",
                               (new_dt.isoformat(), new_dt.tzname(), new_name, key))

        else:
            self._internal_move_file(ndt=new_dt, key=key, flags=flags, dt=dt, db_local_dir=db_local_dir, dbn=db_name)

            self.debug_execute("UPDATE main SET datetime = ?, timezone = ? WHERE key = ?",
                               (new_dt.isoformat(), new_dt.tzname(), key))

        if add_exif_tag or (add_exif_tag is None and self.config.add_safety_exif_tags):
            if dt != new_dt:
                self._add_update_exif_tag(key=key, target_datetime=new_dt, file_path=self.resolve_key_to_path(key))

        # Evicting lookup of old name to key
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        self.clear_presence_table()
        self.clear_hash_update_table()
        self.clear_filename_update_table()

        self.commit()

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

        _, dt, flags, db_local_dir, db_name, original_name = self._get_rename_data(key=key)
        new_name = self.db_name(original_filename=original_name, key=key, fdt=new_dt)
        timezone = new_dt.tzname()
        assert timezone is not None, "Unexpected timezone of None"

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change datetime from files in trash, not present and duplicates")

        # INFO: no exit with dt == new_dt because we could be switching keys.
        # Rename the file
        if rename:
            self._internal_rename(key=key,
                                  flags=flags,
                                  dbn=db_name,
                                  new_name=new_name,
                                  dt=dt,
                                  db_local_dir=db_local_dir,
                                  ndt=new_dt)

        else:
            # Only move the file.
            self._internal_move_file(ndt=new_dt, key=key, flags=flags, dt=dt, db_local_dir=db_local_dir, dbn=db_name)

        self.debug_execute("UPDATE main SET datetime = ?, db_name = ?, timezone = ?WHERE key = ?",
                           (new_dt.isoformat(), new_name, timezone, key))
        self.debug_execute("UPDATE metadata SET naming_tag = ?, datetime_source = ? WHERE main_key = ?",
                           (NewMetadataAggregator.serialize_key(tag), dts.value, key))

        if add_exif_tag or (add_exif_tag is None and self.config.add_safety_exif_tags):
            if dt != new_dt:
                self._add_update_exif_tag(key=key, target_datetime=new_dt, file_path=self.resolve_key_to_path(key))

        # Evicting lookup of old name to key
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        # TODO reset flags of hash, presence and filename tables
        self.clear_presence_table()

        self.commit()

    def change_filename(self, key: int, new_filename: str):
        """
        INFO: Function keeps the file in the same directory of the database.

        The function exists for the purpose of allowing the user to change file names however it is not recommended.

        Change the filename. Set a custom filename. The filename must be unique within the database.
        Also, the file must still be present.

        :param key: Key in main database to update with the new filename
        :param new_filename: The new file name to use. Sets the db_name column.
        """
        self.debug_execute("SELECT key FROM main WHERE db_name = ?", (new_filename,))
        if self.sq_cur.fetchone() is not None:
            raise ValueError("Filename already exists in main table.")

        # PRECONDITION: Filename not present
        _, dt, flags, db_local_dir, db_name, _ = self._get_rename_data(key=key)

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change name from files in trash, not present and duplicates")

        self._internal_rename(key=key,
                              flags=flags,
                              dbn=db_name,
                              new_name=new_filename,
                              dt=dt,
                              db_local_dir=db_local_dir)

        # Update the database after renaming
        self.debug_execute("UPDATE main SET db_name = ? WHERE key = ?",
                           (new_filename, key))
        self.debug_execute("UPDATE metadata SET naming_tag = ? WHERE main_key = ?",
                           ("CUSTOM", key))

        # Update cache
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        # TODO reset flags of hash, presence and filename tables
        self.clear_presence_table()

        self.commit()

    def move_file(self, key: int, new_dir: str):
        """
        Move a file within the database. Option to set the db_dir later on
        """
        ...

        # TODO reset flags of hash, presence and filename tables

    def _internal_rename(self, key: int, flags: MainFlags, dbn: str, new_name: str, dt: datetime.datetime,
                         ndt: datetime.datetime = None,
                         db_local_dir: str = None):
        """
        Shared part of the function that all functions that rename a file use.

        Info: Sets the prune_fs_dir flag.

        :param key: key of image to rename
        :param dbn: current name of image to rename
        :param new_name: new name of image to rename
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
            new_path = os.path.join(self.get_trash_dir(), new_name)
        elif db_local_dir is not None:
            current_path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), dbn)
            new_path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), new_name)
        elif ndt is not None:
            current_path = os.path.join(self.root_path, self.dt_to_dir(dt), dbn)
            new_path = os.path.join(self.root_path, self.dt_to_dir(ndt), new_name)
        else:
            assert db_local_dir is None and ndt is None, \
                f"Unexpected argument combination. db_local_dir {db_local_dir}, ndt: {ndt}"
            current_path = os.path.join(self.root_path, self.dt_to_dir(dt), dbn)
            new_path = os.path.join(self.root_path, self.dt_to_dir(dt), new_name)

        self.check_flags(key=key, flags=flags, org_path=current_path)

        if new_path == current_path:
            return

        # Check the file extensions.
        if os.path.splitext(new_name)[1] != os.path.splitext(dbn)[1]:
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

    def build_import_table_lookup(self, target_table: str):
        """
        Build the row lookup table for an import table
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

    def change_parent(self, key: int, new_parent: int):
        """
        Option to change a parent of a duplicate file, needed to undo an erroneous selection of the parent
        """
        self.debug_execute("UPDATE main SET parent = ? WHERE key = ?", (new_parent, key))

    def list_children(self, key: int) -> List[int]:
        """
        List all files which have the given key as parent.
        """
        self.debug_execute("SELECT key FROM main WHERE parent = ?", (key,))
        return [res[0] for res in self.sq_cur.fetchall()]

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


    def check_flags(self, key: int,
                    flags: MainFlags,
                    miniature: bool = False,
                    thumbnail: bool = False,
                    org_path: str = None):
        """
        Check the flags, of a given image. Report issues to integrity_logger.

        INFO:
        - Doesn't update the DB and doesn't update the flags object
        - Only is executed when self.opt_integrity_check si True.

        """
        if not self.opt_integrity_check:
            return

        # Check the miniatures.
        if miniature:
            if os.path.exists(self.full_miniature_path(key)) and not flags.has_miniature:
                self.integrity_logger.warning(f"Miniature present, flags record not present.")
            elif not os.path.exists(self.full_miniature_path(key)) and flags.has_miniature:
                self.integrity_logger.warning(f"Miniature not present, flags record present.")

        if thumbnail:
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

    def _db_resolve_key_to_abs_path(self, key: int) -> str | None:
        """
        Resolves a given key to an absolute filepath. The file doesn't have to exist.

        :param key: The key to resolve.
        """
        # TODO test.
        self.debug_execute("SELECT m.key, m.db_name, d.db_local_dir, m.datetime, m.flags "
                           "FROM main AS m "
                           "JOIN metadata AS md ON m.key = md.main_key "
                           "LEFT OUTER JOIN db_dir AS d ON md.db_dir = d.key "
                           "WHERE m.key = ? ", (key,))
        res = self.sq_cur.fetchall()
        if len(res) == 0:
            return None

        # Result is not None
        if len(res) > 1:
            raise CorruptDatabase(f"Key duplicated.")

        # PRECONDITION, len(res) == 1
        _, db_name, db_local_dir, _dt, _flags = res[0]
        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        # Parse the paths.
        if flags.trashed or flags.duplicate:
            path = os.path.join(self.get_trash_dir(), db_name)
        elif db_local_dir is not None:
            path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), db_name)
        else:
            assert db_local_dir is None and dt is not None, \
                f"Unexpected argument combination. db_local_dir {db_local_dir}, ndt: {dt}"
            path = os.path.join(self.root_path, self.dt_to_dir(dt), db_name)

        self.check_flags(flags=flags, key=key, miniature=False, thumbnail=False, org_path=path)
        return path

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

    def _db_resolve_filename_to_key(self, file_name: str) -> int | None:
        """
        Query the Database and get the key given a file name.
        """
        self.debug_execute("SELECT key FROM main WHERE db_name = ? ", (file_name,))
        res = self.sq_cur.fetchall()
        if len(res) == 0:
            return None

        if len(res) > 1:
            raise CorruptDatabase(f"file_name {file_name} appears in main and replaced table.")

        # PRECONDITION: number of results = 1
        return res[0][0]

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
        return f"thumb_{key:04}.jpeg"

    @staticmethod
    def miniature_name(key: int) -> str:
        """
        Given a key, get the miniature name
        """
        return f"miniature_{key:04}.jpeg"

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
        base_name = fdt.strftime(format="%Y-%m-%dT%H-%M-%S") + f"_{key:04}"
        ob, ext = os.path.splitext(original_filename)

        if self.config.org_filename_append:
            def_new_name = base_name + "_" + ob
            trunc_new_name = def_new_name[:120] + ext
        else:
            # Should technically not be possible, but we truncate just to be sure.
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

    @staticmethod
    def exif_tag_creator(dt: datetime.datetime) -> dict[str, str]:
        """
        Create a dict of
        """
        assert dt.tzinfo is not None, "Need a timezone aware object inside database"
        return {"EXIF:ModifyDate": dt.strftime("%Y:%m:%d %H:%M:%S"),
                "EXIF:OffsetTime": dt.strftime("%z")}

    @staticmethod
    def sanitize_json(obj: Any):
        """
        Util function to reduce code length.
        """
        return json.dumps(obj).replace("'", "''")

    def get_db_file_path(self, config: Config = None):
        """
        Resolve the db_file to an absolute path
        """
        config = self.config if config is None else config
        if os.path.isabs(config.db_file):
            return config.db_file
        else:
            return os.path.abspath(os.path.join(self.root_path, config.db_file))


class RemedyPhotoDB(PhotoDB):
    """
    A specific instance I need to migrate some remaining images, which are only available in older databases into this
    one.
    """

    def import_other_db(self):
        """
        Functionality needed because some images are only on older dbs including their metadata.
        """
        ...
