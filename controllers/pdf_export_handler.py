from __future__ import annotations

import tkinter as tk
from logging import getLogger
from typing import List, Tuple, Dict, Any, TypeAlias, Final, Optional
from PIL import Image
from PIL.Image import Image as PILImage
from configurations.message_manager import get_message_manager
message_manager = get_message_manager()

logger = getLogger(__name__)

# Type aliases for better readability
TransformData: TypeAlias = Tuple[
    float, float, float, float
]  # (rotation, offset_x, offset_y, scale)
ImagePath: TypeAlias = str
PDFMetadata: TypeAlias = Dict[str, Any]

# Constants
DEFAULT_WIDTH: Final[int] = 2000
DEFAULT_HEIGHT: Final[int] = 2000
DEFAULT_OUTPUT_FILENAME: Final[str] = "final_output.pdf"


class PDFExportError(Exception):
    """Custom exception for PDF export operations.

    Args:
        message (str): Error message
        details (Optional[Dict]): Additional error details
    """

    def __init__(self, message: str, details: Optional[Dict] = None) -> None:
        super().__init__(message)
        self.details = details or {}


class PDFExportHandler:
    """Handles the export of transformed images to a single PDF file.

    This class manages:
    1. Image collection and validation
    2. PDF file creation
    3. Error handling during export process

    Args:
        base_pages (List[ImagePath]): List of base image paths
        comp_pages (List[ImagePath]): List of comparison image paths
        base_transform_data (List[TransformData]): List of base image transformation data
        comp_transform_data (List[TransformData]): List of comparison image transformation data
        output_folder (str): Path where the PDF will be saved
        pdf_metadata (PDFMetadata | None): PDF metadata (page size, etc.)
    """

    def __init__(
        self,
        base_pages: List[ImagePath],
        comp_pages: List[ImagePath],
        base_transform_data: List[TransformData],
        comp_transform_data: List[TransformData],
        output_folder: str,
        pdf_metadata: PDFMetadata | None = None,
    ) -> None:
        """Initialize the PDF export handler.

        Args:
            base_pages (List[ImagePath]): List of base image paths
            comp_pages (List[ImagePath]): List of comparison image paths
            base_transform_data (List[TransformData]): List of base image transformation data
            comp_transform_data (List[TransformData]): List of comparison image transformation data
            output_folder (str): Path where the PDF will be saved
            pdf_metadata (PDFMetadata): PDF metadata (page size, etc.)

        Raises:
            ValueError: If input lists have different lengths
            PDFExportError: If initialization fails
        """
        try:
            if len(base_pages) != len(base_transform_data):
                raise ValueError(
                    "Base pages and transformation data have different lengths"
                )
            if len(comp_pages) != len(comp_transform_data):
                raise ValueError(
                    "Comparison pages and transformation data have different lengths"
                )

            self.__base_pages = base_pages
            self.__comp_pages = comp_pages
            self.__base_transform_data = base_transform_data
            self.__comp_transform_data = comp_transform_data
            self.__output_folder = output_folder
            self.__pdf_metadata = pdf_metadata or {}

            logger.info("PDF export handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PDF export handler: {e}")
            raise PDFExportError(
                "Failed to initialize export handler", {"error": str(e)}
            )

    def export_to_pdf(self, filename: str, parent_widget: tk.Widget) -> None:
        """Export all pages to a single PDF file. Warn if file exists (balloon message, multilingual).

        Args:
            filename (str): Output PDF filename
            parent_widget (tk.Widget): Widget to show balloon message on

        Raises:
            PDFExportError: If export fails
        """
        from utils.utils import show_balloon_message
        import os
        try:
            # Get page size from metadata or use default values
            pdf_w = int(self.__pdf_metadata.get("page_width", DEFAULT_WIDTH))
            pdf_h = int(self.__pdf_metadata.get("page_height", DEFAULT_HEIGHT))

            max_pages = max(len(self.__base_pages), len(self.__comp_pages))
            if max_pages == 0:
                logger.warning("No pages to export")
                return

            sample_pages: List[PILImage] = []
            for i in range(max_pages):
                # Create a blank image with the specified size
                blank_img = Image.new("RGBA", (pdf_w, pdf_h), (255, 255, 255, 255))

                # Add base page if it exists
                if i < len(self.__base_pages):
                    r, offx, offy, scale = self.__base_transform_data[i]
                    b_path = self.__base_pages[i]
                    base_img = Image.open(b_path).convert("RGBA")
                    new_w = int(base_img.width * scale)
                    new_h = int(base_img.height * scale)
                    base_img = base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    base_img = base_img.rotate(r, expand=True)
                    blank_img.paste(base_img, (int(offx), int(offy)), base_img)

                # Add comparison page if it exists
                if i < len(self.__comp_pages):
                    r, offx, offy, scale = self.__comp_transform_data[i]
                    c_path = self.__comp_pages[i]
                    comp_img = Image.open(c_path).convert("RGBA")
                    new_w = int(comp_img.width * scale)
                    new_h = int(comp_img.height * scale)
                    comp_img = comp_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    comp_img = comp_img.rotate(r, expand=True)
                    blank_img.paste(comp_img, (int(offx), int(offy)), comp_img)

                # Convert to RGB
                final_page = blank_img.convert("RGB")
                sample_pages.append(final_page)

            # Create output directory if it doesn't exist
            if not os.path.isdir(self.__output_folder):
                os.makedirs(self.__output_folder, exist_ok=True)

            output_pdf_path = os.path.join(self.__output_folder, filename)

            # Overwrite warning (balloon, multilingual)
            if os.path.exists(output_pdf_path):
                # U_OVERWRITE_WARN: Show overwrite warning message (multilingual)
                show_balloon_message(parent_widget, message_manager.get_ui_message("U_OVERWRITE_WARN"))

            first_page, *rest = sample_pages
            first_page.save(output_pdf_path, save_all=True, append_images=rest)
            logger.info(f"Successfully exported PDF to: {output_pdf_path}")

        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            raise PDFExportError("Failed to export PDF", {"error": str(e)})

        """Export all pages to a single PDF file.

        Raises:
            PDFExportError: If export fails
        """
        try:
            # Get page size from metadata or use default values
            pdf_w = int(self.__pdf_metadata.get("page_width", DEFAULT_WIDTH))
            pdf_h = int(self.__pdf_metadata.get("page_height", DEFAULT_HEIGHT))

            max_pages = max(len(self.__base_pages), len(self.__comp_pages))
            if max_pages == 0:
                logger.warning("No pages to export")
                return

            temp_pages: List[PILImage] = []
            for i in range(max_pages):
                # Create a blank image with the specified size
                blank_img = Image.new("RGBA", (pdf_w, pdf_h), (255, 255, 255, 255))

                # Add base page if it exists
                if i < len(self.__base_pages):
                    r, offx, offy, scale = self.__base_transform_data[i]
                    b_path = self.__base_pages[i]
                    base_img = Image.open(b_path).convert("RGBA")
                    new_w = int(base_img.width * scale)
                    new_h = int(base_img.height * scale)
                    base_img = base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    base_img = base_img.rotate(r, expand=True)
                    blank_img.paste(base_img, (int(offx), int(offy)), base_img)

                # Add comparison page if it exists
                if i < len(self.__comp_pages):
                    r, offx, offy, scale = self.__comp_transform_data[i]
                    c_path = self.__comp_pages[i]
                    comp_img = Image.open(c_path).convert("RGBA")
                    new_w = int(comp_img.width * scale)
                    new_h = int(comp_img.height * scale)
                    comp_img = comp_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    comp_img = comp_img.rotate(r, expand=True)
                    blank_img.paste(comp_img, (int(offx), int(offy)), comp_img)

                # Convert to RGB
                final_page = blank_img.convert("RGB")
                temp_pages.append(final_page)

            # Create output directory if it doesn't exist
            if not os.path.isdir(self.__output_folder):
                os.makedirs(self.__output_folder, exist_ok=True)

            output_pdf_path = os.path.join(
                self.__output_folder, DEFAULT_OUTPUT_FILENAME
            )

            first_page, *rest = temp_pages
            first_page.save(output_pdf_path, save_all=True, append_images=rest)
            logger.info(f"Successfully exported PDF to: {output_pdf_path}")

        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            raise PDFExportError("Failed to export PDF", {"error": str(e)})
