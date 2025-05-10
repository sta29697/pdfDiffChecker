from __future__ import annotations

from pathlib import Path
import tkinter as tk
from logging import getLogger
from tkinter import filedialog as fd
from tkinter import messagebox
from typing import Any, Optional, Callable, Dict

from configurations.user_setting_manager import UserSettingManager
from controllers.widgets_tracker import WidgetsTracker, ThemeColorApplicable
from models.class_dictionary import FilePathInfo, FolderPathInfo
from utils.utils import get_resource_path
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_path_entry import BasePathEntry
from configurations.message_manager import get_message_manager
from controllers.color_theme_manager import ColorThemeManager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()

class BasePathSelectButton(tk.Frame, ColoringThemeIF, ThemeColorApplicable):
    """Base class for path selection buttons.

    This class provides base functionality for buttons that:
    1. Handle file/directory path selection
    2. Support theme color application
    3. Manage path selection dialogs
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        entry_setting_key: str,
        share_path_entry: BasePathEntry,
        text: str = "",
        command: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the path select button.

        Args:
            fr (tk.Frame): Parent frame
            color_key (str): Color key for theme application
            entry_setting_key (str): Key for entry widget settings
            share_path_entry (BasePathEntry): Shared path entry widget
            text (str): Custom button text (default: "")
            command (Optional[Callable[..., Any]]): Custom button command (default: None)
            **kwargs: Additional keyword arguments for tk.Frame
        """
        self.__fr = fr
        # Store custom button text and command
        self.__button_text = text
        self.__button_command = command
        super().__init__(master=self.__fr, **kwargs)
        self.__color_key = color_key
        self.__entry_setting_key = entry_setting_key
        self.__share_path_entry = share_path_entry
        self.__path_info: Optional[FilePathInfo | FolderPathInfo] = None
        self.__settings = UserSettingManager()

        # Get theme colors from ColorThemeManager
        ctm = ColorThemeManager()
        # Convert TypedDict theme to plain dict for safe get()
        theme_dict: Dict[str, Any] = dict(ctm.get_current_theme())
        base_image_theme_config: Dict[str, Any] = theme_dict.get(self.__color_key, {})

        try:
            # Determine button text and command
            # Determine button text: use custom text or default UI message
            btn_text = self.__button_text or message_manager.get_ui_message("U019")
            btn_command = self.__button_command or self._select_path
            # Create button inside this Frame to avoid mix of pack/grid in parent
            self.path_select_btn = tk.Button(
                self,
                text=btn_text,
                command=btn_command,
                **base_image_theme_config,
            )
            self.path_select_btn.pack(fill="both", expand=True)
            # Successfully created path select button
            logger.debug(message_manager.get_log_message("L083"))
        except Exception as e:
            # Failed to create path select button: {0}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

    def _select_path(self) -> None:
        """Open file dialog and handle path selection."""
        try:
            if self.__entry_setting_key == "base_file_path":
                # Dialog title for selecting base file
                file_path = fd.askopenfilename(
                    title=message_manager.get_ui_message("U003"),
                    filetypes=[("PDF files", "*.pdf"), ("TIFF files", "*.tif")],
                )
                if file_path:
                    path = Path(file_path)
                    self.__share_path_entry.path_var.set(str(path))
                    self.__path_info = FilePathInfo(path)
            elif self.__entry_setting_key == "comparison_file_path":
                # Dialog title for selecting comparison file
                file_path = fd.askopenfilename(
                    title=message_manager.get_ui_message("U003"),
                    filetypes=[("PDF files", "*.pdf"), ("TIFF files", "*.tif")],
                )
                if file_path:
                    path = Path(file_path)
                    self.__share_path_entry.path_var.set(str(path))
                    self.__path_info = FilePathInfo(path)
            else:
                # Dialog title for selecting folder
                folder_path = fd.askdirectory(
                    title=message_manager.get_ui_message("U032")
                )
                if folder_path:
                    path = Path(folder_path)
                    self.__share_path_entry.path_var.set(str(path))
                    self.__path_info = FolderPathInfo(path)
        except Exception as e:
            # Failed to select path: use specific log code based on entry_setting_key
            code = {
                "base_file_path": "L077",
                "comparison_file_path": "L078"
            }.get(self.__entry_setting_key, "L079")
            logger.error(message_manager.get_log_message(code, str(e)))
            # Show warning dialog title for invalid path
            messagebox.showwarning(
                message_manager.get_ui_message("U033"),
                # Show warning dialog message for invalid path
                message_manager.get_ui_message("U034")
            )

    def get_path_info(self) -> Optional[FilePathInfo | FolderPathInfo]:
        """Get the selected path info.

        Returns:
            Optional[FilePathInfo | FolderPathInfo]: Selected path info
        """
        return self.__path_info

    def apply_theme_color(self, theme_colors: dict[str, Any]) -> None:
        """
        Applies theme colors to the widget.

        Args:
            theme_colors (dict[str, Any]): Theme color data from ColorThemeManager. Accepts ThemeColors type or dict.
        """
        theme_data = theme_colors.get(self.__color_key, {})
        self.path_select_btn.configure(**theme_data)

    def _config_widget(self, theme_settings: dict[str, Any]) -> None:
        """
        Applies theme settings to the button widget.

        Args:
            theme_settings (dict[str, Any]): Theme settings to apply.
        """
        self.path_select_btn.configure(**theme_settings)
