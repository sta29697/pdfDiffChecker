from __future__ import annotations

import tkinter as tk
from logging import getLogger
from pathlib import Path
from tkinter import messagebox
from typing import Optional, Any, Dict

from configurations.user_setting_manager import UserSettingManager
from controllers.color_theme_manager import ColorThemeManager
from models.class_dictionary import FilePathInfo, FolderPathInfo
from configurations.message_manager import get_message_manager
from widgets.base_entry import BaseEntry
from themes.coloring_theme_interface import ColoringThemeIF
from controllers.app_state import AppState

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()

class BasePathEntry(tk.Frame, ColoringThemeIF):
    """Base class for path entry widgets.

    This class provides base functionality for entry widgets that:
    1. Handle file/directory paths
    2. Support theme color application
    3. Manage path validation and updates
    
    Attributes:
        path_var (tk.StringVar): Variable for storing the path
        path_entry (BaseEntry): Entry widget for displaying the path
        path_obj (Optional[FilePathInfo | FolderPathInfo]): Path information object
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        entry_setting_key: str,
        **kwargs: Any
    ) -> None:
        """Initialize the path entry widget.

        Args:
            fr (tk.Frame): Parent frame
            color_key (str): Color key for theme application
            entry_setting_key (str): Key for entry widget settings
            **kwargs: Additional keyword arguments for tk.Frame
        """
        super().__init__(fr, **kwargs)
        self.__entry_setting_key = entry_setting_key
        self.__color_key = color_key
        self.__settings = UserSettingManager()
        self.path_obj: Optional[FilePathInfo | FolderPathInfo] = None

        # Flag to track if theme has been initialized
        self._theme_initialized: bool = False

        # Initialize path variable with suppressed callback during initial setup
        self.path_var = tk.StringVar()
        self._suppress_callback: bool = True
        self.path_var.trace_add("write", self._on_path_var_write)
        # Enable callback after widget initialization
        self.after_idle(lambda: setattr(self, "_suppress_callback", False))

        try:
            # Create entry widget
            self.path_entry = BaseEntry(
                self,
                color_key=color_key,
                textvariable=self.path_var
            )
            self.path_entry.pack(fill="both", expand=True)
            # Theme application is handled in main.py's init_color_theme method
            # Path entry widget created successfully - only log if appropriate
            if AppState.should_log_widget_init():
                # Use a more internationalized format for path information
                current_path = self.path_entry.get() or message_manager.get_ui_message("U098") # Using "None" or localized equivalent
                logger.debug(message_manager.get_log_message("L107", current_path))
        except Exception as e:
            # Always log errors regardless of initialization state
            # Failed to create widget: {error}
            logger.error(message_manager.get_log_message("L265", str(e)))
            raise

    @property
    def entry_setting_key(self) -> str:
        """Get the entry setting key.
        
        Returns:
            str: The entry setting key
        """
        return self.__entry_setting_key
        
    @property
    def color_key(self) -> str:
        """Get the color key.
        
        Returns:
            str: The color key
        """
        return self.__color_key
    
    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Apply theme colors to the path entry.
        Only applies theme when ColorThemeManager has completed initialization.
        
        Args:
            theme_data: Dictionary containing theme color settings.
        """
        # Reset theme initialization flag
        self._theme_initialized = False if not hasattr(self, "_theme_initialized") else self._theme_initialized
        
        # Skip applying theme if ColorThemeManager initialization is not complete
        if not ColorThemeManager.is_initialization_complete():
            # Get parent widget info for better context (potentially a tab)
            parent_info = getattr(self.master, '__class__.__name__', 'unknown')
        try:
            # If theme data is None or empty, log it and return
            if not theme_data:
                import sys
                
                # Get caller information
                caller_info = "unknown"
                caller_frame = sys._getframe().f_back
                if caller_frame is not None:
                    back_frame = caller_frame.f_back
                    if back_frame is not None:
                        caller_info = f"{back_frame.f_code.co_filename}:{back_frame.f_lineno}"
                
                # Get parent widget info for better context (potentially a tab)
                parent_info = getattr(self.master, '__class__.__name__', 'unknown')
                if hasattr(self.master, '__module__'):
                    parent_module = self.master.__module__.split('.')[-1]
                    parent_info = f"{parent_module}.{parent_info}"
                
                path_entry_info = f"{self.__class__.__name__}({self.__entry_setting_key}) in {parent_info}, caller={caller_info}"
                # Log empty theme data with appropriate message code
                logger.debug(message_manager.get_log_message("L067", path_entry_info))
                return
                
            # Apply theme to path entry and configure widget colors
            self.path_entry.apply_theme_color(theme_data)
            self._config_widget(theme_data)
            
            # Mark that theme has been successfully initialized
            self._theme_initialized = True
            # Get caller information for accurate logging
            import inspect
            import os
            
            # Default caller file is current file
            caller_file = os.path.basename(__file__)
            
            # Check if caller context was provided by the widgets tracker
            if hasattr(self, "_caller_context") and isinstance(self._caller_context, dict):
                # Use caller info from the actual caller context
                caller_file = self._caller_context.get("file", caller_file)
                
                # Get the actual tab or view file name if we have that information
                # This helps trace which view/tab actually contains this widget
                if "caller" in self._caller_context and self._caller_context["caller"] == "widgets_tracker":
                    # Try to get actual parent module info for better context
                    if hasattr(self.master, "__module__") and self.master.__module__.startswith("views."):
                        caller_file = self.master.__module__.split(".")[1] + ".py"
            else:
                # Get caller through inspect module if no context provided
                current_frame = inspect.currentframe()
                if current_frame is not None:  # Explicitly check for None
                    caller_frames = inspect.getouterframes(current_frame)
                    if len(caller_frames) > 1:
                        caller_file = os.path.basename(caller_frames[1].filename)
            
            # Log with caller file and entry key
            logger.debug(message_manager.get_log_message("L087", caller_file, f"entry_{self.__entry_setting_key}"))
        except Exception as e:
            # Add detailed error information to properly explain what went wrong
            import traceback
            
            # Get parent widget info for better context (potentially a tab)
            parent_info = getattr(self.master, '__class__.__name__', 'unknown')
            if hasattr(self.master, '__module__'):
                parent_module = self.master.__module__.split('.')[-1]
                parent_info = f"{parent_module}.{parent_info}"
            
            # Always log errors at error level regardless of initialization state
            # Use L266 which has parameters for entry key, parent info, and error message
            logger.error(message_manager.get_log_message("L266", self.__entry_setting_key, parent_info, str(e)))
            
            # Only log detailed debug information if we're past initialization or verbose logging is enabled
            if AppState.should_log_widget_init():
                # Log additional details and stack trace at debug level
                widget_details = f"Widget ID: {id(self)}, Entry setting key: {self.__entry_setting_key}"
                logger.debug(message_manager.get_log_message("L258", widget_details))
                
                # Log stack trace at debug level
                trace = traceback.format_exc()
                logger.debug(f"Stack trace: \n{trace}")

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget appearance based on theme settings.
        
        Args:
            theme_settings: Dictionary of theme settings to apply
        """
        # Apply background color to the frame if available in theme
        frame_bg = theme_settings.get("background_color")
        if frame_bg:
            self.configure(bg=frame_bg)
    
    def _on_path_var_write(self, *args: Any) -> None:
        """Handle path_var changes with initial suppression."""
        if self._suppress_callback:
            return
        self._set_path_obj_from_entry(self.path_var)
    def _set_path_obj_from_entry(self, path_var: tk.StringVar, *args: Any) -> None:
        """
        Update path object from entry widget value.

        Args:
            path_var (tk.StringVar): StringVar containing the path
            *args: Additional arguments from trace_add callback
        """
        try:
            path_str = path_var.get()
            if not path_str:
                return

            path = Path(path_str)
            if path.is_file():
                self.path_obj = FilePathInfo(path)
            elif path.is_dir():
                self.path_obj = FolderPathInfo(path)
            else:
                # Log invalid path warning with entered path
                logger.warning(message_manager.get_log_message("L108", path_str))
                # Show warning dialog for invalid path entered
                messagebox.showwarning(
                    message_manager.get_ui_message("U050"),
                    message_manager.get_ui_message("U051")
                )
                return

            # Save to user settings
            self.__settings.update_setting(self.__entry_setting_key, str(path))
            self.__settings.save_settings()
            # Path object updated: {path_obj}
            logger.debug(message_manager.get_log_message("L109", self.path_obj))
        except Exception as e:
            # Log error when setting path object fails
            logger.error(message_manager.get_log_message("L067", str(e)))
            # Show warning dialog for failed to set path
            messagebox.showwarning(
                message_manager.get_ui_message("U050"),
                message_manager.get_ui_message("U052")
            )
