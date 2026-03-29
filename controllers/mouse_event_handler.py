from __future__ import annotations
import sys
import tkinter as tk
from tkinter import messagebox
import tkinter.font as tkfont
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
            on_live_translation_update: Optional[Callable[[], None]] = None,
            operations_enabled: bool = True,
            blocked_message_code: str = "M055",
            commit_keyboard_preview_rotation: Optional[Callable[[], None]] = None,
            clear_keyboard_preview_rotation: Optional[Callable[[], None]] = None,
            on_transform_commit_no_propagate: Optional[Callable[[], None]] = None,
            sheet_rotate_guard: Optional[Callable[[], bool]] = None,
            sheet_rotate_blocked_message_code: str = "U177",
        ) -> None:
        """Initialize the MouseEventHandler.

        Args:
            layer_transform_data: List of transformation data for each layer
                Dict[layer_number, List[(rotation, x, y, scale), ...]]
            current_page_index: Current page index
            visible_layers: Layer visibility state Dict[layer_number, visibility_state]
            on_transform_update: Callback after transformation update
            on_live_translation_update: Optional lightweight callback used during drag-only translation
            operations_enabled: Whether canvas operations (zoom/pan/rotate/transform) are enabled
            blocked_message_code: Message code to display when an operation is blocked
            commit_keyboard_preview_rotation: Merge pending Ctrl+Shift preview rotation into layer data
                before other transform shortcuts run.
            clear_keyboard_preview_rotation: Drop pending Ctrl+Shift preview without merging (e.g. reset).
            on_transform_commit_no_propagate: Optional refresh after per-page sheet rotation (skip batch copy).
            sheet_rotate_guard: If set, Ctrl+Alt+R/L runs only when this returns True (e.g. dual-PDF main tab).
            sheet_rotate_blocked_message_code: UI message code when the guard fails.
        """
        # Transform data and callbacks
        self.__layer_transform_data: Dict[int, List[Tuple[float, float, float, float]]] = layer_transform_data
        self.__current_page_index: int = current_page_index
        self.__visible_layers: Dict[int, bool] = visible_layers
        self.__on_transform_update: Callable[[], None] = on_transform_update
        self.__on_live_translation_update: Optional[Callable[[], None]] = on_live_translation_update
        self.__commit_keyboard_preview_rotation: Optional[Callable[[], None]] = commit_keyboard_preview_rotation
        self.__clear_keyboard_preview_rotation: Optional[Callable[[], None]] = clear_keyboard_preview_rotation
        self.__on_transform_commit_no_propagate: Optional[Callable[[], None]] = (
            on_transform_commit_no_propagate
        )
        self.__sheet_rotate_guard: Optional[Callable[[], bool]] = sheet_rotate_guard
        self.__sheet_rotate_blocked_message_code: str = sheet_rotate_blocked_message_code

        # Tracking variables
        self.__dragging: bool = False
        self.__drag_start_x: float = 0.0
        self.__drag_start_y: float = 0.0
        self.__last_mouse_x: float = 0.0
        self.__last_mouse_y: float = 0.0
        self.__rotation_mode: bool = False
        self.__rotation_center_x: float = 0.0
        self.__rotation_center_y: float = 0.0
        self.__rotation_start_time: float = 0.0
        self.__rotation_active: bool = False
        self.__rotation_drag_start_angle: float = 0.0
        self.__rotation_drag_total_diff: float = 0.0
        self.__rotation_last_angle: float = 0.0
        self.__rotation_drag_base_rotations: Dict[int, float] = {}
        self.__rotation_center_candidate_x: float = 0.0
        self.__rotation_center_candidate_y: float = 0.0
        self.__rotation_center_candidate_pending: bool = False
        self.__rotation_center_candidate_moved: bool = False
        self.__rotation_center_img_offsets: Dict[int, tuple[float, float]] = {}
        self.__rotation_drag_base_transforms: Dict[int, tuple[float, float, float, float]] = {}
        self.__last_applied_angle: float = 0.0
        self.__last_rotation_update_time: float = 0.0
        self.__translation_preview_active: bool = False
        
        # Get message manager for localized messages
        self.__msg_mgr = get_message_manager()
        
        # Canvas reference (will be set in attach_to_canvas)
        self.__canvas_ref: Optional[tk.Canvas] = None

        # Original image dimensions (needed for rotation pivot calculation)
        self.__orig_image_width: int = 0
        self.__orig_image_height: int = 0

        # Operation control
        self.__operations_enabled: bool = operations_enabled
        self.__blocked_message_code: str = blocked_message_code
        self.__blocked_warning_ids: Optional[tuple[int, int]] = None
        self.__blocked_warning_after_id: Optional[str] = None
        
        # Feedback visual elements
        self.__feedback_circle_id: Optional[Union[int, tuple[int, ...]]] = None
        self.__guidance_text_id: Optional[int] = None
        self.__background_id: Optional[Union[int, tuple[int, ...]]] = None
        self.__notification_text_id: Optional[int] = None
        self.__notification_border_id: Optional[int] = None
        self.__notification_after_id: Optional[str] = None
        self.__shortcut_help_id: Optional[Union[int, tuple[int, ...]]] = None
        self.__help_display_id: Optional[int] = None
        self.__help_footnote_id: Optional[int] = None
        self.__help_background_id: Optional[int] = None
        
        # UI state (M1-011: single source of truth for shortcut help visibility)
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

    def set_original_image_size(self, width: int, height: int) -> None:
        """Store the original (unrotated, unscaled) image dimensions.

        These are needed to compute rotation pivot translation adjustments.

        Args:
            width: Original image width in pixels.
            height: Original image height in pixels.
        """
        self.__orig_image_width = width
        self.__orig_image_height = height

    @property
    def shortcut_help_visible(self) -> bool:
        """Return whether the shortcut help overlay is currently visible (M1-011).

        This property provides a read-only view of the help visibility flag
        so that external code (e.g. other tabs) can query the state without
        directly accessing private attributes.

        Returns:
            True if the shortcut help overlay is displayed.
        """
        return self.__shortcut_help_visible

    def set_shortcut_help_visibility(self, visible: bool) -> None:
        """Explicitly show or hide the shortcut help overlay (M1-011).

        Provides a programmatic interface for controlling the help overlay,
        enabling reuse of the same mechanism across multiple tabs.

        Args:
            visible: True to show, False to hide.
        """
        if visible:
            if not self.__shortcut_help_visible:
                self._show_shortcut_help()
        else:
            # Always remove canvas items tagged ``overlay_shortcut_help`` so orphaned
            # overlays (e.g. after handler recreation) cannot stay visible or toggle oddly.
            self._hide_shortcut_help()

    def clear_overlays(self) -> None:
        """Clear all canvas overlay items managed by this handler."""
        if self.__canvas_ref is None:
            return

        # Main processing: cancel scheduled callbacks.
        if self.__notification_after_id is not None:
            try:
                self.__canvas_ref.after_cancel(self.__notification_after_id)
            except Exception:
                pass
            self.__notification_after_id = None

        if self.__blocked_warning_after_id is not None:
            try:
                self.__canvas_ref.after_cancel(self.__blocked_warning_after_id)
            except Exception:
                pass
            self.__blocked_warning_after_id = None

        # Main processing: delete all overlay-tagged items.
        try:
            self.__canvas_ref.delete("overlay")
        except Exception:
            pass

        # Main processing: reset IDs and flags.
        self.__feedback_circle_id = None
        self.__guidance_text_id = None
        self.__background_id = None
        self.__notification_text_id = None
        self.__notification_border_id = None
        self.__help_display_id = None
        self.__help_footnote_id = None
        self.__help_background_id = None
        self.__blocked_warning_ids = None
        self.__shortcut_help_visible = False

    def refresh_overlay_positions(self) -> None:
        """Refresh overlay positions based on the current visible area."""
        if self.__canvas_ref is None:
            return

        x0, y0 = self._get_visible_origin()
        width = self.__canvas_ref.winfo_width()
        height = self.__canvas_ref.winfo_height()

        if width <= 1 or height <= 1:
            try:
                self.__canvas_ref.update_idletasks()
            except Exception:
                pass
            width = self.__canvas_ref.winfo_width()
            height = self.__canvas_ref.winfo_height()

        # Main processing: notification (top-center of visible area).
        if self.__notification_text_id is not None:
            try:
                self.__canvas_ref.coords(
                    self.__notification_text_id,
                    x0 + width / 2,
                    y0 + 12,
                )
                bbox = self.__canvas_ref.bbox(self.__notification_text_id)
                if bbox is not None and self.__notification_border_id is not None:
                    x1, y1, x2, y2 = bbox
                    pad = 6
                    self.__canvas_ref.coords(
                        self.__notification_border_id,
                        x1 - pad,
                        y1 - pad,
                        x2 + pad,
                        y2 + pad,
                    )
            except Exception:
                pass

        # Main processing: shortcut help (top-RIGHT of visible area) (M1-011).
        if self.__shortcut_help_visible:
            # Validate that canvas items still exist (may have been deleted externally).
            items_exist = (
                self.__help_display_id is not None
                and self.__help_background_id is not None
                and self.__canvas_ref.find_withtag("overlay_shortcut_help")
            )
            if not items_exist:
                # Sync flag: items were deleted externally, reset state.
                self.__help_display_id = None
                self.__help_footnote_id = None
                self.__help_background_id = None
                self.__shortcut_help_visible = False
            else:
                try:
                    try:
                        self.__canvas_ref.update_idletasks()
                    except Exception:
                        pass
                    self._relayout_shortcut_help_overlay(x0, y0, width)
                except Exception:
                    pass

        # Main processing: rotation center red dot (reposition from image coords).
        if self.__rotation_mode and self.__feedback_circle_id is not None and self.__rotation_center_img_offsets:
            try:
                rc = self._rotation_center_canvas_pos()
                if rc[0] is not None:
                    self.__rotation_center_x = rc[0]
                    self.__rotation_center_y = rc[1]
                    radius = 5
                    self.__canvas_ref.coords(
                        self.__feedback_circle_id,
                        rc[0] - radius, rc[1] - radius,
                        rc[0] + radius, rc[1] + radius,
                    )
            except Exception:
                pass

        # Main processing: guidance text (bottom-center of visible area).
        if self.__guidance_text_id is not None and self.__background_id is not None:
            try:
                bottom = y0 + height
                self.__canvas_ref.coords(
                    self.__guidance_text_id,
                    x0 + width / 2,
                    bottom - 25,
                )
                if isinstance(self.__background_id, tuple):
                    for bg_id in self.__background_id:
                        self.__canvas_ref.coords(
                            bg_id,
                            x0 + 10,
                            bottom - 40,
                            x0 + width - 10,
                            bottom - 10,
                        )
                else:
                    self.__canvas_ref.coords(
                        self.__background_id,
                        x0 + 10,
                        bottom - 40,
                        x0 + width - 10,
                        bottom - 10,
                    )
            except Exception:
                pass

        # Main processing: shortcut help must stay above other overlay items.
        if self.__shortcut_help_visible:
            try:
                self.__canvas_ref.tag_raise("overlay_shortcut_help")
            except Exception:
                pass

    def _get_visible_origin(self) -> tuple[float, float]:
        """Get the top-left origin of the visible canvas area in canvas coordinates."""
        if self.__canvas_ref is None:
            return (0.0, 0.0)
        return (float(self.__canvas_ref.canvasx(0)), float(self.__canvas_ref.canvasy(0)))

    def _compute_rotated_dims(self, angle_deg: float) -> tuple[float, float]:
        """Compute the rotated image dimensions after PIL rotate with expand=True.

        Args:
            angle_deg: Rotation angle in degrees.

        Returns:
            (rotated_width, rotated_height) in original image pixels.
        """
        rad = math.radians(angle_deg)
        abs_cos = abs(math.cos(rad))
        abs_sin = abs(math.sin(rad))
        W = self.__orig_image_width
        H = self.__orig_image_height
        rw = W * abs_cos + H * abs_sin
        rh = W * abs_sin + H * abs_cos
        return (rw, rh)

    def _canvas_to_image_offset(
        self, cx: float, cy: float, r: float, tx: float, ty: float, s: float,
    ) -> tuple[float, float]:
        """Convert a canvas point to an offset from the original image center.

        The offset is in original (unrotated) image coordinates relative to the
        image center, so it stays constant regardless of rotation/scale/translation.

        Args:
            cx: Canvas x coordinate.
            cy: Canvas y coordinate.
            r: Current rotation in degrees.
            tx: Current translation x (image NW anchor).
            ty: Current translation y (image NW anchor).
            s: Current scale factor.

        Returns:
            (ux, uy) offset from image center in original image pixels.
        """
        rad = math.radians(r)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        rw, rh = self._compute_rotated_dims(r)
        # Point in rotated-image coords (centered at rotated image center)
        vx = (cx - tx) / s - rw / 2
        vy = (cy - ty) / s - rh / 2
        # Inverse PIL rotation: R_pil(-r) = [[cos, -sin], [sin, cos]]
        ux = cos_r * vx - sin_r * vy
        uy = sin_r * vx + cos_r * vy
        return (ux, uy)

    def _image_offset_to_canvas(
        self, ux: float, uy: float, r: float, tx: float, ty: float, s: float,
    ) -> tuple[float, float]:
        """Convert an image-center-relative offset back to canvas coordinates.

        Args:
            ux: Offset x from image center in original image pixels.
            uy: Offset y from image center in original image pixels.
            r: Current rotation in degrees.
            tx: Current translation x (image NW anchor).
            ty: Current translation y (image NW anchor).
            s: Current scale factor.

        Returns:
            (canvas_x, canvas_y) on the canvas.
        """
        rad = math.radians(r)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        rw, rh = self._compute_rotated_dims(r)
        # Forward PIL rotation: R_pil(r) = [[cos, sin], [-sin, cos]]
        vx = cos_r * ux + sin_r * uy
        vy = -sin_r * ux + cos_r * uy
        # Canvas position
        canvas_x = s * (vx + rw / 2) + tx
        canvas_y = s * (vy + rh / 2) + ty
        return (canvas_x, canvas_y)

    def _rotation_center_canvas_pos(self) -> tuple[float | None, float | None]:
        """Compute current canvas position of rotation center from image-relative offset.

        Uses the first visible layer that has stored image offset data.

        Returns:
            (canvas_x, canvas_y) or (None, None) if unavailable.
        """
        if not self.__rotation_center_img_offsets or self.__orig_image_width == 0:
            return (None, None)
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
            if layer_id not in self.__rotation_center_img_offsets:
                continue
            if layer_id not in self.__layer_transform_data:
                continue
            if self.__current_page_index >= len(self.__layer_transform_data[layer_id]):
                continue
            ux, uy = self.__rotation_center_img_offsets[layer_id]
            r, tx, ty, s = self.__layer_transform_data[layer_id][self.__current_page_index]
            return self._image_offset_to_canvas(ux, uy, r, tx, ty, s)
        return (None, None)

    def set_operations_enabled(self, enabled: bool) -> None:
        """Enable or disable interactive canvas operations.

        Args:
            enabled: True to enable operations, False to disable them
        """
        self.__operations_enabled = enabled

    def show_operation_blocked_warning(self) -> None:
        """Show a centered warning overlay on the canvas for blocked operations."""
        if self.__canvas_ref is None:
            return

        if self.__blocked_warning_ids is not None:
            if self.__blocked_warning_after_id is not None:
                try:
                    self.__canvas_ref.after_cancel(self.__blocked_warning_after_id)
                except Exception:
                    pass
            self.__blocked_warning_after_id = self.__canvas_ref.after(
                1500,
                self._hide_operation_blocked_warning,
            )
            return

        # Main processing: render a warning in the canvas center.
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            self.__canvas_ref.update_idletasks()
            canvas_width = self.__canvas_ref.winfo_width()
            canvas_height = self.__canvas_ref.winfo_height()

        x0, y0 = self._get_visible_origin()

        message = self.__msg_mgr.get_message(self.__blocked_message_code)
        padding_x = 18
        padding_y = 12

        # Clear previous warning
        if self.__blocked_warning_ids is not None:
            rect_id, text_id = self.__blocked_warning_ids
            self.__canvas_ref.delete(rect_id)
            self.__canvas_ref.delete(text_id)
            self.__blocked_warning_ids = None

        # Create text first to get bbox
        text_id = self.__canvas_ref.create_text(
            x0 + canvas_width / 2,
            y0 + canvas_height / 2,
            text=message,
            fill="#ffffff",
            font=("Helvetica", 12, "bold"),
            justify=tk.CENTER,
            tags=("overlay", "overlay_blocked_warning"),
        )
        bbox = self.__canvas_ref.bbox(text_id)
        if bbox is None:
            self.__canvas_ref.delete(text_id)
            return
        x1, y1, x2, y2 = bbox

        rect_id = self.__canvas_ref.create_rectangle(
            x1 - padding_x,
            y1 - padding_y,
            x2 + padding_x,
            y2 + padding_y,
            fill="#ff3b30",
            outline="#ff0000",
            width=2,
            tags=("overlay", "overlay_blocked_warning"),
        )
        self.__canvas_ref.tag_lower(rect_id, text_id)
        self.__blocked_warning_ids = (rect_id, text_id)
        # Auto-hide after a short duration
        self.__blocked_warning_after_id = self.__canvas_ref.after(
            1500,
            self._hide_operation_blocked_warning,
        )

    def _hide_operation_blocked_warning(self) -> None:
        """Hide the copy-protected operation blocked warning overlay."""
        if self.__canvas_ref is None:
            return

        if self.__blocked_warning_ids is None:
            return

        rect_id, text_id = self.__blocked_warning_ids
        self.__canvas_ref.delete(rect_id)
        self.__canvas_ref.delete(text_id)
        self.__blocked_warning_ids = None
        self.__blocked_warning_after_id = None
        
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
            try:
                canvas_widget.delete("overlay_shortcut_help")
            except Exception:
                pass
            self.__help_footnote_id = None
            self.__help_display_id = None
            self.__help_background_id = None
            self.__shortcut_help_visible = False

        if canvas_widget is not None:
            # Set up keyboard bindings
            
            # Rotate 90 degrees to the right
            canvas_widget.bind('<Control-r>', self._on_rotate_right)
            canvas_widget.bind('<Control-R>', self._on_rotate_right)

            # Rotate 90 degrees to the left
            canvas_widget.bind('<Control-l>', self._on_rotate_left)
            canvas_widget.bind('<Control-L>', self._on_rotate_left)

            # Rotate every page sheet ±90° (Ctrl+Alt+R/L)
            canvas_widget.bind('<Control-Alt-r>', self._on_rotate_sheet_right)
            canvas_widget.bind('<Control-Alt-R>', self._on_rotate_sheet_right)
            canvas_widget.bind('<Control-Alt-l>', self._on_rotate_sheet_left)
            canvas_widget.bind('<Control-Alt-L>', self._on_rotate_sheet_left)
            
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
            canvas_widget.bind('<Control-slash>', self._toggle_shortcut_help)
            canvas_widget.bind('<Control-Shift-slash>', self._toggle_shortcut_help)
            canvas_widget.bind('<Control-Shift-h>', self._toggle_shortcut_help)
            canvas_widget.bind('<Control-Shift-H>', self._toggle_shortcut_help)

            # Main processing: exit rotation mode when Ctrl is released.
            canvas_widget.bind('<KeyRelease-Control_L>', self._on_ctrl_key_release)
            canvas_widget.bind('<KeyRelease-Control_R>', self._on_ctrl_key_release)
            
            # Allow canvas to receive keyboard events by making it focusable
            canvas_widget.config(takefocus=1)
            
            # Set focus to canvas on click
            canvas_widget.bind('<Button-1>', lambda e: canvas_widget.focus_set())

    def _event_to_canvas_coords(self, event_x: float, event_y: float) -> tuple[float, float]:
        """Convert event (widget) coordinates to canvas coordinates.

        Args:
            event_x: Event x in widget coordinates.
            event_y: Event y in widget coordinates.

        Returns:
            Tuple[float, float]: (x, y) in canvas coordinates.
        """
        if self.__canvas_ref is None:
            return (event_x, event_y)
        return (float(self.__canvas_ref.canvasx(event_x)), float(self.__canvas_ref.canvasy(event_y)))

    def _is_ctrl_physically_pressed(self) -> bool:
        """Check if the Ctrl key is physically held right now (M1-006).

        Uses the Windows API ``GetAsyncKeyState`` to query the real-time
        hardware key state, bypassing stale events that may still be queued
        in the Tkinter event loop.  On non-Windows platforms the method
        returns ``True`` as a safe fallback so that rotation processing
        proceeds normally and relies on the Tkinter KeyRelease event.

        Returns:
            bool: True if Ctrl is currently pressed (or on non-Windows).
        """
        if sys.platform == "win32":
            try:
                import ctypes
                # VK_CONTROL = 0x11; high bit set means key is currently down.
                return bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
            except (AttributeError, OSError):
                return True
        return True

    def _on_ctrl_key_release(self, event: tk.Event) -> str | None:
        """Exit rotation mode when Ctrl key is released.

        Args:
            event: Keyboard event.

        Returns:
            str | None: "break" to stop propagation.
        """
        if not self.__rotation_mode:
            return "break"

        # Main processing: clear rotation UI and state.
        self._hide_feedback_circle()
        self._hide_guidance_text()
        self.__rotation_mode = False
        self.__rotation_active = False
        self.__dragging = False  # Discard queued motion events (M1-006).
        self.__rotation_drag_base_rotations = {}
        self.__rotation_drag_base_transforms = {}
        self.__rotation_center_img_offsets = {}
        self.__rotation_center_candidate_pending = False
        self.__rotation_center_candidate_moved = False
        self.__last_applied_angle = 0.0
        return "break"

    def _get_visible_layer_ids(self) -> list[int]:
        """Return the currently visible layer IDs.

        Returns:
            List of visible layer IDs.
        """
        return [layer_id for layer_id, visible in self.__visible_layers.items() if visible]

    def _get_transform_target_layer_ids(self, *, ctrl_pressed: bool) -> list[int]:
        """Resolve which layers should receive pan or zoom updates.

        Args:
            ctrl_pressed: Whether the Ctrl key is currently held.

        Returns:
            Ordered list of layer IDs to update.
        """
        visible_layer_ids = self._get_visible_layer_ids()
        if ctrl_pressed and len(visible_layer_ids) == 1:
            return visible_layer_ids
        return list(self.__layer_transform_data.keys())

    def _is_ctrl_pressed(self, state: int) -> bool:
        """Return whether Ctrl is pressed in a Tk event state mask.

        Args:
            state: Tk event state bitmask.

        Returns:
            bool: True when Ctrl is pressed.
        """
        return (state & 0x0004) != 0

    def _is_shift_pressed(self, state: int) -> bool:
        """Return whether Shift is pressed in a Tk event state mask.

        Args:
            state: Tk event state bitmask.

        Returns:
            bool: True when Shift is pressed.
        """
        return (state & 0x0001) != 0

    def _is_ctrl_shift_pressed(self, state: int) -> bool:
        """Return whether Ctrl and Shift are both pressed.

        Args:
            state: Tk event state bitmask.

        Returns:
            bool: True when Ctrl and Shift are pressed together.
        """
        return self._is_ctrl_pressed(state) and self._is_shift_pressed(state)
    
    def on_mouse_down(self, event: tk.Event) -> None:
        """Handle mouse button press.
        
        Args:
            event: Mouse event
        """
        self.__dragging = True
        last_x, last_y = self._event_to_canvas_coords(event.x, event.y)
        self.__drag_start_x = last_x
        self.__drag_start_y = last_y
        self.__last_mouse_x = last_x
        self.__last_mouse_y = last_y
        self.__translation_preview_active = False
        
        # Main processing: resolve modifier state for rotation and translation gestures.
        state = int(event.state)
        ctrl_pressed = self._is_ctrl_pressed(state)
        ctrl_shift_pressed = self._is_ctrl_shift_pressed(state)
        visible_layer_ids = self._get_visible_layer_ids()
        isolate_visible_layer = ctrl_pressed and len(visible_layer_ids) == 1
        
        if ctrl_pressed and not self.__operations_enabled:
            return

        if ctrl_pressed and not ctrl_shift_pressed and self.__canvas_ref and not isolate_visible_layer:
            # Toggle rotation mode or update rotation center
            if not self.__rotation_mode:
                # Entering rotation mode: record pivot in image-relative coords
                self.__rotation_mode = True
                center_x, center_y = self._event_to_canvas_coords(event.x, event.y)
                self.__rotation_center_x = center_x
                self.__rotation_center_y = center_y
                self.__rotation_active = False
                self.__rotation_start_time = time.time()
                self.__rotation_drag_base_rotations = {}
                self.__rotation_center_candidate_pending = False
                self.__rotation_center_candidate_moved = False
                self.__last_applied_angle = 0.0
                # Main processing: store per-layer image offsets and base transforms.
                self.__rotation_center_img_offsets = {}
                self.__rotation_drag_base_transforms = {}
                have_img_size = self.__orig_image_width > 0 and self.__orig_image_height > 0
                for lid, vis in self.__visible_layers.items():
                    if not vis:
                        continue
                    if lid in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[lid]):
                        r, tx, ty, s = self.__layer_transform_data[lid][self.__current_page_index]
                        self.__rotation_drag_base_transforms[lid] = (r, tx, ty, s)
                        self.__rotation_drag_base_rotations[lid] = r
                        if have_img_size:
                            ux, uy = self._canvas_to_image_offset(center_x, center_y, r, tx, ty, s)
                            self.__rotation_center_img_offsets[lid] = (ux, uy)

                self._show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self._show_guidance_text(self.__msg_mgr.get_message('M042'))  # M042: Rotation mode - drag to rotate
            else:
                # Main processing: keep rotation center fixed; reset drag for a new gesture.
                self.__rotation_active = False
                self.__rotation_start_time = time.time()
                self.__rotation_center_candidate_pending = False
                self.__rotation_center_candidate_moved = False
                self.__last_applied_angle = 0.0

                # Re-snapshot base transforms for a fresh drag gesture
                self.__rotation_drag_base_rotations = {}
                self.__rotation_drag_base_transforms = {}
                have_img_size = self.__orig_image_width > 0 and self.__orig_image_height > 0
                for lid, vis in self.__visible_layers.items():
                    if not vis:
                        continue
                    if lid in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[lid]):
                        r, tx, ty, s = self.__layer_transform_data[lid][self.__current_page_index]
                        self.__rotation_drag_base_transforms[lid] = (r, tx, ty, s)
                        self.__rotation_drag_base_rotations[lid] = r

                # Recompute red dot canvas position from image coords
                rc = self._rotation_center_canvas_pos()
                if rc[0] is not None:
                    self.__rotation_center_x = rc[0]
                    self.__rotation_center_y = rc[1]
                self._show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self._show_guidance_text(self.__msg_mgr.get_message('M042'))  # M042: Rotation mode - drag to rotate

    def on_mouse_drag(self, event: tk.Event) -> None:
        """Handle mouse drag.
        
        Performs different operations based on modifier keys:
        - Ctrl+drag (rotation mode): Rotate around the pivot.
        - Drag: Move/pan image
        - Ctrl+Shift+drag (when not in rotation mode): Move/pan only the isolated visible layer
        
        Args:
            event: Mouse event
        """
        if not self.__dragging:
            return

        current_x, current_y = self._event_to_canvas_coords(event.x, event.y)
        dx = current_x - self.__last_mouse_x
        dy = current_y - self.__last_mouse_y

        # Cast event.state to int for type safety
        state = int(event.state)
        ctrl_pressed = self._is_ctrl_pressed(state)
        ctrl_shift_pressed = self._is_ctrl_shift_pressed(state)
        target_layer_ids = self._get_transform_target_layer_ids(ctrl_pressed=ctrl_pressed)

        # Check if we're in rotation mode.
        if ctrl_pressed and self.__rotation_mode:
            # Discard stale queued events: check real-time Ctrl state (M1-006).
            if not self._is_ctrl_physically_pressed():
                self._on_ctrl_key_release(event)
                return

            if not self.__operations_enabled:
                return

            if self.__rotation_center_candidate_pending and not self.__rotation_center_candidate_moved:
                if (abs(current_x - self.__drag_start_x) > 4) or (abs(current_y - self.__drag_start_y) > 4):
                    self.__rotation_center_candidate_moved = True
                    self.__rotation_center_candidate_pending = False
            # Check if we should activate rotation (after brief delay)
            current_time = time.time()
            if not self.__rotation_active and (current_time - self.__rotation_start_time) > 0.05:
                curr_dx = current_x - self.__rotation_center_x
                curr_dy = current_y - self.__rotation_center_y
                if (curr_dx * curr_dx + curr_dy * curr_dy) >= (10.0 * 10.0):
                    self.__rotation_active = True
                    # Main processing: record initial angle for incremental delta tracking.
                    self.__rotation_last_angle = math.atan2(-curr_dy, curr_dx)
                    self.__rotation_drag_total_diff = 0.0
                    self.__last_applied_angle = 0.0
                    self.__last_rotation_update_time = 0.0
                    # Re-snapshot base rotations/transforms at drag activation
                    self.__rotation_drag_base_rotations = {}
                    self.__rotation_drag_base_transforms = {}
                    for layer_id, visible in self.__visible_layers.items():
                        if not visible:
                            continue
                        if layer_id in self.__layer_transform_data and self.__current_page_index < len(self.__layer_transform_data[layer_id]):
                            r, tx, ty, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                            self.__rotation_drag_base_rotations[layer_id] = r
                            self.__rotation_drag_base_transforms[layer_id] = (r, tx, ty, s)
                    self._show_guidance_text(self.__msg_mgr.get_message('M042'))
             
            # Only apply rotation if active
            if self.__rotation_active:
                curr_dx = current_x - self.__rotation_center_x
                curr_dy = current_y - self.__rotation_center_y
                if (curr_dx * curr_dx + curr_dy * curr_dy) < (10.0 * 10.0):
                    self.__last_mouse_x = current_x
                    self.__last_mouse_y = current_y
                    return

                # Rate-limit rotation updates (~30fps) to prevent event queue buildup
                now = time.time()
                if (now - self.__last_rotation_update_time) < 0.033:
                    self.__last_mouse_x = current_x
                    self.__last_mouse_y = current_y
                    return
                self.__last_rotation_update_time = now

                curr_angle = math.atan2(-curr_dy, curr_dx)

                # Main processing: incremental delta with unwrap (handles >360° naturally).
                delta = curr_angle - self.__rotation_last_angle
                if delta > math.pi:
                    delta -= 2 * math.pi
                elif delta < -math.pi:
                    delta += 2 * math.pi
                self.__rotation_drag_total_diff += delta
                self.__rotation_last_angle = curr_angle

                angle_diff = round(math.degrees(self.__rotation_drag_total_diff), 1)
                # Hysteresis: ignore changes < 0.2° to absorb mouse position jitter
                if abs(angle_diff - self.__last_applied_angle) < 0.2:
                    self.__last_mouse_x = current_x
                    self.__last_mouse_y = current_y
                    return
                self.__last_applied_angle = angle_diff

                have_img_size = self.__orig_image_width > 0 and self.__orig_image_height > 0
                # Use fixed canvas position for pivot (do NOT recompute during drag)
                px, py = self.__rotation_center_x, self.__rotation_center_y

                # Apply rotation with pivot-compensated translation to all visible layers
                for layer_id, visible in self.__visible_layers.items():
                    if not visible:
                        continue
                    if layer_id not in self.__layer_transform_data:
                        continue
                    if self.__current_page_index >= len(self.__layer_transform_data[layer_id]):
                        continue

                    base_t = self.__rotation_drag_base_transforms.get(layer_id)
                    if base_t is None:
                        continue
                    base_r, base_tx, base_ty, base_s = base_t
                    new_r = base_r + angle_diff

                    if have_img_size and layer_id in self.__rotation_center_img_offsets:
                        # Compute new translation so that the pivot stays at (px, py)
                        ux, uy = self.__rotation_center_img_offsets[layer_id]
                        rad_new = math.radians(new_r)
                        cos_new = math.cos(rad_new)
                        sin_new = math.sin(rad_new)
                        vx_new = cos_new * ux + sin_new * uy
                        vy_new = -sin_new * ux + cos_new * uy
                        rw_new, rh_new = self._compute_rotated_dims(new_r)
                        new_tx = px - base_s * (vx_new + rw_new / 2)
                        new_ty = py - base_s * (vy_new + rh_new / 2)
                        self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, new_tx, new_ty, base_s)
                    else:
                        # Fallback: rotate without translation adjustment
                        _, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                        self.__layer_transform_data[layer_id][self.__current_page_index] = (new_r, x, y, s)
                
                # Main processing: update canvas; keep red dot at fixed canvas position during drag.
                self.__on_transform_update()
                self._show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self.refresh_overlay_positions()
                
        else:
            if not self.__operations_enabled:
                return

            # Main processing: move the preview image during normal drag gestures.
            should_update = abs(dx) > 0 or abs(dy) > 0
            
            # Process for each layer
            for layer_id in target_layer_ids:
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
                if self.__on_live_translation_update is not None:
                    self.__translation_preview_active = True
                    self.__on_live_translation_update()
                else:
                    self.__on_transform_update()

        # Update last mouse position
        self.__last_mouse_x = current_x
        self.__last_mouse_y = current_y

    def on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release.
        
        Args:
            event: Mouse event
        """
        self.__dragging = False
        
        # Check if Ctrl is still pressed
        state = int(event.state)
        ctrl_pressed = self._is_ctrl_pressed(state)

        # Handle rotation mode completion
        if self.__rotation_mode:
            # Main processing: keep M042 visible until Ctrl is released.
            if ctrl_pressed:
                self.__rotation_active = False
                self.__rotation_drag_base_rotations = {}
                self.__rotation_drag_base_transforms = {}
                self.__rotation_center_candidate_pending = False
                self.__rotation_center_candidate_moved = False
                self.__last_applied_angle = 0.0
                # Recompute red dot canvas position from image coords
                rc = self._rotation_center_canvas_pos()
                if rc[0] is not None:
                    self.__rotation_center_x = rc[0]
                    self.__rotation_center_y = rc[1]
                self._show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)
                self._show_guidance_text(self.__msg_mgr.get_message('M042'))
                return
                
            # If Ctrl is no longer pressed, exit rotation mode completely
            if not ctrl_pressed:
                self._hide_feedback_circle()
                self._hide_guidance_text()
                self.__rotation_mode = False
                self.__rotation_active = False
                self.__rotation_drag_base_rotations = {}
                self.__rotation_drag_base_transforms = {}
                self.__rotation_center_img_offsets = {}
                self.__rotation_center_candidate_pending = False
                self.__rotation_center_candidate_moved = False
                self.__last_applied_angle = 0.0

        if self.__translation_preview_active:
            self.__translation_preview_active = False
            self.__on_transform_update()

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
        
        # Main processing: keep rotation guidance while Ctrl rotation mode is active.
        if not self.__rotation_mode:
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
        
        state = int(getattr(event, "state", 0))
        ctrl_pressed = self._is_ctrl_pressed(state)
        if not self.__operations_enabled:
            return

        self._maybe_commit_keyboard_preview_rotation()

        # Apply zoom to visible layers
        zoom_factor = 1.1 if direction > 0 else 0.9
        target_layer_ids = self._get_transform_target_layer_ids(ctrl_pressed=ctrl_pressed)
        
        # Get canvas center for scaling origin
        canvas_width = self.__canvas_ref.winfo_width()
        canvas_height = self.__canvas_ref.winfo_height()
        x0, y0 = self._get_visible_origin()
        center_x = x0 + canvas_width / 2
        center_y = y0 + canvas_height / 2
        
        # Apply zoom to the resolved target layers around canvas center
        for layer_id in target_layer_ids:
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

        # Main processing: recompute red dot position after zoom if in rotation mode.
        if self.__rotation_mode and self.__rotation_center_img_offsets:
            rc = self._rotation_center_canvas_pos()
            if rc[0] is not None:
                self.__rotation_center_x = rc[0]
                self.__rotation_center_y = rc[1]
            self._show_feedback_circle(self.__rotation_center_x, self.__rotation_center_y, is_rotating=True)

        self.refresh_overlay_positions()
        
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

        # Main processing: show a red dot for rotation center.
        radius = 5
        dot_id = self.__canvas_ref.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="#ff0000", outline="#ff0000", width=1,
            tags=("overlay", "overlay_rotation_center"),
        )

        # Store IDs for later removal
        self.__feedback_circle_id = dot_id
        
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
        x0, y0 = self._get_visible_origin()
        
        # Create red border rectangle with transparent background
        bg = self.__canvas_ref.create_rectangle(
            x0 + 10,
            y0 + canvas_height - 40,
            x0 + canvas_width - 10,
            y0 + canvas_height - 10,
            fill="",
            outline="#ff0000",
            width=2,
            tags=("overlay", "overlay_guidance"),
        )
        
        # Create text in red - centered both horizontally and vertically
        text_id = self.__canvas_ref.create_text(
            x0 + canvas_width / 2,
            y0 + canvas_height - 25,
            text=message,
            fill="#ff0000",
            font=("Helvetica", 10, "bold"),
            anchor="center",
            justify="center",
            tags=("overlay", "overlay_guidance"),
        )
        self.__canvas_ref.tag_raise(text_id, bg)
        
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
            
        # Main processing: cancel any existing scheduled hide.
        if self.__notification_after_id is not None:
            try:
                self.__canvas_ref.after_cancel(self.__notification_after_id)
            except Exception:
                pass
            self.__notification_after_id = None

        # Hide any existing notification
        if self.__notification_text_id is not None:
            self.__canvas_ref.delete(self.__notification_text_id)
            self.__notification_text_id = None

        if self.__notification_border_id is not None:
            self.__canvas_ref.delete(self.__notification_border_id)
            self.__notification_border_id = None
            
        # Get canvas dimensions for positioning
        canvas_width = self.__canvas_ref.winfo_width()
        x0, y0 = self._get_visible_origin()

        # Create text (red) at top-center of the visible area
        self.__notification_text_id = self.__canvas_ref.create_text(
            x0 + canvas_width / 2,
            y0 + 12,
            text=message,
            fill="#ff0000",
            font=("Helvetica", 12, "bold"),
            justify=tk.CENTER,
            anchor="n",
            tags=("overlay", "overlay_notification"),
        )

        # Main processing: draw red border rectangle around the text (transparent background).
        self.__canvas_ref.update_idletasks()
        bbox = self.__canvas_ref.bbox(self.__notification_text_id)
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            pad = 6
            self.__notification_border_id = self.__canvas_ref.create_rectangle(
                x1 - pad,
                y1 - pad,
                x2 + pad,
                y2 + pad,
                fill="",
                outline="#ff0000",
                width=2,
                tags=("overlay", "overlay_notification"),
            )
            self.__canvas_ref.tag_raise(self.__notification_text_id, self.__notification_border_id)

        # Set up auto-removal
        duration_ms = max(1000, int(duration * 1000))
        self.__notification_after_id = self.__canvas_ref.after(duration_ms, self._hide_notification)
        
        # Log notification display
        logger.debug(message_manager.get_log_message("L336", message))
        
    def _hide_notification(self) -> None:
        """Hide the notification text."""
        if self.__canvas_ref is None:
            return

        if self.__notification_after_id is not None:
            try:
                self.__canvas_ref.after_cancel(self.__notification_after_id)
            except Exception:
                pass
            self.__notification_after_id = None

        if self.__notification_text_id is not None:
            self.__canvas_ref.delete(self.__notification_text_id)
            self.__notification_text_id = None

        if self.__notification_border_id is not None:
            self.__canvas_ref.delete(self.__notification_border_id)
            self.__notification_border_id = None
        
    def _hide_shortcut_help(self) -> None:
        """Hide the shortcut help display."""
        if self.__canvas_ref is None:
            self.__help_footnote_id = None
            self.__help_display_id = None
            self.__help_background_id = None
            self.__shortcut_help_visible = False
            return

        try:
            self.__canvas_ref.delete("overlay_shortcut_help")
        except Exception:
            pass
        self.__help_footnote_id = None
        self.__help_display_id = None
        self.__help_background_id = None
        self.__shortcut_help_visible = False
        
    def _apply_rotation_delta_current_page_visible_layers(self, delta_deg: float) -> None:
        """Add ``delta_deg`` to rotation for the current page on each visible layer.

        Args:
            delta_deg: Degrees to add (may be negative).
        """
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
            if (
                layer_id in self.__layer_transform_data
                and self.__current_page_index < len(self.__layer_transform_data[layer_id])
            ):
                r, x, y, s = self.__layer_transform_data[layer_id][self.__current_page_index]
                self.__layer_transform_data[layer_id][self.__current_page_index] = (
                    r + float(delta_deg),
                    x,
                    y,
                    s,
                )
        self.__on_transform_update()

    def _apply_rotation_delta_all_pages_visible_layers(self, delta_deg: float) -> None:
        """Add ``delta_deg`` to rotation on every page for each visible layer.

        Used for Ctrl+Alt+R/L (per-sheet rotation) without copying one page to all.

        Args:
            delta_deg: Degrees to add (may be negative).
        """
        for layer_id, visible in self.__visible_layers.items():
            if not visible:
                continue
            if layer_id not in self.__layer_transform_data:
                continue
            page_list = self.__layer_transform_data[layer_id]
            for page_index in range(len(page_list)):
                r, x, y, s = page_list[page_index]
                page_list[page_index] = (r + float(delta_deg), x, y, s)
        if self.__on_transform_commit_no_propagate is not None:
            self.__on_transform_commit_no_propagate()
        else:
            self.__on_transform_update()

    def _maybe_commit_keyboard_preview_rotation(self) -> None:
        """Merge pending Ctrl+Shift preview rotation before another transform shortcut."""
        if self.__commit_keyboard_preview_rotation is not None:
            self.__commit_keyboard_preview_rotation()

    def _maybe_clear_keyboard_preview_rotation(self) -> None:
        """Discard pending Ctrl+Shift preview without merging (e.g. reset shortcut)."""
        if self.__clear_keyboard_preview_rotation is not None:
            self.__clear_keyboard_preview_rotation()

    def _on_rotate_right(self, event: tk.Event) -> str | None:
        """Handle Ctrl+R keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        if not self.__operations_enabled:
            return "break"

        self._maybe_commit_keyboard_preview_rotation()
        self._apply_rotation_delta_current_page_visible_layers(90.0)
        self._show_notification(self.__msg_mgr.get_message('M044'))  # M044: Rotated right 90°
        logger.debug(message_manager.get_log_message("L337", "right"))
        return "break"  # Prevent default handling
        
    def _on_rotate_left(self, event: tk.Event) -> str | None:
        """Handle Ctrl+L keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        if not self.__operations_enabled:
            return "break"

        self._maybe_commit_keyboard_preview_rotation()
        self._apply_rotation_delta_current_page_visible_layers(-90.0)
        self._show_notification(self.__msg_mgr.get_message('M045'))  # M045: Rotated left 90°
        logger.debug(message_manager.get_log_message("L337", "left"))
        return "break"  # Prevent default handling

    def _on_rotate_sheet_right(self, event: tk.Event) -> str | None:
        """Handle Ctrl+Alt+R: +90° on every page (visible layers)."""
        if not self.__operations_enabled:
            return "break"
        if self.__sheet_rotate_guard is not None and not self.__sheet_rotate_guard():
            try:
                top = event.widget.winfo_toplevel()
            except Exception:
                top = None
            messagebox.showinfo(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message(self.__sheet_rotate_blocked_message_code),
                parent=top,
            )
            return "break"
        self._maybe_commit_keyboard_preview_rotation()
        self._apply_rotation_delta_all_pages_visible_layers(90.0)
        self._show_notification(self.__msg_mgr.get_message("M061"))
        logger.debug(message_manager.get_log_message("L337", "sheet_right"))
        return "break"

    def _on_rotate_sheet_left(self, event: tk.Event) -> str | None:
        """Handle Ctrl+Alt+L: −90° on every page (visible layers)."""
        if not self.__operations_enabled:
            return "break"
        if self.__sheet_rotate_guard is not None and not self.__sheet_rotate_guard():
            try:
                top = event.widget.winfo_toplevel()
            except Exception:
                top = None
            messagebox.showinfo(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message(self.__sheet_rotate_blocked_message_code),
                parent=top,
            )
            return "break"
        self._maybe_commit_keyboard_preview_rotation()
        self._apply_rotation_delta_all_pages_visible_layers(-90.0)
        self._show_notification(self.__msg_mgr.get_message("M062"))
        logger.debug(message_manager.get_log_message("L337", "sheet_left"))
        return "break"
        
    def _on_flip_vertical(self, event: tk.Event) -> str | None:
        """Handle Ctrl+V keyboard shortcut.
        
        Args:
            event: Keyboard event
        """
        if not self.__operations_enabled:
            return "break"

        self._maybe_commit_keyboard_preview_rotation()
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
        if not self.__operations_enabled:
            return "break"

        self._maybe_commit_keyboard_preview_rotation()
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
        if not self.__operations_enabled:
            return "break"

        self._maybe_clear_keyboard_preview_rotation()
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

    def _relayout_shortcut_help_overlay(self, x0: int, y0: int, canvas_width: int) -> None:
        """Place M049 header, optional M049F footnotes, and shared background (top-right box)."""
        if self.__canvas_ref is None or self.__help_display_id is None:
            return
        outer_pad = 12
        inner_pad = 10
        wrap_w = self._shortcut_help_wrap_width(canvas_width)
        try:
            self.__canvas_ref.itemconfigure(self.__help_display_id, width=wrap_w)
            if self.__help_footnote_id is not None:
                self.__canvas_ref.itemconfigure(self.__help_footnote_id, width=wrap_w)
        except Exception:
            pass
        self.__canvas_ref.update_idletasks()
        bm = self.__canvas_ref.bbox(self.__help_display_id)
        if bm is None:
            return
        mw, mh = bm[2] - bm[0], bm[3] - bm[1]
        bf = (
            self.__canvas_ref.bbox(self.__help_footnote_id)
            if self.__help_footnote_id is not None
            else None
        )
        fw = (bf[2] - bf[0]) if bf is not None else 0
        fh = (bf[3] - bf[1]) if bf is not None else 0
        maxw = max(mw, fw, 1)
        rect_x2 = x0 + canvas_width - outer_pad
        rect_y1 = y0 + outer_pad
        text_x = rect_x2 - maxw - 2 * inner_pad
        text_y = rect_y1 + inner_pad
        self.__canvas_ref.coords(self.__help_display_id, text_x, text_y)
        gap = 10
        if self.__help_footnote_id is not None and fh > 0:
            self.__canvas_ref.coords(
                self.__help_footnote_id,
                text_x,
                text_y + mh + gap,
            )
        self.__canvas_ref.update_idletasks()
        bm2 = self.__canvas_ref.bbox(self.__help_display_id)
        if bm2 is None or self.__help_background_id is None:
            return
        ul, ut, ur, ubt = bm2[0], bm2[1], bm2[2], bm2[3]
        if self.__help_footnote_id is not None:
            bf2 = self.__canvas_ref.bbox(self.__help_footnote_id)
            if bf2 is not None:
                ul = min(ul, bf2[0])
                ut = min(ut, bf2[1])
                ur = max(ur, bf2[2])
                ubt = max(ubt, bf2[3])
        self.__canvas_ref.coords(
            self.__help_background_id,
            ul - inner_pad,
            ut - inner_pad,
            ur + inner_pad,
            ubt + inner_pad,
        )
        try:
            self.__canvas_ref.tag_raise(self.__help_display_id, self.__help_background_id)
            if self.__help_footnote_id is not None:
                self.__canvas_ref.tag_raise(self.__help_footnote_id, self.__help_background_id)
                self.__canvas_ref.tag_raise(self.__help_footnote_id, self.__help_display_id)
        except Exception:
            pass

    def _shortcut_help_wrap_width(self, canvas_width: int) -> int:
        """Width for M049 overlay: fit shortcut block; M049F uses the same width on a separate item.

        Args:
            canvas_width: Visible canvas width in pixels.

        Returns:
            Width argument for ``Canvas.create_text`` / ``itemconfigure(..., width=...)``.
        """
        outer_pad = 12
        inner_pad = 10
        measure_font = tkfont.Font(family="Helvetica", size=10, weight="bold")
        max_px = 0.0
        for block in (
            self.__msg_mgr.get_message("M049"),
            self.__msg_mgr.get_message("M049F"),
        ):
            for raw in block.split("\n"):
                line = raw.replace("\r", "")
                if not line.strip():
                    continue
                m = float(measure_font.measure(line))
                if m > max_px:
                    max_px = m
        desired = int(max_px) + 20
        avail = max(canvas_width - outer_pad * 2 - 2 * inner_pad - 8, 120)
        return max(min(desired, avail), 120)

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
        """Show the keyboard shortcut help overlay at the top-right of the visible area."""
        if self.__canvas_ref is None:
            return
            
        # First hide if already displayed
        self._hide_shortcut_help()
        
        try:
            self.__canvas_ref.update_idletasks()
        except Exception:
            pass
        x0, y0 = self._get_visible_origin()
        canvas_width = self.__canvas_ref.winfo_width()
        wrap_w = self._shortcut_help_wrap_width(canvas_width)

        header_text = self.__msg_mgr.get_message("M049")
        foot_text = self.__msg_mgr.get_message("M049F").strip()

        # Background first so header/footnote text stacks above it.
        self.__help_background_id = self.__canvas_ref.create_rectangle(
            0,
            0,
            1,
            1,
            fill="#fff2a8",
            outline="#e6c200",
            width=2,
            tags=("overlay", "overlay_shortcut_help"),
        )
        self.__help_display_id = self.__canvas_ref.create_text(
            0,
            0,
            text=header_text,
            width=wrap_w,
            fill="#008000",
            font=("Helvetica", 10, "bold"),
            justify=tk.LEFT,
            anchor="nw",
            tags=("overlay", "overlay_shortcut_help"),
        )
        self.__help_footnote_id = None
        if foot_text:
            self.__help_footnote_id = self.__canvas_ref.create_text(
                0,
                0,
                text=foot_text,
                width=wrap_w,
                fill="#008000",
                font=("Helvetica", 10, "bold"),
                justify=tk.LEFT,
                anchor="nw",
                tags=("overlay", "overlay_shortcut_help"),
            )

        self._relayout_shortcut_help_overlay(x0, y0, canvas_width)
        try:
            self.__canvas_ref.tag_raise("overlay_shortcut_help")
        except Exception:
            pass

        self.__shortcut_help_visible = True
        self.refresh_overlay_positions()
