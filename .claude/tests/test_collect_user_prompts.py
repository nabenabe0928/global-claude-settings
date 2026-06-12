"""Tests for claude_utils.scripts.utils.collect_user_prompts."""

from __future__ import annotations

from io import StringIO
import json

import pytest

import claude_utils.collect_user_prompts as cup


def _write_transcript(path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_user_record(prompt, session="sess-1", timestamp="2026-06-02T10:00:00Z"):
    return {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "uuid": "u1",
        "timestamp": timestamp,
        "sessionId": session,
        "cwd": "/test",
        "gitBranch": "main",
    }


def _make_stdin(data, monkeypatch):
    text = data if isinstance(data, str) else json.dumps(data)
    monkeypatch.setattr("sys.stdin", StringIO(text))


@pytest.fixture()
def _patch_cup(tmp_path, monkeypatch):
    out_dir = tmp_path / "claude_utils/workspace"
    out_dir.mkdir(parents=True)
    monkeypatch.setattr(cup, "_OUT_DIR", out_dir)
    monkeypatch.setattr(cup, "_OUT_FILE", out_dir / "user-prompts.jsonl")
    monkeypatch.setattr(cup, "_OFFSET_FILE", out_dir / ".user-prompts-offset.json")
    return out_dir


class TestExtractPromptText:
    def test_string_content(self):
        msg = {"role": "user", "content": "hello world"}
        assert cup._extract_prompt_text(msg) == "hello world"

    def test_list_content_text_blocks(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "first"},
                {"type": "text", "text": "second"},
            ],
        }
        assert cup._extract_prompt_text(msg) == "first\nsecond"

    def test_list_content_mixed_types(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "image", "source": "..."},
            ],
        }
        assert cup._extract_prompt_text(msg) == "hello"

    def test_list_content_raw_strings(self):
        msg = {"role": "user", "content": ["a", "b"]}
        assert cup._extract_prompt_text(msg) == "a\nb"

    def test_raw_string_message(self):
        assert cup._extract_prompt_text("just a string") == "just a string"

    def test_empty_content(self):
        msg = {"role": "user", "content": ""}
        assert cup._extract_prompt_text(msg) == ""


class TestParseTranscript:
    def test_extracts_user_records(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {"type": "system", "message": "sys"},
                _make_user_record("first prompt"),
                {"type": "assistant", "message": "response"},
                _make_user_record("second prompt"),
            ],
        )
        records, total = cup._parse_transcript(str(transcript), 0)
        assert len(records) == 2
        assert records[0]["prompt"] == "first prompt"
        assert records[1]["prompt"] == "second prompt"
        assert total == 4

    def test_respects_offset(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                _make_user_record("first"),
                {"type": "assistant", "message": "r"},
                _make_user_record("second"),
            ],
        )
        records, total = cup._parse_transcript(str(transcript), 2)
        assert len(records) == 1
        assert records[0]["prompt"] == "second"
        assert total == 3

    def test_missing_file_returns_empty(self):
        records, total = cup._parse_transcript("/nonexistent/path.jsonl", 0)
        assert records == []
        assert total == 0

    def test_skips_empty_prompts(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                _make_user_record(""),
                _make_user_record("   "),
                _make_user_record("real prompt"),
            ],
        )
        records, _ = cup._parse_transcript(str(transcript), 0)
        assert len(records) == 1
        assert records[0]["prompt"] == "real prompt"

    def test_extracts_metadata(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                _make_user_record(
                    "hello", session="s1", timestamp="2026-06-02T12:00:00Z"
                ),
            ],
        )
        records, _ = cup._parse_transcript(str(transcript), 0)
        assert records[0]["session"] == "s1"
        assert records[0]["timestamp"] == "2026-06-02T12:00:00Z"
        assert records[0]["cwd"] == "/test"
        assert records[0]["git_branch"] == "main"


class TestOffsets:
    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cup, "_OFFSET_FILE", tmp_path / "missing.json")
        assert cup._load_offsets() == {}

    def test_load_invalid_json(self, tmp_path, monkeypatch):
        offset_file = tmp_path / "bad.json"
        offset_file.write_text("not json")
        monkeypatch.setattr(cup, "_OFFSET_FILE", offset_file)
        assert cup._load_offsets() == {}

    def test_roundtrip(self, tmp_path, monkeypatch):
        offset_file = tmp_path / "offsets.json"
        monkeypatch.setattr(cup, "_OFFSET_FILE", offset_file)
        cup._save_offsets({"s1": 5, "s2": 10})
        assert cup._load_offsets() == {"s1": 5, "s2": 10}


class TestMain:
    def test_empty_stdin(self, _patch_cup, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO(""))
        cup.main()
        assert not (_patch_cup / "user-prompts.jsonl").exists()

    def test_invalid_json(self, _patch_cup, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO("not json"))
        cup.main()
        assert not (_patch_cup / "user-prompts.jsonl").exists()

    def test_subagent_filtered(self, _patch_cup, monkeypatch):
        _make_stdin({"agent_id": "sub-1", "transcript_path": "/t.jsonl"}, monkeypatch)
        cup.main()
        assert not (_patch_cup / "user-prompts.jsonl").exists()

    def test_no_transcript_path(self, _patch_cup, monkeypatch):
        _make_stdin({"session_id": "s1"}, monkeypatch)
        cup.main()
        assert not (_patch_cup / "user-prompts.jsonl").exists()

    def test_missing_transcript_file(self, _patch_cup, monkeypatch):
        _make_stdin(
            {"session_id": "s1", "transcript_path": "/nonexistent.jsonl"},
            monkeypatch,
        )
        cup.main()
        assert not (_patch_cup / "user-prompts.jsonl").exists()

    def test_extracts_and_writes(self, _patch_cup, tmp_path, monkeypatch):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                {"type": "system", "message": "sys"},
                _make_user_record("hello"),
                {"type": "assistant", "message": "hi"},
                _make_user_record("goodbye"),
            ],
        )
        _make_stdin(
            {"session_id": "s1", "transcript_path": str(transcript)},
            monkeypatch,
        )
        cup.main()
        out = _patch_cup / "user-prompts.jsonl"
        assert out.exists()
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["prompt"] == "hello"
        assert json.loads(lines[1])["prompt"] == "goodbye"

    def test_offset_prevents_duplicates(self, _patch_cup, tmp_path, monkeypatch):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                _make_user_record("first"),
                {"type": "assistant", "message": "r"},
            ],
        )
        _make_stdin(
            {"session_id": "s1", "transcript_path": str(transcript)},
            monkeypatch,
        )
        cup.main()

        _write_transcript(
            transcript,
            [
                _make_user_record("first"),
                {"type": "assistant", "message": "r"},
                _make_user_record("second"),
                {"type": "assistant", "message": "r2"},
            ],
        )
        _make_stdin(
            {"session_id": "s1", "transcript_path": str(transcript)},
            monkeypatch,
        )
        cup.main()

        out = _patch_cup / "user-prompts.jsonl"
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["prompt"] == "first"
        assert json.loads(lines[1])["prompt"] == "second"

    def test_separate_sessions_independent(self, _patch_cup, tmp_path, monkeypatch):
        t1 = tmp_path / "t1.jsonl"
        _write_transcript(t1, [_make_user_record("from s1", session="s1")])
        _make_stdin(
            {"session_id": "s1", "transcript_path": str(t1)},
            monkeypatch,
        )
        cup.main()

        t2 = tmp_path / "t2.jsonl"
        _write_transcript(t2, [_make_user_record("from s2", session="s2")])
        _make_stdin(
            {"session_id": "s2", "transcript_path": str(t2)},
            monkeypatch,
        )
        cup.main()

        out = _patch_cup / "user-prompts.jsonl"
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_empty_agent_id_not_filtered(self, _patch_cup, tmp_path, monkeypatch):
        transcript = tmp_path / "t.jsonl"
        _write_transcript(transcript, [_make_user_record("hello")])
        _make_stdin(
            {"agent_id": "", "session_id": "s1", "transcript_path": str(transcript)},
            monkeypatch,
        )
        cup.main()
        out = _patch_cup / "user-prompts.jsonl"
        assert out.exists()
