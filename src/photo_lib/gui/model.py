import datetime
import multiprocessing
import os.path
import time
import warnings
from typing import List, Union, Tuple, Dict
import multiprocessing as mp
from multiprocessing.connection import Connection
from dataclasses import dataclass

from photo_lib.metadataagregator import MetadataAggregator
from photo_lib.PhotoDatabase import PhotoDb, DatabaseEntry, ImportTileInfo, MatchTypes, FullImportTableEntry
from photo_lib.custom_enum import SourceTable, GUICommandTypes
from photo_lib.data_objects import *
from photo_lib.metadataagregator import key_lookup_dir


@dataclass
class Block:
    """
    Store information about list where a certain block if images is stored
    """
    start: int
    length: int


@dataclass
class ImportManifest:
    """
    Manifest where every block of images is stored in the import table.
    """
    no_match: Block
    binary_match: Block
    binary_match_replaced: Block
    binary_match_trash: Block
    hash_match_replaced: Block
    hash_match_trash: Block
    not_allowed: Block


class NoDbException(Exception):
    """
    To make handling of returned values easier, we use an exception to indicate that there's not database loaded.
    """
    pass


def prepare_folder_for_import_process(tbl: str, folder_path: str, com: Connection, db_path: str, exiftool_location: str,
                                      recomp_metadata: bool = False, allowed_file_types: set = None):
    """
    Function to be spawned in a separate process. This will import the folder into the database.
    :param exiftool_location: Needed for Metadata Aggregator
    :param tbl: table name to use for import
    :param folder_path: path of folder to import
    :param com: one end of a mulitprocessing.Pipe
    :param db_path: path to database
    :param recomp_metadata: if metadata should be recomputed
    :param allowed_file_types: set of allowed file extensions.
    :return:
    """
    pdb = PhotoDb(root_dir=db_path)
    pdb.verify()
    pdb.mda = MetadataAggregator(exiftool_path=exiftool_location)
    pdb.prepare_import(tbl_name=tbl,
                       folder_path=folder_path,
                       recompute_metadata=recomp_metadata,
                       allowed_file_types=allowed_file_types,
                       com=com
                       )
    pdb.find_matches_for_import_table(table=tbl, com=com)
    pdb.clean_up()


def import_folder_process(tbl: str, com: Connection, db_path: str, exiftool_location: str,
                          mt: List[MatchTypes], keys: List[int] = None, copy_google_fotos_metadata: bool = False):
    """
    Function to be spawned in a separate process. This will import the folder into the database.

    :param copy_google_fotos_metadata: On Binary match copy google fotos metadata to binary match in db
    :param keys: list of keys to import
    :param mt: list of match types to import.
    :param exiftool_location: Needed for Metadata Aggregator
    :param tbl: table name to use for import
    :param com: one end of a mulitprocessing.Pipe
    :param db_path: path to database
    :return:
    """
    pdb = PhotoDb(root_dir=db_path)
    pdb.verify()
    pdb.mda = MetadataAggregator(exiftool_path=exiftool_location)
    pdb.import_folder(table_name=tbl, match_types=mt, com=com, copy_gfmd=copy_google_fotos_metadata)
    if keys is not None:
        pdb.import_selected_keys(keys=keys, tbl_name=tbl, com=com)
    pdb.clean_up()


class Model:
    pdb: Union[PhotoDb, None] = None
    folder_path: Union[str, None] = None

    current_extensions: Union[None, set] = None

    # Compare Layout for deduplication
    files: List[DatabaseEntry]
    current_row: Union[int, None] = None

    search_level: Union[str, None] = None
    resources: str = os.path.join(os.path.dirname(__file__), "resources")

    # Stuff for importing
    import_folder: Union[str, None] = None
    current_import_table_name: Union[str, None] = None
    __tile_infos: List[ImportTileInfo] = None
    __tile_indexes: ImportManifest = None

    handle: Union[None, mp.Process] = None
    gui_com: Union[None, Connection] = None
    abort: Union[bool, None] = None

    # Stuff for general view
    grouping: GroupingCriterion = GroupingCriterion.NONE
    trash: Union[None, bool] = False

    # TODO config
    wait_timeout: int = 10
    exiftool_location = "/usr/bin/Image-ExifTool-12.44/exiftool"

    def get_default_extensions(self):
        """
        Get the default extensions from the database.
        # TODO should be in config!
        :return:
        """

        if self.pdb is None:
            allowed_files = {".jpeg", ".jpg", ".png", ".mov", ".m4v", ".mp4", '.gif', '.3gp', '.dng', '.heic',
                             '.heif', '.webp', '.tif', '.tiff'}
        else:
            allowed_files = self.pdb.allowed_files

        return ", ".join([x.replace(".", "") for x in list(allowed_files)])

    def get_current_extensions_string(self):
        """
        Get the current extensions string. If not set, return default extensions.
        :return:
        """
        if self.current_extensions is not None and len(self.current_extensions) > 0:
            return ", ".join([x.replace(".", "") for x in list(self.current_extensions)])
        return self.get_default_extensions()

    def process_ext(self, extensions: str = None):
        """
        Process the extensions string and set the current extensions.
        :param extensions: string of current extensions.
        :return:
        """

        allowed_ext_set = None
        if extensions is not None:
            if extensions != self.get_default_extensions():
                # Allowed extensions my not contain ", ', ., /
                if "'" in extensions or "\"" in extensions or "/" in extensions or "." in extensions:
                    raise ValueError("Allowed extensions cannot contain \" or ' or / or .")

                allowed_ext_set = set(filter(lambda x: len(x) > 0, ["." + ext.replace(" ", "")
                                                                    for ext in extensions.split(",")]))
        self.current_extensions = allowed_ext_set

    def new_database_from_folder(self, path: str):
        """
        Create New Database.
        """
        if self.db_loaded():
            self.pdb.clean_up()
            self.pdb = None
            self.folder_path = None

        # We create the path if it doesn't exist - just to be sure if qt allows this on different platforms.
        if not os.path.exists(os.path.abspath(path)):
            os.makedirs(path)

        if not os.path.exists(os.path.join(path, ".photos.db")):
            self.pdb = PhotoDb(root_dir=path)
            self.pdb.mda = MetadataAggregator(exiftool_path=self.exiftool_location)
            self.folder_path = path
            self.pdb.create_db()
        else:
            raise ValueError("Target Directory already contains a db")

    def __init__(self, folder_path: str = None):
        if folder_path is not None:
            self.pdb = PhotoDb(root_dir=folder_path)
            self.pdb.verify()

        self.clear_tile_infos()

    def get_current_import_table_name(self, table_name: str = None):
        """
        Get the name of the current import table.

        :param table_name: name of the import table. Can be set to None to use the current table name.

        :return:
        """
        if table_name is not None:
            self.current_import_table_name = table_name
        if self.current_import_table_name is None:
            return

        return self.pdb.import_table_message(tbl_name=self.current_import_table_name)

    def build_tiles_from_table(self, table_name: str = None):
        """
        Given the name of an import table, build the tiles for the images in the table.

        :param table_name: name of the import table. Can be set to None to use the current table name.
        :return:
        """
        if table_name is not None:
            self.current_import_table_name = table_name
        elif self.current_import_table_name is None:
            return

        tiles = self.pdb.tiles_from_import_table(tbl_name=self.current_import_table_name)
        # Concatinate all lists returned from the database
        self.__tile_infos = tiles[MatchTypes.No_Match.name.lower()] + \
                            tiles[MatchTypes.Binary_Match_Images.name.lower()] + \
                            tiles[MatchTypes.Binary_Match_Replaced.name.lower()] + \
                            tiles[MatchTypes.Binary_Match_Trash.name.lower()] + \
                            tiles[MatchTypes.Hash_Match_Replaced.name.lower()] + \
                            tiles[MatchTypes.Hash_Match_Trash.name.lower()] + \
                            tiles["not_allowed"]

        # Determine the indexes of the different blocks
        no_match =              Block(0,
                                      len(tiles[MatchTypes.No_Match.name.lower()]))
        binary_match =          Block(no_match.length,
                                      len(tiles[MatchTypes.Binary_Match_Images.name.lower()]))
        binary_match_replaced = Block(binary_match.start + binary_match.length,
                                      len(tiles[MatchTypes.Binary_Match_Replaced.name.lower()]))
        binary_match_trash =    Block(binary_match_replaced.start + binary_match_replaced.length,
                                      len(tiles[MatchTypes.Binary_Match_Trash.name.lower()]))
        hash_match_replaced =   Block(binary_match_trash.start + binary_match_trash.length,
                                      len(tiles[MatchTypes.Hash_Match_Replaced.name.lower()]))
        hash_match_trash =      Block(hash_match_replaced.start + hash_match_replaced.length,
                                      len(tiles[MatchTypes.Hash_Match_Trash.name.lower()]))
        not_allowed =           Block(hash_match_trash.start + hash_match_trash.length,
                                      len(tiles["not_allowed"]))

        # Store the blocks in the manifest
        self.__tile_indexes = ImportManifest(no_match=no_match,
                                             binary_match=binary_match,
                                             binary_match_replaced=binary_match_replaced,
                                             binary_match_trash=binary_match_trash,
                                             hash_match_replaced=hash_match_replaced,
                                             hash_match_trash=hash_match_trash,
                                             not_allowed=not_allowed)

    @property
    def tile_infos(self):
        """
        Give access to the tile info list.
        :return:
        """
        return self.__tile_infos

    def clear_tile_infos(self):
        """
        Reset the tile infos and indexes.
        :return:
        """
        self.__tile_infos = []
        self.__tile_indexes = ImportManifest(no_match=             Block(start=0, length=0),
                                             binary_match=         Block(start=0, length=0),
                                             binary_match_replaced=Block(start=0, length=0),
                                             binary_match_trash=   Block(start=0, length=0),
                                             hash_match_replaced=  Block(start=0, length=0),
                                             hash_match_trash=     Block(start=0, length=0),
                                             not_allowed=          Block(start=0, length=0))

    def finish_import(self):
        """
        Done with import, reset all state variables that are related to import.
        :return:
        """
        self.current_extensions = None
        self.current_import_table_name = None
        self.import_folder = None
        self.clear_tile_infos()

    def db_loaded(self):
        """
        Checker function to test if the database is loaded or not.
        :return:
        """
        return self.pdb is not None

    def set_folder_path(self, folder_path: Union[str, None]):
        """
        Wrapper function in case more logic is needed in the future.
        :param folder_path: path to the database
        :return:
        """
        if self.db_loaded():
            self.pdb.clean_up()
            self.pdb = None
            self.folder_path = None

        if os.path.exists(os.path.join(folder_path, ".photos.db")):
            self.pdb = PhotoDb(root_dir=folder_path)
            self.pdb.verify()
            self.pdb.mda = MetadataAggregator(exiftool_path=self.exiftool_location)
            self.folder_path = folder_path

    @staticmethod
    def process_metadata(metadict: dict):
        """
        Parse the Metadata dict and convert it into a text string that can be displayed.

        :param metadict: dictionary of metadata, generated by the exiftool

        :return: metadata string, file size string
        """
        keys = metadict.keys()
        key_list = list(keys)
        key_list.sort()
        file_size = ""

        result = f"Number of Attributes: {len(key_list)}\n"

        for key in key_list:
            result += f"{key}: {metadict.get(key)}\n"
            if key == "File:FileSize":
                file_size = f"File Size: {int(metadict.get(key)):,}".replace(",", "'")

        return result, file_size

    def try_rename_image(self, tag: str, dbe: DatabaseEntry, custom_datetime: str = None):
        """
        Perform the renaming logic on the badkend. This will update the database entry, and rename the file.
        :param tag: new tag to be used for datetime
        :param dbe: databse entry
        :param custom_datetime: the custom datetime string, if tag is "custom"
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if tag.strip().lower() == "custom":
            tag = "Custom"
            new_datetime = datetime.datetime.strptime(custom_datetime, "%Y-%m-%d %H.%M.%S")

        else:
            parsing_function = key_lookup_dir.get(tag)

            if parsing_function is None:
                raise ValueError(f"Tag {tag} does not have a matching parsing function.")

            new_datetime, key = parsing_function(dbe.metadata)

        if new_datetime == dbe.datetime:
            print("Equivalent Datetime, exiting")
            return

        # print(new_datetime)

        # Update the Database entry
        dbe.new_name = self.pdb.rename_file(entry=dbe, new_datetime=new_datetime, naming_tag=tag)
        dbe.datetime = new_datetime
        dbe.naming_tag = tag

    def fetch_duplicate_row(self):
        """
        Fetch the current row from the database.
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        success, results, row_id = self.pdb.get_duplicate_entry()
        if success:
            self.files = []
            for entry in results:
                if entry is not None:
                    self.files.append(entry)
            self.current_row = row_id

        return success

    def compare_current_files(self):
        """
        Compare access all available files and determine the areas of similarity.

        - identical_binary: If (all) files are identical on a binary level
        - identical_names: If all files have the same original name
        - identical_datetime: If all files have the same datetime
        - identical_file_size: If all files have the same file size
        - difference: The average difference in file size between all files

        :return: identical_binary, identical_names, identical_datetime, identical_file_size, difference
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if len(self.files) == 0 or self.files is None:
            return None

        # compare the files
        identical_binary = True
        for i in range(1, len(self.files)):
            if self.files[i] is not None and self.files[0] is not None:
                suc, msg = self.pdb.compare_files(self.files[i].key, self.files[0].key)
                if suc is None:
                    print(msg)
                identical_binary = identical_binary and suc

        # compare the filenames
        identical_names = True
        for i in range(1, len(self.files)):
            if self.files[i] is not None and self.files[0] is not None:
                identical_names = identical_names and self.files[i].org_fname.lower() == self.files[0].org_fname.lower()

        identical_datetime = True
        for i in range(1, len(self.files)):
            if self.files[i] is not None and self.files[0] is not None:
                identical_datetime = identical_datetime and self.files[i].datetime == self.files[0].datetime

        identical_file_size = True
        difference = 0
        count = 0
        # All to all comparison of the file size
        for i in range(len(self.files)):
            for j in range(i + 1, len(self.files)):
                if self.files[i] is not None and self.files[j] is not None:
                    identical_file_size = identical_file_size and \
                                          self.files[i].metadata.get("File:FileSize") \
                                          == self.files[j].metadata.get("File:FileSize")
                    difference += (self.files[i].metadata.get("File:FileSize")
                                   - self.files[j].metadata.get("File:FileSize")) ** 2
                    count += 1

        if count > 0:
            print(f"Average Difference {(difference ** 0.5) / count}")
            difference = (difference ** 0.5) / count

        return identical_binary, identical_names, identical_datetime, identical_file_size, difference

    def clear_files(self):
        """
        Clear the files list of the current model.

        => Future proofing...
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        self.files = []
        if self.current_row is not None:
            self.pdb.delete_duplicate_row(self.current_row)
            self.current_row = None

    def remove_file(self, dbe: DatabaseEntry):
        """
        Remove a file from the current selection of present files.

        => Future proofing...
        :return:
        """
        self.files.remove(dbe)

    def mark_duplicates(self, original: DatabaseEntry, duplicates: List[DatabaseEntry]):
        """
        Mark the duplicates as such in the database.

        :param original: The original file
        :param duplicates: The list of duplicates
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        main_key = original.key
        print(f"Keeping: {original.new_name}")

        for marks in duplicates:
            print(f"Marking: {marks.new_name}")
            marks: DatabaseEntry
            self.pdb.mark_duplicate(successor=main_key, duplicate_image_id=marks.key, delete=False)

    def search_duplicates(self) -> Tuple[bool, mp.Pipe]:
        """
        Search for duplicates in the database.

        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if self.search_level == "hash":
            self.pdb.duplicates_from_hash(overwrite=True)
            return True, None

        # Other thing
        # success, pipe = self.pdb.img_ana_dup_search(overwrite=True, level=self.search_level)
        success, pipe = self.pdb.img_ana_dup_search(overwrite=True, level=self.search_level, new=True)

        if not success:
            print(pipe)
            return False, None

        return True, pipe

    # ------------------------------------------------------------------------------------------------------------------
    # Accessor Functions for Import view
    # ------------------------------------------------------------------------------------------------------------------

    def get_import_not_allowed(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.not_allowed.start
        end = self.__tile_indexes.not_allowed.start + self.__tile_indexes.not_allowed.length
        return self.__tile_infos[start:end]

    def get_import_binary_match(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.binary_match.start
        end = self.__tile_indexes.binary_match.start + self.__tile_indexes.binary_match.length
        return self.__tile_infos[start:end]

    def get_import_binary_match_replaced(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.binary_match_replaced.start
        end = self.__tile_indexes.binary_match_replaced.start + self.__tile_indexes.binary_match_replaced.length
        return self.__tile_infos[start:end]

    def get_import_binary_match_trash(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.binary_match_trash.start
        end = self.__tile_indexes.binary_match_trash.start + self.__tile_indexes.binary_match_trash.length
        return self.__tile_infos[start:end]

    def get_import_hash_match_replaced(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.hash_match_replaced.start
        end = self.__tile_indexes.hash_match_replaced.start + self.__tile_indexes.hash_match_replaced.length
        return self.__tile_infos[start:end]

    def get_import_hash_match_trash(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.hash_match_trash.start
        end = self.__tile_indexes.hash_match_trash.start + self.__tile_indexes.hash_match_trash.length
        return self.__tile_infos[start:end]

    def get_import_no_match(self) -> List[ImportTileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        if self.__tile_indexes is None:
            return []

        start = self.__tile_indexes.no_match.start
        end = self.__tile_indexes.no_match.start + self.__tile_indexes.no_match.length
        return self.__tile_infos[start:end]

    # ------------------------------------------------------------------------------------------------------------------
    # Get a full row from the database, path to image, thumbnail
    # ------------------------------------------------------------------------------------------------------------------

    def get_file_import_full_entry(self, key: int) -> FullImportTableEntry:
        """
        Get the full import table entry for the current file.
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if self.current_import_table_name is None:
            raise ValueError("No import table selected")

        return self.pdb.get_full_import_table_entry_from_key(key=key, table=self.current_import_table_name)

    def get_any_match(self, tile: ImportTileInfo) -> Union[None, int]:
        """
        Get the key of the match in the database

        :param tile: for which the match is to be found
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if not tile.allowed:
            return None

        if tile.match_type == MatchTypes.No_Match:
            return None

        # get the match from the database
        return self.pdb.get_match_from_import_table(tile.key, self.current_import_table_name)

    def get_metadata_of_key(self, key: int) -> Union[FullDatabaseEntry, FullReplacedEntry]:
        """
        Get the metadata of a key from the database.
        :param key: key of the image

        :raises NoDbException: if no database is selected
        :raises ValueError: if the key is not in the images or replaced table.

        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        table = self.pdb.get_parent_table_from_key(key)
        if table is SourceTable.Replaced:
            return self.pdb.get_full_duplicates_entry_from_key(key)
        elif table is SourceTable.Images:
            return self.pdb.get_full_images_entry_from_key(key)
        else:
            raise ValueError("Not valid Database Source.")

    def get_any_image_of_key(self, key: int):
        """
        Given the key, returns the path of the image.
        If that doesn't exist, returns the path of the successor
        If that doesn't exist, returns the path of the thumbnail
        :param key:
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        source = self.pdb.get_source_image_path(key)
        # Try to get source image first
        if source is not None:
            return source

        thumbnail = self.pdb.get_thumbnail_path(key)
        if thumbnail is not None:
            return thumbnail

        warnings.warn("Couldn't find image in file system.")
        return None

    def get_full_database_entry(self, key: int) -> Union[FullDatabaseEntry, FullReplacedEntry]:
        """
        Get the full database entry for the target key.

        :param key: file to get full row from
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        tbl = self.pdb.get_parent_table_from_key(key)

        if tbl == SourceTable.Images:
            return self.pdb.get_full_images_entry_from_key(key)
        elif tbl == SourceTable.Replaced:
            return self.pdb.get_full_duplicates_entry_from_key(key)
        else:
            raise ValueError("Not valid Database Source.")

    # ------------------------------------------------------------------------------------------------------------------
    # Everything related to import tables view
    # ------------------------------------------------------------------------------------------------------------------

    def get_import_tables(self) -> List[ImportTableEntry]:
        """
        Get all import tables form the db
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        return self.pdb.list_import_tables()

    def change_import_table_description(self, key: int, description: str):
        """
        Change the description of a file in the database.
        :param key: key of the file
        :param description: new description
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if '"' in description:
            raise ValueError("Description cannot contain \"")
        elif "'" in description:
            raise ValueError("Description cannot contain '")

        self.pdb.change_import_table_desc(key=key, desc=description)

    def delete_import_table(self, tbl_name: str):
        """
        Delete import table
        :param tbl_name: table name to delete
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        self.pdb.remove_import_table(tbl_name=tbl_name)

    def remove_all_import_tables(self):
        """
        Deletes all import tables.
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        self.pdb.purge_import_tables()

    # ------------------------------------------------------------------------------------------------------------------
    # Functions to perform importing and stuff
    # ------------------------------------------------------------------------------------------------------------------

    def new_import(self, folder: str, description: str = None, allowed_ext: str = None):
        """
        Create a new import table in the database.
        :param allowed_ext: allowed extensions
        :param description: table description
        :param folder: folder to import
        :return:
        """
        if self.handle is not None:
            raise ValueError("Process in Progress or Bug")

        if self.pdb is None:
            raise NoDbException("No Database selected")

        if not os.path.exists(folder):
            raise FileExistsError("Folder does not exist")

        self.process_ext(allowed_ext)

        if description == "":
            description = None

        self.gui_com, com_b = multiprocessing.Pipe()

        self.import_folder = folder
        self.current_import_table_name = self.pdb.create_import_table(folder_path=folder, msg=description)

        # Disconnect from db
        self.pdb.clean_up()
        self.pdb = None

        self.handle = mp.Process(target=prepare_folder_for_import_process, args=(self.current_import_table_name,
                                                                                 self.import_folder,
                                                                                 com_b,
                                                                                 self.folder_path,
                                                                                 self.exiftool_location,
                                                                                 False,
                                                                                 self.current_extensions))
        self.handle.start()

    def update_allowed_metadata(self, extensions: str = None, rcmp_mtdt: bool = False):
        """
        Given an already existing import table, change the allowed files and compute their metadata if desired.
        :param extensions: string of extensions
        :param rcmp_mtdt: if metadata is to be recomputed.
        :return:
        """
        if self.handle is not None:
            raise ValueError("Process in Progress or Bug")

        if self.pdb is None:
            raise NoDbException("No Database selected")

        self.process_ext(extensions)

        self.gui_com, com_b = multiprocessing.Pipe()

        # Disconnect from db
        self.pdb.clean_up()
        self.pdb = None

        self.handle = mp.Process(target=prepare_folder_for_import_process, args=(self.current_import_table_name,
                                                                                 self.import_folder,
                                                                                 com_b,
                                                                                 self.folder_path,
                                                                                 self.exiftool_location,
                                                                                 rcmp_mtdt,
                                                                                 self.current_extensions))
        self.handle.start()

    def stop_process(self):
        """
        Sends stop command to the currently long-running process.

        Kills the process if it takes longer than the wait_timeout.
        :return:
        """

        self.abort = True
        self.gui_com.send(GUICommandTypes.QUIT)

        time.sleep(self.wait_timeout)

        if self.handle.is_alive():
            self.handle.kill()

    def recover_long_running_process(self) -> bool:
        """
        Recover after long-running process as in, reconnect db.
        :return: bool if process was aborted or not.
        """
        if not self.handle.is_alive():
            self.handle = None
            self.gui_com = None

        self.pdb = PhotoDb(self.folder_path)
        self.pdb.verify()

        abrt = self.abort
        self.abort = None
        return abrt

    def has_google_fotos_metadata(self, tbl: str = None) -> bool:
        """
        Check if the import table has google fotos metadata.
        :param tbl: table name
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if tbl is None:
            tbl = self.current_import_table_name

        return self.pdb.has_google_fotos_metadata(tbl)

    def import_current_target_folder(self, m: List[MatchTypes], cgfdm: bool = False, l: List[int] = None):
        """
        Import a block of images
        :param l: list of specific keys to import
        :param cgfdm: Copy the google fotos metadata to existing images.
        :param m: List of match types that should be imported
        :return:
        """
        if self.handle is not None:
            raise ValueError("Process in Progress or Bug")

        if self.pdb is None:
            raise NoDbException("No Database selected")

        self.gui_com, com_b = multiprocessing.Pipe()

        # Disconnect from db
        self.pdb.clean_up()
        self.pdb = None

        self.handle = mp.Process(target=import_folder_process, args=(self.current_import_table_name,
                                                                     com_b,
                                                                     self.folder_path,
                                                                     self.exiftool_location,
                                                                     m,
                                                                     l,
                                                                     cgfdm))
        self.handle.start()

    def get_images_carousel(self, start: int, count: int):
        """
        Get the images for the carousel. Fetch a contin
        :param start:
        :param count:
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        tiles = self.pdb.generate_tiles(crit=GroupingCriterion.NONE,
                                        trash=self.trash,
                                        dt=None,
                                        offset=start,
                                        count=count)
        return tiles

    def get_total_image_count(self) -> int:
        """
        Get the image count of all images in the database matching the current trash value
        :return: int
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        return  self.pdb.get_grouped_image_count(GroupingCriterion.NONE, trash=self.trash)[0].count
