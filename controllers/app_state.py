"""Application state manager for controlling global behavior.

This module provides a central place to manage application state
that needs to be shared across multiple components.
"""
from __future__ import annotations

class AppState:
    """Static class to manage application state and control behavior.
    
    This class provides flags and state that control the behavior
    of various components, particularly during initialization.
    """
    
    # Application is in initialization phase
    is_initializing: bool = True
    
    # When True, detailed logging is enabled even during initialization
    verbose_logging: bool = False
    
    # When True, widget initialization logs are enabled
    enable_widget_init_logs: bool = False
    
    # Log level control for specific components
    log_widget_registration: bool = False  # Controls widget registration logs
    log_theme_application: bool = False    # Controls theme application logs
    
    # Counter to reduce log frequency
    log_counter: int = 0
    
    # Classes to exclude from logging (common base widgets that generate too much noise)
    excluded_widget_classes: set[str] = {
        "Frame", "Label", "Button", "Entry", "Checkbutton", "Radiobutton", 
        "TFrame", "TLabel", "TButton", "TEntry", "TCheckbutton", "TRadiobutton"
    }
    
    @classmethod
    def set_initialization_complete(cls) -> None:
        """Mark application initialization as complete.
        
        This enables normal logging and other behaviors that should
        only happen after the application is fully initialized.
        """
        cls.is_initializing = False
        
    @classmethod
    def enable_detailed_logging(cls) -> None:
        """Enable detailed logging for debugging purposes."""
        cls.verbose_logging = True
    
    @classmethod
    def enable_widget_registration_logs(cls) -> None:
        """Enable logging of widget registration events."""
        cls.log_widget_registration = True
    
    @classmethod
    def enable_theme_application_logs(cls) -> None:
        """Enable logging of theme application events."""
        cls.log_theme_application = True
        
    @classmethod
    def should_log_widget_init(cls) -> bool:
        """Determine if widget initialization logs should be shown.
        
        Returns:
            bool: True if widget init logs should be shown, False otherwise.
        """
        # Only log occasionally during initialization to reduce noise
        if cls.is_initializing and not cls.verbose_logging:
            # Increment counter and log only every 10th widget during initialization
            cls.log_counter += 1
            return cls.log_counter % 10 == 0 or cls.enable_widget_init_logs
        
        # After initialization or with verbose logging, follow the widget log flag
        return not cls.is_initializing or cls.verbose_logging or cls.enable_widget_init_logs
    
    @classmethod
    def should_log_widget_registration(cls, widget_class_name: str) -> bool:
        """Determine if widget registration should be logged based on widget type.
        
        Args:
            widget_class_name: The name of the widget class being registered
            
        Returns:
            bool: True if this widget registration should be logged
        """
        # Skip logging for common base widgets that generate too much noise
        if widget_class_name in cls.excluded_widget_classes and not cls.verbose_logging:
            return False
            
        # Use the general widget initialization rules
        return cls.should_log_widget_init() and cls.log_widget_registration
