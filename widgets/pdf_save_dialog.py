from __future__ import annotations

import os
import datetime
import tkinter as tk
from logging import getLogger
from typing import Callable, Dict, Any, Optional

from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_label_class import BaseLabelClass
from widgets.base_entry_class import BaseEntryClass
from utils.utils import show_balloon_message
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()


class PDFSaveDialog(tk.Toplevel, ColoringThemeIF, ThemeColorApplicable):
    """Dialog for saving PDF files with a custom name."""
    def __init__(
        self,
        parent: tk.Widget,
        on_save: Callable[[str, tk.Widget], None],
        # UI text for PDF save dialog title
        title: str = message_manager.get_ui_message("U041"),  # Save PDF
    ) -> None:
        """Initialize the PDF save dialog.

        Args:
            parent: Parent widget
            on_save: Callback function when save is confirmed
            title: Dialog title
        """
        super().__init__(parent)
        self.title(title)
        # Set transient only if parent is Tk or Toplevel
        if isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.transient(parent)
        else:
            self.transient(None)
        self.grab_set()

        default_base = "output"
        if hasattr(parent, 'get_base_file_path'):
            base_path = parent.get_base_file_path()
            if base_path:
                default_base = os.path.splitext(os.path.basename(base_path))[0]
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{default_base}_diff_{now}.pdf"
        self.__filename_var: tk.StringVar = tk.StringVar(value=default_filename)
        self.__on_save: Callable[[str, tk.Widget], None] = on_save
        self.__main_frame: Optional[tk.Frame] = None
        self.__button_frame: Optional[tk.Frame] = None
        self.__save_button: Optional[tk.Button] = None
        self.__cancel_button: Optional[tk.Button] = None
        self.__filename_entry: Optional[BaseEntryClass] = None
        WidgetsTracker().add_widgets(self)
        self.__create_widgets()
        # Ensure filename entry widget is initialized before showing guidance
        assert self.__filename_entry is not None
        # UI balloon for filename entry guidance
        show_balloon_message(self.__filename_entry.path_entry, message_manager.get_ui_message("U043"))
        self.__setup_bindings()
        self.update_idletasks()
        width = 300
        height = 150
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.focus_set()
        self.wait_window()

    def apply_theme_color(self, theme_data: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the dialog and its components.

        Args:
            theme_data: Dictionary containing theme color data.
        """
        try:
            # Apply theme to the dialog itself
            subwindow_theme_config = theme_data.get("SubWindow", {})
            self.configure(**subwindow_theme_config)

            # Apply theme to the main frame
            frame_theme_config = theme_data.get("Frame", {})
            if self.__main_frame:
                self.__main_frame.configure(**frame_theme_config)

            # Apply theme to the button frame
            if self.__button_frame:
                self.__button_frame.configure(**frame_theme_config)

            # Apply theme to the buttons
            button_theme_config = theme_data.get("Button", {})
            if self.__save_button:
                self.__save_button.configure(**button_theme_config)
            if self.__cancel_button:
                self.__cancel_button.configure(**button_theme_config)

            # Applied theme to PDFSaveDialog with provided theme data
            logger.debug(message_manager.get_log_message("L102", theme_data))
        except Exception as e:
            # Failed to apply theme to PDFSaveDialog: {0}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Dictionary containing theme settings.
        """
        try:
            self.configure(**theme_settings)
            # Configured PDFSaveDialog with settings: {0}
            logger.debug(message_manager.get_log_message("L103", theme_settings))
        except Exception as e:
            # Failed to configure PDFSaveDialog: {0}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def __create_widgets(self) -> None:
        """Create and layout the dialog widgets."""
        # Main frame
        self.__main_frame = tk.Frame(self, padx=10, pady=10)
        self.__main_frame.grid(row=0, column=0, sticky="nsew")

        # Filename label and entry
        filename_label = BaseLabelClass(
            fr=self.__main_frame,
            color_key="Label",
            text=message_manager.get_ui_message("U042")
        )
        filename_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.__filename_entry = BaseEntryClass(
            fr=self.__main_frame,
            color_key="Entry",
        )
        self.__filename_entry.path_entry.config(textvariable=self.__filename_var)
        self.__filename_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")


        # Buttons frame
        self.__button_frame = tk.Frame(self.__main_frame)
        self.__button_frame.grid(row=1, column=0, columnspan=2, pady=10)

        # Save button
        self.__save_button = tk.Button(
            self.__button_frame,
            text=message_manager.get_ui_message("U044"), # Save
            command=self.__on_save_click,
        )
        self.__save_button.grid(row=0, column=0, padx=5)

        # Cancel button
        self.__cancel_button = tk.Button(
            self.__button_frame,
            text=message_manager.get_ui_message("U045"), # Cancel
            command=self.destroy,
        )
        self.__cancel_button.grid(row=0, column=1, padx=5)

        # Configure grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.__main_frame.columnconfigure(1, weight=1)


    def __setup_bindings(self) -> None:
        """Setup keyboard bindings."""
        self.bind("<Return>", lambda e: self.__on_save_click())
        self.bind("<Escape>", lambda e: self.destroy())

    def __on_save_click(self) -> None:
        """Handle save button click."""
        filename = self.__filename_var.get().strip()
        if not filename:
            filename_entry = self.__filename_entry
            assert filename_entry is not None
            show_balloon_message(
                filename_entry.path_entry,
                message_manager.get_ui_message("U046")
            )
            return

        # Add .pdf extension if not present
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        try:
            # Call export handler with filename and entry widget as parent_widget
            filename_entry = self.__filename_entry
            assert filename_entry is not None
            self.__on_save(filename, filename_entry.path_entry)
            self.destroy()
        except Exception as e:
            # Failed to save PDF: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            # Show error balloon message on filename entry
            filename_entry = self.__filename_entry
            assert filename_entry is not None
            show_balloon_message(
                filename_entry.path_entry,
                message_manager.get_ui_message("U047", str(e))
            )
