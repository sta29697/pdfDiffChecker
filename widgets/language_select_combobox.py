import tkinter as tk
from tkinter import ttk
from configurations.message_manager import get_message_manager
from configurations.tool_settings import LANGUAGE_CODES
from configurations.user_setting_manager import UserSettingManager
from utils.utils import show_balloon_message

# Initialize singleton message manager
message_manager = get_message_manager()

class LanguageSelectCombo(ttk.Combobox):
    """Language selection combobox widget."""

    def __init__(self, parent: tk.Widget) -> None:
        """Initialize language selection combobox."""
        self.parent = parent
        self.settings = UserSettingManager()
        values = [LANGUAGE_CODES["ja"], LANGUAGE_CODES["en"]]
        super().__init__(self.parent, values=values, state="readonly")
        lang = self.settings.get_setting("language", "japanese")
        current = LANGUAGE_CODES["ja"] if lang == "japanese" else LANGUAGE_CODES["en"]
        self.set(current)
        self.bind("<Enter>", self._on_hover)
        self.bind("<<ComboboxSelected>>", self._on_select)

    # Show balloon informing restart required on hover
    def _on_hover(self, event: tk.Event) -> None:
        # Display balloon message on the combobox itself for better positioning
        show_balloon_message(self, message_manager.get_message("M039"))

    # Notify application restart needed after language selection
    def _on_select(self, event: tk.Event) -> None:
        selected = self.get()
        code = "japanese" if selected == LANGUAGE_CODES["ja"] else "english"
        self.settings.update_setting("language", code)
        
        # Create a notification label positioned close to the combobox
        # Find existing notification label and destroy it if exists
        for widget in self.parent.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, "notification_tag"):
                widget.destroy()
                
        # Create new notification label
        label = tk.Label(self.parent, text=message_manager.get_message("M040"))
        # Set a custom attribute using setattr to avoid mypy errors
        setattr(label, "notification_tag", True)
        # Position the label next to the combobox
        label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
