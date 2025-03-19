import datetime
import json
import os
import os.path
from zoneinfo import ZoneInfo

from photo_lib.custom_enum import Allowed, MediaType, ImportStatus
from photo_lib.flag_dataclasses import MainFlags
from photo_lib.metadata_aggregator import DateTimeSource
from .import_base_casses import PrepareDirForImportBaseClass, PerformImportBaseClass

"""
File contains auxiliary tests run which are needed to ensure correct operation of the import methods.
"""

class TestVerifyExternalDirectory(PrepareDirForImportBaseClass):
    """
    Fully test all errors of the api.verify_external_dir function.
    """
    def test_verify_external_dir(self):
        """
        Test all possible wrong import sources and check that they are caught every time
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
        self.assertRaises(TypeError, lambda: self.api.verify_external_dir(tgt_dir=rel_root))
        self.assertRaises(FileNotFoundError, lambda: self.api.verify_external_dir(tgt_dir=root_file))
        self.assertRaises(ValueError, lambda: self.api.verify_external_dir(tgt_dir=child_of_root))
        self.assertRaises(TypeError, lambda : self.api.verify_external_dir(tgt_dir=child_file))

        # Check the db directories
        self.assertRaises(ValueError, lambda: self.api.verify_external_dir(tgt_dir=child_of_temp))
        self.assertRaises(ValueError, lambda: self.api.verify_external_dir(tgt_dir=child_of_thumb))
        self.assertRaises(ValueError, lambda: self.api.verify_external_dir(tgt_dir=child_of_trash))
        
        
class TestVerifyCustomTargetDir(PerformImportBaseClass):
    """
    Fully test the verify_custom_target_dir function.
    """
    def test_internal_dir(self):
        """
        Test the internal dir function (checks that a given path is inside the scope of the db)
        """
        rel_root = "foo/bar/baz"
        not_equal_child_of_root = os.path.join(self.import_source, "some_dir")
        child_file = os.path.join(self.temp_db, "baz.txt")

        os.makedirs(not_equal_child_of_root, exist_ok=True)
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
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=not_equal_child_of_root))

        # Check the db directories
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_of_temp))
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_of_thumb))
        self.assertRaises(ValueError, lambda: self.api.verify_custom_target_dir(tgt_dir=child_of_trash))


class TestInsertRowMainTable(PerformImportBaseClass):
    """
    Fully test the insert_main_table function.
    """
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


class TestUpdateRowMainTable(PerformImportBaseClass):
    """
    Fully test the db.update_row_main_table function
    """
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

        # Check original_filename is not allowed
        self.assertRaises(ValueError, lambda : self.api.db.update_row_main_table(key=1,
                                                                                 original_filename="Hello World"))

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


class TestUpdateMetadataRow(PerformImportBaseClass):
    """
    Fully test the update_row_metadata_table function
    """
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
        dir_key = self.api._insert_get_dir(os.path.join(self.api.root_path, "insert/second/dir"))

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


class TestSetImportStatus(PerformImportBaseClass):
    """
    Fully test the set set_imported_status function.
    """
    def test_set_imported_to_ignore(self):
        """
        Test that we can set the imported status to ignore given the right conditions
        """
        self.api.db.debug_execute_many(f"UPDATE `{self.tgt_table}` SET imported = ?, allowed = ? WHERE key = ?",
                                  [(ImportStatus.MARKED.value, Allowed.ALLOWED.value, 1),
                                   (ImportStatus.MARKED.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                                   (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 3),
                                   (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 4),
                                   (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 5),
                                   (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 6)])

        # Test MARKED, ALLOWED -> IGNORED, ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=1, status=ImportStatus.IGNORE)

        # Test MARKED, NOT_ALLOWED -> IGNORED, NOT ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=2, status=ImportStatus.IGNORE)

        # IGNORED, NOT ALLOWED -> IGNORED, NOT ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=3, status=ImportStatus.IGNORE)

        # IGNORED, NOT ALLOWED -> IGNORED, NOT ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=4, status=ImportStatus.IGNORE)

        # IMPORTED, ALLOWED -> IGNORED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=5,
                                                                                  status=ImportStatus.IGNORE))

        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=6,
                                                                                  status=ImportStatus.IGNORE))

        # Get rows
        self.api.db.debug_execute(F"SELECT imported, allowed, key FROM `{self.tgt_table}` "
                                  F"WHERE key in (1, 2, 3, 4, 5, 6) ORDER BY key")

        res = self.api.db.sq_cur.fetchall()
        self.assertListEqual(res, [(ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 1),
                                   (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                                   (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 3),
                                   (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 4),
                                   (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 5),
                                   (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 6)])

    def test_set_imported_status_marked_for_import(self):
        """
        Test the set_imported_status function with marked_for_import.
        """
        self.api.db.debug_execute_many(f"UPDATE `{self.tgt_table}` SET imported = ?, allowed = ? WHERE key = ?",
                                  [(ImportStatus.MARKED.value, Allowed.ALLOWED.value, 1),
                                   (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                                   (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 3),
                                   (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 4),
                                   (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 5)])

        # MARKED, ALLOWED -> MARKED, ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=1, status=ImportStatus.MARKED)

        # FAIL IGNORED, NOT ALLOWED -> IGNORED, NOT ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=2,
                                                                                  status=ImportStatus.MARKED))

        # IGNORE, ALLOWED -> MARKED, ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=3, status=ImportStatus.MARKED)

        # FAIL IMPORTED, ALLOWED -> IMPORTED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=4,
                                                                                  status=ImportStatus.MARKED))

        # FAIL DELETED, ALLOWED -> DELETED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=5,
                                                                                  status=ImportStatus.MARKED))

        # Get rows
        self.api.db.debug_execute(F"SELECT imported, allowed, key FROM `{self.tgt_table}` "
                                  F"WHERE key in (1, 2, 3, 4, 5) ORDER BY key")

        self.assertListEqual(self.api.db.sq_cur.fetchall(),
                             [(ImportStatus.MARKED.value, Allowed.ALLOWED.value, 1),
                              (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                              (ImportStatus.MARKED.value, Allowed.ALLOWED.value, 3),
                              (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 4),
                              (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 5)]
                             )

    def test_set_imported_status_imported(self):
        """
        Test the set_imported_status function with imported.
        """
        self.api.db.debug_execute_many(f"UPDATE `{self.tgt_table}` SET imported = ?, allowed = ? WHERE key = ?",
                                  [(ImportStatus.MARKED.value, Allowed.ALLOWED.value, 1),
                                   (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                                   (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 3),
                                   (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 4),
                                   (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 5)])

        # Shouldn't work because import_key not provided
        self.assertRaises(ValueError, lambda : self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                               key=1,
                                                                               status=ImportStatus.IMPORTED))

        # MARKED, ALLOWED -> IMPORTED, ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=1, status=ImportStatus.IMPORTED, import_key=-1)

        # FAIL: IGNORE, NOT ALLOWED -> IGNORE, NOT ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=2,
                                                                                  import_key=-1,
                                                                                  status=ImportStatus.IMPORTED))

        # FAIL: IGNORE, ALLOWED -> IGNORE, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=3,
                                                                                  import_key=-1,
                                                                                  status=ImportStatus.IMPORTED))

        # FAIL: IMPORTED, ALLOWED -> IMPORTED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=4,
                                                                                  import_key=-1,
                                                                                  status=ImportStatus.IMPORTED))

        # FAIL: DELETED, ALLOWED -> DELETED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=5,
                                                                                  import_key=-1,
                                                                                  status=ImportStatus.IMPORTED))

        # Get rows
        self.api.db.debug_execute(F"SELECT imported, allowed, key FROM `{self.tgt_table}` "
                                  F"WHERE key in (1, 2, 3, 4, 5) ORDER BY key")

        self.assertListEqual(self.api.db.sq_cur.fetchall(),
                             [(ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 1),
                              (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                              (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 3),
                              (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 4),
                              (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 5)])

    def test_set_imported_status_deleted(self):
        """
        Test the set_imported_status function with deleted.
        """
        self.api.db.debug_execute_many(f"UPDATE `{self.tgt_table}` SET imported = ?, allowed = ? WHERE key = ?",
                                  [(ImportStatus.MARKED.value, Allowed.ALLOWED.value, 1),
                                   (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                                   (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 3),
                                   (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 4),
                                   (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 5)])

        # MARKED, ALLOWED -> DELETED, ALLOWED
        self.api.db.set_imported_status(tbl_name=self.tgt_table, key=1, status=ImportStatus.DELETED)

        # FAIL: IGNORE, NOT ALLOWED -> IGNORE, NOT ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=2,
                                                                                  status=ImportStatus.DELETED))

        # FAIL: IGNORE, ALLOWED -> IGNORE, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=3,
                                                                                  status=ImportStatus.DELETED))

        # FAIL: IMPORTED, ALLOWED -> IMPORTED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=4,
                                                                                  status=ImportStatus.DELETED))

        # FAIL: DELETED, ALLOWED -> DELETED, ALLOWED
        self.assertRaises(AssertionError, lambda: self.api.db.set_imported_status(tbl_name=self.tgt_table,
                                                                                  key=5,
                                                                                  status=ImportStatus.DELETED))

        # Get rows
        self.api.db.debug_execute(F"SELECT imported, allowed, key FROM `{self.tgt_table}` "
                                  F"WHERE key in (1, 2, 3, 4, 5) ORDER BY key")

        self.assertListEqual(self.api.db.sq_cur.fetchall(),
                             [(ImportStatus.DELETED.value, Allowed.ALLOWED.value, 1),
                              (ImportStatus.IGNORE.value, Allowed.NOT_ALLOWED_EXT.value, 2),
                              (ImportStatus.IGNORE.value, Allowed.ALLOWED.value, 3),
                              (ImportStatus.IMPORTED.value, Allowed.ALLOWED.value, 4),
                              (ImportStatus.DELETED.value, Allowed.ALLOWED.value, 5)])