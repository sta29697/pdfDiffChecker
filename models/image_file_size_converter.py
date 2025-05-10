from __future__ import annotations
from typing import Protocol
from pathlib import Path
from PIL import Image
from configurations.message_manager import get_message_manager

message_manager = get_message_manager()


class ImageSizeConverterInterface(Protocol):
    """Interface for image size conversion.

    This interface defines methods for converting image sizes.
    """

    def resize_image(self, image: Image.Image, width: int, height: int) -> Image.Image:
        """Resize an image to the specified dimensions.

        Args:
            image: Source image
            width: Target width
            height: Target height

        Returns:
            Resized image
        """
        ...

    def resize_image_by_percentage(
        self, image: Image.Image, percentage: float
    ) -> Image.Image:
        """Resize an image by percentage.

        Args:
            image: Source image
            percentage: Resize percentage (0.0 to 1.0)

        Returns:
            Resized image
        """
        ...

    def get_image_size(self, image: Image.Image) -> tuple[int, int]:
        """Get the size of an image.

        Args:
            image: Source image

        Returns:
            Tuple of (width, height)
        """
        ...

    def save_resized_image(
        self, image: Image.Image, output_path: Path, format: str = "PNG"
    ) -> None:
        """Save a resized image to the specified path.

        Args:
            image: Resized image
            output_path: Output file path
            format: Image format (default: PNG)
        """
        ...

    def get_supported_formats(self) -> list[str]:
        """Get supported image formats.

        Returns:
            List of supported image formats
        """
        ...


class ImageSizeConverter(ImageSizeConverterInterface):
    """Implementation of image size conversion functionality.

    This class provides methods for resizing images while maintaining aspect ratio
    and saving them in various formats.
    """

    def resize_image(self, image: Image.Image, width: int, height: int) -> Image.Image:
        """Resize an image to the specified dimensions while maintaining aspect ratio.

        Args:
            image: Source image
            width: Target width
            height: Target height

        Returns:
            Resized image with maintained aspect ratio
        """
        original_width, original_height = image.size
        aspect_ratio = original_width / original_height

        # Calculate new dimensions while maintaining aspect ratio
        if width / height > aspect_ratio:
            new_width = int(height * aspect_ratio)
            new_height = height
        else:
            new_width = width
            new_height = int(width / aspect_ratio)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def resize_image_by_percentage(
        self, image: Image.Image, percentage: float
    ) -> Image.Image:
        """Resize an image by percentage.

        Args:
            image: Source image
            percentage: Resize percentage (0.0 to 1.0)

        Returns:
            Resized image
        """
        if not 0.0 <= percentage <= 1.0:
            raise ValueError("Percentage must be between 0.0 and 1.0")

        width, height = image.size
        new_width = int(width * percentage)
        new_height = int(height * percentage)
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def get_image_size(self, image: Image.Image) -> tuple[int, int]:
        """Get the size of an image.

        Args:
            image: Source image

        Returns:
            Tuple of (width, height)
        """
        return image.size

    def save_resized_image(
        self,
        image: Image.Image,
        output_path: Path,
        format: str = "PNG",
        keep_metadata: bool = True,
    ) -> None:
        """Save a resized image to the specified path.

        Args:
            image: Resized image
            output_path: Output file path
            format: Image format (default: PNG)
            keep_metadata: Whether to keep metadata (default: True)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy metadata if requested
        if keep_metadata:
            image.save(output_path, format=format)
        else:
            # Create a new image without metadata
            new_image = Image.new(image.mode, image.size)
            new_image.paste(image)
            new_image.save(output_path, format=format)

    def get_supported_formats(self) -> list[str]:
        """Get supported image formats.

        Returns:
            List of supported image formats
        """
        return ["PNG", "JPEG", "GIF", "TIFF", "BMP"]
