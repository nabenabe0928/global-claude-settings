#!/usr/bin/env python3
"""Claude Code hook — logs tool use events to JSONL."""

from datetime import datetime
from datetime import timezone
import json
import os
from pathlib import Path
import re
import sys


_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|credentials?|auth)"
    r"""(["'\s:=]+)"""
    r"([A-Za-z]+\s+)?"
    r"([A-Za-z0-9_\-/.+=]{8,})"
)

_MAX_LEN = 5000
_MAX_FILE_BYTES = 10 * 1024 * 1024
_PURGE_DAYS = 30
_OUT_DIR = Path("claude_utils/workspace")
_OUT_FILE = _OUT_DIR / "observation.jsonl"
_ARCHIVE_DIR = _OUT_DIR / "observations.archive"
_PURGE_MARKER = _OUT_DIR / ".last-purge"


def _scrub(val: str) -> str:
    return _SECRET_RE.sub(
        lambda m: m.group(1) + m.group(2) + (m.group(3) or "") + "[REDACTED]",
        val,
    )


def _truncate(obj: object) -> str:
    if isinstance(obj, dict):
        return json.dumps(obj)[:_MAX_LEN]
    return str(obj)[:_MAX_LEN]


def _archive_if_needed() -> None:
    if not _OUT_FILE.exists():
        return
    if _OUT_FILE.stat().st_size < _MAX_FILE_BYTES:
        return
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    _OUT_FILE.rename(_ARCHIVE_DIR / f"observations-{ts}-{os.getpid()}.jsonl")


def _purge_old_archives() -> None:
    if _PURGE_MARKER.exists():
        age_s = datetime.now(timezone.utc).timestamp() - _PURGE_MARKER.stat().st_mtime
        if age_s < 86400:
            return
    if _ARCHIVE_DIR.is_dir():
        cutoff = datetime.now(timezone.utc).timestamp() - _PURGE_DAYS * 86400
        for f in _ARCHIVE_DIR.glob("observations-*.jsonl"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
    _PURGE_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _PURGE_MARKER.touch()


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        return

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    if data.get("agent_id"):
        return

    hook_event = os.environ.get("CLAUDE_HOOK_EVENT_NAME", "")
    event = "tool_start" if hook_event == "PreToolUse" else "tool_complete"

    tool = data.get("tool_name", data.get("tool", "unknown"))
    session = data.get("session_id", "unknown")

    tool_input = data.get("tool_input", data.get("input", {}))
    tool_output = data.get("tool_response")
    if tool_output is None:
        tool_output = data.get("tool_output", data.get("output", ""))

    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "tool": tool,
        "session": session,
    }

    if event == "tool_start":
        record["input"] = _scrub(_truncate(tool_input))
    else:
        record["output"] = _scrub(_truncate(tool_output))

    _purge_old_archives()
    _archive_if_needed()

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_OUT_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
