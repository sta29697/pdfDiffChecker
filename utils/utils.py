from __future__ import annotations

import os
import sys
import shutil
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
    """Get path to temporary directory within the project folder.

    This function returns the path to the 'temp' directory in the project folder.
    It does NOT use system's temporary directory (tempfile.gettempdir()) to avoid
    file dispersion issues.

    Returns:
        str: Path to project's temporary directory

    Raises:
        Exception: If temp directory creation fails
    """
    try:
        # Use project directory instead of system temp directory
        from configurations import tool_settings
        base_dir = str(tool_settings.BASE_DIR)
        temp_dir = os.path.join(base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        # L012: Temporary directory created
        logger.debug(message_manager.get_log_message("L012", temp_dir))
        return temp_dir
    except Exception as e:
        # L013: Error occurred while creating temporary directory
        logger.error(message_manager.get_log_message("L013", e))
        # E001: Show error message (multilingual)
        messagebox.showerror("Error", message_manager.get_message("E001", str(e)))
        raise


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
        # Determine project root directory
        base_dir = str(tool_settings.BASE_DIR)
        # Log base directory for troubleshooting directory creation
        logger.debug(message_manager.get_log_message("L190", base_dir))
        # Ensure project directories exist under base_dir with detailed logging
        for directory in ["temp", "logs", "docs"]:
            path_dir = os.path.join(base_dir, directory)
            exists = os.path.exists(path_dir)
            logger.debug(message_manager.get_log_message("L191", path_dir, exists))
            if not exists:
                os.makedirs(path_dir)
                # Log full absolute path for directory creation
                full_path = os.path.abspath(path_dir)
                logger.debug(message_manager.get_log_message("L014", full_path))
            else:
                logger.debug(message_manager.get_log_message("L192", path_dir))

        # Use project root temp directory and log its usage status
        temp_dir = os.path.join(base_dir, "temp")
        exists_temp = os.path.exists(temp_dir)
        logger.debug(message_manager.get_log_message("L193", temp_dir, exists_temp))
        if not exists_temp:
            os.makedirs(temp_dir)
            logger.debug(message_manager.get_log_message("L015", temp_dir))

        # If file_name is provided, create a subdirectory for this file
        if file_name:
            # Create a safe directory name from the file name
            safe_name = os.path.basename(file_name)
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._- ")
            safe_name = safe_name.replace(" ", "_")

            # Create a unique directory name to avoid conflicts
            file_temp_dir = os.path.join(temp_dir, f"{safe_name}_{os.getpid()}")
            os.makedirs(file_temp_dir, exist_ok=True)
            logger.debug(message_manager.get_log_message("L009", file_temp_dir))

            return file_temp_dir

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
