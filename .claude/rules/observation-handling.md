---
paths:
  - "**/observation.jsonl"
---

# Observation Data Handling

`claude_utils/workspace/observation.jsonl` is a log that stores every tool invocation in the project level.
Analyze the log to extract repeated patterns.

## Rules
- Present patterns and aggregates, e.g., tool frequency, session duration, error rates, instead of pasting raw JSONL records.
- Minimize repeated reads to avoid feedback loops. Reading `observation.jsonl` triggers a new observation entry.
  - Define the line range, e.g., from 1 to 100, to avoid an infinite loop.

# Observation Schema (`claude_utils/workspace/observation.jsonl`)

Each line is a JSON object with this shape:
```json
{
  "timestamp": "2026-06-02T12:00:00Z",
  "event": "tool_start | tool_complete",
  "tool": "Bash",
  "session": "session-id",
  "project_id": "abc123",
  "project_name": "my-project",
  "input": "...",
  "output": "..."
}
```

- `input` is present only when `event` is `"tool_start"`.
- `output` is present only when `event` is `"tool_complete"`.
