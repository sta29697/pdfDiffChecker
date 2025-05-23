"""
Log throttling utility to prevent excessive logging.

This module provides a utility class to throttle log messages 
that occur frequently, such as window resize events.
Settings are loaded from tool_settings.py for centralized management.
"""

import time
from functools import wraps
from typing import Callable, Dict, Any, TypeVar, cast, Optional

# Import throttle settings from tool_settings
from configurations.tool_settings import LOG_THROTTLE_SETTINGS

# Type variables for better type hinting in decorators
F = TypeVar('F', bound=Callable[..., Any])

# Extract interval values from settings
def get_throttle_settings() -> Dict[str, float]:
    """
    Extract throttle interval settings from tool_settings.
    
    Returns:
        Dictionary mapping throttle keys to interval values in seconds
    """
    settings = {}
    
    try:
        # Extract interval values from config
        for key, data in LOG_THROTTLE_SETTINGS.items():
            if isinstance(data, dict) and 'interval' in data:
                settings[key] = float(data['interval'])
    except Exception as e:
        # Fall back to defaults if extraction fails
        from logging import getLogger
        logger = getLogger(__name__)
        logger.warning(f"Failed to load throttle settings: {e}")
    
    return settings

# Global settings dictionary
THROTTLE_SETTINGS = get_throttle_settings()

class LogThrottle:
    """
    Utility class to throttle log messages based on time intervals.
    
    This helps prevent log flooding from events that happen frequently,
    such as window resize events. Interval settings can be loaded from
    a configuration file for centralized management.
    
    Attributes:
        last_log_time: Dictionary to track last log time for each key
        min_interval: Minimum time interval between logs (in seconds)
    """
    
    def __init__(self, min_interval: float = 0.2, throttle_key: Optional[str] = None):
        """
        Initialize a LogThrottle instance.
        
        Args:
            min_interval: Default minimum time interval between logs in seconds
            throttle_key: Optional key to look up in settings file for interval value
        """
        self.last_log_time: Dict[str, float] = {}
        
        # If throttle_key is provided, try to get interval from settings
        if throttle_key and throttle_key in THROTTLE_SETTINGS:
            self.min_interval = THROTTLE_SETTINGS[throttle_key]
        else:
            self.min_interval = min_interval
    
    def should_log(self, key: str, min_interval: Optional[float] = None, throttle_key: Optional[str] = None) -> bool:
        """
        Check if a log message should be allowed for the given key.
        
        Args:
            key: Unique identifier for the log event type
            min_interval: Optional override for the minimum interval for this specific call
            throttle_key: Optional key to look up in settings file for this specific call
            
        Returns:
            True if enough time has passed to allow logging, False otherwise
        """
        current_time = time.time()
        last_time = self.last_log_time.get(key, 0)
        
        # Priority: 1. Explicit min_interval, 2. throttle_key from settings, 3. default min_interval
        if min_interval is not None:
            interval = min_interval
        elif throttle_key and throttle_key in THROTTLE_SETTINGS:
            interval = THROTTLE_SETTINGS[throttle_key]
        else:
            interval = self.min_interval
        
        # Check if minimum interval has passed
        if current_time - last_time >= interval:
            self.last_log_time[key] = current_time
            return True
        
        return False
    
    def throttle(self, key: str) -> Callable[[F], F]:
        """
        Decorator to throttle a function that generates log messages.
        
        Args:
            key: Unique identifier for the log event type
            
        Returns:
            Decorated function that only executes if throttling allows
        """
        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if self.should_log(key):
                    return func(*args, **kwargs)
                return None
            return cast(F, wrapper)
        return decorator

# Global instances for application-wide use
window_resize_throttle = LogThrottle(min_interval=0.2, throttle_key="window_resize")
theme_throttle = LogThrottle(min_interval=60.0, throttle_key="theme_load")
icon_throttle = LogThrottle(min_interval=300.0, throttle_key="window_icon")
temp_dir_throttle = LogThrottle(min_interval=30.0, throttle_key="temp_dir")
png_load_throttle = LogThrottle(min_interval=10.0, throttle_key="png_load")
transform_throttle = LogThrottle(min_interval=3.0, throttle_key="transform_update")
zoom_throttle = LogThrottle(min_interval=1.0, throttle_key="zoom_factor")
image_position_throttle = LogThrottle(min_interval=5.0, throttle_key="image_position")
