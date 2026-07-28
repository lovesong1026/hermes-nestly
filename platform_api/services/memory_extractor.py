"""Conversation → pending memory extraction (Phase 2).

Disabled by default (``PLATFORM_MEMORY_EXTRACTOR``). When enabled, a post-chat
hook may enqueue LLM extraction that inserts **pending only** Memory Center
rows (never silent permanent save / md projection).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from typing import Any, Optional

logger = logging.getLogger("hermes.platform.memory_extractor")

_EXTRACT_CATEGORIES = frozenset({"profile", "preference", "project"})
_MIN_CONFIDENCE = 0.55
_MAX_HISTORY_MESSAGES = 8
_MAX_ITEMS = 5

_EXTRACT_PROMPT = (
    "You extract durable personal facts worth remembering later.\n"
    "Return ONLY a JSON array (no markdown fences). Each element:\n"
    '{"category":"profile"|"preference"|"project","content":"...","confidence":0.0-1.0,'
    '"raw_excerpt":"optional short quote"}\n'
    "Rules:\n"
    "- Only lasting facts (identity, stable prefs, ongoing projects).\n"
    "- Skip ephemeral task chatter, one-off questions, secrets/passwords.\n"
    "- If nothing worth saving, return [].\n"
    "- Keep content atomic (one fact per item), max 5 items.\n"
)


def extractor_enabled() -> bool:
    return os.environ.get("PLATFORM_MEMORY_EXTRACTOR", "").strip() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _truncate_messages(
    messages: Optional[list[dict[str, Any]]],
) -> list[dict[str, str]]:
    if not messages:
        return []
    trimmed: list[dict[str, str]] = []
    for m in messages[-_MAX_HISTORY_MESSAGES:]:
        role = str(m.get("role") or "").strip()
        if role not in {"user", "assistant", "system"}:
            continue
        content = m.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        trimmed.append({"role": role, "content": content.strip()[:2000]})
    return trimmed


def _parse_llm_json_array(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return []
    # Strip optional ```json fences
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Best-effort: first [...] slice
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _normalize_item(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    cat = str(raw.get("category") or "").strip().lower()
    if cat not in _EXTRACT_CATEGORIES:
        return None
    content = str(raw.get("content") or "").strip()
    if not content:
        return None
    try:
        conf = float(raw.get("confidence", 0.7))
    except (TypeError, ValueError):
        conf = 0.7
    if conf < _MIN_CONFIDENCE:
        return None
    excerpt = raw.get("raw_excerpt")
    excerpt_s = str(excerpt).strip() if excerpt else None
    return {
        "category": cat,
        "content": content[:2000],
        "confidence": max(0.0, min(1.0, conf)),
        "raw_excerpt": (excerpt_s[:500] if excerpt_s else None),
    }


def _skip_if_agent_tool_pending(db, *, workspace_id: str) -> bool:
    """Skip extractor when agent already queued pending via web_memory recently."""
    from datetime import datetime, timedelta, timezone

    from gateway.web.platform.models import MemoryItem
    from sqlalchemy import select

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
    rows = list(
        db.execute(
            select(MemoryItem).where(
                MemoryItem.workspace_id == workspace_id,
                MemoryItem.status == "pending",
                MemoryItem.source == "agent_tool",
                MemoryItem.created_at >= cutoff,
            )
        ).scalars().all()
    )
    return len(rows) > 0


def run_memory_extraction(
    *,
    user_id: str,
    workspace_id: str,
    session_id: str,
    messages: Optional[list[dict[str, Any]]] = None,
    main_runtime: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Run LLM extraction and insert pending rows. Never projects md."""
    from gateway.web.platform.database import session_scope
    from gateway.web.platform.models import Workspace
    from gateway.web.platform.store import PlatformStore
    from gateway.web.user_store_factory import create_user_store
    from platform_api.services import memory_center as mc

    trimmed = _truncate_messages(messages)
    if not trimmed:
        return {"enqueued": False, "reason": "no_messages", "created": 0}

    store = create_user_store()
    if not isinstance(store, PlatformStore):
        return {"enqueued": False, "reason": "no_platform_store", "created": 0}

    # Throttle: skip if web_memory already proposed recently for this workspace
    with session_scope(store._engine) as db:
        if _skip_if_agent_tool_pending(db, workspace_id=workspace_id):
            return {
                "enqueued": False,
                "reason": "agent_tool_pending",
                "created": 0,
            }

    from agent.auxiliary_client import call_llm

    llm_messages = [
        {"role": "system", "content": _EXTRACT_PROMPT},
        {
            "role": "user",
            "content": "Conversation:\n"
            + "\n".join(f"{m['role']}: {m['content']}" for m in trimmed),
        },
    ]

    try:
        response = call_llm(
            task="memory_extraction",
            messages=llm_messages,
            max_tokens=800,
            temperature=0.2,
            timeout=45.0,
            main_runtime=main_runtime,
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("memory extraction LLM failed: %s", exc)
        return {"enqueued": False, "reason": "llm_error", "created": 0, "error": str(exc)}

    items = [_normalize_item(x) for x in _parse_llm_json_array(text)]
    items = [x for x in items if x][:_MAX_ITEMS]
    if not items:
        return {"enqueued": True, "reason": "empty", "created": 0}

    created_ids: list[str] = []
    with session_scope(store._engine) as db:
        workspace = db.get(Workspace, workspace_id)
        if not workspace or workspace.owner_id != user_id:
            return {"enqueued": False, "reason": "workspace_mismatch", "created": 0}
        for item in items:
            row = mc.create_item(
                db,
                workspace=workspace,
                user_id=user_id,
                category=item["category"],
                content=item["content"],
                source="conversation",
                status="pending",
                confidence=item["confidence"],
                source_ref=session_id,
                raw_excerpt=item.get("raw_excerpt"),
                ai_summary=item["content"],
            )
            created_ids.append(row.id)

    logger.info(
        "memory extraction created %s pending item(s) user=%s session=%s",
        len(created_ids),
        user_id,
        session_id,
    )
    return {
        "enqueued": True,
        "reason": "ok",
        "created": len(created_ids),
        "ids": created_ids,
    }


def maybe_enqueue_memory_extraction(
    *,
    user_id: str,
    workspace_id: str,
    session_id: str,
    messages: Optional[list[dict[str, Any]]] = None,
    main_runtime: Optional[dict[str, Any]] = None,
    sync: bool = False,
) -> dict[str, Any]:
    """Enqueue post-turn memory extraction.

    When the feature flag is off, returns ``{"enqueued": False, "reason": "disabled"}``.
    When on, starts a daemon thread (unless ``sync=True`` for tests) that only
    writes pending Memory Center rows — never permanent md projection.
    """
    if not extractor_enabled():
        return {"enqueued": False, "reason": "disabled"}

    if sync or os.environ.get("PLATFORM_MEMORY_EXTRACTOR_SYNC", "").strip() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return run_memory_extraction(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            messages=messages,
            main_runtime=main_runtime,
        )

    thread = threading.Thread(
        target=run_memory_extraction,
        kwargs={
            "user_id": user_id,
            "workspace_id": workspace_id,
            "session_id": session_id,
            "messages": messages,
            "main_runtime": main_runtime,
        },
        daemon=True,
        name="memory-extract",
    )
    thread.start()
    return {
        "enqueued": True,
        "reason": "started",
        "user_id": user_id,
        "workspace_id": workspace_id,
        "session_id": session_id,
    }
