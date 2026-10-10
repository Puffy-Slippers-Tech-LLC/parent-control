# Reusable customer E2E building blocks

Apply the [UI/E2E allocation](UI-and-E2E-Coverage.md) when composing consumers.
UI tests own individual control behavior and local functional boundaries;
installed cases use the same shared operations to achieve realistic customer
goals and verify meaningful product outcomes. A qualified block is a reusable
means, not an obligation to test its controls in each consumer. Simplify redundant
inputs, dialog visits, unchanged observations and incidental GUI presentation outright
under the [result contract](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope).
New or changed provider routes still require scoped entry/refusal qualification.
Apply the [product-focused journey contract](E2E-Execution-Contracts.md#product-focused-journeys)
to current callables as well as future consumers; historical provider checks
below describe earlier qualification, not mandatory steps in every journey.

This is the contract catalogue for the operations used by customer scenarios.
The [documentation map](README.md) defines document ownership and status terms;
the [execution plan](E2E-Execution-Plan.md) owns task selection and live
completion, while the [recipes](E2E-Scenario-Recipes.md) own exact scenario
composition. Read only the rows required by the selected task.

Every row below records an implementation status. Existing behavior that still
needs extraction, migration or qualification is `pending`, even when an older
scenario run passed. Current ready inventory bindings retain implementations,
behavioral evidence and functional customer assertions. Retain their helper
regressions while migrating them. Retired E2E IDs 140–150 remain engineering
system-test obligations and cannot be selected by the E2E runner. Current scenario counts come from
`tests/e2e/scenarios.json` and the generated coverage report, not this catalogue.

## How to implement one block

Apply the [UI automation mandate](../Mandates/UI-Automation-Mandate.MD) throughout
this catalogue. All product-control blocks use the
[Application UI API](Application-UI-API.md) through the shared
[test facade](../../tests/support/application_ui.py); external authentication,
file choosers and supporting desktop tools retain provider adapters. Historical
input mechanics are evidence of earlier runs, not implementation requirements.
Rows marked **Migration required** describe existing mechanisms
to replace before reuse while preserving their behavioral and safety assertions.
A `ready` label applies only to the exact compliant scope named in that row;
older results and unlisted bindings confer no readiness. [Functional
validation](#functional-validation) applies the mandate here. Callable names
locate implementation to inspect, not permission to reuse noncompliant selectors
or input routes. Documentation alone does not establish compliance or a live pass.

The tests exercise customer-facing product behavior and observe the results.
Name the customer's goal before selecting blocks; compose only operations that
advance the journey, establish safe input or observe a distinct customer outcome.
Select users in the app, type into its real approval prompts, operate product
settings, read messages and use windows. Never replace those product actions
and assertions with internal methods, saved-data reads/writes, process inspection,
service checks or synthetic grants. Supporting system operations and launch
routes follow the distinction below. Existing runner
ownership, secret handling, installation setup and cleanup remain supporting
machinery, not customer assertions. Apply the distinction below to each action.

### Environment preparation and customer interaction

Choose routes under the [UI mandate](../Mandates/UI-Automation-Mandate.MD#route-selection).
This catalogue binds those routes to callables and qualified scopes; it does not
repeat the mandate's command, login, launch or external-link rules. Product
actions and public results remain distinct from supporting environment checks.

The shared installed envelope verifies each observed fixture Parent desktop's
prepared accessibility and idle settings through independent readback before
acknowledging entry. Cases must not add idle-prevention stages. See the
[shared entry contract](../../tests/e2e/README.md#shared-system-and-account-entry-helpers)
for ownership, cleanup and the unchanged child-session policies.

### Keep supporting work bounded

First classify each input's lifetime under the
[baseline mandate](../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
Baseline reconciliation owns reusable inputs; FIX06 verifies declared fixture
profiles after restore. FIX04 transfers attempt inputs. A package or file change
explicitly tested by a recipe remains a scenario mutation.

For every remaining task, name the product assertion first, then choose one
supported way to establish each unrelated prerequisite. Reuse the qualified
helper and stop preparation as soon as that prerequisite is independently
observed. Qualify ownership, reversal and the result needed by the consumer;
do not turn a dependency into another feature matrix or framework.

When preparation fails, inspect the direct failure evidence and distinguish an
environment/fixture defect from a potential product defect. For non-product
work, use the simplest reliable maintained recovery route or a small repair of
the immediate proven mechanical defect. Verify the prerequisite and return to
the product test as soon as it is ready. First remove any incidental requirement
or choose a simpler supported route that preserves the product result; do not
expand GDM or desktop qualification solely to reproduce an unnecessary step.
If the remaining prerequisite requires recursively repairing
dependencies, investigating their internals, or creating new infrastructure,
stop that branch and report the exact blocker, evidence and minimum external
action needed to resume. Do not add prerequisite tasks merely to continue that
detour. A bounded adviser review, when required, answers the immediate question;
it does not expand the authorized scope. This stopping rule preserves routine
automatic preparation and does not permit bypassing guards or weakening checks.

Product installation and enforcement are product boundaries even when their
failures occur during snapshot or fixture preparation. For example, a child trust
database readiness failure during product package installation is a potential
product defect until classified from evidence, not grounds to seed private state
or disable a readiness gate. Preserve the failure and apply the repository
[failure contract](../../tests/README.md#handling-test-failures); keep any product
repair focused on the failing boundary and required regression coverage.

The existing [fixture builder](../../tests/fixtures/build_test_applications.py)
and [GUI fixture](../../tests/fixtures/gui_application.py) are the starting point
for app/game assets. Reuse them and add only a missing finite identity or action
required by the recipe; their existence does not qualify an unimplemented route.

| Supporting work | Minimal route and stopping point |
| --- | --- |
| App and game assets | Reuse the maintained fixture builder, verified manifests and artifact cache for native, Snap, Flatpak, versioned-path and offline-game inputs. Reconcile reusable native executables, shared GUI files and launchers through `tools/prepare-baseline`; attempts independently verify them over guarded SSH. Deliberate scenario file mutations use shared file operations. No native fixture package or product installer is required. Independently controlled native roles need distinct executable content where content-based enforcement applies. Use the shared package helper only for inputs that actually require package/runtime installation. Bind the required public identity and one ordinary usable action in its consuming slice. No store browsing, vendor account creation, third-party repository setup, updater exercise or new packaging framework. Real package format, confinement, enforcement and retained activity assertions still apply where declared. Lunar's explicitly real-app profile uses FIX05 instead. |
| Files and desktop entries | Use shared exact-path copy/rename and supported per-user commands/APIs for launcher placement, permissions and trust metadata. Open Files directly at the prepared directory only when its launch route is tested; the actual Files/DING activation remains graphical. No folder tours, Properties-dialog preparation or alternate launch after failure. Product downloads use the bound user's `~/Downloads` and the existing destination helper. |
| Sessions and power | Reuse direct entry, logout, lock/greeter and reboot helpers. Suspend uses one supported guest command and one supported owned-VM wake operation, followed by the actual public return/unlock result. Do not add power-settings, screensaver, RTC, hardware or wake-method matrices. Ordinary overlay reopening uses REQUEST02. |
| Offline and recovery | Every consumer uses LIFE06's same VM Internet-isolation/recovery helper, including from a child desktop or GDM. Restoring Internet access needs no visit to Parent, network settings or another session. Preserve the current product surface and independently observe the app's retry, stop or local-operation result. |
| Feedback and information | Reuse one supported real feedback-service/recipient profile and the reviewed sending scope. Stop at the app's acceptance/retry/error and exit behavior; mailbox provisioning, portal administration, receipt polling and delivery internals are separate work. Check offered links under the link-only mandate and open/read/close the owned Privacy disclosure. No external page/content or handler validation. |
| Unavailable prerequisites | Check the declared route and report the exact missing prerequisite. Same-child desktops, real collection failures, prepared Lunar assets and natural calendar windows retain their gates. Do not build virtual seats/display servers, fault frameworks, vendor setup automation or a new calendar scheduler to manufacture eligibility. Preserve the product assertion and its pending status. |

Preparation never writes the product policy, grants, usage, private state or
outcome under test. An explicitly tested dependency boundary still runs: package
changes during an open match draft, real graphical authentication, launch-route
enforcement, real gameplay, natural expiry and calendar transitions are product
integration assertions. Simplify their setup without replacing their results.

### Block contracts

- **A — atomic:** one input operation or one public observation. Its local
  target, safety and result checks do not silently log in, launch an app,
  select a child or change a setting. It uses the App UI API for product controls,
  qualified provider APIs for external surfaces and
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
- **Status:** use the [shared vocabulary](README.md#status-vocabulary).
  Mark a composite ready only after its callees and its own complete behavior
  are qualified for the declared binding.

Every implementation records its source callable and qualification reference
in its row. Repository-owned selectors use public `automation-id` values scoped
to their application and surface. External providers follow the exception in the
[UI mandate](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception);
catalogue ID bindings describe the current implementation, not a ban
on qualifying an adapter. Scenario labels and expected text are recipe data,
not selector definitions. Use explicit fixture identities; do not
expose arbitrary commands, arbitrary UI-tree dumps or private account names in
reports. Return small semantic observations, never live widget handles across
checkpoints. Reacquire controls after transitions. A block may return a local
public object only to another operation within the same adapter invocation.
Comparisons use explicit immutable observations owned by the scenario and keyed
by their unique checkpoint stages.

Case callbacks and worker recipes compose these blocks and the existing harness.
They may declare finite inputs, checkpoint order, phase boundaries, fixture
bindings and expected values. Keep input, public observation, transport,
recording and recovery mechanics in shared modules, including when only one
current case needs a registered binding. Do not import another case's plan to
reuse its entry sequence. [Checkpoint fragments](../../tests/e2e/journey_blocks.py)
declare shared GDM07/DESK01 and SEARCH06 stages; recipes still own their phases.

Successful input is not a successful customer outcome. Observe the resulting
access, saved work, retained setting or meaningful product information separately.
A selection, text or window observation may supply that evidence; an incidental
widget transition is not another customer result. Retry fresh reads within
the deadline; never replay uncertain input. Repeated submission is a deliberate
customer gesture with its own finite contract. All waits have a named result
and a timeout; elapsed time alone cannot establish enforcement.

Tables define callees before composites: leaves, small control composites, GDM
and the case-1 harness, desktop entry, application surfaces, then journey fragments.
The master execution queue schedules scoped work across these families and places
each eligible scenario after its prerequisites. Catalogue order is not a mandate
to implement every block before starting scenarios. Fixture operations have their
own preparation order and are called only by the surrounding envelope or at
declared recipe checkpoints.

### Implementation slices

The [execution plan](E2E-Execution-Plan.md#task-size-and-order) and
[task queue](E2E-Task-Queue.md) are the single source for slicing, dependency
order, live verification and close-out. A slice implements only its dependency
set and required bindings. Preserve established assertions and adapters needed
by other consumers. If a prerequisite is unavailable, leave the row `pending`
with its concrete blocker and return condition. The selected queue row stays
current; do not choose independent tasks around it. A diagnostic or host-only slice cannot establish installed scenario
readiness.

## Ordered building-block catalogue

### Public observations and individual inputs

These are in-process building blocks behind registered public-UI checkpoints,
not a new remotely executable scripting API. The existing adapter's shared
system-prompt handling and guarded recorder remain middleware for every block.
UI rows that name `automation-id` resolve product controls through the shared
Application UI API. Supporting fixture apps retain their shared public-ID
activity adapters. An explicit external-provider adapter may supply an external
operation through its qualified resolution method while retaining ownership,
ambiguity, required recipient focus, input and independent-result guards.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| UI01 | A | Resolve one control with `getElementById` in its Application UI API surface. Require the current unique owner and logical availability before input; reject missing or ambiguous IDs. | Shared `tests/support/application_ui.py` facade and `AccessibleUI.id_target`; external provider resolution stays in its scoped adapter. | ready |
| UI02 | A | Read logical visibility, sensitivity and declared canonical boolean values from the API snapshot. Disabled controls remain readable; product focus is not a value or readiness prerequisite. | `AccessibleUI.has_state`, `showing` and saved-state readers share API node projections; `revoke_disabled` retains independent zero-balance assertions. Historical qualification reports: `20260925T065641Z-c6d3948b`. | ready |
| UI03 | A | Read bounded nonsecret text with `getText` or translated snapshot name/description after scoped ID lookup. Return only the declared semantic projection. | `AccessibleUI.read_synthetic_text`, label/document readers and shared API node projections. Masked external-provider fields remain excluded. Historical qualification reports: `20260925T030015Z-4c7d9b02`. | ready |
| UI04 | A | Resolve a fresh product element and invoke `activate` once through the Application UI API. Return input completion; observe the required result independently. | `AccessibleUI.activate_id` and `_invoke_target` use the shared API facade. `activate_provider` retains the external-provider route. | ready |
| UI05 | A | Send one declared key/chord only to a qualified external provider or supporting-tool recipient. Product controls use API operations with explicit handlers instead. | `testapi::send_key` retains fresh recipient proofs for Shell/GDM/authentication and external tools; product Enter maps to normal activation and product close to surface `close`. | ready |
| UI06 | A | Enter one nonsecret string into a qualified external provider with a fresh recipient proof. Product text uses UI16 and the Application UI API. | External `testapi::type_string`, including `onpc_parent::enter_search_query`; product text is shared `setText`. | ready |
| UI07 | A | **Retired.** Geometry-based resolution has no executable route. Use UI01 and semantic input; no execution exemption. | Retained `AccessibleUI.pointer_target`, `pointer_glyph` and `stable_pointer` entry points refuse before traversal or geometry access. | retired; safely refused |
| UI08 | A | **Retired.** Coordinate clicking has no executable route. Use product API UI04 or qualified external-provider input; uncertain input still refuses. | Retained `onpc_journey::click_target` and `onpc_pointer::click` entry points refuse before backend, image or input access. | retired; safely refused |
| UI10 | A | Wait for a read-only API/provider predicate under one bounded deadline. Reacquire current scoped observations without replaying mutations. | `AccessibleUI.wait`; predicates contain no input. | ready |
| UI11 | A | Observe absence of an explicit `automation-id` within an otherwise positively ID-addressed surface. Bind `snapshot` or `stable` mode explicitly. Both require complete fresh reads; stable mode additionally requires its declared finite interval and deadline. | Existing absence/window-closure paths must use registered IDs for both the absent target and surrounding surface. Incomplete/defunct reads cannot prove absence; stable reads restart their interval. [Search contracts](#search-and-standard-sign-in-contracts), [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| UI12 | A | Compare explicit sanitized observations with an explicit expected value or earlier observation; report the differing approved fields. No hidden initial/new-child slots. | `SettingsObservation.from_settings` freezes sanitized values; `compare_settings(observed, expected)` compares explicit immutable observations and reports only differing field names. `JourneyPlan.settings_checks` owns expectations and prior-stage references. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI13 | A | Observe a bounded public collection of children first resolved by stable public IDs: canonical identities/order, matching window count, or displayed row set. Inputs declare the ID-addressed root, projection, maximum and expected cardinality (including zero). Order may be verified as a result but never used as identity or to calculate input. Require complete fresh traversal for exclusion/count claims; reject duplicate IDs and unknown requested targets. | `AccessibleUI.app_rows` / `AppRowsObservation` qualify complete App Limits collections through `check_e2e_app_row_observations`; see [app-row observations](#app-row-observations). Case 159 qualified `AccessibleUI.parent_window_count` as a strict complete-tree projection of exactly one owned Parent management window after a second direct launch in `20260929T070054Z-c0f58f19`; duplicate/absent windows refuse. Product choice collections use API canonical identities; greeter and supporting fixture collections retain their separately scoped public adapters. Harness and [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI19 | A | Type one fixture secret once through the unchanged secret-safe API for one challenge whose surface, recipient and empty masked field were freshly resolved by owned public IDs or a qualified external-provider adapter. Accept a registered secret reference and explicit recipient proof, never plaintext in stage data. Do not submit or infer authentication success. Capture remains sealed and uncertainty/failure forbids replay. | `onpc_password::type_fixture_secret` consumes one proof from `enter_gdm_challenge`; distinct Parent GDM challenges are qualified by `check_e2e_challenges`, and the explicit child challenge by [fresh child qualification](#fresh-child-success-qualification). Used identities and the terminal failure latch never reset. Serial retains its separate proof binding; other graphical surfaces remain pending. [Challenge contract](#refactoring-the-established-cases). | ready |
| UI20 | A | Native double-click: unsupported and excluded from automation; do not implement or schedule consumers. | See the [unsupported native-gesture rule](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures). Public mouse synthesis requires geometry; semantic activation is not the gesture. No compliant callable or qualification. E2E-014 cases 38–43 remain uncovered and unscheduled. | excluded; no active task or queue blocker |
| UI23 | A | Make logically collapsed product content available through its declared API value/action only when the required result needs it. Clipping requires no action. | `AccessibleUI.reveal_id` and the shared API facade; `parent-time-status` and declared disclosures use their ordinary handlers. | ready |
| UI24 | A | Read `feedback-editor-document` through `getValue` and compare bounded synthetic text, inline attributes, block attributes and links independently of toolbar state. Selection indexes use Quill UTF-16 offsets. | `AccessibleUI` formatting/block readers project the public document delta; shared `feedback_formats` and `block_semantics` preserve their finite assertions. No arbitrary DOM/JavaScript or private draft reads. Historical qualification reports: `20260927T220402Z-60e41f1b`, `20260927T221053Z-796e5c0f`, `20260927T221352Z-4432e213`, `20260928T000001Z-b07e2a8f`, `20260928T000512Z-196ba37b`, `20260928T000805Z-44ce5cac`, `20260928T005139Z-951ec3ec`, `20260928T005856Z-1f56e149`, `20260928T010152Z-75515a1c`. | ready for declared Parent bold/normal, complex inline and `body-blocks` ranges, linked inline and complete format/removal composition; other bindings pending |
| UI25 | A | Start a bounded read-only API-state trace with a single-use observation token before the declared input. The trace observes only declared public values. | `UiObservations.start_trace`, `poll_trace`, `observe_accessibility_input` and shared API-backed observations retain boot identity, readiness and command framing; legacy callable names do not select AT-SPI product events. Historical qualification reports: `20260929T004135Z-792e22c3`, `20260929T010256Z-f90c015e`, `20260929T014247Z-be5d65b5`. | ready for declared Parent feedback traces and Parent checked-state observation during UI17 enable; other bindings pending |
| UI26 | A | Finish the trace at its explicit public terminal predicate/deadline and return ordered immutable samples. Independently read the final saved state; infer no unobserved transient. | `UiObservations.finish_trace`, trace bindings and terminal projections retain token/order/ownership checks. API text setters are atomic inputs and require no per-keystroke samples. Historical qualification reports: `20260929T010548Z-f022ae23`, `20260929T014509Z-d8b1b110`, `20260929T014830Z-04eed3cb`, `20260929T015123Z-d85b79c6`. | ready for declared Parent feedback traces and checked-state events during UI17 enable; other projections pending |
| UI27 | A | Read countdown tooltip text from its stable Application UI API ID when the local component assertion needs that explanation. No hover gesture is required. | `child-request-tooltip` through `getText`; PANEL03 and local UI obligation 181h. | pending UI coverage |
| UI28 | A | Open the ordinary panel context menu with `activate` on `child-countdown-menu` when a declared operation needs it. Direct preference access requires no menu opening. | Shared `child-panel` API facade; PANEL01/PANEL02 use the canonical preference value directly. | pending |
| SEC01 | A | Preserve fresh intended-recipient, focus, empty masked field, capture and single-use secret checks for unavoidable graphical authentication. Wrong-recipient rejection is a harness safety test. | `AccessibleUI.password_recipient`; shared `onpc_password` input. Routine entries never visit a wrong account. | pending; prepared recipient checks qualified |
| SEC02 | A | Resolve the intended fixture account for minimal shared greeter entry. Reject ambiguous or wrong ownership before input. | `AccessibleUI.gdm_nonsecret_navigation`; direct focus then Enter without an unrelated account visit or menu tour. Harness qualification owns negative-entry exercises. | pending; prepared selection checks qualified |
| UI09 | C | Read the scoped product content, using its explicit API disclosure only when logically hidden. Reacquire its public result; clipped content requires no reveal. | UI01/UI02/UI03 with optional UI23; Parent explanations and About information share API projections. | ready |
| UI14 | C | Select an external-provider choice through its qualified semantic focus route and fresh recipient observation. Product selectors use UI15 without highlight or focus. | `onpc_journey::highlight_choice` and `AccessibleUI.gdm_nonsecret_navigation` retain GDM routes; product choices use canonical API setters. | pending; prepared installed and product-free GDM bindings ready |
| UI15 | C | Set one declared canonical value on an ID-addressed selector and independently read the result. Read `getChoices` when offered-choice assertions are part of the case. | Shared API `setValue` covers Parent/request account UIDs, durations, language codes, app-access keys, filters and menus; `AccessibleUI` owns ordinary save/readiness waits. | ready |
| UI21 | C | Establish focus only for an external-provider input route that needs it. Product fields require scoped API ownership and availability, not keyboard focus. | `AccessibleUI.focus_search_field` and provider recipient proofs remain external. Product text/selection uses UI16 and the fixed editor API. Historical qualification reports: `20260925T030015Z-4c7d9b02`. | pending; fresh desktop search focus ready. Parent feedback body/reply, Jordan App Limits search and kiosk custom-duration editing belong to UI16. |
| UI16 | C | Replace text with one scoped `setText`, then independently read the exact public result. Empty input means clear; invalid literal text is preserved for normal validation. | `onpc_text::replace_text` and `AccessibleUI` share API text input and `read_synthetic_text`; `TEXT_VALUES`, custom durations, allowance and search bindings retain their finite values. Normal Enter validation uses `activate`. Historical qualification reports: `20260925T030015Z-4c7d9b02`, `20260925T053812Z-45e24883`. | ready for declared Parent feedback body/reply including the [synthetic-rtl binding](#parent-inherited-dialog-qualification), SOH, complex and length-boundary fixtures, custom daily 1/2/3, Jordan catalogue finite queries, kiosk 1.25-minute and finite invalid values; other bindings pending |
| UI17 | C | Set one product toggle to an explicit canonical boolean and independently read the result and any required saved policy. | `AccessibleUI.set_toggle` shares API `setValue` for Parent, request and filter controls; unchanged values retain ordinary no-change semantics. | pending; Parent, kiosk soft-app and catalogue filter bindings qualified |
| UI18 | C | Close a product surface through its ordinary API `close` request and independently observe disappearance and the expected underlying surface. External windows retain their qualified close route. | `onpc_window::close` and `AccessibleUI` share product surface close; external keyboard close retains active-recipient proofs. Historical qualification reports: `20260926T214728Z-4a3ca1b4`. | ready for Parent→desktop, feedback→Parent and Privacy→feedback; other extracted bindings await live validation |

| UI22 | C | Bracket a declared caller-owned input with public-state observation. Start before input and finish at the supplied result/deadline; do not infer a transient from the final state. | `journey_blocks.observed_text(entry, binding)` and `onpc_feedback_states::observed_text` compose UI25 → one explicitly declared UI16 replacement → UI26 through the existing worker/controller channel. `JourneyPlan.trace_bindings` and `trace_terminals` supply the input and expected result; the controller passes the single-use token explicitly. Failed readiness prevents input; uncertain input is never replayed. `compose_observation.PLAN` / `ComposeObservationJourney` qualified `body-first` → `body-clear` through `check_e2e_compose_observation_around_one_caller_input` in `20260929T005940Z-b33fb38a`: two independent entries, wrong-entry refusal, immutable samples during clearing, and independent FEED09 terminal comparison. Edit-only invalid body retains enabled Send and no validation message. Trace/stable/FEED09 regressions passed in `20260929T010256Z-f90c015e`, `20260929T010548Z-f022ae23` and `20260929T010822Z-1f4e5c65`; collection, owned cleanup and baseline restoration passed throughout. `watch` is the declared composition, never a hidden callback with extra actions. | ready for declared Parent feedback body-first and body-clear inputs; other bindings pending; Parent saves use PARENT08 final results; collection uses FEED09 readiness without a transition requirement |

### Sign-in and desktop entry

Account parameters are a closed set of provisioned fixture roles, not arbitrary
usernames. The public-UI connection must be qualified for the selected greeter
or desktop. Extending the current fixed Parent/other-child routing is part of
the affected entry block; that connection metadata supplies no product evidence.

The GDM prompt and denial blocks below are opt-in operations for a real
authentication input, an explicit enforcement assertion or isolated harness
qualification. Ordinary journeys require only their declared destination and
product result. A shared entry operation must not force a password prompt when
a qualified direct return suffices; it must still establish the intended session
and apply fresh recipient guards before any secret delivery. Existing
prompt-specific qualification does not by itself qualify a direct-return branch.

`greeter_account` uses bounded public logind reads. If a listed session disappears
before its properties can be read, a fresh successful inventory must confirm
its absence before the incomplete scan is discarded. The next scan rechecks
the sole active local greeter; a still-listed failed read, failed inventory,
ambiguity or deadline expiry refuses. No graphical input is replayed, and the
destination still requires an independent public UI observation.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| GDM08 | A | Observe the selected account label, focused showing password role and hidden account list. This is a nonsecret prompt observation only; it cannot authorize password input and never reads password contents. | `AccessibleUI.greeter_prompt()` uses the scoped semantic GDM adapter to resolve the sole greeter, exact prepared recipient and protected password node while rejecting visible account rows. `check_e2e_gdm_recipient` installed-qualifies the Parent prompt; `GdmProductFreeJourney` / `check_e2e_gdm_product_free` qualifies the same protected Parent prompt on the declared product-free baseline. Focused tests reject wrong/duplicate recipients, missing/duplicate/unfocused/nonempty/unmasked fields and list overlap without traversing or reading password text. | pending; prepared installed and product-free Parent prompts qualified |
| GDM03 | A | Read the intended GDM recipient's identity and sole showing, enabled, focused, empty masked field with the account list hidden. Read character count only, never password content. | `AccessibleUI.password_recipient(name)` uses the same protected semantic snapshot and reads only `Text` character count. `onpc_gdm::recipient_qualification` obtains two fresh Parent proofs for one challenge; the installed qualification also proves the prepared other-parent recipient and refuses it as Parent. Fresh and retained-child GDM proofs passed the shared explicit challenge; see [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Other accounts and prompt surfaces remain unqualified. | pending; prepared Parent/other-parent, fresh and retained-child GDM bindings qualified |
| GDM01 | C | Observe the usable greeter and its account list, with no active password prompt. | `AccessibleUI.gdm_nonsecret_account(name)` retains the installed Parent/station cardinality contract for ordinary-account entry. Station entry and `kiosk_gdm_returned` require only the usable station row; locked, absent or differently named parents do not gate station access. Task 024 retains live requalification for that revised station scope. `gdm_product_free_account()` separately requires the declared Parent row and excludes the station from one complete product-free list. `GdmProductFreeJourney` / `check_e2e_gdm_product_free` qualifies two independent product-free list/return cycles; wrong fixture shape, owner, duplicate, stale and list/prompt overlap paths refuse. Case 2 additionally qualifies the complete fixed personal-account/station read after reboot through `gdm-installed-accounts`; [scope](#clean-installation-journey). Other bindings remain unqualified. | pending; prepared installed/product-free Parent list and case 2 account-set bindings qualified |
| GDM02 | C | Select a named user on the logon screen. Use UI14's qualified provider navigation, verify focus before Enter, then observe the declared fresh/retained GDM password prompt or passwordless station. Selection does not itself activate or unlock a retained desktop. Do not type a password. | `AccessibleUI.gdm_nonsecret_navigation(name)` retains the installed account/station route. `gdm_product_free_navigation()` separately focuses and freshly verifies Parent on the declared station-free fixture before `onpc_gdm::product_free_qualification` sends one Enter. `check_e2e_gdm_product_free` qualifies two independent Parent entries; installed Parent/other-parent/station bindings remain separately qualified. The retained-child GDM challenge passed `onpc_gdm::sign_in_challenge`; see [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Configured-zero retained-child denial also passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification). Other accounts and session choices remain unqualified; positional Home/Down calculation stays retired. | pending; prepared installed/product-free Parent and retained-child GDM selection bindings qualified |
| GDM09 | C | Dismiss an already observed GDM password prompt with one Escape and independently observe the account list again. No secret is typed. | `onpc_gdm::product_free_qualification` consumes each scoped prompt proof before one Escape and obtains a fresh `gdm_product_free_account()` returned-list proof; `check_e2e_gdm_product_free` qualifies both independent cycles. The installed qualification separately covers the prepared other-parent and Parent prompts. Retained locks and other prompt surfaces remain unqualified. | pending; prepared installed and product-free Parent bindings qualified |
| GDM04 | C | Harness safety qualification only: prove that another recipient cannot authorize an intended fixture secret. Never compose this negative exercise into customer sign-in. | `onpc_gdm::recipient_qualification`; wrong-recipient unit regressions. | ready; harness only |
| GDM05 | C | Deliver the intended fixture password once to an already selected prompt after two fresh ordered recipient checks. Do not submit or infer success. No wrong-account visit is a prerequisite. | `onpc_password::enter_gdm_challenge` binds two fresh proofs to each declared challenge through `JourneyPlan.challenges` and `onpc_journey::declare_challenges`. `check_e2e_challenges` qualified two Parent authentications separated by shared DESK04 logout, independent desktop results and wrong-entry refusal, with durable assertions, reconciliation, private collection and owned cleanup (run `20260924T192200Z-c833e973`). The explicit child challenge passed [fresh child qualification](#fresh-child-success-qualification). Compatibility entries remain `enter_parent_gdm_password` / `enter_standard_gdm_password`; child input requires an explicit challenge. The distinct child `retained-login` challenge passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Other recipients and surfaces remain pending. | pending; distinct Parent, fresh and retained-child GDM challenge bindings ready |
| GDM06 | C | Observe the declared access result at GDM or lock: usable intended desktop, or time-limit rejection with its explanation and no desktop access. A generic failed login is not the expected denial. | `AccessibleUI.standard_shell_desktop(no_prompt=True)` on the intended child's bound bus supplies the independently observed [fresh success](#fresh-child-success-qualification). `AccessibleUI.gdm_child_time_denied` supplies the [specific zero-time denial](#fresh-child-time-denial-and-return-qualification). Direct child lock-screen success and retained-child GDM reauthentication success passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Configured-zero retained denial remains unqualified on both surfaces. | pending; fresh child success/zero-time denial and both stated retained success routes ready |
| GDM07 | C | Shared minimal fresh graphical entry for the intended fixture account with declared success or product time-limit denial. Retained targets use unlock. | `journey_blocks.fresh_desktop` and `onpc_parent::sign_in`: intended account focus/Enter → fresh GDM03 proofs → GDM05 → Enter → GDM06/DESK01. Explicit challenges use `onpc_gdm::sign_in_challenge`; `fresh_desktop('child')` declares the [qualified child success](#fresh-child-success-qualification), and `fresh_desktop('child', 'time-denied')` declares the [qualified denial](#fresh-child-time-denial-and-return-qualification). `ProductFreeEntryJourney` / `onpc_product_free_entry::run` qualify the product-free Parent binding; see [qualification scope](#product-free-parent-entry-and-command-context). No wrong-account visit or prompt-cancellation tour. Preserve real graphical PAM enforcement. | product-free Parent and fresh child success/zero-time denial ready; other unqualified bindings pending |
| GDM10 | C | Retired duplicate legacy Parent sign-in. | Consumers reuse shared GDM07; no separate provider qualification or implementation task. | retired |

#### Fresh child success qualification

`check_e2e_fresh_child_allowed` passed on every enabled VM in
`20261001T111319Z-2c5fe866`. `fresh_child_allowed.PLAN` /
`FreshChildAllowedJourney` composes shared Parent entry/selection, FLOW02's
disabled-to-enabled 15-minute allowance with saved balance readback, DESK03's
switch from a newly observed Parent desktop, and the intended child's fresh
GDM entry through `onpc_gdm::sign_in_challenge`. The child challenge binds two
fresh ordered `gdm-child-recipient` proofs to sealed single-use UI19 input.
`gdm-child-list` focuses the exact fixture through the existing owned GDM
adapter; `fresh-child-desktop` connects to `CHILD_ACCOUNTS[CHILD]` and requires
a complete, usable, prompt-free Shell desktop for two seconds.

The separate harness wrong-recipient exercise passed before child input.
Host regressions retain stale/mixed/incorrect-role proofs, uncertainty,
non-replay, privacy canaries, actual worker order, real recorder entry,
controller decoding and failure before durable acknowledgement. Collection,
worker shutdown, callback closure, owned cleanup and baseline restoration passed.
Affected challenge and desktop-session regressions passed in
`20261001T111551Z-e34062ad` and `20261001T112043Z-9810576c`, including owned
cleanup and baseline restoration.
Sanitized provider evidence records GDM `50.1-0ubuntu0.1`, Shell
`50.1-0ubuntu1.2`, actual locale `en_US.UTF-8` and keyboard `[["xkb", "us"]]`
at the greeter and child desktop. This qualifies only fresh child success with
ordinary positive daily time. Later successful retained-child routes are
[qualified separately](#successful-child-unlock-and-retained-gdm-reauthentication-qualification);
complete scenarios remain pending. The separate zero-time result is qualified below. The report is
`output/test-runs/host/reports/20261001T111319Z-2c5fe866/report.md`.

#### Fresh child time denial and return qualification

`check_e2e_unlock` passed on every enabled VM in
`20261001T114758Z-22b2d095`. `fresh_child_denied.PLAN` /
`FreshChildDeniedJourney` prepares zero daily/no grant through Parent, consumes
a newly observed Parent desktop for Switch User, and calls the same
`onpc_gdm::sign_in_challenge` entry with two fresh ordered child recipient
proofs and sealed single-use password input. `fresh_desktop('child', 'time-denied')`
binds the specific result. `AccessibleUI.gdm_child_time_denied` requires the
intended child, hidden account list and exact English-GDM account-expiry
explanation; generic failed authentication cannot satisfy it.

`rejected_gdm_return` / `onpc_gdm::return_from_time_denial` reobserve that
rejected prompt and consume the proof before Escape. The current shared route
then observes either the usable account list or the intended child's empty,
focused masked prompt. Only that fresh child prompt authorizes one additional
Escape; all other or ambiguous states refuse. This handles GNOME's renewed
verification after cancellation without replaying credentials or accepting a
prompt as the final result. The final observation independently requires the
usable child account list. The observer discards the entire scope when a
GDM transition leaves defunct nodes, reacquiring within the existing bounded
wait. Stale reads authorize neither results nor input; persistent stale state,
wrong recipients and ambiguous ownership still refuse. Host checks cover that
transition, secret exclusion, real worker order, controller decoding and failure
before Escape or durable acknowledgement. All 2831 affected host checks passed
in `20261001T114523Z-255177a4`.

Fresh-child success, distinct-challenge and desktop-session regressions passed
separately in `20261001T115033Z-f55da4b5`, `20261001T115307Z-a19ef2ed` and
`20261001T115500Z-4e9c011e`. Every attempt passed collection, worker shutdown,
callback closure, owned cleanup and baseline restoration. The greeter tuple is
GDM `50.1-0ubuntu0.1`, Shell `50.1-0ubuntu1.2`, actual locale `en_US.UTF-8`
and keyboard `[["xkb", "us"]]` on Ubuntu 26.04. This qualifies fresh child
zero-time denial and rejected-GDM return only; retained lock/unlock, other
provider tuples and complete scenarios remain separate.

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
| HAR03 | A | Obtain one fresh fixed harness observation: `boot`, `greeter`, `serial-password` or `serial-session`. Require the existing lease, identity, exact result schema and terminal failure latch. | Serial and boot projections retain their checks. The greeter projection is pending because appearance cannot identify GDM; split or requalify the branch before reuse. | pending |
| HAR04 | A | Permanently seal explicit capture before serial authentication preparation. Repeated calls cannot reopen it. | `onpc_password::seal_capture`; the serial worker's existing no-video policy and secret registry remain mandatory. | ready |
| HAR05 | C | Authenticate the fixed serial fixture once and observe its real session and usable shell. No graphical secret is involved. | `onpc_serial::login(state)`: HAR04 → HAR01 → HAR02(login) → UI06(username) → HAR02(password) → HAR03 checkpoint → UI19 → UI06(newline) → HAR03(session) → HAR02(shell). `attempt(exchange, body)` retains the encompassing single-attempt/video/capture/failure boundary. | ready |
| HAR06 | C | Submit the existing harmless serial command once and observe actual output, then independently corroborate its session. | `onpc_serial::command(state)`: UI06(fixed split-marker command) → HAR02(output) → HAR03(session checkpoint). Explicit authenticated entry; consumes state before input and never replays failures. | ready |
| HAR07 | C | Log out the authenticated serial fixture normally and independently observe the session-free greeter before any graphical return. | Serial logout stays valid; its graphical greeter result needs HAR03's GDM route qualification. | pending |
| HAR08 | C | Return from the logged-out serial console to graphics and obtain a fresh public greeter observation. Require HAR07's explicit evidence from this attempt. | The ordering and replay guards remain; the graphical result needs HAR03/GDM01 route qualification. | pending |
| HAR09 | A | Reconcile all ordered case-1 public-UI results with worker markers, requiring exactly one successful serial logout between dismissed GDM and returned GDM. Read existing evidence; perform no guest action. | `serial_harness.matched_screens`; [controller reconciliation regressions](../../tests/unit/test_e2e_controller_qualification_cleanup_safety.py). Case module retains its import for compatibility. | ready |
| HAR10 | A | Validate the complete expected stage sequence, actual worker module success and verified shutdown result before terminal assertions. Zero exit alone is insufficient. | `serial_harness.validate_stages(directory, observations)` is the existing pre-shutdown callback; `validate_completion(directory, observations, worker)` repeats complete stage/module validation and requires verified shutdown before reconciliation. Case module retains these imports for compatibility. | ready |

HAR03(boot) brackets acknowledged stages exactly as the current callback does;
every value must equal the first boot. Persist observations and any phase change
before a reply permits further input. This recorder middleware is common to the
blocks, not a hidden second customer operation. Asset receipt, worker ownership,
evidence collection and outer restoration remain the existing attempt envelope.

### Desktop and retained-session entry

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| DESK01 | C | Observe a usable desktop for the explicitly selected fixture; require its normal Shell controls. | `AccessibleUI.standard_shell_desktop(no_prompt=True)` uses the bound fixture session bus, one complete scoped Shell snapshot per read, unique showing enabled Activities control and complete unknown/authentication-modal refusal. `check_e2e_fresh_desktop` independently qualified fresh Parent and standard desktop results over two seconds in separate restored attempts; the same adapter qualified the intended child's fresh desktop through [fresh child qualification](#fresh-child-success-qualification). `check_e2e_desktop_keyring` additionally qualified `cancel_keyring_prompt` on a prepared real standard-account gcr challenge, followed by disappearance and an independent two-second desktop readback without replaying login input. Lock observation is qualified separately under DESK06; the preserved child's usable desktop passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Other retained bindings and Shell surfaces remain pending. | pending; fresh Parent/standard/child, stated retained-child success and prepared standard gcr Cancel return ready |
| DESK02 | A | Retired Shell system/session-menu automation. These menus are not product features. | Use shared DESK03/04/05 and LIFE02/03/06 system operations. No menu adapter to qualify. | retired |
| DESK03 | C | Lock and switch to the greeter while retaining the fixture desktop. Independently check the original session and usable GDM destination. | `session_control.observe` uses the bound user's public ScreenSaver lock and GDM switching API over guarded SSH; `onpc_desktop_session::switch_user` then observes GDM01. `check_e2e_desktop_session` qualified a fresh installed Parent entry, one switch, independent source locked/inactive readback and usable GDM using its then-current installed snapshot, then requalified it in a separate restored attempt alongside DESK04; private collection and owned cleanup passed (run `20260923T170614Z-02c46f60`, now outside runner retention). [Fresh child qualification](#fresh-child-success-qualification) additionally consumes a newly observed Parent `repeat-desktop` proof after allowance preparation. No Quick Settings. Other fixture bindings and retained-window behavior remain pending. | pending; fresh and newly reobserved Parent switch bindings ready |
| DESK04 | C | Log out the bound fixture desktop and independently check that its session ended and GDM is usable. | Shared `session_control.observe` invokes `gnome-session-quit --logout --no-prompt` once as the bound user over guarded SSH, verifies the source session disappeared and a greeter session is active; `onpc_desktop_session::log_out` then observes usable GDM01. `check_e2e_desktop_session` qualified a fresh installed Parent desktop, direct logout and independent GDM result, then requalified DESK03 in a separate restored attempt; private collection and owned cleanup passed (run `20260923T170614Z-02c46f60`, now outside runner retention). No logout-dialog/Cancel or forced-termination fallback. Other fixture bindings remain pending. | pending; fresh Parent logout binding ready |
| DESK05 | C | Explicitly lock through Super+L or the supported session lock API and independently observe the lock surface. Never manufacture natural expiry. | `onpc_desktop_session::lock` consumes a fresh desktop proof, invokes shared `session_control` Lock once and calls DESK06. `desktop_session.LOCK_PLAN` / `SUPPLIED_LOCK_PLAN` qualify separate command and independently supplied Super+L attempts. No system-menu navigation. [Parent scope](#parent-lock-surface-qualification); child command Lock passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). | fresh Parent command/Super+L and child command Lock ready; other bindings pending |
| DESK06 | C | Observe the intended user's lock surface: password challenge or native time restriction. Input declares curtain or already-open challenge; reveal with one normal key only for curtain. | `journey_blocks.lock_challenge` / `onpc_desktop_session::observe_lock` and `AccessibleUI.shell_lock_snapshot` bind the sole local locked declared fixture session and its Shell-owned public window. Curtain requires the English unlock hint and fresh scoped focus before one Space; challenge reads the public intended-fixture identity and focused password role without contents or secret authority. Wrong-session, other-surface, ambiguity and replacement guards retain independent result readback. [Qualified scope](#parent-lock-surface-qualification); child curtain/reveal and challenge read passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). The child's native configured-zero restriction passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification), through the same guarded curtain reveal. Recipient proofs are qualified separately. | Parent and child curtain/reveal and independent challenge read and child native zero-time restriction ready; other bindings pending |
| DESK07 | A | Qualify the lock-screen recipient, masked empty focused field and intended identity independently of GDM. | `journey_blocks.lock_recipient` / `onpc_desktop_session::lock_recipient`, `AccessibleUI.lock_surface` and `UiObservations` bind two ordered fresh proofs to the same actual lock window and password field. `desktop_session.LOCK_RECIPIENT_PLAN` / `LockRecipientQualification` independently qualify the Parent command-lock binding. [Parent scope](#parent-lock-recipient-qualification); the shared `account='child'` proofs passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). | Parent and child command-lock recipient proofs ready; other retained-user bindings pending |
| DESK08 | C | Attempt normal unlock with an explicit expected success or time-limit restriction on the observed surface. GNOME's configured-zero native lock restriction blocks authentication before password entry; retained GDM denial follows real authentication. | Actual lock success: DESK06 → DESK07 twice → UI19 → UI05(Enter) → GDM06/DESK01 through `onpc_desktop_session::unlock_success`. Native restriction: guarded curtain reveal through `onpc_desktop_session::reveal_lock` → `AccessibleUI.lock_surface('child-lock-time-denied')`, requiring the specific native explanation, absent password input and no desktop access. Never activate Ignore, which requests more time. Retained GDM: GDM02 → GDM03 twice → GDM05/UI19 → UI05(Enter) → independent success or authenticated time denial. Never interchange proofs. See [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification) and [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). | pending; stated child lock-screen/retained-GDM success and configured-zero restriction/denial ready; other bindings pending |
| DESK09 | C | From another usable desktop, visit a specified retained user's desktop without replacing it. Inputs include target account and expected unlock result. | DESK03 → GDM02 → the actual GDM reauthentication branch of DESK08 → DESK01. GDM selection does not directly enter the child's lock screen; actual lock entry needs independent DESK06 observation before that DESK08 branch. Fresh entry explicitly uses DESK03 → GDM07 instead. `journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop` qualify [both retained child visits](#both-retained-child-desktops-and-explicit-entry-modes). `onpc_parent::open_for_child` retains the [Jordan → Jamie Parent entry](#retained-parent-desktop-and-window-entry) and adds Riley → the same Jamie/Riley window in that two-child history. | fixed retained Parent and both child visit bindings ready; other-parent management remains separate |
| DESK10 | C | Activate a named existing window with the simplest reliable public focus action or bounded shortcut, then verify that window is active. | `AccessibleUI.window_switch_ready` → `onpc_feedback_read::activate_existing_window` (one Alt+Tab) → `window_switch_proof`; compare recorded public endpoint/PID and preserved synthetic draft. [Qualified scope](#same-desktop-window-activation). No logout or relaunch. | Parent, feedback and supporting GPL viewer ready; diagnostic exports use FILE08 without a viewer |
| DESK11 | C | From an observed locked fixture session, use the shared greeter-return command; from an observed rejected GDM prompt, use Escape. Preserve the denial observation before leaving and independently require the usable account list. Select the route from the declared source; never try alternatives after uncertain input. | Locked desktop: `session_control.observe` with the bound `return-greeter` action preserves the locked session and invokes GDM's public API without another Lock. Rejected GDM: `rejected_gdm_return` / `onpc_gdm::return_from_time_denial` compose fresh provider observation → UI05(Escape) → GDM01; [qualified child denial return](#fresh-child-time-denial-and-return-qualification). The pre-authentication locked-child command return passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification); Both native lock restriction and authenticated retained-GDM denial returns passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification). No lock-screen Switch User button or menu navigation. | pending; fresh rejected-child GDM, pre-authentication locked-child and both retained time-denial returns ready; other bindings pending |
| DESK12 | C | Resolve the product panel API surface from the observed unlocked child desktop, including a caller-declared fullscreen activity. Require the current session and logical control availability. | DESK01 → shared `child-panel` client → UI01/UI02. `AccessibleUI.overlay_panel_target` binds `child-request-button`; the adapter owns desktop/session details. See [overlay entry qualification](#overlay-entry-qualification). E2E-024 retains real gameplay and request/return outcomes without focus or pointer revelation. | normal request entry and open-overlay history retained; other bindings keep their existing scope |
| DESK13 | A | Set the explicitly bound fixture user's desktop language to one declared installed locale through a supported system API, then independently read back that account's language. Do not change product preferences, another account or the observer locale; no implicit logout/login. Return the confirmed setting and whether session renewal is required. | `AccountLanguage.submit` / `confirm` in [account_language.py](../../tests/e2e/account_language.py), with AccountsService `User.SetLanguage` and independent `Language` API reads in [account_language_guest.py](../../tests/e2e/account_language_guest.py). `check_e2e_desktop_language` qualified Jordan → `zh_CN.UTF-8` on every enabled VM (Ubuntu 26.04) in `20261003T215747Z-6bd9c168`, confirming Ubuntu's normalized `zh_CN` and required renewal. Greeter/account/locale refusals, Chinese FIX06, independent readbacks, preservation, collection and owned cleanup passed. Task 300's recipe owns explicit renewal and public fresh-desktop observation. [Language preparation contract](#chinese-language-preparation-and-desktop-language-setup). | ready for the Jordan Chinese setting binding |

#### Parent lock surface qualification

`check_e2e_lock_surface` passed separate restored command-lock and supplied
Super+L attempts on every selected VM (Ubuntu 26.04), in
`20261008T212721Z-70cc7575` (now outside runner retention).
Provider tuple: Shell `50.1-0ubuntu1.3`, actual locale `en_US.UTF-8`, keyboard
`xkb/us`. Both attempts observed a fresh usable Parent desktop, refused unlocked
entry, observed the curtain, consumed a fresh reveal proof before one Space,
read the Parent challenge, passed wrong-session/ambiguous-window/duplicate-field/
wrong-recipient refusal projections, and independently reread the same challenge.
The command attempt also independently verified its retained locked session.
No password contents, secret authorization or unlock submission are involved.

`AccessibleUI.shell_lock_window` binds the unique window owning the public lock
semantics within its own window boundary. Additional showing Shell windows must
be strict ancestors with no independent lock markers or authentication controls.
The recorded graph must provide unique ancestry and exclusive control ownership;
cycles, shared paths, sibling and descendant windows refuse. Global outside-window
focus/password/dialog/modal rejection remains in `shell_lock_snapshot`.
The surface identity names the actual unlock window, so replacement beneath an
unchanged wrapper cannot authorize reveal. Protected traversal, session recheck,
focused sensitive editable challenge field and fresh input proofs remain required.
Host regressions cover those boundaries and preserve bounded text-free diagnostics.

The required DESK03/04 logout and switch regression passed separate restored
attempts in `20261008T213017Z-fc39a92b` (now outside runner retention).
All four attempts passed private collection, worker shutdown, callback closure,
owned cleanup, baseline restoration and host/source preservation. These
Parent-only attempts supply no child unlock or natural-expiry claim; this capability supplies no
complete-scenario acceptance. Task 042 requalified both lock-surface routes and
DESK03/04 on Ubuntu 26.04 and Fedora 44 in the retained reports below.

#### Parent lock recipient qualification

Task 042's `check_e2e_lock_recipient` passed on every selected VM:

- Ubuntu 26.04: `20261009T001919Z-c214d973` (outside runner retention), Shell `50.1-0ubuntu1.3`, actual locale `en_US.UTF-8`, keyboard `xkb/us`.
- Fedora 44: `20261009T003642Z-42e11ff1` (outside runner retention), Shell `0:50.5-1.fc44`, actual locale `en_US.UTF-8`, keyboard `xkb/us`.

Each restored attempt observed a fresh usable Parent desktop, command Lock,
curtain and guarded reveal, wrong-user/nonempty/unfocused/stale-owner refusals,
an independent challenge, two ordered empty/masked/focused intended-recipient
proofs on the same actual window and field, and a final independent challenge.
Only the public password character count is read; contents are never read.
The controller refuses GDM proofs, changed challenges, reads older than 30 seconds
and failed durable acknowledgements. No lock password or unlock is delivered.
Child success is [qualified separately](#successful-child-unlock-and-retained-gdm-reauthentication-qualification);
other retained-user bindings and provider tuples remain pending.

Both reports also retain the required `check_e2e_lock_surface` (command and
supplied Super+L), `check_e2e_desktop_session` (logout and switch) and
`check_e2e_challenges` regressions. All six attempts per VM passed collection,
worker shutdown, callback closure, owned cleanup, baseline restoration and
host/source preservation. Ubuntu's valid live results were preserved by resume;
Fedora used separate VM-bound named inputs, the verified baseline's RPM package
probe and the shared package-version reader for snapshot attachment. Host
safety/source revalidation passed in
`20261009T003418Z-2f9de057` (outside runner retention).
This fixed capability supplies no complete-scenario or natural-expiry credit.

#### Successful child unlock and retained-GDM reauthentication qualification

Task 043c's `check_e2e_retained_unlock_success` passed two independent restored
attempts per VM: `installed-lock-child-success-qualification` and
`installed-lock-retained-success-qualification`. The original selected reports,
now outside runner retention, also passed all six required regressions:
`check_e2e_lock_recipient`, `check_e2e_lock_surface`,
`check_e2e_desktop_session`, `check_e2e_challenges`,
`check_e2e_fresh_child_allowed` and `check_e2e_unlock`.

| VM | Actual GDM | Actual Shell | Actual locale / keyboard | Original report (outside retention) |
| --- | --- | --- | --- | --- |
| Ubuntu 26.04 | `50.1-0ubuntu0.1` | `50.1-0ubuntu1.3` | `en_US.UTF-8` / `[["xkb", "us"]]` | `20261009T034106Z-2897dec2` |
| Fedora 44 | `1:50.3-1.fc44` | `0:50.5-1.fc44` | `en_US.UTF-8` / `[["xkb", "us"]]` | `20261009T034106Z-adc58695` |

Task 043a requalified both success routes and all six regressions on both VMs;
its [retained eight-check reports](#retained-child-time-restriction-and-greeter-return-qualification)
preserve that unchanged coverage.

`desktop_session.CHILD_UNLOCK_PLAN` and `RETAINED_UNLOCK_PLAN` independently
reuse public Parent preparation of 15 daily minutes, fresh child entry and
`native_activity_entry('activity', child='child')`. Command Lock preserves the
child session. Direct child unlock composes `journey_blocks.lock_challenge`,
two fresh `lock_recipient(account='child')` proofs on the same actual window
and field, `onpc_password::enter_lock_password` and
`onpc_desktop_session::unlock_success`. Unlocked entry, wrong recipients,
replaced challenges and GDM proofs on lock-screen input refuse.

The independent retained route first uses `session_control.observe` with
`return-greeter`, preserving the locked child without another Lock. GDM02
selects that child and opens GDM reauthentication, not the child's lock screen.
`onpc_desktop_session::retained_gdm_unlock` composes the shared
`onpc_gdm::sign_in_challenge` with its distinct `retained-login` identity,
two fresh GDM recipient proofs and sealed single-use input. GDM authenticates
before activating the preserved child session. Proofs from the two surfaces are
never interchangeable.

Both attempts independently observed the original usable activity with the same
PID, public endpoint and synthetic draft, resubmitted in that original window,
then independently compared it again. Every qualification and regression passed
collection, worker shutdown, callback closure, owned cleanup, baseline
restoration, finalization and host/source preservation.

The fresh-child zero-time regression requalified the bounded rejected-GDM
return on both recorded tuples. After the first Escape, a usable account list
finishes cancellation; only a fresh intended-child empty/focused/editable/
sensitive prompt authorizes one additional Escape. The final usable account
list, explicit time denial and no-desktop-access assertions passed without
credential replay. Ubuntu observed `account-list` after the first Escape;
Fedora observed the renewed `child-prompt` and passed the guarded additional
cancellation. The historical denial scope remains [documented above](#fresh-child-time-denial-and-return-qualification).

These results qualify direct child lock-screen success, retained-child GDM
reauthentication success and the pre-authentication locked-child greeter return.
Configured-zero retained denial on GDM and the actual child lock screen are
qualified separately below; visiting from another user's desktop, other provider
tuples, natural expiry and complete scenarios remain separate.

#### Retained-child time restriction and greeter return qualification

Task 043a's `check_e2e_retained_unlock` passed two independent restored attempts
per VM: `installed-lock-retained-denied-qualification` and
`installed-lock-child-denied-qualification`. Both use
`desktop_session.RetainedDenialJourney` with `RETAINED_DENIAL_PLAN` or
`CHILD_DENIAL_PLAN` and `onpc_desktop_session::qualify_retained_denial`.
Public Parent setup supplies 15 daily minutes, normal Parent logout and fresh
child admission. Switch User preserves that child; a fresh Parent login changes
daily/grant time to zero through public controls before the declared denial.

The retained-GDM branch uses `onpc_gdm::sign_in_challenge`, two fresh same-child
GDM03 proofs, sealed single-use input and one submission. It independently
observes the specific time-limit explanation and no desktop access, then uses
`rejected_gdm_return` / `onpc_gdm::return_from_time_denial` to observe a usable
account list. GDM proofs never authorize actual lock-screen input.

The developer explicitly accepted GNOME's native configured-zero
pre-authentication restriction. Shell 50 replaces the password field with
**Screen Time Limit Reached** and **Daily limit for screen time on this device
has been reached. Resume tomorrow.** Observe the same Shell window in the
verified active locked child's session with no password input or desktop access;
return through DESK11 without unlocking, relocking or activating Ignore.
`session_control`'s `child-enter-locked` binding activates the preserved locked
child once through public logind, without authenticating, unlocking or relocking.
`onpc_desktop_session::reveal_lock` consumes fresh curtain/reveal proofs before
one Space; `AccessibleUI.lock_surface('child-lock-time-denied')` independently
reads the complete scoped native restriction. `UiObservations` requires the
immediately preceding reveal guard and the same window identity. This branch
delivers no lock password and makes no authenticated lock/PAM-denial claim.
Wrong-session, stale/replaced/ambiguous surface, incomplete tree, mixed password
input and nonspecific/duplicate-message observations refuse. Positive-time lock
authentication retains its separately qualified recipient/input guards.

Both branches independently observe usable GDM after leaving the denial and
compare `child-retained-locked` before/after identities, requiring the same
preserved locked child. `RetainedDenialJourney` declares those endpoints for
the shared `journey_checks.RetainedSessionJourney`; reusable comparison mechanics
do not depend on the qualification's checkpoint names. Collection, worker
shutdown, callback closure, owned
cleanup, baseline restoration, finalization and host/source preservation passed.
Both selected VMs were rechecked shut down after the complete selection.

| VM | Actual GDM | Actual Shell | Actual locale / keyboard | Historical eight-check report |
| --- | --- | --- | --- | --- |
| Ubuntu 26.04 | `50.1-0ubuntu0.1` | `50.1-0ubuntu1.3` | `en_US.UTF-8` / `[["xkb", "us"]]` | `20261009T052638Z-dfbce8ad` (outside retention) |
| Fedora 44 | `1:50.3-1.fc44` | `0:50.5-1.fc44` | `en_US.UTF-8` / `[["xkb", "us"]]` | `20261009T052638Z-53e9b9e6` (outside retention) |

Each historical report recorded both qualifications' sanitized steps/assertions,
worker completion and cleanup results in `category-001.log`, plus all seven required
regressions: `check_e2e_retained_unlock_success`, `check_e2e_lock_recipient`,
`check_e2e_lock_surface`, `check_e2e_desktop_session`, `check_e2e_challenges`,
`check_e2e_fresh_child_allowed` and `check_e2e_unlock`. Host ownership/credential
safety, worker composition, source and close-out consistency checks passed.
The exact configured-zero child bindings are qualified; natural exhaustion,
other users/provider tuples and complete customer scenarios remain separate.

The shared comparison extraction passed both independent routes again through
`check_e2e_retained_unlock` on Ubuntu 26.04 in `20261009T060915Z-31a3c2c3`
and Fedora 44 in `20261009T060915Z-10f4ba5c` (both outside retention),
including collection, worker/callback shutdown, owned cleanup and restoration.
Provider input and the seven regression routes above were unchanged.
Both denial routes were subsequently rechecked on both VMs as task 044b
regressions; their current retained reports are under
[retained Parent entry](#retained-parent-desktop-and-window-entry).

### Same-desktop window activation

DESK10's [`window_switch.PLAN`](../../tests/e2e/window_switch.py) and
`onpc_feedback_read::run_window_switch` passed `check_e2e_window_switch` in
report `20260928T025758Z-911df7f2`. The guarded slice independently entered
Parent and feedback, activated the supporting viewer and returned twice,
compared the same public window endpoints/PIDs and exact synthetic body/reply,
diagnostic attachment and controls before any new edit. Closing the viewer
then requesting it again refused without launching it. Collection, worker
shutdown, owned cleanup and baseline restoration passed. This is capability
qualification, not complete case 153 acceptance.

The shared worker resolves an active source and inactive destination before
one Alt+Tab, then requires the named destination's independently observed ACTIVE
state. A missing, replaced, wrong-owner or ambiguous window, prompt, lost focus
or uncertain input stops the sequence; there is no fallback shortcut or relaunch.
GTK top-level AT-SPI `Component.GrabFocus` is unsupported, as established by
the host preview check. Parent and feedback retain public owned IDs. The
supporting GNOME Text Editor uses `license_viewer_snapshot`'s scoped provider
owner, sole window and `view` ID, with bounded GPL content verification. It is
launched by a shared command using the installed LICENSE file, never a title.
Switch readiness reacquires both endpoints and the inactive-window proof together
after an incomplete read; no shortcut runs until that complete proof succeeds.
Launch entry, switch readiness, viewer-close absence, final window proof and provider metadata use
bounded read-only waits for a complete public tree. The command invalidates prior observations
and executes once; an uncertain launch or failed result never replays it.
An incomplete tree during provider shutdown never proves absence. The close
result reacquires a complete tree within the existing deadline, then retains
the absent-target refusal and unchanged feedback-window/draft comparison.
The switch-readiness retry passed complete case 152 on the Ubuntu 26.04 test VM in
report `20261003T044953Z-2445cbcf`, including draft preservation, app-exit reset,
collection and owned cleanup.
The observed tuple was Ubuntu 26.04, Text Editor `50.1-0ubuntu0.1`, provider
locale `en_US.UTF-8`, keyboard `[["xkb", "us"]]`. Qualification covers the
two-application same-desktop route; arbitrary switcher order, additional
applications and other viewers remain unqualified. FEED08 export inspection
uses FILE08 and same-dialog readback without activating a supporting viewer.
DESK10 needs no Shell switcher GUI adapter.

### Retained Parent desktop and window entry

DESK09/FLOW01's [`journey_blocks.retained_parent_entry`](../../tests/e2e/journey_blocks.py)
and [`retained_parent.PLAN`](../../tests/e2e/retained_parent.py),
`onpc_parent::open_for_child` retained/same-user branches and
`onpc_desktop_session::qualify_retained_parent` passed
`check_e2e_retained_parent` on both selected VMs. The fixed binding starts from
Jordan's usable desktop and returns through Switch User, GDM's two ordered
recipient proofs and legitimate Jamie authentication. The existing Parent window
has Riley selected, App Limits displayed and enabled 15-minute settings.
An independent supplied Parent entry qualifies the same-user/retained branch.

`AccessibleUI.retained_parent_operation` captures the incoming page, verifies the
selected child without reselection and reaches Screen Limits before reading
settings. Shared `journey_checks.RetainedDesktopJourney` compares caller-declared
immutable before/after snapshots of the page, settings and DESK10 public endpoint/PID
before replying to the worker. Both retained qualifiers bind their own expected
values and Parent/window/session comparison endpoints to that engine.
The read-only `session_control` Parent identity proof independently requires the
same active unlocked desktop session. Current retained qualifications compare
the original public Parent endpoint, page and settings directly, without
launching a supporting GPL viewer or switching foreground windows. Product API
operations require their owned usable surface, not a foregrounding tour.
Normal Parent closure then qualifies absent
window refusal with no relaunch. Wrong child, page, settings, window or desktop,
missing baseline and malformed observations retain host refusal regressions.
The table below records historical qualification that included the viewer tour;
the shortened qualification still needs live verification.

| VM | Supporting viewer version / actual locale / keyboard | Qualification and session regressions | Window-switch, allowance and case 6 regressions |
| --- | --- | --- | --- |
| Ubuntu 26.04 | `50.1-0ubuntu0.1` / `en_US.UTF-8` / `[["xkb", "us"]]` | Historical qualification/session regression passed (report outside retained history) | Historical `20261009T155056Z-67254e9a` (outside runner retention) |
| Fedora 44 | `0:50.1-1.fc44` / `en_US.UTF-8` / `[["xkb", "us"]]` | Historical qualification/session regression; first five checks passed (report outside runner retention) | Historical `20261009T155056Z-a2e0f2a5` (outside runner retention) |

The qualification runs recorded steps/assertions, public comparisons
and cleanup, plus `check_e2e_desktop_session` and both independent
`check_e2e_retained_unlock` denial routes. Fedora's first window-switch preparation
stopped before creating a graphical worker because its generic input lacked an
RPM package. The maintained selector and automatic builder now both use the
selected VM's named inputs; valid existing inputs remain intact. The final
three-check reports qualify `check_e2e_window_switch`'s existing Parent/feedback
and viewer bindings on both tuples, `check_e2e_set_an_allowance_for_a_named_child`
and Parent launch case `6`. All required attempts passed collection,
worker/callback shutdown, owned cleanup, baseline restoration, finalization and
host/source preservation. Both VMs were independently rechecked shut down.
Scoped host guards, worker composition, source and close-out consistency passed;
coverage was regenerated after the case regression. Both retained-child visits
are qualified below; task 198's second-parent management remains separate.
This capability slice supplies no complete-scenario credit.

### Both retained child desktops and explicit entry modes

Task 044 qualifies DESK09/FLOW15 and the retained FLOW01 return through
[`retained_entry.PLAN` / `RetainedEntryJourney`](../../tests/e2e/retained_entry.py)
and `onpc_desktop_session::qualify_retained_entry`. The reusable declaration and
worker are `journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop`;
`session_control.entry_identity` rejects incompatible declared sources without
repairing state. The fixed history independently enters Riley and Jordan,
records their native activities, checks same-user entry and wrong-mode refusal,
returns from each child's desktop to the other's retained desktop, and revisits
Riley independently. This also qualifies DESK01/03's supporting usable-desktop
and Switch User bindings for those two children. Session identities and original public activity/window
fingerprints must match before a new activity action; both original windows
remain usable. Riley additionally locks and unlocks normally.

The same history returns from Riley to Jamie's original Riley-selected Parent
window, preserving its desktop identity, endpoint/PID, App Limits page and saved
settings. FLOW01 explicitly reaches Screen Limits for its settings read without
reselection or a foreground-window tour. The current qualifier compares the
original public Parent endpoint and values directly; the shortened sequence
still needs live verification. After public zero-time
configuration, retained Riley GDM authentication produces the specific denial,
and native lock entry produces the time restriction without secret delivery.
Both return routes preserve the same locked child desktop.

| VM | Retained-entry qualification and required session regressions | Final window-switch regression |
| --- | --- | --- |
| Ubuntu 26.04 | Six selectors passed (report outside retained history) | Passed in `20261009T202254Z-b461cfd3` (report expired under retention) |
| Fedora 44 | First five selectors passed (report outside runner retention); the original final window-switch failure is superseded by the adjacent pass | Passed in `20261009T202254Z-570d98e5` (report expired under retention) |

The historical retained selections were `check_e2e_retained_entry`, `check_e2e_retained_parent`,
`check_e2e_retained_unlock_success`, `check_e2e_retained_unlock`,
`check_e2e_desktop_session` and `check_e2e_window_switch`. At that close-out the
first five remained valid unchanged; only the viewer-close observer was repaired and requalified on
both VMs. It now discards incomplete shutdown trees in its existing bounded
read-only wait, retaining absence, absent-target refusal and unchanged feedback
draft assertions without replaying Close. The supporting viewer tuples are
Text Editor `50.1-0ubuntu0.1` on Ubuntu and `0:50.1-1.fc44` on Fedora, both
`en_US.UTF-8` with `[["xkb", "us"]]`.

The retained-child lock boundary uses the maintained
[locked-session focus synchronization](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement)
with the unchanged foreign-recipient refusal. Temporary compositor/focus probes
and dispatcher routes are removed; diagnostic replays supply no acceptance.
Affected host safety/composition, source, child lifecycle and package build checks
passed. All accepted runs completed collection, worker/callback shutdown, owned
cleanup, baseline restoration and finalization; both VMs were independently
rechecked off. Scope remains these finite child/Parent bindings. Other-parent
management and complete scenarios remain pending.

Both retained selectors passed after extraction of their comparisons into
`journey_checks.RetainedDesktopJourney` in Ubuntu run `20261009T225326Z-5e8bd6f9`
and Fedora run `20261009T222838Z-7052a5d9` (reports outside runner retention).
These runs covered the stated Parent/child bindings and assertions, with completed
collection, worker/callback shutdown, owned cleanup and baseline restoration.

### Personal-language selection

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| LANG01 | C | Observe the owned frontend's untouched first-run language chooser or open its public Preferences chooser; read the checked choice and native names, select one declared candidate, apply Save or Cancel once, and independently observe closure, readiness, translated labels and the retained choice after reopening. Callers own language/account values, relaunches, isolation and policy comparisons. | `AccessibleUI.language_scope`, `open_language_preferences`, `choose_language`, `save_language`, `cancel_language` and `language_save_completed` in [accessible_ui.py](../../tests/e2e/accessible_ui.py); installed observations `read_parent_language`, `parent_language_management`, `parent_language_operation` and `parent_language_state`, registered through `ui_observations.py`; finite literals/recipe in [parent_language.py](../../tests/e2e/parent_language.py) and shared worker `onpc_parent::language_selection` / `qualify_language`. The `initial-language` launch result observes first presentation without the ordinary `parent-window` automatic Save; lifecycle observations use `parent-language-state`. Visible page titles and accessible switch names are independently compared; stale chooser snapshots are reacquired under the original bounded deadline without replaying input. `check_e2e_parent_language` passed on Ubuntu 26.04 in `20261004T092815Z-1784595b`: untouched English first choice and four native names, English/German/Simplified Chinese/Hebrew Save and checked-choice/text readback, Chinese Cancel preserving German, normal relaunch persistence, unchanged selected child/zero allowance/app-policy projection and wrong-entry refusal. Required case 6 passed in `20261004T093246Z-b19110a7`; collection, owned cleanup, baseline restoration and preservation passed. The fixed Chinese kiosk Save binding remains qualified under [Chinese language preparation](#chinese-language-preparation-and-desktop-language-setup). | pending overall; stated Parent, fixed Jordan kiosk, fixed Riley overlay and Jordan/German–Riley/Hebrew station restoration/approver isolation bindings qualified (see below); Parent inherited dialogs qualified below; other isolation bindings, panel, other inherited dialogs and Hebrew logical text, countdown and complete-case acceptance remain separate |

The dedicated-kiosk LANG01 fixed Jordan binding passed
`check_e2e_kiosk_language` on Ubuntu 26.04 in `20261004T103336Z-73d60bd2`:
untouched English first choice and four native names,
English/German/Simplified Chinese/Hebrew checked-choice and translated
visible/accessibility chooser/form observations, Save, Chinese Cancel retaining
German, normal re-entry with German retained, and unchanged request/policy
projections. The required fixed Chinese native-authentication regression passed
all 14 assertions in `20261004T104017Z-b60581d0`. Collection, worker shutdown,
callback closure, owned cleanup, baseline restoration, finalization and
host/source preservation passed in both runs. Task 300h is complete.
`read_kiosk_language` shares the bounded owned chooser reader;
`kiosk_language_form` independently reads visible/accessibility text and REQUEST03
values, and `kiosk_language_policy` compares public Parent settings, balances and
application rows. `journey_blocks.language_selection` and
`onpc_parent::language_selection` share chooser mechanics; `kiosk_language.PLAN`
and `onpc_request_flow::kiosk_language` own this finite qualification.
The untouched read reuses `initial_kiosk_child` within the chooser's complete
owned snapshot, preserving the fixed Chinese reader's UID/uniqueness/visibility
guards without calling Parent-only child-control helpers. Existing
`CHINESE_LANGUAGE_OPERATIONS` only supplies the fixed Chinese Save/form result;
the Parent reader does not qualify another application.
Selected-child restoration/isolation, panel,
inherited dialogs, Hebrew logical text, countdown and translated approval results remain
separate bindings owned by the personal-language decomposition below.

Task 300i qualified the fixed Riley child-overlay LANG01 binding.
`read_overlay_language` and
`overlay_language_operation` use `language_scope('overlay')` to require the
child application and active Riley session. Untouched and reopened chooser reads
bind Riley's selected public UID; `kiosk_language_form(..., overlay=True)` shares
the translated REQUEST03 reader without automatically completing startup.
`overlay_language.PLAN` / `OverlayLanguageJourney` and
`onpc_request_flow::overlay_language` compose shared `language_selection` and
direct `overlay_entry` operations. The argument-free
`check_e2e_overlay_language` passed on Ubuntu 26.04 in
`20261004T115946Z-5cd0363a`: untouched English first presentation and four native
names, English/German/Simplified Chinese/Hebrew Save with independent
visible/accessibility text and checked-choice readback, Chinese Cancel preserving
German, unchanged fixed request values, normal German command-relaunch without
startup setup and final unchanged saved Parent allowance/enablement/app rows.
The required shell-panel and kiosk-language regressions passed in
`20261004T114913Z-24503104` and `20261004T115236Z-05dd2d98`.
All three passed collection, worker shutdown, callback closure, owned cleanup,
baseline restoration, finalization and host/source preservation. The refreshed
overlay report replaces its expired earlier acceptance evidence.
This qualifies only the fixed Riley surface; selected-child restoration/isolation,
panel translation, inherited dialogs, Hebrew logical text, countdown, translated approval
results and complete-case acceptance remain separate.

Task 300j qualified the REQUEST04/LANG01 selected-child station binding through
`check_e2e_kiosk_language_restoration` on Ubuntu 26.04 in
`20261004T170801Z-0fa8c3c1`: Jordan/German and Riley/Hebrew restoration,
approver independence, fresh kiosk re-entry, both unchanged final public
policy/time/app projections and Parent's retained English choice. Each child's
1800-second request, hidden custom text and excluded soft apps remained intact.
`select_kiosk_account`, `kiosk_request_form` and `kiosk_language_form` carry
explicit pre-input language, selected-child identity and post-selection language
bindings. Selection discards its confirmed UID snapshot before independently
observing readiness, so a mixed-time traversal cannot suppress startup setup.
`kiosk_language_restoration.PLAN` / `KioskLanguageRestorationJourney` and
`onpc_request_flow::kiosk_language_restoration` retain finite per-child assertions
while composing shared account, chooser and Parent-entry mechanics.

The retained Parent return uses `onpc_parent::launch` with a fresh desktop receipt
and `switch-parent`'s independent window proof. Final Riley selection uses
`journey_blocks.custom_child_selection` and
`onpc_allowance_boundaries::select_child` through UI15's canonical API setter
on `parent-child-selector`. There is one product selection route. Retained
`open`/`focus`/`selected` stage names mean offered-choice observation, API value
selection and independent selected-result observation; they require no popup
or keyboard focus. The shared helper reads selected UID and loaded controls.
Real GTK coverage preserves the retained-window boundary after input to another
owned preview, refusal and terminal uncertain input, without popup/focus steps.

Required fixed-kiosk-language, English selector and overlay-language regressions
passed in `20261004T171755Z-c5bff9fc`; case 6 passed separately in
`20261004T174440Z-9e1c38e7` after a pre-VM ownership refusal in the combined run.
All accepted runs passed collection, worker shutdown, callback closure, owned
cleanup, baseline restoration and finalization; qualification/regression source
preservation passed. Required reports were verified retained in the runner's
report directories after final host validation and export rotation.
Host validation passed 2,364 unit checks, source and twelve GTK checks; coverage
was regenerated after case 6. This installed-snapshot capability supplies no
latest-install Chinese, panel/dialog/RTL/countdown/approval-result or
complete-language-scenario acceptance.

Task 306a qualified Jamie's Chinese Parent language across enabled Riley/Jordan
selection on Ubuntu 26.04 in `20261005T064245Z-f3e34714` through
`check_e2e_parent_language_isolation`. Each child has its own immutable English
60-minute policy/name/balance capture. Chinese Riley → Jordan → Riley reads
before and after normal relaunch prove selected UID, unchanged account/app names
and policy, checked Chinese choice, zero grant and balances within the declared
600-second elapsed bound. The untouched reopened window reads Jordan, the first
alphabetically listed child, without first-run setup before explicitly selecting
Riley. Parent language persistence does not imply child-selector persistence.

`AccessibleUI.parent_language_state(child=..., enabled=True, language=...)`
adds the explicit English/Chinese bindings while retaining the disabled/zero
reader. `child_selection` and `parent-language-{riley,jordan}-selected` prove
selected UID/name and loaded controls independently of the English-only settings
reader. `time_explanation` / `reach_time_explanation` carry the declared language;
`app_rows(include_names=True)` reads public names with the complete policy rows.
`ParentLanguageIsolationJourney` / `ISOLATION_PLAN` in `parent_language.py` and
`onpc_parent::qualify_language_isolation` own the finite qualification.
Required Parent-language and kiosk-restoration regressions passed in
`20261005T064855Z-182479a8` and `20261005T065436Z-d38a43df` respectively.
All three runs passed collection, worker shutdown, owned cleanup, baseline
restoration, finalization and host/source preservation. Host validation passed
2,621 unit checks, source and six GTK checks. Shared Parent launch mechanics are
unchanged. This qualifies only the stated enabled binding, not complete account/
offline scenarios, Hebrew Parent policy readback or presentation/dialog matrices.

#### Enabled Parent Hebrew policy qualification

Task 307c qualified the fixed Riley enabled 60-minute Parent English → Hebrew →
English history through `check_e2e_parent_hebrew_policy` on Ubuntu 26.04 in
`20261005T192822Z-66af915e` (its report has since rotated under retention).
Normal Parent controls establish one immutable English UID/account/application-name,
complete application-policy and balance capture. Two independent public read
entries per language prove closed chooser, translated management labels and
accessible switch name, unchanged enabled control and saved allowance, zero
grant, positive daily balance at most 3600 seconds and equal daily/total balances.
Each later read is compared against that original capture within the declared
600-second elapsed bound and two-second refresh/formatter tolerance. Hebrew
compact duration text is decoded into numeric balances, not substituted for
policy preservation.

`parent-language-riley-enabled-he` and
`AccessibleUI.parent_language_state(child=..., enabled=True, language='he')`
add only the finite Riley/Hebrew enabled binding; English/Chinese bindings and
the disabled-zero reader remain intact. `time_explanation` / `duration_projection`
support the literal Hebrew public balance format. `language_composition.language_policy`
owns immutable comparisons; `ParentHebrewPolicyJourney` / `HEBREW_POLICY_PLAN`
in `parent_language.py` and `onpc_parent::qualify_hebrew_policy` own the finite
qualification. Shared `onpc_parent::language_presentation_roundtrip` now supplies
the translated chooser, Save/reopen/Cancel and retained-choice results to both
this qualification and the existing chooser qualification. The historical
Cancel/Tab/Save focus sequence is no longer a test condition.

Required regressions passed:
enabled English/Chinese policy isolation (`20261005T193305Z-d8d2ea5b`; its report has since rotated),
Hebrew chooser (`20261005T192024Z-8e416119`; its report export has since rotated), and
public time explanation (`20261005T192506Z-fb7e084e`; its report has since rotated).
All four runs passed collection, worker shutdown/callback closure, owned cleanup,
baseline restoration, finalization and host/source preservation. The retained
qualification and isolation runs replace passing runs whose reports expired;
the chooser report and detailed result were exported before execution retention
rotated them. Required reports were verified retained at task 307c's close-out;
those report/export paths are now absent and these IDs preserve historical scope.
Scoped host
unit/safety/source and
eight real GTK checks
passed, including Hebrew allowance/expanded numeric text and English/Chinese
regressions. This capability supplies no visual, inherited-dialog, approval or
complete-case acceptance credit.

Task 306 completed E2E-054 `account-offline`, case 255, on Ubuntu 26.04 in
`20261005T162608Z-4a7cb85e` (the report has since rotated under retention).
All 26 assertions passed: Jamie/Chinese Parent, Jordan/German station and
Riley/Hebrew station/overlay retain independent choices through offline account
and approver changes, Cancel, normal relaunches, fresh kiosk entry and a renewed
child desktop session. Both children's Custom `1.25`, 75-second requests and
included soft apps persist; each immutable policy/name/app capture is compared
under the declared elapsed bound before and after independent Internet recovery.

`language_persistence.PLAN` and `onpc_language_persistence::run` own the finite
history. Shared `language_composition.PublicLanguageJourney` composes language
readbacks, request comparisons and `InternetIsolation`; offline entry/recovery
use the public enabled Parent policy bindings. `AccessibleUI.language_history_request`
supplies guarded public form actions. Station history operations and Jordan's
text binding use the kiosk session; overlay operations use Riley's child desktop.
The shared observer preserves diagnostic lines separately from terminal replies.

Required regressions passed:
Parent language isolation (`20261005T155822Z-88a6b7fe`),
kiosk language restoration (`20261005T160451Z-31e5762b`; both exports have since
rotated under retention) and overlay language
(`20261005T161240Z-fe4f9c67`; its export has also rotated). All four acceptance slices passed collection,
worker shutdown, owned cleanup, baseline restoration, finalization and
preservation. The retained case run replaces an earlier passing run whose report
expired under retention. Host validation passed 1,555 unit checks, source and
the real GTK nondefault-request history check. This completes only the stated
account/offline history; Hebrew presentation, inherited dialogs, translated
approval, panel/countdown and expiry acceptance remain with their queued owners.

Task 307a qualified the fixed Parent English → Hebrew → English chooser history
on Ubuntu 26.04 through `check_e2e_parent_rtl` in
`20261005T171218Z-0b4a41da`. Each language has two independent chooser visits:
bounded AT-SPI logical heading text, accessible native names and checked choice,
public Cancel focus followed by normal Tab and independent Save focus,
Save/reopen/Cancel, and unchanged selected child, disabled zero allowance and
application-policy projection. Wrong-entry refusal also passed.
That historical run used `AccessibleUI.language_presentation` and
`parent-language-presentation-*` operations for focus observations. Current
`ParentRtlJourney` / `RTL_PLAN` in `parent_language.py` and
`onpc_parent::qualify_rtl` use the shared language reader and
`language_presentation_roundtrip`; the focus-only operations are removed.
Required `check_e2e_parent_language` regression passed in
`20261005T172018Z-01fd8580`, including all four saved languages, Chinese Cancel
preserving German, normal relaunch and unchanged policy. Both runs passed
collection, worker shutdown, owned cleanup, baseline restoration, finalization
and preservation. Both report exports have since rotated under retention.
This qualifies only the Parent chooser binding. Other dialogs and surfaces,
enabled-state Hebrew readback and complete scenarios remain separate. The
developer removed visual review for this and future tasks while retaining the
geometry prohibition; this evidence supplies no pixel-rendering acceptance.

#### Parent inherited dialog qualification

Task 307b qualified Parent About/feedback through
`check_e2e_parent_dialog_language` on Ubuntu 26.04 in
`20261005T183953Z-3eaae8af` (the report has since rotated under retention).
The fixed English → Hebrew → English history observes two independent entries
per dialog and language, translated public logical Text and accessible labels,
unchanged product/license names, forward/backward Tab focus, owned closure and
wrong-entry refusal. The exact body `שלום Alex 75` and reply
`rtl-check@example.invalid` are seeded once, then independently compared before
new input on every reopen across public Preferences language changes.
Selected child, disabled zero allowance and application policy stay unchanged.
Send and external links are never activated; visual acceptance remains excluded.

`AccessibleUI.parent_dialog_presentation` / `parent_dialog_operation` reuse
`open_about`, `open_feedback`, `feedback_snapshot` and the `synthetic-rtl`
projection. `onpc_text::replace_text` supplies the declared normal Unicode input.
The removed `onpc_parent::dialog_navigation` exercised both keyboard directions;
current consumers read the translated dialog and retained draft directly.
Host previews execute the shared dialog input/read blocks through
`gui_blocks.run_block`. `ParentDialogLanguageJourney` /
`DIALOG_PLAN` and `onpc_parent::qualify_dialog_language` own the fixed qualification.
Qualifications use `onpc_parent::dialog_visit`; case 256 uses `dialog_use`, whose
opening already reads the contents. Both share `dialog_close` for owned closure
and independent absence. Their historical keyboard
direction coverage does not require traversal in current consumers.
Callers retain finite visits, language and draft comparison endpoints.
This extends UI16, ABOUT01, FEED01/03 and FEED10(dialog) only for the stated
Parent binding; it does not qualify translated Privacy or another frontend.

All required regressions passed:
information links in `20261005T182127Z-060b67e7`, feedback read in
`20261005T182410Z-ffae3fc4`, text replacement/clearing in
`20261005T182625Z-db844a25`, and Privacy/draft preservation in
`20261005T184729Z-e87250e4`. These report exports have since rotated under retention.
All five runs passed collection, worker shutdown, owned cleanup, baseline
restoration, finalization and host/source preservation. Host GTK history and
scoped unit/safety/source checks passed. This capability supplies no complete-case credit.

#### Complete Parent Hebrew history

The completed evidence below describes the original history. Current case 256
uses one necessary dialog visit per language, saves only the actual Hebrew and
English changes, and preserves the original policy and draft. Chooser
reopen/Cancel and link-control matrices remain UI coverage; product keyboard
traversal is no longer an acceptance requirement in either layer.

Task 307 completed E2E-055 `parent-hebrew`, case 256, on Ubuntu 26.04 in
run `20261005T195414Z-0e17bba7` (subject to runner retention).
All 15 assertions passed: Jamie's Parent English → Hebrew → English history
retains Riley's enabled 60-minute allowance, zero grant, original account/app
names and complete application policy. Public daily/total balances are compared
against the original immutable English capture within the declared 600-second
monotonic bound and two-second refresh/formatter tolerance. Each language has
Preferences Save/reopen/Cancel with Cancel→Save focus, inherited About/feedback
logical Text/labels and both keyboard directions. The exact body `שלום Alex 75`
and reply `rtl-check@example.invalid` are seeded once and independently compared
before later input through normal closure, language changes and reopening.

`parent_presentation.PLAN` and `onpc_parent_presentation::run` declare the finite
history and comparison endpoints. Shared `language_composition.language_policy`
and `public_language_value` preserve immutable policy/draft captures; the latter
rejects changed or missing complete public values and capture replay before a
durable worker reply. Shared `onpc_parent::language_save`,
`dialog_use` / `dialog_close` and `onpc_text::replace_text` own normal input and
independent results. The case does not inherit qualification controllers.

Required regressions passed:
Parent dialog language, `20261005T200314Z-74a53e25`, and
enabled Parent Hebrew policy, `20261005T201150Z-adf84902` (subject to runner retention).
All three runs passed collection, worker shutdown/callback closure, owned cleanup,
baseline restoration, finalization and preservation. Host unit/controller/recorder/
actual-worker refusal checks, source and four real GTK checks passed; coverage
was regenerated. All three acceptance reports were retained at close-out after the final
289-check host consistency pass and Markdown validation.
This completes only the Parent history. Other frontend/dialog,
translated approval, panel/countdown and expiry bindings remain separate.
Visual review remains excluded and geometry prohibited.

The remaining personal-language bindings follow the
[acceptance decomposition](E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition).
The Parent chooser and inherited dialogs are qualified above; this allocation supplies no acceptance
for the remaining bindings:

| Pending binding | Qualification task | Complete scenario |
| --- | --- | --- |
| Installed Hebrew logical text and labels | Parent chooser/dialogs and finite enabled policy qualified by 307a/307b/307c; complete Parent case 256 passed; other surfaces require separate qualification | 308–310 |
| Hebrew overlay product approval/result with ordinary native Shell authentication | 308b | 308 |
| Overlay Hebrew/restored-English request with unchanged choices and original activity | 308a | 308 |
| Restricted kiosk Hebrew/restored-English request and child's language across approver changes | 309a | 309 |
| Remaining-time and request information refresh after overlay language changes and session resume | 310a, using qualified panel reading and retained-session operations; tooltip/menu text matrices remain UI scope | 310 countdown/natural expiry |

Parent enabled-state readback is qualified for English/Chinese and the finite
Riley/Hebrew 60-minute binding above. Complete Parent task 307 passed its own
policy and inherited-dialog comparisons; prerequisite qualification alone supplies
no complete-case credit.
Feedback entry/readers include the stated Parent English/Hebrew binding; shared IDs do not establish translated child/station
routes. Follow the [no-visual presentation acceptance rule](../Mandates/UI-Automation-Mandate.MD#input-and-independent-results);
Missing public text or identity remains an explicit gate in these tasks, not
claimed readiness. Repeated overlay/station About and error-report tours are
outside 308/309. Parent task 307 retains the mixed-script ordinary feedback draft
history; error-report drafts end on closure under the
[specification](../Specification.md#feedback-and-error-reports).
The existing fixed countdown observations do not qualify translation,
minute/final-second progression or natural expiry; retain those earlier queued
capabilities before composing 310. No future selector listed in these briefs is
registered merely by this table.

### Reminder controls and notification qualification

The shared request Preferences controls and repository-owned reminder banners
use the [Application UI API](Application-UI-API.md#shared-request-form-and-language-chooser), including the
[ChildUI notification surface](Application-UI-API.md#child-panel). Their
installed operations remain **pending**; implemented product controls and host
UI checks do not establish qualification. The queue extracts these bounded
bindings before the complete reminder cases:

| Task | Exact qualification slice |
| --- | --- |
| [312a](E2E-Tasks/312a-overlay-reminder-editing.md) | Riley overlay reminder CRUD, main Save/Cancel and saved empty-list readback |
| [312b](E2E-Tasks/312b-kiosk-reminder-binding.md) | Selected-child kiosk reminder save/readback, overlay continuity and account isolation |
| [311a](E2E-Tasks/311a-reminder-fullscreen-preference.md) | Saved account-wide `reminder-show-in-fullscreen` boolean; no notification-delivery credit |
| [311b](E2E-Tasks/311b-natural-reminder-observation.md) | Naturally emitted ChildUI body, canonical seconds, urgency and natural-lock removal; public-value contract gate remains explicit in the brief |
| [311c](E2E-Tasks/311c-fullscreen-reminder-visibility.md) | Owned banner visibility/suppression with task 129's genuine fullscreen game; independent of urgency |

`PreferencesDialog` implements reminder editing and the fullscreen switch in
`kiosk/oh_no_parent_control_kiosk/preference_dialog.py`. Child notification
content and surface flags are mapped by `GnomeApplicationUiAdapter` in
`child/gnomeApplicationUiAdapter.js`; `child/reminderBanner.js` owns the banner,
outside Shell's generic message tray. Qualify these public mappings through
shared facade operations; no generic Shell notification adapter is a prerequisite.
Missing independent public identity or visibility remains a qualification gate.

The [saved-reminder case 312](E2E-Tasks/312-child-reminder-preferences.md) and
[warning case 311](E2E-Tasks/311-remaining-time-notifications.md) retain their
separate complete histories. Case 311 reuses task 135a's real verified upgrade
and task 129's fullscreen game. No selector, numeric inventory binding,
installed qualification or acceptance is supplied by this planning record.

### Daily allowance selection

PARENT06 uses one Application UI API sequence in every UI/E2E consumer:
set `parent-daily-limit-selector` to the offered canonical token, then
independently read the saved allowance. For Custom, select `custom`, set
`parent-custom-daily-limit` text and invoke its ordinary validation action
when the caller's commit path requires it. Saving remains a separate public
result. `journey_blocks.allowance_selection`, `onpc_allowance_selection::select`
and `tests.support.gui_blocks.select_allowance` share
`AccessibleUI.select_allowance`; the retained `allowance_keyboard` name
exposes compatibility input/result boundaries without native input.

The API resolves the current Parent surface, selected child and enabled selector.
It requires no popup, focus, pointer bounds, native transform or compositor input
session. Preset/custom, rejection, named-child and rapid-save callers vary finite
values and assertions while reusing this block. The
[mandatory route](../Mandates/UI-Automation-Mandate.MD#application-ui-api)
also applies after work in another window and after a product restart.

Earlier native-input attempts are historical evidence only. They observed lost
selector input, failed stream binding, a retained overview input grab and
window-offset/pointer-target mismatches; expected saved values did not match
the displayed values in those failures. Those mechanics have been replaced by
the API route. The final historical host stress run retained exact latest-save,
Custom-to-preset and custom validation assertions. Historical run IDs (subject
to runner retention):
`20261005T183200Z-6f124ff4`, `20261005T185942Z-a1354093`, `20261005T192353Z-642681c0`, `20261005T204924Z-140e6d45`, `20261005T204607Z-9cf327f3`, `20261005T205003Z-5d6ddb1f`, `20261005T205534Z-f2e93578`, `20261005T213533Z-082cdd28`, `20261005T215528Z-df2ccd55`, `20261005T221436Z-ffcbb9d7`, `20261005T224722Z-a1d943d6`.

### App-grid search and Parent launch

PARENT01 owns ordinary direct-command entry. SEARCH05/06 own the explicit
app-grid integration bindings under the
[ordinary app-entry mandate](../Mandates/UI-Automation-Mandate.MD#ordinary-app-entry).
The same Parent control inventory below serves both entry routes.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| SEARCH01 | C | Open the app grid/Overview with Super-A and observe an enabled, editable, empty search field. | `AccessibleUI.shell_search_field` resolves the sole showing, sensitive, editable field inside one complete, uniquely owned Shell snapshot. Fresh Parent entry qualified in `check_e2e_shell_search_results`; independent standard-account entry qualified in `check_e2e_shell_search`. [Qualified scope](#search-and-standard-sign-in-contracts). Other routes remain pending. | pending; fresh Parent/standard branches ready |
| SEARCH03 | C | Enter the complete app-name query once into an already open, empty, focused search field without launching; independently read the exact final query. | `onpc_parent::enter_search_query` retains the fresh recipient proof and bounded typing pace; `AccessibleUI.search_query` reads the result. Historical Parent/standard qualifications used split input; current consumers omit the intermediate first-character check. [Qualified scope](#search-and-standard-sign-in-contracts). Other queries remain pending. | pending; Parent/standard query branches ready |
| SEARCH04 | C | Observe the declared search result after scoped provider resolution: a launchable app, or the complete exact query with stable absence of the app launcher and management window. Unrelated web suggestions are not validated on any distro. Repository-owned windows retain their IDs. | `AccessibleUI.launchable_result` qualified the unique showing, sensitive Parent result and unrelated-binding refusal in `check_e2e_shell_search_results`. `AccessibleUI.search_absence` historically qualified the standard-account exact web description and two-second complete launcher/window absence in `check_e2e_shell_search`; the developer removed web-suggestion validation on 2026-10-07. [Qualified scope](#search-and-standard-sign-in-contracts). Other apps remain pending. | pending; Parent launchable and standard unavailable branches ready |
| SEARCH06 | C | Open Overview, resolve the empty search field by a qualified provider adapter, semantically focus it and independently observe focus before typing the registered app name once. Read back the complete query, then resolve and focus its launchable result. Independently observe result focus as the recipient guard before Enter. | `onpc_shell_search::run` and `AccessibleUI.focus_search_result` check the final query and launchable result. The whole-query route passed in case 3 (run `20260922T212944Z-ad23b979`, subject to runner retention); the historical split-query qualification is recorded below. [Qualified scope](#search-and-standard-sign-in-contracts). Other entries and queries remain pending. | pending; fresh Parent query branch ready |
| SEARCH05 | C | Launch a named app from the app grid and observe its expected opening window. The search route is an explicit argument. | `onpc_parent::open_from_app_grid` composes SEARCH06 and `launch_search_result(journey, proof, expected)`. Both the composed administrator launch and independently supplied `app-grid` management entry passed `check_e2e_parent_search_launch`, with owned window readback, normal close and wrong-entry refusal. Host checks cover wrong/stale proofs, wrong owner/result and uncertain-input non-replay. FIX02's `fixture-requested`→empty commit remains host-checked pending live validation. [Qualified scope](#search-and-standard-sign-in-contracts). | pending; administrator management bindings ready |
| PARENT01 | C | Invoke `oh-no-parent-control-parent` directly as the active desktop user and independently observe the declared management window or access denial. Mandatory for ordinary Parent setup/reopening; no child is selected implicitly. App-grid discovery tests explicitly use SEARCH05/06. | `onpc_parent::launch` consumes the desktop proof, submits the fixed command through `AccessibleUI.launch_parent_command`, then observes `parent-window` or `management-denied`. Case 2 qualifies its fresh `reboot-desktop` proof; case 6 requalified the default fresh standard denial/return binding in run `20260924T234847Z-41112953`. The fresh Parent desktop binding also passed in case 151. No terminal/search input. [About scope](#about-block-contracts) and [clean installation](#clean-installation-journey). | ready for fresh Parent/standard and post-reboot Parent bindings; a second same-session Parent launch with one-window readback passed in case 159 (`20260929T070054Z-c0f58f19`); other entries pending |
| PARENT02 | C | Set Parent's child selector to the canonical eligible UID, verify the selected identity and wait for that child's controls. | `onpc_parent::select_child`, `AccessibleUI` and UI15 share the `parent-child-selector` API setter and independent `selected_child` readback. Child/existing/new/returned bindings retain their finite identities. [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| PARENT03 | C | Read the current selected child's identity, screen-limit switch, allowance and remaining-time section as a sanitized observation. Do not change selection; disabled allowance controls remain readable. | `AccessibleUI.settings(child)` reads the explicit child, switch and duration-label projection and reveals the remaining-time section. When the selector displays `Custom value`, read bounded whole minutes from the identified custom editor; retain the numeric value in the snapshot, never just the mode label. Scenario expectations remain in `parent_discovery.PLAN`, not the adapter. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| PARENT04 | C | Select Screen Limits or App Limits and require that page's named usable controls. | `AccessibleUI.parent_page(child, page)` checks the displayed child, selects one named page, then observes its controls. Reacquire the window after transition and reuse that local root for search/filter reads. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| PARENT05 | C | Select a daily preset through PARENT06 and independently read the saved allowance. Custom selection makes the ordinary editor available. | `AccessibleUI.allowance_preset` / `custom_allowance` delegate to `select_allowance` and PARENT08. Reload checks retain selected-child and reopened saved-value assertions. Historical qualification reports: `20260925T181548Z-2eeb40fa`, `20260926T031042Z-c0e70792`. | API implementation; historical saved-value and persistence evidence retained |
| PARENT06 | C | Set `parent-daily-limit-selector` to an offered canonical duration or `custom`; set custom literal text and invoke normal validation. Observe saving separately. | `journey_blocks.allowance_selection`, `onpc_allowance_selection::select`, `AccessibleUI.select_allowance` and `gui_blocks.select_allowance` share the API route. Retained `allowance_keyboard` naming supplies input/result boundaries without native input. Custom, rapid-save, per-child and restart assertions remain in their existing callers. Historical qualification reports: `20260925T181548Z-2eeb40fa`, `20260926T031042Z-c0e70792`, `20260929T030021Z-d7980dce`, `20260929T070054Z-c0f58f19`, `20260929T054754Z-ff2b12fc`. | API implementation; historical saved-value and persistence evidence retained |
| PARENT08 | C | Wait for the declared saved, rejected or unavailable result and independently read the final value. Preserve selected-child identity, rejection recovery and last-change-wins ordering; intermediate Saving and control inhibition are not acceptance. | `AccessibleUI.parent_save_snapshot` through `ParentToggleJourney` / `onpc_parent_toggle::run`; `check_e2e_parent_save` qualified enabled/disabled saved snapshots, independent entry, wrong-child refusal and owned cleanup. Snapshots verify the selected UID/label, reject visible error reports and require expected control availability. `AccessibleUI.invalid_allowance` observes the exact draft and public rejection description for empty/abc/-1/0.5/1440/1441. `check_e2e_allowance_boundaries` qualified each rejection from saved 15, then independently read unchanged saved and reopened-editor values in run `20260925T181548Z-2eeb40fa`, with collection, cleanup and baseline restoration. Complete case 158 repeated the entire rejection table and final Parent reopen persistence in `20260926T031042Z-c0e70792`, with all outcome domains and baseline restoration passed. `UiObservations.observe_accessibility_input(..., mode='save')` / `AccessibleUI.parent_save_events` qualified two independent disabled-to-enabled transitions, wrong-entry refusals, event-derived conflicting-control inhibition/recovery and independent saved snapshots through `check_e2e_parent_save_trace` in `20260929T022732Z-a3624dd4`; collection, cleanup and baseline restoration passed. `UiObservations.observe_accessibility_input(..., mode='custom-save')` / `AccessibleUI.parent_save_events(custom=True)` / `read_custom_trace_draft` qualified two enabled rapid-edit entries, event-derived inhibition/recovery with usable editor/picker, wrong-child/surface/disabled refusal and independent saved readback through `check_e2e_custom_save_trace` in `20260929T030021Z-d7980dce`; the affected toggle regression passed in `20260929T030347Z-821a11a0`. Case 57 observes saved limits-off; other result states remain pending; complete case 159 passed its save-order composition in `20260929T070054Z-c0f58f19`. A terminal snapshot makes no transient-saving claim. The same named-child qualification bound Jordan's rapid-save event-derived inhibition/recovery, usable editor/picker and Riley's independent custom 7 saved readback; wrong-child refusal remained before input or trace. `AccessibleUI.parent_app_save_snapshot` additionally qualifies the App Limits terminal controls after valid match Save/Cancel; see [Match editor Save and Cancel](#match-editor-save-and-cancel). | pending overall; saved and custom-validation snapshots qualified; historical transition samples retained as evidence only |
| PARENT20 | C | Read an already expanded, showing remaining-time explanation for the explicitly selected child. Return daily, one-time and total values, public display precision and observation time. Perform no navigation or expansion. | `AccessibleUI.time_explanation(child)` reads the selected UID/label and showing `parent-time-status`, `parent-time-explanation` and collapse control in one complete public snapshot. `duration_projection` returns each bounded compact text, seconds and one-second display precision; `observed_monotonic_ns` timestamps the read. `UiObservations` validates the transport projection. `time_explanation.PLAN` / `onpc_time_explanation::run` / `check_e2e_read_an_expanded_time_explanation` qualified a saved 15-minute allowance, explicit collapsed refusal and expansion preparation, wrong-child refusal and two independent 900/0/900-second reads in run `20260925T061535Z-18f56b25`, with collection, owned cleanup and baseline restoration. PARENT20 never expands; PARENT09 and arithmetic/elapsed comparisons remain separate. Historical first consumer: E2E-036 case 161, now [UI-owned](UI-and-E2E-Coverage.md#duplicate-review-and-allocation). | ready |
| PARENT09 | C | Reach the selected child's remaining-time explanation, expanding it only if currently collapsed, then read its balances. | `AccessibleUI.reach_time_explanation(child)` requires the selected child's Screen Limits surface, expands only a proven collapsed section with its public row action, then uses PARENT20. Repeated reads perform no collapse. `check_e2e_time_explanation` qualified independent collapsed/expanded entry, wrong-child refusal and repeated positive/zero reads in run `20260925T062949Z-49d65b22`, including collection, owned cleanup and baseline restoration. Use PARENT20 for read-only observation; neither block visits another desktop. | ready |
| PARENT12 | C | Read a displayed app row's identity, access choice and match choice. | `AccessibleUI.app_rows(child, maximum=256, expected_ids=None)` returns immutable public ID/access/match triples; `AppRowsObservation.from_rows` validates the controller projection. UI01 → UI02 → UI03, without installed-catalogue or executable probes. Fresh selected-child defaults, independent App Limits reread and wrong-child/page refusals qualified by `check_e2e_app_row_observations`; [scope](#app-row-observations). Declared native [search](#catalogue-search) results are qualified; filtering and policy edits retain their separate pending consumers. | ready for selected-child row observations |
| PARENT10 | C | Search the App Limits catalogue by name, description or launcher identifier and observe the matching displayed rows, including an explicitly expected empty set. | `onpc_app_rows::search` composes UI16 replacement with caller-named UI13 row read and independent controller comparison. Representative query, filter and combined-result checks use the shared native oracle and worker composites in UI preview; installed name, absent and clear results passed `check_e2e_catalogue_search`, and combined precise/Allowed passed `check_e2e_catalogue` in `20261001T040733Z-d8b05f90`. See [catalogue search](#catalogue-search) and [catalogue filters](#catalogue-filters). Row details use PARENT12 separately. | ready for declared native queries and filter combinations; complete cases remain separate |
| PARENT11 | C | Set one named App Limits filter's explicit canonical selection set and observe the exact displayed result set. Both access-rule and match-rule selections use the same API operation. | `onpc_app_rows::filter` sets the declared key list on `parent-filter-match-rule` or `parent-filter-access-rule`, then reads final rows; no popup or Escape is required. Caller-owned UI13/UI12 stages compare complete rows through `native_fixtures.catalogue_rows`; see [catalogue filters](#catalogue-filters). Historical representative qualification: `20261001T040733Z-d8b05f90`. | ready for declared Parent App Limits selection sets; complete cases remain separate |
| PARENT13 | C | Open a named app's Edit Match Rule dialog and read its current rule. | `AccessibleUI.open_match_rule` / `read_match_rule(editor=True)` through `onpc_app_rows::match_editor`; owned Parent, selected child, complete row and app-bound dialog guards. See [Match editor Save and Cancel](#match-editor-save-and-cancel). | ready for the declared native fixture binding; other app bindings pending |
| PARENT15 | C | Apply Save, Cancel or Reset to the open match editor and observe the explicitly expected result. Empty/unrelated precise text stays in the editor; a rejected wildcard closes it and opens a failure report. Do not close that report implicitly. | `AccessibleUI.respond_match_rule` through `onpc_app_rows::match_response`: one guarded Save/Cancel/Reset response → UI11(editor) → `parent_app_save_snapshot` (PARENT08) → independent public row read. Local invalid Save instead reads the retained exact draft and rejection description. `MatchRuleJourney` compares the caller's captured old rule after Cancel, exact supplied new rule after Save and detected default after Reset. See [Match editor Save and Cancel](#match-editor-save-and-cancel). The `rejected` response proves the declared rejected draft, invokes Save once, observes editor disappearance and leaves the automatic report open; see [automatic Parent error reports](#automatic-parent-error-reports). Caller uses FEED15/UI18 before reading restored rows. | ready for ordinary Save/Cancel/Reset, local invalid drafts and the declared rejected-directory/report slice; other bindings pending |
| PARENT16 | C | Choose Allowed, Hard blocked or Soft blocked for one displayed app; observe save and displayed choice. | `onpc_app_rows::access_choice(journey, save, row)` composes `AccessibleUI.choose_app_access` (UI15/PARENT08) and `read_app_access` (PARENT12); `AccessChoiceJourney` compares the caller's exact expected public choice. See [Public access choices](#public-access-choices). | ready for native fixture A and the existing child; other app bindings pending |
| PARENT17 | C | Open revocation confirmation and read its target and warning about time, blocked apps and daily allowance. | UI01 → UI04 → UI01 → UI03. | pending |
| PARENT18 | C | Cancel or confirm the open revocation dialog and observe its closure and displayed time/settings. Child effects are checked by later app/access blocks. | UI04 → UI11 → PARENT08 → PARENT03. | pending |
| PARENT19 | C | Observe Parent's no-eligible-child explanation together with the `(None)` picker placeholder. Never activate the disabled picker. | `AccessibleUI.parent_empty()` reacquires the Parent window and showing picker, then uses UI03's registered projections for the explanation and sole `(None)` label in one bounded read-only wait. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |

### App-row observations

`AccessibleUI.app_rows` in [accessible_ui.py](../../tests/e2e/accessible_ui.py)
resolves `parent-app-rows` beneath the owned App Limits page and verifies the
selected child and loaded controls. One complete Application UI API snapshot
traversal returns at most 256 sorted `(row ID, access, match)` triples within 45 seconds.
Off-viewport rows remain readable without scrolling; explicitly filtered rows
are excluded. Missing, duplicate, stale, incomplete, ambiguous or wrong-owner
observations refuse. Optional `expected_ids` compares the complete displayed
set, including an explicitly empty set. Search/filter consumers must establish
their own inputs and expectations before using that projection.

`AppRowsObservation` in [ui_observations.py](../../tests/e2e/ui_observations.py)
validates the bounded immutable values; app-row replies permit up to 32,768
bytes while ordinary replies retain their existing bounds. Expected access
choices belong to the caller. `onpc_app_rows::read_rows(journey, stage)` reads
one caller-owned stage; its one-argument form preserves the full qualification
sequence. Complete case 184 qualified the single-stage form in
`20261001T054514Z-f7691e2f`, and `check_e2e_native_fixtures` revalidated the
full sequence in `20261001T055119Z-f82bf7c3`, on every enabled VM with collection,
owned cleanup and baseline restoration. `AppRowJourney` in
[app_row_observations.py](../../tests/e2e/app_row_observations.py) and
`onpc_app_rows::run` compose the qualified fresh Parent entry, require nonempty
initial Allowed rows, refuse wrong-child/page reads, and compare an independent
reread after navigating away and reopening App Limits.

`tools/run-tests integration check_e2e_app_row_observations` qualified that slice
in run `20260924T232402Z-75f99b74`: 46 initial Allowed rows and the identical
independent reread passed, as did both refusals, private collection, owned
cleanup and baseline restoration. This supplies PARENT12/UI13 capability scope;
complete E2E-002 case 2 is qualified [below](#clean-installation-journey).
Filter inputs and policy-edit journeys remain pending under their own tasks.

### Catalogue search

`onpc_app_rows::search(journey, binding, result_stage)` in
[onpc_app_rows.pm](../../tests/integration/graphical_smoke/lib/onpc_app_rows.pm)
calls `onpc_text::replace_text` and consumes the caller's independent complete
row observation. Bindings are finite: `catalogue-name` (`ONPC Allowed Fixture`),
`catalogue-absent` (`ONPC Absent Catalogue Fixture 077b`) and `catalogue-clear`.
`AccessibleUI.text_recipient` checks the owned Parent API surface, selected
child's public ID, usable App Limits page and editable search field before
input. The shared text operation calls `setText` on `parent-app-search` once;
exact bounded API text readback and the debounced row result follow separately.

`AccessibleUI.CATALOGUE_ROW_OPERATIONS` binds complete result/reopening reads
to Jordan. Each checks exact query readback and waits for the complete expected
public ID set after SearchEntry debounce; it never retries input. Clearing waits
for all four declared fixtures, then the controller compares the entire original
collection. PARENT12 separately supplies the access/match triples. Missing,
duplicate, incomplete, wrong-child/page and wrong-owner reads retain their guards.
`catalogue-incomplete-refused` rejects an explicitly incomplete expected set.

[catalogue_search.py](../../tests/e2e/catalogue_search.py) owns the qualification
order and independent comparisons. It starts with `fixture_actions()` read-only
baseline verification, selects Jordan, captures the initial rows, refuses
wrong-child/page entry, enters App Limits independently, searches and reopens
both nonempty and empty results, then clears and compares the full collection.
Shared finite fixture queries and expected ID/access/match triples live in
[native_fixtures.py](../../tests/e2e/native_fixtures.py); future consumers compose
these leaves with their own plans and assertions.

`tools/run-tests integration check_e2e_catalogue_search` passed on every enabled
VM in run `20261001T030658Z-bf81b835`, including independent reopening, fixture
Allowed/precise readback, empty results, refusals, private collection, owned
cleanup and baseline restoration. Host checks cover complete traversal,
nondefault child input/refusal, delayed results, controller transport, worker
stop boundaries and real recorder startup/comparison. The preview checks real
API replacement, clear and wrong-child/page refusal. This qualifies only the
declared search slice. The representative query/filter UI results and installed
combined-filter sample are qualified under [catalogue filters](#catalogue-filters);
case 184 retains its separate complete acceptance.

### Catalogue filters

`AccessibleUI.catalogue_filter(child, kind, mask, action)` in
[accessible_ui.py](../../tests/e2e/accessible_ui.py) binds `match-rule` to
`pattern/precise` and `access-rule` to `allowed/conditional/permanent`.
Bitmasks select each option explicitly, including none and all. Before each
input it checks the owned Parent API surface, selected child and usable App
Limits page. It sets the complete canonical key list on
`parent-filter-match-rule` or `parent-filter-access-rule` through UI15 once;
the caller independently reads the complete resulting rows. Selection requires
no popup, Escape or focus step.
Wrong-child/page entry, missing/duplicate options and uncertain input refuse.

`onpc_app_rows::filter(journey, kind, mask, prefix)` in
[onpc_app_rows.pm](../../tests/integration/graphical_smoke/lib/onpc_app_rows.pm)
uses caller-owned stage names. `journey_blocks.filter_screens` declares their
finite operations. The caller separately observes complete rows through UI13
and supplies its exact expected result, without inheriting a qualification's
fixture lifecycle. `native_fixtures.catalogue_rows` supplies the shared finite
oracle for name, description, identifier, empty and absent queries and declared
match/access subsets. This oracle does not require executing their Cartesian
product through the GUI. Empty expected results remain explicit; observations
use no installed-catalogue backend.

[catalogue.py](../../tests/e2e/catalogue.py) owns the qualification's fresh native
verification, Jordan entry, precise/Allowed installed sample, independent entry,
wrong-entry refusals, and full clear/unchanged-policy comparison. Its selector is
`tools/run-tests integration check_e2e_catalogue`. It passed on every enabled VM
in `20261001T040733Z-d8b05f90`, together with `check_e2e_catalogue_search` and
`check_e2e_toggle`: exact rows, independent entry, wrong-child/page refusals,
collection, owned cleanup and baseline restoration all passed.
The representative preview coverage is
`test_preview_smoke.py::test_catalogue_query_and_representative_filter_results`,
with each query checked against unfiltered rows, individual filter categories
and empty filters checked on the complete catalogue, and two combined predicates.
It retains scripted hard/soft policies and a final complete row comparison plus no broker
policy writes. Complete case 184 has its own acceptance under task 226.

`native_fixtures.CataloguePolicyJourney` owns reusable immutable row comparisons,
with `JourneyPlan.catalogue_checks` declaring initial/unchanged endpoints or finite
query/match/access tuples. Search, filter and legend qualifications and case 184
use this same comparison implementation. The initial endpoint must precede every
comparison; missing captures, replay and changed policies refuse before reply.
Callers supply their own plan and fixture actions; no qualification lifecycle is
inherited. Case 184's independent composition is described in
the [E2E-041 recipe](E2E-Scenario-Recipes.md#e2e-041).
Its shortened direct Parent/Jordan entry removes allowance writes and balance
readbacks while preserving initial, search, combined-filter and unchanged-policy
comparisons. It passed on Ubuntu 26.04 in `20261010T172702Z-f2ff759d`, including
collection, owned cleanup and baseline restoration. Fedora 44 run
`20261010T172703Z-e3e339fa` was cancelled at the developer's request, with owned
cleanup complete; the shortened composition remains unverified there.

### Match editor Save and Cancel

`AccessibleUI.match_entry`, `open_match_rule`, `read_match_rule` and
`respond_match_rule` in [accessible_ui.py](../../tests/e2e/accessible_ui.py)
bind Jordan's complete App Limits row for native launcher `A.desktop`, the owned
Parent and its active transient editor. The dialog's app-content ID binds the
recipient independently of entry text. Wrong owner, child, app or page,
missing/duplicate controls, hidden/disabled/inactive recipients and uncertain
input refuse before action. Each response invokes one Save, Cancel or Reset action;
missing closure never replays it. `parent_app_save_snapshot` observes an active
usable row, search and child selector with no visible error report after closure.
It makes no transient-saving claim.

Editor entry uses `absent_id(..., incomplete_raises=True)` in a bounded read-only
preflight. A positively observed owned editor refuses immediately as already
open; an indeterminate complete negative proof retries without input. Defunct
trees, unavailable anchors, historical-owner nodes and query failures retain
fixed nonsecret absence notes. Legacy absence callers retain their existing
Boolean result. The app/child proof and independent opened-editor readback
remain required, and Open dispatch stays outside the retry boundary.

`onpc_text::replace_text` supplies the finite precise/wildcard drafts through the
same scoped `parent-match-rule-entry.setText` operation. The row's public match-button value supplies
the saved rule; no preference or broker reads are used. The qualified absolute
values are `/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage` and
`/opt/onpc-test-fixtures/Applications/Exact*.AppImage`, with their basename input
forms. The full GTK matrix is
`test_preview_smoke.py::test_match_editor_valid_save_cancel_matrix`: all four
draft forms, exact old-rule preservation on Cancel, independently reopened
editor readback, exact canonical saved rule and reopened editor after Save.
Host adapter checks also refuse duplicate response controls.

`test_match_editor_invalid_drafts_cancel_or_reset` extends the same public
entry/text and response operations with empty, whitespace, unrelated absolute
and unrelated basename drafts. Precise old rules exercise Cancel; wildcard old
rules exercise Reset, without multiplying independent old-rule/response choices.
Local invalid Save checks the exact retained draft and the entry's
public rejection description without a policy write. Cancel preserves the old
rule; Reset closes and immediately saves the detected default, independently
read in the row and reopened editor. Editing clears the rejection description.
The shared post-selection text observation, independent match-rule reader and
match-response recipient proof retry only incomplete/query reads under their
configured deadlines; no API
text input or response action is repeated when a toast or animation disappears
during traversal. Every fresh proof rechecks the owned child and editor.
Persistent incomplete reads and changed recipients refuse before input;
action query/dispatch errors retain the uncertain-input guard and expose the
fixed `ui:match-response-query:action` diagnostic without retrying the action.

`match_save_cancel.py::EDITOR_PLAN` and
`onpc_app_rows::match_editor_validation` declare the installed qualification for
`check_e2e_match_editor`: local empty-input refusal/Cancel and unchanged row,
same-directory wildcard Save, independently opened Reset and exact default row
and reopened-editor readback. This qualification passed on every enabled VM in
`20261001T082218Z-c41e928a`, including collection, owned cleanup and baseline
restoration. The affected Save/Cancel regression passed in
`20261001T082634Z-41bd2ec3` with the same lifecycle checks. The full valid and
invalid/Reset GTK matrices passed in `20261001T081537Z-ef1b9e50`.

[match_rules.py](../../tests/e2e/match_rules.py)'s reusable `MatchRuleJourney`
owns immutable ordered comparisons through caller-supplied
`JourneyPlan.match_checks`. Captures precede comparisons; missing captures,
replay and changed rules refuse before durable reply. Lifecycle ownership stays
in `InstalledJourney`. `onpc_app_rows::match_editor` and `match_response` are
shared mechanics; [match_save_cancel.py](../../tests/e2e/match_save_cancel.py)
declares the qualification's finite order and assertions.

`match_rules.match_edit(draft, prefix, editor=(open_stage, read_stage), row=row_stage)`
and `onpc_app_rows::match_edit(journey, draft, prefix, open_stage, read_stage, row_stage)`
compose editor entry/read, UI16 replacement and one Save. All bindings and
invocation collisions are validated before input. Ordinary Save requires an
independent row endpoint; `match-rejected-directory` requires `row=None`/`undef`
and ends at the automatic report. The caller owns report review/closure and
exact restored-rule assertions. FLOW03, the rejected-rule qualification and
case 205 reuse this composition without changing their stage order.

`tools/run-tests integration check_e2e_match_save_cancel` passed on every enabled
VM in `20261001T070820Z-36f8cd02`: precise initial capture, wildcard draft/Cancel,
unchanged public row, independent editor entry, wildcard draft/Save and exact
new public row. Wrong-app and non-single-response requests refused before input.
Collection, owned cleanup and baseline restoration passed. This is capability
qualification; no complete scenario is credited. Ordinary Reset and local
invalid drafts are qualified above; broker-rejected reports are qualified below.

The affected `check_e2e_catalogue` regression passed on every enabled VM in
`20261001T071148Z-bb578688`, including independent row/filter readbacks,
collection, owned cleanup and baseline restoration.

### Automatic Parent error reports

[rejected_parent_rule.py](../../tests/e2e/rejected_parent_rule.py)'s finite `PLAN`
qualified PARENT15 failed-save and FEED15 Parent/report-close through
`check_e2e_review_a_rejected_parent_rule_s_report` in `20261001T100005Z-225f84e2`
on every enabled VM. Jordan's native fixture A first confirms
`/opt/onpc-test-fixtures/Applications/Exact*.AppImage`, then rejects
`/opt/onpc-test-fixtures/Rejected/*.AppImage` through the normal editor Save.
Two independently opened editors/reports passed the fixed public explanation
and `Error` category, synthetic body/reply, available public actions, actual
Privacy and normal report closure, followed by exact last-confirmed row reads.
Absent-report wrong entry refuses before input; Send is untouched.

[parent_reports.py](../../tests/e2e/parent_reports.py)'s `report_review(prefix)` /
`ParentReportJourney` and `onpc_feedback_privacy::review_parent_report` share
ordered review mechanics and immutable draft comparisons across Privacy.
`AccessibleUI.parent_report_operation` observes the already-open report and
action availability without invoking them. Guarded editor Save never replays
an uncertain action or implicitly closes the report. Shared text preflights
retry incomplete/query reads only; API text input stays single-use.
The precise/wildcard GTK matrix and recorder/ownership/refusal checks passed.
Affected `check_e2e_match_editor`, `check_e2e_text` and
`check_e2e_feedback_privacy` regressions passed in `20261001T100734Z-e823553a`,
`20261001T101157Z-f954c618` and `20261001T101532Z-82e7d0a7` respectively.
Collection, owned cleanup and baseline restoration passed for all four runs.
This fixture/custom-wildcard proof preserves the precise-override reload
limitation in [Frontends](../SystemDesign/Frontends.md). Request report choices, sending, other bindings
remain separate.

Complete case 205 composes these shared operations through
[parent_error_report.py](../../tests/e2e/parent_error_report.py)'s `PLAN` and
`onpc_fresh_thirty_allowance::parent_error_report`. Its first report is reviewed
as above; the repeated error uses `parent_reports.report_close(prefix)` /
`onpc_feedback_privacy::close_parent_report` to read the untouched automatic
draft and bind one normal Close to a fresh `onpc_window::close('parent-report')`
proof. Both exits independently compare the exact confirmed wildcard.
This complete composition passed in `20261001T103654Z-6ee68021` on every enabled
VM. The affected rejected-rule/report qualification passed in
`20261001T104444Z-4f7b970a`; collection, owned cleanup and baseline restoration
passed for both runs. Scoped host checks cover the full worker order/refusal
stops, real recorder startup, comparisons before durable reply, stale close
proofs and the unchanged worker bundle bounds; both precise/wildcard GTK
variants passed with direct untouched-report closure. No report toggle or Send
input is introduced; the precise-override reload limitation remains unchanged.

### Public access choices

`AccessibleUI.choose_app_access(child, app, control)` in
[accessible_ui.py](../../tests/e2e/accessible_ui.py) accepts the declared app's
exact public choice ID. The current binding is native fixture A
(`com.puffyslippers.ONPCTest.A.desktop`); ID suffixes `allowed`, `permanent`
and `conditional` represent Allowed, Hard Blocked and Soft Blocked.
One fresh complete snapshot proves ownership, selected child, App Limits,
loaded catalogue, logically available management surface and visible/sensitive target before
one public action. Wrong-row IDs, wrong child, hidden/disabled/duplicate/foreign
controls and uncertain input refuse. Incomplete reads may retry before input;
actions and uncertain results never replay.

PARENT08's `parent_app_save_snapshot` waits for usable management controls and
refuses a public failure report. `read_app_access(child, app)` independently
projects the named row from the complete PARENT12 collection, without navigating
or supplying an expected value. `UiObservations` validates the finite app/choice
reply. `onpc_app_rows::access_choice` accepts caller-owned save/read stage names
and performs no implicit entry. `AccessChoiceJourney` in
[access_choices.py](../../tests/e2e/access_choices.py) snapshots the plan's
`access_checks`, rejects replay and compares exact expected choices before
durable acknowledgement. Cases can use this comparison class with their own
plan and actions; they do not inherit the qualification's fixture lifecycle.
It extends `MatchRuleJourney` and accepts both `match_checks` and
`access_checks` for a composed edit; each comparison retains its caller-owned
capture/order and exact public result.

`check_e2e_access_choices` qualified Allowed → Hard → Soft saves/readback,
wrong-row and modal-unavailable refusal, and the same sequence from an
independently supplied App Limits entry on every enabled VM in
`20261001T084642Z-820caae6`. Collection, owned cleanup and baseline restoration
passed. `test_preview_smoke.py::test_app_access_choices_save_and_independent_readback`
exercises the shared public-ID leaves and Perl composite on real GTK, including
unchanged Allowed without an extra save. Host guards cover insensitive targets,
decoder refusals, independent renamed invocations, recorder startup and failure
before a durable reply. This qualifies UI15's declared access group and PARENT16;
enforcement, other app bindings and complete scenarios remain separate tasks.

### Public app-policy edits

`policy_edits.policy_edit(app, draft, access, prefix, filters=())` declares
FLOW03's finite search, optional filters, editor draft/Save, access save and
independent match/access reads. `onpc_app_rows::edit_policy(journey, app, draft,
access, prefix, filters)` executes the same sequence for qualifications and
future cases. Both validate the complete app/draft/access/filter binding before
input. The caller supplies the selected child's App Limits entry and invocation
names; the composite never selects a child or reopens a page implicitly.
Search uses the declared launcher identifier. Filters explicitly bind each
selected set, including none. Existing leaves preserve public IDs, exact draft
reads, complete row ownership, error-report refusal and uncertain-input
non-replay. `AccessChoiceJourney` compares the caller's exact saved match and
access values before durable acknowledgement.

`policy_qualification.PLAN` / `onpc_app_rows::policy_edit` passed
`check_e2e_policy` on every enabled VM in `20261001T092758Z-7658aa78`:
Jordan/native fixture A, both optional filters, saved
`/opt/onpc-test-fixtures/Applications/*.AppImage` with Hard Blocked, subsequent
Soft Blocked and Allowed saves, independent App Limits readback, an unfiltered
precise/Soft edit and a second independent entry. Wrong-row/child/page requests
refuse before input. The shared comparison regression `check_e2e_access_choices`
passed in `20261001T093345Z-c4de983c`; collection, owned cleanup and baseline
restoration passed for both runs. No enforcement or complete-case credit follows
from these public editing checks. Other apps and input bindings retain their
own qualification requirements.

The actual qualification pattern must render without omissions against the
declared baseline fixture names before live work. `Exact*.AppImage` is valid
editor text but leaves unrelated space-bearing ELF fixtures outside the match;
the directory guard cannot safely preserve those nonmatches, and Parent opens
the documented warning report when blocking. FLOW03 uses the separate finite
`match-wildcard-appimages` binding to cover those files, preserving existing
editor-matrix inputs and the report guard. The owning host regression is
`test_e2e_app_rows.py::test_policy_qualification_pattern_is_representable_with_baseline_fixtures`.
`test_policy_composite_independent_names_and_every_refusal_stop` checks renamed
invocations and every failure stop; the actual GTK composition is
`test_preview_smoke.py::test_policy_composite_filtered_and_independent_entry`.

### Public policy legend

`AccessibleUI.expand_policy_legend(child)` / `read_policy_legend(child)` in
[accessible_ui.py](../../tests/e2e/accessible_ui.py) bind the owned usable Parent API surface,
selected child and App Limits page before input or read. UI04 resolves
`parent-legend-toggle` once and invokes its public action only when collapsed;
UI03 independently resolves `parent-legend-content` and requires both headings
and all five complete access/matching explanations. Missing/duplicate IDs,
wrong owner, child/page, stale or incomplete content and uncertain input refuse.
GTK may omit collapsed content or expose the pressed toggle before its Revealer
subtree. Only the post-input result wait retries missing content within its
original deadline; misplaced content refuses immediately, initial already-open
entry and standalone reads remain strict, and input is never replayed.

`onpc_app_rows::legend(journey, expanded_stage, read_stage)` in
[onpc_app_rows.pm](../../tests/integration/graphical_smoke/lib/onpc_app_rows.pm)
uses caller-owned stages; `expanded_stage = undef` reads an independently open
legend without expansion. Callers own finite child bindings and complete
initial/final policy row assertions, without inheriting qualification setup.
[policy_legend.py](../../tests/e2e/policy_legend.py)'s `PLAN` /
`PolicyLegendJourney` and `PolicyLegendQualification` own fresh Jordan allowance
setup, independent balances/legend reads, wrong-entry refusals and immutable
unchanged row comparisons. `check_e2e_policy_legend` passed on every enabled VM
in `20261001T051651Z-f6a0ab62`, including all explanations and unchanged 61-row
policies. Affected `check_e2e_catalogue` / `check_e2e_toggle` regressions passed in
`20261001T051932Z-f4508577` / `20261001T052424Z-65757534`; collection, owned cleanup
and baseline restoration passed for all three runs. Host guard/readiness,
decoder, worker-order and recorder checks plus
`test_preview_smoke.py::test_public_policy_legend_full_read_and_unchanged_choices`
cover the shared mechanics. Complete case 184 has its own acceptance under task 226.

### Kiosk, child overlay and the shared request form

One shared set of form blocks takes `surface = overlay | kiosk`. Child selection
is fixed/read-only in the overlay and selectable in kiosk. Different destinations
and recipient checks are explicit; duplicate surface-specific implementations
are unnecessary.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| AUTH01 | A | Qualify the real approval prompt's selected parent, displayed request/child/duration/app choice and sole empty masked focused field. No password contents or product authorization calls. | `AccessibleUI.mate_prompt`, `mate_prompt_refusals` and `kiosk_mate_cancel` qualify the fixed kiosk request and refusal matrix in the MATE provider row through `check_e2e_auth_prompt`. `shell_prompt_owner`, `shell_prompt` and `shell_prompt_refusals` qualify the fixed child-overlay binding through [Shell prompt qualification](#overlay-shell-prompt-and-cancel-qualification). Preserve the [secret boundary](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary). | fixed kiosk and overlay bindings ready; other bindings pending |
| AUTH02 | C | Approve, enter a declared wrong fixture password, or cancel authentication. For input, freshly qualify the same challenge twice and submit once. Observe acceptance, explicit rejection or dismissal; REQUEST11 separately reads the form result. | AUTH01 twice → UI19 → UI05, or UI04(Cancel) → UI01 → UI03 → UI11 as appropriate. A rejected prompt may need its normal Cancel action to return; never infer denial from timeout. A later retry needs a new challenge. `kiosk_approval.PLAN` / `onpc_password::enter_kiosk_mate_password` qualify the fixed correct-password binding; see [kiosk approval](#kiosk-approval-qualification). `kiosk_rejection.PLAN` / `AccessibleUI.kiosk_mate_rejected` qualify the fixed wrong-password and password-free Cancel branches; see [kiosk rejection](#kiosk-rejection-qualification). `overlay_shell_cancel_ready` / `onpc_request_flow::shell_cancel` qualify password-free Cancel only; see [Shell prompt qualification](#overlay-shell-prompt-and-cancel-qualification). `overlay_shell_approval` / `onpc_request_flow::shell_approve` qualify fixed correct-password approval; see [overlay approval](#overlay-approval-and-automatic-return-qualification). `overlay_rejection.PLAN` / `onpc_request_flow::shell_reject` qualify fixed wrong-password rejection and preserved form; see [overlay rejection](#overlay-rejection-and-cancel-qualification). | fixed kiosk approval with both exits/rejection/Cancel and fixed overlay approval/rejection/password-free Cancel ready; other bindings pending |
| AUTH03 | A | Validate the administrator authority, owned VM and verified input for one registered package command. | `PackageCommand.validate_input` and `guest_submit` bind finite current-install, previous-release-install and current-upgrade commands to verified FIX04 bytes, the active local Parent administrator and the owned transport attempt; [install qualification](#administrator-package-command-and-output) and [upgrade qualification](#genuine-package-upgrade). No Terminal or unrelated administrator-password challenge. Product approval authentication remains AUTH01/02. | fixed install, genuine v1.2/current upgrade and [finite Ubuntu libc6 reconfiguration](#genuine-unrelated-package-reboot-request) authority ready; other package bindings pending |
| REQUEST01 | C | Enter the dedicated request station from GDM through shared minimal account selection and observe its request form. | `journey_blocks.station_entry` / `onpc_gdm::enter_station` reuse `AccessibleUI.gdm_nonsecret_navigation`, consume one fresh focused-station proof before Enter, then independently require the active station owner and one showing owned window/form. The passwordless destination was qualified on the prepared Ubuntu 26.04/English-GDM/baseline-keyboard image with GNOME Shell `50.1-0ubuntu1.2`. `check_e2e_kiosk_eligible_choices` qualified direct composition after Parent preparation and shared Switch User. Station navigation requires the station row, without a named-parent prerequisite. This route and Cancel/GDM/reentry after locking all eligible parents passed `check_e2e_kiosk_fixtures` in run `20260924T173358Z-94d5db62`; the affected no-child route passed `check_e2e_kiosk_no_child` in run `20260924T173643Z-8d742069`, both with collection and owned restoration. Routine entry never visits another account. | ready |
| REQUEST02 | C | Open or deliberately reopen the child overlay by direct `oh-no-parent-control-child` invocation as the active child desktop user; observe one usable form and fixed child identity. Mandatory for ordinary overlay entry. | DESK01 → `AccessibleUI.launch_child_command` (`child-command-launch`, fixed command, one submission) → UI01 → UI02 → UI13(form count=1) → UI03(fixed child). Shared `overlay_entry(..., 'command')` qualified two independent entries and immutable form readback in [overlay entry qualification](#overlay-entry-qualification). Repetition is deliberate customer input, not retry. | direct entry and default form ready |
| REQUEST03 | C | Read a form's child, approver, duration, custom text, soft-app choice, controls and messages; observe the absence of mute in the current release. Require exactly one showing form and the fixed child in overlay. | UI13(form count=1) → UI01 → UI02 → UI03. `AccessibleUI.kiosk_request_form` retains the installed-qualified disabled-child projection. Its `enabled=True` binding also qualifies default 1800-second duration, selected child/approver IDs, enabled controls and absent disabled notice/mute/custom value. `RequestObservation.from_request` validates immutable operation-specific expectations. `check_e2e_kiosk_eligible_choices` independently reread both selections in run `20260923T204614Z-0601b77a`. `duration_seconds` / `custom_text` extend the immutable projection to the [qualified valid kiosk choices](#valid-kiosk-choice-qualification). `overlay=True` qualifies the default fixed-child projection through [overlay entry qualification](#overlay-entry-qualification); Declared valid overlay values are qualified through the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification); preserved invalid input and open/new FLOW04 projections passed the [overlay FLOW04/invalid/Escape slice](#overlay-flow04-invalid-submission-and-escape-qualification). Other values and account profiles remain pending. | default/declared valid kiosk/overlay and representative overlay invalid projections ready; other bindings pending |
| REQUEST04 | C | Set the child/approver selector to an eligible UID or duration selector to its canonical value. Observe selected identity, loaded values and availability; fixed-child overlay selection refuses. | `AccessibleUI.select_kiosk_account` / `kiosk_valid_choice` use `getChoices`, `setValue` and fresh REQUEST03 readback on the appropriate kiosk/overlay surface. Language restoration and disabled-child assertions retain their explicit child and language bindings. Historical qualification reports: `20260923T204614Z-0601b77a`, `20260923T235007Z-9d21bba1`, `20260925T035647Z-9242c8fd`. | pending; enabled kiosk child/approver including the stated German/Hebrew restoration binding, disabled-child selection and declared kiosk/overlay valid durations and overlay approver/refusals ready |
| REQUEST05 | C | Type a custom duration, including deliberately invalid text, and observe validation/request availability. | UI16 → REQUEST03. `onpc_text::replace_text(kiosk-fraction)` / `AccessibleUI.read_synthetic_text` qualify exact `1.25` minutes (75 seconds); see [valid kiosk choices](#valid-kiosk-choice-qualification). `kiosk-invalid-*` bindings qualify all seven invalid custom values with enabled Request and exact preserved text; see [invalid kiosk choices](#invalid-kiosk-choice-qualification). Do not coerce or repair the customer's value. `onpc_text::replace_text(overlay-fraction)` reuses the same guarded text mechanics for exact overlay `1.25`; see the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). `overlay-invalid-*` uses the same text binding and exact readback guards; representative `0.09` passed installed qualification and all seven invalid values passed the local native GTK matrix. See [overlay invalid submission](#overlay-flow04-invalid-submission-and-escape-qualification). Other values remain pending. | pending; kiosk/overlay 1.25-minute, kiosk finite invalid and representative overlay invalid input ready |
| REQUEST06 | C | Set the request form's soft-app choice to an explicit boolean and observe it. The surface and child are explicit. | UI17 → REQUEST03. `AccessibleUI.set_toggle` through `kiosk_valid_choice` qualifies explicit inclusion/exclusion and independent kiosk readback; see [valid kiosk choices](#valid-kiosk-choice-qualification). The explicit fixed-child overlay inclusion/exclusion binding also passed the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification); the fixed 75-second soft-included FLOW04 binding and subsequent exclusion also passed the [overlay FLOW04 slice](#overlay-flow04-invalid-submission-and-escape-qualification). Other overlay bindings remain pending; interactive mute is deferred future-feature scope. | pending; declared kiosk/overlay inclusion/exclusion ready |
| REQUEST08 | C | Read the visible estimate/footer for the chosen duration, including rest-of-day meaning, loading or unavailable estimates. | UI01 → UI03. `AccessibleUI.kiosk_request_form(enabled=False, expected_selection=...)` and `RequestObservation.from_request` bind `kiosk-disabled-form` to the selected child, retained nonempty approver, exact disabled-screen-limit explanation and unavailable Request/duration/soft-app/approver controls. Complete fresh prompt checks refuse authentication; disabled controls receive no input. `check_e2e_request_choices` qualified selection and independent readback in run `20260923T235007Z-9d21bba1`, with collection and owned cleanup. Complete case 57 also passed these public results with limits off throughout in run `20260925T035647Z-9242c8fd`, including Cancel-to-GDM, collection and owned cleanup. `AccessibleUI.kiosk_valid_choice` reads numeric estimates and the exact midnight footer through the public status ID; `KioskValidDurationJourney.check_settings` bounds fixed estimates using earlier public Parent balances and guest monotonic elapsed time. See [valid kiosk choices](#valid-kiosk-choice-qualification). `KioskRequestJourney.check_estimate` applies independent Parent balance/elapsed bounds to declared overlay values, preserving the unused-child equality check for kiosk; see the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). Open/default and new/remembered 75-second, soft-included overlay estimates also passed the [overlay FLOW04 slice](#overlay-flow04-invalid-submission-and-escape-qualification), with independent balance bounds and reproduced-choice comparison. Other values and loading/unavailable numeric outcomes remain pending. | pending; kiosk disabled-child explanation, unavailable Request and declared kiosk/overlay valid estimates ready |
| REQUEST09 | C | Activate an enabled Request once and observe the declared result: authentication for valid input or validation for invalid custom input. | UI01 → UI02(enabled) → UI04; valid then AUTH01, invalid then REQUEST03 → UI11(no prompt). `AccessibleUI.kiosk_mate_cancel` / `mate_prompt.PLAN` qualify the fixed valid kiosk submission through `check_e2e_auth_prompt`; `overlay_shell_cancel_ready` qualifies the fixed valid overlay submission through [Shell prompt qualification](#overlay-shell-prompt-and-cancel-qualification). `AccessibleUI.kiosk_invalid_choice` / `request_duration.PLAN` qualify enabled kiosk submission, exact validation, preserved form and no authentication for every finite invalid custom value; see [qualification](#invalid-kiosk-choice-qualification). `overlay-invalid-below-*` shares the same single-submit/no-prompt mechanics with explicit overlay/fixed-child guards; see [overlay invalid submission](#overlay-flow04-invalid-submission-and-escape-qualification). Missing accounts, unloaded preferences or disabled limits instead require the disabled state and no activation. | kiosk invalid-custom/fixed valid-authentication and representative overlay invalid-custom/fixed valid-authentication branches ready; other bindings pending |
| REQUEST10 | C | Native double-click Request and one-prompt observation: excluded on both kiosk and overlay. | Requires unsupported UI20; see the [UI mandate](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures). Do not substitute two activations or recreate capability/consumer tasks. Ordinary REQUEST09 and independent public observations remain separate capabilities. | excluded; no active task or queue blocker |
| REQUEST11 | C | Observe success confirmation, rejection, cancellation without an error, or validation feedback, with the explicitly expected preserved choices. | UI01 → UI03 → REQUEST03 where the form remains → UI12. Capture brief success before waiting for automatic exit. `AccessibleUI.kiosk_gdm_returned` is installed-qualified through `check_e2e_request_exit` for Cancel/Escape from the fixed disabled-child kiosk form: usable GDM and absent request/error UI. Case 54 also validates Cancel from the no-child form through `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run`. `AccessibleUI.kiosk_approval_success` qualifies explicit success before automatic or immediate exit; see [kiosk approval](#kiosk-approval-qualification). `kiosk_rejection.PLAN` independently compares preserved choices after explicit rejection and Cancel; see [kiosk rejection](#kiosk-rejection-qualification). Normal overlay Cancel and exact original usable-app activity passed the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). The [overlay FLOW04/invalid/Escape slice](#overlay-flow04-invalid-submission-and-escape-qualification) adds representative invalid validation with preserved choices/no prompt and an independent Escape/activity comparison. `OverlayPromptJourney` / `KioskRequestJourney` independently compare unchanged usable no-error overlay choices after password-free Shell Cancel; see [Shell prompt qualification](#overlay-shell-prompt-and-cancel-qualification). The child-owned Time granted result passed [overlay approval](#overlay-approval-and-automatic-return-qualification) and both [approved exit compositions](#overlay-immediate-exit-and-approval-compositions). `OverlayRejectionJourney` / `KioskRequestJourney` qualified explicit overlay rejection and unchanged usable no-error form; see [overlay rejection](#overlay-rejection-and-cancel-qualification). Other bindings remain pending. | pending; kiosk Cancel/Escape, fixed approval success and rejection/Cancel preserved form, declared overlay Cancel/Escape/invalid validation and fixed Shell rejection/Cancel preserved form and fixed overlay approval success ready |
| REQUEST12 | C | Exit through the normal API Cancel action, surface close, approved immediate exit action, or already-approved automatic exit. Observe overlay disappearance plus child desktop, or kiosk disappearance plus GDM. Form cancellation refuses an active authentication prompt. Legacy Escape bindings retain their normal-close user outcome. | UI04(Cancel or approved immediate exit), UI18, or no input for automatic exit → UI11 → DESK01 or GDM01. `AccessibleUI.cancel_kiosk_request` invokes the owned API action; `onpc_request_exit::escape` composes the scoped request-surface close with `kiosk_gdm_returned` or `overlay_desktop` for independent destination observation. Retained `focus_kiosk_escape_recipient` names supply guarded API close, with no native key or focus requirement. Cases 47/48 and 54 retain their choices and GDM assertions; see [prepared request qualification](#prepared-request-qualification). `kiosk_approval.PLAN` and `auth_result.PLAN` retain automatic/immediate approved exit; see [kiosk approval](#kiosk-approval-qualification). Overlay Cancel/close shares the request API and compares the original usable activity; see [valid overlay slice](#valid-overlay-choice-and-cancel-qualification), [overlay close history](#overlay-flow04-invalid-submission-and-escape-qualification) [automatic overlay approval](#overlay-approval-and-automatic-return-qualification) and [immediate/automatic overlay compositions](#overlay-immediate-exit-and-approval-compositions). Historical native-Escape evidence does not require keyboard input in current consumers. | pending; kiosk Cancel/Escape and fixed automatic/immediate approved exits and declared overlay Cancel/Escape and fixed automatic/immediate approved exits ready |
| REQUEST13 | C | Open the child overlay through the Shell panel only when the case explicitly tests that graphical launch route. Observe one usable form and fixed child identity. | DESK12(request entry) → UI04 → UI01 → UI02 → UI13(form count=1) → UI03(fixed child). Declare the exception in case metadata and recipe. Shared `overlay_entry` routes `panel` and `panel-reopen` qualify normal launch and deliberate repeated activation over the open form; see [overlay entry qualification](#overlay-entry-qualification). Fullscreen gameplay uses the same product API entry without panel reveal or focus choreography; its distinct request/return and retained-game results still need qualification. | normal launch and singleton ready; fullscreen gameplay/request/return binding pending |

#### Overlay Shell prompt and Cancel qualification

`overlay_prompt.PLAN` / `OverlayPromptJourney`, the shared
`onpc_request_flow::shell_cancel` and `check_e2e_overlay_prompt` passed on every
enabled VM (Ubuntu 26.04) in run `20261003T194901Z-f8ac692b`. Two separate guarded
attempts each publicly prepared the 900-second allowance, entered the child
desktop and declared Jamie/Riley, 75-second custom duration and included soft
apps. Provider tuple: Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, keyboard `xkb/us`.

Both this recipe and the approval recipe below declare authentication through
`request_flow.overlay_authentication(result=..., prefix=...)`. The fragment
ends at prompt dismissal or explicit approval success; callers retain form
preservation, destination/activity checks and assertion phases. It declares the
existing fixed binding, without extending the worker's supported endpoints or
provider qualification.

`AccessibleUI.shell_prompt_owner` binds the unique live top-level Shell process
on the active child's public bus even behind the fullscreen form. `shell_prompt`
requires the displayed approver and exact child/duration/app request before
checking the sole empty masked focused field. Fresh same-challenge reacquisition
and `shell_prompt_refusals` passed wrong provider/session/owner/recipient/request,
ambiguous/hidden/disabled/unfocused/nonempty/stale-field and replaced-challenge
refusals. `overlay_shell_cancel_ready` consumes no password; the worker releases
one normal Escape/Cancel only after the proof. Independent prompt disappearance,
usable no-error form and immutable choices are checked through
`KioskRequestJourney`, then the overlay closes normally.

Complete protected reads and bounded metadata-read retries retain all prompt and
owner refusals; incomplete observations never authorize input. Private collection,
worker shutdown, callback closure, owned cleanup, baseline restoration and
finalization passed in both attempts. The affected kiosk/MATE regression
`check_e2e_auth_prompt` passed in `20261002T072321Z-22f55417` with cleanup.
This qualifies AUTH01, fixed valid REQUEST09 and password-free Cancel/preserved
REQUEST11 only; correct-password approval is qualified separately below.
Rejection is qualified [separately below](#overlay-rejection-and-cancel-qualification);
complete scenarios remain separate work.

#### Overlay approval and automatic return qualification

`overlay_approved_exit.PLAN` / `OverlayApprovedExitJourney` and
`check_e2e_overlay_approved_exit` passed on every enabled VM (Ubuntu 26.04) in
`20261003T200552Z-980e4691`. The fixed request uses Jamie/Riley, 75 seconds and
included soft apps after public 900-second allowance preparation and fresh child
entry. The Shell tuple is `50.1-0ubuntu1.2`, `en_US.UTF-8`, keyboard `xkb/us`.

`AccessibleUI.overlay_shell_approval` and the ordered `UiObservations` decoder
bind two fresh empty-field proofs to the same challenge before
`onpc_password::enter_overlay_shell_password` delivers the sealed credential
once. Opening/refusal work grants no password authority; recipient proof clocks
start at acquisition and retain their freshness/order/replay guards.
`UiObservations.observe_shell_success` rechecks the filled recipient and records
observer readiness before `onpc_request_flow::shell_approve` releases one Enter
through the existing owned input rendezvous. Its matching acknowledgement is
required. Failed, stale, replaced or repeated authority never retries input.

The shared `kiosk_approval_success` reader pins the child-owned request window
before submission and reads its fresh public subtree for the brief **Time granted**
result. Hidden result controls may appear after submission; disappearance alone
does not establish approval. After observing success, bounded prompt-absence
reads tolerate the closing window without repeating submission. The worker
sends no exit input. `overlay_desktop` and `InstalledJourney.check_activity`
independently proved automatic disappearance, the child desktop and the exact
original usable fixture window, draft and activity.

Independent valid entry, wrong-account/surface and recipient refusal checks,
sealed capture reconciliation, collection, worker shutdown, owned cleanup,
baseline restoration and host/source preservation passed. Host regressions
cover transient success, closing-window query interruption, proof freshness and
replay, durable readiness, malformed/duplicate input release and matching
acknowledgements. The two independent Shell Cancel regression attempts passed
`20261003T194901Z-f8ac692b`; kiosk approval passed
`20261003T195605Z-9520133b`, all with collection and cleanup. This qualifies fixed
overlay AUTH02 approval and REQUEST11/12 success/automatic return. Rejection is
qualified [separately below](#overlay-rejection-and-cancel-qualification).
Immediate approved exit and FLOW05/07 compositions are qualified
[below](#overlay-immediate-exit-and-approval-compositions). Other provider tuples
and complete scenarios retain their separate tasks.

The Shell reader requires the broker's complete English child/duration/soft-app
message before inspecting the protected field's length; obsolete wording refuses.
Both authentication regression selectors and their automatic preparation bind
`named_input(package_source=True)`. Current app-snapshot preparation does not
make a fixed legacy package bundle current. Preserve immutable inputs and all
snapshot freshness, provenance and ownership guards.

#### Overlay immediate exit and approval compositions

`overlay_approved_exit.IMMEDIATE_PLAN`, `FLOW_REJECTION_PLAN` and
`FLOW_CANCEL_PLAN` / `OverlayApprovedExitJourney` passed
`check_e2e_overlay_approval` on every selected VM (Ubuntu 26.04) in
`20261008T192839Z-50210847` (its exported report has since rotated).
Three fresh attempts publicly prepared the 900-second allowance and child
desktop with an immutable native-app activity, then declared Riley/Jamie,
75 seconds and included soft apps. The Shell tuple was `50.1-0ubuntu1.3`,
`en_US.UTF-8`, keyboard `xkb/us`.

`request_flow.overlay_approved_request(exit='automatic'|'immediate')` and
`onpc_request_flow::overlay_approve` compose FLOW05 from the qualified Shell
recipient, single sealed submission, explicit success and declared exit leaves.
The immediate branch uses `AccessibleUI.kiosk_approval_success` to read the brief
child-owned success result and activate its offered public action once, after
independent prompt absence. Both branches then require overlay disappearance,
the child desktop and the exact original usable window, draft and activity through
`JourneyPlan.activity_checks` / `InstalledJourney.check_activity`.

Complete case 46 now composes this immediate binding with the shared native
activity entry/resume operations and TIME01 in `overlay_approved.PLAN` /
`onpc_kiosk_cancel::run(exchange, 'overlay-approved', ...)`. Its
`KioskRequestJourney` countdown comparison uses an immutable public estimate
already bounded by the earlier daily/no-grant balance, elapsed child usage and
requested addition. The numeric kiosk binding remains exact. This consumer
passed on the selected Ubuntu 26.04 VM; the [completed task row](E2E-Task-Queue.md#ordered-task-queue)
retains its acceptance and affected exit/countdown regression reports. It
qualifies no additional request choice, provider tuple or scenario.

`request_flow.overlay_rejected_request(outcome='rejection'|'cancel')` and
`onpc_request_flow::overlay_reject` compose FLOW07, leaving the form open after
`KioskRequestJourney` compares its immutable unchanged usable no-error choices.
The rejection attempt observed explicit denial before safe Cancel, then used a
new challenge for FLOW05's automatic exit. The password-free Cancel attempt
likewise preserved the form before a new challenge and immediate approved exit.
No old challenge proof authorizes the later request. A separate fresh immediate
approval attempt qualified that exit without a preceding rejection or Cancel.

The complete `AccessibleUI.nodes` read boundary includes deferred public-label
projection. A non-uncertain provider exit discards the entire observation for
bounded reacquisition; cached owner pins remain intact, uncertain/denied reads
stay terminal and no input is replayed. The real desktop/catalogue host regression
covers both inventory traversal and label projection, plus replacement-owner,
missing-desktop, denied and uncertain-operation refusals. This repaired the
observer's abort after explicit approval while the child window was closing.

Required regressions passed: overlay automatic approval/activity return in
`20261008T194256Z-987c8208` (its exported report has since rotated),
independent overlay rejection and password-free Cancel in
`20261008T194714Z-14858d96` (its exported report has since rotated),
and kiosk approval through the shared success reader in
`20261008T195522Z-2e720591` (its aggregate report has since rotated).
All attempts passed sealed capture reconciliation, collection, worker shutdown,
callback closure, owned cleanup, baseline restoration, finalization and
host/source preservation. Affected host guards and source validation passed in
`20261008T192712Z-a44b09a1`. This qualifies the fixed overlay AUTH01/02, valid
REQUEST09, REQUEST11/12 automatic/immediate and FLOW05/07 bindings; other choices,
provider tuples and complete scenarios remain separate work.

#### Overlay rejection and Cancel qualification

`overlay_rejection.PLAN` / `OverlayRejectionJourney` and
`check_e2e_overlay_rejection` passed on every selected VM (Ubuntu 26.04) in
`20261008T050819Z-ffdb973c`. The selector runs a wrong-password attempt and a
separate fresh `overlay_prompt.PLAN` password-free Cancel attempt. Both use
public 900-second allowance preparation, fresh child entry and Jamie/Riley,
75-second custom duration with soft apps included. Recorded Shell tuple:
`50.1-0ubuntu1.3`, `en_US.UTF-8`, keyboard `xkb/us`.

`request_flow.overlay_authentication(result='rejection', prefix=...)` pairs with
`onpc_request_flow::shell_reject`; callers retain order, assertion phases and
form/destination results. `onpc_password::enter_overlay_shell_password` consumes
two fresh empty-field proofs for the same challenge before one sealed declared
wrong password. A filled masked recipient proof precedes the single submission.
`AccessibleUI.overlay_shell_rejected` independently reads Shell's explicit
denial and rechecks the unchanged challenge with an empty, enabled, focused
masked retry field before `shell_cancel` releases one normal Escape/Cancel.
Missing, ambiguous, replaced, stale or uncertain proofs refuse; neither timeout
nor prompt disappearance establishes rejection.

Both attempts passed wrong-account/surface and recipient refusals, prompt
disappearance and immutable unchanged usable no-error form readback through
`KioskRequestJourney`, followed by normal overlay closure and child desktop.
The wrong-surface refusal now waits for a complete read after a provider exits
during traversal. Failed reads discard the whole observation; no subtree is
omitted and no input is retried. Host transient/persistent-query and incomplete
read regressions preserve that boundary and the existing refusal checks.

Affected overlay approval/automatic original-activity return passed in
`20261008T051602Z-bcc96b27` on the same Shell tuple; kiosk/MATE rejection and
password-free Cancel passed in `20261008T052150Z-8cb6735d`. All required attempts
passed sealed capture reconciliation, collection, worker shutdown, callback
closure, owned cleanup, baseline restoration, finalization and host/source
preservation. This qualifies fixed overlay AUTH02 rejection/Cancel and preserved
REQUEST11 only. Immediate approved exit and overlay FLOW05/07 composition are
qualified [above](#overlay-immediate-exit-and-approval-compositions). Other
request/provider bindings and complete scenarios retain their separate tasks.

#### Overlay entry qualification

The task 300i regression passed the unchanged six shell-panel assertions on
Ubuntu 26.04 in `20261004T114913Z-24503104`, with collection, worker shutdown,
owned cleanup, restoration and preservation. `check_e2e_shell_panel` and its
automatic artifact preparation both bind current-source package inputs; the
snapshot lookup continues to derive the installed version from the verified
package. Existing valid inputs are preserved and missing inputs use the shared
artifact builder.

`shell_panel.PLAN` / `ShellPanelJourney`, `journey_blocks.overlay_entry` and
`onpc_request_flow::overlay_entry` passed `check_e2e_shell_panel` in run
`20261001T204343Z-02c499af` on every enabled VM (Ubuntu 26.04). Provider tuple:
GNOME Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, keyboard `xkb/us`.
The qualification publicly prepared 900 daily seconds, refused the wrong
account, freshly entered the child desktop, and independently read two direct
entries and one form after two deliberate panel activations. Each read proved
the fixed child, default Casey approver, 1800-second choice and enabled controls.
Collection, worker shutdown, owned cleanup, baseline restoration and host/source
preservation passed. This supplies no complete-case or reusable exit credit.
The shared form-reader regressions `check_e2e_kiosk_entry` and
`check_e2e_kiosk_eligible_choices` passed separately on every enabled VM in
`20261001T205001Z-054e4d9a` and `20261001T205138Z-8b5d73c9`, including collection,
shutdown, owned cleanup and baseline restoration.

Panel operations now use the `child-panel` Application UI API. Fresh entry
activates `child-request-button` once and independently reads the fixed-child
form. An already open form is read/reused; the API's busy/active-request guard
is a refusal boundary, not permission to inject a key through another route.
Historical repeated-activation/reveal evidence above is not a required popup
sequence. Gameplay consumers retain their real activity and return outcomes.
Form descriptions follow
`Selected account: …`; namespace-scoped UID IDs still establish account identity.

#### Valid overlay choice and Cancel qualification

`overlay_valid_choices.PLAN` / `OverlayValidChoicesJourney`,
`OverlayValidChoicesQualification` and `onpc_request_flow::overlay_valid_choices`
passed `check_e2e_overlay_valid_choices` in `20261001T212417Z-410934a0` on every
enabled VM (Ubuntu 26.04). This finite REQUEST04/05/06/08 and REQUEST11/12 Cancel
slice uses the existing installed snapshot/secret/worker envelope; it adds no
complete-case or overlay FLOW04 acceptance credit.

Public Parent preparation independently proves Riley's 900-second daily balance.
Fresh child sign-in and `native_usable_app('command', child='child')` establish
usable activity before `overlay-native-activity` captures the owned native
window endpoint and submitted draft. Shared `overlay_entry(..., 'command')`
requires the fixed-child singleton. `request_surface(overlay=True)` binds each
input to the child application/session; `kiosk_valid_target` requires the
locked child selector and selected Jamie approver. The qualification refuses
child reselection and kiosk input on this overlay before input is released.

Shared `select_kiosk_account(..., overlay=True)` selects Jamie and independently
reads it. `kiosk_valid_choice` / `overlay-valid-*` select/read 300 seconds,
custom `1.25` minutes (75 seconds), Rest-of-day, inclusion and exclusion of soft
apps. `onpc_text::replace_text(overlay-fraction)` reuses UI16's product API text
replacement and independent exact text readback. `KioskRequestJourney.check_estimate` bounds fixed estimates by
the earlier public balances, elapsed time and precision; Rest-of-day requires
the exact midnight footer. Existing kiosk unused-child equality remains intact.

`cancel_kiosk_request(overlay=True)` invokes the normal owned Cancel once, then
`overlay_desktop` proves absence/usable destination and
`InstalledJourney.check_activity` compares the exact earlier window/draft before
the durable reply. A separate command entry reads the remembered zero-duration,
Jamie/excluded choice via `overlay_entry(...,
form_operation='overlay-valid-excluded-read')`, selects/reads 300 seconds and
Cancels to the same activity again. The native app then closes normally.
All four assertions, collection, worker shutdown, owned cleanup, baseline
restoration and source preservation passed. This slice supplies no Escape,
invalid-submission, authentication or overlay FLOW04 credit; the following
qualification adds the declared Escape/invalid/FLOW04 scope.

Host regression coverage is `test_e2e_overlay_valid_choices.py`, the shared
composition guard and the native GTK overlay check in
`test_request_form_component.py`. The module reuses its private preview and
waited Perl input lifetime. Unit scheduling classifies the new module as private
process-local doubles/evidence plus bounded reaped Perl children; no shared
resource or cleanup inventory is introduced.

All affected live regressions passed on every enabled VM, including collection,
worker shutdown, owned cleanup, baseline restoration and source preservation:

| Shared boundary | Selector | Run |
| --- | --- | --- |
| Kiosk valid durations/estimates | `check_e2e_kiosk_valid_duration` | `20261001T213243Z-936b0244` |
| Account selection | `check_e2e_kiosk_eligible_choices` | `20261001T213814Z-16f005ba` |
| Kiosk Cancel/Escape | `check_e2e_request_exit` | `20261001T214112Z-04d66799` |
| Default native command binding | `check_e2e_native_app` | `20261001T214337Z-561e36ba` |
| Default direct/panel overlay entry | `check_e2e_shell_panel` | `20261001T214741Z-fc13b5da` |

#### Overlay FLOW04, invalid submission and Escape qualification

`overlay_choices.PLAN` / `OverlayChoicesJourney`,
`OverlayChoicesQualification` and `onpc_request_flow::overlay_choices` passed
`check_e2e_overlay_choices` in `20261001T225151Z-5d6c2c04` on every enabled VM
(Ubuntu 26.04). The qualification inherits the installed snapshot, credential,
worker, recording and cleanup envelope; it supplies no complete-case credit.

Public Parent preparation proves Riley's 900-second daily balance before fresh
child sign-in. Shared `native_usable_app('command', child='child')` prepares the
usable native window/draft, captured once by `overlay-native-activity`.
`overlay_entry(..., 'command')` independently proves the default fixed-child
singleton; wrong-surface and child-reselection refusals precede form input.

`request_flow.prepared_request(surface='overlay')` /
`onpc_request_flow::prepare(..., 'overlay')` compose REQUEST03/04/05/06/08 without
child-selector input. The qualified binding is Riley/Jamie, custom `1.25`
minutes (75 seconds), included soft apps, `entry=open, initial=default` and
`entry=new, initial=selected`. New entry independently reads the remembered
custom/included choices via `overlay-valid-fraction-soft-read`, then reselects
and rereads them. `KioskRequestJourney.check_estimate` bounds both estimates
with earlier public balances and elapsed time; the declared `request_checks`
endpoint independently compares reproduced choices with the open-form capture.
Other child/parent/value bindings remain pending.

After separate soft-app exclusion, `text-overlay-invalid-below-*` replaces the
custom text with the recipe's representative `0.09`. Explicit overlay guards
require the locked child, correct approver, available controls and no prompt.
`AccessibleUI.kiosk_invalid_choice` handles `overlay-invalid-below-ready`, one
enabled submission, then independent preserved-form/exact validation/no-prompt
readback. No authentication input is sent, and uncertain input is never replayed.
The full seven-value invalid matrix belongs in native GTK UI tests; the shared
decoder/stream tests also retain wrong surface/child, unlocked child, disabled
controls, prompts, changed text and uncertain-input refusals.

Cancel after the open FLOW04 branch and the legacy Escape-labelled API close
after invalid validation have distinct return/activity observations.
`cancel_kiosk_request(overlay=True)` invokes the owned Cancel once; shared
`onpc_request_exit::escape` uses the product surface-close operation. Historical
native Escape/focus proofs are not current product input requirements. Each independently
requires overlay absence and usable child desktop, then
`InstalledJourney.check_activity` compares the exact original window/draft.
The native app closes normally afterward. All five declared assertions,
collection, worker shutdown, owned cleanup, baseline restoration and source
preservation passed. Window-close, authenticated exits and other values remain
pending.

Host coverage extends `test_e2e_overlay_valid_choices.py` for both real worker
plans, every-stage stop behavior, recorder/immutable comparisons, diagnostic
stream decoding and Escape focus guards. Existing composition/progress,
worker/installed-journey/credential safety checks passed. The native GTK shared
overlay adapter passed all seven invalid values separately for Cancel and
Escape. The existing unit module remains private process-local doubles/evidence
with bounded reaped Perl workers; native GTK extends its existing UI fixture
and resource profile. No new shared resource or cleanup inventory is added.
Host reports are `20261001T224510Z-854f6cda`,
`20261001T224637Z-d546567e` and `20261001T224946Z-9691fd53`.

All affected live regressions passed on every enabled VM with collection,
worker shutdown, owned cleanup, baseline restoration and source preservation:

| Shared boundary | Selector | Run |
| --- | --- | --- |
| Valid overlay choices/Cancel | `check_e2e_overlay_valid_choices` | `20261001T230641Z-65655fad` |
| Kiosk invalid submission | `check_e2e_request_duration` | `20261001T231558Z-5b985f05` |
| Kiosk open/new FLOW04 | `check_e2e_request_flow` | `20261001T232522Z-e5697445` |
| Kiosk Cancel/Escape | `check_e2e_request_exit` | `20261001T233017Z-710715cc` |

#### Overlay choices transferred to kiosk

`choices_overlay_to_kiosk.PLAN` / `ChoicesOverlayToKioskJourney` exercise
`request_flow.overlay_to_kiosk` / `onpc_request_flow::overlay_to_kiosk` through
`check_e2e_choices_overlay_to_kiosk`. The shared composite has historical
qualification on Ubuntu 26.04 and Fedora 44. The shortened qualifier below passed
on both: Ubuntu run `20261010T170933Z-ebf81845` and Fedora run
`20261010T170933Z-47ccb69c`, including collection, owned cleanup and baseline
restoration. The composite
consumes a fresh source observation, explicitly cancels the child overlay,
switches to GDM, enters the kiosk and selects the declared child. The destination
is read before editing and remains open. `AccessibleUI.transfer_choices` binds
the public operations to each child; `KioskRequestJourney.check_transferred_request`
compares immutable endpoints declared by `JourneyPlan.request_transfer_checks`.

Both children receive public 30-minute daily allowances. Riley's overlay uses
custom `1.25` minutes / 75 seconds with soft apps included; Jordan's uses `2.5`
minutes / 150 seconds with soft apps excluded. Both overlays retain Jamie as
approver while the kiosk retains Casey. The current qualifier transfers each
child once, then reselects Riley and Jordan in the same open kiosk and compares
each saved value with that child's original overlay capture. Its four immutable
comparisons preserve transfer, persistence, child isolation and local approvers
without a third overlay visit or retained GDM authentication. A wrong journey
receipt still refuses before input. Host checks also cover wrong-account
and owner refusals, stale observations, immutable comparisons and independent
shared-helper composition. Kiosk-to-overlay, interactive mute and complete
cases 59–61 remain separate pending scope. Case 58 has independent
[complete-case acceptance](#request-forms-and-remembered-choices).

The historical qualifier additionally returned to Riley's retained desktop and
repeated its transfer; that GDM branch is no longer a prerequisite of choice
persistence qualification. That qualifier and all six affected regressions (`check_e2e_overlay_valid_choices`,
`check_e2e_overlay_choices`, `check_e2e_kiosk_eligible_choices`,
`check_e2e_request_flow`, `check_e2e_request_choices`, `check_e2e_request_exit`)
passed on each selected VM in one grouped invocation:
Ubuntu run `20261009T213325Z-6d160963` and Fedora run
`20261009T213325Z-260b5ddc` (reports outside retained history).
Every execution passed collection, worker/callback shutdown, owned cleanup,
baseline restoration and source/host preservation, with its lease complete.
The shared source/fixture input bundle selects DEB or RPM from the verified VM
baseline; qualification planning uses private allocator doubles in unit tests.

#### Kiosk approval qualification

`kiosk_approval.PLAN` / `KioskApprovalJourney` and
`onpc_request_flow::run(exchange, 'approval')` passed
`tools/run-tests integration check_e2e_kiosk_approval` in run
`20261003T195605Z-9520133b`. Scope is the selected fixture child/administrator,
custom 75 seconds and soft apps included, on Ubuntu 26.04 with MATE Polkit
`1.26.1-6`, provider locale `en_US.UTF-8` and keyboard `[["xkb", "us"]]`.
An independent request/Cancel entry exercises the full AUTH01 refusal matrix;
fresh station entry then submits the correct fixture password once.

`AccessibleUI.kiosk_mate_approval` opens the request and supplies fresh recipient
checks through `mate_prompt`. Initial discovery uses `wait_mate_prompt` after
the one Request action: the kiosk's
[locale preparation](../SystemDesign/Localization.md) may restart the agent
before presenting authentication. While no prompt is visible, observation waits
without requiring a running service process. Once visible, the unique prompt
and every control must belong to the current service PID, which must remain
unchanged throughout that proof. Subsequent proofs retain the established
process/challenge binding; replacement remains a terminal refusal. Password-free
Cancel uses the same initial discovery. `mate_challenge_identity` binds opaque public
AT-SPI references to boot, UID and service process lifetime. `UiObservations`
requires ordered, non-replayed same-challenge proofs with a 30-second freshness
bound and rejects intervening operations. `onpc_password::enter_kiosk_mate_password`
consumes the two durable proofs through the shared single-use secret transport;
capture, reused challenges and uncertain delivery remain terminal refusals.
The English MATE binding checks the catalogue's complete multiline request label:
`Grant [Child user] access?`, `Requested time: 1 minute, 15 seconds.` and
`Allow soft blocked apps for this grant.` The 30-minute, soft-excluded binding
checks the first two sentences with its selected child and duration. Missing,
hidden, duplicate or changed request context refuses before any password proof;
the old one-line wording is not an alternate accepted binding. Private-tree
fixtures use the [shared English source messages](../../common/oh_no_parent_control_ui/messages.py)
so catalogue changes cannot leave the adapter and its doubles silently stale.
Submission freshly rechecks the filled masked focused recipient and invokes the
unique MATE Authenticate action once. `kiosk_approval_success` independently
reads the owned visible `kiosk-result-title` value `Request approved` in the same
observer process, before the three-second automatic exit. A later independent
`kiosk_gdm_returned` read requires usable GDM and absent request/error UI, with
no exit input. Prompt disappearance alone cannot pass.

Private capture reconciliation, collection, owned worker shutdown/cleanup and
baseline restoration passed. Host coverage in `test_e2e_kiosk_valid_duration.py`,
`test_challenges_cleanup_safety.py` and `test_installed_journey_cleanup_safety.py`
retains stale/reused/replaced proofs, nonempty/unfocused fields, wrong recipients,
uncertain input and durable-before-input failure checks. These tests retain
their compatible unit/cleanup classifications: private trees and bounded owned
Perl doubles only, with no shared display, bus, VM or heavyweight build.
This qualification grants no complete-scenario credit. Wrong-password rejection
is qualified separately below. Overlay approval and other request bindings remain pending.

Task 020 qualified the immediate exit in report run `20260926T160110Z-c946f822`
through `auth_result.PLAN` / `AuthResultJourney`, `AuthResultQualification` and
`tools/run-tests integration check_e2e_auth_result`.
`onpc_request_flow::run(exchange, 'immediate')` reuses the same single-use approval
secret binding. `kiosk-mate-submit-immediate` reads explicit approval and resolves
`kiosk-result-action` inside the owned result page, then invokes its public action
once before the automatic countdown. `new-returned` independently requires GDM
and absent request/error UI. Missing, duplicate, hidden, disabled and uncertain
actions refuse; uncertain input is never replayed. The automatic branch passed
its affected regression in report run `20260926T160801Z-2f278af9`.
Both runs passed independent entry/refusals, sealed private capture reconciliation,
collection, owned cleanup and baseline restoration on the provider tuple above.

The fixed kiosk outcome set composes these leaves: `kiosk_approval.PLAN` and
worker binding `approval` for automatic exit; `auth_result.PLAN` and `immediate`
for offered exit; `kiosk_rejection.PLAN` and `rejection` for explicit rejection
and independent preserved-form readback, including separate password-free Cancel.
Reuse unchanged rejection/Cancel evidence below. The fixed FLOW05/06 composition
and FLOW07 are qualified below; complete customer scenarios remain separately
queued. Added host checks retain
the existing compatible unit/cleanup classifications: private tree/recorder
fixtures and bounded owned Perl doubles, with no shared bus, display, VM or
heavyweight fixture construction.

#### Kiosk rejection qualification

`kiosk_rejection.PLAN` / `KioskRejectionJourney` and
`onpc_request_flow::run(exchange, 'rejection')` passed
`tools/run-tests integration check_e2e_kiosk_rejection` in report run
`20260926T154532Z-4ed66f34`. Scope is the selected fixture child/administrator,
custom 75 seconds and soft apps included, on Ubuntu 26.04 with MATE Polkit
`1.26.1-6`, provider locale `en_US.UTF-8` and keyboard `[["xkb", "us"]]`.

Separate station entries qualify password-free Cancel with the full AUTH01
refusal matrix, then one wrong-password submission and explicit rejection.
`onpc_password::enter_kiosk_mate_password(journey, 'wrong')` reuses sealed,
single-use delivery with two fresh same-challenge proofs. Its declared public
negative fixture is `onpc-wrong-fixture-password`, switching to
`onpc-other-wrong-fixture-password` only when the first equals the frozen
credential. No secret-derived value is published.
`AccessibleUI.kiosk_mate_rejected` requires MATE's explicit unsuccessful-attempt
label in the original service-owned dialog, freshly rechecks the empty retry
field and invokes normal Cancel once. It never retries authentication.
The separate `rejection-form` observation requires usable no-error form state;
the journey compares it with the independently prepared choices. Prompt
disappearance, success or timeout cannot pass as rejection.

Independent valid entry, wrong-entry/refusal guards, private capture
reconciliation, collection, owned worker shutdown/cleanup and baseline
restoration passed. Host coverage extends `test_e2e_kiosk_valid_duration.py`,
`test_challenges_cleanup_safety.py` and
`test_installed_journey_cleanup_safety.py`; their compatible unit/cleanup
classifications remain valid: private trees/fixtures and bounded owned Perl
doubles, without shared displays, buses, sockets, caches or heavyweight builds.
No complete-scenario credit. Immediate approved exit, overlay outcomes and
broader request bindings remain pending.

#### Valid kiosk choice qualification

`kiosk_valid_duration.PLAN` / `KioskValidDurationJourney` and
`onpc_kiosk_valid_duration::run` qualified the enabled kiosk's 5-minute preset,
exact custom `1.25` minutes (75 seconds), Rest of the day, and soft apps included
then excluded through `check_e2e_kiosk_valid_duration` in run
`20260926T043102Z-88f3a4f2`. Public Parent enable/save and a 15-minute balance
precede Switch User and station child/approver selection. Independent readbacks
require 20 minutes for the preset, 16m 15s for the fraction, the midnight footer,
explicit soft-app states, and Cancel back to GDM without authentication.
Wrong-entry/choice refusal, collection, owned cleanup and baseline restoration
passed. This capability supplies no complete-scenario credit.

`AccessibleUI.kiosk_valid_target` resolves owned selected-child/approver IDs
and enabled controls. After the single Custom action, `awaiting_custom=True`
waits only for the asynchronously published entry within the existing deadline;
it never replays input or accepts a disabled field. Prompt and ownership checks
remain active on each read. `test_e2e_kiosk_valid_duration.py` covers delayed
reveal, persistent absence, disabled state and an intervening prompt.
`kiosk_request_form` / `RequestObservation.from_request` retain exact finite
value checks. Other valid duration values, authentication and overlay bindings
need their own qualifications. Invalid kiosk input is qualified below.

#### Invalid kiosk choice qualification

`request_duration.PLAN` / `RequestDurationJourney` and
`onpc_kiosk_valid_duration::run(exchange, 'invalid')` passed
`tools/run-tests integration check_e2e_request_duration` in run
`20260926T044605Z-b5be87de`. The fresh installed attempt repeated the valid
choice/estimate/soft-app branches above, then qualified UI16/REQUEST05 and
REQUEST09 for empty text, `abc`, `-1`, `0`, `0.09`, `1440.1` and `1,5`.
Each `onpc_text::replace_text(kiosk-invalid-<binding>)` uses the shared focus,
single keyboard batch and exact independent text readback. Request stays enabled
on the otherwise ready form; one activation shows the exact range validation,
preserves child/approver/custom text/soft-app choice and starts no authentication.
Separate `ready`, `submit` and `read` operations bind finite expectations through
`AccessibleUI.kiosk_invalid_choice` and `RequestObservation.from_request`;
invalid durations project `duration_seconds=None`, never a valid-value estimate.
Wrong-entry refusal, Cancel-to-GDM, collection, owned cleanup and baseline
restoration passed. Host tests retain wrong-value/child, disabled-input, prompt,
changed-form and uncertain-input refusal plus actual worker order/stop checks.
This capability does not qualify authentication, overlay input or a complete
scenario; their inventory bindings remain pending.

### Customer terminal, files and application use

FILE02 executes registered public commands over guarded SSH as the declared
fixture user. INFO02 reads the public help/manual interface through bounded
stdout. Neither route permits private product probes or Terminal GUI setup. Fixture package/path arguments come from
verified prepared assets. Native/Snap/Flatpak and app names are parameters of
these blocks, not copies of them.
INFO02 validates each command's output without an intervening desktop UI check;
the complete command-help case owns one final public desktop result.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| FILE01 | A | Bind the guarded SSH channel to the declared fixture user/session for supporting commands. | Shared transport and fixed command registry; INFO02 already uses `command_documentation`. `session_control.observe` / `execute` bind `parent-command-context` to the active local administrator and read the verified staged package; [product-free qualification](#product-free-parent-entry-and-command-context) includes greeter refusal. `PackageCommand` rechecks that context for the [fixed install](#administrator-package-command-and-output) and [genuine upgrade](#genuine-package-upgrade) bindings. No graphical Terminal merely to execute commands. | product-free Parent context, fixed install, genuine upgrade and [finite Ubuntu libc6 reconfiguration](#genuine-unrelated-package-reboot-request) authority ready; additional bindings pending |
| FILE02 | A | Submit one registered command with finite validated arguments over shared SSH as the declared user. No arbitrary shell strings or replay. | `PackageCommand.submit` / `guest_submit` execute finite fixed APT argument arrays under the bound administrator context and guarded VM transport; [install qualification](#administrator-package-command-and-output) and [upgrade qualification](#genuine-package-upgrade). PARENT01/REQUEST02 retain dedicated launch bindings. FILE06 observes the later result. | fixed install, genuine v1.2/current upgrade and [finite Ubuntu libc6 reconfiguration](#genuine-unrelated-package-reboot-request) submission ready; additional bindings pending |
| FILE06 | A | Read bounded stdout/stderr, exit status and required public product notice or launch denial. Command echo or generic failure cannot prove enforcement. | `PackageCommand.read_result` independently requires successful exit, actual completion and final reboot notice at the later checkpoint; [install qualification](#administrator-package-command-and-output) and [upgrade qualification](#genuine-package-upgrade). `read_identity` supplies independent public installed-version and preservation readback. Graphical management denial remains PARENT01. No terminal rendering or unrelated password exercise. | fixed install/genuine upgrade completion and [finite Ubuntu libc6 completion/system reboot result](#genuine-unrelated-package-reboot-request) ready; additional bindings pending |
| FILE07 | C | Set a declared location only within an explicitly tested file-manager launch or product chooser handoff. Prefer direct directory launch or supported public location APIs, with minimal necessary shortcuts and independent destination readback. | Shared provider adapter with prepared exact-path/owner guards; no folder-browsing prerequisite. FILE03 owns real chooser Open/Save/Cancel; FILE04 opens Files directly at the target directory when its launch action is under test. | pending |
| FILE03 | C | Supply declared files to the external chooser, save a named file, or cancel. Mode and files are explicit; observe closure and independently read the caller's result. No folder-browsing or per-row selection exercise. | Open: prepared FILE05/FIX04 fixtures → shared `AccessibleUI.chooser_operation` using public EditableText/Selection APIs and minimal Location/Enter shortcuts → Open → independent `feedback_snapshot`. `file_chooser.PLAN` / `onpc_feedback_read::run_file_chooser` implement the [qualified handoff](#attachment-chooser-handoff); `profile` adds the six [boundary batches](#attachment-rejection-boundaries) and [single-file draft](#formatted-one-file-draft-lifecycle). Save uses `save_chooser_operation`, shared `save_handoff` / `save_cancellation` and FILE05 exact output readback as described below. Exact-file/owner guards remain in the adapter. Cancel acts directly without candidate selection; unchanged caller attachments are required. | ready for Parent two-file Nautilus Open/Cancel, single-file Open, six declared boundary Open batches, named diagnostic Save/Cancel to `~/Downloads` and fixed `Unwritable` save-error/recovery; native GTK and other profiles pending |
| FILE04 | C | Open the file manager directly at a declared directory only when the case explicitly tests that app launch route. | Shared fixed command/URI launch → FILE07/UI13. Supporting file preparation uses commands; product attachment/export handoffs use FILE03's actual chooser without a separate Files window. | pending |
| FILE05 | C | Copy or rename a registered fixture file through a bounded shared SSH filesystem operation and verify its exact destination. | `SyntheticFiles.call` in [synthetic_files.py](../../tests/e2e/synthetic_files.py), fixed `synthetic-text` profile; [qualified scope](#synthetic-file-commands). `save_destination_actions` adds fixed `save` preparation, exact output readback and owned cleanup for the diagnostic Save binding below. Product catalogue/enforcement results remain independent UI observations. No Files copy/rename tour. | synthetic-text and diagnostic Save destination bindings ready; other profiles pending |
| FILE08 | C | Inspect a declared synthetic or customer-exported text/ZIP artifact with bounded read-only filesystem/archive APIs over guarded SSH. Bind exact file identity and compare actual contents. For explicitly tested retained work, directly open its document in the registered work app and observe real activity instead. | `read_declared_text` / `read_declared_zip` in [synthetic_files.py](../../tests/e2e/synthetic_files.py) and fixed `open-text` / `open-zip` in [synthetic_files_guest.py](../../tests/e2e/synthetic_files_guest.py) qualify synthetic text/ZIP and the fixed `diagnostic-export` Save receipt binding; see [artifact-read boundary](#customer-artifact-read-boundary). Work uses APP01/03/04; file reads cannot prove usable or retained activity. No Files/editor/archive-viewer GUI for export inspection and no private product files. | synthetic text/ZIP and named Parent diagnostic-export bindings ready; retained-work and other exported artifacts pending |
| FILE09 | C | Change a registered synthetic source file using the shared file helper and observe the product's attachment snapshot/re-add result. For declared retained-work assertions, edit/save in the existing work fixture and read its activity. | `change_attachment_source` / `SyntheticFiles.call('change-source')`; [qualified source binding](#synthetic-source-change). UI16/Ctrl-S/public saved state only for work observed by an enforcement/retention case. | standard/single synthetic source preparation ready; product snapshot/re-add belongs to the attachment UI matrix; retained-work binding pending |
| APP01 | C | Attempt a launch once by the route explicitly tested by product enforcement. Default supporting launch uses a shared direct command. Hidden launcher and execution denial are distinct. | `onpc_app_rows::native_search/native_launch_grid/native_open_grid` qualify Jordan's exact Allowed fixture grid route under [native fixture preparation](#native-fixture-preparation). `native_open_command` / `AccessibleUI.native_launch_command` qualify the fixed native command as the bound active child desktop user over guarded SSH, with independent APP02 window readback. Explicit app-grid, desktop-icon and file-manager cases retain their GUI route. Command cases use FILE01/02 without Terminal UI. Never substitute the tested route after failure. | native Allowed grid/command ready; other bindings pending |
| APP02 | C | Observe exactly the expected usable window, named launch denial, hidden launcher, or closure of a previously observed window. Inputs include route, result and earlier window observation when required. | `AccessibleUI.native_app_snapshot/native_app_closed` independently observe the owned primary native window and exact initial activity, then complete absence with the recognized desktop after `onpc_app_rows::native_close_app`. UI01 → UI03 for presence; FILE06 for command denial; UI11 for hidden/closed surface with a recognized surrounding UI. Hidden launcher alone cannot prove blocked execution. | native Allowed presence/normal closure ready; denial, hidden and other bindings pending |
| APP03 | C | Perform one declared normal app input and observe its customer-visible effect, proving usability. Repeated game actions are separate bounded invocations. | `onpc_app_rows::native_use_app` composes guarded public Submit draft through `AccessibleUI.native_app_submit` and separate exact submitted-label readback. UI01 → one of UI04, UI05 or UI06 according to the declared input mode → UI03 or UI02 according to the declared result projection. App action/expected effect is fixture data. | native primary draft submission ready; other actions/bindings pending |
| APP04 | C | Read a recognizable public activity/window state, or compare it after legitimate return. Inputs declare capture/compare and the earlier immutable observation. | `AccessibleUI.native_app_snapshot(with_window=True)` / `native-activity` read the owned public window endpoint and exact submitted draft. `AppActivityObservation`, `compare_app_activity` and `InstalledJourney.check_activity` copy immutable captures and compare explicit `JourneyPlan.activity_checks` endpoints; `onpc_app_rows::native_read_activity` supplies caller-owned invocation IDs. APP02(present) → UI03 → UI12 only for compare; [native activity qualification](#native-fixture-preparation). A newly launched window cannot satisfy retained-activity expectations. `overlay-native-activity` adds the fixed Riley command binding and two exact retained-window/draft comparisons after normal Cancel; see the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). No hidden process/window inspection. | native primary submitted-draft capture/same-window comparison ready; cross-user retention and other bindings pending |
| APP05 | C | Prepare the real offline game's declared windowed/fullscreen mode and reproducible level through shared supported commands or keyboard shortcuts, then observe active gameplay. Game settings menus are supporting setup. | Bind startup options in the preceding APP01 launch, or use a fixed supported command/UI05 shortcut on the observed game; do not relaunch retained activity. UI01/UI03 verifies the mode/level, then APP03 proves actual gameplay input/effect. The selected game needs usable public observations; a menu or timer fixture is insufficient. | pending |
| APP06 | A | Read one complete, account-scoped public projection of Lunar's tray/background control, Lunar window and Minecraft activity, with the recognized surrounding desktop. Presence/absence is explicit input; do not launch, reveal or quit anything. | No callable yet. The [Lunar profile slices](#lunar-client-preparation-and-observation-gate) separately qualify Lunar/tray, Minecraft activity and login observations, including absence and incomplete/wrong-owner refusal. UI22 composes repeated observations across the declared login interval; one final absent window cannot establish blocked autostart. [Consumer gate](#lunar-client-preparation-and-observation-gate). | pending |

The qualified FILE03 Save binding uses `AccessibleUI.save_chooser_operation` and
`attachment_composition.save_handoff`, shared by qualification and future consumers;
`save_cancellation` separately declares a fresh Cancel/preservation check. The
matching `onpc_feedback_read` composites execute each fragment. Its
writable destination is the bound parent's `~/Downloads`, with the ZIP directly
in that folder. All VM customer-download destinations use
[`download_destination.download_directory`](../../tests/e2e/download_destination.py)
with the explicitly bound account home; both guest dispatchers load that same
module. FILE05 `save_destination_actions` / `synthetic_files_guest.save_operate`
prepare and independently read that same destination, preserve existing contents,
refuse conflicting output names and clean only identity-verified attempt-owned
objects. `tools/run-tests integration check_e2e_save_chooser` passed in
`20260929T191454Z-a2f14da3` on Nautilus `1:50.2.2-0ubuntu0.2`, `en_US.UTF-8`,
`xkb/us`, caller `parent-feedback`. Two independent entries passed collection
readiness, wrong-entry/mode refusal, exact directory/name proof, real Save,
chooser closure, independent output-file and app readback, and fresh Cancel
with the saved output unchanged and no second file. Owned fixture removal,
evidence collection, worker cleanup and baseline restoration passed. Case 155 in
`20260929T203255Z-29d6637e` additionally qualified the fixed
`save_handoff(destination='unwritable', draft='synthetic-first')` binding to
`~/Downloads/Unwritable`, prepared at `0500` and independently verified as the
saving user. `denied-export-save-chooser-*` reuses the same provider guards and
exact name/destination proof. Chooser closure must precede the exact public app
subtitle `Could not save logs. Try another location.`; a provider error cannot
replace it. `save_cancellation(draft='synthetic-first')` retains the synthetic
draft. Separate finite Cancel/failure checkpoints in
`diagnostic_export_actions(preservation=True)` read the unchanged empty output
receipt, retaining single-use mutation and uncertain-command refusal. The
successful Save/Cancel regression passed in `20260929T203754Z-7b47ee7e`.
Native GTK and other destinations remain unqualified.
Nautilus's [filename widget](https://github.com/GNOME/nautilus/blob/50.0/src/resources/ui/nautilus-file-chooser.blp)
collapses on focus loss. After exact destination readback and Escape from
Location, `save_chooser_restore_name` invokes the unique public button whose
`LABELLED_BY` relation targets `filename_label`, then checks the revealed
`filename_entry` and unchanged exact name. This is a provider-local semantic
binding, not a button ID; Reset File Name is never invoked. Duplicate labels or
buttons, wrong ownership, unexpected modals and uncertain input refuse.

#### Customer artifact read boundary

Tasks 195a/195 qualify shared command readers for text and ZIP artifacts; 045
binds them to the actual product Download/Save result. Read only declared
synthetic files or the exact file created by that caller's successful save in
the owned attempt, as the bound user. Pin file identity, reject path traversal,
symlinks, replacement and unrelated paths, and retain explicit byte/time limits.
The ZIP reader uses a maintained public archive API, enumerates exact entries
including empty folders, and reads declared text/JSON members without extraction.
Bound expanded bytes and member counts as well as archive size; malformed,
duplicate or unsafe entries refuse. Record bounded sanitized comparisons of
actual contents, never an inference from command success or expected fixture data.

This observes customer-exported output, not internal state: source logs, private
drafts and collector/broker internals remain unavailable. Preserve the real
Download/Save/Cancel/error journey, then independently reread the same feedback
dialog and draft. No Files, File Roller or text-editor qualification is needed
for export inspection. Offered preview and information-link handlers remain GUI
integrations under their own blocks. Retained work still needs its direct app
launch, observable edit/save and activity comparison through APP01/03/04 and
FILE09; these command readers do not qualify that binding. The synthetic text
binding passed `tools/run-tests integration check_e2e_document_open` in report
`20260928T044018Z-75574827`: two independently staged entries returned the
exact declared size/digest. Wrong attempt/user/artifact, stale receipt,
missing, symlink, replacement, empty, different and oversized probes refused.
The fixed reader pins directory/file descriptors, compares the preparation
receipt before reading, limits text to 1024 bytes and returns sanitized
comparison evidence. Owned fixture/probe cleanup, collection and baseline
restoration passed.

The synthetic ZIP binding passed
`tools/run-tests integration check_e2e_open_a_customer_document_or_archive` in
report `20260928T045842Z-69443040`. Two independently staged archives passed exact
member-set checks, including `empty/`, and actual text/JSON size/digest comparisons.
The shared `read_pinned` reader binds directory/file identity, owner and receipt;
`inspect_zip` uses Python's public `zipfile` API without extraction. Limits are
64 KiB archive bytes, 16 members, 4 KiB per expanded member, 8 KiB expanded total,
five seconds for inspection and a 30-second guarded command timeout. Wrong
attempt/user/artifact, missing/symlink/replaced files, wrong declared owner,
malformed/duplicate/unsafe/unexpected members, changed content and each byte/count
limit refused. Owned fixture/probe cleanup, collection, worker shutdown and
baseline restoration passed. This synthetic slice supplies no case 155 or real
Download/Save acceptance; the diagnostic-export binding is qualified below.
The affected synthetic text qualification also passed in
`20260928T050106Z-51ffa8ad`, including both entries, refusal checks, collection,
owned cleanup and baseline restoration through the shared file-identity reader.

The fixed `diagnostic-export` profile passed `check_e2e_diagnostic_export` in
`20260929T194911Z-9bb9b122`. `diagnostic_export_actions` supplies the original
Save controller and its successful receipt to `read_declared_zip`, binding
attempt, parent user, exact `Selected diagnostics.zip` and single-use inspection.
`read_saved_zip` revalidates the complete receipt before and after a pinned read
from `download_directory(home)`, retaining baseline files and owned cleanup.
Existing owned Downloads may be `0755`; synthetic directories retain `0700`.
Files remain owner-only, single-link regular files with exact identity/digest.
No existing directory permissions are changed. The diagnostic limits are 2 MiB
archive, 17 members, 16 MiB per member/expanded total, five seconds inspection
and 30 seconds command timeout; synthetic limits remain unchanged.
Independent comparisons require `system-info.json`, all four empty component
folders, the exact declared dated logs (at most three per component), schema 3,
frontend system information, health/counters, complete log headings and record
counts. The installed closed-format parser additionally validates every record,
system category and readable description using only the exported ZIP. This
fresh-package binding requires dated logs; legacy `undated.log` is outside scope.
Only validated names, sizes/digests, counts and finite comparisons become evidence.
Both independent entries passed wrong attempt/user/artifact/owner refusal,
same-dialog endpoint/PID and exact body/reply/attachment/control preservation,
collection, owned cleanup and baseline restoration. Affected Save/Cancel,
synthetic ZIP and text qualifications passed in `20260929T195352Z-64a83e8b`,
`20260929T195728Z-9b0b20c4` and `20260929T195845Z-ed63fec7` respectively.
Complete case 155 passed in `20260929T203255Z-29d6637e`, including Cancel,
save-error/recovery, Privacy and same-dialog comparisons at each return.
Inspection also rejects the declared synthetic account, email, draft and
file-content values in actual exported bytes. The affected export qualification
passed in `20260929T204158Z-388a25b4`, with both independent entries, refusal
checks, collection, owned cleanup and baseline restoration.
Retained-work and other export profiles remain pending.

#### Synthetic source change

`change_attachment_source(journey, guard, profile='standard')` in
[synthetic_files.py](../../tests/e2e/synthetic_files.py) reuses the controller
created by `fixture_actions` and carries its updated receipt through the same
cleanup action. The `standard` and `single` profiles change only
`Synthetic note.txt` from the fixed 26-byte original to the fixed 34-byte
`ONPC changed synthetic attachment\n`. Other files and the directory identity
must remain unchanged. No caller-supplied path or content is accepted.

The guest validates the complete original receipt, owner, mode, link count and
bytes, pins the directory/file descriptors and performs one bounded write.
Independent guarded SSH readback checks exact changed bytes and the new receipt.
Uncertain writes latch controller failure, preventing replay and cleanup against
an obsolete receipt. Traversal, wrong declared owner, symlink, replacement,
changed original and hard-link probes must refuse without mutation. Cleanup
accepts only the carried exact receipt and independently confirms absence.

`tools/run-tests integration check_e2e_edit_and_save_an_open_synthetic_document`
passed in `20260928T050905Z-0e6857aa`: independent standard/single entries,
changed-content readback, refusal probes and owned cleanup. Collection, worker
shutdown and baseline restoration passed. The affected FILE05 copy/rename/read/
cleanup regression `check_e2e_files` passed in `20260928T051104Z-c57dd2ac`.
The attachment UI matrix owns the real attachment's unchanged public metadata
followed by Remove/re-add and larger-size observation. This source preparation supplies
no attachment snapshot or APP03/04 retained-work acceptance.

#### Attachment chooser handoff

The [UI mandate](../Mandates/UI-Automation-Mandate.MD) treats the chooser as an
external tool. FILE03's installed feedback helper opens the real Add files
dialog, uses Location once, replaces the prepared directory through public
[EditableText](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.EditableText.set_text_contents.html),
then uses Enter and public
[Selection.SelectAll](https://github.com/GNOME/at-spi2-core/blob/main/xml/Selection.xml)
on the bounded two-file fixture set. It invokes Open once, observes closure and
independently checks the app's exact attachment IDs/names and ready status.
Reopen/Cancel directly verifies that the app retains those attachments.

The declaration/execution pairs `attachment_composition.chooser_preservation`
/ `onpc_feedback_read::chooser_preservation` and
`attachment_composition.attachment_removal` /
`onpc_feedback_read::attachment_removal` are shared by case 154 and the chooser,
item and boundary qualifications. Optional invocation prefixes rename stages,
not registered operations or expected results. The callers still own entry,
fixture lifetime, qualification refusals and phase boundaries.

Folder browsing, individual row selection and a changed candidate before Cancel
are outside customer acceptance. The shared adapter still refuses wrong owners,
ambiguous dialogs, unexpected files, partial selection and uncertain input;
host regressions exercise those safeguards without adding a live chooser tour.
Nautilus's scoped Content View exposes public Selection with a custom model.
[GtkGridView's hint](https://github.com/GNOME/gtk/blob/4.22.0/gtk/gtkgridview.c)
reports multi-selectability only for `GtkMultiSelection`, whereas
[NautilusViewModel](https://github.com/GNOME/nautilus/blob/50.2.2/src/nautilus-view-model.c)
implements `GtkSelectionModel` itself. The adapter therefore proves both selected
files through Selection readback before Open instead of requiring that type hint
on the Nautilus route. Native GTK retains its existing hint check.
The same provider's
[file labels](https://github.com/GNOME/nautilus/blob/50.2.2/src/nautilus-file.c)
include the exact `. File` role suffix in `en_US.UTF-8`; the adapter maps only
the registered fixture labels back to basenames, refusing folder/extra suffixes.
`tools/run-tests integration check_e2e_file_chooser` qualified this handoff in
`20260928T025758Z-911df7f2`: Nautilus `1:50.2.2-0ubuntu0.1`, actual provider locale
`en_US.UTF-8`, keyboard sources `[["xkb", "us"]]`. The two prepared files reached
Parent feedback with exact attachment IDs/names and ready status; independent
reopen/Cancel retained both files and `diagnostic-logs.zip`. Wrong-entry refusal,
owned fixture removal, collection, worker cleanup and baseline restoration
passed. Send was untouched. This capability slice does not complete case 152.
The same Open/Cancel scope passed again in `20260929T191829Z-3d1fd72a` on
Nautilus `1:50.2.2-0ubuntu0.2`, `en_US.UTF-8`, `xkb/us`, including collection,
owned cleanup and baseline restoration. Save has its separate qualification
above; native GTK and other fixture profiles remain pending under their consumers.

Consumers must carry this handoff forward through the shared implementation:

- Reuse `AccessibleUI.chooser_operation`, the public facade in
  [public_atspi.py](../../tests/e2e/public_atspi.py), and the worker/plan wiring in
  [file_chooser.py](../../tests/e2e/file_chooser.py) and
  [onpc_feedback_read.pm](../../tests/integration/graphical_smoke/lib/onpc_feedback_read.pm).
  Extend shared leaves for declared inputs; do not copy this qualification's
  entire journey or create a chooser driver in each consumer.
- Keep whole-path `EditableText.SetTextContents` with a trailing directory slash
  and fresh exact text readback. Preserve current `button` and legacy
  `push button` roles, provider-local Nautilus Close versus native GTK Cancel,
  public portal Request ownership and snapshot-scoped prompt guards. Keep
  Nautilus's selection-model and exact file-label handling inside that adapter.
- The standard two-file selection, `feedback_snapshot(attachments=True)` and
  six [boundary profiles](#attachment-rejection-boundaries) and the
  [formatted one-file draft](#formatted-one-file-draft-lifecycle) are fixed
  bindings, not arbitrary-file APIs. Other mixed-validity or source-change
  consumers must first extend the shared fixture and observation contracts
  with finite declared inputs. SelectAll is valid only after the prepared view
  is proved to contain exactly that batch; never select a broader directory or
  relax the exact check. Keep the fixture controller and ownership receipts
  through cleanup.
- The `attachments=True` result proves IDs/names and ready status. Its sorted
  name list does **not** prove displayed order, sizes, preview contents, removal
  or rejection. Reuse the [item observations](#attachment-item-metadata-and-removal)
  for the qualified metadata/removal profiles; extend independent public
  observations for other results, including the unchanged prior list after rejection.
  A fixture's expected values or a successful input cannot supply the observation.
- Before a changed handoff's live attempt, retain the success/refusal coverage in
  [test_e2e_feedback_read.py](../../tests/unit/test_e2e_feedback_read.py) and
  [test_public_atspi.py](../../tests/unit/test_public_atspi.py), including realistic
  provider roles/labels, absent multi-selection hint, partial selection and
  uncertain-input refusal. Follow [composition preflight](#composition-preflight)
  through worker dispatch, observation decoding and recorded assertions. Inspect
  the earliest failed stage and command evidence; a generic worker/SSH failure
  alone does not establish a product defect or justify longer waits/replay.
- Reuse only the recorded provider/version/locale/keyboard scope. New profiles
  and compositions need their own affected qualification; Open does not qualify
  Save. Supporting source-file changes use shared commands, while offered
  preview and required app results remain public customer observations.

#### Formatted one-file draft lifecycle

Case 152 (`parent_feedback_draft.PLAN`) passed the complete customer history in
`20260928T030531Z-1c1850d6`, including collection, owned cleanup and baseline
restoration. The shortened composition passed on Ubuntu 26.04 in
`20261010T171847Z-0b1bc336` and Fedora 44 in `20261010T171847Z-310d8f89`,
including collection, owned cleanup and baseline restoration. Formatting, reset
and Privacy regressions passed in
`20260928T022907Z-f877531d`; window-switch and chooser regressions passed in
`20260928T025758Z-911df7f2`, with collection and owned cleanup.
`synthetic_files.fixture_actions(('single',))` prepares only
`Synthetic note.txt` with its declared 26 bytes and retains its ownership receipt
through cleanup. `onpc_feedback_read::supply_files(journey, 'draft-chooser')`
uses the existing public chooser with `profile='single'`; exact-directory and
selection guards remain unchanged. This adds the one-file Parent Open binding
to FILE03/FEED06, without qualifying Save or another provider tuple.

`AccessibleUI.feedback_snapshot('formatted')` reads the `body-smoke` text/emoji,
synthetic reply and the bold/normal public ranges. Full `body-blocks` formatting
is owned by UI tests using the same worker composites. `formatted-file` additionally
requires the exact attachment ID, name, displayed 26-byte size and diagnostics.
The finite success statuses allow the original attachment confirmation or its
cleared state after collection on reopen; errors still refuse. The shared
`attachment_composition.compare_formatted_draft` validates the complete closed
projection, and `FeedbackDraftJourney` requires independent earlier evidence
before preservation or reset comparisons. DESK10 retains the same window/PID
and draft across switching. FEED05 reads Privacy without following a link.

Cases and qualifications share the declaration/execution pairs
`window_switch.window_switch_entry` / `onpc_feedback_read::prepare_window_switch`
and `feedback_composition.privacy_review` / `onpc_feedback_privacy::review_privacy`.
The former observes Parent, launches the supporting viewer once, then returns
through the guarded existing-window operation. The latter opens Privacy and
closes it through UI18 before independently comparing the returned draft.
Callers select the qualified draft profile and own phase boundaries, independent
entry/refusal checks and later preservation/reset assertions. Invocation prefixes
rename evidence, not operations; window comparisons resolve the plan's operation
so a renamed invocation cannot bypass identity or draft checks.

FEED10 reuses `preserve_dialog` and `app_exit`; the latter and `onpc_window::close`
accept a unique invocation prefix for repeated close proofs. Parent relaunch
must expose empty body/reply, no user files, no block/link semantics and normal
public inline attributes before any input. Case 152 uses that first complete
fresh-app feedback observation as its reset result; no unchanged second read
follows it. Fresh close-recipient proofs before earlier dialog closes remain
required by the shared ownership contract. Thus FEED03/05/10 include this
formatted, one-file Parent profile as well as `synthetic-first`. Other surfaces
and undeclared profiles remain pending. `feedback_formats.all_formats(prefix)`
and `onpc_format::apply_all(journey, prefix)` share the original finite selection
sequence while giving repeated applications distinct observations. No Send.

#### Attachment rejection boundaries

`attachment_boundaries.PLAN` / `AttachmentBoundariesJourney` passed
`tools/run-tests integration check_e2e_attachments` in
`20260927T201620Z-2f063a97`. It composes the preview plan, shared
`AccessibleUI.remove_attachment` and
`onpc_feedback_read::chooser_handoff` / `boundary_batch`. Independent chooser
entry, wrong-entry refusal, exact public results, fixture/worker cleanup,
collection and baseline restoration passed. The qualified provider is Nautilus
`1:50.2.2-0ubuntu0.1`, `en_US.UTF-8`, `xkb/us`. The affected item and preview
regressions passed in `20260927T202223Z-a017145c` and
`20260927T202523Z-dcb2ff2a`, with the same cleanup guarantees. No Send is invoked;
this supplies no complete-scenario credit.

`SyntheticFiles(transport, profile)` stages separately owned, exact directories
for six finite profiles: `count` has `Count 1.txt` through `Count 5.txt` (one
`C` byte each); `sixth` has `Count 6.txt` (one `C` byte); `maximum` has
`Maximum.txt` (5 MiB of `M`); `oversized` has `Oversized.txt` (5 MiB+1 of `O`);
`total` has `Total.txt` (3 MiB of `T`); `overflow` has `Overflow.txt` (3 MiB+1
of `X`). Each uses the existing fixture root with its fixed profile suffix,
exclusive creation, exact byte/identity receipts, independent readback and
receipt-checked cleanup. No arbitrary paths or contents are accepted.

`AccessibleUI.chooser_operation(profile=...)` reuses the qualified ownership,
Location/EditableText and Selection handoff. SelectAll requires the exact
profile's entire file set and independently verifies all selected files before
Open. Each batch's `before`, `result` and `preserved` operations independently
read public attachment IDs, names, displayed sizes/order, status and diagnostic
inclusion. The journey compares captured immutable pre-rejection lists after
both rejection reads. Five files are accepted; a sixth is rejected unchanged.
After public removals and the diagnostic toggle, 5 MiB is accepted and 5 MiB+1
rejected unchanged. Adding 3 MiB must accept exactly 8 MiB; removing that file
and adding 3 MiB+1 must reject and retain the existing 5 MiB file. The public
`No logs attached` row and hidden download control prove diagnostic exclusion.
The client counts cached diagnostics toward the limit only while they are
included. The loader regression in
[test_feedback_collection.py](../../tests/unit/test_feedback_collection.py)
preserves acceptance at 8 MiB without logs, rejection with included logs, and
rejection at 8 MiB+1 without logs. The fixture safety, public adapter/decoder,
worker sequencing and rejection-preservation checks remain in
[test_e2e_files_cleanup_safety.py](../../tests/unit/test_e2e_files_cleanup_safety.py)
and [test_e2e_feedback_read.py](../../tests/unit/test_e2e_feedback_read.py).
Other filenames, mixed selections, source changes, surfaces and offered previews
remain pending with their consumers.

#### Attachment item metadata and removal

`AccessibleUI.feedback_snapshot(attachments='details')` reads the prepared
`Second note.txt` / `Synthetic note.txt` rows in displayed order, with exact
sizes of 33 / 26 bytes. Each row is resolved by its public attachment ID;
order is an observed result, never a selector. Read the displayed subtitle via
the row's public `DESCRIBED_BY` relation: GTK's `Description` property is empty.
Require one visible relation target within that row's complete current subtree.
Missing, duplicate, stale, foreign or mismatching metadata refuses.

`AccessibleUI.attachment_operation` binds `attachment-details`,
`attachment-wrong-entry`, `attachment-remove` and `attachment-remaining`.
Remove targets `Second note.txt` by its owned Remove ID exactly once. Because
GTK queues activation, the bounded result wait permits only the unchanged valid
old list while pending. It requires the exact remaining `Synthetic note.txt`
row and 26-byte size; wrong-item removal refuses and uncertain input is never
replayed. The `attachments='remaining'` profile and `UiObservations` decoder
retain this exact one-file expectation and the diagnostic attachment.

[attachment_items.py](../../tests/e2e/attachment_items.py) composes
`file_chooser.journey` and the shared `onpc_feedback_read::run_file_chooser`
items branch, retaining the prepared-file controller through owned cleanup.
Reusable chooser input lives in `onpc_feedback_read::supply_files`; its matching
declaration is `attachment_composition.file_handoff`. Boundary batches call
that same input sequence. Qualifications retain their own independent entry,
wrong-entry refusal and Cancel assertions rather than adding those checks to
every customer handoff. `synthetic_files.fixture_actions` binds an explicit tuple
of file profiles to guarded staging and cleanup, retains each controller before
transport, and refuses repeated preparation or cleanup without its owned set.
Use this library directly in future cases; the qualification modules own recipes.

The composition refactor passed host worker/fixture/comparison regressions and
live `check_e2e_file_chooser` in `20260928T012531Z-b814a47d`,
`check_e2e_attachment_items` in `20260928T012819Z-76605176`,
`check_e2e_attachment_preview` in `20260928T013127Z-fdb49954` and
`check_e2e_attachments` in `20260928T013920Z-68c267ef`. Collection, owned fixture
cleanup, worker shutdown and baseline restoration passed. These runs preserve
the qualified scopes below; they supply no complete-case or offered-preview credit.

`tools/run-tests integration check_e2e_attachment_items` qualified the slice in
`20260927T175107Z-aac1d11d`; the shared chooser regression passed in
`20260927T175421Z-d6087694`. Real Add files/Open, independent reopen/Cancel,
wrong-entry refusal, metadata/order, removal and fresh remaining-list readback
passed with collection, worker cleanup and baseline restoration. Send was
untouched. Reuse the chooser's recorded provider tuple; no additional provider
binding or complete scenario is qualified here.

Host regression coverage in
[test_e2e_feedback_read.py](../../tests/unit/test_e2e_feedback_read.py) retains
metadata/ownership/order refusals, queued action completion, stale and wrong-item
removal without replay, worker sequencing and exact decoder checks.
[test_parent_feedback.py](../../tests/ui/test_parent_feedback.py) exercises the
same adapter against real GTK rows in the private preview; that seeded fixture
is engineering coverage, not a substitute for the installed chooser journey.
The declared [rejection boundary profiles](#attachment-rejection-boundaries)
add qualified metadata/removal bindings. Other file sets and offered previews
remain pending.

Complete reduced case 154, `parent_feedback_attachments.PLAN` /
`onpc_feedback_privacy::_attachments`, passed in
`20260928T165312Z-34f506c3`. It reused the shared two-file chooser Open,
reopen/Cancel preservation, exact displayed metadata and removal/remaining-list
comparison; the full boundary matrix remains in the UI test. The affected
`check_e2e_attachments`, `check_e2e_feedback_privacy` and
`check_e2e_window_switch` qualifications passed separately in
`20260928T171342Z-7bca2287`, `20260928T182554Z-16a03049` and
`20260928T182911Z-8db012de`, with collection, owned cleanup and baseline
restoration. No Send or diagnostic export.

#### Attachment preview applicability

`AccessibleUI.attachment_operation('attachment-preview')` qualifies the
explicitly inapplicable branch for the declared Parent two-file profile.
`feedback_snapshot(attachments='preview')` resolves each row and its
`feedback-preview-availability-*` icon by owned public ID, checks the accessible
"Preview is not available" label and validates the row's public action set.
The generic `row.activate` action and GTK label text/clipboard/link actions are
not preview handlers. Unexpected actions, wrong owners, missing or ambiguous
IDs and changed metadata refuse; a newly offered preview requires its own
implemented and qualified public route. No external editor or private file
inspection supplies preview acceptance.

[attachment_preview.py](../../tests/e2e/attachment_preview.py) composes the
shared `onpc_feedback_read::run_file_chooser` preview branch and retains the
prepared-file controller through cleanup. The shared
`attachment_composition.AttachmentJourney` captures
an immutable `attachment-details` list, then compares independent
`attachment-preview` and `attachment-preview-return` observations against it.
`UiObservations` validates the exact public result, including `not-offered`.
The same journey compares rejected boundary batches, including diagnostic
inclusion, against their independent pre-input lists. It resolves operation
names through the plan so a consumer can use distinct invocation names without
silently losing comparisons. The qualification's `AttachmentPreviewJourney`
and `AttachmentBoundariesJourney` imports alias this shared implementation.

`tools/run-tests integration check_e2e_attachment_preview` qualified this scope
in `20260927T193459Z-36234a89`: independent entry/wrong-entry refusal, real
chooser handoff and Cancel, preview inapplicability and unchanged names, sizes
and order passed. Collection, owned fixture/worker cleanup and baseline
restoration passed. Reuse the chooser's recorded provider tuple. Send was
untouched; this supplies no offered-preview content or complete-scenario credit.
The affected `check_e2e_attachment_items` regression passed in
`20260927T193811Z-d7dfede2`, including collection, owned cleanup and baseline
restoration.
The host adapter/worker/decoder refusals and immutable-list comparison remain in
[test_e2e_feedback_read.py](../../tests/unit/test_e2e_feedback_read.py), with real
GTK coverage in [test_parent_feedback.py](../../tests/ui/test_parent_feedback.py).
Other file profiles and surfaces remain pending.

#### Synthetic file commands

Task 036 qualified `SyntheticFiles.call` and `synthetic_files.qualify` through
`tools/run-tests integration check_e2e_files` in report
`20260927T062302Z-0a76f9d8`. Two independent entries staged `Synthetic note.txt`
and `Second note.txt`, copied the first to `Synthetic copy.txt`, renamed that
copy to `Renamed synthetic note.txt`, and independently listed/read exact bytes
after each operation. The fixed bytes/names live in
[synthetic_files_guest.py](../../tests/e2e/synthetic_files_guest.py).

The guarded SSH helper runs as the canonical Parent fixture account beneath
its private `.onpc-e2e-synthetic-files` home directory. It accepts only fixed
operations, takes a nonblocking shared directory lock, checks canonical paths,
ownership, modes, regular single-link files, exact contents and previous inode
receipts before mutation, and refuses unknown entries or replaced objects.
Copy uses exclusive creation; rename refuses an existing destination.
Cleanup requires the full owned receipt and independently observes absence.
An uncertain command permanently stops that controller; it cannot replay or
attempt cleanup with guessed ownership. The enclosing VM lease retains failed
evidence and owns baseline restoration.

Live qualification proved traversal/unregistered-operation, wrong-order and
duplicate-destination refusal without changing the fixture, independent entry,
exact content readback and owned cleanup. Host
[safety regressions](../../tests/unit/test_e2e_files_cleanup_safety.py) also cover
symlink/hardlink/wrong-owner/replaced/unknown-file refusal, concurrent commands,
uncertain transport and no acknowledgement after a failed fixture action.
Collection, worker shutdown and baseline restoration passed. This is fixture
capability evidence, not a complete product scenario. Chooser GUI, attachment
boundary profiles, original-file editing and application-enforcement launch
routes remain separate consumers.

### Time and ordinary lifecycle boundaries

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| TIME01 | C | Read the child's remaining usable time during activity or session return. Retain stable absence on the limits-off desktop as a qualified supporting observation; local lock/greeter visibility belongs to UI obligation 052b. | UI01 → UI03, or UI11 with the destination positively identified. `AccessibleUI.child_countdown(present)` / `countdown.CountdownObservation` and `check_countdown_balance`; [child-desktop qualification](#child-desktop-countdown-qualification). | child-desktop horizontal presence and limits-off absence ready; new customer time/session bindings need qualification, local visibility is UI scope |
| TIME02 | C | Compare displayed remaining time across real activity with public starting balances, elapsed intervals and explicit precision/tolerances. This supports actual time-use and expiry outcomes; tick formatting belongs in UI tests. | TIME01 → UI10 → TIME01 → UI12. No guest clock/usage manipulation. | pending |
| TIME03 | A | Let a declared bounded real interval elapse while retaining the runner guard and deadline. Return elapsed time only; this does not prove a lock or grant expiry. | `real_interval.wait_real_interval(duration, deadline=absolute_monotonic, guard=attempt_guard, progress=callback)` accepts finite durations through 300 seconds, checks ownership/deadline between sleeps of at most 250 ms and publishes five checkpoints. `interval_action(duration)` binds it to an `InstalledJourney` stage action using the guard's attempt deadline. `real_interval_qualification.PLAN` / `onpc_parent_about::run_interval` passed `check_e2e_wait_a_bounded_real_interval_under_the_attempt_guard` in `20260929T212620Z-9ce87d41`: five real seconds between independent unchanged About endpoint/PID/product/version reads, valid entry and wrong-entry refusal, collection, owned cleanup and baseline restoration. Host safety checks cover lost ownership, deadline, cancellation, recorder failure and durable reply refusal. No product state follows from elapsed time. | guarded elapsed-time helper ready; five-second About slice qualified; complete consumers remain separate |
| TIME04 | C | Use the selected app/game until natural expiry, then observe the lock owning normal input and loss of desktop access. Earlier visible time and the timeout are explicit inputs. | Bounded APP03 → TIME03 repetitions, with TIME02 only while the countdown is showing → UI01(lock) → UI05(harmless normal input) → UI01(lock challenge)/UI02. Do not require a visible countdown during fullscreen play or inspect the game underneath the lock. | pending |
| LIFE01 | C | Close and reopen one named ordinary app through a shared direct command, unless the case explicitly tests its graphical launch route; observe its opening window. Do not reselect a child or restore settings before reading them. | `onpc_lifecycle::reopen(journey, 'parent', prior_window, 'management')` consumes `prior-window`, independently guards the active owned window, composes UI18 → PARENT01, then reads the initial child selection before edits. `app_restart.PLAN` / `onpc_app_restart::run` passed `check_e2e_app_restart` in report `20260925T070959Z-faca1de4`: fresh entry, already-closed and wrong named-window refusal without repair, complete old-window absence, new management window, initial selection, collection, owned cleanup and baseline restoration. Shared launch/close helpers are unchanged. Other ordinary apps use APP01 with the declared route; overlay/kiosk reopening uses their explicit exit/entry blocks. | Parent→management ready with the baseline eligible children; other apps/bindings pending |
| LIFE02 | C | Reboot through a fixed supported system command in the owned guest, then observe a new boot and fresh GDM in the same attempt. | `JourneyPlan.reboot_transition`, `InstalledJourney.submit_reboot` and `Transport.request_customer_reboot`; independent `ReadOnlyObservations.wait_boot_change` then fresh GDM. [Qualified install/reboot composition](#customer-reboot-continuity). No Shell power menu; product persistence and activation notices remain required. | fresh install/reboot/administrator return ready; other bindings pending |
| LIFE03 | C | Suspend through a fixed supported system command, wait the real interval, wake through the owned VM's supported input and observe the return. | Shared lifecycle harness → TIME03 → bound wake input → public result; unlock remains DESK08. No Shell menus. | pending |
| LIFE04 | C | Perform a declared real install/update/remove/reinstall/purge with a registered package command over guarded SSH; observe completion and the actual customer notice. | `package_install.submit_install` / `observe_install` compose FILE01/02/06 and AUTH03 with verified artifact identity, one submission and independent completion/final notice. `PackageInstallJourney` qualifies the fresh product-free install entry; [install qualification](#customer-package-install-composition). `submit_release` / `observe_release` and `PackageUpgradeJourney` qualify the [genuine v1.2/current upgrade](#genuine-package-upgrade), including old-release activation and unchanged boot after upgrade. No Terminal, sudo-prompt exercise or private product-state assertion. | install, genuine v1.2/current update and [finite Ubuntu libc6 reconfiguration/system result](#genuine-unrelated-package-reboot-request) ready; other update/remove/reinstall/purge bindings pending |
| LIFE05 | C | Follow the displayed activation requirement for the explicit finite list of affected apps/users: none, process reopen, session renewal, or reboot/login. | None: UI03(notice). Process: LIFE01 for each app. Session: DESK03 → GDM02 → DESK08 when reaching another retained user, then DESK04 → GDM07 for each required renewal. Reboot: LIFE02 → GDM07. Compare displayed state afterward; one user's logout does not renew every session. | pending |
| LIFE06 | C | Remove and restore the owned VM's Internet access through one shared distro-independent operation; independently observe offline/online state and required product results. Local test-control access remains available. | `vm_internet.InternetIsolation.enter(transport)` / `restore(lease)` and `offline_controls.offline_controls`; [owned VM Internet contract](#owned-vm-internet-isolation). No guest networking service, new transport or injected product fault. | ready for the VM Internet helper and Parent enable/disable with independent saved-state reads and same-window continuity; other product results and complete scenarios remain pending |
| LIFE07 | C | Read the installed product's owned restart modal before language setup; Close without reboot, re-enter and submit one normal Reboot now action. Observe a new boot, usable greeter and fresh target without the modal separately. | `AccessibleUI.restart_notice` / `restart_action` / `restart_closed` / `restart_usable`, `JourneyPlan.modal_reboots` and `UiObservations.submit_restart`; `restart_notice.RestartNoticeJourney` / `onpc_customer_reboot::restart_notice` compose LIFE04, fresh desktop/station entries and LIFE02's independent boot result. `check_e2e_restart_notice` starts product-free and binds Parent, direct Child App and kiosk without policy setup before the notice. `journey_blocks.restart_reentry` / `onpc_customer_reboot::restart_reentry` share Close/exit/reopening; `restart_kiosk_usability` supplies public Jamie selection before the independent Jordan/Jamie final guard. `fresh_parent_restart.PLAN` / `onpc_customer_reboot::run_parent_notice`, `fresh_child_restart.PLAN` / `run_child_notice` and `fresh_kiosk_restart.PLAN` / `run_kiosk_notice` bind complete cases 257–259 through the same package recorder and modal operations. Exact owners, duplicate/missing IDs and consumed input refuse; no marker injection or command-reboot fallback. [Installed qualification](#installed-restart-notice-qualification). | English fresh-install three-surface notice/Close/re-entry, kiosk reboot and postboot usability ready; complete Parent/Child App/kiosk cases 257–259 passed |

`journey_blocks.parent_reopen()` supplies LIFE01's shared checkpoint declaration
for `onpc_lifecycle::reopen`, including `initial-selection`. The app-restart
qualification and cases 152, 158 and 159 compose it before their separate draft
reset or child-persistence assertions; it never repairs the selected child.

#### Installed restart notice qualification

`check_e2e_restart_notice` passed all 15 assertions on Ubuntu 26.04 in
`20261008T001340Z-0ac17273` (historical report rotated by normal retention).
The genuine product-free install supplies the package completion/reboot notice;
English Parent, direct Child App and kiosk each show the owned modal before
language or policy setup, Close without a boot change and show it again on
ordinary re-entry. Wrong-owner refusal precedes input. One public kiosk Reboot now
produces a separately verified new boot and usable GDM. Fresh Parent is usable
with no modal and refuses a missing-modal reboot; public Parent setup then saves
enabled 30-minute allowances for Riley and Jamie before fresh Child App and
default kiosk entries require enabled Request and no modal. Installation's
disabled defaults are verified before that setup, not mistaken for an enabled
request prerequisite.

The affected command-reboot continuity regression passed all five assertions in
`20261008T002206Z-08d2c230` (historical report rotated by normal retention).
Both runs passed capture reconciliation, private collection, worker shutdown,
owned cleanup, baseline restoration, finalization and source/host preservation.
Host safety/composition and all three real GTK modal previews passed in
`20261008T001304Z-6721020e`. This qualifies the fixed English slice, not complete
cases or a Parent/Child App public reboot history. Tasks 302–304 supply
the complete histories below. No visual acceptance
or product defect is claimed.

Complete E2E-056 `parent`, case 257, passed all seven assertions on Ubuntu 26.04 in
`20261008T005153Z-5fc78720` (historical report rotated by normal retention).
`fresh_parent_restart.PLAN` / `onpc_customer_reboot::run_parent_notice` compose
the product-free package install, Parent Close/re-entry, one public Parent reboot,
independent changed boot/usable GDM/fresh administrator entry and usable Parent
without the modal. `journey_checks.restart_instructions` binds the recipe's
literal neutral text to each fresh owned public read before a reply or reboot.
The required command-reboot continuity regression passed all five assertions in
`20261008T010236Z-98646c71` (historical report rotated by normal retention).
Both passed collection, worker-title reconciliation, worker shutdown, owned
cleanup, baseline restoration, finalization and preservation. Scoped host checks
and coverage generation passed. This supplies no Child App/kiosk complete-case
or unrelated-reboot acceptance.

`journey_blocks.restart_reentry` / `onpc_customer_reboot::restart_reentry`
share the same-boot Close/normal exit/reopening fragment between LIFE07 and
complete Parent/Child App/kiosk histories. The kiosk binding exits to usable
GDM and enters the station afresh; `fresh_kiosk_restart.PLAN` /
`onpc_customer_reboot::run_kiosk_notice` register case 259 with postboot public
Jordan setup and enabled Request plus usable Jordan/Jamie account selectors.
`journey_blocks.restart_kiosk_usability` /
`onpc_customer_reboot::restart_kiosk_usability` share the public Jamie selection
and independent final usability read with LIFE07. Baselines preserve other
eligible administrators, so the recipe supplies the declared approver input
instead of assuming the initial account order.
Complete case 259 passed all seven assertions on Ubuntu 26.04 in
`20261008T022232Z-88a775f3` (historical report/export rotated out):
genuine installation/final notice, first English kiosk modal before policy setup,
same-boot Close/normal exit/re-entry, one public kiosk reboot, new boot/usable GDM,
public Jordan enabled 30-minute setup and fresh usable Jordan/Jamie request without
the modal. The public Jamie selection repairs the omitted recipe input while
retaining wrong-child/approver, disabled-control and uncertain-input refusals.
The required shared three-surface notice regression passed all 14 declared
assertions in
`20261008T022938Z-30eb5c08`,
and command-reboot continuity passed all five assertions in
`20261008T023915Z-9b1c48e7` (historical exports rotated out).
All three passed collection, worker-title reconciliation, worker shutdown, owned
cleanup, baseline restoration, finalization and preservation. Scoped host safety,
independent helper consumption, controller result/refusal, composition and metadata
consistency passed; coverage was regenerated. This completes task 304's kiosk
history.

`fresh_child_restart.PLAN` /
`onpc_customer_reboot::run_child_notice` register complete E2E-057 `child`, case
258: direct pre-policy Child App entry, overlay modal reboot, independent boot
and GDM result, public postboot Riley setup and fresh fixed-child request
usability. Complete case 258 passed all eight assertions on Ubuntu 26.04 in
`20261008T014508Z-450ffde5` (historical export rotated by normal retention).
The required command-reboot continuity regression passed in
`20261008T015149Z-bfb425de` (historical report rotated by normal retention),
the shared three-surface notice qualification passed in
`20261008T012832Z-f24bf5b2` (historical export rotated by normal retention),
and Parent case 257 passed all seven assertions in
`20261008T013814Z-8069c961` (historical export rotated by normal retention).
All passed collection, worker-title reconciliation, worker shutdown, owned
cleanup, baseline restoration, finalization and preservation. Reports were
preserved through the maintained exporter before subsequent VM runs; those
historical reports later rotated under normal retention.
Scoped host safety/composition, metadata consistency and
traceability passed; coverage was regenerated. The consumer's unit/cleanup
tests retain private evidence and bounded waited Perl children with no new
resource lifetime. This completes task 303 without kiosk complete-case,
unrelated-request, other-language or visual acceptance credit.

#### Child desktop countdown qualification

`check_e2e_countdown` passed on every enabled VM in
`20261001T121730Z-8a327c27`, with separate restored enabled/off attempts.
`countdown_qualification.PLAN` / `OFF_PLAN` and `CountdownJourney` compose
shared fresh Parent/child entry and ordinary Parent allowance preparation;
`onpc_challenges::countdown` reuses the qualified login and Switch User helpers.
Both attempts save and read a positive 15-minute daily allowance. The off
attempt additionally disables limits through Parent and reads the saved result.
Wrong-account refusal on Parent and independently repeated child-desktop reads
pass without observer preparation or input. No complete scenario is qualified.

`AccessibleUI.child_countdown(present)` requires the active intended fixture
child and a complete guarded product panel observation. Presence resolves the
owned API IDs `child-screen-time-indicator`, `child-request-button` and
`child-remaining-time` on the bound `child-panel` surface, then
reads bounded horizontal `HH:MM` or final seconds. Complete absence of visible
indicator/button/label must persist for at least two seconds; wrong session,
incomplete or defunct reads restart that interval. Wrong owners, duplicate IDs,
unknown prompts, inactive/wrong accounts and malformed text refuse.

`countdown.CountdownObservation.from_value` returns an immutable result.
`countdown.check_countdown_balance` takes the caller's explicit public seconds,
precision and monotonic timestamp: this slice allows at most 180 real elapsed
seconds, the public balance's reported precision (one second in qualification),
flooring to minutes above 60 seconds, and two seconds of estimate/sampling
tolerance. Enabled reads showed `00:14` after 36.42 and 39.52 seconds from
Parent's balance. Off reads established absence for 2278 and 2347 ms.
No clock, usage, grant or private policy manipulation supplies the result.

Host safety/composition checks passed all 3932 tests in
`20261001T121457Z-2f7aded5`, including immutable capture, invalid/stale readback,
the real controller decoder, worker order, recorder startup and refusal before
durable reply. Separate fresh-child success, challenge and logout/switch
regressions passed `20261001T122258Z-caba8911`, `20261001T122606Z-1363057f`
and `20261001T122801Z-b6362573`. Every attempt passed collection, worker
shutdown, callback closure, owned cleanup and baseline restoration.
The installed tuple is Ubuntu 26.04, Shell `50.1-0ubuntu1.2`, GDM
`50.1-0ubuntu0.1`, actual locale `en_US.UTF-8` and keyboard `[["xkb", "us"]]`.
Local lock/greeter presentation and explanation checks remain UI obligations
052b/181h. Installed remaining-time observations, natural exhaustion and complete
cases retain their own bindings; those UI obligations are not their prerequisites.

For LIFE06, `disconnect` and `reconnect` in recipes mean remove and restore
Internet access, not disable a guest network adapter. Use the same qualified
VM-level implementation for Ubuntu, Fedora and other distributions. Establish
real Internet unavailability without losing controller access or allowing an
alternate Internet route. Networking is supporting test setup: once this fixed
mechanism and owned cleanup are qualified, consumers focus on app assertions.
Use that same helper from the current surface for recovery, including a child
desktop or GDM after a report closes. No Parent visit or login is needed solely
to restore Internet access.

### Owned VM Internet isolation

`vm_internet.InternetIsolation(lease).enter(transport)` requires the owned
running domain instance, matching guarded SSH transport and one unchanged NIC
on the active libvirt `default` network. It creates only a run-owned nwfilter
and tap binding through public libvirt APIs. The filter permits exact
controller/guest ARP and controller-initiated SSH, denies IPv4/IPv6 Internet
traffic and other Ethernet encapsulations, and changes no guest or shared
network configuration. The implementation is independent of guest distribution.

Use its context manager around the consumer's offline actions;
`vm_internet.restore(lease)` also runs in outer lease cleanup and recorded
recovery. Durable intent precedes mutation; wrong transport, uncertain replay,
changed domain/network/resource identity, foreign references and reused taps
refuse before cleanup mutation. A restored journal still audits resource absence.
Snapshot transitions refresh the pinned domain handle because libvirt caches
its instance ID. Compare network XML exactly except its read-only root
`connections` count; keep raw journal XML and every configuration check.

`vm_internet_qualification.online_offline_online` owns the finite helper
qualification; consumers use the isolation helper and
`vm_internet_qualification.internet_result(transport)` for independent bounded
TCP/UDP DNS observations. They do not inherit the qualification journey.
The offline language composition requires at least one reachable baseline path,
all declared probes blocked during isolation, and recovery of every path that
worked before it. A previously unavailable external endpoint may recover without
failing the product case. Exhaustive endpoint availability belongs to the
network helper's qualification, not language/policy acceptance; the shortened
language composition retains its pending live verification.
`parent_setup_qualification.IndependentNetworkQualification` passed
`tools/run-tests integration check_e2e_independent_network_management` in
`20260930T225447Z-420cdcde` on every enabled VM (the configured Ubuntu VM). It proved
online → offline → online, fresh SSH/public desktop reads, watch reconnects,
wrong-entry/replay refusal and exception-unwind restoration, with collection,
owned cleanup and baseline restoration. IPv6 had no default route in this run;
the helper denies it and probes it whenever one is available. Evidence remains
in `onpc-graphical-smoke-d8q5v0v_` and `onpc-e2e-evidence-oqm37q1r` under
privileged test allocations. Parent usability and other customer assertions
remain separate qualifications.

`offline_controls.offline_controls` composes declared public input/readback
operations with that same owned isolation lifetime. It pins the Parent window's
endpoint/PID before isolation, compares it around every input and after recovery,
and requires independent Internet probes before, during and after isolation.
`public_connectivity_controls.PLAN` / `qualify` reuse the unchanged UI17 control
sequence through `onpc_parent_toggle::run`, with fresh qualified sign-in and
PARENT01 launch rather than autologin/autostart preparation.
`check_e2e_operate_public_connectivity_controls` passed in
`20260930T233245Z-9d68a23f` on every enabled VM (the configured Ubuntu VM): disabled
entry and wrong-child refusal, offline enable/disable with separate saved-state
reads, unchanged active Parent window and Internet recovery. The affected
`check_e2e_toggle` qualification passed in `20260930T233540Z-66f7eb21`.
Both passed collection, owned cleanup and baseline restoration. These qualify
the exact Parent slice; no complete offline approval/enforcement scenario is
claimed. Runtime-binding failures retain bounded service/session state on
private command stderr without changing input, timeout or refusal checks.

### About, feedback and customer-selected attachments

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| ABOUT01 | C | Open the declared surface's About entry; read product/version and reach the license information. Parent, overlay and restricted kiosk bindings are ready. Kiosk reads plain legal information and proves external actions absent. | Parent: `onpc_about::open_about` / `AccessibleUI.open_about(version)`. Kiosk: `AccessibleUI.open_kiosk_about` / `read_kiosk_about(version)`; `onpc_window::close('station-about')` returns to the unchanged form. Overlay: `AccessibleUI.open_overlay_about` / `read_overlay_license` / `read_overlay_link`; `journey_blocks.overlay_license_read` / `onpc_about::overlay_license` close only owned About and return to captured choices. The finite `information` binding includes Help and every About link through `overlay_license.INFORMATION_PLAN`; complete case 191 uses `overlay_about.PLAN` / `onpc_parent_about::run_overlay` with shared `KioskRequestJourney` comparisons. UI01 → UI04(menu) → UI04(About) → UI01 → UI03 → UI09, plus kiosk UI11 exclusion. [About contracts](#about-block-contracts). | ready for Parent/kiosk/overlay; [Parent English/Hebrew inherited text and keyboard](#parent-inherited-dialog-qualification) qualified; full overlay information qualified by `check_e2e_read_overlay_about_and_links` in `20261002T045632Z-62a50e45`, license and website/privacy regressions passed in `20261002T050326Z-b8fd7de5`; complete case 191 passed on every enabled VM (Ubuntu 26.04) in `20261002T052623Z-0b463dbc` with collection and owned cleanup |
| ABOUT02 | C | Check the owned license link is clickable without invoking it or inspecting its URI/destination. | `AccessibleUI.open_license` is a compatibility name for `clickable_link('about-license-value', root=about())`; overlay `read_overlay_license` uses the same reader under `overlay_about_scope(opened=True)`. No external handler/content dependency. `check_e2e_license_viewer` retains its selector name for Parent link-only qualification. [Scope](#about-block-contracts). | ready for Parent link-only scope in `20260929T220011Z-55987e7f` and overlay scope in `20261002T040745Z-84b460dd` |
| ABOUT04 | C | Reach and read the About footer in the already open About window through semantic ID reveal. | `onpc_about::read_footer(journey, returned, 'semantic-reveal')` delegates to `AccessibleUI.about_footer`: UI09 → UI03(footer), with no preliminary positional keys. [About contracts](#about-block-contracts). | ready |
| ABOUT03 | C | Close only owned About and compare the selected child/settings with the supplied earlier observation. | Customer information return uses `onpc_about::close_information`, consuming the information observation and a fresh owned close proof before UI18; `JourneyPlan.settings_checks` supplies UI12. The historical `onpc_about::return_to_parent` link-only qualifier additionally composes ABOUT04 → UI18. Its footer read is not a prerequisite of the customer information return. No external window or handler is inspected/closed. | historical Parent link-only scope ready in `20260929T220011Z-55987e7f`; shortened information-return composition awaits live verification; other bindings pending |
| FEED01 | C | Open ordinary Parent feedback through its Feedback action and observe editor/collection state. Error-report entry uses FEED15; no hidden error creation. | `AccessibleUI.open_feedback(projection='initial-empty', language=None)`: UI01 → UI04(`parent-feedback-button`) → UI01 → UI02 → UI03. `feedback_read.PLAN` / `onpc_feedback_read::run` qualified initial empty entry and independent reopen through `check_e2e_feedback_read` in run `20260925T011124Z-21d4f936`. `check_e2e_feedback_privacy` additionally qualified preserved `synthetic-first` entry in `20260926T214728Z-4a3ca1b4`; collection, owned cleanup and baseline restoration passed. Send remains untouched. | ready for ordinary Parent initial-empty, synthetic-first and [English/Hebrew synthetic-rtl entry](#parent-inherited-dialog-qualification); other bindings pending |
| FEED03 | C | Read the visible synthetic draft, exact attachment list and validation/control state into an explicit observation. | `AccessibleUI.feedback_snapshot(projection, language=None)` → explicit closed comparison: UI01 → UI02 → UI03 → UI13(attachments). `check_e2e_feedback_read` qualified `initial-empty` in `20260925T011124Z-21d4f936`. `check_e2e_feedback_privacy` qualified `synthetic-first` in `20260926T214728Z-4a3ca1b4`, including unchanged Privacy/dialog reopening. The [attachment handoff](#attachment-chooser-handoff), [boundary lists/statuses](#attachment-rejection-boundaries) and [formatted one-file lifecycle](#formatted-one-file-draft-lifecycle) add exact finite files, metadata and format comparisons. Never project arbitrary private text. | ready for Parent initial-empty, synthetic-first, [English/Hebrew synthetic-rtl](#parent-inherited-dialog-qualification), formatted single-file, fixed two-file and declared boundary readback; other bindings pending |
| FEED04 | C | Set the retained editor selection using canonical UTF-16 index/length, apply an offered format through its fixed API value/action, then independently read document formatting and text. | `onpc_format`, `AccessibleUI.format_operation`, `block_operation` and shared format composites use `feedback-editor-selection`, formatting IDs and UI24. Synthetic link editing uses fixed link actions without navigation; document insertion and undo/redo use their fixed API operations. Historical qualification reports: `20260927T220402Z-60e41f1b`, `20260927T221053Z-796e5c0f`, `20260927T221352Z-4432e213`, `20260928T000001Z-b07e2a8f`, `20260928T000512Z-196ba37b`, `20260928T000805Z-44ce5cac`, `20260928T005139Z-951ec3ec`, `20260928T005856Z-1f56e149`, `20260928T010152Z-75515a1c`. | ready for declared Parent bold, four-format complex and `body-blocks` fixtures, linked inline and complete format/removal composition; other bindings and complete scenarios pending |
| FEED05 | C | Open Privacy, read the disclosure/diagnostic explanation, then close it. | `AccessibleUI.feedback_privacy(projection)` → `onpc_window::close('feedback-privacy', proof)` → `AccessibleUI.window_closed('feedback-privacy', 'feedback')`: UI04 → UI09 → UI03 → UI18. Reads the actual ID-owned disclosure about delivery, retention and diagnostic/personal content; opens no external link. `feedback_privacy.PLAN` / `check_e2e_feedback_privacy` qualified Parent synthetic-first and independent reopened entry in `20260926T214728Z-4a3ca1b4`; case 152 adds the [formatted one-file draft](#formatted-one-file-draft-lifecycle). Draft comparisons, collection, owned cleanup and baseline restoration passed. | ready for Parent synthetic-first and formatted single-file; overlay/kiosk and other projections pending |
| FEED06 | C | Add prepared synthetic attachments through Add files and the actual file chooser, then observe the displayed list or validation. | UI04 → FILE03 → FEED03. The [attachment handoff](#attachment-chooser-handoff) and [item qualification](#attachment-item-metadata-and-removal) cover fixed two-file Parent entry and metadata/order. The [formatted one-file lifecycle](#formatted-one-file-draft-lifecycle) adds the single-file profile. `AccessibleUI.boundary_operation` / `onpc_feedback_read::boundary_batch` qualify the declared [count/size boundaries](#attachment-rejection-boundaries), with independent unchanged-list comparisons after rejection. | ready for fixed single/two-file Parent handoff and declared count/per-file/aggregate boundaries; other inputs/validation pending |
| FEED07 | C | Resolve one attachment row by its stable public ID, then read its displayed synthetic name/size and verify its order if required. Order is a result and never identifies the row. Does not preview or remove it. | `AccessibleUI.feedback_snapshot(attachments='details')` / `attachments='remaining'` → exact public `items`; see [qualified item scope](#attachment-item-metadata-and-removal). `attachment_state` adds the declared [boundary profiles](#attachment-rejection-boundaries); `formatted-file` adds the exact name/size in the [one-file draft](#formatted-one-file-draft-lifecycle). UI01 → UI03 → UI13(order when required). | ready for declared Parent two-file, remaining-file, formatted one-file and boundary profiles; other inputs/surfaces pending |
| FEED12 | C | Open an offered attachment preview, read declared synthetic contents and close it, returning to feedback. Explicitly record an unoffered preview and independently compare the unchanged list. | `AccessibleUI.attachment_operation('attachment-preview')` / `attachment-preview-return` → `AttachmentPreviewJourney` comparison; [qualified applicability scope](#attachment-preview-applicability). Offered route: UI01 → UI04 → UI03 → UI18. An unoffered preview does not authorize private storage inspection. | ready for declared Parent two-file inapplicability and unchanged-list comparison; offered preview and other bindings pending |
| FEED13 | C | Remove one explicitly identified attachment and observe the remaining list. | `AccessibleUI.remove_attachment` supplies `attachment_operation('attachment-remove')` → independent `attachment-remaining` and the explicit [boundary removals](#attachment-rejection-boundaries); [qualified item scope](#attachment-item-metadata-and-removal). UI01 → UI04(Remove) → FEED03 → UI12(expected list). | ready for declared Parent single-item and boundary-profile removals; other inputs/surfaces pending |
| FEED08 | C | Explicitly save diagnostic output to a customer-selected location, inspect that exported artifact through the shared read-only SSH helper, and reobserve the preserved feedback draft. | `attachment_composition.diagnostic_export` / `onpc_feedback_read::diagnostic_export`: UI04(download) → shared `save_handoff(draft='synthetic-first')` → FILE08 through `diagnostic_export_actions` → FEED03 and same-dialog endpoint/PID comparison in `DiagnosticExportJourney`. Qualification revalidated two independent entries in `20260929T204158Z-388a25b4`; see [export scope](#customer-artifact-read-boundary). `parent_diagnostic_export.PLAN` / `onpc_feedback_privacy::_diagnostic_export` passed full case 155 in `20260929T203255Z-29d6637e`, including synthetic Cancel, `destination='unwritable'` app error before recovery, Privacy and preserved draft. No original product log/storage reads. | ready for named Parent Save/export inspection, Cancel, fixed unwritable-destination error/recovery and preserved synthetic-first draft; other surfaces/destinations pending |
| FEED09 | C | Observe collection, validation, sending, retry, error or thank-you state and control availability. Collection waits for finished diagnostics and available Download; immediate completion passes without observing an intermediate state. Other modes retain their declared state assertions. | `UiObservations.observe('feedback-collection-ready')` → `AccessibleUI.wait_feedback_collection` reuses `AccessibleUI.wait` with complete public ID-owned snapshots. It advances only when collection is finished and Download is available; the deadline only fails a stuck attempt. `feedback_collection.PLAN` / `onpc_feedback_states::run_collection` qualified two independent Parent entries, separate readback, wrong-entry refusal and owned cleanup through `check_e2e_feedback_collection` in `20260929T170731Z-88b24b8a`. `AccessibleUI.feedback_snapshot(projection, states=True)` → immutable `FeedbackStateObservation`; `feedback_states.PLAN` / `check_e2e_feedback_states` qualify the [edit-only Parent snapshots](#feedback-validation-snapshots). `reject_invalid_feedback` / `rejection_operation` and `feedback_rejection.PLAN` additionally qualify the fixed [invalid-only rejection](#feedback-rejection) inputs and exact explanations. `length_operation` / `feedback_length.PLAN` qualify the [ASCII and mixed-emoji boundaries](#feedback-utf-16-boundaries). UI01 → UI02 → UI03 → UI10, or UI22 with the same projections. No provider receipt or delivery-internal assertion. | ready for Parent collection readiness and declared Parent edit-only snapshots, ASCII/mixed-emoji boundaries and empty/malformed/SOH/complex/excessive-text rejection; other validation inputs, sending/retry/success and other surfaces pending |
| FEED10 | C | Close/reopen feedback and compare its in-memory draft. `dialog` preserves the supplied draft; `app-exit` explicitly closes/relaunches Parent and expects reset. Return with feedback open. | `onpc_feedback_privacy::preserve_dialog(journey, before)` composes FEED03(before) → UI18(feedback) → FEED01 → FEED03 → UI12 against an explicit earlier observation. `app_exit(journey, before, invocation_prefix)` composes UI18(feedback) → LIFE01(Parent→management) → FEED01/03(`initial-empty`) before new input. Wrong-entry refusal remains in the isolated `run_reset` qualification, outside the customer fragment. `feedback_reset.PLAN` / `check_e2e_feedback_reset` qualified nonempty body/reply → empty body/reply, no customer-selected files and fresh default diagnostics in `20260927T205202Z-fc8560e8`. `check_e2e_feedback_privacy` requalified dialog preservation in `20260927T205545Z-2fd1c308`. The [formatted one-file lifecycle](#formatted-one-file-draft-lifecycle) extends both comparisons through `FeedbackDraftJourney`; shortened complete case 152 passed on Ubuntu 26.04 and Fedora 44 with collection and owned cleanup. | ready for Parent dialog preservation, isolated reset and formatted one-file case 152; [Parent dialog synthetic-rtl across English/Hebrew changes](#parent-inherited-dialog-qualification) also qualified; other surfaces/profiles pending |
| FEED11 | C | Submit one already reviewed synthetic report. Require explicit sending authorization and dedicated test-recipient configuration; activate the explicit `Send` or `Send without logs` action once and return. Observe the outcome and dismiss confirmation separately. | UI01 → UI02(enabled) → UI04(Send). Prior FEED03 → FEED05 evidence is supplied, not repeated inside this block. This document grants no sending authorization. | pending |
| FEED14 | C | Dismiss an observed success confirmation normally and observe the expected return surface. | UI01 → UI04(Close) → UI11(confirmation) → UI01(return surface). FEED09 supplies the earlier success observation. | pending |


#### Feedback validation snapshots

`check_e2e_feedback_states` last passed in report `20260927T180816Z-1660edb1`,
including independent reopened entry, wrong-entry refusal, collection, owned
cleanup and baseline restoration. `AccessibleUI.feedback_state_operation`
observes edits supplied by the caller through `onpc_text::replace_text`; it never
activates Send. Exact bounded public text comparisons bind these projections:

| Projection | Body | Reply |
| --- | --- | --- |
| `initial-empty` | Empty | Empty |
| `states-whitespace` | Three ASCII spaces (`body-whitespace`) | Empty |
| `states-no-reply` | `Synthetic feedback first` | Empty |
| `states-malformed` | `Synthetic feedback first` | `invalid-reply` (`reply-malformed`) |
| `synthetic-first` | `Synthetic feedback first` | `first@example.invalid` |

UI16's additional `body-whitespace` and `reply-malformed` bindings passed exact
readback in this slice. Each snapshot independently reads Send sensitivity and
the public validation status, with exactly `diagnostic-logs.zip`, collection
ready and the remaining controls usable. The current app validates body/reply
only on Send; after these edits the expected state is **enabled Send and no
validation explanation**, including invalid input. Reopening must preserve the
valid snapshot before any new input. This does not establish submission rejection.
The fixed rejection explanation projections are qualified separately below;
disabled-Send observation still has host coverage only. Complete case 153 is
qualified [below](#complete-local-validation); never infer rejection from input validity or
substitute private transport validation for public evidence.

`feedback_states.edit_states()` declares the shared edit-only matrix;
`onpc_feedback_states::edit_states(journey)` executes it for both qualification
and complete-case composition. Its entry is an open empty Parent feedback
dialog, and its result is the independently read valid synthetic draft. It
includes no Send or dialog lifecycle. The caller owns subsequent close/reopen
and independent-entry checks.

#### Complete local validation

[`parent_feedback_validation.PLAN`](../../tests/e2e/parent_feedback_validation.py)
composes the installed case 153 [sample](E2E-Scenario-Recipes.md#feedback-local-values)
through `record_installed_journey`,
[`FeedbackValidationJourney`](../../tests/e2e/feedback_composition.py) and
`onpc_feedback_privacy::run(exchange, 'validation')`. Repeated operations have
unique invocation IDs. Public snapshots and guarded invalid-only rejection
cover an empty send followed by body/reply editing and recovery after reopening.
UI tests retain text/email, ASCII/emoji boundaries, SOH and excessive formatting,
using the shared text/format/state composites and public comparisons.
No valid submission or portal mutation is permitted. Qualification-only wrong-entry
and repeated-rejection checks remain in their callers; shared blocks do not
choose a case's recorder phases or reset its dialog implicitly.

Case 153 passed in report `20260927T183144Z-a559af49`, including collection,
owned cleanup and baseline restoration. The shared edit-state and UTF-16
composites passed their independent qualifications in
`20260927T180816Z-1660edb1` and `20260927T181813Z-ee5c57b5`, with the same
cleanup guarantees. These results do not qualify the other local feedback cases,
additional surfaces or sending/delivery behavior.

#### Feedback rejection

`feedback_rejection.PLAN` / `FeedbackRejectionJourney`,
`onpc_feedback_states::run_rejection` and `AccessibleUI.rejection_operation`
last passed `check_e2e_feedback_rejection` in `20260927T055529Z-5492a75e`.
The qualification covers empty body, malformed reply, the authorized SOH fixture
and excessive formatting, exact public explanations, usable controls, independent
reopened entry, wrong-entry and valid-input refusal. Collection, owned cleanup
and baseline restoration passed. No valid report is submitted; complete case 153
has separate [composition acceptance](#complete-local-validation).

`reject_invalid_feedback(case)` requires a fresh owned editor, exact bounded
body/reply and enabled Send. It refuses valid, mismatched, ambiguous, stale or
uncertain input before the single Send action. The subsequent `*-read` operation
independently observes the exact `FEEDBACK_VALIDATION` explanation and controls;
input validity alone supplies no rejection credit. Reopening must retain the
complex text and all formats, clear the previous status after diagnostic
collection, and permit a second independently guarded rejection.

UI16's hidden fixture is `a\x01b`: literal SOH text through the fixed editor API
between `a` and `b`, with exact public text/scalar comparison
before Send. The product rejects both NUL and SOH; NUL retains product regression
coverage. No valid substitute, private editor assignment or arbitrary text export
is permitted.

The formatting fixture is 1,200 `x` paragraphs separated by newlines (2,399
UTF-16 units), built through the shared duplication route below. A canonical
`feedback-editor-selection` range precedes each named bold, italic, underline
and strike operation. `rejection_formatting` reads the public document delta
and requires all four attributes on every declared synthetic `x` range, including
after reopening. Missing formats or incomplete bounds refuse; removal checks
confirm that each attribute clears when its format is removed. No toolbar-only,
arbitrary DOM or private-draft proof is accepted.
The maintained paragraph serialization requires at least 57,600 HTML units while
the body stays below 5,000; transport-limit regressions guard this invalid-only
precondition, and the live public complexity explanation supplies acceptance.

#### Feedback UTF-16 boundaries

`feedback_length.PLAN` / `FeedbackLengthJourney`,
`onpc_feedback_states::run_length` and `AccessibleUI.length_operation` passed
`check_e2e_feedback_length` in report `20260927T181813Z-ee5c57b5`. Exact public readback
qualified 5,000/5,001 ASCII `x` characters and 4,998/4,999 `x` characters followed
by U+1F600. Public character offsets count scalars; the mixed fixtures contain
5,000/5,001 UTF-16 units. Only the editor's implicit terminal newline is allowed.

`feedback_length.length_boundary(family)` and
`onpc_feedback_states::length_boundary(journey, family)` are the shared
declaration/execution pair for `ascii` or `mixed`. Starting with an open Parent
feedback dialog and empty reply, they replace the body, observe/refuse the valid
boundary, then submit only the exact invalid boundary and independently read its
rejection. They leave that result visible. The caller owns dialog return,
wrong-entry checks and repeated rejection, so qualification and customer cases
reuse identical input/result mechanics without inheriting each other's recipe.

UI16 uses the guarded clipboard construction below, followed for mixed input by
`onpc_text::append_scalar` / `AccessibleUI.scalar_text_operation`: exact ASCII
source and public caret proofs precede ordinary numeric Unicode input.
`feedback_plain_text` proves normal public attributes over the entire body.
At 5,000 units, `LENGTH_OBSERVATIONS` independently confirms enabled Send and
no validation message; the invalid-only guard must refuse that valid draft.
At 5,001 units, `REJECTION_CASES` permits one Send only after fresh exact owned
body/reply and length proofs. Independent public reads require
`Feedback must be at most 5,000 UTF-16 characters (some emoji count as two).`
and usable controls. Each family closes, refuses wrong entry, reopens and
compares its preserved draft and repeated rejection independently. Host checks
also cover mismatched values, formatting, wrong owners, stale/ambiguous targets
and uncertain input; none may reach Send.

Qualification completed collection, owned cleanup and baseline restoration.
No valid report was submitted; complete case
153 has separate [composition acceptance](#complete-local-validation).

#### Synthetic text duplication

UI16 also has a shared `onpc_text::duplicate_text(journey, binding)` composite
for large declared nonsecret fixtures. `TEXT_DUPLICATIONS` maps each result to
its exact source. `AccessibleUI.duplicate_text_operation` checks that source,
selects the insertion point through `feedback-editor-selection` and inserts
the declared text through `feedback-editor-insert`, excluding the implicit
terminal paragraph newline. `TEXT_DUPLICATION_SEPARATORS` declares the exact join;
public readback must match `source + separator + source`. Any failure stops
before further input, without falling back to typing the full document.
No helper application, clipboard service, DOM assignment or private draft read
is involved. Shared UI/E2E operations use the same packaged editor adapter.

The rejection consumer sets the declared 75-line seed through the API, then
doubles to 150, 300, 600 and 1,200 lines.
This preserves the 2,399-character final fixture and all rejection assertions.
`check_e2e_feedback_rejection` qualified exact construction and the complete
consumer in `20260927T015525Z-a02ac59c`, with collection and owned cleanup. New bindings
must declare exact source/result projections and receive consumer qualification.

The four UTF-16 boundary inputs use `TEXT_REPETITIONS`: a 312-character seed,
four API insertions to 4,992 characters, and a 6–9-character suffix through
`onpc_text::repeat_text` / `AccessibleUI.suffix_text_operation`. The host UI test
uses these same public operations. Each source and doubled result is checked
before continuing; exact final ASCII/emoji text and UTF-16 boundaries remain
mandatory. `check_e2e_feedback_length`
qualified these bindings in `20260927T041209Z-240ad5c2`: all sixteen clipboard
doubles, exact ASCII/emoji boundaries, valid-input refusal, invalid-only rejection
and independent reopen passed, with collection, owned cleanup and baseline
restoration. This is scoped qualification, not complete case 153 acceptance.

### Additional public surfaces

These blocks supply the named new consumers in the
[scenario recipes](E2E-Scenario-Recipes.md). All are pending; a documented
binding does not extend an existing callable's qualified scope.

| ID | Kind | Block and explicit contract | Callees / first consumer | Status |
| --- | --- | --- | --- | --- |
| AUTH04 | A | Validate authority and protected-account restrictions for shared fixture account operations. No Users-settings password prompt. | Owned fixture/SSH boundary; product approval challenges remain AUTH01/02. | pending |
| ACCOUNT01 | A | Read the declared fixture account/role set through public system account interfaces over guarded SSH. | Shared account-fixture library with bounded nonsecret output. Preparation metadata only; app account lists supply customer assertions. | pending |
| ACCOUNT02 | C | Add/remove/change the role of a registered spare fixture account through shared system commands or AccountsService and read back the change. | Reuse `account_fixture` infrastructure; protect active/last administrator and station, registered secrets and owned cleanup. Independently observe Parent/request-selector refresh. No GNOME Users wizard. | pending |
| PANEL01 | C | Read the child's saved animation preference through `child-countdown-animation-toggle`; discover the owned panel surface independently. | Shared `child-panel` client `getValue`; use `child-countdown-menu.activate` only when ordinary menu entry itself is needed. E2E-022 cases 118/120 own persistence and isolation; E2E-008 case 22 owns locking with animation enabled. | pending |
| PANEL02 | C | Set the canonical animation boolean through the panel API and independently read it before continuing child activity. Preserve session/account persistence assertions. | UI17 on `child-countdown-animation-toggle`, independent PANEL01 readback and DESK01; no popup or Escape dependency. | pending |
| PANEL03 | C | Read the public countdown explanation through `child-request-tooltip.getText` in its local UI owner. | UI01 → UI03 through the shared panel API; local obligation 181h retains text/function assertions. | pending UI coverage |
| INFO01 | C | Check declared Help/About external links are clickable, then stop. Never invoke them or inspect their URIs/destinations. Kiosk asserts unavailable external actions instead. | `AccessibleUI.clickable_link(identity, root=owned_surface)` checks the ID-owned visible/enabled control and sole public activation action without input. Parent: `check_parent_help`, `open_about(menu_open=True)` and `check_parent_information`; shared worker calls `onpc_about::read_help`, `open_from_help`, `check_link`, `return_to_parent`. `license_viewer_provider.INFORMATION_PLAN` / `ParentInformationJourney` and `check_e2e_read_parent_information_links` qualify the composite through `onpc_license_viewer_provider::run(exchange, 'information')`. Historical case 190 used `parent_information.PLAN` / `onpc_parent_about::run_links`; its link-only assertions are now [UI-owned](UI-and-E2E-Coverage.md#duplicate-review-and-allocation), with no E2E executable. Overlay: `check_overlay_help`, `open_overlay_about(menu_open=True)` and `read_overlay_link`; `journey_blocks.overlay_license_read(links='information')` / `onpc_about::overlay_license(..., 'information')` compose Help and all five About links with caller-owned immutable form comparisons. `overlay_license.INFORMATION_PLAN` / `OverlayLicenseJourney` and `onpc_request_flow::overlay_information` supply the qualification; legacy license and browser-link plans/selectors retain their finite scopes. Complete case 191 owns `overlay_about.PLAN` / `onpc_parent_about::run_overlay` and shared `KioskRequestJourney` capture/return comparisons. Fresh independent entry, wrong-entry proof refusal, owned About close and unchanged Parent selection/settings or overlay choices. No external handler dependency. Kiosk UI11 on recognized About. [About contracts](#about-block-contracts); E2E-042. | Parent Help and all five About links qualified in `20260930T192004Z-89316fef`; historical case 190 passed in `20260930T195316Z-5a8d360d`. Overlay Help and all five About links qualified in `20261002T045632Z-62a50e45` on every enabled VM (Ubuntu 26.04); license and website/privacy regressions passed in `20261002T050326Z-b8fd7de5`. Complete case 191 passed on every enabled VM (Ubuntu 26.04) in `20261002T052623Z-0b463dbc`, including unchanged-form return, collection and owned cleanup |
| INFO02 | C | Read one installed product help command or command manual from bounded, guarded SSH stdout as the parent fixture account. | `onpc_documentation::read(journey, binding)` invokes `command_documentation.observe`; the stdout adapter checks fixed command identity, help usage/options or manual sections/purpose without Terminal rendering. Case 193 composes all four bindings and one final independent desktop result. Its historical run `20260923T194553Z-e2f16f7e` also checked the desktop after every command; those extra checks are removed from the current contract. | ready stdout bindings; consolidated case return awaits live verification |
| FEED15 | C | Review or decline a displayed product error report. Request result entry explicitly sets Report this error then closes the result; Parent entry observes its automatically opened report without inventing a report button. Read the report or declared exit destination. | Request: UI17(report choice) → UI04(result Close) → UI01 → FEED03 for review; Parent: `parent_reports.report_review` / `onpc_feedback_privacy::review_parent_report` → FEED03/UI16 → FEED05 → guarded UI18 → independent destination/rule read. Direct closure: `parent_reports.report_close` / `onpc_feedback_privacy::close_parent_report` → automatic-draft read → guarded UI18 → independent destination/rule read. See [automatic Parent error reports](#automatic-parent-error-reports). Parent has no report-choice toggle. E2E-045. | ready for the declared Parent review and edited/untouched report-close bindings; request surfaces and other bindings pending |
| FEED16 | C | Retry an observed failed diagnostic collection and read its result and retained draft. | UI04(Retry collection) → FEED09 → FEED03 → UI12. Scheduled qualification is Parent retry, E2E-046 case 208; overlay/station retry bindings are no longer scheduled. Station without-logs submission reuses FEED11 in case 213; it is not hidden inside retry. | pending |
| FEED17 | C | Attempt normal Close on a sending error report and read the stop-sending confirmation. Do not yet stop or exit. | UI04(Close) → UI01(confirmation) → UI03. E2E-047. | pending |
| FEED18 | C | Choose the explicit Stop sending and close or stay-open response, then read the destination. | UI04(response) → UI11(confirmation) → UI01(destination); report closure uses UI11(report) separately. E2E-047. | pending |
| TIME05 | A | Read actual local date/time, UTC offset and timezone through bounded `date`/`timedatectl` output over guarded SSH. Do not change them. | Shared clock observation with explicit precision/monotonic bracketing. No Shell calendar or Settings page. Natural calendar windows and product countdown assertions remain required. | pending |

### Reusable journey fragments

These fragments do not own fixture provisioning, attempt startup or cleanup.
Arguments include expected results and the exact accounts/apps/choices. No
fragment skips an unsuccessful step or resumes a previous attempt.

| ID | Kind | Block and explicit contract | Callees, in order | Status |
| --- | --- | --- | --- | --- |
| FLOW00 | C | Run case 1's complete graphical/serial qualification within the unchanged harness envelope. Its step boundaries and terminal assertions are fixed below. | `controller_qualification.PLAN` and `Smoke._step` bind the graphical stages to `gdm_product_free_account()` / `gdm_product_free_navigation()` observations; `onpc_flow00::run` consumes the exact product-free prompt proof before Escape. The existing authenticated serial command, session/boot identity, single logout, return reconciliation, capture assertions, collection and owned cleanup passed in an earlier retained case 1 run. | ready; retained case 1 implementation |
| FLOW15 | C | Reach an explicit user's desktop from the declared source surface. `entry=fresh` requires no retained session; `retained` requires an earlier observed desktop; `same` requires the current user already matches; `lock` requires the declared locked child session. Return the observed desktop or expected time-limit denial. | `journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop` compose fresh GDM, retained GDM/from-another-desktop, same-user and native lock branches, guarded by `session_control.entry_identity`. [Both-child qualification](#both-retained-child-desktops-and-explicit-entry-modes) covers Riley/Jordan fresh, same and reciprocal retained success, Riley lock/unlock and both zero-time denial routes. Existing [fresh-child success](#fresh-child-success-qualification), [fresh denial](#fresh-child-time-denial-and-return-qualification), [retained success](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) and [retained denial](#retained-child-time-restriction-and-greeter-return-qualification) remain qualified. | stated Parent and both-child fresh/same/retained bindings and Riley lock/denial ready; other bindings pending |
| FLOW01 | C | Open or return to Parent for a named child and record displayed settings. Inputs declare source, parent entry and `window=new` or `retained`. Default first entry is GDM/fresh/new; a return uses retained entry and the existing window. New launches always use PARENT01's direct command. | `onpc_parent::open_for_child(journey, source, entry, window, child, invocation)` composes fresh FLOW15 → PARENT01(management) → PARENT02, or `desktop/same-user/new` with independent window-absence and Parent-desktop observations before the direct launch and child selection. Retained/same-user branches consume `retained_parent_entry` with explicit invocation and preserved child/page/settings; [exact retained qualification](#retained-parent-desktop-and-window-entry) and [Riley-to-Parent return in the two-child history](#both-retained-child-desktops-and-explicit-entry-modes). `check_e2e_set_an_allowance_for_a_named_child` qualified fresh and independently reopened same-user Parent/child entries, persisted settings and wrong-window refusal in run `20260925T064318Z-ac40f2a1`, including collection, owned cleanup and baseline restoration. Case 6's affected launch regression passed in `20260925T064705Z-37ca73c8`. Fresh Parent/Riley also passed in case 151; second-parent and other bindings remain pending. | fresh and same-user/new bindings ready; Jamie/Riley retained entry from either child ready; other bindings pending |
| FLOW02 | C | Configure the selected child's time controls, observing save and explanation. Inputs declare initial/final enablement and allowance. Enable first only when needed to make the allowance editor usable. | `AccessibleUI.configure_time_controls(child, initial_enabled=…, minutes=…, final_enabled=…)`: PARENT04(Screen Limits) → conditional UI17(true)/PARENT08 → PARENT05 preset commit/PARENT08 → UI17(final boolean)/PARENT08 → PARENT03 → PARENT09. Qualified inputs are 0/15-minute presets and explicit boolean enablement, plus disabled→enabled with 30 minutes through FLOW16's fresh binding; custom values remain with PARENT06 until separately composed. `check_e2e_time_explanation` qualified enabled→disabled, disabled→enabled and enabled→enabled paths, saved settings, positive/zero balances and wrong-child/initial-state refusal in run `20260925T062949Z-49d65b22`, with collection and owned cleanup. Disabling intentionally clears a grant; it is never navigation. | ready |
| FLOW03 | C | Configure one app's matching and access choices through Parent and read the saved row. | `policy_edits.policy_edit` / `onpc_app_rows::edit_policy`: PARENT10 → PARENT11 if declared → PARENT13 → UI16(match draft) → PARENT15(save) → PARENT16 → PARENT12. Caller owns entry, finite inputs and exact comparisons; see [public app-policy edits](#public-app-policy-edits). | ready for Jordan/native fixture A's precise and `*.AppImage` match/access slice; other bindings pending |
| FLOW04 | C | Open the selected request surface, or use an explicitly already-open form, then choose child/approver/duration/app access and read the estimate. | REQUEST01 or REQUEST02 only for `entry=new`; `entry=open` starts with REQUEST03 → REQUEST04(child only in kiosk, approver, duration) → REQUEST05 if custom → REQUEST06 → REQUEST08. `request_flow.prepared_request` / `onpc_request_flow::prepare` qualify the explicit kiosk child/parent, custom 1.25-minute, soft-included binding for independently open and new entry; see [prepared request qualification](#prepared-request-qualification). `prepared_request(surface='overlay')` / `prepare(..., 'overlay')` reuse the shared overlay entry/form leaves for the fixed child, Jamie approver, 75 seconds and included soft apps: open/default and new/remembered branches passed [overlay FLOW04 qualification](#overlay-flow04-invalid-submission-and-escape-qualification). | pending; declared kiosk and overlay open/new bindings ready; other choices pending |
| FLOW05 | C | Complete a real approval from a prepared form, observe confirmation and its declared automatic or immediate exit. | REQUEST09 → AUTH02(correct credential) → REQUEST11(success) → REQUEST12(automatic or immediate). `kiosk_approved_flow.approved_request` / `onpc_request_flow::approve`; see [approved kiosk flow qualification](#approved-kiosk-flow-qualification). `request_flow.overlay_approved_request` / `onpc_request_flow::overlay_approve`; see [overlay composition qualification](#overlay-immediate-exit-and-approval-compositions). | fixed kiosk and overlay 75-second/soft-included automatic and immediate bindings ready; other choices pending |
| FLOW06 | C | Obtain time through kiosk from an existing GDM screen and return to GDM. | FLOW04(kiosk) → FLOW05. `kiosk_approved_flow.obtain_time` / `onpc_request_flow::obtain_time`; see [approved kiosk flow qualification](#approved-kiosk-flow-qualification). Child login/unlock is deliberately a later step. | fixed kiosk remembered-choice binding ready; other choices pending |
| FLOW07 | C | Reject/cancel one request and compare its preserved choices. Return with that form open; do not retry yet. | REQUEST03(before) → REQUEST09 → AUTH02(wrong/cancel) → REQUEST11 → UI12. `approval_flow.rejected_request` / `onpc_request_flow::reject`; see [rejected kiosk flow qualification](#rejected-kiosk-flow-qualification). `request_flow.overlay_rejected_request` / `onpc_request_flow::overlay_reject`; see [overlay composition qualification](#overlay-immediate-exit-and-approval-compositions). The recipe can inspect restrictions before invoking FLOW05 for a successful retry, avoiding a second implementation of approval. | fixed kiosk and overlay 75-second/soft-included rejection and Cancel bindings ready; other choices pending |
| FLOW08 | C | Exercise an app through its declared route and prove the expected usable/denied result. | `journey_blocks.native_usable_app(route)` / `onpc_app_rows::native_usable_app(journey, route, desktop)` compose APP01 → APP02 → APP03 for the declared native `command` or `grid` usable route; [qualification](#native-fixture-preparation). `native_usable_app('command', child='child')` adds Riley's usable-time command binding through the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). No alternative launch after failure. APP03 runs only for expected usable access. | native Allowed command/grid usable scope ready; policy denial and other bindings pending |
| FLOW09 | C | Visit an explicitly retained user and prove the same app/activity remains usable. Inputs include source surface and that user's earlier activity observation. | FLOW15(entry=retained) → APP04(compare) → APP03. | pending |
| FLOW10 | C | Launch the prepared real game with its declared mode/level and play to natural lock. | FLOW08(game, usable, registered launch options) → APP05 → APP04(record activity) → TIME04. | pending |
| FLOW11 | C | After a displayed lock, obtain legitimate replacement time, unlock and observe the expected retained app or closed blocked app. | DESK11 → FLOW06 → FLOW15(child, retained) → APP02 → APP04(compare) → APP03 when preservation is expected. Closed-app branch ends at APP02. | pending |
| FLOW12 | C | From an open request form, visit the other surface for that child and compare duration/custom/soft-app choices before editing. Compare the independently remembered parent for each requesting OS user, not parent equality across surfaces. Interactive mute is separate deferred scope. Finish with the second form open. | Overlay→kiosk: `request_flow.overlay_to_kiosk` / `onpc_request_flow::overlay_to_kiosk` compose REQUEST12(cancel) → DESK03 → REQUEST01 → REQUEST03. `KioskRequestJourney` compares immutable endpoints declared in `request_transfer_checks`; `choices_overlay_to_kiosk.PLAN` binds both children and same-kiosk persistence/isolation readbacks. The [both-child qualification](#overlay-choices-transferred-to-kiosk) passed the shortened scope on Ubuntu 26.04 and Fedora 44; its historical independent retained entry is no longer a prerequisite. Kiosk→overlay: REQUEST12(cancel) → FLOW15(child, declared fresh/retained entry) → REQUEST02 → REQUEST03 → UI12(shared values and user-local selectors), still unimplemented. Interactive mute remains deferred outside this current-choice composite. | overlay-to-kiosk both-child transfer and same-kiosk persistence/isolation ready; reverse pending |
| FLOW13 | C | Establish a named time profile entirely through customer controls and finish at GDM. Entry/window arguments are explicit. Verify no grant or revoke it first; use the profile table below. | FLOW01 → PARENT09. If revocation is declared: PARENT17 → PARENT18(confirm) → PARENT09. Then UI12(no grant) on that observation, without another unchanged read → FLOW02(initial allowance) → DESK03. Grant profiles then FLOW06 → FLOW01(parent/window retained); daily-dominant adds PARENT06(larger allowance, still enabled) → PARENT08. All grant profiles finish PARENT09 → UI12(profile) → DESK03. | pending |
| FLOW14 | C | Open apps/recognizable activities for a finite declared user list, retaining each desktop through Switch User. Inputs state each user's fresh/retained entry and usable-time/policy prerequisites. Start and finish at GDM. | For each user: FLOW15 → FLOW08 → APP04(capture) → DESK03. Earlier retained desktops must be revisited, not recreated. Multiple desktops for one identity require a supported customer route; see applicability notes. | pending |
| FLOW16 | C | As the named parent, reach Parent for the named child and set a daily allowance and final limit state. This is the reusable “Set Jordan's daily allowance to zero” recipe; zero is an allowance, not an approval. | `onpc_parent::set_allowance(journey, source, parent, entry, window, child, initial, minutes, final)` composes FLOW01 → FLOW02. Qualified bindings: `gdm/parent/fresh/new/child/0/0/1`, `desktop/parent/same-user/new/child/1/15/1` and `gdm/parent/fresh/new/child/0/30/1`. `set_allowance.PLAN` binds zero/15-minute setup to `time-explanation-setup-zero-read` and `time-explanation-setup-positive-read`; `fresh_thirty_allowance.PLAN`, `FreshThirtyAllowanceQualification` and `onpc_fresh_thirty_allowance::run` bind fresh 30-minute setup to `time-explanation-setup-thirty-read`. FLOW02 owns Screen Limits navigation and saved-settings validation. `check_e2e_set_fresh_thirty_minute_allowance` passed saved enabled/30-minute settings, independent 1800/0/1800-second daily/grant/total reads and wrong-child/state/window refusals in `20260926T211055Z-daafbf03`. Existing zero/positive setup, independent rereads, persisted settings and wrong-child/window refusal passed `check_e2e_set_an_allowance_for_a_named_child` in `20260926T210708Z-8962d2d1`; affected Parent launch case 6 passed in `20260926T211422Z-3cda058b`. All passed collection, owned cleanup and baseline restoration. Setup finishes in Parent without implicit logout. Other allowances, enablement combinations, parents and retained-window bindings need separate qualification. Historical fresh-zero consumer E2E-036 case 161, now UI-owned with no E2E executable, passed in `20260925T065641Z-c6d3948b`; complete 30-minute consumers remain separate. | pending; fresh-zero, fresh-thirty and same-user-positive bindings ready |
| FLOW17 | C | Leave a request with authentication pending by one declared supported action, observe its destination, then return and read cancellation before a new request. | Lock: shared DESK05 shortcut/command → DESK06 → DESK08; switch: DESK03 → FLOW15(return retained); sign-out: DESK04 → FLOW15(fresh); close: UI18(API surface close) → UI11(app), followed by REQUEST01/02 as declared. REQUEST03 → UI11(old prompt). E2E-039; system commands work independently of modal menu access. An unavailable tested app-close control remains gated. | pending |
| FLOW18 | C | Prepare positive daily time that outlasts a soft-app grant without resetting its launch exception. Finish on the child desktop with both balances positive and daily dominant. | FLOW13(combined, soft included) → FLOW15(child) → FLOW08(soft app) → APP04 → DESK03 → FLOW01(parent retained) → PARENT09 → TIME03(wait until the declared remaining-grant window while child is away) → PARENT09 → UI12(D>G>0) → DESK03 → FLOW15(child retained) → TIME01. No allowance edit or app save after approval. E2E-038. | pending |
| FLOW19 | C | Configure a finite named app-rule set for one child and return to sign-in. Each match/access edit and save is explicit; no time approval or account preparation is hidden. | FLOW01(parent, explicit source/entry/window/child) → PARENT04(App Limits) → FLOW03 for each declared app/rule → DESK03. First consumers E2E-006/007; reused as AppSet in the recipes. | pending |
| FLOW20 | C | Approve a specified interval on either request surface and continue as the named child. Accept explicit new/open form entry, child/parent, duration, soft choice, child fresh/retained entry and expected countdown. New overlay entry requires that child's unlocked desktop; new kiosk entry requires GDM. It does not create those preconditions or alter daily policy. | FLOW04(entry and all choices) → FLOW05 → FLOW15(child,declared entry) only for kiosk → TIME01 → UI12(expected interval). Overlay returns to its existing desktop. Reuse FLOW04/05/15 without another surface-specific approval implementation. E2E-048 immediate repeat and E2E-049/050/051. | pending |

FLOW16 also qualifies `gdm/parent/fresh/new/existing/0/30/1` for Jordan through
`fresh_thirty_allowance.JORDAN_PLAN`, `FreshThirtyAllowanceJourney`,
`JordanThirtyAllowanceQualification` and `onpc_fresh_thirty_allowance::run(exchange, 'existing')`.
`onpc_parent::set_allowance` carries the explicit child through FLOW01 selection;
`JourneyPlan.child_bindings` carries it through FLOW02 setup and the independent
PARENT20 reread. `AccessibleUI.time_explanation_operation` and `UiObservations`
validate that same child; Riley receipts are refused. The thirty-minute setup
requires disabled/zero initial settings before edits. Saved enabled/30-minute
settings, separate 1800/0/1800-second balance reads and wrong-child/state/window
refusals passed `check_e2e_set_jordan_thirty_minute_allowance` in
`20261001T044105Z-eb3ffcb2` on every enabled VM. Riley's existing fresh-thirty and
zero/positive bindings passed their unchanged selectors in
`20261001T044336Z-31c717c4` and `20261001T044557Z-2a15ce8d`. All three runs passed
collection, owned cleanup and baseline restoration. This adds only the named
fresh Parent/Jordan FLOW01 and thirty-minute FLOW02/FLOW16 slice; other pending
bindings and complete case 184 remain separate.

#### Approved kiosk flow qualification

Case 50 composes the qualified fresh-zero FLOW16 setup, caller-owned station
entry, `onpc_station::restrictions`, FLOW04(open/default) and FLOW05 automatic
exit in `restricted_station.PLAN` / `onpc_restricted_station::run`.
`AccessibleUI.kiosk_restrictions` anchors a complete public tree at the owned
station window/form, excludes showing content outside its application, and
inspects offered control IDs for request-only actions. The ID-owned menu's
single anonymous direct GTK toggle is its implementation child, never an input
target or a blanket subtree exemption; named unknown controls and other
anonymous controls still refuse. Each Super, Super-A and
Ctrl-Alt-T input has a fresh ID-owned focused Cancel recipient and independent
two-second absence observation followed by REQUEST03. It never types a search
query. Approval replaces the form with success and automatically exits; no
post-approval form restriction pass is applicable. Case 50 passed independently
in `20260926T172007Z-3a5d2feb`: all three shortcut restrictions, exact prepared
choices, real approval, explicit success and automatic usable-GDM return passed,
with private capture reconciliation, collection, owned cleanup and baseline
restoration. About/report actions remain E2E-042/045 obligations.
The added host regressions use private trees, bounded owned Perl doubles and
the existing private durable-recorder fixtures. Unit and cleanup scheduler
classifications remain compatible: no shared cache, bus, display, VM or heavy
fixture construction is added. The real GTK restriction regression in
`tests/ui/test_e2e_accessible_adapter.py` reuses the existing private preview,
bus/display and event log; its UI scheduler classification remains compatible.

`kiosk_approved_flow.PLAN` / `KioskApprovedFlowJourney` and
`onpc_request_flow::run(exchange, 'approved-flow')` passed
`tools/run-tests integration check_e2e_kiosk_approved_flow` in report run
`20260926T162146Z-b021e65a`. An independently opened form qualified the valid
choices and wrong-child/request/authentication refusals, then Cancel returned
to GDM. FLOW06 independently reentered, reproduced the choices and estimate,
submitted one real approval, observed explicit success and automatically
returned to usable GDM. Private capture reconciliation, collection, owned worker
cleanup and baseline restoration passed. This supplies no complete-case credit.

FLOW05's declaration `approved_request` and worker `approve` take explicit
child, approver, duration, soft-app choice and `exit='automatic'` or `immediate`. The qualified
binding is `fixture-child`, `fixture-parent`, 75 seconds (`1.25` minutes), soft
apps included. The caller supplies a prepared form; the existing REQUEST09
leaf freshly verifies its exact choices before input. FLOW06's `obtain_time`
composes FLOW04 `new/selected` and FLOW05 from caller-owned GDM and enabled
policy. It neither changes policy nor logs in the child. One invocation per
fresh attempt uses the existing `kiosk-approval` challenge namespace and unique
`new-*` / `approval-*` stages; repeated approvals remain unqualified. Both
reuse the unchanged MATE binding, provider tuple and single-use secret guards
in [kiosk approval qualification](#kiosk-approval-qualification).

Host checks cover exact worker order, refusal before later input, unsupported
bindings and durable recorder/cleanup failures. Existing compatible unit and
cleanup classifications remain valid: private trees and bounded owned Perl
doubles, with no shared bus, display, VM, cache or heavyweight fixture build.

Complete case 49 (`kiosk_approved.PLAN` /
`onpc_kiosk_cancel::run(exchange, 'approved', invocations, challenges)`) passed
on every enabled VM in `20261001T124720Z-77d15a97`. It independently prepared
900 daily seconds and zero grant through Parent, reproduced the 75-second
soft-included request, observed explicit approval and invoked the owned immediate
exit action before automatic exit. Absent form and usable GDM, fresh intended
child entry, usable child desktop and TIME01 all passed. `KioskRequestJourney`
uses the plan's `countdown_checks` endpoints and finite balance/precision/deadline
to capture the estimate immutably and compare the later immutable countdown
through `countdown.check_countdown_balance`. The recipe owns 975 seconds,
one-second precision, minute flooring, two-second sampling tolerance and a
180-second elapsed bound from the public estimate timestamp.
Private capture reconciliation, collection, worker shutdown, owned cleanup and
baseline restoration passed. All 1612 scoped host checks and eight final
declaration checks passed; no private grant/time probe supplies acceptance.
The affected Cancel case 47 passed in `20261001T125148Z-49cc07cc`, and automatic
FLOW05/06 `check_e2e_kiosk_approved_flow` passed in `20261001T125510Z-18d567bf`,
both on every enabled VM with collection, owned cleanup and baseline restoration.
Coverage was regenerated after each complete case.
FLOW06 retains its automatic-exit-only binding; other choices and overlay remain
separate work.

#### Rejected kiosk flow qualification

`approval_flow.REJECTION_PLAN` / `CANCEL_PLAN`, `ApprovalFlowJourney` and
`onpc_request_flow::run(exchange, 'flow-rejection' | 'flow-cancel')` passed
`tools/run-tests integration check_e2e_approval_flow` in run
`20260926T175707Z-78d5f0fd`. Each branch used a separate restored attempt with
independent open/new entry, wrong-entry refusals and explicit
`fixture-child`, `fixture-parent`, 75 seconds (`1.25` minutes), soft apps included.
The MATE provider tuple remains Ubuntu 26.04, `1.26.1-6`, `en_US.UTF-8`,
keyboard `[["xkb", "us"]]`.

FLOW07's `rejected_request(outcome, child, approver, duration_seconds, allow_soft)`
and worker `reject` accept only that fixed binding and `rejection` or `cancel`.
They observe explicit wrong-password rejection or password-free Cancel, then
independently compare the no-error open form with its saved before-observation.
They end at `flow-preserved`, without retry or exit. Their caller can inspect
the remaining form before separately composing FLOW05.

Cases 51 and 52 compose that open-form boundary in `restricted_station.DENIED_PLAN`
and `CANCELLED_PLAN`, with `request_composition.KioskRequestJourney` and
`onpc_restricted_station::run(exchange, 'denied' | 'cancelled')`.
The caller repeats `onpc_station::restrictions(journey, 'after-')`, then activates
Cancel and independently observes usable GDM. Restriction observations declare
their form state: `kiosk-restriction-ready/read` retains the default disabled
form contract; `kiosk-restriction-prepared-ready/read` passes `prepared=True` to
`AccessibleUI.kiosk_restrictions` and independently validates the fixed FLOW04
child, approver, 75-second custom value, included soft apps and estimate.
Neither route infers expectations from the current selection. Both retain the
complete public-tree exclusions, fresh owned recipient and two-second absence
observation. Case 52 passed in `20260926T185046Z-2140b0d4`; affected cases 50
and 51 passed separately in `20260926T185518Z-026edc31` and
`20260926T185927Z-3a6cff95`. All passed collection, owned cleanup and baseline
restoration. Cancellation enters no approval password and compares the preserved
choices before repeating restrictions and exiting normally.
The host regression exercises both prepared operations through the real decoder,
including changed choices and forbidden surfaces/controls. It uses private
trees and bounded Perl workers; both unapproved worker branches are checked for
order and refusal at every stage. The existing compatible unit scheduling
classification still applies.

The qualification explicitly composes a later FLOW05: a fresh read and a
distinct challenge precede two new recipient proofs, one correct submission,
explicit success and automatic usable-GDM return. `UiObservations` permits
this transition after completed rejection only through the fresh form read;
reused/replaced challenges, failed reads, uncertain input and secret replay
remain refusals. Worker stages use the `kiosk-approval-flow` namespace and
separate single-use rejection/approval secret bindings. Repeated approvals
and other request values remain unqualified.

Both branches passed private capture reconciliation, collection, owned cleanup
and baseline restoration. The affected FLOW05/06 regression
`check_e2e_kiosk_approved_flow` passed separately in
`20260926T180713Z-246238d4` with the same terminal guarantees. These are
capability qualifications, with no complete-scenario credit.
Host coverage retains exact worker order, refusal before later input, preserved
choices, fresh challenges, bounded session-discovery races and terminal errors.
Added tests retain the existing compatible unit/cleanup classifications: private
Python state, recorder fixtures and bounded owned Perl doubles, with no shared
paths, caches, buses, displays or heavy fixture construction.

#### Prepared request qualification

`request_flow.daily_station_entry()` and
`onpc_request_flow::daily_station_entry(journey)` share the preparation used by
this qualification and cases 47–49: from the already selected fixture child in
Parent, enable limits, save/read the 15-minute preset, independently read the
balance, switch to GDM and enter the station. Request selection, authentication
and exit remain separate compositions. This fragment changes no existing
stage names, phase boundaries or balance assertions.

`request_flow.prepared_request(prefix, entry, initial, child, approver,
duration_seconds, allow_soft)` declares the finite FLOW04 kiosk stage mapping;
`onpc_request_flow::prepare` executes the same composition. Arguments are explicit:
`fixture-child`, `fixture-parent`, 75 seconds (exact custom text `1.25`) and
`allow_soft=True`. `entry=open` performs no station entry; `entry=new` uses the
shared station helper. `initial=default` observes the fresh default form before
selection; `initial=selected` observes the remembered child/approver/custom/soft
choices. Prefixes `open` and `new` keep repeated evidence distinct. Callers must
supply enabled Parent policy and an independent public balance; the flow never
changes policy or submits Request.

`request_flow.PLAN` / `RequestFlowJourney` passed
`tools/run-tests integration check_e2e_request_flow` in run
`20260926T050310Z-aef4320a`. Separate public Parent preparation established a
15-minute daily balance. The caller independently opened the default form for
`entry=open`; after Cancel and observed GDM, `entry=new` reproduced all choices
from the remembered form. Both estimates were 16m 15s, checked against the
earlier public balance with `KioskValidDurationJourney.check_settings` and its
elapsed-time/precision bounds. Each branch ended with Cancel and usable GDM.
Wrong-entry refusal, capture reconciliation, collection, owned cleanup and
baseline restoration passed. No complete scenario was registered or qualified.

`AccessibleUI.select_kiosk_account` accepts explicit expected duration/custom
readback for already prepared forms. `kiosk-flow-child-select` and
`kiosk-flow-approver-select` retain exact account-set, ownership and prompt guards;
`kiosk-valid-fraction-soft-select/read` bind the custom/included projection through
`RequestObservation.from_request`. Host regressions cover controller decoding,
remembered-value reselection, independent estimate/choice comparison, worker
order and terminal refusal. Other choices and overlay composition remain pending.

Complete case 47 composes the same open/default binding through
`kiosk_cancel.PLAN` / `onpc_kiosk_cancel::run`, with independent Parent
enablement and a 15-minute daily balance. `KioskRequestJourney` accepts the
consumer plan and recorder actions while retaining its public estimate checks.
`tools/run-tests e2e --id '47'` passed in `20260926T051531Z-576edf40`: one Cancel
from the enabled custom/soft-included form, independently absent form and usable
GDM, capture reconciliation, collection, owned cleanup and baseline restoration.
This qualifies REQUEST12's enabled-choice Cancel consumer.

Complete case 48 composes that same prepared binding through
`kiosk_escape.PLAN` / `onpc_kiosk_escape::run`, using
`onpc_request_exit::escape` for an owned request-surface API close and
independent GDM return. The historical native-Escape implementation passed
`tools/run-tests e2e --id '48'` in
`20260926T052659Z-8144eb94`: independent Parent balance and estimate comparison,
absent form and usable GDM, capture reconciliation, collection, owned cleanup
and baseline restoration. The affected shared disabled-child Cancel/Escape
qualification `check_e2e_request_exit` passed in `20260926T053454Z-d3ce9eca`,
including both public returns, collection, owned cleanup and baseline restoration.
Host checks cover worker order, one API close and terminal refusal before input
or after a failed result. Approved exits and overlay cases remain pending.

### Canonical reuse and implementation checkpoints

The former duplicate wrappers are retired identifiers, not pending work:

| Former ID | Canonical block | Binding |
| --- | --- | --- |
| SEARCH02 | UI21 | Overview search field |
| PARENT07 | UI17 | Parent's Screen time limit switch |
| PARENT14 | UI16 | Open match-rule draft field; do not Save |
| FEED02 | UI16 | Synthetic feedback body or reply field |
| REQUEST07 | UI17 (future binding only) | Retired interactive mute wrapper; no current customer dependency |

The split operations intentionally have separate checkpoints: UI23 reveals
logically collapsed content and UI09 observes reachability; PARENT09
expands/navigates and PARENT20 only reads
an already showing explanation; GDM08 observes a prompt, GDM03 qualifies a secret
recipient and GDM09 dismisses; HAR05/06/07/08 separate serial login, command,
logout and return; FILE02 submits
and FILE06 observes; FEED07 reads an attachment, FEED12 previews and FEED13
removes; FEED11 submits and FEED09 observes before FEED14 dismisses success.
FILE08 reads a declared customer artifact, FILE09 changes its declared synthetic
source, and FEED08 composes download, chooser and independent archive inspection.
An explicitly retained-work binding instead needs an already-open document's
observable edit/save and activity comparison; source mutation does not qualify it. An atomic
block never hides any of those extra inputs. Existing multi-action rows remain
explicit composites; do not relabel an entire sign-in or approval as atomic.
Recipes own the order. This prevents a completion wait from blocking required
authentication, and prevents reopening, editing or a second Send from hiding
the state a scenario is supposed to inspect. FLOW07 now ends after rejection;
FLOW05 owns the later approval. REQUEST06 owns only the current soft-app control; future mute reuses UI17 after its separate feature gate.

FLOW01's pending retained-window and other-parent bindings must reach Screen
Limits with PARENT04 before their PARENT03 settings capture if the remembered
window is on App Limits. Its established fresh/new binding still uses the
initial Screen Limits page. A selected child is not proof that the controls
being read are showing. Qualify the second administrator's own desktop/window
with E2E-051; selecting that administrator in an approval prompt does not qualify
management entry under that account.

Every invocation binds `surface/account`, registered `target`, input values,
expected output, deadline and immutable prior observations. It returns a fresh
semantic result plus its declared destination. A composite may perform pure
argument selection/comparison and finite control flow; all UI/secret/fixture
I/O must come from its listed callees. Row order, rather than ID number, is the
implementation order; added IDs keep old references stable.

Use the [UI result contract](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope)
for current consumers: perform the declared operation once, then independently
read its final value or functional effect. Rapid edits must prove the last
accepted value wins, including per-child and reopened readback; do not require
Saving, temporary inhibition or recovery presentation. A trace remains useful
only when a distinct functional result would otherwise be lost, such as automatic
approval followed by closure. Start its observer before the action and retain
the existing readiness, recipient, token and deadline guards.

For Parent saves, `UiObservations.observe_accessibility_input` obtains a frozen
public owner/source and retains its ready token before releasing one existing
input batch. Custom input waits for the owned worker's bounded, token-checked
completion receipt. `AccessibleUI.parent_saved_result` then independently reads
the final enabled state or custom value and verifies the same public owner.
Child reselection and restart separately prove persistence. The legacy
`parent-save-events` / `parent-custom-events` operation names now prepare input;
they do not subscribe to sensitivity events. No input route is added.

Task 016c's checked-state event-delivery qualification and feedback trace
diagnostics retain their separate event subscriptions. Task 017a historically
qualified PARENT08 inhibition/recovery samples; those incidental samples are no
longer required. This simplification does not claim a new installed pass.

A row becomes `ready` only when its implemented projection/selector scope is
explicit and its source callable and required installed slice qualification are
recorded under the [status contract](README.md#status-vocabulary). A later
complete scenario is not a prerequisite of its own block. Ready primitives above
refer to existing
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

The [snapshot and case-entry contract](#parent-login-and-time-scenarios) owns
suite preparation, online/offline restoration and final audit. The rows below
own finite fixture operations within that envelope; a fixture result supplies
no customer acceptance.

These supporting operations are the only fixture exceptions to customer input.
They prepare unrelated accounts/assets, never the policy, time balance,
authentication outcome or app behavior being tested.

| ID | Kind | Supporting operation and boundary | Existing source | Status |
| --- | --- | --- | --- | --- |
| FIX04 | A | Transfer the existing verified asset manifest to the powered-off guarded guest before the attempt; stage finite synthetic files through guarded SSH. No asset installation or arbitrary bundle interface. | `AssetTransfer.provision` / `observe` in [asset_transfer.py](../../tests/e2e/asset_transfer.py); [transfer safety](../../tests/unit/test_e2e_asset_transfer_cleanup_safety.py), case 1 qualification. `SyntheticFiles.call('stage')` supplies the [synthetic text files](#synthetic-file-commands); its six finite `profile` values supply the qualified [attachment boundaries](#attachment-rejection-boundaries), with exact receipt/readback and cleanup. Reusable fixture readiness belongs to FIX06, not transfer or installation during an attempt. `stage_upgrade_assets` and `VerifiedInputs(upgrade=True)` supply the [qualified genuine v1.2/current dual-package binding](#verified-upgrade-asset-transfer). | existing transfer, synthetic-text, six attachment-boundary profiles and Ubuntu amd64 dual-package upgrade transfer ready |
| FIX06 | A | Independently verify one declared reusable fixture profile after baseline restore. Read-only files, launchers and ownership checks; no installation, repair, app launch or product-state setup. | Native: `NativeFixtures.verify` / `fixture_actions` in [native_fixtures.py](../../tests/e2e/native_fixtures.py), with guarded reads in [native_fixtures_guest.py](../../tests/e2e/native_fixtures_guest.py); see [native preparation](#native-fixture-preparation). Native Jordan-bound verification/catalogue qualified by `check_e2e_native_fixtures` in `20261001T024817Z-a8a37e09`, with affected regression in `20261003T210811Z-d41b9452`. Chinese: `fixture_actions(profile='chinese')` and `chinese_language_assets.verify`; [language preparation](#chinese-language-preparation-and-desktop-language-setup). `check_e2e_chinese_language_assets` qualified wrong-entry refusal, independent valid readback and unchanged state on Ubuntu 26.04 in `20261003T210556Z-9dc87030`. Tasks 035d/035a/035b, 109p, 116p and 126p extend their finite baseline profiles and verification before consumers; they do not broaden FIX04. FIX05 retains the separate real Lunar profile. | native file/catalogue and Chinese asset verification ready; other profiles planned |
| FIX03 | A | Prepare one declared account-eligibility profile before a kiosk journey: multiple, no child, no approver or ineligible approver. Do not generalize FIX02 into arbitrary account mutation. | `EmptyAccountFixture.prepare` / `e2e_dynamic_account.prepare_empty` changes only the two canonical children's account type, preserving identities, existing administrators and the station; outer lease cleanup restores the profile. `kiosk_no_child.PLAN` / `onpc_kiosk_no_child::run` qualified this profile through `check_e2e_kiosk_no_child` in run `20260924T064646Z-19f2aad6`, with shared station navigation requalified in run `20260924T173643Z-8d742069`. `AccessibleUI.kiosk_request_form(no_child=True)` and `RequestObservation.from_request` independently require the exact empty child set and no-child explanation, disabled Request/duration/soft-app/approver controls and no authentication prompt. Valid station entry, wrong-entry refusal, repeated public readback, sanitized collection, owned cleanup and baseline restoration passed without product-policy mutation. Complete case 54 separately passed via `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run` and `tools/run-tests e2e --id '54'`, adding public Cancel/GDM return; wrong-entry refusal remains qualification-only. The no-approver callables and independent case 55 acceptance below supply the second ready profile. `kiosk_multiple.PLAN` / `onpc_kiosk_multiple::run` supply the qualified multiple profile below. `kiosk_multiple.INELIGIBLE_PLAN` / `KioskIneligibleJourney` supplies the locked-administrator exclusion profile qualified below. | ready; multiple/no-child/no-approver/locked-approver profiles |
| FIX01 | A | Create one eligible account at the declared durable checkpoint while Parent stays open. Customer acceptance requires later visible discovery/selection. | `DynamicAccountFixture.create` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX02 | A | Make the exact two canonical eligible child fixtures ineligible at the declared checkpoint before Parent launches; preserve the request station. Unexpected account sets refuse. | `EmptyAccountFixture.prepare` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX05 | A | Validate the one declared, manually prepared Lunar/AppImageLauncher/Minecraft profile after the normal installed-snapshot restore and before the attempt. Read-only setup verification, not installation, policy configuration or customer acceptance. | No callable yet. Task 295 binds versions/digests, original AppImage and launcher/autostart routes, local world, credential references and ordinary restore/provisioning ownership. Refuse missing/drifted assets; never synthesize a denial. [Profile contract](#lunar-client-preparation-and-observation-gate). | pending |

### Verified upgrade asset transfer

`check_e2e_upgrade_assets` qualified FIX04's genuine v1.2/current package binding
on every enabled VM (Ubuntu 26.04, amd64) in `20261003T234321Z-f5394d82`.
`stage_upgrade_assets` in [system_runner.py](../../tests/integration/system_runner.py)
and `VerifiedInputs(upgrade=True)` in [provenance.py](../../tests/e2e/provenance.py)
bind separate source/manifests and exact bytes before the powered-off transfer.
The maintained builder pins the signed v1.2 tag and source commit; current must
be newer, with a distinct package digest and matching product/architecture.
The qualified inputs were `1.2+ppa1~ubuntu26.04.1` and
`1.3+ppa1~ubuntu26.04.1`. Missing inputs use maintained automatic preparation;
valid inputs are preserved, never fabricated by rewriting version metadata.

`AssetTransfer.provision` / `observe` and the finite
[qualification](../../tests/e2e/upgrade_assets_qualification.py) passed independent
repeated booted-guest identity/digest readback, product-free administrator entry,
wrong-attempt/powered-on/collision/replay refusals and preservation of accounts,
locales, desktop session and unrelated files. The offline witness preserves
Ubuntu's exact `/etc/default/locale` → `../locale.conf` link identity and separately
hashes its canonical regular file; other links, dangling or unsafe targets still
refuse. Asset link/owner/immutability and consumed-failure guards remain required.
[Upgrade safety](../../tests/unit/test_upgrade_assets_cleanup_safety.py) covers
these boundaries through the real transfer, decoder and recorder.

The affected one-package `check_e2e_product_free_entry` regression passed in
`20261003T234636Z-cd0eba55`. Both runs passed private collection, worker shutdown,
callback closure, owned cleanup, baseline restoration, finalization and
host/source preservation. GDM `50.1-0ubuntu0.1`, Shell `50.1-0ubuntu1.3`,
`en_US.UTF-8` and `xkb/us` were observed. No package installation, upgrade,
reboot-required result, Chinese authentication or complete-case credit is supplied.

### Chinese language preparation and desktop-language setup

Task 300's [Chinese kiosk history](E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle)
requires one declared Simplified Chinese profile. **Chinese language installation
must be implemented in `tools/prepare-baseline`**, through its existing finite
dependency/fixture declaration and supported distro package/locale preparation.
Install and verify `zh_CN.UTF-8`, the distribution's Chinese translations for
the ordinary MATE PolicyKit agent and authentication stack, and CJK fonts. Record
the exact installed package/provider tuple and verify the required translated
native strings are available. Reconciliation is idempotent, preserves unrelated
assets and supports retry of owned partial work under the
[baseline lifetime contract](../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
The Ubuntu profile is implemented in
[chinese_language_assets.py](../../tests/integration/chinese_language_assets.py)
and the existing dependency/baseline routes. Distribution-managed `locales-all`
supplies `zh_CN.UTF-8`; MATE PolicyKit and Linux-PAM catalogues are read independently,
with required Chinese strings, package-byte identity and Noto CJK glyph coverage.
The profile also requires Ubuntu's `language-pack-gnome-zh-hans-base` and
`language-pack-gnome-zh-hans`, independently verifying the packaged Shell
`Activities` translation before any renewed Chinese desktop observation.
The general Chinese language packs alone do not supply GNOME translations.
Baseline source identity includes this module. Offline bootstrap and restored
online app snapshots use the same read-only oracle. The in-progress Fedora
Workstation 44 RPM profile spans the same preparation, bootstrap,
snapshot-readiness and FIX06 routes. Its finite package owners are
`glibc-langpack-zh`, `mate-polkit`, `pam`, `gnome-shell` and
`google-noto-sans-cjk-fonts`; RPM SHA-256 manifests bind locale/catalogue/font
bytes. The canonical release/Workstation identity, targeted enforcing SELinux,
runtime UTF-8 locale, required Chinese translations and static Noto CJK glyphs
must all pass. Fedora assets, renewed desktop/first presentation and native
prompt bindings remain unqualified. Task 300's historical acceptance scope was
Ubuntu-only. On 2026-10-08 the developer authorized the same E2E-053/latest-install
journey on Fedora Workstation 44 with all current assertions preserved and no
change to the Ubuntu path. Retained Fedora preparation work supplies no installed
acceptance; the complete journey must pass on Fedora before claiming it qualified.
Asset preparation and scope decisions supply no complete-case acceptance.
Task 300a passed host checks and auto baseline/app-snapshot preparation. Chinese
FIX06 qualified wrong-entry refusal, two independent valid reads and unchanged
account/locale/product state on every enabled VM (Ubuntu 26.04) in
the historical Chinese qualification `20261003T210556Z-9dc87030` (its host report
has since rotated out of retention).
The qualification recorded the installed package/provider tuple; MATE
PolicyKit `1.26.1-6`, Linux-PAM `1.7.0-5ubuntu3.2`, six required Chinese strings
and 12 CJK glyphs passed. The affected native fixture/catalogue regression passed
in the historical native qualification `20261003T210811Z-d41b9452` (its host
report has since rotated out of retention).
Collection, worker shutdown, owned cleanup, baseline restoration, finalization
and preservation passed for both runs. This qualifies assets, not the language
of a running authentication dialog or any desktop-language switch.

The read-only preservation proof pins Ubuntu's canonical `/usr/lib/os-release`
and `/etc/locale.conf`. It records `/etc/default/locale`'s compatibility-link
identity without opening that link as a regular file, refuses an unexpected or
dangling destination and retains the shared asset reader's no-link guards.
On installed entries, `native_fixtures_guest.product_tree` compares bounded,
descriptor-pinned directory and regular-file witnesses for the product state;
links, special files, replacement and content changes refuse. These private
preservation witnesses never supply a customer result. Installed consumers use
their existing public entry observation before FIX06, without borrowing FIX04's
package-command context or requiring a product-free transfer payload.

Attempts and app-snapshot preparation verify the declared language assets;
they never install packages, generate locales or download translations.
Missing Chinese assets block the case with a preparation diagnostic. Reusable
language installation is not a case stage; the latest product installation remains a
deliberate LIFE04 mutation inside the case. Do not install the product or change
the child/station language as a side effect of installing language assets.

Task 300's current recipe uses one verified current-package installation and one
subsequent reboot. Tasks 300c/300d and the upgrade-based 300e/300f journey envelopes
below remain historical qualifications; reuse their scoped Chinese observations
and approval bindings without importing the old-release installation or upgrade.
Task 300k qualified the fresh-install composition through
`check_e2e_chinese_current_install` on Ubuntu 26.04 in
`20261004T185057Z-2010e28f`. `chinese_current_install.PLAN` /
`ChineseCurrentInstallJourney` compose one current-package installation and one
reboot, reusing `ChinesePresentationMixin` and the worker's
`chinese_desktop_renewal`, `chinese_initial_notice` and `chinese_initial_form`
leaves. All 11 assertions passed: product-free entry/refusals, Chinese assets and
renewed desktop, installation completion/version/notice with independent
unchanged-boot reread, the first Chinese restart notice, changed boot and fresh
greeter, then untouched Jordan Chinese chooser/default and form after Cancel
without saving. No Parent policy setup was needed for these initial observations.

Required customer-reboot and historical Chinese kiosk lifecycle regressions
passed in `20261004T185756Z-2e816150` and `20261004T190226Z-07180c48`.
All three runs passed collection, worker shutdown, callback closure, owned
cleanup, baseline restoration, finalization and host/source preservation.
Reports remain under `output/test-runs/host/reports/<run>/report.md`.
Scoped host safety/composition checks and source validation passed. The isolated
guest payload includes `session_control`; its real isolated-import regression
and synthetic transport fixtures protect that dependency boundary. This qualifies
first presentation only; task 300's complete single-reboot history with two
genuine Chinese approvals has its separate acceptance below.

Pre-install renewal binds `fresh_desktop(..., product_free=True)` through
`renewed_desktop` for Jordan and Jamie. The product-free standard list/focus
operations reuse the owned GDM semantic adapter, requiring both declared rows
and absence of the station before focus. Installed standard entry still requires
the station. Both bindings retain the same role-specific, ordered fresh password
recipient proofs; changing package lifetime never relaxes authentication guards.
The current-install qualification supplies live coverage of both product-free bindings.

The **user desktop-language switch is DESK13**, a shared building block, not
case-local shell code or a locale-file edit. Its fixed consumer binds Jordan
and `zh_CN.UTF-8`; it independently confirms the system account language while
preserving Jamie and the station's English settings. Qualify exact account
ownership, installed-locale validation, supported API errors, wrong-account
refusal, readback and owned cleanup. A DESK13 setting readback establishes only
setup: explicit session renewal and the child's publicly observed Chinese
desktop precede the product assertions. Product personal-language preferences
are changed only through the public Preferences controls.
`compare_desktop_entry` in the shared account helper permits only the disappearance
of GNOME's temporary `gdm-greeter` account bound to the departed observed greeter
session. Setting/readback preservation compares every account and graphical
session exactly against fresh desktop witnesses; persistent-account removal,
addition or language changes remain refusals.
The confirmed setting is the actual `Language` API value, alongside the
submitted `requested_locale`. For this single binding, independent reads must
agree on exactly `zh_CN.UTF-8` or `zh_CN`; Ubuntu's
[AccountsService language validator](https://git.launchpad.net/ubuntu/+source/accountsservice/tree/debian/patches/0009-language-tools.patch?h=ubuntu/resolute)
removes the encoding suffix. No other region, fallback list or variant is
accepted. This representation handling does not normalize preservation witnesses
for other accounts or establish the language of a renewed desktop.
After explicit child logout/login, `language_upgrade_entry` independently
requires the same finite Chinese locale representations at both the setting
and renewed-entry boundaries. It retains the actual renewed API value for
upgrade preservation; every other account field and preservation witness remains
exact. GNOME login can restore the encoding suffix removed by `SetLanguage`.
Task 300b's bounded `check_e2e_desktop_language` setting/readback slice passed
on every enabled VM (Ubuntu 26.04) in
desktop-language qualification run `20261003T215747Z-6bd9c168`
(its bounded report retention has expired).
It verified Chinese FIX06, greeter/account/locale refusal, one declared setter,
two independent reads confirming `zh_CN`, explicit renewal requirement and
unchanged other-account, observer, system-locale, graphical-session and
product-free witnesses. Collection, worker shutdown, owned cleanup, baseline
restoration, finalization and host/source preservation passed. The shared helper
also retains reproduced regressions for the departed greeter and normalized
API value, with undeclared-language and preservation refusals.
This setting/readback slice supplies no renewed Chinese desktop or
product-language result.

Reusable fixture settings suppress the optional GTK folder-renaming prompt
across deliberate desktop-language changes through per-user XDG autostart and
systemd overrides. The [baseline fixture owner](../../tests/integration/Environment.md#reusable-preparation-ownership)
reconciles and independently verifies them, preserving existing folder mappings
and contents. This is supporting preparation; it changes no account language,
product state or actual Chinese Shell assertion. Unexpected prompts still refuse.

Chinese approval also needs a scoped extension of the
[MATE provider binding](#external-provider-qualification). Reuse its ownership,
selected-parent/context and secret-recipient guards; qualify the actual Chinese
button labels and system-owned explanatory/password text on the installed
provider, including after kiosk agent restart and fresh kiosk entry. English
provider evidence and translated product messages do not qualify these native
results. Keep the agent unmodified and use supported locale/session APIs.
The fixed Jamie-from-station binding uses MATE's single-other-user explanation,
not its same-user explanation: the upstream
[dialog branch](https://github.com/mate-desktop/mate-polkit/blob/v1.26.1/src/polkitmateauthenticationdialog.c#L653-L675)
selects the super-user message when the sole authentication identity differs
from the agent's user. `chinese_mate_texts(provider_version)` pins the exact
Chinese catalogue for the installed MATE version: Ubuntu's 1.26.1 retains its
original wording and mnemonic Cancel label; Fedora's 1.28.1 uses its upstream
wording and Cancel label without a mnemonic. Unknown versions refuse. The host
decoder independently checks the version-bound oracle; public-tree fixtures
specify both catalogues independently and reject crossed catalogues, same-user
and multiple-user branches. Native text still must pass on each actual prompt
before credentials are released. This reader extension supplies no Fedora
installed acceptance; the complete journey remains subject to verification.
The task 300e first-presentation/reboot slice
is implemented in [chinese_kiosk_lifecycle.py](../../tests/e2e/chinese_kiosk_lifecycle.py)
and `check_e2e_chinese_kiosk_lifecycle`, with qualification recorded below. It composes
genuine installation/activation, installed-product DESK13, explicit Chinese child
desktop renewal, one real current upgrade, Chinese initial notice and a second
declared customer reboot before independently observed Chinese chooser/default
and usable form. Initial public operations do not save a personal preference or
submit approval. The task 300f native authentication slice,
[chinese_native_auth.PLAN](../../tests/e2e/chinese_native_auth.py) /
`check_e2e_chinese_native_auth`,
passed all 14 assertions in `20261004T073743Z-9a030ef1` on Ubuntu 26.04:
both native Chinese prompts and real approvals, fresh agent/challenge identities,
persisted form language, normal GDM returns, collection and owned cleanup.
The actual tuple was MATE `1.26.1-6`, `zh_CN.utf8`, `xkb/us` on both prompts.
The required English approved-flow regression passed in `20261004T075449Z-01e10e04`;
both runs passed collection, verified worker shutdown, callback closure, baseline
restoration, finalization and host/source preservation. The English wrong-entry
guard now uses the shared bounded read wait for incomplete or stale observations;
only a complete owned refusal passes, with no input. The repair passed 1,933 host
checks in `20261004T075211Z-82086cc0`. Task 300f is complete.
Reuse `request_flow.chinese_request` / `onpc_request_flow::prepare_chinese` and
`kiosk_approved_flow.chinese_approval` / `onpc_request_flow::approve_chinese` for
the finite request and native challenge; callers own fresh entry and GDM return.
Case 254's `chinese_lifecycle.PLAN` / `onpc_chinese_lifecycle::run` passed its
complete single-reboot history and all 25 assertions on Ubuntu 26.04 in
`20261005T052511Z-d5a980d9`. `ChineseRequestInstallJourney` composes the shared
installation/presentation and approval comparisons; recipe-declared public checks
retain checked Chinese preferences, request estimates and independent Parent
time/policy results after both real approvals. The post-setup approver input uses
`kiosk-language-jordan-jamie-chinese`, binding the already Chinese form through
startup Save and selected-account readback. The English-only selector is not a
valid substitute for that input. Native provider scope remains the qualified
Jamie/Jordan, 75-second, soft-included MATE binding.

Required `check_e2e_chinese_current_install` and `check_e2e_chinese_native_auth`
regressions passed in `20261005T053736Z-2bf99fd4` and
`20261005T054603Z-b58a3339`. All three reports remain under
`output/test-runs/host/reports/<run>/report.md`; collection, worker shutdown,
owned cleanup, baseline restoration, finalization and preservation passed.
The mechanical language-binding repair passed 2,752 selected host tests and
source validation; coverage was regenerated. This completes task 300 only;
tasks 306–310 retain the other language histories and Fedora remains unqualified.

The Chinese first-presentation slice passed on every enabled VM (Ubuntu 26.04)
in `20261004T044302Z-572b0ee7`, including all 14 declared assertions, genuine
package history, Chinese Shell renewal, both changed boots, initial notice and
chooser/default/form, immutable comparisons and refusal gates. Collection,
verified worker shutdown, callback closure, baseline restoration, finalization
and host/source preservation passed. Shell was `50.1-0ubuntu1.3`,
`zh_CN.UTF-8`, `xkb/us`. The required package-upgrade regression passed in
`20261004T024908Z-8d5137eb`, with its retained report at
`output/test-runs/host/exports/onpc-artifact-export-v2s6wi_5/report.md`.
The required kiosk-entry regression passed in `20261004T043928Z-7e4cf5c1`.
Its launcher and qualifier use `named_input(package_source=True)` so the
verified package selects the current prepared snapshot, preserving legacy
bundles rather than silently restoring their older release. Both regressions
passed collection, worker shutdown, callback closure, baseline restoration,
finalization and preservation. Task 300e is complete; no native authentication
or complete-scenario result is supplied.

### Native fixture preparation

FIX06's finite native declaration is [native_assets.py](../../tests/fixtures/native_assets.py).
A/H/S/N are later policy roles; preparation leaves every launcher Allowed.
The shared [builder](../../tests/fixtures/build_test_applications.py) compiles
distinct retained role identities while preserving the GUI's native kind.
The four executables share adjacent `onpc-test-gui.py` and `gtk_automation.py`.

| Role | Desktop ID suffix (`com.puffyslippers.ONPCTest.`) | Executable below `/opt/onpc-test-fixtures/Applications` | Visible name | Description | Default match |
| --- | --- | --- | --- | --- | --- |
| A | `A.desktop` | `Exact Fixture.AppImage` | ONPC Allowed Fixture | Exact native catalogue fixture | precise |
| H | `H.desktop` | `Path With Spaces.AppImage` | ONPC Hard Fixture | Whitespace native catalogue fixture | precise |
| S | `S.desktop` | `Lunar Client-3.7.17.AppImage` | ONPC Soft Fixture | Versioned native catalogue fixture | pattern (`Lunar Client-*.AppImage`) |
| N | `N.desktop` | `PrismLauncher.AppImage` | ONPC Nonmatching Fixture | Unrelated native catalogue fixture | precise |

`tools/prepare-baseline` installs this finite declaration through
[baseline_fixtures.py](../../tests/integration/baseline_fixtures.py), with the
static engineering fixtures declared in
[baseline_assets.py](../../tests/fixtures/baseline_assets.py). Reconciliation
reuses matching files, updates only recorded owned files, preserves unrelated
entries and supports interrupted retry. New directories/binaries are `0755`,
GUI/desktop files `0644`, owned by Jordan (`accounts['other']` in baseline
preparation; `session_control.ACCOUNTS['standard']` in guarded readback). Baseline
inspection verifies bytes, modes, owners and launchers before snapshot capture;
fixture sources participate in its preparation digest.

[NativeFixtures](../../tests/e2e/native_fixtures.py) uses guarded administrator
SSH after independent graphical entry solely for readback. `fixture_actions()`
supplies wrong-entry refusal and `native-verify`; `verify()` independently reads
the ten declared files twice against the source-keyed artifact digests.
[The fixed guest helper](../../tests/e2e/native_fixtures_guest.py) uses
[descriptor-pinned reads](../../tests/e2e/guest_files.py), resolves the child's
home through `pwd`, and refuses missing files, links, hardlinks, unsafe parents,
corruption, ownership/mode changes and replacement. It never copies or repairs
files. Missing/stale fixtures require a separate baseline refresh. No product
policy, grant or fixture launch is part of preparation/readiness verification.

`native_fixture_qualification.PLAN` / `NativeFixtureJourney` and
`onpc_app_rows::native_fixtures` compose fresh guarded entry, baseline verification,
PARENT12/UI13 public Allowed/default-match observations for all four identities,
wrong-child/page refusals and independent reopening. `check_catalogue()` is a
shared caller-owned comparison; stock rows are retained in the full reread.
Select Jordan with the existing-child picker/settings operations and open
`existing-apps`; `existing-parent-app-rows` and its reopened/refusal bindings
read Jordan and reject Riley as the wrong child. The unprefixed operations keep
their Riley binding for existing consumers.
The argument-free selector is `tools/run-tests integration check_e2e_native_fixtures`;
run `20261001T024817Z-a8a37e09` passed on every enabled VM with four declared
Allowed/default-match identities, identical 61-row reopening, independent
ten-file readback, refusals, collection, owned cleanup and baseline restoration.
Launch/usability and complete scenarios
remain separate tasks. Host readback/refusal checks live in
`test_native_fixtures_cleanup_safety.py`; idempotent placement/retry checks live
in `test_baseline_fixtures_cleanup_safety.py`; recorder and worker distribution checks
use the existing shared safety inventories. Source-keyed `named_input(fixture_source=True)`
prepares absent inputs through the maintained artifact builder and preserves
existing frozen inputs.

`native_grid_usable.PLAN` / `NativeGridJourney` and
`onpc_app_rows::native_grid_usable` qualify APP01/02/03 for Jordan's
`ONPC Allowed Fixture` search result and `onpc-fixture-native-primary` window.
The shared `native_search` uses `onpc_parent::search_whole_query` with that finite
query; `native_launch_grid` consumes a fresh grid observation before one Enter.
`native_use_app` submits the initial `ONPC fixture draft` through the public
Submit draft ID, then independently reads that exact submitted label with
unchanged draft and `Moves: 0; token: 0`. `native_close_app` closes normally and
independently requires complete owned window absence with the recognized desktop.
Two separately supplied valid entries and wrong-entry, wrong-instance and
uncertain-input refusals passed `check_e2e_native_grid_usable` in
`20261001T162654Z-8a3c8079` on every enabled VM. The affected Parent search-launch
regression passed in `20261001T163039Z-3076ff7a`; both runs passed collection,
owned cleanup and baseline restoration. The observed Shell provider tuple was
`50.1-0ubuntu1.2`, `en_US.UTF-8`, keyboard `[["xkb", "us"]]`.
Host checks in `test_e2e_native_grid_usable.py` reconcile actual worker marker
titles and fresh ordered public observations; the shared ownership/recorder and
native GTK preview checks preserve input/refusal and exact activity assertions.
`native_app.PLAN` / `NativeAppJourney` and `onpc_app_rows::native_app`
qualified the same APP01/02/03 usable scope through the fixed command route in
`check_e2e_native_app`, report `20261001T170046Z-2e777027`, on every enabled VM.
FIX06's ten-file readback precedes child entry. The worker uses the shared
`onpc_gdm::sign_in_challenge` with distinct declared Parent and Jordan challenges;
the unchanged password helper consumes two fresh same-challenge proofs once for
each login. `native_open_command` consumes a fresh desktop proof and delegates
one fixed executable submission to `AccessibleUI.native_launch_command` in the
active child session over guarded SSH. APP02 independently reads the actual
owned primary window; command success alone supplies no window result.
Two independent launches reused `native_use_app` / `native_close_app` and passed
the exact draft/effect and complete closure observations above, with
wrong-entry/instance/uncertain-input refusals, collection, owned cleanup and
baseline restoration. Host regressions in `test_e2e_native_app.py` exercise the
real password/worker sequence, reject failed or mismatched child proofs before
secret input, and reconcile actual markers and challenge evidence. Shared
recorder/composition and challenge-safety regressions passed. The existing grid
qualification and its provider tuple remain unchanged.
Hidden/denied results, other fixture actions and complete scenarios remain
pending under their own task bindings.

`native_activity.PLAN` / `NativeActivityJourney` and
`onpc_app_rows::app_activity` qualified APP04 and FLOW08's native usable slice in
`check_e2e_app_activity`, run `20261001T175200Z-a1d92898`, on every enabled VM.
The shared `native_usable_app` declaration/composition uses the command and grid
launch/result/usability leaves above. Each independently supplied desktop entry
launches once, submits the normal draft and reads its exact public effect before
APP04 captures and independently rereads that activity. Wrong-entry reads refuse
without input. The later grid window has identical text but a different public
AT-SPI endpoint/PID, so its replacement check cannot prove the command window
survived. Both windows close normally through `native_finish_app`.

`AppActivityObservation.from_value` in
[`ui_observations.py`](../../tests/e2e/ui_observations.py) copies the nested
endpoint and state into frozen tuples. `JourneyPlan.activity_checks` declares
each comparison's earlier capture and `same` result; `replaced` is a negative
qualification binding requiring different window identity with identical text.
`InstalledJourney.check_activity` compares before the durable worker reply and
refuses missing/replayed capture or changed state/window. Renamed invocation IDs
retain the same checks. Host regressions in `test_e2e_app_activity.py` cover the
actual worker order, every refusal boundary, controller decoding, immutable
captures and real recorder startup/replies. The native GTK preview independently
read the same public identity twice. The affected `check_e2e_native_app` regression
passed in `20261001T175724Z-8d97badf`; both live runs passed collection, worker
shutdown, owned cleanup, baseline restoration and host/source preservation.
The grid provider tuple remains `50.1-0ubuntu1.2`, `en_US.UTF-8`, keyboard
`[["xkb", "us"]]`. Policy denial, cross-user retention and complete scenarios
retain their separate task bindings.

FIX03's multiple profile reuses the guarded installed snapshot's two canonical
children and two approvers; it changes no account identities, roles or station
ownership. `kiosk_multiple.PLAN` / `KioskMultipleJourney`,
`KioskMultipleQualification` and `onpc_kiosk_multiple::run` publicly enable and
read back each child's Screen Limits before switching to the station.
`AccessibleUI.select_kiosk_account` checks the exact offered set on every
selection. The finite `multiple-*` entries in `KIOSK_ACCOUNT_REQUESTS` and
`MULTIPLE_MATE_BINDINGS` register both children and both approvers. The current
journey uses Riley/Jamie and Jordan/Casey as representative pairs rather than
their Cartesian product. Each pair uses 1800 seconds with soft apps excluded, a freshly
owned real MATE prompt with exact child/request/recipient context, one normal
Cancel, complete prompt absence and independent unchanged-form/no-error readback.
`mate_prompt(binding=...)` retains owner, ambiguity, focused empty masked field,
same-challenge and uncertain-input guards; this extension submits no password.

`tools/run-tests integration check_e2e_kiosk_multiple` passed in report run
`20260926T191541Z-dc28d61d`, including independent valid entry and wrong-entry
refusal. The earlier 75-second/soft-included prompt binding and its refusal
matrix passed `check_e2e_auth_prompt` in `20260926T192244Z-e74f7983`.
Both attempts passed sanitized collection, owned cleanup and baseline restoration.
The qualified provider tuple remains Ubuntu 26.04, MATE Polkit `1.26.1-6`,
`en_US.UTF-8`, keyboard `[["xkb", "us"]]`. Case 53 and the ineligible-approver
profile remain separate from that qualification; these runs give no complete-case credit.
Complete case 53 is registered through `kiosk_multiple.CASE_PLAN` and
`onpc_kiosk_multiple::run`'s complete-case branch. It omits qualification-only
wrong-entry checks and verifies final selected accounts, their matching approval
prompts and preserved-form readback. Exact offered sets remain part of the shared
selection operation. Separate list open/collapse assertions have been removed.
Case 53 passed in run `20260926T193803Z-abb86806`; the unchanged disabled-child
collapse binding passed case 57 in `20260926T194240Z-ff1d1166`. Both include
reconciliation, collection, owned cleanup and baseline restoration.
The ineligible-approver profile is `kiosk_multiple.INELIGIBLE_PLAN` /
`KioskIneligibleJourney`, selected by `KioskIneligibleQualification` and
`check_e2e_eligible_kiosk_fixtures`. Its setup action uses
`station_fixture_actions(context, 'ineligible-approver')` /
`IneligibleApproverFixture` / `e2e_dynamic_account.prepare_ineligible_approver`.
It creates only the fixed `onpc-e2e-locked-parent` administrator through
AccountsService, requires it locked without credentials, refuses collisions,
and checks preservation of existing identities, both children, eligible parents
and station. Outer snapshot restoration owns removal. This qualification covers
locked administrators; other ineligibility causes need their own declared scope.
The exact-set selectors exclude the new account; both representative
child/approver pairs reach correctly bound real prompts and cancel normally.
The slice passed in report run `20260926T195528Z-eb3740b5`, including independent
entry, wrong-entry refusal, both public child enable/save results, exclusion,
unchanged forms, Cancel/GDM return, collection, owned cleanup and baseline
restoration. No provider input, Parent launch or prompt binding changed;
the multiple-profile and original-prompt qualifications above remain valid.
Complete case 56 uses `kiosk_multiple.INELIGIBLE_CASE_PLAN` / `execute_ineligible`
with the same fixed setup action and complete multiple-account worker. Both
representative eligible pairs reach correctly bound prompts and cancel. The locked
administrator is excluded by every exact offered-set check. The historical
four-pair case with separate selector-collapse checks passed in
`20260926T200913Z-2d372359`, including preserved-form readback, Cancel/GDM return,
collection, owned cleanup and baseline restoration.
Host adapter/decoder/worker regressions live in
`test_e2e_kiosk_valid_duration.py` and `test_e2e_kiosk_eligible_choices.py`;
fixed account creation and preservation are covered by `test_dynamic_account_fixture.py`;
the plan participates in `test_installed_journey_cleanup_safety.py`.

FIX03's no-approver profile starts with
`AccessibleUI.kiosk_approver_baseline`: require at least one parent in the public
form, without fixed parent names or counts. The API's selected canonical UID and
owned selected-value control establish the account independently of popup state.
`NoApproverFixture.prepare` privately passes that observed UID to
`e2e_dynamic_account.prepare_no_approver`, which detects all eligible OS accounts
before mutation, requires the observed parent in that set, then validates and
locks those accounts through AccountsService. Preserve both children, the station and other
accounts; outer snapshot restoration owns undo. `kiosk_no_approver.PLAN` returns
to GDM and reopens the station before requiring the empty parent list,
unavailable explanation/controls and no prompt through
`AccessibleUI.kiosk_request_form(no_approver=True)` and
`RequestObservation.from_request`. `onpc_kiosk_no_approver::run` qualified the
composition through `check_e2e_kiosk_fixtures` in run
`20260924T173358Z-94d5db62`: independent valid entry, wrong-entry refusal,
nonempty public baseline, eligible-parent locking, Cancel/GDM/reentry, repeated
empty-state observations, collection, owned cleanup and baseline restoration
passed. This developer-authorized scope replaces the two-canonical-parent setup
rule. Complete case 55 independently passed through
`kiosk_no_approver.CASE_PLAN` / `onpc_no_parent::run` and
`tools/run-tests e2e --id '55'` in run `20260925T035302Z-c89cac03` after the
shared-fixture extraction: public
nonempty-parent baseline, discovered eligible-parent locking, Cancel/GDM return,
fresh station entry, repeated exact empty-parent explanation/list, disabled
submission and absent prompt. Capture reconciliation, collection, owned cleanup
and baseline restoration passed. Wrong-entry refusal remains qualification-only;
durable journey evidence records presence/counts, not account identities.

Every recipe has the same surrounding phases, already present in all inventory declarations:

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

The [customer scenario recipes](E2E-Scenario-Recipes.md) now own all finite
case bindings and ordered step compositions. The JSON inventory contains only
customer actions and observations in customer families. Use the recipe together
with these blocks; do not reintroduce old private witnesses from a task note.
Ready callbacks retain their existing fixture, credential and phase contracts.

The scoped links below locate recipe families without repeating their case lists
or assertion review. Follow every retained variant in the selected recipe;
a family link is not permission to sample. Customer setup is part of each
independent case. Harness case 1 remains separate qualification. Retired E2E
IDs 140–150 belong only to the system-test tasks listed under inventory reconciliation.

### Parent, login and time scenarios

Every E2E invocation, including a single-case selection, holds one exclusive VM
lease. Suite preparation runs once, before the first case, reusing an existing
`onpc-v[version]` snapshot (the current app release without package revisions).
Qualification inputs are keyed to current source content through `named_input()`.
Reuse requires matching package bytes, baseline identity and the
installation recipe recorded in snapshot metadata, plus the requested mode and
online freshness/restore guards. Missing, legacy or changed snapshots restore
`onpc_baseline`, install and verify the declared package, and capture the version
snapshot under the shared lease. Online mode captures the running guest after
verified reboot; offline mode captures after shutdown and gets its clean restart
when the restored guest boots. This installation belongs to suite preparation.

Freshness metadata is published only after snapshot creation returns successfully,
using libvirt's [metadata redefinition API](https://libvirt.org/html/libvirt-libvirt-domain-snapshot.html#virDomainSnapshotCreateXML).
An interrupted creation leaves an unmarked snapshot, which preparation refreshes.

The installed-state fingerprint deliberately excludes test code, guest helper
logging, scenario selections, fixture delivery payloads, documentation and run
outputs. These are refreshed as a separately verified test payload before each
attempt; they do not reinstall the app. Reusable fixture sources instead belong
to the baseline preparation identity; changes invalidate the baseline and its
derived app snapshots. App-snapshot preparation installs the product and verifies
the declared baseline inputs. It never installs persistent test prerequisites.
The [guest input resolver](../../tests/integration/guest_inputs.py) follows local
Python imports recursively from declared entry points, including imports inside
functions, and rejects missing or ambiguous dependencies before staging. Dynamic
entry points and non-Python resources still require explicit consumer declarations.
E2E freezes its helper bundle once per invocation; system tests freeze their
selected closure before acquiring the VM. Later checkout edits affect the next
bundle. Existing transfer digests and offline retirement of old guest payloads
prevent changed or removed helpers from leaking across restored attempts.

Each case then starts from the snapshot required by its purpose:

- Installed-app validation must declare `installed-digest-verified-product` and
  restore the suite's version snapshot, without installing or rebooting as case
  setup. This covers E2E-003's two ready variants, both E2E-004 launch routes,
  E2E-030/parent and E2E-042/command-help.
- Cases testing installation, removal or package behavior may declare
  `declared-package-lifecycle-fixture` and start from `onpc_baseline`, with
  installation performed as part of the tested package behavior.
- Runner-only product-free harness checks, including retained case E2E-001, start
  from `onpc_baseline` without installing the app.

Inventory validation enforces these declarations for existing and future cases;
the installed-app and package-lifecycle prerequisites are mutually exclusive.
The suite verifies the required snapshot was restored before provisioning.
Installed journeys have no per-case installer: a missing snapshot fails the
invocation without fallback installation.

The expensive baseline audit and offline guest inspection bracket the suite.
After collecting a case's observations, the worker's final power-off callback
restores the required off state through the shared lease; it does not wait for
ACPI. After fresh attempt inputs are staged, installed online state resumes
through the owned memory-snapshot route; offline/product-free state uses guarded
provisioning and boot. The shared lease owns these transitions; cases issue no
additional restores. Live ownership, disk identity, snapshot metadata and
isolation checks still apply; transitions add no package validation,
installation or reboot. Suite cleanup restores `onpc_baseline` and
preserves the version snapshot through the final audit. The journal records its
exact name during creation for interrupted-preparation cleanup; successful creation
clears that deletion obligation so completed snapshots survive interrupted runs.
Per-case evidence is
provisional until the final suite audit and release; failures stop subsequent
cases. This changes runner transitions, not any customer action or assertion.
See [suite lease](../../tests/e2e/suite_lease.py) and the shared
[app snapshot module](../../tests/e2e/app_snapshot.py). `run-tests` calls it with
`overwrite=False` to reuse a current version snapshot and uses the shared [cleanup module](../../tools/test_recovery.py)
before starting the E2E run.

Standalone preparation uses `tools/prepare-appsnapshot` under
[Approval tools](../Approval-Tools.md#one-time-setup), which owns mode defaults,
overwrite behavior, platform selection and maintained recovery. Online is the
default: matching fresh state is restored without a build and the guest remains
running under VM-maintenance ownership. Offline preparation leaves it powered
off. Both retain `onpc-v[version]`; neither a snapshot name nor a prior task's
mutable guest state is freshness or acceptance evidence. Reusable guest inputs
remain exclusively owned by baseline preparation.

The [live verification contract](E2E-Execution-Contracts.md#live-verification-contract)
defines when a task prepares or reuses this snapshot. A retained snapshot is a
setup prerequisite, not customer-acceptance evidence. Release an online
maintenance instance through `tools/test-vm --vm NAME stop` before the guarded
qualification or E2E attempt acquires its own lease. Subsequent VM actions still
use the guarded ownership interfaces.


E2E-001 remains [harness qualification](#case-1-stage-contract). For customer
families E2E-002–011, select the exact [family recipe](E2E-Scenario-Recipes.md#family-compositions)
and consult the [family allocation review](UI-and-E2E-Coverage.md#complete-scenario-family-review)
for assertion ownership. Case IDs and runtime bindings come from the inventory;
this catalogue does not maintain another case list.

### Request forms and remembered choices

Use the [E2E-012–018 recipes](E2E-Scenario-Recipes.md#e2e-012) for request
entry, approval, exit, selection and persistence compositions. E2E-014 retains
the [native-gesture exclusion](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures);
its recipe records uncovered assertions, not reusable qualification or an
implementation task.

Case 58 uses `remembered_choices.PLAN` / `onpc_remembered_choices::run`.
Jordan sets custom `1.25` minutes / 75 seconds with soft apps included; Riley
sets `2.5` minutes / 150 seconds with soft apps excluded. Each overlay retains
Casey (the Sam fixture binding), while the kiosk retains Jamie. One overlay
visit and transfer per child supply immutable source captures. The kiosk then
reselects both children and compares their saved values against those original
captures: four comparisons cover transfer, persistence, child isolation and
independent surface approvers. Neither retained child desktop is revisited;
its GDM password behavior is outside this acceptance history. Initial account
and credential-recipient guards are unchanged. The historical retained-return
scene remains explicit maintenance-only `remembered_choices.DIAGNOSTIC_PLAN`.

Independent complete-case acceptance passed on Ubuntu 26.04 in
`20261010T163428Z-a8f26ba6` and Fedora 44 in `20261010T163428Z-b7f41533`.
Both runs passed collection, owned shutdown/cleanup, baseline restoration and
source/host preservation. Host composition checks also prove that either old
retained-return failure checkpoint cannot interrupt the shortened case.
Cases 59–61 remain pending.

### Application routes and complete customer journeys

Use the [E2E-019–027 recipes](E2E-Scenario-Recipes.md#e2e-019) for launch,
catalogue mutation, retained-session, gameplay, update and removal journeys.
Their finite route sets, ordered outcomes and applicability gates remain in
those recipes and their selected task briefs.

### Recovery, information and feedback

Use the [E2E-030–033 recipes](E2E-Scenario-Recipes.md#e2e-030) for installed
information, report composition, service acceptance and reconnection journeys.
Retired families E2E-028/029 retain the engineering obligations listed under
[inventory reconciliation](#inventory-reconciliation).

### Additional customer coverage

Use the [remaining family recipes](E2E-Scenario-Recipes.md#e2e-035) and
[additional finite branch recipes](E2E-Scenario-Recipes.md#additional-finite-branch-recipes)
for later features. The [coverage review](UI-and-E2E-Coverage.md#complete-scenario-family-review)
records absorbed, removed and UI-owned assertions; the inventory owns stable
IDs and executable status. The Lunar gate below supplements E2E-052's recipe.

### Lunar Client preparation and observation gate

Case 253 is a planned real-application regression, not an extension of the native
fixture's qualified scope. Its reusable prerequisites must be declared and
reconciled by baseline preparation before the attempt: install a pinned Lunar Client AppImage and AppImageLauncher,
integrate the original AppImage through the provider's normal route, enable
Lunar's child-login autostart and tray behavior, and prepare Minecraft with a
legitimately usable test account, downloaded runtime/assets and a disposable local
world. Record versions/digests, the exact integrated launcher, original AppImage
path (including spaces), same-directory version pattern, autostart entry and
provider versions as private fixture inputs. No real child's name/path or account
credentials belong in scenario metadata, ordinary logs or screenshots. Use the
existing secret API for any required authentication; no new account purchase or
external account creation is implied.

Task 295/FIX05 must first establish how these inputs are present **after** the
runner's ordinary installed-snapshot restore. Use the authorized baseline route
and its finite idempotent inventory; do not add alternate snapshots, skip
restoration or rely on earlier manual VM state. FIX04 transfers attempt inputs;
FIX05 verifies this real-app profile and FIX06 verifies repository-owned fixtures.
This prerequisite does not grant FIX05 an installer or
unattended vendor sign-in. Missing integration, invalid sign-in, mandatory update,
network dependence or unavailable assets blocks this profile until resolved in
preparation. Pin a profile that runs the declared local activity without downloads
or authentication during the measured launch checks; requalify after drift.

The [canonical queue](E2E-Task-Queue.md) separates original-AppImage usable
launch/Quit (296c), tray close/restore (296d), specific command denial and their
composition (296), Minecraft entry/exit (296e), local-world activity (296a),
allowed continuous login (296f), and denied login/launch observation (296b).
Their APP01/02/03/06, UI18 and UI22 bindings stay separately qualified; task
order and prerequisites remain in the queue. Apply the
[provider exception](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception)
inside explicit adapters. Ownership, complete absence observations, ambiguity
refusal and independent results remain mandatory.

Task 296b reuses UI22's qualified observer lifecycle and the existing reboot/session recorder: arm
the public observation before child login submission, preserve secret filtering,
and observe the login transition through **90 seconds after desktop readiness**.
Qualify observer reattachment before any possible Lunar surface; a blind login
interval cannot pass. APP06 observations must cover both tray and app/game
surfaces, not just a final window list. A usable Lunar/Minecraft surface at any
point in a denied interval fails even if it later closes. Require the allowed
autostart control in the same attempt, plus a specific public access denial from
one explicit original-AppImage launch in each denied checkpoint. A hidden grid
entry, generic startup failure or absent tray alone is insufficient. These
bindings remain pending until they can reliably establish the observations;
process lists, rule files and daemon logs are not customer acceptance substitutes.

No source extraction, direct embedded-binary/Java launch, alternative package,
disabled autostart or post-login policy save may replace the registered route.
The real AppImageLauncher route is the regression target; its read/copy/execute
mechanics belong to engineering coverage. Future version matching and other-user
isolation retain their existing owners. This planned profile changes no product
dependency, activation or migration, and no VM preparation has been performed.

### Inventory reconciliation

The UI inventory contains only the harness qualification and customer journeys.
Retired E2E coverage IDs 140–150 are never reused. Their fault injection,
service, process, D-Bus and transaction assertions remain engineering
obligations in system-test tasks 169–179, outside `scenarios.json` and E2E
selection. Customer families have no backend assertions or delivery-receipt
evidence. E2E-033 is the ordinary network-controls customer retry route.

The exact displaced engineering assertions are retained below, grouped only
when their original wording is identical. The listed source files are maintained
owners, not a claim that every obligation already has an executable or passed
case. Missing exact implementation stays pending under that owner; preserve all
existing checks. Engineering completion requires its own complete qualification.
Case 1 remains the noncustomer harness qualification. The retired 140–150
assertions remain in tasks 169–179 and their maintained engineering owners;
they are never E2E cases or customer passes.

| Scope | Maintained engineering owner |
| --- | --- |
| Package content, notices, startup, migration and removal | [installed package checks](../../tests/system/test_install_smoke.py), [installer](../../tests/unit/test_installer.py), [removal](../../tests/unit/test_package_removal.py), [APT notice](../../tests/unit/test_apt_removal_notice.py), [broker startup](../../tests/component/test_broker_startup.py) |
| Identity, grants, transaction ordering, stale approvals and rollback | [core](../../tests/unit/test_core.py), [authorization lifecycle](../../tests/component/test_authorization_lifecycle.py), [installed authorization](../../tests/system/test_authorization.py) |
| Time accounting, enforcement and retained process/session identity | [installed expiry](../../tests/system/test_session_expiry.py), [installed enforcement](../../tests/system/test_enforcement.py), [application termination](../../tests/unit/test_app_termination.py), [execution policy](../../tests/unit/test_execution_policy.py) |
| Saved selectors and future mute fields | [preferences](../../tests/unit/test_preferences.py), [shared form](../../tests/ui/test_request_form_component.py); task 154 remains deferred future-feature qualification |
| Diagnostics, draft bytes, privacy, retry transport and provider receipt | [diagnostic export](../../tests/unit/test_diagnostic_export.py), [privacy](../../tests/unit/test_diagnostic_privacy.py), [feedback transport](../../tests/unit/test_feedback_transport.py), [Parent feedback](../../tests/ui/test_parent_feedback.py), [error feedback](../../tests/ui/test_error_feedback.py). Actual recipient/provider work requires separately authorized integration; no portal change is authorized. |

| Original assertion identities | Retained wording |
| --- | --- |
| E2E-002/installation-result | Absence before installation, exact installed package digest and product-created reboot marker are independently observed. |
| E2E-002/backend-result | Boot identity changes without a baseline restore; installed files, ownership, services, D-Bus, Polkit, PAM, sessions, configuration, extension payload, logs and execution policy match the release package. |
| E2E-002/broker-readiness | Broker D-Bus object publication follows completed execution-policy reconciliation and required extension activation; a final active-service snapshot alone cannot prove ordering. |
| E2E-002/login-readiness | The live-policy canary denial completes fapolicyd startup before display-manager startup; correlate same-boot backend ordering with the GDM screen. |
| E2E-002/other-user-result | Compare existing child, parent and unrelated-account identities and unrelated settings before installation and after reboot, allowing only documented package provisioning and enforcement changes. Reboot ends sessions; do not claim foreground process continuity across it. |
| E2E-005/backend-result | Verify saved allowance, grant preservation/clearing, child-component activation and app policy per transition; invalid values never commit. |
| E2E-005/other-user-result, E2E-006/other-user-result, E2E-007/other-user-result, E2E-008/other-user-result, E2E-009/other-user-result, E2E-010/other-user-result, E2E-011/other-user-result, E2E-012/other-user-result, E2E-013/other-user-result, E2E-014/other-user-result, E2E-015/other-user-result, E2E-016/other-user-result, E2E-017/other-user-result, E2E-018/other-user-result, E2E-019/other-user-result, E2E-020/other-user-result, E2E-021/other-user-result, E2E-022/other-user-result, E2E-023/other-user-result, E2E-024/other-user-result, E2E-025/other-user-result, E2E-026/other-user-result, E2E-027/other-user-result, E2E-031/other-user-result, E2E-032/other-user-result, E2E-033/other-user-result | Compare other child, parent, and unrelated-user policy, grants, sessions and recorded process identities before and after; verify no unintended change or interruption of the other foreground user. |
| E2E-006/backend-result | Current executable/filter/process identities and saved match patterns agree with visible effects. |
| E2E-007/backend-result | Grant is removed, daily usage/allowance preserved and all selected-child session effects verified. |
| E2E-008/backend-result | Measured usage exhausts daily allowance; expiry retains the session until the explicit logout and never ends another session. |
| E2E-009/backend-result | Grant identity, retained session and replacement-policy/process effects agree with each approval. |
| E2E-010/backend-result | The actual retained sessions survive with child-only lock enforcement. |
| E2E-011/backend-result | Read-only daily/grant values and session identities explain the displayed maximum remaining time. |
| E2E-012/backend-result | Time and app access commit together; excluded soft apps close required child apps before granting, included soft apps preserve open processes. |
| E2E-013/backend-result | The denied/cancelled attempt grants no time or policy relaxation; only successful retry commits. |
| E2E-014/backend-result | Exactly one grant transaction occurs per deliberate valid request; rejected values never grant access. |
| E2E-015/backend-result | Only approved exit changes grant state; cancellation never logs out the child session. |
| E2E-016/backend-result | The real dedicated session has no general desktop or management authority. |
| E2E-017/backend-result | Displayed account identity and enabled state match real services; rejected requests do not mutate access. |
| E2E-018/backend-result | Read-only preference identities corroborate choices and other-child isolation. |
| E2E-019/backend-result | Actual executable or sandbox application identity, filter and process evidence explain each decision. |
| E2E-020/backend-result | Verified before/after app identities and stored rule target match the real package operation. |
| E2E-021/backend-result | Identity-recorded process and session evidence proves all selected-child sessions and other-user isolation. |
| E2E-022/backend-result | Boot/session continuity records the actual transition; stored preferences and current grant explain enforcement. |
| E2E-023/backend-result | Input digests, natural grant expiry, boot/session continuity and identity-recorded surviving game corroborate every transition. |
| E2E-024/backend-result | Measured daily use, preexisting grant and approved duration corroborate accumulation without shortening expiry. |
| E2E-025/backend-result | Current grant identity and live filter show session entry respects the replacement and does not apply stale expired-grant policy. |
| E2E-026/backend-result | Release/supplemental package digests, actual activation transition and persisted settings agree. |
| E2E-027/backend-result | Actual package transitions and read-only removal assertions corroborate file/account/policy cleanup without in-journey restore. |
| E2E-031/backend-result | Read-only exported fixture metadata and local draft behavior match the declared contract without private preference/credential disclosure. |
| E2E-032/backend-result | Dedicated recipient receipt and safe service/idempotency evidence corroborate delivery for this attempt. |
| E2E-033/backend-result | Declared network failure/recovery and safe receipt/idempotency evidence establish retry of the same frozen report. |

Original installation-notice assertions in E2E-002/027 additionally required
red final output. Their exact notice content and last-output contract remain;
color has no customer acceptance authority. The existing notice tests are
retained under package/UI qualification, not weakened to manufacture a pass.

The original E2E-018 visible assertion, “Cross-surface selections persist per
child; mute remains independent for each surface,” retains its interactive
mute portion as deferred future-feature scope. Current ONPC-CORE-REQUEST-018
requires no public mute control; E2E-018/022 now test available choices without
waiting for that future feature. The saved-field engineering obligation remains.

E2E-033's displaced engineering intervention and receipt sequence is retained
under the feedback transport/integration owner:

- step-2: Use the declared guest network control to interrupt the real delivery transport before Send; do not replace the server or forge responses.
- step-4: Restore the real network connection within the documented retry window and record recovery.
- Original visible-result: The real transport failure and eventual delivery are visible; no mock success is accepted.

Each intervention retained its declared guarded guest actor and independent
service/account/process and continuity evidence. The new customer case uses
only displayed connectivity/retry/results and does not satisfy those internal
or recipient assertions.

No customer recipe secretly prepares an already-open hard-blocked app. The
preservation of such an app by soft-included approval remains in core/application
termination qualification until a real public setup is demonstrated. Similarly,
same-child multiple desktops remain gated; repeated GDM resume is not a substitute.
Package unsupported-OS/reserved-account failures, storage conversion/rollback,
all-account authorization, diagnostic sanitization/retention and injected failures
remain separate technical coverage. The complete original obligations do not
disappear because their customer counterparts have visible outcomes.

### Bound recipe data before implementation

Use the [finite data and budgets](E2E-Scenario-Recipes.md#finite-data-and-execution-budgets),
[branch recipes](E2E-Scenario-Recipes.md#additional-finite-branch-recipes) and
[coverage ownership](E2E-Scenario-Recipes.md#coverage-ownership-and-remaining-limits).
Every required public route, fixture, selector, response, time margin and
comparison must be bound before execution. No callback may choose a more
convenient expected result after failure.

Each repeated-routine row has its own immutable public observations and unique
checkpoint names (case/cycle/row/child). Preserve the complete prefix of a failed
run in existing runner artifacts; there is no resume from cycle 2 and no terminal
state that can substitute for a missing cycle. Limits, permissions and window
lifetimes come from that case's public actions. Read-only observation does not
include switching users: a return after grant expiry may itself restore blocks.
E2E-038 performs its no-restoration checks before leaving the child desktop.
FLOW13 uses the [explicit time preparation table](E2E-Scenario-Recipes.md#explicit-time-preparation);
positive daily allowance must never be assumed to mean positive remaining time.

## Finite values and applicability constraints

The recipe document owns the complete finite value sets. UI allowance is
0–1439; request custom duration is 0.1–1440 minutes. Interactive mute is deferred;
case 154 (attachments) must not be confused with task 154 (future mute).
Public same-child desktop entry, pending-prompt leave/close routes, genuine
diagnostic-collection failures, calendar windows and external sending remain
explicit gates. Missing gates keep only their dependent cases pending.

Functional acceptance uses accessible meaning and real user input. It never
gates on transient animation duration, color, fixed geometry, scale or image
similarity. A read-only UI trace may establish a required disabled/pending state;
no observer may pause the product to make that state last longer.

## Case 1 stage contract

The harness uses this protocol from
[controller_qualification.py](../../tests/e2e/controller_qualification.py),
`FUNCTIONAL_SERIAL_STAGES` in
[check_graphical_smoke.py](../../tests/integration/check_graphical_smoke.py),
[onpc_gdm.pm](../../tests/integration/graphical_smoke/lib/onpc_gdm.pm) and
[onpc_serial.pm](../../tests/integration/graphical_smoke/lib/onpc_serial.pm).
Block IDs map to the existing wire stages and runner.

| Ordered stage | Block boundary and evidence | Recorder phase / next input |
| --- | --- | --- |
| `ready` | Existing asset receipt/guard plus HAR03(greeter/boot); bind `functional_smoke`. | `start`; durably open `step-1` before reply. HAR01 selects `sut`. |
| `gdm` | GDM01 + UI13: fresh `ui:gdm-product-free-list`, exact Parent-only account set and fresh semantic focus. | `step-1`; `ui_focused` permits UI14 without positional navigation. |
| `focused` | UI14's independent focus observation: `ui:gdm-product-free-focused`. | `step-1`; only now send one Enter via UI05. |
| `selected` | GDM08: `ui:gdm-product-free-select-parent`, correct label/focused password role and hidden list. | `step-1`; no graphical password, then GDM09 sends one Escape. |
| `dismissed` | GDM09's GDM01 result: `ui:gdm-product-free-returned`. | `step-1`; durably open `step-2` before reply permits serial entry. |
| `serial-password` | HAR05: actual login prompt, selected fixture echo and bounded password prompt; HAR03 verifies login process/TTY and disabled echo. | `step-2`; store proof before one UI19 secret input and one newline submission. |
| `serial-authenticated` | HAR05: fresh HAR03 confirms the real fixed serial session. HAR02 still waits for the shell prompt before a command. | `step-2`; never infer shell readiness from session activation alone. |
| `serial-command` | HAR06: actual complete output of the existing split-marker command, then HAR03 session proof. | `step-2`; store command evidence before permitting logout. |
| `serial-logout` | HAR07: `exit`, fresh login prompt and independent session-free greeter. | `step-2`; durably open `step-3` before reply permits return to graphics. Emit exactly one successful logout marker. |
| `gdm-return` | HAR08: select `sut`, independent session-free greeter and fresh `ui:gdm-product-free-returned`. | `step-3`; record `other-user-result` with its evidence before reply. |
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
requirements. Keep them in registered bindings; do not offer arbitrary
commands/regexes or broaden authentication. Preserve
the legacy serial install/refusal callers and all existing safety regressions.
The public GDM blocks must remain usable by another independently supplied valid
entry state; they must not depend on case 1 having run first.

## Refactoring the established cases

Ready cases are discovered from the executable inventory, including installation
and unavailable-request variants. Each recipe composes the catalogue and shared
harness. Python recipes own expected values, ordered checkpoints, fixture
bindings and phases; Perl recipes invoke shared blocks and checkpoint operations. Shared entry
declarations come from `journey_blocks`, with no case-to-case plan imports.

Qualification belongs to each route's catalogue entry and retained runner
result; the [execution plan](E2E-Execution-Plan.md#current-scope) records the
completed initial migration. Composition checks alone supply no live credit.

The current product-focused revision removes consecutive activity readbacks in
cases 44–46, duplicate unavailable-form reads in cases 54/55 and their
qualifications, and duplicate pre-request station restriction sweeps in cases
51/52. Original activity is still compared before resuming; every forbidden
station route is checked after denial/cancellation (before exit for approval).
Both empty-account cases finish through normal Cancel and an independent
usable-greeter result. Case 152 keeps wrong-entry exercises in isolated harness
qualification. Cases 184/193/255 and retained-entry qualifications have the narrower
contracts recorded above. Their changed compositions need scoped live validation;
historical passes and ready inventory bindings alone do not establish it.

| Established code | Shared composition | Preserved behavior |
| --- | --- | --- |
| [controller_qualification.py](../../tests/e2e/controller_qualification.py), `onpc_flow00::run` | `serial_harness.record_serial_journey` owns the product-free attempt envelope; FLOW00 composes GDM02/09 and HAR05/06/07/08, then HAR10/09 reconcile evidence. | No graphical secret; real serial authentication/command/logout; exactly one logout before fresh graphical return. Preserve all harness/backend safeguards and the existing wire stages. |
| [parent_discovery.py](../../tests/e2e/parent_discovery.py), [onpc_parent_discovery.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_discovery.pm) | GDM07, SEARCH06, PARENT02/03/04/19, FIX01 in case 3 or FIX02 in case 4 and explicit UI12 comparisons. | Product pickers use stable IDs and canonical values through the shared API, with independent selected-child/settings readback. Existing child starts limits-off/zero; each child's returned values compare with its own observation. FIX01 stays after visible initial settings; FIX02 stays after launchable search but before launching Parent. |
| [parent_access.py](../../tests/e2e/parent_access.py), [onpc_parent_access.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_access.pm) | GDM07(standard), SEARCH01 → UI21 → SEARCH03 → SEARCH04(unavailable). | Direct standard-account selection and two fresh intended-recipient checks; semantic focus then independent focus observation; one complete query then independent full readback; complete stable launcher/window absence; unrelated results remain unopened. |
| [parent_terminal.py](../../tests/e2e/parent_terminal.py), [onpc_parent_terminal.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_terminal.pm) | GDM07(standard) → PARENT01(denied) → `onpc_window::close` (UI18). | Direct command once, management denial and exclusion, fresh active-window proof before close, desktop return with management absent. The legacy variant ID remains `terminal`. |
| [parent_about.py](../../tests/e2e/parent_about.py), [onpc_parent_about.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_about.pm) | FLOW01(GDM07, direct-command PARENT01), one product-information read/guarded About close and explicit settings observation. | Functional GDM goes straight to the intended account and retains two fresh recipient checks. Read owned product/version/legal information, close only About and compare child/switch/allowance; link controls belong in UI tests. |
| [command_help.py](../../tests/e2e/command_help.py), [onpc_command_help.pm](../../tests/integration/graphical_smoke/lib/onpc_command_help.pm) | GDM07(Parent) → four explicit INFO02 bindings → one final desktop-clear observation. | Parent/station help and manuals use bounded command stdout with identity/content checks, followed by one independent desktop result. No per-command desktop checks, terminal or arbitrary command API. |
| [clean_install.py](../../tests/e2e/clean_install.py) | `package_journey.record_package_journey`, `journey_checks`, LIFE04/02 and shared Parent/station blocks. | The recipe declares result-check placement; the envelope stages assets and submits once. Independent completion, account preservation and nonempty Allowed rows must pass before the durable reply. |
| [kiosk_no_child.py](../../tests/e2e/kiosk_no_child.py), [kiosk_no_approver.py](../../tests/e2e/kiosk_no_approver.py), [disabled_child.py](../../tests/e2e/disabled_child.py) | FIX03 `account_fixture.station_fixture_actions` for the two empty-account cases, `journey_blocks.parent_management` for disabled-child, `station_entry` and shared request operations. | Each empty-account attempt receives a fresh single-use fixture. No-child preparation remains at setup; no-approver preparation remains after its public baseline. Disabled-child never enables limits. |

The extracted helpers are [onpc_about.pm](../../tests/integration/graphical_smoke/lib/onpc_about.pm),
[onpc_window.pm](../../tests/integration/graphical_smoke/lib/onpc_window.pm),
[onpc_documentation.pm](../../tests/integration/graphical_smoke/lib/onpc_documentation.pm),
`onpc_parent::launch_search_result`, [journey_blocks.py](../../tests/e2e/journey_blocks.py),
[journey_checks.py](../../tests/e2e/journey_checks.py),
[package_journey.py](../../tests/e2e/package_journey.py),
[account_fixture.py](../../tests/e2e/account_fixture.py) and
[serial_harness.py](../../tests/e2e/serial_harness.py).
UI18 shares one close implementation across About and denial. SEARCH05 shares
one result-commit implementation across normal and empty-account discovery;
FIX02 still completes before its proof permits Enter. Recorder and serial
protocol mechanics stay in the harness, without adding a second runtime.

Shared capabilities and remaining extension boundaries:

- The discovery `AccessibleUI.run` bindings delegate to registered picker,
  settings, page, search and desktop callables. Continue extracting the other
  consumers without exposing unrestricted operations or moving expectations
  out of their recipes.
- The discovery `JourneyPlan.settings_checks` supplies immutable expected values and
  explicit earlier-stage references. `InstalledJourney.check_settings` checks
  these before fixture actions and durable replies; the discovery-specific
  hidden settings slots are gone. The About recipe uses the same explicit
  comparison contract. Legacy credential order still uses `last_operation`
  within the qualified single-authentication route.
- Kiosk cases and qualifications use
  [`request_composition.KioskRequestJourney`](../../tests/e2e/request_composition.py).
  `JourneyPlan.request_checks` maps each returned stage to an earlier capture,
  failure label and comparison-result key; `balance_checks` declares exact fresh
  unused-child balances. The shared class copies observations, compares the
  complete request, and rejects missing/replayed captures before acknowledgement.
  Stage names and qualification default plans carry no implicit assertions.
  Cases 47/48/50/51/52/192 select this class directly; qualification wrappers
  only supply their own plans. Renamed-stage and changed-field regressions live
  in [the kiosk checks](../../tests/unit/test_e2e_kiosk_valid_duration.py).
- `JourneyPlan.challenges` binds a nonsecret challenge ID to its fixture role
  and two consecutive declared invocation IDs. `UiObservations.observe_challenge`
  requires fresh, ordered same-challenge observations; the durable controller
  reply carries the challenge, role, GDM surface and check identity.
  `onpc_journey::declare_challenges` and `onpc_password::enter_gdm_challenge`
  consume those proofs through the repeated-stage interface. The shared UI19
  leaf retains one fixed secret API call, capture sealing, wrong-recipient
  refusal and terminal failure; neither used identities nor failure latches
  reset. Legacy workers retain their single-use compatibility entry. The fixed
  `check_e2e_challenges` plan observes wrong-entry refusal, two Parent logins and
  shared DESK04 logout between them. Live run `20260924T192200Z-c833e973`
  passed all four durable assertions, proof reconciliation, private collection,
  worker cleanup and baseline restoration. Qualification covers two distinct
  Parent GDM challenges on the pinned Ubuntu 26.04 English-GDM,
  baseline-keyboard image; it supplies no complete-scenario credit. Host safety
  regressions retain stale/reused/mixed-proof and terminal-failure refusals.
  DESK08/AUTH02 and other
  surfaces still need their own declared bindings and qualifications.
- Current public-bus routing supports the active greeter, fixed Parent and
  other-child desktop. Add the intended child/other-parent/kiosk/lock routes
  only with their named entry consumer, preserving socket/account ownership
  checks. Metadata for routing is not evidence of product behavior.
- `JourneyPlan.screen_tags` maps unique stage IDs to public operations, allowing
  the same operation at several stages. `JourneyPlan.invocations` declares an
  ordered finite subset for `onpc_journey::declare_invocations/invoke`; the ready
  reply binds the worker's fixed list. Each invocation observes afresh and rejects
  duplicate, missing, stale or reordered replies, with a terminal failure latch.
  `assertions_after` places a visible assertion after its stage's durable
  observation and before `advance_after` opens the next phase or replies permit
  input. Empty declarations preserve existing workers and terminal assertions.
  [The repeated-operation plan](../../tests/e2e/repeated_operations.py) gives two page-return
  cycles separate immutable baselines and assertions, with wrong-child entry
  refusal. Its fixed `check_e2e_give_repeated_public_operations_distinct_stages`
  installed qualification passed in run `20260924T182527Z-aff50093`: fresh Parent
  entry, wrong-child refusal, both immutable-baseline comparisons, durable
  `first-return`/`step-1` and `second-return`/`step-2` assertions, collection,
  reconciliation and owned cleanup. The first assertion precedes the next phase
  and acknowledgement. Preserve `phases`, fixture timing and store-before-reply;
  this qualifies the repeated PARENT03/04 and UI12 slice, not case 2 or repeated
  authentication.
- UI22 needs bounded public-state observation active before the triggering
  worker input. Extend the existing rendezvous for its named transition
  consumer, retaining durable readiness/input/result ordering, single input and
  the terminal failure latch. Post-action polling cannot replace this trace.
- `InstalledJourney` rejects customer-phase boot changes except for one explicit
  adjacent `JourneyPlan.reboot_transition` pair. The command stage requires the
  administrator command context, records intent before one guarded submission,
  and the next stage independently verifies the changed boot before fresh GDM.
  Its [qualified scope](#customer-reboot-continuity) is fresh install/reboot and
  administrator return. Unexpected or additional boot changes still fail;
  existing plans retain their unchanged single-boot path. LIFE05's product
  activation/persistence assertions remain with their consumers.

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
The [composition guard](../../tests/unit/test_e2e_case_composition.py) discovers
every ready executable and its registered worker, checking all Python definitions
for local mechanics and case dependencies, and reconciling phases/assertions with
the inventory. Its reviewed API list contains shared callables, never a fixed
list of cases. Independent
window-close and search-commit regressions reject stale/missing proofs, uncertain
input, missing results and replay; real worker tests preserve exact stage order.
Run affected host checks and the applicable live acceptance in the
[execution contract](E2E-Execution-Contracts.md#live-verification-contract).
Changes to shared GDM, secret input, stage
reconciliation or public-UI routing also require their affected safety/harness
qualification; do not run the whole future matrix merely for an extraction.
## About block contracts

Current customer information journeys use one About visit and preserve the work
they return to. Case 151 uses `parent-about-information` /
`AccessibleUI.read_about_information` and `onpc_about::close_information` for
product/version/legal information and unchanged Parent settings. Case 191 uses
`overlay_license_read(links='summary')` for that information before returning to
its captured request. Case 192 keeps the restricted station's offered information
and lack of external actions. Link availability is UI coverage; case 190 has no
E2E binding because its remaining installed outcome duplicates 151. The detailed
link qualifications and historical results below retain their original scope.

Overlay product/version and license clickability use `overlay_license.PLAN` /
`OverlayLicenseJourney` through `check_e2e_overlay_license`, passed on every
enabled VM (Ubuntu 26.04) in `20261002T040745Z-84b460dd`.
`journey_blocks.overlay_license_read` and `onpc_about::overlay_license` expose
the reusable read/close fragment with caller-owned invocation and entry proofs.
`AccessibleUI.overlay_about_scope` binds the active form/About to the child
application, public transient ownership and fixed-child session. The license
reader checks product/version and the shared visible/enabled/actionable link;
it never activates the link or reads its URI. Close uses a fresh active About
proof and one `onpc_window::close('overlay-about')`; complete absence and active
form return precede immutable `KioskRequestJourney` request comparison.
The qualifier exercises missing-About and wrong-account entry refusal, stale
worker-proof refusal, two independent About entries and unchanged 75-second
custom/soft-included choices, then Cancel/desktop return. Host checks cover
missing/disabled/hidden/nonactionable/ambiguous/wrong-owner/stale controls,
product/version mismatches, decoder boundaries, renamed comparison endpoints,
capture mutation/replay and actual worker order/refusal stops. Native GTK uses
the same readers and compares both returns. Private collection, worker shutdown,
owned cleanup and baseline restoration passed. Shared Parent license/About
regression passed in `20261002T041425Z-993080b3` with collection and cleanup.
This qualifies the overlay
license slice of INFO01. Website/privacy use `AccessibleUI.read_overlay_link`,
`overlay_license.BROWSER_LINKS_PLAN` / `OverlayLicenseJourney` and
`OverlayBrowserLinksQualification` through `check_e2e_overlay_browser_links`.
The shared fragment accepts the finite `links='browser-links'` binding; worker
entry is `onpc_request_flow::overlay_browser_links`. Two independent About
entries, website/privacy clickability without activation or URI inspection,
wrong-account/missing-About/stale-proof refusal, unchanged 75-second custom/
soft-included form choices and Cancel/desktop return passed on every enabled VM
(Ubuntu 26.04) in `20261002T042846Z-f7c7a6ce`. Host public-link refusal,
fresh owner/state reacquisition, decoder, worker-order/failure-stop and recorder
startup/cleanup checks passed; native GTK read/return checks passed in
`20261002T042724Z-2d00117e`. The shared overlay-license regression passed in
`20261002T043713Z-c2373c3e`. Both live runs passed collection, worker shutdown,
owned cleanup, source/host preservation and baseline restoration.

Full overlay ABOUT01/INFO01 passed `check_e2e_read_overlay_about_and_links`
on every enabled VM (Ubuntu 26.04) in `20261002T045632Z-62a50e45`.
`overlay_license.INFORMATION_PLAN` declares the finite
`journey_blocks.overlay_license_read(links='information')` binding, with execution
through `onpc_about::overlay_license(..., 'information')` and qualification entry
`onpc_request_flow::overlay_information`. `AccessibleUI.check_overlay_help`
opens the child-owned menu and checks Help without activation;
`open_overlay_about(menu_open=True)` rechecks Help before entering About from
that same menu. Each fresh `read_overlay_link` checks product/version and one
of website, privacy, support, license and legal-notices link clickability.
Two independent About entries, wrong-account/missing-About/stale-proof refusal,
both immutable 75-second custom/soft-included form comparisons and Cancel/
desktop return passed. Host checks cover every link's public-control refusals,
fresh state/owner reads, Help-to-About failure stops, realistic decoder output,
actual worker order/titles, recorder startup and durable comparison refusal.
Native GTK uses the same full information readers and compares both returns.
License-only and website/privacy regressions passed in
`20261002T050326Z-b8fd7de5`. All three live attempts passed private collection,
worker shutdown, owned cleanup, host/source preservation and baseline restoration.
Complete E2E-042 case 191 passed on every enabled VM (Ubuntu 26.04) in
`20261002T052623Z-0b463dbc`, through `overlay_about.PLAN`, shared
`KioskRequestJourney` and `onpc_parent_about::run_overlay`. Fresh 30-minute
Parent setup, child entry, captured 75-second custom/soft-included choices,
Help/all five About links, owned About close, unchanged form and Cancel/desktop
return passed, with private collection, worker shutdown, owned cleanup and
baseline restoration. This complete consumer adds no new link/provider route.

The restricted-station binding uses `AccessibleUI.kiosk_about_entry`,
`open_kiosk_about`, `kiosk_about_snapshot` and `read_kiosk_about(version)`.
The caller supplies an independently open station form; Parent and overlay
owners cannot authorize this route. Its real menu and About actions use public
IDs. Product/version, the five website/privacy/support/license/legal values and
copyright footer are read on the owned About surface. A complete fresh tree
must show the five values as labels and exclude external action controls,
including viewport-clipped controls; inaccessible traversal cannot prove absence.
The close checkpoint reacquires the station-owned About surface before
`onpc_window::close('station-about')` issues its ordinary API close once. Complete About absence
and a fresh form observation precede the immutable captured-form comparison.

`restricted_station_about.PLAN` / `RestrictedStationAboutJourney` and
`onpc_restricted_station_about::run` qualified this slice through
`tools/run-tests integration check_e2e_read_restricted_station_about` in report
run `20260926T202755Z-941af41f`. Independent station entry, wrong Parent entry
refusal, offered information, external-action absence, preserved 75-second
custom request/soft-app choices, normal Cancel/GDM return, private collection,
owned cleanup and baseline restoration passed. This is capability acceptance.
Adapter, worker, return-comparison and controller regressions are maintained in
`test_e2e_kiosk_valid_duration.py` and `test_installed_journey_cleanup_safety.py`.

Complete E2E-042 case 192 composes `kiosk_about.PLAN` / `onpc_kiosk_about::run`
with FLOW16's fresh 30-minute binding. `KioskRequestJourney` accepts
the caller's plan, checks the 1800/0/1800-second starting balances, and compares
the captured form after About closes. `tools/run-tests e2e --id '192'` passed
in `20260926T212947Z-358f37d8`, including offered information, external-action
absence, unchanged choices, Cancel/GDM return, collection, owned cleanup and
baseline restoration.

The [recipe](../../tests/e2e/parent_about.py) and
[worker](../../tests/integration/graphical_smoke/lib/onpc_parent_about.pm) compose
FLOW01, the product-information read and one guarded About close/return. Shared launch stops at `parent-window`
before picker input; selection consumes its own fresh offered-choice, canonical
API setter and independent selected-result observations. Setup reattachment
stays outside the customer entry block.
The About blocks live in `onpc_about`; the worker only composes them. All three
About/denial API close routes reuse `onpc_window::close` (UI18); the
Parent→desktop binding also uses this helper.

PARENT01 is [`onpc_parent::launch`](../../tests/integration/graphical_smoke/lib/onpc_parent.pm).
It consumes one fresh desktop proof, then the fixed `parent-command` checkpoint
invokes `/usr/bin/oh-no-parent-control-parent` through the desktop user's
systemd service manager, inheriting its graphical environment. The adapter runs
unprivileged on the selected fixture bus, verifies one active local graphical
session for its UID and refuses system prompts before submitting once. No
terminal, shell command string, product method or private state is used. An
uncertain submission stops the journey without retry or fallback. Submission
success is not acceptance: a separate checkpoint observes the owned management
window or the specific access denial. Case 6 reuses the same block with
`expected=denied`, then dismisses the denial and independently observes the
desktop with management absent. The legacy `terminal` variant ID stays stable;
terminal opening, focus and closure are no longer part of this case.
Both fresh direct-command bindings passed in
run `20260922T220454Z-80a92d46` (subject to runner artifact retention):
case 6 observed standard-account denial/dismissal/desktop return, and case 151
observed the Parent management window before child selection and completed its
About/license/return journey. Product, infrastructure, collection, cleanup and
suite baseline restoration passed. This qualifies those fresh bindings on the
pinned Ubuntu 26.04 environment; retained-session/reopening and other entry
bindings still need their consumers.

The dedicated `check_e2e_terminal_provider` qualification passed in
run `20260923T193211Z-9824fb0f` on the pinned installed snapshot. It reused
`onpc_parent::launch` from the standard desktop, refused a wrong entry proof
before submission, invoked the fixed command once, observed the owned specific
management denial and absence of management controls, then closed it through
`onpc_window::close` and independently observed the clear standard desktop.
Private collection, reconciliation and owned cleanup passed in that run (now outside runner retention). Complete case 6 then passed in run `20260923T193956Z-9e1b6eac` (also outside runner retention), including the specific denial, management exclusion, desktop return, collection and owned cleanup.

GDM07 uses the shared qualified account navigation to select only Parent and
verify focus before Enter. Wrong-account refusal belongs to separate harness
qualification, not this customer journey. Two fresh intended-recipient checkpoints require the
exact account, hidden list and sole showing/enabled/focused empty masked field.
The final proof immediately precedes the unchanged sealed secret API. No new
role, password surface or appearance gate is qualified. Legacy image helpers
refuse before backend or input; their safety obligations remain represented by
the functional semantic recipient proofs.

ABOUT01 resolves the owned About product/version information by public IDs.
ABOUT02 checks the license control with `AccessibleUI.clickable_link`: visible,
enabled, nondefunct and offering one public activation action. It does not
invoke that action, inspect the URI or validate any external handler/content.
The retained `open_license` callable and `license` stage are compatibility names
for this read-only check. No browser, mail or document provider is required.

`check_e2e_license_viewer`, `LicenseViewerProviderJourney` and
`onpc_license_viewer_provider::run` retain their names but now qualify only
owned link clickability and About return. External fixture launches and
unrelated/empty/ambiguous document checks are retired from this qualification.
Historical viewer passes do not qualify the changed link-only scope.

The link-only scope passed `check_e2e_license_viewer` in run
`20260929T220011Z-55987e7f`: owned clickable license control, fresh repeated
entry, wrong-entry proof refusal, owned footer/About close and unchanged Parent
settings, with collection, owned cleanup and baseline restoration. The link capability
workers share `onpc_about::return_to_parent`; its finite source-stage
binding accepts the ordinary link read or the qualification's repeated read.
This qualifies Parent ABOUT02/03, not INFO01's other links or a new complete
case 151 pass.

Parent INFO01 website clickability passed `check_e2e_parent_website` in
`20260929T221436Z-ffd7ea02`. `WEBSITE_PLAN` maps the shared qualification's
compatibility stages `license` and `license-provider-refusals` to independent
`website-clickable` observations of `about-website-value`. The worker shares
`onpc_about::check_link` and `return_to_parent`, retaining wrong-entry proof
refusal, owned About/footer close and immutable child/settings comparison.
Host success/refusal checks cover missing, disabled, hidden, nonactionable,
ambiguous and wrong-owner links without activation or URI inspection. Collection,
owned cleanup and baseline restoration passed; the affected license-link
regression passed in `20260929T221658Z-c73ff45c`. This qualifies only the Parent
website binding, with no complete-case or destination acceptance credit.

Parent INFO01 support clickability passed `check_e2e_parent_support` in
`20260930T184923Z-b99a34a9` on Ubuntu 26.04. `SUPPORT_PLAN` /
`ParentSupportJourney` bind the same shared sequence to two fresh
`support-clickable` observations of `about-support-value`. Independent entry,
wrong-entry proof refusal, owned About close and unchanged child/settings passed.
The host refusal matrix covers missing, disabled, hidden, nonactionable,
ambiguous and wrong-owner controls without activation. Website, privacy and
license regressions passed in `20260930T185117Z-84119637`,
`20260930T185313Z-66db2268` and `20260930T185506Z-ba92b80b`.
All passed collection, owned cleanup and baseline restoration. Mail handlers,
URI/recipient/subject inspection and sending mail are outside this scope.
The complete Parent information case is implemented separately below.

Parent INFO01 Help and all five About links passed
`check_e2e_read_parent_information_links` in `20260930T192004Z-89316fef`
on Ubuntu 26.04. `INFORMATION_PLAN` / `ParentInformationJourney` bind Help menu
reading, About entry from that still-open owned menu and two fresh all-link
reads to the same shared `clickable_link` reader. `check_parent_information`
checks website, privacy, support, license and legal notices in that order,
stopping on the first refusal. `onpc_about::read_help` and `open_from_help`
preserve consumed-entry proofs; `check_link` and `return_to_parent` preserve
wrong-entry refusal and unchanged Parent child/settings. The Parent GUI matrix
passed at display scales 1.0 and 1.25; host checks cover missing, disabled,
hidden, nonactionable, ambiguous and wrong-owner Help/legal controls without
activation. Website/privacy/support/license regressions passed in
`20260930T192205Z-9e64048b`, `20260930T192406Z-1fb5aa6f`,
`20260930T192605Z-cd5921c0` and `20260930T192803Z-ded12aaf`.
Collection, owned cleanup and baseline restoration passed. This qualifies the
Parent INFO01 binding only.

Historical E2E-042/parent-links case 190 used `parent_information.PLAN` and
`onpc_parent_about::run_links` for fresh Parent entry, Help, owned About,
all five link readers and About return through the shared operations above.
It captured Parent settings before information input and compared the
returned child, switch and allowance before its terminal reply. The retained
plan/worker now serve engineering checks only, with no registered E2E binding;
case 151 owns the customer information/return result. Host worker tests cover every stage refusal and
uncertain close without replay; controller tests exercise durable phase gates,
complete ordered observations and changed/missing settings refusal. Existing
unit/cleanup classifications remain applicable: private pytest storage,
bounded isolated Perl children, no VM, shared socket, bus or display changes.
Case 190 passed on Ubuntu 26.04 in `20260930T195316Z-5a8d360d`, including
public results, reconciliation, collection, owned cleanup and baseline
restoration. The other INFO01 surfaces remain separate unfinished scope.

The historical ABOUT03 link-only qualifier consumes the link observation,
confirms About remains open, reads ABOUT04's owned footer and closes only About
through UI18. The customer information return closes through
`onpc_about::close_information` without that additional footer read. The legacy
`license-closed` stage observes the same About; it sends no external close.
The final close reacquires Parent and reads its child, limit switch and
allowance without changing selection/settings.
`settings_checks={'parent-returned': 'parent-selected'}` compares immutable,
scenario-owned values before the terminal acknowledgement. Missing, changed,
stale or replayed observations fail, including after successful About input.

Qualification uses the actual [Perl worker](../../tests/unit/test_parent_about_worker.py),
[public adapter](../../tests/unit/test_accessible_e2e_ui.py),
[return comparison](../../tests/unit/test_parent_about_cleanup_safety.py),
[durable phase controller](../../tests/unit/test_installed_journey_cleanup_safety.py),
and [real GTK adapter](../../tests/ui/test_e2e_accessible_adapter.py).
Complete installed acceptance and cleanup remain the completion gate; run
references belong in retained runner artifacts and the implementation report.

## Parent discovery block contracts

The `parent-window` checkpoint separates successful launch from subsequent
picker input. Per-attempt evidence and outcomes remain in the runner artifacts.

Case **3 / E2E-003/existing-and-new** passed the complete current route through
`tools/run-tests e2e --id '3'` in run `20260923T183522Z-d4969e1e`
(outside runner retention).
The retained `parent_discovery.PLAN` and `onpc_parent_discovery::run` bindings
qualified fresh Parent entry, SEARCH05 launch, ID-owned existing/new-child
selection, FIX01 after unchanged initial settings, both pages and all four
immutable settings comparisons without reopening Parent. Private evidence
reconciliation, product, infrastructure, collection, owned cleanup and final
baseline restoration passed; coverage was regenerated. This closes retained
task 003r only; case 4's empty-account binding keeps its separate acceptance.

The [worker](../../tests/integration/graphical_smoke/lib/onpc_parent_discovery.pm)
composes FLOW15 and the explicit SEARCH05 discovery exception from
[onpc_parent.pm](../../tests/integration/graphical_smoke/lib/onpc_parent.pm),
then explicit page and child-selection checkpoints. Each selection consumes
its own current surface/choice proof before the canonical API setter; its
result independently verifies the intended child. Functional
GDM selects the intended account directly and retains two fresh recipient checks,
one secret input and independent desktop observation. Wrong-recipient rejection
is exercised separately in harness safety qualification. Its extracted UI19 leaf consumes the explicit final proof and
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

The empty-account recipe composes GDM07 and SEARCH06, consuming the explicit
fresh desktop observation before whole-query input. SEARCH06 stops at the
provider-resolved, independently focused launchable result. Search-field readiness,
focus and complete-query readback are separate checkpoints before that result.
A second fresh result-focus observation and the durable step-2
boundary precede FIX02; only its successful acknowledgement opens step-3 and
permits Enter. The worker consumes that acknowledgement before launch. FIX02
requires exactly the two canonical eligible children, preserves the request
station and refuses missing, substituted or additional accounts.
PARENT19 independently requires the showing explanation,
“No interactive non-administrator account was found.”, inside Parent and the
picker's sole showing `(None)` label. Disabled picker state remains readable;
no picker input occurs. Missing/hidden text, a selected child, stale or defunct
picker reads and failed fixture preparation refuse. Outer cleanup restores the
fixture. Neither discovery recipe changes time policy or claims child-login
enforcement.

Case **4 / E2E-003/none** passed its complete retained `parent_discovery.EMPTY_PLAN`
and `onpc_parent_discovery::run_none` route through `tools/run-tests e2e --id '4'`
in run `20260923T184507Z-a2d36b98` (outside runner retention).
The declared two-child FIX02 checkpoint, independent Parent explanation and sole
`(None)` picker observation, private evidence collection and owned cleanup passed.
Coverage was regenerated. This closes retained task 004r for the empty-account
binding; it does not qualify other SEARCH01–06 bindings.

The [adapter](../../tests/e2e/accessible_ui.py) exposes ID-scoped text reading,
complete API choice collection, selected values, settings,
page navigation and logical disclosure callables. All repository-owned targets,
including child-list rows, must be resolved by public ID before labels or states
verify their meaning. External Shell/GDM controls use the qualified provider
adapter. Local roots may be reused within one observation and are reacquired
after input or page transitions. The shared prompt guard uses one fresh,
complete scoped observation before input and refuses unexpected dialogs without
dismissing them. Prepared keyring Cancel remains separate harness qualification.
Missing/stale reads, ambiguous prompts and uncertain input still refuse. This keeps
installed-catalogue size from multiplying prompt scans without changing
observation deadlines or substituting appearance checks.

Qualification includes the actual [Perl discovery worker](../../tests/unit/test_parent_discovery_worker.py),
[GDM](../../tests/unit/test_e2e_gdm_helper.py) and
[secret helpers](../../tests/unit/test_e2e_secret_variables.py),
[public adapter regressions](../../tests/unit/test_accessible_e2e_ui.py),
[durable recorder/fixture safety](../../tests/unit/test_installed_journey_cleanup_safety.py),
and [real GTK/Shell adapter checks](../../tests/ui/test_e2e_accessible_adapter.py).
Independent offered-choice and immutable-observation tests cover reuse without
prior scenario execution; the empty-state block also accepts an independently
supplied Parent window. Failed/missing/stale/replayed observations prevent
further input, and uncertain whole-query input cannot be retried or reach FIX02.
Shared harness, access and About regressions preserve compatibility.

## Functional validation

Apply the canonical [UI automation mandate](../Mandates/UI-Automation-Mandate.MD).
Register each surface/control's shared ID contract before adding its consumer.
Missing repository-owned IDs require code changes exposing them through the
Application UI API. Supporting fixture controls require public IDs in their
shared activity adapters; external surfaces may use the approved provider exception.
Documentation records requirements and gaps; it does not qualify a route.
Do not dismiss unknown dialogs or bypass modal guards.

Both preview and guest readers use the shared
[Application UI API facade](../../tests/support/application_ui.py), with
application/owner pins, explicit surface scope, canonical values and bounded
inventory. Snapshot names/descriptions preserve translated accessibility-label
assertions. Rich-editor text, selection, document formatting and history use
the fixed packaged API; no caller JavaScript, arbitrary DOM, toolkit calls or
AT-SPI product-read/input fallback is allowed. Qualification exercises public
input/readback as well as identity discovery.

External provider gaps remain separate from the rich-editor adapter. The source mappings name logical consumer requirements, not IDs assigned by the
client. An ID route binds them to real provider-owned values; an exception route
records its actual selectors and qualification separately.

Repository-owned application fixtures have a separate implementation in
[gui_application.py](../../tests/fixtures/gui_application.py), with public
activity projections in [fixture_ui.py](../../tests/e2e/fixture_ui.py).
These supporting apps retain their existing shared activity adapter and public
IDs; they are not product Application UI API endpoints, and missing fixture IDs
must be fixed in fixture source rather than through the external-provider exception.
Native, Flatpak, Snap and game surfaces use
`onpc-fixture-<kind>-<instance>` IDs, where the scenario explicitly declares
`primary` or `secondary`; controls append `draft`, `edit`, `submit`, `submitted`,
`move`, `score`, `status` or `close`. Instance identity never comes from a title
or window order. Native owners retain their executable while their GUI child
runs, and close that owned child when terminated. The separately built
`mechanical/onpc-test-application` preserves the system suite's one-shot
readiness-marker contract. The explicit `--stay-alive` mode remains a headless
mechanical fixture, not GUI acceptance evidence.

The [builder](../../tests/fixtures/build_test_applications.py) packages a real
Python/GTK Flatpak runtime and a strict-confinement Snap payload using the
maintained host's runtime bytes. Full `setup.sh` and `--dependencies-only`
provide its build/runtime prerequisites. Host tests exercise native/game
payloads, an isolated user Flatpak installation and the unpacked Snap launcher.
The unpacked Snap test does not qualify snapd installation or confinement.
All installed app-filter consumers remain pending: public package installation,
allowed/denied launch, running-app closure, retention and each required launch
route still need their complete installed consumer. These are repository-owned
qualification tasks, not external-provider blockers.

### External-provider qualification

Only the necessary GUI routes recorded below are candidates for provider
qualification. Supporting Shell/GDM work uses shared system commands; completed
historical GUI tasks do not authorize retaining those routes. Product launch,
authentication and result observations retain their scoped qualification. Host doubles prove refusal and adapter mechanics, not installed qualification.
Legacy generic image, pointer and positional entry points remain retired; the
approved exception requires an explicit, qualified provider adapter rather than
restoring those generic routes.

Register mappings and adapter selectors in
[accessible_ui.py](../../tests/e2e/accessible_ui.py), with affected consumers and
installed qualification in the rows below. Follow the UI mandate's provider
exception. Missing IDs are an implementation gap, not a requirement to wait for
an upstream change. Qualification is limited to the exact scope recorded in a
row; retained ready scenario bindings do not broaden it.

For each supported route, qualify actual input/readback, application/surface
ownership, ambiguous and wrong-target refusal and the required independent
result. Qualify focus only when its input route requires keyboard delivery.
An independently supplied entry or lifetime transition can warrant another
qualification branch; an unchanged read or unrelated desktop tour cannot.
Secret routes additionally require intended-recipient and wrong-recipient refusal guards, empty masked field,
capture, single-use and uncertain-input checks. Refuse if those guards cannot be
established. Do not present semantic or visual selectors as provider-owned IDs.

| Provider / surface | Current gap and route-specific return condition | Affected consumers |
| --- | --- | --- |
| Chinese kiosk MATE Polkit agent | `mate_prompt(language='zh-Hans')`, `kiosk_mate_approval` and the shared Chinese request/approval fragments qualified by `check_e2e_chinese_native_auth` in `20261004T073743Z-9a030ef1`. Ubuntu 26.04, MATE `1.26.1-6`, actual locale `zh_CN.utf8`, keyboard `xkb/us`. Two fresh kiosk sessions passed actual Chinese system buttons/explanation/password label, exact Jamie/Jordan/75-second/soft-included context, fresh agent/challenge identities, same-challenge empty masked recipient guards, refusal projections, real approval, Chinese granted result and normal GDM return. The second entry retained Chinese without a chooser. Collection, worker shutdown, owned cleanup and restoration passed; required English regression passed in `20261004T075449Z-01e10e04`. [Qualified scope and callables](#chinese-language-preparation-and-desktop-language-setup). | Fixed Chinese AUTH01/AUTH02 and normal REQUEST11/12 ready; other tuples and task 300's complete history remain separate |
| External GNOME Shell desktop, app grid, sessions, notifications, lock | Shell `50.1-0ubuntu1.2` exposed no nonempty public IDs. On the pinned Ubuntu 26.04, English-GDM, baseline-keyboard image, `AccessibleUI.standard_shell_desktop(no_prompt=True)` qualified unique Activities control and complete prompt-free observations for the fresh Parent and standard fixture buses through `check_e2e_fresh_desktop`. `check_e2e_desktop_keyring` also qualified the independent standard desktop readback after the prepared gcr Cancel branch below. `AccessibleUI.shell_search_snapshot` qualified fresh Parent search, result focus and launched window in case 3 (run `20260922T212944Z-ad23b979`). The fresh Parent split-query/result-focus and Escape/empty-field/Super/dismissal slice passed `check_e2e_shell_search_results` in run `20260923T180845Z-4df4db55`. `check_e2e_shell_search` independently requalified administrator launch/close and standard-account split-query readback, exact web description and stable launcher/window absence in run `20260923T191129Z-64de2a7a`, with private collection and owned cleanup; see [exact scope](#search-and-standard-sign-in-contracts). Normal child panel launch and deliberate singleton activation with open-overlay reveal passed [overlay entry qualification](#overlay-entry-qualification). The product child panel now uses the Application UI API under DESK12/REQUEST13/PANEL01–03; its scope and retained evidence live in those product rows. Fresh Parent command/supplied-shortcut lock, curtain reveal and independent challenge observation passed on Shell `50.1-0ubuntu1.3`, `en_US.UTF-8`, `xkb/us`; see [lock scope and reports](#parent-lock-surface-qualification). Parent recipient proofs are qualified [separately](#parent-lock-recipient-qualification). Child command Lock, lock-screen recipient proofs, direct successful unlock and preserved-child desktop readback passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) on its exact Ubuntu/Fedora tuples. The configured-zero native child lock restriction and same-session greeter return passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification). Other lock bindings and retained-session observations remain unqualified. Session, power and connectivity inputs use shared system commands. | Fresh DESK01 Parent/standard and prepared standard gcr return, stated child DESK01/05–08 success and configured-zero native restriction bindings, Parent SEARCH01/02/03/04/05/06 and standard SEARCH01/03/04 branches ready; other necessary external DESK01/06–08 and SEARCH01–06 bindings retain their existing qualification scope; product panel operations are outside this provider row; DESK03–05, DESK11 locked-session return and LIFE02/03/06 inputs are system helpers; DESK10 uses the [qualified shortcut](#same-desktop-window-activation) |
| GDM greeter | Historical installed/product-free list, recipient and Escape qualification remains harness evidence. Shared customer entry selects only the intended account, verifies two fresh recipient proofs, delivers once and independently observes the desktop or product denial. `onpc_gdm::sign_in_challenge` qualified two distinct Parent GDM challenges with independent desktops and shared DESK04 logout through `check_e2e_challenges` (run `20260924T192200Z-c833e973`), on the pinned Ubuntu 26.04 English-GDM, baseline-keyboard image. Its separate wrong-recipient exercise, durable assertions, reconciliation, private collection and owned cleanup passed. The intended child's [fresh success](#fresh-child-success-qualification) and [specific zero-time denial with normal return](#fresh-child-time-denial-and-return-qualification) are qualified on their recorded provider tuple. Wrong-account tours and keyring exercises remain harness-only. Retained-child GDM reauthentication success and the bounded fresh-child denied-prompt return passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) on its exact Ubuntu/Fedora tuples. GDM authenticates before activating the retained desktop; these proofs never authorize lock-screen input. Configured-zero retained-child authenticated time denial and guarded account-list return passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification). Other challenge recipients and new account bindings remain pending. | GDM01–03/05–09 for unavoidable graphical entry; distinct Parent, fresh child success/zero-time denial with rejected-GDM return and retained-child GDM reauthentication success/time-denial ready; GDM04 harness safety only |
| Graphical VT6 getty/login | Retained routes refuse before image, secret or input access. Qualify a dedicated recipient/input adapter; serial proof cannot authorize graphical secret input. | Retained VT6 qualification modes |
| MATE Polkit agent | `AccessibleUI.mate_prompt`, `mate_prompt_refusals`, `kiosk_mate_cancel` and `mate_prompt.PLAN` qualified REQUEST09/AUTH01's fixed kiosk binding through `check_e2e_auth_prompt` in run `20260926T064045Z-b4159145`. Recorded tuple: Ubuntu 26.04, mate-polkit `1.26.1-6`, actual provider locale `en_US.UTF-8`, keyboard sources `[["xkb", "us"]]` (system configuration when the kiosk per-user list is empty). The semantic adapter binds the kiosk agent service PID, unique live dialog, English PAM recipient label, exact displayed child/75-second/soft-app request, sole empty masked focused field and enabled Cancel. Two independent deliberate requests each passed fresh same-challenge reacquisition, one Cancel, independent disappearance and usable unchanged no-error form return. The controller records distinct single-use challenge IDs; these are evidence, never secret-delivery authority. Parent wrong-entry and projected wrong-provider/owner/parent/child/duration/apps, multiple/hidden/disabled/unfocused/nonempty/stale-field and replaced-challenge refusals passed. The same run passed enabled invalid `abc` submission, exact validation and no prompt; unavailable entry retained disabled Request. Private collection, owned cleanup and baseline restoration passed. No geometry, invented provider IDs, password submission or complete-scenario credit. Source discovery: upstream [dialog](https://github.com/mate-desktop/mate-polkit/blob/master/src/polkitmateauthenticationdialog.c) and [PAM recipient label](https://github.com/mate-desktop/mate-polkit/blob/master/src/polkitmateauthenticator.c). Missing displayed context refuses; broker state cannot replace it. Task 020a separately qualified the fixed correct-password submission and automatic approved exit in `20260926T065928Z-8c15b645`; see [kiosk approval](#kiosk-approval-qualification) for callables and limits. Task 020b separately qualified wrong-password rejection and password-free Cancel with preserved form in report run `20260926T154532Z-4ed66f34`; see [kiosk rejection](#kiosk-rejection-qualification). Other tuples and broader secret routes remain unqualified. | Fixed kiosk REQUEST09/AUTH01 proof/Cancel and AUTH02 correct-password approval with REQUEST11/12 automatic exit ready; rejection/Cancel ready; immediate approved exit ready through task 020's owned result action and independent GDM read |
| Shell Polkit agent | `AccessibleUI.shell_prompt_owner`, `shell_prompt`, `shell_prompt_refusals` and `overlay_shell_cancel_ready` qualified the fixed child-overlay request through `overlay_prompt.PLAN` / `check_e2e_overlay_prompt` in `20261003T194901Z-f8ac692b`: two separate attempts, displayed parent/child/75-second/soft-app context, sole empty masked focused field, fresh same-challenge recheck, refusal matrix, one normal Escape/Cancel and independent unchanged usable no-error form. Tuple: Ubuntu 26.04, Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, `xkb/us`. Collection, worker shutdown, callback closure, owned cleanup, baseline restoration, finalization and host/source preservation passed; affected MATE approval regression passed in `20261003T195605Z-9520133b`. See [scope](#overlay-shell-prompt-and-cancel-qualification). Fixed correct-password input, explicit child-owned success and automatic original-activity return passed `check_e2e_overlay_approved_exit` in `20261003T200552Z-980e4691`; see [overlay approval](#overlay-approval-and-automatic-return-qualification). Fixed wrong-password rejection and an independent fresh password-free Cancel passed `check_e2e_overlay_rejection` in `20261008T050819Z-ffdb973c` on Shell `50.1-0ubuntu1.3`, `en_US.UTF-8`, `xkb/us`, with preserved usable no-error choices, sealed capture, collection and owned cleanup. Approval/automatic original-activity return passed on that tuple in `20261008T051602Z-bcc96b27`; affected kiosk rejection passed in `20261008T052150Z-8cb6735d`. See [rejection scope](#overlay-rejection-and-cancel-qualification). Immediate approved exit, other tuples and complete scenarios remain separate. Supporting package/account commands do not require an unrelated GUI challenge. | Fixed overlay AUTH01/REQUEST09 proof and password-free Cancel/preserved REQUEST11 ready; fixed AUTH02 approval/rejection and REQUEST11/12 automatic approved return ready; other bindings pending |
| gcr keyring prompt | `AccessibleUI.keyring_cancel_target` / `cancel_keyring_prompt` qualified the prepared standard-account login-keyring Cancel route through `check_e2e_desktop_keyring` (run `20260923T051904Z-f0d79b4d`, outside runner retention). Recorded tuple: Ubuntu 26.04, gcr `3.41.2-6`, Shell `50.1-0ubuntu1.2`, actual gcr locale `en_US.UTF-8`, keyboard sources `[["xkb", "us"]]`. The semantic adapter requires a unique live gcr application owner, visible Login Keyring dialog, sole empty masked focused field and unique enabled Cancel; the application container itself has no visibility requirement. It invokes Cancel once, observes disappearance and independently observes a prompt-free desktop for two seconds. Host regressions reject wrong/ambiguous ownership, hidden/disabled input, lost focus, replacement/queued prompts, incomplete absence and uncertain input. Preparation activates installed `PrivatePrompter`, verifies its ownership of `SystemPrompter`, and locks/requests unlock of the existing Login collection through Secret Service without reading or supplying a password. Separate fresh Parent and standard attempts passed private collection, reconciliation and owned cleanup. Other locales, provider tuples, Parent keyring cancellation and automatic search-middleware composition remain unqualified. | Prepared standard DESK01 gcr Cancel return ready; other keyring handling and secret routes pending |
| GTK native file chooser | Qualify each caller-owned dialog route, exact selected-file readback and wrong-dialog refusal. | FILE03, FEED06, FEED08 native routes |
| GNOME portal / Nautilus chooser | `chooser_snapshot` binds the unique active modal and provider controls; `validate_chooser_portal_owner` binds the sole live delegated request to feedback through public D-Bus ownership and Request introspection. Missing/ambiguous/replaced requests and contradictory explicit relations refuse. Imported Wayland parents lack GTK `CONTROLLED_BY`; see [Nautilus](https://github.com/GNOME/nautilus/blob/50.0/src/nautilus-portal.c) and the [public caller-path contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Request.html). Cancellation uses scoped Close; native GTK retains Cancel. Current `button` and legacy `push button` roles are supported. The [attachment handoff](#attachment-chooser-handoff) qualified two-file Open/Cancel in `20260927T161010Z-7e6515c9` on `1:50.2.2-0ubuntu0.1`; Open/Cancel regression passed in `20260929T191829Z-3d1fd72a` on `1:50.2.2-0ubuntu0.2`, both `en_US.UTF-8`, `xkb/us`. Case 155's Cancel/unwritable-save/recovery passed in `20260929T203255Z-29d6637e`; named Save/Cancel and export qualifications passed in `20260929T203754Z-7b47ee7e` and `20260929T204158Z-388a25b4` on `1:50.2.2-0ubuntu0.2`, `en_US.UTF-8`, `xkb/us`, caller `parent-feedback`, with collection, owned cleanup and baseline restoration. Save restores the collapsed filename through scoped `filename_label` before exact-name proof and real Save. | fixed Parent Open/Cancel, named Save/Cancel, fixed unwritable save-error/recovery and FEED08 export ready; other profiles/tuples pending |
| Supporting document viewer | `license_viewer_snapshot` and `check_e2e_license_viewer` qualified Parent's actual GNOME Text Editor handler in run `20260923T201618Z-50520052`: Ubuntu 26.04, editor `50.1-0ubuntu0.1`, actual provider locale `en_US.UTF-8`, keyboard sources `[["xkb", "us"]]`. Live independent entry, wrong-entry/unrelated/empty content refusal, ambiguous viewer/close refusal, bounded GPL headings, active viewer, normal close/absence, owned About/footer and unchanged Parent settings passed with private collection and owned cleanup. Wrong ownership, masked/hidden content, incomplete trees and uncertain input also retain host regressions. DESK10 additionally qualified shared command launch of the installed LICENSE and repeated existing-window activation on the same tuple; see [scope and evidence](#same-desktop-window-activation). This historical viewer qualification now supports DESK10 only; link acceptance uses the owned clickable-link reader and never invokes a handler. Other supporting document workflows remain pending. | DESK10 supporting GPL viewer binding ready; ABOUT02/03 and INFO01 need no external provider. FILE08/FEED08 artifact reads require no viewer |
| Terminal | Retired as supporting infrastructure. Shared FILE01/02/06 execute fixed commands over guarded SSH; INFO02 already reads bounded stdout. Historical Ptyxis qualification creates no customer requirement or provider dependency. | No Terminal GUI consumers |
| GNOME Settings Users / Date & Time | Retired provider work. Use protected spare-account commands and read-only date/timezone commands in shared infrastructure. Observe the app refresh/fallback and time behavior independently. | ACCOUNT01/02, AUTH04 and TIME05 system helpers |
| DING desktop icons | No provider registry route exists. Qualify the declared desktop icon, focus/selection, activation and independent launched-window result inside a DING-specific adapter. | APP01/02 desktop launch route |
| Nautilus Files | Qualify only the explicitly tested file-manager enforcement launch. Shared commands prepare, copy, rename and open supporting files; product file choosers retain their separate GUI assertions. | FILE04 and declared APP01/02 file-manager launch routes |
| File Roller archive viewer | No current GUI consumer. Inspect declared customer-exported ZIPs through FILE08's shared bounded archive API over SSH. | FILE08 synthetic ZIP and FEED08 fixed product-export readers ready; no archive-viewer route required |
| Registered document editor | Use a shared direct handler launch only for an explicitly tested information/preview integration or retained-work activity. Ordinary attachment source mutation and exported text reads use shared FILE05/08/09 commands; GUI edit/save is limited to declared retained-work assertions. | FILE08 work binding and APP03/04 retained work; information/preview bindings under their own blocks; no FEED08 viewer dependency |
| Lunar Client, AppImageLauncher, Shell tray and Minecraft | No bindings are qualified. Require the prepared real-AppImage profile, allowed autostart control, complete login-interval tray/window observations, specific same-route denial, game launch/local-world action and genuine Quit. [Preparation and observation gate](#lunar-client-preparation-and-observation-gate); refuse incomplete ownership/absence observations. | E2E-052/case 253; APP01/02/03/06, UI18/22 and FIX05 |

Provider implementation and qualification are scheduled only by the
[E2E execution plan](E2E-Execution-Plan.md). Its queue places the following
capabilities before their consumers; these are task identifiers, not readiness
claims or an alternate execution order:

| Provider work | Queue owners |
| --- | --- |
| Necessary GDM entry, isolated keyring safety and system session helpers | 003a/003ba unavoidable login observations; 003b isolated keyring qualification; 003c/003d shared system operations; case 1 remains harness qualification |
| Product search, direct launch and owned license link | 001s product search; 001t direct-command denial; historical 185l scope now follows ABOUT02/03 link-only acceptance; retained scenario regressions |
| Kiosk MATE prompt and request results | 019a, 019, 020a, 020; 300f Chinese native binding |
| Overlay Shell prompt and request results | 048c, 048d, 048b |
| Shared file preparation and tested file-manager launch | 036 shared file preparation; 036f/036a explicitly tested file-manager enforcement launches |
| Installed feedback Open/Cancel, with its actual native/portal provider binding | 037; attachment composition 038 |
| Installed feedback Save/Cancel, with its actual native/portal provider binding | 037a; export composition 045 |
| Shared text/ZIP artifact reads and source edits; separately observed retained work | 195a/195 SSH artifact readers; 196 source-change commands and separately qualified work binding |
| Owned information-link clickability; no browser/mail/legal provider work | 185w, 185v, 185s, 185p and overlay 185oa/185ob/185o |
| Shared system lifecycle helpers and required unlock observations | 005/006 package commands, 007 reboot command, 042/043a necessary lock/unlock observation, 044a shared window activation, 193 network command, 166 suspend command |
| DING desktop fixture launch | 036b |
| System account and clock helpers | 184/184b/184c shared account operations; 191 read-only clock/timezone commands |
| Snap, Flatpak and game baseline preparation and restored-input verification | 109p → 109/109a; 116p → 116/116a; 126p → 126a |
| Reviewed external feedback submissions | 150a profile/authorization → 150 and its surface/result consumers |
| Lunar, Minecraft and login observation | Tasks 295–297 and their split prerequisites under the [canonical queue](E2E-Task-Queue.md); operation scopes stay in the [profile contract](#lunar-client-preparation-and-observation-gate) |

There is no active customer requirement for generic Shell notification handling,
an archive/text/PDF viewer for diagnostic export inspection, or graphical VT6 login.
Those surfaces remain unqualified; they supply no acceptance credit and have no
speculative implementation tasks. Chooser tasks qualify the actual Gtk.FileDialog
caller; they do not force an unused backend or introduce a compatibility matrix.
Case 1 retains its real authenticated serial
journey and public GDM return. A future named consumer needs an explicit scoped
prerequisite in the same queue before using any additional surface.

Case 1's product-free GDM route uses the explicit
`gdm_product_free_account()` / `gdm_product_free_navigation()` fixture binding.
The fixed `check_e2e_gdm_product_free` qualification passed two independent
Parent list/focus/prompt/Escape-return cycles with collection and owned cleanup.
The installed `gdm_nonsecret_account()` binding retains its station cardinality
checks. Retained case 1 now binds every graphical stage to the product-free
operations and passed its complete graphical/serial route, reconciliation,
collection and cleanup. The shared migration audit reran complete case 1 in
`20260923T202714Z-fc680b74`, including authenticated serial input, observed command
output, logout-before-return and suite baseline restoration.

### Product-free Parent entry and command context

`check_e2e_product_free_entry` passed in run `20260924T203125Z-f94d7c37` on
the accepted Ubuntu 26.04 product-free baseline. `ProductFreeEntryQualification`
uses FIX04 without installing or rebooting the product; `InstalledJourney`
requires exclusive setup modes and a matching booted transfer receipt.
`ProductFreeEntryJourney` and `onpc_product_free_entry::run` reuse minimal Parent
login, two fresh recipient proofs and single-use secret input, then independently
observe the Parent desktop. The separate greeter entry proves command-context
refusal. `session_control.execute('parent-command-context')` binds the active
local unlocked Parent session, drops to that account, verifies administrator
group authority and reads the protected staged package. The journey requires its
digest to match verified input provenance before acknowledging the result.

Durable `provider` observations at `installed-greeter` and `desktop` qualify
GDM `50.1-0ubuntu0.1` and Shell `50.1-0ubuntu1.2`, with actual provider-process
locale `en_US.UTF-8` and keyboard sources `[["xkb", "us"]]` on both surfaces.
The greeter reader uses public locale1 `X11Layout`/`X11Variant`; the desktop
reader uses account GSettings. Missing or malformed metadata refuses without
synthesizing a default layout. Support is limited to these observed tuples and
this route; other provider bindings retain their separate qualification.

The run passed all three capability assertions, capture reconciliation, private
collection, owned worker cleanup and baseline restoration. The durable
after-cleanup result is
`output/test-runs/privileged/allocations/onpc-e2e-evidence-liy0bxsc/event-000016.json`;
the report is `output/test-runs/host/reports/20260924T203125Z-f94d7c37/report.md`.
Package execution/notice and installation composition have their separate
qualifications below; complete case 2 is qualified [separately](#clean-installation-journey). This qualification
supplies no complete-scenario credit.

The affected one-package regression passed again on every enabled VM (Ubuntu
26.04) in `20261003T234636Z-cd0eba55`, with GDM `50.1-0ubuntu0.1`, Shell
`50.1-0ubuntu1.3`, `en_US.UTF-8` and `xkb/us`. All entry/context assertions,
collection, worker shutdown, callback closure, owned cleanup, baseline restoration
and host/source preservation passed. The dual-package scope is qualified
[separately](#verified-upgrade-asset-transfer).

### Administrator package command and output

`check_e2e_package_authority` passed in run `20260924T215601Z-8f5800a9`
on the product-free Ubuntu 26.04 baseline. `PackageAuthorityQualification`,
`PackageAuthorityJourney` and `onpc_package_authority::run` reuse the qualified
product-free entry and FIX04 transfer. The shared leaves are in
[`package_command.py`](../../tests/e2e/package_command.py):

- `PackageCommand.validate_input` binds the fixed `install-staged-package`
  command, verified package digest and transport VM/attempt identity.
- `submit` and `guest_submit` recheck the active unlocked local Parent
  administrator and immutable staged bytes before one fixed APT invocation.
  APT may fetch runtime dependencies; an empty baseline need not cache them.
  Host consumption and an exclusive guest marker prevent replay after uncertain
  input. The guarded transport supplies system authority; no Terminal or
  unrelated password prompt is involved.
- `read_result` runs at a separate checkpoint, rechecks attempt/provenance,
  and requires exit status zero, the actual package completion line and the
  actual reboot notice as the last output line. Combined stdout/stderr is
  bounded to 1 MiB with a 660-second command deadline; raw diagnostics remain
  private and shared evidence contains only the matched public lines.

Fedora's current-package bindings use the
[native output contract](../Fedora-Packaging.md#fedora-lifecycle): the exact
verified package's completed `%posttrans` or `%postun` scriptlet must end with
the literal reboot notice, ignoring trailing empty scriptlet lines. DNF framing
and its later transaction messages may follow. Exit status and independent
installed-version/absence checks remain required. Packaged purge reads its own
completion and reminder after DNF returns.

The live slice proved greeter refusal, independent valid administrator entry,
unregistered-command/wrong-artifact/wrong-VM/wrong-attempt/replay refusals,
successful command completion and the final reboot notice. Capture
reconciliation, private collection, owned worker shutdown, baseline restoration
and lease completion passed. The durable after-cleanup result is
`output/test-runs/privileged/allocations/onpc-e2e-evidence-1kzlp7dr/event-000017.json`;
the report is `output/test-runs/host/reports/20260924T215601Z-8f5800a9/report.md`.
This capability qualification records its three assertions; the envelope's
complete-product result is `not-run`. LIFE04 installation composition is qualified
separately below; other package operations remain pending. Complete case 2 uses
the [continuous customer journey](#clean-installation-journey).

### Customer package install composition

`check_e2e_package_command` passed in run `20260924T221715Z-9ebb5329` on a
fresh product-free Ubuntu 26.04 attempt. `PackageInstallQualification`,
[`PackageInstallJourney`](../../tests/e2e/package_install.py) and
`onpc_package_install::run` compose the qualified entry and command leaves.
Reusable `submit_install` binds the verified package to one administrator
submission and retains the consumed command on uncertain failure;
`observe_install` independently reads successful completion and the actual final
reboot-required line at a later checkpoint, before durable acknowledgement.

The slice passed greeter refusal, fresh Parent login and desktop readback,
administrator authority, one real installation, completion/final notice,
capture reconciliation, private collection, owned worker shutdown and baseline
restoration. The durable after-cleanup record is
`output/test-runs/privileged/allocations/onpc-e2e-evidence-8xqbpjt2/event-000017.json`;
the report is `output/test-runs/host/reports/20260924T221715Z-9ebb5329/report.md`.
Its three capability assertions passed; the complete-product result remains
`not-run`. Reboot continuity is qualified below; update/remove/reinstall/purge
remain unfinished; complete case 2 is qualified [below](#clean-installation-journey).

### Genuine unrelated-package reboot request

`check_e2e_unrelated_reboot_request` qualified task 305a on Ubuntu 26.04 in
`20261008T031925Z-f3d2d6e5`, with all seven assertions. The shared
`package_install.submit_unrelated` / `observe_unrelated` operations use
`PackageCommand`\'s finite `reconfigure-unrelated-libc6` binding;
`unrelated_reboot.UnrelatedRebootJourney` / `PLAN` and
`onpc_customer_reboot::unrelated_request` compose the qualification.

The input is the already installed Ubuntu `libc6:amd64` **2.43-2ubuntu2.4**,
source `glibc`, archive SHA256
`a613b457f3ff9c84ebd28af8a05afdec22605ad9aed87c71e3a6ae5170aeb9ca`, filename
`pool/main/g/glibc/libc6_2.43-2ubuntu2.4_amd64.deb`. Its fixed normal command is
`/usr/sbin/dpkg-reconfigure --frontend=noninteractive libc6:amd64`.
`installation_observations.UNRELATED_PACKAGE` / `UNRELATED_SCRIPTS` bind
repository provenance, installed payload integrity, maintainer/command bytes
and absent alternative scripts. These distribution dependencies have baseline
lifetime; the deliberate reconfiguration remains attempt-owned. No package
download/install, synthetic package, manual reboot marker or direct notifier
invocation supplies this input.

Entry requires genuine product installation and observed activation reboot,
fresh administrator return, exact unrelated-package identity/integration, and
no system/product reboot request. Submission retains consumed input and refuses
unregistered command, wrong digest, VM, attempt and replay. The separate result
requires exit zero and the actual `Processing triggers for systemd (…) ...`
completion from libc6\'s normal `libc-upgrade` trigger. The pinned postinst\'s
`Nothing to restart.` branch applies only to previous versions below 2.43;
it is not this same-version command\'s completion. Independently read the genuine
`*** System restart required ***` message attributed to `libc6`, absent product
requests, and unchanged product identity, boot, session and preservation witnesses
before acknowledging the result.

Collection, title reconciliation, worker shutdown/callback closure, owned cleanup,
baseline restoration, lease completion, finalization and host/source preservation
passed. Historical qualification run `20261008T031925Z-f3d2d6e5` has had its
report rotated by normal retention. Its original worker evidence was
`output/test-runs/privileged/allocations/onpc-graphical-smoke-q427m766/result.json`
with the after-cleanup record
`output/test-runs/privileged/allocations/onpc-e2e-evidence-awkav_ee/event-000030.json`.
Affected `check_e2e_package_command` (`20261008T032451Z-e5adea37`, three assertions)
and `check_e2e_customer_reboot` (`20261008T032801Z-219b3d94`, five assertions)
regressions passed the same collection/cleanup/preservation boundaries on the
selected Ubuntu VM. This qualifies only the finite LIFE04 supporting operation
and system result. No complete-case acceptance is claimed. Other package bindings remain pending.

### Genuine package upgrade

`check_e2e_package_upgrade` qualified the finite genuine v1.2-to-current update
on every enabled VM (Ubuntu 26.04, amd64) in `20261004T002735Z-d4779228`.
`PackageCommand` preserves `install-staged-package` and adds finite
`install-previous-release` / `upgrade-staged-package` identities, separate
consumption markers, immutable dual-package validation, public phase guards and
package-version/preservation readback. An uncertain submission remains consumed
across command objects; the upgrade requires the independently activated old
release and its changed boot. The authentic previous release's completion is
checked against its own output contract rather than a current-only notice rule.
`PackageUpgradeJourney`, `submit_release` / `observe_release` and
`onpc_customer_reboot::install_entry` / `return_entry` compose the authentic
`1.2+ppa1~ubuntu26.04.1` installation, activation reboot and one upgrade to
`1.3+ppa1~ubuntu26.04.1`. Independent repeated readback established actual
successful completion, the final reboot-required notice and the unchanged boot
after upgrade. Wrong-entry/attempt/VM/artifact/phase and replay refusals,
account/language/session/unrelated-file and immutable-input preservation passed.
The optional static `/etc/motd` witness records absence explicitly; later
creation, removal or content change still fails preservation. Missing required
files and other read errors refuse. Host regressions exercise the actual decoder,
recorder/worker sequence, nondefault package identity and consumed uncertainty.

The affected current-only `check_e2e_customer_reboot` regression passed on every
enabled VM in `20261004T003258Z-f006d805`. Both runs passed capture reconciliation,
private collection, worker shutdown, callback closure, owned cleanup, baseline
restoration, finalization and host/source preservation. The upgrade after-cleanup
record is `output/test-runs/privileged/allocations/onpc-e2e-evidence-njbxci0w/event-000032.json`;
The historical live report was `20261004T002735Z-d4779228`; its bounded retention
has expired. Task 300e's package-upgrade regression passed in
`20261004T024908Z-8d5137eb`; its report is retained at
`output/test-runs/host/exports/onpc-artifact-export-v2s6wi_5/report.md`.
The recorded provider tuple is GDM `50.1-0ubuntu0.1`, Shell `50.1-0ubuntu1.3`,
`en_US.UTF-8`, `xkb/us`. This supplies the package operation, not Chinese initial
UI, post-upgrade reboot composition, native authentication or complete-case credit.

### Customer reboot continuity

`check_e2e_customer_reboot` passed in run `20260924T223309Z-4d98a4b2`.
[`CustomerRebootJourney`](../../tests/e2e/customer_reboot.py),
`CustomerRebootQualification` and `onpc_customer_reboot::run` reuse the fresh
LIFE04 install composition, completion and final reboot notice in one attempt.
The slice refused reboot outside its declared entry, submitted one fixed
`systemctl --no-ask-password reboot` through guarded SSH on the pinned old boot,
independently observed a changed boot and fresh usable GDM, then reached the
administrator desktop using the shared `after-reboot` graphical challenge and
two fresh recipient proofs. No in-journey baseline restore occurs.

`JourneyPlan.reboot_transition` names adjacent command-context and `ui:gdm-list`
checkpoints. `InstalledJourney.submit_reboot` records a durable intent before
submission and consumes the action even if its result is uncertain. The result
checkpoint uses `ReadOnlyObservations.wait_boot_change`, retains the same VM and
transport identity, and discards pre-reboot UI state. Unexpected, repeated or
additional boot changes refuse; command success alone cannot satisfy the result.
The shared wait remains bounded at 330 seconds, followed by the existing GDM
observation budget, within the worker's 780-second reboot-result checkpoint.

Qualification used Ubuntu 26.04, GDM `50.1-0ubuntu0.1`, Shell
`50.1-0ubuntu1.2`, provider locale `en_US.UTF-8` and `xkb/us`. All five capability
assertions, capture reconciliation, private collection, owned worker shutdown
and baseline restoration passed. The after-cleanup record is
`output/test-runs/privileged/allocations/onpc-e2e-evidence-hjzm4rb7/event-000025.json`;
the report is `output/test-runs/host/reports/20260924T223309Z-4d98a4b2/report.md`.
Host coverage is in `test_customer_reboot_cleanup_safety.py`,
`test_installed_journey_cleanup_safety.py`, `test_vm_transport.py` and the shared
observation/authentication/worker safety suites. This qualifies the fresh
install/reboot/administrator-return slice; other lifecycle bindings remain
pending, and this capability's complete-product result is `not-run`.

### Clean installation journey

`tests/e2e/clean_install.py::clean` and `onpc_clean_install::run` compose LIFE04,
LIFE02, fresh Parent defaults, complete Allowed app rows and station entry/Cancel
in one product-free attempt. The shared
[`record_package_journey`](../../tests/e2e/package_journey.py) binds asset staging
and LIFE04 input to `record_installed_journey`; the case contains only its plan,
checks and callback. [`journey_checks`](../../tests/e2e/journey_checks.py) supplies
the independent account read and Allowed-row comparison, also reused by app-row
qualification. Package completion uses `package_install.check_install_result`.
`gdm-installed-accounts` uses the scoped GDM semantic snapshot to require all four
fixture personal accounts and the station, without unrelated navigation. It
rejects missing, duplicate, disabled, wrong-owner and incomplete observations.
`onpc_parent::launch` can consume the fresh `reboot-desktop` proof; its default
fresh-desktop binding is unchanged. No in-journey snapshot restore occurs.

Complete case 2 passed `tools/run-tests e2e --id '2'` in run
`20260925T033902Z-25077d1e` after the shared-envelope extraction, including both customer assertions, capture
reconciliation, collection, owned cleanup and baseline restoration. The attempt
evidence is `output/test-runs/privileged/allocations/onpc-e2e-evidence-tt8yep8a`.
The affected case 6 Parent-launch regression passed in
`20260924T234847Z-41112953` with the same terminal gates. Coverage was regenerated
after each case. Host refusal/composition coverage is in
`test_clean_install_cleanup_safety.py`, alongside the shared controller, reboot,
public accessibility, app-row, inventory and worker tests. This qualifies the
pinned Ubuntu 26.04 English-GDM fixture route; other lifecycle/provider bindings
retain their own acceptance requirements.

### Reachability and result checks

Resolve product targets through the shared Application UI API facade, pinning
the current application owner and explicit surface. Use canonical setters,
normal actions and independent fresh result reads. Logical disclosure may be
required for hidden content, but clipping and foreground focus do not affect
identity or require native input. Hidden, disabled, detached, busy or modal-blocked
controls refuse. An API failure never selects a different input route.

External adapters retain their qualified provider resolution, complete scoped
prompt/ownership observations, and recipient focus when their input requires it.
No snapshot survives input or a session transition. A following result
observation is fresh and independent of input completion.

Do not call private product methods, mutate toolkit widgets directly, read saved policy or
treat the Application UI API's success as the customer result. Disabled settings remain
readable. Screenshots have no cosmetic pass/fail authority; an external image
selector must stay inside its explicitly qualified provider adapter.

Examples:

- Set the child selector's canonical UID and verify the selected child and
  usable settings independently.
- Toggle a time limit, verify its UI state and exercise the affected child's
  normal login/session behavior. Reopen settings when persistence is required.
  An illuminated switch alone cannot prove enforcement.
- Identify the installed product/version in About, then resume the same
  management task or unfinished request. One visit and the preserved customer
  state establish this result; the link-control matrix belongs in UI tests.
  No external handler is needed.

For required text, assert meaning-bearing content on a showing public UI node,
not its line breaks, font or coordinates. Missing controls, wrong selection,
inaccessible required information, ineffective settings,
timeouts and crashes remain failures. Keep a failed journey failed; no fallback
that silently skips an assertion or directly applies the requested setting.

The shared [UI adapter](../../tests/e2e/accessible_ui.py) uses bounded
fresh API lookups and operations. [UiObservations](../../tests/e2e/ui_observations.py)
runs it as the fixed fixture user or qualified greeter inside the guarded VM transport, accepts
only registered operations, and returns sanitized semantic screen evidence.
No raw accessibility trees, document bodies or account names enter reports.
For external providers, use explicitly qualified interface methods when GI method names collide, such
as `Atspi.Text.get_text(text, start, end)`, rather than the different
`Accessible.get_text` accessor. Read-only lookups may retry stale objects within
their deadline; never replay an action whose effect is uncertain.
`standard_shell_desktop` discards a traversal containing any defunct node as an
incomplete read, then reacquires within that same deadline. Persistent stale
state still refuses; a prompt-free stability interval restarts after a failed
read. This covers application closure before same-user Parent reopening without
using stale state as desktop or prompt-absence evidence.
External-provider waits also dispatch a bounded batch of pending public
accessibility events before each read, so queued focus/text/registry changes can
be delivered. Product waits reacquire API observations under the same deadline.
Functional station and desktop waits share
`AccessibleUI.handle_system_prompt`. Before a surrounding public observation or
input, one complete tree read classifies visible MATE Polkit, Shell Polkit,
gcr-keyring and unknown authentication modals through a provider's available
application/surface IDs or its scoped semantic adapter. Every classified prompt
is refused without reading a secret, authenticating, dismissing the dialog or
delivering any action. Ambiguous and incomplete reads also refuse. A no-prompt
result is meaningful only when the operation then obtains its complete positive
station or desktop observation; missing full prompt ID maps do not preflight-fail
that observation. GDM credential checkpoints are outside this middleware.
The old `UiObservations`/`InstalledJourney`/`service_system_prompt`/
`click_target` coordinate rendezvous still cannot dispatch: coordinate
production and controller payload handling are removed, and retained worker
entry points refuse before acknowledgement/input. Provider input remains
pending its own task and installed qualification.
The [real GTK adapter checks](../../tests/ui/test_e2e_accessible_adapter.py)
exercise selection, disabled-setting reads, About and footer access at 100%
and 125% display scale. These are examples, not an allowed-scale list or proof of
resolution independence. These are adapter qualification; the installed case
still must pass its whole guarded journey.
Product operations follow the [Application UI API](Application-UI-API.md);
external provider access uses upstream [AT-SPI](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/class.Accessible.html).
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

Case **3 / E2E-003/existing-and-new** reuses this contract for app search,
existing-child selection, dynamic discovery and return. Preserve the original
existing fixture's limits-off/zero-allowance expectation and the new child's
visible remaining-time section. The fixed account fixture
runs only after fresh visible settings and a durable phase boundary while Parent
stays open. The shared selector setter checks its owning surface and offered
UID; the case verifies the intended child's displayed settings. Popup state
and highlighted rendering do not add customer assertions.
Both children expose App Limits search and rule-filter controls through normal
tab navigation. Returning to Screen Limits and the original child must preserve
their independently recorded switch and allowance values, including disabled
allowance reads. This case changes no time policy and claims no child-session
enforcement; E2E-005 owns settings changes followed by child use.

Case 3 uses the shared minimal GDM entry for the intended parent. Deliberately
selecting another parent and refusing that recipient is separate harness
qualification, not a step in this customer journey. The secret helper
requires two consecutive fresh controller acknowledgements of the exact account
label, hidden account list, sole showing/enabled/focused `password text` role and
zero character count. It reads no password contents. The second acknowledgement
immediately precedes the existing `type_password` API with fixed secret options.
Wrong order/identity, nonempty or unmasked fields, review mode, uncertain typing,
capture and replay refuse. The active local greeter and owned session socket
retain ownership guards; replace legacy appearance gates with semantic recipient
proofs without weakening credential safety.

Case **1 / E2E-001/gdm-observation** uses the same `ui:` checkpoints for
GDM account selection, the intended account's focused password prompt, Escape
dismissal and fresh graphical return after serial logout. The adapter connects
as the sole active local greeter for these registered operations only. Public
logind metadata resolves its current account, including dynamic GDM accounts;
the owned runtime/session socket is validated before dropping privileges. No
graphical password is submitted or authorized by this observation contract.
When account rows expose no public action, use UI14's qualified provider
keyboard navigation, verify the intended button's focus, press
Enter and independently verify the selected account's prompt. This external GDM
worker uses `onpc_journey::navigate_choice` to validate navigation replies;
product Parent selectors use UI15's canonical API values without keyboard navigation.
Its real serial authentication, command-output, session/boot, asset and cleanup
checks remain harness qualification, with no customer feature coverage credit.
The shared reconciler requires fresh controller results for each ordered worker
marker, and case 1 additionally requires logout before graphical return.

### Station branch diagnosis and default-entry scope

The kiosk qualification's `station-branch` checkpoint calls
`AccessibleUI.station_entry_branch` after the freshly focused station row is
submitted once. This is a read-only branch diagnosis, not UI15 session selection or
REQUEST01/03 qualification. Active local seat/session metadata binds the observer
to the sole greeter or dedicated station account; another account or ambiguous
owner refuses. Metadata alone cannot establish the destination.

On the greeter, the adapter requires the station recipient and no password
field, then reports at most twelve showing public controls as sanitized label
categories, roles, ID-presence flags, sensitivity and focus. Unknown labels stay
`unresolved`; duplicate known categories refuse. The English label mapping is
only a diagnostic candidate, without an installed version/locale/layout
qualification. The worker stops on `greeter-controls` without activating or
dismissing a choice. It neither resolves nor qualifies the offered session.

On the station bus, the observer requires the owned `kiosk-request-window` and
`kiosk-request-form` IDs before reporting `default-request-form`. This limited
destination observation does not run prompt handling or validate the form's
selectors, values and unavailable controls; those remain the separate
`kiosk-request-form` checkpoint and its prompt-refusal contract. No input is
authorized by the branch observation. Installed diagnosis reached the station
and recorded `default-request-form` with no unresolved greeter controls.

The default-entry binding uses the installed tuple's observed passwordless
default only; it does not
add UI15 or a session catalogue. The worker consumes the fresh focused station
row proof once before Enter. Its separate `station-default-entry` checkpoint
then waits for the active dedicated station account and independently reads back
one showing, nondefunct owned request window/form destination. A greeter owner,
another or ambiguous active session, duplicate/hidden/stale owned destination,
or any result other than `default-request-form` refuses. This host binding does
not by itself qualify the installed route or complete request form. The
`check_e2e_kiosk_entry` run `20260921T184544Z-62e716ef` qualified that exact nonsecret station input/result
and the fixed disabled-child kiosk projection: one form, disabled approver,
duration, soft-app and Request controls, enabled Cancel, 30-minute selection,
screen-limit-disabled notice, and absent mute/custom value. It completed in two
fresh tree reads with no incomplete reads or query errors; enabled choices,
overlay scope and authentication remained pending at that qualification; later
case 57 acceptance is recorded under REQUEST04/08 above.

### Search and standard sign-in contracts

`check_e2e_shell_search` qualified two separately restored installed attempts in
run `20260923T191129Z-64de2a7a`: administrator SEARCH05 launch and normal close,
then standard-account SEARCH01/03/04 entry through an independent desktop proof,
first-character and exact full-query readback, the query-specific web description,
and complete stable absence of the Parent launcher and management window.
The web suggestion was not activated. Wrong-entry refusal preceded the standard
search. Both attempts passed evidence reconciliation, private collection and
owned cleanup. The sanitized provider tuple was Shell `50.1-0ubuntu1.2`, locale
`en_US.UTF-8`, keyboard sources `[["xkb", "us"]]`; other Shell tuples and query
bindings remain pending. This is a capability qualification, with no complete
case 5 acceptance credit. The run `20260923T191129Z-64de2a7a` is outside
runner retention.

The complete retained E2E-004/app-grid case 5 passed through
`parent_access.PLAN` and `onpc_parent_access::run` in run
`20260923T192157Z-7d86e72a`. Its fresh standard-account login, exact
`Oh No! Parent Control` query, web suggestion, stable Parent launcher/window
absence, private collection, reconciliation and owned cleanup all passed.
The suggestion was not opened. That run's report is outside runner retention.

`check_e2e_parent_search_launch` qualified SEARCH05's administrator management
bindings in run `20260923T182610Z-718ecc45` (outside runner retention).
`onpc_parent::open_from_app_grid` launched the full product query once and
independently observed the owned `parent-window`. After normal closure, a
separate caller supplied a fresh SEARCH06 result to `launch_search_result`;
the same owned result and closure passed again. A desktop proof refused before
activation. Host checks retain wrong/stale proof, wrong-owner/result, incomplete
read and uncertain-input non-replay coverage. UI18's `onpc_window::close` Parent
binding consumes the owned surface proof before the ordinary API close request;
`AccessibleUI.parent_search_closed` requires a prompt-free desktop and complete
fresh absence of management, denial and startup-error windows. Private collection,
worker shutdown and owned cleanup passed. Actual Shell tuple retained in both
close-readiness observations: `50.1-0ubuntu1.2`, provider locale `en_US.UTF-8`,
keyboard sources `[["xkb", "us"]]` on the pinned Ubuntu 26.04 image. This supplies
no complete-scenario credit; the FIX02 empty-result binding remains pending.

`check_e2e_shell_search_results` qualified the fresh Parent SEARCH01/02/03/04/06
slice in run `20260923T180845Z-4df4db55` (now outside runner retention):
That historical `onpc_shell_search::run` supplied the search entry independently of the
`AccessibleUI` observations; `shell_search_field`, `focus_search_field`,
`search_ready` and `search_query` observed the empty field, fresh focus, `O`, then
`Oh No! Parent Control`. `launchable_result` and `focus_search_result` identify
and focus the product launcher; the unrelated `Terminal` binding refuses.
Escape clears the query, `shell-search-cleared` observes the empty field, Super
closes Overview, and `shell-search-dismissed` requires a prompt-free desktop and
complete-tree search-field absence. Private collection and owned cleanup passed.
This qualifies only the pinned Shell provider environment described in the
[provider catalogue](#external-provider-qualification), with no launch,
standard-account unavailability or complete-scenario acceptance credit. Current
qualification types the full query once and closes Overview directly after the
result check; first-character and empty-query checkpoints are removed. Other
queries and entry routes retain their separate gates.

The registered standard operations connect to the canonical other-child
desktop's owned accessibility bus. GDM07 reuses direct intended-account selection and two fresh recipient checks
from Parent sign-in, with explicit account bindings. Wrong-account visits are
never composed into normal entry.
Standard-specific ordered recipient checkpoints cannot reuse Parent evidence.
Both fresh checks require the intended identity and sole empty, masked,
showing, enabled, focused field. Review, uncertain input, capture and replay
refuse; preserve the secret API and recipient-safety assertions while migrating
any legacy appearance gates to semantic proofs.

SEARCH01 consumes a fresh desktop observation and requires a prompt-free desktop
before sending Super-A once, then returns the showing, enabled, editable,
empty Overview field. A modal can consume the shortcut; the prompt guard refuses
it before the opening gesture, with no dismissal or shortcut replay. UI21 consumes that reply for
semantic focus through the qualified Shell adapter, then independently observes
focus. SEARCH03 consumes the fresh focus proof, types the complete query once
at the existing bounded pace and reads it at `search-entered`. Input uncertainty
is terminal; no repair or replay is permitted.
The app-grid acknowledgement opens step-2 before its first input.

SEARCH04's unavailable result composes UI03 and UI11. The exact query and
its usable search field must remain showing while complete fresh accessibility
traversals exclude the product launcher and management window
for two seconds within the 45-second adapter deadline. Missing or defunct
subtrees restart that interval. Resolve the query and product launchers through
the qualified Shell adapter; the repository-owned management window remains
ID-addressed. The developer removed all web-suggestion validation on 2026-10-07,
regardless of VM or distro: no results or unrelated results are acceptable when
the product launcher and management window remain absent. Never activate an
unrelated search result.
This observes launcher unavailability; direct-command denial and time enforcement
belong to their own scenarios.

Current prompt middleware has host-only recognition/refusal for MATE Polkit,
Shell Polkit, keyring and unknown authentication modals, including late
arrivals. Routine customer/search flows perform no automatic prompt dismissal. The separate
`AccessibleUI.cancel_keyring_prompt` route is qualified for the prepared standard
gcr harness challenge described in the provider catalogue: masked-field focus, one Cancel,
observed disappearance and independent desktop readback without input replay.
The separate `AccessibleUI.kiosk_mate_cancel` route is qualified for the fixed
kiosk request and provider tuple in the catalogue, including independent reentry
and unchanged no-error form return; it does not authorize middleware dismissal.
Incomplete or ambiguous provider observations refuse before input.
Separate MATE Polkit, Shell Polkit and keyring adapters must independently
qualify each owner and surface. Never read or supply a keyring password, dismiss
unknown dialogs, or mistake one provider's challenge for another.

[Worker regressions](../../tests/unit/test_parent_access_worker.py) qualify
independent block entry, fresh proof consumption and uncertain-input refusal.
[Adapter regressions](../../tests/unit/test_accessible_e2e_ui.py) cover bounded
text reads, focus, delayed launchers and stale reads resetting stable absence.
The [controller regressions](../../tests/unit/test_installed_journey_cleanup_safety.py)
reconcile every ordered checkpoint and durable phase boundary. The
[isolated Shell probe](../../tests/ui/e2e_search_probe.py) remains adapter
qualification; complete installed execution and cleanup earn acceptance.

## Existing runtime services

The catalogue owns feature-block contracts and status; the
[task queue](E2E-Task-Queue.md) owns implementation order.
These existing services support those blocks within their current qualified
scope; reuse them without building a second runner or counting their checks
as customer behavior.

| Need | Implementation | Contract |
| --- | --- | --- |
| Public UI read boundary | [accessible_ui.py](../../tests/e2e/accessible_ui.py): `run`, `wait`, `observation`, `nodes` | All registered operations and standalone waits use the same element-independent observation scope. Composed lookups reuse a complete tree and its scoped projections until input, a pending predicate, a failed read or an accessibility-client reset invalidates it. Separate operations always start fresh. Protected text scopes stay distinct; tolerant/incomplete reads never seed complete observations. |
| Installed app prerequisite | [suite_lease.py](../../tests/e2e/suite_lease.py), [installed_setup.py](../../tests/e2e/installed_setup.py) | Use the [snapshot and case-entry contract](#parent-login-and-time-scenarios) for content identity, online/offline capture, independent restoration and final audit. Preparation failure is terminal; no case-local fallback installer. |
| Controller rendezvous | [installed_journey.py](../../tests/e2e/installed_journey.py): `JourneyPlan`, `InstalledJourney` | Ordered requests, durable observation callback, fresh ownership guard, then atomic reply. Boot identity supplies harness continuity only. |
| Recorder composition | [installed_journey.py](../../tests/e2e/installed_journey.py): `record_installed_journey` | Provision fixture credentials, enter declared phases, checkpoint observations and reconcile screenshots. Strict customer execution; existing recorder owns evidence and final acceptance. |
| Product-free serial envelope | [serial_harness.py](../../tests/e2e/serial_harness.py): `record_serial_journey`, `matched_screens`, `validate_stages`, `validate_completion` | Retain case 1's credential/getty/assets setup, unchanged-boot recording, durable phase transitions, HAR09/HAR10 checks and separate evidence outcomes. Outer execution owns lease restoration. |
| Shared checkpoint declarations | [journey_blocks.py](../../tests/e2e/journey_blocks.py): `fresh_desktop`, `parent_search` | Fresh caller-owned mappings for registered GDM07/DESK01 and SEARCH06 stages. No I/O, expected customer values or implicit phase changes. |
| Legacy/security matched click | [onpc_pointer.pm](../../tests/integration/graphical_smoke/lib/onpc_pointer.pm): `click(tag, timeout)` | Retired generic route; refuses before input. Any permitted external-provider image route requires its own explicit adapter and qualification. |
| Worker stage reporting | [onpc_journey.pm](../../tests/integration/graphical_smoke/lib/onpc_journey.pm): `seen`, `finish` | Emit the named semantic stage and wait for its acknowledgement; `observe` refuses legacy image gates. Verify shutdown. |
| Interrupted pre-start setup | [system_runner.py](../../tests/integration/system_runner.py): `recover_graphical_cleanup`, through `tools/run-tests integration check_graphical_recovery` | Restore a recorded `isolated` attempt only with a null instance ID, powered-off pinned guest, matching run tag, original disk identities, no host sharing and a full baseline proof under the exclusive lease. Reuse outer cleanup; never start the guest or replace the baseline. |
| Reviewed image preparation | [parent_needles.py](../../tests/e2e/parent_needles.py), via [prepare-e2e-needle](../../tools/prepare-e2e-needle) | Retained artifact tooling; preparing an image does not qualify an external-provider adapter or a customer result. |

The scenario recipes own expected results. Shared runtime services do not
choose a customer's expected result or query internal product state.

New UI helpers inherit read reuse through the common adapter; do not add caches
for individual controls or providers. Use the captured IDs and tree edges for
multiple lookups in one observation. A standalone composed reader can use
`with ui.observation():`; nested helpers share that scope automatically.
Registered operations already open it in `run`, and `wait` reacquires after a
pending predicate while preserving its deadline. Public input must use the
existing action API or set `input_uncertain` before dispatch; that shared latch
invalidates every cached scope, including on failed input. An accessibility
client reset must call `invalidate_observation()` before reconnecting. Never
carry observations across external input or session changes. Independent
checkpoints, stable-absence intervals and result assertions remain required.

## Add a consumer

Apply the [VM observation mandate](../Mandates/VM-Mandate.MD#vm-observation-mandate)
and [shared viewer contract](../../tests/e2e/README.md#optional-live-viewing)
before VM work. They own collector lifetime, authenticated transcripts, viewer
independence and required nonsecret intent; consumers reuse those interfaces.

Before a Perl block acts, publish its fixed nonsecret intent with
`onpc_progress::operation('Fixed nonsecret description')`. Use literal prose
and redacted role labels, never credentials, entered text or observed account
names. Public UI operations declare their labels in
`ui_observations.OPERATION_LABELS`. Keep inventory descriptions complete for
the shared recorder/viewer; viewing supplies observation, not acceptance.
[Progress regressions](../../tests/unit/test_e2e_progress.py) own the registration
and timing checks for new worker blocks and UI operations.

1. Select one inventory variant and its complete visible result. Identify the
   required fixtures and surfaces. Reuse accepted setup; installation mechanics
   do not become customer assertions. If a shared operation is missing, name the
   blocked action and implement only that operation with this consumer.
2. Compose a worker module from the ordered blocks and selected recipe above.
   The established cases demonstrate current working sequences; migrate their
   selectors/input routing while preserving recipient-safety assertions. Use normal
   app-search input and functional checkpoints.
   Product selectors use UI15's canonical API setter with current owner/surface
   and offered-choice checks. A fresh checkpoint verifies the displayed
   child/settings independently. UI14 focus/navigation remains external-provider
   infrastructure and is not a product selector prerequisite.
   Add a fixed branch in [smoke.pm](../../tests/integration/graphical_smoke/tests/smoke.pm)
   for the new worker mode. Reuse the existing exchange channel and owned worker;
   do not create another VM runner or invoke private product APIs.
3. Define a `JourneyPlan` in the Python scenario module. `screen_tags` maps
   stage names to `ui:<operation>` **in execution order**, including security stages.
   Provider-specific selection stays inside the qualified adapter; `ready` and
   `setup-detached` are prepended automatically. `prefix` must match the worker's
   `onpc_journey` prefix. `worker_mode` names the fixed ready-reply branch.
   `phases` maps every stage to a declared recorder step. `advance_after` opens
   the next step before the current reply permits that step's first input.
   The About plan opens `step-2` after its `about` product-information result,
   before the guarded close and unchanged-management observation.
   For settings comparisons, `settings_checks` maps the current stage to an
   immutable `SettingsObservation` expectation or an explicit earlier stage.
   The controller retains sanitized immutable values, compares before fixture
   actions/storage/reply, and refuses missing earlier evidence or replay.
4. Have the callback call `record_installed_journey(recorder, context, PLAN)`
   and register it in `E2E_CASES`. Reuse `invocations` for repeated operations,
   `challenges` for separately bound authentication, `assertions_after` for
   intermediate results and `reboot_transition` for a customer reboot. Finite
   `additional_reboot_transitions` supports at most four more; each refuses input
   until every preceding reboot has an independent changed-boot observation.
   Their scopes are maintained under [shared capabilities](#refactoring-the-established-cases).
   Product-free install recipes use `record_package_journey` with declared
   public-result checks. Fixed account-fixture stage actions are supported.
   Extend only a missing binding; do not recreate these mechanisms in a case.
   Ordinary feature
   installation/reboot belongs only to suite snapshot preparation. Tested package
   installation/reboot in E2E-002/026/027 remains a real customer action.
5. Reconcile that variant's inventory declaration, requirements, visible
   assertions and evidence. Customer families use `category: customer-journey`.
   The `installed-digest-verified-product` prerequisite selects the suite's
   installed snapshot and package-bound bootstrap, without a case-ID branch in
   the executor. Package lifecycle scenarios omit it, explicitly declare
   `declared-package-lifecycle-fixture`, and provision their declared initial
   package from `onpc_baseline` as part of the tested package behavior. A feature
   case cannot omit its installed prerequisite or fall back to installation.
   Runner-only product-free harness checks may use baseline without installing.
   Declare
   `fixture-credentials-via-secret-api` when using authenticated input. A ready
   callback must exist, and all required steps must have real implementations.
   Registration enables execution; only complete acceptance earns coverage.
6. Complete the [composition preflight](#composition-preflight), then use
   verified inputs containing the intended product changes and run the exact variant
   through the [public E2E command](../../tests/e2e/README.md#run-e2e-scenarios).
   Preserve staged inputs, evidence and owned cleanup. Concurrent checkout edits
   follow the documentation map and do not invalidate the attempt.
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
| Black VNC image after the installation reboot | Treat graphical reattachment as provider-blocked until the public GDM identity route can re-establish the surface. The retained legacy `onpc_gdm::reattach_after_setup` entry point refuses; never restore it with image readiness or reset the VM inside a customer journey. |
| Displaced or covered owned controls | Invoke the ID-resolved public action directly. Viewport clipping alone needs no focus or scroll; reveal only when a required observation or unavailable action needs it, then reacquire. Follow the [UI input contract](../Mandates/UI-Automation-Mandate.MD#input-and-independent-results). |
| Installed greeter differs from the baseline account list | Use the qualified GDM adapter and independently prove the intended secret recipient; see external-provider qualification. |
| A fullscreen overlay hides Shell desktop controls, or Shell metadata goes stale after desktop readiness (048c) | Discover the unique top-level Shell application on the active child's public bus through `AccessibleUI.shell_prompt_owner`, preserving PID/UID/session and protected-field guards; do not require Activities visibility to identify the authentication provider. Desktop readiness does not freeze the next tree: `shell_provider_metadata` retries only a complete fresh metadata observation under the existing deadline. Regress missing/ambiguous/nested/foreign/stale owners before Request input and transient versus persistent query failure. Keep this provider behavior in the shared adapter. |
| GDM scrolls its account list | Reuse the qualified GDM provider's direct account selection or bounded keyboard navigation with observed identity/focus under the UI mandate. Reacquire the intended recipient before secret input; list order and image absence are not recipient proof. |
| Parent search returns no product launcher for a standard user | The [launcher contract](../SystemDesign/Broker.md#accounts-and-roles) intentionally restricts app-grid discovery to administrators. Match the full product query and complete stable absence of the product launcher and management window. Empty or unrelated results are acceptable; do not require a web suggestion, activate another result or invent a denial dialog. Executable denial belongs to the separate direct-command variant. |
| Keyboard assumptions select the wrong child or menu item | Set the canonical UID or command through UI15 and independently verify the selected child/result. Product controls require no highlighted-row or Enter sequence. Ordinary Parent launch/reopening uses PARENT01's direct command and independent window result; only explicit app-grid discovery cases use whole-query SEARCH05/06. |
| An acknowledged action has no durable evidence, or belongs to the wrong step | Store the observation and any required next-phase start before publishing the reply; guard ownership again after storage. An acknowledgement may immediately permit input. Storage or guard failure latches terminal failure. |
| A stale observation appears to prove returning to the same child | Reconcile one fresh semantic result per ordered stage. Compare the returned child, switch state and allowance with the initial displayed settings. Missing, reused or reordered evidence refuses. Worker exit zero alone cannot pass. |
| A complete accessibility traversal combines old readiness with a new account identity (300j) | Completeness is not atomicity. Confirm the selected UID and closed list, then discard that snapshot before the separate language-readiness/setup boundary. Regress the mixed-time traversal, saved/unset language and failed Save without input replay. Reuse the [shared account-selection implementation](../../tests/support/README.md#host-and-guest-boundaries), rather than adding sleeps or treating submitted values as results. |
| A retained Parent window follows work in another window (300j) | Preserve that preceding input/return history in `test_parent_child_picker_after_language_policy_reads` in the [real GTK regressions](../../tests/ui/test_language_settings.py). Select the child by canonical API UID and independently read its policy; foreground/focus/popup state supplies no selection result. Keep the same owner/surface and uncertain-input guards. |
| A resumed brief describes a failure although newer repairs or tests already exist (300j) | Reconcile the checkout, active runner selection and retained reports before editing or rerunning. A run title emitted before the exchange completes is not confirmed result evidence. Preserve valid completed slices and retry only outstanding work; follow [failure handling](../../tests/README.md#handling-test-failures) and [VM ownership](../Mandates/VM-Mandate.MD#authority-and-operation). |
| Choosing package inputs | Build artifacts when the installed product needs to include current changes. Runs use the supplied artifacts and allow concurrent checkout edits; private staged artifacts remain integrity-checked. Multi-VM qualifications also bind named inputs with `vm_source=True` and select the package format from each verified baseline. Task 042's Fedora entry required a separate RPM input and the shared package-version reader for snapshot attachment; a valid Ubuntu bundle cannot supply that boundary. Task 044b's window-switch regression likewise stopped before worker startup when its consumer lacked RPM input, despite the main qualifier's correct binding. Check both the selected consumer and its automatic preparation binding before live entry, preserving existing inputs and provenance refusals; fixture users also bind `fixture_source=True`. Planning regressions use private allocator doubles so they cannot reserve an empty real bundle. See [snapshot preparation](../../tests/e2e/README.md#reusable-startup-preparation). |
| VM is off but baseline acquisition reports `guard:source-changed` | Inspect the saved run phase and inactive configuration through the approved readers. An interrupted `isolated` setup can retain the test configuration. Use recorded graphical cleanup; do not edit the journal, recreate the baseline or treat powered-off status alone as restored state. |
| A small fake collection passes but the installed app's reply exceeds the transport limit | Test the complete observation through serialization and both buffered/streamed transport at realistic and maximum declared sizes, including repeated save events (017b). Keep byte, item-count and schema bounds consistent. [App-row regressions](../../tests/unit/test_e2e_app_rows.py) and [trace regressions](../../tests/unit/test_e2e_feedback_read.py) exercise realistic collections and reject oversized/partial results. |
| Widget doubles omit behavior seen through the real toolkit | Exercise the new projection with the real public adapter before VM qualification. Language tasks 300g–300i additionally separate visible labels from accessible names (including English capitalization) and compare both against literal caller-owned oracles; shared IDs stay locale-independent. Capture supported representation in the shared leaf and its regression, such as collapsed selectors or rich-editor paragraph endings; link the existing binding contract rather than teaching every consumer to normalize it. Task 226b additionally showed that collapsed legend content can be absent and its pressed state can precede content realization: regress absent-before-reveal, delayed-after-input and already-open reads in the shared adapter. Retry fresh result reads within the existing deadline, never the toggle input. |
| Adding a qualification breaks an older conflict test even though both routes refuse safely | Assert refusal before credentials, storage and VM work. Do not couple a multi-invalid-input test to whichever validator happens to run first. Keep exact diagnostic checks for a single invalid condition. |
| Later cases escape an earlier composition audit | Discover cases and workers from ready inventory bindings. Review helper methods and subclasses as well as callbacks; moving I/O into a case-local helper is still case-owned mechanics. The [composition guard](../../tests/unit/test_e2e_case_composition.py) enforces this boundary and joins the [registration/close-out checks](E2E-Execution-Contracts.md#completion-and-document-cleanup). Case 139 exposed local lifecycle comparisons and scoped worker input despite an already-ready binding. Keep its independent values/endpoints in the recipe and use the shared lifecycle recorder, public comparison factories and named entry/edit leaves; verify a renamed caller, actual worker titles and failure stops before accepting an extraction. |
| A negative-entry or provider-close check encounters an incomplete tree (300f–300h, 044) | An incomplete read establishes neither absence nor a safe refusal. Reacquire only the complete read through the existing bounded wait, preserving its original deadline; a complete wrong-owner, wrong-surface or unexpected-prompt result stays terminal. Keep input outside the predicate and retain transient/persistent failures and no-input assertions in the [shared adapter regressions](../../tests/unit/test_e2e_kiosk_eligible_choices.py). Task 044's viewer-close result also needed bounded fresh absence reads while provider nodes retired; retain `test_window_close_requires_complete_absence_without_replaying_input` in the [feedback reader regressions](../../tests/unit/test_e2e_feedback_read.py), including query failure, visible provider, ambiguity and wrong owner. Do not add case sleeps, replay Close or relaunch an absent target. |
| Qualified sequences are copied into a complete case | The prepared-request and approval tasks demonstrate reusable composites feeding several complete cases. Apply that pattern to feedback's edit-state and UTF-16 matrices too: expose one declaration/execution pair in a shared module and call it from qualification and cases. Save and fresh Cancel are separate fragments, so a consumer can select either without inheriting the qualification journey. Keep different terminal results and independent-entry checks in the callers. Catalogue search/filter/legend (077b/077/226b) and case 184 likewise share `CataloguePolicyJourney`: put finite comparison endpoints in the plan instead of copying a comparison override or adding a case class just to bind a table. |
| A long accessibility-driven Parent journey reaches the desktop idle timeout | Baseline owns the persistent idle setting. The shared desktop-entry envelope verifies it after every qualified entry, including reopening/reboot paths, and refuses stale state. Never add per-case settings writes/keepalive input or alter the child's tested expiry behavior. See [shared entry helpers](../../tests/e2e/README.md#shared-system-and-account-entry-helpers). |
| Attachment metadata is visible but GTK's Description property is empty (038a) | Qualify the real public relation before designing the projection: read the owned row's `DESCRIBED_BY` target, retain exact order/name/size, and regress absent, foreign and ambiguous targets. Put toolkit representation in the adapter, not each case. |
| A Remove action returns before GTK updates the list (038a/038) | Submit once; while waiting permit only the exact valid pre-action state, then require the exact expected result. Regress delayed success and wrong-item removal without replay. Reuse guarded fixture actions and immutable list comparisons across attachment profiles. |
| A generic row activation looks like a preview (038b) | Prove the app's offered capability through its public availability and action contract first. Record an explicit inapplicable result and an independently unchanged list when no preview is offered; do not invent an external-editor route or claim offered-preview coverage. |
| Rich text is exposed through different public structures (034aa/034ab/034a) | Probe real block semantics, inline Text attributes and Hyperlink text/URI independently before composing all formats. Associate each with exact unique synthetic ranges; Hyperlink indices are local embedded-object positions, not editor-global offsets. Regress linked and unlinked ranges, removal preserving text and independent reopen. |
| A reset check could accidentally restore the draft it is meant to inspect (030a) | Capture a nonempty draft, compose the shared app lifecycle, then independently read the empty result before any restorative input. Keep dialog preservation and app-exit reset as separate assertions; extend profiles explicitly for formatted/file-bearing consumers. |
| A supporting viewer command succeeds before its public window is ready (034) | Keep launch and observation as separate states in the shared adapter. Submit once, retry only read-only observations within the existing deadline, require a complete snapshot for acceptance, and refuse wrong ownership or ambiguity immediately. Regress delayed appearance, terminal refusal and command timeout with an exact one-launch assertion; never retry the whole operation to fix a slow result. |
| Individually qualified draft operations must preserve a combined formatted/file-bearing draft (034) | Before the live case, carry the complete profile through the real decoder and recorder: text/reply, formatting/link meaning, exact attachment list and window identity. Exercise dialog return and app-exit reset independently; helper success alone does not prove the combined history. Reuse the same Privacy/window preparation fragments in qualifications and cases. |
| File-reading and source-change capabilities could be mistaken for product snapshot or export acceptance (195a/195/196) | Reuse the guarded reader with a declared artifact and its owned identity receipt; compare independently specified content, exact ZIP members and bounded sizes/digests. Retain malformed/replaced/unsafe-file refusals and cleanup. A changed source qualifies FILE09 only; frozen attachment bytes, re-add and product exports stay with their [coverage owner](UI-and-E2E-Coverage.md) and named binding. |
| The attachment matrix made the installed case repeat toolkit coverage (039) | Check the [UI/E2E ownership table](UI-and-E2E-Coverage.md) before designing the live journey. Keep the full boundary matrix with its GUI owner and the installed integration assertions in the case. Case 154 and qualifications share `file_handoff` / `supply_files`, `chooser_preservation` and `attachment_removal`; qualification-only refusal checks remain in their callers. An audit does not authorize dropping assertions outside that agreed ownership. |
| A transient functional result can be lost during synchronous input (048d) | Use the existing token/boot/deadline rendezvous and retain readiness before input. For automatic overlay approval, pin the child-owned request window and observe the explicit result before its automatic closure, then independently read the original activity. Regress wrong owner, denied/missing result and failed readiness without replay. Disappearance alone cannot prove approval. Parent saves use independent final value and persistence reads instead of transient Saving or inhibition samples. |
| Observer readiness triggers nested commands that also produce output (016c) | Keep stdout parsing local to each command. Exercise split/buffered replies and nested ownership/input commands through the real transport; unrelated command output must never enter the observer's JSON stream. Keep readiness, one input and terminal evidence ordered under the same attempt guard. |
| Rapid saves must preserve the last accepted value (017b/017c) | Declare the finite edit batch once and bind it to the named child before input. After rapid changes, independently reselect and reload each child's distinct expected value. Preserve recipient, single-use input, source/token and failure boundaries; temporary inhibition, editable-control recovery and intermediate Saving are not acceptance. |
| Fixture preparation could be confused with catalogue, launch or enforcement acceptance (035p/077b/077/226/079) | Follow the [baseline lifetime](../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline), then independently verify its finite source inventory in the guarded attempt. Compare declared fixture IDs and defaults within the complete public catalogue, preserving unrelated stock rows. Search/filter expectations come from the shared finite oracle, including empty sets; restoring filters compares the full initial policies. Before live pattern edits, exercise the actual draft against the complete declared fixture directory, including space-bearing nonmatches: task 079's narrower pattern exposed an unrepresentable omitted rule. Retain a no-omission regression for the chosen pattern rather than changing the expected policy or fixture inventory. File verification and catalogue visibility do not qualify launch/usability or enforcement. Keep distinct local functional outcomes with their [UI owner](UI-and-E2E-Coverage.md) and reuse its oracle in the installed sample. |
| An external-handler workflow is considered before checking what acceptance requires (185w/185v/185s/185p/232) | Resolve the [current integration contract](../Mandates/UI-Automation-Mandate.MD#product-integrations) before adding a provider dependency. These tasks reused the owned clickable-link reader for individual links and then the complete information composition. Qualify an added control's missing/disabled/nonactionable/wrong-owner refusals, then compose the same reader; historical handler qualification does not expand the consumer's acceptance. |
| Internet isolation risks disconnecting the attempt's own transport (193a/193) | Qualify shared infrastructure isolation separately from product usability. Preserve guarded SSH, display/watch and VM identity, independently observe Internet absence and recovery, and test interruption restoration and replay/wrong-entry refusal before composing Parent actions. The infrastructure result does not establish LIFE06 or a complete offline case. Reuse `vm_internet.InternetIsolation` and `offline_controls`, rather than case-local network commands. |
| A request estimate or unchanged app text could falsely pass a continuation (052/061/047/048e) | Bind the expected countdown to independently observed daily time and the explicit requested increment (case 49: 900 + 75 seconds), with declared elapsed-time bounds; the request estimate alone is not issued-time evidence. Capture activity before opening the overlay and compare both the immutable native-window identity and exact draft after Cancel, before cleanup or new input. A replacement window with identical text must refuse. Reuse `countdown.check_countdown_balance` and `ui_observations.compare_app_activity`; these checks do not qualify expiry, denial or cross-user retention. |
| Authentication expectations or prepared inputs outlive their producer (048d, 300e, 300i) | Before a live attempt, compare the complete expected request message with the current broker producer, including child, duration and soft-app context; regress the obsolete message's refusal before touching the protected field. Bind qualification inputs to current package sources and, when native fixtures are exercised, their sources too. Reuse `named_input(package_source=True)` or its fixture-inclusive `fixture_source=True` binding and the maintained builder/provenance checks; dual-release work uses `upgrade_source=True`. Check affected regression launchers and their automatic preparation bindings too. Task 300e's kiosk-entry regression selected an older snapshot from a valid legacy package bundle; 300i likewise needed current-source Shell-panel inputs. Preserve that bundle and select current verified inputs through the shared launcher rather than relaxing snapshot identity. A version label or historical pass cannot establish current bytes. |
| Distribution compatibility paths look like unsafe asset files (300a) | Identify the canonical distribution-owned file and record the compatibility link's identity separately. Verify its exact destination and refuse dangling or unexpected links; preserve the shared regular-file/no-link reader. Apply this in the owning asset verifier and baseline reconciliation, rather than adding per-case path exceptions. See [Chinese preparation](#chinese-language-preparation-and-desktop-language-setup). |
| Login and a supported API change the representation of preservation witnesses (300b, 300e) | Reproduce the specific transition before adjusting an oracle. Separate pre-login preservation from mutation preservation: only the independently bound departed temporary greeter may disappear, while the setter compares all accounts and graphical sessions against a fresh desktop snapshot. Accept only the declared API representations of the requested locale, report the actual readback, and keep other witnesses exact. Explicit logout/login can restore the encoding suffix and replace the administrator session; compare the independently observed renewed language/session against only those declared changes before rebinding the upgrade preservation snapshot. A setter's success or normalized language value does not prove a renewed desktop. The [DESK13 contract](#chinese-language-preparation-and-desktop-language-setup) owns the finite exceptions. |
| Transfer, installation and upgrade could be conflated (300c–300e) | Keep FIX04 transfer/readback, LIFE04 package commands and LIFE02 reboot observations separate. Verify both genuine package identities before transfer; independently read both guest digests and metadata afterward. Reuse `PackageCommand`, `submit_release` and `observe_release` for one old install, observed activation reboot and one current upgrade. Check the actual installed version, final completion/reboot notice, same boot after upgrade and preserved witnesses separately from command success. Keep refusal checks in qualifications and customer assertions in cases; never substitute two current installs or a simulated notice for a genuine upgrade. See [upgrade transfer](#verified-upgrade-asset-transfer) and [package upgrade](#genuine-package-upgrade). |
| A startup helper would consume the first presentation under test (300e, 300g–300k) | Enter through the surface's initial binding and observe the actual modal/form before any generic setup handler, preference save or dismissal. Check the default choice without choosing it. Parameterize the shared chooser reader by surface and selected child, including Save/Cancel completion; qualify a new binding separately. Current-install first presentation (300k) starts product-free with current bytes and one reboot; the historical upgrade/reboot composition does not establish that causal history. Capture before Close/Cancel, submit once, then independently compare the returned form; an unchanged form after Cancel must not be repaired by saving a preference. The [language-selection scope](#personal-language-selection) owns surface/child bindings; the [first-presentation scope](#chinese-language-preparation-and-desktop-language-setup) supplies the public operations and finite expectations. |

### Composition preflight

Collection readiness (031a) demonstrates a result wait, not a transition test:
use the shared predicate wait for the complete public result (finished diagnostics
and available Download), accepting immediate completion. Require intermediate
events only to establish a distinct functional result that a final observation
would miss. Save ordering uses rapid input followed by final saved and reloaded
values, without transient control-state events.
Regress immediate success, delayed success, timeout and ownership refusal before
live qualification; do not introduce an observer/input rendezvous merely to wait
for readiness.

Before the first live attempt, check the changed boundary end to end on the host:

1. Bind recipe stages to the actual shared callable, operation registration,
   worker dispatch, observation schema and recorder assertion. Run
   `tools/run-tests unit 'tests/unit/test_e2e_case_composition.py' 'tests/unit/test_e2e_progress.py'`
   after registering or changing a case; it discovers new ready bindings
   automatically. Keep scenario values, order and expected outcomes in the recipe;
   put transport, fixture lifetime, provider input and reusable comparisons in
   their owning libraries. A new shared API gets a meaningful success/refusal
   regression and review of the guard's shared API list, never a case exemption.
   Check each declared `system:` stage against the actual shared session registry
   and controller decoder; a mocked worker-order test can hide an unregistered
   operation. The overlay-language regression drives those declared stages
   through `session_control.observe` before live entry.
   Review imported callable references (including recorder classes/actions) and
   qualified Perl calls, not just direct Python calls. The guard is a source
   regression check, not proof that an allowlisted library is reusable or safe;
   inspect the changed helper and its consumers too.
   Resolve package inputs for the selected qualification and its affected
   regressions before starting the live sequence. Use the source-bound inputs
   above; snapshot preparation alone does not refresh a launcher's asset bundle.
   In particular, a case dispatcher in a shared library is still a composition
   root: inspect its body for copied qualification mechanics. Case 159 and the
   named-child qualification share `journey_blocks.ordinary_custom_save` /
   `onpc_feedback_states::ordinary_custom_save` for selection and ordinary custom
   input; callers retain the independent per-child and restart readbacks.
   For a newly parameterized identity, trace the binding through every layer,
   including defaults in nested helpers and asynchronous input receipts. Test
   the nondefault identity and a mismatched receipt before live qualification;
   a renamed stage alone does not prove the input targets the intended child.
   Trace each post-transition usability assertion to the public input that
   establishes its required policy and selected accounts. A reboot does not
   enable fresh-install child controls, and preserved eligible administrators
   do not guarantee the recipe's initial approver. Keep untouched startup reads
   before setup; exercise explicit account selection from a different eligible
   default on the host, retaining the final identity and enabled-control guards.
   Reuse the declaration/execution pairs in the
   [shared support guide](../../tests/support/README.md#extend-without-hiding-the-scenario)
   and the qualified [LIFE07 scope](#installed-restart-notice-qualification).
2. Exercise the actual worker sequence against the plan and inject refusal at
   the changed boundary. Check that no later input or successful reply occurs.
   Reconcile the worker's actual recorded titles through `matched_screens`;
   generating titles from the plan can hide mismatched nested worker prefixes
   even when every observation callback ran in order.
   For a custom journey class, also call the real recorder entry point through
   worker startup: its constructor must accept and forward `plan` and keyword
   `actions`. Direct class tests and a mocked recorder do not cover this boundary.
   For standalone guest observers, execute the actual stdin payload with isolated
   Python from a private directory. An invalid operation must reach the argument
   refusal before any host UI or account access; checkout imports must not hide
   a missing bundled dependency. Keep synthetic transport fixtures aligned with
   that same dependency bundle.
   Drive a changed comparison subclass through the real `InstalledJourney.step`
   as well: helper names must not override another recorder hook accidentally.
   Verify both the inherited observation validation and the new comparison run
   once, and either failure prevents the durable reply.
   For a new observation shape, carry realistic-sized output through the real
   controller decoder; an adapter-only mock cannot qualify that boundary. The
   shared request-form reader emits bounded diagnostics on both kiosk and
   overlay surfaces. Keep those validated progress records separate from the
   sole final reply in `UiObservations.call`; regress arbitrary stream chunks,
   missing/replayed replies, late diagnostics and owned transport timeout.
   Session-account binding remains separate from diagnostic-stream selection.
   Account-selector descriptions use `Selected account: …` for both child and
   approver. Keep synthetic form metadata aligned with the current producer;
   namespace-scoped selected UID IDs establish identity before description readback.
   Panel entry uses `child-request-button.activate` through the shared
   `child-panel` API, then independently reads the request form. The panel
   adapter owns Shell session/actor constraints; consumers do not inspect
   `St.Button`, focus actors or inject Enter. Refusals release no input and
   uncertain activation is never replayed.
   The actual worker bundle must also pass `e2e_worker.distribution_inputs()` through
   `test_e2e_worker_cleanup_safety.py` when adding or moving worker files. Direct
   Perl tests do not exercise its file-count, size and provenance guards; prefer
   extending an existing owning library when appropriate, preserving those bounds.
   The [lessons above](#lessons-to-preserve) identify the recurring representation
   and transport traps.
   For observation around input, include a host test where the input runs while
   the observer is active, nested commands emit output, and readiness storage
   fails. Assert that failed readiness releases no input and uncertain input is
   never repeated; a pre/post snapshot test cannot cover this boundary.
3. On failure, use the earliest failed boundary and retained evidence to state
   one cause or a diagnostic that distinguishes remaining explanations before
   another live attempt. Reproduce a mechanical defect in the smallest
   appropriate host regression before fixing it.
   Include the relevant preceding transition in that regression: a fresh widget
   may work while the same retained widget fails after session/window input.
   Bind package lifetime explicitly when installation/removal or a station entry
   depends on it. Full installed/product-free account-set assertions belong to
   those journeys; ordinary login needs the intended account/session and fresh
   recipient guards. Existing list adapters still enforce their documented
   fixture shape until a narrower binding is implemented and qualified; do not
   add a station-account sweep to a consumer merely to navigate between apps.
   Record the hypothesis, the observation that would distinguish it, and the
   actual result in the existing attempt/handoff. If the added prerequisite
   passes but the same boundary still fails, retire that explanation as
   insufficient; do not repeat the same repair or call the prerequisite a fix.
   Separate a reproduced symptom from an unverified toolkit mechanism in code
   comments and handoffs. A later passed input/result boundary establishes the
   repair; merely reaching its worker title does not.
   Preserve behavior decisions under the existing
   [failure contract](../../tests/README.md#handling-test-failures); wider retries
   and longer timeouts are not explanations.
4. Compare the capability worker and each affected ready consumer for copied
   sequences. Extract a repeated semantic operation with explicit entry/result
   and finite inputs, then verify both callers' complete stage order and failure
   stops. Leave scenario values, phase boundaries and distinct assertions in
   the recipes. A generic callback wrapper or a helper named after one case does
   not by itself make mechanics reusable. Do not combine independent attempts
   or add mode flags that silently skip a caller's required checks.
   Include capability qualifications in this review: future cases must import
   shared operations and comparisons, not inherit a qualification's private
   fixture lifecycle. Put reusable declarations in shared modules rather than
   exporting them from a qualification recipe. Validate invocation syntax rather
   than allowlisting the current callers' names; keep supported operation/data
   bindings finite. Split independently useful operations instead of forcing a
   qualification-only second action on every consumer.
   Package consumers share `journey_blocks.package_installation` for fresh
   administrator entry, submission and independent result stages. Qualification
   refusal, package binding, reboot, phase boundaries and assertions stay with
   each caller; compare complete ordered stage/operation pairs after extraction.
   Keep the finite recipe in its owner and test the shared
   fragment from an independent caller with renamed invocation IDs. Keep the
   inventory-driven composition guard and shared-fragment regressions together:
   neither allowlisted imports nor a passing case prove independent reuse.
   Resolve comparisons through the declared operation, not a case's stage-name
   spelling: a renamed invocation must still reject a changed window or draft.
   When the same operation occurs before and after a transition, declare both
   invocation endpoints in the recipe and copy the captured value. Exercise
   changed fields, missing/replayed capture and mutation of the original result;
   importing a qualification class with hidden stage-name checks is not reuse.
   Nested window endpoints, attachment lists and formatting projections must be
   copied too; retaining the decoder's dictionary allows later mutation to
   rewrite the comparison baseline.
   Where the same comparison engine serves several recipes, declare its finite
   endpoints in the plan and use the shared class directly. Test each caller's
   comparison table with renamed endpoints, immutable capture, explicit empty
   results, missing capture, replay and refusal before the real recorder reply.
   Preserve the full worker event order in regression tests when extracting a
   fragment, including failure at each boundary before any later input.

At close-out, fold a newly demonstrated recurring trap into its existing helper,
regression and owning contract. Correct obsolete capability limits and the next
consumer's callable references as part of that change. Do not append a second
history, copy mandates into briefs, or infer time savings from queue estimates;
use retained attempt/session records if comparing completion time or retry rate.

## Retained image artifacts and migration

Retain reports, images and safety regressions as evidence during migration.
Preserve recipient identity, refusal guards, empty-field/focus proofs
and capture restrictions. Use the
[approved screenshot export](../Approval-Tools.md), preserve originals and clean
only named temporary exports with `tools/cleanup-screenshots`.

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
