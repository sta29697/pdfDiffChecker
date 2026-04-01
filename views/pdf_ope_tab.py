from __future__ import annotations

from logging import getLogger
import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from utils.log_throttle import LogThrottle
import os
from pathlib import Path

# PIL imports
from PIL import Image, ImageTk
from PIL.Image import Resampling, Transpose
from PIL.ImageFile import ImageFile

from configurations.message_manager import get_message_manager
from controllers.color_theme_manager import ColorThemeManager
from controllers.mouse_event_handler import MouseEventHandler
from controllers.drag_and_drop_file import DragAndDropHandler
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.color_theme_change_button import ColorThemeChangeButton
from widgets.language_select_combobox import LanguageSelectCombo
from widgets.base_path_entry import BasePathEntry
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_label_class import BaseLabelClass
from widgets.page_control_frame import PageControlFrame
from utils.utils import create_unique_file_path, get_temp_dir
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog
from utils.workspace_input_formats import (
    MAIN_PDF_OPE_INPUT_EXTENSIONS,
    main_pdf_ope_askopen_filetypes,
    main_pdf_ope_drop_suffixes,
)
from utils.path_normalization import normalize_host_path
from utils.transform_tuple import as_transform6, pack_transform6
from controllers.file2png_by_page import build_workspace_input_converter
from controllers.pdf_export_handler import PDFExportHandler
from models.class_dictionary import FilePathInfo
from themes.coloring_theme_interface import ColoringThemeIF
from controllers.widgets_tracker import WidgetsTracker
from configurations.user_setting_manager import UserSettingManager

logger = getLogger(__name__)
message_manager = get_message_manager()

class PDFOperationApp(ttk.Frame, ColoringThemeIF):
    """PDF operation tab."""

    # Sequences registered with bind_all while this notebook tab is active (avoid duplicate main-tab handlers).
    _GLOBAL_SHORTCUT_SEQUENCES: tuple[str, ...] = (
        "<Control-r>",
        "<Control-R>",
        "<Control-Shift-r>",
        "<Control-Shift-R>",
        "<Control-l>",
        "<Control-L>",
        "<Control-Shift-l>",
        "<Control-Shift-L>",
        "<Control-Alt-r>",
        "<Control-Alt-R>",
        "<Control-Alt-l>",
        "<Control-Alt-L>",
        "<Control-v>",
        "<Control-V>",
        "<Control-h>",
        "<Control-H>",
        "<Control-b>",
        "<Control-B>",
        "<Control-question>",
        "<Control-slash>",
        "<Control-Shift-slash>",
        "<Control-Shift-h>",
        "<Control-Shift-H>",
        "<KeyRelease-Control_L>",
        "<KeyRelease-Control_R>",
        "<Control-plus>",
        "<Control-minus>",
    )

    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        """Initialize the PDF operation tab.

        Args:
            master (Optional[tk.Misc]): Parent widget
            **kwargs: Additional keyword arguments
        """
        super().__init__(master, **kwargs)
        WidgetsTracker().add_widgets(self)
        self._pdf_global_shortcuts_active: bool = False
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
        self._show_pdf_reference_grid_var = tk.BooleanVar(
            value=bool(UserSettingManager().get_setting("show_reference_grid", False)),
        )

        # Create frames without borders
        self.frame_main0 = tk.Frame(self)
        self.frame_main0.grid(row=0, column=0, sticky="we", ipady=2)
        self.frame_main0.grid_columnconfigure(1, weight=1)  # This column will expand
        
        self.frame_main1 = tk.Frame(self)
        self.frame_main1.grid(row=1, column=0, sticky="we", ipady=2)
        self.frame_main1.grid_columnconfigure(1, weight=1)  # Entry column expands
        
        self.frame_main2 = tk.Frame(self)
        self.frame_main2.grid(row=2, column=0, sticky="nsew")
        self.frame_main2.grid_columnconfigure(0, weight=1)
        self.frame_main2.grid_rowconfigure(0, weight=1)  # Make canvas row expandable

        # Create canvas (same background resolution as Main tab preview)
        _theme0 = ColorThemeManager.get_instance().get_current_theme()
        _nb0 = _theme0.get("Notebook", {})
        _cv0 = dict(_theme0.get("canvas", {}))
        _canvas_bg0 = _cv0.get(
            "background",
            _nb0.get("tab_bg", _nb0.get("bg", "#1d1d29")),
        )
        self.canvas = tk.Canvas(
            self.frame_main2,
            bg=_canvas_bg0,
            relief=tk.FLAT,
            borderwidth=0,
            takefocus=1,
            highlightthickness=2,
            highlightbackground=_cv0.get("highlightbackground", "#888888"),
            highlightcolor=_cv0.get("highlightcolor", "#e0e0e0"),
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
        self._footer_meta_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 2))
        self._pdf_shortcut_guide_frame: Optional[tk.Frame] = None
        self._pdf_shortcut_guide_label: Optional[tk.Label] = None

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
        self.base_transform_data: list[Tuple[float, ...]] = []  # (r,tx,ty,s[,fh,fv]) per page
        self.comp_transform_data: list[Tuple[float, float, float, float]] = []  # For comparison transform data
        
        # UI components
        self.mouse_handler: Optional[MouseEventHandler] = None
        self.page_control_frame: Optional[PageControlFrame] = None
        self.visualized_image: tk.StringVar = tk.StringVar(value="base")
        self._preferred_preview_scale: float = self._get_saved_preview_scale()
        self._loaded_pdf_source_path: Optional[str] = None
        self._preview_keyboard_rotation_delta: float = 0.0

        # Setup UI
        self._setup_ui()
        self._setup_drag_and_drop()
        self.canvas.bind("<Configure>", self._on_pdf_canvas_configure, add="+")

        # Main processing: refresh shared paths when the tab becomes visible.
        self.bind("<Visibility>", self._sync_shared_paths_from_settings)
        self.after_idle(self._sync_shared_paths_from_settings)

    def _sync_shared_paths_from_settings(self, event: Any = None) -> None:
        """Synchronize shared base/output paths from persisted settings.

        On idle (startup), if base points to an existing file, the PDF tab shows the
        parent folder locally only so startup does not auto-load a preview; shared
        settings are not rewritten (main tab keeps full PDF paths).

        Args:
            event: Tkinter visibility event (unused).
        """
        _ = event
        placeholder_base = message_manager.get_ui_message("U053")
        placeholder_output = message_manager.get_ui_message("U054")

        try:
            saved_base = UserSettingManager().get_setting("base_file_path")
            use_startup_normalization = event is None
            if (
                isinstance(saved_base, str)
                and saved_base
                and saved_base != placeholder_base
            ):
                saved_norm = normalize_host_path(saved_base)
                base_value_to_apply = saved_norm
                base_path_obj = Path(saved_norm)
                if use_startup_normalization and base_path_obj.exists() and base_path_obj.is_file():
                    # Main processing: avoid startup-time preview load; do not persist folder to settings.
                    base_value_to_apply = str(base_path_obj.parent)

                if self._base_file_path_entry.path_var.get() != base_value_to_apply:
                    self._base_file_path_entry.path_var.set(base_value_to_apply)
                    self.base_path.set(base_value_to_apply)

                loaded_norm = normalize_host_path(str(self._loaded_pdf_source_path or ""))
                if (
                    not use_startup_normalization
                    and base_path_obj.exists()
                    and base_path_obj.is_file()
                    and base_path_obj.suffix.lower() in MAIN_PDF_OPE_INPUT_EXTENSIONS
                    and str(base_path_obj) != loaded_norm
                ):
                    self._load_and_display_pdf(saved_norm)

            saved_output = UserSettingManager().get_setting("output_folder_path")
            if (
                isinstance(saved_output, str)
                and saved_output
                and saved_output != placeholder_output
            ):
                out_norm = normalize_host_path(saved_output)
                if self._output_folder_path_entry.path_var.get() != out_norm:
                    self._output_folder_path_entry.path_var.set(out_norm)
                    self.output_path.set(out_norm)
        except Exception as exc:
            logger.warning(f"Shared path sync failed in pdf tab: {exc}")

    def _get_saved_preview_scale(self) -> float:
        """Return the persisted PDF-operation preview scale.

        Returns:
            float: Saved scale factor, clamped to a positive value.
        """
        raw_scale = UserSettingManager().get_setting("pdf_operation_preview_scale", 1.0)
        try:
            resolved_scale = float(raw_scale)
        except (TypeError, ValueError):
            return 1.0
        if resolved_scale <= 0:
            return 1.0
        return max(0.05, min(10.0, resolved_scale))

    def _persist_preview_scale(self, scale_value: float) -> None:
        """Persist the current PDF-operation preview scale in memory.

        Args:
            scale_value: Scale factor to save.
        """
        resolved_scale = max(0.05, min(10.0, float(scale_value)))
        if abs(resolved_scale - self._preferred_preview_scale) < 1e-6:
            return
        self._preferred_preview_scale = resolved_scale
        UserSettingManager().update_setting("pdf_operation_preview_scale", resolved_scale)

    def _update_preferred_preview_scale_from_current_page(self) -> None:
        """Refresh the persisted preferred scale from the current page transform."""
        if not hasattr(self, "base_transform_data"):
            return
        if not (0 <= self.current_page_index < len(self.base_transform_data)):
            return
        _rotation, _tx, _ty, scale, _fh, _fv = as_transform6(self.base_transform_data[self.current_page_index])
        self._persist_preview_scale(scale)

    def _build_export_metadata(self) -> Dict[str, Any]:
        """Build export metadata for the currently loaded PDF pages.

        Returns:
            Dict[str, Any]: Metadata containing page width and page height when available.
        """
        export_metadata: Dict[str, Any] = {}
        if hasattr(self, "_conversion_dpi"):
            export_metadata["dpi"] = int(getattr(self, "_conversion_dpi", 0) or 0)

        if not getattr(self, "base_page_paths", None):
            return export_metadata

        first_page_path = self.base_page_paths[0]
        if not first_page_path.exists():
            return export_metadata

        with Image.open(first_page_path) as first_image:
            export_metadata["page_width"] = first_image.width
            export_metadata["page_height"] = first_image.height
        return export_metadata

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
        self._lang_select_combo = LanguageSelectCombo(self.frame_main0)
        self._lang_select_combo.grid(row=0, column=1, padx=5, pady=5, sticky="e")

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
            entry_setting_key="base_file_path",
            allow_files=True,
            allow_directories=False,
            allowed_file_extensions=MAIN_PDF_OPE_INPUT_EXTENSIONS,
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
            entry_setting_key="output_folder_path",
            allow_files=False,
            allow_directories=True,
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

    def build_keyboard_focus_chain(self) -> List[tk.Widget]:
        """Build column-major keyboard focus order for the PDF operation tab.

        Order: path entries then select buttons, header (language, theme), preview
        canvas, then ``PageControlFrame`` widgets when present.

        Returns:
            Interactive widgets participating in Tab / Shift+Tab navigation.
        """
        chain: List[tk.Widget] = []
        chain.append(self._base_file_path_entry.path_entry)
        chain.append(self._base_file_path_button.path_select_btn)
        chain.append(self._output_folder_path_entry.path_entry)
        chain.append(self._output_folder_path_button.path_select_btn)
        lang = getattr(self, "_lang_select_combo", None)
        if lang is not None:
            chain.append(lang)
        theme_btn = getattr(self, "_color_theme_change_btn", None)
        if theme_btn is not None and hasattr(theme_btn, "color_theme_change_btn"):
            chain.append(theme_btn.color_theme_change_btn)

        chain.append(self.canvas)
        if self.page_control_frame is not None:
            chain.extend(self.page_control_frame.iter_focus_widgets())
        return chain

    def _on_base_file_select(self) -> None:
        """Handle base file selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("base_file_path")
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U022",
            filetypes=main_pdf_ope_askopen_filetypes(),
            parent=self.winfo_toplevel(),
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
            self.output_path.set(folder_path)
            logger.debug(message_manager.get_log_message("L073", folder_path))

    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop functionality for PDF input and output folder."""
        # Try to register drop target; suppress non-fatal errors
        success = DragAndDropHandler.register_drop_target(
            self.canvas, self._on_drop, main_pdf_ope_drop_suffixes(), self._show_drop_feedback
        )
        DragAndDropHandler.register_drop_target(
            self._base_file_path_entry,
            self._on_drop,
            main_pdf_ope_drop_suffixes(),
            self._show_drop_feedback,
        )
        DragAndDropHandler.register_drop_target(
            self._output_folder_path_entry,
            self._on_drop_output_folder,
            feedback_callback=self._show_drop_feedback,
            allow_directories=True,
        )
        if success:
            # Log successful initialization of drag and drop
            logger.info(message_manager.get_log_message("L234"))

    def _on_drop_output_folder(self, folder_path: str) -> None:
        """Handle folder drop on the output path entry.

        Args:
            folder_path: Dropped folder path.
        """
        self._output_folder_path_entry.path_var.set(folder_path)
        self.output_path.set(folder_path)
        self._show_drop_feedback(f"Folder loaded: {folder_path}", True)

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
            old_guide = getattr(self, "_pdf_shortcut_guide_frame", None)
            if old_guide is not None:
                try:
                    old_guide.destroy()
                except Exception:
                    pass
            self._pdf_shortcut_guide_frame = None
            self._pdf_shortcut_guide_label = None
            try:
                self.canvas.delete("all")
            except Exception:
                pass
            self._original_page_width = 0
            self._original_page_height = 0

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
            self.current_pdf_converter = build_workspace_input_converter(
                file_path_info,
                program_mode=tool_settings.is_production_mode,
                name_flag="base",
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
            self._loaded_pdf_source_path = str(Path(file_path))

            self._refresh_operation_restriction_state()
            
            # Main processing: initialize page transforms with the persisted preferred scale.
            self.base_transform_data = [
                pack_transform6(0.0, 0.0, 0.0, self._preferred_preview_scale, 0, 0)
                for _ in range(self.page_count)
            ]
            
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

    def _commit_preview_keyboard_rotation(self) -> None:
        """Merge pending Ctrl+Shift preview rotation into stored transform data (then propagate if batch)."""
        delta = float(self._preview_keyboard_rotation_delta)
        if abs(delta) < 1e-9:
            return
        self._preview_keyboard_rotation_delta = 0.0
        if not hasattr(self, "base_transform_data") or self.page_count <= 0:
            return
        idx = self.current_page_index
        if not (0 <= idx < len(self.base_transform_data)):
            return
        r, x, y, s, fh, fv = as_transform6(self.base_transform_data[idx])
        self.base_transform_data[idx] = pack_transform6(r + delta, x, y, s, fh, fv)
        self._on_transform_update()

    def _clear_preview_keyboard_rotation_only(self) -> None:
        """Discard pending Ctrl+Shift preview rotation without writing it to transform data."""
        self._preview_keyboard_rotation_delta = 0.0

    def _on_pdf_preview_keyboard_rotate_right(self, event: Optional[tk.Event] = None) -> str:
        """Handle Ctrl+Shift+R: preview +90° (committed on click, page change, or other transform shortcuts)."""
        _ = event
        if self.mouse_handler is None:
            return "break"
        if not self._ensure_visual_adjustments_enabled():
            return "break"
        if not hasattr(self, "page_count") or self.page_count <= 0:
            return "break"
        self._preview_keyboard_rotation_delta += 90.0
        self._display_page(self.current_page_index)
        self.mouse_handler._show_notification(message_manager.get_message("M063"))
        return "break"

    def _on_pdf_preview_keyboard_rotate_left(self, event: Optional[tk.Event] = None) -> str:
        """Handle Ctrl+Shift+L: preview −90° (committed on click, page change, or other transform shortcuts)."""
        _ = event
        if self.mouse_handler is None:
            return "break"
        if not self._ensure_visual_adjustments_enabled():
            return "break"
        if not hasattr(self, "page_count") or self.page_count <= 0:
            return "break"
        self._preview_keyboard_rotation_delta -= 90.0
        self._display_page(self.current_page_index)
        self.mouse_handler._show_notification(message_manager.get_message("M064"))
        return "break"

    def _on_pdf_canvas_escape_preview(self, event: Optional[tk.Event] = None) -> str:
        """Discard pending Ctrl+Shift preview rotation when Escape is pressed on the canvas."""
        _ = event
        if abs(self._preview_keyboard_rotation_delta) < 1e-9:
            return "break"
        self._clear_preview_keyboard_rotation_only()
        self._display_page(self.current_page_index)
        return "break"

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

            if page_index != self.current_page_index:
                self._commit_preview_keyboard_rotation()

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
                rotation, translate_x, translate_y, scale, flip_h, flip_v = as_transform6(
                    self.base_transform_data[page_index]
                )
                rotation_draw = rotation
                if page_index == self.current_page_index:
                    rotation_draw = rotation + float(self._preview_keyboard_rotation_delta)

                # Apply transformations: mirror → rotate → scale (same order as main tab / export).
                if abs(rotation_draw) > 1e-9 or scale != 1.0 or flip_h or flip_v:
                    if flip_v:
                        pil_image = cast(Union[Image.Image, ImageFile], pil_image.transpose(Transpose.FLIP_TOP_BOTTOM))
                    if flip_h:
                        pil_image = cast(Union[Image.Image, ImageFile], pil_image.transpose(Transpose.FLIP_LEFT_RIGHT))
                    if abs(rotation_draw) > 1e-9:
                        rotated_image = pil_image.rotate(rotation_draw, resample=Resampling.BICUBIC, expand=True)
                        pil_image = cast(Union[Image.Image, ImageFile], rotated_image)
                    if scale != 1.0:
                        new_width = int(pil_image.width * scale)
                        new_height = int(pil_image.height * scale)
                        if new_width > 0 and new_height > 0:
                            resized_image = pil_image.resize((new_width, new_height), Resampling.LANCZOS)
                            pil_image = cast(Union[Image.Image, ImageFile], resized_image)
            
            # Convert to PhotoImage for display
            photo_image = ImageTk.PhotoImage(pil_image)
            self.photo_image = photo_image  # Keep reference to prevent garbage collection
            
            # Clear canvas (keep overlay items)
            self.canvas.delete("pdf_image")
            self.canvas.delete("export_outline")
            self.canvas.delete("pdf_reference_grid")
            
            # Display image with any translation offset
            if hasattr(self, 'base_transform_data') and self.base_transform_data:
                _, translate_x, translate_y, _, _, _ = as_transform6(self.base_transform_data[page_index])
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
            
            self._draw_export_outline()
            self._update_canvas_scrollregion()
            self._draw_pdf_canvas_reference_grid()
            self._draw_pdf_canvas_footer_guide()

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
                    r, tx, ty, s, _fh, _fv = as_transform6(self.base_transform_data[page_index])
                    r_panel = r + float(self._preview_keyboard_rotation_delta)
                    self.page_control_frame.update_transform_info(r_panel, tx, ty, s)

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

            # Prefer PDF embedded DPI (from PyPDF MediaBox vs largest image), then raster DPI.
            dpi_int = 0
            try:
                if hasattr(self, "file_path_info") and self.file_path_info:
                    raw_emb = (self.file_path_info.file_meta_info or {}).get("embedded_page_dpi")
                    if raw_emb is not None:
                        dpi_int = int(raw_emb)
            except (TypeError, ValueError):
                dpi_int = 0
            if dpi_int <= 0:
                dpi_val = getattr(self, "_conversion_dpi", None)
                try:
                    dpi_int = int(dpi_val) if dpi_val is not None else 0
                except (TypeError, ValueError):
                    dpi_int = 0
            if dpi_int <= 0:
                try:
                    dpi_int = int(UserSettingManager().get_setting("setted_dpi", 0) or 0)
                except (TypeError, ValueError):
                    dpi_int = 0
            lbl_dpi = message_manager.get_ui_message("U073")  # "Pixel density:" / "ピクセル密度:"
            dpi_text = f"{lbl_dpi} {dpi_int}dpi" if dpi_int > 0 else f"{lbl_dpi} -"

            # Main processing: estimate paper size from original pixel dimensions and DPI.
            lbl_paper = message_manager.get_ui_message("U074")  # "Paper size:" / "用紙サイズ:"
            paper_name = (
                self._estimate_paper_size(int(width), int(height), dpi_int)
                if (width and height and dpi_int > 0)
                else ""
            )

            # Compose footer text (saved-size prefix matches former export overlay, U172).
            footer_text = f"{size_text}  |  {dpi_text}"
            if paper_name:
                footer_text += f"  |  {lbl_paper} {paper_name}"
            saved_line = self._format_export_bounds_label_text()
            if saved_line:
                footer_text = f"{saved_line}  |  {footer_text}"
            self._footer_meta_label.configure(text=footer_text)
        except Exception:
            try:
                self._footer_meta_label.configure(text="-")
            except Exception:
                pass

    def _on_pdf_canvas_configure(self, event: tk.Event) -> None:
        """Redraw the PDF Operation reference grid when the canvas size changes.

        Args:
            event: Tkinter configure event (unused).
        """
        _ = event
        self._draw_pdf_canvas_reference_grid()
        self.schedule_pdf_canvas_footer_reposition()
        try:
            mh = getattr(self, "mouse_handler", None)
            if mh is not None:
                mh.refresh_overlay_positions()
        except Exception:
            pass

    def schedule_pdf_canvas_footer_reposition(self) -> None:
        """Defer PDF canvas footer layout until Tk geometry has settled."""

        def _run() -> None:
            self._reposition_pdf_canvas_footer_guide()

        try:
            self.after_idle(_run)
        except Exception:
            try:
                _run()
            except Exception:
                pass

    def _reposition_pdf_canvas_footer_guide(self) -> None:
        """Keep the PDF canvas shortcut guide aligned with the visible canvas bottom."""
        if not hasattr(self, "canvas"):
            return
        guide_frame = getattr(self, "_pdf_shortcut_guide_frame", None)
        guide_label = getattr(self, "_pdf_shortcut_guide_label", None)
        if guide_frame is None or guide_label is None:
            return
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            cw = int(self.canvas.winfo_width())
        except Exception:
            cw = 1
        canvas_width = max(cw, 1)
        left_inset = 2
        right_inset = 2
        guide_width = max(canvas_width - left_inset - right_inset, 120)
        guide_label.configure(wraplength=max(guide_width - 12, 80))
        try:
            guide_frame.update_idletasks()
        except Exception:
            pass
        guide_height = max(guide_frame.winfo_reqheight(), 28)
        guide_frame.place(
            x=left_inset,
            rely=1.0,
            y=-2,
            anchor="sw",
            width=guide_width,
            height=guide_height,
        )
        try:
            guide_frame.lift()
        except Exception:
            pass

    def _draw_pdf_canvas_footer_guide(self) -> None:
        """Draw the same shortcut/canvas hint strip as the Main tab (U150)."""
        if not hasattr(self, "canvas"):
            return
        mouse_handler = getattr(self, "mouse_handler", None)
        if mouse_handler is not None and hasattr(mouse_handler, "set_shortcut_help_visibility"):
            try:
                mouse_handler.set_shortcut_help_visibility(False)
            except Exception:
                pass
        current_theme = ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        guide_fg = str(frame_theme.get("fg", "#000000"))
        overlay_bg = str(self.canvas.cget("bg"))

        if getattr(self, "_pdf_shortcut_guide_frame", None) is None:
            self._pdf_shortcut_guide_frame = tk.Frame(
                self.canvas,
                relief=tk.FLAT,
                borderwidth=0,
                highlightthickness=0,
            )
        if getattr(self, "_pdf_shortcut_guide_label", None) is None:
            self._pdf_shortcut_guide_label = tk.Label(
                self._pdf_shortcut_guide_frame,
                anchor="w",
                justify="left",
                padx=5,
                pady=2,
                font=("Helvetica", 9),
            )
            self._pdf_shortcut_guide_label.pack(fill="both", expand=True)

        self._pdf_shortcut_guide_frame.configure(bg=overlay_bg)
        raw_u150 = message_manager.get_ui_message("U150")
        if "|||" in raw_u150 and "\n" in raw_u150:
            line1, line2 = raw_u150.split("\n", 1)
            left, right = line1.split("|||", 1)
            raw_u150 = f"{left.strip()}    {right.strip()}\n{line2}"
        self._pdf_shortcut_guide_label.configure(
            text=raw_u150,
            bg=overlay_bg,
            fg=guide_fg,
            pady=2,
        )
        self._reposition_pdf_canvas_footer_guide()
        try:
            self._pdf_shortcut_guide_frame.lift()
        except Exception:
            pass

    def _show_pdf_rotation_guide_dialog(self) -> None:
        """Show the custom rotation guide (same copy as the Main tab)."""
        messagebox.showinfo(
            title=message_manager.get_ui_message("U151"),
            message=message_manager.get_ui_message("U152"),
            parent=self.winfo_toplevel(),
        )

    def _on_pdf_reference_grid_toggle(self) -> None:
        """Persist reference-grid visibility and refresh the PDF canvas."""
        try:
            UserSettingManager().update_setting(
                "show_reference_grid",
                bool(self._show_pdf_reference_grid_var.get()),
            )
        except Exception:
            pass
        if getattr(self, "page_count", 0) > 0:
            self._display_page(self.current_page_index)

    def _get_pdf_canvas_reference_grid_color(self) -> str:
        """Return the dot-grid color aligned with the main preview tab.

        Returns:
            str: Hex color for reference dots.
        """
        current_theme = ColorThemeManager.get_instance().get_current_theme()
        canvas_theme = dict(current_theme.get("canvas", {}))
        frame_theme = dict(current_theme.get("Frame", {}))
        return str(
            canvas_theme.get("reference_grid", frame_theme.get("disabledforeground", "#bfc3cf"))
        )

    def _draw_pdf_canvas_reference_grid(self) -> None:
        """Draw a full-canvas intersection-dot grid like the Main tab preview."""
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("pdf_reference_grid")
        try:
            if not bool(self._show_pdf_reference_grid_var.get()):
                return
        except Exception:
            pass
        try:
            cw = max(int(self.canvas.winfo_width()), 1)
            ch = max(int(self.canvas.winfo_height()), 1)
        except Exception:
            return
        spacing = 24
        if cw < spacing or ch < spacing:
            return
        grid_color = self._get_pdf_canvas_reference_grid_color()
        x1, y1, x2, y2 = 0, 0, cw, ch
        start_x = int(math.floor(x1 / spacing) * spacing)
        start_y = int(math.floor(y1 / spacing) * spacing)
        for x in range(start_x, x2 + spacing, spacing):
            for y in range(start_y, y2 + spacing, spacing):
                self.canvas.create_line(
                    x,
                    y,
                    x + 1,
                    y,
                    fill=grid_color,
                    width=1,
                    capstyle=tk.ROUND,
                    tags=("pdf_reference_grid",),
                )
        # Stack: pdf_image (back) -> reference grid -> export outline -> window footer (front).
        try:
            self.canvas.tag_lower("pdf_image")
        except Exception:
            pass
        if self.canvas.find_withtag("pdf_image"):
            try:
                self.canvas.tag_raise("pdf_reference_grid", "pdf_image")
            except Exception:
                pass
        if self.canvas.find_withtag("export_outline"):
            try:
                self.canvas.tag_raise("export_outline", "pdf_reference_grid")
            except Exception:
                pass

    @staticmethod
    def _merge_canvas_bboxes(
        first_bbox: Optional[tuple[int, int, int, int]],
        second_bbox: Optional[tuple[int, int, int, int]],
    ) -> Optional[tuple[int, int, int, int]]:
        """Merge two canvas bounding boxes into one rectangle.

        Args:
            first_bbox: First bounding box in canvas coordinates.
            second_bbox: Second bounding box in canvas coordinates.

        Returns:
            Optional[tuple[int, int, int, int]]: Bounding box covering both inputs.
        """
        if first_bbox is None:
            return second_bbox
        if second_bbox is None:
            return first_bbox
        return (
            min(int(first_bbox[0]), int(second_bbox[0])),
            min(int(first_bbox[1]), int(second_bbox[1])),
            max(int(first_bbox[2]), int(second_bbox[2])),
            max(int(first_bbox[3]), int(second_bbox[3])),
        )

    def _format_export_bounds_label_text(self) -> str:
        """Build the saved-size line shown beside the footer (same data as former canvas label).

        Returns:
            Localized text, or empty string when no page dimensions are available.
        """
        width = int(getattr(self, "_original_page_width", 0) or 0)
        height = int(getattr(self, "_original_page_height", 0) or 0)
        if width <= 1 or height <= 1:
            return ""
        dpi_value = int(getattr(self, "_conversion_dpi", 0) or 0)
        paper_name = (
            self._estimate_paper_size(width, height, dpi_value)
            if dpi_value > 0
            else ""
        )
        label_text = f"{message_manager.get_ui_message('U172')}: {width} x {height} px"
        if dpi_value > 0:
            label_text += f" / {dpi_value} dpi"
        if paper_name:
            label_text += f" / {paper_name}"
        return label_text

    def _draw_export_outline(self) -> None:
        """Draw a dashed page outline that matches the saved PDF bounds."""
        self.canvas.delete("export_outline")
        width = int(getattr(self, "_original_page_width", 0) or 0)
        height = int(getattr(self, "_original_page_height", 0) or 0)
        if width <= 1 or height <= 1:
            return

        current_theme = ColorThemeManager.get_instance().get_current_theme()
        canvas_theme = dict(current_theme.get("canvas", {}))
        frame_theme = dict(current_theme.get("Frame", {}))
        outline_color = str(
            canvas_theme.get(
                "highlightbackground",
                frame_theme.get("disabledforeground", "#9ca4bc"),
            )
        )
        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            outline=outline_color,
            width=1,
            dash=(6, 4),
            tags=("export_outline",),
        )
        try:
            self.canvas.tag_raise("export_outline")
        except Exception:
            pass

    def _update_canvas_scrollregion(self) -> None:
        """Update the scroll region to include both the page image and save outline."""
        combined_bbox = self._merge_canvas_bboxes(
            cast(Optional[tuple[int, int, int, int]], self.canvas.bbox("pdf_image")),
            cast(Optional[tuple[int, int, int, int]], self.canvas.bbox("export_outline")),
        )
        if combined_bbox is not None:
            x0, y0, x1, y1 = (
                int(combined_bbox[0]),
                int(combined_bbox[1]),
                int(combined_bbox[2]),
                int(combined_bbox[3]),
            )
            cw = max(int(self.canvas.winfo_width()), 1)
            ch = max(int(self.canvas.winfo_height()), 1)
            self.canvas.config(
                scrollregion=(
                    min(0, x0),
                    min(0, y0),
                    max(x1, cw),
                    max(y1, ch),
                )
            )
            return
        try:
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
        except Exception:
            self.canvas.config(
                scrollregion=(0, 0, self.canvas.winfo_width(), self.canvas.winfo_height())
            )

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
            self._commit_preview_keyboard_rotation()
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
            self._commit_preview_keyboard_rotation()
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
            self._commit_preview_keyboard_rotation()
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
            commit_keyboard_preview_rotation=self._commit_preview_keyboard_rotation,
            clear_keyboard_preview_rotation=self._clear_preview_keyboard_rotation_only,
            on_transform_commit_no_propagate=self._on_transform_update_skip_batch_propagate,
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
        def _pdf_canvas_button1(event: tk.Event) -> None:
            self._commit_preview_keyboard_rotation()
            self.canvas.focus_set()
            if self.mouse_handler is not None:
                self.mouse_handler.on_mouse_down(event)

        self.canvas.bind("<Button-1>", _pdf_canvas_button1)
        self.canvas.bind("<B1-Motion>", lambda e: self.mouse_handler.on_mouse_drag(e) if self.mouse_handler else None)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.mouse_handler.on_mouse_up(e) if self.mouse_handler else None)
        self.canvas.bind("<Button-3>", lambda e: self.mouse_handler.on_right_click(e) if self.mouse_handler and hasattr(self.mouse_handler, 'on_right_click') else None)
        
        # MouseWheel events are handled in PDFOperationApp class
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)  # Linux scroll down

        self.canvas.bind("<Escape>", self._on_pdf_canvas_escape_preview)

        # Canvas rebuild drops bind_all state; clear flag so reactivation can re-register.
        self._pdf_global_shortcuts_active = False
        self._unbind_pdf_global_shortcuts()
        self._reactivate_pdf_shortcuts_if_tab_selected()
        
        # Log event binding
        logger.info(message_manager.get_log_message("L302"))

    def _unbind_pdf_global_shortcuts(self) -> None:
        """Remove PDF-tab bind_all handlers (safe when tab is hidden or before rebinding)."""
        for seq in self._GLOBAL_SHORTCUT_SEQUENCES:
            try:
                self.unbind_all(seq)
            except Exception:
                pass

    def _bind_pdf_global_shortcuts(self) -> None:
        """Register bind_all handlers for PDF Operation tab (call only when this tab is selected)."""
        self._unbind_pdf_global_shortcuts()

        # Main processing: rotation / flip / reset shortcuts are handled by MouseEventHandler.
        self.bind_all("<Control-r>", self._on_shortcut_rotate_right)
        self.bind_all("<Control-R>", self._on_shortcut_rotate_right)
        self.bind_all("<Control-Shift-r>", self._on_shortcut_rotate_fast_right)
        self.bind_all("<Control-Shift-R>", self._on_shortcut_rotate_fast_right)
        self.bind_all("<Control-l>", self._on_shortcut_rotate_left)
        self.bind_all("<Control-L>", self._on_shortcut_rotate_left)
        self.bind_all("<Control-Shift-l>", self._on_shortcut_rotate_fast_left)
        self.bind_all("<Control-Shift-L>", self._on_shortcut_rotate_fast_left)
        self.bind_all("<Control-Alt-r>", self._on_shortcut_rotate_sheet_right)
        self.bind_all("<Control-Alt-R>", self._on_shortcut_rotate_sheet_right)
        self.bind_all("<Control-Alt-l>", self._on_shortcut_rotate_sheet_left)
        self.bind_all("<Control-Alt-L>", self._on_shortcut_rotate_sheet_left)
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

    def _activate_pdf_global_shortcuts(self) -> None:
        """Bind PDF global shortcuts (idempotent)."""
        if self._pdf_global_shortcuts_active:
            return
        self._bind_pdf_global_shortcuts()
        self._pdf_global_shortcuts_active = True

    def _deactivate_pdf_global_shortcuts(self) -> None:
        """Unbind PDF global shortcuts and hide the canvas shortcut overlay."""
        if not self._pdf_global_shortcuts_active:
            return
        self._unbind_pdf_global_shortcuts()
        self._pdf_global_shortcuts_active = False
        mh = getattr(self, "mouse_handler", None)
        if mh is not None and hasattr(mh, "set_shortcut_help_visibility"):
            try:
                mh.set_shortcut_help_visibility(False)
            except Exception:
                pass

    def set_pdf_tab_shortcuts_active(self, active: bool) -> None:
        """Enable or disable PDF Operation global shortcuts from the notebook.

        Args:
            active: True when this tab is the selected notebook page.
        """
        if active:
            self._activate_pdf_global_shortcuts()
        else:
            self._deactivate_pdf_global_shortcuts()

    def _reactivate_pdf_shortcuts_if_tab_selected(self) -> None:
        """After canvas rebuild, re-bind globals only if the PDF tab is currently visible."""
        try:
            nb = self.master.master
            cur = nb.index("current")
            mine = nb.index(self.master)
            if cur == mine:
                self._activate_pdf_global_shortcuts()
        except Exception:
            pass

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

    def _on_shortcut_rotate_fast_right(self, event: tk.Event) -> str:
        """Handle Ctrl+Shift+R shortcut (preview rotation; see _on_pdf_preview_keyboard_rotate_right)."""
        return self._on_pdf_preview_keyboard_rotate_right(event)

    def _on_shortcut_rotate_fast_left(self, event: tk.Event) -> str:
        """Handle Ctrl+Shift+L shortcut (preview rotation; see _on_pdf_preview_keyboard_rotate_left)."""
        return self._on_pdf_preview_keyboard_rotate_left(event)

    def _on_shortcut_rotate_sheet_right(self, event: tk.Event) -> str:
        """Handle Ctrl+Alt+R shortcut (rotate every page sheet)."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_rotate_sheet_right(event) or "break")

    def _on_shortcut_rotate_sheet_left(self, event: tk.Event) -> str:
        """Handle Ctrl+Alt+L shortcut (rotate every page sheet)."""
        if self.mouse_handler is None:
            return "break"
        return cast(str, self.mouse_handler._on_rotate_sheet_left(event) or "break")

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

    def _on_transform_update_skip_batch_propagate(self) -> None:
        """Redraw after Ctrl+Alt sheet rotation without copying the current page to all."""
        if not hasattr(self, "page_count") or self.page_count <= 0:
            return
        self._update_preferred_preview_scale_from_current_page()
        self._display_page(self.current_page_index)

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
        if (
            self.page_control_frame
            and hasattr(self.page_control_frame, "batch_edit_var")
            and self.page_control_frame.batch_edit_var.get()
            and hasattr(self, "base_transform_data")
        ):
            current_transform = self.base_transform_data[self.current_page_index]
            for i in range(len(self.base_transform_data)):
                if i != self.current_page_index:
                    self.base_transform_data[i] = current_transform

        self._update_preferred_preview_scale_from_current_page()
        self._display_page(self.current_page_index)
    
    def _on_transform_value_input(self, rotation: float, tx: float,
                                   ty: float, scale: float,
                                   changed_fields: Optional[set[str]] = None) -> None:
        """Apply user-entered transform values to the current page.

        Called from PageControlFrame when the user presses Enter in one of the
        transform entry fields.

        Args:
            rotation: Rotation angle in degrees.
            tx: X translation offset.
            ty: Y translation offset.
            scale: Scale factor.
            changed_fields: Explicitly confirmed entry field names.
        """
        _ = changed_fields
        if not hasattr(self, 'base_transform_data'):
            return
        if self.current_page_index >= len(self.base_transform_data):
            return

        # Main processing: update transform data and refresh display.
        _r, _x, _y, _s, fh, fv = as_transform6(self.base_transform_data[self.current_page_index])
        self.base_transform_data[self.current_page_index] = pack_transform6(rotation, tx, ty, scale, fh, fv)
        self._on_transform_update()

    def _reset_transform(self) -> None:
        """Reset transformation for the current page."""
        if not self._ensure_visual_adjustments_enabled():
            return

        # Reset transform data for the current page
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Reset to default transform values (0 rotation, 0,0 position, 1.0 scale)
            _r, _x, _y, s, _fh, _fv = as_transform6(self.base_transform_data[self.current_page_index])
            self.base_transform_data[self.current_page_index] = pack_transform6(0.0, 0.0, 0.0, s, 0, 0)
            self._on_transform_update()
    
    def _zoom_in(self) -> None:
        """Zoom in on the current page."""
        if not self._ensure_visual_adjustments_enabled():
            return

        # Apply zoom by scaling
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Get current transform data
            rotation, tx, ty, scale, fh, fv = as_transform6(self.base_transform_data[self.current_page_index])
            scale *= 1.05  # Smaller increment for smoother zooming
            self.base_transform_data[self.current_page_index] = pack_transform6(rotation, tx, ty, scale, fh, fv)
            self._on_transform_update()
    
    def _zoom_out(self) -> None:
        """Zoom out on the current page."""
        if not self._ensure_visual_adjustments_enabled():
            return

        # Apply zoom by scaling
        if hasattr(self, 'base_transform_data') and self.current_page_index < len(self.base_transform_data):
            # Get current transform data
            rotation, tx, ty, scale, fh, fv = as_transform6(self.base_transform_data[self.current_page_index])
            scale *= 0.95  # Smaller decrement for smoother zooming
            self.base_transform_data[self.current_page_index] = pack_transform6(rotation, tx, ty, scale, fh, fv)
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
                on_rotation_guide=self._show_pdf_rotation_guide_dialog,
                reference_grid_var=self._show_pdf_reference_grid_var,
                on_reference_grid_toggle=self._on_pdf_reference_grid_toggle,
            )
            self.page_control_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 4), pady=0)

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
        
        suffix = Path(file_path).suffix.lower()
        if suffix in MAIN_PDF_OPE_INPUT_EXTENSIONS:
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
        self.base_transform_data.insert(
            insert_position, pack_transform6(0.0, 0.0, 0.0, self._preferred_preview_scale, 0, 0)
        )

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

    def _commit_pending_transform_entries(self) -> None:
        """Apply any pending transform-entry text before exporting."""
        if self.page_control_frame is None:
            return
        commit_method = getattr(self.page_control_frame, "commit_transform_entries", None)
        if callable(commit_method):
            commit_method()

    def _build_export_transform_data(self) -> list[Tuple[float, float, float, float]]:
        """Build export transforms for PDF-operation saving.

        Returns:
            list[Tuple[float, float, float, float]]: Export transforms with preview
            zoom removed so saved pages always use ``1.0`` scale.
        """
        export_transforms: list[Tuple[float, ...]] = []
        for raw in self.base_transform_data:
            rotation, translate_x, translate_y, _scale, fh, fv = as_transform6(raw)
            export_transforms.append(pack_transform6(rotation, translate_x, translate_y, 1.0, fh, fv))
        return export_transforms

    def _on_complete_edit(self) -> None:
        """Complete the editing process and export the PDF."""
        if self._copy_protected:
            return

        if not hasattr(self, 'page_count') or self.page_count == 0:
            messagebox.showinfo(message_manager.get_ui_message("U056"), message_manager.get_ui_message("U057"))
            return

        # Main processing: make sure unsaved text in the transform fields is reflected in the export.
        self._commit_pending_transform_entries()
        self._commit_preview_keyboard_rotation()

        # Get output folder path
        output_folder = self._output_folder_path_entry.path_var.get().strip()
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
            self.output_path.set(output_folder)
        else:
            self.output_path.set(output_folder)

        UserSettingManager().update_setting("output_folder_path", output_folder)
            
        # Get the base file name for the new PDF
        source_pdf_path = str(self._loaded_pdf_source_path or self.base_path.get()).strip()
        source_pdf_name = Path(source_pdf_path).name if source_pdf_path else "edited_output.pdf"
        if not source_pdf_name.lower().endswith(".pdf"):
            source_pdf_name = f"{Path(source_pdf_name).stem}.pdf"

        source_stem = Path(source_pdf_name).stem
        output_path = create_unique_file_path(
            Path(output_folder), f"edited_{source_stem}", ".pdf"
        )
        output_filename = output_path.name
        output_file = str(output_path)

        try:
            # Main processing: export the current transformed PDF pages into a new PDF file.
            export_handler = PDFExportHandler(
                base_pages=[str(path) for path in self.base_page_paths],
                comp_pages=[],
                base_transform_data=self._build_export_transform_data(),
                comp_transform_data=[],
                output_folder=output_folder,
                pdf_metadata=self._build_export_metadata(),
                color_processing_mode="original",
                show_base_layer=True,
                show_comp_layer=False,
            )
            export_handler.export_to_pdf(output_filename, self)
            messagebox.showinfo(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message("U167").format(output_file)
            )
            logger.info(message_manager.get_log_message("L305", output_file))
        except Exception as e:
            logger.error(message_manager.get_log_message("L124", str(e)))
            messagebox.showerror(
                message_manager.get_ui_message("U056"),
                message_manager.get_ui_message("U047").format(str(e))
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

            # Apply theme to canvas (match Main tab: Notebook tab_bg fallback + canvas overrides)
            if hasattr(self, "canvas"):
                notebook_settings = theme_data.get("Notebook", {})
                canvas_theme = dict(theme_data.get("canvas", {}))
                canvas_background = notebook_settings.get(
                    "tab_bg", notebook_settings.get("bg", frame_bg)
                )
                self._config_widget(
                    {
                        "background": canvas_theme.get("background", canvas_background),
                        "highlightbackground": canvas_theme.get(
                            "highlightbackground", frame_bg
                        ),
                        "highlightcolor": canvas_theme.get(
                            "highlightcolor", frame_settings.get("fg", "#000000")
                        ),
                    }
                )
            self._draw_pdf_canvas_reference_grid()
            self._draw_pdf_canvas_footer_guide()

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
