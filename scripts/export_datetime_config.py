import os
import json


human_file = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "photo_lib", "metadata_aggregator", "datetime_human_fmt.json"))

comp_file = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "photo_lib", "metadata_aggregator", "datetime_fmt.json"))

hstat = os.stat(human_file)
cstat = os.stat(comp_file)

if hstat.st_mtime > cstat.st_mtime:
    print(f"{human_file} is newer than {comp_file} writing new compressed file")
    with open(human_file, "r") as f:
        data = json.load(f)

    with open(comp_file, "w") as f:
        json.dump(data, f)
