import json
import shutil

from db_integrity.test_file_hashes import HashUpdateBase
import os

from photo_lib.errors_and_warnings import ImplementationError

wip = False


"""
Fully test the update the filenames given file hashes functionality

This file fully tests the following functions:
- api.check_filenames
- api.update_filename_from_hash

The file covers 100% of the function without specific tests:

"""


class FixFilenameBase(HashUpdateBase):
    """
    Contains all necessary setup and util functions for testing
    """
    bmm1: str = ""
    bmm2: str = ""
    bmm3: str = ""
    bmm4: str = ""
    bmm5: str = ""
    bmm6: str = ""

    hmm1: str = ""
    hmm2: str = ""
    hmm3: str = ""
    hmm4: str = ""
    hmm5: str = ""

    bmt1: str = ""
    bmt2: str = ""
    bmt3: str = ""
    bmt4: str = ""

    hmt1: str = ""
    hmt2: str = ""
    hmt3: str = ""

    bmd1: str = ""
    bmd2: str = ""

    hmd1: str = ""

    dup_target: str = ""

    def setUp(self):
        super().setUp()
        self.api.config.batch_size = 2

        self.bmm1 = "11_Binary_Match_Main.png"
        self.bmm2 = "12_Hash_Match_Main.png"
        self.bmm3 = "13_Binary_Match_Trash.png"
        self.bmm4 = "14_Hash_Match_Trash.png"
        self.bmm5 = "15_Binary_Match_Duplicates.png"
        self.bmm6 = "16_Hash_Match_Duplicates.png"

        self.hmm1 = "21_Hash_Match_Main.png"
        self.hmm2 = "22_Binary_Match_Trash.png"
        self.hmm3 = "23_Hash_Match_Trash.png"
        self.hmm4 = "24_Binary_Match_Duplicates.png"
        self.hmm5 = "25_Hash_Match_Duplicates.png"

        self.bmt1 = "31_Binary_Match_Trash.png"
        self.bmt2 = "32_Hash_Match_Trash.png"
        self.bmt3 = "33_Binary_Match_Duplicates.png"
        self.bmt4 = "34_Hash_Match_Duplicates.png"

        self.hmt1 = "41_Hash_Match_Trash.png"
        self.hmt2 = "42_Binary_Match_Duplicates.png"
        self.hmt3 = "43_Hash_Match_Duplicates.png"

        self.bmd1 = "51_Binary_Match_Duplicates.png"
        self.bmd2 = "52_Hash_Match_Duplicates.png"

        self.hmd1 = "61_Hash_Match_Duplicates.png"

        self.dup_target = "71_Duplicate_Target.png"

        # All Hash matches in main need to be deleted
        os.remove(self.api.resolve_key_to_path(self.api.db.db_resolve_org_filename_to_keys(self.bmm2)[0]))
        os.remove(self.api.resolve_key_to_path(self.api.db.db_resolve_org_filename_to_keys(self.hmm1)[0]))

        # Preparing hash match trash
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.bmm4)[0])
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.hmm3)[0])
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.bmt2)[0])
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.hmt1)[0])

        # Preparing hash_match_duplicates
        par_key = self.api.db.db_resolve_org_filename_to_keys(self.dup_target)[0]

        # Moving all hash match duplicates to trash
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.bmm6)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.hmm5)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.bmt4)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.hmt3)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.bmd2)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.hmd1)[0])

        # check size of trash as a shorthand for checking that all files are in the trash
        self.assertEqual(len(os.listdir(self.api.db.get_trash_dir())), 10)

        # empty trash, so the originals are gone
        self.api.empty_trash()

        # Move all binary matches to trash
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.bmm3)[0])
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.hmm2)[0])
        self.api.move_to_trash(key=self.api.db.db_resolve_org_filename_to_keys(self.bmt1)[0])

        # Move all binary matches to duplicates
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.bmm5)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.hmm4)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.bmt3)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.hmt2)[0])
        self.api.move_to_duplicates(parent_key=par_key,
                                    child_key=self.api.db.db_resolve_org_filename_to_keys(self.bmd1)[0])

    def check_empty_name_update_table(self):
        """
        Test the update table is empty
        """
        tbl = self.api.db.dump_name_update_table()
        self.assertListEqual(tbl, [])

    def check_import_match_table(self):
        """
        Check that the given name update table matches our expectation for what we have for the match files
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "10_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 27523,
                "hash": "65725b932e0c81c0e659ac5cf63d08791fe5aa2bb00f9321f030d93c22fe5e97",
                "matches": "{\"136\": 1, \"137\": 2, \"138\": 3, \"139\": 4, \"140\": 5, \"141\": 6}",
                "best_match": 136,
                "match_type": 1,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "20_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 26077,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1",
                "matches": "{\"142\": 2, \"143\": 3, \"144\": 4, \"145\": 5, \"146\": 6}",
                "best_match": 142,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "30_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 27051,
                "hash": "a98a68b6f5d0a35a748fa4e7220a21192c10d7f4f173bbf687c3b4030f2f3d94",
                "matches": "{\"147\": 3, \"148\": 4, \"149\": 5, \"150\": 6}",
                "best_match": 147,
                "match_type": 3,
                "updated": 0,
                "message": None
            },
            {
                "key": 4,
                "name": "40_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25590,
                "hash": "86bf066c72393325509562d3c93bd47524f8e11979da1339c86c3192a5bca5ad",
                "matches": "{\"151\": 4, \"152\": 5, \"153\": 6}",
                "best_match": 151,
                "match_type": 4,
                "updated": 0,
                "message": None
            },
            {
                "key": 5,
                "name": "50_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 30749,
                "hash": "f8828518c0ad926a3536e9dff79133368999626f5dc5800bf2340fd1aee7637a",
                "matches": "{\"154\": 5, \"155\": 6}",
                "best_match": 154,
                "match_type": 5,
                "updated": 0,
                "message": None
            },
            {
                "key": 6,
                "name": "60_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 29439,
                "hash": "808ce20368e8a7c463fcb1e75ba57e6955372a4f3028450526f884c55fb3c72c",
                "matches": "{\"156\": 6}",
                "best_match": 156,
                "match_type": 6,
                "updated": 0,
                "message": None
            },
            {
                "key": 7,
                "name": "81_No_Match.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 42798,
                "hash": "9b9e0c5b46c73cedf092524e29828de87a0e60bdf21c893493087186d6d58d44",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 8,
                "name": "81_No_Match.pvl",
                "dir_name": "2025/03/19",
                "file_size_bytes": 42798,
                "hash": "9b9e0c5b46c73cedf092524e29828de87a0e60bdf21c893493087186d6d58d44",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Import Match TBL Dump")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_empty_match_initial(self):
        """
        Check the tables which don't contain a match for the initial
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25932,
                "hash": "352fe77d3340c06f37987696113d57811b32f6db782b1cac973f8e1c68c93e57",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25932,
                "hash": "e6138ca6b0d879584d019e1d5633f24ffde3d214fc35d0022db2c5b7c6ee6ff7",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25932,
                "hash": "bb9d4d7d1e53d8a8efc594ba5a4ffbf9a7f61d6e93bb0b86ae3163fc26739b7a",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Match Initial Empty Match")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_empty_change_1(self):
        """
        Check the tables which don't contain a match for the initial
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a_c1.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 31192,
                "hash": "b007bcf5870829075a975a87ce0a7e6dff399959a9d412bb8d5d30355e68e065",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a_c1.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 31394,
                "hash": "74ca94dce04467231bfcd8dee4cd0105dbdba23003ab93e55171a5cda7b4637f",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a_c1.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 31404,
                "hash": "c12310f9e92bd9a481baae87e2ffa5e1c75865c3e7537407f1ebd7e4d0df1cae",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Match Change 1 Empty Match")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_empty_change_2(self):
        """
        Check the tables which don't contain a match for the initial
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a_c2.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 36491,
                "hash": "22c190b51d4bd4e1647f2ddf8daed3336fa08b80efb6cf8cdf0ad6ebc8d92699",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a_c2.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 36929,
                "hash": "00c6fed5b8cf63cc5b498a70c33b1c5d1733780dee15a8fa121c8ca8c4192bc8",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a_c2.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 36990,
                "hash": "5865daa73a4fc9049136a47d08e57caefe0d3cc2d86d04ed3c20ea652e6ac264",
                "matches": "{}",
                "best_match": None,
                "match_type": 0,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Hash Match Change 2 Empty Match")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_initial(self):
        """
        Check the hash table is correct, if we want to match the initial files.
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25932,
                "hash": "352fe77d3340c06f37987696113d57811b32f6db782b1cac973f8e1c68c93e57",
                "matches": "{\"128\": 2, \"129\": 2, \"130\": 2}",
                "best_match": 128,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25932,
                "hash": "e6138ca6b0d879584d019e1d5633f24ffde3d214fc35d0022db2c5b7c6ee6ff7",
                "matches": "{\"128\": 2, \"129\": 2, \"130\": 2}",
                "best_match": 128,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 25932,
                "hash": "bb9d4d7d1e53d8a8efc594ba5a4ffbf9a7f61d6e93bb0b86ae3163fc26739b7a",
                "matches": "{\"128\": 2, \"129\": 2, \"130\": 2}",
                "best_match": 128,
                "match_type": 2,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Import Match Hash Initial Dump")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_change_1(self):
        """
        Check the hash table is correct, if we want to match the change 1 files.
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a_c1.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 31192,
                "hash": "b007bcf5870829075a975a87ce0a7e6dff399959a9d412bb8d5d30355e68e065",
                "matches": "{\"128\": 2}",
                "best_match": 128,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a_c1.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 31394,
                "hash": "74ca94dce04467231bfcd8dee4cd0105dbdba23003ab93e55171a5cda7b4637f",
                "matches": "{\"129\": 2}",
                "best_match": 129,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a_c1.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 31404,
                "hash": "c12310f9e92bd9a481baae87e2ffa5e1c75865c3e7537407f1ebd7e4d0df1cae",
                "matches": "{\"130\": 2}",
                "best_match": 130,
                "match_type": 2,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Import Match Hash Change 1 Dump")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_change_2(self):
        """
        Check the hash table is correct, if we want to match the change 2 files.
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a_c2.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 36491,
                "hash": "22c190b51d4bd4e1647f2ddf8daed3336fa08b80efb6cf8cdf0ad6ebc8d92699",
                "matches": "{\"128\": 2}",
                "best_match": 128,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a_c2.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 36929,
                "hash": "00c6fed5b8cf63cc5b498a70c33b1c5d1733780dee15a8fa121c8ca8c4192bc8",
                "matches": "{\"129\": 2}",
                "best_match": 129,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a_c2.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 36990,
                "hash": "5865daa73a4fc9049136a47d08e57caefe0d3cc2d86d04ed3c20ea652e6ac264",
                "matches": "{\"130\": 2}",
                "best_match": 130,
                "match_type": 2,
                "updated": 0,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Import Match Hash Change 2 Dump")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def check_table_hash_change_3(self):
        """
        Check the hash table is correct, if we want to match the change 3 files.
        """
        tbl = self.api.db.dump_name_update_table()
        expected_tbl = [
            {
                "key": 1,
                "name": "01_match_a_c3.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 42438,
                "hash": "77adee194b27ed04cbda01b42600dd6bd4dab1d75c188c28b33f33f9bed85b6b",
                "matches": "{\"128\": 2}",
                "best_match": 128,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 2,
                "name": "02_match_a_c3.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 43025,
                "hash": "b7bca94d8c2a51f14de49379418b1e2f5c2003d5a32f7553dd5e1b2926bcfdc2",
                "matches": "{\"129\": 2}",
                "best_match": 129,
                "match_type": 2,
                "updated": 0,
                "message": None
            },
            {
                "key": 3,
                "name": "03_match_a_c3.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 43097,
                "hash": "9950a3d9360b1dbe6509dfdbd0922826e7fed1d973442fccd1efc12f33a33bd2",
                "matches": "{\"130\": 2}",
                "best_match": 130,
                "match_type": 2,
                "updated": 0,
                "message": None
            }
        ]
        
        if wip:  # pragma: no cover
            print("Import Match Hash Change 3 Dump")
            print(json.dumps(tbl, indent=4))

        self.assertEqual(len(tbl), len(expected_tbl))
        for row in tbl:
            self.assertIn(row, expected_tbl)

    def setup_hash_history(self):
        """
        Set up the history of hashes for the specific hashes
        """
        # Setup and check initial state
        self.setup_hash_change_1()
        self.check_hash_update_empty()

        # Perform check and assert table changes
        count1 = self.api.check_file_hashes()
        self.assertEqual(count1, 3)
        self.check_hash_update_tbl_1()

        # Perform update
        added, modifies = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)

        # --------------------------------------------------------------------------------------------------------------

        # Clear the table and check empty
        self.api.db.clear_hash_update_table()
        self.setup_hash_change_2()
        self.check_hash_update_empty()

        # Perform second search and assert changes
        count2 = self.api.check_file_hashes()
        self.assertEqual(count2, 3)
        self.check_hash_update_tbl_2()

        # perform update
        added, modified = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)

        # --------------------------------------------------------------------------------------------------------------

        #  Clear the table and check empty
        self.api.db.clear_hash_update_table()
        self.setup_hash_change_3()
        self.check_hash_update_empty()

        # Perform third search and assert changes
        count3 = self.api.check_file_hashes()
        self.assertEqual(count3, 3)
        self.check_hash_update_tbl_3()

        # perform update
        added, modified = self.api.update_hash_from_filename_table()
        self.assertEqual(added, 3)
        self.assertEqual(modifies, 0)


class TestCheckFilenames(FixFilenameBase):
    """
    Fully test the check_filenames function.
    """
    def test_empty(self):
        """
        Check correct exit if no changes were made
        """
        self.assertEqual(self.api.check_filenames(), 0)
        self.check_empty_name_update_table()

    def test_rename_all_match_files(self):
        """
        Check that it correctly matches up all files with the ones in the ones from the match test
        """
        # copy all files form import source into the main table
        base_dir = os.path.join(self.media_source, "import_match_source")
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")

        # copy into database
        shutil.copytree(base_dir, tgt_dir)

        self.assertEqual(self.api.check_filenames(), 8)

        self.check_import_match_table()

    def test_match_initial_any(self):
        """
        Test that the match works for the initial hash
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "db", "hash_matches")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=False)
        self.assertEqual(count, 3)

        self.check_table_hash_initial()

    def test_match_change_1_any(self):
        """
        Test that the match works for the change 1 hashes
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "hash_change_1")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=False)
        self.assertEqual(count, 3)

        self.check_table_hash_change_1()

    def test_match_change_2_any(self):
        """
        Test that the match works for the change 2 hashes
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "hash_change_2")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=False)
        self.assertEqual(count, 3)

        self.check_table_hash_change_2()

    def test_match_change_3_any(self):
        """
        Test that the match works for the change 3 hashes
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "hash_change_3")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(False)
        self.assertEqual(count, 3)

        self.check_table_hash_change_3()

    def test_match_initial_latest(self):
        """
        Test that the match works for the initial hash; shouldn't match
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "db", "hash_matches")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=True)
        self.assertEqual(count, 3)

        self.check_table_hash_empty_match_initial()

    def test_match_change_1_latest(self):
        """
        Test that the match works for the change 1 hashes; shouldn't match
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "hash_change_1")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=True)
        self.assertEqual(count, 3)

        self.check_table_hash_empty_change_1()

    def test_match_change_2_latest(self):
        """
        Test that the match works for the change 2 hashes; shouldn't match
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "hash_change_2")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=True)
        self.assertEqual(count, 3)

        self.check_table_hash_empty_change_2()

    def test_match_change_3_latest(self):
        """
        Test that the match works for the change 3 hashes; shouldn't match
        """
        self.setup_hash_history()

        # Remove the files
        os.remove(self.api.resolve_key_to_path(128))
        os.remove(self.api.resolve_key_to_path(129))
        os.remove(self.api.resolve_key_to_path(130))

        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(128)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(129)))
        self.assertFalse(os.path.exists(self.api.resolve_key_to_path(130)))

        # copy initial into the db
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")
        source_dir = os.path.join(self.media_source, "hash_change_3")
        shutil.copytree(source_dir, tgt_dir)

        count = self.api.check_filenames(only_latest=True)
        self.assertEqual(count, 3)

        self.check_table_hash_change_3()


class TestUpdateFilenameFromHash(FixFilenameBase):
    """
    Fully test update_filename_from_hash
    """
    def clear_table_to_only_allowed(self):
        """
        Clear all rows which aren't of the correct match type
        """
        self.api.db.debug_execute("DELETE FROM name_update_table WHERE match_type IS NOT 2")

    def setup_base(self):
        """
        Prepare the directory for the matching
        """
        # copy all files form import source into the main table
        base_dir = os.path.join(self.media_source, "import_match_source")
        tgt_dir = os.path.join(self.api.root_path, "2025", "03", "19")

        # copy into database
        shutil.copytree(base_dir, tgt_dir)

        self.assertEqual(self.api.check_filenames(), 8)

        self.check_import_match_table()

    def test_correct_number_of_files_available(self):
        """
        Test that exactly one file is eligible for update (namely the one which has a hash match main)
        """
        self.setup_base()

        self.assertEqual(self.api.db.get_update_filename_from_hash_iterator_size(), 1)

    def test_tgt_path_missing(self):
        """
        Test that the row is correctly updated if the target doesn't exist.
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Remove the matched key
        self.api.db.delete_row_main_table(142)

        # Check nothing was updated
        correct, conflict = self.api.update_filename_from_hash(False)
        self.assertEqual(correct, 0)
        self.assertEqual(conflict, 1)

        tbl_dump = self.api.db.dump_name_update_table()
        expected_dump = [
            {
                "key": 2,
                "name": "20_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 26077,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1",
                "matches": "{\"142\": 2, \"143\": 3, \"144\": 4, \"145\": 5, \"146\": 6}",
                "best_match": 142,
                "match_type": 2,
                "updated": 2,
                "message": "Matched key doesn't exist in main table"
            }
        ]

        if wip:  # pragma: no cover
            print("Target Path Missing Table Dump")
            print(json.dumps(tbl_dump, indent=4))

        self.assertEqual(len(tbl_dump), len(expected_dump))
        for row in tbl_dump:
            self.assertIn(row, expected_dump)

    def test_tgt_path_exists(self):
        """
        Test that the row is correctly updated if the target path for some reason exists.
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Create file for conflict
        with open(self.api.resolve_key_to_path(142), "w") as f:
            f.write("Hello World")

        # Check nothing was updated
        correct, conflict = self.api.update_filename_from_hash(False)
        self.assertEqual(correct, 0)
        self.assertEqual(conflict, 1)

        tbl_dump = self.api.db.dump_name_update_table()
        expected_dump = [
            {
                "key": 2,
                "name": "20_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 26077,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1",
                "matches": "{\"142\": 2, \"143\": 3, \"144\": 4, \"145\": 5, \"146\": 6}",
                "best_match": 142,
                "match_type": 2,
                "updated": 2,
                "message": "Parent File is Present"
            }
        ]

        if wip:  # pragma: no cover
            print("Target Path Exists Table Dump")
            print(json.dumps(tbl_dump, indent=4))

        self.assertEqual(len(tbl_dump), len(expected_dump))
        for row in tbl_dump:
            self.assertIn(row, expected_dump)

    def test_target_file_exists(self):
        """
        Check that the file also doesn't exist in the current directory
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Create file for conflict
        name = os.path.basename(self.api.resolve_key_to_path(142))
        with open(os.path.join(self.api.root_path, "2025", "03", "19", name), "w") as f:
            f.write("Hello World")

        # Check nothing was updated
        correct, conflict = self.api.update_filename_from_hash(False)
        self.assertEqual(correct, 0)
        self.assertEqual(conflict, 1)

        tbl_dump = self.api.db.dump_name_update_table()
        expected_dump = [
            {
                "key": 2,
                "name": "20_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 26077,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1",
                "matches": "{\"142\": 2, \"143\": 3, \"144\": 4, \"145\": 5, \"146\": 6}",
                "best_match": 142,
                "match_type": 2,
                "updated": 2,
                "message": "Filename exists at alterior location"
            }
        ]

        if wip:  # pragma: no cover
            print("Target Path Exists Table Dump")
            print(json.dumps(tbl_dump, indent=4))

        self.assertEqual(len(tbl_dump), len(expected_dump))
        for row in tbl_dump:
            self.assertIn(row, expected_dump)

    def test_parent_in_trash(self):
        """
        Check the error if the parent is marked as trashed
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Get flags and update them
        flags = self.api.db.get_main_flags(142)
        flags.trashed = True
        self.api.db.update_row_main_table(key=142, flags=flags)

        # Check error caught
        self.assertRaises(ImplementationError, lambda : self.api.update_filename_from_hash(False))

    def test_parent_in_duplicates(self):
        """
        Check the error if the parent is marked as duplicate
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Get flags and update them
        flags = self.api.db.get_main_flags(142)
        flags.trashed = True
        self.api.db.update_row_main_table(key=142, flags=flags)

        # Check error caught
        self.assertRaises(ImplementationError, lambda: self.api.update_filename_from_hash(False))

    def test_update_success_with_move(self):
        """
        Test correct update with move operation
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Check parent isn't marked as present
        mr = self.api.db.get_main_row(142)
        self.assertIsNotNone(mr)
        mr.flags.present = False
        self.api.db.update_row_main_table(key=142, flags=mr.flags)

        # Check the main row flags
        self.assertFalse(mr.flags.present)

        # Check nothing was updated
        correct, conflict = self.api.update_filename_from_hash(True)
        self.assertEqual(correct, 1)
        self.assertEqual(conflict, 0)

        tbl_dump = self.api.db.dump_name_update_table()
        expected_dump = [
            {
                "key": 2,
                "name": "20_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 26077,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1",
                "matches": "{\"142\": 2, \"143\": 3, \"144\": 4, \"145\": 5, \"146\": 6}",
                "best_match": 142,
                "match_type": 2,
                "updated": 1,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Target Path Exists Table Dump")
            print(json.dumps(tbl_dump, indent=4))

        self.assertEqual(len(tbl_dump), len(expected_dump))
        for row in tbl_dump:
            self.assertIn(row, expected_dump)

        mr = self.api.db.get_main_row(142)
        self.assertIsNotNone(mr)

        # Check the main row flags
        self.assertTrue(mr.flags.present)

        # Check dir table is empty
        self.assertListEqual([], self.api.db.dump_db_dir_table())

    def test_update_success_without_move(self):
        """
        Test correct update without move operation
        """
        self.setup_base()

        self.clear_table_to_only_allowed()

        # Check parent isn't marked as present
        mr = self.api.db.get_main_row(142)
        self.assertIsNotNone(mr)
        mr.flags.present = False
        self.api.db.update_row_main_table(key=142, flags=mr.flags)

        # Check nothing was updated
        correct, conflict = self.api.update_filename_from_hash(False)
        self.assertEqual(correct, 1)
        self.assertEqual(conflict, 0)

        tbl_dump = self.api.db.dump_name_update_table()
        expected_dump = [
            {
                "key": 2,
                "name": "20_Matching_Source.png",
                "dir_name": "2025/03/19",
                "file_size_bytes": 26077,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1",
                "matches": "{\"142\": 2, \"143\": 3, \"144\": 4, \"145\": 5, \"146\": 6}",
                "best_match": 142,
                "match_type": 2,
                "updated": 1,
                "message": None
            }
        ]

        if wip:  # pragma: no cover
            print("Target Path Exists Table Dump")
            print(json.dumps(tbl_dump, indent=4))

        self.assertEqual(len(tbl_dump), len(expected_dump))
        for row in tbl_dump:
            self.assertIn(row, expected_dump)

        mr = self.api.db.get_main_row(142)
        self.assertIsNotNone(mr)

        # Check the main row flags
        self.assertTrue(mr.flags.present)

        # Check dir table is empty
        self.assertListEqual([{"key": 1, "db_local_dir": '["2025", "03", "19"]'}], self.api.db.dump_db_dir_table())
