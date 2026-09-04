# Task 26 — Failure, concurrency, persistence, and recovery

Execute 26A and 26B separately. Reuse existing failure controls; add a new control
only at a maintained public guest OS boundary. No hidden production injection
method or authorization bypass is permitted.

## Task 26A

- Title: Prove adversarial transaction races and failure recovery.
- Depends on: Task 25B.
- Complexity: very high. Controlling stale identities, concurrent requests, and
  irreversible side effects across real services is the hardest remaining
  cross-component correctness task.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `xhigh`
- Work:
  1. Inventory existing evidence and complete the matrix for invalid/unauthorized
     calls, Polkit denial/cancel, requester disconnect, account/role/preference
     changes during authentication, usage-query failure, broker restart, agent
     failure, fapolicyd reload failure, and process-termination failure.
  2. Synchronize at observable public boundaries with bounded deadlines. Prove
     each intended failure actually occurred, rather than inferring it from a
     generic error or using a timing sleep.
  3. Verify reversible failures restore prior state and failed rollback read-back
     is reported distinctly. After partial process termination, keep strict
     blocks and required prior time while other users remain untouched.
  4. Interleave policy saves, approvals, revocations, and session preparation.
     Prove single-flight serialization, exactly-once grant changes, replacement-
     grant precedence, and repeat-interval consumption only after success.
  5. Verify displayed failures are actionable and expose no internal paths,
     service names, account PII, or backend details on both request surfaces.
  6. Publish a failure-case/evidence matrix and reusable assertions for 26B.
     Update failure, concurrency, and rollback mappings.
- Verification:
  - Run each new controller's cleanup-safety regressions in isolation first.
  - Run each destructive failure/race from a separate fresh overlay; compare
    authoritative before/after snapshots and redacted evidence.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<transaction-failures>`,
    `make check`, and `git diff --check`.
- Completion criteria: the failure/race matrix is deterministic, fail-closed,
  and supported by evidence of the actual triggered boundary.

## Task 26B

- Title: Complete restart and persistence scenarios.
- Depends on: Task 26A.
- Complexity: medium. Restart boundaries and expected state are specified and
  reusable failure/guest controls now exist.
- Recommended Codex model: `gpt-5.6-terra`
- Recommended reasoning effort: `medium`
- Work:
  1. Restart Parent, both request surfaces, the broker, affected user sessions,
     package services, and the VM using the established guest controllers.
  2. At each boundary verify per-child preferences, shared choices, separate
     mute values, grants, extension publication, and enforcement. Distinguish
     durable data from derived state using `System-Design.md`.
  3. Verify recovery from a prior safe denial without retaining authorization or
     applying an obsolete grant/policy. Reuse 26A's state assertions.
  4. Update persistence/restart mappings and the boundary/evidence matrix.
- Verification:
  - Run cleanup-safety regressions in isolation before restart controllers.
  - Run restart cases in fresh overlays; correlate visible results with
    authoritative state and boot/session identities.
  - Run `make check-e2e VM_IMAGE=<verified-baseline> SCENARIO=<persistence>`,
    `make check`, and `git diff --check`.
- Completion criteria: every specified persistence boundary is exercised with
  independent child state and correct recovery.
