from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

# Base project root directory path
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Settings file
THEME_COLOR_FILE: Path = BASE_DIR / "themes" / "dark.json"

# Program mode
# Main processing: treat frozen PyInstaller/Nuitka builds and standalone .exe launches as
# production so temp/logs/settings use Windows-standard locations (not the extract dir).


def _is_packaged_executable() -> bool:
    """Return True when running as a built executable (not ``python main.py``).

    PyInstaller sets ``sys.frozen``. Nuitka may set it inconsistently, so we also
    treat a Nuitka-compiled main module (``__compiled__``) and a non-Python
    ``.exe`` in ``sys.argv[0]`` as packaged production builds.

    Returns:
        bool: Whether production-style path rules should apply.
    """
    if getattr(sys, "frozen", False):
        return True
    try:
        import __main__ as _main

        if "__compiled__" in getattr(_main, "__dict__", {}):
            return True
    except Exception:
        pass
    try:
        argv0 = (sys.argv[0] if sys.argv else "").strip()
        if not argv0:
            return False
        base = os.path.basename(argv0).lower()
        return base.endswith(".exe") and "python" not in base
    except Exception:
        return False


PRODUCTION_MODE: bool = _is_packaged_executable()
DEVELOP_MODE: bool = not PRODUCTION_MODE
program_mode: bool = PRODUCTION_MODE
is_production_mode: bool = PRODUCTION_MODE
is_development_mode: bool = DEVELOP_MODE


def _resolve_local_appdata_root() -> Path:
    """Resolve the per-user Local AppData base directory.

    Returns:
        Path: Local AppData directory used for persistent user data.
    """
    local_appdata = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_appdata:
        return Path(local_appdata)
    return Path.home() / "AppData" / "Local"


def _resolve_runtime_storage_root() -> Path:
    """Resolve the storage root for runtime-generated files.

    Returns:
        Path: Root directory for temporary and log files.
    """
    if is_production_mode:
        return Path(tempfile.gettempdir()) / "pdfDiffChecker"
    return BASE_DIR


def _resolve_user_settings_root() -> Path:
    """Resolve the root directory used for persisted user settings.

    Returns:
        Path: Per-user settings directory for the active runtime mode.
    """
    if is_production_mode:
        return _resolve_local_appdata_root() / "pdfDiffChecker"
    return BASE_DIR


def _resolve_user_settings_file() -> Path:
    """Resolve the persisted user-settings file path.

    Returns:
        Path: Settings JSON path for the active runtime mode.
    """
    if is_production_mode:
        return USER_SETTINGS_ROOT / "configurations" / "user_settings.json"
    return BASE_DIR / "configurations" / "user_settings.json"


USER_SETTINGS_ROOT: Path = _resolve_user_settings_root()
RUNTIME_STORAGE_ROOT: Path = _resolve_runtime_storage_root()
TEMP_DIR: Path = RUNTIME_STORAGE_ROOT / "temp"
LOG_DIR: Path = (RUNTIME_STORAGE_ROOT if is_production_mode else BASE_DIR / "logs")
USER_SETTINGS_FILE: Path = _resolve_user_settings_file()
LOG_FILE_PATH: Path = (
    LOG_DIR / "pdfDiffChecker.log"
    if is_production_mode
    else LOG_DIR / "debug.log"
)
RUNTIME_ICON_ICO_PATH: Path = TEMP_DIR / "LOGOm.ico"


def ensure_runtime_directories() -> None:
    """Create the runtime temp and log directories when they are missing."""
    # Main processing: centralize runtime-generated file locations for both modes.
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    USER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Application title - Using message code instead of hardcoded string
APP_TITLE_CODE: str = "U009"  # "PDF Difference Checker"

# Tab names - Using message codes instead of hardcoded strings
# These will be retrieved using MessageManager.get_ui_message()
MAIN_TAB_NAME_CODE: str = "U004"  # "Main"
PDF_OPERATION_TAB_NAME_CODE: str = "U005"  # "PDF Operation"
FILE_EXTENSION_AND_SIZE_TAB_NAME_CODE: str = (
    "U006"  # "File Extension and Size"
)
DESCRIPTION_TAB_NAME_CODE: str = "U007"  # "Description"
LICENSES_TAB_NAME_CODE: str = "U008"  # "Licenses"
CONVERT_IMAGE_BUTTON_NAME_CODE: str = "U014"  # "Convert"

# Language settings
LANGUAGE_CODES: Dict[str, str] = {
    "ja": "日本語",
    "en": "English"
}
DEFAULT_LANGUAGE: str = "ja"

# Logging information
LOG_FILE: str = str(LOG_FILE_PATH)
LOG_LEVEL = (
    logging.DEBUG
    if is_development_mode else logging.INFO
)

# Font settings
font_family: str = "BIZ UDゴシック"
font_size: int = 12

# Operation setting flags
window_set: bool = True
is_base_path_set: bool = False
is_compare_path_set: bool = False
is_output_path_set: bool = False

# Default user settings (``default`` body must match ``configurations/user_settings.json``).
DEFAULT_USER_SET: Dict[str, Dict[str, Any]] = {
    "meta_data": {"user_settings_status": "default"},
    "default": {
        "theme_color": "dark",
        "language": "ja",
        "window_set": True,
        "input_file_path": "直接入力、参照選択",
        "base_file_path": "C:\\Users",
        "comparison_file_path": "C:\\Users",
        "output_folder_path": "C:\\Users",
        "show_base_layer": True,
        "show_comp_layer": True,
        "show_reference_grid": False,
        "window_position_x": 500,
        "window_position_y": 10,
        "window_width": 846,
        "window_height": 859,
        "window_geometry": "846x859+500+10",
        "window_state": "normal",
        "window_display_width": 0,
        "window_display_height": 0,
        "separat_color_threshold": 700,
        "base_separat_color_threshold": 700,
        "comparison_separat_color_threshold": 700,
        "color_processing_mode": "指定色濃淡",
        "setted_dpi": 300,
        "setted_dpi_mode": "detected",
        "preview_scale": 1.0,
        "pdf_operation_preview_scale": 1.0,
        "setted_alpha": 127,
        "dpi_list": [72, 96, 144, 150, 300, 600, 720, 1200, 2400, 3600, 4000],
        "base_file_graph_subwindow_pos_x": 300,
        "base_file_graph_subwindow_pos_y": 300,
        "base_file_graph_subwindow_width": 500,
        "base_file_graph_subwindow_height": 10,
        "base_file_graph_subwindow_geometry": "500x10+300+300",
        "comparison_file_graph_subwindow_pos_x": 300,
        "comparison_file_graph_subwindow_pos_y": 300,
        "comparison_file_graph_subwindow_width": 500,
        "comparison_file_graph_subwindow_height": 10,
        "comparison_file_graph_subwindow_geometry": "500x10+300+300",
    },
}

# Fallback dark theme when ``themes/dark.json`` cannot be loaded (must match that file).
DEFAULT_COLOR_THEME_SET: Dict[str, Dict[str, Any]] = {
    "Window": {"bg": "#1d1d29"},
    "SubWindow": {"bg": "#1d1d29"},
    "Frame": {
        "bg": "#1d1d29",
        "highlightbackground": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#db57c4",
        "selectforeground": "#3e77d2",
        "insertbackground": "#c03755",
    },
    "Label": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#db57c4",
    },
    "Notebook": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "tab_bg": "#27283a",
        "tab_fg": "#43c0cd",
    },
    "primary_combobox": {
        "bg": "#27283a",
        "selectbackground": "#27283a",
        "selectforeground": "#db57c4",
        "fg": "#db57c4",
        "highlightcolor": "#c03755",
    },
    "primary_progressbar": {
        "bg": "#43c0cd",
        "troughcolor": "#27283a",
        "bordercolor": "#c03755",
    },
    "base_file_path_label": {"fg": "#3e77d2", "bg": "#27283a"},
    "comparison_file_path_label": {"fg": "#c03755", "bg": "#27283a"},
    "output_folder_path_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "create_fb_threshold_set_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "dpi_set_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "dpi_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "dpi_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "width_size_set_label": {"fg": "#43c0cd", "bg": "#1d1d29"},
    "height_size_set_label": {"fg": "#43c0cd", "bg": "#1d1d29"},
    "base_file_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "comparison_file_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "output_folder_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "fb_threshold_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "create_fb_threshold_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "create_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "base_image_color_change_button": {
        "fg": "#0000FF",
        "bg": "#0000FF",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "comparison_image_color_change_button": {
        "fg": "#FF0000",
        "bg": "#FF0000",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "base_file_analyze_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "comparison_file_analyze_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "base_image_display_toggle_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "comparison_image_display_toggle_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "total_pages_label": {"fg": "#3e77d2", "bg": "#27283a"},
    "change_previous_page_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#27283a",
        "activebackground": "#43c0cd",
    },
    "change_new_page_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "insert_blank_page_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#27283a",
        "activebackground": "#43c0cd",
    },
    "delete_page_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#27283a",
        "activebackground": "#43c0cd",
    },
    "color_theme_change_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "activebackground": "#43c0cd",
        "activeforeground": "#27283a",
        "relief": "flat",
    },
    "process_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "activebackground": "#43c0cd",
        "activeforeground": "#27283a",
        "relief": "raised",
    },
    "pdf_save_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "activebackground": "#43c0cd",
        "activeforeground": "#27283a",
        "relief": "raised",
    },
    "create_image_color_select_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "create_layer_select_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "create_path_select_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "create_path_select_label": {"bg": "#27283a", "fg": "#43c0cd"},
    "create_sub_graph_window_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "convert_image_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6",
    },
    "ext_convert_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#555555",
        "disabledbackground": "#1d1d29",
        "activeforeground": "#27283a",
        "activebackground": "#43c0cd",
    },
    "size_convert_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#555555",
        "disabledbackground": "#1d1d29",
        "activeforeground": "#27283a",
        "activebackground": "#43c0cd",
    },
    "meta_info_label": {"fg": "#8888aa", "bg": "#1d1d29"},
    "warning_label": {"fg": "#ff6b6b", "bg": "#1d1d29"},
    "conversion_arrow_label": {"fg": "#43c0cd", "bg": "#1d1d29"},
    "section_header_label": {"fg": "#43c0cd", "bg": "#1d1d29"},
    "filename_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "entry_normal": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a",
        "insertbackground": "#db57c4",
    },
    "canvas": {
        "background": "#ffffff",
        "highlightbackground": "#e0e0e0",
        "highlightcolor": "#e0e0e0",
    },
}
