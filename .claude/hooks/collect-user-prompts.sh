#!/bin/bash
cd "${CLAUDE_PROJECT_DIR}" || exit 0
python3 "$HOME/.claude/claude_utils/collect_user_prompts.py"
exit 0
