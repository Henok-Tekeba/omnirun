"""Parse the two user inputs we accept: a Hugging Face URL or a repo id.

The parser is deliberately strict and offline. It does not resolve aliases or
hit the network; the HF client does that. Rejecting weird input early keeps the
range-request code from having to defend against path traversal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from urllib.parse import unquote, urlsplit

from core.errors import InputError

_ALLOWED_HOSTS = {"huggingface.co", "www.huggingface.co", "hf.co"}
_UNSUPPORTED_FIRST_SEGMENTS = {"datasets", "spaces"}
_IGNORED_FIRST_SEGMENTS = {"models"}

_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_REVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class ModelInput:
    """A normalized reference to an HF model repo.

    ``revision`` is only set when a tree/blob URL contained one. The API always
    resolves the repo to a commit SHA before reading files.
    """

    repo_id: str
    revision: str | None = None
    source_url: str | None = None
    was_url: bool = False
    original: str = ""

    @property
    def display_name(self) -> str:
        return self.repo_id


def _fail(message: str, *, code: str = "invalid_model_input", hint: str | None = None) -> None:
    raise InputError(message, code=code, hint=hint)


def _validate_component(component: str, *, kind: str) -> str:
    if not component or not _COMPONENT_RE.fullmatch(component):
        _fail(
            f"Invalid {kind} {component!r}.",
            hint=(
                "Use a Hugging Face repo id such as 'org/model-name'. Names may contain "
                "letters, digits, dots, underscores and hyphens."
            ),
        )
    if component in {".", ".."} or component.endswith(".git"):
        _fail(f"Invalid {kind} {component!r}.")
    return component


def _decode_segment(segment: str) -> str:
    decoded = unquote(segment)
    if "/" in decoded or "\\" in decoded or _CONTROL_RE.search(decoded):
        _fail("URL path contains an invalid encoded character.")
    if decoded in {".", ".."}:
        _fail("URL path traversal is not allowed.")
    return decoded


def _validate_revision(revision: str) -> str:
    if not _REVISION_RE.fullmatch(revision):
        _fail(
            "Unsupported revision in URL.",
            hint=(
                "Use a commit SHA, tag, or simple branch name. Branch names containing "
                "'/' are not supported in v1."
            ),
        )
    return revision


def _parse_repo_path(segments: list[str], *, from_url: bool) -> tuple[str, str | None]:
    if not segments:
        _fail("No model repo id found.")

    first = segments[0].lower()
    if first in _UNSUPPORTED_FIRST_SEGMENTS:
        _fail(
            "OmniRun v1 only supports model repositories, not datasets or Spaces.",
            code="unsupported_hf_resource",
            hint="Open the model page on huggingface.co and paste that URL or repo id.",
        )
    if first in _IGNORED_FIRST_SEGMENTS:
        segments = segments[1:]
        if not segments:
            _fail("No model repo id found.")

    if len(segments) < 2:
        if from_url:
            _fail(
                "Hugging Face model URLs must include an owner and a model name.",
                hint="Example: https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct",
            )
        # Legacy single-component repo ids such as 'bert-base-uncased' exist.
        return _validate_component(segments[0], kind="repo name"), None

    owner = _validate_component(segments[0], kind="owner")
    name = _validate_component(segments[1], kind="model name")
    revision: str | None = None

    if len(segments) > 2:
        if segments[2] not in {"tree", "blob"}:
            _fail(
                "Unexpected path in Hugging Face URL.",
                hint=(
                    "Paste a model page URL such as "
                    "https://huggingface.co/org/model, or a repo id such as 'org/model'."
                ),
            )
        if len(segments) < 4:
            _fail("The tree/blob URL is missing a revision.")
        revision = _validate_revision(_decode_segment(segments[3]))
        # Remaining path segments are a file/directory inside the repo. They do
        # not affect model identity, but the API does not use them in v1.
        if len(segments) > 4:
            # A tree path is ambiguous: 'tree/feature/foo' could mean branch
            # 'feature' + directory 'foo', or branch 'feature/foo'. v1 refuses
            # that ambiguity; blob paths are unambiguous enough for our purpose.
            if segments[2] == "tree":
                _fail(
                    "Tree URLs with a path after the revision are ambiguous in v1.",
                    hint="Paste the model page URL or repo id instead.",
                )
            for segment in segments[4:]:
                _decode_segment(segment)

    repo_id = f"{owner}/{name}"
    if len(repo_id) > 200:
        _fail("Repo id is too long.")
    return repo_id, revision


def parse_model_input(raw: str) -> ModelInput:
    """Parse a URL or repo id into a :class:`ModelInput`.

    Supported examples::

        HuggingFaceTB/SmolLM2-135M-Instruct
        https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct
        https://hf.co/org/model/tree/main
        huggingface.co/org/model/blob/main/config.json
        bert-base-uncased

    Dataset and Space URLs are rejected with a specific error code.
    """

    if not isinstance(raw, str):
        _fail("Model must be a string containing a URL or repo id.")

    original = raw
    value = raw.strip()
    if not value:
        _fail("Model is required.", hint="Paste a Hugging Face URL or a repo id.")
    if len(value) > 512:
        _fail("Model input is too long.")
    if _CONTROL_RE.search(value):
        _fail("Model input contains control characters.")
    if any(ch.isspace() for ch in value):
        _fail(
            "Model input contains whitespace.",
            hint="Paste a single URL or repo id with no spaces.",
        )

    has_scheme = "://" in value
    if has_scheme:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https":
            _fail("Only https:// Hugging Face URLs are accepted.")
        host = (parsed.hostname or "").lower()
        if host not in _ALLOWED_HOSTS:
            _fail(
                f"Unsupported URL host {host!r}.",
                hint="Only huggingface.co, www.huggingface.co, and hf.co URLs are accepted.",
            )
        if parsed.port is not None:
            _fail("URLs with explicit ports are not accepted.")
        if parsed.username or parsed.password:
            _fail("URLs with credentials are not accepted; use the hf_token field instead.")
        segments = [_decode_segment(s) for s in parsed.path.split("/") if s]
        repo_id, revision = _parse_repo_path(segments, from_url=True)
        return ModelInput(
            repo_id=repo_id,
            revision=revision,
            source_url=value,
            was_url=True,
            original=original,
        )

    # Be forgiving when a user pastes a URL without a scheme.
    lowered = value.lower()
    for host in _ALLOWED_HOSTS:
        if lowered == host or lowered.startswith(host + "/"):
            parsed = parse_model_input(f"https://{value}")
            # Preserve exactly what the user pasted, while source_url records
            # the normalized https URL actually used.
            return replace(parsed, original=original)

    if "/" not in value:
        # One-component legacy repo id.
        repo_id = _validate_component(value, kind="repo name")
        return ModelInput(repo_id=repo_id, original=original)

    parts = value.split("/")
    if len(parts) == 3 and parts[0].lower() in _IGNORED_FIRST_SEGMENTS:
        parts = parts[1:]
    if len(parts) != 2:
        _fail(
            "Expected a repo id with one slash, such as 'org/model'.",
            hint="Paste the full Hugging Face model URL if the id is ambiguous.",
        )
    repo_id, revision = _parse_repo_path(parts, from_url=False)
    return ModelInput(repo_id=repo_id, revision=revision, original=original)
