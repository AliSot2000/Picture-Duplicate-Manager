import skimage.color
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import cv2
import os
import time
import collections
from pathlib import Path
import argparse
import json
import warnings
from typing import Union
from concurrent.futures import ProcessPoolExecutor
warnings.filterwarnings('ignore')
import sqlite3


# TODO: -> compoare image aspect ration if not equal within certain range, disregard (not equal aspect ration cannot be
#  the same image)
# TODO: cupy -> GPU for numpy -> speedup of 4
# TODO: to detect compressed carbon copies, use precision reduction and small array and then perform hash to get sets on
#   which to perform O(n²) comparison
# TODO: improve mse function for faster computation.

def load_file(task_dict: dict):
    # check if the file is not a folder
    path = task_dict["path"]
    px_size = task_dict["size"]

    if not os.path.isdir(path):
        try:
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if type(img) == np.ndarray:
                img = img[..., 0:3]  # specifies only rgb is taken for every image even if there was an alpha channel
                img = cv2.resize(img, dsize=(px_size, px_size), interpolation=cv2.INTER_CUBIC)

                if len(img.shape) == 2:
                    img = skimage.color.gray2rgb(img)
                return True, path, img, ""
            else:
                return False, path, None, "Image not of type np.ndarray"
        except Exception as e:
            return False, path, None, e.__str__()
    else:
        return False, path, None, "Path is dir"


class dif:
    __dir_a: str
    __dir_b: Union[str, None] = None
    __similarity: float
    __px_size: int
    __show_prog: bool
    __show_out: bool
    __delete: bool
    __silent: bool

    dir_a_content: list
    dir_b_content: list

    # ------------------------------------------------------------------------------------------------------------------
    # Properties and type checking -------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------
    # String type properties -------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def dir_a(self):
        return self.__dir_a

    @dir_a.setter
    def dir_a(self, value):
        if type(value) is not str:
            raise TypeError("directory_A needs to be of type string")
        self.__dir_a = value

    @property
    def dir_b(self):
        return self.__dir_b

    @dir_b.setter
    def dir_b(self, value):
        if type(value) is not str and value is not None:
            raise TypeError("directory_B needs to be of type string")
        self.__dir_b = value

    # ------------------------------------------------------------------------------------------------------------------
    # Bool type properties ---------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def show_prog(self):
        return self.__show_prog

    @show_prog.setter
    def show_prog(self, value):
        if type(value) is not bool:
            raise TypeError("show_progress needs to be of type bool")
        self.__show_prog = value

    @property
    def show_out(self):
        return self.__show_prog

    @show_out.setter
    def show_out(self, value):
        if type(value) is not bool:
            raise TypeError("show_output needs to be of type bool")
        self.__show_out = value

    @property
    def delete(self):
        return self.__delete

    @delete.setter
    def delete(self, value):
        if type(value) is not bool:
            raise TypeError("delete needs to be of type bool")
        self.__delete = value

    @property
    def silent_del(self):
        return self.__silent

    @silent_del.setter
    def silent_del(self, value):
        if type(value) is not bool:
            raise TypeError("silent_delete needs to be of type bool")
        self.__silent = value

    # ------------------------------------------------------------------------------------------------------------------
    # Number type properties -------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def px_size(self):
        return self.__px_size

    @px_size.setter
    def px_size(self, value):
        if type(value) is not int:
            raise TypeError("px_size needs to be of type int")
        if not (10 < value < 5000):
            raise ValueError("px_size exceedingly large")
        self.__px_size = value

    @property
    def similarity(self):
        return self.__similarity

    @similarity.setter
    def similarity(self, value):
        if type(value) is str:
            if value not in ("high", "low", "normal"):
                raise ValueError("Supported names are 'high', 'normal' and 'low'")
            if value == "low":
                ref = 1000
            # search for exact duplicate images, extremly sensitive, MSE < 0.1
            elif value == "high":
                ref = 0.1
            # normal, search for duplicates, recommended, MSE < 200
            else:
                ref = 200

        # assuming it is float type
        else:
            try:
                ref = float(value)
            except ValueError:
                raise ValueError("Invalid argument for similarity, either 'low', 'normal', 'high' or a float")

        self.__similarity = value

    # ------------------------------------------------------------------------------------------------------------------
    # Static Util ------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def recursive_list_dir(path: str):
        """
        Recursively lists a directory and returns a list of all files that are in the directory.
        :param path: root path from which to start listing
        :return:
        """
        if path is None:
            return None

        def __rec_list(rp, results):
            sub = os.scandir(rp)
            for f in sub:
                np = os.path.join(rp, f)
                if os.path.isfile(np):
                    results.append(np)
                elif os.path.isdir(np):
                    __rec_list(np, results)

        res = []
        __rec_list(path, res)
        return res

    def generate_dict_list(self, attrib: str):
        file_list = getattr(self, attrib)
        return [{"path": f, "size": self.px_size} for f in file_list]

    # ------------------------------------------------------------------------------------------------------------------
    # Main Functions ---------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def __init__(self, directory_A: Union[str, list], directory_B: Union[str, list] = None,
                 similarity: Union[str, int] = "normal", px_size: int = 50, show_progress: bool = True,
                 show_output: bool = False, delete: bool = False, silent_del: bool = False, **kwargs):
        """
        directory_A (str)........folder path to search for duplicate/similar images
        directory_B (str)........second folder path to search for duplicate/similar images
        similarity (str, int)...."normal" = searches for duplicates, recommended setting, MSE < 200
                                 "high" = serached for exact duplicates, extremly sensitive to details, MSE < 0.1
                                 "low" = searches for similar images, MSE < 1000
                                 or any int, which will be used as MSE threshold for comparison
        px_size (int)............recommended not to change default value
                                 resize images to px_size height x width (in pixels) before being compared
                                 the higher the pixel size, the more computational ressources and time required
        show_progress (bool).....True = shows progress stats of where your lengthy processing currently is
                                 False = doesn't show the progress stats
        show_output (bool).......False = omits the output and doesn't show found images
                                 True = shows duplicate/similar images found in output
        delete (bool)............! please use with care, as this cannot be undone
                                 lower resolution duplicate images that were found are automatically deleted
        silent_del (bool)........! please use with care, as this cannot be undone
                                 True = skips the asking for user confirmation when deleting lower resolution duplicate images
                                 will only work if "delete" AND "silent_del" are both == True

        OUTPUT (set).............a dictionary with the filename of the duplicate images
                               and a set of lower resultion images of all duplicates

        *** CLI-Interface ***
        dif.py [-h] -A DIRECTORY_A [-B [DIRECTORY_B]] [-Z [OUTPUT_DIRECTORY]] [-s [{low,normal,high}]] [-px [PX_SIZE]]
               [-p [{True,False}]] [-o [{True,False}]] [-d [{True,False}]] [-D [{True,False}]]

        OUTPUT.................output data is written to files and saved in the working directory
                               difPy_results_xxx_.json
                               difPy_lower_quality_xxx_.txt
                               difPy_stats_xxx_.json
        """
        self.a_img_mat: Union[list, None] = None
        self.b_img_mat: Union[list, None] = None
        self.a_fail_list: Union[list, None] = None
        self.b_fail_list: Union[list, None] = None

        # Setting object attributes
        self.dir_a = directory_A
        self.dir_b = directory_B
        self.similarity = similarity
        self.px_size = px_size
        self.show_prog = show_progress
        self.show_out = show_output
        self.delete = delete
        self.silent_del = silent_del
        self.dir_a_content = kwargs.get("list_a")
        self.dir_b_content = kwargs.get("list_b")

        start_time = time.time()
        if self.show_prog:
            print("DifPy process initializing...", end="\r")

        # list both directories, dir a and dir b
        if self.dir_a_content is None:
            self.dir_a_content = self.recursive_list_dir(self.dir_a)

        if self.dir_b_content is None:
            self.dir_b_content = self.recursive_list_dir(self.dir_b)

        # process directory
        self._create_imgs_matrix()
        if self.dir_b_content is not None:
            self._create_imgs_matrix(is_b=True)
        result, lower_quality, total = dif._search_one_dir(img_matrices_A, folderfiles_A,
                                                           ref, show_output, show_progress)

        end_time = time.time()
        time_elapsed = np.round(end_time - start_time, 4)
        stats = dif._generate_stats(directory_A, directory_B,
                                    time.localtime(start_time), time.localtime(end_time), time_elapsed,
                                    similarity, total, len(result))


        self.result = result
        self.lower_quality = lower_quality
        self.stats = stats

        if len(result) == 1:
            images = "image"
        else:
            images = "images"
        print("Found", len(result), images, "with one or more duplicate/similar images in", time_elapsed, "seconds.")

        if len(result) != 0:
            # optional delete images
            if delete:
                if not silent_del:
                    usr = input(
                        "Are you sure you want to delete all lower resolution duplicate images? \nThis cannot be undone. (y/n)")
                    if str(usr) == "y":
                        dif._delete_imgs(set(lower_quality))
                    else:
                        print("Image deletion canceled.")
                else:
                    dif._delete_imgs(set(lower_quality))

    # Function that creates a list of matrices for each image found in the folders
    def _create_imgs_matrix(self, is_b:bool = False):
        # create images matrix and task list
        attr = "dir_b_content" if is_b else "dir_a_content"
        task_list = self.generate_dict_list(attr)

        # if else, because we don't want to reset the content of the a_list if it is already computed.
        if is_b:
            self.b_img_mat = []
            mat = self.b_img_mat
            self.b_fail_list = []
            fail = self.b_fail_list
        else:
            self.a_img_mat = []
            mat = self.a_img_mat
            self.a_fail_list = []
            fail = self.a_fail_list

        # initialise parallel execution stuff
        executor = ProcessPoolExecutor()
        it = executor.map(load_file, task_list, chunksize=10)

        for result in it:
            if result[0]:
                mat.append((result[1], result[2]))
            else:
                fail.append(result[1])
                if self.show_prog:
                    print(f"Failed to process: {result[1]}")

    # Function that searches one directory for duplicate/similar images
    def _search_one_dir(self):
        total = len(self.a_img_mat)
        result = {}
        lower_quality = []

        if self.b_img_mat is None:
            self.dir_b_content = self.dir_a_content

        for count_A, imageMatrix_A in enumerate(img_matrices_A):
            img_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
            while img_id in result.keys():
                img_id = str(int(img_id) + 1)
            for count_B, imageMatrix_B in enumerate(img_matrices_A):
                if count_B > count_A and count_A != len(img_matrices_A):
                    rotations = 0
                    while rotations <= 3:
                        if rotations != 0:
                            imageMatrix_B = dif._rotate_img(imageMatrix_B)

                        err = dif._mse(imageMatrix_A, imageMatrix_B)
                        if err < ref:
                            if show_output:
                                dif._show_img_figs(imageMatrix_A, imageMatrix_B, err)
                                dif._show_file_info(Path(folderfiles_A[count_A][0]) / folderfiles_A[count_A][1],
                                                    # 0 is the path, 1 is the filename
                                                    Path(folderfiles_A[count_B][0]) / folderfiles_A[count_B][1])
                            if img_id in result.keys():
                                result[img_id]["duplicates"] = result[img_id]["duplicates"] + [
                                    str(Path(folderfiles_A[count_B][0]) / folderfiles_A[count_B][1])]
                            else:
                                result[img_id] = {'filename': str(folderfiles_A[count_A][1]),
                                                  'location': str(
                                                      Path(folderfiles_A[count_A][0]) / folderfiles_A[count_A][1]),
                                                  'duplicates': [
                                                      str(Path(folderfiles_A[count_B][0]) / folderfiles_A[count_B][1])]}
                            try:
                                high, low = dif._check_img_quality(
                                    Path(folderfiles_A[count_A][0]) / folderfiles_A[count_A][1],
                                    Path(folderfiles_A[count_B][0]) / folderfiles_A[count_B][1])
                                lower_quality.append(str(low))
                            except:
                                pass
                            break
                        else:
                            rotations += 1

        result = collections.OrderedDict(sorted(result.items()))
        lower_quality = list(set(lower_quality))

        return result, lower_quality, total

    # Function that calulates the mean squared error (mse) between two image matrices
    @staticmethod
    def _mse(imageA, imageB):
        err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
        err /= float(imageA.shape[0] * imageA.shape[1])
        return err

    # Function that plots two compared image files and their mse
    def _show_img_figs(imageA, imageB, err):
        fig = plt.figure()
        plt.suptitle("MSE: %.2f" % (err))
        # plot first image
        ax = fig.add_subplot(1, 2, 1)
        plt.imshow(imageA, cmap=plt.cm.gray)
        plt.axis("off")
        # plot second image
        ax = fig.add_subplot(1, 2, 2)
        plt.imshow(imageB, cmap=plt.cm.gray)
        plt.axis("off")
        # show the images
        plt.show()

    # Function for printing filename info of plotted image files
    def _show_file_info(imageA, imageB):
        imageA = "..." + str(imageA)[-45:]
        imageB = "..." + str(imageB)[-45:]
        print(f"""Duplicate files:\n{imageA} and \n{imageB}\n""")

    # Function for rotating an image matrix by a 90 degree angle
    def _rotate_img(image):
        image = np.rot90(image, k=1, axes=(0, 1))
        return image

    # Function for checking the quality of compared images, appends the lower quality image to the list
    def _check_img_quality(imageA, imageB):
        size_imgA = os.stat(imageA).st_size
        size_imgB = os.stat(imageB).st_size
        if size_imgA >= size_imgB:
            return imageA, imageB
        else:
            return imageB, imageA

    # Function that displays a progress bar during the search
    def _show_progress(count, list, task='processing images'):
        if count + 1 == len(list):
            print(f"DifPy {task}: [{count}/{len(list)}] [{count / len(list):.0%}]", end="\r")
            print(f"DifPy {task}: [{count + 1}/{len(list)}] [{(count + 1) / len(list):.0%}]")
        else:
            print(f"DifPy {task}: [{count}/{len(list)}] [{count / len(list):.0%}]", end="\r")

    # Function for deleting the lower quality images that were found after the search
    def _delete_imgs(lower_quality_set):
        deleted = 0
        # delete lower quality images
        for file in lower_quality_set:
            print("\nDeletion in progress...", end="\r")
            try:
                os.remove(file)
                print("Deleted file:", file, end="\r")
                deleted += 1
            except:
                print("Could not delete file:", file, end="\r")
        print("\n***\nDeleted", deleted, "images.")


def type_str_int(x):
    try:
        return int(x)
    except:
        return x


# Parameters for when launching difPy via CLI
if __name__ == "__main__":
    # set CLI arguments
    parser = argparse.ArgumentParser(
        description='Find duplicate or similar images on your computer with difPy - https://github.com/elisemercury/Duplicate-Image-Finder')
    parser.add_argument("-A", "--directory_A", type=str, help='Directory to search for images.', required=True)
    parser.add_argument("-B", "--directory_B", type=str, help='(optional) Second directory to search for images.',
                        required=False, nargs='?', default=None)
    parser.add_argument("-Z", "--output_directory", type=str,
                        help='(optional) Output directory for the difPy result files. Default is working dir.',
                        required=False, nargs='?', default=None)
    parser.add_argument("-s", "--similarity", type=type_str_int, help='(optional) Similarity grade.', required=False,
                        nargs='?', default='normal')
    parser.add_argument("-px", "--px_size", type=int, help='(optional) Compression size of images in pixels.',
                        required=False, nargs='?', default=50)
    parser.add_argument("-p", "--show_progress", type=bool, help='(optional) Shows the real-time progress of difPy.',
                        required=False, nargs='?', choices=[True, False], default=True)
    parser.add_argument("-o", "--show_output", type=bool, help='(optional) Shows the comapred images in real-time.',
                        required=False, nargs='?', choices=[True, False], default=False)
    parser.add_argument("-d", "--delete", type=bool, help='(optional) Deletes all duplicate images with lower quality.',
                        required=False, nargs='?', choices=[True, False], default=False)
    parser.add_argument("-D", "--silent_del", type=bool,
                        help='(optional) Supresses the user confirmation when deleting images.', required=False,
                        nargs='?', choices=[True, False], default=False)
    args = parser.parse_args()

    # initialize difPy
    search = dif(directory_A=args.directory_A, directory_B=args.directory_B,
                 similarity=args.similarity, px_size=args.px_size,
                 show_output=args.show_output, show_progress=args.show_progress,
                 delete=args.delete, silent_del=args.silent_del)

    # create filenames for the output files
    timestamp = str(time.time()).replace(".", "_")
    result_file = "difPy_results_" + timestamp + ".json"
    lq_file = "difPy_lower_quality_" + timestamp + ".txt"
    stats_file = "difPy_stats_" + timestamp + ".json"

    if args.output_directory != None:
        dir = args.output_directory
    else:
        dir = os.getcwd()

    if not os.path.exists(dir):
        os.makedirs(dir)

    with open(os.path.join(dir, result_file), "w") as file:
        json.dump(search.result, file)

    with open(os.path.join(dir, lq_file), "w") as file:
        file.writelines(search.lower_quality)

    with open(os.path.join(dir, stats_file), "w") as file:
        json.dump(search.stats, file)

    print(f"""\nSaved difPy results into folder {dir} and filenames:\n{result_file} \n{lq_file} \n{stats_file}""")