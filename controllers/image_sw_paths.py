from __future__ import annotations

import os
import random
from logging import getLogger
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union, Any, Final, TypeAlias

from configurations.user_setting_manager import UserSettingManager
from configurations.message_manager import get_message_manager
from utils.utils import get_resource_path

logger = getLogger(__name__)
message_manager = get_message_manager()

# Define PathType as a proper type alias
PathType: TypeAlias = Union[str, Path]


@dataclass
class SwitchPaths:
    """Class for managing image paths for switch buttons.

    This class provides functionality to:
    1. Get image paths based on environment (development or production)
    2. Handle random image selection for buttons
    3. Support both development and production paths
    """

    on_img_path: Optional[PathType] = None
    off_img_path: Optional[PathType] = None


@dataclass
class SwitchImageFileName:
    on_img_name: str
    off_img_name: str


class ImageSwPaths:
    """Class for managing image paths for switch buttons.

    This class provides functionality to:
    1. Get image paths based on environment (development or production)
    2. Handle random image selection for buttons
    3. Support both development and production paths
    """

    # Define image directory paths as class constants
    IMAGES_DIR: Final[str] = "images"

    def __init__(self) -> None:
        """Initialize ImageSwPaths with default values."""
        self.__toggle_image_on_path: Optional[PathType] = None
        self.__toggle_image_off_path: Optional[PathType] = None
        self.__color_theme: Optional[str] = None
        # Default fallback image path (1x1 transparent pixel)
        self.__fallback_image_path = self._get_fallback_image_path()
        # Error message for image loading failures
        self.__error_message = "ファイルの読み込みに失敗しました。ファイルの拡張子やファイルが破損していないことを確認してください。または、本アプリを再起動してください。"

    def set_automatic_convert_btn_image(self, program_mode: bool) -> SwitchPaths:
        """Set image paths for automatic convert button.

        Args:
            program_mode (bool): Program mode.

        Returns:
            SwitchPaths: Updated instance with set paths
        """
        try:
            # Define image file names
            on_img_name = "shotted_arrow.png"
            off_img_name = "set_arrow.png"

            # Get image paths using utility function
            self.__toggle_image_on_path = self._get_image_path(
                on_img_name, program_mode
            )
            self.__toggle_image_off_path = self._get_image_path(
                off_img_name, program_mode
            )

            # Verify paths exist
            self.__toggle_image_on_path = self._verify_image_path(
                self.__toggle_image_on_path
            )
            self.__toggle_image_off_path = self._verify_image_path(
                self.__toggle_image_off_path
            )
        except Exception as e:
            logger.error(f"Failed to set automatic convert button images: {e}")
            self.__toggle_image_on_path = self.__fallback_image_path
            self.__toggle_image_off_path = self.__fallback_image_path

        return SwitchPaths(
            on_img_path=self.__toggle_image_on_path,
            off_img_path=self.__toggle_image_off_path,
        )

    def set_color_theme_change_btn_image(
        self, program_mode: bool, theme_color: str
    ) -> SwitchPaths:
        """Set image paths for color theme change button.

        Args:
            program_mode (bool): Program mode.
            theme_color (str): Theme color.

        Returns:
            SwitchPaths: Updated instance with set paths
        """
        try:
            self.__color_theme = theme_color

            # Determine button image names based on theme color
            if self.__color_theme == "pastel":
                on_img_name = "pastel_mode.png"
                off_img_name = "dark_mode.png"
            elif self.__color_theme == "light":
                on_img_name = "light_mode.png"
                off_img_name = "dark_mode.png"
            else:
                on_img_name = "dark_mode.png"
                off_img_name = "light_mode.png"

            # Get image paths using utility function
            self.__toggle_image_on_path = self._get_image_path(
                on_img_name, program_mode
            )
            self.__toggle_image_off_path = self._get_image_path(
                off_img_name, program_mode
            )

            # Verify paths exist
            self.__toggle_image_on_path = self._verify_image_path(
                self.__toggle_image_on_path
            )
            self.__toggle_image_off_path = self._verify_image_path(
                self.__toggle_image_off_path
            )
        except Exception as e:
            logger.error(f"Failed to set color theme change button images: {e}")
            self.__toggle_image_on_path = self.__fallback_image_path
            self.__toggle_image_off_path = self.__fallback_image_path

        return SwitchPaths(
            on_img_path=self.__toggle_image_on_path,
            off_img_path=self.__toggle_image_off_path,
        )

    def set_custom_convert_btn_image(self, program_mode: bool) -> SwitchPaths:
        """Set image paths for custom convert button.

        Args:
            program_mode (bool): Program mode.

        Returns:
            SwitchPaths: Updated instance with set paths
        """
        try:
            settings = UserSettingManager()
            __btn_image_no = (
                random.randrange(1, 50, 1) if settings.get_setting("window_set") else 1
            )

            # Determine button image name based on random number
            if __btn_image_no == 5:
                off_img_name = "apologize_for_the_misfires.png"
            elif __btn_image_no == 10:
                off_img_name = "hide_from_angry_person.png"
            elif __btn_image_no == 15:
                off_img_name = "shield_arrows.png"
            else:
                off_img_name = "hennshinn_pose.png"

            on_img_name = "hennshinn_pose_flash.png"

            # Get image paths using utility function
            self.__toggle_image_on_path = self._get_image_path(
                on_img_name, program_mode
            )
            self.__toggle_image_off_path = self._get_image_path(
                off_img_name, program_mode
            )

            # Verify paths exist
            self.__toggle_image_on_path = self._verify_image_path(
                self.__toggle_image_on_path
            )
            self.__toggle_image_off_path = self._verify_image_path(
                self.__toggle_image_off_path
            )
        except Exception as e:
            logger.error(f"Failed to set custom convert button images: {e}")
            self.__toggle_image_on_path = self.__fallback_image_path
            self.__toggle_image_off_path = self.__fallback_image_path

        return SwitchPaths(
            on_img_path=self.__toggle_image_on_path,
            off_img_path=self.__toggle_image_off_path,
        )

    def set_move_page_btn_image(
        self, img_name: SwitchImageFileName, program_mode: bool
    ) -> SwitchPaths:
        """Set image paths for move page button.

        Args:
            img_name (SwitchImageFileName): Image names.
            program_mode (bool): Program mode flag.

        Returns:
            SwitchPaths: Updated instance with set paths
        """
        try:
            # Get image paths using utility function
            self.__custom_toggle_image_on_path = self._get_image_path(
                img_name.on_img_name, program_mode
            )
            self.__custom_toggle_image_off_path = self._get_image_path(
                img_name.off_img_name, program_mode
            )

            # Verify paths exist
            self.__custom_toggle_image_on_path = self._verify_image_path(
                self.__custom_toggle_image_on_path
            )
            self.__custom_toggle_image_off_path = self._verify_image_path(
                self.__custom_toggle_image_off_path
            )
        except Exception as e:
            logger.error(f"Failed to set move page button images: {e}")
            self.__custom_toggle_image_on_path = self.__fallback_image_path
            self.__custom_toggle_image_off_path = self.__fallback_image_path

        return SwitchPaths(
            on_img_path=self.__custom_toggle_image_on_path,
            off_img_path=self.__custom_toggle_image_off_path,
        )

    def _get_image_path(self, image_name: str, program_mode: bool) -> str:
        """Get image path based on program mode.

        Args:
            image_name (str): Image file name
            program_mode (bool): Program mode flag

        Returns:
            str: Full path to image
        """
        try:
            # Use get_resource_path for consistent path resolution
            if program_mode:
                # For Nuitka-compiled executable
                return get_resource_path(os.path.join(self.IMAGES_DIR, image_name))
            else:
                # For development mode
                return str(
                    Path(os.path.dirname(__file__)).parent
                    / self.IMAGES_DIR
                    / image_name
                )
        except Exception as e:
            logger.error(f"Failed to get image path for {image_name}: {e}")
            return self.__fallback_image_path

    @staticmethod
    def _get_fallback_image_path() -> str:
        """Get fallback image path.

        Returns:
            str: Path to fallback image (1x1 transparent pixel)
        """
        # Create a fallback image path in the images directory
        images_dir = Path(os.path.dirname(__file__)).parent / "images"
        os.makedirs(images_dir, exist_ok=True)
        fallback_path = str(images_dir / "fallback_empty.png")

        return fallback_path

    def _verify_image_path(self, path: Optional[PathType]) -> str:
        """Verify that the image path exists and is valid.

        Args:
            path (Optional[PathType]): Image path to verify

        Returns:
            str: Verified path or fallback path
        """
        if path is None:
            logger.warning("Image path is None, using fallback image")
            return self.__fallback_image_path

        try:
            # Convert to string if it's a Path object
            str_path = str(path)

            # Check if file exists
            if not os.path.exists(str_path):
                logger.warning(
                    f"Image file does not exist at path: {str_path}, using fallback image"
                )
                return self.__fallback_image_path

            return str_path
        except Exception as e:
            logger.error(f"Error verifying image path: {e}")
            return self.__fallback_image_path

    def show_error_balloon(self, widget: Any) -> None:
        """Show error balloon message for image loading failures.

        Args:
            widget (Any): Widget to show balloon message on
        """
        if widget is None:
            logger.debug("Widget is None, skipping error balloon display")
            return

        try:
            from utils.utils import show_balloon_message

            show_balloon_message(widget, self.__error_message)
            logger.debug("Displayed error balloon for image loading failure")
        except Exception as e:
            logger.error(f"Failed to show error balloon: {e}")
