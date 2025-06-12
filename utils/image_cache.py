"""
Image cache module for efficient image handling.

This module provides a caching mechanism for images to improve performance
by reducing the need to reload images from disk.
"""
from __future__ import annotations
import time
from typing import Dict, Any, Optional
from logging import getLogger
from PIL import Image

logger = getLogger(__name__)

class ImageCache:
    """A cache for storing and retrieving images with TTL and size limits.
    
    This class implements a simple cache for PIL Images with time-to-live (TTL)
    and maximum size constraints to prevent memory leaks.
    
    Attributes:
        max_size_mb (int): Maximum cache size in megabytes.
        ttl (int): Time-to-live for cached items in seconds.
        cache (Dict[str, Dict[str, Any]]): Dictionary storing the cached images.
        stats (Dict[str, int]): Statistics about cache usage.
    """
    
    def __init__(self, max_size_mb: int = 100, ttl: int = 300) -> None:
        """Initialize the image cache.
        
        Args:
            max_size_mb (int): Maximum cache size in megabytes. Default is 100.
            ttl (int): Time-to-live for cached items in seconds. Default is 300.
        """
        self.max_size_mb = max_size_mb
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "size_bytes": 0
        }
        logger.debug(f"ImageCache initialized with max_size={max_size_mb}MB, ttl={ttl}s")
    
    def get(self, key: str) -> Optional[Image.Image]:
        """Retrieve an image from the cache.
        
        Args:
            key (str): The cache key for the image.
            
        Returns:
            Optional[Image.Image]: The cached image or None if not found or expired.
        """
        if key in self.cache:
            entry = self.cache[key]
            # Check if the entry has expired
            if time.time() - entry["timestamp"] > self.ttl:
                logger.debug(f"Cache entry expired for {key}")
                self._remove_entry(key)
                self.stats["misses"] += 1
                return None
            
            # Return the cached image
            self.stats["hits"] += 1
            entry["last_accessed"] = time.time()
            logger.debug(f"Cache hit for {key}")
            return entry["image"]
        
        self.stats["misses"] += 1
        logger.debug(f"Cache miss for {key}")
        return None
    
    def put(self, key: str, image: Image.Image) -> None:
        """Store an image in the cache.
        
        Args:
            key (str): The cache key for the image.
            image (Image.Image): The PIL Image to cache.
        """
        # Check if the key already exists in the cache to prevent duplicate entries
        if key in self.cache:
            logger.debug(f"Image already in cache: {key}, skipping")
            return
            
        # Estimate image size in bytes
        width, height = image.size
        channels = len(image.getbands())
        image_size_bytes = width * height * channels
        
        # Check if adding this image would exceed the max cache size
        if (self.stats["size_bytes"] + image_size_bytes) / (1024 * 1024) > self.max_size_mb:
            self._evict_entries()
        
        # Add the image to the cache
        self.cache[key] = {
            "image": image,
            "timestamp": time.time(),
            "last_accessed": time.time(),
            "size_bytes": image_size_bytes
        }
        
        self.stats["size_bytes"] += image_size_bytes
        logger.debug(f"Added image to cache: {key}, size={image_size_bytes/1024:.2f}KB")
    
    def _remove_entry(self, key: str) -> None:
        """Remove an entry from the cache.
        
        Args:
            key (str): The cache key to remove.
        """
        if key in self.cache:
            entry_size = self.cache[key]["size_bytes"]
            self.stats["size_bytes"] -= entry_size
            del self.cache[key]
            logger.debug(f"Removed cache entry: {key}, size={entry_size/1024:.2f}KB")
    
    def _evict_entries(self) -> None:
        """Evict entries from the cache based on least recently used policy.
        
        This method removes the least recently accessed entries from the cache
        until the cache size is below the maximum size limit.
        """
        # Sort entries by last accessed time
        sorted_entries = sorted(
            [(k, v["last_accessed"]) for k, v in self.cache.items()],
            key=lambda x: x[1]
        )
        
        # Remove oldest entries until we're under the size limit
        for key, _ in sorted_entries:
            if self.stats["size_bytes"] / (1024 * 1024) <= self.max_size_mb * 0.8:  # Aim for 80% of max
                break
                
            self._remove_entry(key)
            self.stats["evictions"] += 1
    
    def clear(self) -> None:
        """Clear all entries from the cache.
        
        Removes all entries from the cache and resets the cache statistics.
        """
        self.cache.clear()
        self.stats["size_bytes"] = 0
        logger.debug("Cache cleared")
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dict[str, int]: Dictionary with cache statistics including hits, misses,
                evictions, and current size in bytes.
        """
        return {
            "size_mb": self.stats["size_bytes"] / (1024 * 1024),
            "item_count": len(self.cache),
            "hit_rate": self.stats["hits"] / (self.stats["hits"] + self.stats["misses"]) 
                        if (self.stats["hits"] + self.stats["misses"]) > 0 else 0,
            "evictions": self.stats["evictions"]
        }
    
    def mark_unused(self) -> None:
        """Mark all entries as unused to help with garbage collection."""
        # This doesn't actually remove entries, but helps Python's GC
        # by breaking circular references if they exist
        for key in list(self.cache.keys()):
            if "image" in self.cache[key]:
                self.cache[key]["image"] = None
        logger.debug("Marked all cache entries as unused")
