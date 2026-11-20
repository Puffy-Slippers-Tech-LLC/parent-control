# Product error detection task queue

[Master plan](../Error_Reporting.md)

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [x] | 001 | Make product failures visible to the runner | Baseline | Define and qualify one structured signal for dialog and silent failures, independent of the broker. | Installed check passed on both targets |
| [ ] | 002 | [Decide which faults fail a test](002.md) | 001 | Implement shared matching and automatic routing for unexpected faults and incomplete observation. | 1–3 h |
| [ ] | 003 | [Check for faults before every VM test passes](003.md) | 002 | Wire the evaluator into all three VM case routes and annotate deliberate fault steps before each route is enabled. | 3–6 h |
| [ ] | 004 | [Verify that unexpected faults reach repair](004.md) | 003 | Exercise installed pass and failure boundaries and verify exact-case repair dispatch and the zero-agent paths. | 1–3 h |
