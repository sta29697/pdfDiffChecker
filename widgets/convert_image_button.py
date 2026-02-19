from __future__ import annotations
from logging import getLogger
import tkinter as tk
from typing import Any, Callable

from widgets.base_button import BaseButton
from controllers.widgets_tracker import WidgetsTracker
from configurations.message_manager import get_message_manager

# Initialize singleton message manager
message_manager = get_message_manager()

logger = getLogger(__name__)

class ConvertImageButton(BaseButton):
    """Button that triggers the convert image action in ImageOperationApp."""
    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        text: str,
        command: Callable[[], Any],
        **kwargs: Any,
    ) -> None:
        """Initialize the convert image button.

        Args:
            fr: Parent frame.
            color_key: Theme color key.
            text: Button label text.
            command: Callback function for image conversion.
            **kwargs: Additional tk.Button kwargs.
        """
        # Initialize base button
        super().__init__(fr=fr, color_key=color_key, text=text, command=command, **kwargs)
        # Register widget for theme updates
        WidgetsTracker().add_widgets(self)
        # Log initialization of ConvertImageButton with color key
        logger.debug(message_manager.get_log_message("L176", color_key))

    # apply_theme_color is inherited from BaseButton.
    # Do NOT override here — BaseButton stores __color_key with its own
    # name-mangling prefix (_BaseButton__color_key), so accessing
    # self.__color_key from this subclass would resolve to
    # _ConvertImageButton__color_key (which does not exist).
