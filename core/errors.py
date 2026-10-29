from __future__ import annotations

from typing import Any


class OmniRunError(Exception):
    """Base error with a stable, machine-readable code.

    ``status_code`` is the HTTP status the API should use. Core never imports
    FastAPI; it only carries an integer.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class InputError(OmniRunError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_input",
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            hint=hint,
            status_code=422,
            details=details,
        )


class HFError(OmniRunError):
    """An error talking to the Hugging Face Hub.

    ``upstream_status`` is the status returned by HF (if any). It is separate
    from the status OmniRun returns to its own caller.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 502,
        upstream_status: int | None = None,
        hint: str | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            hint=hint,
            status_code=status_code,
            retryable=retryable,
            details=details,
        )
        self.upstream_status = upstream_status
        self.retry_after = retry_after
