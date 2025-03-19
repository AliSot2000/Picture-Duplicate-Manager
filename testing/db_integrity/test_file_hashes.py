import json
import logging
import os.path
import shutil
from typing import List, Dict, Any

from base_class import TestDefaultBase
from photo_lib.custom_enum import SelectionType
from photo_lib.data_objects import Selection

"""
File contains functionality to test check_file_hashes and update_hash_from_filename_table

This file fully tests the following functions:
- api.prune_filesystem_directories
- api._internal_prune_fs_dir
- api.prune_db_dir
- api._internal_prune_db_dir
- api.db.prune_gps
- api.db.prune_hash
- api.prune_all
- api.db.selection_from_hash_update_table

The file covers 100% of the function without specific tests:
- api.db.dump_hash_update_table
- api.db.reset_selection
- api.db.hash_update_table_size
"""


wip = False


class HashUpdateBase(TestDefaultBase):
    """
    Class contains the setup methods. Needed for testing hash update functionality
    """
    def setup_hash_change_1(self):
        """
        Update the three hash files
        """
        sf1 = os.path.join(self.media_source, "hash_change_1", "01_match_a_c1.png")
        sf2 = os.path.join(self.media_source, "hash_change_1", "02_match_a_c1.png")
        sf3 = os.path.join(self.media_source, "hash_change_1", "03_match_a_c1.png")

        # dst
        tf1 = self.api.resolve_key_to_path(128)
        tf2 = self.api.resolve_key_to_path(129)
        tf3 = self.api.resolve_key_to_path(130)

        shutil.copy2(sf1, tf1)
        shutil.copy2(sf2, tf2)
        shutil.copy2(sf3, tf3)

    def setup_hash_change_2(self):
        """
        Update the three hash files
        """
        sf1 = os.path.join(self.media_source, "hash_change_2", "01_match_a_c2.png")
        sf2 = os.path.join(self.media_source, "hash_change_2", "02_match_a_c2.png")
        sf3 = os.path.join(self.media_source, "hash_change_2", "03_match_a_c2.png")

        # dst
        tf1 = self.api.resolve_key_to_path(128)
        tf2 = self.api.resolve_key_to_path(129)
        tf3 = self.api.resolve_key_to_path(130)

        shutil.copy2(sf1, tf1)
        shutil.copy2(sf2, tf2)
        shutil.copy2(sf3, tf3)

    def setup_hash_change_3(self):
        """
        Update the three hash files
        """
        sf1 = os.path.join(self.media_source, "hash_change_3", "01_match_a_c3.png")
        sf2 = os.path.join(self.media_source, "hash_change_3", "02_match_a_c3.png")
        sf3 = os.path.join(self.media_source, "hash_change_3", "03_match_a_c3.png")

        # dst
        tf1 = self.api.resolve_key_to_path(128)
        tf2 = self.api.resolve_key_to_path(129)
        tf3 = self.api.resolve_key_to_path(130)

        shutil.copy2(sf1, tf1)
        shutil.copy2(sf2, tf2)
        shutil.copy2(sf3, tf3)

    def check_hash_update_tbl_3(self):
        """
        Check the hash_update_table dump and assert is equal to our expectation
        """
        tbl_size = self.api.db.hash_update_table_size()
        self.assertEqual(3, tbl_size)

        tbl = self.api.db.dump_hash_update_table()
        expected_tbl = [
            {
                "main_key": 128,
                "new_hash": "77adee194b27ed04cbda01b42600dd6bd4dab1d75c188c28b33f33f9bed85b6b",
                "file_size_bytes": 42438
            },
            {
                "main_key": 129,
                "new_hash": "b7bca94d8c2a51f14de49379418b1e2f5c2003d5a32f7553dd5e1b2926bcfdc2",
                "file_size_bytes": 43025
            },
            {
                "main_key": 130,
                "new_hash": "9950a3d9360b1dbe6509dfdbd0922826e7fed1d973442fccd1efc12f33a33bd2",
                "file_size_bytes": 43097
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Change 3")
            print(json.dumps(tbl, indent=4))

        self.assertListEqual(tbl, expected_tbl)

    def check_hash_update_tbl_2(self):
        """
        Check the hash_update_table dump and assert is equal to our expectation
        """
        tbl_size = self.api.db.hash_update_table_size()
        self.assertEqual(3, tbl_size)

        tbl = self.api.db.dump_hash_update_table()
        expected_tbl = [
            {
                "main_key": 128,
                "new_hash": "22c190b51d4bd4e1647f2ddf8daed3336fa08b80efb6cf8cdf0ad6ebc8d92699",
                "file_size_bytes": 36491
            },
            {
                "main_key": 129,
                "new_hash": "00c6fed5b8cf63cc5b498a70c33b1c5d1733780dee15a8fa121c8ca8c4192bc8",
                "file_size_bytes": 36929
            },
            {
                "main_key": 130,
                "new_hash": "5865daa73a4fc9049136a47d08e57caefe0d3cc2d86d04ed3c20ea652e6ac264",
                "file_size_bytes": 36990
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Change 2")
            print(json.dumps(tbl, indent=4))

        self.assertListEqual(tbl, expected_tbl)

    def check_hash_update_tbl_1(self):
        """
        Check the hash_update_table dump and assert is equal to our expectation
        """
        tbl_size = self.api.db.hash_update_table_size()
        self.assertEqual(3, tbl_size)

        tbl = self.api.db.dump_hash_update_table()
        expected_tbl = [
            {
                "main_key": 128,
                "new_hash": "b007bcf5870829075a975a87ce0a7e6dff399959a9d412bb8d5d30355e68e065",
                "file_size_bytes": 31192
            },
            {
                "main_key": 129,
                "new_hash": "74ca94dce04467231bfcd8dee4cd0105dbdba23003ab93e55171a5cda7b4637f",
                "file_size_bytes": 31394
            },
            {
                "main_key": 130,
                "new_hash": "c12310f9e92bd9a481baae87e2ffa5e1c75865c3e7537407f1ebd7e4d0df1cae",
                "file_size_bytes": 31404
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Change 1")
            print(json.dumps(tbl, indent=4))

        self.assertListEqual(tbl, expected_tbl)

    def check_hash_update_empty(self):
        """
        Check the hash_update_table is empty
        """
        tbl_size = self.api.db.hash_update_table_size()
        self.assertEqual(0, tbl_size)

        tbl = self.api.db.dump_hash_update_table()
        expected_tbl = []

        if wip:  # pragma: no cover
            print("Empty Table")
            print(json.dumps(tbl, indent=4))

        self.assertListEqual(tbl, expected_tbl)

class TestCheckFileHashes(HashUpdateBase):
    """
    Fully test the update_hash_from_filename_table and update_hash_from_filename_table function
    """
    def check_hash_update_tbl_1_partial(self):
        """
        Check that we have a partial content
        """
        tbl_size = self.api.db.hash_update_table_size()
        self.assertEqual(2, tbl_size)

        tbl = self.api.db.dump_hash_update_table()
        expected_tbl = [
            {
                "main_key": 129,
                "new_hash": "74ca94dce04467231bfcd8dee4cd0105dbdba23003ab93e55171a5cda7b4637f",
                "file_size_bytes": 31394
            },
            {
                "main_key": 130,
                "new_hash": "c12310f9e92bd9a481baae87e2ffa5e1c75865c3e7537407f1ebd7e4d0df1cae",
                "file_size_bytes": 31404
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Change 1 Partial")
            print(json.dumps(tbl, indent=4))

        self.assertListEqual(tbl, expected_tbl)

    def test_no_op(self):
        """
        Test that we don't have anything if we just run the function
        """
        count = self.api.check_file_hashes()
        self.assertEqual(count, 0)

        self.check_hash_update_empty()

    def test_add_change_1(self):
        """
        Check that changes are detected correctly
        """
        self.setup_hash_change_1()

        count = self.api.check_file_hashes()
        self.assertEqual(count, 3)

        self.check_hash_update_tbl_1()

    def test_add_change_2(self):
        """
        Check that changes are detected correctly
        """
        self.setup_hash_change_2()

        count = self.api.check_file_hashes()
        self.assertEqual(count, 3)

        self.check_hash_update_tbl_2()

    def test_add_change_3(self):
        """
        Check that changes are detected correctly
        """
        self.setup_hash_change_3()

        count = self.api.check_file_hashes()
        self.assertEqual(count, 3)

        self.check_hash_update_tbl_3()

    def test_empty_select(self):
        """
        Test the selection influence on update
        """
        self.setup_hash_change_1()

        # set custom target directory
        target_dir = os.path.join(self.api.root_path, "1990", "04", "01")
        for file in os.listdir(target_dir):
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        count = self.api.check_file_hashes(selection=Selection(selection_type=SelectionType.SELECTION_A))
        self.assertEqual(count, 0)

    def test_partial_intersection(self):
        """
        Check the selection works correctly such that we get a partial result.
        """
        self.setup_hash_change_1()

        # set custom target directory
        target_dir = os.path.join(self.api.root_path, "1990", "04", "01")
        for file in os.listdir(target_dir):
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        for key in (129, 130):
            flags = self.api.db.get_main_flags(key)

            flags.sel_a = True
            self.api.db.update_row_main_table(key=key, flags=flags)

        count = self.api.check_file_hashes(selection=Selection(selection_type=SelectionType.SELECTION_A))
        self.assertEqual(count, 2)
        self.check_hash_update_tbl_1_partial()

    def test_missing_file(self):
        """
        Remove an entire directory to check branch continue
        """
        # set custom target directory
        target_dir = os.path.join(self.api.root_path, "1990", "04", "01")
        for file in os.listdir(target_dir):
            os.remove(os.path.join(target_dir, file))

        count = self.api.check_file_hashes()

        self.assertEqual(0, count)

        self.check_hash_update_empty()

    def test_delete_row(self):
        """
        Test delete row in the db
        """
        self.setup_hash_change_1()

        count = self.api.check_file_hashes()
        self.assertEqual(3, count)

        self.api.db.delete_row_hash_update_table(128)

        self.check_hash_update_tbl_1_partial()

    def test_rare_occurrence_logger(self):
        """
        Test the rare occurrence is
        """
        # Update the row of file 1 in the hash assoz table to have a different file size
        self.api.db.debug_execute("UPDATE hash_assoz SET file_size_bytes = 5 WHERE hash_key = 1 AND file_key = 1")

        with self.assertLogs(self.api.rare_occurrence_logger, level=logging.WARNING):
            self.api.check_file_hashes()


class TestUpdateHashFromFilenameTable(HashUpdateBase):
    """
    Test applying hash increment.
    """
    def check_initial_table_dump(self):
        """
        Check the initial state of the hash_assoz_table and the hashes_table
        """
        assoz_table_dump = self.api.db.dump_hash_assoz_table()
        if wip:  # pragma: no cover
            print("Initial Assoz Table Dump")
            print(json.dumps(assoz_table_dump, indent=4))

        expected_assoz_dump = self.load_dump_from_file("initial_assoz_dump.json")
        san_expected_assoz_dump = self.drop_unpredictable_col(expected_assoz_dump, ["hash_date"])

        self.assertEqual(len(assoz_table_dump), len(expected_assoz_dump))
        for row in self.drop_unpredictable_col(assoz_table_dump, ["hash_date"]):
            self.assertIn(row, san_expected_assoz_dump)

        hash_table_dump = self.api.db.dump_hashes_table()
        if wip:  # pragma: no cover
            print("Initial Hash Table Dump")
            print(json.dumps(hash_table_dump, indent=4))

        expected_hash_dump = self.load_dump_from_file("initial_hash_dump.json")

        self.assertEqual(len(hash_table_dump), len(expected_hash_dump))
        for row in hash_table_dump:
            self.assertIn(row, expected_hash_dump)

    def check_change_1_dump(self):
        """
        Check the initial state of the hash_assoz_table and the hashes_table after the first set of changes
        """
        assoz_table_dump = self.api.db.dump_hash_assoz_table()
        if wip:  # pragma: no cover
            print("Change 1 Assoz Table Dump")
            print(json.dumps(assoz_table_dump, indent=4))

        expected_assoz_dump = self.load_dump_from_file("change_1_assoz_dump.json")
        san_expected_assoz_dump = self.drop_unpredictable_col(expected_assoz_dump, ["hash_date"])

        self.assertEqual(len(assoz_table_dump), len(expected_assoz_dump))
        for row in self.drop_unpredictable_col(assoz_table_dump, ["hash_date"]):
            self.assertIn(row, san_expected_assoz_dump)

        hash_table_dump = self.api.db.dump_hashes_table()
        if wip:  # pragma: no cover
            print("Change 1 Hash Table Dump")
            print(json.dumps(hash_table_dump, indent=4))

        expected_hash_dump = self.load_dump_from_file("change_1_hash_dump.json")


        self.assertEqual(len(hash_table_dump), len(expected_hash_dump))
        for row in hash_table_dump:
            self.assertIn(row, expected_hash_dump)

    def check_change_2_dump(self):
        """
        Check the initial state of the hash_assoz_table and the hashes_table after the second set of changes
        """
        assoz_table_dump = self.api.db.dump_hash_assoz_table()
        if wip:  # pragma: no cover
            print("Change 2 Assoz Table Dump")
            print(json.dumps(assoz_table_dump, indent=4))

        expected_assoz_dump = self.load_dump_from_file("change_2_assoz_dump.json")
        san_expected_assoz_dump = self.drop_unpredictable_col(expected_assoz_dump, ["hash_date"])

        self.assertEqual(len(assoz_table_dump), len(expected_assoz_dump))
        for row in self.drop_unpredictable_col(assoz_table_dump, ["hash_date"]):
            self.assertIn(row, san_expected_assoz_dump)

        hash_table_dump = self.api.db.dump_hashes_table()
        if wip:  # pragma: no cover
            print("Change 2 Hash Table Dump")
            print(json.dumps(hash_table_dump, indent=4))

        expected_hash_dump = self.load_dump_from_file("change_2_hash_dump.json")

        self.assertEqual(len(hash_table_dump), len(expected_hash_dump))
        for row in hash_table_dump:
            self.assertIn(row, expected_hash_dump)

    def check_change_3_dump(self):
        """
        Check the initial state of the hash_assoz_table and the hashes_table after the second set of changes
        """
        assoz_table_dump = self.api.db.dump_hash_assoz_table()
        if wip:  # pragma: no cover
            print("Change 3 Assoz Table Dump")
            print(json.dumps(assoz_table_dump, indent=4))

        expected_assoz_dump = self.load_dump_from_file("change_3_assoz_dump.json")
        san_expected_assoz_dump = self.drop_unpredictable_col(expected_assoz_dump, ["hash_date"])

        self.assertEqual(len(assoz_table_dump), len(expected_assoz_dump))
        for row in self.drop_unpredictable_col(assoz_table_dump, ["hash_date"]):
            self.assertIn(row, san_expected_assoz_dump)

        hash_table_dump = self.api.db.dump_hashes_table()
        if wip:  # pragma: no cover
            print("Change 3 Hash Table Dump")
            print(json.dumps(hash_table_dump, indent=4))

        expected_hash_dump = self.load_dump_from_file("change_3_hash_dump.json")

        self.assertEqual(len(hash_table_dump), len(expected_hash_dump))
        for row in hash_table_dump:
            self.assertIn(row, expected_hash_dump)

    def load_dump_from_file(self, file: str) -> List[Dict[str, Any]]:
        """
        Load dump from file and return object

        :param file: filename of dump in the tbl_dump_dir

        :returns:
        """
        fp = os.path.join(self.tbl_dump_dir, "hash_update",  file)
        with open(fp, 'r') as f:
            return json.load(f)

    @staticmethod
    def drop_unpredictable_col(tgt: List[Dict[str, Any]], col_name: List[str]):
        """
        Drop a given column from a table dump

        :param tgt: Table dump to clean
        :param col_name: Name of column to drop
        """
        for row in tgt:
            for col in col_name:
                row.pop(col)

        return tgt

    def test_raises_error(self):
        """
        Test ValueError is raised if table is empty
        """
        self.api.db.clear_hash_update_table()
        self.assertRaises(ValueError, self.api.update_hash_from_filename_table)

    def test_no_apply(self):
        """
        Test empty hash update
        """
        res = self.api.check_file_hashes()
        self.assertEqual(0, res)

        self.check_hash_update_empty()
        self.check_initial_table_dump()

    def test_apply_all(self):
        """
        Check the updates upon applying all changes
        """
        # Setup and check initial state
        self.setup_hash_change_1()
        self.check_hash_update_empty()
        self.check_initial_table_dump()

        # Perform check and assert table changes
        count1 = self.api.check_file_hashes()
        self.assertEqual(count1, 3)
        self.check_hash_update_tbl_1()

        # Perform update
        added, modifies = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)
        self.check_change_1_dump()

        # --------------------------------------------------------------------------------------------------------------

        # Clear the table and check empty
        self.api.db.clear_hash_update_table()
        self.setup_hash_change_2()
        self.check_hash_update_empty()

        # Perform second search and assert changes
        count2 = self.api.check_file_hashes()
        self.assertEqual(count2, 3)
        self.check_hash_update_tbl_2()
        self.check_change_1_dump()

        # perform update
        added, modified = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)
        self.check_change_2_dump()

        # --------------------------------------------------------------------------------------------------------------

        #  Clear the table and check empty
        self.api.db.clear_hash_update_table()
        self.setup_hash_change_3()
        self.check_hash_update_empty()

        # Perform third search and assert changes
        count3 = self.api.check_file_hashes()
        self.assertEqual(count3, 3)
        self.check_hash_update_tbl_3()
        self.check_change_2_dump()

        # perform update
        added, modified = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)
        self.check_change_3_dump()

    def test_set_selection_from_update_table(self):
        """
        Test that the selection flag is correctly set from the hash_update_table
        """
        # Setup and check initial state
        self.setup_hash_change_1()
        self.check_hash_update_empty()
        self.check_initial_table_dump()

        # Perform check and assert table changes
        count1 = self.api.check_file_hashes()
        self.assertEqual(count1, 3)
        self.check_hash_update_tbl_1()

        # Perform update
        added, modifies = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)
        self.check_change_1_dump()

        count = self.api.db.selection_from_hash_update_table(True)
        self.assertEqual(count, 3)

        for key, flag in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key in (128, 129, 130):
                self.assertTrue(flag.sel_a)
                self.assertFalse(flag.sel_b)

            else:
                self.assertFalse(flag.sel_a)
                self.assertFalse(flag.sel_b)

        # Reset selection
        count = self.api.db.reset_selection(sel_a=True)
        self.assertEqual(count, 3)

        # Test selection is reset
        for key, flag in self.api.db.main_key_flags_iterator(allow_selection=False):
            self.assertFalse(flag.sel_a)
            self.assertFalse(flag.sel_b)

        count = self.api.db.selection_from_hash_update_table(False)
        self.assertEqual(count, 3)

        for key, flag in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key in (128, 129, 130):
                self.assertFalse(flag.sel_a)
                self.assertTrue(flag.sel_b)

            else:
                self.assertFalse(flag.sel_a)
                self.assertFalse(flag.sel_b)

        # Reset selection
        count = self.api.db.reset_selection(sel_a=False)
        self.assertEqual(count, 3)

        # Test selection is reset
        for key, flag in self.api.db.main_key_flags_iterator(allow_selection=False):
            self.assertFalse(flag.sel_a)
            self.assertFalse(flag.sel_b)