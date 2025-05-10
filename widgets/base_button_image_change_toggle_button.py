from __future__ import annotations
from logging import getLogger
import tkinter as tk
from typing import Callable, Any
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()

class BaseButtonImageChangeToggleButton(tk.Button):
    """
    A tkinter Button subclass for toggling images on a button, typically used for actions such as 'execute' or 'toggle'.
    If the image cannot be loaded, it falls back to a localized text label. Used in main_tab.py for the execute button.
    """
    def __init__(self, parent: tk.Widget, command: Callable[[], None], image_path: str) -> None:
        """Initialize the button.

        Args:
            parent (tk.Widget): Parent widget
            command (Callable[[], None]): Command to execute when clicked
            image_path (str): Path to the button image
        """
        super().__init__(parent, command=command)
        self.__load_image(image_path)

    def __load_image(self, image_path: str) -> None:
        """Load the button image.

        Args:
            image_path (str): Path to the button image
        """
        try:
            img = tk.PhotoImage(file=image_path)
            # Resize to 1/20 of original
            small = img.subsample(20, 20)
            self.image = small
            self.config(image=self.image)
        except Exception as e:
            # Log failure to load the button image
            logger.error(message_manager.get_log_message("L159", str(e)))
            # Fallback to localized text on image load failure
            # UI text for fallback button label
            self.config(text=message_manager.get_ui_message("U031"))

    def grid(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Shortcut method to call grid on the button.

        Args:
            **kwargs: Additional keyword arguments for grid
        """
        super().grid(**kwargs)

    def configure(self, **kwargs: Any) -> None:  # type: ignore[override]
        """Configure the button with the given options.

        Args:
            **kwargs: Keyword arguments for configuration
        """
        super().configure(**kwargs)
