"""Account soft-deactivate (self-service disable)."""

from __future__ import annotations

from tests.platform.conftest import register_user


def test_deactivate_requires_password_and_confirm(client, mock_upstream_key):
    del mock_upstream_key
    _, cookie = register_user(
        client, email="bye@example.com", password="password123"
    )

    bad_confirm = client.post(
        "/api/v1/auth/deactivate",
        json={"password": "password123", "confirm": "nope"},
        cookies={"hermes_session": cookie},
    )
    assert bad_confirm.status_code == 400

    bad_pw = client.post(
        "/api/v1/auth/deactivate",
        json={"password": "wrong-pass", "confirm": "DELETE"},
        cookies={"hermes_session": cookie},
    )
    assert bad_pw.status_code == 401

    ok = client.post(
        "/api/v1/auth/deactivate",
        json={"password": "password123", "confirm": "DELETE"},
        cookies={"hermes_session": cookie},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "deactivated"

    # Session no longer valid
    me = client.get("/api/v1/auth/me", cookies={"hermes_session": cookie})
    assert me.status_code == 401

    # Cannot log in again
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "bye@example.com", "password": "password123"},
    )
    assert login.status_code == 401


def test_patch_me_email_conflict(client, mock_upstream_key):
    del mock_upstream_key
    register_user(client, email="taken@example.com", password="password123")
    _, cookie = register_user(
        client, email="free@example.com", password="password123"
    )
    conflict = client.patch(
        "/api/v1/auth/me",
        json={"email": "taken@example.com"},
        cookies={"hermes_session": cookie},
    )
    assert conflict.status_code == 400
    assert "email" in conflict.json()["detail"].lower()
