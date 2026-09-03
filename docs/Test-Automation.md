# Test automation execution entry point

This is the stable entry point for the test-automation execution plan.

Before executing a task:

1. Read `AGENTS.md`.
2. Read this file.
3. Read [the master plan](TestAutomation/Test-Automation.md).
4. Locate the first unchecked task in the master plan and read only that task
   document. Do not read any other task document.
5. Report that task's recommended model and reasoning effort, then stop. Make
   changes only after the user switches to that model and effort and asks for
   execution.

When executing a task, execute exactly that one task, run only its stated
verification plus the required common checks, update its checkbox in the master
plan, append its completion record there, and stop. Never redo checked tasks or
execute a later task in the same session.

The master plan contains the overall summary, sequencing rules, shared
verification requirements, traceability rules, stable command interfaces, task
index, and completion records. The task documents contain the detailed work and
verification for their individual task.

Task documents: [master plan](TestAutomation/Test-Automation.md).
