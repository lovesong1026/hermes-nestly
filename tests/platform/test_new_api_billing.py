"""Tests for new-api admin URL normalization and token usage parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

from platform_api.services.new_api_billing import (
    admin_base_url,
    fetch_token_usage,
    token_balance_usd,
)


def test_admin_base_url_strips_trailing_v1(monkeypatch):
    monkeypatch.setenv("NEW_API_BASE_URL", "http://upstream.test/v1")
    assert admin_base_url() == "http://upstream.test"


def test_fetch_token_usage_hits_root_api_path(monkeypatch):
    monkeypatch.setenv("NEW_API_BASE_URL", "http://upstream.test/v1")

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {"total_available": 500_000, "unlimited_quota": False}
    }
    client = MagicMock()
    client.get.return_value = resp

    data = fetch_token_usage(client, api_key="sk-test")
    assert data is not None
    client.get.assert_called_once_with(
        "http://upstream.test/api/usage/token",
        headers={"Authorization": "Bearer sk-test"},
        timeout=15.0,
    )


def test_token_balance_usd_converts_quota():
    usd, unlimited = token_balance_usd(
        {"total_available": 1_000_000, "unlimited_quota": False}
    )
    assert unlimited is False
    assert abs(usd - 2.0) < 1e-9


def test_token_balance_unlimited():
    usd, unlimited = token_balance_usd({"unlimited_quota": True})
    assert unlimited is True
    assert usd is None
