# Task 19A — public controller acceptance

**19A accepted. Solid progress:** a declared real public-controller case now
passes preparation, authenticated serial execution, scenario evidence validation,
owned shutdown, restored-baseline verification, release and final invocation
reporting. The first attempt found a missing preparation input; its correction
is covered by a regression executing the actual bootstrap implementation.
This closes the remaining composition gap from the
[public-dispatch handoff](19A-Public-Dispatch-20260907.md).

The original 156 variants remain pending, including E2E-001. The additional
`E2E-034/serial-controller` is a runner qualification, not customer coverage or
stable screen-matching acceptance. There are now 34 families / 157 variants.

## Changes and the demonstrated defect

`controller_qualification.py` uses the existing serial worker, asset and
credential provisioners, recorder and sole lease owner. It records each real
stage before acknowledging the next guest input. The fixed read-only `boot`
probe hashes the guest kernel boot identifier; all eight stage observations
must agree. It creates no session aliases or authentication outcomes.

Attempt 1 failed before boot because `execution.attempt` omitted
`input/selected-inputs.json`, which `system_runner.bootstrap` hashes into the
guest observation marker. Read-only inspection confirmed that the failed raw
directory contained assets, private diagnostics and SSH keys, but no input
directory. The earlier host tests had substituted bootstrap and missed this
dependency. The controller now stages/fsyncs a 0600 selected-input document in
a 0700 directory before acquiring the VM. The regression runs the actual
bootstrap against substituted offline guest operations and verifies the marker
digest. Credential-bearing selections also check the existing OpenSSL pin
before VM acquisition, restoring the older qualification's prerequisite check.

Activation is development-only `none` (next invocation). No product, saved-data,
host setup, transport, process-cleanup or accepted-baseline implementation was
changed. No new VM, overlay, snapshot, checkpoint, cleanup owner or launcher
override was introduced.

## Live attempts and host verification

Both attempts used the ordinary public route:

```sh
tools/run-tests e2e --artifacts <fresh-verified-build> --scenario E2E-034
```

| Check / handle | Result | Measured timing |
| --- | --- | --- |
| Initial focused four-module checks / 76581 | 217 passed | 1.51 s |
| Initial `make check` / 84418 | 2,500 unit/contracts, 17 components, syntax and stage traceability passed | 46.33 s / 0.38 s |
| Attempt 1 / 10689; artifacts `4gg3869u` | Failed on missing bootstrap input; no guest boot; restoration completed; exit 1 | Preparation 82.441 s, test 0 s, cleanup 76.388 s |
| Bootstrap regression batch | Actual bootstrap regression passed; three public-entry tests initially failed because their test-local OS substitute omitted real `fchmod`/`fsync`; corrected to preserve those functions | Corrected 41 passed / 0.62 s |
| Intermediate `make check` / 56338 | 2,501 unit/contracts and 17 components passed | 44.80 s / 0.36 s |
| Final controller checks | 42 passed, including the credential-pin refusal | 0.59 s |
| Attempt 2 / 33292; artifacts `b2jqhuan` | Passed exact selection, all evidence and cleanup; final public output passed; exit 0 | Preparation 403.435 s, test 667.579 s, cleanup 77.295 s; invocation report interval 1,520.246 s |
| Final `make check` / 14188 | 2,502 unit/contracts, 17 components, syntax and stage traceability passed | 39.23 s / 0.32 s |
| `git diff --check` | Passed after documentation completion | No VM work |

The guarded dispatcher independently ran isolated cleanup prerequisites before
each attempt: 443 tests plus three subtests, then 445 tests plus three subtests.
There are **17 new host regression cases** relative to the prior handoff.
Both artifact builds (70871 and 24973) exited successfully. The two different
source identities produced the same product package bytes; manifests were never
edited to reuse stale provenance.

Attempt 2's worker took **49.395 s** and returned backend exit 0, no fatal
artifact, no failures, `worker_stopped=true`, `callback_closed=true`, and
`shutdown_verified=true`. Its unchanged distribution digest equals the retained
[shutdown qualification](19A-Shutdown-20260907.md). One corrected successful
composition attempt is sufficient here: neither graphical nor cleanup transport
changed. Task 19B still owns three complete qualification attempts for its new
screen/readiness behavior.

The invocation interval comes from its started/terminal report timestamps; it
excludes the tiny subsequent close/print interval. Timed stage sums leave
approximately **371.938 s** of finalization/provenance work unbucketed. The
667.579 s test bucket also includes offline fixture setup and preservation
checks; it is not serial interaction time. This is a measured lead for 27C/28A,
not permission to skip guards or cache the baseline proof. The slice exceeded
its initial 15–30-minute audit budget to implement the missing live composition,
fix the demonstrated defect and finish both complete attempts. No total session
duration or token telemetry was recorded.

## Retained identities and evidence

Original failed attempt:

- Build `/tmp/onpc-test-artifacts-4gg3869u`.
- Invocation `/tmp/onpc-e2e-evidence-ycwdjge0`.
- Attempt `/tmp/onpc-e2e-evidence-r4teetix`; raw `/tmp/onpc-e2e-attempt-yonip78m`.
- Source `929b4c63582f7c0ce5434f9c06743e9d7044421e914630a09b5027f9f715efa9`.

Accepted attempt:

- Build `/tmp/onpc-test-artifacts-b2jqhuan`.
- Invocation `/tmp/onpc-e2e-evidence-53cr_gf8`.
- Scenario `/tmp/onpc-e2e-evidence-5qi949rz/acceptance.json`.
- Worker `/tmp/onpc-e2e-evidence-0exvqvlp/worker-result.json`.
- Raw `/tmp/onpc-e2e-attempt-shjo6t1b`, retained privately, not approved for export.
- Run `scenario-7938bd31aed743d4a4d775baafca2c17`.

| Accepted input | SHA-256 |
| --- | --- |
| Source | `534bcfa5622c30063e192132dbe0605759b61b2d2f3499f1d8e3594bf7a09b3a` |
| Inventory | `dc5ccd5e954dc2f8b0ce188b1d89cde15865e4113cbab1244e220dc74f1456d4` |
| Package | `65ad9d3fe797ffc7ddd05e5a8bac56302264841098a8f850d970f4db3052ae61` |
| Staged assets | `5cd902b1eb498d612f1543f62835f29485aef4e4ee4759fd3852419a8d059510` |
| Baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Worker distribution | `d09250a0a279ad8e001ade0b5bc01d3187d6df8aa911e9a94613d04051669d08` |
| `execution.py` | `175c30676e1598797eb54b29e2259928e5639159154e180b7c48ec121f59652f` |
| `controller_qualification.py` | `db51645b84eab4d56592059e22521b4efaff765a6a7b1507f2ffbb7fa70a7d95` |
| `guest_observations.py` | `f4ccc76df735daee1fa56227aba315003ed3e8b18f16362a934645d140a1c596` |
| `observation_transport.py` | `d20b041e8066b245d338cd3b43790e0fc745678e05549ffd01620829d8fa9cb3` |
| `test_e2e_execution_cleanup_safety.py` | `e0b3d044b119b7c0da977c5607ba15a57869cd5cfbd29e77aa3115ed4a57d7ef` |
| `test_e2e_controller_qualification_cleanup_safety.py` | `bd34e19227d9f24f9708ee96c2cad2cb4d77d43781fedfd2168fc6ac7aa22948` |

The final record contains 11 ordered steps, three passing assertions, 15
reviewed/secret-checked artifacts and no failures. Setup is explicit provisioning;
start records the actual boot; the seven worker stages distinguish observation
from guest input; end records actual backend shutdown; the sole outer reset is
the final cleanup step. The worker lifecycle is
`initial-off → poweron → poweroff → status-off → status-off → poweroff`;
the last poweroff is the existing idempotent backend stop, not a reset.

Private artifact review verified four provisioned passwords with unrelated
accounts preserved, 44 transferred files / 92 total entries, actual serial
command/session evidence, no remaining non-observer user session after logout,
and eight identical boot observations. Three 1024×768 capture records show a
changed selected screen and an exact return to the initial digest on dismissal.
Only dimensions/digests are collected as screen evidence here; no raw images,
passwords, account names, terminal output or vars were exported. This is metadata
and controller-composition review, not new pixel/needle acceptance.

## Audit of the eight 19A deliverables

| Deliverable | Acceptance basis |
| --- | --- |
| 1. Qualified backend and sole lease owner | Retained 19P compatibility/three-smoke proof; unchanged worker distribution and lease bridge; current run uses the same owner and public transport. |
| 2. Worker, console, configuration, observation and pinned tooling | Maintained worker/distribution, read-only programs and public launcher; existing backend/credential pins, current serial worker pass and actual bootstrap regression. |
| 3. Baseline, verified transfer and public command | Current public selection verifies fresh source/package assets and exact baseline, copies all expected entries, then restores the baseline. Host guards reject `VM_IMAGE`, checkpoint/resume and pending selections. |
| 4. Input/observation/provisioning separation | Actual guest mouse/keyboard and serial command; fixed probes corroborate session/boot state. Offline credentials/assets/getty are declared setup, with no manufactured grant/session/expiry outcome. |
| 5. Secret-safe credentials and capture | Existing [secret contract](19A-Secret-Boundary-20260907.md), retained live [positive/negative authentication](19A-Authentication-20260907.md), current same-lease serial authentication and secret-checked private artifacts. Other roles/surfaces remain their owning tasks' work. |
| 6. Bounded operations, interruption, collection and cleanup | Current isolated safety suite and full host checks; retained ownership/replacement/refusal cases; first live preparation failure safely restored; corrected live worker and outer cleanup passed. |
| 7. Fresh serial command, evidence and shutdown | E2E-034 executed all eight worker stages and accepted actual scenario records after restoration/release; final invocation output and exit 0 establish completion. |
| 8. Enumerable declarations and evidence | Existing inventory/evidence tests plus current exact case reconciliation. Original 156 cases remain pending; E2E-034 adds a harness guarantee without accepting E2E-001 or customer work. |

All owned command handles exited. An intentional chat interruption was resumed
through the same handle 33292; no duplicate attempt or recovery was started.
Final read-only VM status returned `state=5, id=-1`. No screenshot exports,
log modifications, setup refresh, or outstanding operation remains.
Subsequent changes are documentation only and invalidate package-artifact reuse
under the current full-source contract; build fresh inputs for the next VM run.

**Remaining 19A: zero sessions.** Continue with 19B's stable screen matching and
E2E-001, reusing this public execution/recording proof. Preliminary 19B estimate:
**two substantial sessions / 3–5 hours**, moderate-to-low confidence. Three full
qualifications alone may take about 75 minutes at the measured controller cost;
needle/readiness development and corrections are additional. Do not re-investigate
public dispatch or rerun the unchanged serial qualification just to resume.
