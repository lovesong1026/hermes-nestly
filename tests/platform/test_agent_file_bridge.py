"""Agent web_file_write/patch registers FileRecord for Files UI."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from gateway.web.platform.models import FileRecord
from gateway.web.sandbox import enter_user_context
from platform_api.deps import get_store
from tests.platform.conftest import bind_upstream_key, register_user


@pytest.fixture()
def agent_user(client, mock_upstream_key, platform_env):
    data, cookie = register_user(client)
    bind_upstream_key(client)
    return {
        "user_id": data["user"]["user_id"],
        "workspace_id": data["workspace"]["id"],
        "cookie": cookie,
    }


def _write(path: str, content: str) -> str:
    from gateway.web.tools.sandboxed_file_operations import _handle_web_file_write

    return _handle_web_file_write({"path": path, "content": content})


def _patch(path: str, old: str, new: str) -> str:
    from gateway.web.tools.sandboxed_file_operations import _handle_web_file_patch

    return _handle_web_file_patch(
        {
            "mode": "replace",
            "path": path,
            "old_string": old,
            "new_string": new,
        }
    )


def test_web_file_write_registers_agent_file(agent_user, client):
    uid = agent_user["user_id"]
    ws_id = agent_user["workspace_id"]
    cookie = agent_user["cookie"]

    with enter_user_context(uid):
        raw = _write("files/agent-note.md", "# hello from agent\n")
    data = json.loads(raw)
    assert not data.get("error"), raw

    store = get_store()
    with store._session_factory() as db:
        rows = (
            db.execute(select(FileRecord).where(FileRecord.workspace_id == ws_id))
            .scalars()
            .all()
        )
    assert len(rows) == 1
    rec = rows[0]
    assert rec.origin == "agent"
    assert rec.status == "skipped"
    assert rec.storage_key == "files/agent-note.md"
    assert rec.filename == "agent-note.md"
    assert (rec.size_bytes or 0) > 0

    listed = client.get(
        f"/api/v1/workspaces/{ws_id}/files",
        cookies={"hermes_session": cookie},
    )
    assert listed.status_code == 200, listed.text
    files = listed.json()
    assert any(f["filename"] == "agent-note.md" and f["origin"] == "agent" for f in files)


def test_web_file_write_upserts_same_storage_key(agent_user):
    uid = agent_user["user_id"]
    ws_id = agent_user["workspace_id"]

    with enter_user_context(uid):
        _write("files/same.md", "v1")
        _write("files/same.md", "version two longer")

    store = get_store()
    with store._session_factory() as db:
        rows = (
            db.execute(select(FileRecord).where(FileRecord.workspace_id == ws_id))
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].storage_key == "files/same.md"
    assert rows[0].size_bytes == len("version two longer".encode("utf-8"))


def test_web_file_write_skips_memories_and_skills(agent_user):
    uid = agent_user["user_id"]
    ws_id = agent_user["workspace_id"]

    with enter_user_context(uid):
        _write("memories/secret.md", "nope")
        _write("skills/custom/SKILL.md", "nope")
        _write("cache/tmp.txt", "nope")

    store = get_store()
    with store._session_factory() as db:
        rows = (
            db.execute(select(FileRecord).where(FileRecord.workspace_id == ws_id))
            .scalars()
            .all()
        )
    assert rows == []


def test_web_file_write_isolation_other_user(agent_user, client, mock_upstream_key):
    uid = agent_user["user_id"]
    with enter_user_context(uid):
        _write("files/private.md", "mine")

    other, cookie2 = register_user(client, email="other-agent@example.com")
    other_ws = other["workspace"]["id"]
    listed = client.get(
        f"/api/v1/workspaces/{other_ws}/files",
        cookies={"hermes_session": cookie2},
    )
    assert listed.status_code == 200
    assert listed.json() == []


def test_web_file_patch_updates_registered_size(agent_user):
    uid = agent_user["user_id"]
    ws_id = agent_user["workspace_id"]

    with enter_user_context(uid):
        _write("files/edit-me.md", "alpha")
        raw = _patch("files/edit-me.md", "alpha", "alpha-beta-gamma")
    data = json.loads(raw)
    assert not data.get("error"), raw

    store = get_store()
    with store._session_factory() as db:
        rows = (
            db.execute(select(FileRecord).where(FileRecord.workspace_id == ws_id))
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].size_bytes == len("alpha-beta-gamma".encode("utf-8"))


def test_web_file_write_skips_disallowed_suffix(agent_user):
    uid = agent_user["user_id"]
    ws_id = agent_user["workspace_id"]

    with enter_user_context(uid):
        _write("files/script.py", "print(1)\n")

    store = get_store()
    with store._session_factory() as db:
        rows = (
            db.execute(select(FileRecord).where(FileRecord.workspace_id == ws_id))
            .scalars()
            .all()
        )
    assert rows == []
