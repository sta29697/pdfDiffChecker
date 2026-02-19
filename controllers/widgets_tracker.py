from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from collections.abc import Iterator
from logging import getLogger
from typing import List, Protocol, runtime_checkable, Dict, Any, Final

from configurations.message_manager import get_message_manager
from controllers.event_bus import EventBus, EventNames
from controllers.app_state import AppState

# Constants for component names in events
THEME_COMPONENT_NAME: Final[str] = "ColorThemeManager"

message_manager = get_message_manager()

logger = getLogger(__name__)


def adjust_hex_color(hex_color: str, amount: float) -> str:
    """Adjust a hex color by the given amount.

    Positive values lighten the color, negative values darken it.

    Args:
        hex_color (str): Color in '#RRGGBB' format.
        amount (float): Adjustment amount in range [-1.0, 1.0].

    Returns:
        str: Adjusted color in '#RRGGBB' format.
    """
    # Main processing: parse '#RRGGBB' and adjust each RGB channel.
    if not isinstance(hex_color, str):
        return "#000000"

    color = hex_color.strip()
    if not color.startswith("#"):
        return hex_color
    if len(color) != 7:
        return hex_color

    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
    except Exception:
        return hex_color

    amt = max(-1.0, min(1.0, float(amount)))

    def _adjust_channel(v: int) -> int:
        if amt >= 0:
            v2 = v + int((255 - v) * amt)
        else:
            v2 = v + int(v * amt)
        return max(0, min(255, v2))

    r2 = _adjust_channel(r)
    g2 = _adjust_channel(g)
    b2 = _adjust_channel(b)
    return f"#{r2:02x}{g2:02x}{b2:02x}"


def get_hex_color_luminance(hex_color: str) -> float:
    """Get relative luminance of a hex color.

    Args:
        hex_color (str): Color in '#RRGGBB' format.

    Returns:
        float: Luminance in range [0.0, 1.0].
    """
    # Main processing: approximate luminance based on RGB channels.
    if not isinstance(hex_color, str):
        return 0.0

    color = hex_color.strip().lower()
    if not color.startswith("#"):
        return 0.0
    if len(color) != 7:
        return 0.0

    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
    except Exception:
        return 0.0

    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def ensure_contrast_color(color: str, background: str, fallback_amount: float = -0.2) -> str:
    """Ensure the returned color is distinct from the given background.

    Args:
        color (str): Base color candidate.
        background (str): Background color to compare against.
        fallback_amount (float): Adjustment amount applied to background when colors match.

    Returns:
        str: A color string that differs from background when possible.
    """
    # Main processing: if colors match, derive a contrasting shade from the background.
    if not isinstance(color, str) or not isinstance(background, str):
        return color

    c = color.strip().lower()
    bg = background.strip().lower()
    if c == bg and bg.startswith("#") and len(bg) == 7:
        magnitude = abs(float(fallback_amount))
        lum = get_hex_color_luminance(background)
        amount = magnitude if lum < 0.5 else -magnitude
        return adjust_hex_color(background, amount)
    return color


def refresh_combobox_popdown_listboxes(
    root: tk.Misc,
    listbox_bg: str,
    listbox_fg: str,
    listbox_sel_bg: str,
    listbox_sel_fg: str,
) -> None:
    """Refresh ttk.Combobox dropdown Listbox colors for already created popdowns.

    Tk's option database (`option_add`) affects widgets created after the option is set.
    If a combobox dropdown popdown was created earlier (e.g., before a theme switch),
    its internal Listbox may keep the old colors. This helper re-applies the colors
    directly to existing Listbox instances under combobox popdown windows.

    Args:
        root (tk.Misc): Root widget (typically Tk) used as the traversal start point.
        listbox_bg (str): Background color for normal rows.
        listbox_fg (str): Foreground color for normal rows.
        listbox_sel_bg (str): Background color for selected rows.
        listbox_sel_fg (str): Foreground color for selected rows.
    """
    # Main processing: traverse Tcl widget paths and update Listbox under combobox popdown windows.
    try:
        if root is None:
            return

        tkapp = getattr(root, "tk", None)
        if tkapp is None:
            return

        def _iter_descendant_paths(widget_path: str) -> Iterator[str]:
            try:
                children_raw = tkapp.call("winfo", "children", widget_path)
            except Exception:
                children_raw = ()

            try:
                children = tkapp.splitlist(children_raw)
            except Exception:
                children = children_raw if isinstance(children_raw, (list, tuple)) else ()

            for child_path in children:
                child_str = str(child_path)
                yield child_str
                yield from _iter_descendant_paths(child_str)

        for w_path in _iter_descendant_paths("."):
            try:
                w_class = str(tkapp.call("winfo", "class", w_path) or "").lower()
                if w_class != "listbox":
                    continue

                top_path_raw = str(tkapp.call("winfo", "toplevel", w_path) or "")
                top_path_lc = top_path_raw.lower()
                top_class = ""
                try:
                    top_class = str(tkapp.call("winfo", "class", top_path_raw) or "").lower()
                except Exception:
                    top_class = ""
                if "popdown" not in top_path_lc and "popdown" not in top_class:
                    continue

                tkapp.call(
                    w_path,
                    "configure",
                    "-background",
                    listbox_bg,
                    "-foreground",
                    listbox_fg,
                    "-selectbackground",
                    listbox_sel_bg,
                    "-selectforeground",
                    listbox_sel_fg,
                )
            except Exception:
                continue
    except Exception:
        return


@runtime_checkable
class ThemeColorApplicable(Protocol):
    """Protocol for widgets that can apply theme colors.

    This protocol defines the interface for widgets that support theme color application.
    It is used as a marker interface to identify widgets that can be themed.

    Note:
        The theme_colors parameter in apply_theme_color should match the structure
        defined in ThemeColors TypedDict from color_theme_manager.py
    """

    def apply_theme_color(self, theme_colors: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the widget.

        Args:
            theme_colors: Dictionary containing theme colors to apply.
                        The outer dict keys are widget types (e.g., 'Button', 'Frame'),
                        and the inner dict contains color settings as str key-value pairs.
        """
        ...


@runtime_checkable
class WidgetWithChildren(Protocol):
    """Protocol for widgets that have children and can be themed.

    This protocol defines the interface for widgets that have children and support theming.
    Used to ensure proper traversal of the widget hierarchy during theme application.
    """

    def winfo_children(self) -> List[tk.Misc]:
        """Get the children of the widget.

        Returns:
            List of child widgets as tk.Misc.
            tk.Misc is the base class for all tkinter widgets.
        """
        ...

    def winfo_class(self) -> str:
        """Get the class name of the widget.

        Returns:
            Widget class name as a string.
            Used for identifying widget types in theme application.
        """
        ...


class WidgetsTracker:
    """Singleton class for tracking and theming widgets.

    This class manages the registration and theme application for all widgets
    in the application. It maintains a single source of truth for widget references
    and ensures that when the theme changes, all registered widgets are updated.
    
    Subscribes to event bus events to coordinate theme application timing.

    Now uses event-driven architecture to receive theme changes from ColorThemeManager
    without direct dependencies, solving circular dependency issues.

    Note:
        Uses tk.Misc as the base type for all widgets to ensure compatibility
        with both tk and ttk widgets while maintaining type safety.

    Attributes:
        __instance: Singleton instance of WidgetsTracker.
        __registered_widgets: List of registered widgets that support theme colors.
        __theme_initialized: Flag indicating if theme system is initialized.
        __current_theme: Current theme data received from events.
    """

    __instance: WidgetsTracker | None = None
    __registered_widgets: List[ThemeColorApplicable] = []
    __theme_initialized: bool = False
    __current_theme: Dict[str, Any] = {}
    __theme_apply_generation: int = 0
    __widget_origins: Dict[int, Dict[str, Any]] = {}  # Dict to store parent file information for each widget

    def __new__(cls) -> WidgetsTracker:
        """Create a new instance of WidgetsTracker using singleton pattern.

        Returns:
            Single instance of WidgetsTracker.
        """
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
        
    def __del__(self) -> None:
        """Clean up resources when WidgetsTracker is garbage collected.
        
        Unsubscribes from all events to prevent memory leaks and clears all stored widget data.
        """
        try:
            # Unsubscribe from all events
            EventBus().unsubscribe_all(self)
            # Clear widget origins dictionary to prevent memory leaks
            self.__widget_origins.clear()
            # Clear registered widgets list
            self.__registered_widgets.clear()
            # Log that WidgetsTracker has unsubscribed from all events and cleaned up resources
            logger.debug(message_manager.get_log_message("L035"))
        except Exception:
            # Ignore errors during shutdown
            pass
            
    def __init__(self) -> None:
        """Initialize the WidgetsTracker and set up event subscriptions.
        
        Subscribes to theme-related events from the EventBus to receive
        notifications when themes change without direct dependency on ColorThemeManager.
        """
        # Only run initialization once (singleton pattern)
        if not hasattr(self, "_WidgetsTracker__initialized"):
            # Register event listeners
            self.__initialized = True
            
            # Subscribe to theme change events
            EventBus().subscribe(EventNames.THEME_CHANGED, self._handle_theme_changed)
            
            # Subscribe to app initialization events
            EventBus().subscribe(EventNames.PHASE1_COMPLETED, self._handle_phase1_completed)
            EventBus().subscribe(EventNames.WIDGETS_REGISTRATION_COMPLETED, self._handle_widgets_registration_completed)
            EventBus().subscribe(EventNames.THEME_APPLICATION_COMPLETED, self._handle_theme_application_completed)
            EventBus().subscribe(EventNames.TAB_LAYOUT_COMPLETED, self._handle_tab_layout_completed)
            
            # Log initialization with message code
            logger.debug(message_manager.get_log_message("L258", "WidgetsTracker"))
    
    def _handle_theme_changed(self, theme: Dict[str, Any], theme_name: str) -> None:
        """Handle theme changed event.
        
        Args:
            theme: Theme data from event
            theme_name: Name of the theme
        """
        # Store the current theme 
        self.__current_theme = theme 
        self.__theme_initialized = True
        self.__theme_apply_generation += 1
        current_generation = self.__theme_apply_generation

        # Main processing: apply ttk global styles (Notebook/Combobox/etc.) on theme change.
        # Some ttk widgets are not registered in WidgetsTracker, so ttk.Style must be updated globally.
        self._apply_ttk_global_styles(theme, theme_name)
        
        # Apply theme to all registered widgets
        self.apply_colors_to_widgets(theme)
        # Main processing: run one extra pass after idle to stabilize mixed tk/ttk repaint order.
        self._schedule_theme_stabilization_pass(theme, theme_name, current_generation)
        # Use the appropriate message code for theme application to multiple widgets
        logger.debug(message_manager.get_log_message("L231", theme_name, len(self.__registered_widgets)))

    def _schedule_theme_stabilization_pass(
        self,
        theme: Dict[str, Any],
        theme_name: str,
        generation: int,
    ) -> None:
        """Schedule one deferred theme-application pass after idle.

        This helps when a theme toggle updates both tk widgets and ttk styles in the
        same cycle and some widgets repaint later than others.

        Args:
            theme: Theme dictionary to re-apply.
            theme_name: Current theme name used for logging.
            generation: Monotonic theme apply generation to avoid stale re-apply.
        """
        try:
            root = getattr(tk, "_default_root", None)
            if root is None:
                return

            def _apply_once_more() -> None:
                """Re-apply style and widget colors once after idle."""
                try:
                    if generation != self.__theme_apply_generation:
                        return
                    self._apply_ttk_global_styles(theme, theme_name)
                    self.apply_colors_to_widgets(theme)
                except Exception:
                    return

            root.after_idle(_apply_once_more)
        except Exception:
            return

    def _apply_ttk_global_styles(self, theme: Dict[str, Any], theme_name: str) -> None:
        """Apply ttk global styles (ttk.Style) based on the current theme.

        This method updates ttk widget appearances such as Notebook tabs and Combobox
        colors. It is called from the THEME_CHANGED event handler to ensure ttk
        widgets also reflect theme changes even if they are not explicitly tracked.

        Args:
            theme (Dict[str, Any]): Theme dictionary published by ColorThemeManager.
            theme_name (str): Theme name (e.g., "dark", "light", "pastel").
        """
        try:
            logger.debug(f"[THEME] ttk global style apply (WidgetsTracker): theme_name={theme_name}")
        except Exception:
            pass

        # Main processing: configure ttk.Style safely across platforms/themes.
        try:
            style = ttk.Style()
        except Exception:
            return

        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        notebook_theme = theme.get("Notebook", {}) if isinstance(theme, dict) else {}
        notebook_bg = notebook_theme.get("bg", "#2d2d2d")

        frame_theme = theme.get("Frame", {}) if isinstance(theme, dict) else {}
        window_theme = theme.get("Window", {}) if isinstance(theme, dict) else {}
        window_bg = window_theme.get("bg", notebook_bg)
        frame_bg = frame_theme.get("bg", window_bg)

        tab_bg = notebook_theme.get("tab_bg", frame_bg)
        tab_fg = notebook_theme.get("tab_fg", "#ffffff")
        # Main processing: derive tab colors and border contrast for clear selection visibility.
        border_color_base = frame_theme.get("highlightbackground", notebook_bg)
        theme_key = str(theme_name or "").strip().lower()
        border_color = border_color_base

        if theme_key in ("light", "pastel"):
            try:
                base_norm = str(border_color_base).strip().lower()
                frame_bg_norm = str(frame_bg).strip().lower()
                tab_bg_norm = str(tab_bg).strip().lower()
                notebook_bg_norm = str(notebook_bg).strip().lower()
                if base_norm in {frame_bg_norm, tab_bg_norm, notebook_bg_norm}:
                    border_color = adjust_hex_color(str(notebook_bg), -0.12)
            except Exception:
                pass

        # Main processing: compute selected/unselected backgrounds per theme.
        selected_tab_bg = tab_bg
        active_tab_bg = tab_bg
        unselected_tab_bg = notebook_bg

        if theme_key == "dark":
            selected_tab_bg = window_bg
            unselected_tab_bg = adjust_hex_color(str(tab_bg), 0.06)
            active_tab_bg = adjust_hex_color(str(tab_bg), 0.10)
        elif theme_key in ("light", "pastel"):
            unselected_tab_bg = adjust_hex_color(str(notebook_bg), -0.05)

        # Main processing: unify tab edge rendering to avoid thin/bright borders.
        tab_borderwidth = 1
        relief_map = [("selected", "solid"), ("active", "solid"), ("!selected", "flat")]
        try:
            root = getattr(tk, "_default_root", None)
            if root is not None:
                root.configure(bg=window_bg)
        except Exception:
            pass

        try:
            style.configure("TNotebook", background=notebook_bg)
        except Exception:
            pass
        try:
            style.configure(
                "TNotebook",
                bordercolor=border_color,
                lightcolor=border_color,
                darkcolor=border_color,
            )
        except Exception:
            pass
        try:
            style.configure(
                "TNotebook.Tab",
                background=unselected_tab_bg,
                foreground=tab_fg,
                padding=[10, 2],
                borderwidth=tab_borderwidth,
            )
        except Exception:
            pass
        try:
            # Main processing: minimize visual mismatch caused by ttk theme bevel/shading.
            style.configure(
                "TNotebook.Tab",
                bordercolor=border_color,
                lightcolor=border_color,
                darkcolor=border_color,
                focuscolor=border_color,
            )
        except Exception:
            pass
        try:
            style.map(
                "TNotebook.Tab",
                background=[("selected", selected_tab_bg), ("active", active_tab_bg), ("!selected", unselected_tab_bg)],
                foreground=[("selected", tab_fg), ("active", tab_fg), ("!selected", tab_fg)],
                borderwidth=[("selected", tab_borderwidth), ("active", tab_borderwidth), ("!selected", tab_borderwidth)],
                bordercolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                lightcolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                darkcolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
                focuscolor=[("selected", border_color), ("active", border_color), ("!selected", border_color)],
            )
        except Exception:
            pass

        try:
            style.map(
                "TNotebook.Tab",
                relief=relief_map,
            )
        except Exception:
            pass

        label_theme = theme.get("Label", {}) if isinstance(theme, dict) else {}
        button_theme = theme.get("Button", {}) if isinstance(theme, dict) else {}
        entry_theme = theme.get("Entry", {}) if isinstance(theme, dict) else {}
        combobox_theme = theme.get("primary_combobox", {}) if isinstance(theme, dict) else {}
        progress_theme = theme.get("primary_progressbar", {}) if isinstance(theme, dict) else {}

        try:
            style.configure("TFrame", background=frame_bg)
        except Exception:
            pass
        try:
            style.configure(
                "TLabel",
                background=label_theme.get("bg", frame_bg),
                foreground=label_theme.get("fg", tab_fg),
            )
        except Exception:
            pass
        try:
            style.configure(
                "TButton",
                background=button_theme.get("bg", frame_bg),
                foreground=button_theme.get("fg", tab_fg),
            )
        except Exception:
            pass
        try:
            style.configure(
                "TEntry",
                fieldbackground=entry_theme.get("bg", frame_theme.get("bg", notebook_bg)),
                foreground=entry_theme.get("fg", tab_fg),
            )
        except Exception:
            pass

        combo_bg = combobox_theme.get("bg", entry_theme.get("bg", "#ffffff"))
        combo_fg = combobox_theme.get("fg", entry_theme.get("fg", "#000000"))
        combo_border_base = combobox_theme.get(
            "bordercolor",
            frame_theme.get("highlightbackground", combo_bg),
        )
        combo_border = ensure_contrast_color(combo_border_base, combo_bg, 0.25)
        combo_light = adjust_hex_color(combo_border, 0.25)
        combo_dark = adjust_hex_color(combo_border, -0.25)
        combo_focus = combobox_theme.get("highlightcolor", combo_border)
        combo_arrow_bg = ensure_contrast_color(combobox_theme.get("arrowbackground", combo_bg), combo_bg, 0.06)

        try:
            style.configure(
                "TCombobox",
                fieldbackground=combo_bg,
                background=combo_arrow_bg,
                foreground=combo_fg,
                selectbackground=combobox_theme.get("selectbackground", combo_bg),
                selectforeground=combobox_theme.get("selectforeground", combo_fg),
                arrowcolor=combo_fg,
                bordercolor=combo_border,
                lightcolor=combo_light,
                darkcolor=combo_dark,
                focuscolor=combo_focus,
            )
        except Exception:
            pass
        try:
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", combo_bg), ("disabled", combo_bg)],
                background=[("readonly", combo_arrow_bg), ("disabled", combo_arrow_bg), ("active", combo_arrow_bg)],
                foreground=[("readonly", combo_fg), ("disabled", combo_fg), ("active", combo_fg)],
                selectbackground=[("readonly", combobox_theme.get("selectbackground", combo_bg))],
                selectforeground=[("readonly", combobox_theme.get("selectforeground", combo_fg))],
                arrowcolor=[("readonly", combo_fg), ("active", combo_fg), ("disabled", combo_fg)],
                bordercolor=[("readonly", combo_border), ("active", combo_border), ("disabled", combo_border)],
                focuscolor=[("readonly", combo_focus), ("active", combo_focus)],
            )
        except Exception:
            pass

        # Main processing: style combobox dropdown list (Listbox) via option database.
        try:
            root = getattr(tk, "_default_root", None)
            if root is not None:
                listbox_bg = combobox_theme.get("list_bg", combo_bg)
                listbox_fg = combobox_theme.get("list_fg", combo_fg)
                listbox_sel_bg = combobox_theme.get(
                    "list_selectbackground",
                    combobox_theme.get("selectbackground", combo_bg),
                )
                listbox_sel_fg = combobox_theme.get(
                    "list_selectforeground",
                    combobox_theme.get("selectforeground", combo_fg),
                )

                listbox_sel_bg = ensure_contrast_color(str(listbox_sel_bg), str(listbox_bg), 0.08)

                root.option_add("*TCombobox*Listbox.background", listbox_bg)
                root.option_add("*TCombobox*Listbox.foreground", listbox_fg)
                root.option_add("*TCombobox*Listbox.selectBackground", listbox_sel_bg)
                root.option_add("*TCombobox*Listbox.selectForeground", listbox_sel_fg)

                refresh_combobox_popdown_listboxes(
                    root,
                    str(listbox_bg),
                    str(listbox_fg),
                    str(listbox_sel_bg),
                    str(listbox_sel_fg),
                )
        except Exception:
            pass

        btn_bg = button_theme.get("bg", frame_bg)
        btn_border_base = frame_theme.get("highlightbackground", btn_bg)
        btn_border = ensure_contrast_color(btn_border_base, btn_bg, 0.25)
        btn_light = adjust_hex_color(btn_border, 0.25)
        btn_dark = adjust_hex_color(btn_border, -0.25)
        try:
            style.configure(
                "TButton",
                bordercolor=btn_border,
                lightcolor=btn_light,
                darkcolor=btn_dark,
                focuscolor=btn_border,
            )
        except Exception:
            pass

        try:
            style.configure(
                "Primary.Horizontal.TProgressbar",
                background=progress_theme.get("bg", "#000000"),
                troughcolor=progress_theme.get("troughcolor", window_bg),
                bordercolor=progress_theme.get("bordercolor", progress_theme.get("bg", "#000000")),
                lightcolor=progress_theme.get("bg", "#000000"),
                darkcolor=progress_theme.get("bg", "#000000"),
            )
        except Exception:
            pass
    
    def _handle_phase1_completed(self) -> None:
        """Handle phase 1 completion event.
        
        This is called when main initialization phase 1 is completed,
        before widgets are registered and themed.
        """
        # Log phase 1 completion received
        logger.debug(message_manager.get_log_message("L259", "Phase 1"))
    
    def _handle_widgets_registration_completed(self) -> None:
        """Handle widgets registration completion event.
        
        This is called when all widgets have been registered to the tracker,
        and before themes are applied.
        """
        # Log widget registration completion received
        logger.debug(message_manager.get_log_message("L259", "Widgets Registration"))
        
    def _handle_theme_application_completed(self) -> None:
        """Handle theme application completion event.
        
        This is called when theme application has been completed for all widgets.
        """
        # Log theme application completion received
        logger.debug(message_manager.get_log_message("L259", "Theme Application"))
        
    def _handle_tab_layout_completed(self) -> None:
        """Handle tab layout completion event.
        
        This is called when all tabs have been laid out and are ready to use.
        Enables detailed widget initialization logging after this point.
        """
        # Log tab layout completion received
        logger.debug(message_manager.get_log_message("L259", "Tab Layout"))
        
        # Enable widget initialization logs after tabs are laid out
        # This will allow detailed logging for widgets created after this point
        # while suppressing noise during initial application startup
        AppState.enable_widget_init_logs = True
        
        # Count uninitialized theme widgets and log a summary instead of individual messages
        uninitialized_widgets = []
        for widget in self.__registered_widgets:
            if hasattr(widget, "_theme_not_initialized") and getattr(widget, "_theme_not_initialized", False):
                # Get widget module.class information
                widget_info = f"{widget.__class__.__name__}"
                if hasattr(widget, "__module__"):
                    widget_info = f"{widget.__module__}.{widget_info}"
                
                # Get detailed origin information from the tracker
                widget_id = id(widget)
                origin_details = self.__widget_origins.get(widget_id, {})
                
                if origin_details:
                    # Use detailed origin information if available
                    file_name = origin_details.get("creator_file", "unknown")
                    func_name = origin_details.get("func_name", "")
                    line_num = origin_details.get("line_num", 0)
                    
                    # Build a more informative widget description
                    if file_name != "unknown":
                        # Include function name and line number for more precise identification
                        creator_info = f"{file_name}:{func_name}:{line_num}"
                        uninitialized_widgets.append(f"{widget_info} ({creator_info})")
                    else:
                        uninitialized_widgets.append(widget_info)
                else:
                    # Fall back to simple creator file if detailed info is not available
                    if hasattr(widget, "_creator_file"):
                        file_name = getattr(widget, "_creator_file")
                        if file_name != "unknown":
                            creator_info = f"{file_name}"
                            uninitialized_widgets.append(f"{widget_info} ({creator_info})")
                        else:
                            uninitialized_widgets.append(widget_info)
                    else:
                        uninitialized_widgets.append(widget_info)
        
        # Log a summary count of uninitialized widgets
        if uninitialized_widgets:
            count = len(uninitialized_widgets)
            # Log only the count as debug info
            logger.debug(message_manager.get_log_message("L228", count))
            
            # Log detailed list at trace level (will not appear in normal debug logs)
            if count < 10:  # Only show detailed list for small numbers
                for widget_info in uninitialized_widgets:
                    logger.debug(message_manager.get_log_message("L264", f"{widget_info}"))
            # Otherwise just show the count
    
    def _handle_app_initializing(self, component: str) -> None:
        """Handle application initializing event.
        
        Legacy method - maintained for backwards compatibility.
        Args:
            component: The component that is initializing
        """
        if component == THEME_COMPONENT_NAME:
            # Use a proper message code for theme initialization started
            logger.debug(message_manager.get_log_message("L185"))
            
    def _handle_app_initialized(self, component: str, theme_name: str, fallback: bool = False) -> None:
        """Handle application initialized event.
        
        Args:
            component: The component that finished initializing
            theme_name: Name of the initialized theme
            fallback: Whether this is a fallback theme
        """
        if component == THEME_COMPONENT_NAME:
            self.__theme_initialized = True
            # Use theme initialization message with appropriate theme name
            # Pass theme name as an argument here, it will be formatted by the message template
            theme_info = f"fallback: {theme_name}" if fallback else theme_name
            logger.debug(message_manager.get_log_message("L186", theme_info))
    
    def apply_colors_to_widgets(self, theme: Dict[str, Any]) -> None:
        """Apply colors to all registered widgets.
        
        Args:
            theme: Theme data to apply
        """
        caller_info = "widgets_tracker"
        
        # Count the number of widgets
        widget_count = 0
        
        # Apply theme to all registered widgets with proper caller context
        for widget in self.__registered_widgets:
            try:
                if hasattr(widget, "apply_theme_color"):
                    # Get the original registration information for each widget
                    original_creator = "unknown"
                    
                    # If _creator_file is already set, use that information
                    if hasattr(widget, "_creator_file"):
                        original_creator = getattr(widget, "_creator_file")
                    
                    # Set context information (using the original creator info of each widget instead of caller_info)
                    caller_context = {"file": original_creator, "caller": caller_info}
                    widget_count += 1
                    
                    # Permanently set context information to the widget
                    setattr(widget, "_caller_context", caller_context)
                    
                    # Apply theme
                    widget.apply_theme_color(theme)  # type: ignore[arg-type]
            except Exception as e:
                widget_info = f"{widget.__class__.__name__}"
                if hasattr(widget, "__module__"):
                    widget_info = f"{widget.__module__}.{widget_info}"
                # Log error when applying theme to widget fails
                logger.debug(message_manager.get_log_message("L067", f"{widget_info}", str(e)))
    
    @property
    def registered_widgets(self) -> List[ThemeColorApplicable]:
        """Get the list of registered widgets.

        Returns:
            List of registered widgets that support theme colors.
        """
        return self.__registered_widgets
        
    def remove_widget(self, widget: ThemeColorApplicable) -> None:
        """Remove a widget from the registry when it's destroyed.
        
        This method is called when a widget is destroyed to clean up all tracking information.
        It prevents memory leaks by removing all references to the widget from the tracker.
        
        Args:
            widget: Widget to remove from tracking.
        """
        if widget in self.__registered_widgets:
            # Remove from registered widgets list
            self.__registered_widgets.remove(widget)
            
            # Remove widget origin information
            widget_id = id(widget)
            if widget_id in self.__widget_origins:
                del self.__widget_origins[widget_id]
                
            # Widget removal logging removed - L229 message code was deleted
        
    def add_widgets(self, widget: ThemeColorApplicable) -> None:
        """Add a widget to the registry.
        
        Registers widget for theme color updates. If theme initialization is complete, 
        the current theme will be applied immediately to the widget.
        
        This method now implements improved origin tracking to better identify where
        widgets are actually used/created, especially for shared/common widgets.
        
        Args:
            widget: Widget to register for theme color application.
        """
        if widget:
            # Skip if widget is already registered
            if widget in self.__registered_widgets:
                return
                
            # Add to registry
            self.__registered_widgets.append(widget)
            
            # Get widget info for logging
            widget_info = f"{widget.__class__.__name__}"
            if hasattr(widget, "__module__"):
                widget_info = f"{widget.__module__}.{widget_info}"
                
            # Get calling frame info to include tab information
            import inspect
            import os
            caller_frame = inspect.currentframe()
            caller_info = ""
            creator_file = "unknown"
            widget_id = id(widget)
            origin_info = {}
            
            # Store the full call stack to track widget origins more accurately
            if caller_frame is not None:
                # Collect all candidate files from the stack for better tracking
                candidate_files = []
                frame = caller_frame.f_back
                frame_index = 0
                
                while frame and frame_index < 10:  # Limit to 10 frames to avoid excessive searching
                    file_path = frame.f_code.co_filename
                    file_name = os.path.basename(file_path)
                    line_num = frame.f_lineno
                    func_name = frame.f_code.co_name
                    
                    # Store frame information in the candidate list
                    candidate_files.append({
                        "file_name": file_name,
                        "file_path": file_path,
                        "line_num": line_num,
                        "func_name": func_name,
                        "priority": 0  # Default priority
                    })
                    
                    # Prioritize different file types
                    if "_tab" in file_name or "tab_" in file_name:
                        # Tab files get highest priority
                        candidate_files[-1]["priority"] = 10
                    elif file_name == "main.py" or file_name == "licenses.py":
                        # Special files get high priority
                        candidate_files[-1]["priority"] = 8
                    elif file_name.startswith("view_") or "_view" in file_name or "/views/" in file_path:
                        # View files get medium-high priority
                        candidate_files[-1]["priority"] = 7
                    elif "widget" in file_name and file_name != "widgets_tracker.py":
                        # Widget files get medium priority (but not the tracker itself)
                        candidate_files[-1]["priority"] = 5
                    else:
                        # Other files get lower priority based on depth in the stack
                        # Files deeper in the stack get lower priority
                        candidate_files[-1]["priority"] = 3 - min(frame_index, 3)
                    
                    frame = frame.f_back
                    frame_index += 1
                
                # Sort by priority to find the best candidate
                candidate_files.sort(key=lambda x: x["priority"], reverse=True)
                
                # Use the highest priority file as the creator
                if candidate_files:
                    best_candidate = candidate_files[0]
                    # Explicitly cast to string to satisfy type checking
                    creator_file = str(best_candidate["file_name"])
                    caller_info = f" (called from: {creator_file})"
                    
                    # Store detailed origin information
                    origin_info = {
                        "creator_file": creator_file,
                        "file_path": best_candidate["file_path"],
                        "line_num": best_candidate["line_num"],
                        "func_name": best_candidate["func_name"],
                        "candidates": candidate_files
                    }
            
            # Store the origin information in the tracker's dictionary
            self.__widget_origins[widget_id] = origin_info
                    
            # Save creator file information to the widget
            setattr(widget, "_creator_file", creator_file)
            
            # Add color_key to widget_info if available for better identification
            if hasattr(widget, "_BaseEntry__color_key") and getattr(widget, "_BaseEntry__color_key", None):
                widget_info = f"{widget_info} (color_key={widget._BaseEntry__color_key})"
            elif hasattr(widget, "color_key") and getattr(widget, "color_key", None):
                widget_info = f"{widget_info} (color_key={widget.color_key})"
                
            # Only log registration if enabled by AppState
            from controllers.app_state import AppState
            
            # Check if we should log this widget registration based on its class
            if AppState.should_log_widget_registration(widget.__class__.__name__):
                # Log registration with improved details using the standard widget registration message code
                # Include caller tab information if available
                logger.debug(message_manager.get_log_message("L033", f"{widget_info}{caller_info}"))
            
            # Setup widget destruction listener if it's a tkinter widget
            if isinstance(widget, tk.BaseWidget) and hasattr(widget, "bind"):
                # Register widget destruction callback to remove it from tracker
                # Define a typed callback for the Destroy event
                def destroy_callback(event: tk.Event, target_widget: ThemeColorApplicable = widget) -> None:
                    self.remove_widget(target_widget)
                    
                widget.bind("<Destroy>", destroy_callback)
                
            # Publish widget registration event (for other components that may be interested)
            EventBus().publish(
                EventNames.WIDGET_REGISTERED,
                widget=widget,
                widget_info=widget_info
            )
            
            # If theme system is initialized, apply current theme immediately
            if self.__theme_initialized and self.__current_theme:
                try:
                    if hasattr(widget, "apply_theme_color"):
                        widget.apply_theme_color(self.__current_theme)  # type: ignore[arg-type]
                        # Only log theme application if enabled by AppState
                        from controllers.app_state import AppState
                        if AppState.log_theme_application:
                            # Log successful theme application to widget using theme application message code
                            logger.debug(message_manager.get_log_message("L039", widget_info))
                except Exception as e:
                    # Log error when applying theme to widget
                    error_info = f"{widget_info}: {str(e)}"
                    logger.debug(message_manager.get_log_message("L067", error_info))
            # Set a flag for later logging if theme is not initialized
            elif not self.__theme_initialized and hasattr(widget, "apply_theme_color"):
                # Mark the widget - theme uninitialized will be displayed after tab layout is completed
                setattr(widget, "_theme_not_initialized", True)

    def _is_compatible_widget(self, widget: tk.Misc, child: tk.Misc) -> bool:
        """Check if a child widget is compatible with its parent.

        Uses tk.Misc as the base type to handle all widget types uniformly.
        Performs runtime checks for widget compatibility.

        Args:
            widget: Parent widget (tk.Misc).
            child: Child widget to check (tk.Misc).

        Returns:
            True if child is compatible with parent, False otherwise.
        """
        try:
            # Relaxed type checking as we're using tk.Misc
            return isinstance(child, WidgetWithChildren) and isinstance(
                widget, type(child)
            )
        except Exception as e:
            # L034: Error occurred while checking widget compatibility
            logger.error(
                message_manager.get_log_message("L034", widget, child, e)
            )
            return False

    def _get_widget_children(self, widget: tk.Misc) -> Iterator[tk.Misc]:
        """Get all children of a widget that match its type.

        Traverses the widget hierarchy to find all compatible child widgets.
        Uses tk.Misc as the base type for uniform handling of all widget types.

        Args:
            widget: The widget (tk.Misc) to get children from.

        Returns:
            Iterator of child widgets (also tk.Misc).

        Note:
            Skips widgets that don't implement WidgetWithChildren protocol.
        """
        try:
            if not isinstance(widget, WidgetWithChildren):
                yield from ()  # Return empty iterator explicitly

            for child in widget.winfo_children():
                if self._is_compatible_widget(widget, child):
                    yield child
                    yield from self._get_widget_children(child)
        except Exception as e:
            # L035: Error occurred while getting widget children
            logger.error(message_manager.get_log_message("L035", e))
            yield from ()  # Return empty iterator explicitly

    def remove_widgets(self, widget: tk.Misc) -> None:
        """Remove a widget and its children from tracking.

        Recursively removes all themed child widgets from the registry.
        Uses tk.Misc as the base type for widget parameters.

        Args:
            widget: The root widget to unregister (tk.Misc).
        """
        try:
            for child in self._get_widget_children(widget):
                if isinstance(child, ThemeColorApplicable) and hasattr(
                    child, "apply_theme_color"
                ):
                    self.__registered_widgets.remove(child)
                    # L036: Removed child widget from theme color tracking
                    logger.debug(message_manager.get_log_message("L036", child))
        except Exception as e:
            # L037: Error occurred while removing widgets
            logger.error(message_manager.get_log_message("L037", e))
