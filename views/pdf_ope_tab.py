from __future__ import annotations

from logging import getLogger
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional, Tuple, Union, cast
from utils.log_throttle import LogThrottle
import os
from pathlib import Path

# PIL imports
from PIL import Image, ImageTk
from PIL.Image import Resampling
from PIL.ImageFile import ImageFile

from configurations.message_manager import get_message_manager
from controllers.mouse_event_handler import MouseEventHandler
from controllers.drag_and_drop_file import DragAndDropHandler
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.color_theme_change_button import ColorThemeChangeButton
from widgets.language_select_combobox import LanguageSelectCombo
from widgets.base_path_entry import BasePathEntry
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_label_class import BaseLabelClass
from widgets.page_control_frame import PageControlFrame
from utils.utils import get_temp_dir
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog
from controllers.file2png_by_page import Pdf2PngByPages
from models.class_dictionary import FilePathInfo
from themes.coloring_theme_interface import ColoringThemeIF
from controllers.widgets_tracker import WidgetsTracker
from configurations.user_setting_manager import UserSettingManager

logger = getLogger(__name__)
message_manager = get_message_manager()

class PDFOperationApp(ttk.Frame, ColoringThemeIF):
    """PDF operation tab."""

    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        """Initialize the PDF operation tab.

        Args:
            master (Optional[tk.Misc]): Parent widget
            **kwargs: Additional keyword arguments
        """
        super().__init__(master, **kwargs)
        WidgetsTracker().add_widgets(self)
        self.base_widgets = BaseTabWidgets(self)
        
        # Configure frame to expand
        self.pack(fill="both", expand=True)
        self.grid_rowconfigure(2, weight=1)  # Make the bottom frame (with canvas) expandable
        self.grid_columnconfigure(0, weight=1)  # Make columns expandable

        # Initialize variables for status updates
        self.status_var: tk.StringVar = tk.StringVar(value="")
        self.after_id: Optional[str] = None

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
        self.frame_main2.grid_columnconfigure(0, weight=1)
        self.frame_main2.grid_rowconfigure(0, weight=1)  # Make canvas row expandable

        # Create canvas
        self.canvas = tk.Canvas(
            self.frame_main2,
            bg="#ffffff",  # Default canvas background (will be themed)
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#e0e0e0",
            highlightcolor="#e0e0e0",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        # Make canvas expand with frame_main2
        self.frame_main2.grid_rowconfigure(0, weight=1)
        self.frame_main2.grid_columnconfigure(0, weight=1)
        self.base_widgets.add_widget(self.canvas)

        # Footer metadata label (M1-009) - small text below canvas
        self._footer_meta_label = tk.Label(
            self.frame_main2,
            text="-",
            font=("", 8),
            anchor="w",
        )
        self._footer_meta_label.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))

        # Initialize variables for PDF display
        self.current_pdf_document = None
        self.current_page_index = 0
        self.photo_image: Optional[Union[tk.PhotoImage, 'ImageTk.PhotoImage']] = None

        # Operation restriction (e.g., copy-protected files)
        self._copy_protected: bool = False
        self._visual_adjustments_enabled: bool = True
        
        # Initialize page data structures
        self.base_pages: list[str] = []  # List of file paths for base pages
        self.base_page_paths: list[Path] = []
        self.base_transform_data: list[Tuple[float, float, float, float]] = []  # For storing transform data for each page
        self.comp_transform_data: list[Tuple[float, float, float, float]] = []  # For comparison transform data
        
        # UI components
        self.mouse_handler: Optional[MouseEventHandler] = None
        self.page_control_frame: Optional[PageControlFrame] = None
        self.visualized_image: tk.StringVar = tk.StringVar(value="base")

        # Setup UI
        self._setup_ui()
        self._setup_drag_and_drop()

        # Main processing: refresh shared paths when the tab becomes visible.
        self.bind("<Visibility>", self._sync_shared_paths_from_settings)
        self.after_idle(self._sync_shared_paths_from_settings)

    def _sync_shared_paths_from_settings(self, event: Any = None) -> None:
        """Synchronize shared base/output paths from persisted settings.

        Args:
            event: Tkinter visibility event (unused).
        """
        _ = event
        placeholder_base = message_manager.get_ui_message("U053")
        placeholder_output = message_manager.get_ui_message("U054")

        try:
            saved_base = UserSettingManager().get_setting("base_file_path")
            if (
                isinstance(saved_base, str)
                and saved_base
                and saved_base != placeholder_base
                and self._base_file_path_entry.path_var.get() != saved_base
            ):
                self._base_file_path_entry.path_var.set(saved_base)
                self.base_path.set(saved_base)
                base_path_obj = Path(saved_base)
                if base_path_obj.exists() and base_path_obj.is_file() and base_path_obj.suffix.lower() == ".pdf":
                    self._load_and_display_pdf(saved_base)

            saved_output = UserSettingManager().get_setting("output_folder_path")
            if (
                isinstance(saved_output, str)
                and saved_output
                and saved_output != placeholder_output
                and self._output_folder_path_entry.path_var.get() != saved_output
            ):
                self._output_folder_path_entry.path_var.set(saved_output)
                self.output_path.set(saved_output)
        except Exception as exc:
            logger.warning(f"Shared path sync failed in pdf tab: {exc}")

    def _get_initial_dir_from_setting(self, setting_key: str) -> str:
        """Return an initial directory path for dialogs based on saved settings.

        Args:
            setting_key (str): UserSettingManager key (e.g., "base_file_path").

        Returns:
            str: Existing directory path suitable for dialog initialdir.
        """
        try:
            saved_value = UserSettingManager().get_setting(setting_key)
        except Exception:
            saved_value = None

        if isinstance(saved_value, str) and saved_value:
            try:
                path = Path(saved_value)
                if path.is_dir() and path.exists():
                    return str(path)
                parent = path.parent
                if parent.exists() and parent.is_dir():
                    return str(parent)
            except Exception:
                return os.getcwd()

        return os.getcwd()

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
            row=0, column=2, padx=5, pady=5, sticky="e"
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
        # Main processing: clear persisted path display on startup (placeholder only)
        self._base_file_path_entry.path_var.set(self.base_path.get())
        self.base_path.set(self._base_file_path_entry.path_var.get())

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
        # Main processing: clear persisted path display on startup (placeholder only)
        self._output_folder_path_entry.path_var.set(self.output_path.get())
        self.output_path.set(self._output_folder_path_entry.path_var.get())

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
        initial_dir = self._get_initial_dir_from_setting("base_file_path")
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U022",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self._base_file_path_entry.path_var.set(file_path)
            self.base_path.set(file_path)
            # Try to display PDF when file is selected
            self._load_and_display_pdf(file_path)
            logger.debug(message_manager.get_log_message("L071", file_path))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("output_folder_path")
        folder_path = ask_folder_dialog(
            initialdir=initial_dir,
            title_code="U024",
        )
        if folder_path:
            self._output_folder_path_entry.path_var.set(folder_path)
            logger.debug(message_manager.get_log_message("L073", folder_path))

    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop functionality for the canvas."""
        # Try to register drop target; suppress non-fatal errors
        success = DragAndDropHandler.register_drop_target(
            self.canvas, self._on_drop, [".pdf"], self._show_drop_feedback
        )
        if success:
            # Log successful initialization of drag and drop
            logger.info(message_manager.get_log_message("L234"))

    def _load_and_display_pdf(self, file_path: str) -> None:
        """Load and display PDF file on canvas."""
        try:
            # Main processing: clear canvas overlays when the input file changes.
            # Page switching is handled separately and should keep overlays for batch editing.
            try:
                if self.mouse_handler is not None and hasattr(self.mouse_handler, "clear_overlays"):
                    self.mouse_handler.clear_overlays()
            except Exception:
                pass
            try:
                self.canvas.delete("all")
            except Exception:
                pass

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
            
            # Main processing: get DPI from user settings and pass to converter (M1-009 fix).
            self._conversion_dpi = int(UserSettingManager.get_setting("setted_dpi", 150))
            
            # Process the file and convert to PNGs
            self.current_pdf_converter.process_with_progress_window(
                self.frame_main2, dpi=self._conversion_dpi)
            
            # Store the converted pages information
            self.current_page_index = 0
            self.file_path_info = file_path_info
            self.page_count = file_path_info.file_page_count

            self._refresh_operation_restriction_state()
            
            # Create empty transform data for mouse operations (rotation, translation, scale)
            self.base_transform_data = [(0.0, 0.0, 0.0, 1.0) for _ in range(self.page_count)]
            
            # Generate base_pages list for display and reference
            self.base_pages = [f"Page {i+1}" for i in range(self.page_count)]

            # Main processing: build actual PNG path list from converter output.
            self.base_page_paths = []
            try:
                temp_dir_path = Path(str(temp_dir))
                for page_num in range(1, self.page_count + 1):
                    candidate = temp_dir_path / f"base_{page_num:04d}.png"
                    if candidate.exists():
                        self.base_page_paths.append(candidate)
            except Exception:
                self.base_page_paths = []
            
            # Set up page control frame first to ensure page numbers are visible
            self._create_page_control_frame(self.page_count)

            # Main processing: check page size uniformity for batch edit (M1-010).
            self._check_batch_edit_eligibility()

            # Initialize mouse handler with the transform data
            self._setup_mouse_events(self.page_count)
            
            # Display the first page
            self._display_page(self.current_page_index)

            # Main processing: ensure the canvas can receive keyboard shortcuts.
            try:
                self.canvas.focus_set()
            except Exception:
                pass
            
            # Update page control frame explicitly
            if self.page_control_frame:
                self.page_control_frame.update_page_label(self.current_page_index, self.page_count)

            # Main processing: show confirmation dialog for copy-protected PDFs.
            if self._copy_protected:
                self.after(1700, self._show_copy_protected_confirmation_dialog)
            
            # Log success
            logger.info(message_manager.get_log_message("L276", 
                       str(self.page_count), str(file_path)))
                       
        except Exception as e:
            logger.error(message_manager.get_log_message("L277", str(e)))
            # Output error stack trace
            import traceback
            logger.error(traceback.format_exc())

    def _is_copy_protected(self) -> bool:
        """Return True if the currently loaded PDF should be treated as copy-protected.

        Returns:
            bool: True when copy-protected (operations must be blocked)
        """
        if not hasattr(self, 'file_path_info') or not self.file_path_info:
            return False

        meta = getattr(self.file_path_info, 'file_meta_info', None)
        if not isinstance(meta, dict):
            return False

        if "CopyProtected" in meta:
            return bool(meta.get("CopyProtected"))

        return bool(meta.get("Encrypted"))

    def _refresh_operation_restriction_state(self) -> None:
        """Refresh the operation enabled/disabled state based on current metadata."""
        self._copy_protected = self._is_copy_protected()
        self._visual_adjustments_enabled = not self._copy_protected

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.set_edit_buttons_enabled(not self._copy_protected)
            except Exception:
                pass

        if self.mouse_handler is not None:
            try:
                self.mouse_handler.set_operations_enabled(self._visual_adjustments_enabled)
            except Exception:
                pass

    def _show_copy_protected_confirmation_dialog(self) -> None:
        """Show an OK-only confirmation dialog for copy-protected PDFs.

        This dialog enables rotation and other visual adjustments after the user
        confirms. Insert/Finish remain disabled.
        """
        # Main processing: release any existing grab (e.g., ProgressWindow) before showing a modal dialog.
        try:
            top = self.winfo_toplevel()
            current_grab = top.grab_current()
            if current_grab is not None:
                current_grab.grab_release()
        except Exception:
            pass

        # Main processing: show OK-only modal dialog near the canvas center.
        self._show_modal_ok_dialog_near_canvas(
            title=message_manager.get_ui_message("U033"),
            message=message_manager.get_user_message("M056"),
        )

        self._visual_adjustments_enabled = True
        if self.mouse_handler is not None:
            try:
                self.mouse_handler.set_operations_enabled(True)
            except Exception:
                pass

        try:
            self.canvas.focus_set()
        except Exception:
            pass

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.set_edit_buttons_enabled(False)
            except Exception:
                pass

    def _show_modal_ok_dialog_near_canvas(self, title: str, message: str) -> None:
        """Show a modal OK-only dialog near the center of the canvas.

        Args:
            title: Dialog title.
            message: Dialog body message.
        """
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())

        # Main processing: build UI.
        container = ttk.Frame(dialog, padding=12)
        container.pack(fill="both", expand=True)

        msg_label = ttk.Label(container, text=message, justify="left", wraplength=520)
        msg_label.pack(fill="x", expand=True)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(12, 0))

        def on_ok() -> None:
            dialog.destroy()

        ok_btn = ttk.Button(btn_frame, text="OK", command=on_ok)
        ok_btn.pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", on_ok)

        # Main processing: place dialog near canvas center.
        try:
            self.update_idletasks()
            self.canvas.update_idletasks()
            dialog.update_idletasks()

            center_x = self.canvas.winfo_rootx() + (self.canvas.winfo_width() // 2)
            center_y = self.canvas.winfo_rooty() + (self.canvas.winfo_height() // 2)

            width = max(dialog.winfo_reqwidth(), dialog.winfo_width())
            height = max(dialog.winfo_reqheight(), dialog.winfo_height())

            x = int(center_x - (width // 2))
            y = int(center_y - (height // 2))

            dialog.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

        try:
            dialog.lift()
            dialog.grab_set()
            ok_btn.focus_set()
            dialog.wait_window(dialog)
        finally:
            try:
                dialog.grab_release()
            except Exception:
                pass

    def _ensure_visual_adjustments_enabled(self) -> bool:
        """Return whether visual adjustments are enabled.

        Returns:
            bool: True when visual adjustments are enabled.
        """
        return bool(getattr(self, "_visual_adjustments_enabled", True))

    def _display_page(self, page_index: int) -> None:
        """Display specified page of the current PDF document using PNG files.
        
        Args:
            page_index (int): Index of the page to display (0-based)
        """
        try:
            # ... (rest of the code remains the same)
            # Check if page information is available
            if not hasattr(self, 'file_path_info') or not self.file_path_info:
                logger.warning(message_manager.get_log_message("L282"))
                return
                
            # Validate page index
            if not (0 <= page_index < self.page_count):
                logger.warning(message_manager.get_log_message("L283", 
                             str(page_index), str(self.page_count-1)))
                return
            
            # Main processing: prefer actual path list from converter output.
            png_path: Path
            if hasattr(self, 'base_page_paths') and self.base_page_paths and page_index < len(self.base_page_paths):
                png_path = self.base_page_paths[page_index]
            else:
                if hasattr(self, 'current_pdf_converter') and self.current_pdf_converter and hasattr(self.current_pdf_converter, '_temp_dir'):
                    temp_dir = self.current_pdf_converter._temp_dir
                else:
                    temp_dir = get_temp_dir()
                png_filename = f"base_{page_index + 1:04d}.png"
                png_path = Path(str(temp_dir)) / png_filename
            
            # Use LogThrottle to prevent excessive logging of the same PNG path
            # Only log once per file path every 5 seconds
            png_path_str = str(png_path)
            if not hasattr(self, '_png_path_log_throttle'):
                self._png_path_log_throttle: Dict[str, LogThrottle] = {}
            
            if png_path_str not in self._png_path_log_throttle:
                self._png_path_log_throttle[png_path_str] = LogThrottle(min_interval=5.0)
                
            if self._png_path_log_throttle[png_path_str].should_log("png_path_check"):
                # Looking for PNG file at path
                logger.debug(message_manager.get_log_message("L346", str(png_path)))
            
            # Check if PNG file exists
            if not png_path.exists():
                logger.warning(message_manager.get_log_message("L279", str(png_path)))
                return
            
            # Load the PNG file
            pil_image: Union[Image.Image, ImageFile] = Image.open(png_path)

            # Main processing: store original (pre-transform) dimensions for footer metadata (M1-009 fix).
            self._original_page_width = pil_image.width
            self._original_page_height = pil_image.height

            # Main processing: pass original image size to mouse handler for rotation pivot math.
            if self.mouse_handler is not None and hasattr(self.mouse_handler, "set_original_image_size"):
                try:
                    self.mouse_handler.set_original_image_size(pil_image.width, pil_image.height)
                except Exception:
                    pass
            
            # Apply any transformations from transform data
            if hasattr(self, 'base_transform_data') and len(self.base_transform_data) > page_index:
                # Get transform data for current page
                rotation, translate_x, translate_y, scale = self.base_transform_data[page_index]
                
                # Apply transformations if needed
                if rotation != 0 or scale != 1.0:
                    # Apply rotation if needed (PIL can handle any rotation angle, not limited to 90 degree increments)
                    if rotation != 0:
                        # Use cast to handle type compatibility
                        # PIL can rotate by any angle - no need to normalize to 90 degree increments
                        rotated_image = pil_image.rotate(rotation, resample=Resampling.BICUBIC, expand=True)
                        pil_image = cast(Union[Image.Image, ImageFile], rotated_image)
                    
                    # Apply scaling if needed
                    if scale != 1.0:
                        new_width = int(pil_image.width * scale)
                        new_height = int(pil_image.height * scale)
                        if new_width > 0 and new_height > 0:
                            # Use cast to handle type compatibility
                            resized_image = pil_image.resize((new_width, new_height), Resampling.LANCZOS)
                            pil_image = cast(Union[Image.Image, ImageFile], resized_image)
            
            # Convert to PhotoImage for display
            photo_image = ImageTk.PhotoImage(pil_image)
            self.photo_image = photo_image  # Keep reference to prevent garbage collection
            
            # Clear canvas (keep overlay items)
            self.canvas.delete("pdf_image")
            
            # Display image with any translation offset
            if hasattr(self, 'base_transform_data') and self.base_transform_data:
                _, translate_x, translate_y, _ = self.base_transform_data[page_index]
                self.canvas.create_image(
                    int(translate_x), int(translate_y),
                    anchor="nw", 
                    image=self.photo_image,
                    tags=("pdf_image",),
                )
            else:
                self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image, tags=("pdf_image",))

            try:
                self.canvas.tag_lower("pdf_image")
            except Exception:
                pass
            
            # Update scroll region
            try:
                self.canvas.config(scrollregion=self.canvas.bbox("pdf_image"))
            except Exception:
                self.canvas.config(scrollregion=self.canvas.bbox("all"))

            # Store previous page index to check if page actually changed
            previous_page_index = getattr(self, 'current_page_index', None)
            
            # Update current page index
            self.current_page_index = page_index
            
            # Update page control frame
            if self.page_control_frame:
                # Only update label if page index changed
                if previous_page_index != page_index:
                    self.page_control_frame.update_page_label(page_index, self.page_count)
                
            # Update mouse handler
            if self.mouse_handler:
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

            # Main processing: refresh overlay positions after state update.
            if self.mouse_handler is not None and hasattr(self.mouse_handler, "refresh_overlay_positions"):
                try:
                    self.mouse_handler.refresh_overlay_positions()
                except Exception:
                    pass
            
            # Log displayed page information only if page actually changed
            if previous_page_index != page_index:
                logger.info(message_manager.get_log_message("L284", page_index + 1, self.page_count))

            # Update transform info display (M1-008)
            if self.page_control_frame is not None and hasattr(self, 'base_transform_data'):
                if page_index < len(self.base_transform_data):
                    r, tx, ty, s = self.base_transform_data[page_index]
                    self.page_control_frame.update_transform_info(r, tx, ty, s)

            # Update footer metadata label (M1-009)
            self._update_footer_meta(pil_image)

        except Exception as e:
            # Error displaying page
            logger.error(message_manager.get_log_message("L285", str(e)))
            import traceback
            logger.error(traceback.format_exc())

    def _update_footer_meta(self, pil_image: Union[Image.Image, 'ImageFile']) -> None:
        """Update the footer metadata label with image size, DPI, and paper size (M1-009).

        Displays labeled image width/height in pixels, DPI used during conversion,
        and estimated paper size (e.g. A4, A3) if dimensions match a known size.
        Uses original (pre-transform) dimensions so that zoom/rotation does not
        affect the displayed pixel size or paper size estimation.
        Labels are localized via message codes U072-U074.
        Shows '-' when information is missing.

        Args:
            pil_image: The loaded PIL image for the current page (unused after fix;
                       original dimensions come from self._original_page_width/height).
        """
        try:
            if not hasattr(self, '_footer_meta_label'):
                return

            # Main processing: use original (pre-transform) dimensions (M1-009 zoom fix).
            width = getattr(self, '_original_page_width', None)
            height = getattr(self, '_original_page_height', None)

            # Main processing: build labeled pixel size text (U072).
            lbl_size = message_manager.get_ui_message("U072")  # "Pixel size:" / "ピクセルサイズ:"
            size_text = f"{lbl_size} {width} x {height} px" if width and height else f"{lbl_size} -"

            # Main processing: get DPI from stored conversion value (M1-009 fix).
            dpi_val = getattr(self, '_conversion_dpi', None)
            lbl_dpi = message_manager.get_ui_message("U073")  # "Pixel density:" / "ピクセル密度:"
            dpi_text = f"{lbl_dpi} {dpi_val}dpi" if dpi_val else f"{lbl_dpi} -"

            # Main processing: estimate paper size from original pixel dimensions and DPI.
            lbl_paper = message_manager.get_ui_message("U074")  # "Paper size:" / "用紙サイズ:"
            paper_name = self._estimate_paper_size(width, height, dpi_val) if (width and height and dpi_val) else ""

            # Compose footer text
            footer_text = f"{size_text}  |  {dpi_text}"
            if paper_name:
                footer_text += f"  |  {lbl_paper} {paper_name}"
            self._footer_meta_label.configure(text=footer_text)
        except Exception:
            try:
                self._footer_meta_label.configure(text="-")
            except Exception:
                pass

    @staticmethod
    def _estimate_paper_size(width_px: int, height_px: int, dpi: int) -> str:
        """Estimate standard paper size from pixel dimensions and DPI.

        Compares the physical dimensions (mm) against known ISO/JIS paper sizes
        with a tolerance of ±5mm.

        Args:
            width_px: Image width in pixels.
            height_px: Image height in pixels.
            dpi: Dots per inch used during conversion.

        Returns:
            Paper size name (e.g. 'A4') or empty string if no match.
        """
        # Convert pixels to mm: mm = px / dpi * 25.4
        w_mm = width_px / dpi * 25.4
        h_mm = height_px / dpi * 25.4
        # Ensure portrait orientation for comparison (shorter side = width)
        w_mm, h_mm = min(w_mm, h_mm), max(w_mm, h_mm)

        # Known paper sizes (width_mm, height_mm, name)
        paper_sizes = [
            (148, 210, "A5"),
            (210, 297, "A4"),
            (297, 420, "A3"),
            (420, 594, "A2"),
            (594, 841, "A1"),
            (841, 1189, "A0"),
            (182, 257, "B5"),
            (257, 364, "B4"),
            (364, 515, "B3"),
            (216, 279, "Letter"),
            (216, 356, "Legal"),
        ]
        tolerance = 5  # mm
        for pw, ph, name in paper_sizes:
            if abs(w_mm - pw) <= tolerance and abs(h_mm - ph) <= tolerance:
                return name
        return ""

    def _check_batch_edit_eligibility(self) -> None:
        """Check if all pages have the same dimensions and enable/disable batch edit (M1-010).

        Opens each page PNG to read its dimensions. If all pages share the
        same width and height, batch edit is allowed. Otherwise it is disabled.
        """
        try:
            if not self.page_control_frame:
                return
            if not hasattr(self, 'base_page_paths') or len(self.base_page_paths) <= 1:
                # Single page or no paths: allow batch edit (no conflict possible)
                self.page_control_frame.set_batch_edit_enabled(True)
                return

            # Main processing: compare dimensions of all pages.
            first_size = None
            uniform = True
            for page_path in self.base_page_paths:
                try:
                    with Image.open(page_path) as img:
                        size = (img.width, img.height)
                except Exception:
                    continue
                if first_size is None:
                    first_size = size
                elif size != first_size:
                    uniform = False
                    break

            self.page_control_frame.set_batch_edit_enabled(uniform)
        except Exception:
            pass

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
                # Update the page control UI (1-based index for display)
                self.page_control_frame.update_page_label(self.current_page_index, page_count)
                
            # Log page movement
            logger.info(message_manager.get_log_message("L290", self.current_page_index + 1, page_count))
        else:
            # Already at first page
            logger.info(message_manager.get_log_message("L291"))
            # Show info message that this is the first page
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U058"))
            
    def _on_mouse_wheel(self, event: Any) -> None:
        """
        Handle mouse wheel events for zooming in/out.
        
        Args:
            event: Mouse wheel event
        """
        try:
            # Check if PDF is loaded
            if not hasattr(self, 'file_path_info') or not self.file_path_info:
                return
                
            # Check if mouse handler exists
            if not self.mouse_handler:
                return
                
            # Forward the event to the mouse handler
            if hasattr(self.mouse_handler, 'on_mouse_wheel'):
                self.mouse_handler.on_mouse_wheel(event)
        except Exception as e:
            # Always log errors regardless of throttling
            logger.error(message_manager.get_log_message("L300", str(e)))
        
        # Reset bindings immediately to ensure wheel events are captured
        self._rebind_mouse_wheel()

    def _rebind_mouse_wheel(self) -> None:
        """Rebind mouse wheel event bindings."""
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)    # Linux UP
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)    # Linux DOWN
        
    def _on_next_page(self) -> None:
        """Go to next page."""
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
                # Update the page control UI (1-based index for display)
                self.page_control_frame.update_page_label(self.current_page_index, page_count)
                
            # Log page movement
            logger.info(message_manager.get_log_message("L294", self.current_page_index + 1, page_count))
        else:
            # Already at last page
            logger.info(message_manager.get_log_message("L295"))
            # Show info message that this is the last page
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U059"))
    
    def _on_page_entry(self, event: tk.Event) -> None:
        """Handle page entry event."""
        try:
            # Log page entry event
            logger.info(message_manager.get_log_message("L305"))
            
            # Get the page control frame
            if not self.page_control_frame:
                logger.info(message_manager.get_log_message("L306"))
                return
                
            # Get the entered page number (1-based)
            page_num = self.page_control_frame.page_var.get()
            
            # Convert to 0-based index and validate
            page_index = page_num - 1
            if page_index < 0 or not hasattr(self, 'page_count') or page_index >= self.page_count:
                logger.warning(message_manager.get_log_message("L307", str(page_num), str(self.page_count)))
                return
                
            # Update current page index and display
            self.current_page_index = page_index
            self._display_page(self.current_page_index)
            
            # Update page label (page_num is already 1-based)
            self.page_control_frame.update_page_label(self.current_page_index, self.page_count)
            
            # Log success
            logger.info(message_manager.get_log_message("L308", str(page_num), str(self.page_count)))
        except Exception as e:
            # Log error
            logger.error(message_manager.get_log_message("L309", str(e)))
            # Show error message
            messagebox.showerror(message_manager.get_ui_message("U056"), 
                               message_manager.get_ui_message("U060") + str(e))
        
    def _setup_mouse_events(self, page_count: int) -> None:
        """Set up mouse events for canvas operations.
        
        Args:
            page_count: Number of pages in the PDF
        """
        # Create layer transform data dictionary
        layer_transform_data = {
            0: self.base_transform_data,  # Layer 0 = base
        }
        
        # Create visibility layer dictionary
        visible_layers = {
            0: True,  # Base is visible
            1: False  # Comp is not visible
        }
        
        # Clear any existing mouse handler
        if self.mouse_handler is not None:
            # Remove existing bindings
            self.canvas.unbind("<Button-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.unbind("<ButtonRelease-1>")
            self.canvas.unbind("<Button-3>")
            
        # Create a new mouse event handler with the required parameters
        mouse_handler = MouseEventHandler(
            layer_transform_data=layer_transform_data,
            current_page_index=self.current_page_index,
            visible_layers=visible_layers,
            on_transform_update=self._on_transform_update,
            operations_enabled=self._visual_adjustments_enabled,
        )
        
        # Attach mouse handler to canvas
        mouse_handler.attach_to_canvas(self.canvas)
        
        # Update the mouse handler state with current page data
        mouse_handler.update_state(
            current_page_index=self.current_page_index,
            visible_layers=visible_layers
        )
        
        # Store the mouse handler
        self.mouse_handler = mouse_handler
        
        # Log mouse handler creation
        logger.info(message_manager.get_log_message("L301", page_count))
        
        # Explicitly bind mouse events to ensure they work
        self.canvas.bind(
            "<Button-1>",
            lambda e: (self.canvas.focus_set() or (self.mouse_handler.on_mouse_down(e) if self.mouse_handler else None)),
        )
        self.canvas.bind("<B1-Motion>", lambda e: self.mouse_handler.on_mouse_drag(e) if self.mouse_handler else None)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.mouse_handler.on_mouse_up(e) if self.mouse_handler else None)
        self.canvas.bind("<Button-3>", lambda e: self.mouse_handler.on_right_click(e) if self.mouse_handler and hasattr(self.mouse_handler, 'on_right_click') else None)
        
        # MouseWheel events are handled in PDFOperationApp class
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)  # Linux scroll down

        self._bind_global_shortcuts()
        
        # Log event binding
        logger.info(message_manager.get_log_message("L302"))

    def _bind_global_shortcuts(self) -> None:
        """Bind global keyboard shortcuts for transform operations."""
        # Main processing: clear existing bindings to avoid duplicates on reload.
        for seq in [
            "<Control-r>", "<Control-R>",
            "<Control-l>", "<Control-L>",
            "<Control-v>", "<Control-V>",
            "<Control-h>", "<Control-H>",
            "<Control-b>", "<Control-B>",
            "<Control-question>",
            "<Control-slash>",
            "<Control-Shift-slash>",
            "<Control-Shift-h>",
            "<Control-Shift-H>",
            "<KeyRelease-Control_L>",
            "<KeyRelease-Control_R>",
            "<Control-plus>",
            "<Control-minus>",
        ]:
            try:
                self.unbind_all(seq)
            except Exception:
                pass

        # Main processing: rotation / flip / reset shortcuts are handled by MouseEventHandler.
        self.bind_all("<Control-r>", self._on_shortcut_rotate_right)
        self.bind_all("<Control-R>", self._on_shortcut_rotate_right)
        self.bind_all("<Control-l>", self._on_shortcut_rotate_left)
        self.bind_all("<Control-L>", self._on_shortcut_rotate_left)
        self.bind_all("<Control-v>", self._on_shortcut_flip_vertical)
        self.bind_all("<Control-V>", self._on_shortcut_flip_vertical)
        self.bind_all("<Control-h>", self._on_shortcut_flip_horizontal)
        self.bind_all("<Control-H>", self._on_shortcut_flip_horizontal)
        self.bind_all("<Control-b>", self._on_shortcut_reset_transform)
        self.bind_all("<Control-B>", self._on_shortcut_reset_transform)

        # Main processing: toggle shortcut help.
        self.bind_all("<Control-question>", self._on_shortcut_toggle_shortcut_help)
        self.bind_all("<Control-slash>", self._on_shortcut_toggle_shortcut_help)
        self.bind_all("<Control-Shift-slash>", self._on_shortcut_toggle_shortcut_help)
        self.bind_all("<Control-Shift-h>", self._on_shortcut_toggle_shortcut_help)
        self.bind_all("<Control-Shift-H>", self._on_shortcut_toggle_shortcut_help)

        # Main processing: ensure rotation mode exits when Ctrl is released.
        self.bind_all("<KeyRelease-Control_L>", self._on_shortcut_ctrl_key_release)
        self.bind_all("<KeyRelease-Control_R>", self._on_shortcut_ctrl_key_release)

        # Main processing: zoom shortcuts are handled by this view.
        self.bind_all("<Control-plus>", self._on_shortcut_zoom_in)
        self.bind_all("<Control-minus>", self._on_shortcut_zoom_out)

    def _on_shortcut_rotate_right(self, event: tk.Event) -> str:
        """Handle Ctrl+R shortcut."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_rotate_right(event) or "break")

    def _on_shortcut_rotate_left(self, event: tk.Event) -> str:
        """Handle Ctrl+L shortcut."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_rotate_left(event) or "break")

    def _on_shortcut_flip_vertical(self, event: tk.Event) -> str:
        """Handle Ctrl+V shortcut."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_flip_vertical(event) or "break")

    def _on_shortcut_flip_horizontal(self, event: tk.Event) -> str:
        """Handle Ctrl+H shortcut."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_flip_horizontal(event) or "break")

    def _on_shortcut_reset_transform(self, event: tk.Event) -> str:
        """Handle Ctrl+B shortcut."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_reset_transform(event) or "break")

    def _on_shortcut_toggle_shortcut_help(self, event: tk.Event) -> str:
        """Handle Ctrl+? shortcut."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._toggle_shortcut_help(event) or "break")

    def _on_shortcut_ctrl_key_release(self, event: tk.Event) -> str:
        """Handle Ctrl key release."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_ctrl_key_release(event) or "break")

    def _on_shortcut_zoom_in(self, event: tk.Event) -> str:
        """Handle Ctrl+Plus shortcut."""
        self._zoom_in()
        return "break"

    def _on_shortcut_zoom_out(self, event: tk.Event) -> str:
        """Handle Ctrl+Minus shortcut."""
        self._zoom_out()
        return "break"

    def _on_transform_update(self) -> None:
        """Callback when transform data is updated.

        When batch edit mode is enabled (M1-010), propagates the current
        page's transform data to all other pages before redrawing.
        """
        # Redisplay the current page with updated transform data
        # Main processing: guard against invalid state during initialization.
        if not hasattr(self, 'page_count') or self.page_count <= 0:
            return

        # Main processing: propagate transform to all pages when batch edit is ON (M1-010).
        if (self.page_control_frame
                and hasattr(self.page_control_frame, 'batch_edit_var')
                and self.page_control_frame.batch_edit_var.get()
                and hasattr(self, 'base_transform_data')):
            current_transform = self.base_transform_data[self.current_page_index]
            for i in range(len(self.base_transform_data)):
                if i != self.current_page_index:
                    self.base_transform_data[i] = current_transform

        self._display_page(self.current_page_index)
    
    def _on_transform_value_input(self, rotation: float, tx: float,
                                   ty: float, scale: float) -> None:
        """Apply user-entered transform values to the current page.

        Called from PageControlFrame when the user presses Enter in one of the
        transform entry fields.

        Args:
            rotation: Rotation angle in degrees.
            tx: X translation offset.
            ty: Y translation offset.
            scale: Scale factor.
        """
        if not hasattr(self, 'base_transform_data'):
            return
        if self.current_page_index >= len(self.base_transform_data):
            return

        # Main processing: update transform data and refresh display.
        self.base_transform_data[self.current_page_index] = (rotation, tx, ty, scale)
        self._on_transform_update()

    def _reset_transform(self) -> None:
        """Reset transformation for the current page."""
        if not self._ensure_visual_adjustments_enabled():
            return

        # Reset transform data for the current page
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Reset to default transform values (0 rotation, 0,0 position, 1.0 scale)
            self.base_transform_data[self.current_page_index] = (0.0, 0.0, 0.0, 1.0)
            self._on_transform_update()
    
    def _zoom_in(self) -> None:
        """Zoom in on the current page."""
        if not self._ensure_visual_adjustments_enabled():
            return

        # Apply zoom by scaling
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Get current transform data
            rotation, tx, ty, scale = self.base_transform_data[self.current_page_index]
            # Apply smoother zoom increment
            scale *= 1.05  # Smaller increment for smoother zooming
            # Update transform data
            self.base_transform_data[self.current_page_index] = (rotation, tx, ty, scale)
            self._on_transform_update()
    
    def _zoom_out(self) -> None:
        """Zoom out on the current page."""
        if not self._ensure_visual_adjustments_enabled():
            return

        # Apply zoom by scaling
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Get current transform data
            rotation, tx, ty, scale = self.base_transform_data[self.current_page_index]
            # Apply smoother zoom decrement
            scale *= 0.95  # Smaller decrement for smoother zooming
            # Update transform data
            self.base_transform_data[self.current_page_index] = (rotation, tx, ty, scale)
            self._on_transform_update()
            
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

    def _create_page_control_frame(self, page_count: int) -> None:
        """Create or recreate the page control frame.

        Args:
            page_count (int): Number of pages in the loaded document.
        """
        try:
            # Main processing: destroy previous frame to avoid duplicated controls.
            if self.page_control_frame is not None:
                try:
                    self.page_control_frame.destroy()
                except Exception:
                    pass
                self.page_control_frame = None

            # Main processing: place controls next to the canvas without changing the canvas grid.
            self.frame_main2.grid_columnconfigure(1, weight=0)

            self.page_control_frame = PageControlFrame(
                parent=self.frame_main2,
                color_key="page_control",
                base_pages=self.base_pages,
                comp_pages=[],
                base_transform_data=self.base_transform_data,
                comp_transform_data=[],
                visualized_image=self.visualized_image,
                page_amount_limit=max(1, int(page_count)),
                on_prev_page=self._on_prev_page,
                on_next_page=self._on_next_page,
                on_insert_blank=self._on_insert_blank_page,
                on_delete_page=self._on_delete_page,
                on_export=self._on_complete_edit,
                on_page_entry=self._on_page_entry,
                on_transform_value_change=self._on_transform_value_input,
            )
            self.page_control_frame.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=5)

            self.page_control_frame.update_page_label(self.current_page_index, page_count)
            self.page_control_frame.set_edit_buttons_enabled(not self._copy_protected)
        except Exception as e:
            logger.error(message_manager.get_log_message("L285", str(e)))
            import traceback
            logger.error(traceback.format_exc())
    
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
    
    def _on_insert_blank_page(self) -> None:
        """Insert a blank page after the current page.

        The blank page size matches the currently displayed page's dimensions
        so that portrait/landscape and page size are preserved.
        """
        if self._copy_protected:
            return

        if not hasattr(self, 'page_count') or self.page_count == 0:
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return

        # Main processing: match blank page size to the current page (M1-010 fix).
        blank_size = (595, 842)  # fallback: A4 portrait at ~72 DPI
        try:
            if hasattr(self, 'base_page_paths') and self.current_page_index < len(self.base_page_paths):
                with Image.open(self.base_page_paths[self.current_page_index]) as cur_img:
                    blank_size = (cur_img.width, cur_img.height)
        except Exception:
            pass
        blank_img = Image.new('RGBA', blank_size, (255, 255, 255, 255))
        
        # Get temp directory for saving the blank page
        if hasattr(self, 'current_pdf_converter') and self.current_pdf_converter and hasattr(self.current_pdf_converter, '_temp_dir'):
            temp_dir = self.current_pdf_converter._temp_dir
        else:
            temp_dir = get_temp_dir()
            
        # Insertion position (after current page)
        insert_position = self.current_page_index + 1
        
        # Main processing: use unique filename to avoid overwriting existing page files.
        import uuid
        png_filename = f"base_blank_{uuid.uuid4().hex[:8]}.png"
        png_path = Path(str(temp_dir)) / png_filename
        
        # Save the blank image
        blank_img.save(png_path, format="PNG")
        
        # Update page count and transform data
        self.page_count += 1
        self.base_transform_data.insert(insert_position, (0.0, 0.0, 0.0, 1.0))

        # Main processing: insert new path into base_page_paths at the correct position.
        if hasattr(self, 'base_page_paths'):
            self.base_page_paths.insert(insert_position, png_path)

        # Update base_pages
        self.base_pages = [f"Page {i+1}" for i in range(self.page_count)]
        
        # Refresh UI
        self._create_page_control_frame(self.page_count)
        self._check_batch_edit_eligibility()
        self._display_page(insert_position)  # Show the new blank page
        
        logger.info(message_manager.get_log_message("L304", insert_position + 1))

    def _on_delete_page(self) -> None:
        """Delete the currently displayed page after user confirmation (M1-007).

        Shows a confirmation dialog before deleting. If only one page remains,
        shows a warning and aborts.
        """
        if self._copy_protected:
            return

        if not hasattr(self, 'page_count') or self.page_count == 0:
            messagebox.showinfo(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message("U057"))
            return

        # Cannot delete the only remaining page
        if self.page_count <= 1:
            messagebox.showinfo(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message("U063"))
            return

        # Show confirmation dialog
        result = messagebox.askyesno(
            message_manager.get_ui_message("U033"),
            message_manager.get_ui_message("U062"))
        if not result:
            return

        # Main processing: remove the current page from data structures.
        delete_index = self.current_page_index

        # Remove transform data
        if delete_index < len(self.base_transform_data):
            self.base_transform_data.pop(delete_index)

        # Remove page path
        if hasattr(self, 'base_page_paths') and delete_index < len(self.base_page_paths):
            self.base_page_paths.pop(delete_index)

        # Update page count
        self.page_count -= 1
        self.base_pages = [f"Page {i+1}" for i in range(self.page_count)]

        # Determine which page to show after deletion
        if self.current_page_index >= self.page_count:
            self.current_page_index = max(0, self.page_count - 1)

        # Refresh UI
        self._create_page_control_frame(self.page_count)
        self._check_batch_edit_eligibility()
        self._display_page(self.current_page_index)

        logger.info(message_manager.get_log_message("L304", delete_index + 1))

    def _on_complete_edit(self) -> None:
        """Complete the editing process and export the PDF."""
        if self._copy_protected:
            return

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
        base_file_name = os.path.basename(self.base_path.get())
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
            
    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Apply theme colors to the PDF operation tab widgets.
        
        Args:
            theme_data (Dict[str, Any]): Theme data obtained from ColorThemeManager.load_theme
        """
        try:
            # Apply theme to frame backgrounds
            window_settings = theme_data.get("Window", {})
            window_bg = window_settings.get("bg", "#ffffff")
            frame_settings = theme_data.get("Frame", {})
            frame_bg = frame_settings.get("bg", window_bg)
            for attr_name in ["frame_main0", "frame_main1", "frame_main2"]:
                if hasattr(self, attr_name):
                    frame = getattr(self, attr_name)
                    if frame is not None:
                        frame.configure(bg=frame_bg)
                
            # Apply theme to footer metadata label (M1-009)
            if hasattr(self, '_footer_meta_label') and self._footer_meta_label:
                label_fg = frame_settings.get("fg", "#000000")
                self._footer_meta_label.configure(bg=frame_bg, fg=label_fg)

            # Apply theme to canvas
            canvas_settings = theme_data.get("canvas", {})
            if canvas_settings and hasattr(self, "canvas"):
                self._config_widget(canvas_settings)
                
            logger.debug(message_manager.get_log_message("L211", "PDF operation tab"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L199", str(e)))
    
    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget-specific theme settings for the canvas.
        
        Args:
            theme_settings (Dict[str, Any]): Widget-specific theme settings
        """
        try:
            if hasattr(self, "canvas"):
                self.canvas.configure(
                    background=theme_settings.get("background", "#ffffff"),
                    highlightbackground=theme_settings.get("highlightbackground", "#e0e0e0"),
                    highlightcolor=theme_settings.get("highlightcolor", "#e0e0e0"),
                )
                
            logger.debug(message_manager.get_log_message("L200", self.__class__.__name__, theme_settings))
        except Exception as e:
            logger.error(message_manager.get_log_message("L201", self.__class__.__name__, str(e)))
