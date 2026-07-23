"""Ingest worker entry: REDIS required, job success / retry / skip."""

from __future__ import annotations

from collections import defaultdict

import pytest

from platform_api.services import queue as queue_mod
from platform_api.worker import __main__ as worker_mod


class _FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = defaultdict(list)

    def rpush(self, key: str, value: str) -> int:
        self.lists[key].append(value)
        return len(self.lists[key])

    def brpop(self, key, timeout: int = 0):
        # redis-py accepts a single key or a list of keys
        keys = key if isinstance(key, (list, tuple)) else [key]
        for k in keys:
            if self.lists[k]:
                return k, self.lists[k].pop(0)
        return None

    def llen(self, key: str) -> int:
        return len(self.lists[key])


def test_main_exits_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(SystemExit) as ei:
        worker_mod.main()
    assert ei.value.code == 1


def test_handle_job_ok(monkeypatch):
    calls: list[tuple[str, str, bool]] = []

    def fake_ingest(file_id: str, user_id: str, *, raise_on_error: bool = False) -> None:
        calls.append((file_id, user_id, raise_on_error))

    monkeypatch.setattr(
        "platform_api.services.ingest.ingest_file_record", fake_ingest
    )
    assert (
        worker_mod.handle_ingest_job(
            {"file_id": "f1", "user_id": "u1", "attempt": 0}
        )
        == "ok"
    )
    assert calls == [("f1", "u1", True)]


def test_handle_job_skip_malformed():
    assert worker_mod.handle_ingest_job({"file_id": "f1"}) == "skip"
    assert worker_mod.handle_ingest_job({}) == "skip"


def test_handle_job_retry_on_failure(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setattr(queue_mod, "_redis", lambda: fake)
    monkeypatch.setattr(queue_mod.time, "sleep", lambda _s: None)

    def boom(file_id: str, user_id: str, *, raise_on_error: bool = False) -> None:
        raise RuntimeError("extract failed")

    monkeypatch.setattr("platform_api.services.ingest.ingest_file_record", boom)
    assert (
        worker_mod.handle_ingest_job(
            {"file_id": "f1", "user_id": "u1", "workspace_id": "ws", "attempt": 0}
        )
        == "retry"
    )
    assert len(fake.lists[queue_mod.INGEST_QUEUE]) == 1


def test_main_consumes_one_job_then_stops(monkeypatch):
    """main() loop: one job → ingest → next brpop raises to stop."""
    jobs = [{"file_id": "fx", "user_id": "ux", "attempt": 0, "job_type": "ingest"}]

    def fake_brpop(timeout: int = 5):
        if jobs:
            return jobs.pop(0)
        raise KeyboardInterrupt

    calls: list[str] = []

    def fake_ingest(file_id: str, user_id: str, *, raise_on_error: bool = False) -> None:
        calls.append(file_id)

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setattr(queue_mod, "redis_configured", lambda: True)
    # Worker consumes via brpop_platform_job (ingest + knowledge queues).
    monkeypatch.setattr(queue_mod, "brpop_platform_job", fake_brpop)
    monkeypatch.setattr(
        "platform_api.services.ingest.ingest_file_record", fake_ingest
    )
    with pytest.raises(KeyboardInterrupt):
        worker_mod.main()
    assert calls == ["fx"]


def test_handle_knowledge_job_ok(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_index(*, knowledge_id: str, user_id: str):
        calls.append((knowledge_id, user_id))
        return {"id": knowledge_id, "status": "ready"}

    monkeypatch.setattr(
        "platform_api.services.knowledge_center.run_knowledge_index",
        fake_index,
    )
    assert (
        worker_mod.handle_knowledge_job(
            {"knowledge_id": "k1", "user_id": "u1", "attempt": 0}
        )
        == "ok"
    )
    assert calls == [("k1", "u1")]


def test_handle_job_routes_knowledge(monkeypatch):
    """handle_job dispatches knowledge payloads by job_type / knowledge_id."""
    seen: list[str] = []

    monkeypatch.setattr(
        worker_mod,
        "handle_knowledge_job",
        lambda job: seen.append("knowledge") or "ok",
    )
    monkeypatch.setattr(
        worker_mod,
        "handle_ingest_job",
        lambda job: seen.append("ingest") or "ok",
    )
    assert worker_mod.handle_job(
        {"job_type": "knowledge_index", "knowledge_id": "k"}
    ) == "ok"
    assert worker_mod.handle_job({"file_id": "f", "user_id": "u"}) == "ok"
    assert seen == ["knowledge", "ingest"]
