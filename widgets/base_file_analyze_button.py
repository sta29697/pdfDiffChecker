from __future__ import annotations
import tkinter as tk
from typing import Any, Callable
from logging import getLogger
from widgets.base_button import BaseButton
from widgets.progress_window import ProgressWindow
from configurations.message_manager import get_message_manager
from pathlib import Path
import sys
import ctypes

logger = getLogger(__name__)

# Initialize singleton message manager
message_manager = get_message_manager()

class BaseFileAnalyzeButton(BaseButton):
    """Base class for file analyze buttons.

    This class provides base functionality for buttons that:
    1. Analyze file content
    2. Support theme color application
    3. Show progress during analysis
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        text: str | None = None,
        command: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the base file analyze button.

        Args:
            fr (tk.Widget): Parent widget
            color_key (str): Color key for theme application
            text (str | None): Button text
            command (Callable[[], Any] | None): Command to execute on button click
            **kwargs: Additional keyword arguments for tk.Button
        """
        super().__init__(
            fr, color_key=color_key, text=text, command=command, **kwargs
        )
        self.__color_key = color_key
        # Initialize progress window
        self.progress_window = ProgressWindow(self)

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Applies theme settings to the button widget.

        Args:
            theme_settings (dict[str, Any]): Theme settings to apply.
        """
        # Remove unsupported option before applying configuration
        filtered = {k: v for k, v in theme_settings.items() if k != "disabledbackground"}
        self.configure(**filtered)

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

    def _file_analyze_btn_clicked(self) -> None:
        """Handle the event when the button is clicked."""
        try:
            # UI text for analyze button click
            self.config(text=message_manager.get_ui_message("U027"))

            # Get current theme and set titlebar color
            self.__current_theme_name = ""
            self._windows_set_titlebar_color(
                "dark" if self.__current_theme_name == "dark" else "light"
            )

            self.run_analysis()
        except Exception as err:
            # Error in analyze button click handler: {error}
            logger.error(message_manager.get_log_message("L067", str(err)))
            # UI text for analyze button error
            self.config(text=message_manager.get_ui_message("U028"))

    def _windows_set_titlebar_color(self, color_mode: str) -> None:
        """Set the title bar color of the Toplevel window to dark or light on Windows.

        Args:
            color_mode (str): "dark" or "light"
        """
        try:
            # Skip if not on Windows or no progress window
            if not Path(sys.executable).root == Path("/"):
                return
            if self.progress_window is None or not self.progress_window.winfo_exists():
                return

            value = 1 if color_mode.lower() == "dark" else 0
            hwnd = ctypes.windll.user32.GetParent(self.progress_window.winfo_id())

            # Try modern attribute first, fall back to older one if needed
            for attr in [20, 19]:  # DWMWA_USE_IMMERSIVE_DARK_MODE values
                try:
                    ret = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        attr,
                        ctypes.byref(ctypes.c_int(value)),
                        ctypes.sizeof(ctypes.c_int(value)),
                    )
                    if ret == 0:  # S_OK
                        break
                except Exception as err:
                    # Failed to set window attribute {attr}: {error}
                    logger.error(message_manager.get_log_message("L080", attr, str(err)))
                    continue
        except Exception as err:
            # Error setting window titlebar color: {error}
            logger.error(message_manager.get_log_message("L067", str(err)))

    def run_analysis(self) -> None:
        """Run the file analysis process."""
        try:
            # Create progress window
            self.progress_window.show()

            # UI text for progress update
            self.progress_window.update_progress(0, message_manager.get_ui_message("U029"))

            # Analyze file
            self._analyze_file_impl()

            # Hide progress window
            self.progress_window.hide()

            # Log message for analysis completion
            logger.debug(message_manager.get_log_message("L081"))
        except Exception as err:
            # Failed to analyze file: {error}
            logger.error(message_manager.get_log_message("L067", str(err)))
            self.progress_window.hide()
            raise

    def _analyze_file_impl(self) -> None:
        """Implement file analysis."""
        raise NotImplementedError("Subclasses must implement _analyze_file_impl")

    def __cleanup(self) -> None:
        """Clean up resources after analysis completion or error."""
        try:
            # UI text for cleanup fallback
            self.winfo_toplevel().after(0, lambda: self.config(text=message_manager.get_ui_message("U028")))
            if (
                hasattr(self, "progress_window")
                and self.progress_window is not None
                and self.progress_window.winfo_exists()
            ):
                self.progress_window.destroy()
        except Exception as err:
            # Error in cleanup: {error}
            logger.error(message_manager.get_log_message("L067", str(err)))
