# Reusable customer E2E building blocks

This is the ordered implementation backlog for composing customer scenarios.
It covers all **33 families / 157 variants** in
[scenarios.json](../../tests/e2e/scenarios.json).
The inventory currently has five ready variants: cases **1, 3, 4, 5 and 151**.
Case 1 qualifies the harness; the other four are customer journeys.
Case 1 composes FLOW00; case 3 now composes the scoped functional FLOW01,
Parent navigation and explicit settings-comparison blocks. Cases 4, 5 and 151
retain their existing worker compositions and inventory statuses.
Every catalogue row has an implementation status; existing
behavior that still needs extraction is `pending` even when its scenario is
already `ready`. There are **153 blocks: 51 ready and 102 pending**, including
four fixture operations and explicitly scoped harness/credential-safety blocks.

The review covers every step, variant parameter and assertion in all 33
families. The recipes account for **144 customer variants**, the conditional
customer retry route for **157**, harness case **1**, and the **11 internal-fault
variants 140–150**. Case 1 now has a complete block composition, including its
serial segment. The remaining internal-fault declarations and legacy backend
assertions cannot be fulfilled by customer UI blocks; their exact disposition
is recorded under [inventory reconciliation](#inventory-reconciliation).
Accounting for an assertion is not a claim that it has been implemented.

**Completed refactors: cases 1 and 3 within their qualified scopes.**
Case 3 has passed its complete installed journey, terminal collection and
baseline restoration. See [case-3 qualification](#case-3-refactor-qualification)
for its callable boundaries and preserved assertions. The
[case-1 stage contract](#case-1-stage-contract) remains its preservation
reference, with baseline evidence in retained runner artifacts.
Case 4 is the remaining consumer in the
second implementation slice; its existing ready status is unchanged. Retain
shared-helper regressions for all five ready cases and require each migrated
consumer's complete installed acceptance.

## How to implement one block

The tests simulate a customer's operations and observe the results. They do
not care how the application achieves them. Select users, type into real
prompts, operate settings, launch applications, read messages and use windows.
Never replace those steps with product methods, saved-data reads/writes,
process inspection, service checks or synthetic grants. Existing runner
ownership, secret handling, installation setup and cleanup remain supporting
machinery, not customer assertions.

- **A — atomic:** one input operation or one public observation. Its local
  target, safety and result checks do not silently log in, launch an app,
  select a child or change a setting. It may use native UI/runner APIs and
  local implementation helpers, but performs no second scenario operation. Pure observation comparisons and
  bounded elapsed-time measurements are also leaves. A harness leaf is explicitly
  marked as such and cannot supply a customer product assertion.
- **C — composite:** only the listed earlier blocks, in the stated sequence.
  Branches use explicit arguments or a declared public result. Bounded repeats
  and optional confirmation dialogs are declared, never guessed after failure.
- **Independent:** a block receives its surface, target, expected value,
  deadline and any earlier observation explicitly. A visible UI precondition
  is allowed; requiring a particular previous test or hidden global state is
  not. An independently supplied valid entry state must work. A wrong entry
  state fails without performing preparatory customer actions.
- **`ready`:** the cited callable implements the exact stated scope today.
  **`pending`:** extraction, generalization, new implementation or qualification
  is still needed. Existing code is a reuse source, not proof that the proposed
  interface is ready. A runnable scenario can contain pending-to-extract blocks.
  Mark a composite ready only after its callees and its own complete behavior
  are qualified. Block readiness is distinct from inventory readiness and a
  passing scenario run.

Every implementation records its source callable and qualification reference
in its row. Use explicit fixture identities and registered selectors; do not
expose arbitrary commands, arbitrary UI-tree dumps or private account names in
reports. Return small semantic observations, never live widget handles across
checkpoints. Reacquire controls after transitions. A block may return a local
public object only to another operation within the same adapter invocation.
Comparisons use explicit immutable observations owned by the scenario, replacing
the current special `initial_settings` / `new_settings` slots when migrated.

Successful input is not a successful customer outcome. Observe the resulting
selection, text, window, message or access separately. Retry fresh reads within
the deadline; never replay uncertain input. Repeated submission is a deliberate
customer gesture with its own finite contract. All waits have a named result
and a timeout; elapsed time alone cannot establish enforcement.

Tables are in dependency order: leaves, small control composites, GDM and the
case-1 harness, desktop entry, application surfaces, then journey fragments.
Each composite calls only earlier IDs; row order, not numeric ID, determines
implementation order. Fixture operations have their own preparation order and
are called only by the surrounding envelope or at declared recipe checkpoints.

### Implementation slices

| Order | Consumer and bounded work | Completion gate |
| --- | --- | --- |
| 1 | Case **1**: scoped UI/GDM/HAR extraction and FLOW00. | Complete; preserve its stage contract and affected shared-helper regressions. |
| 2 | Cases **3 and 4**: functional sign-in, whole-query search, child selection/settings/navigation, explicit comparison and the two existing fixture checkpoints. | Case 3 complete: installed acceptance and cleanup passed, including FIX01 timing and each child's own returned settings. Case 4's remaining extraction and live qualification are still pending; preserve FIX02 before launch. |
| 3 | Case **5**: focus, paced first-character/full-query readback, exact web-only result and stable absence. Generalize UI03 only for the required projections. | Complete installed case 5 passes with no input repair and no Enter on the web suggestion. |
| 4 | Case **151**: retained credential guards, shared launch/selection, About, bounded license content, footer and unchanged return. | Complete installed case 151 passes; license-close input still belongs to step-2. |
| 5 | Pending customer cases in numeric order, selecting their transitive dependencies in catalogue order. Extend only the scopes their named consumer needs. | Full declared journey and assertions pass after any explicit inventory reconciliation; no partial pass. |

A slice implements its dependency set, not every earlier unrelated pending row.
For example, case 1 needs neither the search/license UI03 extraction nor repeated
graphical authentication. Preserve adapters used by other ready cases until their
own migration. If a prerequisite is unavailable, retain `pending` with the
concrete blocker and return condition; work may continue on an independent row.
All five ready cases must remain runnable and passing throughout the migration.

## Ordered building-block catalogue

### Public observations and individual inputs

These are in-process building blocks behind registered public-UI checkpoints,
not a new remotely executable scripting API. The existing adapter's shared
system-prompt handling and guarded recorder remain middleware for every block.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| UI01 | A | Find one control by public surface, name and role. Require showing state; require enabled state only for input. Reject ambiguity; return a fresh local target. | `AccessibleUI.target`, `find`, `labelled_button` in [accessible_ui.py](../../tests/e2e/accessible_ui.py). | ready |
| UI02 | A | Read one declared public boolean state through the state interface, such as selected, checked, focused, enabled or showing. Disabled settings remain readable. New surface/state bindings need their consumer's qualification. | `AccessibleUI.has_state`, `showing`; existing selector scope only. | ready |
| UI03 | A | Read one registered nonsecret text projection from a showing label, field or document. Inputs: surface/selector, maximum characters, expected projection and deadline. Return a bounded semantic value or match result, never arbitrary document text. Reject masked fields before accessing Text. | `AccessibleUI.read_label(root, projection, maximum=80, expected=child)` returns only canonical child identities or bounded duration labels. Parent labels only; search/document projections remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI04 | A | Activate one fresh showing, enabled control through its sole public action once. Return input completion, not the claimed customer result. | `AccessibleUI.activate`. | ready |
| UI05 | A | Send one declared normal key/chord to an already qualified recipient, such as Enter, Escape, Tab, Home, Down or Super-A. | Existing workers' `testapi::send_key`; secret entry is excluded. | ready |
| UI06 | A | Type one nonsecret string once at a declared bounded pace into the intended input surface. | Existing workers' `testapi::type_string`; case 5 demonstrates paced input. | ready |
| UI07 | A | Resolve a current pointer target from a showing, enabled public control's screen extents. Coordinates only route input. | `AccessibleUI.pointer_target`. | ready |
| UI08 | A | Perform one normal pointer click at the freshly supplied target, validating console and current framebuffer bounds. Never retry an uncertain click. | `onpc_journey::click_target` in [onpc_journey.pm](../../tests/integration/graphical_smoke/lib/onpc_journey.pm). | ready |
| UI10 | A | Wait for a read-only public predicate within its deadline, dispatching pending accessibility events and reacquiring stale objects. | `AccessibleUI.wait`; the predicate must contain no input. | ready |
| UI11 | A | Observe absence of a named window/control within an otherwise positively recognized surface. Bind `snapshot` or `stable` mode explicitly. Both require complete fresh reads; stable mode additionally requires its declared finite interval and deadline. | `AccessibleUI.observe_absence` supports fresh complete GDM snapshots and the Parent child-popup snapshot with a positive closed picker and intended identity. Stale/defunct trees refuse. Stable/search scope remains pending. Case-1 and [case-3 qualification](#case-3-refactor-qualification). | ready |
| UI12 | A | Compare explicit sanitized observations with an explicit expected value or earlier observation; report the differing approved fields. No hidden initial/new-child slots. | `SettingsObservation.from_settings` freezes sanitized values; `compare_settings(observed, expected)` compares explicit immutable observations and reports only differing field names. `JourneyPlan.settings_checks` owns expectations and prior-stage references. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI13 | A | Observe a bounded public collection: canonical choice identities/order, matching window count, or displayed row set. Inputs declare root, projection, maximum and expected cardinality (including zero). Require complete fresh traversal for exclusion/count claims; reject duplicate fixture identities and unknown requested targets. | `AccessibleUI.choice_order(root, identities, maximum, cardinality, projection)` supports registered greeter and child-picker order. Complete fresh traversal rejects duplicate fixture identities, stale reads and invalid bounds; unrelated labels remain private. `greeter_navigation` and `child_navigation` derive Home/Down. Case-1 and [case-3 qualification](#case-3-refactor-qualification). | ready |
| UI19 | A | Type one fixture secret once through the unchanged secret-safe API for one freshly qualified challenge. Accept a registered secret reference and explicit recipient proof, never plaintext in stage data. Do not submit or infer authentication success. Capture remains sealed and uncertainty/failure forbids replay. | `onpc_serial::type_fixture_secret` retains its serial proof binding. `onpc_password::type_fixture_secret(role, journey, proof)` consumes a fresh registered GDM recheck reply before one sealed secret API call. Parent/GDM and serial are qualified; multiple authentications and other surfaces remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI20 | A | Perform one deliberate bounded native double-click gesture on a freshly qualified enabled target. Record it as one intended gesture; no retry or click repair. | Existing normal pointer API; new consumer is E2E-014. A disabled/hidden target cannot authorize a gesture. This is not two separately retried click blocks. | pending |
| UI22 | A | Observe a bounded trace of registered public status/control states across one declared transition. Start before the triggering input, acknowledge observation readiness, then finish at the explicit terminal predicate/deadline. Return sanitized ordered samples and monotonic offsets. The caller owns the input between start and finish. | New read-only public observation for E2E-005 saving/control inhibition, E2E-014 duplicate submission and E2E-031 collection. Reuse guarded checkpoint transport; missing a required transient state is unproven, never inferred from the final state. No product hooks, fault delays or replay. | pending |
| UI23 | A | Request one public scroll-to operation for a registered existing offscreen target, only when it is not already showing. Require a visible, nondefunct object and its public Component interface; return input completion only. | `AccessibleUI.scroll_target(name, roles, root=...)` issues the public scroll request; `reveal` independently reacquires the showing target. Qualified for Parent remaining-time and filter controls. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI24 | A | Read the public formatting attributes of one explicit bounded synthetic text range and compare the named expected format. Return semantic attributes only. | New FEED04 consumer using the editor's public accessibility Text attributes. A pressed toolbar button alone does not prove text formatting; unavailable attributes block that assertion. No DOM or saved-draft read. | pending |
| SEC01 | A | Observe one fixed legacy credential-safety predicate: reviewed needle present/absent, or the existing bounded settling check. Its profile, timeout and expected polarity are explicit; it authorizes no input by itself. | Extract the fixed checks in `onpc_parent::login` and `onpc_password::enter_password` for case 151 only. Preserve tags, thresholds and wrong-recipient exclusions. No new customer appearance gate. | pending |
| SEC02 | A | Click one registered legacy account-input needle through its existing matched-pointer helper. Require current match and input eligibility; return input completion only. | `onpc_pointer::click` for case 151's two account choices; qualification stays separate from the password recipient. No fixed-coordinate fallback or new needle. | ready |
| UI09 | C | Reveal a named existing control/content, then independently require a fresh showing target. | `AccessibleUI.reveal` composes `scroll_target` (UI23) and a fresh `target` (UI01/UI02). Parent content/filter scope; other selectors need their consumers. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI14 | C | Highlight one choice in an already open list. Derive Home/Down from its observed order, then independently verify the intended identity and focus/selection before committing. | `onpc_journey::highlight_choice` consumes an explicit fresh list reply, sends bounded Home/Down and obtains a separate focus/selection checkpoint. GDM and case-3 child-picker bindings are qualified; other controls remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI15 | C | Select one value from a named dropdown/menu or visible choice group. The registered control kind and commit route are explicit; independently verify the resulting selected value. | `AccessibleUI.open_child_picker`, `child_highlighted`, `selected_child` and `onpc_parent::select_child` compose the opened/highlighted/committed/closed-picker checkpoints. Only the registered existing/new/returned child bindings are qualified; other dropdowns/groups remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| UI21 | C | Focus one named showing, enabled nonsecret field by a normal pointer click; independently require focus. Input: explicit surface/field. | UI01 → UI07 → UI08 → UI02. Generalizes case-5 search focus for fields, terminal input and rich-text editing. | pending |
| UI16 | C | Replace text in one named nonsecret field: focus, select all, type once, then read the exact result. Empty input explicitly means clear. | UI21 → UI05(Ctrl-A) → UI06(value), or UI05(Backspace) for empty → UI03(exact value, including zero length). Selecting all alone does not clear a field. Register field-specific projections with their consumer. | pending |
| UI17 | C | Set one named toggle to an explicit boolean. Read first, activate once only when different, then independently require the desired state. | UI01 → UI02 → conditional UI04 → UI02. Used directly for Parent screen limits and by request/network composites. | pending |
| UI18 | C | Close the explicitly identified window with its declared Close action or Alt-F4. For keyboard close, first verify the window is active. Observe disappearance and the expected underlying surface. | UI01 → UI02(active, keyboard route) → UI04 or UI05 → UI11 → UI01. Modal confirmations require separately declared input. | pending |

### Sign-in and desktop entry

Account parameters are a closed set of provisioned fixture roles, not arbitrary
usernames. The public-UI connection must be qualified for the selected greeter
or desktop. Extending the current fixed Parent/other-child routing is part of
the affected entry block; that connection metadata supplies no product evidence.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| GDM08 | A | Observe the selected account label, focused showing password role and hidden account list. This is a nonsecret prompt observation only; it cannot authorize password input and never reads password contents. | `AccessibleUI.greeter_prompt()` for the current Parent fixture in case 1. Other identity bindings remain pending with their consumer. Keep this distinct from GDM03's stricter empty-field recipient proof. | ready |
| GDM03 | A | Read the intended GDM recipient's identity and sole showing, enabled, focused, empty masked field with the account list hidden. Read character count only, never password content. | `AccessibleUI.password_recipient(name)` for the existing four fixture identities. Other surfaces are not covered. | ready |
| GDM01 | C | Observe the usable greeter and its account list, with no active password prompt. | `AccessibleUI.greeter_list(name)` → UI11(snapshot) with the fresh UI01 account control. Used at initial list, dismissal and graphical return; case-1 Parent binding qualified. | ready |
| GDM02 | C | Select a named user on the logon screen. Derive navigation from the current list, verify focus before Enter, then observe the declared password prompt, retained lock or passwordless station. Do not type a password. | `onpc_gdm::select_prompt(journey, 'parent', 'prompt')`: GDM01/UI13 at `gdm` → UI14 → UI05(Enter) → GDM08 at `selected`. Only Parent/prompt is qualified; lock/station bindings remain pending. | ready |
| GDM09 | C | Dismiss an already observed GDM password prompt with one Escape and independently observe the account list again. No secret is typed. | `onpc_gdm::dismiss_observed_prompt(journey, prompt)` consumes the explicit fresh GDM08 prompt, sends UI05(Escape), then obtains GDM01 at `dismissed`. Missing, stale, replayed and review evidence refuse. Parent/prompt binding only. | ready |
| GDM04 | C | Observe a different account's empty GDM prompt, prove it is refused as the intended secret recipient, dismiss it, and observe the account list again. The declared wrong account has no retained desktop, so selection reaches a GDM prompt. | `onpc_gdm::refuse_wrong_recipient(journey, 'other-parent', 'parent')` uses `choose_account` (UI14/UI05), the positive wrong/negative intended GDM03 checkpoint, one Escape and fresh GDM01. Fixed Parent sign-in binding only. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| GDM05 | C | Type the intended user's password into the already selected GDM prompt. Require the explicit wrong-recipient evidence and two fresh ordered recipient checks immediately before one secret input. Do not submit. | `onpc_password::enter_parent_gdm_password` retains the two ordered fresh GDM03 acknowledgements and passes the explicit final proof to `type_fixture_secret` (UI19). One Parent/GDM authentication; subsequent challenges remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| GDM06 | C | Observe the declared access result at GDM or lock: usable intended desktop, or time-limit rejection with its explanation and no desktop access. A generic failed login is not the expected denial. | `AccessibleUI.desktop_result(account, 'success')` observes normal Shell controls on the qualified Parent desktop connection. Only Parent success is qualified by this extraction; denial/lock routes remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| GDM07 | C | Enter a fresh session as an explicit account with expected success or time-limit rejection. Require a declared wrong-recipient fixture and no retained target desktop. Retained entry is a separate unlock route. | `onpc_parent::sign_in(journey, 'parent', 'other-parent', 'success')` composes wrong-recipient refusal, fresh list/highlight/Enter, GDM05, submission and GDM06. `choose_account` stops at Enter; GDM05's first observation independently qualifies the resulting prompt. Fresh Parent success only. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| GDM10 | C | Preserve case 151's qualified legacy Parent sign-in until a separate credential migration passes. Inputs bind its exact fixed account tags and stage names; no new role/surface is supported. | SEC01(list present, intended prompt absent) → SEC02(other parent) → SEC01(existing settle and wrong-recipient/list exclusions) → UI05(Escape) → SEC02(parent) → SEC01(list absent, intended prompt present) → SEC01(fresh recipient check) → UI19(legacy Parent/GDM) → UI05(Enter) → GDM06(success). Extract `onpc_parent::login($journey, 1)` without changing its guards. Runtime reattachment remains in the setup envelope. | pending |

### Harness transport and serial qualification

These blocks serve **case 1's harness assertions**, not customer product
acceptance. They name and split its existing operations without adding commands,
probes, authentication attempts or runner services. Fixed serial input strings
are registered recipe data; UI06 never becomes a remote arbitrary-command API.
Raw terminal text and fixture names stay private. Keep the current single-attempt
serial latch around the entire composition, including every failure path.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| HAR01 | A | Select one existing public test console, `sut` or `onpc-serial`, once. Require the declared current console and verify the resulting selection. Initial `sut` binding also permits the runner's known unselected state. Do not create/reconnect/reset a console here. | `onpc_harness::select_console(from, to)` supports only initial→sut, sut→onpc-serial and onpc-serial→sut. Source/destination checks and independent entry states are qualified by the real Perl GDM/serial tests. | ready |
| HAR02 | A | Wait for one registered serial text projection within its existing timeout: login prompt, exact fixture echo plus password prompt, shell prompt, or complete harmless-command output. Return a semantic match only. | `onpc_serial::observe_text(projection)`, closed login/password/shell/command/logout profiles. Retains quiet/private output, fixed deadlines, exact bounded fixture echo, LF/CRLF normalization and split-marker stdout match. | ready |
| HAR03 | A | Obtain one fresh fixed harness observation: `boot`, `greeter`, `serial-password` or `serial-session`. Require the existing lease, identity, exact result schema and terminal failure latch. | `check_graphical_smoke.harness_observation(observer, projection)` exposes only boot/greeter/serial-password/serial-session through the existing guarded, schema-checked `ReadOnlyObservations.read`; used by `Smoke` and recorder boot middleware. | ready |
| HAR04 | A | Permanently seal explicit capture before serial authentication preparation. Repeated calls cannot reopen it. | `onpc_password::seal_capture`; the serial worker's existing no-video policy and secret registry remain mandatory. | ready |
| HAR05 | C | Authenticate the fixed serial fixture once and observe its real session and usable shell. No graphical secret is involved. | `onpc_serial::login(state)`: HAR04 → HAR01 → HAR02(login) → UI06(username) → HAR02(password) → HAR03 checkpoint → UI19 → UI06(newline) → HAR03(session) → HAR02(shell). `attempt(exchange, body)` retains the encompassing single-attempt/video/capture/failure boundary. | ready |
| HAR06 | C | Submit the existing harmless serial command once and observe actual output, then independently corroborate its session. | `onpc_serial::command(state)`: UI06(fixed split-marker command) → HAR02(output) → HAR03(session checkpoint). Explicit authenticated entry; consumes state before input and never replays failures. | ready |
| HAR07 | C | Log out the authenticated serial fixture normally and independently observe the session-free greeter before any graphical return. | `onpc_serial::logout(state)`: UI06(exit) → HAR02(login) → HAR03(session-free greeter checkpoint). Returns this attempt's explicit logout evidence and emits the existing successful marker exactly once. | ready |
| HAR08 | C | Return from the logged-out serial console to graphics and obtain a fresh public greeter observation. Require HAR07's explicit evidence from this attempt. | `onpc_serial::return_graphics(state, logout)`: consumes HAR07's evidence → HAR01(sut) → HAR03(greeter) and GDM01 at the existing `gdm-return` checkpoint. Missing/stale/reused or early return refuses. | ready |
| HAR09 | A | Reconcile all ordered case-1 public-UI results with worker markers, requiring exactly one successful serial logout between dismissed GDM and returned GDM. Read existing evidence; perform no guest action. | `controller_qualification.matched_screens`; [controller reconciliation regressions](../../tests/unit/test_e2e_controller_qualification_cleanup_safety.py). | ready |
| HAR10 | A | Validate the complete expected stage sequence, actual worker module success and verified shutdown result before terminal assertions. Zero exit alone is insufficient. | `controller_qualification.validate_stages(directory, observations)` is the existing pre-shutdown callback; `validate_completion(directory, observations, worker)` repeats complete stage/module validation and requires verified shutdown before reconciliation. | ready |

HAR03(boot) brackets acknowledged stages exactly as the current callback does;
every value must equal the first boot. Persist observations and any phase change
before a reply permits further input. This recorder middleware is common to the
blocks, not a hidden second customer operation. Asset receipt, worker ownership,
evidence collection and outer restoration remain the existing attempt envelope.

### Desktop and retained-session entry

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| DESK01 | C | Observe a usable desktop for the explicitly selected fixture; require its normal Shell controls. | `AccessibleUI.desktop_result(account, 'success')` through the fixed Parent public-bus route. No retained-session or other-account generalization is claimed. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| DESK02 | C | Open the desktop's system/session menu and observe its available actions. | DESK01 → UI01 → UI04 → UI01. | pending |
| DESK03 | C | Choose Switch User, preserving the existing desktop, and observe GDM. | DESK02 → UI04 → GDM01. | pending |
| DESK04 | C | Log out through the normal session controls, including the declared confirmation, and observe GDM. | DESK02 → UI04 → optional UI04(confirm) → GDM01. | pending |
| DESK05 | C | Lock using the normal customer control and observe the lock surface. Only for explicit lock/visibility journeys, never to manufacture natural expiry. | DESK02 → UI04 → UI01 → UI11. | pending |
| DESK06 | C | Observe the intended user's lock challenge. Input declares curtain or already-open challenge; reveal with one normal key only for curtain. | UI05 only for curtain → UI01 → UI02(identity and password challenge). Never submit an empty challenge to reveal it. | pending |
| DESK07 | A | Qualify the lock-screen recipient, masked empty focused field and intended identity independently of GDM. | New public-UI recipient adapter; reuse secret-boundary rules, not GDM evidence. | pending |
| DESK08 | C | Attempt normal unlock with an explicit expected success or time-limit denial. | DESK06 → DESK07 twice → UI19 → UI05(Enter) → GDM06. | pending |
| DESK09 | C | From another usable desktop, visit a specified retained user's desktop without replacing it. Inputs include target account and expected unlock result. | DESK03 → GDM02(destination=lock) → DESK08. Fresh entry explicitly uses DESK03 → GDM07 instead. | pending |
| DESK10 | C | Bring a named already-open window to the foreground through the normal app switcher and independently verify the intended active window. | Bounded UI05 navigation → UI01 → UI02. No direct focus API or assumption that the last app is still active. | pending |
| DESK11 | C | From a recognized lock/rejected sign-in screen, return to the account list using that surface's normal Switch User, Cancel or Back action. Require the declared source; never try several routes after failure. | UI01 → UI04 or UI05 for the registered source route → GDM01. Reused after expiry, rejection and kiosk replacement. | pending |
| DESK12 | C | Expose a named Shell panel control from a previously observed unlocked desktop, including fullscreen gameplay. Input declares already-showing or a qualified normal reveal sequence. | UI05 for reveal when declared → DESK01 → UI01 → UI02(control). Do not require hidden panel controls before reveal. Qualify fullscreen with E2E-024; no usable route blocks that consumer. | pending |

### App-grid search and Parent launch

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| SEARCH01 | C | Open the app grid/Overview with Super-A and observe an enabled, editable, empty search field. | DESK01 → UI05 → UI01 → UI02 → UI03. | pending |
| SEARCH03 | C | Enter an app-name query into an already open, empty, focused search field without launching: type the first character, read it, type the remainder once, read the exact full query. | UI06 → UI03 → UI06 → UI03. Extract the case-5 sequence; no retyping after uncertainty. | pending |
| SEARCH04 | C | Observe the declared search result: a launchable named app, or the exact query-specific web suggestion with stable absence of the app launcher and management window. | `AccessibleUI.launchable_result(PRODUCT)` observes the registered Parent result through `labelled_button`. Only the launchable branch is extracted; case 5's stable unavailable branch remains pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| SEARCH06 | C | Preserve the established whole-query Shell route: open Overview, type the registered app name once, then observe its launchable result. Stop before Enter. It makes no first-character/focus/readback claim. | `onpc_parent::search_whole_query(journey, desktop, PRODUCT, 'app-grid')` consumes the explicit fresh desktop reply, sends Super-A, types the registered query once and observes SEARCH04 before Enter. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| SEARCH05 | C | Launch a named app from the app grid and observe its expected opening window. The search route is an explicit argument. | `onpc_parent::open_management(journey, desktop, 'whole-query')` calls SEARCH06, consumes its fresh result, sends Enter and independently observes `ui:parent-window`. Only Parent/whole-query/new-window is qualified. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| PARENT01 | C | Launch Parent from an administrator desktop and observe its management window. No child is selected implicitly. | `onpc_parent::open_management` uses the separate `parent-window` checkpoint before any picker input. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| PARENT02 | C | Select a child from Parent's dropdown, verify the intended selected identity and wait for that child's controls. | `onpc_parent::select_child` accepts an explicit opened-list reply and registered child/stage binding, uses UI14, consumes fresh highlight evidence, sends Enter and observes `AccessibleUI.selected_child`. Existing/new/returned child bindings only. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| PARENT03 | C | Read the current selected child's identity, screen-limit switch, allowance and remaining-time section as a sanitized observation. Do not change selection; disabled allowance controls remain readable. | `AccessibleUI.settings(child)` reads the explicit child, switch and duration-label projection and reveals the remaining-time section. Scenario expectations remain in `parent_discovery.PLAN`, not the adapter. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| PARENT04 | C | Select Screen Limits or App Limits and require that page's named usable controls. | `AccessibleUI.parent_page(child, page)` checks the displayed child, selects one named page, then observes its controls. Reacquire the window after transition and reuse that local root for search/filter reads. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| PARENT05 | C | Open the daily-allowance picker and, when requested, its Custom amount editor. | UI01 → UI04 → optional UI04(Custom amount) → UI01. | pending |
| PARENT06 | C | Choose a daily preset or type a custom allowance and commit through the normal UI. Return the displayed value/validation; saving is observed separately. | Preset: PARENT05(picker) → UI04(preset) → UI03. Custom: PARENT05(custom editor) → UI16(value) → UI05(commit) → UI03(value/validation). | pending |
| PARENT08 | C | Observe loading, saving, saved, validation or unavailable state and availability of conflicting controls. Snapshot mode waits for the named result; transition mode surrounds the triggering input with a bounded trace. | Snapshot: UI01 → UI02 → UI03 → UI10. Transition: UI22 with those projections; caller supplies the input block between observer readiness and collection. E2E-005 needs this for transient saving. | pending |
| PARENT09 | C | Read the selected child's remaining-time explanation, expanding it only if currently collapsed. Return displayed daily, one-time and total values with formatting/rounding bounds. | UI01 → UI02(expanded) → UI04 only if collapsed → UI09 → UI03. Compare visible explanations, never stored time; repeated reads must not collapse the section. | pending |
| PARENT12 | C | Read a displayed app row's identity, access choice and match choice. | UI01 → UI02 → UI03. No installed-catalogue or executable probe. | pending |
| PARENT10 | C | Search the App Limits catalogue by name and observe the matching displayed rows, including an explicitly expected empty set. | PARENT04(App Limits) → UI16(search) → UI13(rows) → UI12(expected set). Row details use PARENT12 separately. | pending |
| PARENT11 | C | Set one named App Limits filter's explicit selection set and observe the exact displayed result set. Both access-rule and match-rule popovers use independently checked options. | UI01 → UI04(open) → UI17 for each declared option → UI05(Escape) → UI11(popover) → UI13(rows) → UI12(expected set). Same implementation for both filters. | pending |
| PARENT13 | C | Open a named app's Edit Match Rule dialog and read its current rule. | UI01 → UI04 → UI01 → UI03. | pending |
| PARENT15 | C | Apply Save, Cancel or Reset to the open match-rule editor. Invalid Save keeps the editor open; Cancel preserves the supplied earlier rule; Reset follows the actual UI's commit behavior. Observe validation or the resulting rule. | UI04(response) → PARENT08; closed editor then UI11 → PARENT12 → UI12, or invalid draft then UI03 → UI02. For an absent app use the declared deferred-row branch and later reinstall/observation, not an impossible row lookup. | pending |
| PARENT16 | C | Choose Allowed, Hard blocked or Soft blocked for one displayed app; observe save and displayed choice. | UI15(access choice group) → PARENT08 → PARENT12. | pending |
| PARENT17 | C | Open revocation confirmation and read its target and warning about time, blocked apps and daily allowance. | UI01 → UI04 → UI01 → UI03. | pending |
| PARENT18 | C | Cancel or confirm the open revocation dialog and observe its closure and displayed time/settings. Child effects are checked by later app/access blocks. | UI04 → UI11 → PARENT08 → PARENT03. | pending |
| PARENT19 | C | Observe Parent's no-eligible-child explanation together with the `(None)` picker placeholder. Never activate the disabled picker. | UI01 → UI03 → UI02; extract `parent-empty` without weakening either assertion. | pending |

### Kiosk, child overlay and the shared request form

One shared set of form blocks takes `surface = overlay | kiosk`. Child selection
is fixed/read-only in the overlay and selectable in kiosk. Different destinations
and recipient checks are explicit; duplicate surface-specific implementations
are unnecessary.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| REQUEST01 | C | Enter the dedicated request station from GDM and observe its request form. Use only the documented station/session selection, without a desktop-login shortcut. | GDM02(station) → UI15(session choice, only if offered) → UI01 → UI02. | pending |
| REQUEST02 | C | Open or deliberately reopen the child overlay through its panel entry; observe one usable form and fixed child identity. | DESK12(request entry) → UI04 → UI01 → UI02 → UI13(form count=1). Repetition is deliberate customer input, not retry. | pending |
| REQUEST03 | C | Read a form's child, approver, duration, custom text, soft-app choice, controls and messages; include mute only when available. Require exactly one showing form and the fixed child in overlay. | UI13(form count=1) → UI01 → UI02 → UI03. Return an immutable observation; unavailable mute has no value. Ineligible-choice exclusions use UI13 on each opened list. | pending |
| REQUEST04 | C | Select a named form field: child, approver or duration choice. Observe loaded selection and control availability. Reject child selection on the fixed-child overlay. | UI15(field, value) → REQUEST03. All offered durations are data, not separate blocks. | pending |
| REQUEST05 | C | Type a custom duration, including deliberately invalid text, and observe validation/request availability. | UI16 → REQUEST03. Do not coerce or repair the customer's value. | pending |
| REQUEST06 | C | Set one named request-form toggle (`soft-apps` or `mute`) to an explicit boolean and observe it. The surface and child are explicit. | UI17 → REQUEST03. One implementation for both choices; the mute binding remains blocked by hidden/disabled media controls. | pending |
| REQUEST08 | C | Read the visible estimate/footer for the chosen duration, including rest-of-day meaning, loading or unavailable estimates. | UI01 → UI03. Expected time comes from prior visible observations and elapsed time. | pending |
| REQUEST09 | C | Submit one valid request and observe the actual system authentication prompt. | UI01 → UI04 → UI01. An invalid/disabled request instead uses REQUEST03 and UI11 to prove no prompt; never activate a disabled control. | pending |
| REQUEST10 | C | Double-click an enabled Request control and observe exactly one in-progress prompt/form. | UI01 → UI07 → UI20, surrounded by UI22 tracking registered prompt/form counts and Request availability; UI13 independently confirms final counts. No second approval input or internal exactly-once claim. | pending |
| REQUEST11 | C | Observe success confirmation, rejection, cancellation without an error, or validation feedback, with the explicitly expected preserved choices. | UI01 → UI03 → REQUEST03 where the form remains → UI12. Capture brief success before waiting for automatic exit. | pending |
| REQUEST12 | C | Exit by Cancel, Escape, normal window close, or the already-approved automatic exit. Observe overlay disappearance plus child desktop, or kiosk disappearance plus GDM. No authentication prompt may be active for form Cancel/Escape. | UI04, UI05, UI18, or no input for automatic exit → UI11 → DESK01 or GDM01. | pending |
| AUTH01 | A | Qualify the real approval prompt's selected parent, displayed request/child/duration/app choice and sole empty masked focused field. No password contents or product authorization calls. | New public-UI contract over the actual system agent; preserve the [secret boundary](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary). | pending |
| AUTH02 | C | Approve, enter a declared wrong fixture password, or cancel authentication. For input, freshly qualify the same challenge twice and submit once. Observe acceptance, explicit rejection or dismissal; REQUEST11 separately reads the form result. | AUTH01 twice → UI19 → UI05, or UI04(Cancel) → UI01 → UI03 → UI11 as appropriate. A rejected prompt may need its normal Cancel action to return; never infer denial from timeout. A later retry needs a new challenge. | pending |
| AUTH03 | A | Qualify a visible terminal administrator-authentication recipient for one declared package command, including the selected account and non-echoing input. | Reuse qualified terminal safety machinery only where its contract applies; a generic `Password:` string is insufficient. No policy/result probes. | pending |

### Customer terminal, files and application use

Commands are declared customer commands typed into the guest terminal. They
must not turn into SSH/product probes. Fixture package/path arguments come from
verified prepared assets. Native/Snap/Flatpak and app names are parameters of
these blocks, not copies of them.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| FILE01 | C | Open the normal desktop terminal and observe its usable input surface. | SEARCH05(terminal) → UI01 → UI02. First pending scenario consumer: E2E-004/terminal. | pending |
| FILE02 | C | Submit one declared nonsecret command to an already open terminal. Return after Enter; do not wait for completion or type authentication here. | UI21(terminal input) → UI06(command) → UI05(Enter). Do not Ctrl-A a terminal or accept command echo as output. | pending |
| FILE06 | C | Observe the declared terminal result: real administrator challenge, command completion/notice, or launch-denial output. Read only its bounded approved output projection. Generic prompts, command echo and arbitrary failures are insufficient. | UI01 → UI10 → UI03. A challenge returns control immediately to the caller. First consumers: E2E-004/terminal and customer package operations. | pending |
| FILE07 | C | Navigate an open file manager/chooser to one declared customer directory. Use its normal Location shortcut, enter the directory and observe the destination. | UI05(Location shortcut) → UI16(location field) → UI05(Enter) → UI01 → UI03(destination). Directory identity comes from prepared synthetic fixtures or the selected save location. | pending |
| FILE03 | C | Choose files, save a named file, or cancel in an already open chooser. Mode and selected files are explicit. Observe selection/closure; the caller observes its later result separately. | Open: FILE07(directory) → UI14(first file) → UI05 for declared additional modifier/navigation selection → UI13(exact selected set) → UI04(Open) → UI11(chooser). Save: FILE07 → UI16(filename) → UI04(Save) → UI11. Cancel: UI04(Cancel) → UI11. No unmodified second selection that silently drops earlier files. | pending |
| FILE04 | C | Open the file manager, navigate to a customer directory and observe its declared named entries. | SEARCH05(file manager) → FILE07(directory) → UI13(entries). | pending |
| FILE05 | C | Copy or rename one fixture file through normal file-manager input and observe the resulting entry. Explicit inputs include source, destination/name and expected entry set. | UI01 → UI07 → UI08 → UI02(selected). Copy: UI05(Copy) → FILE07(destination) → UI05(Paste). Rename: UI05(Rename) → UI16(name) → UI04(confirm). Both: UI13(entries) → UI12. | pending |
| APP01 | C | Attempt a launch by the declared route without waiting for its result. A hidden launcher is a distinct observation, not an execution attempt. | Grid: SEARCH01 → UI21 → SEARCH03 → SEARCH04 → UI05 only if the expected launcher is offered. Desktop: UI01 → UI04. File: FILE04 → UI04. Terminal: FILE01 → FILE02. No silent route substitution. | pending |
| APP02 | C | Observe exactly the expected usable window, named launch denial, hidden launcher, or closure of a previously observed window. Inputs include route, result and earlier window observation when required. | UI01 → UI03 for presence; FILE06 for terminal denial; UI11 for hidden/closed surface with a recognized surrounding UI. Hidden launcher alone cannot prove blocked execution. | pending |
| APP03 | C | Perform one declared normal app input and observe its customer-visible effect, proving usability. Repeated game actions are separate bounded invocations. | UI01 → one of UI04, UI05 or UI06 according to the declared input mode → UI03 or UI02 according to the declared result projection. App action/expected effect is fixture data. | pending |
| APP04 | C | Read a recognizable public activity/window state, or compare it after legitimate return. Inputs declare capture/compare and the earlier immutable observation. | APP02(present) → UI03 → UI12 only for compare. A newly launched window cannot satisfy retained-activity expectations. No hidden process/window inspection. | pending |
| APP05 | C | Choose the real offline game's offered windowed/fullscreen mode and reproducible level, then observe active gameplay. | UI15(mode/level) → APP03(start) → UI01 → UI03. The selected game needs usable public observations; a menu or timer fixture is insufficient. | pending |

### Time and ordinary lifecycle boundaries

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| TIME01 | C | Read the displayed countdown or require its stable absence on a specified desktop, lock or GDM surface. | UI01 → UI03, or UI11 with the destination positively identified. | pending |
| TIME02 | C | Observe minute ticks/final seconds over real monotonic intervals; compare actual displayed values and formatting with explicit tolerances. | TIME01 → UI10 → TIME01 → UI12. No guest clock/usage manipulation. | pending |
| TIME03 | A | Let a declared bounded real interval elapse while retaining the runner guard and deadline. Return elapsed time only; this does not prove a lock or grant expiry. | Extract a guarded monotonic wait with finite progress checkpoints for E2E-010/022. | pending |
| TIME04 | C | Use the selected app/game until natural expiry, then observe the lock owning normal input and loss of desktop access. Earlier visible time and the timeout are explicit inputs. | Bounded APP03 → TIME03 repetitions, with TIME02 only while the countdown is showing → UI01(lock) → UI05(harmless normal input) → UI01(lock challenge)/UI02. Do not require a visible countdown during fullscreen play or inspect the game underneath the lock. | pending |
| LIFE01 | C | Close and reopen one named ordinary app through its normal launcher; observe its opening window. Do not reselect a child or restore settings before reading them. | UI18 → SEARCH05. Caller reads/compares the relevant fields afterward. Overlay/kiosk reopening uses their explicit exit/entry blocks. | pending |
| LIFE02 | C | Reboot through the desktop's normal controls and confirmation, then observe fresh GDM. Retain one continuous attempt. | DESK02 → UI04 → optional UI04(confirm) → GDM01. Requires the scoped boot-transition recorder extension below. | pending |
| LIFE03 | C | Suspend through customer controls, wait the declared real interval, wake through supported normal input and observe the actual return surface. | DESK02 → UI04 → TIME03 → UI05(wake) → UI01; subsequent unlock remains DESK08. | pending |
| LIFE04 | C | Perform one declared install/update/remove/reinstall/purge through a visible administrator terminal. Submit once, observe challenge or completion, authenticate only if challenged, then observe completion and final notice. | FILE01 → FILE02 → FILE06(challenge or completion); challenge branch: AUTH03 twice → UI19 → UI05 → FILE06(completion/notice). Package, command, notice and permitted prompts are explicit data. No completion wait before servicing authentication. | pending |
| LIFE05 | C | Follow the displayed activation requirement for the explicit finite list of affected apps/users: none, process reopen, session renewal, or reboot/login. | None: UI03(notice). Process: LIFE01 for each app. Session: DESK03 → GDM02 → DESK08 when reaching another retained user, then DESK04 → GDM07 for each required renewal. Reboot: LIFE02 → GDM07. Compare displayed state afterward; one user's logout does not renew every session. | pending |
| LIFE06 | C | Change connectivity through the customer's ordinary network UI and observe its displayed state. Only for an explicitly reconciled customer-reproducible feedback case. | DESK02 → UI04(network controls) → UI17 → UI02. No injected transport/provider fault. | pending |

### About, feedback and customer-selected attachments

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| ABOUT01 | C | Open Parent's app menu and About; read product/version and reach the license link. | UI01 → UI04(menu) → UI04(About) → UI01 → UI03 → UI09. Extract the `about` checkpoint. | pending |
| ABOUT02 | C | Follow the license link to the actual viewer and read the identifying license content. | UI04(link) → UI01(viewer) → UI03. Extract `license`; link existence alone is insufficient. | pending |
| ABOUT04 | C | Reach and read the About footer in the already open About window. Bind the existing case-151 Tab/End navigation explicitly when preserving that worker. | Declared UI05(Tab) → UI05(End), then UI09 → UI03(footer). Other consumers may declare no preliminary keys when the public scroll route suffices. | pending |
| ABOUT03 | C | Close the license, read the About footer, close About and compare the selected child/settings with the supplied earlier observation. | UI18(license) → ABOUT04 → UI18(About) → PARENT03 → UI12. Reacquire each window; do not reselect the child before comparison. | pending |
| FEED01 | C | Open Parent feedback and observe the editor and diagnostic-collection state. | UI01 → UI04(feedback entry) → UI01 → UI02 → UI03. | pending |
| FEED03 | C | Read the visible synthetic draft, exact attachment list and validation/control state into an explicit observation. | UI01 → UI02 → UI03 → UI13(attachments). Only the declared synthetic content is eligible for comparison. | pending |
| FEED04 | C | Apply one offered rich-text format to an explicit synthetic range and observe its public text attributes. Select the range through normal keyboard input, then use its toolbar/menu. | UI21(editor) → UI05 for bounded declared selection → UI04 or UI15(format) → UI24. No DOM bridge or direct text/selection assignment. | pending |
| FEED05 | C | Open Privacy, read the disclosure/diagnostic explanation, then close it. | UI04 → UI09 → UI03 → UI18. | pending |
| FEED06 | C | Add prepared synthetic attachments through Add files and the actual file chooser, then observe the displayed list or validation. | UI04 → FILE03 → FEED03. Repeat finite fixture values for the declared attachment-count and size validation. | pending |
| FEED07 | C | Read one attachment's displayed synthetic name/size and list position. Does not preview or remove it. | UI01 → UI03. | pending |
| FEED12 | C | Open an offered attachment preview, read declared synthetic contents and close it, returning to feedback. | UI01 → UI04 → UI03 → UI18. An unoffered preview does not authorize private storage inspection. | pending |
| FEED13 | C | Remove one explicitly identified attachment and observe the remaining list. | UI01 → UI04(Remove) → FEED03 → UI12(expected list). | pending |
| FEED08 | C | Explicitly save diagnostic output to a customer-selected location, open that saved output through the file manager/viewer and read the expected public contents. | UI04(download) → FILE03(save) → FILE04 → UI04(open) → UI03. Do not inspect original product logs or storage. | pending |
| FEED09 | C | Observe collection, validation, sending, retry, error or thank-you state and control availability. Snapshot mode reads the current state; transition mode records required transient states around FEED01 or FEED11. | UI01 → UI02 → UI03 → UI10, or UI22 with the same projections. No provider receipt or delivery-internal assertion. | pending |
| FEED10 | C | Close/reopen feedback and compare its in-memory draft. `dialog` preserves the supplied draft; `app-exit` explicitly closes/relaunches Parent and expects reset. Return with feedback open. | FEED03(before) → UI18(feedback) → LIFE01(Parent) only for app-exit → FEED01 → FEED03 → UI12(expected draft). Do not edit fields before comparison. | pending |
| FEED11 | C | Submit one already reviewed synthetic report. Require explicit sending authorization and dedicated test-recipient configuration; activate Send once and return. Observe the outcome and dismiss confirmation separately. | UI01 → UI02(enabled) → UI04(Send). Prior FEED03 → FEED05 evidence is supplied, not repeated inside this block. This document grants no sending authorization. | pending |
| FEED14 | C | Dismiss an observed success confirmation normally and observe the expected return surface. | UI01 → UI04(Close) → UI11(confirmation) → UI01(return surface). FEED09 supplies the earlier success observation. | pending |

### Reusable journey fragments

These fragments do not own fixture provisioning, attempt startup or cleanup.
Arguments include expected results and the exact accounts/apps/choices. No
fragment skips an unsuccessful step or resumes a previous attempt.

| ID | Kind | Block and explicit contract | Callees, in order | Status |
| --- | --- | --- | --- | --- |
| FLOW00 | C | Run case 1's complete graphical/serial qualification within the unchanged harness envelope. Its step boundaries and terminal assertions are fixed below. | `onpc_flow00::run(journey, exchange)` calls HAR01 → GDM02 → GDM09 and its `serial(exchange)` fragment calls HAR05 → HAR06 → HAR07 → HAR08 within `onpc_serial::attempt`. Normal finish/shutdown stays in `smoke.pm`; `controller_qualification.execute` then calls HAR10 → HAR09 with unchanged evidence/phase middleware. | ready |
| FLOW15 | C | Reach an explicit user's desktop from the declared source surface. `entry=fresh` requires no retained session; `retained` requires an earlier observed desktop; `same` requires the current user already matches. Return the observed desktop or expected time-limit denial. | `onpc_parent::enter_desktop(journey, 'gdm', 'parent', 'fresh', 'success')` calls GDM07. Only this explicit route is ready; retained, same-user, lock and denial routes remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| FLOW01 | C | Open or return to Parent for a named child and record displayed settings. Inputs declare source, parent entry and `window=new` or `retained`. Default first entry is GDM/fresh/new; a return uses retained entry and the existing window. | `onpc_parent::open_for_child(journey, 'gdm', 'fresh', 'new', 'existing')` calls FLOW15, PARENT01 and PARENT02/PARENT03. Setup reattachment stays in the worker envelope. Retained-window and remembered-selection routes remain pending. [Case-3 qualification](#case-3-refactor-qualification). | ready |
| FLOW02 | C | Configure the selected child's time controls, observing save and explanation. Inputs declare initial/final enablement and allowance. Enable first only when needed to make the allowance editor usable. | UI17(Screen time limit=true) if required → PARENT06 → PARENT08 → UI17(final boolean) → PARENT08 → PARENT03 → PARENT09. Disabling clears a grant; this is not a harmless navigation step. | pending |
| FLOW03 | C | Configure one app's matching and access choices through Parent and read the saved row. | PARENT10 → PARENT11 if declared → PARENT13 → UI16(match draft) → PARENT15(save) → PARENT16 → PARENT12. | pending |
| FLOW04 | C | Open the selected request surface and choose child/approver/duration/app access; read the estimate. | REQUEST01 or REQUEST02 → REQUEST03 → REQUEST04(child only in kiosk, approver, duration) → REQUEST05 if custom → REQUEST06 → REQUEST08. | pending |
| FLOW05 | C | Complete a real approval from a prepared form, observe confirmation and its surface-specific automatic exit. | REQUEST09 → AUTH02(correct credential) → REQUEST11(success) → REQUEST12(automatic). | pending |
| FLOW06 | C | Obtain time through kiosk from an existing GDM screen and return to GDM. | FLOW04(kiosk) → FLOW05. Child login/unlock is deliberately a later step. | pending |
| FLOW07 | C | Reject/cancel one request and compare its preserved choices. Return with that form open; do not retry yet. | REQUEST03(before) → REQUEST09 → AUTH02(wrong/cancel) → REQUEST11 → UI12. The recipe can inspect restrictions before invoking FLOW05 for a successful retry, avoiding a second implementation of approval. | pending |
| FLOW08 | C | Exercise an app through its declared route and prove the expected usable/denied result. | APP01 → APP02 → APP03 only for expected usable access. | pending |
| FLOW09 | C | Visit an explicitly retained user and prove the same app/activity remains usable. Inputs include source surface and that user's earlier activity observation. | FLOW15(entry=retained) → APP04(compare) → APP03. | pending |
| FLOW10 | C | Launch the prepared real game, select mode/level and play to natural lock. | FLOW08(game, usable) → APP05 → APP04(record activity) → TIME04. | pending |
| FLOW11 | C | After a displayed lock, obtain legitimate replacement time, unlock and observe the expected retained app or closed blocked app. | DESK11 → FLOW06 → FLOW15(child, retained) → APP02 → APP04(compare) → APP03 when preservation is expected. Closed-app branch ends at APP02. | pending |
| FLOW12 | C | From an open request form, visit the other surface for that child and compare remembered choices before any edit. Mute expectations are independently supplied per surface. Return with the second form open. | Overlay→kiosk: REQUEST12(cancel) → DESK03 → REQUEST01. Kiosk→overlay: REQUEST12(cancel) → FLOW15(child, declared fresh/retained entry) → REQUEST02. Both then REQUEST03 → UI12(shared fields and separate mute). | pending |
| FLOW13 | C | Establish a named time profile entirely through customer controls and finish at GDM. Entry/window arguments are explicit. Verify no grant or revoke it first; use the profile table below. | FLOW01 → PARENT09 → PARENT17 → PARENT18(confirm) only if revocation is declared → PARENT09 → UI12(no grant) → FLOW02(initial allowance) → DESK03. Grant profiles then FLOW06 → FLOW01(parent/window retained); daily-dominant adds PARENT06(larger allowance, still enabled) → PARENT08. All grant profiles finish PARENT09 → UI12(profile) → DESK03. | pending |
| FLOW14 | C | Open apps/recognizable activities for a finite declared user list, retaining each desktop through Switch User. Inputs state each user's fresh/retained entry and usable-time/policy prerequisites. Start and finish at GDM. | For each user: FLOW15 → FLOW08 → APP04(capture) → DESK03. Earlier retained desktops must be revisited, not recreated. Multiple desktops for one identity require a supported customer route; see applicability notes. | pending |


### Canonical reuse and implementation checkpoints

The former duplicate wrappers are retired identifiers, not pending work:

| Former ID | Canonical block | Binding |
| --- | --- | --- |
| SEARCH02 | UI21 | Overview search field |
| PARENT07 | UI17 | Parent's Screen time limit switch |
| PARENT14 | UI16 | Open match-rule draft field; do not Save |
| FEED02 | UI16 | Synthetic feedback body or reply field |
| REQUEST07 | REQUEST06 | `toggle=mute`, explicit surface; feature availability still required |

The split operations intentionally have separate checkpoints: UI23 scrolls and
UI09 observes reachability; GDM08 observes a prompt, GDM03 qualifies a secret
recipient and GDM09 dismisses; HAR05/06/07/08 separate serial login, command,
logout and return; FILE02 submits
and FILE06 observes; FEED07 reads an attachment, FEED12 previews and FEED13
removes; FEED11 submits and FEED09 observes before FEED14 dismisses success.
Recipes own the order. This prevents a completion wait from blocking required
authentication, and prevents reopening, editing or a second Send from hiding
the state a scenario is supposed to inspect. FLOW07 now ends after rejection;
FLOW05 owns the later approval. REQUEST06 parameterizes both request toggles.

Every invocation binds `surface/account`, registered `target`, input values,
expected output, deadline and immutable prior observations. It returns a fresh
semantic result plus its declared destination. A composite may perform pure
argument selection/comparison and finite control flow; all UI/secret/fixture
I/O must come from its listed callees. Row order, rather than ID number, is the
implementation order; added IDs keep old references stable.

For required transient states, write `watch(observer) { action }`: start UI22,
wait for its readiness acknowledgement, perform the action once, then collect
the trace. The observer must be able to see public UI events during input;
post-action polling cannot establish that Saving appeared or a button was
inhibited. Missing samples fail that assertion. This needs a scoped extension
of the existing guarded rendezvous with E2E-005, not another runner.

A row becomes `ready` only when its implemented projection/selector scope is
explicit, source callable and meaningful qualification are recorded, and its
first installed consumer passes. Ready primitives above refer to existing
[public-UI regressions](../../tests/unit/test_accessible_e2e_ui.py),
[real adapter checks](../../tests/ui/test_e2e_accessible_adapter.py),
[actual pointer](../../tests/unit/test_e2e_pointer_helper.py) and
[worker checks](../../tests/unit/test_parent_access_worker.py), with existing
case results in retained runner artifacts.
They do not claim qualification for future kiosk, lock, terminal or game
selectors. Add those with their first consuming block. A later extension of an
already-ready primitive leaves its established scope ready and the new consumer
pending; do not silently broaden what the status means.

## Fixture boundaries and the common attempt envelope

These supporting operations are the only fixture exceptions to customer input.
They prepare unrelated accounts/assets, never the policy, time balance,
authentication outcome or app behavior being tested.

| ID | Kind | Supporting operation and boundary | Existing source | Status |
| --- | --- | --- | --- | --- |
| FIX04 | A | Transfer the existing verified asset manifest to the powered-off guarded guest before the attempt. No asset installation or arbitrary bundle interface. | `AssetTransfer.provision` in [asset_transfer.py](../../tests/e2e/asset_transfer.py); [transfer safety](../../tests/unit/test_e2e_asset_transfer_cleanup_safety.py), case 1 qualification. New game/Snap/Flatpak/attachment profiles still need preparation with their consumers. | ready |
| FIX03 | A | Prepare one declared account-eligibility profile before a kiosk journey: multiple, no child, no approver or ineligible approver. Do not generalize FIX02 into arbitrary account mutation. | Extend the supported fixture route only for E2E-017's named profile and its cleanup. | pending |
| FIX01 | A | Create one eligible account at the declared durable checkpoint while Parent stays open. Customer acceptance requires later visible discovery/selection. | `DynamicAccountFixture.create` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX02 | A | Make the exact two canonical eligible child fixtures ineligible at the declared checkpoint before Parent launches; preserve the request station. Unexpected account sets refuse. | `EmptyAccountFixture.prepare` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |

Every recipe below has the same surrounding phases, already present in all 33
inventory declarations:

1. **Setup:** existing guarded baseline/account/credential/assets preparation;
   verified installed setup for ordinary feature cases. Use FIX04 for available
   unrelated assets and FIX03 only where declared. Case 1 starts product-free and
   retains offline stock-getty/credential preparation and the existing asset
   receipt. E2E-002/027 start product-free because installation itself is a
   customer action. Case 3's FIX01 and case 4's FIX02 retain their explicit
   in-journey positions; they belong to independent attempts, not one sequence.
2. **Start:** the existing recorder begins one attempt and binds its inputs.
   Customer blocks receive that context explicitly. There is no state resume.
3. **Steps:** execute the ordered recipe, including fresh visible observations
   after inputs. `1:`, `2:` below correspond to inventory `step-1`, `step-2`, etc.
4. **End:** reconcile all declared actions/observations and retain the original
   failure and existing private evidence.
5. **Cleanup:** existing owned worker shutdown, baseline restoration and
   host/source preservation, including failure paths. Never reset the VM inside
   a recipe. These safeguards do not assert the app's inner workings.

Reuse [InstalledSetup](../../tests/e2e/installed_setup.py),
[InstalledJourney / record_installed_journey](../../tests/e2e/installed_journey.py)
and the existing outer [execution](../../tests/e2e/execution.py) / [leased
recording](../../tests/e2e/leased_recording.py) services. They are the retained
runtime envelope, not replacement infrastructure to implement ahead of a
customer block. See the [migration constraints](#refactoring-the-established-cases)
before adding repeated authentication or a customer reboot.

## Complete scenario decomposition

Every listed numeric case is accounted for below. A range includes every
existing variant in that range; Cartesian products use exactly the named
inventory values, without adding combinations. The recipes are planned
composites, not runnable code or newly earned coverage. Repeated values use the
same blocks with distinct recorded invocations and expected observations.

Notation expands to catalogue calls; it adds no implementation:

- `P0` = FLOW01 from GDM, parent fresh, new Parent window, named child.
- `P` = FLOW01 from the explicitly recorded current surface, retained parent
  desktop and retained Parent window, named child. After logout/reboot, use P0
  or explicitly declare a fresh parent/new window.
- `V(user, fresh|retained|same, result)` = FLOW15 with that entry and expected
  result (success unless shown). Source is the previous block's observed
  destination, passed explicitly. Never guess whether a session exists.
- `repeat(values) { ... }` runs every finite listed value in order, with fresh
  invocation IDs and observations. `watch(observer) { action }` uses UI22's
  readiness/input/collection order.
- Arrows mean sequence. Alternatives use `or` and their selecting argument.
  A result claim names a fresh observation; hidden setup supplies no input.
- An unqualified REQUEST06 call binds `toggle=soft-apps`; mute is always named
  explicitly. SEARCH05/Parent launch bind `whole-query` for cases 3, 4 and 151;
  case 5 keeps its explicit focus/first-character/readback sequence.

Preconditions in a row are mandatory recipe prefixes, not fixtures that set
product policy. For each claimed continuing other-user activity, start at GDM
with FLOW14 for the finite named users. If Parent's desktop exists but its
management window does not, first use FLOW01(parent retained, window=new);
P is valid only after both have been observed. Return with FLOW09 for each same
observation after the change. Do not add user permutations
where the scenario has no isolation claim. Do not append an internal
"other-user unchanged" assertion. No continuation across logout/reboot is
claimed for windows; after those boundaries, launch and use the app anew.

Each recipe binds a current-surface/session ledger from its own observations:
which fixture desktops exist, which windows/forms remain open, and which are
active. Before a block requiring another surface, insert the declared route
already in the catalogue: V for user entry, DESK10 for an existing window,
DESK03/DESK11 for GDM, PARENT04 for a Parent page. Spell out these calls in the
implementation plan; adapters must not repair missing preconditions themselves.
Every close/approval/reboot updates the ledger. Read remembered values before
any selection/edit that could conceal a persistence defect. A range of case IDs
is recipe reuse with every original parameter binding, never sampling.

### Parent, login and time scenarios

| Family / cases / variant parameters | Ordered recipe and visible finish line |
| --- | --- |
| E2E-001 / **1** / `gdm-observation` | **Harness qualification, no customer credit.** FLOW00 inside the unchanged setup/start/end/cleanup envelope. 1: HAR01(sut) → GDM02(parent, prompt) → GDM09. 2: HAR05(serial login) → HAR06(harmless command) → HAR07(logout). 3: HAR08(fresh graphics); after worker finish/shutdown, HAR10 → HAR09 and all three existing terminal assertions. The [stage contract](#case-1-stage-contract) fixes every acknowledgement and phase boundary. |
| E2E-002 / **2** / `clean` | 1: GDM07(administrator, fresh success) → LIFE04(install), reading actual completion and final reboot-required notice. 2: LIFE02. 3: GDM01 → V(administrator, fresh) → DESK01. Product absence/package identity/startup ordering remain separate package/system qualification; usable GDM does not prove them. |
| E2E-003 / **3** / `existing-and-new` | 1: FLOW01(existing child, functional login, whole-query search) → PARENT04(App Limits), checking search and both filters; retain the initial limits-off/zero-minute observation. 2: PARENT04(Screen Limits) → PARENT03 → FIX01 while Parent stays open → UI01(picker) → UI04(open) → UI13(new child). 3: UI14(new child) → UI05(Enter) → PARENT03 → PARENT04(App Limits) → PARENT04(Screen Limits) → PARENT03 → UI12(new child's own earlier values) → PARENT02(original child) → PARENT03 → UI12(original values). No time-policy change. |
| E2E-003 / **4** / `none` | 1: GDM07(parent) → SEARCH06(Parent, whole query), stopping at the fresh launchable result before Enter. 2: FIX02 at the durable boundary, with a fresh SEARCH04(launchable) observation as in the existing fixture-requested checkpoint. 3: UI05(Enter) → PARENT19. The showing explanation and `(None)` picker must both be observed. |
| E2E-004 / **5–6** / `app-grid`, `terminal` | 1: GDM07(standard user) → SEARCH01 for grid, or FILE01 for terminal. 2: grid: UI21 → SEARCH03 → SEARCH04(unavailable), preserving full query, web-only suggestion and stable absence; never Enter. Terminal: FILE02(Parent executable) → FILE06(expected management-denial output) → UI11(management window). No alternate-user state probe. |
| E2E-005 / **7–12** / `{daily-only, grant-only, combined}` × `{new, retained}` | 1–2: P0 → FLOW02(enabled) → repeat(daily validation set below) { watch(PARENT08) { PARENT06(value) } → PARENT03 → PARENT09 }; after invalid input reopen the picker and UI12(last accepted value). Set the profile allowance → UI17(false) → PARENT08. Retained variant now V(child, fresh) → FLOW08 → APP04(capture) → P. 3–4: execute the finite transition plan below: enable, change allowance while enabled, disable, re-enable. Each action uses watch(PARENT08), then PARENT03 → PARENT09, V(child, variant entry, expected result), and FLOW08 when admitted. After each successful visit use DESK04 for new-session variants or DESK03 for retained; denied entry uses DESK11. Return via P. Grant-only/combined explicitly use DESK03 → FLOW06 → P after the enable check and before allowance edits. Reconcile the pending phase declaration to this reachable order; an already-enabled no-op earns no enable-transition credit. |
| E2E-006 / **13–16** / `{enabled, disabled}` × `{precise, pattern}` | Prerequisite: permissive policy/usable child time, then FLOW14(child and named other-user apps). 1: P → UI17(control) → PARENT10 → PARENT11 → PARENT13 → UI16(match draft) → PARENT15(save). 2–3: repeat(Allowed, Hard blocked, Soft blocked) { P → PARENT16 → V(child, retained) → APP02(existing window result) → FLOW08(matching/nonmatching targets) → FLOW09(each other user's activity) }. Reopen test apps normally under a permissive rule before any later transition whose assertion requires an already-open app. |
| E2E-007 / **17–20** / `{zero, remaining}` daily × `{single, multiple}` retained sessions | 1: FLOW13(real grant plus selected daily time) → FLOW14(child and other-user activities) → P. 2: PARENT03(before) → PARENT17 → PARENT18(cancel) → UI12(unchanged settings/time allowing elapsed time) → FLOW09(child and other users). 3: P → PARENT17 → PARENT18(confirm) → PARENT09. With daily time remaining, V(each supported child desktop, retained) → APP02(blocked windows closed) → FLOW08. With zero time, V(child, retained, time-limit denial) → DESK11; no invisible closure claim. FLOW09(other users). Multiple-same-child applicability is below. |
| E2E-008 / **21** / `retained-unlock` | 1: FLOW13(short daily-only) → V(child, fresh) → FLOW08(usable app). 2: TIME04 natural exhaustion. 3: DESK08(correct password, time-limit denial). No Lock input creates expiry. |
| E2E-008 / **22** / `fresh-login` | 1–2: FLOW13(short daily-only) → V(child, fresh) → FLOW08 → TIME04, preserving actual natural exhaustion. 3: DESK08(time-limit denial) → DESK11 → FLOW06(temporary legitimate time) → V(child, retained) → DESK04(normal logout) → P → PARENT17 → PARENT18(confirm removal of temporary grant) → PARENT09 → UI12(daily exhausted, no grant) → DESK03 → GDM07(child, fresh time-limit denial). The explicit temporary grant permits normal logout; it does not replace natural expiry or change daily allowance. Reconcile these additional public steps before registration. If normal logout is available directly on the qualified lock surface, document that supported route instead; never silently substitute configured-zero denial. |
| E2E-009 / **23–24** / soft apps `{excluded, included}` | 1: FLOW13(grant-only, selected soft app initially usable) → V(child, fresh) → FLOW08 → APP04(capture). 2: TIME04. 3: FLOW11(replacement with variant soft choice) → FLOW08(hard/soft expectations). Legitimate unlock provides the retained-activity observation point. |
| E2E-010 / **25–26** / foreground `{parent, other-child}` | 1: FLOW13(short grant) → V(child, fresh) → TIME01 → V(foreground user, retained for parent or fresh for other-child) → FLOW08 → APP04(capture). 2: bounded APP03 and TIME03 repetitions past the earlier displayed interval prove continued foreground use. 3: V(child, retained, time-limit denial). No hidden-session observer. |
| E2E-011 / **27–29** / `{daily-only, grant-only, combined}` | 1: FLOW13(profile) → V(child, fresh). 2: TIME02 over minutes and final seconds. 3: DESK05 → TIME01(absent on lock); DESK08(success while time remains) → TIME01(refreshed); DESK03 → TIME01(absent at GDM); V(other user, declared entry) → TIME01(absent). Budget the final-second round trip before expiry, or explicitly use DESK11 → FLOW06 → V(child, retained) for a later return; never assume expired time permits unlock. |

### Request forms and remembered choices

| Family / cases / variant parameters | Ordered recipe and visible finish line |
| --- | --- |
| E2E-012 / **30–33** / soft apps `{excluded, included}` × approver `{first, second}` | 1: establish usable time, soft-app exception and open activities with FLOW13 → FLOW14; V(child, retained) → REQUEST02 twice → REQUEST03(one form, fixed child). 2: REQUEST04(approver/duration) → REQUEST06 → REQUEST08 → REQUEST09 → AUTH01(exact request/parent). 3: AUTH02(correct) → REQUEST11(success) → REQUEST12(automatic) → TIME01 → APP02(existing app) → FLOW08(soft/hard expectations). Reopen with REQUEST02 → REQUEST09 → AUTH01 → AUTH02(cancel) → REQUEST11(cancel) → REQUEST12(cancel), proving later authentication is still required. |
| E2E-013 / **34–37** / `{child-overlay, kiosk}` × `{wrong-password, cancel}` | Prerequisite: enabled target and restricted app; overlay has positive daily time and a FILE01 terminal left open, kiosk has zero daily/no grant. 1–2: FLOW04(surface) → FLOW07(selected rejection/cancellation), with step-2 starting before AUTH02 input. Overlay restriction check: DESK10(terminal) → FILE02(restricted app command) → FILE06(expected denial) → UI11(app window) → DESK10(request form) → REQUEST03 → UI12(preserved choices). Kiosk: REQUEST12(cancel) → V(child, fresh, time-limit denial) → DESK11 → REQUEST01 → REQUEST03 → UI12. 3: FLOW05(new challenge) → child access/use via V if needed and FLOW08. Reconcile explicit kiosk exit/reopen with old same-form wording; no object-continuity claim. |
| E2E-014 / **38–43** / `{child-overlay, kiosk}` × `{predefined, custom, rest-of-day}` | Prerequisite: enabled target and usable overlay time when needed; enter REQUEST01 from GDM or REQUEST02 from child desktop. 1–2: repeat(variant's finite duration values) { REQUEST04 → REQUEST05 if custom → REQUEST03 → REQUEST08 }. Invalid input requires validation/disabled Request and UI11(no prompt). 3: repeat(each declared valid value, reopened and selected again) { REQUEST10 → AUTH01 → AUTH02(correct) → REQUEST11(success) → REQUEST12(automatic) }; observe one prompt and the declared confirmation/time result. Large values need no expiry wait. |
| E2E-015 / **44–49** / `{child-overlay, kiosk}` × `{cancel, escape, approved}` | Prerequisite: APP04 captures child activity for overlay, and FLOW04 starts at the declared GDM/child desktop. 1: FLOW04 changes choices; approved branch REQUEST09 → AUTH02(correct) → REQUEST11(success); Cancel/Escape keeps authentication inactive. 2: REQUEST12(variant exit). Overlay: APP04(compare) → APP03, plus TIME01 after approval. Kiosk: GDM01, then V(child, declared fresh/retained entry) → TIME01 for approved access. Cancellation at zero time does not imply desktop access. |
| E2E-016 / **50–52** / `{approved, denied, cancelled}` | 1: REQUEST01 → REQUEST03; repeat(finite restriction routes below) { UI05 or UI04 for that route → UI11(forbidden surface) → REQUEST03(form usable) }. 2: REQUEST04 → REQUEST05 if custom → REQUEST06 → REQUEST09 → AUTH02(outcome) → REQUEST11. Repeat restriction checks only if the kiosk remains open; observe approved exit immediately. 3: REQUEST12(cancel or automatic, selected by outcome) → GDM01. |
| E2E-017 / **53–57** / `{multiple, no-child, no-parent, ineligible-parent, disabled-child}` | Setup: FIX03 for declared account eligibility; disabled-child instead P0 → UI17(false) → PARENT08 → DESK03. 1: REQUEST01. 2: for each offered child/approver selector, UI01 → UI02(enabled) → UI04(open) → UI13(exact eligible choices) → UI05(Escape) → UI11(popup), then REQUEST04 for every declared available target. Disabled/absent selectors instead use UI02/UI03(explanation), without activation. 3: REQUEST03 → REQUEST08 checks loading/empty/ineligible/disabled explanation and availability. Unavailable Request stays disabled with UI11(no prompt); a valid target uses REQUEST09 → AUTH01 → AUTH02(cancel) → REQUEST11(cancel) to prove reachability. |
| E2E-018 / **58–61** / `{overlay-to-kiosk, kiosk-to-overlay}` × child `{first, second}` | Prerequisite: usable time for both children and independently observed initial mute on each surface. 1: enter starting surface → REQUEST04(duration/approver) → REQUEST05(fraction) → REQUEST06(soft-apps) → REQUEST06(mute) → REQUEST03(capture). 2: FLOW12 leaves the other surface open after comparing shared choices and its separate mute. 3: select the second child with REQUEST04 in kiosk, or REQUEST12 → V(second child, declared entry) → REQUEST02 for overlay; set distinct choices and capture REQUEST03. Return through the same explicit route and compare each child's observations with UI12 before editing. Mute remains blocked until available. |

### Application routes and complete customer journeys

| Family / cases / variant parameters | Ordered recipe and visible finish line |
| --- | --- |
| E2E-019 / **62–109** / eight routes × `{allowed, hard-blocked, soft-blocked}` × `{enabled, disabled}` | Routes: native grid/desktop/file-manager/command, Snap grid/command, Flatpak grid/command. 1: P0 → FLOW02(usable allowance, selected control state) → FLOW03(policy/match). 2: V(child, fresh) → FLOW08(exact route), including precise nonmatches and applicable AppImage new-version/nonmatch examples; FILE05 supplies tested copy/rename input. A hidden blocked launcher uses APP02(hidden), then a declared command-route FLOW08 to prove denial; no grid-execution claim. 3: V(other user, fresh) → FLOW08(same app/route, usable). All 48 bindings reuse these blocks. |
| E2E-020 / **110–111** / `{update, remove}` | 1: P0 → PARENT10 → PARENT13 → UI16(match draft), leaving it unsaved. 2: LIFE04(target app update/removal) in a separate administrator terminal. 3: DESK10(Parent/editor) → PARENT15(save, row expected only if present). Update: PARENT10 → PARENT12 → V(child, fresh) → FLOW08(updated target). Removal: UI13(catalogue excludes app); if retained rules have no public row, LIFE04(reinstall) → DESK10(Parent) → PARENT10 → PARENT12 → UI12(retained rule) → V(child, fresh) → FLOW08. Never freeze autosave or inspect saved rules. |
| E2E-021 / **112–115** / `{save, approve-without-soft, approve-with-soft, revoke}` | Prerequisite: child has usable time/policy and any grant needed for revocation. 1: FLOW14(declared desktops/apps). 2: save branch P → FLOW03; approval branch V(child, retained) → FLOW04(overlay) → FLOW05; revoke branch P → PARENT17 → PARENT18(confirm). 3: V(each child desktop, retained) → APP02 → APP04(compare only if retained) → FLOW08; FLOW09(each other user). Use positive daily time when a post-revocation desktop visit is required. Same-child multiple-session support must be demonstrated, not inferred from repeated GDM selection. |
| E2E-022 / **116–125** / `{app-restart, sign-out-in, reboot, idle, suspend-wake}` × `{active, expired}` grant | 1: P0 → FLOW02 → FLOW03 → V(child, fresh) → FLOW04(overlay) → REQUEST03(capture) → FLOW05 → TIME01 → FLOW08 → APP04(capture). Include REQUEST06(mute) and separate surface mute observations when the required feature becomes available. 2: app-restart explicitly closes/reopens Parent and both request surfaces via LIFE01 and their exit/entry blocks; sign-out uses DESK04 and defers login to step 4; reboot uses LIFE02; idle uses TIME03; suspend uses LIFE03. 3: expired variants wait the actual remaining interval with TIME03; active variants require positive remaining time. 4: attempt fresh login after logout/reboot or retained unlock otherwise; expired zero-daily variants prove denial before DESK11 → FLOW06 → V(child, declared entry). Reopen Parent/request surfaces through the declared user route, read PARENT03 → REQUEST03 before changing selections → UI12; TIME01 and FLOW08 prove resumed behavior. APP04 continuity applies only to retained sessions. |
| E2E-023 / **126–127** / gameplay `{windowed, fullscreen}` | 1: P0 → FLOW02(enabled, zero daily/no grant) → FLOW03(game usable). 2: V(child, fresh, time-limit denial). 3: DESK11 → FLOW06(short grant). 4: V(child, fresh) → TIME01 → FLOW08(game) → APP05(mode/level) → APP03(actual play). 5: TIME04 → observe lock/loss of game input. 6: DESK08(correct password, time-limit denial). One continuous attempt; no hidden game-survival assertion. |
| E2E-024 / **128–131** / `{daily-dominant, grant-dominant}` × gameplay `{windowed, fullscreen}` | 1: P0 → FLOW03(game usable) → DESK03 → FLOW13(dominant profile, parent/window retained) → V(child, fresh) → TIME01(before fullscreen) → FLOW08(game) → APP05(mode/level) → APP03 → APP04(capture). 2: REQUEST02(including qualified fullscreen panel route) → REQUEST04(duration) → REQUEST08 → FLOW05 → TIME01 → UI12(increase over the larger earlier balance allowing elapsed time). 3: DESK10(game) → APP04(compare) → APP03 → TIME04. If the post-approval countdown needs normal Shell reveal, use DESK12; it need not remain visible during fullscreen play. |
| E2E-025 / **132–135** / soft apps `{excluded, included}` × entry `{new-login, retained-unlock}` | 1: P0 → FLOW03 → DESK03 → FLOW13(real grant, parent/window retained) → V(child, fresh) → FLOW08 → APP04(capture). 2: TIME04. 3: retained-unlock: FLOW11(replacement with variant soft choice) → FLOW08. New-login: DESK11 → FLOW06(temporary legitimate access) → V(child, retained) → DESK04 → FLOW06(declared replacement) → V(child, fresh) → FLOW08. The new-login route tests launches, not survival across logout; reconcile legacy shared wording. |
| E2E-026 / **136–138** / activation `{process, session, reboot}` | 1: P0 → FLOW02 → FLOW03 → DESK03 → FLOW04(kiosk) → REQUEST03(capture) → REQUEST12(cancel) → V(child, fresh) → FLOW08. 2: P → LIFE04(product update) → LIFE05(activation), covering each affected frontend/session declared by the package profile. 3: enter/reopen Parent through that activation route, read PARENT03 and PARENT12 before changing values → UI12; enter each declared request surface → REQUEST03 → UI12; V(child, declared post-boundary entry) → FLOW08. Mechanical activation/migration qualification remains separate. |
| E2E-027 / **139** / `continuous` | 1: product-free GDM07(administrator) → LIFE04(install) → LIFE02. 2: P0 → FLOW02 → FLOW03 → DESK03 → FLOW04(kiosk) → REQUEST03(capture) → REQUEST12(cancel) → V(child, fresh) → FLOW08. 3: P → LIFE04(remove) → LIFE02 → V(child, fresh) → FLOW08(previously restricted app, now usable). 4: V(administrator, fresh) → LIFE04(reinstall) → LIFE05(required activation); reopen Parent/request surfaces and UI12(retained observations). Return to the administrator → LIFE04(purge) → LIFE05(required notice) → ordinary child login/app use. Explicitly reinstall once more before asserting visible fresh defaults; never infer them from removed files. Mechanical cleanup qualification remains separate. |

### Recovery, information and feedback

| Family / cases / variant parameters | Ordered recipe and visible finish line |
| --- | --- |
| E2E-028 / **140–141** / `startup-enforcement`, `startup-broker` | Required **mechanical package/system qualification**, not customer E2E. Retain its declared fault/failure/recovery sequence and assertions in the system suite. GDM/Parent blocks may supply its visible portions; no customer block stops a service or probes readiness. |
| E2E-028 / **142–144** / `zero-time-exposure`, `usage-read`, `kiosk-auth-agent` | The declared internal interventions are outside customer scope under the customer building-block contract. Retain/transfer them to separate system qualification. Customer denial, expiry, countdown and retry are composed in E2E-008–018. This disposition is not three completed cases. |
| E2E-029 / **145–150** / `failed-save`, `stale-identity`, `disconnect`, `concurrent-transaction`, `policy-reload`, `partial-termination` | Preserve the six declared engineering obligations separately. Do not implement internal fault controls as building blocks. Customer close/cancel/reopen/retry uses UI18, REQUEST12, REQUEST01 → REQUEST02, REQUEST03 → UI12 and FLOW05 or FLOW07, or LIFE01 or FEED10. Reuse E2E-013/014/015/031 where identical; a distinct customer path must be reconciled explicitly before associating one of these old IDs. No transfer earns a pass. |
| E2E-030 / **151** / `parent` | 1: FLOW01(child, legacy GDM10 login, whole-query SEARCH06 route) → ABOUT01 → ABOUT02. 2: ABOUT03 using the initial child/settings observation and existing Tab/End footer navigation. Preserve strict legacy GDM recipient checks until separate qualification; open step-2 before permitting license-close input. |
| E2E-031 / **152** / `draft-reopen` | 1: P0 → FEED01 → UI16(synthetic body/reply) → FEED04(format) → FEED03. 2: FEED05 → FEED10(dialog, preserved draft), then FEED10(app-exit, reset draft). Do not Send. |
| E2E-031 / **153** / `validation` | 1: P0 → FEED01 → repeat(declared invalid/valid body/reply values) { UI16 → FEED03 → FEED09(validation/Send availability) }. 2: FEED05 → FEED10(dialog, retained draft). Disabled/invalid Send needs no external submission. |
| E2E-031 / **154** / `attachments` | 1: P0 → FEED01 → UI16(synthetic body) → FEED06(finite file/count/size cases) → FEED07(review) → FEED12 only if preview is offered → FEED13(remove named attachment) → FEED03. 2: FEED05 → FEED10(dialog, retained attachments/draft). Do not Send. |
| E2E-031 / **155** / `diagnostic-export` | 1: P0 → watch(FEED09 collection) { FEED01 } → FEED08(save/open through customer UI). 2: DESK10(feedback) → FEED05 → FEED10(dialog). Read the saved customer artifact, not original logs/collector internals. |
| E2E-032 / **156** / `success` | With explicit sending authorization/test recipient: 1: P0 → FEED01 → UI16(synthetic body/reply) → FEED06(attachments) → FEED03 → FEED05 → FEED11. 2: FEED09(success) → FEED14 → FEED01 → FEED03(cleared draft). Observe the app response; no provider/recipient receipt probe or delivery claim. |
| E2E-033 / **157** / `retry` | Injected transport interruptions remain separate integration work. Conditional customer route: 1: P0 → FEED01 → UI16 → FEED06 → FEED03 → FEED05. 2: LIFE06(disconnect through normal UI). 3: DESK10(feedback) → FEED11 → FEED09(retry). 4: LIFE06(reconnect). 5: DESK10(feedback) → FEED09(automatic success for the same submission) → FEED14. Never click Send again to fake automatic retry. Without a supported customer network route and sending authorization, retain pending and the original integration obligation. |

### Inventory reconciliation

The JSON inventory is unchanged by this design and baseline qualification. Its five
ready cases have no contract rewrite in this plan. Many pending declarations
still combine customer actions with internal assertions; implementing only
their visible recipe must not satisfy the unchanged larger declaration.
Before registering a pending consumer, reconcile its phases, assertions and
evidence with the following dispositions, preserving the engineering obligations
in their existing unit/component/system owners. Do not silently delete them or
count a transfer as completed coverage.

| Declarations reviewed | Customer composition and retained obligation |
| --- | --- |
| E2E-001 / 1 | FLOW00 covers every existing input and observation. HAR03/09/10 and the retained envelope cover its explicit harness assertions. These are allowed only in harness qualification; no scope reduction or new exception is needed. |
| E2E-003 / 3–4, E2E-004 / 5, E2E-030 / 151 | Complete visible recipes map to the new blocks. Preserve IDs, phase timing, assertions, fixture boundaries and established input routes. Readiness alone is not new passing evidence. |
| E2E-002 / 2, E2E-026 / 136–138, E2E-027 / 139 | LIFE04/05, FILE06 and the normal login/app blocks cover package commands, notices, activation and usable return. Package bytes/ownership, reboot-marker files, service/D-Bus publication order, canary execution, account cleanup and storage migration remain mechanical qualification. The required notice text/result is functional; red color is cosmetic and cannot gate customer acceptance. Keep package-install/removal checks under their existing owners. |
| E2E-005–025 / 7–135 | PARENT/REQUEST/TIME/APP plus UI12 and retained-user FLOW09 cover displayed settings, balances, denial, app use and observed activity continuity. Saved preferences, process identities, component activation, internal transaction ordering/exactly-once counts and live filters remain unit/component/system assertions. A single visible prompt cannot prove one internal transaction; a later unlocked desktop cannot prove an invisible earlier process event. Public observations and these engineering claims are distinct obligations. |
| E2E-005–029 and E2E-031–033 generic `other-user-result` | Preserve customer isolation with FLOW14 capture → the declared transaction → FLOW09 for each declared fixture activity. Where relevant, FLOW01/PARENT03/PARENT09/PARENT12 → UI12 compare other children's displayed settings without edits. Bind the actual users/apps before execution, including an unrelated fixture when the claim needs one; missing provisioning is a prerequisite gap. Internal policy/grant/process snapshots remain separate. Logout/reboot ends activity continuity; post-boundary normal login/use supplies the public result. |
| E2E-028 / 140–144 and E2E-029 / 145–150 | These **11 variants cannot be composed as customer-only scenarios as currently written**: step-2 and step-4 require internal fault controls. Retain their exact failure-before-recovery, rollback and isolation requirements as engineering qualification. Their normal entry/retry UI can reuse this catalogue, but there is deliberately no service-stop, policy-write or fault-injection customer block. A future inventory ownership change must retain every numeric ID and obligation. |
| E2E-031 / 152–155 | FEED/FILE blocks cover draft persistence, validation, attachment review and customer-selected export. Raw draft storage, private collector metadata and original product logs are not customer observations. Retain local privacy/size/transport checks separately; qualify UI24 before claiming rich-text formatting. |
| E2E-032 / 156 | FEED11 → FEED09 → FEED14 proves the actual app's service response. Dedicated-recipient receipt and provider/idempotency evidence in the current declaration remain separately authorized integration verification. UI confirmation alone cannot satisfy that unchanged backend assertion. |
| E2E-033 / 157 | The proposed customer route is LIFE06 disconnect → one FEED11 → FEED09(retry) → LIFE06 reconnect → FEED09(automatic success). Bind a supported normal network control and restoration deadline inside the real retry window. Replace the pending fault-phase wording only when this route is qualified; recipient receipt, frozen transport bytes and idempotency remain integration obligations. No second Send and no forged response. |

Every visible recipe step therefore has named customer or harness blocks. The
11 fault variants are the explicit scenario-level exceptions; the table above
also retains non-customer assertions embedded in other pending declarations.
Do not report “all 157 are implementable as customer UI composites” or complete
coverage until those declaration conflicts and feature prerequisites are resolved.

Reachability differences also require explicit phase wording when their pending
consumer is implemented: allowance validation versus enable/save/child visits
(7–12), natural expiry followed by a legitimate logout route (22), reopening
the kiosk to check denied access (36–37), app preservation observed only after
legitimate return (126–127, 132–135), and fresh-default observation after a final
reinstall (139). Do not weaken natural-expiry or retained-activity assertions to
make a shorter recipe pass. Hidden mute, unavailable same-child multi-desktop
entry, public game/format locators and sending prerequisites remain the concrete
gaps listed below. These are pending requirements, not permitted skips.

### Bound recipe data before implementation

Each implementation binds every route, account, app, selector, expected message,
interval and comparison before running. Use registered fixture identities and
synthetic content. Public reads supply actual observations; they must not select
a more convenient expected outcome after a failure. A missing public locator,
asset or product feature is a named pending prerequisite, not custom scenario
code that bypasses a block.

For time arithmetic, D and G mean the **displayed** daily and one-time remaining
values from PARENT09 → REQUEST08, with declared rounding bounds; R is the selected
fixed additional duration. UI12 compares intervals allowing measured elapsed
time. The documented visible total is max(D, G), and a fixed approval adds R
to that larger balance. Rest-of-day instead uses the displayed until-midnight
meaning. These expectations come from the [time contract](../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities);
no runtime backend value is read.

| FLOW13 profile | Ordered public preparation and required observation |
| --- | --- |
| Daily-only | Observe no grant (or revoke); FLOW02 with positive daily allowance. PARENT09 must show D > 0, no one-time balance. DESK03 finishes at GDM. |
| Grant-only | No grant → FLOW02(enabled, daily=0) → DESK03 → FLOW06(R). Return via FLOW01(parent/window retained) → PARENT09 requiring D=0, G>0 → DESK03. |
| Combined / grant-dominant | No grant → FLOW02(enabled, positive daily) → DESK03 → FLOW06(R>0). Return to Parent → PARENT09 requiring both positive, and G>D for grant-dominant → DESK03. A fixed approval already includes the prior larger balance. |
| Daily-dominant | No grant → FLOW02(enabled, daily=0) → DESK03 → FLOW06(R). Return to Parent → PARENT06(larger daily allowance **while still enabled**) → PARENT08 → PARENT09 requiring D>G>0 → DESK03. Do not disable control, which clears G. |

Select durations and display-rounding margins large enough to preserve the
required inequality through login/game launch, and short enough for the
scenario's real-time expiry deadline. Verify the inequality again at the
request estimate; do not silently relabel a daily-dominant variant if G wins.

| E2E-005 transition | Inputs and independently observed result |
| --- | --- |
| Preparation | Validate allowances while enabled, select the variant daily allowance, then visibly disable. For retained entry, create the child's usable session while unrestricted and return to Parent. At tested enable there is no grant. |
| Enable | UI17(true), save observation, then child visit. Positive daily remaining admits; grant-only zero denies with the time-limit message. App hard/soft rules still apply. |
| Edit while enabled | Daily-only has no request. Grant-only/combined first obtain real time with FLOW06 and record it. Daily-only/combined change positive allowance to a different positive value; grant-only uses 0 → positive → 0, checking **each** save/child visit. The one-time balance remains subject to elapsed time, not reset or extended by the allowance edit. |
| Disable | UI17(false), save observation, child visit. Time becomes unrestricted and the one-time balance is cleared; saved app rules still apply. |
| Re-enable | UI17(true), save observation, child visit. No old grant returns. Positive remaining daily time admits; grant-only zero denies. New variants log out after each admitted visit, retained variants preserve the original desktop. |

Use PARENT09 and TIME01 where the values are public. If a zero-time screen
prevents inspecting app windows, assert access denial there; do not claim
unseen closure. Existing scenarios with retained-window assertions obtain
legitimate time before inspecting them.

## Finite values and applicability constraints

The following are explicit boundaries of the plan, not permission to skip an
assertion. Block composition is defined even where a product/prerequisite gap
currently prevents execution.

| Area | Data or implementation constraint |
| --- | --- |
| Daily allowance | E2E-005's old text names 0 and 1440 plus out-of-range/invalid input. Current Parent custom entry accepts whole minutes **0–1439** and its presets stop below 1440. Use 0, preset 15, 1439, 1440, −1, 1441, empty and `abc` as the finite review set. The current UI accepts the first three and rejects the rest. Reconcile the 1440 expectation against the current customer contract before implementation; do not declare 1440 valid or silently remove its case. [Current UI](../../parent/oh_no_parent_control_parent/main.py) owns the displayed range. |
| Request durations | Predefined values are 5, 15, 30, 60, 120 and 240 minutes from [request-options.json](../../child/request-options.json); Rest of the day and Custom value belong to their separate variants. Custom valid values 0.1, 0.5, 1.25, 1440; invalid 0.09, 1440.1, empty and `abc`; rest-of-day's displayed until-midnight meaning. Invalid cases stop before authentication. Large valid grants test form/result behavior, not a 24-hour expiry wait. |
| Time profiles and deadlines | Daily-only starts without a grant; grant-only sets daily to zero; combined/dominant profiles use actual UI approval and observed balances. Choose short supported values for expiry and adequate values for active-return cases. Carry elapsed time/tolerance explicitly; keep every recipe within its declared duration (currently 1800 seconds) or reconcile a justified duration before registration. Never change the guest clock. |
| App expectations | Allowed/nonmatching targets must be usable. Hard blocks remain denied; soft blocks follow the explicitly approved choice. Screen-time enablement and app rules are separate customer controls. Test update/new-version/space/copy/rename examples using declared assets and actual launches, within the documented matching limits; do not invent universal copied-executable enforcement. Hidden launcher coverage and denied execution are separate observations. |
| Kiosk restriction attempts | A finite route list: normal Overview/app-grid keys, normal terminal shortcut, and available settings/Parent launch controls. Require the request form still usable plus absence of the attempted forbidden surface. If no search UI appears, do not type an app query into the request form. No VT/service escape or containment probe is a customer action. |
| Mute | [Front-end design](../SystemDesign/Frontends.md#lightning-audio) and `REQUEST_MEDIA_ENABLED = False` in [request main.py](../../kiosk/oh_no_parent_control_kiosk/main.py) currently hide and disable mute. REQUEST06's mute binding and the mute portions of E2E-018/022 stay pending until the customer feature is available or its scope is explicitly revised. Do not flip private preferences or enable a test-only switch. |
| Multiple sessions for one child | Repeated GDM selection can resume the existing session. E2E-007/multiple and E2E-021 need a demonstrated supported customer route to distinct desktops if they retain that claim. FLOW14 does not manufacture sessions with a backend helper. If unavailable, preserve the unfulfilled obligation and explicitly reconcile its system/customer ownership. Distinct-user retained desktops remain ordinary customer coverage. |
| Save pause in E2E-020 | Access buttons autosave. The actual Edit Match Rule dialog has an editable draft and Save/Cancel, so PARENT13 → UI16 provide a real pause while the app is updated/removed. Do not suspend saves internally or treat a completed autosave as still pending. |
| Rejection and replacement wording | Case 22 retains natural exhaustion, then needs a supported normal logout route; its planned temporary-grant/logout/revocation sequence is explicit. A request form exited for an access check must be reopened and its choices compared. A new login after logout cannot preserve the prior app window. Retained-activity cases must obtain legitimate access before comparing APP04 observations, without attributing later transaction effects to an unseen earlier event. Reconcile those pending declarations with their first consumer. |
| Feedback | Use synthetic content/files and the actual privacy disclosure. Finite local cases: empty/whitespace/normal body, 5,000 and 5,001 ASCII characters; empty, valid synthetic and malformed reply address; 5 vs 6 selected files; 5 MiB vs 5 MiB + 1 per file. Total files plus diagnostics have an 8 MiB limit: bind public displayed diagnostic size when testing that boundary, otherwise retain that exact aggregate boundary in existing local tests rather than inspect private bytes. Bounds are in [feedback_transport.py](../../common/oh_no_parent_control_ui/feedback_transport.py). Do not transmit for validation. Sending cases require an available supported service profile and explicit authorization. Only the app's response is customer evidence. Existing injected transport/idempotency/provider tests remain separate. |
| Game/app fixtures | Prepare real installed native/Snap/Flatpak apps and a pinned offline game/level through supported fixture setup. Their customer actions and public result locators must be qualified; no fake game window, internal game-state probe or screenshot-similarity acceptance. Missing public access to required information is a specific automation limitation, not a cosmetic failure or permission to pass. |

The only non-customer recipe segments are the retained harness case, required
mechanical package qualification, explicitly transferred internal fault cases,
and declared account/asset setup. All in-scope customer steps map to the same
catalogue. The current feature/applicability gaps above remain visible rather
than being counted as implemented exceptions or completed coverage.

## Case 1 stage contract

The first refactor preserves this exact existing protocol from
[controller_qualification.py](../../tests/e2e/controller_qualification.py),
`FUNCTIONAL_SERIAL_STAGES` in
[check_graphical_smoke.py](../../tests/integration/check_graphical_smoke.py),
[onpc_gdm.pm](../../tests/integration/graphical_smoke/lib/onpc_gdm.pm) and
[onpc_serial.pm](../../tests/integration/graphical_smoke/lib/onpc_serial.pm).
The new block IDs do not rename wire stages or add an alternative runner.

| Ordered stage | Block boundary and evidence | Recorder phase / next input |
| --- | --- | --- |
| `ready` | Existing asset receipt/guard plus HAR03(greeter/boot); bind `functional_smoke`. | `start`; durably open `step-1` before reply. HAR01 selects `sut`. |
| `gdm` | GDM01 + UI13: fresh `ui:gdm-list`, bounded current account order. | `step-1`; only this reply's navigation may drive UI14. |
| `focused` | UI14's independent focus observation: `ui:gdm-focused`. | `step-1`; only now send one Enter via UI05. |
| `selected` | GDM08: `ui:gdm-select-parent`, correct label/focused password role and hidden list. | `step-1`; no graphical password, then GDM09 sends one Escape. |
| `dismissed` | GDM09's GDM01 result: `ui:gdm-dismissed`. | `step-1`; durably open `step-2` before reply permits serial entry. |
| `serial-password` | HAR05: actual login prompt, selected fixture echo and bounded password prompt; HAR03 verifies login process/TTY and disabled echo. | `step-2`; store proof before one UI19 secret input and one newline submission. |
| `serial-authenticated` | HAR05: fresh HAR03 confirms the real fixed serial session. HAR02 still waits for the shell prompt before a command. | `step-2`; never infer shell readiness from session activation alone. |
| `serial-command` | HAR06: actual complete output of the existing split-marker command, then HAR03 session proof. | `step-2`; store command evidence before permitting logout. |
| `serial-logout` | HAR07: `exit`, fresh login prompt and independent session-free greeter. | `step-2`; durably open `step-3` before reply permits return to graphics. Emit exactly one successful logout marker. |
| `gdm-return` | HAR08: select `sut`, independent session-free greeter and fresh `ui:gdm-returned`. | `step-3`; record `other-user-result` with its evidence before reply. |
| Worker finish and reconciliation | Existing `journey->finish`, normal owned worker shutdown, HAR10 and HAR09. | Still `step-3`: assert `visible-result` and `backend-result` using original evidence rules, then enter `end`. |

Setup retains fixture credentials, stock serial getty and FIX04. Every acknowledged
stage retains unchanged-boot proof, durable evidence before reply and the terminal
failure latch. End/cleanup still collect separate outcomes, stop only owned
operations, restore the accepted baseline and verify host/source preservation.
No explicit post-authentication capture is reopened. Do not force this
product-free harness case through `record_installed_journey` or silently perform
installed-product setup.

The serial worker's exact username/command strings, secret API options, console
identity checks, LF/CRLF matching, timeouts and one-attempt latch are compatibility
requirements. Extract them into registered bindings; do not offer arbitrary
commands/regexes or broaden authentication while doing this refactor. Preserve
the legacy serial install/refusal callers and all existing safety regressions.
The public GDM blocks must remain usable by another independently supplied valid
entry state; they must not depend on case 1 having run first.

## Refactoring the established cases

The five ready callbacks and their real Perl workers were reviewed, together
with `AccessibleUI`, `UiObservations`, `InstalledJourney`, the password/GDM/
serial helpers and relevant regression contracts. Their customer operations
can be expressed using the catalogue; the migration must preserve these seams:

| Established code | Refactor target | Behavior that must survive |
| --- | --- | --- |
| [controller_qualification.py](../../tests/e2e/controller_qualification.py), `onpc_gdm::functional_selection`, `onpc_serial::run_functional` | FLOW00, expanded by the [case-1 stage contract](#case-1-stage-contract): GDM02/09, HAR05/06/07/08, then HAR10/09 in the existing envelope. | No graphical secret; real serial authentication/command/logout; exactly one logout before fresh graphical return. Preserve all harness/backend safeguards and the existing wire stages. |
| [parent_discovery.py](../../tests/e2e/parent_discovery.py), [onpc_parent_discovery.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_discovery.pm) | GDM07, SEARCH06, PARENT02/03/04/19, FIX01 in case 3 or FIX02 in case 4 and explicit UI12 comparisons. | Every picker opens from current public order, highlights before Enter and verifies selection afterward. Existing child starts limits-off/zero; each child's returned values compare with its own observation. FIX01 stays after visible initial settings; FIX02 stays after launchable search but before launching Parent. |
| [parent_access.py](../../tests/e2e/parent_access.py), [onpc_parent_access.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_access.pm) | GDM07(standard), SEARCH01 → UI21 → SEARCH03 → SEARCH04(unavailable). | Standard-specific wrong-recipient refusal and two fresh checks; pointer click then independent focus; first character then readback, remainder then full readback; exact query-specific web suggestion and complete stable absence; no Enter on it. |
| [parent_about.py](../../tests/e2e/parent_about.py), [onpc_parent_about.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_about.pm) | FLOW01(GDM10, whole-query SEARCH06), ABOUT01/02/04/03 and explicit settings observation. | Keep strict legacy GDM credential checks until separately migrated. Read actual installed version/license/footer, close the real viewer, and return to the same child/switch/allowance. Open step-2 before the acknowledgement that permits closing the license. |

Concrete shared changes are needed before the proposed interfaces are ready:

- Case 3's `AccessibleUI.run` bindings now delegate to registered picker,
  settings, page, search and desktop callables. Continue extracting the other
  consumers without exposing unrestricted operations or moving expectations
  out of their recipes.
- Case 3's `JourneyPlan.settings_checks` supplies immutable expected values and
  explicit earlier-stage references. `InstalledJourney.check_settings` checks
  these before fixture actions and durable replies; the discovery-specific
  hidden settings slots are gone. The retained About adapter still uses
  `initial_settings`, and credential order still uses `last_operation` within
  the qualified single-authentication route. Migrate those remaining consumers
  with explicit observations/challenge context, preserving stale/replay refusal.
- The functional password helper's `functional_started` latch permits only
  one authentication per worker. UI19 → GDM05 → DESK08 → AUTH02 need distinct,
  ordered, single-use challenges for legitimate subsequent authentication.
  Preserve the terminal failure latch, wrong-recipient refusal, two fresh
  checks, fixed secret options and capture restrictions. Clearing the existing
  latch between calls is not the implementation.
- Current public-bus routing supports the active greeter, fixed Parent and
  other-child desktop. Add the intended child/other-parent/kiosk/lock routes
  only with their named entry consumer, preserving socket/account ownership
  checks. Metadata for routing is not evidence of product behavior.
- `JourneyPlan.screen_tags` is ordered and each stage is unique. Repeated
  blocks need unique invocation/stage IDs and a fresh controller observation
  for each invocation; they cannot reuse a previous stage's result. Preserve
  `phases`, `advance_after`, fixture action timing and store-before-reply.
- UI22 needs bounded public-state observation active before the triggering
  worker input. Extend the existing rendezvous for its named transition
  consumer, retaining durable readiness/input/result ordering, single input and
  the terminal failure latch. Post-action polling cannot replace this trace.
- `InstalledJourney` currently rejects any customer-phase boot change and
  `record_installed_journey` emits one terminal `visible-result` assertion.
  LIFE02/05 and journeys with multiple declared assertions need small explicit
  extensions for planned boot transitions and assertion placement. Reconnect
  only after the recorded customer reboot; unexpected boot changes must still
  fail. Keep the current path for the four established customer cases.

Do this incrementally, retaining old registered operation adapters while each
consumer migrates. A new block's output shape and event sequence must be checked
against its old consumer before replacing that path. No wholesale worker,
recorder, schema or VM-runner replacement is needed.

Relevant retained checks are [public UI adapter tests](../../tests/unit/test_accessible_e2e_ui.py),
[case-1 GDM worker](../../tests/unit/test_e2e_gdm_helper.py),
[serial worker](../../tests/unit/test_e2e_serial_helper.py),
[case-1 recorder/reconciliation](../../tests/unit/test_e2e_controller_qualification_cleanup_safety.py),
[actual Perl discovery](../../tests/unit/test_parent_discovery_worker.py),
[actual Perl access](../../tests/unit/test_parent_access_worker.py),
[actual Perl About](../../tests/unit/test_parent_about_worker.py),
[controller/phase/fixture safety](../../tests/unit/test_installed_journey_cleanup_safety.py),
[About cleanup and reconciliation](../../tests/unit/test_parent_about_cleanup_safety.py),
and [real GTK/Shell adapter qualification](../../tests/ui/test_e2e_accessible_adapter.py).
Run the affected meaningful checks, then the live consumers required by the
current slice on final unchanged inputs. Changes to shared GDM, secret input, stage
reconciliation or public-UI routing also require their affected safety/harness
qualification; do not run the whole future matrix merely for an extraction.
For the completed case-1 extraction, the preservation gate was case **1**,
including terminal collection and cleanup, on fresh final artifacts, plus
affected shared-helper regressions. Do not run cases 3, 4, 5 or 151 as part of
that slice. Keep all five ready statuses and preserve their compatibility;
this scoped validation supplies no new live acceptance claim for the other cases.

Case-1 extraction qualification uses the actual Perl GDM/serial/FLOW00 helpers,
public-UI adapter, graphical-smoke controller and durable recorder regressions
linked above. Independently supplied entry states cover list collection, prompt
dismissal, console selection, serial command/logout/return and terminal evidence;
missing, stale, duplicate, reordered and failed observations refuse further input.
The case-1 shared worker/recorder regressions preserved cases 3, 4, 5 and 151
without running their live journeys. Its initial UI11/UI13/UI14/UI19 scopes were
GDM snapshots, the GDM collection/highlight route and serial input. Case 3 now
extends those scoped qualifications below; other bindings remain pending with
their named consumers.

The retained baseline run preserves the original behavior evidence.
Final acceptance uses fresh artifacts and
the unchanged public case-1 command, requiring all ten stages, all three assertions,
owned shutdown and complete collection/restoration. Per-attempt paths and outcomes
belong to the existing runner artifacts and invocation report. Block readiness
does not replace that final complete run. This extraction activates on invocation
(`none`); it adds no product integration, setup requirement or data migration.

## Case 3 refactor qualification

Case **3 / E2E-003/existing-and-new** has passed the complete public
`tools/run-tests e2e --id 3` run, including all **23 public-UI checkpoints**,
the terminal `visible-result` assertion, owned worker shutdown, evidence
collection and verified baseline restoration. The ready inventory declaration
and customer assertions are unchanged. The new `parent-window` checkpoint
separates successful launch from subsequent picker input. Per-attempt evidence
and outcomes remain in the runner artifacts; qualification is not a partial
worker-success claim.

The [worker](../../tests/integration/graphical_smoke/lib/onpc_parent_discovery.pm)
composes the scoped FLOW01 from [onpc_parent.pm](../../tests/integration/graphical_smoke/lib/onpc_parent.pm),
then explicit page and child-selection checkpoints. Each selection consumes
its own fresh opened-list and highlighted-choice replies before Enter; each
closed-picker result independently verifies the intended child. Functional
GDM retains positive wrong-account observation, intended-account refusal,
two fresh intended-recipient checks, one secret input and independent desktop
observation. Its extracted UI19 leaf consumes the explicit final proof and
retains capture sealing and terminal failure/replay latches. This qualifies one
fresh Parent login, not repeated authentication or new account/surface routes.

The [recipe](../../tests/e2e/parent_discovery.py) owns four explicit comparisons:
the original child's limits-off/zero-minute expectation, that child's unchanged
settings immediately before FIX01, the new child's settings after returning
from App Limits, and the original child's settings on return. Earlier values
are immutable `SettingsObservation` objects keyed by unique stage, with no
hidden initial/new-child slots. Comparison failure prevents both the fixture
action and acknowledgement and latches the existing controller failure state.
FIX01 remains after the initial visible settings and App Limits checks while
Parent stays open. The new child must appear without restarting Parent.

The [adapter](../../tests/e2e/accessible_ui.py) exposes scoped label reading,
complete child-list collection, popup absence, highlight, selection, settings,
page navigation and scroll/reveal callables. Local roots may be reused within
one invocation and are reacquired after page transitions. The shared keyring
handler checks all registered titles in one complete fresh traversal before
each wait/input; it keeps no cross-call UI cache. Missing/stale reads, ambiguous
prompts, uncertain clicks and undisposed dialogs still refuse. This keeps
installed-catalogue size from multiplying prompt scans without changing
observation deadlines or substituting appearance checks.

Qualification includes the actual [Perl discovery worker](../../tests/unit/test_parent_discovery_worker.py),
[GDM](../../tests/unit/test_e2e_gdm_helper.py) and
[secret helpers](../../tests/unit/test_e2e_secret_variables.py),
[public adapter regressions](../../tests/unit/test_accessible_e2e_ui.py),
[durable recorder/fixture safety](../../tests/unit/test_installed_journey_cleanup_safety.py),
and [real GTK/Shell adapter checks](../../tests/ui/test_e2e_accessible_adapter.py).
Independent opened-list and immutable-observation tests cover reuse without
prior scenario execution; failed/missing/stale/replayed observations prevent
further input. Shared case-1, access and About regressions preserve compatibility.
Cases 4, 5 and 151 retain their existing ready status; this extraction makes no
new complete live-acceptance claim for them. Activation is `none` (next test-tool
invocation), with no product or saved-data changes.

## Functional validation

Customer E2E passes on usable interactions and their results. It must tolerate
misalignment, altered size, colors, fonts, spacing, resolution, scale and ugly
but functional rendering. Do not compare screenshot appearance, widget geometry,
whole-window layout, decoration, tile positions or pixel similarity for customer
acceptance. Rendering regressions belong to separate UI tests.

Use public AT-SPI names, roles, state and text to locate UI controls and observe
results. Public accessibility actions and normal keyboard/mouse input operate
the installed GUI. Require an unambiguous, showing, enabled target before input;
then wait for the expected resulting state. Do not call product methods, set
widget values directly, read saved policy or treat an action API's success as
the functional result. A displayed setting may be read while disabled (for
example, daily allowance when limits are off); only input requires enablement.
Ordinary scrolling and keyboard navigation are valid
ways to reach a control regardless of its position. Do not activate hidden
controls to conceal a reachability failure.

Examples:

- Open the child picker, observe the intended choice, select it, and verify the
  selected child and usable settings. A displaced popup is acceptable.
- Toggle a time limit, verify its UI state and exercise the affected child's
  normal login/session behavior. Reopen settings when persistence is required.
  An illuminated switch alone cannot prove enforcement.
- Open About, read product/version information, follow the license link to its
  actual viewer, read the license, close it, reach the footer and return to the
  same child and displayed settings. Font/color/layout changes do not matter.

For required text, assert meaning-bearing content on a showing public UI node,
not its line breaks, font or coordinates. Missing controls, failed expansion,
wrong selection, inaccessible required information, ineffective settings,
timeouts and crashes remain failures. Keep a failed journey failed; no fallback
that silently skips an assertion or directly applies the requested setting.

The shared [accessible UI adapter](../../tests/e2e/accessible_ui.py) uses bounded
fresh lookups and public actions. [UiObservations](../../tests/e2e/ui_observations.py)
runs it as the fixed fixture user or qualified greeter inside the guarded VM transport, accepts
only registered operations, and returns sanitized semantic screen evidence.
No raw accessibility trees, document bodies or account names enter reports.
Use explicitly qualified interface methods when GI method names collide, such
as `Atspi.Text.get_text(text, start, end)`, rather than the different
`Accessible.get_text` accessor. Read-only lookups may retry stale objects within
their deadline; never replay an action whose effect is uncertain.
Fresh waits also dispatch a bounded batch of pending public accessibility events
before each read, so queued focus/text/registry changes can be delivered.
Functional desktop waits share `AccessibleUI.handle_system_prompt`: a recognized
login-keyring dialog pauses the current operation, requests one normal click on
its enabled Cancel control, and independently waits for complete public reads
to prove that specific dialog disappeared. Queued requests can replace it with
an identical-looking dialog: qualify that new public UI object independently
only after proving the previous one disappeared, never repeat a click on the
original. This applies before operations and during waits, including
after an earlier customer action. It never restarts that operation or replays
its input. The controller streams the fixed, secret-free pointer request through
the existing guarded worker rendezvous; `onpc_journey::service_system_prompt`
reuses `click_target`, records input before clicking, and acknowledges only
completed input. Missing acknowledgements, uncertain clicks, stale absence reads,
or a prompt that stays open fail; at most three fresh prompts per checkpoint are
handled. Prompt appearance during text input does not authorize repairing or
retyping the query. GDM credential checkpoints and unknown authentication dialogs
are excluded. No password content is read or supplied, and no keyring is reset.
Use this shared path for later consumers instead of adding scenario-specific
Escape keys, fixed coordinates or prompt needles.
The [real GTK adapter checks](../../tests/ui/test_e2e_accessible_adapter.py)
exercise selection, disabled-setting reads, About and footer access at 100%
and 125% display scale. These are adapter qualification; the installed case
still must pass its whole guarded journey.
The APIs are documented by upstream [AT-SPI](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/class.Accessible.html).
Test-tool activation is `none` (next invocation); no product integration or
saved-data migration is involved.

In `JourneyPlan.screen_tags`, use `ui:<operation>` for functional observations.
The controller performs the fixed public UI operation at that stage, records its
fresh result durably, checks ownership and only then acknowledges the worker.
Final reconciliation requires all ordered worker markers and matching controller
results. Reusing an earlier result or merely returning zero cannot pass. `screen`
evidence may describe the observed public accessibility surface; it does not
require a screenshot or a pixel score. Private diagnostic images have no cosmetic
pass/fail authority.

Case **151 / E2E-030/parent** is the migration example. Its Parent, app-search,
About and license stages use functional validation. Its existing GDM password
recipient checks remain deliberately strict as a separate input-safety boundary.
Do not lower those thresholds or type secrets into an uncertain recipient.
Future authentication adaptation must prove intended identity, masked/focused
field and wrong-recipient refusal through an equally strong public UI contract.
Report an unsupported locator/recipient as an automation limitation, not a
cosmetic product failure. Legacy cases retain their existing behavior until
migrated; they are not templates for new pixel-based customer acceptance.

Case **3 / E2E-003/existing-and-new** reuses this contract for app search,
existing-child selection, dynamic discovery and return. Preserve the original
existing fixture's limits-off/zero-allowance expectation and the new child's
visible remaining-time section. The fixed account fixture
runs only after fresh visible settings and a durable phase boundary while Parent
stays open. Each picker expansion derives navigation from the current public
list; a separate checkpoint verifies the intended highlighted row before Enter,
then another requires the closed picker and intended child's displayed settings.
Both children expose App Limits search and rule-filter controls through normal
tab navigation. Returning to Screen Limits and the original child must preserve
their independently recorded switch and allowance values, including disabled
allowance reads. This case changes no time policy and claims no child-session
enforcement; E2E-005 owns settings changes followed by child use.

Case **4 / E2E-003/none** uses the same functional GDM credential gate and
app-search checkpoints. Before Enter launches Parent, a fresh launchable search
result and durable phase boundary authorize the finite empty-account fixture.
It requires exactly the two canonical eligible child identities before mutation;
missing, substituted or additional standard accounts refuse. The final
`ui:parent-empty` checkpoint independently requires the
showing explanation, “No interactive non-administrator account was found.”,
inside Parent and the public child picker's `(None)` placeholder. Disabled picker state may be
read; no picker input is attempted. Missing/hidden explanations, a selected
child, stale/reordered evidence or failed fixture preparation refuse. Appearance
has no acceptance authority. This case changes no time policy and makes no
child-login enforcement claim. Outer cleanup restores the account fixture.

Case 3 also uses functional GDM account navigation. Its credential gate is
separate from ordinary observations: select the other parent, positively verify
that empty masked prompt and refuse it as the intended parent's recipient,
dismiss, then independently focus/select the intended parent. The secret helper
requires two consecutive fresh controller acknowledgements of the exact account
label, hidden account list, sole showing/enabled/focused `password text` role and
zero character count. It reads no password contents. The second acknowledgement
immediately precedes the existing `type_password` API with fixed secret options.
Wrong order/identity, nonempty or unmasked fields, review mode, uncertain typing,
capture and replay refuse. The active local greeter and owned session socket
remain qualified; no screenshot threshold or legacy credential gate is weakened.

Case **5 / E2E-004/app-grid** connects the registered standard-user operations
to the canonical other-child desktop's owned accessibility bus. Its functional
GDM gate derives navigation from the public list, independently verifies focus,
positively observes and refuses the wrong parent's empty masked prompt, then
checks the intended standard account's identity and sole empty, masked, showing,
enabled, focused field twice before secret input. Standard-specific ordered
checkpoints cannot reuse the Parent acknowledgement; review mode, uncertain
typing, capture and replay refuse. Legacy recipient needles stay unchanged.
After normal
Super-A input, a fresh public Overview search field must be showing, enabled,
editable and empty. Its public screen extents supply a current pointer target
for one normal click; `ui:standard-search-focused` independently verifies focus.
Coordinates route input only, with no reference positions, image comparison or
fixed resolution. A blocked click fails, and an uncertain click is never replayed.
The shared system-prompt handler automatically cancels recognized login-keyring
prompts during desktop observations, including late arrivals. Its public Cancel
control must be showing and enabled, with a focused masked field in the same
identified dialog. `ui:standard-system-prompt` and the subsequent app-grid
checkpoint require dismissal before search input. Parent and unknown dialogs
are never closed. Use the shared pointer request and independently verify each
dialog's dismissal; checking only for the absence of every keyring prompt can
confuse queued, identical-looking requests with a failed Cancel action.
Shell's keyring prompt may expose its full login-keyring explanation instead
of the legacy window title; require that exact explanation, authentication
heading, masked field and Unlock control together before cancelling. Never read
or supply a keyring password.
GNOME's normal type-to-search route submits the first
character once; `ui:standard-search-started` independently reads it before the
remaining query is entered once at a bounded pace. No focus API, uncertain input
repair or replay is used. The result checkpoint reads that exact query, the showing web-search
suggestion and its query-specific explanation, and requires the absence of a
Parent launcher or management window across fresh complete accessibility reads
for a bounded stable interval. Stale subtrees cannot establish absence; missing
search UI, wrong text or a delayed Parent result fail. No Enter activates the
web suggestion. Reuse `find_labelled_button` for search results whose visible
label identifies an enclosing button, and require the query-specific description
inside that same result. Application pixels and fixed coordinates have no acceptance
authority. This preserves standard-user launcher unavailability only; it changes
no time policy and makes no child-session enforcement or terminal-denial claim.
The [isolated Shell search qualification](../../tests/ui/e2e_search_probe.py)
reuses the owned nested desktop launcher and normal Super-A/keyboard input to
exercise type-to-search and exact query readback. It is adapter qualification; only the
complete installed case and cleanup earn customer acceptance.

Case **1 / E2E-001/gdm-observation** uses the same `ui:` checkpoints for
GDM account selection, the intended account's focused password prompt, Escape
dismissal and fresh graphical return after serial logout. The adapter connects
as the sole active local greeter for these registered operations only. Public
logind metadata resolves its current account, including dynamic GDM accounts;
the owned runtime/session socket is validated before dropping privileges. No
graphical password is submitted or authorized by this observation contract.
Account rows expose no AT-SPI click action in this GDM. Derive bounded Home/Down
input from their public list order, verify the intended button's focus, press
Enter and independently verify the selected account's prompt. Both this worker
and case 151 use `onpc_journey::navigate_choice` to validate navigation replies.
Its real serial authentication, command-output, session/boot, asset and cleanup
checks remain harness qualification, with no customer feature coverage credit.
The shared reconciler requires fresh controller results for each ordered worker
marker, and case 1 additionally requires logout before graphical return.

## Existing runtime services

The ordered catalogue owns feature-block status and implementation order.
These existing services support those blocks within their current qualified
scope; reuse them without building a second runner or counting their checks
as customer behavior.

| Need | Implementation | Contract |
| --- | --- | --- |
| Verified installed app | [installed_setup.py](../../tests/e2e/installed_setup.py): `stage`, `InstalledSetup.run` | Bind package/helper/selection bytes before bootstrap; install, reboot and verify once in setup. Failure is terminal. |
| Controller rendezvous | [installed_journey.py](../../tests/e2e/installed_journey.py): `JourneyPlan`, `InstalledJourney` | Ordered requests, durable observation callback, fresh ownership guard, then atomic reply. Boot identity supplies harness continuity only. |
| Recorder composition | [installed_journey.py](../../tests/e2e/installed_journey.py): `record_installed_journey` | Provision fixture credentials, enter declared phases, checkpoint observations and reconcile screenshots. Strict customer execution; existing recorder owns evidence and final acceptance. |
| Legacy/security matched click | [onpc_pointer.pm](../../tests/integration/graphical_smoke/lib/onpc_pointer.pm): `click(tag, timeout)` | Retained for unmigrated consumers and credential qualification; not the customer acceptance template. |
| Worker stage reporting | [onpc_journey.pm](../../tests/integration/graphical_smoke/lib/onpc_journey.pm): `seen`, `observe`, `finish` | Emit the named screen stage and wait for its acknowledgement. Keep automatic captures private and verify shutdown. |
| Interrupted pre-start setup | [system_runner.py](../../tests/integration/system_runner.py): `recover_graphical_cleanup`, through `tools/run-tests integration check_graphical_recovery` | Restore a recorded `isolated` attempt only with a null instance ID, powered-off pinned guest, matching run tag, original disk identities, no host sharing and a full baseline proof under the exclusive lease. Reuse outer cleanup; never start the guest or replace the baseline. |
| Reviewed image preparation | [parent_needles.py](../../tests/e2e/parent_needles.py), via [prepare-e2e-needle](../../tools/prepare-e2e-needle) | Fixed registered nonsecret tags, inspected source pixels, reviewed regions, 16-pixel matcher context, bounded destinations. |

The scenario recipes own expected results. Shared runtime services do not
choose a customer's expected result or query internal product state.

## Add a consumer

1. Select one inventory variant and its complete visible result. Identify the
   required fixtures and surfaces. Reuse accepted setup; installation mechanics
   do not become customer assertions. If a shared operation is missing, name the
   blocked action and implement only that operation with this consumer.
2. Compose a worker module from the ordered blocks and selected recipe above.
   The established cases demonstrate current working sequences; retain their
   recipient gates until the corresponding new block is qualified. Use normal
   app-search input and functional checkpoints.
   The picker-open checkpoint clicks its exposed toggle button. The next
   reply supplies Home/Down navigation derived from the current public list
   order. A checkpoint verifies the intended highlighted row; Enter selects it,
   and a fresh
   checkpoint verifies the closed picker and displayed child/settings.
   Add a fixed branch in [smoke.pm](../../tests/integration/graphical_smoke/tests/smoke.pm)
   for the new worker mode. Reuse the existing exchange channel and owned worker;
   do not create another VM runner or invoke private product APIs.
3. Define a `JourneyPlan` in the Python scenario module. `screen_tags` maps
   stage names to `ui:<operation>` **in execution order** (legacy/security stages
   may still name a needle); `ready` and
   `setup-detached` are prepended automatically. `prefix` must match the worker's
   `onpc_journey` prefix. `worker_mode` names the fixed ready-reply branch.
   `phases` maps every stage to a declared recorder step. `advance_after` opens
   the next step before the current reply permits that step's first input.
   The About plan opens `step-2` at `license`, before closing the viewer.
   For settings comparisons, `settings_checks` maps the current stage to an
   immutable `SettingsObservation` expectation or an explicit earlier stage.
   The controller retains sanitized immutable values, compares before fixture
   actions/storage/reply, and refuses missing earlier evidence or replay.
4. Have the callback call `record_installed_journey(recorder, context, PLAN)`
   and register it in `E2E_CASES`. This composition currently supports one
   authenticated installed journey with unchanged customer boot and a terminal
   `visible-result` assertion. Its fixed account-fixture stage actions are
   already supported. Repeated authentication, customer reboot or additional
   assertion needs require the scoped extensions identified above; do not force
   them into the current path or bypass its failure latch. Ordinary feature
   setup installation/reboot stays outside the customer steps. Tested package
   installation/reboot in E2E-002/026/027 remains a real customer action.
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
   Reuse resulting runner artifacts; report only the
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
| Keyboard assumptions select the wrong child or menu item | Derive Home/Down navigation from the current public list order, verify the intended highlighted row, then press Enter. Verify the selected child independently. Launch Parent with Super-A, the product query, a functional search-result checkpoint and Enter. |
| About footer starts below the viewport | Use public accessibility scrolling to bring the required content into view. Assert its text and showing state; do not require a fixed scroll distance, dialog size or pixel match. |
| An acknowledged action has no durable evidence, or belongs to the wrong step | Store the observation and any required next-phase start before publishing the reply; guard ownership again after storage. An acknowledgement may immediately permit input. Storage or guard failure latches terminal failure. |
| A stale observation appears to prove returning to the same child | Reconcile one fresh semantic result per ordered stage. Compare the returned child, switch state and allowance with the initial displayed settings. Missing, reused or reordered evidence refuses. Worker exit zero alone cannot pass. |
| Fresh code runs against stale package/needle inputs | Finish all edits, including docs, before building. Use the generated artifact directory unchanged. Do not edit during a guarded attempt; provenance changes invalidate its result. |
| VM is off but baseline acquisition reports `guard:source-changed` | Inspect the saved run phase and inactive configuration through the approved readers. An interrupted `isolated` setup can retain the test configuration. Use recorded graphical cleanup; do not edit the journal, recreate the baseline or treat powered-off status alone as restored state. |

## Add or repair a screen needle

This section is for retained legacy/security consumers. For customer feature
validation, migrate to the functional contract above instead of recording more
image variants, loosening a similarity threshold or adding coordinate fallbacks.

A needle is a reviewed PNG plus JSON regions used by the real image matcher.
It must come from the installed surface being tested. Inspect the current
failure and named private screenshot before changing coordinates or pixels.
Do not lower matching thresholds, synthesize evidence, add fixed click fallback
positions or copy another account's password recipient.

Use the [approved screenshot export](../Approval-Tools.md) to create a caller-owned
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
matches cannot pass validation. These retained image-preparation routes do not
replace the public E2E-004/app-grid callback's functional observations and
separately qualified secret-recipient gate.

Explicit captures after authentication remain prohibited. Automatic worker
captures stay private. Preserve original reports and screenshots; remove only
named temporary exports with `tools/cleanup-screenshots` when finished.

## Current extension boundary

E2E-003 reuses installed Parent login, launch and evidence handling. Its two
scoped fixture actions cover dynamic eligible-account creation after an existing
child is visible and a finite no-eligible-account state before Parent launches.
The latter requires exactly the two canonical child accounts to be eligible,
preserves the fixed package request station and refuses unexpected
identity/object sets before mutation. A stage action executes only while the
worker is fresh and before its durable reply; failed workers retain owned
process/callback cleanup for outer restoration. Visible refresh/selection or the
reviewed empty explanation supplies the assertion; no broker/catalog probe can
replace it. Keep qualification in retained runner artifacts and the implementation report.

These are development test tools, activated on the next invocation (`none` for
package update activation); no product integration or saved-data format changes.
Refresh the installed dispatcher with `./setup.sh --test-tools-only` after its
command-line interface changes. Shared modules alone need no setup refresh.
