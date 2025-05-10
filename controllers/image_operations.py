from __future__ import annotations
from logging import getLogger
from PIL import Image, ImageTk
from tkinter import Canvas as tk_Canvas
from typing import Optional, Tuple
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
message_manager = get_message_manager()


class ImageOperations:
    """
    Handles image operations such as moving, rotating, and zooming.

    Attributes:
        canvas (tk_Canvas): The canvas widget where the image is displayed
        image_id (int): The ID of the image on the canvas
        pil_image (Image.Image): The original PIL image object
        rotation_center (Optional[Tuple[int, int]]): Center point for rotation
        angle (float): Current rotation angle
        scale (float): Current scale factor
    """

    def __init__(self, canvas: tk_Canvas, image_id: int, pil_image: Image.Image) -> None:
        """
        Initialize the ImageOperations.

        Args:
            canvas: The canvas widget
            image_id: The ID of the image on the canvas
            pil_image: The original PIL image object
        """
        self.canvas = canvas
        self.image_id = image_id
        self.pil_image = pil_image  # Original PIL image object
        self.rotation_center: Optional[Tuple[int, int]] = None
        self.angle: float = 0
        self.scale: float = 1.0

    def move(self, dx: int, dy: int) -> None:
        """
        Move the image by the specified amount.

        Args:
            dx: Horizontal movement amount
            dy: Vertical movement amount
        """
        self.canvas.move(self.image_id, dx, dy)

    def set_rotation_center(self, x: int, y: int) -> None:
        """
        Set the rotation center point.

        Args:
            x: X coordinate of the rotation center
            y: Y coordinate of the rotation center
        """
        self.rotation_center = (x, y)

    def rotate(self, angle: float) -> None:
        """
        Rotate the image by the specified angle.

        Args:
            angle: Rotation angle in degrees
        """
        self.angle += angle
        rotated_image = self.pil_image.rotate(
            self.angle, resample=Image.Resampling.BICUBIC, expand=True
        )
        self.update_image(rotated_image)

    def zoom(self, scale: float) -> None:
        """
        Zoom the image by the specified scale factor.

        Args:
            scale: Scale factor (e.g., 1.1 for 10% zoom in, 0.9 for 10% zoom out)
        """
        self.scale *= scale
        width, height = self.pil_image.size
        new_size = (int(width * self.scale), int(height * self.scale))
        resized_image = self.pil_image.resize(new_size, Image.Resampling.LANCZOS)
        self.update_image(resized_image)

    def reset_rotation_center(self) -> None:
        """Reset the rotation center point."""
        self.rotation_center = None

    def update_image(self, new_image: Image.Image) -> None:
        """
        Update the image on the canvas.

        Args:
            new_image: The new image to display
        """
        self.tk_image = ImageTk.PhotoImage(new_image)
        self.canvas.itemconfig(self.image_id, image=self.tk_image)
