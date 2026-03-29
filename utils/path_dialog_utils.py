"""
Utility functions for file and folder selection dialogs.
"""
from tkinter import filedialog
from typing import Any, List, Tuple, Optional
from logging import getLogger
from configurations.message_manager import get_message_manager
from utils.path_normalization import normalize_host_path

logger = getLogger(__name__)
# Obtain the singleton message manager instance
message_manager = get_message_manager()


def ask_file_dialog(
    initialdir: str,
    title_code: str,
    filetypes: List[Tuple[str, str]],
    typevariable: Any | None = None,
) -> Optional[str]:
    """Ask user to select a file and return the selected path.

    Args:
        initialdir: Initial directory for dialog.
        title_code: Message code for dialog title.
        filetypes: File type filters.
        typevariable: Optional Tk variable that stores the selected filter pattern.

    Returns:
        Selected file path or None if cancelled.
    """
    title = message_manager.get_ui_message(title_code)
    try:
        dialog_kwargs = {
            "initialdir": initialdir,
            "title": title,
            "filetypes": filetypes,
        }
        if typevariable is not None:
            dialog_kwargs["typevariable"] = typevariable
        file_path = filedialog.askopenfilename(
            **dialog_kwargs,
        )
        if not file_path:
            return None
        return normalize_host_path(file_path)
    except Exception as e:
        logger.error(message_manager.get_log_message("L067", str(e)))
        return None


def ask_folder_dialog(
    initialdir: str,
    title_code: str,
) -> Optional[str]:
    """Ask user to select a folder and return the selected path.

    Args:
        initialdir: Initial directory for dialog.
        title_code: Message code for dialog title.

    Returns:
        Selected folder path or None if cancelled.
    """
    title = message_manager.get_ui_message(title_code)
    try:
        folder_path = filedialog.askdirectory(
            initialdir=initialdir,
            title=title,
        )
        if not folder_path:
            return None
        return normalize_host_path(folder_path)
    except Exception as e:
        logger.error(message_manager.get_log_message("L067", str(e)))
        return None
