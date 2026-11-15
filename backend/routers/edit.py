import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from pydantic import BaseModel

from backend.services.credentials import store as credential_store
from backend.services.guardrail import enforce_guardrail
from backend.services.providers import (
    SUPPORTED_PROVIDERS,
    ProviderError,
    ProviderNotConfigured,
    get_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/edit", tags=["Edit"])


class EditResponse(BaseModel):
    success: bool
    edited_text: str | None = None
    error: str | None = None


@router.post("/text", response_model=EditResponse)
async def edit_text(
    text: Annotated[str, Form(max_length=50000)],
    instruction: Annotated[str, Form(max_length=500)],
    provider: Annotated[str, Form()] = "openai",
):
    """Run a text-only edit pass using the selected LLM provider."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_provider",
                "message": f"Provider must be one of {SUPPORTED_PROVIDERS}, got '{provider}'.",
            },
        )

    enforce_guardrail(instruction)

    try:
        provider_instance = get_provider(provider, credential_store)
    except ProviderNotConfigured:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_not_configured",
                "message": f"'{provider}' is not configured. Add its credentials via the settings modal.",
            },
        )

    try:
        edited = await asyncio.wait_for(
            provider_instance.edit_text(text, instruction), timeout=60
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"code": "provider_timeout", "message": f"{provider} timed out after 60s."},
        )
    except ProviderError as e:
        logger.error(f"{provider} returned {e.status_code}: {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code, "message": e.message},
        )
    except Exception as e:
        logger.error(f"Edit failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"code": "edit_failed", "message": str(e)},
        )

    return EditResponse(success=True, edited_text=edited, error=None)
