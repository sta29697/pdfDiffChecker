from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from logging import getLogger
from typing import Any, Dict, List, Optional, Union

from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from utils.utils import get_resource_path
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets as btw
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()


class BaseValueCombobox(ttk.Combobox, ThemeColorApplicable, ColoringThemeIF):
    """Base class for value selection comboboxes.

    This class provides base functionality for comboboxes that:
    1. Handle value selection (e.g., DPI, file size)
    2. Support theme color application
    3. Manage value validation and updates
    """

    def __init__(
        self,
        master: tk.Widget,
        color_key: str,
        values: List[Union[str, int, float]],
        default_value: Optional[Union[str, int, float]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the value combobox.

        Args:
            master: Parent widget
            color_key: Key for theme color application
            values: List of available values
            default_value: Default selected value
            **kwargs: Additional keyword arguments for ttk.Combobox
        """
        super().__init__(master, **kwargs)
        self.__color_key = color_key
        self.__values = values
        self.__default_value = default_value

        # Convert all values to strings
        str_values = [str(value) for value in values]

        # Configure combobox
        self.configure(
            values=str_values,
            font=btw.base_font,
            state="readonly",
        )

        # Set default value if provided
        if default_value is not None:
            self.set(str(default_value))

        # Register for theme updates
        WidgetsTracker().add_widgets(self)
        # BaseValueCombobox initialized with values: {values}
        # logger.debug(message_manager.get_log_message("L112", values))

    def get_value(self) -> Union[str, int, float]:
        """Get the current selected value.

        Returns:
            Union[str, int, float]: Selected value
        """
        value = self.get()
        # Try to convert back to original type
        for original_value in self.__values:
            if str(original_value) == value:
                return original_value
        return value

    def set_value(self, value: Union[str, int, float]) -> None:
        """Set the selected value.

        Args:
            value: Value to set
        """
        str_value = str(value)
        if str_value in [str(v) for v in self.__values]:
            self.set(str_value)
            # Value set to: {value}
            # logger.debug(message_manager.get_log_message("L113", value))
        else:
            # Invalid value: {value}
            # logger.warning(message_manager.get_log_message("L114", value))
            pass

    def apply_theme_color(self, theme_data: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the combobox.

        Args:
            theme_data: Dictionary containing theme color data
        """
        try:
            combobox_theme_config = theme_data.get(self.__color_key, {})
            self.configure(**combobox_theme_config)
            if self.__color_key in {"base_file_path_entry", "filename_label"}:
                logger.debug(
                    f"[COMBO_THEME] color_key={self.__color_key}, config={combobox_theme_config}, "
                    f"widget_id={id(self)}, state={self.cget('state')}"
                )
        except Exception as e:
            # Failed to apply theme to combobox: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Dictionary containing theme settings
        """
        try:
            self.configure(**theme_settings)
            # Configured combobox with settings: {settings}
            # logger.debug(message_manager.get_log_message("L116", theme_settings))
        except Exception as e:
            # Failed to configure combobox: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
