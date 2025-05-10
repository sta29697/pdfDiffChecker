from __future__ import annotations
import os
from logging import getLogger
import tkinter as tk
from PIL import Image, ImageTk

from controllers.image_operations import ImageOperations
from models.file_converter import PdfFileConverter, TiffFileConverter
from widgets.create_layer_select_button import LayerSelectButton
from configurations.message_manager import get_message_manager

message_manager = get_message_manager()

logger = getLogger(__name__)

class ImageEditorView:
    def __init__(
        self, root: tk.Tk, file1_path: str, file2_path: str, temp_dir: str
    ) -> None:
        """Initialize the image editor view.

        Args:
            root (tk.Tk): Root window
            file1_path (str): Path to the first file
            file2_path (str): Path to the second file
            temp_dir (str): Directory for temporary files
        """
        self.root = root
        self.canvas = tk.Canvas(root, width=800, height=600)
        self.canvas.pack()
        # Initialized canvas for image editing
        # Log image editor view initialization
        logger.debug(message_manager.get_log_message("L152"))

        # Create file converters and convert files to PNG
        self.converter1 = PdfFileConverter(file1_path) if file1_path.endswith(".pdf") else TiffFileConverter(file1_path)
        self.converter2 = PdfFileConverter(file2_path) if file2_path.endswith(".pdf") else TiffFileConverter(file2_path)

        self.converter1.convert_to_png(temp_dir)
        self.converter2.convert_to_png(temp_dir)

        self.load_images(temp_dir, file1_path, file2_path)

        # Add layer select buttons
        button_frame = tk.Frame(root)
        button_frame.pack(side=tk.BOTTOM)
        LayerSelectButton(
            button_frame,
            1,
            command=lambda: self.select_layer(1),
            color_key="button_normal",
        ).pack(side=tk.LEFT)
        LayerSelectButton(
            button_frame,
            2,
            command=lambda: self.select_layer(2),
            color_key="button_normal",
        ).pack(side=tk.LEFT)

        # Bind canvas events
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Control-ButtonPress-1>", self.set_rotation_center)
        self.canvas.bind("<Control-B1-Motion>", self.rotate_layer)
        self.canvas.bind("<Escape>", self.reset_rotation_center)
        self.canvas.bind("<MouseWheel>", self.zoom_layer)

    def load_images(self, temp_dir: str, file1_path: str, file2_path: str) -> None:
        """Load images from the specified paths.

        Args:
            temp_dir (str): Directory for temporary files
            file1_path (str): Path to the first file
            file2_path (str): Path to the second file
        """
        img1_path = os.path.join(temp_dir, f"{os.path.basename(file1_path).split('.')[0]}_000.png")
        img2_path = os.path.join(temp_dir, f"{os.path.basename(file2_path).split('.')[0]}_000.png")

        self.image1_pil = Image.open(img1_path)
        self.image2_pil = Image.open(img2_path)

        self.image1 = ImageTk.PhotoImage(self.image1_pil)
        self.image2 = ImageTk.PhotoImage(self.image2_pil)

        self.layer1_id = self.canvas.create_image(0, 0, anchor='nw', image=self.image1)
        self.layer2_id = self.canvas.create_image(0, 0, anchor='nw', image=self.image2)

        self.image_ops = ImageOperations(self.canvas, self.layer1_id, self.image1_pil)

    def select_layer(self, layer_num: int) -> None:
        """Select the specified layer for editing.

        Args:
            layer_num (int): Layer number to select (1 or 2)
        """
        if layer_num == 1:
            self.image_ops.image_id = self.layer1_id
            self.image_ops.pil_image = self.image1_pil
        elif layer_num == 2:
            self.image_ops.image_id = self.layer2_id
            self.image_ops.pil_image = self.image2_pil

    def on_click(self, event: tk.Event) -> None:
        """Handle click events on the canvas.

        Args:
            event (tk.Event): Click event on the canvas.
        """
        # Click event: record drag start position
        self.drag_data = {"x": event.x, "y": event.y}

    def on_drag(self, event: tk.Event) -> None:
        """Handle drag events on the canvas.

        Args:
            event (tk.Event): Drag event on the canvas.
        """
        # Drag event: move image
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.image_ops.move(dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def set_rotation_center(self, event: tk.Event) -> None:
        """Set the rotation center point.

        Args:
            event (tk.Event): Ctrl-click event to set rotation center.
        """
        # Set rotation center with Ctrl + click
        self.image_ops.set_rotation_center(event.x, event.y)

    def rotate_layer(self, event: tk.Event) -> None:
        """Rotate the selected layer by dragging with Ctrl held.

        Args:
            event (tk.Event): Ctrl-drag event for rotating the selected layer.
        """
        rotation_center = self.image_ops.rotation_center
        if rotation_center is None:
            return
        # Determine rotation angle based on drag distance
        angle = (event.x - rotation_center[0]) * 0.5
        self.image_ops.rotate(angle)

    def reset_rotation_center(self, event: tk.Event) -> None:
        """Reset the rotation center point.

        Args:
            event (tk.Event): Escape key event to reset rotation center.
        """
        # Reset rotation center with Esc key
        self.image_ops.reset_rotation_center()

    def zoom_layer(self, event: tk.Event) -> None:
        """Zoom the selected layer.

        Args:
            event (tk.Event): Mouse wheel event for zooming.
        """
        # Zoom in/out with mouse wheel
        scale = 1.1 if event.delta > 0 else 0.9  # Determine scale based on wheel direction
        self.image_ops.zoom(scale)
