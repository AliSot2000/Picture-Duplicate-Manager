from photo_lib.sqlite_wrapper import BaseSQliteDB
from photo_lib.new_metadata_aggregator import NewMetadataAggregator
import json
import multiprocessing as mp
import logging.handlers as handlers
import logging
import sys

logging_queue = mp.Queue()

listener = handlers.QueueListener(logging_queue, logging.StreamHandler(sys.stderr))
listener.start()


db = "scratch.db"
dbo = BaseSQliteDB(db)

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
mda = NewMetadataAggregator(logging_queue, discover=True)
mda.setup_logging()


if check_mda:
    res = dbo.sq_cur.fetchone()
    while res is not None:
        mda.metadata_to_datetime(json.loads(res[0]))
        if index % 1000 == 0:
            print(f"index: {index:06} of {todo}")
        index += 1
        res = dbo.sq_cur.fetchone()

    print(json.dumps(mda.new_dt_cfg.model_dump(), indent=4, sort_keys=True))

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