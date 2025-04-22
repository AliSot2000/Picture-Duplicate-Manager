import json
import sys

import exiftool
import os


"""
Create the database which contains the results of the exiftool. That way, we can run the test against the 
database and don't have to mount the file system with all files.
"""


paths = ["/mnt/Aljoscha-Storage/trash/",
         "/mnt/Aljoscha-Storage/herbstball/",

         "/mnt/Aljoscha-Storage/dedup-benchmark/",

         "/mnt/Aljoscha-Storage/Photo_Library_Correct/",
         "/mnt/Aljoscha-Storage/Photo_Library_Correct_10_07_2023/",
         "/mnt/Aljoscha-Storage/Photo_Library_New_16.7.2023/",
         "/mnt/Aljoscha-Storage/PLC_bis_Export_Fotos_MacBook/",
         "/mnt/Aljoscha-Storage/PLC_Pre_Google_Fotos_AliSot2000/"]

# paths = ["/home/alisot2000/Desktop/2024-30-11-Photos-Retrat/"]
paths = paths + ["/home/alisot2000/Desktop/2024-30-11-Photos-Retrat/"]
db_path = os.path.join(os.path.dirname(__file__), "scratch.db")

eh = exiftool.ExifToolHelper()
known_attrs = {}

from photo_lib.sqlite_wrapper import BaseSQliteDB
from typing import List, Union


class ScratchDB(BaseSQliteDB):
    def __init__(self, db_name):
        BaseSQliteDB.__init__(self, db_name)

    def create_scratch_table(self):
        """
        Create Table
        """
        self.debug_execute("CREATE TABLE IF NOT EXISTS scratch_md "
                           "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
                           "metadata TEXT, "
                           "path TEXT UNIQUE NOT NULL)")

    def purge_scratch_table(self):
        """
        Remove Table
        """
        self.debug_execute("DROP TABLE IF EXISTS scratch_md")

    def add_metadata(self, md: Union[str, List[str]] , path: Union[str, List[str]]):
        """
        Add Metadata to the table
        """
        if isinstance(md, str) and isinstance(path, str):
            md = [md]
            path = [path]

        elif isinstance(md, list) and isinstance(path, list):
            pass
        else:
            raise TypeError("Both Arguments must be str or list")

        self.debug_execute_many(stmt="INSERT OR IGNORE INTO scratch_md (metadata, path) VALUES (?, ?) ",
                                args=list(zip(md, path)))


db = ScratchDB(db_path)
db.create_scratch_table()

for p in paths:
    for root, dirs, files in os.walk(p):
        print(f"Checking {root} with {len(files)} files")

        if len(files) == 0:
            continue

        mdp = []
        mdj = []

        for f in files:
            path = os.path.join(root, f)

            try:
                md = eh.get_metadata(path)
            except exiftool.exceptions.ExifToolExecuteError:
                print(f"ExifTool failed for {path}", file=sys.stderr)

            if len(md) !=  1:
                print(f"Unexpected number of metadata for {path} {len(md)}", file=sys.stderr)
                continue

            m = md[0]

            for key, value in m.items():

                if known_attrs.get(key) is None:
                    known_attrs[key] = {"value": value, "source": m.get("SourceFile")}

            if not "SourceFile" in m.keys():
                print(f"Missing File Path Information", file=sys.stderr)
                continue

            mdp.append(m["SourceFile"])
            mdj.append(json.dumps(m).replace("'", "''"))

        db.add_metadata(mdj, mdp)
        db.commit()

        with open("known_attrs3.json", "w") as outfile:
            json.dump(known_attrs, outfile, indent=4, sort_keys=True)


db.cleanup()
