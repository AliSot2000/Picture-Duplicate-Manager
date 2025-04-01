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


# ======================================================================================================================
# Create the data structure needed for testing import table creation
bmm1 = "11_Binary_Match_Main.png"
bmm2 = "12_Hash_Match_Main.png"
bmm3 = "13_Binary_Match_Trash.png"
bmm4 = "14_Hash_Match_Trash.png"
bmm5 = "15_Binary_Match_Duplicates.png"
bmm6 = "16_Hash_Match_Duplicates.png"

hmm1 = "21_Hash_Match_Main.png"
hmm2 = "22_Binary_Match_Trash.png"
hmm3 = "23_Hash_Match_Trash.png"
hmm4 = "24_Binary_Match_Duplicates.png"
hmm5 = "25_Hash_Match_Duplicates.png"

bmt1 = "31_Binary_Match_Trash.png"
bmt2 = "32_Hash_Match_Trash.png"
bmt3 = "33_Binary_Match_Duplicates.png"
bmt4 = "34_Hash_Match_Duplicates.png"

hmt1 = "41_Hash_Match_Trash.png"
hmt2 = "42_Binary_Match_Duplicates.png"
hmt3 = "43_Hash_Match_Duplicates.png"

bmd1 = "51_Binary_Match_Duplicates.png"
bmd2 = "52_Hash_Match_Duplicates.png"

hmd1 = "61_Hash_Match_Duplicates.png"

dup_target = "71_Duplicate_Target.png"

# All Hash matches in main need to be deleted
os.remove(api.resolve_key_to_path(api.db.db_resolve_org_filename_to_keys(bmm2)[0]))
os.remove(api.resolve_key_to_path(api.db.db_resolve_org_filename_to_keys(hmm1)[0]))

# Preparing hash match trash
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(bmm4)[0])
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(hmm3)[0])
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(bmt2)[0])
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(hmt1)[0])

# Preparing hash_match_duplicates
par_key = api.db.db_resolve_org_filename_to_keys(dup_target)[0]

# Moving all hash match duplicates to trash
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(bmm6)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(hmm5)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(bmt4)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(hmt3)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(bmd2)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(hmd1)[0])

# check size of trash as a shorthand for checking that all files are in the trash
assert len(os.listdir(api.db.get_trash_dir())) == 10, "Correct moving to duplicates"

# empty trash, so the originals are gone
api.empty_trash()

# Move all binary matches to trash
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(bmm3)[0])
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(hmm2)[0])
api.move_to_trash(key=api.db.db_resolve_org_filename_to_keys(bmt1)[0])


# Move all binary matches to duplicates
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(bmm5)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(hmm4)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(bmt3)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(hmt2)[0])
api.move_to_duplicates(parent_key=par_key,
                            child_key=api.db.db_resolve_org_filename_to_keys(bmd1)[0])

# ======================================================================================================================
import_source = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..", "testing", "test_file_out", "import_match_source"))

api.prepare_directory_for_import(import_source, tbl_name="import_test")
api.find_match_for_import_table(tbl_name="import_test")

api.cleanup()

