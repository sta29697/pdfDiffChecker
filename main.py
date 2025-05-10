from __future__ import annotations
import logging
from logging import getLogger
import os
import sys
import traceback
import shutil
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from pathlib import Path
from typing import Final

# Core utilities and configuration
from configurations import tool_settings
from configurations.message_manager import get_message_manager
from controllers.event_bus import EventBus, EventNames
from configurations.user_setting_manager import get_user_setting_manager as usm
from controllers.color_theme_manager import ColorThemeManager

# View components
from views.description import DescriptionApp
from views.licenses import LicensesApp

# Initialize singleton message manager at module level
message_manager = get_message_manager()
logger: Final = getLogger(__name__)

def setup_logging() -> None:
    """Set up logging configuration for the application.

    This function configures:
    1. Log file location and format
    2. Console output for debugging
    3. File handler for persistent logging

    The log file is stored in the 'logs' directory with the name 'debug.log'.
    """
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "debug.log"

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(lineno)d): %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )
        
        # File handler for logging to file
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Add handlers to root logger - file only, no console output
        root_logger.addHandler(file_handler)
        
        # Clear any existing handlers to avoid duplicates
        for handler in list(root_logger.handlers):
            if not isinstance(handler, logging.FileHandler):
                root_logger.removeHandler(handler)
                
        # Set PIL logger level to WARNING to suppress verbose PNG file loading logs
        pil_logger = logging.getLogger('PIL')
        pil_logger.setLevel(logging.WARNING)
        # Direct log message specification before message manager initialization
        logger.info("[SYS] Logging system initialized")
        # This log will be multilingualized later through message_manager
    except Exception as e:
        error_msg = str(e)
        # Direct log message specification before message manager initialization
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
        logger.debug(message_manager.get_log_message("L179"))

        # Create necessary directories
        logger.debug(message_manager.get_log_message("L180"))
        temp_dir = Path(tool_settings.BASE_DIR) / "temp"
        temp_dir.mkdir(exist_ok=True)
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
    return "images/LOGO_032.ico"


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
        # Use project-local temp directory for cleanup
        temp_dir = Path(tool_settings.BASE_DIR) / "temp"
        if temp_dir.exists():
            try:
                # First delete files, then delete directories
                # Delete files
                for file in temp_dir.glob("**/*"):
                    if file.is_file():
                        try:
                            file.unlink()
                        except Exception as e:
                            # Log but continue if a file can't be deleted
                            logger.warning(message_manager.get_log_message("L227", str(e)))
                
                # Delete directories (using shutil to remove non-empty directories)
                for dir_path in temp_dir.glob("*/"):
                    if dir_path.is_dir() and dir_path != temp_dir:
                        try:
                            shutil.rmtree(dir_path)
                            logger.debug(f"Removed directory: {dir_path}")
                        except Exception as e:
                            logger.warning(message_manager.get_log_message("L227", str(e)))
                # Use the global message_manager
                logger.info(message_manager.get_log_message("L225", ""))
            except Exception as e:
                # Log but continue if temp directory can't be cleaned
                logger.error(message_manager.get_log_message("L228", str(e)))

        # Save user settings
        try:
            settings = usm()
            settings.save_settings()
            # Use the global message_manager
            logger.info(message_manager.get_log_message("L226", ""))
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
    return "v1.0.0"


def set_args() -> dict:
    """Process command line arguments.
    
    Returns:
        dict: Dictionary of processed arguments
    """
    # Simple placeholder for argument processing
    return {}


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
    global message_manager
    
    try:
        print("Starting application...")
        # Initialize the application (sets up logging, creates directories, etc.)
        initialize_application()
        
        # Reinitialize message_manager if it's None or not defined
        if 'message_manager' not in globals() or message_manager is None:
            message_manager = get_message_manager()
            
        # Directory creation log with directory path
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
        logger.info(message_manager.get_log_message("L014", temp_dir))

        # Create main window (WindowEventManager is initialized inside create_main_window)
        main_window = create_main_window()
        
        # Set window title with version information
        version_info = get_version_info()
        main_window.title(f"PDF Diff Checker {version_info}")
        
        # Set window icon
        icon_path = change_logo_icon()
        if os.path.exists(icon_path):
            try:
                main_window.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(message_manager.get_log_message("L227", f"Failed to set window icon: {str(e)}"))
        
        # Set window geometry
        main_window.geometry("800x600")
        
        # Initialize color theme manager for theme control and force dark theme
        theme_manager = ColorThemeManager.get_instance()
        theme_manager.init_color_theme()
        # Force apply dark theme
        theme_manager.load_theme("dark", force_reload=True)
        
        # Setup ttk style for dark theme
        style = ttk.Style()
        style.configure('TFrame', background='#2d2d2d')
        style.configure('TNotebook', background='#2d2d2d')
        style.configure('TNotebook.Tab', background='#2d2d2d', foreground='white', padding=[10, 2])
        style.map('TNotebook.Tab', background=[('selected', '#3d3d3d')], foreground=[('selected', 'white')])
        style.configure('TLabel', background='#2d2d2d', foreground='white')
        style.configure('TButton', background='#3d3d3d', foreground='white')
        style.configure('TEntry', fieldbackground='#3d3d3d', foreground='white')
        
        # Apply all widget colors
        theme_manager.apply_color_theme_all_widgets()
        
        # Configure main window to expand properly
        main_window.rowconfigure(0, weight=1)
        main_window.columnconfigure(0, weight=1)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_window)
        
        # Create frames for each tab
        # main_tab = tk.Frame(notebook)  # Main tab is still disabled
        pdf_ope_tab = tk.Frame(notebook)  # PDF Operation tab
        # image_ope_tab = tk.Frame(notebook)  # Image Operation tab is still disabled
        description_tab = tk.Frame(notebook)  # Description tab
        licenses_tab = tk.Frame(notebook)  # Licenses tab
        
        # Add tabs to notebook (text only, no icons)
        # notebook.add(main_tab, text=message_manager.get_ui_message("U001"))  # Main tab
        notebook.add(pdf_ope_tab, text=message_manager.get_ui_message("U005"))  # PDF Operation tab
        # notebook.add(image_ope_tab, text=message_manager.get_ui_message("U003"))  # Image Operation tab
        notebook.add(description_tab, text=message_manager.get_ui_message("U007"))  # Description tab
        notebook.add(licenses_tab, text=message_manager.get_ui_message("U008"))  # Licenses tab
        
        # Configure notebook to expand properly
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initialize tab content using views and pack to fill frames
        # Create and pack instances so they fill their container frames
        
        # Initialize PDF Operation tab
        from views.pdf_ope_tab import PDFOperationApp
        pdf_app = PDFOperationApp(pdf_ope_tab)
        pdf_app.pack(expand=True, fill="both")
        
        # Initialize Description tab
        desc_app = DescriptionApp(description_tab)
        desc_app.pack(expand=True, fill="both")
        
        # Initialize Licenses tab
        license_app = LicensesApp(licenses_tab)
        license_app.pack(expand=True, fill="both")
        
        # Language is fixed to Japanese, so language switching buttons are not needed
        # Set default language to Japanese
        message_manager.set_language("ja")
        
        # Pack notebook to fill the window
        notebook.pack(expand=True, fill=tk.BOTH)
        
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
