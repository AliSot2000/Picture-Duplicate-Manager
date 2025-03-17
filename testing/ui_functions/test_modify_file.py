import datetime
import logging
import os
import shutil
from zoneinfo import ZoneInfoNotFoundError, ZoneInfo

from photo_lib.metadata_aggregator import DateTimeSource, DoubleKey
from .base_class import TestClassifyBase

"""
This file fully tests the following functions:
- api.modify_timezone
- api.change_datetime
- metadata_aggregator.serialize_key
- api.change_filename
- api.move_file
- api._internal_move_file
- api._internal_rename

The file covers 100% of the function without specific tests:
- api.db.get_path_data
- api._add_update_exif_tag
- api._handle_gps_import
- api.db.insert_get_gps_loc
"""


class TestModifyTimezone(TestClassifyBase):
    """
    Fully test the modify_timezone function.
    """
    def test_raised_errors(self):
        """
        Check that the correct errors are raised.
        """
        # not supported timezone
        self.assertRaises(TypeError, lambda : self.api.modify_timezone(key=1, _target_tz=5))

        # Key doesn't exist
        self.assertRaises(ValueError, lambda : self.api.modify_timezone(key=1000, _target_tz="CET"))

        # Wrong flags
        self.api.move_to_trash(2)
        self.api.move_to_duplicates(child_key=4, parent_key=3)

        flags = self.api.db.get_main_flags(key=5)
        self.assertIsNotNone(flags)

        flags.present = False
        self.api.db.update_row_main_table(key=5, flags=flags)

        self.assertRaises(ValueError, lambda : self.api.modify_timezone(key=2, _target_tz="CET"))
        self.assertRaises(ValueError, lambda : self.api.modify_timezone(key=4, _target_tz="CET"))
        self.assertRaises(ValueError, lambda : self.api.modify_timezone(key=5, _target_tz="CET"))

        self.assertRaises(ZoneInfoNotFoundError, lambda : self.api.modify_timezone(key=5, _target_tz="unga"))

    def test_early_abort(self):
        """
        Test, that if two timezones have the same utc offset, nothing happens
        """
        new_tz = "MET"
        prev_file = self.api.resolve_key_to_path(1)

        self.api.modify_timezone(key=1, _target_tz=new_tz)

        # check updated timezone
        mr = self.api.db.get_main_row(1)
        self.assertIsNotNone(mr)

        # Check timezone correctly named
        self.assertEqual(mr.timezone, new_tz)

        # check that the file is still in the same place
        self.assertTrue(os.path.exists(prev_file))

    def test_add_gps(self):
        """
        Check that a gps entry is correctly added
        """
        new_tz = "EST"
        prev_file = self.api.resolve_key_to_path(1)
        prev_mdr = self.api.db.get_metadata_row(1)
        prev_mr = self.api.db.get_main_row(1)

        # Check datetime
        self.assertIsNotNone(prev_mdr)
        self.assertIsNotNone(prev_mr)

        self.assertIsNone(prev_mdr.gps_lat)
        self.assertIsNone(prev_mdr.gps_long)

        self.assertEqual(prev_mr.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
        )

        gps_lat = 40.71427000
        gps_long = -74.00597000

        # Move timezone
        self.api.modify_timezone(key=1, _target_tz=new_tz, gps_lat=gps_lat, gps_long=gps_long, add_exif_tag=False)

        # check destination path
        new_dt = prev_mr.datetime.astimezone(ZoneInfo(new_tz))
        new_name = self.api.db.db_name(prev_mr.original_filename, 1, new_dt)
        path = self.api.db.dt_to_dir(new_dt)
        self.assertTrue(os.path.exists(os.path.join(self.api.root_path, path, new_name)))
        self.assertFalse(os.path.exists(prev_file))

        # new rows
        new_mr = self.api.db.get_main_row(1)
        new_mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(new_mdr)
        self.assertIsNotNone(new_mr)

        # Check new gps
        self.assertEqual(new_mdr.gps_lat, gps_lat)
        self.assertEqual(new_mdr.gps_long, gps_long)

        # Check datetime
        self.assertEqual(new_mr.datetime, new_dt)
        self.assertEqual(new_mr.timezone, new_tz)

        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(1)))

    def test_replace_branches(self):
        """
        Test the outcome of replace = true and replace = false
        """
        new_tz = "EST"

        prev_file1 = self.api.resolve_key_to_path(1)
        prev_file2 = self.api.resolve_key_to_path(2)

        prev_mdr1 = self.api.db.get_metadata_row(1)
        prev_mr1 = self.api.db.get_main_row(1)

        prev_mdr2 = self.api.db.get_metadata_row(2)
        prev_mr2 = self.api.db.get_main_row(2)

        # Check datetime
        self.assertIsNotNone(prev_mdr1)
        self.assertIsNotNone(prev_mr1)

        self.assertIsNotNone(prev_mdr2)
        self.assertIsNotNone(prev_mr2)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
        )
        self.assertEqual(prev_mr2.datetime, datetime.datetime(
            year=1990, month=2, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
        )

        # Check only one hash present in the beginning
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(1)))
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(1)))

        self.api.modify_timezone(key=1, _target_tz=new_tz, replace=False)
        self.api.modify_timezone(key=2, _target_tz=new_tz, replace=True)

        new_dt1 = prev_mr1.datetime.astimezone(ZoneInfo(new_tz))
        new_dt2 = prev_mr2.datetime.replace(tzinfo=ZoneInfo(new_tz))

        new_name1 = self.api.db.db_name(prev_mr1.original_filename, 1, new_dt1)
        new_name2 = self.api.db.db_name(prev_mr2.original_filename, 2, new_dt2)

        new_path1 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt1), new_name1)
        new_path2 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt2), new_name2)

        # New paths exist
        self.assertTrue(os.path.exists(new_path1))
        self.assertTrue(os.path.exists(new_path2))

        # Old paths removed
        self.assertFalse(os.path.exists(prev_file1))
        self.assertEqual(prev_file2, new_path2)

        # new rows
        new_mr1 = self.api.db.get_main_row(1)
        new_mr2 = self.api.db.get_main_row(2)

        self.assertIsNotNone(new_mr1)
        self.assertIsNotNone(new_mr2)

        # Check datetime
        self.assertEqual(new_mr1.datetime, new_dt1)
        self.assertEqual(new_mr1.timezone, new_tz)
        self.assertEqual(new_mr2.datetime, new_dt2)
        self.assertEqual(new_mr2.timezone, new_tz)

        # check there are two hashes for the two files
        fh1 = [{"hash": hs, "file_size": fs, "initial": ini}
               for hs, fs, _, ini in  self.api.db.get_all_hashes_of_file(1)]
        fh2 = [{"hash": hs, "file_size": fs, "initial": ini}
               for hs, fs, _, ini in  self.api.db.get_all_hashes_of_file(2)]

        ex_fh1 = [
            {
                'hash': 'f99faa2783761e229fa56eb97d3271852a1cbdbff81dbc2366815714d6c9e4f4',
                'file_size': 18258,
                'initial': True
            },
            {
                'hash': '042d3f52d4e60b15c57411e190dad2d2c323656d094a1aeff1949c86f81709f1',
                'file_size': 18258,
                'initial': False
            }
        ]
        ex_fh2 = [
            {
                'hash': '12adde7b6c3908bfd0f30fa694f1f8d73ea8a27edc06860e9bd8c40bb926acc8',
                'file_size': 18567,
                'initial': True
            },
            {
                'hash': 'a2e04329ad851e6a7394a288195b6359ded0afb745003ea5542499d204eb8ed6',
                'file_size': 18567,
                'initial': False
            }
        ]

        self.assertListEqual(fh1, ex_fh1)
        self.assertListEqual(fh2, ex_fh2)

    def test_cache_update_and_no_tag(self):
        """
        Adding update for filename_to_key_cache, and make sure the number of hashes is 1
        """
        new_tz = "EST"

        prev_file1 = self.api.resolve_key_to_path(1)

        prev_mr1 = self.api.db.get_main_row(1)

        self.assertIsNotNone(prev_mr1)

        _ = self.api.filename_to_key(prev_mr1.db_name)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
        )

        self.api.modify_timezone(key=1, _target_tz=new_tz, replace=False, add_exif_tag=False)

        new_dt1 = prev_mr1.datetime.astimezone(ZoneInfo(new_tz))
        new_name1 = self.api.db.db_name(prev_mr1.original_filename, 1, new_dt1)
        new_path1 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt1), new_name1)

        # New paths exist
        self.assertTrue(os.path.exists(new_path1))

        # Old paths removed
        self.assertFalse(os.path.exists(prev_file1))

        # new rows
        new_mr1 = self.api.db.get_main_row(1)

        self.assertIsNotNone(new_mr1)

        # Check datetime
        self.assertEqual(new_mr1.datetime, new_dt1)
        self.assertEqual(new_mr1.timezone, new_tz)

        # check hashes
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(1)))

        # Check cache
        self.assertEqual(self.api.filename_to_key(new_name1), 1)
        self.assertIsNone(self.api.filename_to_key(prev_mr1.db_name))

    def test_all_timezone_types(self):
        """
        Test all possible types of timezones
        """
        tz1 = datetime.timedelta(hours=2)
        tz2 = "EST"
        tz3 = ZoneInfo("US/Pacific")

        # Paths
        prev_file1 = self.api.resolve_key_to_path(1)
        prev_file2 = self.api.resolve_key_to_path(2)
        prev_file3 = self.api.resolve_key_to_path(3)

        # Check datetime
        prev_mr1 = self.api.db.get_main_row(1)
        prev_mr2 = self.api.db.get_main_row(2)
        prev_mr3 = self.api.db.get_main_row(3)

        self.assertIsNotNone(prev_mr1)
        self.assertIsNotNone(prev_mr2)
        self.assertIsNotNone(prev_mr3)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )
        self.assertEqual(prev_mr2.datetime, datetime.datetime(
            year=1990, month=2, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )
        self.assertEqual(prev_mr3.datetime, datetime.datetime(
            year=1990, month=2, day=1, hour=12, minute=0, second=1, tzinfo=ZoneInfo("CET"))
                         )

        self.api.modify_timezone(key=1, _target_tz=tz1, replace=False, add_exif_tag=False)
        self.api.modify_timezone(key=2, _target_tz=tz2, replace=False, add_exif_tag=False)
        self.api.modify_timezone(key=3, _target_tz=tz3, replace=False, add_exif_tag=False)

        # Ensure new paths exist
        new_dt1 = prev_mr1.datetime.astimezone(datetime.timezone(tz1))
        new_dt2 = prev_mr2.datetime.astimezone(ZoneInfo(tz2))
        new_dt3 = prev_mr3.datetime.astimezone(tz3)

        new_name1 = self.api.db.db_name(prev_mr1.original_filename, 1, new_dt1)
        new_name2 = self.api.db.db_name(prev_mr2.original_filename, 2, new_dt2)
        new_name3 = self.api.db.db_name(prev_mr3.original_filename, 3, new_dt3)

        new_path1 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt1), new_name1)
        new_path2 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt2), new_name2)
        new_path3 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt3), new_name3)

        # Paths exist
        self.assertTrue(os.path.exists(new_path1))
        self.assertTrue(os.path.exists(new_path2))
        self.assertTrue(os.path.exists(new_path3))

        # Old paths are gone
        self.assertFalse(os.path.exists(prev_file1))
        self.assertFalse(os.path.exists(prev_file2))
        self.assertFalse(os.path.exists(prev_file3))

        # new rows
        new_mr1 = self.api.db.get_main_row(1)
        new_mr2 = self.api.db.get_main_row(2)
        new_mr3 = self.api.db.get_main_row(3)

        self.assertIsNotNone(new_mr1)
        self.assertIsNotNone(new_mr2)
        self.assertIsNotNone(new_mr3)

        # Check datetime
        self.assertEqual(new_mr1.datetime, new_dt1)
        self.assertEqual(new_mr2.datetime, new_dt2)
        self.assertEqual(new_mr3.datetime, new_dt3)

        self.assertEqual(new_mr1.timezone, new_dt1.tzname())
        self.assertEqual(new_mr2.timezone, new_dt2.tzname())
        self.assertEqual(new_mr3.timezone, new_dt3.tzname())

        # check hashes
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(1)))
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(2)))
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(3)))

    def test_move(self):
        """
        Test that the file is moved correctly
        """
        tz = ZoneInfo("Etc/GMT-14")

        prev_file1 = self.api.resolve_key_to_path(1)

        prev_mr1 = self.api.db.get_main_row(1)

        self.assertIsNotNone(prev_mr1)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
        )

        self.api.modify_timezone(key=1, _target_tz=tz, replace=False, rename=False, add_exif_tag=False)

        new_dt1 = prev_mr1.datetime.astimezone(tz)
        new_path1 = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt1), prev_mr1.db_name)

        # New paths exist
        self.assertTrue(os.path.exists(new_path1))

        # Old paths removed
        self.assertFalse(os.path.exists(prev_file1))

        # new rows
        new_mr1 = self.api.db.get_main_row(1)

        self.assertIsNotNone(new_mr1)

        # Check datetime
        self.assertEqual(new_mr1.datetime, new_dt1)
        self.assertEqual(new_mr1.timezone, new_dt1.tzname())

        # check hashes
        self.assertEqual(1, len(self.api.db.get_all_hashes_of_file(1)))


class TestChangeDatetime(TestClassifyBase):
    """
    Fully test the change_datetime function
    """
    def test_errors(self):
        """
        Check that all errors are raised correctly.
        """
        naive_dt = datetime.datetime(year=2025, month=3, day=17, hour=12, minute=0, second=0)
        tz_dt = naive_dt.replace(tzinfo=ZoneInfo("CET"))

        # Check an error is raised if a naive datetime object is passed
        self.assertRaises(TypeError, lambda : self.api.change_datetime(key=1,
                                                                        tag="Custom",
                                                                        dts=DateTimeSource.CUSTOM,
                                                                        new_dt=naive_dt))

        # Check that the key needs to exist
        self.assertRaises(ValueError, lambda : self.api.change_datetime(key=1000,
                                                                        tag="Custom",
                                                                        dts=DateTimeSource.CUSTOM,
                                                                        new_dt=tz_dt))

        # Wrong flags
        self.api.move_to_trash(2)
        self.api.move_to_duplicates(child_key=4, parent_key=3)

        flags = self.api.db.get_main_flags(key=5)
        self.assertIsNotNone(flags)

        flags.present = False
        self.api.db.update_row_main_table(key=5, flags=flags)

        self.assertRaises(ValueError, lambda: self.api.change_datetime(key=2,
                                                                       tag="Custom",
                                                                       dts=DateTimeSource.CUSTOM,
                                                                       new_dt=tz_dt))
        self.assertRaises(ValueError, lambda: self.api.change_datetime(key=2,
                                                                       tag="Custom",
                                                                       dts=DateTimeSource.CUSTOM,
                                                                       new_dt=tz_dt))
        self.assertRaises(ValueError, lambda: self.api.change_datetime(key=2,
                                                                       tag="Custom",
                                                                       dts=DateTimeSource.CUSTOM,
                                                                       new_dt=tz_dt))

        self.assertRaises(TypeError, lambda : self.api.change_datetime(key=1,
                                                                       tag=1234,
                                                                       dts=DateTimeSource.CUSTOM,
                                                                       new_dt=tz_dt))

    def test_no_exiftag_on_equal_dt(self):
        """
        Check that when two datetime objects have the same offset, now change is performed on the exiftag
        """
        new_tz = "MET"

        prev_file = self.api.resolve_key_to_path(1)

        # Get the main row
        prev_mr1 = self.api.db.get_main_row(1)
        self.assertIsNotNone(prev_mr1)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )

        new_dt = prev_mr1.datetime.astimezone(tz=ZoneInfo(new_tz))

        self.api.change_datetime(key=1, tag="CUSTOM", dts=DateTimeSource.CUSTOM, new_dt=new_dt, add_exif_tag=True)

        # check results
        new_name = self.api.db.db_name(prev_mr1.original_filename, 1, new_dt)
        new_path = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt), new_name)

        # New path present, old path not
        self.assertTrue(os.path.exists(new_path))
        self.assertEqual(prev_file, new_path)

        # get row
        new_mr = self.api.db.get_main_row(1)
        new_mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(new_mr)
        self.assertIsNotNone(new_mdr)

        # Check timezone and datetime
        self.assertEqual(new_mr.datetime, new_dt)
        self.assertEqual(new_mr.timezone, new_tz)

        # check metadata row
        self.assertEqual(new_mdr.datetime_source, DateTimeSource.CUSTOM)
        self.assertEqual(new_mdr.naming_tag, "CUSTOM")

        # Check no new hash was added since the offset is equal
        self.assertEqual(len(self.api.db.get_all_hashes_of_file(1)), 1)

    def test_gps_and_cache_update(self):
        """
        Test that the gps data is added and also that cache update is performed
        """
        gps_lat = 40.71427000
        gps_long = -74.00597000

        new_tz = "EST"

        prev_file = self.api.resolve_key_to_path(1)

        prev_mr1 = self.api.db.get_main_row(1)
        self.assertIsNotNone(prev_mr1)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )

        new_dt = prev_mr1.datetime.astimezone(tz=ZoneInfo(new_tz))

        prev_mdr1 = self.api.db.get_metadata_row(1)
        self.assertIsNotNone(prev_mdr1)

        self.assertIsNone(prev_mdr1.gps_long)
        self.assertIsNone(prev_mdr1.gps_lat)

        # Populate cache
        self.api.filename_to_key(prev_mr1.db_name)

        # Check that there's one hash
        self.assertEqual(len(self.api.db.get_all_hashes_of_file(1)), 1)

        # Perform update
        self.api.change_datetime(key=1,
                                 tag="CUSTOM",
                                 dts=DateTimeSource.CUSTOM,
                                 new_dt=new_dt,
                                 add_exif_tag=True,
                                 gps_long=gps_long,
                                 gps_lat=gps_lat)

        new_name = self.api.db.db_name(prev_mr1.original_filename, 1, new_dt)
        new_path = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt), new_name)

        # check paths
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(prev_file))

        new_mr1 = self.api.db.get_main_row(1)
        new_mdr1 = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(new_mr1)
        self.assertIsNotNone(new_mdr1)

        # check new datetime
        self.assertEqual(new_mr1.datetime, new_dt)
        self.assertEqual(new_mr1.timezone, new_dt.tzname())

        # Test metadata
        self.assertEqual(new_mdr1.datetime_source, DateTimeSource.CUSTOM)
        self.assertEqual(new_mdr1.naming_tag, "CUSTOM")
        self.assertEqual(new_mdr1.gps_lat, gps_lat)
        self.assertEqual(new_mdr1.gps_long, gps_long)

        # Check new hashes were added
        fh1 = [{"hash": hs, "file_size": fs, "initial": ini}
               for hs, fs, _, ini in  self.api.db.get_all_hashes_of_file(1)]

        ex_fh1 = [
            {
                'hash': 'f99faa2783761e229fa56eb97d3271852a1cbdbff81dbc2366815714d6c9e4f4',
                'file_size': 18258,
                'initial': True
            },
            {
                'hash': '042d3f52d4e60b15c57411e190dad2d2c323656d094a1aeff1949c86f81709f1',
                'file_size': 18258,
                'initial': False
            }
        ]

        self.assertListEqual(fh1, ex_fh1)

        # Check cache
        self.assertEqual(self.api.filename_to_key(new_name), 1)
        self.assertIsNone(self.api.filename_to_key(prev_mr1.db_name))

    def test_move(self):
        """
        Test correct function when moving a file
        """
        new_tz = "Etc/GMT-14"

        prev_file = self.api.resolve_key_to_path(1)

        # Get the main row
        prev_mr1 = self.api.db.get_main_row(1)
        self.assertIsNotNone(prev_mr1)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )

        new_dt = prev_mr1.datetime.astimezone(tz=ZoneInfo(new_tz))

        self.api.change_datetime(key=1,
                                 tag="CUSTOM",
                                 dts=DateTimeSource.CUSTOM,
                                 new_dt=new_dt,
                                 add_exif_tag=False,
                                 rename=False)

        # check results
        new_path = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt), prev_mr1.db_name)

        # New path present, old path not
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(prev_file))

        # get row
        new_mr = self.api.db.get_main_row(1)
        new_mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(new_mr)
        self.assertIsNotNone(new_mdr)

        # Check timezone and datetime
        self.assertEqual(new_mr.datetime, new_dt)
        self.assertEqual(new_mr.timezone, new_dt.tzname())

        # check metadata row
        self.assertEqual(new_mdr.datetime_source, DateTimeSource.CUSTOM)
        self.assertEqual(new_mdr.naming_tag, "CUSTOM")

        # Check no new hash was added since the offset is equal
        self.assertEqual(len(self.api.db.get_all_hashes_of_file(1)), 1)

    def test_move_with_list_key(self):
        """
        Test correct function when moving a file
        """
        new_tz = "Etc/GMT-14"

        prev_file = self.api.resolve_key_to_path(1)

        # Get the main row
        prev_mr1 = self.api.db.get_main_row(1)
        self.assertIsNotNone(prev_mr1)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )

        new_dt = prev_mr1.datetime.astimezone(tz=ZoneInfo(new_tz))

        tag = ["key", 5, "some_other_key", 4]
        self.api.change_datetime(key=1,
                                 tag=tag,
                                 dts=DateTimeSource.CUSTOM,
                                 new_dt=new_dt,
                                 add_exif_tag=False,
                                 rename=False)

        # check results
        new_path = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt), prev_mr1.db_name)

        # New path present, old path not
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(prev_file))

        # get row
        new_mr = self.api.db.get_main_row(1)
        new_mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(new_mr)
        self.assertIsNotNone(new_mdr)

        # Check timezone and datetime
        self.assertEqual(new_mr.datetime, new_dt)
        self.assertEqual(new_mr.timezone, new_dt.tzname())

        # check metadata row
        self.assertEqual(new_mdr.datetime_source, DateTimeSource.CUSTOM)
        self.assertEqual(new_mdr.naming_tag, "GooglePhotosMetadata:" + ":".join(map(str, tag)))

        # Check no new hash was added since the offset is equal
        self.assertEqual(len(self.api.db.get_all_hashes_of_file(1)), 1)

    def test_move_with_DoubleKey(self):
        """
        Test correct function when moving a file
        """
        new_tz = "Etc/GMT-14"

        prev_file = self.api.resolve_key_to_path(1)

        # Get the main row
        prev_mr1 = self.api.db.get_main_row(1)
        self.assertIsNotNone(prev_mr1)

        self.assertEqual(prev_mr1.datetime, datetime.datetime(
            year=1990, month=1, day=1, hour=12, minute=0, second=0, tzinfo=ZoneInfo("CET"))
                         )

        new_dt = prev_mr1.datetime.astimezone(tz=ZoneInfo(new_tz))

        tag = DoubleKey(first_key="EXIF:ModifyDate", second_key="EXIF:OffsetTime")
        self.api.change_datetime(key=1,
                                 tag=tag,
                                 dts=DateTimeSource.CUSTOM,
                                 new_dt=new_dt,
                                 add_exif_tag=False,
                                 rename=False)

        # check results
        new_path = os.path.join(self.api.root_path, self.api.db.dt_to_dir(new_dt), prev_mr1.db_name)

        # New path present, old path not
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(prev_file))

        # get row
        new_mr = self.api.db.get_main_row(1)
        new_mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(new_mr)
        self.assertIsNotNone(new_mdr)

        # Check timezone and datetime
        self.assertEqual(new_mr.datetime, new_dt)
        self.assertEqual(new_mr.timezone, new_dt.tzname())

        # check metadata row
        self.assertEqual(new_mdr.datetime_source, DateTimeSource.CUSTOM)
        self.assertEqual(new_mdr.naming_tag, tag.first_key + ", " + tag.second_key)

        # Check no new hash was added since the offset is equal
        self.assertEqual(len(self.api.db.get_all_hashes_of_file(1)), 1)


class TestChangeFileName(TestClassifyBase):
    """
    Tests for the change_filename
    """
    def test_raise_errors(self):
        """
        Check that the correct errors are raised.
        """
        # File doesn't exist
        self.assertRaises(ValueError, lambda : self.api.change_filename(key=1000, new_filename="unga_bunga.png"))

        # Filename exists
        fpath = self.api.resolve_key_to_path(100)
        self.assertIsNotNone(fpath)

        # Try to update to a name that's already taken
        self.assertRaises(ValueError, lambda : self.api.change_filename(key=1, new_filename=os.path.basename(fpath)))

        # Wrong flags
        self.api.move_to_trash(2)
        self.api.move_to_duplicates(child_key=4, parent_key=3)

        flags = self.api.db.get_main_flags(key=5)
        self.assertIsNotNone(flags)

        flags.present = False
        self.api.db.update_row_main_table(key=5, flags=flags)

        self.assertRaises(ValueError, lambda : self.api.change_filename(key=2, new_filename="unga_bunga.png"))
        self.assertRaises(ValueError, lambda : self.api.change_filename(key=4, new_filename="unga_bunga.png"))
        self.assertRaises(ValueError, lambda : self.api.change_filename(key=5, new_filename="unga_bunga.png"))

    def test_early_exit(self):
        """
        Check that nothing is done if the filename matches
        """
        fpath = self.api.resolve_key_to_path(1)

        # attempt change
        self.api.change_filename(key=1, new_filename=os.path.basename(fpath))

        # Check the metadata row
        mdr = self.api.db.get_metadata_row(1)
        self.assertIsNotNone(mdr)

        # Naming tag shouldn't be custom
        self.assertNotEqual(mdr.naming_tag, "CUSTOM")

        self.assertEqual(mdr.naming_tag, "EXIF:ModifyDate, EXIF:OffsetTime")

    def test_actual_rename(self):
        """
        Test file is actually renamed
        """
        new_name = "ungabunga.png"
        prev_path = self.api.resolve_key_to_path(1)

        self.api.change_filename(1, new_name)

        # check file was renamed
        self.assertFalse(os.path.exists(prev_path))
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(prev_path), new_name)))

        # Check correctly resolved
        mr = self.api.db.get_main_row(1)
        mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(mr)
        self.assertIsNotNone(mdr)

        self.assertEqual(mr.db_name, new_name)
        self.assertEqual(mdr.naming_tag, "CUSTOM")

    def test_actual_rename_with_cache_eviction(self):
        """
        Test cache eviction is working
        """
        new_name = "ungabunga.png"
        prev_path = self.api.resolve_key_to_path(1)

        self.api.filename_to_key(os.path.basename(prev_path))

        self.api.change_filename(1, new_name)

        # check file was renamed
        self.assertFalse(os.path.exists(prev_path))
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(prev_path), new_name)))

        # Check correctly resolved
        mr = self.api.db.get_main_row(1)
        mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(mr)
        self.assertIsNotNone(mdr)

        self.assertEqual(mr.db_name, new_name)
        self.assertEqual(mdr.naming_tag, "CUSTOM")

        self.assertEqual(self.api.filename_to_key(new_name), 1)
        self.assertIsNone(self.api.filename_to_key(os.path.basename(prev_path)))


class TestMoveFile(TestClassifyBase):
    """
    Fully test the move_file function
    """
    def test_errors_raised(self):
        """
        Test that the correct errors are raised.
        """
        tgt_path = os.path.join(self.temp_db, "foo", "bar", "baz")
        self.assertRaises(ValueError, lambda : self.api.move_file(1000, tgt_path))

        # Wrong flags
        self.api.move_to_trash(2)
        self.api.move_to_duplicates(child_key=4, parent_key=3)

        flags = self.api.db.get_main_flags(key=5)
        self.assertIsNotNone(flags)

        flags.present = False
        self.api.db.update_row_main_table(key=5, flags=flags)

        self.assertRaises(ValueError, lambda : self.api.move_file(2, tgt_path))
        self.assertRaises(ValueError, lambda : self.api.move_file(4, tgt_path))
        self.assertRaises(ValueError, lambda : self.api.move_file(5, tgt_path))

        os.remove(self.api.resolve_key_to_path(6))

        # Removed source file
        self.assertRaises(FileNotFoundError, lambda : self.api.move_file(6, tgt_path))

        # Check file exists at target
        file = self.api.resolve_key_to_path(10)

        # Create directory
        os.makedirs(tgt_path)

        # copy file to destination
        shutil.copy2(file, os.path.join(tgt_path, os.path.basename(file)))

        self.assertRaises(FileExistsError, lambda: self.api.move_file(10, tgt_path))


        old_path = self.api.resolve_key_to_path(20)

        # Move file to other dir and them moving it bac
        self.api.move_file(20, tgt_path)

        new_path = self.api.resolve_key_to_path(20)

        shutil.copy2(new_path, old_path)

        self.assertRaises(FileExistsError, lambda : self.api.move_file(20, os.path.dirname(old_path)))

    def test_abort_same_dt_path(self):
        """
        Test the system aborts if the file paths are identical
        """
        cur_dir_path = self.api.resolve_key_to_path(1)

        dst = os.path.dirname(cur_dir_path)

        # Tra to move
        self.api.move_file(1, dst)

        # Ensure we stay there
        self.assertTrue(os.path.exists(cur_dir_path))

    def test_abort_same_custom_path_and_move_to_custom_dir(self):
        """
        Test the system aborts if the file paths are identical
        """
        new_path = os.path.join(self.temp_db, "foo", "bar", "baz")

        self.api.move_file(1, new_path)

        # Test move was successful
        mr = self.api.db.get_main_row(1)
        mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(mr)
        self.assertIsNotNone(mdr)

        self.assertIsNotNone(mdr.db_local_dir)

        self.assertTrue(mr.flags.present)
        self.assertTrue(os.path.exists(os.path.join(new_path, mr.db_name)))

        self.api.move_file(1, new_path)

        self.assertTrue(os.path.exists(os.path.join(new_path, mr.db_name)))

    def test_correct_move_back(self):
        """
        Move a file to a custom dir and then back to check that the move back works correctly.
        """
        new_path = os.path.join(self.temp_db, "foo", "bar", "baz")
        org_path = self.api.resolve_key_to_path(1)

        # Move to custom path and check the result
        self.api.move_file(1, new_path)

        # Test move was successful
        mr = self.api.db.get_main_row(1)
        mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(mr)
        self.assertIsNotNone(mdr)

        self.assertIsNotNone(mdr.db_local_dir)

        self.assertTrue(mr.flags.present)
        self.assertTrue(os.path.exists(os.path.join(new_path, mr.db_name)))

        # Move back to dt path and check result
        self.api.move_file(1, os.path.dirname(org_path))

        # Test move was successful
        mr = self.api.db.get_main_row(1)
        mdr = self.api.db.get_metadata_row(1)

        self.assertIsNotNone(mr)
        self.assertIsNotNone(mdr)

        self.assertIsNone(mdr.db_local_dir)

        self.assertTrue(mr.flags.present)
        self.assertTrue(os.path.exists(org_path))

