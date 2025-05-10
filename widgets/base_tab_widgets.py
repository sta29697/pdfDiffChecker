from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font, messagebox
import time
from logging import getLogger
from controllers.widgets_tracker import WidgetsTracker, ThemeColorApplicable
from typing import List, Any
from utils.log_throttle import LogThrottle

from configurations import tool_settings
from configurations.user_setting_manager import UserSettingManager
from models.class_dictionary import CurrentAreaInfo
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()

class BaseTabWidgets(tk.Frame):
    """Base class for tab widgets.

    This class provides base functionality for tab widgets that:
    1. Handle tab-specific UI elements
    2. Support theme color application
    3. Manage tab state and interactions
    """

    # Base font placeholder; will be initialized lazily once a root window exists
    base_font: font.Font = None  # type: ignore[assignment]

    def __init__(
        self, master: tk.Misc | None = None
    ) -> None:
        """Initialize the tab widget.

        Args:
            master (tk.Misc | None): Parent widget
        """
        if not sys.platform.startswith("win"):
            # Show OS compatibility error dialog
            messagebox.showerror(
                message_manager.get_ui_message("U048"),
                # Inform user that application is Windows-only
                message_manager.get_ui_message("U049")
            )
            sys.exit(1)

        self._current_window_info = CurrentAreaInfo(width=0, height=0)
        if master is not None:
            super().__init__(master)
            # Removed <Configure> event binding; using centrally managed window size information instead
            # master.bind("<Configure>", self.get_window_info)
        self.__settings = UserSettingManager()
        # Window resize log throttling: suppress logs until target size or timeout
        self._window_log_enabled = False
        self._window_log_timer_start = time.time()
        self._window_log_target_width = self.__settings.get_setting("window_width")
        self._window_log_target_height = self.__settings.get_setting("window_height")
        self._window_log_throttle_seconds = 30
        # Store previous window size to only log actual size changes
        self._previous_width = 0
        self._previous_height = 0
        # Create window resize log throttle with 0.2s minimum interval
        self._window_resize_throttle = LogThrottle(min_interval=0.2)
        # Lazily initialize base_font after a root window exists
        if BaseTabWidgets.base_font is None:
            BaseTabWidgets.base_font = font.Font(
                family=tool_settings.font_family,
                size=tool_settings.font_size,
            )
        # Suppress window resize logging until layout complete is set
        self._layout_complete = False
        # Internal widget tracker for theming
        self._widgets_tracker: WidgetsTracker = WidgetsTracker()

    def _update_window_info_silent(self, width: int, height: int) -> None:
        """Update window dimensions without logging.
        
        This method is called by the main window to update dimensions in all tabs
        when a resize event occurs, but without generating duplicate logs.
        
        Args:
            width (int): Window width
            height (int): Window height
        """
        self._current_window_info.width = width
        self._current_window_info.height = height
        # Update previous dimensions for change tracking
        self._previous_width = width
        self._previous_height = height

    def get_window_info(self, event: tk.Event) -> CurrentAreaInfo:
        """Get current window information.
        
        This method is now DEPRECATED and only kept for compatibility.
        Window resize handling is centralized in main.py.

        Args:
            event (tk.Event): Event object

        Returns:
            CurrentAreaInfo: Current window information
        """
        # This method is kept for backward compatibility
        # Window resize handling is now centralized in main.py
        self._current_window_info.width = event.width
        self._current_window_info.height = event.height
        return self._current_window_info

    def get_current_window_info(self) -> CurrentAreaInfo:
        """Get current window information.

        Returns:
            CurrentAreaInfo: Current window information
        """
        return self._current_window_info

    def exit_window(self, master: tk.Misc) -> None:
        """Exit the window.

        Args:
            master (tk.Misc): Parent widget
        """
        # Log window exit event
        logger.debug(message_manager.get_log_message("L105"))
        
        # Instead of directly handling cleanup and exit,
        # publish a window close request event that will be handled by WindowEventManager
        from controllers.event_bus import EventBus, EventNames
        event_bus = EventBus()
        
        # Log that we're requesting window close via event bus
        logger.debug(message_manager.get_log_message("L511", "Publishing window close request"))
        
        # Publish window close request
        event_bus.publish(EventNames.WINDOW_CLOSE_REQUESTED)
        
        # Note: The actual window destruction and cleanup is now handled by WindowEventManager

    def add_widget(self, widget: Any) -> None:
        """Register a widget for theme color application."""
        # Register only if widget supports theme color application
        if hasattr(widget, "apply_theme_color"):
            self._widgets_tracker.add_widgets(widget)

    def get_widgets(self) -> List[ThemeColorApplicable]:
        """Return all registered widgets for theming."""
        return self._widgets_tracker.registered_widgets
