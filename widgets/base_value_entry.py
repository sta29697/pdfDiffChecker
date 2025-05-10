from __future__ import annotations

from logging import getLogger
import tkinter as tk
from typing import Any, Optional

from configurations.tool_settings import DEFAULT_USER_SET
from configurations.user_setting_manager import UserSettingManager as usm
from widgets.base_entry import BaseEntry
from widgets.base_tab_widgets import BaseTabWidgets as btw
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()


class BaseValueEntry(BaseEntry):
    """
    Entry widget for foreground/background threshold (inherits BaseEntry for theme and widget tracking).
    """
    def __init__(self, fr: tk.Frame, color_key: str, setting_key: str) -> None:
        """
        Initialize the value entry widget for threshold.

        Args:
            fr (tk.Frame): Parent frame
            color_key (str): Theme color key for this entry
            setting_key (str): Key for user setting persistence
        """
        self.__fr = fr
        self.__color_key = color_key
        self.__setting_key = setting_key

        # Determine which section to read based on user_settings_status
        try:
            status = usm.get_settings_status()
            self.settings_section = "user_settings" if status == "user_settings" else "default"
            self.__current_fb_th = usm.get_setting(self.__setting_key)
        except Exception as e:
            logger.error(message_manager.get_log_message("L067", str(e)))
            self.settings_section = "default"
            self.__current_fb_th = DEFAULT_USER_SET["default"][self.__setting_key]
        self._fb_th = tk.IntVar(value=self.__current_fb_th)

        # Initialize the base entry widget for threshold input
        super().__init__(
            fr,  # Pass parent frame as master
            color_key=color_key,
            textvariable=self._fb_th,
            font=btw.base_font,
            cursor="hand2",
            width=6,
            takefocus=True,
            justify=tk.RIGHT,
            highlightthickness=2,
        )
        self.bind("<FocusOut>", self._update_fb_threshold)
        self.bind("<Return>", self._update_fb_threshold)

        # Register to WidgetsTracker 
        from controllers.widgets_tracker import WidgetsTracker
        WidgetsTracker().add_widgets(self)

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Apply theme colors to the entry.

        Args:
            theme_data (dict[str, Any]): Theme color data from ColorThemeManager.
        """
        try:
            entry_theme_config = theme_data.get(self.__color_key, {})
            # Apply all relevant keys for Entry widget
            self.configure(**entry_theme_config)
            logger.debug(message_manager.get_log_message("L110", self.__color_key))
        except Exception as e:
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _update_fb_threshold(self, event: Optional[tk.Event] = None) -> None:
        # Log message for threshold update attempt
        logger.debug(message_manager.get_log_message("L127"))
        _new_th = self._fb_th.get()
        if _new_th != self.__current_fb_th:
            self.fb_threshold = _new_th
            # Foreground/Background threshold updated to: {threshold}
            logger.info(message_manager.get_log_message("L128", _new_th))

    @property
    def fb_threshold(self) -> int:
        return self._fb_th.get()

    @fb_threshold.setter
    def fb_threshold(self, input_fb_th: int) -> None:
        """Set the foreground/background threshold.

        Args:
            input_fb_th (int): New threshold value
        """
        if input_fb_th is None:
            input_fb_th = 0  # Default value if None is provided
        self._fb_th.set(input_fb_th)
        # Threshold updated to: {threshold}
        logger.info(message_manager.get_log_message("L129", input_fb_th))
