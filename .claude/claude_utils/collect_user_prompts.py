#!/usr/bin/env python3
"""Claude Code Stop hook — extracts user prompts from the session transcript."""

import json
from pathlib import Path
import sys


_OUT_DIR = Path("claude_utils/workspace")
_OUT_FILE = _OUT_DIR / "user-prompts.jsonl"
_OFFSET_FILE = _OUT_DIR / ".user-prompts-offset.json"


def _load_offsets() -> dict[str, int]:
    if _OFFSET_FILE.exists():
        try:
            return json.loads(_OFFSET_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def _save_offsets(offsets: dict[str, int]) -> None:
    _OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OFFSET_FILE.write_text(json.dumps(offsets))


def _extract_prompt_text(message: dict | str) -> str:
    if isinstance(message, str):
        return message
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _parse_transcript(transcript_path: str, offset: int) -> tuple[list[dict], int]:
    path = Path(transcript_path)
    if not path.exists():
        return [], 0

    records = []
    total_lines = 0
    with open(path) as f:
        for i, line in enumerate(f):
            total_lines = i + 1
            if i < offset:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if obj.get("type") != "user":
                continue
            prompt_text = _extract_prompt_text(obj.get("message", ""))
            if not prompt_text.strip():
                continue
            records.append(
                {
                    "timestamp": obj.get("timestamp", ""),
                    "session": obj.get("sessionId", ""),
                    "prompt": prompt_text,
                    "cwd": obj.get("cwd", ""),
                    "git_branch": obj.get("gitBranch", ""),
                }
            )
    return records, total_lines


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

    transcript_path = data.get("transcript_path", "")
    session_id = data.get("session_id", "")
    if not transcript_path:
        return

    offsets = _load_offsets()
    offset = offsets.get(session_id, 0)

    records, total_lines = _parse_transcript(transcript_path, offset)
    if not total_lines:
        return

    if records:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(_OUT_FILE, "a") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    offsets[session_id] = total_lines
    _save_offsets(offsets)


if __name__ == "__main__":
    main()
