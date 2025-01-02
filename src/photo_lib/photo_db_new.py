from photo_lib.sqlite_wrapper import BaseSQliteDB
from typing import Set, Tuple, Dict, List, Union
from custom_enum import GroupingCriterion
import multiprocessing.connection as connection
import datetime


class PhotoDB(BaseSQliteDB):
    def __init__(self, db_file: str, thumb_dir: str, trash_dir: str):
        super().__init__(db_file)

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

        # Check the tables
        ...

    def _verify_tables(self):
        """
        Go through all tables and check their definitions
        """
        ...

    def update_database_vxxx_vyyy(self):
        """
        Placeholder for updating database from one version to another.
        """
        ...

    # ==================================================================================================================
    # File Integrity checks
    # ==================================================================================================================

    def list_changed_hashes(self):
        """
        Create an import table full of files who's hash has changed.

        Goes through all images in the database and checks the hash of their counterpart.
        """

    def update_hash_from_filename(self, fname: Dict[str, str]):
        """
        Updates the hash of the image file with the given file name.
        """

    def list_changed_filenames(self):
        """
        Match hash and filesize of files against the db. If the two match and the filename is different, these files
        will be added to the new import table.
        """

    def update_filenames(self, new_names: Dict[int, str]):
        """
        Update the names of files resolved through hash and filesize.
        """
        ...

    def list_missing_files(self):
        """
        Go through db and
        """

    def check_thumbnails(self):
        """
        Go through db and check the mark for thumbnail and a thumbnail existing are correct.
        """
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

        :param append: Files were added in the import directory. Add the new files to the table
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

    def perform_import(self, tbl: str, dest_dir: str = None) -> int:
        """
        Imports all files from the given import table into the main database.
        - Files which are imported already will be ignored and
        - All disallowed files will not be imported.

        :param tbl: Name of the table to import from
        :param dest_dir: Destination directory to create in within the database. Defaults to db/yyyy/mm/dd/


        :return: Number of imported files
        """
        ...

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

    def set_known_dup(self, key_a: int, key_b: int):
        """
        Moves a pair of duplicates into the known_dup table.
        """

    # ==================================================================================================================
    # UI
    # ==================================================================================================================

    def change_datetime(self, key: int, new_dt: datetime.datetime):
        """
        Change the datetime associated with the given image. Each image should have a filename string and a given
        datetime
        """
        ...

    def change_filename(self, key: int, new_filename: str):
        """
        Change the filename
        """

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

    def resolve_key_to_path(self, key: int):
        """
        Get the original filename for image
        """
        ...

    def filename_to_key(self, fname: str):
        """
        Resolve a filename to key
        """
        ...
