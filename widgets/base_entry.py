"""Base entry class for the application."""

from __future__ import annotations

import tkinter as tk
from logging import getLogger
from typing import Any, cast
from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from controllers.color_theme_manager import ColorThemeManager
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)

# Initialize singleton message manager
message_manager = get_message_manager()


class BaseEntry(tk.Entry, ThemeColorApplicable, ColoringThemeIF):
    """Base class for entry widgets.

    This class provides base functionality for entries that support theme color
    application and automatic registration with WidgetsTracker.

    Attributes:
        __color_key: Key for accessing theme colors specific to this entry.
    """

    def __init__(
        self,
        master: tk.Frame,
        color_key: str,
        **kwargs: Any
    ) -> None:
        """Initialize a new BaseEntry instance.

        Args:
            master: Parent frame.
            color_key: Key for theme color application.
            **kwargs: Additional keyword arguments for tk.Entry.
        """
        super().__init__(master, **kwargs)  # type: ignore[arg-type]
        self.__color_key = color_key

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

    # Type annotation for initialization flag
    _theme_initialized: bool = False
    _logged_successful_theme: bool = False
    
    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Apply theme colors to the entry.
        Only applies theme when ColorThemeManager has completed initialization.

        Args:
            theme_data (dict[str, Any]): Dictionary containing theme color data.
        """
        try:
            # Initialize theme status tracking if not already present
            if not hasattr(self, "_theme_initialized"):
                self._theme_initialized = False
            
            # Skip applying theme if ColorThemeManager initialization is not complete
            if not ColorThemeManager.is_initialization_complete():
                # Don't log during initialization phase
                return
                
            entry_theme_config = cast(dict[str, Any], theme_data.get(self.__color_key, {}))
            
            # Check if entry_theme_config is empty and log appropriately
            if not entry_theme_config:
                # Get calling frame info for better logging
                import inspect
                caller_frame = inspect.currentframe()
                caller_info = "unknown"
                
                # Null check for currentframe (may return None)
                if caller_frame is not None:
                    back_frame = caller_frame.f_back
                    if back_frame is not None:
                        caller_info = f"{back_frame.f_code.co_filename}:{back_frame.f_lineno}"
                
                entry_info = f"{self.__color_key} in {self.__class__.__module__}.{self.__class__.__name__}(id={id(self)}, caller={caller_info})"
                # logger.debug(message_manager.get_log_message("L161", entry_info))
                return
                
            # Apply theme configuration
            self.configure(**entry_theme_config)  # type: ignore[arg-type]
            self._config_widget(entry_theme_config)
            
            # Mark that theme has been successfully initialized
            self._theme_initialized = True

            if self.__color_key == "base_file_path_entry":
                fg = entry_theme_config.get("fg")
                bg = entry_theme_config.get("bg")
                hlfg = entry_theme_config.get("highlightcolor")
                hlbg = entry_theme_config.get("highlightbackground")
                logger.debug(
                    f"[ENTRY_THEME] color_key={self.__color_key}, fg={fg}, bg={bg}, "
                    f"highlight={hlfg}/{hlbg}, widget_id={id(self)}, state={self.cget('state')}"
                )
        except Exception as e:
            # Add more detailed error information to help with debugging
            import traceback
            error_details = f"Error applying theme: {str(e)}\nColor key: {self.__color_key}\nWidget: {self.__class__.__name__}\nID: {id(self)}"
            logger.error(message_manager.get_log_message("L067", error_details))
            
            # Log stack trace at debug level for developers
            trace = traceback.format_exc()
            # logger.debug(message_manager.get_log_message("L241", trace))

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Configure widget appearance based on theme settings.
        
        Args:
            theme_settings: Dictionary of theme settings to apply
            
        Note:
            This method is required by ColoringThemeIF interface and can be
            overridden by derived classes to add custom theming behavior.
            BaseEntry implements the core Entry widget theming behavior, while
            derived classes can extend or modify this as needed.
        """
        try:
            # Apply basic Entry configurations that aren't handled in apply_theme_color
            # Currently Entry widget is fully configured in apply_theme_color,
            # but future derived classes may need additional configurations
            
            # Call a hook method that derived classes can override without
            # having to override the entire _config_widget method
            self._on_theme_config(theme_settings)
        except Exception as e:
            # Log error with message code - more structured and internationalized
            logger.error(message_manager.get_log_message("L067", str(e)))
            
    def _on_theme_config(self, theme_settings: dict[str, Any]) -> None:
        """
        Hook method for derived classes to implement custom theme configurations.
        
        Args:
            theme_settings: Dictionary of theme settings to apply
        """
        # Base implementation does nothing
        # Derived classes can override this method to add custom behavior
        pass
