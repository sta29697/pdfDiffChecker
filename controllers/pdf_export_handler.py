from __future__ import annotations

import colorsys
import tkinter as tk
from tkinter import messagebox
from logging import getLogger
from typing import List, Tuple, Dict, Any, TypeAlias, Final, Optional
from PIL import Image
from PIL.Image import Image as PILImage, Transpose
import numpy as np
from configurations.message_manager import get_message_manager
from utils.transform_tuple import as_transform6

message_manager = get_message_manager()

logger = getLogger(__name__)

# Type aliases for better readability
TransformData: TypeAlias = Tuple[float, ...]  # (r, offx, offy, scale[, flip_h, flip_v])
ImagePath: TypeAlias = str
PDFMetadata: TypeAlias = Dict[str, Any]

# Constants
DEFAULT_WIDTH: Final[int] = 2000
DEFAULT_HEIGHT: Final[int] = 2000
DEFAULT_OUTPUT_FILENAME: Final[str] = "final_output.pdf"


def _hex_to_rgba(hex_color: Optional[str]) -> tuple[int, int, int, int]:
    """Convert a hex color string into an RGBA tuple.

    Args:
        hex_color: Color such as ``"#3366ff"``.

    Returns:
        RGBA tuple with alpha fixed at ``255``.
    """
    normalized = str(hex_color or "").strip()
    if normalized.startswith("#"):
        normalized = normalized[1:]
    if len(normalized) != 6:
        return (0, 0, 0, 255)
    try:
        return (
            int(normalized[0:2], 16),
            int(normalized[2:4], 16),
            int(normalized[4:6], 16),
            255,
        )
    except ValueError:
        return (0, 0, 0, 255)


def _selected_color_hsv_components(hex_color: Optional[str]) -> tuple[float, float]:
    """Return HSV hue and saturation derived from the selected color.

    Args:
        hex_color: Selected palette color.

    Returns:
        Tuple of hue and saturation in the range ``0.0`` to ``1.0``.
    """
    red, green, blue, _alpha = _hex_to_rgba(hex_color)
    hue, saturation, _value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
    return hue, saturation


def apply_color_processing_to_image(
    page_image: PILImage,
    mode: str,
    selected_color: Optional[str],
    threshold: Optional[int] = None,
) -> PILImage:
    """Apply main-tab color processing to one image.

    Args:
        page_image: Source page image.
        mode: Processing mode name.
        selected_color: Hex color selected from the palette button.
        threshold: Optional RGB-total threshold for binary mode.

    Returns:
        Processed ``RGBA`` image.
    """
    rgba_image = page_image.convert("RGBA") if page_image.mode != "RGBA" else page_image.copy()
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode in {"original", "none", "off", "raw"}:
        return rgba_image
    pixel_array = np.asarray(rgba_image, dtype=np.uint8)
    rgb_total = pixel_array[:, :, 0].astype(np.uint16) + pixel_array[:, :, 1].astype(np.uint16) + pixel_array[:, :, 2].astype(np.uint16)
    alpha_channel = pixel_array[:, :, 3]

    if mode == "二色化":
        resolved_threshold = max(0, min(765, int(765 if threshold is None else threshold)))
        selected_rgba = np.array(_hex_to_rgba(selected_color), dtype=np.uint8)
        colored_mask = (alpha_channel > 0) & (rgb_total <= resolved_threshold)

        processed = np.zeros_like(pixel_array, dtype=np.uint8)
        processed[colored_mask, 0] = selected_rgba[0]
        processed[colored_mask, 1] = selected_rgba[1]
        processed[colored_mask, 2] = selected_rgba[2]
        processed[colored_mask, 3] = selected_rgba[3]
        return Image.fromarray(processed, mode="RGBA")

    grayscale_source = np.asarray(rgba_image.convert("L"), dtype=np.uint8)
    selected_rgba = np.array(_hex_to_rgba(selected_color), dtype=np.uint8)
    selected_rgb = selected_rgba[:3].astype(np.float32) / 255.0

    processed = np.zeros_like(pixel_array, dtype=np.uint8)

    # Main processing: preserve white paper as a very light tint and map dark strokes to a dark selected-color shade.
    if np.max(selected_rgb) <= 1e-6:
        processed[:, :, 0] = grayscale_source
        processed[:, :, 1] = grayscale_source
        processed[:, :, 2] = grayscale_source
        processed[:, :, 3] = alpha_channel
        return Image.fromarray(processed, mode="RGBA")

    lightness_channel = grayscale_source.astype(np.float32) / 255.0
    darkness_channel = 1.0 - lightness_channel
    light_tint_strength = 0.03
    darkness_gamma = 0.55

    light_tint_rgb = 1.0 - ((1.0 - selected_rgb) * light_tint_strength)
    ink_weight = np.power(darkness_channel, darkness_gamma)
    shaded_rgb = (light_tint_rgb[None, None, :] * (1.0 - ink_weight[:, :, None])) + (
        selected_rgb[None, None, :] * ink_weight[:, :, None]
    )

    processed[:, :, 0] = np.clip(shaded_rgb[:, :, 0] * 255.0, 0, 255).astype(np.uint8)
    processed[:, :, 1] = np.clip(shaded_rgb[:, :, 1] * 255.0, 0, 255).astype(np.uint8)
    processed[:, :, 2] = np.clip(shaded_rgb[:, :, 2] * 255.0, 0, 255).astype(np.uint8)
    processed[:, :, 3] = alpha_channel
    return Image.fromarray(processed, mode="RGBA")


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
        color_processing_mode: str = "指定色濃淡",
        base_selected_color: Optional[str] = None,
        comparison_selected_color: Optional[str] = None,
        base_threshold: int = 700,
        comparison_threshold: int = 700,
        show_base_layer: bool = True,
        show_comp_layer: bool = True,
    ) -> None:
        """Initialize the PDF export handler.

        Args:
            base_pages (List[ImagePath]): List of base image paths
            comp_pages (List[ImagePath]): List of comparison image paths
            base_transform_data (List[TransformData]): List of base image transformation data
            comp_transform_data (List[TransformData]): List of comparison image transformation data
            output_folder (str): Path where the PDF will be saved
            pdf_metadata (PDFMetadata): PDF metadata (page size, etc.)
            color_processing_mode: Active main-tab color processing mode.
            base_selected_color: Selected color for the base layer.
            comparison_selected_color: Selected color for the comparison layer.
            base_threshold: Threshold for the base layer in binary mode.
            comparison_threshold: Threshold for the comparison layer in binary mode.
            show_base_layer: Whether the base layer is currently visible.
            show_comp_layer: Whether the comparison layer is currently visible.

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
            self.__color_processing_mode = color_processing_mode
            self.__base_selected_color = base_selected_color
            self.__comparison_selected_color = comparison_selected_color
            self.__base_threshold = int(base_threshold)
            self.__comparison_threshold = int(comparison_threshold)
            self.__show_base_layer = bool(show_base_layer)
            self.__show_comp_layer = bool(show_comp_layer)

            logger.info("PDF export handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PDF export handler: {e}")
            raise PDFExportError(
                "Failed to initialize export handler", {"error": str(e)}
            )

    def _export_source_page_size(
        self, page_index: int, fallback_w: int, fallback_h: int
    ) -> tuple[int, int]:
        """Return raster width/height for one page index from disk, or metadata fallback."""
        if page_index < len(self.__base_pages):
            try:
                with Image.open(self.__base_pages[page_index]) as im:
                    return int(im.width), int(im.height)
            except Exception:
                pass
        if page_index < len(self.__comp_pages):
            try:
                with Image.open(self.__comp_pages[page_index]) as im:
                    return int(im.width), int(im.height)
            except Exception:
                pass
        return int(fallback_w), int(fallback_h)

    def _compose_one_export_page(self, page_index: int, fallback_w: int, fallback_h: int) -> PILImage:
        """Composite visible layers for one page using a tight canvas (handles sheet rotation).

        Args:
            page_index: Zero-based page index.
            fallback_w: Default canvas width when no layer is drawn.
            fallback_h: Default canvas height when no layer is drawn.

        Returns:
            RGB image for that PDF page.
        """
        pw, ph = self._export_source_page_size(page_index, fallback_w, fallback_h)
        boxes: List[tuple[int, int, int, int]] = []
        base_paste: Optional[tuple[PILImage, int, int]] = None
        comp_paste: Optional[tuple[PILImage, int, int]] = None

        if self.__show_base_layer and page_index < len(self.__base_pages):
            r, offx, offy, scale, flip_h, flip_v = as_transform6(self.__base_transform_data[page_index])
            base_img = Image.open(self.__base_pages[page_index]).convert("RGBA")
            base_img = apply_color_processing_to_image(
                base_img,
                self.__color_processing_mode,
                self.__base_selected_color,
                self.__base_threshold,
            )
            if flip_v:
                base_img = base_img.transpose(Transpose.FLIP_TOP_BOTTOM)
            if flip_h:
                base_img = base_img.transpose(Transpose.FLIP_LEFT_RIGHT)
            base_img = base_img.rotate(r, expand=True)
            new_w = int(base_img.width * scale)
            new_h = int(base_img.height * scale)
            base_img = base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            ox, oy = int(round(offx)), int(round(offy))
            boxes.append((ox, oy, ox + base_img.width, oy + base_img.height))
            base_paste = (base_img, ox, oy)

        if self.__show_comp_layer and page_index < len(self.__comp_pages):
            r, offx, offy, scale, flip_h, flip_v = as_transform6(self.__comp_transform_data[page_index])
            comp_img = Image.open(self.__comp_pages[page_index]).convert("RGBA")
            comp_img = apply_color_processing_to_image(
                comp_img,
                self.__color_processing_mode,
                self.__comparison_selected_color,
                self.__comparison_threshold,
            )
            if flip_v:
                comp_img = comp_img.transpose(Transpose.FLIP_TOP_BOTTOM)
            if flip_h:
                comp_img = comp_img.transpose(Transpose.FLIP_LEFT_RIGHT)
            comp_img = comp_img.rotate(r, expand=True)
            new_w = int(comp_img.width * scale)
            new_h = int(comp_img.height * scale)
            comp_img = comp_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            if self.__show_base_layer:
                alpha_channel = comp_img.getchannel("A")
                softened_alpha = alpha_channel.point(lambda value: int(value * 150 / 255))
                comp_img.putalpha(softened_alpha)
            ox, oy = int(round(offx)), int(round(offy))
            boxes.append((ox, oy, ox + comp_img.width, oy + comp_img.height))
            comp_paste = (comp_img, ox, oy)

        if not boxes:
            return Image.new("RGBA", (pw, ph), (255, 255, 255, 255)).convert("RGB")

        min_x = min(b[0] for b in boxes)
        min_y = min(b[1] for b in boxes)
        max_x = max(b[2] for b in boxes)
        max_y = max(b[3] for b in boxes)
        bw = max(1, max_x - min_x)
        bh = max(1, max_y - min_y)
        blank_img = Image.new("RGBA", (bw, bh), (255, 255, 255, 255))
        if base_paste is not None:
            bi, bx, by = base_paste
            blank_img.paste(bi, (bx - min_x, by - min_y), bi)
        if comp_paste is not None:
            ci, cx, cy = comp_paste
            blank_img.paste(ci, (cx - min_x, cy - min_y), ci)
        return blank_img.convert("RGB")

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
            try:
                pdf_resolution = float(self.__pdf_metadata.get("dpi", 72) or 72)
            except (TypeError, ValueError):
                pdf_resolution = 72.0
            if pdf_resolution <= 0:
                pdf_resolution = 72.0

            max_pages = max(len(self.__base_pages), len(self.__comp_pages))
            if max_pages == 0:
                logger.warning("No pages to export")
                return

            sample_pages: List[PILImage] = []
            for i in range(max_pages):
                sample_pages.append(self._compose_one_export_page(i, pdf_w, pdf_h))

            # Create output directory if it doesn't exist
            if not os.path.isdir(self.__output_folder):
                os.makedirs(self.__output_folder, exist_ok=True)

            output_pdf_path = os.path.join(self.__output_folder, filename)

            # Main processing: warn immediately before overwriting an existing file.
            if os.path.exists(output_pdf_path):
                messagebox.showwarning(
                    message_manager.get_ui_message("U033"),
                    message_manager.get_ui_message("U_OVERWRITE_WARN"),
                    parent=parent_widget.winfo_toplevel(),
                )

            first_page, *rest = sample_pages
            # Main processing: preserve the original raster DPI so scale changes stay consistent after re-opening the PDF.
            first_page.save(
                output_pdf_path,
                save_all=True,
                append_images=rest,
                resolution=pdf_resolution,
            )
            logger.info(f"Successfully exported PDF to: {output_pdf_path}")

        except Exception as e:
            logger.error(f"Failed to export PDF: {e}")
            raise PDFExportError("Failed to export PDF", {"error": str(e)})
