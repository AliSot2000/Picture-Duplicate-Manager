import datetime
import json
import os
import shutil
import time
import zoneinfo

from photo_lib.custom_enum import MediaType
from .base_class import TestClassifyBase

"""
This file fully tests the following functions:
- api.move_to_duplicates
- api.move_to_trash
- api.restore_duplicate
- api.restore_trash
- api._internal_undo


The file covers 100% of the function without specific tests:
- api.db.migrate_parent_duplicate
- api.db.remove_all_tuples_with_key
- api.db.delete_row_metadata_table
- api.db.delete_row_main_table
- api.db.get_main_flags
- api.db.get_replace_data
- api.db.get_metadata_row
"""


class TestClassifyBase(unittest.TestCase):
    """
    Test all functions surrounding the perform_import method.
    """
    shadow_db: str
    temp_db: str
    media_source: str
    import_source: str

    api: Optional[PhotoAPI] = None
    tgt_table: Optional[str] = None

    @classmethod
    def setUpClass(cls):  # pragma: no cover
        cls.shadow_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shadow_db"))
        cls.temp_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_db"))
        cls.media_source = os.path.join(os.path.dirname(__file__), "..", "test_file_out")
        cls.import_source = os.path.join(os.path.dirname(__file__), "..", "scratch")
        cls.tbl_dump_dir = os.path.join(os.path.dirname(__file__), "..", "db_dump", "import")

        # Check the input files are present
        if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "test_file_out")):
            raise FileNotFoundError(
                "Need test files to test the db. Create them with the scripts/generate_dummy_media.py"
            )

        # Check and remove the past of the shadow db
        if os.path.exists(cls.shadow_db):
            shutil.rmtree(cls.shadow_db)

        # Create a fresh instance
        api = PhotoAPI(root_path=cls.shadow_db,
                      init=True,
                      init_loggers=True,
                      opt_integrity_check=True)

        tgt_table = api.prepare_directory_for_import(source_dir=os.path.join(cls.media_source, "db"))
        api.db.debug_execute(f"UPDATE `{tgt_table}` SET imported = 1 WHERE allowed = 1")
        api.perform_import(tbl_name=tgt_table)

        api.cleanup()

    @classmethod
    def tearDownClass(cls):  # pragma: no cover
        # Class teardown is the removing of the shadow db
        path = cls.shadow_db

        shutil.rmtree(path)

        delattr(cls, "shadow_db")
        delattr(cls, "temp_db")
        delattr(cls, "media_source")
        delattr(cls, "import_source")
        delattr(cls, "tbl_dump_dir")

    def setUp(self):  # pragma: no cover
        """
        Setup function creates a fresh instance of the db to run the tests against
        """
        # Part of setup is teardown of the test db
        if os.path.exists(self.temp_db):
            shutil.rmtree(self.temp_db)

        shutil.copytree(self.shadow_db, self.temp_db)

        # Part of setup is teardown of the import_source directory
        if os.path.exists(self.import_source):
            shutil.rmtree(self.import_source)

        self.api = PhotoAPI(root_path=self.temp_db,
                            init_loggers=False,
                            init=False)

        self.api.config.batch_size = 10

    def tearDown(self):  # pragma: no cover
        """
        Remove the local instance of the db.
        """
        self.api.cleanup(True)
        self.api = None

        # Part of setup is teardown of the test db
        if os.path.exists(self.temp_db):
            shutil.rmtree(self.temp_db)

        # Part of setup is teardown of the import_source directory
        if os.path.exists(self.import_source):
            shutil.rmtree(self.import_source)

    def check_table_post_migration(self):
        """
        Check the tables look the way we expect them to prior to the
        """
        dt = self.api.db.dump_duplicates_table()

        expected_dt = [
            {"key_a": 1, "key_b": 3, "delta": 0.0},
            {"key_a": 1, "key_b": 4, "delta": 0.0},
            {"key_a": 1, "key_b": 5, "delta": 0.0},

            {"key_a": 1, "key_b": 10, "delta": 0.0},
            {"key_a": 1, "key_b": 11, "delta": 0.0},
            {"key_a": 1, "key_b": 12, "delta": 0.0},

            {"key_a": 1, "key_b": 20, "delta": 0.0},
            {"key_a": 1, "key_b": 21, "delta": 0.0},
            {"key_a": 1, "key_b": 22, "delta": 0.0},
        ]

        self.assertEqual(len(dt), len(expected_dt))

        for row in dt:
            self.assertIn(row, expected_dt)

        kdt = self.api.db.dump_known_duplicates_table()

        expected_kdt = [
            {"key_a": 1, "key_b": 6, "delta": 0.0},
            {"key_a": 1, "key_b": 7, "delta": 0.0},
            {"key_a": 1, "key_b": 8, "delta": 0.0},

            {"key_a": 1, "key_b": 13, "delta": 0.0},
            {"key_a": 1, "key_b": 14, "delta": 0.0},
            {"key_a": 1, "key_b": 15, "delta": 0.0},

            {"key_a": 1, "key_b": 23, "delta": 0.0},
            {"key_a": 1, "key_b": 24, "delta": 0.0},
            {"key_a": 1, "key_b": 25, "delta": 0.0},
        ]

        self.assertEqual(len(kdt), len(expected_kdt))

        for row in kdt:
            self.assertIn(row, expected_kdt)

    def check_table_pre_migration(self, with_child: bool = False):
        """
        Check the tables look the way we expect them to prior to the
        """
        dt = self.api.db.dump_duplicates_table()

        expected_dt = [
            {"key_a": 2, "key_b": 3, "delta": 0.0},
            {"key_a": 2, "key_b": 4, "delta": 0.0},
            {"key_a": 2, "key_b": 5, "delta": 0.0},

            {"key_a": 1, "key_b": 10, "delta": 0.0},
            {"key_a": 1, "key_b": 11, "delta": 0.0},
            {"key_a": 1, "key_b": 12, "delta": 0.0},

            {"key_a": 1, "key_b": 20, "delta": 0.0},
            {"key_a": 1, "key_b": 21, "delta": 0.0},
            {"key_a": 1, "key_b": 22, "delta": 0.0},
            {"key_a": 2, "key_b": 20, "delta": 0.0},
            {"key_a": 2, "key_b": 21, "delta": 0.0},
            {"key_a": 2, "key_b": 22, "delta": 0.0},
        ]

        if with_child:
            expected_dt.append({"key_a": 1, "key_b": 2, "delta": 0.0})

        self.assertEqual(len(dt), len(expected_dt))

        for row in dt:
            self.assertIn(row, expected_dt)

        kdt = self.api.db.dump_known_duplicates_table()

        expected_kdt = [
            {"key_a": 2, "key_b": 6, "delta": 0.0},
            {"key_a": 2, "key_b": 7, "delta": 0.0},
            {"key_a": 2, "key_b": 8, "delta": 0.0},

            {"key_a": 1, "key_b": 13, "delta": 0.0},
            {"key_a": 1, "key_b": 14, "delta": 0.0},
            {"key_a": 1, "key_b": 15, "delta": 0.0},

            {"key_a": 1, "key_b": 23, "delta": 0.0},
            {"key_a": 1, "key_b": 24, "delta": 0.0},
            {"key_a": 1, "key_b": 25, "delta": 0.0},
            {"key_a": 2, "key_b": 23, "delta": 0.0},
            {"key_a": 2, "key_b": 24, "delta": 0.0},
            {"key_a": 2, "key_b": 25, "delta": 0.0},
        ]

        self.assertEqual(len(kdt), len(expected_kdt))

        for row in kdt:
            self.assertIn(row, expected_kdt)


class TestToDuplicates(TestClassifyBase):
    """
    Tests for the move_to_duplicates method.
    """

    def test_errors(self):
        """
        Check Errors are raised for the correct conditions
        """
        # Parent doesn't exist
        self.assertRaises(ValueError, lambda : self.api.move_to_duplicates(parent_key=1000, child_key=1))

        # Child doesn't exist
        self.assertRaises(ValueError, lambda:  self.api.move_to_duplicates(child_key=1000, parent_key=1))


        # Check only files which are present can be made to duplicates
        os.remove(self.api.db.db_resolve_key_to_abs_path(3))
        self.assertRaises(FileNotFoundError, lambda:  self.api.move_to_duplicates(parent_key=2, child_key=3))

        # Set the duplicate flag of key 1
        flags = self.api.db.get_main_flags(1)

        self.assertIsNotNone(flags)

        flags.duplicate = True
        self.api.db.update_row_main_table(key=1, flags=flags)

        self.assertRaises(ValueError, lambda : self.api.move_to_duplicates(parent_key=2, child_key=1))

    def test_basic(self):
        """
        Test basic changes of moving a key to the duplicates table
        """
        self.perform_basic()

    def perform_basic(self):
        """
        Perform basic move to duplicate
        """
        self.api.move_to_duplicates(child_key=2, parent_key=1)

        mr = self.api.db.get_main_row(2)
        self.assertIsNotNone(mr)

        # File in trash
        self.assertTrue(os.path.exists(os.path.join(self.api.db.get_trash_dir(), mr.db_name)))

        # Flag is set to duplicates
        self.assertTrue(mr.flags.duplicate)

        # Parent is set correctly
        self.assertEqual(mr.parent, 1)

        # No google metadata
        self.assertIsNone(mr.google_metadata)

        # Check the metadata
        self.assertTrue(mr.flags.org_google_metadata)

        # No children
        self.assertEqual(0, self.api.db.get_number_of_children(2))

        # No entries in duplicates tables
        self.assertEqual({}, self.api.db.get_duplicates(key=2, known=False))
        self.assertEqual({}, self.api.db.get_duplicates(key=2, known=True))

        # metadata row exists
        mdr = self.api.db.get_metadata_row(2)

        # Metadata row should exist
        self.assertIsNotNone(mdr)

        # Indicator should be set
        self.assertEqual(mdr.replaced, MediaType.DUPLICATE)

    def test_warning_with_trash(self):
        """
        Test logging call when parent is trashed
        """
        pflags = self.api.db.get_main_flags(1)
        self.assertIsNotNone(pflags)

        pflags.trashed = True
        self.api.db.update_row_main_table(key=1, flags=pflags)

        self.perform_basic()

    def test_children(self):
        """
        Test movement to duplicates but the key we mark as duplicate has children
        """
        # Set the children first
        self.api.db.update_row_main_table(key=3, parent=2)
        self.api.db.update_row_main_table(key=4, parent=2)
        self.api.db.update_row_main_table(key=5, parent=2)

        # Perform the basic movement operation
        self.perform_basic()

        # Check children now point to parent
        for i in (3,4,5):
            with self.subTest(f"Test Parent; target key {i}"):
                row = self.api.db.get_main_row(i)

                # Row should exist
                self.assertIsNotNone(row)

                # Check parent is set correctly.
                self.assertEqual(row.parent, 1)

    def test_duplicates_migration(self):
        """
        Test that the duplicates of the key are correctly migrated in the tables.
        """
        # Duplicates
        # Key to move 2
        # Parent 1
        # Children of 2, duplicates,  (3,4,5)
        self.api.db.add_default_duplicate(key_a=[2, 2, 2], key_b=[3, 4, 5])

        # Children of 2, known_duplicates, (6,7,8)
        self.api.db.add_known_duplicate(key_a=[2, 2, 2], key_b=[6 ,7 ,8])

        # Children of 1, duplicates, (10, 11, 12)
        self.api.db.add_default_duplicate(key_a=[1, 1, 1], key_b=[10, 11, 12])

        # Children of 1, known_duplicates (13, 14, 15)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1], key_b=[13, 14, 15])

        # Children of 1, 2 duplicates (20, 21, 22)
        self.api.db.add_default_duplicate(key_a=[20, 21, 22, 20, 21, 22], key_b=[1, 1, 1, 2, 2, 2])

        # Children of 1, 2 known_duplicates (23, 24, 25)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1, 2, 2, 2], key_b=[23, 24, 25, 23, 24, 25])

        self.check_table_pre_migration()

        self.api.move_to_duplicates(child_key=2, parent_key=1)

        mr = self.api.db.get_main_row(2)
        self.assertIsNotNone(mr)

        # File in trash
        self.assertTrue(os.path.exists(os.path.join(self.api.db.get_trash_dir(), mr.db_name)))

        # Flag is set to duplicates
        self.assertTrue(mr.flags.duplicate)

        # Parent is set correctly
        self.assertEqual(mr.parent, 1)

        # No google metadata
        self.assertIsNone(mr.google_metadata)

        # Check the metadata
        self.assertTrue(mr.flags.org_google_metadata)

        # No children
        self.assertEqual(0, self.api.db.get_number_of_children(2))

        # INFO: duplicates and known_duplicates are checked later.

        # metadata row exists
        mdr = self.api.db.get_metadata_row(2)

        # Metadata row should exist
        self.assertIsNotNone(mdr)

        # Indicator should be set
        self.assertEqual(mdr.replaced, MediaType.DUPLICATE)

        # Check tables after migration
        self.check_table_post_migration()

    def test_duplicates_migration_child_of_parent(self):
        """
        Test that the duplicates of the key are correctly migrated in the tables. Here, we also have the child key
        being a child of the parent in the known_duplicates_table
        """
        # Duplicates
        # Key to move 2
        # Parent 1
        # Children of 2, duplicates,  (3,4,5)
        self.api.db.add_default_duplicate(key_a=[2, 2, 2], key_b=[3, 4, 5])

        # Children of 2, known_duplicates, (6,7,8)
        self.api.db.add_known_duplicate(key_a=[2, 2, 2], key_b=[6 ,7 ,8])

        # Children of 1, duplicates, (10, 11, 12)
        self.api.db.add_default_duplicate(key_a=[1, 1, 1], key_b=[10, 11, 12])

        # Children of 1, known_duplicates (13, 14, 15)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1], key_b=[13, 14, 15])

        # Children of 1, 2 duplicates (20, 21, 22)
        self.api.db.add_default_duplicate(key_a=[20, 21, 22, 20, 21, 22], key_b=[1, 1, 1, 2, 2, 2])

        # Children of 1, 2 known_duplicates (23, 24, 25)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1, 2, 2, 2], key_b=[23, 24, 25, 23, 24, 25])

        # Add known duplicates for test
        self.api.db.add_default_duplicate(key_a=1, key_b=2)

        self.check_table_pre_migration(with_child=True)

        # Perform actual move
        self.api.move_to_duplicates(child_key=2, parent_key=1)

        mr = self.api.db.get_main_row(2)
        self.assertIsNotNone(mr)

        # File in trash
        self.assertTrue(os.path.exists(os.path.join(self.api.db.get_trash_dir(), mr.db_name)))

        # Flag is set to duplicates
        self.assertTrue(mr.flags.duplicate)

        # Parent is set correctly
        self.assertEqual(mr.parent, 1)

        # No google metadata
        self.assertIsNone(mr.google_metadata)

        # Check the metadata
        self.assertTrue(mr.flags.org_google_metadata)

        # No children
        self.assertEqual(0, self.api.db.get_number_of_children(2))

        # metadata row exists
        mdr = self.api.db.get_metadata_row(2)

        # Metadata row should exist
        self.assertIsNotNone(mdr)

        # Indicator should be set
        self.assertEqual(mdr.replaced, MediaType.DUPLICATE)
        # Check tables after migration
        self.check_table_post_migration()

    def test_disp_media_removed(self):
        """
        Check that the thumbnails and miniatures are removed
        """
        self.api.create_display_files(thumbnail=True, miniature=True)

        self.perform_basic()

        self.assertFalse(os.path.exists(self.api.db.full_thumbnail_path(2)))
        self.assertFalse(os.path.exists(self.api.db.full_miniature_path(2)))

    def test_google_metadata(self):
        """
        Add a json string to the google metadata for testing
        """
        mr = self.api.db.get_main_row(2)

        # Check current state
        self.assertIsNone(mr.google_metadata)
        self.assertTrue(mr.flags.org_google_metadata)

        gfmd = {"key1": "value",
             "key2": 1,
             "key3": 1.2,
             "key4": True,
             "key5": None,
             "key6": [],
             "key7": {"None": 21},
             "key8": "This is a string with a problematic character ' "}

        # Add the google metadata
        self.api.db.update_row_main_table(key=2, google_metadata=json.dumps(gfmd))

        # Main Operation of moving to duplicates
        self.api.move_to_duplicates(child_key=2, parent_key=1)

        mr = self.api.db.get_main_row(2)
        self.assertIsNotNone(mr)

        # File in trash
        self.assertTrue(os.path.exists(os.path.join(self.api.db.get_trash_dir(), mr.db_name)))

        # Flag is set to duplicates
        self.assertTrue(mr.flags.duplicate)

        # Parent is set correctly
        self.assertEqual(mr.parent, 1)

        # No google metadata
        self.assertEqual(mr.google_metadata, json.dumps(gfmd))

        # Check the metadata
        self.assertTrue(mr.flags.org_google_metadata)

        # No children
        self.assertEqual(0, self.api.db.get_number_of_children(2))

        # No entries in duplicates tables
        self.assertEqual({}, self.api.db.get_duplicates(key=2, known=False))
        self.assertEqual({}, self.api.db.get_duplicates(key=2, known=True))

        # metadata row exists
        mdr = self.api.db.get_metadata_row(2)

        # Metadata row should exist
        self.assertIsNotNone(mdr)

        # Indicator should be set
        self.assertEqual(mdr.replaced, MediaType.DUPLICATE)

        # Check the parent now
        par_row = self.api.db.get_main_row(1)
        self.assertIsNotNone(par_row)

        # Check flags
        self.assertFalse(par_row.flags.org_google_metadata)

        # Check the metadata
        self.assertEqual(par_row.google_metadata, json.dumps(gfmd))


class TestToTrash(TestClassifyBase):
    """
    Tests for the move_to_trash method.
    """

    def test_errors(self):
        """
        Test that all error conditions are correctly handled.
        """
        self.assertRaises(ValueError, lambda: self.api.move_to_trash(1000))

        # check trash flag error
        mr = self.api.db.get_main_row(key=1)
        self.assertIsNotNone(mr)

        mr.flags.trashed = True
        self.api.db.update_row_main_table(key=1, flags=mr.flags)

        # raise actual error
        self.assertRaises(ValueError, lambda: self.api.move_to_trash(1))

        # check duplicate flag error
        mr = self.api.db.get_main_row(key=2)
        self.assertIsNotNone(mr)

        mr.flags.duplicate = True
        self.api.db.update_row_main_table(key=2, flags=mr.flags)

        # raise actual error
        self.assertRaises(ValueError, lambda: self.api.move_to_trash(2))

        # Remove the third key
        os.remove(self.api.db.db_resolve_key_to_abs_path(3))

        self.assertRaises(FileNotFoundError, lambda: self.api.move_to_trash(3))

    def test_regular_move(self):
        """
        Test that the file is moved and the thumbnails are created
        """
        self.api.move_to_trash(key=1, overwrite=False)

        self.perform_basic_checks()

    def perform_basic_checks(self):
        """
        Performs the basic operation of moving a file to trash
        """
        mr = self.api.db.get_main_row(1)
        self.assertIsNotNone(mr)

        # Check the file is in the trash
        self.assertTrue(os.path.exists(os.path.join(self.api.db.get_trash_dir(), mr.db_name)))

        # Check the trash flag is set and the present flag is set
        self.assertTrue(mr.flags.trashed)
        self.assertTrue(mr.flags.present)

        # Check the metadata row exists and is set to trash
        mdr = self.api.db.get_metadata_row(1)
        self.assertIsNotNone(mdr)

        self.assertEqual(mdr.replaced, MediaType.TRASH)

        # Ensure the images exist
        self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(1)))
        self.assertTrue(os.path.exists(self.api.db.full_miniature_path(1)))

    def test_move_with_overwrite(self):
        """
        Check that the display files are created after the current datetime
        """
        # Create the display files
        self.api.create_display_files(miniature=True, thumbnail=True)

        default_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()
        time_limit = datetime.datetime.now(zoneinfo.ZoneInfo(default_tz))

        self.api.move_to_trash(key=1, overwrite=True)

        self.perform_basic_checks()

        # Ensure the file is created newer
        created_min = os.stat(self.api.db.full_miniature_path(1)).st_ctime
        self.assertLess(time_limit, datetime.datetime.fromtimestamp(created_min, zoneinfo.ZoneInfo(default_tz)))

        # Ensure the file is created newer
        created_thumb = os.stat(self.api.db.full_thumbnail_path(1)).st_ctime
        self.assertLess(time_limit, datetime.datetime.fromtimestamp(created_thumb, zoneinfo.ZoneInfo(default_tz)))

    def test_no_update_display_files(self):
        """
        Test that display files aren't created if they exist already
        """
        # Create the display files
        self.api.create_display_files(miniature=True, thumbnail=True, overwrite=False)

        time.sleep(1)

        now = time.time()

        self.api.move_to_trash(key=1, overwrite=False)

        self.perform_basic_checks()

        # Ensure the file is created newer
        created_min = os.stat(self.api.db.full_miniature_path(1)).st_ctime
        # created_min_dt = datetime.datetime.fromtimestamp(created_min, zoneinfo.ZoneInfo(default_tz))
        # self.assertGreater(time_limit, created_min_dt)
        self.assertGreater(now, created_min)

        # Ensure the file is created newer
        created_thumb = os.stat(self.api.db.full_thumbnail_path(1)).st_ctime
        # created_thumb_dt = datetime.datetime.fromtimestamp(created_thumb, zoneinfo.ZoneInfo(default_tz))
        # self.assertGreater(time_limit, created_thumb_dt)
        self.assertGreater(now, created_thumb)


class TestRestore(TestClassifyBase):
    """
    Test the restore function which allows the undo of the to trash action or the undo of the to duplicates action
    """

    def test_errors(self):
        """
        Check that errors are  raised on the right conditions
        """
        self.api.db.delete_row_main_table(40)

        self.api.db.delete_row_main_table(1000, assert_exists=False)

        # Check main row not found
        self.assertRaises(ValueError, lambda : self.api.restore_trash(40))

        self.api.db.delete_row_metadata_table(key=1)

        self.api.db.delete_row_main_table(key=1000, assert_exists=False)

        # Metadata row not found
        self.assertRaises(ValueError, lambda: self.api.restore_trash(1))

        # file not found
        self.api.move_to_trash(2)

        # delete it
        os.remove(self.api.resolve_key_to_path(2))

        self.assertRaises(FileNotFoundError, lambda: self.api.restore_trash(2))

        # Create a duplicate and a trash file and check raises

        self.api.move_to_trash(10)
        self.api.move_to_duplicates(11, 10)

        # Check wrongly attributed calls
        self.assertRaises(ValueError, lambda: self.api.restore_trash(11))
        self.assertRaises(ValueError, lambda: self.api.restore_duplicate(10))

        # Check file exists at destination
        cur_path = self.api.resolve_key_to_path(20)
        self.api.move_to_trash(20)

        shutil.copy2(self.api.resolve_key_to_path(20), cur_path)
        self.assertRaises(FileExistsError, lambda: self.api.restore_trash(20))

    def test_normal_restore(self):
        """
        Test the restore functionality for a basic case
        """
        # 1 parent, 2 duplicate, 3 trash
        self.api.move_to_duplicates(child_key=2, parent_key=1)
        self.api.move_to_trash(3)

        self.api.restore_trash(3, create_display_files=False)
        self.api.restore_duplicate(2, create_display_files=False)

        # INFO: The to trash and to replaced functionality is tested in different classes,
        #   we don't check that the files were moved to trash and replaced correctly.
        for i in (2, 3):
            with self.subTest(f"Test restore, target key {i}"):
                mr = self.api.db.get_main_row(i)

                # Check row and check flags
                self.assertIsNotNone(mr)
                self.assertTrue(mr.flags.present)
                self.assertFalse(mr.flags.trashed)
                self.assertFalse(mr.flags.duplicate)

                # Check parent
                self.assertIsNone(mr.parent)


                mdr = self.api.db.get_metadata_row(i)
                self.assertIsNotNone(mdr)

                self.assertEqual(mdr.replaced, MediaType.MAIN)

    def test_normal_restore_with_display_files(self):
        """
        Check regular restore procedure now with creating display files.
        """
        # 1 parent, 2 duplicate, 3 trash
        self.api.move_to_duplicates(child_key=2, parent_key=1)
        self.api.move_to_trash(3)

        self.api.restore_trash(3, create_display_files=True)
        self.api.restore_duplicate(2, create_display_files=True)

        # INFO: The to trash and to replaced functionality is tested in different classes,
        #   we don't check that the files were moved to trash and replaced correctly.
        for i in (2, 3):
            with self.subTest(f"Test restore, target key {i}"):
                mr = self.api.db.get_main_row(i)

                # Check row and check flags
                self.assertIsNotNone(mr)
                self.assertTrue(mr.flags.present)
                self.assertFalse(mr.flags.trashed)
                self.assertFalse(mr.flags.duplicate)

                # Check display file flags
                self.assertTrue(mr.flags.has_thumbnail)
                self.assertTrue(mr.flags.has_miniature)

                # Check parent
                self.assertIsNone(mr.parent)

                mdr = self.api.db.get_metadata_row(i)
                self.assertIsNotNone(mdr)

                self.assertEqual(mdr.replaced, MediaType.MAIN)

                # Check that the paths exist
                self.assertTrue(os.path.exists(self.api.db.full_thumbnail_path(i)))
                self.assertTrue(os.path.exists(self.api.db.full_miniature_path(i)))

    def test_custom_dir_restore(self):
        """
        Check restore with a custom directory
        """
        tgt_dir = os.path.join(self.media_source, "hash_change_1")
        tbl_name = self.api.prepare_directory_for_import(source_dir=tgt_dir)

        self.api.db.debug_execute(f"UPDATE `{tbl_name}` SET imported = 1")

        # Perform import to custom directory
        self.api.perform_import(tbl_name=tbl_name, _dest_dir="import/custom/directory")

        # Move a specific file to trash from the given import table
        self.api.move_to_trash(158)

        self.api.restore_trash(158)

        mr = self.api.db.get_main_row(158)

        # Check row and check flags
        self.assertIsNotNone(mr)
        self.assertTrue(mr.flags.present)
        self.assertFalse(mr.flags.trashed)
        self.assertFalse(mr.flags.duplicate)

        # Check parent
        self.assertIsNone(mr.parent)

        mdr = self.api.db.get_metadata_row(158)
        self.assertIsNotNone(mdr)

        self.assertEqual(mdr.replaced, MediaType.MAIN)

        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, "import/custom/directory", mr.db_name)))

    def test_no_effect_on_dup_tables_restore_duplicates(self):
        """
        Check that restore doesn't perform any chanages on the duplicates tables.
        """
        # Duplicates
        # Key to move 2
        # Parent 1
        # Children of 2, duplicates,  (3,4,5)
        self.api.db.add_default_duplicate(key_a=[2, 2, 2], key_b=[3, 4, 5])

        # Children of 2, known_duplicates, (6,7,8)
        self.api.db.add_known_duplicate(key_a=[2, 2, 2], key_b=[6 ,7 ,8])

        # Children of 1, duplicates, (10, 11, 12)
        self.api.db.add_default_duplicate(key_a=[1, 1, 1], key_b=[10, 11, 12])

        # Children of 1, known_duplicates (13, 14, 15)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1], key_b=[13, 14, 15])

        # Children of 1, 2 duplicates (20, 21, 22)
        self.api.db.add_default_duplicate(key_a=[20, 21, 22, 20, 21, 22], key_b=[1, 1, 1, 2, 2, 2])

        # Children of 1, 2 known_duplicates (23, 24, 25)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1, 2, 2, 2], key_b=[23, 24, 25, 23, 24, 25])

        # Add known duplicates for test
        self.api.db.add_default_duplicate(key_a=1, key_b=2)

        self.check_table_pre_migration(with_child=True)

        # Perform actual move
        self.api.move_to_duplicates(child_key=2, parent_key=1)

        self.check_table_post_migration()

        self.api.restore_duplicate(2)

        self.check_table_post_migration()

    def test_no_effect_on_dup_tables_restore_trash(self):
        """
        Check that restoring after having moved a file to trash doesn't affect the duplicates tables.
        """
        # Duplicates
        # Key to move 2
        # Parent 1
        # Children of 2, duplicates,  (3,4,5)
        self.api.db.add_default_duplicate(key_a=[2, 2, 2], key_b=[3, 4, 5])

        # Children of 2, known_duplicates, (6,7,8)
        self.api.db.add_known_duplicate(key_a=[2, 2, 2], key_b=[6, 7, 8])

        # Children of 1, duplicates, (10, 11, 12)
        self.api.db.add_default_duplicate(key_a=[1, 1, 1], key_b=[10, 11, 12])

        # Children of 1, known_duplicates (13, 14, 15)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1], key_b=[13, 14, 15])

        # Children of 1, 2 duplicates (20, 21, 22)
        self.api.db.add_default_duplicate(key_a=[20, 21, 22, 20, 21, 22], key_b=[1, 1, 1, 2, 2, 2])

        # Children of 1, 2 known_duplicates (23, 24, 25)
        self.api.db.add_known_duplicate(key_a=[1, 1, 1, 2, 2, 2], key_b=[23, 24, 25, 23, 24, 25])

        # Add known duplicates for test
        self.api.db.add_default_duplicate(key_a=1, key_b=2)

        self.check_table_pre_migration(with_child=True)

        # Perform actual move
        self.api.move_to_trash(2)

        self.check_table_pre_migration(with_child=True)

        self.api.restore_trash(2)

        self.check_table_pre_migration(with_child=True)