#!/usr/bin/env bash
# Notify when Claude Code finishes responding.
# macOS: native notification with sound
# Linux over SSH: terminal bell (triggers alert in Mac terminal emulator)

set -euo pipefail

# Consume stdin (hook contract) but we only need it for the summary
INPUT=$(cat)

# Skip notification for subagent stops (agent_id is present only inside subagents)
if echo "$INPUT" | jq -e '.agent_id' >/dev/null 2>&1; then
  exit 0
fi

SUMMARY=$(echo "$INPUT" | jq -r '
  [.assistant_message.content[] | select(.type == "text") | .text] | last //  "Done."
  | split("\n") | map(select(length > 0)) | first // "Done."
  | .[:100] | gsub("\""; "\\\"")
' 2>/dev/null || echo "Done.")

case "$(uname -s)" in
  Darwin)
    afplay /System/Library/Sounds/Glass.aiff &
    osascript -e 'display dialog "'"$SUMMARY"'" with title "Claude Code" buttons {"OK"} default button "OK"'
    ;;
  Linux)
    # Terminal bell — reaches the Mac terminal emulator over SSH
    printf '\a'
    # Also try notify-send for local Ubuntu sessions (non-SSH)
    if command -v notify-send &>/dev/null && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
      notify-send "Claude Code" "$SUMMARY" 2>/dev/null || true
    fi
    ;;
esac

exit 0
