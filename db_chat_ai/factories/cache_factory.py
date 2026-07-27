"""factories/cache_factory.py — resolves FEATURES["cache"] + CACHE["type"]
into a concrete Cache. Disabled (the default) costs nothing: NoCache
allocates no storage and `redis` is never imported unless CACHE["type"]
== "redis" AND the feature is on."""

from ..interfaces.cache import Cache, MemoryCache, NoCache, RedisCache


class CacheFactory:
    @staticmethod
    def create(config) -> Cache:
        if not config.features.get("cache", False):
            return NoCache()

        cache_type = config.cache_type
        if cache_type == "redis":
            return RedisCache(url=config.cache_redis_url)
        if cache_type == "memory":
            return MemoryCache()
        return NoCache()
