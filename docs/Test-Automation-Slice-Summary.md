# Test automation slice summaries

The launcher appends one end-of-session report here, with completion time in the
session heading and five fields: Task, Duration, Completed, Verification and
cleanup, and Next session. Follow the
[summary format](TestAutomation/Unattended-Sessions.md#cumulative-session-summaries).
Session 41 illustrates it; earlier entries retain their historical format.
This is an operator log, not context for future sessions.
The launcher never reads or rewrites previous entries. Implementation workers
must exclude this file from reads, searches, diffs and edits.

## Session 84 — 2026-09-13 22:22 PDT

- Task: Task 15A — immutable generation ownership for native execution admission.
- Duration: 12 minutes
- Completed: Implemented and locally qualified ProbeGeneration: private witness copies, pinned inode/digest verification, mutation refusal and replacement-safe cleanup retries. Updated the owning contract, reuse map and docs/TestAutomation/Task-15.md handoff. Native lifecycle integration and installed acceptance remain unfinished.

- Verification and cleanup: Passed 398 focused tests, 981 isolated safety tests plus 3 subtests, and 67 native component cases. Corrected an initial logger-domain collection error and a native fixture permission refusal; the corrected runs passed. All 206 documentation links and scoped whitespace checks passed. All commands exited and owned process/socket/filesystem cleanup completed. No VM/systemd attempt or Task 20 recovery work ran.

- Next session: Continue Task 15A: integrate generation ownership, channel admission and manager binding into retained run/recover state, including shared deadlines and terminal identity checks. Then qualify guarded systemd behavior. Next settings: gpt-6-astra/high, Standard.


## Session 85 — 2026-09-13 22:41 PDT

- Task: Task 15A: integrate native probe admission into retained execution/recovery. Installed acceptance and policy receipts remain unfinished.
- Duration: 14 minutes
- Completed: **Solid and healthy** — Integrated retained native admission, shared deadlines, terminal validation and guarded cleanup. Interrupted collection now preserves its retained frame without replay or outcome promotion. Updated the owning contract, reuse map and docs/TestAutomation/Task-15.md handoff.

- Verification and cleanup: Final checks passed: 568 focused tests; 1,011 isolated cleanup-safety tests plus 3 subtests; 80 private-bus/native component tests; 208 documentation links and staged/unstaged whitespace checks. No new test failures. All commands exited and owned process, bus, socket and directory teardown completed. Full native lifecycle uses synthetic manager/channel coverage; real systemd qualification, VM runs and full make check were not performed. Source identities and exact selections are retained in the handoff.

- Next session: Task 15A remains earliest ready. Package the fixed native payloads and provision their private runtime root, then qualify complete systemd success/failure/cleanup through the guarded installed runner. Next settings: gpt-6-astra/high, Standard.


## Session 86 — 2026-09-13 22:51 PDT

- Task: Task 15A — native probe packaging and runtime prerequisites.
- Duration: 10 minutes
- Completed: **Solid and healthy** — Packaged the native gate, witness and three probe modules; added the preserved private runtime-directory declaration. Fixed activation hashes becoming stale after ELF stripping. Updated owning contracts, reuse links and docs/TestAutomation/Task-15.md. Task 15A remains unchecked pending installed qualification.

- Verification and cleanup: 88 tests and 7 subtests passed. Corrected a misplaced test assertion that initially failed three variants. Two Debian builds completed; the first package’s digest mismatch is retained as failed evidence. All 110 activation digests match the corrected extracted package. All 241 documentation links and staged/unstaged whitespace checks passed. Artifact identities and reproduction details are in the active handoff. Every command exited; evidence retained, no pending cleanup. No VM/systemd attempt, full make check, denial or Task 20 R1 charge.

- Next session: Continue Task 15A: add the guarded installed case, validate safety and collection locally, build fresh test artifacts, then qualify real-systemd provisioning, admission success/failure and cleanup. Next settings: gpt-6-astra/high, Standard.


## Session 87 — 2026-09-13 23:11 PDT

- Task: Task 15A — qualify native probe creation, admission and retained cleanup with real systemd.
- Duration: 16 minutes
- Completed: **Solid and healthy** — Added the guarded native-probe scenario and reached its first installed qualification boundary. Creation failed before admission; added locally verified, privacy-safe D-Bus error-name retention to discriminate the cause next. Updated owning contracts, reuse links and docs/TestAutomation/Task-15.md. Task 15A remains unchecked.

- Verification and cleanup: Four package/reboot prerequisites and runtime provisioning passed. The lifecycle failed with create-uncertain, no job identity and incomplete adapter recovery; refusal and subsequent-success stages did not execute. Evidence: /tmp/onpc-system-7owbex3p/evidence/result.json and guest-results/enforcement.xml. Outer cleanup restored and verified the baseline; all commands exited. Final checks passed: 238 focused safety tests, 296 collector/runner tests, 1,024 launcher safety tests plus 3 subtests, and 13 private-bus tests. Selector and temporary local-lease refusals were resolved. Links and whitespace passed. No execution/Polkit denial or R1 recovery charge. Diagnostic edits postdate the failed artifact; full task acceptance and make check remain outstanding.

- Next session: Continue Task 15A: build fresh artifacts and run test_native_probe_systemd_lifecycle with the new diagnostic field. Distinguish API, authorization and transport failure before correcting behavior; never reroute a denial. This will be composition attempt 2. Namespace, restart retention and full launch acceptance remain open. Next settings: gpt-6-astra/high, Standard.


## Session 88 — 2026-09-13 23:24 PDT

- Task: Task 15A — classify installed native-probe creation failure and select a bounded correction.
- Duration: 13 minutes
- Completed: **Solid and healthy** — Attempt 2 identified an API PropertyReadOnly rejection. The source audit implicates JobTimeoutUSec setter fallthrough; the exact rejected property remains inferred. Saved the evidence and a supported timeout-delivery correction candidate in docs/TestAutomation/Task-15.md, the owning contract, reuse map and continuation. Task 15A remains unchecked.

- Verification and cleanup: 320 focused safety tests and the runner’s 1,024 safety tests plus 3 subtests passed; artifact build passed. The guarded run passed four prerequisites but failed probe creation and adapter recovery; refusal/fresh-success stages did not execute. Evidence: /tmp/onpc-system-2vsowz65/evidence/result.json. Filesystem-blocked JUnit access succeeded through the approved artifact exporter. Outer collection, restoration and full backing verification passed; every command exited. All 214 documentation links and staged/unstaged whitespace checks passed. Full make check and task acceptance remain outstanding; no Polkit denial or R1 recovery charge.

- Next session: Continue Task 15A: implement the package-owned timeout drop-in, verify equivalent queue bounds and refusal behavior locally, then qualify fresh artifacts with test_native_probe_systemd_lifecycle. No unchanged diagnostic rerun. Next settings: gpt-6-astra/high, Standard.


## Session 89 — 2026-09-13 23:33 PDT

- Task: Task 15A — correct the transient probe timeout defect and prepare native lifecycle qualification.
- Duration: 9 minutes
- Completed: **Solid and healthy** — Implemented the packaged four-second queue timeout, effective-value admission refusal, cleanup-preserving collection and activation coverage. Updated owning contracts, reuse map and docs/TestAutomation/Task-15.md. Live qualification and full Task 15A acceptance remain unfinished.

- Verification and cleanup: Passed 299 isolated safety tests, 265 package/collector tests with 7 subtests, 1,036 runner safety tests with 3 subtests, and 13 private-bus tests. All 409 documentation links and whitespace checks passed. Artifact building was stopped before invocation because current collectors lack the required operator-log exclusion. No new build, VM attempt or make check ran. Every started command exited; local cleanup completed. R1 implementation/recovery ledger remains unchanged.

- Next session: Task 15A: correct the explicit operator-log exclusion consistently in artifact-builder and controller source selection, preserving product-input integrity; then build fresh artifacts and run test_native_probe_systemd_lifecycle as composition attempt 3. Both previous failures remain retained. Continuation.md records the next action. Next settings: gpt-6-astra/high, Standard.


## Session 90 — 2026-09-13 23:42 PDT

- Task: 15A: resolve source-selection prerequisite for native lifecycle qualification.
- Duration: 7 minutes
- Completed: **Solid and healthy** — Implemented matching operator-log exclusions in artifact builder/controller, preserving other source-change detection. Updated contracts, reuse map and docs/TestAutomation/Task-15.md. Task 15A remains unchecked.

- Verification and cleanup: 78 focused provenance/artifact tests passed; no failures or skips. Verified no-open/no-copy behavior, matching digests and other-source mutation refusals. Documentation links and explicitly scoped whitespace checks passed. All commands exited; no VM operation started or cleanup remains. Full make check, fresh build and installed qualification remain outstanding.

- Next session: Task 15A remains earliest ready. Build fresh artifacts and run guarded test_native_probe_systemd_lifecycle attempt 3 with timeout readback and cleanup verification. Two previous failures remain retained; Task 20 R1 ledger is unchanged. Next settings: gpt-6-astra/high, Standard.


## Session 91 — 2026-09-13 23:54 PDT

- Task: Task 15A: qualify the corrected native probe lifecycle on real systemd.
- Duration: 12 minutes
- Completed: **Solid and healthy** — Composition attempt 3 passed native success, withheld admission and fresh success, with effective 4,000,000 µs timeout and owned cleanup. Updated the owning contracts, reuse map and docs/TestAutomation/Task-15.md handoff. Both earlier failures remain retained. Policy receipts and full native/Snap/Flatpak acceptance remain open.

- Verification and cleanup: Passed 299 focused safety tests, fresh artifact build/verification, 1,036 runner safety tests plus 3 subtests, and all five selected installed executions. Evidence: /tmp/onpc-system-jq_9bl4m/evidence/result.json and sibling guest-results/enforcement.xml. Private JUnit access was filesystem-blocked; approved export succeeded. All commands exited; collection, cleanup and full restored-baseline verification passed. Documentation checks passed: 241 links, zero missing, clean whitespace. Full make check and complete Task 15A acceptance were not run. Only documentation changed after execution; fresh artifacts are required for the next run.

- Next session: Task 15A remains earliest ready; none bypassed. Qualify writable probe storage inside the packaged broker service namespace and generation preservation across stop/restart, with local ownership/refusal checks before fresh guarded execution. Continuation.md records the selection. R1 remains uncharged with no decision hold. Next settings: gpt-6-astra/high, Standard.


## Session 92 — 2026-09-14 00:08 PDT

- Task: Task 15A: qualify packaged broker mount access and probe-storage retention.
- Duration: 14 minutes
- Completed: **Solid and healthy** — Verified broker mount access, exact generation preservation across stop/start and restart, fresh-generation independence, and owned cleanup. Updated the owning contract, reuse map, and docs/TestAutomation/Task-15.md handoff. Task 15A remains unchecked; policy receipts and the full launch matrix remain unfinished.

- Verification and cleanup: Passed 320 isolated safety tests, 296 focused regressions, fresh artifact build, and all five guarded installed executions; runner prerequisites passed 1,057 tests plus three subtests. Evidence: /tmp/onpc-system-zk0l5jew/evidence/result.json and sibling guest-results/enforcement.xml. No new failures or denials; earlier composition failures remain retained. All commands exited, evidence was collected, and full baseline restoration passed. Links and whitespace checks passed. Full make check and 15A acceptance matrix were not run.

- Next session: Continue Task 15A with permanent dedicated-client loss after confirmed creation/admission, validating retained ownership and settlement locally before one guarded run. No entries bypassed; R1 recovery ledger unchanged. Documentation edits require fresh artifacts. Next settings: gpt-6-astra/high, Standard.


## Session 93 — 2026-09-14 08:48 PDT

- Task: Task 15A: permanent probe-client loss and retained-owner cleanup.
- Duration: 16 minutes
- Completed: **Solid and healthy** — Fixed cleanup after permanent sender loss when creation and terminal evidence are retained. Guarded loss/fresh-success qualification passed. Earlier loss still preserves uncertainty. Updated docs/TestAutomation/Task-15.md, the owning contract, reuse map and continuation; Task 15A remains unchecked.

- Verification and cleanup: Passed 154 probe regressions, 14 private-bus cases, 296 collector/runner checks, and 1,068 isolated safety tests plus 3 subtests. All five installed executions passed in /tmp/onpc-system-lejxzgpd/evidence/result.json; retained enforcement.xml confirms sender loss, native evidence and fresh success. Six pre-fix regression failures were resolved. A concurrent launcher-lock refusal was resolved by sequential execution after its owner exited. All commands exited; collection, owned cleanup and full restored-baseline verification passed. Documentation links and whitespace checks passed. Full make check, policy attribution and the complete native/Snap/Flatpak acceptance matrix remain outstanding.

- Next session: Continue Task 15A by qualifying native creation, admission and cleanup under the packaged broker’s full service sandbox, with local ownership/restoration checks first. Fresh artifacts are required after the documentation edits. No entries were bypassed; Task 20 R1 recovery remains uncharged. Next settings: gpt-6-astra/high, Standard.


## Session 94 — 2026-09-14 09:05 PDT

- Task: Task 15A — native probe lifecycle under the complete packaged service sandbox.
- Duration: 17 minutes
- Completed: **Solid and healthy** — Qualified native success, withheld-admission recovery and fresh success under the packaged broker service sandbox. Effective restrictions and temporary drop-in restoration passed. Updated the owning contract, reuse map, Task-15 handoff and Continuation.md. Task 15A remains unchecked: policy attribution, earlier-loss settlement, broker integration/recovery and the full launch matrix remain open.

- Verification and cleanup: Passed 360 isolated safety tests, 296 collector/runner tests, fresh artifact build, 1,097 runner safety tests plus 3 subtests, and all 5 installed executions. Evidence: /tmp/onpc-system-t5ira6cj/evidence/result.json; exact identities and exported assertions are in docs/TestAutomation/Task-15.md. All 231 documentation links and staged/unstaged whitespace checks passed. No test failures or execution/Polkit denials. Every command exited; collection, broker restoration and full baseline byte verification passed. Full make check and Task 15A acceptance matrix were not run.

- Next session: Continue Task 15A: establish the supported rule-decision source and bind it to the witness generation, compiled inputs and daemon invocation; implement local fail-closed checks before another installed observation. No tasks bypassed or R1 recovery charged. Next settings: gpt-6-astra/high, Standard.


## Session 95 — 2026-09-14 09:14 PDT

- Task: Task 15A — bind policy-decision evidence to the qualified native witness.
- Duration: 10 minutes
- Completed: **Solid and healthy** — Added test-only positive decision correlation with fail-closed checks for daemon identity, compiled inputs, journal records and native witness evidence. Updated the owning contract, reuse map and docs/TestAutomation/Task-15.md handoff. Activation acknowledgement and full 15A acceptance remain open: endpoint snapshots cannot exclude intervening input restoration, and arbitrary administrator-rule completeness remains unresolved.

- Verification and cleanup: 236 focused unit tests passed, including 82 new correlation cases; 237 links and scoped whitespace checks passed. Tested source hashes are retained in the handoff. Browser fetch failures were resolved through direct upstream reads; no execution/Polkit denial. No build, make check or VM attempt ran. Every command exited; no runtime fixture or cleanup remains. Historical attempts and the R1 recovery ledger are unchanged.

- Next session: Task 15A remains earliest ready; none bypassed. Add the guarded guest collector and fixture, prepare the marker before native dispatch, verify bounded collection/restoration locally, then qualify a positive record and rule-attributed deny control. Reuse existing native qualification. Next settings: gpt-6-astra/high, Standard.
