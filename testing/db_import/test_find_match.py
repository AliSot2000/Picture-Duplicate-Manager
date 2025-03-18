import logging
import os
import unittest
from unittest.mock import patch

from base_class import TestClassifyBase
from photo_lib.custom_enum import NewMatchTypes
from photo_lib.errors_and_warnings import ImplementationError, CorruptDatabase

"""
This file fully tests the following functions:
- api.find_match_for_import_table
- api._get_best_match_type_common
- api.db.get_import_match_iterator_size

The file covers 100% of the function without specific tests:
- api.db.find_import_match_iterator
- api._get_import_best_match_type
"""


class TestFindMatch(TestClassifyBase):
    """
    Test the find_match_for_import_table method
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

    def test_errors_raised(self):
        """
        Test the correct errors are raised.
        """
        self.assertRaises(ValueError, self.api.find_match_for_import_table, tbl_name="Ungabunga")

    def test_regular_matches(self):
        """
        Test default behavior when importing and then performing the match
        """
        tbl = self.api.prepare_directory_for_import(source_dir=os.path.join(self.media_source, "import_match_source"))

        self.assertEqual(7, self.api.db.get_import_match_iterator_size(tbl_name=tbl, recompute=False))
        self.api.find_match_for_import_table(tbl_name=tbl, recompute=False)

        self.check_full_import_table(tbl_name=tbl)

    def test_not_recompute(self):
        """
        Test that no recompute works correctly by setting half of the files to be of no match
        """
        tbl = self.api.prepare_directory_for_import(source_dir=os.path.join(self.media_source, "import_match_source"))

        # Now set dummy values
        for element in ("10_Matching_Source.png", "20_Matching_Source.png", "30_Matching_Source.png", "81_No_Match.png"):
            # get key:
            self.api.db.debug_execute(f"SELECT key FROM `{tbl}` WHERE original_filename = ?", args=(element,))
            res = self.api.db.sq_cur.fetchone()

            self.assertIsNotNone(res)
            key = res[0]

            # Set the dummy values
            self.api.db.set_match_type_import_table(tbl_name=tbl, key=key,
                                                    matches={}, best_match=None, best_match_type=NewMatchTypes.NO_MATCH)

        self.assertEqual(3, self.api.db.get_import_match_iterator_size(tbl_name=tbl, recompute=False))
        self.check_dummy_values(tbl_name=tbl)

        self.api.find_match_for_import_table(tbl_name=tbl, recompute=False)

        self.check_dummy_values(tbl_name=tbl)
        self.check_half_table(tbl_name=tbl)

    def test_recompute(self):
        """
        Test that no recompute works correctly by setting half of the files to be of no match
        """
        tbl = self.api.prepare_directory_for_import(source_dir=os.path.join(self.media_source, "import_match_source"))

        # Now set dummy values
        for element in (
        "10_Matching_Source.png", "20_Matching_Source.png", "30_Matching_Source.png", "81_No_Match.png"):
            # get key:
            self.api.db.debug_execute(f"SELECT key FROM `{tbl}` WHERE original_filename = ?", args=(element,))
            res = self.api.db.sq_cur.fetchone()

            self.assertIsNotNone(res)
            key = res[0]

            # Set the dummy values
            self.api.db.set_match_type_import_table(tbl_name=tbl, key=key,
                                                    matches={}, best_match=None, best_match_type=NewMatchTypes.NO_MATCH)

        self.check_dummy_values(tbl_name=tbl)

        self.assertEqual(7, self.api.db.get_import_match_iterator_size(tbl_name=tbl, recompute=True))

        self.api.find_match_for_import_table(tbl_name=tbl, recompute=True)

        self.check_full_import_table(tbl_name=tbl)

    def check_full_import_table(self, tbl_name: str):
        """
        Check the state of the import table after fully importing.

        :param tbl_name: Import Table to process
        """
        # Iterate through import table
        for key, ofn, mt, bm, parsed_matches in self.api.db.match_test(tbl_name=tbl_name):
            if ofn == "10_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.BINARY_MATCH_MAIN)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.bmm1)[0])
                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.bmm1)[0]: NewMatchTypes.BINARY_MATCH_MAIN,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmm2)[0]: NewMatchTypes.HASH_MATCH_MAIN,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmm3)[0]: NewMatchTypes.BINARY_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmm4)[0]: NewMatchTypes.HASH_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmm5)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmm6)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "20_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.HASH_MATCH_MAIN)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.hmm1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.hmm1)[0]: NewMatchTypes.HASH_MATCH_MAIN,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmm2)[0]: NewMatchTypes.BINARY_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmm3)[0]: NewMatchTypes.HASH_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmm4)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmm5)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "30_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.BINARY_MATCH_TRASH)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.bmt1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.bmt1)[0]: NewMatchTypes.BINARY_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmt2)[0]: NewMatchTypes.HASH_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmt3)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmt4)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "40_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.HASH_MATCH_TRASH)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.hmt1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.hmt1)[0]: NewMatchTypes.HASH_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmt2)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmt3)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "50_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.BINARY_MATCH_DUPLICATES)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.bmd1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.bmd1)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmd2)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "60_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.HASH_MATCH_DUPLICATES)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.hmd1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.hmd1)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "81_No_Match.png":
                self.assertEqual(mt, NewMatchTypes.NO_MATCH)
                self.assertIsNone(bm)
                self.assertDictEqual(parsed_matches, {})


            else:
                raise ImplementationError(f"Unexpected file {ofn}")

    def check_dummy_values(self, tbl_name: str):
        """
        Check the import table matching after half the table is set with dummy values

        :param tbl_name: Import Table to process
        """
        for key, ofn, mt, bm, parsed_matches in self.api.db.match_test(tbl_name=tbl_name):
            if ofn in ("10_Matching_Source.png", "20_Matching_Source.png", "30_Matching_Source.png", "81_No_Match.png"):
                self.assertEqual(mt, NewMatchTypes.NO_MATCH)
                self.assertIsNone(bm)
                self.assertDictEqual(parsed_matches, {})

            elif ofn in ("40_Matching_Source.png", "50_Matching_Source.png", "60_Matching_Source.png"):
                continue
            else:
                raise ImplementationError(f"Unexpected file {ofn}")

    def check_half_table(self, tbl_name: str):
        """
        Check the table when the one half is dummy values and one half is actual match values.

        :param tbl_name: Import Table to process
        """
        for key, ofn, mt, bm, parsed_matches in self.api.db.match_test(tbl_name=tbl_name):
            if ofn in ("10_Matching_Source.png", "20_Matching_Source.png", "30_Matching_Source.png", "81_No_Match.png"):
                continue

            elif ofn == "40_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.HASH_MATCH_TRASH)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.hmt1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.hmt1)[0]: NewMatchTypes.HASH_MATCH_TRASH,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmt2)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.hmt3)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "50_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.BINARY_MATCH_DUPLICATES)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.bmd1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.bmd1)[0]: NewMatchTypes.BINARY_MATCH_DUPLICATES,
                        self.api.db.db_resolve_org_filename_to_keys(self.bmd2)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )

            elif ofn == "60_Matching_Source.png":
                self.assertEqual(mt, NewMatchTypes.HASH_MATCH_DUPLICATES)
                self.assertEqual(bm, self.api.db.db_resolve_org_filename_to_keys(self.hmd1)[0])

                self.assertDictEqual(
                    parsed_matches,
                    {
                        self.api.db.db_resolve_org_filename_to_keys(self.hmd1)[0]: NewMatchTypes.HASH_MATCH_DUPLICATES,
                    }
                )
            else:
                raise ImplementationError(f"Unexpected file {ofn}")


class TestGetBestMatchTypeCommon(TestClassifyBase):
    """
    Fully test the _get_best_match_type_common
    """

    @patch("photo_lib.new_photo_db.PhotoDB.db_resolve_key_to_abs_path")
    def test_raises_corrupt_db_error(self, mock_patch: unittest.mock.MagicMock):
        """
        Test CorruptDB Error is raised. Mock the resolve function.
        """
        mock_patch.return_value = None

        self.assertRaises(CorruptDatabase, lambda : self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                         file_hash="some_str",
                                                                                         match_keys=[1]))

    def test_error_raised_if_both_flags_are_true(self):
        """
        Test an error is raised if trash and duplicate are true
        """
        flags = self.api.db.get_main_flags(1)
        self.assertIsNotNone(flags)

        flags.duplicate = True
        flags.trashed = True

        # Set both flags and update the table
        self.api.db.update_row_main_table(key=1, flags=flags)

        self.assertRaises(CorruptDatabase, lambda:  self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                         file_hash="some_str",
                                                                                         match_keys=[1]))

    @patch("filecmp.cmp", new=lambda a, b, shallow: False)
    def test_logging_hash_match_no_binary_match(self):
        """
        Check that when we have a hash match and
        """
        with self.assertLogs(self.api.rare_occurrence_logger, logging.WARNING):
            fh, _, _ = self.api.db.get_newest_hash(1)

            matches, best_match, best_match_type = self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                        file_hash=fh,
                                                                                        match_keys=[1])

            self.assertDictEqual(matches, {1: NewMatchTypes.HASH_MATCH_MAIN})
            self.assertEqual(best_match_type, NewMatchTypes.HASH_MATCH_MAIN)
            self.assertEqual(best_match, 1)

    @patch("filecmp.cmp", new=lambda a, b, shallow: True)
    def test_logging_with_binary_match_and_no_hash_match(self):
        """
        Check that when we have a hash match and
        """
        with self.assertLogs(self.api.rare_occurrence_logger, logging.WARNING):
            matches, best_match, best_match_type = self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                        file_hash="Some hash",
                                                                                        match_keys=[1])

            self.assertDictEqual(matches, {1: NewMatchTypes.HASH_MATCH_MAIN})
            self.assertEqual(best_match_type, NewMatchTypes.HASH_MATCH_MAIN)
            self.assertEqual(best_match, 1)

    @patch("filecmp.cmp", new=lambda a, b, shallow: True)
    @patch("photo_lib.new_photo_db.PhotoDB.get_main_flags")
    def test_raises_corrupt_db_on_main_flags_not_found(self, mock_patch: unittest.mock.MagicMock):
        """
        Check that if no main flags are found, we raise a corrupt database error
        """
        mock_patch.return_value = None

        self.assertRaises(CorruptDatabase, lambda:  self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                         file_hash="some_str",
                                                                                         match_keys=[1]))

    @patch("filecmp.cmp", new=lambda a, b, shallow: True)
    def test_return_with_non_matching_hashes_and_parent_in_trash(self):
        """
        Check that when we have a hash match and
        """
        self.api.move_to_trash(key=1)

        with self.assertLogs(self.api.rare_occurrence_logger, logging.WARNING):
            matches, best_match, best_match_type = self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                        file_hash="Some hash",
                                                                                        match_keys=[1])

            self.assertDictEqual(matches, {1: NewMatchTypes.HASH_MATCH_TRASH})
            self.assertEqual(best_match_type, NewMatchTypes.HASH_MATCH_TRASH)
            self.assertEqual(best_match, 1)

    @patch("filecmp.cmp", new=lambda a, b, shallow: True)
    def test_return_with_non_matching_hashes_and_parent_in_duplicates(self):
        """
        Check that when we have a hash match and
        """
        self.api.move_to_duplicates(child_key=1, parent_key=2)

        with self.assertLogs(self.api.rare_occurrence_logger, logging.WARNING):
            matches, best_match, best_match_type = self.api._get_best_match_type_common(tgt_fp="/foo/bar/baz.png",
                                                                                        file_hash="Some hash",
                                                                                        match_keys=[1])

            self.assertDictEqual(matches, {1: NewMatchTypes.HASH_MATCH_DUPLICATES})
            self.assertEqual(best_match_type, NewMatchTypes.HASH_MATCH_DUPLICATES)
            self.assertEqual(best_match, 1)