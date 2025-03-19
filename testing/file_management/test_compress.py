import shutil

from base_class import TestDefaultBase

import os
from photo_lib.utils import rec_list_all

"""
This file fully tests the following functions:
- api.compress

"""

class TestCompress(TestDefaultBase):
    """
    Test the functionality of the compress function
    """
    def setUp(self):
        super().setUp()

        self.api.create_display_files()

    def test_temp(self):
        """
        Test the files of the temp directory are correctly remove.
        """
        tmp_dir = self.api.db.get_temp_dir()

        tmp_sub_dir = os.path.join(tmp_dir, 'sub')
        os.makedirs(tmp_sub_dir)

        # Create files in the subdir
        for i in range(10):
            with open(os.path.join(tmp_sub_dir, f"{i}.json"), "w") as file:
                file.write(f"Test file Nr {i}")

        # Create test files in the regular directory
        for i in range(10):
            with open(os.path.join(tmp_dir, f"{i}.json"), "w") as file:
                file.write(f"Test file Nr {i}")

        all_files = rec_list_all(tmp_dir)

        # Perform compression
        self.api.compress()

        for file in all_files:
            self.assertFalse(os.path.exists(file))

    def test_retain_trash_thumb(self):
        """
        Test that the thumbnails from the trash are retained
        """
        # Remove files for testing continue
        missing_dir = os.path.join(self.api.root_path, "1990", "04", "01")
        missing_files = os.listdir(missing_dir)

        # Remove missing directory
        shutil.rmtree(missing_dir)

        # Missing display files
        disp_missing_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        disp_missing_files = os.listdir(disp_missing_dir)

        # Check files are currently existing
        for df in disp_missing_files:
            self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(df))))
            self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(df))))

            # Files are now missing
            os.remove(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(df)))
            os.remove(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(df)))

            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(df))))
            self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(df))))

        # need to compress
        self.api.compress()

        # Check that for all missing, the thumbnails are present
        for file in missing_files:
            self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
            self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        for df in disp_missing_files:
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(df))))
            self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(df))))

    def test_no_thumb_for_duplicates(self):
        """
        Check that thumbnails for duplicates
        """
        duplicate_dir = os.path.join(self.api.root_path, "1990", "05", "01")
        dup_files = os.listdir(duplicate_dir)

        # mark the files as duplicates
        for file in dup_files:
            fk = self.api.resolve_filename_to_key(file)
            self.api.move_to_duplicates(child_key=fk, parent_key=1)

        self.api.empty_trash()
        self.api.compress()

        # Check that all files are deleted
        for file in dup_files:
            fk = self.api.resolve_filename_to_key(file)
            self.assertFalse(os.path.exists(self.api.db.db_resolve_key_to_abs_path(fk)))
            self.assertFalse(os.path.exists(self.api.db.full_miniature_path(fk)))
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(fk)))