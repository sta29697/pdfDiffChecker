from __future__ import annotations

import os
from logging import getLogger
from pathlib import Path
import tkinter as tk
from typing import Any, Optional, cast

from PIL import Image, ImageColor, ImageTk

from configurations import tool_settings
from configurations.tool_settings import DEFAULT_USER_SET
from controllers.color_theme_manager import ColorThemeManager, ThemeType
from controllers.image_sw_paths import ImageSwPaths, SwitchPaths
from widgets.base_button import BaseButton
from utils.utils import show_balloon_message
from configurations.message_manager import get_message_manager

logger = getLogger(__name__)
# Initialize singleton message manager
message_manager = get_message_manager()


class ColorThemeChangeButton(tk.Frame):
    def __init__(
        self, fr: tk.Frame, color_theme_change_btn_status: bool, text: str = "", **kwargs: Any
    ):
        """
        Initializes the color theme change button.

        Args:
            fr: Parent frame
            color_theme_change_btn_status: Initial button status
            text: Button label text
            **kwargs: Additional keyword arguments for tk.Frame
        """
        self.__fr = fr
        # Store button label text and initialize frame
        self.__button_text = text
        super().__init__(master=self.__fr, **kwargs)
        self.__color_theme_change_btn_status_on = color_theme_change_btn_status
        # Error message for image loading failures
        self.__error_message = "Failed to load the file. Please check the file extension and ensure the file is not corrupted. Alternatively, please restart the application."

        # Initialize image variables
        self._toggle_image_on: Optional[tk.PhotoImage] = None
        self._toggle_image_off: Optional[tk.PhotoImage] = None
        self._toggle_image: Optional[tk.PhotoImage] = None

        # Get the current theme color name from color_theme_manager
        try:
            self.__color_theme_manager = ColorThemeManager()
            theme_name = self.__color_theme_manager.get_current_theme_name()
            self.__current_theme_color_name: ThemeType = (
                cast(ThemeType, theme_name) if theme_name else "dark"
            )
        except Exception as e:
            # Failed to load user settings: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            default_theme = DEFAULT_USER_SET["user_settings_default"]["theme_color"]
            self.__current_theme_color_name = cast(ThemeType, default_theme)

        if self.__current_theme_color_name is None:
            self.__current_theme_color_name = "dark"
            # Log error for missing theme name, fallback to dark
            logger.error(message_manager.get_log_message("L132"))

        # Main processing: show the icon for the *current* theme (dark/light/pastel)
        self.__color_theme_change_btn_status_on = True

        # Set the initial button image based on the current theme color
        self.color_theme_change_btn_img: (
            SwitchPaths
        ) = ImageSwPaths().set_color_theme_change_btn_image(
            program_mode=tool_settings.program_mode == "PRODUCTION_MODE",
            theme_color=self.__current_theme_color_name,
        )

        # Load initial button image
        self._load_button_image()

        # Configure fully transparent background - use system default background
        parent_bg = self.__fr.cget("background")
        if parent_bg == "SystemButtonFace" or parent_bg == "":
            # Main processing: prefer theme Window.bg over system default.
            try:
                theme = ColorThemeManager.get_instance().get_current_theme()
                parent_bg = str(theme.get("Window", {}).get("bg", "#f0f0f0"))
            except Exception:
                parent_bg = "#f0f0f0"  # Fallback
        
        self.configure(bg=parent_bg)
        logger.debug(message_manager.get_log_message("L255", parent_bg))
        
        # Place BaseButton inside this frame to isolate geometry management
        self.color_theme_change_btn = BaseButton(
            self,
            "color_theme_change_button",
            text="",  # No text, image only
            command=self._on_click,
            image=self._toggle_image,
            compound=None,  # Show only the image, no text
            bg=parent_bg,  # Match parent's background color
            activebackground=parent_bg,  # Also make active background match parent
            highlightthickness=0,  # Remove highlight border
            bd=0,  # Remove border
            relief=tk.FLAT,  # Make button flat (no 3D effect)
            padx=0,  # Avoid image clipping
            pady=0   # Avoid image clipping
        )
        
        # Pack button with center alignment for vertical centering
        # Use more constrained packing to avoid excessive size
        self.color_theme_change_btn.pack(fill="both", expand=False, pady=0, anchor="center")

        # Log message for successful creation of color theme change button
        logger.info(message_manager.get_log_message("L133"))
        


    def _load_button_image(self) -> None:
        """Load the appropriate button image based on current state."""
        try:
            image_path = self.color_theme_change_btn_img.on_img_path
            subsample_factor = 76
            
            logger.debug(message_manager.get_log_message("L253", str(image_path)))

            if image_path:
                try:
                    # Main processing: resize image to match UI height (pixel-accurate)
                    try:
                        parent_height = int(self.__fr.winfo_height())
                    except Exception:
                        parent_height = 0

                    target_height = 40
                    if parent_height > 0:
                        target_height = max(32, min(48, parent_height - 6))

                    pil_img = Image.open(image_path)
                    if pil_img.mode != "RGBA":
                        pil_img = pil_img.convert("RGBA")

                    # Main processing: avoid black artifacts by compositing alpha onto parent background.
                    try:
                        raw_bg = str(self.__fr.cget("background"))
                        if raw_bg in {"SystemButtonFace", ""}:
                            try:
                                theme = ColorThemeManager.get_instance().get_current_theme()
                                raw_bg = str(theme.get("Window", {}).get("bg", "#f0f0f0"))
                            except Exception:
                                raw_bg = "#f0f0f0"
                        bg_color = ImageColor.getrgb(raw_bg)
                    except Exception:
                        bg_color = (240, 240, 240)
                    bg = Image.new("RGBA", pil_img.size, (*bg_color[:3], 255))
                    try:
                        bg.alpha_composite(pil_img)
                        pil_img = bg
                    except Exception:
                        pil_img = bg
                    if pil_img.height > 0:
                        scale = target_height / float(pil_img.height)
                        target_width = max(1, int(pil_img.width * scale))
                        pil_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    img = ImageTk.PhotoImage(pil_img)
                    
                    logger.debug(message_manager.get_log_message("L254", 
                        f"Resized: {img.width()}x{img.height()}"))
                    
                    if self.__color_theme_change_btn_status_on:
                        self._toggle_image_on = img
                        self._toggle_image = self._toggle_image_on
                    else:
                        self._toggle_image_off = img
                        self._toggle_image = self._toggle_image_off
                        
                    # Update button image if button exists
                    if hasattr(self, 'color_theme_change_btn'):
                        self.color_theme_change_btn.configure(image=self._toggle_image)
                        
                        # Main processing: keep the pre-calculated button size
                        # (do not override width/height based on image pixels)
                        
                except Exception as e:
                    # Failed to load image: {error}
                    logger.error(message_manager.get_log_message("L067", str(e)))
                    self._load_fallback_image(subsample_factor)
            else:
                # Image path is None
                logger.error(message_manager.get_log_message("L133"))
                self._load_fallback_image(subsample_factor)
        except Exception as e:
            # Error in _load_button_image: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            self._create_empty_image()

        # Refresh once after geometry is ready so initial size is correct
        try:
            if not hasattr(self, "_image_refreshed"):
                self._image_refreshed = True
                self.after_idle(self._load_button_image)
        except Exception:
            return

    def _load_fallback_image(self, subsample_factor: int) -> None:
        """
        Load fallback image when primary image loading fails.

        Args:
            subsample_factor: Factor to subsample the image by
        """
        self._show_error_balloon()
        fallback_path = self._get_fallback_image_path()
        try:
            img = tk.PhotoImage(file=fallback_path).subsample(
                subsample_factor, subsample_factor
            )
            if self.__color_theme_change_btn_status_on:
                self._toggle_image_on = img
                self._toggle_image = self._toggle_image_on
            else:
                self._toggle_image_off = img
                self._toggle_image = self._toggle_image_off
        except Exception as e:
            # Failed to load fallback image: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))
            self._create_empty_image()

    def _create_empty_image(self) -> None:
        """Create an empty 1x1 image as last resort."""
        empty_image = tk.PhotoImage(width=1, height=1)
        if self.__color_theme_change_btn_status_on:
            self._toggle_image_on = empty_image
            self._toggle_image = self._toggle_image_on
        else:
            self._toggle_image_off = empty_image
            self._toggle_image = self._toggle_image_off

    def _on_click(self) -> None:
        """Handle the button click event to change the color theme."""
        try:
            self.__color_theme_manager.change_color_theme()
            theme_name = self.__color_theme_manager.get_current_theme_name()
            new_theme: ThemeType = cast(ThemeType, theme_name) if theme_name else "dark"
            if new_theme is None:
                new_theme = "dark"
                # Log message for new theme None fallback to dark
                logger.error(message_manager.get_log_message("L120"))

            self._update_button_theme(new_theme)
            # Color theme changed to: {theme}
            logger.info(message_manager.get_log_message("L121", new_theme))
        except Exception as e:
            # Error changing color theme: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _update_button_theme(self, theme_color: ThemeType) -> None:
        """
        Update the button theme when the color theme changes.

        Args:
            theme_color: New theme color
        """
        try:
            self.__current_theme_color_name = theme_color
            self.__color_theme_change_btn_status_on = True
            self.color_theme_change_btn_img = (
                ImageSwPaths().set_color_theme_change_btn_image(
                    program_mode=tool_settings.program_mode == "PRODUCTION_MODE",
                    theme_color=theme_color,
                )
            )
            
            # Get parent background color for consistent styling
            parent_bg = self.__fr.cget("background")
            if parent_bg == "SystemButtonFace" or parent_bg == "":
                try:
                    theme = ColorThemeManager.get_instance().get_current_theme()
                    parent_bg = str(theme.get("Window", {}).get("bg", parent_bg))
                except Exception:
                    pass
            logger.debug(message_manager.get_log_message("L256", parent_bg))
            
            # Update button background to match parent frame
            if hasattr(self, 'color_theme_change_btn'):
                self.color_theme_change_btn.configure(
                    bg=parent_bg,
                    activebackground=parent_bg
                )
            
            # Load new button image (this will also update the button size)
            self._load_button_image()
            
            # Ensure image is not None before configuring
            if self._toggle_image is not None:
                self.color_theme_change_btn.configure(image=self._toggle_image)
            else:
                # Log message for failed button image update
                logger.error(message_manager.get_log_message("L134"))
            
            # Note: L121 log is already emitted by _on_click(); no duplicate here.
        except Exception as e:
            # Failed to update button theme: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    def _show_error_balloon(self) -> None:
        """Show error balloon message for image loading failures."""
        try:
            # UI balloon for image loading failure
            show_balloon_message(self, message_manager.get_ui_message("U027"))
            # Log message for error balloon displayed
            logger.debug(message_manager.get_log_message("L135"))
        except Exception as e:
            # Failed to show error balloon: {error}
            logger.error(message_manager.get_log_message("L067", str(e)))

    @staticmethod
    def _get_fallback_image_path() -> str:
        """
        Get fallback image path.

        Returns:
            str: Path to fallback image (1x1 transparent pixel)
        """
        images_dir = Path(os.path.dirname(__file__)).parent / "images"
        fallback_path = str(images_dir / "fallback_empty.png")

        if not os.path.exists(fallback_path):
            # Fallback image not found at {path}
            logger.warning(message_manager.get_log_message("L136", fallback_path))
            return str(images_dir / "dark_mode.png")

        return fallback_path
