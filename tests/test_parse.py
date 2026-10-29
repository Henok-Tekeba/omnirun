from __future__ import annotations

import pytest

from core.errors import InputError
from core.parse import parse_model_input


@pytest.mark.parametrize(
    ("raw", "repo_id", "revision", "was_url"),
    [
        ("HuggingFaceTB/SmolLM2-135M-Instruct", "HuggingFaceTB/SmolLM2-135M-Instruct", None, False),
        ("bert-base-uncased", "bert-base-uncased", None, False),
        (
            "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct",
            "HuggingFaceTB/SmolLM2-135M-Instruct",
            None,
            True,
        ),
        (
            "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/tree/main",
            "HuggingFaceTB/SmolLM2-135M-Instruct",
            "main",
            True,
        ),
        (
            "https://hf.co/org/model/blob/main/config.json",
            "org/model",
            "main",
            True,
        ),
        (
            "huggingface.co/org/model",
            "org/model",
            None,
            True,
        ),
        (
            "hf.co/org/model/tree/v1.0",
            "org/model",
            "v1.0",
            True,
        ),
        (
            "https://www.huggingface.co/org/model/",
            "org/model",
            None,
            True,
        ),
        (
            "https://huggingface.co/models/org/model",
            "org/model",
            None,
            True,
        ),
        (
            "https://huggingface.co/org/model?foo=bar#section",
            "org/model",
            None,
            True,
        ),
        ("models/org/model", "org/model", None, False),
        (
            "https://huggingface.co/org/model/blob/abc123/config.json",
            "org/model",
            "abc123",
            True,
        ),
        (
            "https://huggingface.co/org/model/tree/main/",
            "org/model",
            "main",
            True,
        ),
    ],
)
def test_parse_valid(raw: str, repo_id: str, revision: str | None, was_url: bool) -> None:
    parsed = parse_model_input(raw)
    assert parsed.repo_id == repo_id
    assert parsed.revision == revision
    assert parsed.was_url is was_url
    assert parsed.original == raw


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", "invalid_model_input"),
        ("   ", "invalid_model_input"),
        ("org /model", "invalid_model_input"),
        ("https://huggingface.co/datasets/org/data", "unsupported_hf_resource"),
        ("https://huggingface.co/spaces/org/app", "unsupported_hf_resource"),
        ("https://example.com/org/model", "invalid_model_input"),
        ("http://huggingface.co/org/model", "invalid_model_input"),
        ("https://huggingface.co.evil.com/org/model", "invalid_model_input"),
        ("https://huggingface.co:443/org/model", "invalid_model_input"),
        ("https://user:pass@huggingface.co/org/model", "invalid_model_input"),
        ("https://huggingface.co/org", "invalid_model_input"),
        ("org/model/extra", "invalid_model_input"),
        ("../model", "invalid_model_input"),
        ("org/model?x=1", "invalid_model_input"),
        ("https://huggingface.co/org/model/tree", "invalid_model_input"),
        ("https://huggingface.co/org/model/tree/main/../../x", "invalid_model_input"),
        ("https://huggingface.co/org/model/blob/main/%2e%2e/x", "invalid_model_input"),
        ("https://huggingface.co/org/model/tree/feature/foo", "invalid_model_input"),
        ("a" * 100 + "/model", "invalid_model_input"),
        ("org/mo\ndel", "invalid_model_input"),
    ],
)
def test_parse_invalid(raw: str, code: str) -> None:
    with pytest.raises(InputError) as exc:
        parse_model_input(raw)
    assert exc.value.code == code


def test_parse_non_string() -> None:
    with pytest.raises(InputError):
        parse_model_input(123)  # type: ignore[arg-type]


def test_parse_strips_outer_whitespace() -> None:
    parsed = parse_model_input("  org/model  ")
    assert parsed.repo_id == "org/model"
    assert parsed.original == "  org/model  "
