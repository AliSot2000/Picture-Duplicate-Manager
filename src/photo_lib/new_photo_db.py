import datetime
import functools
import logging
import multiprocessing.connection as connection
import os.path
from typing import Set, Dict, List, Union, Tuple

import cv2
import ffmpeg

import photo_lib.defaults as defaults
from custom_enum import GroupingCriterion
from photo_lib.config import Config
from photo_lib.db_definitions import current_version, history, StaticDeclaration, GenericDeclaration
from photo_lib.errors_and_warnings import ImplementationError
from photo_lib.flag_dataclasses import MainFlags, ReplacedFlags
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
        # TODO paths should be relative
        return Config(
            version=current_version.current_version,
            image_extensions=defaults.image_extensions,
            video_extensions=defaults.video_extensions,
            allowed_extensions=defaults.extensions,
            temp_path=defaults.temp_path,
            thumbnail=defaults.thumbnails_path,
            trash=defaults.trash_path,
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

    def add_default_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Moves a pair of duplicates into the known_duplicates table.
        """
        self._internal_add_duplicate(key_a=key_a, key_b=key_b, known=False)

    def remove_default_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Removes a pair of duplicates from the known_duplicates table.
        """
        self._internal_remove_duplicate(key_a=key_a, key_b=key_b, known=False)

    def add_known_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Moves a pair of duplicates into the known_duplicates table.
        """
        self._internal_add_duplicate(key_a=key_a, key_b=key_b, known=True)

    def remove_known_duplicate(self, key_a: int | List[int], key_b: int | List[int]):
        """
        Removes a pair of duplicates from the known_duplicates table.
        """
        self._internal_remove_duplicate(key_a=key_a, key_b=key_b, known=True)

    def _internal_add_duplicate(self, key_a: int | List[int], key_b: int | List[int], known: bool):
        """
        Internal Function to add a duplicate tuple, parametrizes the table to modify.

        :param key_a: First key of Tuple
        :param key_b: Second key of Tuple
        :param known: If true, will remove the tuple from the  known_duplicates table else duplicates table.
        """
        tbl = "known_duplicates" if known else "duplicates"

        if isinstance(key_a, int) and isinstance(key_b, int):
            if key_b == key_a:
                raise ValueError("Identical Keys.")

            if key_a >= key_b:
                key_a, key_b = key_b, key_a

            self.debug_execute(f"INSERT OR IGNORE INTO {tbl} (key_a, key_b) VALUES (?, ?)",
                               (key_a, key_b))

        elif isinstance(key_a, list) and isinstance(key_b, list):
            if not len(key_a) == len(key_b):
                raise ValueError("key_a and key_b must have same length")

            args = []
            for ka, kb in zip(key_a, key_b):
                if ka == kb:
                    raise ValueError("Identical Keys.")

                args.append((kb, ka) if ka >= kb else (kb, ka))

            self.debug_execute_many(f"INSERT OR IGNORE INTO {tbl} (key_a, key_b) VALUES (?, ?)",
                                    args)
        else:
            raise TypeError("key_a and key_b must be either both list or both int.")

    def _internal_remove_duplicate(self, key_a: int | List[int], key_b: int | List[int], known: bool):
        """
        Internal Function to remove a duplicate tuple, parametrizes the table to modify.

        :param key_a: First key of Tuple
        :param key_b: Second key of Tuple
        :param known: If true, will remove the tuple from the  known_duplicates table else duplicates table.
        """
        tbl = "known_duplicates" if known else "duplicates"

        if isinstance(key_a, int) and isinstance(key_b, int):
            if key_b == key_a:
                raise ValueError("Identical Keys.")

            if key_a >= key_b:
                key_a, key_b = key_b, key_a

            self.debug_execute(f"DELETE FROM {tbl} WHERE key_a = ? AND key_b = ?", (key_a, key_b))

        elif isinstance(key_a, list) and isinstance(key_b, list):
            if not len(key_a) == len(key_b):
                raise ValueError("key_a and key_b must have same length")

            args = []
            for ka, kb in zip(key_a, key_b):
                if ka == kb:
                    raise ValueError("Identical Keys.")

                args.append((kb, ka) if ka >= kb else (kb, ka))

            self.debug_execute_many(f"DELETE FROM {tbl} WHERE key_a = ? AND key_b = ?",
                                    args)
        else:
            raise TypeError("key_a and key_b must be either both list or both int.")
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

    def create_display_files(self, miniature: bool = True, thumbnail: bool = True, overwrite: bool = False) \
            -> Tuple[int, int]:
        """
        Create thumbnails for all elements in the database.

        :param miniature: If true, create miniature images
        :param thumbnail: If true, create thumbnails images
        :param overwrite: If true, overwrite existing files.

        returns: <number of new files created> and <number of undetected missing files>
        """
        self.add_extra_cursor("update_thumbnails")

        # TODO switch to >> operator
        self.debug_execute("SELECT m.key, m.datetime, m.db_name, d.db_local_dir, m.flags "
                           "FROM main AS m JOIN db_dir AS d ON main.db_dir = db_dir.key "
                           # Check present                 check trash
                           "WHERE mod(m.flags, 2) == 1 AND mod(m.flags / 4, 2) == 0")

        missing = 0
        created = 0
        for row in self.sq_cur:
            key, _dt, dbn, _db_dir, _flags = row

            flags = MainFlags.from_int(_flags)
            dt = datetime.datetime.fromisoformat(_dt)
            par_dir = os.path.join(self.db_path, _db_dir) if _db_dir else os.path.join(self.root_path,
                                                                                       self.dt_to_dir(dt))

            # skip missing images or images in trash
            if not flags.present or flags.trashed:
                assert False, "Error in SQL Statement, should not find trash or not present files."
                continue

            # keeping track of missing files
            if not os.path.exists(os.path.join(par_dir, dbn)):

                # INFO we're not updating the presence in the db because it doesn't fit the scope of this function.
                self.logger.warning(f"File from DB is missing: {dbn}, in {par_dir}")
                missing += 1
                continue

            # Thumbnail: write if not exists or exists + overwrite
            if thumbnail:
                if (not os.path.exists(os.path.join(self.get_thumb_dir(), self.thumbnail_name(key)))
                        or (os.path.exists(os.path.join(self.get_thumb_dir(), self.thumbnail_name(key)))
                            and overwrite)):

                    flags.has_thumbnail = self._create_display_file(
                        in_path=os.path.join(par_dir, dbn),
                        out_path=os.path.join(self.get_thumb_dir(), self.thumbnail_name(key)),
                        major_size=self.config.thumbnail_target)
                    created += 1

                else:
                    self.logger.debug(f"Thumbnail already exists for key: {key}")
                    flags.has_thumbnail = True

            # Miniature: write if not exists or exists + overwrite
            if miniature:
                if (not os.path.exists(os.path.join(self.get_thumb_dir(), self.miniature_name(key)))
                        or (os.path.exists(os.path.join(self.get_thumb_dir(), self.miniature_name(key)))
                            and overwrite)):

                    flags.has_miniature = self._create_display_file(
                        in_path=os.path.join(par_dir, dbn),
                        out_path=os.path.join(self.get_thumb_dir(), self.miniature_name(key)),
                        major_size=self.config.thumbnail_target)
                    created += 1

                else:
                    self.logger.debug(f"Miniature already exists for key: {key}")
                    flags.has_miniature = True

            # Update the flags of the given key.
            self.debug_execute(stmt="UPDATE main SET flags = ? WHERE key = ?",
                               args=(flags.to_int(), key),
                               cur="update_thumbnails")

        self.remove_extra_cursor("update_thumbnails")
        self.commit()
        self.logger.info(f"Created: {created} Display Files, found {missing} newly missing")
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
            self.logger.warning(f"Unknown extension: {in_path}. Attempting to to create display file anyway")

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
            self.logger.exception(f"OpenCV encountered an error while generating the thumbnail for {in_path}",
                                  exc_info=e)
        except Exception as e:
            self.logger.exception(f"Unexpected Exception while generating thumbnail: {e}", exc_info=e)

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
            self.logger.exception(f"Error Probing File with FFMPEG: {in_path}, "
                                  f"stderr: {e.stderr.decode('utf-8')}, "
                                  f"stdout: {e.stdout.decode('utf-8')}", exc_info=e)
            return False

        except Exception as e:
            self.logger.exception(f"Unexpected Exception while Probing File: {in_path}", exc_info=e)
            return False

        # Get target time for the image.
        try:
            if probe_res["streams"][0]["duration"] < target_time:
                self.logger.warning("Video to short for default time point where to take thumbnail")
                target_time = probe_res["streams"][0]["duration"] // 2

            # Try to get the width of the stream
            for stream in probe_res["streams"]:
                width = stream.get("width")

                if width is not None:
                    break

        except KeyError:
            self.logger.error(f"Failed to get time data from probe result of ffmpeg: {in_path}")
        except IndexError:
            self.logger.error("Failed to get time data from probe result of ffmpeg")
        except Exception as e:
            self.logger.exception(f"Unexpected error {type(e).__name__}", exc_info=e)

        if width is None:
            self.logger.info(f"Failed to retrieve width of the input file: {in_path}, aborting")
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
            self.logger.exception(f"Error Exporting Thumbnail from video: {in_path}, "
                                  f"stderr: {e.stderr.decode('utf-8')}, "
                                  f"stdout: {e.stdout.decode('utf-8')}", exc_info=e)
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected Exception while writing thumbnail: {type(e).__name__}", exc_info=e)
            return False

        return True

    def move_to_replaced(self, child_key: int, parent_key: int):
        """
        Move a duplicate into the replaced table.

        - Ensure no duplicate chaining
        - Original, Thumbnail, Miniature Deleted, can be taken from parent
        - Attributes are transferred into the replaced table.
        - Need to remove mentions in duplicates and known_duplicates table.
        """
        self.debug_execute("SELECT key, flags FROM main WHERE key = ?", (parent_key,))
        raw_parent = self.sq_cur.fetchall()

        if len(raw_parent) == 0:
            raise ValueError("Parent Key doesn't exist in main table.")

        assert len(raw_parent) == 1, "SQL Error, Shouldn't be able to hae more than one with same key"
        photo_libflags = MainFlags.from_int(raw_parent[0][1])

        # INFO: Warning User, shouldn't really be occurring, since trashed shouldn't be able to be deduplicated
        if photo_libflags.trashed:
            self.logger.warning(f"Moving File to Replaced Table with Parent in Trash.")

        if not photo_libflags.present:
            self.logger.warning("Moving File to Replaced Table without Parent file being present.")

        # Execute Statement here, because we want to be sure that this key exists.
        self.debug_execute(stmt="SELECT m.key, m.db_name, m.original_filename, m.metadata, m.google_metadata, "
                                "m.datetime, m.timezone, m.flags, d.db_local_dir "
                                "FROM main AS m JOIN db_dir AS d ON main.db_dir = db_dir.key WHERE m.key = ?",
                           args=(child_key,))

        result = self.sq_cur.fetchone()
        if result is None:
            raise ValueError("Child Key not found in replaced table")

        # Unpack result for ease of use
        key, db_name, original_filename, metadata, google_metadata, _dt, timezone, _flags, db_dir = result

        # Parse the datetime for folder
        dt = datetime.datetime.fromisoformat(_dt)
        main_flags = MainFlags.from_int(_flags)

        # Check children in replaced table
        self.debug_execute("SELECT COUNT(*) FROM replaced WHERE parent == ?", args=(child_key,))
        count = self.sq_cur.fetchone()[0]

        if count > 0:
            self.logger.info(f"Updating {count} children of this entry in the replaced table")

            self.debug_execute("UPDATE replaced SET parent = ? WHERE parent = ?", (child_key, parent_key))

        # Check Entries in duplicates table
        self._migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=False)

        # Check Entries in known_duplicates table
        self._migrate_parent_duplicate(child_key=child_key, parent_key=parent_key, known=True)

        # Inserting first the key into the replaced table
        self.debug_execute(stmt="INSERT OR REPLACE INTO replaced (key, original_filename, metadata, google_metadata, "
                                "datetime, former_name, parent, timezone, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                           args=(key, original_filename, metadata.replace("'", "''"),
                                 google_metadata.replace("'", "''"), dt.isoformat(), db_name, parent_key, timezone))

        # Update file system
        if db_dir is None:
            tgt_path = os.path.join(self.root_path, self.dt_to_dir(dt))
        else:
            tgt_path = os.path.join(self.root_path, db_dir)

        # Checking consistency between FS and DB
        if (not os.path.exists(os.path.join(tgt_path, db_name)) and main_flags.present)\
                or (os.path.exists(os.path.join(tgt_path, db_name)) and not main_flags.present):
            self.logger.warning(f"Attempting to move file to replaced, "
                                f"Inconsistency between presence noted in DB and presence on file system:"
                                f"db: {main_flags.present}, "
                                f"file_system: {os.path.exists(os.path.join(tgt_path, db_name))}")

        # Take care of three kinds of files.
        if os.path.exists(os.path.join(tgt_path, db_name)):
            self.logger.debug("Moving Original File to Trash")
            main_flags.present = True
            os.rename(os.path.join(tgt_path, db_name), os.path.join(self.get_trash_dir(), db_name))
        else:
            main_flags.present = os.path.exists(os.path.join(self.get_trash_dir(), db_name))

        # Updating the flags again
        self.debug_execute("UPDATE replaced SET flags = ? WHERE key = ?",
                           args=(child_key, ReplacedFlags.from_main_flags(main_flags).to_int()))

        # Remove Thumbnail
        if os.path.exists(os.path.join(self.get_thumb_dir(), self.thumbnail_name(key))):
            self.logger.debug("Deleting Thumbnail")
            os.remove(os.path.join(self.get_thumb_dir(), self.thumbnail_name(key)))

        # Remove Miniature
        if os.path.exists(os.path.join(self.get_thumb_dir(), self.miniature_name(key))):
            self.logger.debug("Deleting Miniature")
            os.remove(os.path.join(self.get_thumb_dir(), self.miniature_name(key)))

        # TODO Darktable???
        self.debug_execute("DELETE FROM main WHERE key = ?", (child_key,))
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
            self.logger.info(f"Changing {len(results)} {tbl} entries to the new parent")

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
            self._internal_add_duplicate(key_a=[a[0] for a in filtered_args],
                                         key_b=[a[1] for a in filtered_args],
                                         known=known)

            self._internal_remove_duplicate(key_a=[r[0] for r in results],
                                            key_b=[r[1] for r in results],
                                            known=known)

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

    def temp_video_path(self) -> str:
        """
        For a video, give a temporary path, where the thumbnail for the video is extracted to.
        """
        return os.path.join(self.config.thumbnail, "video_temp.jeg")

    def get_thumb_dir(self):
        """
        Get folder where to store thumbnails.
        """
        if os.path.isabs(self.config.thumbnail):
            return self.config.thumbnail
        else:
            return os.path.join(self.root_path, self.config.thumbnail)

    def get_trash_dir(self):
        """
        Get folder where to store trash.
        """
        if os.path.isabs(self.config.trash):
            return self.config.trash
        else:
            return os.path.join(self.root_path, self.config.trash)

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