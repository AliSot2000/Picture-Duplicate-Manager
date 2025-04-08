import photo_lib.dev_util as dev_util
from photo_lib.new_photo_api import PhotoAPI


def setup_populated_database():
    """
    Build database with valid data (not just example images)
    """
    # Remove previous version
    # import shutil
    # shutil.rmtree(dev_util.full_scratch_root)

    api = PhotoAPI(dev_util.real_world_scratch_root, init=True)

    for directory in dev_util.real_world_input_dirs:
        dir_table = api.prepare_directory_for_import(directory)

        api.db.debug_execute(f"UPDATE `{dir_table}` SET imported = 1 WHERE allowed = 1")

        res = api.perform_import(tbl_name=dir_table)
        print(res)


if __name__ == "__main__":
    setup_populated_database()