# Accessibility identity audit execution plan

Execute one numbered task per new session, in the order below. This plan breaks
down the supplied accessibility/UI automation handoff; creating it performs no
implementation or test qualification. The next task is
[06 — Fixture lifecycle](06-fixture-lifecycle.md). Its current
inventory is in [02 — Owned UI and inventory](02-owned-ui-and-inventory.md#current-callable-inventory).

This is a temporary remediation queue for the existing audit. The
[E2E execution plan](../E2E-Execution-Plan.md),
[customer queue](../E2E-Task-Queue.md), and
[building-block contracts](../E2E-Building-Blocks.md) retain ownership of customer
acceptance. Finishing this queue does not mark their scenarios complete.

## Ordered sessions

| Task | Deliverable | Prerequisites | Recommended model / effort | Status |
| --- | --- | --- | --- | --- |
| [01](01-legend-expansion.md) | Correct legend state query and independently observe identified expanded content | Session preflight | GPT-5.6 Sol / high | Complete |
| [02](02-owned-ui-and-inventory.md) | Audit callable identity paths; finish product/preview ID gaps | 01 | GPT-6 Astra / high | Complete; O1–O4 and 02a–02b closed |
| [02a](02a-owned-identity-closure.md) | Finish guest/preview ownership, complete absence and selected-account identities | 02 inventory | GPT-6 Astra / high | Complete; central read regression and final 79-case UI selection passed |
| [02b](02b-spectator-ui.md) | Migrate newly found spectator UI and retain mechanical obligations | 02a | GPT-6 Astra / high | Complete; 303 units and synthetic host UI passed |
| [03](03-authentication-surfaces.md) | GDM, authentication and keyring paths use scoped IDs or refuse safely | 02 complete, including 02a–02b | GPT-6 Astra / high | Complete; A1–A3 contained on exact provider blockers |
| [04](04-desktop-and-external-apps.md) | Desktop, search, terminal and viewer paths use scoped IDs or refuse safely | 02 inventory; 03 shared adapter changes settled | GPT-6 Astra / high | Complete; D1–D6 contained on exact provider blockers |
| [05](05-legacy-input-routes.md) | Close Perl image/pointer and direct Shell routes, including retained callers | 03–04 dispositions recorded | GPT-6 Astra / high | Complete; L1–L10 closed or safely provider-contained |
| [06](06-fixture-lifecycle.md) | Review fixture process ownership, runtime packaging and mechanical compatibility | 02; execute after 05 to keep one session active | GPT-6 Astra / high | Not started |
| [07](07-focused-unit-verification.md) | Complete focused unit selection on final implementation | 01–06 resolved or safely contained | GPT-5.6 Sol / high | Not started |
| [08](08-host-ui-verification.md) | Complete all twelve host UI files on frozen implementation | 07 passed | GPT-5.6 Sol / high | Not started |
| [09](09-child-static-runtime.md) | Child Node, static and applicable isolated fixture-runtime checks | 08 passed | GPT-5.6 Sol / high | Not started |
| [10](10-reconcile-and-close.md) | Reconcile contracts, generate coverage inventory, validate documents and close scope | 07–09 results recorded | GPT-6 Astra / high | Not started |

Sol suits settled implementation and verification. Astra is recommended where
identity, secret recipients, ownership, concurrency or cross-layer correctness
remain unresolved. Reassess at each task boundary under the repository model
policy; a difficult failure in a verification task can justify Astra. These are
recommendations for the next session, not requests to change this session or
launch parallel agents.

An external task may reach **Contained; provider blocked** when every affected
entry point refuses before prohibited discovery/input, its behavioral obligations
remain covered or explicitly pending, and its provider return conditions are
recorded. That disposition permits independent downstream host work; it does
not qualify the provider or count as customer acceptance. An unsafe callable
path, unresolved regression or failing cleanup gate cannot use that disposition.

## Session preflight and common constraints

1. Read [AGENTS.md](../../../AGENTS.md),
   [System-Design.md](../../System-Design.md),
   [Approval-Tools.md](../../Approval-Tools.md), this file, and the selected brief.
   Read only relevant sections of linked implementation contracts afterward.
2. Inspect `git status --short`, `git diff --stat`, `git diff --cached --stat`,
   and the selected files' staged and unstaged diffs. Record the session's index
   checksum with `sha256sum '.git/index'`. Preserve all pre-existing work. Never
   reset, discard, unstage, automatically stage or commit as part of these tasks.
   The current checkout is the starting point, not a historical index checksum.
3. Use native `apply_patch` for edits and direct quoted reads/validated launchers.
   Reuse grants. Missing prerequisites or a denial are blockers, not permission
   to broaden policy or use a fallback. One-time host prerequisites belong only
   in `setup.sh` and its maintained modules; tests/builders must not install them.
4. No VM operations, installed-system tests, broad E2E runs, host product
   installation, baseline preparation, publishing or portal changes. Do not run
   `tools/run-tests` without a category, or use `all`, `host`, `system`, `e2e`,
   broad Make aggregates or integration execution to close this audit.
   Task 10's established coverage generator may perform read-only collection and
   system inventory listing; it must not execute installed cases or touch a VM.
5. Run suites sequentially. Respect the checkout activity lock and launcher
   attach/unread-result behavior. Collect a running invocation's actual final
   status before starting another; never delete locks or infer success from
   collection. Do not claim a historical run is still active without current
   evidence. Keep normal runner artifacts, not new incident reports.
6. All targets, including retained helpers, require stable public `automation-id`
   lookup scoped to their owning application and surface. Reject duplicates,
   missing IDs and wrong owners. Labels, roles, text and states verify meaning
   only after identity lookup. No coordinates, extents, image matches, titles,
   frame roles, tree positions or fixed navigation counts may select targets,
   route input, establish readiness or decide acceptance.
7. Add missing IDs in repository-owned product/fixture code before consumers.
   External provider requirements are not actual provider IDs: use the existing
   [provider gap catalogue](../E2E-Building-Blocks.md#functional-validation),
   preserve blockers and refuse before input. Never invent IDs in client metadata
   or substitute direct Shell/backend operations for customer interaction.
8. Reacquire IDs after semantic reveal, scroll, focus or navigation. Preserve
   reachability, ownership, secret-recipient, single-use secret, uncertain-input,
   timing and behavioral checks. Do not activate hidden controls to hide a
   reachability failure. Preserve child-form/kiosk compatibility.
9. Before host-integrated process cleanup, pass isolated cleanup-safety and lease
   regressions through the approved launcher/gate. Signal only explicitly spawned,
   identity-recorded processes. No name-based process discovery or host scans.
10. Follow [failure handling](../../../tests/README.md#handling-test-failures).
    Preserve evidence and report expected versus actual product behavior. Seek
    developer direction before accepting changed behavior or expectations unless
    already authorized. Mechanical corrections may proceed with evidence that
    the intended assertion survives. Never weaken, skip or delete checks for a
    passing result; identity migration must retain the original behavior checks.

## Starting evidence and limits

Read-only checkout inspection on 2026-09-19 confirmed the legend test still
queries `CHECKED`, the control is `Gtk.ToggleButton`, and its content grid lacks
a public ID. The App Limits search readiness predicate already checks existence
before `SENSITIVE`. The supplied handoff diagnoses `PRESSED` as the correct
toggle state; task 01 verifies that mapping and the independent expansion result.

At plan creation, existing changes were staged and `git diff --stat` was empty.
The observed index SHA256 was
`a3a65336fd537d376a5fd25d0806a62cd73ab86e33b7cf0a96956a041b175a1e`,
different from the supplied historical checkpoint. Preserve the current staged
content; do not recreate the old index. These planning files start as new,
unstaged files. Future sessions must inspect their own actual baseline.

The following are **handoff-reported results**, not new executions:

- The latest two-file host UI run completed with 14 passed and 2 failed, both
  scales of `test_parent_app_controls_and_filters_remain_reachable`. Its cleanup
  gate passed 1,475 tests and 3 subtests. Evidence directories:
  `/var/tmp/onpc-ui-preview-vdkkjwz2` and `/var/tmp/onpc-ui-preview-qcz7ntat`.
- Native, game, isolated user Flatpak and unpacked Snap GUI fixtures passed
  independent-instance, typing, submit/readback, moves and close interactions.
  Logs are under `/var/tmp/pytest-of-edgar/pytest-1180/` in
  `test_payload_gui_preserves_ind0/native.log`, `ind1/game.log`, `ind2/flatpak.log`
  and `ind3/snap.log` (the latter directories share the full
  `test_payload_gui_preserves_` prefix). This does not qualify installed App
  Limits enforcement, snapd installation or Snap confinement.
- The earlier search-readiness failure is preserved at
  `/var/tmp/onpc-ui-preview-lc9c1y5f`. The existence guard progressed past it in
  the narrower run. The original full run's final totals were unrecoverable.
- Focused units, the final twelve-file UI run, child-node, static, optional
  fixture-runtime and coverage regeneration remained outstanding. Previous link,
  JSON and diff checks must be repeated on the final documents/code.

Preserve the UID-based Parent picker and independent focus/readback/Enter commit;
explicit kiosk account identities; shared public ID readers; preview launch
ownership and refusal-before-spawn; coordinate-input refusal; GUI fixture
adapters; native executable identity and owned-child lifecycle; separate
mechanical fixture; offline runtime packaging; and `installed_qualified=false`.

## Session close and next-session instruction

Each task ends with a small update to its row and brief: disposition, exact
verification command/result, existing artifact location, remaining blocker and
next task. Keep only current evidence pointers here; detailed run history stays
in runner artifacts. Record any callable path newly found by task 02 against its
owning task so it cannot disappear from the remaining scope.

Run `git diff --check` and `git diff --cached --check`, validate changed Markdown
with `tools/read-only links`, and inspect status/index preservation. A changed
checksum needs investigation of staged content, not a reset. Finish only the
selected task; do not silently continue into the next numbered session.

To start a session, ask the recommended model at the stated effort:

> Execute task NN from docs/TestAutomation/Audit/README.md and its linked brief
> in /Data/Code/PST/parent-control. Apply the shared preflight and constraints.
> Complete only that task, record evidence and blockers, update its status and
> the next-task pointer, and stop. Preserve every existing staged/unstaged change.

If a task proves too large, split only its remaining work into bounded follow-up
briefs, with explicit model/effort, dependencies and unchanged acceptance scope.
Do not mark the parent task complete until those obligations are resolved.
