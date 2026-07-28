"""Tests for host-path privacy on the web_chat multi-user surface.

Contracts:
1. Absolute ``web_workspaces/<uid>/…`` paths rewrite to workspace-relative.
2. Ephemeral system prompt must NOT embed the host workspace absolute path.
3. Sandboxed file-tool results rewrite absolute paths before the model / SSE see them.
4. Outbound scrubbing is idempotent and preserves relative paths.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gateway.web.path_privacy import scrub_host_paths, scrub_value
from gateway.web.sandbox import enter_user_context


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def test_scrub_rewrites_active_workspace_absolute_path(hermes_home):
    with enter_user_context("u_alice") as ws:
        abs_file = str(ws / "uploads" / "data.csv")
        text = f"Read {abs_file} then summarize."
        out = scrub_host_paths(text)
        assert abs_file not in out
        assert "uploads/data.csv" in out
        assert "web_workspaces" not in out


def test_scrub_rewrites_sibling_user_workspace_path(hermes_home):
    """Even another tenant's absolute path must not leak as a host path."""
    bob = hermes_home / "web_workspaces" / "u_bob" / "files" / "secret.txt"
    bob.parent.mkdir(parents=True)
    bob.write_text("x", encoding="utf-8")
    with enter_user_context("u_alice"):
        out = scrub_host_paths(f"found at {bob}")
    assert str(bob) not in out
    assert "web_workspaces" not in out
    assert "files/secret.txt" in out


def test_scrub_rewrites_hermes_home_prefix(hermes_home):
    with enter_user_context("u_alice"):
        leaked = f"config at {hermes_home / 'config.yaml'}"
        out = scrub_host_paths(leaked)
    assert str(hermes_home) not in out
    assert "[hermes]/config.yaml" in out or "[hermes]" in out


def test_scrub_preserves_relative_and_urls(hermes_home):
    with enter_user_context("u_alice"):
        text = "See uploads/a.csv and https://example.com/path/to/page"
        assert scrub_host_paths(text) == text


def test_scrub_value_walks_nested_structures(hermes_home):
    with enter_user_context("u_alice") as ws:
        payload = {
            "path": str(ws / "files" / "a.txt"),
            "matches": [{"path": str(ws / "files" / "b.txt"), "line": 1}],
        }
        scrubbed = scrub_value(payload)
    assert scrubbed["path"] == "files/a.txt"
    assert scrubbed["matches"][0]["path"] == "files/b.txt"


def test_scrub_is_idempotent(hermes_home):
    with enter_user_context("u_alice") as ws:
        once = scrub_host_paths(f"x {ws / 'uploads' / 'f.txt'} y")
        twice = scrub_host_paths(once)
    assert once == twice


def _patch_gateway_runtime(monkeypatch):
    """Minimal gateway.run stubs so ``_create_agent`` can construct AIAgent."""
    fake_runtime = {
        "api_key": "fake-key",
        "base_url": "https://fake.example/v1",
        "provider": "fake",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": None,
    }
    monkeypatch.setattr(
        "gateway.run._resolve_runtime_agent_kwargs", lambda: dict(fake_runtime)
    )
    monkeypatch.setattr(
        "gateway.run._resolve_gateway_model", lambda config=None: "fake-model"
    )
    monkeypatch.setattr("gateway.run._load_gateway_config", lambda: {})
    monkeypatch.setattr(
        "gateway.run.GatewayRunner._load_reasoning_config",
        lambda: None,
    )
    monkeypatch.setattr(
        "gateway.run.GatewayRunner._load_fallback_model",
        lambda: None,
    )
    monkeypatch.setattr(
        "hermes_cli.tools_config._get_platform_tools",
        lambda config, platform: {"web_file_read"},
    )


def test_create_agent_prompt_omits_absolute_workspace(monkeypatch, hermes_home):
    """Runtime prompt teaches relative paths — never the host absolute root."""
    from gateway.web.chat_runner import WebChatAgentRunner

    _patch_gateway_runtime(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        "run_agent.AIAgent",
        lambda **kw: (captured.update(kw), type("A", (), {})())[1],
    )
    ws = hermes_home / "web_workspaces" / "u_alice"
    ws.mkdir(parents=True)

    with patch("gateway.web.sandbox.get_user_workspace", return_value=ws):
        WebChatAgentRunner()._create_agent(user_id="u_alice")

    eph = captured.get("ephemeral_system_prompt") or ""
    assert str(ws) not in eph
    assert "web_workspaces" not in eph
    assert "web_file_read" in eph
    assert "relative" in eph.lower() or "uploads/" in eph


def test_web_file_read_result_scrubs_absolute_path(hermes_home):
    from gateway.web.tools.sandboxed_file_operations import _handle_web_file_read

    with enter_user_context("u_alice") as ws:
        target = ws / "files" / "doc.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("hello", encoding="utf-8")
        leaked = json.dumps(
            {"success": True, "path": str(target), "content": "1|hello"},
            ensure_ascii=False,
        )
        with patch(
            "gateway.web.tools.sandboxed_file_operations.read_file_tool",
            return_value=leaked,
        ):
            result = _handle_web_file_read({"path": "files/doc.txt"})

    data = json.loads(result)
    assert str(target) not in result
    assert "web_workspaces" not in result
    assert data["path"] == "files/doc.txt"
