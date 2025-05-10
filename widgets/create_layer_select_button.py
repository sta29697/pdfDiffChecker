from __future__ import annotations
import tkinter as tk
from typing import Any, Callable
from logging import getLogger
from widgets.base_button import BaseButton
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)

# Initialize singleton message manager
message_manager = get_message_manager()

class LayerSelectButton(BaseButton):
    def __init__(self, parent: tk.Frame, layer_number: int, command: Callable[[], None], color_key: str) -> None:
        """
        Initializes a LayerSelectButton instance.

        Args:
            parent: The parent widget.
            layer_number: The layer number to display.
            command: The command to execute when clicked.
            color_key: The key for theme color settings.
        """
        # UI text for layer select button
        label = message_manager.get_ui_message("U031") + f" {layer_number}"
        super().__init__(parent, color_key=color_key, text=label, command=command)
        self.layer_number = layer_number

    def configure(self, cnf: dict[str, Any] | str | None = None, **kwargs: Any) -> Any:
        """
        Configures the button with the given options. Signature matches tk.Button superclass.

        Args:
            cnf: Configuration dictionary, string, or None.
            **kwargs: Keyword arguments for configuration.
        Returns:
            Configuration dictionary or None.
        """
        return super().configure(cnf, **kwargs)

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Applies theme colors to the button.

        Args:
            theme_data: Theme color data from ColorThemeManager.
        """
        theme_settings = theme_data.get(self.__color_key, {})
        self._config_widget({
            "fg": theme_settings.get("fg", "#27283a"),
            "bg": theme_settings.get("bg", "#22a9e9"),
            "activeforeground": theme_settings.get("activeforeground", "#574ed6"),
            "activebackground": theme_settings.get("activebackground", "#0fd2d6"),
            "disabledforeground": theme_settings.get("disabledforeground", "#27283a"),
            "disabledbackground": theme_settings.get("disabledbackground", "#22a9e9"),
        })

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Applies theme settings to the button widget.

        Args:
            theme_settings (dict[str, Any]): Theme settings to apply.
        """
        self.configure(**theme_settings)
