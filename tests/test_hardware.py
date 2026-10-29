from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.errors import InputError
from core.hardware import (
    APPLE_SILICON_USABLE_MEMORY_FRACTION,
    GIB,
    decode_hardware_code,
    encode_hardware_code,
    load_device_table,
    profile_from_helper,
    profile_from_manual,
    profile_from_unknown,
)

ROOT = Path(__file__).resolve().parent.parent
HELPER_PATH = ROOT / "helper" / "omnirun_helper.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("omnirun_helper_test", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(**overrides):
    data = {
        "v": 1,
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": "omnirun-helper/0.1.0",
        "os": "macOS 15.0",
        "arch": "arm64",
        "cpu": "Apple M4 Pro",
        "cores": 14,
        "ram": 48 * GIB,
        "acc": {
            "kind": "unified",
            "name": "Apple M4 Pro",
            "vendor": "apple",
            "vram": None,
        },
        "bw": {
            "gbps": 190.5,
            "method": "threaded_memcpy_v1",
            "seconds": 2.01,
            "threads": 4,
        },
        "notes": [],
    }
    data.update(overrides)
    return data


def test_device_table_loads_and_looks_up() -> None:
    table = load_device_table()
    assert table.get("apple-m2-pro") is not None
    assert table.get("nvidia-rtx-4090").vram_gib == 24
    assert table.find_by_name("NVIDIA GeForce RTX 4090").id == "nvidia-rtx-4090"
    assert table.find_by_name("RTX 4090").id == "nvidia-rtx-4090"
    assert table.find_by_name("Apple M4 Pro").id == "apple-m4-pro"
    assert table.find_by_name("NVIDIA GeForce RTX 4090 Laptop GPU") is None


def test_code_roundtrip() -> None:
    code = encode_hardware_code(payload())
    assert len(code) < 4096
    decoded = decode_hardware_code(code)
    assert decoded.ram_bytes == 48 * GIB
    assert decoded.acc_kind.value == "unified"
    assert decoded.bandwidth_gbps == 190.5
    assert decoded.cores == 14


def test_helper_encoder_matches_core_decoder() -> None:
    helper = load_helper()
    data = payload()
    code = helper.encode_code(data)
    decoded = decode_hardware_code(code)
    assert decoded.acc_name == "Apple M4 Pro"
    assert decoded.bandwidth_gbps == 190.5


def test_helper_build_profile_no_bench() -> None:
    helper = load_helper()
    data = helper.build_profile(seconds=0.2, no_bench=True)
    assert data["ram"] > 0
    assert data["acc"]["kind"] in {"unified", "discrete", "cpu"}
    assert data["bw"] is None
    decoded = decode_hardware_code(helper.encode_code(data))
    assert decoded.ram_bytes == data["ram"]


def test_helper_main_json_and_code_only(capsys) -> None:
    helper = load_helper()
    assert helper.main(["--no-bench", "--json"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["v"] == 1

    assert helper.main(["--no-bench", "--code-only"]) == 0
    code = capsys.readouterr().out.strip()
    assert code.startswith("OR1.")
    decode_hardware_code(code)


def test_helper_benchmark_is_positive() -> None:
    helper = load_helper()
    if helper.np is None:
        pytest.skip("numpy unavailable")
    result = helper.benchmark_memory(seconds=0.2)
    assert result is not None
    assert 0.1 < result["gbps"] < 5000
    assert result["threads"] >= 1


def test_apple_unified_budget_is_fraction_of_ram() -> None:
    profile = profile_from_helper(encode_hardware_code(payload()))
    assert profile.kind.value == "unified"
    assert profile.memory_budget_bytes == round(48 * GIB * APPLE_SILICON_USABLE_MEMORY_FRACTION)
    assert profile.bandwidth_gbps == 190.5
    assert profile.confidence.value == "high"
    assert profile.apple_fraction == APPLE_SILICON_USABLE_MEMORY_FRACTION


def test_discrete_helper_uses_table_bandwidth() -> None:
    data = payload(
        cpu="AMD Ryzen 9",
        acc={
            "kind": "discrete",
            "name": "NVIDIA GeForce RTX 4090",
            "vendor": "nvidia",
            "vram": 24 * GIB,
        },
        bw=None,
    )
    profile = profile_from_helper(encode_hardware_code(data))
    assert profile.kind.value == "discrete"
    assert profile.memory_budget_bytes == 24 * GIB - 512 * 1024**2
    assert profile.bandwidth_gbps == 1008
    assert profile.bandwidth_source == "device_table"
    assert profile.bandwidth_confidence.value == "medium"


def test_unknown_discrete_gpu_does_not_guess_bandwidth() -> None:
    data = payload(
        cpu="AMD Ryzen 9",
        acc={
            "kind": "discrete",
            "name": "NVIDIA GeForce RTX 5090",
            "vendor": "nvidia",
            "vram": 32 * GIB,
        },
        bw=None,
    )
    profile = profile_from_helper(encode_hardware_code(data))
    assert profile.bandwidth_gbps is None
    assert profile.bandwidth_confidence.value == "low"
    assert profile.memory_budget_bytes == 32 * GIB - 512 * 1024**2


def test_laptop_gpu_not_matched_to_desktop() -> None:
    data = payload(
        cpu="Intel",
        acc={
            "kind": "discrete",
            "name": "NVIDIA GeForce RTX 4090 Laptop GPU",
            "vendor": "nvidia",
            "vram": 16 * GIB,
        },
        bw=None,
    )
    profile = profile_from_helper(encode_hardware_code(data))
    assert profile.bandwidth_gbps is None


def test_manual_apple_and_discrete() -> None:
    table = load_device_table()
    apple = profile_from_manual("apple-m2-pro", ram_gib=32, table=table)
    assert apple.memory_budget_bytes == round(32 * GIB * 0.75)
    assert apple.bandwidth_gbps == 200
    assert apple.confidence.value == "medium"

    gpu = profile_from_manual("nvidia-rtx-4090", table=table)
    assert gpu.memory_budget_bytes == 24 * GIB - 512 * 1024**2
    assert gpu.system_ram_bytes is None
    assert gpu.bandwidth_gbps == 1008

    with pytest.raises(InputError) as exc:
        profile_from_manual("apple-m2-pro", table=table)
    assert exc.value.code == "ram_required"


def test_manual_cpu_is_low_confidence() -> None:
    profile = profile_from_manual("cpu-generic", ram_gib=16)
    assert profile.kind.value == "cpu"
    assert profile.memory_budget_bytes == round(16 * GIB * 0.80)
    assert profile.confidence.value == "low"
    assert profile.bandwidth_gbps == 25


def test_unknown_hardware() -> None:
    profile = profile_from_unknown(ram_gib=16)
    assert profile.memory_budget_bytes == round(16 * GIB * 0.80)
    assert profile.bandwidth_gbps == 25
    assert profile.confidence.value == "low"
    assert profile.memory_confidence.value == "low"

    no_ram = profile_from_unknown()
    assert no_ram.memory_budget_bytes is None
    assert no_ram.confidence.value == "low"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c[:-1] + ("0" if c[-1] != "0" else "1"),
        lambda c: "XX" + c[2:],
        lambda c: c.rsplit(".", 1)[0],
        lambda c: encode_hardware_code(payload(v=2)),
        lambda c: encode_hardware_code(payload(ram=10**18)),
        lambda c: encode_hardware_code(
            payload(
                acc={
                    "kind": "discrete",
                    "name": "NVIDIA RTX 4090",
                    "vendor": "nvidia",
                    "vram": None,
                }
            )
        ),
        lambda c: encode_hardware_code(
            payload(ts=(datetime.now(UTC) + timedelta(days=2)).isoformat())
        ),
    ],
)
def test_invalid_helper_codes(mutate) -> None:
    with pytest.raises(InputError):
        decode_hardware_code(mutate(encode_hardware_code(payload())))


def test_code_size_limit() -> None:
    with pytest.raises(InputError) as exc:
        decode_hardware_code("OR1." + "a" * 5000 + ".00000000")
    assert exc.value.code == "invalid_hardware_code"
