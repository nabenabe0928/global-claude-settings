"""Collect per-session cost data and aggregate into daily/monthly summaries.

Data flow:
  statusline.sh saves a per-session snapshot to .sessions/<session_id>.json.
  This module (called from a Stop hook) reads the snapshot, computes the cost
  delta since the last recording, and updates the daily JSONL log and monthly
  summary.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import fcntl
import json
import os
from pathlib import Path
import random
import sys


_SUMMARY_FILE = "summary.json"
_STATUS_LOG_DIR = Path.home() / ".claude" / "status-log"
_SESSIONS_DIR = _STATUS_LOG_DIR / ".sessions"
_TRACKER_FILE = _STATUS_LOG_DIR / ".session-tracker.json"
_LOCK_FILE = _STATUS_LOG_DIR / ".status-log.lock"
_CLEANUP_MONTHS = 3
_CLEANUP_PROBABILITY = 0.05


@contextmanager
def _flock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return default


def _read_session_snapshot(session_id: str) -> dict | None:
    return _load_json(_SESSIONS_DIR / f"{session_id}.json")


def _load_tracker() -> dict:
    return _load_json(_TRACKER_FILE, {})


def _save_tracker(tracker: dict) -> None:
    _atomic_write_json(_TRACKER_FILE, tracker)


def _load_summary(month_dir: Path) -> dict:
    return _load_json(month_dir / _SUMMARY_FILE, {})


def _save_summary(month_dir: Path, summary: dict) -> None:
    _atomic_write_json(month_dir / _SUMMARY_FILE, summary)


def _atomic_write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)


def _compute_delta(tracker: dict, session_id: str, current_cost: float) -> float:
    entry = tracker.get(session_id)
    if entry is None:
        return current_cost
    last_cost = entry.get("last_cost", 0.0)
    delta = current_cost - last_cost
    return max(0.0, delta)


def _append_to_daily_log(month_dir: Path, day: str, record: dict) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / f"{day}.jsonl"
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with open(path, "a") as f:
        f.write(line)


def _cleanup_month(month_dir: Path) -> None:
    sessions: dict[str, dict] = {}
    for jsonl_file in sorted(month_dir.glob("[0-9][0-9].jsonl")):
        for line in jsonl_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            sid = record.get("session_id", "")
            if not sid:
                continue
            sessions[sid] = {
                "last-updated": record.get("date", ""),
                "session_id": sid,
                "project_dir": record.get("project_dir", ""),
                "cost_usd": record.get("cost_usd", 0.0),
            }

    if sessions:
        sessions_file = month_dir / "sessions.jsonl"
        with open(sessions_file, "w") as f:
            for entry in sessions.values():
                f.write(json.dumps(entry) + "\n")

    for jsonl_file in month_dir.glob("[0-9][0-9].jsonl"):
        jsonl_file.unlink()


def _maybe_cleanup() -> None:
    if random.random() > _CLEANUP_PROBABILITY or not _STATUS_LOG_DIR.exists():
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=_CLEANUP_MONTHS * 30)
    cutoff_date = cutoff.strftime("%Y-%m-%d")
    cutoff_month = cutoff_date[:7]

    with _flock(_LOCK_FILE):
        for month_dir in sorted(
            _STATUS_LOG_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]")
        ):
            if month_dir.name >= cutoff_month:
                continue
            _cleanup_month(month_dir)
        tracker = _load_tracker()
        pruned = {
            k: v for k, v in tracker.items() if v.get("last_date", "") >= cutoff_date
        }
        if len(pruned) < len(tracker):
            _save_tracker(pruned)

    # Clean up stale session snapshot files (older than 7 days)
    if _SESSIONS_DIR.exists():
        stale_cutoff = datetime.now(timezone.utc).timestamp() - 7 * 86400
        for f in _SESSIONS_DIR.iterdir():
            if f.suffix == ".json" and f.stat().st_mtime < stale_cutoff:
                f.unlink(missing_ok=True)


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

    session_id = data.get("session_id", "")
    if not session_id:
        return

    snapshot = _read_session_snapshot(session_id)
    if snapshot is None:
        return

    current_cost = snapshot.get("cost_usd", 0.0)
    today = snapshot.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    year_month = today[:7]
    day = today[8:]

    month_dir = _STATUS_LOG_DIR / year_month

    with _flock(_LOCK_FILE):
        tracker = _load_tracker()
        delta = _compute_delta(tracker, session_id, current_cost)

        summary = _load_summary(month_dir)
        summary[day] = round(summary.get(day, 0.0) + delta, 6)
        _save_summary(month_dir, summary)

        tracker[session_id] = {"last_cost": current_cost, "last_date": today}
        _save_tracker(tracker)

        _append_to_daily_log(month_dir, day, snapshot)

    _maybe_cleanup()


if __name__ == "__main__":
    main()
