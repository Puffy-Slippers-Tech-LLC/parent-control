# Task 14 final acceptance — 2026-09-06

Task 14 is accepted. One fresh current-input build and one complete registered
authorization-area attempt passed. No code correction or diagnostic rerun was
needed in this session. This accepts installed identity/authorization coverage;
it is not a complete system suite or graphical E2E/release pass.

## Commands and results

- Isolated six-module cleanup selection documented in `tests/README.md`:
  **49 passed, 3 subtests passed**; command session 25355 exited 0.
- `make build-test-artifacts OUTPUT_DIR=/tmp/onpc-test-artifacts/task14-final-20260906`:
  build and verification passed; command session 9454 exited 0.
- `pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-test-artifacts/task14-final-20260906 --area authorization`:
  dispatcher prerequisites **175 passed, 3 subtests passed**;
  controller session **98893** exited **0** after cleanup.
- `make check`: **1,293 unit tests and 17 private-D-Bus component tests passed**,
  with traceability and source checks; session 42905 exited 0.
- `git diff --check`: passed, including the final documentation edits.

Evidence: `/tmp/onpc-system-9670iwjl/evidence`.
`result.json` reports `all-checks-passed`, `cleanup_phase=complete`, and separate
passed product, infrastructure, collection and cleanup outcomes. JUnit contains
**2 installed + 2 rebooted + 229 authorization = 233 executions**, with no
failure, error or skip. Independent review compared the expected/executed
phase-and-case multisets exactly and confirmed no duplicate identities.

## Reviewed boundaries

The [finite coverage audit](Task-14-Coverage-Audit.md) defines the method/role and
requirement scope. All registered cases executed on these inputs. JUnit retains
four independent local eligibility denials (noninteractive and unsafe-name
administrators on child/kiosk), two real remote fixture classifications, and
all six remote direct boundaries returning `AccessDenied`. Remote identities
are NSS-resolved, nonlocal, nonsystem, unlocked, interactive, safe-name accounts
with the expected standard/admin roles. Authentication, requester disconnect,
recovery and in-flight deletion properties are retained in `authorization.xml`.
Reviewed collected broker log entries use redacted account labels and record
D-Bus and adapter outcomes. Existing raw evidence remains in its original storage.

## Input identity

| Input | SHA-256 |
| --- | --- |
| Source content (363 files) | `ae45d7d6227272a16c956b370ad8db78c9ffbfb3bedf6cd75bdf7903b753b14e` |
| Package | `5e831f4866dcab4e49a702c7ab8dbeb37b017b9c28a189fb037fa595a9aa99d4` |
| Fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |
| Selected test inputs | `0ef984b57058a505de0429108082d802dbb9b2ff9a0e137ae7a994f31cba5ca9` |
| Baseline provenance | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |

The build records revision `bf21d6dadcee419523b8755d1fcf446ff4618312` plus
then-uncommitted work. That work was committed externally during startup as
`a5ee2b3` (Task 14 checkpoint). The current checkout's source content digest
was recomputed and exactly matched the build; the commit changed no input
content. Only acceptance/handoff documentation changed afterward.

## Timing and final state

One attempt: preparation **71.783 s**, bootstrap **46.711 s**, installation
**50.176 s**, reboot **22.670 s**, tests **224.257 s**, collection **2.581 s**,
cleanup **98.528 s**; recorded stages total **516.706 s** (about 8.6 minutes).
The authorization phase itself took **191.303 s**. No repeated experiment or
unresolved Task 14 blocker remains.

The guarded runner restored and verified the retained baseline.
`virsh --connect qemu:///system domstate ubuntu26.04` independently confirmed
**shut off** after controller exit. All command sessions finished; no owned
operation remains. No host product/account changes or new VM were made.
Next implementation is Task 19A; reuse 19P's accepted backend and safety helpers.
