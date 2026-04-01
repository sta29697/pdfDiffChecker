from __future__ import annotations
import tkinter as tk
from typing import Dict, Any, Callable, Optional, cast
from logging import getLogger
from configurations.tool_settings import DEFAULT_COLOR_THEME_SET
from controllers.color_theme_manager import ColorThemeManager
from controllers.widgets_tracker import ThemeColorApplicable, WidgetsTracker, ensure_contrast_color
from themes.coloring_theme_interface import ColoringThemeIF
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)

# Initialize singleton message manager
message_manager = get_message_manager()
ctm = ColorThemeManager()


class BaseImageColorChangeButton(ColoringThemeIF, ThemeColorApplicable):
    """Base class for image color change buttons.

    This class provides base functionality for buttons that:
    1. Change image colors
    2. Support theme color application
    3. Handle image processing events
    """

    def __init__(
        self,
        fr: tk.Frame,
        color_key: str,
        command: Optional[Callable[..., Any]] = None,
        **kwargs: Any
    ) -> None:
        """Initialize the image color change button.

        Args:
            fr (tk.Frame): Parent frame.
            color_key (str): Color key.
            command (Optional[Callable[..., Any]], optional): Command to execute. Defaults to None.
        """
        self.__command = command
        self.__fr: tk.Frame = fr
        self.__color_key: str = color_key
        self.__selected_color: Optional[tuple] = None
        self.__new_selected_color: Optional[str] = None
        self.__theme_dict: Dict[str, str] = {}

        # Acquire theme color from ColorThemeManager
        try:
            current_theme = ctm.get_current_theme()
            self.__theme_dict = cast(
                Dict[str, str],
                current_theme.get(self.__color_key, current_theme.get("Button", {})),
            )
        except Exception as e:
            # Failed to get theme for image color change button
            logger.error(message_manager.get_log_message("L067", str(e)))
            self.__theme_dict = cast(Dict[str, str], DEFAULT_COLOR_THEME_SET.get(self.__color_key, {}))

        self.__fg: str = self.__theme_dict.get("fg", self.__theme_dict.get("button_inactive_font_color", "#0000FF"))
        self.__bg: str = self.__theme_dict.get("bg", self.__theme_dict.get("button_inactive_bg_color", "#0000FF"))
        self.__acfg: str = self.__theme_dict.get("button_active_font_color", "#574ed6")
        self.__acbg: str = self.__theme_dict.get("button_active_bg_color", "#0fd2d6")

        self.image_color_select_btn: tk.Button = tk.Button(
            master=self.__fr,
            text="",
            width=5,
            fg=self.__fg,
            bg=self.__bg,
            font=("Arial", 10),
            activeforeground=self.__acfg,
            activebackground=self.__acbg,
            command=self.__color_select_btn_clicked,
        )

        # Register for theme updates
        WidgetsTracker().add_widgets(self)
        self._apply_keyboard_focus_chrome()

    def _apply_keyboard_focus_chrome(self) -> None:
        """Make keyboard focus visible (Tk highlight ring around the color swatch)."""
        try:
            bg = str(self.image_color_select_btn.cget("bg"))
            ring = str(
                self.__theme_dict.get(
                    "highlightcolor",
                    ensure_contrast_color("#f5d742", bg, 0.35),
                )
            )
            ring = ensure_contrast_color(ring, bg, 0.3)
            self.image_color_select_btn.configure(
                takefocus=1,
                highlightthickness=2,
                highlightbackground=bg,
                highlightcolor=ring,
            )
        except tk.TclError:
            pass

    def __color_select_btn_clicked(self) -> None:
        """Handle color selection button click."""
        import tkinter.colorchooser as colorchooser

        self.__selected_color = colorchooser.askcolor()
        if self.__selected_color and self.__selected_color[1]:
            self.__new_selected_color = str(self.__selected_color[1])
            # Main processing: keep the button swatch and theme cache aligned with the selected color.
            updated_theme_dict = dict(ctm.get_current_theme().get(self.__color_key, DEFAULT_COLOR_THEME_SET.get(self.__color_key, {})))
            updated_theme_dict["bg"] = self.__new_selected_color
            updated_theme_dict["fg"] = self.__new_selected_color
            self._config_widget(updated_theme_dict)
            ctm.update_theme_color(
                self.__color_key,
                updated_theme_dict,
            )
            if self.__command is not None:
                self.__command()

    def grid(self, **kwargs: Any) -> None:
        """Grid the image color select button widget.

        Args:
            **kwargs (Any): Keyword arguments for grid method.
        """
        self.image_color_select_btn.grid(**kwargs)

    def apply_theme_color(self, theme_colors: Dict[str, Dict[str, str]]) -> None:
        """Apply theme colors to the button based on color_key.

        Args:
            theme_colors (Dict[str, Dict[str, str]]): Theme colors to apply.
        """
        try:
            # Determine the correct color key
            if "base" in self.__color_key:
                key = "base_image_color_change_button"
            elif "comp" in self.__color_key:
                key = "comparison_image_color_change_button"
            else:
                key = self.__color_key
            theme_dict = dict(theme_colors.get(key, DEFAULT_COLOR_THEME_SET.get(key, {})))
            if self.__new_selected_color:
                theme_dict["bg"] = self.__new_selected_color
                theme_dict["fg"] = self.__new_selected_color
            self._config_widget(theme_dict)
        except Exception as e:
            # Failed to apply theme color to image color change button
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def _config_widget(self, theme_dict: Dict[str, str]) -> None:
        """Configure the button widget with the given theme dictionary.

        Args:
            theme_dict (Dict[str, str]): Theme color dictionary for the button.
        """
        try:
            self.image_color_select_btn.configure(**theme_dict)
            self._apply_keyboard_focus_chrome()
            # Applied theme color to image display toggle button
            logger.debug(message_manager.get_log_message("L101", self.__color_key))
        except Exception as e:
            # Failed to load theme for image color change button
            logger.error(message_manager.get_log_message("L067", str(e)))
            raise

    def get_base_color(self) -> Optional[str]:
        """Get the base color for the button (for 2-color mode)."""
        if "base" in self.__color_key:
            key = "base_image_color_change_button"
        elif "comp" in self.__color_key:
            key = "comparison_image_color_change_button"
        else:
            key = self.__color_key
        if self.__new_selected_color:
            return self.__new_selected_color
        try:
            current_bg = str(self.image_color_select_btn.cget("bg"))
            if current_bg:
                return current_bg
        except Exception:
            pass
        theme = ctm.get_current_theme().get(key, DEFAULT_COLOR_THEME_SET.get(key, {}))
        return cast(Optional[str], theme.get("bg"))

    def get_selected_color_hex(self) -> Optional[str]:
        """Return the currently selected color as a hex string.

        Returns:
            Optional[str]: Selected color such as ``"#3366ff"``.
        """
        return self.get_base_color()
