import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


def test_ttl_cache_hits_expires_and_invalidates(monkeypatch):
    import cache_store

    now = {"value": 100.0}
    monkeypatch.setattr(cache_store.time, "monotonic", lambda: now["value"])
    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return {"value": calls["count"]}

    cache = cache_store.TTLCache()
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 1}
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 1}
    now["value"] = 111.0
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 2}
    cache.invalidate("dashboard")
    assert cache.get("dashboard", "admin", ttl=10, loader=loader) == {"value": 3}


def test_ttl_cache_separates_namespaces_and_keys(monkeypatch):
    import cache_store

    monkeypatch.setattr(cache_store.time, "monotonic", lambda: 10.0)
    cache = cache_store.TTLCache()

    assert cache.get("dashboard", "admin", ttl=10, loader=lambda: "admin") == "admin"
    assert cache.get("dashboard", "user:alice", ttl=10, loader=lambda: "alice") == "alice"
    assert cache.get("rates", "public", ttl=10, loader=lambda: "rates") == "rates"

    cache.invalidate("dashboard")
    assert cache.get("dashboard", "admin", ttl=10, loader=lambda: "fresh") == "fresh"
    assert cache.get("rates", "public", ttl=10, loader=lambda: "stale") == "rates"
