"""Shared new-api admin API helpers (token usage, logs)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from gateway.web.upstream_key import normalize_new_api_base_url

logger = logging.getLogger("hermes.platform.new_api")

# Re-export for billing + usage_log USD conversion (same as log quota divisor).
DEFAULT_QUOTA_PER_USD = 500_000.0


def admin_base_url() -> str:
    """Canonical new-api root (no trailing /v1) for ``/api/*`` admin routes."""
    return normalize_new_api_base_url(os.environ.get("NEW_API_BASE_URL", ""))


def quota_per_usd() -> float:
    raw = (os.environ.get("USAGE_LOG_QUOTA_PER_USD") or "").strip()
    if not raw:
        return DEFAULT_QUOTA_PER_USD
    try:
        val = float(raw)
    except ValueError:
        return DEFAULT_QUOTA_PER_USD
    return val if val > 0 else DEFAULT_QUOTA_PER_USD


def quota_to_usd(quota: float, *, per_usd: Optional[float] = None) -> float:
    div = per_usd if per_usd is not None else quota_per_usd()
    if div <= 0:
        return 0.0
    return float(quota) / div


def _parse_token_usage_payload(payload: Any) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    # Some deployments return fields at the top level.
    if any(k in payload for k in ("total_available", "unlimited_quota", "remain_quota")):
        return payload
    return None


def fetch_token_usage(
    client: httpx.Client,
    *,
    api_key: str,
    timeout: float = 15.0,
) -> Optional[dict[str, Any]]:
    """GET /api/usage/token — returns parsed data dict or None on failure."""
    base = admin_base_url()
    if not base:
        logger.warning("NEW_API_BASE_URL not configured — balance unavailable")
        return None
    try:
        resp = client.get(
            f"{base}/api/usage/token",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        logger.warning("token usage fetch failed: %s", exc)
        return None

    if resp.status_code != 200:
        logger.warning("token usage HTTP %s", resp.status_code)
        return None

    data = _parse_token_usage_payload(resp.json())
    if not data:
        logger.warning("token usage unexpected payload shape")
        return None
    return data


def token_balance_usd(data: dict[str, Any]) -> tuple[Optional[float], bool]:
    """Return (balance_usd, unlimited). balance_usd is None when unlimited/unavailable."""
    unlimited = bool(data.get("unlimited_quota"))
    if unlimited:
        return None, True
    raw = data.get("total_available")
    if raw is None:
        raw = data.get("remain_quota")
    try:
        available = float(raw or 0)
    except (TypeError, ValueError):
        available = 0.0
    return quota_to_usd(available), False
