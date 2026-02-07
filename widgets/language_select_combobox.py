import tkinter as tk
from tkinter import ttk
from configurations.message_manager import get_message_manager
from configurations.tool_settings import LANGUAGE_CODES
from configurations.user_setting_manager import UserSettingManager
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import ensure_contrast_color
from utils.utils import show_balloon_message

# Initialize singleton message manager
message_manager = get_message_manager()

class LanguageSelectCombo(ttk.Combobox):
    """Language selection combobox widget."""

    def _normalize_language_value(self, language_value: str) -> str:
        """Normalize language values from settings.

        Args:
            language_value (str): Language value from settings.

        Returns:
            str: Normalized language code, either "ja" or "en".
        """
        value = (language_value or "").strip().lower()
        if value in {"ja", "japanese", "jp"}:
            return "ja"
        if value in {"en", "english"}:
            return "en"
        return "ja"

    def __init__(self, parent: tk.Widget) -> None:
        """Initialize language selection combobox."""
        self.parent = parent
        self.settings = UserSettingManager()
        values = [LANGUAGE_CODES["ja"], LANGUAGE_CODES["en"]]
        super().__init__(self.parent, values=values, state="readonly")
        lang = self.settings.get_setting("language", "ja")
        lang_code = self._normalize_language_value(str(lang))
        self._initial_language_code = lang_code
        current = LANGUAGE_CODES["ja"] if lang_code == "ja" else LANGUAGE_CODES["en"]
        self.set(current)
        self.bind("<Enter>", self._on_hover)
        self.bind("<<ComboboxSelected>>", self._on_select)

    def _remove_notification_labels(self) -> None:
        """Remove existing language change notification labels from the parent.

        Returns:
            None
        """
        for widget in self.parent.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, "notification_tag"):
                widget.destroy()

    def _get_selected_language_code(self) -> str:
        """Get the normalized language code from current combobox selection.

        Returns:
            str: Normalized language code, either "ja" or "en".
        """
        selected = self.get()
        code = "japanese" if selected == LANGUAGE_CODES["ja"] else "english"
        return self._normalize_language_value(code)

    def _create_notification_label(self) -> None:
        """Create a themed notification label for language change guidance.

        Returns:
            None
        """
        theme = ColorThemeManager.get_current_theme()
        theme_name = ColorThemeManager.get_current_theme_name()

        window_bg = str(theme.get("Window", {}).get("bg", "#ffffff"))
        label_fg_default = str(theme.get("Label", {}).get("fg", "#000000"))

        accent_border = str(
            theme.get("comparison_file_path_label", {}).get(
                "fg", theme.get("primary_combobox", {}).get("highlightcolor", "#ff5a74")
            )
        )

        # Main processing: pick per-theme background candidates to stand out.
        if theme_name == "light":
            label_bg = str(theme.get("page_number_entry", {}).get("bg", window_bg))
        elif theme_name == "pastel":
            label_bg = str(
                theme.get("comparison_file_path_label", {}).get("bg", window_bg)
            )
        else:
            label_bg = str(theme.get("Notebook", {}).get("tab_bg", window_bg))

        label_fg = ensure_contrast_color(label_fg_default, label_bg)

        label = tk.Label(
            self.parent,
            text=message_manager.get_message("M040"),
            bg=label_bg,
            fg=label_fg,
            highlightthickness=2,
            highlightbackground=accent_border,
            highlightcolor=accent_border,
        )
        # Set a custom attribute using setattr to avoid mypy errors
        setattr(label, "notification_tag", True)
        # Position the label next to the combobox
        label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    # Show balloon informing restart required on hover
    def _on_hover(self, event: tk.Event) -> None:
        # Display balloon message on the combobox itself for better positioning
        show_balloon_message(self, message_manager.get_message("M039"))

    # Notify application restart needed after language selection
    def _on_select(self, event: tk.Event) -> None:
        selected = self.get()
        code = "japanese" if selected == LANGUAGE_CODES["ja"] else "english"
        self.settings.update_setting("language", code)

        self._remove_notification_labels()

        # If the user reverted to the initial language, hide the guidance message.
        if self._get_selected_language_code() == self._initial_language_code:
            return

        self._create_notification_label()
