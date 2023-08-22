from PyQt6.QtWidgets import QPushButton
from photo_lib.gui.clickable_image import ClickableTile
from typing import Union, List, Callable


class MediaPane:
    pass


"""
Utility functions - namely wrapper functions to bake an argument into a function call for a signal.
"""
def bake_attribute(name: str, func: Callable):
    def baked_attribute_func(*args, **kwargs):
        return func(*args, name=name,**kwargs)

    return baked_attribute_func

# TODO test this
def general_wrapper(func: Callable, **bake_kwargs):
    """
    Given a function and then keyword arguments bakes the keyword arguments in the function call for a signal.

    :param func: function to decorate
    :param bake_kwargs: arguments to bake in
    :return:
    """
    def baked_argument_func(*args, **kwargs):
        return func(*args, **bake_kwargs, **kwargs)
    return baked_argument_func

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


def button_wrapper(btn: QPushButton, func: Callable):
    """
    This function is used to wrap the button that calls the function into the function so that one function can be
    used for many different buttons. Because Slots in QT don't communicate the caller of the function.

    :param btn: button that calls the function
    :param func: methode to execute that needs to have the button as a parameter
    :return:
    """
    def wrapper():
        return func(btn=btn)
    return wrapper


def pain_wrapper(media_pane: MediaPane, func: Callable):
    """
    This function is used to wrap the media pain that calls the function into the function so that one function can be
    used for many different buttons. Because Slots in QT don't communicate the caller of the function.

    :param media_pane: pain that calls the function
    :param func: methode to execute that needs to have the button as a parameter
    :return:
    """
    def wrapper():
        return func(media_pane=media_pane)
    return wrapper


def path_wrapper(path: str, func: Callable):
    """
    Given a path at time of creation, bakes the path into the function call since the function called in signals may not
    have any arguments.
    :param path: Path to bake in
    :param func: function to call with it
    :return:
    """
    def wrapper():
        return func(path=path)
    return wrapper