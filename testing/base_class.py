import unittest
from typing import Optional
from photo_lib.new_photo_api import PhotoAPI
import os
import shutil

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
        if self.api is not None:
            self.api.cleanup(True)
            self.api = None

        # Part of setup is teardown of the test db
        if os.path.exists(self.temp_db):
            shutil.rmtree(self.temp_db)

        # Part of setup is teardown of the import_source directory
        if os.path.exists(self.import_source):
            shutil.rmtree(self.import_source)
