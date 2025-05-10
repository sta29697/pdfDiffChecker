"""
BalloonMessageWindow: Balloon message window with theme support
"""
import tkinter as tk
from typing import Any, Dict, Optional
from logging import getLogger
import ctypes
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager
from utils.theme_helpers import get_theme_color
message_manager = get_message_manager()

logger = getLogger(__name__)

# Remove erroneous self-reference, message_manager already instantiated above

class BalloonMessageWindow(tk.Toplevel, ColoringThemeIF):
    """
    BalloonMessageWindow: Balloon message window with theme support and color_key-based theming.

    Args:
        parent (Optional[tk.Widget]): Parent widget.
        message (str): Message to display. Must be pre-localized (multilingual support handled by caller).
        color_key (str): Key to look up color theme block. If not found, fallback to DEFAULT_COLOR_THEME_SET.
        hover_delay (float): Delay in seconds before showing balloon after hover. Default: 0.3 seconds.
        display_time (int): Time in milliseconds to display the balloon. Default: 3000ms (3 seconds).
        *args, **kwargs: Additional arguments for tk.Toplevel.

    Note:
        When the window is destroyed, it is also unregistered from WidgetsTracker.
    """
    def __init__(self, parent: Optional[tk.Widget], message: str, color_key: str = "Frame", 
                 hover_delay: float = 0.6, display_time: int = 5000, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self.withdraw()  # Hide initially
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.color_key = color_key
        self.hover_delay = hover_delay  # Seconds to wait before showing the balloon
        self.display_time = display_time  # Milliseconds to display the balloon
        
        self.label = tk.Label(self, text=message, justify=tk.LEFT, font=("Arial", 9))
        self.label.pack(padx=2, pady=2)
        self.__apply_theme()
        
        # Schedule display with hover delay
        self.after(int(self.hover_delay * 1000), self._show_balloon)
        
        WidgetsTracker().add_widgets(self)

    def _show_balloon(self) -> None:
        """
        Show the balloon after hover delay
        """
        self.deiconify()
        self.lift()
        # Log balloon message window display event
        logger.info(message_manager.get_log_message("L152"))
        # Schedule auto-destroy
        self.after(self.display_time, self.destroy)

    def destroy(self) -> None:
        """
        Destroy the balloon message window and unregister from WidgetsTracker.
        """
        # Log balloon message window destroy event
        logger.info(message_manager.get_log_message("L153"))
        WidgetsTracker().remove_widgets(self)
        super().destroy()

    def __apply_theme(self) -> None:
        """
        Apply color theme to the balloon using color_key. Fallback to text_box if not found.
        """
        theme_obj = ColorThemeManager.get_current_theme()
        theme = dict(theme_obj)
        try:
            bg_color = get_theme_color(theme, self.color_key, "text_box", "bg", "#ffffe0")
            fg_color = get_theme_color(theme, self.color_key, "text_box", "fg", "#000000")
            self.configure(bg=bg_color)
            self.label.configure(bg=bg_color, fg=fg_color)
        except Exception as e:
            # Failed to apply theme to balloon message window: {0}
            logger.error(message_manager.get_log_message("L156", str(e)))
        theme_name = ColorThemeManager.get_current_theme_name()
        bg = get_theme_color(theme, self.color_key, "text_box", "bg", "#ffffe0")
        fg = get_theme_color(theme, self.color_key, "text_box", "fg", "#000000")
        self.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg)
        self._set_windows_titlebar_color(theme_name)

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """
        Apply provided theme colors to the balloon using color_key.
        """
        bg = get_theme_color(theme_data, self.color_key, "text_box", "bg", "#ffffe0")
        fg = get_theme_color(theme_data, self.color_key, "text_box", "fg", "#000000")
        self.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg)
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
            # Failed to set Windows titlebar color: {0}
            logger.error(message_manager.get_log_message("L158", str(e)))
