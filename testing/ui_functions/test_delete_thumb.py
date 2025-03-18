import os.path

from base_class import TestClassifyBase
from photo_lib.custom_enum import SelectionType
from photo_lib.data_objects import Selection


"""
This file fully tests the following functions:
- api.delete_thumb
"""

class TestDeleteThumb(TestClassifyBase):
    """
    Test how deletion of thumbnails works
    """
    def test_errors_raised(self):
        """
        Test that the correct errors are raised
        """
        # Neither specified
        self.assertRaises(ValueError, self.api.delete_thumb,
                          key=None, selection=None, trash_override=False)

        # Both specified
        self.assertRaises(ValueError, self.api.delete_thumb,
                          key=1, selection=Selection(selection_type=SelectionType.SELECTION_A), trash_override=False)

        # key doesn't exist
        self.assertRaises(ValueError, self.api.delete_thumb,
                          key=1000, trash_override=False)

        # Move to trash
        self.api.move_to_trash(key=1)

        # Check the error is raised
        self.assertRaises(ValueError, self.api.delete_thumb,
                          key=1, trash_override=False)

    def test_delete_of_key(self):
        """
        Test trash is correctly deleted
        """
        self.api.create_display_files()

        # Check that thumbnails of image exist
        self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(1)))
        self.assertTrue(os.path.exists(self.api.db.full_miniature_path(1)))

        self.api.delete_thumb(key=1)

        # Check thumbnails were deleted
        self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(1)))
        self.assertFalse(os.path.exists(self.api.db.full_miniature_path(1)))

        # Check flags
        flags = self.api.db.get_main_flags(1)
        self.assertIsNotNone(flags)
        self.assertFalse(flags.has_miniature)
        self.assertFalse(flags.has_thumbnail)

    def test_deleting_selection(self):
        """
        Test deleting regular selection, trash not touched
        """
        self.api.create_display_files(miniature=True, thumbnail=True)

        dir_1 = os.path.join(self.api.root_path, "1990", "04", "01")
        dir_2 = os.path.join(self.api.root_path, "1990", "05", "01")

        files_dir_1 = os.listdir(dir_1)
        files_dir_2 = os.listdir(dir_2)

        # move dir 2 to trash
        for file in files_dir_1:
            self.api.move_to_trash(self.api.resolve_filename_to_key(file))

        # Set selection a
        for file in files_dir_2 + files_dir_2:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            self.assertIsNotNone(flags)

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        # Delete thumbnails of selection
        del_thumb = self.api.delete_thumb(selection=Selection(selection_type=SelectionType.SELECTION_A))
        self.assertEqual(del_thumb, 2 * len(files_dir_2))

        # Check files in trash exist and files in regular dir are deleted
        for file in files_dir_1:
            self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
            self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        for file in files_dir_2:
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
            self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

    def test_deleting_selection_with_trash_override(self):
        """
        Test deleting regular selection, with trash override, should delete both
        """
        self.api.create_display_files(miniature=True, thumbnail=True)

        dir_1 = os.path.join(self.api.root_path, "1990", "04", "01")
        dir_2 = os.path.join(self.api.root_path, "1990", "05", "01")

        files_dir_1 = os.listdir(dir_1)
        files_dir_2 = os.listdir(dir_2)

        # move dir 2 to trash
        for file in files_dir_1:
            self.api.move_to_trash(self.api.resolve_filename_to_key(file))

        # Set selection a
        for file in files_dir_2 + files_dir_1:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            self.assertIsNotNone(flags)

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        # Delete thumbnails of selection
        del_thumb = self.api.delete_thumb(selection=Selection(selection_type=SelectionType.SELECTION_A),
                                          trash_override=True)
        self.assertEqual(del_thumb, 2 * len(files_dir_2) + 2 * len(files_dir_1))

        # Check all files are deleted
        for file in files_dir_1 + files_dir_2:
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
            self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

    def test_flags_not_touched(self):
        """
        Test that the flags aren't touched if the file is deleted.
        """
        self.api.create_display_files(miniature=True, thumbnail=True)

        dir_1 = os.path.join(self.api.root_path, "1990", "04", "01")
        files_dir_1 = os.listdir(dir_1)

        # Set selection
        for file in files_dir_1:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            self.assertIsNotNone(flags)

            flags.sel_a = True
            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        # Delete files
        del_thumb = self.api.delete_thumb(selection=Selection(selection_type=SelectionType.SELECTION_A),
                                          trash_override=False)

        self.assertEqual(del_thumb,  2 * len(files_dir_1))

        # Check files are deleted and set the flags to be not deleted
        for file in files_dir_1:
            key = self.api.resolve_filename_to_key(file)

            # Display files deleted
            self.assertFalse(os.path.exists(self.api.db.full_miniature_path(key)))
            self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(key)))

            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            self.assertIsNotNone(flags)

            # Ensure state
            self.assertFalse(flags.has_thumbnail)
            self.assertFalse(flags.has_miniature)
            self.assertTrue(flags.sel_a)

            # Update flags
            flags.has_thumbnail = flags.has_miniature = True

            self.api.db.update_row_main_table(key=self.api.resolve_filename_to_key(file), flags=flags)

        # Delete files
        del_thumb = self.api.delete_thumb(selection=Selection(selection_type=SelectionType.SELECTION_A),
                                          trash_override=False)

        # Now nothing should be deleted
        self.assertEqual(del_thumb, 0)

        # Flags should have remained untouched
        for file in files_dir_1:
            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            self.assertIsNotNone(flags)

            # Ensure state
            self.assertTrue(flags.has_thumbnail)
            self.assertTrue(flags.has_miniature)
            self.assertTrue(flags.sel_a)
