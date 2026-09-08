# Task 19A — live fixture credentials and asset transfer

Solid progress: both planned live attempts completed successfully on the dev
host's existing guarded VM. Credential provisioning/staging now works against
the real guest disk and worker; the previously unaccepted asset transfer has a
complete passing attempt. Task 19A remains open for actual authenticated input,
reviewed prompt needles and the harmless public serial-console command.

## Implemented and verified

`FixtureCredentials` creates fresh independent secrets for the four canonical
fixture roles. The accepted baseline retains no plaintext setup password, so
the runner neither requests nor attempts to recover that password. Provisioning
is one-shot, same-lease, isolated and offline; the outer owner alone restores
the baseline. Fixed UID/shell checks precede the write. Private password files
use the established pinned-directory/exclusive-file implementation.

The supported [virt-customize password-file selector](https://libguestfs.org/virt-customize.1.html)
sets only fixture passwords, with networking disabled. Host OpenSSL receives
passwords on stdin and verifies the actual guest hashes without retaining hash
output in command artifacts. Full passwd bytes, non-fixture shadow rows, and
fixture password-aging fields must remain unchanged. Root is never a password
target. Failures latch worker refusal and emit fixed codes. The exact frozen
secret registry feeds variable staging and both private evidence collectors.
The clean-host dependency is pinned in the tool inventory and installed through
`setup.sh`; it was already present here. Activation is `none` on next invocation,
with no product data migration or accepted-baseline change.

The distribution contract now freezes bounded PNG/JSON pairs alongside Perl
sources, following the [public needle format](https://open.qa/docs/#_needles).
Tags, dimensions, rectangles, thresholds, file kinds and pair completeness are
validated before staging. Structural checks do not qualify pixels or prove
authentication: no real needle images have been added.

## Executed evidence

| Operation | Command handle / outcome | Preparation / test / cleanup / total seconds |
| --- | --- | --- |
| Fresh artifact build | 75192 / exit 0; `/tmp/onpc-test-artifacts-k4h7pwbw` | A few seconds; exact total not retained |
| Credential qualification, attempt 1 | 30139 / exit 0; `tools/run-tests integration check_graphical_credentials` | 391.116 / 109.406 / 73.382 / 714.458 |
| Transfer qualification, attempt 5 overall | 63823 / exit 0; `tools/run-tests e2e --qualify-transfer --artifacts /tmp/onpc-test-artifacts-k4h7pwbw` | 397.476 / 110.868 / 73.203 / 722.379 |
| Final focused host checks | 88090 / exit 0; six credential/needle/worker/smoke modules | 187 passed in 0.89 s |
| Final `make check` | 1248 / exit 0 | 2,316 unit/contracts in 43.63 s; 17 components in 0.46 s; syntax/traceability passed |

Each live dispatch independently passed 339 isolated cleanup prerequisites and
three subtests before VM access. An earlier isolated safety run also passed;
the final focused selection includes the strengthened role-specific guard.
There are 46 new regressions relative to the previous 2,270-test baseline.
`git diff --check` passed after the handoff edits.

Total live runtime was 1,436.837 seconds (23.95 minutes). The approximately
140-second difference between stage sums and total in each run includes held-
lease finalization; it is not worker execution. This session exceeded the
planned 25–40-minute slice to complete both attempts, review and cleanup.
No usage telemetry was available. Estimate two further sessions / 2–3 hours
for the remaining 19A integration and acceptance, including real VM waits.

Retained root-private evidence:

- Credentials: `/tmp/onpc-graphical-smoke-3u3p2hte/result.json`;
  checkpoints `/tmp/onpc-e2e-evidence-6295u6jb`;
  worker `/tmp/onpc-e2e-evidence-67k57s2s/worker-result.json`.
- Transfer: `/tmp/onpc-graphical-smoke-oithe0ub/result.json`;
  checkpoints `/tmp/onpc-e2e-evidence-aai7um3_`;
  worker `/tmp/onpc-e2e-evidence-jnuqr5na/worker-result.json`.

Both report infrastructure, collection and cleanup passed; source and host
preservation true; `lease_phase=complete`; product not run. Both worker reports
have no failures and confirm worker/callback cleanup. Transfer delivered 44
files in 92 total tree entries; the booted receipt matched offline verification:
`20ffcf173f50948866dc4c59841063403a675618adda9e4f4c7fd8f1a32cbdd6`.
The user confirmed concurrent editing had ended before these attempts. The
earlier four transfer failures, including [attempt 4's source refusal](19A-Asset-Observation-20260907.md),
remain failures; this is a new corrected-input qualification.

## Inputs and visual findings

Both live runs used revision `5fe25e39d5001289b390c3d3da6320d5f1393506` plus
the recorded uncommitted source bytes:

- Source SHA-256: `3985bbf54b72c13637c38db3d317aeb95b7dd0d30203941e1888b6c0315881f7`.
- Baseline SHA-256: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
- Transfer package SHA-256: `fe8963635dd93fa56a03d05df0011db2e051bda974ab3345ed21407c9edef146`.
- Transfer staged-assets SHA-256: `936d291fadd9e6e557f5926ee123b28170e4a4956516caba0bd9dff74f51c5ef`.
- Live distribution SHA-256: `5c9bdd94976b2f725354b7e94f0b7be43a1e2efd43284fe4f5cc25e7394c189d`.

Private review of all three screenshots from each run confirmed the account
list, selected empty password field and Escape return. The feasibility geometry
selects an unrelated baseline account, not a fixture. Those captures contain
non-fixture identities and remain private; they are not approved public needle
assets. All six review exports were removed with `tools/cleanup-screenshots`.
Original screenshots, vars and logs were not modified or deleted.

After that review, the password helper and needle validator were tightened to
require `onpc-<surface>-<role>-masked-password`. One match must establish the
intended fixture identity and its empty, focused, masked field together. Generic
password-field tags refuse. This post-live change is host-tested only; neither
live run entered a password or exercised a real needle. Final relevant hashes:

| File | SHA-256 |
| --- | --- |
| `tests/e2e/fixture_credentials.py` (unchanged after live runs) | `3adb9b59bf29241899eed2946ce4d8c5c25ff015396057ccfb31c114e0c1482d` |
| `tests/e2e/e2e_worker.py` | `df7be7e51e11280721286d380a63b429a9dd964ca321ef926f33bbbc71178eb9` |
| `tests/integration/graphical_smoke/lib/onpc_password.pm` | `c337ee2394ef37003e8911ce56b67c0546dd2939cc55f9022afa7ce378bee9ed` |
| `tests/unit/test_e2e_needle_inputs.py` | `0c7a25903d9aac3521f0b233a9948bf92dd22e6cae2dd8d241b329004c1d63a2` |
| `tests/unit/test_e2e_secret_variables.py` | `ecbbc75cf2af05f222b901000440b7cf36ce656961a6a6ef8d4d862e456d6197` |

Subsequent edits were documentation only. The artifact directory above is
historical, not nominated for another run; current source includes the stronger
role guard and handoff edits. Do not repeat unaffected transfer work merely to
resume. Next build reviewed fixture-account/prompt needles and the public serial
smoke, using these credential, worker, observation and provenance interfaces.
All 156 customer variants remain pending. All command handles exited, both
leases completed, and the final `tools/test-vm status` returned `state=5`, `id=-1`.
No VM/backend/controller recovery or outstanding operation remains.

## Forecast correction after user review

The two-session / 2–3-hour forecast above is historical and withdrawn. The user
correctly identified repeated similar forecasts across earlier handoffs. Those
sessions added implementation and safety coverage, but transfer stayed blocked
until this session and actual authentication/serial execution is still absent.
This session's two live passes are concrete progress; additional regression
counts do not establish how close all of 19A is to completion. The public
launcher's explicit unfinished-controller refusal also remains and was omitted
from the latest summary of remaining work. The active handoff now tracks live
authentication, serial execution, and launcher/evidence acceptance explicitly.
This correction changed documentation only; no tests or VM attempts were rerun.
