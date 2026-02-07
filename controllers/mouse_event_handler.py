from __future__ import annotations
import tkinter as tk
import math
import time
from logging import getLogger
from typing import Dict, List, Tuple, Optional, Callable, Union
from configurations.message_manager import get_message_manager
from utils.log_throttle import LogThrottle

logger = getLogger(__name__)
message_manager = get_message_manager()

class MouseEventHandler:
    """Class that handles mouse event operations.
    
    Processes image operations (drag, rotate, zoom), manages keyboard shortcuts,
    and visual feedback. Maintains transformation data for each layer.
    """
    
    def __init__(
            self,
            layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]],
            current_page_index: int,
            visible_layers: Dict[int, bool],
            on_transform_update: Callable[[], None],
        ) -> None:
        """Initialize the MouseEventHandler.

        Args:
            layer_transform_data: List of transformation data for each layer
                Dict[layer_number, List[(rotation, x, y, scale), ...]]
            current_page_index: Current page index
            visible_layers: Layer visibility state Dict[layer_number, visibility_state]
            on_transform_update: Callback after transformation update
        """
        # Transform data and callbacks
        self.__layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]] = layer_transform_data
        self.__current_page_index: int = current_page_index
        self.__visible_layers: Dict[int, bool] = visible_layers
        self.__on_transform_update: Callable[[], None] = on_transform_update

        # Tracking variables
        self.__dragging: bool = False
        self.__last_mouse_x: float = 0.0
        self.__last_mouse_y: float = 0.0
        self.__rotation_mode: bool = False
        self.__rotation_center_x: float = 0.0
        self.__rotation_center_y: float = 0.0
        self.__rotation_start_time: float = 0.0
        self.__rotation_active: bool = False
        
        # Get message manager for localized messages
        self.__msg_mgr = get_message_manager()
        
        # Canvas reference (will be set in attach_to_canvas)
        self.__canvas_ref: Optional[tk.Canvas] = None
        
        # Feedback visual elements
        self.__feedback_circle_id: Optional[Union[int, tuple[int, ...]]] = None
        self.__guidance_text_id: Optional[int] = None
        self.__background_id: Optional[Union[int, tuple[int, ...]]] = None
        self.__notification_text_id: Optional[int] = None
        self.__shortcut_help_id: Optional[Union[int, tuple[int, ...]]] = None
        self.__help_display_id: Optional[int] = None
        self.__help_background_id: Optional[int] = None
        
        # UI state
        self.__shortcut_help_visible: bool = False
        
        # Feedback message state
        self.__current_message: Optional[str] = None
        self.__message_start_time: float = 0.0
        self.__message_duration: float = 1.0  # Display time in seconds
        
        # Message manager (for localized text)
        self.__msg_mgr = message_manager  # Use the global message_manager instance
        
        # Log throttle for mouse wheel events (0.5 second interval)
        self._wheel_log_throttle = LogThrottle(min_interval=0.5)

    def update_state(
            self,
            current_page_index: int,
            visible_layers: Dict[int, bool],
        ) -> None:
        """Update the current state.
        
        Args:
            current_page_index: New current page index
            visible_layers: Layer visibility state Dict[layer_number, visibility_state]
        """
        self.__current_page_index = current_page_index
        self.__visible_layers = visible_layers
        
        # Clear visual feedback when state changes
        self._clear_feedback()
        
    def add_layer(self, layer_id: int, init_transform_data: List[Tuple[float, float, float, float]]) -> None:
        """Add a new layer.
        
        Args:
            layer_id: Layer ID
            init_transform_data: Initial transformation data
        """
        self.__layer_transform_data[layer_id] = init_transform_data
        
    def remove_layer(self, layer_id: int) -> None:
        """Remove a layer.
        
        Args:
            layer_id: ID of the layer to remove
        """
        if layer_id in self.__layer_transform_data:
            del self.__layer_transform_data[layer_id]
        
    def attach_to_canvas(self, canvas_widget: tk.Canvas) -> None:
        """Attach to a canvas for visual feedback.
        
        Args:
            canvas_widget: Canvas to attach to
        """
        self.__canvas_ref = canvas_widget
        
        if canvas_widget is not None:
            # Set up keyboard bindings
            
            # Rotate 90 degrees to the right
            canvas_widget.bind('<Control-r>', self._on_rotate_right)
            canvas_widget.bind('<Control-R>', self._on_rotate_right)
            
            # Rotate 90 degrees to the left
            canvas_widget.bind('<Control-l>', self._on_rotate_left)
            canvas_widget.bind('<Control-L>', self._on_rotate_left)
            
            # Flip vertically
            canvas_widget.bind('<Control-v>', self._on_flip_vertical)
            canvas_widget.bind('<Control-V>', self._on_flip_vertical)
            
            # Flip horizontally
            canvas_widget.bind('<Control-h>', self._on_flip_horizontal)
            canvas_widget.bind('<Control-H>', self._on_flip_horizontal)
            
            # Reset to initial state
            canvas_widget.bind('<Control-b>', self._on_reset_transform)
            canvas_widget.bind('<Control-B>', self._on_reset_transform)
            
            # Toggle shortcut help (Ctrl+? or Ctrl+Shift+H for help)
            canvas_widget.bind('<Control-question>', self._toggle_shortcut_help)
            canvas_widget.bind('<Control-Shift-h>', self._toggle_shortcut_help)
            canvas_widget.bind('<Control-Shift-H>', self._toggle_shortcut_help)
            
            # Allow canvas to receive keyboard events by making it focusable
            canvas_widget.config(takefocus=1)
            
            # Set focus to canvas on click
            canvas_widget.bind('<Button-1>', lambda e: canvas_widget.focus_set())
    
    def on_mouse_down(self, event: tk.Event) -> None:
        """Handle mouse button press.
        
        Args:
            event: Mouse event
        """
        self.__dragging = True
        self.__last_mouse_x = event.x
        self.__last_mouse_y = event.y
        
        # Check for Ctrl key
        state = int(event.state)
        ctrl_pressed = (state & 0x0004) != 0  # Control key bitmask
        
        if ctrl_pressed and self.__canvas_ref:
            # Toggle rotation mode or update rotation center
            if not self.__rotation_mode:
                # Entering rotation mode
                self.__rotation_mode = True
                self.__rotation_center_x = event.x
                self.__rotation_center_y = event.y
                self.__rotation_active = False
                self.__rotation_start_time = time.time()
                self._show_feedback_circle(event.x, event.y)
                self._show_guidance_text(self.__msg_mgr.get_message('M042'))  # M042: Rotation mode - drag to rotate
            else:
                # Already in rotation mode, update center point
                self.__rotation_center_x = event.x
                self.__rotation_center_y = event.y
                self.__rotation_active = False
                self.__rotation_start_time = time.time()
                self._show_feedback_circle(event.x, event.y)
                self._show_guidance_text(self.__msg_mgr.get_message('M042'))  # M042: Rotation mode - drag to rotate

    def on_mouse_drag(self, event: tk.Event) -> None:
        """Handle mouse drag.
        
        Performs different operations based on modifier keys:
        - Regular drag: Move/pan image
        - Ctrl+drag: Rotate image around defined center point
        
        Args:
            event: Mouse event
        """
        if not self.__dragging:
            return

        dx = event.x - self.__last_mouse_x
        dy = event.y - self.__last_mouse_y

        # Cast event.state to int for type safety
        state = int(event.state)
        ctrl_pressed = (state & 0x0004) != 0  # Control key bitmask

        # Check if we're in rotation mode with Ctrl key
        if ctrl_pressed and self.__rotation_mode:
            # Check if we should activate rotation (after brief delay)
            current_time = time.time()
            if not self.__rotation_active and (current_time - self.__rotation_start_time) > 0.05:
                self.__rotation_active = True
                self._show_guidance_text(self.__msg_mgr.get_message('M042'))  # Now rotating
            
            # Only apply rotation if active
            if self.__rotation_active:
                # Calculate angle from center point
                # Get angle between previous point and center
                prev_dx = self.__last_mouse_x - self.__rotation_center_x
                prev_dy = self.__last_mouse_y - self.__rotation_center_y
                prev_angle = math.atan2(prev_dy, prev_dx)
                
                # Get angle between current point and center
                curr_dx = event.x - self.__rotation_center_x
                curr_dy = event.y - self.__rotation_center_y
                curr_angle = math.atan2(curr_dy, curr_dx)
                
                # Calculate angle difference in degrees
                angle_diff = math.degrees(curr_angle - prev_angle)
                
                # Apply to all visible layers
                for layer_id, visible in self.__visible_layers.items():
                    # Check if current page index is within range
                    if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                        r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                        new_r = r + angle_diff
                        # Round to nearest degree for smoother display
                        new_r = round(new_r)
                        self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, x, y, s)
                
                # Update feedback circle to show rotation is active
                self._show_feedback_circle(event.x, event.y, is_rotating=True)
                
                # Always update when rotating
                self.__on_transform_update()
        else:
            # Standard image movement
            # Apply throttling to prevent excessive rendering
            move_threshold = 5  # Threshold for normal movement
            should_update = abs(dx) > move_threshold or abs(dy) > move_threshold
            
            # Process for each layer
            for layer_id, visible in self.__visible_layers.items():
                # Check if current page index is within range
                if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                    r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                    
                    # Movement
                    self.__layer_transform_data[layer_id][self.__current_page_index] = (
                        r,
                        x + dx,
                        y + dy,
                        s,
                    )
            
            # Update display only when necessary
            if should_update:
                self.__on_transform_update()

        # Update last mouse position
        self.__last_mouse_x = event.x
        self.__last_mouse_y = event.y

    def on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release.
        
        Args:
            event: Mouse event
        """
        self.__dragging = False
        
        # Check if Ctrl is still pressed
        state = int(event.state)
        ctrl_pressed = (state & 0x0004) != 0  # Control key bitmask
        
        # Handle rotation mode completion
        if self.__rotation_mode:
            if self.__rotation_active:
                # Extract current rotation angle for the notification
                angle = 0.0  # Initialize as float type
                for layer_id in self.__layer_transform_data:
                    if self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                        r, _, _, _ = self.__layer_transform_data[layer_id][self.__current_page_index]
                        angle = float(r)  # Explicitly convert to float type
                        break
                
                # Update UI with rotation information - round to nearest degree for better readability
                rounded_angle = round(angle)
                self._show_notification(self.__msg_mgr.get_message('M043'))  # M043: Rotation complete
                
                # Keep feedback circle visible briefly before fading out
                if self.__canvas_ref is not None:
                    # Schedule feedback circle to be hidden after 500ms for better visual feedback
                    self.__canvas_ref.after(500, self._hide_feedback_circle)
                    
                    # Also update guidance text to confirm rotation is complete
                    self._show_guidance_text(self.__msg_mgr.get_message('M043'))  # M043: Rotation complete
                    # Schedule guidance text to be hidden after 800ms
                    self.__canvas_ref.after(800, self._hide_guidance_text)
                
                # Reset rotation active state but stay in rotation mode if Ctrl is still pressed
                self.__rotation_active = False
                
            # If Ctrl is no longer pressed, exit rotation mode completely
            if not ctrl_pressed:
                self._hide_feedback_circle()
                self._hide_guidance_text()
                self.__rotation_mode = False
                self.__rotation_active = False

    def _hide_feedback_circle(self) -> None:
        """Hide the feedback circle."""
        if self.__canvas_ref is None:
            return
        
        if self.__feedback_circle_id is not None:
            if isinstance(self.__feedback_circle_id, tuple):
                for circle_id in self.__feedback_circle_id:
                    self.__canvas_ref.delete(circle_id)
            else:
                self.__canvas_ref.delete(self.__feedback_circle_id)
            self.__feedback_circle_id = None
    
    def _hide_guidance_text(self) -> None:
        """Hide the guidance text."""
        if self.__canvas_ref is None:
            return
        
        if self.__guidance_text_id is not None:
            self.__canvas_ref.delete(self.__guidance_text_id)
            self.__guidance_text_id = None
            
        if self.__background_id is not None:
            if isinstance(self.__background_id, tuple):
                for bg_id in self.__background_id:
                    self.__canvas_ref.delete(bg_id)
            else:
                self.__canvas_ref.delete(self.__background_id)
            self.__background_id = None
    
    def on_mouse_wheel(self, event: tk.Event) -> None:
        """Handle mouse wheel for zooming.
        
        Compatible with different platforms:
        - Windows: uses event.delta
        - MacOS/Linux: uses event.num
        
        Args:
            event: Mouse event
        """
        if self.__canvas_ref is None:
            return
        
        # Hide any help or guidance that might be showing
        self._hide_guidance_text()
        
        # Only log mouse wheel events if throttle allows (0.5 second interval)
        should_log = self._wheel_log_throttle.should_log("mouse_wheel_event")
        
        # Determine direction based on platform
        if hasattr(event, 'delta'):  # Windows
            # Windows: event.delta is positive for scroll up, negative for scroll down
            delta = event.delta
            direction = 1 if delta > 0 else -1
        elif hasattr(event, 'num'):  # Linux/Mac
            # Linux/Mac: event.num is 4 for scroll up, 5 for scroll down
            direction = 1 if event.num == 4 else -1 if event.num == (4 + 1) else 0
        else:
            # Unknown platform, no action
            return
        
        # Apply zoom to visible layers
        zoom_factor = 1.1 if direction > 0 else 0.9
        
        # Get canvas center for scaling origin
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        center_x = canvas_width / 2
        center_y = canvas_height / 2
        
        # Apply zoom to all visible layers around canvas center
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                
                # Calculate new scale
                new_scale = s * zoom_factor
                
                # Adjust position to scale from center
                dx = x - center_x
                dy = y - center_y
                new_x = center_x + dx * zoom_factor
                new_y = center_y + dy * zoom_factor
                
                # Update transform data
                self.__layer_transform_data[layer_id][self.__current_page_index] = (r, new_x, new_y, new_scale)
        
        # Update display
        self.__on_transform_update()
        
        # Log zoom operation only if throttle allows (0.5秒間隔)
        if should_log:
            logger.debug(f"{message_manager.get_log_message('L299')} zoom_factor={zoom_factor}")
            
    def _clear_feedback(self) -> None:
        """Clear all visual feedback elements."""
        self._hide_feedback_circle()
        self._hide_guidance_text()
        self._hide_notification()
        self._hide_shortcut_help()
        
    def _show_feedback_circle(self, x: float, y: float, is_rotating: bool = False) -> None:
        """Show a feedback circle at the given position.
        
        Args:
            x: X position
            y: Y position
            is_rotating: Whether we're in rotation mode
        """
        if self.__canvas_ref is None:
            return
            
        # Hide any existing circle
        self._hide_feedback_circle()
        
        # Determine size and colors based on mode - improved visibility
        radius = 25 if is_rotating else 12  # Larger radius for better visibility
        # Always use red for rotation center (Ctrl+Click) and blue for regular feedback
        outer_color = "#ff0000" if is_rotating else "#00aaff"  # Red for rotation center
        inner_color = "#ff5555" if is_rotating else "#55ccff"   # Lighter red for inner circle
        
        # Draw outer circle
        outer_circle = self.__canvas_ref.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline=outer_color, width=2
        )
        
        # Draw inner circle (2/3 size)
        inner_radius = radius * 2/3
        inner_circle = self.__canvas_ref.create_oval(
            x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius,
            fill=inner_color, outline=""
        )
        
        # Store IDs for later removal
        self.__feedback_circle_id = (outer_circle, inner_circle)
        
        # Log feedback creation
        logger.debug(message_manager.get_log_message("L334", f"position=({x},{y}), rotating={is_rotating}"))
        
    def _show_guidance_text(self, message: str) -> None:
        """Show guidance text on the canvas.
        
        Args:
            message: Message to display
        """
        if self.__canvas_ref is None:
            return
            
        # Hide any existing text
        self._hide_guidance_text()
        
        # Get canvas dimensions for centering
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        
        # Create semi-transparent background
        bg = self.__canvas_ref.create_rectangle(
            10, canvas_height - 40, canvas_width - 10, canvas_height - 10,
            fill="#000000", stipple="gray50"
        )
        
        # Determine text color based on content - use red for rotation guidance
        text_color = "#ff0000" if "回転" in message or "rotating" in message.lower() else "#ffffff"
        
        # Create text on top - centered both horizontally and vertically
        text_id = self.__canvas_ref.create_text(
            canvas_width / 2, canvas_height - 25,
            text=message, fill=text_color, font=("Helvetica", 10, "bold"),
            anchor="center", justify="center"
        )
        
        # Store IDs for later removal
        self.__guidance_text_id = text_id
        self.__background_id = bg
        
        # Log guidance text display
        logger.debug(message_manager.get_log_message("L335", message))
        
    def _show_notification(self, message: str, duration: float = 1.5) -> None:
        """Show a transient notification.
        
        Args:
            message: Message to display
            duration: How long to display (seconds)
        """
        if self.__canvas_ref is None:
            return
            
        # Hide any existing notification
        if self.__notification_text_id is not None:
            self.__canvas_ref.delete(self.__notification_text_id)
            
        # Get canvas dimensions for positioning
        canvas_width = self.__canvas_ref.winfo_width()
        
        # Create text
        self.__notification_text_id = self.__canvas_ref.create_text(
            canvas_width / 2, 20,
            text=message, fill="#ffcc00", font=("Helvetica", 12, "bold")
        )
        
        # Set up auto-removal
        self.__canvas_ref.after(int(duration * 1000), self._hide_notification)
        
        # Log notification display
        logger.debug(message_manager.get_log_message("L336", message))
        
    def _hide_notification(self) -> None:
        """Hide the notification text."""
        if self.__canvas_ref is None or self.__notification_text_id is None:
            return
            
        self.__canvas_ref.delete(self.__notification_text_id)
        self.__notification_text_id = None
        
    def _hide_shortcut_help(self) -> None:
        """Hide the shortcut help display."""
        if self.__canvas_ref is None:
            return
            
        if self.__help_display_id is not None:
            self.__canvas_ref.delete(self.__help_display_id)
            self.__help_display_id = None
            
        if self.__help_background_id is not None:
            self.__canvas_ref.delete(self.__help_background_id)
            self.__help_background_id = None
            
        self.__shortcut_help_visible = False
        
    def _on_rotate_right(self, event: tk.Event) -> str | None:
        """Handle Ctrl+R keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        # Rotate visible layers 90 degrees clockwise
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                new_r = r + 90
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, x, y, s)
                
        # Update display
        self.__on_transform_update()
        
        # Show notification
        self._show_notification(self.__msg_mgr.get_message('M044'))  # M044: Rotated right 90°
        
        # Log rotation
        logger.debug(message_manager.get_log_message("L337", "right"))
        
        return "break"  # Prevent default handling
        
    def _on_rotate_left(self, event: tk.Event) -> str | None:
        """Handle Ctrl+L keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        # Rotate visible layers 90 degrees counter-clockwise
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                new_r = r - 90
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, x, y, s)
                
        # Update display
        self.__on_transform_update()
        
        # Show notification
        self._show_notification(self.__msg_mgr.get_message('M045'))  # M045: Rotated left 90°
        
        # Log rotation
        logger.debug(message_manager.get_log_message("L337", "left"))
        
        return "break"  # Prevent default handling
        
    def _on_flip_vertical(self, event: tk.Event) -> str | None:
        """Handle Ctrl+V keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        # Flip visible layers vertically (180° rotation)
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                new_r = r + 180
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, x, y, s)
                
        # Update display
        self.__on_transform_update()
        
        # Show notification
        self._show_notification(self.__msg_mgr.get_message('M046'))  # M046: Flipped vertically
        
        # Log flip
        logger.debug(message_manager.get_log_message("L338", "vertical"))
        
        return "break"  # Prevent default handling
        
    def _on_flip_horizontal(self, event: tk.Event) -> str | None:
        """Handle Ctrl+H keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        # Flip visible layers horizontally (horizontal mirror)
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                new_r = r + 180  # Technically this is a vertical flip + 180° rotation
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, x, y, s)
                
        # Update display
        self.__on_transform_update()
        
        # Show notification
        self._show_notification(self.__msg_mgr.get_message('M047'))  # M047: Flipped horizontally
        
        # Log flip
        logger.debug(message_manager.get_log_message("L338", "horizontal"))
        
        return "break"  # Prevent default handling
        
    def _on_reset_transform(self, event: tk.Event) -> str | None:
        """Handle Ctrl+B keyboard shortcut to reset transformation.
        
        Args:
            event: Keyboard event
        """
        # Reset all transforms to identity
        for layer_id, visible in self.__visible_layers.items():
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                self.__layer_transform_data[layer_id][self.__current_page_index] = (0.0, 0.0, 0.0, 1.0)  # Identity transform
                
        # Update display
        self.__on_transform_update()
        
        # Show notification
        self._show_notification(self.__msg_mgr.get_message('M048'))  # M048: Reset to original
        
        # Log reset
        logger.debug(message_manager.get_log_message("L339", "reset_transform"))
        
        return "break"  # Prevent default handling
        
    def _toggle_shortcut_help(self, event: tk.Event) -> str | None:
        """Handle Ctrl+? keyboard shortcut to show/hide keyboard shortcuts.
        
        Args:
            event: Keyboard event
        """
        if self.__canvas_ref is None:
            return "break"
            
        if self.__shortcut_help_visible:
            # Hide help
            self._hide_shortcut_help()
            logger.debug(message_manager.get_log_message("L340", "hide_help"))
        else:
            # Show help
            self._show_shortcut_help()
            logger.debug(message_manager.get_log_message("L340", "show_help"))
            
        return "break"  # Prevent default handling
        
    def _show_shortcut_help(self) -> None:
        """Show the keyboard shortcut help overlay."""
        if self.__canvas_ref is None:
            return
            
        # First hide if already displayed
        self._hide_shortcut_help()
        
        # Get canvas dimensions for positioning
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        
        # Create more opaque background with border for better visibility
        self.__help_background_id = self.__canvas_ref.create_rectangle(
            50, 50, canvas_width - 50, canvas_height - 50,
            fill="#000000", stipple="gray25", outline="#ffffff", width=2
        )
        
        # Create help text with high contrast color
        help_text = self.__msg_mgr.get_message('M049')  # M049: Keyboard Shortcuts (help overlay)
        self.__help_display_id = self.__canvas_ref.create_text(
            canvas_width / 2, canvas_height / 2,
            text=help_text, fill="#ffff00", font=("Helvetica", 12, "bold"), justify=tk.CENTER
        )
        
        self.__shortcut_help_visible = True
