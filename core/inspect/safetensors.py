"""Safetensors inspection using HTTP range requests only.

The safetensors format is:
    8 bytes: little-endian u64 header length N
    N bytes: UTF-8 JSON header (tensor name -> dtype/shape/data_offsets)
    rest:    tensor payload

We read the 8 bytes and the JSON header. The tensor payload is never fetched.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.errors import InspectionError
from core.hf_client import HFClient, HFRepo
from core.inspect.config import MoEConfig, QuantizationConfig
from core.inspect.types import Confidence, Issue

MAX_HEADER_BYTES = 32 * 1024 * 1024
MAX_TENSORS = 200_000
MAX_SHARDS = 512
MAX_DIMS = 8
MAX_ELEMENTS = 10**15

_SAFETENSORS_DTYPE_BYTES: dict[str, int] = {
    "BOOL": 1,
    "U8": 1,
    "I8": 1,
    "F8_E4M3": 1,
    "F8_E5M2": 1,
    "F8_E8M0": 1,
    "I16": 2,
    "U16": 2,
    "F16": 2,
    "BF16": 2,
    "I32": 4,
    "U32": 4,
    "F32": 4,
    "I64": 8,
    "U64": 8,
    "F64": 8,
}

_EXPERT_RE = re.compile(r"(?:^|\.)experts\.(\d+)\.")
_LAYER_RE = re.compile(r"(?:^|\.)layers\.(\d+)\.")
_BLOCK_RE = re.compile(r"(?:^|\.)h\.(\d+)\.")


@dataclass(frozen=True, slots=True)
class TensorInfo:
    name: str
    dtype: str
    shape: tuple[int, ...]
    data_start: int
    data_end: int
    numel: int
    nbytes: int


@dataclass(frozen=True, slots=True)
class SafetensorsHeader:
    tensors: tuple[TensorInfo, ...]
    metadata: Mapping[str, str]
    header_size: int
    data_size: int | None
    file_size: int | None
    weight_bytes: int
    params: int
    dtype_bytes: Mapping[str, int]
    issues: tuple[Issue, ...]
    confidence: Confidence
    weight_bytes_exact: bool = True

    @property
    def tensor_count(self) -> int:
        return len(self.tensors)

    @property
    def total_file_bytes(self) -> int | None:
        if self.file_size is None:
            return None
        return self.header_size + 8 + (self.data_size or 0)


@dataclass(frozen=True, slots=True)
class ShardSelection:
    shards: tuple[str, ...]
    index_file: str | None
    index_total_size: int | None
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True)
class ExpertStats:
    num_layers_detected: int
    routed_expert_bytes: int
    non_expert_bytes: int
    active_weight_bytes: int
    experts_per_layer: tuple[int, ...]
    confidence: Confidence
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SafetensorsInspection:
    format: str
    weight_bytes: int
    weight_bytes_exact: bool
    params: int | None
    stored_elements: int
    tensor_count: int
    shard_count: int
    header_bytes: int
    dtype_bytes: Mapping[str, int]
    shards: tuple[str, ...]
    index_total_size: int | None
    expert_stats: ExpertStats | None
    confidence: Confidence
    issues: tuple[Issue, ...]


def _fail(message: str, *, code: str = "invalid_safetensors_header") -> None:
    raise InspectionError(message, code=code, status_code=502)


def _safe_numel(shape: tuple[int, ...], name: str) -> int:
    if len(shape) > MAX_DIMS:
        _fail(f"Tensor {name!r} has too many dimensions.", code="safetensors_tensor_limit")
    numel = 1
    for dim in shape:
        if dim < 0:
            _fail(f"Tensor {name!r} has a negative dimension.", code="invalid_safetensors_header")
        if dim and numel > MAX_ELEMENTS // dim:
            _fail(f"Tensor {name!r} is too large to inspect.", code="safetensors_tensor_limit")
        numel *= dim
    return numel


def parse_safetensors_header(
    raw_header: bytes | str,
    *,
    header_size: int,
    file_size: int | None,
    quantization: QuantizationConfig | None = None,
) -> SafetensorsHeader:
    """Validate a safetensors JSON header and compute exact weight bytes."""
    if header_size <= 0 or header_size > MAX_HEADER_BYTES:
        _fail("Safetensors header length is outside the allowed range.")
    raw_bytes = raw_header.encode("utf-8") if isinstance(raw_header, str) else raw_header
    if len(raw_bytes) != header_size:
        _fail(
            "Safetensors header length does not match the declared length.",
            code="invalid_safetensors_header",
        )
    if file_size is not None and file_size < 8 + header_size:
        _fail("Safetensors header is larger than the file.")
    try:
        payload = json.loads(raw_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InspectionError(
            "The safetensors header is not valid JSON.",
            code="invalid_safetensors_header",
            status_code=502,
        ) from exc
    if not isinstance(payload, dict):
        _fail("The safetensors header must be a JSON object.")

    metadata: dict[str, str] = {}
    raw_metadata = payload.get("__metadata__")
    if isinstance(raw_metadata, dict):
        metadata = {str(k): str(v) for k, v in raw_metadata.items()}

    tensor_items = [(k, v) for k, v in payload.items() if k != "__metadata__"]
    if len(tensor_items) > MAX_TENSORS:
        _fail(
            f"The safetensors header declares too many tensors ({len(tensor_items)}).",
            code="safetensors_tensor_limit",
        )

    tensors: list[TensorInfo] = []
    issues: list[Issue] = []
    dtype_bytes: dict[str, int] = defaultdict(int)
    params = 0
    spans: list[tuple[int, int]] = []
    unknown_dtypes: set[str] = set()
    mismatch_count = 0

    for name, entry in tensor_items:
        if not isinstance(name, str) or not name:
            _fail("The safetensors header contains an invalid tensor name.")
        if not isinstance(entry, dict):
            _fail(f"Tensor {name!r} is not an object.")
        dtype_raw = entry.get("dtype")
        if not isinstance(dtype_raw, str) or not dtype_raw:
            _fail(f"Tensor {name!r} has no dtype.")
        dtype = dtype_raw.upper()
        shape_raw = entry.get("shape")
        if not isinstance(shape_raw, list) or any(
            not isinstance(dim, int) or isinstance(dim, bool) or dim < 0
            for dim in shape_raw
        ):
            _fail(f"Tensor {name!r} has an invalid shape.")
        shape = tuple(shape_raw)
        offsets_raw = entry.get("data_offsets")
        if (
            not isinstance(offsets_raw, list)
            or len(offsets_raw) != 2
            or any(
                not isinstance(offset, int) or isinstance(offset, bool) or offset < 0
                for offset in offsets_raw
            )
        ):
            _fail(f"Tensor {name!r} has invalid data_offsets.")
        start, end = int(offsets_raw[0]), int(offsets_raw[1])
        if end < start:
            _fail(f"Tensor {name!r} has reversed data_offsets.")
        numel = _safe_numel(shape, name)
        nbytes = end - start
        itemsize = _SAFETENSORS_DTYPE_BYTES.get(dtype)
        if itemsize is None:
            unknown_dtypes.add(dtype)
        else:
            expected = numel * itemsize
            if expected != nbytes:
                mismatch_count += 1
                issues.append(
                    Issue(
                        "tensor_span_mismatch",
                        f"Tensor {name!r} declares {nbytes} bytes but its shape/dtype "
                        f"imply {expected}.",
                        "warning",
                    )
                )
        spans.append((start, end))
        dtype_bytes[dtype] += nbytes
        params += numel
        tensors.append(
            TensorInfo(
                name=name,
                dtype=dtype,
                shape=shape,
                data_start=start,
                data_end=end,
                numel=numel,
                nbytes=nbytes,
            )
        )

    data_size = None
    if file_size is not None:
        data_size = file_size - 8 - header_size
        if data_size < 0:
            _fail("Safetensors data section has a negative size.")

    max_end = max((end for _, end in spans), default=0)
    if data_size is not None and max_end > data_size:
        _fail(
            "A safetensors tensor extends past the end of the file.",
            code="safetensors_bounds_error",
        )
    if data_size is None:
        data_size = max_end
        issues.append(
            Issue(
                "unknown_file_size",
                "The HF file list did not provide a size, so the safetensors "
                "payload was validated against its declared offsets only.",
                "warning",
            )
        )

    # Overlap detection. Safetensors should have disjoint spans; a malicious
    # header could otherwise double-count bytes.
    ordered = sorted((start, end) for start, end in spans if start != end)
    overlap = False
    previous_end = -1
    for start, end in ordered:
        if start < previous_end:
            overlap = True
            break
        previous_end = end
    if overlap:
        issues.append(
            Issue(
                "overlapping_safetensors_tensors",
                "Safetensors tensor spans overlap; weight bytes are not trustworthy.",
                "risk",
            )
        )

    declared_spans = sum(end - start for start, end in spans)
    weight_bytes = declared_spans
    exact = not unknown_dtypes and mismatch_count == 0 and not overlap

    if unknown_dtypes:
        issues.append(
            Issue(
                "unknown_safetensors_dtype",
                "Unknown safetensors dtype(s): " + ", ".join(sorted(unknown_dtypes)),
                "risk",
            )
        )
    if data_size > max_end:
        issues.append(
            Issue(
                "trailing_safetensors_bytes",
                f"{data_size - max_end} bytes are outside declared tensor spans; "
                "they are not counted as weights.",
                "info",
            )
        )
    if quantization and quantization.is_quantized:
        issues.append(
            Issue(
                "packed_weight_params",
                "The checkpoint is quantized/packed; stored element counts are not "
                "the model's logical parameter count.",
                "info",
            )
        )

    confidence = Confidence.HIGH
    if issues:
        if any(issue.severity == "risk" for issue in issues):
            confidence = Confidence.LOW
        elif not exact or any(issue.severity == "warning" for issue in issues):
            confidence = Confidence.MEDIUM

    return SafetensorsHeader(
        tensors=tuple(tensors),
        metadata=metadata,
        header_size=header_size,
        data_size=data_size,
        file_size=file_size,
        weight_bytes=weight_bytes,
        params=params,
        dtype_bytes=dict(dtype_bytes),
        issues=tuple(issues),
        confidence=confidence,
        weight_bytes_exact=exact,
    )


async def read_safetensors_header(
    client: HFClient,
    repo: HFRepo,
    path: str,
    *,
    token: str | None = None,
    quantization: QuantizationConfig | None = None,
) -> SafetensorsHeader:
    file_meta = repo.file(path)
    file_size = file_meta.size if file_meta is not None else None
    prefix = await client.get_range(repo, path, 0, 7, token=token)
    if len(prefix) != 8:
        _fail(f"Could not read the safetensors length prefix of {path}.")
    header_size = int.from_bytes(prefix, "little")
    if header_size <= 0:
        _fail(f"{path} declares an empty safetensors header.")
    if header_size > MAX_HEADER_BYTES:
        _fail(
            f"{path} declares a {header_size}-byte header, above OmniRun's cap.",
            code="safetensors_header_too_large",
        )
    if file_size is not None and header_size > file_size - 8:
        _fail(f"{path} declares a header larger than the file.")

    raw = await client.get_range(repo, path, 8, 8 + header_size - 1, token=token)
    return parse_safetensors_header(
        raw,
        header_size=header_size,
        file_size=file_size,
        quantization=quantization,
    )


async def find_safetensors_shards(
    client: HFClient,
    repo: HFRepo,
    *,
    token: str | None = None,
) -> ShardSelection | None:
    """Choose the model safetensors files, handling the HF shard index."""
    index_path = "model.safetensors.index.json"
    if repo.file(index_path) is not None:
        index = await client.get_json_file(repo, index_path, token=token)
        data = index.data
        if not isinstance(data, dict):
            _fail(f"{index_path} is not a JSON object.")
        weight_map = data.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            _fail(f"{index_path} has no weight_map.")
        shards = sorted({str(value) for value in weight_map.values() if isinstance(value, str)})
        if not shards:
            _fail(f"{index_path} does not reference any shards.")
        if len(shards) > MAX_SHARDS:
            _fail(f"{index_path} references too many shards ({len(shards)}).")
        for shard in shards:
            if (
                not shard.endswith(".safetensors")
                or shard.startswith("/")
                or ".." in shard.split("/")
            ):
                _fail(f"{index_path} references an invalid shard path: {shard!r}.")
            if repo.file(shard) is None:
                _fail(
                    f"{index_path} references {shard!r}, but it is not in the repo file list.",
                    code="inconsistent_safetensors_index",
                )
        total_size = None
        metadata = data.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("total_size"), int):
            total_size = metadata["total_size"]
        issues: tuple[Issue, ...] = ()
        if total_size is None:
            issues = (
                Issue(
                    "missing_index_total_size",
                    f"{index_path} has no metadata.total_size; header sums will be used.",
                    "info",
                ),
            )
        return ShardSelection(
            shards=tuple(shards),
            index_file=index_path,
            index_total_size=total_size,
            issues=issues,
        )

    if repo.file("model.safetensors") is not None:
        return ShardSelection(
            shards=("model.safetensors",),
            index_file=None,
            index_total_size=None,
            issues=(),
        )

    candidates = sorted(path for path in repo.filenames() if path.endswith(".safetensors"))
    if len(candidates) == 1:
        return ShardSelection(
            shards=(candidates[0],),
            index_file=None,
            index_total_size=None,
            issues=(),
        )
    if candidates:
        shard_pattern = re.compile(r"(?:^|/)model-\d{5}-of-\d{5}\.safetensors$")
        if all(shard_pattern.search(path) for path in candidates):
            if len(candidates) > MAX_SHARDS:
                _fail(f"Too many safetensors shards ({len(candidates)}).")
            return ShardSelection(
                shards=tuple(candidates),
                index_file=None,
                index_total_size=None,
                issues=(
                    Issue(
                        "safetensors_multiple_without_index",
                        "Multiple sharded safetensors files were found without an index; "
                        "the filename pattern was used.",
                        "warning",
                    ),
                ),
            )
        _fail(
            "Multiple .safetensors files are present but no model.safetensors.index.json "
            "identifies the model shards.",
            code="ambiguous_safetensors",
        )
    return None


def derive_expert_stats(
    headers: tuple[SafetensorsHeader, ...],
    moe: MoEConfig,
) -> ExpertStats | None:
    """Derive routed/active weight bytes from tensor names.

    This is intentionally name-based and conservative. If the repo uses fused
    expert tensors or a naming scheme we do not recognize, we return None and
    the caller must treat MoE speed as unknown.
    """
    by_layer: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    non_expert_bytes = 0
    total_bytes = 0
    detected = 0
    for header in headers:
        for tensor in header.tensors:
            total_bytes += tensor.nbytes
            match = _EXPERT_RE.search(tensor.name)
            if match is None or "shared_expert" in tensor.name:
                non_expert_bytes += tensor.nbytes
                continue
            layer_match = _LAYER_RE.search(tensor.name) or _BLOCK_RE.search(tensor.name)
            layer = int(layer_match.group(1)) if layer_match else 0
            by_layer[layer][int(match.group(1))] += tensor.nbytes
            detected += 1

    if not by_layer:
        return None

    experts_per_layer = tuple(len(experts) for experts in by_layer.values())
    routed_expert_bytes = sum(
        size for experts in by_layer.values() for size in experts.values()
    )
    active_routed = 0.0
    notes: list[str] = []
    uniform = True
    for layer, experts in by_layer.items():
        sizes = list(experts.values())
        if len(sizes) != moe.num_experts:
            uniform = False
            notes.append(
                f"Layer {layer} exposes {len(sizes)} expert tensors, config says "
                f"{moe.num_experts}."
            )
        mean = sum(sizes) / len(sizes)
        if max(sizes, default=0) > mean * 1.01:
            uniform = False
        active_routed += mean * moe.experts_per_token

    active_weight_bytes = round(non_expert_bytes + active_routed)
    confidence = Confidence.HIGH if uniform else Confidence.MEDIUM
    if len(by_layer) < 2:
        confidence = Confidence.LOW
        notes.append("Only one MoE layer was detected; active-weight inference is weak.")
    notes.append(
        f"Active weights = non-expert bytes + mean routed expert size * "
        f"top-{moe.experts_per_token}, per detected layer."
    )
    return ExpertStats(
        num_layers_detected=len(by_layer),
        routed_expert_bytes=routed_expert_bytes,
        non_expert_bytes=non_expert_bytes,
        active_weight_bytes=active_weight_bytes,
        experts_per_layer=experts_per_layer,
        confidence=confidence,
        notes=tuple(notes),
    )


async def inspect_safetensors(
    client: HFClient,
    repo: HFRepo,
    *,
    token: str | None = None,
    quantization: QuantizationConfig | None = None,
    moe: MoEConfig | None = None,
) -> SafetensorsInspection | None:
    selection = await find_safetensors_shards(client, repo, token=token)
    if selection is None:
        return None

    headers = await asyncio.gather(
        *[
            read_safetensors_header(
                client,
                repo,
                shard,
                token=token,
                quantization=quantization,
            )
            for shard in selection.shards
        ]
    )

    total_weight_bytes = sum(header.weight_bytes for header in headers)
    stored_elements = sum(header.params for header in headers)
    tensor_count = sum(header.tensor_count for header in headers)
    header_bytes = sum(header.header_size + 8 for header in headers)
    dtype_bytes: dict[str, int] = defaultdict(int)
    issues: list[Issue] = list(selection.issues)
    for header in headers:
        issues.extend(header.issues)
        for dtype, nbytes in header.dtype_bytes.items():
            dtype_bytes[dtype] += nbytes

    if selection.index_total_size is not None and selection.index_total_size != total_weight_bytes:
        issues.append(
            Issue(
                "safetensors_index_size_mismatch",
                f"Index metadata.total_size={selection.index_total_size} does not match "
                f"the header sum={total_weight_bytes}.",
                "warning",
            )
        )

    exact = all(header.weight_bytes_exact for header in headers)
    confidence = Confidence.lowest(*(header.confidence for header in headers))
    if selection.index_total_size is not None and selection.index_total_size != total_weight_bytes:
        confidence = Confidence.lowest(confidence, Confidence.MEDIUM)

    expert_stats = derive_expert_stats(tuple(headers), moe) if moe else None
    if moe and expert_stats is None:
        issues.append(
            Issue(
                "moe_expert_tensors_not_recognized",
                "The config declares MoE, but expert tensors could not be identified "
                "from their names. Active-parameter speed will be UNKNOWN.",
                "warning",
            )
        )

    params = None if quantization and quantization.is_quantized else stored_elements
    return SafetensorsInspection(
        format="safetensors",
        weight_bytes=total_weight_bytes,
        weight_bytes_exact=exact,
        params=params,
        stored_elements=stored_elements,
        tensor_count=tensor_count,
        shard_count=len(headers),
        header_bytes=header_bytes,
        dtype_bytes=dict(dtype_bytes),
        shards=selection.shards,
        index_total_size=selection.index_total_size,
        expert_stats=expert_stats,
        confidence=confidence,
        issues=tuple(issues),
    )


def estimate_param_count_from_config(config: Any) -> int | None:
    """Rough logical parameter count from config fields.

    Used only when a checkpoint is pickle-only (no tensor shapes) and for
    hypothetical quantization alternatives. It is deliberately conservative:
    returns None rather than guessing when architecture-defining fields are
    missing. The result is labeled LOW confidence by callers.
    """
    layers = getattr(config, "layers", None)
    hidden = getattr(config, "hidden_size", None)
    heads = getattr(config, "attention_heads", None)
    kv_heads = getattr(config, "kv_heads_effective", None)
    head_dim = getattr(config, "head_dim_effective", None)
    vocab = getattr(config, "vocab_size", None)
    intermediate = getattr(config, "intermediate_size", None)
    if not all((layers, hidden, heads, head_dim, vocab)):
        return None

    attn = hidden * (heads * head_dim)  # q
    attn += 2 * hidden * (kv_heads * head_dim) if kv_heads else 0  # k/v
    attn += (heads * head_dim) * hidden  # o

    moe = getattr(config, "moe", None)
    if moe:
        if not moe.moe_intermediate_size:
            return None
        expert_mlp = 3 * hidden * moe.moe_intermediate_size
        shared = 0
        if moe.shared_expert_intermediate_size:
            shared = 3 * hidden * moe.shared_expert_intermediate_size * (moe.shared_experts or 1)
        per_layer = attn + 2 * hidden + shared + moe.num_experts * expert_mlp
    else:
        if not intermediate:
            return None
        per_layer = attn + 2 * hidden + 3 * hidden * intermediate

    tied = getattr(config, "tie_word_embeddings", None)
    lm_head = 0 if tied else vocab * hidden
    total = vocab * hidden + layers * per_layer + hidden + lm_head
    return int(total)


def active_param_count_from_config(config: Any) -> int | None:
    """Rough active-parameter count for MoE speed estimates."""
    total = estimate_param_count_from_config(config)
    moe = getattr(config, "moe", None)
    if total is None or not moe or not moe.moe_intermediate_size:
        return total
    layers = getattr(config, "layers", None)
    hidden = getattr(config, "hidden_size", None)
    if not layers or not hidden:
        return None
    # Remove routed experts from total, then add top-k experts back.
    routed_total = layers * moe.num_experts * 3 * hidden * moe.moe_intermediate_size
    routed_active = (
        layers * moe.experts_per_token * 3 * hidden * moe.moe_intermediate_size
    )
    return int(total - routed_total + routed_active)


__all__ = [
    "MAX_HEADER_BYTES",
    "ExpertStats",
    "SafetensorsHeader",
    "SafetensorsInspection",
    "ShardSelection",
    "active_param_count_from_config",
    "derive_expert_stats",
    "estimate_param_count_from_config",
    "find_safetensors_shards",
    "inspect_safetensors",
    "parse_safetensors_header",
    "read_safetensors_header",
]
