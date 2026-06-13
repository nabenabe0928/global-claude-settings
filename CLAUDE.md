# Purpose

This repository is used to manage Claude Code's global settings.
The files under `./.claude/` is supposed to be copied to `~/.claude/`.

# Rules
- Test first, develop later. Test-driven development.
- Make sure the settings under `./.claude` works when copied to `~/.claude`.
- Use `$HOME` if possible. Avoid absolute paths as much as possible.
- Use `tests.sh` with `uv` to test Python scripts. Do NOT improvise commands by yourself.
- `copy.sh` is a user-only file, which copy the config files to `~/.claude/`.
