from __future__ import annotations
from logging import getLogger
import tkinter as tk
from typing import Any, Callable

from widgets.base_button import BaseButton
from controllers.widgets_tracker import WidgetsTracker
from configurations.message_manager import get_message_manager

# Initialize singleton message manager
message_manager = get_message_manager()

logger = getLogger(__name__)

class ConvertImageButton(BaseButton):
    """Button that triggers the convert image action in ImageOperationApp."""
    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        text: str,
        command: Callable[[], Any],
        **kwargs: Any,
    ) -> None:
        """Initialize the convert image button.

        Args:
            fr: Parent frame.
            color_key: Theme color key.
            text: Button label text.
            command: Callback function for image conversion.
            **kwargs: Additional tk.Button kwargs.
        """
        # Initialize base button
        super().__init__(fr=fr, color_key=color_key, text=text, command=command, **kwargs)
        # Register widget for theme updates
        WidgetsTracker().add_widgets(self)
        # Log initialization of ConvertImageButton with color key
        logger.debug(message_manager.get_log_message("L176", color_key))

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Applies theme colors to the button.

        Args:
            theme_data (dict[str, Any]): Theme color data from ColorThemeManager. Accepts ThemeColors type or dict.
        """
        theme_settings = theme_data.get(self.__color_key, {})
        self._config_widget({
            "fg": theme_settings.get("fg", "#43c0cd"),
            "bg": theme_settings.get("bg", "#1d1d29"),
            "activeforeground": theme_settings.get("activeforeground", "#574ed6"),
            "activebackground": theme_settings.get("activebackground", "#0fd2d6"),
            "disabledforeground": theme_settings.get("disabledforeground", "#27283a"),
            "disabledbackground": theme_settings.get("disabledbackground", "#22a9e9"),
        })

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """Applies theme settings to the button widget.

        Args:
            theme_settings: Theme settings to apply.
        """
        self.configure(**theme_settings)
