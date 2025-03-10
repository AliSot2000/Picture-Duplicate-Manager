import datetime
import json
import logging
import os.path
import sys
from typing import Set, Dict, List, Union, Tuple, Iterator

from photo_lib.config import Config
from photo_lib.custom_enum import GroupingCriterion, SelectionType, MediaType, Allowed, ImportStatus, NameUpdateStatus, \
    NewMatchTypes
from photo_lib.data_objects import Selection, NewImportTableEntry, MetadataRow, MainRow, MediaPaths
from photo_lib.db_definitions import StaticDeclaration, GenericDeclaration, DBVersion, \
    DBHistorySpec
from photo_lib.db_definitions import current_version as db_current_version
from photo_lib.db_definitions import history as db_history
from photo_lib.errors_and_warnings import ImplementationError, CorruptDatabase
from photo_lib.flag_dataclasses import MainFlags, GenericTableFlags
from photo_lib.metadata_aggregator import MetadataParsingResult
from photo_lib.metadata_aggregator.enums import DateTimeSource
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
    integrity_logger_name: str = "PhotoDB.Integrity"
    rare_occurrence_logger_name: str = "PhotoDB.RareOccurrence"

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
        path = inst.db_path

        inst.cleanup(fast=True)

        new_inst = cls(db_path=path,
                       root_path=inst.root_path,
                       config=inst.config,
                       init=False,
                       init_loggers=False,
                       verify=False,
                       opt_integrity_check=False)

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
        - Both the config and the db_file must not exist.

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

        self.static_decls, self.generic_decls = self.build_definition_lookup()
        self.opt_integrity_check = opt_integrity_check

        # Prepping Config
        if not init:
            if not os.path.exists(db_path):
                raise FileNotFoundError("Database File Not Found")

        else:
            # Checking existence of db file
            if os.path.exists(db_path):
                raise FileExistsError("Database File Exists")

        super().__init__(db_path)

        if init:
            self.__verified = True
            self.init_db()
        else:
            if verify:
                self.__verified = True
                self.__verified = self.__verified and self.verify_tables()
                self.__verified = self.__verified and self.basic_integrity_check()

                if self.verified:
                    self.clear_filename_update_table()
                    self.clear_hash_update_table()
                    self.clear_presence_table()

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
            self.prune_gps()
            self.prune_hash()

            self.basic_integrity_check()

        super().cleanup()

    def init_db(self):
        """
        Create all tables from db_definitions.py
        """
        self.logger.info("Initializing Database")

        for short_name, decl in self.static_decls.items():
            self.logger.info(f"Creating {short_name}")

            self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, decl.name))

        self.logger.info("Initialization Complete")

    @staticmethod
    def build_definition_lookup(version_override: DBVersion = None, history_override: DBHistorySpec = None) \
            -> Tuple[Dict[str, StaticDeclaration], Dict[str, GenericDeclaration]]:
        """
        Get all defined versions and build lookup of the versions.

        Use a sorted list of the previous declarations of the versions and walk backwards until all declarations names
        have an associated value.

        :param version_override: Version to build lookup for
        :param history_override: History to build lookup for

        Populates the attr(static_decls) and attr(generic_decls)
        """
        current_version = db_current_version if version_override is None else version_override
        history = db_history if history_override is None else history_override

        temp_static: Dict[str, StaticDeclaration | None] = {key: None
                                                            for key in current_version.all_definitions}
        temp_generic: Dict[str, GenericDeclaration | None] = {key: None
                                                              for key in current_version.all_generic_definitions}

        # Build the table lookups from the current version.
        for key, value in current_version.definitions.items():
            temp_static[key] = value

        for key, value in current_version.generic_definitions.items():
            temp_generic[key] = value

        cv = current_version.current_version
        ex_old = current_version.previous_version

        # check all values have been populated.
        for i in range(len(history.history)):
            if all(list(temp_static.values()) + list(temp_generic.values())):
                break
            db_declaration = history.history[i]

            # First entry of history is current version
            if db_declaration.current_version == cv:
                continue

            if ex_old is not None and db_declaration.current_version != ex_old:
                raise ImplementationError("Didn't get expected previous version")

            ex_old = db_declaration.previous_version

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

        if not all(list(temp_static.values()) + list(temp_generic.values())):
            raise ImplementationError("Not all declarations were filled.")

        # Check that all generic decls have a table containing the list of the generic tables
        parent_tables = {key: False for key in current_version.all_generic_definitions}
        for key, value in temp_static.items():
            if value.name in parent_tables.keys():
                parent_tables[value.name] = True

        if not all(list(parent_tables.values())):
            raise ImplementationError("Not all generic tables have a parent table. Error in Table Definitions.")

        return temp_static, temp_generic

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

            if not result[0].strip() == decl.declaration_string.replace(decl.name_placeholder, decl.name).strip():
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
                    continue

                if not result[0].strip() == decl.declaration_string.replace(decl.name_placeholder, table).strip():
                    return False

        self.__verified = True
        return True

    def basic_integrity_check(self) -> bool:
        """
        Basic sanity checks on the db to ensure we don't get corrupt data.

        :return: True, all checks ran successfully
        """

        # - Check that file_keys in the hash_assoz table have a matching entry in replaced or main
        # - Check that all entries in main have a hash
        # - Check no entries in main table with reserved db_name
        # - Exactly one entry per file_key with initial flags hash_assoz.
        # - Check constraint on flags: either trashed OR duplicate but both.
        # - Check no duplicate chaining.
        # TODO Implement
        return True

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
            tbl_name = (os.path.basename(os.path.abspath(root_path))
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
        self.debug_execute(stmt="INSERT INTO import_table (root_path, table_name, table_description, flags) "
                                "VALUES (?, ?, ?, ?)",
                           args=(root_path, tbl_name, description, flags.to_int()))

        # Actually creating table
        decl = self.generic_decls["import_table"]
        self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, tbl_name))
        self.commit()
        return tbl_name

    def get_import_tables_size(self, stale: bool = None) -> int:
        """
        Get the number of import tables present in the database

        PRECONDITION: The Table exists
        """
        base_stmt = "SELECT COUNT(key) FROM import_table"
        args = None

        if stale is not None:
            base_stmt += " WHERE mod(flags, 2) = ?"
            args = (stale, )

        self.debug_execute(base_stmt, args)
        return self.sq_cur.fetchone()[0]

    def import_table_flags(self, tbl_name: str) -> GenericTableFlags | None:
        """
        Return the Flags of an Import Table.

        """
        self.debug_execute("SELECT flags FROM import_table WHERE table_name = ?", (tbl_name,))
        res = self.sq_cur.fetchone()

        if res is None:
            return None

        return GenericTableFlags.from_int(res[0])

    def import_table_exists(self, name: str = None) -> bool:
        """
        Check if a given name with root_path and name exists already.
        """
        self.debug_execute("SELECT key FROM import_table WHERE  table_name = ?", (name,))
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

        self.debug_execute("SELECT key FROM import_table WHERE table_name IS ?", (name,))
        del_row = self.sq_cur.fetchone() is not None

        self.debug_execute("DELETE FROM import_table WHERE table_name IS ?", (name,))
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
            stmt = "UPDATE import_table SET flags = flags + 1 WHERE key = ? AND mod(flags, 2) == 0"
            args = (key,)
        else:
            # Update all tables to be stale if they aren't already.
            stmt = "UPDATE import_table SET flags = flags + 1 WHERE mod(flags, 2) == 0"
            args = tuple()

        self.debug_execute(stmt, args)
        self.commit()

    def list_import_tables(self) -> Iterator[NewImportTableEntry]:
        """
        Return List of all Import Tables
        """
        self.add_extra_cursor("list_import_tables")
        self.debug_execute("SELECT key, root_path, table_name, table_name, flags FROM import_table")
        for key, rp, tbl_name, tbl_desc, _flags in self.get_cursor("list_import_tables"):
            yield NewImportTableEntry(key, rp, tbl_name, tbl_desc, GenericTableFlags.from_int(_flags))

        self.remove_extra_cursor("list_import_tables")

    # INFO: Needed for testing
    def get_size_of_single_import_table(self, tbl_name: str):
        """
        Get the number of rows (unfiltered) of an import table.

        Needed for testing.
        """
        self.debug_execute(f"SELECT COUNT(key) FROM `{tbl_name}`")
        return self.sq_cur.fetchone()[0]

    def set_selection_from_import_table(self, sel_a: bool, tbl_name: str) -> int:
        """
        Set the selection flag in the main table of all keys which were imported from this table. Only updates based on
        import, no setting selection based on best_match

        PRECONDITION: The Table exists

        :param sel_a: Whether to set the selection_a flag or the selection_b flag
        :param tbl_name: Name of Import Table from which to generate a selection.

        :raises sqlite3.OperationalError: If the Import Table doesn't exist

        :returns: number of rows affected in main table
        """
        if sel_a:
            self.debug_execute(f"UPDATE main SET flags = flags + 16 WHERE mod(flags >> 4, 2) = 0 "
                               f"AND key IN (SELECT import_key FROM `{tbl_name}` WHERE import_key IS NOT NULL) ")
            rc = self.sq_cur.rowcount
        else:
            self.debug_execute(f"UPDATE main SET flags = flags + 32 WHERE mod(flags >> 5, 2) = 0 "
                               f"AND key IN (SELECT import_key FROM `{tbl_name}` WHERE import_key IS NOT NULL) ")
            rc = self.sq_cur.rowcount
        return rc

    def get_import_table_key_from_path(self, tbl_name: str, path: str) -> int | None:
        """
        Check whether a given path is already present in the import table.

        PRECONDITION: The Table exists

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

        PRECONDITION: The Table exists

        :param tbl_name: Name of table to add the file to
        :param parsing_result: Parsing result of metadata aggregator
        :param allowed_ext: Allowed file extensions, to compute allowed field.

        :raises ValueError: If not append and file in table.
        :raises sqlite3.OperationalError: If the Import Table doesn't exist
        :raises sqlite3.IntegrityError: If the file path already exists
        """
        # Compute complex rows
        int_allowed_ext = [ext.lower() for ext in allowed_ext]
        allowed = os.path.splitext(parsing_result.filename)[1].lower() in int_allowed_ext
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
                                f"WHERE key = ?",
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

        PRECONDITION: The Table exists

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

        else:  # pragma: no cover
            raise ImplementationError(f"Unknown ImportStatus {status.name}")

    def get_update_allowed_iterator_size(self, tbl_name: str) -> int:
        """
        Get the number of rows in the update_allowed_iterator.

        PRECONDITION: Table Exists

        :param tbl_name: import table to query
        """
        self.debug_execute(stmt=f"SELECT COUNT(key) FROM `{tbl_name}` WHERE imported IN (0, 1)")
        return self.sq_cur.fetchone()[0]

    def update_allowed_iterator(self, tbl_name: str) -> Iterator[Tuple[int, Allowed, str]]:
        """
        Creates an iterator to update the allowed state of the files in the import table.

        PRECONDITION: The Table exists

        :param tbl_name: import table to update

        :yields: key, Allowed, org_filename
        """
        self.add_extra_cursor("update_allowed")
        self.debug_execute(stmt=f"SELECT key, allowed, original_filename FROM `{tbl_name}` WHERE imported IN (0, 1)",
                           cur="update_allowed")
        for key, _allowed, org_fname in self.get_cursor("update_allowed"):
            yield key, Allowed(_allowed), org_fname

        self.remove_extra_cursor("update_allowed")

    def get_perform_import_iterator_size(self, tbl_name: str):
        """
        Get the size of the perform_import_iterator. I.e. the number of rows ready to be imported.

        PRECONDITION: Table Exists

        :param tbl_name: import table to query
        """
        self.debug_execute(stmt=f"SELECT COUNT(key) FROM `{tbl_name}` WHERE imported = 1")
        return self.sq_cur.fetchone()[0]

    def perform_import_iterator(self, tbl_name: str) -> Iterator[
        Tuple[int, str, str, str | None, str | None, str, int, datetime.datetime,
              str, str, float | None, float | None, DateTimeSource, Allowed, int | None]]:
        """
        Iterator to get all rows which can be imported from the import table.

        PRECONDITION: The Table exists

        # INFO: Metadata isn't parsed to from json, because we do not need to interact with it.

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
                                f"FROM `{tbl_name}` WHERE imported = 1 ORDER BY original_dirname, original_filename",
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

    def get_import_match_iterator_size(self, tbl_name: str, recompute: bool = False) -> int:
        """
        Get the number of rows to process in the find_import_match_iterator

        PRECONDITION: The Table exists

        :param tbl_name: import table to query
        :param recompute: If the matches are to be recomputed
        """
        if recompute:
            # Reset the match columns before recomputing.
            self.debug_execute(f"UPDATE `{tbl_name}` SET highest_match= NULL, matches = NULL, match_type = 0 "
                               f"WHERE allowed = 1, AND imported IN (0, 1)")

            self.debug_execute(f"SELECT COUNT(key) FROM `{tbl_name}` WHERE imported IN (0, 1) AND allowed = 1")
        else:
            self.debug_execute(f"SELECT COUNT(key) FROM `{tbl_name}` "
                               f"WHERE imported IN (0, 1) AND allowed = 1 AND matches IS NULL")
        return self.sq_cur.fetchone()[0]

    def find_import_match_iterator(self, tbl_name: str, recompute: bool = False) \
            -> Iterator[Tuple[int, str, str, int, str]]:
        """
        Get an iterator with the necessary information to check for matches in the main table.

        PRECONDITION: The Table exists

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

        else:  # pragma: no cover
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

    def selection_from_hash_update_table(self, sel_a: bool) -> int:
        """
        Given the name_update_table, set either the sel_a or sel_b flag for all rows which successfully update a row in
        the main table.

        :param sel_a: Whether to set the sel_a or sel_b flag

        :return: Number of rows affected in main table.
        """
        if sel_a:
            self.debug_execute(f"UPDATE main SET flags = flags + 16 WHERE mod(flags >> 4, 2) = 0 "
                               f"AND key IN (SELECT main_key FROM hash_update_table ) ")
            rc = self.sq_cur.rowcount
        else:
            self.debug_execute(f"UPDATE main SET flags = flags + 32 WHERE mod(flags >> 5, 2) = 0 "
                               f"AND key IN (SELECT main_key FROM hash_update_table) ")
            rc = self.sq_cur.rowcount
        return rc

    def delete_row_hash_update_table(self, key: int):
        """
        Delete a row from the hash_update_table (needed in case you don't want to update all files)

        :param key: key to delete from hash_update_table
        """
        self.debug_execute("DELETE FROM hash_update_table WHERE main_key = ?", (key,))
        assert self.sq_cur.rowcount == 1, "SQL Error, Failed to Delte Row from hash_update_table"

    def insert_row_hash_update_table(self, key: int, new_hash: str, file_size: int):
        """
        Insert a new row into the hash_update_table.

        :param key: Key of the file in the main table
        :param new_hash: New hash of the file
        :param file_size: New file size of the file
        """
        self.debug_execute(stmt="INSERT INTO hash_update_table (main_key, new_hash, file_size_bytes) VALUES (?, ?, ?)",
                           args=(key, new_hash, file_size))

        assert self.sq_cur.rowcount == 1, "SQL ERROR, Failed to Insert Row into hash_update_table"

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

    def get_update_filename_from_hash_iterator_size(self) -> int:
        """
        Get the number of rows of name_update_table that need to be processed
        """
        self.debug_execute("SELECT COUNT(key) FROM name_update_table "
                           "WHERE best_match IS NOT NULL AND updated = 0 AND match_type = 2")
        return self.sq_cur.fetchone()[0]

    def update_filename_from_hash_iterator(self) -> Iterator[Tuple[int, str, str, int]]:
        """
        Get an iterator to all rows of the name_update_table which can be used to update the file name of a file matched
        by file hash.

        The criteria are:

        - best_match must contain an integer (pointing to the file in the main table that is the candidate to update)
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
                           "WHERE best_match IS NOT NULL AND updated = 0 AND match_type = 2",
                           cur="name_update")

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

    def delete_dir(self, key: int | List[int]):
        """
        Delete row(s) of the directory table, given a key.

        PRECONDITION: Rows exist in table
        """
        if isinstance(key, int):
            raw_key = [key]
        else:
            assert isinstance(key, list), f"Unexpected Type: {type(key).__name__}"
            raw_key = key

        pruned_keys = list(set(raw_key))
        self.debug_execute_many("DELETE FROM db_dir WHERE key = ?", args=[(k,) for k in pruned_keys])

        # TODO test
        assert len(pruned_keys) == self.sq_cur.rowcount, (f"Unexpected number of updated rows {self.sq_cur.rowcount}, "
                                                          f"given keys: {pruned_keys}")

    def get_prune_db_dir_iterator_size(self) -> int:
        """
        Get the number of rows to process in the prune_db_dir_iterator
        """
        self.debug_execute("SELECT COUNT(key) FROM db_dir WHERE key NOT IN (SELECT db_dir FROM metadata)")
        return self.sq_cur.fetchone()[0]

    def prune_db_dir_iterator(self) -> Iterator[Tuple[int, List[str]]]:
        """
        Get an iterator to all custom directories which are now empty.

        Tuple elements are:
        - key in db_dir table
        - node list of directory relative to db_root
        """
        self.add_extra_cursor("prune_db_dir")
        self.debug_execute("SELECT key, db_local_dir FROM db_dir WHERE key NOT IN (SELECT db_dir FROM metadata)",
                           cur="prune_db_dir")

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
                               "WHERE h.hash = ? AND ha.file_size_bytes = ? AND ha.initial = 1",
                               (target_hash, file_size))
        else:  # pragma: no cover
            raise ImplementationError(f"Got unexpected mode {mode.lower()}")

        return [r[0] for r in self.sq_cur.fetchall()]

    def get_newest_hash(self, key: int) -> Tuple[str, int, datetime.datetime] | Tuple[None, None, None]:
        """
        Get the newest hash of a given file.

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

        return res[0], res[1], datetime.datetime.fromisoformat(res[2])

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

    def get_number_of_hashes_of_file(self, key: int) -> int:
        """
        Get the number of hashes associated with a file.

        :param key: key in main table.
        """
        self.debug_execute("SELECT COUNT(*) FROM hash_assoz WHERE file_key = ?", (key,))
        return self.sq_cur.fetchone()[0]

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
        :param initial: Only consider initial hashes of images Otherwise, consider all hashes
            AND inserted hash isn't initial.

        :return: True if the row exists, True, row existed but wasn't newest one, False if the row were added.
        """
        # INFO: CASE Initial
        if initial:
            self.debug_execute("SELECT h.hash, ha.hash_key, ha.file_key "
                               "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                               "WHERE h.hash = ? AND ha.file_key = ? AND ha.file_size_bytes = ? AND ha.initial = 1",
                               (file_hash, file_key, file_size))

            res = self.sq_cur.fetchall()

            if len(res) > 1:
                raise CorruptDatabase("There's not supposed to be more than one initial hash per file.")

            if len(res) == 0:
                now = datetime.datetime.now(datetime.timezone.utc)
                hash_key = self.insert_get_hash_key(file_hash=file_hash)
                self.debug_execute("INSERT INTO hash_assoz (hash_key, file_key, file_size_bytes, hash_date, initial) "
                                   "VALUES (?, ?, ?, ?, 1)",
                                   (hash_key, file_key, file_size, now.isoformat()))
                return False

            assert len(res) == 1, "POSTCONDITION Failed: Unexpected number of rows found."

            return True

        # INFO: Case any hash
        else:
            # Get the necessary rows
            self.debug_execute("SELECT ha.hash_key, ha.file_key, ha.file_size_bytes, ha.hash_date "
                               "FROM hashes AS h JOIN hash_assoz AS ha ON h.key = ha.hash_key "
                               "WHERE h.hash = ? AND ha.file_key = ? AND ha.file_size_bytes = ?",
                               (file_hash, file_key, file_size))

            # Hash doesn't exist, add it
            res = self.sq_cur.fetchone()
            if res is None:
                now = datetime.datetime.now(datetime.timezone.utc)
                hash_key = self.insert_get_hash_key(file_hash=file_hash)
                self.debug_execute(
                    "INSERT INTO hash_assoz (hash_key, file_key, file_size_bytes, hash_date, initial) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (hash_key, file_key, file_size, now.isoformat()))

                return False

            # Parse the row and get the newest hash
            hash_key, file_key, file_size_db, _hash_date = res

            hash_date = datetime.datetime.fromisoformat(_hash_date)

            assert file_size == file_size_db, "Unexpected outcome, file size doesn't match"

            newest_hash, newest_size, fhdt = self.get_newest_hash(res[1])

            # A newest hash should exist, previouse result wasn't None
            if (newest_hash, newest_size, fhdt) == (None, None, None):  # pragma: no cover
                raise CorruptDatabase("File without File hash found")

            assert hash_date <= fhdt, "PRECONDITION Failed: Newest datetime of hash is older than found hash"

            # Check the given hash is the newest hash of the file and update otherwise.
            if newest_hash != file_hash or newest_hash == file_hash and newest_size != file_size:
                if newest_hash == file_hash and newest_size != file_size:
                    self.rare_occurrence_logger.info(f"Found matching hashes with different file sizes: "
                                                     f"{newest_hash}, {newest_size}")

                ndt = datetime.datetime.now(datetime.timezone.utc)
                # Update the row to be the newest one.
                self.debug_execute(stmt="UPDATE hash_assoz "
                                        "SET hash_date = ? "
                                        "WHERE hash_key = ? AND file_key = ? AND file_size_bytes = ? AND hash_date = ?",
                                   args=(ndt.isoformat(), hash_key, file_key, file_size, _hash_date))


            return True

        raise ImplementationError("Tertiem Non Datur")  # pragma: no cover

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
                else:  # pragma: no cover
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

        - original_dirname: str
        - naming_tag: str
        - datetime_source: DateTimeSource
        - gps_location: int
        - db_dir: int
        - replaced: MediaType
        """
        given = set(kwargs.keys())
        all_cols = {"original_dirname", "naming_tag", "datetime_source", "gps_location", "db_dir", "replaced"}

        if "original_dirname" in kwargs.keys():
            raise ValueError("Column: original_dirname can only be set in the insert_row function. $"
                             "This column shouldn't change")

        # Check the keys datetime_source
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

        mk, ofd, nt, _dts, _rep, db_ld, gps_lat, gps_long = res
        dts = DateTimeSource(_dts)
        rep= MediaType(_rep)
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

        - original_filename: str
        - metadata: str | dict | list | None
        - google_metadata: str | dict | list | None
        - datetime: datetime.datetime (timezone aware object)
        - db_name: str
        - parent: int
        - timezone: str
        - flags: MainFlags
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

        # Convert flags
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
        else:  # pragma: no cover
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

        if len(res) > 1:  # pragma: no cover
            raise CorruptDatabase(f"file_name {file_name} appears in main and replaced table.")

        # PRECONDITION: number of results = 1
        return res[0][0]

    def db_resolve_org_filename_to_keys(self, org_name: str) -> List[int]:
        """
        Resolve the Search for keys which have the matching original file name

        :param org_name: org_name to match against
        :return: (potentially empty) of keys which had this file name originally.
        """
        self.debug_execute("SELECT key FROM main WHERE original_filename = ?", (org_name,))
        return [res[0] for res in self.sq_cur.fetchall()]

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

    def get_main_key_flags_iterator_size(self, allow_selection: bool, selection: Selection = None, **kwargs) -> int:
        """
        Get the number of rows covered in the main table by a given selection and kwargs.

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
        keys = list(kwargs.keys())
        all_keys = {"present", "verify", "trashed", "org_google_metadata", "sel_a", "sel_b", "has_thumbnail",
                    "has_miniature", "duplicate"}

        stmt = "SELECT COUNT(key) FROM main "
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

        return self.sq_cur.fetchone()[0]

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
            self.debug_execute(stmt, cur="main_key_flags_iterator")

        else:
            stmt += " WHERE "
            const_str = ", ".join(constraints)
            self.debug_execute(stmt=stmt + const_str, args=tuple(const_args), cur="main_key_flags_iterator")

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

    def build_hash_update_table_lookup(self):
        """
        Build the lookup table for the hash_update_table
        """
        # TODO implement

    def build_name_update_table_lookup(self):
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
