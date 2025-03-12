import os
import shutil
import unittest
from typing import Optional, Type, Callable
from unittest.mock import patch

import cv2
import ffmpeg

from photo_lib.new_photo_model import PhotoAPI


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

