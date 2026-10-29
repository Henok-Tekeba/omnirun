"""A small, dependency-free JSON disk cache.

Design notes:
- Keys are hashed, so auth scopes and repo ids are not exposed in filenames.
- Writes are atomic (temp file + os.replace), so a crashed process does not
  leave a half-written cache entry.
- The cache stores only JSON. Binary ranges are never cached; parsed headers are.
- Corrupt/expired entries are ignored, not fatal.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CACHE_FORMAT_VERSION = 1
DEFAULT_MAX_VALUE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CacheEntry:
    value: Any
    created_at: float
    expires_at: float
    stale: bool = False


class DiskCache:
    def __init__(
        self,
        root: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        max_value_bytes: int = DEFAULT_MAX_VALUE_BYTES,
    ) -> None:
        self.root = Path(root).expanduser()
        self._clock = clock
        self._max_value_bytes = max_value_bytes
        self._lock = threading.RLock()

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / digest[:2] / f"{digest}.json"

    def get(self, key: str, *, allow_stale: bool = False) -> CacheEntry | None:
        path = self._path(key)
        try:
            with self._lock:
                raw = path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            return None

        try:
            payload = json.loads(raw)
            if payload.get("v") != CACHE_FORMAT_VERSION or payload.get("key") != key:
                self._unlink(path)
                return None
            value = payload["value"]
            created_at = float(payload["created_at"])
            expires_at = float(payload["expires_at"])
        except (ValueError, KeyError, TypeError):
            self._unlink(path)
            return None

        now = self._clock()
        stale = now >= expires_at
        if stale and not allow_stale:
            return None
        return CacheEntry(
            value=value,
            created_at=created_at,
            expires_at=expires_at,
            stale=stale,
        )

    def set(self, key: str, value: Any, *, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        payload = {
            "v": CACHE_FORMAT_VERSION,
            "key": key,
            "created_at": self._clock(),
            "expires_at": self._clock() + ttl_seconds,
            "value": value,
        }
        try:
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            return
        if len(raw) > self._max_value_bytes:
            return

        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            with self._lock:
                fd, tmp_name = tempfile.mkstemp(
                    prefix=".tmp-", suffix=".json", dir=path.parent
                )
                try:
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(raw)
                    os.chmod(tmp_name, 0o600)
                    os.replace(tmp_name, path)
                finally:
                    if os.path.exists(tmp_name):
                        os.unlink(tmp_name)
        except OSError:
            # A cache failure must never turn into a request failure.
            return

    def delete(self, key: str) -> None:
        self._unlink(self._path(key))

    def clear(self) -> None:
        with self._lock:
            if not self.root.exists():
                return
            for path in self.root.rglob("*.json"):
                self._unlink(path)

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def default_cache_dir() -> Path:
    """Return the cache directory, honoring OMNIRUN_CACHE_DIR."""
    override = os.environ.get("OMNIRUN_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "omnirun"
