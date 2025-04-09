# pragma: no cover

"""
File contains variables and declarations needed to facilitate development. Please copy this file to dev_util.py
and populate the variables
"""
from photo_lib.custom_enum import TargetViewTable
from photo_lib.data_objects import MediaPaths, MediaElement

# Provide a list of directories which you would like to import into the real world database for testing.
real_world_input_dirs = [
    "<Fill-This-In>",
    "<Fill-This-In>",
    "<Fill-This-In>",
    "<Fill-This-In>",
    "<Fill-This-In>"
]

# Var provides a path to a library which contains actual data that can be viewed.
real_world_scratch_root = "<Fill-This-In>"


# Output directory where the files form the generate_dummy_media.py are stored
synthetic_file_out = "<Fill-This-In>"


# Path to where a library populated with the files generated with the generate_dummy_media.py is located
synthetic_scratch_root = "<Fill-This-In>"


# Provide a MediaPaths object with different paths for each scale (without a database to test image widgets)
different_default_media_paths: MediaPaths = ...


# Provide a MediaPaths object with the same picture at different sizes (without a database to test image widgets)
same_default_media_paths: MediaPaths = ...


# Provide a MediaPaths object that links to an element in the real_world_scratch_root. Ensure the import table exists.
import_media_paths: MediaPaths = MediaPaths(
    element=MediaElement(
        key=1,
        source_table=TargetViewTable.IMPORT,
        target_import_table=...
    ),
    original_fp="<Fill-This-In>",
    miniature_fp="<Fill-This-In>",
    thumbnail_fp="<Fill-This-In>",
)