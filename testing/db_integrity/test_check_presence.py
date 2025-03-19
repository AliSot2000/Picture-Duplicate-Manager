import datetime
import json
import logging
import os

from base_class import TestDefaultBase
from photo_lib.custom_enum import MediaType, SelectionType
from photo_lib.data_objects import Selection

"""
Test the functions around check_presence

This file fully tests the following functions:
- api.check_presence
- api.db.update_presence_from_table
- api.update_missing_to_trash
- api.db.update_presence_from_table
- api.db.selection_from_presence_table
- api.db._set_trash_from_selection

The file covers 100% of the function without specific tests:
- api.db.update_missing_to_trash
"""

wip = False


class TestCheckPresenceBase(TestDefaultBase):
    """
    Class contains setup functions and checkers for the check presence functionailty.
    """
    def check_presence_table_dump_empty(self):
        """
        Check that the presence table is empty
        """
        table_dump = self.api.db.dump_presence_table_table()
        self.assertListEqual(table_dump, [])
        self.assertEqual(self.api.db.presence_table_size(), 0)

    def check_presence_table_06(self):
        """
        Check only dir 1990/06 was detected
        """
        table_dump = self.api.db.dump_presence_table_table()
        expected_tbl_dump = [
            {"main_key": 32, "message": None},
            {"main_key": 33, "message": None},
            {"main_key": 34, "message": None},
            {"main_key": 35, "message": None},
            {"main_key": 36, "message": None},
            {"main_key": 37, "message": None},
            {"main_key": 38, "message": None},
            {"main_key": 39, "message": None},
            {"main_key": 40, "message": None},
            {"main_key": 41, "message": None},
            {"main_key": 42, "message": None},
            {"main_key": 43, "message": None},
            {"main_key": 44, "message": None},
            {"main_key": 45, "message": None},
            {"main_key": 46, "message": None},
            {"main_key": 47, "message": None},
            {"main_key": 48, "message": None},
            {"main_key": 49, "message": None},
            {"main_key": 50, "message": None},
            {"main_key": 51, "message": None},
            {"main_key": 52, "message": None},
            {"main_key": 53, "message": None},
            {"main_key": 54, "message": None},
            {"main_key": 55, "message": None},
            {"main_key": 56, "message": None},
            {"main_key": 57, "message": None},
            {"main_key": 58, "message": None},
            {"main_key": 59, "message": None},
            {"main_key": 60, "message": None},
            {"main_key": 61, "message": None},
            {"main_key": 62, "message": None},
            {"main_key": 63, "message": None}
        ]

        self.assertEqual(self.api.db.presence_table_size(), 32)

        if wip:  # pragma: no cover
            print("Check Presence 05 06")
            print(json.dumps(table_dump, indent=4))

        self.assertEqual(len(expected_tbl_dump), len(table_dump))
        for row in table_dump:
            self.assertIn(row, expected_tbl_dump)

    def check_presence_table_05(self):
        """
        Check only dir 1990/06 was detected
        """
        table_dump = self.api.db.dump_presence_table_table()
        expected_tbl_dump = [
            {"main_key": 16, "message": None},
            {"main_key": 17, "message": None},
            {"main_key": 18, "message": None},
            {"main_key": 19, "message": None},
            {"main_key": 20, "message": None},
            {"main_key": 21, "message": None},
            {"main_key": 22, "message": None},
            {"main_key": 23, "message": None},
            {"main_key": 24, "message": None},
            {"main_key": 25, "message": None},
            {"main_key": 26, "message": None},
            {"main_key": 27, "message": None},
            {"main_key": 28, "message": None},
            {"main_key": 29, "message": None},
            {"main_key": 30, "message": None},
            {"main_key": 31, "message": None},

        ]

        self.assertEqual(self.api.db.presence_table_size(), 16)

        if wip:  # pragma: no cover
            print("Check Presence 05 06")
            print(json.dumps(table_dump, indent=4))

        self.assertEqual(len(expected_tbl_dump), len(table_dump))
        for row in table_dump:
            self.assertIn(row, expected_tbl_dump)

    def check_presence_table_05_06(self):
        """
        Check that dir 1990/05 and 1990/06 have been marked as erroneous
        """
        table_dump = self.api.db.dump_presence_table_table()
        expected_tbl_dump = [
            {"main_key": 16, "message": None},
            {"main_key": 17, "message": None},
            {"main_key": 18, "message": None},
            {"main_key": 19, "message": None},
            {"main_key": 20, "message": None},
            {"main_key": 21, "message": None},
            {"main_key": 22, "message": None},
            {"main_key": 23, "message": None},
            {"main_key": 24, "message": None},
            {"main_key": 25, "message": None},
            {"main_key": 26, "message": None},
            {"main_key": 27, "message": None},
            {"main_key": 28, "message": None},
            {"main_key": 29, "message": None},
            {"main_key": 30, "message": None},
            {"main_key": 31, "message": None},
            {"main_key": 32, "message": None},
            {"main_key": 33, "message": None},
            {"main_key": 34, "message": None},
            {"main_key": 35, "message": None},
            {"main_key": 36, "message": None},
            {"main_key": 37, "message": None},
            {"main_key": 38, "message": None},
            {"main_key": 39, "message": None},
            {"main_key": 40, "message": None},
            {"main_key": 41, "message": None},
            {"main_key": 42, "message": None},
            {"main_key": 43, "message": None},
            {"main_key": 44, "message": None},
            {"main_key": 45, "message": None},
            {"main_key": 46, "message": None},
            {"main_key": 47, "message": None},
            {"main_key": 48, "message": None},
            {"main_key": 49, "message": None},
            {"main_key": 50, "message": None},
            {"main_key": 51, "message": None},
            {"main_key": 52, "message": None},
            {"main_key": 53, "message": None},
            {"main_key": 54, "message": None},
            {"main_key": 55, "message": None},
            {"main_key": 56, "message": None},
            {"main_key": 57, "message": None},
            {"main_key": 58, "message": None},
            {"main_key": 59, "message": None},
            {"main_key": 60, "message": None},
            {"main_key": 61, "message": None},
            {"main_key": 62, "message": None},
            {"main_key": 63, "message": None}
        ]

        self.assertEqual(self.api.db.presence_table_size(), 48)

        if wip:  # pragma: no cover
            print("Check Presence 05 06")
            print(json.dumps(table_dump, indent=4))

        self.assertEqual(len(expected_tbl_dump), len(table_dump))
        for row in table_dump:
            self.assertIn(row, expected_tbl_dump)

    def setup_missing_present(self):
        """
        Set one directory as missing but is present, set one directory as present but is missing
        """
        # Create missing files
        tgt_dir_1 = os.path.join(self.api.root_path, "1990", "06", "01")

        # delete files
        for file in os.listdir(tgt_dir_1):
            os.remove(os.path.join(tgt_dir_1, file))
            self.assertFalse(os.path.exists(os.path.join(tgt_dir_1, file)))

        # mark files as missing but are present
        tgt_dir_2 = os.path.join(self.api.root_path, "1990", "05", "01")

        # delete files
        for file in os.listdir(tgt_dir_2):
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            flags.present = False

            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)


class TestCheckPresence(TestCheckPresenceBase):
    """
    Fully test the check_presence function
    """
    def test_default_main(self):
        """
        Test that per default, we get an empty table
        """
        count = self.api.check_presence(m_type=MediaType.MAIN)
        self.assertEqual(count, 0)
        self.check_presence_table_dump_empty()

    def test_default_trash(self):
        """
        Move a directory to trash and check that presence is working correctly.
        """
        tgt_dir = os.path.join(self.api.root_path, "1990", "06", "01")

        # move files to trash
        for file in os.listdir(tgt_dir):
            self.api.move_to_trash(key=self.api.resolve_filename_to_key(file))

        count = self.api.check_presence(m_type=MediaType.TRASH)
        self.assertEqual(0, count)
        self.check_presence_table_dump_empty()

    def test_default_duplicates(self):
        """
        Test presence is correctly detected for duplicates
        """
        tgt_dir = os.path.join(self.api.root_path, "1990", "06", "01")

        # move files to trash
        for file in os.listdir(tgt_dir):
            self.api.move_to_duplicates(child_key=self.api.resolve_filename_to_key(file), parent_key=1)

        count = self.api.check_presence(m_type=MediaType.DUPLICATE)
        self.assertEqual(0, count)
        self.check_presence_table_dump_empty()

    def test_missing_and_presente(self):
        """
        Test with some files present and some missing file
        """
        self.setup_missing_present()

        count = self.api.check_presence(m_type=MediaType.MAIN)
        self.assertEqual(count, 48)

        self.check_presence_table_05_06()

    def test_no_intersection(self):
        """
        Set Selection A to all keys < 16, and check that 0 presence offsets are recorded
        """
        self.setup_missing_present()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key < 16:
                flags.sel_a = True
                self.api.db.update_row_main_table(key=key, flags=flags)

        count = self.api.check_presence(selection=Selection(selection_type=SelectionType.SELECTION_A),
                                        m_type=MediaType.MAIN)

        self.assertEqual(count, 0)
        self.check_presence_table_dump_empty()

    def test_only_missing_intersection(self):
        """
        Test what happens when the files which are present but are marked as missing are indexed
        """
        self.setup_missing_present()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key > 31:
                flags.sel_a = True
                self.api.db.update_row_main_table(key=key, flags=flags)

        count = self.api.check_presence(selection=Selection(selection_type=SelectionType.SELECTION_A),
                                        m_type=MediaType.MAIN)

        self.assertEqual(count, 32)
        self.check_presence_table_06()

    def test_only_present_intersection(self):
        """
        Test what happens when the files present but are marked as missing
        """
        self.setup_missing_present()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key < 32:
                flags.sel_a = True
                self.api.db.update_row_main_table(key=key, flags=flags)

        count = self.api.check_presence(selection=Selection(selection_type=SelectionType.SELECTION_A),
                                        m_type=MediaType.MAIN)

        self.assertEqual(count, 16)
        self.check_presence_table_05()


class TestDBFunctionBase(TestDefaultBase):
    """
    Contains setup and checks for basic db tests
    """
    def check_presence_table(self):
        """
        Check presence table contains exatly the two keys we want
        """
        tbl_dump = self.api.db.dump_presence_table_table()
        expected = [
            {"main_key": 2, "message": None},
            {"main_key": 3, "message": None}
        ]

        self.assertEqual(len(tbl_dump), len(expected))
        self.assertListEqual(tbl_dump, expected)

    def setup_two_file_base_main(self, mt: MediaType):
        """
        Set one file as missing despite present, remove another source file but is marked as presnt.
        """
        if mt == MediaType.TRASH:
            self.api.move_to_trash(key=2)
            self.api.move_to_trash(key=3)

        elif mt == MediaType.DUPLICATE:
            self.api.move_to_duplicates(child_key=3, parent_key=1)
            self.api.move_to_duplicates(child_key=2, parent_key=1)

        # Remove file one
        os.remove(self.api.db.db_resolve_key_to_abs_path(2))

        # Mark file as missing despite present
        flags = self.api.db.get_main_flags(3)
        flags.present = False
        self.api.db.update_row_main_table(key=3, flags=flags)


class UpdatePresenceFromTable(TestDBFunctionBase):
    """
    Fully check the update_presence_from_table
    """
    def test_update_presence_from_table_missing_main(self):
        """
        Test update_presence_from_table given a target missing and source main
        """
        # Perform setup
        mt = MediaType.MAIN
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform update
        self.assertEqual(self.api.db.update_presence_from_table(missing=True, mtype=mt), 1)

        # Check flags of file 2
        flags2 = self.api.db.get_main_flags(2)
        self.assertFalse(flags2.present)
        self.assertFalse(flags2.duplicate)
        self.assertFalse(flags2.trashed)

        # Check flags of file 2
        flags3 = self.api.db.get_main_flags(3)
        self.assertFalse(flags3.present)
        self.assertFalse(flags3.duplicate)
        self.assertFalse(flags3.trashed)


    def test_update_presence_from_table_missing_trash(self):
        """
        Test update_presence_from_table given a target missing and source trash
        """
        # Perform setup
        mt = MediaType.TRASH
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform update
        self.assertEqual(self.api.db.update_presence_from_table(missing=True, mtype=mt), 1)

        # Check flags of file 2
        flags2 = self.api.db.get_main_flags(2)
        self.assertFalse(flags2.present)
        self.assertFalse(flags2.duplicate)
        self.assertTrue(flags2.trashed)

        # Check flags of file 2
        flags3 = self.api.db.get_main_flags(3)
        self.assertFalse(flags3.present)
        self.assertFalse(flags3.duplicate)
        self.assertTrue(flags3.trashed)

    def test_update_presence_from_table_missing_duplicates(self):
        """
        Test update_presence_from_table given a target missing and source duplicates
        """
        # Perform setup
        mt = MediaType.DUPLICATE
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform update
        self.assertEqual(self.api.db.update_presence_from_table(missing=True, mtype=mt), 1)

        # Check flags of file 2
        flags2 = self.api.db.get_main_flags(2)
        self.assertFalse(flags2.present)
        self.assertTrue(flags2.duplicate)
        self.assertFalse(flags2.trashed)

        # Check flags of file 2
        flags3 = self.api.db.get_main_flags(3)
        self.assertFalse(flags3.present)
        self.assertTrue(flags3.duplicate)
        self.assertFalse(flags3.trashed)

    def test_update_presence_from_table_present_main(self):
        """
        Test update_presence_from_table given a target present and source main
        """
        # Perform setup
        mt = MediaType.MAIN
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform update
        self.assertEqual(self.api.db.update_presence_from_table(missing=False, mtype=mt), 1)

        # Check flags of file 2
        flags2 = self.api.db.get_main_flags(2)
        self.assertTrue(flags2.present)
        self.assertFalse(flags2.duplicate)
        self.assertFalse(flags2.trashed)

        # Check flags of file 2
        flags3 = self.api.db.get_main_flags(3)
        self.assertTrue(flags3.present)
        self.assertFalse(flags3.duplicate)
        self.assertFalse(flags3.trashed)

    def test_update_presence_from_table_present_trash(self):
        """
        Test update_presence_from_table given a target present and source trash
        """
        # Perform setup
        mt = MediaType.TRASH
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform update
        self.assertEqual(self.api.db.update_presence_from_table(missing=False, mtype=mt), 1)

        # Check flags of file 2
        flags2 = self.api.db.get_main_flags(2)
        self.assertTrue(flags2.present)
        self.assertFalse(flags2.duplicate)
        self.assertTrue(flags2.trashed)

        # Check flags of file 2
        flags3 = self.api.db.get_main_flags(3)
        self.assertTrue(flags3.present)
        self.assertFalse(flags3.duplicate)
        self.assertTrue(flags3.trashed)

    def test_update_presence_from_table_present_duplicates(self):
        """
        Test update_presence_from_table given a target present and source duplicates
        """
        # Perform setup
        mt = MediaType.DUPLICATE
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform update
        self.assertEqual(self.api.db.update_presence_from_table(missing=False, mtype=mt), 1)

        # Check flags of file 2
        flags2 = self.api.db.get_main_flags(2)
        self.assertTrue(flags2.present)
        self.assertTrue(flags2.duplicate)
        self.assertFalse(flags2.trashed)

        # Check flags of file 2
        flags3 = self.api.db.get_main_flags(3)
        self.assertTrue(flags3.present)
        self.assertTrue(flags3.duplicate)
        self.assertFalse(flags3.trashed)

    def test_raises_error(self):
        """
        Check that an error is raised if the table is empty.
        """
        self.api.db.clear_presence_table()

        self.assertRaises(ValueError, lambda : self.api.db.update_presence_from_table(missing=True,
                                                                                      mtype=MediaType.MAIN))

class TestSelectionFromPresenceTable(TestDBFunctionBase):
    """
    Fully test the selection_from_presence_table function.
    """
    def test_selection_from_presence_table_sel_a_missing(self):
        """
        Test the selection_from_presence_table given selection A as target and the files which are missing.
        """
        sel = True
        missing = True
        mt = MediaType.MAIN

        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform set
        self.assertEqual(self.api.db.selection_from_presence_table(sel_a=sel, missing=missing), 1)

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key == 2:
                self.assertFalse(flags.sel_b)
                self.assertTrue(flags.sel_a)

    def test_selection_from_presence_table_sel_b_missing(self):
        """
        Test the selection_from_presence_table given selection A as target and the files which are missing.
        """
        sel = False
        missing = True
        mt = MediaType.MAIN

        # Perform Setup
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform set
        self.assertEqual(self.api.db.selection_from_presence_table(sel_a=sel, missing=missing), 1)

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key == 2:
                self.assertTrue(flags.sel_b)
                self.assertFalse(flags.sel_a)

    def test_selection_from_presence_table_sel_a_present(self):
        """
        Test the selection_from_presence_table given selection A as target and the files which are missing.
        """
        sel = True
        missing = False
        mt = MediaType.MAIN

        # Perform Setup
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform set
        self.assertEqual(self.api.db.selection_from_presence_table(sel_a=sel, missing=missing), 1)

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key == 3:
                self.assertFalse(flags.sel_b)
                self.assertTrue(flags.sel_a)

    def test_selection_from_presence_table_sel_b_present(self):
        """
        Test the selection_from_presence_table given selection A as target and the files which are missing.
        """
        sel = False
        missing = False
        mt = MediaType.MAIN

        # Perform Setup
        self.setup_two_file_base_main(mt=mt)
        self.assertEqual(self.api.check_presence(m_type=mt), 2)
        self.check_presence_table()

        # Perform set
        self.assertEqual(self.api.db.selection_from_presence_table(sel_a=sel, missing=missing), 1)

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            if key == 3:
                self.assertTrue(flags.sel_b)
                self.assertFalse(flags.sel_a)

    def test_raises_error(self):
        """
        Check a Value Error is raised when the table is empty.
        """
        self.api.db.clear_presence_table()

        self.assertRaises(ValueError, lambda : self.api.db.selection_from_presence_table(sel_a=True, missing=True))


class TestDeleteRowPresenceTable(TestCheckPresenceBase):
    """
    Test the delete_row_presence_table
    """
    def test_delete_row_presence_table_sel_a_missing(self):
        self.setup_missing_present()

        self.assertEqual(self.api.check_presence(m_type=MediaType.MAIN), 48)

        self.check_presence_table_05_06()

        for i in range(16, 32):
            self.api.db.delete_row_presence_table(i)

        self.check_presence_table_06()


class TestUpdateTrashFromSelection(TestCheckPresenceBase):
    """
    Fully test the _set_trash_from_selection
    """

    def test_raises_error(self):
        """
        Test that datetime selection is not allowed
        """
        self.assertRaises(TypeError, lambda : self.api.db._set_trash_from_selection(
            selection=Selection(selection_type=SelectionType.TIME_RANGE,
                                start=datetime.datetime.now(datetime.timezone.utc),
                                duration=datetime.timedelta(minutes=1),)))

    def test_sel_a(self):
        """
        Test selection A is working correctly
        """
        self.setup_missing_present()
        self.check_presence_table_dump_empty()

        # Check that we get the right number of errors
        self.assertEqual(self.api.check_presence(m_type=MediaType.MAIN), 48)

        # Check presence detection worked.
        self.check_presence_table_05_06()

        # Get all missing files
        count = self.api.db.selection_from_presence_table(sel_a=True, missing=True)
        self.assertEqual(count, 32)

        # INFO: Dir 1990/06/01 is missing
        affected = self.api.db._set_trash_from_selection(selection=Selection(selection_type=SelectionType.SELECTION_A))
        self.assertEqual(count, affected)

        # Check the tables have the correct format
        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key=key)
            self.assertIsNotNone(mdr)

            if 31 < key < 64:
                self.assertTrue(flags.trashed)
                self.assertEqual(mdr.replaced, MediaType.TRASH)
            else:
                self.assertFalse(flags.trashed)
                self.assertEqual(mdr.replaced, MediaType.MAIN)

    def test_sel_a_via_api(self):
        """
        Test selection A is working correctly
        """
        self.setup_missing_present()
        self.check_presence_table_dump_empty()

        # Check that we get the right number of errors
        self.assertEqual(self.api.check_presence(m_type=MediaType.MAIN), 48)

        # Check presence detection worked.
        self.check_presence_table_05_06()

        self.api.update_missing_to_trash()

        # Check the tables have the correct format
        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key=key)
            self.assertIsNotNone(mdr)

            if 31 < key < 64:
                self.assertTrue(flags.trashed)
                self.assertEqual(mdr.replaced, MediaType.TRASH)
            else:
                self.assertFalse(flags.trashed)
                self.assertEqual(mdr.replaced, MediaType.MAIN)

    def test_sel_b(self):
        """
        Test that the entire process also works with Selection B
        """
        self.setup_missing_present()
        self.check_presence_table_dump_empty()

        # Check that we get the right number of errors
        self.assertEqual(self.api.check_presence(m_type=MediaType.MAIN), 48)

        # Check presence detection worked.
        self.check_presence_table_05_06()

        # Get all missing files
        count = self.api.db.selection_from_presence_table(sel_a=False, missing=True)
        self.assertEqual(count, 32)

        # INFO: Dir 1990/06/01 is missing
        affected = self.api.db._set_trash_from_selection(
            selection=Selection(selection_type=SelectionType.SELECTION_B))
        self.assertEqual(count, affected)

        # Check the tables have the correct format
        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key=key)
            self.assertIsNotNone(mdr)

            if 31 < key < 64:
                self.assertTrue(flags.trashed)
                self.assertEqual(mdr.replaced, MediaType.TRASH)
            else:
                self.assertFalse(flags.trashed)
                self.assertEqual(mdr.replaced, MediaType.MAIN)

    def test_warning_integrity_logger(self):
        """
        Test that the entire process also works with Selection B
        """
        self.setup_missing_present()
        self.check_presence_table_dump_empty()

        # Check that we get the right number of errors
        self.assertEqual(self.api.check_presence(m_type=MediaType.MAIN), 48)

        # Check presence detection worked.
        self.check_presence_table_05_06()

        # Get all missing files
        count = self.api.db.selection_from_presence_table(sel_a=False, missing=True)
        self.assertEqual(count, 32)

        # Delete all rows from metadata table
        for i in range(32, 64):
            self.api.db.delete_row_metadata_table(key=i)

        # INFO: Dir 1990/06/01 is missing
        with self.assertLogs(self.api.integrity_logger, logging.WARNING):
            affected = self.api.db._set_trash_from_selection(
                selection=Selection(selection_type=SelectionType.SELECTION_B))

        self.assertEqual(count, affected)

        # Check the tables have the correct format
        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key=key)

            if 31 < key < 64:
                self.assertTrue(flags.trashed)
                self.assertIsNone(mdr)
            else:
                self.assertFalse(flags.trashed)
                self.assertIsNotNone(mdr)
                self.assertEqual(mdr.replaced, MediaType.MAIN)

    def test_wrapper_error(self):
        """
        Test that the wrapper raises an error, if the table is empty.
        """
        self.api.db.clear_presence_table()

        self.assertRaises(ValueError, self.api.update_missing_to_trash)
