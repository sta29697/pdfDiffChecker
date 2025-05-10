from logging import getLogger
from tkinter import ttk
from typing import Any, Dict
from abc import ABC, abstractmethod

from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
message_manager = get_message_manager()

class ColoringThemeIF(ABC):
    @abstractmethod
    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Implement the theme application process in a subclass

        Args:
            theme_data (Dict[str, Any]): Theme data obtained
                                         by ColorThemeManager.load_theme
        """
        pass

    @abstractmethod
    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Methods for reflecting theme settings in widgets.

        Args:
            theme_settings (Dict[str, Any]): Implement in subclasses
                                             only when necessary.
        """
        pass

class ColoringNotebookIF(ttk.Notebook, ColoringThemeIF):
    """Interface for applying theme colors to ttk.Notebook widgets."""
    
    def apply_theme_color(self, theme_data: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the ttk.Notebook widget.

        Args:
            theme_data (Dict[str, Dict[str, str]]): Theme data to apply
        """
        try:
            notebook_settings = theme_data.get("Notebook", {})
            style = ttk.Style()
            style.configure(
                "TNotebook", 
                background=notebook_settings.get("bg", "#1d1d29")
            )
            style.configure(
                "TNotebook.Tab", 
                background=notebook_settings.get("tab_bg", "#2d2d39"),
                foreground=notebook_settings.get("tab_fg", "#ffffff")
            )
            # Get theme name from singleton ColorThemeManager if possible
            try:
                from controllers.color_theme_manager import ColorThemeManager
                theme_name = ColorThemeManager.get_current_theme_name()
            except Exception:
                theme_name = "dark"  # Default to 'dark' theme as a safe fallback
            logger.debug(message_manager.get_log_message("L211", theme_name))
        except Exception as e:
            logger.error(message_manager.get_log_message("L199", str(e)))
    
    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget-specific theme settings.

        Args:
            theme_settings (Dict[str, Any]): Widget-specific theme settings
        """
        try:
            self.configure(**theme_settings)  # type: ignore[arg-type]
            # Configured widget with settings
            logger.debug(message_manager.get_log_message("L200", self.__class__.__name__, theme_settings))
        except Exception as e:
            logger.error(message_manager.get_log_message("L201", self.__class__.__name__, str(e)))

