from __future__ import annotations

import tkinter as tk
import unicodedata
from logging import getLogger
from typing import Dict, Any, Callable, List, Optional, Tuple, cast

from configurations.tool_settings import DEFAULT_COLOR_THEME_SET
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker, resolve_disabled_visual_colors
from utils.utils import get_resource_path
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets as btw
from widgets.base_button import BaseButton
from widgets.base_label_class import BaseLabelClass
from widgets.base_page_change_button import BasePageChangeButton
from widgets.insert_blank_page_button import InsertBlankPageButton
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
res_path = get_resource_path("relative/path/to/your/resource.ext")
# Initialize singleton message manager
message_manager = get_message_manager()

class PageControlFrame(tk.Frame, ThemeColorApplicable, ColoringThemeIF):
    """
    A frame containing page navigation controls, blank insertion, and export button.

    This frame is used within the PDFCompareCanvas to provide page navigation controls
    for PDF files that have been converted to images. It includes:
    - Previous/Next page buttons
    - Page number entry and display
    - Blank page insertion
    - PDF export functionality
    """

    def __init__(
        self,
        parent: tk.Frame,
        color_key: str,
        base_pages: List[str],
        comp_pages: List[str],
        base_transform_data: List[Tuple[float, float, float, float]],
        comp_transform_data: List[Tuple[float, float, float, float]],
        visualized_image: tk.StringVar,
        page_amount_limit: int,
        on_prev_page: Optional[Callable[[], None]] = None,
        on_next_page: Optional[Callable[[], None]] = None,
        on_insert_blank: Optional[Callable[[], None]] = None,
        on_delete_page: Optional[Callable[[], None]] = None,
        on_export: Optional[Callable[[], None]] = None,
        on_page_entry: Optional[Callable[[tk.Event], None]] = None,
        on_transform_value_change: Optional[Callable[[float, float, float, float, set[str]], None]] = None,
        initial_batch_edit_checked: bool = True,
        on_batch_edit_toggle: Optional[Callable[[bool], None]] = None,
        on_rotation_guide: Optional[Callable[[], None]] = None,
        reference_grid_var: Optional[tk.BooleanVar] = None,
        on_reference_grid_toggle: Optional[Callable[[], None]] = None,
        on_base_transform_value_change: Optional[Callable[[float, float, float, float, set[str]], None]] = None,
        on_comp_transform_value_change: Optional[Callable[[float, float, float, float, set[str]], None]] = None,
        on_auto_align_frames: Optional[Callable[[], None]] = None,
        on_auto_align_content: Optional[Callable[[], None]] = None,
        on_auto_align_priority: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize the page control frame.

        Args:
            parent: Parent frame where this frame will be placed
            color_key: Key for color theming
            base_pages: List of base file page paths
            comp_pages: List of comparison file page paths
            base_transform_data: List of transform data tuples for base pages
            comp_transform_data: List of transform data tuples for comparison pages
            visualized_image: StringVar indicating which file is or both files are displayed
            page_amount_limit: Maximum number of pages allowed
            on_prev_page: Callback for previous page button
            on_next_page: Callback for next page button
            on_insert_blank: Callback for blank page insertion
            on_delete_page: Callback for delete page button
            on_export: Callback for export button
            on_page_entry: Callback for page number entry
            initial_batch_edit_checked: Initial checkbox state for batch edit.
            on_batch_edit_toggle: Callback when the batch edit checkbox changes.
            on_rotation_guide: Optional callback to show the custom rotation guide (PDF tab).
            reference_grid_var: When set, show a reference-grid visibility checkbox (PDF tab).
            on_reference_grid_toggle: Optional callback after the reference-grid checkbox changes.
            on_base_transform_value_change: When provided, enables dual-layer mode; callback for base transform.
            on_comp_transform_value_change: Callback for comp transform; triggers dual-layer UI when set.
            on_auto_align_frames: Optional callback for the "Auto-align Frames" button (dual-layer mode only).
            on_auto_align_content: Optional callback for the "Align Content" button (dual-layer mode only).
            on_auto_align_priority: Optional callback for the "Priority Align" button (dual-layer mode only).
        """
        try:
            super().__init__(parent)
            self.__parent: tk.Frame = parent
            self.__color_key: str = color_key
            self.__page_amount_limit: int = page_amount_limit
            self.__on_batch_edit_toggle = on_batch_edit_toggle
            self.__on_rotation_guide = on_rotation_guide
            self.__on_reference_grid_toggle = on_reference_grid_toggle
            self.__reference_grid_var = reference_grid_var
        except Exception as e:
            # Failed to initialize PageControlFrame: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

        # Acquire theme color from ColorThemeManager
        try:
            color_theme_manager = ColorThemeManager()
            current_theme = color_theme_manager.get_current_theme()
            self.__theme_dict: Dict[str, Any] = cast(
                Dict[str, Any], current_theme.get(self.__color_key, {})
            )
            self.__entry_theme_dict: Dict[str, Any] = cast(
                Dict[str, Any],
                current_theme.get(
                    "page_number_entry",
                    current_theme.get(
                        "output_folder_path_entry",
                        current_theme.get(
                            "base_file_path_entry",
                            current_theme.get("dpi_entry", {}),
                        ),
                    ),
                ),
            )
        except Exception as e:
            # Failed to get theme color: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            self.__theme_dict = DEFAULT_COLOR_THEME_SET.get(self.__color_key, {})
            self.__entry_theme_dict = {}

        # Base color settings
        # Fall back to Frame.fg when component-specific key is absent from theme
        frame_theme_init = current_theme.get("Frame", {})
        self.__swfg: str = self.__theme_dict.get(
            "base_font_color", frame_theme_init.get("fg", "#43c0cd"))
        self.__swbg: str = self.__theme_dict.get(
            "base_bg_color", frame_theme_init.get("bg", "#1d1d29"))
        self.__fg: str = self.__theme_dict.get("button_inactive_font_color", "#27283a")
        self.__bg: str = self.__theme_dict.get("button_inactive_bg_color", "#22a9e9")
        self.__acfg: str = self.__theme_dict.get("button_active_font_color", "#574ed6")
        self.__acbg: str = self.__theme_dict.get("button_active_bg_color", "#0fd2d6")
        self.__hlfg: str = self.__theme_dict.get(
            "primary_highlight_font_color", "#43c0cd"
        )
        self.__hlbg: str = self.__theme_dict.get(
            "primary_highlight_bg_color", "#27283a"
        )
        self.__base_fg: str = self.__theme_dict.get("base_fg_color", "#43c0cd")
        self.__base_bg: str = self.__theme_dict.get("base_bg_color", "#1d1d29")

        # Configure frame
        self.configure(
            bg=self.__base_bg,
            highlightthickness=1,
            highlightbackground=self.__swfg,
            highlightcolor=self.__swfg,
            bd=0,
            relief=tk.FLAT,
        )

        # Page variables
        self.page_var = tk.IntVar(value=1)  # Current page (1-based)
        self.current_file_page_amount = tk.IntVar(value=0)  # Total pages

        # Main processing: keep desired edit button enabled state across theme updates.
        self.__edit_buttons_enabled: bool = True
        self.__workspace_controls_enabled: bool = True

        # Page navigation buttons (vertical stack; compact sidebar width for canvas)
        self.prev_page_btn = BasePageChangeButton(
            fr=self,
            color_key="change_previous_page_button",
            text="<",
            command=on_prev_page if on_prev_page else lambda: None,
        )
        self.prev_page_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        # Current page display - Interactive entry that also acts as a label
        self.current_page_label = tk.Entry(
            self,
            textvariable=self.page_var,
            width=5,
            font=btw.base_font,
            bg=self.__entry_theme_dict.get("bg", self.__acbg),  # Use themed Entry background
            fg=self.__entry_theme_dict.get("fg", self.__acfg),  # Use themed Entry foreground
            highlightcolor=self.__entry_theme_dict.get("highlightcolor", self.__hlfg),
            highlightbackground=self.__entry_theme_dict.get("highlightbackground", self.__hlbg),
            insertbackground=self.__entry_theme_dict.get("insertbackground", self.__acfg),
            justify='center', # Center the text for better appearance
            relief='sunken',  # Keep visible border like other input fields
            bd=1,
            highlightthickness=1,
        )
        self.current_page_label.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        # Bind events for interactive behavior
        self.on_page_entry_callback = on_page_entry
        if on_page_entry:
            # Enhance binding to handle both Return and KP_Enter (numpad enter)
            self.current_page_label.bind("<Return>", self._handle_page_entry)
            self.current_page_label.bind("<KP_Enter>", self._handle_page_entry)
            
        # Add focus events to change appearance
        self.current_page_label.bind("<FocusIn>", self._on_entry_focus_in)
        self.current_page_label.bind("<FocusOut>", self._on_entry_focus_out)

        # Total pages display
        self.total_pages_label = BaseLabelClass(
            fr=self,
            color_key="total_pages_label",
            text="/ 0",
        )
        self.total_pages_label.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        # Next page button
        self.next_page_btn = BasePageChangeButton(
            fr=self,
            color_key="change_new_page_button",
            text=">",
            command=on_next_page if on_next_page else lambda: None,
        )
        self.next_page_btn.grid(row=3, column=0, padx=5, pady=5, sticky="ew")

        # Page entry is now integrated with current_page_label above

        # Insert blank page button
        self.insert_blank_btn = InsertBlankPageButton(
            master=self,
            color_key="insert_blank_page_button",
            command=on_insert_blank if on_insert_blank else lambda: None,
        )
        self.insert_blank_btn.grid(row=4, column=0, padx=5, pady=5, sticky="ew")

        # Delete current page button (M1-007)
        self.delete_page_btn = BaseButton(
            fr=self,
            color_key="delete_page_button",
            text=message_manager.get_ui_message("U061"),  # "Delete Page"
            command=on_delete_page if on_delete_page else lambda: None,
        )
        self.delete_page_btn.grid(row=5, column=0, padx=5, pady=5, sticky="ew")

        layout_row = 6

        self.__reference_grid_cb: Optional[tk.Checkbutton] = None
        if reference_grid_var is not None:
            self.__reference_grid_cb = tk.Checkbutton(
                self,
                text=message_manager.get_ui_message("U149"),
                variable=reference_grid_var,
                font=("", 8),
                bg=self.__base_bg,
                fg=self.__swfg,
                selectcolor=self.__base_bg,
                activebackground=self.__base_bg,
                activeforeground=self.__swfg,
                anchor="w",
                command=self._on_reference_grid_checkbox_changed,
            )
            self.__reference_grid_cb.grid(
                row=layout_row, column=0, padx=5, pady=5, sticky="ew"
            )
            layout_row += 1

        # --- Batch edit checkbox (M1-010) ---
        self.batch_edit_var = tk.BooleanVar(value=bool(initial_batch_edit_checked))
        self.__batch_edit_cb = tk.Checkbutton(
            self,
            text=message_manager.get_ui_message("U070"),  # "Batch Edit" / "一括編集"
            variable=self.batch_edit_var,
            font=("", 8),
            bg=self.__base_bg,
            fg=self.__swfg,
            selectcolor=self.__base_bg,
            activebackground=self.__base_bg,
            activeforeground=self.__swfg,
            anchor="center",
            command=self._on_batch_edit_changed,
        )
        self.__batch_edit_cb.grid(row=layout_row, column=0, padx=5, pady=(5, 0), sticky="ew")
        layout_row += 1

        # Store transform value change callbacks
        self.__on_transform_value_change = on_transform_value_change
        # Dual-layer mode: when on_comp_transform_value_change is provided, show separate
        # Base / Comp transform entry sections.
        self.__dual_mode: bool = on_comp_transform_value_change is not None
        self.__on_base_transform_value_change: Optional[Callable] = (
            on_base_transform_value_change or on_transform_value_change
        )
        self.__on_comp_transform_value_change: Optional[Callable] = on_comp_transform_value_change
        self.__on_auto_align_frames: Optional[Callable] = on_auto_align_frames
        self.__on_auto_align_content: Optional[Callable] = on_auto_align_content
        self.__on_auto_align_priority: Optional[Callable] = on_auto_align_priority

        # --- Transform info section (M1-008) ---
        # Separator line
        self.__transform_separator = tk.Frame(self, height=1, bg=self.__swfg)
        self.__transform_separator.grid(row=layout_row, column=0, padx=3, pady=(8, 2), sticky="ew")
        layout_row += 1

        # Header label
        self.__transform_header = tk.Label(
            self,
            text=message_manager.get_ui_message("U064"),  # "Transform" / "変換情報"
            font=("", 8),
            bg=self.__base_bg,
            fg=self.__swfg,
            anchor="center",
        )
        self.__transform_header.grid(row=layout_row, column=0, padx=2, pady=(0, 2), sticky="ew")
        layout_row += 1

        # Entry style settings
        entry_font = ("", 8)
        entry_width = 8
        label_width = 5

        # Lists to hold sub-frame and label references for theme updates (base and comp)
        self.__transform_sub_frames: List[tk.Frame] = []
        self.__transform_labels: List[tk.Label] = []
        self.__comp_transform_sub_frames: List[tk.Frame] = []
        self.__comp_transform_labels: List[tk.Label] = []

        def _make_transform_row(
            parent_frame: tk.Frame,
            row: int,
            label_text: str,
            sub_frames: List[tk.Frame],
            labels: List[tk.Label],
        ) -> tk.Entry:
            """Create a labeled entry row for transform info.

            Args:
                parent_frame: Parent frame to place widgets in.
                row: Grid row number.
                label_text: Label text for the entry.
                sub_frames: List to append the container frame to.
                labels: List to append the label widget to.

            Returns:
                The created Entry widget.
            """
            sub = tk.Frame(parent_frame, bg=self.__base_bg)
            sub.grid(row=row, column=0, padx=2, pady=1, sticky="w")
            sub.grid_columnconfigure(0, weight=0)
            sub.grid_columnconfigure(1, weight=0)
            sub_frames.append(sub)
            lbl = tk.Label(
                sub, text=label_text, font=entry_font, width=label_width,
                bg=self.__base_bg, fg=self.__swfg, anchor="e",
            )
            lbl.grid(row=0, column=0, sticky="e")
            labels.append(lbl)
            ent = tk.Entry(
                sub, font=entry_font, width=entry_width, justify="right",
                bg=self.__entry_theme_dict.get("bg", self.__acbg),
                fg=self.__entry_theme_dict.get("fg", self.__acfg),
                insertbackground=self.__entry_theme_dict.get("insertbackground", self.__acfg),
                relief="sunken", bd=1,
            )
            ent.grid(row=0, column=1, sticky="w", padx=(2, 0))
            return ent

        # --- Base transform section ---
        self.__base_subheader: Optional[tk.Label] = None
        if self.__dual_mode:
            self.__base_subheader = tk.Label(
                self,
                text=message_manager.get_ui_message("U187"),  # "ベース" / "Base"
                font=("", 7),
                bg=self.__base_bg,
                fg=self.__swfg,
                anchor="w",
            )
            self.__base_subheader.grid(row=layout_row, column=0, padx=4, pady=(4, 0), sticky="ew")
            layout_row += 1

        self.__transform_x_entry = _make_transform_row(
            self, layout_row, message_manager.get_ui_message("U065"),
            sub_frames=self.__transform_sub_frames, labels=self.__transform_labels,
        )
        layout_row += 1
        self.__transform_y_entry = _make_transform_row(
            self, layout_row, message_manager.get_ui_message("U066"),
            sub_frames=self.__transform_sub_frames, labels=self.__transform_labels,
        )
        layout_row += 1
        self.__transform_angle_entry = _make_transform_row(
            self, layout_row, message_manager.get_ui_message("U067"),
            sub_frames=self.__transform_sub_frames, labels=self.__transform_labels,
        )
        layout_row += 1
        self.__transform_scale_entry = _make_transform_row(
            self, layout_row, message_manager.get_ui_message("U068"),
            sub_frames=self.__transform_sub_frames, labels=self.__transform_labels,
        )
        layout_row += 1

        # Bind Enter key to base transform entries
        for ent in (self.__transform_x_entry, self.__transform_y_entry,
                    self.__transform_angle_entry, self.__transform_scale_entry):
            ent.bind("<Return>", self._on_base_transform_entry_submit)
            ent.bind("<KP_Enter>", self._on_base_transform_entry_submit)

        self.__rotation_guide_btn: Optional[BaseButton] = None
        if on_rotation_guide is not None:
            self.__rotation_guide_btn = BaseButton(
                fr=self,
                color_key="process_button",
                text=message_manager.get_ui_message("U175"),
                command=on_rotation_guide,
                font=btw.base_font,
            )
            self.__rotation_guide_btn.grid(
                row=layout_row, column=0, padx=5, pady=(10, 6), sticky="ew"
            )
            layout_row += 1

        # --- Auto-align buttons (dual mode only) ---
        self.__auto_align_btn: Optional[BaseButton] = None
        if self.__dual_mode and self.__on_auto_align_frames is not None:
            self.__auto_align_btn = BaseButton(
                fr=self,
                color_key="process_button",
                text=message_manager.get_ui_message("U189"),  # "図枠合わせ" / "Auto-align Frames"
                command=self.__on_auto_align_frames,
                font=btw.base_font,
            )
            self.__auto_align_btn.grid(
                row=layout_row, column=0, padx=5, pady=(6, 2), sticky="ew"
            )
            layout_row += 1

        self.__auto_align_content_btn: Optional[BaseButton] = None
        if self.__dual_mode and self.__on_auto_align_content is not None:
            self.__auto_align_content_btn = BaseButton(
                fr=self,
                color_key="process_button",
                text=message_manager.get_ui_message("U190"),  # "内容合わせ" / "Align Content"
                command=self.__on_auto_align_content,
                font=btw.base_font,
            )
            self.__auto_align_content_btn.grid(
                row=layout_row, column=0, padx=5, pady=(2, 2), sticky="ew"
            )
            layout_row += 1

        self.__auto_align_priority_btn: Optional[BaseButton] = None
        if self.__dual_mode and self.__on_auto_align_priority is not None:
            self.__auto_align_priority_btn = BaseButton(
                fr=self,
                color_key="process_button",
                text=message_manager.get_ui_message("U193"),  # "優先順位合わせ" / "Priority Align"
                command=self.__on_auto_align_priority,
                font=btw.base_font,
            )
            self.__auto_align_priority_btn.grid(
                row=layout_row, column=0, padx=5, pady=(2, 4), sticky="ew"
            )
            layout_row += 1

        # --- Comp transform section (dual mode only) ---
        self.__comp_subheader: Optional[tk.Label] = None
        self.__comp_transform_x_entry: Optional[tk.Entry] = None
        self.__comp_transform_y_entry: Optional[tk.Entry] = None
        self.__comp_transform_angle_entry: Optional[tk.Entry] = None
        self.__comp_transform_scale_entry: Optional[tk.Entry] = None
        if self.__dual_mode:
            self.__comp_subheader = tk.Label(
                self,
                text=message_manager.get_ui_message("U188"),  # "比較" / "Comp"
                font=("", 7),
                bg=self.__base_bg,
                fg=self.__swfg,
                anchor="w",
            )
            self.__comp_subheader.grid(row=layout_row, column=0, padx=4, pady=(6, 0), sticky="ew")
            layout_row += 1

            self.__comp_transform_x_entry = _make_transform_row(
                self, layout_row, message_manager.get_ui_message("U065"),
                sub_frames=self.__comp_transform_sub_frames, labels=self.__comp_transform_labels,
            )
            layout_row += 1
            self.__comp_transform_y_entry = _make_transform_row(
                self, layout_row, message_manager.get_ui_message("U066"),
                sub_frames=self.__comp_transform_sub_frames, labels=self.__comp_transform_labels,
            )
            layout_row += 1
            self.__comp_transform_angle_entry = _make_transform_row(
                self, layout_row, message_manager.get_ui_message("U067"),
                sub_frames=self.__comp_transform_sub_frames, labels=self.__comp_transform_labels,
            )
            layout_row += 1
            self.__comp_transform_scale_entry = _make_transform_row(
                self, layout_row, message_manager.get_ui_message("U068"),
                sub_frames=self.__comp_transform_sub_frames, labels=self.__comp_transform_labels,
            )
            layout_row += 1

            for ent in (self.__comp_transform_x_entry, self.__comp_transform_y_entry,
                        self.__comp_transform_angle_entry, self.__comp_transform_scale_entry):
                ent.bind("<Return>", self._on_comp_transform_entry_submit)
                ent.bind("<KP_Enter>", self._on_comp_transform_entry_submit)

        self.grid_rowconfigure(layout_row, weight=1, minsize=0)
        self.__vertical_tail_spacer = tk.Frame(self, bg=self.__base_bg)
        self.__vertical_tail_spacer.grid(row=layout_row, column=0, sticky="nsew")
        layout_row += 1

        self.export_btn = BaseButton(
            fr=self,
            color_key="pdf_save_button",
            text=message_manager.get_ui_message("U037"),
            command=on_export if on_export else lambda: None,
            font=btw.base_font,
            relief=tk.RAISED,
            bd=2,
            highlightthickness=1,
        )
        self.export_btn.grid(row=layout_row, column=0, padx=5, pady=(4, 6), sticky="ew")

        self.__last_transform_values: Dict[str, float] = {
            "tx": 0.0,
            "ty": 0.0,
            "rotation": 0.0,
            "scale": 1.0,
        }
        self.__last_comp_transform_values: Dict[str, float] = {
            "tx": 0.0,
            "ty": 0.0,
            "rotation": 0.0,
            "scale": 1.0,
        }

        # Initialize entries with default values
        self._set_transform_entries(0.0, 0.0, 0.0, 1.0)
        if self.__dual_mode:
            self._set_comp_transform_entries(0.0, 0.0, 0.0, 1.0)

        # Register for theme updates
        WidgetsTracker().add_widgets(self)
        # Log PageControlFrame initialization
        logger.debug(message_manager.get_log_message("L097"))

    def iter_focus_widgets(self) -> List[tk.Widget]:
        """Return sidebar widgets in top-to-bottom keyboard focus order.

        Returns:
            Interactive widgets from page navigation through export, excluding
            static labels.
        """
        ordered: List[tk.Widget] = [
            self.prev_page_btn,
            self.current_page_label,
            self.next_page_btn,
            self.insert_blank_btn,
            self.delete_page_btn,
        ]
        if self.__reference_grid_cb is not None:
            ordered.append(self.__reference_grid_cb)
        ordered.append(self.__batch_edit_cb)
        ordered.extend(
            [
                self.__transform_x_entry,
                self.__transform_y_entry,
                self.__transform_angle_entry,
                self.__transform_scale_entry,
            ]
        )
        if self.__rotation_guide_btn is not None:
            ordered.append(self.__rotation_guide_btn)
        if self.__auto_align_btn is not None:
            ordered.append(self.__auto_align_btn)
        if self.__auto_align_content_btn is not None:
            ordered.append(self.__auto_align_content_btn)
        if self.__auto_align_priority_btn is not None:
            ordered.append(self.__auto_align_priority_btn)
        if self.__dual_mode and self.__comp_transform_x_entry is not None:
            ordered.extend(
                [
                    self.__comp_transform_x_entry,
                    self.__comp_transform_y_entry,
                    self.__comp_transform_angle_entry,
                    self.__comp_transform_scale_entry,
                ]
            )
        ordered.append(self.export_btn)
        return ordered

    def update_page_label(self, current_index: int, max_pages: int) -> None:
        """Set the display text for current page and total pages.

        Args:
            current_index: Current page index (0-based)
            max_pages: Maximum number of pages
        """
        try:
            # Update page_var which will automatically update the Entry widget
            # (Cannot set text directly on Entry like with Label widgets)
            self.page_var.set(current_index + 1)
            # Update the total pages label (BaseLabelClass has its own configure method)
            if hasattr(self.total_pages_label, "configure"):
                self.total_pages_label.configure(text=f"/ {max_pages}")
                
            # Update max pages tracking variable
            self.current_file_page_amount.set(max_pages)
            
            # Log updated page labels with current index and total pages
            # Use L209 (Page label updated) instead of L098 (Button theme error)
            logger.debug(message_manager.get_log_message("L209", current_index + 1, max_pages))
        except Exception as e:
            # Failed to update page labels: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def set_edit_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable edit-related buttons.

        This method controls the availability of:
        - Insert Blank Page
        - Delete Page
        - Finish (export)

        When disabled, buttons are visually grayed out so they are clearly
        distinguishable from active buttons in every theme (including pastel).

        Args:
            enabled: True to enable, False to disable.
        """
        self.__edit_buttons_enabled = bool(enabled)
        state = tk.NORMAL if enabled else tk.DISABLED
        for widget in (
            getattr(self, "insert_blank_btn", None),
            getattr(self, "delete_page_btn", None),
            getattr(self, "export_btn", None),
        ):
            if widget is None:
                continue
            self._apply_edit_button_visual_state(widget, state)

    def set_workspace_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable page-navigation and transform-entry controls.

        Args:
            enabled: True to enable interactive workspace controls, False to disable them.
        """
        self.__workspace_controls_enabled = bool(enabled)
        state = tk.NORMAL if enabled else tk.DISABLED

        for widget in (
            getattr(self, "prev_page_btn", None),
            getattr(self, "next_page_btn", None),
        ):
            if widget is None:
                continue
            self._apply_edit_button_visual_state(widget, state)

        entry_theme = self.__entry_theme_dict if isinstance(self.__entry_theme_dict, dict) else {}
        disabled_visuals = resolve_disabled_visual_colors(
            str(entry_theme.get("bg", self.__acbg)),
            str(ColorThemeManager().get_current_theme().get("LabelDisabled", {}).get("fg", self.__fg)),
            fallback_bg=self.__base_bg,
            use_emphasis_surface=True,
        )
        disabled_bg = str(disabled_visuals.get("disabled_bg", self.__base_bg))
        disabled_fg = str(disabled_visuals.get("disabled_fg", self.__fg))

        try:
            self.current_page_label.configure(
                state=state,
                disabledbackground=disabled_bg,
                disabledforeground=disabled_fg,
                readonlybackground=disabled_bg,
                bg=entry_theme.get("bg", self.__acbg) if enabled else disabled_bg,
                fg=entry_theme.get("fg", self.__acfg) if enabled else disabled_fg,
                insertbackground=entry_theme.get("insertbackground", self.__acfg) if enabled else disabled_fg,
            )
        except Exception:
            pass

        all_transform_entries = [
            getattr(self, "_PageControlFrame__transform_x_entry", None),
            getattr(self, "_PageControlFrame__transform_y_entry", None),
            getattr(self, "_PageControlFrame__transform_angle_entry", None),
            getattr(self, "_PageControlFrame__transform_scale_entry", None),
            getattr(self, "_PageControlFrame__comp_transform_x_entry", None),
            getattr(self, "_PageControlFrame__comp_transform_y_entry", None),
            getattr(self, "_PageControlFrame__comp_transform_angle_entry", None),
            getattr(self, "_PageControlFrame__comp_transform_scale_entry", None),
        ]
        for ent in all_transform_entries:
            if ent is None:
                continue
            try:
                ent.configure(
                    state=state,
                    disabledbackground=disabled_bg,
                    disabledforeground=disabled_fg,
                    readonlybackground=disabled_bg,
                    bg=entry_theme.get("bg", self.__acbg) if enabled else disabled_bg,
                    fg=entry_theme.get("fg", self.__acfg) if enabled else disabled_fg,
                    insertbackground=entry_theme.get("insertbackground", self.__acfg) if enabled else disabled_fg,
                )
            except Exception:
                continue

    def _apply_edit_button_visual_state(self, widget: tk.Button, state: str) -> None:
        """Apply the page edit button visual state using the resize-tab disabled pattern.

        Args:
            widget: Target button widget.
            state: Target Tk state string.
        """
        theme_snapshot = ColorThemeManager().get_current_theme()
        label_disabled_theme = dict(theme_snapshot.get("LabelDisabled", {}))
        button_theme = dict(
            theme_snapshot.get(
                getattr(widget, "_BaseButton__color_key", "Button"),
                theme_snapshot.get("Button", {}),
            )
        )
        button_bg = str(button_theme.get("bg", self.__bg))
        button_fg = str(button_theme.get("fg", self.__fg))
        active_bg = str(button_theme.get("activebackground", self.__acbg))
        active_fg = str(button_theme.get("activeforeground", self.__acfg))
        disabled_visuals = resolve_disabled_visual_colors(
            button_bg,
            str(label_disabled_theme.get("fg", "#808080")),
            fallback_bg=self.__base_bg,
            use_emphasis_surface=True,
        )
        disabled_bg = disabled_visuals.get("disabled_bg", button_bg)
        disabled_fg = disabled_visuals.get("disabled_fg", button_fg)

        try:
            if state == tk.DISABLED:
                if hasattr(widget, "_disabled_visual_bg"):
                    setattr(widget, "_disabled_visual_bg", str(disabled_bg))
                if hasattr(widget, "_disabled_visual_fg"):
                    setattr(widget, "_disabled_visual_fg", str(disabled_fg))
                widget.configure(
                    state=state,
                    bg=disabled_bg,
                    fg=disabled_fg,
                    disabledforeground=disabled_fg,
                    activebackground=disabled_bg,
                    activeforeground=disabled_fg,
                    highlightbackground=self.__base_bg,
                )
                return

            if hasattr(widget, "_disabled_visual_bg"):
                setattr(widget, "_disabled_visual_bg", str(disabled_bg))
            if hasattr(widget, "_disabled_visual_fg"):
                setattr(widget, "_disabled_visual_fg", str(disabled_fg))
            widget.configure(
                state=state,
                bg=button_bg,
                fg=button_fg,
                disabledforeground=disabled_fg,
                activebackground=active_bg,
                activeforeground=active_fg,
                relief=tk.RAISED,
                bd=2,
                highlightthickness=1,
                highlightbackground=active_bg,
            )
        except Exception:
            return

    def set_batch_edit_enabled(self, enabled: bool) -> None:
        """Enable or disable the batch edit checkbox (M1-010).

        When page sizes differ, batch edit should be disabled.

        Args:
            enabled: True to enable, False to disable.
        """
        try:
            if hasattr(self, '_PageControlFrame__batch_edit_cb'):
                state = tk.NORMAL if enabled else tk.DISABLED
                self.__batch_edit_cb.configure(state=state)
                if not enabled:
                    self.batch_edit_var.set(False)
                    self._on_batch_edit_changed()
        except Exception:
            pass

    def set_batch_edit_checked(self, checked: bool) -> None:
        """Set the batch edit checkbox value.

        Args:
            checked: Checkbox state to apply.
        """
        try:
            self.batch_edit_var.set(bool(checked))
            self._on_batch_edit_changed()
        except Exception:
            pass

    def is_batch_edit_checked(self) -> bool:
        """Return whether batch edit is currently checked.

        Returns:
            ``True`` when the checkbox is checked.
        """
        try:
            return bool(self.batch_edit_var.get())
        except Exception:
            return False

    def _on_reference_grid_checkbox_changed(self) -> None:
        """Notify listeners when the reference-grid checkbox state changes."""
        if self.__on_reference_grid_toggle is None:
            return
        try:
            self.__on_reference_grid_toggle()
        except Exception:
            pass

    def _on_batch_edit_changed(self) -> None:
        """Notify listeners when the batch edit checkbox state changes."""
        if self.__on_batch_edit_toggle is None:
            return

        try:
            self.__on_batch_edit_toggle(bool(self.batch_edit_var.get()))
        except Exception:
            pass

    def _on_entry_focus_in(self, event: tk.Event) -> None:
        """Handle entry focus in event to change appearance.
        
        Args:
            event: Focus in event
        """
        # Change to sunken relief when focused for better visual feedback
        self.current_page_label.config(relief='sunken')
    
    def _on_entry_focus_out(self, event: tk.Event) -> None:
        """Handle entry focus out event to restore appearance.
        
        Args:
            event: Focus out event
        """
        # Keep sunken appearance so the field is recognizable as an input.
        self.current_page_label.config(relief='sunken')
        
    def _handle_page_entry(self, event: tk.Event) -> None:
        """Handle Enter key press in the page entry field.
        
        Args:
            event: Key event
        """
        try:
            # Log the event for debugging
            logger.info(f"Page entry event detected: {self.page_var.get()}")
            
            # Call the callback if it exists
            if self.on_page_entry_callback:
                self.on_page_entry_callback(event)
                
            # Always blur the entry after Enter to improve UX
            self.current_page_label.master.focus_set()
        except Exception as e:
            logger.error(f"Error handling page entry: {str(e)}")
            # Display more detailed error information in debug log
            logger.debug(f"Page entry event handler error details: {type(e).__name__}: {str(e)}")
            # Try to recover by clearing focus
            self.current_page_label.master.focus_set()
        
    @property
    def page_entry(self) -> tk.Entry:
        """Returns the current page label as an entry for backward compatibility
        
        Returns:
            tk.Entry: The current page label (functioning as an entry widget)
        """
        return self.current_page_label
    
    def apply_theme_color(self, theme_data: Dict[str, Dict[str, Any]]) -> None:
        """Apply theme colors to the frame and its widgets.

        Args:
            theme_data (Dict[str, Dict[str, Any]]): Theme data from ColorThemeManager
        """
        try:
            # Get frame / button / component-specific theme settings
            frame_theme = theme_data.get("Frame", {})
            button_theme = theme_data.get("Button", {})
            component_theme: Dict[str, Any] = theme_data.get(self.__color_key, {})

            # Update color variables from theme
            self.__base_bg = frame_theme.get("bg", self.__base_bg)
            self.__base_fg = frame_theme.get("fg", self.__base_fg)
            self.__bg = button_theme.get("bg", self.__bg)
            self.__fg = button_theme.get("fg", self.__fg)
            self.__acbg = button_theme.get("activebackground", self.__acbg)
            self.__acfg = button_theme.get("activeforeground", self.__acfg)

            # Update component-specific colors (used by transform info section)
            # Fall back to Frame.fg/bg when page_control key is absent from theme
            self.__swfg = component_theme.get(
                "base_font_color", frame_theme.get("fg", self.__swfg))
            self.__swbg = component_theme.get(
                "base_bg_color", frame_theme.get("bg", self.__swbg))

            # Apply to frame
            self.configure(
                bg=self.__base_bg,
                highlightthickness=1,
                highlightbackground=self.__swfg,
                highlightcolor=self.__swfg,
                bd=0,
                relief=tk.FLAT,
            )
            # Update Entry widget colors (use the same style as other input entries)
            entry_theme = theme_data.get(
                "page_number_entry",
                theme_data.get(
                    "output_folder_path_entry",
                    theme_data.get(
                        "base_file_path_entry",
                        theme_data.get("dpi_entry", {}),
                    ),
                ),
            )
            self.current_page_label.configure(
                bg=entry_theme.get("bg", self.__acbg),
                fg=entry_theme.get("fg", self.__acfg),
                highlightcolor=entry_theme.get("highlightcolor", self.__hlfg),
                highlightbackground=entry_theme.get("highlightbackground", self.__hlbg),
                insertbackground=entry_theme.get("insertbackground", self.__acfg),
                relief="sunken",
                bd=1,
                highlightthickness=1,
            )

            # Note: total_pages_label, prev/next_page_btn, insert_blank_btn
            # are self-registered with WidgetsTracker and receive
            # apply_theme_color calls automatically. No explicit loop needed.

            # Apply theme to batch edit checkbox (M1-010)
            if hasattr(self, '_PageControlFrame__batch_edit_cb'):
                self.__batch_edit_cb.configure(
                    bg=self.__base_bg, fg=self.__swfg,
                    selectcolor=self.__base_bg,
                    activebackground=self.__base_bg,
                    activeforeground=self.__swfg,
                )

            if self.__reference_grid_cb is not None:
                self.__reference_grid_cb.configure(
                    bg=self.__base_bg,
                    fg=self.__swfg,
                    selectcolor=self.__base_bg,
                    activebackground=self.__base_bg,
                    activeforeground=self.__swfg,
                )

            if hasattr(self, "_PageControlFrame__vertical_tail_spacer"):
                self.__vertical_tail_spacer.configure(bg=self.__base_bg)

            # Apply theme to transform info section (M1-008)
            if hasattr(self, '_PageControlFrame__transform_separator'):
                self.__transform_separator.configure(bg=self.__swfg)
                self.__transform_header.configure(
                    bg=self.__base_bg, fg=self.__swfg)
                for sub in self.__transform_sub_frames:
                    sub.configure(bg=self.__base_bg)
                for lbl in self.__transform_labels:
                    lbl.configure(bg=self.__base_bg, fg=self.__swfg)
                for ent in (self.__transform_x_entry, self.__transform_y_entry,
                            self.__transform_angle_entry, self.__transform_scale_entry):
                    ent.configure(
                        bg=entry_theme.get("bg", self.__acbg),
                        fg=entry_theme.get("fg", self.__acfg),
                        insertbackground=entry_theme.get("insertbackground", self.__acfg),
                    )
                # Dual-layer: apply theme to sub-headers and comp entries
                if self.__dual_mode:
                    if self.__base_subheader is not None:
                        self.__base_subheader.configure(bg=self.__base_bg, fg=self.__swfg)
                    if self.__comp_subheader is not None:
                        self.__comp_subheader.configure(bg=self.__base_bg, fg=self.__swfg)
                    for sub in self.__comp_transform_sub_frames:
                        sub.configure(bg=self.__base_bg)
                    for lbl in self.__comp_transform_labels:
                        lbl.configure(bg=self.__base_bg, fg=self.__swfg)
                    for ent in (
                        self.__comp_transform_x_entry, self.__comp_transform_y_entry,
                        self.__comp_transform_angle_entry, self.__comp_transform_scale_entry,
                    ):
                        if ent is not None:
                            ent.configure(
                                bg=entry_theme.get("bg", self.__acbg),
                                fg=entry_theme.get("fg", self.__acfg),
                                insertbackground=entry_theme.get("insertbackground", self.__acfg),
                            )

            if self.__rotation_guide_btn is not None:
                try:
                    self.__rotation_guide_btn.configure(
                        text=message_manager.get_ui_message("U175"),
                    )
                except Exception:
                    pass

            # Main processing: re-apply edit buttons state (e.g. copy-protected mode).
            self.__entry_theme_dict = cast(Dict[str, Any], entry_theme)
            self.set_workspace_controls_enabled(self.__workspace_controls_enabled)
            self.set_edit_buttons_enabled(self.__edit_buttons_enabled)
            self.set_batch_edit_checked(self.is_batch_edit_checked())

            logger.debug(message_manager.get_log_message("L173"))
        except Exception as e:
            logger.error(message_manager.get_log_message("L174", str(e)))
            raise

    def _config_widget(self, theme_settings: Dict[str, Any]) -> None:
        """Apply theme settings to the frame.

        Args:
            theme_settings (Dict[str, Any]): Theme settings to apply
        """
        try:
            # Apply settings to this frame and its components
            self.configure(
                **{
                    k: v
                    for k, v in theme_settings.items()
                    if k in ["bg", "fg", "bd", "relief"]
                }
            )

            # Apply settings to BaseLabelClass widgets
            # Check both for attribute existence and if it's callable
            if hasattr(self.total_pages_label, "configure"):
                # BaseLabelClass uses direct configuration
                self.total_pages_label.configure(
                    bg=theme_settings.get("bg", self.__bg),
                    fg=theme_settings.get("fg", self.__fg)
                )
                
            # Entry widget needs direct configuration
            self.current_page_label.configure(
                bg=theme_settings.get("bg", self.__acbg),
                fg=theme_settings.get("fg", self.__acfg),
                relief=theme_settings.get("relief", "sunken"),
                bd=theme_settings.get("bd", 1),
                highlightthickness=theme_settings.get("highlightthickness", 1),
            )
        except Exception as e:
            logger.error(message_manager.get_log_message("L175", str(e)))
            raise

    # --- Transform info methods (M1-008) ---

    def _set_transform_entries(self, tx: float, ty: float,
                               angle: float, scale: float) -> None:
        """Set the text content of the base transform entry fields.

        Args:
            tx: X translation offset.
            ty: Y translation offset.
            angle: Rotation angle in degrees.
            scale: Scale factor.
        """
        for ent, val, fmt in (
            (self.__transform_x_entry, tx, "{:.1f}"),
            (self.__transform_y_entry, ty, "{:.1f}"),
            (self.__transform_angle_entry, angle, "{:.1f}"),
            (self.__transform_scale_entry, scale, "{:.3f}"),
        ):
            ent.delete(0, tk.END)
            ent.insert(0, fmt.format(val))
        self.__last_transform_values = {
            "tx": float(tx),
            "ty": float(ty),
            "rotation": float(angle),
            "scale": float(scale),
        }

    def _set_comp_transform_entries(self, tx: float, ty: float,
                                    angle: float, scale: float) -> None:
        """Set the text content of the comp transform entry fields (dual mode only).

        Args:
            tx: X translation offset.
            ty: Y translation offset.
            angle: Rotation angle in degrees.
            scale: Scale factor.
        """
        if not self.__dual_mode:
            return
        for ent, val, fmt in (
            (self.__comp_transform_x_entry, tx, "{:.1f}"),
            (self.__comp_transform_y_entry, ty, "{:.1f}"),
            (self.__comp_transform_angle_entry, angle, "{:.1f}"),
            (self.__comp_transform_scale_entry, scale, "{:.3f}"),
        ):
            if ent is None:
                continue
            ent.delete(0, tk.END)
            ent.insert(0, fmt.format(val))
        self.__last_comp_transform_values = {
            "tx": float(tx),
            "ty": float(ty),
            "rotation": float(angle),
            "scale": float(scale),
        }

    def update_transform_info(self, rotation: float, tx: float,
                              ty: float, scale: float) -> None:
        """Update the base transform info display with current values.

        Called externally (e.g. from pdf_ope_tab) whenever the transform
        data for the active page changes.  In dual-layer mode prefer the
        dedicated ``update_base_transform_info`` / ``update_comp_transform_info``
        methods instead.

        Args:
            rotation: Rotation angle in degrees.
            tx: X translation offset.
            ty: Y translation offset.
            scale: Scale factor.
        """
        focused = self.focus_get()
        transform_entries = (
            self.__transform_x_entry, self.__transform_y_entry,
            self.__transform_angle_entry, self.__transform_scale_entry,
        )
        if focused in transform_entries:
            return
        self._set_transform_entries(tx, ty, rotation, scale)

    def update_base_transform_info(self, rotation: float, tx: float,
                                   ty: float, scale: float) -> None:
        """Update the base-layer transform entry fields.

        Skips the update when a base entry currently has keyboard focus to
        avoid overwriting in-progress user input.

        Args:
            rotation: Rotation angle in degrees.
            tx: X translation offset.
            ty: Y translation offset.
            scale: Scale factor.
        """
        focused = self.focus_get()
        base_entries = (
            self.__transform_x_entry, self.__transform_y_entry,
            self.__transform_angle_entry, self.__transform_scale_entry,
        )
        if focused in base_entries:
            return
        self._set_transform_entries(tx, ty, rotation, scale)

    def update_comp_transform_info(self, rotation: float, tx: float,
                                   ty: float, scale: float) -> None:
        """Update the comp-layer transform entry fields (dual mode only).

        Skips the update when a comp entry currently has keyboard focus to
        avoid overwriting in-progress user input.

        Args:
            rotation: Rotation angle in degrees.
            tx: X translation offset.
            ty: Y translation offset.
            scale: Scale factor.
        """
        if not self.__dual_mode:
            return
        focused = self.focus_get()
        comp_entries = (
            self.__comp_transform_x_entry, self.__comp_transform_y_entry,
            self.__comp_transform_angle_entry, self.__comp_transform_scale_entry,
        )
        if focused in comp_entries:
            return
        self._set_comp_transform_entries(tx, ty, rotation, scale)

    def commit_transform_entries(self) -> None:
        """Apply the current transform entry values without requiring Enter.

        This is used before export so pending text edits in the transform fields
        are reflected in the saved output.
        """
        self._on_base_transform_entry_submit(cast(tk.Event, None))
        if self.__dual_mode:
            self._on_comp_transform_entry_submit(cast(tk.Event, None))

    @staticmethod
    def _normalize_fullwidth(text: str) -> str:
        """Convert full-width characters to half-width equivalents.

        Handles full-width digits (０-９), minus (−/ー), period (．),
        and plus (＋) which users may accidentally type with Japanese IME.

        Args:
            text: Input string potentially containing full-width characters.

        Returns:
            String with full-width numeric characters converted to half-width.
        """
        # Use NFKC normalization to convert full-width ASCII to half-width
        normalized = unicodedata.normalize("NFKC", text)
        # Also handle katakana prolonged sound mark (ー) used as minus
        normalized = normalized.replace("\u30FC", "-")
        return normalized.strip()

    def _on_transform_entry_submit(self, event: tk.Event) -> None:
        """Backward-compatible alias for ``_on_base_transform_entry_submit``."""
        self._on_base_transform_entry_submit(event)

    def _on_base_transform_entry_submit(self, event: tk.Event) -> None:
        """Handle Enter key press in a base transform entry field.

        Reads the base entry values, validates them, and invokes the base
        transform change callback.  Full-width characters are converted to
        half-width automatically.

        Args:
            event: Key event from the Entry widget (may be None when called
                from ``commit_transform_entries``).
        """
        try:
            from utils.input_normalization import parse_strict_float

            tx = parse_strict_float(self._normalize_fullwidth(self.__transform_x_entry.get()))
            ty = parse_strict_float(self._normalize_fullwidth(self.__transform_y_entry.get()))
            angle = parse_strict_float(self._normalize_fullwidth(self.__transform_angle_entry.get()))
            scale = parse_strict_float(self._normalize_fullwidth(self.__transform_scale_entry.get()))
        except ValueError:
            logger.warning("Base transform entry: invalid numeric input ignored")
            return

        if scale < 0.01:
            scale = 0.01
        elif scale > 10.0:
            scale = 10.0

        previous_values = dict(self.__last_transform_values)
        self._set_transform_entries(tx, ty, angle, scale)

        cb = self.__on_base_transform_value_change
        if cb is not None:
            changed_fields: set[str] = set()
            if abs(tx - float(previous_values.get("tx", 0.0))) > 1e-6:
                changed_fields.add("tx")
            if abs(ty - float(previous_values.get("ty", 0.0))) > 1e-6:
                changed_fields.add("ty")
            if abs(angle - float(previous_values.get("rotation", 0.0))) > 1e-6:
                changed_fields.add("rotation")
            if abs(scale - float(previous_values.get("scale", 1.0))) > 1e-6:
                changed_fields.add("scale")
            cb(angle, tx, ty, scale, changed_fields)
            self.__last_transform_values = {
                "tx": float(tx),
                "ty": float(ty),
                "rotation": float(angle),
                "scale": float(scale),
            }

        self.focus_set()

    def _on_comp_transform_entry_submit(self, event: tk.Event) -> None:
        """Handle Enter key press in a comp transform entry field (dual mode only).

        Reads the comp entry values, validates them, and invokes the comp
        transform change callback.

        Args:
            event: Key event from the Entry widget (may be None when called
                from ``commit_transform_entries``).
        """
        if not self.__dual_mode:
            return
        try:
            from utils.input_normalization import parse_strict_float

            tx = parse_strict_float(self._normalize_fullwidth(self.__comp_transform_x_entry.get()))
            ty = parse_strict_float(self._normalize_fullwidth(self.__comp_transform_y_entry.get()))
            angle = parse_strict_float(self._normalize_fullwidth(self.__comp_transform_angle_entry.get()))
            scale = parse_strict_float(self._normalize_fullwidth(self.__comp_transform_scale_entry.get()))
        except ValueError:
            logger.warning("Comp transform entry: invalid numeric input ignored")
            return

        if scale < 0.01:
            scale = 0.01
        elif scale > 10.0:
            scale = 10.0

        previous_values = dict(self.__last_comp_transform_values)
        self._set_comp_transform_entries(tx, ty, angle, scale)

        cb = self.__on_comp_transform_value_change
        if cb is not None:
            changed_fields: set[str] = set()
            if abs(tx - float(previous_values.get("tx", 0.0))) > 1e-6:
                changed_fields.add("tx")
            if abs(ty - float(previous_values.get("ty", 0.0))) > 1e-6:
                changed_fields.add("ty")
            if abs(angle - float(previous_values.get("rotation", 0.0))) > 1e-6:
                changed_fields.add("rotation")
            if abs(scale - float(previous_values.get("scale", 1.0))) > 1e-6:
                changed_fields.add("scale")
            cb(angle, tx, ty, scale, changed_fields)
            self.__last_comp_transform_values = {
                "tx": float(tx),
                "ty": float(ty),
                "rotation": float(angle),
                "scale": float(scale),
            }

        self.focus_set()
