"""
CustomMessageBox: Message box window with theme support
"""
import tkinter as tk
from typing import Any, Dict, Optional
from logging import getLogger
import ctypes
from utils.theme_helpers import get_theme_color
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()

class CustomMessageBox(tk.Toplevel, ColoringThemeIF):
    """
    CustomMessageBox: Message box window with theme support and color_key-based theming.

    Args:
        parent (Optional[tk.Widget]): Parent widget.
        message (str): Message to display. Must be pre-localized (multilingual support handled by caller).
        title (str): Title of the message box window.
        message_type (str): Type of message (e.g., 'info', 'warning').
        color_key (str): Key to look up color theme block. If not found, fallback to DEFAULT_COLOR_THEME_SET.
        *args, **kwargs: Additional arguments for tk.Toplevel.

    Note:
        When the window is destroyed, it is also unregistered from WidgetsTracker.
    """
    def __init__(self, parent: Optional[tk.Widget], message: str, title: Optional[str] = None, message_type: str = "info", color_key: str = "SubWindow", *args: Any, **kwargs: Any) -> None:
        """
        Initialize the custom message box window with theme and localization support.
        Args:
            parent (Optional[tk.Widget]): Parent widget.
            message (str): Message to display (should be pre-localized).
            title (Optional[str]): Title of the message box. If None, use multi-language UI code U029.
            message_type (str): Type of message (e.g., 'info', 'warning').
            color_key (str): Theme color key.
            *args, **kwargs: Additional arguments for tk.Toplevel.
        """
        super().__init__(parent, *args, **kwargs)
        self.withdraw()
        # Multi-language title resolution
        if title is None:
            # UI text for default message box title
            resolved_title = message_manager.get_ui_message("U029")
        else:
            resolved_title = title
        self.title(resolved_title)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.color_key = color_key
        self.label = tk.Label(self, text=message, justify=tk.LEFT, font=("Arial", 10))
        self.label.pack(padx=12, pady=8)
        self.button = tk.Button(self, text="OK", command=self.destroy)
        self.button.pack(pady=(0, 8))
        self.__apply_theme()
        self.deiconify()
        self.lift()
        # Log message for custom message box shown
        logger.info(message_manager.get_log_message("L154"))
        WidgetsTracker().add_widgets(self)

    def destroy(self) -> None:
        """
        Destroy the custom message box window and unregister from WidgetsTracker.
        """
        # Log message for custom message box destroyed
        logger.info(message_manager.get_log_message("L155"))
        WidgetsTracker().remove_widgets(self)
        super().destroy()

    def __apply_theme(self) -> None:
        """
        Apply color theme to the message box using color_key. Fallback to DEFAULT_COLOR_THEME_SET if not found.
        """
        theme_obj = ColorThemeManager.get_current_theme()
        theme = dict(theme_obj)
        theme_name = ColorThemeManager.get_current_theme_name()
        try:
            bg = get_theme_color(theme, self.color_key, "text_box", "bg", "#ffffe0")
            fg = get_theme_color(theme, self.color_key, "text_box", "fg", "#000000")
            btn_bg = get_theme_color(theme, self.color_key, "Button", "bg", "#e0e0e0")
            btn_fg = get_theme_color(theme, self.color_key, "Button", "fg", "#000000")
            self.configure(bg=bg)
            self.label.configure(bg=bg, fg=fg)
            self.button.configure(bg=btn_bg, fg=btn_fg, activebackground=btn_bg, activeforeground=btn_fg)
        except Exception as e:
            # Failed to apply theme to custom message box: {0}
            logger.error(message_manager.get_log_message("L157", str(e)))
        self._set_windows_titlebar_color(theme_name)

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """
        Apply provided theme colors to the message box using color_key.
        """
        bg = theme_data.get(self.color_key, {}).get("bg", theme_data.get("text_box", {}).get("bg", "#ffffe0"))
        fg = theme_data.get(self.color_key, {}).get("fg", theme_data.get("text_box", {}).get("fg", "#000000"))
        btn_bg = theme_data.get(self.color_key, {}).get("bg", theme_data.get("Button", {}).get("bg", "#e0e0e0"))
        btn_fg = theme_data.get(self.color_key, {}).get("fg", theme_data.get("Button", {}).get("fg", "#000000"))
        bg = theme_data.get(self.color_key, theme_data.get("SubWindow", {})).get("bg", "#ffffe0")
        fg = theme_data.get(self.color_key, theme_data.get("Label", {})).get("fg", "#000000")
        btn_bg = theme_data.get(self.color_key, theme_data.get("Button", {})).get("bg", "#e0e0e0")
        btn_fg = theme_data.get(self.color_key, theme_data.get("Button", {})).get("fg", "#000000")
        self.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg)
        self.button.configure(bg=btn_bg, fg=btn_fg, activebackground=btn_bg, activeforeground=btn_fg)
        theme_name = ColorThemeManager.get_current_theme_name()
        self._set_windows_titlebar_color(theme_name)

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """
        Additional widget-specific configuration (not used).
        """
        pass

    def _set_windows_titlebar_color(self, theme: str) -> None:
        """
        Set Windows titlebar color for Windows 10 and above. No effect on older Windows or other OS.
        On Windows 10+, sets immersive dark mode for the titlebar if theme is 'dark'.
        On other platforms or older Windows, this function does nothing and the titlebar color remains default.
        (No Windows 10+ restriction comment previously because this function is cross-version safe.)
        """
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            if theme == "dark":
                value = ctypes.c_int(1)
            else:
                value = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        except Exception as e:
            # Failed to set Windows titlebar color
            logger.error(message_manager.get_log_message("L158", str(e)))
