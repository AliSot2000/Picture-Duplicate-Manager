import os.path

from base_class import TestClassifyBase

from typing import List, Tuple

from photo_lib.custom_enum import MediaType
from photo_lib.errors_and_warnings import ImplementationError


# TODO assert count
"""
This file fully tests the following functions:
- api.empty_trash
- api._empty_trash
"""


class TestEmptyTrash(TestClassifyBase):
    """
    Test the empty trash functionality.
    """
    def get_dir_0(self):
        """
        Get the files of 1990/04/01
        """
        path = os.path.join(self.api.root_path, "1990", "04", "01")
        files = os.listdir(path)

        return path, files

    def get_dir_1(self):
        """
        Get the files of 1990/05/01
        """
        path = os.path.join(self.api.root_path, "1990", "05", "01")
        files = os.listdir(path)

        return path, files

    def get_dir_2(self):
        """
        Get the files of 1990/06/01
        """
        path = os.path.join(self.api.root_path, "1990", "06", "01")
        files = os.listdir(path)

        return path, files

    def setup_dir_0(self) -> Tuple[str, List[str]]:
        """
        Move dir 1990/04/01 to trash and check all things are move to trash
        """
        path, files = self.get_dir_0()
        self.assertEqual(len(files), 8)

        # Actually move files to trash
        for file in files:
            self.api.move_to_trash(self.api.resolve_filename_to_key(file))

        # Check the files are contained in the trash dir
        trash_files = os.listdir(self.api.db.get_trash_dir())
        for file in files:
            self.assertIn(file, trash_files)

        # Check thumbnails are present
        for file in files:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        return path, files

    def setup_dir_1(self) -> Tuple[str, List[str]]:
        """
        Move dir 1990/05/01 to trash and check all things are moved to trash
        """
        path, files = self.get_dir_1()
        self.assertEqual(len(files), 16)

        for file in files:
            self.api.move_to_trash(self.api.resolve_filename_to_key(file))

        # check that all files were moved
        self.assertListEqual(sorted(os.listdir(self.api.db.get_trash_dir())), sorted(files))

        # Check thumbnails are present
        for file in files:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        return path, files

    def setup_dir_2(self) -> Tuple[str, List[str]]:
        """
        Move dir 1990/06/01 to trash via marking them as duplicates.
        """
        path, files = self.get_dir_2()
        self.assertEqual(len(files), 32)

        for file in files:
            self.api.move_to_duplicates(child_key=self.api.resolve_filename_to_key(file), parent_key=1)

        # check that all files were moved
        trash_files = os.listdir(self.api.db.get_trash_dir())
        for file in files:
            self.assertIn(file, trash_files)

        # Check thumbnails are present
        for file in files:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        return path, files

    def test_basic_empty_trash(self):
        """
        Test if a directory is trashed, it is emptied afterwards
        """
        path0, files0 = self.get_dir_0()
        self.check_flags_main_table(duplicate=False, trashed=False, filenames=files0)
        self.check_metadata_table(state="main", files=files0)

        path, files = self.setup_dir_0()

        # Check the state of the rows
        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files)
        self.check_metadata_table(state="trash", files=files)

        self.api.empty_trash()

        # Check trash is empty
        trash_files = os.listdir(self.api.db.get_trash_dir())
        for file in files:
            self.assertNotIn(file, trash_files)

        # check no files exist
        for file in files:
            self.assertFalse(os.path.exists(os.path.join(self.api.db.get_trash_dir(), file)))

        for file in files:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files)
        self.check_metadata_table(state="deleted", files=files)

    def test_basic_empty_trash_with_duplicates(self):
        """
        Test empty trash works with duplicates
        """
        path1, files1 = self.get_dir_2()
        self.check_flags_main_table(duplicate=False, trashed=False, filenames=files1)
        self.check_metadata_table(state="main", files=files1)

        path, files = self.setup_dir_2()
        self.check_flags_main_table(duplicate=True, trashed=False, filenames=files)
        self.check_metadata_table(state="duplicates", files=files)

        self.api.empty_trash()

        self.assertEqual(len(os.listdir(self.api.db.get_trash_dir())), 0)

        for file in files:
            self.assertFalse(os.path.exists(os.path.join(self.api.db.get_trash_dir(), file)))

        for file in files:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        self.check_flags_main_table(duplicate=True, trashed=False, filenames=files)
        self.check_metadata_table(state="deleted", files=files)

    def test_both(self):
        """
        Test deletion with both present.
        """
        path1, files1 = self.get_dir_1()
        path2, files2 = self.get_dir_2()

        self.check_flags_main_table(duplicate=False, trashed=False, filenames=files1 + files2)
        self.check_metadata_table(state="main", files=files1 + files2)

        path1, files1 = self.setup_dir_1()
        path2, files2 = self.setup_dir_2()

        # Check the files after they were setup
        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files1)
        self.check_flags_main_table(duplicate=True, trashed=False, filenames=files2)

        self.check_metadata_table(state="duplicates", files=files2)
        self.check_metadata_table(state="trash", files=files1)

        self.api.empty_trash()

        for file in files1 + files2:
            self.assertFalse(os.path.exists(os.path.join(self.api.db.get_trash_dir(), file)))

        # Check trash thumbs exist
        for file in files1:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        for file in files2:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files1)
        self.check_flags_main_table(duplicate=True, trashed=False, filenames=files2)

        self.check_metadata_table(state="deleted", files=files1 + files2)

    def test_call_twice(self):
        """
        Test trash emptying with two calls to empty trash
        """
        path, files = self.get_dir_0()

        self.check_flags_main_table(duplicate=False, trashed=False, filenames=files)
        self.check_metadata_table(state="main", files=files)

        # First Files moved to trash
        path0, files0 = self.setup_dir_0()

        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files0)
        self.check_metadata_table(state="trash", files=files0)

        self.api.empty_trash()

        for file in files0:
            self.assertFalse(os.path.exists(os.path.join(self.api.db.get_trash_dir(), file)))

        # Check trash thumbs exist
        for file in files0:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files0)
        self.check_metadata_table(state="deleted", files=files0)

        # Test the new files
        path1, files1 = self.get_dir_1()
        path2, files2 = self.get_dir_2()

        self.check_flags_main_table(duplicate=False, trashed=False, filenames=files1 + files2)
        self.check_metadata_table(state="main", files=files1 + files2)

        # Second helping if files moved to trash
        path1, files1 = self.setup_dir_1()
        path2, files2 = self.setup_dir_2()

        # Test the state of dir 0
        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files0)
        self.check_metadata_table(state="deleted", files=files0)

        # Test the state fo dir 1 and dir 2
        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files1)
        self.check_flags_main_table(duplicate=True, trashed=False, filenames=files2)

        self.check_metadata_table(state="duplicates", files=files2)
        self.check_metadata_table(state="trash", files=files1)

        self.api.empty_trash()

        for file in files1 + files2 + files0:
            self.assertFalse(os.path.exists(os.path.join(self.api.db.get_trash_dir(), file)))

        # Check trash thumbs exist
        for file in files1:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        for file in files2:
            with self.subTest(f"Testing Display Files for {file}"):
                self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(self.api.resolve_filename_to_key(file))))
                self.assertFalse(os.path.exists(self.api.db.full_miniature_path(self.api.resolve_filename_to_key(file))))

        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files0)
        self.check_flags_main_table(duplicate=False, trashed=True, filenames=files1)
        self.check_flags_main_table(duplicate=True, trashed=False, filenames=files2)

        self.check_metadata_table(state="deleted", files=files0 + files1 + files2)

    def check_flags_main_table(self, duplicate: bool, trashed: bool, filenames: List[str]):
        """
        Check the flags for a given list of file names
        """
        for file in filenames:

            flags = self.api.db.get_main_flags(self.api.resolve_filename_to_key(file))

            self.assertEqual(flags.duplicate, duplicate)
            self.assertEqual(flags.trashed, trashed)

    def check_metadata_table(self, state: str, files: List[str]):
        """
        Check the state of the rows in the metadata table
        """
        assert state in ("main", "duplicates", "trash", "deleted")

        for file in files:
            mdr = self.api.db.get_metadata_row(self.api.resolve_filename_to_key(file))

            if state.lower() == "main":
                self.assertEqual(mdr.replaced, MediaType.MAIN)
            elif state.lower() == "duplicates":
                self.assertEqual(mdr.replaced, MediaType.DUPLICATE)
            elif state.lower() == "trash":
                self.assertEqual(mdr.replaced, MediaType.TRASH)
            elif state.lower() == "deleted":
                self.assertIsNone(mdr)
            else: # pragma: no cover
                raise ImplementationError("Uncovered case")

