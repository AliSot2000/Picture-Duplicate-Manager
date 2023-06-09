import datetime
import filecmp
import os
import sqlite3
import json
import base64
import time

import cv2
from .metadataagregator import MetadataAggregator, FileMetaData
import shutil
from typing import Set, Union
import warnings
from dataclasses import dataclass
from difPy.dif import dif
from _queue import Empty
import multiprocessing as mp
import multiprocessing.connection as mpconn
from typing import Tuple
import sys
import ffmpeg
from .errors_and_warnings import *
from fast_diff_py import fastDif
from photo_lib.utils import rec_list_all


# INFO: If you run the img_ana_dup_search from another file and not the gui, MAKE SURE TO EMPTY THE PIPE.
# After around 1000 Calls, the pipe will be full and the program will freeze !!!

@dataclass
class DatabaseEntry:
    key: int
    org_fname: str
    org_fpath: str
    metadata: dict
    google_fotos_metadata: dict
    naming_tag: str
    file_hash: str
    new_name: str
    datetime: datetime.datetime
    verify: int


class PhotoDb:
    root_dir: str
    img_db: str
    thumbnail_dir: str
    trash_dir: str

    # database
    cur: sqlite3.Cursor = None
    con: sqlite3.Connection = None

    # allowed files in database:
    allowed_files: set = {".jpeg", ".jpg", ".png", ".mov", ".m4v", ".mp4", '.gif'}
    __mda: MetadataAggregator = None

    __datetime_format = "%Y-%m-%d %H.%M.%S"

    proc_handles: list = []

    # Table Creation Commands
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
         "present INTEGER DEFAULT 1 CHECK (images.present >= 0 AND images.present < 2), "
         "verify INTEGER DEFAULT 0 CHECK (images.verify >= 0 AND images.verify < 2),"
         "original_google_metadata INTEGER DEFAULT 1 "
         "CHECK (images.original_google_metadata >= 0 AND images.original_google_metadata < 2))")

    names_table_command: str = \
        "CREATE TABLE names (key INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)"

    replaced_table_command: str = \
        ("CREATE TABLE replaced "
         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
         " org_fname TEXT,"
         " metadata TEXT,"
         " google_fotos_metadata TEXT,"
         " file_hash TEXT, "
         " datetime TEXT,"
         " successor INTEGER NOT NULL)")

    import_tables_table_command: str = \
        ("CREATE TABLE import_tables "
         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
         " root_path TEXT NOT NULL, "
         " import_table_name TEXT UNIQUE NOT NULL)")

    trash_table_command: str = \
        ("CREATE TABLE trash "
         "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
         "org_fname TEXT NOT NULL, "
         "org_fpath TEXT NOT NULL, "
         "metadata TEXT NOT NULL, "
         "google_fotos_metadata TEXT,"
         "naming_tag TEXT, "
         "file_hash TEXT, "
         "new_name TEXT UNIQUE , "
         "datetime TEXT, "
         "original_google_metadata INTEGER DEFAULT 1 "
         "CHECK (trash.original_google_metadata >= 0 AND trash.original_google_metadata < 2))")

    table_command_dict: dict

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
                                   "trash": self.trash_table_command}

        self.__connect()

        existence, correctness = self.verify_tables()

        if not existence and not correctness:
            self.create_db()

        if existence and not correctness:
            raise CorruptDatabase("Database is not correctly formatted and might not work. Check the logs.")

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
        for i in range(1000):
            base = dt_obj.strftime(self.__datetime_format)
            extension = os.path.splitext(old_fname)[1].lower()
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
        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='duplicates'")
        dups = self.cur.fetchone()
        return dups is not None

    def create_duplicates_table(self):
        self.cur.execute("CREATE TABLE duplicates ("
                         "key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         "match_type TEXT,"
                         "matched_keys TEXT)")

    def delete_duplicates_table(self):
        self.cur.execute("DROP TABLE IF EXISTS duplicates")

    def get_duplicate_table_size(self):
        self.cur.execute("SELECT COUNT(key) FROM duplicates")
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
        self.cur.execute("SELECT import_table_name FROM import_tables")
        ttd = self.cur.fetchone()

        while ttd is not None:
            try:
                self.cur.execute(f"DROP TABLE {ttd[0]}")
                print(f"Successfully droped '{ttd[0]}'")
            except sqlite3.OperationalError as e:
                if "no such table:" in str(e):
                    print(f"table '{ttd[0]}' already deleted")

            self.cur.execute(f"DELETE FROM import_Tables WHERE import_table_name = '{ttd[0]}'")

            self.cur.execute("SELECT import_table_name FROM import_tables")
            ttd = self.cur.fetchone()

        self.con.commit()

    def __list_present_tables(self) -> list:
        self.cur.execute("SELECT name FROM sqlite_master WHERE type ='table'")
        result = self.cur.fetchall()
        tables = []

        # fill all table names into a single list
        for t in result:
            tables.append(t[0])

        return tables

    def __get_table_definition(self, table: str):
        # precondition, table exists already.
        self.cur.execute(f"SELECT sql FROM sqlite_master WHERE tbl_name = '{table}' AND type = 'table'")
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
        tables = ("images", "names", "replaced", "import_tables", "trash")
        all_correctly_formatted = True
        all_present = True

        for tb in tables:
            exists, correct = self.__verify_table(tb, existing_tables)
            all_correctly_formatted = all_correctly_formatted and correct
            all_present = all_present and exists

        return all_present, all_correctly_formatted

    def create_db(self):
        try:
            self.cur.execute(self.images_table_command)
        except sqlite3.OperationalError as e:
            print("*** You still try to initialize the database. Do not set init arg when instantiating class ***")
            raise e

        self.cur.execute(self.names_table_command)

        # naming_tag, new_name, from images table, drop path info because not needed anymore,
        # TODO: Database needs a new replaced table -> DAtetime and file_hash
        self.cur.execute(self.replaced_table_command)

        self.cur.execute(self.import_tables_table_command)

        # Todo: Think about trash -> once removed images not reimported?
        self.cur.execute(self.trash_table_command)

        self.con.commit()

    def rename_file(self, entry: DatabaseEntry, new_datetime: datetime.datetime, naming_tag: str):
        """
        Performs renaming action of a file
        :param entry: DatabaseEntry provided from g ui
        :param new_datetime: the new datetime generated from a tag
        :param naming_tag: the naming tag
        :return:
        """

        fmd = FileMetaData(org_fname=entry.org_fname,
                           org_fpath=entry.org_fpath,
                           metadata=entry.metadata,
                           naming_tag=naming_tag,
                           file_hash=entry.file_hash,
                           datetime_object=new_datetime,
                           verify=entry.verify == 1,
                           google_fotos_metadata=entry.google_fotos_metadata)

        imp, msg, successor = self.determine_import(file_metadata=fmd,
                                                    current_file_path=self.path_from_datetime(entry.datetime,
                                                                                              entry.new_name))

        new_name = self.__file_name_generator(new_datetime, entry.org_fname)
        new_path = self.path_from_datetime(new_datetime, new_name)

        old_path = self.path_from_datetime(entry.datetime, entry.new_name)

        # free file name
        self.cur.execute(f"DELETE FROM names WHERE name = '{entry.new_name}'")

        # warning -> if a match was found.
        if imp <= 0:
            print(f"While Renaming: {msg}")

        # update images table
        self.cur.execute(f"UPDATE images SET "
                         f"new_name = '{new_name}', "
                         f"naming_tag = '{naming_tag}', "
                         f"datetime = '{self.__datetime_to_db_str(new_datetime)}', "
                         f"verify = {1 - imp} "
                         f"WHERE key = {entry.key}")

        # update the names table
        self.cur.execute(f"INSERT INTO names (name) VALUES ('{new_name}')")

        print(f"Renaming: {old_path}\nto      : {new_path}")

        folder = self.__folder_from_datetime(new_datetime)
        if not os.path.exists(folder):
            os.makedirs(folder)

        os.rename(src=old_path, dst=new_path)
        return new_name

    def revert_import(self, tbl_name: str):
        """
        In case an import failed, revert the import and remove the images from the database and stuff.
        :param tbl_name: name of the import table
        :return:
        """
        self.cur.execute(f"SELECT * FROM {tbl_name}")
        rows = self.cur.fetchall()

        for row in rows:
            # imported is 1
            if row[7] == 1:
                dt = row[6].split("_")[0]
                try:
                    os.remove(self.path_from_datetime(self.__db_str_to_datetime(dt), row[6]))
                except FileNotFoundError:
                    print(f"File {row[6]} not found. Skipping.")

                # remove from the images table
                self.cur.execute(f"DELETE FROM images WHERE new_name = '{row[6]}'")

            # deleting the row from the import table
            self.cur.execute(f"DELETE FROM {tbl_name} WHERE key = {row[0]}")

        # deleting the import table
        self.cur.execute(f"DELETE FROM import_tables WHERE import_table_name = '{tbl_name}'")

        # dropping the table
        self.cur.execute(f"DROP TABLE {tbl_name}")
        self.con.commit()

    def import_folder(self, folder_path: str, al_fl: Set[str] = None, ignore_deleted: bool = False):
        folder_path = os.path.abspath(folder_path.rstrip("/"))
        temp_table_name = self.__create_import_table(folder_path)

        # add all files which aren't in allowed files already.
        if al_fl is None:
            al_fl = self.allowed_files

        # Step 1: Create Database
        self.cur.execute(f"CREATE TABLE {temp_table_name} "
                         f"(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         f" org_fname TEXT NOT NULL, "
                         f" org_fpath TEXT NOT NULL, "
                         f" metadata TEXT, "
                         f" google_fotos_metadata TEXT,"
                         f" file_hash TEXT, "
                         f" new_name TEXT,"
                         f" imported INTEGER DEFAULT 0 CHECK ({temp_table_name}.imported >= 0 AND {temp_table_name}.imported < 2),"
                         f" allowed INTEGER DEFAULT 0 CHECK ({temp_table_name}.allowed >= 0 AND {temp_table_name}.allowed < 2),"
                         f" processed INTEGER DEFAULT 0 CHECK ({temp_table_name}.processed >= 0 AND {temp_table_name}.processed < 2),"
                         f" message TEXT,"
                         f" hash_based_duplicate TEXT)")

        self.con.commit()

        # import all files in subdirectory and count them
        number_of_files = self.__rec_list(path=folder_path, table=temp_table_name, allowed_files=al_fl)
        self.con.commit()

        for i in range(number_of_files):
            if i % 100 == 0:
                print(i)

            # fetch a not processed file from import table
            self.cur.execute(
                f"SELECT org_fname, org_fpath, key FROM {temp_table_name} WHERE allowed = 1 AND processed = 0")
            cur_file = self.cur.fetchone()

            # all files which are allowed processed. stopping
            if cur_file is None:
                break

            # perform the metadata aggregation
            file_metadata = self.mda.process_file(os.path.join(cur_file[1], cur_file[0]))
            # imported_file_name = self.__file_name_generator(file_metadata.datetime_object, file_metadata.org_fname)

            # should be imported?
            should_import, message, successor = self.determine_import(file_metadata)

            # DEBUG AID
            # assert 0 <= should_import <= 2

            # 0 equal to not import, already present
            if should_import <= 0:
                self.__handle_preset(table=temp_table_name, file_metadata=file_metadata, msg=message,
                                     present_file_name=successor, update_key=cur_file[2], status_code=should_import,
                                     successor=successor)

            # straight import
            elif should_import == 1:
                self.__handle_import(fmd=file_metadata, table=temp_table_name, msg=message, update_key=cur_file[2])

        return temp_table_name

    def __rec_list(self, path, table: str, allowed_files: set):
        count = 0
        sub = os.listdir(path)
        for f in sub:
            np = os.path.join(path, f)
            if os.path.isfile(np):
                # compute the allowed
                f_allowed = 1 if os.path.splitext(np)[1].lower() in allowed_files else 0
                fname = os.path.basename(np)
                fpath = os.path.dirname(np)

                # insert into temporary database
                self.cur.execute(f"INSERT INTO {table} (org_fname, org_fpath, allowed) "
                                 f"VALUES ('{fname}', '{fpath}', {f_allowed})")
                count += 1
            elif os.path.isdir(np):
                count += self.__rec_list(np, table, allowed_files)
        return count

    def __handle_preset(self, table: str, file_metadata: FileMetaData, msg: str,
                        present_file_name: str, update_key: int, status_code: int, successor: str):
        """
        Handler to be called if a file which is to be imported is already present in the database.

        :param table: import_table for the currently imported folder
        :param file_metadata: metadata from MetadataAggregator of current file
        :param msg: Message from determine import
        :param present_file_name: id of the
        :param update_key:
        :return:
        """
        if file_metadata.google_fotos_metadata is None:
            self.cur.execute(f"UPDATE {table} "
                             f"SET metadata = '{self.__dict_to_b64(file_metadata.metadata)}', "
                             f"file_hash = '{file_metadata.file_hash}', "
                             f"imported = 0, "
                             f"processed=1, "
                             f"message = '{msg}', "
                             f"hash_based_duplicate = '{present_file_name}' WHERE key = {update_key}")
            self.con.commit()
        else:
            self.cur.execute(f"UPDATE {table} "
                             f"SET metadata = '{self.__dict_to_b64(file_metadata.metadata)}', "
                             f"file_hash = '{file_metadata.file_hash}', "
                             f"imported = 0, "
                             f"processed=1, "
                             f"message = '{msg}', "
                             f"google_fotos_metadata = '{self.__dict_to_b64(file_metadata.google_fotos_metadata)}', "
                             f"hash_based_duplicate = '{present_file_name}' WHERE key = {update_key}")
            self.con.commit()


            # TODO simplify the two if blocks.
            if status_code == 0:
                self.cur.execute(f"UPDATE images SET "
                                 f"google_fotos_metadata = '{self.__dict_to_b64(file_metadata.google_fotos_metadata)}', "
                                 f"original_google_metadata = 0 WHERE new_name = '{successor}'")

                self.con.commit()

            elif status_code == -1:
                self.cur.execute(f"UPDATE images SET "
                                 f"google_fotos_metadata = '{self.__dict_to_b64(file_metadata.google_fotos_metadata)}', "
                                 f"original_google_metadata = 0 WHERE new_name = '{successor}'")

                self.con.commit()
                # raise NotImplementedError("Updating of google fotos metadata if file is in replaced not implemented.")

    def __handle_import(self, fmd: FileMetaData, table: str, msg: str, update_key: int):

        # create subdirectory
        if not os.path.exists(self.__folder_from_datetime(fmd.datetime_object)):
            os.makedirs(self.__folder_from_datetime(fmd.datetime_object))

        new_file_name = self.__file_name_generator(fmd.datetime_object, fmd.org_fname)
        new_file_path = self.path_from_datetime(fmd.datetime_object, new_file_name)

        self.cur.execute(f"INSERT INTO names (name) VALUES ('{new_file_name}')")

        # copy file and preserve metadata
        shutil.copy2(src=os.path.join(fmd.org_fpath, fmd.org_fname),
                     dst=new_file_path,
                     follow_symlinks=True)

        if fmd.google_fotos_metadata is None:
            # create entry in images database
            self.cur.execute("INSERT INTO images (org_fname, org_fpath, metadata, naming_tag, "
                             "file_hash, new_name, datetime, present, verify) "
                             f"VALUES ('{fmd.org_fname}', '{fmd.org_fpath}',"
                             f"'{self.__dict_to_b64(fmd.metadata)}', '{fmd.naming_tag}', "
                             f"'{fmd.file_hash}', '{new_file_name}',"
                             f"'{self.__datetime_to_db_str(fmd.datetime_object)}',"
                             f"1, {1 if fmd.verify else 0})")

            # create entry in temporary database
            self.cur.execute(f"UPDATE {table} "
                             f"SET metadata = '{self.__dict_to_b64(fmd.metadata)}', "
                             f"file_hash = '{fmd.file_hash}', "
                             f"new_name = '{new_file_name}', "
                             f"imported = 1, "
                             f"processed = 1, "
                             f"message = '{msg}' WHERE key = {update_key}")
        else:
            # create entry in images database
            self.cur.execute("INSERT INTO images (org_fname, org_fpath, metadata, naming_tag, "
                             "file_hash, new_name, datetime, present, verify,google_fotos_metadata ) "
                             f"VALUES ('{fmd.org_fname}', '{fmd.org_fpath}',"
                             f"'{self.__dict_to_b64(fmd.metadata)}', '{fmd.naming_tag}', "
                             f"'{fmd.file_hash}', '{new_file_name}',"
                             f"'{self.__datetime_to_db_str(fmd.datetime_object)}',"
                             f"1, {1 if fmd.verify else 0},"
                             f"'{self.__dict_to_b64(fmd.google_fotos_metadata)}')")

            # create entry in temporary database
            self.cur.execute(f"UPDATE {table} "
                             f"SET metadata = '{self.__dict_to_b64(fmd.metadata)}', "
                             f"file_hash = '{fmd.file_hash}', "
                             f"new_name = '{new_file_name}', "
                             f"imported = 1, "
                             f"processed = 1, "
                             f"google_fotos_metadata = '{self.__dict_to_b64(fmd.google_fotos_metadata)}', "
                             f"message = '{msg}' WHERE key = {update_key}")

        self.con.commit()

    def determine_import(self, file_metadata: FileMetaData, current_file_path: str = None) -> tuple:
        # Verify existence in the database
        # TODO: rethink the present column in database

        print(file_metadata.datetime_object)

        self.cur.execute(f"SELECT org_fname, org_fpath, metadata, naming_tag, file_hash, new_name, datetime, key "
                         f"FROM images WHERE datetime IS '{self.__datetime_to_db_str(file_metadata.datetime_object)}'")

        matches = self.cur.fetchall()

        # check all matches in images database for hash and binary match
        for match in matches:

            # path to existing file
            dt_obj = self.__string_to_datetime(dt_str=match[6])
            old_path = self.path_from_datetime(dt_obj=dt_obj, file_name=match[5])

            # file that we want to import
            if current_file_path is None:
                current_file_path = os.path.join(file_metadata.org_fpath, file_metadata.org_fname)

            # verify match by hash, if has doesn't match, search replaced table
            if match[4] == file_metadata.file_hash:

                # compare binary if hash is match
                if not filecmp.cmp(old_path, current_file_path, shallow=False):
                    warnings.warn(f"Files with identical hash but differing binary found.\n"
                                  f"New File: {current_file_path}\nOld File: {old_path}", RareOccurrence)
                # matching hash and binary:
                else:
                    return 0, "Binary matching file found.", match[5]

        return self.presence_in_replaced(file_metadata=file_metadata)

    def presence_in_replaced(self, file_metadata: FileMetaData) -> tuple:
        # search the replaced database
        self.cur.execute(
            f"SELECT metadata, key, successor FROM replaced "
            f"WHERE datetime = '{self.__datetime_to_db_str(file_metadata.datetime_object)}' "
            f"AND file_hash IS '{file_metadata.file_hash}'")

        matches = self.cur.fetchall()

        # no matches, continue with import
        if len(matches) == 0:
            return 1, "no file found matching datetime and hash in replaced", ""

        # unusual event, multiple matching hashes... TODO: is this allowed / possible
        if len(matches) > 1:
            warnings.warn(f"Found {len(matches)} entries matching hash and creation datetime", RareOccurrence)
            return 1, "Found multiple matching entries, importing just to be sure", ""

        # number of matches must be 1 (from guard clauses before)
        # Get the file name of the image that is already present.
        self.cur.execute(f"SELECT new_name FROM images WHERE key = {matches[0][2]}")
        successor_in_images = self.cur.fetchone()
        if successor_in_images is None:
            warnings.warn(f"Found entry in replaced database with matching hash, but no successor in images database",
                          RareOccurrence)
            return 1, "Found entry in replaced database with matching hash, but no successor in images database", ""

        successor_name = successor_in_images[0]
        return -1, "Found entry in database with matching hash", successor_name

    def __create_import_table(self, folder_path: str) -> str:
        table_name = os.path.basename(folder_path)
        table_name = table_name.replace("-", "_ds_").replace(" ", "_sp_").replace(".", "_d_")
        if table_name[0].isdigit():
            table_name = "t" + table_name
        print(table_name)
        name_extension = -1

        try:
            self.cur.execute(f"INSERT INTO import_tables (root_path, import_table_name) VALUES "
                             f"('{folder_path}', '{table_name}')")
            return table_name
        except sqlite3.IntegrityError:
            name_extension = 0

        # try 100 times to find a matching name
        while 0 <= name_extension < 100:
            try:
                self.cur.execute(f"INSERT INTO import_tables (root_path, import_table_name) VALUES "
                                 f"('{folder_path}', '{table_name}{name_extension}')")
                return f"{table_name}{name_extension}"
            except sqlite3.IntegrityError:
                name_extension += 1

        raise Exception("Couldn't create import table, to many matching names")

    def find_hash_based_duplicates(self, only_key: bool = True):
        """
        Finds all hashes that occur more than once and provides one full image each.
        :return:
        """
        self.cur.execute("SELECT *, COUNT(key) FROM images GROUP BY file_hash HAVING COUNT(key) > 1")

        results = self.cur.fetchall()

        duplicates = []

        if not only_key:
            for row in results:
                duplicates.append({
                    "key": row[0],
                    "org_fname": row[1],
                    "org_fpath": row[2],
                    "metadata": row[3],
                    "naming_tag": row[4],
                    "file_hash": row[5],
                    "new_name": row[6],
                    "datetime": row[7],
                    "present": row[8],
                    "verify": row[9],
                    "google_fotos_metadata": row[10],
                    "count": row[11]
                })

            return duplicates

        return [row[0] for row in results]

    def find_hash_in_pictures(self, hash_str: str, only_key: bool = True) -> list:
        """
        Returns a list of all images with identical hash
        :param only_key: only returns a list of the keys with the same hash, not entire rows
        :param hash_str: hash to search for
        :return:
        """
        self.cur.execute(f"SELECT * FROM images WHERE file_hash = '{hash_str}'")

        results = self.cur.fetchall()

        duplicates = []

        if not only_key:
            for row in results:
                duplicates.append({
                    "key": row[0],
                    "org_fname": row[1],
                    "org_fpath": row[2],
                    "metadata": row[3],
                    "naming_tag": row[4],
                    "file_hash": row[5],
                    "new_name": row[6],
                    "datetime": row[7],
                    "present": row[8],
                    "verify": row[9],
                    "google_fotos_metadata": row[10],
                })

            return duplicates

        # only list keys
        return [row[0] for row in results]

    # def hash_bin_dups(self, dryrun: bool = True):
    #     hash_matches = self.find_hash_based_duplicates()
    #
    #     # iterate over list and search for files which match binary
    #     for row in hash_matches:
    #         matching_hashes = self.find_hash_in_pictures(row["file_hash"])
    #
    #         first_file = self.__path_from_datetime(self.__db_str_to_datetime(matching_hashes[0]["datetime"]),
    #                                                matching_hashes[0]["new_name"])
    #
    #         # only matching to first image:
    #         for i in range(1, len(matching_hashes)):
    #             current_file = self.__path_from_datetime(self.__db_str_to_datetime(matching_hashes[i]["datetime"]),
    #                                                      matching_hashes[i]["new_name"])
    #
    #             if not filecmp.cmp(first_file, current_file, shallow=False):
    #                 print(f"{first_file} and {current_file} have matching hashes but not matching binary data")
    #             else:
    #                 if matching_hashes[0]['naming_tag'] == matching_hashes[i]['naming_tag']:
    #                     print(f"{matching_hashes[0]['new_name']} and {matching_hashes[i]['new_name']} match binary")
    #                 else:
    #                     print(
    #                         f"{matching_hashes[0]['new_name']} named {matching_hashes[0]['naming_tag']} and {matching_hashes[i]['new_name']} named {matching_hashes[0]['naming_tag']}  match binary")
    #
    #             if not dryrun:
    #                 # here would be the deletion and shit.
    #                 pass

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
        self.cur.execute(f"SELECT successor FROM replaced WHERE key is {successor}")
        result = self.cur.fetchone()

        if result is not None:
            raise DuplicateChainingError(f"Original is duplicate itself, successor of original is {result[0]}")

        # get data from the target to be marked as duplicate from the main table
        self.cur.execute(
            f"SELECT key, org_fname, metadata, google_fotos_metadata, file_hash, datetime, new_name FROM images "
            f"WHERE key is {duplicate_image_id}")
        data = self.cur.fetchall()

        # would violate SQL but just put it in here because I might be stupid
        assert len(data) == 1

        # insert duplicate into replaced table
        self.cur.execute(f"INSERT INTO replaced "
                         f"(key, org_fname, metadata, google_fotos_metadata, file_hash, successor, datetime) "
                         f"VALUES "
                         f"({data[0][0]}, '{data[0][1]}', '{data[0][2]}', '{data[0][3]}', '{data[0][4]}', {successor}, "
                         f"'{data[0][5]}')")

        # is removed duplicate from main table because it could result in confusion
        self.cur.execute(f"DELETE FROM images WHERE key = {duplicate_image_id}")

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
            self.cur.execute(f"SELECT key, org_fname , org_fpath, metadata, google_fotos_metadata, naming_tag, "
                             f"file_hash, new_name , datetime, present, verify FROM images WHERE key is {key}")

        else:
            self.cur.execute(f"SELECT key, org_fname , org_fpath, metadata, google_fotos_metadata, naming_tag, "
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

    def get_metadata(self,  key: int = None, filename: str = None):
        if key is None and filename is None:
            raise ValueError("Key or Filename must be provided")

        if key is not None:
            self.cur.execute(f"SELECT metadata FROM images WHERE key is {key}")

        else:
            self.cur.execute(f"SELECT metadata FROM images WHERE new_name = '{filename}'")

        res = self.cur.fetchone()

        if res is not None:
            return self.__b64_to_dict(res[0])

        return None

    def create_vid_thumbnail(self, key: int = None, fname: str = None, max_pixel: int = 512,
                             overwrite: bool = False, inform: bool = False) -> bool:
        # both none
        if key is None and fname is None:
            raise ValueError("Key or fname must be provided")
        elif key is None:
            self.cur.execute(f"SELECT key, new_name, datetime FROM images WHERE new_name IS '{fname}'")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        # key provided -> overrules a secondary fname
        else:
            self.cur.execute(f"SELECT key, new_name, datetime FROM images WHERE key = {key}")
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
        if os.path.exists(self.thumbnail_name(ext=os.path.splitext(img_fname)[1], key=img_key)) and not overwrite:
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
                .output(self.thumbnail_name(ext=".jpg", key=img_key), vframes=1)
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
            self.cur.execute(f"SELECT key, new_name, datetime FROM images WHERE new_name IS '{fname}'")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        # key provided -> overrules a secondary fname
        else:
            self.cur.execute(f"SELECT key, new_name, datetime FROM images WHERE key = {key}")
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
                # print(f"{img_fname} was not of supported type to create thumbnails with cv2 lib.")
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
            px = int(max_pixel / max_pix * img.shape[1])
        else:
            px = max_pixel
            py = int(max_pixel / max_pix * img.shape[0])

        # resize image to new size
        img_half = cv2.resize(img, dsize=(px, py))

        # store image
        cv2.imwrite(self.thumbnail_name(ext=os.path.splitext(img_fname)[1], key=img_key), img_half)

        return True

    def image_to_trash(self, key: int = None, file_name: str = None):
        # both none
        if key is None and file_name is None:
            raise ValueError("Key or file name must be provided")
        elif key is None:
            self.cur.execute(
                f"SELECT key, org_fname, org_fpath, metadata, google_fotos_metadata, naming_tag, file_hash,"
                f" new_name, datetime, original_google_metadata FROM images WHERE new_name IS '{file_name}'")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical name")

        # key provided -> overrules a secondary fname
        else:
            self.cur.execute(
                f"SELECT key, org_fname, org_fpath, metadata, google_fotos_metadata, naming_tag, file_hash,"
                f" new_name, datetime, original_google_metadata FROM images WHERE key = {key}")
            results = self.cur.fetchall()

            if len(results) > 1:
                raise ValueError("Corrupted Database - multiple images with identical key")

        # Parse the result of the Database
        key = results[0][0]
        org_fname = results[0][1]
        org_fpath = results[0][2]
        metadata = results[0][3]
        google_fotos_metadata = results[0][4]
        naming_tag = results[0][5]
        file_hash = results[0][6]
        new_name = results[0][7]
        datetime = results[0][8]
        original_google_metadata = results[0][9]

        # make sure thumbnail exists
        self.create_img_thumbnail(key=key)

        # move file
        src = self.path_from_datetime(self.__db_str_to_datetime(datetime), new_name)
        dst = self.trash_path(new_name)

        if os.path.exists(dst):
            raise ValueError("Image exists in trash already?")

        os.rename(src, dst)

        # create entries in databases
        self.cur.execute("INSERT into trash "
                         "(key, org_fname, org_fpath, metadata, google_fotos_metadata, naming_tag, file_hash,"
                         f" new_name, datetime, original_google_metadata) "
                         "VALUES "
                         f"({key}, '{org_fname}', '{org_fpath}', '{metadata}', '{google_fotos_metadata}', "
                         f"'{naming_tag}', '{file_hash}', '{new_name}', '{datetime}', {original_google_metadata})")

        self.cur.execute(f"DELETE FROM images WHERE key = {key}")
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

                self.cur.execute(f"INSERT INTO duplicates (match_type, matched_keys) "
                                 f"VALUES ('{info}', '{json.dumps(keys)}')")
            self.con.commit()
            pipe_in.send((i, initial_size))

        pipe_in.send("DONE")
        pipe_in.close()


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
        self.cur.execute(f"SELECT key FROM images WHERE new_name = '{file_name}'")
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

                self.cur.execute(f"INSERT INTO duplicates (match_type, matched_keys) "
                                 f"VALUES ('{info}', '{json.dumps(keys)}')")
            self.con.commit()
            pipe_in.send((count, initial_size))

        pipe_in.send("DONE")
        pipe_in.close()

    def duplicates_from_hash(self, overwrite: bool = False) -> tuple:
        """
        Populates the duplicates table based on duplicates detected by identical hash
        :param overwrite: do not ask if existing duplicate computations should be preserved.
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

        duplicates = self.find_hash_based_duplicates(only_key=False)

        for i in range(len(duplicates)):
            if i % 100 == 0:
                print(f"Processing {i} of {len(duplicates)}")

            d = duplicates[i]
            matching_keys = self.find_hash_in_pictures(d["file_hash"], only_key=True)

            self.cur.execute(f"INSERT INTO duplicates (match_type, matched_keys) "
                             f"VALUES ('hash', '{json.dumps(matching_keys)}')")

        print(f"Done Processing")

        self.con.commit()
        return True, msg + f"Successfully found {len(duplicates)} duplicates"

    def delete_duplicate_row(self, key: int):
        self.cur.execute(f"DELETE FROM duplicates WHERE key = {key}")
        self.con.commit()

    def get_duplicate_entry(self):
        """
        Returns one entry from the duplicates table
        :return:
        """
        self.cur.execute("SELECT matched_keys, key FROM duplicates")
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

    def fill_names(self):
        index = 0
        self.cur.execute(f"SELECT new_name FROM images WHERE key >= {index}")
        result = self.cur.fetchone()

        count = 0

        while result is not None:
            # increment index
            index += 1

            # check if name is already present
            self.cur.execute(f"SELECT name FROM names WHERE name = '{result[0]}'")
            found = self.cur.fetchone()

            # if not, insert into db
            if found is None:
                self.cur.execute(f"INSERT INTO names (name) VALUES ('{result[0]}')")
                count += 1

            # fetch next new_name
            self.cur.execute(f"SELECT new_name FROM images WHERE key >= {index}")
            result = self.cur.fetchone()

        self.con.commit()
        print(f"Added {count} non-tracked names to names table of {index} entries")

    def thumbnail_creation(self):
        index = 0
        self.cur.execute(f"SELECT key FROM images WHERE key >= {index}")
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
            self.cur.execute(f"SELECT key FROM images WHERE key >= {index}")
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
        self.cur.execute(f"SELECT new_name, datetime FROM images WHERE key = {a_key}")
        res_a = self.cur.fetchall()

        if len(res_a) == 0:
            return None, "Failed to find key_a in images"

        if len(res_a) > 1:
            raise CorruptDatabase("Multiple entries with identical key")

        # Locate Entry b
        self.cur.execute(f"SELECT new_name, datetime FROM images WHERE key = {b_key}")
        res_b = self.cur.fetchall()

        if len(res_a) == 0:
            return None, "Failed to find key_b in images"

        if len(res_a) > 1:
            raise CorruptDatabase("Multiple entries with identical key")

        path_a = self.path_from_datetime(self.__db_str_to_datetime(res_a[0][1]), res_a[0][0])
        path_b = self.path_from_datetime(self.__db_str_to_datetime(res_b[0][1]), res_b[0][0])

        success = filecmp.cmp(path_a, path_b, shallow=False)
        msg = f"'{res_a[0][0]}' is{'' if success else ' FUCKING NOT'} identical to '{res_b[0][0]}'"

        return success, msg

    def index_files(self):
        """
        Go through database and check that all files have a key associated with them.

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