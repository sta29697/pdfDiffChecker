from __future__ import annotations

import os
from logging import getLogger
from typing import Dict, Any, List, Optional

import tkinter as tk
from tkinter import ttk
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
        self._ext_input_name_var = tk.StringVar(value="-")
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

        self._ext_output_name_var = tk.StringVar(value="-")
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
            anchor="w", font=("", 9),
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
            self._options_row, text=message_manager.get_ui_message("U085"),
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
        )
        self._aspect_check.pack(side="left", padx=(0, 5))

        # --- Row 3: Warning label (hidden by default) ---
        self._size_warning_var = tk.StringVar(value="")
        self._size_warning_label = tk.Label(
            self.frame_size, textvariable=self._size_warning_var,
            anchor="w", font=("", 9),
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
        """Setup drag and drop for input file path entry."""
        try:
            DragAndDropHandler.register_drop_target(
                self._base_file_path_entry,
                self._on_drop_input_file,
                _DROP_EXTENSIONS,
                self._show_status_feedback,
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
        initial_dir = self._get_initial_dir_from_setting("base_file_path")
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U022",
            filetypes=[
                ("Image files", _IMAGE_EXTENSIONS),
                ("PDF files", "*.pdf"),
                ("SVG files", "*.svg"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
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

            # Extension block: input name + output name base
            self._ext_input_name_var.set(name)
            self._ext_output_name_var.set(f"{stem}.")

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
        except Exception as e:
            logger.error(f"Error updating file info: {e}")

    def _update_meta_info(self, file_path: str) -> None:
        """Update the meta info label for the extension block.

        Args:
            file_path: Path to the input file.
        """
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                mode = img.mode
                w, h = img.size
                fmt = img.format or "-"
                dpi = img.info.get("dpi", None)
                dpi_str = f"{int(dpi[0])}x{int(dpi[1])}" if dpi else "-"
                # Localized labels for meta info display
                lbl_fmt = message_manager.get_ui_message("U091")
                lbl_mode = message_manager.get_ui_message("U092")
                lbl_size = message_manager.get_ui_message("U093")
                lbl_icc = message_manager.get_ui_message("U094")
                lbl_exif = message_manager.get_ui_message("U095")
                lbl_avail = message_manager.get_ui_message("U096")
                # Use "-" consistently for absent values
                icc_val = lbl_avail if img.info.get("icc_profile") else "-"
                exif_val = lbl_avail if img.info.get("exif") else "-"
                # Use vertical bar separators for compact readability.
                meta_text = (
                    f"{lbl_fmt}  {fmt}  |  {lbl_mode}  {mode}  |  "
                    f"{lbl_size}  {w}×{h} px  |  "
                    f"DPI :  {dpi_str}  |  {lbl_icc}  {icc_val}  |  {lbl_exif}  {exif_val}"
                )
                self._ext_meta_var.set(meta_text)

                # Update current size in the size block
                self._size_current_var.set(f"{w} px \u00d7 {h} px")

                # Store original dimensions for aspect ratio calculation
                self._orig_width = w
                self._orig_height = h
        except Exception:
            self._ext_meta_var.set("-")
            self._size_current_var.set("- px \u00d7 - px")

    def _on_paper_size_selected(self, event: Any = None) -> None:
        """Handle paper size combobox selection.

        Calculates pixel dimensions from paper mm size and current DPI.

        Args:
            event: Combobox selection event (unused).
        """
        paper_name = self._paper_var.get()
        if paper_name not in self._paper_sizes:
            return

        try:
            dpi = float(self._dpi_var.get() or "72")
        except ValueError:
            dpi = 72.0

        w_mm, h_mm = self._paper_sizes[paper_name]
        # Convert mm to pixels: px = mm * dpi / 25.4
        w_px = int(w_mm * dpi / 25.4)
        h_px = int(h_mm * dpi / 25.4)

        self.width_var.set(str(w_px))
        self.height_var.set(str(h_px))

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
    # Conversion stubs (logic to be implemented in M2-003 / M2-004)
    # ------------------------------------------------------------------
    def _on_ext_convert(self) -> None:
        """Handle extension conversion button click.

        Stub: full logic will be implemented in M2-003.
        """
        self._set_status(message_manager.get_ui_message("U077") + " - not yet implemented")

    def _on_size_convert(self) -> None:
        """Handle size conversion button click.

        Stub: full logic will be implemented in M2-004.
        """
        self._set_status(message_manager.get_ui_message("U090") + " - not yet implemented")

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
