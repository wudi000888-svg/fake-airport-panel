import time
from threading import RLock


class TTLCache:
    def __init__(self):
        self._items = {}
        self._lock = RLock()

    def get(self, namespace, key, ttl, loader):
        cache_key = (str(namespace), str(key))
        now = time.monotonic()
        with self._lock:
            item = self._items.get(cache_key)
            if item and item["expires_at"] > now:
                return item["value"]

        value = loader()
        with self._lock:
            self._items[cache_key] = {"value": value, "expires_at": now + float(ttl)}
        return value

    def invalidate(self, namespace=None):
        with self._lock:
            if namespace is None:
                self._items.clear()
                return
            prefix = str(namespace)
            for cache_key in list(self._items):
                if cache_key[0] == prefix:
                    self._items.pop(cache_key, None)

    def stats(self):
        now = time.monotonic()
        with self._lock:
            return {
                "items": len(self._items),
                "namespaces": sorted({key[0] for key in self._items}),
                "active": sum(1 for item in self._items.values() if item["expires_at"] > now),
            }


app_cache = TTLCache()
