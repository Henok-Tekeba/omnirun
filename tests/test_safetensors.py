from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.errors import HFError, InspectionError
from core.hf_client import HFRepo, RepoFile
from core.inspect.model import ModelFormat, inspect_model
from core.inspect.safetensors import (
    find_safetensors_shards,
    parse_safetensors_header,
)
from tests.hf_fixtures import fixture_client, fixture_dir, load_manifest


def make_header(tensors: dict, *, file_size: int | None = None) -> tuple[bytes, int]:
    raw = json.dumps(tensors, separators=(",", ":")).encode("utf-8")
    if file_size is None:
        data_end = max(
            (
                entry["data_offsets"][1]
                for entry in tensors.values()
                if isinstance(entry, dict) and "data_offsets" in entry
            ),
            default=0,
        )
        file_size = 8 + len(raw) + data_end
    return raw, len(raw)


def test_parse_safetensors_header_exact() -> None:
    raw, header_len = make_header(
        {
            "__metadata__": {"format": "pt"},
            "a": {"dtype": "F16", "shape": [2, 3], "data_offsets": [0, 12]},
            "b": {"dtype": "BF16", "shape": [4], "data_offsets": [12, 20]},
        }
    )
    header = parse_safetensors_header(raw, header_size=header_len, file_size=8 + header_len + 20)
    assert header.weight_bytes == 20
    assert header.params == 10
    assert header.tensor_count == 2
    assert header.dtype_bytes == {"F16": 12, "BF16": 8}
    assert header.metadata == {"format": "pt"}
    assert header.confidence.value == "high"
    assert header.weight_bytes_exact is True


def test_parse_safetensors_scalar_and_empty() -> None:
    raw, header_len = make_header(
        {"scalar": {"dtype": "F32", "shape": [], "data_offsets": [0, 4]}}
    )
    header = parse_safetensors_header(raw, header_size=header_len, file_size=8 + header_len + 4)
    assert header.params == 1
    assert header.weight_bytes == 4

    empty_raw = b"{}"
    empty = parse_safetensors_header(
        empty_raw, header_size=len(empty_raw), file_size=8 + len(empty_raw)
    )
    assert empty.tensor_count == 0
    assert empty.weight_bytes == 0


def test_parse_safetensors_overlap_is_low_confidence() -> None:
    raw, header_len = make_header(
        {
            "a": {"dtype": "F16", "shape": [6], "data_offsets": [0, 12]},
            "b": {"dtype": "F16", "shape": [6], "data_offsets": [8, 20]},
        }
    )
    header = parse_safetensors_header(raw, header_size=header_len, file_size=8 + header_len + 20)
    assert header.confidence.value == "low"
    assert any(issue.code == "overlapping_safetensors_tensors" for issue in header.issues)


def test_parse_safetensors_bounds_error() -> None:
    raw, header_len = make_header(
        {"a": {"dtype": "F16", "shape": [2], "data_offsets": [0, 4]}}
    )
    with pytest.raises(InspectionError) as exc:
        parse_safetensors_header(raw, header_size=header_len, file_size=8 + header_len + 2)
    assert exc.value.code == "safetensors_bounds_error"


def test_parse_safetensors_header_length_mismatch() -> None:
    raw = b'{"a":{"dtype":"F16","shape":[1],"data_offsets":[0,2]}}'
    with pytest.raises(InspectionError) as exc:
        parse_safetensors_header(raw, header_size=len(raw) + 1, file_size=100)
    assert exc.value.code == "invalid_safetensors_header"


def test_unknown_dtype_lowers_confidence() -> None:
    raw, header_len = make_header(
        {"a": {"dtype": "F4", "shape": [8], "data_offsets": [0, 4]}}
    )
    header = parse_safetensors_header(raw, header_size=header_len, file_size=8 + header_len + 4)
    assert header.confidence.value == "low"
    assert any(issue.code == "unknown_safetensors_dtype" for issue in header.issues)


async def test_inspect_single_safetensors(tmp_path: Path) -> None:
    async with fixture_client("smollm2_135m", tmp_path) as client:
        inspection = await inspect_model(client, "HuggingFaceTB/SmolLM2-135M-Instruct")

    assert inspection.format == ModelFormat.SAFETENSORS
    assert inspection.config is not None
    assert inspection.config.primary_architecture == "LlamaForCausalLM"
    assert inspection.weight_bytes is not None
    assert inspection.weight_bytes_exact is True
    assert inspection.confidence.value == "high"
    assert 100_000_000 < (inspection.params or 0) < 200_000_000
    assert inspection.active_weight_bytes == inspection.weight_bytes
    manifest = load_manifest("smollm2_135m")
    file_info = manifest["files"]["model.safetensors"]
    assert inspection.weight_bytes == file_info["size"] - 8 - file_info["header_len"]
    assert inspection.safetensors is not None
    assert inspection.safetensors.shard_count == 1


async def test_inspect_sharded_safetensors(tmp_path: Path) -> None:
    async with fixture_client("mistral_7b", tmp_path) as client:
        inspection = await inspect_model(client, "mistralai/Mistral-7B-v0.1")

    assert inspection.format == ModelFormat.SAFETENSORS
    assert inspection.safetensors is not None
    assert inspection.safetensors.shard_count == 2
    assert inspection.safetensors.index_total_size == 14_483_464_192
    assert inspection.weight_bytes == 14_483_464_192
    assert inspection.weight_bytes_exact is True
    assert inspection.safetensors.confidence.value == "high"
    assert inspection.params is not None and 7_000_000_000 < inspection.params < 7_500_000_000
    assert inspection.issues == () or all(issue.severity != "risk" for issue in inspection.issues)


async def test_inspect_pickle_only_repo(tmp_path: Path) -> None:
    async with fixture_client("opt_350m", tmp_path) as client:
        inspection = await inspect_model(client, "facebook/opt-350m")

    assert inspection.format == ModelFormat.PYTORCH_PICKLE
    assert inspection.pickle is not None
    assert inspection.weight_bytes is not None
    assert inspection.weight_bytes_exact is False
    assert inspection.confidence.value == "low"
    assert inspection.params is not None
    assert inspection.param_source == "config_estimate"
    assert any(issue.code == "pickle_never_read" for issue in inspection.issues)


async def test_gated_repo_needs_token(tmp_path: Path) -> None:
    async with fixture_client("llama_3_2_1b_gated", tmp_path) as client:
        with pytest.raises(HFError) as exc:
            await inspect_model(client, "meta-llama/Llama-3.2-1B")
    assert exc.value.code == "repo_auth_required"
    assert exc.value.status_code == 403


async def test_ambiguous_safetensors_rejected() -> None:
    repo = HFRepo(
        repo_id="org/model",
        requested_repo_id="org/model",
        sha="a" * 40,
        files={
            "a.safetensors": RepoFile("a.safetensors", 100),
            "b.safetensors": RepoFile("b.safetensors", 100),
        },
    )
    with pytest.raises(InspectionError) as exc:
        await find_safetensors_shards(None, repo)  # type: ignore[arg-type]
    assert exc.value.code == "ambiguous_safetensors"


def test_fixture_header_files_exist() -> None:
    assert (fixture_dir("mistral_7b") / "model-00001-of-00002.safetensors.header.json").exists()
