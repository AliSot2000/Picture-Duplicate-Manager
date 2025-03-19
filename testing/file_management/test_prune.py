import json
import logging
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
- api._internal_prune_db_dir
- api.db.prune_gps
- api.db.prune_hash
- api.prune_all

The file covers 100% of the function without specific tests:
- api.db.get_db_dir_count
- api.db.get_hash_table_size
- api.db.get_gps_table_size
"""


wip = False


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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)
        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))

        self.assertEqual(self.api.db.get_db_dir_count(), 1)

        shutil.rmtree(tgt_dir)
        self.assertFalse(os.path.exists(tgt_dir))

        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        self.assertEqual(self.api.db.get_db_dir_count(), 1)

        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        self.assertEqual(self.api.db.get_db_dir_count(), 1)

        res = self.api.prune_db_dir()

        self.assertEqual(self.api.db.get_db_dir_count(), 0)
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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        tgt_dir = os.path.join(self.api.root_path, "1990", "05", "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        self.assertEqual(self.api.db.get_db_dir_count(), 2)

        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        self.assertEqual(self.api.db.get_db_dir_count(), 1)

        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        self.assertEqual(self.api.db.get_db_dir_count(), 1)

        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

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

        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        # Directory for testing
        tgt_dir = os.path.join(self.api.root_path, "dir_a")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        tgt_dir = os.path.join(self.api.root_path, "dir_a", "dir_b")
        self.api._insert_get_dir(tgt_dir)
        self.assertTrue(os.path.exists(tgt_dir))
        self.assertEqual(self.api.db.get_db_dir_count(), 2)

        res = self.api.prune_db_dir()
        self.assertEqual(self.api.db.get_db_dir_count(), 0)

        self.assertEqual(res, 2)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)


class TestPruneFileSystemDirectories(TestClassifyBase):
    """
    Fully test teh api.prune_filesystem_directories
    """
    def test_noop(self):
        """
        Test that nothing is done if no directories are added.
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        res = self.api.prune_filesystem_directories()

        self.assertEqual(res, 0)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_removal_of_one_extra_dir(self):
        """
        Test one leaf is added and is removed
        """
        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Create directory
        tgt_path = os.path.join(self.api.root_path, "1990", "01", "31")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))

        count = self.api.prune_filesystem_directories()
        self.assertEqual(1, count)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_removal_one_extra_dir_2(self):
        """
        Test that a path of extra dirs is removed
        """
        prev_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Create directory
        tgt_path = os.path.join(self.api.root_path, "1990", "01", "31", "some_event")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))

        count = self.api.prune_filesystem_directories()
        self.assertEqual(2, count)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_multiple_extra_dir(self):
        """
        Test that two leafs are correctly removed.
        """
        prev_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Create directory
        tgt_path = os.path.join(self.api.root_path, "1990", "01", "31", "some_event")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))
        tgt_path = os.path.join(self.api.root_path, "1990", "01", "29")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))

        count = self.api.prune_filesystem_directories()
        self.assertEqual(3, count)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_remove_dir_from_root_1(self):
        """
        Test that up till root is removed
        """
        prev_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Create directory
        tgt_path = os.path.join(self.api.root_path, "2025", "03", "01")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))

        count = self.api.prune_filesystem_directories()
        self.assertEqual(3, count)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_remove_dir_from_root_2(self):
        """
        Test that up till root is removed
        """
        prev_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Create directory
        tgt_path = os.path.join(self.api.root_path, "2025", "03", "01", "some_event")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))

        count = self.api.prune_filesystem_directories()
        self.assertEqual(4, count)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_remove_multiple_from_root(self):
        """
        Test that multiple directories are correctly removed
        """
        prev_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        # Create directory
        tgt_path = os.path.join(self.api.root_path, "2025", "03", "01")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))
        tgt_path = os.path.join(self.api.root_path, "2025", "03", "02", "some_event")
        os.makedirs(tgt_path, exist_ok=True)
        self.assertTrue(os.path.exists(tgt_path))

        count = self.api.prune_filesystem_directories()
        self.assertEqual(5, count)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_dir_from_db_dir_not_touched_1(self):
        """
        Check that a db_dir directory isn't touched.
        """
        self.api._insert_get_dir(os.path.join(self.api.root_path, "1990", "01", "12"))
        self.api._insert_get_dir(os.path.join(self.api.root_path, "1990", "01", "some_event"))

        prev_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        res = self.api.prune_filesystem_directories()

        self.assertEqual(res, 0)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x : not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)

    def test_dir_from_db_dir_not_touched_2(self):
        """
        Check that a db_dir directory isn't touched even if they are correctly a completely empty.
        """
        self.api._insert_get_dir(os.path.join(self.api.root_path, "2025", "01", "12"))

        prev_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                    sorted(rec_list_all(self.api.root_path))))

        res = self.api.prune_filesystem_directories()

        self.assertEqual(res, 0)

        self.api.db.commit()
        after_rec_list = list(filter(lambda x: not x.endswith(".photos.db-journal"),
                                     sorted(rec_list_all(self.api.root_path))))

        self.assertListEqual(prev_rec_list, after_rec_list)


class TestPruneHashes(TestClassifyBase):
    """
    Fully test the api.db.prune_hash function
    """
    def check_hash_table_equivalent(self):
        cur_hash_table = self.api.db.dump_hashes_table()

        expected_hash_table = [
            {
                "key": 1,
                "hash": "f99faa2783761e229fa56eb97d3271852a1cbdbff81dbc2366815714d6c9e4f4"
            },
            {
                "key": 2,
                "hash": "12adde7b6c3908bfd0f30fa694f1f8d73ea8a27edc06860e9bd8c40bb926acc8"
            },
            {
                "key": 3,
                "hash": "2efde3247b6e0e7a2ff6c5a4cb7108706cdbe9752f2c3115f6a07c4f0ba201f4"
            },
            {
                "key": 4,
                "hash": "982bd2594a5f33be0c8adbc3adbee49107fa80416944ee2f26ef6759b1d7e653"
            },
            {
                "key": 5,
                "hash": "da08e8b24416ae8999c548c576162416a3eef99ab71173ab7eccafc6413e144a"
            },
            {
                "key": 6,
                "hash": "100a27c5bf74fc81a29a51c0c985fba8514fca432d7f0713d27f054c1bd7ef95"
            },
            {
                "key": 7,
                "hash": "bd1b305fef7f1a7b4a3922dc692fad8de47e5360537a5cb2e0b87a8760a8063b"
            },
            {
                "key": 8,
                "hash": "e5ce67dc2f3e5ab824cee3c657c5eb17496e41bfacfd92adbb5c596047b86ee9"
            },
            {
                "key": 9,
                "hash": "d9f6eb368a8c1d1ddadd857a3c09c13a5c5672ca5570a2ae3b3321d538265a63"
            },
            {
                "key": 10,
                "hash": "62581ac6fde582dcd845ed7e3d4665a8dd7667a7f28968029442f49862ad520c"
            },
            {
                "key": 11,
                "hash": "b1db6df4556bcbc6ac45dec6d6a569d24629f600e1d91c2f80d29b766d1a23bd"
            },
            {
                "key": 12,
                "hash": "155c94216e25adee74beb3b1b734b572d4ba23d1a34895865a2094a440a0db67"
            },
            {
                "key": 13,
                "hash": "8790197445ce9f35e94cb8121e161a1803319a67829e38426982fad2754cb916"
            },
            {
                "key": 14,
                "hash": "47720b8cf0c53199bb2d8382b33d26b0dd32182471608a1cce968ac8ab81cfb3"
            },
            {
                "key": 15,
                "hash": "9be5927da65efad25b78818316f21867bed7ae7d5adc838a3dde34da0529f25b"
            },
            {
                "key": 16,
                "hash": "0558c32c95576f77db5fa88f6a5704706856782598846cd198e94789317c85fa"
            },
            {
                "key": 17,
                "hash": "cd556bf758e84fc2436099159263fd69f40247c9d01f2c89b514b91381f84c6a"
            },
            {
                "key": 18,
                "hash": "430f1f5919d55509a486eb9282aeb0b8fc4b840d74dca5aeed499305852a8784"
            },
            {
                "key": 19,
                "hash": "004a2637f7f177a2c8ebcb002361061f8faeab9d3ecc4ea6bfa8794e74db2266"
            },
            {
                "key": 20,
                "hash": "a3b5ea9d6b6391ad7d6b2b4494378f8df5cdf242d812701e7e0c7ac75fdee8a4"
            },
            {
                "key": 21,
                "hash": "d59e4ecd729c449346f8cc62c11a82225d2a3d1748c0b33fb22019e02aa69626"
            },
            {
                "key": 22,
                "hash": "d5c38449643bd2f9d3d49abc92092ef3648c820e64a96054b31db0350c838d3a"
            },
            {
                "key": 23,
                "hash": "13c02f764d92a04e70bf695a9acdc7b3244a8106f1b83e54dd5cd3aa17f97d4d"
            },
            {
                "key": 24,
                "hash": "4870ee173d559831d6d998c495522ae1ea3d50138b6eb849fac5dd517402425e"
            },
            {
                "key": 25,
                "hash": "7e24acfe7e6af6ee23d0b7f2ce49e82e2963d61e123de6d01c64a762fb71dda2"
            },
            {
                "key": 26,
                "hash": "05015cd5ddffc5de38202ddde0a937cc28c09f9eec832c2fe22dee0c70748660"
            },
            {
                "key": 27,
                "hash": "9289f722a590f392ffdf383fcca5c4eb0e8e7589255551ac9a96f14872f7966f"
            },
            {
                "key": 28,
                "hash": "f69f97d13606b31e6ca20055ada0bbc931ba6642e000f7f57331c6454526e19b"
            },
            {
                "key": 29,
                "hash": "5eb169774038c774cadef481cffa4d4151153a6d2562095bb340aaf9340de955"
            },
            {
                "key": 30,
                "hash": "ad2b9470cb81a76ac2824dc77d08b0523cab8584681482ba722e75ea83d3701f"
            },
            {
                "key": 31,
                "hash": "b4647b028f8c6007257d3c47cc046eb1b5b4d18859183a78aa0b61e5e1b27611"
            },
            {
                "key": 32,
                "hash": "5800f23cb090f07ab79e6660808d2132d2e5c79568b7dc8a00556e12b9be4cbd"
            },
            {
                "key": 33,
                "hash": "d2ea183dcf9ac41ff45dd80753b904f32434545b7ef4c0ebe455aeb3232e2ce7"
            },
            {
                "key": 34,
                "hash": "9d008c8d57b27f8113316b2c199cfffc104846448724063e3a9ca84b587e3e37"
            },
            {
                "key": 35,
                "hash": "088a28b17d9d6c71bde3fd135c94522e448095ec39e7c99dff927a6ff9b03aae"
            },
            {
                "key": 36,
                "hash": "1f17c72633d282b151382b95dfff0ba2e1cfa3fdb63caf6a8354081768400ed5"
            },
            {
                "key": 37,
                "hash": "ad316f24d1650f465fae2b301c49fbe22cf8eb195d6e56091c2b948acabb8041"
            },
            {
                "key": 38,
                "hash": "093743a01222b9312283d9c934e69f27a6af6b4ce3707f9311e1aaab64c19031"
            },
            {
                "key": 39,
                "hash": "546dd26da6455fa5b7e93a0d0debf43d3db8f9fbbb7c37b3e79fb76d88b2f443"
            },
            {
                "key": 40,
                "hash": "ab20c8bd9ab53184bf815ceacee292d11cbf352dd0c8b0b5e1d8c68cb8e09c39"
            },
            {
                "key": 41,
                "hash": "727aebb321a712c22057b23db4b6469f03f34ff095a724082d96671d291de213"
            },
            {
                "key": 42,
                "hash": "68e5a653809cf483d3f5988f171c9ba4e2ae98d6b82e3582b66dd03425826d01"
            },
            {
                "key": 43,
                "hash": "480f35140c63890e3d422e322fe8760edc1d2c117d3e0acf8bfe137aabd93f6a"
            },
            {
                "key": 44,
                "hash": "446e2c0ce77942a4aca029a64410ea2bb53992cfd19fe8fe9ec7b5c1635b2b17"
            },
            {
                "key": 45,
                "hash": "f2b324c8864963e7a586eb3062bbbcc62bd648fb5070a364ab2ca2ac637cc4dd"
            },
            {
                "key": 46,
                "hash": "ae35bcdbefc6df9aefdecb7357eb031d9d2bd28fb97ba7439bf19b72069c923e"
            },
            {
                "key": 47,
                "hash": "27206ac13bf739072669ad687755f9765bad9fec540f6a36c8d7a7ead5fe1eab"
            },
            {
                "key": 48,
                "hash": "3a52a6f96e4b8eee705193f0f96ddd0d5775f6413bca41e151d339c3393ece12"
            },
            {
                "key": 49,
                "hash": "8afd9f282134afa2d902a2cac2dae797cf4b03de874a93ce65f114e8bb18df0f"
            },
            {
                "key": 50,
                "hash": "ffb600f9959618e47294752c974b8f577dae50a4c4fbd7fb4d76c67298ede296"
            },
            {
                "key": 51,
                "hash": "a2bd347b776c383404284db7898bd51873927e93d5b233c85f138c7a3a7f1f4a"
            },
            {
                "key": 52,
                "hash": "0afb27a1ae3ab4a503b1643362f2ca1e8ec96e0092493cba2c2a357eef696095"
            },
            {
                "key": 53,
                "hash": "79b32f4a05d77e30f66091e2450a64b411843efbaa894d6823b634fd4a298b3d"
            },
            {
                "key": 54,
                "hash": "705c61c7de95706766bd42c2dec60288469cd30d7c2cc5e83dccb78977ce8b4f"
            },
            {
                "key": 55,
                "hash": "4456d404fb4d1dfe17624994d781ad3f13095fff63dbc34c359cc80ec3f1080d"
            },
            {
                "key": 56,
                "hash": "2678d4525e51337aa34114b27bd9d8510c99196d1028204680ae7fdf43d2f9c9"
            },
            {
                "key": 57,
                "hash": "7b22cd6617153158373246ea06a4e5437d840cec15937fc03da9d1e3a901b583"
            },
            {
                "key": 58,
                "hash": "e8bb1334eab28d98be3fa4d19d5fe31eb5cc4648937434c0394e6a7e9c0b7393"
            },
            {
                "key": 59,
                "hash": "8b2d5a876d1480f48210c34af97765afb1bc9916621af82660be9fb67cb7a358"
            },
            {
                "key": 60,
                "hash": "9fd8b458d1dfb66515eeeac7798b5fd19dd78923ead101be2dcfe39db1c67b6f"
            },
            {
                "key": 61,
                "hash": "0ce943b0d6b30d780b7719cab9976d8fb01636e3b86d1bc3c365ce9a83ff8058"
            },
            {
                "key": 62,
                "hash": "505e38457e99740a544737901d9232eae42d12964ca2f2cc8103f7b695ca3cef"
            },
            {
                "key": 63,
                "hash": "17195e31d90b3470e792eebff736e4607510d978126a2daff91f7f13002ee667"
            },
            {
                "key": 64,
                "hash": "e793d43e8eb7c62177a33c005faeb6568e86d6a5be4fa111740bba4691546a03"
            },
            {
                "key": 65,
                "hash": "35339e27d1e261e101b8ecf20af4a74ef2095a1349c6fcc44bd2c8eff478acb9"
            },
            {
                "key": 66,
                "hash": "1e864c544fbb6fab9b2fd110169945600063bbcc15ecf64cccf0f2e9aac0f2ed"
            },
            {
                "key": 67,
                "hash": "6edb114ca2122654242981d24443c0ae7a782c1eb889b49a540f8873041a5356"
            },
            {
                "key": 68,
                "hash": "50d88e34831e49a2c19fdf526609753625425a948cf32d4c2d5ecd471b1d9902"
            },
            {
                "key": 69,
                "hash": "cbbaff856f5aa11676d49ff7c33dd9936ac62247278e4bdea3fda202ba0eb401"
            },
            {
                "key": 70,
                "hash": "2c8b3f212bb598d327e9c5e7205bceba58b066dca88d6efcfa964066c7f9a3b9"
            },
            {
                "key": 71,
                "hash": "c253706f2f012aad60a42510dba9b98917be336f6ebdd58d72e0091f1c1ac264"
            },
            {
                "key": 72,
                "hash": "1f0cec3f1ce9206172a7f69cd32a03e9b3362fc3132e0895410880ddd61a51d6"
            },
            {
                "key": 73,
                "hash": "4fa5571f3326fe38ea4404f1ee27d617c7bd3edbb021e652bd78d9be198bb95b"
            },
            {
                "key": 74,
                "hash": "2f4180abb476401612c21174eda961e6fc6a37450aa3c9d3a1be9a3faa671c79"
            },
            {
                "key": 75,
                "hash": "50466d82b28bbe5546924b7e6bdf3db10c151aa0d6926ca764d9e5ec06b0d099"
            },
            {
                "key": 76,
                "hash": "7c3d6b4c2408dc3e6c0d8a77ed3533e1987bf1566921d5f7fea72f619e98dccd"
            },
            {
                "key": 77,
                "hash": "8e5f3efa45dde760fa2a887d2a806a54dcf5f747ac8f8c40f01829ed47f21c25"
            },
            {
                "key": 78,
                "hash": "49f06c6265412046c06fe5f2e29e0de31dac11e9f8f0ae9719491ccdbe976038"
            },
            {
                "key": 79,
                "hash": "5e8b65ea7439a8ad7628708cd10b95e0f4ca85415a08dbffbe4a53ccb154656f"
            },
            {
                "key": 80,
                "hash": "e200184b38c97f14b1a8d4f18d67eb3ee27d3b00a9bb70293ae2adeb289eac68"
            },
            {
                "key": 81,
                "hash": "4c1587b0d245126175243a44176bd05b94cd3a0a1156023340270fe6831f3e57"
            },
            {
                "key": 82,
                "hash": "8930f065124766dd9da46bbd5eb00fe1fca0eeb2be24741b4deee7c54bf14617"
            },
            {
                "key": 83,
                "hash": "4c366af3b39abc8b429e3354110d3e52f86107914c2bf39ccb1f92b8113756f5"
            },
            {
                "key": 84,
                "hash": "31674fb4fabf72a74eab4b569e85d8bfc188a463ec348a5f626f6c736c4527a2"
            },
            {
                "key": 85,
                "hash": "dc0565edea3646838585cb3b27f6a018c44578182badc15910266fc1dd6d7ff2"
            },
            {
                "key": 86,
                "hash": "b316f4053a4c17de2bb59abf80a05555c2e1377b922d3e18ba55c45dcc6d035a"
            },
            {
                "key": 87,
                "hash": "115af2fa18a39c719a02909bc1175b2dc9b3ce44512ca0b991de6a4008ede409"
            },
            {
                "key": 88,
                "hash": "a6c61c4c23ca1c45128726dbc2f9bd3475fc59cee868c1ff99b19998483952aa"
            },
            {
                "key": 89,
                "hash": "a605f5fb0d76738b7f10fa81868a508cc84b09810ce5fcdd649fc0e77e01c1fd"
            },
            {
                "key": 90,
                "hash": "f46641213aa62c55a4cd10b54a721263a91fe800ace7a3da9ca98ba4dc920acc"
            },
            {
                "key": 91,
                "hash": "2bf02e9b78a043ebefe3adf372336e1891ac11a2f191d96c60cc155201170b8d"
            },
            {
                "key": 92,
                "hash": "ee5c52b33e3ee1dcfd3ca554df0412798ebac3af854923e641398a01494135df"
            },
            {
                "key": 93,
                "hash": "31d7f6d24b0a2017575b549c9df9d8a9188243281c207a5dae2da390b3b82c0c"
            },
            {
                "key": 94,
                "hash": "d20e54154459477e7fc9ba28e60076493a895c72e1cbeaf3a8d6eba463ee174f"
            },
            {
                "key": 95,
                "hash": "72139f8ba54ea1d5d3fdd3d5a80740cdb494d6f898cf269215d6df074ee2f0aa"
            },
            {
                "key": 96,
                "hash": "a46ba7bceb86d1a57573291f4e42e671b51bfce768a814e06a52939a5ad1345e"
            },
            {
                "key": 97,
                "hash": "50b70c4f1ad4ed65f2cb086dcfcdeed14f6228886f3df083a95e7725c632d7ad"
            },
            {
                "key": 98,
                "hash": "700607af685ed5d428bceb1ab09d29f2725c47796e77ce53ebd1e7e475456682"
            },
            {
                "key": 99,
                "hash": "de36f537e5b04e23524d8d72251f90a7fcf0267bf33af50dd894b7e953a1cfbd"
            },
            {
                "key": 100,
                "hash": "fddf582673b1300a5304149aa825de2927b90eb7014415cf9f03af73c4c13adb"
            },
            {
                "key": 101,
                "hash": "12bfb7b12c645d2a42f6d4c430aa2ec3fc41ec8aad14e41ad3bf610efa019f11"
            },
            {
                "key": 102,
                "hash": "34b4b26adfd032c1262b2fb0e73cb93964ef6b11d3fced5dbc5aee28c75f944c"
            },
            {
                "key": 103,
                "hash": "5c31d9cb708c86e52e72e3b3fff37342363d59b8fc178fe346f9a24add684659"
            },
            {
                "key": 104,
                "hash": "330c28f687aab06923a9640ff888d23bd39659791e60f88d803082e65beb9802"
            },
            {
                "key": 105,
                "hash": "85095cb82263d12f2f381bce53b382ddf62eaa26816b9a90943079a19a6731fc"
            },
            {
                "key": 106,
                "hash": "1fccf0087153286cee1262aff1074c57a59ed0351eee2adda6c6e013fa545c27"
            },
            {
                "key": 107,
                "hash": "a31da3868557016bb3043d5e09d0945c37b537c2f717b7a2eb32d2adcc261ef4"
            },
            {
                "key": 108,
                "hash": "60558b1caed7b5e75a37d863868964db2676d5f85a68d4a3f0d6593e8193ad05"
            },
            {
                "key": 109,
                "hash": "8a4c89322a5d107eb0be88763a1c631db35d04bb4a95a43f2b2418a8eff4433c"
            },
            {
                "key": 110,
                "hash": "cb25c8a52ba37c1ee8cd0508a60db97cd934062bc7ef1575ad42a4f2215bef98"
            },
            {
                "key": 111,
                "hash": "c48cc15fc80a2545adab44862063d9cd92085462b414b67716f6c4d257966411"
            },
            {
                "key": 112,
                "hash": "b70076071d6240b87a7e3106ce39f150a20a2126210db8b277c49d60f403f470"
            },
            {
                "key": 113,
                "hash": "3554536805514bf4aa48c4291f8bf701e642f4f777868e3feda6e3e257abe0cf"
            },
            {
                "key": 114,
                "hash": "108bd23d95ca024d316a5036e39a8897a03fb62f5ebc8e5b9bd05279109aa688"
            },
            {
                "key": 115,
                "hash": "03c8ee4e692674e4eb1cc9b9e40120325c33b71bc51b31383772eb0e31c27824"
            },
            {
                "key": 116,
                "hash": "a287472fd3b264f5263601de65d09bbeb7602ad7d930c2537ede5e1a32898848"
            },
            {
                "key": 117,
                "hash": "89e53dae544683593e82b9639e05620f947ffcfdc8f9564523d94c8d846f9625"
            },
            {
                "key": 118,
                "hash": "ce5b63e3eeaf8debc1dfe9feefd3aae9d97373fb0d862ef0d83d4945500fe547"
            },
            {
                "key": 119,
                "hash": "6c5fbd82b524f77b401f31f2fbd54e56ace4cc9cf187e3c2182678f1f8a3ae52"
            },
            {
                "key": 120,
                "hash": "44e6750cb594ed93d5fe60eb08458103bd0c2b206959eb69efcb48d548a554d8"
            },
            {
                "key": 121,
                "hash": "c2e76ec45b263a497f5266b50161fb8f2e63e6bff37a8d90bdeb4d8e1dc97af3"
            },
            {
                "key": 122,
                "hash": "41b1fe42d34ec194c690d6932f9c4d524324feceb4126842b766746c456f8f6a"
            },
            {
                "key": 123,
                "hash": "7b60387f44e22b23b88426daea13079c77858ae6a77ded683e15d74e4bd006b0"
            },
            {
                "key": 124,
                "hash": "db272f8fc00722be06bbb34b1873a6c0cb7a9287a340510d452c59a25d52bd69"
            },
            {
                "key": 125,
                "hash": "176acd5f83eb0547bd9dcceef9b1ed57005ac53e1709a8c88aed8db2b70ba970"
            },
            {
                "key": 126,
                "hash": "dbf466de99c657a5d1956a88537ef03e439c5c996646a831253698216c08e382"
            },
            {
                "key": 127,
                "hash": "1c9a27180604b82729b171fcb04a4acdfc335881e379959aaecc78eb8cf85008"
            },
            {
                "key": 128,
                "hash": "352fe77d3340c06f37987696113d57811b32f6db782b1cac973f8e1c68c93e57"
            },
            {
                "key": 129,
                "hash": "e6138ca6b0d879584d019e1d5633f24ffde3d214fc35d0022db2c5b7c6ee6ff7"
            },
            {
                "key": 130,
                "hash": "bb9d4d7d1e53d8a8efc594ba5a4ffbf9a7f61d6e93bb0b86ae3163fc26739b7a"
            },
            {
                "key": 131,
                "hash": "67a8e47517a010bb6b941386760ae8df2de828bba45372d296ed5a0830b7b5b5"
            },
            {
                "key": 132,
                "hash": "d6b97c1d507555f31bee86d784c2020cacaa069021d1735574604d5eaba41c6c"
            },
            {
                "key": 133,
                "hash": "46327fcfe4230c065f5125eaef0e661cd0c3ed3306c5e2cd1901d92073737904"
            },
            {
                "key": 134,
                "hash": "599f3f9e04b2dea6f48c62a798394b17e5b2d7b54abb44eeef9b42173006e193"
            },
            {
                "key": 135,
                "hash": "5951fb4c1b434daeea319d0d5f04028fd1c41938d4f7973e73b0568d0abc2ce6"
            },
            {
                "key": 136,
                "hash": "d043133bc8866534207a587021a808acecc8ff25d39d814f269be13b1f2dc25b"
            },
            {
                "key": 137,
                "hash": "65725b932e0c81c0e659ac5cf63d08791fe5aa2bb00f9321f030d93c22fe5e97"
            },
            {
                "key": 138,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1"
            },
            {
                "key": 139,
                "hash": "a98a68b6f5d0a35a748fa4e7220a21192c10d7f4f173bbf687c3b4030f2f3d94"
            },
            {
                "key": 140,
                "hash": "86bf066c72393325509562d3c93bd47524f8e11979da1339c86c3192a5bca5ad"
            },
            {
                "key": 141,
                "hash": "f8828518c0ad926a3536e9dff79133368999626f5dc5800bf2340fd1aee7637a"
            },
            {
                "key": 142,
                "hash": "808ce20368e8a7c463fcb1e75ba57e6955372a4f3028450526f884c55fb3c72c"
            },
            {
                "key": 143,
                "hash": "a153e9b3725bb42d5650cca0eddd7e5e172b9ab70a046ea546bd53628833e7a0"
            }
        ]


        if wip:  # pragma: no cover
            print("Check Add Eq")
            print(json.dumps(cur_hash_table, indent=4))

        self.assertListEqual(cur_hash_table, expected_hash_table)

    def check_add_single(self):
        """
        Check that the hash table has an extra row
        """
        cur_hash_table = self.api.db.dump_hashes_table()

        expected_hash_table = [
            {
                "key": 1,
                "hash": "f99faa2783761e229fa56eb97d3271852a1cbdbff81dbc2366815714d6c9e4f4"
            },
            {
                "key": 2,
                "hash": "12adde7b6c3908bfd0f30fa694f1f8d73ea8a27edc06860e9bd8c40bb926acc8"
            },
            {
                "key": 3,
                "hash": "2efde3247b6e0e7a2ff6c5a4cb7108706cdbe9752f2c3115f6a07c4f0ba201f4"
            },
            {
                "key": 4,
                "hash": "982bd2594a5f33be0c8adbc3adbee49107fa80416944ee2f26ef6759b1d7e653"
            },
            {
                "key": 5,
                "hash": "da08e8b24416ae8999c548c576162416a3eef99ab71173ab7eccafc6413e144a"
            },
            {
                "key": 6,
                "hash": "100a27c5bf74fc81a29a51c0c985fba8514fca432d7f0713d27f054c1bd7ef95"
            },
            {
                "key": 7,
                "hash": "bd1b305fef7f1a7b4a3922dc692fad8de47e5360537a5cb2e0b87a8760a8063b"
            },
            {
                "key": 8,
                "hash": "e5ce67dc2f3e5ab824cee3c657c5eb17496e41bfacfd92adbb5c596047b86ee9"
            },
            {
                "key": 9,
                "hash": "d9f6eb368a8c1d1ddadd857a3c09c13a5c5672ca5570a2ae3b3321d538265a63"
            },
            {
                "key": 10,
                "hash": "62581ac6fde582dcd845ed7e3d4665a8dd7667a7f28968029442f49862ad520c"
            },
            {
                "key": 11,
                "hash": "b1db6df4556bcbc6ac45dec6d6a569d24629f600e1d91c2f80d29b766d1a23bd"
            },
            {
                "key": 12,
                "hash": "155c94216e25adee74beb3b1b734b572d4ba23d1a34895865a2094a440a0db67"
            },
            {
                "key": 13,
                "hash": "8790197445ce9f35e94cb8121e161a1803319a67829e38426982fad2754cb916"
            },
            {
                "key": 14,
                "hash": "47720b8cf0c53199bb2d8382b33d26b0dd32182471608a1cce968ac8ab81cfb3"
            },
            {
                "key": 15,
                "hash": "9be5927da65efad25b78818316f21867bed7ae7d5adc838a3dde34da0529f25b"
            },
            {
                "key": 16,
                "hash": "0558c32c95576f77db5fa88f6a5704706856782598846cd198e94789317c85fa"
            },
            {
                "key": 17,
                "hash": "cd556bf758e84fc2436099159263fd69f40247c9d01f2c89b514b91381f84c6a"
            },
            {
                "key": 18,
                "hash": "430f1f5919d55509a486eb9282aeb0b8fc4b840d74dca5aeed499305852a8784"
            },
            {
                "key": 19,
                "hash": "004a2637f7f177a2c8ebcb002361061f8faeab9d3ecc4ea6bfa8794e74db2266"
            },
            {
                "key": 20,
                "hash": "a3b5ea9d6b6391ad7d6b2b4494378f8df5cdf242d812701e7e0c7ac75fdee8a4"
            },
            {
                "key": 21,
                "hash": "d59e4ecd729c449346f8cc62c11a82225d2a3d1748c0b33fb22019e02aa69626"
            },
            {
                "key": 22,
                "hash": "d5c38449643bd2f9d3d49abc92092ef3648c820e64a96054b31db0350c838d3a"
            },
            {
                "key": 23,
                "hash": "13c02f764d92a04e70bf695a9acdc7b3244a8106f1b83e54dd5cd3aa17f97d4d"
            },
            {
                "key": 24,
                "hash": "4870ee173d559831d6d998c495522ae1ea3d50138b6eb849fac5dd517402425e"
            },
            {
                "key": 25,
                "hash": "7e24acfe7e6af6ee23d0b7f2ce49e82e2963d61e123de6d01c64a762fb71dda2"
            },
            {
                "key": 26,
                "hash": "05015cd5ddffc5de38202ddde0a937cc28c09f9eec832c2fe22dee0c70748660"
            },
            {
                "key": 27,
                "hash": "9289f722a590f392ffdf383fcca5c4eb0e8e7589255551ac9a96f14872f7966f"
            },
            {
                "key": 28,
                "hash": "f69f97d13606b31e6ca20055ada0bbc931ba6642e000f7f57331c6454526e19b"
            },
            {
                "key": 29,
                "hash": "5eb169774038c774cadef481cffa4d4151153a6d2562095bb340aaf9340de955"
            },
            {
                "key": 30,
                "hash": "ad2b9470cb81a76ac2824dc77d08b0523cab8584681482ba722e75ea83d3701f"
            },
            {
                "key": 31,
                "hash": "b4647b028f8c6007257d3c47cc046eb1b5b4d18859183a78aa0b61e5e1b27611"
            },
            {
                "key": 32,
                "hash": "5800f23cb090f07ab79e6660808d2132d2e5c79568b7dc8a00556e12b9be4cbd"
            },
            {
                "key": 33,
                "hash": "d2ea183dcf9ac41ff45dd80753b904f32434545b7ef4c0ebe455aeb3232e2ce7"
            },
            {
                "key": 34,
                "hash": "9d008c8d57b27f8113316b2c199cfffc104846448724063e3a9ca84b587e3e37"
            },
            {
                "key": 35,
                "hash": "088a28b17d9d6c71bde3fd135c94522e448095ec39e7c99dff927a6ff9b03aae"
            },
            {
                "key": 36,
                "hash": "1f17c72633d282b151382b95dfff0ba2e1cfa3fdb63caf6a8354081768400ed5"
            },
            {
                "key": 37,
                "hash": "ad316f24d1650f465fae2b301c49fbe22cf8eb195d6e56091c2b948acabb8041"
            },
            {
                "key": 38,
                "hash": "093743a01222b9312283d9c934e69f27a6af6b4ce3707f9311e1aaab64c19031"
            },
            {
                "key": 39,
                "hash": "546dd26da6455fa5b7e93a0d0debf43d3db8f9fbbb7c37b3e79fb76d88b2f443"
            },
            {
                "key": 40,
                "hash": "ab20c8bd9ab53184bf815ceacee292d11cbf352dd0c8b0b5e1d8c68cb8e09c39"
            },
            {
                "key": 41,
                "hash": "727aebb321a712c22057b23db4b6469f03f34ff095a724082d96671d291de213"
            },
            {
                "key": 42,
                "hash": "68e5a653809cf483d3f5988f171c9ba4e2ae98d6b82e3582b66dd03425826d01"
            },
            {
                "key": 43,
                "hash": "480f35140c63890e3d422e322fe8760edc1d2c117d3e0acf8bfe137aabd93f6a"
            },
            {
                "key": 44,
                "hash": "446e2c0ce77942a4aca029a64410ea2bb53992cfd19fe8fe9ec7b5c1635b2b17"
            },
            {
                "key": 45,
                "hash": "f2b324c8864963e7a586eb3062bbbcc62bd648fb5070a364ab2ca2ac637cc4dd"
            },
            {
                "key": 46,
                "hash": "ae35bcdbefc6df9aefdecb7357eb031d9d2bd28fb97ba7439bf19b72069c923e"
            },
            {
                "key": 47,
                "hash": "27206ac13bf739072669ad687755f9765bad9fec540f6a36c8d7a7ead5fe1eab"
            },
            {
                "key": 48,
                "hash": "3a52a6f96e4b8eee705193f0f96ddd0d5775f6413bca41e151d339c3393ece12"
            },
            {
                "key": 49,
                "hash": "8afd9f282134afa2d902a2cac2dae797cf4b03de874a93ce65f114e8bb18df0f"
            },
            {
                "key": 50,
                "hash": "ffb600f9959618e47294752c974b8f577dae50a4c4fbd7fb4d76c67298ede296"
            },
            {
                "key": 51,
                "hash": "a2bd347b776c383404284db7898bd51873927e93d5b233c85f138c7a3a7f1f4a"
            },
            {
                "key": 52,
                "hash": "0afb27a1ae3ab4a503b1643362f2ca1e8ec96e0092493cba2c2a357eef696095"
            },
            {
                "key": 53,
                "hash": "79b32f4a05d77e30f66091e2450a64b411843efbaa894d6823b634fd4a298b3d"
            },
            {
                "key": 54,
                "hash": "705c61c7de95706766bd42c2dec60288469cd30d7c2cc5e83dccb78977ce8b4f"
            },
            {
                "key": 55,
                "hash": "4456d404fb4d1dfe17624994d781ad3f13095fff63dbc34c359cc80ec3f1080d"
            },
            {
                "key": 56,
                "hash": "2678d4525e51337aa34114b27bd9d8510c99196d1028204680ae7fdf43d2f9c9"
            },
            {
                "key": 57,
                "hash": "7b22cd6617153158373246ea06a4e5437d840cec15937fc03da9d1e3a901b583"
            },
            {
                "key": 58,
                "hash": "e8bb1334eab28d98be3fa4d19d5fe31eb5cc4648937434c0394e6a7e9c0b7393"
            },
            {
                "key": 59,
                "hash": "8b2d5a876d1480f48210c34af97765afb1bc9916621af82660be9fb67cb7a358"
            },
            {
                "key": 60,
                "hash": "9fd8b458d1dfb66515eeeac7798b5fd19dd78923ead101be2dcfe39db1c67b6f"
            },
            {
                "key": 61,
                "hash": "0ce943b0d6b30d780b7719cab9976d8fb01636e3b86d1bc3c365ce9a83ff8058"
            },
            {
                "key": 62,
                "hash": "505e38457e99740a544737901d9232eae42d12964ca2f2cc8103f7b695ca3cef"
            },
            {
                "key": 63,
                "hash": "17195e31d90b3470e792eebff736e4607510d978126a2daff91f7f13002ee667"
            },
            {
                "key": 64,
                "hash": "e793d43e8eb7c62177a33c005faeb6568e86d6a5be4fa111740bba4691546a03"
            },
            {
                "key": 65,
                "hash": "35339e27d1e261e101b8ecf20af4a74ef2095a1349c6fcc44bd2c8eff478acb9"
            },
            {
                "key": 66,
                "hash": "1e864c544fbb6fab9b2fd110169945600063bbcc15ecf64cccf0f2e9aac0f2ed"
            },
            {
                "key": 67,
                "hash": "6edb114ca2122654242981d24443c0ae7a782c1eb889b49a540f8873041a5356"
            },
            {
                "key": 68,
                "hash": "50d88e34831e49a2c19fdf526609753625425a948cf32d4c2d5ecd471b1d9902"
            },
            {
                "key": 69,
                "hash": "cbbaff856f5aa11676d49ff7c33dd9936ac62247278e4bdea3fda202ba0eb401"
            },
            {
                "key": 70,
                "hash": "2c8b3f212bb598d327e9c5e7205bceba58b066dca88d6efcfa964066c7f9a3b9"
            },
            {
                "key": 71,
                "hash": "c253706f2f012aad60a42510dba9b98917be336f6ebdd58d72e0091f1c1ac264"
            },
            {
                "key": 72,
                "hash": "1f0cec3f1ce9206172a7f69cd32a03e9b3362fc3132e0895410880ddd61a51d6"
            },
            {
                "key": 73,
                "hash": "4fa5571f3326fe38ea4404f1ee27d617c7bd3edbb021e652bd78d9be198bb95b"
            },
            {
                "key": 74,
                "hash": "2f4180abb476401612c21174eda961e6fc6a37450aa3c9d3a1be9a3faa671c79"
            },
            {
                "key": 75,
                "hash": "50466d82b28bbe5546924b7e6bdf3db10c151aa0d6926ca764d9e5ec06b0d099"
            },
            {
                "key": 76,
                "hash": "7c3d6b4c2408dc3e6c0d8a77ed3533e1987bf1566921d5f7fea72f619e98dccd"
            },
            {
                "key": 77,
                "hash": "8e5f3efa45dde760fa2a887d2a806a54dcf5f747ac8f8c40f01829ed47f21c25"
            },
            {
                "key": 78,
                "hash": "49f06c6265412046c06fe5f2e29e0de31dac11e9f8f0ae9719491ccdbe976038"
            },
            {
                "key": 79,
                "hash": "5e8b65ea7439a8ad7628708cd10b95e0f4ca85415a08dbffbe4a53ccb154656f"
            },
            {
                "key": 80,
                "hash": "e200184b38c97f14b1a8d4f18d67eb3ee27d3b00a9bb70293ae2adeb289eac68"
            },
            {
                "key": 81,
                "hash": "4c1587b0d245126175243a44176bd05b94cd3a0a1156023340270fe6831f3e57"
            },
            {
                "key": 82,
                "hash": "8930f065124766dd9da46bbd5eb00fe1fca0eeb2be24741b4deee7c54bf14617"
            },
            {
                "key": 83,
                "hash": "4c366af3b39abc8b429e3354110d3e52f86107914c2bf39ccb1f92b8113756f5"
            },
            {
                "key": 84,
                "hash": "31674fb4fabf72a74eab4b569e85d8bfc188a463ec348a5f626f6c736c4527a2"
            },
            {
                "key": 85,
                "hash": "dc0565edea3646838585cb3b27f6a018c44578182badc15910266fc1dd6d7ff2"
            },
            {
                "key": 86,
                "hash": "b316f4053a4c17de2bb59abf80a05555c2e1377b922d3e18ba55c45dcc6d035a"
            },
            {
                "key": 87,
                "hash": "115af2fa18a39c719a02909bc1175b2dc9b3ce44512ca0b991de6a4008ede409"
            },
            {
                "key": 88,
                "hash": "a6c61c4c23ca1c45128726dbc2f9bd3475fc59cee868c1ff99b19998483952aa"
            },
            {
                "key": 89,
                "hash": "a605f5fb0d76738b7f10fa81868a508cc84b09810ce5fcdd649fc0e77e01c1fd"
            },
            {
                "key": 90,
                "hash": "f46641213aa62c55a4cd10b54a721263a91fe800ace7a3da9ca98ba4dc920acc"
            },
            {
                "key": 91,
                "hash": "2bf02e9b78a043ebefe3adf372336e1891ac11a2f191d96c60cc155201170b8d"
            },
            {
                "key": 92,
                "hash": "ee5c52b33e3ee1dcfd3ca554df0412798ebac3af854923e641398a01494135df"
            },
            {
                "key": 93,
                "hash": "31d7f6d24b0a2017575b549c9df9d8a9188243281c207a5dae2da390b3b82c0c"
            },
            {
                "key": 94,
                "hash": "d20e54154459477e7fc9ba28e60076493a895c72e1cbeaf3a8d6eba463ee174f"
            },
            {
                "key": 95,
                "hash": "72139f8ba54ea1d5d3fdd3d5a80740cdb494d6f898cf269215d6df074ee2f0aa"
            },
            {
                "key": 96,
                "hash": "a46ba7bceb86d1a57573291f4e42e671b51bfce768a814e06a52939a5ad1345e"
            },
            {
                "key": 97,
                "hash": "50b70c4f1ad4ed65f2cb086dcfcdeed14f6228886f3df083a95e7725c632d7ad"
            },
            {
                "key": 98,
                "hash": "700607af685ed5d428bceb1ab09d29f2725c47796e77ce53ebd1e7e475456682"
            },
            {
                "key": 99,
                "hash": "de36f537e5b04e23524d8d72251f90a7fcf0267bf33af50dd894b7e953a1cfbd"
            },
            {
                "key": 100,
                "hash": "fddf582673b1300a5304149aa825de2927b90eb7014415cf9f03af73c4c13adb"
            },
            {
                "key": 101,
                "hash": "12bfb7b12c645d2a42f6d4c430aa2ec3fc41ec8aad14e41ad3bf610efa019f11"
            },
            {
                "key": 102,
                "hash": "34b4b26adfd032c1262b2fb0e73cb93964ef6b11d3fced5dbc5aee28c75f944c"
            },
            {
                "key": 103,
                "hash": "5c31d9cb708c86e52e72e3b3fff37342363d59b8fc178fe346f9a24add684659"
            },
            {
                "key": 104,
                "hash": "330c28f687aab06923a9640ff888d23bd39659791e60f88d803082e65beb9802"
            },
            {
                "key": 105,
                "hash": "85095cb82263d12f2f381bce53b382ddf62eaa26816b9a90943079a19a6731fc"
            },
            {
                "key": 106,
                "hash": "1fccf0087153286cee1262aff1074c57a59ed0351eee2adda6c6e013fa545c27"
            },
            {
                "key": 107,
                "hash": "a31da3868557016bb3043d5e09d0945c37b537c2f717b7a2eb32d2adcc261ef4"
            },
            {
                "key": 108,
                "hash": "60558b1caed7b5e75a37d863868964db2676d5f85a68d4a3f0d6593e8193ad05"
            },
            {
                "key": 109,
                "hash": "8a4c89322a5d107eb0be88763a1c631db35d04bb4a95a43f2b2418a8eff4433c"
            },
            {
                "key": 110,
                "hash": "cb25c8a52ba37c1ee8cd0508a60db97cd934062bc7ef1575ad42a4f2215bef98"
            },
            {
                "key": 111,
                "hash": "c48cc15fc80a2545adab44862063d9cd92085462b414b67716f6c4d257966411"
            },
            {
                "key": 112,
                "hash": "b70076071d6240b87a7e3106ce39f150a20a2126210db8b277c49d60f403f470"
            },
            {
                "key": 113,
                "hash": "3554536805514bf4aa48c4291f8bf701e642f4f777868e3feda6e3e257abe0cf"
            },
            {
                "key": 114,
                "hash": "108bd23d95ca024d316a5036e39a8897a03fb62f5ebc8e5b9bd05279109aa688"
            },
            {
                "key": 115,
                "hash": "03c8ee4e692674e4eb1cc9b9e40120325c33b71bc51b31383772eb0e31c27824"
            },
            {
                "key": 116,
                "hash": "a287472fd3b264f5263601de65d09bbeb7602ad7d930c2537ede5e1a32898848"
            },
            {
                "key": 117,
                "hash": "89e53dae544683593e82b9639e05620f947ffcfdc8f9564523d94c8d846f9625"
            },
            {
                "key": 118,
                "hash": "ce5b63e3eeaf8debc1dfe9feefd3aae9d97373fb0d862ef0d83d4945500fe547"
            },
            {
                "key": 119,
                "hash": "6c5fbd82b524f77b401f31f2fbd54e56ace4cc9cf187e3c2182678f1f8a3ae52"
            },
            {
                "key": 120,
                "hash": "44e6750cb594ed93d5fe60eb08458103bd0c2b206959eb69efcb48d548a554d8"
            },
            {
                "key": 121,
                "hash": "c2e76ec45b263a497f5266b50161fb8f2e63e6bff37a8d90bdeb4d8e1dc97af3"
            },
            {
                "key": 122,
                "hash": "41b1fe42d34ec194c690d6932f9c4d524324feceb4126842b766746c456f8f6a"
            },
            {
                "key": 123,
                "hash": "7b60387f44e22b23b88426daea13079c77858ae6a77ded683e15d74e4bd006b0"
            },
            {
                "key": 124,
                "hash": "db272f8fc00722be06bbb34b1873a6c0cb7a9287a340510d452c59a25d52bd69"
            },
            {
                "key": 125,
                "hash": "176acd5f83eb0547bd9dcceef9b1ed57005ac53e1709a8c88aed8db2b70ba970"
            },
            {
                "key": 126,
                "hash": "dbf466de99c657a5d1956a88537ef03e439c5c996646a831253698216c08e382"
            },
            {
                "key": 127,
                "hash": "1c9a27180604b82729b171fcb04a4acdfc335881e379959aaecc78eb8cf85008"
            },
            {
                "key": 128,
                "hash": "352fe77d3340c06f37987696113d57811b32f6db782b1cac973f8e1c68c93e57"
            },
            {
                "key": 129,
                "hash": "e6138ca6b0d879584d019e1d5633f24ffde3d214fc35d0022db2c5b7c6ee6ff7"
            },
            {
                "key": 130,
                "hash": "bb9d4d7d1e53d8a8efc594ba5a4ffbf9a7f61d6e93bb0b86ae3163fc26739b7a"
            },
            {
                "key": 131,
                "hash": "67a8e47517a010bb6b941386760ae8df2de828bba45372d296ed5a0830b7b5b5"
            },
            {
                "key": 132,
                "hash": "d6b97c1d507555f31bee86d784c2020cacaa069021d1735574604d5eaba41c6c"
            },
            {
                "key": 133,
                "hash": "46327fcfe4230c065f5125eaef0e661cd0c3ed3306c5e2cd1901d92073737904"
            },
            {
                "key": 134,
                "hash": "599f3f9e04b2dea6f48c62a798394b17e5b2d7b54abb44eeef9b42173006e193"
            },
            {
                "key": 135,
                "hash": "5951fb4c1b434daeea319d0d5f04028fd1c41938d4f7973e73b0568d0abc2ce6"
            },
            {
                "key": 136,
                "hash": "d043133bc8866534207a587021a808acecc8ff25d39d814f269be13b1f2dc25b"
            },
            {
                "key": 137,
                "hash": "65725b932e0c81c0e659ac5cf63d08791fe5aa2bb00f9321f030d93c22fe5e97"
            },
            {
                "key": 138,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1"
            },
            {
                "key": 139,
                "hash": "a98a68b6f5d0a35a748fa4e7220a21192c10d7f4f173bbf687c3b4030f2f3d94"
            },
            {
                "key": 140,
                "hash": "86bf066c72393325509562d3c93bd47524f8e11979da1339c86c3192a5bca5ad"
            },
            {
                "key": 141,
                "hash": "f8828518c0ad926a3536e9dff79133368999626f5dc5800bf2340fd1aee7637a"
            },
            {
                "key": 142,
                "hash": "808ce20368e8a7c463fcb1e75ba57e6955372a4f3028450526f884c55fb3c72c"
            },
            {
                "key": 143,
                "hash": "a153e9b3725bb42d5650cca0eddd7e5e172b9ab70a046ea546bd53628833e7a0"
            },
            {
                "key": 144,
                "hash": "uncovered_hash"
            }
        ]

        if wip:  # pragma: no cover
            print("Check Add Single")
            print(json.dumps(cur_hash_table, indent=4))

        self.assertListEqual(cur_hash_table, expected_hash_table)

    def check_add_multiple(self):
        """
        Check that the hash table has an extra row
        """
        cur_hash_table = self.api.db.dump_hashes_table()

        expected_hash_table = [
            {
                "key": 1,
                "hash": "f99faa2783761e229fa56eb97d3271852a1cbdbff81dbc2366815714d6c9e4f4"
            },
            {
                "key": 2,
                "hash": "12adde7b6c3908bfd0f30fa694f1f8d73ea8a27edc06860e9bd8c40bb926acc8"
            },
            {
                "key": 3,
                "hash": "2efde3247b6e0e7a2ff6c5a4cb7108706cdbe9752f2c3115f6a07c4f0ba201f4"
            },
            {
                "key": 4,
                "hash": "982bd2594a5f33be0c8adbc3adbee49107fa80416944ee2f26ef6759b1d7e653"
            },
            {
                "key": 5,
                "hash": "da08e8b24416ae8999c548c576162416a3eef99ab71173ab7eccafc6413e144a"
            },
            {
                "key": 6,
                "hash": "100a27c5bf74fc81a29a51c0c985fba8514fca432d7f0713d27f054c1bd7ef95"
            },
            {
                "key": 7,
                "hash": "bd1b305fef7f1a7b4a3922dc692fad8de47e5360537a5cb2e0b87a8760a8063b"
            },
            {
                "key": 8,
                "hash": "e5ce67dc2f3e5ab824cee3c657c5eb17496e41bfacfd92adbb5c596047b86ee9"
            },
            {
                "key": 9,
                "hash": "d9f6eb368a8c1d1ddadd857a3c09c13a5c5672ca5570a2ae3b3321d538265a63"
            },
            {
                "key": 10,
                "hash": "62581ac6fde582dcd845ed7e3d4665a8dd7667a7f28968029442f49862ad520c"
            },
            {
                "key": 11,
                "hash": "b1db6df4556bcbc6ac45dec6d6a569d24629f600e1d91c2f80d29b766d1a23bd"
            },
            {
                "key": 12,
                "hash": "155c94216e25adee74beb3b1b734b572d4ba23d1a34895865a2094a440a0db67"
            },
            {
                "key": 13,
                "hash": "8790197445ce9f35e94cb8121e161a1803319a67829e38426982fad2754cb916"
            },
            {
                "key": 14,
                "hash": "47720b8cf0c53199bb2d8382b33d26b0dd32182471608a1cce968ac8ab81cfb3"
            },
            {
                "key": 15,
                "hash": "9be5927da65efad25b78818316f21867bed7ae7d5adc838a3dde34da0529f25b"
            },
            {
                "key": 16,
                "hash": "0558c32c95576f77db5fa88f6a5704706856782598846cd198e94789317c85fa"
            },
            {
                "key": 17,
                "hash": "cd556bf758e84fc2436099159263fd69f40247c9d01f2c89b514b91381f84c6a"
            },
            {
                "key": 18,
                "hash": "430f1f5919d55509a486eb9282aeb0b8fc4b840d74dca5aeed499305852a8784"
            },
            {
                "key": 19,
                "hash": "004a2637f7f177a2c8ebcb002361061f8faeab9d3ecc4ea6bfa8794e74db2266"
            },
            {
                "key": 20,
                "hash": "a3b5ea9d6b6391ad7d6b2b4494378f8df5cdf242d812701e7e0c7ac75fdee8a4"
            },
            {
                "key": 21,
                "hash": "d59e4ecd729c449346f8cc62c11a82225d2a3d1748c0b33fb22019e02aa69626"
            },
            {
                "key": 22,
                "hash": "d5c38449643bd2f9d3d49abc92092ef3648c820e64a96054b31db0350c838d3a"
            },
            {
                "key": 23,
                "hash": "13c02f764d92a04e70bf695a9acdc7b3244a8106f1b83e54dd5cd3aa17f97d4d"
            },
            {
                "key": 24,
                "hash": "4870ee173d559831d6d998c495522ae1ea3d50138b6eb849fac5dd517402425e"
            },
            {
                "key": 25,
                "hash": "7e24acfe7e6af6ee23d0b7f2ce49e82e2963d61e123de6d01c64a762fb71dda2"
            },
            {
                "key": 26,
                "hash": "05015cd5ddffc5de38202ddde0a937cc28c09f9eec832c2fe22dee0c70748660"
            },
            {
                "key": 27,
                "hash": "9289f722a590f392ffdf383fcca5c4eb0e8e7589255551ac9a96f14872f7966f"
            },
            {
                "key": 28,
                "hash": "f69f97d13606b31e6ca20055ada0bbc931ba6642e000f7f57331c6454526e19b"
            },
            {
                "key": 29,
                "hash": "5eb169774038c774cadef481cffa4d4151153a6d2562095bb340aaf9340de955"
            },
            {
                "key": 30,
                "hash": "ad2b9470cb81a76ac2824dc77d08b0523cab8584681482ba722e75ea83d3701f"
            },
            {
                "key": 31,
                "hash": "b4647b028f8c6007257d3c47cc046eb1b5b4d18859183a78aa0b61e5e1b27611"
            },
            {
                "key": 32,
                "hash": "5800f23cb090f07ab79e6660808d2132d2e5c79568b7dc8a00556e12b9be4cbd"
            },
            {
                "key": 33,
                "hash": "d2ea183dcf9ac41ff45dd80753b904f32434545b7ef4c0ebe455aeb3232e2ce7"
            },
            {
                "key": 34,
                "hash": "9d008c8d57b27f8113316b2c199cfffc104846448724063e3a9ca84b587e3e37"
            },
            {
                "key": 35,
                "hash": "088a28b17d9d6c71bde3fd135c94522e448095ec39e7c99dff927a6ff9b03aae"
            },
            {
                "key": 36,
                "hash": "1f17c72633d282b151382b95dfff0ba2e1cfa3fdb63caf6a8354081768400ed5"
            },
            {
                "key": 37,
                "hash": "ad316f24d1650f465fae2b301c49fbe22cf8eb195d6e56091c2b948acabb8041"
            },
            {
                "key": 38,
                "hash": "093743a01222b9312283d9c934e69f27a6af6b4ce3707f9311e1aaab64c19031"
            },
            {
                "key": 39,
                "hash": "546dd26da6455fa5b7e93a0d0debf43d3db8f9fbbb7c37b3e79fb76d88b2f443"
            },
            {
                "key": 40,
                "hash": "ab20c8bd9ab53184bf815ceacee292d11cbf352dd0c8b0b5e1d8c68cb8e09c39"
            },
            {
                "key": 41,
                "hash": "727aebb321a712c22057b23db4b6469f03f34ff095a724082d96671d291de213"
            },
            {
                "key": 42,
                "hash": "68e5a653809cf483d3f5988f171c9ba4e2ae98d6b82e3582b66dd03425826d01"
            },
            {
                "key": 43,
                "hash": "480f35140c63890e3d422e322fe8760edc1d2c117d3e0acf8bfe137aabd93f6a"
            },
            {
                "key": 44,
                "hash": "446e2c0ce77942a4aca029a64410ea2bb53992cfd19fe8fe9ec7b5c1635b2b17"
            },
            {
                "key": 45,
                "hash": "f2b324c8864963e7a586eb3062bbbcc62bd648fb5070a364ab2ca2ac637cc4dd"
            },
            {
                "key": 46,
                "hash": "ae35bcdbefc6df9aefdecb7357eb031d9d2bd28fb97ba7439bf19b72069c923e"
            },
            {
                "key": 47,
                "hash": "27206ac13bf739072669ad687755f9765bad9fec540f6a36c8d7a7ead5fe1eab"
            },
            {
                "key": 48,
                "hash": "3a52a6f96e4b8eee705193f0f96ddd0d5775f6413bca41e151d339c3393ece12"
            },
            {
                "key": 49,
                "hash": "8afd9f282134afa2d902a2cac2dae797cf4b03de874a93ce65f114e8bb18df0f"
            },
            {
                "key": 50,
                "hash": "ffb600f9959618e47294752c974b8f577dae50a4c4fbd7fb4d76c67298ede296"
            },
            {
                "key": 51,
                "hash": "a2bd347b776c383404284db7898bd51873927e93d5b233c85f138c7a3a7f1f4a"
            },
            {
                "key": 52,
                "hash": "0afb27a1ae3ab4a503b1643362f2ca1e8ec96e0092493cba2c2a357eef696095"
            },
            {
                "key": 53,
                "hash": "79b32f4a05d77e30f66091e2450a64b411843efbaa894d6823b634fd4a298b3d"
            },
            {
                "key": 54,
                "hash": "705c61c7de95706766bd42c2dec60288469cd30d7c2cc5e83dccb78977ce8b4f"
            },
            {
                "key": 55,
                "hash": "4456d404fb4d1dfe17624994d781ad3f13095fff63dbc34c359cc80ec3f1080d"
            },
            {
                "key": 56,
                "hash": "2678d4525e51337aa34114b27bd9d8510c99196d1028204680ae7fdf43d2f9c9"
            },
            {
                "key": 57,
                "hash": "7b22cd6617153158373246ea06a4e5437d840cec15937fc03da9d1e3a901b583"
            },
            {
                "key": 58,
                "hash": "e8bb1334eab28d98be3fa4d19d5fe31eb5cc4648937434c0394e6a7e9c0b7393"
            },
            {
                "key": 59,
                "hash": "8b2d5a876d1480f48210c34af97765afb1bc9916621af82660be9fb67cb7a358"
            },
            {
                "key": 60,
                "hash": "9fd8b458d1dfb66515eeeac7798b5fd19dd78923ead101be2dcfe39db1c67b6f"
            },
            {
                "key": 61,
                "hash": "0ce943b0d6b30d780b7719cab9976d8fb01636e3b86d1bc3c365ce9a83ff8058"
            },
            {
                "key": 62,
                "hash": "505e38457e99740a544737901d9232eae42d12964ca2f2cc8103f7b695ca3cef"
            },
            {
                "key": 63,
                "hash": "17195e31d90b3470e792eebff736e4607510d978126a2daff91f7f13002ee667"
            },
            {
                "key": 64,
                "hash": "e793d43e8eb7c62177a33c005faeb6568e86d6a5be4fa111740bba4691546a03"
            },
            {
                "key": 65,
                "hash": "35339e27d1e261e101b8ecf20af4a74ef2095a1349c6fcc44bd2c8eff478acb9"
            },
            {
                "key": 66,
                "hash": "1e864c544fbb6fab9b2fd110169945600063bbcc15ecf64cccf0f2e9aac0f2ed"
            },
            {
                "key": 67,
                "hash": "6edb114ca2122654242981d24443c0ae7a782c1eb889b49a540f8873041a5356"
            },
            {
                "key": 68,
                "hash": "50d88e34831e49a2c19fdf526609753625425a948cf32d4c2d5ecd471b1d9902"
            },
            {
                "key": 69,
                "hash": "cbbaff856f5aa11676d49ff7c33dd9936ac62247278e4bdea3fda202ba0eb401"
            },
            {
                "key": 70,
                "hash": "2c8b3f212bb598d327e9c5e7205bceba58b066dca88d6efcfa964066c7f9a3b9"
            },
            {
                "key": 71,
                "hash": "c253706f2f012aad60a42510dba9b98917be336f6ebdd58d72e0091f1c1ac264"
            },
            {
                "key": 72,
                "hash": "1f0cec3f1ce9206172a7f69cd32a03e9b3362fc3132e0895410880ddd61a51d6"
            },
            {
                "key": 73,
                "hash": "4fa5571f3326fe38ea4404f1ee27d617c7bd3edbb021e652bd78d9be198bb95b"
            },
            {
                "key": 74,
                "hash": "2f4180abb476401612c21174eda961e6fc6a37450aa3c9d3a1be9a3faa671c79"
            },
            {
                "key": 75,
                "hash": "50466d82b28bbe5546924b7e6bdf3db10c151aa0d6926ca764d9e5ec06b0d099"
            },
            {
                "key": 76,
                "hash": "7c3d6b4c2408dc3e6c0d8a77ed3533e1987bf1566921d5f7fea72f619e98dccd"
            },
            {
                "key": 77,
                "hash": "8e5f3efa45dde760fa2a887d2a806a54dcf5f747ac8f8c40f01829ed47f21c25"
            },
            {
                "key": 78,
                "hash": "49f06c6265412046c06fe5f2e29e0de31dac11e9f8f0ae9719491ccdbe976038"
            },
            {
                "key": 79,
                "hash": "5e8b65ea7439a8ad7628708cd10b95e0f4ca85415a08dbffbe4a53ccb154656f"
            },
            {
                "key": 80,
                "hash": "e200184b38c97f14b1a8d4f18d67eb3ee27d3b00a9bb70293ae2adeb289eac68"
            },
            {
                "key": 81,
                "hash": "4c1587b0d245126175243a44176bd05b94cd3a0a1156023340270fe6831f3e57"
            },
            {
                "key": 82,
                "hash": "8930f065124766dd9da46bbd5eb00fe1fca0eeb2be24741b4deee7c54bf14617"
            },
            {
                "key": 83,
                "hash": "4c366af3b39abc8b429e3354110d3e52f86107914c2bf39ccb1f92b8113756f5"
            },
            {
                "key": 84,
                "hash": "31674fb4fabf72a74eab4b569e85d8bfc188a463ec348a5f626f6c736c4527a2"
            },
            {
                "key": 85,
                "hash": "dc0565edea3646838585cb3b27f6a018c44578182badc15910266fc1dd6d7ff2"
            },
            {
                "key": 86,
                "hash": "b316f4053a4c17de2bb59abf80a05555c2e1377b922d3e18ba55c45dcc6d035a"
            },
            {
                "key": 87,
                "hash": "115af2fa18a39c719a02909bc1175b2dc9b3ce44512ca0b991de6a4008ede409"
            },
            {
                "key": 88,
                "hash": "a6c61c4c23ca1c45128726dbc2f9bd3475fc59cee868c1ff99b19998483952aa"
            },
            {
                "key": 89,
                "hash": "a605f5fb0d76738b7f10fa81868a508cc84b09810ce5fcdd649fc0e77e01c1fd"
            },
            {
                "key": 90,
                "hash": "f46641213aa62c55a4cd10b54a721263a91fe800ace7a3da9ca98ba4dc920acc"
            },
            {
                "key": 91,
                "hash": "2bf02e9b78a043ebefe3adf372336e1891ac11a2f191d96c60cc155201170b8d"
            },
            {
                "key": 92,
                "hash": "ee5c52b33e3ee1dcfd3ca554df0412798ebac3af854923e641398a01494135df"
            },
            {
                "key": 93,
                "hash": "31d7f6d24b0a2017575b549c9df9d8a9188243281c207a5dae2da390b3b82c0c"
            },
            {
                "key": 94,
                "hash": "d20e54154459477e7fc9ba28e60076493a895c72e1cbeaf3a8d6eba463ee174f"
            },
            {
                "key": 95,
                "hash": "72139f8ba54ea1d5d3fdd3d5a80740cdb494d6f898cf269215d6df074ee2f0aa"
            },
            {
                "key": 96,
                "hash": "a46ba7bceb86d1a57573291f4e42e671b51bfce768a814e06a52939a5ad1345e"
            },
            {
                "key": 97,
                "hash": "50b70c4f1ad4ed65f2cb086dcfcdeed14f6228886f3df083a95e7725c632d7ad"
            },
            {
                "key": 98,
                "hash": "700607af685ed5d428bceb1ab09d29f2725c47796e77ce53ebd1e7e475456682"
            },
            {
                "key": 99,
                "hash": "de36f537e5b04e23524d8d72251f90a7fcf0267bf33af50dd894b7e953a1cfbd"
            },
            {
                "key": 100,
                "hash": "fddf582673b1300a5304149aa825de2927b90eb7014415cf9f03af73c4c13adb"
            },
            {
                "key": 101,
                "hash": "12bfb7b12c645d2a42f6d4c430aa2ec3fc41ec8aad14e41ad3bf610efa019f11"
            },
            {
                "key": 102,
                "hash": "34b4b26adfd032c1262b2fb0e73cb93964ef6b11d3fced5dbc5aee28c75f944c"
            },
            {
                "key": 103,
                "hash": "5c31d9cb708c86e52e72e3b3fff37342363d59b8fc178fe346f9a24add684659"
            },
            {
                "key": 104,
                "hash": "330c28f687aab06923a9640ff888d23bd39659791e60f88d803082e65beb9802"
            },
            {
                "key": 105,
                "hash": "85095cb82263d12f2f381bce53b382ddf62eaa26816b9a90943079a19a6731fc"
            },
            {
                "key": 106,
                "hash": "1fccf0087153286cee1262aff1074c57a59ed0351eee2adda6c6e013fa545c27"
            },
            {
                "key": 107,
                "hash": "a31da3868557016bb3043d5e09d0945c37b537c2f717b7a2eb32d2adcc261ef4"
            },
            {
                "key": 108,
                "hash": "60558b1caed7b5e75a37d863868964db2676d5f85a68d4a3f0d6593e8193ad05"
            },
            {
                "key": 109,
                "hash": "8a4c89322a5d107eb0be88763a1c631db35d04bb4a95a43f2b2418a8eff4433c"
            },
            {
                "key": 110,
                "hash": "cb25c8a52ba37c1ee8cd0508a60db97cd934062bc7ef1575ad42a4f2215bef98"
            },
            {
                "key": 111,
                "hash": "c48cc15fc80a2545adab44862063d9cd92085462b414b67716f6c4d257966411"
            },
            {
                "key": 112,
                "hash": "b70076071d6240b87a7e3106ce39f150a20a2126210db8b277c49d60f403f470"
            },
            {
                "key": 113,
                "hash": "3554536805514bf4aa48c4291f8bf701e642f4f777868e3feda6e3e257abe0cf"
            },
            {
                "key": 114,
                "hash": "108bd23d95ca024d316a5036e39a8897a03fb62f5ebc8e5b9bd05279109aa688"
            },
            {
                "key": 115,
                "hash": "03c8ee4e692674e4eb1cc9b9e40120325c33b71bc51b31383772eb0e31c27824"
            },
            {
                "key": 116,
                "hash": "a287472fd3b264f5263601de65d09bbeb7602ad7d930c2537ede5e1a32898848"
            },
            {
                "key": 117,
                "hash": "89e53dae544683593e82b9639e05620f947ffcfdc8f9564523d94c8d846f9625"
            },
            {
                "key": 118,
                "hash": "ce5b63e3eeaf8debc1dfe9feefd3aae9d97373fb0d862ef0d83d4945500fe547"
            },
            {
                "key": 119,
                "hash": "6c5fbd82b524f77b401f31f2fbd54e56ace4cc9cf187e3c2182678f1f8a3ae52"
            },
            {
                "key": 120,
                "hash": "44e6750cb594ed93d5fe60eb08458103bd0c2b206959eb69efcb48d548a554d8"
            },
            {
                "key": 121,
                "hash": "c2e76ec45b263a497f5266b50161fb8f2e63e6bff37a8d90bdeb4d8e1dc97af3"
            },
            {
                "key": 122,
                "hash": "41b1fe42d34ec194c690d6932f9c4d524324feceb4126842b766746c456f8f6a"
            },
            {
                "key": 123,
                "hash": "7b60387f44e22b23b88426daea13079c77858ae6a77ded683e15d74e4bd006b0"
            },
            {
                "key": 124,
                "hash": "db272f8fc00722be06bbb34b1873a6c0cb7a9287a340510d452c59a25d52bd69"
            },
            {
                "key": 125,
                "hash": "176acd5f83eb0547bd9dcceef9b1ed57005ac53e1709a8c88aed8db2b70ba970"
            },
            {
                "key": 126,
                "hash": "dbf466de99c657a5d1956a88537ef03e439c5c996646a831253698216c08e382"
            },
            {
                "key": 127,
                "hash": "1c9a27180604b82729b171fcb04a4acdfc335881e379959aaecc78eb8cf85008"
            },
            {
                "key": 128,
                "hash": "352fe77d3340c06f37987696113d57811b32f6db782b1cac973f8e1c68c93e57"
            },
            {
                "key": 129,
                "hash": "e6138ca6b0d879584d019e1d5633f24ffde3d214fc35d0022db2c5b7c6ee6ff7"
            },
            {
                "key": 130,
                "hash": "bb9d4d7d1e53d8a8efc594ba5a4ffbf9a7f61d6e93bb0b86ae3163fc26739b7a"
            },
            {
                "key": 131,
                "hash": "67a8e47517a010bb6b941386760ae8df2de828bba45372d296ed5a0830b7b5b5"
            },
            {
                "key": 132,
                "hash": "d6b97c1d507555f31bee86d784c2020cacaa069021d1735574604d5eaba41c6c"
            },
            {
                "key": 133,
                "hash": "46327fcfe4230c065f5125eaef0e661cd0c3ed3306c5e2cd1901d92073737904"
            },
            {
                "key": 134,
                "hash": "599f3f9e04b2dea6f48c62a798394b17e5b2d7b54abb44eeef9b42173006e193"
            },
            {
                "key": 135,
                "hash": "5951fb4c1b434daeea319d0d5f04028fd1c41938d4f7973e73b0568d0abc2ce6"
            },
            {
                "key": 136,
                "hash": "d043133bc8866534207a587021a808acecc8ff25d39d814f269be13b1f2dc25b"
            },
            {
                "key": 137,
                "hash": "65725b932e0c81c0e659ac5cf63d08791fe5aa2bb00f9321f030d93c22fe5e97"
            },
            {
                "key": 138,
                "hash": "cea254d6c081a7abdbb58c905a8f6aed69759a2b7afa43ee0feb92ac96e9edd1"
            },
            {
                "key": 139,
                "hash": "a98a68b6f5d0a35a748fa4e7220a21192c10d7f4f173bbf687c3b4030f2f3d94"
            },
            {
                "key": 140,
                "hash": "86bf066c72393325509562d3c93bd47524f8e11979da1339c86c3192a5bca5ad"
            },
            {
                "key": 141,
                "hash": "f8828518c0ad926a3536e9dff79133368999626f5dc5800bf2340fd1aee7637a"
            },
            {
                "key": 142,
                "hash": "808ce20368e8a7c463fcb1e75ba57e6955372a4f3028450526f884c55fb3c72c"
            },
            {
                "key": 143,
                "hash": "a153e9b3725bb42d5650cca0eddd7e5e172b9ab70a046ea546bd53628833e7a0"
            },
            {
                "key": 144,
                "hash": "hash_1"
            },
            {
                "key": 145,
                "hash": "hash_2"
            },
            {
                "key": 146,
                "hash": "hash_3"
            }
        ]

        if wip:  # pragma: no cover
            print("Check Add Multiple")
            print(json.dumps(cur_hash_table, indent=4))

        self.assertListEqual(cur_hash_table, expected_hash_table)

    def test_hash_table_no_op(self):
        """
        Check that nothing is done, if the hash table isn't modified.
        """
        self.check_hash_table_equivalent()
        self.assertEqual(self.api.db.get_hash_table_size(), 143)

        # Prune
        res = self.api.db.prune_hash()
        self.assertEqual(res, 0)

        self.check_hash_table_equivalent()
        self.assertEqual(self.api.db.get_hash_table_size(), 143)

    def test_hash_table_single_add(self):
        """
        Test that one element is removed from the hash table if one element is added
        """
        # Check base is equivalent
        self.check_hash_table_equivalent()
        self.assertEqual(self.api.db.get_hash_table_size(), 143)

        self.api.db.insert_get_hash_key(file_hash="uncovered_hash")
        self.assertEqual(self.api.db.get_hash_table_size(), 144)

        self.check_add_single()

        res = self.api.db.prune_hash()
        self.assertEqual(1, res)

        self.check_hash_table_equivalent()
        self.assertEqual(self.api.db.get_hash_table_size(), 143)

    def test_hash_table_multiple_add(self):
        """
        Test that all extra elements are removed from the hash table if multiple are added
        """
        # Check base is equivalent
        self.check_hash_table_equivalent()
        self.assertEqual(self.api.db.get_hash_table_size(), 143)

        self.api.db.insert_get_hash_key(file_hash="hash_1")
        self.api.db.insert_get_hash_key(file_hash="hash_2")
        self.api.db.insert_get_hash_key(file_hash="hash_3")
        self.assertEqual(self.api.db.get_hash_table_size(), 146)

        self.check_add_multiple()

        res = self.api.db.prune_hash()
        self.assertEqual(3, res)

        self.check_hash_table_equivalent()
        self.assertEqual(self.api.db.get_hash_table_size(), 143)


class TestPruneGPS(TestClassifyBase):
    """
    Fully test the api.db.prune_gps function
    """
    def check_gps_equivalent(self):
        """
        Check the base state of the gps table
        """
        cur_gps_table = self.api.db.dump_gps_location_table()

        expected_gps_table = [
            {
                "key": 1,
                "gps_latitude": 47.36865,
                "gps_longitude": 8.539183
            },
            {
                "key": 2,
                "gps_latitude": 40.73061,
                "gps_longitude": -73.935242
            },
            {
                "key": 3,
                "gps_latitude": -29.90453,
                "gps_longitude": -71.24894
            },
            {
                "key": 4,
                "gps_latitude": -28.4792625,
                "gps_longitude": 24.6727134999667
            }
        ]


        if wip:  # pragma: no cover
            print("Check Equivalent")
            print(json.dumps(cur_gps_table, indent=4))

        self.assertListEqual(cur_gps_table, expected_gps_table)

    def check_gps_add_single(self):
        """
        Check the GPS state after adding a single extra row
        """
        cur_gps_table = self.api.db.dump_gps_location_table()

        expected_gps_table = [
            {
                "key": 1,
                "gps_latitude": 47.36865,
                "gps_longitude": 8.539183
            },
            {
                "key": 2,
                "gps_latitude": 40.73061,
                "gps_longitude": -73.935242
            },
            {
                "key": 3,
                "gps_latitude": -29.90453,
                "gps_longitude": -71.24894
            },
            {
                "key": 4,
                "gps_latitude": -28.4792625,
                "gps_longitude": 24.6727134999667
            },
            {
                "key": 5,
                "gps_latitude": 10.5,
                "gps_longitude": 10.5
            }
        ]

        if wip:  # pragma: no cover
            print("Check Add Single")
            print(json.dumps(cur_gps_table, indent=4))

        self.assertListEqual(cur_gps_table, expected_gps_table)

    def check_gps_add_multiple(self):
        """
        Check the GPS state after adding a multiple extra row
        """
        cur_gps_table = self.api.db.dump_gps_location_table()

        expected_gps_table = [
            {
                "key": 1,
                "gps_latitude": 47.36865,
                "gps_longitude": 8.539183
            },
            {
                "key": 2,
                "gps_latitude": 40.73061,
                "gps_longitude": -73.935242
            },
            {
                "key": 3,
                "gps_latitude": -29.90453,
                "gps_longitude": -71.24894
            },
            {
                "key": 4,
                "gps_latitude": -28.4792625,
                "gps_longitude": 24.6727134999667
            },
            {
                "key": 5,
                "gps_latitude": 10.5,
                "gps_longitude": 10.5
            },
            {
                "key": 6,
                "gps_latitude": 11.5,
                "gps_longitude": 11.5
            },
            {
                "key": 7,
                "gps_latitude": 12.5,
                "gps_longitude": 12.5
            }
        ]

        if wip:  # pragma: no cover
            print("Check Add Multiple")
            print(json.dumps(cur_gps_table, indent=4))

        self.assertListEqual(cur_gps_table, expected_gps_table)

    def test_no_op_gps_prune(self):
        """
        Test that nothing is modified in the base case
        """
        self.check_gps_equivalent()

        res = self.api.db.prune_gps()
        self.assertEqual(res, 0)

        self.check_gps_equivalent()

    def test_single_op_gps_prune(self):
        """
        Check that a single row was deleted
        """
        self.check_gps_equivalent()

        self.api.db.insert_get_gps_loc(10.5, 10.5)
        self.check_gps_add_single()

        res = self.api.db.prune_gps()
        self.assertEqual(res, 1)

        self.check_gps_equivalent()

    def test_multiple_op_gps_prune(self):
        """
        Check that multiple rows were deleted
        """
        self.check_gps_equivalent()

        self.api.db.insert_get_gps_loc(10.5, 10.5)
        self.api.db.insert_get_gps_loc(11.5, 11.5)
        self.api.db.insert_get_gps_loc(12.5, 12.5)
        self.check_gps_add_single()

        res = self.api.db.prune_gps()
        self.assertEqual(res, 1)

        self.check_gps_equivalent()
        self.assertEqual(self.api.db.get_gps_table_size(), 4)


class TestPruneAll(TestClassifyBase):
    """
    Simple class for covering the prune_all function
    """

    def test_just_cover_prune_all(self):
        """
        INFO: Every functionality of prune_all was tested in the upper classes.

        This test class serves only the purpose of covering prune_all. Which is just a short hand for calling all
        prune methods. What is asserted is, that a logging call is made
        """
        with self.assertLogs(self.api.main_logger, logging.INFO):
            res = self.api.prune_all()
            self.assertEqual(res, 0)