import os.path

from photo_lib.errors_and_warnings import CorruptDatabase
from base_class import TestClassifyBase


"""
Test the forget functionality of the api.

This file fully tests the following functions:
- api.forget_file
- api._internal_forget

The file covers 100% of the function without specific tests:
- api.db.get_main_flags
- api.db.list_children
- api.resolve_key_to_path
- api.db.delete_file_association
- api.db.delete_row_metadata_table
- api.db.remove_all_tuples_with_key
- api.db.delete_row_main_table
"""


class TestForget(TestClassifyBase):
    """
    Check the forget functionality of the api.
    """
    def test_errors(self):
        """
        Check that the errors of the forget function are raised correctly
        """
        # Key doesn't exist
        self.assertRaises(ValueError, lambda : self.api.forget_file(1000))

        # Duplicate chaining
        self.api.db.update_row_main_table(key=3, parent=2)
        self.api.db.update_row_main_table(key=2, parent=1)

        self.assertRaises(CorruptDatabase, lambda : self.api.forget_file(1))

    def test_child_warning(self):
        """
        Check that the child outputs a warning if the duplicate flag isn't set
        """
        self.api.db.update_row_main_table(key=2, parent=1)

        paths = {1: self.api.resolve_key_to_path(1), 2:self.api.resolve_key_to_path(2)}

        # Perform forget
        self.api.forget_file(1)

        for i in (1,2):
            with self.subTest(f"Test forget, target key {i}"):
                self.check_successfully_forgotten(i, paths[i])

    def check_successfully_forgotten(self, key: int, prev_path: str):
        """
        Function to verify a file was properly forgotten.
        """
        # check file is not present
        self.assertFalse(os.path.exists(prev_path))

        # check disp files aren't present
        self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(key)))
        self.assertFalse(os.path.exists(self.api.db.full_miniature_path(key)))

        # Check there's no associated hash
        self.assertEqual(self.api.db.get_all_hashes_of_file(key), [])

        # Check there's no content in the caches
        self.assertIsNone(self.api.resolve_key_to_path(key))
        self.assertIsNone(self.api.filename_to_key(os.path.basename(prev_path)))

        # Check no row in main or metadata table
        self.assertIsNone(self.api.db.get_main_row(key))
        self.assertIsNone(self.api.db.get_metadata_row(key))

        self.assertEqual(self.api.db.get_duplicates(key, known=True), {})
        self.assertEqual(self.api.db.get_duplicates(key, known=False), {})

    def test_regular_forget(self):
        """
        Test forgetting with a single file, in main, in trash, in duplicates
        """
        # Check regular file
        path1 = self.api.resolve_key_to_path(1)
        self.api.forget_file(1)
        self.check_successfully_forgotten(1, path1)

        # Check a file from the trash
        self.api.move_to_trash(key=2)
        path2 = self.api.resolve_key_to_path(2)
        self.api.forget_file(2)
        self.check_successfully_forgotten(2, path2)

        # Check a file from duplicates
        self.api.move_to_duplicates(child_key=3, parent_key=4)
        path3 = self.api.resolve_key_to_path(3)
        self.api.forget_file(3)
        self.check_successfully_forgotten(3, path3)

    def test_forget_with_dips_files(self):
        """
        Check forgetting if display files are present.
        """
        self.api.create_display_files(miniature=True, thumbnail=True)

        path = self.api.resolve_key_to_path(1)
        self.api.forget_file(1)

        self.check_successfully_forgotten(1, path)

    def test_entries_in_dup_tables(self):
        """
        Check that the entries in the duplicates tables are deleted
        """
        # Add rows to known table
        self.api.db.add_known_duplicate(key_a=[1, 1, 1], key_b=[2, 3, 4])

        # Add rows to default duplicates
        self.api.db.add_default_duplicate(key_a=[1, 1, 1], key_b=[5, 6, 7])

        # INFO: We don't test the functions any further. duplicates function are tested in different file.

        path = self.api.resolve_key_to_path(1)
        self.api.forget_file(1)

        self.check_successfully_forgotten(1, path)

    def test_file_does_not_exist(self):
        """
        Check that the process works even if the file is already removed
        """
        path = self.api.resolve_key_to_path(1)
        os.remove(path)

        self.api.forget_file(1)
        self.check_successfully_forgotten(1, path)