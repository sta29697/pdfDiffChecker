from __future__ import annotations

import os
import json
from logging import getLogger
from typing import Any, Dict, List, TypedDict, Literal, Optional, TypeVar, overload, cast
from typing_extensions import Self
from configurations.message_manager import get_message_manager

# Determine tool_settings lazily to avoid circular imports
_helper_ts = __import__("configurations.tool_settings", fromlist=["DEFAULT_USER_SET","USER_SETTINGS_FILE"])  # noqa: E402
DEFAULT_USER_SET = _helper_ts.DEFAULT_USER_SET
USER_SETTINGS_FILE = _helper_ts.USER_SETTINGS_FILE


logger = getLogger(__name__)

T = TypeVar("T")


class WindowSettings(TypedDict, total=False):
    """Window settings type definition."""

    window_geometry: str
    window_width: int
    window_height: int
    window_position_x: int
    window_position_y: int
    base_file_graph_subwindow_geometry: str
    base_file_graph_subwindow_pos_x: int
    base_file_graph_subwindow_pos_y: int
    base_file_graph_subwindow_width: int
    base_file_graph_subwindow_height: int
    comparison_file_graph_subwindow_geometry: str
    comparison_file_graph_subwindow_pos_x: int
    comparison_file_graph_subwindow_pos_y: int
    comparison_file_graph_subwindow_width: int
    comparison_file_graph_subwindow_height: int


class FileSettings(TypedDict, total=False):
    """File settings type definition."""

    input_file_path: str
    comparison_file_path: str
    output_folder_path: str
    temp_dir_path: str


class DisplaySettings(TypedDict, total=False):
    """Display settings type definition."""

    theme_color: Literal["dark", "light", "pastel"]
    dpi: int
    setted_dpi: int
    setted_alpha: int
    separat_color_threshold: int
    dpi_list: List[int]
    language: Literal["japanese", "english"]


class SettingsMetaData(TypedDict):
    """Settings metadata type definition."""

    user_settings_status: Literal["default", "user_settings"]


class UserSettingsData(TypedDict, total=False):
    """User settings data type definition.

    Note: This is a flattened structure that matches the actual DEFAULT_USER_SET format,
    not a nested structure with window/file/display sections.
    """

    # Window settings
    window_geometry: str
    window_width: int
    window_height: int
    window_position_x: int
    window_position_y: int
    base_file_graph_subwindow_geometry: str
    base_file_graph_subwindow_pos_x: int
    base_file_graph_subwindow_pos_y: int
    base_file_graph_subwindow_width: int
    base_file_graph_subwindow_height: int
    comparison_file_graph_subwindow_geometry: str
    comparison_file_graph_subwindow_pos_x: int
    comparison_file_graph_subwindow_pos_y: int
    comparison_file_graph_subwindow_width: int
    comparison_file_graph_subwindow_height: int

    # File settings
    input_file_path: str
    comparison_file_path: str
    output_folder_path: str

    # Display settings
    theme_color: Literal["dark", "light", "pastel"]
    setted_dpi: int
    setted_alpha: int
    separat_color_threshold: int
    dpi_list: List[int]
    language: Literal["japanese", "english"]


class SettingsDict(TypedDict):
    """Complete settings dictionary type definition."""

    meta_data: SettingsMetaData
    default: UserSettingsData
    user_settings: Optional[UserSettingsData]


class UserSettingManager:
    """User settings manager class implementing the Singleton pattern.

    This class manages user settings throughout the application lifecycle.
    It provides methods to load, get, update, and save settings.
    Settings are stored in a JSON file and cached in memory for performance.

    The settings file has two main sections:
    1. "default": Contains default settings that are never modified
    2. "user_settings": Contains user-modified settings

    The active section is determined by the "user_settings_status" in the metadata.
    """

    _instance: Optional[Self] = None
    _user_settings: Dict[str, Any] = {}
    _settings_status: Literal["default", "user_settings"] = "default"

    def __new__(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        """Create a new instance of UserSettingManager using singleton pattern.

        This method ensures that only one instance of UserSettingManager exists
        throughout the application's lifecycle. When first called, it:
        1. Creates a new instance if none exists
        2. Initializes default settings
        3. Attempts to load user settings from file
        4. If loading fails, falls back to default settings
        5. Returns the instance

        Subsequent calls will return the existing instance without reloading settings.

        Returns:
            Self: Single instance of UserSettingManager
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._user_settings = DEFAULT_USER_SET.copy()
            cls._settings_status = "default"
            # Log that default user settings are initialized in memory
            logger.debug("Default user settings initialized in UserSettingManager")
            try:
                cls._load_user_settings()
            except Exception as e:
                # Log error during loading user settings and fallback to default
                logger.error(get_message_manager().get_error_message("E011", e))
                cls._user_settings = DEFAULT_USER_SET.copy()
                cls._settings_status = "default"
                # Log fallback to default settings due to loading error
                logger.debug(get_message_manager().get_log_message("L026"))
        return cast(Self, cls._instance)

    @classmethod
    def _load_user_settings(cls) -> None:
        """Load user settings from JSON file.

        The loading process follows these steps:
        1. Check if user_settings.json exists
        2. If file exists:
           - Read metadata to determine settings status
           - Load appropriate section based on status:
             * "user_settings": Load user-modified settings
             * "default": Load default settings from file
        3. If file doesn't exist or error occurs:
           - Use default settings from DEFAULT_USER_SET

        The loaded settings are stored in memory for quick access.
        """
        # Log settings file path and existence status
        logger.debug(f"User settings file: {USER_SETTINGS_FILE}, exists={os.path.exists(USER_SETTINGS_FILE)}")
        try:
            if os.path.exists(USER_SETTINGS_FILE):
                try:
                    with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                        file_settings = json.load(f)
                    # Log raw settings content preview (first 200 chars)
                    logger.debug(f"Raw settings content preview: {str(file_settings)[:200]}")

                    # Get status from metadata
                    status = file_settings.get("meta_data", {}).get(
                        "user_settings_status", "default"
                    )

                    # Load appropriate section based on status
                    if status == "user_settings":
                        # Use only the user_settings section from file
                        user_block = file_settings.get("user_settings", {})
                        cls._user_settings = {
                            "meta_data": {"user_settings_status": "user_settings"},
                            "user_settings": user_block,
                        }
                        cls._settings_status = "user_settings"
                    else:
                        # Use default section from file
                        cls._user_settings = {
                            "meta_data": {"user_settings_status": "default"},
                            "default": file_settings.get("default", {}),
                        }
                        cls._settings_status = "default"

                    # Log final determined status
                    logger.debug(f"Settings loading result: status={status}")

                    logger.debug(
                        get_message_manager().get_log_message(
                            "L023", cls._settings_status
                        )
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    # Log invalid format and fallback
                    logger.error(get_message_manager().get_error_message("E012", e))
                    cls._user_settings = DEFAULT_USER_SET.copy()
                    cls._settings_status = "default"
                    # Include file path and exception in log
                    logger.debug(get_message_manager().get_log_message("L024", USER_SETTINGS_FILE, e))
            else:
                # Use DEFAULT_USER_SET if file not found
                cls._user_settings = DEFAULT_USER_SET.copy()
                cls._settings_status = "default"
                # L025: User settings loaded from file successfully
                logger.debug(get_message_manager().get_log_message("L025"))
                # File not found fallback log
                logger.debug(f"User settings file not found at {USER_SETTINGS_FILE}, using default settings")
        except Exception as e:
            # E011: Error occurred while loading user settings from file
            logger.error(get_message_manager().get_error_message("E011", e))
            cls._user_settings = DEFAULT_USER_SET.copy()
            cls._settings_status = "default"
            # L026: Fallback to default settings due to loading error
            logger.debug(get_message_manager().get_log_message("L026"))

    @classmethod
    @overload
    def get_setting(cls, key: str) -> Any: ...

    @classmethod
    @overload
    def get_setting(cls, key: str, default_value: T) -> T: ...

    @classmethod
    def get_setting(cls, key: str, default_value: Any = None) -> Any:
        """Get a setting value by key.

        Args:
            key (str): Setting key
            default_value: Optional default value to return if key is not found

        Returns:
            Any: Setting value
        """
        section = (
            "user_settings" if cls._settings_status == "user_settings" else "default"
        )
        try:
            return cls._user_settings[section][key]
        except KeyError as e:
            logger.error(get_message_manager().get_log_message("L027", key, e))
            if default_value is not None:
                return default_value

            try:
                return DEFAULT_USER_SET["default"][key]
            except KeyError:
                return None

    @classmethod
    def get_setting_list(
        cls, key: str, default_value: Optional[List[Any]] = None
    ) -> List[Any]:
        """Get a list setting from the active settings section.

        Similar to get_setting, but specifically for list-type settings.
        This method ensures type safety for list settings.

        Args:
            key: Setting key to retrieve
            default_value: Optional default list to return if key is not found

        Returns:
            List of setting values
        """
        section = (
            "user_settings" if cls._settings_status == "user_settings" else "default"
        )
        try:
            value = cls._user_settings[section][key]
            if not isinstance(value, list):
                logger.warning(get_message_manager().get_log_message("L029", key))
                return [value]
            return value
        except KeyError as e:
            logger.error(get_message_manager().get_log_message("L027", key, e))
            try:
                value = DEFAULT_USER_SET["default"][key]
                if not isinstance(value, list):
                    logger.warning(get_message_manager().get_log_message("L030", key))
                    return [value]
                return value
            except KeyError:
                logger.warning(get_message_manager().get_log_message("L028", key))
                return default_value if default_value is not None else []

    @classmethod
    def update_setting(cls, key: str, value: Any) -> None:
        """Update a setting value in memory.

        This method updates a setting in the current active section based on _settings_status.
        If _settings_status is "default", it updates the default section.
        If _settings_status is "user_settings", it updates the user_settings section.

        Args:
            key: Setting key to update
            value: New value to set

        Raises:
            Exception: If the update operation fails
        """
        try:
            # Determine which section to update based on current status
            section = (
                "user_settings"
                if cls._settings_status == "user_settings"
                else "default"
            )

            # Create user_settings section if needed and status is user_settings
            if section == "user_settings" and "user_settings" not in cls._user_settings:
                cls._user_settings["user_settings"] = cls._user_settings[
                    "default"
                ].copy()

            # Update value in memory in the appropriate section
            cls._user_settings[section][key] = value
            logger.debug(
                get_message_manager().get_log_message("L031", key, value, section)
            )
        except Exception as e:
            logger.error(get_message_manager().get_error_message("E014", key, e))
            raise

    @classmethod
    def save_settings(cls) -> None:
        """Save current settings to file.

        This method is called when the save button is pressed.
        It performs the following steps:
        1. Creates user_settings section if it doesn't exist
        2. Changes status to user_settings
        3. Updates metadata to reflect the new status
        4. Saves all settings to the JSON file

        Raises:
            Exception: If the save operation fails
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(USER_SETTINGS_FILE), exist_ok=True)

            # Ensure user_settings section exists and contains current settings
            if "user_settings" not in cls._user_settings:
                # Copy settings from the current active section
                current_section = (
                    "default" if cls._settings_status == "default" else "user_settings"
                )
                cls._user_settings["user_settings"] = cls._user_settings[
                    current_section
                ].copy()

            # Change status to user_settings
            cls._settings_status = "user_settings"
            cls._user_settings["meta_data"]["user_settings_status"] = "user_settings"

            # Save to file
            with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._user_settings, f, indent=4, ensure_ascii=False)
            logger.debug(get_message_manager().get_log_message("L032"))
        except Exception as e:
            logger.error(get_message_manager().get_error_message("E013", e))
            raise

    @classmethod
    def get_settings_status(cls) -> Literal["default", "user_settings"]:
        """Get current settings status.

        Returns:
            str: Current settings status ("default" or "user_settings")
        """
        return cls._settings_status

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance.

        This method is primarily used for testing purposes to ensure
        that each test starts with a clean instance.
        """
        cls._instance = None
        cls._user_settings = {}
        cls._settings_status = "default"

    def get_current_theme(self) -> Dict[str, Any]:
        """Get the current theme data.

        Returns:
            Dict[str, Any]: Current theme data
        """
        return cast(Dict[str, Any], self.get_setting("theme_color"))


def get_user_setting_manager() -> UserSettingManager:
    """Get the singleton instance of UserSettingManager.

    Returns:
        UserSettingManager: The singleton instance
    """
    return UserSettingManager()
