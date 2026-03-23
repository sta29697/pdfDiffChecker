from __future__ import annotations
from logging import getLogger
from typing import Tuple, Callable, Optional
from PIL import Image, ImageTk
import tkinter as tk
import os

logger = getLogger(__name__)


class ImageEditorController:
    """
    Controller for image editing operations.
    Handles image processing and mouse events for image manipulation.
    """

    def __init__(
        self,
        view: object,  # Any -> object
        canvas: tk.Canvas,
        temp_dir: str,
        file1_path: str,
        file2_path: str,
        on_transform_update: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize the image editor controller.

        Args:
            view: The associated view object
            canvas: The canvas widget for displaying images
            temp_dir: Directory for temporary files
            file1_path: Path to the first image file
            file2_path: Path to the second image file
            on_transform_update: Callback to update display after transform changes
        """
        self.view = view
        self.canvas = canvas
        self.temp_dir = temp_dir
        self.file1_path = file1_path
        self.file2_path = file2_path
        self.on_transform_update = on_transform_update

        # Image state variables
        self.image1_pil: Optional[Image.Image] = None
        self.image2_pil: Optional[Image.Image] = None
        self.image1_tk: Optional[ImageTk.PhotoImage] = None
        self.image2_tk: Optional[ImageTk.PhotoImage] = None
        self.image1_id: Optional[int] = None
        self.image2_id: Optional[int] = None

        # Transform state
        self.x1: float = 0
        self.y1: float = 0
        self.x2: float = 0
        self.y2: float = 0
        self.angle1: float = 0
        self.angle2: float = 0
        self.scale1: float = 1.0
        self.scale2: float = 1.0

        # Mouse event state
        self.drag_start_x: Optional[int] = None
        self.drag_start_y: Optional[int] = None
        self.rotation_center: Optional[Tuple[int, int]] = None
        self.active_layer: int = 1  # 1 or 2

        # Initialize
        self.load_images()
        self.setup_event_handlers()

    def load_images(self) -> None:
        """
        Load and convert images from source files.
        """
        try:
            # Generate paths for converted PNG images
            img1_path = os.path.join(
                self.temp_dir,
                f"{os.path.basename(self.file1_path).split('.')[0]}_000.png",
            )
            img2_path = os.path.join(
                self.temp_dir,
                f"{os.path.basename(self.file2_path).split('.')[0]}_000.png",
            )

            # Load PIL images
            self.image1_pil = Image.open(img1_path)
            self.image2_pil = Image.open(img2_path)

            # Create Tkinter PhotoImage objects
            self.image1_tk = ImageTk.PhotoImage(self.image1_pil)
            self.image2_tk = ImageTk.PhotoImage(self.image2_pil)

            # Display images on canvas
            self.image1_id = self.canvas.create_image(
                400, 300, image=self.image1_tk, tags=("layer1",)
            )
            self.image2_id = self.canvas.create_image(
                400, 300, image=self.image2_tk, tags=("layer2",)
            )

            logger.info("Images loaded successfully")
        except Exception as e:
            logger.error(f"Error loading images: {e}")

    def setup_event_handlers(self) -> None:
        """
        Set up event handlers for mouse interactions.
        """
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Control-ButtonPress-1>", self.set_rotation_center)
        self.canvas.bind("<Control-B1-Motion>", self.rotate_layer)
        self.canvas.bind("<Escape>", self.reset_rotation_center)
        self.canvas.bind("<MouseWheel>", self.zoom_layer)

    # === Layer Selection Methods ===

    def select_layer(self, layer_num: int) -> None:
        """
        Select the active layer for manipulation.

        Args:
            layer_num: Layer number (1 or 2)
        """
        if layer_num in (1, 2):
            self.active_layer = layer_num
            logger.info(f"Selected layer {layer_num}")

            # Update UI to indicate active layer if needed
            if hasattr(self.view, "update_layer_selection"):
                self.view.update_layer_selection(layer_num)

    # === Mouse Event Handlers ===

    def on_click(self, event: tk.Event) -> None:
        """
        Handle mouse click event.

        Args:
            event: Mouse event object
        """
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag(self, event: tk.Event) -> None:
        """
        Handle mouse drag event.

        Args:
            event: Mouse event object
        """
        if self.drag_start_x is None or self.drag_start_y is None:
            return

        # Calculate movement delta
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y

        # Move the active layer
        if self.active_layer == 1 and self.image1_id is not None:
            self.canvas.move(self.image1_id, dx, dy)
            self.x1 += dx
            self.y1 += dy
        elif self.active_layer == 2 and self.image2_id is not None:
            self.canvas.move(self.image2_id, dx, dy)
            self.x2 += dx
            self.y2 += dy

        # Update last mouse position
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        # Call update callback if provided
        if self.on_transform_update:
            self.on_transform_update()

    def set_rotation_center(self, event: tk.Event) -> None:
        """
        Set the rotation center point.

        Args:
            event: Mouse event object
        """
        self.rotation_center = (event.x, event.y)
        logger.info(f"Rotation center set to ({event.x}, {event.y})")

    def rotate_layer(self, event: tk.Event) -> None:
        """
        Rotate the active layer.

        Args:
            event: Mouse event object
        """
        if not self.rotation_center:
            return

        # Calculate angle based on mouse movement relative to rotation center
        center_x, center_y = self.rotation_center
        dx = event.x - center_x
        dy = event.y - center_y

        # Simple rotation calculation (can be improved for more precise control)
        angle_change = dx * 0.5 + (dy * 0.1)  # Adjust sensitivity as needed

        if self.active_layer == 1:
            self.angle1 += angle_change
            self._rotate_image(1, self.angle1)
        elif self.active_layer == 2:
            self.angle2 += angle_change
            self._rotate_image(2, self.angle2)

        # Call update callback if provided
        if self.on_transform_update:
            self.on_transform_update()

    def reset_rotation_center(self, event: Optional[tk.Event] = None) -> None:
        """
        Reset the rotation center point.

        Args:
            event: Mouse event object (optional)
        """
        self.rotation_center = None
        logger.info("Rotation center reset")

    def zoom_layer(self, event: tk.Event) -> None:
        """
        Zoom the active layer.

        Args:
            event: Mouse wheel event object
        """
        # Get zoom direction from mouse wheel
        delta = event.delta if hasattr(event, "delta") else -1 if event.num == 4 else 1
        scale_factor = 1.1 if delta > 0 else 0.9

        if self.active_layer == 1:
            self.scale1 *= scale_factor
            self._scale_image(1, self.scale1)
        elif self.active_layer == 2:
            self.scale2 *= scale_factor
            self._scale_image(2, self.scale2)

        # Call update callback if provided
        if self.on_transform_update:
            self.on_transform_update()

    # === Image Transformation Methods ===

    def _rotate_image(self, layer: int, angle: float) -> None:
        """
        Rotate an image layer.

        Args:
            layer: Layer number (1 or 2)
            angle: Rotation angle in degrees
        """
        try:
            if layer == 1 and self.image1_pil and self.image1_id:
                rotated = self.image1_pil.rotate(
                    angle, resample=Image.Resampling.BICUBIC, expand=True
                )
                self.image1_tk = ImageTk.PhotoImage(rotated)
                self.canvas.itemconfig(self.image1_id, image=self.image1_tk)

            elif layer == 2 and self.image2_pil and self.image2_id:
                rotated = self.image2_pil.rotate(
                    angle, resample=Image.Resampling.BICUBIC, expand=True
                )
                self.image2_tk = ImageTk.PhotoImage(rotated)
                self.canvas.itemconfig(self.image2_id, image=self.image2_tk)
        except Exception as e:
            logger.error(f"Error rotating image: {e}")

    def _scale_image(self, layer: int, scale: float) -> None:
        """
        Scale an image layer.

        Args:
            layer: Layer number (1 or 2)
            scale: Scale factor
        """
        try:
            if layer == 1 and self.image1_pil and self.image1_id:
                width, height = self.image1_pil.size
                new_size = (int(width * scale), int(height * scale))
                resized = self.image1_pil.resize(new_size, Image.Resampling.LANCZOS)
                self.image1_tk = ImageTk.PhotoImage(resized)
                self.canvas.itemconfig(self.image1_id, image=self.image1_tk)

            elif layer == 2 and self.image2_pil and self.image2_id:
                width, height = self.image2_pil.size
                new_size = (int(width * scale), int(height * scale))
                resized = self.image2_pil.resize(new_size, Image.Resampling.LANCZOS)
                self.image2_tk = ImageTk.PhotoImage(resized)
                self.canvas.itemconfig(self.image2_id, image=self.image2_tk)
        except Exception as e:
            logger.error(f"Error scaling image: {e}")

    # === Utility Methods ===

    def update_state(
        self,
        current_page_index: int,
        base_visible: bool,
        comp_visible: bool,
    ) -> None:
        """
        Update the controller state.

        Args:
            current_page_index: Current page index
            base_visible: Whether base image is visible
            comp_visible: Whether comp image is visible
        """
        # No implementation needed for this example

    def save_transformed_images(self, output_dir: str) -> Tuple[str, str]:
        """
        Save the transformed images.

        Args:
            output_dir: Directory to save the images

        Returns:
            Tuple of paths to the saved images
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Save base image
            base_output_path = os.path.join(
                output_dir, f"transformed_base_{os.path.basename(self.file1_path)}"
            )
            if self.image1_pil:
                # Apply transformations
                transformed = self._apply_transformations(
                    self.image1_pil, (self.x1, self.y1, self.angle1, self.scale1)
                )
                transformed.save(base_output_path)

            # Save comp image
            comp_output_path = os.path.join(
                output_dir, f"transformed_comp_{os.path.basename(self.file2_path)}"
            )
            if self.image2_pil:
                # Apply transformations
                transformed = self._apply_transformations(
                    self.image2_pil, (self.x2, self.y2, self.angle2, self.scale2)
                )
                transformed.save(comp_output_path)

            logger.info(f"[APP_SAVE] Saved transformed images to {output_dir}")
            return base_output_path, comp_output_path
        except Exception as e:
            logger.error(f"Error saving transformed images: {e}")
            return "", ""

    def _apply_transformations(
        self, image: Image.Image, transform_data: Tuple[float, float, float, float]
    ) -> Image.Image:
        """
        Apply all transformations to an image.

        Args:
            image: PIL Image object
            transform_data: Transform data tuple (x, y, angle, scale)

        Returns:
            Transformed PIL Image
        """
        x, y, angle, scale = transform_data

        # Apply scale
        width, height = image.size
        new_size = (int(width * scale), int(height * scale))
        transformed = image.resize(new_size, Image.Resampling.LANCZOS)

        # Apply rotation
        if angle != 0:
            transformed = transformed.rotate(
                angle, resample=Image.Resampling.BICUBIC, expand=True
            )

        return transformed
