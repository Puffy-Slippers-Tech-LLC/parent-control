# Product error detection task queue

[Master plan](../Error_Reporting.md)

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | Make product failures visible to the runner | Baseline | Define and qualify one structured signal for dialog and silent failures, independent of the broker. | Installed check passed on both targets |
| [x] | 002 | Decide which faults fail a test | 001 | Implement shared matching and automatic routing for unexpected faults and incomplete observation. | Host checks passed |
| [x] | 003 | Check for faults before every VM test passes | 002 | Wire the evaluator into all three VM case routes and annotate deliberate fault steps before each route is enabled. | Installed checks passed on Ubuntu and Fedora |
| [x] | 004 | Verify that unexpected faults reach repair | 003 | Exercise installed pass and failure boundaries and verify exact-case repair dispatch and the zero-agent paths. | Ubuntu installed checks and repair handoff passed |
