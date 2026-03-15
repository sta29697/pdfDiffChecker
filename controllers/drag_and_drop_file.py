"""
Drag and drop handler for the application.
"""

from logging import getLogger
import os
import tkinter as tk
from tkinterdnd2 import DND_FILES  # type: ignore
from tkinter import TclError
from typing import Callable, Optional, List, Any, Protocol, cast, TypeVar

from configurations.message_manager import get_message_manager
message_manager = get_message_manager()

# Setup logger
logger = getLogger(__name__)

# Protocol for tkinterdnd2 widgets
class TkinterDnDWidget(Protocol):
    """Protocol for tkinterdnd2 widgets."""

    def drop_target_register(self, *args: Any) -> None:
        """Register as a drop target."""
        ...

    def dnd_bind(
        self, sequence: str, func: Callable[[Any], None], add: Optional[bool] = None
    ) -> str:
        """Bind a function to a DnD event."""
        ...


# Type variable for tkinter widgets with DnD capabilities
T = TypeVar("T", bound=tk.Widget)


class DragAndDropHandler:
    """Base class for handling drag and drop operations."""

    def __init__(self) -> None:
        """Initialize the DragAndDropHandler."""
        self.error_manager = message_manager

    @staticmethod
    def register_drop_target(
        widget: tk.Widget,
        on_drop: Callable[[str], None],
        allowed_extensions: Optional[List[str]] = None,
        feedback_callback: Optional[Callable[[str, bool], None]] = None,
        allow_directories: bool = False,
    ) -> bool:
        """Register a widget as a drop target.

        Args:
            widget: The widget to register as a drop target
            on_drop: Callback function to handle dropped files
            allowed_extensions: List of allowed file extensions
            feedback_callback: Optional callback for user feedback
            allow_directories: Whether dropped directories are accepted

        Returns:
            bool: True if registration is successful, False otherwise
        """
        try:
            # Register the widget as a drop target
            dnd_widget = cast(TkinterDnDWidget, widget)
            dnd_widget.drop_target_register(DND_FILES)

            # Define the drop callback
            def drop(event: Any) -> None:
                """Handle drop event.

                Args:
                    event: Drop event
                """
                # Get the file path from the event
                file_path = event.data
                if file_path.startswith("{") and file_path.endswith("}"):
                    file_path = file_path[1:-1]

                # Check if the file exists
                # os.path.exists() checks if the path is a file or directory
                # This check is necessary to prevent errors when trying to access the file
                if not os.path.exists(file_path):
                    error_manager = message_manager
                    # E003: The dropped file does not exist: {0}
                    error_msg = error_manager.get_error_message("E003", file_path)
                    logger.error(error_msg)
                    if feedback_callback:
                        feedback_callback(error_msg, False)
                    return

                # Check whether dropped item type is allowed.
                if allow_directories:
                    if not os.path.isdir(file_path):
                        error_manager = message_manager
                        error_msg = error_manager.get_error_message("E003", file_path)
                        logger.error(error_msg)
                        if feedback_callback:
                            feedback_callback(error_msg, False)
                        return
                else:
                    if not os.path.isfile(file_path):
                        error_manager = message_manager
                        error_msg = error_manager.get_error_message("E003", file_path)
                        logger.error(error_msg)
                        if feedback_callback:
                            feedback_callback(error_msg, False)
                        return

                # Check if the file extension is allowed
                if allowed_extensions and not allow_directories:
                    _, ext = os.path.splitext(file_path)
                    # ext represents the file extension (e.g., .pdf, .jpg, etc.)
                    # The file extension is used to determine the type of file
                    if ext.lower() not in allowed_extensions:
                        error_manager = message_manager
                        ext_list = ", ".join(allowed_extensions)
                        # E002: Invalid file extension. Allowed extensions: {0}
                        error_msg = error_manager.get_error_message("E002", ext_list)
                        logger.error(f"{error_msg} - File: {file_path}")
                        if feedback_callback:
                            feedback_callback(error_msg, False)
                        return

                # Call the on_drop callback
                on_drop(file_path)

                # Provide feedback
                if feedback_callback:
                    feedback_callback(f"File loaded: {file_path}", True)

            # Bind the drop callback to the widget
            dnd_widget.dnd_bind("<<Drop>>", drop)
            return True

        except TclError:
            # DnD extension not available: skip silently
            return False
        except Exception as e:
            logger.error(f"Failed to register drop target: {e}")
            if feedback_callback:
                feedback_callback(f"Failed to setup drag and drop: {e}", False)
            return False


class DragAndDropFileConverter(DragAndDropHandler):
    """Class for handling drag and drop operations for files and images."""

    def __init__(self) -> None:
        """Initialize the DragAndDropFileConverter."""
        super().__init__()
        self.message_manager = message_manager
        # File conversion processing will use appropriate converters as needed

    def setup_drag_and_drop_for_pdf_tab(
        self,
        base_canvas: tk.Canvas,
        base_path_var: tk.StringVar,
        comp_canvas: tk.Canvas,
        comp_path_var: tk.StringVar,
        feedback_callback: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        """Set up drag and drop for the PDF tab.

        Args:
            base_canvas: Canvas for base PDF
            base_path_var: StringVar for base PDF path
            comp_canvas: Canvas for comparison PDF
            comp_path_var: StringVar for comparison PDF path
            feedback_callback: Optional callback for user feedback
        """

        # Set up drag and drop for base PDF
        def on_base_drop(file_path: str) -> None:
            """Handle drop on base canvas.

            Args:
                file_path: Path to dropped file
            """
            base_path_var.set(file_path)

        self.register_drop_target(
            base_canvas,
            on_base_drop,
            allowed_extensions=[".pdf"],
            feedback_callback=feedback_callback,
        )

        # Set up drag and drop for comparison PDF
        def on_comp_drop(file_path: str) -> None:
            """Handle drop on comparison canvas.

            Args:
                file_path: Path to dropped file
            """
            comp_path_var.set(file_path)

        self.register_drop_target(
            comp_canvas,
            on_comp_drop,
            allowed_extensions=[".pdf"],
            feedback_callback=feedback_callback,
        )

    def setup_drag_and_drop_for_image_tab(
        self,
        base_canvas: tk.Canvas,
        base_path_var: tk.StringVar,
        comp_canvas: tk.Canvas,
        comp_path_var: tk.StringVar,
        feedback_callback: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        """Set up drag and drop for the image tab.

        Args:
            base_canvas: Canvas for base image
            base_path_var: StringVar for base image path
            comp_canvas: Canvas for comparison image
            comp_path_var: StringVar for comparison image path
            feedback_callback: Optional callback for user feedback
        """

        # Set up drag and drop for base image
        def on_base_drop(file_path: str) -> None:
            """Handle drop on base canvas.

            Args:
                file_path: Path to dropped file
            """
            base_path_var.set(file_path)

        self.register_drop_target(
            base_canvas,
            on_base_drop,
            allowed_extensions=[".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            feedback_callback=feedback_callback,
        )

        # Set up drag and drop for comparison image
        def on_comp_drop(file_path: str) -> None:
            """Handle drop on comparison canvas.

            Args:
                file_path: Path to dropped file
            """
            comp_path_var.set(file_path)

        self.register_drop_target(
            comp_canvas,
            on_comp_drop,
            allowed_extensions=[".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            feedback_callback=feedback_callback,
        )

    def setup_drag_and_drop_for_file_operation_tab(
        self,
        canvas: tk.Canvas,
        file_path_var: tk.StringVar,
        feedback_callback: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        """Set up drag and drop for the file operation tab.

        Args:
            canvas: Canvas widget to register as a drop target
            file_path_var: StringVar to store the dropped file path
            feedback_callback: Optional callback function to provide feedback to the user
        """
        try:

            def on_file_drop(file_path: str) -> None:
                """Handle drop on file operation canvas.

                Args:
                    file_path: Path to dropped file
                """
                # Update the file path variable
                file_path_var.set(file_path)

                # Provide feedback to the user
                if feedback_callback:
                    # M002: File path dropped via drag-and-drop
                    feedback_callback(
                        self.message_manager.get_message("M002", file_path), True
                    )

            # Use the parent class method to register the drop target
            self.register_drop_target(
                canvas,
                on_file_drop,
                feedback_callback=feedback_callback,
            )

        except Exception as e:
            # Log error using message code for multilingual support
            logger.error(self.message_manager.get_log_message("L206", str(e)))
            if feedback_callback:
                # E008: Failed to setup drag and drop: {0}
                feedback_callback(
                    self.message_manager.get_error_message("E008", str(e)), False
                )
