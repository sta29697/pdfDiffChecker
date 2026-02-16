from __future__ import annotations
import tkinter as tk
from typing import Any, Callable, Optional
from widgets.base_button import BaseButton
from configurations.message_manager import get_message_manager

class InsertBlankPageButton(BaseButton):
    """
    Button to insert a blank PNG page into either base or comp folder.
    Uses BaseButton for theme and MessageManager for i18n.
    If both images are visible ("base_and_comp"), then no insertion is performed,
    and a warning message is displayed to the user.
    """

    def __init__(
        self,
        master: tk.Frame,
        color_key: str,
        command: Optional[Callable[[], None]] = None,
        **kwargs: Any
    ) -> None:
        """
        Initialize the button for inserting blank pages.

        Args:
            master: Parent frame where this button will be placed
            color_key: Key for color theming
            command: Callback function when button is clicked
            **kwargs: Additional keyword arguments for tk.Button
        """
        message_manager = get_message_manager()
        label = message_manager.get_ui_message("U038")
        # Note: BaseButton.__init__ sets __color_key, registers with
        # WidgetsTracker, and provides apply_theme_color / _config_widget.
        # No need to duplicate them here (doing so caused AttributeError
        # due to Python name mangling + initialization order).
        super().__init__(master, color_key=color_key, text=label, command=command, **kwargs)  # type: ignore[arg-type]
