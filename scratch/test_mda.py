from photo_lib.metadata_aggregator.new_metadata_aggregator import NewMetadataAggregator
from photo_lib.metadata_aggregator.dataclasses import MetadataParsingResult
import logging
import sys
from photo_lib.sqlite_wrapper import BaseSQliteDB
import os
import json


"""
File goes through all direcctoreis specified in the paths variable. Then adds the metadata persing 
result into the table.
"""


class ScratchDB(BaseSQliteDB):
    def __init__(self, db_name):
        BaseSQliteDB.__init__(self, db_name)

    def create_scratch_table(self):
        """
        Create Table
        """
        self.debug_execute("CREATE TABLE IF NOT EXISTS scratch_md "
                           "(key INTEGER PRIMARY KEY AUTOINCREMENT, "
                           "filename TEXT NOT NULL, "
                           "dirname TEXT NOT NULL,"
                           "creation_datetime TEXT NOT NULL,"
                           "naming_tag TEXT NOT NULL,"
                           "file_hash TEXT NOT NULL,"
                           "metadata TEXT,"
                           "google_photos_metadata TEXT,"
                           "gps_latitude REAL,"
                           "gps_longitude REAL,"
                           "timezone_name TEXT,"
                           "datetime_source TEXT)")

    def create_index(self):
        """
        Create Index for faster searching
        """
        self.debug_execute("CREATE INDEX IF NOT EXISTS filepath_idx ON scratch_md (filename, dirname)")

    def purge_scratch_table(self):
        """
        Remove Table
        """
        self.debug_execute("DROP TABLE IF EXISTS scratch_md")

    def add_metadata(self, md: MetadataParsingResult):
        """
        Add metadata to the table
        """
        tz_name = md.tz_name if isinstance(md.tz_name, str) else md.tz_name.key
        self.debug_execute("INSERT INTO scratch_md ("
                           "filename, "
                           "dirname, "
                           "creation_datetime, "
                           "naming_tag, "
                           "file_hash, "
                           "metadata, "
                           "google_photos_metadata, "
                           "gps_latitude, "
                           "gps_longitude, "
                           "timezone_name, "
                           "datetime_source) VALUES ("
                           "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", args=(
            md.filename,
            md.dirname,
            md.creation_date,
            md.naming_tag,
            md.file_hash,
            json.dumps(md.metadata).replace("'", "''") if md.metadata is not None else None,
            json.dumps(md.google_photos_metadata).replace("'", "''") if md.google_photos_metadata is not None else None,
            md.gps_lat,
            md.gps_long,
            tz_name,
            md.source  ))

recover: bool = True


path = "full.db"
db  = ScratchDB(path)
if not recover:
    db.purge_scratch_table()
db.create_scratch_table()
db.create_index()

paths = ["/mnt/Aljoscha-Storage/trash/",
         "/mnt/Aljoscha-Storage/herbstball/",

         # "/mnt/Aljoscha-Storage/dedup-benchmark/",
         "/mnt/Aljoscha-Storage/dedup-benchmark/TQ-Benchmark/",

         "/mnt/Aljoscha-Storage/Photo_Library_Correct/",
         "/mnt/Aljoscha-Storage/Photo_Library_Correct_10_07_2023/",
         "/mnt/Aljoscha-Storage/Photo_Library_New_16.7.2023/",
         "/mnt/Aljoscha-Storage/PLC_bis_Export_Fotos_MacBook/",
         "/mnt/Aljoscha-Storage/PLC_Pre_Google_Fotos_AliSot2000/"]

fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MetadataAggregator")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(fmt)
handler.setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

mda = NewMetadataAggregator(logger=logger)
paths = paths + ["/home/alisot2000/Desktop/2024-30-11-Photos-Retrat/"]
paths = paths + ["/home/alisot2000/Desktop/New_DB/"]
# paths = ["/home/alisot2000/Desktop/2024-30-11-Photos-Retrat/"]
# paths = ["/mnt/Aljoscha-Storage/trash/GD_The_Small_Lets_play/Takeout/"]

for p in paths:
    for root, dirs, files in os.walk(p):
        print(f"Checking {root} with {len(files)} files")

        if len(files) == 0:
            continue

        for f in files:
            db.debug_execute("SELECT filename, dirname FROM scratch_md WHERE filename IS ? AND dirname IS ?",
                             (f, os.path.abspath(root)))
            res = db.sq_cur.fetchone()
            if res is not None:
                print(f"Skipping {os.path.join(root, f)}")
                continue

            path = os.path.join(root, f)

            res = mda.handle_file(path)
            db.add_metadata(res)

        db.commit()
