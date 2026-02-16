from __future__ import annotations

from typing import Any, Callable, Optional

import tkinter as tk
import tkinter.font as tkfont
from logging import getLogger

from configurations import tool_settings
from utils.utils import get_resource_path
from widgets.base_button import BaseButton
from widgets.base_tab_widgets import BaseTabWidgets as btw
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()


class BasePageChangeButton(BaseButton):
    """Base class for page change buttons.

    This class provides base functionality for buttons that:
    1. Handle page navigation
    2. Support theme color application
    3. Manage page state

    Attributes:
        __fr (tk.Frame): Parent frame
        __color_key (str): Key for color theming
        __text (str): Button text
        __theme_dict (Dict[str, Any]): Theme dictionary
        __fg (str): Font color
        __bg (str): Background color
        __acfg (str): Active font color
        __acbg (str): Active background color
    """

    _bold_font: tkfont.Font | None = None

    @classmethod
    def _get_bold_font(cls) -> tkfont.Font | None:
        """Get a bold font instance used for arrow buttons.

        Returns:
            tkinter.font.Font | None: Bold font if available, otherwise None.
        """
        # Main processing: derive a bold font from the app's base font.
        try:
            if cls._bold_font is not None:
                return cls._bold_font

            base_font = getattr(btw, "base_font", None)
            if base_font is None:
                try:
                    btw.base_font = tkfont.Font(
                        family=tool_settings.font_family,
                        size=tool_settings.font_size,
                    )
                except Exception:
                    return None

                base_font = getattr(btw, "base_font", None)
                if base_font is None:
                    return None

            base_actual = base_font.actual()
            base_actual["weight"] = "bold"
            cls._bold_font = tkfont.Font(**base_actual)
            return cls._bold_font
        except Exception:
            return None

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        text: str,
        command: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the page change button.

        Args:
            fr: Parent frame
            color_key: Key for color theming
            text: Button text (should be set via MessageManager for i18n)
            command: Callback function when button is clicked
            **kwargs: Additional keyword arguments for tk.Button
        """
        # Check if text is a UI message code or direct text
        if text.startswith("U") and text[1:].isdigit():
            # This is a UI message code
            button_text = message_manager.get_ui_message(text)
        else:
            # Replace problematic characters with safer alternatives
            # Replace < with ← and > with → to avoid HTML/XML parsing issues
            if text == "<":
                button_text = "←"
                # Log the button text replacement
                logger.debug(message_manager.get_log_message("L280", text, button_text))
            elif text == ">":
                button_text = "→"
                # Log the button text replacement
                logger.debug(message_manager.get_log_message("L280", text, button_text))
            else:
                # This is direct text
                button_text = text

        if "font" not in kwargs:
            bold_font = self._get_bold_font()
            if bold_font is not None:
                kwargs["font"] = bold_font

        # Initialize the button with text
        # Note: BaseButton.__init__ sets __color_key, registers with
        # WidgetsTracker, and provides apply_theme_color / _config_widget.
        # No need to duplicate them here (doing so caused AttributeError
        # due to Python name mangling + initialization order).
        super().__init__(fr=fr, color_key=color_key, text=button_text, command=command, **kwargs)
