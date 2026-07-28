"""Host-path privacy for the multi-user ``web_chat`` surface.

Absolute filesystem paths under ``$HERMES_HOME/web_workspaces/<user_id>/``
must not appear in model prompts, tool results, SSE events, or stored
transcripts returned to the SPA.  Users and the model should only see
workspace-relative paths (``uploads/a.csv``, ``files/notes.md``).

Internal sandbox code still uses absolute paths for ``confine_path`` /
disk I/O — this module only rewrites *outbound* / *model-visible* text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

# Absolute (POSIX or Windows drive) paths that include our per-user layout.
# Captures optional rest under the user id so we can rewrite to a relative key.
_WEB_WORKSPACE_ABS = re.compile(
    r"(?:[A-Za-z]:[\\/]|/)[^\s\"'`]*?"
    r"[/\\]web_workspaces[/\\]"
    r"(?P<uid>[^/\\\"'`\s]+)"
    r"(?P<rest>[/\\][^\s\"'`]*)?"
)


def _workspace_candidates(workspace: Path) -> list[str]:
    """Absolute spellings of ``workspace`` to strip (longest first)."""
    raw: list[str] = []
    try:
        raw.append(str(workspace.resolve()))
    except OSError:
        pass
    raw.append(str(workspace))
    # De-dupe while preferring longer prefixes (avoid partial replace bugs).
    uniq = sorted({p.rstrip("/\\") for p in raw if p}, key=len, reverse=True)
    return uniq


def _replace_prefix(text: str, prefix: str, relative_replacement: str) -> str:
    """Replace ``prefix`` and ``prefix/…`` with a relative form."""
    if not prefix or prefix not in text:
        return text
    out = text
    # Prefer slash-terminated replacement so ``…/uploads`` becomes ``uploads``.
    for sep in ("/", "\\"):
        needle = prefix + sep
        if needle in out:
            out = out.replace(needle, relative_replacement)
    if prefix in out:
        # Bare workspace root → "."
        out = out.replace(prefix, ".")
    return out


def scrub_host_paths(
    text: str,
    *,
    workspace: Optional[Path] = None,
) -> str:
    """Rewrite absolute host paths in ``text`` to workspace-relative forms.

    Order:
    1. Active user workspace absolute prefix → relative (``uploads/…``).
    2. Any ``…/web_workspaces/<uid>/…`` absolute path → path under that uid.
    3. Process ``HERMES_HOME`` absolute prefix → ``[hermes]/…``.
    """
    if not text or not isinstance(text, str):
        return text

    ws = workspace
    if ws is None:
        try:
            from gateway.web.sandbox import get_user_workspace

            ws = get_user_workspace()
        except Exception:
            ws = None

    out = text

    if ws is not None:
        for cand in _workspace_candidates(ws):
            out = _replace_prefix(out, cand, "")

    def _ws_sub(match: re.Match[str]) -> str:
        rest = match.group("rest") or ""
        rel = rest.replace("\\", "/").lstrip("/")
        return rel if rel else "."

    out = _WEB_WORKSPACE_ABS.sub(_ws_sub, out)

    try:
        from gateway.web.sandbox import process_hermes_home

        home = str(process_hermes_home().resolve()).rstrip("/\\")
    except Exception:
        home = ""
    if home and home in out:
        out = _replace_prefix(out, home, "[hermes]/")
        # Bare home left as opaque marker.
        if home in out:
            out = out.replace(home, "[hermes]")

    return out


def scrub_value(value: Any, *, workspace: Optional[Path] = None) -> Any:
    """Recursively scrub strings inside JSON-ish structures."""
    if isinstance(value, str):
        return scrub_host_paths(value, workspace=workspace)
    if isinstance(value, list):
        return [scrub_value(v, workspace=workspace) for v in value]
    if isinstance(value, dict):
        return {k: scrub_value(v, workspace=workspace) for k, v in value.items()}
    return value
