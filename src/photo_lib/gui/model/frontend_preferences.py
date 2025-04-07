from pydantic import BaseModel


"""
Contains the last states the user left things in. E.g. for the session. Only provides the user with the clear cache
"""


class UIUserPreferences(BaseModel):
    """
    Contains shorthands (basically things the way the user left them so they are picked up correctly again.
    """
    ...