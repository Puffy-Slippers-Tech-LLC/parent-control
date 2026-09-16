# Task 21 — Parent customer journeys

Follow [E2E-Coverage.md](E2E-Coverage.md). All acceptance uses real customer
actions and visible results. Existing lower-level regressions stay unchanged;
backend account/catalog, D-Bus, grant, rule and private-state assertions are
not part of these journeys.

## Implementation slices

Complete one named variant before expanding. Use accepted installation/account
setup, graphical input and cleanup. A helper from another task may be used or
minimally completed with this consumer; that task's full matrix is not a dependency.
Use [the workflow](Implementation-Workflow.md) for bounded work and progress.

## Task 21A

- Title: Parent discovery, navigation, access and feedback drafting.
- Depends on: accepted graphical runner and verified installed-package setup.
- Default settings: `gpt-5.6-sol` / `high`; reassess ordinary expansion.
- Customer scope: E2E-003/004/030/031. E2E-005 saves belong to 21B.
- Work:
  1. Log in as a parent, launch Parent from the app grid, discover and select
     eligible children. Observe loading, selection and independent displayed
     settings. For dynamic discovery, use the supported account fixture while
     Parent stays open and observe the new child appear.
  2. Use allowance controls, app search/filter, displayed rules and matching
     choices. Cover representative valid/invalid boundaries and visible
     explanations. Do not expand already-tested local validation matrices.
  3. Log in as a standard user and try the normal Parent launcher. Observe
     management is unavailable. Direct broker attacks remain separate tests.
  4. Open About/license, compose feedback, review synthetic attachments and
     cancel. Check visible validation and retained/cleared drafts as specified.
     No external message is sent in this task.
- Verification: run the assigned complete variants through the guarded E2E
  selector, inspect safe screens/step results, and run affected regressions
  plus existing safety prerequisites. Use `make check` and scoped whitespace
  checks once at stable task acceptance, not after every UI step.
- Completion criteria: the listed visible flows pass on the installed app.
  Correct the pending E2E-003 fixture-event declaration with its first consumer.
  E2E-005 ownership now matches 21B; registration or reclassification earns no
  scenario credit.

## Current handoff — 2026-09-15

**Accepted coverage includes E2E-003/existing-and-new, E2E-003/none,
E2E-004/app-grid and E2E-030/parent; the functional migration is described below.**
Progress is **4 completed, 152 remaining of the frozen 156**, with no additions
or transfers and **0 consecutive slices without a completed customer variant**.
Task 21A remains unchecked for E2E-004/terminal and E2E-031.

The registered [discovery callback](../../tests/e2e/parent_discovery.py) now owns
both finite variants. Case 3 existing-and-new uses functional AT-SPI checkpoints
for app search, existing/new child selection, App Limits navigation and return to
the original displayed settings. It retains the guarded in-app account event,
qualified GDM credential boundary and complete cleanup. The functional GDM
route verifies wrong-recipient refusal and twice checks the intended identity
and empty masked field's focus before single-use secret input. Each selected child is
observed independently after keyboard selection; switch and allowance values are
compared on return. No time policy changes or enforcement claims occur here.
Case 4 (none) now uses the same functional GDM credential gate, pauses at a
fresh launchable Parent search result, requires
the guarded baseline's exact two eligible canonical child fixtures, preserves
the package request station, makes only that finite set ineligible, launches
Parent and independently reads the showing empty explanation and empty child
picker through public accessibility. There are no application needles or fixed
coordinates in this journey. Fixture identities and role changes remain setup
evidence; ordered semantic UI checkpoints supply customer acceptance. The
functional migration's complete passing run is recorded below.
The [composition contract](../../tests/e2e/README.md#parent-consumer-composition-limits),
[building blocks](E2E-Building-Blocks.md) and [reuse row](Reuse-Map.md#customer-scenario-work)
own the bounded action, refusal, matcher and cleanup limits.

Case 4 functional public acceptance `scenario-37e11b1362104b3290bba31ce28f630e`
passed `tools/run-tests e2e --id 4`, every declared phase and all four outcome
domains. Case evidence is `/tmp/onpc-e2e-evidence-1t7cymxc`, invocation evidence
`/tmp/onpc-e2e-evidence-kcvntm3k`, worker evidence
`/tmp/onpc-e2e-evidence-3mqjfpb1`, and artifacts
`/tmp/onpc-test-artifacts-xdfh384u`. Passing source is
`c29da50e850bd3abbaf389dc93c524eac670d77e1c78f179f5f51297fd5fb373`;
inventory is `f75e8e8952ea41c0310e73bdc1194ed35b13249760f1081551150911afcbfaf0`.
The 328 focused regressions, real GTK empty-state adapter at 100%/125% scale,
and the runner's 1,235 cleanup-safety tests plus 3 subtests passed. This is the
no-eligible-child journey only; it changes no time limits. This post-pass handoff
edit preserves the recorded runtime result's original source identity.
E2E-003/existing-and-new remains `scenario-117ce953fa404067aef01072bbce5b6b`;
E2E-030's current passing attempt is `scenario-c2585a481eca4cf9b2b9021f502eaf42`,
with all customer steps and cleanup passed; invocation evidence is
`/tmp/onpc-e2e-evidence-wqwsmafn`, using source
`fd5f6b37120cdcfdcb3408b6a86e5a28a964191f484e879d62715abf2e6d5072` and
artifacts `/tmp/onpc-test-artifacts-ntq5uzt6`. Later handoff edits need fresh
build inputs, but do not invalidate the demonstrated screen behavior.

**Prior image-matcher blocker:** E2E-003/existing-and-new attempt
`scenario-e7cc3a8d1bc04ff2a189e882d88ea2b2` reached Parent, where an Ubuntu
update-notifier banner obscured the title required by the child-picker needle.
See `/tmp/onpc-graphical-smoke-abfecf2s/testresults/smoke-37.png` and invocation
`/tmp/onpc-e2e-evidence-lch8lg4y`. This is a graphical harness blocker, with
cleanup passed and no demonstrated product failure. The invocation stopped
before cases 4/5. Case 3's functional migration removes the application image
dependency: a notification matters only when it blocks required interaction or
information. Validate case 3 through its full public selector and retain the
new invocation evidence. Case 4's migration is described above. Case 5 now uses
functional public accessibility for the standard-user desktop, app-grid search
field, exact product query and web-only result, with fresh complete reads proving
no Parent launcher or management window. Its credential gate now reuses the
functional wrong-recipient refusal and two fresh identity/masked/focus checks
with standard-specific acknowledgements; legacy credential needles remain intact.
The functional migration passed the full public selector and cleanup in
`scenario-9bf9dd14b42045e8a902b9177688b3aa` (`tools/run-tests e2e --id 5`).
All declared checkpoints and all four outcome domains passed, including full
baseline restoration. Invocation evidence is `/tmp/onpc-e2e-evidence-xy712c88`,
case evidence `/tmp/onpc-e2e-evidence-fpdkzh3m`, worker evidence
`/tmp/onpc-e2e-evidence-d2oe7frs`, raw artifacts
`/tmp/onpc-graphical-smoke-1ugnpkf0`, and build artifacts
`/tmp/onpc-test-artifacts-fy5qwyk2`. Passing source is
`27a21c8c56898555c005eaf53542c0afe87ff255640601896806cbd625b1551a`;
inventory is `f9611705d978097a1be3d11068b8ce6cafb977fe05fbfb9a48195d9edb8c03a3`.
The inventory listing confirms case 5 remains `ready` at
`tests/e2e/parent_access.py::app-grid`.

The shared desktop wait handler cancelled three successive login-keyring
dialogs through normal pointer input, independently proving each specific
dialog disappeared before handling its replacement. It resumes the pending
observation without replaying earlier actions; GDM and unknown prompts remain
excluded. The web-only result uses the shared label-to-button lookup and requires
its query-specific description within the same result. Guidance and regressions
cover these reusable operations. The 309 final focused accessibility/discovery/
access regressions, transport/worker safety checks, isolated Shell query test
(`/tmp/onpc-e2e-search-unu7npxr`), source validation, and the installed runner's
1,251 cleanup prerequisites plus 3 subtests passed. This post-pass documentation
edit preserves the passing run's source identity. No time policy changed:
E2E-005 enforcement and E2E-004/terminal remain outside this case's proof.

Four failed acquisition runs remain retained and fully restored: the first
exposed a missing declared step-2 transition (`/tmp/onpc-e2e-evidence-z2nkqg2x`);
the second visibly exposed one unhandled baseline standard account
(`/tmp/onpc-e2e-evidence-ynz2p1qn`); the third fixed the failure at the package
request-station exclusion (`empty-account:baseline`,
`/tmp/onpc-e2e-evidence-ubaj_nv8`); the fourth acquired the genuine empty screen
before its reviewed needle existed (`/tmp/onpc-e2e-evidence-oboc3c81`). Each
subsequent attempt used new discriminating evidence and locally checked code;
none reported a product failure. Focused fixture, worker, inventory, runner,
needle and controller regressions pass, as do each run's 1,184 cleanup-safety
tests plus 3 subtests. The final run verified full baseline restoration.

**Next: E2E-004/terminal.** Reuse the qualified standard-user recipient and
installed setup. Invoke the executable through the guest terminal and observe
denial with no management window. The app-grid variant proves the intentional
absence of the administrator-only launcher; it does not exercise executable
denial. Do not add internal authorization assertions.
Post-pass documentation edits require fresh artifacts. VM is off,
temporary exports are removed, no owned operation remains, and R1 stays 0 hours /
0 attempts.

**Actual settings:** `gpt-5.6-sol` / `high`, Standard.
**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep; effort: keep.
**Reason:** standard-user login and app-grid unavailability are qualified; the
terminal route needs its own complete installed customer run.
## Task 21B

- Title: Parent saves, control changes and revocation.
- Depends on: only the Parent/login/approval interactions needed by its selected
  variant; no Task 15B, 16B or policy-acknowledgement prerequisite.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-005/006/007; share canonical app-use cases with Task 25.
- Work:
  1. Set zero/positive allowance and enable/disable control in Parent. Observe
     saving, reopen the settings, and attempt child login/use to see the result.
  2. Change allowed/hard/soft app choices and supported matching options.
     Attempt actual child launches; observe the intended window or denial.
     Switch to another user and use their app where isolation is claimed.
  3. Establish time through a real request/authentication when needed. Cancel
     revocation, then confirm it in a separate declared path. Observe displayed
     time, child access and app-window effects required by the product.
  4. Check visible loading/disabled controls and ordinary cancellation/retry.
     Do not induce service/reload/termination faults or inspect transaction state.
     A real failed save remains a failed scenario with a separate product blocker.
- Verification: complete each selected UI-to-child-use journey, retain visible
  evidence and existing cleanup results, then affected regressions and stable
  task acceptance checks.
- Completion criteria: saved choices and revocation have the documented visible
  effect for the selected child, with customer-observed isolation where assigned.
  No internal atomicity, activation receipt or rollback-readback claim is made.
