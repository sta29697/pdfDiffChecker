from __future__ import annotations
from logging import getLogger
import tkinter as tk
from typing import Any
from widgets.base_entry import BaseEntry
from configurations.message_manager import get_message_manager

# Initialize singleton message manager
message_manager = get_message_manager()

logger = getLogger(__name__)

class BaseEntryClass(BaseEntry):
    """
    Base class for all entry widgets in the application.
    """
    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        **kwargs: Any
    ) -> None:
        """
        Initialize the base entry class.

        Args:
            fr (tk.Frame): Parent frame.
            color_key (str): Key for theme color settings.
            **kwargs: Additional keyword arguments for tk.Entry.
        """
        super().__init__(fr, color_key=color_key, **kwargs)
        self.path_entry = self

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Apply theme colors to the entry.

        Args:
            theme_data (dict[str, Any]): Theme data to apply.
        """
        super().apply_theme_color(theme_data)

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Configure widget with theme settings.

        Args:
            theme_settings (dict[str, Any]): Theme settings to apply.
        """
        super()._config_widget(theme_settings)
