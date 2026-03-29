from __future__ import annotations

import os
from logging import getLogger
import tkinter as tk
import numpy as np
from PIL import Image, ImageOps, ImageFile
from typing import Any, Dict, Optional, Protocol, Tuple, TypedDict, cast

# Import PyPDFium2 for PDF rendering
try:
    import pypdfium2 as pdfium
    HAVE_PYPDFIUM2 = True
except ImportError:
    HAVE_PYPDFIUM2 = False

# Import PyPDF for metadata extraction (optional)
try:
    from pypdf import PdfReader
    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False

from configurations.message_manager import get_message_manager
from models.class_dictionary import FilePathInfo
from utils import utils
from widgets.progress_window import ProgressWindow

message_manager = get_message_manager()

logger = getLogger(__name__)


def _extract_embedded_dpi_from_pypdf_page(
    page: Any,
    page_width_pt: float,
    page_height_pt: float,
) -> Optional[Tuple[int, int]]:
    """Infer effective DPI from the largest embedded image vs page MediaBox (points).

    Matches the logic used in ``image_ope_tab`` so PDF Operation footer can show the
    same embedded-resolution hint as the extension tab.

    Args:
        page: First page object from ``pypdf.PdfReader.pages``.
        page_width_pt: Page width in PDF points.
        page_height_pt: Page height in PDF points.

    Returns:
        ``(dpi_x, dpi_y)`` when derivable, otherwise ``None``.
    """
    if page_width_pt <= 0 or page_height_pt <= 0:
        return None
    try:
        resources = page.get("/Resources")
        if resources is None or "/XObject" not in resources:
            return None
        xobjects = resources["/XObject"].get_object()
    except Exception:
        return None

    max_area = 0
    best_width = 0
    best_height = 0

    for xobj_ref in xobjects.values():
        try:
            xobj = xobj_ref.get_object()
        except Exception:
            continue
        if xobj.get("/Subtype") != "/Image":
            continue
        try:
            img_width = int(xobj.get("/Width", 0) or 0)
            img_height = int(xobj.get("/Height", 0) or 0)
        except Exception:
            continue
        area = img_width * img_height
        if area > max_area:
            max_area = area
            best_width = img_width
            best_height = img_height

    if max_area <= 0 or best_width <= 0 or best_height <= 0:
        return None

    dpi_x = int(round(best_width * 72.0 / page_width_pt))
    dpi_y = int(round(best_height * 72.0 / page_height_pt))
    if dpi_x <= 0 or dpi_y <= 0:
        return None
    return dpi_x, dpi_y


def _merge_embedded_pdf_dpi_into_meta(reader: Any, file_meta: Dict[str, Any]) -> None:
    """Store embedded page DPI hints into ``file_meta`` when PyPDF is available.

    Args:
        reader: ``PdfReader`` instance positioned on the target file.
        file_meta: ``FilePathInfo.file_meta_info`` dictionary to update in place.
    """
    try:
        if len(reader.pages) < 1:
            return
        page0 = reader.pages[0]
        mb = page0.mediabox
        page_w_pt = float(mb.width)
        page_h_pt = float(mb.height)
        pair = _extract_embedded_dpi_from_pypdf_page(page0, page_w_pt, page_h_pt)
        if pair:
            file_meta["embedded_page_dpi_x"] = pair[0]
            file_meta["embedded_page_dpi_y"] = pair[1]
            file_meta["embedded_page_dpi"] = pair[0]
    except Exception:
        return


class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Args:
        current (int): Current progress value
        total (int): Total progress value
        message (Optional[str]): Optional status message

    Returns:
        None
    """

    def __call__(
        self, current: int, total: int, message: Optional[str] = None
    ) -> None: ...


class ProgressWindowAdapter:
    """Adapter class to use ProgressWindow as a ProgressCallback.

    This class adapts the ProgressWindow class to be used with functions
    that expect a ProgressCallback.
    """

    def __init__(self, progress_window: Optional[ProgressWindow] = None) -> None:
        """Initialize the adapter.

        Args:
            progress_window: Optional ProgressWindow instance. If None, callbacks will be ignored.
        """
        self.progress_window = progress_window

    def __call__(self, current: int, total: int, message: Optional[str] = None) -> None:
        """Callback function that updates the progress window.

        Args:
            current: Current progress value
            total: Total progress value
            message: Optional status message
        """
        if self.progress_window is not None:
            # Calculate percentage (0-100)
            percentage = int((current / total) * 100) if total > 0 else 0

            # Update progress window
            self.progress_window.update_progress(percentage, message)

            logger.debug(
                message_manager.get_log_message("L314", percentage, current, total, message)
            )


class ColorKey(TypedDict):
    """Color key configuration for binarization.

    Attributes:
        r (int): Red component (0-255)
        g (int): Green component (0-255)
        b (int): Blue component (0-255)
        a (int): Alpha component (0-255)
    """

    r: int
    g: int
    b: int
    a: int


class BaseImageConverter:
    """Base class for converting multi-page image files (PDF, TIFF) to grayscale PNGs.

    This class provides:
    1. Common workflow for image conversion
    2. Data storage for converted images
    3. Temporary file management
    4. Progress tracking capabilities

    Attributes:
        file_info (FilePathInfo): File information
        _temp_dir (str): Temporary directory for storing intermediate files
        _file_temp_dir (str | None): File-specific temporary directory
        _name_flag (str): Flag indicating 'base' or 'comp' file type
    """

    def __init__(self, file_info: FilePathInfo, name_flag: str) -> None:
        """Initialize the converter with file information.

        Args:
            file_info (FilePathInfo): File information
            name_flag (str): Flag indicating 'base' or 'comp' file type
        """
        self.file_info = file_info
        self._name_flag = name_flag
        
        # Initialize directory references - actual creation will happen in derived classes
        self._temp_dir = ""  # Empty string instead of None to match type definition
        self._file_temp_dir = None
        
        # Store the original flag for internal reference
        self._original_flag = name_flag

        # Initialize histogram data if None
        if self.file_info.file_histogram_data is None:
            self.file_info.file_histogram_data = []
            
        # Log completion of initialization - Not logging directory yet as it's not created
        # This will be logged after directory creation in derived classes
        logger.info(message_manager.get_log_message("L304"))

    def _save_page(self, page_img: Image.Image, page_num: int, name_flag: str) -> None:
        """Save a single page image in PNG format to the temp folder.

        Args:
            page_img (Image.Image): Source image to save
            page_num (int): Page number
            name_flag (str): Internal flag for tracking source type ('base' or 'comp')
        """
        # Save with appropriate mode to preserve transparency if present
        # If already in RGBA mode, keep it; otherwise convert to grayscale
        if page_img.mode == 'RGBA':
            # Keep transparency information
            img_to_save = page_img
        else:
            # Convert to grayscale for non-transparent images
            img_to_save = ImageOps.grayscale(page_img)
        
        # Check if temp directory is available
        if not self._temp_dir:  # Check for empty string instead of None
            # Log error and raise exception (using E022 for temp directory not set error)
            logger.error(message_manager.get_log_message("L013", message_manager.get_message("E022")))
            raise ValueError(message_manager.get_message("E022"))
            
        # Save to custom temp subdirectory with appropriate naming
        filename = self._generate_filename(name_flag, page_num)
        output_path = os.path.join(self._temp_dir, filename)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save the image with appropriate format
        if img_to_save.mode == 'RGBA':
            img_to_save.save(output_path, 'PNG')
        else:
            img_to_save.save(output_path)
        
        # Log the saved file path with appropriate message (NOT an error)
        logger.debug(message_manager.get_log_message("L306", page_num, output_path))

        # Calculate and store histogram data for later analysis
        try:
            histogram = self._build_rgb_total_histogram(img_to_save)
            if self.file_info.file_histogram_data is None:
                self.file_info.file_histogram_data = []
            self.file_info.file_histogram_data.append(histogram)
        except Exception as e:
            logger.error(message_manager.get_log_message("L055", str(e)))

    def _build_rgb_total_histogram(self, page_img: Image.Image) -> list[int]:
        """Build a histogram whose bins represent the RGB total from 0 to 765.

        Args:
            page_img (Image.Image): Source page image.

        Returns:
            list[int]: Histogram counts indexed by ``R + G + B``.
        """
        if page_img.mode not in ("RGB", "RGBA"):
            rgb_image = page_img.convert("RGB")
        else:
            rgb_image = page_img.convert("RGB")

        rgb_array = np.asarray(rgb_image, dtype=np.uint16)
        if rgb_array.ndim != 3 or rgb_array.shape[2] < 3:
            grayscale_array = np.asarray(rgb_image.convert("L"), dtype=np.uint16)
            rgb_total = grayscale_array * 3
        else:
            rgb_total = rgb_array[:, :, 0] + rgb_array[:, :, 1] + rgb_array[:, :, 2]

        histogram = np.bincount(rgb_total.reshape(-1), minlength=766)
        return histogram.astype(int).tolist()

    def _generate_filename(self, name_flag: str, page_num: int) -> str:
        """Generate a filename for each page using the specified naming convention.

        Args:
            name_flag (str): Internal flag for tracking source type ('base' or 'comp')
            page_num (int): Page number

        Returns:
            str: Generated filename
        """
        # Use the expected naming convention that the main tab is looking for
        # Format: base_0001.png or comp_0001.png
        return f"{name_flag}_{page_num:04d}.png"

    def convert_to_grayscale_pngs(
        self, progress_callback: Optional[ProgressCallback] = None, **kwargs: Any
    ) -> None:
        """Convert the file to grayscale PNG pages.

        This method should be implemented by subclasses.

        Args:
            progress_callback: Optional callback for progress reporting
            **kwargs: Additional arguments for specific converters
        """
        raise NotImplementedError(message_manager.get_error_message("E103"))

    def process_with_progress_window(
        self, parent_widget: tk.Widget, **kwargs: Any
    ) -> None:
        """Process the file with a progress window.

        This method creates a progress window and calls the convert_to_grayscale_pngs
        method with a progress callback.

        Args:
            parent_widget: Parent widget for the progress window
            **kwargs: Additional arguments to pass to convert_to_grayscale_pngs
        """
        # Create progress window
        progress_window = ProgressWindow(parent_widget)
        progress_window.show()

        try:
            # Create progress callback
            progress_callback = ProgressWindowAdapter(progress_window)

            # Convert file to grayscale PNGs
            self.convert_to_grayscale_pngs(
                progress_callback=progress_callback, **kwargs
            )

        except Exception as e:
            logger.error(message_manager.get_log_message("L056", str(e)))
            # Show error message in progress window
            if progress_window:
                progress_window.update_progress(100, f"Error: {str(e)}")

            # Re-raise exception
            raise

        finally:
            # Hide progress window after a short delay
            if progress_window:
                try:
                    progress_window.grab_release()
                except Exception:
                    pass
                parent_widget.after(1000, progress_window.hide)
                parent_widget.after(1500, progress_window.destroy)


class Pdf2PngByPages(BaseImageConverter):
    """Class for converting PDF files to grayscale PNG pages with transparency.

    This class uses PyPDFium2 to render PDF pages to PNG images with
    transparency support.

    Attributes:
        file_info (FilePathInfo): Information about the PDF file
    """

    def __init__(
        self, 
        pdf_obj: FilePathInfo, 
        program_mode: bool = False, 
        name_flag: str = "base"
    ) -> None:
        """Initialize the converter with PDF file information.

        Args:
            pdf_obj: Information about the PDF file
            program_mode: Whether the program is running in production mode
            name_flag: Flag indicating 'base' or 'comp' file type
        """
        super().__init__(pdf_obj, name_flag)
        
        # Create a temporary directory for this PDF file
        pdf_file_name = os.path.basename(str(self.file_info.file_path))
        # Get directory path and explicitly set as str (not None)
        self._temp_dir = cast(str, utils.create_directories(pdf_file_name))
        
        # Extract metadata and page count
        self._extract_metadata()
        
        # Log initialization
        logger.info(message_manager.get_log_message("L315", self.file_info.file_path))
    
    def _extract_metadata(self) -> None:
        """Extract metadata from PDF file.
        
        Stores the metadata in file_info.file_meta_info dictionary.
        Uses PyPDF if available, otherwise falls back to PyPDFium2.
        """
        # Store source file path for debugging and referencing
        self.file_info.file_meta_info["source_file"] = str(self.file_info.file_path)
        self.file_info.file_meta_info["temp_dir"] = str(self._temp_dir)
        
        # Store timestamp to help with cleanup later
        import time
        self.file_info.file_meta_info["timestamp"] = time.time()
        
        # Try PyPDF first if available
        # Use LogThrottle to prevent excessive logging of metadata extraction
        if not hasattr(self, '_metadata_log_throttle'):
            from utils.log_throttle import LogThrottle
            self._metadata_log_throttle = LogThrottle(min_interval=10.0)  # 10秒間隔で制限
            
        if self._metadata_log_throttle.should_log("metadata_extraction"):
            logger.info(message_manager.get_log_message("L334"))
            
        if HAVE_PYPDF:
            try:
                logger.info(message_manager.get_log_message("L316", self.file_info.file_path))
                reader = PdfReader(str(self.file_info.file_path))
                
                # Extract basic metadata
                if hasattr(reader, "metadata") and reader.metadata:
                    info = reader.metadata
                    
                    # Extract basic metadata
                    metadata = {
                        "Title": getattr(info, "title", None),
                        "Author": getattr(info, "author", None),
                        "Creator": getattr(info, "creator", None),
                        "Producer": getattr(info, "producer", None),
                        "Subject": getattr(info, "subject", None),
                        "Keywords": getattr(info, "keywords", None),
                        "NumberOfPages": len(reader.pages),
                        "Encrypted": reader.is_encrypted,
                        "CopyProtected": bool(reader.is_encrypted),
                    }
                else:
                    # Fallback if metadata is not available
                    metadata = {
                        "NumberOfPages": len(reader.pages),
                        "Encrypted": reader.is_encrypted,
                        "CopyProtected": bool(reader.is_encrypted),
                    }
                
                # Update file_info metadata
                self.file_info.file_meta_info.update(metadata)
                
                # Set page count
                self.file_info.file_page_count = len(reader.pages)

                # Main processing: derive embedded image DPI vs MediaBox (same idea as image tab).
                _merge_embedded_pdf_dpi_into_meta(reader, self.file_info.file_meta_info)

                # Log metadata extraction
                logger.info(message_manager.get_log_message("L307", str(metadata)))
                return
            except Exception as e:
                # Log metadata extraction error
                logger.error(message_manager.get_log_message("L308", str(e)))
                # Continue to fallback
        else:
            # Log warning about PyPDF not being available
            logger.warning(message_manager.get_log_message("L309"))
            
        # Fallback to PyPDFium2
        try:
            if HAVE_PYPDFIUM2:
                # Falling back to PyPDFium2 for metadata extraction
                logger.info(message_manager.get_log_message("L333"))
                logger.info(message_manager.get_log_message("L317"))
                pdf = pdfium.PdfDocument(str(self.file_info.file_path))
                page_count = len(pdf)

                encrypted = False
                copy_protected = False
                try:
                    import pypdfium2.raw as pdfium_raw

                    security_rev = int(pdfium_raw.FPDF_GetSecurityHandlerRevision(pdf.raw))
                    encrypted = security_rev != -1

                    permissions: int | None = None
                    try:
                        permissions = int(pdfium_raw.FPDF_GetDocUserPermissions(pdf.raw))
                    except Exception:
                        try:
                            permissions = int(pdfium_raw.FPDF_GetDocPermissions(pdf.raw))
                        except Exception:
                            permissions = None

                    if encrypted and permissions is not None:
                        copy_allowed = bool(permissions & 0x10)
                        copy_protected = not copy_allowed
                    else:
                        copy_protected = encrypted
                except Exception:
                    encrypted = False
                    copy_protected = False
                
                # Basic metadata from PyPDFium2
                logger.info(message_manager.get_log_message("L337"))
                metadata = {
                    "NumberOfPages": page_count,
                    "Library": "PyPDFium2",
                    "Pages": page_count,  # Duplicate for uniformity
                    "Encrypted": encrypted,
                    "CopyProtected": copy_protected,
                }
                
                # Update file_info metadata
                logger.info(message_manager.get_log_message("L335"))
                self.file_info.file_meta_info.update(metadata)
                
                # Set page count
                logger.info(message_manager.get_log_message("L336", page_count))
                self.file_info.file_page_count = page_count
                
                # Print the metadata for debugging - page count summary
                logger.info(message_manager.get_log_message("L318", page_count))
                
                # Detailed metadata logging - full metadata contents for debugging
                logger.debug(message_manager.get_log_message("L319", str(metadata)))
                logger.debug(message_manager.get_log_message("L320", str(self.file_info.file_meta_info)))
                
                # Close the PDF file
                pdf.close()
                logger.info(message_manager.get_log_message("L321"))
            else:
                logger.error(message_manager.get_log_message("L322"))
                self.file_info.file_page_count = 0
        except Exception as e:
            # Error getting page count with PyPDFium2
            logger.error(message_manager.get_log_message("L323", str(e)))
            self.file_info.file_page_count = 0

    def get_metadata(self) -> Dict[str, Any]:
        """Extract metadata from the PDF file using PyPDFium2 or PyPDF.

        Returns:
            Dict[str, Any]: Metadata dictionary
        """
        # This is now just a wrapper around _extract_metadata, which is called at initialization
        # Return a copy of the metadata dict for safety
        return dict(self.file_info.file_meta_info)

    def convert_to_grayscale_pngs(
        self, progress_callback: Optional[ProgressCallback] = None, **kwargs: Any
    ) -> None:
        """Convert PDF to PNG files with transparency support using PyPDFium2.

        Renders each PDF page to a PNG image with transparent background.

        Args:
            progress_callback: Callback for progress updates
            **kwargs: Additional arguments like scale, dpi, etc.
        """
        # Log metadata only if available
        if self.file_info.file_meta_info:
            logger.info(message_manager.get_log_message("L060", str(self.file_info.file_meta_info)))

        try:
            # Get PDF file path
            pdf_path = str(self.file_info.file_path)
            # Processing PDF file path
            logger.info(message_manager.get_log_message("L338", pdf_path))
            page_count = self.file_info.file_page_count
            
            if page_count == 0:
                # No pages found in PDF file
                logger.error(message_manager.get_log_message("L324"))
                raise ValueError(message_manager.get_error_message("E101"))

            start_page = int(kwargs.get("start_page", 1) or 1)
            end_page = int(kwargs.get("end_page", page_count) or page_count)
            start_page = max(1, min(page_count, start_page))
            end_page = max(start_page, min(page_count, end_page))
            
            # Calculate scale factor (1.0 = 72 DPI, standard PDF resolution)
            # User can override with kwargs
            dpi = kwargs.get("dpi", 150)
            # Calculating scale factor for DPI
            logger.info(message_manager.get_log_message("L339", dpi))
            # If custom DPI is specified, override the scale factor
            if "dpi" in kwargs:
                # Using custom DPI value from user override
                logger.info(message_manager.get_log_message("L340", kwargs["dpi"]))
                scale = kwargs["dpi"] / 72.0  # Convert DPI to scale factor
            else:
                scale = dpi / 72.0  # Convert DPI to scale factor
            
            # Log page count and scale
            logger.info(message_manager.get_log_message("L325", page_count, dpi, f"{scale:.2f}"))
            
            # Check if PyPDFium2 is available
            if not HAVE_PYPDFIUM2:
                logger.error(message_manager.get_log_message("L326"))
                raise ImportError(message_manager.get_error_message("E102"))
            # Open the PDF document with PyPDFium2
            pdf = pdfium.PdfDocument(pdf_path)
            
            # Process each page
            for page_num in range(start_page, end_page + 1):
                if progress_callback:
                    progress_callback(page_num, page_count, 
                                     message_manager.get_log_message("L310", page_num, page_count))
                
                try:
                    # Set up file paths
                    name_flag = self._get_name_flag()
                    target_filename = self._generate_filename(name_flag, page_num)
                    target_path = os.path.join(str(self._temp_dir), target_filename)
                    
                    logger.info(message_manager.get_log_message("L332", page_num, target_path))
                    
                    # Get the page from the PDF (0-based index)
                    pdf_page = pdf.get_page(page_num - 1)
                    
                    # Render the page to a PIL Image with transparent background
                    bitmap = pdf_page.render(
                        scale=scale,           # Scale factor based on DPI
                        rotation=0,            # No rotation
                        crop=(0, 0, 0, 0)      # No cropping
                    )
                    
                    # Convert to PIL image - API changed in newer versions
                    logger.debug(message_manager.get_log_message("L331"))
                    try:
                        # Main processing: render normally and compose later.
                        # The 'colour' parameter can yield fully transparent results on some environments.
                        pil_image = bitmap.to_pil()
                        logger.debug(message_manager.get_log_message("L330"))

                        # If we need transparency, convert to RGBA
                        if pil_image.mode != 'RGBA':
                            pil_image = pil_image.convert('RGBA')
                    except Exception as e:
                        # Error converting PDF bitmap to PIL
                        logger.error(message_manager.get_log_message("L341", str(e)))
                        # Last resort fallback
                        pil_image = Image.new('RGBA', bitmap.size, (255, 255, 255, 255))
                    
                    # Optionally convert to grayscale if specified
                    if kwargs.get("grayscale", False):
                        pil_image = ImageOps.grayscale(pil_image)
                        # Convert back to RGBA after grayscale conversion to preserve transparency
                        pil_image = pil_image.convert('RGBA')

                    # Main processing: ensure the rendered page is visible on white background
                    if pil_image.mode != "RGBA":
                        pil_image = pil_image.convert("RGBA")
                    white_bg = Image.new("RGBA", pil_image.size, (255, 255, 255, 255))
                    try:
                        white_bg.alpha_composite(pil_image)
                        pil_image = white_bg
                    except Exception:
                        pil_image = white_bg
                    
                    # Main processing: persist a single PNG series per converter side.
                    self._save_page(pil_image, page_num, name_flag)
                    
                    logger.info(message_manager.get_log_message("L328", page_num, page_count))
                    
                except Exception as e:
                    # Handle individual page errors
                    # Error converting PDF page
                    logger.error(message_manager.get_log_message("L342", page_num, str(e)))
                    
                    # Create a fallback image with light gray background
                    blank_img = cast(ImageFile.ImageFile, Image.new('RGBA', (595, 842), (240, 240, 240, 255)))
                    
                    # Main processing: persist only the fallback page needed by this converter side.
                    self._save_page(blank_img, page_num, name_flag)
            
            # Clean up resources
            pdf.close()
            
            # Notify completion
            if progress_callback:
                progress_callback(page_count, page_count, "Conversion complete")
            
            # Successfully converted all pages from PDF to PNG
            logger.info(message_manager.get_log_message("L311"))

        except Exception as e:
            logger.error(message_manager.get_log_message("L056", str(e)))
            raise

    def _get_name_flag(self) -> str:
        """Get the name flag based on the file path.

        Returns:
            str: Name flag ('base' or 'comp')
        """
        _path_str = str(self.file_info.file_path).lower()
        if "base" in _path_str:
            return "base"
        elif "comp" in _path_str:
            return "comp"
        else:
            return self._name_flag


class Tiff2PngByPages(BaseImageConverter):
    """Class for converting TIFF files to grayscale PNG pages.

    Attributes:
        _tiff_file_obj (FilePathInfo): TIFF file information
    """

    def __init__(self, tiff_obj: FilePathInfo, program_mode: bool = False, name_flag: str = "base") -> None:
        """Initialize the converter with TIFF file information.

        Args:
            tiff_obj (FilePathInfo): TIFF file information
            program_mode (bool): Whether the program is running in production mode
            name_flag (str): Flag indicating 'base' or 'comp' file type
        """
        super().__init__(tiff_obj, name_flag)
        self.__tiff_file_obj = tiff_obj
        
        # Create a temporary directory for this TIFF file
        tiff_file_name = os.path.basename(str(self.file_info.file_path))
        # Get directory path and explicitly set as str (not None)
        self._temp_dir = cast(str, utils.create_directories(tiff_file_name))

    def convert_to_grayscale_pngs(
        self, progress_callback: Optional[ProgressCallback] = None, **kwargs: Any
    ) -> None:
        """Convert the TIFF file to grayscale PNG pages.

        Args:
            progress_callback (Optional[ProgressCallback]): Progress callback function
            **kwargs: Additional arguments for specific converters
        """
        self.file_info.file_meta_info["source_format"] = "TIFF"
        self.file_info.file_meta_info["library"] = f"Pillow {Image.__version__}"

        tiff_path = self.__tiff_file_obj.file_path

        try:
            # Load the TIFF file
            if progress_callback:
                progress_callback(0, 100, "Loading TIFF file...")

            with Image.open(tiff_path) as tiff_img:
                page_index = 0
                total_frames = getattr(tiff_img, "n_frames", 1)

                if progress_callback:
                    progress_callback(10, 100, f"Processing {total_frames} pages...")

                while True:
                    try:
                        if progress_callback:
                            progress_callback(
                                page_index + 1,
                                total_frames,
                                f"Processing page {page_index + 1}/{total_frames}...",
                            )

                        self._save_page(tiff_img, page_index + 1, self._get_name_flag())
                        page_index += 1
                        tiff_img.seek(page_index)
                    except EOFError:
                        break

                self.file_info.file_page_count = page_index

                if progress_callback:
                    progress_callback(100, 100, "Conversion complete")

        except Exception as e:
            logger.error(message_manager.get_log_message("L063", str(e)))
            raise

    def _get_name_flag(self) -> str:
        """Get the name flag based on the file path.

        Returns:
            str: Name flag ('base' or 'comp')
        """
        _path_str = str(self.file_info.file_path).lower()
        if "base" in _path_str:
            return "base"
        elif "comp" in _path_str or "comparison" in _path_str:
            return "comp"
        else:
            return self._name_flag


def binarize_grayscale_images_in_folder(
    folder_path: str, threshold: int, color_key: ColorKey
) -> None:
    """Binarize grayscale images in a folder.

    Args:
        folder_path (str): Path to the folder containing images
        threshold (int): Threshold for binarization
        color_key (ColorKey): Color key for binarization
    """
    # Extract the selected color from the color key
    selected_color = (
        color_key.get("r", 0),
        color_key.get("g", 0),
        color_key.get("b", 0),
        color_key.get("a", 255),
    )

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".png"):
            continue

        file_path = os.path.join(folder_path, filename)
        try:
            with Image.open(file_path) as img:
                # Convert to RGBA mode
                img = img.convert("RGBA")

                # Get pixel data
                pixels = img.load()
                width, height = img.size

                for y in range(height):
                    for x in range(width):
                        # Get grayscale value
                        r, g, b, a = pixels[x, y]

                        # Set selected color if grayscale value is above threshold
                        if r >= threshold:
                            pixels[x, y] = selected_color
                        else:
                            # Make pixel transparent
                            pixels[x, y] = (0, 0, 0, 0)

                # Save binarized image
                img.save(file_path)
                logger.info(message_manager.get_log_message("L313", file_path))
        except Exception as e:
            logger.error(message_manager.get_log_message("L065", str(e)))
