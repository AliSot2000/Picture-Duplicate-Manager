from typing import List

from base_class import TestExtraMediaBase
import os

from photo_lib.custom_enum import SelectionType
from photo_lib.data_objects import Selection

"""
Test the check_and_update_disp_files function.
"""


class TestCheckAndUpdateDispFiles(TestExtraMediaBase):
    """
    Full test the check_and_update_disp_files
    """
    def test_no_op(self):
        """
        Test that we have no updates if everything is correct.
        """
        output = self.api.check_and_update_disp_files()

        missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min = output

        self.assertEqual(missing_min, 0)
        self.assertEqual(missing_thumb, 0)
        self.assertEqual(present_min, 0)
        self.assertEqual(present_thumb, 0)
        self.assertEqual(correct_min, 157)
        self.assertEqual(correct_thumb, 157)

    def set_up_missing_present(self):
        """
        Check that we correctly identify missing and suddenly present thumbnails and miniatures
        """
        # missing dir
        missing_dir = os.path.join(self.api.root_path, "1990", "04", "01")

        # present dir
        present_dir = os.path.join(self.api.root_path, "1990", "05", "01")

        # Remove files for missing dir
        for file in os.listdir(missing_dir):
            # remove the display files
            os.remove(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file)))
            os.remove(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file)))

            # Check files do not exist
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))

        # INFO: get_main_flags and update_row_main_table are in different table
        # Set not present for present dir
        for file in os.listdir(present_dir):
            main_flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))
            self.assertIsNotNone(main_flags)

            # reset the flags
            main_flags.has_miniature = False
            main_flags.has_thumbnail = False

            # update the main row
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=main_flags)

        return os.listdir(missing_dir), os.listdir(present_dir)

    def check_present(self, files: List[str]):
        """
        Check that the flags for the given files are set to present
        """
        for file in files:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            # Check the flags are set correctly
            self.assertTrue(flags.has_thumbnail)
            self.assertTrue(flags.has_miniature)

    def check_missing(self, files: List[str]):
        """
        Check that the flags for the given files are set to not present.
        """
        for file in files:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            # Check the flags are set correctly
            self.assertFalse(flags.has_thumbnail)
            self.assertFalse(flags.has_miniature)

    def test_both_all(self):
        """
        Check the entire database and update the files
        """
        missing, present = self.set_up_missing_present()

        output = self.api.check_and_update_disp_files()

        missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min = output

        self.assertEqual(missing_min, 8)
        self.assertEqual(missing_thumb, 8)
        self.assertEqual(present_min, 16)
        self.assertEqual(present_thumb, 16)
        self.assertEqual(correct_min, 133)
        self.assertEqual(correct_thumb, 133)

        self.check_missing(missing)
        self.check_present(present)

    def test_not_intersecting_subset(self):
        """
        Check that selection is working correctly. No files updated for the directory we haven't modified
        """
        self.set_up_missing_present()

        # set selection
        sel_dir = os.path.join(self.api.root_path, "1990", "07", "01")
        for file in os.listdir(sel_dir):
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        output = self.api.check_and_update_disp_files(selection=Selection(selection_type=SelectionType.SELECTION_A))

        missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min = output

        self.assertEqual(missing_min, 0)
        self.assertEqual(missing_thumb, 0)
        self.assertEqual(present_min, 0)
        self.assertEqual(present_thumb, 0)
        self.assertEqual(correct_min, 64)
        self.assertEqual(correct_thumb, 64)

    def test_only_missing(self):
        """
        Testing with selection where we have files staying the same and files that are missing.
        """
        missing, _ = self.set_up_missing_present()

        # set selection
        sel_dir = os.path.join(self.api.root_path, "1990", "07", "01")
        for file in os.listdir(sel_dir) + missing:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        output = self.api.check_and_update_disp_files(selection=Selection(selection_type=SelectionType.SELECTION_A))

        missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min = output

        self.assertEqual(missing_min, 8)
        self.assertEqual(missing_thumb, 8)
        self.assertEqual(present_min, 0)
        self.assertEqual(present_thumb, 0)
        self.assertEqual(correct_min, 64)
        self.assertEqual(correct_thumb, 64)

        self.check_missing(missing)

    def test_only_present(self):
        """
        Testing with selection where we have files staying the same and files that are present.
        """
        _, present = self.set_up_missing_present()

        # set selection
        sel_dir = os.path.join(self.api.root_path, "1990", "07", "01")
        for file in os.listdir(sel_dir) + present:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        output = self.api.check_and_update_disp_files(selection=Selection(selection_type=SelectionType.SELECTION_A))

        missing_thumb, present_thumb, correct_thumb, missing_min, present_min, correct_min = output

        self.assertEqual(missing_min, 0)
        self.assertEqual(missing_thumb, 0)
        self.assertEqual(present_min, 16)
        self.assertEqual(present_thumb, 16)
        self.assertEqual(correct_min, 64)
        self.assertEqual(correct_thumb, 64)

        self.check_present(present)
