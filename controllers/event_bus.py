"""
Event Bus implementation for decoupled communication between components.

This module provides an event-driven architecture that allows components to
communicate without direct dependencies, reducing circular references and
making the application more maintainable and testable.
"""

from __future__ import annotations

import weakref
from logging import getLogger
from typing import Any, Callable, Dict, Optional, Set, Union, TypeVar, Hashable
from weakref import WeakMethod, ReferenceType

from configurations.message_manager import get_message_manager

# Initialize message manager for localized logging
message_manager = get_message_manager()
logger = getLogger(__name__)

# Type definitions for callbacks
T = TypeVar('T')
CallbackFunc = Callable[..., Any]
WeakCallbackRef = Union[WeakMethod[Callable[..., Any]], ReferenceType[Callable[..., Any]]]
CallbackKey = Hashable


class EventBus:
    """
    Singleton EventBus for application-wide event management.
    
    Allows components to communicate via events without direct dependencies.
    Uses weak references to prevent memory leaks when subscribers are destroyed.
    
    Usage:
        # Publishing an event
        EventBus().publish('theme_changed', theme_name='dark')
        
        # Subscribing to an event
        EventBus().subscribe('theme_changed', self.handle_theme_change)
        
        # Unsubscribing from an event
        EventBus().unsubscribe('theme_changed', self.handle_theme_change)
        
        # Unsubscribing from all events for an object
        EventBus().unsubscribe_all(self)
    """
    
    _instance: Optional[EventBus] = None
    
    # Structure: { event_name: { callback_key: weak_ref_to_callback } }
    _subscribers: Dict[str, Dict[CallbackKey, WeakCallbackRef]] = {}
    
    # Structure: { id(object): set(event_names) }
    _object_subscriptions: Dict[int, Set[str]] = {}
    
    def __new__(cls) -> EventBus:
        """Create a new instance or return the existing singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logger.debug(message_manager.get_log_message("L033", "EventBus"))
        return cls._instance
    
    def subscribe(self, event_name: str, callback: CallbackFunc) -> None:
        """
        Subscribe to an event with a callback function.
        
        Args:
            event_name: Name of the event to subscribe to
            callback: Function to call when the event is published
        """
        # Initialize event subscribers dict if needed
        if event_name not in self._subscribers:
            self._subscribers[event_name] = {}
        
        # Create a deterministic key so subscriptions are not overwritten by
        # temporary bound-method object id reuse.
        callback_key = self._make_callback_key(callback)
        
        # Store the method differently based on whether it's a bound method or a function
        if hasattr(callback, '__self__'):
            # It's a bound method - explicitly use WeakMethod for bound methods
            # The typing system needs help to understand this - we know it's actually a Callable
            bound_method = callback  # help mypy understand this is a bound method
            weak_ref: WeakCallbackRef = WeakMethod(bound_method)  # type: ignore
            
            # Track the object that owns this method
            obj_id = id(callback.__self__)  # type: ignore
            if obj_id not in self._object_subscriptions:
                self._object_subscriptions[obj_id] = set()
            self._object_subscriptions[obj_id].add(event_name)
        else:
            # It's a regular function - use weakref.ref
            func = callback  # help mypy understand this is a regular function
            weak_ref = weakref.ref(func)  # type: ignore
        
        # Store the weak reference
        self._subscribers[event_name][callback_key] = weak_ref
        logger.debug(message_manager.get_log_message("L261", event_name))
    
    def unsubscribe(self, event_name: str, callback: CallbackFunc) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Name of the event to unsubscribe from
            callback: The callback function to remove
        """
        if event_name in self._subscribers:
            callback_key = self._make_callback_key(callback)
            if callback_key in self._subscribers[event_name]:
                del self._subscribers[event_name][callback_key]
                logger.debug(message_manager.get_log_message("L255", event_name))
                
                # Clean up object subscriptions if this was a bound method
                if hasattr(callback, '__self__'):
                    obj_id = id(callback.__self__)  # type: ignore
                    if obj_id in self._object_subscriptions:
                        self._object_subscriptions[obj_id].discard(event_name)
                        if not self._object_subscriptions[obj_id]:
                            del self._object_subscriptions[obj_id]
                
                # Clean up empty event dicts
                if not self._subscribers[event_name]:
                    del self._subscribers[event_name]
    
    def unsubscribe_all(self, obj: Any) -> None:
        """
        Unsubscribe an object from all events it's subscribed to.
        Call this when an object is being destroyed to prevent memory leaks.
        
        Args:
            obj: The object to unsubscribe from all events
        """
        obj_id = id(obj)
        if obj_id in self._object_subscriptions:
            # Get a copy of the event names as we'll be modifying the set during iteration
            event_names = list(self._object_subscriptions[obj_id])
            
            for event_name in event_names:
                # Find and remove all callbacks for this object
                if event_name in self._subscribers:
                    # Find callback IDs to remove
                    to_remove = []
                    for callback_id, weak_ref in self._subscribers[event_name].items():
                        callback = weak_ref()
                        if callback is None:
                            # Reference is dead, remove it
                            to_remove.append(callback_id)
                        elif hasattr(callback, '__self__') and id(callback.__self__) == obj_id:
                            # This is a method of the object, remove it
                            to_remove.append(callback_id)
                    
                    # Remove the callbacks
                    for callback_id in to_remove:
                        del self._subscribers[event_name][callback_id]
                    
                    # Clean up empty event dicts
                    if not self._subscribers[event_name]:
                        del self._subscribers[event_name]
            
            # Clean up object subscriptions
            del self._object_subscriptions[obj_id]
            logger.debug(message_manager.get_log_message("L256", obj.__class__.__name__))
    
    def publish(self, event_name: str, **data: Any) -> None:
        """
        Publish an event with optional data.
        
        Args:
            event_name: Name of the event to publish
            **data: Data to pass to the callbacks
        """
        if event_name not in self._subscribers:
            # No subscribers for this event
            return
        
        # Collect callbacks to remove (those whose weak references are dead)
        to_remove = []
        
        # Call all callbacks
        for callback_key, weak_ref in self._subscribers[event_name].items():
            callback = weak_ref()
            if callback is None:
                # Reference is dead, mark for removal
                to_remove.append(callback_key)
            else:
                try:
                    # Call the callback with the event data
                    callback(**data)
                except Exception as e:
                    logger.error(message_manager.get_log_message("L257", event_name, str(e)))
        
        # Clean up dead references
        for callback_key in to_remove:
            del self._subscribers[event_name][callback_key]
        
        # Clean up empty event dict
        if not self._subscribers[event_name]:
            del self._subscribers[event_name]

    @staticmethod
    def _make_callback_key(callback: CallbackFunc) -> CallbackKey:
        """Build a deterministic key for callback identity.

        Bound-method objects are temporary wrappers, so using ``id(callback)`` can
        collide and overwrite previously registered subscribers. For bound methods
        we key by (instance id, function id); for plain functions we use function id.

        Args:
            callback: Callback function or bound method.

        Returns:
            A hashable key that remains stable across repeated attribute access.
        """
        if hasattr(callback, "__self__") and hasattr(callback, "__func__"):
            owner = getattr(callback, "__self__", None)
            func = getattr(callback, "__func__", None)
            return ("method", id(owner), id(func))
        return ("function", id(callback))


# Define event names as constants to avoid string duplication and typos
class EventNames:
    """Constants for event names used in the application."""
    THEME_CHANGED = "theme_changed"
    WIDGET_REGISTERED = "widget_registered"
    WIDGET_UNREGISTERED = "widget_unregistered"
    APP_INITIALIZING = "app_initializing"
    APP_INITIALIZED = "app_initialized"
    TAB_CHANGED = "tab_changed"
    LANGUAGE_CHANGED = "language_changed"
    
    # Phase-based initialization events
    PHASE1_COMPLETED = "phase1_completed"
    WIDGETS_REGISTRATION_COMPLETED = "widgets_registration_completed"
    THEME_APPLICATION_COMPLETED = "theme_application_completed"
    TAB_LAYOUT_COMPLETED = "tab_layout_completed"
    
    # Window control events
    WINDOW_CLOSE_REQUESTED = "window_close_requested"
    WINDOW_MINIMIZE_REQUESTED = "window_minimize_requested"
    WINDOW_MAXIMIZE_REQUESTED = "window_maximize_requested"
    APP_SHUTDOWN = "app_shutdown"
