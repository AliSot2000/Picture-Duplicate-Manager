import os.path
import shutil
import unittest
from typing import Optional

from photo_lib.custom_enum import Allowed
from photo_lib.new_photo_model import PhotoAPI


class TestAPIPrepareDirectoryForImport(unittest.TestCase):
    shadow_db: str
    temp_db: str
    media_source: str
    import_source: str

    api: Optional[PhotoAPI] = None

    @classmethod
    def setUpClass(cls):
        cls.shadow_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "shadow_db"))
        cls.temp_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_db"))
        cls.media_source = os.path.join(os.path.dirname(__file__), "test_file_out")
        cls.import_source = os.path.join(os.path.dirname(__file__), "scratch")

        # Check the input files are present
        if not os.path.exists(os.path.join(os.path.dirname(__file__), "test_file_out")):
            raise FileNotFoundError(
                "Need test files to test the db. Create them with the scripts/generate_dummy_media.py"
            )

        # Check and remove the past of the shadow db
        if os.path.exists(cls.shadow_db):
            shutil.rmtree(cls.shadow_db)

        # Create a fresh instaance
        db = PhotoAPI(root_path=cls.shadow_db,
                      init=True,
                      opt_integrity_check=True)

        db.cleanup()

    @classmethod
    def tearDownClass(cls):
        # Class teardown is the removing of the shadow db
        path = cls.shadow_db

        shutil.rmtree(path)

        delattr(cls, "shadow_db")
        delattr(cls, "temp_db")
        delattr(cls, "media_source")
        delattr(cls, "import_source")

    def setUp(self):
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

    def tearDown(self):
        """
        Remove the local instance of the db.
        """
        # Part of setup is teardown of the test db
        if os.path.exists(self.temp_db):
            shutil.rmtree(self.temp_db)

        # Part of setup is teardown of the import_source directory
        if os.path.exists(self.import_source):
            shutil.rmtree(self.import_source)

    def test_verify_external_dir(self):
        """
        Test all possible wrong import sources and check that they are cought every time
        """
        rel_root = "foo/bar/baz"
        root_file = "/foo/bar/baz.txt"
        child_of_root = os.path.join(self.temp_db, "some_dir")
        os.makedirs(child_of_root, exist_ok=True)

        db = PhotoAPI(root_path=self.temp_db)

        child_of_temp = os.path.join(db.db.get_temp_dir(), "some_dir")
        child_of_thumb = os.path.join(db.db.get_thumb_dir(), "some_dir")
        child_of_trash = os.path.join(db.db.get_trash_dir(), "some_dir")

        os.makedirs(child_of_temp, exist_ok=True)
        os.makedirs(child_of_thumb, exist_ok=True)
        os.makedirs(child_of_trash, exist_ok=True)

        # Check the default problems
        self.assertRaises(TypeError, lambda: db.prepare_directory_for_import(source_dir=rel_root))
        self.assertRaises(TypeError, lambda: db.prepare_directory_for_import(source_dir=root_file))
        self.assertRaises(ValueError, lambda: db.prepare_directory_for_import(source_dir=child_of_root))

        # Check the db directories
        self.assertRaises(ValueError, lambda: db.prepare_directory_for_import(source_dir=child_of_temp))
        self.assertRaises(ValueError, lambda: db.prepare_directory_for_import(source_dir=child_of_thumb))
        self.assertRaises(ValueError, lambda: db.prepare_directory_for_import(source_dir=child_of_trash))

        db.cleanup(fast=True)

    def test_append_purge_errors(self):
        """
        Test alternate possibilities with append and purge set
        """
        db = PhotoAPI(root_path=self.temp_db)
        db_dir = os.path.join(self.media_source, "db")

        # Both not allowed
        self.assertRaises(ValueError, lambda : db.prepare_directory_for_import(source_dir=db_dir,
                                                                               append=True,
                                                                               purge=True))

        # Table empty
        self.assertRaises(ValueError, lambda : db.prepare_directory_for_import(source_dir=db_dir,
                                                                               append=True,
                                                                               purge=False))

        # Table empty
        self.assertRaises(ValueError, lambda : db.prepare_directory_for_import(source_dir=db_dir,
                                                                               append=False,
                                                                               purge=True))

        # Test table exists
        self.assertRaises(ValueError, lambda : db.prepare_directory_for_import(source_dir=db_dir,
                                                                               append=True,
                                                                               purge=False,
                                                                               tbl_name="some_table"))

        # Actually perform import:
        tbl = db.prepare_directory_for_import(source_dir=db_dir,
                                              append=False,
                                              purge=False)

        # Error, Table Exists
        self.assertRaises(ValueError, lambda : db.prepare_directory_for_import(source_dir=db_dir,
                                                                               tbl_name=tbl))


        # Perform import
        db.cleanup(fast=True)

    def test_append(self):
        """
        Test that appending to import table works
        """
        db = PhotoAPI(root_path=self.temp_db)

        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = db.prepare_directory_for_import(source_dir=self.import_source)
        tbl_size = db.db.get_size_of_single_import_table(tbl)

        self.assertEqual(tbl_size, 152)

        # Test empty append
        db.prepare_directory_for_import(source_dir=self.import_source, append=True, tbl_name=tbl)
        tbl_size_1 = db.db.get_size_of_single_import_table(tbl)

        self.assertEqual(tbl_size_1, 152)

        # Directory to copy.
        allowed_test = os.path.join(self.media_source, "import_base_dir")

        # Copy directory over of 4 files
        shutil.copytree(allowed_test, os.path.join(self.import_source, "import_base_dir"))

        # Prepare the next 4 files.
        db.prepare_directory_for_import(source_dir=self.import_source, append=True, tbl_name=tbl)
        table_size_2 = db.db.get_size_of_single_import_table(tbl)


        self.assertEqual(table_size_2, 156)

        db.cleanup(fast=True)

    def test_allowed_ext_override(self):
        """
        Check that if we're passing an empty set for allowed_ext, the imported files will be empty.
        """
        db = PhotoAPI(root_path=self.temp_db)

        tbl = db.prepare_directory_for_import(source_dir=os.path.join(self.media_source, "db"),
                                              allowed_ext=set())

        allowed_sum = 0
        for row in db.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(0, allowed_sum)

        db.cleanup(fast=True)

    def test_purging(self):
        """
        CHeck if purging works correctly.
        """
        db = PhotoAPI(root_path=self.temp_db)

        # Copy the files
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = "Test_Table"

        db.prepare_directory_for_import(source_dir=self.import_source, purge=True, tbl_name=tbl)

        # Check the size after the first run
        self.assertEqual(152, db.db.get_size_of_single_import_table(tbl))

        tbl = db.prepare_directory_for_import(source_dir=self.import_source, purge=True, tbl_name=tbl)

        # Number should be the same
        self.assertEqual(152, db.db.get_size_of_single_import_table(tbl))

        # Change the directory. New number should be reflected
        shutil.rmtree(self.import_source)
        shutil.copytree(os.path.join(self.media_source, "import_base_dir"), self.import_source)

        # With purge, we should end with 4 files
        tbl = db.prepare_directory_for_import(source_dir=self.import_source, purge=True, tbl_name=tbl)

        self.assertEqual(4, db.db.get_size_of_single_import_table(tbl))

        db.cleanup(fast=True)

    def test_file_exists(self):
        """
        Check Add file to import table raises an error if a file is encoutered twice
        """

        db = PhotoAPI(root_path=self.temp_db)
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = "Test_Table"

        db.prepare_directory_for_import(source_dir=self.import_source, tbl_name=tbl)

        for root, dirs, files in os.walk(self.import_source):
            for f in files:
                self.assertRaises(ValueError, lambda : db._prepare_file_import(tbl_name=tbl,
                                                                               allowed_ext=set(),
                                                                               append=False,
                                                                               file_path=os.path.join(root, f)))

        db.cleanup(True)

    def test_recursive(self):
        """
        Check that if we don't search recursively, the db dir, which only contains directories, will not add a single
        row to the import table
        """
        db = PhotoAPI(root_path=self.temp_db)
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = "Test_Table"

        db.prepare_directory_for_import(source_dir=self.import_source, tbl_name=tbl, recursive=False)

        self.assertEqual(0, db.db.get_size_of_single_import_table(tbl))

        # Copy directory with 4 files
        for root, _, files in os.walk(os.path.join(self.media_source, "import_base_dir")):
            for f in files:
                shutil.copy2(os.path.join(root, f), os.path.join(self.import_source, f))

        db.prepare_directory_for_import(source_dir=self.import_source, tbl_name=tbl, recursive=False, purge=True)

        self.assertEqual(4, db.db.get_size_of_single_import_table(tbl))

        db.cleanup(True)

    def test_really_long_table_name(self):
        """
        Test if the table name will be truncated
        """
        db = PhotoAPI(root_path=self.temp_db)
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        very_long_name = "HelloWorld"*15

        tbl = db.prepare_directory_for_import(source_dir=self.import_source, tbl_name=very_long_name, recursive=False)

        self.assertEqual(len(tbl), 120)

        db.cleanup(True)

    def test_update_allowed(self):
        """
        Check that update allowed works correctly
        """
        db = PhotoAPI(root_path=self.temp_db)
        shutil.copytree(os.path.join(self.media_source, "import_base_dir"), self.import_source)

        tbl = db.prepare_directory_for_import(source_dir=self.import_source, allowed_ext={".png", ".jpg"})

        allowed_sum = 0
        for row in db.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(2, allowed_sum)

        # Update, make all files included
        db.update_allowed(allowed_ext={".png", ".jpg", ".jpeg", ".tiff"}, tbl=tbl)

        allowed_sum = 0
        for row in db.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(4, allowed_sum)

        # Update, other half not included
        db.update_allowed(allowed_ext={".jpeg", ".tiff"}, tbl=tbl)

        allowed_sum = 0
        for row in db.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(2, allowed_sum)
        db.cleanup(True)

    def test_file_ext_update_allowed(self):
        """
        Check that file exts without . are raise a ValueError
        """
        db = PhotoAPI(root_path=self.temp_db)
        shutil.copytree(os.path.join(self.media_source, "import_base_dir"), self.import_source)

        tbl = db.prepare_directory_for_import(source_dir=self.import_source, allowed_ext={".png", ".jpg"})

        self.assertRaises(ValueError, lambda : db.update_allowed(allowed_ext={"jpg"}, tbl=tbl))

        db.cleanup(True)
