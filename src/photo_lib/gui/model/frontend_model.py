from photo_lib.new_photo_api import PhotoAPI
from typing import Optional
from multiprocessing.connection import Connection
from .frontend_config import UIConfig
from .frontend_preferences import UIUserPreferences
from .frontend_state import UIState
import photo_lib.defaults as defaults


"""
Root Model for new database backend.
Contains:
- The API Instance
- The state for long-running operations of the database
- The config for the UI
- The 'remember' states of the front end
"""


class UIModel:
    """
    The Model Containing all shared information throughout the frontend.
    """
    api: Optional[PhotoAPI] = None
    runner_connection: Optional[Connection] = None

    ui_preferences: UIUserPreferences
    ui_config: UIConfig
    ui_state: UIState

    def __init__(self,
                 preferences: UIUserPreferences = None,
                 ui_config: UIConfig = None,
                 ui_state: UIState = None,
                 api: PhotoAPI = None,
                 runner_connection: Connection = None):
        """
        Build the UIModel
        """
        if preferences is None or ui_state is None or ui_state is None:
            raise NotImplementedError("Loading from system paths not implemented")

        self.ui_preferences = preferences
        self.ui_config = ui_config
        self.ui_state = ui_state

        self.api = api
        self.runner_connection = runner_connection

    @property
    def thumbnail_size(self):
        """
        This property is needed by the ImageWidgets (which might still be instantiated, so it may not be None) to
        determine which file to load for displaying
        """
        if self.api is not None:
            return self.api.config.thumbnail_target

        else:
            return defaults.thumbnail_size

    @property
    def miniature_size(self):
        """
        This property is needed by the ImageWidgets (which might still be instantiated, so it may not be None)
        determine which file to load for displaying
        """
        if self.api is not None:
            return self.api.config.miniature_target

        else:
            return defaults.miniature_size
