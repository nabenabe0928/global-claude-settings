---
accessed: 2026-05-23
---

# Hooks Gotchas

## SessionStart: exit 2 stderr is invisible in practice

### The spec

- `SessionStart` **cannot block** the session (see exit code 2 behavior table in hooks.md).
- Exit code 2: "Shows stderr to user only" — but in practice, the TUI swallows this output. The user sees nothing in either the terminal CLI or the VS Code extension.
- Exit code 0: stdout is added as context that Claude can see. JSON output on stdout is parsed for structured fields.

### The fix: use `systemMessage` with exit 0

Instead of writing to stderr and exiting 2, exit 0 and print JSON with `systemMessage` to show a visible warning to the user. Add `additionalContext` if Claude should also see it.

```bash
#!/bin/bash
cat /dev/stdin > /dev/null
cd "${CLAUDE_PROJECT_DIR}" || exit 0

output=$(your-validation-command 2>&1)
if [ $? -ne 0 ]; then
  jq -n --arg ctx "$output" '{systemMessage: $ctx}'
fi
```

- `systemMessage`: warning message shown to the user.
- `hookSpecificOutput.additionalContext`: string injected into Claude's context at the start of the conversation.
