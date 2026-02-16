from __future__ import annotations

import tkinter as tk
import unicodedata
from logging import getLogger
from typing import Dict, Any, Callable, List, Optional, Tuple, cast

from configurations.tool_settings import DEFAULT_COLOR_THEME_SET
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker
from utils.utils import get_resource_path
from themes.coloring_theme_interface import ColoringThemeIF
from widgets.base_tab_widgets import BaseTabWidgets as btw
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
        on_transform_value_change: Optional[Callable[[float, float, float, float], None]] = None,
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
        """
        try:
            super().__init__(parent)
            self.__parent: tk.Frame = parent
            self.__color_key: str = color_key
            self.__page_amount_limit: int = page_amount_limit
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
        self.configure(bg=self.__base_bg)

        # Page variables
        self.page_var = tk.IntVar(value=1)  # Current page (1-based)
        self.current_file_page_amount = tk.IntVar(value=0)  # Total pages

        # Main processing: keep desired edit button enabled state across theme updates.
        self.__edit_buttons_enabled: bool = True

        # Page navigation buttons
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
        from widgets.base_button import BaseButton
        self.delete_page_btn = BaseButton(
            fr=self,
            color_key="delete_page_button",
            text=message_manager.get_ui_message("U061"),  # "Delete Page"
            command=on_delete_page if on_delete_page else lambda: None,
        )
        self.delete_page_btn.grid(row=5, column=0, padx=5, pady=5, sticky="ew")

        # Export button
        self.export_btn: tk.Button = tk.Button(
            self,
            text=message_manager.get_ui_message("U037"), # Save
            font=btw.base_font,
            bg=self.__bg,
            fg=self.__fg,
            activeforeground=self.__acfg,
            activebackground=self.__acbg,
            command=on_export if on_export else lambda: None,
        )
        self.export_btn.grid(row=6, column=0, padx=5, pady=5, sticky="ew")

        # --- Batch edit checkbox (M1-010) ---
        self.batch_edit_var = tk.BooleanVar(value=False)
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
        )
        self.__batch_edit_cb.grid(row=7, column=0, padx=5, pady=(5, 0), sticky="ew")

        # Store transform value change callback
        self.__on_transform_value_change = on_transform_value_change

        # --- Transform info section (M1-008) ---
        # Separator line
        self.__transform_separator = tk.Frame(self, height=1, bg=self.__swfg)
        self.__transform_separator.grid(row=8, column=0, padx=3, pady=(8, 2), sticky="ew")

        # Header label
        self.__transform_header = tk.Label(
            self,
            text=message_manager.get_ui_message("U064"),  # "Transform" / "変換情報"
            font=("", 8),
            bg=self.__base_bg,
            fg=self.__swfg,
            anchor="center",
        )
        self.__transform_header.grid(row=9, column=0, padx=2, pady=(0, 2), sticky="ew")

        # Entry style settings
        entry_font = ("", 8)
        entry_width = 8
        label_width = 5

        # Lists to hold sub-frame and label references for theme updates
        self.__transform_sub_frames: List[tk.Frame] = []
        self.__transform_labels: List[tk.Label] = []

        # Helper to create a label+entry row
        def _make_transform_row(parent_frame: tk.Frame, row: int,
                                label_text: str) -> tk.Entry:
            """Create a labeled entry row for transform info.

            Args:
                parent_frame: Parent frame to place widgets in.
                row: Grid row number.
                label_text: Label text for the entry.

            Returns:
                The created Entry widget.
            """
            sub = tk.Frame(parent_frame, bg=self.__base_bg)
            sub.grid(row=row, column=0, padx=2, pady=1, sticky="ew")
            sub.grid_columnconfigure(1, weight=1)
            self.__transform_sub_frames.append(sub)
            lbl = tk.Label(
                sub, text=label_text, font=entry_font, width=label_width,
                bg=self.__base_bg, fg=self.__swfg, anchor="e",
            )
            lbl.grid(row=0, column=0, sticky="e")
            self.__transform_labels.append(lbl)
            ent = tk.Entry(
                sub, font=entry_font, width=entry_width, justify="right",
                bg=self.__entry_theme_dict.get("bg", self.__acbg),
                fg=self.__entry_theme_dict.get("fg", self.__acfg),
                insertbackground=self.__entry_theme_dict.get("insertbackground", self.__acfg),
                relief="sunken", bd=1,
            )
            ent.grid(row=0, column=1, sticky="ew", padx=(2, 0))
            return ent

        # Create transform entry fields
        self.__transform_x_entry = _make_transform_row(self, 10,
            message_manager.get_ui_message("U065"))   # "X:"
        self.__transform_y_entry = _make_transform_row(self, 11,
            message_manager.get_ui_message("U066"))   # "Y:"
        self.__transform_angle_entry = _make_transform_row(self, 12,
            message_manager.get_ui_message("U067"))   # "Angle:" / "角度:"
        self.__transform_scale_entry = _make_transform_row(self, 13,
            message_manager.get_ui_message("U068"))   # "Scale:" / "倍率:"

        # Bind Enter key to apply transform values
        for ent in (self.__transform_x_entry, self.__transform_y_entry,
                    self.__transform_angle_entry, self.__transform_scale_entry):
            ent.bind("<Return>", self._on_transform_entry_submit)
            ent.bind("<KP_Enter>", self._on_transform_entry_submit)

        # Initialize entries with default values
        self._set_transform_entries(0.0, 0.0, 0.0, 1.0)

        # Register for theme updates
        WidgetsTracker().add_widgets(self)
        # Log PageControlFrame initialization
        logger.debug(message_manager.get_log_message("L097"))

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
        - Finish (export)

        When disabled, buttons are visually grayed out so they are clearly
        distinguishable from active buttons in every theme (including pastel).

        Args:
            enabled: True to enable, False to disable.
        """
        self.__edit_buttons_enabled = bool(enabled)
        # Main processing: disable edit operations for copy-protected PDFs.
        state = tk.NORMAL if enabled else tk.DISABLED
        # Disabled appearance: uniform gray to make inactivity obvious
        disabled_bg = "#b0b0b0"
        disabled_fg = "#808080"
        try:
            if hasattr(self, "insert_blank_btn"):
                if enabled:
                    self.insert_blank_btn.configure(
                        state=state, bg=self.__bg, fg=self.__fg,
                        disabledforeground=disabled_fg,
                    )
                else:
                    self.insert_blank_btn.configure(
                        state=state, bg=disabled_bg,
                        disabledforeground=disabled_fg,
                    )
        except Exception:
            pass

        try:
            if hasattr(self, "delete_page_btn"):
                if enabled:
                    self.delete_page_btn.configure(
                        state=state, bg=self.__bg, fg=self.__fg,
                        disabledforeground=disabled_fg,
                    )
                else:
                    self.delete_page_btn.configure(
                        state=state, bg=disabled_bg,
                        disabledforeground=disabled_fg,
                    )
        except Exception:
            pass

        try:
            if hasattr(self, "export_btn"):
                if enabled:
                    self.export_btn.configure(
                        state=state, bg=self.__bg, fg=self.__fg,
                        disabledforeground=disabled_fg,
                    )
                else:
                    self.export_btn.configure(
                        state=state, bg=disabled_bg,
                        disabledforeground=disabled_fg,
                    )
        except Exception:
            pass

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
            self.configure(bg=self.__base_bg)

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

            # Apply theme to export button (plain tk.Button, not self-registered)
            self.export_btn.configure(
                bg=self.__bg,
                fg=self.__fg,
                activeforeground=self.__acfg,
                activebackground=self.__acbg,
            )

            # Apply theme to batch edit checkbox (M1-010)
            if hasattr(self, '_PageControlFrame__batch_edit_cb'):
                self.__batch_edit_cb.configure(
                    bg=self.__base_bg, fg=self.__swfg,
                    selectcolor=self.__base_bg,
                    activebackground=self.__base_bg,
                    activeforeground=self.__swfg,
                )

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

            # Main processing: re-apply edit buttons state (e.g. copy-protected mode).
            self.set_edit_buttons_enabled(self.__edit_buttons_enabled)

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
        """Set the text content of all transform entry fields.

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

    def update_transform_info(self, rotation: float, tx: float,
                              ty: float, scale: float) -> None:
        """Update the transform info display with current values.

        Called externally (e.g. from pdf_ope_tab) whenever the transform
        data for the active page changes.

        Args:
            rotation: Rotation angle in degrees.
            tx: X translation offset.
            ty: Y translation offset.
            scale: Scale factor.
        """
        # Only update if the entry does not currently have keyboard focus
        # (to avoid overwriting user input in progress).
        focused = self.focus_get()
        transform_entries = (
            self.__transform_x_entry, self.__transform_y_entry,
            self.__transform_angle_entry, self.__transform_scale_entry,
        )
        if focused in transform_entries:
            return
        self._set_transform_entries(tx, ty, rotation, scale)

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
        """Handle Enter key press in any transform entry field.

        Reads the current values from all four entries, validates them,
        and invokes the on_transform_value_change callback.
        Full-width characters are automatically converted to half-width.

        Args:
            event: Key event from the Entry widget.
        """
        try:
            # Main processing: convert full-width to half-width before parsing
            tx = float(self._normalize_fullwidth(self.__transform_x_entry.get()))
            ty = float(self._normalize_fullwidth(self.__transform_y_entry.get()))
            angle = float(self._normalize_fullwidth(self.__transform_angle_entry.get()))
            scale = float(self._normalize_fullwidth(self.__transform_scale_entry.get()))
        except ValueError:
            # Invalid input; restore previous display values
            logger.warning("Transform entry: invalid numeric input ignored")
            return

        # Clamp scale to a reasonable range
        if scale < 0.01:
            scale = 0.01
        elif scale > 10.0:
            scale = 10.0

        # Update display with validated values
        self._set_transform_entries(tx, ty, angle, scale)

        # Invoke callback to apply the new transform
        if self.__on_transform_value_change is not None:
            self.__on_transform_value_change(angle, tx, ty, scale)

        # Move focus away from entry so subsequent updates are not blocked
        self.focus_set()
