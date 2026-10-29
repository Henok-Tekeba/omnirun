from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from api.main import create_app
from api.settings import Settings
from core.hardware import GIB, encode_hardware_code
from tests.hf_fixtures import fixture_client

ROOT = Path(__file__).resolve().parent.parent


def helper_code(
    *,
    ram_gib: float = 48,
    bandwidth_gbps: float = 190.5,
    acc_name: str = "Apple M4 Pro",
    acc_kind: str = "unified",
    vram_gib: float | None = None,
) -> str:
    return encode_hardware_code(
        {
            "v": 1,
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "tool": "omnirun-helper/0.1.0",
            "os": "macOS 15.0",
            "arch": "arm64",
            "cpu": acc_name,
            "cores": 14,
            "ram": int(ram_gib * GIB),
            "acc": {
                "kind": acc_kind,
                "name": acc_name,
                "vendor": "apple" if acc_kind == "unified" else "nvidia",
                "vram": int(vram_gib * GIB) if vram_gib else None,
            },
            "bw": {
                "gbps": bandwidth_gbps,
                "method": "threaded_memcpy_v1",
                "seconds": 2.0,
                "threads": 4,
            },
            "notes": [],
        }
    )


def make_settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(
        data_dir=ROOT / "data",
        cache_dir=tmp_path / "cache",
        result_cache_ttl_seconds=overrides.pop("result_cache_ttl_seconds", 600),
        **overrides,
    )


async def api_client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def test_go_response_and_result_cache(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("smollm2_135m", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            payload = {
                "model": "HuggingFaceTB/SmolLM2-135M-Instruct",
                "hardware": {"source": "helper", "code": helper_code()},
                "context": 4096,
                "batch": 1,
            }
            response = await client.post("/check", json=payload)
            assert response.status_code == 200, response.text
            assert response.headers.get("x-request-id")
            data = response.json()
            assert data["schema_version"] == "1.0"
            assert data["verdict"]["value"] == "GO"
            assert data["claims"]["fits"]["status"] == "yes"
            assert data["claims"]["supported"]["status"] == "yes"
            assert data["claims"]["verified"]["status"] == "unknown"
            assert data["model"]["architecture"] == "LlamaForCausalLM"
            assert data["model"]["format"] == "safetensors"
            assert data["hardware"]["source"] == "helper"
            assert data["hardware"]["memory_budget_bytes"] > 30 * GIB
            assert data["memory"]["peak"]["min"] < data["memory"]["peak"]["max"]
            assert data["speed"]["available"] is True
            assert data["speed"]["aggregate"]["likely"] > 0
            assert data["cache"]["result_cache_hit"] is False
            assert data["links"]["hf_model"].startswith("https://huggingface.co/")
            assert data["assumptions"]
            assert data["recommendations"] == []

            again = await client.post("/check", json=payload)
            assert again.status_code == 200
            cached = again.json()
            assert cached["cache"]["result_cache_hit"] is True
            assert cached["verdict"]["value"] == "GO"


async def test_manual_hardware_and_context_clamp(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("smollm2_135m", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            response = await client.post(
                "/check",
                json={
                    "model": "HuggingFaceTB/SmolLM2-135M-Instruct",
                    "hardware": {
                        "source": "manual",
                        "device_id": "apple-m2-pro",
                        "ram_gib": 32,
                    },
                    "context": 10_000,
                    "batch": 1,
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["hardware"]["confidence"] == "medium"
            assert data["inputs"]["context_clamped"] is True
            assert data["inputs"]["context_effective"] == 8192
            assert any(
                assumption["id"] == "context_clamped"
                for assumption in data["assumptions"]
            )


async def test_optimize_verdict_for_small_gpu(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("mistral_7b", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            response = await client.post(
                "/check",
                json={
                    "model": "mistralai/Mistral-7B-v0.1",
                    "hardware": {"source": "manual", "device_id": "nvidia-rtx-3060-12gb"},
                    "context": 4096,
                    "batch": 1,
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["verdict"]["value"] == "OPTIMIZE"
            assert data["claims"]["fits"]["status"] == "no"
            assert data["claims"]["supported"]["status"] == "yes"
            alternatives = {
                item["name"]: item
                for item in data["memory"]["weights"]["alternatives"]
            }
            assert alternatives["int8"]["fits"] == "yes"
            assert alternatives["4bit"]["fits"] == "yes"


async def test_no_verdict_for_tiny_memory(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("mistral_7b", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            response = await client.post(
                "/check",
                json={
                    "model": "mistralai/Mistral-7B-v0.1",
                    "hardware": {"source": "unknown", "ram_gib": 4},
                    "context": 4096,
                    "batch": 1,
                },
            )
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["verdict"]["value"] == "NO"
            assert data["hardware"]["confidence"] == "low"


async def test_hf_token_is_not_echoed(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("smollm2_135m", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            secret = "hf_this_must_not_echo_123"
            response = await client.post(
                "/check",
                json={
                    "model": "HuggingFaceTB/SmolLM2-135M-Instruct",
                    "hardware": {"source": "helper", "code": helper_code()},
                    "hf_token": secret,
                },
            )
            assert response.status_code == 200, response.text
            assert secret not in response.text


async def test_invalid_helper_code_is_clear_error(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("smollm2_135m", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            response = await client.post(
                "/check",
                json={
                    "model": "HuggingFaceTB/SmolLM2-135M-Instruct",
                    "hardware": {"source": "helper", "code": "not-a-code"},
                },
            )
            assert response.status_code == 422
            data = response.json()
            assert data["error"]["code"] == "invalid_hardware_code"
            assert data["error"]["hint"]


async def test_gated_repo_error_envelope(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with fixture_client("llama_3_2_1b_gated", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            response = await client.post(
                "/check",
                json={
                    "model": "meta-llama/Llama-3.2-1B",
                    "hardware": {"source": "manual", "device_id": "nvidia-rtx-4090"},
                },
            )
            assert response.status_code == 403
            data = response.json()
            assert data["schema_version"] == "1.0"
            assert data["error"]["code"] == "repo_auth_required"
            assert data["error"]["status"] == 403
            assert data["request_id"] == response.headers["x-request-id"]


async def test_validation_error_envelope(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with await api_client(app) as client:
        response = await client.post("/check", json={"model": "org/model"})
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "validation_error"
        assert data["error"]["details"]["errors"]


async def test_rate_limit(tmp_path: Path) -> None:
    app = create_app(
        make_settings(
            tmp_path,
            rate_limit_per_minute=1,
            rate_limit_burst=1,
            result_cache_ttl_seconds=0,
        )
    )
    async with fixture_client("smollm2_135m", tmp_path) as hf:
        app.state.hf_client = hf
        async with await api_client(app) as client:
            payload = {
                "model": "HuggingFaceTB/SmolLM2-135M-Instruct",
                "hardware": {"source": "helper", "code": helper_code()},
            }
            first = await client.post("/check", json=payload)
            assert first.status_code == 200
            second = await client.post("/check", json=payload)
            assert second.status_code == 429
            data = second.json()
            assert data["error"]["code"] == "rate_limited"
            assert int(second.headers["retry-after"]) >= 1


async def test_health_and_schema(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    async with await api_client(app) as client:
        health = await client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        schema = await client.get("/schema")
        assert schema.status_code == 200
        data = schema.json()
        assert data["schema_version"] == "1.0"
        assert "CheckRequest" in data["request"]["title"]
        assert "CheckResponse" in data["response"]["title"]
        assert "ErrorResponse" in data["error"]["title"]
