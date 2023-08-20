from photo_lib.gui.clickable_image import ClickableTile
from typing import Union, List, Callable


"""
Utility functions - namely wrapper functions to bake an argument into a function call for a signal.
"""


def image_wrapper(image: ClickableTile, fn: Callable):
    """
    Given a function and a tile, bake tile as argument into function call for signal.
    :param image: tile to bake in
    :param fn: function to call
    :return:
    """
    def wrapper():
        fn(image=image)
    return wrapper