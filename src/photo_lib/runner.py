import datetime
import filecmp
import os
import sqlite3
import json
import base64

from docutils.nodes import emphasis

from .metadataagregator import MetadataAggregator, FileMetaData
import shutil
from typing import Set
import warnings


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

    # database
    cur: sqlite3.Cursor = None
    con: sqlite3.Connection = None

    # allowed files in database:
    allowed_files: set = {".jpeg", ".jpg", ".png", ".mov", ".m4v", ".mp4", '.gif'}
    __mda: MetadataAggregator = None

    __datetime_format = "%Y-%m-%d %H.%M.%S"

    def __init__(self, root_dir: str, db_path: str = None, init: bool = False):

        if os.path.exists(root_dir):
            self.root_dir = root_dir
        else:
            raise ValueError(f"{root_dir} doesn't exist")

        if db_path is not None and os.path.exists(db_path):
            self.img_db = db_path
        else:
            # db default path
            self.img_db = os.path.join(self.root_dir, ".photos.db")

        self.__connect()

        if init:
            self.create_db()

    # ------------------------------------------------------------------------------------------------------------------
    # UTILITY CONVERTERS
    # ------------------------------------------------------------------------------------------------------------------

    def __folder_from_datetime(self, dt_obj: datetime.datetime):
        return os.path.join(self.root_dir, f"{dt_obj.year}", f"{dt_obj.month:02}", f"{dt_obj.day:02}")

    def __path_from_datetime(self, dt_obj: datetime.datetime, file_name: str):
        return os.path.join(self.__folder_from_datetime(dt_obj), file_name)

    def __datetime_to_db_str(self, dt_obj: datetime.datetime):
        return dt_obj.strftime(self.__datetime_format)

    def __db_str_to_datetime(self, dt_str: str):
        return datetime.datetime.strptime(dt_str, self.__datetime_format)

    def __file_name_generator(self, dt_obj: datetime.datetime, old_fname: str, index: int = 0):
        base = dt_obj.strftime(self.__datetime_format)
        extension = os.path.splitext(old_fname)[1].lower()
        return f"{base}_{index:03}{extension}"

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

    # ------------------------------------------------------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def mda(self):
        return self.__mda

    @mda.setter
    def mda(self, value):
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
                             "verify INTEGER DEFAULT 0 CHECK (images.verify >= 0 AND images.verify < 2))")
        except sqlite3.OperationalError as e:
            print("*** You still try to initialize the database. Do not set init arg when instantiating class ***")
            raise e

        self.cur.execute("CREATE TABLE replaced "
                         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         " org_fname TEXT,"
                         " metadata TEXT,"
                         " google_fotos_metadata TEXT,"
                         " hash TEXT, "
                         " successor INTEGER NOT NULL)")

        self.cur.execute("CREATE TABLE import_tables "
                         "(key INTEGER PRIMARY KEY AUTOINCREMENT,"
                         " root_path TEXT NOT NULL, "
                         " import_table_name TEXT UNIQUE NOT NULL) ")

        self.con.commit()

        # Todo: Think about trash -> once removed images not reimported?
        # self.cur.execute("CREATE TABLE trashed "
        #                  "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
        #                  "org_fname TEXT NOT NULL, "
        #                  "org_fpath TEXT NOT NULL, "
        #                  "metadata TEXT NOT NULL, "
        #                  "naming_tag TEXT, "
        #                  "file_hash TEXT, "
        #                  "new_name TEXT)")

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
                    print(message)

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



