import datetime
import functools
import logging
import multiprocessing.connection as connection
import os.path
from typing import Set, Dict, List, Union, Tuple

import photo_lib.defaults as defaults
from custom_enum import GroupingCriterion
from photo_lib.config import Config
from photo_lib.db_definitions import current_version, history, StaticDeclaration, GenericDeclaration
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.flag_dataclasses import MainFlags
from photo_lib.sqlite_wrapper import BaseSQliteDB


class PhotoDB(BaseSQliteDB):
    __verified: bool = False
    config: Config

    root_path: str

    static_decls: Dict[str, StaticDeclaration]
    generic_decls: Dict[str, GenericDeclaration]

    # Redefining logger as mandatory
    logger: logging.Logger

    @property
    def current_version(self):
        return current_version.current_version

    def __init__(self,
                 root_path: str,
                 logger: logging.Logger,
                 init: bool = False,
                 config: Config = None,):
        """
        Construct a Database Object from a preexisting database file.
        """
        self.logger = logger
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
                config = self.build_default_config(self.root_path)

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

    # ==================================================================================================================
    # Table Creation & Deletion & Modify Functions
    # ==================================================================================================================

    def init_db(self):
        """
        Create all tables from
        """
        self.logger.info("Initializing Database")

        for short_name, decl in self.static_decls.items():
            self.logger.info(f"Creating {short_name}")

            self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, decl.name))

        self.logger.info("Initialization Complete")

    @staticmethod
    def build_default_config(root_path: str) -> Config:
        """
        Create a new config with only defaults.
        """
        return Config(
            version=current_version.current_version,
            image_extensions=defaults.image_extensions,
            video_extensions=defaults.video_extensions,
            allowed_extensions=defaults.extensions,
            temp_path=defaults.temp_path(root_path),
            thumbnail=defaults.thumbnails_path(root_path),
            trash=defaults.trash_path(root_path),
            db_file=defaults.db_file,

        )

    def add_import_table(self, root_path: str, name: str = None, description: str = None):
        """
        Add a new import table to the database.

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
            self.logger.warning(f"Table Name longer than 120 characters. Truncating to: {tbl_name}")

        # Add the table to the generic lookup table
        self.debug_execute("INSERT INTO import_tables (root_path, table_name, table_description) VALUES (?, ?, ?)",
                           (root_path, tbl_name, description))

        # Actually creating table
        decl = self.generic_decls["import_table"]
        self.debug_execute(decl.declaration_string.replace(decl.name_placeholder, tbl_name))
        self.commit()

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

    def compress(self):
        """
        Remove all files which can be recomputed to save space. Removes all Thumbnails and all temporary files
        generated for deduplication.
        """
        ...

    def clear_trash(self):
        """
        Removes all originals from the trash.
        """
        ...

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
                    self.logger.warning(f"Found orphaned entry: {table} in the parent table: {name}. "
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

    # ==================================================================================================================
    # File Integrity checks
    # ==================================================================================================================

    def list_changed_hashes(self, from_select: bool = False):
        """
        Create an import table full of files who's hash has changed.

        Goes through all images in the database and checks the hash of their counterpart.

        :param from_select: Use selection marker of images to check changed hashes only for those images.
        """

    def update_hash_from_filename(self, fname: Dict[str, str]):
        """
        Updates the hash of the image file with the given file name.
        """

    def list_changed_filenames(self, from_select: bool = False):
        """
        Match hash and filesize of files against the db. If the two match and the filename is different, these files
        will be added to the new import table.

        :param from_select: Use selection marker of images to check changed hashes only for those images.
        """

    def update_filenames(self, new_names: Dict[int, str]):
        """
        Update the names of files resolved through hash and filesize.
        """
        ...

    def check_presence(self, from_select: bool = False):
        """
        Go through db and check that all files in the db are present in the file system.

        :param from_select: Use selection marker of images to check changed hashes for those images.
        """
        ...

    def update_trash_from_presence(self, from_select: bool = False):
        """
        Update the files which have aren't present to have been moved to the trash.

        :param from_select: Use the selection marker to only affect those files.
        """
        ...

    def check_thumbnails(self, from_select: bool = False):
        """
        Go through db and check the mark for thumbnail and a thumbnail existing are correct.

        :param from_select: Use selection marker of images to check changed hashes for those images.
        """
        ...

    # ==================================================================================================================
    # Importing
    # ==================================================================================================================

    def prepare_directory_for_import(self,
                                     source_dir: str,
                                     allowed_ext: Set[str] = None,
                                     tbl_name: str = None,
                                     recursive: bool = True,
                                     append: bool = False,
                                     purge: bool = False):
        """
        Go through all files in the directory, and prepare the index for import.

        :param source_dir: Directory to import into the db
        :param allowed_ext: Allowed extensions to import from. Defaults to None (Uses from Config)
        :param tbl_name: Name of temporary table created for import. Defaults to hash(datetime.now())
        :param recursive: Recursively index all subdirectories.

        :param append: Files were added in the import directory. Add the new files to the table. Don't modify the data
            in the import table for the files already indexed.
        :param purge: Clear the import table and perform indexing again, retaining the table name.
        """

    # TODO should we return anything? New number of allowed files, new number of disallowed files, deltas? =>
    #  Extra query
    def update_allowed(self, allowed_ext: Set[str], tbl: str):
        """
        Update the allowed extensions for a given

        :param allowed_ext: Allowed extensions to import from.
        :param tbl: Name of temporary table created for import.
        """
        ...

    def perform_import(self, tbl: str, dest_dir: str = None, add_safety_exif_tags: bool = None) -> int:
        """
        Imports all files from the given import table into the main database.
        - Files which are imported already will be ignored and
        - All disallowed files will not be imported.

        :param tbl: Name of the table to import from
        :param dest_dir: Destination directory to create in within the database. Defaults to db/yyyy/mm/dd/
        :param add_safety_exif_tags: Add the datetime to exiftag if only filesystem datetime is available.
            (Override, default taken from config)

        :return: Number of imported files
        """
        ...

    def import_other_db(self):
        """
        Functionality needed because some images are only on older dbs including their metadata.
        """

    # ==================================================================================================================
    # Deduplication
    # ==================================================================================================================

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

    def add_known_duplicate(self, key_a: int, key_b: int):
        """
        Moves a pair of duplicates into the known_duplicates table.
        """
        if key_b == key_a:
            raise ValueError("Identical Keys.")

        if key_a >= key_b:
            key_a, key_b = key_b, key_a

        self.debug_execute("INSERT OR IGNORE INTO known_duplicates (key_a, key_b) VALUES (?, ?)",
                           (key_a, key_b))

    def remove_known_duplicate(self, key_a: int, key_b: int):
        """
        Removes a pair of duplicates from the known_duplicates table.
        """
        if key_b == key_a:
            raise ValueError("Identical Keys.")

        if key_a >= key_b:
            key_a, key_b = key_b, key_a

        self.debug_execute("DELETE FROM known_duplicates WHERE key_a = ? AND key_b = ?", (key_a, key_b))

    # ==================================================================================================================
    # UI
    # ==================================================================================================================

    def change_datetime(self,
                        key: int,
                        new_dt: datetime.datetime = None,
                        tag: datetime.datetime = None,
                        rename: bool = True):
        """
        Change the datetime associated with the given image. Each image should have a filename string and a given
        datetime. The file name will also be adapted.

        :param key: key of image to update
        :param new_dt: new datetime object. (should have an utc offset)
        :param tag: tag of image to use for update.
        :param rename: Rename image if True.
        """
        ...

        # Last operation, clear lookup caches
        self.filename_to_key.clear_cache()
        self.resolve_key_to_path.clear_cache()

    def change_filename(self, key: int, new_filename: str):
        """
        Change the filename. Set a custom filename.

        :param key: Key in main database to update with the new filename
        :param new_filename: The new file name to use. Sets the db_name column.
        """
        # Last operation, clear lookup caches
        self.filename_to_key.clear_cache()
        self.resolve_key_to_path.clear_cache()

    def build_import_table_lookup(self, target_table: str):
        """
        Build the row lookup table for a import table
        """
        ...

    def build_images_table_lookup(self, grouping: GroupingCriterion, trash: bool = None):
        """
        Build the row lookup table for the images table
        """
        ...

    # TODO give smarter name
    def lookup_row_to_xxx(self, row: int, images_table: bool = True):
        """
        Resolve row to list of image metadata

        :param row: Row to resolve
        :param images_table: If true, resolve images table else import table
        """

    def lookup_key_to_row(self, key: int, images_table: bool = True):
        """
        Resolve a given key from the row table to the row in the ui

        :param key: Row to resolve
        :param images_table: If true, resolve images table else import table
        """

    # ==================================================================================================================
    # Utility
    # ==================================================================================================================

    def create_thumbnails(self):
        """
        Create thumbnails for all elements in the database.
        """
        ...

    def _create_img_thumbnails(self):
        """
        Create thumbnails for images in the database.
        """
        ...

    def _create_vid_thumbnails(self):
        """
        Create thumbnails for the videos in the database.
        """

    def move_to_replaced(self, child_key: int, parent_key: int):
        """
        Move a duplicate into the replaced table.
        """
        ...

    def move_to_trash(self, key: int):
        """
        Move a given image to trash.
        """
        ...

    def delete_trash_thumb(self, key: Union[List[int], int, None]):
        """
        Delete the remaining thumbnail of an image in the trash. For recognition purposes, the thumbnails of the
        trashed images are retained.
        """
        ...

    def forget_image(self, key: int):
        """
        Forgets the image:

        Removes it from all tables and removes all children. Images which are forgotten, will be not be detected
        upon import and will be reimported if the given image shows up again.
        """
        ...

    @functools.lru_cache(maxsize=1024)
    def resolve_key_to_path(self, key: int):
        """
        Get the original filename for image
        """
        ...

    @functools.lru_cache(maxsize=1024)
    def filename_to_key(self, fname: str):
        """
        Resolve a filename to key
        """
        ...

    # ==================================================================================================================
    # Util
    # ==================================================================================================================

    @staticmethod
    def dt_to_dir(dt: datetime.datetime) -> str:
        """
        Get path suffix for
        """
        return os.path.join(dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"))
