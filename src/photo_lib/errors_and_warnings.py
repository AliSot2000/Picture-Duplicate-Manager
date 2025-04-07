"""
This file contains custom Errors that are needed by the photo api.
"""


class DuplicateChainingError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class CorruptDatabase(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


# TODO to Exception
class NoDatabaseEntry(Warning):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class ImplementationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class KeyNotFound(Exception):
    def __init__(self, table: str, key: int, message: str = None):
        self.message = message
        self.tbl = table
        self.key = key

    def __str__(self):
        if self.message is not None:
            return f"Key: {self.key} not in {self.tbl}. {self.message}"

        return f"Key: {self.key} not in {self.tbl}"
