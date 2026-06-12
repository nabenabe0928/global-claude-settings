#!/bin/bash
cd "${CLAUDE_PROJECT_DIR}" || exit 0
python3 "$HOME/.claude/claude_utils/observe.py"
exit 0
