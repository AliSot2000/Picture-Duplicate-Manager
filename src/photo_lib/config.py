from pydantic import BaseModel
from typing import Union

# TODO implement config

class Config(BaseModel):
    exiftool: Union[str, None]
