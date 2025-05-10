"""
Utility functions for file and folder selection dialogs.
"""
from tkinter import filedialog
from typing import List, Tuple, Optional
from logging import getLogger
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Obtain the singleton message manager instance
message_manager = get_message_manager()


def ask_file_dialog(
    initialdir: str,
    title_code: str,
    filetypes: List[Tuple[str, str]],
) -> Optional[str]:
    """Ask user to select a file and return the selected path.

    Args:
        initialdir: Initial directory for dialog.
        title_code: Message code for dialog title.
        filetypes: File type filters.

    Returns:
        Selected file path or None if cancelled.
    """
    title = message_manager.get_ui_message(title_code)
    try:
        file_path = filedialog.askopenfilename(
            initialdir=initialdir,
            title=title,
            filetypes=filetypes,
        )
        return file_path or None
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
        return folder_path or None
    except Exception as e:
        logger.error(message_manager.get_log_message("L067", str(e)))
        return None
