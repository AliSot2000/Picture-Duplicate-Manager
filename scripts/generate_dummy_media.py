import datetime
import os.path
import shutil
import zoneinfo as zi
from datetime import datetime as dt
from typing import Tuple, Dict

import cv2
import exiftool
import numpy as np


"""
Call this file to generate the dummy media for the unit tests of the database
"""


def add_text(text: str, pos: Tuple[int, int], mat: np.ndarray, scale: int = 3):
    """
    Add Text to an image.

    :param text: Text to add. (will be split by newline and stripped.)
    :param pos: Position of the text to add.
    :param mat: Mat to add to.
    :param scale: Scale factor for the font
    """
    lines = [line.strip() for line in text.split("\n")]

    font = cv2.FONT_HERSHEY_PLAIN
    col = (255, 255, 255)
    thickness = 2

    cur_y = pos[0]

    for line in lines:
        size, baseline = cv2.getTextSize(line, cv2.FONT_HERSHEY_PLAIN, scale, thickness)
        width, height = size
        cur_y = cur_y + int(height * 1.5)
        org = (pos[0], cur_y)
        # drawing the actual text
        mat = cv2.putText(mat, line, org, font, scale, col, thickness, cv2.LINE_AA)

    return mat


def hello_world2():
    """
    New version to test our add text method.
    """
    im = np.zeros((1080, 1920, 3), np.uint8)

    text = "Hello World\n   This is the second line     \n    And this the third. \n and guess what, this is the fourth"

    im = add_text(text, (50, 50), im)
    cv2.imshow("Data", im )
    cv2.waitKey(0)


def hello_world():
    """
    First Hello World Version to experiment with opencv
    """
    # blank image
    im = np.zeros((1080, 1920, 3), np.uint8)

    string = "Hello World!"

    font = cv2.FONT_HERSHEY_PLAIN

    org = (150, 250)

    font_scale = 3

    col = (255, 255, 255)

    thickness = 2

    size, baseline = cv2.getTextSize(string, font, font_scale, thickness)
    print(size, baseline)
    width, height = size

    img = cv2.putText(im, string, (org[0], org[1]+height), font, font_scale, col, thickness, cv2.LINE_AA)
    cv2.drawMarker(img, org, col, thickness, cv2.LINE_AA)
    # cv2.line(img, (org[0], org[1]-height+baseline), (org[0]+width, org[1]-height+baseline), col, thickness, cv2.LINE_AA)
    # cv2.rectangle(img, org, (org[0]+width, org[1]-height), col, 1, cv2.LINE_AA)

    cv2.imshow("Data", img )
    cv2.waitKey(0)


def add_exif_data(dst: str, created: dt, tag_override: Dict = None):
    """
    Add exif data to an image or video, if specified.

    :param dst: Destination path
    :param created: Date of creation
    :param tag_override: Tag override
    """
    if tag_override is None:
        tag_override = {"EXIF:ModifyDate": created.strftime("%Y:%m:%d %H:%M:%S"),
                        "EXIF:OffsetTime": created.strftime("%z")}

    if len(tag_override) > 0:
        with exiftool.ExifToolHelper() as eh:
            eh.set_tags(files=dst, tags=tag_override, params=["-overwrite_original"])

    os.utime(dst, times=(created.timestamp(), created.timestamp()))


def create_image(text: str, created: dt, dst: str, height: int = 1080, width: int = 1920, tag_override: Dict = None):
    """
    Create a file with the following text written onto it.

    :param text: Text to be written
    :param created: Date the file was created
    :param height: Height of the file
    :param width: Width of the file
    :param dst: Destination where to write the file to.
    :param tag_override: Dictionary of tags to override
    """
    print(f"Creating File: {os.path.basename(dst)}")
    assert height > 0, "Height must be greater than 0"
    assert width > 0, "Width must be greater than 0"
    assert created.tzinfo is not None, "Creation date must be timezone aware"

    mat = np.zeros((height, width, 3), np.uint8)

    org = (50, 50)

    text_mat = add_text(text=text,mat=mat, pos=org, scale=3)

    cv2.imwrite(dst, text_mat)

    add_exif_data(dst, created, tag_override)


def create_video(text: str, duration: int, created: dt, dst: str, height: int = 1080, width: int = 1920,
                 tag_override: Dict = None):
    """
    Create a video file for testing.

    :param text: Base Text to put into video.
    :param duration: length of video in seconds
    :param created: Date the file was created
    :param height: Height of the file
    :param width: Width of the file
    :param dst: Destination where to write the file to.
    :param tag_override: Dictionary of tags to override
    """
    print(f"Creating File: {os.path.basename(dst)}")
    assert height > 0, "Height must be greater than 0"
    assert width > 0, "Width must be greater than 0"
    assert created.tzinfo is not None, "Creation date must be timezone aware"

    fmt_str = "mp4v"
    fmt = cv2.VideoWriter.fourcc(*fmt_str)
    writer = cv2.VideoWriter(dst, fmt, 24, (1920, 1080))

    end = duration * 24

    for i in range(end):
        assert writer.isOpened(), "Writer needs to be open"

        img = np.zeros((height, width, 3), np.uint8)
        new_mat = add_text(f"{text} {i // 24:02}:{i % 24:02}", mat=img, pos=(50, 50))

        org = (50, 520)

        width = int((i + 1) / end * 1820)
        col = (255, 255, 255)
        cv2.rectangle(img, org, (org[0] + width, org[1] + 40), col, 1, cv2.LINE_AA)

        writer.write(new_mat)

    writer.release()

    add_exif_data(dst, created, tag_override)


def create_files_from_dict(arg_dict: dict, tgt_dir: str):
    """
    Create the files in a given directory
    """
    # Create the directory
    if not os.path.exists(tgt_dir):
        os.makedirs(tgt_dir)

    for file_name, file_args in arg_dict.items():
        create_image(text=file_args["text"], created=file_args["created"], dst=os.path.join(tgt_dir, file_name))



if __name__ == '__main__':
    # File Spec
    cet = zi.ZoneInfo("CET")

    files = {}

    target_dir = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..", "testing", "test_file_out"))

    # Clear the dir first
    shutil.rmtree(target_dir, ignore_errors=True)

    for i in range(7):
        # Create a file for the directory
        files[f"{i+1}"] = {}

        for j in range(2**i):
            # Compute hours and seconds
            s = j % 60
            h = j // 60

            # Create the files.
            files[f"{i+1}"][f"{i+1}_{j+1}.png"] = {
                "text": f"Image Day {i+1} \n idx {j+1}",
                "created": dt(year=1990, month=i+1, day=1, hour=12, minute=h, second=s, tzinfo=cet)

            }

    # Make the test files for the import test
    import_matches = {
        "11_Binary_Match_Main.png": {
            "text": "Match Test, \nBinary Match Main",
            "created": dt(year=1990, month=10, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "12_Hash_Match_Main.png": {
            "text": "Match Test, \nBinary Match Main",
            "created": dt(year=1990, month=10, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "13_Binary_Match_Trash.png": {
            "text": "Match Test, \nBinary Match Main",
            "created": dt(year=1990, month=10, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "14_Hash_Match_Trash.png": {
            "text": "Match Test, \nBinary Match Main",
            "created": dt(year=1990, month=10, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "15_Binary_Match_Duplicates.png": {
            "text": "Match Test, \nBinary Match Main",
            "created": dt(year=1990, month=10, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "16_Hash_Match_Duplicates.png": {
            "text": "Match Test, \nBinary Match Main",
            "created": dt(year=1990, month=10, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },

        "21_Hash_Match_Main.png": {
            "text": "Match Test, \nHash Match Main",
            "created": dt(year=1990, month=10, day=2, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "22_Binary_Match_Trash.png": {
            "text": "Match Test, \nHash Match Main",
            "created": dt(year=1990, month=10, day=2, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "23_Hash_Match_Trash.png": {
            "text": "Match Test, \nHash Match Main",
            "created": dt(year=1990, month=10, day=2, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "24_Binary_Match_Duplicates.png": {
            "text": "Match Test, \nHash Match Main",
            "created": dt(year=1990, month=10, day=2, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "25_Hash_Match_Duplicates.png": {
            "text": "Match Test, \nHash Match Main",
            "created": dt(year=1990, month=10, day=2, hour=12, minute=0, second=0, tzinfo=cet)
        },

        "31_Binary_Match_Trash.png": {
            "text": "Match Test, \nBinary Match Trash",
            "created": dt(year=1990, month=10, day=3, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "32_Hash_Match_Trash.png": {
            "text": "Match Test, \nBinary Match Trash",
            "created": dt(year=1990, month=10, day=3, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "33_Binary_Match_Duplicates.png": {
            "text": "Match Test, \nBinary Match Trash",
            "created": dt(year=1990, month=10, day=3, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "34_Hash_Match_Duplicates.png": {
            "text": "Match Test, \nBinary Match Trash",
            "created": dt(year=1990, month=10, day=3, hour=12, minute=0, second=0, tzinfo=cet)
        },

        "41_Hash_Match_Trash.png": {
            "text": "Match Test, \nHash Match Trash",
            "created": dt(year=1990, month=10, day=4, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "42_Binary_Match_Duplicates.png": {
            "text": "Match Test, \nHash Match Trash",
            "created": dt(year=1990, month=10, day=4, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "43_Hash_Match_Duplicates.png": {
            "text": "Match Test, \nHash Match Trash",
            "created": dt(year=1990, month=10, day=4, hour=12, minute=0, second=0, tzinfo=cet)
        },

        "51_Binary_Match_Duplicates.png": {
            "text": "Match Test, \nBinary Match Duplicates",
            "created": dt(year=1990, month=10, day=5, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "52_Hash_Match_Duplicates.png": {
            "text": "Match Test, \nBinary Match Duplicates",
            "created": dt(year=1990, month=10, day=5, hour=12, minute=0, second=0, tzinfo=cet)
        },

        "61_Hash_Match_Duplicates.png": {
            "text": "Match Test, \nHash Match Duplicates",
            "created": dt(year=1990, month=10, day=6, hour=12, minute=0, second=0, tzinfo=cet)
        },

        "71_Duplicate_Target.png" : {
            "text": "Target for all files marked as duplicates",
            "created": dt(year=1990, month=10, day=7, hour=12, minute=0, second=0, tzinfo=cet)
        }
    }

    # Make the test files for match test
    import_match_input = {
        "10_Matching_Source.png": import_matches["11_Binary_Match_Main.png"],
        "20_Matching_Source.png": import_matches["21_Hash_Match_Main.png"],
        "30_Matching_Source.png": import_matches["31_Binary_Match_Trash.png"],
        "40_Matching_Source.png": import_matches["41_Hash_Match_Trash.png"],
        "50_Matching_Source.png": import_matches["51_Binary_Match_Duplicates.png"],
        "60_Matching_Source.png": import_matches["61_Hash_Match_Duplicates.png"],
    }

    # Make the files for the allowed ext test
    allowed_ext_test = {
        "01_format.png": {
            "text": "Test Format png",
            "created": dt(year=1990, month=8, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "02_format.jpg": {
            "text": "Test Format jpg",
            "created": dt(year=1990, month=8, day=1, hour=12, minute=0, second=1, tzinfo=cet)
        },
        "03_format.jpeg": {
            "text": "Test Format jpeg",
            "created": dt(year=1990, month=8, day=1, hour=12, minute=0, second=2, tzinfo=cet)
        },
        "04_format.tiff": {
            "text": "Test Format tiff",
            "created": dt(year=1990, month=8, day=1, hour=12, minute=0, second=3, tzinfo=cet)
        }
    }

    # Create all files for the multi hash matching
    hash_matching_test = {
        "01_match_a.png": {
            "text": "Multi Hash Test, \nHash Match A",
            "created": dt(year=1990, month=9, day=1, hour=12, minute=0, second=0, tzinfo=cet)
        },
        "01_match_a_c1.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 1",
            "created": dt(year=1990, month=9, day=1, hour=12, minute=0, second=1, tzinfo=cet)
        },
        "01_match_a_c2.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 1\nChange 2",
            "created": dt(year=1990, month=9, day=1, hour=12, minute=0, second=2, tzinfo=cet)
        },
        "01_match_a_c3.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 1\nChange 2\nChange 3",
            "created": dt(year=1990, month=9, day=1, hour=12, minute=0, second=3, tzinfo=cet)
        },

        "02_match_a.png": {
            "text": "Multi Hash Test, \nHash Match A",
            "created": dt(year=1990, month=9, day=1, hour=13, minute=1, second=0, tzinfo=cet)
        },
        "02_match_a_c1.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 4",
            "created": dt(year=1990, month=9, day=1, hour=13, minute=1, second=1, tzinfo=cet)
        },
        "02_match_a_c2.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 4\nChange 5",
            "created": dt(year=1990, month=9, day=1, hour=13, minute=1, second=2, tzinfo=cet)
        },
        "02_match_a_c3.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 4\nChange 5\nChange 6",
            "created": dt(year=1990, month=9, day=1, hour=13, minute=1, second=3, tzinfo=cet)
        },

        "03_match_a.png": {
            "text": "Multi Hash Test, \nHash Match A",
            "created": dt(year=1990, month=9, day=1, hour=14, minute=1, second=0, tzinfo=cet)
        },
        "03_match_a_c1.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 7",
            "created": dt(year=1990, month=9, day=1, hour=14, minute=1, second=1, tzinfo=cet)
        },
        "03_match_a_c2.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 7\nChange 8",
            "created": dt(year=1990, month=9, day=1, hour=14, minute=1, second=2, tzinfo=cet)
        },
        "03_match_a_c3.png": {
            "text": "Multi Hash Test, \nHash Match A\nChange 7\nChange 8\nChange 9",
            "created": dt(year=1990, month=9, day=1, hour=14, minute=1, second=3, tzinfo=cet)
        },
    }

    hash_db_base_tests = {
        "01_match_a.png": hash_matching_test["01_match_a.png"],
        "02_match_a.png": hash_matching_test["02_match_a.png"],
        "03_match_a.png": hash_matching_test["03_match_a.png"],
    }

    hash_test_change_1 = {
        "01_match_a_c1.png": hash_matching_test["01_match_a_c1.png"],
        "02_match_a_c1.png": hash_matching_test["02_match_a_c1.png"],
        "03_match_a_c1.png": hash_matching_test["03_match_a_c1.png"],
    }

    hash_test_change_2 = {
        "01_match_a_c2.png": hash_matching_test["01_match_a_c2.png"],
        "02_match_a_c2.png": hash_matching_test["02_match_a_c2.png"],
        "03_match_a_c2.png": hash_matching_test["03_match_a_c2.png"],
    }

    hash_test_change_3 = {
        "01_match_a_c3.png": hash_matching_test["01_match_a_c3.png"],
        "02_match_a_c3.png": hash_matching_test["02_match_a_c3.png"],
        "03_match_a_c3.png": hash_matching_test["03_match_a_c3.png"],
    }

    # Create file structure
    for group_dir, f_dicts in files.items():
        base_dir = os.path.join(target_dir, "db", group_dir)
        create_files_from_dict(f_dicts, base_dir)

    # Create the directory for testing **allowed** imports.
    all_ext_base_dir = os.path.join(target_dir, "import_base_dir")
    create_files_from_dict(allowed_ext_test, all_ext_base_dir)

    # Create a files to test import matching
    import_match_dir = os.path.join(target_dir, "db", "import_matches")
    create_files_from_dict(import_matches, import_match_dir)

    # Create the directory for the source which should be matched against the db
    import_input_dir = os.path.join(target_dir, "import_match_source")
    create_files_from_dict(import_match_input, import_input_dir)

    # Create the directory for the database files for the hash matching test
    hash_db_base = os.path.join(target_dir, "db", "hash_matches")
    create_files_from_dict(arg_dict=hash_db_base_tests, tgt_dir=hash_db_base)

    # Create the directory for the first changes of the hash match files
    hash_c1_base = os.path.join(target_dir, "hash_change_1")
    create_files_from_dict(arg_dict=hash_test_change_1, tgt_dir=hash_c1_base)

    # Create the directory for the second changes of the hash match files
    hash_c1_base = os.path.join(target_dir, "hash_change_2")
    create_files_from_dict(arg_dict=hash_test_change_2, tgt_dir=hash_c1_base)

    # Create the directory for the third changes of the hash match files
    hash_c1_base = os.path.join(target_dir, "hash_change_3")
    create_files_from_dict(arg_dict=hash_test_change_3, tgt_dir=hash_c1_base)

    # Create directory for testing gps input and correct detection of file aware attribute
    import_test_dir = os.path.join(target_dir, "db", "import_aux_test")
    os.makedirs(import_test_dir, exist_ok=True)

    cd1 = datetime.datetime(year=1990, month=11, day=1, hour=12, minute=0, second=0, tzinfo=cet)
    cd2 = datetime.datetime(year=1990, month=11, day=1, hour=12, minute=0, second=1, tzinfo=cet)
    cd3 = datetime.datetime(year=1990, month=11, day=1, hour=12, minute=0, second=2, tzinfo=cet)
    cd4 = datetime.datetime(year=1990, month=11, day=1, hour=12, minute=0, second=3, tzinfo=cet)
    cd5 = datetime.datetime(year=1990, month=11, day=1, hour=12, minute=0, second=4, tzinfo=cet)

    create_image("Test File without any metadata",
                 created=cd1,
                 dst=os.path.join(import_test_dir, "10_no_metadata.jpg"),
                 tag_override={})

    create_image("Test File without any metadata",
                 created=cd2,
                 dst=os.path.join(import_test_dir, "20_gps_metadata.jpg"),
                 tag_override={"EXIF:GPSLatitude": 47.368650,
                               "EXIF:GPSLatitudeRef": "N",
                               "EXIF:GPSLongitude": 8.539183,
                               "EXIF:GPSLongitudeRef": "E",
                               "EXIF:GPSAltitude": 405,
                               "EXIF:GPSAltitudeRef": 0,
                               "EXIF:ModifyDate": cd2.strftime("%Y:%m:%d %H:%M:%S")})

    create_image("Test File with GPS 2, New York USA",
                 created=cd3,
                 dst=os.path.join(import_test_dir, "21_gps_metadata.jpg"),
                 tag_override={"EXIF:GPSLatitude": 40.730610,
                               "EXIF:GPSLatitudeRef": "N",
                               "EXIF:GPSLongitude": 73.935242,
                               "EXIF:GPSLongitudeRef": "W",
                               "EXIF:GPSAltitude": 22,
                               "EXIF:GPSAltitudeRef": 0,
                               "EXIF:ModifyDate": cd3.strftime("%Y:%m:%d %H:%M:%S")})

    create_image("Test File with GPS 3, La Serena Chile",
                 created=cd4,
                 dst=os.path.join(import_test_dir, "22_gps_metadata.jpg"),
                 tag_override={"EXIF:GPSLatitude": 29.90453,
                               "EXIF:GPSLatitudeRef": "S",
                               "EXIF:GPSLongitude": 71.24894,
                               "EXIF:GPSLongitudeRef": "W",
                               "EXIF:GPSAltitude": 405,
                               "EXIF:GPSAltitudeRef": 0,
                               "EXIF:ModifyDate": cd4.strftime("%Y:%m:%d %H:%M:%S")})

    create_image("Test File with GPS 4, Johannesburg",
                 created=cd5,
                 dst=os.path.join(import_test_dir, "23_gps_metadata.jpg"),
                 tag_override={"EXIF:GPSLatitude": 28.4792625,
                               "EXIF:GPSLatitudeRef": "S",
                               "EXIF:GPSLongitude": 24.6727135,
                               "EXIF:GPSLongitudeRef": "E",
                               "EXIF:GPSAltitude": 405,
                               "EXIF:GPSAltitudeRef": 0,
                               "EXIF:ModifyDate": cd5.strftime("%Y:%m:%d %H:%M:%S")})


