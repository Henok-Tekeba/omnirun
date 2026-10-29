#!/usr/bin/env python3
"""OmniRun hardware helper.

Single-file, dependency-light script. It detects the local CPU/RAM/accelerator,
runs a ~2 second memory-bandwidth benchmark for CPU/unified memory, and prints
a short code that the OmniRun API accepts instead of manual hardware input.

Usage:
    python omnirun_helper.py
    python omnirun_helper.py --code-only
    python omnirun_helper.py --no-bench --json
    python omnirun_helper.py --seconds 2

Optional dependencies: psutil (RAM/cores), numpy (benchmark). The script
degrades gracefully if either is missing, but a code without a bandwidth
measurement produces a lower-confidence speed estimate.

The code is unsigned. It contains a version, zlib payload, and CRC32; it is not
a security boundary. Do not treat it as proof of hardware.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HELPER_VERSION = "0.1.0"
CODE_PREFIX = "OR1."
CODE_VERSION = 1
GIB = 1024**3
MIB = 1024**2
MAX_CODE_LENGTH = 4096

try:  # optional
    import psutil
except Exception:  # pragma: no cover - environment dependent
    psutil = None

try:  # optional, benchmark only
    import numpy as np
except Exception:  # pragma: no cover - environment dependent
    np = None


def _run(command: list[str], timeout: float = 4.0) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _cpu_name() -> str:
    system = platform.system()
    if system == "Darwin":
        value = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if value:
            return value
    if system == "Linux":
        try:
            cpuinfo = Path("/proc/cpuinfo").read_text(
                encoding="utf-8", errors="replace"
            )
            for line in cpuinfo.splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine() or "Unknown CPU"


def _total_ram_bytes() -> int | None:
    if psutil is not None:
        try:
            return int(psutil.virtual_memory().total)
        except Exception:
            pass
    system = platform.system()
    if system == "Darwin":
        value = _run(["sysctl", "-n", "hw.memsize"])
        if value and value.isdigit():
            return int(value)
    if system == "Linux":
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    kib = int(line.split()[1])
                    return kib * 1024
        except (OSError, ValueError, IndexError):
            pass
    if system == "Windows":  # pragma: no cover - platform dependent
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except Exception:
            pass
    return None


def _cores() -> int | None:
    if psutil is not None:
        try:
            physical = psutil.cpu_count(logical=False)
            if physical:
                return int(physical)
            logical = psutil.cpu_count(logical=True)
            if logical:
                return int(logical)
        except Exception:
            pass
    return os.cpu_count()


def _nvidia_gpu() -> tuple[str, int] | None:
    if shutil.which("nvidia-smi") is None:
        return None
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return None
    first = output.splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 2:
        return None
    name = parts[0]
    try:
        memory_mib = float(parts[1])
    except ValueError:
        return None
    if memory_mib <= 0:
        return None
    return name, round(memory_mib * MIB)


def detect_accelerator(cpu: str) -> dict[str, Any]:
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return {
            "kind": "unified",
            "name": cpu if cpu.startswith("Apple") else "Apple Silicon GPU",
            "vendor": "apple",
            "vram": None,
        }
    nvidia = _nvidia_gpu()
    if nvidia is not None:
        name, vram_bytes = nvidia
        return {
            "kind": "discrete",
            "name": name,
            "vendor": "nvidia",
            "vram": vram_bytes,
        }
    return {
        "kind": "cpu",
        "name": "CPU only",
        "vendor": "generic",
        "vram": None,
    }


def benchmark_memory(seconds: float = 2.0) -> dict[str, Any] | None:
    """Threaded memcpy benchmark. Returns GB/s and method metadata.

    This measures CPU/unified memory bandwidth. It is intentionally not used
    for discrete GPUs; without CUDA/torch the helper cannot measure VRAM
    bandwidth, and pretending otherwise would be worse than returning None.
    """
    if np is None:
        return None
    seconds = max(0.2, min(float(seconds), 10.0))
    total_ram = _total_ram_bytes() or 8 * GIB
    if total_ram < 2 * GIB:
        chunk_bytes = 8 * MIB
        threads = 1
    else:
        chunk_bytes = 32 * MIB
        threads = max(1, min(4, os.cpu_count() or 1))
    # Keep total buffers <= ~256 MiB.
    chunk_bytes = min(chunk_bytes, max(8 * MIB, (256 * MIB) // max(1, threads * 2)))
    elements = max(1, chunk_bytes // 8)

    counts: list[int] = []
    stop = threading.Event()
    barrier = threading.Barrier(threads + 1)

    def worker() -> None:
        try:
            source = np.ones(elements, dtype=np.float64)
            target = np.empty_like(source)
            target[:] = source  # fault pages / warm up
            local = 0
            barrier.wait(timeout=10)
            while not stop.is_set():
                for _ in range(4):
                    target[:] = source
                    local += 2 * source.nbytes
            counts.append(local)
        except Exception:
            with contextlib.suppress(Exception):
                barrier.abort()

    workers = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    for thread in workers:
        thread.start()
    try:
        barrier.wait(timeout=10)
    except threading.BrokenBarrierError:
        stop.set()
        return None
    started = time.perf_counter()
    time.sleep(seconds)
    stop.set()
    for thread in workers:
        thread.join(timeout=5)
    elapsed = max(time.perf_counter() - started, 1e-6)
    total_bytes = sum(counts)
    if total_bytes <= 0:
        return None
    return {
        "gbps": round(total_bytes / elapsed / 1e9, 1),
        "method": "threaded_memcpy_v1",
        "seconds": round(elapsed, 2),
        "threads": threads,
        "chunk_bytes": chunk_bytes,
    }


def build_profile(*, seconds: float = 2.0, no_bench: bool = False) -> dict[str, Any]:
    cpu = _cpu_name()
    ram = _total_ram_bytes()
    if ram is None:
        raise RuntimeError("Could not determine total RAM; pass hardware manually instead.")
    acc = detect_accelerator(cpu)
    notes: list[str] = []
    bandwidth = None
    if no_bench:
        notes.append("Bandwidth benchmark skipped with --no-bench.")
    elif acc["kind"] == "discrete":
        notes.append(
            "Discrete GPU bandwidth is not measured by the helper; the API uses its "
            "curated device table when it recognizes the GPU."
        )
    else:
        try:
            bandwidth = benchmark_memory(seconds)
        except Exception as exc:  # pragma: no cover - platform dependent
            notes.append(f"Bandwidth benchmark failed: {type(exc).__name__}.")
            bandwidth = None
        if bandwidth is None:
            notes.append(
                "No bandwidth measurement was produced "
                "(numpy missing, allocation failure, or benchmark error)."
            )

    return {
        "v": CODE_VERSION,
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": f"omnirun-helper/{HELPER_VERSION}",
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "cpu": cpu,
        "cores": _cores(),
        "ram": int(ram),
        "acc": acc,
        "bw": bandwidth,
        "notes": notes,
    }


def encode_code(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw, 9)
    crc = zlib.crc32(compressed) & 0xFFFFFFFF
    token = base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")
    code = f"{CODE_PREFIX}{token}.{crc:08x}"
    if len(code) > MAX_CODE_LENGTH:
        raise RuntimeError("Generated hardware code is unexpectedly long.")
    return code


def _gib(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"{value / GIB:.1f} GiB"


def print_summary(payload: dict[str, Any], code: str) -> None:
    acc = payload["acc"]
    print("OmniRun hardware profile")
    print(f"  CPU:         {payload['cpu']} ({payload['cores']} physical cores)")
    print(f"  RAM:         {_gib(payload['ram'])}")
    acc_line = f"{acc['name']} ({acc['kind']})"
    if acc.get("vram"):
        acc_line += f", {_gib(acc['vram'])} VRAM"
    print(f"  Accelerator: {acc_line}")
    bw = payload.get("bw")
    if bw:
        print(
            f"  Bandwidth:   {bw['gbps']} GB/s measured "
            f"({bw['method']}, {bw['threads']} threads, {bw['seconds']}s)"
        )
    elif acc["kind"] == "discrete":
        print("  Bandwidth:   not measured for discrete GPU; API uses its device table")
    else:
        print("  Bandwidth:   not measured")
    print()
    print("Paste this code into OmniRun:")
    print(code)
    for note in payload.get("notes", []):
        print(f"\nNote: {note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect hardware and emit an OmniRun code.")
    parser.add_argument("--seconds", type=float, default=2.0, help="benchmark duration (default 2)")
    parser.add_argument("--no-bench", action="store_true", help="skip the bandwidth benchmark")
    parser.add_argument("--json", action="store_true", help="print profile JSON instead of a code")
    parser.add_argument("--code-only", action="store_true", help="print only the code")
    args = parser.parse_args(argv)

    try:
        payload = build_profile(seconds=args.seconds, no_bench=args.no_bench)
        code = encode_code(payload)
    except Exception as exc:
        print(f"OmniRun helper error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.code_only:
        print(code)
        return 0
    print_summary(payload, code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
