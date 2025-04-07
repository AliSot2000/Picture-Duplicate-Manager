import pydantic
from enum import Enum
from pydantic import BaseModel

"""
Contains the progress of an action runner during a long running action
"""


class TaskType(Enum):
    """
    List of all known tasks.
    """

class UIState:
    pass

class UIState(pydantic.BaseModel):
    current_task: TaskType
    progress: str | int


