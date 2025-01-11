import json
import logging
import logging.handlers as handlers
import multiprocessing as mp
import os.path
import sys

from photo_lib.custom_enum import DateTimeSource
from photo_lib.new_metadata_aggregator import NewMetadataAggregator
from photo_lib.sqlite_wrapper import BaseSQliteDB

logging_queue = mp.Queue()

listener = handlers.QueueListener(logging_queue, logging.StreamHandler(sys.stderr))
listener.start()


db = "scratch.db"
dbo = BaseSQliteDB(db)

gdb = "google_scratch.db"
gdbo = BaseSQliteDB(gdb)

dbo.debug_execute("SELECT COUNT(*) "
                  "FROM scratch_md "
                  "WHERE path NOT LIKE '/mnt/Aljoscha-Storage/dedup-benchmark/IMDB-Benchmark/%'")
todo = dbo.sq_cur.fetchone()[0]

index = 0
check_mda: bool = True
build_attrs: bool = False


dbo.debug_execute("SELECT metadata, path "
                  "FROM scratch_md "
                  "WHERE key > ? AND path NOT LIKE '/mnt/Aljoscha-Storage/dedup-benchmark/IMDB-Benchmark/%'",
                  (index,))

logger = logging.getLogger("MetadataAggregator")
logger.setLevel(logging.DEBUG)
h = handlers.QueueHandler(logging_queue)
h.setLevel(logging.DEBUG)
logger.addHandler(h)

mda = NewMetadataAggregator(use_dateutil=True, discover=False, logger=logger)

aware = 0
unaware_gps = 0
unaware_default = 0
file_aware = 0
date_or_time = 0
google_photos_aware = 0
google_photos_unaware = 0
from_dateutil = 0

skipped_json = 0

if check_mda:
    res = dbo.sq_cur.fetchone()

    while res is not None:
        path = res[1] + ".json"
        gdbo.debug_execute("SELECT google_metadata FROM scratch_google_md WHERE path = ?", (path,))
        gfres = gdbo.sq_cur.fetchone()

        if gfres is not None:
            # google fotos metadata
            gfmd = json.loads(gfres[0])

            google_photos_results = mda.parse_google_photos_metadata(gfmd)
        else:
            google_photos_results = None

        # mda.search_possible_new_keys(json.loads(res[0]))

        if os.path.splitext(res[1])[1] == ".json":
            skipped_json += 1
            res = dbo.sq_cur.fetchone()
            continue

        dt_pr, source, _ = mda.metadata_to_datetime(md=json.loads(res[0]),
                                                    google_photos_result=google_photos_results)
        if source == DateTimeSource.ANY_AWARE:
            aware += 1
        elif source == DateTimeSource.UNAWARE_GPS:
            unaware_gps += 1
        elif source == DateTimeSource.UNAWARE_DEFAULT:
            unaware_default += 1
        elif source == DateTimeSource.FILE_AWARE:
            file_aware += 1
        elif source == DateTimeSource.DATE_OR_TIME:
            date_or_time += 1
        elif source == DateTimeSource.GOOGLE_PHOTOS_AWARE:
            google_photos_aware += 1
        elif source == DateTimeSource.GOOGLE_PHOTOS_UNAWARE:
            google_photos_unaware += 1
        else:
            raise ValueError("Tertiem Non Datur")


        if index % 1000 == 0:
            print(f"index: {index:06} of {todo}")
        index += 1
        res = dbo.sq_cur.fetchone()

    if mda.new_dt_cfg is not None:
        print(json.dumps(mda.new_dt_cfg.model_dump(), indent=4, sort_keys=True))

    print(f"Found {aware} timezone aware datetimes, \n"
          f"{unaware_gps} Unaware Datetimes with GPS Position, \n"
          f"{unaware_default} unaware without gps, using default timezone \n"
          f"{file_aware} files without any extra datetime information\n"
          f"{date_or_time} files with either date or time but not datetime from additional keys\n"
          f"{google_photos_aware} Google Photos aware datetimes, \n"
          f"{google_photos_unaware} Google Photos unaware datetimes, \n"
          f"{mda.dt_util_count} Parsed without specific instructions from datetuil\n"
          f"{skipped_json} Files skipped because json")

    print(f"Number of new keys found: {len(mda.found_keys)}")
    for key, value in mda.found_keys.items():
        print(f"Possible key: {key}: {value}")

if build_attrs:
    data_dict = {}
    val_dict = {}

    res = dbo.sq_cur.fetchone()
    while res is not None:
        data = json.loads(res[0])
        print(res[1])
        for key, value in data.items():
            if data_dict.get(key) is None and value:
                data_dict[key] = {"value": value, "source": res[1]}
                val_dict[key] = value
        res = dbo.sq_cur.fetchone()

    # Writing to file
    with open("known_attrs_google.json", "w") as f:
        json.dump(data_dict, f, indent=4, sort_keys=True)

    with open("known_attrs_google.json", "w") as f:
        json.dump(val_dict, f, indent=4, sort_keys=True)


listener.stop()