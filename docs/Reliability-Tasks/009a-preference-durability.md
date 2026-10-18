# 009a — Preference write durability and retry

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract authoritative preference durability from 009. Read the
[state durability contract](../SystemDesign/State.md), complete
`broker/oh_no_parent_control/preferences.py` writer/merge logic, necessary
broker callers and canonical `test_preferences.py` tests. Use launcher-configured
private filesystem fixtures and narrow syscall doubles around the real writer.

Cover temporary write refusal, replacement failure and directory-flush failure,
each followed by an identical normalized request retry and a changed-value retry.
Confirmed saved values survive; unconfirmed writes are never acknowledged as
durable. A failed flush invalidates the successful-file-identity shortcut, so
an identical retry must perform required persistence work. Reopen the store to
distinguish cache success from persistence. Preserve writer locking, atomic
replacement, file/directory flush guarantees and unrelated record fields. No
host disk exhaustion, shared-path permission changes or new database is needed.

## Acceptance and close-out

Run exact affected unit and, when crossing that boundary, private-D-Bus component
selections through `tools/run-tests`, preserving timeouts. Assert reopened state,
acknowledgements and retry behavior with bounded privacy canaries. Repair
proven root causes, review resource changes, build as required and retain actual
passing evidence. Close only 009a. Selector fallback remains in 009; agent-locale
retry belongs once in 008a.
