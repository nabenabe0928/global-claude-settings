#!/bin/bash
cd "${CLAUDE_PROJECT_DIR}" || exit 0
uv run python claude_utils/scripts/utils/collect_user_prompts.py
exit 0
