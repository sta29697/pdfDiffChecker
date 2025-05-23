from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Base project root directory path
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Settings file
USER_SETTINGS_FILE: Path = BASE_DIR / "configurations" / "user_settings.json"
THEME_COLOR_FILE: Path = BASE_DIR / "themes" / "dark.json"

# Program mode
# Switch between development and production (Nuitka) modes
PRODUCTION_MODE: bool = True
DEVELOP_MODE: bool = False
program_mode: bool = PRODUCTION_MODE if getattr(sys, "frozen", False) else DEVELOP_MODE

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
LOG_FILE: str = r".\logs\debug.log"
LOG_LEVEL = (
    logging.DEBUG
    if program_mode else logging.INFO
)

# Font settings
font_family: str = "BIZ UDゴシック"
font_size: int = 12

# Operation setting flags
window_set: bool = False
is_base_path_set: bool = False
is_compare_path_set: bool = False
is_output_path_set: bool = False

# Log throttle settings - controls frequency of log messages
# Each setting defines the minimum interval in seconds between log messages of the same type
LOG_THROTTLE_SETTINGS: Dict[str, Dict[str, Any]] = {
    "theme_load": {
        "interval": 60.0,
        "message_code": "L401"  # Theme loading log throttle interval
    },
    "theme_apply": {
        "interval": 60.0,
        "message_code": "L402"  # Theme application log throttle interval
    },
    "window_icon": {
        "interval": 300.0,
        "message_code": "L403"  # Window icon setting log throttle interval
    },
    "temp_dir": {
        "interval": 30.0,
        "message_code": "L404"  # Temporary directory log throttle interval
    },
    "png_load": {
        "interval": 10.0,
        "message_code": "L405"  # PNG file loading log throttle interval
    },
    "transform_update": {
        "interval": 3.0,
        "message_code": "L406"  # Transform update log throttle interval
    },
    "zoom_factor": {
        "interval": 1.0,
        "message_code": "L407"  # Zoom factor log throttle interval
    },
    "image_position": {
        "interval": 5.0,
        "message_code": "L408"  # Image position log throttle interval
    },
    "window_resize": {
        "interval": 0.2,
        "message_code": "L409"  # Window resize log throttle interval
    }
}

# Default user settings
DEFAULT_USER_SET: Dict[str, Dict[str, Any]] = {
    "meta_data": {"user_settings_status": "default"},
    "default": {
        "theme_color": "dark",
        "language": "ja",
        "input_file_path": "直接入力、参照選択",
        "comparison_file_path": "直接入力、参照選択",
        "output_folder_path": "直接入力、参照選択",
        "window_position_x": 500,
        "window_position_y": 10,
        "window_width": 800,
        "window_height": 600,
        "window_geometry": "800x600+500+10",
        "separat_color_threshold": 700,
        "setted_dpi": 96,
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

# Default color theme settings only dark theme
DEFAULT_COLOR_THEME_SET: Dict[str, Dict[str, Any]] = {
    "Window": {"bg": "#1d1d29"},
    "SubWindow": {"bg": "#1d1d29"},
    "Frame": {
        "bg": "#1d1d29",
        "highlightbackground": "#27283a",
        "fg": "#43c0cd",
        "disabledforeground": "#db57c4",
        "selectforeground": "#3e77d2",
        "insertbackground": "#c03755"
    },
    "Notebook": {"bg": "#1d1d29", "fg": "#43c0cd"},
    "Label": {
        "fg": "#fffae3"
    },
    "balloon": {
        "bg": "#222233",
        "fg": "#fffae3"
    },
    "text_box": {
        "bg": "#333344",
        "fg": "#ffffff"
    },
    "primary_combobox": {
        "bg": "#27283a",
        "selectbackground": "#27283a",
        "selectforeground": "#db57c4",
        "fg": "#db57c4",
        "highlightcolor": "#c03755"
    },
    "primary_progressbar": {
        "bg": "#43c0cd",
        "troughcolor": "#27283a",
        "bordercolor": "#c03755"
    },
    "base_file_path_label": {"fg": "#3e77d2", "bg": "#27283a"},
    "comparison_file_path_label": {"fg": "#c03755", "bg": "#27283a"},
    "output_folder_path_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "create_fb_threshold_set_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "dpi_set_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "width_size_set_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "height_size_set_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "base_file_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a"
    },
    "comparison_file_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a"
    },
    "output_folder_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a"
    },
    "fb_threshold_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a"
    },
    "base_image_color_change_button": {
        "fg": "#0000FF",
        "bg": "#0000FF",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "comparison_image_color_change_button": {
        "fg": "#FF0000",
        "bg": "#FF0000",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "base_file_analyze_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "comparison_file_analyze_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "base_image_display_toggle_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "comparison_image_display_toggle_button": {
        "bg": "#1d1d29",
        "fg": "#43c0cd",
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "color_theme_change_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "activebackground": "#43c0cd",
        "activeforeground": "#27283a",
        "relief": "flat"
    },
    "process_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "activebackground": "#43c0cd",
        "activeforeground": "#27283a",
        "relief": "flat"
    },
    "pdf_save_button": {
        "bg": "#27283a",
        "fg": "#43c0cd",
        "activebackground": "#43c0cd",
        "activeforeground": "#27283a",
        "relief": "flat"
    },
    "total_pages_label": {"fg": "#3e77d2", "bg": "#27283a"},
    "change_previous_page_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "change_new_page_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "insert_blank_page_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "create_fb_threshold_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a"
    },
    "create_image_color_select_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "create_layer_select_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "create_path_entry": {
        "fg": "#db57c4",
        "bg": "#27283a",
        "highlightcolor": "#43c0cd",
        "highlightbackground": "#27283a"
    },
    "create_path_select_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "create_path_select_label": {"bg": "#27283a", "fg": "#43c0cd"},
    "create_sub_graph_window_button": {
        "disabledforeground": "#27283a",
        "disabledbackground": "#22a9e9",
        "activeforeground": "#574ed6",
        "activebackground": "#0fd2d6"
    },
    "dpi_label": {"fg": "#43c0cd", "bg": "#27283a"},
    "dpi_entry": {"fg": "#db57c4", "bg": "#27283a", "highlightcolor": "#43c0cd", "highlightbackground": "#27283a", "insertbackground": "#db57c4"}
}
