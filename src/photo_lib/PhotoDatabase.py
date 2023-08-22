import datetime
import filecmp
import os
import sqlite3
import json
import base64
import time
from photo_lib.data_objects import *

import cv2
from .metadataagregator import MetadataAggregator, FileMetaData
import shutil
import warnings
from difPy.dif import dif
from _queue import Empty
import multiprocessing as mp
import multiprocessing.connection as mpconn
from typing import Tuple, List, Set, Union, Dict
import sys
import ffmpeg
from .errors_and_warnings import *
from fast_diff_py import fastDif
from photo_lib.utils import rec_list_all, rec_walker, path_builder


# TODO Tables to add:
#   - Thunbmails Table
#   - Known duplicates table
# TODO Account for cases when a file is modified - keep track of the new hash. So we need an initial hash and file size.
# TODO Add a row for the last_import table.
# INFO: If you run the img_ana_dup_search from another file and not the gui, MAKE SURE TO EMPTY THE PIPE.
# After around 1000 Calls, the pipe will be full and the program will freeze !!!


message_lookup = [
    "No Match found in Database",
    "Found a Binary Match in the Database",
    "Found a Binary Match in the Trash",
    "Found a Hash Match in the Trash",
    "Found a Binary Match in the Replaced Files",
    "Found a Hash Match in the Replaced Files"
]


class PhotoDb:
    root_dir: str
    img_db: str
    thumbnail_dir: str
    trash_dir: str

    # database
    cur: sqlite3.Cursor = None
    con: sqlite3.Connection = None

    # allowed files in database:
    allowed_files: set = {".jpeg", ".jpg", ".png", ".mov", ".m4v", ".mp4", '.gif', '.3gp', '.dng', '.heic', '.heif', '.webp', '.tif', '.tiff'}
    __mda: MetadataAggregator = None

    __datetime_format = "%Y-%m-%d %H.%M.%S"

    proc_handles: list = []

    # ------------------------------------------------------------------------------------------------------------------
    # New Table definitions.
    # ------------------------------------------------------------------------------------------------------------------

    table_command_dict: dict

    images_table_command: str = \
        ("CREATE TABLE images "
         "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
         "org_fname TEXT NOT NULL, "
         "org_fpath TEXT NOT NULL, "
         "metadata TEXT NOT NULL, "
         "google_fotos_metadata TEXT,"
         "naming_tag TEXT, "
         "file_hash TEXT, "
         "new_name TEXT UNIQUE , "
         "datetime TEXT, "
         "present INTEGER DEFAULT 1 CHECK (present in (0, 1) ), "
         "verify INTEGER DEFAULT 0 CHECK (verify in (0, 1)),"
         "trashed INTEGER DEFAULT 0 CHECK (trashed in (0, 1)),"
         "original_google_metadata INTEGER DEFAULT -1 CHECK (original_google_metadata in (0, 1, -1)),"
         "timestamp INTEGER DEFAULT 0)")

    names_table_command: str = \
        "CREATE TABLE names (key INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)"
    # New name doesn't have a FOREIGN KEY because it might be that it is in replaced or in images table

    replaced_table_command: str = \
        ("CREATE TABLE replaced "
         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
         " org_fname TEXT,"
         " metadata TEXT,"
         " google_fotos_metadata TEXT,"
         " file_hash TEXT, "
         " datetime TEXT,"
         " successor INTEGER,"
         " former_name TEXT DEFAULT NULL,"
         " original_google_metadata INTEGER DEFAULT -1 CHECK (original_google_metadata in (0, 1, -1)),"
         " FOREIGN KEY (successor) REFERENCES images(key))")

    import_tables_table_command: str = \
        ("CREATE TABLE import_tables "
         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
         " root_path TEXT NOT NULL, "
         " import_table_name TEXT UNIQUE NOT NULL,"
         "import_table_description TEXT)")

    def __init__(self, root_dir: str, db_path: str = None):
        if os.path.exists(root_dir):
            self.root_dir = root_dir
            self.thumbnail_dir = os.path.join(root_dir, ".thumbnails")
            self.trash_dir = os.path.join(root_dir, ".trash")
        else:
            raise ValueError(f"{root_dir} doesn't exist")

        # verify database path
        if db_path is not None and os.path.exists(db_path):
            self.img_db = db_path
        else:
            # db default path
            self.img_db = os.path.join(self.root_dir, ".photos.db")

        # create directory for trash and thumbnails
        if not os.path.exists(self.thumbnail_dir):
            os.mkdir(self.thumbnail_dir)

        if not os.path.exists(self.trash_dir):
            os.mkdir(self.trash_dir)

        self.table_command_dict = {"images": self.images_table_command,
                                   "names": self.names_table_command,
                                   "replaced": self.replaced_table_command,
                                   "import_tables": self.import_tables_table_command,
                                   }

        self.__connect()

        existence, correctness = self.verify_tables()

        if not existence and not correctness:
            self.create_db()

        if existence and not correctness:
            # raise CorruptDatabase("Database is not correctly formatted and might not work. Check the logs.")
            warnings.warn("Database is not correctly formatted and might not work. Proceed with caution")

    # ------------------------------------------------------------------------------------------------------------------
    # UTILITY CONVERTERS
    # ------------------------------------------------------------------------------------------------------------------

    def __folder_from_datetime(self, dt_obj: datetime.datetime):
        return os.path.join(self.root_dir, f"{dt_obj.year}", f"{dt_obj.month:02}", f"{dt_obj.day:02}")

    def path_from_datetime(self, dt_obj: datetime.datetime, file_name: str):
        return os.path.join(self.__folder_from_datetime(dt_obj), file_name)

    def __datetime_to_db_str(self, dt_obj: datetime.datetime):
        return dt_obj.strftime(self.__datetime_format)

    def __db_str_to_datetime(self, dt_str: str):
        return datetime.datetime.strptime(dt_str, self.__datetime_format)

    def __file_name_generator(self, dt_obj: datetime.datetime, old_fname: str):
        """
        Generates a new file name based on the datetime that is provided. The old fname is used for the extension.
        A given second may have up to 1000 files at the same time.

        :param dt_obj: datetime when the file needs to be inserted
        :param old_fname: old file name used for file extension.

        :return:
        """
        base = dt_obj.strftime(self.__datetime_format)
        extension = os.path.splitext(old_fname)[1].lower()

        for i in range(1000):
            name = f"{base}_{i:03}{extension}"

            self.cur.execute(f"SELECT * FROM names WHERE name = '{name}'")
            if self.cur.fetchone() is None:
                return name

        raise ValueError("No valid name found")

    def __string_to_datetime(self, dt_str: str):
        return datetime.datetime.strptime(dt_str, self.__datetime_format)

    @staticmethod
    def __dict_to_b64(metadata: dict):
        json_string = json.dumps(metadata)
        json_bytes = json_string.encode("utf-8")
        b64_bytes = base64.b64encode(json_bytes)
        b64_string = b64_bytes.decode("ascii")
        return b64_string

    @staticmethod
    def __b64_to_dict(b64_str: str):
        if b64_str is None:
            return None
        b64_bytes = b64_str.encode("ascii")
        json_bytes = base64.b64decode(b64_bytes)
        json_str = json_bytes.decode("utf-8")
        meta_dict = json.loads(json_str)
        return meta_dict

    def thumbnail_name(self, ext: str, key: int):
        thumbnail_name = f"thumb_{key}{ext}"
        return os.path.join(self.thumbnail_dir, thumbnail_name)

    def trash_path(self, file_name: str):
        return os.path.join(self.trash_dir, file_name)

    def duplicate_table_exists(self) -> bool:
        self.debug_exec("SELECT name FROM sqlite_master WHERE type='table' AND name='duplicates'")
        dups = self.cur.fetchone()
        return dups is not None

    def create_duplicates_table(self):
        self.debug_exec("CREATE TABLE duplicates ("
                        "key INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "match_type TEXT,"
                        "matched_keys TEXT)")

    def delete_duplicates_table(self):
        self.debug_exec("DROP TABLE IF EXISTS duplicates")

    def get_duplicate_table_size(self):
        self.debug_exec("SELECT COUNT(key) FROM duplicates")
        return self.cur.fetchone()[0]

    # ------------------------------------------------------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def mda(self):
        return self.__mda

    @mda.setter
    def mda(self, value):
        if not type(value) is MetadataAggregator:
            raise ValueError("MetadataAggregator Object required for mda property")

        self.__mda = value

    def __connect(self):
        self.con = sqlite3.Connection(self.img_db)
        self.cur = self.con.cursor()

    def purge_import_tables(self):
        self.debug_exec("SELECT import_table_name FROM import_tables")
        ttd = self.cur.fetchone()

        while ttd is not None:
            try:
                self.debug_exec(f"DROP TABLE {ttd[0]}")
                print(f"Successfully droped '{ttd[0]}'")
            except sqlite3.OperationalError as e:
                if "no such table:" in str(e):
                    print(f"table '{ttd[0]}' already deleted")

            self.debug_exec(f"DELETE FROM import_Tables WHERE import_table_name = '{ttd[0]}'")

            self.debug_exec("SELECT import_table_name FROM import_tables")
            ttd = self.cur.fetchone()

        self.con.commit()

    def __list_present_tables(self) -> list:
        """
        Get a list of all names of the tables present in the database
        :return:
        """
        self.debug_exec("SELECT name FROM sqlite_master WHERE type ='table'")
        result = self.cur.fetchall()
        tables = [ res[0] for res in result]

        return tables

    def __get_table_definition(self, table: str):
        """
        Fetches the definition of a table from sqlite master.

        :param table: name of the table (must exist, no error checking)

        :return: definition string
        """
        # precondition, table exists already.
        self.debug_exec(f"SELECT sql FROM sqlite_master WHERE tbl_name = '{table}' AND type = 'table'")
        return self.cur.fetchone()[0]

    @staticmethod
    def __column_equality(definition_a: str, definition_b: str):
        col_start_a = definition_a.index("(")
        col_start_b = definition_b.index("(")

        col_str_a = definition_a[col_start_a+1:-1]
        col_str_b = definition_b[col_start_b+1:-1]

        cols_a = col_str_a.split(",")
        cols_b = col_str_b.split(",")

        # sanitise cols
        for i in range(len(cols_a)):
            p = cols_a[i].strip()
            p = p.replace("\n", "")
            cols_a[i] = p

        for i in range(len(cols_b)):
            p = cols_b[i].strip()
            p = p.replace("\n", "")
            cols_b[i] = p

        # go through all columns and remove them from the other dictionary.
        while len(cols_a) > 0 and len(cols_b) > 0:
            target_col_a = cols_a.pop()

            if target_col_a not in cols_b:
                print(f"Failed: {target_col_a}")
                return False

            cols_b.remove(target_col_a)

        if len(cols_b) > 0:
            return False

        return True

    def __verify_table(self, table: str, existing_tables: list) -> Tuple[bool, bool]:
        """
        Verifies existence and correctness of definition of a table.

        **Preconditions:**

        - self.table_command_dict contains table as key


        :param table: name of table to be searched
        :param existing_tables: list of all tables existing in the database
        :return: First bool -> table exists, Second bool -> Table is correctly formatted.
        """

        if table not in existing_tables:
            return False, False

        # table exists but is not correctly formatted
        if not self.__column_equality(self.__get_table_definition(table), self.table_command_dict[table]):
            print(f"Table {table} not correctly formatted:\n"
                  f"is:     {self.__get_table_definition(table)}\n"
                  f"target: {self.table_command_dict[table]}")
            return True, False

        return True, True

    def verify_tables(self) -> Tuple[bool, bool]:
        existing_tables = self.__list_present_tables()
        tables = ("images", "names", "replaced", "import_tables")
        all_correctly_formatted = True
        all_present = True

        for tb in tables:
            exists, correct = self.__verify_table(tb, existing_tables)
            all_correctly_formatted = all_correctly_formatted and correct
            all_present = all_present and exists

        return all_present, all_correctly_formatted

    def create_db(self):
        """
        Create all necessary tables for database.

        :return:
        """
        try:
            self.debug_exec(self.images_table_command)
        except sqlite3.OperationalError as e:
            print("*** You still try to initialize the database. Do not set init arg when instantiating class ***")
            raise e

        self.debug_exec(self.names_table_command)

        self.debug_exec(self.replaced_table_command)

        self.debug_exec(self.import_tables_table_command)

        self.con.commit()

    # ------------------------------------------------------------------------------------------------------------------
    # Main Functions
    # ------------------------------------------------------------------------------------------------------------------

    def rename_file(self, entry: DatabaseEntry, new_datetime: datetime.datetime, naming_tag: str):
        """
        Performs renaming action of renaming a file. This action specifically CHECKS NOT if the file exists in any
        other table. It is assumed that during the step if importing deduplication on hashes is already performed.

        :param entry: DatabaseEntry provided from g ui
        :param new_datetime: the new datetime generated from a tag
        :param naming_tag: the naming tag
        :return:
        """

        new_name = self.__file_name_generator(dt_obj=new_datetime, old_fname=entry.org_fname)
        new_path = self.path_from_datetime(dt_obj=new_datetime, file_name=new_name)

        old_path = self.path_from_datetime(dt_obj=entry.datetime, file_name=entry.new_name)

        # free file name
        self.debug_exec(f"DELETE FROM names WHERE name = '{entry.new_name}'")

        # update images table
        self.debug_exec(f"UPDATE images SET "
                        f"new_name = '{new_name}', "
                        f"naming_tag = '{naming_tag}', "
                        f"datetime = '{self.__datetime_to_db_str(new_datetime)}', "
                        f"timestamp = {str(new_datetime.timestamp()).split('.')[0]}, "
                        f"WHERE key = {entry.key}")

        # update the names table
        self.debug_exec(f"INSERT INTO names (name) VALUES ('{new_name}')")

        print(f"Renaming: {old_path}\nto      : {new_path}")

        folder = self.__folder_from_datetime(new_datetime)
        if not os.path.exists(folder):
            os.makedirs(folder)

        os.rename(src=old_path, dst=new_path)
        self.con.commit()
        return new_name

    def revert_import(self, tbl_name: str):
        """
        In case an import failed, revert the import and remove the images from the database and stuff.

        :param tbl_name: name of the import table

        :return:
        """
        self.debug_exec(f"SELECT key, imported, impoprt_key FROM {tbl_name}")
        rows = self.cur.fetchall()

        for row in rows:
            # imported is 1
            if row[1] == 1:

                assert row[2] is not None, "Imported is 1 but import_key is None"

                self.debug_exec(f"SELECT datetime, new_name FROM images WHERE key = {row[2]}")
                dt_str, new_name = self.cur.fetchone()
                try:
                    os.remove(self.path_from_datetime(self.__db_str_to_datetime(dt_str), new_name))
                except FileNotFoundError:
                    print(f"File {new_name} not found. Skipping.")

                # remove from the images table
                self.debug_exec(f"DELETE FROM images WHERE key = {row[2]}")

            # deleting the row from the import table
            self.debug_exec(f"DELETE FROM {tbl_name} WHERE key = {row[0]}")

        # deleting the import table
        self.debug_exec(f"DELETE FROM import_tables WHERE import_table_name = '{tbl_name}'")

        # dropping the table
        self.debug_exec(f"DROP TABLE {tbl_name}")
        self.con.commit()

    def prepare_import(self, folder_path: str, allowed_file_types: Set[str] = None, tbl_name: str = None,
                       recompute_metadata: bool = False, com: mp.connection.Connection = None):
        """
        Create the import table or update the import table. This will add all files to the table and retrieve all
        metadata on the files.

        :param com: Used for progress communication with the gui
        :param recompute_metadata: if true metadata will be recomputed (necessary if you are reindexing the directory)
        :param folder_path: Path to folder to import
        :param allowed_file_types: Override allowed file types
        :param tbl_name: Name of the import table. If None, a new one will be created.

        :return: temp_table_name
        """
        folder_path = os.path.abspath(folder_path.rstrip("/"))

        # Create table if no table is provided.
        if tbl_name is None:
            tbl_name = self.create_import_table(folder_path=folder_path)

        # index the directory
        # assertion we have enough ram to store the information
        files = rec_list_all(folder_path)

        metadata_needed = self.__insert_or_update_directory(tbl_name=tbl_name, files=files,
                                                            allowed_file_types=allowed_file_types)

        if recompute_metadata:
            metadata_needed = files

        # precondition - the files that need the metadata are already in the table and the table only needs to be
        # updated.

        if com is not None:
            com.send(Progress(type=ProcessComType.MESSAGE, value="Importing Metadata"))
            com.send(Progress(type=ProcessComType.MAX, value=len(metadata_needed)))

        # compute metadata
        for i in range(len(metadata_needed)):
            if i % 100 == 0:
                # TODO logging
                print(f"Computing metadata for file {i} of {len(metadata_needed)}")
            if com is not None:
                # Handle Communication with gui
                if com.poll():
                    msg = com.recv()

                    if msg.type == GUICommandTypes.QUIT:
                        break
                com.send(Progress(type=ProcessComType.CURRENT, value=i))

            file = metadata_needed[i]
            fname = os.path.basename(file)
            fpath = os.path.dirname(file)
            self.debug_exec(f"SELECT allowed, metadata FROM `{tbl_name}` "
                            f"WHERE org_fpath = '{fpath}' AND org_fname = '{fname}'")

            res = self.cur.fetchone()
            assert res is not None, f"File {file} not found in the import table."

            # Not allowed, we continue
            if res[0] == 0:
                continue

            if res[1] is not None and not recompute_metadata:
                continue

            mdo = self.mda.process_file(file)

            query = (
                f"UPDATE `{tbl_name}` SET "
                f"metadata = '{self.__dict_to_b64(mdo.metadata)}',"
            )

            if mdo.google_fotos_metadata is not None:
                query += f"google_fotos_metadata = '{self.__dict_to_b64(mdo.google_fotos_metadata)}',"

            query +=  (
                f"file_hash = '{mdo.file_hash}',"
                f"naming_tag = '{mdo.naming_tag}',"
                f"datetime = '{self.__datetime_to_db_str(mdo.datetime_object)}' "
                f"WHERE org_fpath = '{mdo.org_fpath}' AND org_fname = '{mdo.org_fname}'"
            )

            # update the import table
            self.debug_exec(query)

        self.con.commit()
        return tbl_name

    def __insert_or_update_directory(self, tbl_name: str, files: list, allowed_file_types: Set[str] = None,):
        """
        Insert or update the directory. This will add all files to the table and update the allowed column.

        :param tbl_name: name of the table to perform action in
        :param files: list of file paths to add or update
        :param allowed_file_types: set of files that are allowed needs to be like .ending, and ending needs to be lower
        case.

        :return:
        """
        metadata_needed = []
        count = 0

        if allowed_file_types is None:
            allowed_file_types = self.allowed_files

        for file in files:
            # compute the allowed
            f_allowed = 1 if os.path.splitext(file)[1].lower() in allowed_file_types else 0
            fname = os.path.basename(file)
            fpath = os.path.dirname(file)

            if f_allowed:
                metadata_needed.append(file)

            # if exists, update the table
            self.debug_exec(f"SELECT key FROM `{tbl_name}` WHERE org_fname = '{fname}' AND org_fpath = '{fpath}'")

            result = self.cur.fetchone()
            if result is not None:
                self.debug_exec(f"UPDATE `{tbl_name}` SET allowed = {f_allowed} WHERE key = {result[0]}")

                continue

            # otherwise - perform insert and add to metadata_needed
            self.debug_exec(f"INSERT INTO `{tbl_name}` (org_fname, org_fpath, allowed) "
                            f"VALUES ('{fname}', '{fpath}', {f_allowed})")
            count += 1

        print(f"Added {count} files to the import table.\nTotal Files: {len(files)}")
        return metadata_needed


    def find_matches_for_import_table(self, table: str, com: mp.connection.Connection = None):
        """
        The import is only looked at for files that have not been imported. If a file has been imported, it won't be
        updated since then the match would be the same as the import_key field.

        Determines for all files in a given import table if the files can be imported or if they are existing in some
        capacity. It sets the match_type field of the database and the message

        The most rudimentary check is performed first. Check if a file exists at the same date and
        time and if so, check the files if they are identical (binary).

        If this doesn't produce a match: The import also checks against the hash of the file. That is, if there's a
        file in the database that has the same hash and file size, if will be checked if they are identical (binary).

        If this doesn't produce a match: The import will check if the file is in the trash (by matching the hash stored
        with the trash.). If so, it will be considered a match. It also checks to trash folder if the image still
        exists there and if so, it will be checked if they are identical (binary).

        If this doesn't produce a match: The import will check if the file is in the replaced table (by matching the hash
        stored with the replaced table.). If so, it will be considered a match. It also checks to trash folder if the
        image still exists there and if so, it will be checked if they are identical (binary).

        :param com: Used for progress communication with the gui
        :param table: prepared import table to take for determining the match state.
        :return:
        """
        self.debug_exec(f"UPDATE `{table}` SET match_type = 0, message = '{message_lookup[0]}' WHERE allowed = 1")
        self.debug_exec(f"SELECT key, org_fpath, org_fname, datetime, file_hash, metadata FROM `{table}` WHERE allowed = 1 AND imported = 0")
        targets = self.cur.fetchall()

        if com is not None:
            com.send(Progress(type=ProcessComType.MESSAGE, value="Matching Files with DB"))
            com.send(Progress(type=ProcessComType.MAX, value=len(targets)))

        for i in range(len(targets)):
            if com is not None:
                if com.poll():
                    msg = com.recv()
                    if msg.type == GUICommandTypes.QUIT:
                        break
                com.send(Progress(type=ProcessComType.CURRENT, value=i))

            if i % 100 == 0:
                print(f"Matched: {i} of {len(targets)}")
            row = targets[i]
            key = row[0]
            file_path = os.path.join(row[1], row[2])
            dt_obj = self.__db_str_to_datetime(row[3])
            file_hash = row[4]
            file_size = self.__b64_to_dict(row[5])["File:FileSize"]

            # check if there's a match on datetime and binary check
            m_found, m_key, m_type = self.__date_time_checker(to_import_file_path=file_path, target_datetime=dt_obj)

            # if no match was found, check if there's a match by hash in the images.
            if not m_found:
                m_found, m_key, m_type = self.__check_hash_images(target_file=file_path,
                                                                  target_hash=file_hash,
                                                                  target_file_size=file_size,
                                                                  trash=False)

            # if no match was found, check if there's a match in the trash
            if not m_found:
                m_found, m_key, m_type = self.__check_hash_images(target_file=file_path,
                                                                  target_hash=file_hash,
                                                                  target_file_size=file_size,
                                                                  trash=True)

            # if no match was found, check if there's a match in the replaced table
            if not m_found:
                m_found, m_key, m_type = self.__check_hash_replaced(target_file=file_path,
                                                                    target_hash=file_hash,
                                                                    target_file_size=file_size)

            if m_found:
                self.debug_exec(f"UPDATE `{table}` SET "
                                f"match_type = {m_type.value}, "
                                f"match = {m_key}, "
                                f"message = '{message_lookup[m_type.value]}' "
                                f"WHERE key = {key}")

        self.con.commit()


    def __date_time_checker(self, to_import_file_path: str, target_datetime: datetime.datetime) \
            -> Tuple[bool, Union[None, int], MatchTypes]:
        """
        Go through the files in the images database and check if there's a file with the same datetime and if so,
        check if the files are identical.

        :param to_import_file_path: the file path of the file we want to impoprt
        :param target_datetime: the datetime of the file we want to import

        :return: bool - true <-> there's a match, int / none - the key of the match in the database,match-type
        """
        self.debug_exec(f"SELECT key, new_name FROM images "
                        f"WHERE datetime = '{self.__datetime_to_db_str(target_datetime)}'")

        results = self.cur.fetchall()
        for result in results:
            # check if the files are identical
            # file needs to exist first:
            if os.path.exists(self.path_from_datetime(dt_obj=target_datetime, file_name=result[1])):
                if filecmp.cmp(to_import_file_path,
                               self.path_from_datetime(dt_obj=target_datetime, file_name=result[1]),
                               shallow=False):
                    return True, result[0], MatchTypes.Binary_Match_Images

        return False, None, MatchTypes.No_Match

    def __check_hash_images(self, target_file: str, target_hash: str, target_file_size: int, trash: bool) \
            -> Tuple[bool, Union[None, int], MatchTypes]:
        """
        Check if there's a file in the images table with the same hash and file size.

        :param target_file: the file path of the file we want to import
        :param target_hash: the hash of the file we want to import
        :param target_file_size: the file size of the file we want to import
        :param trash: if true, the trashed images are checked instead of the images table.

        :return: bool - true <-> there's a match, int / none - the key of the match in the database, matchtype
        """
        self.debug_exec(f"SELECT key, metadata, new_name, datetime FROM images "
                        f"WHERE file_hash = '{target_hash}' AND trashed = {1 if trash else 0}")

        results = self.cur.fetchall()
        for result in results:
            metadata = self.__b64_to_dict(result[1])

            # file size needs to match
            if metadata["File:FileSize"] != target_file_size:
                continue

            # check if the file is in the trash and if so,
            if trash:
                match_path = self.trash_path(result[2])
                if not os.path.exists(match_path):
                    return True, result[0], MatchTypes.Hash_Match_Trash

                if filecmp.cmp(target_file, match_path, shallow=False):
                    return True, result[0], MatchTypes.Binary_Match_Trash

                # TODO Logging
                raise ValueError("File with matching hash and file size found but not matching binary.")

            # check if the files are identical
            pm_dt = self.__db_str_to_datetime(result[3])
            if filecmp.cmp(target_file,
                           self.path_from_datetime(dt_obj=pm_dt, file_name=result[2]),
                           shallow=False):
                return True, result[0], MatchTypes.Binary_Match_Images

        return False, None, MatchTypes.No_Match

    def __check_hash_replaced(self, target_file: str, target_hash: str, target_file_size: int) \
            -> Tuple[bool, Union[None, int], MatchTypes]:
        """
        Check if there's a file in the replaced table with the same hash and file size.

        :param target_file: the file path of the file we want to import
        :param target_hash: the hash of the file we want to import
        :param target_file_size: the file size of the file we want to import

        :return: bool - true <-> there's a match, int / none - the key of the match in the database, matchtype
        """
        self.debug_exec(f"SELECT key, metadata, former_name FROM replaced "
                        f"WHERE file_hash = '{target_hash}'")

        results = self.cur.fetchall()
        for result in results:
            metadata = self.__b64_to_dict(result[1])

            # file size needs to match
            if metadata["File:FileSize"] != target_file_size:
                continue

            # We don't have a file in the trash to compare against, so use only the hash and return
            pm_path = self.trash_path(result[2])
            if not os.path.exists(pm_path):
                return True, result[0], MatchTypes.Hash_Match_Replaced

            # check if the files are identical, and return
            if filecmp.cmp(target_file, pm_path, shallow=False):
                return True, result[0], MatchTypes.Binary_Match_Replaced

            # TODO logging
            raise ValueError("File with matching hash and file size found but not matching binary.")

        return False, None, MatchTypes.No_Match

    def import_folder(self, table_name: str, match_types: List[MatchTypes] = None,
                      copy_gfmd: bool = True, com: mp.connection.Connection = None) -> None:
        """
        From a given table, import all files which are marked with a match_type in the match_types list and which have
        not yet been imported.

        :param com: Used for progress communication with the gui
        :param table_name: the name of the table to import from
        :param match_types: the match types to import, given None, assumed is MatchTypes.NO_MATCH
        :param copy_gfmd: if true, the google fotos metadata is copied to the new file if it is a binary match.

        :return:
        """
        msg = GUICommandTypes.NONE

        if match_types is None:
            match_types = [MatchTypes.No_Match]

        self.debug_exec(f"SELECT "
                        f"key, org_fname, org_fpath, metadata, google_fotos_metadata, file_hash, datetime, naming_tag "
                        f"FROM `{table_name}` "
                        f"WHERE allowed = 1 AND imported = 0 "
                        f"AND match_type IN ({','.join([str(x.value) for x in match_types])})")

        # Assume all rows fit in memory
        rows = self.cur.fetchall()

        if com is not None:
            com.send(Progress(type=ProcessComType.MESSAGE, value="Copying Files to DB"))
            com.send(Progress(type=ProcessComType.MAX, value=len(rows)))

        for i in range(len(rows)):
            if com is not None:
                if com.poll():
                    msg = com.recv()
                    if msg == GUICommandTypes.QUIT:
                        break
                com.send(Progress(type=ProcessComType.CURRENT, value=i))
            if i % 100 == 0:
                # TODO logging
                print(i)

            fmd = FileMetaData(
                org_fname=rows[i][1],
                org_fpath=rows[i][2],
                metadata=self.__b64_to_dict(rows[i][3]),
                google_fotos_metadata=self.__b64_to_dict(rows[i][4]),
                file_hash=rows[i][5],
                datetime_object=self.__db_str_to_datetime(rows[i][6]),
                naming_tag=rows[i][7],
                verify=rows[i][7][:4] == "File"
            )

            self.__handle_import(fmd=fmd, table=table_name, update_it_key=rows[i][0])

        self.con.commit()

        if copy_gfmd and msg != GUICommandTypes.QUIT:
            # Get all google fotos metadata from the images table, binary match, binary_match_trash, hash_match_trash
            self.debug_exec(f"SELECT match, google_fotos_metadata FROM `{table_name}` "
                            f"WHERE match_type > 0 AND match_type < 4 AND google_fotos_metadata IS NOT NULL")

            rows = self.cur.fetchall()
            if com is not None:
                com.send(Progress(type=ProcessComType.MESSAGE, value="Updating Google Fotos Metadata in Main Table"))
                com.send(Progress(type=ProcessComType.MAX, value=len(rows)))

            for i in range(len(rows)):
                if com is not None:
                    if com.poll():
                        msg = com.recv()
                        if msg == GUICommandTypes.QUIT:
                            break
                    com.send(Progress(type=ProcessComType.CURRENT, value=i))
                row = rows[i]
                self.debug_exec(f"SELECT google_fotos_metadata, original_google_metadata "
                                f"FROM images WHERE key = {row[0]}")

                res = self.cur.fetchone()
                assert res is not None, f"Inconsistent data, found match in {table_name} but not in images table."

                # There already exists metadata, continuing
                if res[0] is not None or res[1] != -1:
                    continue

                self.debug_exec(f"UPDATE images SET google_fotos_metadata = '{row[1]}', original_google_metadata = 0 "
                                f"WHERE key = {row[0]}")

            # Get all google fotos metadata from the replaced table
            self.debug_exec(f"SELECT match, google_fotos_metadata FROM `{table_name}` "
                            f"WHERE match_type > 3  AND google_fotos_metadata IS NOT NULL")

            rows = self.cur.fetchall()
            if com is not None:
                com.send(Progress(type=ProcessComType.MESSAGE, value="Updating Google Fotos Metadata in Duplicates "
                                                                     "Table"))
                com.send(Progress(type=ProcessComType.MAX, value=len(rows)))

            for i in range(len(rows)):
                if com is not None:
                    if com.poll():
                        msg = com.recv()
                        if msg == GUICommandTypes.QUIT:
                            break
                    com.send(Progress(type=ProcessComType.CURRENT, value=i))
                row = rows[i]
                self.debug_exec(f"SELECT google_fotos_metadata, original_google_metadata "
                                f"FROM replaced WHERE key = {row[0]}")

                res = self.cur.fetchone()
                assert res is not None, f"Inconsistent data, found match in {table_name} but not in replaced table."

                # There already exists metadata, continuing
                if res[0] is not None or res[1] != -1:
                    continue

                self.debug_exec(
                    f"UPDATE replaced SET google_fotos_metadata = '{row[1]}', original_google_metadata = 0 "
                    f"WHERE key = {row[0]}")

        self.con.commit()

        return

    def __handle_import(self, fmd: FileMetaData, table: str, update_it_key: int):
        """
        Handles the import of the file. Moves the file to the database and adds it to the main table.

        :param fmd: metadata object
        :param table: table from which import is occurring
        :param update_it_key: key of the row in the import table to update

        :return:
        """
        # create subdirectory
        if not os.path.exists(self.__folder_from_datetime(fmd.datetime_object)):
            os.makedirs(self.__folder_from_datetime(fmd.datetime_object))

        new_file_name = self.__file_name_generator(fmd.datetime_object, fmd.org_fname)
        new_file_path = self.path_from_datetime(fmd.datetime_object, new_file_name)

        self.debug_exec(f"INSERT INTO names (name) VALUES ('{new_file_name}')")

        # copy file and preserve metadata
        shutil.copy2(src=os.path.join(fmd.org_fpath, fmd.org_fname),
                     dst=new_file_path,
                     follow_symlinks=True)

        if fmd.google_fotos_metadata is None:
            # create entry in images database
            self.debug_exec("INSERT INTO images (org_fname, org_fpath, metadata, naming_tag, "
                            "file_hash, new_name, datetime, present, verify, timestamp) "
                            f"VALUES ('{fmd.org_fname}', '{fmd.org_fpath}',"
                            f"'{self.__dict_to_b64(fmd.metadata)}', '{fmd.naming_tag}', "
                            f"'{fmd.file_hash}', '{new_file_name}',"
                            f"'{self.__datetime_to_db_str(fmd.datetime_object)}',"
                            f"1, {1 if fmd.verify else 0}, {str(fmd.datetime_object.timestamp()).split('.')[0]})")

        else:
            # create entry in images database
            self.debug_exec("INSERT INTO images (org_fname, org_fpath, metadata, naming_tag, "
                            "file_hash, new_name, datetime, present, verify, google_fotos_metadata, timestamp, "
                            "original_google_metadata) "
                            f"VALUES ('{fmd.org_fname}', '{fmd.org_fpath}',"
                            f"'{self.__dict_to_b64(fmd.metadata)}', '{fmd.naming_tag}', "
                            f"'{fmd.file_hash}', '{new_file_name}',"
                            f"'{self.__datetime_to_db_str(fmd.datetime_object)}',"
                            f"1, {1 if fmd.verify else 0},"
                            f"'{self.__dict_to_b64(fmd.google_fotos_metadata)}', "
                            f"'{str(fmd.datetime_object.timestamp()).split('.')[0]}', 1)")

        self.debug_exec(f"SELECT key FROM images WHERE new_name = '{new_file_name}'")
        update_key = self.cur.fetchone()[0]

        # create entry in temporary database
        self.debug_exec(f"UPDATE `{table}` "
                        f"SET import_key = {update_key}, "
                        f"imported = 1 "
                        f"WHERE key == {update_it_key}")

    def import_table_message(self, tbl_name: str) -> Union[None, str]:
        """
        Return the table description of the given import table. If the table does not exist, return None.
        :param tbl_name: table to fetch description from
        :return: None or table description.
        """
        self.debug_exec(f"SELECT import_table_description FROM import_tables WHERE import_table_name = '{tbl_name}'")
        res = self.cur.fetchone()
        if res is None:
            return None

        return res[0]

    def create_import_table(self, folder_path: str, msg: str = None) -> str:
        """
        Creates a temporary table for the import process.

        :param folder_path: path to folder we're importing
        :param msg: message to be stored in the database associated with the folder
        :return: name of the temporary table
        """
        success = False

        if msg is None:
            msg = os.path.basename(folder_path)
            msg = msg.replace("'", "''")
            folder_path = folder_path.replace("'", "''")

        for i in range(100):
            temp_table_name = f"tbl_{str(hash(datetime.datetime.now()))}"

            try:
                self.debug_exec(f"INSERT INTO import_tables (root_path, import_table_name, import_table_description) "
                                f"VALUES ('{folder_path}', '{temp_table_name}', '{msg}')")
                success = True
                break
            except sqlite3.IntegrityError:
                pass

        if not success:
            raise Exception("Couldn't create import table, to many matching names.")

        self.debug_exec(f"CREATE TABLE `{temp_table_name}`"
                        f"(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                        f"org_fname TEXT NOT NULL,"
                        f"org_fpath TEXT NOT NULL,"
                        f"metadata TEXT,"
                        f"google_fotos_metadata TEXT,"
                        f"file_hash TEXT,"
                        f"imported INTEGER DEFAULT 0 CHECK (imported in (0,1)),"
                        f"allowed INTEGER DEFAULT 0 CHECK (allowed in (0,1)),"
                        f"match_type INTEGER DEFAULT 0 CHECK (match_type in (0,1,2,3,4,5)),"
                        f"message TEXT,"
                        f"datetime TEXT,"
                        f"naming_tag TEXT,"
                        f"match INTEGER DEFAULT NULL,"  # the match found in the trash, images or replaced table
                        f"import_key INTEGER DEFAULT NULL,"  # the key may not have foreign key constraint since we 
                        # want to be able to move the image to the replaced 
                        # table
                        f"UNIQUE (org_fpath, org_fname));"
                        )

        self.con.commit()
        return temp_table_name

    def find_not_unique_hash(self):
        """
        Finds all hashes that occur more than once and provides one full image each.
        :return:
        """
        self.debug_exec("SELECT key, file_hash, COUNT(key) FROM images GROUP BY file_hash HAVING COUNT(key) > 1")

        results = self.cur.fetchall()

        duplicates = []

        for row in results:
            duplicates.append({
                "key": row[0],
                "file_hash": row[1],
                "count": row[2]
            })

        return duplicates

    def find_all_identical_hashes(self, hash_str: str, trash: bool = None) -> list:
        """
        Returns a list of all images with identical hash

        :param hash_str: hash to search for
        :param trash: none search both images and trash, true - only trash, false only images

        :return:
        """
        if trash is None:
            self.debug_exec(f"SELECT key FROM images WHERE file_hash = '{hash_str}'")
        elif trash:
            self.debug_exec(f"SELECT key FROM images WHERE file_hash = '{hash_str}' AND trashed = 1")
        else:
            self.debug_exec(f"SELECT key FROM images WHERE file_hash = '{hash_str}' AND trashed = 0")

        results = self.cur.fetchall()

        return [row[0] for row in results]

    def mark_duplicate(self, successor: int, duplicate_image_id: int, delete: bool = False):
        """
        Given two keys of images, the function marks the duplicate_image_id as the duplicate, removing the image from
        the database and marking it as a duplicate, pointing to the successor.

        If desired, the image is also deleted straight away.

        :param successor: sql id of the successor
        :param duplicate_image_id: sql id of the duplicate image
        :param delete: if the image should be deleted or moved to the trash.
        :return:
        """

        # verify original is not a duplicate itself
        self.debug_exec(f"SELECT successor FROM replaced WHERE key is {successor}")
        result = self.cur.fetchone()

        if result is not None:
            raise DuplicateChainingError(f"Original is duplicate itself, successor of original is {result[0]}")

        # get data from the target to be marked as duplicate from the main table
        self.debug_exec(
            f"SELECT key, org_fname, metadata, google_fotos_metadata, file_hash, datetime, new_name, "
            f"original_google_metadata "
            f"FROM images WHERE key is {duplicate_image_id}")
        data = self.cur.fetchall()

        # would violate SQL but just put it in here because I might be stupid
        assert len(data) == 1, "Multiple images matching key!!!"

        # insert duplicate into replaced table
        if data[0][3] is not None:
            self.debug_exec(f"INSERT INTO replaced "
                            f"(key, "
                            f"org_fname, "
                            f"metadata, "
                            f"google_fotos_metadata, "
                            f"file_hash, "
                            f"successor, "
                            f"datetime, "
                            f"former_name, "
                            f"original_google_metadata) VALUES "
                            f"({data[0][0]}, "
                            f"'{data[0][1]}', "
                            f"'{data[0][2]}', "
                            f"'{data[0][3]}', "
                            f"'{data[0][4]}', "
                            f"{successor}, "
                            f"'{data[0][5]}', "
                            f"'{data[0][6]}', "
                            f"'{data[0][7]}')")
        else:
            self.debug_exec(f"INSERT INTO replaced "
                            f"(key, "
                            f"org_fname, "
                            f"metadata, "
                            f"file_hash, "
                            f"successor, "
                            f"datetime, "
                            f"former_name, "
                            f"original_google_metadata) VALUES "
                            f"({data[0][0]}, "
                            f"'{data[0][1]}', "
                            f"'{data[0][2]}', "
                            f"'{data[0][4]}', "
                            f"{successor}, "
                            f"'{data[0][5]}', "
                            f"'{data[0][6]}', "
                            f"'{data[0][7]}')")
        # update children that have the target as successor
        self.debug_exec(f"UPDATE replaced SET successor = {successor} WHERE successor = {data[0][0]}")

        # is removed duplicate from main table because it could result in confusion
        self.debug_exec(f"DELETE FROM images WHERE key = {duplicate_image_id}")

        self.con.commit()

        src = self.path_from_datetime(self.__db_str_to_datetime(data[0][5]), data[0][6])

        if not delete:
            # move file
            dst = self.trash_path(data[0][6])

            if os.path.exists(dst):
                raise ValueError(f"Image exists in trash already? {dst}")

            os.rename(src, dst)
        else:
            os.remove(src)

    def bulk_duplicate_marking(self, processing_list: list):
        for f in processing_list:
            self.mark_duplicate(successor=f["o_image_id"], duplicate_image_id=f["d_image_id"], delete=f["delete"])

    def gui_get_image(self, key: int = None, filename: str = None):
        if key is None and filename is None:
            raise ValueError("Key or Filename must be provided")

        if key is not None:
            self.debug_exec(f"SELECT key, org_fname , org_fpath, metadata, google_fotos_metadata, naming_tag, "
                            f"file_hash, new_name , datetime, present, verify FROM images WHERE key is {key}")

        else:
            self.debug_exec(f"SELECT key, org_fname , org_fpath, metadata, google_fotos_metadata, naming_tag, "
                            f"file_hash, new_name , datetime, present, verify FROM images WHERE new_name = '{filename}'")

        res = self.cur.fetchone()

        if res is not None:
            return DatabaseEntry(
                key=res[0],
                org_fname=res[1],
                org_fpath=res[2],
                metadata=self.__b64_to_dict(res[3]),
                naming_tag=res[5],
                file_hash=res[6],
                new_name=res[7],
                datetime=self.__db_str_to_datetime(res[8]),
                google_fotos_metadata=self.__b64_to_dict(res[4]),
                verify=res[10])

        return None

    def create_vid_thumbnail(self, key: int = None, fname: str = None, max_pixel: int = 512,
                             overwrite: bool = False, inform: bool = False) -> bool:
        # both none
        if key is None and fname is None:
            raise ValueError("Key or fname must be provided")
        elif key is None:
            self.debug_exec(f"SELECT key, new_name, datetime FROM images WHERE new_name IS '{fname}'")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        # key provided -> overrules a secondary fname
        else:
            self.debug_exec(f"SELECT key, new_name, datetime FROM images WHERE key = {key}")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        if len(results) == 0:
            warnings.warn("Couldn't locate image by id or name in images table. Image might exist but not be in table ",
                          NoDatabaseEntry)

        # only on is allowed otherwise the database is broken
        assert len(results) == 1, "more results than allowed, Database configuration is wrong, should be unique or " \
                                  "primary key"

        img_dt = self.__db_str_to_datetime(results[0][2])
        img_key = results[0][0]
        img_fname = results[0][1]

        if os.path.splitext(img_fname)[1] not in {".mov", ".m4v", ".mp4", ".gif"}:
            if inform:
                # TODO Debug
                # print(f"{img_fname} was not of supported type to create thumbnails with ffmpeg lib.")
                pass
            return False

        img_fpath = self.path_from_datetime(img_dt, img_fname)

        # don't create a thumbnail if it already exists.
        if os.path.exists(self.thumbnail_name(ext=".jpeg", key=img_key)) and not overwrite:
            return False

        try:
            probe = ffmpeg.probe(img_fpath)
        except ffmpeg.Error as e:
            print(e.stderr.decode(), file=sys.stderr)
            return False

        time = float(probe['streams'][0]['duration']) // 2

        for i in range(len(probe['streams'])):
            width = probe['streams'][i].get('width')
            if width is not None:
                break
        try:
            (
                ffmpeg
                .input(img_fpath, ss=time)
                .filter('scale', width, -1)
                .output(self.thumbnail_name(ext=".jpeg", key=img_key), vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            print(e.stderr.decode(), file=sys.stderr)
            return False

        return True

    def create_img_thumbnail(self, key: int = None, fname: str = None, max_pixel: int = 512,
                             overwrite: bool = False, inform: bool = False) -> bool:
        # both none
        if key is None and fname is None:
            raise ValueError("Key or fname must be provided")
        elif key is None:
            self.debug_exec(f"SELECT key, new_name, datetime FROM images WHERE new_name IS '{fname}'")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        # key provided -> overrules a secondary fname
        else:
            self.debug_exec(f"SELECT key, new_name, datetime FROM images WHERE key = {key}")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        if len(results) == 0:
            warnings.warn("Couldn't locate image by id or name in images table. Image might exist but not be in table ",
                          NoDatabaseEntry)

        # only on is allowed otherwise the database is broken
        assert len(results) == 1, "more results than allowed, Database configuration is wrong, should be unique or " \
                                  "primary key"

        img_dt = self.__db_str_to_datetime(results[0][2])
        img_key = results[0][0]
        img_fname = results[0][1]

        if os.path.splitext(img_fname)[1] not in {".jpeg", ".jpg", ".png", ".tiff"}:
            if inform:
                # TODO logging debug
                print(f"{img_fname} was not of supported type to create thumbnails with cv2 lib.")
                pass
            return False

        img_fpath = self.path_from_datetime(img_dt, img_fname)

        # don't create a thumbnail if it already exists.
        if os.path.exists(self.thumbnail_name(ext=os.path.splitext(img_fname)[1], key=img_key)) and not overwrite:
            return False

        # load image from disk, 1 means cv::IMREAD_COLOR
        img = cv2.imread(img_fpath, 1)

        # determine which axis is larger
        max_pix = max(img.shape[0], img.shape[1])

        # calculate new size
        if max_pix == img.shape[0]:
            py = max_pixel
            px = max(1, int(max_pixel / max_pix * img.shape[1]))
        else:
            px = max_pixel
            py = max(1, int(max_pixel / max_pix * img.shape[0]))

        # resize image to new size
        img_half = cv2.resize(img, dsize=(px, py))

        # store image
        cv2.imwrite(self.thumbnail_name(ext=".jpeg" , key=img_key), img_half)

        return True

    def media_file_to_trash(self, key: int = None, file_name: str = None, delete: bool = False):
        """
        Moves an image to trash folder or deletes it directly. The image is retained in the database. The file hash is
        kept to prevent future re-imports of the same image again.

        Either key or file_name can be provided. key overrules file_name if both are present.

        :param key: key of the target image
        :param file_name: file name of the target image
        :param delete: if true the image is deleted directly, otherwise it is moved to trash folder

        :return:
        """
        # both none
        if key is None and file_name is None:
            raise ValueError("Key or file name must be provided")
        elif key is None:
            self.debug_exec(
                f"SELECT key, new_name, datetime, trashed, present FROM images WHERE new_name IS '{file_name}'")
            results = self.cur.fetchall()

            assert len(results) <= 1, "more results than allowed, Database configuration is wrong, should be unique or "

        # key provided -> overrules a secondary fname
        else:
            self.debug_exec(
                f"SELECT key, new_name, datetime, trashed, present FROM images WHERE key = {key}")
            results = self.cur.fetchall()

            assert len(results) <= 1, "more results than allowed, Database configuration is wrong, should be unique or "

        # Parse the result of the Database
        key = results[0][0]
        new_name = results[0][1]
        dt_obj = self.__db_str_to_datetime(results[0][2])
        trashed = bool(results[0][3])
        present = bool(results[0][4])

        if trashed and not delete:
            print(f"WARNING: Image {results[0][0]} is already in trash folder")
            return
        # Image is still in db if not delete

        if delete and not present:
            print(f"WARNING: Image {results[0][0]} is already deleted")
            return
        # Image is still in trash if delete



        # make sure thumbnail exists
        if not trashed and present:
            self.create_img_thumbnail(key=key)

        # move file
        if not delete:
            src = self.path_from_datetime(dt_obj, new_name)
            dst = self.trash_path(new_name)

            if os.path.exists(dst):
                raise ValueError("Image exists in trash already?")

            os.rename(src, dst)
        else:
            # Trashed
            if not trashed:
                os.remove(self.path_from_datetime(dt_obj, new_name))
            else:
                try:
                    os.remove(self.trash_path(new_name))
                except FileNotFoundError:
                    print(f"WARNING: File {new_name} not found in trash folder.")

        # update the image table
        self.debug_exec(f"UPDATE images SET trashed = 1, present = {0 if delete else 1} WHERE key = {key}")

        self.con.commit()

    def img_ana_dup_search(self, level: str, procs: int = 16, overwrite: bool = False, new: bool = True, separate_process: bool = True):
        if new:
            return self.img_ana_dup_search_new(level, overwrite, separate_process)
        else:
            return self.img_ana_dup_search_old(level, procs, overwrite)


    def img_ana_dup_search_new(self, level: str, overwrite: bool = False,
                               separate_process: bool = True):
        """
        Perform default difpy search. Level determines the level at which the fotos are compared. The higher the level,
        the longer the comparison. O(n²) The implementation here is my own using parallel searching on global level.
        :param overwrite: Will drop an existing duplicates table if detected
        :param level: possible: all, year, month, day
        :param procs: number of parallel processes
        :param separate_process: if true, the search will be performed in a separate process (bc gui)
        :return:
        """
        if level not in ("all", "year", "month", "day"):
            raise ValueError("Not supported search level")

        if self.duplicate_table_exists():

            # on not overwrite, return already
            if not overwrite:
                return False, "Duplicates Table exist."

            # otherwise drop table
            self.delete_duplicates_table()

        self.create_duplicates_table()

        if level == "all":
            # raise NotImplementedError("This function is not implemented since it requires a rewrite of difpy")
            dirs = [self.root_dir]

        elif level == "year":
            dirs = self.limited_dir_rec_list(path=self.root_dir, nor=0)

        elif level == "month":
            dirs = self.limited_dir_rec_list(path=self.root_dir, nor=1)

        # day
        else:
            dirs = self.limited_dir_rec_list(path=self.root_dir, nor=2)

        # remove thumbnail and trash directory
        while self.thumbnail_dir in dirs:
            dirs.remove(self.thumbnail_dir)

        # remove the trash directory
        while self.trash_dir in dirs:
            dirs.remove(self.trash_dir)

        pipe_out, pipe_in = mp.Pipe()

        if separate_process:
            p = mp.Process(target=self.process_images_fast_difpy, args=(dirs, pipe_in, level))
            p.start()

        else:
            self.process_images_fast_difpy(dirs, pipe_in, level)
            pipe_in.send("DONE")
        return True, pipe_out

    def process_images_fast_difpy(self, folders: list, pipe_in: mpconn.Connection, info: str):
        """
        The eigentliche implementation. Needs to be fixed. I namely need to switch to using the Qt5 gui stuff.

        :param folders: list of folders to search
        :param pipe_in: the pipe to inform the gui about the progress
        :param info: Info in the database what type of search it was
        :return:
        """
        initial_size = len(folders)
        pipe_in.send((0, initial_size))

        for i in range(len(folders)):
            folder = folders[i]

            old_db = os.path.join(folder, "diff.db")
            if os.path.exists(old_db):
                print(f"Removing old db in {folder}")
                os.remove(old_db)

            # perform the difpy stuff
            fdp = fastDif.FastDifPy.init_new(directory_a=folder, default_db=True, progress=True)
            fdp.ignore_names = (".thumbnails", ".trash", ".thumbnailsold", ".temp_thumbnails")
            fdp.index_the_dirs()
            fdp.estimate_disk_usage()
            fdp.first_loop_iteration()
            fdp.second_loop_iteration()

            results, low_quality = fdp.get_duplicates()
            fdp.clean_up()

            print(results)
            print(low_quality)

            # iterate through results
            for val in results.values():
                keys = [self.file_name_to_key(val['filename'])]

                # iterate through duplicates of single result
                for d in val["duplicates"]:
                    keys.append(self.file_name_to_key(os.path.basename(d)))

                self.debug_exec(f"INSERT INTO duplicates (match_type, matched_keys) "
                                f"VALUES ('{info}', '{json.dumps(keys)}')")
            self.con.commit()
            pipe_in.send((i, initial_size))

        pipe_in.send("DONE")
        pipe_in.close()
        print("Done")


    def img_ana_dup_search_old(self, level: str, procs: int = 16, overwrite: bool = False):
        """
        Perform default difpy search. Level determines the level at which the fotos are compared. The higher the level,
        the longer the comparison. O(n²)
        :param overwrite: Will drop an existing duplicates table if detected
        :param level: possible: all, year, month, day
        :param procs: number of parallel processes
        :return:
        """

        if level not in ("all", "year", "month", "day"):
            raise ValueError("Not supported search level")

        if self.duplicate_table_exists():

            # on not overwrite, return already
            if not overwrite:
                return False, "Duplicates Table exist."

            # otherwise drop table
            self.delete_duplicates_table()

        self.create_duplicates_table()

        if level == "all":
            raise NotImplementedError("This function is not implemented since it requires a rewrite of difpy")

        elif level == "year":
            dirs = self.limited_dir_rec_list(path=self.root_dir, nor=0)

        elif level == "month":
            dirs = self.limited_dir_rec_list(path=self.root_dir, nor=1)

        # day
        else:
            dirs = self.limited_dir_rec_list(path=self.root_dir, nor=2)

        # remove thumbnail and trash directory
        while self.thumbnail_dir in dirs:
            dirs.remove(self.thumbnail_dir)

        while self.trash_dir in dirs:
            dirs.remove(self.thumbnail_dir)

        task_queue = mp.Queue()
        [task_queue.put(directory) for directory in dirs]
        result_queue = mp.Queue()
        init_size = len(dirs)

        def difpy_process(task: mp.Queue, results: mp.Queue, id: int):
            timeout = 10
            while timeout > 0:
                try:
                    task_dir = task.get(block=False)
                    print(f"{id:02}: processing {task_dir}")
                    timeout = 10
                except Empty:
                    timeout -= 1
                    time.sleep(1)
                    continue

                duplicates = dif(task_dir, show_progress=False, show_output=False)
                results.put(duplicates.result)

            print("Difpy Exiting")

        self.proc_handles = []

        for i in range(procs):
            p = mp.Process(target=difpy_process, args=(task_queue, result_queue, i))
            p.start()
            self.proc_handles.append(p)

        pipe_out, pipe_in = mp.Pipe()

        p = mp.Process(target=self.result_processor, args=(init_size, result_queue, pipe_in, level))
        p.start()
        self.proc_handles.append(p)
        return True, pipe_out

    def file_name_to_key(self, file_name: str):
        self.debug_exec(f"SELECT key FROM images WHERE new_name = '{file_name}'")
        res = self.cur.fetchall()

        # if len(res) > 1:
        #     print("\n\n\n\n\n\n\n")
        #     print(res)
        #
        # if len(res) == 0:
        #     print("\n\n\n\n\n\n\n")
        #     print(f"File name is: {file_name}")
        assert len(res) <= 1, "multiple matching files found error in database, since not allowed by filesystem"

        if len(res) == 0:
            print("Image in folder structure that is not recorded in the database. This should not happen.")
            print(f"File name is: {file_name}")
            return -1

        return res[0][0]

    def result_processor(self, initial_size: int, result: mp.Queue, pipe_in: mpconn.Connection, info: str):
        count = 0
        pipe_in.send((0, initial_size))

        while count != initial_size:
            results: dict = result.get()
            count += 1

            # iterate through results
            for val in results.values():
                keys = [self.file_name_to_key(val['filename'])]

                # iterate through duplicates of single result
                for d in val["duplicates"]:
                    keys.append(self.file_name_to_key(os.path.basename(d)))

                self.debug_exec(f"INSERT INTO duplicates (match_type, matched_keys) "
                                f"VALUES ('{info}', '{json.dumps(keys)}')")
            self.con.commit()
            pipe_in.send((count, initial_size))

        pipe_in.send("DONE")
        pipe_in.close()
        print("Results processor done")

    def duplicates_from_hash(self, overwrite: bool = False, trash: bool = False) -> tuple:
        """
        Populates the duplicates table based on duplicates detected by identical hash

        :param overwrite: do not ask if existing duplicate computations should be preserved.
        :param trash: if None, all duplicates are considered. If True, only duplicates in trash are considered.
            If False, only the ones not in trash default False

        :return:
        """
        msg = ""
        if self.duplicate_table_exists():

            # on not overwrite, return already
            if not overwrite:
                return False, "Duplicates Table exist."

            # otherwise drop table
            self.delete_duplicates_table()
            msg = "Dropped table; "

        self.create_duplicates_table()

        duplicates = self.find_not_unique_hash()

        for i in range(len(duplicates)):
            if i % 100 == 0:
                print(f"Processing {i} of {len(duplicates)}")

            d = duplicates[i]
            matching_keys = self.find_all_identical_hashes(d["file_hash"], trash=trash)

            self.debug_exec(f"INSERT INTO duplicates (match_type, matched_keys) "
                            f"VALUES ('hash', '{json.dumps(matching_keys)}')")

        print(f"Done Processing")

        self.con.commit()
        return True, msg + f"Successfully found {len(duplicates)} duplicates"

    def delete_duplicate_row(self, key: int):
        self.debug_exec(f"DELETE FROM duplicates WHERE key = {key}")
        self.con.commit()

    def get_duplicate_entry(self):
        """
        Returns one entry from the duplicates table
        :return:
        """
        try:
            self.debug_exec("SELECT matched_keys, key FROM duplicates")
        except sqlite3.OperationalError:
            print("No Duplicates Table found.")
            return False, [], None
        key_str = self.cur.fetchone()

        if key_str is None:
            return False, [], None

        row_id = key_str[1]
        key_str = key_str[0]
        keys = json.loads(key_str)
        img_attribs = []

        for k in keys:
            img_attribs.append(self.gui_get_image(key=k))

        return True, img_attribs, row_id

    def limited_dir_rec_list(self, path: str, nor: int, results: list = None) -> Union[None, list]:
        """
        Lists all leafs of the folder tree at a certain level. Level is indicated with nor. A list can be provided for
        the results as an argument, then the function returns None or if it is left empty, a list is returned.

        ----------------------------------------------------------------------------------------------------------------

        if you have:

        foo/
            bar/
                ...
            baz/
                ...

        lar/
            ung/
                ...
            tug/
                ...

        the result will be with two recursions:
        [foo/bar, foo/baz, lar/ung, lar/tug]

        :param path: root of the partial folder tree
        :param nor: number of levels of the tree
        :param results: List where the paths are stored in. If not given, func will return list instead.
        :return: None (results given), list (results was None)
        """
        # Initialise function such that it has a
        if results is None:
            result_list = []
            self.limited_dir_rec_list(path=path, nor=nor, results=result_list)
            return result_list
        else:
            content = os.listdir(path)

            for c in content:

                # ignore none dirs
                if not os.path.isdir(os.path.join(path, c)):
                    continue

                # zero, add to list
                if nor == 0:
                    results.append(os.path.join(path, c))
                    continue

                # not zero, continue in subdirectories.
                self.limited_dir_rec_list(path=os.path.join(path, c), nor=nor - 1, results=results)

            return None

    def thumbnail_creation(self):
        index = 0
        self.debug_exec(f"SELECT key FROM images WHERE key >= {index}")
        result = self.cur.fetchone()

        count = 0
        last = 1

        while result is not None:
            # increment index
            index += 1

            if self.create_img_thumbnail(key=result[0]):
                count += 1
            elif self.create_vid_thumbnail(key=result[0]):
                count += 1

            # fetch next new_name
            self.debug_exec(f"SELECT key FROM images WHERE key >= {index}")
            result = self.cur.fetchone()

            if count > last and count % 100 == 0:
                last = count
                print(f"Created {count} thumbnails")

        self.con.commit()
        print(f"Created {count} thumbnails for {index} entries")

    # TODO what happens if one file is not in images table but in trash or sth.
    def compare_files(self, a_key: int, b_key: int) -> Tuple[Union[bool, None], str]:
        """
        Given two keys, performs binary comparison of the two files.
        :param a_key: key of file first in table
        :param b_key: key of file second in table
        :return: Tuple[success, message]
        success: True False -> binary comparison result, None, failed to find keys
        message: Message on what went wrong or result of comparison
        """
        # Locate Entry a
        self.debug_exec(f"SELECT new_name, datetime FROM images WHERE key = {a_key}")
        res_a = self.cur.fetchall()

        if len(res_a) == 0:
            return None, "Failed to find key_a in images"

        if len(res_a) > 1:
            raise CorruptDatabase("Multiple entries with identical key")

        # Locate Entry b
        self.debug_exec(f"SELECT new_name, datetime FROM images WHERE key = {b_key}")
        res_b = self.cur.fetchall()

        if len(res_a) == 0:
            return None, "Failed to find key_b in images"

        if len(res_a) > 1:
            raise CorruptDatabase("Multiple entries with identical key")

        path_a = self.path_from_datetime(self.__db_str_to_datetime(res_a[0][1]), res_a[0][0])
        path_b = self.path_from_datetime(self.__db_str_to_datetime(res_b[0][1]), res_b[0][0])

        try:
            success = filecmp.cmp(path_a, path_b, shallow=False)
        except FileNotFoundError:
            return False, "File not found on disk"

        msg = f"'{res_a[0][0]}' is{'' if success else ' FUCKING NOT'} identical to '{res_b[0][0]}'"

        return success, msg

    def rename_from_google_fotos_meta_data(self):
        """
        Go through all images which have their naming tag be something with file.
        If that's the case check if there's google foto metadata and rename with that if it is earlier than the
        file data.
        :return:
        """
        self.debug_exec("SELECT key FROM images WHERE google_fotos_metadata Is NOT NULL AND naming_tag LIKE 'File%'")
        keys = self.cur.fetchall()
        keys_only = [x[0] for x in keys]

        dts = {}

        gfdt = self.__db_str_to_datetime("2009-01-03 12.52.06")
        count = 0
        renams = 0

        for key in keys_only:

            dbe = self.gui_get_image(key=key)
            gf_md = dbe.google_fotos_metadata

            creation_time = None
            photo_taken_time = None
            photo_last_modified_time = None

            if gf_md.get("creationTime") is not None:
                creation_time = gf_md.get("creationTime").get("timestamp")

            if gf_md.get("photoTakenTime") is not None:
                photo_taken_time = gf_md.get("photoTakenTime").get("timestamp")

            if gf_md.get("photoLastModifiedTime") is not None:
                photo_last_modified_time = gf_md.get("photoLastModifiedTime").get("timestamp")

            # loading the timestamps
            if creation_time is not None:
                dts["creationTime"] = datetime.datetime.fromtimestamp(int(creation_time))

            if photo_taken_time is not None:
                if datetime.datetime.fromtimestamp(int(photo_taken_time))!= gfdt:
                    dts["photoTakenTime"] = datetime.datetime.fromtimestamp(int(photo_taken_time))
                else:
                    count += 1

            if photo_last_modified_time is not None:
                dts["photoLastModifiedTime"] = datetime.datetime.fromtimestamp(int(photo_last_modified_time))

            vals = list(dts.values())
            try:
                lowest = min(vals)
            except ValueError:
                assert len(vals) == 0
                continue

            key = None
            for k in dts.keys():
                if dts[k] == lowest:
                    key = k
                    break

            assert key is not None, "You are stupid how could the key be None ?!?!?!"

            if lowest < dbe.datetime:
                self.rename_file(entry=dbe, new_datetime=lowest,naming_tag=f"GoogleFotos:{key}")
                print(f"File for Renaming: {dbe.new_name}, current_dt: {self.__datetime_to_db_str(dbe.datetime)}, new_dt: {self.__datetime_to_db_str(lowest)}" )
                renams += 1
            if lowest == dbe.datetime:
                print(f"File Eqivalent DT: {dbe.new_name}, current_dt: {self.__datetime_to_db_str(dbe.datetime)}")
            else:
                print(f"File for google older: {dbe.new_name}, current_dt: {self.__datetime_to_db_str(dbe.datetime)}, new_dt: {self.__datetime_to_db_str(lowest)}")

            # creationTime
            # photoTakenTime
            # photoLastModifiedTime
        print(count)
        print(renams)
        self.con.commit()

    # Error Fixing functions.

    def fix_duplicate_chaining(self):
        """
        Moved images to duplicates without checking if they are the parent for duplicates. This fixes that.

        :return:
        """
        self.debug_exec("SELECT successor FROM replaced LEFT JOIN  images ON images.key = replaced.successor WHERE images.key IS NULL;")
        rows = self.cur.fetchall()
        clean_rows = [x[0] for x in rows]

        for key in clean_rows:
            # verify the key is indeed in the replaced table
            self.debug_exec(f"SELECT key, successor FROM replaced WHERE key = {key};")
            matches = self.cur.fetchall()

            assert len(matches) == 1, f"Key {key} is not in replaced table or is in there multiple times"

            # self.debug_exec(f"UPDATE replaced SET successor = {matches[0][1]} WHERE successor = {key}" )
            print(f"UPDATE replaced SET successor = {matches[0][1]} WHERE successor = {key}" )

        self.con.commit()

    def index_files(self):
        """
        Go through database and check that all files have a key associated with them. Prints all files that are not in
        database. (Needed because of bug in Program and not deleted images)

        :return:
        """
        subdirs = os.listdir(self.root_dir)
        not_to_index = (".thumbnails", ".trash", ".thumbnailsold", ".temp_thumbnails", "backup.photos.db", "backup2(before orignal_google_metadata).photos.db", ".photos.db")
        files = []
        errors = []

        for n in not_to_index:
            try:
                subdirs.remove(n)
            except ValueError:
                pass

        for subdir in subdirs:
            path = os.path.join(self.root_dir, subdir)
            files.extend(rec_list_all(path))

        for file in files:
            if self.file_name_to_key(os.path.basename(file)) == -1:
                errors.append(file)

        print(errors)

    def dict_indexer(self):
        """
        Get all possible keys of the metadata dict n stuff
        :return:
        """
        data_type = {}
        data_sample = {}

        path_type = {}
        path_sample = {}

        # get all data from database with google photos metadata
        self.debug_exec("SELECT google_fotos_metadata FROM images WHERE google_fotos_metadata Is NOT NULL;")
        md = self.cur.fetchall()

        for x in md:
            json_dict = self.__b64_to_dict(x[0])
            rec_walker(json_dict, data_sample, data_type)
            path_builder(target=json_dict, path="", path_val=path_sample, path_type=path_type)

        print(data_type)
        print(data_sample)

        for key in path_type:
            print(f"{key}: {path_sample[key]}, type: {path_type[key]}")

        print(path_type)
        print(path_sample)

    def fill_names(self):
        index = 0
        self.debug_exec(f"SELECT new_name FROM images WHERE key >= {index}")
        result = self.cur.fetchone()

        count = 0

        while result is not None:
            # increment index
            index += 1

            # check if name is already present
            self.debug_exec(f"SELECT name FROM names WHERE name = '{result[0]}'")
            found = self.cur.fetchone()

            # if not, insert into db
            if found is None:
                self.debug_exec(f"INSERT INTO names (name) VALUES ('{result[0]}')")
                count += 1

            # fetch next new_name
            self.debug_exec(f"SELECT new_name FROM images WHERE key >= {index}")
            result = self.cur.fetchone()

        self.con.commit()
        print(f"Added {count} non-tracked names to names table of {index} entries")

    def debug_exec(self, command: str):
        """
        Execute a Command with sql cursor, in case of error print command string and raise error
        :param command:
        :return:
        """
        try:
            self.cur.execute(command)
        except Exception:
            print("Error in command")
            print(command)
            raise Exception

    # ------------------------------------------------------------------------------------------------------------------
    # FUNCTIONS TO BUILD TILE INFORMATION FOR IMPORT VIEW
    # ------------------------------------------------------------------------------------------------------------------

    def tiles_from_import_table(self, tbl_name: str) -> Dict[str, List[TileInfo]]:
        """
        Build TileInformation from import table. Assumption RAM is large enough to hold all tiles. Converts entire table
        to tile information.

        :param tbl_name: table to convert
        :return: TileInfos
        """
        output = {}
        t = self.tiles_from_not_allowed(tbl_name=tbl_name)
        output["not_allowed"] = t

        for mt in MatchTypes:
            t = self.tiles_from_match_type(tbl_name=tbl_name, mt=mt)
            output[mt.name.lower()] = t

        return output

    def tiles_from_match_type(self, tbl_name: str, mt: MatchTypes) -> List[TileInfo]:
        """
        Given a Match_Type, fetches all images from the import table which are allowed and have said match type.

        :param tbl_name: import table name
        :param mt: match type to filer for
        :return:
        """

        self.debug_exec(f"SELECT key, org_fname, org_fpath, imported, allowed, match_type FROM `{tbl_name}` "
                        f"WHERE match_type = {mt.value} and allowed = 1")
        return self.__tiles_from_cursor()

    def tiles_from_not_allowed(self, tbl_name) -> List[TileInfo]:
        """
        Get all images from import table which are not allowed.

        :param tbl_name: import table name
        :return:
        """
        self.debug_exec(f"SELECT key, org_fname, org_fpath, imported, allowed, match_type FROM `{tbl_name}` "
                        f"WHERE allowed = 0")
        return self.__tiles_from_cursor()


    def __tiles_from_cursor(self) -> List[TileInfo]:
        """
        Function builds tiles from the current result in the cursor. This function must be called by
        tiles_from_not_allowed or tiles_from_match_type.

        :return:
        """
        results = self.cur.fetchall()
        output = []

        for row in results:
            t = TileInfo(
                key=row[0],
                path=os.path.join(row[2], row[1]),
                imported=bool(row[3]),
                allowed=bool(row[4]),
                match_type=MatchTypes(row[5])
            )
            output.append(t)
        return output

    def get_full_import_table_entry_from_key(self, key: int, table: str) -> FullImportTableEntry:
        """
        Given an import table and a key, returns the full entry from the table.
        :param key: key in the import table
        :param table: table to select from
        :return:
        """
        self.debug_exec(f"SELECT key, org_fname, org_fpath, metadata, google_fotos_metadata, file_hash, imported, "
                        f"allowed, match_type, message, datetime, naming_tag, `match`, import_key "
                        f"FROM `{table}` WHERE key = {key}")

        result = self.cur.fetchone()
        return FullImportTableEntry(
            key=result[0],
            org_fname=result[1],
            org_fpath=result[2],
            metadata=self.__b64_to_dict(result[3]),
            google_fotos_metadata=self.__b64_to_dict(result[4]),
            file_hash=result[5],
            imported=bool(result[6]),
            allowed=bool(result[7]),
            match_type=MatchTypes(result[8]),
            message=result[9],
            datetime=self.__db_str_to_datetime(result[10]) if result[10] is not None else None ,
            naming_tag=result[11],
            match=result[12],
            import_key=result[13]
        )

    def get_full_images_entry_from_key(self, key: int) -> Union[FullDatabaseEntry, None]:
        """
        Given a key, returns the full entry from the images table in a FullDatabaseEntry Object. If the key's not found
        returns None.
        :param key: key in the images table
        :return: None or Row
        """
        self.debug_exec(f"SELECT key, org_fname, org_fpath, metadata, google_fotos_metadata, naming_tag, file_hash, "
                        f"new_name, datetime, present, verify, trashed, original_google_metadata "
                        f"FROM images WHERE key = {key}")

        result = self.cur.fetchone()
        if result is None:
            return None

        return FullDatabaseEntry(
            key=result[0],
            org_fname=result[1],
            org_fpath=result[2],
            metadata=self.__b64_to_dict(result[3]),
            google_fotos_metadata=self.__b64_to_dict(result[4]),
            naming_tag=result[5],
            file_hash=result[6],
            new_name=result[7],
            datetime=self.__db_str_to_datetime(result[8]),
            present=bool(result[9]),
            verify=bool(result[10]),
            trashed=bool(result[11]),
            original_google_metadata=GoogleFotosMetadataStatus(result[12])
        )

    def get_full_duplicates_entry_from_key(self, key: int) -> Union[None, FullReplacedEntry]:
        """
        Given a key, returns the full entry from the duplicates table in a FullDatabaseEntry Object. If the key's not
        found returns None.
        :param key: key to get row from
        :return: Row or None
        """

        self.debug_exec(f"SELECT key, org_fname, metadata, google_fotos_metadata, file_hash, datetime, successor, "
                        f"former_name, original_google_metadata FROM replaced WHERE key = {key}")

        result = self.cur.fetchone()
        if result is None:
            return None

        return FullReplacedEntry(
            key=result[0],
            org_fname=result[1],
            metadata=self.__b64_to_dict(result[2]),
            google_fotos_metadata=self.__b64_to_dict(result[3]),
            file_hash=result[4],
            datetime=self.__db_str_to_datetime(result[5]),
            successor=result[6],
            former_name=result[7],
            original_google_metadata=GoogleFotosMetadataStatus(result[8])
        )

    def get_parent_table_from_key(self, key: int) -> SourceTable:
        """
        Given a key check if it is in the replaced table or in the images table

        :param key: key to check, needs to exist.
        :return: SourceTable Enum

        :raise: ValueError, when key not found.
        """
        self.debug_exec(f"SELECT key FROM replaced WHERE key = {key}")
        res_a = self.cur.fetchone()

        self.debug_exec(f"SELECT key FROM images WHERE key = {key}")
        res_b = self.cur.fetchone()

        if res_a is not None and res_b is None:
            return SourceTable.Replaced

        elif res_a is None and res_b is not None:
            return SourceTable.Images

        elif res_a is not None and res_b is not None:
            raise CorruptDatabase("Key in both tables")

        else:
            raise ValueError("Key not found in database")


    def get_source_image_path(self, key: int) -> Union[str, None]:
        """
        Get the path to the images in the original resolution. For Images in the replaced table, check the trash folder
        otherwise, get the successor of that image.
        
        :param key: key of image -> in Database (Replaced or Images)
        :return: path to image. Guaranteed to exist. otherwise None
        """
        self.debug_exec(f"SELECT key, former_name, successor FROM replaced WHERE key = {key}")
        result = self.cur.fetchone()
        
        # Found a result in the replaced table
        if result is not None:
            # File still exists in trash
            path = os.path.join(self.trash_dir, result[1])
            if os.path.exists(path):
                return path
            else:
                # replace the key with the successor
                key = result[2]

        
        self.debug_exec(f"SELECT key, new_name, datetime, trashed, present FROM images WHERE key = {key}")
        result = self.cur.fetchone()

        # No entry found
        if result is None:
            warnings.warn("Key not found in database")
            return None

        dt = self.__db_str_to_datetime(result[2])

        # trashed and present, check the trash.
        if result[3] and result[4]:
            path = os.path.join(self.trash_dir, result[1])
            if os.path.exists(path):
                return path
            else:
                warnings.warn("File removed from trash without updating database")
                return None

        # trashed and not present
        if result[3] and not result[4]:
            # Once definitely trashed files should not return.
            assert not os.path.exists(os.path.join(self.trash_dir, result[1])), \
                "File trashed, marked as deleted but still present."
            return None

        # not trashed and not present
        assert not result[3], "Bug, now should only be not trashed"

        if not result[4]:
            warnings.warn("File not present but not trashed. This should not happen.")
            return None

        # default location.
        path = self.path_from_datetime(dt, result[1])
        if not os.path.exists(path):
            warnings.warn("File not present but not marked in database.")
            return None

        return path

    def get_thumbnail_path(self, key: int):
        """
        Get the thumbnail path of the image. For images in the replaced table, the thumbnail from the successor is
        considered as well.

        :param key: key to get the thumbnail from
        :return: path to thumbnail - exists, otherwise None.
        """

        thumbnail_path = self.thumbnail_name(ext=".jpeg", key=key)

        # Path exists, return it
        if os.path.exists(thumbnail_path):
            return thumbnail_path

        # test successor
        self.debug_exec(f"SELECT successor FROM replaced WHERE key = {key}")
        result = self.cur.fetchone()

        # No successor, return None
        if result is None:
            return None

        # test thumbnail of successor
        thumbnail_path = self.thumbnail_name(ext=".jpeg", key=result[0])
        if os.path.exists(thumbnail_path):
            return thumbnail_path

        # No path found
        return None

    def get_match_from_import_table(self, import_key: int, tbl_name: str) -> int:
        """
        Given a key and an import table name, get the match key from the database.

        :param import_key: key from which we are interested in the match type
        :param tbl_name: import table to select from
        :return: key in database
        :raises: ValueError if the key not found or the match is Null
        """

        self.debug_exec(f"SELECT match FROM `{tbl_name}` WHERE key = {import_key}")
        res = self.cur.fetchone()

        if res is None:
            raise ValueError(f"Key: {import_key} not found in import table {tbl_name}")

        if res[0] is None:
            raise ValueError(f"Match of key {import_key} is None")

        return res[0]

    def number_of_known_duplicates(self, key: int):
        """
        Given a key in the images table, may be trashed or not. Return the number of known duplicates.

        :param key: to get the number of duplicates from
        :return: number of duplicates found
        """

        self.debug_exec(f"SELECT COUNT(key) FROM replaced WHERE successor = {key}")
        res = self.cur.fetchone()
        return res[0]

    def get_duplicate_keys(self, key: int) -> List[int]:
        """
        Given a key, gets all keys which are a known duplicate of it.
        :param key: key to get duplicates from
        :return: List of keys
        """
        self.debug_exec(f"SELECT key FROM replaced WHERE successor = {key}")
        res = self.cur.fetchall()
        return [x[0] for x in res]

    def list_import_tables(self):
        """
        Prepare all import tables to be displayed in the gui.
        :return:
        """
        self.debug_exec("SELECT key, root_path, import_table_name, import_table_descriptio FROM import_tables")
        tables = self.cur.fetchone()
        return [ImportTableEntry(key=t[0], root_path=t[1], table_name=t[2], table_desc=t[3]) for t in tables]

    def remove_import_table(self, tbl_name: str):
        """
        Removes the import table from the database and deletes the table.
        :param tbl_name:
        :return:
        """
        self.debug_exec(f"DELETE FROM import_tables WHERE import_table_name = '{tbl_name}'")
        try:
            self.debug_exec(f"DROP TABLE `{tbl_name}`")
        except sqlite3.OperationalError as e:
            if "no such table:" in str(e):
                print(f"Table {tbl_name} already deleted.")

    def change_import_table_desc(self, key: int, desc: str):
        """
        Change the description of an import table.
        :param key: key to change description of
        :param desc: string to change to.
        :return:
        """
        self.debug_exec(f"UPDATE import_tables SET import_table_descriptio = {desc} WHERE key = {key}")