# Confinement test/proof handoff

Updated 2026-10-16. The user requested a cooperative stop and a resumable handoff. Do not restart VM execution until the user resumes this task.

## Objective and output

Finish running every test referenced in the defense column of the [offense/defense table](SystemDesign/Kiosk-Confinement.md#offense-and-defense-scenarios), then finish the standalone proof table already created as the untracked file `docs/Kiosk-Confinement-Proof.md`.

The proof has all 34 scenario rows, unchanged scenario text, and GitHub source links pinned to `f895a6b8ffe5016e54943ae4b5e64f6d4c216530`. Recording links must use actual absolute paths beneath `/Data/Code/PST/parent-control/output/test-runs/recordings/`. Use one combined-VM recording per persistent case ID. Leave engineering qualifiers without recording links or added limitation explanations. Do not add navigation/index links to the proof or commit it; the user intends to remove it from the checkout.

The draft currently has 203 recording-link occurrences, including repeated references and parameterized case groups. Its recording filenames were provisional and are not fully validated. Many cases have not run; older files in the recordings folder do not establish a pass in this batch.

The user does not want incremental execution-status messages. Report unusual issues and the final result.

## Execution state

Batch session: `11fb9c53669f42f997d47dd5be4f97e5`. It used the two enabled registered VMs with concurrency 2.

| Target | First system selection | Removal selection | E2E / engineering qualifiers |
| --- | --- | --- | --- |
| `onpc-Ubuntu26.04` | 135/135 executions passed | 91/155 completed, then infrastructure failure `command:failed:ssh` | Unrun |
| `onpc-Fedora44` | 135/135 executions passed | 117/163 completed before the user-requested stop | Unrun |

Ubuntu's last completed removal history was system ID 17, `test_ownership_refusal_retry[confinement-record-link]`, including its retry reboot. It failed after package installation while preparing `confinement-record-uid-installed`, before the next registered assertion. This is an unresolved transport/infrastructure failure, not evidence of a failed product assertion. Its evidence separately reports product/collection/cleanup passed and infrastructure failed; inspect the retained operation before diagnosing or repairing it.

Fedora was interrupted in the `home-link-installed` prerequisite, inside system ID 5's account/confinement check. System ID 20, `test_identity_filesystem_refusal_retry[home-owner]`, had completed both history phases. The in-flight ID 5 phase is not a retained pass.

The runner has fully exited with status 130 after the requested cancellation. Both VM reports confirmed owned cleanup and restored-baseline verification passed. Recording publication also finished: the batch's `recordings.json` has `complete: true`, `status: 130`, and 150 published system clips. No new E2E clips were generated. System ID 5's clip is marked interrupted. The recording index has no case-level failed flags, but that does not erase Ubuntu's separate SSH infrastructure failure; use the per-VM reports for execution outcomes.

## Resume without resetting passes

Read the [resume contract](../tests/README.md#resuming-test-execution) and [failure handling](../tests/README.md#handling-test-failures). From `/Data/Code/PST/parent-control`, use the exact explicit selection:

```sh
tools/run-tests --resume system --id '4,5,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,267,268,269,270,271' system --area 'removal' e2e --id '47,48,50,51,52,192' integration 'check_e2e_kiosk_preferences_confinement' integration 'check_e2e_kiosk_feedback_confinement'
```

Do not use bare `tools/run-tests --resume`: another host unit run has overwritten the latest public request with `unit tests/unit/test_kiosk_confinement.py -k admission_layout_profile -s -q`. The VM checkpoints still retain the correct full batch selection. Do not start the batch without `--resume`, change selectors, edit checkpoints, or discard retained evidence.

The matching checkpoint directories are:

- Fedora: `output/test-runs/host/state/run-tests-vm-10cd4429f8ce5f58fb078f52/`, with 250 retained distinct system phase/case identities at stop.
- Ubuntu: `output/test-runs/host/state/run-tests-vm-8e0f29791197f6bce6eeef93/`, with 224 retained identities.

Counts differ from summed report totals because the same installed/rebooted prerequisite identities recur across category groups. The runner owns the exclusion list. Completed cases are retained; failed/interrupted cases replay. Lifecycle predecessors, preparation and ownership checks still replay when required to reconstruct guest state. This is a fresh guarded attempt from checkpointed case boundaries, not continuation of a live guest or an interrupted assertion.

System IDs in the first selection are 4, 5, 26–151 and 267–271. The second system group selects the whole removal area so the RPM-only ID 8 is automatically excluded on Ubuntu. Selecting ID 8 explicitly for both VMs causes `selection:history-package-format-mismatch`; do not revert to that earlier invalid selection.

## Retained evidence

- Ubuntu report: [report](../output/test-runs/host/reports/20261016T175552Z-ddee6a74/report.md), with adjacent `progress.json`, `failure.json` and category logs.
- Fedora report: [report](../output/test-runs/host/reports/20261016T175552Z-a2fc1e48/report.md), with adjacent progress and category logs.
- Combined queue result: `output/test-runs/host/allocations/onpc-vm-queue-i6u1cjb7/results.json`.
- Ubuntu removal evidence: `output/test-runs/privileged/allocations/onpc-system-ug0pyudq/evidence/`.
- Fedora interrupted removal evidence: `output/test-runs/privileged/allocations/onpc-system-5r_tygfn/evidence/`.
- Batch metadata and recording index: `output/test-runs/host/sessions/11fb9c53669f42f997d47dd5be4f97e5/`.

Use the maintained [artifact reader](../tests/README.md#prompt-free-test-artifact-access) for privileged evidence, for example:

```sh
pkexec --keep-cwd /usr/local/libexec/onpc-test-artifacts read '/Data/Code/PST/parent-control/output/test-runs/privileged/allocations/onpc-system-ug0pyudq/evidence/result.json' --bytes 16000
```

The previous quiet monitor missed Ubuntu's completed failure because the live queue frame stopped displaying that target. Future monitoring must also inspect completed workers' retained reports/results, not only the active queue frame.

## Remaining close-out

1. Investigate the Ubuntu SSH failure through retained evidence. Preserve expected versus actual behavior and all ownership guards. Do not weaken checks or assume a generic SSH error proves a product regression.
2. Once the user resumes, run the exact resume command above. Complete remaining removal cases, E2E IDs 47/48/50/51/52/192, and both engineering qualifiers on the selected VMs.
3. After each runner session has fully exited, inspect its `recordings.json`. Clips are cut, fully decoded and atomically published at session finalization, including cancellation. Each persistent category/ID has only its latest recording; repeated phases share a clip. Resume can supersede earlier clips for replayed IDs. Preserve run-specific index/SHA evidence and do not mistake older clips for newly executed cases.
   In this stopped session, IDs 18–20 published Fedora-only clips because Ubuntu had already failed. A resume that retains Fedora's passes can replace these with Ubuntu-only clips; the recorder does not merge media across sessions. Before resuming, decide how to preserve any needed earlier media through the maintained artifact exporter/bundler, or arrange a bounded both-VM rerun of the affected cases if a single clip must show both executions. Do not reset the whole suite for this. A filename naming both visible feeds alone does not prove both targets executed or passed the case.
4. Reconcile every proof recording URL against actual published filenames. Filename VM suffixes describe visible feeds, so do not infer the suffix solely from which VM executes a platform-specific case. Engineering qualifiers receive no recording links.
5. Verify all 34 copied rows and source links, all intended recording files, and Markdown links with `tools/read-only links`. Keep the proof standalone and uncommitted. Do not claim the full table passed until the missing work passes.
6. Preserve unrelated work. Concurrent work changed and committed files during this batch; this task edited neither product code nor tests. At this check, HEAD was `59a1c2aa05511e7ed60e030baafe0ad4c020aa44` and only the two handoff/proof documents were untracked. Compared with the proof's pinned starting revision, changes include `packaging/kiosk_confinement.py`, `Makefile`, `tests/integration/system_first_configure.py`, guest prerequisites, runner/unit tests, design/installation contracts and release notes. Inspect that diff and current contracts before resuming. Checkpoints retain valid historical passes, but those passes do not certify later changed inputs. Assess renewed affected qualification under the design/runner contracts separately; do not silently reset all checkpoints or claim one immutable current revision passed this mixed-time batch.

Recommended continuation: GPT-6.1 Sol Medium for routine resume and document close-out; GPT-6.1 Sol High if the SSH/infrastructure failure requires unresolved diagnosis. Follow repository instructions and the [VM mandate](Mandates/VM-Mandate.MD); do not install the product on the development host.

