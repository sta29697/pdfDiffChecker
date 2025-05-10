from __future__ import annotations

import tkinter as tk
from logging import getLogger
from typing import Any, Dict, Union

from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from utils.utils import get_resource_path
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()


class BaseLabel(tk.Label, ThemeColorApplicable, ColoringThemeIF):
    """Base class for label widgets.

    This class provides base functionality for labels that support theme color
    application and automatic registration with WidgetsTracker.

    Attributes:
        __color_key: Key for accessing theme colors specific to this label.
    """

    def __init__(
        self,
        fr: tk.Widget,
        color_key: str,
        text: Union[float, str] = "",
        **kwargs: Any,
    ) -> None:
        """Initialize a new BaseLabel instance.

        Args:
            fr: Parent widget.
            color_key: Key for theme color application.
            text: Label text. Can be string or float. Defaults to empty string.
            **kwargs: Additional keyword arguments for tk.Label.
        """
        # Handle text separately to ensure proper type
        label_args: Dict[str, Any] = {"text": text}

        # Call parent constructor with all arguments
        super().__init__(fr, **label_args, **kwargs)  # type: ignore[arg-type]
        self.__color_key = color_key

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

    def apply_theme_color(self, theme_data: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the label.

        Args:
            theme_data: Dictionary containing theme color data.
        """
        try:
            # Apply theme through _config_widget implementation
            label_theme_config = theme_data.get(self.__color_key, {})
            self._config_widget(label_theme_config)
            
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
            
            # Log with caller file and label key for better traceability
            logger.debug(message_manager.get_log_message("L087", caller_file, f"label_{self.__color_key}"))
        except Exception as e:
            # Failed to apply theme to label: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Dictionary containing theme settings.
        """
        try:
            self.configure(**theme_settings)  # type: ignore[arg-type]
            # Configured label with settings: {settings}
            logger.debug(message_manager.get_log_message("L049", theme_settings))
        except Exception as e:
            # Failed to configure label: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
