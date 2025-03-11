import datetime
import json
import os.path
import shutil
import unittest
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from photo_lib.custom_enum import Allowed, MediaType
from photo_lib.flag_dataclasses import GenericTableFlags, MainFlags
from photo_lib.metadata_aggregator import DateTimeSource
from photo_lib.new_photo_model import PhotoAPI
from photo_lib.utils import rec_list_all

# TODO add full table dump for verification.
wip: bool = False

class TestAPIPrepareDirectoryForImport(unittest.TestCase):
    shadow_db: str
    temp_db: str
    media_source: str
    import_source: str

    api: Optional[PhotoAPI] = None

    @classmethod
    def setUpClass(cls):  # pragma: no cover
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

        # Create a fresh instance
        db = PhotoAPI(root_path=cls.shadow_db,
                      init=True,
                      opt_integrity_check=True)

        db.cleanup(fast=True)

    @classmethod
    def tearDownClass(cls):  # pragma: no cover
        # Class teardown is the removing of the shadow db
        path = cls.shadow_db

        shutil.rmtree(path)

        delattr(cls, "shadow_db")
        delattr(cls, "temp_db")
        delattr(cls, "media_source")
        delattr(cls, "import_source")

    def setUp(self):  # pragma: no cover
        """
        Setup function creates a fresh instance of the db to run the tests against
        """
        # Need to clear api if not done so already
        if self.api is not None:
            self.api.cleanup(True)
            self.api = None

        # Part of setup is teardown of the test db
        if os.path.exists(self.temp_db):
            shutil.rmtree(self.temp_db)

        shutil.copytree(self.shadow_db, self.temp_db)

        # Part of setup is teardown of the import_source directory
        if os.path.exists(self.import_source):
            shutil.rmtree(self.import_source)

        self.api = PhotoAPI(root_path=self.temp_db,
                            init=False, init_loggers=False)

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

    def test_verify_external_dir(self):
        """
        Test all possible wrong import sources and check that they are cought every time
        """
        rel_root = "foo/bar/baz"
        root_file = "/foo/bar/baz.txt"
        child_of_root = os.path.join(self.temp_db, "some_dir")
        child_file = os.path.join(self.temp_db, "baz.txt")

        os.makedirs(child_of_root, exist_ok=True)
        with open(child_file, "w") as f:
            f.write("Content")

        child_of_temp = os.path.join(self.api.db.get_temp_dir(), "some_dir")
        child_of_thumb = os.path.join(self.api.db.get_thumb_dir(), "some_dir")
        child_of_trash = os.path.join(self.api.db.get_trash_dir(), "some_dir")

        os.makedirs(child_of_temp, exist_ok=True)
        os.makedirs(child_of_thumb, exist_ok=True)
        os.makedirs(child_of_trash, exist_ok=True)

        # Check the default problems
        self.assertRaises(TypeError, lambda: self.api.prepare_directory_for_import(source_dir=rel_root))
        self.assertRaises(FileNotFoundError, lambda: self.api.prepare_directory_for_import(source_dir=root_file))
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=child_of_root))
        self.assertRaises(TypeError, lambda : self.api.prepare_directory_for_import(source_dir=child_file))

        # Check the db directories
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=child_of_temp))
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=child_of_thumb))
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=child_of_trash))

    def test_append_purge_errors(self):
        """
        Test alternate possibilities with append and purge set
        """
        db_dir = os.path.join(self.media_source, "db")

        # Both not allowed
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=db_dir,
                                                                                    append=True,
                                                                                    purge=True))

        # Table empty
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=db_dir,
                                                                                    append=True,
                                                                                    purge=False))

        # Table empty
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=db_dir,
                                                                                    append=False,
                                                                                    purge=True))

        # Test table exists
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=db_dir,
                                                                                    append=True,
                                                                                    purge=False,
                                                                                    tbl_name="some_table"))

        # Actually perform import:
        tbl = self.api.prepare_directory_for_import(source_dir=db_dir,
                                                    append=False,
                                                    purge=False)

        # Error, Table Exists
        self.assertRaises(ValueError, lambda: self.api.prepare_directory_for_import(source_dir=db_dir,
                                                                                    tbl_name=tbl))

    def test_append(self):
        """
        Test that appending to import table works
        """
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = self.api.prepare_directory_for_import(source_dir=self.import_source)
        tbl_size = self.api.db.get_size_of_single_import_table(tbl)

        self.assertEqual(tbl_size, 157)

        # Test empty append
        self.api.prepare_directory_for_import(source_dir=self.import_source, append=True, tbl_name=tbl)
        tbl_size_1 = self.api.db.get_size_of_single_import_table(tbl)

        self.assertEqual(tbl_size_1, 157)

        # Directory to copy.
        allowed_test = os.path.join(self.media_source, "import_base_dir")

        # Copy directory over of 4 files
        shutil.copytree(allowed_test, os.path.join(self.import_source, "import_base_dir"))

        # Prepare the next 4 files.
        self.api.prepare_directory_for_import(source_dir=self.import_source, append=True, tbl_name=tbl)
        table_size_2 = self.api.db.get_size_of_single_import_table(tbl)

        self.assertEqual(table_size_2, 161)

    def test_allowed_ext_override(self):
        """
        Check that if we're passing an empty set for allowed_ext, the imported files will be empty.
        """
        tbl = self.api.prepare_directory_for_import(source_dir=os.path.join(self.media_source, "db"),
                                                    allowed_ext=set())

        allowed_sum = 0
        for row in self.api.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(0, allowed_sum)

    def test_purging(self):
        """
        CHeck if purging works correctly.
        """
        # Copy the files
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = "Test_Table"

        self.api.prepare_directory_for_import(source_dir=self.import_source, purge=True, tbl_name=tbl)

        # Check the size after the first run
        self.assertEqual(157, self.api.db.get_size_of_single_import_table(tbl))

        tbl = self.api.prepare_directory_for_import(source_dir=self.import_source, purge=True, tbl_name=tbl)

        # Number should be the same
        self.assertEqual(157, self.api.db.get_size_of_single_import_table(tbl))

        # Change the directory. New number should be reflected
        shutil.rmtree(self.import_source)
        shutil.copytree(os.path.join(self.media_source, "import_base_dir"), self.import_source)

        # With purge, we should end with 4 files
        tbl = self.api.prepare_directory_for_import(source_dir=self.import_source, purge=True, tbl_name=tbl)

        self.assertEqual(4, self.api.db.get_size_of_single_import_table(tbl))

    def test_file_exists(self):
        """
        Check Add file to import table raises an error if a file is encoutered twice
        """
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = "Test_Table"

        self.api.prepare_directory_for_import(source_dir=self.import_source, tbl_name=tbl)

        for root, dirs, files in os.walk(self.import_source):
            for f in files:
                self.assertRaises(ValueError, lambda: self.api._prepare_file_import(tbl_name=tbl,
                                                                                    allowed_ext=set(),
                                                                                    append=False,
                                                                                    file_path=os.path.join(root, f)))

    def test_recursive(self):
        """
        Check that if we don't search recursively, the db dir, which only contains directories, will not add a single
        row to the import table
        """
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        tbl = "Test_Table"

        self.api.prepare_directory_for_import(source_dir=self.import_source, tbl_name=tbl, recursive=False)

        self.assertEqual(0, self.api.db.get_size_of_single_import_table(tbl))

        # Copy directory with 4 files
        for root, _, files in os.walk(os.path.join(self.media_source, "import_base_dir")):
            for f in files:
                shutil.copy2(os.path.join(root, f), os.path.join(self.import_source, f))

        self.api.prepare_directory_for_import(source_dir=self.import_source, tbl_name=tbl, recursive=False, purge=True)

        self.assertEqual(4, self.api.db.get_size_of_single_import_table(tbl))

    def test_really_long_table_name(self):
        """
        Test if the table name will be truncated
        """
        shutil.copytree(os.path.join(self.media_source, "db"), self.import_source)

        very_long_name = "HelloWorld" * 15

        tbl = self.api.prepare_directory_for_import(source_dir=self.import_source, tbl_name=very_long_name,
                                                    recursive=False)

        self.assertEqual(len(tbl), 120)

    def test_update_allowed(self):
        """
        Check that update allowed works correctly
        """
        shutil.copytree(os.path.join(self.media_source, "import_base_dir"), self.import_source)

        tbl = self.api.prepare_directory_for_import(source_dir=self.import_source, allowed_ext={".png", ".jpg"})

        allowed_sum = 0
        for row in self.api.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(2, allowed_sum)

        # Update, make all files included
        self.api.update_allowed(allowed_ext={".png", ".jpg", ".jpeg", ".tiff"}, tbl=tbl)

        allowed_sum = 0
        for row in self.api.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(4, allowed_sum)

        # Update, other half not included
        self.api.update_allowed(allowed_ext={".jpeg", ".tiff"}, tbl=tbl)

        allowed_sum = 0
        for row in self.api.db.update_allowed_iterator(tbl):
            key, allowed, org_fname = row
            if allowed == Allowed.ALLOWED:
                allowed_sum += 1

        self.assertEqual(2, allowed_sum)

    def test_file_ext_update_allowed(self):
        """
        Check that file exts without . are raise a ValueError
        """
        shutil.copytree(os.path.join(self.media_source, "import_base_dir"), self.import_source)

        tbl = self.api.prepare_directory_for_import(source_dir=self.import_source, allowed_ext={".png", ".jpg"})

        self.assertRaises(ValueError, lambda: self.api.update_allowed(allowed_ext={"jpg"}, tbl=tbl))


class TestAPIPerformImport(unittest.TestCase):
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
        cls.shadow_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "shadow_db"))
        cls.temp_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_db"))
        cls.media_source = os.path.join(os.path.dirname(__file__), "test_file_out")
        cls.import_source = os.path.join(os.path.dirname(__file__), "scratch")
        cls.tbl_dump_dir = os.path.join(os.path.dirname(__file__), "db_dump", "import")

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
                      init_loggers=True,
                      opt_integrity_check=True)

        cls.tgt_table = db.prepare_directory_for_import(source_dir=os.path.join(cls.media_source, "db"))

        db.cleanup()

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

    # ==================================================================================================================
    # Actual Test methods
    # ==================================================================================================================

    def test_internal_dir(self):
        """
        Test the internal dir function (checks that a given path is inside the scope of the db)
        """
        rel_root = "foo/bar/baz"
        not_equalchild_of_root = os.path.join(self.import_source, "some_dir")
        child_file = os.path.join(self.temp_db, "baz.txt")

        os.makedirs(not_equalchild_of_root, exist_ok=True)
        with open(child_file, "w") as f:
            f.write("Content")

        child_of_temp = os.path.join(self.api.db.get_temp_dir(), "some_dir")
        child_of_thumb = os.path.join(self.api.db.get_thumb_dir(), "some_dir")
        child_of_trash = os.path.join(self.api.db.get_trash_dir(), "some_dir")

        os.makedirs(child_of_temp, exist_ok=True)
        os.makedirs(child_of_thumb, exist_ok=True)
        os.makedirs(child_of_trash, exist_ok=True)

        # Check the default problems
        self.assertRaises(TypeError, lambda: self.api.verify_custom_target_dir(tgt_dir=rel_root))
        self.assertRaises(TypeError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_file))
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=not_equalchild_of_root))

        # Check the db directories
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_of_temp))
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_of_thumb))
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_of_trash))

    def test_correct_paths_rel(self):
        """
        Correct Custom Target Dir, check with the target directory being a relative path
        """
        rel_path_list = "imports", "testing", "full_import"
        rel_path = str(os.path.join(*rel_path_list))

        # For next test needed
        # target = os.path.join(self.api.root_path, rel_path)
        # os.makedirs(target)

        # set everything ready to import
        self.api.db.debug_execute(f"UPDATE `{self.tgt_table}` SET imported = 1 WHERE allowed = 1")

        self.api.perform_import(tbl_name=self.tgt_table, _dest_dir=rel_path)

        # get abs paths for all things in the db
        paths = rec_list_all(self.temp_db)
        rel_paths = [p.removeprefix(self.api.root_path).removeprefix(os.sep) for p in paths]

        self.check_custom_dir_table_dump()
        self.check_rel_custom_dir(rel_paths=rel_paths, custom_target_dir=rel_path)

    def test_correct_paths_abs(self):
        """
        Correct Custom Target Dir, check with the target directory being a absolute path
        """
        rel_path_list = "imports", "testing", "full_import"
        rel_path = str(os.path.join(*rel_path_list))

        # For next test needed
        target = os.path.join(self.api.root_path, rel_path)
        os.makedirs(target)

        # set everything ready to import
        self.api.db.debug_execute(f"UPDATE `{self.tgt_table}` SET imported = 1 WHERE allowed = 1")

        self.api.perform_import(tbl_name=self.tgt_table, _dest_dir=target)

        # get abs paths for all things in the db
        paths = rec_list_all(self.temp_db)
        rel_paths = [p.removeprefix(self.api.root_path).removeprefix(os.sep) for p in paths]

        self.check_rel_custom_dir(rel_paths=rel_paths, custom_target_dir=rel_path)
        self.check_custom_dir_table_dump()
        self.assertEqual(self.api.db.get_db_dir_count(), 1)

    def test_correct_paths_abs_append_file_name(self):
        """
        Check the correctness of the db_name function given, a config where we append the filenames
        """
        rel_path_list = "imports", "testing", "full_import"
        rel_path = str(os.path.join(*rel_path_list))

        # For next test needed
        target = os.path.join(self.api.root_path, rel_path)
        os.makedirs(target)

        self.api.config.org_filename_append = True

        # set everything ready to import
        self.api.db.debug_execute(f"UPDATE `{self.tgt_table}` SET imported = 1 WHERE allowed = 1")

        self.api.perform_import(tbl_name=self.tgt_table, _dest_dir=target)

        # get abs paths for all things in the db
        paths = rec_list_all(self.temp_db)
        rel_paths = [p.removeprefix(self.api.root_path).removeprefix(os.sep) for p in paths]

        self.check_append_filename(rel_paths=rel_paths, custom_target_dir=rel_path)
        self.check_custom_dir_append_fname_dump()

        # Check the db_dirs contains one entry
        self.assertEqual(self.api.db.get_db_dir_count(), 1)

    def test_tbl_defs(self):
        """
        Check that an exception is raised if the table doesn't exist.
        """
        self.assertRaises(ValueError, lambda : self.api.perform_import(tbl_name="self.tgt_table"))

        # Set teh flag of the import table to be internal
        gtf = GenericTableFlags(stale=False, internal=True)
        self.api.db.debug_execute("UPDATE import_table SET flags = ? WHERE table_name = ?",
                                  (gtf.to_int(), self.tgt_table))

        self.assertRaises(TypeError, lambda : self.api.perform_import(tbl_name=self.tgt_table))

        # Set teh flag of the import table to be internal
        gtf = GenericTableFlags(stale=True, internal=False)
        self.api.db.debug_execute("UPDATE import_table SET flags = ? WHERE table_name = ?",
                                  (gtf.to_int(), self.tgt_table))

        self.assertRaises(ValueError, lambda : self.api.perform_import(tbl_name=self.tgt_table))

    def test_dynamic_dirs(self):
        """
        Check the directories the way they are generated if the
        """
        # Set all files to be imported
        self.api.db.debug_execute(f"UPDATE `{self.tgt_table}` SET imported = 1 WHERE allowed = 1")

        self.api.perform_import(tbl_name=self.tgt_table)

        # Perform the import
        paths = rec_list_all(self.temp_db)
        rel_paths = [p.removeprefix(self.api.root_path).removeprefix(os.sep) for p in paths]

        self.check_dynamic_dirs(rel_paths)
        self.check_dyn_table_dump()

    def test_adding_exif_metadata(self):
        """
        Check that the file '10_no_metadata'
        - has the verify flag set
        - has two hashes
        - has the metadata set correctly
        """
        test_file = "10_no_metadata.jpg"
        test_fp = os.path.join(self.media_source, "db", "import_aux_test", test_file)
        pr = self.api.mda.eth.get_metadata(files=test_fp)

        # Check the properties of the file prior to importing
        self.assertEqual(1, len(pr))
        self.assertNotIn("EXIF:ModifyDate", pr[0].keys())
        self.assertNotIn("EXIF:OffsetTime", pr[0].keys())

        # check the import source and the
        self.api.db.debug_execute(f"SELECT datetime_source, allowed, key FROM `{self.tgt_table}` "
                                  f"WHERE original_filename = ?",
                                  (test_file,))
        row = self.api.db.sq_cur.fetchone()
        self.assertIsNotNone(row)

        # Check this is we only have the file data
        self.assertEqual(row[0], DateTimeSource.FILE_AWARE.value)
        self.assertEqual(row[1], Allowed.ALLOWED.value)

        # Update the import table and set the imported status to be ready for the import
        self.api.db.debug_execute(f"UPDATE `{self.tgt_table}` SET imported = 1 WHERE original_filename = ? ",
                                  (test_file,))

        self.api.perform_import(tbl_name=self.tgt_table, add_safety_exif_tags=True)

        # --------------------------------------------------------------------------------------------------------------
        # Check it is imported correctly
        import_path = os.path.join(self.api.root_path, "1990/11/01/1990-11-01T12-00-00_0001.jpg")
        self.assertTrue(os.path.exists(import_path))

        # Get the key in the main table
        main_key = self.api.db.db_resolve_filename_to_key("1990-11-01T12-00-00_0001.jpg")
        self.assertIsNotNone(main_key)

        flags = self.api.db.get_main_flags(main_key)
        self.assertTrue(flags.verify)

        # Check that we have the metadata set now
        pr2 = self.api.mda.eth.get_metadata(files=import_path)
        self.assertEqual(1, len(pr2))
        self.assertIn("EXIF:ModifyDate", pr2[0].keys())
        self.assertIn("EXIF:OffsetTime", pr2[0].keys())

        # Check that there are two hashes
        self.assertEqual(2, self.api.db.get_number_of_hashes_of_file(main_key))

    def test_add_gps(self):
        """
        Check that the gps row is added correctly
        """
        test_args = [
            {"file_name": "20_gps_metadata.jpg",
             "gps_lat": 47.36865,
             "gps_long": 8.539183,
             "import_path": "1990/11/01/1990-11-01T12-00-01_0001.jpg",
             "file_main_key": 1,
             "gps_key": 1},
            {"file_name": "21_gps_metadata.jpg",
             "gps_lat": 40.730610,
             "gps_long": -73.935242,
             "import_path": "1990/11/01/1990-11-01T12-00-02_0002.jpg",
             "file_main_key": 2,
             "gps_key": 2},
            {"file_name": "22_gps_metadata.jpg",
             "gps_lat": -29.90453,
             "gps_long": -71.24894,
             "import_path": "1990/11/01/1990-11-01T12-00-03_0003.jpg",
             "file_main_key": 3,
             "gps_key": 3},
            {"file_name": "23_gps_metadata.jpg",
             "gps_lat": -28.4792625,
             "gps_long": 24.6727135,
             "import_path": "1990/11/01/1990-11-01T12-00-04_0004.jpg",
             "file_main_key": 4,
             "gps_key": 4},
        ]

        for i in range(len(test_args)):
            args = test_args[i]
            with self.subTest(f"File = {args['file_name']}"):
                test_file = args["file_name"]
                test_fp = os.path.join(self.media_source, "db", "import_aux_test", test_file)
                pr = self.api.mda.eth.get_metadata(files=test_fp)

                # Check the properties of the file prior to importing
                self.assertEqual(1, len(pr))
                self.assertIn("EXIF:ModifyDate", pr[0].keys())
                self.assertNotIn("EXIF:OffsetTime", pr[0].keys())

                # Check GPS presence
                self.assertIn('EXIF:GPSLatitudeRef', pr[0].keys())
                self.assertIn('EXIF:GPSLatitude', pr[0].keys())
                self.assertIn('EXIF:GPSLongitudeRef', pr[0].keys())
                self.assertIn('EXIF:GPSLongitude', pr[0].keys())
                self.assertIn('EXIF:GPSAltitudeRef', pr[0].keys())
                self.assertIn('EXIF:GPSAltitude', pr[0].keys())

                # Check the gps data in the import table
                self.api.db.debug_execute(f"SELECT datetime_source, allowed, key, gps_latitude, gps_longitude "
                                          f"FROM `{self.tgt_table}` WHERE original_filename = ?",
                                          (test_file,))

                row = self.api.db.sq_cur.fetchone()
                self.assertIsNotNone(row)

                # Check this is we only have the file data
                self.assertEqual(row[0], DateTimeSource.UNAWARE_GPS.value)
                self.assertEqual(row[1], Allowed.ALLOWED.value)

                # Check the GPS is the correct value
                self.assertLess((row[3] - args["gps_lat"]), 10e-10) # GPS Lat
                self.assertLess((row[4] - args["gps_long"]), 10e-10) # GPS Long

                actual_gps_lat = row[3]
                actual_gps_long = row[4]

                # Update the import table and set the imported status to be ready for the import
                self.api.db.debug_execute(f"UPDATE `{self.tgt_table}` SET imported = 1 WHERE original_filename = ? ",
                                          (test_file,))

                self.api.perform_import(tbl_name=self.tgt_table, add_safety_exif_tags=True)

                # --------------------------------------------------------------------------------------------------------------
                # Check it is imported correctly
                import_path = os.path.join(self.api.root_path, args["import_path"])
                self.assertTrue(os.path.exists(import_path))

                # Check gps row
                self.api.db.debug_execute("SELECT key FROM gps_location WHERE gps_latitude = ? AND  gps_longitude = ?",
                                          (actual_gps_lat, actual_gps_long))

                # Check the gps key is added
                self.assertEqual(self.api.db.sq_cur.fetchone()[0], args["gps_key"])

                # Check row is matched in the metadata table
                row = self.api.db.get_metadata_row(args["file_main_key"])

                self.assertIsNotNone(row)

                # Check the
                self.assertIsNotNone(row.gps_lat)
                self.assertIsNotNone(row.gps_long)

    # ==================================================================================================================
    #  Perform some checks against the used db functions
    # ==================================================================================================================

    def test_insert_row_main_errors(self):
        """
        Check the correct errors are raised by the function
        """
        tz = ZoneInfo("CET")
        dt = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=tz)

        # Check Error raised for metadata
        self.assertRaises(TypeError, lambda : self.api.db.insert_row_main_table(
            original_filename="test_file_1.png",
            db_name="test_file_1.png",
            dt=dt,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=0,
            google_metadata=None))

        self.assertRaises(TypeError, lambda : self.api.db.insert_row_main_table(
            original_filename="test_file_1.png",
            db_name="test_file_1.png",
            dt=dt,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=None,
            google_metadata=0))

    def test_working_row_main(self):
        """
        Check that different types of metadata and google_fotos_metadata works correctly
        """
        tz = ZoneInfo("CET")
        dt1 = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=tz)
        dt2 = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=1, tzinfo=tz)
        dt3 = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=2, tzinfo=tz)
        dt4 = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=3, tzinfo=tz)
        dt5 = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=4, tzinfo=tz)
        dt6 = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=5, tzinfo=tz)

        md1 = "some_metadata_string"
        md2 = ["value_1", "value_2"]
        md3 = {"key_1": "value_1", "key_2": "value_2"}

        # Insert metadata rows
        # Inserted as 1
        self.api.db.insert_row_main_table(
            original_filename="test_file_1.png",
            db_name="test_file_1.png",
            dt=dt1,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=md1,
            google_metadata=None)

        # Inserted as 2
        self.api.db.insert_row_main_table(
            original_filename="test_file_2.png",
            db_name="test_file_2.png",
            dt=dt2,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=md2,
            google_metadata=None)

        # Inserted as 3
        self.api.db.insert_row_main_table(
            original_filename="test_file_3.png",
            db_name="test_file_3.png",
            dt=dt3,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=md3,
            google_metadata=None)

        # Check the functionality of serialization of metadata
        r1 = self.api.db.get_main_row(1)
        self.assertEqual(r1.db_name, "test_file_1.png")
        self.assertEqual(md1, r1.metadata)
        self.assertIsNone(r1.google_metadata)
        self.assertEqual(dt1, r1.datetime)

        r2 = self.api.db.get_main_row(2)
        self.assertEqual(r2.db_name, "test_file_2.png")
        self.assertEqual(json.dumps(md2), r2.metadata)
        self.assertIsNone(r2.google_metadata)
        self.assertEqual(dt2, r2.datetime)

        r3 = self.api.db.get_main_row(3)
        self.assertEqual(r3.db_name, "test_file_3.png")
        self.assertEqual(json.dumps(md3), r3.metadata)
        self.assertIsNone(r3.google_metadata)
        self.assertEqual(dt3, r3.datetime)

        # Insert google_metadata rows
        # Inserted as 4
        self.api.db.insert_row_main_table(
            original_filename="test_file_4.png",
            db_name="test_file_4.png",
            dt=dt4,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=None,
            google_metadata=md1)

        # Inserted as 5
        self.api.db.insert_row_main_table(
            original_filename="test_file_5.png",
            db_name="test_file_5.png",
            dt=dt5,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=None,
            google_metadata=md2)

        # Inserted as 6
        self.api.db.insert_row_main_table(
            original_filename="test_file_6.png",
            db_name="test_file_6.png",
            dt=dt6,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=None,
            google_metadata=md3)

        # Check the functionality of serialization of google_metadata
        r4 = self.api.db.get_main_row(4)
        self.assertEqual(r4.db_name, "test_file_4.png")
        self.assertEqual(md1, r4.google_metadata)
        self.assertIsNone(r4.metadata)
        self.assertEqual(dt4, r4.datetime)

        r5 = self.api.db.get_main_row(5)
        self.assertEqual(r5.db_name, "test_file_5.png")
        self.assertEqual(json.dumps(md2), r5.google_metadata)
        self.assertIsNone(r5.metadata)
        self.assertEqual(dt5, r5.datetime)

        r6 = self.api.db.get_main_row(6)
        self.assertEqual(r6.db_name, "test_file_6.png")
        self.assertEqual(json.dumps(md3), r6.google_metadata)
        self.assertIsNone(r6.metadata)
        self.assertEqual(dt6, r6.datetime)

    # INFO: insert_row_metadata_table has no validation, no extra tests needed

    def test_update_row_main_table_errors(self):
        """
        Test all errors update_row_main_table
        """
        tz = ZoneInfo("CET")
        dt = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=tz)
        dt_naive = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=0)

        self.api.db.insert_row_main_table(
            original_filename="test_file_1.png",
            db_name="test_file_1.png",
            dt=dt,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=None,
            google_metadata=None)

        # Type Errors for Metadata
        self.assertRaises(TypeError, lambda : self.api.db.update_row_main_table(key=1, metadata=0))
        self.assertRaises(TypeError, lambda: self.api.db.update_row_main_table(key=1, google_metadata=0))

        # Check superfluous row detected
        self.assertRaises(ValueError, lambda : self.api.db.update_row_main_table(key=1, some_string="Hello World"))

        # Test Datetime
        self.assertRaises(TypeError, lambda : self.api.db.update_row_main_table(key=1, datetime=dt_naive))

        # Test Flags
        self.assertRaises(TypeError, lambda : self.api.db.update_row_main_table(key=1, flags="Hello World"))

    def test_update_row_main_table_sanitization(self):
        """
        Test correct update with sanitization of types
        """
        tz = ZoneInfo("CET")
        dt = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=tz)
        dt_change = datetime.datetime(year=1990, month=1, day=1, hour=12, minute=0, second=1, tzinfo=tz)

        md1 = "some_metadata_string"
        md2 = ["value_1", "value_2"]
        md3 = {"key_1": "value_1", "key_2": "value_2"}

        new_flags = MainFlags.default()
        new_flags.verify = True

        self.api.db.insert_row_main_table(
            original_filename="test_file_1.png",
            db_name="test_file_1.png",
            dt=dt,
            timezone="CET",
            flags=MainFlags.default(),
            metadata=None,
            google_metadata=None)

        # Check string metadata
        self.api.db.update_row_main_table(key=1, metadata=md1)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertEqual(r.metadata, md1)
        self.assertIsNone(r.google_metadata)
        self.assertEqual(r.datetime, dt)

        # Check list metadata
        self.api.db.update_row_main_table(key=1, metadata=md2)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertEqual(r.metadata, json.dumps(md2))
        self.assertIsNone(r.google_metadata)
        self.assertEqual(r.datetime, dt)

        # Check dict metadata
        self.api.db.update_row_main_table(key=1, metadata=md3)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertEqual(r.metadata, json.dumps(md3))
        self.assertIsNone(r.google_metadata)
        self.assertEqual(r.datetime, dt)

        # Check string google metadata
        self.api.db.update_row_main_table(key=1, metadata=None, google_metadata=md1)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertEqual(r.google_metadata, md1)
        self.assertIsNone(r.metadata)
        self.assertEqual(r.datetime, dt)

        # Check list google metadata
        self.api.db.update_row_main_table(key=1, google_metadata=md2)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertEqual(r.google_metadata, json.dumps(md2))
        self.assertIsNone(r.metadata)
        self.assertEqual(r.datetime, dt)

        # Check dict google metadata
        self.api.db.update_row_main_table(key=1, google_metadata=md3)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertEqual(r.google_metadata, json.dumps(md3))
        self.assertIsNone(r.metadata)
        self.assertEqual(r.datetime, dt)

        # Check datetime
        self.api.db.update_row_main_table(key=1, google_metadata=None, datetime=dt_change)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, MainFlags.default())
        self.assertIsNone(r.google_metadata)
        self.assertIsNone(r.metadata)
        self.assertEqual(r.datetime, dt_change)

        # Check flags
        self.api.db.update_row_main_table(key=1, datetime=dt, flags=new_flags)

        # Check the row after update
        r = self.api.db.get_main_row(1)
        self.assertEqual(r.flags, new_flags)
        self.assertIsNone(r.google_metadata)
        self.assertIsNone(r.metadata)
        self.assertEqual(r.datetime, dt)

    def test_update_row_metadata_table_errors(self):
        """
        Check the correct errors are raised during the call of update_row_metadata_table
        """
        self.api.db.insert_row_metadata_table(key=1,
                                              original_dirname="/foo/bar/baz",
                                              naming_tag="File:AccessDate",
                                              datetime_source=DateTimeSource.FILE_AWARE)

        # Check not supported tag
        self.assertRaises(ValueError, lambda : self.api.db.update_row_metadata_table(key=1, some_tag="Value"))

        # check not supported type
        self.assertRaises(TypeError, lambda : self.api.db.update_row_metadata_table(key=1,
                                                                                    datetime_source="FILE_AWARE"))

        self.assertRaises(TypeError, lambda : self.api.db.update_row_metadata_table(key=1,
                                                                                    replaced="MAIN"))
        self.assertRaises(ValueError, lambda : self.api.db.update_row_metadata_table(key=1,
                                                                                     original_dirname="/foo/bar/baz"))

    def test_update_row_metadata_table_success(self):
        """
        Check the updating process is working correctly.
        """
        self.api.db.insert_row_metadata_table(key=1,
                                              original_dirname="/foo/bar/baz",
                                              naming_tag="File:AccessDate",
                                              datetime_source=DateTimeSource.FILE_AWARE)

        # Check everything is the way we expect
        mdr = self.api.db.get_metadata_row(key=1)
        self.assertEqual(mdr.replaced, MediaType.MAIN)
        self.assertEqual(mdr.main_key, 1)
        self.assertEqual(mdr.datetime_source, DateTimeSource.FILE_AWARE)
        self.assertEqual(mdr.naming_tag, "File:AccessDate")
        self.assertEqual(mdr.original_dirname, "/foo/bar/baz")

        self.assertIsNone(mdr.gps_lat)
        self.assertIsNone(mdr.gps_long)
        self.assertIsNone(mdr.db_local_dir)

        gps_key = self.api.db.insert_get_gps_loc(9.876543, 1.234567)
        dir_key = self.api._insert_get_dir("insert/second/dir")

        self.api.db.update_row_metadata_table(key=1, gps_location=gps_key, db_dir=dir_key)

        # Check that everything was set correctly
        mdr = self.api.db.get_metadata_row(key=1)
        self.assertEqual(mdr.replaced, MediaType.MAIN)
        self.assertEqual(mdr.main_key, 1)
        self.assertEqual(mdr.datetime_source, DateTimeSource.FILE_AWARE)
        self.assertEqual(mdr.naming_tag, "File:AccessDate")
        self.assertEqual(mdr.original_dirname, "/foo/bar/baz")

        self.assertEqual(mdr.gps_lat, 9.876543)
        self.assertEqual(mdr.gps_long, 1.234567)

        self.assertEqual(mdr.db_local_dir, "insert/second/dir".split(os.sep))
        # Update everything else and that works
        self.api.db.update_row_metadata_table(1,
                                              naming_tag="CUSTOM",
                                              datetime_source=DateTimeSource.CUSTOM,
                                              replaced=MediaType.TRASH)

        mdr = self.api.db.get_metadata_row(key=1)
        self.assertEqual(mdr.replaced, MediaType.TRASH)
        self.assertEqual(mdr.main_key, 1)
        self.assertEqual(mdr.datetime_source, DateTimeSource.CUSTOM)
        self.assertEqual(mdr.naming_tag, "CUSTOM")
        self.assertEqual(mdr.original_dirname, "/foo/bar/baz")

        self.assertEqual(mdr.gps_lat, 9.876543)
        self.assertEqual(mdr.gps_long, 1.234567)
        self.assertEqual(mdr.db_local_dir, "insert/second/dir".split(os.sep))

    # ==================================================================================================================
    # Check paths
    # ==================================================================================================================

    # TODO FIRST: Add the three extra GPS files
    # TODO dump tables and verify


    def check_dynamic_dirs(self, rel_paths: List[str]):
        """
        Check the paths given
        """
        self.assertIn(".config.json", rel_paths)
        self.assertIn(".photos.db", rel_paths)

        # Remove the already checked files.
        rel_paths.remove(".config.json")
        rel_paths.remove(".photos.db")

        if wip:  # pragma: no cover
            rel_paths.sort()
            print(json.dumps(rel_paths, indent=4))

        db_paths = [
            "1990/01/01/1990-01-01T12-00-00_0001.png",
            "1990/02/01/1990-02-01T12-00-00_0002.png",
            "1990/02/01/1990-02-01T12-00-01_0003.png",
            "1990/03/01/1990-03-01T12-00-00_0004.png",
            "1990/03/01/1990-03-01T12-00-01_0005.png",
            "1990/03/01/1990-03-01T12-00-02_0006.png",
            "1990/03/01/1990-03-01T12-00-03_0007.png",
            "1990/04/01/1990-04-01T12-00-00_0008.png",
            "1990/04/01/1990-04-01T12-00-01_0009.png",
            "1990/04/01/1990-04-01T12-00-02_0010.png",
            "1990/04/01/1990-04-01T12-00-03_0011.png",
            "1990/04/01/1990-04-01T12-00-04_0012.png",
            "1990/04/01/1990-04-01T12-00-05_0013.png",
            "1990/04/01/1990-04-01T12-00-06_0014.png",
            "1990/04/01/1990-04-01T12-00-07_0015.png",
            "1990/05/01/1990-05-01T12-00-00_0016.png",
            "1990/05/01/1990-05-01T12-00-01_0024.png",
            "1990/05/01/1990-05-01T12-00-02_0025.png",
            "1990/05/01/1990-05-01T12-00-03_0026.png",
            "1990/05/01/1990-05-01T12-00-04_0027.png",
            "1990/05/01/1990-05-01T12-00-05_0028.png",
            "1990/05/01/1990-05-01T12-00-06_0029.png",
            "1990/05/01/1990-05-01T12-00-07_0030.png",
            "1990/05/01/1990-05-01T12-00-08_0031.png",
            "1990/05/01/1990-05-01T12-00-09_0017.png",
            "1990/05/01/1990-05-01T12-00-10_0018.png",
            "1990/05/01/1990-05-01T12-00-11_0019.png",
            "1990/05/01/1990-05-01T12-00-12_0020.png",
            "1990/05/01/1990-05-01T12-00-13_0021.png",
            "1990/05/01/1990-05-01T12-00-14_0022.png",
            "1990/05/01/1990-05-01T12-00-15_0023.png",
            "1990/06/01/1990-06-01T12-00-00_0032.png",
            "1990/06/01/1990-06-01T12-00-01_0043.png",
            "1990/06/01/1990-06-01T12-00-02_0054.png",
            "1990/06/01/1990-06-01T12-00-03_0058.png",
            "1990/06/01/1990-06-01T12-00-04_0059.png",
            "1990/06/01/1990-06-01T12-00-05_0060.png",
            "1990/06/01/1990-06-01T12-00-06_0061.png",
            "1990/06/01/1990-06-01T12-00-07_0062.png",
            "1990/06/01/1990-06-01T12-00-08_0063.png",
            "1990/06/01/1990-06-01T12-00-09_0033.png",
            "1990/06/01/1990-06-01T12-00-10_0034.png",
            "1990/06/01/1990-06-01T12-00-11_0035.png",
            "1990/06/01/1990-06-01T12-00-12_0036.png",
            "1990/06/01/1990-06-01T12-00-13_0037.png",
            "1990/06/01/1990-06-01T12-00-14_0038.png",
            "1990/06/01/1990-06-01T12-00-15_0039.png",
            "1990/06/01/1990-06-01T12-00-16_0040.png",
            "1990/06/01/1990-06-01T12-00-17_0041.png",
            "1990/06/01/1990-06-01T12-00-18_0042.png",
            "1990/06/01/1990-06-01T12-00-19_0044.png",
            "1990/06/01/1990-06-01T12-00-20_0045.png",
            "1990/06/01/1990-06-01T12-00-21_0046.png",
            "1990/06/01/1990-06-01T12-00-22_0047.png",
            "1990/06/01/1990-06-01T12-00-23_0048.png",
            "1990/06/01/1990-06-01T12-00-24_0049.png",
            "1990/06/01/1990-06-01T12-00-25_0050.png",
            "1990/06/01/1990-06-01T12-00-26_0051.png",
            "1990/06/01/1990-06-01T12-00-27_0052.png",
            "1990/06/01/1990-06-01T12-00-28_0053.png",
            "1990/06/01/1990-06-01T12-00-29_0055.png",
            "1990/06/01/1990-06-01T12-00-30_0056.png",
            "1990/06/01/1990-06-01T12-00-31_0057.png",
            "1990/07/01/1990-07-01T12-00-00_0064.png",
            "1990/07/01/1990-07-01T12-00-01_0075.png",
            "1990/07/01/1990-07-01T12-00-02_0086.png",
            "1990/07/01/1990-07-01T12-00-03_0097.png",
            "1990/07/01/1990-07-01T12-00-04_0108.png",
            "1990/07/01/1990-07-01T12-00-05_0119.png",
            "1990/07/01/1990-07-01T12-00-06_0125.png",
            "1990/07/01/1990-07-01T12-00-07_0126.png",
            "1990/07/01/1990-07-01T12-00-08_0127.png",
            "1990/07/01/1990-07-01T12-00-09_0065.png",
            "1990/07/01/1990-07-01T12-00-10_0066.png",
            "1990/07/01/1990-07-01T12-00-11_0067.png",
            "1990/07/01/1990-07-01T12-00-12_0068.png",
            "1990/07/01/1990-07-01T12-00-13_0069.png",
            "1990/07/01/1990-07-01T12-00-14_0070.png",
            "1990/07/01/1990-07-01T12-00-15_0071.png",
            "1990/07/01/1990-07-01T12-00-16_0072.png",
            "1990/07/01/1990-07-01T12-00-17_0073.png",
            "1990/07/01/1990-07-01T12-00-18_0074.png",
            "1990/07/01/1990-07-01T12-00-19_0076.png",
            "1990/07/01/1990-07-01T12-00-20_0077.png",
            "1990/07/01/1990-07-01T12-00-21_0078.png",
            "1990/07/01/1990-07-01T12-00-22_0079.png",
            "1990/07/01/1990-07-01T12-00-23_0080.png",
            "1990/07/01/1990-07-01T12-00-24_0081.png",
            "1990/07/01/1990-07-01T12-00-25_0082.png",
            "1990/07/01/1990-07-01T12-00-26_0083.png",
            "1990/07/01/1990-07-01T12-00-27_0084.png",
            "1990/07/01/1990-07-01T12-00-28_0085.png",
            "1990/07/01/1990-07-01T12-00-29_0087.png",
            "1990/07/01/1990-07-01T12-00-30_0088.png",
            "1990/07/01/1990-07-01T12-00-31_0089.png",
            "1990/07/01/1990-07-01T12-00-32_0090.png",
            "1990/07/01/1990-07-01T12-00-33_0091.png",
            "1990/07/01/1990-07-01T12-00-34_0092.png",
            "1990/07/01/1990-07-01T12-00-35_0093.png",
            "1990/07/01/1990-07-01T12-00-36_0094.png",
            "1990/07/01/1990-07-01T12-00-37_0095.png",
            "1990/07/01/1990-07-01T12-00-38_0096.png",
            "1990/07/01/1990-07-01T12-00-39_0098.png",
            "1990/07/01/1990-07-01T12-00-40_0099.png",
            "1990/07/01/1990-07-01T12-00-41_0100.png",
            "1990/07/01/1990-07-01T12-00-42_0101.png",
            "1990/07/01/1990-07-01T12-00-43_0102.png",
            "1990/07/01/1990-07-01T12-00-44_0103.png",
            "1990/07/01/1990-07-01T12-00-45_0104.png",
            "1990/07/01/1990-07-01T12-00-46_0105.png",
            "1990/07/01/1990-07-01T12-00-47_0106.png",
            "1990/07/01/1990-07-01T12-00-48_0107.png",
            "1990/07/01/1990-07-01T12-00-49_0109.png",
            "1990/07/01/1990-07-01T12-00-50_0110.png",
            "1990/07/01/1990-07-01T12-00-51_0111.png",
            "1990/07/01/1990-07-01T12-00-52_0112.png",
            "1990/07/01/1990-07-01T12-00-53_0113.png",
            "1990/07/01/1990-07-01T12-00-54_0114.png",
            "1990/07/01/1990-07-01T12-00-55_0115.png",
            "1990/07/01/1990-07-01T12-00-56_0116.png",
            "1990/07/01/1990-07-01T12-00-57_0117.png",
            "1990/07/01/1990-07-01T12-00-58_0118.png",
            "1990/07/01/1990-07-01T12-00-59_0120.png",
            "1990/07/01/1990-07-01T12-01-00_0121.png",
            "1990/07/01/1990-07-01T12-01-01_0122.png",
            "1990/07/01/1990-07-01T12-01-02_0123.png",
            "1990/07/01/1990-07-01T12-01-03_0124.png",
            "1990/09/01/1990-09-01T12-00-00_0128.png",      # Needed for hash based matching (change filename)
            "1990/09/01/1990-09-01T13-01-00_0129.png",      # Needed for hash based matching (change filename)
            "1990/09/01/1990-09-01T14-01-00_0130.png",      # Needed for hash based matching (change filename)
            "1990/10/01/1990-10-01T12-00-00_0136.png",      # Needed for matching algo during import
            "1990/10/01/1990-10-01T12-00-00_0137.png",      # Needed for matching algo during import
            "1990/10/01/1990-10-01T12-00-00_0138.png",      # Needed for matching algo during import
            "1990/10/01/1990-10-01T12-00-00_0139.png",      # Needed for matching algo during import
            "1990/10/01/1990-10-01T12-00-00_0140.png",      # Needed for matching algo during import
            "1990/10/01/1990-10-01T12-00-00_0141.png",      # Needed for matching algo during import
            "1990/10/02/1990-10-02T12-00-00_0142.png",      # Needed for matching algo during import
            "1990/10/02/1990-10-02T12-00-00_0143.png",      # Needed for matching algo during import
            "1990/10/02/1990-10-02T12-00-00_0144.png",      # Needed for matching algo during import
            "1990/10/02/1990-10-02T12-00-00_0145.png",      # Needed for matching algo during import
            "1990/10/02/1990-10-02T12-00-00_0146.png",      # Needed for matching algo during import
            "1990/10/03/1990-10-03T12-00-00_0147.png",      # Needed for matching algo during import
            "1990/10/03/1990-10-03T12-00-00_0148.png",      # Needed for matching algo during import
            "1990/10/03/1990-10-03T12-00-00_0149.png",      # Needed for matching algo during import
            "1990/10/03/1990-10-03T12-00-00_0150.png",      # Needed for matching algo during import
            "1990/10/04/1990-10-04T12-00-00_0151.png",      # Needed for matching algo during import
            "1990/10/04/1990-10-04T12-00-00_0152.png",      # Needed for matching algo during import
            "1990/10/04/1990-10-04T12-00-00_0153.png",      # Needed for matching algo during import
            "1990/10/05/1990-10-05T12-00-00_0154.png",      # Needed for matching algo during import
            "1990/10/05/1990-10-05T12-00-00_0155.png",      # Needed for matching algo during import
            "1990/10/06/1990-10-06T12-00-00_0156.png",      # Needed for matching algo during import
            "1990/10/07/1990-10-07T12-00-00_0157.png",      # Needed for matching algo during import
            "1990/11/01/1990-11-01T12-00-00_0131.jpg",      # Needed to test add exif tag
            "1990/11/01/1990-11-01T12-00-01_0132.jpg",      # Needed to test gps parsing
            "1990/11/01/1990-11-01T12-00-02_0133.jpg",      # Needed to test gps parsing
            "1990/11/01/1990-11-01T12-00-03_0134.jpg",      # Needed to test gps parsing
            "1990/11/01/1990-11-01T12-00-04_0135.jpg",      # Needed to test gps parsing
        ]

        for rp in rel_paths:
            self.assertIn(rp, db_paths)

    def check_rel_custom_dir(self, rel_paths: List[str], custom_target_dir: str):
        """
        Check that the file system (after an index) and the list of expected files are equivalent.
        (In Case of an import into a custom target directory)
        """
        self.assertIn(".config.json", rel_paths)
        self.assertIn(".photos.db", rel_paths)

        # Remove the already checked files.
        rel_paths.remove(".config.json")
        rel_paths.remove(".photos.db")

        files = [p.removeprefix(custom_target_dir).removeprefix(os.sep) for p in rel_paths]

        if wip:  # pragma: no cover
            files.sort()
            print(json.dumps(files, indent=4))

        db_files = [
            "1990-01-01T12-00-00_0001.png",
            "1990-02-01T12-00-00_0002.png",
            "1990-02-01T12-00-01_0003.png",
            "1990-03-01T12-00-00_0004.png",
            "1990-03-01T12-00-01_0005.png",
            "1990-03-01T12-00-02_0006.png",
            "1990-03-01T12-00-03_0007.png",
            "1990-04-01T12-00-00_0008.png",
            "1990-04-01T12-00-01_0009.png",
            "1990-04-01T12-00-02_0010.png",
            "1990-04-01T12-00-03_0011.png",
            "1990-04-01T12-00-04_0012.png",
            "1990-04-01T12-00-05_0013.png",
            "1990-04-01T12-00-06_0014.png",
            "1990-04-01T12-00-07_0015.png",
            "1990-05-01T12-00-00_0016.png",
            "1990-05-01T12-00-01_0024.png",
            "1990-05-01T12-00-02_0025.png",
            "1990-05-01T12-00-03_0026.png",
            "1990-05-01T12-00-04_0027.png",
            "1990-05-01T12-00-05_0028.png",
            "1990-05-01T12-00-06_0029.png",
            "1990-05-01T12-00-07_0030.png",
            "1990-05-01T12-00-08_0031.png",
            "1990-05-01T12-00-09_0017.png",
            "1990-05-01T12-00-10_0018.png",
            "1990-05-01T12-00-11_0019.png",
            "1990-05-01T12-00-12_0020.png",
            "1990-05-01T12-00-13_0021.png",
            "1990-05-01T12-00-14_0022.png",
            "1990-05-01T12-00-15_0023.png",
            "1990-06-01T12-00-00_0032.png",
            "1990-06-01T12-00-01_0043.png",
            "1990-06-01T12-00-02_0054.png",
            "1990-06-01T12-00-03_0058.png",
            "1990-06-01T12-00-04_0059.png",
            "1990-06-01T12-00-05_0060.png",
            "1990-06-01T12-00-06_0061.png",
            "1990-06-01T12-00-07_0062.png",
            "1990-06-01T12-00-08_0063.png",
            "1990-06-01T12-00-09_0033.png",
            "1990-06-01T12-00-10_0034.png",
            "1990-06-01T12-00-11_0035.png",
            "1990-06-01T12-00-12_0036.png",
            "1990-06-01T12-00-13_0037.png",
            "1990-06-01T12-00-14_0038.png",
            "1990-06-01T12-00-15_0039.png",
            "1990-06-01T12-00-16_0040.png",
            "1990-06-01T12-00-17_0041.png",
            "1990-06-01T12-00-18_0042.png",
            "1990-06-01T12-00-19_0044.png",
            "1990-06-01T12-00-20_0045.png",
            "1990-06-01T12-00-21_0046.png",
            "1990-06-01T12-00-22_0047.png",
            "1990-06-01T12-00-23_0048.png",
            "1990-06-01T12-00-24_0049.png",
            "1990-06-01T12-00-25_0050.png",
            "1990-06-01T12-00-26_0051.png",
            "1990-06-01T12-00-27_0052.png",
            "1990-06-01T12-00-28_0053.png",
            "1990-06-01T12-00-29_0055.png",
            "1990-06-01T12-00-30_0056.png",
            "1990-06-01T12-00-31_0057.png",
            "1990-07-01T12-00-00_0064.png",
            "1990-07-01T12-00-01_0075.png",
            "1990-07-01T12-00-02_0086.png",
            "1990-07-01T12-00-03_0097.png",
            "1990-07-01T12-00-04_0108.png",
            "1990-07-01T12-00-05_0119.png",
            "1990-07-01T12-00-06_0125.png",
            "1990-07-01T12-00-07_0126.png",
            "1990-07-01T12-00-08_0127.png",
            "1990-07-01T12-00-09_0065.png",
            "1990-07-01T12-00-10_0066.png",
            "1990-07-01T12-00-11_0067.png",
            "1990-07-01T12-00-12_0068.png",
            "1990-07-01T12-00-13_0069.png",
            "1990-07-01T12-00-14_0070.png",
            "1990-07-01T12-00-15_0071.png",
            "1990-07-01T12-00-16_0072.png",
            "1990-07-01T12-00-17_0073.png",
            "1990-07-01T12-00-18_0074.png",
            "1990-07-01T12-00-19_0076.png",
            "1990-07-01T12-00-20_0077.png",
            "1990-07-01T12-00-21_0078.png",
            "1990-07-01T12-00-22_0079.png",
            "1990-07-01T12-00-23_0080.png",
            "1990-07-01T12-00-24_0081.png",
            "1990-07-01T12-00-25_0082.png",
            "1990-07-01T12-00-26_0083.png",
            "1990-07-01T12-00-27_0084.png",
            "1990-07-01T12-00-28_0085.png",
            "1990-07-01T12-00-29_0087.png",
            "1990-07-01T12-00-30_0088.png",
            "1990-07-01T12-00-31_0089.png",
            "1990-07-01T12-00-32_0090.png",
            "1990-07-01T12-00-33_0091.png",
            "1990-07-01T12-00-34_0092.png",
            "1990-07-01T12-00-35_0093.png",
            "1990-07-01T12-00-36_0094.png",
            "1990-07-01T12-00-37_0095.png",
            "1990-07-01T12-00-38_0096.png",
            "1990-07-01T12-00-39_0098.png",
            "1990-07-01T12-00-40_0099.png",
            "1990-07-01T12-00-41_0100.png",
            "1990-07-01T12-00-42_0101.png",
            "1990-07-01T12-00-43_0102.png",
            "1990-07-01T12-00-44_0103.png",
            "1990-07-01T12-00-45_0104.png",
            "1990-07-01T12-00-46_0105.png",
            "1990-07-01T12-00-47_0106.png",
            "1990-07-01T12-00-48_0107.png",
            "1990-07-01T12-00-49_0109.png",
            "1990-07-01T12-00-50_0110.png",
            "1990-07-01T12-00-51_0111.png",
            "1990-07-01T12-00-52_0112.png",
            "1990-07-01T12-00-53_0113.png",
            "1990-07-01T12-00-54_0114.png",
            "1990-07-01T12-00-55_0115.png",
            "1990-07-01T12-00-56_0116.png",
            "1990-07-01T12-00-57_0117.png",
            "1990-07-01T12-00-58_0118.png",
            "1990-07-01T12-00-59_0120.png",
            "1990-07-01T12-01-00_0121.png",
            "1990-07-01T12-01-01_0122.png",
            "1990-07-01T12-01-02_0123.png",
            "1990-07-01T12-01-03_0124.png",
            "1990-09-01T12-00-00_0128.png",     # Needed for hash based matching (change filename)
            "1990-09-01T13-01-00_0129.png",     # Needed for hash based matching (change filename)
            "1990-09-01T14-01-00_0130.png",     # Needed for hash based matching (change filename)
            "1990-10-01T12-00-00_0136.png",     # Needed for matching algo during import
            "1990-10-01T12-00-00_0137.png",     # Needed for matching algo during import
            "1990-10-01T12-00-00_0138.png",     # Needed for matching algo during import
            "1990-10-01T12-00-00_0139.png",     # Needed for matching algo during import
            "1990-10-01T12-00-00_0140.png",     # Needed for matching algo during import
            "1990-10-01T12-00-00_0141.png",     # Needed for matching algo during import
            "1990-10-02T12-00-00_0142.png",     # Needed for matching algo during import
            "1990-10-02T12-00-00_0143.png",     # Needed for matching algo during import
            "1990-10-02T12-00-00_0144.png",     # Needed for matching algo during import
            "1990-10-02T12-00-00_0145.png",     # Needed for matching algo during import
            "1990-10-02T12-00-00_0146.png",     # Needed for matching algo during import
            "1990-10-03T12-00-00_0147.png",     # Needed for matching algo during import
            "1990-10-03T12-00-00_0148.png",     # Needed for matching algo during import
            "1990-10-03T12-00-00_0149.png",     # Needed for matching algo during import
            "1990-10-03T12-00-00_0150.png",     # Needed for matching algo during import
            "1990-10-04T12-00-00_0151.png",     # Needed for matching algo during import
            "1990-10-04T12-00-00_0152.png",     # Needed for matching algo during import
            "1990-10-04T12-00-00_0153.png",     # Needed for matching algo during import
            "1990-10-05T12-00-00_0154.png",     # Needed for matching algo during import
            "1990-10-05T12-00-00_0155.png",     # Needed for matching algo during import
            "1990-10-06T12-00-00_0156.png",     # Needed for matching algo during import
            "1990-10-07T12-00-00_0157.png",     # Needed for matching algo during import
            "1990-11-01T12-00-00_0131.jpg",     # Needed to test add exif tag
            "1990-11-01T12-00-01_0132.jpg",     # Needed to test gps parsing
            "1990-11-01T12-00-02_0133.jpg",     # Needed to test gps parsing
            "1990-11-01T12-00-03_0134.jpg",     # Needed to test gps parsing
            "1990-11-01T12-00-04_0135.jpg",     # Needed to test gps parsing
        ]

        for file in files:
            self.assertIn(file, db_files)

    def check_append_filename(self, rel_paths: List[str], custom_target_dir: str):
        """
        Check the appended filenaemsw
        """
        self.assertIn(".config.json", rel_paths)
        self.assertIn(".photos.db", rel_paths)

        # Remove the already checked files.
        rel_paths.remove(".config.json")
        rel_paths.remove(".photos.db")

        files = [p.removeprefix(custom_target_dir).removeprefix(os.sep) for p in rel_paths]

        if wip:  # pragma: no cover
            files.sort()
            print(json.dumps(files, indent=4))

        db_files = [
            "1990-01-01T12-00-00_0001_1_1.png",
            "1990-02-01T12-00-00_0002_2_1.png",
            "1990-02-01T12-00-01_0003_2_2.png",
            "1990-03-01T12-00-00_0004_3_1.png",
            "1990-03-01T12-00-01_0005_3_2.png",
            "1990-03-01T12-00-02_0006_3_3.png",
            "1990-03-01T12-00-03_0007_3_4.png",
            "1990-04-01T12-00-00_0008_4_1.png",
            "1990-04-01T12-00-01_0009_4_2.png",
            "1990-04-01T12-00-02_0010_4_3.png",
            "1990-04-01T12-00-03_0011_4_4.png",
            "1990-04-01T12-00-04_0012_4_5.png",
            "1990-04-01T12-00-05_0013_4_6.png",
            "1990-04-01T12-00-06_0014_4_7.png",
            "1990-04-01T12-00-07_0015_4_8.png",
            "1990-05-01T12-00-00_0016_5_1.png",
            "1990-05-01T12-00-01_0024_5_2.png",
            "1990-05-01T12-00-02_0025_5_3.png",
            "1990-05-01T12-00-03_0026_5_4.png",
            "1990-05-01T12-00-04_0027_5_5.png",
            "1990-05-01T12-00-05_0028_5_6.png",
            "1990-05-01T12-00-06_0029_5_7.png",
            "1990-05-01T12-00-07_0030_5_8.png",
            "1990-05-01T12-00-08_0031_5_9.png",
            "1990-05-01T12-00-09_0017_5_10.png",
            "1990-05-01T12-00-10_0018_5_11.png",
            "1990-05-01T12-00-11_0019_5_12.png",
            "1990-05-01T12-00-12_0020_5_13.png",
            "1990-05-01T12-00-13_0021_5_14.png",
            "1990-05-01T12-00-14_0022_5_15.png",
            "1990-05-01T12-00-15_0023_5_16.png",
            "1990-06-01T12-00-00_0032_6_1.png",
            "1990-06-01T12-00-01_0043_6_2.png",
            "1990-06-01T12-00-02_0054_6_3.png",
            "1990-06-01T12-00-03_0058_6_4.png",
            "1990-06-01T12-00-04_0059_6_5.png",
            "1990-06-01T12-00-05_0060_6_6.png",
            "1990-06-01T12-00-06_0061_6_7.png",
            "1990-06-01T12-00-07_0062_6_8.png",
            "1990-06-01T12-00-08_0063_6_9.png",
            "1990-06-01T12-00-09_0033_6_10.png",
            "1990-06-01T12-00-10_0034_6_11.png",
            "1990-06-01T12-00-11_0035_6_12.png",
            "1990-06-01T12-00-12_0036_6_13.png",
            "1990-06-01T12-00-13_0037_6_14.png",
            "1990-06-01T12-00-14_0038_6_15.png",
            "1990-06-01T12-00-15_0039_6_16.png",
            "1990-06-01T12-00-16_0040_6_17.png",
            "1990-06-01T12-00-17_0041_6_18.png",
            "1990-06-01T12-00-18_0042_6_19.png",
            "1990-06-01T12-00-19_0044_6_20.png",
            "1990-06-01T12-00-20_0045_6_21.png",
            "1990-06-01T12-00-21_0046_6_22.png",
            "1990-06-01T12-00-22_0047_6_23.png",
            "1990-06-01T12-00-23_0048_6_24.png",
            "1990-06-01T12-00-24_0049_6_25.png",
            "1990-06-01T12-00-25_0050_6_26.png",
            "1990-06-01T12-00-26_0051_6_27.png",
            "1990-06-01T12-00-27_0052_6_28.png",
            "1990-06-01T12-00-28_0053_6_29.png",
            "1990-06-01T12-00-29_0055_6_30.png",
            "1990-06-01T12-00-30_0056_6_31.png",
            "1990-06-01T12-00-31_0057_6_32.png",
            "1990-07-01T12-00-00_0064_7_1.png",
            "1990-07-01T12-00-01_0075_7_2.png",
            "1990-07-01T12-00-02_0086_7_3.png",
            "1990-07-01T12-00-03_0097_7_4.png",
            "1990-07-01T12-00-04_0108_7_5.png",
            "1990-07-01T12-00-05_0119_7_6.png",
            "1990-07-01T12-00-06_0125_7_7.png",
            "1990-07-01T12-00-07_0126_7_8.png",
            "1990-07-01T12-00-08_0127_7_9.png",
            "1990-07-01T12-00-09_0065_7_10.png",
            "1990-07-01T12-00-10_0066_7_11.png",
            "1990-07-01T12-00-11_0067_7_12.png",
            "1990-07-01T12-00-12_0068_7_13.png",
            "1990-07-01T12-00-13_0069_7_14.png",
            "1990-07-01T12-00-14_0070_7_15.png",
            "1990-07-01T12-00-15_0071_7_16.png",
            "1990-07-01T12-00-16_0072_7_17.png",
            "1990-07-01T12-00-17_0073_7_18.png",
            "1990-07-01T12-00-18_0074_7_19.png",
            "1990-07-01T12-00-19_0076_7_20.png",
            "1990-07-01T12-00-20_0077_7_21.png",
            "1990-07-01T12-00-21_0078_7_22.png",
            "1990-07-01T12-00-22_0079_7_23.png",
            "1990-07-01T12-00-23_0080_7_24.png",
            "1990-07-01T12-00-24_0081_7_25.png",
            "1990-07-01T12-00-25_0082_7_26.png",
            "1990-07-01T12-00-26_0083_7_27.png",
            "1990-07-01T12-00-27_0084_7_28.png",
            "1990-07-01T12-00-28_0085_7_29.png",
            "1990-07-01T12-00-29_0087_7_30.png",
            "1990-07-01T12-00-30_0088_7_31.png",
            "1990-07-01T12-00-31_0089_7_32.png",
            "1990-07-01T12-00-32_0090_7_33.png",
            "1990-07-01T12-00-33_0091_7_34.png",
            "1990-07-01T12-00-34_0092_7_35.png",
            "1990-07-01T12-00-35_0093_7_36.png",
            "1990-07-01T12-00-36_0094_7_37.png",
            "1990-07-01T12-00-37_0095_7_38.png",
            "1990-07-01T12-00-38_0096_7_39.png",
            "1990-07-01T12-00-39_0098_7_40.png",
            "1990-07-01T12-00-40_0099_7_41.png",
            "1990-07-01T12-00-41_0100_7_42.png",
            "1990-07-01T12-00-42_0101_7_43.png",
            "1990-07-01T12-00-43_0102_7_44.png",
            "1990-07-01T12-00-44_0103_7_45.png",
            "1990-07-01T12-00-45_0104_7_46.png",
            "1990-07-01T12-00-46_0105_7_47.png",
            "1990-07-01T12-00-47_0106_7_48.png",
            "1990-07-01T12-00-48_0107_7_49.png",
            "1990-07-01T12-00-49_0109_7_50.png",
            "1990-07-01T12-00-50_0110_7_51.png",
            "1990-07-01T12-00-51_0111_7_52.png",
            "1990-07-01T12-00-52_0112_7_53.png",
            "1990-07-01T12-00-53_0113_7_54.png",
            "1990-07-01T12-00-54_0114_7_55.png",
            "1990-07-01T12-00-55_0115_7_56.png",
            "1990-07-01T12-00-56_0116_7_57.png",
            "1990-07-01T12-00-57_0117_7_58.png",
            "1990-07-01T12-00-58_0118_7_59.png",
            "1990-07-01T12-00-59_0120_7_60.png",
            "1990-07-01T12-01-00_0121_7_61.png",
            "1990-07-01T12-01-01_0122_7_62.png",
            "1990-07-01T12-01-02_0123_7_63.png",
            "1990-07-01T12-01-03_0124_7_64.png",
            "1990-09-01T12-00-00_0128_01_match_a.png",                  # Needed for hash based matching (change filename)
            "1990-09-01T13-01-00_0129_02_match_a.png",                  # Needed for hash based matching (change filename)
            "1990-09-01T14-01-00_0130_03_match_a.png",                  # Needed for hash based matching (change filename)
            "1990-10-01T12-00-00_0136_11_Binary_Match_Main.png",        # Needed for matching algo during import
            "1990-10-01T12-00-00_0137_12_Hash_Match_Main.png",          # Needed for matching algo during import
            "1990-10-01T12-00-00_0138_13_Binary_Match_Trash.png",       # Needed for matching algo during import
            "1990-10-01T12-00-00_0139_14_Hash_Match_Trash.png",         # Needed for matching algo during import
            "1990-10-01T12-00-00_0140_15_Binary_Match_Duplicates.png",  # Needed for matching algo during import
            "1990-10-01T12-00-00_0141_16_Hash_Match_Duplicates.png",    # Needed for matching algo during import
            "1990-10-02T12-00-00_0142_21_Hash_Match_Main.png",          # Needed for matching algo during import
            "1990-10-02T12-00-00_0143_22_Binary_Match_Trash.png",       # Needed for matching algo during import
            "1990-10-02T12-00-00_0144_23_Hash_Match_Trash.png",         # Needed for matching algo during import
            "1990-10-02T12-00-00_0145_24_Binary_Match_Duplicates.png",  # Needed for matching algo during import
            "1990-10-02T12-00-00_0146_25_Hash_Match_Duplicates.png",    # Needed for matching algo during import
            "1990-10-03T12-00-00_0147_31_Binary_Match_Trash.png",       # Needed for matching algo during import
            "1990-10-03T12-00-00_0148_32_Hash_Match_Trash.png",         # Needed for matching algo during import
            "1990-10-03T12-00-00_0149_33_Binary_Match_Duplicates.png",  # Needed for matching algo during import
            "1990-10-03T12-00-00_0150_34_Hash_Match_Duplicates.png",    # Needed for matching algo during import
            "1990-10-04T12-00-00_0151_41_Hash_Match_Trash.png",         # Needed for matching algo during import
            "1990-10-04T12-00-00_0152_42_Binary_Match_Duplicates.png",  # Needed for matching algo during import
            "1990-10-04T12-00-00_0153_43_Hash_Match_Duplicates.png",    # Needed for matching algo during import
            "1990-10-05T12-00-00_0154_51_Binary_Match_Duplicates.png",  # Needed for matching algo during import
            "1990-10-05T12-00-00_0155_52_Hash_Match_Duplicates.png",    # Needed for matching algo during import
            "1990-10-06T12-00-00_0156_61_Hash_Match_Duplicates.png",    # Needed for matching algo during import
            "1990-10-07T12-00-00_0157_71_Duplicate_Target.png",         # Needed for matching algo during import
            "1990-11-01T12-00-00_0131_10_no_metadata.jpg",              # Needed to test add exif tag
            "1990-11-01T12-00-01_0132_20_gps_metadata.jpg",             # Needed to test gps parsing
            "1990-11-01T12-00-02_0133_21_gps_metadata.jpg",             # Needed to test gps parsing
            "1990-11-01T12-00-03_0134_22_gps_metadata.jpg",             # Needed to test gps parsing
            "1990-11-01T12-00-04_0135_23_gps_metadata.jpg",             # Needed to test gps parsing
        ]

        for file in files:
            self.assertIn(file, db_files)

    def load_dump_from_file(self, file: str) -> List[Dict[str, Any]]:
        """
        Load dump from file and return object

        :param file: filename of dump in the tbl_dump_dir

        :returns:
        """
        fp = os.path.join(self.tbl_dump_dir, file)
        with open(fp, 'r') as f:
            return json.load(f)

    @staticmethod
    def drop_unpredictable_col(tgt: List[Dict[str, Any]], col_name: List[str]):
        """
        Drop a given column from a table dump

        :param tgt: Table dump to clean
        :param col_name: Name of column to drop
        """
        for row in tgt:
            for col in col_name:
                row.pop(col)

        return tgt

    def check_dyn_table_dump(self):
        """
        Go through all tables that were modified during the operation and assert that they are correct.
        """
        # Main Table
        cur_main_table = self.api.db.dump_main_table()
        main_tbl = self.load_dump_from_file("main_table.json")

        self.assertListEqual(self.drop_unpredictable_col(main_tbl, ["metadata", "google_metadata"]),
                             self.drop_unpredictable_col(cur_main_table, ["metadata", "google_metadata"]))

        # Metadata Table
        cur_metadata_table = self.api.db.dump_metadata_table()
        metadata_tbl = self.load_dump_from_file("dynamic_metadata_table.json")

        self.assertListEqual(self.drop_unpredictable_col(metadata_tbl, ["original_dirname"]),
                             self.drop_unpredictable_col(cur_metadata_table, ["original_dirname"]))

        # Dir Table
        cur_dir_table = self.api.db.dump_db_dir_table()
        dir_table = []
        self.assertListEqual(dir_table, cur_dir_table)

        self.check_table_dump_common()

    def check_custom_dir_table_dump(self):
        """
        Go through all tables that were modified during the operation and assert that they are correct.
        """
        # Main Table
        cur_main_table = self.api.db.dump_main_table()
        main_tbl = self.load_dump_from_file("main_table.json")

        self.assertListEqual(self.drop_unpredictable_col(main_tbl, ["metadata", "google_metadata"]),
                             self.drop_unpredictable_col(cur_main_table, ["metadata", "google_metadata"]))

        # Metadata Table
        cur_metadata_table = self.api.db.dump_metadata_table()
        metadata_tbl = self.load_dump_from_file("custom_dir_metadata_table.json")

        self.assertListEqual(self.drop_unpredictable_col(metadata_tbl, ["original_dirname"]),
                             self.drop_unpredictable_col(cur_metadata_table, ["original_dirname"]))

        # Dir Table
        cur_dir_table = self.api.db.dump_db_dir_table()
        dir_table = self.load_dump_from_file("custom_dir_dir_table.json")
        self.assertListEqual(dir_table, cur_dir_table)

        self.check_table_dump_common()

    def check_custom_dir_append_fname_dump(self):
        """
        Go through all tables that were modified during the operation and assert that they are correct.
        """
        # Main Table
        cur_main_table = self.api.db.dump_main_table()
        main_tbl = self.load_dump_from_file("main_table_append_fname.json")

        self.assertListEqual(self.drop_unpredictable_col(main_tbl, ["metadata", "google_metadata"]),
                             self.drop_unpredictable_col(cur_main_table, ["metadata", "google_metadata"]))

        # Metadata Table
        cur_metadata_table = self.api.db.dump_metadata_table()
        metadata_tbl = self.load_dump_from_file("custom_dir_metadata_table.json")

        self.assertListEqual(self.drop_unpredictable_col(metadata_tbl, ["original_dirname"]),
                             self.drop_unpredictable_col(cur_metadata_table, ["original_dirname"]))

        # Dir Table
        cur_dir_table = self.api.db.dump_db_dir_table()
        dir_table = self.load_dump_from_file("custom_dir_dir_table.json")
        self.assertListEqual(dir_table, cur_dir_table)

        self.assertListEqual(dir_table, cur_dir_table)

        self.check_table_dump_common()

    def check_table_dump_common(self):
        """
        Go through all tables that were modified during the operation and assert that they are correct.
        """
        # GPS Table
        cur_gps_table = self.api.db.dump_gps_location_table()
        gps_table = self.load_dump_from_file("gps_table.json")

        self.assertListEqual(gps_table, cur_gps_table)

        # Hash Table
        cur_hash_table = self.api.db.dump_hashes_table()
        hash_table = self.load_dump_from_file("hash_table.json")

        self.assertListEqual(hash_table, cur_hash_table)

        # Hash assoz Table
        cur_hash_assoz_table = self.api.db.dump_hash_assoz_table()
        hash_assoz_table = self.load_dump_from_file("hash_assoz_table.json")

        self.assertListEqual(self.drop_unpredictable_col(hash_assoz_table, ["hash_date"]),
                             self.drop_unpredictable_col(cur_hash_assoz_table, ["hash_date"]))