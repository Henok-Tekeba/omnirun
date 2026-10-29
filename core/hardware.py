"""Hardware profiles from the helper code, manual device table, or unknown input.

The three input paths and their confidence:
- helper code: measured on the user's machine (highest);
- manual pick: curated device table + user RAM (medium);
- CPU-only/unknown: conservative defaults (lowest).

The helper code is unsigned. It has a version, CRC, strict size limits, and
server-side clamping; that protects against corruption and absurd values, not
against a user deliberately lying about their machine.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from core.errors import InputError
from core.inspect.types import Confidence

GIB = 1024**3
MIB = 1024**2

# Documented, named assumption. macOS does not expose one universal number; the
# GPU wired limit varies with OS version, RAM size, and other apps. 75% is a
# deliberately conservative planning fraction, not an OS query.
APPLE_SILICON_USABLE_MEMORY_FRACTION = 0.75
CPU_USABLE_MEMORY_FRACTION = 0.80
DISCRETE_VRAM_RESERVE_BYTES = 512 * MIB
DEFAULT_CPU_BANDWIDTH_GBPS = 25.0

HELPER_CODE_PREFIX = "OR1."
HELPER_CODE_VERSION = 1
MAX_HELPER_CODE_LENGTH = 4096
MAX_HELPER_PAYLOAD_BYTES = 16 * 1024
MAX_COMPRESSED_BYTES = 8 * 1024
MAX_FUTURE_SKEW = timedelta(days=1)
MAX_MEASUREMENT_AGE = timedelta(days=3650)

_DEVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")


class HardwareSource(StrEnum):
    HELPER = "helper"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class DeviceKind(StrEnum):
    UNIFIED = "unified"
    DISCRETE = "discrete"
    CPU = "cpu"


@dataclass(frozen=True, slots=True)
class DeviceSpec:
    id: str
    name: str
    vendor: str
    kind: DeviceKind
    bandwidth_gbps: float
    vram_gib: float | None
    ram_options_gib: tuple[float, ...]
    default_ram_gib: float | None
    source: str
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceTable:
    devices: Mapping[str, DeviceSpec]
    by_name: Mapping[str, str]

    def get(self, device_id: str) -> DeviceSpec | None:
        return self.devices.get(device_id.strip().lower())

    def find_by_name(self, name: str) -> DeviceSpec | None:
        query = _normalize_name(name)
        if not query:
            return None
        device_id = self.by_name.get(query)
        if device_id:
            return self.devices[device_id]
        # Conservative fuzzy match: only a whole-token-ish containment, and
        # never match a laptop GPU to a desktop entry with the same number.
        if "laptop" in query or "mobile" in query:
            return None
        candidates = [
            spec
            for spec in self.devices.values()
            if query in _normalize_name(spec.name) or _normalize_name(spec.name) in query
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda spec: len(spec.name), reverse=True)
        return candidates[0]


@dataclass(frozen=True, slots=True)
class HelperProfile:
    version: int
    measured_at: datetime | None
    os_name: str | None
    arch: str | None
    cpu: str | None
    cores: int | None
    ram_bytes: int
    acc_kind: DeviceKind
    acc_name: str
    acc_vendor: str | None
    vram_bytes: int | None
    bandwidth_gbps: float | None
    bandwidth_method: str | None
    bandwidth_seconds: float | None
    bandwidth_threads: int | None
    tool: str | None


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    source: HardwareSource
    kind: DeviceKind
    device_id: str | None
    device_name: str
    vendor: str | None
    system_ram_bytes: int | None
    device_memory_bytes: int | None
    memory_budget_bytes: int | None
    bandwidth_gbps: float | None
    bandwidth_source: str  # helper_measured | device_table | assumed | unknown
    memory_source: str  # helper_measured | device_table | user | assumed | unknown
    confidence: Confidence
    memory_confidence: Confidence
    bandwidth_confidence: Confidence
    apple_fraction: float | None
    measured_at: datetime | None
    cpu: str | None
    cores: int | None
    notes: tuple[str, ...] = ()
    helper_tool: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "kind": self.kind.value,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "vendor": self.vendor,
            "system_ram_bytes": self.system_ram_bytes,
            "device_memory_bytes": self.device_memory_bytes,
            "memory_budget_bytes": self.memory_budget_bytes,
            "bandwidth_gbps": self.bandwidth_gbps,
            "bandwidth_source": self.bandwidth_source,
            "memory_source": self.memory_source,
            "confidence": self.confidence.value,
            "memory_confidence": self.memory_confidence.value,
            "bandwidth_confidence": self.bandwidth_confidence.value,
            "apple_fraction": self.apple_fraction,
            "measured_at": self.measured_at.isoformat() if self.measured_at else None,
            "cpu": self.cpu,
            "cores": self.cores,
            "notes": list(self.notes),
            "helper_tool": self.helper_tool,
        }


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _default_devices_path() -> Path:
    override = os.environ.get("OMNIRUN_DATA_DIR")
    if override:
        return Path(override).expanduser() / "devices.yaml"
    return Path(__file__).resolve().parents[1] / "data" / "devices.yaml"


def load_device_table(path: str | Path | None = None) -> DeviceTable:
    source_path = Path(path) if path is not None else _default_devices_path()
    try:
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(
            "The device table is missing.",
            code="device_table_missing",
            hint=f"Expected {source_path}.",
        ) from exc
    except yaml.YAMLError as exc:
        raise InputError(
            "The device table is not valid YAML.",
            code="device_table_invalid",
            hint=str(exc),
        ) from exc

    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise InputError(
            "The device table has an unsupported version.",
            code="device_table_invalid",
        )
    items = raw.get("devices")
    if not isinstance(items, list) or not items:
        raise InputError("The device table has no devices.", code="device_table_invalid")

    devices: dict[str, DeviceSpec] = {}
    by_name: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise InputError("A device table entry is not an object.", code="device_table_invalid")
        device_id = str(item.get("id", "")).strip().lower()
        if not _DEVICE_ID_RE.fullmatch(device_id):
            raise InputError(
                f"Invalid device id {device_id!r}.", code="device_table_invalid"
            )
        if device_id in devices:
            raise InputError(
                f"Duplicate device id {device_id!r}.", code="device_table_invalid"
            )
        try:
            kind = DeviceKind(str(item["kind"]))
            name = str(item["name"]).strip()
            vendor = str(item["vendor"]).strip().lower()
            bandwidth = float(item["bandwidth_gbps"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InputError(
                f"Device {device_id!r} is missing required fields.",
                code="device_table_invalid",
            ) from exc
        if not name or bandwidth <= 0 or bandwidth > 10_000:
            raise InputError(
                f"Device {device_id!r} has invalid values.", code="device_table_invalid"
            )
        vram_raw = item.get("vram_gib")
        vram = float(vram_raw) if vram_raw is not None else None
        if kind == DeviceKind.DISCRETE and (vram is None or vram <= 0):
            raise InputError(
                f"Discrete device {device_id!r} needs vram_gib.", code="device_table_invalid"
            )
        if kind != DeviceKind.DISCRETE and vram is not None:
            raise InputError(
                f"Only discrete devices may set vram_gib ({device_id!r}).",
                code="device_table_invalid",
            )
        options_raw = item.get("ram_options_gib") or []
        if not isinstance(options_raw, list):
            raise InputError(
                f"Device {device_id!r} ram_options_gib must be a list.",
                code="device_table_invalid",
            )
        options = tuple(float(value) for value in options_raw)
        default_ram = item.get("default_ram_gib")
        devices[device_id] = DeviceSpec(
            id=device_id,
            name=name,
            vendor=vendor,
            kind=kind,
            bandwidth_gbps=bandwidth,
            vram_gib=vram,
            ram_options_gib=options,
            default_ram_gib=float(default_ram) if default_ram is not None else None,
            source=str(item.get("source", "unspecified")),
            notes=str(item["notes"]) if item.get("notes") else None,
        )
        normalized = _normalize_name(name)
        if normalized in by_name:
            raise InputError(
                f"Duplicate normalized device name {name!r}.", code="device_table_invalid"
            )
        by_name[normalized] = device_id

    return DeviceTable(devices=devices, by_name=by_name)


def _encode(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(raw) > MAX_HELPER_PAYLOAD_BYTES:
        raise ValueError("helper payload too large")
    compressed = zlib.compress(raw, 9)
    if len(compressed) > MAX_COMPRESSED_BYTES:
        raise ValueError("helper payload does not compress small enough")
    crc = zlib.crc32(compressed) & 0xFFFFFFFF
    token = base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")
    return f"{HELPER_CODE_PREFIX}{token}.{crc:08x}"


def encode_hardware_code(payload: Mapping[str, Any]) -> str:
    """Encode a helper payload. Used by tests and tooling, not the API hot path."""
    return _encode(payload)


def decode_hardware_code(code: str) -> HelperProfile:
    if not isinstance(code, str):
        raise InputError(
            "Hardware code must be a string.",
            code="invalid_hardware_code",
            hint="Generate a code with helper/omnirun_helper.py.",
        )
    code = code.strip()
    if not code:
        raise InputError("Hardware code is empty.", code="invalid_hardware_code")
    if len(code) > MAX_HELPER_CODE_LENGTH:
        raise InputError("Hardware code is too long.", code="invalid_hardware_code")
    if not code.startswith(HELPER_CODE_PREFIX):
        raise InputError(
            "Hardware code has an unsupported prefix.",
            code="invalid_hardware_code",
            hint=f"Codes start with {HELPER_CODE_PREFIX!r}.",
        )
    body = code[len(HELPER_CODE_PREFIX) :]
    try:
        token, crc_text = body.rsplit(".", 1)
    except ValueError as exc:
        raise InputError(
            "Hardware code is missing its checksum.",
            code="invalid_hardware_code",
        ) from exc
    if not re.fullmatch(r"[0-9a-fA-F]{8}", crc_text):
        raise InputError("Hardware code checksum is malformed.", code="invalid_hardware_code")
    try:
        padded = token + "=" * (-len(token) % 4)
        compressed = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, binascii.Error, UnicodeEncodeError) as exc:
        raise InputError(
            "Hardware code payload is not valid base64url.",
            code="invalid_hardware_code",
        ) from exc
    if not compressed or len(compressed) > MAX_COMPRESSED_BYTES:
        raise InputError("Hardware code payload has an invalid size.", code="invalid_hardware_code")
    expected_crc = int(crc_text, 16)
    actual_crc = zlib.crc32(compressed) & 0xFFFFFFFF
    if expected_crc != actual_crc:
        raise InputError(
            "Hardware code checksum does not match.",
            code="invalid_hardware_code",
            hint="Regenerate the code; do not edit it by hand.",
        )
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_HELPER_PAYLOAD_BYTES + 1)
        if len(raw) > MAX_HELPER_PAYLOAD_BYTES or decompressor.unconsumed_tail:
            raise ValueError
        raw += decompressor.flush()
    except (zlib.error, ValueError) as exc:
        raise InputError(
            "Hardware code payload could not be decompressed.",
            code="invalid_hardware_code",
        ) from exc
    if len(raw) > MAX_HELPER_PAYLOAD_BYTES:
        raise InputError("Hardware code payload is too large.", code="invalid_hardware_code")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InputError(
            "Hardware code payload is not valid JSON.",
            code="invalid_hardware_code",
        ) from exc
    if not isinstance(payload, dict):
        raise InputError("Hardware code payload is not an object.", code="invalid_hardware_code")
    return _profile_from_payload(payload)


def _int_bytes(value: Any, *, minimum: int, maximum: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(
            "Hardware profile contains a non-numeric size.",
            code="invalid_hardware_code",
        )
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise InputError(
            "Hardware profile contains an out-of-range size.",
            code="invalid_hardware_code",
        )
    return round(value)


def _string(value: Any, *, field_name: str, max_length: int = 200) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputError(
            f"Hardware profile field {field_name!r} is not a string.",
            code="invalid_hardware_code",
        )
    value = value.strip()
    if len(value) > max_length or any(ord(ch) < 32 for ch in value):
        raise InputError(
            f"Hardware profile field {field_name!r} is invalid.",
            code="invalid_hardware_code",
        )
    return value or None


def _profile_from_payload(payload: Mapping[str, Any]) -> HelperProfile:
    if payload.get("v") != HELPER_CODE_VERSION:
        raise InputError(
            "Hardware code version is not supported by this API.",
            code="unsupported_hardware_code_version",
            hint="Regenerate the code with the current helper.",
        )
    ram_bytes = _int_bytes(payload.get("ram"), minimum=256 * MIB, maximum=4 * 1024**4)
    if ram_bytes is None:
        raise InputError("Hardware code does not include RAM.", code="invalid_hardware_code")

    acc = payload.get("acc")
    if not isinstance(acc, dict):
        raise InputError("Hardware code has no accelerator record.", code="invalid_hardware_code")
    try:
        acc_kind = DeviceKind(str(acc.get("kind")))
    except ValueError as exc:
        raise InputError(
            "Hardware code has an unknown accelerator kind.",
            code="invalid_hardware_code",
        ) from exc
    acc_name = _string(acc.get("name"), field_name="acc.name", max_length=160)
    if not acc_name:
        raise InputError("Hardware code has no accelerator name.", code="invalid_hardware_code")
    vram_bytes = _int_bytes(
        acc.get("vram"), minimum=128 * MIB, maximum=1024**4
    )
    if acc_kind == DeviceKind.DISCRETE and vram_bytes is None:
        raise InputError(
            "Discrete GPU code has no VRAM size.",
            code="invalid_hardware_code",
        )
    if acc_kind != DeviceKind.DISCRETE and vram_bytes is not None:
        raise InputError(
            "Unified/CPU code must not report VRAM.",
            code="invalid_hardware_code",
        )

    bw = payload.get("bw")
    if bw is not None and not isinstance(bw, dict):
        raise InputError("Hardware code bandwidth record is invalid.", code="invalid_hardware_code")
    bw_gbps = None
    bw_method = None
    bw_seconds = None
    bw_threads = None
    if isinstance(bw, dict):
        raw_gbps = bw.get("gbps")
        if raw_gbps is not None:
            if isinstance(raw_gbps, bool) or not isinstance(raw_gbps, (int, float)):
                raise InputError(
                    "Hardware bandwidth is not numeric.",
                    code="invalid_hardware_code",
                )
            if not math.isfinite(raw_gbps) or not (0.1 <= raw_gbps <= 5000):
                raise InputError(
                    "Hardware bandwidth is out of range.",
                    code="invalid_hardware_code",
                )
            bw_gbps = float(raw_gbps)
        bw_method = _string(bw.get("method"), field_name="bw.method", max_length=80)
        raw_seconds = bw.get("seconds")
        if (
            isinstance(raw_seconds, (int, float))
            and not isinstance(raw_seconds, bool)
            and math.isfinite(raw_seconds)
            and 0.01 <= raw_seconds <= 60
        ):
            bw_seconds = float(raw_seconds)
        raw_threads = bw.get("threads")
        if (
            isinstance(raw_threads, int)
            and not isinstance(raw_threads, bool)
            and 1 <= raw_threads <= 1024
        ):
            bw_threads = raw_threads

    measured_at = None
    raw_ts = payload.get("ts")
    if raw_ts is not None:
        if not isinstance(raw_ts, str):
            raise InputError("Hardware timestamp is invalid.", code="invalid_hardware_code")
        try:
            measured_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError(
                "Hardware timestamp is invalid.",
                code="invalid_hardware_code",
            ) from exc
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if measured_at > now + MAX_FUTURE_SKEW:
            raise InputError("Hardware timestamp is in the future.", code="invalid_hardware_code")
        if measured_at < now - MAX_MEASUREMENT_AGE:
            measured_at = None

    cores = payload.get("cores")
    if isinstance(cores, bool) or (cores is not None and not isinstance(cores, int)):
        raise InputError("Hardware core count is invalid.", code="invalid_hardware_code")
    if isinstance(cores, int) and not (1 <= cores <= 4096):
        raise InputError("Hardware core count is out of range.", code="invalid_hardware_code")

    return HelperProfile(
        version=HELPER_CODE_VERSION,
        measured_at=measured_at,
        os_name=_string(payload.get("os"), field_name="os", max_length=120),
        arch=_string(payload.get("arch"), field_name="arch", max_length=40),
        cpu=_string(payload.get("cpu"), field_name="cpu", max_length=160),
        cores=cores,
        ram_bytes=ram_bytes,
        acc_kind=acc_kind,
        acc_name=acc_name,
        acc_vendor=_string(acc.get("vendor"), field_name="acc.vendor", max_length=80),
        vram_bytes=vram_bytes,
        bandwidth_gbps=bw_gbps,
        bandwidth_method=bw_method,
        bandwidth_seconds=bw_seconds,
        bandwidth_threads=bw_threads,
        tool=_string(payload.get("tool"), field_name="tool", max_length=80),
    )


def _budget(kind: DeviceKind, memory_bytes: int | None, *, apple: bool) -> int | None:
    if memory_bytes is None:
        return None
    if kind == DeviceKind.DISCRETE:
        return max(0, memory_bytes - DISCRETE_VRAM_RESERVE_BYTES)
    if kind == DeviceKind.UNIFIED:
        return round(memory_bytes * APPLE_SILICON_USABLE_MEMORY_FRACTION)
    return round(memory_bytes * CPU_USABLE_MEMORY_FRACTION)


def profile_from_helper(code: str, table: DeviceTable | None = None) -> HardwareProfile:
    table = table or load_device_table()
    helper = decode_hardware_code(code)
    notes: list[str] = [
        "Helper values are self-reported and unsigned; confidence means 'measured by "
        "the helper on this machine', not cryptographic attestation."
    ]
    match = table.find_by_name(helper.acc_name)
    if helper.acc_kind == DeviceKind.UNIFIED:
        memory_bytes = helper.ram_bytes
        budget = _budget(DeviceKind.UNIFIED, memory_bytes, apple=True)
        bandwidth = helper.bandwidth_gbps
        bandwidth_source = "helper_measured" if bandwidth is not None else "unknown"
        bandwidth_confidence = Confidence.HIGH if bandwidth is not None else Confidence.LOW
        if bandwidth is None:
            notes.append("The helper did not produce a bandwidth measurement.")
        notes.append(
            f"Usable unified memory is {APPLE_SILICON_USABLE_MEMORY_FRACTION:.0%} of total "
            "RAM; this is a documented assumption, not an OS query."
        )
        if match is not None:
            notes.append(f"Helper accelerator matched the device table entry {match.id!r}.")
        return HardwareProfile(
            source=HardwareSource.HELPER,
            kind=DeviceKind.UNIFIED,
            device_id=match.id if match else None,
            device_name=helper.acc_name,
            vendor=helper.acc_vendor or (match.vendor if match else None),
            system_ram_bytes=helper.ram_bytes,
            device_memory_bytes=memory_bytes,
            memory_budget_bytes=budget,
            bandwidth_gbps=bandwidth,
            bandwidth_source=bandwidth_source,
            memory_source="helper_measured",
            confidence=Confidence.HIGH,
            memory_confidence=Confidence.HIGH,
            bandwidth_confidence=bandwidth_confidence,
            apple_fraction=APPLE_SILICON_USABLE_MEMORY_FRACTION,
            measured_at=helper.measured_at,
            cpu=helper.cpu,
            cores=helper.cores,
            notes=tuple(notes),
            helper_tool=helper.tool,
        )

    if helper.acc_kind == DeviceKind.DISCRETE:
        memory_bytes = helper.vram_bytes
        budget = _budget(DeviceKind.DISCRETE, memory_bytes, apple=False)
        bandwidth = helper.bandwidth_gbps
        bandwidth_source = "helper_measured"
        bandwidth_confidence = Confidence.HIGH
        if bandwidth is None:
            if match is not None:
                bandwidth = match.bandwidth_gbps
                bandwidth_source = "device_table"
                bandwidth_confidence = Confidence.MEDIUM
                notes.append(
                    f"VRAM is measured; bandwidth is the device-table value for {match.name!r}, "
                    "because the helper cannot benchmark a discrete GPU without CUDA/torch."
                )
            else:
                bandwidth = None
                bandwidth_source = "unknown"
                bandwidth_confidence = Confidence.LOW
                notes.append(
                    "VRAM is measured, but the helper could not match this GPU to a "
                    "bandwidth entry. Speed will be UNKNOWN rather than guessed."
                )
        return HardwareProfile(
            source=HardwareSource.HELPER,
            kind=DeviceKind.DISCRETE,
            device_id=match.id if match else None,
            device_name=helper.acc_name,
            vendor=helper.acc_vendor or (match.vendor if match else None),
            system_ram_bytes=helper.ram_bytes,
            device_memory_bytes=memory_bytes,
            memory_budget_bytes=budget,
            bandwidth_gbps=bandwidth,
            bandwidth_source=bandwidth_source,
            memory_source="helper_measured",
            confidence=Confidence.HIGH,
            memory_confidence=Confidence.HIGH,
            bandwidth_confidence=bandwidth_confidence,
            apple_fraction=None,
            measured_at=helper.measured_at,
            cpu=helper.cpu,
            cores=helper.cores,
            notes=tuple(notes),
            helper_tool=helper.tool,
        )

    memory_bytes = helper.ram_bytes
    budget = _budget(DeviceKind.CPU, memory_bytes, apple=False)
    bandwidth = helper.bandwidth_gbps
    if bandwidth is None:
        bandwidth = DEFAULT_CPU_BANDWIDTH_GBPS
        bandwidth_source = "assumed"
        bandwidth_confidence = Confidence.LOW
        notes.append("No CPU bandwidth measurement; using the conservative default.")
    else:
        bandwidth_source = "helper_measured"
        bandwidth_confidence = Confidence.HIGH
    return HardwareProfile(
        source=HardwareSource.HELPER,
        kind=DeviceKind.CPU,
        device_id="cpu-generic" if match and match.kind == DeviceKind.CPU else None,
        device_name=helper.acc_name,
        vendor=helper.acc_vendor or "generic",
        system_ram_bytes=helper.ram_bytes,
        device_memory_bytes=memory_bytes,
        memory_budget_bytes=budget,
        bandwidth_gbps=bandwidth,
        bandwidth_source=bandwidth_source,
        memory_source="helper_measured",
        confidence=Confidence.HIGH,
        memory_confidence=Confidence.HIGH,
        bandwidth_confidence=bandwidth_confidence,
        apple_fraction=None,
        measured_at=helper.measured_at,
        cpu=helper.cpu,
        cores=helper.cores,
        notes=tuple(notes),
        helper_tool=helper.tool,
    )


def _ram_bytes(ram_gib: float | None, *, required: bool, device_name: str) -> int | None:
    if ram_gib is None:
        if required:
            raise InputError(
                f"RAM is required for {device_name}.",
                code="ram_required",
                hint="Pass ram_gib from the machine's total RAM.",
            )
        return None
    if isinstance(ram_gib, bool) or not isinstance(ram_gib, (int, float)):
        raise InputError("ram_gib must be a number.", code="invalid_ram")
    if not math.isfinite(ram_gib) or not (1 <= ram_gib <= 4096):
        raise InputError(
            "ram_gib is outside the supported range.",
            code="invalid_ram",
            hint="Pass total RAM in GiB (1..4096).",
        )
    return round(ram_gib * GIB)


def profile_from_manual(
    device_id: str,
    *,
    ram_gib: float | None = None,
    table: DeviceTable | None = None,
) -> HardwareProfile:
    table = table or load_device_table()
    spec = table.get(device_id)
    if spec is None:
        raise InputError(
            f"Unknown device id {device_id!r}.",
            code="unknown_device",
            hint="Pick an id from data/devices.yaml, or use the helper code.",
        )
    requires_ram = spec.kind in {DeviceKind.UNIFIED, DeviceKind.CPU}
    ram_bytes = _ram_bytes(ram_gib, required=requires_ram, device_name=spec.name)
    if spec.kind == DeviceKind.DISCRETE:
        memory_bytes = round((spec.vram_gib or 0) * GIB)
        device_memory = memory_bytes
        budget = _budget(DeviceKind.DISCRETE, device_memory, apple=False)
    else:
        memory_bytes = ram_bytes
        device_memory = ram_bytes
        budget = _budget(spec.kind, device_memory, apple=spec.kind == DeviceKind.UNIFIED)
    notes = [
        "Manual profile: curated device-table bandwidth, not a measurement on this machine."
    ]
    if spec.notes:
        notes.append(spec.notes)
    if spec.kind == DeviceKind.UNIFIED:
        notes.append(
            f"Usable unified memory is {APPLE_SILICON_USABLE_MEMORY_FRACTION:.0%} of total "
            "RAM; this is a documented assumption."
        )
    if (
        requires_ram
        and ram_bytes is not None
        and spec.ram_options_gib
        and ram_gib not in spec.ram_options_gib
    ):
        notes.append(
            f"RAM {ram_gib:g} GiB is not one of the curated options "
            f"({', '.join(f'{v:g}' for v in spec.ram_options_gib)} GiB); using the user value."
        )
    confidence = Confidence.MEDIUM
    memory_confidence = Confidence.MEDIUM
    bandwidth_confidence = Confidence.MEDIUM
    if spec.kind == DeviceKind.CPU:
        confidence = Confidence.LOW
        memory_confidence = Confidence.LOW
        bandwidth_confidence = Confidence.LOW
        notes.append("CPU-only manual profiles use the lowest confidence.")
    return HardwareProfile(
        source=HardwareSource.MANUAL,
        kind=spec.kind,
        device_id=spec.id,
        device_name=spec.name,
        vendor=spec.vendor,
        system_ram_bytes=ram_bytes,
        device_memory_bytes=device_memory,
        memory_budget_bytes=budget,
        bandwidth_gbps=spec.bandwidth_gbps,
        bandwidth_source="device_table",
        memory_source="device_table" if spec.kind == DeviceKind.DISCRETE else "user",
        confidence=confidence,
        memory_confidence=memory_confidence,
        bandwidth_confidence=bandwidth_confidence,
        apple_fraction=(
            APPLE_SILICON_USABLE_MEMORY_FRACTION if spec.kind == DeviceKind.UNIFIED else None
        ),
        measured_at=None,
        cpu=None,
        cores=None,
        notes=tuple(notes),
    )


def profile_from_unknown(*, ram_gib: float | None = None) -> HardwareProfile:
    ram_bytes = _ram_bytes(ram_gib, required=False, device_name="unknown hardware")
    if ram_bytes is None:
        return HardwareProfile(
            source=HardwareSource.UNKNOWN,
            kind=DeviceKind.CPU,
            device_id=None,
            device_name="Unknown hardware",
            vendor=None,
            system_ram_bytes=None,
            device_memory_bytes=None,
            memory_budget_bytes=None,
            bandwidth_gbps=DEFAULT_CPU_BANDWIDTH_GBPS,
            bandwidth_source="assumed",
            memory_source="unknown",
            confidence=Confidence.LOW,
            memory_confidence=Confidence.LOW,
            bandwidth_confidence=Confidence.LOW,
            apple_fraction=None,
            measured_at=None,
            cpu=None,
            cores=None,
            notes=(
                "No hardware data and no RAM; memory fit is UNKNOWN rather than guessed.",
            ),
        )
    return HardwareProfile(
        source=HardwareSource.UNKNOWN,
        kind=DeviceKind.CPU,
        device_id=None,
        device_name="Unknown CPU-only system",
        vendor=None,
        system_ram_bytes=ram_bytes,
        device_memory_bytes=ram_bytes,
        memory_budget_bytes=_budget(DeviceKind.CPU, ram_bytes, apple=False),
        bandwidth_gbps=DEFAULT_CPU_BANDWIDTH_GBPS,
        bandwidth_source="assumed",
        memory_source="user",
        confidence=Confidence.LOW,
        memory_confidence=Confidence.LOW,
        bandwidth_confidence=Confidence.LOW,
        apple_fraction=None,
        measured_at=None,
        cpu=None,
        cores=None,
        notes=(
            "Conservative CPU-only defaults: 80% of RAM and 25 GB/s.",
            "This is the lowest-confidence hardware source; use the helper for speed estimates.",
        ),
    )
