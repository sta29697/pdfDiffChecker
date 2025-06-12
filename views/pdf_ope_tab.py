from __future__ import annotations

import os
import sys
import gc
import ctypes
from logging import getLogger
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
# mypy: ignore-errors
from typing import Any, Dict, Optional, Tuple, Union, cast

# PIL imports
from PIL import Image, ImageTk

# Utility imports
from utils.log_throttle import LogThrottle, window_resize_throttle
from utils.utils import get_temp_dir
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog
from utils.image_cache import ImageCache

# Controller imports
from controllers.mouse_event_handler import MouseEventHandler
from controllers.drag_and_drop_file import DragAndDropHandler
from controllers.file2png_by_page import Pdf2PngByPages

# Configuration imports
from configurations.message_manager import get_message_manager
from configurations.user_setting_manager import UserSettingManager # Import UserSettingManager

# Widget imports
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.color_theme_change_button import ColorThemeChangeButton
from widgets.language_select_combobox import LanguageSelectCombo
from widgets.base_path_entry import BasePathEntry
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_label_class import BaseLabelClass
from widgets.page_control_frame import PageControlFrame

# Model imports
from models.class_dictionary import FilePathInfo
from themes.coloring_theme_interface import ColoringThemeIF

logger = getLogger(__name__)
message_manager = get_message_manager()

class PDFOperationApp(ttk.Frame, ColoringThemeIF):
    """PDF operation tab for manipulating PDF files.
    
    This class provides a user interface for loading, viewing, and performing
    operations on PDF files such as rotation, page extraction, and more.
    """

    def __init__(self, master: Optional[tk.Misc] = None, user_settings_manager: UserSettingManager = None, **kwargs: Any) -> None: # Add user_settings_manager argument
        """Initialize the PDF operation tab.

        Args:
            master (Optional[tk.Misc]): Parent widget
            user_settings_manager (UserSettingManager): Instance of UserSettingManager.
            **kwargs: Additional keyword arguments
        """
        super().__init__(master, **kwargs)
        self.user_settings_manager = user_settings_manager # Store UserSettingManager instance
        self.base_widgets = BaseTabWidgets(self)
        
        # Configure frame to expand
        self.pack(fill="both", expand=True)
        self.grid_rowconfigure(2, weight=1)  # Make the bottom frame (with canvas) expandable
        self.grid_columnconfigure(0, weight=1)  # Make columns expandable

        # Initialize variables for status updates
        self.status_var: tk.StringVar = tk.StringVar(value="")
        self.after_id: Optional[str] = None
        
        # Initialize image cache
        # Use a larger cache size for PDF operations (200MB) to improve performance
        self.image_cache = ImageCache(max_size_mb=200, ttl=600)  # 10 minutes TTL

        # Initialize paths with internationalized messages
        self.base_path = tk.StringVar()
        self.base_path.set(message_manager.get_ui_message("U053"))
        self.output_path = tk.StringVar()
        self.output_path.set(message_manager.get_ui_message("U054"))

        # Create frames without borders
        self.frame_main0 = tk.Frame(self)
        self.frame_main0.grid(row=0, column=0, sticky="we", ipady=2)
        self.frame_main0.grid_columnconfigure(1, weight=1)  # This column will expand
        
        self.frame_main1 = tk.Frame(self)
        self.frame_main1.grid(row=1, column=0, sticky="we", ipady=2)
        self.frame_main1.grid_columnconfigure(1, weight=1)  # Entry column expands
        
        self.frame_main2 = tk.Frame(self)
        self.frame_main2.grid(row=2, column=0, sticky="nsew", ipady=2)  # nsew to fill all directions
        # Configure grid for vertical layout: controls on top, canvas below
        self.frame_main2.grid_columnconfigure(0, weight=1)  # Full width
        self.frame_main2.grid_rowconfigure(0, weight=0)  # Controls row doesn't expand
        self.frame_main2.grid_rowconfigure(1, weight=1)  # Canvas row expands

        # Create canvas with theme-compatible background
        # Background will be set by apply_theme_color method
        self.canvas = tk.Canvas(
            self.frame_main2,
            relief=tk.SUNKEN,
            borderwidth=1
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        # Make canvas expand with frame_main2
        self.frame_main2.grid_rowconfigure(1, weight=1)  # Canvas row expands
        self.frame_main2.grid_columnconfigure(0, weight=1)  # Full width
        self.base_widgets.add_widget(self.canvas)
        
        # Initialize variables for PDF display
        self.current_pdf_document = None
        self.current_page_index = 0
        self.photo_image: Optional[Union[tk.PhotoImage, 'ImageTk.PhotoImage']] = None
        
        # Initialize page data structures
        self.base_pages: list[str] = []  # List of file paths for base pages
        self.base_transform_data: list[Tuple[float, float, float, float]] = []  # For storing transform data for each page
        self.comp_transform_data: list[Tuple[float, float, float, float]] = []  # For comparison transform data
        
        # UI components
        self.mouse_handler: Optional[MouseEventHandler] = None
        self.page_control_frame: Optional[PageControlFrame] = None
        
        # Log throttling for mouse events
        self._wheel_log_throttle = LogThrottle(min_interval=1.0)

        # Setup UI
        self._setup_ui()
        self._setup_drag_and_drop()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Configure first frame column weights to push controls to the right
        self.frame_main0.grid_columnconfigure(0, weight=1)  # This column will expand
        
        # Create language selection combobox (right-aligned)
        lang_combo = LanguageSelectCombo(self.frame_main0)
        lang_combo.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        # Create theme change button (right-aligned)
        self._color_theme_change_btn = ColorThemeChangeButton(
            fr=self.frame_main0,
            color_theme_change_btn_status=False,
            text=message_manager.get_ui_message("U025"),
        )
        self._color_theme_change_btn.grid(
            row=0, column=2, padx=5, pady=1, sticky="e", ipadx=1  # Reduce size with smaller padx/pady/ipadx
        )

        # Base file path label and entry
        # Base file path label text
        self._base_file_path_label = BaseLabelClass(
            fr=self.frame_main1,
            color_key="base_file_path_label",
            text=message_manager.get_ui_message("U018"),
        )
        self._base_file_path_label.grid(
            column=0, row=1, padx=5, pady=8, sticky="w"
        )
        
        # type: ignore[call-arg] # suppress mypy errors for fr/entry_setting_key arguments
        self._base_file_path_entry = BasePathEntry(
            fr=self.frame_main1,
            color_key="base_file_path_entry",
            entry_setting_key="base_file_path"
        )
        self._base_file_path_entry.grid(
            column=1, row=1, padx=5, pady=8, sticky="ew"
        )
        self._base_file_path_entry.path_var.set(self.base_path.get())

        # Base file path select button
        # Button for base file path selection
        self._base_file_path_button = BasePathSelectButton(
            fr=self.frame_main1,
            color_key="base_file_path_button",
            entry_setting_key="base_file_path",
            share_path_entry=self._base_file_path_entry,
            text=message_manager.get_ui_message("U019"),
            command=self._on_base_file_select,
        )
        self._base_file_path_button.grid(column=2, row=1, padx=5, pady=8, sticky="e")


        # Output folder path label and entry
        # Output folder path label text
        self._output_folder_path_label = BaseLabelClass(
            fr=self.frame_main1,
            color_key="output_folder_path_label",
            text=message_manager.get_ui_message("U021"),
        )
        self._output_folder_path_label.grid(
            column=0, row=3, padx=5, pady=8, sticky="w"
        )

        # type: ignore[call-arg] # suppress mypy errors for fr/entry_setting_key arguments
        self._output_folder_path_entry = BasePathEntry(
            fr=self.frame_main1,
            color_key="output_folder_path_entry",
            entry_setting_key="output_folder_path"
        )
        self._output_folder_path_entry.grid(
            column=1, row=3, padx=5, pady=8, sticky="ew"
        )
        self._output_folder_path_entry.path_var.set(self.output_path.get())

        # Output folder path button
        # Button for output folder selection
        self._output_folder_path_button = BasePathSelectButton(
            fr=self.frame_main1,
            color_key="output_folder_path_button",
            entry_setting_key="output_folder_path",
            share_path_entry=self._output_folder_path_entry,
            text=message_manager.get_ui_message("U019"),
            command=self._on_output_folder_select,
        )
        self._output_folder_path_button.grid(column=2, row=3, padx=5, pady=8, sticky="e")

        self.pdf_file_path_entry = None

    def _on_base_file_select(self) -> None:
        """Handle base file selection event using common dialog."""
        file_path = ask_file_dialog(
            initialdir=self._base_file_path_entry.path_var.get(),
            title_code="U022",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            # Log file selection first
            logger.debug(message_manager.get_log_message("L071", file_path))
            
            # Update UI elements with the selected file path
            self._base_file_path_entry.path_var.set(file_path)
            self.base_path.set(file_path)
            
            # Load and display PDF (this will handle all necessary operations)
            self._load_and_display_pdf(file_path)
            
            # Set window icon to application icon to fix taskbar icon issue
            try:
                # Get the root window (Tk instance)
                root = self.winfo_toplevel()
                # Set icon if it's a Tk window
                if isinstance(root, tk.Tk):
                    icon_path = "images/LOGO_032.ico"
                    if os.path.exists(icon_path):
                        # Create a class-level icon log throttle if it doesn't exist
                        if not hasattr(PDFOperationApp, '_icon_log_throttle'):
                            PDFOperationApp._icon_log_throttle = LogThrottle(min_interval=300.0)  # 5 minutes
                        
                        # Only set icon if not already set (check window attributes)
                        if not hasattr(root, '_icon_set') or not root._icon_set:
                            root.iconbitmap(icon_path)
                            root._icon_set = True  # Mark icon as set
                            
                            # Log that the window icon has been set, but throttle to avoid excessive logs
                            # Use L350 which is for window icon setting and requires only one parameter
                            if PDFOperationApp._icon_log_throttle.should_log("window_icon"):
                                logger.debug(message_manager.get_log_message("L350", icon_path))
            except Exception as e:
                # Log failure to set window icon
                logger.warning(message_manager.get_log_message("L351", str(e)))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection event using common dialog.
        
        Opens a folder selection dialog and updates the output folder path entry
        with the selected folder path.
        """
        folder_path = ask_folder_dialog(
            initialdir=self._output_folder_path_entry.path_var.get(),
            title_code="U024",
        )
        if folder_path:
            self._output_folder_path_entry.path_var.set(folder_path)
            logger.debug(message_manager.get_log_message("L073", folder_path))

    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop functionality for the canvas.
        
        Registers the canvas as a drop target for PDF files and sets up the
        necessary callbacks for handling dropped files.
        """
        # Try to register drop target; suppress non-fatal errors
        success = DragAndDropHandler.register_drop_target(
            self.canvas, self._on_drop, [".pdf"], self._show_drop_feedback
        )
        if success:
            # Log successful initialization of drag and drop
            logger.info(message_manager.get_log_message("L234"))

    def _load_and_display_pdf(self, file_path: str) -> None:
        """Load and display PDF file on canvas.
        
        Args:
            file_path (str): Path to the PDF file to load and display.
        """
        try:
            # Create temporary directory for extracted PNG files
            self.session_id = f"pdf_op_{os.path.basename(file_path)}_{Path(file_path).stem}"
            
            # Create FilePathInfo object for the PDF file
            file_path_info = FilePathInfo(
                file_path=Path(file_path),
                file_page_count=0,  # Will be updated during conversion
                file_meta_info={},
                file_histogram_data=[]
            )
            
            # Show progress window during conversion
            # Use correct program_mode from tool_settings to ensure path consistency
            from configurations import tool_settings
            self.current_pdf_converter = Pdf2PngByPages(
                pdf_obj=file_path_info,
                program_mode=tool_settings.program_mode,  # Use actual program mode from settings
                name_flag="base"  # This is the base file
            )
            
            # Log the temp directory path for debugging
            temp_dir = self.current_pdf_converter._temp_dir
            logger.info(message_manager.get_log_message("L278", str(temp_dir)))
            
            # Process the file and convert to PNGs
            self.current_pdf_converter.process_with_progress_window(self.frame_main2)
            
            # Store the converted pages information
            self.current_page_index = 0
            self.file_path_info = file_path_info
            self.page_count = file_path_info.file_page_count
            
            # Create empty transform data for mouse operations (rotation, translation, scale)
            self.base_transform_data = [(0.0, 0.0, 0.0, 1.0) for _ in range(self.page_count)]
            
            # Generate base_pages list for display and reference
            self.base_pages = [f"Page {i+1}" for i in range(self.page_count)]
            
            # Initialize image_operations_dict for flip operations
            self.image_operations_dict = {}
            
            # Set up page control frame first to ensure page numbers are visible
            self._create_page_control_frame(self.page_count)
            
            # Initialize mouse handler with the transform data
            self._initialize_mouse_handler()
            
            # Set up mouse events for canvas operations
            self._setup_mouse_events()
            
            # Display the first page
            self._display_page(self.current_page_index)
            
            # Force update the canvas to ensure the image is displayed
            self.canvas.update()
            
            # Update page control frame explicitly
            if self.page_control_frame:
                self.page_control_frame.update_page_label(self.current_page_index, self.page_count)
                # Ensure page count is properly displayed
                logger.debug(message_manager.get_log_message("L350", str(self.current_page_index + 1), str(self.page_count)))
            
            # Log success
            logger.info(message_manager.get_log_message("L276", 
                       str(self.page_count), str(file_path)))
                       
        except Exception as e:
            logger.error(message_manager.get_log_message("L277", str(e)))
            # Output error stack trace
            import traceback
            logger.error(traceback.format_exc())

    def _display_page(self, page_index: int) -> None:
        """Display specified page of the current PDF document using PNG files.
        
        Args:
            page_index (int): Index of the page to display (0-based)
        
        """
        # Fix-1: Set current page index at the beginning
        self.current_page_index = page_index
        
        # Store mouse handler state before page change
        mouse_handler_state = None
        if hasattr(self, 'mouse_handler') and self.mouse_handler:
            # Check if in rotation mode
            rotation_mode = False
            if hasattr(self.mouse_handler, '_MouseEventHandler__rotation_mode'):
                rotation_mode = self.mouse_handler._MouseEventHandler__rotation_mode
                
            # Check if shortcut guide is visible
            shortcut_guide_visible = False
            if hasattr(self.mouse_handler, '_MouseEventHandler__keep_rotation_elements_visible'):
                shortcut_guide_visible = self.mouse_handler._MouseEventHandler__keep_rotation_elements_visible
                
            # Store state for restoration after page change
            mouse_handler_state = {
                'rotation_mode': rotation_mode,
                'shortcut_guide_visible': shortcut_guide_visible
            }
        try:
            # Initialize transformation variables
            # These variables will be used in future implementations for image transformations
            rotation = 0.0  # noqa: F841
            translate_x = 0.0  # noqa: F841
            translate_y = 0.0  # noqa: F841
            scale = 1.0  # noqa: F841
            
            # Check if page information is available
            if not hasattr(self, 'file_path_info') or not self.file_path_info:
                logger.warning(message_manager.get_log_message("L282"))
                return
                
            # Validate page index
            if not (0 <= page_index < self.page_count):
                logger.warning(message_manager.get_log_message("L283", 
                             str(page_index), str(self.page_count-1)))
                return
            
            # Generate the PNG filename for this page (1-based index in filename)
            # Use the correct temp directory from the PDF converter if available
            if hasattr(self, 'current_pdf_converter') and self.current_pdf_converter and hasattr(self.current_pdf_converter, '_temp_dir'):
                temp_dir = self.current_pdf_converter._temp_dir
                # Log the temp directory path for debugging, but throttle to avoid excessive logging
                # Use global temp_dir_throttle instead of creating a new instance
                from utils.log_throttle import temp_dir_throttle
                # Only log on first access or very infrequently
                if temp_dir_throttle.should_log(f"temp_dir_{temp_dir}", throttle_key="temp_dir") and not hasattr(self, '_temp_dir_logged'):
                    logger.debug(message_manager.get_log_message("L360", str(temp_dir)))
                    self._temp_dir_logged = True
            else:
                temp_dir = get_temp_dir()
                # Throttle logging to avoid excessive messages
                # Use global temp_dir_throttle instead of creating a new instance
                from utils.log_throttle import temp_dir_throttle
                # Only log on first access or very infrequently
                if temp_dir_throttle.should_log(f"temp_dir_{temp_dir}", throttle_key="temp_dir") and not hasattr(self, '_temp_dir_logged'):
                    logger.debug(message_manager.get_log_message("L348", str(temp_dir)))
                    self._temp_dir_logged = True
                
            # Use only one temporary directory - the converter's directory
            png_filename = f"base_{page_index + 1:04d}.png"
            # Ensure path is a Path object for proper path handling
            png_path = Path(str(temp_dir)) / png_filename
            
            # Use LogThrottle to prevent excessive logging of the same PNG path
            # Only log once per file path every 10 seconds (increased from 5 to further reduce logs)
            png_path_str = str(png_path)
            
            # Use global png_load_throttle instead of creating a new instance
            from utils.log_throttle import png_load_throttle
                
            # Check if PNG file exists
            if png_path.exists():
                try:
                    # Check if image is in cache first
                    cached_img = self.image_cache.get(str(png_path))
                    
                    if cached_img:
                        # Use cached image
                        img = cached_img
                        logger.debug(message_manager.get_log_message("L484", str(img.width), str(img.height), img.mode))
                        logger.debug(f"Using cached image for {png_path}")
                    else:
                        # Open the PNG file and add to cache
                        img = Image.open(png_path)
                        # Add to cache for future use only if not already in cache
                        # This prevents overwriting existing cache entries which may cause image disappearance
                        if self.image_cache.get(str(png_path)) is None:
                            self.image_cache.put(str(png_path), img)
                        
                        # Log cache statistics periodically
                        if self.current_page_index % 5 == 0:  # Log every 5 pages
                            cache_info = self.image_cache.get_cache_info()
                            logger.info(message_manager.get_log_message("L494", 
                                                                     f"{cache_info['size_mb']:.2f}", 
                                                                     str(cache_info['item_count']), 
                                                                     f"{cache_info['hit_rate']:.2f}"))
                    
                    # Log PNG file details including dimensions and mode
                    logger.debug(message_manager.get_log_message("L484", str(img.width), str(img.height), img.mode))
                    
                    # Only log file loading - skip the file searching log to avoid consecutive logs
                    # Use L373 message code which indicates PNG file loading
                    # Add throttling to reduce log frequency
                    if png_load_throttle.should_log(f"png_load_{png_path_str}", throttle_key="png_load"):
                        logger.debug(message_manager.get_log_message("L373", str(png_path)))
                    
                    # Log image dimensions for debugging with throttling and dimension change detection
                    # Create a class attribute to track last logged dimensions if it doesn't exist
                    if not hasattr(PDFOperationApp, '_last_logged_dimensions'):
                        PDFOperationApp._last_logged_dimensions = {}
                    
                    # Create a key for this image based on page index and filename
                    dimension_key = f"{self.current_page_index}_{png_filename}"
                    
                    # Check if dimensions have changed or not logged before
                    current_dimensions = (img.width, img.height)
                    if (dimension_key not in PDFOperationApp._last_logged_dimensions or 
                            PDFOperationApp._last_logged_dimensions[dimension_key] != current_dimensions):
                        # Only log if dimensions have changed or not logged before
                        # Use the new message code L410 specifically for image dimensions
                        logger.debug(message_manager.get_log_message("L410", f"{img.width}", f"{img.height}"))
                        # Update the stored dimensions
                        PDFOperationApp._last_logged_dimensions[dimension_key] = current_dimensions
                    
                    # Apply transformations - these will be used in future implementations
                    if self.current_page_index < len(self.base_transform_data):
                        rotation, tx, ty, scale = self.base_transform_data[self.current_page_index]
                    else:
                        rotation, tx, ty, scale = 0.0, 0.0, 0.0, 1.0
                    
                    # Apply scale factor from mouse wheel zoom if available
                    if hasattr(self, 'scale_factor'):
                        # Store original scale for logging
                        original_scale = scale
                        
                        # Combine the base scale with the zoom scale factor
                        scale *= self.scale_factor
                        
                        # Log scale factor before and after application
                        logger.debug(message_manager.get_log_message("L485", str(original_scale), str(scale)))
                        
                        # Use global zoom_throttle instead of creating a new instance
                        from utils.log_throttle import zoom_throttle
                        if zoom_throttle.should_log("zoom_factor", throttle_key="zoom_factor"):
                            # Use L407 message code which is for zoom factor log throttle interval
                            logger.debug(message_manager.get_log_message("L407", str(scale)))
                    
                    # Log the final transformation values that will be applied
                    logger.debug(message_manager.get_log_message("L486", str(rotation), str(tx), str(ty), str(scale)))
                    
                    # Get flip flags from mouse handler if available
                    h_flip, v_flip = False, False
                    if hasattr(self, 'mouse_handler') and self.mouse_handler:
                        # Use layer 0 as default for now
                        layer_id = 0
                        h_flip, v_flip = self.mouse_handler.get_flip_flags(layer_id, self.current_page_index)
                        logger.debug(f"[DEBUG] Flip flags: h_flip={h_flip}, v_flip={v_flip}")
                    
                    # Apply horizontal flip if needed
                    if h_flip:
                        from PIL import ImageOps
                        img = ImageOps.mirror(img)
                        logger.debug("[DEBUG] Image flipped horizontally")
                    
                    # Apply vertical flip if needed
                    if v_flip:
                        from PIL import ImageOps
                        img = ImageOps.flip(img)
                        logger.debug("[DEBUG] Image flipped vertically")
                    
                    # Actually apply transformations to the image
                    if scale != 1.0:
                        # Calculate new dimensions based on scale factor
                        new_width = int(img.width * scale)
                        new_height = int(img.height * scale)
                        
                        # Resize the image using the calculated dimensions
                        # Use LANCZOS resampling for better quality
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                        logger.debug(f"[DEBUG] Image resized to {new_width}x{new_height} with scale={scale}")
                    
                    # Apply rotation if needed
                    if rotation != 0.0:
                        # Rotate the image
                        # Use expand=True to ensure the entire rotated image is visible
                        img = img.rotate(-rotation, resample=Image.BICUBIC, expand=True)
                        logger.debug(f"[DEBUG] Image rotated by {rotation} degrees")
                    
                    # Get canvas dimensions
                    canvas_width = self.canvas.winfo_width()
                    canvas_height = self.canvas.winfo_height()
                    
                    # Convert to PhotoImage for display
                    photo_image = ImageTk.PhotoImage(img)
                    self.photo_image = photo_image  # Keep reference to prevent garbage collection
                    
                    # Create image_operations_dict if it doesn't exist
                    if not hasattr(self, 'image_operations_dict'):
                        self.image_operations_dict = {}
                    
                    # Store UI elements that should be preserved during rotation mode
                    preserved_items = []
                    
                    # Check if mouse handler exists and is in rotation mode
                    in_rotation_mode = False
                    if hasattr(self, 'mouse_handler') and self.mouse_handler:
                        # Check if the mouse handler has rotation mode attribute and it's True
                        if hasattr(self.mouse_handler, '_MouseEventHandler__rotation_mode'):
                            in_rotation_mode = self.mouse_handler._MouseEventHandler__rotation_mode
                    
                    # If in rotation mode, preserve UI elements
                    if in_rotation_mode and self.mouse_handler:
                        # Get all canvas items
                        all_items = self.canvas.find_all()
                        
                        for item_id in all_items:
                            # Check if this is a rotation-related UI element by checking tags
                            tags = self.canvas.gettags(item_id)
                            # Skip the image itself
                            if 'pdf_image' not in tags:
                                # Store item properties for recreation
                                item_type = self.canvas.type(item_id)
                                coords = self.canvas.coords(item_id)
                                options = {}
                                
                                # Get all configuration options for this item
                                if item_type == 'oval':
                                    options['fill'] = self.canvas.itemcget(item_id, 'fill')
                                    options['outline'] = self.canvas.itemcget(item_id, 'outline')
                                    options['width'] = self.canvas.itemcget(item_id, 'width')
                                elif item_type == 'text':
                                    options['text'] = self.canvas.itemcget(item_id, 'text')
                                    options['fill'] = self.canvas.itemcget(item_id, 'fill')
                                    options['font'] = self.canvas.itemcget(item_id, 'font')
                                    options['anchor'] = self.canvas.itemcget(item_id, 'anchor')
                                elif item_type == 'rectangle':
                                    options['fill'] = self.canvas.itemcget(item_id, 'fill')
                                    options['outline'] = self.canvas.itemcget(item_id, 'outline')
                                    options['width'] = self.canvas.itemcget(item_id, 'width')
                                
                                # Store item for recreation
                                preserved_items.append((item_type, coords, options, tags))
                    
                    # Clear canvas but only remove the image
                    self.canvas.delete("pdf_image")
                    
                    # Display the image on the canvas with transformations applied
                    # Center the image and apply translation
                    # For PDF operation tab, set transparency to 0% (fully opaque)
                    image_id = self.canvas.create_image(
                        canvas_width // 2 + tx, canvas_height // 2 + ty,
                        image=photo_image,
                        tags="pdf_image"
                    )
                    
                    # Lower the image to ensure it's behind all UI elements
                    self.canvas.lower(image_id)
                    
                    # ----- Added: Create ImageOperations and register to dictionary -----
                    from controllers.image_operations import ImageOperations
                    # Update existing dictionary instead of overwriting
                    if not hasattr(self, 'image_operations_dict'):
                        self.image_operations_dict = {}
                    # Register ImageOperations for layer 0 (base layer)
                    self.image_operations_dict[0] = ImageOperations(self.canvas, image_id, img)
                    
                    # Recreate preserved items if in rotation mode
                    # Store the recreated item IDs for potential future use
                    recreated_item_ids = []
                    for item_type, coords, options, tags in preserved_items:
                        if item_type == 'oval':
                            item_id = self.canvas.create_oval(
                                *coords,
                                fill=options['fill'],
                                outline=options['outline'],
                                width=options['width'],
                                tags=tags
                            )
                            recreated_item_ids.append(item_id)
                        elif item_type == 'text':
                            item_id = self.canvas.create_text(
                                *coords,
                                text=options['text'],
                                fill=options['fill'],
                                font=options['font'],
                                anchor=options['anchor'],
                                tags=tags
                            )
                            recreated_item_ids.append(item_id)
                        elif item_type == 'rectangle':
                            item_id = self.canvas.create_rectangle(
                                *coords,
                                fill=options['fill'],
                                outline=options['outline'],
                                width=options['width'],
                                tags=tags
                            )
                            recreated_item_ids.append(item_id)
                            
                    # Update mouse handler with current page index
                    if hasattr(self, 'mouse_handler') and self.mouse_handler:
                        # Update the mouse handler with the current page index
                        self.mouse_handler.update_state(current_page_index=self.current_page_index)
                        
                        # Restore mouse handler state if we stored it earlier
                        if 'mouse_handler_state' in locals() and mouse_handler_state:
                            # Restore rotation mode if it was active
                            if mouse_handler_state['rotation_mode']:
                                # Get rotation center from previous state if available
                                if hasattr(self.mouse_handler, '_MouseEventHandler__rotation_center_x') and \
                                   hasattr(self.mouse_handler, '_MouseEventHandler__rotation_center_y'):
                                    center_x = self.mouse_handler._MouseEventHandler__rotation_center_x
                                    center_y = self.mouse_handler._MouseEventHandler__rotation_center_y
                                    self.mouse_handler.draw_feedback_circle(center_x, center_y, is_rotating=True)
                                    self.mouse_handler.show_guidance_text(message_manager.get_message('M042'), is_rotation=True)
                                    
                            # Restore shortcut guide visibility based on the stored state
                            if mouse_handler_state['shortcut_guide_visible']:
                                self.mouse_handler.toggle_shortcut_guide(event=None, force_show=True)
                            else:
                                # If the state indicates the guide should not be visible, ensure it is hidden.
                                # This handles cases where it might have been turned on by other means
                                # before state restoration.
                                self.mouse_handler.toggle_shortcut_guide(event=None, force_show=False)
                    
                    # Log the final position where the image is displayed on the canvas
                    # Use throttling to avoid excessive logging during page navigation
                    from utils.log_throttle import image_position_throttle
                    if image_position_throttle.should_log("image_position", throttle_key="image_position"):
                        logger.debug(message_manager.get_log_message("L370", f"{canvas_width // 2 + tx}", f"{canvas_height // 2 + ty}"))
                except Exception as e:
                    logger.error(message_manager.get_log_message("L285", str(e)))
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.warning(message_manager.get_log_message("L279", str(png_path)))
                return
                
            # Store previous page index to check if page actually changed
            previous_page_index = getattr(self, 'current_page_index', None)
            
            # Update current page index to the new value
            self.current_page_index = page_index
            
            # Set focus to the canvas for keyboard events
            # Fix-1a: Ensure canvas gets focus for keyboard events
            self.canvas.focus_set()
            
            # Fix-1b: Force canvas to update to ensure focus is properly set
            self.canvas.update_idletasks()
            
            # Update scroll region
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
            
            # Update page control frame
            if self.page_control_frame:
                # Only update label if page index changed
                if previous_page_index != page_index:
                    # Update with page_index because update_page_label expects 0-based index
                    self.page_control_frame.update_page_label(page_index, self.page_count)
                    
                    # Force update of page var to ensure consistency
                    self.page_control_frame.page_var.set(page_index + 1)
                    # Force update of total pages to ensure it's displayed
                    self.page_control_frame.current_file_page_amount.set(self.page_count)
                
            # Always update mouse handler with the current page index
            if hasattr(self, 'mouse_handler') and self.mouse_handler:
                # Create visibility layer dictionary (0=base, 1=comp)
                visible_layers = {}
                visible_layers[0] = True  # Base is visible
                visible_layers[1] = False  # Comp is not visible
                
                # Update mouse handler with correct parameters
                try:
                    self.mouse_handler.update_state(
                        current_page_index=page_index,
                        visible_layers=visible_layers
                    )
                except Exception as e:
                    # Mouse event handler update failed
                    logger.error(message_manager.get_log_message("L287", str(e)))
            
            # Log displayed page information only if page actually changed
            if previous_page_index != page_index:
                logger.info(message_manager.get_log_message("L284", page_index + 1, self.page_count))
                        
        except Exception as e:
            # Error displaying page
            logger.error(message_manager.get_log_message("L285", str(e)))
            import traceback
            logger.error(traceback.format_exc())

    def _on_prev_page(self) -> None:
        """Go to previous page."""
        # Check if PDF is loaded
        if not hasattr(self, 'file_path_info') or not self.file_path_info:
            # Log attempt to navigate when no PDF is loaded
            logger.warning(message_manager.get_log_message("L289"))
            # Show info message that no PDF is loaded
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return
            
        # Get total page count
        page_count = self.page_count if hasattr(self, 'page_count') else 0
        
        # Check if we can go to a previous page
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._display_page(self.current_page_index)
            if hasattr(self, 'page_control_frame') and self.page_control_frame:
                # Update the page control UI (0-based index for update_page_label)
                self.page_control_frame.update_page_label(self.current_page_index, page_count)
                # Update the page variable to ensure consistency
                self.page_control_frame.page_var.set(self.current_page_index + 1)
                
            # Log page movement using window_resize_throttle to prevent excessive logging
            if window_resize_throttle.should_log("page_navigation"):
                logger.info(message_manager.get_log_message("L290", self.current_page_index + 1, page_count))
        else:
            # Already at first page
            logger.info(message_manager.get_log_message("L291"))
            # Show info message that this is the first page
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U058"))

    def _initialize_mouse_handler(self) -> None:
        """Initialize the mouse event handler.
        
        This method creates a new MouseEventHandler instance and configures it
        for use with the PDF viewer.
        """
        try:
            # Initialize base transform data if not already created
            if not hasattr(self, 'base_transform_data'):
                # Default transformation: no rotation, no translation, scale=1.0
                self.base_transform_data = [(0.0, 0.0, 0.0, 1.0)] * self.page_count
                
            # Create a dictionary for layer transform data
            # For PDF operation tab, we only have one layer (base)
            layer_transform_data = {0: self.base_transform_data}
            
            # Create a dictionary for layer visibility
            # For PDF operation tab, only the base layer is visible
            visible_layers = {0: True}
            
            # Create mouse event handler with current page index
            self.mouse_handler = MouseEventHandler(
                layer_transform_data=layer_transform_data,
                current_page_index=self.current_page_index if hasattr(self, 'current_page_index') else 0,
                visible_layers=visible_layers,
                on_transform_update=self._on_transform_update,
                user_settings_manager=self.user_settings_manager,
                image_operations_dict=self.image_operations_dict if hasattr(self, 'image_operations_dict') else {}
            )
            
            # Attach to canvas for visual feedback and event handling
            self.mouse_handler.attach_to_canvas(self.canvas)
            
            # Ensure global shortcut keys are properly bound
            self._bind_global_shortcut_keys()
            
            # Log successful initialization
            logger.debug(message_manager.get_log_message("L175"))
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L067", str(e)))
            import traceback
            logger.error(traceback.format_exc())

    # _on_mouse_wheel method has been removed as its functionality is now handled by MouseEventHandler

    def _rebind_mouse_wheel(self) -> None:
        """Rebind mouse wheel event bindings.
    
        This method sets up mouse wheel event bindings for zoom functionality.
        It includes platform-specific bindings and error handling to ensure
        robust operation across different environments.
        """
        # Create mouse handler if it doesn't exist
        if not hasattr(self, 'mouse_handler') or self.mouse_handler is None:
            try:
                self._initialize_mouse_handler()
            except Exception as ex:
                # Log initialization error with specific error code
                logger.error(message_manager.get_log_message("L287", f"Failed to initialize mouse handler: {str(ex)}"))
                return  # Exit if initialization fails
            
        # Create a wrapper function for mouse wheel events with improved error handling
        def on_mouse_wheel_wrapper_zoom(e):
            # Use throttle to reduce excessive logging
            log_event = self._wheel_log_throttle.should_log("wheel_zoom", throttle_key="mouse_wheel")
            
            try:
                # Ensure canvas has focus for wheel events
                self.canvas.focus_set()
                
                # Verify all required components are available
                if (hasattr(self, 'mouse_handler') and self.mouse_handler):
                    # If logging is allowed, log the event with more detailed information
                    if log_event:
                        # Log mouse wheel event detection
                        logger.debug(message_manager.get_log_message("L424", self.current_page_index + 1))
                        # Log that we're about to call the zoom method
                        logger.debug(message_manager.get_log_message("L467", "on_mouse_wheel"))
                    
                    # Process the wheel event - no need to pass layer_data, the handler has all it needs
                    result = self.mouse_handler.on_mouse_wheel(e)
                    
                    # Log successful zoom operation
                    if log_event:
                        logger.debug(message_manager.get_log_message("L468"))
                        
                    return result
                else:
                    # Only log missing components if throttling allows
                    if log_event:
                        logger.warning(message_manager.get_log_message("L287", "Missing required components for mouse wheel handling"))
            except Exception as ex:
                # Only log errors if throttling allows to prevent log flooding
                if log_event:
                    logger.error(message_manager.get_log_message("L287", f"Mouse wheel error: {str(ex)}"))
            return None
            
        # Unbind any existing wheel bindings first to prevent duplicates
        try:
            self.canvas.unbind("<MouseWheel>")
            self.canvas.unbind("<Button-4>")
            self.canvas.unbind("<Button-5>")
        except Exception as ex:
            logger.warning(message_manager.get_log_message("L287", f"Failed to unbind mouse wheel events: {str(ex)}"))
        
        # Bind wheel events for all platforms with error handling
        try:
            self.canvas.bind("<MouseWheel>", on_mouse_wheel_wrapper_zoom)  # Windows
            self.canvas.bind("<Button-4>", on_mouse_wheel_wrapper_zoom)    # Linux scroll up
            self.canvas.bind("<Button-5>", on_mouse_wheel_wrapper_zoom)    # Linux scroll down
            
            # Log wheel binding with throttling
            if self._wheel_log_throttle.should_log("wheel_binding", throttle_key="mouse_wheel"):
                logger.debug(message_manager.get_log_message("L431"))
        except Exception as ex:
            logger.error(message_manager.get_log_message("L287", f"Failed to bind mouse wheel events: {str(ex)}"))
        
    # _zoom_in and _zoom_out methods have been removed and integrated with MouseEventHandler
        
    def _on_next_page(self) -> None:
        """Go to next page."""
# ... (rest of the code remains the same)
        # Check if PDF is loaded
        if not hasattr(self, 'file_path_info') or not self.file_path_info:
            # Log attempt to navigate when no PDF is loaded
            logger.warning(message_manager.get_log_message("L289"))
            # Show info message that no PDF is loaded
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return
            
        # Get total page count
        page_count = self.page_count if hasattr(self, 'page_count') else 0
        
        # Check if we can go to a next page
        if self.current_page_index < page_count - 1:
            self.current_page_index += 1
            self._display_page(self.current_page_index)
            if hasattr(self, 'page_control_frame') and self.page_control_frame:
                # Update the page control UI (0-based index for update_page_label)
                self.page_control_frame.update_page_label(self.current_page_index, page_count)
                # Update the page variable to ensure consistency
                self.page_control_frame.page_var.set(self.current_page_index + 1)
                
            # Log page movement using window_resize_throttle to prevent excessive logging
            if window_resize_throttle.should_log("page_navigation"):
                # Use L353 for page navigation which has placeholders for page numbers
                logger.info(message_manager.get_log_message("L353", self.current_page_index + 1, page_count))
        else:
            # Already at last page
            logger.info(message_manager.get_log_message("L295"))
            # Show info message that this is the last page
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U059"))
    
    def _on_page_entry(self, event: tk.Event) -> None:
        """Handle page entry event."""
        try:
            # Get the page control frame
            if not self.page_control_frame:
                # Use L295 for page control frame not available
                logger.warning(message_manager.get_log_message("L294"))
                return
                
            # Get the entered page number (1-based) directly from the page control frame
            page_num = self.page_control_frame.page_var.get()
            
            # Log page entry event with throttling to prevent excessive logging
            if window_resize_throttle.should_log("page_entry"):
                logger.info(message_manager.get_log_message("L354", str(page_num)))
            
            # Convert to 0-based index and validate
            page_index = page_num - 1
            if page_index < 0 or not hasattr(self, 'page_count') or page_index >= self.page_count:
                logger.warning(message_manager.get_log_message("L307", str(page_num), str(self.page_count)))
                return
                
            # Update current page index and display
            self.current_page_index = page_index
            self._display_page(self.current_page_index)
            
            # Update page label with 0-based index for update_page_label
            # update_page_label expects 0-based index and adds 1 internally
            self.page_control_frame.update_page_label(page_index, self.page_count)
            
            # Log success with throttling
            if window_resize_throttle.should_log("page_entry_success"):
                logger.info(message_manager.get_log_message("L353", str(page_num), str(self.page_count)))
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L309", str(e)))
            # Show error message
            messagebox.showerror(message_manager.get_ui_message("U056"), 
                               message_manager.get_ui_message("U060") + str(e))
        
    # This method has been merged with the other _setup_mouse_events method at line ~1228

    # _on_transform_update method is defined later in the class
    
    def _reset_transform(self) -> None:
        """Reset transformation for the current page."""
        # Reset transform data for the current page
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Reset to default transform values (0 rotation, 0,0 position, 1.0 scale)
            self.base_transform_data[self.current_page_index] = (0.0, 0.0, 0.0, 1.0)
            self._on_transform_update()
    
    # _zoom_in and _zoom_out methods have been integrated into MouseEventHandler
            
    def _go_to_first_page(self) -> None:
        """Go to the first page of the document."""
        if hasattr(self, 'page_count') and self.page_count > 0:
            self.current_page_index = 0
            self._display_page(self.current_page_index)
            if self.page_control_frame:
                self.page_control_frame.update_page_label(self.current_page_index, self.page_count)
    
    def _go_to_last_page(self) -> None:
        """Go to the last page of the document."""
        if hasattr(self, 'page_count') and self.page_count > 0:
            self.current_page_index = self.page_count - 1
            self._display_page(self.current_page_index)
            if self.page_control_frame:
                self.page_control_frame.update_page_label(self.current_page_index, self.page_count)
                
    def _on_prev_page(self) -> None:
        """Handle previous page button click."""
        # Log the previous page request
        logger.info(message_manager.get_log_message("L286"))
        
        # Check if PDF is loaded
        if not hasattr(self, 'file_path_info') or not self.file_path_info:
            # Log attempt to navigate when no PDF is loaded
            logger.warning(message_manager.get_log_message("L289"))
            # Show info message that no PDF is loaded
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return
            
        # Get total page count
        page_count = self.page_count if hasattr(self, 'page_count') else 0
        
        # Check if we can go to a previous page
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._display_page(self.current_page_index)
            if hasattr(self, 'page_control_frame') and self.page_control_frame:
                # Update the page control UI (0-based index for update_page_label)
                self.page_control_frame.update_page_label(self.current_page_index, page_count)
                # Update the page variable to ensure consistency
                self.page_control_frame.page_var.set(self.current_page_index + 1)
                
            # Log page movement using window_resize_throttle to prevent excessive logging
            if window_resize_throttle.should_log("page_navigation"):
                # Use L353 for page navigation which has placeholders for page numbers
                logger.info(message_manager.get_log_message("L353", self.current_page_index + 1, page_count))
        else:
            # Already at first page
            logger.info(message_manager.get_log_message("L291"))
            # Show info message that this is the first page
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U058"))
    
    def _on_next_page(self) -> None:
        """Handle next page button click."""
        # Log the next page request
        logger.info(message_manager.get_log_message("L288"))
        
        # Check if PDF is loaded
        if not hasattr(self, 'file_path_info') or not self.file_path_info:
            # Log attempt to navigate when no PDF is loaded
            logger.warning(message_manager.get_log_message("L289"))
            # Show info message that no PDF is loaded
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return
            
        # Get total page count
        page_count = self.page_count if hasattr(self, 'page_count') else 0
        
        # Check if we can go to a next page
        if self.current_page_index < page_count - 1:
            self.current_page_index += 1
            self._display_page(self.current_page_index)
            if hasattr(self, 'page_control_frame') and self.page_control_frame:
                # Update the page control UI (0-based index for update_page_label)
                self.page_control_frame.update_page_label(self.current_page_index, page_count)
                # Update the page variable to ensure consistency
                self.page_control_frame.page_var.set(self.current_page_index + 1)
                
            # Log page movement using window_resize_throttle to prevent excessive logging
            if window_resize_throttle.should_log("page_navigation"):
                # Use L353 for page navigation which has placeholders for page numbers
                logger.info(message_manager.get_log_message("L353", self.current_page_index + 1, page_count))
        else:
            # Already at last page
            logger.info(message_manager.get_log_message("L292"))
            # Show info message that this is the last page
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U059"))
    
    def _on_drop(self, file_path: str) -> None:
        """Handle file drop event.
        
        Args:
            file_path: Path of the dropped file
        """
        if not file_path:
            return
        
        # Only accept PDF files
        if file_path.lower().endswith('.pdf'):
            self._base_file_path_entry.path_var.set(file_path)
            self.base_path.set(file_path)
            self._load_and_display_pdf(file_path)
            logger.info(message_manager.get_log_message("L302", file_path))
        else:
            logger.warning(message_manager.get_log_message("L303", file_path))
    
    def _show_drop_feedback(self, drop_data: str, is_valid: bool) -> None:
        """Show visual feedback for file drop.
        
        Args:
            drop_data: Data being dropped
            is_valid: Whether the dropped file type is valid
        """
        # Clear previous feedback
        self.canvas.delete("drop_feedback")
        
        if is_valid:
            # Green outline for valid drop
            self.canvas.create_rectangle(
                0, 0, self.canvas.winfo_width(), self.canvas.winfo_height(),
                outline="#00ff00", width=5, tags="drop_feedback"
            )
        else:
            # Red outline for invalid drop
            self.canvas.create_rectangle(
                0, 0, self.canvas.winfo_width(), self.canvas.winfo_height(),
                outline="#ff0000", width=5, tags="drop_feedback"
            )
        
        # Schedule removal of feedback
        self.after(500, lambda: self.canvas.delete("drop_feedback"))
    
    def _create_page_control_frame(self, page_count: int) -> None:
        """Create or update the page control frame with navigation buttons.
        
        Args:
            page_count: Total number of pages
        """
        try:
            # Remove existing page control frame if it exists
            if hasattr(self, 'page_control_frame') and self.page_control_frame:
                self.page_control_frame.destroy()
                
            # Initialize page control variables
            self.page_var = tk.IntVar(value=self.current_page_index + 1)  # 1-based for display
            self.current_file_page_amount = tk.IntVar(value=page_count)
            
            # Log page count for debugging
            # Log the total number of pages when creating page control frame
            logger.debug(message_manager.get_log_message("L355", str(page_count)))
            
            # Create a new page control frame
            self.page_control_frame = PageControlFrame(
                parent=cast(tk.Frame, self),  # Cast to tk.Frame to satisfy type checker
                color_key="page_control",
                base_pages=self.base_pages,
                comp_pages=[],  # No comparison pages in PDF Operation tab
                base_transform_data=self.base_transform_data,
                comp_transform_data=[],  # No comparison transform data
                visualized_image=tk.StringVar(value="base"),  # Always show base image
                page_amount_limit=page_count,
                on_prev_page=self._on_prev_page,
                on_next_page=self._on_next_page,
                on_insert_blank=self._on_insert_blank_page,
                on_export=self._on_complete_edit,
                on_page_entry=self._on_page_entry
            )
            
            # Set initial page number and total pages
            self.page_control_frame.page_var.set(self.current_page_index + 1)
            # Explicitly set total pages
            self.page_control_frame.current_file_page_amount.set(page_count)
            # Force update of the label
            self.page_control_frame.total_pages_label.configure(text=f"/ {page_count}")
            
            # Place the page control frame above the canvas
            self.page_control_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5, in_=self.frame_main2)
            
            # Register with widgets tracker
            self.base_widgets.add_widget(self.page_control_frame)
            
            # Log successful creation
            logger.debug(message_manager.get_log_message("L298"))
            
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L067", str(e)))
    
    def _setup_mouse_events(self, page_count: int | None = None) -> None:
        """Set up mouse events for canvas operations.
        
        Args:
            page_count: Number of pages in the PDF (optional)
        """
        try:
            # Use page_count if provided, otherwise use existing value
            if page_count is None:
                page_count = getattr(self, 'page_count', 0)
                
            # Initialize mouse handler if not already initialized
            if self.mouse_handler is None:
                self._initialize_mouse_handler()
            
            # Create visibility layer dictionary
            visible_layers = {
                0: True,  # Base is visible
            }
            
            # Create layer transform data dictionary for the mouse handler
            # This will be used when initializing or updating the mouse handler
            layer_transform_data = {
                0: self.base_transform_data,  # Layer 0 = base
            }
            
            # Store mouse handler state before updating
            rotation_mode = False
            shortcut_guide_visible = False
            if self.mouse_handler is not None:
                # Check if in rotation mode
                if hasattr(self.mouse_handler, '_MouseEventHandler__rotation_mode'):
                    rotation_mode = self.mouse_handler._MouseEventHandler__rotation_mode
                    
                # Check if shortcut guide is visible
                if hasattr(self.mouse_handler, '_MouseEventHandler__keep_rotation_elements_visible'):
                    shortcut_guide_visible = self.mouse_handler._MouseEventHandler__keep_rotation_elements_visible
            
            # Update the mouse handler with the layer transform data if it exists
            if self.mouse_handler is not None and hasattr(self.mouse_handler, 'update_state'):
                self.mouse_handler.update_state(
                    current_page_index=self.current_page_index,
                    visible_layers=visible_layers,
                    layer_transform_data=layer_transform_data
                )
            
            # We don't need to clear and rebind mouse events on every page change
            # Only do this if the mouse handler is newly created or bindings are missing
            if self.mouse_handler is not None and not hasattr(self, '_mouse_events_bound'):
                # Remove existing bindings only if necessary
                self.canvas.unbind("<Button-1>")
                self.canvas.unbind("<B1-Motion>")
                self.canvas.unbind("<ButtonRelease-1>")
                self.canvas.unbind("<Button-3>")
                self.canvas.unbind("<KeyPress>")
                self.canvas.unbind("<KeyRelease>")
                
                # Mark that we've bound the events
                self._mouse_events_bound = True
            
            # Make canvas focusable to receive keyboard events
            self.canvas.config(takefocus=1)
            
            # Set initial focus to the canvas to ensure keyboard events work
            self.canvas.focus_set()
            
            # Explicitly bind mouse events to ensure they work
            # Use a wrapper function to set focus before handling the event
            def on_mouse_press_wrapper(e):
                self.canvas.focus_set()  # Ensure canvas has focus when clicked
                if self.mouse_handler:
                    return self.mouse_handler.on_mouse_press(e)
                return None
                
            # Bind mouse events to canvas
            self.canvas.bind("<Button-1>", on_mouse_press_wrapper)
            self.canvas.bind("<B1-Motion>", lambda e: self.mouse_handler.on_mouse_drag(e) if self.mouse_handler else None)
            self.canvas.bind("<ButtonRelease-1>", lambda e: self.mouse_handler.on_mouse_up(e) if self.mouse_handler else None)
            
            # Bind keyboard shortcuts
            self.canvas.bind("<KeyPress>", lambda e: self.mouse_handler.on_key_press(e) if self.mouse_handler else None)
            self.canvas.bind("<KeyRelease>", lambda e: self.mouse_handler.on_key_release(e) if self.mouse_handler else None)
            
            # Bind mouse wheel for zooming
            self._rebind_mouse_wheel()
            
            # Restore state after update if needed
            if rotation_mode:
                # Schedule restoration of rotation mode after state update
                self.after_idle(lambda: self._restore_rotation_mode_after_update())
                
            if shortcut_guide_visible:
                # Schedule restoration of shortcut guide after state update
                self.after_idle(lambda: self._restore_shortcut_guide_after_update())
                
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L067", str(e)))
            import traceback
            logger.error(traceback.format_exc())
    
    def _restore_rotation_mode_after_update(self) -> None:
        """Restore rotation mode after mouse handler state update."""
        if hasattr(self, 'mouse_handler') and self.mouse_handler:
            # Check if rotation center coordinates are available
            if hasattr(self.mouse_handler, '_MouseEventHandler__rotation_center_x') and \
               hasattr(self.mouse_handler, '_MouseEventHandler__rotation_center_y'):
                center_x = self.mouse_handler._MouseEventHandler__rotation_center_x
                center_y = self.mouse_handler._MouseEventHandler__rotation_center_y
                # Fixed: Changed show_feedback_circle to draw_feedback_circle to match the correct method name
                self.mouse_handler.draw_feedback_circle(center_x, center_y, is_rotating=True)
                self.mouse_handler.show_guidance_text(message_manager.get_message('M042'), is_rotation=True)
    
    def _restore_shortcut_guide_after_update(self) -> None:
        """Restore shortcut guide after mouse handler state update."""
        if hasattr(self, 'mouse_handler') and self.mouse_handler:
            self.mouse_handler._show_shortcut_guide(message_manager.get_message('M049'))
    
    def _bind_shortcut_keys(self) -> None:
        """Bind keyboard shortcuts to functions."""
        # Bind keyboard shortcuts for PDF navigation
        self.canvas.bind("<Right>", lambda e: self._on_next_page())
        self.canvas.bind("<Left>", lambda e: self._on_prev_page())
        self.canvas.bind("<Up>", lambda e: self._on_first_page())
        self.canvas.bind("<Down>", lambda e: self._on_last_page())
        

            
    def _bind_global_shortcut_keys(self) -> None:
        """Bind global keyboard shortcuts that should work regardless of focus."""
        # Get the root window
        root = self.canvas.winfo_toplevel()
        
        # Bind global shortcuts
        if hasattr(self, 'mouse_handler') and self.mouse_handler:
            # Toggle shortcut guide with F1 key
            root.bind_all("<F1>", self.mouse_handler.toggle_shortcut_guide)
            
            # Rotation shortcuts
            root.bind_all("<Control-r>", lambda e: self._on_rotate_clockwise())
            root.bind_all("<Control-l>", lambda e: self._on_rotate_counterclockwise())
            
            # Flip shortcuts
            root.bind_all("<Control-h>", lambda e: self._on_flip_horizontal())
            root.bind_all("<Control-v>", lambda e: self._on_flip_vertical())
            
            # Log binding of global shortcuts
            logger.debug(message_manager.get_log_message("L350", "Global shortcut keys bound successfully"))
    
    def destroy(self) -> None:
        """Clean up resources when tab is destroyed."""
        # Clean up any active timers
        if hasattr(self, '_update_timer') and self._update_timer:
            try:
                self.canvas.after_cancel(self._update_timer)
                self._update_timer = None
                logger.debug(message_manager.get_log_message("L351", "Update timer cancelled"))
            except Exception as e:
                logger.error(message_manager.get_log_message("L288", str(e)))
        
        # Cancel any other timers that might be active
        for timer_attr in ['_resize_timer', '_load_timer', '_display_timer']:
            if hasattr(self, timer_attr) and getattr(self, timer_attr):
                try:
                    self.canvas.after_cancel(getattr(self, timer_attr))
                    setattr(self, timer_attr, None)
                    logger.debug(message_manager.get_log_message("L351", f"{timer_attr} cancelled"))
                except Exception as e:
                    logger.error(message_manager.get_log_message("L288", str(e)))
        
        # Clean up mouse handler if it exists
        if hasattr(self, 'mouse_handler') and self.mouse_handler:
            try:
                # Fix-5a: Ensure all after timers in mouse handler are cancelled
                if hasattr(self.mouse_handler, '_hide_after_ids'):
                    for timer_id in self.mouse_handler._hide_after_ids:
                        if timer_id:
                            try:
                                self.canvas.after_cancel(timer_id)
                                logger.debug(message_manager.get_log_message("L351", f"Mouse handler timer {timer_id} cancelled"))
                            except Exception as e_timer:
                                logger.error(message_manager.get_log_message("L288", f"Error cancelling timer {timer_id}: {str(e_timer)}"))
                
                # Fix-5b: Cancel any ctrl check timer
                if hasattr(self.mouse_handler, '_MouseEventHandler__ctrl_check_timer_id'):
                    ctrl_timer = self.mouse_handler._MouseEventHandler__ctrl_check_timer_id
                    if ctrl_timer:
                        try:
                            self.canvas.after_cancel(ctrl_timer)
                            logger.debug(message_manager.get_log_message("L351", "Ctrl check timer cancelled"))
                        except Exception as e_ctrl:
                            logger.error(message_manager.get_log_message("L288", f"Error cancelling ctrl timer: {str(e_ctrl)}"))
                
                # Call the mouse handler's cleanup method
                self.mouse_handler.cleanup()
                logger.debug(message_manager.get_log_message("L352", "Mouse handler cleaned up"))
            except Exception as e:
                logger.error(message_manager.get_log_message("L289", str(e)))
        
        # Unbind global shortcuts
        try:
            root = self.canvas.winfo_toplevel()
            root.unbind_all("<F1>")
            root.unbind_all("<Control-r>")
            root.unbind_all("<Control-l>")
            root.unbind_all("<Control-h>")
            root.unbind_all("<Control-v>")
            logger.debug(message_manager.get_log_message("L539", "Global shortcuts unbound"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L290", str(e)))
        
        # Call parent destroy method
        super().destroy()
        
    def _on_transform_update(self) -> None:
        """Callback when transform data is updated."""
        try:
            # Store current scale factor for use in _display_page
            if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
                _, _, _, scale = self.base_transform_data[self.current_page_index]
                self.scale_factor = scale
                
            # Log memory usage before garbage collection
            if sys.platform == 'win32':
                import psutil
                process = psutil.Process(os.getpid())
                memory_before = process.memory_info().rss / (1024 * 1024)
                logger.debug(f"Memory usage before GC: {memory_before:.2f}MB")
            
            # Enhanced memory management to ensure proper resource cleanup
            # First, clear any references that might be keeping objects alive
            if hasattr(self, 'image_cache'):
                # Mark unused images for deletion
                self.image_cache.mark_unused()
            
            # Force full garbage collection with generational cleanup
            # Generation 2 is the oldest generation and contains long-lived objects
            gc.collect(2)  # Collect oldest generation first
            gc.collect(1)  # Then middle generation
            gc.collect(0)  # Finally, youngest generation
            
            # Additional steps to ensure memory is released back to the OS
            if sys.platform == 'win32':
                # On Windows, explicitly request memory compaction
                ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1)
            
            # Log memory usage after garbage collection
            if sys.platform == 'win32':
                memory_after = process.memory_info().rss / (1024 * 1024)
                logger.debug(f"Memory usage after GC: {memory_after:.2f}MB, Freed: {memory_before - memory_after:.2f}MB")
                
            # Redisplay the current page with updated transformations
            self._display_page(self.current_page_index)
            
            # Log cache statistics periodically during transformations
            if hasattr(self, 'image_cache'):
                # Only log every few operations to avoid excessive logging
                if not hasattr(self, '_transform_count'):
                    self._transform_count = 0
                self._transform_count += 1
                
                if self._transform_count % 10 == 0:  # Log every 10 transformations
                    cache_info = self.image_cache.get_cache_info()
                    logger.info(message_manager.get_log_message("L494", 
                                                             f"{cache_info['size_mb']:.2f}", 
                                                             str(cache_info['item_count']), 
                                                             f"{cache_info['hit_rate']:.2f}"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L406", str(e)))
            import traceback
            logger.error(traceback.format_exc())
            
    def update_image_transform(self, rotation: float = 0.0, tx: float = 0.0, ty: float = 0.0, scale: float = 1.0) -> None:
        """Update image transformation parameters and redisplay the current page.
        
        This method updates the transformation data for the current page and triggers
        a redisplay of the page with the new transformation applied.
        
        Args:
            rotation (float): Rotation angle in degrees (default: 0.0)
            tx (float): X-axis translation (default: 0.0)
            ty (float): Y-axis translation (default: 0.0)
            scale (float): Scale factor (default: 1.0)
        """
        try:
            # Ensure we have valid base_transform_data
            if not hasattr(self, 'base_transform_data') or not self.base_transform_data:
                logger.warning(message_manager.get_log_message("L344", "no_transform_data_available"))
                return
                
            # Ensure current_page_index is valid
            if not hasattr(self, 'current_page_index') or self.current_page_index < 0 or self.current_page_index >= len(self.base_transform_data):
                logger.warning(message_manager.get_log_message("L344", "invalid_page_index"))
                return
                
            # Update transformation data for the current page
            self.base_transform_data[self.current_page_index] = (rotation, tx, ty, scale)
            
            # Store scale factor for use in _display_page
            self.scale_factor = scale
            
            # Log the transformation update
            logger.debug(message_manager.get_log_message("L344", 
                f"update_image_transform: rotation={rotation}, tx={tx}, ty={ty}, scale={scale}"))
            
            # Redisplay the current page with updated transformations
            self._display_page(self.current_page_index)
        except Exception as e:
            logger.error(message_manager.get_log_message("L303", str(e)))
            import traceback
            logger.error(traceback.format_exc())
    
    def _on_insert_blank_page(self) -> None:
        """Insert a blank page after the current page."""
        if not hasattr(self, 'page_count') or self.page_count == 0:
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return
            
        # Create a blank image with white background (A4 size at 72 DPI: 595x842)
        blank_img = Image.new('RGBA', (595, 842), (255, 255, 255, 255))
        
        # Generate a filename for the blank page
        if hasattr(self, 'current_pdf_converter') and self.current_pdf_converter and hasattr(self.current_pdf_converter, '_temp_dir'):
            temp_dir = self.current_pdf_converter._temp_dir
        else:
            temp_dir = get_temp_dir()
            
        # Insertion position (after current page)
        insert_position = self.current_page_index + 1
        
        # Generate filenames for the new blank page
        png_filename = f"base_{insert_position + 1:04d}.png"
        png_path = Path(str(temp_dir)) / png_filename
        
        # Save the blank image
        blank_img.save(png_path, format="PNG")
        
        # Update page count and transform data
        self.page_count += 1
        self.base_transform_data.insert(insert_position, (0.0, 0.0, 0.0, 1.0))
        # Update base_pages
        self.base_pages = [f"Page {i+1}" for i in range(self.page_count)]
        
        # Refresh UI
        self._create_page_control_frame(self.page_count)
        self._display_page(insert_position)  # Show the new blank page
        
        logger.info(message_manager.get_log_message("L304", insert_position + 1))
    

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Apply theme colors to the PDF operation tab widgets.
        
        Args:
            theme_data (Dict[str, Any]): Theme data obtained from ColorThemeManager.load_theme
        """
        try:
            # Apply theme to canvas
            canvas_settings = theme_data.get("Canvas", {})
            self._config_widget(canvas_settings)
            
            # Log theme application
            logger.debug(message_manager.get_log_message("L380", "PDFOperationApp"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L381", str(e)))
    
    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget-specific theme settings for the canvas.
        
        Args:
            theme_settings (Dict[str, Any]): Widget-specific theme settings
        """
        try:
            # Apply background color to canvas
            bg_color = theme_settings.get("bg", "#ffffff")
            self.canvas.configure(bg=bg_color)
            
            # Log canvas theme configuration
            logger.debug(message_manager.get_log_message("L382", bg_color))
        except Exception as e:
            logger.error(message_manager.get_log_message("L383", str(e)))
    
    def _on_complete_edit(self) -> None:
        """Complete the editing process and export the PDF."""
        if not hasattr(self, 'page_count') or self.page_count == 0:
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return
            
        # Get output folder path
        output_folder = self._output_folder_path_entry.path_var.get()
        if not output_folder or not os.path.isdir(output_folder):
            # Ask user to select an output folder
            current_dir = os.getcwd()  # Use current working directory as initial directory
            output_folder_path = ask_folder_dialog(initialdir=current_dir, title_code="U060")
            if not output_folder_path:
                # User cancelled the folder selection
                return
            # Update the output folder path entry with selected path
            output_folder = str(output_folder_path)  # Convert None or str to str
            self._output_folder_path_entry.path_var.set(output_folder)
            
        # Get the base file name for the new PDF
        base_path = self.base_path.get()
        if not base_path or base_path == "":
            # If base_path is not set, use a default name
            base_file_name = "output.pdf"
            logger.warning(message_manager.get_log_message("L307", "No base path set, using default filename"))
        else:
            base_file_name = os.path.basename(base_path)
            
        output_file = os.path.join(output_folder, f"edited_{base_file_name}")
        
        try:
            # This would normally call a PDF creation function
            # For now, just show a message that it would create a PDF
            messagebox.showinfo(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message("U061").format(output_file)
            )
            logger.info(message_manager.get_log_message("L305", output_file))
        except Exception as e:
            logger.error(message_manager.get_log_message("L306", str(e)))
            messagebox.showerror(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message("U062").format(str(e))
            )
            
    # This is the end of _on_complete_edit method
    # The duplicate apply_theme_color and _config_widget methods have been removed
    # The original methods are defined at lines 1202 and 1217
