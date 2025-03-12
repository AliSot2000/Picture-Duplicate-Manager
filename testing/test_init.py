import logging
import os
import shutil
import unittest

from pydantic_core import ValidationError

from photo_lib import defaults
from photo_lib.db_definitions import Version
from photo_lib.new_photo_db import PhotoDB
from photo_lib.new_photo_model import PhotoAPI


test_scratch = os.path.join(os.path.dirname(__file__), "scratch")



class BaseInit(unittest.TestCase):
    def setUp(self):  # pragma: no cover
        """
        Clear out the scratch directory for testing and create a new one
        """
        # Needed in case tearDown wasn't called because of exception or debug
        if os.path.exists(test_scratch):
            print(f"Clearing Test Directory")
            shutil.rmtree(test_scratch)

        if not os.path.exists(test_scratch):
            print(f"Making Test Directory")
            os.makedirs(test_scratch)

    def tearDown(self):  # pragma: no cover
        """
        Remove the scratch directory for testing
        """
        if os.path.exists(test_scratch):
            print(f"Clearing Test Directory")
            shutil.rmtree(test_scratch)

class TestDBInit(BaseInit):

    def test_exists(self):
        """
        Check that an error is raised when the db is supposed to initialize and a db exists already.
        """
        db_path = os.path.join(test_scratch, "test.db")
        with open(db_path, "w") as f:
            f.write("Content")

        def create():
            PhotoDB(root_path=test_scratch,
                    db_path=db_path,
                    init=True,
                    init_loggers=False,
                    config=PhotoAPI.build_default_config())

        self.assertRaises(FileExistsError, create)

    def test_missing(self):
        """
        Check that the database raises a file not exists error, if you attempt to reconnect to one that doens't exist
        """
        db_path = os.path.join(test_scratch, "test.db")

        def create():
            PhotoDB(root_path=test_scratch,
                    db_path=db_path,
                    init=False,
                    init_loggers=False,
                    config=PhotoAPI.build_default_config())

        self.assertRaises(FileNotFoundError, create)

    def test_init_and_connect(self):
        """
        Check that the database is created correctly and check that the reconnection process works
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=False,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        db.cleanup()

        self.assertTrue(os.path.exists(db_path))

        ex_db = PhotoDB(
            root_path=test_scratch, db_path=db_path, init=False, init_loggers=False,
            config=PhotoAPI.build_default_config(), verify=True)

        self.assertIsInstance(ex_db, PhotoDB)
        self.assertTrue(ex_db.verified)

        ex_db.cleanup()

    def test_detach(self):
        """
        Check that after detachment, verified is set correctly
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=False,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        new_db = PhotoDB.detach(db)

        del db

        self.assertIsInstance(new_db, PhotoDB)
        self.assertTrue(new_db.verified)

        new_db.cleanup()

    def test_cover_logging(self):
        """
        Check that initializing the loggers doesn't cause any errors
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        db.cleanup()

    def test_missing_static_table(self):
        """
        Create database where the first table is missing. And the if res is None path is taken
        """

        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=False,
                     config=PhotoAPI.build_default_config())

        db.debug_execute("DROP TABLE duplicates")

        db.commit()
        db.cleanup()

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=False,
                     init_loggers=False,
                     verify=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertFalse(db.verified)

        # Need to do fast, because db not verified.
        db.cleanup(fast=True)

    def test_wrong_table_decl(self):
        """
        Create an instance and change a table definition.
        """

        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        # Create a wrong presence table
        db.debug_execute("DROP TABLE presence_table")
        db.debug_execute("CREATE TABLE presence_table ("
                         "main_key INTEGER NOT NULL, "
                         "message TEXT, "
                         "value TEXT, "
                         "FOREIGN KEY (main_key) REFERENCES main(key))")

        db.commit()
        db.cleanup()

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=False,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())


        self.assertIsInstance(db, PhotoDB)
        self.assertFalse(db.verified)

        # Need to do fast, because db not verified.
        db.cleanup(fast=True)

    def test_generic_tables(self):
        """
        Test that generic tables are verified correctly.
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        db.add_import_table(root_path="/foo/bar")

        db.cleanup()

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=False,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        db.cleanup(fast=True)

    def test_generic_tables_wrong_decl(self):
        """
        Create a table and update it to have a wrong definition
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        tbl_name = db.add_import_table(root_path="/foo/bar")
        db.debug_execute(f"DROP TABLE `{tbl_name}`")
        db.debug_execute(f"CREATE TABLE `{tbl_name}` (key INTEGER, value TEXT)")

        db.cleanup()

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=False,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertFalse(db.verified)

        db.cleanup(fast=True)

    def test_table_removed(self):
        """
        Create a Create table and remove the table but not the entry in the parent table. Check it is removed correctly.
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        tbl_name = db.add_import_table(root_path="/foo/bar")
        db.debug_execute(f"DROP TABLE `{tbl_name}`")

        db.cleanup()

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=False,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        self.assertFalse(db.import_table_exists(tbl_name))

        db.cleanup(fast=True)

    def test_paths(self):
        """
        Check that path generation works correctly.
        """
        db_path = os.path.join(test_scratch, "test.db")

        db = PhotoDB(root_path=test_scratch,
                     db_path=db_path,
                     init=True,
                     init_loggers=True,
                     config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoDB)
        self.assertTrue(db.verified)

        # Check the paths like this
        self.assertEqual(db.get_temp_dir(), os.path.join(test_scratch, ".temp"))
        self.assertEqual(db.get_thumb_dir(), os.path.join(test_scratch, ".thumbnails"))
        self.assertEqual(db.get_trash_dir(), os.path.join(test_scratch, ".trash"))

        # Set abs paths
        db.config.temp_path = temp = os.path.join(test_scratch, "foo")
        db.config.trash = trash = os.path.join(test_scratch, "bar")
        db.config.thumbnail = thumbnail = os.path.join(test_scratch, "baz")

        self.assertEqual(db.get_temp_dir(), temp)
        self.assertEqual(db.get_thumb_dir(), thumbnail)
        self.assertEqual(db.get_trash_dir(), trash)

        db.cleanup(fast=True)


class TestAPIInit(BaseInit):
    def test_base_init(self):
        """
        Check the init is working the way we expect if nothing is wrong
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False)

        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

    def test_base_init_w_loggers(self):
        """
        Check the init is working the way we expect if nothing is wrong
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=True, opt_integrity_check=True)

        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

    def test_init_with_config(self):
        """
        Check the init is working the way we expect if nothing is wrong
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False, opt_integrity_check=False,
                      config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

    def test_root_dir_created(self):
        """
        Check that the database will create the root_dir, if it is not
        """
        # Check the dire is created
        shutil.rmtree(test_scratch)

        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False, opt_integrity_check=False,
                      config=PhotoAPI.build_default_config())

        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

    def test_config_exists(self):
        """
        Check that the database will create the root_dir, if it is not
        """
        with open(os.path.join(test_scratch, defaults.config_path), "w") as f:
            f.write(PhotoAPI.build_default_config().model_dump_json())

        def test_fn():
            PhotoAPI(root_path=test_scratch,
                     init=True, init_loggers=False, opt_integrity_check=False,
                     config=PhotoAPI.build_default_config())

        self.assertRaises(FileExistsError, test_fn)

    def test_db_exists(self):
        with open(os.path.join(test_scratch, defaults.db_file), "w") as f:
            f.write("Content")

        def test_fn():
            PhotoAPI(root_path=test_scratch,
                     init=True, init_loggers=False, opt_integrity_check=False,
                     config=PhotoAPI.build_default_config())

        self.assertRaises(FileExistsError, test_fn)

    def test_logger_reload(self):
        """
        Check reload loggers works as expected and check the loggers are correctly loaded
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False, opt_integrity_check=False,
                      config=PhotoAPI.build_default_config())

        # Check the DB
        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        # Check the logger defaults
        self.assertEqual(db.main_logger.name, PhotoAPI.main_logger_name)
        self.assertEqual(db.integrity_logger.name, PhotoAPI.integrity_logger_name)
        self.assertEqual(db.rare_occurrence_logger.name, PhotoAPI.rare_occurrence_logger_name)

        self.assertEqual(db.mda_logger.name, PhotoAPI.metadata_aggregator_logger_name)
        self.assertEqual(db.mda_parsing_logger.name, PhotoAPI.metadata_aggregator_parsing_logger_name)

        db.main_logger = logging.getLogger("a")
        db.integrity_logger = logging.getLogger("b")
        db.rare_occurrence_logger = logging.getLogger("c")

        db.mda_logger = logging.getLogger("d")
        db.mda_parsing_logger = logging.getLogger("e")

        # check loggers were updated
        self.assertEqual(db.main_logger.name, "a")
        self.assertEqual(db.integrity_logger.name, "b")
        self.assertEqual(db.rare_occurrence_logger.name, "c")

        self.assertEqual(db.mda_logger.name, "d")
        self.assertEqual(db.mda_parsing_logger.name, "e")

        db.reload_loggers()

        # Check the logger defaults
        self.assertEqual(db.main_logger.name, PhotoAPI.main_logger_name)
        self.assertEqual(db.integrity_logger.name, PhotoAPI.integrity_logger_name)
        self.assertEqual(db.rare_occurrence_logger.name, PhotoAPI.rare_occurrence_logger_name)

        self.assertEqual(db.mda_logger.name, PhotoAPI.metadata_aggregator_logger_name)
        self.assertEqual(db.mda_parsing_logger.name, PhotoAPI.metadata_aggregator_parsing_logger_name)

        db.cleanup(fast=True)

    def test_connect_base(self):
        """
        Check the database correctly reconnects after closing
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False, opt_integrity_check=False,
                      config=PhotoAPI.build_default_config())

        # Check the DB
        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

        db = PhotoAPI(root_path=test_scratch,
                      init=False, init_loggers=False, opt_integrity_check=False)

        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

    def test_connect_missing_config(self):
        """
        Check the database correctly reconnects after closing
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False, opt_integrity_check=False,
                      config=PhotoAPI.build_default_config())

        # Check the DB
        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.cleanup(fast=True)

        os.remove(os.path.join(db.root_path, defaults.config_path))
        self.assertFalse(os.path.exists(os.path.join(db.root_path, defaults.config_path)))

        def test_fn():
            PhotoAPI(root_path=test_scratch, init=False, init_loggers=False, opt_integrity_check=False)

        self.assertRaises(FileNotFoundError, test_fn)

    def test_connect_wrong_version(self):
        """
        Check that the config version is correctly detected after an error
        """
        db = PhotoAPI(root_path=test_scratch,
                      init=True, init_loggers=False, opt_integrity_check=False,
                      config=PhotoAPI.build_default_config())

        # Check the DB
        self.assertIsInstance(db, PhotoAPI)
        self.assertIsNotNone(db.mda)

        self.assertTrue(os.path.exists(db.db.get_temp_dir()))
        self.assertTrue(os.path.exists(db.db.get_thumb_dir()))
        self.assertTrue(os.path.exists(db.db.get_trash_dir()))

        self.assertTrue(os.path.exists(os.path.join(db.root_path, defaults.config_path)))
        self.assertTrue(os.path.exists(db.db.root_path))

        db.config.version = Version(major=0, minor=0, patch=0)
        db.write_config()

        db.cleanup(fast=True)

        def test_fn():
            PhotoAPI(root_path=test_scratch, init=False, init_loggers=False, opt_integrity_check=False)

        self.assertRaises(ValueError, test_fn)

    def test_validation_error(self):
        """
        Check that writing a config that isn't a valid config raises an validation error
        """
        with open(os.path.join(test_scratch, defaults.config_path), "w") as file:
            file.write("Some content")

        def test_fn():
            PhotoAPI(root_path=test_scratch, init=False, init_loggers=False, opt_integrity_check=False)

        self.assertRaises(ValidationError, test_fn)

    # INFO: missing and present db alrady checked in DBINIT

