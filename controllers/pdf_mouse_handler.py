from __future__ import annotations

from logging import getLogger
from typing import Any, Optional

# Only import what we need
from controllers.mouse_event_handler import MouseEventHandler
from configurations.message_manager import get_message_manager
from utils.log_throttle import LogThrottle, transform_throttle

logger = getLogger(__name__)
message_manager = get_message_manager()

class PDFMouseHandler:
    """Handler for mouse events in PDF viewer."""
    
    # Class variable for tracking zoom scale logging
    _last_logged_scale: float = 1.0
    
    def __init__(self, parent: Any) -> None:
        """Initialize the PDF mouse handler.
        
        Args:
            parent: Parent widget that contains the canvas and transform data
        """
        self.parent = parent
        self.mouse_handler: Optional[MouseEventHandler] = None
        self._zoom_log_throttle = LogThrottle(min_interval=1.0)
        self._mouse_down_log_throttle = LogThrottle(min_interval=1.0)
        self._mouse_move_log_throttle = LogThrottle(min_interval=5.0)
        self._mouse_up_log_throttle = LogThrottle(min_interval=1.0)
        self._mouse_move_error_throttle = LogThrottle(min_interval=5.0)
        self._transform_log_throttle = LogThrottle(min_interval=1.0)
    
    def initialize_mouse_handler(self) -> None:
        """Initialize the mouse event handler.
        
        This method creates a new MouseEventHandler instance and configures it
        for use with the PDF viewer.
        """
        try:
            # Initialize base transform data if not already created
            if not hasattr(self.parent, 'base_transform_data'):
                # Default transformation: no rotation, no translation, scale=1.0
                self.parent.base_transform_data = [(0.0, 0.0, 0.0, 1.0)] * self.parent.page_count
                
            # Create a dictionary for layer transform data
            # For PDF operation tab, we only have one layer (base)
            layer_transform_data = {0: self.parent.base_transform_data}
            
            # Create a dictionary for layer visibility
            # For PDF operation tab, only the base layer is visible
            visible_layers = {0: True}
            
            # Create mouse event handler with current page index
            self.mouse_handler = MouseEventHandler(
                layer_transform_data=layer_transform_data,
                current_page_index=self.parent.current_page_index if hasattr(self.parent, 'current_page_index') else 0,
                visible_layers=visible_layers,
                on_transform_update=self.parent._on_transform_update
            )
            
            # Log successful initialization with correct tag
            logger.debug(message_manager.get_log_message("L344", "mouse_handler_initialized"))
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L067", str(e)))
            import traceback
            logger.error(traceback.format_exc())
    
    def setup_mouse_events(self) -> None:
        """Set up mouse events for canvas operations."""
        try:
            # Initialize mouse handler if not already created
            if not self.mouse_handler:
                self.initialize_mouse_handler()
            
            # Important: Attach MouseEventHandler to canvas to enable keyboard shortcuts and mouse events
            if self.mouse_handler:
                self.mouse_handler.attach_to_canvas(self.parent.canvas)
                logger.debug(message_manager.get_log_message("L301", "MouseEventHandler attached to canvas"))
                
            # Bind mouse wheel event for zooming
            # Use a stronger binding with '+' to ensure our handler gets priority
            self.parent.canvas.bind("<MouseWheel>", self.on_mouse_wheel, add="+")  # Windows
            self.parent.canvas.bind("<Button-4>", self.on_mouse_wheel, add="+")  # Linux scroll up
            self.parent.canvas.bind("<Button-5>", self.on_mouse_wheel, add="+")  # Linux scroll down
            
            # Log that mouse wheel bindings are set up
            logger.debug(message_manager.get_log_message("L344", "mouse_wheel_bindings_setup"))
            
            # Bind mouse button events for dragging and rotation
            # Use a separate function for Button-1 to avoid conflict with focus_set
            def on_button_press(event):
                self.parent.canvas.focus_set()
                self.on_mouse_down(event)
                
            self.parent.canvas.bind("<ButtonPress-1>", on_button_press)
            self.parent.canvas.bind("<B1-Motion>", self.on_mouse_move)
            self.parent.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
            
            # Bind keyboard shortcuts for zoom
            self.parent.canvas.bind("<Control-plus>", self.on_zoom_in)
            self.parent.canvas.bind("<Control-minus>", self.on_zoom_out)
            
            # Make canvas focusable for keyboard events
            self.parent.canvas.config(takefocus=1)
            
            # Important: Make sure the canvas has focus to receive keyboard events
            self.parent.canvas.focus_set()
            
            # Note: Other keyboard shortcuts like rotation are handled by MouseEventHandler
            # through the attach_to_canvas method called above
            
            # Log successful setup with correct tag
            logger.debug(message_manager.get_log_message("L412"))
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L067", str(e)))
            import traceback
            logger.error(traceback.format_exc())
    
    def on_mouse_wheel(self, event: Any) -> str | None:
        """Handle mouse wheel events for zooming in/out by delegating to MouseEventHandler.
        
        Args:
            event: Mouse wheel event
        """
        try:
            # Check if mouse handler is initialized
            if not self.mouse_handler:
                logger.warning(message_manager.get_log_message("L300", "Mouse handler not initialized"))
                return None
                
            # Get the delta - Windows uses event.delta
            # Normalize the delta for consistent behavior
            delta = event.delta if hasattr(event, 'delta') else 0
            
            # For Linux/Unix platforms
            if hasattr(event, 'num'):
                if event.num == 4:  # Scroll up
                    delta = 120
                elif event.num == 5:  # Scroll down
                    delta = -120
                    
            # Determine zoom direction
            zoom_factor = 1.0  # Default: no change
            if delta > 0:
                # Zoom in (make larger)
                zoom_factor = 1.1  # Increase by 10%
                if self._zoom_log_throttle.should_log("zoom_in"):
                    logger.debug(message_manager.get_log_message("L347", str(zoom_factor)))
            elif delta < 0:
                # Zoom out (make smaller)
                zoom_factor = 0.9  # Decrease by 10%
                if self._zoom_log_throttle.should_log("zoom_out"):
                    logger.debug(message_manager.get_log_message("L347", str(zoom_factor)))
            
            # Apply zoom to current page with mouse position as center
            if hasattr(self.parent, 'base_transform_data') and self.parent.current_page_index < len(self.parent.base_transform_data):
                # Get current transformation
                rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                
                # Get mouse position relative to canvas
                mouse_x = event.x
                mouse_y = event.y
                
                # Calculate the point in the image space before zoom
                img_x = (mouse_x - tx) / scale
                img_y = (mouse_y - ty) / scale
                
                # Apply zoom factor to scale
                new_scale = scale * zoom_factor
                
                # Limit scale to reasonable bounds (0.1 to 10.0)
                new_scale = max(0.1, min(10.0, new_scale))
                
                # Calculate new translation to keep mouse point fixed
                new_tx = mouse_x - img_x * new_scale
                new_ty = mouse_y - img_y * new_scale
                
                # Update transformation data
                self.parent.base_transform_data[self.parent.current_page_index] = (rotation, new_tx, new_ty, new_scale)
                
                # Store scale factor for use in _display_page
                self.parent.scale_factor = new_scale
                
                # Update mouse handler state if available
                if self.mouse_handler:
                    self.mouse_handler.update_state(
                        current_page_index=self.parent.current_page_index,
                        visible_layers={0: True}
                    )
                
                # Update display
                self.parent._on_transform_update()
                
                # Return 'break' to prevent the event from being processed further
                return "break"
                
        except Exception as e:
            # Always log errors regardless of throttling
            logger.error(message_manager.get_log_message("L302", str(e)))
            import traceback
            logger.error(traceback.format_exc())
        
        # Reset bindings immediately to ensure wheel events are captured
        self.rebind_mouse_wheel()
        
        # Return None for all other cases
        return None
    
    def rebind_mouse_wheel(self) -> None:
        """Rebind mouse wheel event bindings."""
        # Ensure mouse handler is initialized before binding events
        if not self.mouse_handler:
            self.initialize_mouse_handler()
            
        self.parent.canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.parent.canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux UP
        self.parent.canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux DOWN
    
    def on_mouse_down(self, event: Any) -> None:
        """Handle mouse button press events.
        
        Args:
            event: Mouse button press event
        """
        try:
            # Initialize mouse handler if not already created
            if not self.mouse_handler:
                self.initialize_mouse_handler()
                
            # Process mouse down event if handler exists
            if self.mouse_handler:
                self.mouse_handler.on_mouse_down(event)
                
                # Log mouse down event with throttling
                if self._mouse_down_log_throttle.should_log("mouse_down"):
                    logger.debug(message_manager.get_log_message("L362", str(event.x), str(event.y)))
        except Exception as e:
            logger.error(message_manager.get_log_message("L306", str(e)))
    
    def on_mouse_move(self, event: Any) -> None:
        """Handle mouse movement events.
        
        Args:
            event: Mouse movement event
        """
        try:
            # Initialize mouse handler if not already created
            if not self.mouse_handler:
                self.initialize_mouse_handler()
                
            # Process mouse move event if handler exists
            if self.mouse_handler:
                self.mouse_handler.on_mouse_drag(event)  # Use on_mouse_drag instead of on_mouse_move
                
                # Log transform update with throttling
                if self._transform_log_throttle.should_log("transform_update") and hasattr(self.parent, 'base_transform_data') and self.parent.current_page_index < len(self.parent.base_transform_data):
                    rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                    logger.debug(message_manager.get_log_message("L368", str(scale), str(tx), str(ty)))
                
                self.parent._on_transform_update()
                
                # Log mouse move event with extreme throttling (very frequent event)
                if self._mouse_move_log_throttle.should_log("mouse_move"):
                    logger.debug(message_manager.get_log_message("L363", str(event.x), str(event.y)))
        except Exception as e:
            # Only log errors occasionally to avoid flooding the log
            if self._mouse_move_error_throttle.should_log("mouse_move_error"):
                logger.error(message_manager.get_log_message("L308", str(e)))
    
    def on_mouse_up(self, event: Any) -> None:
        """Handle mouse button release events.
        
        Args:
            event: Mouse button release event
        """
        try:
            # Initialize mouse handler if not already created
            if not self.mouse_handler:
                self.initialize_mouse_handler()
                
            # Process mouse up event if handler exists
            if self.mouse_handler:
                self.mouse_handler.on_mouse_up(event)
                
                # Log transform update with throttling
                if self._transform_log_throttle.should_log("transform_update") and hasattr(self.parent, 'base_transform_data') and self.parent.current_page_index < len(self.parent.base_transform_data):
                    rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                    logger.debug(message_manager.get_log_message("L368", str(scale), str(tx), str(ty)))
                
                self.parent._on_transform_update()
                
                # Log mouse up event with throttling
                if self._mouse_up_log_throttle.should_log("mouse_up"):
                    logger.debug(message_manager.get_log_message("L364", str(event.x), str(event.y)))
        except Exception as e:
            logger.error(message_manager.get_log_message("L310", str(e)))
    
    def on_zoom_in(self, event: Any = None) -> None:
        """Handle zoom in keyboard shortcut.
        
        Args:
            event: Keyboard event (optional)
        """
        try:
            # Apply zoom in directly
            if hasattr(self.parent, 'base_transform_data') and self.parent.current_page_index < len(self.parent.base_transform_data):
                # Get current transformation
                rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                
                # Apply zoom factor to scale (increase by 10%)
                new_scale = scale * 1.1
                
                # Limit scale to reasonable bounds (0.1 to 10.0)
                new_scale = max(0.1, min(10.0, new_scale))
                
                # Update transformation data
                self.parent.base_transform_data[self.parent.current_page_index] = (rotation, tx, ty, new_scale)
                
                # Store scale factor for use in _display_page
                self.parent.scale_factor = new_scale
                
                # Only log significant zoom changes to reduce log noise
                # Using class variable defined at the class level
                
                # Only log if scale changed by more than 10% from last logged value
                scale_change_threshold = 0.1  # 10% change threshold
                if abs(new_scale - PDFMouseHandler._last_logged_scale) / PDFMouseHandler._last_logged_scale > scale_change_threshold:
                    logger.debug(message_manager.get_log_message("L365", str(new_scale)))
                    PDFMouseHandler._last_logged_scale = new_scale
                
                # Use global transform_throttle imported at the top of the file
                
                if transform_throttle.should_log("transform_update", throttle_key="transform_update"):
                    rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                    logger.debug(message_manager.get_log_message("L368", str(scale), str(tx), str(ty)))
                
                # Update display
                self.parent._on_transform_update()
            elif hasattr(self.parent, 'zoom_in'):
                # Fall back to zoom_in method if available
                self.parent.zoom_in()
        except Exception as e:
            logger.error(message_manager.get_log_message("L312", str(e)))
    
    def on_zoom_out(self, event: Any = None) -> None:
        """Handle zoom out keyboard shortcut.
        
        Args:
            event: Keyboard event (optional)
        """
        try:
            # Apply zoom out directly
            if hasattr(self.parent, 'base_transform_data') and self.parent.current_page_index < len(self.parent.base_transform_data):
                # Get current transformation
                rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                
                # Apply zoom factor to scale (decrease by 10%)
                new_scale = scale * 0.9
                
                # Limit scale to reasonable bounds (0.1 to 10.0)
                new_scale = max(0.1, min(10.0, new_scale))
                
                # Update transformation data
                self.parent.base_transform_data[self.parent.current_page_index] = (rotation, tx, ty, new_scale)
                
                # Store scale factor for use in _display_page
                self.parent.scale_factor = new_scale
                
                # Log zoom out operation
                logger.debug(message_manager.get_log_message("L366", str(new_scale)))
                
                # Log transform update with throttling
                if self._transform_log_throttle.should_log("transform_update"):
                    rotation, tx, ty, scale = self.parent.base_transform_data[self.parent.current_page_index]
                    logger.debug(message_manager.get_log_message("L368", str(scale), str(tx), str(ty)))
                
                # Update display
                self.parent._on_transform_update()
            elif hasattr(self.parent, 'zoom_out'):
                # Fall back to zoom_out method if available
                self.parent.zoom_out()
        except Exception as e:
            logger.error(message_manager.get_log_message("L314", str(e)))
