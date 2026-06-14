---
paths:
  - "**/status-log/**"
---

# Cost Data Handling

`~/.claude/status-log/` stores per-session cost snapshots and daily/monthly summaries.
Analyze the log to extract spending patterns and trends.

## Rules
- Present patterns and aggregates, e.g., daily/monthly totals, per-project cost, model breakdown, instead of pasting raw JSONL records.
- Minimize repeated reads to avoid feedback loops. Reading cost data during a session triggers new cost entries.
  - Define the line range, e.g., from 1 to 100, to avoid an infinite loop.

# Directory Layout (`~/.claude/status-log/`)

```
status-log/
├── .sessions/             # Per-session snapshots (written by statusline.sh)
│   └── <session_id>.json
├── .session-tracker.json  # Last-recorded cost per session (avoids double-counting)
├── .status-log.lock       # File lock for concurrent access
└── YYYY-MM/               # Monthly directory
    ├── DD.jsonl            # Daily append-only log of session snapshots
    ├── summary.json        # Daily cost totals {"DD": <cost_usd>, ...}
    └── sessions.jsonl      # Compacted per-session final costs (created by cleanup after three month)
```

# Session Snapshot Schema (`.sessions/<session_id>.json`)

Written atomically by `statusline.sh` on every status update:
```json
{
  "date": "2026-06-14",
  "session_id": "session-id",
  "model_id": "claude-opus-4-6",
  "project_dir": "/path/to/project",
  "version": "1.0.0",
  "cost_usd": 0.42,
  "context_window_size": 200000,
  "used_token_percentage": 35,
  "input_tokens": 50000,
  "output_tokens": 20000,
  "cache_write_tokens": 10000,
  "cache_read_tokens": 30000,
  "effort": "high",
  "thinking": true,
  "agent_name": null
}
```

# Daily Log Schema (`YYYY-MM/DD.jsonl`)

Each line is a session snapshot (same schema as above), appended by `collect_cost.py` on every Stop hook invocation. Multiple entries per session are expected — the last entry holds the final cost.

# Summary Schema (`YYYY-MM/summary.json`)

Keyed by zero-padded day, values are cumulative USD cost deltas for that day:
```json
{
  "01": 1.23,
  "14": 0.85
}
```

- Each entry is collected by a `Stop` hook (`collect-cost.sh`) that reads the session snapshot and computes cost deltas.
- Subagent sessions are logged but excluded from the delta/summary computation to avoid double-counting.
- Old monthly directories (>3 months) are probabilistically compacted: daily JSONL files are replaced with a single `sessions.jsonl` containing the final cost per session.
