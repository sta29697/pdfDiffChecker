from __future__ import annotations
import logging
from logging import getLogger
import os
import sys
import traceback
import shutil
import ctypes
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from pathlib import Path
from typing import Final, Optional

from PIL import Image, ImageTk

# Core utilities and configuration
from configurations import tool_settings

# Raise Pillow's decompression-bomb ceiling for trusted local PDF render outputs (see tool_settings).
Image.MAX_IMAGE_PIXELS = tool_settings.PIL_MAX_IMAGE_PIXELS
from configurations.message_manager import get_message_manager
from controllers.event_bus import EventBus, EventNames
from configurations.user_setting_manager import get_user_setting_manager as usm
from controllers.color_theme_manager import ColorThemeManager
from controllers.app_state import AppState
from utils.utils import get_resource_path
from controllers.widgets_tracker import (
    WidgetsTracker,
    adjust_hex_color,
    ensure_contrast_color,
    refresh_combobox_popdown_listboxes,
)
from controllers.keyboard_navigation import KeyboardNavigationShell

# View components
from views.description import DescriptionApp
from views.licenses import LicensesApp

# Initialize singleton message manager at module level
message_manager = get_message_manager()
logger: Final = getLogger(__name__)
main_window: Optional[tk.Tk] = None


def _save_main_window_geometry(root: tk.Tk) -> None:
    """Persist the current main window geometry and display information.

    Args:
        root: Main Tk window.
    """
    settings = usm()
    try:
        # Main processing: capture the normal geometry even when the window is maximized.
        root.update_idletasks()
        current_state = str(root.state())
        width = int(root.winfo_width())
        height = int(root.winfo_height())
        pos_x = int(root.winfo_x())
        pos_y = int(root.winfo_y())
        if current_state == "zoomed":
            try:
                root.state("normal")
                root.update_idletasks()
                width = int(root.winfo_width())
                height = int(root.winfo_height())
                pos_x = int(root.winfo_x())
                pos_y = int(root.winfo_y())
            finally:
                root.state("zoomed")
                root.update_idletasks()

        geometry = f"{width}x{height}{pos_x:+d}{pos_y:+d}"
        settings.update_setting("window_width", width)
        settings.update_setting("window_height", height)
        settings.update_setting("window_position_x", pos_x)
        settings.update_setting("window_position_y", pos_y)
        settings.update_setting("window_geometry", geometry)
        settings.update_setting("window_state", current_state)
        settings.update_setting("window_display_width", int(root.winfo_screenwidth()))
        settings.update_setting("window_display_height", int(root.winfo_screenheight()))
    except Exception as exc:
        logger.warning(
            message_manager.get_log_message(
                "L227", f"Failed to save main window geometry: {str(exc)}"
            )
        )


def _restore_main_window_geometry(root: tk.Tk) -> None:
    """Restore the main window geometry when the saved display still matches.

    Args:
        root: Main Tk window.
    """
    settings = usm()
    try:
        saved_display_width = int(settings.get_setting("window_display_width", 0) or 0)
        saved_display_height = int(settings.get_setting("window_display_height", 0) or 0)
        current_display_width = int(root.winfo_screenwidth())
        current_display_height = int(root.winfo_screenheight())
        default_w = int(settings.get_setting("window_width", 884) or 884)
        default_h = int(settings.get_setting("window_height", 859) or 859)
        default_geometry = f"{default_w}x{default_h}+500+10"
        saved_geometry = str(settings.get_setting("window_geometry", default_geometry) or default_geometry)
        saved_state = str(settings.get_setting("window_state", "normal") or "normal")

        same_display = (
            saved_display_width == current_display_width
            and saved_display_height == current_display_height
            and saved_display_width > 0
            and saved_display_height > 0
        )

        geometry_to_apply = saved_geometry if same_display else default_geometry

        # Clamp window to screen if it would overflow (e.g. smaller display)
        try:
            import re as _re
            _m = _re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geometry_to_apply)
            if _m and current_display_width > 0 and current_display_height > 0:
                _gw, _gh = int(_m.group(1)), int(_m.group(2))
                _gx, _gy = int(_m.group(3)), int(_m.group(4))
                _margin = 40  # px kept on-screen
                _gw = min(_gw, current_display_width)
                _gh = min(_gh, current_display_height - _margin)
                _gx = max(0, min(_gx, current_display_width - _margin))
                _gy = max(0, min(_gy, current_display_height - _margin))
                geometry_to_apply = f"{_gw}x{_gh}{_gx:+d}{_gy:+d}"
        except Exception:
            pass

        root.geometry(geometry_to_apply)
        root.update_idletasks()
        if same_display and saved_state == "zoomed":
            root.state("zoomed")
    except Exception as exc:
        logger.warning(
            message_manager.get_log_message(
                "L227", f"Failed to restore main window geometry: {str(exc)}"
            )
        )


# Fallback when user settings do not yet contain window dimensions.
MAIN_WINDOW_MIN_WIDTH = 400
MAIN_WINDOW_MIN_HEIGHT = 280


def _get_persisted_main_window_minimum_size() -> tuple[int, int]:
    """Return minimum main-window size from persisted ``window_width`` / ``window_height``.

    Uses the last saved normal window size so the user cannot shrink below their
    chosen layout. Invalid values fall back to ``MAIN_WINDOW_MIN_*``.

    Returns:
        tuple[int, int]: Minimum window width and height.
    """
    settings = usm()
    try:
        w = int(settings.get_setting("window_width", MAIN_WINDOW_MIN_WIDTH) or MAIN_WINDOW_MIN_WIDTH)
        h = int(settings.get_setting("window_height", MAIN_WINDOW_MIN_HEIGHT) or MAIN_WINDOW_MIN_HEIGHT)
        if w < 1:
            w = MAIN_WINDOW_MIN_WIDTH
        if h < 1:
            h = MAIN_WINDOW_MIN_HEIGHT
        return (max(MAIN_WINDOW_MIN_WIDTH, w), max(MAIN_WINDOW_MIN_HEIGHT, h))
    except Exception:
        return (MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT)


def _apply_main_window_minimum_size(root: tk.Tk) -> None:
    """Apply ``root.minsize`` from persisted window dimensions (with absolute floors).

    Args:
        root: Main Tk window.
    """
    try:
        min_width, min_height = _get_persisted_main_window_minimum_size()
        root.minsize(min_width, min_height)
    except Exception as exc:
        logger.warning(
            message_manager.get_log_message(
                "L227", f"Failed to apply main window minimum size: {str(exc)}"
            )
        )


class ProductionLogFilter(logging.Filter):
    """Allow only production-critical logs and app lifecycle messages.

    Production logging should remain lightweight so end users only keep error
    reports plus startup, shutdown, and save traces.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True when the record should be written in production mode.

        Args:
            record: The logging record being evaluated.

        Returns:
            bool: True when the record should be preserved.
        """
        if record.levelno >= logging.ERROR:
            return True
        message = record.getMessage()
        return "[APP_LIFECYCLE]" in message or "[APP_SAVE]" in message

def setup_logging() -> None:
    """Set up logging configuration for the application.

    This function configures:
    1. Log file location and format
    2. Console output for debugging
    3. File handler for persistent logging

    The log file is stored as ``./logs/debug.log`` in development mode and as
    ``pdfDiffChecker.log`` under the Windows temp app folder in production mode.
    """
    try:
        tool_settings.ensure_runtime_directories()
        log_dir = tool_settings.LOG_DIR
        log_file = tool_settings.LOG_FILE_PATH

        if tool_settings.is_development_mode:
            try:
                # Main processing: clear the development log before recording a new startup trace.
                log_file.write_text("", encoding="utf-8")
            except Exception:
                pass

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if tool_settings.is_development_mode else logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(lineno)d): %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )
        
        # File handler for logging to file
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG if tool_settings.is_development_mode else logging.INFO)
        file_handler.setFormatter(formatter)
        if tool_settings.is_production_mode:
            # Main processing: keep production logs limited to errors and lifecycle events.
            file_handler.addFilter(ProductionLogFilter())
        
        # Main processing: clear existing handlers first to avoid duplicate outputs.
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        # Add handlers to root logger - file only, no console output
        root_logger.addHandler(file_handler)
                
        # Set PIL logger level to WARNING to suppress verbose PNG file loading logs
        pil_logger = logging.getLogger('PIL')
        pil_logger.setLevel(logging.WARNING)
        if tool_settings.is_development_mode:
            # Main processing: enable theme tracing only in development mode.
            AppState.enable_theme_application_logs()
        logger.info("[APP_LIFECYCLE] Logging system initialized")
        # This log will be multilingualized later through message_manager
    except Exception as e:
        error_msg = str(e)
        # Direct log message specification before message_manager initialization
        logger.error(f"[SYS] Failed to initialize logging: {error_msg}")
        # Only English messages are used in the initialization phase
        # Use English for errors during initialization phase
        title = "Error"
        message = f"Failed to initialize logging system: {error_msg}"
        messagebox.showerror(title, message)
        sys.exit(1)


def initialize_application() -> str:
    """Initialize the application components.

    This function:
    1. Sets up the logging system
    2. Creates necessary directories
    3. Initializes user settings
    4. Sets up color themes
    5. Initializes message manager for internationalization
    
    Returns:
        str: Path to the temporary directory
    """
    try:
        message_manager = get_message_manager()
        logger.debug(message_manager.get_log_message("L178"))
        # Setup logging
        setup_logging()
        logger.info("[APP_LIFECYCLE] Application startup")
        logger.debug(message_manager.get_log_message("L179"))

        # Create necessary directories
        logger.debug(message_manager.get_log_message("L180"))
        tool_settings.ensure_runtime_directories()
        temp_dir = tool_settings.TEMP_DIR
        logger.debug(message_manager.get_log_message("L181", temp_dir, os.path.exists(temp_dir)))
        logger.info(message_manager.get_log_message("L182", temp_dir))

        # Initialize user settings
        logger.debug(message_manager.get_log_message("L183"))
        settings_manager = usm()
        logger.debug(message_manager.get_log_message("L184", settings_manager._settings_status, os.path.exists(tool_settings.USER_SETTINGS_FILE)))

        # Initialize color themes - explicitly load themes before creating UI components
        logger.debug(message_manager.get_log_message("L185"))
        theme_manager = ColorThemeManager.get_instance()
        theme_color = settings_manager.get_setting("theme_color")
        # Load saved theme if available
        if theme_color:
            theme_manager.load_theme(theme_color)
        logger.debug(message_manager.get_log_message("L186", theme_manager.get_current_theme_name()))
        
        # Set application state for UI components
        logger.debug(message_manager.get_log_message("L187"))
        
        # Retrieve language setting and determine two-letter code
        lang_setting = settings_manager.get_setting("language", tool_settings.DEFAULT_LANGUAGE)
        # Use message code after MessageManager is available
        logger.debug(message_manager.get_log_message("L243", lang_setting))
        if lang_setting in ["ja", "en"]:
            language_code = lang_setting
        elif lang_setting.lower() in ["japanese", "english"]:
            language_code = "ja" if lang_setting.lower() == "japanese" else "en"
        else:
            language_code = tool_settings.DEFAULT_LANGUAGE
        get_message_manager().set_language(language_code)
        logger.debug(message_manager.get_log_message("L242", language_code))
        
        # Return temp directory path
        return str(temp_dir)

    except Exception as e:
        message_manager = get_message_manager()
        error_msg = str(e)
        logger.error(message_manager.get_log_message("L241", error_msg))
        messagebox.showerror(message_manager.get_message("E001"), message_manager.get_message("M000", error_msg))
        sys.exit(1)


class WindowEventManager:
    """Window event management class for centralized event handling.
    
    This class manages window control events (close, minimize, maximize)
    and routes them through the EventBus for decoupled handling.
    
    CRITICAL: This class must be initialized ONCE immediately after Tk() creation
    and its protocol handlers must not be overridden by any other code.
    """
    
    def __init__(self, root: tk.Tk):
        """Initialize window event manager.
        
        Args:
            root (tk.Tk): Root window to manage
        """
        self.root = root
        # Use the singleton EventBus instance - this is critical for event coordination
        self.event_bus = EventBus()
        
        # Log the EventBus instance ID for debugging event routing issues
        event_bus_id = id(self.event_bus)
        logger.debug(message_manager.get_log_message("L344", event_bus_id))
        
        # CRITICAL: Set up window protocol handlers FIRST before any other code can override them
        self.setup_window_protocols()
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventNames.WINDOW_CLOSE_REQUESTED, self.handle_close_request)
        self.event_bus.subscribe(EventNames.WINDOW_MINIMIZE_REQUESTED, self.handle_minimize_request)
        self.event_bus.subscribe(EventNames.WINDOW_MAXIMIZE_REQUESTED, self.handle_maximize_request)
        
        # Print statements for debugging
        print("WindowEventManager initialized")
        # Log that WindowEventManager was successfully initialized
        logger.debug(message_manager.get_log_message("L341", "WindowEventManager"))
    
    def setup_window_protocols(self) -> None:
        """Set up window protocol handlers.
        
        CRITICAL: This method sets the WM_DELETE_WINDOW protocol handler
        which must not be overridden by any other code.
        """
        # Print to console for debugging
        print("Setting up window protocols in WindowEventManager")
        
        # CRITICAL: Register WM_DELETE_WINDOW protocol handler for close button clicks
        # This must be the ONLY place in the entire application that sets this protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close_protocol)
        
        # Setup keyboard shortcuts for window control
        # These event handlers just publish events, which are then processed by the appropriate handlers
        self.root.bind_all("<Escape>", lambda e: self.event_bus.publish(EventNames.WINDOW_CLOSE_REQUESTED))
        self.root.bind_all("<Alt-F4>", lambda e: self.event_bus.publish(EventNames.WINDOW_CLOSE_REQUESTED))
        self.root.bind_all("<Control-q>", lambda e: self.event_bus.publish(EventNames.WINDOW_CLOSE_REQUESTED))
        
        # Ensure standard window behavior
        if self.root.winfo_toplevel().wm_overrideredirect():
            # Force standard window decorations if overrideredirect was set to True anywhere
            self.root.wm_overrideredirect(False)
        
    def enable_window_controls(self) -> None:
        """Enable standard window manager controls.
        
        This method ensures that the window has standard decorations and controls.
        It should only be called if window controls need to be restored, not during
        normal application operation.
        """
        try:
            # We only check and restore standard decorations if needed
            # This avoids unnecessary window state changes
            if sys.platform.startswith("win"):
                if self.root.winfo_toplevel().wm_overrideredirect():
                    # Restoring standard window decorations
                    logger.debug(message_manager.get_log_message("L272"))
                    self.root.winfo_toplevel().wm_overrideredirect(False)
            
            # We don't force normal state here anymore, as it could interfere
            # with legitimate maximized or minimized states
            # Window events bound successfully
            logger.debug(message_manager.get_log_message("L147"))
        except Exception as e:
            # Error binding window events
            logger.error(message_manager.get_log_message("L148", str(e)))
    
    def on_window_close_protocol(self) -> None:
        """Handle WM_DELETE_WINDOW protocol event."""
        # Application shutdown initiated by window close button
        logger.debug(message_manager.get_log_message("L267"))
        # Publish window close request through event bus
        self.event_bus.publish(EventNames.WINDOW_CLOSE_REQUESTED)
    
    def handle_close_request(self) -> None:
        """Handle window close request - this is the critical path for window close operations.
        
        This method is triggered when:
        1. The user clicks the X button in the title bar
        2. The user presses Alt+F4, Esc, or Ctrl+Q
        3. The close button in the UI is clicked
        
        It performs cleanup, destroys the window, and exits the application safely.
        """
        # IMPORTANT: Print directly to console for debugging window close operations
        print("\n==== WindowEventManager.handle_close_request called ====\n")
        logger.info(message_manager.get_log_message("L232"))
        
        # Disable all protocol handlers first to prevent any recursive calls
        try:
            # Unbind the WM_DELETE_WINDOW protocol to prevent recursive calls
            self.root.protocol("WM_DELETE_WINDOW", lambda: None)
            print("Window protocols disabled to prevent recursive calls")
        except Exception as protocol_e:
            print(f"Error disabling protocols: {protocol_e}")
            
        # Perform cleanup - Always call the cleanup() from global scope
        try:
            print("Calling cleanup function...")
            cleanup()
            print("Cleanup completed successfully")
        except NameError as e:
            # If cleanup function is not found, log error and continue
            print(f"Cleanup function not found: {e}")
            logger.error(message_manager.get_log_message("L224", f"cleanup function not found: {str(e)}"))
        except Exception as e:
            # Log any other cleanup errors but continue with window destruction
            print(f"Cleanup failed with error: {e}")
            logger.error(message_manager.get_log_message("L224", str(e)))
            
        # Always destroy the window regardless of cleanup success/failure
        try:
            print("Destroying main window...")
            self.root.destroy()
            print("Window destroyed successfully")
        except Exception as destroy_e:
            print(f"Error destroying window: {destroy_e}")
            # If we couldn't destroy normally, try to force close
            try:
                self.root.quit()
            except Exception as quit_e:
                print(f"Error quitting application: {quit_e}")
        
        # Exit the application
        print("Exiting application...")
        sys.exit(0)
    
    def handle_minimize_request(self) -> None:
        """Handle window minimize request."""
        # Debug: Log that minimize request handler was called
        print("Minimizing window via WindowEventManager")
        
        # In Windows, calling iconify() will un-maximize a window first
        # So we need to check current state before minimizing
        current_state = self.root.state()
        
        # Log the minimize request with window state information
        logger.debug(message_manager.get_log_message("L268", current_state))
        
        # Use wm_iconify() instead of iconify() - same function but more explicit
        try:
            self.root.wm_iconify()
            logger.debug(message_manager.get_log_message("L274", "Window minimized successfully"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L275", str(e)))
    
    def handle_maximize_request(self) -> None:
        """Handle window maximize request."""
        # Debug: Log that maximize request handler was called
        print("Maximizing/restoring window via WindowEventManager")
        
        # Get current window state
        current_state = self.root.state()
        logger.debug(message_manager.get_log_message("L269", current_state))
        
        try:
            # Toggle maximized state
            if current_state == "zoomed":
                # If currently maximized, restore to normal
                self.root.state("normal")
                logger.debug(message_manager.get_log_message("L270"))
            elif current_state == "iconic":  # Window is minimized
                # First restore from minimized state
                self.root.state("normal")
                # Then maximize
                self.root.state("zoomed")
                logger.debug(message_manager.get_log_message("L271"))
            else:
                # Normal state or other - maximize the window
                # On Windows, this is the 'zoomed' state
                self.root.state("zoomed")
                logger.debug(message_manager.get_log_message("L271"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L275", str(e)))


def create_main_window() -> tk.Tk:
    """Create the main application window.
    
    This function initializes the main Tk root window with proper window controls.
    CRITICAL: WindowEventManager must be initialized immediately after Tk() creation.
    
    Returns:
        tk.Tk: Initialized root window with proper event handling setup
    """
    try:
        print("Creating main application window")
        # Create root window with standard window decorations
        root = tk.Tk()
        root.withdraw()
        # Force standard window controls (minimize, maximize, close)
        root.wm_overrideredirect(False)
        root.resizable(True, True)
        
        # CRITICAL: Initialize WindowEventManager immediately after window creation
        # This ensures that the WM_DELETE_WINDOW protocol is set correctly and
        # not later overridden by any other code
        print("Initializing WindowEventManager in create_main_window")
        # The manager is automatically registered with EventBus, no need to store reference
        WindowEventManager(root)
        # Log that window management system is initialized
        logger.debug(message_manager.get_log_message("L016"))
        
        return root
    except Exception as e:
        logger.critical(message_manager.get_log_message("L012", str(e)))
        print(f"Critical error creating main window: {e}")
        sys.exit(1)


def change_logo_icon() -> str:
    """Get path to the application logo icon using resource resolver."""
    # Resolve icon path from project resources
    # Main processing: prefer the runtime-generated transparent ICO.
    return str(tool_settings.RUNTIME_ICON_ICO_PATH)


def cleanup() -> None:
    """Clean up application resources before exit.

    This function:
    1. Removes temporary files
    2. Saves user settings
    3. Closes open resources
    
    The function is designed to be robust against failures, logging errors
    but continuing execution to ensure a clean application exit.
    """
    # Print statement for debugging cleanup process
    print("Starting application cleanup process")
    
    try:
        # Remove temporary files
        # Main processing: clean the active runtime temp directory.
        temp_dir = tool_settings.TEMP_DIR
        if temp_dir.exists():
            try:
                for entry in temp_dir.iterdir():
                    try:
                        # Main processing: keep the cached transparent icon ICO across runs.
                        if entry.is_file() and entry.name.strip().lower() == "logom.ico":
                            continue
                        if entry.is_file() or entry.is_symlink():
                            entry.unlink()
                        elif entry.is_dir():
                            shutil.rmtree(entry)
                    except Exception as e:
                        logger.warning(message_manager.get_log_message("L227", str(e)))
                # Use the global message_manager
                logger.info(message_manager.get_log_message("L225", ""))
            except Exception as e:
                # Log but continue if temp directory can't be cleaned
                logger.error(message_manager.get_log_message("L228", str(e)))

        # Save user settings
        try:
            if 'main_window' in globals() and main_window is not None:
                _save_main_window_geometry(main_window)
            settings = usm()
            settings.save_settings()
            # Use the global message_manager
            logger.info(message_manager.get_log_message("L226", ""))
            logger.info("[APP_LIFECYCLE] Application shutdown")
        except Exception as e:
            # Log but continue if settings can't be saved
            logger.error(message_manager.get_log_message("L229", str(e)))
            
        # Print statement to confirm cleanup completion
        print("Cleanup process completed")
    except Exception as e:
        # Catch-all for any unexpected errors in cleanup
        print(f"Unexpected error in cleanup: {e}")
        logger.error(message_manager.get_log_message("L230", str(e)))
        logger.error(message_manager.get_log_message("L224", str(e)))
        messagebox.showerror(message_manager.get_ui_message("E001"), message_manager.get_ui_message("E022"))


def get_version_info() -> str:
    """Get application version information.
    
    Returns:
        str: Version string for display in window title
    """
    # Hard-coded version for this application
    return "v1.0.13"


def set_args() -> dict:
    """Process command line arguments.
    
    Returns:
        dict: Dictionary of processed arguments
    """
    # Simple placeholder for argument processing
    return {}


def _set_windows_app_user_model_id() -> None:
    """Set the Windows AppUserModelID for correct taskbar icon binding.

    Windows can keep showing the default Tk icon on the taskbar when the
    process identity is not explicitly assigned before the main window is
    created. This helper binds the process to the application icon resources.
    """
    if not sys.platform.startswith("win"):
        return

    try:
        # Main processing: assign a stable AppUserModelID before Tk window creation.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "sta29697.pdfDiffChecker"
        )
    except Exception as exc:
        logger.warning(
            message_manager.get_log_message(
                "L227", f"Failed to set Windows AppUserModelID: {str(exc)}"
            )
        )


def main() -> None:
    """Main entry point for the application.
    
    This function:
    1. Initializes the application
    2. Creates the main window (which also initializes WindowEventManager)
    3. Creates UI components and sets up the notebook with tabs
    4. Starts the event loop
    
    Returns:
        None
    """
    # Explicitly declare message_manager as a global variable
    global message_manager, main_window
    
    try:
        print("Starting application...")
        # Initialize the application (sets up logging, creates directories, etc.)
        initialize_application()
        _set_windows_app_user_model_id()
        settings_manager = usm()
        
        # Reinitialize message_manager if it's None or not defined
        if 'message_manager' not in globals() or message_manager is None:
            message_manager = get_message_manager()
            
        # Directory creation log with directory path
        temp_dir = str(tool_settings.TEMP_DIR)
        exists_temp_dir = os.path.exists(temp_dir)
        if exists_temp_dir:
            logger.info(message_manager.get_log_message("L192", temp_dir))
        else:
            logger.info(message_manager.get_log_message("L014", temp_dir))

        # Create main window (WindowEventManager is initialized inside create_main_window)
        main_window = create_main_window()
        
        # Set window title with version information
        version_info = get_version_info()
        main_window.title(f"PDF Diff Checker {version_info}")
        
        # Set window icon
        icon_png_path = get_resource_path("images/LOGOm.png")
        icon_multi_ico_path = get_resource_path("images/icon_multi.ico")
        runtime_ico_path = str(tool_settings.RUNTIME_ICON_ICO_PATH)
        icon_path = ""
        base_img: Optional[Image.Image] = None

        if (not os.path.exists(icon_multi_ico_path)) and os.path.exists(icon_png_path):
            try:
                with Image.open(icon_png_path) as img:
                    base_img = img.convert("RGBA")

                # Main processing: generate the runtime ICO only when missing or stale.
                try:
                    os.makedirs(os.path.dirname(runtime_ico_path), exist_ok=True)
                    png_mtime = os.path.getmtime(icon_png_path)
                    ico_is_fresh = (
                        os.path.exists(runtime_ico_path)
                        and os.path.getsize(runtime_ico_path) > 0
                        and os.path.getmtime(runtime_ico_path) >= png_mtime
                    )

                    if not ico_is_fresh:
                        ico_sizes = (16, 32, 48, 64, 128, 256)
                        try:
                            base_img.save(
                                runtime_ico_path,
                                format="ICO",
                                sizes=[(s, s) for s in ico_sizes],
                                bitmap_format="png",
                            )
                        except TypeError:
                            base_img.save(
                                runtime_ico_path,
                                format="ICO",
                                sizes=[(s, s) for s in ico_sizes],
                            )
                except Exception as e:
                    logger.warning(
                        message_manager.get_log_message(
                            "L227",
                            f"Failed to generate transparent ICO from PNG: {str(e)}",
                        )
                    )
            except Exception as e:
                logger.warning(
                    message_manager.get_log_message(
                        "L227", f"Failed to load icon PNG (iconphoto): {str(e)}"
                    )
                )

        if os.path.exists(runtime_ico_path):
            icon_path = runtime_ico_path

        if os.path.exists(icon_multi_ico_path):
            icon_path = icon_multi_ico_path

        if icon_path and os.path.exists(icon_path):
            try:
                main_window.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(
                    message_manager.get_log_message(
                        "L227", f"Failed to set window icon: {str(e)}"
                    )
                )

        # Main processing: also apply PNG icons via iconphoto for better alpha handling.
        icon_png_candidates = (
            (256, get_resource_path("images/icon_256x256.png")),
            (128, get_resource_path("images/icon_128x128.png")),
            (64, get_resource_path("images/icon_64x64.png")),
            (48, get_resource_path("images/icon_48x48.png")),
            (32, get_resource_path("images/icon_32x32.png")),
            (24, get_resource_path("images/icon_24x24.png")),
            (16, get_resource_path("images/icon_16x16.png")),
        )
        try:
            icon_imgs = [
                tk.PhotoImage(file=p)
                for _, p in icon_png_candidates
                if os.path.exists(p)
            ]
            if icon_imgs:
                main_window.iconphoto(True, *icon_imgs)
                setattr(main_window, "_icon_photos", icon_imgs)
            elif base_img is not None:
                resample = (
                    Image.Resampling.LANCZOS
                    if hasattr(Image, "Resampling")
                    else Image.LANCZOS
                )
                icon_sizes = (16, 24, 32, 48, 64, 128)
                icon_imgs = [
                    ImageTk.PhotoImage(base_img.resize((s, s), resample))
                    for s in icon_sizes
                ]
                main_window.iconphoto(True, *icon_imgs)
                setattr(main_window, "_icon_photos", icon_imgs)
        except Exception as e:
            logger.warning(
                message_manager.get_log_message(
                    "L227", f"Failed to set window icon (iconphoto): {str(e)}"
                )
            )
        
        # Set window geometry: min size from saved window_width/height, then restore position/size.
        _apply_main_window_minimum_size(main_window)
        _restore_main_window_geometry(main_window)
        _apply_main_window_minimum_size(main_window)
        try:
            main_window.update_idletasks()
            main_window.deiconify()
            main_window.lift()
        except Exception:
            pass
        
        # Initialize color theme manager for theme control
        WidgetsTracker()
        theme_manager = ColorThemeManager.get_instance()
        theme_manager.init_color_theme()

        class NotebookStyleUpdater:
            """Update ttk.Notebook styles when the theme changes.

            This class exists to provide a stable, long-lived subscriber for
            EventBus callbacks. EventBus uses weak references; therefore the
            subscriber must remain strongly referenced for the lifetime of the
            application.
            """

            def __init__(self, style: ttk.Style, root_window: tk.Tk) -> None:
                """Initialize the updater.

                Args:
                    style (ttk.Style): The ttk.Style instance to configure.
                    root_window (tk.Tk): The root window to configure.
                """
                self._style = style
                self._root_window = root_window

            def handle_theme_changed(self, theme: dict, theme_name: str) -> None:
                """Apply Notebook tab styles from theme data.

                Args:
                    theme (dict): Theme data published by ColorThemeManager.
                    theme_name (str): Theme name (e.g., "dark", "light").
                """
                try:
                    logger.debug(f"[THEME] ttk style update: theme_name={theme_name}")
                except Exception:
                    pass

                # Main processing: update ttk.Notebook / ttk.Notebook.Tab colors
                notebook_theme = theme.get("Notebook", {}) if isinstance(theme, dict) else {}
                notebook_bg = notebook_theme.get("bg", "#2d2d2d")
                tab_bg = notebook_theme.get("tab_bg", notebook_bg)
                tab_fg = notebook_theme.get("tab_fg", "#ffffff")

                frame_theme = theme.get("Frame", {}) if isinstance(theme, dict) else {}
                window_theme = theme.get("Window", {}) if isinstance(theme, dict) else {}
                window_bg = window_theme.get("bg", notebook_bg)

                frame_bg = frame_theme.get("bg", window_bg)

                # Main processing: derive tab colors and border contrast for clear selection visibility.
                border_color_base = frame_theme.get("highlightbackground", notebook_bg)
                theme_key = str(theme_name or "").strip().lower()
                border_color = border_color_base

                if theme_key in ("light", "pastel"):
                    try:
                        base_norm = str(border_color_base).strip().lower()
                        frame_bg_norm = str(frame_bg).strip().lower()
                        tab_bg_norm = str(tab_bg).strip().lower()
                        notebook_bg_norm = str(notebook_bg).strip().lower()
                        if base_norm in {frame_bg_norm, tab_bg_norm, notebook_bg_norm}:
                            border_color = adjust_hex_color(str(notebook_bg), -0.12)
                    except Exception:
                        pass

                # Main processing: compute selected/unselected backgrounds per theme.
                selected_tab_bg = tab_bg
                active_tab_bg = tab_bg
                unselected_tab_bg = notebook_bg

                if theme_key == "dark":
                    selected_tab_bg = frame_bg
                    unselected_tab_bg = adjust_hex_color(str(tab_bg), 0.06)
                    active_tab_bg = adjust_hex_color(str(tab_bg), 0.10)
                elif theme_key in ("light", "pastel"):
                    selected_tab_bg = frame_bg
                    active_tab_bg = frame_bg
                    unselected_tab_bg = adjust_hex_color(str(notebook_bg), -0.05)

                # Main processing: unify tab edge rendering to avoid thin/bright borders.
                tab_borderwidth = 1
                relief_map = [("selected", "solid"), ("active", "solid"), ("!selected", "flat")]

                try:
                    self._style.configure("TNotebook", background=notebook_bg)
                except Exception:
                    pass
                try:
                    self._style.configure(
                        "TNotebook",
                        borderwidth=1,
                        bordercolor=border_color,
                        lightcolor=border_color,
                        darkcolor=border_color,
                    )
                except Exception:
                    pass
                try:
                    self._style.configure(
                        "TNotebook.Tab",
                        background=unselected_tab_bg,
                        foreground=tab_fg,
                        padding=[10, 2],
                        borderwidth=tab_borderwidth,
                    )
                except Exception:
                    pass
                try:
                    self._style.configure(
                        "TNotebook.Tab",
                        bordercolor=border_color,
                        lightcolor=border_color,
                        darkcolor=border_color,
                        focuscolor=border_color,
                    )
                except Exception:
                    pass
                try:
                    self._style.map(
                        "TNotebook.Tab",
                        background=[("selected", selected_tab_bg), ("active", active_tab_bg), ("!selected", unselected_tab_bg)],
                        foreground=[("selected", tab_fg), ("active", tab_fg), ("!selected", tab_fg)],
                        borderwidth=[("selected", tab_borderwidth), ("active", tab_borderwidth), ("!selected", tab_borderwidth)],
                        bordercolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                        lightcolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                        darkcolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                        focuscolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                    )
                except Exception:
                    pass

                try:
                    self._style.map(
                        "TNotebook.Tab",
                        relief=relief_map,
                    )
                except Exception:
                    pass

                label_theme = theme.get("Label", {}) if isinstance(theme, dict) else {}
                button_theme = theme.get("Button", {}) if isinstance(theme, dict) else {}
                entry_theme = theme.get("Entry", {}) if isinstance(theme, dict) else {}
                combobox_theme = theme.get("primary_combobox", {}) if isinstance(theme, dict) else {}
                progress_theme = theme.get("primary_progressbar", {}) if isinstance(theme, dict) else {}

                # Main processing: keep root background consistent
                try:
                    self._root_window.configure(bg=window_bg)
                except Exception:
                    pass

                self._style.configure(
                    "TFrame",
                    background=frame_bg,
                )
                self._style.configure(
                    "TLabel",
                    background=label_theme.get("bg", frame_bg),
                    foreground=label_theme.get("fg", tab_fg),
                )
                self._style.configure(
                    "TButton",
                    background=button_theme.get("bg", frame_bg),
                    foreground=button_theme.get("fg", tab_fg),
                )
                self._style.configure(
                    "TEntry",
                    fieldbackground=entry_theme.get("bg", frame_theme.get("bg", notebook_bg)),
                    foreground=entry_theme.get("fg", tab_fg),
                )

                # Main processing: style combobox consistently across themes
                try:
                    self._style.configure(
                        "TCombobox",
                        fieldbackground=combobox_theme.get("bg", entry_theme.get("bg", "#ffffff")),
                        background=combobox_theme.get("bg", entry_theme.get("bg", "#ffffff")),
                        foreground=combobox_theme.get("fg", entry_theme.get("fg", "#000000")),
                        selectbackground=combobox_theme.get("selectbackground", combobox_theme.get("bg", "#ffffff")),
                        selectforeground=combobox_theme.get("selectforeground", combobox_theme.get("fg", "#000000")),
                    )
                except Exception:
                    pass

                # Main processing: map combobox/button state colors to avoid OS-theme black overrides
                combo_bg = combobox_theme.get("bg", entry_theme.get("bg", "#ffffff"))
                combo_fg = combobox_theme.get("fg", entry_theme.get("fg", "#000000"))
                combo_border_base = combobox_theme.get(
                    "bordercolor",
                    frame_theme.get("highlightbackground", combo_bg),
                )
                combo_border = ensure_contrast_color(combo_border_base, combo_bg, 0.25)
                combo_light = adjust_hex_color(combo_border, 0.25)
                combo_dark = adjust_hex_color(combo_border, -0.25)
                combo_focus = combobox_theme.get("highlightcolor", combo_border)
                combo_arrow_bg = ensure_contrast_color(combobox_theme.get("arrowbackground", combo_bg), combo_bg, 0.06)
                try:
                    self._style.configure(
                        "TCombobox",
                        arrowcolor=combo_fg,
                        bordercolor=combo_border,
                        lightcolor=combo_light,
                        darkcolor=combo_dark,
                        focuscolor=combo_focus,
                        background=combo_arrow_bg,
                    )
                except Exception:
                    pass
                try:
                    combo_focus_ring = ensure_contrast_color(
                        str(combo_focus),
                        combo_bg,
                        0.28,
                    )
                    self._style.map(
                        "TCombobox",
                        fieldbackground=[("readonly", combo_bg), ("disabled", combo_bg)],
                        background=[("readonly", combo_arrow_bg), ("disabled", combo_arrow_bg), ("active", combo_arrow_bg)],
                        foreground=[("readonly", combo_fg), ("disabled", combo_fg), ("active", combo_fg)],
                        selectbackground=[("readonly", combobox_theme.get("selectbackground", combo_bg))],
                        selectforeground=[("readonly", combobox_theme.get("selectforeground", combo_fg))],
                        arrowcolor=[("readonly", combo_fg), ("active", combo_fg), ("disabled", combo_fg)],
                        bordercolor=[
                            ("focus", combo_focus_ring),
                            ("readonly", combo_border),
                            ("active", combo_border),
                            ("disabled", combo_border),
                        ],
                        focuscolor=[
                            ("focus", combo_focus_ring),
                            ("readonly", combo_focus),
                            ("active", combo_focus),
                        ],
                    )
                except Exception:
                    pass

                # Main processing: language combobox uses a dedicated style for a stronger focus ring.
                try:
                    lang_focus_ring = ensure_contrast_color(
                        str(combo_focus),
                        combo_bg,
                        0.52,
                    )
                    self._style.configure(
                        "LanguageSelect.TCombobox",
                        arrowcolor=combo_fg,
                        bordercolor=combo_border,
                        lightcolor=combo_light,
                        darkcolor=combo_dark,
                        focuscolor=lang_focus_ring,
                        background=combo_arrow_bg,
                    )
                    self._style.map(
                        "LanguageSelect.TCombobox",
                        fieldbackground=[("readonly", combo_bg), ("disabled", combo_bg)],
                        background=[
                            ("readonly", combo_arrow_bg),
                            ("disabled", combo_arrow_bg),
                            ("active", combo_arrow_bg),
                        ],
                        foreground=[("readonly", combo_fg), ("disabled", combo_fg), ("active", combo_fg)],
                        selectbackground=[
                            ("readonly", combobox_theme.get("selectbackground", combo_bg)),
                        ],
                        selectforeground=[
                            ("readonly", combobox_theme.get("selectforeground", combo_fg)),
                        ],
                        arrowcolor=[("readonly", combo_fg), ("active", combo_fg), ("disabled", combo_fg)],
                        bordercolor=[
                            ("focus", lang_focus_ring),
                            ("readonly", combo_border),
                            ("active", combo_border),
                            ("disabled", combo_border),
                        ],
                        focuscolor=[
                            ("focus", lang_focus_ring),
                            ("readonly", combo_focus),
                            ("active", combo_focus),
                        ],
                    )
                except Exception:
                    pass

                # Main processing: style combobox dropdown list (Listbox) via option database.
                try:
                    listbox_bg = combobox_theme.get("list_bg", combo_bg)
                    listbox_fg = combobox_theme.get("list_fg", combo_fg)
                    listbox_sel_bg = combobox_theme.get(
                        "list_selectbackground",
                        combobox_theme.get("selectbackground", combo_bg),
                    )
                    listbox_sel_fg = combobox_theme.get(
                        "list_selectforeground",
                        combobox_theme.get("selectforeground", combo_fg),
                    )

                    listbox_sel_bg = ensure_contrast_color(str(listbox_sel_bg), str(listbox_bg), 0.08)

                    self._root_window.option_add("*TCombobox*Listbox.background", listbox_bg)
                    self._root_window.option_add("*TCombobox*Listbox.foreground", listbox_fg)
                    self._root_window.option_add("*TCombobox*Listbox.selectBackground", listbox_sel_bg)
                    self._root_window.option_add("*TCombobox*Listbox.selectForeground", listbox_sel_fg)

                    refresh_combobox_popdown_listboxes(
                        self._root_window,
                        str(listbox_bg),
                        str(listbox_fg),
                        str(listbox_sel_bg),
                        str(listbox_sel_fg),
                    )
                except Exception:
                    pass

                btn_bg = button_theme.get("bg", frame_bg)
                btn_border_base = frame_theme.get("highlightbackground", btn_bg)
                btn_border = ensure_contrast_color(btn_border_base, btn_bg, 0.25)
                btn_light = adjust_hex_color(btn_border, 0.25)
                btn_dark = adjust_hex_color(btn_border, -0.25)
                try:
                    self._style.configure(
                        "TButton",
                        bordercolor=btn_border,
                        lightcolor=btn_light,
                        darkcolor=btn_dark,
                        focuscolor=btn_border,
                    )
                except Exception:
                    pass
                btn_fg = button_theme.get("fg", tab_fg)
                self._style.map(
                    "TButton",
                    background=[("active", btn_bg), ("pressed", btn_bg), ("disabled", btn_bg)],
                    foreground=[("active", btn_fg), ("pressed", btn_fg), ("disabled", btn_fg)],
                )

                # Main processing: style progressbar using theme colors
                self._style.configure(
                    "Primary.Horizontal.TProgressbar",
                    background=progress_theme.get("bg", "#000000"),
                    troughcolor=progress_theme.get("troughcolor", window_theme.get("bg", "#ffffff")),
                    bordercolor=progress_theme.get("bordercolor", progress_theme.get("bg", "#000000")),
                    lightcolor=progress_theme.get("bg", "#000000"),
                    darkcolor=progress_theme.get("bg", "#000000"),
                )

        # Setup ttk style for themeable widgets
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass
        notebook_style_updater = NotebookStyleUpdater(style, main_window)
        EventBus().subscribe(EventNames.THEME_CHANGED, notebook_style_updater.handle_theme_changed)
        # Initialize Notebook styles from the currently loaded theme
        notebook_style_updater.handle_theme_changed(
            theme=theme_manager.get_current_theme(),
            theme_name=theme_manager.get_current_theme_name(),
        )
        
        # Apply all widget colors
        theme_manager.apply_color_theme_all_widgets()
        
        # Configure main window to expand properly
        main_window.rowconfigure(0, weight=1)
        main_window.columnconfigure(0, weight=1)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_window)
        
        # Create frames for each tab
        main_tab = tk.Frame(notebook)
        pdf_ope_tab = tk.Frame(notebook)  # PDF Operation tab
        image_ope_tab = tk.Frame(notebook)  # Image Operation tab (U006)
        description_tab = tk.Frame(notebook)  # Description tab
        licenses_tab = tk.Frame(notebook)  # Licenses tab

        class TabContainerBgUpdater:
            """Update tab container backgrounds when the theme changes.

            EventBus uses weak references, so this object must be strongly
            referenced for the lifetime of the application.
            """

            def __init__(self, containers: list[tk.Frame]) -> None:
                """Initialize updater.

                Args:
                    containers (list[tk.Frame]): Notebook tab container frames.
                """
                self._containers = containers

            def handle_theme_changed(self, theme: dict, theme_name: str) -> None:
                """Apply background to notebook tab containers.

                Args:
                    theme (dict): Theme data published by ColorThemeManager.
                    theme_name (str): Theme name.
                """
                # Main processing: keep tab container background consistent
                window_theme = theme.get("Window", {}) if isinstance(theme, dict) else {}
                window_bg = window_theme.get("bg", "#ffffff")
                frame_theme = theme.get("Frame", {}) if isinstance(theme, dict) else {}
                frame_bg = frame_theme.get("bg", window_bg)
                for container in self._containers:
                    try:
                        container.configure(bg=frame_bg)
                    except Exception:
                        continue

        tab_container_bg_updater = TabContainerBgUpdater(
            containers=[main_tab, pdf_ope_tab, image_ope_tab, description_tab, licenses_tab]
        )
        EventBus().subscribe(EventNames.THEME_CHANGED, tab_container_bg_updater.handle_theme_changed)
        tab_container_bg_updater.handle_theme_changed(
            theme=theme_manager.get_current_theme(),
            theme_name=theme_manager.get_current_theme_name(),
        )
        
        # Add tabs to notebook (text only, no icons)
        notebook.add(main_tab, text=message_manager.get_ui_message("U004"))  # Main tab
        notebook.add(pdf_ope_tab, text=message_manager.get_ui_message("U005"))  # PDF Operation tab
        notebook.add(image_ope_tab, text=message_manager.get_ui_message("U006"))  # Image Operation tab (File Extension and Size)
        notebook.add(description_tab, text=message_manager.get_ui_message("U007"))  # Description tab
        notebook.add(licenses_tab, text=message_manager.get_ui_message("U008"))  # Licenses tab
        
        # Configure notebook to expand properly
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initialize tab content using views and pack to fill frames
        # Create and pack instances so they fill their container frames
        
        # Initialize Main tab
        from views.main_tab import CreateComparisonFileApp
        main_app = CreateComparisonFileApp(main_tab, settings_manager)
        main_app.pack(expand=True, fill="both")

        # Initialize PDF Operation tab
        from views.pdf_ope_tab import PDFOperationApp
        pdf_app = PDFOperationApp(pdf_ope_tab)
        pdf_app.pack(expand=True, fill="both")
        
        # Initialize Image Operation tab (U006)
        from views.image_ope_tab import ImageOperationApp
        image_app = ImageOperationApp(image_ope_tab)
        image_app.pack(expand=True, fill="both")
        
        # Initialize Description tab
        desc_app = DescriptionApp(description_tab)
        desc_app.pack(expand=True, fill="both")
        
        # Initialize Licenses tab
        license_app = LicensesApp(licenses_tab)
        license_app.pack(expand=True, fill="both")

        def _keyboard_chain_for_tab(tab_index: int):
            """Return main-tab focus chain or None to use default Tk traversal.

            Args:
                tab_index: Notebook tab index.

            Returns:
                Ordered focus targets for the main tab, else None.
            """
            if tab_index == 0:
                try:
                    return main_app.build_keyboard_focus_chain()
                except Exception:
                    return None
            if tab_index == 1:
                try:
                    return pdf_app.build_keyboard_focus_chain()
                except Exception:
                    return None
            if tab_index == 2:
                try:
                    return image_app.build_keyboard_focus_chain()
                except Exception:
                    return None
            return None

        KeyboardNavigationShell(
            main_window,
            notebook,
            (main_tab, pdf_ope_tab, image_ope_tab, description_tab, licenses_tab),
            _keyboard_chain_for_tab,
        )

        # Main processing: re-apply theme after tab contents are created.
        theme_manager.apply_color_theme_all_widgets()
        # Main processing: run one more pass after idle so launch-time colors settle.
        main_window.after_idle(theme_manager.apply_color_theme_all_widgets)

        def _focus_main_tab_base_path_entry() -> None:
            """Move keyboard focus to the main tab base path entry when possible."""
            try:
                if not main_window.winfo_exists():
                    return
                main_window.lift()
                main_window.update_idletasks()
                ent = main_app._base_file_path_entry.path_entry
                if ent.winfo_exists():
                    try:
                        notebook.select(main_tab)
                    except tk.TclError:
                        pass
                    ent.focus_force()
                    try:
                        ent.icursor(0)
                    except tk.TclError:
                        pass
            except Exception:
                pass

        def _schedule_startup_base_path_focus() -> None:
            """Schedule focus after theme passes; ``apply_color_theme`` can reset focus."""
            _focus_main_tab_base_path_entry()
            for _delay_ms in (50, 150, 400, 900, 1800, 3500, 6000):
                main_window.after(_delay_ms, _focus_main_tab_base_path_entry)

        main_window.after_idle(_schedule_startup_base_path_focus)

        def _sync_shared_paths_on_tab_change(event: tk.Event) -> None:
            """Refresh shared path fields whenever the active tab changes.

            Args:
                event: Notebook tab-change event.
            """
            for tab_app in (main_app, pdf_app, image_app):
                sync_method = getattr(tab_app, "_sync_shared_paths_from_settings", None)
                if callable(sync_method):
                    try:
                        sync_method(event)
                    except Exception as exc:
                        logger.warning(
                            message_manager.get_log_message(
                                "L227",
                                f"Failed to sync shared paths on tab change: {str(exc)}",
                            )
                        )
            try:
                schedule_main = getattr(main_app, "schedule_canvas_footer_reposition", None)
                if callable(schedule_main):
                    schedule_main()
            except Exception:
                pass
            try:
                schedule_pdf = getattr(pdf_app, "schedule_pdf_canvas_footer_reposition", None)
                if callable(schedule_pdf):
                    schedule_pdf()
            except Exception:
                pass
            try:
                pdf_short = getattr(pdf_app, "set_pdf_tab_shortcuts_active", None)
                if callable(pdf_short):
                    pdf_short(
                        notebook.index(notebook.select()) == notebook.index(pdf_ope_tab)
                    )
            except tk.TclError:
                pass

            def _focus_base_path_for_selected_notebook_tab() -> None:
                """After switching tabs, move focus to that tab's base file path entry."""
                try:
                    sel = notebook.select()
                    idx = int(notebook.index(sel))
                except tk.TclError:
                    return
                ent = None
                try:
                    if idx == int(notebook.index(main_tab)):
                        ent = main_app._base_file_path_entry.path_entry
                    elif idx == int(notebook.index(pdf_ope_tab)):
                        ent = pdf_app._base_file_path_entry.path_entry
                    elif idx == int(notebook.index(image_ope_tab)):
                        ent = image_app._base_file_path_entry.path_entry
                except (tk.TclError, AttributeError):
                    ent = None
                if ent is not None and ent.winfo_exists():
                    try:
                        ent.focus_force()
                        ent.icursor(0)
                    except tk.TclError:
                        pass

            # Idle + short delays so focus wins over reparenting/repaint after tab switch
            # (e.g. Main → PDF → Main should land on base path entry reliably).
            main_window.after_idle(_focus_base_path_for_selected_notebook_tab)
            main_window.after(10, _focus_base_path_for_selected_notebook_tab)
            main_window.after(50, _focus_base_path_for_selected_notebook_tab)

        notebook.bind("<<NotebookTabChanged>>", _sync_shared_paths_on_tab_change)
        try:
            pdf_short0 = getattr(pdf_app, "set_pdf_tab_shortcuts_active", None)
            if callable(pdf_short0):
                pdf_short0(
                    notebook.index(notebook.select()) == notebook.index(pdf_ope_tab)
                )
        except tk.TclError:
            pass

        # Process command line arguments
        set_args()

        print("Starting main event loop")
        # Start the main event loop
        logger.debug(message_manager.get_log_message("L001"))
        main_window.mainloop()
        
        # Ensure cleanup on normal exit
        cleanup()
    except Exception as e:
        logger.critical(message_manager.get_log_message("L017", str(e)))
        print(f"Critical error in main: {e}")
        traceback.print_exc()
        # Always attempt cleanup on errors
        cleanup()
        # Show error message to user
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
