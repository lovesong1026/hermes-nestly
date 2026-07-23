"""Platform worker: file ingest + knowledge index queues.

``python -m platform_api.worker`` or ``hermes-platform-worker``.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

logging.basicConfig(
    level=os.environ.get("HERMES_WORKER_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [platform-worker] %(message)s",
)
logger = logging.getLogger("hermes.platform.worker")


def handle_ingest_job(job: dict[str, Any]) -> str:
    """Process one ingest payload. Returns ``ok``, ``skip``, ``retry``, or ``dlq``."""
    file_id = job.get("file_id")
    user_id = job.get("user_id")
    if not file_id or not user_id:
        logger.warning("malformed ingest job: %s", job)
        return "skip"
    try:
        from platform_api.services.ingest import ingest_file_record

        ingest_file_record(str(file_id), str(user_id), raise_on_error=True)
        logger.info("ingest ok file=%s attempt=%s", file_id, job.get("attempt"))
        return "ok"
    except Exception as exc:
        from platform_api.services.queue import requeue_or_deadletter

        action = requeue_or_deadletter(job, error=str(exc))
        logger.warning(
            "ingest fail file=%s action=%s err=%s",
            file_id,
            action,
            exc,
        )
        return action


def handle_knowledge_job(job: dict[str, Any]) -> str:
    knowledge_id = job.get("knowledge_id")
    user_id = job.get("user_id")
    if not knowledge_id or not user_id:
        logger.warning("malformed knowledge job: %s", job)
        return "skip"
    try:
        from platform_api.services.knowledge_center import run_knowledge_index

        run_knowledge_index(knowledge_id=str(knowledge_id), user_id=str(user_id))
        logger.info(
            "knowledge index ok id=%s attempt=%s",
            knowledge_id,
            job.get("attempt"),
        )
        return "ok"
    except Exception as exc:
        from platform_api.services.queue import requeue_or_deadletter_knowledge

        action = requeue_or_deadletter_knowledge(job, error=str(exc))
        logger.warning(
            "knowledge index fail id=%s action=%s err=%s",
            knowledge_id,
            action,
            exc,
        )
        return action


def handle_job(job: dict[str, Any]) -> str:
    if job.get("job_type") == "knowledge_index" or job.get("knowledge_id"):
        return handle_knowledge_job(job)
    return handle_ingest_job(job)


def main() -> None:
    from platform_api.services.queue import brpop_platform_job, redis_configured

    if not redis_configured():
        logger.error("REDIS_URL is not set — worker has nothing to consume")
        sys.exit(1)

    logger.info(
        "platform worker started queues=hermes:ingest,hermes:knowledge_index"
    )
    while True:
        try:
            job = brpop_platform_job(timeout=5)
        except Exception:
            logger.exception("brpop failed; sleeping")
            time.sleep(2)
            continue
        if not job:
            continue
        handle_job(job)


if __name__ == "__main__":
    main()
