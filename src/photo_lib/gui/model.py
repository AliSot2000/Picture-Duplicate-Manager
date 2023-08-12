import datetime
import os.path
from typing import List, Union, Tuple, Dict
import multiprocessing as mp
from dataclasses import dataclass

from photo_lib.PhotoDatabase import PhotoDb, DatabaseEntry, TileInfo, MatchTypes
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


class Model:
    pdb:  Union[PhotoDb, None] = None

    # Compare Layout for deduplication
    files: List[DatabaseEntry]
    current_row: Union[int, None] = None

    search_level: Union[str, None] = None
    resources: str = os.path.join(os.path.dirname(__file__), "resources")

    # Stuff for importing
    import_folder: Union[str, None] = None
    current_import_table_name: Union[str, None] = None
    __tile_infos: List[TileInfo] = None
    __tile_indexes: ImportManifest = None

    def get_default_extensions(self):
        """
        Get the default extensions from the database.
        # TODO should be in config!
        :return:
        """
        if self.pdb is None:
            return ""

        return ", ".join([x.replace(".", "") for x in list(self.pdb.allowed_files)])

    def __init__(self, folder_path: str = None):
        if folder_path is not None:
            self.pdb = PhotoDb(root_dir=folder_path)

        self.__tile_infos = []
        self.__tile_indexes = ImportManifest(no_match=             Block(start=0, length=0),
                                             binary_match=         Block(start=0, length=0),
                                             binary_match_replaced=Block(start=0, length=0),
                                             binary_match_trash=   Block(start=0, length=0),
                                             hash_match_replaced=  Block(start=0, length=0),
                                             hash_match_trash=     Block(start=0, length=0),
                                             not_allowed=          Block(start=0, length=0))

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
        self.__tile_infos = tiles[MatchTypes.No_Match.name.lower()] + \
                            tiles[MatchTypes.Binary_Match_Images.name.lower()] + \
                            tiles[MatchTypes.Binary_Match_Replaced.name.lower()] + \
                            tiles[MatchTypes.Binary_Match_Trash.name.lower()] + \
                            tiles[MatchTypes.Hash_Match_Replaced.name.lower()] + \
                            tiles[MatchTypes.Hash_Match_Trash.name.lower()] + \
                            tiles["not_allowed"]

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

    def set_folder_path(self, folder_path: str):
        """
        Wrapper function in case more logic is needed in the future.
        :param folder_path: path to the database
        :return:
        """
        if os.path.exists(os.path.join(folder_path, ".photos.db")):
            self.pdb = PhotoDb(root_dir=folder_path)

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

    def get_media_infos_import(self, key: int, tbl_name: str = None):
        """
        Get all information related to an image from the import table.
        :param key: key in the table
        :param tbl_name: table name if left empty, current_import_table_name will be used.
        :return:
        """
        pass

    def get_media_info_database(self, key: int):
        """
        Get all information related to the image from the database.
        :return:
        """
        pass

    def get_import_not_allowed(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.not_allowed.start
        end = self.__tile_indexes.not_allowed.start + self.__tile_indexes.not_allowed.length
        return self.__tile_infos[start:end]

    def get_import_binary_match(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.binary_match.start
        end = self.__tile_indexes.binary_match.start + self.__tile_indexes.binary_match.length
        return self.__tile_infos[start:end]

    def get_import_binary_match_replaced(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.binary_match_replaced.start
        end = self.__tile_indexes.binary_match_replaced.start + self.__tile_indexes.binary_match_replaced.length
        return self.__tile_infos[start:end]

    def get_import_binary_match_trash(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.binary_match_trash.start
        end = self.__tile_indexes.binary_match_trash.start + self.__tile_indexes.binary_match_trash.length
        return self.__tile_infos[start:end]

    def get_import_hash_match_replaced(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.hash_match_replaced.start
        end = self.__tile_indexes.hash_match_replaced.start + self.__tile_indexes.hash_match_replaced.length
        return self.__tile_infos[start:end]

    def get_import_hash_match_trash(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.hash_match_trash.start
        end = self.__tile_indexes.hash_match_trash.start + self.__tile_indexes.hash_match_trash.length
        return self.__tile_infos[start:end]

    def get_import_no_match(self) -> List[TileInfo]:
        """
        Wrapper function so the view doesn't have to work with indexes in the list.
        :return:
        """
        start = self.__tile_indexes.no_match.start
        end = self.__tile_indexes.no_match.start + self.__tile_indexes.no_match.length
        return self.__tile_infos[start:end]

