# Task 14: coverage audit, private writes and live approver lock

Scope: development host and the existing guarded `ubuntu26.04` VM. The
[finite coverage audit](Task-14-Coverage-Audit.md) records each method group,
requirement mapping and the concrete account-fixture gaps. Task 14 remains
incomplete; a complete registered authorization-area run is not a release pass.

## Implemented this session

- Extended the real-UID private-record helper with `private-write`: opening the
  exact child record with `O_WRONLY`, without creation, truncation or writing.
  A permission failure is required for both child records under all seven
  front-end role accounts. Missing files are errors, not false denial passes.
  Authoritative state is unchanged after the probes. Unit checks cover rejected
  arbitrary paths and write-open flags/error handling.
- Added child and kiosk cases that select a currently eligible parent, begin a
  real password prompt, lock that parent through AccountsService's public API,
  observe the lock and removal from discovery, submit the original password,
  and require denial with no preference, limit, grant or filter changes across
  all seven role accounts. Fixtures unlock the parent and restore preferences.
  Real PAM denial is recorded separately from broker post-authentication
  revalidation, which the existing role/preference mutation cases already prove.
- Registered exact password prerequisites for both new selectors and verified
  their execution identities. Added missing installed-suite references to
  BROKER-001/003/007; retained `planned` where full requirement coverage remains.

No product code, installed host configuration or saved-data schema changed.
Test helper/selector activation is next invocation. Existing artifact-helper
changes were preserved. The working-tree baseline advanced externally to
`bf21d6dadcee419523b8755d1fcf446ff4618312` during this session; this agent made no
commit. Captured input identities, rather than diff size alone, describe the run.

## Verification and experiments

Focused helper/selector checks: **117 passed**. Isolated runner/caller/agent
cleanup prerequisites: **30 passed** before each guarded attempt. Each installed
dispatcher additionally passed **175 tests / 3 subtests**. Final code's
`make check`: **1,284 unit/contract and 17 private-D-Bus component tests passed**,
plus stage traceability, syntax and source guards.

1. `/tmp/onpc-system-r6nobp_g/evidence`: **226/227 authorization cases passed**;
   all four package/reboot prerequisites passed. The new kiosk assertion raised
   `IndexError` after real PAM denial because it expected the child method's
   third result field. `RequestAccess` has only two output arguments. Corrected
   the assertion against the D-Bus XML, preserving state checks on both surfaces.
   Infrastructure, collection and cleanup passed; the runner correctly retains
   the pytest failure in its product outcome. This is diagnosed as a test bug,
   not evidence of a product authorization defect. Original failure retained.

Commands (second attempt uses the same commands with artifact suffix `-v2`):

```sh
/usr/bin/python3 -B -m pytest tests/unit/test_system_caller.py tests/unit/test_system_runner.py -q
/usr/bin/python3 -B -m pytest tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_agent_cleanup_safety.py -q
make check-system LIST=1 AREA=authorization TEST='test_request_rejects_locked_approver_during_authentication[child1]'
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-coverage-audit
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-coverage-audit --area authorization
make check
git diff --check
```

First build source: `3adaa667978e578b9d9d23d98caf84309e62f602aab8ac421f6e7ea71c7d8275`;
selected inputs: `77001a216c54713ad4ed0a72bd8c4a9e605f54253fbd39769fb4a455cc46cd7c`.
First run timings: preparation 71.9 s, bootstrap 45.7 s, install 50.3 s,
reboot 20.2 s, tests 176.3 s (authorization 143.5 s), collection 2.4 s,
cleanup 107.5 s. Context/token telemetry unavailable.

2. `/tmp/onpc-system-umj5ndg_/evidence`: corrected full authorization area
   **227 passed**, plus **four package/reboot prerequisites passed**. Exactly
   **231 expected executions**, no failures, errors or skips; all four outcome
   domains passed, `all-checks-passed`, cleanup phase `complete`. Both new cases
   recorded `denied` / `pam-authenticate`, then completed all state checks.
   All seven selected test/helper hashes match the checkout. Final mapping-only
   updates mark BROKER-002/004 covered; stage validation was rerun afterward.
   Other account/transaction requirements retain their documented gaps.

| Corrected input | SHA-256 |
| --- | --- |
| Source | `77f9d02d32ac956507eac4e7e7f1e44f201dfb63442fb95d6a5b8506348258fa` |
| Selected test/helper inputs | `579af84f3549f507e312c17b974358af29b1d7d786631ca55518bf17938dbbe1` |
| Package | `97b0759db1c879db90f486e2684d7ee1f3657313760a84afd8cd19d3d60fee3f` |
| Stable fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |

Corrected run timings: preparation 73.4 s, bootstrap 45.8 s, install 50.7 s,
reboot 19.1 s, tests 178.0 s (authorization 144.7 s), collection 2.5 s,
cleanup 104.1 s. Each complete attempt takes about eight minutes; preparation,
installation and restoration remain a larger cost than the authorization tests.
The next local predicate cases can be batched into one installed attempt; do
not repeat the completed method audit or qualify this lock transport again.

Scanned **4,106 / 4,141 public guest files** in the first/corrected attempts
for the six known ordinary parent/child and added standard/locked fixture
usernames: zero matches. This is a scoped identity scan, not exhaustive PII
validation. Private source logs and failed evidence remain intact. Read-only
artifact exports used the documented `onpc-test-artifacts` helper.

Final build session **43404**, checks **96333**, and VM **20356** exited **0**.
First VM session **64512** exited **1** with cleanup complete. All owned
operations finished; final `virsh` observation: **shut off**, retained baseline
restored. No VM operation is handed to the next session.

## Next session

Task 14 remains unchecked. Add independent noninteractive-admin and unsafe-name
admin eligibility cases using public account APIs, recording each authoritative
predicate to avoid passing only because a fixture is non-admin or locked.
Resolve how to exercise a real remote account without faking installed evidence;
the absence of such a fixture is explicit, not an undiscovered matrix question.
Then run changed cases and eventual final full-area acceptance as appropriate.

Next settings: **`gpt-5.6-sol` / `medium`**; model: keep; effort: keep. Real UID,
authentication, locking and cleanup helpers are proven. The remaining work is
account-fixture construction and predicate isolation, with no new concurrency
boundary currently identified. Reassess if the remote-account fixture requires
a new integration design.
