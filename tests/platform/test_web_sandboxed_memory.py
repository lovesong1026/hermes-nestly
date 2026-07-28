"""web_memory tool queues pending Memory Center items (no silent permanent save)."""

from __future__ import annotations

import json

from gateway.web.sandbox import enter_user_context
from gateway.web.tools import sandboxed_memory  # noqa: F401 — register
from gateway.web.tools.sandboxed_memory import web_memory
from platform_api.deps import get_store
from tests.platform.conftest import bind_upstream_key, register_user
from tools.memory_tool import ENTRY_DELIMITER, MemoryStore


def _user(client, mock_upstream_key, email: str = "agent-mem@example.com"):
    del mock_upstream_key
    body, _ = register_user(client, email=email)
    bind_upstream_key(client)
    get_store.cache_clear()
    return body["user"]["user_id"], body["workspace"]["id"]


def test_web_memory_add_creates_pending_not_projected(client, mock_upstream_key):
    user_id, workspace_id = _user(client, mock_upstream_key)

    with enter_user_context(user_id):
        raw = web_memory(
            action="add",
            target="memory",
            content="Prefers UI-only agent operations",
        )
    data = json.loads(raw)
    assert data["success"] is True
    assert data["status"] == "pending"
    item_id = data["id"]

    store = get_store()
    with store._session_factory() as db:
        from gateway.web.platform.models import MemoryItem

        row = db.get(MemoryItem, item_id)
        assert row is not None
        assert row.status == "pending"
        assert row.workspace_id == workspace_id
        assert "UI-only" in row.content

    with enter_user_context(user_id):
        ms = MemoryStore()
        ms.load_from_disk()
        assert "UI-only" not in ENTRY_DELIMITER.join(ms.memory_entries)


def test_web_memory_preference_and_project_targets(client, mock_upstream_key):
    """target preference/project map to Memory Center categories (pending only)."""
    user_id, workspace_id = _user(
        client, mock_upstream_key, email="agent-mem-cats@example.com"
    )

    with enter_user_context(user_id):
        pref = json.loads(
            web_memory(
                action="add",
                target="preference",
                content="Prefers concise bullet answers",
            )
        )
        proj = json.loads(
            web_memory(
                action="add",
                target="project",
                content="Working on Hermes multi-user SaaS MVP",
            )
        )
        profile = json.loads(
            web_memory(
                action="add",
                target="user",
                content="Name is Alex",
            )
        )

    assert pref["success"] and pref["category"] == "preference"
    assert proj["success"] and proj["category"] == "project"
    assert profile["success"] and profile["category"] == "profile"

    store = get_store()
    with store._session_factory() as db:
        from gateway.web.platform.models import MemoryItem

        for item_id, cat in (
            (pref["id"], "preference"),
            (proj["id"], "project"),
            (profile["id"], "profile"),
        ):
            row = db.get(MemoryItem, item_id)
            assert row is not None
            assert row.status == "pending"
            assert row.category == cat
            assert row.workspace_id == workspace_id

    with enter_user_context(user_id):
        ms = MemoryStore()
        ms.load_from_disk()
        blob = ENTRY_DELIMITER.join(ms.memory_entries + ms.user_entries)
        assert "concise bullet" not in blob
        assert "Hermes multi-user" not in blob
        assert "Alex" not in blob


def test_web_memory_cannot_replace_active(client, mock_upstream_key):
    user_id, workspace_id = _user(
        client, mock_upstream_key, email="agent-mem2@example.com"
    )

    from gateway.web.platform.database import session_scope
    from gateway.web.platform.models import Workspace
    from platform_api.services import memory_center as mc

    store = get_store()
    with session_scope(store._engine) as db:
        ws = db.get(Workspace, workspace_id)
        mc.create_item(
            db,
            workspace=ws,
            user_id=user_id,
            category="knowledge",
            content="Active only memory",
            status="active",
            source="manual",
        )
        mc.project_active_memories(db, workspace_id=workspace_id, user_id=user_id)

    with enter_user_context(user_id):
        raw = web_memory(
            action="replace",
            target="memory",
            old_text="Active only",
            content="Hacked",
        )
    data = json.loads(raw)
    assert data["success"] is False
    assert "Memory Center" in data["error"]
