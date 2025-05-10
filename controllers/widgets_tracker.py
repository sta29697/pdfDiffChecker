from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator
from logging import getLogger
from typing import List, Protocol, runtime_checkable, Dict, Any, Final

from configurations.message_manager import get_message_manager
from controllers.event_bus import EventBus, EventNames
from controllers.app_state import AppState

# Constants for component names in events
THEME_COMPONENT_NAME: Final[str] = "ColorThemeManager"

message_manager = get_message_manager()

logger = getLogger(__name__)


@runtime_checkable
class ThemeColorApplicable(Protocol):
    """Protocol for widgets that can apply theme colors.

    This protocol defines the interface for widgets that support theme color application.
    It is used as a marker interface to identify widgets that can be themed.

    Note:
        The theme_colors parameter in apply_theme_color should match the structure
        defined in ThemeColors TypedDict from color_theme_manager.py
    """

    def apply_theme_color(self, theme_colors: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the widget.

        Args:
            theme_colors: Dictionary containing theme colors to apply.
                        The outer dict keys are widget types (e.g., 'Button', 'Frame'),
                        and the inner dict contains color settings as str key-value pairs.
        """
        ...


@runtime_checkable
class WidgetWithChildren(Protocol):
    """Protocol for widgets that have children and can be themed.

    This protocol defines the interface for widgets that have children and support theming.
    Used to ensure proper traversal of the widget hierarchy during theme application.
    """

    def winfo_children(self) -> List[tk.Misc]:
        """Get the children of the widget.

        Returns:
            List of child widgets as tk.Misc.
            tk.Misc is the base class for all tkinter widgets.
        """
        ...

    def winfo_class(self) -> str:
        """Get the class name of the widget.

        Returns:
            Widget class name as a string.
            Used for identifying widget types in theme application.
        """
        ...


class WidgetsTracker:
    """Singleton class for tracking and theming widgets.

    This class manages the registration and theme application for all widgets
    in the application. It maintains a single source of truth for widget references
    and ensures that when the theme changes, all registered widgets are updated.
    
    Subscribes to event bus events to coordinate theme application timing.

    Now uses event-driven architecture to receive theme changes from ColorThemeManager
    without direct dependencies, solving circular dependency issues.

    Note:
        Uses tk.Misc as the base type for all widgets to ensure compatibility
        with both tk and ttk widgets while maintaining type safety.

    Attributes:
        __instance: Singleton instance of WidgetsTracker.
        __registered_widgets: List of registered widgets that support theme colors.
        __theme_initialized: Flag indicating if theme system is initialized.
        __current_theme: Current theme data received from events.
    """

    __instance: WidgetsTracker | None = None
    __registered_widgets: List[ThemeColorApplicable] = []
    __theme_initialized: bool = False
    __current_theme: Dict[str, Any] = {}
    __widget_origins: Dict[int, Dict[str, Any]] = {}  # Dict to store parent file information for each widget

    def __new__(cls) -> WidgetsTracker:
        """Create a new instance of WidgetsTracker using singleton pattern.

        Returns:
            Single instance of WidgetsTracker.
        """
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
        
    def __del__(self) -> None:
        """Clean up resources when WidgetsTracker is garbage collected.
        
        Unsubscribes from all events to prevent memory leaks and clears all stored widget data.
        """
        try:
            # Unsubscribe from all events
            EventBus().unsubscribe_all(self)
            # Clear widget origins dictionary to prevent memory leaks
            self.__widget_origins.clear()
            # Clear registered widgets list
            self.__registered_widgets.clear()
            # Log that WidgetsTracker has unsubscribed from all events and cleaned up resources
            logger.debug(message_manager.get_log_message("L035"))
        except Exception:
            # Ignore errors during shutdown
            pass
            
    def __init__(self) -> None:
        """Initialize the WidgetsTracker and set up event subscriptions.
        
        Subscribes to theme-related events from the EventBus to receive
        notifications when themes change without direct dependency on ColorThemeManager.
        """
        # Only run initialization once (singleton pattern)
        if not hasattr(self, "_WidgetsTracker__initialized"):
            # Register event listeners
            self.__initialized = True
            
            # Subscribe to theme change events
            EventBus().subscribe(EventNames.THEME_CHANGED, self._handle_theme_changed)
            
            # Subscribe to app initialization events
            EventBus().subscribe(EventNames.PHASE1_COMPLETED, self._handle_phase1_completed)
            EventBus().subscribe(EventNames.WIDGETS_REGISTRATION_COMPLETED, self._handle_widgets_registration_completed)
            EventBus().subscribe(EventNames.THEME_APPLICATION_COMPLETED, self._handle_theme_application_completed)
            EventBus().subscribe(EventNames.TAB_LAYOUT_COMPLETED, self._handle_tab_layout_completed)
            
            # Log initialization with message code
            logger.debug(message_manager.get_log_message("L258", "WidgetsTracker"))
    
    def _handle_theme_changed(self, theme: Dict[str, Any], theme_name: str) -> None:
        """Handle theme changed event.
        
        Args:
            theme: Theme data from event
            theme_name: Name of the theme
        """
        # Store the current theme 
        self.__current_theme = theme 
        self.__theme_initialized = True
        
        # Apply theme to all registered widgets
        self.apply_colors_to_widgets(theme)
        # Use the appropriate message code for theme application to multiple widgets
        logger.debug(message_manager.get_log_message("L231", theme_name, len(self.__registered_widgets)))
    
    def _handle_phase1_completed(self) -> None:
        """Handle phase 1 completion event.
        
        This is called when main initialization phase 1 is completed,
        before widgets are registered and themed.
        """
        # Log phase 1 completion received
        logger.debug(message_manager.get_log_message("L259", "Phase 1"))
    
    def _handle_widgets_registration_completed(self) -> None:
        """Handle widgets registration completion event.
        
        This is called when all widgets have been registered to the tracker,
        and before themes are applied.
        """
        # Log widget registration completion received
        logger.debug(message_manager.get_log_message("L259", "Widgets Registration"))
        
    def _handle_theme_application_completed(self) -> None:
        """Handle theme application completion event.
        
        This is called when theme application has been completed for all widgets.
        """
        # Log theme application completion received
        logger.debug(message_manager.get_log_message("L259", "Theme Application"))
        
    def _handle_tab_layout_completed(self) -> None:
        """Handle tab layout completion event.
        
        This is called when all tabs have been laid out and are ready to use.
        Enables detailed widget initialization logging after this point.
        """
        # Log tab layout completion received
        logger.debug(message_manager.get_log_message("L259", "Tab Layout"))
        
        # Enable widget initialization logs after tabs are laid out
        # This will allow detailed logging for widgets created after this point
        # while suppressing noise during initial application startup
        AppState.enable_widget_init_logs = True
        
        # Count uninitialized theme widgets and log a summary instead of individual messages
        uninitialized_widgets = []
        for widget in self.__registered_widgets:
            if hasattr(widget, "_theme_not_initialized") and getattr(widget, "_theme_not_initialized", False):
                # Get widget module.class information
                widget_info = f"{widget.__class__.__name__}"
                if hasattr(widget, "__module__"):
                    widget_info = f"{widget.__module__}.{widget_info}"
                
                # Get detailed origin information from the tracker
                widget_id = id(widget)
                origin_details = self.__widget_origins.get(widget_id, {})
                
                if origin_details:
                    # Use detailed origin information if available
                    file_name = origin_details.get("creator_file", "unknown")
                    func_name = origin_details.get("func_name", "")
                    line_num = origin_details.get("line_num", 0)
                    
                    # Build a more informative widget description
                    if file_name != "unknown":
                        # Include function name and line number for more precise identification
                        creator_info = f"{file_name}:{func_name}:{line_num}"
                        uninitialized_widgets.append(f"{widget_info} ({creator_info})")
                    else:
                        uninitialized_widgets.append(widget_info)
                else:
                    # Fall back to simple creator file if detailed info is not available
                    if hasattr(widget, "_creator_file"):
                        file_name = getattr(widget, "_creator_file")
                        if file_name != "unknown":
                            creator_info = f"{file_name}"
                            uninitialized_widgets.append(f"{widget_info} ({creator_info})")
                        else:
                            uninitialized_widgets.append(widget_info)
                    else:
                        uninitialized_widgets.append(widget_info)
        
        # Log a summary count of uninitialized widgets
        if uninitialized_widgets:
            count = len(uninitialized_widgets)
            # Log only the count as debug info
            logger.debug(message_manager.get_log_message("L228", count))
            
            # Log detailed list at trace level (will not appear in normal debug logs)
            if count < 10:  # Only show detailed list for small numbers
                for widget_info in uninitialized_widgets:
                    logger.debug(message_manager.get_log_message("L264", f"{widget_info}"))
            # Otherwise just show the count
    
    def _handle_app_initializing(self, component: str) -> None:
        """Handle application initializing event.
        
        Legacy method - maintained for backwards compatibility.
        Args:
            component: The component that is initializing
        """
        if component == THEME_COMPONENT_NAME:
            # Use a proper message code for theme initialization started
            logger.debug(message_manager.get_log_message("L185"))
            
    def _handle_app_initialized(self, component: str, theme_name: str, fallback: bool = False) -> None:
        """Handle application initialized event.
        
        Args:
            component: The component that finished initializing
            theme_name: Name of the initialized theme
            fallback: Whether this is a fallback theme
        """
        if component == THEME_COMPONENT_NAME:
            self.__theme_initialized = True
            # Use theme initialization message with appropriate theme name
            # Pass theme name as an argument here, it will be formatted by the message template
            theme_info = f"fallback: {theme_name}" if fallback else theme_name
            logger.debug(message_manager.get_log_message("L186", theme_info))
    
    def apply_colors_to_widgets(self, theme: Dict[str, Any]) -> None:
        """Apply colors to all registered widgets.
        
        Args:
            theme: Theme data to apply
        """
        # Get actual caller information for accurate logging
        import inspect
        import os
        
        frame = inspect.currentframe()
        caller_info = "unknown"  # Default value when caller cannot be identified
        if frame:
            # Scan up the stack to find the most relevant caller frame
            frames = inspect.getouterframes(frame)
            # Start from 1 to skip this function
            for i in range(1, min(5, len(frames))):
                # Look for tab-related files or other meaningful sources
                file_path = frames[i].filename
                file_name = os.path.basename(file_path)
                if "_tab" in file_name or "tab_" in file_name or file_name == "main.py" or file_name == "licenses.py":
                    caller_info = file_name
                    break
                
        logger.debug(message_manager.get_log_message("L038", f"Applying theme from {caller_info}"))
        
        # Count the number of widgets
        widget_count = 0
        
        # Apply theme to all registered widgets with proper caller context
        for widget in self.__registered_widgets:
            try:
                if hasattr(widget, "apply_theme_color"):
                    # Get the original registration information for each widget
                    original_creator = "unknown"
                    
                    # If _creator_file is already set, use that information
                    if hasattr(widget, "_creator_file"):
                        original_creator = getattr(widget, "_creator_file")
                    
                    # Set context information (using the original creator info of each widget instead of caller_info)
                    caller_context = {"file": original_creator, "caller": caller_info}
                    widget_count += 1
                    
                    # Permanently set context information to the widget
                    setattr(widget, "_caller_context", caller_context)
                    
                    # Apply theme
                    widget.apply_theme_color(theme)  # type: ignore[arg-type]
            except Exception as e:
                widget_info = f"{widget.__class__.__name__}"
                if hasattr(widget, "__module__"):
                    widget_info = f"{widget.__module__}.{widget_info}"
                # Log error when applying theme to widget fails
                logger.debug(message_manager.get_log_message("L067", f"{widget_info}", str(e)))
    
    @property
    def registered_widgets(self) -> List[ThemeColorApplicable]:
        """Get the list of registered widgets.

        Returns:
            List of registered widgets that support theme colors.
        """
        return self.__registered_widgets
        
    def remove_widget(self, widget: ThemeColorApplicable) -> None:
        """Remove a widget from the registry when it's destroyed.
        
        This method is called when a widget is destroyed to clean up all tracking information.
        It prevents memory leaks by removing all references to the widget from the tracker.
        
        Args:
            widget: Widget to remove from tracking.
        """
        if widget in self.__registered_widgets:
            # Remove from registered widgets list
            self.__registered_widgets.remove(widget)
            
            # Remove widget origin information
            widget_id = id(widget)
            if widget_id in self.__widget_origins:
                del self.__widget_origins[widget_id]
                
            # Widget removal logging removed - L229 message code was deleted
        
    def add_widgets(self, widget: ThemeColorApplicable) -> None:
        """Add a widget to the registry.
        
        Registers widget for theme color updates. If theme initialization is complete, 
        the current theme will be applied immediately to the widget.
        
        This method now implements improved origin tracking to better identify where
        widgets are actually used/created, especially for shared/common widgets.
        
        Args:
            widget: Widget to register for theme color application.
        """
        if widget:
            # Skip if widget is already registered
            if widget in self.__registered_widgets:
                return
                
            # Add to registry
            self.__registered_widgets.append(widget)
            
            # Get widget info for logging
            widget_info = f"{widget.__class__.__name__}"
            if hasattr(widget, "__module__"):
                widget_info = f"{widget.__module__}.{widget_info}"
                
            # Get calling frame info to include tab information
            import inspect
            import os
            caller_frame = inspect.currentframe()
            caller_info = ""
            creator_file = "unknown"
            widget_id = id(widget)
            origin_info = {}
            
            # Store the full call stack to track widget origins more accurately
            if caller_frame is not None:
                # Collect all candidate files from the stack for better tracking
                candidate_files = []
                frame = caller_frame.f_back
                frame_index = 0
                
                while frame and frame_index < 10:  # Limit to 10 frames to avoid excessive searching
                    file_path = frame.f_code.co_filename
                    file_name = os.path.basename(file_path)
                    line_num = frame.f_lineno
                    func_name = frame.f_code.co_name
                    
                    # Store frame information in the candidate list
                    candidate_files.append({
                        "file_name": file_name,
                        "file_path": file_path,
                        "line_num": line_num,
                        "func_name": func_name,
                        "priority": 0  # Default priority
                    })
                    
                    # Prioritize different file types
                    if "_tab" in file_name or "tab_" in file_name:
                        # Tab files get highest priority
                        candidate_files[-1]["priority"] = 10
                    elif file_name == "main.py" or file_name == "licenses.py":
                        # Special files get high priority
                        candidate_files[-1]["priority"] = 8
                    elif file_name.startswith("view_") or "_view" in file_name or "/views/" in file_path:
                        # View files get medium-high priority
                        candidate_files[-1]["priority"] = 7
                    elif "widget" in file_name and file_name != "widgets_tracker.py":
                        # Widget files get medium priority (but not the tracker itself)
                        candidate_files[-1]["priority"] = 5
                    else:
                        # Other files get lower priority based on depth in the stack
                        # Files deeper in the stack get lower priority
                        candidate_files[-1]["priority"] = 3 - min(frame_index, 3)
                    
                    frame = frame.f_back
                    frame_index += 1
                
                # Sort by priority to find the best candidate
                candidate_files.sort(key=lambda x: x["priority"], reverse=True)
                
                # Use the highest priority file as the creator
                if candidate_files:
                    best_candidate = candidate_files[0]
                    # Explicitly cast to string to satisfy type checking
                    creator_file = str(best_candidate["file_name"])
                    caller_info = f" (called from: {creator_file})"
                    
                    # Store detailed origin information
                    origin_info = {
                        "creator_file": creator_file,
                        "file_path": best_candidate["file_path"],
                        "line_num": best_candidate["line_num"],
                        "func_name": best_candidate["func_name"],
                        "candidates": candidate_files
                    }
            
            # Store the origin information in the tracker's dictionary
            self.__widget_origins[widget_id] = origin_info
                    
            # Save creator file information to the widget
            setattr(widget, "_creator_file", creator_file)
            
            # Add color_key to widget_info if available for better identification
            if hasattr(widget, "_BaseEntry__color_key") and getattr(widget, "_BaseEntry__color_key", None):
                widget_info = f"{widget_info} (color_key={widget._BaseEntry__color_key})"
            elif hasattr(widget, "color_key") and getattr(widget, "color_key", None):
                widget_info = f"{widget_info} (color_key={widget.color_key})"
                
            # Only log registration if enabled by AppState
            from controllers.app_state import AppState
            
            # Check if we should log this widget registration based on its class
            if AppState.should_log_widget_registration(widget.__class__.__name__):
                # Log registration with improved details using the standard widget registration message code
                # Include caller tab information if available
                logger.debug(message_manager.get_log_message("L033", f"{widget_info}{caller_info}"))
            
            # Setup widget destruction listener if it's a tkinter widget
            if isinstance(widget, tk.BaseWidget) and hasattr(widget, "bind"):
                # Register widget destruction callback to remove it from tracker
                # Define a typed callback for the Destroy event
                def destroy_callback(event: tk.Event, target_widget: ThemeColorApplicable = widget) -> None:
                    self.remove_widget(target_widget)
                    
                widget.bind("<Destroy>", destroy_callback)
                
            # Publish widget registration event (for other components that may be interested)
            EventBus().publish(
                EventNames.WIDGET_REGISTERED,
                widget=widget,
                widget_info=widget_info
            )
            
            # If theme system is initialized, apply current theme immediately
            if self.__theme_initialized and self.__current_theme:
                try:
                    if hasattr(widget, "apply_theme_color"):
                        widget.apply_theme_color(self.__current_theme)  # type: ignore[arg-type]
                        # Only log theme application if enabled by AppState
                        from controllers.app_state import AppState
                        if AppState.log_theme_application:
                            # Log successful theme application to widget using theme application message code
                            logger.debug(message_manager.get_log_message("L039", widget_info))
                except Exception as e:
                    # Log error when applying theme to widget
                    error_info = f"{widget_info}: {str(e)}"
                    logger.debug(message_manager.get_log_message("L067", error_info))
            # Set a flag for later logging if theme is not initialized
            elif not self.__theme_initialized and hasattr(widget, "apply_theme_color"):
                # Mark the widget - theme uninitialized will be displayed after tab layout is completed
                setattr(widget, "_theme_not_initialized", True)

    def _is_compatible_widget(self, widget: tk.Misc, child: tk.Misc) -> bool:
        """Check if a child widget is compatible with its parent.

        Uses tk.Misc as the base type to handle all widget types uniformly.
        Performs runtime checks for widget compatibility.

        Args:
            widget: Parent widget (tk.Misc).
            child: Child widget to check (tk.Misc).

        Returns:
            True if child is compatible with parent, False otherwise.
        """
        try:
            # Relaxed type checking as we're using tk.Misc
            return isinstance(child, WidgetWithChildren) and isinstance(
                widget, type(child)
            )
        except Exception as e:
            # L034: Error occurred while checking widget compatibility
            logger.error(
                message_manager.get_log_message("L034", widget, child, e)
            )
            return False

    def _get_widget_children(self, widget: tk.Misc) -> Iterator[tk.Misc]:
        """Get all children of a widget that match its type.

        Traverses the widget hierarchy to find all compatible child widgets.
        Uses tk.Misc as the base type for uniform handling of all widget types.

        Args:
            widget: The widget (tk.Misc) to get children from.

        Returns:
            Iterator of child widgets (also tk.Misc).

        Note:
            Skips widgets that don't implement WidgetWithChildren protocol.
        """
        try:
            if not isinstance(widget, WidgetWithChildren):
                yield from ()  # Return empty iterator explicitly

            for child in widget.winfo_children():
                if self._is_compatible_widget(widget, child):
                    yield child
                    yield from self._get_widget_children(child)
        except Exception as e:
            # L035: Error occurred while getting widget children
            logger.error(message_manager.get_log_message("L035", e))
            yield from ()  # Return empty iterator explicitly

    def remove_widgets(self, widget: tk.Misc) -> None:
        """Remove a widget and its children from tracking.

        Recursively removes all themed child widgets from the registry.
        Uses tk.Misc as the base type for widget parameters.

        Args:
            widget: The root widget to unregister (tk.Misc).
        """
        try:
            for child in self._get_widget_children(widget):
                if isinstance(child, ThemeColorApplicable) and hasattr(
                    child, "apply_theme_color"
                ):
                    self.__registered_widgets.remove(child)
                    # L036: Removed child widget from theme color tracking
                    logger.debug(message_manager.get_log_message("L036", child))
        except Exception as e:
            # L037: Error occurred while removing widgets
            logger.error(message_manager.get_log_message("L037", e))
