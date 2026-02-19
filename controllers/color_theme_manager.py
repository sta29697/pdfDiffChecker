from __future__ import annotations

from typing import Any, Dict, Optional, Literal, cast, TypedDict, Final, Set, Union

import json
import os
import random
import sys
from logging import getLogger

from configurations.tool_settings import DEFAULT_COLOR_THEME_SET
from configurations.user_setting_manager import UserSettingManager as usm
from configurations.message_manager import get_message_manager
from controllers.event_bus import EventBus, EventNames

logger = getLogger(__name__)

# Valid theme names definition
VALID_THEMES: Final[Set[str]] = {"dark", "light", "pastel"}
DEFAULT_THEME: Final[Literal["dark"]] = "dark"


class ThemeColors(TypedDict):
    """Theme colors dictionary type definition."""

    Window: Dict[str, str]
    SubWindow: Dict[str, str]
    Frame: Dict[str, str]
    Canvas: Dict[str, str]
    Label: Dict[str, str]
    Entry: Dict[str, str]
    Button: Dict[str, str]
    Combobox: Dict[str, str]
    Notebook: Dict[str, str]


ThemeType = Literal["dark", "light", "pastel"]


def validate_theme_name(theme_name: str) -> Optional[ThemeType]:
    """Validate if the theme name is valid.

    Args:
        theme_name (str): Theme name to validate

    Returns:
        Optional[ThemeType]: ThemeType if valid, None if invalid
    """
    # Check if the theme name is valid (multilingual code-based key)
    # This line checks if the provided theme name matches any of the valid theme names defined in VALID_THEMES
    return cast(ThemeType, theme_name) if theme_name in VALID_THEMES else None


class ColorThemeManager:
    """Singleton class for managing color themes.

    This class manages color themes for the entire application.
    It provides functionality for loading, saving, and applying themes to widgets.

    Supported themes:
    1. "dark": Default dark theme
    2. "light": Light theme
    3. "pastel": Pastel color theme
    """

    __instance: Optional[ColorThemeManager] = None
    __current_theme: ThemeColors = cast(ThemeColors, {})
    __current_theme_name: ThemeType = DEFAULT_THEME
    __initialization_complete: bool = False

    def __new__(cls) -> ColorThemeManager:
        """Create a new instance of ColorThemeManager using singleton pattern.

        Returns:
            ColorThemeManager: Single instance of ColorThemeManager
        """
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls._load_default_theme()
        return cls.__instance

    @classmethod
    def get_instance(cls) -> ColorThemeManager:
        """Get the singleton instance of ColorThemeManager."""
        return cls()

    @classmethod
    def _load_default_theme(cls) -> None:
        """Load the default color theme."""
        cls.__current_theme = cast(ThemeColors, DEFAULT_COLOR_THEME_SET)
        cls.__current_theme_name = DEFAULT_THEME
        message_manager = get_message_manager()
        # L038: Loaded default color theme
        # Log default theme load event
        logger.debug(message_manager.get_log_message("L038"))

    @classmethod
    def init_color_theme(cls) -> None:
        """Initialize color theme from user settings and notify subscribers via events.
        
        This method now uses event-driven architecture to notify subscribers about
        theme initialization, which helps resolve circular dependencies between
        ColorThemeManager and WidgetsTracker.
        """
        try:
            # Publish event that theme initialization is starting
            # This allows components to prepare for theme changes
            EventBus().publish(EventNames.APP_INITIALIZING, component="ColorThemeManager")
            
            # Get user settings for theme
            settings = usm()
            theme_name = settings.get_setting("theme_color")
            validated_theme = (
                validate_theme_name(theme_name) if isinstance(theme_name, str) else None
            )

            if validated_theme:
                # Load theme and check success
                theme_loaded = cls.load_theme(validated_theme)
                if theme_loaded:
                    # Mark initialization as complete after successful theme loading
                    cls.__initialization_complete = True
                    
                    # Apply theme to all registered widgets via event system
                    cls.apply_color_theme_all_widgets()
                    
                    message_manager = get_message_manager()
                    # L039: Initialized color theme from user settings: {validated_theme}
                    logger.debug(message_manager.get_log_message("L039", validated_theme))
                    
                    # Publish event that initialization is complete
                    EventBus().publish(
                        EventNames.APP_INITIALIZED, 
                        component="ColorThemeManager",
                        theme_name=validated_theme
                    )
                else:
                    # Theme loading failed, load default theme
                    message_manager = get_message_manager()
                    logger.error(message_manager.get_log_message("L047", f"Failed to load theme: {validated_theme}"))
                    cls._load_default_theme()
                    cls.__initialization_complete = True
                    
                    # Publish event for default theme
                    EventBus().publish(
                        EventNames.APP_INITIALIZED, 
                        component="ColorThemeManager",
                        theme_name=DEFAULT_THEME,
                        fallback=True
                    )
            else:
                message_manager = get_message_manager()
                # L040: Invalid color theme name in user settings: {theme_name}
                logger.error(message_manager.get_log_message("L040", theme_name))
                cls._load_default_theme()
                cls.__initialization_complete = True  # Mark initialization as complete even with default theme
        except Exception as e:
            message_manager = get_message_manager()
            # L041: Error occurred during color theme initialization: {error}
            logger.error(message_manager.get_log_message("L041", str(e)))
            cls._load_default_theme()
            cls.__initialization_complete = True  # Mark initialization as complete even with error

    @classmethod
    def load_theme(cls, theme_name: ThemeType, force_reload: bool = False) -> bool:
        """Load color theme with specified theme name.

        Args:
            theme_name (ThemeType): Theme name to load
            force_reload (bool): Force reload theme even if it's the same as current
            
        Returns:
            bool: True if theme was loaded or already loaded, False if loading failed
        """
        try:
            # Skip if theme is already loaded and force_reload is False
            if cls.__current_theme_name == theme_name and cls.__current_theme and not force_reload:
                message_manager = get_message_manager()
                logger.debug(message_manager.get_log_message("L154", f"{theme_name} (already loaded)"))
                return True
                
            # This line creates the correct theme file path based on the theme name
            theme_file = f"themes/{theme_name}.json"
            
            # This line checks if the theme file exists at the specified path
            if os.path.exists(theme_file):
                # Remember previous theme name before loading
                previous_theme = cls.__current_theme_name
                
                with open(theme_file, "r", encoding="utf-8") as f:
                    theme_data = json.load(f)
                    cls.__current_theme = cast(ThemeColors, theme_data)
                    cls.__current_theme_name = theme_name

                message_manager = get_message_manager()
                # Log detailed theme load including file source
                if force_reload:
                    logger.debug(message_manager.get_log_message("L042", f"{theme_name} (file={theme_file}, force_reload=True)"))
                else:
                    logger.debug(message_manager.get_log_message("L042", f"{theme_name} (file={theme_file})"))

                # Update user settings only if theme actually changed
                if previous_theme != theme_name:
                    settings = usm()
                    settings.update_setting(
                        "theme_color", cast(Union[str, int, bool, None], theme_name)
                    )
                    settings.save_settings()
                    message_manager = get_message_manager()
                    logger.debug(message_manager.get_log_message("L240", previous_theme, theme_name))
                return True
            else:
                message_manager = get_message_manager()
                # L043: Theme file not found: {theme_file}
                logger.warning(message_manager.get_log_message("L043", theme_file))
                cls._load_default_theme()
                return False
        except (ValueError, FileNotFoundError, RuntimeError, Exception) as e:
            message_manager = get_message_manager()
            if isinstance(e, ValueError):
                # L044: Invalid theme value: {error}
                logger.error(message_manager.get_log_message("L044", str(e)))
            elif isinstance(e, FileNotFoundError):
                # L045: Theme file not found: {error}
                logger.error(message_manager.get_log_message("L045", str(e)))
            elif isinstance(e, RuntimeError):
                # L046: Runtime error loading theme: {error}
                logger.error(message_manager.get_log_message("L046", str(e)))
            else:
                # L047: Error loading theme: {error}
                logger.error(message_manager.get_log_message("L047", str(e)))
            cls._load_default_theme()
            return False

    @classmethod
    def get_current_theme(cls) -> ThemeColors:
        """Get the current color theme.

        Returns:
            ThemeColors: Current color theme
        """
        return cls.__current_theme

    @classmethod
    def get_current_theme_name(cls) -> ThemeType:
        """Get the current theme name.

        Returns:
            ThemeType: Current theme name
        """
        return cls.__current_theme_name
        
    @classmethod
    def is_initialization_complete(cls) -> bool:
        """Check if the color theme initialization is complete.
        
        Returns:
            bool: True if initialization is complete, False otherwise
        """
        return cls.__initialization_complete

    @classmethod
    def save_theme(cls, theme_name: ThemeType) -> None:
        """Save the current color theme with specified theme name.

        Args:
            theme_name (ThemeType): Theme name to save
        """
        try:
            # Get theme file path based on environment
            if getattr(sys, "frozen", False):
                # Running as compiled (.exe)
                theme_dir = os.path.join(os.path.dirname(sys.executable), "themes")
                theme_file = os.path.join(theme_dir, f"{theme_name}.json")
            else:
                # Running in development environment
                theme_dir = "themes"
                theme_file = f"themes/{theme_name}.json"

            # Create theme directory if it does not exist
            os.makedirs(theme_dir, exist_ok=True)

            with open(theme_file, "w", encoding="utf-8") as f:
                json.dump(cls.__current_theme, f, indent=4, ensure_ascii=False)
            message_manager = get_message_manager()
            # L045: Saved current color theme as {theme_name}
            logger.debug(message_manager.get_log_message("L045", theme_name))
        except Exception as e:
            message_manager = get_message_manager()
            # L046: Error occurred while saving color theme: {error}
            logger.error(message_manager.get_log_message("L046", str(e)))

    @classmethod
    def update_theme_color(cls, key: str, color_dict: Dict[str, Any]) -> None:
        """Update the color theme with specified key.

        Args:
            key (str): Key to update
            color_dict (Dict[str, Any]): New color theme
        """
        try:
            cls.__current_theme[key] = color_dict  # type: ignore
            message_manager = get_message_manager()
            # L047: Updated color theme key {key}
            logger.debug(message_manager.get_log_message("L047", key))
        except Exception as e:
            message_manager = get_message_manager()
            # L048: Error occurred while updating theme color: {error}
            logger.error(message_manager.get_log_message("L048", str(e)))
            raise

    @classmethod
    def apply_color_theme_all_widgets(cls) -> None:
        """Apply the current color theme to all widgets by publishing an event.
        
        Instead of directly iterating through widgets, this method now publishes a
        theme_changed event that WidgetsTracker and other interested components can
        subscribe to. This resolves circular dependencies.
        """
        try:
            # Get current theme data
            current_theme = cls.__current_theme
            current_theme_name = cls.__current_theme_name
            
            # Log the theme application attempt
            message_manager = get_message_manager()
            logger.debug(message_manager.get_log_message("L047", current_theme_name))
            
            # Publish event for theme change - all subscribers will receive this
            EventBus().publish(
                EventNames.THEME_CHANGED,
                theme=current_theme,
                theme_name=current_theme_name
            )
            
            # Log successful event publication
            logger.debug(message_manager.get_log_message("L049", current_theme_name))
        except Exception as e:
            message_manager = get_message_manager()
            # L050: Error occurred while applying color theme to widget: {error}
            logger.error(message_manager.get_log_message("L050", str(e)))

    @classmethod
    def change_color_theme(cls) -> None:
        """Cycle through color themes (dark -> light/pastel -> dark).
        
        Now uses event-driven architecture to notify subscribers when theme changes.
        """
        try:
            current = cls.__current_theme_name
            # Main processing: keep random branch from dark to light/pastel.
            if current == "dark":
                # 50% -> light, 50% -> pastel
                new_theme = cast(
                    ThemeType, "pastel" if random.random() < 0.5 else "light"
                )
            else:
                # from 'light' or 'pastel' to 'dark'
                new_theme = DEFAULT_THEME

            # Load the new theme
            theme_loaded = cls.load_theme(new_theme)
            
            # Apply theme to all widgets via event system
            if theme_loaded:
                cls.apply_color_theme_all_widgets()
        except Exception as e:
            message_manager = get_message_manager()
            # L052: Error occurred while changing color theme: {error}
            logger.error(message_manager.get_log_message("L052", str(e)))
            # If color theme change fails, load the default theme so the app can continue.
            cls._load_default_theme()
            # Notify about default theme via events
            cls.apply_color_theme_all_widgets()
        else:
            message_manager = get_message_manager()
            # L051: Changed color theme from {0} -> {1} (format requires two separate args)
            logger.debug(message_manager.get_log_message("L051", current, new_theme))
