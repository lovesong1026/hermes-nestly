"""Shared file registration for chat uploads, agent writes, and platform API."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select

from gateway.web.platform.database import session_scope
from gateway.web.platform.models import FileRecord, Workspace
from platform_api.deps import get_store


def register_sandbox_file(
    *,
    workspace_id: str,
    storage_key: str,
    filename: str,
    size_bytes: int,
    mime_type: Optional[str] = None,
    origin: str = "chat",
    auto_ingest: bool = False,
    folder_id: Optional[str] = None,
    file_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a FileRecord pointing at an existing sandbox / object key.

    Chat attachments use ``auto_ingest=False`` and get ``status='skipped'``.
    Platform uploads with ingest enabled start at ``pending``.
    """
    file_id = file_id or str(uuid.uuid4())
    initial_status = "pending" if auto_ingest else "skipped"
    store = get_store()
    with session_scope(store._engine) as db:
        ws = db.get(Workspace, workspace_id)
        if ws is None:
            raise ValueError(f"unknown workspace: {workspace_id}")
        rec = FileRecord(
            id=file_id,
            tenant_id=ws.tenant_id,
            workspace_id=ws.id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            origin=origin,
            folder_id=folder_id,
            status=initial_status,
        )
        db.add(rec)
        db.flush()
        return file_record_dict(rec, tag_ids=[])


def upsert_sandbox_file(
    *,
    workspace_id: str,
    storage_key: str,
    filename: str,
    size_bytes: int,
    mime_type: Optional[str] = None,
    origin: str = "agent",
    auto_ingest: bool = False,
) -> dict[str, Any]:
    """Insert or update a FileRecord for the same ``workspace_id`` + ``storage_key``.

    Agent ``web_file_write`` / ``web_file_patch`` reuses the same relative key
    when rewriting a path; avoid duplicate list rows in Files UI.
    """
    key = (storage_key or "").strip().lstrip("/")
    if not key:
        raise ValueError("storage_key required")
    store = get_store()
    with session_scope(store._engine) as db:
        ws = db.get(Workspace, workspace_id)
        if ws is None:
            raise ValueError(f"unknown workspace: {workspace_id}")
        existing = db.execute(
            select(FileRecord).where(
                FileRecord.workspace_id == workspace_id,
                FileRecord.storage_key == key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.filename = filename
            existing.size_bytes = size_bytes
            if mime_type is not None:
                existing.mime_type = mime_type
            # Keep origin/status if already registered (e.g. chat upload
            # later overwritten by agent — still one row).
            db.flush()
            return file_record_dict(existing, tag_ids=[])

        initial_status = "pending" if auto_ingest else "skipped"
        rec = FileRecord(
            id=str(uuid.uuid4()),
            tenant_id=ws.tenant_id,
            workspace_id=ws.id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_key=key,
            origin=origin,
            status=initial_status,
        )
        db.add(rec)
        db.flush()
        return file_record_dict(rec, tag_ids=[])


def file_record_dict(rec: FileRecord, *, tag_ids: list[str]) -> dict[str, Any]:
    return {
        "id": rec.id,
        "filename": rec.filename,
        "mime_type": rec.mime_type,
        "size_bytes": rec.size_bytes,
        "storage_key": rec.storage_key,
        "origin": rec.origin,
        "category_id": rec.category_id,
        "folder_id": getattr(rec, "folder_id", None),
        "tag_ids": tag_ids,
        "status": rec.status,
        "error_message": rec.error_message,
        "created_at": rec.created_at.timestamp(),
    }
