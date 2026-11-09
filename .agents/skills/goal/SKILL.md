---
name: goal
description: Start a goal to keep solutions simple, lean and robust. Use when the user invokes $goal or requests this simplicity goal.
---

Use the goal creation tool to start a goal with this exact objective, equivalent
to invoking `/goal` with the following text:

> Simple, lean, robust; do not overengineer. Prefer solutions that simplify the resulting codebase as a whole, not merely minimize the patch. Keep refactoring within the task’s scope.

Do not set a token budget unless the user explicitly requests one. If an
unfinished goal already exists, preserve it and report that the new goal could
not be started.
