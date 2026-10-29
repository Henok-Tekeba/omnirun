"""A small async Hugging Face Hub client built for preflight inspection.

Why not use ``HfApi`` directly?
- We need strict byte caps on every response, because a malicious config or
  header must not be able to exhaust memory.
- We need raw HTTP range requests for safetensors/GGUF headers.
- We want async timeouts, bounded concurrency, and a cache we control.

``huggingface_hub`` remains a project dependency for fixture recording and
URL/endpoint conventions, but the hot path is deliberately just httpx.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from core.cache import CacheEntry, DiskCache, default_cache_dir
from core.errors import HFError
from core.parse import parse_model_input

DEFAULT_ENDPOINT = "https://huggingface.co"
USER_AGENT = "OmniRun/0.1 (+https://github.com/omnirun; metadata-only preflight)"
MODEL_INFO_TTL_SECONDS = 10 * 60
IMMUTABLE_TTL_SECONDS = 7 * 24 * 60 * 60
MUTABLE_FILE_TTL_SECONDS = 10 * 60
MAX_MODEL_INFO_BYTES = 32 * 1024 * 1024
MAX_JSON_FILE_BYTES = 32 * 1024 * 1024
MAX_RANGE_BYTES = 64 * 1024 * 1024
MAX_ERROR_BODY_BYTES = 8 * 1024
MAX_FILES = 50_000
MAX_TOKEN_LENGTH = 4096
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$", re.IGNORECASE)
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_AUTH_STATUS = {401, 403}


@dataclass(frozen=True, slots=True)
class RepoFile:
    path: str
    size: int | None = None
    blob_id: str | None = None
    lfs_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "blob_id": self.blob_id,
            "lfs_sha256": self.lfs_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepoFile:
        size = data.get("size")
        return cls(
            path=str(data["path"]),
            size=int(size) if isinstance(size, int) and size >= 0 else None,
            blob_id=str(data["blob_id"]) if data.get("blob_id") else None,
            lfs_sha256=str(data["lfs_sha256"]) if data.get("lfs_sha256") else None,
        )


@dataclass(frozen=True, slots=True)
class HFRepo:
    repo_id: str
    requested_repo_id: str
    sha: str
    private: bool = False
    gated: bool = False
    gated_mode: str | None = None
    pipeline_tag: str | None = None
    library_name: str | None = None
    tags: tuple[str, ...] = ()
    last_modified: datetime | None = None
    files: Mapping[str, RepoFile] = field(default_factory=dict)
    cache_hit: bool = False
    cache_stale: bool = False
    fetched_at: datetime | None = None

    @property
    def revision(self) -> str:
        return self.sha

    def file(self, path: str) -> RepoFile | None:
        return self.files.get(path)

    def filenames(self) -> tuple[str, ...]:
        return tuple(self.files)

    def to_cache_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "requested_repo_id": self.requested_repo_id,
            "sha": self.sha,
            "private": self.private,
            "gated": self.gated,
            "gated_mode": self.gated_mode,
            "pipeline_tag": self.pipeline_tag,
            "library_name": self.library_name,
            "tags": list(self.tags),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "files": {path: f.to_dict() for path, f in self.files.items()},
        }

    @classmethod
    def from_cache_dict(
        cls,
        data: Mapping[str, Any],
        *,
        fetched_at: datetime,
        stale: bool,
    ) -> HFRepo:
        raw_files = data.get("files")
        if not isinstance(raw_files, dict):
            raise ValueError("invalid cached files")
        files = {
            str(path): RepoFile.from_dict(file_data)
            for path, file_data in raw_files.items()
            if isinstance(file_data, dict)
        }
        last_modified_raw = data.get("last_modified")
        last_modified = None
        if isinstance(last_modified_raw, str):
            last_modified = datetime.fromisoformat(last_modified_raw)
        tags = data.get("tags")
        return cls(
            repo_id=str(data["repo_id"]),
            requested_repo_id=str(data["requested_repo_id"]),
            sha=str(data["sha"]),
            private=bool(data.get("private", False)),
            gated=bool(data.get("gated", False)),
            gated_mode=str(data["gated_mode"]) if data.get("gated_mode") else None,
            pipeline_tag=str(data["pipeline_tag"]) if data.get("pipeline_tag") else None,
            library_name=str(data["library_name"]) if data.get("library_name") else None,
            tags=tuple(str(t) for t in tags) if isinstance(tags, list) else (),
            last_modified=last_modified,
            files=files,
            cache_hit=True,
            cache_stale=stale,
            fetched_at=fetched_at,
        )


@dataclass(frozen=True, slots=True)
class JsonFile:
    data: Any
    from_cache: bool
    stale: bool
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    headers: Mapping[str, str]
    content: bytes
    url: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _token_scope(token: str | None) -> str:
    if not token:
        return "anon"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _validate_token(token: str | None) -> str | None:
    if token is None:
        return None
    if not isinstance(token, str):
        raise HFError(
            "invalid_token",
            "hf_token must be a string.",
            status_code=422,
        )
    token = token.strip()
    if not token:
        return None
    if len(token) > MAX_TOKEN_LENGTH or any(ord(ch) < 32 for ch in token):
        raise HFError(
            "invalid_token",
            "hf_token has an invalid format.",
            status_code=422,
            hint="Pass the token value only, without 'Bearer ' or whitespace.",
        )
    return token


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
        if math.isfinite(seconds):
            return max(0.0, seconds)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return max(0.0, (when - _utcnow()).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def _sanitize_upstream_message(content: bytes) -> str | None:
    if not content:
        return None
    text = content[:MAX_ERROR_BODY_BYTES].decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            message = payload.get("error") or payload.get("message")
            if isinstance(message, str):
                return message[:300]
    except ValueError:
        pass
    text = " ".join(text.split())
    return text[:300] if text else None


class HFClient:
    """Bounded, cached, retrying HF Hub client.

    ``max_attempts`` counts the first request. 401/403/404/416 are never
    retried. The client is safe to share inside one event loop.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        cache: DiskCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
        max_attempts: int = 3,
        max_concurrent: int = 4,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
        user_agent: str = USER_AGENT,
    ) -> None:
        endpoint = (endpoint or os.environ.get("HF_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")
        if not endpoint.startswith(("https://", "http://")):
            raise ValueError("HF endpoint must start with https:// or http://")
        self.endpoint = endpoint
        self.cache = cache or DiskCache(default_cache_dir())
        self._endpoint_scope = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:8]
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._max_attempts = max(1, int(max_attempts))
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            headers={
                "User-Agent": user_agent,
                "Accept-Encoding": "identity",
                "X-OmniRun-Version": "0.1",
            },
        )

    async def __aenter__(self) -> HFClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ URLs

    def _api_url(self, repo_id: str) -> str:
        return f"{self.endpoint}/api/models/{_quote_repo(repo_id)}?blobs=true"

    def _file_url(self, repo_id: str, revision: str, path: str) -> str:
        return (
            f"{self.endpoint}/{_quote_repo(repo_id)}/resolve/"
            f"{_quote_segment(revision)}/{_quote_path(path)}"
        )

    def _model_key(self, repo_id: str, scope: str) -> str:
        return f"v1:{self._endpoint_scope}:model:{repo_id.lower()}:{scope}"

    def _file_key(self, repo_id: str, revision: str, path: str, scope: str) -> str:
        return (
            f"v1:{self._endpoint_scope}:json:"
            f"{repo_id.lower()}@{revision}:{path}:{scope}"
        )

    # -------------------------------------------------------------- requests

    async def _request(
        self,
        url: str,
        *,
        token: str | None,
        max_bytes: int,
        range_header: str | None = None,
        accept: str = "application/json, */*",
    ) -> _Response:
        headers: dict[str, str] = {"Accept": accept}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if range_header:
            headers["Range"] = range_header

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            retry_after: float | None = None
            try:
                async with self._semaphore, self._client.stream(
                    "GET", url, headers=headers
                ) as response:
                    status = response.status_code
                    if status == 200 and range_header:
                        # Do not accidentally download a full weights file
                        # when the CDN ignores Range.
                        return _Response(
                            status=200,
                            headers=dict(response.headers),
                            content=b"",
                            url=url,
                        )
                    if status in _RETRYABLE_STATUS:
                        body = await _read_capped(response, MAX_ERROR_BODY_BYTES)
                        retry_after = _parse_retry_after(response.headers.get("retry-after"))
                        if attempt < self._max_attempts:
                            await self._sleep(self._retry_delay(attempt, retry_after))
                            continue
                        raise self._status_error(status, body, retry_after)
                    if 200 <= status < 300:
                        body = await _read_capped(response, max_bytes)
                        return _Response(
                            status=status,
                            headers=dict(response.headers),
                            content=body,
                            url=url,
                        )
                    body = await _read_capped(response, MAX_ERROR_BODY_BYTES)
                    return _Response(
                        status=status,
                        headers=dict(response.headers),
                        content=body,
                        url=url,
                    )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    await self._sleep(self._retry_delay(attempt, None))
                    continue
                raise HFError(
                    "hf_timeout",
                    "The Hugging Face Hub request timed out.",
                    status_code=504,
                    retryable=True,
                    hint=(
                        "Try again, or check whether huggingface.co is reachable "
                        "from the API host."
                    ),
                ) from exc
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    await self._sleep(self._retry_delay(attempt, None))
                    continue
                raise HFError(
                    "hf_unreachable",
                    "Could not reach the Hugging Face Hub.",
                    status_code=502,
                    retryable=True,
                    hint="Check the API host's network connection and DNS.",
                ) from exc
            except httpx.HTTPError as exc:
                raise HFError(
                    "hf_request_failed",
                    "The Hugging Face Hub request failed.",
                    status_code=502,
                    retryable=False,
                ) from exc

        raise HFError(
            "hf_request_failed",
            "The Hugging Face Hub request failed.",
            status_code=502,
            retryable=True,
            details={"last_error": type(last_error).__name__ if last_error else "unknown"},
        )

    def _retry_delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(10.0, max(0.0, retry_after))
        base = min(8.0, 2.0 ** (attempt - 1))
        return base + self._rng.uniform(0.0, 0.25)

    def _status_error(
        self,
        status: int,
        body: bytes,
        retry_after: float | None,
    ) -> HFError:
        if status == 429:
            return HFError(
                "hf_rate_limited",
                "Hugging Face rate-limited OmniRun.",
                status_code=503,
                upstream_status=status,
                retryable=True,
                retry_after=retry_after,
                hint="Wait a moment and retry. Adding an hf_token raises Hub rate limits.",
                details={"upstream_message": _sanitize_upstream_message(body)},
            )
        return HFError(
            "hf_upstream_error",
            f"Hugging Face returned HTTP {status}.",
            status_code=502,
            upstream_status=status,
            retryable=True,
            retry_after=retry_after,
            details={"upstream_message": _sanitize_upstream_message(body)},
        )

    # ----------------------------------------------------------- model info

    async def resolve_repo(self, model: str, *, token: str | None = None) -> HFRepo:
        """Resolve a URL/repo id to a canonical repo and pinned commit SHA."""
        parsed = parse_model_input(model)
        token = _validate_token(token)
        scope = _token_scope(token)
        key = self._model_key(parsed.repo_id, scope)

        cached = self.cache.get(key)
        if cached is not None:
            repo = self._repo_from_cache(cached, stale=False)
            if repo is not None:
                return repo

        try:
            response = await self._request(
                self._api_url(parsed.repo_id),
                token=token,
                max_bytes=MAX_MODEL_INFO_BYTES,
                accept="application/json",
            )
        except HFError as exc:
            if exc.retryable:
                stale = self.cache.get(key, allow_stale=True)
                if stale is not None:
                    repo = self._repo_from_cache(stale, stale=True)
                    if repo is not None:
                        return repo
            raise

        if response.status != 200:
            raise self._repo_http_error(response, parsed.repo_id, has_token=bool(token))

        try:
            payload = json.loads(response.content)
        except ValueError as exc:
            raise HFError(
                "invalid_hf_response",
                "Hugging Face returned a model record that was not valid JSON.",
                status_code=502,
                upstream_status=response.status,
            ) from exc
        if not isinstance(payload, dict):
            raise HFError(
                "invalid_hf_response",
                "Hugging Face returned an unexpected model record.",
                status_code=502,
                upstream_status=response.status,
            )

        repo = _repo_from_payload(payload, parsed.repo_id, fetched_at=_utcnow())
        self.cache.set(key, repo.to_cache_dict(), ttl_seconds=MODEL_INFO_TTL_SECONDS)
        return repo

    def _repo_from_cache(self, entry: CacheEntry, *, stale: bool) -> HFRepo | None:
        if not isinstance(entry.value, dict):
            return None
        try:
            return HFRepo.from_cache_dict(
                entry.value,
                fetched_at=datetime.fromtimestamp(entry.created_at, UTC),
                stale=stale,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _repo_http_error(self, response: _Response, repo_id: str, *, has_token: bool) -> HFError:
        upstream = _sanitize_upstream_message(response.content)
        if response.status in _AUTH_STATUS:
            if has_token:
                return HFError(
                    "repo_access_denied",
                    "Hugging Face rejected the token or this account has no access "
                    "to the repo.",
                    status_code=403,
                    upstream_status=response.status,
                    hint=(
                        "Check that the token is valid. For a gated model, open the model page, "
                        "accept its license, and pass a token from an account with access."
                    ),
                    details={"repo_id": repo_id, "upstream_message": upstream},
                )
            return HFError(
                "repo_auth_required",
                "This model is gated or private (or the repo does not exist).",
                status_code=403,
                upstream_status=response.status,
                hint=(
                    "Open the model page on huggingface.co. If access is gated, accept the "
                    "license and retry with hf_token. Hugging Face uses 401/404 to avoid "
                    "revealing whether private repos exist."
                ),
                details={"repo_id": repo_id, "upstream_message": upstream},
            )
        if response.status == 404:
            return HFError(
                "repo_not_found",
                f"No Hugging Face model repo was found for {repo_id!r}.",
                status_code=404,
                upstream_status=404,
                hint="Check the owner/model spelling, or open the URL in a browser.",
                details={"repo_id": repo_id},
            )
        if response.status == 429:
            return self._status_error(
                429,
                response.content,
                _parse_retry_after(response.headers.get("retry-after")),
            )
        return HFError(
            "hf_upstream_error",
            f"Hugging Face returned HTTP {response.status} while resolving the repo.",
            status_code=502,
            upstream_status=response.status,
            retryable=True,
            details={"repo_id": repo_id, "upstream_message": upstream},
        )

    # --------------------------------------------------------------- files

    async def get_json_file(
        self,
        repo: HFRepo,
        path: str,
        *,
        token: str | None = None,
        revision: str | None = None,
        max_bytes: int = MAX_JSON_FILE_BYTES,
    ) -> JsonFile:
        path = _validate_repo_path(path)
        token = _validate_token(token)
        revision = revision or repo.sha
        scope = _token_scope(token)
        key = self._file_key(repo.repo_id, revision, path, scope)

        cached = self.cache.get(key)
        if cached is not None and isinstance(cached.value, dict) and "data" in cached.value:
            return JsonFile(
                data=cached.value["data"],
                from_cache=True,
                stale=False,
                fetched_at=datetime.fromtimestamp(cached.created_at, UTC),
            )

        file_meta = repo.file(path)
        if file_meta is not None and file_meta.size is not None and file_meta.size > max_bytes:
            raise HFError(
                "file_too_large",
                f"{path} is too large to inspect safely ({file_meta.size} bytes).",
                status_code=502,
                hint="OmniRun refuses to read metadata files above its safety cap.",
                details={"repo_id": repo.repo_id, "path": path, "size": file_meta.size},
            )

        try:
            response = await self._request(
                self._file_url(repo.repo_id, revision, path),
                token=token,
                max_bytes=max_bytes,
                accept="application/json, */*",
            )
        except HFError as exc:
            if exc.retryable:
                stale = self.cache.get(key, allow_stale=True)
                if (
                    stale is not None
                    and isinstance(stale.value, dict)
                    and "data" in stale.value
                ):
                    return JsonFile(
                        data=stale.value["data"],
                        from_cache=True,
                        stale=True,
                        fetched_at=datetime.fromtimestamp(stale.created_at, UTC),
                    )
            raise

        if response.status != 200:
            raise self._file_http_error(response, repo, path, has_token=bool(token))

        try:
            data = json.loads(response.content)
        except ValueError as exc:
            raise HFError(
                "invalid_json",
                f"{path} in {repo.repo_id} is not valid JSON.",
                status_code=502,
                upstream_status=response.status,
                details={"repo_id": repo.repo_id, "path": path},
            ) from exc

        ttl = IMMUTABLE_TTL_SECONDS if _SHA_RE.fullmatch(revision) else MUTABLE_FILE_TTL_SECONDS
        self.cache.set(key, {"data": data}, ttl_seconds=ttl)
        return JsonFile(data=data, from_cache=False, stale=False, fetched_at=_utcnow())

    async def get_range(
        self,
        repo: HFRepo,
        path: str,
        start: int,
        end_inclusive: int,
        *,
        token: str | None = None,
        revision: str | None = None,
        max_bytes: int = MAX_RANGE_BYTES,
    ) -> bytes:
        """Read ``[start, end_inclusive]`` and never the tensor payload.

        A server that ignores Range returns 200; we fail rather than stream a
        full weights file.
        """
        path = _validate_repo_path(path)
        if start < 0 or end_inclusive < start:
            raise HFError(
                "invalid_range",
                "Invalid byte range requested.",
                status_code=500,
                details={"start": start, "end": end_inclusive},
            )
        length = end_inclusive - start + 1
        if length > max_bytes:
            raise HFError(
                "range_too_large",
                "The requested metadata range exceeds OmniRun's safety cap.",
                status_code=502,
                details={"requested_bytes": length, "max_bytes": max_bytes},
            )

        file_meta = repo.file(path)
        if file_meta is None:
            raise HFError(
                "file_not_found",
                f"{path} was not found in {repo.repo_id}.",
                status_code=404,
                details={"repo_id": repo.repo_id, "path": path},
            )
        if file_meta.size is not None and end_inclusive >= file_meta.size:
            raise HFError(
                "range_not_satisfiable",
                f"Requested range ends beyond the size of {path}.",
                status_code=500,
                details={
                    "repo_id": repo.repo_id,
                    "path": path,
                    "size": file_meta.size,
                    "start": start,
                    "end": end_inclusive,
                },
            )

        token = _validate_token(token)
        revision = revision or repo.sha
        response = await self._request(
            self._file_url(repo.repo_id, revision, path),
            token=token,
            max_bytes=length,
            range_header=f"bytes={start}-{end_inclusive}",
            accept="application/octet-stream",
        )

        if response.status == 206:
            content_range = response.headers.get("content-range")
            parsed = _parse_content_range(content_range)
            if parsed is None:
                raise HFError(
                    "invalid_hf_response",
                    "Hugging Face returned a partial response without a usable Content-Range.",
                    status_code=502,
                    upstream_status=206,
                    details={"repo_id": repo.repo_id, "path": path},
                )
            range_start, range_end, total = parsed
            if range_start != start or range_end != end_inclusive:
                raise HFError(
                    "invalid_hf_response",
                    "Hugging Face returned a different byte range than requested.",
                    status_code=502,
                    upstream_status=206,
                    details={
                        "repo_id": repo.repo_id,
                        "path": path,
                        "requested": [start, end_inclusive],
                        "returned": [range_start, range_end],
                    },
                )
            if total is not None and file_meta.size is not None and total != file_meta.size:
                raise HFError(
                    "invalid_hf_response",
                    "The file size changed while OmniRun was reading it.",
                    status_code=502,
                    upstream_status=206,
                    details={"repo_id": repo.repo_id, "path": path},
                )
            if len(response.content) != length:
                raise HFError(
                    "invalid_hf_response",
                    "Hugging Face returned an incomplete metadata range.",
                    status_code=502,
                    upstream_status=206,
                    details={
                        "repo_id": repo.repo_id,
                        "path": path,
                        "expected_bytes": length,
                        "received_bytes": len(response.content),
                    },
                )
            return response.content

        if response.status == 200:
            raise HFError(
                "range_unsupported",
                "Hugging Face did not honor the byte-range request.",
                status_code=502,
                upstream_status=200,
                hint="OmniRun refuses to download a full weights file. Try again later.",
                details={"repo_id": repo.repo_id, "path": path},
            )

        raise self._file_http_error(response, repo, path, has_token=bool(token))

    def _file_http_error(
        self,
        response: _Response,
        repo: HFRepo,
        path: str,
        *,
        has_token: bool,
    ) -> HFError:
        upstream = _sanitize_upstream_message(response.content)
        if response.status in _AUTH_STATUS:
            if has_token:
                return HFError(
                    "repo_access_denied",
                    "Hugging Face denied access to this file.",
                    status_code=403,
                    upstream_status=response.status,
                    hint=(
                        "Check the token and whether the account has accepted this model's "
                        "license. Gated files cannot be inspected anonymously."
                    ),
                    details={
                        "repo_id": repo.repo_id,
                        "path": path,
                        "upstream_message": upstream,
                    },
                )
            return HFError(
                "repo_auth_required",
                "This model file is gated or private.",
                status_code=403,
                upstream_status=response.status,
                hint=(
                    "Open the model page, accept the license if required, and retry with "
                    "an hf_token from an account with access."
                ),
                details={
                    "repo_id": repo.repo_id,
                    "path": path,
                    "upstream_message": upstream,
                },
            )
        if response.status == 404:
            return HFError(
                "file_not_found",
                f"{path} was not found at revision {repo.sha[:12]}.",
                status_code=404,
                upstream_status=404,
                details={"repo_id": repo.repo_id, "path": path},
            )
        if response.status == 416:
            return HFError(
                "range_not_satisfiable",
                "Hugging Face could not satisfy the metadata byte range.",
                status_code=502,
                upstream_status=416,
                details={"repo_id": repo.repo_id, "path": path},
            )
        return HFError(
            "hf_upstream_error",
            f"Hugging Face returned HTTP {response.status} while reading {path}.",
            status_code=502,
            upstream_status=response.status,
            retryable=True,
            details={"repo_id": repo.repo_id, "path": path, "upstream_message": upstream},
        )


def _quote_repo(repo_id: str) -> str:
    # quote() with safe='/' preserves the owner/model separator.
    return quote(repo_id, safe="/")


def _quote_segment(value: str) -> str:
    return quote(value, safe="")


def _quote_path(path: str) -> str:
    return quote(path, safe="/")


def _validate_repo_path(path: str) -> str:
    if not isinstance(path, str) or not path:
        raise HFError("invalid_path", "File path is required.", status_code=500)
    if len(path) > 1000 or "\x00" in path or "\\" in path:
        raise HFError("invalid_path", "File path has an invalid format.", status_code=500)
    if path.startswith("/") or path.endswith("/") or "//" in path:
        raise HFError("invalid_path", "File path must be relative to the repo.", status_code=500)
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise HFError("invalid_path", "File path traversal is not allowed.", status_code=500)
    return path


def _parse_content_range(value: str | None) -> tuple[int, int, int | None] | None:
    if not value:
        return None
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", value.strip(), re.IGNORECASE)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    total = None if match.group(3) == "*" else int(match.group(3))
    if end < start:
        return None
    return start, end, total


async def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    length_header = response.headers.get("content-length")
    if length_header:
        try:
            if int(length_header) > max_bytes:
                raise HFError(
                    "response_too_large",
                    "Hugging Face returned more metadata than OmniRun allows.",
                    status_code=502,
                    details={"max_bytes": max_bytes},
                )
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise HFError(
                "response_too_large",
                "Hugging Face returned more metadata than OmniRun allows.",
                status_code=502,
                details={"max_bytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _repo_from_payload(
    payload: Mapping[str, Any],
    requested_repo_id: str,
    *,
    fetched_at: datetime,
) -> HFRepo:
    repo_id = payload.get("id")
    sha = payload.get("sha")
    if not isinstance(repo_id, str) or not repo_id:
        raise HFError(
            "invalid_hf_response",
            "Hugging Face did not return a repo id.",
            status_code=502,
        )
    if not isinstance(sha, str) or not sha:
        raise HFError(
            "invalid_hf_response",
            "Hugging Face did not return a commit SHA; refusing to inspect a moving revision.",
            status_code=502,
        )

    siblings = payload.get("siblings") or []
    if not isinstance(siblings, list):
        raise HFError(
            "invalid_hf_response",
            "Hugging Face returned an invalid file list.",
            status_code=502,
        )
    if len(siblings) > MAX_FILES:
        raise HFError(
            "repo_too_many_files",
            f"This repo has too many files to inspect safely ({len(siblings)}).",
            status_code=502,
        )

    files: dict[str, RepoFile] = {}
    for item in siblings:
        if not isinstance(item, dict):
            continue
        path = item.get("rfilename")
        if not isinstance(path, str) or not path or path in files:
            continue
        size: int | None = None
        raw_size = item.get("size")
        if isinstance(raw_size, int) and raw_size >= 0:
            size = raw_size
        lfs = item.get("lfs")
        lfs_sha = None
        if isinstance(lfs, dict):
            if size is None:
                lfs_size = lfs.get("size")
                if isinstance(lfs_size, int) and lfs_size >= 0:
                    size = lfs_size
            if isinstance(lfs.get("sha256"), str):
                lfs_sha = lfs["sha256"]
        files[path] = RepoFile(
            path=path,
            size=size,
            blob_id=item.get("blobId") if isinstance(item.get("blobId"), str) else None,
            lfs_sha256=lfs_sha,
        )

    gated_raw = payload.get("gated", False)
    gated = bool(gated_raw)
    gated_mode: str | None = None
    if isinstance(gated_raw, str):
        gated_mode = gated_raw
    elif gated:
        gated_mode = "manual"

    last_modified = None
    raw_modified = payload.get("lastModified")
    if isinstance(raw_modified, str):
        try:
            last_modified = datetime.fromisoformat(raw_modified.replace("Z", "+00:00"))
        except ValueError:
            last_modified = None

    tags = payload.get("tags")
    pipeline_tag = payload.get("pipeline_tag")
    library_name = payload.get("library_name")
    return HFRepo(
        repo_id=repo_id,
        requested_repo_id=requested_repo_id,
        sha=sha,
        private=bool(payload.get("private", False)),
        gated=gated,
        gated_mode=gated_mode,
        pipeline_tag=pipeline_tag if isinstance(pipeline_tag, str) else None,
        library_name=library_name if isinstance(library_name, str) else None,
        tags=tuple(str(tag) for tag in tags) if isinstance(tags, list) else (),
        last_modified=last_modified,
        files=files,
        cache_hit=False,
        cache_stale=False,
        fetched_at=fetched_at,
    )
