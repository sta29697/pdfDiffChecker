from __future__ import annotations

from utils.utils import get_resource_path
import inspect
import tkinter as tk
from logging import getLogger
import os
from typing import Any, Callable

from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")

# Initialize singleton message manager
message_manager = get_message_manager()


class BaseButton(tk.Button, ThemeColorApplicable, ColoringThemeIF):
    """Base class for button widgets.

    This class provides base functionality for buttons that support theme color
    application and automatic registration with WidgetsTracker.

    Attributes:
        __color_key: Key for accessing theme colors specific to this button.
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        text: str | None = "",
        command: Callable[[], Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a new BaseButton instance.

        Args:
            fr: Parent frame.
            color_key: Key for theme color application.
            text: Button text. Defaults to empty string.
            command: Callback function for button click. Defaults to None.
            **kwargs: Additional keyword arguments for tk.Button.
        """
        # Handle command separately to avoid passing None
        button_args: dict[str, Any] = {"text": text if text is not None else ""}
        if command is not None:
            button_args["command"] = command

        # Merge button_args with kwargs
        all_kwargs = {**button_args, **kwargs}

        # Call parent constructor with all arguments
        # type: ignore[arg-type]
        super().__init__(fr, **all_kwargs)  # type: ignore[arg-type]
        self.__color_key = color_key
        self.__persistent_visual_config = {
            key: kwargs[key]
            for key in [
                "relief",
                "bd",
                "borderwidth",
                "highlightthickness",
                "highlightbackground",
                "highlightcolor",
            ]
            if key in kwargs
        }
        self._disabled_visual_bg: str | None = None
        self._disabled_visual_fg: str | None = None

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

    def apply_theme_color(self, theme_data: dict[str, Any]) -> None:
        """
        Applies theme colors to the button.

        Args:
            theme_data (dict[str, Any]): Theme color data from ColorThemeManager. Accepts ThemeColors type or dict.
        """
        try:
            # Get theme configuration for this button
            theme_config = theme_data.get(self.__color_key, {})
            
            # Check if theme configuration is empty
            if not theme_config:
                # Theme configuration not found for button - add file location info
                button_info = f"{self.__color_key} (in {self.__class__.__module__}.{self.__class__.__name__})"
                logger.debug(message_manager.get_log_message("M041", button_info))
                return
                
            # Remove unsupported options before applying theme
            button_theme_config = dict(theme_config)
            # Main processing: never override runtime enabled/disabled state.
            button_theme_config.pop("state", None)
            button_theme_config.pop("disabledbackground", None)
            button_theme_config.update(self.__persistent_visual_config)
            self.configure(**button_theme_config)  # type: ignore[arg-type]
            if str(self.cget("state")) == str(tk.DISABLED):
                disabled_bg = str(self._disabled_visual_bg or self.cget("bg"))
                disabled_fg = str(self._disabled_visual_fg or self.cget("disabledforeground"))
                self.configure(
                    bg=disabled_bg,
                    fg=disabled_fg,
                    activebackground=disabled_bg,
                    activeforeground=disabled_fg,
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
            # Failed to apply theme to button: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Applies theme settings to the button widget.

        Args:
            theme_settings (dict[str, Any]): Theme settings to apply
        """
        try:
            # Remove unsupported options before configuring widget
            filtered_settings = dict(theme_settings)
            # Main processing: never override runtime enabled/disabled state.
            filtered_settings.pop("state", None)
            filtered_settings.pop("disabledbackground", None)
            self.configure(**filtered_settings)  # type: ignore[arg-type]
            if str(self.cget("state")) == str(tk.DISABLED):
                disabled_bg = str(self._disabled_visual_bg or self.cget("bg"))
                disabled_fg = str(self._disabled_visual_fg or self.cget("disabledforeground"))
                self.configure(
                    bg=disabled_bg,
                    fg=disabled_fg,
                    activebackground=disabled_bg,
                    activeforeground=disabled_fg,
                )
            # Configured button with settings: {settings}
            logger.debug(message_manager.get_log_message("L079", theme_settings))
        except Exception as e:
            # Failed to configure widget: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
