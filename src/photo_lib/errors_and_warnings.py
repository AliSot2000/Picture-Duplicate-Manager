

class RareOccurrence(Warning):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


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


class NoDatabaseEntry(Warning):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)
