# 005a — Administrative bridge identity boundary

Acceptance: host

[Master](../Reliability-Plan.md) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Required tasks: none (Baseline).
Estimate: 15–30 minutes.

## Deliverable and route

Extract administrative-bridge identity controls from original 005. Read the
[bridge contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement),
`tools/session_limit_check.py`, complete identity/command callers and existing
host PAM/bridge tests. Reuse canonical process/unit fixtures; extend only
missing compositions.

The positive control binds the root system manager's transient unit, target
user, exact executable/arguments and verified process identity for
`systemd-stdio-bridge --user --quiet`. Ordinary terminal/SSH/GDM restrictions and
kiosk admission retain existing decisions. Names, environment and forged
arguments alone grant no exemption. Cover changed owner/unit/ancestry, wrong
target, command/argument substitutions and ambiguous or vanished process
identity at the existing validation boundary. Preserve supported executable
forms; do not broaden the PAM exception or fabricate product time.

## Acceptance and close-out

Run exact affected unit PAM/bridge selections through `tools/run-tests unit`,
with explicit timeouts, asserting accepted verified identity and refused
counterexamples. Fix demonstrated shared defects, retain expected/actual
evidence and follow master build/resource/cleanup rules. Close only 005a. Host
identity fixtures do not establish real package triggers; 005 owns the complete
installed retained-user history.
