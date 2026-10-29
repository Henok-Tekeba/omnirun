from __future__ import annotations

from pathlib import Path

from core.cache import DiskCache


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_cache_roundtrip_and_expiry(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = DiskCache(tmp_path, clock=clock)
    cache.set("key", {"hello": "world"}, ttl_seconds=10)

    entry = cache.get("key")
    assert entry is not None
    assert entry.value == {"hello": "world"}
    assert entry.stale is False

    clock.advance(9)
    assert cache.get("key") is not None

    clock.advance(2)
    assert cache.get("key") is None

    stale = cache.get("key", allow_stale=True)
    assert stale is not None
    assert stale.stale is True


def test_cache_isolated_by_key(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.set("a", 1, ttl_seconds=10)
    cache.set("b", 2, ttl_seconds=10)
    assert cache.get("a").value == 1  # type: ignore[union-attr]
    assert cache.get("b").value == 2  # type: ignore[union-attr]


def test_cache_corrupt_entry_is_discarded(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = DiskCache(tmp_path, clock=clock)
    cache.set("key", 1, ttl_seconds=10)
    path = cache._path("key")
    path.write_text("{not json", encoding="utf-8")

    assert cache.get("key") is None
    assert not path.exists()


def test_cache_key_not_in_filename(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.set("secret-token-scope", 1, ttl_seconds=10)
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    assert "secret" not in str(files[0])


def test_cache_ignores_wrong_key_payload(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.set("key", 1, ttl_seconds=10)
    path = cache._path("key")
    payload = path.read_text(encoding="utf-8").replace('"key":"key"', '"key":"other"')
    path.write_text(payload, encoding="utf-8")
    assert cache.get("key") is None
