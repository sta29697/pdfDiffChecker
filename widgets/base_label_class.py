from __future__ import annotations

from logging import getLogger
import tkinter as tk

from utils.utils import get_resource_path
from widgets.base_label import BaseLabel
from widgets.base_tab_widgets import BaseTabWidgets as btw
from configurations.message_manager import get_message_manager
from controllers.app_state import AppState

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()


class BaseLabelClass(BaseLabel):
    """Base class for all label widgets in the application.

    This class extends BaseLabel to provide additional functionality
    specific to the application's needs.
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        text: str,
    ) -> None:
        """Initialize the base label class.

        Args:
            fr (tk.Frame): Parent frame
            color_key (str): Key for color theming
            text (str): Label text
        """
        super().__init__(fr=fr, color_key=color_key, text=text, font=btw.base_font)
        
        # Get current file name for better context instead of parent widget info
        import os
        # Extract just the filename without path or extension for cleaner logs
        current_file = os.path.basename(__file__)
        
        # Log label initialization with file context information for improved debugging
        # Note: Using file name instead of parent widget as requested by user
        # Only log if we're past initialization or verbose logging is enabled
        if AppState.should_log_widget_init():
            context_info = f"{text} (in {current_file}, color_key={color_key})"
            logger.debug(message_manager.get_log_message("L202", context_info))
