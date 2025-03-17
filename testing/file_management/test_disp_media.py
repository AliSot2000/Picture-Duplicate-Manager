import json
import os
import shutil
import unittest
from typing import Optional, Type, Callable
from unittest.mock import patch

import cv2
import ffmpeg

from photo_lib.new_photo_model import PhotoAPI
from photo_lib.utils import rec_list_all

wip = False

"""
This file fully tests the following functions:
- api._create_img_thumbnails
- api._create_vid_thumbnails
- api._create_display_file
- api.create_display_files
"""


# Custom error to test exception handling
class CustomError(Exception):
    """
    Custom Exception to test the except Exception as e
    """
    ...


def raise_ffmpeg_error(*args, **kwargs):
    """
    Function to raise an ffmpeg exception. Needs separate function to define stdout and stderr
    """
    stdout = "Standard Out sample".encode("utf-8")
    stderr = "Standard Error sample".encode("utf-8")
    raise ffmpeg.Error(cmd="Custom Exception Command", stdout=stdout, stderr=stderr)


def raise_custom_error(exc: Type[Exception], *args, **kwargs):
    """
    Function to accept any arguments, which raises the following exe
    """
    raise exc("Custom Error for Testing")


def bake_exception(exc: Type[Exception]) -> Callable:
    """
    Function creates wrapper around raise_custom_error which bakes in the error to raise
    """
    def ret_fun(*args, **kwargs):
        raise_custom_error(exc, *args, **kwargs)

    return ret_fun


class TestDisplayMediaCreation(unittest.TestCase):
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
        cls.shadow_db = os.path.abspath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shadow_db")))
        cls.temp_db = os.path.abspath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_db")))
        cls.media_source = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_file_out"))
        cls.import_source = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch"))
        cls.tbl_dump_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db_dump", "import"))

        # Check the input files are present
        if not os.path.exists(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_file_out"))):
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

    @patch("cv2.imwrite", new=bake_exception(exc=cv2.error))
    def test_img_exception(self):
        """
        Test the correct handling of cv2.error
        """
        img = os.path.join(self.media_source, "test_thumbnails", "test_horizontal_thumbnail.png")

        self.assertFalse(self.api._create_img_thumbnails(in_path=img,
                                                         out_path=self.api.db.full_thumbnail_path(1000),
                                                         major_size=512))

    @patch("cv2.imwrite", new=bake_exception(AttributeError))
    def test_img_attribute_error(self):
        """
        Test the correct handling of AttributeError
        """
        img = os.path.join(self.media_source, "test_thumbnails", "test_horizontal_thumbnail.png")

        self.assertFalse(self.api._create_img_thumbnails(in_path=img,
                                                         out_path=self.api.db.full_thumbnail_path(1000),
                                                         major_size=512))

    @patch("cv2.imwrite", new=bake_exception(CustomError))
    def test_any_exception(self):
        """
        Test the correct handling of other Exception
        """
        img = os.path.join(self.media_source, "test_thumbnails", "test_horizontal_thumbnail.png")

        self.assertFalse(self.api._create_img_thumbnails(in_path=img,
                                                         out_path=self.api.db.full_thumbnail_path(1000),
                                                         major_size=512))

    @patch("ffmpeg.probe", new=raise_ffmpeg_error)
    def test_probe_ffmpeg_exception(self):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    @patch("ffmpeg.probe", new=bake_exception(exc=CustomError))
    def test_probe_any_exception(self):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    @patch("ffmpeg.probe")
    def test_get_stream_key_error(self, mock_probe: unittest.mock.MagicMock):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        mock_probe.return_value = {}

        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    @patch("ffmpeg.probe")
    def test_get_stream_index_error(self, mock_probe: unittest.mock.MagicMock):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        mock_probe.return_value = {"streams": []}

        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    @patch("ffmpeg.probe")
    def test_get_any_exception(self, mock_probe: unittest.mock.MagicMock):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        mock_probe.return_value = None

        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    @patch("ffmpeg.input", new=raise_ffmpeg_error)
    def test_input_ffmpeg_error(self):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    @patch("ffmpeg.input", new=bake_exception(AttributeError))
    def test_input_any_exception(self):
        """
        Test the correct handling of ffmpeg.Error in the ffmpeg.probe call
        """
        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")

        self.assertFalse(self.api._create_vid_thumbnails(in_path=vid,
                                                         out_path=self.api.db.full_thumbnail_path(1000)))

    def test_create_images(self):
        """
        Check that the images are created successfully (relies on images created with .png ext)
        """
        img1 = os.path.join(self.media_source, "test_thumbnails", "test_horizontal_thumbnail.png")
        img2 = os.path.join(self.media_source, "test_thumbnails", "test_vertical_thumbnail.png")

        out1 = self.api.db.full_thumbnail_path(1000)
        out2 = self.api.db.full_thumbnail_path(1001)

        self.assertTrue(self.api._create_display_file(in_path=img1,
                                                      out_path=out1,
                                                      major_size=500))

        self.assertTrue(self.api._create_display_file(in_path=img2,
                                                      out_path=out2,
                                                      major_size=500))

        self.assertTrue(os.path.exists(out1))
        self.assertTrue(os.path.exists(out2))

    def test_create_video_thumb(self):
        """
        Check that video thumbnails are created correctly.
        """
        vid1 = os.path.join(self.media_source, "test_thumbnails", "test_short_video.mp4")
        vid2 = os.path.join(self.media_source, "test_thumbnails", "test_long_video.mp4")

        out1 = self.api.db.full_thumbnail_path(2000)
        out2 = self.api.db.full_thumbnail_path(2001)

        self.assertTrue(self.api._create_display_file(in_path=vid1,
                                                      out_path=out1,
                                                      major_size=500))

        self.assertTrue(self.api._create_display_file(in_path=vid2,
                                                      out_path=out2,
                                                      major_size=500))

        self.assertTrue(os.path.exists(out1))
        self.assertTrue(os.path.exists(out2))

    def test_harakiri(self):
        """
        Check that harakiri method works too
        """
        img = os.path.join(self.media_source, "test_thumbnails", "test_vertical_thumbnail.md")
        out1 = self.api.db.full_thumbnail_path(3000)

        vid = os.path.join(self.media_source, "test_thumbnails", "test_short_video.pdf")
        out2 = self.api.db.full_thumbnail_path(3001)

        self.assertTrue(self.api._create_display_file(in_path=img,
                                                      out_path=out1,
                                                      major_size=500))

        self.assertTrue(self.api._create_display_file(in_path=vid,
                                                      out_path=out2,
                                                      major_size=500))

        self.assertTrue(os.path.exists(out1))
        self.assertTrue(os.path.exists(out2))

    def test_extract_fail(self):
        """
        Check premature abort of file creation
        """
        img1 = os.path.join(self.media_source, "test_thumbnails", "corrupt.mp4")
        out1 = self.api.db.full_thumbnail_path(5000)

        self.assertFalse(self.api._create_display_file(in_path=img1, out_path=out1, major_size=500))

        self.assertFalse(os.path.exists(out1))

    def test_empty(self):
        """
        Test create_display_files and specify neither thumbnail or miniatures
        """
        c, m = self.api.create_display_files(thumbnail=False, miniature=False)
        self.assertEqual(c, 0)
        self.assertEqual(c, 0)

        files = rec_list_all(self.api.db.get_thumb_dir())

        self.assertEqual(files, [])

    def test_missing(self):
        """
        Removing a folder from the database directory. Check that the number of missing files is correct
        and that file content is correct
        """
        # Move the folder
        os.rename(os.path.join(self.api.db.root_path, "1990", "06", "01"),
                  os.path.join(self.api.db.root_path, "1990", "06", "temp"))

        c, m = self.api.create_display_files()

        self.assertEqual(c, 250)
        self.assertEqual(m, 32)

        self.check_paths_missing_1990_06_01()

    def test_missing_with_subsequent_creation(self):
        """
        Test files are missing, and add the files, only the missing files should be generated.
        """
        # Move the folder
        os.rename(os.path.join(self.api.db.root_path, "1990", "06", "01"),
                  os.path.join(self.api.db.root_path, "1990", "06", "temp"))

        c1, m1 = self.api.create_display_files(thumbnail=True, miniature=True, overwrite=False)

        self.assertEqual(c1, 250)
        self.assertEqual(m1, 32)

        self.check_paths_missing_1990_06_01()

        # Move the folder back
        os.rename(os.path.join(self.api.db.root_path, "1990", "06", "temp"),
                  os.path.join(self.api.db.root_path, "1990", "06", "01"))

        c2, m2 = self.api.create_display_files(thumbnail=True, miniature=True, overwrite=False)

        self.assertEqual(c2, 64)
        self.assertEqual(m2, 0)

        self.check_all_disp_paths()

    def test_missing_with_subsequent_override(self):
        """
        Test files are missing, and add the files. All files are regenerated.
        """
        # Move the folder
        os.rename(os.path.join(self.api.db.root_path, "1990", "06", "01"),
                  os.path.join(self.api.db.root_path, "1990", "06", "temp"))

        c1, m1 = self.api.create_display_files(thumbnail=True, miniature=True, overwrite=False)

        self.assertEqual(c1, 250)
        self.assertEqual(m1, 32)

        self.check_paths_missing_1990_06_01()

        # Move the folder back
        os.rename(os.path.join(self.api.db.root_path, "1990", "06", "temp"),
                  os.path.join(self.api.db.root_path, "1990", "06", "01"))

        c2, m2 = self.api.create_display_files(thumbnail=True, miniature=True, overwrite=True)

        self.assertEqual(c2, 314)
        self.assertEqual(m2, 0)

        self.check_all_disp_paths()

    def test_only_thumb(self):
        """
        Test only thumbnails created.
        """
        c1, m1 = self.api.create_display_files(thumbnail=True, miniature=False, overwrite=False)

        self.assertEqual(c1, 157)
        self.assertEqual(m1, 0)

        self.check_only_thumbnails()

    def test_only_miniature(self):
        """
        Test only miniatures created.
        """
        c1, m1 = self.api.create_display_files(thumbnail=False, miniature=True, overwrite=False)

        self.assertEqual(c1, 157)
        self.assertEqual(m1, 0)

        self.check_only_miniatures()

    def check_paths_missing_1990_06_01(self):
        """
        Having moved the 1990/06/01 dir check the present files
        """
        files = [file.removeprefix(self.api.db.get_thumb_dir()).removeprefix(os.sep)
                 for file in rec_list_all(self.api.db.get_thumb_dir())]

        db_files = [
            "miniature_0001.jpeg",
            "miniature_0002.jpeg",
            "miniature_0003.jpeg",
            "miniature_0004.jpeg",
            "miniature_0005.jpeg",
            "miniature_0006.jpeg",
            "miniature_0007.jpeg",
            "miniature_0008.jpeg",
            "miniature_0009.jpeg",
            "miniature_0010.jpeg",
            "miniature_0011.jpeg",
            "miniature_0012.jpeg",
            "miniature_0013.jpeg",
            "miniature_0014.jpeg",
            "miniature_0015.jpeg",
            "miniature_0016.jpeg",
            "miniature_0017.jpeg",
            "miniature_0018.jpeg",
            "miniature_0019.jpeg",
            "miniature_0020.jpeg",
            "miniature_0021.jpeg",
            "miniature_0022.jpeg",
            "miniature_0023.jpeg",
            "miniature_0024.jpeg",
            "miniature_0025.jpeg",
            "miniature_0026.jpeg",
            "miniature_0027.jpeg",
            "miniature_0028.jpeg",
            "miniature_0029.jpeg",
            "miniature_0030.jpeg",
            "miniature_0031.jpeg",
            "miniature_0064.jpeg",
            "miniature_0065.jpeg",
            "miniature_0066.jpeg",
            "miniature_0067.jpeg",
            "miniature_0068.jpeg",
            "miniature_0069.jpeg",
            "miniature_0070.jpeg",
            "miniature_0071.jpeg",
            "miniature_0072.jpeg",
            "miniature_0073.jpeg",
            "miniature_0074.jpeg",
            "miniature_0075.jpeg",
            "miniature_0076.jpeg",
            "miniature_0077.jpeg",
            "miniature_0078.jpeg",
            "miniature_0079.jpeg",
            "miniature_0080.jpeg",
            "miniature_0081.jpeg",
            "miniature_0082.jpeg",
            "miniature_0083.jpeg",
            "miniature_0084.jpeg",
            "miniature_0085.jpeg",
            "miniature_0086.jpeg",
            "miniature_0087.jpeg",
            "miniature_0088.jpeg",
            "miniature_0089.jpeg",
            "miniature_0090.jpeg",
            "miniature_0091.jpeg",
            "miniature_0092.jpeg",
            "miniature_0093.jpeg",
            "miniature_0094.jpeg",
            "miniature_0095.jpeg",
            "miniature_0096.jpeg",
            "miniature_0097.jpeg",
            "miniature_0098.jpeg",
            "miniature_0099.jpeg",
            "miniature_0100.jpeg",
            "miniature_0101.jpeg",
            "miniature_0102.jpeg",
            "miniature_0103.jpeg",
            "miniature_0104.jpeg",
            "miniature_0105.jpeg",
            "miniature_0106.jpeg",
            "miniature_0107.jpeg",
            "miniature_0108.jpeg",
            "miniature_0109.jpeg",
            "miniature_0110.jpeg",
            "miniature_0111.jpeg",
            "miniature_0112.jpeg",
            "miniature_0113.jpeg",
            "miniature_0114.jpeg",
            "miniature_0115.jpeg",
            "miniature_0116.jpeg",
            "miniature_0117.jpeg",
            "miniature_0118.jpeg",
            "miniature_0119.jpeg",
            "miniature_0120.jpeg",
            "miniature_0121.jpeg",
            "miniature_0122.jpeg",
            "miniature_0123.jpeg",
            "miniature_0124.jpeg",
            "miniature_0125.jpeg",
            "miniature_0126.jpeg",
            "miniature_0127.jpeg",
            "miniature_0128.jpeg",
            "miniature_0129.jpeg",
            "miniature_0130.jpeg",
            "miniature_0131.jpeg",
            "miniature_0132.jpeg",
            "miniature_0133.jpeg",
            "miniature_0134.jpeg",
            "miniature_0135.jpeg",
            "miniature_0136.jpeg",
            "miniature_0137.jpeg",
            "miniature_0138.jpeg",
            "miniature_0139.jpeg",
            "miniature_0140.jpeg",
            "miniature_0141.jpeg",
            "miniature_0142.jpeg",
            "miniature_0143.jpeg",
            "miniature_0144.jpeg",
            "miniature_0145.jpeg",
            "miniature_0146.jpeg",
            "miniature_0147.jpeg",
            "miniature_0148.jpeg",
            "miniature_0149.jpeg",
            "miniature_0150.jpeg",
            "miniature_0151.jpeg",
            "miniature_0152.jpeg",
            "miniature_0153.jpeg",
            "miniature_0154.jpeg",
            "miniature_0155.jpeg",
            "miniature_0156.jpeg",
            "miniature_0157.jpeg",
            "thumb_0001.jpeg",
            "thumb_0002.jpeg",
            "thumb_0003.jpeg",
            "thumb_0004.jpeg",
            "thumb_0005.jpeg",
            "thumb_0006.jpeg",
            "thumb_0007.jpeg",
            "thumb_0008.jpeg",
            "thumb_0009.jpeg",
            "thumb_0010.jpeg",
            "thumb_0011.jpeg",
            "thumb_0012.jpeg",
            "thumb_0013.jpeg",
            "thumb_0014.jpeg",
            "thumb_0015.jpeg",
            "thumb_0016.jpeg",
            "thumb_0017.jpeg",
            "thumb_0018.jpeg",
            "thumb_0019.jpeg",
            "thumb_0020.jpeg",
            "thumb_0021.jpeg",
            "thumb_0022.jpeg",
            "thumb_0023.jpeg",
            "thumb_0024.jpeg",
            "thumb_0025.jpeg",
            "thumb_0026.jpeg",
            "thumb_0027.jpeg",
            "thumb_0028.jpeg",
            "thumb_0029.jpeg",
            "thumb_0030.jpeg",
            "thumb_0031.jpeg",
            "thumb_0064.jpeg",
            "thumb_0065.jpeg",
            "thumb_0066.jpeg",
            "thumb_0067.jpeg",
            "thumb_0068.jpeg",
            "thumb_0069.jpeg",
            "thumb_0070.jpeg",
            "thumb_0071.jpeg",
            "thumb_0072.jpeg",
            "thumb_0073.jpeg",
            "thumb_0074.jpeg",
            "thumb_0075.jpeg",
            "thumb_0076.jpeg",
            "thumb_0077.jpeg",
            "thumb_0078.jpeg",
            "thumb_0079.jpeg",
            "thumb_0080.jpeg",
            "thumb_0081.jpeg",
            "thumb_0082.jpeg",
            "thumb_0083.jpeg",
            "thumb_0084.jpeg",
            "thumb_0085.jpeg",
            "thumb_0086.jpeg",
            "thumb_0087.jpeg",
            "thumb_0088.jpeg",
            "thumb_0089.jpeg",
            "thumb_0090.jpeg",
            "thumb_0091.jpeg",
            "thumb_0092.jpeg",
            "thumb_0093.jpeg",
            "thumb_0094.jpeg",
            "thumb_0095.jpeg",
            "thumb_0096.jpeg",
            "thumb_0097.jpeg",
            "thumb_0098.jpeg",
            "thumb_0099.jpeg",
            "thumb_0100.jpeg",
            "thumb_0101.jpeg",
            "thumb_0102.jpeg",
            "thumb_0103.jpeg",
            "thumb_0104.jpeg",
            "thumb_0105.jpeg",
            "thumb_0106.jpeg",
            "thumb_0107.jpeg",
            "thumb_0108.jpeg",
            "thumb_0109.jpeg",
            "thumb_0110.jpeg",
            "thumb_0111.jpeg",
            "thumb_0112.jpeg",
            "thumb_0113.jpeg",
            "thumb_0114.jpeg",
            "thumb_0115.jpeg",
            "thumb_0116.jpeg",
            "thumb_0117.jpeg",
            "thumb_0118.jpeg",
            "thumb_0119.jpeg",
            "thumb_0120.jpeg",
            "thumb_0121.jpeg",
            "thumb_0122.jpeg",
            "thumb_0123.jpeg",
            "thumb_0124.jpeg",
            "thumb_0125.jpeg",
            "thumb_0126.jpeg",
            "thumb_0127.jpeg",
            "thumb_0128.jpeg",
            "thumb_0129.jpeg",
            "thumb_0130.jpeg",
            "thumb_0131.jpeg",
            "thumb_0132.jpeg",
            "thumb_0133.jpeg",
            "thumb_0134.jpeg",
            "thumb_0135.jpeg",
            "thumb_0136.jpeg",
            "thumb_0137.jpeg",
            "thumb_0138.jpeg",
            "thumb_0139.jpeg",
            "thumb_0140.jpeg",
            "thumb_0141.jpeg",
            "thumb_0142.jpeg",
            "thumb_0143.jpeg",
            "thumb_0144.jpeg",
            "thumb_0145.jpeg",
            "thumb_0146.jpeg",
            "thumb_0147.jpeg",
            "thumb_0148.jpeg",
            "thumb_0149.jpeg",
            "thumb_0150.jpeg",
            "thumb_0151.jpeg",
            "thumb_0152.jpeg",
            "thumb_0153.jpeg",
            "thumb_0154.jpeg",
            "thumb_0155.jpeg",
            "thumb_0156.jpeg",
            "thumb_0157.jpeg"
        ]

        if wip:  # pragma: no cover
            print(json.dumps(sorted(files), indent=4))

        self.assertListEqual(db_files, sorted(files))

    def check_all_disp_paths(self):
        """
        Check that all Thumbnails and all Miniatures are created
        """
        files = [file.removeprefix(self.api.db.get_thumb_dir()).removeprefix(os.sep)
                 for file in rec_list_all(self.api.db.get_thumb_dir())]

        db_files = [
            "miniature_0001.jpeg",
            "miniature_0002.jpeg",
            "miniature_0003.jpeg",
            "miniature_0004.jpeg",
            "miniature_0005.jpeg",
            "miniature_0006.jpeg",
            "miniature_0007.jpeg",
            "miniature_0008.jpeg",
            "miniature_0009.jpeg",
            "miniature_0010.jpeg",
            "miniature_0011.jpeg",
            "miniature_0012.jpeg",
            "miniature_0013.jpeg",
            "miniature_0014.jpeg",
            "miniature_0015.jpeg",
            "miniature_0016.jpeg",
            "miniature_0017.jpeg",
            "miniature_0018.jpeg",
            "miniature_0019.jpeg",
            "miniature_0020.jpeg",
            "miniature_0021.jpeg",
            "miniature_0022.jpeg",
            "miniature_0023.jpeg",
            "miniature_0024.jpeg",
            "miniature_0025.jpeg",
            "miniature_0026.jpeg",
            "miniature_0027.jpeg",
            "miniature_0028.jpeg",
            "miniature_0029.jpeg",
            "miniature_0030.jpeg",
            "miniature_0031.jpeg",
            "miniature_0032.jpeg",
            "miniature_0033.jpeg",
            "miniature_0034.jpeg",
            "miniature_0035.jpeg",
            "miniature_0036.jpeg",
            "miniature_0037.jpeg",
            "miniature_0038.jpeg",
            "miniature_0039.jpeg",
            "miniature_0040.jpeg",
            "miniature_0041.jpeg",
            "miniature_0042.jpeg",
            "miniature_0043.jpeg",
            "miniature_0044.jpeg",
            "miniature_0045.jpeg",
            "miniature_0046.jpeg",
            "miniature_0047.jpeg",
            "miniature_0048.jpeg",
            "miniature_0049.jpeg",
            "miniature_0050.jpeg",
            "miniature_0051.jpeg",
            "miniature_0052.jpeg",
            "miniature_0053.jpeg",
            "miniature_0054.jpeg",
            "miniature_0055.jpeg",
            "miniature_0056.jpeg",
            "miniature_0057.jpeg",
            "miniature_0058.jpeg",
            "miniature_0059.jpeg",
            "miniature_0060.jpeg",
            "miniature_0061.jpeg",
            "miniature_0062.jpeg",
            "miniature_0063.jpeg",
            "miniature_0064.jpeg",
            "miniature_0065.jpeg",
            "miniature_0066.jpeg",
            "miniature_0067.jpeg",
            "miniature_0068.jpeg",
            "miniature_0069.jpeg",
            "miniature_0070.jpeg",
            "miniature_0071.jpeg",
            "miniature_0072.jpeg",
            "miniature_0073.jpeg",
            "miniature_0074.jpeg",
            "miniature_0075.jpeg",
            "miniature_0076.jpeg",
            "miniature_0077.jpeg",
            "miniature_0078.jpeg",
            "miniature_0079.jpeg",
            "miniature_0080.jpeg",
            "miniature_0081.jpeg",
            "miniature_0082.jpeg",
            "miniature_0083.jpeg",
            "miniature_0084.jpeg",
            "miniature_0085.jpeg",
            "miniature_0086.jpeg",
            "miniature_0087.jpeg",
            "miniature_0088.jpeg",
            "miniature_0089.jpeg",
            "miniature_0090.jpeg",
            "miniature_0091.jpeg",
            "miniature_0092.jpeg",
            "miniature_0093.jpeg",
            "miniature_0094.jpeg",
            "miniature_0095.jpeg",
            "miniature_0096.jpeg",
            "miniature_0097.jpeg",
            "miniature_0098.jpeg",
            "miniature_0099.jpeg",
            "miniature_0100.jpeg",
            "miniature_0101.jpeg",
            "miniature_0102.jpeg",
            "miniature_0103.jpeg",
            "miniature_0104.jpeg",
            "miniature_0105.jpeg",
            "miniature_0106.jpeg",
            "miniature_0107.jpeg",
            "miniature_0108.jpeg",
            "miniature_0109.jpeg",
            "miniature_0110.jpeg",
            "miniature_0111.jpeg",
            "miniature_0112.jpeg",
            "miniature_0113.jpeg",
            "miniature_0114.jpeg",
            "miniature_0115.jpeg",
            "miniature_0116.jpeg",
            "miniature_0117.jpeg",
            "miniature_0118.jpeg",
            "miniature_0119.jpeg",
            "miniature_0120.jpeg",
            "miniature_0121.jpeg",
            "miniature_0122.jpeg",
            "miniature_0123.jpeg",
            "miniature_0124.jpeg",
            "miniature_0125.jpeg",
            "miniature_0126.jpeg",
            "miniature_0127.jpeg",
            "miniature_0128.jpeg",
            "miniature_0129.jpeg",
            "miniature_0130.jpeg",
            "miniature_0131.jpeg",
            "miniature_0132.jpeg",
            "miniature_0133.jpeg",
            "miniature_0134.jpeg",
            "miniature_0135.jpeg",
            "miniature_0136.jpeg",
            "miniature_0137.jpeg",
            "miniature_0138.jpeg",
            "miniature_0139.jpeg",
            "miniature_0140.jpeg",
            "miniature_0141.jpeg",
            "miniature_0142.jpeg",
            "miniature_0143.jpeg",
            "miniature_0144.jpeg",
            "miniature_0145.jpeg",
            "miniature_0146.jpeg",
            "miniature_0147.jpeg",
            "miniature_0148.jpeg",
            "miniature_0149.jpeg",
            "miniature_0150.jpeg",
            "miniature_0151.jpeg",
            "miniature_0152.jpeg",
            "miniature_0153.jpeg",
            "miniature_0154.jpeg",
            "miniature_0155.jpeg",
            "miniature_0156.jpeg",
            "miniature_0157.jpeg",
            "thumb_0001.jpeg",
            "thumb_0002.jpeg",
            "thumb_0003.jpeg",
            "thumb_0004.jpeg",
            "thumb_0005.jpeg",
            "thumb_0006.jpeg",
            "thumb_0007.jpeg",
            "thumb_0008.jpeg",
            "thumb_0009.jpeg",
            "thumb_0010.jpeg",
            "thumb_0011.jpeg",
            "thumb_0012.jpeg",
            "thumb_0013.jpeg",
            "thumb_0014.jpeg",
            "thumb_0015.jpeg",
            "thumb_0016.jpeg",
            "thumb_0017.jpeg",
            "thumb_0018.jpeg",
            "thumb_0019.jpeg",
            "thumb_0020.jpeg",
            "thumb_0021.jpeg",
            "thumb_0022.jpeg",
            "thumb_0023.jpeg",
            "thumb_0024.jpeg",
            "thumb_0025.jpeg",
            "thumb_0026.jpeg",
            "thumb_0027.jpeg",
            "thumb_0028.jpeg",
            "thumb_0029.jpeg",
            "thumb_0030.jpeg",
            "thumb_0031.jpeg",
            "thumb_0032.jpeg",
            "thumb_0033.jpeg",
            "thumb_0034.jpeg",
            "thumb_0035.jpeg",
            "thumb_0036.jpeg",
            "thumb_0037.jpeg",
            "thumb_0038.jpeg",
            "thumb_0039.jpeg",
            "thumb_0040.jpeg",
            "thumb_0041.jpeg",
            "thumb_0042.jpeg",
            "thumb_0043.jpeg",
            "thumb_0044.jpeg",
            "thumb_0045.jpeg",
            "thumb_0046.jpeg",
            "thumb_0047.jpeg",
            "thumb_0048.jpeg",
            "thumb_0049.jpeg",
            "thumb_0050.jpeg",
            "thumb_0051.jpeg",
            "thumb_0052.jpeg",
            "thumb_0053.jpeg",
            "thumb_0054.jpeg",
            "thumb_0055.jpeg",
            "thumb_0056.jpeg",
            "thumb_0057.jpeg",
            "thumb_0058.jpeg",
            "thumb_0059.jpeg",
            "thumb_0060.jpeg",
            "thumb_0061.jpeg",
            "thumb_0062.jpeg",
            "thumb_0063.jpeg",
            "thumb_0064.jpeg",
            "thumb_0065.jpeg",
            "thumb_0066.jpeg",
            "thumb_0067.jpeg",
            "thumb_0068.jpeg",
            "thumb_0069.jpeg",
            "thumb_0070.jpeg",
            "thumb_0071.jpeg",
            "thumb_0072.jpeg",
            "thumb_0073.jpeg",
            "thumb_0074.jpeg",
            "thumb_0075.jpeg",
            "thumb_0076.jpeg",
            "thumb_0077.jpeg",
            "thumb_0078.jpeg",
            "thumb_0079.jpeg",
            "thumb_0080.jpeg",
            "thumb_0081.jpeg",
            "thumb_0082.jpeg",
            "thumb_0083.jpeg",
            "thumb_0084.jpeg",
            "thumb_0085.jpeg",
            "thumb_0086.jpeg",
            "thumb_0087.jpeg",
            "thumb_0088.jpeg",
            "thumb_0089.jpeg",
            "thumb_0090.jpeg",
            "thumb_0091.jpeg",
            "thumb_0092.jpeg",
            "thumb_0093.jpeg",
            "thumb_0094.jpeg",
            "thumb_0095.jpeg",
            "thumb_0096.jpeg",
            "thumb_0097.jpeg",
            "thumb_0098.jpeg",
            "thumb_0099.jpeg",
            "thumb_0100.jpeg",
            "thumb_0101.jpeg",
            "thumb_0102.jpeg",
            "thumb_0103.jpeg",
            "thumb_0104.jpeg",
            "thumb_0105.jpeg",
            "thumb_0106.jpeg",
            "thumb_0107.jpeg",
            "thumb_0108.jpeg",
            "thumb_0109.jpeg",
            "thumb_0110.jpeg",
            "thumb_0111.jpeg",
            "thumb_0112.jpeg",
            "thumb_0113.jpeg",
            "thumb_0114.jpeg",
            "thumb_0115.jpeg",
            "thumb_0116.jpeg",
            "thumb_0117.jpeg",
            "thumb_0118.jpeg",
            "thumb_0119.jpeg",
            "thumb_0120.jpeg",
            "thumb_0121.jpeg",
            "thumb_0122.jpeg",
            "thumb_0123.jpeg",
            "thumb_0124.jpeg",
            "thumb_0125.jpeg",
            "thumb_0126.jpeg",
            "thumb_0127.jpeg",
            "thumb_0128.jpeg",
            "thumb_0129.jpeg",
            "thumb_0130.jpeg",
            "thumb_0131.jpeg",
            "thumb_0132.jpeg",
            "thumb_0133.jpeg",
            "thumb_0134.jpeg",
            "thumb_0135.jpeg",
            "thumb_0136.jpeg",
            "thumb_0137.jpeg",
            "thumb_0138.jpeg",
            "thumb_0139.jpeg",
            "thumb_0140.jpeg",
            "thumb_0141.jpeg",
            "thumb_0142.jpeg",
            "thumb_0143.jpeg",
            "thumb_0144.jpeg",
            "thumb_0145.jpeg",
            "thumb_0146.jpeg",
            "thumb_0147.jpeg",
            "thumb_0148.jpeg",
            "thumb_0149.jpeg",
            "thumb_0150.jpeg",
            "thumb_0151.jpeg",
            "thumb_0152.jpeg",
            "thumb_0153.jpeg",
            "thumb_0154.jpeg",
            "thumb_0155.jpeg",
            "thumb_0156.jpeg",
            "thumb_0157.jpeg"
        ]

        if wip:  # pragma: no cover
            print(json.dumps(sorted(files), indent=4))

        self.assertListEqual(db_files, sorted(files))

    def check_only_thumbnails(self):
        """
        Check that the directory only contains thumbnails
        """
        files = [file.removeprefix(self.api.db.get_thumb_dir()).removeprefix(os.sep)
                 for file in rec_list_all(self.api.db.get_thumb_dir())]

        db_files = [
            "thumb_0001.jpeg",
            "thumb_0002.jpeg",
            "thumb_0003.jpeg",
            "thumb_0004.jpeg",
            "thumb_0005.jpeg",
            "thumb_0006.jpeg",
            "thumb_0007.jpeg",
            "thumb_0008.jpeg",
            "thumb_0009.jpeg",
            "thumb_0010.jpeg",
            "thumb_0011.jpeg",
            "thumb_0012.jpeg",
            "thumb_0013.jpeg",
            "thumb_0014.jpeg",
            "thumb_0015.jpeg",
            "thumb_0016.jpeg",
            "thumb_0017.jpeg",
            "thumb_0018.jpeg",
            "thumb_0019.jpeg",
            "thumb_0020.jpeg",
            "thumb_0021.jpeg",
            "thumb_0022.jpeg",
            "thumb_0023.jpeg",
            "thumb_0024.jpeg",
            "thumb_0025.jpeg",
            "thumb_0026.jpeg",
            "thumb_0027.jpeg",
            "thumb_0028.jpeg",
            "thumb_0029.jpeg",
            "thumb_0030.jpeg",
            "thumb_0031.jpeg",
            "thumb_0032.jpeg",
            "thumb_0033.jpeg",
            "thumb_0034.jpeg",
            "thumb_0035.jpeg",
            "thumb_0036.jpeg",
            "thumb_0037.jpeg",
            "thumb_0038.jpeg",
            "thumb_0039.jpeg",
            "thumb_0040.jpeg",
            "thumb_0041.jpeg",
            "thumb_0042.jpeg",
            "thumb_0043.jpeg",
            "thumb_0044.jpeg",
            "thumb_0045.jpeg",
            "thumb_0046.jpeg",
            "thumb_0047.jpeg",
            "thumb_0048.jpeg",
            "thumb_0049.jpeg",
            "thumb_0050.jpeg",
            "thumb_0051.jpeg",
            "thumb_0052.jpeg",
            "thumb_0053.jpeg",
            "thumb_0054.jpeg",
            "thumb_0055.jpeg",
            "thumb_0056.jpeg",
            "thumb_0057.jpeg",
            "thumb_0058.jpeg",
            "thumb_0059.jpeg",
            "thumb_0060.jpeg",
            "thumb_0061.jpeg",
            "thumb_0062.jpeg",
            "thumb_0063.jpeg",
            "thumb_0064.jpeg",
            "thumb_0065.jpeg",
            "thumb_0066.jpeg",
            "thumb_0067.jpeg",
            "thumb_0068.jpeg",
            "thumb_0069.jpeg",
            "thumb_0070.jpeg",
            "thumb_0071.jpeg",
            "thumb_0072.jpeg",
            "thumb_0073.jpeg",
            "thumb_0074.jpeg",
            "thumb_0075.jpeg",
            "thumb_0076.jpeg",
            "thumb_0077.jpeg",
            "thumb_0078.jpeg",
            "thumb_0079.jpeg",
            "thumb_0080.jpeg",
            "thumb_0081.jpeg",
            "thumb_0082.jpeg",
            "thumb_0083.jpeg",
            "thumb_0084.jpeg",
            "thumb_0085.jpeg",
            "thumb_0086.jpeg",
            "thumb_0087.jpeg",
            "thumb_0088.jpeg",
            "thumb_0089.jpeg",
            "thumb_0090.jpeg",
            "thumb_0091.jpeg",
            "thumb_0092.jpeg",
            "thumb_0093.jpeg",
            "thumb_0094.jpeg",
            "thumb_0095.jpeg",
            "thumb_0096.jpeg",
            "thumb_0097.jpeg",
            "thumb_0098.jpeg",
            "thumb_0099.jpeg",
            "thumb_0100.jpeg",
            "thumb_0101.jpeg",
            "thumb_0102.jpeg",
            "thumb_0103.jpeg",
            "thumb_0104.jpeg",
            "thumb_0105.jpeg",
            "thumb_0106.jpeg",
            "thumb_0107.jpeg",
            "thumb_0108.jpeg",
            "thumb_0109.jpeg",
            "thumb_0110.jpeg",
            "thumb_0111.jpeg",
            "thumb_0112.jpeg",
            "thumb_0113.jpeg",
            "thumb_0114.jpeg",
            "thumb_0115.jpeg",
            "thumb_0116.jpeg",
            "thumb_0117.jpeg",
            "thumb_0118.jpeg",
            "thumb_0119.jpeg",
            "thumb_0120.jpeg",
            "thumb_0121.jpeg",
            "thumb_0122.jpeg",
            "thumb_0123.jpeg",
            "thumb_0124.jpeg",
            "thumb_0125.jpeg",
            "thumb_0126.jpeg",
            "thumb_0127.jpeg",
            "thumb_0128.jpeg",
            "thumb_0129.jpeg",
            "thumb_0130.jpeg",
            "thumb_0131.jpeg",
            "thumb_0132.jpeg",
            "thumb_0133.jpeg",
            "thumb_0134.jpeg",
            "thumb_0135.jpeg",
            "thumb_0136.jpeg",
            "thumb_0137.jpeg",
            "thumb_0138.jpeg",
            "thumb_0139.jpeg",
            "thumb_0140.jpeg",
            "thumb_0141.jpeg",
            "thumb_0142.jpeg",
            "thumb_0143.jpeg",
            "thumb_0144.jpeg",
            "thumb_0145.jpeg",
            "thumb_0146.jpeg",
            "thumb_0147.jpeg",
            "thumb_0148.jpeg",
            "thumb_0149.jpeg",
            "thumb_0150.jpeg",
            "thumb_0151.jpeg",
            "thumb_0152.jpeg",
            "thumb_0153.jpeg",
            "thumb_0154.jpeg",
            "thumb_0155.jpeg",
            "thumb_0156.jpeg",
            "thumb_0157.jpeg"
        ]

        self.assertListEqual(db_files, sorted(files))

    def check_only_miniatures(self):
        """
        Check only the miniatures are in the thumbnail directory.
        """
        files = [file.removeprefix(self.api.db.get_thumb_dir()).removeprefix(os.sep)
                 for file in rec_list_all(self.api.db.get_thumb_dir())]

        db_files = [
            "miniature_0001.jpeg",
            "miniature_0002.jpeg",
            "miniature_0003.jpeg",
            "miniature_0004.jpeg",
            "miniature_0005.jpeg",
            "miniature_0006.jpeg",
            "miniature_0007.jpeg",
            "miniature_0008.jpeg",
            "miniature_0009.jpeg",
            "miniature_0010.jpeg",
            "miniature_0011.jpeg",
            "miniature_0012.jpeg",
            "miniature_0013.jpeg",
            "miniature_0014.jpeg",
            "miniature_0015.jpeg",
            "miniature_0016.jpeg",
            "miniature_0017.jpeg",
            "miniature_0018.jpeg",
            "miniature_0019.jpeg",
            "miniature_0020.jpeg",
            "miniature_0021.jpeg",
            "miniature_0022.jpeg",
            "miniature_0023.jpeg",
            "miniature_0024.jpeg",
            "miniature_0025.jpeg",
            "miniature_0026.jpeg",
            "miniature_0027.jpeg",
            "miniature_0028.jpeg",
            "miniature_0029.jpeg",
            "miniature_0030.jpeg",
            "miniature_0031.jpeg",
            "miniature_0032.jpeg",
            "miniature_0033.jpeg",
            "miniature_0034.jpeg",
            "miniature_0035.jpeg",
            "miniature_0036.jpeg",
            "miniature_0037.jpeg",
            "miniature_0038.jpeg",
            "miniature_0039.jpeg",
            "miniature_0040.jpeg",
            "miniature_0041.jpeg",
            "miniature_0042.jpeg",
            "miniature_0043.jpeg",
            "miniature_0044.jpeg",
            "miniature_0045.jpeg",
            "miniature_0046.jpeg",
            "miniature_0047.jpeg",
            "miniature_0048.jpeg",
            "miniature_0049.jpeg",
            "miniature_0050.jpeg",
            "miniature_0051.jpeg",
            "miniature_0052.jpeg",
            "miniature_0053.jpeg",
            "miniature_0054.jpeg",
            "miniature_0055.jpeg",
            "miniature_0056.jpeg",
            "miniature_0057.jpeg",
            "miniature_0058.jpeg",
            "miniature_0059.jpeg",
            "miniature_0060.jpeg",
            "miniature_0061.jpeg",
            "miniature_0062.jpeg",
            "miniature_0063.jpeg",
            "miniature_0064.jpeg",
            "miniature_0065.jpeg",
            "miniature_0066.jpeg",
            "miniature_0067.jpeg",
            "miniature_0068.jpeg",
            "miniature_0069.jpeg",
            "miniature_0070.jpeg",
            "miniature_0071.jpeg",
            "miniature_0072.jpeg",
            "miniature_0073.jpeg",
            "miniature_0074.jpeg",
            "miniature_0075.jpeg",
            "miniature_0076.jpeg",
            "miniature_0077.jpeg",
            "miniature_0078.jpeg",
            "miniature_0079.jpeg",
            "miniature_0080.jpeg",
            "miniature_0081.jpeg",
            "miniature_0082.jpeg",
            "miniature_0083.jpeg",
            "miniature_0084.jpeg",
            "miniature_0085.jpeg",
            "miniature_0086.jpeg",
            "miniature_0087.jpeg",
            "miniature_0088.jpeg",
            "miniature_0089.jpeg",
            "miniature_0090.jpeg",
            "miniature_0091.jpeg",
            "miniature_0092.jpeg",
            "miniature_0093.jpeg",
            "miniature_0094.jpeg",
            "miniature_0095.jpeg",
            "miniature_0096.jpeg",
            "miniature_0097.jpeg",
            "miniature_0098.jpeg",
            "miniature_0099.jpeg",
            "miniature_0100.jpeg",
            "miniature_0101.jpeg",
            "miniature_0102.jpeg",
            "miniature_0103.jpeg",
            "miniature_0104.jpeg",
            "miniature_0105.jpeg",
            "miniature_0106.jpeg",
            "miniature_0107.jpeg",
            "miniature_0108.jpeg",
            "miniature_0109.jpeg",
            "miniature_0110.jpeg",
            "miniature_0111.jpeg",
            "miniature_0112.jpeg",
            "miniature_0113.jpeg",
            "miniature_0114.jpeg",
            "miniature_0115.jpeg",
            "miniature_0116.jpeg",
            "miniature_0117.jpeg",
            "miniature_0118.jpeg",
            "miniature_0119.jpeg",
            "miniature_0120.jpeg",
            "miniature_0121.jpeg",
            "miniature_0122.jpeg",
            "miniature_0123.jpeg",
            "miniature_0124.jpeg",
            "miniature_0125.jpeg",
            "miniature_0126.jpeg",
            "miniature_0127.jpeg",
            "miniature_0128.jpeg",
            "miniature_0129.jpeg",
            "miniature_0130.jpeg",
            "miniature_0131.jpeg",
            "miniature_0132.jpeg",
            "miniature_0133.jpeg",
            "miniature_0134.jpeg",
            "miniature_0135.jpeg",
            "miniature_0136.jpeg",
            "miniature_0137.jpeg",
            "miniature_0138.jpeg",
            "miniature_0139.jpeg",
            "miniature_0140.jpeg",
            "miniature_0141.jpeg",
            "miniature_0142.jpeg",
            "miniature_0143.jpeg",
            "miniature_0144.jpeg",
            "miniature_0145.jpeg",
            "miniature_0146.jpeg",
            "miniature_0147.jpeg",
            "miniature_0148.jpeg",
            "miniature_0149.jpeg",
            "miniature_0150.jpeg",
            "miniature_0151.jpeg",
            "miniature_0152.jpeg",
            "miniature_0153.jpeg",
            "miniature_0154.jpeg",
            "miniature_0155.jpeg",
            "miniature_0156.jpeg",
            "miniature_0157.jpeg"
        ]

        self.assertListEqual(db_files, sorted(files))
