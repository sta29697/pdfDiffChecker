from __future__ import annotations
import inspect
import os
import tkinter as tk
from logging import getLogger
from typing import Any, Dict, Callable

from configurations.tool_settings import DEFAULT_COLOR_THEME_SET
from configurations.message_manager import get_message_manager
from controllers.color_theme_manager import ColorThemeManager as ctm, ThemeColors
from controllers.widgets_tracker import ThemeColorApplicable
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets as btw

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()


class ImageVisibilityToggleFrame(tk.Frame, ThemeColorApplicable, ColoringThemeIF):
    """
    A frame containing toggle buttons for base and comp image visibility.
    """

    def __init__(
        self,
        parent: tk.Frame,
        color_key: str = "image_visibility_toggle",
        callback: Callable[[str, bool], None] | None = None,
    ) -> None:
        """
        Initialize the toggle frame.

        Args:
            parent: Parent frame where this frame will be placed
            color_key: Key for color theming
            callback: Function to call when toggle state changes
        """
        self.__parent = parent
        super().__init__(self.__parent)
        self.__color_key = color_key
        self.__callback = callback

        # Acquire theme color from ColorThemeManager
        try:
            current_theme: ThemeColors = ctm.get_current_theme()
            self.__theme_dict: Dict[str, Any] = current_theme.colors.get(self.__color_key, {})  # type: ignore
        except Exception as e:
            # Failed to get theme color: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            self.__theme_dict = DEFAULT_COLOR_THEME_SET[self.__color_key]  # type: ignore

        # Base color settings
        self.__fg = self.__theme_dict.get("button_inactive_font_color", "#0000FF")
        self.__bg = self.__theme_dict.get("button_inactive_bg_color", "#0000FF")
        self.__acfg = self.__theme_dict.get("button_active_font_color", "#574ed6")
        self.__acbg = self.__theme_dict.get("button_active_bg_color", "#0fd2d6")

        # Create toggle buttons
        self.__create_toggle_buttons()

    def __create_toggle_buttons(self) -> None:
        """Create the toggle buttons for base and comp visibility."""
        # Base toggle
        self.__base_var = tk.BooleanVar(value=True)
        # UI text for base image visibility toggle
        self.__base_toggle = tk.Checkbutton(
            self,
            text=message_manager.get_ui_message("U141"),  # Base visibility
            font=btw.base_font,
            variable=self.__base_var,
            command=lambda: self.__on_toggle("base", self.__base_var.get()),
            fg=self.__fg,
            bg=self.__bg,
            activeforeground=self.__acfg,
            activebackground=self.__acbg,
            selectcolor=self.__bg,
        )
        self.__base_toggle.grid(row=0, column=0, padx=5, pady=5)

        # Comp toggle
        self.__comp_var = tk.BooleanVar(value=True)
        # UI text for comparison image visibility toggle
        self.__comp_toggle = tk.Checkbutton(
            self,
            text=message_manager.get_ui_message("U142"),  # Comparison visibility
            font=btw.base_font,
            variable=self.__comp_var,
            command=lambda: self.__on_toggle("comp", self.__comp_var.get()),
            fg=self.__fg,
            bg=self.__bg,
            activeforeground=self.__acfg,
            activebackground=self.__acbg,
            selectcolor=self.__bg,
        )
        self.__comp_toggle.grid(row=0, column=1, padx=5, pady=5)

    def __on_toggle(self, image_type: str, new_state: bool) -> None:
        """Handle toggle button state changes."""
        if self.__callback:
            self.__callback(image_type, new_state)

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Apply new theme colors to all widgets.

        Args:
            theme_data: New theme color data
        """
        try:
            # Check if theme_data is empty
            if not theme_data:
                # Empty theme data for ImageVisibilityToggleFrame
                logger.debug(message_manager.get_log_message("L165", self.__class__.__name__))
                return
                
            toggle_theme_config: Dict[str, Any] = theme_data.get(self.__color_key, {})
            
            # Check if toggle_theme_config is empty
            if not toggle_theme_config:
                # Empty theme configuration for ImageVisibilityToggleFrame
                logger.debug(message_manager.get_log_message("L166", self.__color_key))
                return

            # Apply theme settings to this frame
            self._config_widget(toggle_theme_config)

            # Get current theme (by fallback)
            current_fg = self.__base_toggle.cget("fg")
            current_bg = self.__base_toggle.cget("bg")
            current_acfg = self.__base_toggle.cget("activeforeground")
            current_acbg = self.__base_toggle.cget("activebackground")

            # Overwrite if in new theme, otherwise keep current theme
            self.__fg = toggle_theme_config.get("button_inactive_font_color", current_fg)
            self.__bg = toggle_theme_config.get("button_inactive_bg_color", current_bg)
            self.__acfg = toggle_theme_config.get("button_active_font_color", current_acfg)
            self.__acbg = toggle_theme_config.get("button_active_bg_color", current_acbg)

            # Apply to both toggles
            for toggle in [self.__base_toggle, self.__comp_toggle]:
                toggle.configure(
                    fg=self.__fg,
                    bg=self.__bg,
                    activeforeground=self.__acfg,
                    activebackground=self.__acbg,
                    selectcolor=self.__bg,
                )

            # Get caller information for accurate logging
            caller_file = os.path.basename(__file__) # デフォルトは現在のファイル
            
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
                # If no context, use inspect to get caller info
                frame = inspect.currentframe()
                if frame:
                    frame_info_list = inspect.getouterframes(frame)
                    if len(frame_info_list) > 1:
                        caller_file = os.path.basename(frame_info_list[1].filename)
            
            # Log with caller file and color key
            logger.debug(message_manager.get_log_message("L087", caller_file, self.__color_key))
        except Exception as e:
            # Failed to apply theme color: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Apply theme settings to the frame.

        Args:
            theme_settings (Dict[str, Any]): Theme settings to apply
        """
        try:
            # Check if theme_settings is empty
            if not theme_settings:
                # Empty theme settings for ImageVisibilityToggleFrame
                logger.debug(message_manager.get_log_message("L167"))
                return
                
            # Configure frame with theme settings
            self.configure(**theme_settings)
            # Log message after configuring visibility toggles with theme settings
            logger.debug(message_manager.get_log_message("L088", theme_settings))
        except Exception as e:
            # Failed to configure ImageVisibilityToggleFrame with theme settings: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise
