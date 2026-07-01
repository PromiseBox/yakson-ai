from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger("uvicorn.error")


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _coarsen_age(value: Any) -> str:
    if isinstance(value, bool):
        return "[REDACTED_AGE]"
    if isinstance(value, int):
        return f"{value // 10 * 10}s"
    return "[REDACTED_AGE]"


def mask_pii(data: Any) -> Any:
    """Mask person-identifying values before LangSmith tracing.

    Drug names and alert text are preserved because they are needed for
    medication-safety evaluation. Person names and exact ages are coarsened.
    """
    if isinstance(data, list):
        return [mask_pii(item) for item in data]
    if not isinstance(data, Mapping):
        return data

    masked: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"nickname", "displayName", "display_name", "name"}:
            masked[key] = "[REDACTED_NAME]"
        elif key in {"age", "ageYears", "age_years"} and isinstance(value, int):
            masked[key] = _coarsen_age(value)
        else:
            masked[key] = mask_pii(value)
    return masked


def is_langsmith_enabled() -> bool:
    return _truthy_env("LANGSMITH_TRACING") and bool(os.getenv("LANGSMITH_API_KEY"))


def get_langsmith_client():
    if not is_langsmith_enabled():
        return None

    try:
        from langsmith import Client
    except Exception as exc:
        logger.warning("langsmith_tracing=false reason=import_failed error=%s", exc)
        return None

    client_kwargs: dict[str, Any] = dict(
        hide_inputs=mask_pii,
        hide_outputs=mask_pii,
    )
    endpoint = os.getenv("LANGSMITH_ENDPOINT")
    if endpoint:
        client_kwargs["api_url"] = endpoint

    return Client(**client_kwargs)


def maybe_wrap_openai_client(openai_client):
    if not is_langsmith_enabled():
        return openai_client

    get_langsmith_client()
    try:
        from langsmith.wrappers import wrap_openai
    except Exception as exc:
        logger.warning("langsmith_tracing=false reason=wrap_import_failed error=%s", exc)
        return openai_client

    try:
        return wrap_openai(openai_client)
    except Exception as exc:
        logger.warning("langsmith_tracing=false reason=wrap_failed error=%s", exc)
        return openai_client
