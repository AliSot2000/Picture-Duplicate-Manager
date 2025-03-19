import os.path
import shutil

from base_class import TestClassifyBase
from photo_lib.utils import rec_list_all

"""
File contains all tests for the prune functions of the database:

This file fully tests the following functions:
- api.prune_filesystem_directories
- api._internal_prune_fs_dir
- api.prune_db_dir
- api.db.prune_gps
- api.db.prune_hash
- api.prune_all

"""

class TestDeleteDBDir(TestClassifyBase):
    """
    Fully test the api.prune_db_dir function.
    """
    def test_noop(self):
        """
        Test that nothing is done if no directories are added.
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 0)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_base_missing(self):
        """
        Test pruning is still correctly performed even if the specified directory is already removed
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        shutil.rmtree(tgt_dir)
        self.assertFalse(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 1)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)


    def test_shared_base_1(self):
        """
        Test that if the custom dir has a shared base with a given other directory, the shared path isn't removed
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 1)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_shared_base_2(self):
        """
        Test that if the custom dir has a shared base with a given other directory, the shared path isn't removed
        (this time two deep)
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 1)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_multi_shared(self):
        """
        Test multiple dirs are removed correctly.
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 2)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_extra_1(self):
        """
        Test extra directory, with only depth of 1. Should be fully removed
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 1)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_extra_dir_2(self):
        """
        Test extra directory, with only depth of 2. Should be fully removed
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 1)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_multiple_extra(self):
        """
        Test multiple directories are correctly removed with no shared path.
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        tgt_dir = os.path.join(self.api.root_path, "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()

        self.assertEqual(res, 1)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)


