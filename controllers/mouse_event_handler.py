import tkinter as tk
import time
import math
import threading
from logging import getLogger
from typing import Dict, List, Tuple, Union, Optional, Callable, TYPE_CHECKING, Literal, cast, Any

# Type checking imports
if TYPE_CHECKING:
    from configurations.user_setting_manager import UserSettingManager  # type: ignore
    from controllers.image_operations import ImageOperations

from configurations.message_manager import get_message_manager
from configurations import tool_settings
from utils.log_throttle import LogThrottle
from configurations.user_setting_manager import UserSettingManager  # type: ignore
from controllers.image_operations import ImageOperations

# Type aliases for canvas anchor positions
AnchorLiteral = Literal["nw", "n", "ne", "e", "se", "s", "sw", "w", "center"]

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
            user_settings_manager: Optional[Any] = None,
            image_operations_dict: Optional[Dict[int, Any]] = None,
        ) -> None:
        """Initialize the MouseEventHandler.

        Args:
            layer_transform_data (Dict[int, List[Tuple[float, float, float, float]]]): Transformation data for each layer.
                Dict[layer_number, List[(rotation, x, y, scale), ...]]
            current_page_index (int): Current page index.
            visible_layers (Dict[int, bool]): Layer visibility state Dict[layer_number, visibility_state].
            on_transform_update (Callable[[], None]): Callback function to update the display after transformation.
            user_settings_manager (Optional[Any]): User settings manager instance. Default is None.
            image_operations_dict (Optional[Dict[int, Any]]): Dictionary of image operations for each layer. Default is None.
        """
        # Transform data and callbacks
        self.__layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]] = layer_transform_data
        self.__current_page_index: int = current_page_index
        self.__visible_layers: Dict[int, bool] = visible_layers
        self.__on_transform_update: Callable[[], None] = on_transform_update
        
        # Store ImageOperations instances by layer ID
        self.__image_operations_dict: Dict[int, ImageOperations] = {} if image_operations_dict is None else image_operations_dict

        # Tracking variables
        self.__dragging: bool = False
        self.__last_mouse_x: float = 0.0
        self.__last_mouse_y: float = 0.0
        
        # Timer tracking - after() returns str in tkinter
        self._hide_after_ids: List[Optional[str]] = []
        
        # Rotation parameters
        self.__rotation_mode: bool = False
        self.__rotation_center_x: float = 0.0
        self.__rotation_center_y: float = 0.0
        self.__rotation_start_time: float = 0.0
        self.__rotation_active: bool = False
        self.__last_rotation_exit_time: float = 0.0  # Track last rotation exit time for log suppression
        
        # Flip flags for each layer and page
        # Dict[layer_id, List[Tuple[flip_horizontal, flip_vertical], ...]] for each page
        self.__layer_flip_flags: Dict[int, List[Tuple[bool, bool]]] = {}
        
        # Initialize flip flags for all layers
        self.__initialize_flip_flags()
        
        # Flag to track if shortcut guide was toggled by user
        self.__user_toggled_shortcut_guide: bool = False
        
        # Flag to track if shortcut guide is currently visible
        self.__shortcut_guide_visible: bool = False
        
        # Shortcut guide item IDs
        self.__shortcut_guide_ids: List[Union[int, str]] = []
        self.__shortcut_guide_timer: Optional[threading.Timer] = None
        self.__auto_hide_timer: Optional[str] = None  # Timer ID for auto-hide functionality
        
        # Get message manager for localized messages
        self.__msg_mgr = get_message_manager()
        
        # Canvas reference (will be set in attach_to_canvas)
        self.__canvas_ref: Optional[tk.Canvas] = None
        
        # Feedback visual elements with improved type annotations
        self.__feedback_circle_id: Optional[Union[int, str, Tuple[int, int], Tuple[str, str]]] = None
        # Type annotation for guidance text ID that can be None, int, str, or tuple of int/str
        self.__guidance_text_id: Optional[Union[int, str, Tuple[int, int], Tuple[str, str]]] = None
        self.__background_id: Optional[Union[int, str]] = None
        
        # Initialize user settings manager
        # Use provided user_settings_manager if available, otherwise create a new instance
        self.__user_settings_mgr: UserSettingManager = user_settings_manager if user_settings_manager is not None else UserSettingManager()
        # Type annotation for notification text ID that can be None, int, str, or tuple of int/str
        self.__notification_text_id: Optional[Union[int, str, Tuple[int, int], Tuple[str, str]]] = None
        self.__help_display_id: Optional[int] = None
        self.__help_background_id: Optional[int] = None
        
        # UI state
        # self.__shortcut_guide_visible is already defined at line 67
        # self.__guidance_text_visible is already defined at line 60
        # self.__notification_visible is already defined at line 62

        # UI Element Tags
        self.ROTATION_CENTER_TAG: str = "rotation_center_dot_tag"
        self.ROTATION_GUIDANCE_TAG: str = "rotation_guidance_text_tag" # Tag for rotation-specific guidance
        self.GUIDANCE_TEXT_TAG: str = "guidance_text_tag" # Tag for general guidance text
        self.SHORTCUT_GUIDE_TAG: str = "shortcut_guide_tag" # Tag for shortcut guide elements
        
        # UI visibility flags
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
        self.__ctrl_check_timer_id: Optional[int] = None
        self.__ctrl_check_interval: int = 100  # Check every 100ms
        
        # Message manager (for localized text)
        self.__msg_mgr = message_manager  # Use the global message_manager instance
        
        # Log throttles for various events
        self._wheel_log_throttle = LogThrottle(min_interval=0.5)
        self._transform_log_throttle = LogThrottle(min_interval=0.5)
        
        # Initialize wheel log time tracking for throttling
        self._last_wheel_log_time: float = 0.0
        
        # Operation throttling to prevent rapid consecutive operations
        # Last operation timestamp and cooldown period
        self.__last_operation_time: float = 0.0
        self.__operation_cooldown: float = 0.3  # 300ms cooldown between operations

    def __initialize_flip_flags(self) -> None:
        """Initialize flip flags for all layers and pages.
        
        This method ensures that flip flags are properly initialized for all layers
        in the layer_transform_data dictionary.
        """
        # Initialize flip flags for each layer that has transform data
        for layer_id in self.__layer_transform_data.keys():
            # Create empty list for this layer if it doesn't exist
            if layer_id not in self.__layer_flip_flags:
                self.__layer_flip_flags[layer_id] = []
            
            # Ensure flip flags exist for all pages in this layer
            while len(self.__layer_flip_flags[layer_id]) < len(self.__layer_transform_data[layer_id]):
                # Default is no flipping (False, False) for horizontal and vertical
                self.__layer_flip_flags[layer_id].append((False, False))
                
    def __update_flip_flags_for_layer(self, layer_id: int) -> None:
        """Update flip flags for a layer, initializing if needed.
        
        Args:
            layer_id (int): Layer ID to update flip flags for
        """
        # Initialize flip flags for this layer if not already done
        if layer_id not in self.__layer_flip_flags:
            self.__layer_flip_flags[layer_id] = []
            
        # Ensure we have enough entries for the current page
        while len(self.__layer_flip_flags[layer_id]) <= self.__current_page_index:
            self.__layer_flip_flags[layer_id].append((False, False))  # Default: no flips
            
    def get_flip_flags(self, layer_id: int, page_index: int) -> Tuple[bool, bool]:
        """Get the horizontal and vertical flip flags for a specific layer and page.
        
        Args:
            layer_id (int): Layer ID to get flip flags for
            page_index (int): Page index to get flip flags for
            
        Returns:
            Tuple[bool, bool]: A tuple containing (horizontal_flip, vertical_flip) flags
        """
        # Initialize flip flags for this layer if not already done
        if layer_id not in self.__layer_flip_flags:
            return (False, False)  # Default: no flips
            
        # Check if we have flip flags for this page
        if page_index < len(self.__layer_flip_flags[layer_id]):
            return self.__layer_flip_flags[layer_id][page_index]
            
        # If page index is out of range, return default
        return (False, False)

    def __toggle_flip_flag(self, axis: str) -> None:
        """Toggle flip flag for the specified axis on all visible layers.
        
        Args:
            axis: The axis to flip, either "x" for horizontal or "y" for vertical
        """
        # Apply flip to all visible layers
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
                
            # Check if we have an ImageOperations instance for this layer
            if layer_id in self.__image_operations_dict:
                # Use the appropriate flip method from ImageOperations
                if axis == "x":
                    # Horizontal flip (mirror across vertical axis)
                    self.__image_operations_dict[layer_id].flip_horizontal()
                else:  # axis == "y":
                    # Vertical flip (mirror across horizontal axis)
                    self.__image_operations_dict[layer_id].flip_vertical()
                    
                # Ensure we update the flip flags to match the operation
                # Initialize or update flip flags for this layer
                self.__update_flip_flags_for_layer(layer_id)
                    
                # Get current flip flags
                current_h_flip, current_v_flip = self.__layer_flip_flags[layer_id][self.__current_page_index]
                
                # Toggle appropriate flip flag based on axis
                if axis == "x":
                    # Toggle horizontal flip flag
                    self.__layer_flip_flags[layer_id][self.__current_page_index] = (not current_h_flip, current_v_flip)
                else:  # axis == "y"
                    # Toggle vertical flip flag
                    self.__layer_flip_flags[layer_id][self.__current_page_index] = (current_h_flip, not current_v_flip)
                continue
                
            # Fall back to coordinate-based flipping if no ImageOperations instance
            # Initialize or update flip flags for this layer
            self.__update_flip_flags_for_layer(layer_id)
            
            # Get current flip flags
            current_h_flip, current_v_flip = self.__layer_flip_flags[layer_id][self.__current_page_index]
            
            # Toggle appropriate flip flag based on axis
            if axis == "x":
                # Toggle horizontal flip flag
                self.__layer_flip_flags[layer_id][self.__current_page_index] = (not current_h_flip, current_v_flip)
            else:  # axis == "y"
                # Toggle vertical flip flag
                self.__layer_flip_flags[layer_id][self.__current_page_index] = (current_h_flip, not current_v_flip)
                
            # Update transformation data based on new flip flags
            if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                # Get current transformation data
                r, tx, ty, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                
                # Get updated flip flags
                h_flip, v_flip = self.__layer_flip_flags[layer_id][self.__current_page_index]
                
                # Apply scale sign changes based on flip flags
                # For horizontal flip, negate the scale
                # For vertical flip, negate the scale
                # If both flips are active, scale remains positive
                scale_sign = 1
                if h_flip != v_flip:  # If only one flip is active, negate scale
                    scale_sign = -1
                
                # Update transformation with correct scale sign
                self.__layer_transform_data[layer_id][self.__current_page_index] = (r, tx, ty, abs(s) * scale_sign)
                
                # Trigger transform update callback
                # Direct call without unnecessary check as function is always truthy
                self.__on_transform_update()
    
    def __is_other_key_pressed(self, event: tk.Event) -> bool:
        """Check if any key other than Ctrl is effectively pressed along with Ctrl.
        This is a helper to distinguish Ctrl-only from Ctrl+Key combinations.

        Args:
            event: The key event.

        Returns:
            True if another key (modifier or regular) seems to be part of the event, False otherwise.
        """
        # This is a simplified check. Tkinter's event.keysym for modifier-only presses
        # usually gives the modifier itself (e.g., "Control_L").
        # If event.keysym is something else (like "r", "L", "Shift_L", etc.) while Ctrl is held,
        # it means it's a Ctrl+Key combination.
        if event.keysym not in ("Control_L", "Control_R"):
            return True
        
        # Further check: if event.state has bits other than the Ctrl bit (0x4),
        # it implies other modifiers like Shift (0x1), Alt, etc., are also pressed.
        # Ctrl state is 0x4. If event.state is, for example, 0x5 (Ctrl+Shift),
        # then (event.state & ~0x4) would be non-zero.
        if isinstance(event.state, int) and (event.state & ~0x4) != 0: # Check if other modifier bits are set
            return True
            
        return False
        
        # List to store after IDs for cancellation is already defined at line 55

    def on_rotate_right(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+R keyboard shortcut for 90-degree clockwise rotation.
        
        Args:
            event: Keyboard event (optional)
            
        Returns:
            String to prevent default handling or None
        """
        # Cancel any existing timers to prevent UI conflicts
        self.__cancel_all_timers()
        
        # Hide any existing feedback circles
        self.hide_feedback_circle()
        
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
        
        # Set default rotation center if not already set(rotate right)
        if not was_in_rotation_mode:
            # Calculate image center based on visible layers' positions and dimensions
            # instead of using canvas center
            image_center_x = None
            image_center_y = None
            
            # Try to find the center of the first visible layer
            for layer_id, visible in self.__visible_layers.items():
                if visible and layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                    # Get current transformation data
                    transform_data = self.__layer_transform_data[layer_id][self.__current_page_index]
                    _, x, y, s = transform_data[:4]
                    
                    # Calculate image center based on transformation data
                    # Estimate image dimensions (typical PDF page size)
                    estimated_width = 800
                    estimated_height = 1100
                    
                    # Calculate center position based on position and scale
                    image_center_x = x + (estimated_width * abs(s)) / 2
                    image_center_y = y + (estimated_height * abs(s)) / 2
                    break
            
            # If we couldn't find an image center, fall back to canvas center
            if image_center_x is None or image_center_y is None:
                if self.__canvas_ref:
                    canvas_width = self.__canvas_ref.winfo_width()
                    canvas_height = self.__canvas_ref.winfo_height()
                    image_center_x = canvas_width / 2
                    image_center_y = canvas_height / 2
                else:
                    # Default values if canvas reference is not available
                    image_center_x = 0
                    image_center_y = 0
            
            # Set rotation center to image center
            self.__rotation_center_x = image_center_x
            self.__rotation_center_y = image_center_y
            
            # Temporarily activate rotation mode to show feedback
            self.__rotation_mode = True
            self.__rotation_active = False
            self.__rotation_start_time = time.time()
            
            # Only show feedback circle if already in rotation mode to prevent unwanted red dots
            if was_in_rotation_mode:
                # Do not show feedback circle for shortcut operations - prevent unwanted red dots
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation mode
        
        # Rotate visible layers 90 degrees clockwise
        self.__rotate_by_angle(90)
        
        # Reset translation to prevent image from moving off-screen after multiple rotations
        for layer_id, visible in self.__visible_layers.items():
            if visible and layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                # Get current transform data
                rotation, tx, ty, scale = self.__layer_transform_data[layer_id][self.__current_page_index]
                # Reset translation while keeping rotation and scale
                self.__layer_transform_data[layer_id][self.__current_page_index] = (rotation, 0.0, 0.0, scale)
                
        # Update display
        self.__on_transform_update()
        
        # First draw shortcut guide (fixed position in viewport)
        self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
        
        # Then show notification and raise it to the top
        self.show_notification(self.__msg_mgr.get_message('M044'), 1.5, warning=True)  # Rotated 90° right
        # Ensure notification is always on top
        if self.__notification_text_id and self.__canvas_ref:
            self.__canvas_ref.tag_raise("notification_tag")
        if self.__notification_text_id and self.__canvas_ref and isinstance(self.__notification_text_id, (str, int)):
            self.__canvas_ref.tag_raise(self.__notification_text_id)  # Ensure notification is on top
        
        # Restore rotation mode state if it was active or Ctrl is pressed
        if was_in_rotation_mode or ctrl_pressed:
            self.__rotation_mode = True
            self.__rotation_active = was_rotation_active  # Preserve active state
            self.__rotation_center_x = rotation_center_x if rotation_center_x is not None else self.__rotation_center_x
            self.__rotation_center_y = rotation_center_y if rotation_center_y is not None else self.__rotation_center_y
            
            # Only show feedback and guidance if in rotation mode or Ctrl is pressed
            if self.__rotation_mode or ctrl_pressed:
                # Do not show feedback circle for shortcut operations - prevent unwanted red dots
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
        else:
            # If we weren't in rotation mode before and Ctrl is not pressed, exit it after the rotation
            self.__rotation_mode = False
            self.__rotation_active = False
            
            # Hide the feedback after a short delay, but only if we were in rotation mode
            # This prevents showing feedback circle when not in rotation mode
            if self.__canvas_ref and was_in_rotation_mode:
                # Use longer delay (2000ms) for better visibility after rotation
                # Store the after_id for later cancellation
                # Only hide guidance text after a delay
                # No need to hide feedback circle as it's not shown for shortcuts
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after ID to the list for possible cancellation
                self._hide_after_ids.append(aid2)
        
        # Log rotation with proper multilingual message
        logger.debug(self.__msg_mgr.get_message("L415"))
        
        return "break"  # Prevent default handling
        
    def on_rotate_left(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+L keyboard shortcut for 90-degree counterclockwise rotation.
        
        Args:
            event (tk.Event | None): Keyboard event that triggered this action. Default is None.
            
        Returns:
            str | None: String to prevent default handling or None.
        """
        # Cancel any existing timers to prevent UI conflicts
        self.__cancel_all_timers()
        
        # Always hide any existing feedback circles to prevent red dot display
        # This is critical to fix the issue with red dots appearing when switching between rotation modes
        self.hide_feedback_circle()
        
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
        
        # Set default rotation center if not already set(rotate left)
        if not was_in_rotation_mode:
            # Calculate image center based on visible layers' positions and dimensions
            # instead of using canvas center
            image_center_x = None
            image_center_y = None
            
            # Try to find the center of the first visible layer
            for layer_id, visible in self.__visible_layers.items():
                if visible and layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                    # Get current transformation data
                    transform_data = self.__layer_transform_data[layer_id][self.__current_page_index]
                    _, x, y, s = transform_data[:4]
                    
                    # Calculate image center based on transformation data
                    # Estimate image dimensions (typical PDF page size)
                    estimated_width = 800
                    estimated_height = 1100
                    
                    # Calculate center position based on position and scale
                    image_center_x = x + (estimated_width * abs(s)) / 2
                    image_center_y = y + (estimated_height * abs(s)) / 2
                    break
            
            # If we couldn't find an image center, fall back to canvas center
            if image_center_x is None or image_center_y is None:
                if self.__canvas_ref:
                    canvas_width = self.__canvas_ref.winfo_width()
                    canvas_height = self.__canvas_ref.winfo_height()
                    image_center_x = canvas_width / 2
                    image_center_y = canvas_height / 2
                else:
                    # Default values if canvas reference is not available
                    image_center_x = 0
                    image_center_y = 0
            
            # Set rotation center to image center
            self.__rotation_center_x = image_center_x
            self.__rotation_center_y = image_center_y
            
            # Temporarily activate rotation mode to show feedback
            self.__rotation_mode = True
            self.__rotation_active = False
            self.__rotation_start_time = time.time()
            
            # Only show feedback circle if already in rotation mode to prevent unwanted red dots
            if was_in_rotation_mode:
                # Do not show feedback circle for shortcut operations - prevent unwanted red dots
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation mode
        
        # Rotate visible layers 90 degrees counterclockwise
        self.__rotate_by_angle(-90)
        
        # Reset translation to prevent image from moving off-screen after multiple rotations
        for layer_id, visible in self.__visible_layers.items():
            if visible and layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                # Get current transform data
                rotation, tx, ty, scale = self.__layer_transform_data[layer_id][self.__current_page_index]
                # Reset translation while keeping rotation and scale
                self.__layer_transform_data[layer_id][self.__current_page_index] = (rotation, 0.0, 0.0, scale)
                
        # Update display
        self.__on_transform_update()
        
        # Draw shortcut guide first (fixed position in viewport)
        self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
        
        # Then show notification and raise it to the top
        self.show_notification(self.__msg_mgr.get_message('M045'), 1.5, warning=True)  # Rotated 90° left
        # Ensure notification is always on top
        if self.__notification_text_id and self.__canvas_ref:
            self.__canvas_ref.tag_raise("notification_tag")
        if self.__notification_text_id and self.__canvas_ref and isinstance(self.__notification_text_id, (str, int)):
            self.__canvas_ref.tag_raise(self.__notification_text_id)  # Ensure notification is on top
        
        # Restore rotation mode state if it was active or Ctrl is pressed
        if was_in_rotation_mode or ctrl_pressed:
            self.__rotation_mode = True
            self.__rotation_active = was_rotation_active  # Preserve active state
            self.__rotation_center_x = rotation_center_x if rotation_center_x is not None else self.__rotation_center_x
            self.__rotation_center_y = rotation_center_y if rotation_center_y is not None else self.__rotation_center_y
            
            # Only show feedback and guidance if in rotation mode or Ctrl is pressed
            if self.__rotation_mode or ctrl_pressed:
                # Do not show feedback circle for shortcut operations - prevent unwanted red dots
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
        else:
            # If we weren't in rotation mode before and Ctrl is not pressed, exit it after the rotation
            self.__rotation_mode = False
            self.__rotation_active = False
            # Hide the feedback after a short delay, but only if we were in rotation mode
            # This prevents showing feedback circle when not in rotation mode
            if self.__canvas_ref and was_in_rotation_mode:
                # Use longer delay (2000ms) for better visibility after rotation
                # Store the after_id for later cancellation
                # Only hide guidance text after a delay
                # No need to hide feedback circle as it's not shown for shortcuts
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after ID to the list for possible cancellation
                self._hide_after_ids.append(aid2)
        
        # Log rotation with proper multilingual message
        logger.debug(self.__msg_mgr.get_message("L416"))
        
        return "break"  # Prevent default handling
        
    def on_flip_vertical(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+V keyboard shortcut for vertical flip.
        
        Args:
            event: Keyboard event (optional)
            
        Returns:
            String to prevent default handling or None
        """
        self.__cancel_all_timers() # Cancel previous timers
        
        # Clear existing UI elements to prevent duplication
        if self.__canvas_ref:
            # Clear any existing feedback circles and guidance text
            self.hide_feedback_circle()
            self.hide_guidance_text()
            self.hide_notification()
        
        # Log the vertical flip operation
        logger.debug(self.__msg_mgr.get_message("L418"))
        
        # Use the common toggle flip flag method for vertical flip (y-axis)
        self.__toggle_flip_flag("y")
        
        # Reset translation to prevent image from moving off-screen after multiple flips
        for layer_id, visible in self.__visible_layers.items():
            if visible and layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                # Get current transform data
                rotation, tx, ty, scale = self.__layer_transform_data[layer_id][self.__current_page_index]
                # Reset translation while keeping rotation and scale
                self.__layer_transform_data[layer_id][self.__current_page_index] = (rotation, 0.0, 0.0, scale)
        
        # Update display
        self.__on_transform_update()
        
        # Draw shortcut guide first (fixed position in viewport)
        self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
        
        # Then show notification and raise it to the top
        self.show_notification(self.__msg_mgr.get_message('M046'), 1.5, warning=True)  # Flipped vertically
        # Ensure notification is always on top
        if self.__notification_text_id and self.__canvas_ref:
            self.__canvas_ref.tag_raise("notification_tag")
            # Only hide guidance text after a delay
            # No need to hide feedback circle as it's not shown for shortcuts
            aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
            # Add after ID to the list for possible cancellation
            self._hide_after_ids.append(aid2)
        
        return "break"  # Prevent default handling
        
    def on_flip_horizontal(self, event: tk.Event | None = None) -> str | None:
        """Handle Ctrl+H keyboard shortcut for horizontal flip.
        
        Args:
            event: Keyboard event (optional)
            
        Returns:
            String to prevent default handling or None
        """
        self.__cancel_all_timers() # Cancel previous timers
        # Save rotation mode state before operations
        was_in_rotation_mode = self.__rotation_mode
        
        # Clear existing UI elements to prevent duplication
        if self.__canvas_ref:
            # Clear any existing feedback circles and guidance text
            self.hide_feedback_circle()
            self.hide_guidance_text()
            self.hide_notification()
        
        # Log the horizontal flip operation
        logger.debug(self.__msg_mgr.get_message("L419"))
        
        # Use the common toggle flip flag method for horizontal flip (x-axis)
        self.__toggle_flip_flag("x")
        
        # Reset translation to prevent image from moving off-screen after multiple flips
        for layer_id, visible in self.__visible_layers.items():
            if visible and layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                # Get current transform data
                rotation, tx, ty, scale = self.__layer_transform_data[layer_id][self.__current_page_index]
                # Reset translation while keeping rotation and scale
                self.__layer_transform_data[layer_id][self.__current_page_index] = (rotation, 0.0, 0.0, scale)
        
        # Update display
        self.__on_transform_update()
        
        # Draw shortcut guide first (fixed position in viewport)
        self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
        
        # Then show notification and raise it to the top
        self.show_notification(self.__msg_mgr.get_message('M047'), 1.5, warning=True)  # Flipped horizontally
        # Ensure notification is always on top
        if self.__notification_text_id and self.__canvas_ref:
            self.__canvas_ref.tag_raise("notification_tag")
        if self.__notification_text_id and self.__canvas_ref and isinstance(self.__notification_text_id, (str, int)):
            self.__canvas_ref.tag_raise(self.__notification_text_id)  # Ensure notification is on top
        
        # Show feedback and handle rotation mode
        if self.__canvas_ref:
            # Check if Ctrl key is pressed
            ctrl_pressed = False
            if event and hasattr(event, 'state') and isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0
                
            # If in rotation mode or Ctrl is pressed, maintain rotation mode
            if was_in_rotation_mode or ctrl_pressed:
                self.__rotation_mode = True
                # Do not show feedback circle for shortcut operations - prevent unwanted red dots
                self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
            else:
                # Only hide guidance text after a delay
                # No need to hide feedback circle as it's not shown for shortcuts
                aid2 = self.__canvas_ref.after(2000, self.hide_guidance_text)
                # Add after ID to the list for possible cancellation
                self._hide_after_ids.append(aid2)
        
        return "break"  # Prevent default handling
        
    def draw_feedback_circle(self, x: float, y: float, is_rotating: bool = False) -> None:
        """Draw a feedback circle at the specified coordinates.
        
        Args:
            x (float): X-coordinate for the feedback circle.
            y (float): Y-coordinate for the feedback circle.
            is_rotating (bool): If True, indicates this is for rotation mode which may affect styling.
                Default is False.
        """
        # Ensure canvas reference is available
        if self.__canvas_ref is None:
            # Log missing canvas reference if attempting to draw
            logger.warning(self.__msg_mgr.get_message("L527")) # L527: Canvas reference is not set.
            return

        # Delete the old dot if it exists by its specific tag to prevent duplicates
        assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
        self.__canvas_ref.delete(self.ROTATION_CENTER_TAG)

        # Get user settings for feedback circle appearance
        radius = int(self.__user_settings_mgr.get_setting("feedback_circle_radius", 4))
        
        # Get colors from user settings
        fill_color = self.__user_settings_mgr.get_setting("feedback_circle_fill", "#ff0000") # Default: red
        outline_color = self.__user_settings_mgr.get_setting("feedback_circle_outline", "#ffffff") # Default: white
        outline_width = int(self.__user_settings_mgr.get_setting("feedback_circle_outline_width", 1))
        
        # Create the outer circle (white outline for better visibility)
        if outline_width > 0:
            outer_circle_id = self.__canvas_ref.create_oval(
                x - (radius + outline_width), 
                y - (radius + outline_width), 
                x + (radius + outline_width), 
                y + (radius + outline_width),
                fill=outline_color,
                outline="",
                tags=(self.ROTATION_CENTER_TAG,)
            )
        
        # Create the inner circle (red fill)
        inner_circle_id = self.__canvas_ref.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=fill_color,
            outline="",
            tags=(self.ROTATION_CENTER_TAG,)
        )
        
        # Store the IDs for later reference
        if outline_width > 0:
            self.__feedback_circle_id = (outer_circle_id, inner_circle_id)
        else:
            self.__feedback_circle_id = inner_circle_id
            
        # Add a pulsing effect if supported and enabled in user settings
        pulse_effect = self.__user_settings_mgr.get_setting("feedback_circle_pulse", False)
        if pulse_effect and hasattr(self.__canvas_ref, "after"):
            # Create a simple pulse effect by alternating opacity
            def pulse_animation(count=0):
                if not self.__feedback_circle_id or count >= 6:  # Limit to prevent infinite animation
                    return
                    
                # Toggle between normal and slightly larger size
                if count % 2 == 0:
                    self.__canvas_ref.itemconfig(inner_circle_id, fill=fill_color)
                    if outline_width > 0:
                        self.__canvas_ref.itemconfig(outer_circle_id, fill=outline_color)
                else:
                    # Use a slightly lighter color for the pulse effect
                    lighter_fill = self.__lighten_color(fill_color, 0.3)
                    lighter_outline = self.__lighten_color(outline_color, 0.3)
                    self.__canvas_ref.itemconfig(inner_circle_id, fill=lighter_fill)
                    if outline_width > 0:
                        self.__canvas_ref.itemconfig(outer_circle_id, fill=lighter_outline)
                
                # Schedule next pulse
                after_id = self.__canvas_ref.after(300, lambda: pulse_animation(count + 1))
                self._hide_after_ids.append(after_id)
            
            # Start the pulse animation
            pulse_animation()
        
        # Log the creation of the feedback circle
        logger.debug(self.__msg_mgr.get_message("L518").format(x, y))
        
    def __lighten_color(self, color_hex: str, factor: float = 0.3) -> str:
        """Lighten a hex color by the specified factor.
        
        Args:
            color_hex: Hex color string (e.g., "#ff0000")
            factor: Factor by which to lighten (0.0-1.0)
            
        Returns:
            Lightened hex color string
        """
        try:
            # Remove '#' if present
            color = color_hex.lstrip('#')
            
            # Convert to RGB
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            
            # Lighten each component
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
            
            # Convert back to hex
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            # Return original color if any error occurs
            return color_hex

    def hide_feedback_circle(self) -> None:
        """Hide the feedback circle if it exists."""
        # Remove the feedback circle from the canvas
        if self.__canvas_ref:
            # Delete all items tagged with ROTATION_CENTER_TAG
            assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
            self.__canvas_ref.delete(self.ROTATION_CENTER_TAG)
            
            # Reset the stored ID if any, as it's no longer valid
            if self.__feedback_circle_id is not None:
                try:
                    # Handle both single ID and tuple of IDs
                    if isinstance(self.__feedback_circle_id, tuple):
                        # Delete each ID in the tuple separately
                        for circle_id in self.__feedback_circle_id:
                            self.__canvas_ref.delete(circle_id)
                    else:
                        # Delete single ID
                        self.__canvas_ref.delete(self.__feedback_circle_id)
                except Exception as e:
                    # Log error when deleting feedback circle
                    logger.error(self.__msg_mgr.get_message("L505").format(str(e)))
                self.__feedback_circle_id = None
            
            if self.__background_id is not None:
                self.__background_id = None # Also reset this if it was used
        
        # Log the action of hiding the feedback circle
        logger.debug(self.__msg_mgr.get_message("L519", "Feedback circle (red dot) hidden.")) # L519: Feedback circle (red dot) hidden.
    
    # __cancel_all_timers method has been moved to line 954
    # with improved implementation including Ctrl check timer cancellation

    def show_guidance_text(self, message: str, is_rotation: bool = False) -> None:
        """Show guidance text on the canvas with a styled background.
        
        Args:
            message: The message to display
            is_rotation: Whether this is rotation-specific guidance
        """
        if not self.__canvas_ref:
            logger.warning(self.__msg_mgr.get_message("L527"))
            return
        
        # Log the request to show guidance text
        logger.debug(self.__msg_mgr.get_message("L540").format(f"Showing guidance text: {message}, is_rotation: {is_rotation}"))
        
        # Hide any existing guidance text first
        self.hide_guidance_text()
        
        # Force canvas update to ensure previous text is cleared
        self.__canvas_ref.update_idletasks()
        
        # Delete any existing guidance text tags to ensure clean slate
        tag_to_delete = self.ROTATION_GUIDANCE_TAG if is_rotation else self.GUIDANCE_TEXT_TAG
        self.__canvas_ref.delete(tag_to_delete)
        
        # For rotation mode, ensure rotation mode flag is set
        if is_rotation:
            self.__rotation_mode = True
            self.__keep_rotation_elements_visible = True
        
        if not self.__canvas_ref or not message:
            if not self.__canvas_ref:
                # Log missing canvas reference if attempting to draw
                logger.warning(self.__msg_mgr.get_message("L527")) # L527: Canvas reference is not set.
            elif not message:
                logger.debug("Empty message provided to show_guidance_text")
            return

        assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
        try:
            self.__canvas_ref.update_idletasks()
            canvas_height = self.__canvas_ref.winfo_height()
            canvas_width = self.__canvas_ref.winfo_width()

            # Font settings from UserSettingManager, with fallback from tool_settings
            font_family_val = self.__user_settings_mgr.get_setting("font_family", tool_settings.DEFAULT_FONT_FAMILY)
            
            # Get font size with proper error handling to prevent conversion errors
            try:
                font_size_val = self.__user_settings_mgr.get_setting("font_size", 10)
                # Ensure font_size is an integer
                guidance_font_size = int(font_size_val) if isinstance(font_size_val, (int, str)) else 10
            except (ValueError, TypeError) as e:
                # Log the error and use default font size
                logger.warning(self.__msg_mgr.get_log_message("L540", f"Invalid font size value: {e}"))
                guidance_font_size = 10
                
            font_style = "bold"  # Default font style for guidance text
            
            # Position settings - allow customization of position through user settings
            position = self.__user_settings_mgr.get_setting("guidance_position", "bottom-left")
            
            # Set position based on user preference or default to bottom-left
            if position == "bottom-right":
                text_x_val = float(canvas_width - 10)
                text_y_val = float(canvas_height - 10)
                anchor_val = "se"  # southeast anchor
            elif position == "top-left":
                text_x_val = 10.0
                text_y_val = 10.0
                anchor_val = "nw"  # northwest anchor
            elif position == "top-right":
                text_x_val = float(canvas_width - 10)
                text_y_val = 10.0
                anchor_val = "ne"  # northeast anchor
            else:  # Default to bottom-left
                text_x_val = 10.0
                text_y_val = float(canvas_height - 10)
                anchor_val = "sw"  # southwest anchor

            # Style settings from user settings with fallbacks
            if is_rotation:
                # Rotation guidance has special styling (typically red)
                text_color = self.__user_settings_mgr.get_setting("rotation_guidance_text_color", "#FF0000") # Red text
                # Use semi-transparent red border only
                bg_fill = ""          # No fill - transparent background
                border_color = "#FF0000"  # Red border
                stipple_option = "gray25"  # Semi-transparent pattern
            else:
                # Normal guidance uses standard styling (typically blue)
                text_color = self.__user_settings_mgr.get_setting("guidance_text_color", "#0000FF") # Blue text
                # Tkinter doesn't support RGBA 8-digit hex color codes like "#0000FF00" for transparency
                # Use empty background with stipple pattern instead for semi-transparency
                bg_fill = ""  # No fill - transparent background
                border_color = self.__user_settings_mgr.get_setting("guidance_border_color", "#0000FF") # Blue border
            
            # Get stipple pattern for semi-transparency
            stipple_option = self.__user_settings_mgr.get_setting("guidance_stipple", "gray25")

            # Ensure font components have explicit types for Mypy
            font_family_str = cast(str, font_family_val)
            font_size_int = cast(int, guidance_font_size)
            font_style_str = cast(str, font_style)
            
            # Handle font names with spaces by properly formatting the font definition
            # If font name contains spaces, wrap it in braces to ensure proper Tkinter font format
            if " " in font_family_str:
                font_definition = f"{{{font_family_str}}} {font_size_int} {font_style_str}"
            else:
                font_definition = f"{font_family_str} {font_size_int} {font_style_str}"

            # Create temporary text item to calculate dimensions
            temp_text_id = self.__canvas_ref.create_text(
                text_x_val,
                text_y_val,
                text=message,
                fill=text_color,
                font=font_definition,
                anchor=cast(AnchorLiteral, anchor_val),
                tags="_temp_guidance_tag"
            )

            text_bbox = self.__canvas_ref.bbox(temp_text_id)
            if not text_bbox:
                # Log warning if bounding box is not found
                logger.warning(self.__msg_mgr.get_message("L528").format(temp_text_id))
                self.__canvas_ref.delete(temp_text_id)
                return

            # Calculate background dimensions with proper padding
            x1_text, y1_text, x2_text, y2_text = text_bbox
            horizontal_padding = 8  # Increased padding for better readability
            vertical_padding = 4

            bg_x1 = float(x1_text - horizontal_padding)
            bg_y1 = float(y1_text - vertical_padding)
            bg_x2 = float(x2_text + horizontal_padding)
            bg_y2 = float(y2_text + vertical_padding)
            
            # Ensure background rectangle doesn't go outside canvas boundaries
            # This fixes the issue where the left border of the message appears outside the canvas
            if bg_x1 < 0:
                # Adjust bg_x1 to be at least 0 (canvas left edge)
                bg_x1 = 0.0
            
            # Delete temporary text
            self.__canvas_ref.delete(temp_text_id)

            # Create background rectangle with stipple for semi-transparency
            logger.debug(self.__msg_mgr.get_message("L540").format(f"Creating guidance background rectangle with tag: {self.ROTATION_GUIDANCE_TAG if is_rotation else self.GUIDANCE_TEXT_TAG}"))
            bg_id = self.__canvas_ref.create_rectangle(
                bg_x1, bg_y1, bg_x2, bg_y2,
                fill=bg_fill,
                outline=border_color,
                width=2,  # Thicker border for better visibility
                stipple=stipple_option, 
                tags=(self.ROTATION_GUIDANCE_TAG if is_rotation else self.GUIDANCE_TEXT_TAG,)
            )
            logger.debug(self.__msg_mgr.get_message("L540").format(f"Created background rectangle with ID: {bg_id}"))
            
            # Create actual text on top of background
            logger.debug(self.__msg_mgr.get_message("L540").format(f"Creating guidance text with message: '{message}'"))
            text_id = self.__canvas_ref.create_text(
                text_x_val,
                text_y_val,
                text=message,
                fill=text_color,
                font=font_definition,
                anchor=cast(AnchorLiteral, anchor_val),
                tags=(self.ROTATION_GUIDANCE_TAG if is_rotation else self.GUIDANCE_TEXT_TAG,)
            )
            logger.debug(self.__msg_mgr.get_message("L540").format(f"Created text with ID: {text_id}"))
            
            # Ensure text is on top of the background
            self.__canvas_ref.tag_raise(text_id, bg_id)
            
            # Store IDs of both background and text
            self.__guidance_text_id = (bg_id, text_id)
            self.__guidance_text_visible = True
            
            # For rotation mode, ensure the elements stay visible
            if is_rotation:
                self.__keep_rotation_elements_visible = True
                # Force canvas update to ensure immediate visibility
                self.__canvas_ref.update_idletasks()
            else:
                # For non-rotation guidance, set up auto-hide timer if needed
                hide_ms = int(3000)  # 3 seconds default display time
                try:
                    # Tkinter's after() should always return an integer timer ID
                    after_id = self.__canvas_ref.after(hide_ms, self.hide_guidance_text)
                    
                    # Strict type checking to ensure after_id is an integer
                    if isinstance(after_id, int):
                        self._hide_after_ids.append(after_id)
                        logger.debug(self.__msg_mgr.get_message("L540").format(f"Auto-hide timer set for guidance text: {after_id}"))
                    else:
                        # Log warning if after_id is not an integer
                        # Skipping invalid timer ID
                        logger.debug(self.__msg_mgr.get_message("L552", "Skipping invalid timer ID: {0}").format(after_id))
                except Exception as e:
                    # Log error if setting timer fails
                    logger.error(self.__msg_mgr.get_message("L562", "Error setting guidance text timer: {0}").format(e))
            
            # Log successful display of guidance text only when DEBUG_TIMER_LOGS is enabled
            if tool_settings.DEBUG_TIMER_LOGS:
                logger.debug(self.__msg_mgr.get_message("L540").format(f"Guidance text displayed successfully with IDs: {self.__guidance_text_id}, is_rotation: {is_rotation}"))
        except Exception as e:
            # Log error if showing guidance text fails
            logger.error(self.__msg_mgr.get_message("L521").format(str(e)))

    def show_notification(self, message: str, duration: float = 1.0, warning: bool = False) -> None:
        """Show a temporary notification message on the canvas.
        
        Args:
            message: The notification message to display
            duration: How long to display the message (in seconds)
            warning: Whether to show as a warning (red text on white background)
        """
        self.__cancel_all_timers()
        
        self.hide_notification()
        
        # Enhanced logging for notification display debugging
        logger.debug(self.__msg_mgr.get_message("L540").format(f"Attempting to show notification: '{message}' (duration: {duration}s, warning: {warning})"))

        if self.__canvas_ref and message: # Check if canvas_ref is not None and message is not empty
            assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
            try:
                self.__canvas_ref.update_idletasks()
                canvas_width = self.__canvas_ref.winfo_width()

                # Get font settings from user settings or use defaults
                font_family_val = self.__user_settings_mgr.get_setting("font_family", tool_settings.DEFAULT_FONT_FAMILY)
                font_size_val = self.__user_settings_mgr.get_setting("font_size", tool_settings.font_size)
                font_weight = "bold"  # Default font weight for notifications

                # Get colors from user settings or use defaults
                if warning:
                    text_color = self.__user_settings_mgr.get_setting("warning_text_color", "#FF0000") # Red for warnings
                    bg_fill = self.__user_settings_mgr.get_setting("warning_bg_color", "#FFFFCC") # Light yellow for warnings
                    border_color = self.__user_settings_mgr.get_setting("warning_border_color", "#FF0000") # Red border
                else:
                    text_color = self.__user_settings_mgr.get_setting("notification_text_color", "#000000") # Black for normal
                    bg_fill = self.__user_settings_mgr.get_setting("notification_bg_color", "#E6F2FF") # Light blue for normal
                    border_color = self.__user_settings_mgr.get_setting("notification_border_color", "#0066CC") # Blue border

                # Position notification at the top center of the canvas
                # Use viewport coordinates without scroll adjustment for fixed positioning
                
                # Calculate position in viewport coordinates
                text_x_val: float = float(canvas_width / 2)
                text_y_val: float = 30.0
                anchor = "n"
                
                # Ensure font components have explicit types for Mypy using cast
                font_family_str_notify = cast(str, font_family_val)
                font_size_int_notify = cast(int, font_size_val)
                font_weight_str_notify = cast(str, font_weight)

                # Define font as a string: "Family Size Style"
                font_definition_notify: str = f"{font_family_str_notify} {font_size_int_notify} {font_weight_str_notify}"
                
                # Create background first for proper layering
                # We'll adjust its size after creating the text
                temp_text_id = self.__canvas_ref.create_text(
                    text_x_val, 
                    text_y_val, 
                    text=message,
                    fill=text_color,
                    font=font_definition_notify,
                    anchor=cast(AnchorLiteral, anchor),
                    tags="_temp_notification_tag"
                )
                
                text_bbox = self.__canvas_ref.bbox(temp_text_id)
                if not text_bbox:
                    logger.warning(self.__msg_mgr.get_message("L529").format(temp_text_id))
                    self.__canvas_ref.delete(temp_text_id)
                    return
                    
                # Calculate background dimensions with proper padding
                x1_text, y1_text, x2_text, y2_text = text_bbox
                horizontal_padding = 10 # Increased padding for better readability
                vertical_padding = 6
                
                bg_x1: float = float(x1_text - horizontal_padding)
                bg_y1: float = float(y1_text - vertical_padding)
                bg_x2: float = float(x2_text + horizontal_padding)
                bg_y2: float = float(y2_text + vertical_padding)

                # Delete temporary text
                self.__canvas_ref.delete(temp_text_id)
                
                # Create actual background with rounded corners if supported
                bg_id = self.__canvas_ref.create_rectangle(
                    bg_x1, bg_y1, bg_x2, bg_y2,
                    fill=bg_fill,
                    outline=border_color,
                    width=2, # Thicker border for better visibility
                    tags="notification_tag"
                )
                
                # Create actual text on top of background
                text_id = self.__canvas_ref.create_text(
                    text_x_val, 
                    text_y_val, 
                    text=message,
                    fill=text_color,
                    font=font_definition_notify,
                    anchor=cast(AnchorLiteral, anchor),
                    tags="notification_tag"
                )
                
                # Ensure text is above background
                self.__canvas_ref.tag_raise(text_id, bg_id)
                
                # Ensure notification is always on top of all other elements
                self.__canvas_ref.tag_raise("notification_tag")
                # Force update to ensure immediate visibility
                self.__canvas_ref.update()
                
                # Store IDs for later reference
                self.__notification_text_id = (bg_id, text_id)
                self.__notification_visible = True

                # Set up auto-hide timer
                hide_ms = int(duration * 1000)
                # Force canvas update before setting timer to ensure notification is visible
                self.__canvas_ref.update_idletasks()
                after_id = self.__canvas_ref.after(hide_ms, self.hide_notification)
                # Ensure after_id is a valid integer before adding to the list
                if isinstance(after_id, int):
                    self._hide_after_ids.append(after_id)
                    logger.debug(self.__msg_mgr.get_message("L509").format(message, duration))
                else:
                    # Log warning if after_id is not an integer
                    # Skipping invalid timer ID
                    logger.debug(self.__msg_mgr.get_message("L552", "Skipping invalid timer ID: {0}").format(after_id))

            except Exception as e:
                # Log error when showing notification
                logger.error(self.__msg_mgr.get_message("L522").format(str(e)))
                
    # hide_notification method moved to line 1282

    def hide_guidance_text(self) -> None:
        """Hide the guidance text and its background from the canvas."""
        # Single log entry at the start with detailed information
        if self.__guidance_text_id:
            logger.debug(self.__msg_mgr.get_message("L540").format(f"Hiding guidance text with ID: {self.__guidance_text_id}"))
        else:
            # If there's no guidance text ID, it might be already hidden or never shown
            logger.debug(self.__msg_mgr.get_message("L540").format("Hiding guidance text (no active ID)"))
            return
        
        if self.__canvas_ref:
            assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
            
            # Track deletion results for summary logging
            deleted_ids = []
            errors = []
            
            if isinstance(self.__guidance_text_id, tuple):
                for item_id in self.__guidance_text_id:
                    if item_id: # Ensure item_id is not None
                        try:
                            self.__canvas_ref.delete(item_id)
                            deleted_ids.append(item_id)
                        except Exception as e:
                            errors.append(f"Error with ID {item_id}: {str(e)}")
                            logger.error(self.__msg_mgr.get_message("L521").format(f"Error deleting guidance text item {item_id}: {str(e)}"))
            elif isinstance(self.__guidance_text_id, int): # Check if it's a single int ID
                try:
                    self.__canvas_ref.delete(self.__guidance_text_id)
                    deleted_ids.append(self.__guidance_text_id)
                except Exception as e:
                    errors.append(f"Error with ID {self.__guidance_text_id}: {str(e)}")
                    logger.error(self.__msg_mgr.get_message("L521").format(f"Error deleting guidance text item {self.__guidance_text_id}: {str(e)}"))
            else:
                logger.warning(f"Unexpected type for __guidance_text_id: {type(self.__guidance_text_id)}")
            
            # Single summary log instead of multiple individual logs
            if deleted_ids:
                logger.debug(self.__msg_mgr.get_message("L540").format(f"Deleted guidance text items: {deleted_ids}"))

        # Reset state variables
        self.__guidance_text_id = None
        self.__guidance_text_visible = False

    def hide_notification(self) -> None:
        """Hide the notification message and its background from the canvas.
        
        This method cancels any active notification timers and removes notification
        elements from the canvas. It's called automatically after the notification
        duration expires or can be called manually to immediately hide a notification.
        """
        # Cancel all active notification timers
        for after_id in self._hide_after_ids:
            if self.__canvas_ref and after_id is not None: 
                assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
                # Check if after_id is a valid integer for after_cancel
                if not isinstance(after_id, int):
                    # Log warning for invalid timer ID type
                    # Skipping invalid timer ID
                    logger.debug(self.__msg_mgr.get_message("L552", "Skipping invalid timer ID: {0}").format(after_id))
                    continue
                    
                # Cast to int for internal use, but convert to string for after_cancel
                timer_id = cast(int, after_id)
                self.__canvas_ref.after_cancel(str(timer_id))
        self._hide_after_ids.clear()

        # Remove notification elements from canvas
        if self.__notification_visible and self.__notification_text_id and self.__canvas_ref:
            assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
            
            # Track deletion results for summary logging
            deleted_ids = []
            errors = []
            
            if isinstance(self.__notification_text_id, tuple):
                for item_id in self.__notification_text_id:
                    if item_id: # Ensure item_id is not None
                        try:
                            self.__canvas_ref.delete(item_id)
                            deleted_ids.append(item_id)
                        except Exception as e:
                            errors.append(f"Error with ID {item_id}: {str(e)}")
                            logger.error(self.__msg_mgr.get_message("L521").format(f"Error deleting notification item {item_id}: {str(e)}"))
            elif isinstance(self.__notification_text_id, int): # Check if it's a single int ID
                try:
                    self.__canvas_ref.delete(self.__notification_text_id)
                    deleted_ids.append(self.__notification_text_id)
                except Exception as e:
                    errors.append(f"Error with ID {self.__notification_text_id}: {str(e)}")
                    logger.error(self.__msg_mgr.get_message("L521").format(f"Error deleting notification item {self.__notification_text_id}: {str(e)}"))
            
            # Log summary of deletion operation
            if errors:
                logger.warning(self.__msg_mgr.get_message("L541").format(f"Deleted {len(deleted_ids)} notification items with {len(errors)} errors"))
            else:
                logger.debug(self.__msg_mgr.get_message("L540").format(f"Successfully deleted {len(deleted_ids)} notification items"))

        # Reset notification state
        self.__notification_text_id = None
        self.__notification_visible = False
        
        # Force canvas update to ensure notification is removed
        if self.__canvas_ref:
            self.__canvas_ref.update_idletasks()


    def _draw_shortcut_guide_on_canvas(self, title: str, content: str, auto_hide_delay: float = 5.0) -> None:
        """Draw shortcut guide with title and content on the canvas.
        
        Args:
            title: Title text for the shortcut guide
            content: Content text for the shortcut guide
            auto_hide_delay: Time in seconds before auto-hiding the guide
        """
        if self.__canvas_ref is None:
            logger.error(self.__msg_mgr.get_message("L527"))
            return
            
        # Clean up any existing shortcut guide
        self._remove_shortcut_guide_from_canvas()
        
        # Get canvas width for positioning
        canvas_width = self.__canvas_ref.winfo_width()
        
        # Get style settings from user settings
        padding = self.__user_settings_mgr.get_setting("ui_shortcut_guide_padding", 10)
        guide_width = self.__user_settings_mgr.get_setting("ui_shortcut_guide_width", 300)
        line_spacing = self.__user_settings_mgr.get_setting("ui_shortcut_guide_line_spacing", 5)
        title_color = self.__user_settings_mgr.get_setting("ui_shortcut_guide_title_color", "#FFFFFF")
        content_color = self.__user_settings_mgr.get_setting("ui_shortcut_guide_content_color", "#CCCCCC")
        bg_color = self.__user_settings_mgr.get_setting("ui_shortcut_guide_bg_color", "#333333")
        outline_color = self.__user_settings_mgr.get_setting("ui_shortcut_guide_outline_color", "#666666")
        outline_width = self.__user_settings_mgr.get_setting("ui_shortcut_guide_outline_width", 1)
        use_animation = self.__user_settings_mgr.get_setting("ui_shortcut_guide_animation", True)
        
        # Calculate position (top right corner with padding)
        x_pos = canvas_width - guide_width - padding
        y_pos = padding
        
        # Create temporary text items to calculate heights
        temp_title_id = self.__canvas_ref.create_text(
            0, 0,  # Position doesn't matter for measurement
            text=title,
            font=("Arial", 12, "bold"),
            fill=title_color,
            anchor="nw"
        )
        title_bbox = self.__canvas_ref.bbox(temp_title_id)
        title_height = title_bbox[3] - title_bbox[1]
        
        # Calculate content height by creating a temporary text item
        temp_content_id = self.__canvas_ref.create_text(
            0, 0,  # Position doesn't matter for measurement
            text=content,
            font=("Arial", 10),
            fill=content_color,
            anchor="nw",
            width=guide_width - (padding * 2)  # Wrap text within guide width
        )
        content_bbox = self.__canvas_ref.bbox(temp_content_id)
        content_height = content_bbox[3] - content_bbox[1]
        
        # Delete temporary items
        self.__canvas_ref.delete(temp_title_id)
        self.__canvas_ref.delete(temp_content_id)
        
        # Calculate total height
        total_height = padding + title_height + line_spacing + content_height + padding
        
        # Create background rectangle
        bg_id = self.__canvas_ref.create_rectangle(
            x_pos, y_pos,
            x_pos + guide_width, y_pos + total_height,
            fill=bg_color,
            outline=outline_color,
            width=outline_width,
            tags=(self.SHORTCUT_GUIDE_TAG,)
        )
        
        # Create title text
        title_id = self.__canvas_ref.create_text(
            x_pos + padding, y_pos + padding,
            text=title,
            font=("Arial", 12, "bold"),
            fill=title_color,
            anchor="nw",
            tags=(self.SHORTCUT_GUIDE_TAG,)
        )
        
        # Create content text
        content_id = self.__canvas_ref.create_text(
            x_pos + padding, y_pos + padding + title_height + line_spacing,
            text=content,
            font=("Arial", 10),
            fill=content_color,
            anchor="nw",
            width=guide_width - (padding * 2),  # Wrap text within guide width
            tags=(self.SHORTCUT_GUIDE_TAG,)
        )
        
        # Store IDs for later removal
        self.__shortcut_guide_ids = [bg_id, title_id, content_id]
        
        # Apply animation if enabled
        if use_animation:
            # Start with transparent and fade in
            for item_id in self.__shortcut_guide_ids:
                self.__canvas_ref.itemconfig(item_id, state="hidden")
            
            # Schedule fade-in animation
            self.__canvas_ref.after(50, self.__fade_in_shortcut_guide)
        
        # Schedule auto-hide if delay is positive
        if auto_hide_delay > 0:
            self.__auto_hide_timer = self.__canvas_ref.after(
                int(auto_hide_delay * 1000),
                lambda: self._remove_shortcut_guide_from_canvas()
            )
    
    def _remove_shortcut_guide_from_canvas(self) -> None:
        """Remove shortcut guide items from canvas."""
        if self.__canvas_ref is None:
            return
            
        # Cancel auto-hide timer if active
        if self.__auto_hide_timer is not None:
            self.__canvas_ref.after_cancel(self.__auto_hide_timer)
            self.__auto_hide_timer = None
        
        # Delete all shortcut guide items
        self.__canvas_ref.delete(self.SHORTCUT_GUIDE_TAG)
        
        # Clear stored IDs
        self.__shortcut_guide_ids = []
        
        # Update visibility flag
        self.__shortcut_guide_visible = False
    
    def __fade_in_shortcut_guide(self, alpha: float = 0.0) -> None:
        """Fade in the shortcut guide items.
        
        Args:
            alpha: Current opacity level (0.0 to 1.0)
        """
        if self.__canvas_ref is None or not self.__shortcut_guide_ids:
            return
            
        # Show items if they're hidden
        for item_id in self.__shortcut_guide_ids:
            self.__canvas_ref.itemconfig(item_id, state="normal")
        
        # Increase alpha
        alpha += 0.1
        
        if alpha < 1.0:
            # Schedule next fade step
            self.__canvas_ref.after(50, lambda: self.__fade_in_shortcut_guide(alpha))
    
    # on_canvas_resize method is implemented below (around line 1719)
    
    def toggle_shortcut_guide(self, event: Optional[tk.Event] = None, force_show: Optional[bool] = None) -> str | None:
        """Toggle the visibility of the shortcut guide.

        Args:
            event (Optional[tk.Event]): The event that triggered the toggle. Default is None.
            force_show (Optional[bool]): If True, show the guide. If False, hide it.
                If None, toggle current state. Default is None.
                
        Returns:
            str | None: String to prevent default handling or None.
        """
        self.__cancel_all_timers()

        # Save rotation mode state to restore it after toggling
        was_in_rotation_mode = self.__rotation_mode

        if force_show is True:
            if not self.__shortcut_guide_visible:
                title = self.__msg_mgr.get_message("M050") # Shortcut Guide Title
                content = self.__msg_mgr.get_message("M049") # Shortcut Guide Content
                # Draw shortcut guide directly on canvas to ensure it's visible
                # Set auto-hide delay to 5 seconds for forced show
                self._draw_shortcut_guide_on_canvas(title, content, auto_hide_delay=5.0)
                # Update visibility flag to track state correctly
                self.__shortcut_guide_visible = True
                # When force_show is used, we don't update __user_toggled_shortcut_guide
                # as this is not a direct user toggle action but a programmatic state restoration.
                logger.debug("Shortcut guide forced ON with 5-second auto-hide.")
        elif force_show is False:
            if self.__shortcut_guide_visible:
                self._remove_shortcut_guide_from_canvas()
                # Update visibility flag to track state correctly
                self.__shortcut_guide_visible = False
                # Similarly, don't update __user_toggled_shortcut_guide for forced actions.
                logger.debug("Shortcut guide forced OFF.")
        else: # Toggle behavior (force_show is None) - This is a direct user action
            if self.__shortcut_guide_visible:
                self._remove_shortcut_guide_from_canvas()
                # Update visibility flag to track state correctly
                self.__shortcut_guide_visible = False
                self.__user_toggled_shortcut_guide = True # User explicitly hid it
                logger.debug("Shortcut guide toggled OFF by user.")
            else:
                title = self.__msg_mgr.get_message("M050") # Shortcut Guide Title
                content = self.__msg_mgr.get_message("M049") # Shortcut Guide Content
                # Draw shortcut guide directly on canvas to ensure it's visible
                # For user-toggled guide, set auto-hide delay to 10 seconds
                self._draw_shortcut_guide_on_canvas(title, content, auto_hide_delay=10.0)
                # Update visibility flag to track state correctly
                self.__shortcut_guide_visible = True
                self.__user_toggled_shortcut_guide = True # User explicitly showed it
                logger.debug("Shortcut guide toggled ON by user with 10-second auto-hide.")
                
        # Restore rotation mode guidance if needed
        if was_in_rotation_mode and self.__canvas_ref:
            self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation Mode: Drag to rotate.
            
        return "break"
        

            
    def on_canvas_resize(self, event: Optional[tk.Event] = None) -> None:
        """Handle canvas resize events.
        
        This method is called when the canvas is resized. It redraws the shortcut guide
        if it is currently visible to ensure it remains properly positioned.
        
        Args:
            event (Optional[tk.Event]): The resize event. Default is None.
        """
        # Only redraw if shortcut guide is visible
        if self.__shortcut_guide_visible and self.__canvas_ref:
            # Store current auto-hide settings
            auto_hide_delay = 0  # Default to no auto-hide when redrawing due to resize
            
            # Get the current title and content
            title = self.__msg_mgr.get_message("M050")  # Shortcut Guide Title
            content = self.__msg_mgr.get_message("M049")  # Shortcut Guide Content
            
            # Redraw the shortcut guide with the same content but no auto-hide
            self._draw_shortcut_guide_on_canvas(title, content, auto_hide_delay=auto_hide_delay)
            
            logger.debug("Shortcut guide redrawn after canvas resize.")
            
        # If in rotation mode, redraw the rotation guidance
        if self.__rotation_mode and self.__canvas_ref:
            self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)  # Rotation Mode: Drag to rotate.

    def __cancel_all_timers(self) -> None:
        """Cancel all pending timers to prevent UI flicker and memory leaks.
        
        This method cancels all timers stored in _hide_after_ids list and the Ctrl check timer
        to prevent UI conflicts when multiple shortcuts are used in rapid succession.
        """
        # Track if any timers were actually cancelled to avoid excessive logging
        timers_cancelled = False
        
        # Cancel all after IDs stored in _hide_after_ids list
        if self._hide_after_ids:
            # Create a copy of the list to avoid modification during iteration
            hide_after_ids_copy = self._hide_after_ids.copy()
            # Clear the original list first to prevent any new timers from being added during cancellation
            self._hide_after_ids.clear()
            
            for after_id in hide_after_ids_copy:
                if self.__canvas_ref and after_id is not None: 
                    try:
                        # Skip if after_id is not a valid integer for after_cancel
                        # Tkinter's after_cancel requires an integer ID
                        if not isinstance(after_id, int):
                            # Skip invalid timer ID silently to reduce log spam
                            # Only log at debug level if DEBUG_TIMER_LOGS is True
                            if getattr(tool_settings, 'DEBUG_TIMER_LOGS', False):
                                # Skipping invalid timer ID
                                logger.debug(self.__msg_mgr.get_message("L552").format(after_id))
                            continue
                            
                        # Convert timer ID to string as after_cancel expects a string
                        self.__canvas_ref.after_cancel(str(after_id))
                        timers_cancelled = True
                    except Exception as e:
                        # Use L553 message code for timer cancellation errors
                        # Error cancelling timer
                        logger.debug(self.__msg_mgr.get_message("L553").format(e))
        
        # Cancel Ctrl check timer if it exists
        if self.__ctrl_check_timer_id is not None and self.__canvas_ref:
            try:
                # Check if timer ID is valid for after_cancel (must be int)
                if not isinstance(self.__ctrl_check_timer_id, int):
                    # Skipping invalid timer ID
                    logger.debug(self.__msg_mgr.get_message("L552").format(self.__ctrl_check_timer_id))
                else:
                    # Convert timer ID to string as after_cancel expects a string
                    self.__canvas_ref.after_cancel(str(self.__ctrl_check_timer_id))
                    self.__ctrl_check_timer_id = None
                    timers_cancelled = True
            except Exception as e:
                # Error cancelling timer
                logger.debug(self.__msg_mgr.get_message("L553").format(e))
        
        # Cancel shortcut guide auto-hide timer if it exists
        if hasattr(self, "__shortcut_guide_timer") and self.__shortcut_guide_timer:
            try:
                self.__shortcut_guide_timer.cancel()
                self.__shortcut_guide_timer = None
                timers_cancelled = True
                logger.debug(self.__msg_mgr.get_message("L554", "Shortcut guide auto-hide timer cancelled."))
            except Exception as e:
                # Error cancelling timer
                logger.debug(self.__msg_mgr.get_message("L553").format(e))
        
        # Only log if we actually cancelled something and it's a shortcut guide timer
        # This reduces log spam when multiple shortcuts are used in succession
        if timers_cancelled and hasattr(self, "__shortcut_guide_timer") and self.__shortcut_guide_timer is None:
            logger.debug(self.__msg_mgr.get_message("L555", "All timers cancelled."))
            
    def __check_operation_throttle(self) -> bool:
        """Check if enough time has passed since the last operation.
        
        This method implements a cooldown mechanism to prevent operations from being
        executed too rapidly in succession, which can cause UI conflicts.
        
        Returns:
            bool: True if operation is allowed, False if it should be throttled.
        """
        current_time = time.time()
        time_since_last_op = current_time - self.__last_operation_time
        
        # If cooldown period has not passed, throttle the operation
        if time_since_last_op < self.__operation_cooldown:
            # Log throttling event with remaining cooldown time
            remaining_ms = int((self.__operation_cooldown - time_since_last_op) * 1000)
            logger.debug(f"Operation throttled. Please wait {remaining_ms}ms before next operation.")
            return False
            
        # Update last operation time and allow the operation
        self.__last_operation_time = current_time
        return True

    def __exit_rotation_mode(self, event: Optional[tk.Event] = None) -> None:
        """Exit rotation mode and clean up UI elements.
        
        This method handles the cleanup when exiting rotation mode.
        It includes a time-based mechanism to prevent duplicate log messages when called
        from multiple event handlers in close succession.
        
        Args:
            event (Optional[tk.Event]): Event that triggered the exit. Default is None.
        """
        # Exit early if not in rotation mode
        if not self.__rotation_mode:
            return
            
        # Use instance variable to track recent exits to prevent duplicate logs
        # This is needed because both on_key_release and on_mouse_up might call this
        # method in close succession
        current_time = time.time()
        time_since_last_exit = current_time - self.__last_rotation_exit_time
        
        # If we've exited rotation mode very recently (within 200ms), skip the log message
        log_exit = time_since_last_exit >= 0.2  # 200ms threshold
        
        # Always update the last exit time
        self.__last_rotation_exit_time = current_time

        # Cancel all pending timers first to prevent UI flicker
        self.__cancel_all_timers()
        
        # Hide all rotation-related UI elements
        self.hide_feedback_circle()
        self.hide_guidance_text()
        self._remove_shortcut_guide_from_canvas()
        
        # Reset rotation mode flags
        self.__rotation_mode = False
        self.__rotation_active = False
        self.__keep_rotation_elements_visible = False
        if hasattr(self, '_MouseEventHandler__rotation_start_angle'):
            del self.__rotation_start_angle
            
        # Log rotation mode exit with appropriate message code only if not recently logged
        # L516 is the existing message code for rotation mode exit
        if log_exit:
            logger.debug(self.__msg_mgr.get_message("L516"))

    def cleanup(self) -> None:
        """Clean up resources, timers, and UI elements."""
        # Log the start of cleanup process
        logger.debug(self.__msg_mgr.get_message("L543")) # L543: [MOUSE] MouseEventHandler cleanup initiated
        self.__cancel_all_timers()
        self.hide_feedback_circle()
        self.hide_guidance_text()
        self.hide_notification()
        self._remove_shortcut_guide_from_canvas() # Ensure shortcut guide is removed

        # Reset core state variables related to mouse interaction
        self.__rotation_mode = False
        self.__rotation_active = False
        self.__dragging = False
        self.__keep_rotation_elements_visible = False # Explicitly reset this flag
        # Log the completion of cleanup process
        logger.debug(self.__msg_mgr.get_message("L544")) # L544: [MOUSE] MouseEventHandler cleanup completed

    def on_mouse_down(self, event: tk.Event) -> Optional[str]:
        """Handle mouse button press event.
        
        Activates rotation mode on Ctrl+Click, showing relevant UI feedback.
        
        Args:
            event (tk.Event): Mouse button press event.
            
        Returns:
            Optional[str]: "break" to prevent default handling, or None if canvas_ref is not set.
        """
        # Log mouse down event with coordinates
        logger.debug(self.__msg_mgr.get_message("L512").format(event.x, event.y)) # L512: Mouse down at ({}, {})
        
        # Ensure canvas reference is available
        if self.__canvas_ref is None:
            # Log missing canvas reference
            logger.warning(self.__msg_mgr.get_message("L527")) # L527: Canvas reference is not set in MouseEventHandler.
            return None

        assert self.__canvas_ref is not None # Ensure canvas_ref is not None for Mypy
        # Store last mouse position in canvas coordinates
        raw_canvas_x = self.__canvas_ref.canvasx(event.x)
        raw_canvas_y = self.__canvas_ref.canvasy(event.y)
        
        # Get canvas dimensions for boundary checking
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        
        # Ensure coordinates are within canvas bounds
        # This prevents issues at canvas edges and corners
        self.__last_mouse_x = max(0, min(raw_canvas_x, canvas_width))
        self.__last_mouse_y = max(0, min(raw_canvas_y, canvas_height))
        
        # Initialize rotation mouse position tracking
        self.__last_rotation_mouse_x = self.__last_mouse_x
        self.__last_rotation_mouse_y = self.__last_mouse_y
        # Set dragging flag to true, indicating a potential drag operation
        self.__dragging = True

        # Check if Ctrl key was pressed during the mouse click
        ctrl_pressed = (cast(int, event.state) & 0x4) != 0

        if ctrl_pressed:
            # Ctrl+Click: Enter or re-affirm rotation mode
            logger.debug(self.__msg_mgr.get_message("L540").format("Ctrl+Click detected, entering rotation mode"))
            
            # Clear any existing rotation-related UI elements before drawing new ones
            logger.debug(self.__msg_mgr.get_message("L540").format(f"Deleting UI elements with tags: {self.ROTATION_CENTER_TAG}, {self.GUIDANCE_TEXT_TAG}, {self.SHORTCUT_GUIDE_TAG}"))
            
            # First hide existing guidance text and notification to ensure proper cleanup
            self.hide_guidance_text()
            self.hide_notification()
            
            # Then delete tags from canvas
            self.__canvas_ref.delete(self.ROTATION_CENTER_TAG)
            self.__canvas_ref.delete(self.ROTATION_GUIDANCE_TAG)
            self.__canvas_ref.delete(self.SHORTCUT_GUIDE_TAG)
            
            # Force canvas update to ensure UI is cleared before drawing new elements
            self.__canvas_ref.update_idletasks()
            
            # Get click coordinates on the canvas
            canvas_click_x = self.__canvas_ref.canvasx(event.x)
            canvas_click_y = self.__canvas_ref.canvasy(event.y)
            
            # Enter rotation mode with explicit flags
            self.__rotation_mode = True
            self.__keep_rotation_elements_visible = True  # Ensure elements stay visible
            self.__rotation_center_x = canvas_click_x
            self.__rotation_center_y = canvas_click_y
            self.__rotation_start_time = time.time()
            self.__rotation_active = False
            logger.debug(self.__msg_mgr.get_message("L540").format("Rotation mode activated with keep_visible flag"))
            
            # Show feedback circle at rotation center
            self.draw_feedback_circle(canvas_click_x, canvas_click_y, is_rotating=True)
            
            # Cancel any existing timers to prevent conflicts
            self.__cancel_all_timers()
            
            # Ensure the canvas is updated before drawing new elements
            self.__canvas_ref.update()
            
            # First draw shortcut guide (fixed position in viewport)
            # This ensures it appears at the correct position without scroll adjustment
            logger.debug(self.__msg_mgr.get_message("L540").format("Drawing shortcut guide on canvas"))
            self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049')) # M050: Rotation Shortcuts, M049: Ctrl+R: RotR, Ctrl+L: RotL, Esc: Exit
            
            # Force update to ensure shortcut guide is displayed
            self.__canvas_ref.update_idletasks()
            
            # Ensure shortcut guide is visible by raising it to the top
            self.__canvas_ref.tag_raise(self.SHORTCUT_GUIDE_TAG)
            
            # Then show rotation guidance text with explicit rotation flag
            logger.debug(self.__msg_mgr.get_message("L540").format("Showing rotation guidance text"))
            self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True) # M042: Rotation Mode: Drag to rotate.
            
            # Ensure guidance text is on top
            if self.__guidance_text_id and isinstance(self.__guidance_text_id, tuple) and len(self.__guidance_text_id) == 2:
                # Raise guidance text to ensure it's visible above other elements
                self.__canvas_ref.tag_raise(self.__guidance_text_id[0])  # Background
                self.__canvas_ref.tag_raise(self.__guidance_text_id[1])  # Text
            
            # Force update again after drawing shortcut guide
            self.__canvas_ref.update_idletasks()
            
            # Display central notification for rotation mode
            logger.debug(self.__msg_mgr.get_message("L540").format("Showing notification"))
            self.show_notification(self.__msg_mgr.get_message('M042'), duration=1.0)  # Longer duration for better visibility
            
            self.__keep_rotation_elements_visible = True
            return "break"
        else:
            # Click without Ctrl
            if self.__rotation_mode and not self.__rotation_active:
                # If in rotation mode (e.g. Ctrl was pressed and released without click)
                # and then a click happens without Ctrl, exit rotation mode.
                self.__exit_rotation_mode(event) # Exit rotation mode on non-Ctrl click if already in passive rotation mode
            
            # For non-Ctrl clicks, allow default handling
            return None


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
            # Log the missing canvas reference with L559 message code
            logger.warning(self.__msg_mgr.get_message("L559")) # L559: [MOUSE] Canvas reference is not set in MouseEventHandler
            return
            
        # Get raw canvas coordinates
        raw_canvas_x = self.__canvas_ref.canvasx(event.x)
        raw_canvas_y = self.__canvas_ref.canvasy(event.y)
        
        # Get canvas dimensions for boundary checking
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        
        # Ensure coordinates are within canvas bounds
        # This prevents issues at canvas edges and corners
        current_x = max(0, min(raw_canvas_x, canvas_width))
        current_y = max(0, min(raw_canvas_y, canvas_height))
        
        # Calculate movement delta
        delta_x = current_x - self.__last_mouse_x
        delta_y = current_y - self.__last_mouse_y

        # Check if in rotation mode
        if self.__rotation_mode:
            # Always ensure the feedback circle is drawn at the original rotation center
            # This prevents the red dot from moving during any mouse movement
            if self.__canvas_ref:
                # Redraw the feedback circle at the fixed rotation center coordinates
                # This ensures the red dot stays in place even before rotation is activated
                self.draw_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                
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
                    
                    # Log that rotation has been activated
                    logger.debug(self.__msg_mgr.get_message("L540").format("Rotation activated after threshold distance"))
                    
                    # Ensure the feedback circle is visible and properly positioned
                    if self.__canvas_ref:
                        # Raise the rotation center tag to ensure it's visible
                        self.__canvas_ref.tag_raise(self.ROTATION_CENTER_TAG)
            
            # If rotation is active, calculate angle and rotate
            if self.__rotation_active:
                # Calculate angle from center to current position
                # Use rotation center as the pivot point for all angle calculations
                current_angle = math.atan2(current_y - self.__rotation_center_y,
                                          current_x - self.__rotation_center_x)
                
                # Calculate angle from center to previous position using rotation-specific tracking variables
                # This ensures consistent angle calculation regardless of other mouse movements
                prev_angle = math.atan2(self.__last_rotation_mouse_y - self.__rotation_center_y,
                                       self.__last_rotation_mouse_x - self.__rotation_center_x)
                
                # Calculate angle difference in degrees
                # This is the amount we need to rotate by in this frame
                angle_diff = math.degrees(current_angle - prev_angle)
                
                # Apply smoothing to prevent jitter
                if abs(angle_diff) > 0.05:  # Threshold to prevent minor jitter
                    # Strictly limit angle change to ±1° per frame for smooth rotation
                    # Clamp the angle_diff value between -1.0 and 1.0
                    if abs(angle_diff) > 1.0:
                        angle_diff = 1.0 if angle_diff > 0 else -1.0
                    
                    # Apply rotation
                    self.__rotate_by_angle(angle_diff)
                    
                    # Calculate total rotation from start for display
                    # Ensure __rotation_start_angle is available
                    if hasattr(self, '_MouseEventHandler__rotation_start_angle'):
                        total_angle_change = math.degrees(current_angle - self.__rotation_start_angle)
                        total_angle_change = round(total_angle_change, 1)  # Round for display
                    else: # Fallback if start angle wasn't set (should not happen if logic is correct)
                        total_angle_change = 0.0
                    
                    # Update display
                    self.__on_transform_update()
                    
                    # Show rotation feedback with current angle - always use the original rotation center
                    # This ensures the red dot stays fixed at the rotation center point
                    # Redraw the feedback circle to ensure it remains visible during rotation
                    self.draw_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                    
                    # Update guidance text with current rotation angle
                    self.show_guidance_text(self.__msg_mgr.get_message('M043').format(total_angle_change), is_rotation=True)
                    
                    # Force canvas update to ensure feedback circle is visible at the correct position
                    if self.__canvas_ref:
                        # Ensure the feedback circle is always on top
                        self.__canvas_ref.tag_raise(self.ROTATION_CENTER_TAG)
                        self.__canvas_ref.update_idletasks()
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
        
        # Always update last mouse position for general tracking
        self.__last_mouse_x = current_x
        self.__last_mouse_y = current_y
        
        # Update rotation-specific mouse position only when in rotation mode
        # This prevents the red dot from moving during rotation
        if self.__rotation_mode and self.__rotation_active:
            # Update rotation-specific last position for angle calculation
            self.__last_rotation_mouse_x = current_x
            self.__last_rotation_mouse_y = current_y
        
        # Log mouse drag with throttling to avoid excessive logs
        if self._transform_log_throttle.should_log(key="mouse_drag"):
            logger.debug(self.__msg_mgr.get_message("L513").format(event.x, event.y, delta_x, delta_y))
    
    def on_mouse_press(self, event: tk.Event) -> Optional[str]:
        """Handle mouse button press event (alias for on_mouse_down).
        
        This method serves as an alias for on_mouse_down to maintain compatibility
        with event bindings in the UI layer.
        
        Args:
            event: Mouse button press event
            
        Returns:
            String to prevent default handling
        """
        return self.on_mouse_down(event)
    
    def on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release event.
        
        Args:
            event: Mouse button release event
        """
        if self.__canvas_ref is None:
            logger.warning(self.__msg_mgr.get_message("L528")) # L528: Canvas reference is not set in MouseEventHandler.on_mouse_up.
            return
        assert self.__canvas_ref is not None

        # Update last mouse position to prevent angle calculation drift using canvas coordinates
        if self.__canvas_ref is not None:
            # Get raw canvas coordinates
            raw_canvas_x = self.__canvas_ref.canvasx(event.x)
            raw_canvas_y = self.__canvas_ref.canvasy(event.y)
            
            # Get canvas dimensions for boundary checking
            canvas_width = self.__canvas_ref.winfo_width()
            canvas_height = self.__canvas_ref.winfo_height()
            
            # Ensure coordinates are within canvas bounds
            # This prevents issues at canvas edges and corners
            self.__last_mouse_x = max(0, min(raw_canvas_x, canvas_width))
            self.__last_mouse_y = max(0, min(raw_canvas_y, canvas_height))
        
        # Reset dragging flag
        self.__dragging = False
        
        # Check if we were in rotation mode
        if self.__rotation_mode:
            # Check if Ctrl key is still pressed
            ctrl_pressed = False
            if hasattr(event, 'state') and isinstance(event.state, int):
                ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is Ctrl key state
            
            if not ctrl_pressed:
                # If Ctrl key is NOT pressed upon mouse up, it means the user intends to potentially
                # release the rotation mode when the Ctrl key is physically released.
                # We set __keep_rotation_elements_visible to False here. The actual exit
                # will be handled by on_key_release when the Control key up event is detected.
                self.__keep_rotation_elements_visible = False
                # If Ctrl is not pressed on mouse up while in rotation mode, exit rotation mode immediately.
                self.__exit_rotation_mode(event)
            # If Ctrl IS still pressed, __keep_rotation_elements_visible remains True (set in on_mouse_down/drag),
            # allowing the user to release the mouse button, move the mouse, and then press the mouse button again
            # to continue rotating from the same center without UI flickering.

        # Log mouse up event
        logger.debug(self.__msg_mgr.get_message("L514").format(event.x, event.y))
        
    def on_key_press(self, event: tk.Event) -> Optional[str]:
        """Handle keyboard press events.
        
        Args:
            event: Keyboard event
            
        Returns:
            String "break" to prevent default handling, or None to allow it.
        """
        # Ensure event has necessary attributes for key processing
        if not (hasattr(event, 'keysym') and hasattr(event, 'state') and isinstance(event.state, int)):
            return None

        ctrl_pressed = (event.state & 0x4) != 0  # 0x4 is the Ctrl modifier bit
        shift_pressed = (event.state & 0x1) != 0 # 0x1 is the Shift modifier bit

        # If Ctrl key is pressed
        if ctrl_pressed:
            # Check if a non-modifier key was part of the event (e.g., 'r' in Ctrl+R)
            if self.__is_other_key_pressed(event):
                key_sym_lower = event.keysym.lower()

                if key_sym_lower == 'r':
                    # Check operation throttling to prevent rapid consecutive operations
                    if not self.__check_operation_throttle():
                        # If throttled, show notification and skip operation
                        if self.__canvas_ref:
                            # Show throttling notification when operations are too frequent
                            self.show_notification(self.__msg_mgr.get_message('M056'), 0.3, warning=True)
                        return "break"
                    
                    self.__cancel_all_timers() # Cancel previous timers
                    # Hide feedback circle to prevent red dot display during shortcut use
                    self.hide_feedback_circle()
                    result = self.on_rotate_right(event)
                    
                    # Show notification message for right rotation
                    if self.__canvas_ref:
                        self.show_notification(self.__msg_mgr.get_message('M044'), 0.5, warning=False)
                    
                    # Show rotation mode message if in rotation mode
                    if self.__rotation_mode and self.__canvas_ref:
                        self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
                    
                    # Draw shortcut guide
                    self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
                        
                    return result if result is not None else "break"
                elif key_sym_lower == 'l':
                    # Check operation throttling to prevent rapid consecutive operations
                    if not self.__check_operation_throttle():
                        # If throttled, show notification and skip operation
                        if self.__canvas_ref:
                            # Show throttling notification when operations are too frequent
                            self.show_notification(self.__msg_mgr.get_message('M056'), 0.3, warning=True)
                        return "break"
                    
                    self.__cancel_all_timers() # Cancel previous timers
                    # Hide feedback circle to prevent red dot display during shortcut use
                    self.hide_feedback_circle()
                    result = self.on_rotate_left(event)
                    
                    # Show notification message for left rotation
                    if self.__canvas_ref:
                        self.show_notification(self.__msg_mgr.get_message('M045'), 0.5, warning=False)
                    
                    # Show rotation mode message if in rotation mode
                    if self.__rotation_mode and self.__canvas_ref:
                        self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
                    
                    # Draw shortcut guide
                    self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
                        
                    return result if result is not None else "break"
                elif key_sym_lower == 'v':
                    # Check operation throttling to prevent rapid consecutive operations
                    if not self.__check_operation_throttle():
                        # If throttled, show notification and skip operation
                        if self.__canvas_ref:
                            # Show throttling notification when operations are too frequent
                            self.show_notification(self.__msg_mgr.get_message('M056'), 0.3, warning=True)
                        return "break"
                    
                    # Properly handle Ctrl+V for vertical flip
                    self.__cancel_all_timers() # Cancel previous timers
                    self.hide_feedback_circle() # Hide feedback for immediate flip
                    
                    # Call vertical flip handler which handles all the logic
                    result = self.on_flip_vertical(event)
                    
                    # Show notification message for vertical flip
                    if self.__canvas_ref:
                        self.show_notification(self.__msg_mgr.get_message('M046'), 0.5, warning=False)
                    
                    # Draw shortcut guide
                    self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
                    
                    # Ensure rotation guidance is shown if in rotation mode
                    if self.__rotation_mode and self.__canvas_ref:
                        self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
                        
                    return result if result is not None else "break"
                elif key_sym_lower == 'h':
                    # Properly handle Ctrl+H for horizontal flip
                    self.__cancel_all_timers() # Cancel previous timers
                    self.hide_feedback_circle() # Hide feedback for immediate flip
                    
                    # Call horizontal flip handler which handles all the logic
                    result = self.on_flip_horizontal(event)
                    
                    # Show notification message for horizontal flip
                    if self.__canvas_ref:
                        self.show_notification(self.__msg_mgr.get_message('M047'), 0.5, warning=False)
                    
                    # Draw shortcut guide
                    self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
                    
                    # Ensure rotation guidance is shown if in rotation mode
                    if self.__rotation_mode and self.__canvas_ref:
                        self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
                        
                    return result if result is not None else "break"
                elif key_sym_lower == 'b':
                    # Cancel all timers to prevent UI conflicts
                    self.__cancel_all_timers()
                    
                    # Clear UI elements for clean reset
                    if self.__canvas_ref:
                        self.hide_feedback_circle()
                        self.hide_guidance_text()
                        self.hide_notification()
                    
                    # Reset transformations for all visible layers
                    for layer_id, visible in self.__visible_layers.items():
                        if not visible:
                            continue
                            
                        if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                            # Reset to default values: no rotation (0), centered (0,0), normal scale (1.0)
                            self.__layer_transform_data[layer_id][self.__current_page_index] = (0.0, 0.0, 0.0, 1.0)
                    
                    # Update display
                    self.__on_transform_update()
                    
                    # Show notification with reset message
                    self.show_notification(self.__msg_mgr.get_message('M048'), 0.5, warning=False) # Reset notification
                    
                    # Draw shortcut guide to ensure it's visible after reset
                    self._draw_shortcut_guide_on_canvas(self.__msg_mgr.get_message('M050'), self.__msg_mgr.get_message('M049'))
                    return "break"
                # Handle Ctrl + ? (Ctrl + Shift + /)
                # Support various keyboard layouts including US and Japanese keyboards
                # US keyboard: Ctrl+Shift+/ (keysym='slash' with shift_pressed=True)
                # Japanese keyboard: may report as 'question' directly or other variants
                elif (event.keysym in ('slash', 'question', 'questiondown', 'question_mark') and shift_pressed) or \
                     (event.keysym == 'question' or event.char == '?'):
                    self.__cancel_all_timers() # Cancel previous timers
                    
                    # Toggle the shortcut guide visibility with force_show=None for explicit toggle behavior
                    # This ensures the toggle behavior works as expected with the auto-hide timer
                    self.toggle_shortcut_guide(event, force_show=None)
                    
                    # Show appropriate notification based on current state
                    if self.__shortcut_guide_visible:
                        # Guide is now visible - show notification
                        shortcut_guide_msg = self.__msg_mgr.get_message('M049') # Shortcut guide content
                        if shortcut_guide_msg:
                            # Show first line as notification
                            first_line = shortcut_guide_msg.split('\n')[0] if '\n' in shortcut_guide_msg else shortcut_guide_msg
                            self.show_notification(first_line, duration=1.0)
                    else:
                        # Guide was hidden - show notification
                        self.show_notification(self.__msg_mgr.get_message('M051', "Shortcut guide hidden"), duration=1.0)
                    
                    # If in rotation mode, ensure rotation guidance is shown
                    if self.__rotation_mode and self.__canvas_ref:
                        self.show_guidance_text(self.__msg_mgr.get_message('M042'), is_rotation=True)
                        
                    return "break"
                # If Ctrl is pressed with another key not defined as a shortcut, do nothing here,
                # allowing rotation mode to potentially be used with mouse interaction if already active.
                # No 'return "break"' here, let it fall through.

            # Else, if Ctrl was pressed but __is_other_key_pressed is false, it means
            # the event.keysym was likely 'Control_L' or 'Control_R' (Ctrl key itself).
            else:
                if not self.__rotation_mode:
                    self.__rotation_mode = True
                    # UI elements (dot, guidance) are NOT shown here.
                    # They are shown when Ctrl + MouseDown occurs.
                    # Use L540 with rotation center coordinates for rotation mode activation log
                    # L540: "[DEBUG] {0}"
                    logger.debug(self.__msg_mgr.get_message("L540").format(f"Rotation mode activated at coordinates: ({self.__rotation_center_x}, {self.__rotation_center_y})"))
                # It can be useful to return "break" here to prevent Tkinter's default
                # processing of a lone Ctrl press if it causes unwanted behavior (e.g., focus changes).
                return "break"
        return None # Allow default handling for other keys or unhandled combinations
        
    def on_key_release(self, event: tk.Event) -> None:
        """Handle keyboard release events.

        Args:
            event: Keyboard event
        """
        # Check if Ctrl key was released
        if event.keysym in ("Control_L", "Control_R"):
            if self.__rotation_mode:
                # Log the attempt to exit rotation mode due to Ctrl key release
                logger.debug(self.__msg_mgr.get_message("L519")) # Attempting to exit rotation mode

                # If UI elements are not meant to be kept visible (e.g., mouse button was already up,
                # or Ctrl was pressed/released without mouse interaction, or mouse was released without Ctrl),
                # then proceed to exit rotation mode.
                if not self.__keep_rotation_elements_visible:
                    self.__exit_rotation_mode() # Handles UI cleanup and flag resets.
                else:
                    # If UI elements are currently meant to be kept visible (this implies that
                    # on_mouse_down or on_mouse_drag set it to True, and on_mouse_up with Ctrl
                    # might have kept it True or on_mouse_up without Ctrl set it to False).
                    # Now that Ctrl is released, we definitely don't want to keep them visible
                    # solely based on a past Ctrl state.
                    self.__keep_rotation_elements_visible = False
                    
                    # If the mouse button is NOT currently pressed (i.e., not actively rotating via mouse drag),
                    # then it's safe to exit rotation mode now that Ctrl is also released.
                    # This covers scenarios like: Ctrl+MouseDown -> Drag -> MouseUp (Ctrl still held) -> CtrlRelease.
                    if not self.__rotation_active:
                        self.__exit_rotation_mode()
            # No 'else' needed here; if not in rotation_mode, Ctrl release does nothing special.
        
    def on_mouse_wheel(self, event: tk.Event, layer_data=None) -> None:
        """Handle mouse wheel events for zooming.
        
        Args:
            event: Mouse wheel event
            layer_data: Optional layer data if provided externally
        """
        # Ensure canvas reference is not None before proceeding
        if self.__canvas_ref is None:
            # Log the missing canvas reference with L559 message code
            logger.warning(self.__msg_mgr.get_message("L559")) # L559: [MOUSE] Canvas reference is not set in MouseEventHandler
            return
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
                
                # Get current flip flags after toggle
                h_flip, v_flip = self.__layer_flip_flags[layer_id][self.__current_page_index]
                
                # Apply flips by adjusting coordinates and scale
                # For horizontal flip, we need to negate x-coordinate and scale
                # For vertical flip, we need to negate y-coordinate and scale
                new_x = -x if h_flip else x
                new_y = -y if v_flip else y
                
                # Apply scale changes to reflect flipping
                # Negative scale indicates flipping
                new_s = abs(s)  # Start with absolute scale
                if h_flip != v_flip:  # If only one axis is flipped
                    new_s = -new_s     # Negate scale to indicate flip
                
                # Keep the original rotation angle
                new_r = r
                
                # Update the transformation data
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, new_x, new_y, new_s)
                
                # Apply zoom factor to scale
                new_scale = new_s * zoom_factor
                
                # Limit scale to reasonable bounds (0.1x to 10x)
                new_scale = max(0.1, min(10.0, new_scale))
                
                # Update transformation data with new scale
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, new_x, new_y, new_scale)
        
        # Log zoom operation with throttling - use a different key than the wrapper
        # to avoid duplicate logs when both the wrapper and this method log
        # Only log here if the wrapper didn't already log (check if we have a canvas reference)
        if not hasattr(self, '_last_wheel_log_time') or time.time() - self._last_wheel_log_time > 1.0:
            # Store last log time to further reduce duplicates
            self._last_wheel_log_time = time.time()
            # Only log from here if we're called directly (not through wrapper)
            if self._wheel_log_throttle.should_log(key="direct_zoom_operation"):
                # Log with L561 for mouse wheel event processing
                logger.debug(self.__msg_mgr.get_message("L561", delta, zoom_factor))
        
        # Update display
        self.__on_transform_update()
        
    def attach_to_canvas(self, canvas: tk.Canvas) -> None:
        """Attach this handler to a canvas widget.
        
        Args:
            canvas: The canvas to attach to
        """
        # Store canvas reference
        self.__canvas_ref = canvas
        
        # Log successful attachment to canvas
        logger.debug(self.__msg_mgr.get_message("L560")) # L560: [MOUSE] Successfully attached to canvas
        
        # Note: We don't bind events here anymore to avoid duplicate bindings.
        # Event binding is now handled by the _setup_mouse_events method in the view class.
        # This prevents duplicate event handlers and potential conflicts.
        
        # Make canvas focusable to receive keyboard events
        # This is still needed here as it's a canvas property, not an event binding
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
            self._remove_shortcut_guide_from_canvas()
        
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
                    self._remove_shortcut_guide_from_canvas() # Ensure this line is correctly indented and present

            self.__current_page_index = current_page_index
            # logger.info(self.__msg_mgr.get_log_message("L538", self.__current_page_index + 1, base_total, comp_current, comp_total)) # TODO: Get total page counts
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

    def __rotate_by_angle(self, angle_degrees: float) -> None:
        """Rotate all visible layers by the specified angle around the rotation center.
    
    Args:
            angle_degrees: Angle to rotate in degrees (positive = clockwise)
        """
        # Skip very small angle changes
        if abs(angle_degrees) < 0.05:
            return

        # Convert incremental angle_degrees to radians for rotating the position
        theta = math.radians(angle_degrees)
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)

        # Rotation center (canvas coordinates)
        cx = self.__rotation_center_x
        cy = self.__rotation_center_y

        # Apply rotation to all visible layers
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue

            if layer_id in self.__layer_transform_data and \
               self.__current_page_index < len(self.__layer_transform_data[layer_id]):

                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]

                # Add the new rotation angle to the current rotation and normalize to 0-360 range
                new_rotation = (r + angle_degrees) % 360

                # Current layer position (canvas coordinates)
                # (x, y) is the layer's current reference point.

                # Translate point (layer's current position) to origin (relative to rotation center)
                translated_x = x - cx
                translated_y = y - cy

                # Rotate point
                # For standard 2D rotation matrix:
                # x' = x*cos(θ) - y*sin(θ)
                # y' = x*sin(θ) + y*cos(θ)
                rotated_x = translated_x * cos_theta - translated_y * sin_theta
                rotated_y = translated_x * sin_theta + translated_y * cos_theta

                # Translate point back to its new position
                new_x = rotated_x + cx
                new_y = rotated_y + cy

                # Update the transformation data with new rotation and new position
                self.__layer_transform_data[layer_id][self.__current_page_index] = (new_rotation, new_x, new_y, s)
        
        # Log the rotation operation (consider logging new_x, new_y as well if needed)
        logger.debug(self.__msg_mgr.get_message("L511").format(angle_degrees))
        
        # Update the display to reflect the rotation changes
        # This ensures the rotated image is immediately visible on the canvas
        self.__on_transform_update()
