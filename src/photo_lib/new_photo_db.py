import datetime
import json
import logging
import os.path
import shutil
import sys
from typing import Set, Dict, List, Union, Tuple, Iterator
from zoneinfo import ZoneInfo

import photo_lib.defaults as defaults
from photo_lib.config import Config
from photo_lib.custom_enum import GroupingCriterion, SelectionType, MediaType, Allowed, ImportStatus, NameUpdateStatus, \
    NewMatchTypes
from photo_lib.data_objects import Selection, NewImportTableEntry, MetadataRow, MainRow, MediaPaths
from photo_lib.db_definitions import current_version, history, StaticDeclaration, GenericDeclaration
from photo_lib.errors_and_warnings import ImplementationError, CorruptDatabase
from photo_lib.flag_dataclasses import MainFlags, GenericTableFlags
from photo_lib.metadata_aggregator import MetadataParsingResult
from photo_lib.metadata_aggregator.config import DoubleKey
from photo_lib.metadata_aggregator.enums import DateTimeSource
from photo_lib.metadata_aggregator.new_metadata_aggregator import NewMetadataAggregator
from photo_lib.sqlite_wrapper import BaseSQliteDB


# https://docs.darktable.org/usermanual/development/en/overview/sidecar-files/sidecar-import/
# https://en.wikipedia.org/wiki/Join_(SQL)
class PhotoDB(BaseSQliteDB):
    __verified: bool = False

    static_decls: Dict[str, StaticDeclaration]
    generic_decls: Dict[str, GenericDeclaration]
    config: Config
    root_path: str

    __reserved_names: List[str] = ["<temp>"]

    # Redefining logger as mandatory
    db_logger_name: str = "PhotoDB.SQLiteDB"
    integrity_logger_name: str = "PhotoDB.SQLiteDB.Integrity"
    rare_occurrence_logger_name: str = "PhotoDB.SQLiteDB.RareOccurrence"

    rare_occurrence_logger: logging.Logger
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
                       root_path=inst.root_path,
                       config=inst.config,
                       init=False,
                       init_loggers=False,
                       verify=False,
                       opt_integrity_check=False),

        new_inst.__verified = inst.verified
        return new_inst

    def debug_execute(self, stmt: str, args: Union[tuple, dict, None] = None, cur: str = None):
        """
        Wrapper that blocks if the database isn't verified.

        :raises ImplementationError: If the database isn't verified.

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

        :raises ImplementationError: If the database isn't verified.

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
                 root_path: str,
                 config: Config,
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
        :param root_path: Root path of the database
        :param config: Config Object needed for path resolution. Config isn't verified or checked in any way.
        :param init: If true, initialize the database.
        :param init_loggers: If true, initialize the loggers. Otherwise, Loggers must be defined externally.
        :param opt_integrity_check: Every time full file paths are computed and flags are present. Flags consistency
            with file system are checked.
        """
        self.logger = logging.getLogger(PhotoDB.db_logger_name)
        self.integrity_logger = logging.getLogger(PhotoDB.integrity_logger_name)
        self.rare_occurrence_logger = logging.getLogger(PhotoDB.rare_occurrence_logger_name)

        # Needed for path generation.
        self.config = config
        self.root_path = root_path

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
        self.rare_occurrence_logger = logging.getLogger(self.rare_occurrence_logger_name)

    def set_logging_defaults(self):
        """
        Set Defaults of loggers.
        """
        # Level
        self.logger.setLevel(logging.DEBUG)
        self.integrity_logger.setLevel(logging.DEBUG)
        self.rare_occurrence_logger.setLevel(logging.DEBUG)

        # Propagate
        self.integrity_logger.propagate = True
        self.rare_occurrence_logger.propagate = True
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
        # TODO Implement
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

    def set_selection_from_import_table(self, sel_a: bool, tbl_name: str) -> int:
        """
        Set the selection flag in the main table of all keys which were imported from this table. Only updates based on
        import, no setting selection based on best_match

        :param sel_a: Whether to set the selection_a flag or the selection_b flag
        :param tbl_name: Name of Import Table from which to generate a selection.

        :raises sqlite3.OperationalError: If the Import Table doesn't exist

        :returns: number of rows affected in main table
        """
        if sel_a:
            self.debug_execute(f"UPDATE main SET flags = flags + 16 WHERE mod(flags >> 4) = 0 "
                               f"AND key IN (SELECT import_key FROM `{tbl_name}` WHERE import_key IS NOT NULL) ")
            rc = self.sq_cur.rowcount
        else:
            self.debug_execute(f"UPDATE main SET flags = flags + 32 WHERE mod(flags >> 5) = 0 "
                               f"AND key IN (SELECT import_key FROM `{tbl_name}` WHERE import_key IS NOT NULL) ")
            rc = self.sq_cur.rowcount
        return rc

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

    def set_match_type_import_table(self, tbl_name: str, key: int, matches: Dict[int, NewMatchTypes],
                                    best_match: int | None, best_match_type: NewMatchTypes):
        """
        Set the match data for a given row in the import table.

        PRECONDITION: Key exists in import table

        :param tbl_name: Name of table in which to update the file
        :param key: key in import table to update
        :param matches: Dict of files matched against the one given with their respective NewMatchType$
        :param best_match: Key of best match in main table
        :param best_match_type: Type of best match.

        :raises sqlite3.OperationalError: If the Import Table doesn't exist
        """
        serializable_matches = {k: v.value for k, v in matches.items()}
        self.debug_execute(stmt=f"UPDATE `{tbl_name}` SET match_type = ?, highest_match = ?, matches = ? "
                                f"WHERE key = {key}",
                           args=(best_match_type.value, best_match, json.dumps(serializable_matches), key))

        assert self.sq_cur.rowcount == 1, f"SQL Error, key not found in table {tbl_name}"

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

    def update_allowed_iterator(self, tbl_name: str) -> Iterator[Tuple[int, Allowed, str]]:
        """
        Creates an iterator to update the allowed state of the files in the import table.
        """
        self.add_extra_cursor("update_allowed")
        self.debug_execute(stmt=f"SELECT key, allowed, original_filename FROM `{tbl_name}` WHERE imported IN (0, 1)")
        for key, _allowed, org_fname in self.get_cursor("update_allowed"):
            yield key, Allowed(_allowed), org_fname

        self.remove_extra_cursor("update_allowed")

    def perform_import_iterator(self, tbl_name: str) -> Iterator[
        Tuple[int, str, str, str | None, str | None, str, int, datetime.datetime,
              str, str, float | None, float | None, DateTimeSource, Allowed, int | None]]:
        """
        Iterator to get all rows which can be imported from the import table.

        # INFO: Metadata isn't parsed to from json, becasue we do not need to interact with it.

        Tuple elements are in this sequence:

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

            assert dt.tzinfo is not None, "Timezone needed for import"

            yield k, ofn, ofd, md, gfmd, fh, fsb, dt, tz, nt, gps_lat, gps_long, dts, allowed, imp_key

        self.remove_extra_cursor("import_cursor")

    def find_import_match_iterator(self, tbl_name: str, recompute: bool = False) \
            -> Iterator[Tuple[int, str, str, int, str]]:
        """
        Get an iterator with the necessary information to check for matches in the main table.

        Tuple elements are in this sequence:

        - import table key
        - original file name
        - original directory name
        - file size bytes
        - file hash

        :param tbl_name: Import table to iterate over
        :param recompute: Recompute the matches, otherwise

        :raises sqlite3.OperationalError: If the Import Table doesn't exist'
        """
        self.add_extra_cursor("match_cursor")
        if recompute:
            # Reset the match columns before recomputing.
            self.debug_execute(f"UPDATE `{tbl_name}` SET highest_match= NULL, matches = NULL, match_type = 0 "
                               f"WHERE allowed = 1, AND imported IN (0, 1)")

            self.debug_execute(f"SELECT key, original_filename, original_dirname, file_size_bytes, file_hash "
                               f"FROM `{tbl_name}` WHERE imported IN (0, 1) AND allowed = 1",
                               cur="match_cursor")
        else:
            self.debug_execute(f"SELECT key, original_filename, original_dirname, file_size_bytes, file_hash "
                               f"FROM `{tbl_name}` WHERE imported IN (0, 1) AND allowed = 1 AND matches IS NULL",
                               cur="match_cursor")

        for key, ofn, ofd, fsb, fh in self.get_cursor("match_cursor"):
            yield key, ofn, ofd, fsb, fh

        self.remove_extra_cursor("match_cursor")

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
            self.debug_execute(f"UPDATE main SET flags = flags - 1 "
                               # Check key is in the table                            
                               f"WHERE key IN (SELECT main_key FROM presence_table) "
                               #     Check present,         check not duplicate        check not trash
                               f"AND mod(flags, 2) = 1 AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)))

            count = self.sq_cur.rowcount
        else:
            self.debug_execute(f"UPDATE main SET flags = flags + 1 "
                               # Check key is in the table
                               f"WHERE key IN (SELECT main_key FROM presence_table) "
                               #     Check present,         check not duplicate        check not trash
                               f"AND mod(flags, 2) = 0 AND mod(flags >> 8, 2) = ? AND mod(flags >> 2, 2) = ?",
                               args=(int(dup_flag), int(trash_flag)))

            count = self.sq_cur.rowcount
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

    def insert_row_presence_table(self, key: int):
        """
        Insert a key into the presence_table to indicate a mismatch between the presence flag and the file system.

        :param key: key to add into the presence_table

        :raises sqlite3.IntegrityError: If the file path already exists
        """
        self.debug_execute(f"INSERT INTO presence_table (main_key) VALUES (?)", (key,))

        assert self.sq_cur.rowcount == 1, "SQL ERROR, Failed to Insert Row"

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
        Get the number of rows of the hash_update_table
        """
        self.debug_execute("SELECT COUNT(main_key) FROM hash_update_table")
        return self.sq_cur.fetchone()[0]

    def insert_row_hash_update_table(self, key: int, new_hash: str, file_size: int):
        """
        Insert a new row into the hash_update_table.

        :param key: Key of the file in the main table
        :param new_hash: New hash of the file
        :param file_size: New file size of the file
        """
        self.debug_execute(stmt="INSERT INTO hash_update_table (main_key, new_hash, file_size_bytes) VALUES (?, ?, ?)",
                           args=(key, new_hash, file_size))

        assert self.sq_cur.rowcount == 1, "SQL ERROR, Failed to Insert Row"

    def hash_update_iterator(self) -> Iterator[Tuple[int, str, int]]:
        """
        Returns an iterator to the table containing the information to update the file hashes.

        Tuple elements are in this sequence:

        - main_key (key in the main table)
        - new_hash newly computed file hash of that file
        - file_size_bytes (new) file size of the given file.
        """
        self.add_extra_cursor("hash_update")
        self.debug_execute("SELECT main_key, new_hash, file_size_bytes FROM hash_update_table")

        for main_key, hash_str, file_size in self.get_cursor("hash_update"):
            yield main_key, hash_str, file_size

        self.remove_extra_cursor("hash_update")

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

    def insert_row_name_update_table(self, filename: str, dirname: str, file_size: int, file_hash: str):
        """
        Insert a new row into the name_update_table.

        :param filename: Filename of the file
        :param dirname: Directory where file is
        :param file_size: File size of the file
        :param file_hash: Hash of the file

        :raises sqlite3.IntegrityError: If the path alread exists.
        """
        self.debug_execute(stmt="INSERT INTO name_update_table (name, dir_name, file_size_bytes, hash) "
                                "VALUES (?, ?, ?, ?)",
                           args=(filename, dirname, file_size, file_hash))

        assert self.sq_cur.rowcount == 1, "SQL ERROR, Failed to insert row into name_update_table"

    def set_updated_status_name_update_table(self, key: int, status: NameUpdateStatus, message: str = None):
        """
        Set the update state of a row in the name_update_table. Can also add a message, if one is provided.

        PRECONDITION: Key exists in name_update_table

        :param key: Key of the file in the name_update_table
        :param status: New status of the file
        :param message: New message of the file
        """

        if status == NameUpdateStatus.READY_TO_UPDATE or status == NameUpdateStatus.UPDATED:
            if message is not None:
                raise ValueError("Message only intended to inform about failure")

        self.debug_execute("UPDATE name_update_table SET updated = ?, message = ? WHERE key = ?",
                           (status.value, message, key))

        assert self.sq_cur.rowcount == 1, "SQL ERROR, Failed to update row in name_update_table"

    def selection_from_name_update_table(self, sel_a: bool) -> int:
        """
        Given the name_update_table, set either the sel_a or sel_b flag for all rows which successfully update a row in
        the main table.

        :param sel_a: Whether to set the sel_a or sel_b flag

        :return: Number of rows affected in main table.
        """
        if sel_a:
            self.debug_execute(f"UPDATE main SET flags = flags + 16 WHERE mod(flags >> 4) = 0 "
                               f"AND key IN (SELECT best_match FROM name_update_table "
                               f"WHERE best_match IS NOT NULL AND updated = 1) ")
            rc = self.sq_cur.rowcount
        else:
            self.debug_execute(f"UPDATE main SET flags = flags + 32 WHERE mod(flags >> 5) = 0 "
                               f"AND key IN (SELECT best_match FROM name_update_table "
                               f"WHERE best_match IS NOT NULL AND updated = 1) ")
            rc = self.sq_cur.rowcount
        return rc

    def set_match_data_name_update_table(self, key: int, matches: Dict[int, NewMatchTypes], best_match: int | None,
                                         match_type: NewMatchTypes):
        """
        Set the match data for a given key in the name_update_table.

        PRECONDITION: Key exists in name_update_table

        :param key: Key of the file in the name_update_table
        :param matches: Dictionary of matched keys and their respective NewMatchType
        :param best_match: Best match of the key
        :param match_type: Match type of best match
        """
        serializable_matches = {k: v.value for k, v in matches.items()}

        self.debug_execute(stmt="UPDATE name_update_table SET matches = ?, best_match = ?, best_match_type = ? "
                                "WHERE key = ?",
                           args=(json.dumps(serializable_matches), best_match, match_type.value, key))

        assert self.sq_cur.rowcount == 1, "SQL ERROR, Failed to update row in name_update_table"

    def update_filename_from_hash_iterator(self) -> Iterator[Tuple[int, str, str, int]]:
        """
        Get an iterator to all rows of the name_update_table which can be used to update the file name of a file matched
        by file hash.

        The criteria are:

        - best_match must contain an integer (pointing to teh file in the main table that is the candidate to update)
        - update = 0 (meaning, can be updated)
        - match_type = 2, we only update file who's aren't trash or duplicates (no 3-6). A match type of 1 would
        indicate that the original file is present (so it doesn't make sense to move the newly detected file) Match
        type 0 means, no candidate to update found. So only 2 remains as an option.

        Tuple elements are in this sequence:

        - key (in name_update_table)
        - name (in name_update_table)
        - dir_name (in name_update_table (so dir_name + name is the path to the detected file))
        - best_match (key to entry in main table which was deemed the best match for this file)

        """
        self.add_extra_cursor("name_update")
        self.debug_execute("SELECT key, name, dir_name, best_match FROM name_update_table "
                           # Ensure match is HASH_MATCH_MAIN
                           "WHERE best_match IS NOT NULL AND updated = 0 AND match_type = 2")

        for key, name, dir_name, best_match in self.get_cursor("name_update"):
            yield key, name, dir_name, best_match

        self.remove_extra_cursor("name_update")

    def find_hash_match_iterator(self) -> Iterator[Tuple[int, str, str, int, str]]:
        """
        Get an iterator for all rows in the name_update_table to find matches based on the file hash and file size.

        Tuple elements are in this sequence:

        - key (in name_update_table)
        - name (in name_update_table)
        - dir_name (in name_update_table (so dir_name + name is the path to the detected file))
        - file_size_bytes (size of the file indicated by name and dir_name)
        - hash (of file indicated by name and dir_name)
        """
        self.add_extra_cursor("name_update_hash_match")
        self.debug_execute(stmt="SELECT key, name, dir_name, file_size_bytes, hash FROM name_update_table",
                           cur="name_update_hash_match")

        for key, name, dir_name, file_size_bytes, hash in self.get_cursor("name_update_hash_match"):
            yield key, name, dir_name, file_size_bytes, hash

        self.remove_extra_cursor("name_update_hash_match")

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

    def delete_dir(self, key: int | List[int]):
        """
        Delete row(s) of the directory table, given a key. PRECONDITION
        """
        if isinstance(key, int):
            raw_key = [key]
        else:
            assert isinstance(key, list), f"Unexpected Type: {type(key).__name__}"
            raw_key = key

        pruned_keys = list(set(raw_key))
        self.debug_execute_many("DELETE FROM db_dir WHERE key = ?", args=[(k,) for k in pruned_keys])

        assert len(pruned_keys) == self.sq_cur.rowcount, (f"Unexpected number of updated rows {self.sq_cur.rowcount}, "
                                                          f"given keys: {pruned_keys}")

    # ==================================================================================================================
    # Hash Assoz Table
    # ==================================================================================================================

    def get_size_of_hash_assoz_table(self) -> int:
        """
        Get the size of the hash_assoz table
        """
        self.debug_execute("SELECT COUNT(*) FROM hash_assoz")
        return self.sq_cur.fetchone()[0]

    def find_hash_match_keys(self, target_hash: str, file_size: int, mode: str) -> List[int]:
        """
        Given a hash and file size, finds all file_keys which share this hash.

        mode (case-insensitive):

        - EARLIEST, given a file_key, only take into account the earliest hash of that file (not initial)
        - LATEST, given a file_key, only take into account the latest hash of that file (including initial)
        - ANY, given a file_key, take into account all hashes the file has had (including initial)
        - INITIAL, given a file_key, only look at initial hashes (only initial)

        :param target_hash: Target hash to search for
        :param file_size: File size to search for
        :param mode: Mode to search for, can be EARLIEST, LATEST, ANY

        :returns: List[int] - list of matching file_keys
        """
        if mode.lower() not in ("earliest", "latest", "any", "initial"):
            raise ValueError(f"Unsupported mode: {mode.lower()}, allowed: [earliest, latest, any, initial]")

        if mode.lower() == "earliest":
            self.debug_execute("SELECT ha.file_key "
                               "FROM hashes AS h JOIN hash_assoz AS ha "
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.hash_date IN "
                               "(SELECT MIN(datetime(ha.hash_date)) "
                               "FROM hash_assoz AS ha JOIN hash ON hash.key = ha.hash_key "
                               "WHERE hash.hash = ? AND ha.file_size_bytes = ? AND ha.initial = 0 "
                               "GROUP BY hash_key, file_key)",
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

    def get_newest_hash(self, key: int) -> Tuple[str, int, datetime.datetime] | Tuple[None, None, None]:
        """
        Get the newest hash of a given file. If the newest hash doesn't match, we don't perform binary comparison.

        :param key: File key to search for
        :returns: Tuple[None, None, None] -> key not found, Tuple[str, int, datetime] -> newest hash and
            file_size_bytes of that hash, datetime when hash was computed.
        """
        self.debug_execute("SELECT h.hash, ha.file_size_bytes, ha.hash_date "
                           "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE ha.file_key = ? AND ha.hash_date IN "
                           "(SELECT MAX(hash_date) FROM hash_assoz WHERE file_key = ?)",
                           (key, key))
        res = self.sq_cur.fetchone()
        if res is None:
            return None, None, None

        return res[0], res[1], res[2]

    def get_initial_hash(self, key: int) -> Tuple[str, int, datetime.datetime] | Tuple[None, None, None]:
        """
        Get the initial hash of a given file in the hash assoz table.

        :param key: key in main table.
        """
        self.debug_execute("SELECT h.hash, ha.file_size_bytes, ha.hash_date "
                           "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE ha.file_key = ? AND ha.initial = 1",
                           (key,))
        res = self.sq_cur.fetchone()
        if res is None:
            return None, None, None

        return res[0], res[1], res[2]

    def get_all_hashes_of_file(self, key: int) -> Iterator[Tuple[str, int, datetime.datetime, bool]]:
        """
        Get all file hashes of a given file.

        :param key: keys in main table to get the hashes for

        :returns Iterator to all files hashes given a file key.
        """
        self.add_extra_cursor("get_file_hash")
        self.debug_execute("SELECT h.hash, ha.file_size_bytes, ha.hash_date, ha.initial "
                           "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                           "WHERE ha.file_key = ?",
                           (key,), "get_file_hash")

        # Process the rows
        for h, fsb, _hd, ini in self.get_cursor("get_file_hash"):
            dt = datetime.datetime.fromisoformat(_hd)
            yield h, fsb, dt, bool(ini)

        self.remove_extra_cursor("get_file_hash")

    def check_add_file_hash(self, file_key: int,
                            file_size: int,
                            file_hash: str,
                            initial: bool = False) -> bool:
        """
        Checks if a given row in the hash_assoz table exists provided a file_hash, a file_size and file_key.

        If the row is found, but it's not the newest row, update the hash.

        Adds the row if it doesn't exist.

        :param file_hash: The hash of the file to check.
        :param file_size: The size of the file to check.
        :param file_key: The key of the file to check.
        :param initial: If this the hash gotten when hashing in the source directory of the import.

        :return: True if the row exists, False if the row were added.
        """
        # TODO rethink operation with initial and not initial. Maybe less optimized code but better readability

        # Consider the hashes a set of all hashes the file had at a given point. The hash to check during import is
        # the one marked with initial
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
        newest_hash, newest_size, fdht = self.get_newest_hash(res[1])

        if (newest_hash, newest_size, fdht) == (None, None, None):
            raise CorruptDatabase("File without File hash found")

        # Check the given hash is the newest hash of the file.
        if newest_hash != file_hash:
            ndt = datetime.datetime.now(datetime.timezone.utc)
            # Update the row to be the newest one.
            self.debug_execute(stmt="UPDATE hash_assoz "
                                    "SET hash_date = ? "
                                    "WHERE hash_key = ? AND file_key = ? AND file_size_bytes = ? AND initial = 0",
                               args=(ndt.isoformat(), hash_key, file_key, file_size))

        if newest_hash == file_hash and newest_size != file_size:
            self.rare_occurrence_logger.info(f"Found matching hashes with different file sizes: "
                                             f"{newest_hash}, {newest_size}")

        return True

    def delete_file_association(self, file_key: int) -> int:
        """
        Delete all associations between a file and its hashes over its life time.

        :parma file_key: The key of the file to delete.

        :returns: Number of Rows deleted
        """
        self.debug_execute("DELETE FROM hash_assoz WHERE file_key = ?", (file_key,))

        return self.sq_cur.rowcount

    # ==================================================================================================================
    # Duplicates and Known Duplicates Table
    # ==================================================================================================================

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

        :raises TypeError: If not key_a, key_b, delta aren't all either numbers or lists
        :raises ValueError: If a tuple of (key_x, key_x) is found
        :raises IndexError: If the lists don't have the same length.
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
                raise IndexError("key_a and key_b must have same length")

            if delta is not None:
                if not isinstance(delta, list):
                    raise TypeError("List[float] required if key_a and key_b are List[int]")

                if not len(key_a) == len(delta):
                    raise IndexError("delta and key_x must have the same length")

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

    def migrate_parent_duplicate(self, child_key: int, parent_key: int, known: bool):
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
            self.logger.debug(f"Changing {len(results)} `{tbl}` entries to the new parent")

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
    # Metadata Table
    # ==================================================================================================================

    def insert_row_metadata_table(self,
                                  key: int,
                                  original_dirname: str,
                                  naming_tag: str,
                                  datetime_source: DateTimeSource):
        """
        Insert a new row into the metadata table.

        :param key: Main Key of Row to Insert.
        :param original_dirname: Original Directory from which the file was imported.
        :param naming_tag: Tag who's the source of teh datetime of the image
        :param datetime_source: Class of Datetime Objects which produced the datetime object.

        :raises sqlite3.IntegrityError: If the db_name already exists.
        """
        self.debug_execute("INSERT INTO metadata (main_key, original_dirname, naming_tag, datetime_source) "
                               "VALUES (?, ?, ?, ?)", args=(key, original_dirname, naming_tag, datetime_source.value))

        assert self.sq_cur.rowcount == 1, "Failed to Insert Row into Metadata Table"

    def delete_row_metadata_table(self, key: int, assert_exists: bool = True) -> bool:
        """
        Delete a given row from the metadata table.


        :param key: Main Key of Row to Delete.
        :param assert_exists: Check Precondition that the row existed.

        :returns: True -> Row was Deleted. False otherwise.
        """
        self.debug_execute("DELETE FROM metadata WHERE main_key = ?", (key,))

        rc = self.sq_cur.rowcount
        if assert_exists:
            assert rc == 1, "PRECONDITION Failed: Row didn't exist in Metadata Table"

        return rc == 1

    # TODO better docs for kwargs
    def update_row_metadata_table(self, key: int, **kwargs):
        """
        Update the row indicated by the key in the metadata table.

        PRECONDITION: row with key exists.

        :param key: Main Key of Row to Update.

        kwargs are all column names of the metadata table. If a row is not supposed to be updated, do not add it to the
        kwargs. If a kwargs is None, the column of that row will be set to NULL!!!
        All possible kwargs are:

        original_dirname: str
        naming_tag: str
        datetime_source: DateTimeSource
        gps_location: int
        db_dir: int
        replaced: MediaType
        """
        given = set(kwargs.keys())
        all_cols = {"original_dirname", "naming_tag", "datetime_source", "gps_location", "db_dir", "replaced"}

        # Check the keysdatetime_source
        if not given.issubset(all_cols):
            rem = given - all_cols
            raise ValueError(f"Columns: {rem} not in metadata table")

        # Update kwarg types from Enums to ints
        if "replaced" in given:
            val = kwargs.get("replaced")

            if not isinstance(val, MediaType):
                raise TypeError(f"replaced column is not of type MediaType but {type(val).__name__}")

            # Update the replaced value
            kwargs["replaced"] = val.value

        if "datetime_source" in given:
            val = kwargs.get("datetime_source")

            if not isinstance(val, DateTimeSource):
                raise TypeError(f"datetime_source column is of type DateTimeSource")

            # Update kwargs
            kwargs["datetime_source"] = val.value

        keys = list(kwargs.keys())
        set_strs = [f"{k} = ?" for k in keys]
        full_set_str = ", ".join(set_strs)

        substitute = [kwargs.get(k) for k in keys]
        substitute += [key]

        self.debug_execute(f"UPDATE metadata SET {full_set_str} WHERE main_key = ?", args=tuple(substitute))

        assert self.sq_cur.rowcount == 1, "Failed to Update Row in Metadata Table"

    def get_metadata_row(self, key: int) -> MetadataRow | None:
        """
        Get a row of metadata table given a key.

        :param key: Main Key of Row to Get

        :returns: Metadata Row or None (if the row wasn't found)
        """
        self.debug_execute(
            "SELECT m.main_key, m.original_dirname, m.naming_tag, m.datetime_source, m.replaced, "
            "d.db_local_dir, g.gps_latitude, g.gps_longitude "
            "FROM metadata AS m "
            "LEFT OUTER JOIN db_dir AS d ON m.db_dir = d.key "
            "LEFT OUTER JOIN gps_location AS g ON g.key = m.gps_location "
            "WHERE m.main_key = ?", (key,))

        res = self.sq_cur.fetchone()
        if res is None:
            return None

        mk, ofd, nt, _dts, rep, db_ld, gps_lat, gps_long = res
        dts = DateTimeSource(_dts)
        return MetadataRow(main_key=mk, original_dirname=ofd, naming_tag=nt, datetime_source=dts,
                           replaced=rep, db_local_dir=db_ld, gps_lat=gps_lat, gps_long=gps_long)

    # ==================================================================================================================
    # Main Table
    # ==================================================================================================================

    def insert_row_main_table(self,
                              original_filename: str,
                              db_name: str,
                              dt: datetime.datetime,
                              timezone: str,
                              flags: MainFlags,
                              metadata: str | dict | list | None = None,
                              google_metadata: str | dict | list | None = None):
        """
        Add a new row into the main table.

        :param original_filename: Original filename in import source.
        :param db_name: Name of file in database.
        :param dt: datetime at which the media was recorded
        :param timezone: Timezone in which media was recorded
        :param flags: MainFlags of the media file
        :param metadata: Metadata Dict from ExifTool
        :param google_metadata: Metadata from Google Photos Export

        :raises sqlite3.IntegrityError: If the db_name already exists.
        """
        assert dt.tzinfo is not None, "Timezone always needed."

        if isinstance(metadata, str):
            san_md = metadata
        elif metadata is None:
            san_md = None
        elif isinstance(metadata, dict) or isinstance(metadata, list):
            san_md = json.dumps(metadata)
        else:
            raise TypeError("Metadata must be a string, dict, list or None")

        if isinstance(google_metadata, str):
            san_gfmd = google_metadata
        elif google_metadata is None:
            san_gfmd = None
        elif isinstance(google_metadata, dict) or isinstance(google_metadata, list):
            san_gfmd = json.dumps(google_metadata)
        else:
            raise TypeError("Metadata must be a string, dict, list or None")

        self.debug_execute(
            stmt=f"INSERT INTO main "
                 f"(original_filename, "
                 f"metadata, "
                 f"google_metadata, "
                 f"db_name, "
                 f"datetime, "
                 f"timezone, "
                 f"flags) VALUES (?, ?, ?, ?, ?, ?, ?)",
            args=(original_filename, san_md, san_gfmd, db_name, dt.isoformat(), timezone, flags.to_int()))

        assert self.sq_cur.rowcount == 1, "Failed to Insert Row into Main Table"

    def delete_row_main_table(self, key: int, assert_exists: bool = True) -> bool:
        """
        Delete a given row from the main table.

        :param key: Key of row to delete.
        :param assert_exists: Check Precondition that the row existed.

        :returns: True -> Row was Deleted. False otherwise.
        """
        self.debug_execute("DELETE FROM main WHERE key = ?", (key,))
        rc = self.sq_cur.rowcount

        if assert_exists:
            assert rc == 1, "PRECONDITION Failed, row didn't exist in main table."

        return rc == 1

    # TODO better docs for kwargs
    def update_row_main_table(self, key: int, **kwargs):
        """
        Update the row indicated by the key in the main table.

        PRECONDITION: row with key exists.

        :param key: Key of Row to Update.

        kwargs are all column names of the main table. If a row is not supposed to be updated, do not add it to the
        kwargs. If a kwargs is None, the column of that row will be set to NULL!!!
        All possible kwargs are:

        original_filename: str
        metadata: str | dict | list | None
        google_metadata: str | dict | list | None
        datetime: datetime.datetime (timezone aware object)
        db_name: str
        parent: int
        timezone: str
        flags: MainFlags
        """
        given = set(kwargs.keys())
        all_cols = {"original_filename",
                    "metadata",
                    "google_metadata",
                    "datetime",
                    "db_name",
                    "parent",
                    "timezone",
                    "flags"}

        # Check the keys
        if not given.issubset(all_cols):
            rem = given - all_cols
            raise ValueError(f"Columns: {rem} not in metadata table")

        # Convert metadata
        if "metadata" in given:
            md = kwargs["metadata"]

            if md is None or isinstance(md, str):
                san_md = md
            elif isinstance(md, list) or isinstance(md, dict):
                san_md = json.dumps(md)
            else:
                raise TypeError(f"Metadata must be a string, dict, list or None, got {type(md).__name__}")

            kwargs["metadata"] = san_md

        # Convert google metadata
        if "google_metadata" in given:
            gfmd = kwargs["google_metadata"]

            if gfmd is None or isinstance(gfmd, str):
                san_gfmd = gfmd
            elif isinstance(gfmd, list) or isinstance(gfmd, dict):
                san_gfmd = json.dumps(gfmd)
            else:
                raise TypeError(f"Metadata must be a string, dict, list or None, got {type(gfmd).__name__}")

            kwargs["google_metadata"] = san_gfmd

        # Convert datetime
        if "datetime" in given:
            dt: datetime.datetime = kwargs["datetime"]

            if dt.tzinfo is None:
                raise TypeError("Datetime Object needs to be Timezone Aware.")

            kwargs["datetime"] = dt.isoformat()

        if "flags" in given:
            flags = kwargs["flags"]

            if not isinstance(flags, MainFlags):
                raise TypeError(f"Flags must be a MainFlags, got {type(flags).__name__}")

            kwargs["flags"] = flags.to_int()

        keys = list(kwargs.keys())
        set_strs = [f"{k} = ?" for k in keys]
        full_set_str = ", ".join(set_strs)

        substitute = [kwargs.get(k) for k in keys]
        substitute += [key]

        self.debug_execute(f"UPDATE main SET {full_set_str} WHERE key = ?", args=tuple(substitute))

        assert self.sq_cur.rowcount == 1, "Failed to Update Row in Main Table"

    def update_trash_flag_from_selection(self, selection: Selection, target_value: bool):
        """
        Update the files which have aren't present to have been moved to the trash.

        :param selection: Selection of Files to update
        :param target_value: bool, whether to set the flag to True or False
        """
        args = tuple()
        if target_value and selection.selection_type == SelectionType.SELECTION_A:
            #                                              trash                       sel_a
            stmt = "UPDATE main SET flags = flags + 4 WHERE mod(flags >> 2, 2) = 0 AND mod(flags >> 4, 2) = 1"
        elif target_value and selection.selection_type == SelectionType.SELECTION_B:
            #                                              trash                       sel_b
            stmt = "UPDATE main SET flags = flags + 4 WHERE mod(flags >> 2, 2) = 0 AND mod(flags >> 5, 2) = 1"
        elif target_value and selection.selection_type == SelectionType.TIME_RANGE:
            #                                               trash
            stmt = ("UPDATE main SET flags = flags + 4 WHERE mod(flags >> 2, 2) = 0 "
                    #            time_range
                    "AND datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?)")
            args = (selection.start.isoformat(), selection.end.isoformat())
        elif not target_value and selection.selection_type == SelectionType.SELECTION_A:
            #                                              trash                       sel_a
            stmt = "UPDATE main SET flags = flags - 4 WHERE mod(flags >> 2, 2) = 1 AND mod(flags >> 4, 2) = 1"
        elif not target_value and selection.selection_type == SelectionType.SELECTION_B:
            #                                              trash                       sel_b
            stmt = "UPDATE main SET flags = flags - 4 WHERE mod(flags >> 2, 2) = 1 AND mod(flags >> 5, 2) = 1"
        elif not target_value and selection.selection_type == SelectionType.TIME_RANGE:
            #                                               trash
            stmt = ("UPDATE main SET flags = flags - 4 WHERE mod(flags >> 2, 2) = 1 "
                    #            time_range
                    "AND datetime(?) <= datetime(datetime) AND datetime(datetime) <= datetime(?)")
            args = (selection.start.isoformat(), selection.end.isoformat())
        else:
            raise ImplementationError("Tertiem Non Datur")

        assert stmt is not None, "Implementation issue, stmt shouldn't be None"
        self.debug_execute(stmt, args)

        count = self.sq_cur.rowcount

        self.commit()
        self.logger.debug(f"updated {count} entries in main table to have trash flag = {target_value} "
                          f"where selection type = {selection}")
        return count

    def change_parent(self, key: int, new_parent: int):
        """
        Option to change a parent of a duplicate file, needed to undo an erroneous selection of the parent
        """
        self.debug_execute("UPDATE main SET parent = ? WHERE key = ?", (new_parent, key))

    def reset_selection(self, sel_a: bool = True) -> int:
        """
        Reset all rows with a set sel_a flag if sel_a, else reset all rows with sel_b flag.

        :param sel_a: Bool whether to reset selection a or selection b
        """
        if sel_a:
            self.debug_execute("UPDATE main SET flags = flags - 16 WHERE (flags >> 4, 2) == 1")
            return self.sq_cur.rowcount

        else:
            self.debug_execute("UPDATE main SET flags = flags - 32 WHERE (flags >> 5, 2) == 1")
            return self.sq_cur.rowcount

    def list_children(self, key: int) -> List[int]:
        """
        List all files which have the given key as parent.
        """
        self.debug_execute("SELECT key FROM main WHERE parent = ?", (key,))
        return [res[0] for res in self.sq_cur.fetchall()]

    def get_number_of_children(self, key: int) -> int:
        """
        Get the number of children of a given key.

        INFO: Function does no checks, doesn't check whether the key is not a duplicate
        INFO: Function doesn't check whether the key exists in the main table
        """
        self.debug_execute("SELECT COUNT(key) FROM main WHERE parent = ?", (key,))
        return self.sq_cur.fetchone()[0]

    def get_parent(self, key: int) -> int | None:
        """
        Get the Parent of a given key.

        PRECONDITION: Key exists

        :param key: Key to get the parent for

        :returns: None, no parent, int, parent key

        :raises ValueError: If the key doesn't exist
        """
        self.debug_execute("SELECT parent FROM main WHERE key = ?", (key,))
        res = self.sq_cur.fetchone()
        if res is None:
            raise ValueError("Key doesn't exist")

        return res[0]

    def get_path_data(self, key: int) -> Tuple[datetime.datetime, MainFlags, str, str, str] | None:
        """
        Get the necessary data from the database to rename a file

        :param key: Key to query the db for

        :returns: Tuple(datetime, flags, db_local_dir, db_name, original_name)
        """
        # TODO test this function
        self.debug_execute(stmt="SELECT m.db_name, d.db_local_dir, m.datetime, m.flags, m.original_filename "
                                "FROM main AS m "
                                "LEFT OUTER JOIN metadata AS md ON m.key = md.main_key "
                                "LEFT OUTER JOIN db_dir AS d ON md.db_dir = d.key "
                                "WHERE m.key = ? ",
                           args=(key,))
        row = self.sq_cur.fetchone()
        if row is None:
            return None

        db_name, db_local_dir, _dt, _flags, original_filename = row

        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        return dt, flags, db_local_dir, db_name, original_filename

    def get_replace_data(self, key: int) -> Tuple[str, MainFlags, str] | None:
        """
        Get the necessary data from the main table to mark a file as a duplicate.

        :param key: key of file in main table

        :returns: google_metadata json string, MainFlags, db_name
        """
        self.debug_execute(stmt="SELECT m.google_metadata, m.flags, m.db_name FROM main AS m WHERE m.key = ?",
                           args=(key,))

        raw = self.sq_cur.fetchone()
        if raw is None:
            return None

        gfmd, _flags, db_name = raw
        flags = MainFlags.from_int(_flags)
        return gfmd, flags, db_name

    def get_main_flags(self, key: int) -> None | MainFlags:
        """
        Get the flags from any entry in the main table
        """
        self.debug_execute("SELECT flags FROM main WHERE key = ?", (key,))
        res = self.sq_cur.fetchone()
        if res is None:
            return None

        return MainFlags.from_int(res[0])

    def db_resolve_key_to_abs_path(self, key: int) -> str | None:
        """
        Resolves a given key to an absolute filepath. The file doesn't have to exist.

        :param key: The key to resolve.
        """
        pd = self.get_path_data(key)
        if pd is None:
            return None

        dt, flags, db_local_dir, db_name, _ = pd

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

    def db_resolve_filename_to_key(self, file_name: str) -> int | None:
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

    def get_main_row(self, key: int) -> MainRow | None:
        """
        Get a row of main table given a key.

        :param key: Main Key of Row to Get

        :returns: Metadata Row or None (if the row wasn't found)
        """
        self.debug_execute(
            "SELECT key, original_filename, metadata, google_metadata, datetime, db_name, parent, timezone, flags "
            "FROM main WHERE key = ?", (key, ))

        res = self.sq_cur.fetchone()
        if res is None:
            return None

        k, ofn, md, gfmd, _dt, dbn, pr, tz, _flags = res
        dt = datetime.datetime.fromisoformat(_dt)
        flags = MainFlags.from_int(_flags)

        return MainRow(key=k, original_filename=ofn, datetime=dt, db_name=dbn, parent=pr, timezone=tz, flags=flags,
                       metadata=md, google_metadata=gfmd)

    def main_key_flags_iterator(self, allow_selection: bool, selection: Selection = None, **kwargs) \
            -> Iterator[Tuple[int, MainFlags]]:
        """
        Function generates an iterator through the main table. The selection of rows can be controlled using a
        Selection object or flags in the kwargs. If you provide kwargs, they must specify names of flags. These
        can be used as additional constraints in the main table.

        :param selection: Selection object to constrain rows in iterator
        :param allow_selection: Whether a selection object may be provided for this call.

        All possible kwargs booleans, and their names are:

        - present
        - verify
        - trashed
        - org_google_metadata
        - sel_a
        - sel_b
        - has_thumbnail
        - has_miniature
        - duplicate

        ValueError:

        - If a key is specified that's not supported
        - If selection is provided in a location where none is allowed.
        - If sel_a oro sel_b are specified in conjunction with SELECTION or SELECTION_B
            respectively.
        """
        self.add_extra_cursor("main_key_flags_iterator")
        keys = list(kwargs.keys())
        all_keys = {"present", "verify", "trashed", "org_google_metadata", "sel_a", "sel_b", "has_thumbnail",
                    "has_miniature", "duplicate"}

        stmt = "SELECT key, flags FROM main "
        constraints = []
        const_args = []

        if not set(keys).issubset(all_keys):
            raise ValueError(f"{set(keys) - all_keys} keys aren't allowed")

        if selection is not None:
            if not allow_selection:
                raise ValueError("Selection Provided in Call location without selection.")

            if "sel_a" in keys and selection.selection_type == SelectionType.SELECTION_A:
                raise ValueError("Cannot constrain keys with selection and kwarg, sel_a")

            elif "sel_b" in kwargs and selection.selection_type == SelectionType.SELECTION_B:
                raise ValueError("Cannot constrain keys with selection and kwarg, sel_b")

            if selection.selection_type == SelectionType.SELECTION_A:
                constraints += ["mod(flags >> 4, 2) = ?"]
                const_args += [1]
            elif selection.selection_type == SelectionType.SELECTION_B:
                constraints += ["mod(flags >> 5, 2) = ?"]
                const_args += [1]
            elif selection.selection_type == SelectionType.TIME_RANGE:
                constraints += ["datetime(?) <= datetime(datetime)", "datetime(datetime) <= datetime(?)"]
                const_args += [selection.start.isoformat(), selection.end.isoformat()]

        for key, value in kwargs.items():
            # Add the argument
            const_args += [1 if value else 0]
            if key == "present":
                constraints += ["mod(flags, 2) = ?"]
            elif key == "verify":
                constraints += ["mod(flags >> 1, 2) = ?"]
            elif key == "trashed":
                constraints += ["mod(flags >> 2, 2) = ?"]
            elif key == "org_google_metadata":
                constraints += ["mod(flags >> 3, 2) = ?"]
            elif key == "sel_a":
                constraints += ["mod(flags >> 4, 2) = ?"]
            elif key == "sel_b":
                constraints += ["mod(flags >> 5, 2) = ?"]
            elif key == "has_thumbnail":
                constraints += ["mod(flags >> 6, 2) = ?"]
            elif key == "has_miniature":
                constraints += ["mod(flags >> 7, 2) = ?"]
            elif key == "duplicate":
                constraints += ["mod(flags >> 8, 2) = ?"]
            else:
                raise ImplementationError("Uncovered key in main_key_flags_iterator")

        # Execute the statement
        if len(constraints) == 0:
            self.debug_execute(stmt)

        else:
            stmt += " WHERE "
            const_str = ", ".join(constraints)
            self.debug_execute(stmt=stmt + const_str, args=tuple(const_args))

        for key, _flags in self.get_cursor("main_key_flags_iterator"):
            yield key, MainFlags.from_int(_flags)

        self.remove_extra_cursor("main_key_flags_iterator")

    # ==================================================================================================================
    # Display Tables
    # ==================================================================================================================

    def build_import_table_lookup(self, target_table: str):
        """
        Build the row lookup table for an import table
        """
        # TODO implement

    def build_images_table_lookup(self, grouping: GroupingCriterion, trash: bool = None):
        """
        Build the row lookup table for the images table
        """
        # TODO implement

    def build_presence_table_lookup(self):
        """
        Build the lookup table for the presence_table
        """
        # TODO implement

    def hash_update_table_lookup(self):
        """
        Build the lookup table for the hash_update_table
        """
        # TODO implement

    def name_update_table_lookup(self):
        """
        Build the lookup table for the name_update_table
        """
        # TODO implement

    # TODO give smarter name
    def lookup_row_to_xxx(self, key: int, target_table: str, tbl_name: str = None):
        """
        Resolve row to list of image metadata

        :param key: Row to resolve
        :param target_table: str; selection of [main, import, presence, hash, name], case insensitive
        :param tbl_name: Name of the import table.
        """
        int_tbl = target_table.lower().strip()
        self._check_target_table(int_tbl, tbl_name)
        # TODO implement

    def lookup_key_to_row(self, key: int, target_table: str, tbl_name: str = None):
        """
        Resolve a given key from the row table to the row in the ui

        :param key: Row to resolve
        :param target_table: str; selection of [main, import, presence, hash, name], case insensitive
        :param tbl_name: Name of the import table.

        :raises ValueError: If the given target_table isn't supported
        :raises TypeError: If import table is selected and tbl_name isn't selected
        """
        int_tbl = target_table.lower().strip()
        self._check_target_table(int_tbl, tbl_name)
        # TODO implement

    @staticmethod
    def _check_target_table(tgt_tbl: str, tbl_name: str = None):
        """
        Check if the given target_table is allowed

        :param tgt_tbl: str; selection of [main, import, presence, hash, name], case-insensitive
        :param tbl_name: Table name of import table

        :raises ValueError: If the given target_table isn't supported
        :raises TypeError: If import table is selected and tbl_name isn't selected
        """
        assert tgt_tbl.islower(), "Argument should be lower case"
        allowed_targets = {"main", "import", "presence", "hash", "name"}

        if tgt_tbl not in allowed_targets:
            raise ValueError(f"Unhandled Case of Target Table: {tgt_tbl}")

        if tgt_tbl == "import" and tbl_name is None:
            raise TypeError("Selecting Import table requires a table_name to be present")

    # ==================================================================================================================
    # INFO: ALL IMPLEMENTATIONS OF LONG RUNNING ACTIONS
    # ==================================================================================================================


    # INFO: long-running action,
    def update_filename_from_hash(self, move: bool):
        """
        Update the names of files resolved through hash and filesize.

        # INFO: Update only possible for files which are neither a duplicate nor trashed.
        # INFO: Given all MatchTypes, the function only considers HASH_MATCH_MAIN

        :parma move: move the file to the correct location based on it's datetime.
        """
        count = 0
        conflict = 0
        for key, name, dir_name, best_match in self.update_filename_from_hash_iterator():
            assert best_match is not None, "best_match shouldn't be None, SQL Error"

            # Try to get the parent's path
            tgt_path = self.db_resolve_key_to_abs_path(best_match)
            if tgt_path is None:
                self.set_updated_status_name_update_table(
                    key=key, status=NameUpdateStatus.FAILED, message="Matched key doesn't exist in main table")

                conflict += 1
                continue

            if os.path.exists(tgt_path):
                self.set_updated_status_name_update_table(
                    key=key, status=NameUpdateStatus.FAILED, message="Parent File is Present")

                conflict += 1
                continue

            # Determine target location
            if not move:
                dst_path = os.path.join(dir_name, name)
            else:
                dst_path = os.path.join(os.path.dirname(tgt_path), name)

            # Check if the destination exists.
            if os.path.exists(dst_path):
                self.set_updated_status_name_update_table(key=key, status=NameUpdateStatus.FAILED,
                                                          message="File exists at destination")

                conflict += 1
                continue

            flags = self.get_main_flags(best_match)
            assert flags is not None, "Flags should exist, if path resolved"

            if flags.trashed or flags.duplicate:
                self.set_updated_status_name_update_table(
                    key=key, status=NameUpdateStatus.FAILED,message=f"Parent is trash or duplicate, update not allowed")

                conflict += 1

            # Need to update
            dir_key = None
            if os.path.dirname(dst_path) != os.path.dirname(tgt_path):
                dir_key = self.insert_get_dir(os.path.dirname(dst_path))

            os.rename(os.path.join(dir_name, name), os.path.join(os.path.dirname(tgt_path), name))
            flags.present = True

            self.set_updated_status_name_update_table(key=key, status=NameUpdateStatus.UPDATED)
            self.update_row_main_table(key=best_match, db_name=name, flags=flags)

            if dir_key is not None:
                self.update_row_metadata_table(key=key, db_dir=dir_key)

            count += 1

        # TODO logger
        self.commit()
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

        self.delete_dir(keys_to_delete)

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
            if root.startswith(self.get_temp_dir()):
                continue

            if root.startswith(self.get_temp_dir()):
                continue

            if root.startswith(self.get_thumb_dir()):
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
        pd = self.get_path_data(key=key)
        if pd is None:
            raise ValueError(f"Couldn't find Path data for key: {key}")

        dt, flags, db_local_dir, db_name, original_name = pd

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change datetime from files in trash, not present and duplicates")

        new_dt = dt.replace(tzinfo=target_tz) if replace else dt.astimezone(tz=target_tz)

        # Early exit, if the new datetime is equivalent to the old one.
        if new_dt == dt:
            # Only update the timezone
            self.update_row_main_table(key=key, timezone=new_dt.tzname())
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

            self.update_row_main_table(key=key, datetime=new_dt, timezone=new_dt.tzname(), db_name=new_name)

        else:
            self._internal_move_file(ndt=new_dt, key=key, flags=flags, dt=dt, db_local_dir=db_local_dir, dbn=db_name)

            self.update_row_main_table(key=key, datetime=new_dt, timezone=new_dt.tzname())

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

        pd = self.get_path_data(key=key)
        if pd is None:
            raise ValueError(f"Couldn't find Path data for key: {key}")

        dt, flags, db_local_dir, db_name, original_name = pd
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

        self.update_row_main_table(key=key, datetime=new_dt, db_name=new_name, timezone=timezone)

        self.update_row_metadata_table(key=key,
                                       naming_tag=NewMetadataAggregator.serialize_key(tag),
                                       datetime_source=dts)

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
        if self.db_resolve_filename_to_key(new_filename):
            raise ValueError("Filename already exists in main table.")

        # PRECONDITION: Filename not present
        pd = self.get_path_data(key=key)
        if pd is None:
            raise ValueError(f"Couldn't find Path data for key: {key}")

        dt, flags, db_local_dir, db_name, _ = pd

        if not flags.present or flags.trashed or flags.duplicate:
            raise ValueError("Cannot change name from files in trash, not present and duplicates")

        self._internal_rename(key=key,
                              flags=flags,
                              dbn=db_name,
                              new_name=new_filename,
                              dt=dt,
                              db_local_dir=db_local_dir)

        # Update the database after renaming
        self.update_row_main_table(key=key, db_name=new_filename)
        self.update_row_metadata_table(key=key, naming_tag="CUSTOM")

        # Update cache
        if self.filename_to_key_cache.evict(arg=db_name):
            self.filename_to_key_cache.set(arg=db_name, value=key)

        # TODO reset flags of hash, presence and filename tables
        self.clear_presence_table()

        self.commit()

    def verify_custom_target_dir(self, tgt_dir: str):
        """
        Verify the correctness of a custom import directory

        - Path is absolute
        - Path points to directory
        - Path is subdir of root_path
        - Path isn't temp, thumb or trash directory
        """
        if not os.path.isabs(tgt_dir):
            raise TypeError("Destination must be an absolute path")

        if not os.path.isdir(tgt_dir):
            raise TypeError("Destination must point to a directory")

        # Path checks
        if not tgt_dir.startswith(self.root_path):
            raise ValueError("new_dir must start with root_path")

        if tgt_dir.startswith(self.get_thumb_dir()) \
                or tgt_dir.startswith(self.get_temp_dir()) \
                or tgt_dir.startswith(self.get_trash_dir()):
            raise ValueError("Trash, Temp and Thumbnail Directory aren't valid destinations.")

    def move_file(self, key: int, new_dir: str):
        """
        Move a file within the database. Option to set the db_dir later on.

        PRECONDITION:
        - new_dir fulfills verify_custom_target_dir
        - file present, not trashed, not duplicate

        :param key: Key in main database to update with the new filename
        :param new_dir: The new directory to move the file to
        """
        self.verify_custom_target_dir(new_dir)

        flags = self.get_main_flags(key)
        if flags is None:
            raise ValueError("Couldn't find key in main table")

        if flags.trashed or flags.duplicate or not flags.present:
            raise ValueError(f"Invalid state of file, trashed: {flags.trashed}, duplicate: {flags.duplicate}, "
                             f"present: {flags.present}")

        rnd = self.get_path_data(key)
        assert rnd is not None, "Unexpected outcome, path data isn't supposed to be None"

        dt, flags, db_local_dir, db_name, org_name = rnd

        dt_path = os.path.join(self.root_path, self.dt_to_dir(dt))

        source_path = self.db_resolve_key_to_abs_path(key)
        assert source_path is not None, "Unexpected outcome, path for key not available"

        if not os.path.exists(source_path):
            raise FileNotFoundError("Source File not found")

        # We move the file to datetime directory
        if dt_path.removesuffix(os.sep) == new_dir.removesuffix(os.sep):
            # The source and destination path are equivalent, abort.
            if os.path.join(os.path.join(dt_path, db_name)) == source_path:
                return

            # Check destination is empty
            if os.path.exists(os.path.join(dt_path, db_name)):
                raise FileExistsError("File exists at destination")

            # PRECONDITION: destination empty, source present
            os.makedirs(dt_path, exist_ok=True)
            os.rename(source_path, os.path.join(dt_path, db_name))

            # Unset the directory
            self.update_row_metadata_table(key=key, db_dir=None)
            self.prune_db_dir()

        # We move file to other directory
        else:
            dst = os.path.join(new_dir, db_name)
            if dst == source_path:
                return

            if os.path.exists(dst):
                raise FileExistsError("File exists at destination")

            # PRECONDITION: destination empty, source present
            os.makedirs(new_dir, exist_ok=True)
            os.rename(source_path, dst)

            rel = new_dir.removeprefix(self.root_path).removeprefix(os.sep)
            rel_list = rel.split(os.sep)
            dir_key = self.insert_get_dir(rel_list)

            self.update_row_metadata_table(key=key, db_dir=dir_key)
            # TODO self.prune_db_dir_flags

        flags.present = True
        self.update_row_main_table(key=key, flags=flags)
        self.commit()
        # TODO reset flags of hash, presence and filename tables

    def get_media(self, key: int, strict: bool = False) -> MediaPaths:
        """
        Returns a Dataclass which contains the thumbnail path, miniature path and original path.

        PRECONDITION: Key exists.

        """
        # TODO fetch from cache
        # TODO cache answer
        org_path = self.db_resolve_key_to_abs_path(key)
        thumb_path = self.full_thumbnail_path(key)
        mini_path = self.full_miniature_path(key)

        if org_path is None:
            raise ValueError("Key not found")

        # Handle strict case, or case when everything is present
        if strict or (os.path.exists(org_path) and os.path.exists(thumb_path) and os.path.exists(mini_path)):
            return MediaPaths(
                target_key=key,
                original_fp=org_path if os.path.exists(org_path) else None,
                thumbnail_fp=thumb_path if os.path.exists(org_path) else None,
                miniature_fp=mini_path if os.path.exists(mini_path) else None
            )

        # Handle non-strict case with missing paths
        assert not os.path.exists(org_path) or not os.path.exists(thumb_path) or not os.path.exists(mini_path), \
            f"Should have at least something missing"
        parent = self.get_parent(key)

        # No parent found, return what we got.
        if parent is None:
            return MediaPaths(
                target_key=key,
                original_fp=org_path if os.path.exists(org_path) else None,
                thumbnail_fp=thumb_path if os.path.exists(org_path) else None,
                miniature_fp=mini_path if os.path.exists(mini_path) else None
            )

        assert parent is not None, "Need parent for further resolution."

        is_parent_org = is_parent_thumb = is_parent_mini = False
        if not os.path.exists(org_path) and os.path.exists(self.db_resolve_key_to_abs_path(parent)):
            org_path = self.db_resolve_key_to_abs_path(parent)
            is_parent_org = True

        if not os.path.exists(thumb_path) and os.path.exists(self.full_thumbnail_path(parent)):
            thumb_path = self.full_thumbnail_path(parent)
            is_parent_thumb = True

        if not os.path.exists(mini_path) and os.path.exists(self.full_miniature_path(parent)):
            mini_path = self.full_miniature_path(parent)
            is_parent_mini = True

        return MediaPaths(
            target_key=key,
            original_fp=org_path,
            thumbnail_fp=thumb_path,
            miniature_fp=mini_path,

            parent_key=parent,
            is_parent_org=is_parent_org,
            is_parent_thumbnail=is_parent_thumb,
            is_parent_miniature=is_parent_mini
        )

    def get_compare_data(self, key: int | List[int]) -> List:
        """
        Get all necessary information to compare images.

        PRECONDITIOIN: Keys exist.
        """
        if isinstance(key, int):
            int_key = [key]
        else:
            assert isinstance(key, list), "Unexpected type of key argument"
            int_key = key

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
        missing: int = 0
        created: int = 0
        for key, flags in self.main_key_flags_iterator(allow_selection=False,
                                                       present=True, trashed=False, duplicate=False):

            # skip missing images or images in trash
            if not flags.present or flags.trashed or flags.duplicate:
                if __debug__:
                    raise ImplementationError("Error in SQL Statement, should not find trash or not present files")
                continue

            fp = self.db_resolve_key_to_abs_path(key)

            # checking for missing file
            if not os.path.exists(fp):
                # INFO we're not updating the presence in the db because it doesn't fit the scope of this function.
                self.integrity_logger.warning(f"File from DB is missing: {os.path.basename(fp)}, "
                                              f"in {os.path.dirname(fp)}")
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
            self.update_row_main_table(key=key, flags=flags)

        self.commit()
        self.main_logger.info(f"Created: {created} Display Files, found {missing} newly missing")

        missing: int
        created: int
        return created, missing

    def move_to_replaced(self, child_key: int, parent_key: int, copy_google_metadata: bool = True):
        """
        Move a duplicate into the replaced table.

        - Ensure no duplicate chaining
        - Original, Thumbnail, Miniature Deleted, can be taken from parent
        - Attributes are transferred into the replaced table.
        - Need to remove mentions in duplicates and known_duplicates table.

        :param child_key: The key of the entry in the main table which will become the duplicate of the parent key.
        :param parent_key: The key of the file which will be newly the parent considered the original file of the dup.
        :param copy_google_metadata: Copy the Google Metadata from the child to the parent if the parent doesn't have
            Google Metadata
        """
        # Ensure both keys exist.
        parent_data = self.get_replace_data(parent_key)

        if parent_data is None:
            raise ValueError("Parent Key doesn't exist")

        parent_google_metadata, parent_flags, _ = parent_data

        child_data = self.get_replace_data(child_key)
        if child_data is None:
            raise ValueError("Child Key doesn't exist")

        child_gfmd, main_flags, db_name = child_data

        # INFO: Warning User, shouldn't really be occurring, since trashed shouldn't be able to be deduplicated
        if parent_flags.trashed:
            self.main_logger.warning(f"Marking File as Duplicate with Parent in Trash")

        if not parent_flags.present:
            self.main_logger.warning("Marking File as Duplicate without Parent file being present")

        # Cannot update if the file is already duplicate
        if main_flags.duplicate:
            raise ValueError("File is already duplicate")
        main_flags.duplicate = True

        # Check children in replaced table
        children = self.list_children(child_key)
        count = len(children)
        if count > 0:
            self.main_logger.info(f"Updating {count} children of this entry")

            for child in children:
                self.change_parent(key=child, new_parent=parent_key)

        # Check Entries in duplicates table and known_duplicates table
        self.migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=False)
        self.migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=True)

        # Marking row as duplicate in metadata table
        self.update_row_metadata_table(key=child_key, replaced=MediaType.DUPLICATE)

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
        if copy_google_metadata and parent_google_metadata is None and child_gfmd is not None:
            parent_flags.org_google_metadata = False
            self.update_row_main_table(key=parent_key, google_metadata=child_gfmd, flags=parent_flags)

        self.change_parent(key=child_key, new_parent=parent_key)

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
        main_flags = self.get_main_flags(key)
        if main_flags is None:
            raise ValueError(f"Key {key} not found in main table")

        if main_flags.trashed:
            raise ValueError("File is already in Trash")

        if main_flags.duplicate:
            raise ValueError("File is Duplicate")

        # INFO: Get the paths, using resolve correct, bc ui probably
        current_path = self.resolve_key_to_path(key)
        target_path = os.path.join(self.get_trash_dir(), os.path.basename(current_path))

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
        self.update_row_main_table(key=key, flags=main_flags)
        self.update_row_metadata_table(key=key, replaced=MediaType.TRASH)

        self.prune_db_dir()
        self.prune_fs_dir = True

        self.key_to_filepath_cache.update(arg=key, value=target_path)

        # TODO clear presence, hash, filenaem
        self.clear_presence_table()
        self.commit()

    def restore_replaced(self, key: int, create_display_files: bool = True):
        """
        Moves file back to original location
        Updates the metadata table.

        Only works if delete_trash wasn't called already

        :param key: Key in main table to restore
        :param create_display_files: Create thumbnail and miniature if they don't exist
        """
        self._internal_undo(trash=False, key=key, cdf=create_display_files)

    def restore_trash(self, key: int, create_display_files: bool = True):
        """
        Move file back from trash to its original location
        Updates Metadata Table

        Only works if delete_trash wasn't called already

        :param key: Key in main table to restore
        :param create_display_files: Create thumbnail and miniature if they don't exist
        """
        self._internal_undo(trash=True, key=key, cdf=create_display_files)

    def _internal_undo(self, trash: bool, key: int, cdf: bool):
        """
        Internal shared function to undo the two common actions of moving a file to trash and marking a file as
        duplicate

        :param trash: Whether to restore file from trashed or duplicate state
        :param key: Key in Main table of file to restore
        :param cdf: Whether to create display files or not
        """
        # Check row main table
        rep_d = self.get_main_row(key)
        if rep_d is None:
            raise ValueError(f"Key {key} doesn't exist in main table")

        # Check row replaced table
        md = self.get_metadata_row(key)
        if md is None:
            raise ValueError(f"Key {key} doesn't exist in metadata table, cannot undo")

        # check file exists
        cur_path = self.db_resolve_key_to_abs_path(key)
        assert cur_path is not None, "PRECONDITION: Rows found, path must exist"

        if not os.path.exists(cur_path):
            raise FileNotFoundError("File in trash not found")

        # Get data for moving back
        rnd = self.get_path_data(key)
        assert rnd is not None, "Unexpected outcome, couldn't get path data of key"

        dt, flags, db_local_dir, db_name, _ = rnd
        if not flags.duplicate and not trash:
            raise ValueError("File isn't duplicate. Undo replaced doesn't apply")
        elif not flags.trashed and trash:
            raise ValueError("File isn't trashed. Undo trashed doesn't apply")

        self.check_flags(key=key, flags=flags, thumbnail=True, miniature=True, org_path=cur_path)

        # Build dest path
        if db_local_dir is not None:
            db_path = os.path.join(self.root_path, *self.parse_db_local_dir(db_local_dir), db_name)
        else:
            db_path = os.path.join(self.root_path, self.dt_to_dir(dt), db_name)

        # Check dest path doesn't exist
        if os.path.exists(db_path):
            raise FileExistsError("File already exists at destination.")

        os.rename(cur_path, db_path)

        # Update flags after movement
        if trash:
            flags.trashed = False
            flags.present = True
        else:
            flags.duplicate = False
            flags.present = True

        # Create display files if necessary
        if cdf:
            # Create thumbnail
            if not os.path.exists(self.full_thumbnail_path(key)):
                flags.has_thumbnail = self._create_display_file(
                    in_path=db_path, out_path=self.full_thumbnail_path(key), major_size=self.config.thumbnail_target)
            else:
                flags.has_thumbnail = True

            # Create miniature
            if not os.path.exists(self.full_miniature_path(key)):
                flags.has_miniature = self._create_display_file(
                    in_path=db_path, out_path=self.full_miniature_path(key), major_size=self.config.thumbnail_target)
            else:
                flags.has_miniature = True

        self.update_row_metadata_table(key=key, replaced=0)
        if trash:
            self.update_row_main_table(key=key, flags=flags)
        else:
            self.update_row_main_table(key=key, flags=flags, parent=None)

        # TODO update caches
        self.commit()

    def delete_trash_thumb(self, key: Union[int, None]) -> int:
        """
        Delete the remaining thumbnail of an image in the trash. For recognition purposes, the thumbnails of the
        trashed images are retained by default. Use this function with care.

        :param key: Key to delete, list of keys to delete, or delete all thumbnails of images in the trash with None
        """
        count: int = 0

        if key is None:
            it = self.main_key_flags_iterator(allow_selection=False, trashed=1)
        else:
            assert isinstance(key, int), f"Unexpected key type: {type(key).__name__}"
            flags = self.get_main_flags(key)
            if flags is None:
                raise ValueError(f"Key: {key} doesn't exist in main table")
            it = [(key, flags)]

        for key, flags in it:
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

            self.update_row_main_table(key=key, flags=flags)

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
        for key, flags in self.main_key_flags_iterator(allow_selection=False,
                                                       present=True, trashed=False, duplicate=False):

            assert flags.trashed is False and flags.duplicate, "SQL Error, Trashed should be false."
            file_path = self.db_resolve_key_to_abs_path(key)

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

            self.update_row_main_table(key=key, flags=flags)

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

        if duplicates:
            it = self.main_key_flags_iterator(allow_selection=False, duplicate=True)
        else:
            it = self.main_key_flags_iterator(allow_selection=False, trashed=True)

        self.main_logger.info(f"Deleting Originals from Files in {'Duplicates' if duplicates else 'Trash'}")

        # Remove originals from files marked as trash
        for key, flags in it:
            # Check for consistency
            if __debug__:
                if duplicates and flags.duplicate is False:
                    raise ImplementationError("Didn't receive duplicate file despite call for it")
                if not duplicates and flags.trashed is False:
                    raise ImplementationError("Didn't receive trashed file despite call for it")

            # TODO darktable
            file_path = self.db_resolve_key_to_abs_path(key)
            self.check_flags(key=key, flags=flags, org_path=file_path)

            if os.path.exists(file_path):
                self.main_logger.debug(f"Deleting {os.path.basename(file_path)} from trash")
                os.remove(file_path)
                count += 1

            flags.present = False
            self.update_row_main_table(key=key, flags=flags)
            self.delete_row_metadata_table(key=key)

        self.main_logger.info(f"Finished Deleting {count} Originals {'Duplicates' if duplicates else 'Trash'}")
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
        Forgets the image in main table:

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
        flags = self.get_main_flags(key)
        if flags is None:
            raise ValueError("Key not found in main table")

        # Removing all children in replaced
        children = self.list_children(key)
        if rec and len(children) > 0:
            raise CorruptDatabase("Got Entry where the children have children.")

        # Remove children
        for k in children:
            self._internal_forget(key=k, rec=True)

        # TODO darktable
        # Remove files
        fp = self.resolve_key_to_path(key)
        self.check_flags(key=key, flags=flags, miniature=True, thumbnail=True, org_path=fp)

        if rec and not flags.duplicate:
            self.main_logger.warning("Child found who's duplicate flag wasn't set.")

        if os.path.exists(fp):
            # Logging message
            if flags.trashed or flags.duplicate:
                self.main_logger.debug(f"Deleting {os.path.basename(fp)} from trash directory")
            else:
                self.main_logger.debug(f"Deleting {os.path.basename(fp)} from main database")

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
        self.delete_file_association(key)

        # Remove row from metadata
        self.delete_row_metadata_table(key=key)

        # Removing files from the duplicates table
        c_known = self.remove_all_tuples_with_key(key=key, known=True)
        self.main_logger.debug(f"Deleted {c_known} tuples from known_duplicates table")
        c_default = self.remove_all_tuples_with_key(key=key, known=False)
        self.main_logger.debug(f"Deleted {c_default} tuples from default table")

        # Finally deleting the main row
        self.delete_row_main_table(key)
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
        self.filename_to_key_cache.evict(os.path.basename(fp))

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

        for key, flags in self.main_key_flags_iterator(allow_selection=True, selection=selection):
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
                self.update_row_main_table(key=key, flags=flags)

        self.main_logger.info(f"Found {missing_thumb} missing thumbnails and {present_thumb} present thumbnails.")
        self.main_logger.info(f"{correct_thumb} flags for thumbnails were correct")
        self.main_logger.info(f"Found {missing_min} missing miniatures and {present_min} present miniatures.")
        self.main_logger.info(f"{correct_min} miniatures for thumbnails were correct")

        return missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min

    # ==================================================================================================================
    # Path Lookup Methods
    # ==================================================================================================================

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
        return os.path.join(self.get_thumb_dir(), "video_temp.jpeg")

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
