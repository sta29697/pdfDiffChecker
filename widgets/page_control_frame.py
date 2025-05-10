from __future__ import annotations

import tkinter as tk
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
        on_export: Optional[Callable[[], None]] = None,
        on_page_entry: Optional[Callable[[tk.Event], None]] = None,
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
        except Exception as e:
            # Failed to get theme color: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            self.__theme_dict = DEFAULT_COLOR_THEME_SET.get(self.__color_key, {})

        # Base color settings
        self.__swfg: str = self.__theme_dict.get("base_font_color", "#43c0cd")
        self.__swbg: str = self.__theme_dict.get("base_bg_color", "#1d1d29")
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

        # Page navigation buttons
        self.prev_page_btn = BasePageChangeButton(
            fr=self,
            color_key="page_control",
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
            bg=self.__acbg,  # Use active background color for better visibility
            fg=self.__acfg,  # Use active foreground color for better visibility
            highlightcolor=self.__hlfg,
            highlightbackground=self.__hlbg,
            justify='center', # Center the text for better appearance
            relief='flat'     # Flat appearance like a label when not focused
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
            color_key="page_control",
            text="/ 0",
        )
        self.total_pages_label.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        # Next page button
        self.next_page_btn = BasePageChangeButton(
            fr=self,
            color_key="page_control",
            text=">",
            command=on_next_page if on_next_page else lambda: None,
        )
        self.next_page_btn.grid(row=3, column=0, padx=5, pady=5, sticky="ew")

        # Page entry is now integrated with current_page_label above

        # Insert blank page button
        self.insert_blank_btn = InsertBlankPageButton(
            master=self,
            color_key="page_control",
            command=on_insert_blank if on_insert_blank else lambda: None,
        )
        self.insert_blank_btn.grid(row=4, column=0, padx=5, pady=5, sticky="ew")

        # Export button ("完成")
        self.export_btn: tk.Button = tk.Button(
            self,
            text=message_manager.get_ui_message("U037"), # Complete
            font=btw.base_font,
            bg=self.__bg,
            fg=self.__fg,
            activeforeground=self.__acfg,
            activebackground=self.__acbg,
            command=on_export if on_export else lambda: None,
        )
        self.export_btn.grid(row=5, column=0, padx=5, pady=5, sticky="ew")

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
        # Restore flat appearance when not focused
        self.current_page_label.config(relief='flat')
        
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
            # Get frame theme settings
            frame_theme = theme_data.get("Frame", {})
            button_theme = theme_data.get("Button", {})

            # Update color variables
            self.__base_bg = frame_theme.get("bg", self.__base_bg)
            self.__base_fg = frame_theme.get("fg", self.__base_fg)
            self.__bg = button_theme.get("bg", self.__bg)
            self.__fg = button_theme.get("fg", self.__fg)
            self.__acbg = button_theme.get("activebackground", self.__acbg)
            self.__acfg = button_theme.get("activeforeground", self.__acfg)
            self.__base_bg = frame_theme.get("bg", self.__base_bg)
            self.__base_fg = frame_theme.get("fg", self.__base_fg)
            
            # Apply to frame
            self.configure(bg=self.__base_bg)

            # Update Entry widget colors
            self.current_page_label.configure(
                bg=self.__acbg,
                fg=self.__acfg,
                highlightcolor=self.__hlfg,
                highlightbackground=self.__hlbg,
            )

            # Apply theme to component widgets that implement ThemeColorApplicable
            for widget in [
                self.total_pages_label,
                self.prev_page_btn,
                self.next_page_btn,
                self.insert_blank_btn,
                self.current_page_label,
            ]:
                if hasattr(widget, "apply_theme_color"):
                    widget.apply_theme_color(theme_data)

            # Apply theme to export button
            self.export_btn.configure(
                bg=self.__bg,
                fg=self.__fg,
                activeforeground=self.__acfg,
                activebackground=self.__acbg,
            )

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
                relief=theme_settings.get("relief", "flat")
            )
        except Exception as e:
            logger.error(message_manager.get_log_message("L175", str(e)))
            raise
