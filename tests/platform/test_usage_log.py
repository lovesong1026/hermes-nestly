"""Usage Center — third-party log.az-ai.icu aggregation (overview + logs)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from tests.platform.conftest import bind_upstream_key, register_user


def _log_row(
    *,
    rid: int,
    created_at: str,
    model: str,
    prompt: int = 100,
    completion: int = 10,
    quota: int = 500,
) -> dict:
    return {
        "id": rid,
        "created_at": created_at,
        "model_name": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "quota": quota,
    }


def _page_payload(rows: list[dict], *, page: int = 1, last_page: int = 1, total: int | None = None):
    return {
        "current_page": page,
        "data": rows,
        "last_page": last_page,
        "per_page": 10,
        "total": total if total is not None else len(rows),
        "next_page_url": None,
        "prev_page_url": None,
    }


def test_usage_log_overview_requires_bound_key(client, mock_upstream_key):
    _, cookie = register_user(client)
    resp = client.get(
        "/api/v1/usage-log/overview?days=7",
        cookies={"hermes_session": cookie},
    )
    assert resp.status_code == 403


def test_usage_log_overview_aggregates_and_filters_days(client, mock_upstream_key):
    _, cookie = register_user(client)
    bind_upstream_key(client)

    now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    # Inside 7d window
    in1 = _log_row(
        rid=1,
        created_at="2026-07-24T07:12:11.000000Z",
        model="gpt-5.6-sol",
        prompt=1000,
        completion=100,
        quota=5000,
    )
    in2 = _log_row(
        rid=2,
        created_at="2026-07-23T11:20:01.000000Z",
        model="gpt-5.6-luna",
        prompt=2000,
        completion=50,
        quota=10000,
    )
    # Outside 7d window (older than Jul 17 12:00)
    old = _log_row(
        rid=3,
        created_at="2026-07-10T00:00:00.000000Z",
        model="gpt-5.6-luna",
        prompt=9999,
        completion=9,
        quota=99999,
    )

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = _page_payload([in1, in2, old], page=1, last_page=1)

    billing = MagicMock()
    billing.status_code = 200
    billing.json.return_value = {
        "data": {
            "total_available": 21_649_150,  # /500000 ≈ 43.2983
            "unlimited_quota": False,
        }
    }

    def _get(url, **kwargs):
        if "/api/log" in str(url):
            return page1
        return billing

    with (
        patch("platform_api.routers.usage_log.httpx.Client") as Client,
        patch("platform_api.services.usage_log._utcnow", return_value=now),
    ):
        Client.return_value.__enter__.return_value.get.side_effect = _get
        resp = client.get(
            "/api/v1/usage-log/overview?days=7",
            cookies={"hermes_session": cookie},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["days"] == 7
    assert body["requests"] == 2
    assert body["prompt_tokens"] == 3000
    assert body["completion_tokens"] == 150
    # (5000+10000)/500000 = 0.03
    assert abs(body["cost_usd"] - 0.03) < 1e-9
    assert abs(body["balance_usd"] - 43.2983) < 1e-4
    assert body["balance_unlimited"] is False
    models = {m["model"]: m for m in body["by_model"]}
    assert models["gpt-5.6-sol"]["requests"] == 1
    assert models["gpt-5.6-luna"]["requests"] == 1
    assert "sk-test" not in resp.text
    # Old row excluded from daily buckets that matter
    assert all(
        (p.get("by_model") or {}).get("gpt-5.6-luna", 0) < 0.2
        or p["date"] >= "2026-07-17"
        for p in body["daily"]
    )


def test_usage_log_balance_with_v1_new_api_base(client, mock_upstream_key, monkeypatch):
    """NEW_API_BASE_URL often includes /v1 — balance must still resolve."""
    monkeypatch.setenv("NEW_API_BASE_URL", "http://upstream.test/v1")
    _, cookie = register_user(client)
    bind_upstream_key(client)

    now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    row = _log_row(
        rid=1,
        created_at="2026-07-24T07:12:11.000000Z",
        model="gpt-5.6-sol",
        quota=5000,
    )
    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = _page_payload([row], page=1, last_page=1)

    billing = MagicMock()
    billing.status_code = 200
    billing.json.return_value = {
        "data": {"total_available": 500_000, "unlimited_quota": False}
    }

    def _get(url, **kwargs):
        if "/api/log" in str(url):
            return page1
        assert str(url) == "http://upstream.test/api/usage/token"
        return billing

    with (
        patch("platform_api.routers.usage_log.httpx.Client") as Client,
        patch("platform_api.services.usage_log._utcnow", return_value=now),
    ):
        Client.return_value.__enter__.return_value.get.side_effect = _get
        resp = client.get(
            "/api/v1/usage-log/overview?days=7",
            cookies={"hermes_session": cookie},
        )

    assert resp.status_code == 200, resp.text
    assert abs(resp.json()["balance_usd"] - 1.0) < 1e-6


def test_usage_log_logs_paginates_filtered_window(client, mock_upstream_key):
    _, cookie = register_user(client)
    bind_upstream_key(client)

    now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        _log_row(
            rid=i,
            created_at=(now - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%S.000000Z"),
            model="gpt-5.6-sol",
            quota=100,
        )
        for i in range(5)
    ]
    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = _page_payload(rows, page=1, last_page=1, total=5)

    with (
        patch("platform_api.routers.usage_log.httpx.Client") as Client,
        patch("platform_api.services.usage_log._utcnow", return_value=now),
    ):
        Client.return_value.__enter__.return_value.get.return_value = page1
        resp = client.get(
            "/api/v1/usage-log/logs?days=7&page=1&per_page=2",
            cookies={"hermes_session": cookie},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 5
    assert body["per_page"] == 2
    assert body["current_page"] == 1
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == 0


def test_usage_log_rejects_bad_days(client, mock_upstream_key):
    _, cookie = register_user(client)
    bind_upstream_key(client)
    resp = client.get(
        "/api/v1/usage-log/overview?days=14",
        cookies={"hermes_session": cookie},
    )
    assert resp.status_code == 422
