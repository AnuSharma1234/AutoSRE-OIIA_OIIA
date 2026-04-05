"""
AutoSRE Enhanced Caching System
Intelligent caching layer with multi-level cache strategy and performance optimization
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union
import hashlib
import logging

from src.oncall_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = 0
    size_bytes: int = 0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.last_accessed == 0:
            self.last_accessed = self.created_at
        if self.size_bytes == 0:
            self.size_bytes = len(str(self.value).encode('utf-8'))


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class CacheStrategy(ABC):
    """Abstract base class for cache eviction strategies."""
    
    @abstractmethod
    async def should_evict(self, entry: CacheEntry, cache_size: int, max_size: int) -> bool:
        """Determine if an entry should be evicted."""
        pass
    
    @abstractmethod
    def get_priority_score(self, entry: CacheEntry) -> float:
        """Get priority score for eviction (lower = more likely to evict)."""
        pass


class LRUStrategy(CacheStrategy):
    """Least Recently Used eviction strategy."""
    
    async def should_evict(self, entry: CacheEntry, cache_size: int, max_size: int) -> bool:
        return cache_size > max_size
    
    def get_priority_score(self, entry: CacheEntry) -> float:
        return entry.last_accessed


class LFUStrategy(CacheStrategy):
    """Least Frequently Used eviction strategy."""
    
    async def should_evict(self, entry: CacheEntry, cache_size: int, max_size: int) -> bool:
        return cache_size > max_size
    
    def get_priority_score(self, entry: CacheEntry) -> float:
        # Combine frequency with recency
        age_factor = time.time() - entry.created_at
        return entry.access_count / (age_factor + 1)


class AdaptiveCacheStrategy(CacheStrategy):
    """Adaptive strategy that considers multiple factors."""
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {
            'frequency': 0.4,
            'recency': 0.3,
            'size': 0.2,
            'creation_time': 0.1
        }
    
    async def should_evict(self, entry: CacheEntry, cache_size: int, max_size: int) -> bool:
        return cache_size > max_size
    
    def get_priority_score(self, entry: CacheEntry) -> float:
        now = time.time()
        
        # Normalize metrics
        frequency_score = min(entry.access_count / 100, 1.0)
        recency_score = 1.0 / (1.0 + (now - entry.last_accessed) / 3600)  # Hours
        size_penalty = min(entry.size_bytes / (1024 * 1024), 1.0)  # MB
        age_penalty = (now - entry.created_at) / (24 * 3600)  # Days
        
        # Calculate weighted score (higher = keep longer)
        score = (
            self.weights['frequency'] * frequency_score +
            self.weights['recency'] * recency_score -
            self.weights['size'] * size_penalty -
            self.weights['creation_time'] * age_penalty
        )
        
        return max(score, 0.0)


class InMemoryCache:
    """High-performance in-memory cache with intelligent eviction."""
    
    def __init__(
        self,
        max_size_mb: int = 512,
        max_entries: int = 10000,
        default_ttl: int = 3600,
        strategy: CacheStrategy = None
    ):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.strategy = strategy or AdaptiveCacheStrategy()
        
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
    
    def _generate_key(self, key: Union[str, Dict[str, Any]]) -> str:
        """Generate a consistent cache key."""
        if isinstance(key, str):
            return key
        elif isinstance(key, dict):
            # Create deterministic key from dict
            sorted_items = sorted(key.items())
            key_str = json.dumps(sorted_items, sort_keys=True, default=str)
            return hashlib.md5(key_str.encode()).hexdigest()
        else:
            return str(key)
    
    async def get(self, key: Union[str, Dict[str, Any]], default: Any = None) -> Any:
        """Get value from cache."""
        cache_key = self._generate_key(key)
        
        async with self._lock:
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                
                # Check expiration
                if entry.expires_at and time.time() > entry.expires_at:
                    del self._cache[cache_key]
                    self._stats.misses += 1
                    self._update_cache_size()
                    return default
                
                # Update access metadata
                entry.access_count += 1
                entry.last_accessed = time.time()
                
                self._stats.hits += 1
                logger.debug(f"Cache hit for key: {cache_key[:50]}...")
                return entry.value
            else:
                self._stats.misses += 1
                logger.debug(f"Cache miss for key: {cache_key[:50]}...")
                return default
    
    async def set(
        self,
        key: Union[str, Dict[str, Any]],
        value: Any,
        ttl: Optional[int] = None,
        tags: List[str] = None
    ) -> bool:
        """Set value in cache."""
        cache_key = self._generate_key(key)
        ttl = ttl or self.default_ttl
        
        async with self._lock:
            # Create cache entry
            now = time.time()
            expires_at = now + ttl if ttl > 0 else None
            
            entry = CacheEntry(
                key=cache_key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                tags=tags or []
            )
            
            # Check if we need to evict entries
            await self._evict_if_needed(entry.size_bytes)
            
            # Store entry
            self._cache[cache_key] = entry
            self._update_cache_size()
            
            logger.debug(f"Cache set for key: {cache_key[:50]}... (TTL: {ttl}s)")
            return True
    
    async def delete(self, key: Union[str, Dict[str, Any]]) -> bool:
        """Delete entry from cache."""
        cache_key = self._generate_key(key)
        
        async with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                self._update_cache_size()
                logger.debug(f"Cache delete for key: {cache_key[:50]}...")
                return True
            return False
    
    async def clear(self, tags: List[str] = None) -> int:
        """Clear cache entries, optionally by tags."""
        async with self._lock:
            if not tags:
                count = len(self._cache)
                self._cache.clear()
                self._update_cache_size()
                logger.info(f"Cleared entire cache ({count} entries)")
                return count
            else:
                # Clear by tags
                keys_to_delete = [
                    key for key, entry in self._cache.items()
                    if any(tag in entry.tags for tag in tags)
                ]
                
                for key in keys_to_delete:
                    del self._cache[key]
                
                self._update_cache_size()
                logger.info(f"Cleared {len(keys_to_delete)} entries with tags: {tags}")
                return len(keys_to_delete)
    
    async def _evict_if_needed(self, new_entry_size: int):
        """Evict entries if cache limits are exceeded."""
        current_size = sum(entry.size_bytes for entry in self._cache.values())
        current_count = len(self._cache)
        
        # Check if eviction is needed
        needs_eviction = (
            current_size + new_entry_size > self.max_size_bytes or
            current_count >= self.max_entries
        )
        
        if not needs_eviction:
            return
        
        # Get entries sorted by priority (lowest first = evict first)
        entries_by_priority = sorted(
            self._cache.items(),
            key=lambda x: self.strategy.get_priority_score(x[1])
        )
        
        evicted_count = 0
        for cache_key, entry in entries_by_priority:
            if (
                current_size + new_entry_size <= self.max_size_bytes and
                current_count < self.max_entries
            ):
                break
            
            del self._cache[cache_key]
            current_size -= entry.size_bytes
            current_count -= 1
            evicted_count += 1
            self._stats.evictions += 1
        
        if evicted_count > 0:
            logger.debug(f"Evicted {evicted_count} cache entries")
    
    def _update_cache_size(self):
        """Update cache statistics."""
        self._stats.entry_count = len(self._cache)
        self._stats.total_size = sum(entry.size_bytes for entry in self._cache.values())
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        async with self._lock:
            self._update_cache_size()
            return {
                'stats': asdict(self._stats),
                'size_mb': self._stats.total_size / (1024 * 1024),
                'utilization_percent': (self._stats.total_size / self.max_size_bytes) * 100,
                'entry_count': self._stats.entry_count,
                'max_entries': self.max_entries,
                'strategy': self.strategy.__class__.__name__
            }
    
    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """Get cache keys matching a pattern."""
        import re
        async with self._lock:
            regex = re.compile(pattern)
            return [key for key in self._cache.keys() if regex.match(key)]


class AutoSRECacheManager:
    """
    Centralized cache manager for AutoSRE with multiple cache layers.
    """
    
    def __init__(self):
        # L1 Cache: Frequently accessed small data (API responses, config)
        self.l1_cache = InMemoryCache(
            max_size_mb=128,
            max_entries=5000,
            default_ttl=300,  # 5 minutes
            strategy=LRUStrategy()
        )
        
        # L2 Cache: Medium-sized data (incident analysis, metrics)
        self.l2_cache = InMemoryCache(
            max_size_mb=256,
            max_entries=2000,
            default_ttl=1800,  # 30 minutes
            strategy=AdaptiveCacheStrategy()
        )
        
        # L3 Cache: Large, long-term data (ML models, aggregated data)
        self.l3_cache = InMemoryCache(
            max_size_mb=512,
            max_entries=500,
            default_ttl=7200,  # 2 hours
            strategy=LFUStrategy()
        )
        
        logger.info("AutoSRE Cache Manager initialized with multi-level caching")
    
    async def get_or_set(
        self,
        key: Union[str, Dict[str, Any]],
        fetch_func,
        cache_level: str = 'l1',
        ttl: Optional[int] = None,
        tags: List[str] = None
    ) -> Any:
        """Get value from cache or fetch and cache it."""
        cache = self._get_cache_by_level(cache_level)
        
        # Try to get from cache
        value = await cache.get(key)
        if value is not None:
            return value
        
        # Fetch and cache
        try:
            if asyncio.iscoroutinefunction(fetch_func):
                value = await fetch_func()
            else:
                value = fetch_func()
            
            await cache.set(key, value, ttl=ttl, tags=tags)
            return value
        except Exception as e:
            logger.error(f"Failed to fetch data for cache key {key}: {e}")
            raise
    
    async def invalidate_by_tags(self, tags: List[str], cache_level: str = None):
        """Invalidate cache entries by tags across specified cache levels."""
        caches_to_clear = []
        
        if cache_level:
            caches_to_clear = [self._get_cache_by_level(cache_level)]
        else:
            caches_to_clear = [self.l1_cache, self.l2_cache, self.l3_cache]
        
        total_cleared = 0
        for cache in caches_to_clear:
            cleared = await cache.clear(tags=tags)
            total_cleared += cleared
        
        logger.info(f"Invalidated {total_cleared} cache entries with tags: {tags}")
        return total_cleared
    
    def _get_cache_by_level(self, level: str) -> InMemoryCache:
        """Get cache instance by level."""
        cache_map = {
            'l1': self.l1_cache,
            'l2': self.l2_cache,
            'l3': self.l3_cache
        }
        
        if level not in cache_map:
            raise ValueError(f"Invalid cache level: {level}")
        
        return cache_map[level]
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Get statistics from all cache levels."""
        l1_stats = await self.l1_cache.get_stats()
        l2_stats = await self.l2_cache.get_stats()
        l3_stats = await self.l3_cache.get_stats()
        
        # Calculate global metrics
        total_hits = (
            l1_stats['stats']['hits'] +
            l2_stats['stats']['hits'] +
            l3_stats['stats']['hits']
        )
        
        total_misses = (
            l1_stats['stats']['misses'] +
            l2_stats['stats']['misses'] +
            l3_stats['stats']['misses']
        )
        
        global_hit_rate = (total_hits / (total_hits + total_misses) * 100) if (total_hits + total_misses) > 0 else 0
        
        return {
            'global_hit_rate': global_hit_rate,
            'total_size_mb': l1_stats['size_mb'] + l2_stats['size_mb'] + l3_stats['size_mb'],
            'total_entries': l1_stats['entry_count'] + l2_stats['entry_count'] + l3_stats['entry_count'],
            'levels': {
                'l1': l1_stats,
                'l2': l2_stats,
                'l3': l3_stats
            }
        }
    
    async def warm_up_cache(self):
        """Warm up cache with frequently accessed data."""
        logger.info("Starting cache warm-up process...")
        
        # Warm up common configuration
        await self.get_or_set(
            'system_config',
            self._fetch_system_config,
            cache_level='l1',
            ttl=3600,
            tags=['system', 'config']
        )
        
        # Warm up recent incidents summary
        await self.get_or_set(
            'recent_incidents_summary',
            self._fetch_recent_incidents,
            cache_level='l2',
            ttl=1800,
            tags=['incidents', 'summary']
        )
        
        logger.info("Cache warm-up completed")
    
    async def _fetch_system_config(self) -> Dict[str, Any]:
        """Fetch system configuration (placeholder)."""
        return {
            'cache_enabled': True,
            'max_concurrent_incidents': 10,
            'ai_enabled': True,
            'version': '2.0.0'
        }
    
    async def _fetch_recent_incidents(self) -> Dict[str, Any]:
        """Fetch recent incidents summary (placeholder)."""
        return {
            'total_today': 5,
            'resolved_today': 4,
            'avg_resolution_time': 12.5,
            'last_updated': time.time()
        }


# Global cache manager instance
cache_manager = AutoSRECacheManager()


# Utility decorators for easy caching
def cache_result(cache_level: str = 'l1', ttl: Optional[int] = None, tags: List[str] = None):
    """Decorator to cache function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = {
                'function': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            
            return await cache_manager.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                cache_level=cache_level,
                ttl=ttl,
                tags=tags
            )
        return wrapper
    return decorator


def cache_async_result(cache_level: str = 'l1', ttl: Optional[int] = None, tags: List[str] = None):
    """Decorator to cache async function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = {
                'function': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            
            return await cache_manager.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                cache_level=cache_level,
                ttl=ttl,
                tags=tags
            )
        return wrapper
    return decorator