#!/bin/bash
cd "${CLAUDE_PROJECT_DIR}" || exit 0
"$HOME/.claude/venv/bin/python3" "$HOME/.claude/claude_utils/collect_user_prompts.py"
exit 0
