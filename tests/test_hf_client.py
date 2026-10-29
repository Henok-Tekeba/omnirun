from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from core.cache import DiskCache
from core.errors import HFError
from core.hf_client import HFClient

SHA = "a" * 40
CONFIG_PATH = "/api/models/org/model"


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def repo_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "org/model",
        "sha": SHA,
        "private": False,
        "gated": False,
        "pipeline_tag": "text-generation",
        "library_name": "transformers",
        "tags": ["safetensors", "text-generation"],
        "lastModified": "2025-01-02T03:04:05.000Z",
        "siblings": [
            {"rfilename": "config.json", "size": 100, "blobId": "config"},
            {
                "rfilename": "model.safetensors",
                "size": 100,
                "blobId": "weights",
                "lfs": {"sha256": "b" * 64, "size": 100},
            },
        ],
    }
    payload.update(overrides)
    return payload


def client_for(
    tmp_path: Path,
    handler: Any,
    *,
    cache: DiskCache | None = None,
    **kwargs: Any,
) -> HFClient:
    return HFClient(
        endpoint="https://hf.test",
        cache=cache or DiskCache(tmp_path),
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def test_resolve_repo_and_cache(tmp_path: Path) -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.url.path == CONFIG_PATH
        assert request.url.params.get("blobs") == "true"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=repo_payload())

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        assert repo.repo_id == "org/model"
        assert repo.sha == SHA
        assert repo.files["config.json"].size == 100
        assert repo.files["model.safetensors"].lfs_sha256 == "b" * 64
        assert repo.cache_hit is False

        cached = await client.resolve_repo("org/model")
        assert cached.cache_hit is True
        assert cached.cache_stale is False

    assert len(calls) == 1


async def test_revision_url_is_honored(tmp_path: Path) -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.path == "/api/models/org/model/revision/v1"
        return httpx.Response(200, json=repo_payload())

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("https://huggingface.co/org/model/tree/v1")
        assert repo.sha == SHA
        assert calls == ["/api/models/org/model/revision/v1"]


async def test_token_cache_isolation_and_auth_errors(tmp_path: Path) -> None:
    calls: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("authorization")
        calls.append(auth)
        if auth == "Bearer good-token":
            return httpx.Response(200, json=repo_payload(private=True))
        return httpx.Response(401, json={"error": "authentication required"})

    async with client_for(tmp_path, handler) as client:
        with pytest.raises(HFError) as exc:
            await client.resolve_repo("org/model")
        assert exc.value.code == "repo_auth_required"
        assert exc.value.status_code == 403
        assert "gated or private" in exc.value.message

        repo = await client.resolve_repo("org/model", token="good-token")
        assert repo.private is True
        assert repo.cache_hit is False
        assert "good-token" not in json.dumps(repo.to_cache_dict())

        with pytest.raises(HFError):
            await client.resolve_repo("org/model")

        cached = await client.resolve_repo("org/model", token="good-token")
        assert cached.cache_hit is True

    assert calls == [None, "Bearer good-token", None]


async def test_token_rejected(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "access denied"})

    async with client_for(tmp_path, handler) as client:
        with pytest.raises(HFError) as exc:
            await client.resolve_repo("org/model", token="bad")
        assert exc.value.code == "repo_access_denied"
        assert exc.value.upstream_status == 403


async def test_repo_not_found(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    async with client_for(tmp_path, handler) as client:
        with pytest.raises(HFError) as exc:
            await client.resolve_repo("org/nope")
        assert exc.value.code == "repo_not_found"
        assert exc.value.status_code == 404


async def test_rate_limit_retry_then_success(tmp_path: Path) -> None:
    calls = 0
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")
        return httpx.Response(200, json=repo_payload())

    async with client_for(
        tmp_path, handler, max_attempts=2, sleep=sleep
    ) as client:
        repo = await client.resolve_repo("org/model")
        assert repo.sha == SHA

    assert calls == 2
    assert sleeps == [0.0]


async def test_rate_limit_exhausted(tmp_path: Path) -> None:
    async def sleep(seconds: float) -> None:
        pass

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")

    async with client_for(
        tmp_path, handler, max_attempts=2, sleep=sleep
    ) as client:
        with pytest.raises(HFError) as exc:
            await client.resolve_repo("org/model")
        assert exc.value.code == "hf_rate_limited"
        assert exc.value.retryable is True
        assert exc.value.retry_after == 0.0


async def test_stale_model_info_used_on_upstream_failure(tmp_path: Path) -> None:
    clock = Clock()
    cache = DiskCache(tmp_path, clock=clock)
    fail = False

    async def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json=repo_payload())

    async with client_for(tmp_path, handler, cache=cache) as client:
        first = await client.resolve_repo("org/model")
        assert first.cache_stale is False

    clock.advance(601)
    fail = True

    async with client_for(
        tmp_path, handler, cache=cache, max_attempts=1
    ) as client:
        stale = await client.resolve_repo("org/model")
        assert stale.cache_hit is True
        assert stale.cache_stale is True


async def test_get_json_file_cached_and_pinned(tmp_path: Path) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        calls += 1
        assert request.url.path == f"/org/model/resolve/{SHA}/config.json"
        return httpx.Response(200, json={"model_type": "llama"})

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        config = await client.get_json_file(repo, "config.json")
        assert config.data == {"model_type": "llama"}
        assert config.from_cache is False

        again = await client.get_json_file(repo, "config.json")
        assert again.from_cache is True
        assert again.stale is False

    assert calls == 1


async def test_get_json_file_rejects_traversal_before_request(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=repo_payload())

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_json_file(repo, "../config.json")
        assert exc.value.code == "invalid_path"


async def test_get_json_file_size_cap(tmp_path: Path) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=repo_payload())

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_json_file(repo, "config.json", max_bytes=50)
        assert exc.value.code == "file_too_large"

    assert calls == 1  # only the model-info request


async def test_get_json_file_invalid_json(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        return httpx.Response(200, content=b"{not json")

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_json_file(repo, "config.json")
        assert exc.value.code == "invalid_json"


async def test_get_json_response_size_cap(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        return httpx.Response(200, content=b"x" * 2000)

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_json_file(repo, "config.json", max_bytes=1000)
        assert exc.value.code == "response_too_large"


async def test_range_request(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        assert request.url.path == f"/org/model/resolve/{SHA}/model.safetensors"
        assert request.headers.get("range") == "bytes=0-7"
        return httpx.Response(
            206,
            content=b"12345678",
            headers={"Content-Range": "bytes 0-7/100"},
        )

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        payload = await client.get_range(repo, "model.safetensors", 0, 7)
        assert payload == b"12345678"


async def test_range_wrong_content_range(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        return httpx.Response(
            206,
            content=b"12345678",
            headers={"Content-Range": "bytes 0-6/100"},
        )

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_range(repo, "model.safetensors", 0, 7)
        assert exc.value.code == "invalid_hf_response"


async def test_range_ignored_returns_200_is_rejected(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        return httpx.Response(200, content=b"x" * 100)

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_range(repo, "model.safetensors", 0, 7)
        assert exc.value.code == "range_unsupported"


async def test_range_beyond_file_size_rejected(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=repo_payload())

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_range(repo, "model.safetensors", 90, 120)
        assert exc.value.code == "range_not_satisfiable"


async def test_range_416_maps(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        return httpx.Response(416)

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_range(repo, "model.safetensors", 0, 7)
        assert exc.value.code == "range_not_satisfiable"


async def test_range_auth_error_maps(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        return httpx.Response(401, text="gated")

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_range(repo, "model.safetensors", 0, 7)
        assert exc.value.code == "repo_auth_required"


async def test_file_auth_error_with_token(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == CONFIG_PATH:
            return httpx.Response(200, json=repo_payload())
        assert request.headers.get("authorization") == "Bearer token"
        return httpx.Response(403, text="gated")

    async with client_for(tmp_path, handler) as client:
        repo = await client.resolve_repo("org/model")
        with pytest.raises(HFError) as exc:
            await client.get_json_file(repo, "config.json", token="token")
        assert exc.value.code == "repo_access_denied"
