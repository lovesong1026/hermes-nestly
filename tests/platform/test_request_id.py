"""Request-id middleware exposes X-Request-ID on Platform API responses."""

from __future__ import annotations


def test_healthz_sets_request_id_header(client):
    res = client.get("/api/v1/healthz")
    assert res.status_code in (200, 503)
    rid = res.headers.get("x-request-id") or res.headers.get("X-Request-ID")
    assert rid
    assert len(rid) >= 8


def test_healthz_echoes_incoming_request_id(client):
    res = client.get(
        "/api/v1/healthz",
        headers={"X-Request-ID": "test-req-abc-123"},
    )
    assert res.status_code in (200, 503)
    assert res.headers.get("x-request-id") == "test-req-abc-123"
