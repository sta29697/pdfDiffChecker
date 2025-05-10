from __future__ import annotations

import tkinter as tk
from logging import getLogger
from typing import Literal, Dict, Any, Callable, Optional, cast

from configurations.tool_settings import DEFAULT_COLOR_THEME_SET
from configurations.user_setting_manager import UserSettingManager
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from utils.utils import get_resource_path
from widgets.base_tab_widgets import BaseTabWidgets as btw
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()


class BaseImageDisplayToggleButton(ColoringThemeIF, ThemeColorApplicable):
    """
    A reusable toggle button class for base or comp image visibility.

    This class provides base functionality for buttons that:
    1. Toggle image display
    2. Support theme color application
    3. Handle image visibility events
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        callback: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        fr: parent frame
        color_key: color key name
        callback: function to call when toggled -> callback(image_type, new_state)
        """
        self.__fr = fr
        self.__color_key = color_key

        if "base" in self.__color_key:
            self.__image_type = "base"
        elif "comparison" in self.__color_key:
            self.__image_type = "comp"

        self.__callback = callback
        self.__visible: bool = False

        # Acquire theme color from ColorThemeManager
        try:
            self.__color_theme_manager = ColorThemeManager()
            current_theme = self.__color_theme_manager.get_current_theme()
            self.__theme_dict = cast(
                Dict[str, Any], current_theme.get(self.__color_key, {})
            )
        except Exception as e:
            # Failed to get theme color: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            self.__theme_dict = DEFAULT_COLOR_THEME_SET.get(self.__color_key, {})

        # Base color settings
        self.__swfg = self.__theme_dict.get("base_font_color", "#43c0cd")
        self.__swbg = self.__theme_dict.get("base_bg_color", "#1d1d29")
        self.__fg = self.__theme_dict.get("button_inactive_font_color", "#27283a")
        self.__bg = self.__theme_dict.get("button_inactive_bg_color", "#22a9e9")
        self.__acfg = self.__theme_dict.get("button_active_font_color", "#574ed6")
        self.__acbg = self.__theme_dict.get("button_active_bg_color", "#0fd2d6")

        btn_text = (
            # {image_type} ON
            message_manager.get_ui_message("U039", self.__image_type.capitalize())
            if self.__visible
            else message_manager.get_ui_message("U040", self.__image_type.capitalize()) # {image_type} OFF
        )
        btn_relief: Literal["sunken", "raised"] = (
            tk.SUNKEN if self.__visible else tk.RAISED
        )

        self.image_display_toggle_btn = tk.Button(
            master=self.__fr,
            text=btn_text,
            relief=btn_relief,
            bg=self.__bg,
            fg=self.__fg,
            font=btw.base_font,
            activebackground=self.__acbg,
            activeforeground=self.__acfg,
            command=self.__toggle,
        )

        self.__settings = UserSettingManager()

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

    def __toggle(self) -> None:
        """
        Toggle ON/OFF and call the callback.
        """
        self.__visible = not self.__visible
        if self.__visible:
            self.image_display_toggle_btn.config(
                # {image_type} ON
                text=message_manager.get_ui_message("U039", self.__image_type.capitalize()),
                relief=tk.SUNKEN
            )
        else:
            self.image_display_toggle_btn.config(
                # {image_type} OFF
                text=message_manager.get_ui_message("U040", self.__image_type.capitalize()),
                relief=tk.RAISED
            )

        if self.__callback:
            self.__callback(self.__image_type, self.__visible)

    def grid(self, **kwargs: Any) -> None:
        """Shortcut method to call grid on the main button."""
        self.image_display_toggle_btn.grid(**kwargs)

    def apply_theme_color(self, theme_colors: Dict[str, Dict[str, str | Literal["#27283a", "#22a9e9", "#574ed6", "#0fd2d6"]]]) -> None:
        """Apply theme colors to the button.

        Args:
            theme_colors (Dict[str, Dict[str, str]]): Theme colors to apply
        """
        try:
            # Get theme settings for this button
            theme_settings = theme_colors.get(self.__color_key, {})

            # Apply theme settings to button
            self._config_widget(theme_settings)

            # Update color variables
            self.__fg = theme_settings.get("button_inactive_font_color", "#27283a")
            self.__bg = theme_settings.get("button_inactive_bg_color", "#22a9e9")
            self.__acfg = theme_settings.get("button_active_font_color", "#574ed6")
            self.__acbg = theme_settings.get("button_active_bg_color", "#0fd2d6")

            # Apply theme to button
            self.image_display_toggle_btn.configure(
                bg=self.__bg,
                fg=self.__fg,
                activeforeground=self.__acfg,
                activebackground=self.__acbg,
            )

            # Theme color applied to {color_key} button
            logger.debug(message_manager.get_log_message("L101", self.__color_key))
        except Exception as e:
            # Failed to apply theme color: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Apply theme settings to the button.

        Args:
            theme_settings (Dict[str, Any]): Theme settings to apply
        """
        try:
            # Configure button with theme settings
            self.image_display_toggle_btn.configure(**theme_settings)
        except Exception as e:
            # Failed to configure widget with theme settings: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise
