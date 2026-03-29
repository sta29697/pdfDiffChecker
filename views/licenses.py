from __future__ import annotations
from logging import getLogger
from pathlib import Path
from typing import Dict, Optional, Any
import tkinter as tk
from tkinter import scrolledtext

from configurations import tool_settings
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import WidgetsTracker
from widgets.base_tab_widgets import BaseTabWidgets
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
message_manager = get_message_manager()

LICENSE_DOCUMENTS: Dict[str, Path] = {
    "tree": tool_settings.BASE_DIR / "licences_tree.txt",
    "detail": tool_settings.BASE_DIR / "licences.txt",
}

LICENSE_TAB_TEXTS: Dict[str, Dict[str, str]] = {
    "ja": {
        "tree_button": "依存ツリー概要を表示",
        "detail_button": "ライセンス全文を表示",
        "path_prefix": "参照中の文書:",
        "missing_title": "文書未検出",
        "missing_body": "指定されたライセンス文書が見つかりません。",
        "tree_heading": "ランタイム依存ライセンス概要",
        "detail_heading": "ライセンス詳細文書",
    },
    "en": {
        "tree_button": "Show Dependency Tree Summary",
        "detail_button": "Show Full License Text",
        "path_prefix": "Current document:",
        "missing_title": "Document Not Found",
        "missing_body": "The selected license document could not be found.",
        "tree_heading": "Runtime Dependency License Summary",
        "detail_heading": "Detailed License Document",
    },
}


class LicensesApp(tk.Frame, ColoringThemeIF):
    """License tab that loads workspace-managed license documents."""

    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        """Initialize the licenses view.

        Args:
            master: Parent widget.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(master, **kwargs)
        WidgetsTracker().add_widgets(self)
        self.root = master
        self.base_widgets = BaseTabWidgets()
        self._current_document_key = "tree"
        self._tree_button: Optional[tk.Button] = None
        self._detail_button: Optional[tk.Button] = None

        self.frame = tk.Frame(self)
        self.frame.pack(expand=True, fill="both")

        self._toolbar_frame = tk.Frame(self.frame)
        self._toolbar_frame.pack(fill="x", padx=8, pady=(8, 4))

        self._tree_button = tk.Button(
            self._toolbar_frame,
            command=lambda: self._set_current_document("tree"),
        )
        self._tree_button.pack(side="left", padx=(0, 8))

        self._detail_button = tk.Button(
            self._toolbar_frame,
            command=lambda: self._set_current_document("detail"),
        )
        self._detail_button.pack(side="left")

        self.licenses_text = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, font=("Meiryo UI", 10))
        self.licenses_text.pack(expand=True, fill="both", padx=8, pady=(0, 8))
        self.licenses_text.config(state="disabled")

        self.refresh_language()
        self.apply_theme_color(ColorThemeManager.get_current_theme())  # type: ignore[arg-type]

    def _get_current_language_texts(self) -> Dict[str, str]:
        """Return localized UI texts for the current language.

        Returns:
            Dict[str, str]: Localized text map.
        """
        current_language = str(getattr(message_manager, "_language", "ja") or "ja")
        return LICENSE_TAB_TEXTS.get(current_language, LICENSE_TAB_TEXTS["ja"])

    def _read_license_document(self, document_key: str) -> str:
        """Read the selected license document from disk.

        Args:
            document_key: Logical document identifier.

        Returns:
            str: Loaded document text or a localized fallback message.
        """
        texts = self._get_current_language_texts()
        document_path = LICENSE_DOCUMENTS[document_key]
        if not document_path.exists():
            return f"{texts['missing_title']}\n\n{texts['missing_body']}\n{document_path}"
        return document_path.read_text(encoding="utf-8")

    def _render_current_document(self) -> None:
        """Render the currently selected license document into the text area."""
        texts = self._get_current_language_texts()
        heading = texts["tree_heading"] if self._current_document_key == "tree" else texts["detail_heading"]
        document_body = self._read_license_document(self._current_document_key)

        self.licenses_text.config(state="normal")
        self.licenses_text.delete("1.0", tk.END)
        self.licenses_text.insert("1.0", f"{heading}\n{'=' * len(heading)}\n\n{document_body}")
        self.licenses_text.config(state="disabled")

        if self._tree_button is not None:
            self._tree_button.configure(
                text=texts["tree_button"],
                relief=tk.SUNKEN if self._current_document_key == "tree" else tk.RAISED,
            )
        if self._detail_button is not None:
            self._detail_button.configure(
                text=texts["detail_button"],
                relief=tk.SUNKEN if self._current_document_key == "detail" else tk.RAISED,
            )

    def _set_current_document(self, document_key: str) -> None:
        """Switch the visible license document.

        Args:
            document_key: Logical document identifier.
        """
        if document_key not in LICENSE_DOCUMENTS:
            return
        self._current_document_key = document_key
        self._render_current_document()

    def bind_window_events(self, master: tk.Tk | tk.Toplevel) -> None:
        """Keep tab mode free from direct window event bindings.

        Args:
            master: Parent window.
        """
        _ = master
        return

    def apply_theme_color(self, theme: Dict[str, Dict[str, str]]) -> None:
        """Apply the current color theme to the license tab widgets.

        Args:
            theme: Theme data dictionary.
        """
        try:
            frame_theme = dict(theme.get("Frame", {})) if isinstance(theme, dict) else {}
            window_theme = dict(theme.get("Window", {})) if isinstance(theme, dict) else {}
            text_theme = dict(theme.get("text_box", {})) if isinstance(theme, dict) else {}
            button_theme = dict(theme.get("process_button", theme.get("Button", {}))) if isinstance(theme, dict) else {}

            frame_bg = frame_theme.get("bg", window_theme.get("bg", "#ffffff"))
            frame_fg = frame_theme.get("fg", "#000000")
            text_bg = text_theme.get("bg", frame_bg)
            text_fg = text_theme.get("fg", frame_fg)

            self.configure(bg=frame_bg)
            self.frame.configure(bg=frame_bg)
            self._toolbar_frame.configure(bg=frame_bg)
            self.licenses_text.configure(
                bg=text_bg,
                fg=text_fg,
                insertbackground=text_fg,
                selectbackground=button_theme.get("activebackground", frame_bg),
                selectforeground=button_theme.get("activeforeground", text_fg),
            )
            try:
                self.licenses_text.vbar.configure(
                    bg=button_theme.get("bg", frame_bg),
                    fg=button_theme.get("fg", frame_fg),
                    activebackground=button_theme.get("activebackground", frame_bg),
                    troughcolor=frame_bg,
                    highlightbackground=frame_bg,
                )
            except Exception:
                pass

            for button in [self._tree_button, self._detail_button]:
                if button is None:
                    continue
                button.configure(
                    bg=button_theme.get("bg", frame_bg),
                    fg=button_theme.get("fg", frame_fg),
                    activebackground=button_theme.get("activebackground", frame_bg),
                    activeforeground=button_theme.get("activeforeground", frame_fg),
                    highlightbackground=button_theme.get("activebackground", frame_bg),
                    highlightcolor=button_theme.get("activebackground", frame_bg),
                )
        except Exception as e:
            logger.error(message_manager.get_log_message("L145", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Theme settings to apply.
        """
        self.configure(**theme_settings)  # type: ignore[arg-type]

    def refresh_language(self) -> None:
        """Refresh localized labels and the currently visible document."""
        self._render_current_document()
        logger.debug(message_manager.get_log_message("L228", getattr(message_manager, "_language", "ja")))


