import tkinter as tk
import time
import math
from logging import getLogger
from typing import Dict, List, Tuple, Union, Optional, Callable, TYPE_CHECKING

# Type checking imports
if TYPE_CHECKING:
    pass  # Add any type-only imports here when needed
from configurations.message_manager import get_message_manager
from configurations.tool_settings import font_family, font_size
from utils.log_throttle import LogThrottle

logger = getLogger(__name__)
message_manager = get_message_manager()

# Create a log throttle for zoom scale logging with 0.5 second interval
zoom_log_throttle = LogThrottle(min_interval=0.5)

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
        
        # Timer tracking
        self._hide_after_ids: List[Optional[str]] = []
        
        # Rotation parameters
        self.__rotation_mode: bool = False
        self.__rotation_center_x: float = 0.0
        self.__rotation_center_y: float = 0.0
        self.__rotation_start_time: float = 0.0
        self.__rotation_active: bool = False
        
        # Flag to track if shortcut guide was toggled by user
        self.__user_toggled_shortcut_guide: bool = False
        
        # Shortcut guide item IDs
        self.__shortcut_guide_id: Optional[Tuple[int, int]] = None
        
        # Get message manager for localized messages
        self.__msg_mgr = get_message_manager()
        
        # Canvas reference (will be set in attach_to_canvas)
        self.__canvas_ref: Optional[tk.Canvas] = None
        
        # Feedback visual elements with improved type annotations
        self.__feedback_circle_id: Optional[Union[int, str]] = None
        # Type annotation for guidance text ID that can be None, int, str, or tuple of int/str
        self.__guidance_text_id: Optional[Union[int, str, Tuple[int, int], Tuple[str, str]]] = None
        self.__background_id: Optional[Union[int, str]] = None
        # Type annotation for notification text ID that can be None, int, str, or tuple of int/str
        self.__notification_text_id: Optional[Union[int, str, Tuple[int, int], Tuple[str, str]]] = None
        self.__help_display_id: Optional[int] = None
        self.__help_background_id: Optional[int] = None
        
        # UI state
        self.__shortcut_guide_visible: bool = False
        self.__guidance_text_visible: bool = False
        self.__notification_visible: bool = False
        
        # Flag to keep rotation elements visible even after Ctrl release
        # This ensures visual elements remain visible after rotation operations
        self.__keep_rotation_elements_visible: bool = False
        
        # Feedback message state
        self.__current_message: Optional[str] = None
        self.__message_start_time: float = 0.0
        self.__message_duration: float = 0.5  # Display time in seconds
        
        # Ctrl key check timer
        self.__ctrl_check_timer_id: Optional[str] = None
        self.__ctrl_check_interval: int = 100  # Check every 100ms
        
        # Message manager (for localized text)
        self.__msg_mgr = message_manager  # Use the global message_manager instance
        
        # Log throttles for various events
        self._wheel_log_throttle = LogThrottle(min_interval=0.5)
        self._transform_log_throttle = LogThrottle(min_interval=0.5)
        
        # List to store after IDs for cancellation is already defined at line 55

    def on_rotate_right(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+R keyboard shortcut for 90-degree clockwise rotation.
        
        Args:
            event: Keyboard event (optional)
            
        Returns:
            String to prevent default handling or None
        """
        # Check if Ctrl key is pressed
        ctrl_pressed = False
        if event and hasattr(event, 'state'):
            # Ensure state is an integer before performing bitwise operation
            if isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
        
        # Save rotation mode state
        was_in_rotation_mode = self.__rotation_mode
        was_rotation_active = self.__rotation_active
        rotation_center_x = self.__rotation_center_x
        rotation_center_y = self.__rotation_center_y
        
        # Set default rotation center if not already set
        if not was_in_rotation_mode:
            # Use canvas center as default rotation center
            if self.__canvas_ref:
                canvas_width = self.__canvas_ref.winfo_width()
                canvas_height = self.__canvas_ref.winfo_height()
                self.__rotation_center_x = canvas_width / 2
                self.__rotation_center_y = canvas_height / 2
                
                # Temporarily activate rotation mode to show feedback
                self.__rotation_mode = True
                self.__rotation_active = False
                self.__rotation_start_time = time.time()
                
                # Show rotation center immediately
                self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation mode
        
        # Rotate visible layers 90 degrees clockwise
        self.__rotate_by_angle(90)
                
        # Update display
        self.__on_transform_update()
        
        # Show notification with warning style
        self.show_notification(self.__msg_mgr.get_message('M044'), 0.5, warning=True)  # Rotated 90° right
        
        # Restore rotation mode state if it was active or Ctrl is pressed
        if was_in_rotation_mode or ctrl_pressed:
            self.__rotation_mode = True
            self.__rotation_active = was_rotation_active  # Preserve active state
            self.__rotation_center_x = rotation_center_x if rotation_center_x is not None else self.__rotation_center_x
            self.__rotation_center_y = rotation_center_y if rotation_center_y is not None else self.__rotation_center_y
            
            # Only show feedback and guidance if in rotation mode or Ctrl is pressed
            if self.__rotation_mode or ctrl_pressed:
                self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
        else:
            # If we weren't in rotation mode before and Ctrl is not pressed, exit it after the rotation
            self.__rotation_mode = False
            self.__rotation_active = False
            
            # Hide the feedback after a short delay
            if self.__canvas_ref:
                # Use longer delay (2000ms) for better visibility after rotation
                # Store the after_id for later cancellation
                aid1 = self.__canvas_ref.after(2000, self.hide_feedback_circle)
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after IDs to the list for possible cancellation
                self._hide_after_ids.append(aid1)
                self._hide_after_ids.append(aid2)
        
        # Log rotation with proper multilingual message
        logger.debug(self.__msg_mgr.get_message("L415"))
        
        return "break"  # Prevent default handling
        
    def on_rotate_left(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+L keyboard shortcut for 90-degree counterclockwise rotation.
        
        Args:
            event: Keyboard event (optional)
            
        Returns:
            String to prevent default handling or None
        """
        # Check if Ctrl key is pressed
        ctrl_pressed = False
        if event and hasattr(event, 'state'):
            # Ensure state is an integer before performing bitwise operation
            if isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
        
        # Save rotation mode state
        was_in_rotation_mode = self.__rotation_mode
        was_rotation_active = self.__rotation_active
        rotation_center_x = self.__rotation_center_x
        rotation_center_y = self.__rotation_center_y
        
        # Set default rotation center if not already set
        if not was_in_rotation_mode:
            # Use canvas center as default rotation center
            if self.__canvas_ref:
                canvas_width = self.__canvas_ref.winfo_width()
                canvas_height = self.__canvas_ref.winfo_height()
                self.__rotation_center_x = canvas_width / 2
                self.__rotation_center_y = canvas_height / 2
                
                # Temporarily activate rotation mode to show feedback
                self.__rotation_mode = True
                self.__rotation_active = False
                self.__rotation_start_time = time.time()
                
                # Show rotation center immediately
                self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation mode
        
        # Rotate visible layers 90 degrees counterclockwise
        self.__rotate_by_angle(-90)
                
        # Update display
        self.__on_transform_update()
        
        # Show notification with warning style
        self.show_notification(self.__msg_mgr.get_message('M045'), 0.5, warning=True)  # Rotated 90° left
        
        # Restore rotation mode state if it was active or Ctrl is pressed
        if was_in_rotation_mode or ctrl_pressed:
            self.__rotation_mode = True
            self.__rotation_active = was_rotation_active  # Preserve active state
            self.__rotation_center_x = rotation_center_x if rotation_center_x is not None else self.__rotation_center_x
            self.__rotation_center_y = rotation_center_y if rotation_center_y is not None else self.__rotation_center_y
            
            # Only show feedback and guidance if in rotation mode or Ctrl is pressed
            if self.__rotation_mode or ctrl_pressed:
                self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
        else:
            # If we weren't in rotation mode before and Ctrl is not pressed, exit it after the rotation
            self.__rotation_mode = False
            self.__rotation_active = False
            
            # Hide the feedback after a short delay
            if self.__canvas_ref:
                # Use longer delay (2000ms) for better visibility after rotation
                # Store the after_id for later cancellation
                aid1 = self.__canvas_ref.after(2000, self.hide_feedback_circle)
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after IDs to the list for possible cancellation
                self._hide_after_ids.append(aid1)
                self._hide_after_ids.append(aid2)
        
        # Log rotation with proper multilingual message
        logger.debug(self.__msg_mgr.get_message("L416"))
        
        return "break"  # Prevent default handling
        
    def on_flip_vertical(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+V keyboard shortcut for vertical flip.
        
        Args:
            event: Keyboard event (optional)
        """
        # Check if Ctrl key is pressed
        ctrl_pressed = False
        if event and hasattr(event, 'state'):
            # Ensure state is an integer before performing bitwise operation
            if isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
        
        # Save rotation mode state
        was_in_rotation_mode = self.__rotation_mode
        
        # Clear existing UI elements to prevent duplication
        if self.__canvas_ref:
            # Clear any existing feedback circles and guidance text
            self.hide_feedback_circle()
            self.hide_guidance_text()
            self.hide_notification()
        
        # Log the vertical flip operation
        logger.debug(self.__msg_mgr.get_message("L418"))
        
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                
                # Vertical flip: Invert the Y-scale by changing sign
                # Keep the same rotation angle and X-position
                self.__layer_transform_data[layer_id][self.__current_page_index] = (r, x, y, -s)
        
        # Update display
        self.__on_transform_update()
        
        # Show notification with warning style
        self.show_notification(self.__msg_mgr.get_message('M046'), 0.5, warning=True)  # Flipped vertically
        
        # Show feedback and handle rotation mode
        if self.__canvas_ref:
            canvas_width = self.__canvas_ref.winfo_width()
            canvas_height = self.__canvas_ref.winfo_height()
            
            # If in rotation mode or Ctrl is pressed, maintain rotation mode
            if was_in_rotation_mode or ctrl_pressed:
                self.__rotation_mode = True
                # Show center point immediately and keep it visible
                self.show_feedback_circle(canvas_width/2, canvas_height/2, is_rotating=True)
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
            else:
                # Show center point briefly and hide after delay
                self.show_feedback_circle(canvas_width/2, canvas_height/2, is_rotating=True)
                # Use longer delay (2000ms) for better visibility after rotation
                # Store the after_id for later cancellation
                aid1 = self.__canvas_ref.after(2000, self.hide_feedback_circle)
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after IDs to the list for possible cancellation
                self._hide_after_ids.append(aid1)
                self._hide_after_ids.append(aid2)
        
        return "break"  # Prevent default handling
        
    def on_flip_horizontal(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+H keyboard shortcut for horizontal flip.
        
        Args:
            event: Keyboard event (optional)
        """
        # Check if Ctrl key is pressed
        ctrl_pressed = False
        if event and hasattr(event, 'state'):
            # Ensure state is an integer before performing bitwise operation
            if isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
        
        # Save rotation mode state
        was_in_rotation_mode = self.__rotation_mode
        
        # Clear existing UI elements to prevent duplication
        if self.__canvas_ref:
            # Clear any existing feedback circles and guidance text
            self.hide_feedback_circle()
            self.hide_guidance_text()
            self.hide_notification()
        
        # Log the horizontal flip operation
        logger.debug(self.__msg_mgr.get_message("L419"))
        
        # Apply horizontal flip to all visible layers
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                
                # Horizontal flip: Apply 180 degree rotation
                # This effectively flips the image horizontally
                self.__layer_transform_data[layer_id][self.__current_page_index] = (r + 180, x, y, s)
        
        # Update display
        self.__on_transform_update()
        
        # Show notification with warning style
        self.show_notification(self.__msg_mgr.get_message('M047'), 0.5, warning=True)  # Flipped horizontally
        
        # Show feedback and handle rotation mode
        if self.__canvas_ref:
            canvas_width = self.__canvas_ref.winfo_width()
            canvas_height = self.__canvas_ref.winfo_height()
            
            # If in rotation mode or Ctrl is pressed, maintain rotation mode
            if was_in_rotation_mode or ctrl_pressed:
                self.__rotation_mode = True
                # Show center point immediately and keep it visible
                self.show_feedback_circle(canvas_width/2, canvas_height/2, is_rotating=True)
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
            else:
                # Show center point briefly and hide after delay
                self.show_feedback_circle(canvas_width/2, canvas_height/2, is_rotating=True)
                # Use longer delay (2000ms) for better visibility after rotation
                # Store the after_id for later cancellation
                aid1 = self.__canvas_ref.after(2000, self.hide_feedback_circle)
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after IDs to the list for possible cancellation
                self._hide_after_ids.append(aid1)
                self._hide_after_ids.append(aid2)
        
        return "break"  # Prevent default handling
        
    def show_feedback_circle(self, x: float, y: float, is_rotating: bool = False) -> None:
        """Show a feedback circle at the specified coordinates.
        
        Args:
            x: X-coordinate for the feedback circle
            y: Y-coordinate for the feedback circle
            is_rotating: Whether the circle is for rotation feedback
        """
        # Cancel any existing hide timers before showing new feedback
        self.__cancel_all_timers()
        
        # Clear any existing feedback circle
        self.hide_feedback_circle()
        
        # Store the rotation center coordinates to prevent them from changing
        if is_rotating:
            self.__rotation_center_x = x
            self.__rotation_center_y = y
        
        if self.__canvas_ref:
            # Create a background circle for better visibility
            # Smaller background for less visual interference
            background_radius = 10
            background_color = "#FFFFFF" if is_rotating else "#555555"
            
            # Create the background circle with transparency
            self.__background_id = self.__canvas_ref.create_oval(
                x - background_radius, y - background_radius,
                x + background_radius, y + background_radius,
                fill=background_color, outline="", stipple="gray50"
            )
            
            # Create the main feedback circle
            # Smaller circle for more precise indication
            circle_radius = 4
            # Use red color for rotation mode as requested
            circle_color = "#FF0000" if is_rotating else "#FFFFFF"
            self.__feedback_circle_id = self.__canvas_ref.create_oval(
                x - circle_radius, y - circle_radius,
                x + circle_radius, y + circle_radius,
                fill=circle_color, outline="#000000", width=1
            )
            
            # Store the center point coordinates for rotation
            self.__rotation_center_x = x
            self.__rotation_center_y = y
            
            # Log the creation of the feedback circle
            logger.debug(self.__msg_mgr.get_message("L504").format(x, y, is_rotating))
    
    def hide_feedback_circle(self) -> None:
        """Hide the feedback circle if it exists."""
        # Remove the feedback circle from the canvas
        if self.__canvas_ref:
            if self.__feedback_circle_id is not None:
                try:
                    self.__canvas_ref.delete(self.__feedback_circle_id)
                    self.__feedback_circle_id = None
                except Exception as e:
                    # Log error when deleting feedback circle
                    logger.error(self.__msg_mgr.get_message("L505").format(str(e)))
            
            if self.__background_id is not None:
                try:
                    self.__canvas_ref.delete(self.__background_id)
                    self.__background_id = None
                except Exception as e:
                    # Log error when deleting background
                    logger.error(self.__msg_mgr.get_message("L506").format(str(e)))
    
    def __cancel_all_timers(self) -> None:
        """Cancel all pending after callbacks to prevent overlapping timers."""
        if self.__canvas_ref:
            for after_id in self._hide_after_ids:
                try:
                    # Convert to string for type compatibility with tkinter
                    after_id_str = str(after_id) if after_id is not None else ""
                    self.__canvas_ref.after_cancel(after_id_str)
                except Exception:
                    pass  # Ignore if already cancelled
            
            # Clear the list
            self._hide_after_ids.clear()
    
    def show_guidance_text(self, message: str, is_rotation: bool = False) -> None:
        """Show guidance text at the bottom left of the canvas.
        
        Args:
            message: The message to display
            is_rotation: Whether the guidance is for rotation mode
        """
        # Cancel any existing hide timers before showing new guidance
        self.__cancel_all_timers()
        
        # Clear any existing guidance text
        self.hide_guidance_text()
        
        if self.__canvas_ref and message:
            try:
                # Set the current message and mark as visible
                self.__current_message = message
                self.__guidance_text_visible = True
                
                # Position at the bottom left of the canvas as requested
                canvas_height = self.__canvas_ref.winfo_height()
                
                # Use smaller font size for less intrusive display
                guidance_font_size = font_size - 2
                
                # Position in the bottom left corner with some padding
                text_x = 20
                text_y = canvas_height - 20
                
                # Create text with background for better visibility
                # Use red for rotation mode as requested
                background_color = "#FFFFFF" if is_rotation else "#555555"
                text_color = "#FF0000" if is_rotation else "#FFFFFF"
                
                # Create the main guidance text first at temporary position (0,0) to measure its size
                text_id = self.__canvas_ref.create_text(
                    0, 0,
                    text=message,
                    fill=text_color,
                    font=(font_family, guidance_font_size, "bold"),
                    anchor="nw"  # Northwest anchor for left alignment
                )
                
                # Get the actual text dimensions after drawing
                x1, y1, x2, y2 = self.__canvas_ref.bbox(text_id)
                text_width = x2 - x1
                text_height = y2 - y1
                
                # Move text to the correct position
                self.__canvas_ref.coords(text_id, text_x, text_y - 5)
                
                # Create text background with red border for rotation mode based on actual text size
                text_bg = self.__canvas_ref.create_rectangle(
                    text_x - 6, text_y - 5 - 2, 
                    text_x + text_width + 6, text_y - 5 + text_height + 2,
                    fill=background_color, 
                    outline="#FF0000" if is_rotation else "", 
                    width=2 if is_rotation else 0
                )
                
                # Raise text above background to ensure visibility
                self.__canvas_ref.tag_raise(text_id, text_bg)
                
                # Store IDs as a tuple
                self.__guidance_text_id = (text_bg, text_id)
                self.__guidance_text_visible = True
                
                # Log guidance text display
                logger.debug(self.__msg_mgr.get_message("L510").format(message))
            except Exception as e:
                # Log error when creating guidance text
                logger.error(self.__msg_mgr.get_message("L521").format(str(e)))
    
    def hide_guidance_text(self) -> None:
        """Hide the guidance text if it exists."""
        if self.__canvas_ref and self.__guidance_text_id is not None:
            try:
                # Check if guidance_text_id is a tuple before unpacking
                if isinstance(self.__guidance_text_id, tuple) and len(self.__guidance_text_id) == 2:
                    bg_id, text_id = self.__guidance_text_id
                else:
                    # If not a tuple, handle as a single ID
                    bg_id = self.__guidance_text_id
                    text_id = None
                
                # Delete both background and text
                self.__canvas_ref.delete(bg_id)
                if text_id is not None: self.__canvas_ref.delete(text_id)
                
                # Reset tracking variables
                self.__guidance_text_id = None
                self.__guidance_text_visible = False
                
                # Log guidance text hiding
                logger.debug(self.__msg_mgr.get_message("L511"))
            except Exception as e:
                # Log error when hiding guidance text
                logger.error(self.__msg_mgr.get_message("L522").format(str(e)))
    
    def hide_notification(self) -> None:
        """Hide the notification if it exists."""
        if self.__canvas_ref and self.__notification_text_id is not None:
            try:
                # Check if notification_text_id is a tuple before unpacking
                if isinstance(self.__notification_text_id, tuple) and len(self.__notification_text_id) == 2:
                    bg_id, text_id = self.__notification_text_id
                else:
                    # If not a tuple, handle as a single ID
                    bg_id = self.__notification_text_id
                    text_id = None
                
                # Delete both background and text
                self.__canvas_ref.delete(bg_id)
                if text_id is not None: self.__canvas_ref.delete(text_id)
                
                # Reset tracking variables
                self.__notification_text_id = None
                self.__notification_visible = False
                
                # Log notification hiding
                logger.debug(self.__msg_mgr.get_message("L511"))
            except Exception as e:
                # Log error when hiding notification
                logger.error(self.__msg_mgr.get_message("L522").format(str(e)))
    
    def cleanup(self) -> None:
        """This method should be called when the application is closing
        to ensure all timers are cancelled and resources are released.
        """
        # Cancel all pending after callbacks
        if self.__canvas_ref:
            for after_id in self._hide_after_ids:
                try:
                    # Convert to string for type compatibility with tkinter
                    after_id_str = str(after_id) if after_id is not None else ""
                    self.__canvas_ref.after_cancel(after_id_str)
                except Exception:
                    pass  # Ignore if already cancelled
            
            # Clear the list
            self._hide_after_ids.clear()
            
            # Hide any visible UI elements
            self.hide_feedback_circle()
            self.hide_guidance_text()
            self.hide_notification()
            self.__hide_shortcut_guide()
            
            # Reset rotation mode
            if self.__rotation_mode:
                self.__exit_rotation_mode()
        
        # Log cleanup
        logger.debug(self.__msg_mgr.get_message("L517"))
        

    
    def __show_shortcut_guide(self, message: str) -> None:
        """Show shortcut guide in the top-right corner of the canvas.
        
        Args:
            message: The shortcut guide message to display
        """
        if self.__canvas_ref and message:
            try:
                # Hide any existing shortcut guide
                self.__hide_shortcut_guide()
                
                # Call update_idletasks to ensure canvas dimensions are up-to-date
                # This is needed when Canvas size is 1x1 at initial call
                try:
                    self.__canvas_ref.update_idletasks()
                except Exception as e:
                    # Log error but continue with best effort
                    logger.debug(self.__msg_mgr.get_message("L526").format(str(e)))
                
                # Position at the top right of the canvas
                canvas_width = self.__canvas_ref.winfo_width()
                
                # Ensure we have a reasonable canvas width
                # If canvas is not yet properly sized, use a default value
                if canvas_width <= 1:
                    canvas_width = 800  # Default fallback width
                    logger.debug(self.__msg_mgr.get_message("L527").format(canvas_width))
                
                text_x = canvas_width - 20
                text_y = 20
                
                # Create text with background for better visibility
                guide_font_size = font_size - 2
                
                # Create the text first at temporary position to measure its size
                text_id = self.__canvas_ref.create_text(
                    0, 0,
                    text=message,
                    fill="#FFFFFF",
                    font=(font_family, guide_font_size),
                    anchor="ne"  # Northeast anchor for right alignment
                )
                
                # Get the actual text dimensions
                x1, y1, x2, y2 = self.__canvas_ref.bbox(text_id)
                text_width = x2 - x1
                text_height = y2 - y1
                
                # Move text to the correct position
                self.__canvas_ref.coords(text_id, text_x, text_y)
                
                # Create background with padding
                bg_id = self.__canvas_ref.create_rectangle(
                    text_x - text_width - 10, text_y - 5,
                    text_x + 5, text_y + text_height + 5,
                    fill="#333333",
                    outline="#555555",
                    width=1
                )
                
                # Raise text above background
                self.__canvas_ref.tag_raise(text_id, bg_id)
                
                # Store IDs and mark as visible
                self.__shortcut_guide_id = (bg_id, text_id)
                self.__shortcut_guide_visible = True
                
                # Log shortcut guide display
                logger.debug(self.__msg_mgr.get_message("L513").format(message))
            except Exception as e:
                # Log error when creating shortcut guide
                logger.error(self.__msg_mgr.get_message("L523").format(str(e)))
    
    def __hide_shortcut_guide(self) -> None:
        """Hide the shortcut guide if it exists."""
        if self.__canvas_ref and self.__shortcut_guide_id is not None:
            try:
                # Unpack the tuple of canvas item IDs
                bg_id, text_id = self.__shortcut_guide_id
                
                # Delete both background and text
                self.__canvas_ref.delete(bg_id)
                if text_id is not None: self.__canvas_ref.delete(text_id)
                
                # Reset tracking variables
                self.__shortcut_guide_id = None
                self.__shortcut_guide_visible = False
                
                # Log shortcut guide hiding
                logger.debug(self.__msg_mgr.get_message("L514"))
            except Exception as e:
                # Log error when hiding shortcut guide
                logger.error(self.__msg_mgr.get_message("L524").format(str(e)))
                
    def __exit_rotation_mode(self, event: Optional[tk.Event] = None) -> None:
        """Exit rotation mode and clean up all related UI elements.
        
        This method resets all rotation-related flags and hides UI feedback elements.
        It should be called when rotation mode is exited (Ctrl key released or page changed).
        """
        try:
            # First cancel all timers to prevent UI elements from reappearing
            self.__cancel_all_timers()
            
            # Reset rotation mode flags
            self.__rotation_mode = False
            self.__rotation_active = False
            
            # Hide all rotation-related UI elements
            self.hide_feedback_circle()
            self.hide_guidance_text()
            
            # Keep shortcut guide visible if it was explicitly toggled by the user
            # Otherwise hide it if it was only shown as part of rotation mode
            if not self.__user_toggled_shortcut_guide and self.__shortcut_guide_visible:
                self.__hide_shortcut_guide()
            
            # Log exit from rotation mode
            logger.debug(self.__msg_mgr.get_message("L516"))
        except Exception as e:
            # Log error when exiting rotation mode
            logger.error(self.__msg_mgr.get_message("L525").format(str(e)))
                
    def toggle_shortcut_guide(self, event: Optional[tk.Event] = None) -> str:
        """Toggle the display of keyboard shortcut guide.
        
        This function can be called from any mode to show or hide the shortcut guide.
        
        Args:
            event: The event that triggered this action (optional)
            
        Returns:
            str: 'break' to prevent default event handling
        """
        try:
            # Mark this as a user-initiated toggle
            self.__user_toggled_shortcut_guide = True
            
            # Toggle the shortcut guide visibility
            if self.__shortcut_guide_visible:
                # Hide the shortcut guide if it's currently visible
                self.__hide_shortcut_guide()
                logger.debug(self.__msg_mgr.get_message("L514"))
            else:
                # Show the shortcut guide if it's currently hidden
                shortcut_guide = self.__msg_mgr.get_message('M049')
                self.__show_shortcut_guide(shortcut_guide)
                logger.debug(self.__msg_mgr.get_message("L513").format("Shortcut guide toggled"))
            
            return "break"  # Prevent default event handling
        except Exception as e:
            # Log error when toggling shortcut guide
            logger.error(self.__msg_mgr.get_message("L524").format(str(e)))
            return "break"
    
    def show_notification(self, message: str, duration: float = 0.5, warning: bool = False) -> None:
        """Show a temporary notification message on the canvas.
        
        Args:
            message: The notification message to display
            duration: How long to display the message (in seconds)
            warning: Whether to show as a warning (red text on white background)
        """
        # Cancel any existing hide timers before showing new notification
        self.__cancel_all_timers()
        
        # Clear any existing notification
        self.hide_notification()
        
        if self.__canvas_ref and message:
            try:
                # Position at the top center of the canvas
                canvas_width = self.__canvas_ref.winfo_width()
                text_x = canvas_width / 2
                text_y = 30
                
                # Set colors based on warning mode
                if warning:
                    bg, txt, border = "#FFFFFF", "#FF0000", "#FF0000"
                else:
                    bg, txt, border = "#333333", "#FFFFFF", "#555555"
                
                # Create notification with background
                notification_font_size = font_size - 1
                
                # Create the text first to measure its size
                text_id = self.__canvas_ref.create_text(
                    text_x, text_y,
                    text=message,
                    fill=txt,
                    font=(font_family, notification_font_size, "bold"),
                    anchor="n"  # North anchor for center alignment
                )
                
                # Get the actual text dimensions
                x1, y1, x2, y2 = self.__canvas_ref.bbox(text_id)
                text_width = x2 - x1
                text_height = y2 - y1
                
                # Create background with padding
                bg_id = self.__canvas_ref.create_rectangle(
                    text_x - text_width/2 - 10, text_y - 5,
                    text_x + text_width/2 + 10, text_y + text_height + 5,
                    fill=bg,
                    outline=border,
                    width=1
                )
                
                # Raise text above background
                self.__canvas_ref.tag_raise(text_id, bg_id)
                
                # Store IDs
                self.__notification_text_id = (bg_id, text_id)
                self.__notification_visible = True
                
                # Set auto-hide timer
                hide_ms = int(duration * 1000)  # Convert seconds to milliseconds
                after_id = self.__canvas_ref.after(hide_ms, self.hide_notification)
                # Add after ID to the list for possible cancellation
                self._hide_after_ids.append(after_id)
                
                # Log notification
                logger.debug(self.__msg_mgr.get_message("L509").format(message, duration))
            except Exception as e:
                # Log error when creating notification
                logger.error(self.__msg_mgr.get_message("L520").format(str(e)))
    
    def on_mouse_down(self, event: tk.Event) -> str:
        """Handle mouse button press event.
        
        Args:
            event: Mouse button press event
            
        Returns:
            String to prevent default handling
        """
        # Set dragging flag and store initial position
        self.__dragging = True
        
        # Use canvas coordinates to account for scrolling
        # Ensure canvas reference is not None before calling methods
        if self.__canvas_ref is not None:
            self.__last_mouse_x = self.__canvas_ref.canvasx(event.x)
            self.__last_mouse_y = self.__canvas_ref.canvasy(event.y)
        
        # Check if Ctrl key is pressed for rotation mode
        ctrl_pressed = False
        if hasattr(event, 'state'):
            # Ensure state is an integer before performing bitwise operation
            if isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
        
        # If Ctrl key is pressed, enter rotation mode
        if ctrl_pressed:
            # Only set a new rotation center if we're not already in rotation mode
            # This prevents the center from changing when clicking again while in rotation mode
            if not self.__rotation_mode:
                self.__rotation_mode = True
                self.__rotation_active = False
                
                # Set rotation center to the clicked point using canvas coordinates
                # Ensure canvas reference is not None before calling methods
                if self.__canvas_ref is not None:
                    self.__rotation_center_x = self.__canvas_ref.canvasx(event.x)
                    self.__rotation_center_y = self.__canvas_ref.canvasy(event.y)
                
                # Show visual feedback for rotation center point
                self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                # Show rotation guidance with shortcuts
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
                
                # Show shortcut guide in the top-right corner if not already visible
                if not self.__shortcut_guide_visible:
                    # Mark this as system-initiated (not user-toggled)
                    self.__user_toggled_shortcut_guide = False
                    # Show the shortcut guide
                    self.__show_shortcut_guide(self.__msg_mgr.get_message('M049'))
        
        # Log mouse down event
        logger.debug(self.__msg_mgr.get_message("L512").format(event.x, event.y))
        
        return "break"  # Prevent default handling

    def on_mouse_drag(self, event: tk.Event) -> None:
        """Handle mouse drag event.

        Args:
            event: Mouse drag event
        """
        # Only process if dragging flag is set
        if not self.__dragging:
            return

        # Calculate the movement delta using canvas coordinates
        # Ensure canvas reference is not None before calling methods
        if self.__canvas_ref is None:
            return
            
        current_x = self.__canvas_ref.canvasx(event.x)
        current_y = self.__canvas_ref.canvasy(event.y)
        delta_x = current_x - self.__last_mouse_x
        delta_y = current_y - self.__last_mouse_y

        # Check if in rotation mode
        if self.__rotation_mode:
            # If rotation has not been activated yet, check if we've moved enough to start
            if not self.__rotation_active:
                # Calculate distance from initial press point
                distance = ((current_x - self.__rotation_center_x) ** 2 + 
                            (current_y - self.__rotation_center_y) ** 2) ** 0.5
                
                # If moved enough distance, activate rotation
                if distance > 10:  # 10 pixels threshold
                    self.__rotation_active = True
                    # Store initial angle for reference
                    self.__rotation_start_angle = math.atan2(current_y - self.__rotation_center_y,
                                                            current_x - self.__rotation_center_x)
            
            # If rotation is active, calculate angle and rotate
            if self.__rotation_active:
                # Calculate angle from center to current position
                current_angle = math.atan2(current_y - self.__rotation_center_y,
                                          current_x - self.__rotation_center_x)
                
                # Calculate angle from center to previous position
                prev_angle = math.atan2(self.__last_mouse_y - self.__rotation_center_y,
                                       self.__last_mouse_x - self.__rotation_center_x)
                
                # Calculate angle difference in degrees
                angle_diff = math.degrees(current_angle - prev_angle)
                
                # Apply smoothing to prevent jitter
                if abs(angle_diff) > 0.05:  # Even lower threshold to catch smaller movements (was 0.1)
                    # Limit angle change per frame to reduce jerkiness
                    if abs(angle_diff) > 0.5:  # Limit to 0.5 degrees per frame
                        angle_diff = 0.5 if angle_diff > 0 else -0.5
                    elif abs(angle_diff) > 0.3:
                        # Apply scaling for medium changes
                        angle_diff = 0.3 if angle_diff > 0 else -0.3
                    
                    # Apply additional smoothing for very small changes
                    if abs(angle_diff) < 0.2:
                        # Apply a stronger scaling factor to make small movements even smoother
                        angle_diff *= 0.5
                    
                    # Apply rotation
                    self.__rotate_by_angle(angle_diff)
                    
                    # Calculate total rotation from start for display
                    total_angle_change = math.degrees(current_angle - self.__rotation_start_angle)
                    total_angle_change = round(total_angle_change, 1)  # Round for display
                    
                    # Update display
                    self.__on_transform_update()
                    
                    # Show rotation feedback with current angle
                    self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                    self.show_guidance_text(self.__msg_mgr.get_message('M043').format(total_angle_change), is_rotation=True)
        else:
            # Normal dragging - move all visible layers
            for layer_id, visible in self.__visible_layers.items():
                if not visible:
                    continue
                    
                if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                    r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                    
                    # Update position
                    new_x = x + delta_x
                    new_y = y + delta_y
                    
                    # Update transformation data
                    self.__layer_transform_data[layer_id][self.__current_page_index] = (r, new_x, new_y, s)
            
            # Update display
            self.__on_transform_update()
        
        # Update last mouse position
        self.__last_mouse_x = current_x
        self.__last_mouse_y = current_y
        
        # Log mouse drag with throttling to avoid excessive logs
        if self._transform_log_throttle.should_log(key="mouse_drag"):
            logger.debug(self.__msg_mgr.get_message("L513").format(event.x, event.y, delta_x, delta_y))
    
    def on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release event.
        
        Args:
            event: Mouse button release event
        """
        # Update last mouse position to prevent angle calculation drift using canvas coordinates
        if self.__canvas_ref is not None:
            self.__last_mouse_x = self.__canvas_ref.canvasx(event.x)
            self.__last_mouse_y = self.__canvas_ref.canvasy(event.y)
        
        # Reset dragging flag
        self.__dragging = False
        
        # Check if we were in rotation mode
        if self.__rotation_mode:
            # Check if Ctrl key is still pressed
            ctrl_pressed = False
            if hasattr(event, 'state'):
                # Ensure state is an integer before performing bitwise operation
                if isinstance(event.state, int):
                    ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
            
            # If Ctrl is no longer pressed and we're not keeping rotation elements visible,
            # exit rotation mode
            if not ctrl_pressed and not self.__keep_rotation_elements_visible:
                # Use the exit rotation mode method to properly clean up
                self.__exit_rotation_mode()
                
                # Update display to reflect changes immediately
                if self.__canvas_ref:
                    try:
                        self.__canvas_ref.update_idletasks()
                    except Exception as e:
                        logger.debug(self.__msg_mgr.get_message("L526").format(str(e)))
                
                # Log exit from rotation mode\n                logger.debug(self.__msg_mgr.get_message(\ L516\))
        
        # Log mouse up event
        logger.debug(self.__msg_mgr.get_message("L514").format(event.x, event.y))
        
    def on_key_press(self, event: tk.Event) -> Optional[str]:
        """Handle keyboard press events.
        
        Args:
            event: Keyboard event
            
        Returns:
            String to prevent default handling or None
        """
        # Process keyboard shortcuts
        if hasattr(event, 'keysym') and hasattr(event, 'state') and isinstance(event.state, int):
            # Check if Ctrl key is pressed
            ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
            
            if ctrl_pressed:
                # Handle Ctrl+R for rotate right 90°
                if event.keysym in ['r', 'R']:
                    # Call rotate right and return its result or "break" if it returns None
                    result = self.on_rotate_right(event)
                    return result if result is not None else "break"
                    
                # Handle Ctrl+L for rotate left 90°
                elif event.keysym in ['l', 'L']:
                    # Call rotate left and return its result or "break" if it returns None
                    result = self.on_rotate_left(event)
                    return result if result is not None else "break"
                    
                # Handle Ctrl+V for vertical flip
                elif event.keysym == 'v' or event.keysym == 'V':
                    # Call vertical flip and return its result or "break" if it returns None
                    # Notification is displayed inside on_flip_vertical method
                    result = self.on_flip_vertical(event)
                    return result if result is not None else "break"
                    
                # Handle Ctrl+H for horizontal flip
                elif event.keysym == 'h' or event.keysym == 'H':
                    # Call horizontal flip and return its result or "break" if it returns None
                    # Notification is displayed inside on_flip_horizontal method
                    result = self.on_flip_horizontal(event)
                    return result if result is not None else "break"
                    
                # Handle Ctrl+B for reset transformations
                elif event.keysym in ['b', 'B']:
                    # TODO: Add reset implementation
                    # Show notification
                    self.show_notification(self.__msg_mgr.get_message('M048'))
                    return "break"
                    
                # Handle Ctrl+? for showing/hiding shortcut help
                elif event.keysym == 'slash' and (event.state & 0x1) != 0:  # Shift+/ is ?
                    # Use the toggle_shortcut_guide method to prevent duplicate calls
                    # This will handle showing/hiding the guide and manage the visibility flag
                    # The toggle_shortcut_guide method will set __user_toggled_shortcut_guide to True
                    self.toggle_shortcut_guide(event)
                    
                    # Show brief notification only when showing the guide (not when hiding)
                    if self.__shortcut_guide_visible:
                        shortcut_guide = self.__msg_mgr.get_message('M049')
                        self.show_notification(shortcut_guide.split('\n')[0])
                    
                    return "break"
        
        # Check if Ctrl key is pressed
        if hasattr(event, 'state'):
            # Ensure state is an integer before performing bitwise operation
            if isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
                
                # If Ctrl is pressed, enter rotation mode
                if ctrl_pressed and not self.__rotation_mode:
                    self.__rotation_mode = True
                    self.__rotation_active = False
                    
                    # Use canvas center as default rotation center
                    if self.__canvas_ref:
                        canvas_width = self.__canvas_ref.winfo_width()
                        canvas_height = self.__canvas_ref.winfo_height()
                        self.__rotation_center_x = canvas_width / 2
                        self.__rotation_center_y = canvas_height / 2
                        
                        # Show rotation center immediately
                        self.show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                        self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation mode
                        
                        # Log rotation mode activation
                        logger.debug(self.__msg_mgr.get_message("L515").format(
                            self.__rotation_center_x, self.__rotation_center_y))
        
        # Allow default handling for other keys
        return None
        
    def on_key_release(self, event: tk.Event) -> None:
        """Handle keyboard release events.
        
        Args:
            event: Keyboard event
        """
        # Check if Ctrl key was released
        if hasattr(event, 'keysym') and (event.keysym == 'Control_L' or event.keysym == 'Control_R'):
            # If in rotation mode, exit it when Ctrl is released
            if self.__rotation_mode and not self.__keep_rotation_elements_visible:
                # Use the exit rotation mode method to properly clean up
                self.__exit_rotation_mode()
                
                # Update display to reflect changes immediately
                if self.__canvas_ref:
                    try:
                        self.__canvas_ref.update_idletasks()
                    except Exception as e:
                        logger.debug(self.__msg_mgr.get_message("L526").format(str(e)))
                
                # Log rotation mode exit
                logger.debug(self.__msg_mgr.get_message("L516"))
        
    def on_mouse_wheel(self, event: tk.Event, layer_data=None) -> None:
        """Handle mouse wheel events for zooming.
        
        Args:
            event: Mouse wheel event
            layer_data: Optional layer data if provided externally
        """
        # Determine the direction and amount of scrolling
        delta = 0
        
        # Handle different wheel event formats across platforms
        if hasattr(event, 'delta'):
            # Windows and macOS (newer Tk versions)
            delta = event.delta
        elif hasattr(event, 'num'):
            # Linux (Button-4 is scroll up, Button-5 is scroll down)
            if event.num == 4:
                delta = 120  # Scroll up
            elif event.num == 5:
                delta = -120  # Scroll down
        
        # Calculate zoom factor based on wheel delta
        # Positive delta = zoom in, negative delta = zoom out
        zoom_factor = 1.0
        if delta > 0:
            zoom_factor = 1.1  # Zoom in by 10%
        elif delta < 0:
            zoom_factor = 0.9  # Zoom out by 10%
        else:
            return  # No change if delta is 0
        
        # Apply zoom to all visible layers
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                
                # Apply zoom factor to scale
                new_scale = s * zoom_factor
                
                # Limit scale to reasonable bounds (0.1x to 10x)
                new_scale = max(0.1, min(10.0, new_scale))
                
                # Update transformation data with new scale
                self.__layer_transform_data[layer_id][self.__current_page_index] = (r, x, y, new_scale)
        
        # Log zoom operation with throttling
        if self._wheel_log_throttle.should_log(key="zoom_operation"):
            logger.debug(self.__msg_mgr.get_message("L517").format(zoom_factor))
        
        # Update display
        self.__on_transform_update()
        
    def attach_to_canvas(self, canvas: tk.Canvas) -> None:
        """Attach this handler to a canvas widget.
        
        Args:
            canvas: The canvas to attach to
        """
        self.__canvas_ref = canvas
        
        # Bind mouse events
        self.__canvas_ref.bind("<ButtonPress-1>", self.on_mouse_down)
        self.__canvas_ref.bind("<B1-Motion>", self.on_mouse_drag)
        self.__canvas_ref.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Bind keyboard events
        self.__canvas_ref.bind("<KeyPress>", self.on_key_press)
        self.__canvas_ref.bind("<KeyRelease>", self.on_key_release)
        
        # Bind specific Ctrl key release events to ensure rotation mode ends
        self.__canvas_ref.bind("<KeyRelease-Control_L>", self.__exit_rotation_mode)
        self.__canvas_ref.bind("<KeyRelease-Control_R>", self.__exit_rotation_mode)
        
        # Bind mouse wheel for zooming
        self.__canvas_ref.bind("<MouseWheel>", self.on_mouse_wheel)
        
        # Make canvas focusable to receive keyboard events
        self.__canvas_ref.config(takefocus=1)
        
    # Note: This method was removed because it was a duplicate of the one defined at line 746
    
    # Note: This method was removed because it was a duplicate of the one defined at line 492
    
    def clear_feedback(self) -> None:
        """Clear all visual feedback elements.
        
        This method cancels all timers and hides all UI feedback elements.
        It also resets rotation mode flags but does not affect the shortcut guide
        if it was explicitly toggled by the user.
        """
        # First cancel all timers to prevent UI elements from reappearing
        self.__cancel_all_timers()
        
        # Hide all UI feedback elements
        self.hide_feedback_circle()
        self.hide_guidance_text()
        self.hide_notification()
        
        # Only hide shortcut guide if it wasn't explicitly toggled by user
        if not self.__user_toggled_shortcut_guide and self.__shortcut_guide_visible:
            self.__hide_shortcut_guide()
        
        # Reset rotation mode flags
        self.__rotation_mode = False
        self.__rotation_active = False
        
        # Log feedback clearing
        logger.debug(self.__msg_mgr.get_message("L528"))
    
    def update_state(self, current_page_index: Optional[int] = None, visible_layers: Optional[Dict[int, bool]] = None, layer_transform_data: Optional[Dict[int, List[Tuple[float, float, float, float]]]] = None) -> None:
        """Update the state of the mouse event handler.
        
        Args:
            current_page_index: Current page index to display
            visible_layers: Dictionary of layer visibility states {layer_id: is_visible}
            layer_transform_data: Dictionary of layer transformation data {layer_id: [(rotation, x, y, scale), ...]}
        """
        # Cancel any existing timers to prevent UI elements from appearing after state changes
        self.__cancel_all_timers()
        
        # Only update if the page index has actually changed
        if current_page_index is not None and current_page_index != self.__current_page_index:
            # Exit rotation mode if active (this will handle cleaning up UI elements)
            if self.__rotation_mode:
                self.__exit_rotation_mode()
            else:
                # Clear any feedback elements when changing pages
                # clear_feedback method already handles shortcut guide visibility based on __user_toggled_shortcut_guide flag
                self.clear_feedback()
                
                # Keep shortcut guide if explicitly toggled by user
                if not self.__user_toggled_shortcut_guide and self.__shortcut_guide_visible:
                    self.__hide_shortcut_guide()
            
            self.__current_page_index = current_page_index
            
            # Log page change
            logger.debug(self.__msg_mgr.get_message("L518").format(current_page_index))
        else:
            # Update current page index if provided but not different
            if current_page_index is not None:
                self.__current_page_index = current_page_index
            
        # Update visible layers if provided
        if visible_layers is not None:
            self.__visible_layers = visible_layers
            
        # Update layer transform data if provided
        if layer_transform_data is not None:
            self.__layer_transform_data = layer_transform_data
            
        # Log the state update with page and layer information
        logger.debug(self.__msg_mgr.get_message("L518").format(
            self.__current_page_index,
            len(self.__visible_layers) if self.__visible_layers else 0,
            sum(1 for layer_id, is_visible in self.__visible_layers.items() if is_visible) if self.__visible_layers else 0
        ))
    
    def __rotate_by_angle(self, angle_degrees: float) -> None:
        """Rotate all visible layers by the specified angle.
        
        Args:
            angle_degrees: Angle to rotate in degrees (positive = clockwise)
        """
        # Skip very small angle changes to prevent infinite loops
        if abs(angle_degrees) < 0.05:
            return
            
        # Apply rotation to all visible layers
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                
                # Add the new rotation angle to the current rotation and normalize to 0-360 range
                # Use modulo operator instead of loops to prevent infinite loops
                new_rotation = (r + angle_degrees) % 360
                
                # Update the transformation data
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_rotation, x, y, s)
        
        # Log the rotation operation
        logger.debug(self.__msg_mgr.get_message("L511").format(angle_degrees))
        
    # Note: This method was removed because it was a duplicate of the one defined at line 653
    
    # Note: This method was removed because it was a duplicate of the one defined at line 725

