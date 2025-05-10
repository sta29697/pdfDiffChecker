from __future__ import annotations
import tkinter as tk
from typing import Any, Callable, Optional
from widgets.base_button import BaseButton
from configurations.message_manager import get_message_manager

class InsertBlankPageButton(BaseButton):
    """
    Button to insert a blank PNG page into either base or comp folder.
    Uses BaseButton for theme and MessageManager for i18n.
    If both images are visible ("base_and_comp"), then no insertion is performed,
    and a warning message is displayed to the user.
    """

    def __init__(
        self,
        master: tk.Frame,
        color_key: str,
        command: Optional[Callable[[], None]] = None,
        **kwargs: Any
    ) -> None:
        """
        Initialize the button for inserting blank pages.

        Args:
            master: Parent frame where this button will be placed
            color_key: Key for color theming
            command: Callback function when button is clicked
            **kwargs: Additional keyword arguments for tk.Button
        """
        message_manager = get_message_manager()
        label = message_manager.get_ui_message("U038")
        super().__init__(master, color_key=color_key, text=label, command=command, **kwargs)  # type: ignore[arg-type]
        # All theme/color handling is managed by BaseButton.
        # The button label is managed via MessageManager for i18n.
        self.__color_key = color_key
        # Apply the current theme to the button at initialization
        # Explicit theme application removed; managed globally

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Applies theme colors to the button.

        Args:
            theme_data (dict[str, Any]): Theme color data from ColorThemeManager. Accepts ThemeColors type or dict.
        """
        theme_settings = theme_data.get(self.__color_key, {})
        # Remove unsupported options before applying theme
        filtered = {k: v for k, v in {
            "fg": theme_settings.get("fg", "#27283a"),
            "bg": theme_settings.get("bg", "#22a9e9"),
            "activeforeground": theme_settings.get("activeforeground", "#574ed6"),
            "activebackground": theme_settings.get("activebackground", "#0fd2d6"),
            "disabledforeground": theme_settings.get("disabledforeground", "#27283a"),
            "disabledbackground": theme_settings.get("disabledbackground", "#22a9e9"),
        }.items() if k != "disabledbackground"}
        self._config_widget(filtered)

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Applies theme settings to the button widget.

        Args:
            theme_settings (dict[str, Any]): Theme settings to apply.
        """
        self.configure(**theme_settings)
