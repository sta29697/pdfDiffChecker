from __future__ import annotations

import os
import stat
from logging import getLogger
from typing import Dict, Any, List, Optional

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from configurations.message_manager import get_message_manager
from configurations.user_setting_manager import UserSettingManager
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import WidgetsTracker

from widgets.base_label_class import BaseLabelClass
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.color_theme_change_button import ColorThemeChangeButton
from widgets.language_select_combobox import LanguageSelectCombo
from widgets.base_path_entry import BasePathEntry
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_entry import BaseEntry
from widgets.convert_image_button import ConvertImageButton
from controllers.drag_and_drop_file import DragAndDropHandler
from themes.coloring_theme_interface import ColoringThemeIF
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog

logger = getLogger(__name__)
message_manager = get_message_manager()

# Supported image extensions for file dialogs
_IMAGE_EXTENSIONS = (
    "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.ico *.tga"
)
_DROP_EXTENSIONS: List[str] = [
    ".png", ".jpg", ".jpeg", ".bmp", ".gif",
    ".tif", ".tiff", ".webp", ".ico", ".tga",
    ".pdf", ".svg",
]

# Extension choices for the conversion dropdown
_EXT_CHOICES: List[str] = [
    "png", "jpg", "bmp", "gif", "tif", "webp", "ico", "tga", "pdf",
]

# Pillow save format mapping for extension conversion.
_PILLOW_SAVE_FORMATS: Dict[str, str] = {
    "jpg": "JPEG",
    "png": "PNG",
    "bmp": "BMP",
    "gif": "GIF",
    "tif": "TIFF",
    "webp": "WEBP",
    "ico": "ICO",
    "tga": "TGA",
    "pdf": "PDF",
}

# DPI preset values
_DPI_CHOICES: List[str] = ["72", "96", "150", "300", "600"]

# Paper size base definitions: name -> (short_mm, long_mm)
_PAPER_SIZE_BASE: Dict[str, tuple[float, float]] = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "B4": (250.0, 353.0),
    "B5": (176.0, 250.0),
    "Letter": (216.0, 279.0),
    "Legal": (216.0, 356.0),
}


def _build_paper_size_entries() -> Dict[str, tuple[float, float]]:
    """Build paper size dropdown entries with portrait/landscape orientation.

    Returns:
        Dict mapping display name -> (width_mm, height_mm).
    """
    portrait = message_manager.get_ui_message("U097")
    landscape = message_manager.get_ui_message("U098")
    result: Dict[str, tuple[float, float]] = {}
    for name, (short, long) in _PAPER_SIZE_BASE.items():
        # Portrait: short x long (e.g. 210x297)
        p_label = f"{name} ({portrait}: {int(short)}\u00d7{int(long)}mm)"
        result[p_label] = (short, long)
        # Landscape: long x short (e.g. 297x210)
        l_label = f"{name} ({landscape}: {int(long)}\u00d7{int(short)}mm)"
        result[l_label] = (long, short)
    return result


class ImageOperationApp(ttk.Frame, ColoringThemeIF):
    """Image operation tab for file extension and size conversions (U006).

    Layout:
        frame_main0  - Language combo + Theme change button
        frame_main1  - Input file path + Output folder path
        frame_ext    - Extension conversion block
        frame_size   - Size conversion block
        frame_status - Status bar
    """

    def __init__(self, master: Optional[tk.Misc] = None, **kwargs: Any) -> None:
        """Initialize the image operation tab.

        Args:
            master (Optional[tk.Misc]): Parent widget.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(master, **kwargs)
        WidgetsTracker().add_widgets(self)
        self.base_widgets = BaseTabWidgets(self)

        # Configure frame to expand
        self.pack(fill="both", expand=True)
        self.grid_columnconfigure(0, weight=1)
        # Extension and size blocks share remaining vertical space
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Initialize status and path variables
        self.status_var: tk.StringVar = tk.StringVar(value="")
        self.after_id: Optional[str] = None
        self._size_syncing = False
        self._copy_protected_pdf_detected = False
        self._input_readonly_detected = False
        self._multi_frame_detected = False
        self._original_dpi: Optional[float] = None
        self._original_dpi_missing = False
        self._paper_size_priority_enabled = False
        self._last_input_dialog_filter = "image"

        # Path placeholders (same message codes as PDF tab)
        self.base_path = tk.StringVar()
        self.base_path.set(message_manager.get_ui_message("U053"))
        self.output_path = tk.StringVar()
        self.output_path.set(message_manager.get_ui_message("U054"))

        # Build all UI sections
        self._build_frame_main0()
        self._build_frame_main1()
        self._build_frame_ext()
        self._build_frame_size()
        self._build_frame_status()

        # Main processing: apply current theme once more after all child widgets exist.
        # This avoids startup-time default colors on plain tk widgets in this tab.
        self._apply_current_theme_after_build()

        # Setup drag and drop for path entries
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
            use_startup_normalization = event is None
            if (
                isinstance(saved_base, str)
                and saved_base
                and saved_base != placeholder_base
            ):
                base_value_to_apply = saved_base
                saved_base_path = Path(saved_base)
                if use_startup_normalization and saved_base_path.exists() and saved_base_path.is_file():
                    # Main processing: avoid startup-time preview load by restoring only folder path.
                    base_value_to_apply = str(saved_base_path.parent)
                    UserSettingManager().update_setting("base_file_path", base_value_to_apply)

                if self._base_file_path_entry.path_var.get() != base_value_to_apply:
                    self._base_file_path_entry.path_var.set(base_value_to_apply)
                    self.base_path.set(base_value_to_apply)

                if not use_startup_normalization and saved_base_path.exists() and saved_base_path.is_file():
                    self._update_file_info(saved_base)

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
            logger.warning(f"Shared path sync failed in image tab: {exc}")

    def _apply_current_theme_after_build(self) -> None:
        """Apply the current theme to this tab after widget construction.

        This method is intentionally called at the end of ``__init__`` because
        ``WidgetsTracker().add_widgets(self)`` happens before child widgets are
        created. Without this pass, plain tk widgets in this tab can keep the
        default system background until the next theme change event.

        Main processing: re-publish the current theme event so both plain tk
        widgets and ttk styles are refreshed using the latest theme snapshot.
        This avoids applying stale colors captured at startup.
        """
        try:
            ColorThemeManager.apply_color_theme_all_widgets()
            self.after_idle(ColorThemeManager.apply_color_theme_all_widgets)
        except Exception:
            return

    # ------------------------------------------------------------------
    # frame_main0: Language combo + Theme change button
    # ------------------------------------------------------------------
    def _build_frame_main0(self) -> None:
        """Build the top toolbar frame with language combo and theme button."""
        self.frame_main0 = tk.Frame(self)
        self.frame_main0.grid(row=0, column=0, sticky="we", ipady=2)
        self.frame_main0.grid_columnconfigure(0, weight=1)

        # Language combo (left-aligned via weight)
        lang_combo = LanguageSelectCombo(self.frame_main0)
        lang_combo.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        # Theme change button (right-aligned)
        self._color_theme_change_btn = ColorThemeChangeButton(
            fr=self.frame_main0,
            color_theme_change_btn_status=False,
            text=message_manager.get_ui_message("U025"),
        )
        self._color_theme_change_btn.grid(
            row=0, column=2, padx=5, pady=5, sticky="e"
        )

    # ------------------------------------------------------------------
    # frame_main1: Input file path + Output folder path
    # ------------------------------------------------------------------
    def _build_frame_main1(self) -> None:
        """Build the path input frame with file and folder entries."""
        self.frame_main1 = tk.Frame(self)
        self.frame_main1.grid(row=1, column=0, sticky="we", ipady=2)
        self.frame_main1.grid_columnconfigure(1, weight=1)

        # Base file path label
        self._base_file_path_label = BaseLabelClass(
            fr=self.frame_main1,
            color_key="base_file_path_label",
            text=message_manager.get_ui_message("U018"),
        )
        self._base_file_path_label.grid(column=0, row=0, padx=5, pady=8, sticky="w")

        # Base file path entry (shared key with PDF tab)
        self._base_file_path_entry = BasePathEntry(
            fr=self.frame_main1,
            color_key="base_file_path_entry",
            entry_setting_key="base_file_path",
        )
        self._base_file_path_entry.grid(column=1, row=0, padx=5, pady=8, sticky="ew")
        # Main processing: set placeholder on startup
        self._base_file_path_entry.path_var.set(self.base_path.get())

        # Base file path select button
        self._base_file_path_button = BasePathSelectButton(
            fr=self.frame_main1,
            color_key="base_file_path_button",
            entry_setting_key="base_file_path",
            share_path_entry=self._base_file_path_entry,
            text=message_manager.get_ui_message("U019"),
            command=self._on_base_file_select,
        )
        self._base_file_path_button.grid(column=2, row=0, padx=5, pady=8, sticky="e")

        # Output folder path label
        self._output_folder_path_label = BaseLabelClass(
            fr=self.frame_main1,
            color_key="output_folder_path_label",
            text=message_manager.get_ui_message("U021"),
        )
        self._output_folder_path_label.grid(column=0, row=1, padx=5, pady=8, sticky="w")

        # Output folder path entry (shared key with PDF tab)
        self._output_folder_path_entry = BasePathEntry(
            fr=self.frame_main1,
            color_key="output_folder_path_entry",
            entry_setting_key="output_folder_path",
        )
        self._output_folder_path_entry.grid(column=1, row=1, padx=5, pady=8, sticky="ew")
        # Main processing: set placeholder on startup
        self._output_folder_path_entry.path_var.set(self.output_path.get())

        # Output folder path select button
        self._output_folder_path_button = BasePathSelectButton(
            fr=self.frame_main1,
            color_key="output_folder_path_button",
            entry_setting_key="output_folder_path",
            share_path_entry=self._output_folder_path_entry,
            text=message_manager.get_ui_message("U019"),
            command=self._on_output_folder_select,
        )
        self._output_folder_path_button.grid(column=2, row=1, padx=5, pady=8, sticky="e")

    # ------------------------------------------------------------------
    # frame_ext: Extension conversion block
    # ------------------------------------------------------------------
    def _build_frame_ext(self) -> None:
        """Build the extension conversion block.

        Layout:
            Section header label
            Input filename.ext  =>  Output filename.[dropdown]
            Meta info display
            Warning label (hidden by default)
            Execute button
        """
        self.frame_ext = tk.LabelFrame(
            self,
            text=f"  {message_manager.get_ui_message('U077')}  ",
            font=("", 11, "bold"),
            padx=8, pady=8,
        )
        self.frame_ext.grid(row=2, column=0, sticky="nsew", padx=8, pady=(8, 4))
        self.frame_ext.grid_columnconfigure(1, weight=1)

        # --- Row 0: Conversion expression ---
        # Input filename (read-only label, updated when file is selected)
        self._ext_input_name_var = tk.StringVar(
            value="-"
        )
        self._ext_input_label = tk.Label(
            self.frame_ext, textvariable=self._ext_input_name_var,
            anchor="w",
        )
        self._ext_input_label.grid(row=0, column=0, padx=5, pady=4, sticky="w")

        # Arrow label (bold triangular arrow for clean, modern visual)
        self._ext_arrow_label = tk.Label(self.frame_ext, text="\u27a4", font=("", 18, "bold"))
        self._ext_arrow_label.grid(row=0, column=1, padx=5, pady=4)

        # Output filename base (read-only) + extension dropdown
        self._ext_output_frame = tk.Frame(self.frame_ext)
        self._ext_output_frame.grid(row=0, column=2, padx=5, pady=4, sticky="w")

        self._ext_output_name_var = tk.StringVar(
            value="-."
        )
        self._ext_output_name_label = tk.Label(
            self._ext_output_frame, textvariable=self._ext_output_name_var,
            anchor="w",
        )
        self._ext_output_name_label.pack(side="left")

        # Extension dropdown
        self._ext_target_var = tk.StringVar(value="png")
        self._ext_combo = ttk.Combobox(
            self._ext_output_frame,
            textvariable=self._ext_target_var,
            values=_EXT_CHOICES,
            state="readonly",
            width=8,
        )
        self._ext_combo.pack(side="left", padx=(2, 0))
        self._ext_combo.bind("<<ComboboxSelected>>", self._refresh_ext_warning_label)

        # --- Row 1: Meta info display ---
        self._ext_meta_var = tk.StringVar(value="-")
        # Meta info inside a bordered sub-frame for clear visual grouping
        self._ext_meta_frame = tk.Frame(
            self.frame_ext, relief="groove", bd=1, padx=4, pady=2,
        )
        self._ext_meta_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=2, sticky="we")
        self._ext_meta_label = tk.Label(
            self._ext_meta_frame, textvariable=self._ext_meta_var,
            anchor="w", font=("", 8),
        )
        self._ext_meta_label.pack(fill="x")

        # --- Row 2: Warning label (hidden by default) ---
        self._ext_warning_var = tk.StringVar(value="")
        self._ext_warning_label = tk.Label(
            self.frame_ext, textvariable=self._ext_warning_var,
            anchor="w", font=("", 10, "bold"), justify="left", wraplength=700,
        )
        self._ext_warning_label.grid(row=2, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        self._ext_warning_label.grid_remove()  # Hidden by default

        # --- Row 3: Execute button (right-aligned) ---
        self._ext_convert_btn = ConvertImageButton(
            fr=self.frame_ext,
            color_key="ext_convert_button",
            text=message_manager.get_ui_message("U077"),
            command=self._on_ext_convert,
        )
        self._ext_convert_btn.grid(row=3, column=2, padx=5, pady=(8, 4), sticky="e")

    # ------------------------------------------------------------------
    # frame_size: Size conversion block
    # ------------------------------------------------------------------
    def _build_frame_size(self) -> None:
        """Build the size conversion block.

        Layout:
            Section header label
            Input filename.ext  =>  Output filename.ext
            Current size  ->  Target width x height
            DPI dropdown + Paper size dropdown
            Aspect ratio checkbox
            Warning label (hidden by default)
            Execute button
        """
        self.frame_size = tk.LabelFrame(
            self,
            text=f"  {message_manager.get_ui_message('U090')}  ",
            font=("", 11, "bold"),
            padx=8, pady=8,
        )
        self.frame_size.grid(row=3, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.frame_size.grid_columnconfigure(1, weight=1)

        # --- Row 0: Conversion expression ---
        self._size_input_name_var = tk.StringVar(value="-")
        self._size_input_label = tk.Label(
            self.frame_size, textvariable=self._size_input_name_var,
            anchor="w",
        )
        self._size_input_label.grid(row=0, column=0, padx=5, pady=4, sticky="w")

        self._size_arrow_label = tk.Label(self.frame_size, text="\u27a4", font=("", 18, "bold"))
        self._size_arrow_label.grid(row=0, column=1, padx=5, pady=4)

        self._size_output_name_var = tk.StringVar(value="-")
        self._size_output_label = tk.Label(
            self.frame_size, textvariable=self._size_output_name_var,
            anchor="w",
        )
        self._size_output_label.grid(row=0, column=2, padx=5, pady=4, sticky="w")

        # --- Row 1: Current size -> Target size ---
        self._size_row = tk.Frame(self.frame_size)
        self._size_row.grid(row=1, column=0, columnspan=3, padx=5, pady=4, sticky="w")

        self._size_current_var = tk.StringVar(value="- px \u00d7 - px")
        self._size_current_label = tk.Label(
            self._size_row, textvariable=self._size_current_var, anchor="w",
        )
        self._size_current_label.pack(side="left", padx=(0, 10))
        self._size_row_arrow = tk.Label(self._size_row, text="\u2192", font=("", 16, "bold"))
        self._size_row_arrow.pack(side="left", padx=5)

        # Width entry
        self._width_label = BaseLabelClass(
            fr=self._size_row, color_key="width_size_set_label",
            text=message_manager.get_ui_message("U012"),
        )
        # Make the field title visually stronger (all themes).
        self._width_label.configure(font=("", 11, "bold"))
        self._width_label.pack(side="left", padx=(10, 2))

        self.width_var = tk.StringVar()
        self._width_entry = BaseEntry(
            master=self._size_row, color_key="entry_normal",
            textvariable=self.width_var, width=8,
        )
        # Match entry font size to the title size.
        self._width_entry.configure(font=("", 11))
        self._width_entry.pack(side="left", padx=2)

        # Height entry
        self._height_label = BaseLabelClass(
            fr=self._size_row, color_key="height_size_set_label",
            text=message_manager.get_ui_message("U013"),
        )
        # Make the field title visually stronger (all themes).
        self._height_label.configure(font=("", 11, "bold"))
        self._height_label.pack(side="left", padx=(10, 2))

        self.height_var = tk.StringVar()
        self._height_entry = BaseEntry(
            master=self._size_row, color_key="entry_normal",
            textvariable=self.height_var, width=8,
        )
        # Match entry font size to the title size.
        self._height_entry.configure(font=("", 11))
        self._height_entry.pack(side="left", padx=2)

        # --- Row 2: DPI + Paper size + Aspect ratio ---
        self._options_row = tk.Frame(self.frame_size)
        self._options_row.grid(row=2, column=0, columnspan=3, padx=5, pady=4, sticky="w")

        # DPI dropdown
        self._dpi_label = tk.Label(
            self._options_row, text=message_manager.get_ui_message("U117"),
        )
        self._dpi_label.pack(side="left", padx=(0, 2))
        self._dpi_var = tk.StringVar(value="72")
        self._dpi_combo = ttk.Combobox(
            self._options_row, textvariable=self._dpi_var,
            values=_DPI_CHOICES, width=6,
        )
        self._dpi_combo.pack(side="left", padx=(0, 15))

        # Paper size dropdown (includes portrait/landscape variants)
        self._paper_size_label = tk.Label(
            self._options_row, text=message_manager.get_ui_message("U086"),
        )
        self._paper_size_label.pack(side="left", padx=(0, 2))
        self._paper_sizes = _build_paper_size_entries()
        paper_names = list(self._paper_sizes.keys())
        self._paper_var = tk.StringVar(value="")
        self._paper_combo = ttk.Combobox(
            self._options_row, textvariable=self._paper_var,
            values=paper_names, state="readonly", width=30,
        )
        self._paper_combo.pack(side="left", padx=(0, 15))
        # Bind paper size selection to auto-fill width/height
        self._paper_combo.bind("<<ComboboxSelected>>", self._on_paper_size_selected)

        # Aspect ratio checkbox
        self._aspect_lock_var = tk.BooleanVar(value=True)
        self._aspect_check = tk.Checkbutton(
            self._options_row,
            text=message_manager.get_ui_message("U081"),
            variable=self._aspect_lock_var,
            command=self._on_aspect_toggle,
        )
        self._aspect_check.pack(side="left", padx=(0, 5))

        # Main processing: keep aspect ratio and warning label in sync with user input.
        self.width_var.trace_add("write", self._on_width_value_changed)
        self.height_var.trace_add("write", self._on_height_value_changed)
        self._dpi_var.trace_add("write", self._on_dpi_value_changed)

        # --- Row 3: Warning label (hidden by default) ---
        self._size_warning_var = tk.StringVar(value="")
        self._size_warning_label = tk.Label(
            self.frame_size, textvariable=self._size_warning_var,
            anchor="w", font=("", 10, "bold"), justify="left", wraplength=700,
        )
        self._size_warning_label.grid(row=3, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        self._size_warning_label.grid_remove()  # Hidden by default

        # --- Row 4: Execute button (right-aligned) ---
        self._size_convert_btn = ConvertImageButton(
            fr=self.frame_size,
            color_key="size_convert_button",
            text=message_manager.get_ui_message("U090"),
            command=self._on_size_convert,
        )
        self._size_convert_btn.grid(row=4, column=2, padx=5, pady=(8, 4), sticky="e")

    # ------------------------------------------------------------------
    # frame_status: Status bar
    # ------------------------------------------------------------------
    def _build_frame_status(self) -> None:
        """Build the status bar at the bottom."""
        self._status_label = ttk.Label(self, textvariable=self.status_var)
        self._status_label.grid(row=4, column=0, sticky="we", padx=5, pady=2)

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------
    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop for input file and output folder entries."""
        try:
            DragAndDropHandler.register_drop_target(
                self._base_file_path_entry,
                self._on_drop_input_file,
                _DROP_EXTENSIONS,
                self._show_status_feedback,
            )
            DragAndDropHandler.register_drop_target(
                self._output_folder_path_entry,
                self._on_drop_output_folder,
                feedback_callback=self._show_status_feedback,
                allow_directories=True,
            )
            logger.info(message_manager.get_log_message("L234"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L206", str(e)))

    def _on_drop_input_file(self, file_path: str) -> None:
        """Handle file drop on the input path entry.

        Args:
            file_path: Dropped file path.
        """
        self._base_file_path_entry.path_var.set(file_path)
        self.base_path.set(file_path)
        self._update_file_info(file_path)
        self._show_status_feedback(f"File loaded: {file_path}", True)

    def _on_drop_output_folder(self, folder_path: str) -> None:
        """Handle folder drop on the output path entry.

        Args:
            folder_path: Dropped folder path.
        """
        self._output_folder_path_entry.path_var.set(folder_path)
        self.output_path.set(folder_path)
        self._show_status_feedback(f"Folder loaded: {folder_path}", True)

    # ------------------------------------------------------------------
    # File / folder selection handlers
    # ------------------------------------------------------------------
    def _get_initial_dir_from_setting(self, setting_key: str) -> str:
        """Return an initial directory path for dialogs based on saved settings.

        Args:
            setting_key: UserSettingManager key.

        Returns:
            Existing directory path suitable for dialog initialdir.
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

    def _on_base_file_select(self) -> None:
        """Handle base file selection via dialog.

        Supports image files, PDF, and SVG.
        """
        prioritized_filetypes = [
            ("Image files", _IMAGE_EXTENSIONS),
            ("PDF files", "*.pdf"),
            ("SVG files", "*.svg"),
            ("All files", "*.*"),
        ]
        if self._last_input_dialog_filter == "pdf":
            prioritized_filetypes = [
                ("PDF files", "*.pdf"),
                ("Image files", _IMAGE_EXTENSIONS),
                ("SVG files", "*.svg"),
                ("All files", "*.*"),
            ]

        initial_dir = self._get_initial_dir_from_setting("base_file_path")
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U022",
            filetypes=prioritized_filetypes,
        )
        if file_path:
            selected_ext = Path(file_path).suffix.lower()
            if selected_ext == ".pdf":
                self._last_input_dialog_filter = "pdf"
            else:
                self._last_input_dialog_filter = "image"
            self._base_file_path_entry.path_var.set(file_path)
            self.base_path.set(file_path)
            self._update_file_info(file_path)
            logger.debug(message_manager.get_log_message("L070", file_path))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection via dialog."""
        initial_dir = self._get_initial_dir_from_setting("output_folder_path")
        folder_path = ask_folder_dialog(
            initialdir=initial_dir,
            title_code="U024",
        )
        if folder_path:
            self._output_folder_path_entry.path_var.set(folder_path)
            logger.debug(message_manager.get_log_message("L072", folder_path))

    # ------------------------------------------------------------------
    # UI update helpers
    # ------------------------------------------------------------------
    def _update_file_info(self, file_path: str) -> None:
        """Update UI elements when a new input file is selected.

        Updates filename labels in both blocks and populates meta info.

        Args:
            file_path: Path to the selected input file.
        """
        try:
            p = Path(file_path)
            name = p.name
            stem = p.stem
            ext = p.suffix.lower()

            # Main processing: show only filenames because arrow already indicates direction.
            self._ext_input_name_var.set(name)
            self._ext_output_name_var.set(f"{stem}.")
            self._last_input_dialog_filter = "pdf" if ext == ".pdf" else "image"

            # Size block: input name unchanged, output name gets "_resize" suffix
            self._size_input_name_var.set(name)
            self._size_output_name_var.set(f"{stem}_resize{ext}")

            # Filter the extension dropdown to exclude the input extension
            input_ext_normalized = ext.lstrip(".")
            # Normalize: .jpeg -> jpg, .tiff -> tif
            if input_ext_normalized in ("jpeg",):
                input_ext_normalized = "jpg"
            elif input_ext_normalized in ("tiff",):
                input_ext_normalized = "tif"
            filtered = [e for e in _EXT_CHOICES if e != input_ext_normalized]
            self._ext_combo.configure(values=filtered)
            if filtered:
                self._ext_target_var.set(filtered[0])

            # Update meta info (basic info from file system)
            self._update_meta_info(file_path)
            self._refresh_ext_warning_label()
            self._apply_copy_protection_state(file_path)
        except Exception as e:
            logger.error(f"Error updating file info: {e}")

    def _set_conversion_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable extension/size conversion buttons.

        Args:
            enabled: ``True`` to enable buttons, otherwise disable them.
        """
        state = "normal" if enabled else "disabled"
        for attr in ("_ext_convert_btn", "_size_convert_btn"):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.configure(state=state)
            except Exception:
                pass

    @staticmethod
    def _is_readonly_file(file_path: Path) -> bool:
        """Return whether the file is read-only on current platform.

        Args:
            file_path: Target file path.

        Returns:
            ``True`` when write access is not available.
        """
        writable_by_access = os.access(file_path, os.W_OK)
        if not writable_by_access:
            return True

        # Main processing: Windows read-only attribute check.
        file_attrs = getattr(file_path.stat(), "st_file_attributes", 0)
        readonly_flag = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0)
        if readonly_flag and file_attrs & readonly_flag:
            return True

        # Main processing: fallback check for ACL-based read-only restrictions.
        try:
            with open(file_path, "r+b"):
                pass
        except OSError:
            return True

        return False

    def _convert_pdf_first_page_to_image(
        self,
        input_path: Path,
        output_path: Path,
        target_ext: str,
    ) -> None:
        """Convert first page of a PDF into one image file.

        Args:
            input_path: PDF file path.
            output_path: Output image path.
            target_ext: Target image extension.
        """
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise RuntimeError(message_manager.get_ui_message("U114")) from exc

        pdf = pdfium.PdfDocument(str(input_path))
        try:
            if len(pdf) == 0:
                raise RuntimeError(message_manager.get_ui_message("U113"))

            page = pdf[0]
            try:
                bitmap = page.render(scale=300 / 72)
                pil_image = bitmap.to_pil()
                self._save_pil_image_to_extension(pil_image, output_path, target_ext)
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        finally:
            try:
                pdf.close()
            except Exception:
                pass

    def _set_size_controls_for_multisize(self, is_multisize: bool) -> None:
        """Toggle size-input controls based on multi-size file detection.

        Args:
            is_multisize: ``True`` when current input has multiple frames.
        """
        # Main processing: keep convert button available but limit editable controls.
        entry_state = "disabled" if is_multisize else "normal"
        paper_state = "disabled" if is_multisize else "readonly"

        for attr in ("_width_entry", "_height_entry", "_dpi_combo"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                widget.configure(state=entry_state)
            except Exception:
                pass

        if hasattr(self, "_paper_combo"):
            try:
                self._paper_combo.configure(state=paper_state)
            except Exception:
                pass

        if is_multisize:
            self._aspect_lock_var.set(True)
            self._size_warning_var.set(message_manager.get_ui_message("U110"))
            self._size_warning_label.grid()
        else:
            self._refresh_size_warning_label()

    def _is_copy_protected_pdf(self, file_path: Path) -> bool:
        """Return whether the PDF is copy-protected.

        Args:
            file_path: Target PDF path.

        Returns:
            True when copy protection is detected.
        """
        if file_path.suffix.lower() != ".pdf":
            return False

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path), strict=False)
            if reader.is_encrypted:
                return True

            encrypt_obj = reader.trailer.get("/Encrypt")
            if encrypt_obj is None:
                return False

            encrypt_dict = (
                encrypt_obj.get_object()
                if hasattr(encrypt_obj, "get_object")
                else encrypt_obj
            )
            permission_raw = encrypt_dict.get("/P") if encrypt_dict else None
            if permission_raw is None:
                return False

            permissions = int(permission_raw)
            copy_allowed = bool(permissions & 0x10)
            return not copy_allowed
        except Exception as exc:
            # Main processing: fail closed to avoid missing copy-protection warnings.
            logger.warning(f"Copy protection check failed: {exc}")
            return True

    def _apply_copy_protection_state(self, file_path: str) -> None:
        """Apply button/popup behavior based on PDF copy-protection state.

        Args:
            file_path: Current input file path.
        """
        path = Path(file_path)
        self._copy_protected_pdf_detected = False
        self._input_readonly_detected = False

        if not path.exists() or not path.is_file():
            self._set_conversion_buttons_enabled(True)
            return

        if path.suffix.lower() == ".pdf":
            self._copy_protected_pdf_detected = self._is_copy_protected_pdf(path)

        # Main processing: treat filesystem read-only files as conversion-blocked.
        self._input_readonly_detected = self._is_readonly_file(path)

        blocked = self._copy_protected_pdf_detected or self._input_readonly_detected
        self._set_conversion_buttons_enabled(not blocked)
        if blocked:
            warning_message = (
                message_manager.get_ui_message("U087")
                if self._copy_protected_pdf_detected
                else message_manager.get_ui_message("U099")
            )
            self._ext_warning_var.set(warning_message)
            self._ext_warning_label.grid()
            self._size_warning_var.set(warning_message)
            self._size_warning_label.grid()
            messagebox.showwarning(
                message_manager.get_ui_message("U033"),
                warning_message,
            )
            self._show_status_feedback(warning_message, False)

    def _update_meta_info(self, file_path: str) -> None:
        """Update the meta info label for the extension block.

        Args:
            file_path: Path to the input file.
        """
        path_obj = Path(file_path)
        source_ext = self.standardize_extension(path_obj.suffix)
        if source_ext == "pdf":
            self._update_pdf_meta_info(path_obj)
            return

        try:
            from PIL import Image
            with Image.open(file_path) as img:
                mode = img.mode
                w, h = img.size
                fmt = img.format or "-"
                dpi = img.info.get("dpi", None)
                dpi_str = self._format_dpi_pair_text(dpi[0], dpi[1]) if dpi else "-"
                self._original_dpi = float(dpi[0]) if dpi else None
                self._original_dpi_missing = dpi is None
                self._multi_frame_detected = int(getattr(img, "n_frames", 1) or 1) > 1
                # Localized labels for meta info display
                lbl_fmt = message_manager.get_ui_message("U091")
                lbl_mode = message_manager.get_ui_message("U092")
                lbl_size = message_manager.get_ui_message("U093")
                lbl_icc = message_manager.get_ui_message("U094")
                lbl_exif = message_manager.get_ui_message("U095")
                lbl_detected_dpi = message_manager.get_ui_message("U116")
                lbl_avail = message_manager.get_ui_message("U096")
                # Use "-" consistently for absent values
                icc_val = lbl_avail if img.info.get("icc_profile") else "-"
                exif_val = lbl_avail if img.info.get("exif") else "-"
                # Use vertical bar separators for compact readability.
                meta_text = (
                    f"{lbl_fmt}  {fmt}  |  {lbl_mode}  {mode}  |  "
                    f"{lbl_size}  {w}×{h} px  |  "
                    f"{lbl_detected_dpi}  {dpi_str}  |  {lbl_icc}  {icc_val}  |  {lbl_exif}  {exif_val}"
                )
                self._ext_meta_var.set(meta_text)

                # Update current size in the size block
                self._size_current_var.set(f"{w} px × {h} px")

                # Store original dimensions for aspect ratio calculation.
                self._orig_width = w
                self._orig_height = h
                if self._paper_size_priority_enabled and self._paper_var.get() in self._paper_sizes:
                    self._apply_paper_size_to_target_dimensions()
                else:
                    self.width_var.set(str(w))
                    self.height_var.set(str(h))
                self._set_size_controls_for_multisize(self._multi_frame_detected)
                self._refresh_size_warning_label()
        except Exception:
            self._original_dpi = None
            self._original_dpi_missing = True
            self._multi_frame_detected = False
            self._ext_meta_var.set("-")
            self._size_current_var.set("- px × - px")
            self._size_warning_var.set("")
            self._size_warning_label.grid_remove()
            self._set_size_controls_for_multisize(False)

    def _update_pdf_meta_info(self, file_path: Path) -> None:
        """Update meta display for PDF input files.

        Args:
            file_path: Input PDF path.
        """
        lbl_fmt = message_manager.get_ui_message("U091")
        lbl_mode = message_manager.get_ui_message("U092")
        lbl_size = message_manager.get_ui_message("U093")
        lbl_detected_dpi = message_manager.get_ui_message("U116")
        lbl_icc = message_manager.get_ui_message("U094")
        lbl_exif = message_manager.get_ui_message("U095")

        page_count = 0
        page_size_text = "-"
        dpi_text = "-"
        current_size_px_text = "- px × - px"
        detected_dpi: Optional[float] = None
        detected_dpi_missing = True
        width_px = 0
        height_px = 0
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path), strict=False)
            page_count = len(reader.pages)
            if page_count > 0:
                first_page = reader.pages[0]
                width_pt = float(first_page.mediabox.width)
                height_pt = float(first_page.mediabox.height)
                page_size_text = f"{int(width_pt)}×{int(height_pt)} pt ({page_count}p)"

                # Main processing: try to read effective DPI from embedded page image.
                extracted_dpi = self._extract_pdf_embedded_image_dpi(first_page, width_pt, height_pt)
                if extracted_dpi is not None:
                    dpi_x, dpi_y = extracted_dpi
                    dpi_text = self._format_dpi_pair_text(dpi_x, dpi_y)
                    detected_dpi = float(dpi_x)
                    detected_dpi_missing = False

                    width_px = int(round(width_pt * dpi_x / 72.0))
                    height_px = int(round(height_pt * dpi_y / 72.0))
                    current_size_px_text = f"{width_px} px × {height_px} px"
        except Exception:
            page_size_text = "-"
            dpi_text = "-"
            current_size_px_text = "- px × - px"

        # Main processing: show PDF-specific metadata instead of a blank placeholder.
        meta_text = (
            f"{lbl_fmt}  PDF  |  {lbl_mode}  -  |  "
            f"{lbl_size}  {page_size_text}  |  "
            f"{lbl_detected_dpi}  {dpi_text}  |  {lbl_icc}  -  |  {lbl_exif}  -"
        )
        self._ext_meta_var.set(meta_text)

        self._size_current_var.set(current_size_px_text)
        self._orig_width = width_px
        self._orig_height = height_px
        self._original_dpi = detected_dpi
        self._original_dpi_missing = detected_dpi_missing
        self._multi_frame_detected = page_count > 1

        if self._paper_size_priority_enabled and self._paper_var.get() in self._paper_sizes:
            self._apply_paper_size_to_target_dimensions()
        else:
            self.width_var.set("")
            self.height_var.set("")

        self._set_size_controls_for_multisize(self._multi_frame_detected)
        self._refresh_size_warning_label()

    @staticmethod
    def _format_dpi_pair_text(dpi_x: float, dpi_y: float) -> str:
        """Format DPI values with explicit X/Y axis labels.

        Args:
            dpi_x: Horizontal DPI value.
            dpi_y: Vertical DPI value.

        Returns:
            Human-readable DPI text with units.
        """
        x_val = int(round(float(dpi_x)))
        y_val = int(round(float(dpi_y)))
        return f"X:{x_val} dpi / Y:{y_val} dpi"

    @staticmethod
    def _extract_pdf_embedded_image_dpi(
        page: Any,
        page_width_pt: float,
        page_height_pt: float,
    ) -> Optional[tuple[int, int]]:
        """Extract effective DPI from the largest embedded image on a PDF page.

        Args:
            page: First page object from ``pypdf.PdfReader.pages``.
            page_width_pt: Page width in points.
            page_height_pt: Page height in points.

        Returns:
            Tuple of ``(dpi_x, dpi_y)`` when extractable, otherwise ``None``.
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

    @staticmethod
    def _parse_positive_int(value: str) -> Optional[int]:
        """Parse positive integer value from text input.

        Args:
            value: Text value from UI entry.

        Returns:
            Parsed positive integer, or ``None`` when invalid.
        """
        text = value.strip()
        if not text:
            return None
        try:
            number = int(text)
        except ValueError:
            return None
        if number <= 0:
            return None
        return number

    def _is_upscaling_target(self, width: int, height: int) -> bool:
        """Return whether target size upscales the source image.

        Args:
            width: Target width in pixels.
            height: Target height in pixels.

        Returns:
            True if either dimension is larger than the original image.
        """
        orig_w = int(getattr(self, "_orig_width", 0) or 0)
        orig_h = int(getattr(self, "_orig_height", 0) or 0)
        if orig_w <= 0 or orig_h <= 0:
            return False
        return width > orig_w or height > orig_h

    def _refresh_size_warning_label(self) -> None:
        """Refresh the size warning label based on current target size."""
        if self._multi_frame_detected:
            self._size_warning_var.set(message_manager.get_ui_message("U110"))
            self._size_warning_label.grid()
            return

        width = self._parse_positive_int(self.width_var.get())
        height = self._parse_positive_int(self.height_var.get())
        if width is None or height is None:
            self._size_warning_var.set("")
            self._size_warning_label.grid_remove()
            return

        warnings = self._collect_size_warnings(width, height)
        if warnings:
            self._size_warning_var.set("\n".join(warnings))
            self._size_warning_label.grid()
        else:
            self._size_warning_var.set("")
            self._size_warning_label.grid_remove()

    def _has_aspect_ratio_conflict(self, width: int, height: int) -> bool:
        """Return whether target ratio conflicts with original ratio.

        Args:
            width: Target width.
            height: Target height.

        Returns:
            ``True`` when ratio differs while aspect lock is enabled.
        """
        if not self._aspect_lock_var.get():
            return False

        orig_w = int(getattr(self, "_orig_width", 0) or 0)
        orig_h = int(getattr(self, "_orig_height", 0) or 0)
        if orig_w <= 0 or orig_h <= 0:
            return False

        # Main processing: compare cross-products to avoid floating-point drift.
        return (width * orig_h) != (height * orig_w)

    def _collect_size_warnings(self, width: int, height: int) -> List[str]:
        """Collect warning messages for size conversion.

        Args:
            width: Target width.
            height: Target height.

        Returns:
            Localized warning message list.
        """
        warnings: List[str] = []

        if self._is_upscaling_target(width, height):
            warnings.append(message_manager.get_ui_message("U082"))

        if self._has_aspect_ratio_conflict(width, height):
            warnings.append(message_manager.get_ui_message("U105"))

        dpi_text = self._dpi_var.get().strip() if hasattr(self, "_dpi_var") else ""
        selected_dpi: Optional[float]
        try:
            selected_dpi = float(dpi_text) if dpi_text else None
        except ValueError:
            selected_dpi = None

        if selected_dpi is not None:
            if self._original_dpi_missing:
                warnings.append(message_manager.get_ui_message("U106"))
            elif self._original_dpi is not None and selected_dpi < self._original_dpi:
                warnings.append(
                    message_manager.get_ui_message(
                        "U107", int(selected_dpi), int(self._original_dpi)
                    )
                )

        deduplicated: List[str] = []
        for msg in warnings:
            if msg not in deduplicated:
                deduplicated.append(msg)
        return deduplicated

    def _on_width_value_changed(self, *args: Any) -> None:
        """Handle width updates for aspect ratio and warning refresh.

        Args:
            *args: Tkinter trace callback arguments.
        """
        _ = args
        if self._size_syncing:
            return

        if not self._aspect_lock_var.get():
            self._refresh_size_warning_label()
            return

        width = self._parse_positive_int(self.width_var.get())
        orig_w = int(getattr(self, "_orig_width", 0) or 0)
        orig_h = int(getattr(self, "_orig_height", 0) or 0)
        if width is None or orig_w <= 0 or orig_h <= 0:
            self._refresh_size_warning_label()
            return

        # Main processing: synchronize height when aspect lock is on.
        synced_height = max(1, int(round(width * orig_h / orig_w)))
        self._size_syncing = True
        try:
            self.height_var.set(str(synced_height))
        finally:
            self._size_syncing = False
        self._refresh_size_warning_label()

    def _on_height_value_changed(self, *args: Any) -> None:
        """Handle height updates for aspect ratio and warning refresh.

        Args:
            *args: Tkinter trace callback arguments.
        """
        _ = args
        if self._size_syncing:
            return

        if not self._aspect_lock_var.get():
            self._refresh_size_warning_label()
            return

        height = self._parse_positive_int(self.height_var.get())
        orig_w = int(getattr(self, "_orig_width", 0) or 0)
        orig_h = int(getattr(self, "_orig_height", 0) or 0)
        if height is None or orig_w <= 0 or orig_h <= 0:
            self._refresh_size_warning_label()
            return

        # Main processing: synchronize width when aspect lock is on.
        synced_width = max(1, int(round(height * orig_w / orig_h)))
        self._size_syncing = True
        try:
            self.width_var.set(str(synced_width))
        finally:
            self._size_syncing = False
        self._refresh_size_warning_label()

    def _on_aspect_toggle(self) -> None:
        """Handle aspect-ratio checkbox toggle event."""
        if self._multi_frame_detected and not self._aspect_lock_var.get():
            message = message_manager.get_ui_message("U109")
            messagebox.showwarning(message_manager.get_ui_message("U033"), message)
            self._aspect_lock_var.set(True)
            self._size_warning_var.set(message)
            self._size_warning_label.grid()
            return

        if self._aspect_lock_var.get():
            self._on_width_value_changed()
        else:
            self._refresh_size_warning_label()

    def _on_paper_size_selected(self, event: Any = None) -> None:
        """Handle paper size selection and auto-fill width/height.

        Args:
            event: Combobox selection event (unused).
        """
        _ = event
        paper_name = self._paper_var.get()
        if paper_name not in self._paper_sizes:
            self._paper_size_priority_enabled = False
            return

        self._paper_size_priority_enabled = True
        self._apply_paper_size_to_target_dimensions()
        self._refresh_size_warning_label()

    def _convert_size_image(
        self,
        input_path: Path,
        output_path: Path,
        width: int,
        height: int,
        dpi: Optional[float],
    ) -> None:
        """Resize an image and save using source extension format.

        Args:
            input_path: Input image path.
            output_path: Output image path.
            width: Target width in pixels.
            height: Target height in pixels.
            dpi: Target DPI value, or ``None`` when unavailable.
        """
        from PIL import Image

        target_ext = self.standardize_extension(output_path.suffix)
        save_format = _PILLOW_SAVE_FORMATS.get(target_ext, target_ext.upper())

        with Image.open(input_path) as img:
            resized = img.resize((width, height), Image.Resampling.LANCZOS)

            # Main processing: normalize mode for format requirements.
            if target_ext in ("jpg", "pdf") and resized.mode in ("RGBA", "LA", "P"):
                resized = resized.convert("RGB")
            elif target_ext == "bmp" and resized.mode not in ("RGB", "L"):
                resized = resized.convert("RGB")
            elif target_ext == "gif" and resized.mode not in ("P", "L"):
                resized = resized.convert("P", palette=Image.ADAPTIVE, colors=256)

            save_kwargs: Dict[str, Any] = {"format": save_format}
            if dpi is not None and dpi > 0:
                save_kwargs["dpi"] = (dpi, dpi)
            resized.save(output_path, **save_kwargs)

    # ------------------------------------------------------------------
    # Extension normalization
    # ------------------------------------------------------------------
    @staticmethod
    def standardize_extension(extension: str) -> str:
        """Normalize a file extension to its canonical lowercase form.

        Args:
            extension: Raw extension string (with or without leading dot).

        Returns:
            Normalized extension without leading dot (e.g. 'jpg', 'tif').
        """
        ext = extension.lstrip(".").lower()
        # Canonical mappings
        if ext in ("jpeg",):
            return "jpg"
        if ext in ("tiff",):
            return "tif"
        return ext

    # ------------------------------------------------------------------
    # Extension conversion (M2-003)
    # ------------------------------------------------------------------
    @staticmethod
    def _image_has_alpha_channel(image: Any) -> bool:
        """Return whether a PIL image has transparency information.

        Args:
            image: PIL Image instance.

        Returns:
            True if the image contains alpha or palette transparency.
        """
        mode = str(getattr(image, "mode", ""))
        if mode in ("RGBA", "LA"):
            return True
        info = getattr(image, "info", {})
        return mode == "P" and "transparency" in info

    def _collect_ext_warnings(self, input_path: Path, target_ext: str) -> List[str]:
        """Collect warning messages for extension conversion.

        Args:
            input_path: Input file path.
            target_ext: Target extension in canonical form.

        Returns:
            Localized warning message list.
        """
        warnings: List[str] = []
        src_ext = self.standardize_extension(input_path.suffix)

        # Main processing: warn for lossy compression formats.
        if target_ext in ("jpg", "webp"):
            warnings.append(message_manager.get_ui_message("U079"))

        # Main processing: warn for GIF palette reduction.
        if target_ext == "gif":
            warnings.append(message_manager.get_ui_message("U080"))

        # Main processing: alpha loss warning for PNG -> jpg/bmp/pdf.
        if src_ext == "png" and target_ext in ("jpg", "bmp", "pdf"):
            try:
                from PIL import Image

                with Image.open(input_path) as img:
                    if self._image_has_alpha_channel(img):
                        warnings.append(message_manager.get_ui_message("U078"))
            except Exception:
                # If metadata inspection fails, continue without blocking conversion.
                pass

        # Keep order while removing duplicates.
        deduplicated: List[str] = []
        for msg in warnings:
            if msg not in deduplicated:
                deduplicated.append(msg)
        return deduplicated

    def _refresh_ext_warning_label(self, event: Any = None) -> None:
        """Refresh extension-warning label based on current selection.

        Args:
            event: Combobox event (unused).
        """
        _ = event
        input_path_str = self._base_file_path_entry.path_var.get().strip()
        if not input_path_str:
            self._ext_warning_var.set("")
            self._ext_warning_label.grid_remove()
            return

        input_path = Path(input_path_str)
        if not input_path.exists() or not input_path.is_file():
            self._ext_warning_var.set("")
            self._ext_warning_label.grid_remove()
            return

        target_ext = self.standardize_extension(self._ext_target_var.get())
        warnings = self._collect_ext_warnings(input_path, target_ext)
        if warnings:
            self._ext_warning_var.set("\n".join(warnings))
            self._ext_warning_label.grid()
        else:
            self._ext_warning_var.set("")
            self._ext_warning_label.grid_remove()

    def _build_unique_output_path(
        self,
        output_dir: Path,
        stem: str,
        target_ext: str,
    ) -> tuple[Path, Optional[str]]:
        """Build a non-conflicting output path in the output directory.

        Args:
            output_dir: Output directory path.
            stem: Base file stem.
            target_ext: Target extension without dot.

        Returns:
            Tuple of (output_path, added_suffix). added_suffix is ``None`` when no
            collision occurred.
        """
        base_candidate = output_dir / f"{stem}.{target_ext}"
        if not base_candidate.exists():
            return base_candidate, None

        index = 1
        while True:
            suffix = f"({index})"
            candidate = output_dir / f"{stem}{suffix}.{target_ext}"
            if not candidate.exists():
                return candidate, suffix
            index += 1

    def _build_unique_output_dir(
        self,
        output_dir: Path,
        stem: str,
    ) -> tuple[Path, Optional[str]]:
        """Build a non-conflicting output directory path.

        Args:
            output_dir: Parent output directory.
            stem: Folder base name.

        Returns:
            Tuple of (folder_path, added_suffix).
        """
        base_candidate = output_dir / stem
        if not base_candidate.exists():
            return base_candidate, None

        index = 1
        while True:
            suffix = f"({index})"
            candidate = output_dir / f"{stem}{suffix}"
            if not candidate.exists():
                return candidate, suffix
            index += 1

    def _save_pil_image_to_extension(
        self,
        image: Any,
        output_path: Path,
        target_ext: str,
    ) -> None:
        """Save a PIL image to target extension with required mode normalization.

        Args:
            image: PIL image instance.
            output_path: Output file path.
            target_ext: Target extension without dot.
        """
        save_img = image
        if target_ext in ("jpg", "pdf") and image.mode in ("RGBA", "LA", "P"):
            save_img = image.convert("RGB")
        elif target_ext == "bmp" and image.mode not in ("RGB", "L"):
            save_img = image.convert("RGB")
        elif target_ext == "gif" and image.mode not in ("P", "L"):
            from PIL import Image

            save_img = image.convert("P", palette=Image.ADAPTIVE, colors=256)

        save_format = _PILLOW_SAVE_FORMATS.get(target_ext, target_ext.upper())
        save_img.save(output_path, format=save_format)

    def _count_pdf_pages(self, input_path: Path) -> int:
        """Count pages in a PDF document.

        Args:
            input_path: Input PDF path.

        Returns:
            Number of pages.
        """
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(input_path))
            try:
                return len(pdf)
            finally:
                try:
                    pdf.close()
                except Exception:
                    pass
        except Exception:
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(input_path), strict=False)
                return len(reader.pages)
            except Exception as exc:
                raise RuntimeError(message_manager.get_ui_message("U114")) from exc

    def _count_multipage_frames(self, input_path: Path) -> int:
        """Count page/frame number for PDF or TIFF-like sources.

        Args:
            input_path: Input source path.

        Returns:
            Page/frame count (>=1 when detectable).
        """
        source_ext = self.standardize_extension(input_path.suffix)
        if source_ext == "pdf":
            return self._count_pdf_pages(input_path)

        if source_ext == "tif":
            try:
                from PIL import Image

                with Image.open(input_path) as img:
                    return int(getattr(img, "n_frames", 1) or 1)
            except Exception:
                return 1
        return 1

    def _convert_with_pillow(
        self,
        input_path: Path,
        output_path: Path,
        target_ext: str,
    ) -> None:
        """Convert image formats supported directly by Pillow.

        Args:
            input_path: Input file path.
            output_path: Output file path.
            target_ext: Target extension without dot.
        """
        from PIL import Image

        with Image.open(input_path) as img:
            save_img = img

            # Main processing: pre-convert unsupported modes for target format.
            if target_ext in ("jpg", "pdf") and img.mode in ("RGBA", "LA", "P"):
                save_img = img.convert("RGB")
            elif target_ext == "bmp" and img.mode not in ("RGB", "L"):
                save_img = img.convert("RGB")
            elif target_ext == "gif" and img.mode not in ("P", "L"):
                save_img = img.convert("P", palette=Image.ADAPTIVE, colors=256)

            save_format = _PILLOW_SAVE_FORMATS.get(target_ext, target_ext.upper())

            # Main processing: preserve metadata where target format supports it.
            save_kwargs: Dict[str, Any] = {"format": save_format}

            exif_bytes = img.info.get("exif")
            if exif_bytes is None:
                try:
                    exif_obj = img.getexif()
                    if exif_obj:
                        exif_bytes = exif_obj.tobytes()
                except Exception:
                    exif_bytes = None
            if exif_bytes and target_ext in ("jpg", "png", "webp", "tif"):
                save_kwargs["exif"] = exif_bytes

            icc_profile = img.info.get("icc_profile")
            if icc_profile and target_ext in ("jpg", "png", "webp", "tif"):
                save_kwargs["icc_profile"] = icc_profile

            dpi_info = img.info.get("dpi")
            if (
                isinstance(dpi_info, tuple)
                and len(dpi_info) >= 2
                and target_ext in ("jpg", "png", "webp", "tif")
            ):
                try:
                    save_kwargs["dpi"] = (float(dpi_info[0]), float(dpi_info[1]))
                except Exception:
                    pass

            try:
                save_img.save(output_path, **save_kwargs)
            except Exception:
                # Main processing: skip unsupported metadata keys without aborting conversion.
                fallback_kwargs = dict(save_kwargs)
                for meta_key in ("exif", "icc_profile", "dpi"):
                    if meta_key in fallback_kwargs:
                        fallback_kwargs.pop(meta_key, None)
                        try:
                            save_img.save(output_path, **fallback_kwargs)
                            return
                        except Exception:
                            continue
                save_img.save(output_path, format=save_format)

    def _convert_pdf_pages_to_images(
        self,
        input_path: Path,
        output_dir: Path,
        base_stem: str,
        target_ext: str,
    ) -> int:
        """Convert all PDF pages to separate image files.

        Args:
            input_path: PDF file path.
            output_dir: Output directory where page files are written.
            base_stem: Base stem for output filenames.
            target_ext: Target image extension.

        Returns:
            Number of converted pages.
        """
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise RuntimeError(message_manager.get_ui_message("U114")) from exc

        pdf = pdfium.PdfDocument(str(input_path))
        try:
            if len(pdf) == 0:
                raise RuntimeError(message_manager.get_ui_message("U113"))

            converted = 0
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                try:
                    bitmap = page.render(scale=300 / 72)
                    pil_image = bitmap.to_pil()
                    page_output_path = output_dir / f"{base_stem}_{page_index + 1:03d}.{target_ext}"
                    self._save_pil_image_to_extension(
                        pil_image,
                        page_output_path,
                        target_ext,
                    )
                    converted += 1
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass
            return converted
        finally:
            try:
                pdf.close()
            except Exception:
                pass

    def _convert_multipage_tiff_to_images(
        self,
        input_path: Path,
        output_dir: Path,
        base_stem: str,
        target_ext: str,
    ) -> int:
        """Convert all TIFF frames to separate image files.

        Args:
            input_path: Input TIFF path.
            output_dir: Output directory for frame files.
            base_stem: Base stem for output filenames.
            target_ext: Target image extension.

        Returns:
            Number of converted frames.
        """
        from PIL import Image

        converted = 0
        with Image.open(input_path) as img:
            frame_count = int(getattr(img, "n_frames", 1) or 1)
            for frame_index in range(frame_count):
                img.seek(frame_index)
                save_img = img.copy()
                page_output_path = output_dir / f"{base_stem}_{frame_index + 1:03d}.{target_ext}"
                self._save_pil_image_to_extension(save_img, page_output_path, target_ext)
                converted += 1
        return converted

    def _convert_svg_to_png(self, input_path: Path, output_path: Path) -> None:
        """Convert SVG to PNG using optional svglib/reportlab stack.

        Args:
            input_path: SVG file path.
            output_path: PNG output path.
        """
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM
        except ImportError as exc:
            raise RuntimeError(message_manager.get_ui_message("U088")) from exc

        try:
            drawing = svg2rlg(str(input_path))
            if drawing is None:
                raise RuntimeError(message_manager.get_ui_message("U088"))
            renderPM.drawToFile(drawing, str(output_path), fmt="PNG")
        except Exception as exc:
            raise RuntimeError(message_manager.get_ui_message("U088")) from exc

    def _convert_extension_file(
        self,
        input_path: Path,
        output_path: Path,
        target_ext: str,
    ) -> None:
        """Convert input file to target extension.

        Args:
            input_path: Input file path.
            output_path: Output file path.
            target_ext: Target extension without dot.
        """
        source_ext = self.standardize_extension(input_path.suffix)

        # Main processing: explicit handlers for PDF/SVG special cases.
        if source_ext == "pdf":
            if target_ext == "pdf":
                raise RuntimeError(message_manager.get_ui_message("U111"))
            self._convert_pdf_first_page_to_image(input_path, output_path, target_ext)
            return

        if source_ext == "svg":
            if target_ext != "png":
                raise RuntimeError(message_manager.get_ui_message("U088"))
            self._convert_svg_to_png(input_path, output_path)
            return

        self._convert_with_pillow(input_path, output_path, target_ext)

    def _on_ext_convert(self) -> None:
        """Handle extension conversion button click."""
        input_path_str = self._base_file_path_entry.path_var.get().strip()
        if input_path_str:
            self._apply_copy_protection_state(input_path_str)

        if self._copy_protected_pdf_detected or self._input_readonly_detected:
            return

        output_dir_str = self._output_folder_path_entry.path_var.get().strip()
        target_ext = self.standardize_extension(self._ext_target_var.get())

        input_path = Path(input_path_str) if input_path_str else Path("")
        output_dir = Path(output_dir_str) if output_dir_str else Path("")

        if not input_path_str or not input_path.exists() or not input_path.is_file():
            self._show_status_feedback(message_manager.get_ui_message("U100"), False)
            return
        if not output_dir_str or not output_dir.exists() or not output_dir.is_dir():
            self._show_status_feedback(message_manager.get_ui_message("U101"), False)
            return
        if not target_ext:
            self._show_status_feedback(message_manager.get_ui_message("U102"), False)
            return

        warnings = self._collect_ext_warnings(input_path, target_ext)
        if warnings:
            confirmed = messagebox.askokcancel(
                message_manager.get_ui_message("U033"),
                "\n".join(warnings),
            )
            if not confirmed:
                self._set_status(message_manager.get_ui_message("U103"))
                return

        source_ext = self.standardize_extension(input_path.suffix)
        try:
            frame_count = self._count_multipage_frames(input_path)
        except RuntimeError as exc:
            self._show_status_feedback(str(exc), False)
            return
        multi_page_export = source_ext in ("pdf", "tif") and frame_count > 1 and target_ext != "pdf"

        if multi_page_export:
            confirm_message = message_manager.get_ui_message("U108")
            self._ext_warning_var.set(confirm_message)
            self._ext_warning_label.grid()
            confirmed = messagebox.askokcancel(
                message_manager.get_ui_message("U033"),
                confirm_message,
            )
            if not confirmed:
                self._set_status(message_manager.get_ui_message("U103"))
                return

            page_output_dir, folder_suffix = self._build_unique_output_dir(
                output_dir=output_dir,
                stem=input_path.stem,
            )
            page_output_dir.mkdir(parents=True, exist_ok=False)
            try:
                if source_ext == "pdf":
                    self._convert_pdf_pages_to_images(
                        input_path=input_path,
                        output_dir=page_output_dir,
                        base_stem=input_path.stem,
                        target_ext=target_ext,
                    )
                else:
                    self._convert_multipage_tiff_to_images(
                        input_path=input_path,
                        output_dir=page_output_dir,
                        base_stem=input_path.stem,
                        target_ext=target_ext,
                    )
            except RuntimeError as exc:
                logger.error(str(exc))
                messagebox.showerror(message_manager.get_ui_message("U033"), str(exc))
                self._show_status_feedback(str(exc), False)
                return
            except Exception as exc:
                logger.error(f"Extension conversion failed: {exc}")
                self._show_status_feedback(str(exc), False)
                return

            status_message = message_manager.get_ui_message("U112")
            if folder_suffix is not None:
                suffix_message = message_manager.get_ui_message("U115").format(folder_suffix)
                status_message = f"{status_message} / {suffix_message}"
            self._show_status_feedback(status_message, True)
            return

        output_path, added_suffix = self._build_unique_output_path(
            output_dir=output_dir,
            stem=input_path.stem,
            target_ext=target_ext,
        )

        try:
            self._convert_extension_file(
                input_path=input_path,
                output_path=output_path,
                target_ext=target_ext,
            )
        except RuntimeError as exc:
            logger.error(str(exc))
            messagebox.showerror(message_manager.get_ui_message("U033"), str(exc))
            self._show_status_feedback(str(exc), False)
            return
        except Exception as exc:
            logger.error(f"Extension conversion failed: {exc}")
            self._show_status_feedback(str(exc), False)
            return

        status_message = message_manager.get_ui_message("U083")
        if added_suffix is not None:
            suffix_message = message_manager.get_ui_message("U089").format(added_suffix)
            status_message = f"{status_message} / {suffix_message}"
        self._show_status_feedback(status_message, True)

    def _on_size_convert(self) -> None:
        """Handle size conversion button click."""
        input_path_str = self._base_file_path_entry.path_var.get().strip()
        if input_path_str:
            self._apply_copy_protection_state(input_path_str)

        if self._copy_protected_pdf_detected or self._input_readonly_detected:
            return

        output_dir_str = self._output_folder_path_entry.path_var.get().strip()

        input_path = Path(input_path_str) if input_path_str else Path("")
        output_dir = Path(output_dir_str) if output_dir_str else Path("")

        if not input_path_str or not input_path.exists() or not input_path.is_file():
            self._show_status_feedback(message_manager.get_ui_message("U100"), False)
            return
        if not output_dir_str or not output_dir.exists() or not output_dir.is_dir():
            self._show_status_feedback(message_manager.get_ui_message("U101"), False)
            return

        width = self._parse_positive_int(self.width_var.get())
        height = self._parse_positive_int(self.height_var.get())
        if width is None or height is None:
            self._show_status_feedback(message_manager.get_ui_message("U052"), False)
            return

        source_ext = self.standardize_extension(input_path.suffix)
        if source_ext in ("pdf", "svg"):
            warning_message = message_manager.get_ui_message("U104")
            self._size_warning_var.set(warning_message)
            self._size_warning_label.grid()
            messagebox.showwarning(message_manager.get_ui_message("U033"), warning_message)
            self._show_status_feedback(warning_message, False)
            return

        if self._multi_frame_detected:
            warning_message = message_manager.get_ui_message("U110")
            self._size_warning_var.set(warning_message)
            self._size_warning_label.grid()
            messagebox.showwarning(message_manager.get_ui_message("U033"), warning_message)
            self._show_status_feedback(warning_message, False)
            return

        warning_messages = self._collect_size_warnings(width, height)
        if warning_messages:
            warning_message = "\n".join(warning_messages)
            self._size_warning_var.set("\n".join(warning_messages))
            self._size_warning_label.grid()
            confirmed = messagebox.askokcancel(
                message_manager.get_ui_message("U033"),
                warning_message,
            )
            if not confirmed:
                self._set_status(message_manager.get_ui_message("U103"))
                return

        try:
            dpi_value = float(self._dpi_var.get().strip()) if self._dpi_var.get().strip() else None
        except ValueError:
            dpi_value = None

        output_path, added_suffix = self._build_unique_output_path(
            output_dir=output_dir,
            stem=f"{input_path.stem}_resize",
            target_ext=source_ext,
        )

        try:
            self._convert_size_image(
                input_path=input_path,
                output_path=output_path,
                width=width,
                height=height,
                dpi=dpi_value,
            )
        except Exception as exc:
            logger.error(f"Size conversion failed: {exc}")
            self._show_status_feedback(str(exc), False)
            return

        status_message = message_manager.get_ui_message("U084")
        if added_suffix is not None:
            suffix_message = message_manager.get_ui_message("U089").format(added_suffix)
            status_message = f"{status_message} / {suffix_message}"
        self._show_status_feedback(status_message, True)
        if warning_messages:
            self._size_warning_var.set("\n".join(warning_messages))
            self._size_warning_label.grid()
        else:
            self._refresh_size_warning_label()

    def _apply_paper_size_to_target_dimensions(self) -> None:
        """Apply selected paper size and DPI to width/height entries.

        This helper keeps target pixel dimensions aligned with paper selection.
        """
        paper_name = self._paper_var.get()
        if paper_name not in self._paper_sizes:
            return

        try:
            dpi = float(self._dpi_var.get() or "72")
        except ValueError:
            dpi = 72.0

        w_mm, h_mm = self._paper_sizes[paper_name]
        w_px = int(w_mm * dpi / 25.4)
        h_px = int(h_mm * dpi / 25.4)

        self._size_syncing = True
        try:
            self.width_var.set(str(w_px))
            self.height_var.set(str(h_px))
        finally:
            self._size_syncing = False

    def _on_dpi_value_changed(self, *args: Any) -> None:
        """Handle DPI changes and update paper-size-derived dimensions.

        Args:
            *args: Tkinter trace callback arguments.
        """
        _ = args
        if self._size_syncing:
            return
        if self._paper_size_priority_enabled and self._paper_var.get() in self._paper_sizes:
            self._apply_paper_size_to_target_dimensions()
        self._refresh_size_warning_label()

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------
    def _set_status(self, text: str, auto_clear_ms: int = 5000) -> None:
        """Set status bar text with optional auto-clear.

        Args:
            text: Status message.
            auto_clear_ms: Milliseconds until auto-clear (0 to disable).
        """
        self.status_var.set(text)
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        if auto_clear_ms > 0:
            self.after_id = self.after(
                auto_clear_ms,
                lambda: self.status_var.set("") if self.status_var is not None else None,
            )

    def _show_status_feedback(self, message: str, success: bool) -> None:
        """Show feedback message in the status bar.

        Args:
            message: Feedback message.
            success: Whether the operation was successful.
        """
        if success:
            logger.info(message)
        else:
            logger.error(message)
        self._set_status(message)

    # ------------------------------------------------------------------
    # Theme color application
    # ------------------------------------------------------------------
    def apply_theme_color(self, theme_colors: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to all widgets in this tab.

        Covers every plain tk.Frame, tk.Label, tk.LabelFrame, tk.Checkbutton
        created inside this tab so that no widget retains the default system
        background colour after a theme switch.

        Args:
            theme_colors: Dictionary of theme color data.
        """
        frame_colors = theme_colors.get("Frame", {})
        label_colors = theme_colors.get("Label", {})
        bg = frame_colors.get("bg", "")
        # Main processing: avoid empty fg when Label key is missing (e.g. light/pastel)
        # so tk.Label/tk.Checkbutton configure does not fail and skip bg updates.
        fg = label_colors.get("fg", frame_colors.get("fg", "#000000"))

        # Block background: always follow Frame bg so block internals match theme base exactly.
        section_hdr = theme_colors.get("section_header_label", {})
        block_bg = bg
        block_fg = section_hdr.get("fg", fg)

        # --- 1. Top-level frames (outside blocks) use Frame bg ---
        for attr in ("frame_main0", "frame_main1"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(bg=bg)
                except Exception:
                    pass

        # --- 2. LabelFrame sections (tk.LabelFrame) ---
        for lf_attr in ("frame_ext", "frame_size"):
            lf = getattr(self, lf_attr, None)
            if lf is not None:
                try:
                    lf.configure(fg=block_fg, bg=block_bg)
                except Exception:
                    pass

        # --- 3. Sub-frames inside blocks use block bg ---
        for attr in ("_ext_meta_frame", "_size_row", "_options_row"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(bg=block_bg)
                except Exception:
                    pass

        # --- 4. Arrow labels ---
        arrow_colors = theme_colors.get("conversion_arrow_label", {})
        arrow_fg = arrow_colors.get("fg", fg)
        for attr in ("_ext_arrow_label", "_size_arrow_label", "_size_row_arrow"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(fg=arrow_fg, bg=block_bg)
                except Exception:
                    pass

        # --- 5. Meta info label + frame ---
        meta_colors = theme_colors.get("meta_info_label", {})
        if hasattr(self, "_ext_meta_frame"):
            try:
                self._ext_meta_frame.configure(bg=block_bg)
            except Exception:
                pass
        if hasattr(self, "_ext_meta_label"):
            try:
                self._ext_meta_label.configure(
                    fg=meta_colors.get("fg", fg),
                    bg=block_bg,
                )
            except Exception:
                pass

        # --- 6. Warning labels ---
        warn_colors = theme_colors.get("warning_label", {})
        for attr in ("_ext_warning_label", "_size_warning_label"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(
                        fg=warn_colors.get("fg", "#ff0000"),
                        bg=block_bg,
                    )
                except Exception:
                    pass

        # --- 7. Filename labels ---
        # Main processing: allow per-theme filename label contrast independent from entry widgets.
        entry_colors = theme_colors.get("entry_normal", {})
        filename_colors = theme_colors.get("filename_label", entry_colors)
        entry_bg = filename_colors.get("bg", entry_colors.get("bg", block_bg))
        filename_fg = filename_colors.get("fg", fg)
        # Output frame container also uses entry bg
        if hasattr(self, "_ext_output_frame"):
            try:
                self._ext_output_frame.configure(bg=entry_bg)
            except Exception:
                pass
        filename_labels = [
            "_ext_input_label", "_ext_output_name_label",
            "_size_input_label", "_size_output_label",
        ]
        for attr in filename_labels:
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(fg=filename_fg, bg=entry_bg)
                except Exception:
                    pass

        # --- 8. Other plain labels inside blocks (current size, DPI, paper) ---
        other_labels = [
            "_size_current_label",
            "_dpi_label", "_paper_size_label",
        ]
        for attr in other_labels:
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(fg=fg, bg=block_bg)
                except Exception:
                    pass

        # --- 9. Checkbutton ---
        if hasattr(self, "_aspect_check"):
            try:
                self._aspect_check.configure(
                    fg=fg, bg=block_bg,
                    activebackground=block_bg, activeforeground=fg,
                    selectcolor=block_bg,
                )
            except Exception:
                pass

        # --- 8. WidgetsTracker-registered child widgets ---
        for widget in self.base_widgets.get_widgets():
            if hasattr(widget, "apply_theme_color"):
                widget.apply_theme_color(theme_colors)

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget with theme settings.

        Args:
            theme_settings: Theme settings dictionary.
        """
        if theme_settings:
            self.configure(**theme_settings)
