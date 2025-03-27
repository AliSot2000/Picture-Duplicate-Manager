# pragma: no cover

import os
from photo_lib.new_photo_api import PhotoAPI


dummy_files = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..", "testing", "test_file_out"))

# Create a fresh instance
api = PhotoAPI(root_path=os.path.join(os.path.dirname(__file__),"testing_db"),
               init=True,
               init_loggers=True,
               opt_integrity_check=True)

tgt_table = api.prepare_directory_for_import(source_dir=os.path.join(dummy_files, "db"))
api.db.debug_execute(f"UPDATE `{tgt_table}` SET imported = 1 WHERE allowed = 1")
api.perform_import(tbl_name=tgt_table)

api.cleanup()

