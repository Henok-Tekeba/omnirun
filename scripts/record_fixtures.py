#!/usr/bin/env python3
"""Record public HF metadata fixtures for offline tests.

This script is the only place that intentionally talks to the live HF Hub for
test data. It never fetches tensor payloads: config/index files are small JSON
documents, and safetensors headers are read with Range requests.

Usage:
    uv run python scripts/record_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "hf"
ENDPOINT = "https://huggingface.co"
USER_AGENT = "OmniRun-fixture-recorder/0.1"

REPOS = {
    "smollm2_135m": {
        "repo": "HuggingFaceTB/SmolLM2-135M-Instruct",
        "json": ["config.json"],
        "headers": ["model.safetensors"],
    },
    "mistral_7b": {
        "repo": "mistralai/Mistral-7B-v0.1",
        "json": ["config.json", "model.safetensors.index.json"],
        "headers": [
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
        ],
    },
    "opt_350m": {
        "repo": "facebook/opt-350m",
        "json": ["config.json"],
        "headers": [],
    },
    "llama_3_2_1b_gated": {
        "repo": "meta-llama/Llama-3.2-1B",
        "json": [],
        "headers": [],
        "gated_error": "config.json",
    },
    "chatglm3": {
        "repo": "THUDM/chatglm3-6b",
        "json": ["config.json"],
        "headers": [],
    },
    "whisper_tiny": {
        "repo": "openai/whisper-tiny",
        "json": ["config.json"],
        "headers": [],
    },
}


async def fetch_json(client: httpx.AsyncClient, url: str, **kwargs: object) -> dict:
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


async def fetch_range(
    client: httpx.AsyncClient, url: str, start: int, end: int
) -> bytes:
    response = await client.get(url, headers={"Range": f"bytes={start}-{end}"})
    if response.status_code != 206:
        raise RuntimeError(f"range request returned {response.status_code}: {url}")
    return response.content


async def record_repo(client: httpx.AsyncClient, key: str, spec: dict) -> None:
    repo = spec["repo"]
    out = FIXTURES / key
    out.mkdir(parents=True, exist_ok=True)

    info_url = f"{ENDPOINT}/api/models/{repo}?blobs=true"
    response = await client.get(info_url)
    response.raise_for_status()
    info = response.json()
    sha = info["sha"]
    (out / "model_info.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    manifest: dict = {
        "repo": repo,
        "sha": sha,
        "recorded_at": datetime.now(UTC).isoformat(),
        "source": "https://huggingface.co/" + repo,
        "files": {},
    }
    files = {item["rfilename"]: item for item in info.get("siblings", [])}

    for path in spec.get("json", []):
        payload = await fetch_json(
            client,
            f"{ENDPOINT}/{repo}/resolve/{sha}/{path}",
            headers={"User-Agent": USER_AGENT},
        )
        (out / Path(path).name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest["files"][path] = {"size": files.get(path, {}).get("size")}

    for path in spec.get("headers", []):
        url = f"{ENDPOINT}/{repo}/resolve/{sha}/{path}"
        prefix = await fetch_range(client, url, 0, 7)
        header_len = int.from_bytes(prefix, "little")
        header = await fetch_range(client, url, 8, 8 + header_len - 1)
        output_name = path + ".header.json"
        (out / output_name).write_bytes(header)
        manifest["files"][path] = {
            "size": files.get(path, {}).get("size"),
            "header_len": header_len,
            "header_fixture": output_name,
        }

    if "gated_error" in spec:
        path = spec["gated_error"]
        url = f"{ENDPOINT}/{repo}/resolve/{sha}/{path}"
        response = await client.get(url, headers={"User-Agent": USER_AGENT})
        error = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "body": response.text[:2000],
        }
        (out / "gated_file_error.json").write_text(
            json.dumps(error, indent=2) + "\n", encoding="utf-8"
        )
        manifest["gated_error"] = {"path": path, "status": response.status_code}

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"recorded {key}: {repo}@{sha[:12]} -> {out.relative_to(ROOT)}")


async def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for key, spec in REPOS.items():
            await record_repo(client, key, spec)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
