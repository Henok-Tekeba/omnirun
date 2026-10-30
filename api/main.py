from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.finder import run_finder
from api.rate_limit import RateLimiter, ceil_retry_after
from api.schemas import (
    SCHEMA_VERSION,
    CacheInfo,
    CheckRequest,
    CheckResponse,
    DeviceEntry,
    DevicesResponse,
    ErrorResponse,
    FindRequest,
    FindResponse,
    SchemaResponse,
)
from api.service import build_response, error_response, resolve_hardware
from api.settings import Settings
from core import __version__
from core.artifacts import discover_artifacts
from core.cache import DiskCache
from core.errors import OmniRunError
from core.estimate import estimate_memory
from core.hardware import load_device_table
from core.hf_client import HFClient
from core.inspect.model import inspect_model
from core.speed import estimate_llm_speed
from core.support import build_support_claim, load_support_matrix
from core.verdict import decide_verdict
from core.verified import build_verified_claim, load_verified_runs

logger = logging.getLogger("omnirun.api")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex)


def _token_scope(token: str | None) -> str:
    if not token:
        return "anon"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _result_cache_key(request: CheckRequest, settings: Settings, matrix_updated: str | None) -> str:
    token = request.hf_token.get_secret_value() if request.hf_token else None
    payload = {
        "schema": SCHEMA_VERSION,
        "endpoint": settings.hf_endpoint,
        "model": request.model.strip().lower(),
        "hardware": request.hardware.model_dump(mode="json"),
        "context": request.context,
        "batch": request.batch,
        "token_scope": _token_scope(token),
        "support_updated": matrix_updated,
        "artifacts": 2,
        "sweep": 2,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    device_table = load_device_table(settings.data_dir / "devices.yaml")
    support_matrix = load_support_matrix(settings.data_dir / "support_matrix.yaml")
    verified_runs = load_verified_runs(settings.data_dir / "verified_runs.json")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        created = False
        if getattr(app.state, "hf_client", None) is None:
            app.state.hf_client = HFClient(
                endpoint=settings.hf_endpoint,
                cache=DiskCache(settings.cache_dir / "hf"),
                max_attempts=settings.hf_max_attempts,
                max_concurrent=settings.hf_max_concurrent,
            )
            created = True
        yield
        if created:
            await app.state.hf_client.close()

    app = FastAPI(
        title="OmniRun API",
        version=__version__,
        description=(
            "Hugging Face model preflight without weight downloads. "
            "FITS, SUPPORTED, and VERIFIED are reported separately."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.device_table = device_table
    app.state.support_matrix = support_matrix
    app.state.verified_runs = verified_runs
    app.state.result_cache = DiskCache(settings.cache_dir / "results")
    app.state.rate_limiter = RateLimiter(
        per_minute=settings.rate_limit_per_minute,
        burst=settings.rate_limit_burst,
    )
    app.state.check_semaphore = asyncio.Semaphore(settings.max_concurrent_checks)
    app.state.hf_client = None

    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["POST", "GET", "OPTIONS"],
            allow_headers=["content-type"],
            expose_headers=["X-Request-ID", "Retry-After"],
        )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(OmniRunError)
    async def omnirun_error_handler(request: Request, exc: OmniRunError) -> JSONResponse:
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is None:
            retry_after = exc.details.get("retry_after_seconds")
        payload = error_response(
            request_id=_request_id(request),
            code=exc.code,
            message=exc.message,
            status=exc.status_code,
            hint=exc.hint,
            retryable=exc.retryable,
            retry_after_seconds=retry_after,
            details=dict(exc.details),
        )
        headers: dict[str, str] = {}
        if retry_after is not None:
            headers["Retry-After"] = str(ceil_retry_after(float(retry_after)))
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        payload = error_response(
            request_id=_request_id(request),
            code="validation_error",
            message="The request body does not match the OmniRun schema.",
            status=422,
            hint="Fetch GET /schema for the request contract.",
            details={"errors": errors},
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error request_id=%s", _request_id(request))
        payload = error_response(
            request_id=_request_id(request),
            code="internal_error",
            message="OmniRun hit an unexpected internal error.",
            status=500,
            retryable=False,
        )
        return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "schema_version": SCHEMA_VERSION}

    @app.get("/schema", response_model=SchemaResponse)
    async def schema() -> SchemaResponse:
        return SchemaResponse(
            schema_version=SCHEMA_VERSION,
            request=CheckRequest.model_json_schema(),
            response=CheckResponse.model_json_schema(),
            error=ErrorResponse.model_json_schema(),
        )

    @app.get("/devices", response_model=DevicesResponse)
    async def devices() -> DevicesResponse:
        """The curated manual hardware profiles, for the frontend picker.

        This is a read-only view of data/devices.yaml. It is not a measurement:
        every entry is labelled with its source and used at MEDIUM confidence.
        """
        return DevicesResponse(
            schema_version=SCHEMA_VERSION,
            devices=[
                DeviceEntry(
                    id=spec.id,
                    name=spec.name,
                    vendor=spec.vendor,
                    kind=spec.kind.value,  # type: ignore[arg-type]
                    bandwidth_gbps=spec.bandwidth_gbps,
                    vram_gib=spec.vram_gib,
                    ram_options_gib=list(spec.ram_options_gib),
                    default_ram_gib=spec.default_ram_gib,
                    source=spec.source,
                    notes=spec.notes,
                )
                for spec in device_table.devices.values()
            ],
        )

    @app.get("/health")
    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/find",
        response_model=FindResponse,
        responses={
            400: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    async def find(payload: FindRequest, request: Request) -> FindResponse:
        client_host = request.client.host if request.client else "unknown"
        retry_after = request.app.state.rate_limiter.check(client_host)
        if retry_after is not None:
            raise OmniRunError(
                "rate_limited",
                "Too many preflight requests from this client.",
                status_code=429,
                retryable=True,
                hint="Wait and retry; the limit is per client IP per minute.",
                details={"retry_after_seconds": retry_after},
            )

        client = request.app.state.hf_client
        if client is None:
            raise OmniRunError(
                "service_not_ready",
                "The Hugging Face client is not ready.",
                status_code=503,
                retryable=True,
            )

        try:
            async with asyncio.timeout(settings.find_timeout_seconds):
                async with request.app.state.check_semaphore:
                    return await run_finder(
                        client,
                        payload,
                        request_id=_request_id(request),
                        device_table=device_table,
                        support_matrix=support_matrix,
                        verified_runs=verified_runs,
                    )
        except TimeoutError as exc:
            raise OmniRunError(
                "find_timeout",
                "The model search exceeded its time budget.",
                status_code=504,
                retryable=True,
                hint="Try a narrower query or a smaller limit.",
            ) from exc

    @app.post(
        "/check",
        response_model=CheckResponse,
        responses={
            400: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    async def check(payload: CheckRequest, request: Request) -> CheckResponse:
        client_host = request.client.host if request.client else "unknown"
        retry_after = request.app.state.rate_limiter.check(client_host)
        if retry_after is not None:
            raise OmniRunError(
                "rate_limited",
                "Too many preflight requests from this client.",
                status_code=429,
                retryable=True,
                hint="Wait and retry; the limit is per client IP per minute.",
                details={"retry_after_seconds": retry_after},
            )

        cache_key = _result_cache_key(payload, settings, support_matrix.updated)
        if settings.enable_result_cache:
            cached = request.app.state.result_cache.get(cache_key)
            if cached is not None:
                response = CheckResponse.model_validate(cached.value)
                response.cache = CacheInfo(
                    model_info_cached=response.cache.model_info_cached,
                    model_info_stale=response.cache.model_info_stale,
                    result_cache_hit=True,
                    result_age_seconds=round(time.time() - cached.created_at, 3),
                )
                return response

        client = request.app.state.hf_client
        if client is None:
            raise OmniRunError(
                "service_not_ready",
                "The Hugging Face client is not ready.",
                status_code=503,
                retryable=True,
            )

        token = payload.hf_token.get_secret_value() if payload.hf_token else None
        try:
            async with asyncio.timeout(settings.check_timeout_seconds):
                async with request.app.state.check_semaphore:
                    hardware = resolve_hardware(payload, device_table)
                    inspection = await inspect_model(client, payload.model, token=token)
                    artifacts = discover_artifacts(inspection.repo)
                    memory = estimate_memory(
                        inspection,
                        context=payload.context,
                        batch=payload.batch,
                    )
                    support = build_support_claim(inspection, support_matrix)
                    verified = build_verified_claim(inspection, hardware, verified_runs)
                    speed = estimate_llm_speed(
                        inspection,
                        memory,
                        hardware,
                        batch=payload.batch,
                    )
                    result = decide_verdict(
                        inspection=inspection,
                        memory=memory,
                        hardware=hardware,
                        support=support,
                        verified=verified,
                        context=payload.context,
                        batch=payload.batch,
                        model_class_supported=inspection.is_llm,
                    )
                    response = build_response(
                        request=payload,
                        request_id=_request_id(request),
                        inspection=inspection,
                        hardware=hardware,
                        memory=memory,
                        speed=speed,
                        support=support,
                        verified=verified,
                        result=result,
                        artifacts=artifacts,
                        cache_info=CacheInfo(
                            model_info_cached=inspection.repo.cache_hit,
                            model_info_stale=inspection.repo.cache_stale,
                            result_cache_hit=False,
                            result_age_seconds=None,
                        ),
                    )
        except TimeoutError as exc:
            raise OmniRunError(
                "check_timeout",
                "The preflight exceeded its time budget.",
                status_code=504,
                retryable=True,
                hint="Retry, or increase OMNIRUN_CHECK_TIMEOUT_SECONDS if your network is slow.",
            ) from exc

        if settings.enable_result_cache and settings.result_cache_ttl_seconds > 0:
            request.app.state.result_cache.set(
                cache_key,
                response.model_dump(mode="json"),
                ttl_seconds=settings.result_cache_ttl_seconds,
            )
        return response

    return app


app = create_app()
