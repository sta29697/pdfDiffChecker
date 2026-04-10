from __future__ import annotations
from io import BytesIO
from logging import getLogger
import math
import shutil
import threading
import time
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from typing import Callable, Optional, Any, List, Dict, Literal
from PIL import Image, ImageTk, ImageFile
from PIL.Image import DecompressionBombError, Resampling, Transpose
from utils.path_dialog_utils import ask_file_dialog, ask_folder_dialog
from utils.path_normalization import normalize_host_path
from utils.workspace_input_formats import (
    MAIN_PDF_OPE_INPUT_EXTENSIONS,
    main_pdf_ope_askopen_filetypes,
    main_pdf_ope_drop_suffixes,
)
from utils.preview_diff_emphasis import build_diff_highlight_overlay_rgba
from utils.transform_tuple import as_transform6, pack_transform6
from utils.utils import (
    create_unique_file_path,
    get_resource_path,
    resolve_initial_dir,
    get_temp_dir,
    show_balloon_message,
)

from configurations.message_manager import get_message_manager
from configurations import tool_settings
from models.class_dictionary import FilePathInfo
from controllers.drag_and_drop_file import DragAndDropHandler
from controllers.file2png_by_page import BaseImageConverter, build_workspace_input_converter
from controllers.pdf_export_handler import PDFExportHandler, apply_color_processing_to_image
from widgets.base_button import BaseButton
from widgets.base_label_class import BaseLabelClass
from widgets.base_path_select_button import BasePathSelectButton
from widgets.base_image_color_change_button import BaseImageColorChangeButton
from widgets.base_sub_graph_window_button import CreateSubGraphWindowButton
from widgets.color_theme_change_button import ColorThemeChangeButton  # type: ignore
from widgets.progress_window import ProgressWindow
from widgets.language_select_combobox import LanguageSelectCombo
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets
from widgets.page_control_frame import PageControlFrame

from configurations.user_setting_manager import UserSettingManager
from controllers.image_sw_paths import ImageSwPaths
from controllers.mouse_event_handler import MouseEventHandler
from controllers.widgets_tracker import WidgetsTracker, adjust_hex_color, ensure_contrast_color, get_hex_color_luminance, resolve_disabled_visual_colors
from widgets.base_path_entry import BasePathEntry
from widgets.base_entry_class import BaseEntryClass
from widgets.base_value_combobox import BaseValueCombobox
from controllers.color_theme_manager import ColorThemeManager

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


from views.main_tab_mixin import _MainTabMixin, WorkspaceRasterTooLarge

# ---------------------------------------------------------------------------
# 図枠 (drawing-frame) detection utilities
# Uses only numpy + PIL so no OpenCV dependency is required.
# ---------------------------------------------------------------------------

from utils.image_alignment import (
    detect_figure_frame_rect as _detect_figure_frame_rect,
    detect_priority_anchor as _detect_priority_anchor,
    detect_content_centroid as _detect_content_centroid,
    compute_frame_align as _compute_frame_align,
    compute_content_align as _compute_content_align,
)

logger = getLogger(__name__)
message_manager = get_message_manager()
_MAIN_TAB_DEFAULT_DPI = 300
_MAIN_TAB_FALLBACK_DPI_CHOICES = [72, 96, 144, 150, 300, 600, 720, 1200, 2400, 3600, 4000]
# Interactive zoom: redraw quickly with bilinear scale, then sharpen with Lanczos after idle.
# (Source PNG is always full-res so canvas geometry matches the stored scale; downsampling
# the source previously made LOD and hi-res frames different sizes and the view "jumped".)
_PREVIEW_HIRES_DEBOUNCE_MS = 200


class CreateComparisonFileApp(tk.Frame, ColoringThemeIF, _MainTabMixin):
    """Main tab of the application for comparing PDF files.

    This class provides the main interface for PDF file comparison functionality.
    It includes UI elements for:
    1. File selection (base and comparison PDFs)
    2. Output folder selection
    3. DPI settings
    4. Page navigation
    5. Theme customization
    6. PDF comparison and analysis

    Attributes:
        root (tk.Widget): Parent widget
        base_widgets (BaseTabWidgets): Base tab widget container
        base_file_obj (Optional[FilePathInfo]): Base PDF file information
        comparison_file_obj (Optional[FilePathInfo]): Comparison PDF file information
        output_folder_obj (Optional[Path]): Output folder path
        base_path (str): Path to base PDF file
        comparison_path (str): Path to comparison PDF file
        output_path (str): Path to output folder
        base_pages (List[fitz.Page]): List of pages from base PDF
        comp_pages (List[fitz.Page]): List of pages from comparison PDF
        selected_dpi_value (int): Selected DPI value for rendering
    """

    # frame_main2: four fixed-width hosts; gutters are columns 1,3,5 (uniform + weight 1).
    # Sum (h0+h2+h4+h6) is fixed (836). Host content uses _MAIN2_HOST_INNER_PAD_X_PX.
    # Host2 spans full width so U146 tint matches the archer column; slightly narrower host4/host6 tighten
    # the DPI→transform segment so the three visual gaps (col0→tint, tint→DPI, DPI→button) read ~1:1:1.
    _MAIN2_HOST0_WIDTH_PX: int = 257
    _MAIN2_HOST2_WIDTH_PX: int = 195
    _MAIN2_HOST4_WIDTH_PX: int = 206
    _MAIN2_HOST6_WIDTH_PX: int = 178
    # Symmetric horizontal inset inside each fixed-width host so inter-column gaps look even.
    _MAIN2_HOST_INNER_PAD_X_PX: int = 6
    # Host6 only: smaller left / matching-sum right grid pad shifts the custom column parcel left so the
    # transform button's side margins match the archer column (uniform gutters + host4 width read as extra left space).
    _MAIN2_HOST6_CUSTOM_COLUMN_PADX_PX: tuple[int, int] = (0, 12)
    # Fixed preview surface so thin vector strokes stay readable in every app theme.
    _PREVIEW_CANVAS_BACKGROUND: str = "#ffffff"
    # Historical DEFAULT_USER_SET placeholder before localized U053/U054 tokens.
    _LEGACY_SETTINGS_PLACEHOLDER_JA: str = "直接入力、参照選択"

    def __init__(
        self, master: tk.Misc, settings: UserSettingManager
    ) -> None:
        """Initialize the main comparison tab.

        Args:
            master (tk.Misc): Parent window
            settings (UserSettingManager): Application settings
        """
        # Init main tab class
        logger.debug(message_manager.get_log_message("L243"))
        super().__init__(master)
        WidgetsTracker().add_widgets(self)
        self.settings = settings
        self.master = master
        self.file_operation_status: bool = True
        self.selected_dpi_value: int = self._get_selected_dpi()
        self.base_widgets = BaseTabWidgets(self)
        self.status_var = tk.StringVar(value="")
        self.base_path = tk.StringVar(value=message_manager.get_ui_message("U053"))
        self.comparison_path = tk.StringVar(value=message_manager.get_ui_message("U053"))
        self.output_path = tk.StringVar(value=message_manager.get_ui_message("U054"))
        saved_threshold_default = int(self.settings.get_setting("separat_color_threshold", 700))
        self._base_threshold_value_var = tk.IntVar(
            value=int(self.settings.get_setting("base_separat_color_threshold", saved_threshold_default))
        )
        self._comparison_threshold_value_var = tk.IntVar(
            value=int(self.settings.get_setting("comparison_separat_color_threshold", saved_threshold_default))
        )
        self.visualized_image = tk.StringVar(value="base")
        self.current_page_index = 0
        self._base_preferred_preview_scale = self._get_saved_preview_scale("base")
        self._comp_preferred_preview_scale = self._get_saved_preview_scale("comp")
        self._show_base_layer_var = tk.BooleanVar(
            value=self._get_saved_boolean_setting("show_base_layer", True)
        )
        self._show_comp_layer_var = tk.BooleanVar(
            value=self._get_saved_boolean_setting("show_comp_layer", True)
        )
        self._show_reference_grid_var = tk.BooleanVar(
            value=self._get_saved_boolean_setting("show_reference_grid", False)
        )
        self.page_count = 0
        self.base_pages: List[str] = []
        self.comp_pages: List[str] = []
        self.base_transform_data: List[tuple[float, float, float, float]] = []
        self.comp_transform_data: List[tuple[float, float, float, float]] = []
        self._base_export_transform_overrides: List[Dict[str, float]] = []
        self._comp_export_transform_overrides: List[Dict[str, float]] = []
        self.page_control_frame: Optional[PageControlFrame] = None
        self._page_ctrl_scroll_outer: Optional[tk.Frame] = None
        self._page_ctrl_viewport: Optional[tk.Canvas] = None
        self._page_ctrl_vbar: Optional[tk.Scrollbar] = None
        self._page_ctrl_inner: Optional[tk.Frame] = None
        self._page_ctrl_window_id: Optional[int] = None
        self.mouse_handler: Optional[MouseEventHandler] = None
        self.photo_image: Optional[tk.PhotoImage] = None
        self._base_photo_image: Optional[ImageTk.PhotoImage] = None
        self._comp_photo_image: Optional[ImageTk.PhotoImage] = None
        self._base_canvas_image_id: Optional[int] = None
        self._comp_canvas_image_id: Optional[int] = None
        self._automatic_execute_button: Optional[tk.Button] = None
        self._custom_execute_button: Optional[tk.Button] = None
        self._base_file_analyze_btn: Optional[CreateSubGraphWindowButton] = None
        self._comparison_file_analyze_btn: Optional[CreateSubGraphWindowButton] = None
        self._automatic_button_images: Dict[str, ImageTk.PhotoImage] = {}
        self._custom_button_images: Dict[str, ImageTk.PhotoImage] = {}
        self._visual_adjustments_enabled = False
        self._copy_protected = False
        self._conversion_dpi = self._get_selected_dpi()
        self._last_preview_ok_dpi: int = _MAIN_TAB_DEFAULT_DPI
        self._workspace_preview_blocked: bool = False
        self._workspace_raster_limit_dialog_shown: bool = False
        self._preview_hires_after_id: Optional[str] = None
        self._diff_src_overlay_cache: dict = {}
        self._diff_overlay_cache_lock = threading.Lock()
        self._diff_overlay_bg_key: Optional[tuple] = None
        self._batch_edit_selected = True
        self._selected_color_processing_mode = self._normalize_color_processing_mode(
            str(self.settings.get_setting("color_processing_mode", "指定色濃淡") or "指定色濃淡")
        )
        self._color_processing_mode_var = tk.StringVar(
            value=self._get_color_processing_mode_display_text(self._selected_color_processing_mode)
        )
        self._base_selected_color_hex: Optional[str] = None
        self._comparison_selected_color_hex: Optional[str] = None
        self.base_page_paths: List[Path] = []
        self.comp_page_paths: List[Path] = []
        self._base_page_records: List[Dict[str, Any]] = []
        self._comp_page_records: List[Dict[str, Any]] = []
        self._base_workspace_dir: Optional[Path] = None
        self._comp_workspace_dir: Optional[Path] = None
        self.base_file_info: Optional[FilePathInfo] = None
        self.comp_file_info: Optional[FilePathInfo] = None
        self.base_pdf_metadata: Dict[str, Any] = {}
        self.comp_pdf_metadata: Dict[str, Any] = {}
        self.base_pdf_converter: Optional[BaseImageConverter] = None
        self.comp_pdf_converter: Optional[BaseImageConverter] = None
        self._dpi_combo: Optional[BaseValueCombobox] = None
        self._dpi_choice_var = tk.StringVar(value=str(self.selected_dpi_value))
        self._detected_dpi_value: Optional[int] = None
        self._preview_source_image_cache: Dict[tuple[str, str, int, int], Image.Image] = {}
        self._preview_processed_image_cache: Dict[tuple[str, str, int, int, str, str, int], Image.Image] = {}
        self._preview_render_generation = 0
        self._background_preview_render_thread: Optional[threading.Thread] = None
        self._base_preview_render_lock = threading.Lock()
        self._comp_preview_render_lock = threading.Lock()
        self._last_translation_aux_update_time = 0.0
        self._translation_aux_update_interval_seconds = 1.0 / 30.0
        self._preview_keyboard_rotation_delta: float = 0.0
        self._diff_emphasis_var = tk.BooleanVar(value=False)
        self._diff_emphasis_photo_image: Optional[ImageTk.PhotoImage] = None
        self._diff_emphasis_canvas_image_id: Optional[int] = None
        # Last successful canvas draw: (page_index, show_base, show_comp) for LOD in-place updates.
        self._preview_canvas_snap: Optional[tuple[int, bool, bool]] = None
        # Workspace identity after last successful load; avoids full rebuild on tab <Visibility>.
        self._workspace_paths_signature_cache: Optional[tuple[str, str]] = None

        # Button images
        self.auto_conv_btn_img: Optional[ImageSwPaths] = None
        self.custom_conv_btn_img: Optional[ImageSwPaths] = None
        self.move_start_page_btn_img: Optional[ImageSwPaths] = None
        self.move_prev_page_btn_img: Optional[ImageSwPaths] = None
        self.move_next_page_btn_img: Optional[ImageSwPaths] = None
        self.move_end_page_btn_img: Optional[ImageSwPaths] = None
        self._current_custom_button_state = "off"
        self._action_button_square_size = 120
        self._action_button_active_delay_ms = 420
        # After dialog/drop/Enter the entry shows the full PDF path; until then only the parent folder.
        self._base_pdf_session_committed: bool = False
        self._comparison_pdf_session_committed: bool = False
        self._shortcut_guide_en_row1: Optional[tk.Frame] = None
        self._shortcut_guide_en_l1_left: Optional[tk.Label] = None
        self._shortcut_guide_en_spacer: Optional[tk.Frame] = None
        self._shortcut_guide_en_l1_right: Optional[tk.Label] = None
        self._shortcut_guide_en_line2: Optional[tk.Label] = None

        # Setup UI components
        self._setup_frames()
        self._setup_widgets()
        self._setup_drag_and_drop()
        self._restore_analysis_panel_state()
        self.bind("<Visibility>", self._sync_shared_paths_from_settings)
        self.after_idle(self._sync_shared_paths_from_settings)
        self.after_idle(self._apply_current_theme_after_build)
        # Completed main tab init
        logger.debug(message_manager.get_log_message("L244"))

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Configure widget-specific theme settings.

        Args:
            theme_settings: Theme settings for the main comparison canvas.
        """
        if hasattr(self, "canvas"):
            self.canvas.configure(
                background=CreateComparisonFileApp._PREVIEW_CANVAS_BACKGROUND,
                highlightbackground=theme_settings.get("highlightbackground", "#e0e0e0"),
                highlightcolor=theme_settings.get("highlightcolor", "#e0e0e0"),
            )

    def apply_theme_color(self, theme_data: Dict[str, Any]) -> None:
        """Apply theme to this tab and its widgets.

        Args:
            theme_data: Theme data obtained from the current theme manager.
        """
        window_settings = theme_data.get("Window", {})
        window_bg = window_settings.get("bg", "#ffffff")
        frame_settings = theme_data.get("Frame", {})
        frame_bg = frame_settings.get("bg", window_bg)
        frame_fg = frame_settings.get("fg", "#000000")

        self.configure(bg=frame_bg)
        for attr_name in [
            "frame_main0",
            "frame_main1",
            "frame_main2",
            "frame_main3",
            "_row4_fixed_col0_host",
            "_row4_fixed_col2_host",
            "_row4_fixed_col4_host",
            "_row4_fixed_col6_host",
            "_row4_comment_frame",
            "_row4_auto_column_frame",
            "_row4_arrow_frame",
            "_row4_action_frame",
            "_row4_custom_column_frame",
            "_row4_custom_frame",
            "_dpi_row_frame",
            "_layer_toggle_frame",
            "_row4_custom_guidance_frame",
            "_shortcut_guide_frame",
        ]:
            frame = getattr(self, attr_name, None)
            if frame is not None:
                frame.configure(
                    bg=frame_bg,
                    relief=tk.FLAT,
                    borderwidth=0,
                    highlightthickness=0,
                )

        process_button_theme = dict(theme_data.get("process_button", {}))
        elevated_process_style = self._build_elevated_button_style(
            process_button_theme,
            frame_bg,
            frame_fg,
        )

        notebook_settings = theme_data.get("Notebook", {})
        canvas_theme = theme_data.get("canvas", {})
        canvas_background = notebook_settings.get("tab_bg", notebook_settings.get("bg", frame_bg))
        self._config_widget(
            {
                "background": canvas_theme.get("background", canvas_background),
                "highlightbackground": canvas_theme.get("highlightbackground", frame_bg),
                "highlightcolor": canvas_theme.get("highlightcolor", frame_fg),
            }
        )

        if process_button_theme:
            for action_button in [
                getattr(self, "_automatic_execute_button", None),
                getattr(self, "_custom_execute_button", None),
            ]:
                if action_button is not None:
                    action_button.configure(**elevated_process_style)
            self._refresh_action_button_image_cache()

        self._apply_path_entry_activity_style(theme_data)
        self._apply_layer_toggle_theme(theme_data)

        # Apply theme to analysis panel collapse button
        collapse_btn = getattr(self, "_collapse_btn", None)
        if collapse_btn is not None:
            try:
                btn_theme = theme_data.get("Button", {})
                collapse_btn.configure(
                    bg=btn_theme.get("bg", frame_bg),
                    fg=btn_theme.get("fg", frame_fg),
                    activebackground=btn_theme.get("activebackground", frame_bg),
                    activeforeground=btn_theme.get("activeforeground", frame_fg),
                )
            except Exception:
                pass

        comment_panel_theme = dict(theme_data.get("create_fb_threshold_set_label", {}))
        comment_panel_bg = str(comment_panel_theme.get("bg", frame_bg))
        comment_panel_fg = str(comment_panel_theme.get("fg", frame_fg))
        comment_frame = getattr(self, "_row4_comment_frame", None)
        if comment_frame is not None:
            try:
                comment_frame.configure(bg=comment_panel_bg)
            except Exception:
                pass

        comment_label = getattr(self, "_row4_comment_text_label", None)
        if comment_label is not None:
            try:
                comment_label.configure(bg=comment_panel_bg, fg=comment_panel_fg)
            except Exception:
                pass

        for attr_name in [
            "_row4_arrow_guidance_frame",
        ]:
            guidance_frame = getattr(self, attr_name, None)
            if guidance_frame is not None:
                try:
                    guidance_frame.configure(bg=comment_panel_bg)
                except Exception:
                    pass

        # U147: only the tight inner band uses the comment-panel tint; the outer row stays frame_bg.
        inner_u147 = getattr(self, "_row4_custom_guidance_inner", None)
        if inner_u147 is not None:
            try:
                inner_u147.configure(bg=comment_panel_bg)
            except Exception:
                pass

        shortcut_guide_label = getattr(self, "_shortcut_guide_label", None)
        if shortcut_guide_label is not None:
            try:
                shortcut_guide_label.configure(bg=frame_bg, fg=frame_fg)
            except Exception:
                pass

        for attr_name in [
            "_row4_custom_guidance_label",
        ]:
            guidance_label = getattr(self, attr_name, None)
            if guidance_label is not None:
                try:
                    guidance_label.configure(bg=comment_panel_bg, fg=comment_panel_fg)
                except Exception:
                    pass

        for attr_name in [
            "_row4_action_frame",
            "_color_mode_label_row_frame",
            "_color_combo_only_row_frame",
            "_dpi_row_frame",
            "_dpi_combo_holder",
        ]:
            frame = getattr(self, attr_name, None)
            if frame is not None:
                try:
                    frame.configure(bg=frame_bg)
                except Exception:
                    pass

        threshold_summary_frame = getattr(self, "_threshold_summary_frame", None)
        if threshold_summary_frame is not None:
            try:
                threshold_summary_frame.configure(bg=comment_panel_bg)
            except Exception:
                pass

        for attr_name in [
            "_color_mode_label",
            "_threshold_summary_label",
            "_base_threshold_inline_label",
            "_comparison_threshold_inline_label",
            "_row4_arrow_guidance_label",
        ]:
            label = getattr(self, attr_name, None)
            if label is not None:
                try:
                    label.configure(bg=comment_panel_bg, fg=comment_panel_fg)
                except Exception:
                    pass

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.apply_theme_color(theme_data)
            except Exception:
                pass

        if hasattr(self, "canvas"):
            try:
                self._draw_canvas_footer_guide()
                self._draw_reference_grid(self.canvas.bbox("pdf_image"), raise_above_images=self._has_loaded_workspace_pages())
            except Exception:
                pass

        self._refresh_interaction_state(theme_data)

    def _apply_current_theme_after_build(self) -> None:
        """Apply the current theme after all child widgets are created."""
        self._refresh_localized_main_tab_text()
        self.apply_theme_color(ColorThemeManager.get_instance().get_current_theme())

    def _apply_path_entry_activity_style(self, theme_data: Optional[Dict[str, Any]] = None) -> None:
        """Apply theme-aware active or inactive styling to path entries.

        Args:
            theme_data: Optional current theme snapshot.
        """
        current_theme = theme_data or ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        label_disabled_theme = dict(current_theme.get("LabelDisabled", {}))

        def _configure_entry(entry_attr: str, color_key: str, is_active: bool) -> None:
            entry_widget = getattr(self, entry_attr, None)
            if entry_widget is None or not hasattr(entry_widget, "path_entry"):
                return

            path_entry = entry_widget.path_entry
            entry_theme = dict(current_theme.get(color_key, current_theme.get("create_path_entry", {})))
            entry_bg = str(entry_theme.get("bg", frame_theme.get("bg", "#ffffff")))
            entry_fg = str(entry_theme.get("fg", frame_theme.get("fg", "#000000")))
            highlight_bg = str(entry_theme.get("highlightbackground", entry_bg))
            highlight_fg = str(entry_theme.get("highlightcolor", entry_fg))

            try:
                if is_active:
                    path_entry.configure(
                        state="normal",
                        bg=entry_bg,
                        fg=entry_fg,
                        insertbackground=entry_theme.get("insertbackground", entry_fg),
                        highlightbackground=highlight_bg,
                        highlightcolor=highlight_fg,
                        disabledbackground=entry_bg,
                        disabledforeground=entry_fg,
                        readonlybackground=entry_bg,
                    )
                    return

                luminance = get_hex_color_luminance(entry_bg)
                inactive_bg = adjust_hex_color(entry_bg, 0.32 if luminance < 0.5 else -0.22)
                if str(inactive_bg).strip().lower() == str(entry_bg).strip().lower():
                    inactive_bg = adjust_hex_color(
                        str(frame_theme.get("bg", entry_bg)),
                        0.24 if get_hex_color_luminance(str(frame_theme.get("bg", entry_bg))) < 0.5 else -0.14,
                    )
                inactive_fg_candidate = str(
                    label_disabled_theme.get(
                        "fg",
                        frame_theme.get("disabledforeground", entry_fg),
                    )
                )
                neutral_inactive_fg = adjust_hex_color(
                    inactive_bg,
                    0.58 if get_hex_color_luminance(inactive_bg) < 0.5 else -0.52,
                )
                inactive_fg = ensure_contrast_color(
                    neutral_inactive_fg or inactive_fg_candidate,
                    inactive_bg,
                    0.42,
                )
                path_entry.configure(
                    state="readonly",
                    bg=inactive_bg,
                    fg=inactive_fg,
                    insertbackground=inactive_fg,
                    highlightbackground=str(frame_theme.get("bg", inactive_bg)),
                    highlightcolor=inactive_fg,
                    disabledbackground=inactive_bg,
                    disabledforeground=inactive_fg,
                    readonlybackground=inactive_bg,
                )
            except Exception:
                pass

        _configure_entry("_base_file_path_entry", "base_file_path_entry", self._path_points_to_file(self.base_path.get()))
        _configure_entry(
            "_comparison_file_path_entry",
            "comparison_file_path_entry",
            self._path_points_to_file(self.comparison_path.get()),
        )
        _configure_entry("_output_folder_path_entry", "output_folder_path_entry", True)

    def _build_elevated_button_style(
        self,
        button_theme: Dict[str, Any],
        frame_bg: str,
        frame_fg: str,
    ) -> Dict[str, Any]:
        """Build a button style that matches the sub-graph analyze button affordance.

        Args:
            button_theme: Theme settings for the target button.
            frame_bg: Background color of the surrounding frame.
            frame_fg: Default foreground color for the surrounding frame.

        Returns:
            Dict[str, Any]: Tkinter button configuration for a raised surface.
        """
        button_bg = str(button_theme.get("bg", frame_bg))
        active_bg = str(button_theme.get("activebackground", button_bg))
        border_color = active_bg if active_bg else button_bg

        if button_bg.startswith("#") and button_bg.strip().lower() == str(frame_bg).strip().lower():
            button_bg = adjust_hex_color(button_bg, 0.06)

        return {
            "bg": button_bg,
            "fg": button_theme.get("fg", frame_fg),
            "activebackground": active_bg,
            "activeforeground": button_theme.get("activeforeground", button_theme.get("fg", frame_fg)),
            "relief": tk.RAISED,
            "bd": 2,
            "highlightthickness": 1,
            "highlightbackground": border_color,
            "highlightcolor": border_color,
        }

    def _resolve_main_button_theme(self, theme_data: Dict[str, Any], theme_key: str) -> Dict[str, Any]:
        """Resolve a button theme with the same fallback behavior as the reference button.

        Args:
            theme_data: Current theme snapshot.
            theme_key: Theme key for the target button.

        Returns:
            Resolved theme dictionary containing at least stable foreground/background values.
        """
        button_theme = dict(theme_data.get(theme_key, {}))
        if "bg" not in button_theme or "fg" not in button_theme:
            fallback_theme = dict(theme_data.get("process_button", theme_data.get("Button", {})))
            fallback_theme.update(button_theme)
            button_theme = fallback_theme
        return button_theme

    def _apply_main_button_state(
        self,
        button: Optional[tk.Button],
        *,
        enabled: bool,
        theme_key: str,
        theme_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Apply enabled or disabled visuals to a main-tab button.

        Args:
            button: Target button widget.
            enabled: Whether the button should be interactive.
            theme_key: Theme key for the target button.
            theme_data: Optional current theme snapshot.
        """
        if button is None:
            return

        current_theme = theme_data or ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        frame_bg = str(frame_theme.get("bg", "#ffffff"))
        frame_fg = str(frame_theme.get("fg", "#000000"))
        label_disabled_theme = dict(current_theme.get("LabelDisabled", {}))
        button_theme = self._resolve_main_button_theme(current_theme, theme_key)
        elevated_style = self._build_elevated_button_style(button_theme, frame_bg, frame_fg)
        disabled_visuals = resolve_disabled_visual_colors(
            str(button_theme.get("bg", frame_bg)),
            str(label_disabled_theme.get("fg", frame_theme.get("disabledforeground", button_theme.get("fg", frame_fg)))),
            fallback_bg=frame_bg,
            use_emphasis_surface=True,
        )
        disabled_bg = str(disabled_visuals.get("disabled_bg", frame_bg))
        disabled_fg = str(disabled_visuals.get("disabled_fg", frame_fg))

        try:
            if enabled:
                if hasattr(button, "_disabled_visual_bg"):
                    setattr(button, "_disabled_visual_bg", disabled_bg)
                if hasattr(button, "_disabled_visual_fg"):
                    setattr(button, "_disabled_visual_fg", disabled_fg)
                button.configure(
                    state=tk.NORMAL,
                    disabledforeground=disabled_fg,
                    **elevated_style,
                )
                return

            if hasattr(button, "_disabled_visual_bg"):
                setattr(button, "_disabled_visual_bg", disabled_bg)
            if hasattr(button, "_disabled_visual_fg"):
                setattr(button, "_disabled_visual_fg", disabled_fg)
            button.configure(
                state=tk.DISABLED,
                bg=disabled_bg,
                fg=disabled_fg,
                activebackground=disabled_bg,
                activeforeground=disabled_fg,
                disabledforeground=disabled_fg,
                relief=tk.RAISED,
                bd=2,
                highlightthickness=1,
                highlightbackground=frame_bg,
                highlightcolor=frame_bg,
            )
        except Exception:
            pass

    def _apply_main_entry_state(
        self,
        entry: Optional[tk.Entry],
        *,
        enabled: bool,
        theme_key: str,
        theme_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Apply enabled or disabled visuals to a main-tab entry widget.

        Args:
            entry: Target entry widget.
            enabled: Whether the entry should accept input.
            theme_key: Theme key for the target entry.
            theme_data: Optional current theme snapshot.
        """
        if entry is None:
            return

        current_theme = theme_data or ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        entry_theme = dict(current_theme.get(theme_key, current_theme.get("dpi_entry", {})))
        entry_bg = str(entry_theme.get("bg", frame_theme.get("bg", "#ffffff")))
        entry_fg = str(entry_theme.get("fg", frame_theme.get("fg", "#000000")))
        disabled_visuals = resolve_disabled_visual_colors(
            entry_bg,
            str(current_theme.get("LabelDisabled", {}).get("fg", frame_theme.get("disabledforeground", entry_fg))),
            fallback_bg=str(frame_theme.get("bg", entry_bg)),
            use_emphasis_surface=True,
        )
        disabled_bg = str(disabled_visuals.get("disabled_bg", entry_bg))
        disabled_fg = str(disabled_visuals.get("disabled_fg", entry_fg))

        try:
            entry.configure(
                state=tk.NORMAL if enabled else tk.DISABLED,
                bg=entry_bg if enabled else disabled_bg,
                fg=entry_fg if enabled else disabled_fg,
                insertbackground=entry_fg if enabled else disabled_fg,
                disabledbackground=disabled_bg,
                disabledforeground=disabled_fg,
                readonlybackground=disabled_bg,
            )
        except Exception:
            pass

    def _apply_main_combobox_state(
        self,
        combobox: Optional[BaseValueCombobox],
        *,
        enabled: bool,
    ) -> None:
        """Apply enabled or disabled state to a readonly combobox.

        Args:
            combobox: Target combobox widget.
            enabled: Whether the combobox should accept selection changes.
        """
        if combobox is None:
            return

        try:
            combobox.configure(state="readonly" if enabled else "disabled")
        except Exception:
            pass

    def _should_enable_batch_edit(self) -> bool:
        """Return whether batch edit should be available for the current workspace.

        Returns:
            ``True`` when either side has multiple pages and editing is allowed.
        """
        return (not self._copy_protected) and (
            len(self.base_page_paths) > 1 or len(self.comp_page_paths) > 1
        )

    def _sync_batch_edit_state(self) -> None:
        """Apply batch edit availability and restore the stored check state."""
        if self.page_control_frame is None:
            return

        batch_edit_enabled = self._should_enable_batch_edit()
        self.page_control_frame.set_batch_edit_enabled(batch_edit_enabled)
        if batch_edit_enabled:
            self.page_control_frame.set_batch_edit_checked(self._batch_edit_selected)

    def _propagate_current_transform_to_all_pages(self, *, visible_only: bool) -> None:
        """Copy the current page transform to every page when batch edit is active.

        Args:
            visible_only: Whether propagation should be limited to visible layers.
        """
        if self.page_control_frame is None or not self.page_control_frame.is_batch_edit_checked():
            return

        layer_targets = [
            (self.base_transform_data, bool(self._show_base_layer_var.get()) or not visible_only),
            (self.comp_transform_data, bool(self._show_comp_layer_var.get()) or not visible_only),
        ]
        for transform_data, should_apply in layer_targets:
            if not should_apply or not transform_data or self.current_page_index >= len(transform_data):
                continue
            current_transform = transform_data[self.current_page_index]
            for index in range(len(transform_data)):
                if index != self.current_page_index:
                    transform_data[index] = current_transform

    def _can_main_sheet_rotate_dual_display(self) -> bool:
        """Return True when Ctrl+Alt sheet rotation is allowed on the main tab.

        Sheet rotation is defined for the comparison workspace and requires both
        PDFs loaded with both layers shown.

        Returns:
            True if both sides are active; otherwise False.
        """
        if not self._has_loaded_workspace_pages():
            return False
        if not self.base_page_paths or not self.comp_page_paths:
            return False
        if not bool(self._show_base_layer_var.get()) or not bool(self._show_comp_layer_var.get()):
            return False
        return True

    def _get_visible_layer_state(self) -> dict[int, bool]:
        """Return the currently visible layer state for the workspace.

        Returns:
            Visibility dictionary keyed by layer ID.
        """
        visible_layers: dict[int, bool] = {}
        if self.base_page_paths and bool(self._show_base_layer_var.get()):
            visible_layers[0] = True
        if self.comp_page_paths and bool(self._show_comp_layer_var.get()):
            visible_layers[1] = True
        return visible_layers

    def _run_blocking_preview_progress(self, status_text: str, work: Callable[[], None]) -> None:
        """Show a modal progress window while running a short main-thread preview task.

        Args:
            status_text: Label shown above the progress bar.
            work: Zero-argument callable (typically redraws the canvas).
        """
        root = self.winfo_toplevel()
        progress_window = ProgressWindow(root)
        try:
            progress_window.show()
            progress_window.update_progress(10, status_text)
            try:
                root.update_idletasks()
            except Exception:
                pass
            work()
            done_text = message_manager.get_ui_message("U186")
            progress_window.update_progress(100, done_text)
            try:
                root.update_idletasks()
            except Exception:
                pass
        finally:
            progress_window.hide()
            try:
                progress_window.destroy()
            except Exception:
                pass

    def _refresh_current_page_view(self, *, show_progress: bool = False) -> None:
        """Refresh the page-control and canvas view for the current page.

        Args:
            show_progress: When True and a workspace is loaded, show a progress bar
                while rebuilding the canvas (page navigation).
        """
        self._cancel_pending_hi_res_preview()
        self._apply_preferred_preview_scale_to_page(self.current_page_index)
        if self.mouse_handler is not None:
            visible_layers = self._get_visible_layer_state()
            self.mouse_handler.update_state(
                current_page_index=self.current_page_index,
                visible_layers=visible_layers,
            )
            if hasattr(self.mouse_handler, "refresh_overlay_positions"):
                self.mouse_handler.refresh_overlay_positions()

        if self._has_loaded_workspace_pages():
            if show_progress:
                self._run_blocking_preview_progress(
                    message_manager.get_ui_message("U182"),
                    lambda: self._display_page(self.current_page_index),
                )
            else:
                self._display_page(self.current_page_index)
            return

        if self.page_control_frame is not None:
            self.page_control_frame.update_page_label(
                self.page_count - 1 if self.page_count == 0 else self.current_page_index,
                self.page_count,
            )
            self._sync_transform_display_to_panel()
        self._render_comparison_placeholder()

    def _main_canvas_viewport_center_canvas_coords(self) -> Optional[tuple[float, float]]:
        """Return the center of the visible canvas viewport in canvas coordinates.

        Matches :meth:`MouseEventHandler._get_visible_origin` plus half the widget
        size, used as the zoom pivot when the user changes scale via numeric entry.

        Returns:
            ``(cx, cy)`` in canvas space, or ``None`` if the canvas is unavailable
            or not yet laid out.
        """
        if not hasattr(self, "canvas"):
            return None
        try:
            self.canvas.update_idletasks()
            w = int(self.canvas.winfo_width())
            h = int(self.canvas.winfo_height())
            if w <= 1 or h <= 1:
                return None
            x0 = float(self.canvas.canvasx(0))
            y0 = float(self.canvas.canvasy(0))
            return (x0 + w * 0.5, y0 + h * 0.5)
        except tk.TclError:
            return None

    def _update_canvas_translation_preview(self) -> None:
        """Update only canvas image coordinates during drag translation.

        This avoids rebuilding PIL images on every mouse move while still keeping
        the visible page position and transform panel in sync.
        """
        if not self._has_loaded_workspace_pages():
            return
        if not (0 <= self.current_page_index < self.page_count):
            return

        if self._base_canvas_image_id is not None and self.current_page_index < len(self.base_transform_data):
            _rotation, translate_x, translate_y, _scale, _fh, _fv = as_transform6(
                self.base_transform_data[self.current_page_index]
            )
            try:
                self.canvas.coords(self._base_canvas_image_id, int(translate_x), int(translate_y))
            except Exception:
                pass

        if self._comp_canvas_image_id is not None and self.current_page_index < len(self.comp_transform_data):
            _rotation, translate_x, translate_y, _scale, _fh, _fv = as_transform6(
                self.comp_transform_data[self.current_page_index]
            )
            try:
                self.canvas.coords(self._comp_canvas_image_id, int(translate_x), int(translate_y))
            except Exception:
                pass

        if (
            self._diff_emphasis_canvas_image_id is not None
            and bool(self._diff_emphasis_var.get())
            and self.current_page_index < len(self.base_transform_data)
            and self.current_page_index < len(self.comp_transform_data)
        ):
            ox, oy = self._diff_overlay_canvas_origin(self.current_page_index)
            try:
                self.canvas.coords(self._diff_emphasis_canvas_image_id, ox, oy)
            except Exception:
                pass

        current_time = time.monotonic()
        should_refresh_auxiliary = (
            current_time - self._last_translation_aux_update_time
        ) >= self._translation_aux_update_interval_seconds
        if not should_refresh_auxiliary:
            return

        self._last_translation_aux_update_time = current_time

        try:
            self._set_main_canvas_scrollregion_from_pdf_image()
        except Exception:
            pass

        self._reposition_canvas_footer_guide()

        if self.mouse_handler is not None and hasattr(self.mouse_handler, "refresh_overlay_positions"):
            self.mouse_handler.refresh_overlay_positions()

        if self.page_control_frame is not None:
            self._sync_transform_display_to_panel()

    def _on_batch_edit_toggle(self, checked: bool) -> None:
        """Store the user's batch edit preference.

        Args:
            checked: Latest checkbox state from the page control frame.
        """
        self._batch_edit_selected = bool(checked)

    def _get_saved_preview_scale(self, side: str = "base") -> float:
        """Return the persisted preview scale for the given layer.

        Args:
            side: ``"base"`` or ``"comp"``.

        Returns:
            Preview scale factor.
        """
        key = "base_preview_scale" if side == "base" else "comp_preview_scale"
        raw_scale = self.settings.get_setting(key, self.settings.get_setting("preview_scale", 1.0))
        try:
            resolved_scale = float(raw_scale)
        except (TypeError, ValueError):
            return 1.0
        if resolved_scale <= 0:
            return 1.0
        return resolved_scale

    def _get_saved_boolean_setting(self, key: str, default_value: bool) -> bool:
        """Return a persisted boolean setting using tolerant coercion.

        Args:
            key: Setting key to read.
            default_value: Fallback boolean value.

        Returns:
            bool: Resolved boolean value.
        """
        raw_value = self.settings.get_setting(key, default_value)
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        try:
            return bool(int(raw_value))
        except Exception:
            return bool(default_value)

    def _persist_base_preview_scale(self, scale_value: float) -> None:
        """Persist the preferred base-layer preview scale when it changes.

        Args:
            scale_value: Preview scale factor to save.
        """
        resolved_scale = max(0.05, min(10.0, float(scale_value)))
        if abs(resolved_scale - self._base_preferred_preview_scale) < 1e-6:
            return
        self._base_preferred_preview_scale = resolved_scale
        self.settings.update_setting("base_preview_scale", resolved_scale)

    def _persist_comp_preview_scale(self, scale_value: float) -> None:
        """Persist the preferred comp-layer preview scale when it changes.

        Args:
            scale_value: Preview scale factor to save.
        """
        resolved_scale = max(0.05, min(10.0, float(scale_value)))
        if abs(resolved_scale - self._comp_preferred_preview_scale) < 1e-6:
            return
        self._comp_preferred_preview_scale = resolved_scale
        self.settings.update_setting("comp_preview_scale", resolved_scale)

    def _apply_preferred_preview_scale_to_page(self, page_index: int) -> None:
        """Apply the persisted preview scale to the target page transforms.

        Each layer uses its own preferred scale so base and comp can differ.

        Args:
            page_index: Zero-based page index.
        """
        if self.base_transform_data and 0 <= page_index < len(self.base_transform_data):
            r, tx, ty, _scale, fh, fv = as_transform6(self.base_transform_data[page_index])
            self.base_transform_data[page_index] = pack_transform6(
                r, tx, ty, self._base_preferred_preview_scale, fh, fv
            )
        if self.comp_transform_data and 0 <= page_index < len(self.comp_transform_data):
            r, tx, ty, _scale, fh, fv = as_transform6(self.comp_transform_data[page_index])
            self.comp_transform_data[page_index] = pack_transform6(
                r, tx, ty, self._comp_preferred_preview_scale, fh, fv
            )

    def _update_preferred_preview_scale_from_current_page(self) -> None:
        """Refresh the persisted preview scales from the currently displayed page."""
        idx = self.current_page_index
        if self.base_transform_data and idx < len(self.base_transform_data):
            _r, _tx, _ty, base_scale, _fh, _fv = as_transform6(self.base_transform_data[idx])
            self._persist_base_preview_scale(base_scale)
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            _r, _tx, _ty, comp_scale, _fh, _fv = as_transform6(self.comp_transform_data[idx])
            self._persist_comp_preview_scale(comp_scale)

    @staticmethod
    def _normalize_color_processing_mode(raw_mode: str) -> str:
        """Normalize stored color-processing values to canonical internal names.

        Args:
            raw_mode: Raw persisted or displayed mode text.

        Returns:
            Canonical internal mode name.
        """
        normalized = str(raw_mode or "").strip().lower()
        if normalized in {"二色化", "binarization", "binary", "two-tone"}:
            return "二色化"
        if normalized in {
            "指定色濃淡",
            "color shading",
            "selected color shading",
            "tinted monochrome",
            "グレースケール化",
            "grayscale",
        }:
            return "指定色濃淡"
        return "指定色濃淡"

    def _get_color_processing_mode_display_text(self, canonical_mode: str) -> str:
        """Return the localized combobox label for a canonical color mode.

        Args:
            canonical_mode: Internal canonical color mode.

        Returns:
            Localized display text.
        """
        if self._normalize_color_processing_mode(canonical_mode) == "二色化":
            return message_manager.get_ui_message("U139")
        return message_manager.get_ui_message("U138")

    def _get_color_processing_mode_display_values(self) -> List[str]:
        """Return localized combobox choices for color processing.

        Returns:
            List of localized display labels.
        """
        return [
            message_manager.get_ui_message("U138"),
            message_manager.get_ui_message("U139"),
        ]

    def _resolve_color_processing_mode_from_display(self, display_value: str) -> str:
        """Resolve a localized combobox label to the canonical internal mode.

        Args:
            display_value: Localized combobox text.

        Returns:
            Canonical internal mode name.
        """
        normalized = self._normalize_color_processing_mode(display_value)
        if normalized == "二色化":
            return "二色化"
        if str(display_value).strip() == message_manager.get_ui_message("U139"):
            return "二色化"
        return "指定色濃淡"

    def _refresh_localized_main_tab_text(self) -> None:
        """Refresh language-dependent labels inside the main comparison controls."""
        if getattr(self, "_color_mode_label", None) is not None:
            self._color_mode_label.configure(text=message_manager.get_ui_message("U136"))
        if getattr(self, "_threshold_summary_label", None) is not None:
            self._threshold_summary_label.configure(text=message_manager.get_ui_message("U142"))
        if getattr(self, "_base_threshold_inline_label", None) is not None:
            self._base_threshold_inline_label.configure(text=message_manager.get_ui_message("U143"))
        if getattr(self, "_comparison_threshold_inline_label", None) is not None:
            self._comparison_threshold_inline_label.configure(
                text=message_manager.get_ui_message("U176")
            )
        if getattr(self, "_row4_arrow_guidance_label", None) is not None:
            self._row4_arrow_guidance_label.configure(text=message_manager.get_ui_message("U146"))
        if getattr(self, "_row4_custom_guidance_label", None) is not None:
            self._row4_custom_guidance_label.configure(text=message_manager.get_ui_message("U147"))
        if getattr(self, "_show_base_layer_check", None) is not None:
            self._show_base_layer_check.configure(text=message_manager.get_ui_message("U140"))
        if getattr(self, "_show_comp_layer_check", None) is not None:
            self._show_comp_layer_check.configure(text=message_manager.get_ui_message("U141"))
        if getattr(self, "_show_reference_grid_check", None) is not None:
            self._show_reference_grid_check.configure(text=message_manager.get_ui_message("U149"))
        if getattr(self, "_diff_emphasis_check", None) is not None:
            self._diff_emphasis_check.configure(text=message_manager.get_ui_message("U178"))
        if getattr(self, "_shortcut_guide_frame", None) is not None:
            self._draw_canvas_footer_guide()
        if getattr(self, "_custom_rotation_guide_button", None) is not None:
            self._custom_rotation_guide_button.configure(text=message_manager.get_ui_message("U151"))
        if getattr(self, "_color_processing_mode_combo", None) is not None:
            self._color_processing_mode_combo.configure(values=self._get_color_processing_mode_display_values())
            self._color_processing_mode_var.set(
                self._get_color_processing_mode_display_text(self._selected_color_processing_mode)
            )

    def _attach_action_button_tooltips(self) -> None:
        """Attach localized hover descriptions to the image action buttons."""
        return

    def _show_custom_rotation_guide(self) -> None:
        """Show a detailed custom rotation guide dialog."""
        # Main processing: show the longer rotation instructions only on demand.
        messagebox.showinfo(
            title=message_manager.get_ui_message("U151"),
            message=message_manager.get_ui_message("U152"),
            parent=self.winfo_toplevel(),
        )

    def _refresh_action_button_image_cache(self) -> None:
        """Rebuild image-button artwork for the current theme colors.

        Theme switches must recreate the composited square artwork so transparent
        PNGs inherit the active button background instead of a stale cached color.
        """
        self._automatic_button_images = self._build_action_button_images("automatic")
        self._custom_button_images = self._build_action_button_images(
            "custom",
            force_default_idle=self._current_custom_button_state != "on",
        )

    def _apply_layer_toggle_theme(self, theme_data: Optional[Dict[str, Any]] = None) -> None:
        """Apply theme colors to the base/comparison layer visibility checkboxes.

        Args:
            theme_data: Optional current theme snapshot.
        """
        current_theme = theme_data or ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        frame_bg = str(frame_theme.get("bg", "#ffffff"))
        frame_fg = str(frame_theme.get("fg", "#000000"))
        disabled_visuals = resolve_disabled_visual_colors(
            frame_bg,
            str(frame_theme.get("disabledforeground", frame_fg)),
            fallback_bg=frame_bg,
        )
        disabled_bg = str(disabled_visuals.get("disabled_bg", frame_bg))
        disabled_fg = str(disabled_visuals.get("disabled_fg", frame_fg))

        layer_toggle_frame = getattr(self, "_layer_toggle_frame", None)
        if layer_toggle_frame is not None:
            try:
                layer_toggle_frame.configure(bg=frame_bg)
            except Exception:
                pass

        for checkbox_attr in [
            "_show_base_layer_check",
            "_show_comp_layer_check",
            "_show_reference_grid_check",
            "_diff_emphasis_check",
        ]:
            checkbox = getattr(self, checkbox_attr, None)
            if checkbox is None:
                continue
            try:
                is_enabled = str(checkbox.cget("state")) != str(tk.DISABLED)
                checkbox.configure(
                    bg=frame_bg if is_enabled else disabled_bg,
                    fg=frame_fg if is_enabled else disabled_fg,
                    selectcolor=frame_bg if is_enabled else disabled_bg,
                    activebackground=frame_bg if is_enabled else disabled_bg,
                    activeforeground=frame_fg if is_enabled else disabled_fg,
                    disabledforeground=disabled_fg,
                    highlightbackground=frame_bg,
                    highlightcolor=frame_bg,
                )
            except Exception:
                pass

    def _sync_diff_emphasis_checkbox_state(
        self,
        *,
        workspace_enabled: bool,
        theme_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enable the diff-emphasis control only when both layers are visible and the workspace is ready."""
        ch = getattr(self, "_diff_emphasis_check", None)
        if ch is None:
            return
        both_layers = bool(self._show_base_layer_var.get() and self._show_comp_layer_var.get())
        allow = bool(workspace_enabled and both_layers)
        try:
            ch.configure(state=tk.NORMAL if allow else tk.DISABLED)
        except Exception:
            pass
        self._apply_layer_toggle_theme(theme_data)

    def _apply_layer_toggle_state(
        self,
        *,
        enabled: bool,
        theme_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Apply enabled or disabled state to the layer visibility checkboxes.

        Args:
            enabled: Whether the checkboxes should be interactive.
            theme_data: Optional current theme snapshot.
        """
        for checkbox_attr in ["_show_base_layer_check", "_show_comp_layer_check", "_show_reference_grid_check"]:
            checkbox = getattr(self, checkbox_attr, None)
            if checkbox is None:
                continue
            try:
                checkbox.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except Exception:
                pass
        self._apply_layer_toggle_theme(theme_data)
        self._sync_diff_emphasis_checkbox_state(workspace_enabled=enabled, theme_data=theme_data)

    def _sync_visualized_image_state(self) -> None:
        """Synchronize the visible-layer StringVar with the checkbox selection state."""
        base_visible = bool(self._show_base_layer_var.get())
        comp_visible = bool(self._show_comp_layer_var.get())
        if base_visible and comp_visible:
            self.visualized_image.set("both")
        elif base_visible:
            self.visualized_image.set("base")
        elif comp_visible:
            self.visualized_image.set("comparison")
        else:
            self.visualized_image.set("none")

    def _on_layer_visibility_changed(self) -> None:
        """Refresh the canvas when the base/comparison visibility checkbox changes."""
        self._sync_visualized_image_state()
        # Main processing: persist layer visibility toggles so the next launch restores the same preview state.
        self.settings.update_setting("show_base_layer", bool(self._show_base_layer_var.get()))
        self.settings.update_setting("show_comp_layer", bool(self._show_comp_layer_var.get()))
        self.settings.update_setting("show_reference_grid", bool(self._show_reference_grid_var.get()))
        self.settings.save_settings()
        if self._has_loaded_workspace_pages():
            self._refresh_current_page_view(show_progress=False)
        else:
            self._render_comparison_placeholder()
        self._sync_diff_emphasis_checkbox_state(
            workspace_enabled=self._has_loaded_workspace_pages(),
        )

    def _on_diff_emphasis_toggled(self) -> None:
        """Redraw the preview when the user toggles diff highlight overlay."""
        if self._has_loaded_workspace_pages():
            self._run_blocking_preview_progress(
                message_manager.get_ui_message("U185"),
                lambda: self._display_page(self.current_page_index),
            )
        else:
            self._render_comparison_placeholder()

    def _get_reference_grid_color(self) -> str:
        """Return the preview reference-grid color.

        Returns:
            Hex color string used for the preview guide lines.
        """
        current_theme = ColorThemeManager.get_instance().get_current_theme()
        canvas_theme = dict(current_theme.get("canvas", {}))
        frame_theme = dict(current_theme.get("Frame", {}))
        return str(canvas_theme.get("reference_grid", frame_theme.get("disabledforeground", "#bfc3cf")))

    def _get_canvas_visible_origin(self) -> tuple[float, float]:
        """Return the current visible origin of the preview canvas.

        Returns:
            Tuple of visible ``(x, y)`` canvas coordinates.
        """
        if not hasattr(self, "canvas"):
            return (0.0, 0.0)
        try:
            return (float(self.canvas.canvasx(0)), float(self.canvas.canvasy(0)))
        except Exception:
            return (0.0, 0.0)

    def _set_main_canvas_scrollregion_from_pdf_image(self) -> None:
        """Expand scrollregion past page pixels so the widget viewport has canvas coordinates.

        Without this, areas of the canvas widget that extend beyond the PDF bbox
        do not receive reference-grid dots after resize.
        """
        if not hasattr(self, "canvas"):
            return
        try:
            ib = self.canvas.bbox("pdf_image")
            cw = max(int(self.canvas.winfo_width()), 1)
            ch = max(int(self.canvas.winfo_height()), 1)
            if ib is None:
                self.canvas.config(scrollregion=(0, 0, cw, ch))
                return
            x0, y0, x1, y1 = (int(ib[0]), int(ib[1]), int(ib[2]), int(ib[3]))
            self.canvas.config(
                scrollregion=(
                    min(0, x0),
                    min(0, y0),
                    max(x1, cw),
                    max(y1, ch),
                )
            )
        except Exception:
            try:
                fallback = self.canvas.bbox("pdf_image")
                if fallback:
                    self.canvas.config(scrollregion=fallback)
            except Exception:
                pass

    def _apply_image_button_state(
        self,
        image_kind: str,
        *,
        enabled: bool,
        theme_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Apply enabled or disabled state to a themed image action button.

        Args:
            image_kind: Either ``automatic`` or ``custom``.
            enabled: Whether the button should be interactive.
            theme_data: Optional current theme snapshot.
        """
        button = self._automatic_execute_button if image_kind == "automatic" else self._custom_execute_button
        if button is None:
            return

        current_theme = theme_data or ColorThemeManager.get_instance().get_current_theme()
        frame_theme = dict(current_theme.get("Frame", {}))
        label_disabled_theme = dict(current_theme.get("LabelDisabled", {}))
        button_theme = self._resolve_main_button_theme(current_theme, "process_button")
        disabled_visuals = resolve_disabled_visual_colors(
            str(button_theme.get("bg", frame_theme.get("bg", "#ffffff"))),
            str(label_disabled_theme.get("fg", frame_theme.get("disabledforeground", button_theme.get("fg", frame_theme.get("fg", "#000000"))))),
            fallback_bg=str(frame_theme.get("bg", button_theme.get("bg", "#ffffff"))),
            use_emphasis_surface=True,
        )
        disabled_bg = str(disabled_visuals.get("disabled_bg", frame_theme.get("bg", "#ffffff")))
        disabled_fg = str(disabled_visuals.get("disabled_fg", frame_theme.get("fg", "#000000")))

        if not enabled:
            button.configure(
                state=tk.DISABLED,
                image="",
                text="",
                bg=disabled_bg,
                fg=disabled_fg,
                activebackground=disabled_bg,
                activeforeground=disabled_fg,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
            )
            button.image = None
            return

        button.configure(
            state=tk.NORMAL,
            bg=str(button_theme.get("bg", frame_theme.get("bg", "#ffffff"))),
            fg=str(button_theme.get("fg", frame_theme.get("fg", "#000000"))),
            activebackground=str(button_theme.get("activebackground", button_theme.get("bg", frame_theme.get("bg", "#ffffff")))),
            activeforeground=str(button_theme.get("activeforeground", button_theme.get("fg", frame_theme.get("fg", "#000000")))),
            relief=tk.RAISED,
            bd=2,
            highlightthickness=1,
            highlightbackground=str(button_theme.get("activebackground", button_theme.get("bg", frame_theme.get("bg", "#ffffff")))),
            highlightcolor=str(button_theme.get("activebackground", button_theme.get("bg", frame_theme.get("bg", "#ffffff")))),
        )
        self._apply_action_button_visual(image_kind, False)

    def _refresh_interaction_state(self, theme_data: Optional[Dict[str, Any]] = None) -> None:
        """Refresh enabled and disabled states for the pink and yellow-green controls.

        Args:
            theme_data: Optional current theme snapshot.
        """
        current_theme = theme_data or ColorThemeManager.get_instance().get_current_theme()
        base_ready = self._path_points_to_file(self.base_path.get())
        comparison_ready = self._path_points_to_file(self.comparison_path.get())
        any_input_ready = base_ready or comparison_ready
        workspace_ready = self._has_loaded_workspace_pages() and not self._copy_protected

        self._apply_main_button_state(
            getattr(self, "_base_file_analyze_btn", None),
            enabled=base_ready,
            theme_key="create_sub_graph_window_button",
            theme_data=current_theme,
        )
        self._apply_main_button_state(
            getattr(self, "_comparison_file_analyze_btn", None),
            enabled=comparison_ready,
            theme_key="create_sub_graph_window_button",
            theme_data=current_theme,
        )
        self._apply_main_combobox_state(
            getattr(self, "_dpi_combo", None),
            enabled=any_input_ready,
        )
        self._apply_main_combobox_state(
            getattr(self, "_color_processing_mode_combo", None),
            enabled=any_input_ready,
        )
        self._apply_main_entry_state(
            getattr(self, "_base_threshold_entry", None),
            enabled=any_input_ready,
            theme_key="create_fb_threshold_entry",
            theme_data=current_theme,
        )
        self._apply_main_entry_state(
            getattr(self, "_comparison_threshold_entry", None),
            enabled=any_input_ready,
            theme_key="create_fb_threshold_entry",
            theme_data=current_theme,
        )
        self._apply_image_button_state("automatic", enabled=any_input_ready, theme_data=current_theme)
        self._apply_image_button_state("custom", enabled=any_input_ready, theme_data=current_theme)
        self._apply_layer_toggle_state(enabled=workspace_ready, theme_data=current_theme)

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.set_workspace_controls_enabled(workspace_ready)
                self.page_control_frame.set_edit_buttons_enabled(workspace_ready)
                self._sync_batch_edit_state()
            except Exception:
                pass

    def _load_action_button_image(
        self,
        image_path: object,
        fallback_text: str,
        target_height: int = 34,
        fill_ratio: float = 0.94,
    ) -> Optional[ImageTk.PhotoImage]:
        """Load and resize an action button image for the main tab.

        Args:
            image_path: Candidate image path resolved by ``ImageSwPaths``.
            fallback_text: Human-readable label used only for logging context.
            target_height: Desired rendered image height in pixels.
            fill_ratio: Relative amount of the square button occupied by the artwork.

        Returns:
            Optional[ImageTk.PhotoImage]: Loaded image reference when available.
        """
        try:
            if image_path is None:
                return None

            resolved_path = Path(str(image_path))
            if not resolved_path.exists():
                return None

            # Main processing: normalize action button artwork to a stable display height.
            with Image.open(resolved_path) as pil_image:
                prepared = pil_image.convert("RGBA")
                button_width = max(self._action_button_square_size, 88)
                button_height = max(self._action_button_square_size, target_height, 88)
                usable_width = max(1, int(button_width * max(0.1, min(fill_ratio, 1.0))))
                usable_height = max(1, button_height - 8)
                scale = min(
                    usable_width / float(max(1, prepared.width)),
                    usable_height / float(max(1, prepared.height)),
                )
                target_width = max(1, int(prepared.width * scale))
                scaled_height = max(1, int(prepared.height * scale))
                resized = prepared.resize((target_width, scaled_height), Resampling.LANCZOS)
                current_theme = ColorThemeManager.get_instance().get_current_theme()
                button_theme = current_theme.get("process_button", {})
                fallback_bg = button_theme.get("bg", current_theme.get("Frame", {}).get("bg", "#1d1d29"))
                bg_rgb = tuple(int(fallback_bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if isinstance(fallback_bg, str) and len(fallback_bg) == 7 else (29, 29, 41)
                canvas = Image.new("RGBA", (button_width, button_height), (*bg_rgb, 255))
                offset_x = (button_width - target_width) // 2
                offset_y = (button_height - scaled_height) // 2
                canvas.alpha_composite(resized, (offset_x, offset_y))
                return ImageTk.PhotoImage(canvas)
        except Exception as exc:
            logger.warning(f"Failed to load main tab action button image ({fallback_text}): {exc}")
            return None

    def _build_action_button_images(
        self,
        image_kind: str,
        force_default_idle: bool = False,
        randomize_custom_idle: bool = False,
    ) -> Dict[str, ImageTk.PhotoImage]:
        """Build the active and inactive images for a main-tab action button.

        Args:
            image_kind: Either ``automatic`` or ``custom``.
            force_default_idle: Whether the custom button must use the default idle image.
            randomize_custom_idle: Whether the custom idle artwork should rotate to gag images.

        Returns:
            Dict[str, ImageTk.PhotoImage]: Loaded ``on``/``off`` image dictionary.
        """
        if image_kind == "automatic":
            switch_paths = ImageSwPaths().set_automatic_convert_btn_image(
                program_mode=tool_settings.is_production_mode
            )
        else:
            switch_paths = ImageSwPaths().set_custom_convert_btn_image(
                program_mode=tool_settings.is_production_mode,
                randomize_idle=randomize_custom_idle and not force_default_idle,
            )
            if force_default_idle:
                switch_paths.off_img_path = get_resource_path("images/hennshinn_pose.png")

        loaded_images: Dict[str, ImageTk.PhotoImage] = {}
        on_fill_ratio = 0.98 if image_kind == "custom" else 0.96
        off_fill_ratio = 0.98 if image_kind == "custom" else 0.96
        on_image = self._load_action_button_image(
            switch_paths.on_img_path,
            f"{image_kind}-on",
            target_height=72,
            fill_ratio=on_fill_ratio,
        )
        off_image = self._load_action_button_image(
            switch_paths.off_img_path,
            f"{image_kind}-off",
            target_height=72,
            fill_ratio=off_fill_ratio,
        )
        if on_image is not None:
            loaded_images["on"] = on_image
        if off_image is not None:
            loaded_images["off"] = off_image
        return loaded_images

    def _apply_action_button_visual(self, image_kind: str, active: bool, refresh_random: bool = False) -> None:
        """Apply the current image state to one of the restored action buttons.

        Args:
            image_kind: Either ``automatic`` or ``custom``.
            active: Whether the button should show its active artwork.
            refresh_random: Whether the random custom artwork should be refreshed first.
        """
        button = self._automatic_execute_button if image_kind == "automatic" else self._custom_execute_button
        if button is None:
            return

        if image_kind == "automatic":
            if not self._automatic_button_images:
                self._automatic_button_images = self._build_action_button_images("automatic")
            image_map = self._automatic_button_images
            fallback_text = message_manager.get_ui_message("U145")
        else:
            if refresh_random:
                self._custom_button_images = self._build_action_button_images(
                    "custom",
                    randomize_custom_idle=True,
                )
            elif not self._custom_button_images:
                self._custom_button_images = self._build_action_button_images("custom", force_default_idle=True)
            image_map = self._custom_button_images
            fallback_text = message_manager.get_ui_message("U023")

        requested_key = "on" if active else "off"
        requested_image = image_map.get(requested_key) or image_map.get("off") or image_map.get("on")
        if requested_image is not None:
            button.configure(
                image=requested_image,
                text="",
                relief=tk.SUNKEN if active else tk.RAISED,
                bd=4 if active else 3,
            )
            button.image = requested_image
        else:
            button.configure(image="", text=fallback_text)

        if image_kind == "custom":
            self._current_custom_button_state = requested_key

    def _restore_custom_button_default_idle(self) -> None:
        """Restore the custom action button to its default idle artwork."""
        self._custom_button_images = self._build_action_button_images(
            "custom",
            force_default_idle=True,
        )
        self._apply_action_button_visual("custom", False)

    def _prepare_custom_button_press_visual(self, event: Optional[tk.Event] = None) -> None:
        """Show the custom-button active image before the command callback runs.

        Args:
            event: Optional Tk button-press event.

        """
        _ = event
        self._custom_button_images = self._build_action_button_images(
            "custom",
            force_default_idle=True,
        )
        self._apply_action_button_visual("custom", True)

    def _restore_action_buttons_after_execute(self) -> None:
        """Restore the image buttons after an execute operation completes.

        The custom button intentionally refreshes its inactive artwork again so the
        remembered random-image gimmick is visible after each execute action.
        """
        self._apply_action_button_visual("automatic", False)
        self._apply_action_button_visual("custom", False, refresh_random=True)

    def _on_automatic_image_button_click(self) -> None:
        """Handle the restored automatic image button click event."""
        self._apply_action_button_visual("automatic", True)
        self.update_idletasks()
        self.after(self._action_button_active_delay_ms, self._run_automatic_image_button_action)

    def _on_custom_image_button_click(self) -> None:
        """Handle the restored custom image button click event."""
        self._custom_button_images = self._build_action_button_images(
            "custom",
            force_default_idle=True,
        )
        self._apply_action_button_visual("custom", True)
        self.update_idletasks()
        self.after(self._action_button_active_delay_ms, self._run_custom_image_button_action)

    def _run_automatic_image_button_action(self) -> None:
        """Run the automatic image-button action after showing the active gimmick."""
        try:
            self._on_execute_click()
        finally:
            self.after(260, self._restore_action_buttons_after_execute)

    def _run_custom_image_button_action(self) -> None:
        """Run the custom image-button action after showing the active gimmick."""
        try:
            self._on_process_click()
        finally:
            self.after(320, self._restore_custom_button_default_idle)

    def _on_color_processing_mode_changed(self, event: Optional[tk.Event] = None) -> None:
        """Refresh the workspace preview after changing the color mode.

        Args:
            event: Optional Tk event.
        """
        _ = event
        with self._diff_overlay_cache_lock:
            self._diff_src_overlay_cache.clear()
            self._diff_overlay_bg_key = None
        self._selected_color_processing_mode = self._resolve_color_processing_mode_from_display(
            self._color_processing_mode_var.get()
        )
        self._color_processing_mode_var.set(
            self._get_color_processing_mode_display_text(self._selected_color_processing_mode)
        )
        self.settings.update_setting("color_processing_mode", self._selected_color_processing_mode)
        self.settings.save_settings()
        if self._has_loaded_workspace_pages():
            self._run_blocking_preview_progress(
                message_manager.get_ui_message("U184"),
                lambda: self._display_page(self.current_page_index),
            )

    def _refresh_preview_after_color_change(self) -> None:
        """Redraw the current page after palette changes when a workspace exists."""
        if self._has_loaded_workspace_pages():
            self._display_page(self.current_page_index)

    def _open_base_analysis_graph(self) -> None:
        """Prepare histogram data and open the base analysis graph window.

        Raises:
            Exception: If the base analysis flow fails.
        """
        if self._base_file_analyze_btn is not None and self._base_file_analyze_btn._graph_status:
            self._base_file_analyze_btn.close_graph_window()
            return

        self._on_base_analyze_click()
        if self._base_file_analyze_btn is not None:
            self._base_file_analyze_btn.open_graph_window()

    def _open_comparison_analysis_graph(self) -> None:
        """Prepare histogram data and open the comparison analysis graph window.

        Raises:
            Exception: If the comparison analysis flow fails.
        """
        if self._comparison_file_analyze_btn is not None and self._comparison_file_analyze_btn._graph_status:
            self._comparison_file_analyze_btn.close_graph_window()
            return

        self._on_comparison_analyze_click()
        if self._comparison_file_analyze_btn is not None:
            self._comparison_file_analyze_btn.open_graph_window()

    def _get_initial_dir_from_setting(self, setting_key: str, current_value: Optional[str] = None) -> str:
        """Return an initial directory for file and folder dialogs.

        Args:
            setting_key: User setting key for the target path.
            current_value: Current entry value that should be preferred when valid.

        Returns:
            A directory path suitable for ``initialdir``.
        """
        candidate_values: List[str] = []
        if isinstance(current_value, str) and current_value:
            candidate_values.append(current_value)

        try:
            saved_value = self.settings.get_setting(setting_key)
        except Exception:
            saved_value = None

        if isinstance(saved_value, str) and saved_value:
            candidate_values.append(saved_value)

        for candidate_value in candidate_values:
            try:
                path = Path(candidate_value)
                if path.exists() and path.is_dir():
                    return str(path)
                if path.parent.exists() and path.parent.is_dir():
                    return str(path.parent)
            except Exception:
                continue

        return str(Path.cwd())

    def _set_path_entry_display(self, entry_widget: BasePathEntry, display_value: str) -> None:
        """Update a path entry display without persisting the temporary startup text.

        Args:
            entry_widget: Path entry widget to update.
            display_value: Display text shown in the entry field.
        """
        previous_suppress = bool(getattr(entry_widget, "_suppress_callback", False))
        setattr(entry_widget, "_suppress_callback", True)
        try:
            entry_widget.path_var.set(display_value)
        finally:
            setattr(entry_widget, "_suppress_callback", previous_suppress)

    def _workspace_source_file_exists(self, path_str: str, placeholder_file: str) -> bool:
        """Return True when ``path_str`` is an existing workspace input file (PDF, image, SVG).

        Args:
            path_str: Candidate filesystem path.
            placeholder_file: Localized unset-path token to treat as empty.

        Returns:
            Whether the path should be treated as a resolved workspace source file.
        """
        if not path_str or path_str == placeholder_file:
            return False
        try:
            p = Path(path_str)
            return (
                p.exists()
                and p.is_file()
                and p.suffix.lower() in MAIN_PDF_OPE_INPUT_EXTENSIONS
            )
        except Exception:
            return False

    def _coerce_main_tab_saved_file_path(self, raw: str, placeholder_file: str) -> str:
        """Normalize a persisted main-tab file slot to a path or the unset sentinel.

        Args:
            raw: Value from user settings for base or comparison PDF.
            placeholder_file: Localized unset-path token (U053).

        Returns:
            ``placeholder_file`` when the value is empty or a legacy/default sentinel;
            otherwise the normalized host path string.
        """
        s = str(raw or "").strip()
        if not s or s == placeholder_file or s == self._LEGACY_SETTINGS_PLACEHOLDER_JA:
            return placeholder_file
        return normalize_host_path(s)

    def _coerce_main_tab_saved_folder_path(self, raw: str, placeholder_folder: str) -> str:
        """Normalize a persisted output-folder slot to a path or the unset sentinel.

        Args:
            raw: Value from user settings for the output folder.
            placeholder_folder: Localized unset-folder token (U054).

        Returns:
            ``placeholder_folder`` when the value is empty or a legacy/default sentinel;
            otherwise the normalized host path string.
        """
        s = str(raw or "").strip()
        if not s or s == placeholder_folder or s == self._LEGACY_SETTINGS_PLACEHOLDER_JA:
            return placeholder_folder
        return normalize_host_path(s)

    def _path_display_for_main_entry(
        self,
        saved_value: str,
        placeholder_file: str,
        session_committed: bool,
    ) -> str:
        """Build base/comparison entry text: folder or placeholder until the side is committed.

        Args:
            saved_value: Persisted path from settings.
            placeholder_file: Localized unset-path token (U053).
            session_committed: Whether the user confirmed this side this session.

        Returns:
            String to show in the path entry.
        """
        if saved_value == placeholder_file:
            return placeholder_file
        if session_committed:
            return saved_value
        if self._workspace_source_file_exists(saved_value, placeholder_file):
            return str(Path(saved_value).parent)
        return saved_value

    def _placeholder_status_path_line(self, path_value: str) -> str:
        """Format a path for the canvas placeholder status lines (folder if PDF on disk).

        Args:
            path_value: Current path entry text (folder, PDF, or placeholder).

        Returns:
            Human-readable line for the placeholder canvas.
        """
        placeholder_pdf = message_manager.get_ui_message("U053")
        if not path_value or path_value == placeholder_pdf:
            return placeholder_pdf
        try:
            p = Path(path_value)
            if p.exists() and p.is_file() and p.suffix.lower() in MAIN_PDF_OPE_INPUT_EXTENSIONS:
                return str(p.parent)
            return str(p)
        except Exception:
            return path_value

    def _workspace_string_for_pdf_side(
        self,
        *,
        saved_value: str,
        placeholder_file: str,
        session_committed: bool,
    ) -> str:
        """Value for ``base_path`` / ``comparison_path`` used by the preview workspace.

        Until the user commits the side, a stored PDF path does not load the workspace
        (placeholder is used). After commit, the saved path is used. Non-PDF saved
        paths (e.g. folders) are passed through like before.

        Args:
            saved_value: Persisted path from user settings.
            placeholder_file: Localized unset-path token.
            session_committed: Whether this side was confirmed this session.

        Returns:
            Path string for ``StringVar`` driving ``_refresh_workspace_state``.
        """
        if saved_value == placeholder_file:
            return placeholder_file
        if self._workspace_source_file_exists(saved_value, placeholder_file) and not session_committed:
            return placeholder_file
        return saved_value

    def _on_row4_comment_frame_configure(self, event: tk.Event) -> None:
        """Keep the U137 guidance label wrapped to the visible column width.

        Args:
            event: Tkinter ``Configure`` event from ``_row4_comment_frame``.
        """
        if event.widget is not getattr(self, "_row4_comment_frame", None):
            return
        label = getattr(self, "_row4_comment_text_label", None)
        if label is None:
            return
        try:
            # Slight margin only; over-subtracting narrows U137 and adds lines (pushes thresholds down).
            wrap_px = max(int(event.width) - 6, 80)
            label.configure(wraplength=wrap_px)
        except Exception:
            pass

    def _on_row4_arrow_guidance_frame_configure(self, event: tk.Event) -> None:
        """Keep the U146 archer-column hint wrapped at the visible column width.

        Args:
            event: Tkinter ``Configure`` event from ``_row4_arrow_guidance_frame``.
        """
        if event.widget is not getattr(self, "_row4_arrow_guidance_frame", None):
            return
        label = getattr(self, "_row4_arrow_guidance_label", None)
        if label is None:
            return
        try:
            wrap_px = max(int(event.width) - 6, 60)
            label.configure(wraplength=wrap_px)
        except Exception:
            pass

    def _sync_shared_paths_from_settings(self, event: Any = None) -> None:
        """Synchronize persisted paths into the main tab inputs.

        Args:
            event: Tkinter visibility or notebook tab-change event (unused). PDF paths
                from settings show as the parent folder in the entry until the user
                commits the side via dialog, drop, or Enter; preview uses
                ``base_path`` / ``comparison_path`` only after they hold file paths.
        """
        _ = event
        placeholder_file = message_manager.get_ui_message("U053")
        placeholder_output = message_manager.get_ui_message("U054")

        try:
            _rb = str(self.settings.get_setting("base_file_path", placeholder_file) or placeholder_file)
            _rc = str(self.settings.get_setting("comparison_file_path", placeholder_file) or placeholder_file)
            _ro = str(self.settings.get_setting("output_folder_path", placeholder_output) or placeholder_output)
            saved_base = self._coerce_main_tab_saved_file_path(_rb, placeholder_file)
            saved_comparison = self._coerce_main_tab_saved_file_path(_rc, placeholder_file)
            saved_output = self._coerce_main_tab_saved_folder_path(_ro, placeholder_output)

            output_display = placeholder_output if saved_output == placeholder_output else saved_output

            base_for_workspace = self._workspace_string_for_pdf_side(
                saved_value=saved_base,
                placeholder_file=placeholder_file,
                session_committed=self._base_pdf_session_committed,
            )
            comparison_for_workspace = self._workspace_string_for_pdf_side(
                saved_value=saved_comparison,
                placeholder_file=placeholder_file,
                session_committed=self._comparison_pdf_session_committed,
            )

            base_entry_text = self._path_display_for_main_entry(
                saved_base, placeholder_file, self._base_pdf_session_committed
            )
            comparison_entry_text = self._path_display_for_main_entry(
                saved_comparison, placeholder_file, self._comparison_pdf_session_committed
            )

            self.base_path.set(base_for_workspace)
            self.comparison_path.set(comparison_for_workspace)
            self.output_path.set(output_display)
            self._set_path_entry_display(self._base_file_path_entry, base_entry_text)
            self._set_path_entry_display(self._comparison_file_path_entry, comparison_entry_text)
            self._set_path_entry_display(self._output_folder_path_entry, output_display)

            new_sig = self._current_workspace_paths_signature()
            cached = self._workspace_paths_signature_cache
            if (
                cached is not None
                and new_sig == cached
                and self._has_loaded_workspace_pages()
            ):
                self._apply_path_entry_activity_style()
                return

            self._refresh_workspace_state()
            self._apply_path_entry_activity_style()
        except Exception as exc:
            logger.warning(f"Shared path sync failed in main tab: {exc}")

    def _setup_drag_and_drop(self) -> None:
        """Setup drag and drop for input and output path entries."""
        try:
            DragAndDropHandler.register_drop_target(
                self._base_file_path_entry,
                self._on_drop_base_file,
                main_pdf_ope_drop_suffixes(),
                self._show_status_feedback,
            )
            DragAndDropHandler.register_drop_target(
                self._comparison_file_path_entry,
                self._on_drop_comparison_file,
                main_pdf_ope_drop_suffixes(),
                self._show_status_feedback,
            )
            DragAndDropHandler.register_drop_target(
                self._output_folder_path_entry,
                self._on_drop_output_folder,
                feedback_callback=self._show_status_feedback,
                allow_directories=True,
            )
        except Exception as e:
            logger.error(message_manager.get_log_message("L206", str(e)))

    def _on_drop_base_file(self, file_path: str) -> None:
        """Handle base PDF drop.

        Args:
            file_path: Dropped file path.
        """
        if not self._base_file_path_entry.accept_dialog_path(file_path):
            return
        self._base_pdf_session_committed = True
        resolved = self._base_file_path_entry.path_var.get()
        self.base_path.set(resolved)
        self.status_var.set("ベースPDFを下のプレビュー用に選択しました。")
        self._refresh_workspace_state()

    def _on_drop_comparison_file(self, file_path: str) -> None:
        """Handle comparison PDF drop.

        Args:
            file_path: Dropped file path.
        """
        if not self._comparison_file_path_entry.accept_dialog_path(file_path):
            return
        self._comparison_pdf_session_committed = True
        resolved = self._comparison_file_path_entry.path_var.get()
        self.comparison_path.set(resolved)
        self.status_var.set("比較PDFを下のプレビュー用に選択しました。")
        self._refresh_workspace_state()

    def _on_drop_output_folder(self, folder_path: str) -> None:
        """Handle output folder drop.

        Args:
            folder_path: Dropped folder path.
        """
        if not self._output_folder_path_entry.accept_dialog_path(folder_path):
            return
        resolved = self._output_folder_path_entry.path_var.get()
        self.output_path.set(resolved)
        self.status_var.set("Output folder updated for future comparison export.")
        if not self._has_loaded_workspace_pages():
            self._render_comparison_placeholder()

    def _show_status_feedback(self, message: str, is_success: bool) -> None:
        """Store drag-and-drop feedback and mirror it to the logger.

        Args:
            message: Feedback message.
            is_success: Whether the operation succeeded.
        """
        self.status_var.set(message)
        if is_success:
            logger.info(message)
        else:
            logger.warning(message)
        if self._has_loaded_workspace_pages():
            return
        self._render_comparison_placeholder()

    def _clear_loaded_workspace_data(self) -> None:
        """Clear converted page data and active converter references."""
        self._preview_render_generation += 1
        self._background_preview_render_thread = None
        self._clear_workspace_temp_artifacts()
        with self._diff_overlay_cache_lock:
            self._diff_src_overlay_cache.clear()
            self._diff_overlay_bg_key = None
        self._batch_edit_selected = True
        self.base_page_paths = []
        self.comp_page_paths = []
        self._base_page_records = []
        self._comp_page_records = []
        self._base_workspace_dir = None
        self._comp_workspace_dir = None
        self.base_pages = []
        self.comp_pages = []
        self.base_transform_data = []
        self.comp_transform_data = []
        self._base_export_transform_overrides = []
        self._comp_export_transform_overrides = []
        self.page_count = 0
        self.current_page_index = 0
        self._copy_protected = False
        self._visual_adjustments_enabled = False
        self.base_file_info = None
        self.comp_file_info = None
        self.base_pdf_metadata = {}
        self.comp_pdf_metadata = {}
        self.base_pdf_converter = None
        self.comp_pdf_converter = None
        self._base_photo_image = None
        self._comp_photo_image = None
        self._base_canvas_image_id = None
        self._comp_canvas_image_id = None
        self._preview_canvas_snap = None
        self._preview_source_image_cache.clear()
        self._preview_processed_image_cache.clear()
        self._preview_keyboard_rotation_delta = 0.0
        self._workspace_paths_signature_cache = None

    def _remove_temp_directory(self, target_dir: Optional[Path]) -> None:
        """Delete one generated temp directory when it is safe to remove.

        Args:
            target_dir: Candidate directory under the application temp root.
        """
        if target_dir is None:
            return

        try:
            candidate_dir = Path(target_dir)
            if not candidate_dir.exists() or not candidate_dir.is_dir():
                return

            temp_root = Path(get_temp_dir()).resolve()
            candidate_resolved = candidate_dir.resolve()
            candidate_resolved.relative_to(temp_root)
            if candidate_resolved == temp_root:
                return

            shutil.rmtree(candidate_resolved, ignore_errors=True)
        except Exception:
            return

    def _clear_workspace_temp_artifacts(self) -> None:
        """Delete generated workspace and converter temp directories for the current sources."""
        candidate_dirs: List[Path] = []
        for workspace_dir in (self._base_workspace_dir, self._comp_workspace_dir):
            if workspace_dir is not None:
                candidate_dirs.append(workspace_dir)

        for converter in (getattr(self, "base_pdf_converter", None), getattr(self, "comp_pdf_converter", None)):
            if converter is None:
                continue
            converter_temp_dir = getattr(converter, "_temp_dir", None)
            if converter_temp_dir:
                candidate_dirs.append(Path(str(converter_temp_dir)))

        seen_dirs: set[str] = set()
        for candidate_dir in candidate_dirs:
            candidate_key = str(candidate_dir)
            if candidate_key in seen_dirs:
                continue
            seen_dirs.add(candidate_key)
            self._remove_temp_directory(candidate_dir)

    def _has_loaded_workspace_pages(self) -> bool:
        """Return whether converted workspace pages are available.

        Returns:
            ``True`` when at least one rendered page image exists.
        """
        return bool(self.base_page_paths or self.comp_page_paths)

    def _get_selected_dpi(self) -> int:
        """Return a safe DPI value from user settings.

        Returns:
            Integer DPI value used for PDF rendering.
        """
        # Main processing: preserve manual selections, but treat detected selections as a 300-dpi startup fallback until sources are available.
        dpi_choices = self._get_configured_dpi_choices()
        raw_mode = str(self.settings.get_setting("setted_dpi_mode", "detected") or "detected").strip().lower()
        if raw_mode == "detected":
            return _MAIN_TAB_DEFAULT_DPI

        raw_dpi = self.settings.get_setting("setted_dpi", _MAIN_TAB_DEFAULT_DPI)
        try:
            resolved_dpi = int(raw_dpi)
        except (TypeError, ValueError):
            resolved_dpi = _MAIN_TAB_DEFAULT_DPI

        if resolved_dpi not in dpi_choices:
            return _MAIN_TAB_DEFAULT_DPI
        return max(1, resolved_dpi)

    def _get_configured_dpi_choices(self) -> List[int]:
        """Return sanitized DPI choices from user settings.

        Returns:
            List[int]: Ordered DPI choices used by the Main tab combobox.
        """
        try:
            raw_values = self.settings.get_setting_list(
                "dpi_list",
                list(_MAIN_TAB_FALLBACK_DPI_CHOICES),
            )
        except Exception:
            raw_values = list(_MAIN_TAB_FALLBACK_DPI_CHOICES)

        resolved_values: List[int] = []
        for raw_value in raw_values:
            try:
                dpi_value = int(raw_value)
            except (TypeError, ValueError):
                continue
            if dpi_value <= 0 or dpi_value in resolved_values:
                continue
            resolved_values.append(dpi_value)

        if _MAIN_TAB_DEFAULT_DPI not in resolved_values:
            resolved_values.append(_MAIN_TAB_DEFAULT_DPI)
        if not resolved_values:
            return list(_MAIN_TAB_FALLBACK_DPI_CHOICES)
        return resolved_values
    def _get_dpi_from_entry(self) -> int:
        """Return a validated DPI value from the current DPI selector.

        Returns:
            Integer DPI value.

        Raises:
            ValueError: If the selector contains an invalid DPI value.
        """
        resolved_dpi, _ = self._get_selected_dpi_from_control()
        if resolved_dpi <= 0:
            raise ValueError("DPI setting must be greater than zero.")
        return resolved_dpi

    def _persist_selected_dpi(self, dpi_value: int, dpi_mode: Literal["manual", "detected"]) -> None:
        """Persist the DPI setting and refresh in-memory fields.

        Args:
            dpi_value: DPI value to store.
            dpi_mode: DPI source mode chosen by the user.
        """
        self.selected_dpi_value = int(dpi_value)
        self._conversion_dpi = int(dpi_value)
        self.settings.update_setting("setted_dpi", int(dpi_value))
        self.settings.update_setting("setted_dpi_mode", str(dpi_mode))
        self.settings.save_settings()

    def _format_detected_dpi_choice(self, dpi_value: int) -> str:
        """Return the display label for the detected-DPI combobox item.

        Args:
            dpi_value: Detected DPI value.

        Returns:
            Combobox label text.
        """
        return f"{message_manager.get_ui_message('U148')} ({int(dpi_value)})"

    @staticmethod
    def _extract_pdf_document_metadata_dpi(metadata: Any) -> Optional[tuple[int, int]]:
        """Extract direct DPI metadata from a PDF document info object.

        Args:
            metadata: Metadata object returned by ``pypdf.PdfReader.metadata``.

        Returns:
            Tuple of detected ``(dpi_x, dpi_y)`` when available.
        """
        if metadata is None:
            return None

        def _read_positive_number(*keys: str) -> Optional[float]:
            """Read the first positive numeric metadata value.

            Args:
                *keys: Candidate metadata keys.

            Returns:
                Positive numeric value when found.
            """
            for key in keys:
                try:
                    value = metadata.get(key)
                except Exception:
                    value = None
                if value in (None, ""):
                    continue
                try:
                    parsed = float(str(value).strip())
                except Exception:
                    continue
                if parsed > 0:
                    return parsed
            return None

        dpi_x = _read_positive_number("/XResolution")
        dpi_y = _read_positive_number("/YResolution")
        dpi_common = _read_positive_number("/DPI")

        if dpi_x is None and dpi_common is not None:
            dpi_x = dpi_common
        if dpi_y is None and dpi_common is not None:
            dpi_y = dpi_common
        if dpi_x is None or dpi_y is None:
            return None

        try:
            resolution_unit_raw = metadata.get("/ResolutionUnit")
        except Exception:
            resolution_unit_raw = None
        resolution_unit = str(resolution_unit_raw).strip().lower() if resolution_unit_raw is not None else ""
        if resolution_unit and resolution_unit not in {"inch", "in", "dpi"}:
            return None

        return int(round(dpi_x)), int(round(dpi_y))

    @staticmethod
    def _extract_pdf_image_metadata_dpi(page: Any) -> Optional[tuple[int, int]]:
        """Extract direct DPI metadata from embedded images on the first PDF page.

        Args:
            page: First page object from ``pypdf.PdfReader.pages``.

        Returns:
            Tuple of detected ``(dpi_x, dpi_y)`` when available.
        """
        try:
            resources = page.get("/Resources")
            if resources is None or "/XObject" not in resources:
                return None
            xobjects = resources["/XObject"].get_object()
        except Exception:
            return None

        best_area = 0
        best_pair: Optional[tuple[int, int]] = None

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
                image_bytes = xobj.get_data()
                if not image_bytes:
                    continue
            except Exception:
                continue

            try:
                with Image.open(BytesIO(image_bytes)) as embedded_img:
                    dpi_info = embedded_img.info.get("dpi") if hasattr(embedded_img, "info") else None
            except Exception:
                continue

            if not (isinstance(dpi_info, tuple) and len(dpi_info) >= 2):
                continue

            try:
                dpi_x = int(round(float(dpi_info[0])))
                dpi_y = int(round(float(dpi_info[1])))
            except Exception:
                continue

            if dpi_x <= 0 or dpi_y <= 0:
                continue

            area = img_width * img_height
            if area > best_area:
                best_area = area
                best_pair = (dpi_x, dpi_y)

        return best_pair

    def _resolve_pdf_direct_metadata_dpi(self, pdf_path: str) -> Optional[int]:
        """Resolve direct metadata DPI from one PDF file.

        Args:
            pdf_path: Source PDF path.

        Returns:
            Averaged DPI value when direct metadata exists, otherwise ``None``.
        """
        if PdfReader is None or not self._path_points_to_file(pdf_path):
            return None

        try:
            reader = PdfReader(str(pdf_path), strict=False)
            metadata_pair = self._extract_pdf_document_metadata_dpi(reader.metadata)
            if metadata_pair is None and len(reader.pages) > 0:
                metadata_pair = self._extract_pdf_image_metadata_dpi(reader.pages[0])
        except Exception:
            return None

        if metadata_pair is None:
            return None

        resolved_dpi = int(round((float(metadata_pair[0]) + float(metadata_pair[1])) / 2.0))
        return resolved_dpi if resolved_dpi > 0 else None

    def _resolve_detected_dpi_from_selected_files(self) -> Optional[int]:
        """Resolve the preferred detected DPI from the selected base/comparison PDFs.

        Returns:
            Base-file detected DPI when available, otherwise comparison-file DPI.
        """
        base_detected = self._resolve_pdf_direct_metadata_dpi(self.base_path.get())
        if base_detected is not None:
            return base_detected
        return self._resolve_pdf_direct_metadata_dpi(self.comparison_path.get())

    def _get_selected_dpi_from_control(self) -> tuple[int, Literal["manual", "detected"]]:
        """Resolve the effective DPI and source mode from the combobox.

        Returns:
            Tuple of selected DPI value and selection mode.
        """
        dpi_choices = self._get_configured_dpi_choices()
        raw_value = str(self._dpi_choice_var.get()).strip()
        detected_choice = (
            self._format_detected_dpi_choice(self._detected_dpi_value)
            if self._detected_dpi_value is not None
            else ""
        )
        if raw_value and detected_choice and raw_value == detected_choice:
            return int(self._detected_dpi_value), "detected"

        try:
            resolved_dpi = int(raw_value)
        except (TypeError, ValueError):
            resolved_dpi = _MAIN_TAB_DEFAULT_DPI

        if resolved_dpi not in dpi_choices:
            resolved_dpi = _MAIN_TAB_DEFAULT_DPI
        return resolved_dpi, "manual"

    def _sync_dpi_combo_choices(self, preserve_current: bool = True) -> None:
        """Refresh the DPI combobox choices from current file selections.

        Args:
            preserve_current: Whether the current combobox intent should be kept.
        """
        previous_detected_choice = (
            self._format_detected_dpi_choice(self._detected_dpi_value)
            if self._detected_dpi_value is not None
            else ""
        )
        current_choice = str(self._dpi_choice_var.get()).strip()
        saved_mode = str(self.settings.get_setting("setted_dpi_mode", "detected") or "detected").strip().lower()
        self._detected_dpi_value = self._resolve_detected_dpi_from_selected_files()

        dpi_choices = self._get_configured_dpi_choices()
        values = [str(value) for value in dpi_choices]
        detected_choice = None
        if self._detected_dpi_value is not None:
            detected_choice = self._format_detected_dpi_choice(self._detected_dpi_value)
            values.append(detected_choice)

        target_choice = ""
        if preserve_current and current_choice:
            if current_choice == previous_detected_choice:
                target_choice = detected_choice or str(_MAIN_TAB_DEFAULT_DPI)
            elif current_choice == str(_MAIN_TAB_DEFAULT_DPI) and detected_choice is not None and saved_mode == "detected":
                target_choice = detected_choice
            elif current_choice in values:
                target_choice = current_choice

        if not target_choice:
            saved_dpi = self._get_selected_dpi()
            if saved_mode == "detected":
                target_choice = detected_choice or str(_MAIN_TAB_DEFAULT_DPI)
            elif saved_dpi in dpi_choices:
                target_choice = str(saved_dpi)
            else:
                target_choice = str(_MAIN_TAB_DEFAULT_DPI)

        if self._dpi_combo is not None:
            self._dpi_combo.configure(values=values)
        self._dpi_choice_var.set(target_choice)

        resolved_dpi, _ = self._get_selected_dpi_from_control()
        self.selected_dpi_value = resolved_dpi
        self._conversion_dpi = resolved_dpi

    def _path_points_to_file(self, path_value: str) -> bool:
        """Return whether the given path points to an existing file.

        Args:
            path_value: Candidate path string.

        Returns:
            ``True`` when the path exists and is a file.
        """
        try:
            if not path_value:
                return False
            return Path(path_value).exists() and Path(path_value).is_file()
        except Exception:
            return False

    def _current_workspace_paths_signature(self) -> tuple[str, str]:
        """Return normalized base/comp PDF paths that would drive a workspace rebuild.

        Empty string for a side means that side does not select an existing file.

        Returns:
            ``(base_key, comp_key)`` suitable for comparing with
            :attr:`_workspace_paths_signature_cache`.
        """
        placeholder_pdf = message_manager.get_ui_message("U053")
        base_raw = (self.base_path.get() or "").strip()
        comp_raw = (self.comparison_path.get() or "").strip()
        b_key = ""
        if base_raw != placeholder_pdf and self._path_points_to_file(base_raw):
            b_key = normalize_host_path(base_raw)
        c_key = ""
        if comp_raw != placeholder_pdf and self._path_points_to_file(comp_raw):
            c_key = normalize_host_path(comp_raw)
        return (b_key, c_key)

    def _ensure_transform_slots(self, target_length: int) -> None:
        """Resize transform arrays to match the current page count.

        Args:
            target_length: Required transform list length.
        """
        base_default = pack_transform6(0.0, 0.0, 0.0, self._base_preferred_preview_scale, 0, 0)
        comp_default = pack_transform6(0.0, 0.0, 0.0, self._comp_preferred_preview_scale, 0, 0)
        while len(self.base_transform_data) < len(self.base_pages):
            self.base_transform_data.append(base_default)
        while len(self.comp_transform_data) < len(self.comp_pages):
            self.comp_transform_data.append(comp_default)
        while len(self._base_export_transform_overrides) < len(self.base_pages):
            self._base_export_transform_overrides.append({})
        while len(self._comp_export_transform_overrides) < len(self.comp_pages):
            self._comp_export_transform_overrides.append({})
        self.base_transform_data = self.base_transform_data[: len(self.base_pages)]
        self.comp_transform_data = self.comp_transform_data[: len(self.comp_pages)]
        self._base_export_transform_overrides = self._base_export_transform_overrides[: len(self.base_pages)]
        self._comp_export_transform_overrides = self._comp_export_transform_overrides[: len(self.comp_pages)]
        if target_length <= 0:
            self.base_transform_data = []
            self.comp_transform_data = []
            self._base_export_transform_overrides = []
            self._comp_export_transform_overrides = []

    def _apply_export_transform_overrides_for_current_page(
        self,
        tx: float,
        ty: float,
        scale: float,
        changed_fields: set[str],
    ) -> None:
        """Store explicit export overrides for the active page.

        Args:
            tx: Current X translation.
            ty: Current Y translation.
            scale: Current preview scale.
            changed_fields: Explicitly edited transform field names.
        """
        export_fields = {field_name for field_name in changed_fields if field_name in {"tx", "ty", "scale"}}
        if not export_fields:
            return

        # Main processing: only entry-confirmed XY and scale values should affect saved output.
        for override_list in (self._base_export_transform_overrides, self._comp_export_transform_overrides):
            if not (0 <= self.current_page_index < len(override_list)):
                continue
            updated_override = dict(override_list[self.current_page_index])
            if "tx" in export_fields:
                updated_override["tx"] = float(tx)
            if "ty" in export_fields:
                updated_override["ty"] = float(ty)
            if "scale" in export_fields:
                updated_override["scale"] = max(0.01, float(scale))
            override_list[self.current_page_index] = updated_override

    def _propagate_export_overrides_to_all_pages(self, changed_fields: set[str]) -> None:
        """Propagate explicit export overrides when batch edit is enabled.

        Args:
            changed_fields: Explicitly edited transform field names.
        """
        export_fields = {field_name for field_name in changed_fields if field_name in {"tx", "ty", "scale"}}
        if not export_fields:
            return
        if self.page_control_frame is None or not self.page_control_frame.is_batch_edit_checked():
            return

        # Main processing: keep saved-output overrides aligned with batch-applied transform entry edits.
        for override_list in (self._base_export_transform_overrides, self._comp_export_transform_overrides):
            if not override_list or not (0 <= self.current_page_index < len(override_list)):
                continue
            current_override = dict(override_list[self.current_page_index])
            for index in range(len(override_list)):
                if index == self.current_page_index:
                    continue
                next_override = dict(override_list[index])
                for field_name in export_fields:
                    if field_name in current_override:
                        next_override[field_name] = current_override[field_name]
                override_list[index] = next_override

    def _build_export_transform_data(
        self,
        preview_transform_data: List[tuple[float, float, float, float]],
        export_override_data: List[Dict[str, float]],
    ) -> List[tuple[float, float, float, float]]:
        """Build export transforms from preview rotations and explicit export offsets.

        Args:
            preview_transform_data: Current preview transforms.
            export_override_data: Explicit export-only XY overrides.

        Returns:
            Export transform tuples.
        """
        resolved_export_transforms: List[tuple[float, float, float, float]] = []
        for page_index, raw_t in enumerate(preview_transform_data):
            rotation, _tx, _ty, _scale, _fh, _fv = as_transform6(raw_t)
            export_override = export_override_data[page_index] if page_index < len(export_override_data) else {}
            resolved_export_transforms.append(
                (
                    float(rotation),
                    float(export_override.get("tx", 0.0)),
                    float(export_override.get("ty", 0.0)),
                    1.0,
                )
            )
        return resolved_export_transforms

    def _get_or_create_converter(
        self, pdf_path: str, name_flag: str
    ) -> tuple[BaseImageConverter, FilePathInfo]:
        """Create or reuse a workspace input converter for the requested side.

        Args:
            pdf_path: Source file path (PDF, raster image, or SVG).
            name_flag: Side identifier, either ``"base"`` or ``"comp"``.

        Returns:
            Tuple of converter and file information.
        """
        existing_converter = self.base_pdf_converter if name_flag == "base" else self.comp_pdf_converter
        existing_info = self.base_file_info if name_flag == "base" else self.comp_file_info
        requested_path = Path(pdf_path)

        if (
            existing_converter is not None
            and existing_info is not None
            and existing_info.file_path == requested_path
        ):
            return existing_converter, existing_info

        file_info = FilePathInfo(
            file_path=requested_path,
            file_page_count=0,
            file_meta_info={},
            file_histogram_data=[],
        )
        converter = build_workspace_input_converter(
            file_info,
            program_mode=tool_settings.is_production_mode,
            name_flag=name_flag,
        )

        if name_flag == "base":
            self.base_pdf_converter = converter
            self.base_file_info = file_info
            self.base_pdf_metadata = dict(file_info.file_meta_info)
        else:
            self.comp_pdf_converter = converter
            self.comp_file_info = file_info
            self.comp_pdf_metadata = dict(file_info.file_meta_info)

        return converter, file_info

    def _sanitize_workspace_stem(self, source_name: str) -> str:
        """Return a filesystem-safe stem for temp workspace directories and files.

        Args:
            source_name: Original filename stem.

        Returns:
            Sanitized stem string.
        """
        safe_name = "".join(ch for ch in str(source_name) if ch.isalnum() or ch in "._- ()")
        safe_name = safe_name.strip().replace(" ", "_")
        return safe_name or "file"

    def _create_unique_directory_path(self, parent_dir: Path, base_name: str) -> Path:
        """Create and return a unique directory path under the target parent directory.

        Args:
            parent_dir: Parent directory.
            base_name: Desired directory name.

        Returns:
            Newly created unique directory path.
        """
        parent_dir.mkdir(parents=True, exist_ok=True)
        candidate_dir = parent_dir / base_name
        if not candidate_dir.exists():
            candidate_dir.mkdir(parents=True, exist_ok=False)
            return candidate_dir

        suffix_index = 1
        while True:
            numbered_dir = parent_dir / f"{base_name}（{suffix_index}）"
            if not numbered_dir.exists():
                numbered_dir.mkdir(parents=True, exist_ok=False)
                return numbered_dir
            suffix_index += 1

    def _create_unique_file_path(self, parent_dir: Path, base_name: str, extension: str) -> Path:
        """Return a unique file path under the target parent directory.

        Args:
            parent_dir: Parent directory.
            base_name: Desired filename stem.
            extension: Desired extension including dot.

        Returns:
            Unique file path that does not exist yet.
        """
        return create_unique_file_path(parent_dir, base_name, extension)

    def _create_workspace_temp_dir(self, pdf_path: str, name_flag: str) -> Path:
        """Create a unique temp directory for one side of the comparison workspace.

        Parent root is ``get_temp_dir()`` / ``tool_settings.TEMP_DIR``: under the project
        in development, and under ``%TEMP%\\pdfDiffChecker\\temp`` when running as a
        packaged Windows executable.

        Args:
            pdf_path: Source PDF path.
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Newly created unique workspace directory.
        """
        temp_root = Path(get_temp_dir())
        source_stem = self._sanitize_workspace_stem(Path(pdf_path).stem)
        workspace_dir_name = f"{source_stem}_{name_flag}"
        return self._create_unique_directory_path(temp_root, workspace_dir_name)

    def _build_page_record(self, page_path: Path, source_page_number: Optional[int], is_blank: bool) -> Dict[str, Any]:
        """Build in-memory page metadata for one workspace page.

        Args:
            page_path: Stored PNG path.
            source_page_number: Original PDF page number, or ``None`` for inserted blanks.
            is_blank: Whether this page was generated as a blank page.

        Returns:
            Dictionary describing the workspace page.
        """
        return {
            "path": page_path,
            "filename": page_path.name,
            "source_page_number": source_page_number,
            "is_blank": is_blank,
        }

    def _copy_workspace_pages_to_temp(
        self,
        source_page_paths: List[Path],
        pdf_path: str,
        name_flag: str,
        workspace_dir: Optional[Path] = None,
    ) -> tuple[List[Path], List[Dict[str, Any]], Path]:
        """Build workspace page records from already converted PNG files.

        Args:
            source_page_paths: Converted PNG paths from the converter cache.
            pdf_path: Source PDF path.
            name_flag: Either ``"base"`` or ``"comp"``.
            workspace_dir: Optional existing directory holding the converted pages.

        Returns:
            Tuple of page paths, page records, and the active workspace directory.
        """
        resolved_workspace_dir = workspace_dir
        if resolved_workspace_dir is None:
            if source_page_paths:
                resolved_workspace_dir = Path(source_page_paths[0]).parent
            else:
                resolved_workspace_dir = self._create_workspace_temp_dir(pdf_path, name_flag)

        workspace_page_paths: List[Path] = []
        page_records: List[Dict[str, Any]] = []

        for page_index, source_page_path in enumerate(source_page_paths, start=1):
            workspace_page_paths.append(source_page_path)
            page_records.append(self._build_page_record(source_page_path, page_index, False))

        return workspace_page_paths, page_records, resolved_workspace_dir

    def _sync_workspace_page_lists(self) -> None:
        """Synchronize public page/path lists from the current workspace records."""
        self.base_page_paths = [Path(record["path"]) for record in self._base_page_records]
        self.comp_page_paths = [Path(record["path"]) for record in self._comp_page_records]
        self.base_pages = [str(path) for path in self.base_page_paths]
        self.comp_pages = [str(path) for path in self.comp_page_paths]
        self.page_count = max(len(self.base_page_paths), len(self.comp_page_paths))

    def _get_workspace_record_list(self, name_flag: str) -> List[Dict[str, Any]]:
        """Return the mutable record list for the requested side.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Mutable page-record list for the requested side.
        """
        return self._base_page_records if name_flag == "base" else self._comp_page_records

    def _get_workspace_directory(self, name_flag: str) -> Optional[Path]:
        """Return the workspace temp directory for the requested side.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.

        Returns:
            Workspace directory path when available.
        """
        return self._base_workspace_dir if name_flag == "base" else self._comp_workspace_dir

    def _create_blank_workspace_page(self, workspace_dir: Path, page_size: tuple[int, int]) -> Path:
        """Create a blank PNG page inside the target workspace directory.

        Args:
            workspace_dir: Directory used for the workspace side.
            page_size: Page size ``(width, height)``.

        Returns:
            Saved blank PNG path.
        """
        blank_path = self._create_unique_file_path(workspace_dir, "blank_page", ".png")
        blank_image = Image.new("RGBA", page_size, (255, 255, 255, 255))
        blank_image.save(blank_path, format="PNG")
        return blank_path

    def _get_current_workspace_page_size(self) -> tuple[int, int]:
        """Return the current workspace page size using the displayed source images.

        Returns:
            Page size tuple ``(width, height)``.
        """
        candidate_paths: List[Path] = []
        if 0 <= self.current_page_index < len(self.base_page_paths):
            candidate_paths.append(self.base_page_paths[self.current_page_index])
        if 0 <= self.current_page_index < len(self.comp_page_paths):
            candidate_paths.append(self.comp_page_paths[self.current_page_index])
        candidate_paths.extend(self.base_page_paths[:1])
        candidate_paths.extend(self.comp_page_paths[:1])

        for candidate_path in candidate_paths:
            try:
                if candidate_path.exists():
                    with Image.open(candidate_path) as candidate_image:
                        return (candidate_image.width, candidate_image.height)
            except Exception:
                continue
        return (595, 842)

    def _build_default_modified_pdf_path(self) -> Path:
        """Return a unique output path for the edited PDF export.

        Returns:
            Unique PDF output path.

        Raises:
            ValueError: If the output folder is not valid.
        """
        output_dir = Path(str(self.output_path.get()).strip())
        if not output_dir.exists() or not output_dir.is_dir():
            raise ValueError("出力フォルダを選択してください。")

        source_candidates = [
            Path(str(self.base_path.get()).strip()),
            Path(str(self.comparison_path.get()).strip()),
        ]
        selected_stem = "output"
        for source_candidate in source_candidates:
            if source_candidate.suffix:
                selected_stem = source_candidate.stem
                break

        base_stem = self._sanitize_workspace_stem(selected_stem)
        return self._create_unique_file_path(output_dir, f"{base_stem}_modified", ".pdf")

    def _collect_png_page_paths(self, temp_dir: str, name_flag: str, page_count: int) -> List[Path]:
        """Collect converted PNG page paths from a converter output directory.

        Args:
            temp_dir: Directory where the converter wrote PNG files.
            name_flag: ``"base"`` or ``"comp"``.
            page_count: Expected page count.

        Returns:
            Existing PNG path list in page order.
        """
        page_paths: List[Path] = []
        temp_dir_path = Path(str(temp_dir))
        for page_num in range(1, page_count + 1):
            candidate = temp_dir_path / f"{name_flag}_{page_num:04d}.png"
            if candidate.exists():
                page_paths.append(candidate)
        return page_paths

    def _build_expected_png_page_paths(self, temp_dir: str, name_flag: str, page_count: int) -> List[Path]:
        """Build the expected PNG path list for every page in one converter temp dir.

        Args:
            temp_dir: Directory where the converter writes PNG files.
            name_flag: ``"base"`` or ``"comp"``.
            page_count: Total page count.

        Returns:
            List[Path]: Expected PNG paths in page order.
        """
        temp_dir_path = Path(str(temp_dir))
        return [temp_dir_path / f"{name_flag}_{page_num:04d}.png" for page_num in range(1, page_count + 1)]

    def _analyze_pdf_path(self, pdf_path: str, name_flag: str) -> Dict[str, Any]:
        """Analyze one selected PDF and return a compact summary.

        Args:
            pdf_path: Source PDF path.
            name_flag: ``"base"`` or ``"comp"``.

        Returns:
            Summary containing file path, page count, and protection flags.
        """
        converter, file_info = self._get_or_create_converter(pdf_path, name_flag)
        metadata = dict(file_info.file_meta_info)
        summary = {
            "path": str(file_info.file_path),
            "page_count": int(file_info.file_page_count),
            "copy_protected": bool(metadata.get("CopyProtected", metadata.get("Encrypted", False))),
            "temp_dir": str(converter._temp_dir),
        }
        if name_flag == "base":
            self.base_pdf_metadata = metadata
        else:
            self.comp_pdf_metadata = metadata
        return summary

    def _convert_pdf_for_workspace(
        self,
        pdf_path: str,
        name_flag: str,
        show_progress: bool = True,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        collect_all_pages: bool = False,
    ) -> List[Path]:
        """Convert a PDF to page PNGs and return the collected output paths.

        Args:
            pdf_path: Source PDF path.
            name_flag: ``"base"`` or ``"comp"``.
            show_progress: Whether to show the progress dialog while converting.
            start_page: Optional first page to render.
            end_page: Optional last page to render.
            collect_all_pages: Whether to return the full expected path list.

        Returns:
            Converted page path list.
        """
        converter, file_info = self._get_or_create_converter(pdf_path, name_flag)
        self._conversion_dpi = self._get_dpi_from_entry()
        render_kwargs: Dict[str, Any] = {"dpi": self._conversion_dpi}
        if start_page is not None:
            render_kwargs["start_page"] = int(start_page)
        if end_page is not None:
            render_kwargs["end_page"] = int(end_page)
        if show_progress:
            converter.process_with_progress_window(self.frame_main3, **render_kwargs)
        else:
            converter.convert_to_grayscale_pngs(**render_kwargs)
        if collect_all_pages:
            page_paths = self._build_expected_png_page_paths(
                temp_dir=str(converter._temp_dir),
                name_flag=name_flag,
                page_count=int(file_info.file_page_count),
            )
        else:
            page_paths = self._collect_png_page_paths(
                temp_dir=str(converter._temp_dir),
                name_flag=name_flag,
                page_count=int(file_info.file_page_count),
            )
        copied_page_paths, page_records, workspace_dir = self._copy_workspace_pages_to_temp(
            page_paths,
            pdf_path,
            name_flag,
            workspace_dir=Path(str(converter._temp_dir)),
        )
        if name_flag == "base":
            self.base_pdf_metadata = dict(file_info.file_meta_info)
            self._base_page_records = page_records
            self._base_workspace_dir = workspace_dir
        else:
            self.comp_pdf_metadata = dict(file_info.file_meta_info)
            self._comp_page_records = page_records
            self._comp_workspace_dir = workspace_dir
        return copied_page_paths

    def _refresh_operation_restriction_state(self) -> None:
        """Refresh whether transform operations should be enabled."""
        # Main processing: disable transform editing when either source is copy protected.
        base_protected = bool(self.base_pdf_metadata.get("CopyProtected", self.base_pdf_metadata.get("Encrypted", False)))
        comp_protected = bool(self.comp_pdf_metadata.get("CopyProtected", self.comp_pdf_metadata.get("Encrypted", False)))
        self._copy_protected = base_protected or comp_protected
        self._visual_adjustments_enabled = self._has_loaded_workspace_pages() and not self._copy_protected

        if self.page_control_frame is not None:
            try:
                self.page_control_frame.set_edit_buttons_enabled(self._has_loaded_workspace_pages() and not self._copy_protected)
            except Exception:
                pass

        if self.mouse_handler is not None:
            try:
                self.mouse_handler.set_operations_enabled(self._visual_adjustments_enabled)
            except Exception:
                pass

    def _cancel_pending_hi_res_preview(self) -> None:
        """Cancel a scheduled full-resolution redraw after interactive zoom."""
        aid = getattr(self, "_preview_hires_after_id", None)
        if aid is not None:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
            self._preview_hires_after_id = None

    def _flush_hi_res_preview(self) -> None:
        """Run a Lanczos-quality page draw after interactive zoom settles (see scheduler)."""
        self._preview_hires_after_id = None
        if not self._has_loaded_workspace_pages():
            return
        self._display_page(self.current_page_index, preview_fast_resize=False)

    def _schedule_interactive_preview_redraw(self) -> None:
        """Redraw immediately with fast scaling, then a sharper pass after a short idle."""
        self._cancel_pending_hi_res_preview()
        self._display_page(self.current_page_index, preview_fast_resize=True)

        def _deferred() -> None:
            self._flush_hi_res_preview()

        self._preview_hires_after_id = self.after(_PREVIEW_HIRES_DEBOUNCE_MS, _deferred)

    def _display_page(self, page_index: int, *, preview_fast_resize: bool = False) -> None:
        """Display one page of the converted comparison workspace.

        Args:
            page_index: Zero-based page index.
            preview_fast_resize: If True, use bilinear instead of Lanczos when applying
                scale to the page image (wheel / drag zoom). Geometry matches the slow
                path so the canvas does not jump between frames.
        """
        self._apply_preferred_preview_scale_to_page(page_index)
        if not self._has_loaded_workspace_pages():
            self._render_comparison_placeholder()
            return
        if not (0 <= page_index < self.page_count):
            self._show_status_feedback("Requested page is out of range.", False)
            return

        if self._workspace_preview_blocked:
            self._render_workspace_raster_blocked_canvas()
            return

        if page_index != self.current_page_index:
            self._commit_preview_keyboard_rotation()

        show_base_layer = bool(self._show_base_layer_var.get())
        show_comp_layer = bool(self._show_comp_layer_var.get())
        any_layer_visible = show_base_layer or show_comp_layer
        snap = self._preview_canvas_snap
        lod_inplace = (
            preview_fast_resize
            and any_layer_visible
            and snap is not None
            and snap[0] == page_index
            and snap[1] == show_base_layer
            and snap[2] == show_comp_layer
            and (not show_base_layer or self._base_canvas_image_id is not None)
            and (not show_comp_layer or self._comp_canvas_image_id is not None)
        )

        if not lod_inplace:
            try:
                self.canvas.delete("workspace")
                self.canvas.delete("pdf_image")
                self.canvas.delete("base_image")
                self.canvas.delete("comp_image")
                self.canvas.delete("diff_emphasis")
            except Exception:
                for _tag in (
                    "workspace",
                    "reference_grid",
                    "pdf_image",
                    "base_image",
                    "comp_image",
                    "diff_emphasis",
                ):
                    try:
                        self.canvas.delete(_tag)
                    except Exception:
                        pass
            self._base_canvas_image_id = None
            self._comp_canvas_image_id = None
            self._diff_emphasis_canvas_image_id = None
        else:
            try:
                self.canvas.delete("diff_emphasis")
            except Exception:
                pass
            self._diff_emphasis_canvas_image_id = None

        base_path = self._get_display_page_path(self.base_page_paths, page_index)
        comp_path = self._get_display_page_path(self.comp_page_paths, page_index)
        base_image: Optional[Image.Image] = None
        comp_image: Optional[Image.Image] = None
        comp_image_for_diff: Optional[Image.Image] = None

        try:
            if base_path is not None and base_path.exists():
                ow, oh = self._get_source_page_pixel_size(base_path)
                self._original_page_width = ow
                self._original_page_height = oh
                base_image = self._processed_preview_image_for_display(
                    base_path, "base", None
                )
            elif comp_path is not None and comp_path.exists():
                ow, oh = self._get_source_page_pixel_size(comp_path)
                self._original_page_width = ow
                self._original_page_height = oh
            if comp_path is not None and comp_path.exists():
                comp_image = self._processed_preview_image_for_display(
                    comp_path, "comp", None
                )
        except WorkspaceRasterTooLarge:
            self._render_workspace_raster_blocked_canvas()
            return

        if base_image is None and comp_image is None:
            self._show_status_feedback("Rendered page images could not be found.", False)
            return

        if self.mouse_handler is not None and hasattr(self.mouse_handler, "set_original_image_size"):
            try:
                self.mouse_handler.set_original_image_size(
                    int(self._original_page_width), int(self._original_page_height)
                )
            except Exception:
                pass

        _lod_fast = preview_fast_resize
        if base_image is not None and page_index < len(self.base_transform_data):
            base_t = self._transform_tuple_for_preview_render(
                page_index, self.base_transform_data[page_index], is_base_layer=True
            )
            base_image = self._apply_transform_to_image(
                base_image, base_t, fast_resize=_lod_fast
            )
        if comp_image is not None and page_index < len(self.comp_transform_data):
            comp_t = self._transform_tuple_for_preview_render(
                page_index, self.comp_transform_data[page_index], is_base_layer=False
            )
            comp_image = self._apply_transform_to_image(
                comp_image, comp_t, fast_resize=_lod_fast
            )

        self._base_photo_image = None
        self._comp_photo_image = None

        if base_image is not None and show_base_layer:
            _, translate_x, translate_y, _, _, _ = as_transform6(self.base_transform_data[page_index])
            self._base_photo_image = ImageTk.PhotoImage(base_image)
            if lod_inplace and self._base_canvas_image_id is not None:
                try:
                    self.canvas.itemconfig(self._base_canvas_image_id, image=self._base_photo_image)
                    self.canvas.coords(self._base_canvas_image_id, int(translate_x), int(translate_y))
                except Exception:
                    self._base_canvas_image_id = self.canvas.create_image(
                        int(translate_x),
                        int(translate_y),
                        anchor="nw",
                        image=self._base_photo_image,
                        tags=("pdf_image", "base_image"),
                    )
            else:
                self._base_canvas_image_id = self.canvas.create_image(
                    int(translate_x),
                    int(translate_y),
                    anchor="nw",
                    image=self._base_photo_image,
                    tags=("pdf_image", "base_image"),
                )

        if comp_image is not None and show_comp_layer:
            # Main processing: only soften the comparison layer while both layers are shown.
            if comp_image.mode != "RGBA":
                comp_image = comp_image.convert("RGBA")
            comp_image_for_diff = comp_image.copy()
            overlay_image = comp_image.copy()
            if show_base_layer:
                alpha_channel = overlay_image.getchannel("A")
                softened_alpha = alpha_channel.point(lambda value: int(value * 150 / 255))
                overlay_image.putalpha(softened_alpha)
            _, translate_x, translate_y, _, _, _ = as_transform6(self.comp_transform_data[page_index])
            self._comp_photo_image = ImageTk.PhotoImage(overlay_image)
            if lod_inplace and self._comp_canvas_image_id is not None:
                try:
                    self.canvas.itemconfig(self._comp_canvas_image_id, image=self._comp_photo_image)
                    self.canvas.coords(self._comp_canvas_image_id, int(translate_x), int(translate_y))
                except Exception:
                    self._comp_canvas_image_id = self.canvas.create_image(
                        int(translate_x),
                        int(translate_y),
                        anchor="nw",
                        image=self._comp_photo_image,
                        tags=("pdf_image", "comp_image"),
                    )
            else:
                self._comp_canvas_image_id = self.canvas.create_image(
                    int(translate_x),
                    int(translate_y),
                    anchor="nw",
                    image=self._comp_photo_image,
                    tags=("pdf_image", "comp_image"),
                )

        if (
            show_base_layer
            and show_comp_layer
            and base_path is not None
            and base_path.exists()
            and comp_path is not None
            and comp_path.exists()
            and page_index < len(self.base_transform_data)
            and page_index < len(self.comp_transform_data)
        ):
            self._display_diff_overlay_from_cache(
                page_index, base_path, comp_path, fast_resize=preview_fast_resize
            )

        reference_bbox = self.canvas.bbox("pdf_image")
        self._draw_reference_grid(reference_bbox, raise_above_images=True)
        try:
            self.canvas.tag_raise("diff_emphasis")
        except Exception:
            pass

        if not show_base_layer and not show_comp_layer:
            self.canvas.create_text(
                max(self.canvas.winfo_width() // 2, 200),
                max(self.canvas.winfo_height() // 2, 120),
                text="Base/Comparison layers are both hidden.",
                fill=ColorThemeManager.get_instance().get_current_theme().get("Frame", {}).get("fg", "#000000"),
                font=("", 11, "bold"),
                tags=("workspace",),
            )

        self._draw_canvas_footer_guide()

        try:
            self._set_main_canvas_scrollregion_from_pdf_image()
        except Exception:
            try:
                self.canvas.config(scrollregion=self.canvas.bbox("all"))
            except Exception:
                pass

        self.current_page_index = page_index

        self._last_preview_ok_dpi = int(self.selected_dpi_value)
        self._workspace_preview_blocked = False
        self._workspace_raster_limit_dialog_shown = False

        self._preview_canvas_snap = (page_index, show_base_layer, show_comp_layer)

        visible_layers = self._get_visible_layer_state()

        self._sync_visualized_image_state()

        if self.mouse_handler is not None:
            self.mouse_handler.update_state(
                current_page_index=page_index,
                visible_layers=visible_layers,
            )
            if hasattr(self.mouse_handler, "refresh_overlay_positions"):
                self.mouse_handler.refresh_overlay_positions()

        try:
            self.canvas.tag_raise("overlay_shortcut_help")
        except Exception:
            pass

        if self.page_control_frame is not None:
            # Always sync the page entry: callers often set current_page_index before
            # _display_page (e.g. next/prev/page entry), so comparing "previous" here
            # skipped updates and left "1 / N" stuck.
            self.page_control_frame.update_page_label(page_index, self.page_count)
            self._sync_transform_display_to_panel()

        if not preview_fast_resize:
            try:
                self.canvas.focus_set()
            except Exception:
                pass

    def _get_active_transform(self) -> tuple[float, float, float, float]:
        """Return the transform currently shown in the placeholder canvas.

        Returns:
            Transform tuple ``(rotation, tx, ty, scale)`` for the page-control UI (mirrors omitted).
        """
        d = float(self._preview_keyboard_rotation_delta) if abs(self._preview_keyboard_rotation_delta) > 1e-9 else 0.0
        idx = self.current_page_index
        show_b = bool(self._show_base_layer_var.get())
        show_c = bool(self._show_comp_layer_var.get())
        if show_b and self.base_transform_data and idx < len(self.base_transform_data):
            r, tx, ty, s, _fh, _fv = as_transform6(self.base_transform_data[idx])
            return (r + d, tx, ty, s)
        if show_c and self.comp_transform_data and idx < len(self.comp_transform_data):
            r, tx, ty, s, _fh, _fv = as_transform6(self.comp_transform_data[idx])
            return (r + d, tx, ty, s)
        if self.base_transform_data and idx < len(self.base_transform_data):
            r, tx, ty, s, _fh, _fv = as_transform6(self.base_transform_data[idx])
            return (r, tx, ty, s)
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            r, tx, ty, s, _fh, _fv = as_transform6(self.comp_transform_data[idx])
            return (r, tx, ty, s)
        return (0.0, 0.0, 0.0, 1.0)

    def _get_single_layer_transform(
        self,
        transform_data: list,
        *,
        add_keyboard_delta: bool = True,
    ) -> tuple[float, float, float, float]:
        """Return ``(rotation, tx, ty, scale)`` for the current page of one layer.

        Args:
            transform_data: Either ``self.base_transform_data`` or
                ``self.comp_transform_data``.
            add_keyboard_delta: When True include any pending Ctrl+Shift
                preview rotation delta.

        Returns:
            4-tuple ``(rotation, tx, ty, scale)`` for the UI.
        """
        idx = self.current_page_index
        d = (
            float(self._preview_keyboard_rotation_delta)
            if add_keyboard_delta and abs(self._preview_keyboard_rotation_delta) > 1e-9
            else 0.0
        )
        if transform_data and idx < len(transform_data):
            r, tx, ty, s, _fh, _fv = as_transform6(transform_data[idx])
            return (r + d, tx, ty, s)
        return (0.0, 0.0, 0.0, 1.0)

    def _sync_transform_display_to_panel(self) -> None:
        """Push the current base and comp transform values to the page-control panel.

        In dual-layer mode the base and comp sections are updated individually.
        Falls back to the legacy single ``update_transform_info`` call otherwise.
        """
        if self.page_control_frame is None:
            return
        if hasattr(self.page_control_frame, "update_base_transform_info"):
            b_r, b_tx, b_ty, b_s = self._get_single_layer_transform(
                self.base_transform_data,
                add_keyboard_delta=bool(self._show_base_layer_var.get()),
            )
            c_r, c_tx, c_ty, c_s = self._get_single_layer_transform(
                self.comp_transform_data,
                add_keyboard_delta=bool(self._show_comp_layer_var.get()),
            )
            self.page_control_frame.update_base_transform_info(b_r, b_tx, b_ty, b_s)
            self.page_control_frame.update_comp_transform_info(c_r, c_tx, c_ty, c_s)
        else:
            rotation, tx, ty, scale = self._get_active_transform()
            self.page_control_frame.update_transform_info(rotation, tx, ty, scale)

    def _transform_tuple_for_preview_render(
        self,
        page_index: int,
        transform_tuple: tuple[float, ...],
        *,
        is_base_layer: bool,
    ) -> tuple[float, float, float, float, int, int]:
        """Build a transform tuple including pending Ctrl+Shift preview rotation for drawing.

        Args:
            page_index: Page index being rendered.
            transform_tuple: Stored transform (4- or 6-tuple).
            is_base_layer: True when rendering the base layer.

        Returns:
            Tuple to pass to :meth:`_apply_transform_to_image` for this draw pass.
        """
        r, x, y, s, fh, fv = as_transform6(transform_tuple)
        if page_index != self.current_page_index or abs(self._preview_keyboard_rotation_delta) < 1e-9:
            return pack_transform6(r, x, y, s, fh, fv)
        if is_base_layer and not bool(self._show_base_layer_var.get()):
            return pack_transform6(r, x, y, s, fh, fv)
        if not is_base_layer and not bool(self._show_comp_layer_var.get()):
            return pack_transform6(r, x, y, s, fh, fv)
        return pack_transform6(r + float(self._preview_keyboard_rotation_delta), x, y, s, fh, fv)

    def _commit_preview_keyboard_rotation(self) -> None:
        """Merge pending Ctrl+Shift preview rotation into stored transform data (then propagate if batch)."""
        delta = float(self._preview_keyboard_rotation_delta)
        if abs(delta) < 1e-9:
            return
        self._preview_keyboard_rotation_delta = 0.0
        idx = self.current_page_index
        if not self._has_loaded_workspace_pages() or idx < 0:
            return
        if bool(self._show_base_layer_var.get()) and idx < len(self.base_transform_data):
            r, x, y, s, fh, fv = as_transform6(self.base_transform_data[idx])
            self.base_transform_data[idx] = pack_transform6(r + delta, x, y, s, fh, fv)
        if bool(self._show_comp_layer_var.get()) and idx < len(self.comp_transform_data):
            r, x, y, s, fh, fv = as_transform6(self.comp_transform_data[idx])
            self.comp_transform_data[idx] = pack_transform6(r + delta, x, y, s, fh, fv)
        self._on_transform_update()

    def _clear_preview_keyboard_rotation_only(self) -> None:
        """Discard pending Ctrl+Shift preview rotation without writing it to transform data."""
        self._preview_keyboard_rotation_delta = 0.0

    def _on_main_preview_keyboard_rotate_right(self, event: Optional[tk.Event] = None) -> str | None:
        """Handle Ctrl+Shift+R: preview +90° (committed on click, page change, or other transform shortcuts)."""
        _ = event
        if not self._has_loaded_workspace_pages():
            return "break"
        if not self._visual_adjustments_enabled or self._copy_protected:
            return "break"
        self._preview_keyboard_rotation_delta += 90.0
        self._refresh_current_page_view()
        if self.mouse_handler is not None:
            self.mouse_handler._show_notification(message_manager.get_message("M063"))
        return "break"

    def _on_main_preview_keyboard_rotate_left(self, event: Optional[tk.Event] = None) -> str | None:
        """Handle Ctrl+Shift+L: preview −90° (committed on click, page change, or other transform shortcuts)."""
        _ = event
        if not self._has_loaded_workspace_pages():
            return "break"
        if not self._visual_adjustments_enabled or self._copy_protected:
            return "break"
        self._preview_keyboard_rotation_delta -= 90.0
        self._refresh_current_page_view()
        if self.mouse_handler is not None:
            self.mouse_handler._show_notification(message_manager.get_message("M064"))
        return "break"

    def _on_main_canvas_escape_preview(self, event: Optional[tk.Event] = None) -> str | None:
        """Discard pending Ctrl+Shift preview rotation when Escape is pressed on the canvas."""
        _ = event
        if abs(self._preview_keyboard_rotation_delta) < 1e-9:
            return "break"
        self._clear_preview_keyboard_rotation_only()
        self._refresh_current_page_view()
        return "break"

    def _refresh_workspace_state(self) -> None:
        """Refresh comparison workspace state from the selected paths."""
        # Main processing: reset to the pre-conversion state whenever the selected source paths change.
        self._clear_loaded_workspace_data()
        self._sync_dpi_combo_choices(preserve_current=True)
        placeholder_pdf = message_manager.get_ui_message("U053")
        base_raw = (self.base_path.get() or "").strip()
        comp_raw = (self.comparison_path.get() or "").strip()
        base_selected = (
            base_raw != placeholder_pdf
            and self._path_points_to_file(base_raw)
        )
        comparison_selected = (
            comp_raw != placeholder_pdf
            and self._path_points_to_file(comp_raw)
        )

        if not base_selected and not comparison_selected:
            self.base_pages = []
            self.comp_pages = []
            self.page_count = 0
            self.current_page_index = 0
            self._workspace_paths_signature_cache = ("", "")
            self._create_page_control_frame(0)
            self._apply_path_entry_activity_style()
            self._setup_mouse_events(0)
            self._render_comparison_placeholder()
            self._refresh_interaction_state()
            return

        try:
            self._preview_render_generation += 1
            current_generation = self._preview_render_generation
            resolved_dpi = self._get_dpi_from_entry()
            background_tasks: List[tuple[str, str, int, int]] = []

            self.base_page_paths = []
            self.comp_page_paths = []

            if base_selected:
                self.base_page_paths = self._convert_pdf_for_workspace(
                    self.base_path.get(),
                    "base",
                    show_progress=False,
                    start_page=1,
                    end_page=1,
                    collect_all_pages=True,
                )
                if self.base_file_info is not None and int(self.base_file_info.file_page_count) > 1:
                    background_tasks.append((self.base_path.get(), "base", 2, int(self.base_file_info.file_page_count)))

            if comparison_selected:
                self.comp_page_paths = self._convert_pdf_for_workspace(
                    self.comparison_path.get(),
                    "comp",
                    show_progress=False,
                    start_page=1,
                    end_page=1,
                    collect_all_pages=True,
                )
                if self.comp_file_info is not None and int(self.comp_file_info.file_page_count) > 1:
                    background_tasks.append((self.comparison_path.get(), "comp", 2, int(self.comp_file_info.file_page_count)))

            self._sync_workspace_page_lists()
            self.current_page_index = 0
            self._ensure_transform_slots(self.page_count)
            self._create_page_control_frame(self.page_count)
            self._apply_path_entry_activity_style()
            self._refresh_operation_restriction_state()
            self._setup_mouse_events(self.page_count)
            if self._has_loaded_workspace_pages():
                self._display_page(self.current_page_index)
            else:
                self._render_comparison_placeholder()
            self._refresh_interaction_state()
            self._start_background_preview_render(background_tasks, resolved_dpi, current_generation)
            self._workspace_paths_signature_cache = self._current_workspace_paths_signature()
        except Exception as exc:
            logger.error(message_manager.get_log_message("L080", str(exc)))
            self._show_status_feedback(f"プレビューの更新に失敗しました: {exc}", False)
            self._clear_loaded_workspace_data()
            self._create_page_control_frame(0)
            self._apply_path_entry_activity_style()
            self._setup_mouse_events(0)
            self._render_comparison_placeholder()
            self._refresh_interaction_state()

    def _render_comparison_placeholder(self) -> None:
        """Render the current minimal comparison workspace on the canvas."""
        if not hasattr(self, "canvas"):
            return

        # Main processing: clear workspace drawings only; keep canvas shortcut overlay items.
        for _tag in ("workspace", "reference_grid", "pdf_image", "base_image", "comp_image", "diff_emphasis"):
            try:
                self.canvas.delete(_tag)
            except Exception:
                pass
        self._base_canvas_image_id = None
        self._comp_canvas_image_id = None
        self._diff_emphasis_canvas_image_id = None
        self._preview_canvas_snap = None
        canvas_width = max(self.canvas.winfo_width(), 720)
        canvas_height = max(self.canvas.winfo_height(), 420)
        active_theme = ColorThemeManager.get_instance().get_current_theme()
        frame_theme = active_theme.get("Frame", {})
        canvas_bg = CreateComparisonFileApp._PREVIEW_CANVAS_BACKGROUND
        text_fg = frame_theme.get("fg", "#000000")
        accent_fg = active_theme.get("process_button", {}).get("fg", text_fg)
        border_fg = active_theme.get("canvas", {}).get("highlightbackground", "#6c6c6c")

        self.canvas.configure(bg=canvas_bg)
        self.canvas.create_rectangle(
            16,
            16,
            canvas_width - 16,
            canvas_height - 16,
            outline=border_fg,
            width=2,
            tags=("workspace",),
        )

        self._draw_reference_grid((16, 16, canvas_width - 16, canvas_height - 16), raise_above_images=False)

        title_text = "下のプレビュー"
        self.canvas.create_text(
            32,
            36,
            anchor="nw",
            text=title_text,
            fill=accent_fg,
            font=("", 12, "bold"),
            tags=("workspace",),
        )

        page_display = self.current_page_index + 1 if self.page_count > 0 else 0
        rotation, tx, ty, scale = self._get_active_transform()
        placeholder_pdf = message_manager.get_ui_message("U053")
        base_pv = (
            self._base_file_path_entry.path_var.get().strip()
            if hasattr(self, "_base_file_path_entry")
            else self.base_path.get()
        )
        comp_pv = (
            self._comparison_file_path_entry.path_var.get().strip()
            if hasattr(self, "_comparison_file_path_entry")
            else self.comparison_path.get()
        )

        body_lines = [
            f"元PDF: {self._placeholder_status_path_line(base_pv)}",
            f"比較PDF: {self._placeholder_status_path_line(comp_pv)}",
            f"出力フォルダ: {self.output_path.get()}",
            f"ページ: {page_display} / {self.page_count}",
            f"変形: 回転={rotation:.1f}, X={tx:.1f}, Y={ty:.1f}, 拡大率={scale:.3f}",
        ]
        if self.status_var.get():
            body_lines.append("")
            body_lines.append(f"状態: {self.status_var.get()}")

        self.canvas.create_text(
            32,
            74,
            anchor="nw",
            text="\n".join(body_lines),
            fill=text_fg,
            width=max(canvas_width - 72, 320),
            font=("", 10),
            tags=("workspace",),
        )
        self._draw_canvas_footer_guide()

        try:
            self.canvas.tag_raise("overlay_shortcut_help")
        except Exception:
            pass

    def _create_page_control_frame(self, page_count: int) -> None:
        """Create or recreate the page control frame for the current workspace.

        Args:
            page_count: Number of pages currently available in the workspace.
        """
        # Main processing: recreate the page control so callbacks and list references stay aligned.
        if self.page_control_frame is not None:
            try:
                self.page_control_frame.destroy()
            except Exception:
                pass
            self.page_control_frame = None

        _pcf_parent = self._page_ctrl_inner if self._page_ctrl_inner is not None else self.frame_main3
        self.page_control_frame = PageControlFrame(
            parent=_pcf_parent,
            color_key="page_control",
            base_pages=self.base_pages,
            comp_pages=self.comp_pages,
            base_transform_data=self.base_transform_data,
            comp_transform_data=self.comp_transform_data,
            visualized_image=self.visualized_image,
            page_amount_limit=max(1, page_count),
            on_prev_page=self._on_prev_page,
            on_next_page=self._on_next_page,
            on_insert_blank=self._on_insert_blank_page,
            on_delete_page=self._on_delete_page,
            on_export=self._on_pdf_save_click,
            on_page_entry=self._on_page_entry,
            on_transform_value_change=self._on_transform_value_input,
            initial_batch_edit_checked=self._batch_edit_selected,
            on_batch_edit_toggle=self._on_batch_edit_toggle,
            on_base_transform_value_change=self._on_base_transform_value_input,
            on_comp_transform_value_change=self._on_comp_transform_value_input,
            on_auto_align_frames=self._on_auto_align_frames,
            on_auto_align_content=self._on_auto_align_content,
            on_auto_align_priority=self._on_auto_align_priority,
        )
        if self._page_ctrl_inner is not None:
            self.page_control_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        else:
            self.page_control_frame.grid(row=0, column=1, padx=(4, 6), pady=0, sticky="nsew")
        self.page_control_frame.update_page_label(page_count - 1 if page_count == 0 else self.current_page_index, page_count)
        self.page_control_frame.set_workspace_controls_enabled(self._has_loaded_workspace_pages() and not self._copy_protected)
        self.page_control_frame.set_edit_buttons_enabled(self._has_loaded_workspace_pages() and not self._copy_protected)
        self._sync_batch_edit_state()

    def _setup_mouse_events(self, page_count: int) -> None:
        """Set up mouse handling for the minimal comparison workspace.

        Args:
            page_count: Number of pages currently available.
        """
        # Main processing: only enable transform shortcuts when a placeholder page is present.
        self.canvas.unbind("<Button-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        self.canvas.unbind("<Button-3>")
        self.canvas.unbind("<MouseWheel>")
        self.canvas.unbind("<Button-4>")
        self.canvas.unbind("<Button-5>")

        if page_count <= 0:
            try:
                self.canvas.delete("overlay_shortcut_help")
            except Exception:
                pass
            self.mouse_handler = None
            return

        layer_transform_data: dict[int, list[tuple[float, ...]]] = {}
        visible_layers: dict[int, bool] = {}
        if self.base_transform_data:
            layer_transform_data[0] = self.base_transform_data
            visible_layers[0] = True
        if self.comp_transform_data:
            layer_transform_data[1] = self.comp_transform_data
            visible_layers[1] = True

        self.mouse_handler = MouseEventHandler(
            layer_transform_data=layer_transform_data,
            current_page_index=self.current_page_index,
            visible_layers=visible_layers,
            on_transform_update=self._on_transform_update,
            on_live_translation_update=self._update_canvas_translation_preview,
            operations_enabled=self._visual_adjustments_enabled,
            commit_keyboard_preview_rotation=self._commit_preview_keyboard_rotation,
            clear_keyboard_preview_rotation=self._clear_preview_keyboard_rotation_only,
            on_transform_commit_no_propagate=self._on_transform_update_skip_batch_propagate,
            sheet_rotate_guard=self._can_main_sheet_rotate_dual_display,
            sheet_rotate_blocked_message_code="U177",
            preview_dpi_normalize=lambda: float(_MAIN_TAB_DEFAULT_DPI)
            / max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI)),
        )
        self.mouse_handler.attach_to_canvas(self.canvas)
        self.mouse_handler.update_state(
            current_page_index=self.current_page_index,
            visible_layers=visible_layers,
        )

        def _main_canvas_button1(event: tk.Event) -> None:
            self._commit_preview_keyboard_rotation()
            self.canvas.focus_set()
            if self.mouse_handler is not None:
                self.mouse_handler.on_mouse_down(event)

        self.canvas.bind("<Button-1>", _main_canvas_button1)
        self.canvas.bind("<B1-Motion>", lambda e: self.mouse_handler.on_mouse_drag(e) if self.mouse_handler else None)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self.mouse_handler.on_mouse_up(e) if self.mouse_handler else None)
        self.canvas.bind("<Button-3>", lambda e: self.mouse_handler.on_right_click(e) if self.mouse_handler and hasattr(self.mouse_handler, "on_right_click") else None)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)
        self.canvas.bind("<Configure>", self._on_main_canvas_configure, add="+")

        self.canvas.bind("<Control-Shift-r>", self._on_main_preview_keyboard_rotate_right)
        self.canvas.bind("<Control-Shift-R>", self._on_main_preview_keyboard_rotate_right)
        self.canvas.bind("<Control-Shift-l>", self._on_main_preview_keyboard_rotate_left)
        self.canvas.bind("<Control-Shift-L>", self._on_main_preview_keyboard_rotate_left)
        self.canvas.bind("<Escape>", self._on_main_canvas_escape_preview)

    def _on_main_canvas_configure(self, event: Any) -> None:
        """Keep the shortcut footer guide sized and positioned when the canvas resizes.

        Args:
            event: Tkinter configure event (unused).
        """
        _ = event
        self.schedule_canvas_footer_reposition()
        try:
            if self.mouse_handler is not None:
                self.mouse_handler.refresh_overlay_positions()
        except Exception:
            pass
        try:
            if self._has_loaded_workspace_pages():
                self._set_main_canvas_scrollregion_from_pdf_image()
                self._draw_reference_grid(
                    self.canvas.bbox("pdf_image"),
                    raise_above_images=True,
                )
            else:
                cw = max(self.canvas.winfo_width(), 720)
                ch = max(self.canvas.winfo_height(), 420)
                self._draw_reference_grid(
                    (16, 16, cw - 16, ch - 16),
                    raise_above_images=False,
                )
        except Exception:
            pass

    def _on_mouse_wheel(self, event: Any) -> None:
        """Forward mouse wheel events to the current mouse handler.

        Args:
            event: Mouse wheel event object.
        """
        if self.mouse_handler is None:
            return
        self.mouse_handler.on_mouse_wheel(event)

    def _on_prev_page(self) -> None:
        """Move to the previous placeholder page when available."""
        if self.page_count <= 0:
            self._show_status_feedback("下のプレビューはまだ準備できていません。", False)
            return
        if self.current_page_index > 0:
            self._commit_preview_keyboard_rotation()
            self.current_page_index -= 1
            self._ensure_preview_page_available(self.current_page_index)
            self._refresh_current_page_view(show_progress=True)

    def _on_next_page(self) -> None:
        """Move to the next placeholder page when available."""
        if self.page_count <= 0:
            self._show_status_feedback("下のプレビューはまだ準備できていません。", False)
            return
        if self.current_page_index < self.page_count - 1:
            self._commit_preview_keyboard_rotation()
            self.current_page_index += 1
            self._ensure_preview_page_available(self.current_page_index)
            self._refresh_current_page_view(show_progress=True)

    def _on_page_entry(self, event: tk.Event) -> None:
        """Jump to the requested page number in the minimal workspace.

        Args:
            event: Page-entry event.
        """
        _ = event
        if self.page_count <= 0 or self.page_control_frame is None:
            self._show_status_feedback("下のプレビューはまだ準備できていません。", False)
            return

        requested_page = int(self.page_control_frame.page_var.get()) - 1
        if requested_page < 0 or requested_page >= self.page_count:
            self._show_status_feedback("Requested page is out of range.", False)
            return
        self._commit_preview_keyboard_rotation()
        self.current_page_index = requested_page
        self._ensure_preview_page_available(self.current_page_index)
        self._refresh_current_page_view(show_progress=True)

    def _on_transform_value_input(
        self,
        rotation: float,
        tx: float,
        ty: float,
        scale: float,
        changed_fields: Optional[set[str]] = None,
    ) -> None:
        """Apply the transform values entered in the page control frame.

        Args:
            rotation: Rotation angle.
            tx: X translation.
            ty: Y translation.
            scale: Scale factor.
            changed_fields: Entry fields explicitly confirmed by the user.
        """
        self._commit_preview_keyboard_rotation()
        explicit_fields = set(changed_fields or ())
        old_base: Optional[tuple[float, ...]] = None
        if self.base_transform_data and self.current_page_index < len(self.base_transform_data):
            old_base = as_transform6(self.base_transform_data[self.current_page_index])
        adj_tx, adj_ty = float(tx), float(ty)
        if (
            old_base is not None
            and explicit_fields == {"scale"}
            and abs(float(rotation)) < 1e-6
        ):
            _, old_x, old_y, old_s, _fh, _fv = old_base
            pivot = self._main_canvas_viewport_center_canvas_coords()
            if pivot is not None:
                ax, ay = pivot
                dpi_norm = float(_MAIN_TAB_DEFAULT_DPI) / float(
                    max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI))
                )
                old_eff = max(0.01, float(old_s) * dpi_norm)
                new_eff = max(0.01, float(scale) * dpi_norm)
                ix = (ax - float(old_x)) / old_eff
                iy = (ay - float(old_y)) / old_eff
                adj_tx = ax - ix * new_eff
                adj_ty = ay - iy * new_eff
        if self.base_transform_data and self.current_page_index < len(self.base_transform_data):
            _r, _x, _y, _s, fh, fv = as_transform6(self.base_transform_data[self.current_page_index])
            self.base_transform_data[self.current_page_index] = pack_transform6(
                rotation, adj_tx, adj_ty, scale, fh, fv
            )
        if self.comp_transform_data and self.current_page_index < len(self.comp_transform_data):
            _r, _x, _y, _s, fh, fv = as_transform6(self.comp_transform_data[self.current_page_index])
            self.comp_transform_data[self.current_page_index] = pack_transform6(
                rotation, adj_tx, adj_ty, scale, fh, fv
            )
        self._persist_base_preview_scale(scale)
        self._persist_comp_preview_scale(scale)
        self._apply_export_transform_overrides_for_current_page(adj_tx, adj_ty, scale, explicit_fields)
        self._propagate_current_transform_to_all_pages(visible_only=False)
        self._propagate_export_overrides_to_all_pages(explicit_fields)
        self._refresh_current_page_view()

    def _propagate_layer_to_all_pages(self, transform_data: list) -> None:
        """Copy the current page transform of one layer to all pages when batch edit is active.

        Args:
            transform_data: The layer's transform list (base or comp).
        """
        if self.page_control_frame is None or not self.page_control_frame.is_batch_edit_checked():
            return
        if not transform_data or self.current_page_index >= len(transform_data):
            return
        current_transform = transform_data[self.current_page_index]
        for index in range(len(transform_data)):
            if index != self.current_page_index:
                transform_data[index] = current_transform

    def _on_base_transform_value_input(
        self,
        rotation: float,
        tx: float,
        ty: float,
        scale: float,
        changed_fields: Optional[set[str]] = None,
    ) -> None:
        """Apply transform values entered in the base transform entry fields.

        Updates only ``base_transform_data``; the comp layer is not touched.

        Args:
            rotation: Rotation angle.
            tx: X translation.
            ty: Y translation.
            scale: Scale factor.
            changed_fields: Entry fields explicitly confirmed by the user.
        """
        self._commit_preview_keyboard_rotation()
        explicit_fields = set(changed_fields or ())
        idx = self.current_page_index
        old_base: Optional[tuple[float, ...]] = None
        if self.base_transform_data and idx < len(self.base_transform_data):
            old_base = as_transform6(self.base_transform_data[idx])
        adj_tx, adj_ty = float(tx), float(ty)
        if (
            old_base is not None
            and explicit_fields == {"scale"}
            and abs(float(rotation)) < 1e-6
        ):
            _, old_x, old_y, old_s, _fh, _fv = old_base
            pivot = self._main_canvas_viewport_center_canvas_coords()
            if pivot is not None:
                ax, ay = pivot
                dpi_norm = float(_MAIN_TAB_DEFAULT_DPI) / float(
                    max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI))
                )
                old_eff = max(0.01, float(old_s) * dpi_norm)
                new_eff = max(0.01, float(scale) * dpi_norm)
                ix = (ax - float(old_x)) / old_eff
                iy = (ay - float(old_y)) / old_eff
                adj_tx = ax - ix * new_eff
                adj_ty = ay - iy * new_eff
        if self.base_transform_data and idx < len(self.base_transform_data):
            _r, _x, _y, _s, fh, fv = as_transform6(self.base_transform_data[idx])
            self.base_transform_data[idx] = pack_transform6(
                rotation, adj_tx, adj_ty, scale, fh, fv
            )
        self._persist_base_preview_scale(scale)
        self._apply_export_transform_overrides_for_current_page(adj_tx, adj_ty, scale, explicit_fields)
        self._propagate_layer_to_all_pages(self.base_transform_data)
        self._propagate_export_overrides_to_all_pages(explicit_fields)
        self._refresh_current_page_view()

    def _on_comp_transform_value_input(
        self,
        rotation: float,
        tx: float,
        ty: float,
        scale: float,
        changed_fields: Optional[set[str]] = None,
    ) -> None:
        """Apply transform values entered in the comp transform entry fields.

        Updates only ``comp_transform_data``; the base layer is not touched.

        Args:
            rotation: Rotation angle.
            tx: X translation.
            ty: Y translation.
            scale: Scale factor.
            changed_fields: Entry fields explicitly confirmed by the user.
        """
        self._commit_preview_keyboard_rotation()
        explicit_fields = set(changed_fields or ())
        idx = self.current_page_index
        old_comp: Optional[tuple[float, ...]] = None
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            old_comp = as_transform6(self.comp_transform_data[idx])
        adj_tx, adj_ty = float(tx), float(ty)
        if (
            old_comp is not None
            and explicit_fields == {"scale"}
            and abs(float(rotation)) < 1e-6
        ):
            _, old_x, old_y, old_s, _fh, _fv = old_comp
            pivot = self._main_canvas_viewport_center_canvas_coords()
            if pivot is not None:
                ax, ay = pivot
                dpi_norm = float(_MAIN_TAB_DEFAULT_DPI) / float(
                    max(1, int(self._conversion_dpi or _MAIN_TAB_DEFAULT_DPI))
                )
                old_eff = max(0.01, float(old_s) * dpi_norm)
                new_eff = max(0.01, float(scale) * dpi_norm)
                ix = (ax - float(old_x)) / old_eff
                iy = (ay - float(old_y)) / old_eff
                adj_tx = ax - ix * new_eff
                adj_ty = ay - iy * new_eff
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            _r, _x, _y, _s, fh, fv = as_transform6(self.comp_transform_data[idx])
            self.comp_transform_data[idx] = pack_transform6(
                rotation, adj_tx, adj_ty, scale, fh, fv
            )
        self._persist_comp_preview_scale(scale)
        self._propagate_layer_to_all_pages(self.comp_transform_data)
        self._refresh_current_page_view()

    # ------------------------------------------------------------------
    # Right-sidebar scroll helpers
    # ------------------------------------------------------------------

    def _on_sidebar_scroll(self, event) -> None:
        """Scroll the right-sidebar viewport on MouseWheel, guarded by cursor position."""
        if self._page_ctrl_viewport is None or self._page_ctrl_scroll_outer is None:
            return
        try:
            px, py = self.winfo_pointerx(), self.winfo_pointery()
            rx = self._page_ctrl_scroll_outer.winfo_rootx()
            ry = self._page_ctrl_scroll_outer.winfo_rooty()
            rw = self._page_ctrl_scroll_outer.winfo_width()
            rh = self._page_ctrl_scroll_outer.winfo_height()
            if rx <= px <= rx + rw and ry <= py <= ry + rh:
                self._page_ctrl_viewport.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _bind_sidebar_scroll(self) -> None:
        """Capture global MouseWheel events to scroll the sidebar when cursor is over it."""
        if self._page_ctrl_viewport is not None:
            self._page_ctrl_viewport.bind_all("<MouseWheel>", self._on_sidebar_scroll)

    def _unbind_sidebar_scroll(self) -> None:
        """Release the global MouseWheel capture when cursor leaves the sidebar."""
        if self._page_ctrl_viewport is not None:
            self._page_ctrl_viewport.unbind_all("<MouseWheel>")

    # ------------------------------------------------------------------

    def _on_auto_align_frames(self) -> None:
        """Align comp 図枠 to base 図枠 (scale + position + rotation)."""
        idx = self.current_page_index
        bp = self._get_display_page_path(self.base_page_paths, idx)
        cp = self._get_display_page_path(self.comp_page_paths, idx)
        if bp is None or cp is None:
            self._show_status_feedback(message_manager.get_ui_message("U188") + ": ファイルが読み込まれていません", False); return
        bf = _detect_figure_frame_rect(bp)
        cf = _detect_figure_frame_rect(cp)
        if bf is None:
            self._show_status_feedback("図枠合わせ: ベースの図枠を検出できませんでした", False); return
        if cf is None:
            self._show_status_feedback("図枠合わせ: 比較の図枠を検出できませんでした", False); return
        _def6 = (0.0, 0.0, 0.0, 1.0, 0, 0)
        b6 = as_transform6(self.base_transform_data[idx] if self.base_transform_data and idx < len(self.base_transform_data) else _def6)
        c6 = as_transform6(self.comp_transform_data[idx] if self.comp_transform_data and idx < len(self.comp_transform_data) else _def6)
        nr, ntx, nty, ns = _compute_frame_align(bf, cf, b6, c6)
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            self.comp_transform_data[idx] = pack_transform6(nr, ntx, nty, ns, c6[4], c6[5])
            self._persist_comp_preview_scale(ns)
            self._propagate_layer_to_all_pages(self.comp_transform_data)
            self._refresh_current_page_view()
            self._sync_transform_display_to_panel()

    def _on_auto_align_content(self) -> None:
        """Align comp content to base using overall ink-mass centroid."""
        idx = self.current_page_index
        bp = self._get_display_page_path(self.base_page_paths, idx)
        cp = self._get_display_page_path(self.comp_page_paths, idx)
        if bp is None or cp is None:
            self._show_status_feedback(message_manager.get_ui_message("U190") + ": ファイルが読み込まれていません", False); return
        bf = _detect_figure_frame_rect(bp)
        cf = _detect_figure_frame_rect(cp)
        if bf is None:
            self._show_status_feedback("内容合わせ: ベースの図枠を検出できませんでした", False); return
        if cf is None:
            self._show_status_feedback("内容合わせ: 比較の図枠を検出できませんでした", False); return
        bc = _detect_content_centroid(bp, bf)
        cc = _detect_content_centroid(cp, cf)
        if bc is None:
            self._show_status_feedback("内容合わせ: ベースの内容を検出できませんでした", False); return
        if cc is None:
            self._show_status_feedback("内容合わせ: 比較の内容を検出できませんでした", False); return
        _def6 = (0.0, 0.0, 0.0, 1.0, 0, 0)
        b6 = as_transform6(self.base_transform_data[idx] if self.base_transform_data and idx < len(self.base_transform_data) else _def6)
        c6 = as_transform6(self.comp_transform_data[idx] if self.comp_transform_data and idx < len(self.comp_transform_data) else _def6)
        ntx, nty = _compute_content_align(bc, cc, b6, c6)
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            self.comp_transform_data[idx] = pack_transform6(c6[0], ntx, nty, c6[3], c6[4], c6[5])
            self._propagate_layer_to_all_pages(self.comp_transform_data)
            self._refresh_current_page_view()
            self._sync_transform_display_to_panel()

    def _on_auto_align_priority(self) -> None:
        """Align comp content using priority-based anchor (左→上→下→右)."""
        idx = self.current_page_index
        bp = self._get_display_page_path(self.base_page_paths, idx)
        cp = self._get_display_page_path(self.comp_page_paths, idx)
        if bp is None or cp is None:
            self._show_status_feedback(message_manager.get_ui_message("U193") + ": ファイルが読み込まれていません", False); return
        bf = _detect_figure_frame_rect(bp)
        cf = _detect_figure_frame_rect(cp)
        if bf is None:
            self._show_status_feedback("優先順位合わせ: ベースの図枠を検出できませんでした", False); return
        if cf is None:
            self._show_status_feedback("優先順位合わせ: 比較の図枠を検出できませんでした", False); return
        ba = _detect_priority_anchor(bp, bf)
        ca = _detect_priority_anchor(cp, cf)
        if ba is None:
            self._show_status_feedback("優先順位合わせ: ベースの基準点を検出できませんでした", False); return
        if ca is None:
            self._show_status_feedback("優先順位合わせ: 比較の基準点を検出できませんでした", False); return
        _def6 = (0.0, 0.0, 0.0, 1.0, 0, 0)
        b6 = as_transform6(self.base_transform_data[idx] if self.base_transform_data and idx < len(self.base_transform_data) else _def6)
        c6 = as_transform6(self.comp_transform_data[idx] if self.comp_transform_data and idx < len(self.comp_transform_data) else _def6)
        ntx, nty = _compute_content_align(ba, ca, b6, c6)
        if self.comp_transform_data and idx < len(self.comp_transform_data):
            self.comp_transform_data[idx] = pack_transform6(c6[0], ntx, nty, c6[3], c6[4], c6[5])
            self._propagate_layer_to_all_pages(self.comp_transform_data)
            self._refresh_current_page_view()
            self._sync_transform_display_to_panel()

    def _on_transform_update_skip_batch_propagate(self) -> None:
        """Redraw after Ctrl+Alt sheet rotation without copying the current page to all."""
        self._update_preferred_preview_scale_from_current_page()
        self._refresh_current_page_view()

    def _on_transform_update(self) -> None:
        """Refresh page control and placeholder display after a transform update."""
        self._update_preferred_preview_scale_from_current_page()
        self._propagate_current_transform_to_all_pages(visible_only=True)
        self._schedule_interactive_preview_redraw()

    def _renumber_workspace_records(self, records: List[Dict[str, Any]]) -> None:
        """Refresh stored filename metadata to match the current workspace order.

        Args:
            records: Mutable record list for one workspace side.
        """
        for display_index, record in enumerate(records, start=1):
            record["display_page_number"] = display_index
            record["filename"] = Path(str(record["path"])).name

    def _insert_blank_record_for_side(self, name_flag: str, insert_position: int, page_size: tuple[int, int]) -> bool:
        """Insert one blank workspace page for the requested side.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.
            insert_position: Zero-based insertion index.
            page_size: Blank page size.

        Returns:
            ``True`` when a blank page was inserted.
        """
        records = self._get_workspace_record_list(name_flag)
        workspace_dir = self._get_workspace_directory(name_flag)
        if workspace_dir is None and not records:
            return False
        if workspace_dir is None:
            return False

        blank_path = self._create_blank_workspace_page(workspace_dir, page_size)
        records.insert(insert_position, self._build_page_record(blank_path, None, True))
        self._renumber_workspace_records(records)
        return True

    def _remove_record_for_side(self, name_flag: str, delete_index: int) -> bool:
        """Remove one workspace page record for the requested side.

        Args:
            name_flag: Either ``"base"`` or ``"comp"``.
            delete_index: Zero-based page index.

        Returns:
            ``True`` when a page record was removed.
        """
        records = self._get_workspace_record_list(name_flag)
        if not (0 <= delete_index < len(records)):
            return False

        removed_record = records.pop(delete_index)
        removed_path = Path(str(removed_record.get("path", "")))
        try:
            if removed_path.exists() and removed_path.is_file():
                removed_path.unlink()
        except Exception:
            pass
        self._renumber_workspace_records(records)
        return True

    def _on_insert_blank_page(self) -> None:
        """Insert a blank page into the current comparison workspace."""
        if self._copy_protected:
            return
        if not self._has_loaded_workspace_pages():
            self._show_status_feedback("先に弓矢ボタンでワークスペースを作成してください。", False)
            return

        insert_position = self.current_page_index + 1
        page_size = self._get_current_workspace_page_size()
        inserted_any = False

        # Main processing: keep both sides aligned by inserting blanks into each active workspace side.
        inserted_any = self._insert_blank_record_for_side("base", insert_position, page_size) or inserted_any
        inserted_any = self._insert_blank_record_for_side("comp", insert_position, page_size) or inserted_any
        if not inserted_any:
            self._show_status_feedback("空白ページの追加先がありません。", False)
            return

        self._commit_preview_keyboard_rotation()
        self.base_transform_data.insert(insert_position, pack_transform6(0.0, 0.0, 0.0, 1.0, 0, 0))
        self.comp_transform_data.insert(insert_position, pack_transform6(0.0, 0.0, 0.0, 1.0, 0, 0))
        self._base_export_transform_overrides.insert(insert_position, {})
        self._comp_export_transform_overrides.insert(insert_position, {})
        self._sync_workspace_page_lists()
        self._ensure_transform_slots(self.page_count)
        self._create_page_control_frame(self.page_count)
        self._refresh_operation_restriction_state()
        self._display_page(insert_position)
        self._refresh_interaction_state()
        self._show_status_feedback(f"空白ページを {insert_position + 1} ページ目に追加しました。", True)

    def _on_delete_page(self) -> None:
        """Delete the current page from the comparison workspace."""
        if self._copy_protected:
            return
        if not self._has_loaded_workspace_pages():
            self._show_status_feedback("削除対象のページがありません。", False)
            return
        if self.page_count <= 1:
            self._show_status_feedback("最後の 1 ページは削除できません。", False)
            return

        delete_index = self.current_page_index
        removed_any = False

        # Main processing: delete the same workspace index from both sides to keep page alignment stable.
        removed_any = self._remove_record_for_side("base", delete_index) or removed_any
        removed_any = self._remove_record_for_side("comp", delete_index) or removed_any
        if not removed_any:
            self._show_status_feedback("削除対象のページが見つかりません。", False)
            return

        self._commit_preview_keyboard_rotation()
        if delete_index < len(self.base_transform_data):
            self.base_transform_data.pop(delete_index)
        if delete_index < len(self.comp_transform_data):
            self.comp_transform_data.pop(delete_index)
        if delete_index < len(self._base_export_transform_overrides):
            self._base_export_transform_overrides.pop(delete_index)
        if delete_index < len(self._comp_export_transform_overrides):
            self._comp_export_transform_overrides.pop(delete_index)

        self._sync_workspace_page_lists()
        self._ensure_transform_slots(self.page_count)
        self.current_page_index = min(delete_index, max(0, self.page_count - 1))
        self._create_page_control_frame(self.page_count)
        self._refresh_operation_restriction_state()
        self._display_page(self.current_page_index)
        self._refresh_interaction_state()
        self._show_status_feedback(f"{delete_index + 1} ページ目を削除しました。", True)

    def _on_save_workspace_pdf(self) -> Path:
        """Save the current edited workspace as one PDF file and return its path.

        Returns:
            Saved PDF path.
        """
        if not self._has_loaded_workspace_pages():
            raise ValueError("保存対象のワークスペースがありません。")

        self._commit_preview_keyboard_rotation()
        output_pdf_path = self._build_default_modified_pdf_path()
        pdf_metadata = self._build_export_metadata()
        handler = PDFExportHandler(
            base_pages=[str(path) for path in self.base_page_paths],
            comp_pages=[str(path) for path in self.comp_page_paths],
            base_transform_data=self._build_export_transform_data(
                self.base_transform_data,
                self._base_export_transform_overrides,
            ),
            comp_transform_data=self._build_export_transform_data(
                self.comp_transform_data,
                self._comp_export_transform_overrides,
            ),
            output_folder=str(output_pdf_path.parent),
            pdf_metadata=pdf_metadata,
            color_processing_mode=self._selected_color_processing_mode,
            base_selected_color=self._get_selected_layer_color("base"),
            comparison_selected_color=self._get_selected_layer_color("comp"),
            base_threshold=self._get_threshold_for_side("base"),
            comparison_threshold=self._get_threshold_for_side("comp"),
            show_base_layer=bool(self._show_base_layer_var.get()),
            show_comp_layer=bool(self._show_comp_layer_var.get()),
        )
        handler.export_to_pdf(output_pdf_path.name, self)
        return output_pdf_path

    def _setup_frames(self) -> None:
        """Setup the main frame layout.

        Creates and configures the following frames:
        1. frame_main0: Top frame for theme controls
        2. frame_main1: File selection frame
        3. frame_main2: Analysis controls frame
        4. frame_main3: Canvas display frame

        Raises:
            Exception: If frame setup fails

        Note:
            This method creates a responsive layout using grid geometry manager,
            which allows for better widget positioning and resizing behavior.
        """
        # Start setting up frames
        logger.debug(message_manager.get_log_message("L245"))
        try:
            # Configure grid weights for main frame
            self.grid_rowconfigure(0, weight=0)
            self.grid_rowconfigure(1, weight=0)
            self.grid_rowconfigure(2, weight=0)
            self.grid_rowconfigure(3, weight=1)
            self.grid_columnconfigure(0, weight=1)

            # Setup main frames
            # Main processing: keep the header compact without forcing an undersized fixed height.
            self.frame_main0 = tk.Frame(self, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
            self.frame_main0.grid(row=0, column=0, padx=2, pady=(2, 1), sticky="ew", ipady=3)
            # col 0: collapse toggle (left); col 1: expands; col 2: lang combo; col 3: theme btn
            self.frame_main0.columnconfigure(0, weight=0)
            self.frame_main0.columnconfigure(1, weight=1)
            self.frame_main0.columnconfigure(2, weight=0)
            self.frame_main0.columnconfigure(3, weight=0)
            self.frame_main0.grid_rowconfigure(0, minsize=40)

            self.frame_main1 = tk.Frame(self, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
            self.frame_main1.grid(row=1, column=0, padx=5, pady=1, sticky="nsew")
            self.frame_main1.grid_columnconfigure(1, weight=1)
            self.frame_main1.grid_columnconfigure(2, weight=0, minsize=28)
            self.frame_main1.grid_columnconfigure(3, weight=0, minsize=76)

            self.frame_main2 = tk.Frame(self, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
            self.frame_main2.grid(row=2, column=0, padx=5, pady=(5, 1), sticky="nsew")
            # Seven columns: fixed content minsize on 0,2,4,6; equal flexible gutters on 1,3,5 (uniform group).
            h0 = int(CreateComparisonFileApp._MAIN2_HOST0_WIDTH_PX)
            h2 = int(CreateComparisonFileApp._MAIN2_HOST2_WIDTH_PX)
            h4 = int(CreateComparisonFileApp._MAIN2_HOST4_WIDTH_PX)
            h6 = int(CreateComparisonFileApp._MAIN2_HOST6_WIDTH_PX)
            gap_u = "main2_mid_gap"
            self.frame_main2.grid_columnconfigure(0, weight=0, minsize=h0)
            self.frame_main2.grid_columnconfigure(1, weight=1, minsize=1, uniform=gap_u)
            self.frame_main2.grid_columnconfigure(2, weight=0, minsize=h2)
            self.frame_main2.grid_columnconfigure(3, weight=1, minsize=1, uniform=gap_u)
            self.frame_main2.grid_columnconfigure(4, weight=0, minsize=h4)
            self.frame_main2.grid_columnconfigure(5, weight=1, minsize=1, uniform=gap_u)
            self.frame_main2.grid_columnconfigure(6, weight=0, minsize=h6)
            # Compact row height: extra minsize steals vertical space from the canvas / page sidebar below.
            # Threshold descenders are handled with modest per-widget pady instead of inflating the whole row.
            _row4_body_h = max(
                240,
                int(self._action_button_square_size) + 112,
            )
            self.frame_main2.grid_rowconfigure(0, minsize=_row4_body_h)

            self.frame_main3 = tk.Frame(self, relief=tk.FLAT, borderwidth=0, highlightthickness=0)
            self.frame_main3.grid(row=3, column=0, padx=5, pady=(1, 5), sticky="nsew")
            self.frame_main3.grid_rowconfigure(0, weight=1)
            self.frame_main3.grid_rowconfigure(1, weight=0)
            self.frame_main3.grid_columnconfigure(0, weight=1)
            self.frame_main3.grid_columnconfigure(1, weight=0)
            # Make canvas area expand more
            self.grid_rowconfigure(3, weight=8)

            # Right sidebar: scrollable container (Canvas + Scrollbar + inner Frame)
            self._page_ctrl_scroll_outer = tk.Frame(
                self.frame_main3, bd=0, highlightthickness=0,
            )
            self._page_ctrl_scroll_outer.grid(
                row=0, column=1, padx=(4, 6), pady=0, sticky="nsew"
            )
            self._page_ctrl_scroll_outer.grid_rowconfigure(0, weight=1)
            self._page_ctrl_scroll_outer.grid_columnconfigure(0, weight=1)

            self._page_ctrl_vbar = tk.Scrollbar(
                self._page_ctrl_scroll_outer, orient="vertical"
            )
            self._page_ctrl_vbar.grid(row=0, column=1, sticky="ns")

            self._page_ctrl_viewport = tk.Canvas(
                self._page_ctrl_scroll_outer,
                yscrollcommand=self._page_ctrl_vbar.set,
                highlightthickness=0,
                bd=0,
                width=1,  # start at 1; resized to inner frame's natural width on first Configure
            )
            self._page_ctrl_viewport.grid(row=0, column=0, sticky="nsew")
            self._page_ctrl_vbar.config(command=self._page_ctrl_viewport.yview)

            self._page_ctrl_inner = tk.Frame(
                self._page_ctrl_viewport, bd=0, highlightthickness=0,
            )
            self._page_ctrl_window_id = self._page_ctrl_viewport.create_window(
                (0, 0), window=self._page_ctrl_inner, anchor="nw"
            )
            self._page_ctrl_inner.grid_rowconfigure(0, weight=1)
            self._page_ctrl_inner.grid_columnconfigure(0, weight=1)

            def _on_inner_configure(e: tk.Event) -> None:
                """Sync canvas width and scroll region to the inner frame's natural size."""
                if self._page_ctrl_viewport is None:
                    return
                w = self._page_ctrl_inner.winfo_reqwidth()
                self._page_ctrl_viewport.configure(
                    width=w,
                    scrollregion=self._page_ctrl_viewport.bbox("all"),
                )

            self._page_ctrl_inner.bind("<Configure>", _on_inner_configure)
            self._page_ctrl_viewport.bind(
                "<Enter>", lambda e: self._bind_sidebar_scroll()
            )
            self._page_ctrl_viewport.bind(
                "<Leave>", lambda e: self._unbind_sidebar_scroll()
            )
            self._page_ctrl_inner.bind(
                "<Enter>", lambda e: self._bind_sidebar_scroll()
            )
            self._page_ctrl_inner.bind(
                "<Leave>", lambda e: self._unbind_sidebar_scroll()
            )

            # Frames setup completed
            logger.debug(message_manager.get_log_message("L246"))
        except Exception as e:
            # Failed to setup frames
            logger.error(message_manager.get_log_message("L066", str(e)))
            raise

    def _toggle_analysis_controls(self) -> None:
        """Collapse or expand the analysis controls panel (frame_main2)."""
        if self._analysis_panel_collapsed:
            self.frame_main2.grid()
            self._analysis_panel_collapsed = False
            self._collapse_btn.configure(text=message_manager.get_ui_message("U191"))
        else:
            self.frame_main2.grid_remove()
            self._analysis_panel_collapsed = True
            self._collapse_btn.configure(text=message_manager.get_ui_message("U192"))
        # Persist state
        try:
            from configurations.user_setting_manager import UserSettingManager
            UserSettingManager.update_setting("analysis_panel_collapsed", self._analysis_panel_collapsed)
            UserSettingManager.save_settings()
        except Exception:
            pass

    def _restore_analysis_panel_state(self) -> None:
        """Restore the collapsed/expanded state of frame_main2 from saved settings."""
        try:
            from configurations.user_setting_manager import UserSettingManager
            collapsed = UserSettingManager.get_setting("analysis_panel_collapsed")
            if collapsed:
                self.frame_main2.grid_remove()
                self._analysis_panel_collapsed = True
                self._collapse_btn.configure(text=message_manager.get_ui_message("U192"))
        except Exception:
            pass

    def _setup_widgets(self) -> None:
        """Setup all widgets in the application.

        Creates and configures the following widgets:
        1. Color theme change button
        2. PDF display canvas
        3. File analysis buttons
        4. File path labels and entries
        5. DPI selection controls

        Raises:
            Exception: If widget setup fails

        Note:
            This method initializes all interactive elements of the application,
            including buttons, labels, and input fields. Each widget is configured
            with appropriate event handlers and visual properties.
        """
        # Start setting up widgets
        logger.debug(message_manager.get_log_message("L247"))
        try:
            # Collapse/expand analysis controls toggle button (col 0, left-aligned)
            self._analysis_panel_collapsed: bool = False
            self._collapse_btn = tk.Button(
                self.frame_main0,
                text=message_manager.get_ui_message("U191"),  # "▼ 操作"
                font=("", 8),
                relief=tk.FLAT,
                bd=0,
                padx=4,
                command=self._toggle_analysis_controls,
                cursor="hand2",
            )
            self._collapse_btn.grid(row=0, column=0, padx=(4, 2), pady=3, sticky="w")

            # Create language selection combobox
            lang_combo = LanguageSelectCombo(self.frame_main0)
            self._lang_select_combo = lang_combo
            lang_combo.grid(row=0, column=2, padx=3, pady=3, sticky="e")

            # Create theme change button
            # UI text for Change Theme button
            self._color_theme_change_btn = ColorThemeChangeButton(
                fr=self.frame_main0,
                color_theme_change_btn_status=False,
                text=message_manager.get_ui_message("U025"),
            )
            self._color_theme_change_btn.grid(
                row=0, column=3, padx=3, pady=2, sticky="e"
            )

            # Base file path label and entry
            # UI text for Base File Path label
            self._base_file_path_label = BaseLabelClass(
                fr=self.frame_main1,
                color_key="base_file_path_label",
                text=message_manager.get_ui_message("U018"),
            )
            self._base_file_path_label.grid(
                column=0, row=1, padx=5, pady=8, sticky="nw"
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
                column=1, row=1, padx=(2, 4), pady=8, sticky="ew"
            )
            self._base_file_path_entry.path_var.set(self.base_path.get())
            self._base_file_path_entry.path_entry.bind("<Return>", lambda event: self._on_path_entry_submit("base", event))
            self._base_file_path_entry.path_entry.bind("<KP_Enter>", lambda event: self._on_path_entry_submit("base", event))

            # Base image color change button
            self._base_image_color_change_btn = BaseImageColorChangeButton(
                fr=self.frame_main1,
                color_key="base_image_color_change_button",
                command=self._on_base_image_color_change,
            )
            self._base_image_color_change_btn.image_color_select_btn.configure(width=2, height=1)
            self._base_image_color_change_btn.grid(column=2, row=1, padx=0, pady=6)

            # Base file path select button
            # UI text for Base File Path select button
            self._base_file_path_button = BasePathSelectButton(
                fr=self.frame_main1,
                color_key="base_file_path_button",
                entry_setting_key="base_file_path",
                share_path_entry=self._base_file_path_entry,
                text=message_manager.get_ui_message("U019"),
                command=self._on_base_file_select,
            )
            self._base_file_path_button.grid(column=3, row=1, padx=(3, 5), pady=8)

            # Comparison file path label and entry
            # UI text for Comparison File Path label
            self._comparison_file_path_label = BaseLabelClass(
                fr=self.frame_main1,
                color_key="comparison_file_path_label",
                text=message_manager.get_ui_message("U020"),
            )
            self._comparison_file_path_label.grid(
                column=0, row=2, padx=5, pady=8, sticky="nw"
            )

            # type: ignore[call-arg] # suppress mypy errors for fr/entry_setting_key arguments
            self._comparison_file_path_entry = BasePathEntry(
                fr=self.frame_main1,
                color_key="comparison_file_path_entry",
                entry_setting_key="comparison_file_path",
                allow_files=True,
                allow_directories=False,
                allowed_file_extensions=MAIN_PDF_OPE_INPUT_EXTENSIONS,
            )
            self._comparison_file_path_entry.grid(
                column=1, row=2, padx=5, pady=8, sticky="we"
            )
            self._comparison_file_path_entry.path_var.set(self.comparison_path.get())
            self._comparison_file_path_entry.path_entry.bind("<Return>", lambda event: self._on_path_entry_submit("comparison", event))
            self._comparison_file_path_entry.path_entry.bind("<KP_Enter>", lambda event: self._on_path_entry_submit("comparison", event))

            # Comparison image color change button
            self._comparison_image_color_change_btn = BaseImageColorChangeButton(
                fr=self.frame_main1,
                color_key="comparison_image_color_change_button",
                command=self._on_comparison_image_color_change,
            )
            self._comparison_image_color_change_btn.image_color_select_btn.configure(width=2, height=1)
            self._comparison_image_color_change_btn.grid(column=2, row=2, padx=(0, 2), pady=6)

            # Comparison file path button
            # UI text for Comparison File Path select button
            self._comparison_file_path_button = BasePathSelectButton(
                fr=self.frame_main1,
                color_key="comparison_file_path_button",
                entry_setting_key="comparison_file_path",
                share_path_entry=self._comparison_file_path_entry,
                text=message_manager.get_ui_message("U019"),
                command=self._on_comparison_file_select,
            )
            self._comparison_file_path_button.grid(column=3, row=2, padx=(3, 5), pady=8)

            # Output folder path label and entry
            # UI text for Output Folder Path label
            self._output_folder_path_label = BaseLabelClass(
                fr=self.frame_main1,
                color_key="output_folder_path_label",
                text=message_manager.get_ui_message("U021"),
            )
            self._output_folder_path_label.grid(
                column=0, row=3, padx=5, pady=8, sticky="nw"
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
                column=1, row=3, padx=5, pady=8, sticky="we"
            )
            self._output_folder_path_entry.path_var.set(self.output_path.get())
            self._output_folder_path_entry.path_entry.bind("<Return>", lambda event: self._on_path_entry_submit("output", event))
            self._output_folder_path_entry.path_entry.bind("<KP_Enter>", lambda event: self._on_path_entry_submit("output", event))

            # Output folder path button
            # UI text for Output Folder Path select button
            self._output_folder_path_button = BasePathSelectButton(
                fr=self.frame_main1,
                color_key="output_folder_path_button",
                entry_setting_key="output_folder_path",
                share_path_entry=self._output_folder_path_entry,
                text=message_manager.get_ui_message("U019"),
                command=self._on_output_folder_select,
            )
            self._output_folder_path_button.grid(column=3, row=3, padx=(1, 4), pady=8)

            self._row4_fixed_col0_host = tk.Frame(
                self.frame_main2,
                width=int(CreateComparisonFileApp._MAIN2_HOST0_WIDTH_PX),
                highlightthickness=0,
                bd=0,
            )
            _hpad = int(CreateComparisonFileApp._MAIN2_HOST_INNER_PAD_X_PX)
            self._row4_fixed_col0_host.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
            self._row4_fixed_col0_host.grid_propagate(False)
            self._row4_fixed_col0_host.grid_rowconfigure(0, weight=1)
            self._row4_fixed_col0_host.grid_columnconfigure(0, weight=1)

            self._row4_comment_frame = tk.Frame(self._row4_fixed_col0_host)
            self._row4_comment_frame.grid(row=0, column=0, padx=(_hpad, _hpad), pady=6, sticky="new")
            self._row4_comment_frame.grid_columnconfigure(0, weight=1)

            self._row4_comment_text_label = tk.Label(
                self._row4_comment_frame,
                text=message_manager.get_ui_message("U137"),
                anchor="w",
                justify="left",
                wraplength=200,
            )
            self._row4_comment_text_label.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            self._row4_comment_frame.bind("<Configure>", self._on_row4_comment_frame_configure, add="+")

            self._base_file_analyze_btn = CreateSubGraphWindowButton(
                master=self._row4_comment_frame,
                window_id="base_file_graph",
                graph_data=[0] * 766,
                graph_color="blue",
                color_key="create_sub_graph_window_button",
                common_setting_key="base_separat_color_threshold",
                threshold_var=self._base_threshold_value_var,
                text=message_manager.get_ui_message("U016"),
                command=self._open_base_analysis_graph,
            )
            self._base_file_analyze_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 4))

            self._comparison_file_analyze_btn = CreateSubGraphWindowButton(
                master=self._row4_comment_frame,
                window_id="comparison_file_graph",
                graph_data=[0] * 766,
                graph_color="red",
                color_key="create_sub_graph_window_button",
                common_setting_key="comparison_separat_color_threshold",
                threshold_var=self._comparison_threshold_value_var,
                text=message_manager.get_ui_message("U017"),
                command=self._open_comparison_analysis_graph,
            )
            self._comparison_file_analyze_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))

            self._threshold_summary_frame = tk.Frame(self._row4_comment_frame)
            self._threshold_summary_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=0)
            # Spacer column eats space on the left; label+entry stay packed to the right edge.
            self._threshold_summary_frame.grid_columnconfigure(0, weight=1)
            self._threshold_summary_frame.grid_columnconfigure(1, weight=0)
            self._threshold_summary_frame.grid_columnconfigure(2, weight=0)

            self._threshold_summary_label = tk.Label(
                self._threshold_summary_frame,
                text=message_manager.get_ui_message("U142"),
                anchor="w",
            )
            self._threshold_summary_label.grid(row=0, column=0, columnspan=3, padx=(0, 4), sticky="w")

            self._base_threshold_inline_label = tk.Label(
                self._threshold_summary_frame,
                text=message_manager.get_ui_message("U143"),
                anchor="e",
                width=14,
            )
            self._base_threshold_inline_label.grid(row=1, column=1, padx=(0, 4), pady=(4, 2), sticky="e")

            self._base_threshold_entry = BaseEntryClass(
                fr=self._threshold_summary_frame,
                color_key="create_fb_threshold_entry",
                textvariable=self._base_threshold_value_var,
                width=6,
            )
            self._base_threshold_entry.grid(row=1, column=2, padx=(0, 0), pady=(4, 2), sticky="w")

            self._comparison_threshold_inline_label = tk.Label(
                self._threshold_summary_frame,
                text=message_manager.get_ui_message("U176"),
                anchor="e",
                width=14,
            )
            self._comparison_threshold_inline_label.grid(row=2, column=1, padx=(0, 4), pady=(4, 4), sticky="e")

            self._comparison_threshold_entry = BaseEntryClass(
                fr=self._threshold_summary_frame,
                color_key="create_fb_threshold_entry",
                textvariable=self._comparison_threshold_value_var,
                width=6,
            )
            self._comparison_threshold_entry.grid(row=2, column=2, padx=(0, 0), pady=(4, 4), sticky="w")

            self._row4_fixed_col2_host = tk.Frame(
                self.frame_main2,
                width=int(CreateComparisonFileApp._MAIN2_HOST2_WIDTH_PX),
                highlightthickness=0,
                bd=0,
            )
            self._row4_fixed_col2_host.grid(row=0, column=2, padx=0, pady=0, sticky="nsew")
            self._row4_fixed_col2_host.grid_propagate(False)
            self._row4_fixed_col2_host.grid_rowconfigure(0, weight=1)
            self._row4_fixed_col2_host.grid_columnconfigure(0, weight=1)

            self._row4_auto_column_frame = tk.Frame(self._row4_fixed_col2_host)
            self._row4_auto_column_frame.grid(row=0, column=0, padx=(_hpad, _hpad), pady=6, sticky="new")
            self._row4_auto_column_frame.grid_columnconfigure(0, weight=1)

            self._row4_arrow_guidance_frame = tk.Frame(self._row4_auto_column_frame)
            self._row4_arrow_guidance_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
            self._row4_arrow_guidance_label = tk.Label(
                self._row4_arrow_guidance_frame,
                text=message_manager.get_ui_message("U146"),
                anchor="w",
                justify="left",
                wraplength=152,
            )
            self._row4_arrow_guidance_label.pack(fill="x")
            self._row4_arrow_guidance_frame.bind(
                "<Configure>", self._on_row4_arrow_guidance_frame_configure, add="+"
            )

            self._row4_arrow_frame = tk.Frame(
                self._row4_auto_column_frame,
                width=self._action_button_square_size,
                height=self._action_button_square_size,
            )
            self._row4_arrow_frame.grid(row=1, column=0, sticky="n", pady=(0, 4))
            self._row4_arrow_frame.grid_propagate(False)
            self._row4_arrow_frame.grid_rowconfigure(0, weight=1)
            self._row4_arrow_frame.grid_columnconfigure(0, weight=1)

            self._automatic_execute_button = tk.Button(
                self._row4_arrow_frame,
                command=self._on_automatic_image_button_click,
                text=message_manager.get_ui_message("U145"),
                relief=tk.RAISED,
                bd=2,
                highlightthickness=1,
                highlightbackground="#ffffff",
                highlightcolor="#ffffff",
            )
            self._automatic_execute_button.place(x=0, y=0, width=self._action_button_square_size, height=self._action_button_square_size)

            self._row4_fixed_col4_host = tk.Frame(
                self.frame_main2,
                width=int(CreateComparisonFileApp._MAIN2_HOST4_WIDTH_PX),
                highlightthickness=0,
                bd=0,
            )
            self._row4_fixed_col4_host.grid(row=0, column=4, padx=0, pady=0, sticky="nsew")
            self._row4_fixed_col4_host.grid_propagate(False)
            self._row4_fixed_col4_host.grid_rowconfigure(0, weight=1)
            self._row4_fixed_col4_host.grid_columnconfigure(0, weight=1)

            self._row4_action_frame = tk.Frame(self._row4_fixed_col4_host)
            self._row4_action_frame.grid(
                row=0, column=0, padx=(_hpad, 2), pady=6, sticky="nsew"
            )
            self._row4_action_frame.grid_columnconfigure(0, weight=1)

            # Row order: toggles, DPI, Color Processing label, combo-only row below label, then Custom Rotation Guide.
            self._layer_toggle_frame = tk.Frame(self._row4_action_frame)
            self._layer_toggle_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
            self._layer_toggle_frame.grid_columnconfigure(0, weight=1)

            self._show_base_layer_check = tk.Checkbutton(
                self._layer_toggle_frame,
                text=message_manager.get_ui_message("U140"),
                variable=self._show_base_layer_var,
                command=self._on_layer_visibility_changed,
                anchor="w",
            )
            self._show_base_layer_check.grid(row=0, column=0, sticky="ew")

            self._show_comp_layer_check = tk.Checkbutton(
                self._layer_toggle_frame,
                text=message_manager.get_ui_message("U141"),
                variable=self._show_comp_layer_var,
                command=self._on_layer_visibility_changed,
                anchor="w",
            )
            self._show_comp_layer_check.grid(row=1, column=0, sticky="ew")

            self._show_reference_grid_check = tk.Checkbutton(
                self._layer_toggle_frame,
                text=message_manager.get_ui_message("U149"),
                variable=self._show_reference_grid_var,
                command=self._on_layer_visibility_changed,
                anchor="w",
            )
            self._show_reference_grid_check.grid(row=2, column=0, sticky="ew")

            self._diff_emphasis_check = tk.Checkbutton(
                self._layer_toggle_frame,
                text=message_manager.get_ui_message("U178"),
                variable=self._diff_emphasis_var,
                command=self._on_diff_emphasis_toggled,
                anchor="w",
            )
            self._diff_emphasis_check.grid(row=3, column=0, sticky="ew")

            self._dpi_row_frame = tk.Frame(self._row4_action_frame)
            self._dpi_row_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
            self._dpi_row_frame.grid_columnconfigure(0, weight=0)
            self._dpi_row_frame.grid_columnconfigure(1, weight=1)

            self._dpi_label = BaseLabelClass(
                fr=self._dpi_row_frame,
                color_key="dpi_label",
                text=message_manager.get_ui_message("U022"),
            )
            self._dpi_label.grid(row=0, column=0, padx=(0, 5), sticky="w")

            # ttk.Combobox often ignores grid stretch; pack inside a grid cell to fill column width.
            self._dpi_combo_holder = tk.Frame(self._dpi_row_frame, bd=0, highlightthickness=0)
            self._dpi_combo_holder.grid(row=0, column=1, sticky="nsew")
            self._dpi_combo = BaseValueCombobox(
                master=self._dpi_combo_holder,
                color_key="dpi_entry",
                values=[str(value) for value in self._get_configured_dpi_choices()],
                default_value=str(self.selected_dpi_value),
                textvariable=self._dpi_choice_var,
                width=6,
                state="disabled",
            )
            self._dpi_combo.pack(fill=tk.X, expand=True)
            self._sync_dpi_combo_choices(preserve_current=False)

            self._color_mode_label_row_frame = tk.Frame(self._row4_action_frame)
            self._color_mode_label_row_frame.grid(row=2, column=0, sticky="ew", pady=(0, 2))
            self._color_mode_label_row_frame.grid_columnconfigure(0, weight=1)
            self._color_mode_label = BaseLabelClass(
                fr=self._color_mode_label_row_frame,
                color_key="dpi_label",
                text=message_manager.get_ui_message("U136"),
            )
            self._color_mode_label.grid(row=0, column=0, sticky="w")

            self._color_combo_only_row_frame = tk.Frame(self._row4_action_frame)
            self._color_combo_only_row_frame.grid(row=3, column=0, sticky="ew", pady=(0, 4))
            self._color_combo_only_row_frame.grid_columnconfigure(0, weight=1)

            self._color_processing_mode_combo = BaseValueCombobox(
                master=self._color_combo_only_row_frame,
                color_key="dpi_entry",
                values=self._get_color_processing_mode_display_values(),
                default_value=self._color_processing_mode_var.get(),
                textvariable=self._color_processing_mode_var,
                width=8,
                state="disabled",
            )
            self._color_processing_mode_combo.pack(fill=tk.X, expand=True)
            self._color_processing_mode_combo.bind("<<ComboboxSelected>>", self._on_color_processing_mode_changed)

            self._custom_rotation_guide_button = BaseButton(
                fr=self._row4_action_frame,
                color_key="process_button",
                text=message_manager.get_ui_message("U151"),
                command=self._show_custom_rotation_guide,
                relief=tk.RAISED,
                bd=2,
                highlightthickness=1,
            )
            self._custom_rotation_guide_button.grid(row=4, column=0, sticky="ew", pady=(8, 0))

            self._row4_fixed_col6_host = tk.Frame(
                self.frame_main2,
                width=int(CreateComparisonFileApp._MAIN2_HOST6_WIDTH_PX),
                highlightthickness=0,
                bd=0,
            )
            self._row4_fixed_col6_host.grid(row=0, column=6, padx=0, pady=0, sticky="nsew")
            self._row4_fixed_col6_host.grid_propagate(False)
            self._row4_fixed_col6_host.grid_columnconfigure(0, weight=1)

            self._row4_custom_column_frame = tk.Frame(self._row4_fixed_col6_host)
            _h6x, _h6y = CreateComparisonFileApp._MAIN2_HOST6_CUSTOM_COLUMN_PADX_PX
            self._row4_custom_column_frame.grid(
                row=0, column=0, padx=(_h6x, _h6y), pady=(6, 8), sticky="nsew"
            )
            self._row4_custom_column_frame.grid_columnconfigure(0, weight=1)
            self._row4_fixed_col6_host.grid_rowconfigure(0, weight=1)

            # Gutter columns center a narrow label over the square custom button (same column, row below).
            self._row4_custom_guidance_frame = tk.Frame(self._row4_custom_column_frame)
            self._row4_custom_guidance_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
            self._row4_custom_guidance_frame.grid_columnconfigure(0, weight=1)
            self._row4_custom_guidance_frame.grid_columnconfigure(1, weight=0)
            self._row4_custom_guidance_frame.grid_columnconfigure(2, weight=1)

            self._row4_custom_guidance_inner = tk.Frame(
                self._row4_custom_guidance_frame,
                highlightthickness=0,
                bd=0,
            )
            self._row4_custom_guidance_inner.grid(row=0, column=1, sticky="")

            self._row4_custom_guidance_label = tk.Label(
                self._row4_custom_guidance_inner,
                text=message_manager.get_ui_message("U147"),
                anchor="nw",
                justify="left",
                wraplength=0,
                padx=4,
                pady=6,
            )
            self._row4_custom_guidance_label.pack(anchor="w")

            self._row4_custom_frame = tk.Frame(
                self._row4_custom_column_frame,
                width=self._action_button_square_size,
                height=self._action_button_square_size,
            )
            self._row4_custom_frame.grid(row=1, column=0, sticky="n")
            self._row4_custom_frame.grid_propagate(False)
            self._row4_custom_frame.grid_rowconfigure(0, weight=1)
            self._row4_custom_frame.grid_columnconfigure(0, weight=1)

            # Canvas uses a fixed white surface so preview linework stays visible in dark themes.
            self.canvas = tk.Canvas(
                self.frame_main3,
                bg=CreateComparisonFileApp._PREVIEW_CANVAS_BACKGROUND,
                relief=tk.SUNKEN,
                bd=2,
                takefocus=1,
                highlightthickness=2,
                highlightbackground="#888888",
            )
            self.canvas.grid(row=0, column=0, padx=5, pady=(1, 5), sticky="nsew")

            self._create_page_control_frame(self.page_count)
            self._render_comparison_placeholder()

            self._custom_execute_button = tk.Button(
                self._row4_custom_frame,
                command=self._on_custom_image_button_click,
                text=message_manager.get_ui_message("U023"),
                relief=tk.RAISED,
                bd=2,
                highlightthickness=1,
                highlightbackground="#ffffff",
                highlightcolor="#ffffff",
            )
            self._custom_execute_button.place(x=0, y=0, width=self._action_button_square_size, height=self._action_button_square_size)
            self._custom_execute_button.bind("<ButtonPress-1>", self._prepare_custom_button_press_visual, add="+")

            self._apply_action_button_visual("automatic", False)
            self._apply_action_button_visual("custom", False)
            self._refresh_interaction_state()

            # Widgets setup completed - using message code for multilingual support
            logger.debug(message_manager.get_log_message("L230", "CreateComparisonFileApp"))
        except Exception as e:
            # Failed to setup widgets
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def build_keyboard_focus_chain(self) -> List[tk.Widget]:
        """Build column-major keyboard focus order for the main tab.

        Order: per path row left-to-right (entry, color swatch when present, select),
        then output folder row, language/theme, analyze and threshold controls,
        automatic-mode options, DPI and processing comboboxes, preview canvas,
        then page-control sidebar.

        Returns:
            Interactive widgets participating in Tab / Shift+Tab navigation.
        """
        chain: List[tk.Widget] = []
        chain.append(self._base_file_path_entry.path_entry)
        chain.append(self._base_image_color_change_btn.image_color_select_btn)
        chain.append(self._base_file_path_button.path_select_btn)
        chain.append(self._comparison_file_path_entry.path_entry)
        chain.append(self._comparison_image_color_change_btn.image_color_select_btn)
        chain.append(self._comparison_file_path_button.path_select_btn)
        chain.append(self._output_folder_path_entry.path_entry)
        chain.append(self._output_folder_path_button.path_select_btn)

        lang = getattr(self, "_lang_select_combo", None)
        if lang is not None:
            chain.append(lang)
        theme_btn = getattr(self, "_color_theme_change_btn", None)
        if theme_btn is not None and hasattr(theme_btn, "color_theme_change_btn"):
            chain.append(theme_btn.color_theme_change_btn)

        chain.append(self._base_file_analyze_btn)
        chain.append(self._comparison_file_analyze_btn)
        chain.append(self._base_threshold_entry)
        chain.append(self._comparison_threshold_entry)

        chain.append(self._automatic_execute_button)

        chain.extend(
            [
                self._show_base_layer_check,
                self._show_comp_layer_check,
                self._show_reference_grid_check,
            ]
        )
        diff_ch = getattr(self, "_diff_emphasis_check", None)
        if diff_ch is not None:
            chain.append(diff_ch)
        chain.extend(
            [
                self._dpi_combo,
                self._color_processing_mode_combo,
                self._custom_rotation_guide_button,
            ]
        )
        chain.append(self._custom_execute_button)

        chain.append(self.canvas)
        if self.page_control_frame is not None:
            chain.extend(self.page_control_frame.iter_focus_widgets())
        return chain

    def _on_base_image_color_change(self) -> None:
        """Handle base image color change button click."""
        if hasattr(self, "_base_image_color_change_btn"):
            try:
                self._base_selected_color_hex = self._base_image_color_change_btn.get_selected_color_hex()
            except Exception:
                self._base_selected_color_hex = None
        with self._diff_overlay_cache_lock:
            self._diff_src_overlay_cache.clear()
            self._diff_overlay_bg_key = None
        self._refresh_preview_after_color_change()

    def _on_comparison_image_color_change(self) -> None:
        """Handle comparison image color change button click."""
        if hasattr(self, "_comparison_image_color_change_btn"):
            try:
                self._comparison_selected_color_hex = self._comparison_image_color_change_btn.get_selected_color_hex()
            except Exception:
                self._comparison_selected_color_hex = None
        with self._diff_overlay_cache_lock:
            self._diff_src_overlay_cache.clear()
            self._diff_overlay_bg_key = None
        self._refresh_preview_after_color_change()

    def _on_base_file_select(self) -> None:
        """Handle base file selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("base_file_path", self.base_path.get())
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U022",
            filetypes=main_pdf_ope_askopen_filetypes(),
            parent=self.winfo_toplevel(),
        )
        if file_path:
            self._base_pdf_session_committed = True
            norm = normalize_host_path(file_path)
            self._base_file_path_entry.path_var.set(norm)
            if not self._base_file_path_entry.validate_current_path(show_warning=True):
                return
            resolved = self._base_file_path_entry.path_var.get().strip()
            self.base_path.set(resolved)
            self.status_var.set("Base PDF route has been prepared. Use Analyze to validate the input side.")
            self._refresh_workspace_state()
            logger.debug(message_manager.get_log_message("L070", resolved))

    def _on_comparison_file_select(self) -> None:
        """Handle comparison file selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("comparison_file_path", self.comparison_path.get())
        file_path = ask_file_dialog(
            initialdir=initial_dir,
            title_code="U023",
            filetypes=main_pdf_ope_askopen_filetypes(),
            parent=self.winfo_toplevel(),
        )
        if file_path:
            self._comparison_pdf_session_committed = True
            norm = normalize_host_path(file_path)
            self._comparison_file_path_entry.path_var.set(norm)
            if not self._comparison_file_path_entry.validate_current_path(show_warning=True):
                return
            resolved = self._comparison_file_path_entry.path_var.get().strip()
            self.comparison_path.set(resolved)
            self.status_var.set("Comparison PDF route has been prepared. Use Analyze to validate the comparison side.")
            self._refresh_workspace_state()
            logger.debug(message_manager.get_log_message("L071", resolved))

    def _on_output_folder_select(self) -> None:
        """Handle output folder selection event using common dialog."""
        initial_dir = self._get_initial_dir_from_setting("output_folder_path", self.output_path.get())
        folder_path = ask_folder_dialog(
            initialdir=initial_dir,
            title_code="U024",
        )
        if folder_path:
            norm = normalize_host_path(folder_path)
            self._output_folder_path_entry.path_var.set(norm)
            if not self._output_folder_path_entry.validate_current_path(show_warning=True):
                return
            resolved = self._output_folder_path_entry.path_var.get().strip()
            self.output_path.set(resolved)
            self.status_var.set("Output folder is ready for later comparison export.")
            if self._has_loaded_workspace_pages():
                self._display_page(self.current_page_index)
            else:
                self._render_comparison_placeholder()
            self._refresh_interaction_state()
            logger.debug(message_manager.get_log_message("L072", resolved))

    def _on_path_entry_submit(self, target: str, event: Optional[tk.Event] = None) -> str:
        """Handle Enter-key submission from a path entry field.

        Args:
            target: One of ``base``, ``comparison``, or ``output``.
            event: Optional Tk event object.

        Returns:
            Tkinter break string to stop duplicate default handling.
        """
        _ = event
        if target == "base":
            if not self._base_file_path_entry.validate_current_path(show_warning=True):
                return "break"
            self._base_pdf_session_committed = True
            self.base_path.set(self._base_file_path_entry.path_var.get().strip())
            self._refresh_workspace_state()
        elif target == "comparison":
            if not self._comparison_file_path_entry.validate_current_path(show_warning=True):
                return "break"
            self._comparison_pdf_session_committed = True
            self.comparison_path.set(self._comparison_file_path_entry.path_var.get().strip())
            self._refresh_workspace_state()
        else:
            if not self._output_folder_path_entry.validate_current_path(show_warning=True):
                return "break"
            self.output_path.set(self._output_folder_path_entry.path_var.get().strip())
            if self._has_loaded_workspace_pages():
                self._display_page(self.current_page_index)
            else:
                self._render_comparison_placeholder()
            self._refresh_interaction_state()
        return "break"

    def _on_pdf_save_click(self) -> None:
        """Handle PDF save button click event."""
        if not self._output_folder_path_entry.validate_current_path(show_warning=False):
            messagebox.showwarning(
                message_manager.get_ui_message("U033"),
                message_manager.get_ui_message("U011"),
                parent=self.winfo_toplevel(),
            )
            self._show_status_feedback(message_manager.get_ui_message("U011"), False)
            return

        self.output_path.set(self._output_folder_path_entry.path_var.get().strip())
        try:
            output_pdf_path = self._on_save_workspace_pdf()
            self._show_status_feedback(f"PDFを保存しました: {output_pdf_path}", True)
        except ValueError as e:
            messagebox.showwarning(
                message_manager.get_ui_message("U033"),
                str(e),
                parent=self.winfo_toplevel(),
            )
            self._show_status_feedback(str(e), False)
        except Exception as e:
            logger.error(message_manager.get_log_message("L124", str(e)))
            self._show_status_feedback(f"PDFの保存に失敗しました: {e}", False)

    def _build_export_metadata(self) -> Dict[str, Any]:
        """Build PDF export metadata from the currently rendered page set.

        Returns:
            Metadata containing at least ``page_width`` and ``page_height``.
        """
        export_metadata = dict(self.base_pdf_metadata or self.comp_pdf_metadata)
        first_page_path = None
        if self.base_page_paths:
            first_page_path = self.base_page_paths[0]
        elif self.comp_page_paths:
            first_page_path = self.comp_page_paths[0]

        if first_page_path is not None and first_page_path.exists():
            try:
                with Image.open(first_page_path) as first_image:
                    export_metadata.setdefault("page_width", first_image.width)
                    export_metadata.setdefault("page_height", first_image.height)
            except DecompressionBombError as exc:
                logger.warning(
                    "Export metadata: skipped page dimensions (pixel limit): %s (%s)",
                    first_page_path,
                    exc,
                )
        return export_metadata

    def _on_process_click(self) -> None:
        """Handle process button click event."""
        try:
            # Main processing: convert the selected PDFs into actual page images and build the live workspace.
            logger.debug(message_manager.get_log_message("L074"))
            self._workspace_preview_blocked = False
            self._workspace_raster_limit_dialog_shown = False
            previous_page_index = int(self.current_page_index)
            resolved_dpi = self._get_dpi_from_entry()
            _, dpi_mode = self._get_selected_dpi_from_control()
            self._persist_selected_dpi(resolved_dpi, dpi_mode)
            base_selected = self._path_points_to_file(self.base_path.get())
            comparison_selected = self._path_points_to_file(self.comparison_path.get())
            if not base_selected and not comparison_selected:
                self._show_status_feedback("Select at least one PDF before processing.", False)
                return

            self.base_page_paths = self._convert_pdf_for_workspace(self.base_path.get(), "base") if base_selected else []
            self.comp_page_paths = self._convert_pdf_for_workspace(self.comparison_path.get(), "comp") if comparison_selected else []
            self._sync_workspace_page_lists()
            if self.page_count > 0:
                self.current_page_index = max(0, min(previous_page_index, self.page_count - 1))
            else:
                self.current_page_index = 0
            self._ensure_transform_slots(self.page_count)
            self._create_page_control_frame(self.page_count)
            self._refresh_operation_restriction_state()
            self._setup_mouse_events(self.page_count)
            self._run_blocking_preview_progress(
                message_manager.get_ui_message("U183"),
                lambda: self._display_page(self.current_page_index),
            )
            self._refresh_interaction_state()
            self._workspace_paths_signature_cache = self._current_workspace_paths_signature()
            self.status_var.set(
                "選択したPDFを現在のDPI設定で下のプレビューへ読み込みました。"
            )
        except Exception as e:
            # Failed to process files: {error}
            logger.error(message_manager.get_log_message("L080", str(e)))
            self._show_status_feedback(f"Process failed: {e}", False)

    def _on_base_analyze_click(self) -> None:
        """Handle base file analyze button click event."""
        try:
            # Main processing: prepare histogram data for the base-file analysis graph window.
            logger.debug(message_manager.get_log_message("L075"))
            if self._path_points_to_file(self.base_path.get()):
                histogram_counts = self._prepare_analysis_histogram("base")
                if self._base_file_analyze_btn is not None:
                    self._base_file_analyze_btn.update_graph_data(histogram_counts)
                self.status_var.set(
                    "ベースファイル解析のヒストグラムを更新しました。"
                )
                if not self._has_loaded_workspace_pages():
                    self._render_comparison_placeholder()
            else:
                self._show_status_feedback("Base analyze could not find a valid base PDF path.", False)
        except Exception as e:
            # Failed to analyze base file: {error}
            logger.error(message_manager.get_log_message("L081", str(e)))
            self._show_status_feedback(f"Base analyze failed: {e}", False)

    def _on_comparison_analyze_click(self) -> None:
        """Handle comparison file analyze button click event."""
        try:
            # Main processing: prepare histogram data for the comparison-file analysis graph window.
            logger.debug(message_manager.get_log_message("L076"))
            if self._path_points_to_file(self.comparison_path.get()):
                histogram_counts = self._prepare_analysis_histogram("comp")
                if self._comparison_file_analyze_btn is not None:
                    self._comparison_file_analyze_btn.update_graph_data(histogram_counts)
                self.status_var.set(
                    "比較ファイル解析のヒストグラムを更新しました。"
                )
                if not self._has_loaded_workspace_pages():
                    self._render_comparison_placeholder()
            else:
                self._show_status_feedback("Comparison analyze could not find a valid comparison PDF path.", False)
        except Exception as e:
            # Failed to analyze comparison file: {error}
            logger.error(message_manager.get_log_message("L082", str(e)))
            self._show_status_feedback(f"Comparison analyze failed: {e}", False)

    def _on_execute_click(self) -> None:
        """Apply the current threshold changes to the lower preview."""
        self._on_threshold_apply_click()
