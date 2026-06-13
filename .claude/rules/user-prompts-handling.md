---
paths:
  - "**/user-prompts.jsonl"
---

# User Prompt Data Handling

`claude_utils/workspace/user-prompts.jsonl` is a log that stores every user prompts in the project level.
Analyze the log to extract repeated patterns.

## Rules
- Present patterns and aggregates, e.g., tool frequency, session duration, error rates, instead of pasting raw JSONL records.
- Minimize repeated questions to avoid feedback loops. Another user prompt adds another line to `user-prompts.jsonl`.
  - Define the line range, e.g., from 1 to 100, to avoid an infinite loop.

# User Prompts Schema (`claude_utils/workspace/user-prompts.jsonl`)

Each line is a JSON object with this shape:
```json
{
  "timestamp": "2026-06-02T12:00:00Z",
  "session": "session-id",
  "prompt": "the user's message text",
  "cwd": "/path/to/working/directory",
  "git_branch": "main"
}
```

- Each entry is collected by a `Stop` hook (`collect-user-prompts.sh`) that parses the session transcript.
- Subagent sessions are skipped (non-empty `agent_id`).
- `.user-prompts-offset.json` is used to avoid re-processing lines across multiple Stop events in the same session.
