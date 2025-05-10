"""
Log throttling utility to prevent excessive logging.

This module provides a utility class to throttle log messages 
that occur frequently, such as window resize events.
"""

import time
from functools import wraps
from typing import Callable, Dict, Any, TypeVar, cast

# Type variables for better type hinting in decorators
F = TypeVar('F', bound=Callable[..., Any])

class LogThrottle:
    """
    Utility class to throttle log messages based on time intervals.
    
    This helps prevent log flooding from events that happen frequently,
    such as window resize events.
    
    Attributes:
        last_log_time: Dictionary to track last log time for each key
        min_interval: Minimum time interval between logs (in seconds)
    """
    
    def __init__(self, min_interval: float = 0.2):
        """
        Initialize a LogThrottle instance.
        
        Args:
            min_interval: Minimum time interval between logs in seconds
        """
        self.last_log_time: Dict[str, float] = {}
        self.min_interval = min_interval
    
    def should_log(self, key: str) -> bool:
        """
        Check if a log message should be allowed for the given key.
        
        Args:
            key: Unique identifier for the log event type
            
        Returns:
            True if enough time has passed to allow logging, False otherwise
        """
        current_time = time.time()
        last_time = self.last_log_time.get(key, 0)
        
        # Check if minimum interval has passed
        if current_time - last_time >= self.min_interval:
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

# Global instance for application-wide use
window_resize_throttle = LogThrottle(min_interval=0.2)
