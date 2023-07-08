import datetime
import os.path
from typing import List, Union, Tuple
import multiprocessing as mp

from photo_lib.PhotoDatabase import PhotoDb, DatabaseEntry
from photo_lib.metadataagregator import key_lookup_dir


class NoDbException(Exception):
    """
    To make handling of returned values easier, we use an exception to indicate that there's not database loaded.
    """
    pass


class Model:
    pdb:  Union[PhotoDb, None] = None
    files: List[DatabaseEntry]
    current_row: Union[int, None] = None
    search_level: Union[str, None] = None
    resources: str = os.path.join(os.path.dirname(__file__), "resources")

    def __init__(self, folder_path: str = None):
        if folder_path is not None:
            self.pdb = PhotoDb(root_dir=folder_path)

    def set_folder_path(self, folder_path: str):
        """
        Wrapper function in case more logic is needed in the future.
        :param folder_path: path to the database
        :return:
        """
        if os.path.exists(os.path.join(folder_path, ".photos.db")):
            self.pdb = PhotoDb(root_dir=folder_path)

    @staticmethod
    def process_metadata(metadict: dict):
        """
        Parse the Metadata dict and convert it into a text string that can be displayed.

        :param metadict: dictionary of metadata, generated by the exiftool

        :return: metadata string, file size string
        """
        keys = metadict.keys()
        key_list = list(keys)
        key_list.sort()
        file_size = ""

        result = f"Number of Attributes: {len(key_list)}\n"

        for key in key_list:
            result += f"{key}: {metadict.get(key)}\n"
            if key == "File:FileSize":
                file_size = f"File Size: {int(metadict.get(key)):,}".replace(",", "'")

        return result, file_size

    def try_rename_image(self, tag: str, dbe: DatabaseEntry, custom_datetime: str = None):
        """
        Perform the renaming logic on the badkend. This will update the database entry, and rename the file.
        :param tag: new tag to be used for datetime
        :param dbe: databse entry
        :param custom_datetime: the custom datetime string, if tag is "custom"
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if tag.strip().lower() == "custom":
            tag = "Custom"
            new_datetime = datetime.datetime.strptime(custom_datetime, "%Y-%m-%d %H.%M.%S")

        else:
            parsing_function = key_lookup_dir.get(tag)

            if parsing_function is None:
                raise ValueError(f"Tag {tag} does not have a matching parsing function.")

            new_datetime, key = parsing_function(dbe.metadata)

        if new_datetime == dbe.datetime:
            print("Equivalent Datetime, exiting")
            return

        # print(new_datetime)

        # Update the Database entry
        dbe.new_name = self.pdb.rename_file(entry=dbe, new_datetime=new_datetime, naming_tag=tag)
        dbe.datetime = new_datetime
        dbe.naming_tag = tag

    def fetch_duplicate_row(self):
        """
        Fetch the current row from the database.
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        success, results, row_id = self.pdb.get_duplicate_entry()
        if success:
            self.files = results
            self.current_row = row_id

        return success

    def compare_current_files(self):
        """
        Compare access all available files and determine the areas of similarity.

        - identical_binary: If (all) files are identical on a binary level
        - identical_names: If all files have the same original name
        - identical_datetime: If all files have the same datetime
        - identical_file_size: If all files have the same file size
        - difference: The average difference in file size between all files

        :return: identical_binary, identical_names, identical_datetime, identical_file_size, difference
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if len(self.files) == 0 or self.files is None:
            return None

        # compare the files
        identical_binary = True
        for i in range(1, len(self.files)):
            if self.files[i] is not None and self.files[0] is not None:
                suc, msg = self.pdb.compare_files(self.files[i].key, self.files[0].key)
                if suc is None:
                    print(msg)
                identical_binary = identical_binary and suc

        # compare the filenames
        identical_names = True
        for i in range(1, len(self.files)):
            if self.files[i] is not None and self.files[0] is not None:
                identical_names = identical_names and self.files[i].org_fname.lower() == self.files[0].org_fname.lower()

        identical_datetime = True
        for i in range(1, len(self.files)):
            if self.files[i] is not None and self.files[0] is not None:
                identical_datetime = identical_datetime and self.files[i].datetime == self.files[0].datetime

        identical_file_size = True
        difference = 0
        count = 0
        # All to all comparison of the file size
        for i in range(len(self.files)):
            for j in range(i + 1, len(self.files)):
                if self.files[i] is not None and self.files[j] is not None:
                    identical_file_size = identical_file_size and \
                                          self.files[i].metadata.get("File:FileSize") \
                                          == self.files[j].metadata.get("File:FileSize")
                    difference += (self.files[i].metadata.get("File:FileSize")
                                   - self.files[j].metadata.get("File:FileSize")) ** 2
                    count += 1

        if count > 0:
            print(f"Average Difference {(difference ** 0.5) / count}")
            difference = (difference ** 0.5) / count

        return identical_binary, identical_names, identical_datetime, identical_file_size, difference

    def clear_files(self):
        """
        Clear the files list of the current model.

        => Future proofing...
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        self.files = []
        self.pdb.delete_duplicate_row(self.current_row)
        self.current_row = None

    def remove_file(self, dbe: DatabaseEntry):
        """
        Remove a file from the current selection of present files.

        => Future proofing...
        :return:
        """
        self.files.remove(dbe)

    def mark_duplicates(self, original: DatabaseEntry, duplicates: List[DatabaseEntry]):
        """
        Mark the duplicates as such in the database.

        :param original: The original file
        :param duplicates: The list of duplicates
        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        main_key = original.key
        print(f"Keeping: {original.new_name}")

        for marks in duplicates:
            print(f"Marking: {marks.new_name}")
            marks: DatabaseEntry
            self.pdb.mark_duplicate(successor=main_key, duplicate_image_id=marks.key, delete=False)

    def search_duplicates(self) -> Tuple[bool, mp.Pipe]:
        """
        Search for duplicates in the database.

        :return:
        """
        if self.pdb is None:
            raise NoDbException("No Database selected")

        if self.search_level == "hash":
            self.pdb.duplicates_from_hash(overwrite=True)
            return True, None

        # Other thing
        # success, pipe = self.pdb.img_ana_dup_search(overwrite=True, level=self.search_level)
        success, pipe = self.pdb.img_ana_dup_search(overwrite=True, level=self.search_level, new=False)

        if not success:
            print(pipe)
            return False, None

        return True, pipe


