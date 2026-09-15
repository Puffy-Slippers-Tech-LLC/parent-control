# Building customer E2E scenarios

Start with the [customer scope](E2E-Coverage.md) and the selected
[reuse-map row](Reuse-Map.md). The installed Parent About/license journey is the
first complete customer example. Reuse its operations and acceptance machinery;
keep each new scenario's actions and visible finish line explicit.

## Existing building blocks

| Need | Implementation | Contract |
| --- | --- | --- |
| Verified installed app | [installed_setup.py](../../tests/e2e/installed_setup.py): `stage`, `InstalledSetup.run` | Bind package/helper/selection bytes before bootstrap; install, reboot and verify once in setup. Failure is terminal. |
| Controller rendezvous | [installed_journey.py](../../tests/e2e/installed_journey.py): `JourneyPlan`, `InstalledJourney` | Ordered requests, durable observation callback, fresh ownership guard, then atomic reply. Boot identity supplies harness continuity only. |
| Recorder composition | [installed_journey.py](../../tests/e2e/installed_journey.py): `record_installed_journey` | Provision fixture credentials, enter declared phases, checkpoint observations and reconcile screenshots. Strict customer execution; existing recorder owns evidence and final acceptance. |
| Fresh matched click | [onpc_pointer.pm](../../tests/integration/graphical_smoke/lib/onpc_pointer.pm): `click(tag, timeout)` | Match all regions perfectly; require an interior click point; map image coordinates to the public framebuffer dimensions. Missing/weak/unsupported input refuses. |
| Worker stage reporting | [onpc_journey.pm](../../tests/integration/graphical_smoke/lib/onpc_journey.pm): `seen`, `observe`, `finish` | Emit the named screen stage and wait for its acknowledgement. Keep automatic captures private and verify shutdown. |
| Interrupted pre-start setup | [system_runner.py](../../tests/integration/system_runner.py): `recover_graphical_cleanup`, through `tools/run-tests integration check_graphical_recovery` | Restore a recorded `isolated` attempt only with a null instance ID, powered-off pinned guest, matching run tag, original disk identities, no host sharing and a full baseline proof under the exclusive lease. Reuse outer cleanup; never start the guest or replace the baseline. |
| Parent entry and navigation | [onpc_parent.pm](../../tests/integration/graphical_smoke/lib/onpc_parent.pm): `login`, `launch_from_app_grid`, `select_existing_child` | Installed GDM recipient qualification, unchanged secret API, real app-grid launch and explicit fixture-child selection. |
| Standard-user Parent access | [parent_access.py](../../tests/e2e/parent_access.py), [onpc_parent_access.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_access.pm) | `login_standard` qualifies the canonical `other-child` GDM recipient, then `open_app_grid` supplies the normal discovery route. Match the full product query, web-only suggestion and empty application results to establish the administrator-only launcher's unavailability. No product backend or other-user-state assertion is collected. |
| Parent account fixtures | [account_fixture.py](../../tests/e2e/account_fixture.py), [e2e_dynamic_account.py](../../tests/integration/e2e_dynamic_account.py) | One fixed action creates a collision-free eligible account while Parent is open; another requires the guarded baseline's finite eligible set, preserves the package request station and makes that set ineligible before Parent launches. Fixture checks are setup evidence; only visible refresh/selection or the empty explanation supplies customer acceptance. |
| Reviewed image preparation | [parent_needles.py](../../tests/e2e/parent_needles.py), via [prepare-e2e-needle](../../tools/prepare-e2e-needle) | Fixed registered nonsecret tags, inspected source pixels, reviewed regions, 16-pixel matcher context, bounded destinations. |

The About-specific compositions are
[parent_about.py](../../tests/e2e/parent_about.py) and
[onpc_parent_about.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_about.pm).
They own the About/license/footer/return expectations. Shared helpers do not
choose a customer's expected result or query internal product state.

## Add a consumer

1. Select one inventory variant and its complete visible result. Identify the
   required fixtures and surfaces. Reuse accepted setup; installation mechanics
   do not become customer assertions. If a shared operation is missing, name the
   blocked action and implement only that operation with this consumer.
2. Compose a worker module from the operations above. For Parent, start with
   `login`, `launch_from_app_grid` and the appropriate visible child selection.
   Add a fixed branch in [smoke.pm](../../tests/integration/graphical_smoke/tests/smoke.pm)
   for the new worker mode. Reuse the existing exchange channel and owned worker;
   do not create another VM runner or invoke private product APIs.
3. Define a `JourneyPlan` in the Python scenario module. `screen_tags` maps
   stage names to expected needles **in execution order**; `ready` and
   `setup-detached` are prepended automatically. `prefix` must match the worker's
   `onpc_journey` prefix. `worker_mode` names the fixed ready-reply branch.
   `phases` maps every stage to a declared recorder step. `advance_after` opens
   the next step before the current reply permits that step's first input.
   The About plan opens `step-2` at `license`, before closing the viewer.
4. Have the callback call `record_installed_journey(recorder, context, PLAN)`
   and register it in `E2E_CASES`. This composition currently supports one
   authenticated installed journey with unchanged customer boot and a terminal
   `visible-result` assertion. New reboot, fixture-change or assertion needs
   require a scoped extension; do not force them into this plan or bypass its
   failure latch. A boot-changing installation belongs to setup, outside it.
5. Reconcile that variant's inventory declaration, requirements, visible
   assertions and evidence. Customer families use `category: customer-journey`.
   The `installed-digest-verified-product` prerequisite selects package-bound
   bootstrap automatically, without a case-ID branch in the executor. Declare
   `fixture-credentials-via-secret-api` when using authenticated input. A ready
   callback must exist, and all required steps must have real implementations.
   Registration enables execution; only complete acceptance earns coverage.
6. Test changed shared boundaries with the actual Perl helper and Python
   recorder. Then finish edits, build fresh artifacts and run the exact variant
   through the [public E2E command](../../tests/e2e/README.md#run-e2e-scenarios).
   Hold source/documents unchanged through terminal collection and cleanup.
   Reuse resulting runner artifacts; update the active handoff with only the
   references and continuation state it needs.

The shared controller regressions use a second synthetic plan to check reuse,
the real durable recorder to check phase timing, and injected checkpoint/worker
failures to prove no further input is acknowledged:
[controller tests](../../tests/unit/test_installed_journey_cleanup_safety.py).
[Pointer tests](../../tests/unit/test_e2e_pointer_helper.py) and
[Parent worker tests](../../tests/unit/test_parent_about_worker.py) execute the
real Perl modules. Synthetic fixtures never count as customer coverage.

## Lessons to preserve

| Observed challenge | Reusable resolution |
| --- | --- |
| Black VNC image after the installation reboot | Disable before setup, then use `onpc_gdm::reattach_after_setup`: public `reset_consoles` followed by `select_console('sut')`. Disabling alone leaves a console marked activated. Never reset the VM inside a customer journey. |
| Correct screenshot match but click misses a small control | Generalhw images are 1024×768; pointer coordinates use the framebuffer. Use `onpc_pointer::click`, which derives the point from the fresh match and public `mouse_width`/`mouse_height`. Qualified framebuffers are 1024×768 and 1280×800. Refuse new sizes until qualified. |
| Installed greeter differs from the baseline account list | Observation and input tags have different purposes. Keep installed and baseline pixels separate. Match the real wrong-role empty prompt negatively and Parent prompt positively before the unchanged secret API. Account selection alone proves no password recipient. |
| GDM scrolls its account list during a standard-account click | `onpc_gdm::inspect_installed_standard` establishes the Parent prompt, returns to the list and navigates from Home through the fixed baseline's account order. Escape resets focus to the top. Match the standard fixture's focused outline before Enter, then its own empty password prompt before secret input. The optional parent-prompt callback provides wrong-role qualification. Never infer the recipient from a clicked position or the absence of a list needle. |
| Parent search shows only an online suggestion for a standard user | The [launcher contract](../SystemDesign/Broker.md#accounts-and-roles) intentionally restricts app-grid discovery to administrators. Match the exact query, web-only suggestion and empty application-result area. Do not press Enter on the suggestion or invent a denial dialog. Executable denial belongs to the separate terminal variant. |
| Keyboard assumptions select the wrong child or menu item | Match and click the explicit fixture row and About menu item. Launch Parent with Super-A, a confirmed app grid, the product name and Enter. An app-grid stage precedes launching the app. |
| About footer stays hidden | After closing LICENSE, reassert About, focus its scroll area with Tab and use plain End. In this GTK ScrolledWindow, Ctrl-End scrolls horizontally. Preserve the positive footer match. |
| An acknowledged action has no durable evidence, or belongs to the wrong step | Store the observation and any required next-phase start before publishing the reply; guard ownership again after storage. An acknowledgement may immediately permit input. Storage or guard failure latches terminal failure. |
| A stale match appears to prove returning to the same child | `matched_screens` consumes one fresh match per ordered stage marker and requires every region at 100%. Reassert the same child's displayed settings on return. Missing, reused, weak or reordered evidence refuses. Worker exit zero alone cannot pass. |
| Fresh code runs against stale package/needle inputs | Finish all edits, including docs, before building. Use the generated artifact directory unchanged. Do not edit during a guarded attempt; provenance changes invalidate its result. |
| VM is off but baseline acquisition reports `guard:source-changed` | Inspect the saved run phase and inactive configuration through the approved readers. An interrupted `isolated` setup can retain the test configuration. Use recorded graphical cleanup; do not edit the journal, recreate the baseline or treat powered-off status alone as restored state. |

## Add or repair a screen needle

A needle is a reviewed PNG plus JSON regions used by the real image matcher.
It must come from the installed surface being tested. Inspect the current
failure and named private screenshot before changing coordinates or pixels.
Do not lower matching thresholds, synthesize evidence, add fixed click fallback
positions or copy another account's password recipient.

Use the [approved screenshot export](Approval-Tools.md) to create a caller-owned
PNG directly under `/tmp/onpc-*.png`, then inspect it. The preparation template is:

```sh
tools/prepare-e2e-needle --source '/tmp/onpc-parent-menu.png' --tag 'onpc-parent-menu' --area 'X,Y,WIDTH,HEIGHT' --click --replace
```

Replace the four coordinates with a region from that inspected image. Repeat
`--area` for identifying context and put the clickable control last; `--click`
uses its interior center. Use `--replace` only for an existing reviewed pair.
The tool removes unrelated pixels and metadata while preserving each region's
16-pixel matcher border. It refuses arbitrary password tags and output paths.
The fixed `onpc-gdm-other-child-masked-password` tag is reserved for the standard
fixture's reviewed empty prompt; preparing pixels alone cannot authorize input.

For a new nonsecret tag, extend the existing `TAGS`/`CLICK_TAGS` registry and the
affected consumer, rather than copying the preparation algorithm. The worker
validates the registered PNG/JSON pair and click eligibility before execution.
Keep input and observation tags distinct where only one should authorize a click.
Secret-recipient changes need their own positive and wrong-role qualification;
this image tool cannot perform that qualification.

When a missing nonsecret observation blocks image acquisition, the fixed
`tools/run-tests integration check_parent_about` diagnostic can observe several
screens in one attempt. Its optional review mode never bypasses recipient,
desktop, app-grid or click checks, and terminal validation still rejects missing
matches. It uses verified artifacts staged at `/tmp/onpc-parent-setup-input`;
preserve the generated originals. Use the public strict scenario for acceptance.

For standard-user access, `tools/run-tests integration check_parent_standard_input`
performs only credential-free prompt acquisition. After reviewing its focused-row
and empty-prompt images, `tools/run-tests integration check_parent_access` reuses
`ParentJourneyQualification` to acquire the unavailable-launcher screen. Both use the same
verified fixed artifact input. The authenticated review still requires the exact
recipient, wrong-role negative check, desktop and app grid; missing terminal
matches cannot pass validation. The public E2E-004/app-grid callback always uses
strict matching.

Explicit captures after authentication remain prohibited. Automatic worker
captures stay private. Preserve original reports and screenshots; remove only
named temporary exports with `tools/cleanup-screenshots` when finished.

## Current extension boundary

E2E-003 reuses installed Parent login, launch and evidence handling. Its two
scoped fixture actions cover dynamic eligible-account creation after an existing
child is visible and a finite no-eligible-account state before Parent launches.
The latter requires exactly the guarded baseline's three eligible standard
accounts, preserves the fixed package request station and refuses unexpected
identity/object sets before mutation. A stage action executes only while the
worker is fresh and before its durable reply; failed workers retain owned
process/callback cleanup for outer restoration. Visible refresh/selection or the
reviewed empty explanation supplies the assertion; no broker/catalog probe can
replace it. Keep qualification in the [Task 21 handoff](Task-21.md#current-handoff--2026-09-15).

These are development test tools, activated on the next invocation (`none` for
package update activation); no product integration or saved-data format changes.
Refresh the installed dispatcher with `./setup.sh --test-tools-only` after its
command-line interface changes. Shared modules alone need no setup refresh.
