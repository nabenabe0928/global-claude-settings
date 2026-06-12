"""Tests for claude_utils.scripts.utils.observe."""

from __future__ import annotations

from io import StringIO
import json
import os
import time

import pytest

import claude_utils.observe as obs


class TestScrub:
    def test_redacts_api_key(self):
        assert "[REDACTED]" in obs._scrub('api_key="sk-abc12345678"')

    def test_redacts_bearer_token(self):
        result = obs._scrub("authorization: Bearer eyJhbGciOiJI")
        assert "Bearer" in result
        assert "[REDACTED]" in result
        assert "eyJhbGciOiJI" not in result

    def test_redacts_password(self):
        result = obs._scrub('password: "my_secret_pass_1234"')
        assert "[REDACTED]" in result
        assert "my_secret_pass_1234" not in result

    def test_preserves_non_secret(self):
        text = "file_path=/Users/test/hello.py"
        assert obs._scrub(text) == text

    def test_short_values_not_redacted(self):
        text = 'token="short"'
        assert obs._scrub(text) == text


class TestTruncate:
    def test_dict_truncated(self):
        big = {"key": "x" * 10000}
        result = obs._truncate(big)
        assert len(result) == obs._MAX_LEN

    def test_string_truncated(self):
        big = "x" * 10000
        result = obs._truncate(big)
        assert len(result) == obs._MAX_LEN

    def test_small_dict_unchanged(self):
        d = {"a": 1}
        result = obs._truncate(d)
        assert result == json.dumps(d)

    def test_small_string_unchanged(self):
        assert obs._truncate("hello") == "hello"


class TestArchiveIfNeeded:
    def test_no_file_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(obs, "_OUT_FILE", tmp_path / "observation.jsonl")
        monkeypatch.setattr(obs, "_ARCHIVE_DIR", tmp_path / "archive")
        obs._archive_if_needed()
        assert not (tmp_path / "archive").exists()

    def test_small_file_noop(self, tmp_path, monkeypatch):
        out_file = tmp_path / "observation.jsonl"
        out_file.write_text("small\n")
        monkeypatch.setattr(obs, "_OUT_FILE", out_file)
        monkeypatch.setattr(obs, "_ARCHIVE_DIR", tmp_path / "archive")
        obs._archive_if_needed()
        assert out_file.exists()
        assert not (tmp_path / "archive").exists()

    def test_large_file_archived(self, tmp_path, monkeypatch):
        out_file = tmp_path / "observation.jsonl"
        out_file.write_bytes(b"x" * (11 * 1024 * 1024))
        archive_dir = tmp_path / "archive"
        monkeypatch.setattr(obs, "_OUT_FILE", out_file)
        monkeypatch.setattr(obs, "_ARCHIVE_DIR", archive_dir)
        obs._archive_if_needed()
        assert not out_file.exists()
        assert archive_dir.exists()
        archived = list(archive_dir.glob("observations-*.jsonl"))
        assert len(archived) == 1


class TestPurgeOldArchives:
    def test_no_archive_dir_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(obs, "_ARCHIVE_DIR", tmp_path / "archive")
        monkeypatch.setattr(obs, "_PURGE_MARKER", tmp_path / ".last-purge")
        obs._purge_old_archives()
        assert (tmp_path / ".last-purge").exists()

    def test_skips_when_marker_recent(self, tmp_path, monkeypatch):
        marker = tmp_path / ".last-purge"
        marker.touch()
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        old_file = archive_dir / "observations-old.jsonl"
        old_file.write_text("old")
        old_mtime = time.time() - 40 * 86400
        os.utime(old_file, (old_mtime, old_mtime))

        monkeypatch.setattr(obs, "_ARCHIVE_DIR", archive_dir)
        monkeypatch.setattr(obs, "_PURGE_MARKER", marker)
        obs._purge_old_archives()
        assert old_file.exists()

    def test_purges_old_files(self, tmp_path, monkeypatch):
        marker = tmp_path / ".last-purge"
        marker.touch()
        old_mtime = time.time() - 2 * 86400
        os.utime(marker, (old_mtime, old_mtime))

        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        old_file = archive_dir / "observations-20200101-000000-1.jsonl"
        old_file.write_text("old")
        file_mtime = time.time() - 40 * 86400
        os.utime(old_file, (file_mtime, file_mtime))

        recent_file = archive_dir / "observations-20260101-000000-2.jsonl"
        recent_file.write_text("recent")

        monkeypatch.setattr(obs, "_ARCHIVE_DIR", archive_dir)
        monkeypatch.setattr(obs, "_PURGE_MARKER", marker)
        obs._purge_old_archives()
        assert not old_file.exists()
        assert recent_file.exists()


@pytest.fixture()
def _patch_observe(tmp_path, monkeypatch):
    """Redirect observe module output to tmp_path and clear env."""
    out_dir = tmp_path / "claude_utils/workspace"
    out_dir.mkdir(parents=True)
    monkeypatch.setattr(obs, "_OUT_DIR", out_dir)
    monkeypatch.setattr(obs, "_OUT_FILE", out_dir / "observation.jsonl")
    monkeypatch.setattr(obs, "_ARCHIVE_DIR", out_dir / "observations.archive")
    monkeypatch.setattr(obs, "_PURGE_MARKER", out_dir / ".last-purge")
    monkeypatch.delenv("CLAUDE_HOOK_EVENT_NAME", raising=False)
    return out_dir


def _make_stdin(data: dict | str, monkeypatch) -> None:
    text = data if isinstance(data, str) else json.dumps(data)
    monkeypatch.setattr("sys.stdin", StringIO(text))


class TestMain:
    def test_empty_stdin(self, _patch_observe, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO(""))
        obs.main()
        out = _patch_observe / "observation.jsonl"
        assert not out.exists()

    def test_invalid_json(self, _patch_observe, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO("not json"))
        obs.main()
        out = _patch_observe / "observation.jsonl"
        assert not out.exists()

    def test_subagent_filtered(self, _patch_observe, monkeypatch):
        _make_stdin({"agent_id": "sub-1", "tool_name": "Read"}, monkeypatch)
        obs.main()
        out = _patch_observe / "observation.jsonl"
        assert not out.exists()

    def test_pre_tool_use_event(self, _patch_observe, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PreToolUse")
        _make_stdin(
            {
                "tool_name": "Bash",
                "session_id": "sess-1",
                "tool_input": {"command": "ls"},
            },
            monkeypatch,
        )
        obs.main()
        out = _patch_observe / "observation.jsonl"
        assert out.exists()
        record = json.loads(out.read_text().strip())
        assert record["event"] == "tool_start"
        assert record["tool"] == "Bash"
        assert record["session"] == "sess-1"
        assert "input" in record
        assert "output" not in record

    def test_post_tool_use_event(self, _patch_observe, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PostToolUse")
        _make_stdin(
            {
                "tool_name": "Read",
                "session_id": "sess-2",
                "tool_response": "file contents here",
            },
            monkeypatch,
        )
        obs.main()
        out = _patch_observe / "observation.jsonl"
        record = json.loads(out.read_text().strip())
        assert record["event"] == "tool_complete"
        assert record["tool"] == "Read"
        assert "output" in record
        assert "input" not in record

    def test_fallback_field_names(self, _patch_observe, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PreToolUse")
        _make_stdin({"tool": "Write", "input": {"file": "a.py"}}, monkeypatch)
        obs.main()
        out = _patch_observe / "observation.jsonl"
        record = json.loads(out.read_text().strip())
        assert record["tool"] == "Write"
        assert record["session"] == "unknown"

    def test_secrets_scrubbed_in_output(self, _patch_observe, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PostToolUse")
        _make_stdin(
            {
                "tool_name": "Bash",
                "session_id": "s",
                "tool_response": 'api_key="sk-secret-key-12345678"',
            },
            monkeypatch,
        )
        obs.main()
        out = _patch_observe / "observation.jsonl"
        record = json.loads(out.read_text().strip())
        assert "sk-secret-key-12345678" not in record["output"]
        assert "[REDACTED]" in record["output"]

    def test_appends_multiple_records(self, _patch_observe, monkeypatch):
        for i in range(3):
            monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PreToolUse")
            _make_stdin({"tool_name": f"Tool{i}", "session_id": "s"}, monkeypatch)
            obs.main()
        out = _patch_observe / "observation.jsonl"
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_no_env_defaults_to_tool_complete(self, _patch_observe, monkeypatch):
        _make_stdin(
            {"tool_name": "Read", "session_id": "s", "tool_response": "ok"},
            monkeypatch,
        )
        obs.main()
        out = _patch_observe / "observation.jsonl"
        record = json.loads(out.read_text().strip())
        assert record["event"] == "tool_complete"

    def test_agent_id_empty_string_not_filtered(self, _patch_observe, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PreToolUse")
        _make_stdin(
            {"agent_id": "", "tool_name": "Bash", "session_id": "s"},
            monkeypatch,
        )
        obs.main()
        out = _patch_observe / "observation.jsonl"
        assert out.exists()

    def test_timestamp_format(self, _patch_observe, monkeypatch):
        monkeypatch.setenv("CLAUDE_HOOK_EVENT_NAME", "PreToolUse")
        _make_stdin({"tool_name": "Bash", "session_id": "s"}, monkeypatch)
        obs.main()
        out = _patch_observe / "observation.jsonl"
        record = json.loads(out.read_text().strip())
        assert record["timestamp"].endswith("Z")
        assert "T" in record["timestamp"]
