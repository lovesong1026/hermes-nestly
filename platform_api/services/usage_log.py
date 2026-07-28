"""Aggregate third-party usage logs (log.az-ai.icu) for the Usage Center."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger("hermes.platform.usage_log")

ALLOWED_DAYS = frozenset({1, 3, 7, 30, 90})
_MAX_PAGES = 50
_DEFAULT_QUOTA_PER_USD = 500_000.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def quota_per_usd() -> float:
    raw = (os.environ.get("USAGE_LOG_QUOTA_PER_USD") or "").strip()
    if not raw:
        return _DEFAULT_QUOTA_PER_USD
    try:
        val = float(raw)
    except ValueError:
        return _DEFAULT_QUOTA_PER_USD
    return val if val > 0 else _DEFAULT_QUOTA_PER_USD


def log_base_url() -> str:
    base = (os.environ.get("USAGE_LOG_BASE_URL") or "https://log.az-ai.icu").strip()
    return base.rstrip("/")


def quota_to_usd(quota: float, *, per_usd: Optional[float] = None) -> float:
    div = per_usd if per_usd is not None else quota_per_usd()
    if div <= 0:
        return 0.0
    return float(quota) / div


def parse_created_at(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        # Unix seconds
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def window_start(days: int, *, now: Optional[datetime] = None) -> datetime:
    ref = now or _utcnow()
    return ref - timedelta(days=days)


def normalize_row(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    created = parse_created_at(raw.get("created_at"))
    if created is None:
        return None
    model = str(raw.get("model_name") or "").strip() or "unknown"
    try:
        prompt = int(raw.get("prompt_tokens") or 0)
    except (TypeError, ValueError):
        prompt = 0
    try:
        completion = int(raw.get("completion_tokens") or 0)
    except (TypeError, ValueError):
        completion = 0
    try:
        quota = float(raw.get("quota") or 0)
    except (TypeError, ValueError):
        quota = 0.0
    return {
        "id": raw.get("id"),
        "created_at": created,
        "model_name": model,
        "prompt_tokens": max(0, prompt),
        "completion_tokens": max(0, completion),
        "quota": max(0.0, quota),
    }


def fetch_log_pages(
    client: httpx.Client,
    *,
    api_key: str,
    since: datetime,
    max_pages: int = _MAX_PAGES,
) -> list[dict[str, Any]]:
    """Fetch paginated logs until pages exhausted or rows fall before ``since``."""
    base = log_base_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    out: list[dict[str, Any]] = []
    page = 1
    last_page = 1

    while page <= last_page and page <= max_pages:
        resp = client.get(
            f"{base}/api/log",
            params={"page": page},
            headers=headers,
            timeout=20.0,
        )
        if resp.status_code == 401:
            raise PermissionError("upstream log key rejected")
        if resp.status_code != 200:
            raise RuntimeError(f"log upstream HTTP {resp.status_code}: {resp.text[:300]}")

        payload = resp.json()
        if not isinstance(payload, dict):
            raise RuntimeError("unexpected log payload")

        try:
            last_page = int(payload.get("last_page") or page)
        except (TypeError, ValueError):
            last_page = page

        raw_rows = payload.get("data")
        if not isinstance(raw_rows, list):
            raw_rows = []

        page_min: Optional[datetime] = None
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            row = normalize_row(raw)
            if row is None:
                continue
            if page_min is None or row["created_at"] < page_min:
                page_min = row["created_at"]
            if row["created_at"] >= since:
                out.append(row)

        # Upstream is newest-first; if the oldest on this page is already
        # outside the window, older pages won't help.
        if page_min is not None and page_min < since:
            break
        if not raw_rows:
            break
        page += 1

    return out


def fetch_balance_usd(
    client: httpx.Client,
    *,
    api_key: str,
) -> tuple[Optional[float], bool]:
    """Return (balance_usd, unlimited). balance_usd None when unavailable."""
    from platform_api.services.new_api_billing import fetch_token_usage, token_balance_usd

    data = fetch_token_usage(client, api_key=api_key)
    if not data:
        return None, False
    return token_balance_usd(data)


def aggregate_overview(
    rows: list[dict[str, Any]],
    *,
    days: int,
    since: datetime,
    now: datetime,
    balance_usd: Optional[float],
    balance_unlimited: bool,
) -> dict[str, Any]:
    per = quota_per_usd()
    prompt_total = 0
    completion_total = 0
    quota_total = 0.0
    by_model: dict[str, dict[str, Any]] = {}
    daily_map: dict[str, dict[str, Any]] = {}

    # Pre-seed empty days so the chart has a continuous axis.
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).date().isoformat()
        daily_map[day] = {"date": day, "requests": 0, "cost_usd": 0.0, "by_model": {}}

    for row in rows:
        if row["created_at"] < since:
            continue
        day = row["created_at"].date().isoformat()
        model = row["model_name"]
        cost = quota_to_usd(row["quota"], per_usd=per)
        prompt_total += row["prompt_tokens"]
        completion_total += row["completion_tokens"]
        quota_total += row["quota"]

        m = by_model.setdefault(
            model, {"model": model, "requests": 0, "cost_usd": 0.0}
        )
        m["requests"] += 1
        m["cost_usd"] += cost

        if day not in daily_map:
            # Outside pre-seeded range (clock skew) — still record.
            daily_map[day] = {
                "date": day,
                "requests": 0,
                "cost_usd": 0.0,
                "by_model": {},
            }
        d = daily_map[day]
        d["requests"] += 1
        d["cost_usd"] += cost
        d["by_model"][model] = float(d["by_model"].get(model, 0.0)) + cost

    daily = [daily_map[k] for k in sorted(daily_map.keys())]
    # Round money for stable JSON
    for d in daily:
        d["cost_usd"] = round(float(d["cost_usd"]), 6)
        d["by_model"] = {
            k: round(float(v), 6) for k, v in sorted(d["by_model"].items())
        }

    models = sorted(by_model.values(), key=lambda x: (-x["requests"], x["model"]))
    for m in models:
        m["cost_usd"] = round(float(m["cost_usd"]), 6)

    return {
        "days": days,
        "requests": sum(m["requests"] for m in models),
        "cost_usd": round(quota_to_usd(quota_total, per_usd=per), 6),
        "balance_usd": (
            None if balance_unlimited else (
                round(balance_usd, 6) if balance_usd is not None else None
            )
        ),
        "balance_unlimited": balance_unlimited,
        "prompt_tokens": prompt_total,
        "completion_tokens": completion_total,
        "daily": daily,
        "by_model": models,
    }


def build_overview(
    *,
    api_key: str,
    days: int,
    http_client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    if days not in ALLOWED_DAYS:
        raise ValueError(f"days must be one of {sorted(ALLOWED_DAYS)}")
    now = _utcnow()
    since = window_start(days, now=now)

    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=20.0)
    try:
        rows = fetch_log_pages(client, api_key=api_key, since=since)
        balance_usd, unlimited = fetch_balance_usd(client, api_key=api_key)
        return aggregate_overview(
            rows,
            days=days,
            since=since,
            now=now,
            balance_usd=balance_usd,
            balance_unlimited=unlimited,
        )
    finally:
        if owns_client:
            client.close()


def build_logs_page(
    *,
    api_key: str,
    days: int,
    page: int = 1,
    per_page: int = 20,
    http_client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    if days not in ALLOWED_DAYS:
        raise ValueError(f"days must be one of {sorted(ALLOWED_DAYS)}")
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))
    now = _utcnow()
    since = window_start(days, now=now)

    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=20.0)
    try:
        rows = fetch_log_pages(client, api_key=api_key, since=since)
    finally:
        if owns_client:
            client.close()

    # Newest first
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    total = len(rows)
    start = (page - 1) * per_page
    slice_rows = rows[start : start + per_page]
    per = quota_per_usd()
    items = []
    for r in slice_rows:
        items.append(
            {
                "id": r["id"],
                "created_at": r["created_at"].isoformat().replace("+00:00", "Z"),
                "model_name": r["model_name"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "quota": r["quota"],
                "cost_usd": round(quota_to_usd(r["quota"], per_usd=per), 6),
            }
        )
    last_page = max(1, (total + per_page - 1) // per_page) if total else 1
    return {
        "days": days,
        "current_page": page,
        "per_page": per_page,
        "total": total,
        "last_page": last_page,
        "items": items,
    }
