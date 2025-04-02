import json
import os.path
import shutil
import unittest
from unittest.mock import patch

from base_class import TestDefaultBase
from photo_lib.errors_and_warnings import CorruptDatabase

"""
This file fully tests the following functions:
- api.set_custom_directories
- api.move_files_to_target_dir
- api.check_file_location
- api.db.set_location_update_table_success
- api.db.delete_row_location_update_table
- api.db.selection_from_location_update_table

The file covers 100% of the function without specific tests:
- api.db.clear_location_update_table
- api.db.location_update_table_size
- api.db.insert_row_location_update_table
- api.db.get_location_update_iterator_size
- api.db.location_update_table_iterator
- api.db.dump_loccation_update_table
"""

wip: bool = False


class TestDBFunctions(TestDefaultBase):
    """
    Test the set_location_update_table_success and delete_row_location_update_table
    """
    def setUp(self):
        """
        Add one row to the location_update_table.
        """
        super().setUp()
        self.api.db.insert_row_location_update_table(key=1, file_name="bla", directory="foo/bar/baz")

    def test_update_to_success(self):
        """
        Test that we can update a row to success, and it won't update afterwards. Also test the iterator size
        """
        self.assertEqual(self.api.db.get_location_update_iterator_size(), 1)

        self.api.db.set_location_update_table_success(key=1, success=True)

        self.assertEqual(self.api.db.get_location_update_iterator_size(), 0)

        self.assertRaises(AssertionError, lambda : self.api.db.set_location_update_table_success(key=1, success=False))

    def test_raises_message_error(self):
        """
        Test that the update call raises an error, if a message is provided in conjunction with success
        """
        self.assertRaises(ValueError, lambda : self.api.db.set_location_update_table_success(
            key=1,
            success=True,
            message="Some Message"
        ))

    def test_update_to_failure(self):
        """
        Test that we can update a row to failure, and it won't update afterwards. Also test the iterator size
        """
        self.assertEqual(self.api.db.get_location_update_iterator_size(), 1)

        self.api.db.set_location_update_table_success(key=1, success=False)

        self.assertEqual(self.api.db.get_location_update_iterator_size(), 0)

        self.assertRaises(AssertionError, lambda: self.api.db.set_location_update_table_success(key=1, success=True))

    def test_delete_function(self):
        """
        Check that we can successfully delete a row
        """
        self.assertEqual(1, self.api.db.location_update_table_size())
        self.assertEqual(1, self.api.db.get_location_update_iterator_size())

        # Delete the row
        self.api.db.delete_row_location_update_table(1)

        self.assertEqual(0, self.api.db.location_update_table_size())
        self.assertEqual(0, self.api.db.get_location_update_iterator_size())

        self.assertListEqual(self.api.db.dump_location_update_table(), [])


class BaseCheckFileLocation(TestDefaultBase):
    """
    Class contains utility functions needed for testing.
    """
    def setup_move(self):
        """
        Perform a move directory action. 1990/05/01 -> 1990/05/02
        """
        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")
        os.rename(base_dir, tgt_dir)

    def setup_copy(self):
        """
        Perform a copy directory action. 1990/05/01 -> 1990/05/02
        """
        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")
        shutil.copytree(base_dir, tgt_dir)

    def check_table_empty(self):
        """
        CHeck that the location_update_table is empty.
        """
        self.assertListEqual(self.api.db.dump_location_update_table(), [])

    def check_content_05(self):
        """
        Check that we have all files of directory 1990/05/01 in the location_update_table.
        """
        tbl_dump = self.api.db.dump_location_update_table()
        expected_dump = [
            {
                "key": 16,
                "file_name": "1990-05-01T12-00-00_0016.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 17,
                "file_name": "1990-05-01T12-00-09_0017.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 18,
                "file_name": "1990-05-01T12-00-10_0018.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 19,
                "file_name": "1990-05-01T12-00-11_0019.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 20,
                "file_name": "1990-05-01T12-00-12_0020.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 21,
                "file_name": "1990-05-01T12-00-13_0021.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 22,
                "file_name": "1990-05-01T12-00-14_0022.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 23,
                "file_name": "1990-05-01T12-00-15_0023.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 24,
                "file_name": "1990-05-01T12-00-01_0024.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 25,
                "file_name": "1990-05-01T12-00-02_0025.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 26,
                "file_name": "1990-05-01T12-00-03_0026.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 27,
                "file_name": "1990-05-01T12-00-04_0027.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 28,
                "file_name": "1990-05-01T12-00-05_0028.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 29,
                "file_name": "1990-05-01T12-00-06_0029.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 30,
                "file_name": "1990-05-01T12-00-07_0030.png",
                "directory": "1990/05/02",
                "success": 0
            },
            {
                "key": 31,
                "file_name": "1990-05-01T12-00-08_0031.png",
                "directory": "1990/05/02",
                "success": 0
            }
        ]
        if wip:  # pragma: no cover
            print(json.dumps(tbl_dump, indent=4))

        self.assertListEqual(tbl_dump, expected_dump)

class TestCheckFileLocation(BaseCheckFileLocation):
    """
    Fully test the check_file_location function
    """

    @patch("photo_lib.new_photo_db.PhotoDB.db_resolve_key_to_abs_path")
    def test_raises_error(self, mock_patch: unittest.mock.MagicMock):
        """
        Check that we raise a corrupt database error
        """
        mock_patch.return_value = None
        
        # Check a corrupt database error is raised
        self.assertRaises(CorruptDatabase, self.api.check_file_location)
        
    def test_no_op(self):
        """
        Check that if we don't do anything, no moved files are detected
        """
        res = self.api.check_file_location()
        
        self.assertEqual(res, 0)

        self.check_table_empty()
        
    def test_directory_moved(self):
        """
        Test that the files are detected correctly, if we move a directory.
        """
        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # check number of entries
        self.assertEqual(len(os.listdir(base_dir)), 16)
        self.assertTrue(os.path.exists(base_dir))
        self.assertFalse(os.path.exists(tgt_dir))

        self.setup_move()

        # move directory
        self.assertEqual(len(os.listdir(tgt_dir)), 16)
        self.assertFalse(os.path.exists(base_dir))
        self.assertTrue(os.path.exists(tgt_dir))

        count = self.api.check_file_location()
        self.assertEqual(count, 16)
        self.check_content_05()

    def test_directory_copied(self):
        """
        Test that the location_update_table also detects if you copied a directory inside the db.
        """
        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # check number of entries
        self.assertEqual(len(os.listdir(base_dir)), 16)
        self.assertTrue(os.path.exists(base_dir))
        self.assertFalse(os.path.exists(tgt_dir))

        self.setup_copy()

        # move directory
        self.assertEqual(len(os.listdir(tgt_dir)), 16)
        self.assertTrue(os.path.exists(base_dir))
        self.assertTrue(os.path.exists(tgt_dir))

        count = self.api.check_file_location()
        self.assertEqual(count, 16)
        self.check_content_05()


class TestMoveFilesToTargetDir(BaseCheckFileLocation):
    """
    Fully test the move_files_to_target_dir and set_custom_directories function.
    """
    def check_failed(self):
        """
        Check the table dump of a failed operation
        """
        tbl_dump = self.api.db.dump_location_update_table()
        expected_dump = [
            {
                "key": 16,
                "file_name": "1990-05-01T12-00-00_0016.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 17,
                "file_name": "1990-05-01T12-00-09_0017.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 18,
                "file_name": "1990-05-01T12-00-10_0018.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 19,
                "file_name": "1990-05-01T12-00-11_0019.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 20,
                "file_name": "1990-05-01T12-00-12_0020.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 21,
                "file_name": "1990-05-01T12-00-13_0021.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 22,
                "file_name": "1990-05-01T12-00-14_0022.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 23,
                "file_name": "1990-05-01T12-00-15_0023.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 24,
                "file_name": "1990-05-01T12-00-01_0024.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 25,
                "file_name": "1990-05-01T12-00-02_0025.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 26,
                "file_name": "1990-05-01T12-00-03_0026.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 27,
                "file_name": "1990-05-01T12-00-04_0027.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 28,
                "file_name": "1990-05-01T12-00-05_0028.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 29,
                "file_name": "1990-05-01T12-00-06_0029.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 30,
                "file_name": "1990-05-01T12-00-07_0030.png",
                "directory": "1990/05/02",
                "success": 2
            },
            {
                "key": 31,
                "file_name": "1990-05-01T12-00-08_0031.png",
                "directory": "1990/05/02",
                "success": 2
            }
        ]
        if wip:  # pragma: no cover
            print(json.dumps(tbl_dump, indent=4))

        self.assertListEqual(tbl_dump, expected_dump)

    def check_success(self):
        """
        Check the table after a successful operation
        """
        tbl_dump = self.api.db.dump_location_update_table()
        expected_dump = [
            {
                "key": 16,
                "file_name": "1990-05-01T12-00-00_0016.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 17,
                "file_name": "1990-05-01T12-00-09_0017.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 18,
                "file_name": "1990-05-01T12-00-10_0018.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 19,
                "file_name": "1990-05-01T12-00-11_0019.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 20,
                "file_name": "1990-05-01T12-00-12_0020.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 21,
                "file_name": "1990-05-01T12-00-13_0021.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 22,
                "file_name": "1990-05-01T12-00-14_0022.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 23,
                "file_name": "1990-05-01T12-00-15_0023.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 24,
                "file_name": "1990-05-01T12-00-01_0024.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 25,
                "file_name": "1990-05-01T12-00-02_0025.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 26,
                "file_name": "1990-05-01T12-00-03_0026.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 27,
                "file_name": "1990-05-01T12-00-04_0027.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 28,
                "file_name": "1990-05-01T12-00-05_0028.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 29,
                "file_name": "1990-05-01T12-00-06_0029.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 30,
                "file_name": "1990-05-01T12-00-07_0030.png",
                "directory": "1990/05/02",
                "success": 1
            },
            {
                "key": 31,
                "file_name": "1990-05-01T12-00-08_0031.png",
                "directory": "1990/05/02",
                "success": 1
            }
        ]
        if wip:  # pragma: no cover
            print(json.dumps(tbl_dump, indent=4))

        self.assertListEqual(tbl_dump, expected_dump)

    def check_dir_table_empty(self):
        """
        Check that the dir table is empty.
        """
        self.assertListEqual(self.api.db.dump_db_dir_table(), [])

    def check_dir_table_one_entry(self):
        """
        Check that an entry was sucessfully added to the dir table
        """
        self.assertListEqual(self.api.db.dump_db_dir_table(),
                             [{"key": 1, "db_local_dir": '["1990", "05", "02"]'}])

    def test_sel_a_from_move_back(self):
        """
        Test that the selection_a flag is correctly set from the location_update_table
        """
        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            self.assertFalse(flags.sel_a)
            self.assertFalse(flags.sel_b)

        self.setup_move()

        self.assertEqual(self.api.db.selection_from_location_update_table(sel_a=True), 0)

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        success, failed = self.api.move_files_to_target_dir()
        self.assertEqual(success, 16)
        self.assertEqual(failed, 0)

        self.check_success()
        # Directory wasn't pruned.
        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, "1990", "05", "02")))
        self.check_dir_table_empty()

        self.assertEqual(self.api.db.selection_from_location_update_table(sel_a=True), 16)

        files = os.listdir(os.path.join(self.api.root_path, "1990", "05", "01"))

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

            file = os.path.basename(self.api.resolve_key_to_path(key))

            if file in files:
                self.assertTrue(flags.sel_a)
                self.assertFalse(flags.sel_b)
            else:
                self.assertFalse(flags.sel_a)
                self.assertFalse(flags.sel_b)

    def test_sel_b_from_move_back(self):
        """
        Test that the selection_a flag is correctly set from the location_update_table
        """
        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            self.assertFalse(flags.sel_a)
            self.assertFalse(flags.sel_b)

        self.setup_move()

        self.assertEqual(self.api.db.selection_from_location_update_table(sel_a=False), 0)

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        success, failed = self.api.move_files_to_target_dir()
        self.assertEqual(success, 16)
        self.assertEqual(failed, 0)

        self.check_success()
        # Directory wasn't pruned.
        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, "1990", "05", "02")))
        self.check_dir_table_empty()

        self.assertEqual(self.api.db.selection_from_location_update_table(sel_a=False), 16)

        files = os.listdir(os.path.join(self.api.root_path, "1990", "05", "01"))

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

            file = os.path.basename(self.api.resolve_key_to_path(key))

            if file in files:
                self.assertFalse(flags.sel_a)
                self.assertTrue(flags.sel_b)
            else:
                self.assertFalse(flags.sel_a)
                self.assertFalse(flags.sel_b)

    def test_move_back(self):
        """
        Test the files are correctly moved back but the parent directory still exists.
        """
        self.setup_move()

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        success, failed = self.api.move_files_to_target_dir()
        self.assertEqual(success, 16)
        self.assertEqual(failed, 0)

        self.check_success()
        # Directory wasn't pruned.
        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, "1990", "05", "02")))
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

    def test_move_back_conflict(self):
        """
        Test move back fails, if the files are present at the destination.
        """
        self.setup_copy()
        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        success, failed = self.api.move_files_to_target_dir()
        self.assertEqual(success, 0)
        self.assertEqual(failed, 16)

        # Directory wasn't pruned.
        self.assertTrue(os.path.exists(tgt_dir))

        # check both directories contain files
        self.assertEqual(len(os.listdir(base_dir)), 16)
        self.assertEqual(len(os.listdir(tgt_dir)), 16)

        self.check_failed()
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

    def test_move_back_duplicates(self):
        """
        Check that move back failes if the files are marked as duplicates
        """
        self.setup_copy()

        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # Set files as duplicates
        for file in os.listdir(base_dir):
            key = self.api.resolve_filename_to_key(file)
            self.assertIsNotNone(key)

            # Perform duplicate
            self.api.move_to_duplicates(child_key=key, parent_key=1)

        for file in os.listdir(self.api.db.get_trash_dir()):
            os.remove(os.path.join(self.api.db.get_trash_dir(), file))

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        # Perform move and check that it fails
        success, failed = self.api.move_files_to_target_dir()
        self.assertEqual(success, 0)
        self.assertEqual(failed, 16)

        self.assertEqual(len(os.listdir(base_dir)), 0)
        self.assertEqual(len(os.listdir(tgt_dir)), 16)

        self.check_failed()
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

    def test_move_back_trash(self):
        """
        Check that move back fails if the files are marked as trashed
        """
        self.setup_copy()

        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        # Set files as duplicates
        for file in os.listdir(base_dir):
            key = self.api.resolve_filename_to_key(file)
            self.assertIsNotNone(key)

            # Perform duplicate
            self.api.move_to_trash(key=key)

        for file in os.listdir(self.api.db.get_trash_dir()):
            os.remove(os.path.join(self.api.db.get_trash_dir(), file))

        # Perform move and check that it fails
        success, failed = self.api.move_files_to_target_dir()
        self.assertEqual(success, 0)
        self.assertEqual(failed, 16)

        self.assertEqual(len(os.listdir(base_dir)), 0)
        self.assertEqual(len(os.listdir(tgt_dir)), 16)

        self.check_failed()
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

    def test_update_dir(self):
        """
        Test that we successfully update the directory table and add the current location as a custom dir
        """
        self.setup_move()

        # Check dir table is initially empty
        self.check_dir_table_empty()

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        success, failed = self.api.set_custom_directories()
        self.assertEqual(success, 16)
        self.assertEqual(failed, 0)

        self.check_success()
        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, "1990", "05", "02")))
        self.assertEqual(len(os.listdir(os.path.join(self.api.root_path, "1990", "05", "02"))), 16)

        self.check_dir_table_one_entry()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            file = self.api.db.db_resolve_key_to_abs_path(key)

            # Get metadata row
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)

            if os.path.basename(file) in os.listdir(os.path.join(self.api.root_path, "1990", "05", "02")):
                self.assertEqual(mdr.db_local_dir, ["1990", "05", "02"])
            else:
                self.assertIsNone(mdr.db_local_dir)

    def test_update_dir_conflict(self):
        """
        Check that updating the directory table fails. When we have a
        """
        self.setup_copy()

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        success, failed = self.api.set_custom_directories()
        self.assertEqual(success, 0)
        self.assertEqual(failed, 16)

        # Directory wasn't pruned.
        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, "1990", "05", "02")))

        # check both directories contain files
        self.assertEqual(len(os.listdir(os.path.join(self.api.root_path, "1990", "05", "02"))), 16)
        self.assertEqual(len(os.listdir(os.path.join(self.api.root_path, "1990", "05", "01"))), 16)

        self.check_failed()
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

    def test_update_dir_duplicates(self):
        """
        Test that set_custom_directories fails if the files are marked as duplicates
        """
        self.setup_copy()

        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # Set files as duplicates
        for file in os.listdir(base_dir):
            key = self.api.resolve_filename_to_key(file)
            self.assertIsNotNone(key)

            # Perform duplicate
            self.api.move_to_duplicates(child_key=key, parent_key=1)

        for file in os.listdir(self.api.db.get_trash_dir()):
            os.remove(os.path.join(self.api.db.get_trash_dir(), file))

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        success, failed = self.api.set_custom_directories()
        self.assertEqual(success, 0)
        self.assertEqual(failed, 16)

        self.assertTrue(os.path.exists(base_dir))
        self.assertTrue(os.path.exists(tgt_dir))

        # check both directories contain files
        self.assertEqual(len(os.listdir(tgt_dir)), 16)
        self.assertEqual(len(os.listdir(base_dir)), 0)

        self.check_failed()
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)

    def test_update_dir_trash(self):
        """
        Check that update directory  fails if the files are in the trash
        """
        self.setup_copy()

        base_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        tgt_dir = os.path.join(self.api.db.root_path, "1990", "05", "02")

        # Set files as duplicates
        for file in os.listdir(base_dir):
            key = self.api.resolve_filename_to_key(file)
            self.assertIsNotNone(key)

            # Perform duplicate
            self.api.move_to_trash(key=key)

        for file in os.listdir(self.api.db.get_trash_dir()):
            os.remove(os.path.join(self.api.db.get_trash_dir(), file))

        # Check detection
        count = self.api.check_file_location()
        self.assertEqual(count, 16)

        self.check_content_05()

        success, failed = self.api.set_custom_directories()
        self.assertEqual(success, 0)
        self.assertEqual(failed, 16)

        self.assertTrue(os.path.exists(base_dir))
        self.assertTrue(os.path.exists(tgt_dir))

        # check both directories contain files
        self.assertEqual(len(os.listdir(tgt_dir)), 16)
        self.assertEqual(len(os.listdir(base_dir)), 0)

        self.check_failed()
        self.check_dir_table_empty()

        for key, flags in self.api.db.main_key_flags_iterator(allow_selection=False):
            mdr = self.api.db.get_metadata_row(key)
            self.assertIsNotNone(mdr)
            self.assertIsNone(mdr.db_local_dir)