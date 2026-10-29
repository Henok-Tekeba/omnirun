from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

import httpx

from core.cache import DiskCache
from core.hf_client import HFClient

FIXTURES = Path(__file__).parent / "fixtures" / "hf"


def fixture_dir(name: str) -> Path:
    return FIXTURES / name


def load_json(name: str, filename: str) -> dict:
    return json.loads((fixture_dir(name) / filename).read_text(encoding="utf-8"))


def load_manifest(name: str) -> dict:
    return load_json(name, "manifest.json")


def _file_bytes(name: str, path: str) -> bytes | None:
    directory = fixture_dir(name)
    candidate = directory / (path + ".header.json")
    if candidate.exists():
        return candidate.read_bytes()
    candidate = directory / Path(path).name
    if candidate.exists():
        return candidate.read_bytes()
    return None


@asynccontextmanager
async def fixture_client(
    name: str,
    tmp_path: Path,
    **client_kwargs: object,
) -> AsyncIterator[HFClient]:
    model_info = load_json(name, "model_info.json")
    manifest = load_manifest(name)
    repo = model_info["id"]
    sha = model_info["sha"]
    files = {item["rfilename"] for item in model_info.get("siblings", [])}
    gated_error = None
    gated_path = (manifest.get("gated_error") or {}).get("path")
    if (fixture_dir(name) / "gated_file_error.json").exists():
        gated_error = load_json(name, "gated_file_error.json")

    async def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        if path.rstrip("/") == f"/api/models/{repo}".rstrip("/"):
            return httpx.Response(200, json=model_info)

        prefix = f"/{repo}/resolve/{sha}/"
        if not path.startswith(prefix):
            return httpx.Response(404, text="unknown fixture route")

        filename = path[len(prefix) :]
        if filename not in files:
            return httpx.Response(404, text="not in fixture file list")
        if gated_error and filename == gated_path:
            return httpx.Response(
                int(gated_error["status"]),
                text=str(gated_error.get("body", "")),
            )

        header_bytes = _file_bytes(name, filename)
        if header_bytes is None:
            return httpx.Response(404, text="no fixture bytes")
        is_header = (fixture_dir(name) / (filename + ".header.json")).exists()
        if is_header:
            header_len = len(header_bytes)
            range_header = request.headers.get("range")
            if range_header == "bytes=0-7":
                return httpx.Response(
                    206,
                    content=header_len.to_bytes(8, "little"),
                    headers={
                        "Content-Range": f"bytes 0-7/{manifest['files'][filename]['size']}"
                    },
                )
            expected_end = 8 + header_len - 1
            if range_header == f"bytes=8-{expected_end}":
                return httpx.Response(
                    206,
                    content=header_bytes,
                    headers={
                        "Content-Range": (
                            f"bytes 8-{expected_end}/"
                            f"{manifest['files'][filename]['size']}"
                        )
                    },
                )
            return httpx.Response(416, text="bad fixture range")

        return httpx.Response(
            200,
            content=header_bytes,
            headers={"Content-Type": "application/json"},
        )

    async with HFClient(
        endpoint="https://hf.test",
        cache=DiskCache(tmp_path / "cache"),
        transport=httpx.MockTransport(handler),
        **client_kwargs,
    ) as client:
        yield client
