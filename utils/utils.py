from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
from logging import getLogger
import tkinter as tk
from tkinter import messagebox
from configurations import tool_settings  # project root settings
from configurations.message_manager import get_message_manager
from widgets.balloon_message_window import BalloonMessageWindow
from typing import Optional, Union
from models.class_dictionary import FilePathInfo, FolderPathInfo

logger = getLogger(__name__)
message_manager = get_message_manager()


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for Nuitka.

    Args:
        relative_path (str): Relative path to the resource

    Returns:
        str: Absolute path to the resource

    Raises:
        Exception: If path resolution fails
    """
    try:
        # Determine base path for resources
        if getattr(sys, "frozen", False):
            # Running in a frozen executable (Nuitka)
            base_path = os.path.dirname(sys.executable)
        else:
            # Running in a development environment
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Construct the absolute resource path
        path = os.path.normpath(os.path.join(base_path, relative_path))
        return path
    except Exception as e:
        error_msg = f"Failed to resolve resource path: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)


def get_temp_dir() -> str:
    """Get path to the active runtime temporary directory.

    This function returns the development-local temp directory when running from
    source, and the Windows temporary storage area when running in production.

    Returns:
        str: Path to project's temporary directory

    Raises:
        Exception: If temp directory creation fails
    """
    try:
        temp_dir = str(tool_settings.TEMP_DIR)
        exists_temp = os.path.exists(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        if exists_temp:
            logger.debug(message_manager.get_log_message("L192", temp_dir))
        else:
            # L012: Temporary directory created
            logger.debug(message_manager.get_log_message("L012", temp_dir))
        return temp_dir
    except Exception as e:
        # L013: Error occurred while creating temporary directory
        logger.error(message_manager.get_log_message("L013", e))
        # E001: Show error message (multilingual)
        messagebox.showerror("Error", message_manager.get_message("E001", str(e)))
        raise


def create_unique_file_path(parent_dir: Path, base_name: str, extension: str) -> Path:
    """Return a path to a new file that does not yet exist under ``parent_dir``.

    If ``base_name + extension`` already exists, appends ``（1）``, ``（2）``, …
    before the extension (full-width parentheses), matching main-tab export behavior.

    Args:
        parent_dir: Directory that will contain the file.
        base_name: Filename stem without extension.
        extension: Extension including the leading dot (e.g. ``".pdf"``).

    Returns:
        A non-existing file path (file is not created).
    """
    parent_dir.mkdir(parents=True, exist_ok=True)
    candidate_file = parent_dir / f"{base_name}{extension}"
    if not candidate_file.exists():
        return candidate_file

    suffix_index = 1
    while True:
        numbered_file = parent_dir / f"{base_name}（{suffix_index}）{extension}"
        if not numbered_file.exists():
            return numbered_file
        suffix_index += 1


def create_directories(file_name: str | None = None) -> str:
    """Create necessary directories for the application.

    Creates the following directories if they don't exist:
    - temp: For temporary files
    - logs: For log files
    - docs: For documentation

    Also configures the temporary directory based on program mode.

    Args:
        file_name (str | None, optional): Name of the file for which to create a temporary directory.
            If provided, creates a subdirectory in the temp directory for this file.

    Returns:
        str: Path to the created temporary directory. If file_name is None, returns the base temp directory.
    """
    try:
        # Main processing: use centralized runtime directories for both temp and logs.
        tool_settings.ensure_runtime_directories()
        base_dir = str(tool_settings.RUNTIME_STORAGE_ROOT)
        logger.debug(message_manager.get_log_message("L190", base_dir))

        for path_dir in [str(tool_settings.TEMP_DIR), str(tool_settings.LOG_DIR)]:
            exists = os.path.exists(path_dir)
            logger.debug(message_manager.get_log_message("L191", path_dir, exists))
            if exists:
                logger.debug(message_manager.get_log_message("L192", path_dir))
            else:
                os.makedirs(path_dir, exist_ok=True)
                logger.debug(message_manager.get_log_message("L014", os.path.abspath(path_dir)))

        docs_dir = os.path.join(str(tool_settings.BASE_DIR), "docs")
        if not os.path.exists(docs_dir):
            os.makedirs(docs_dir, exist_ok=True)

        temp_dir = str(tool_settings.TEMP_DIR)
        exists_temp = os.path.exists(temp_dir)
        logger.debug(message_manager.get_log_message("L193", temp_dir, exists_temp))
        if not exists_temp:
            os.makedirs(temp_dir, exist_ok=True)
            logger.debug(message_manager.get_log_message("L015", temp_dir))

        # If file_name is provided, create a subdirectory for this file
        if file_name:
            # Main processing: create a per-source-file subdirectory under ./temp.
            # Use the original filename (stem) as a reference and append '(1)' on conflicts.
            original_stem = Path(os.path.basename(file_name)).stem
            safe_name = "".join(c for c in original_stem if c.isalnum() or c in "._- ()")
            safe_name = safe_name.replace(" ", "_")
            if not safe_name:
                safe_name = "file"

            candidate_dir = os.path.join(temp_dir, safe_name)
            if not os.path.exists(candidate_dir):
                os.makedirs(candidate_dir)
                logger.debug(message_manager.get_log_message("L009", candidate_dir))
                return candidate_dir

            index = 1
            while True:
                numbered_name = f"{safe_name}({index})"
                numbered_dir = os.path.join(temp_dir, numbered_name)
                if not os.path.exists(numbered_dir):
                    os.makedirs(numbered_dir)
                    logger.debug(message_manager.get_log_message("L009", numbered_dir))
                    return numbered_dir
                index += 1

        # Log completion of temporary directory setup
        logger.info(message_manager.get_log_message("L016"))
        return temp_dir
    except Exception as e:
        logger.error(message_manager.get_log_message("L017", e))
        messagebox.showerror("Error", message_manager.get_message("E001", str(e)))
        return temp_dir if "temp_dir" in locals() else "temp"


def clean_temp_dir() -> None:
    """Clean up temporary directory.

    Raises:
        Exception: If cleanup fails
    """
    try:
        temp_dir = get_temp_dir()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        logger.debug(message_manager.get_log_message("L010"))
    except Exception as e:
        logger.error(message_manager.get_log_message("L018", e))
        messagebox.showerror("Error", message_manager.get_message("E001", str(e)))
        raise


def show_balloon_message(parent: tk.Widget, message: str, hover_delay: float = 0.6) -> None:
    """Show a balloon message near the parent widget, with theme support.
    
    Only displays the message if the mouse stays over the widget for hover_delay seconds.
    
    Args:
        parent: The widget to attach the balloon to
        message: The message to display
        hover_delay: Time in seconds mouse must hover before showing balloon
    """
    balloon_data = {}
    
    def on_enter(event: tk.Event) -> None:
        # Start hover timer when mouse enters widget
        balloon_data['hover_timer'] = parent.after(
            int(hover_delay * 1000),
            lambda: create_balloon(event.widget)
        )
    
    def on_leave(event: tk.Event) -> None:
        # Cancel timer if mouse leaves widget before hover_delay
        if 'hover_timer' in balloon_data:
            parent.after_cancel(balloon_data['hover_timer'])
            balloon_data.pop('hover_timer', None)
    
    def create_balloon(widget: tk.Widget) -> None:
        # Only create balloon if hover timer completed
        try:
            # Clear timer reference
            if 'hover_timer' in balloon_data:
                balloon_data.pop('hover_timer', None)
                
            # Create and position balloon
            balloon = BalloonMessageWindow(parent, message, hover_delay=0.0)  # No additional delay
            x = parent.winfo_rootx() + 20
            y = parent.winfo_rooty() + 20
            balloon.geometry(f"+{x}+{y}")
        except Exception as e:
            widget_class = parent.winfo_class()
            logger.error(message_manager.get_log_message("L020", f"{widget_class}: {e}"))
    
    # Setup mouse event bindings
    parent.bind("<Enter>", on_enter)
    parent.bind("<Leave>", on_leave)


def show_message_box(parent: tk.Widget, message: str, message_type: str = "info", title: str = "情報") -> None:
    """Show a message box with theme support."""
    try:
        from widgets.custom_message_box import CustomMessageBox
        CustomMessageBox(parent, message, title=title, message_type=message_type)
    except Exception as e:
        logger.error(message_manager.get_log_message("L194", str(e)))


def resolve_initial_dir(path_obj: Optional[Union[FilePathInfo, FolderPathInfo]]) -> str:
    """Get initial directory path from a FilePathInfo or FolderPathInfo."""
    if path_obj is None:
        return ""
    if isinstance(path_obj, FilePathInfo):
        return str(path_obj.file_path.parent)
    if isinstance(path_obj, FolderPathInfo):
        return str(path_obj.folder_path)
    return ""
