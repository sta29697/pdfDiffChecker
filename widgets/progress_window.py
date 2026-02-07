from __future__ import annotations
import inspect
import tkinter as tk
from tkinter import ttk
from logging import getLogger
from typing import Any, Dict, Optional, cast
import os

from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from utils.utils import get_resource_path
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")

# Initialize singleton message manager
message_manager = get_message_manager()


class ProgressWindow(tk.Toplevel, ThemeColorApplicable, ColoringThemeIF):
    """
    A window that displays a progress bar and status message.

    This class provides a modal dialog with a progress bar that can be updated
    to show the progress of a long-running operation.
    """

    def __init__(self, parent: tk.Widget) -> None:
        """
        Initialize a new ProgressWindow.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent)

        # Main processing: apply application icon to this Toplevel window.
        icon_multi_ico_path = get_resource_path("images/icon_multi.ico")
        runtime_ico_path = get_resource_path("temp/LOGOm.ico")

        ico_path = icon_multi_ico_path if os.path.exists(icon_multi_ico_path) else runtime_ico_path
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception as e:
                logger.warning(
                    message_manager.get_log_message(
                        "L227", f"Failed to set window icon: {str(e)}"
                    )
                )

        # Main processing: also apply PNG icons via iconphoto for better alpha handling.
        icon_png_candidates = (
            get_resource_path("images/icon_256x256.png"),
            get_resource_path("images/icon_128x128.png"),
            get_resource_path("images/icon_64x64.png"),
            get_resource_path("images/icon_48x48.png"),
            get_resource_path("images/icon_32x32.png"),
            get_resource_path("images/icon_24x24.png"),
            get_resource_path("images/icon_16x16.png"),
        )
        try:
            icon_imgs = [tk.PhotoImage(file=p) for p in icon_png_candidates if os.path.exists(p)]
            if icon_imgs:
                self.iconphoto(True, *icon_imgs)
                setattr(self, "_icon_photos", icon_imgs)
            else:
                icon_png_path = get_resource_path("images/LOGOm.png")
                if os.path.exists(icon_png_path):
                    icon_img = tk.PhotoImage(file=icon_png_path)
                    self.iconphoto(True, icon_img)
                    setattr(self, "_icon_photo", icon_img)
        except Exception as e:
            logger.warning(
                message_manager.get_log_message(
                    "L227", f"Failed to set window icon (iconphoto): {str(e)}"
                )
            )
        
        # Flag to track if theme has been initialized
        self._theme_initialized = False

        # Configure window
        # Set window title from UI message
        self.title(message_manager.get_ui_message("U035"))
        self.geometry("400x120")
        self.resizable(False, False)
        # Set transient only if parent is Tk or Toplevel
        self.transient(cast(tk.Wm, parent))  # Make window modal
        self.grab_set()  # Make window modal

        # Hide window initially
        self.withdraw()

        # Create main frame
        self.main_frame = ttk.Frame(self, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create status label
        # Set status label text from UI message
        self.status_label = ttk.Label(self.main_frame, text=message_manager.get_ui_message("U036"))
        self.status_label.pack(fill=tk.X, pady=(0, 10))

        # Create progress bar
        self.progress_bar = ttk.Progressbar(
            self.main_frame, orient=tk.HORIZONTAL, length=380, mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X)

        # Create cancel button (optional)
        # self.cancel_button = ttk.Button(self.main_frame, text="Cancel", command=self.cancel)
        # self.cancel_button.pack(pady=(10, 0), anchor=tk.E)

        # Center window on parent
        self.update_idletasks()
        self._center_on_parent()

        # Register for theme updates
        WidgetsTracker().add_widgets(self)

        # Progress window initialized
        logger.debug(message_manager.get_log_message("L083"))

    def _center_on_parent(self) -> None:
        """Center the window on its parent."""
        parent = self.master

        # Get parent geometry
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        # Calculate position
        width = self.winfo_width()
        height = self.winfo_height()
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2

        # Set position
        self.geometry(f"+{x}+{y}")

    def show(self) -> None:
        """Show the progress window."""
        self.deiconify()
        self.update()

    def hide(self) -> None:
        """Hide the progress window."""
        self.withdraw()
        self.update()

    def update_progress(self, value: int, message: Optional[str] = None) -> None:
        """
        Update the progress bar and status message.

        Args:
            value: Progress value (0-100).
            message: Optional status message to display.
        """
        # Update progress bar
        self.progress_bar["value"] = value

        # Update status message if provided
        if message is not None:
            self.status_label["text"] = message

        # Update window
        self.update()
        # Progress updated: current value, maximum, and optional message
        logger.debug(
            message_manager.get_log_message(
                "L053",
                value,
                self.progress_bar["maximum"],
                message or ""
            )
        )

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """
        Apply theme color to the progress window and its components.
        Only applies theme when ColorThemeManager has completed initialization.

        Args:
            theme_data: Dictionary containing theme color settings.
        """
        # Reset theme initialization flag at start of theme application
        self._theme_initialized = False
        
        # Skip applying theme if ColorThemeManager initialization is not complete
        if not ColorThemeManager.is_initialization_complete():
            logger.debug(message_manager.get_log_message("L154", "ProgressWindow waiting for theme initialization"))
            return
            
        # Check if theme data is empty and log appropriately
        if not theme_data:
            # 初期化中は詳細ログ、それ以外はエラーとして出力
            if ColorThemeManager.is_initialization_complete():
                logger.error(message_manager.get_log_message("L162", "ProgressWindow"))
            else:
                logger.debug(message_manager.get_log_message("L154", "ProgressWindow waiting for initialization"))
            return
            
        try:
            window_theme = theme_data.get("Window", {})
            label_theme = theme_data.get("Label", {})
            progress_theme = theme_data.get("primary_progressbar", {})

            window_bg = window_theme.get("bg", "#ffffff")
            label_fg = label_theme.get("fg", "#000000")

            # Apply theme to the toplevel background
            self.configure(bg=window_bg)

            # Apply ttk styles (required on Windows for consistent theming)
            style = ttk.Style(self)
            style.configure("ProgressWindow.TFrame", background=window_bg)
            style.configure("ProgressWindow.TLabel", background=window_bg, foreground=label_fg)

            # Main processing: configure progressbar colors from theme
            pb_bg = progress_theme.get("bg", "#000000")
            pb_trough = progress_theme.get("troughcolor", window_bg)
            pb_border = progress_theme.get("bordercolor", pb_bg)
            style.configure(
                "Primary.Horizontal.TProgressbar",
                background=pb_bg,
                troughcolor=pb_trough,
                bordercolor=pb_border,
                lightcolor=pb_bg,
                darkcolor=pb_bg,
            )

            self.main_frame.configure(style="ProgressWindow.TFrame")
            self.status_label.configure(style="ProgressWindow.TLabel")
            self.progress_bar.configure(style="Primary.Horizontal.TProgressbar")

            # Mark theme as initialized
            self._theme_initialized = True
            # Applied theme to progress window
            # Get caller information for accurate logging
            caller_file = os.path.basename(__file__) # Default is current file
            
            # Check if caller context was provided by the widgets tracker
            if hasattr(self, "_caller_context") and isinstance(self._caller_context, dict):
                # Use caller info from the actual caller context
                caller_file = self._caller_context.get("file", caller_file)
                
                # Get the actual tab or view file name if we have that information
                # This helps trace which view/tab actually contains this widget
                if "caller" in self._caller_context and self._caller_context["caller"] == "widgets_tracker":
                    # Try to get actual parent module info for better context
                    if hasattr(self.master, "__module__") and self.master.__module__.startswith("views."):
                        caller_file = self.master.__module__.split(".")[1] + ".py"
            else:
                # If no context, use inspect to get caller info
                frame = inspect.currentframe()
                if frame:
                    frame_info_list = inspect.getouterframes(frame)
                    if len(frame_info_list) > 1:
                        caller_file = os.path.basename(frame_info_list[1].filename)
            
            # Log with caller file and color key
            logger.debug(message_manager.get_log_message("L087", caller_file, "progress_window"))
        except Exception as e:
            # Failed to apply theme to progress window: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """
        Configure widget with theme settings.

        Args:
            theme_settings: Dictionary containing theme settings.
        """
        try:
            self.configure(**theme_settings)  # type: ignore[arg-type]
            # Configured widget with settings: {settings}
            logger.debug(message_manager.get_log_message("L088", theme_settings))
        except Exception as e:
            # Failed to configure widget: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _apply_theme_to_widget(
        self, widget: tk.Widget, theme_settings: Dict[str, Any]
    ) -> None:
        """
        Helper method to apply theme settings to a specific widget.

        Args:
            widget: Widget to configure.
            theme_settings: Dictionary containing theme settings.
        """
        try:
            # Check if theme settings is empty
            if not theme_settings:
                # Only log if ColorThemeManager has finished initialization
                # or if theme has been previously initialized successfully
                if (ColorThemeManager.is_initialization_complete() or 
                    hasattr(self, "_theme_initialized") and self._theme_initialized):
                    widget_name = widget.__class__.__name__
                    logger.debug(message_manager.get_log_message("L162", widget_name))
                return
            
            # Apply theme settings to widget
            widget.configure(**theme_settings)  # type: ignore[arg-type]
            # Mark that theme has been successfully initialized
            self._theme_initialized = True
            # Applied theme to widget: {settings}
            logger.debug(message_manager.get_log_message("L089", theme_settings))
        except Exception as e:
            # Failed to apply theme to widget: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
