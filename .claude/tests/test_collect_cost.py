"""Tests for claude_utils.collect_cost."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

import claude_utils.collect_cost as cc


def _make_stdin(data, monkeypatch):
    text = data if isinstance(data, str) else json.dumps(data)
    monkeypatch.setattr("sys.stdin", StringIO(text))


def _make_snapshot(
    session_id="sess-1",
    cost_usd=0.5,
    date="2026-06-14",
    project_dir="/test/project",
):
    return {
        "date": date,
        "session_id": session_id,
        "model_id": "claude-opus-4-8",
        "project_dir": project_dir,
        "version": "2.1.90",
        "cost_usd": cost_usd,
        "context_window_size": 200000,
        "used_token_percentage": 8,
        "input_tokens": 8500,
        "output_tokens": 1200,
        "cache_write_tokens": 5000,
        "cache_read_tokens": 2000,
        "effort": "high",
        "thinking": True,
        "agent_name": None,
    }


def _write_snapshot(sessions_dir: Path, session_id: str, **kwargs):
    snap = _make_snapshot(session_id=session_id, **kwargs)
    (sessions_dir / f"{session_id}.json").write_text(json.dumps(snap))
    return snap


@pytest.fixture()
def _patch_cost(tmp_path, monkeypatch):
    log_dir = tmp_path / "status-log"
    log_dir.mkdir()
    sessions_dir = log_dir / ".sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(cc, "_STATUS_LOG_DIR", log_dir)
    monkeypatch.setattr(cc, "_SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(cc, "_TRACKER_FILE", log_dir / ".session-tracker.json")
    monkeypatch.setattr(cc, "_LOCK_FILE", log_dir / ".status-log.lock")
    return log_dir


# ── _read_session_snapshot ──


class TestReadSessionSnapshot:
    def test_reads_valid(self, _patch_cost):
        sessions_dir = _patch_cost / ".sessions"
        _write_snapshot(sessions_dir, "sess-1", cost_usd=1.23)
        result = cc._read_session_snapshot("sess-1")
        assert result["cost_usd"] == 1.23
        assert result["session_id"] == "sess-1"

    def test_missing_file(self, _patch_cost):
        assert cc._read_session_snapshot("nonexistent") is None

    def test_invalid_json(self, _patch_cost):
        sessions_dir = _patch_cost / ".sessions"
        (sessions_dir / "bad.json").write_text("not json")
        assert cc._read_session_snapshot("bad") is None


# ── _load_tracker / _save_tracker ──


class TestTracker:
    def test_empty_when_no_file(self, _patch_cost):
        assert cc._load_tracker() == {}

    def test_empty_when_invalid(self, _patch_cost):
        cc._TRACKER_FILE.write_text("broken")
        assert cc._load_tracker() == {}

    def test_roundtrip(self, _patch_cost):
        data = {"sess-1": {"last_cost": 0.5, "last_date": "2026-06-14"}}
        cc._save_tracker(data)
        assert cc._load_tracker() == data


# ── _compute_delta ──


class TestComputeDelta:
    def test_new_session(self):
        assert cc._compute_delta({}, "sess-1", 0.5) == 0.5

    def test_incremental(self):
        tracker = {"sess-1": {"last_cost": 0.3, "last_date": "2026-06-14"}}
        assert cc._compute_delta(tracker, "sess-1", 0.8) == pytest.approx(0.5)

    def test_negative_clamped(self):
        tracker = {"sess-1": {"last_cost": 1.0, "last_date": "2026-06-14"}}
        assert cc._compute_delta(tracker, "sess-1", 0.5) == 0.0

    def test_zero_delta(self):
        tracker = {"sess-1": {"last_cost": 0.5, "last_date": "2026-06-14"}}
        assert cc._compute_delta(tracker, "sess-1", 0.5) == 0.0


# ── _load_summary / _save_summary ──


class TestSummary:
    def test_empty_when_no_file(self, _patch_cost):
        month_dir = _patch_cost / "2026-06"
        month_dir.mkdir()
        assert cc._load_summary(month_dir) == {}

    def test_empty_when_invalid(self, _patch_cost):
        month_dir = _patch_cost / "2026-06"
        month_dir.mkdir()
        (month_dir / "summary.json").write_text("bad")
        assert cc._load_summary(month_dir) == {}

    def test_roundtrip(self, _patch_cost):
        month_dir = _patch_cost / "2026-06"
        month_dir.mkdir()
        data = {"14": 1.23, "15": 0.45}
        cc._save_summary(month_dir, data)
        assert cc._load_summary(month_dir) == data

    def test_atomic_no_partial(self, _patch_cost):
        month_dir = _patch_cost / "2026-06"
        month_dir.mkdir()
        cc._save_summary(month_dir, {"14": 1.0})
        assert not (month_dir / "summary.tmp").exists()


# ── _append_to_daily_log ──


class TestAppendToDailyLog:
    def test_creates_file(self, _patch_cost):
        month_dir = _patch_cost / "2026-06"
        record = _make_snapshot()
        cc._append_to_daily_log(month_dir, "14", record)
        path = month_dir / "14.jsonl"
        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["session_id"] == "sess-1"

    def test_appends_multiple(self, _patch_cost):
        month_dir = _patch_cost / "2026-06"
        cc._append_to_daily_log(month_dir, "14", _make_snapshot(cost_usd=0.1))
        cc._append_to_daily_log(month_dir, "14", _make_snapshot(cost_usd=0.5))
        lines = (month_dir / "14.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["cost_usd"] == 0.1
        assert json.loads(lines[1])["cost_usd"] == 0.5


# ── _cleanup_month ──


class TestCleanupMonth:
    def test_compacts_jsonl(self, _patch_cost):
        month_dir = _patch_cost / "2026-03"
        month_dir.mkdir()
        r1 = _make_snapshot(session_id="s1", cost_usd=0.3, date="2026-03-01")
        r2 = _make_snapshot(session_id="s1", cost_usd=0.8, date="2026-03-02")
        r3 = _make_snapshot(session_id="s2", cost_usd=0.2, date="2026-03-01")
        (month_dir / "01.jsonl").write_text(json.dumps(r1) + "\n" + json.dumps(r3) + "\n")
        (month_dir / "02.jsonl").write_text(json.dumps(r2) + "\n")

        cc._cleanup_month(month_dir)

        assert not (month_dir / "01.jsonl").exists()
        assert not (month_dir / "02.jsonl").exists()
        sessions_file = month_dir / "sessions.jsonl"
        assert sessions_file.exists()
        entries = [json.loads(line) for line in sessions_file.read_text().strip().splitlines()]
        assert len(entries) == 2
        by_sid = {e["session_id"]: e for e in entries}
        assert by_sid["s1"]["cost_usd"] == 0.8
        assert by_sid["s1"]["last-updated"] == "2026-03-02"
        assert by_sid["s2"]["cost_usd"] == 0.2

    def test_preserves_summary(self, _patch_cost):
        month_dir = _patch_cost / "2026-03"
        month_dir.mkdir()
        summary = {"01": 0.5, "02": 0.3}
        (month_dir / "summary.json").write_text(json.dumps(summary))
        r = _make_snapshot(session_id="s1", cost_usd=0.5, date="2026-03-01")
        (month_dir / "01.jsonl").write_text(json.dumps(r) + "\n")

        cc._cleanup_month(month_dir)

        assert json.loads((month_dir / "summary.json").read_text()) == summary

    def test_no_sessions_no_file(self, _patch_cost):
        month_dir = _patch_cost / "2026-03"
        month_dir.mkdir()
        (month_dir / "01.jsonl").write_text("\n")
        cc._cleanup_month(month_dir)
        assert not (month_dir / "sessions.jsonl").exists()
        assert not (month_dir / "01.jsonl").exists()


# ── _maybe_cleanup ──


class TestMaybeCleanup:
    def test_skips_when_random_high(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 0.9)
        month_dir = _patch_cost / "2020-01"
        month_dir.mkdir()
        r = _make_snapshot(session_id="s1", date="2020-01-01")
        (month_dir / "01.jsonl").write_text(json.dumps(r) + "\n")

        cc._maybe_cleanup()
        assert (month_dir / "01.jsonl").exists()

    def test_runs_when_random_low(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 0.01)
        month_dir = _patch_cost / "2020-01"
        month_dir.mkdir()
        r = _make_snapshot(session_id="s1", date="2020-01-01")
        (month_dir / "01.jsonl").write_text(json.dumps(r) + "\n")

        cc._maybe_cleanup()
        assert not (month_dir / "01.jsonl").exists()
        assert (month_dir / "sessions.jsonl").exists()

    def test_recent_month_untouched(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 0.01)
        month_dir = _patch_cost / "2099-12"
        month_dir.mkdir()
        r = _make_snapshot(session_id="s1", date="2099-12-01")
        (month_dir / "01.jsonl").write_text(json.dumps(r) + "\n")

        cc._maybe_cleanup()
        assert (month_dir / "01.jsonl").exists()

    def test_prunes_stale_tracker_entries(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 0.01)
        tracker = {
            "old-sess": {"last_cost": 0.1, "last_date": "2020-01-01"},
            "new-sess": {"last_cost": 0.5, "last_date": "2099-12-01"},
        }
        cc._save_tracker(tracker)
        cc._maybe_cleanup()
        result = cc._load_tracker()
        assert "old-sess" not in result
        assert "new-sess" in result


# ── main ──


class TestMain:
    def test_empty_stdin(self, _patch_cost, monkeypatch):
        _make_stdin("", monkeypatch)
        cc.main()

    def test_invalid_json(self, _patch_cost, monkeypatch):
        _make_stdin("not json", monkeypatch)
        cc.main()

    def test_subagent_logged_without_cost_tracking(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"
        _write_snapshot(sessions_dir, "s1", cost_usd=1.0, date="2026-06-14")
        _make_stdin(
            {"session_id": "s1", "agent_id": "agent-1", "hook_event_name": "Stop"},
            monkeypatch,
        )
        cc.main()

        month_dir = _patch_cost / "2026-06"
        lines = (month_dir / "14.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["cost_usd"] == 1.0

        assert cc._load_summary(month_dir) == {}
        assert cc._load_tracker() == {}

    def test_subagent_does_not_affect_summary(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"

        _write_snapshot(sessions_dir, "s1", cost_usd=0.3, date="2026-06-14")
        _make_stdin({"session_id": "s1"}, monkeypatch)
        cc.main()

        _write_snapshot(sessions_dir, "s2", cost_usd=0.5, date="2026-06-14")
        _make_stdin(
            {"session_id": "s2", "agent_id": "agent-1"},
            monkeypatch,
        )
        cc.main()

        summary = cc._load_summary(_patch_cost / "2026-06")
        assert summary["14"] == pytest.approx(0.3)

        lines = (_patch_cost / "2026-06" / "14.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_empty_agent_id_not_filtered(self, _patch_cost, monkeypatch):
        _make_stdin(
            {"session_id": "s1", "agent_id": "", "hook_event_name": "Stop"},
            monkeypatch,
        )
        sessions_dir = _patch_cost / ".sessions"
        _write_snapshot(sessions_dir, "s1", cost_usd=0.5, date="2026-06-14")
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        cc.main()
        assert (_patch_cost / "2026-06" / "14.jsonl").exists()

    def test_no_session_id(self, _patch_cost, monkeypatch):
        _make_stdin({"hook_event_name": "Stop"}, monkeypatch)
        cc.main()

    def test_no_snapshot_file(self, _patch_cost, monkeypatch):
        _make_stdin({"session_id": "nonexistent"}, monkeypatch)
        cc.main()

    def test_first_recording(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"
        _write_snapshot(sessions_dir, "s1", cost_usd=0.5, date="2026-06-14")
        _make_stdin({"session_id": "s1"}, monkeypatch)

        cc.main()

        month_dir = _patch_cost / "2026-06"
        summary = cc._load_summary(month_dir)
        assert summary["14"] == pytest.approx(0.5)

        tracker = cc._load_tracker()
        assert tracker["s1"]["last_cost"] == 0.5
        assert tracker["s1"]["last_date"] == "2026-06-14"

        lines = (month_dir / "14.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["cost_usd"] == 0.5

    def test_second_recording_delta(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"
        cc._save_tracker({"s1": {"last_cost": 0.3, "last_date": "2026-06-14"}})

        _write_snapshot(sessions_dir, "s1", cost_usd=0.8, date="2026-06-14")
        _make_stdin({"session_id": "s1"}, monkeypatch)
        cc.main()

        summary = cc._load_summary(_patch_cost / "2026-06")
        assert summary["14"] == pytest.approx(0.5)

    def test_cross_day_session(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"

        # Day 1: cost reaches 0.8
        cc._save_tracker({"s1": {"last_cost": 0.8, "last_date": "2026-06-14"}})
        month_dir = _patch_cost / "2026-06"
        month_dir.mkdir()
        cc._save_summary(month_dir, {"14": 0.8})

        # Day 2: cost reaches 1.2
        _write_snapshot(sessions_dir, "s1", cost_usd=1.2, date="2026-06-15")
        _make_stdin({"session_id": "s1"}, monkeypatch)
        cc.main()

        summary = cc._load_summary(month_dir)
        assert summary["14"] == pytest.approx(0.8)
        assert summary["15"] == pytest.approx(0.4)

    def test_cross_month_session(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"

        # May: cost reaches 2.0
        cc._save_tracker({"s1": {"last_cost": 2.0, "last_date": "2026-05-31"}})
        may_dir = _patch_cost / "2026-05"
        may_dir.mkdir()
        cc._save_summary(may_dir, {"31": 0.5})

        # June: cost reaches 2.5
        _write_snapshot(sessions_dir, "s1", cost_usd=2.5, date="2026-06-01")
        _make_stdin({"session_id": "s1"}, monkeypatch)
        cc.main()

        june_summary = cc._load_summary(_patch_cost / "2026-06")
        assert june_summary["01"] == pytest.approx(0.5)
        may_summary = cc._load_summary(may_dir)
        assert may_summary["31"] == pytest.approx(0.5)

    def test_multiple_sessions_same_day(self, _patch_cost, monkeypatch):
        monkeypatch.setattr("claude_utils.collect_cost.random.random", lambda: 1.0)
        sessions_dir = _patch_cost / ".sessions"

        _write_snapshot(sessions_dir, "s1", cost_usd=0.3, date="2026-06-14")
        _make_stdin({"session_id": "s1"}, monkeypatch)
        cc.main()

        _write_snapshot(sessions_dir, "s2", cost_usd=0.2, date="2026-06-14")
        _make_stdin({"session_id": "s2"}, monkeypatch)
        cc.main()

        summary = cc._load_summary(_patch_cost / "2026-06")
        assert summary["14"] == pytest.approx(0.5)

        lines = (_patch_cost / "2026-06" / "14.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
