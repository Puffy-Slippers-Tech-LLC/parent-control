# Test evidence and export target design

This is a proposed infrastructure design, delivered through the
[plan](Export-Execution-Plan.md) and [queue](Export-Task-Queue.md). It does not
describe new commands as implemented or replace existing runtime contracts.
E01 audits history and inventories; E01a proposes concrete protocols and interfaces;
E01b independently reviews and freezes schemas, coverage and task allocation before
implementation. E14 owns composed validation; E14a owns independent final review.

## Investigated failures and remaining exposure

Repository history and existing regressions show several distinct causes.
Commit IDs are historical source references, not passing test evidence. E01
rechecks complete changes and callers rather than relying on commit titles.

| Historical source | Finding | Required prevention |
| --- | --- | --- |
| `4cf81254` (2026-09-16), `test_regression.py` | Missing evidence-directory initialization blocked a run | Initialize and register atomically; test clean first use as well as reuse |
| `7e3f4698` (2026-09-23), storage-migration regressions | Test output moved from system temporary paths into shared storage | Use shared allocation and explicit legacy readers; never guess or reconstruct roots |
| `f1270ba7` (2026-09-28), `test_dev_tool_installation.py` | Installed helpers were bound to an absolute checkout path, breaking worktrees | Resolve the invoking checkout through the validated helper and retain repository identity |
| `e420ac4e` (2026-10-04), retained export guidance in `tests/README.md` | Repeated exports can evict other reports still needed for close-out; the commit documented this exposure | E03/E05/E06 deliver capture before rotation and reusable exports; retain the existing guidance until delivered |
| `0a87b716` (2026-10-06), `test_recovery.py` and retention cleanup-safety regressions | Startup recovery can retire an oversized completed execution allocation outside ordinary count rotation | E04 covers automatic host/privileged recovery as well as ordinary pruning; failed or unacknowledged required capture must preserve the original |
| `31c8c32c` (2026-10-11), `repair_evidence.py` and `test_fix_tests.py` | Original reports and command records can disappear during repair; retained diagnostic tails are bounded and partial | E07a reuses snapshots for diagnosis, preserves truncation/refusal status and never substitutes tails for complete proof |
| `c8fbcd58` (2026-10-17), recovery-diagnostic bundle regressions | Shared and selected-target diagnostic journals needed export discovery; first export and absent optional storage needed distinct handling | E01 inventories `qualification_storage.recovery_session()` and `vm_probe` producers; E06a captures their finalized records while retaining diagnostic status and existing refusal checks |
| `41f23bfd` (2026-10-18), checkpoint and repair regressions | Another invocation can replace a repair's selector checkpoint | E07a retains original selectors and existing host-only replay; malformed state and VM/mixed mismatch keep their refusals |
| `ac5573ff` (2026-10-19), execution-plan regressions | Legitimate destination-only evidence repairs could violate protected queue comparisons | Normalize only proven reference bookkeeping; protect claims, scope, completion and checkpoint ownership |
| `71473c09` (2026-10-20), `test_plan_evidence.py` and recovery tests | Accepted proof needed preservation beyond disposable sessions; stale controllers complicated recovery | Extend existing cumulative publication and restart recovery instead of another archive/launcher state machine |
| `502181f1` (2026-10-20), reference-parsing regressions | Sentence punctuation could become part of an evidence path | Generate structured references and share a tested parser; distinguish literal filename punctuation |
| `3e5cb3f3` (2026-10-20), bundle/helper/plan regressions | Interrupted publication and missing-reference renewal needed exact resumable handling | Separate missing proof from access/integrity refusal; preserve transaction and original attempt across restarts |
| `009f719c` (2026-10-20), verified-record regressions | Repeated archive verification made startup unnecessarily expensive | Verify once per pinned read scope, invalidate on mutation, never trust an unchecked cached path |
| `2ddcf5f7` (2026-10-20), retention/bundle regressions | Concurrent finished evidence readers were incorrectly exclusive | Shared read ownership; publication/cleanup excludes readers and writers in a defined lock order |
| `dbf40859` (2026-10-21), prerequisite/capacity recovery regressions | A failed capacity attempt can leave partial queue edits or a removed brief before a usable response exists | E07 preserves captured inputs, suspended work and session accounting through the existing recovery route; private fixtures simulate failures without starting a model |

Current [retention](../../tests/README.md#aggregate-output-retention) explicitly
warns that every ordinary export consumes a session and can evict another report.
The existing [plan evidence](../../tools/plan_evidence.py) captures explicit
result-check references and the selected queue row; reference rewriting is
limited to selected or previously completed queue Estimate cells. References in
design modules, catalogue prose and other consumers can remain disposable.
The [document checker](../../tools/document_checks.py) checks inline destination
existence, not matching result identity, reference-style links or fragments.
The developer reported another occurrence during this plan's authoring: two
earlier report links expired and retained-copy investigation began while an
installed check was still running. Reproduce that ordering with private host
fixtures: an unrelated synthetic check remains active while both legacy
references resolve from exact retained members. Never interpret that as authority
to inspect or publish the unrelated active owner's mutable allocation.
The developer also reported an older evidence link expiring when a new run
rotated local reports. E06/E14 must reproduce that startup ordering through the
[required regression histories](#required-regression-histories), including a
failed capture whose original remains required. These incidents need prevention
at producer and retirement boundaries, beyond a destination repair after loss.

The [kiosk verification record](../SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits)
also discloses raw system allocations rotated before archival despite surviving
host reports. These losses show that a summary or generic accepted locator cannot
replace the original result/JUnit/TAP/input/cleanup records. Large historical
bundles also approach the finite file limit; copying every old generation
indefinitely is not a capacity strategy. Treat each existing fix as a retained
regression, not an instruction to implement the same fix again.

## E01 source and history audit

Audit baseline: 2026-10-21. All fifteen commits above resolve and their changes
and current complete functions/callers were reviewed. The following maps record
source findings, not new runtime passes or implementation of this proposal.
Existing tests are named for reuse; E01 did not rerun historical suites. Paths in
the maps are checkout-relative. E01a resolves the listed protocol questions;
E01b independently reviews and freezes their answers and delivery allocation.

### Historical fixes to reuse

Test names in this table are existing functions in the named module. The planned
histories below cover the remaining exposure rather than reimplementing fixes.

| History | Current source boundary | Existing regression anchors | Disposition |
| --- | --- | --- | --- |
| `4cf81254` | `tools/regression.py`: `Report.__init__`, `retained_main` | `tests/unit/test_regression.py`: `test_report_initialization_failure_exposes_cause`, `test_report_rejects_symlinked_parent`, `test_final_investigation_prompt_links_closed_report` | Reuse parent creation, refusal and useful diagnostics. Directory creation precedes `retain()`; this fix did not supply atomic registration or finalized capture. E06 owns P01 below. |
| `7e3f4698` | `tools/test_storage.py`, `tools/test_retention.py` and migration/report callers | `tests/unit/test_test_storage_cleanup_safety.py`: `test_allocator_redirects_bulk_tmp_outputs`, `test_legacy_retention_is_preserved_and_live_or_unfinished_owners_refuse`; `tests/unit/test_storage_migration_cleanup_safety.py`: `test_successful_migration_preserves_diagnostics_before_removal`, `test_copy_failure_preserves_entire_original` | Reuse shared roots and identity-checked legacy migration. E11/E12 use finite known references, without reconstructing roots or adopting old allocations. |
| `f1270ba7` | Invoking-checkout resolution in `tools/dev_checkout.py` and installed helper entry points | `tests/unit/test_dev_tool_installation.py`: `test_same_installed_helper_follows_two_repositories`, `test_checkout_resolver_refuses_unsafe_inputs`, `test_rendered_dispatcher_resolves_checkout_and_pins_uuid` | Reuse resolver; E02/E05 preserve repository identity. No new helper-binding mechanism. |
| `e420ac4e` | `tests/README.md` export guidance; `tools/evidence_bundle.py`: `export` | This commit documents exposure; it supplies no export-reuse regression. | Every ordinary export still consumes a session; bundle export still allocates a publication. E03/E05/E06 own P01/P03/P04. |
| `0a87b716` | `Store.reconcile`, host `tools/test_recovery.py`, privileged `tests/integration/check_test_recovery.py` | `tests/unit/test_test_retention_cleanup_safety.py`: `test_execution_recovery_retires_only_verified_oversized_evidence`, `test_execution_recovery_keeps_completed_evidence_within_budget`, `test_host_preflight_automatically_retires_oversized_completed_evidence`, `test_privileged_preflight_retires_oversized_run_under_vm_leases` | Preserve oversized disposable retirement and live-reference/lease refusals. Required-proof acknowledgement is absent; E04 owns P02 at every retirement boundary. |
| `31c8c32c` | `tools/repair_evidence.py`: `capture`; `tools/fix_tests.py`: `handoff` | `tests/unit/test_fix_tests.py`: `test_failure_context_survives_original_report_and_command_removal`, `test_failure_context_bounds_data_and_refuses_linked_sources`, `test_failure_context_uses_scoped_privileged_reader`, `test_failure_context_does_not_retry_a_denied_reader` | Reuse bounded diagnostic snapshots in E07a/P07. Preserve `bounded_tails`, `may_be_truncated`, `read_failures`, `limit_reached`; 4 MiB total, 128 KiB/file and 64-file limits do not establish complete proof. |
| `c8fbcd58` | `evidence_bundle.Selection.catalogue`, `verify_stream`; recovery producers below | `tests/unit/test_evidence_bundle.py`: `test_catalogue_includes_only_selected_targets_host_and_guest_journals`, `test_host_only_catalogue_without_privileged_storage`, `test_recovery_diagnostic_samples_survive_rotation` | Reuse selected-target discovery and optional-storage distinctions. The rotation fixture substitutes a journal name; it does not exercise `recovery_session()`/`vm_probe`. E06a owns P06. |
| `41f23bfd` | `tools/test_checkpoint.py`: `Checkpoint.__init__`; `fix_tests.worker` host replay | `tests/unit/test_fix_tests_cleanup_safety.py`: `test_repair_replays_original_selection_after_another_run_replaces_checkpoint`, `test_repair_does_not_reset_an_invalid_checkpoint`, `test_vm_repair_does_not_reset_checkpoints_after_selection_mismatch`; `tests/unit/test_test_checkpoint.py`: `test_changed_selection_does_not_mask_invalid_saved_progress` | Reuse unchanged host selector replay in E07a/P07. Malformed checkpoints and VM/mixed selections retain refusal. |
| `ac5573ff` | `tools/execution_plan.py`: `evidence_references`, `closeout_structure`; launcher transition/recovery | `tests/unit/test_execution_plan_launcher.py`: `test_completed_evidence_destinations_allow_transition_and_recovery`, `test_completed_evidence_repair_preserves_every_other_obligation`, `test_completed_evidence_repair_survives_retained_restart` | Reuse proven destination-only normalization. E07/E09/P08 preserve labels, scope, order, completion and controller ownership. |
| `71473c09` | `tools/plan_evidence.py`: `capture`, `carry`, `preserve`, `recover`, `rewrite_references`; `tools/plan_evidence_recovery.py` | `tests/unit/test_plan_evidence.py`: `test_exact_proof_survives_more_than_three_later_sessions_and_independent_exports`, `test_unfinished_inputs_survive_more_than_three_restarts`, `test_suspended_inputs_survive_prerequisite_rotations_without_sessions_or_git_changes`, `test_queue_rewrite_changes_only_proven_selected_estimate_destinations`; `tests/unit/test_plan_evidence_recovery.py`: `test_controller_corrects_only_reviewed_links_and_preserves_checkpoint`, `test_interrupted_controller_publication_resumes_exact_transaction` | Reuse cumulative proof, exact inputs, suspended carry and authorized historical disclosures. E03/E07/E09 extend this route; generic locator rewriting is not an exact check selector. |
| `502181f1` | `plan_evidence._references` delimited destinations and bare prose parsing | `tests/unit/test_plan_evidence.py`: `test_prose_report_references_publish_exact_evidence`, `test_delimited_report_paths_preserve_literal_punctuation`, `test_link_labels_are_not_evidence_sources`, `test_queue_prose_and_relative_links_preserve_one_exact_source`, `test_missing_prose_report_still_refuses_publication` | Reuse punctuation/literal-filename distinction. E02/E08/E09 own structured selectors and shared parsing in P08/P09. |
| `3e5cb3f3` | `evidence_bundle.EvidenceUnavailable`, `Selection.load`, `reference_present`; `plan_evidence._source`, `preserve`, `carry`; helper dispatch | `tests/unit/test_plan_evidence.py`: `test_rotated_reference_uses_only_exact_verified_selected_bundle`, `test_expired_references_name_every_missing_path_without_acceptance`, `test_target_helper_only_renews_explicit_structured_missing_references`, `test_evidence_renewal_keeps_exact_rejected_source_across_bounded_rotation`, `test_failed_publication_pending_source_survives_more_than_three_new_runs`; `tests/unit/test_evidence_bundle.py`: `test_public_recovery_removes_only_recorded_incomplete_stage` | Reuse exact missing-reference renewal and interrupted staging recovery. Access/integrity/ownership refusals remain distinct. E04/E07 extend through P02/P08. |
| `009f719c` | `evidence_bundle.verified_record`; `plan_evidence._verified_ledger` | `tests/unit/test_evidence_bundle.py`: `test_verified_record_reuses_one_open_archive_for_bounded_reads`, `test_verified_record_refuses_mutation_during_read_scope`; `tests/unit/test_plan_evidence.py`: `test_startup_verifies_cumulative_archive_once_per_recovery` | Reuse one pinned verified read scope in E05/P04. No unchecked cross-scope cache. |
| `2ddcf5f7` | `Store.inspection` shared ownership and bundle read callers | `tests/unit/test_evidence_bundle.py`: `test_bundle_reads_overlap_without_rejecting_another_reader` | Reuse overlapping finished readers. E05a/P05 still must avoid eager inspection of an unrelated active journal. |
| `dbf40859` | `tools/launcher_runtime.py`: `capacity_session_recovery`, `capacity_retry`; launcher worker/recovery and missing-brief recovery parsing | `tests/unit/test_execution_plan_launcher.py`: `test_capacity_retry_requires_exact_provider_failure_and_clean_supervisor_exit`, `test_capacity_recovery_preserves_prerequisite_and_suspended_consumer`, `test_capacity_restart_restores_removed_brief_on_default_model_with_fresh_retries`, `test_capacity_restart_keeps_identity_and_unrelated_queue_guards`, `test_capacity_restart_reconciles_partial_insertion_before_suspending_consumer` | Reuse exact failure classification, partial queue/brief recovery and counters. E07/P08 must compose real evidence; these controller fixtures stub evidence functions. |

### Planned regression ledger

P01–P12 are finite audit identifiers for **unimplemented, unregistered** histories,
not runnable selectors or acceptance results. E01a specifies their protocols and
E01b freezes executable allocation; implementing rows register concrete test
functions before invocation. Existing regression anchors above remain required.

| ID | Delivery owner | Required history |
| --- | --- | --- |
| P01 | E06, E14 composition | Real aggregate/category/worker/standalone report finalization; complete result, input, command, JUnit/TAP where applicable and cleanup closure; more than three startup runs actually remove A's path; exact archived resolution with A invoked once. Include clean first allocation/registration failure and failed/interrupted attempts. |
| P02 | E04, E14 composition | Each retirement boundary below retains required originals after failed capture, pending/stale acknowledgement, capacity refusal or interruption; only matching durable closure releases them. Unreferenced oversized disposable output still retires. |
| P03 | E03 | Authenticated producer/attempt handoff of an immutable finalized subset; changed source, foreign/active owner, cancellation and failure at every durable transition preserve prior proof and resumable ownership. |
| P04 | E05 | Same verified source/selection reuses one private export/receipt without another slot; changed/missing export refuses reuse; distinct same-basename/provenance remains distinct; grouped publication, shared readers and pinned verification retain limits. |
| P05 | E05a, E07/E14 composition | Required history 2 below through actual authenticated `bundle-plan` dispatch, real catalogue/load/inspection locks and two absent original paths while the same target has an unrelated active producer. Keep missing, corrupt, denied, wrong identity and actual active-source cases distinct. |
| P06 | E06a | Qualification and E2E collector finalization plus actual shared/target `recovery_session()`/`vm_probe` producer call chains, including failed/interrupted diagnostics, optional absent storage and exact cleanup/target provenance. Diagnostics never become acceptance. |
| P07 | E07a | Repair snapshots/original selector replay and E2E retries/continuations preserve original attempts, partial status and exact proof; malformed/VM selector mismatch refuses; no new model or VM execution in fixtures. |
| P08 | E07, E07a specialized integration | Real capture/carry/preserve/recovery through continuation, suspension, capacity partial edits, missing-proof renewal, rejected response and accepted Git retry; protect queue claims, original inputs/counters and cleanup. Disable synthetic evidence stubs for composed histories. |
| P09 | E02 identity; E08 parsing; E09 semantics; E10 gates | Exact check/attempt/target/input/member identity; wrong-but-existing destinations refuse. Relative/reference-style links, fragments, sentence versus literal punctuation, examples/code exclusions, claim changes and required/optional declarations retain typed severity precedence. |
| P10 | E11 inventory, E12 migration, E13 history | Finite tracked/document catalogue; exact live/archive match, ambiguous/wrong destination and unavailable proof; preview/apply refuses changed bytes/digests or protected claims; unchanged historical debt is nonpassing and does not repeatedly block unrelated work. |
| P11 | E02 onward in each introducing row; E07/E14 composition | Mutate every registered dependency's actual bytes with the real fingerprint reader feeding worker; include a newly extracted dependency while original eight stay unchanged. Stop before next task, corrective session or blocked-answer continuation; preserve exact result, inputs, counters and ownership; unchanged bytes do not restart. |
| P12 | E03/E04 accounting, E14 composition | Simultaneous old/staging/new/receipt/recovery capacity, near file/manifest limits, bounded segmentation/compaction and interruption; refuse before destructive rotation, preserve current proof, no multiplied owner budgets or silently dropped members. |

### Producer and consumer inventory

This is a finite source inventory, not a scan of live journals or local evidence.
Each row names its delivery owner and planned regression ledger entries. Shared
mechanisms E02–E05 apply to every captured producer without changing verdicts.

| Family | Current producer/consumer route and lifetime | Delivery and retained coverage |
| --- | --- | --- |
| Ordinary file exports | `tools/onpc-test-artifacts`: authenticated `export` drops to caller; new `exports/retention` session each time, unchanged source, private destination, no reuse receipt/dependency registration. | E05/P04; E03/P03, E04/P02. Reuse `tests/unit/test_test_artifacts.py::test_reads_and_exports_any_format_without_changing_source`. |
| Qualification and plan bundles | `tools/evidence_bundle.py`: `Selection.catalogue/load`, `export`, `inspect`, `verified_record`, `finish`, `recover`; shared finished-source inspection, independent publication owner, exact original member provenance and verified receipt. Plan namespace is distinct from ordinary export journal. | E02–E05/P02–P04/P09/P12; E05a/P05. Reuse `tests/unit/test_evidence_bundle.py`: `test_multiple_allocations_preserve_exact_bytes_manifest_and_sources`, `test_cumulative_bundle_survives_source_and_export_rotation`, `test_plan_references_reuse_only_verified_exact_archived_members`. |
| Aggregate/category/worker reports | `tools/regression.py`: `Report`, `Execution`, `main/retained_main`; `tools/regression_process.py`: `host_run/category_run`; `tools/vm_test_queue.py`: `run`. Markdown, immutable inventories, progress/resources/schedule and category logs belong to report allocation; logs are children, not independent journal owners. Host, batch and selected-VM worker journals are distinct. | E06/P01; reuse `tests/unit/test_regression.py`: `test_inventory_directory_sync_failure_prevents_status_sync_and_can_retry`, `test_partial_failure_is_durable_before_cancellation` and initialization/closed-report tests above. Package inputs, coverage and UI output allocations retain the applicable execution owner. |
| Standalone reports | `Report.__init__` without active token registers under `standalone-reports` in a short session before opening `report.md`; checkout activity is the outer lifetime owner. Finalized-record handoff is absent. | E06/P01 explicitly covers this boundary, not just aggregate termination. Reuse report initialization and close regressions above. |
| Standalone qualifications/wrappers | `tests/integration/qualification_storage.py`: `session`; `check_graphical_smoke.py` and `check_e2e_watch.py` use selected privileged journal or reuse active session. Work directory and private collector are separately registered within that run. Installed-journey wrappers reuse the implementation. | E06a/P06; `tests/unit/test_qualification_storage_cleanup_safety.py`: `test_standalone_qualifications_rotate_both_work_and_collector`, `test_nested_qualification_joins_existing_run`. No installed qualification in this plan. |
| System results | `tests/integration/system_runner.py`: `selection_evidence`, `evidence`, `main`; registered system root holds result, JUnit/TAP, selected inputs, guest output, commands and cleanup ledger. A readable child/summary is not the full private closure. | E06a/P06 with E06 runner integration/P01. Retain exact-member bundle coverage above; add real producer closure rather than summary-only fixtures. |
| E2E collectors | `tests/e2e/private_artifacts.py`: `PrivateCollector`; `tests/e2e/execution.py`: `attempt`; recording/evidence callers register separate evidence root. Collector close releases descriptor, not retention; final candidate may precede cleanup failure. | E06a/P06, E07a/P07; `tests/unit/test_e2e_evidence.py`: `test_real_collector_sync_order_and_failure_precede_registration`, `test_final_gate_rechecks_copies_and_rejects_unregistered_worker_files`, `test_retained_failure_report_tampering_prevents_later_acceptance`, `test_first_failure_survives_cleanup_and_cannot_be_replaced_by_retry`. Capture final returned ledger status. |
| Shared/target recovery diagnostics | `qualification_storage.recovery_session`; `tests/integration/check_graphical_recovery.py`, `baseline_guest.py` and `vm_probe.py` callers listed below. Separate `recovery-diagnostics-<uid>[-target]` owner; interrupted diagnostic runs may recover for rotation without clearing unfinished execution journal. | E06a/P06; `test_qualification_storage_cleanup_safety.py::test_recovery_diagnostics_rotate_without_changing_unfinished_vm_journal` plus catalogue/rotation anchors above. Preserve failure/partial diagnostics and native-log availability; no acceptance promotion. |
| Reconnect/workflow logs | `tools/regression_session.py`: `_select`; `tools/detached_launcher.py`: `select`, session/start/carry callbacks. Registration rings differ from execution journals; resumable startup keeps exact pending-start identity. | E07/P08, E07a/P07; reuse `test_execution_plan_launcher.py`: `test_resumable_start_retries_same_registered_run_without_rotating_source`, `test_pending_partial_carry_over_budget_refuses_before_any_retention_prune`. |
| Ordinary/derived plan proof | `tools/execute-plan`, `reliability-plan`, `kiosk-prompt`, `kiosk-desktop`, `kiosk-prompt-new`, `fixture`, `export` all use `plan_launcher.PlanWorkflow/main`. `plan_evidence.capture/carry/preserve/recover` freezes selected inputs and accepted cumulative proof; `plan_evidence_recovery` owns protected startup correction. | E07/P08; reuse historical accepted/carry/recovery tests plus `test_execution_plan_launcher.py::test_plan_adapter_default_check_has_no_execution_side_effects`. All adapters need a composition disposition, not separate evidence engines. |
| Ordinary accepted Git retry | `plan_launcher.closeout`, `launcher_git` ownership/pull/stage/finish preserve accepted result before Git. Unfinished Git transaction cannot renew missing proof. | E07/P08; `tests/unit/test_plan_evidence.py::test_git_retry_reuses_only_the_exact_verified_result`; `test_execution_plan_launcher.py::test_unavailable_proof_does_not_renew_across_git_transaction`. |
| Repair diagnosis and verification | `tools/fix_tests.py`: `handoff`, worker verification/diagnostic paths; `repair_evidence.capture` stores bounded snapshots within workflow run. Verification uses reported identities; unknown/unexecuted records remain nonpassing. | E07a/P07/P08; retain snapshot/selector tests above and `tests/unit/test_fix_tests.py`: `test_verification_uses_all_reported_identities_but_never_infers_unreported_passes`, `test_case_handoffs_do_not_cross_cases_or_vms_or_aggregate_companions`. |
| Specialized E2E launcher | `tools/write_e2e.py`: `acceptance_evidence`, `validate_progress`, `accept_result`, `recover_completion`; formal live evidence differs from diagnosis/promotion and does not currently use ordinary `plan_evidence`. | E07a/P07/P08; retain `tests/unit/test_write_e2e.py`: `test_diagnostic_rounds_preserve_formal_failure_and_next_same_checkpoint_promotion`, `test_non_live_handoffs_preserve_failure_for_diagnosis_and_repair`, `test_retained_completion_cannot_bypass_acceptance_or_staging`, `test_push_failure_retries_existing_commit_before_counting_completion`. |
| Document check evidence strings | `plan_evidence._references` reads result `checks[].evidence` and selected queue row; legacy prose/link/code paths are potential sources. | E02/E07/E09/P09; reuse literal punctuation, link-label and missing-reference tests above. |
| Queue cells | `rewrite_references` changes only proven simple inline destinations in selected or previously completed Estimate cells. Unfinished/suspended claims have no generic repair exception. Labels, surrounding claims, count, Scope/Requires and completion remain protected. | E07/E09, E12/P08–P10; reuse `test_plan_evidence.py::test_queue_rewrite_retains_verified_completed_proof_and_leaves_unfinished_or_unproven_links` and protected transition/recovery tests above. |
| Briefs, master and handoffs | Exact input snapshots and capsule result/prompt/commands/cleanup survive, but references embedded in their prose are not all semantically validated. | E07/E07a lifecycle, E09/P08/P09; E11 tracked inventory/P10. |
| Catalogue/design/specification prose and report links | Building-block/coverage/kiosk verification records and other prose are outside reference capture unless repeated in a selected row/check. `document_checks.check_links` proves inline destination existence only. | E08/E09/P09; E11 catalogue, E12 guarded migration, E13 unavailable history/P10. No invented historical proof or new product passes. |
| Required instruction links, examples and operational paths | `tools/document_checks.py`: `without_code/inline_destinations/check_links`; `tools/read-only` dispatch. Code is masked for document link checking but deliberately parsed as possible legacy evidence by `plan_evidence`. Role must come from owning declaration, not global exclusion. | E08/E09/E10/P09. Reuse `tests/unit/test_document_checks.py`: `test_local_inline_links_handle_destinations_and_ignore_code_and_urls`, `test_missing_targets_report_document_number_and_line_without_input_values`, `test_link_existence_is_relative_to_each_document`, `test_document_commands_use_existing_executable_reader_without_shell_or_input_execution`. |
| Separate media and disposable storage | `tools/recording_storage.py` latest-only publication; screenshot export/cleanup has its own narrow contract. `test_storage` scratch/runtime is disposable and identity/lease-owned, never required-proof storage. | Preserve separate lifetime policies. E06a/E09/E11 classify media references and required media closure; E04/P02 must not create unlimited pins or silently drop required media. Scratch/VM backup/lifecycle state is outside proof capture. |

The finite direct `tests/integration/vm_probe.py` diagnostic producers are
`reproduce_kiosk_refusal`, `probe_kiosk_latency`, `probe_kiosk_prompt_latency`,
`probe_kiosk_approval`, `probe_revoke_balances`, `probe_retained_app_launch`,
`probe_riley_native_grid`, `probe_remembered_return`, `probe_transfer_refusal`,
`probe_lock_curtain`, shared `reproduce_denial` and
`prepare_maintenance_transport`. Fixed remembered-return/repeat/entry and
retained-unlock callers reuse `reproduce_denial`; they are not new storage owners.
Their observed/timing JSON, JSONL observations, refusal/boundary status, commands,
copied inputs and optional native-log status can be partial on failure.
`baseline_guest` retains only a 16-KiB preparation-log tail. E06a/P06 must retain
these limits and status, rather than treating a discovered directory as complete.

### Retirement entry points

All deletion below currently depends on identity/ownership and lifecycle guards,
not a general required-proof dependency/durable-acknowledgement catalogue. E04/P02
owns that addition at each applicable entry, reusing the existing safety gates.
Publication also belongs to E05/P04; E03/P03 supplies the handoff acknowledgement.
Explicit discard still requires its existing specific authority. This audit
grants no discard or live cleanup permission.

Unless noted, `Store`/`Publication` are in `tools/test_retention.py`; regression
names are in `tests/unit/test_test_retention_cleanup_safety.py`.

| Entry and callers | Owner, locks and present gate | Recovery and retained regression anchors |
| --- | --- | --- |
| `Store.session` start/finalization; ordinary producers, export, workflow and qualification sessions | Exclusive nonblocking owner, serialized writer, optional lifecycle guard. Calls `prune`, but also directly removes old runs at count admission; finished marker/state and allocation identity audited. | Both direct deletion and prune need dependency checks. Reuse `test_one_hundred_runs_have_constant_retained_size`, `test_same_run_keeps_all_vm_categories_until_fourth_run`, `test_active_owner_is_not_rotated`. |
| `Store.prune` count/byte expiry | Owning locked writer; latest allocation claim, mount/identity audit; small recovery receipts expire with run. Oversized current is preserved at finalization. | Preserve current refusal/diagnostics and retry; `tests/unit/test_test_storage_cleanup_safety.py`: `test_current_oversized_evidence_is_preserved_and_reported`, `test_budget_diagnostic_failure_keeps_the_original_refusal`. |
| `Store.reconcile`; host `tools/test_recovery.py`: `cleanup_host/cleanup`; reconnect `regression_session._select` | Checkout activity then owner/writer, recovery guard. Archives unfinished journal/marker before finished-state commit. Host execution supplies `completed_guard=lambda paths: None`; workflow/diagnostic owners do not opt into oversized execution deletion. | Recovery is retryable without adopting replacements. `test_idle_reconciliation_retries_after_marker_archive_and_failed_commit`, `test_idle_reconciliation_preserves_evidence_and_refuses_unsafe_recovery`, host oversized/startup tests above. |
| Privileged startup `tests/integration/check_test_recovery.py`: `main` | First `reconcile(reconcile_vm, completed_guard=unused, lease=retention_lease)`; then a **separate** owner/lease/writer `prune(keep=2, completed_guard=unused)` before memory admission. Compatibility/named VM leases span live-reference audit/deletion. | Both calls need dependency gates. Preserve verified VM recovery and live-reference refusal; privileged oversized regression above. Host-private fixtures simulate these boundaries; no VM action here. |
| `Publication.commit`, `Store.finish_publication`, module-level `recover_publication`, bundle `export/finish/recover` | Independent exclusive owner/writer, recorded staging intent, projected and actual simultaneous budgets; ordinary writers refuse pending publication. Deferred commit leaves durable retirement receipt. | Preparing recovery removes only exact stage; committed finish/recovery verifies payload before exact superseded retirement. Reuse `test_publication_failure_preserves_three_exports_then_commit_rotates`, `test_publication_recovers_durable_intent_without_losing_exports`, `test_committed_publication_verifies_payload_before_retirement_and_retries`, `test_deferred_publication_is_durable_inspectable_and_finishes_exact_retirement`. |
| Plan accepted publication `plan_evidence.preserve/recover` | Separate plan owner/publication; verified cumulative ledger and stable locator must precede old-generation retirement. Foreign locator/owner changes refuse. | Reuse `tests/unit/test_plan_evidence.py`: `test_committed_interruption_recovers_index_before_retiring_old_proof`, `test_foreign_index_change_blocks_committed_recovery_and_preserves_payloads`, `test_changed_publication_owner_refuses_before_index_replacement`. E04/E07 retain this order. |
| `Store.discard_completed`; `tools/cleanup_e2e.py`; `tests/integration/check_retained_runs_cleanup.py` | Explicit selected execution discard only; activity/owner/writer, completed/unmarked owner, full identity audit; privileged recovery plus leases/live-reference guard. Workflow/diagnostic journals excluded. | Journal survives partial deletion for retry. `test_explicit_discard_audits_every_allocation_before_deletion`, `test_explicit_discard_retries_partial_deletion_and_uses_latest_registration`, `test_host_discard_leaves_vm_and_workflow_stores_untouched`. |
| `Store.discard_unpublished_input`; `cleanup_e2e.py` selected unpublished-input recovery | Derived exact qualification input, activity/owner/writer, finished/unmarked journal, absent completion manifest, latest recorded identity. No published/unknown/replaced adoption. | Exact retry after partial deletion; `test_unpublished_input_recovery_refuses_unsafe_or_published_inputs`, `test_unpublished_input_recovery_retries_partial_deletion_and_latest_identity`. Preserve this scoped route in E04. |
| `tools/test_input_transfer.py`; `latest_allocations` claim retirement | Two-owner durable transaction and writer mutation guard. Retires cleanup claim, **not payload**; ordinary reads/writes using writer lock refuse pending intent. | Identical transfer resumes both commits; no older claim resurrection. `test_retirement_never_resurrects_an_older_claim_and_invalid_receipts_refuse`, `test_pending_transfer_blocks_all_ordinary_retention_writers`. E04 preserves this dependency. |
| Explicit legacy cleanup/migration | `tests/integration/check_tmp_storage_cleanup.py` finite manifest/live-reference/full audit; `check_storage_migration.py` verifies copied diagnostics before exact originals retire. Separate authority, no source-name sweep. | Reuse `tests/unit/test_qualification_storage_cleanup_safety.py::test_legacy_cleanup_audits_everything_before_removing` and migration tests above. E11/E12 must not repurpose these into general proof deletion. |
| Scratch/runtime and separate media retirement | `tools/test_storage.py` inherited owner FD, scratch initialization/reclamation receipts and exact runtime identity; recording/screenshot owners preserve their explicit exceptions. No required-proof retention session is implied. | Reuse `tests/unit/test_test_storage_cleanup_safety.py::test_interrupted_scratch_reclamation_keeps_external_identity`. E04 retains separation; captured media must have its independently declared lifetime. |

Current capacity protections are narrower than required-proof preservation:
ordinary sessions may expire older disposable records before discovering an
oversized current run; finalization preserves that run, while execution startup
can later retire it after verified recovery. Publications preflight existing plus
projected payload and check actual old plus staging use; precommit failure leaves
prior exports intact, committed failure resumes recorded retirement. Bundles
remain limited to 1 GiB, 60,000 files, 64-MiB manifest, depth 32 and 256 explicit
selections. Identical records at the same original path deduplicate; identical
bytes at different paths remain distinct members. E01a must define bounded
segmentation/compaction and accounting; E03/E04/P12 deliver it without changing
budgets or provenance merely to fit a campaign.

### Controller dependency inventory

`tools/plan_launcher.py::response_validator_sources` currently hashes exactly
eight files: `plan_launcher.py`, `execution_plan.py`, `document_checks.py`,
`launcher_runtime.py`, `plan_evidence.py`, `plan_evidence_recovery.py`,
`evidence_bundle.py`, `detached_launcher.py`. Keep these. The following is the
audited missing/conditional closure, not an automatic import/filesystem scan.
Registration below is proposed delivery, not a change made by E01.

| Source | Why retained decisions depend on it / exclusion | First delivery disposition |
| --- | --- | --- |
| `tools/test_retention.py` | `Selection.load` inspection; export publication/commit; plan publication recovery; detached startup allocation/rotation. | E02 register existing closure; E04/P02 lifetime changes, P11 restart check. |
| `tools/test_storage.py` | `plan_parent/publication_parent` owner-private roots, `directory`, scratch descriptors and workflow allocation. | E02 register; E03/E04 changes/P11. |
| `tools/test_input_transfer.py` | `Store.locked` invokes `mutation_guard` for writer lock except explicit transfer; affects proof inspection/publication admission as well as deletion. | E02 register; E04 preserve refusal/P11. |
| `tools/launcher_git.py` | Direct `closeout` ownership, suspended baseline release, pull/stage/finish and accepted-result Git retry. Currently **unguarded**. | E02 register; E07/P08/P11. |
| `tools/onpc-test-artifacts` | `plan_evidence.preserve` target helper authenticates caller, plan/target selection and structured unavailable versus refusal; affects renewal. | E02 explicit helper-source registration; E03/E05a/E07/P05/P11. E01a settles installed generated-helper identity. |
| `tools/launcher_question.py` | Validates blocker and retains answer used for another session. | E02 register; E07 blocked-answer/P11. |
| `tools/plan_reconciliation.py` | Startup split/consolidation validates retained queue/task/acceptance transfer. | E02 register; E07 recovery/P11. |
| `tools/vm_selection.py`, `tests/integration/vm_config.py` | Ordinary command target binding and bundle catalogue registry validation; source identity relevance supplies no VM-operation authority. | E02 register relevant source closure; E01a distinguishes source from selected config/input identity, E07/P11. |
| `tools/test_activity.py` | Runner ownership via `regression_session`, `test_launcher`, `test_recovery`; inherited descriptor identity/exclusion. Not directly imported by current ordinary controller. | E03 specifies owner-handoff API; E06 producer ownership. Exclude from ordinary in-process closure unless retained decisions import/use it; introducing task then registers/P11. |
| `tools/repair_evidence.py`, `fix_tests.py`, `write_e2e.py` | Specialized controllers are not ordinary worker imports; their own lifecycle and acceptance policy remains authoritative. | E07a/P07/P11-equivalent supported safe boundary; no extra retries/budgets. |
| Presentation/view/progress/watch modules | Exclude rendering-only behavior from proof validation inventory. Transport/supervisor changes supplying capture provenance require fresh disposition. | E01a freezes boundary; introducing row registers any new decision dependency/P11. |
| Recording, package-input and VM-lifecycle modules | Conditional storage callers outside audited ordinary proof-root/scratch route; not included just because another storage function imports them. | E06a classifies media/qualification dependencies under their owners. No broad VM/product source watcher. |

Planned extraction boundaries have **no registered filenames yet**: logical
identity/member/context resolution (E02); authenticated finalized capture and
acknowledgement (E03); dependency/retirement/capacity decisions (E04); shared
Markdown parsing (E08); structured reference generation/semantics (E09); typed
severity/consumer-role/debt policy (E10). Each introducing row must register its
actual retained-decision modules and run P11 before close-out; E07 is composition,
not deferred first protection.

Existing `tests/unit/test_execution_plan_launcher.py` restart anchors are
`test_rejected_result_stops_before_retrying_with_stale_validation_code`,
`test_valid_result_source_change_stops_before_next_admission_or_blocked_wait`,
`test_valid_continuation_source_change_reaches_fresh_startup_recovery`,
`test_source_change_while_blocked_retains_answer_before_new_session` and
`test_response_validator_sources_detects_content_changes_only`. The first four
mock source dictionaries; the last changes real fixture bytes but tests the
hasher separately. None substitutes for P11 connecting real bytes to worker
decisions. The module's `synthetic_plan_evidence` autouse fixture also stubs
capture/carry/preserve/recover/rewrite; P08/P11 composition must use real functions.

### Concrete questions handed to E01a

All families above have a delivery assignment. These remaining questions belong
to protocol design, not a missing prerequisite or authority request for E01:

1. Define authoritative dependency/consumer ownership, finalized immutable subset,
   producer/attempt authentication, lock order and durable acknowledgement that
   releases a source. Cover cleanup appended after terminal candidates, standalone
   short registration and partial diagnostics; environment inheritance alone is
   insufficient authority.
2. Define exact-member/check/attempt/target/input link syntax and versioned
   manifest/receipt compatibility, using existing bundle/accepted ledger rather
   than a second archive. Current generic locator rewriting is insufficient.
3. Define selective journal discovery/locking for explicit archived members.
   `Selection.load()` currently inspects every catalogue journal before loading
   explicit bundles; direct bundle reads avoid this path and cannot prove P05.
4. Specify every retirement/dependency gate above, stale/missing acknowledgement,
   explicit release/replacement and simultaneous capacity/compaction accounting,
   including resumable partial-capacity edits and retained original inputs.
5. Bind required proof/instruction, optional presentation, example/operational path
   and historical unavailable roles to the owning declaration and exact claim
   revision. Code spans are legacy evidence in one reader and examples in another;
   neither interpretation may silently downgrade required proof.
6. Freeze the explicit restart inventory, helper source versus installed identity,
   target config/input boundary and specialized safe-boundary interface. Preserve
   session counts, selected targets, suspended inputs and protected Git/queue work.

E01b must independently review these maps and proposed answers, freeze P01–P12's
concrete coverage/allocation and resolve provisional ranges before runtime work.
No E01 source finding supplies that gate or acceptance for another task.

## E01a protocol proposal

Proposal date: 2026-10-21. The following answers the six E01 questions. These
schemas, library names and helper options are **proposed and unimplemented**;
E01b must independently freeze them and their delivery allocation. Current
runtime contracts remain authoritative until the owning delivery passes. This
section records design review, not execution of P01–P12 or product acceptance.

### Canonical identities and wire records

Use `evidence_bundle.encoded` canonical JSON (sorted keys, compact separators,
ASCII escapes), SHA-256 lowercase hex and duplicate-key rejection. Versioned
objects have exactly the keys specified below; reject unknown versions, fields,
duplicate IDs, nonfinite numbers and integer/boolean confusion. Strings are
UTF-8 values of at most 4,096 bytes without control characters; paths retain the existing
no-link, no-traversal, privacy and mount checks. IDs are 64 hex characters;
run/attempt tokens are fresh 32-hex tokens issued by the owning controller, never
derived from a title, timestamp or basename. Empty target means a declared
host-only check; it cannot match a named target. Lists of sets are sorted and
unique before hashing; command arguments and ordered input selections retain
their order. Every digest below hashes canonical bytes, except file digests,
which hash the exact original bytes.

The proposed logical record schema is `onpc-evidence-record`, version 1:

| Exact field | Meaning and validation |
| --- | --- |
| `schema`, `version` | Literal schema name above and integer `1`. |
| `context` | Exactly `repository`, `workflow`, `owner`, `run`, `task`, `check`, `attempt`, `target`, `inputs_sha256`, `sources_sha256`. Repository is the validated checkout identity, workflow the checkout-relative master or registered runner name, owner the authenticated journal identity, run its token. Task/check are exact registered IDs/selectors, attempt is issued before execution. Input digest binds role, original name, length and digest of each finite input, including selected target configuration; source digest binds the declared executable dependency inventory and bytes. |
| `record_id` | Hash of `{schema,version,context}`. Relocating storage never changes it. A retry, changed input/source or different target produces another record. |
| `status`, `completeness` | Status is `passed`, `failed`, `interrupted`, `not_run` or `diagnostic`; completeness is `complete` or `partial`. Neither an archived diagnostic nor a partial candidate can supply a passing check. |
| `members` | Finite entries with exactly `member_id`, `role`, `original_path`, `source_allocation`, `bytes`, `sha256`, `required`. Role is result, input, command, junit, tap, cleanup, diagnostic or media. Source allocation preserves the existing journal/run/device/inode/mode provenance; original path is provenance, never permission to open it. Member ID hashes record ID, role, original path and byte digest. |
| `dependencies` | Sorted exact `(record_id,closure_sha256)` pairs, never an unqualified latest result. No cycles; validate the finite transitive closure before acceptance. |
| `cleanup` | Exactly `state`, `record_members`, `scope`. State is `complete`, `failed`, `pending` or `not_applicable`; members name exact cleanup records and scope names the resources actually owned. `not_applicable` needs an owning contract declaration. Producer execution cleanup is separate from capture-publication retirement cleanup. |
| `closure_sha256` | Hash of the entire record excluding only this field. It binds status, completeness, every member, dependencies and cleanup. Same record ID with differing closure is a conflict, not a newer pass. |

Keep command/result/input/cleanup records independently addressable. Required
JUnit/TAP or media cannot disappear through deduplication or a diagnostic size
limit. A required media member uses a verified captured copy, or an exact external
dependency with its owner's explicit lifetime; latest-only recordings alone
cannot promise durable proof. No credential directory is a capture selection.

Extend the existing ZIP format, not its compression/extraction policy. Bundle
manifest schema `2` has exactly the v1 keys `schema`, `files`, `inherited`,
`source_budgets` plus `records` and `member_map`. Physical `files` keep v1
provenance and generated `files/NNNNNNNN` names. `records` contains the logical
records above, sorted by record ID. `member_map` is a JSON list of objects with
exactly `record_id`, `member_id`, `physical_member`, `original_provenance`, sorted
lexicographically by `(record_id, member_id)`, with each pair unique. Physical
member names select exactly one `files[].member`; original provenance contains
exactly `original_path`, `source_allocation`, `identity`, using the shapes below.
Require exactly one mapping for every logical member and no orphan mappings or
physical members. Equal bytes may share one physical member only when all
logical origins remain explicit; unequal bytes or conflicting provenance refuse.
Metadata, logical entries and dependencies all count toward finite limits; byte
deduplication cannot evade the 60,000-file/logical-member bound. Verify logical
closure against stored bytes before returning any result. Schema 2 receipt has
exactly `schema:2` plus the existing `sha256`, `bytes`, `selection_sha256`,
`identity`; `selection_sha256` binds the whole manifest. Never silently add fields
to v1's strict reader.

Accepted ledger schema `2` has exactly `schema`, `plan`, `generation`,
`previous_index_sha256`, `tasks`, `records`, `segments`. Preserve each task's v1
result, inputs, records, attempt and complete-cleanup assertions; add exact logical
record/closure pairs in a new `record_refs` field of each task proof. `records`
maps record IDs to complete logical records. The stable locator schema `2` has exactly
`schema`, `plan`, `generation`, `ledger`, `ledger_sha256`, `segments`, `tasks`.
Ledger segment entries contain exactly `id` and `record_ids`; external locator
segment entries contain exactly `id`, `bundle`, `sha256`, `selection_sha256`,
`allocation`. The archived ledger never contains its own segment's archive or
manifest hash: receipts and the external locator bind those physical hashes.
Locator `ledger` has exactly `segment_id` and `original_path`, selecting an exact
original member whose digest equals `ledger_sha256`. Locator `tasks` repeats the
verified ledger task proofs; it cannot override them. Ledger is an exact original
member in one segment, not a second archive format.
Task lookup cannot substitute for verifying the requested
record/member and dependency closure. A missing segment refuses its dependents;
it does not invalidate unrelated verified proof. Locator generation replacement
uses the existing previous-index digest compare-and-replace.

The external working collection index is `onpc-evidence-collection`, version `1`,
with exactly `schema`, `version`, `owner`, `generation`, `previous_index_sha256`,
`segments`, `records`, `consumers`. Its segments use the external locator entry
shape; records map record IDs to segment/member/closure selectors and consumers
map IDs to exact revisions. It is published after segment verification and before
acknowledgement, using the same private atomic index/publication recovery route.
It never supplies an acceptance verdict or replaces the accepted ledger.

### Frozen nested wire shapes

E01b removes implicit tuple keys and implementation-specific nested dictionaries.
The following are reusable strict JSON shapes, not Python object representations.
Every object has exactly its listed keys. Hashes/IDs are lowercase 64-hex;
run/attempt/nonce/generation tokens are 32-hex unless a generation is explicitly
a monotonic integer. Integers reject booleans, sizes/counts are nonnegative and
device/inode values are positive. All paths use the existing validated absolute
provenance shape or the explicitly declared checkout-relative document shape;
none grants permission to open a path. Map keys are strings; finite lists with
set semantics are sorted by their identifying fields and reject duplicates.

| Shape | Exact keys, representation and checks |
| --- | --- |
| Repository | `root`, `device`, `inode`, `uid`; validated checkout root and pinned directory identity, authenticated owner UID. Relocated report storage does not change it; another checkout cannot adopt it. |
| Caller | `uid`, `gid`; derived authenticated nonnegative integers, never request-supplied authority. |
| Directory identity | `device`, `inode`, `mode`, `uid`, `gid`; exact pinned stat values, existing private directory/mount guards apply. |
| Owner | `repository_sha256`, `caller`, `journal`, `identity`; hash of Repository, Caller object, trusted journal directory provenance and Directory identity. Revalidate against its held owner descriptor; a JSON copy is no authority. |
| Allocation | Existing v1 bundle allocation: `path`, `device`, `inode`, `mode`, `journal`, `run`; mode is integer `448` (0700), valid journal run token, existing allocator/ownership/identity checks. |
| File identity | Existing `evidence_bundle.fingerprint` ten-integer list in exact order: device, inode, full mode, UID, GID, link count, byte length, mtime_ns, ctime_ns, blocks. Regular single-link file, allocated bytes = blocks × 512. |
| Record reference | `record_id`, `closure_sha256`; sorted unique list by record ID. `dependencies` uses these objects, not tuple keys. |
| Member selector | `record_id`, `member_id`, `closure_sha256`; exact immutable logical closure. |
| Consumer revision | `consumer_id`, `revision_sha256`; consumer ID hashes owner plus its stable workflow/document/check key, revision binds exact claim/role/assertions. |
| Capture producer | `repository`, `caller`, `owner`, `run`, `attempt`, `nonce`; the reusable objects above plus issued tokens. Target is bound in the record context and authenticated registration. |
| Sealed request | `owner`, `allocation`, `mappings`; independent finished Owner and Allocation, mappings are the exact sealed mapping objects specified in the capture protocol, sorted by member ID. Their `identity` is the sealed File identity; original File identity is retained in `member_map.original_provenance`. |
| Destination custody | `owner`, `allocation`, `segments`, `index_sha256`, `reservation_id`, `record_refs`; exact committed collection Owner/Allocation, external segment entries, index digest, catalogue reservation ID and Record reference list. Ack `destination` uses this shape. |
| Segment entries | External entries retain exactly `id`, `bundle`, `sha256`, `selection_sha256`, `allocation`; ID is `00`, `01` or `02`, bundle is exact segment directory provenance, allocation uses Allocation. Ledger entries retain only `id`, `record_ids` (sorted unique). |
| Working record selector | `segment_id`, `member_id`, `closure_sha256`; working index `records` is keyed by record ID and selects that record's result member. All supporting members remain in the verified segment manifest. |
| Cleanup scope | `owner`, `resources`; resources are sorted unique objects `kind`, `id`, `disposition`, with kind the registered resource type, ID its owning contract's exact selector, disposition `cleaned`, `preserved` or `not_owned`. Explicitly preserved maintenance scenes cannot imply restored/off state. `record_members` is a sorted unique member-ID list. |

Context `repository` and `owner` use Repository and Owner above. Capture
`consumers`, retirement `consumers` and working-index `consumers` values use
Consumer revision; maps key by that same consumer ID. Retirement `sources` is a
list of exact objects `allocation`, `members`; each member has `original_path`,
`identity`, `sha256`, `record_refs`. Retirement `replacements` uses Destination
custody objects. `entry_revisions` maps transaction/consumer/reservation IDs to
their canonical current-entry hashes. `source_allocation` and `sealed_allocation`
always use Allocation. Record members use File identity from their manifest
mapping without duplicating mutable stat fields into logical content identity.

Catalogue `schema` is integer `1`, `generation` a monotonic integer. `consumers`
maps IDs to full Consumer declarations; `captures` maps IDs to objects exactly
`request`, `state`, `ack` (ack is null before acknowledgement); `reservations`
maps IDs to objects exactly `transaction`, `state`, `destination`, `consumers`
(destination null while provisional); `retirements` maps IDs to objects exactly
`request`, `permit`, `removed`, `remaining` (permit null before permission).
Requests/ack/permits use their versioned shapes; removed/remaining use exact
retirement source entries. Reservation state is `provisional` or `durable`;
capture states are the transition table's states. Index maps and catalogue rows
must agree on IDs, owner, exact revision and complete closure; mismatch refuses.
No cyclic self-hash: destination custody names reservation ID, whose entry binds
that destination, rather than recursively embedding its own catalogue entry.
These formats freeze interoperability; delivery still registers validators and
refusal tests before any new writer or helper command runs.

### Exact references and planned interfaces

Canonical generated Markdown destinations are relative to the containing file:
`RELATIVE-LOCATOR#onpc-evidence-v1:RECORD_ID:MEMBER_ID:CLOSURE_SHA256`.
The three fields are lowercase 64-hex values with no optional components. The
reserved fragment is a structured selector, not a Markdown heading. Resolve
the locator lexically inside the validated checkout, pin its identity and verify
the ledger/segment/member plus the consumer's expected context. Do not strip the
fragment before semantic checking. Ordinary anchors retain normal Markdown
semantics. The destination may change after relocation; the selector must not.
Links choose a specific result or supporting member; a generic locator remains
legacy navigation and supplies no new exact-check proof.

The consumer declaration schema `onpc-evidence-consumer`, version `1`, contains
exactly `schema`, `version`, `consumer_id`, `owner`, `revision_sha256`, `role`,
`expected_context`, `references`, `state`. Revision hashes the original claim
bytes, role and required assertions; expected context fixes task/check/attempt/
target/input/source requirements for evidence. Each reference is discriminated:
`{kind:evidence,record_id,member_id,closure_sha256}` or
`{kind:document,destination,fragment}`. Document destinations resolve relative to
the declaring document inside the checkout; their context is the instruction or
presentation contract, not an invented check attempt. Document references confer
no evidence acceptance. Role is `required_evidence`, `required_instruction`,
`optional_presentation`, `historical_information`, `example` or `operational_path`;
state is `working`, `suspended`, `accepted` or `released`. Declaration owner is the
validated plan/check/catalogue owner, never arbitrary prose. Existing required
instructions/evidence stay required when no valid declaration exists. Queue
claim bytes and protected checkpoint fields retain their stronger existing guard.

Proposed library interfaces (names to register in E02–E10 before use):

| Interface | Exact request/result contract and delivery |
| --- | --- |
| `resolve_reference(reference, *, consumer, read_scope)` | E02: parse the selector, prove expected context, return record, exact member and verified closure; typed refusal otherwise. No latest-attempt fallback. |
| `finalize_capture(session_handle, *, record, consumer_ids)` | E03: only a live producer-owned session handle may issue a finite sealed request; returns a durable capture ID, not acceptance. No path/environment-only authority. |
| `capture_finalized(request, *, destination_owner)` / `acknowledge_capture(session_handle, ack)` | E03: independent verified publication, then exact source-owner acknowledgement; return the transaction state/receipt described below. No arbitrary active-source reader. |
| `dependency_gate(records, *, operation, catalogue_generation)` | E04: called under the existing deletion/mutation owner; returns exact safe release/replacement or refuses, never deletes by itself. |
| `resolve_archived(references, *, bundles, consumer, read_scope)` | E05a: selected finished publication scope only; validate both requested originals without inspecting an unrelated active producer. |
| `generate_reference(record, member, *, consumer, document)` | E09: emits the canonical relative destination only after exact closure/context verification. E08 owns parsing; E10 owns typed classification. |

Planned helper additions extend `onpc-test-artifacts`, not `tools/export`:
`bundle-plan` and `bundle-export` gain repeatable `--record-reference` destinations
and exactly one `--consumer` canonical JSON declaration for that structured mode.
They also gain repeatable `--capture` IDs, resolved only through trusted finished
sealed-subowner registrations. Capture IDs and structured references count in
the same finite selection limit; they never authorize reading the active parent.
Existing `--plan`, repeated `--target`, `--source`, `--bundle`, `--reference`,
`--summary`, `--expect` and `--defer-cleanup` retain their meanings. The helper
validates consumer ownership and exact plan/task inputs; a caller-authored JSON
role cannot relax a required contract. Legacy and structured selections may be
combined within the existing 256-selection total; mandatory sources/bundles are
always strict. `bundle-read` gains paired `--record-id` and `--member-id` with
required `--closure-sha256`, mutually exclusive with legacy `--path`; existing
offset/read limits apply. No new command is runnable until its parser,
documentation, installation and refusal regressions are registered.

The planned privilege-crossing custody action is `bundle-custody --transaction
ID --expect REQUEST_SHA256 --operation OP`, where OP is `inspect`, `reserve`,
`acknowledge`, `retire-permit` or `retire-finish`. It accepts no UID, journal path,
output destination or arbitrary source. Derive its one registered immutable
capture/retirement request from authenticated caller, repository and transaction;
validate the expected digest, owner-issued authority and operation's durable
predecessor. Return canonical transaction state/receipt or a typed refusal.
`reserve` is callable only inside verified publication, before releasing the
destination read scope; other operations use the nonnested protocols below.
Host-only code calls the same library directly. E03 registers capture operations;
E04 registers retirement operations with finite prepared-set/permit schemas
binding transaction, source identities, consumer revisions and replacement
digests. This scoped action supplies no source/VM cleanup or discard authority.

Exit 3 remains only exact absent renewable references, with existing legacy
`error: evidence_unavailable, paths` payload preserved. Structured mode returns
versioned `error: evidence_unavailable, schema:1, references` and exact selectors;
controllers opt in before consuming it. Mandatory absent source/bundle, denial,
unsafe identity, corruption, active source and wrong context remain exit 2 with
distinct typed reasons. Do not parse free-form stderr as a missing-proof signal.
Legacy `read`/`tail` diagnostic slices never establish complete capture.

### Finalized capture authority and durable transitions

The producer session API issues an in-process opaque handle from its held owner
descriptor, private journal identity, run and issued attempt. Validate all four
against current locked state when sealing and acknowledging. `ONPC_TEST_RETENTION`
contains only path/run and inherited activity FDs coordinate exclusion; neither
authenticates a record. Only trusted producer code holding that session handle
can issue a request. An independent helper derives caller UID/GID through its
existing authenticated entry; it never accepts supplied UID or environment as
authority. Bind repository, journal identity, allocation identities and registered
target to the request. Cross-process callers can consume an issued sealed request,
but cannot mint a producer handle through the public reader.

Use a registered sealed snapshot allocation with its own retention subowner,
separate from the active producer journal. Its owner issues a fresh nonce, records
the exact finite allowlist and request digest privately, copies closed final files
under pinned descriptors, verifies before/after identity/digests, then fsyncs and
finishes that subowner. The parent records the subowner/allocation and durable
dependency intent before copying; it remains responsible for interruption and
budgets. A missing seal or active subowner refuses. General selection still
requires finished owners: the collector reads only this independently finished
snapshot, never the parent journal or its mutable siblings. The nonce is a replay
binding, not a bearer secret or substitute for private owner validation. Reuse
shared storage/retention allocation; no caller-selected output root.

The shared allocator derives one bounded sealed-subowner slot from validated
repository/caller/parent-owner identity and capture ID under shared capture state;
the helper accepts an ID, never a caller-supplied journal path. Its durable slot
registration contains parent owner/run/attempt, capture/request digests and exact
subowner/allocation identities. Publish registration before sealing, and mark it
readable only after its independent finished-owner commit. Helpers consult this
finite registration without opening the active parent journal. Missing, pending,
foreign or replaced registration refuses. Parent and sealed allocations are
disjoint, never nested cleanup claims. Parent recovery owns subowner cleanup;
subowner rotation cannot bypass parent budget/dependency gates. Capture ID hashes
producer binding and its fresh 32-hex nonce, so retries reuse the same slot.

Capture request schema `onpc-finalized-capture`, version `1`, has exactly
`schema`, `version`, `capture_id`, `producer`, `record`, `consumers`, `sealed`,
`request_sha256`. Producer binds repository, caller, journal/device/inode, run,
attempt and nonce; sealed binds the finished subowner and exact allocation/file
identities. Each sealed mapping has exactly `member_id`, `original_path`,
`source_allocation`, `sealed_path`, `sealed_allocation`, `identity`, `sha256`.
Keep original provenance distinct from the physical sealed copy; verify both
identities and their exact byte/digest mapping before archive capture.
Consumers are the authoritative owner-issued consumer IDs/revisions.
Request hash excludes only itself. Ack schema `onpc-capture-ack`, version `1`, has
exactly `schema`, `version`, `capture_id`, `request_sha256`, `record_id`,
`closure_sha256`, `destination`, `catalogue_generation`, `cleanup_complete`.
Destination binds the committed publication allocation, receipt/manifest digests
and exact logical member mapping. Ack cleanup means capture transaction cleanup;
producer cleanup is already bound in the record. A receiver independently verifies
the destination before recording the ack; ack JSON alone never authorizes deletion.

| Durable state | Required action and interruption/cancellation outcome |
| --- | --- |
| `required` | Owner registers the finite consumer dependency before the producer can become rotation-eligible. Persist capture intent and source identities. Failure leaves original required and diagnoses admission/capacity refusal. |
| `sealing` | Register empty snapshot before payload. Copy only the finalized allowlist. Interrupted partial stage remains identity-recorded; recover that exact stage or retry from the unchanged required source. No acknowledgement. |
| `sealed` | Finish and verify immutable subowner, fsync request and parent intent. Collector may now inspect this finite source while parent runs. Changed source/seal refuses; prior proof and original remain. |
| `publishing` | Independent destination owner preflights all simultaneous usage; existing `Publication` preparing/committed transaction owns recovery. A preparing failure removes only its exact stage; prior proof and sealed source survive. |
| `durable` | Verify committed payload and manifest; publish working collection index by digest compare-and-replace, then finish recorded publication retirement. A crash after commit recovers the exact index before retirement. No source release yet. |
| `acknowledged` | Source owner revalidates producer/request/attempt/closure, verified destination reservation and consumer revisions, then commits ack and dependency replacement. Lost reply repeats the same capture ID idempotently. Pending/stale/foreign ack cannot release anything. |
| `released` | Existing retention can retire source only after its ordinary finished-owner/identity/lifecycle guards and the dependency gate agree. Required working/accepted destination stays reserved until owner release or verified replacement. |

Cancellation before acknowledgement preserves required source and recoverable
intent; after acknowledgement it preserves the durable destination and exact
consumer bindings. Cancellation supplies no pass. Resume the same transaction,
not a new attempt or retention slot. An owner may explicitly abandon a never-used
consumer through its normal cancellation/cleanup contract; it cannot release an
accepted or suspended consumer or erase failed-attempt diagnostics by implication.

Finalization hooks must respect current late writes. `Report.close` is not the
aggregate seal: `regression.retained_main` may append `failure.json`, and
`regression_session.owned_worker` appends recordings and result after `_main`.
Category/worker captures use closed dedicated records while the shared aggregate
report remains mutable. Standalone short report registration must occur inside a
live owned session before finalization. Complete qualification seals after owned
cleanup; closed immutable diagnostic subsets may seal with cleanup failed/pending
and completeness partial. Never copy still-written files. Later recovery issues
a distinct linked cleanup/recovery record with a fresh attempt, preserving the
original failure rather than changing its immutable closure under the same ID.
Failed/interrupted diagnostics retain finite/truncated/native-log availability.
E2E terminal candidates precede outer/collector cleanup: the outer owner writes
the authoritative post-close returned ledger into a separate registered closure
allocation, links candidate digests and preserves collector exact-list checks.
`PrivateCollector.close()` only closes its descriptor. Recovery probes can leave
a deliberately live maintenance scene: their diagnostic cleanup scope must say
so, never claim restored/off VM state. Transport credentials remain excluded.
Only passed, complete records whose required closure and declared execution
cleanup passed can satisfy a passing check. Declared no-resource cleanup is
vacuous only under its owning contract; failed/pending cleanup is never promoted.

### Lock order, dependencies and retirement

Keep existing checkout activity, nonblocking journal owner, applicable VM
compatibility/named lease, then journal writer order. Multiple source owners and
writers use trusted absolute journal-path order as in input transfer; never
upgrade a shared read lock in place. All dependency catalogue operations take a
short catalogue lock **last**. While holding it, acquire no other owner/writer/
lease, perform no payload I/O, helper/VM call or publication. There is no wait
cycle through destination and source journals: seal under source ownership,
release source writer, publish/verify under independent destination ownership,
release destination locks, then acknowledge through prepared intent and exact
catalogue compare-and-replace. Ordinary read scopes hold only needed shared owners.

The authoritative dependency catalogue is version `1`, with exactly `schema`,
`generation`, `consumers`, `captures`, `reservations`, `retirements`. One canonical
catalogue per authenticated caller and validated checkout lives in caller-private
shared host state; trusted host library code mutates it directly. A privileged
producer/helper switches to its derived caller identity for that same catalogue,
never maintains an independent mirror or trusts supplied UID/path/ack JSON.
For every ever-required privileged source, retain an authoritative root-private
safety witness in its source state **before** catalogue registration: exact caller,
checkout, transaction, source identities, consumer revisions and required closure.
Absent/changed caller entries never make that source disposable. Release needs
the validated lifecycle's root-issued witness too; caller-authored role/release
changes cannot discharge privileged requirements. Source private state is a
safety witness, not a second mutable dependency catalogue. Host-only capture and
retirement need no new privileged operation. Entries identify repository, owner,
exact allocation/record/closure, consumer revision and transaction ID.
Reservations are finite persistent references to verified replacement receipts;
they are not new payload copies. A destination reservation is durable before
verification locks are released; retirement respects it. Source acknowledgement
CAS replaces its original dependency with that reservation, so there is no gap
between verification and deletion. Failed CAS keeps both copies reserved until
exact recovery; it never releases the original. A retirement intent under the
catalogue lock blocks new dependencies on that allocation until deletion commits
or exact recovery aborts it. New consumers either bind the durable replacement
or refuse; no late claim can resurrect deleted proof. Catalogue snapshots alone
grant no deletion authority, and missing/corrupt required catalogue state refuses.

Separate provisional capacity/staging reservations from verified durable custody.
A provisional reservation cannot satisfy a consumer or acknowledgement. Preparing
publication recovery removes only its exact stage plus provisional reservation,
leaving all required source dependencies intact. Promote to durable reservation
only after committed payload verification, before releasing its verification
locks. Outstanding source transactions prohibit unilateral reservation release.

Acknowledgement protocol is source-writer prepare/fsync, release writer,
catalogue CAS (direct library call for host, authenticated helper for privilege
crossing), then reacquire writer and mirror the result. The helper reads only
the sealed registration/prepared immutable request, never reacquires caller-held
source owner/writer/VM leases or runs recovery. Same transaction with a lost reply
returns its canonical result. If final source revalidation fails after catalogue
CAS, preserve the reservation and refuse; never silently undo durable custody.
Use exact-entry revisions for CAS, tolerating unrelated catalogue generation
increments while rejecting changes to this transaction/consumer.

Retirement request schema `onpc-retirement-intent`, version `1`, has exactly
`schema`, `version`, `transaction`, `owner`, `operation`, `sources`, `consumers`,
`replacements`, `request_sha256`. Sources contain exact recorded allocation and
member identities; consumers contain exact IDs/revisions; replacements contain
verified record/closure/receipt/reservation bindings. Operation names the existing
owning retirement route, never a general delete command. Hash excludes only
itself. Permit schema `onpc-retirement-permit`, version `1`, has exactly `schema`,
`version`, `transaction`, `request_sha256`, `entry_revisions`, `state`,
`permit_sha256`; state is `permitted`, `removing`, `finished` or `aborted`, and its
hash excludes only itself. Bind every permit to the full immutable request and
owner; one-use progress records retain exact removed/remaining identities.

Retirement uses the analogous prepare/permit/remove/finish protocol. Audit the
**whole** proposed set of identities, dependencies, replacement closures and
capacity before the first destructive action. Under existing owner/lifecycle
guards and writer, fsync that exact prepared set; release writer, obtain durable
catalogue retirement intents/permit for the whole set, then reacquire writer and
repeat identity/lifecycle/entry checks before deleting only approved identities.
Report completion outside writer. Hold existing owners/VM leases throughout;
helper must not reacquire them. Interrupted removal keeps permit and all original
identities for exact retry; changed source refuses rather than using a stale
permit. Abort is allowed only before any deletion; after partial removal retain
the permit and all remaining/original identities for exact retry or refusal.
Private privileged witness persists until exact retirement completes.
Immediately before privileged deletion, independently reverify replacement
allocation/receipt/complete closure in a pinned read scope protected by its
catalogue reservation; a historical root ack alone is insufficient. Missing or
changed replacement refuses even when old ack JSON matches. Payload verification
occurs outside catalogue locking, with entry revalidation under that lock.
Acquire destination read ownership only while source writer is released; the
deletion owner retains that preacquired pinned scope through source removal.
Never acquire a destination lock from inside source writer or a catalogue lock.

Consumer creation/release is owned by the existing plan/check lifecycle, with
exact revisions and CAS generations, not a Markdown scan. Continuation,
prerequisite suspension, rejected responses, capacity recovery and accepted Git
retry keep dependencies. Acceptance atomically promotes working references to
accepted only after full proof/cleanup verification; Git failure keeps that
accepted closure. Superseding a result retains the old attempt whenever any
consumer still references it. Explicit tracked-document inventory may register
historical information through its owning reviewed migration; it supplies no pass.

Apply the gate at every E01 retirement route:

| Existing boundary | Additional decision, without replacing current guards |
| --- | --- |
| `Store.session` direct count deletion and `prune` | Check exact dependencies/reservations before **both** direct old-run removal and pruning. If a fourth required generation cannot be carried within the three-run limit, refuse admission before deleting; do not silently keep an unbounded fourth run. |
| `Store.reconcile` and host startup | Oversized completed execution is disposable only with no required original or a verified matching acknowledged replacement. Failed capture, pending/stale ack and capacity errors preserve it. Recovery archives markers and validates recorded ownership as today. |
| Privileged startup | Gate both `reconcile` and the later independent `prune(keep=2)` under existing VM leases/live-reference audits. No helper path bypasses either decision. |
| `Publication.commit`, finish and recovery | Preflight the full superseded set; provisional stage reservations cannot release sources. Preparing cleanup removes only its exact stage/provisional reservation; after commit verify complete replacement, publish index and promote durable reservation before retirement. |
| Plan `preserve/recover` | Verify ledger and exact prior index, replace locator durably, then retire only allocations whose complete dependency mappings moved. Foreign locator/owner or corrupt payload preserves the transaction and refuses. |
| Explicit completed discard | Retain specific developer authority and full existing audits. Required proof must first have a verified replacement or explicit consumer-owner release permitted by that authority; a generic discard cannot erase accepted claims. No workflow/diagnostic scope expansion. |
| Unpublished-input discard | Keep exact derived selector, absent completion manifest and recorded identity. A published input is still refused. An input actually required by a captured closure needs verified replacement/release first. |
| Input cleanup-claim transfer | Payload is unchanged. Transfer dependency ownership with the same two-owner durable intent/identity; block ordinary mutation on either pending half, never resurrect an older allocation claim. |
| Explicit legacy cleanup/migration | Existing finite authority and full audit remain; verify copied exact required closure before originals retire. Diagnostic migration deliberately skips input/assets/package and credential names; its success alone is no complete-proof ack. No filesystem/name sweep or adoption of unknown legacy data. |
| Scratch/runtime, recordings, screenshots | Retain their separate owner/FD/latest-only/explicit cleanup contracts. Copy/ack required recordings before same-name rename replacement as well as unlink; a gate only at `_remove` misses overwrite. Do not pin scratch, sockets or screenshot exports as durable proof. |

### Bounded collections, capacity and reuse

Working and accepted collections each use their existing owning bounded journal,
not one journal per record/segment. All sealed subowners and recovery stages are
charged to the parent admission budget; creating a subowner cannot multiply
capacity. Keep at most three generations and 4 GiB allocated blocks per journal,
1 GiB projected bytes per ZIP, 60,000 logical/physical files, 64-MiB manifest,
depth 32, 256 selections and existing 16-MiB read slices. Control JSON adds no
unbounded exception: catalogue/ledger/request manifests must fit 64 MiB and
60,000 total logical entries per collection. Receipts are at most 4,096 bytes;
each manifest has at most 256 inherited-bundle and 64 source-budget entries.
New limits do not enlarge legacy recovery/checkpoint readers' existing bounds;
fail admission if metadata alone cannot fit. Stream larger allowed records in
bounded read slices, never truncate metadata to fit a single read.

Use at most three immutable ZIP segments in the **same** generation/allocation;
each uses the existing verified manifest/receipt format. A logical record and
its required closure must fit one segment; cross-record dependencies may name
other segments. Deterministically pack by record ID, deduplicate only equal
verified payload bytes while retaining every origin, and refuse a fourth segment.
The generation's aggregate logical-member/manifest limits remain the collection
limits above. On append, copy/repack only the finite required closure, remove
only explicitly released metadata/payload and superseded unreferenced control
records, and publish a complete replacement generation. No references depend
on old segment paths; preserve record/member/closure IDs. No hardlinks or shared
writable payload, recursive ZIP nesting, external hosting or new archive format.
This is a bounded compaction strategy, not a promise that any campaign can fit.
Schema 2 collection layout is exactly `segments/00/`, optionally `01/` and `02/`,
each containing only `evidence.zip` and `receipt.json`; the external index binds
the registered collection allocation and each segment's pinned identity. Extend
the existing verifier to this finite layout; ordinary v1 two-file roots retain
their strict listing and verification. No extra segment/journal allocation occurs.

Preflight an explicit allocation ledger before creating any new stage:
`peak = live_old + sealed_sources + preparing_new + committed_unretired +
receipts_and_indexes + recovery_allocations + projected_copy_overhead`.
Measure allocated blocks and conservative projected ZIP/directory overhead;
account every unique allocation identity exactly once in its owner and show
parent subowner charges. Cross-owner copies count on both sides physically;
do not subtract superseded bytes before verified retirement. Reserve projected
bytes/files/metadata first, compare actual use before commit and recover any
interruption with its original reservation. Capture, compaction and reuse cannot
spend another slot while a recorded transaction is pending. If old+new cannot
fit, preserve old and refuse before destructive rotation, model retry or queue
mutation; in-place compaction is prohibited.

Capacity diagnostics give the exact required closure, current/projected/limit
bytes and entries, held consumers and one supported next action. Routes are:
reuse a matching verified existing export; finish/recover the exact recorded
publication; release obsolete consumers through their owning lifecycle; or
group a smaller independent selection and materialize it with existing
`bundle-plan`/`bundle-export` under unchanged budgets. An ordinary export remains
bounded, so it is not a durable archive/release receipt by itself. No external
archive/import service is introduced here. If required old+new still cannot fit
after permitted release/repacking, refuse and request an explicit separately
reviewed storage requirement; preserve required proof. Never propose discarding
required evidence, raising limits silently or rerunning unrelated acceptance.

E05's reusable export key is the hash of authenticated repository/caller,
destination owner, exact selection/context/closure and format version. In one
pinned read scope verify the recorded allocation, archive/receipt identities,
all bytes and authority; return the existing receipt without session allocation.
Missing/replaced/corrupt export refuses reuse, rather than success or an
unannounced fresh export. A deliberate fresh publication needs a fresh plan and
normal capacity checks. Same basenames or bytes with different provenance retain
different logical references. Group related records in one atomic publication;
shared readers exclude mutation and cached verification ends with its pinned
descriptor scope.

### Selective authenticated archived reads

For P05 retain the actual `bundle-plan --plan --target --bundle --reference`
shape. First authenticate caller, validate the plan and canonical target registry,
and derive only trusted possible journal names without inspecting them. Open
explicit finished publication journals/bundles first under sorted shared locks;
verify each archive once. Build an exact original-member index and check both
requested old members/context/digests. An absent original with an exact archived
match depends only on that finished publication, not the current target journal.
Probe original path existence safely without traversing links; access/unsafe
path is a refusal, not absence. If a live original exists, select its exact
recorded journal and perform normal finished-owner, identity, conflict and budget
checks even when an archive has a copy. Never prefer an archived member to hide
a changed or active existing source. Revalidate absence and archive identities
before returning; if the path appears, restart finite selection with normal live
guards or refuse. Do not wait on or read an unrelated active journal.

Map an explicit bundle to its one trusted publication journal; do not eagerly
inspect target/shared execution journals to discover it. For explicit live
sources use only the deterministic candidate journals needed to prove unique
allocation ownership, refusing ambiguity. Absent optional shared diagnostic
storage remains optional; denied/corrupt storage actually needed by the selection
does not. Discovery performs no rotation, allocation, checkpoint write or active
mutable read. Before export, release destination read leases and reacquire its
independent writer through the existing publication route; repeat identities and
selection digest checks to close that transition. Direct `bundle-read` controls
alone do not pass P05.

### Severity, compatibility and restart decisions

Typed diagnostics carry `class`, `severity`, `consumer_id`, `revision_sha256`,
`document`, `line`, `expected`, `actual`, `recovery`. Use finite redacted values.
Precedence is authority/integrity/identity or protected-claim refusal, then
required-closure absence/new broken required reference, then declared historical
availability debt, then optional presentation advisory/normalization. Apply all
relevant errors; a harmless anchor cannot suppress a wrong target or changed
claim. Missing/changed/unauthorized role declarations never downgrade a required
reference. Debt keys hash owner/reference/claim revision and reason; changing
claim or destination invalidates the advisory. Examples and operational paths
are excluded only by their owning declaration; legacy evidence code spans still
use the evidence reader's role. Shared parsing does not broaden protected queue
normalization beyond proven simple inline destinations or permit label changes.

Offline `--check` validates syntax/schema/queue/brief structure without old
output, models, VM or Git. Selected semantic preflight verifies required closure
early; publication revalidates at mutation. Repository-wide historical inventory
is explicit read-only work. A revision-stable unavailable informational reference
is nonpassing debt, not a repeated unrelated repair or acceptance obligation.

Deploy readers before writers. Keep strict v1 ZIP/receipt/index/ledger/helper
and checkpoint reading and existing missing-reference payloads. V1 exact
original-path verification remains valid for its original claim; it cannot invent
missing task/attempt/input identity. E11–E13 migrate only provable context or
record unavailable history through existing authorization. V1 consumers continue
receiving v1 publications until explicitly migrated; a v2-required selection
refuses on an older helper instead of silently downgrading. Never rewrite old
archives/checkpoints in place or adopt unknown owners. New checkpoint fields
are versioned controller-owned capture/dependency references; legacy checkpoints
retain exact original inputs, targets, attempts and counters. Startup validates
and migrates only under inactive owner with identity-bound durable intent,
original checkpoint retained and exact retry after interruption. Missing fields
cannot imply acknowledged capture. Pending Git transactions cannot renew proof.

Freeze the eight existing fingerprint sources plus the E01 additions:
`test_retention.py`, `test_storage.py`, `test_input_transfer.py`,
`launcher_git.py`, `onpc-test-artifacts`, `launcher_question.py`,
`plan_reconciliation.py`, `vm_selection.py`, `tests/integration/vm_config.py`.
Also register `dev_checkout.py` and `install_test_runner.py` for helper trust and
rendered dispatch compatibility. Fingerprint checkout-relative actual source
bytes, not mtime/import name. A helper protocol query (planned `bundle-protocol`)
returns exactly `schema:1`, `bundle_versions`, `reference_versions`,
`capture_versions`, `custody_versions`, `installed_sha256`, binding the SHA-256
of its **installed rendered bytes**; compare to deterministic
`install_test_runner.render_helper` output for the invoking validated checkout
through a pure rendering call, without executing installation. The artifact
template embeds the resolver but has no VM UUID substitution. Pin the installed
root-owned regular singly linked executable without symlink traversal, and
verify descriptor/path identity and byte digest before/after capability querying
and again before mutation; a self-reported digest alone is insufficient.
Refuse stale/mismatched helper capabilities
before mutation; refresh only through authorized setup. Hash source and rendered
identity separately, since an unchanged checkout cannot prove installed helper
bytes. Register a changed retained-decision module in its introducing row.

Selected target configuration is captured as exact input identity (canonical
entry/UUID and relevant fields), distinct from the source fingerprint of its
parser. A changed unrelated target entry alone does not invalidate an unchanged
selected proof. A change to parser/helper/controller source stops a running
controller at the existing safe boundary and revalidates applicability after
restart; it never spends another session under old imports. Historical proof's
recorded executable/input context stays immutable: a new validation-code
fingerprint does not require equality with that old execution context or force
a check rerun. Reassess applicability against the owning acceptance contract;
changed actual acceptance inputs invalidate only their dependent proof.
Keep `test_activity`
conditional until ordinary controller decisions depend on it; E03 registers it
when the handoff does. Rendering-only modules remain excluded, but provenance
transport/supervisor code becomes guarded if it supplies retained decisions.
Specialized repair/E2E controllers use equivalent source/capability snapshots at
their own supported boundary, retaining selectors, formal failed attempts,
diagnostic limits, promotion rules, counters and Git ownership; no new retry
allowance. No filesystem/import watcher or broad product-source fingerprint.

### Transition review and delivery allocation

The source walk above and E01's existing regression anchors imply this finite
review matrix; planned P histories remain unexecuted:

| Case | Expected transition / preserved assertion | Delivery and histories |
| --- | --- | --- |
| Normal complete/failed/interrupted check | Seal authoritative final closure, or an explicitly partial closed diagnostic subset with failed/pending cleanup; publish independently and acknowledge exact bytes without promoting verdict or original attempt. | E02/E03, E06/E06a; P01/P03/P06 |
| Denied, foreign/active, unsafe or corrupt source/destination | Typed refusal, no renewal/ack/deletion or authentication retry; previous proof and exact transaction survive. | E03/E04/E05a; P02/P03/P05 |
| Missing original, two archived members, unrelated active target | Actual authenticated selection resolves both exact members without inspecting active journal; absent archive member alone uses scoped renewal. | E05a/E07/E14; P05/P08 |
| Capacity before seal, copy, commit or compaction | Preserve required original/old generation, exact reserved attempt and inputs; no partial queue adoption or silent extra segment/slot. | E03/E04/E07; P02/P08/P12 |
| Cancellation and crash at every durable state | Retry same intent/request/receipt/locator CAS; no source release before exact verified ack, no old retirement before locator. | E03/E04/E07; P03/P08/P12 |
| Fourth-run ordinary and oversized startup retirement | Real removal only after matching durable replacement; failed/stale/unacknowledged capture holds source. Disposable oversized output still retires. | E04/E06/E14; P01/P02 |
| Reuse, concurrent readers and same basename | One verified export/slot reused; distinct provenance retained, changed receipt refuses; no verification trust beyond pinned scope. | E05; P04/P12 |
| Continuation/suspension/capacity fallback/Git retry | Exact inputs, response/commands/cleanup, counters, protected claims and original selectors survive. No diagnostic promotion. | E07/E07a; P07/P08 |
| Wrong existing destination, changed claim or role | Identity/claim refusal outranks optional anchor advice; unchanged nonrequired historical loss is explicit nonpassing debt. | E02/E08–E13; P09/P10 |
| Actual dependency/helper byte change | Real fingerprint reader reaches worker; stop before next task, corrective session or blocked-answer continuation; unchanged bytes do not restart. | Each introducing row, E07/E14; P11 |

Proposed independently deliverable allocations for E01b to review are E03's
session/sealed-request authentication and working-capture/ack recovery; E04's
catalogue/reservation gates, bounded segmentation/compaction and finite
host/privileged retirement integrations; E07's ordinary adapter/recovery/Git
composition; and E14's startup-rotation, active-target and real-dependency-change
families. E06/E06a already separate runner and qualification/diagnostic producers;
E07/E07a separate ordinary and specialized consumers. Keep indivisible
reservation/ack/release and publication/index/retirement transitions together;
independent safety regressions belong with each delivery, not postponed to E14.
E01b must freeze explicit prerequisite IDs, backward dependencies, valid briefs,
retained assertions, estimates and exact insertion blocks before any runtime
consumer starts. This proposal changes no future row, scope, Requires or status.

### E01a review record

Three bounded GPT-6.1 Sol High source audits and correction reviews covered
producer/capture, retirement/lock/capacity and reference/helper/compatibility
boundaries. Findings resolved: late finalization and partial cleanup, trusted
sealed-slot lookup and provenance mapping, canonical catalogue with privileged
safety witnesses, provisional versus durable reservations, whole-set retirement
and nonnested recovery, acyclic ledger hashes, document/evidence reference types,
finite metadata bounds, historical versus current source context and pinned
installed-helper identity. All three correction reviews passed. The transition
matrix above records the normal/refusal/missing/capacity/cancellation/crash walk.
This is source/design review only; P01–P12 remain unimplemented and unexecuted.
E01b's independent freeze and concrete prerequisite allocation remain required.
Helpers completed without writes or resources; no live journal was mutated.

## E01b delivery freeze

Freeze baseline: 2026-10-21. This freezes the proposed versioned protocols and
delivery allocation above; it implements no runtime behavior. E01's fifteen
history rows, every producer/consumer row, every retirement row, the explicit
controller inventory and P01–P12 remain required. Existing fixes and named
regressions are reused; planned histories are still unimplemented/unregistered
until their delivery registers actual selectors. Current owning runtime contracts
continue to govern execution until each delivery is accepted.

### Frozen delivery allocation

The following resolves **all** reviewed estimates, including the design gates
and independent final review. Queue Estimate cells of future rows remain protected
and retain their earlier planning text; this table and the affected briefs are
the authoritative reviewed allocation. No provisional delivery choice remains.
No session allowance, acceptance scope or completion is changed by an estimate.
Ranges include reading, implementation, safety coverage, review where required,
validation and owned cleanup. Independently deliverable mechanisms and producer/
consumer families use the exact insertion blocks in their consumer briefs.

| Existing row | Reviewed delivery range | Allocation and retained acceptance |
| --- | --- | --- |
| E01 | 45–60 min audit allocation, completed | Fifteen histories and finite maps retained; no new execution claim. |
| E01a | 60–90 min protocol/review allocation, completed | Schemas, helper trust and full recovery proposal retained; E01b closes only its own gate. |
| E01b | 90–120 min | Independent xHigh source/design review, concrete schemas, all allocations/briefs and guard/metadata validation; no runtime delivery. |
| E02 | 60–90 min | Strict v1/v2 reader/selector/helper capability compatibility and real-file guards form one versioned admission boundary; reader-before-writer and wrong-context refusal cannot be split into a permissive partial reader. |
| E03 | 165–225 min total | E03p-auth 45–60; E03p-capture 90–120; E03 composition 30–45. Initial working writer, all-route fail-closed bridge and full publish/reserve/ack/release recovery stay together; none may expose required proof to old rotation. |
| E04 | 210–285 min total | E04p-custody 60–75; E04p-collections 45–60; E04p-retirement 60–90; E04 composition 45–60. Whole-set retirement and recovery remain indivisible across alternate entry points. |
| E05 | 45–60 min | One export key/publication/read-scope concurrency protocol, P04 and bounds; no separate cache trust mechanism. |
| E05a | 30–45 min | Authenticated selective archived load with real locks and all P05 controls. |
| E06 | 60–90 min | Shared aggregate/category/worker/standalone report lifecycle, late writes and startup rotation P01 are one producer contract; splitting shared report finalization would create premature seals. E06a separately owns qualification/collector families. |
| E06a | 150–210 min total | E06ap-qualification 30–45; E06ap-diagnostics 45–60; E06ap-collector 45–60; E06a composition 30–45. |
| E07 | 135–180 min total | E07p-lifecycle 45–60; E07p-recovery 60–75; E07 all-adapter/active-target composition 30–45. |
| E07a | 120–165 min total | E07ap-repair 45–60; E07ap-e2e 45–60; E07a cross-family compatibility 30–45. |
| E08 | 45–60 min | Shared bounded parser plus protected-comparison controls, P09. |
| E09 | 60–75 min | Shared generator/context verification and finite document-consumer adoption use one preview/apply identity boundary; wrong-but-existing and changed-claim controls remain together. |
| E10 | 45–60 min | Typed severity and lifecycle precedence with exact claim-revision tests, P09. |
| E11 | 30–45 min | Read-only finite tracked catalogue and retained real inventory, P10. |
| E12 | 45–60 min | One guarded preview/apply/retry transaction, exact recoverable destinations and pending protected dispositions, P10. |
| E13 | 30–45 min | Explicit unavailable history, retained authorization and no new pass, P10. |
| E14 | 165–225 min total | E14p-rotation 45–60; E14p-active 30–45; E14p-restart 45–60; E14 remaining composition/resource/consumer review 45–60. |
| E14a | 60–90 min | Independent xHigh final source/evidence review of the whole frozen matrix plus bounded correction review; cross-boundary completeness is one final decision, not separate partial approvals. |

E03p-auth owns the root safety witness and sealed authority registration.
E03p-capture owns the **minimal canonical catalogue, provisional/durable
reservations and authenticated custody CAS required by the complete capture/ack
transaction**, plus the initial single-segment v2 working publication writer and
working index after E02's readers. E04p-collections extends that writer to bounded
segmentation/compaction and adds accepted ledger/locator writers; no working
capture depends on a future E04 writer. E03p-capture also owns the **all-route
fail-closed bridge before activation**, not just E03's later composition.
It cannot defer these to E04. Until a retirement integration is
delivered, an ever-required source fails closed at every eligibility route;
introducing capture must not expose unguarded required data to old rotation.
E04p-custody extends that same catalogue with consumer lifetime and whole-set
retirement, rather than introducing a competing store. E04p-retirement applies
it to the complete finite route list. E03p-capture's acceptance exercises the full
bridge before activation, including direct count deletion and both startup calls;
E03 then composes those results.

All original table dispositions remain binding; these refinements name exact
mechanism/family owners rather than remove the original consumer's obligations:

| Frozen inventory/history | Exact delivery and regression owner |
| --- | --- |
| Logical identities, v2 wire readers, helper negotiation and existing missing source closure | E02/P09/P11; preserve every E01 history anchor and v1 strict behavior. |
| Authentication, immutable finalized subset and failed sealing | E03p-auth/P03; full initial working writer/index/reservation/ack/CAS/crash path and all-route fail-closed bridge E03p-capture/P03/P12; suspension/restart and bridge composition E03. |
| Every retirement map row, including explicit discard, input transfer, legacy and media overwrite | E04p-custody generic protocol/P02; E04p-retirement actual finite callers/P02; E04 cross-route stale/failed-ack and disposable controls. Required-media seal disposition also E06ap-collector/E09. |
| Physical/metadata capacity, bounded segmentation and old+new replacement | E04p-collections/P12; capture peak/sealed charges E03p-capture; idempotent exports/read scopes E05/P04. |
| Actual archived helper selection under unrelated same-target producer | E05a/P05, E07 consumer composition, E14p-active/P05/P08. Two absent paths and no unrelated inspection are mandatory at all three owners. |
| Aggregate/category/worker/standalone report producers | E06/P01; late failure/session cleanup and actual path removal after startup rotation, invocation count one. |
| Standalone qualification and system result/JUnit/TAP/input/command closure | E06ap-qualification/P06; E06a all-family composition. |
| All twelve direct vm_probe diagnostic producers plus shared wrapper callers and baseline_guest | E06ap-diagnostics/P06, exact E01 list and partial/native-log/cleanup limits; E06a composition. |
| E2E collector candidate plus outer post-close authoritative closure | E06ap-collector/P06; E06a producer composition and E07ap-e2e consumer/P07. |
| Reconnect/workflow ordinary capture/carry and all seven derived adapters | E07p-lifecycle/P08; E07 adapter disposition. No adapter-specific duplicate evidence engine. |
| Scoped renewal, protected history, capacity partial queue edits and accepted Git retry | E07p-recovery/P08/P11; E07 composition; historical migration E12/E13 under exact prior authority. |
| Repair snapshots, original selectors and specialized policies | E07ap-repair/P07/P08/P11; E07a cross-family check. |
| Specialized E2E failures, diagnosis/promotion and acceptance recovery | E07ap-e2e/P07/P08/P11; E07a cross-family check. |
| checks evidence, queue cells, briefs/master/handoffs, catalogue/design/specification/report prose | E08 parsing/P09, E09 exact generation and each finite consumer/P09, E10 relevance/severity/P09, E11 inventory → E12 migration → E13 unavailable/P10. Queue normalization remains narrow. |
| Required instruction links, code/examples/operational paths and optional presentation | E08 parser/P09; E09 typed declaration validation; E10 strict precedence/P09; E11–E13 revision-bound nonpassing history/P10. |
| Actual-file source inventory and installed helper identity | E02 baseline closure/P11; every introducing task registers actual decision modules and repeats P11; E07 composition; E14p-restart full matrix/P11. Source-map mocks give no composed credit. |
| Three required regression histories and remaining composed matrix | E14p-rotation/P01/P02/P12; E14p-active/P05/P08; E14p-restart/P11; E14 other finite cases, resource and all-consumer dispositions; E14a independent final review. |
| Scratch/runtime, credentials, VM/product operations and separate media policy | Preserve existing owner exceptions; no capture of scratch/credentials, no live VM/product task or acceptance credit. E04/E06a/E09/E11 retain these explicit compatibility exclusions. |

### Frozen compatibility and recovery matrix

The capture transition table and lock order above are frozen unchanged except
for the concrete wire shapes and E03 custody allocation. No catalogue lock may
perform payload I/O or acquire another owner, writer or helper. Prepared writer
intent precedes nonnested CAS; durable destination reservation precedes release
of its verification scope; revalidation precedes source removal. Lost reply
reuses the same transaction. Failed ack/capacity/cancellation preserves original
requirements and prior proof. The existing finished-owner and identity checks
are never replaced by a catalogue snapshot or caller JSON.

| Boundary | Frozen compatibility/recovery decision | First owner |
| --- | --- | --- |
| v1 archive/receipt/accepted locator/ledger | Strict legacy read and unchanged legacy output for unmigrated consumers; no in-place rewrite or inferred identity. | E02 reader, E03p-capture initial working writer, E04p-collections accepted/segmented writers, E07 consumers |
| v2 record/member/closure and v1 structured fragment | Reader and exact context verification before writer; unsupported versions/fields, duplicate map entries or wrong context refuse. | E02; E03 capture, E09 generation |
| Helper installed rendered bytes and capability response | Pin authenticated installed descriptor and deterministic render identity; stale/older capability refuses before mutation. Existing setup only; no self-reported trust. | E02; each helper-changing task/P11 |
| Active parent / sealed finished subowner | Only owner-issued registered sealed allowlist is readable; arbitrary active source remains refused. Incomplete seal retries exact slot. | E03p-auth/E03p-capture |
| Publish / index / custody / ack | Independent publication; verify payload then index before retirement; source release only after durable exact custody and source-owner ack. Recover same transaction, not a new attempt. | E03p-capture; E04 full lifetime |
| Legacy checkpoint / new versioned references | Inactive controller owns durable migration, exact original retained, targets/inputs/counters/suspension/Git preserved. Missing fields do not imply ack. | E07p-lifecycle/E07p-recovery; E07a specialized equivalents |
| Missing proof / denial / corruption / busy active owner | Only exact renewable absence enters existing renewal. Mandatory absent bundle, access/identity/integrity or active-source refusal never becomes expiry. | E02/E05a/E07p-recovery |
| Controller source change / immutable old execution context | Actual changed validation bytes stop next retained decision at supported boundary. Reassess only affected proof applicability; do not force old proof's execution digest to equal new validator code. | Each introducing row/P11; E07/E14p-restart |
| Protected claims / optional or unavailable history | Claims and retained authorization stay strict; declared revision-bound historical debt is nonpassing, optional presentation advisory cannot suppress required proof/instruction errors. | E09/E10/E12/E13 |

### Frozen insertion guard review

Only the selected future consumer performs its frozen insertion, after creating/
verifying the linked finite briefs and before implementation. E01b creates the
briefs and blocks but changes no future queue row. Each consumer block gives
stable IDs, complete ordered rows, backward Requires, host acceptance with no
Targets, exact before/after consumer Requires, range and retained assertions.
Follow [execution/delegation](../Execution-Plans.md#execution-and-delegation):
finish owned cleanup, preserve the unfinished consumer and its exact inputs,
advance the sole pointer to the first inserted prerequisite and return supported
`prerequisite_required` or valid `continue`. Do not edit/adopt checkpoints or run
the inserted task in that session. Broader replanning still needs explicit
reviewed reconciliation, not this freeze.

Source review of `tools/execution_plan.py::Plan.prerequisite_repair()` confirms
each block preserves original direct dependencies, consists only of contiguous
new unchecked ancestor rows before the selected unfinished consumer, and leaves
all existing completion/order/Scope and future fields unchanged. The last new
dependency transitively includes every inserted row. New briefs retain exact
Acceptance/Targets metadata. `plan_launcher.validate_result` additionally requires
owned cleanup and rejects suspension during unresolved Git reconciliation.
Retained executable guards in `tests/unit/test_execution_plan_launcher.py` are
`test_prerequisite_repair_recognizes_exact_multilevel_block_without_accepting_consumer`,
`test_prerequisite_repair_refuses_unsafe_queue_mutations`,
`test_prerequisite_insertion_cannot_drop_existing_consumer_dependency`,
`test_prerequisite_repair_refuses_accepted_or_unverifiable_checkpoint`,
`test_automatic_prerequisite_reconciliation_requires_completed_cleanup`, and
`test_prerequisite_suspension_resumes_original_consumer_across_task_limited_runs`.
`test_export_frozen_blocks_use_real_prerequisite_and_cleanup_guards` additionally
applies each actual frozen block and linked brief to a private copy of the plan,
checks queue-relative destinations and matching dependency/acceptance metadata,
and proves both supported handoffs reject incomplete cleanup without accepting
the consumer. It skips activated or accepted consumers whose temporary briefs
are legitimately retired; normal retained-state regressions then own that state.
The future-row mutation and missing/invalid-brief controls are real existing
tests; these are not P-history implementations or acceptance for inserted tasks.

### E01b independent review record

GPT-6.1 Sol xHigh reviewed the audit maps, complete relevant source boundaries,
protocols and frozen allocations in a self-contained `fork_turns="none"` review.
Correction review approved the final candidate with no remaining actionable
findings. Resolved findings: canonical JSON member mapping and strict nested wire
shapes; E03's minimal catalogue/reservation/witness dependency; initial working
writer and all-route fail-closed bridge before capture activation; and queue-relative
literal insertion destinations with separate brief-relative navigation. All six
blocks, fifteen finite briefs and every estimate, including E01b/E14a, were
independently checked. Existing history, authority, exact cleanup, P01–P12 and
consumer obligations remain binding. The review grants no runtime acceptance.

Validation on 2026-10-21: `tools/run-tests unit` with exactly
`tests/unit/test_execution_plan_launcher.py`, `tests/unit/test_e2e_plan.py`,
`tests/unit/test_e2e_inventory.py`, `tests/unit/test_coverage_generation.py`,
`tests/unit/test_e2e_case_composition.py`, `tests/unit/test_regression_unit.py`
and `--timeout 180s`: **759 passed** in four maintained buckets
([retained report](../../output/test-runs/host/reports/20261022T035225Z-30f98d1c/report.md)).
This includes all twelve actual frozen-block/status combinations and existing
dropped-dependency, future-row, invalid-brief, cleanup and suspension guards.
Plan `--check` passed and changed links had no missing destinations. The new
metadata check reads bounded checkout Markdown and writes only private fixture
text; reviewed compatible unit classification remains, with no cleanup/UI
inventory resource. These checks are not implementations of planned P histories.
After close-out, the exact same frozen-block selector with `-k
'export_frozen_blocks_use_real_prerequisite_and_cleanup_guards'` and
`--timeout 180s` passed all **12** cases again against the final queue/pointer
([report](../../output/test-runs/host/reports/20261022T035426Z-61e9715f/report.md)).
Final plan `--check` selected E02 with 17 unfinished runtime/review rows; final
master/queue/design link checks and `git diff --check` passed.

Both helpers finished and owned no external resources. The maintained test run
finished successfully; no owned process, VM, live journal mutation, export or
temporary allocation needs manual cleanup. Only documentation, a private metadata
regression and its resource-review comment changed. `Makefile` package source
allowlist excludes these inputs, so no build is required. The controller retains
commands, result and cleanup through normal accepted publication; no agent Git
close-out, installation or other queue execution occurred.

## Scope and quality boundary

Change test tools, support, launchers, metadata and their documentation only.
Product behavior, product diagnostic downloads/uploads, product installation,
customer scenarios, UI-provider qualification, test verdicts, case inventories
and acceptance obligations remain with their existing owners. This plan runs
no product or VM acceptance. All implementation checks use host-private fixtures,
including helper/privileged/target protocol simulations. Do not weaken a test
assertion to make reference maintenance easier.

Keep public artifact reading/copying in the existing maintained reader. The
`tools/export` wrapper executes this plan; it must never become a competing copy,
archive or privileged shell route. Reuse shared storage, retention and bundle
publication. Add capabilities to existing scoped helpers only when needed, with
normal argument validation, installation regressions and setup routing.

## Stable and specific references

Use a versioned logical evidence identity that survives relocation and generation
rotation. Bind owner/repository/plan or run, task or case/check selector, attempt,
declared target, exact source/input identities, result status, original member
and digest, and command/cleanup dependencies. Retries and changed inputs receive
distinct identities; identical bytes from different checks are not equivalent
claims. A resolver must prove the requested record matches the requested context.

Extend the existing verified manifest/receipt/accepted locator rather than
introducing a second ZIP format. Generate document links selecting an exact
record, not merely the latest run or a generic `accepted-evidence.json` file.
Freeze the readable link/selector syntax through E01a/E01b and deliver it in E02/E09.
Preserve original member provenance and allow safe checkout-relative resolution;
do not treat an old absolute checkout path as current authority.

Capture callers supply structured records; free-form prose scraping is a legacy
reader only. Enumerate document consumers explicitly, including queue cells,
briefs, catalogue/design prose, report links and handoffs. Generated references
must distinguish live evidence, accepted historical evidence, superseded attempts,
unavailable historical proof and malformed/unsafe references. A stable locator
without a verified matching member remains insufficient proof.

## Capture and publication

Capture finalized check records before their execution journal can rotate, rather
than waiting for final task completion. The producer supplies an explicit finite
selection of result records, selection/input manifests, command logs, applicable
JUnit/TAP and owned-cleanup records. Preserve failed and interrupted attempts
under their own identities. Partial records remain partial and cannot become
passing acceptance. Bulk media stays separately referenced with an explicit
lifetime; do not silently omit media required by the original check.

The existing bundle route requires finished owners and independent publication.
Do not remove those guards to enable early capture. Introduce an owner-authorized
handoff of finalized immutable records into a bounded working collection. Define
the active-run authentication, locks, read-only finalized subset and acknowledgement
that makes it safe to release the source. Reject arbitrary reads from another
active run and any source mutation during transfer. Cancellation or a failed
acknowledgement must preserve the last valid source/publication and a resumable
record. Long task continuation, suspended prerequisites and later Git close-out
must not release unpublished required evidence.

Before retiring a source, confirm required captured dependencies are durable.
Publish the verified accepted manifest/locator before retiring superseded owned
generations. Recover crashes at capture, commit, locator replacement and retirement
through recorded identities. Keep the controller's protected queue/checkpoint
transaction separate from document rewriting; agents never edit checkpoints.
Every new or changed shared dependency follows the
[controller compatibility guard](#controller-compatibility-guard) in the task
that introduces it, before that task can close or the next task is admitted.

## Lifetime, capacity and reuse

Separate disposable output, working required proof and accepted referenced proof.
Ordinary last-three-run rotation must not delete the only copy required by a
working task or accepted reference. Prefer verified copying/carry-forward over
indefinitely pinning original execution allocations. Maintain an authoritative
reference/dependency catalogue; arbitrary document text must not create deletion
authority or allow unlimited retention. Unfinished and suspended consumers hold
their exact required collection until release through their owner.

E01 inventories every retirement entry point and its callers: ordinary
`Store.session()`/`prune()`, startup `Store.reconcile()` with `completed_guard`
through host and privileged recovery, publication commit/finish/recovery and
explicit discard. E04 applies required-dependency and durable-acknowledgement
checks at each applicable boundary. Failed capture, pending acknowledgement or
insufficient capacity cannot make an otherwise required source disposable.
Retain automatic oversized retirement for unreferenced disposable evidence;
unknown/replaced resources and absent discard authority remain refused.

Preserve existing finite byte, file, depth, selection and manifest limits unless
a separately reviewed requirement changes them. Account simultaneous old,
staging and new payloads, receipts and failed recovery allocations before starting
work. Deduplicate identical payload storage without merging differing provenance.
Plan bounded collection segments/compaction when one cumulative archive approaches
its limit; segmentation is not permission to multiply owner budgets. If required
proof cannot fit, report exact projected usage and a supported archive/release
action before destructive rotation or an expensive retry. Preserve current proof.
Required accepted proof has no automatic expiry merely because unrelated tests
ran; retirement requires released dependencies or verified replacement through
the owning contract. Explicit discard authority remains unchanged.
Historical references declared informational rather than required by any active
consumer may transition to explicit unavailable status under that owner. They
must not pin bulk output forever, silently vanish, or continue advertising
materialized proof. Capture remains finite; reaching a genuine required working
set limit is a capacity error, not permission to weaken a test.

Repeated export of the same verified source/selection should return a reusable
private export/receipt without creating a retention slot. Revalidate identity,
content and authority before reuse. A missing or replaced export must not be
returned as success. Distinct same-basename files retain distinct provenance.
Use grouped atomic publication for related files, shared reader locks and one
verification per bounded pinned read scope. A later changed archive invalidates
that scope; deduplication must not introduce unsafe hardlinks or shared writable
payloads. Keep source files unchanged and caller/root ownership boundaries intact.

Resolve explicitly selected, finished retained copies without unnecessarily
locking every unrelated execution journal. The existing selection catalogue can
eagerly inspect selected-target journals; E01a/E01b must freeze selective ownership and
lock ordering that allows an old archived member to resolve while a new producer
on that same target is active. This is an exact archived-member read, not an
exception allowing reads from active mutable sources. Ownership, conflict and
live-path revalidation still apply wherever the request actually depends on them.

Storage stays local/private under the shared allocator. Surviving a host loss or
materializing evidence in another checkout requires an explicitly configured
archive/import route; a Git link is no backup. External hosting, uploads and new
cloud dependencies are outside this plan. A missing local archive must be
reported as unavailable, never mistaken for successful verification.

## Proportional validation

Use one structured classification across readers, document checks and launchers:

| Condition | Required behavior |
| --- | --- |
| Wrong task/check/attempt/target/input, corrupt digest, unsafe ownership/path, untrusted publication or a conflicting record | Block the affected operation; preserve evidence and give a finite actionable diagnostic |
| Proof required by the current task or a declared active dependency is missing | Block acceptance; resolve an exact verified archive member or return the existing scoped renewal handoff; never invent a pass |
| A newly authored evidence or required instruction reference is broken, ambiguous or points to the wrong existing report | Block that reference's publication with document/line/identity details; unrelated suites do not rerun |
| A protected queue/checkpoint claim changes beyond authorized bookkeeping | Preserve the original transaction and follow the existing reconciliation/recovery contract |
| Equivalent relative spelling, harmless sentence punctuation, presentation-only formatting outside protected cells with an unchanged declared claim, or changed physical location with identical verified identity | Normalize or warn; preserve protected labels and claim bytes and do not reject otherwise valid infrastructure results |
| Unchanged historical proof is unavailable and no current acceptance/dependency relies on it | Record explicit nonpassing availability debt once and show an advisory; do not repeatedly block unrelated work or spend repair sessions |
| Optional presentation link/anchor is broken without affecting a required instruction or evidence identity | Give a scoped advisory; required reading/command and evidence references remain blocking |
| Access denied, integrity failure or active/foreign owner | Report the distinct refusal; never relabel it as expiry or retry authentication after denial |

The user explicitly authorized relaxing trivial validation while retaining test
quality. Implement this as typed severity and dependency relevance, not blanket
ignore lists, reduced assertions, fabricated receipts or suppression of errors.
Bind historical debt to the exact reference/claim revision; a changed or newly
introduced bad reference cannot inherit an exception. A historical unavailable
status is never a check pass, task completion or permission to use that proof.
Required/optional classification comes from the owning contract and structured
consumer declaration, not inferred from prose or chosen to bypass a failure.
Integrity, authority, identity and protected-claim failures take precedence over
presentation advisories. A new optional presentation anchor can be advisory
under its declared role; a required instruction or evidence reference cannot.
An absent, conflicting or changed consumer-role declaration cannot downgrade a
required reference to presentation or historical debt. Validate that declaration
against its owning contract before applying an advisory; changing the role or
claim invalidates any retained advisory classification for that reference.
Changing a label from `Ubuntu passed` to `Both targets passed` changes the claim,
even when its destination is unchanged. It never receives format-only treatment;
protected queue labels remain literal under existing transition guards.

Separate offline syntax/structure validation from evidence materialization.
Plan `--check` remains model-free, VM-free and Git-free; it must be usable on a
clean checkout without old local output. Semantic preflight validates only the
selected operation's required closure. Repository-wide audit is explicit and
read-only; unchanged unrelated history is reported without blocking unrelated
task execution. Inspect required identities early and validate publication again
at the mutation boundary. Avoid repeated full-archive scans and repair loops
when no relevant input changed. Diagnostics identify class, consumer/line,
expected versus actual identity, scope and one supported recovery route without
echoing secrets or dumping raw transcripts.

## Compatibility and migration

Retain old helper commands and versioned manifests/checkpoints until every
inventoried consumer has a verified route. Older running controllers keep their
code: use normal session-boundary restart and exact resumption. Preserve preexisting
dirty/staged work, accepted results, targets, session counts, queue order and
scope. Do not run competing launchers or rewrite protected evidence cells outside
the existing controller-owned recovery contract.

### Controller compatibility guard

E03p-auth registers `tools/evidence_capture.py` in the explicit retained-decision
closure, alongside the previously registered retention, storage, bundle and
authenticated-helper sources. The existing actual-file-byte worker histories
cover the added module with the original eight sources unchanged, including
continuation, rejected-result recovery and answered blockers. `test_activity.py`
remains unchanged advisory coordination and is not imported by the capture
authority or ordinary controller; its prior conditional exclusion still applies.

Extend `plan_launcher.response_validator_sources()` and its existing content-change
regressions as shared dependencies are changed or introduced. E01 inventories
the controller's relevant validation/storage dependency closure, including
`test_retention.py`, `test_storage.py` and any extracted identity, reference,
capture or severity module. Follow the current callers into `test_input_transfer.py`
mutation guards, `test_activity.py` ownership and `launcher_git.py` close-out;
record which files affect the controller's retained decisions and why any audited
file is excluded. Include the authenticated helper dispatch where its source
changes affect those decisions. Use an explicit reviewed source inventory; no new
watcher, archive state machine or unbounded filesystem/import scan is needed.
Each introducing task registers its relevant dependencies and runs the guard's
private regressions before completion; E07 is the integration check, not the
first opportunity to add restart protection.

Change actual dependency-file bytes in fixtures, including an extracted module
while the original eight guarded files remain unchanged. Assert session-boundary
stop before another task, corrective session or blocked-answer continuation,
with exact response, inputs, counters and ownership retained for a fresh controller.
Connect the real fingerprint reader to the worker in these histories: a separate
hasher test plus worker tests using mocked source dictionaries cannot establish
the restart guarantee. Snapshot the registered inventory before mutation; verify
unchanged bytes cause no restart and every newly registered dependency is covered.
Preserve normal restart allowances under the existing launcher contract; capture
or retry operations grant no additional allowance. Older specialized controllers
retain their own lifecycle policy and use its supported
safe-boundary restart; this does not add model retries or change their budgets.

### Legacy reference migration

Inventory tracked references and explicitly registered local catalogues, not an
unbounded filesystem scan. Classify each as exact live proof, exact archived
proof, wrong/ambiguous destination, historical unavailable, example or operational
path. Preview finite migrations with exact original bytes and expected proof
digests; apply only an unchanged verified selection. Destination-only repairs
retain claims. Genuine historical proof-loss disclosure uses the existing exact
authorization/recovery route when it changes protected claims; absent authority
produces a concrete proposal and debt record, not a checkpoint edit or a false
completion. No missing product acceptance is executed by this plan.

## Required regression histories

These histories use private stores and simulated authenticated helper/controller
entry points. They perform no VM operation, actual authentication or model launch.
The ordinary-launcher module's `synthetic_plan_evidence` autouse fixture stubs
capture, carry, preservation, recovery and rewriting. Cross-boundary histories
must use the real evidence functions instead of those stubs and verify the
resulting private records. Retain the lighter isolated fixtures for their own
unit scope; they supply no composed evidence-lifetime acceptance.

1. **A later run rotates an older report.** E06 creates report A, its declared
   consumer/reference and complete result/input/command/cleanup closure. Start
   later runs through startup retention until A's original report path is actually
   retired, including more than three runs. Resolve A's exact check, attempt,
   target, inputs and dependencies through the stable reference with no check rerun
   or changed verdict. Assert the original path is absent, compare the complete
   retained closure's bytes/digests and keep A's invocation counter at one through
   resolution. E04 repeats retirement with failed capture and unacknowledged
   handoff: ordinary pruning and automatic oversized startup recovery must retain
   the required original until verified durable capture permits retirement. Also
   test unreferenced oversized evidence still retiring. E14 composes producer,
   consumer and reference generation across this sequence. A stale acknowledgement
   for a different attempt, source identity or dependency closure must not release
   the original; only the matching verified durable acknowledgement permits it.
2. **Two expired reports during an unrelated active producer.** E05a exercises
   the authenticated helper's `bundle-plan` dispatch through real
   `Selection.catalogue()`/`load()` and retention inspection, with a validated
   synthetic plan, target T, retained bundle B and two explicit old references.
   This is the existing `--plan`, `--target`, `--bundle`, repeated `--reference`
   selection shape; register any changed interface before use. Record the pre-fix
   eager-catalogue refusal or verify its earlier delivered fix/regression, then
   require both exact archived members to resolve while an unrelated producer on T
   holds its journal.
   Do not mock away selection or locking. Assert no unrelated journal inspection,
   mutable-payload reads/adoption, source rotation or checkpoint writes during
   resolution. Direct `inspect()`/`bundle-read` success is a useful control but
   insufficient acceptance: it already avoids the eager target catalogue. Keep
   missing, wrong-attempt/target, corrupt, denied and actual active-source refusals
   distinct. Do not reintroduce an already fixed refusal to manufacture a failing
   baseline. E07/E14 exercise this selection through an ordinary-plan consumer;
   any subsequent publication changes only that consumer's owned transaction.
   Simulate only caller authentication, target registration and privileged identity
   operations at the host boundary. Keep helper dispatch, plan validation, source
   selection, archive verification and retention locks real. Assert both original
   paths are absent and both requested original members and digests match.
3. **Changed dependency in a running controller.** E02 onward runs the
   [compatibility guard](#controller-compatibility-guard) when dependencies change;
   E07/E14 compose real file changes with continuation, blocked answers, suspended
   work and fresh-controller recovery. No extra task/session credit or stale
   validation is permitted.

## Infrastructure acceptance

Each task owns meaningful host regressions. E14 reuses their helpers and results
to add boundary-spanning histories, rather than rebuilding each task's safety
matrix. E14a independently reviews the final source and retained results.
Final composition uses private
producer/controller/helper fixtures to reproduce the historical failure families,
including more than three source sessions, more than three unrelated exports,
multiple targets with identical basenames, separate retries, changed source,
concurrent readers, denied authority, active owner, wrong checkout, capacity
exhaustion and injected interruption at each durable transition. Exercise
continuation, suspension, restart and accepted Git retry without running models,
VMs or product suites. Assert exact retained bytes/provenance, durable recovery,
bounded allocation counts/bytes, unchanged foreign resources and scoped severity.
Include two vanished legacy report paths with two exact retained members while
the same synthetic target has an unrelated active producer. Both references
must resolve without rotating sources, changing a checkpoint or reading/adopting
live mutable payloads. A missing archived member stays unavailable; denied access,
corruption and foreign-active ownership remain distinct refusals. The required
regression histories above select the actual integration paths; isolated bundle
member reads or mocked change dictionaries do not replace them.

The outcome is fewer avoidable errors with preserved test quality: repeated reuse
does not rotate exports; required proof survives unrelated runs; wrong existing
destinations fail; format-only changes do not fail; historical unavailable proof
is explicit and cannot satisfy active acceptance. All frozen consumers receive
a delivered migration or an explicit compatibility disposition. Independent final
review checks those outcomes against the source and original failure inventory.
