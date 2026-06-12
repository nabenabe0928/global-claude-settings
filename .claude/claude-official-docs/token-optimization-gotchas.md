---
accessed: 2026-05-26
---

# Token Optimization

## Primary Strategy: Subagent Architecture

Optimize the tools you use and subagent architecture designed to delegate the cheapest possible model that is sufficient for the task.

## Model Selection Quick Reference

Hypothetical setup of subagents on various common tasks and reasoning behind the choices:

| Task Type                 | Model  | Why                                        |
| ------------------------- | ------ | ------------------------------------------ |
| Exploration/search        | Haiku  | Fast, cheap, good enough for finding files |
| Simple edits              | Haiku  | Single-file changes, clear instructions    |
| Multi-file implementation | Sonnet | Best balance for coding                    |
| Complex architecture      | Opus   | Deep reasoning needed                      |
| PR reviews                | Sonnet | Understands context, catches nuance        |
| Security analysis         | Opus   | Can't afford to miss vulnerabilities       |
| Writing docs              | Haiku  | Structure is simple                        |
| Debugging complex bugs    | Opus   | Needs to hold entire system in mind        |

Default to Sonnet for 90% of coding tasks. Upgrade to Opus when first attempt failed, task spans 5+ files, architectural decisions, or security-critical code.
