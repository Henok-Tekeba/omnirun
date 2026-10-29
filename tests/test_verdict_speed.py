from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

from core.claims import ClaimStatus, Verdict
from core.estimate import estimate_memory
from core.hardware import profile_from_manual, profile_from_unknown
from core.inspect.model import ModelFormat
from core.speed import estimate_llm_speed
from core.support import build_support_claim, load_support_matrix
from core.verdict import decide_verdict
from core.verified import build_verified_claim, load_verified_runs
from tests.hf_fixtures import fixture_client, load_json
from tests.test_support import fake_inspection


async def smol(tmp_path: Path):
    async with fixture_client("smollm2_135m", tmp_path) as client:
        return await inspect_smol(client)


async def inspect_smol(client):
    from core.inspect.model import inspect_model

    return await inspect_model(client, "HuggingFaceTB/SmolLM2-135M-Instruct")


async def mistral(tmp_path: Path):
    from core.inspect.model import inspect_model

    async with fixture_client("mistral_7b", tmp_path) as client:
        return await inspect_model(client, "mistralai/Mistral-7B-v0.1")


async def test_speed_dense_decode_and_batch(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    memory = estimate_memory(inspection, context=4096, batch=1)
    speed = estimate_llm_speed(inspection, memory, hardware, batch=1)
    assert speed.available
    assert speed.aggregate is not None
    expected = 200e9 * 0.70 / (inspection.active_weight_bytes + memory.kv.bytes_likely)
    assert math.isclose(speed.aggregate.likely, expected, rel_tol=1e-3)
    assert speed.speed_class.value == "interactive"
    assert speed.confidence.value == "medium"

    batch4 = estimate_llm_speed(
        inspection,
        estimate_memory(inspection, context=4096, batch=4),
        hardware,
        batch=4,
    )
    assert batch4.available and batch4.aggregate is not None
    assert batch4.aggregate.likely > speed.aggregate.likely
    assert math.isclose(batch4.aggregate.likely / 4, batch4.per_sequence.likely, rel_tol=1e-3)


async def test_speed_unknown_without_bandwidth(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    hardware = replace(profile_from_manual("apple-m2-pro", ram_gib=32), bandwidth_gbps=None)
    speed = estimate_llm_speed(
        inspection,
        estimate_memory(inspection, context=4096, batch=1),
        hardware,
        batch=1,
    )
    assert speed.available is False
    assert speed.aggregate is None
    assert any(issue.code == "speed_unavailable" for issue in speed.issues)


async def test_speed_non_llm_is_unavailable(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    inspection = replace(
        inspection,
        repo=replace(inspection.repo, pipeline_tag="text-to-speech"),
        config=replace(
            inspection.config,
            architectures=("WhisperForConditionalGeneration",),
        ),
    )
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    speed = estimate_llm_speed(
        inspection,
        estimate_memory(inspection, context=4096, batch=1),
        hardware,
        batch=1,
    )
    assert speed.available is False


async def test_go_requires_fits_and_supported(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    memory = estimate_memory(inspection, context=4096, batch=1)
    support = build_support_claim(inspection, load_support_matrix())
    verified = build_verified_claim(inspection, hardware, ())
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=verified,
        context=4096,
        batch=1,
        model_class_supported=True,
    )
    assert result.value == Verdict.GO
    assert result.fit.status == ClaimStatus.YES
    assert result.basis_claims == ("fits", "supported")
    assert result.fit.headroom_ratio is not None and result.fit.headroom_ratio > 0.9
    assert "VERIFIED" in result.summary


async def test_optimize_when_smaller_quant_fits(tmp_path: Path) -> None:
    inspection = await mistral(tmp_path)
    hardware = profile_from_manual("nvidia-rtx-3060-12gb")
    memory = estimate_memory(inspection, context=4096, batch=1)
    support = build_support_claim(inspection, load_support_matrix())
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=build_verified_claim(inspection, hardware, ()),
        context=4096,
        batch=1,
        model_class_supported=True,
    )
    assert result.fit.status == ClaimStatus.NO
    assert result.value == Verdict.OPTIMIZE
    fits = {quant.alternative.name: quant.status for quant in result.quant_fits}
    assert fits["int8"] == ClaimStatus.YES
    assert fits["4bit"] == ClaimStatus.YES
    assert any(option.kind == "quantization" for option in result.options)


async def test_no_when_nothing_fits(tmp_path: Path) -> None:
    inspection = await mistral(tmp_path)
    hardware = profile_from_unknown(ram_gib=4)
    memory = estimate_memory(inspection, context=4096, batch=1)
    support = build_support_claim(inspection, load_support_matrix())
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=build_verified_claim(inspection, hardware, ()),
        context=4096,
        batch=1,
        model_class_supported=True,
    )
    assert result.fit.status == ClaimStatus.NO
    assert result.value == Verdict.NO
    assert result.options == ()


async def test_unknown_when_support_matrix_missing(tmp_path: Path) -> None:
    config = load_json("chatglm3", "config.json")
    inspection = fake_inspection(
        architecture_config=config,
        files={"config.json": 10, "model.safetensors": 100},
        fmt=ModelFormat.SAFETENSORS,
        weight_bytes=1,
    )
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    memory = estimate_memory(inspection, context=4096, batch=1)
    support = build_support_claim(inspection, load_support_matrix())
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=build_verified_claim(inspection, hardware, ()),
        context=4096,
        batch=1,
        model_class_supported=True,
    )
    assert support.status == ClaimStatus.UNKNOWN
    assert result.value == Verdict.UNKNOWN


async def test_conversion_only_support_is_optimize(tmp_path: Path) -> None:
    config = {
        "architectures": ["T5ForConditionalGeneration"],
        "model_type": "t5",
        "num_layers": 2,
        "d_model": 32,
        "num_heads": 4,
        "max_position_embeddings": 128,
        "torch_dtype": "float16",
    }
    inspection = fake_inspection(
        architecture_config=config,
        files={"model.gguf": 100},
        fmt=ModelFormat.GGUF,
        weight_bytes=1,
    )
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    memory = estimate_memory(inspection, context=128, batch=1)
    support = build_support_claim(inspection, load_support_matrix())
    assert support.direct_runtime_available is False
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=build_verified_claim(inspection, hardware, ()),
        context=128,
        batch=1,
        model_class_supported=True,
    )
    assert result.value == Verdict.OPTIMIZE
    assert "conversion" in result.summary.lower()


async def test_tight_headroom_is_optimize(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    memory = estimate_memory(inspection, context=4096, batch=1)
    assert memory.peak is not None
    hardware = replace(hardware, memory_budget_bytes=round(memory.peak.max * 1.02))
    support = build_support_claim(inspection, load_support_matrix())
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=build_verified_claim(inspection, hardware, ()),
        context=4096,
        batch=1,
        model_class_supported=True,
    )
    assert result.fit.status == ClaimStatus.YES
    assert result.value == Verdict.OPTIMIZE
    assert "headroom" in result.summary.lower()


async def test_non_llm_class_is_unknown(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    memory = estimate_memory(inspection, context=4096, batch=1)
    support = build_support_claim(inspection, load_support_matrix())
    result = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=build_verified_claim(inspection, hardware, ()),
        context=4096,
        batch=1,
        model_class_supported=False,
    )
    assert result.value == Verdict.UNKNOWN
    assert any(issue.code == "model_class_pending" for issue in result.reasons)


async def test_verified_empty_and_matching(tmp_path: Path) -> None:
    inspection = await smol(tmp_path)
    hardware = profile_from_manual("apple-m2-pro", ram_gib=32)
    assert load_verified_runs() == ()
    empty = build_verified_claim(inspection, hardware, ())
    assert empty.status == ClaimStatus.UNKNOWN

    payload = {
        "version": 1,
        "runs": [
            {
                "run_id": "run-1",
                "repo_id": inspection.repo.repo_id,
                "revision": inspection.repo.sha,
                "architecture": "LlamaForCausalLM",
                "hardware_device_id": "apple-m2-pro",
                "hardware_device_name": "Apple M2 Pro",
                "runtime": "transformers",
                "runtime_version": "4.42.0",
                "artifact_format": "safetensors",
                "quantization": None,
                "context_tokens": 4096,
                "batch": 1,
                "peak_memory_bytes": 700_000_000,
                "decode_tokens_per_second": 370.0,
                "recorded_at": "2026-01-01T00:00:00Z",
                "source_url": "https://example.invalid/run-1",
            }
        ],
    }
    path = tmp_path / "verified.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    runs = load_verified_runs(path)
    claim = build_verified_claim(inspection, hardware, runs)
    assert claim.status == ClaimStatus.YES
    assert claim.runs[0].run_id == "run-1"
