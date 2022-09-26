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
from multiprocessing import Queue, Process, Pipe, Lock
from multiprocessing.connection import Connection


class RareOccurrence(Warning):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class DuplicateChainingError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


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


def rec_list(root_path):
    def __rec_list(rp, results):
        sub = os.listdir(rp)
        for f in sub:
            np = os.path.join(rp, f)
            if os.path.isfile(np):
                results.append(np)
            elif os.path.isdir(np):
                __rec_list(np, results)

    res = []
    __rec_list(root_path, res)
    return res


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

    def __init__(self, root_dir: str, db_path: str = None, init: bool = False):

        if os.path.exists(root_dir):
            self.root_dir = root_dir
            self.thumbnail_dir = os.path.join(root_dir, ".thumbnails")
            self.trash_dir = os.path.join(root_dir, ".trash")
        else:
            raise ValueError(f"{root_dir} doesn't exist")

        if db_path is not None and os.path.exists(db_path):
            self.img_db = db_path
        else:
            # db default path
            self.img_db = os.path.join(self.root_dir, ".photos.db")

        if not os.path.exists(self.thumbnail_dir):
            os.mkdir(self.thumbnail_dir)

        if not os.path.exists(self.trash_dir):
            os.mkdir(self.trash_dir)

        self.__connect()

        if init:
            self.create_db()

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

    def create_db(self):
        try:
            self.cur.execute("CREATE TABLE images "
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
                             "verify INTEGER DEFAULT 0 CHECK (images.verify >= 0 AND images.verify < 2,"
                             "original_google_metadata INTEGER DEFAULT 1 "
                             "CHECK (images.original_google_metadata >= 0 AND images.original_google_metadata < 2)))")
        except sqlite3.OperationalError as e:
            print("*** You still try to initialize the database. Do not set init arg when instantiating class ***")
            raise e

        self.cur.execute("CREATE TABLE names"
                         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         "name TEXT UNIQUE)")

        # naming_tag, new_name, datetime from images table, drop path info because not needed anymore,
        # TODO: Database needs a new replaced table
        self.cur.execute("CREATE TABLE replaced "
                         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         " org_fname TEXT,"
                         " metadata TEXT,"
                         " google_fotos_metadata TEXT,"
                         " file_hash TEXT, "
                         " datetime TEXT,"
                         " successor INTEGER NOT NULL)")

        self.cur.execute("CREATE TABLE import_tables "
                         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         " root_path TEXT NOT NULL, "
                         " import_table_name TEXT UNIQUE NOT NULL) ")

        # Todo: Think about trash -> once removed images not reimported?
        self.cur.execute("CREATE TABLE trash "
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
                         f"google_fotos_metadata TEXT,"
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

        # set the not allowed files processed for the moment...
        # self.cur.execute(f"UPDATE {temp_table_name} SET processed = 1 WHERE allowed = 0")
        for i in range(number_of_files):
            if i % 100 == 0:
                print(i)

            self.cur.execute(
                f"SELECT org_fname, org_fpath, key FROM {temp_table_name} WHERE allowed = 1 AND processed = 0")
            cur_file = self.cur.fetchone()

            # all files which are allowed processed. stopping
            if cur_file is None:
                break

            # perform the metadata aggregation
            file_metadata = self.mda.process_file(os.path.join(cur_file[1], cur_file[0]))
            imported_file_name = self.__file_name_generator(file_metadata.datetime_object, file_metadata.org_fname)

            # should be imported?
            should_import, message, successor = self.determine_import(file_metadata, imported_file_name)

            # DEBUG AID
            # assert 0 <= should_import <= 2

            # 0 equal to not import, already present
            if should_import == 0:
                self.__handle_preset(table=temp_table_name, file_metadata=file_metadata,
                                     new_file_name=imported_file_name, msg=message, present_file_name=successor,
                                     update_key=cur_file[2])

            # straight import
            elif should_import == 1:
                self.__handle_import(fmd=file_metadata, new_file_name=imported_file_name, table=temp_table_name,
                                     msg=message, update_key=cur_file[2])

            elif should_import == 2:
                # on debug
                print(message)

                f_index = 1
                search = True
                while search and f_index < 1000:
                    imported_file_name = self.__file_name_generator(file_metadata.datetime_object,
                                                                    file_metadata.org_fname, f_index)

                    # should be imported?
                    should_import, message, successor = self.determine_import(file_metadata, imported_file_name)

                    # 0 equal to not import, already present
                    if should_import == 0:
                        self.__handle_preset(table=temp_table_name, file_metadata=file_metadata,
                                             new_file_name=imported_file_name, msg=message, present_file_name=successor,
                                             update_key=cur_file[2])
                        search = False

                    # straight import
                    if should_import == 1:
                        self.__handle_import(fmd=file_metadata, new_file_name=imported_file_name, table=temp_table_name,
                                             msg=message, update_key=cur_file[2])

                        search = False

                    # if should_import is 2
                    f_index += 1
                    print(f"{message}: {imported_file_name}")

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

    def __handle_preset(self, table: str, file_metadata: FileMetaData, new_file_name: str, msg: str,
                        present_file_name: str, update_key: int):
        if file_metadata.google_fotos_metadata is None:
            self.cur.execute(f"UPDATE {table} "
                             f"SET metadata = '{self.__dict_to_b64(file_metadata.metadata)}', "
                             f"file_hash = '{file_metadata.file_hash}', "
                             f"new_name = '{new_file_name}', "
                             f"imported = 0, "
                             f"processed=1, "
                             f"message = '{msg}', "
                             f"hash_based_duplicate = '{present_file_name}' WHERE key = {update_key}")
        else:
            self.cur.execute(f"UPDATE {table} "
                             f"SET metadata = '{self.__dict_to_b64(file_metadata.metadata)}', "
                             f"file_hash = '{file_metadata.file_hash}', "
                             f"new_name = '{new_file_name}', "
                             f"imported = 0, "
                             f"processed=1, "
                             f"message = '{msg}', "
                             f"google_fotos_metadata = '{self.__dict_to_b64(file_metadata.google_fotos_metadata)}', "
                             f"hash_based_duplicate = '{present_file_name}' WHERE key = {update_key}")

            self.cur.execute(f"SELECT key FROM images WHERE new_name is '{new_file_name}'")
            res = self.cur.fetchone()

            self.cur.execute(f"UPDATE images SET "
                             f"google_fotos_metadata = '{self.__dict_to_b64(file_metadata.google_fotos_metadata)}', "
                             f"original_google_metadata = 0")
        self.con.commit()

    def __handle_import(self, fmd: FileMetaData, new_file_name: str, table: str, msg: str, update_key: int):
        if not os.path.exists(self.__folder_from_datetime(fmd.datetime_object)):
            # create subdirectory
            os.makedirs(self.__folder_from_datetime(fmd.datetime_object))

        if os.path.exists(self.__path_from_datetime(fmd.datetime_object, new_file_name)):
            raise Exception(f"File Exists already; "
                            f"dst: {self.__path_from_datetime(fmd.datetime_object, new_file_name)}, "
                            f"src: {os.path.join(fmd.org_fpath, fmd.org_fname)}")

        # copy file and preserve metadata
        shutil.copy2(src=os.path.join(fmd.org_fpath, fmd.org_fname),
                     dst=self.__path_from_datetime(fmd.datetime_object, new_file_name),
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

    def determine_import(self, file_metadata: FileMetaData, new_name: str) -> tuple:
        # Verify existence in the database
        # TODO: rethink the present column in database
        self.cur.execute(f"SELECT org_fname, org_fpath, metadata, naming_tag, file_hash, new_name, datetime, key "
                         f"FROM images WHERE new_name IS '{new_name}'")

        match = self.cur.fetchone()

        # file doesn't exist -> insert and create database entry
        if match is None:
            return 1, "no entry in database", ""

        # generate path to new file as well as old file.
        dt_obj = self.__string_to_datetime(dt_str=match[6])
        old_path = self.__path_from_datetime(dt_obj=dt_obj, file_name=match[5])

        new_path = self.__path_from_datetime(file_metadata.datetime_object, new_name)

        # verify match by hash
        if match[4] != file_metadata.file_hash:
            return self.presence_in_replaced(file_metadata=file_metadata, key=match[7], old_file_name=match[5])

        # compare binary if hash is match
        if not filecmp.cmp(old_path, new_path, shallow=False):
            warnings.warn(f"Files with identital hash but differing binary found.\n"
                          f"New File: {new_path}\nOld File: {old_path}", RareOccurrence)
            return 2, "Entry in database with same hash but differing in binary", match[5]

        return 0, "Binary matching file found.", match[5]

    def presence_in_replaced(self, file_metadata: FileMetaData, key: int, old_file_name: str) -> tuple:
        # search the replaced databse
        self.cur.execute(
            f"SELECT metadata FROM replaced "
            f"WHERE successor = {key} AND hash IS '{file_metadata.file_hash}'")

        matches = self.cur.fetchall()

        # no matches, continue with import but change file name
        if len(matches) == 0:
            return 2, "no file found matching datetime and hash in replaced", ""

        # unusual event, multiple matching hashes... TODO: is this allowed / possible
        if len(matches) > 1:
            warnings.warn(f"Found {len(matches)} entries matching hash and creation datetime", RareOccurrence)

        # If filesize of one hash is smaller, import anyway and prommpt user to check
        for m in matches:
            metadict = self.__b64_to_dict(m[0])
            fsize = metadict["File:FileSize"]

            if fsize < file_metadata.metadata["File:FileSize"]:
                return 2, "Found one hash which has a smaller filesize in replaced", old_file_name

        # Import file, Message, (one of possibly many) matches
        return 0, "Found entry in database with matching hash and greater or equal filesize in replaced", old_file_name

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

    def mark_duplicate(self, o_image_id: int, d_image_id: int, delete: bool = False):

        # verify original is not a duplicate itself
        self.cur.execute(f"SELECT successor FROM replaced WHERE key is {o_image_id}")
        result = self.cur.fetchone()

        if result is not None:
            raise DuplicateChainingError(f"Original is duplicate itself, successor of original is {result[0]}")

        # get data from original
        self.cur.execute(
            f"SELECT key, org_fname, metadata, google_fotos_metadata, hash, datetime, new_name FROM images "
            f"WHERE key is {d_image_id}")
        data = self.cur.fetchall()

        # would violate SQL but just put it in here because I might be stupid
        assert len(data) == 1

        # insert duplicate into replaced table
        self.cur.execute(f"INSERT INTO replaced "
                         f"(key, org_fname, metadata, google_fotos_metadata, hash, successor) "
                         f"VALUES "
                         f"({data[0][0]}, {data[0][1]}, {data[0][2]}, {data[0][3]}, {data[0][4]}, {o_image_id})")

        self.con.commit()

        src = self.__path_from_datetime(self.__db_str_to_datetime(data[0][5]), data[0][5])

        if not delete:
            # might be redundant.
            self.create_img_thumbnail(data[0][0])

            # move file
            dst = self.__trash_path(data[0][5])

            if os.path.exists(dst):
                raise ValueError("Image exists in trash already?")

            os.rename(src, dst)
        else:
            os.remove(src)

    def bulk_duplicate_marking(self, processing_list: list):
        for f in processing_list:
            self.mark_duplicate(o_image_id=f["o_image_id"], d_image_id=f["d_image_id"], delete=f["delete"])

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
                naming_tag=res[4],
                file_hash=res[5],
                new_name=res[6],
                datetime=self.__db_str_to_datetime(res[7]),
                google_fotos_metadata=self.__b64_to_dict(res[10]))

        return None

    def create_img_thumbnail(self, key: int = None, fname: str = None, max_pixel: int = 512, overwrite: bool = False):
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

        img_dt = self.__db_str_to_datetime(results[0][2])
        img_key = results[0][0]
        img_fname = results[0][1]

        img_fpath = self.__path_from_datetime(img_dt, img_fname)

        # don't create a thumbnail if it already exists.
        if os.path.exists(self.__thumbnail_name(ext=os.path.splitext(img_fname)[1], key=img_key)) and not overwrite:
            return

        # load image from disk
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
        cv2.imwrite(self.__thumbnail_name(ext=os.path.splitext(img_fname)[1], key=img_key), img_half)

    def image_to_trash(self, key: int = None, fname: str = None):
        # both none
        if key is None and fname is None:
            raise ValueError("Key or fname must be provided")
        elif key is None:
            self.cur.execute(
                f"SELECT key, org_fname, org_fpath, metadata, google_fotos_metadata, naming_tag, file_hash,"
                f" new_name, datetime, original_google_metadata FROM images WHERE new_name IS '{fname}'")
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
        src = self.__path_from_datetime(self.__db_str_to_datetime(datetime), new_name)
        dst = self.__trash_path(new_name)

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

    def img_ana_dup_search(self, level: str, procs: int = 16, overwrite: bool = False):
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

        task_queue = Queue()
        [task_queue.put(directory) for directory in dirs]
        result_queue = Queue()
        init_size = len(dirs)

        def difpy_process(task: Queue, results: Queue, id: int):
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

                duplicates = dif(directory_A=task_dir, show_progress=False, show_output=False)
                results.put(duplicates.result)

        self.proc_handles = []

        for i in range(procs):
            p = Process(target=difpy_process, args=(task_queue, result_queue, i))
            p.start()
            self.proc_handles.append(p)

        pipe_out, pipe_in = Pipe()

        p = Process(target=self.result_processor, args=(init_size, result_queue, pipe_in, level))
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
        assert len(res) == 1

        return res[0][0]

    def result_processor(self, initial_size: int, result: Queue, pipe_in: Connection, info: str):
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

        duplicates = self.find_hash_based_duplicates(only_key=True)

        for d in duplicates:
            matching_keys = self.find_hash_in_pictures(d[0], only_key=True)

            self.cur.execute(f"INSERT INTO duplicates (match_type, matched_keys) "
                             f"VALUES ('hash', '{json.dumps(matching_keys)}')")

        self.con.commit()
        return True, msg + f"Successfully found {len(duplicates)} duplicates"

    def get_duplicate_entry(self):
        """
        Returns one entry from the duplicates table
        :return:
        """
        self.cur.execute("SELECT matched_keys FROM duplicates")
        key_str = self.cur.fetchone()

        if key_str is None:
            return False, []

        keys = json.loads(key_str)
        img_attribs = []

        for k in keys:
            img_attribs.append(self.gui_get_image(key=k))

        return True, img_attribs

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
