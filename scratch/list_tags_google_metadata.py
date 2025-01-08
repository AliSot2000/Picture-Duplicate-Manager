import json
import sys

import exiftool
import os


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
db_path = os.path.join(os.path.dirname(__file__), "google_scratch.db")

eh = exiftool.ExifToolHelper()
known_attrs = {}

from photo_lib.sqlite_wrapper import BaseSQliteDB
from typing import List, Union


class GoogleMetadataDB(BaseSQliteDB):
    def __init__(self, db_name):
        BaseSQliteDB.__init__(self, db_name)

    def create_scratch_table(self):
        """
        Create Table
        """
        self.debug_execute("CREATE TABLE IF NOT EXISTS scratch_google_md "
                           "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
                           "google_metadata TEXT, "
                           "path TEXT UNIQUE NOT NULL)")

    def purge_scratch_table(self):
        """
        Remove Table
        """
        self.debug_execute("DROP TABLE IF EXISTS scratch_google_md")

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

        self.debug_execute_many(stmt="INSERT OR IGNORE INTO scratch_google_md (google_metadata, path) VALUES (?, ?) ",
                                args=list(zip(md, path)))

db = GoogleMetadataDB(db_path)
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
            if os.path.splitext(f)[1].lower() != ".json":
                continue

            try:
                with open(path) as f:
                    data = json.load(f)

            except Exception as e:
                print(f"Failed to load {path}: {e}")
                continue

            mdp.append(path)
            mdj.append(json.dumps(data).replace("'", "''"))

        db.add_metadata(mdj, mdp)
        db.commit()


db.cleanup()
