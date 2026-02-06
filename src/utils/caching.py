"""
Caching utilities for expensive operations.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Any, Optional, Callable
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of analysis results and API responses.
    """

    def __init__(self, cache_dir: Path = Path('data/cache')):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str, format: str = 'json') -> Path:
        """
        Get path for a cache key.

        Args:
            key: Cache key
            format: File format ('json' or 'pickle')

        Returns:
            Path to cache file
        """
        # Hash the key to create a valid filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        extension = 'pkl' if format == 'pickle' else 'json'
        return self.cache_dir / f"{key_hash}.{extension}"

    def get(
        self,
        key: str,
        max_age: Optional[timedelta] = None,
        format: str = 'json'
    ) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            max_age: Maximum age of cached value (optional)
            format: Format to use ('json' or 'pickle')

        Returns:
            Cached value or None if not found/expired
        """
        cache_path = self._get_cache_path(key, format)

        if not cache_path.exists():
            return None

        # Check age
        if max_age:
            file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if datetime.now() - file_time > max_age:
                return None

        # Load cached value
        try:
            if format == 'pickle':
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            else:
                with open(cache_path, 'r') as f:
                    return json.load(f)
        except (IOError, pickle.PickleError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Any, format: str = 'json') -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            format: Format to use ('json' or 'pickle')
        """
        cache_path = self._get_cache_path(key, format)

        try:
            if format == 'pickle':
                with open(cache_path, 'wb') as f:
                    pickle.dump(value, f)
            else:
                with open(cache_path, 'w') as f:
                    json.dump(value, f, indent=2, default=str)
        except (IOError, pickle.PickleError, TypeError) as exc:
            logger.warning("Cache write failed for key %s: %s", key, exc)

    def clear(self, key: Optional[str] = None) -> None:
        """
        Clear cache.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            for format in ['json', 'pickle']:
                cache_path = self._get_cache_path(key, format)
                if cache_path.exists():
                    cache_path.unlink()
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob('*'):
                if cache_file.is_file():
                    cache_file.unlink()

    def cached(
        self,
        key: str,
        max_age: Optional[timedelta] = None,
        format: str = 'json'
    ) -> Callable:
        """
        Decorator to cache function results.

        Args:
            key: Cache key
            max_age: Maximum age of cached value
            format: Format to use ('json' or 'pickle')

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # Try to get from cache
                cached_value = self.get(key, max_age, format)
                if cached_value is not None:
                    return cached_value

                # Execute function
                result = func(*args, **kwargs)

                # Cache result
                self.set(key, result, format)

                return result

            return wrapper
        return decorator

    def get_cache_info(self) -> dict:
        """
        Get information about cached items.

        Returns:
            Dictionary with cache statistics
        """
        cache_files = list(self.cache_dir.glob('*'))

        total_size = sum(f.stat().st_size for f in cache_files if f.is_file())

        return {
            'cache_dir': str(self.cache_dir),
            'num_files': len(cache_files),
            'total_size_mb': total_size / 1024 / 1024,
            'oldest_file': min((f.stat().st_mtime for f in cache_files), default=None),
            'newest_file': max((f.stat().st_mtime for f in cache_files), default=None)
        }
