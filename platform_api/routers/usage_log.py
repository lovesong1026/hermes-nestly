"""Proxy + aggregate third-party usage logs for the SPA Usage Center."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from gateway.web.platform.store import PlatformStore
from platform_api.deps import get_current_user_id, get_store, get_vault
from platform_api.services import usage_log as svc

router = APIRouter(prefix="/usage-log", tags=["usage-log"])


def _decrypt_upstream_key(user_id: str) -> str:
    store = get_store()
    if not isinstance(store, PlatformStore):
        raise HTTPException(status_code=503, detail="platform store required")
    enc = store.get_user_upstream_key_enc(user_id)
    if not enc:
        raise HTTPException(status_code=403, detail="upstream key not bound")
    try:
        return get_vault().decrypt(enc)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="key storage error") from exc


def _parse_days(days: int) -> int:
    if days not in svc.ALLOWED_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"days must be one of {sorted(svc.ALLOWED_DAYS)}",
        )
    return days


@router.get("/overview")
def usage_log_overview(
    days: int = Query(default=7),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    days = _parse_days(days)
    api_key = _decrypt_upstream_key(user_id)
    try:
        with httpx.Client(timeout=20.0) as client:
            return svc.build_overview(api_key=api_key, days=days, http_client=client)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/logs")
def usage_log_logs(
    days: int = Query(default=7),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    days = _parse_days(days)
    api_key = _decrypt_upstream_key(user_id)
    try:
        with httpx.Client(timeout=20.0) as client:
            return svc.build_logs_page(
                api_key=api_key,
                days=days,
                page=page,
                per_page=per_page,
                http_client=client,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
