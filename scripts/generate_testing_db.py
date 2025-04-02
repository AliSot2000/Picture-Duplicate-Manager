# pragma: no cover

import os
import shutil

from photo_lib.new_photo_api import PhotoAPI


def setup_missing_and_present(api_internal: PhotoAPI, file_root: str):
    """
    Set up the database for missing and present files.

    :param api_internal: PhotoAPI that we want to prepare
    :param file_root: Root of the file we want to import (not needed for this function)
    """
    # Create missing files
    tgt_dir_1 = os.path.join(api_internal.root_path, "1990", "06", "01")

    # delete files
    for file in os.listdir(tgt_dir_1):
        os.remove(os.path.join(tgt_dir_1, file))

    # mark files as missing but are present
    tgt_dir_2 = os.path.join(api_internal.root_path, "1990", "05", "01")

    # delete files
    for file in os.listdir(tgt_dir_2):
        flags = api_internal.db.get_main_flags(api_internal.resolve_filename_to_key(file))

        flags.present = False

        api_internal.db.update_row_main_table(key=api_internal.resolve_filename_to_key(file), flags=flags)

    api_internal.check_presence()

def setup_matches(api_internal: PhotoAPI, file_root: str):
    """
    Set up the database for the matching of the import table.
    """
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
    os.remove(api_internal.resolve_key_to_path(api_internal.db.db_resolve_org_filename_to_keys(bmm2)[0]))
    os.remove(api_internal.resolve_key_to_path(api_internal.db.db_resolve_org_filename_to_keys(hmm1)[0]))

    # Preparing hash match trash
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(bmm4)[0])
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(hmm3)[0])
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(bmt2)[0])
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(hmt1)[0])

    # Preparing hash_match_duplicates
    par_key = api_internal.db.db_resolve_org_filename_to_keys(dup_target)[0]

    # Moving all hash match duplicates to trash
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(bmm6)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(hmm5)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(bmt4)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(hmt3)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(bmd2)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(hmd1)[0])

    # check size of trash as a shorthand for checking that all files are in the trash
    assert len(os.listdir(api_internal.db.get_trash_dir())) == 10, "Correct moving to duplicates"

    # empty trash, so the originals are gone
    api_internal.empty_trash()

    # Move all binary matches to trash
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(bmm3)[0])
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(hmm2)[0])
    api_internal.move_to_trash(key=api_internal.db.db_resolve_org_filename_to_keys(bmt1)[0])

    # Move all binary matches to duplicates
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(bmm5)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(hmm4)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(bmt3)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(hmt2)[0])
    api_internal.move_to_duplicates(parent_key=par_key,
                                    child_key=api_internal.db.db_resolve_org_filename_to_keys(bmd1)[0])

    # ======================================================================================================================
    import_source = os.path.abspath(
        os.path.join(file_root, "import_match_source"))

    api_internal.prepare_directory_for_import(import_source, tbl_name="import_test")
    api_internal.find_match_for_import_table(tbl_name="import_test")



def setup_hash_update(api_internal: PhotoAPI, file_root: str):
    """
    Copy the files into the database so we can detect the changed hashes
    """
    sf1 = os.path.join(file_root, "hash_change_1", "01_match_a_c1.png")
    sf2 = os.path.join(file_root, "hash_change_1", "02_match_a_c1.png")
    sf3 = os.path.join(file_root, "hash_change_1", "03_match_a_c1.png")

    # dst
    tf1 = api_internal.resolve_key_to_path(128)
    tf2 = api_internal.resolve_key_to_path(129)
    tf3 = api_internal.resolve_key_to_path(130)

    shutil.copy2(sf1, tf1)
    shutil.copy2(sf2, tf2)
    shutil.copy2(sf3, tf3)

    api_internal.check_file_hashes()


def setup_name_match(api_internal: PhotoAPI, file_root: str):
    """
    Set up the api for matching against names.
    """
    sf1 = os.path.join(file_root, "hash_change_1", "01_match_a_c1.png")
    sf2 = os.path.join(file_root, "hash_change_1", "02_match_a_c1.png")
    sf3 = os.path.join(file_root, "hash_change_1", "03_match_a_c1.png")

    # dst
    tf1 = api_internal.resolve_key_to_path(128)
    tf2 = api_internal.resolve_key_to_path(129)
    tf3 = api_internal.resolve_key_to_path(130)

    shutil.copy2(sf1, tf1)
    shutil.copy2(sf2, tf2)
    shutil.copy2(sf3, tf3)

    api_internal.check_file_hashes()
    api_internal.update_hash_from_filename_table()

    of1 = os.path.join(file_root, "db", "hash_matches", "01_match_a.png")
    of2 = os.path.join(file_root, "db", "hash_matches", "02_match_a.png")
    of3 = os.path.join(file_root, "db", "hash_matches", "03_match_a.png")

    # dst
    tf1 = api_internal.resolve_key_to_path(128)
    tf2 = api_internal.resolve_key_to_path(129)
    tf3 = api_internal.resolve_key_to_path(130)

    shutil.copy2(of1, tf1)
    shutil.copy2(of2, tf2)
    shutil.copy2(of3, tf3)

    os.rename(tf1, os.path.join(os.path.dirname(tf1), "unga.png"))
    os.rename(tf2, os.path.join(os.path.dirname(tf2), "bunga.png"))
    os.rename(tf3, os.path.join(os.path.dirname(tf3), "cavemanbrain.png"))

    dst_path = os.path.join(api_internal.root_path, "2025", "hash_matches")
    src_path = os.path.join(file_root, "import_match_source")

    os.makedirs(dst_path, exist_ok=True)

    for file in os.listdir(src_path):
        shutil.copy2(os.path.join(src_path, file), os.path.join(dst_path, "abs" + file))

    api_internal.check_filenames()

    # Mark one as failed
    api_internal.db.debug_execute("SELECT key FROM name_update_table WHERE name = 'unga.png'")
    key_1 = api_internal.db.sq_cur.fetchone()[0]
    api_internal.db.debug_execute("UPDATE name_update_table SET updated = 1 WHERE key = ?", (key_1,))

    # Mark one as success
    api_internal.db.debug_execute("SELECT key FROM name_update_table WHERE name = 'bunga.png'")
    key_2 = api_internal.db.sq_cur.fetchone()[0]
    api_internal.db.debug_execute("UPDATE name_update_table SET updated = 2 WHERE key = ?", (key_2,))


dummy_files = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..", "testing", "test_file_out"))


# Create a fresh instance
api = PhotoAPI(root_path=os.path.join(os.path.dirname(__file__),"testing_db"),
               init=True,
               init_loggers=True,
               opt_integrity_check=True)

tgt_table = api.prepare_directory_for_import(source_dir=os.path.join(dummy_files, "db"))
api.db.debug_execute(f"UPDATE `{tgt_table}` SET imported = 1 WHERE allowed = 1")
api.perform_import(tbl_name=tgt_table)


setup_missing_and_present(api, dummy_files)
setup_hash_update(api, file_root=dummy_files)
setup_name_match(api, file_root=dummy_files)


api.cleanup()

