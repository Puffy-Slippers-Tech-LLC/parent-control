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
