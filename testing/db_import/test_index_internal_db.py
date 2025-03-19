import logging
import os.path
import shutil
from typing import List, Dict, Any

from photo_lib.metadata_aggregator import DateTimeSource
from photo_lib.utils import rec_list_all
from .import_base_casses import PrepareDirForImportBaseClass
from base_class import TestClassifyBase
from photo_lib.custom_enum import Allowed, ImportStatus
import json

"""
Contains tests for
- api.search_db_for_new_files
- api.import_internal_new_files
- api.remove_untracked_files

The file covers 100% of the function without specific tests:
- api._handle_file_internal_import
"""


wip = False


class TestSearchDBForNewFiles(TestClassifyBase):
    """
    Tests search_Db_for_new_files
    """
    def test_no_new_files(self):
        """
        Test what happens if we perform an import without any new files present
        """
        with open(os.path.join(self.api.db.get_temp_dir(), "testfile.txt"), "w") as f:
            f.write("File needed for walk to enter temp dir")

        # Prior to running it, we have one import table
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 1)
        self.assertEqual(self.api.db.get_import_tables_size(), 1)

        # Perform the search
        with self.assertLogs(self.api.main_logger, logging.INFO):
            res = self.api.search_db_for_new_files()
            self.assertIsNone(res)

        # Make sure we still only have two tables
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 1)
        self.assertEqual(self.api.db.get_import_tables_size(), 1)

    def test_logging_message_on_moved_file(self):
        """
        Move a file within the db and check it outputs a warning.
        """
        dir_1 = os.path.join(self.api.root_path, "1990", "04", "01")
        dir_2 = os.path.join(self.api.root_path, "1990", "03", "01")
        file = os.listdir(dir_1)[0]

        # Move a file
        os.rename(os.path.join(dir_1, file), os.path.join(dir_2, file))

        # Prior to running it, we have one import table
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 1)
        self.assertEqual(self.api.db.get_import_tables_size(), 1)

        # Perform the search
        with self.assertLogs(self.api.main_logger, logging.WARNING):
            res = self.api.search_db_for_new_files()
            self.assertIsNone(res)

        # Make sure we still only have two tables
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 1)
        self.assertEqual(self.api.db.get_import_tables_size(), 1)

    def test_allowed_ext_override(self):
        """
        Check that if we have empty allowed ext, we get zero allowed files
        """
        # preparation, move a directory over
        base_dir = os.path.join(self.media_source, "import_base_dir")

        target_dir = os.path.join(self.api.root_path, "1990", "12", "unga")

        shutil.copytree(base_dir, target_dir)

        # Prior to running it, we have one import table
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 1)
        self.assertEqual(self.api.db.get_import_tables_size(), 1)

        res = self.api.search_db_for_new_files(allowed_ext=set())
        self.assertEqual(res[1], 4)
        self.assertIsInstance(res[0], str)

        # Make sure we still only have two tables
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 2)
        self.assertEqual(self.api.db.get_import_tables_size(), 2)

        count = 0
        for key, allowed, ofn in self.api.db.update_allowed_iterator(tbl_name=res[0]):
            count += 1
            self.assertEqual(Allowed(allowed), Allowed.NOT_ALLOWED_EXT)

        self.assertEqual(self.api.db.get_update_allowed_iterator_size(res[0]), count)

    def test_all_allowed_files(self):
        """
        Test search db with all files allowed.
        """
        # preparation, move a directory over
        base_dir = os.path.join(self.media_source, "import_base_dir")

        target_dir = os.path.join(self.api.root_path, "1990", "12", "unga")

        shutil.copytree(base_dir, target_dir)

        # Prior to running it, we have one import table
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 1)
        self.assertEqual(self.api.db.get_import_tables_size(), 1)

        res = self.api.search_db_for_new_files(allowed_ext={".tiff", ".jpg", ".jpeg", ".png"})
        self.assertEqual(res[1], 4)
        self.assertIsInstance(res[0], str)

        # Make sure we still only have two tables
        import_tbl_list = self.api.db.list_import_tables()
        self.assertEqual(len(import_tbl_list), 2)
        self.assertEqual(self.api.db.get_import_tables_size(),2)

        count = 0
        for key, allowed, ofn in self.api.db.update_allowed_iterator(tbl_name=res[0]):
            count += 1
            self.assertEqual(Allowed(allowed), Allowed.ALLOWED)

        self.assertEqual(count, self.api.db.get_update_allowed_iterator_size(res[0]))


class BaseInternalImportTable(PrepareDirForImportBaseClass):
    """
    Class contains some utility functions we need to test the Internal Import Functions
    """
    def setup_hash_dir(self, end_dir: str):
        """
        Copy a hash dir into the database for testing
        """
        base_dir = os.path.join(self.media_source, "hash_change_1")

        target_dir = os.path.join(self.api.root_path, "1990", "12", end_dir)

        if os.path.exists(target_dir):  # pragma: no cover
            shutil.rmtree(target_dir)

        shutil.copytree(base_dir, target_dir)

        self.assertEqual(len(os.listdir(target_dir)), 3)

    def setup_aux_dir(self, end_dir: str):
        """
        Copy the import_aux_dir into the database for testing
        """
        base_dir = os.path.join(self.media_source, "db", "import_aux_test")

        target_dir = os.path.join(self.api.root_path, "1990", "12", end_dir)

        if os.path.exists(target_dir):  # pragma: no cover
            shutil.rmtree(target_dir)

        shutil.copytree(base_dir, target_dir)

        self.assertEqual(len(os.listdir(target_dir)), 5)

    def mark_all_as_ready(self, tbl: str):
        """
        Mark all files in table as ready for import
        """
        self.api.db.debug_execute(f"UPDATE `{tbl}` SET allowed = 1, imported = 1")

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


class TestImportInternalNewFiles(BaseInternalImportTable):
    """
    Fully test the import_internal_new_files function
    """

    def test_errors_raised(self):
        """
        Test that the correct errors are raised
        """
        # Table doesn't exist
        self.assertRaises(ValueError, self.api.import_internal_new_files, tbl="ungabunga")

        self.api.db.add_import_table(root_path="/foo/bar/baz", name="some_name")

        self.assertRaises(ValueError, self.api.import_internal_new_files, tbl="some_name")

    def test_internal_adding_exif_metadata(self):
        """
        Check that the file '10_no_metadata'
        - has the verify flag set
        - has two hashes
        - has the metadata set correctly
        """
        self.setup_aux_dir("unga")

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)
        tbl, count = res

        self.assertEqual(count, 5)

        # Test current location
        test_file = "10_no_metadata.jpg"
        test_fp = os.path.join(self.api.root_path, "1990", "12", "unga", test_file)
        pr = self.api.mda.eth.get_metadata(files=test_fp)

        # Check the properties of the file prior to importing
        self.assertEqual(1, len(pr))
        self.assertNotIn("EXIF:ModifyDate", pr[0].keys())
        self.assertNotIn("EXIF:OffsetTime", pr[0].keys())

        # check the import source and the allowed state of the file given the file name in the new import table
        self.api.db.debug_execute(f"SELECT datetime_source, allowed, key FROM `{tbl}` "
                                  f"WHERE original_filename = ?",
                                  (test_file,))
        row = self.api.db.sq_cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], DateTimeSource.FILE_AWARE.value)
        self.assertEqual(row[1], Allowed.ALLOWED.value)

        # Update the import table and set the imported status to be ready for the import
        self.api.db.debug_execute(f"UPDATE `{tbl}` SET imported = 1 WHERE original_filename = ? ",
                                  (test_file,))

        self.api.import_internal_new_files(tbl=tbl, add_safety_exif_tags=True, rename=True, move=True)

        # --------------------------------------------------------------------------------------------------------------
        # Check it is imported correctly
        # --------------------------------------------------------------------------------------------------------------

        # Check file exists
        import_path = os.path.join(self.api.root_path, "1990/11/01/1990-11-01T12-00-00_0001.jpg")
        self.assertTrue(os.path.exists(import_path))

        # Get the key in the main table and check flags have verify set.
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

    def test_internal_add_gps(self):
        """
        Check that the gps row is added correctly
        """
        self.setup_aux_dir("unga")

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl, count = res
        self.assertEqual(count, 5)

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
                test_fp = os.path.join(self.api.root_path, "1990", "12", "unga", test_file)
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
                                          f"FROM `{tbl}` WHERE original_filename = ?",
                                          (test_file,))

                row = self.api.db.sq_cur.fetchone()
                self.assertIsNotNone(row)

                # Check this is we only have the file data
                self.assertEqual(row[0], DateTimeSource.UNAWARE_GPS.value)
                self.assertEqual(row[1], Allowed.ALLOWED.value)

                # Check the GPS is the correct value
                self.assertLess((row[3] - args["gps_lat"]), 10e-10)  # GPS Lat
                self.assertLess((row[4] - args["gps_long"]), 10e-10)  # GPS Long

                actual_gps_lat = row[3]
                actual_gps_long = row[4]

                # Update the import table and set the imported status to be ready for the import
                self.api.db.debug_execute(f"UPDATE `{tbl}` SET imported = 1 WHERE original_filename = ? ",
                                          (test_file,))

                self.api.import_internal_new_files(tbl=tbl, add_safety_exif_tags=False, rename=True, move=True)

                # --------------------------------------------------------------------------------------------------------------
                # Check it is imported correctly
                # --------------------------------------------------------------------------------------------------------------

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

                # Check the rows aren't none
                self.assertIsNotNone(row.gps_lat)
                self.assertIsNotNone(row.gps_long)

                # And check the gps values
                self.assertLess((row.gps_lat - args["gps_lat"]), 10e-10)  # GPS Lat
                self.assertLess((row.gps_long - args["gps_long"]), 10e-10)  # GPS Long

    def test_import_hash_dir_rename_move(self):
        """
        Importing hash dir shouldn't cause any issues. It should simply add the three files into the db.
        """
        self.setup_hash_dir("unga")

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl, count = res
        self.assertEqual(count, 3)

        self.mark_all_as_ready(tbl)

        it_size = self.api.db.get_perform_import_iterator_size(tbl)
        allowed, conflict = self.api.import_internal_new_files(tbl=tbl, rename=True, move=True)
        self.assertEqual(it_size, allowed + conflict)

        self.check_table_dump_common()
        self.check_metadata_table_dump_move()
        self.check_main_table_dump_rename()
        self.check_dir_table_dump_empty()

    def test_import_hash_dir_no_rename_move(self):
        """
        Importing hash dir shouldn't cause any issues. It should simply add the three files into the db.
        """
        self.setup_hash_dir("unga")

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl, count = res
        self.assertEqual(count, 3)

        self.mark_all_as_ready(tbl)

        it_size = self.api.db.get_perform_import_iterator_size(tbl)
        allowed, conflict = self.api.import_internal_new_files(tbl=tbl, rename=False, move=True)
        self.assertEqual(it_size, allowed + conflict)

        self.check_table_dump_common()
        self.check_metadata_table_dump_move()
        self.check_main_table_dump_no_rename()
        self.check_dir_table_dump_empty()

    def test_import_hash_dir_rename_no_move(self):
        """
        Importing hash dir shouldn't cause any issues. It should simply add the three files into the db.
        """
        self.setup_hash_dir("unga")

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl, count = res
        self.assertEqual(count, 3)

        self.mark_all_as_ready(tbl)

        it_size = self.api.db.get_perform_import_iterator_size(tbl)
        allowed, conflict = self.api.import_internal_new_files(tbl=tbl, rename=True, move=False)
        self.assertEqual(it_size, allowed + conflict)


        self.check_table_dump_common()
        self.check_metadata_table_dump_no_move()
        self.check_main_table_dump_rename()
        self.check_non_empty_dir_table_dump()

    def test_import_hash_dir_no_rename_no_move(self):
        """
        Importing hash dir shouldn't cause any issues. It should simply add the three files into the db.
        """
        self.setup_hash_dir("unga")

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl, count = res
        self.assertEqual(count, 3)

        self.mark_all_as_ready(tbl)

        it_size = self.api.db.get_perform_import_iterator_size(tbl)
        allowed, conflict = self.api.import_internal_new_files(tbl=tbl, rename=False, move=False)
        self.assertEqual(it_size, allowed + conflict)

        self.check_table_dump_common()
        self.check_metadata_table_dump_no_move()
        self.check_main_table_dump_no_rename()
        self.check_non_empty_dir_table_dump()

    def test_import_hash_dir_name_conflict(self):
        """
        Perform an import which will cause a conflict during the name resolution
        """
        # Set up the directory for import
        self.setup_hash_dir("unga")
        self.setup_hash_dir("bunga")

        # Index it and make assertions about indexing
        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl1, count1 = res
        self.assertEqual(count1, 6)

        self.mark_all_as_ready(tbl1)

        # Perform the import
        it_size = self.api.db.get_perform_import_iterator_size(tbl1)
        imported, conflict = self.api.import_internal_new_files(tbl=tbl1, rename=False, move=True)
        self.assertEqual(imported, 3)
        self.assertEqual(conflict, 3)
        self.assertEqual(it_size, imported + conflict)

        # Check the messages in the import table
        for row in self.api.db.import_status_test(tbl1):
            key, allowed, import_status, message, original_filename = row

            if key <= 3:
                with self.subTest(f"Testing Import Table {tbl1} and Key: {key}"):
                    self.assertEqual(allowed, Allowed.ALLOWED)
                    self.assertEqual(import_status, ImportStatus.IMPORTED)
                    self.assertIsNone(message)
            else:
                with self.subTest(f"Testing Import Table {tbl1} and Key: {key}"):
                    self.assertEqual(allowed, Allowed.NOT_ALLOWED_ERR)
                    self.assertEqual(import_status, ImportStatus.IGNORE)
                    self.assertEqual(message, f"Filename {original_filename} already exists")

        self.check_table_dump_common()
        self.check_metadata_table_dump_move()
        self.check_main_table_dump_no_rename()
        self.check_dir_table_dump_empty()

    def test_import_with_file_at_dest(self):
        """
        Perform import with the files at the target destination already present.
        """
        # Set up directory for import
        self.setup_hash_dir("unga")

        # Perform index and assert reults
        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)

        tbl1, count1 = res
        self.assertEqual(count1, 3)

        self.mark_all_as_ready(tbl1)

        # Directories
        source_dir = os.path.join(self.media_source, "hash_change_1")
        tgt_dir = os.path.join(self.api.root_path, "1990", "09", "01")
        os.makedirs(tgt_dir, exist_ok=True)

        # source files
        sf1 = os.path.join(source_dir, "01_match_a_c1.png")
        sf2 = os.path.join(source_dir, "02_match_a_c1.png")
        sf3 = os.path.join(source_dir, "03_match_a_c1.png")

        df1 = os.path.join(tgt_dir, "01_match_a_c1.png")
        df2 = os.path.join(tgt_dir, "02_match_a_c1.png")
        df3 = os.path.join(tgt_dir, "03_match_a_c1.png")

        # copy files to target destination
        shutil.copy2(sf1, df1)
        shutil.copy2(sf2, df2)
        shutil.copy2(sf3, df3)

        # Perform import this time with errors
        it_size = self.api.db.get_perform_import_iterator_size(tbl1)
        imported, conflict = self.api.import_internal_new_files(tbl=tbl1, rename=False, move=True)
        self.assertEqual(imported, 0)
        self.assertEqual(conflict, 3)
        self.assertEqual(it_size, imported + conflict)

        for row in self.api.db.import_status_test(tbl1):
            key, allowed, import_status, message, original_filename = row

            with self.subTest(f"Testing Import Table {tbl1} and Key: {key}"):
                self.assertEqual(allowed, Allowed.NOT_ALLOWED_ERR)
                self.assertEqual(import_status, ImportStatus.IGNORE)
                self.assertEqual(message, "File Exists at Destination. Import Aborted")

    def check_table_dump_common(self):
        """
        Test table dumps that are equivalent across the variations.
        """
        self.check_gps_table_dump()
        self.check_hash_table_dump()
        self.check_hash_assoz_table_dump()

    def check_hash_table_dump(self):
        """
        Test that the dumped hash table matches our expectation
        """
        hash_tbl = self.api.db.dump_hashes_table()
        expected_hash_tbl = [
            {
                "key": 1,
                "hash": "b007bcf5870829075a975a87ce0a7e6dff399959a9d412bb8d5d30355e68e065"
            },
            {
                "key": 2,
                "hash": "74ca94dce04467231bfcd8dee4cd0105dbdba23003ab93e55171a5cda7b4637f"
            },
            {
                "key": 3,
                "hash": "c12310f9e92bd9a481baae87e2ffa5e1c75865c3e7537407f1ebd7e4d0df1cae"
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(hash_tbl, indent=4))

        self.assertEqual(len(hash_tbl), len(expected_hash_tbl))

        for row in hash_tbl:
            self.assertIn(row, expected_hash_tbl)

    def check_hash_assoz_table_dump(self):
        """
        Test that the dumped hash assoz table matches our expectation
        """
        assoz_tbl = self.api.db.dump_hash_assoz_table()

        expected_hash_assoz_tbl = [
            {
                "hash_key": 1,
                "file_key": 1,
                "file_size_bytes": 31192,
                "hash_date": "2025-03-18T23:46:49.285694+00:00",
                "initial": 1
            },
            {
                "hash_key": 2,
                "file_key": 2,
                "file_size_bytes": 31394,
                "hash_date": "2025-03-18T23:46:49.289327+00:00",
                "initial": 1
            },
            {
                "hash_key": 3,
                "file_key": 3,
                "file_size_bytes": 31404,
                "hash_date": "2025-03-18T23:46:49.290362+00:00",
                "initial": 1
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(assoz_tbl, indent=4))

        self.assertEqual(len(expected_hash_assoz_tbl), len(assoz_tbl))

        san_expect = self.drop_unpredictable_col(expected_hash_assoz_tbl, col_name=["hash_date"])
        for row in self.drop_unpredictable_col(assoz_tbl, col_name=["hash_date"]):
            self.assertIn(row, san_expect)

    def check_gps_table_dump(self):
        """
        Check that our GPS table is empty.
        """
        gps_tbl = self.api.db.dump_gps_location_table()
        expected_gps_tbl = []
        self.assertListEqual(gps_tbl, expected_gps_tbl)

    def check_dir_table_dump_empty(self):
        """
        Check that the db_dir table is empty
        """
        dir_table = self.api.db.dump_db_dir_table()
        expected_dir_table = []
        self.assertEqual(dir_table, expected_dir_table)

    def check_non_empty_dir_table_dump(self):
        """
        Check dir table contains the correct entry
        """
        dir_table = self.api.db.dump_db_dir_table()
        expected_dir_table = [
            {
                "key": 1,
                "db_local_dir": "[\"1990\", \"12\", \"unga\"]"
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(dir_table, indent=4))

        self.assertEqual(len(dir_table), len(expected_dir_table))
        for row in dir_table:
            self.assertIn(row, expected_dir_table)

    def check_main_table_dump_rename(self):
        """
        Check the main table dump given files that were renamed
        """
        main_tbl = self.api.db.dump_main_table()

        expected_main_tbl = [
            {
                "key": 1,
                "original_filename": "01_match_a_c1.png",
                "metadata": None,
                "google_metadata": None,
                "datetime": "1990-09-01T12:00:01+02:00",
                "db_name": "1990-09-01T12-00-01_0001.png",
                "parent": None,
                "timezone": "UTC+02:00",
                "flags": 9
            },
            {
                "key": 2,
                "original_filename": "02_match_a_c1.png",
                "metadata": None,
                "google_metadata": None,
                "datetime": "1990-09-01T13:01:01+02:00",
                "db_name": "1990-09-01T13-01-01_0002.png",
                "parent": None,
                "timezone": "UTC+02:00",
                "flags": 9
            },
            {
                "key": 3,
                "original_filename": "03_match_a_c1.png",
                "metadata": None,
                "google_metadata": None,
                "datetime": "1990-09-01T14:01:01+02:00",
                "db_name": "1990-09-01T14-01-01_0003.png",
                "parent": None,
                "timezone": "UTC+02:00",
                "flags": 9
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(main_tbl, indent=4))

        self.assertEqual(len(expected_main_tbl), len(main_tbl))

        san_expect_main_tbl = self.drop_unpredictable_col(expected_main_tbl, ["metadata", "google_metadata"])
        san_given_rows = self.drop_unpredictable_col(main_tbl, ["metadata", "google_metadata"])
        for row in san_given_rows:
            self.assertIn(row, san_expect_main_tbl)

    def check_main_table_dump_no_rename(self):
        """
        Check the main table dump given files that were not renamed
        """
        main_tbl = self.api.db.dump_main_table()

        expected_main_tbl = [
            {
                "key": 1,
                "original_filename": "01_match_a_c1.png",
                "metadata": None,
                "google_metadata": None,
                "datetime": "1990-09-01T12:00:01+02:00",
                "db_name": "01_match_a_c1.png",
                "parent": None,
                "timezone": "UTC+02:00",
                "flags": 9
            },
            {
                "key": 2,
                "original_filename": "02_match_a_c1.png",
                "metadata": None,
                "google_metadata": None,
                "datetime": "1990-09-01T13:01:01+02:00",
                "db_name": "02_match_a_c1.png",
                "parent": None,
                "timezone": "UTC+02:00",
                "flags": 9
            },
            {
                "key": 3,
                "original_filename": "03_match_a_c1.png",
                "metadata": None,
                "google_metadata": None,
                "datetime": "1990-09-01T14:01:01+02:00",
                "db_name": "03_match_a_c1.png",
                "parent": None,
                "timezone": "UTC+02:00",
                "flags": 9
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(main_tbl, indent=4))

        self.assertEqual(len(expected_main_tbl), len(main_tbl))

        san_expect_main_tbl = self.drop_unpredictable_col(expected_main_tbl, ["metadata", "google_metadata"])
        for row in self.drop_unpredictable_col(main_tbl, ["metadata", "google_metadata"]):
            self.assertIn(row, san_expect_main_tbl)

    def check_metadata_table_dump_move(self):
        """
        Check the table dump of the metadata table given that we moved the files.
        """
        metadata_tbl = self.api.db.dump_metadata_table()

        expected_metadata_tbl = [
            {
                "main_key": 1,
                "original_dirname": "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/testing/test_db/1990/12/unga",
                "naming_tag": "EXIF:ModifyDate, EXIF:OffsetTime",
                "gps_location": None,
                "db_dir": None,
                "datetime_source": 0,
                "replaced": 0
            },
            {
                "main_key": 2,
                "original_dirname": "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/testing/test_db/1990/12/unga",
                "naming_tag": "EXIF:ModifyDate, EXIF:OffsetTime",
                "gps_location": None,
                "db_dir": None,
                "datetime_source": 0,
                "replaced": 0
            },
            {
                "main_key": 3,
                "original_dirname": "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/testing/test_db/1990/12/unga",
                "naming_tag": "EXIF:ModifyDate, EXIF:OffsetTime",
                "gps_location": None,
                "db_dir": None,
                "datetime_source": 0,
                "replaced": 0
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(metadata_tbl, indent=4))

        self.assertEqual(len(metadata_tbl), len(expected_metadata_tbl))

        san_expect_metadata_tbl = self.drop_unpredictable_col(expected_metadata_tbl, ["original_dirname"])
        for row in self.drop_unpredictable_col(metadata_tbl, ["original_dirname"]):
            self.assertIn(row, san_expect_metadata_tbl)

    def check_metadata_table_dump_no_move(self):
        """
        Check the table dump of the metadata table given that we didn't move the files.
        """
        metadata_tbl = self.api.db.dump_metadata_table()

        expected_metadata_tbl = [
            {
                "main_key": 1,
                "original_dirname": "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/testing/test_db/1990/12/unga",
                "naming_tag": "EXIF:ModifyDate, EXIF:OffsetTime",
                "gps_location": None,
                "db_dir": 1,
                "datetime_source": 0,
                "replaced": 0
            },
            {
                "main_key": 2,
                "original_dirname": "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/testing/test_db/1990/12/unga",
                "naming_tag": "EXIF:ModifyDate, EXIF:OffsetTime",
                "gps_location": None,
                "db_dir": 1,
                "datetime_source": 0,
                "replaced": 0
            },
            {
                "main_key": 3,
                "original_dirname": "/home/alisot2000/Documents/01_ReposNCode/Picture-Duplicate-Manager/testing/test_db/1990/12/unga",
                "naming_tag": "EXIF:ModifyDate, EXIF:OffsetTime",
                "gps_location": None,
                "db_dir": 1,
                "datetime_source": 0,
                "replaced": 0
            }
        ]

        if wip:  # pragma: no cover
            print(json.dumps(metadata_tbl, indent=4))

        self.assertEqual(len(metadata_tbl), len(expected_metadata_tbl))

        san_expect_metadata_tbl = self.drop_unpredictable_col(expected_metadata_tbl, ["original_dirname"])
        for row in self.drop_unpredictable_col(metadata_tbl, ["original_dirname"]):
            self.assertIn(row, san_expect_metadata_tbl)


class TestRemoveUntrackedFiles(BaseInternalImportTable):
    """
    Fully test the api.remove_untracked_files function.
    """
    def check_empty_scratch(self):
        """
        Test that the scratch dir is empty
        """
        dir_content = os.listdir(os.path.abspath(self.import_source))
        self.assertListEqual(dir_content, [])

    def check_empty_database(self):
        """
        Check the database is empty
        """
        current_db = sorted(map(lambda x: x.removeprefix(self.api.root_path).removeprefix(os.sep),
                                rec_list_all(self.api.root_path)))

        expected_db = [
            ".config.json",
            ".photos.db"
        ]

        if wip:  # pragma: no cover
            print(json.dumps(current_db, indent=4))

        self.assertListEqual(expected_db, current_db)

    def check_non_empty_scratch_dir(self):
        """
        Check that the files were successfully moved to the scratch dir
        """
        current_trash = sorted(map(lambda x: x.removeprefix(self.import_source).removeprefix(os.sep),
                                   rec_list_all(self.import_source)))

        expected_trash = [
            "1990/12/bunga/1_10_no_metadata.jpg",
            "1990/12/bunga/2_20_gps_metadata.jpg",
            "1990/12/bunga/3_21_gps_metadata.jpg",
            "1990/12/bunga/4_22_gps_metadata.jpg",
            "1990/12/bunga/5_23_gps_metadata.jpg",
            "1990/12/unga/6_01_match_a_c1.png",
            "1990/12/unga/7_02_match_a_c1.png",
            "1990/12/unga/8_03_match_a_c1.png"
        ]

        if wip:  # pragma: no cover
            print(json.dumps(current_trash, indent=4))

        self.assertListEqual(current_trash, expected_trash)

    def test_errors_raised(self):
        """
        Test that the correct errors are raised
        """
        # Table doesn't exist
        self.assertRaises(ValueError, self.api.remove_untracked_files, tbl="ungabunga")

        # Test wrong table flag
        self.api.db.add_import_table(root_path="/foo/bar/baz", name="some_name")
        self.assertRaises(ValueError, self.api.remove_untracked_files, tbl="some_name")

        # Should raise type error, if destination isn't provided but we don't want to delete.
        self.assertRaises(TypeError, self.api.remove_untracked_files, delete=False, target_dir=None, tbl="some_name")

    def test_delete(self):
        """
        Test deletion is working correctly
        """
        self.setup_hash_dir("unga")
        self.setup_aux_dir("bunga")

        os.makedirs(self.import_source, exist_ok=True)

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)
        tbl, count = res

        self.assertEqual(count, 8)

        count = self.api.remove_untracked_files(tbl=tbl, delete=True, target_dir=None)
        self.assertEqual(count, 8)

        # Check the directories
        self.check_empty_database()
        self.check_empty_scratch()

    def test_move(self):
        """
        Check that all untracked files are correctly moved over to the scratch dir
        """
        self.setup_hash_dir("unga")
        self.setup_aux_dir("bunga")

        os.makedirs(self.import_source, exist_ok=True)

        res = self.api.search_db_for_new_files()
        self.assertIsNotNone(res)
        tbl, count = res

        self.assertEqual(count, 8)

        count = self.api.remove_untracked_files(tbl=tbl, delete=False, target_dir=self.import_source)
        self.assertEqual(count, 8)

        # Check the directories
        self.check_empty_database()
        self.check_non_empty_scratch_dir()
