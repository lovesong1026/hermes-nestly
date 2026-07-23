"""Memory extractor — pending-only conversation extraction."""

from __future__ import annotations

from types import SimpleNamespace

from gateway.web.sandbox import enter_user_context
from platform_api.deps import get_store
from platform_api.services.memory_extractor import (
    extractor_enabled,
    maybe_enqueue_memory_extraction,
    run_memory_extraction,
)
from tests.platform.conftest import bind_upstream_key, register_user
from tools.memory_tool import ENTRY_DELIMITER, MemoryStore


def _user(client, mock_upstream_key, email: str = "extract@example.com"):
    del mock_upstream_key
    body, _ = register_user(client, email=email)
    bind_upstream_key(client)
    get_store.cache_clear()
    return body["user"]["user_id"], body["workspace"]["id"]


def test_extractor_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PLATFORM_MEMORY_EXTRACTOR", raising=False)
    assert extractor_enabled() is False
    result = maybe_enqueue_memory_extraction(
        user_id="u1",
        workspace_id="w1",
        session_id="s1",
        messages=[{"role": "user", "content": "remember I like cats"}],
    )
    assert result == {"enqueued": False, "reason": "disabled"}


def test_extractor_creates_pending_preference_project(
    client, mock_upstream_key, monkeypatch
):
    monkeypatch.setenv("PLATFORM_MEMORY_EXTRACTOR", "1")
    user_id, workspace_id = _user(client, mock_upstream_key)

    fake = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '[{"category":"preference","content":"Prefers dark mode",'
                        '"confidence":0.9},'
                        '{"category":"project","content":"Building SaaS MVP",'
                        '"confidence":0.85}]'
                    )
                )
            )
        ]
    )
    monkeypatch.setattr(
        "agent.auxiliary_client.call_llm",
        lambda **kwargs: fake,
    )

    result = run_memory_extraction(
        user_id=user_id,
        workspace_id=workspace_id,
        session_id="sess-extract-1",
        messages=[
            {"role": "user", "content": "I prefer dark mode. Working on SaaS MVP."},
            {"role": "assistant", "content": "Got it."},
        ],
    )
    assert result["enqueued"] is True
    assert result["created"] == 2

    store = get_store()
    with store._session_factory() as db:
        from gateway.web.platform.models import MemoryItem
        from sqlalchemy import select

        rows = list(
            db.execute(
                select(MemoryItem).where(
                    MemoryItem.workspace_id == workspace_id,
                    MemoryItem.status == "pending",
                    MemoryItem.source == "conversation",
                )
            ).scalars().all()
        )
        cats = {r.category for r in rows}
        assert cats == {"preference", "project"}
        assert all(r.source_ref == "sess-extract-1" for r in rows)

    with enter_user_context(user_id):
        ms = MemoryStore()
        ms.load_from_disk()
        blob = ENTRY_DELIMITER.join(ms.memory_entries + ms.user_entries)
        assert "dark mode" not in blob
        assert "SaaS MVP" not in blob


def test_extractor_isolation_other_workspace(
    client, mock_upstream_key, monkeypatch
):
    monkeypatch.setenv("PLATFORM_MEMORY_EXTRACTOR", "1")
    user_a, ws_a = _user(client, mock_upstream_key, email="ex-a@example.com")
    user_b, ws_b = _user(client, mock_upstream_key, email="ex-b@example.com")

    fake = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '[{"category":"profile","content":"Secret for A only",'
                        '"confidence":0.95}]'
                    )
                )
            )
        ]
    )
    monkeypatch.setattr(
        "agent.auxiliary_client.call_llm",
        lambda **kwargs: fake,
    )

    # Wrong owner for workspace B must not insert
    result = run_memory_extraction(
        user_id=user_a,
        workspace_id=ws_b,
        session_id="sess-iso",
        messages=[
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Hi Alice"},
        ],
    )
    assert result["created"] == 0
    assert result["reason"] == "workspace_mismatch"

    store = get_store()
    with store._session_factory() as db:
        from gateway.web.platform.models import MemoryItem
        from sqlalchemy import select, func

        n = db.execute(
            select(func.count())
            .select_from(MemoryItem)
            .where(MemoryItem.workspace_id == ws_b)
        ).scalar_one()
        assert int(n or 0) == 0

    _ = user_b, ws_a


def test_extractor_skips_when_recent_agent_tool(
    client, mock_upstream_key, monkeypatch
):
    monkeypatch.setenv("PLATFORM_MEMORY_EXTRACTOR", "1")
    user_id, workspace_id = _user(
        client, mock_upstream_key, email="ex-skip@example.com"
    )

    from gateway.web.platform.database import session_scope
    from gateway.web.platform.models import Workspace
    from platform_api.services import memory_center as mc

    store = get_store()
    with session_scope(store._engine) as db:
        ws = db.get(Workspace, workspace_id)
        mc.create_pending_from_agent(
            db,
            workspace=ws,
            user_id=user_id,
            content="Already suggested via tool",
            category="preference",
        )

    called = {"n": 0}

    def _boom(**kwargs):
        called["n"] += 1
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr("agent.auxiliary_client.call_llm", _boom)

    result = run_memory_extraction(
        user_id=user_id,
        workspace_id=workspace_id,
        session_id="sess-skip",
        messages=[
            {"role": "user", "content": "I like tea"},
            {"role": "assistant", "content": "ok"},
        ],
    )
    assert result["reason"] == "agent_tool_pending"
    assert called["n"] == 0
