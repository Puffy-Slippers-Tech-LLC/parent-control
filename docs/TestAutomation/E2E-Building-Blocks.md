# Reusable customer E2E building blocks

Compose meaningful customer outcomes under the
[UI/E2E allocation](UI-and-E2E-Coverage.md) and
[result contract](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope).
UI owns local control/value matrices; installed cases reuse shared operations
for distinct backend/OS results. Provider-refusal qualification remains separate
from ordinary consumer journeys.

This catalogue owns reusable operation contracts, exact qualified scopes and
concrete gaps. The [documentation map](README.md) defines ownership/status;
[recipes](E2E-Scenario-Recipes.md) own finite scenario values and composition.

Every row below records an implementation status. Existing behavior that still
needs extraction, migration or qualification is `pending`, even when an older
scenario run passed. Current ready inventory bindings retain implementations,
behavioral evidence and functional customer assertions. Retain critical shared
safety regressions while migrating them. Retired E2E IDs 140–150 remain engineering
system-test obligations and cannot be selected by the E2E runner. Current scenario counts come from
`tests/e2e/scenarios.json` and the generated coverage report, not this catalogue.

Standalone qualifications for ordinary supporting helpers were removed under
the [integration scope reduction](../../tests/integration/README.md#aggregate-scheduling).
Their names below and in completed queue rows describe historical qualification;
they do not require recreating the entry points or repeating those histories.
Keep the qualified shared operations and runtime guards. Validate changes through
affected product consumers and focused critical-boundary checks under the
[test scope mandate](../Mandates/Test-Scope-Mandate.md).

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
Extend the existing callable with only the missing finite binding or operation.
Add an abstraction only for concrete shared mechanics or a required safety
boundary; future possible consumers do not justify a dispatcher, registry,
configuration language or fallback chain. Case data, ordering and assertions
stay in the case. Stop once its stated outcomes and scoped checks pass.
Apply the mandate's [prerequisite and early-refusal rules](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope)
inside helpers as well as task lists. Reuse the guarded operation and its valid
unchanged qualification, not the qualifier's complete sequence. Keep focused
refusal coverage separate from the consuming feature journey.

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
| App and game assets | Reuse the maintained fixture builder, verified manifests and artifact cache for native, Snap, Flatpak, versioned-path and offline-game inputs. Reconcile reusable native executables, shared GUI files and launchers through `tools/prepare-vm`; attempts independently verify them over guarded SSH. Deliberate scenario file mutations use shared file operations. No native fixture package or product installer is required. Independently controlled native roles need distinct executable content where content-based enforcement applies. Use the shared package helper only for inputs that actually require package/runtime installation. Bind the required public identity and one ordinary usable action in its consuming slice. No store browsing, vendor account creation, third-party repository setup, updater exercise or new packaging framework. Real package format, confinement, enforcement and retained activity assertions still apply where declared. Lunar's explicitly real-app profile uses FIX05 instead. |
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

Atomic/composite labels describe operation boundaries, not a requirement for a
new function, module or qualification script for every action. Use existing
callables directly when they already provide the required boundary.

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

Tables define callees before composites: leaves, control composites, GDM,
harness, desktop entry, application surfaces and journey fragments. Fixture
operations run only in the surrounding envelope or at declared checkpoints.

### Implementation slices

Qualification covers only the declared dependency set and bindings. Preserve
established assertions/adapters for other consumers; keep unavailable bindings
`pending` with concrete blockers and return conditions. Diagnostic/host-only
checks cannot establish installed scenario readiness.

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
| UI02 | A | Read logical visibility, sensitivity and declared canonical boolean values from the API snapshot. Disabled controls remain readable; product focus is not a value or readiness prerequisite. | `AccessibleUI.has_state`, `showing` and saved-state readers share API node projections; `revoke_disabled` retains independent zero-balance assertions. | ready |
| UI03 | A | Read bounded nonsecret text with `getText` or translated snapshot name/description after scoped ID lookup. Return only the declared semantic projection. | `AccessibleUI.read_synthetic_text`, label/document readers and shared API node projections. Masked external-provider fields remain excluded. | ready |
| UI04 | A | Resolve a fresh product element and invoke `activate` once through the Application UI API. Return input completion; observe the required result independently. | `AccessibleUI.activate_id` and `_invoke_target` use the shared API facade. `activate_provider` retains the external-provider route. | ready |
| UI05 | A | Send one declared key/chord only to a qualified external provider or supporting-tool recipient. Product controls use API operations with explicit handlers instead. | `testapi::send_key` retains fresh recipient proofs for Shell/GDM/authentication and external tools; product Enter maps to normal activation and product close to surface `close`. | ready |
| UI06 | A | Enter one nonsecret string into a qualified external provider with a fresh recipient proof. Product text uses UI16 and the Application UI API. | External `testapi::type_string`, including `onpc_parent::enter_search_query`; product text is shared `setText`. | ready |
| UI07 | A | **Retired.** Geometry-based resolution has no executable route. Use UI01 and semantic input; no execution exemption. | Retained `AccessibleUI.pointer_target`, `pointer_glyph` and `stable_pointer` entry points refuse before traversal or geometry access. | retired; safely refused |
| UI08 | A | **Retired.** Coordinate clicking has no executable route. Use product API UI04 or qualified external-provider input; uncertain input still refuses. | Retained `onpc_journey::click_target` and `onpc_pointer::click` entry points refuse before backend, image or input access. | retired; safely refused |
| UI10 | A | Wait for a read-only API/provider predicate under one bounded deadline. Reacquire current scoped observations without replaying mutations. | `AccessibleUI.wait`; predicates contain no input. | ready |
| UI11 | A | Observe absence of an explicit `automation-id` within an otherwise positively ID-addressed surface. Bind `snapshot` or `stable` mode explicitly. Both require complete fresh reads; stable mode additionally requires its declared finite interval and deadline. | Existing absence/window-closure paths must use registered IDs for both the absent target and surrounding surface. Incomplete/defunct reads cannot prove absence; stable reads restart their interval. [Search contracts](#search-and-standard-sign-in-contracts), [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| UI12 | A | Compare explicit sanitized observations with an explicit expected value or earlier observation; report the differing approved fields. No hidden initial/new-child slots. | `SettingsObservation.from_settings` freezes sanitized values; `compare_settings(observed, expected)` compares explicit immutable observations and reports only differing field names. `JourneyPlan.settings_checks` owns expectations and prior-stage references. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI13 | A | Observe a bounded public collection of children first resolved by stable public IDs: canonical identities/order, matching window count, or displayed row set. Inputs declare the ID-addressed root, projection, maximum and expected cardinality (including zero). Order may be verified as a result but never used as identity or to calculate input. Require complete fresh traversal for exclusion/count claims; reject duplicate IDs and unknown requested targets. | `AccessibleUI.app_rows` / `AppRowsObservation` qualify complete App Limits collections through `check_e2e_app_row_observations`; see [app-row observations](#app-row-observations). Case 159 qualified `AccessibleUI.parent_window_count` as a strict complete-tree projection of exactly one owned Parent management window after a second direct launch; duplicate/absent windows refuse. Product choice collections use API canonical identities; greeter and supporting fixture collections retain their separately scoped public adapters. Harness and [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI19 | A | Type one fixture secret once through the unchanged secret-safe API for one challenge whose surface, recipient and empty masked field were freshly resolved by owned public IDs or a qualified external-provider adapter. Accept a registered secret reference and explicit recipient proof, never plaintext in stage data. Do not submit or infer authentication success. Capture remains sealed and uncertainty/failure forbids replay. | `onpc_password::type_fixture_secret` consumes one proof from `enter_gdm_challenge`; distinct Parent GDM challenges are qualified by `check_e2e_challenges`, and the explicit child challenge by [fresh child qualification](#fresh-child-success-qualification). Used identities and the terminal failure latch never reset. Serial retains its separate proof binding; other graphical surfaces remain pending. [Challenge contract](#refactoring-the-established-cases). | ready |
| UI20 | A | Native double-click: unsupported and excluded from automation; do not implement or schedule consumers. | See the [unsupported native-gesture rule](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures). Public mouse synthesis requires geometry; semantic activation is not the gesture. No compliant callable or qualification. E2E-014 cases 38–43 remain uncovered and unscheduled. | excluded; no active task or queue blocker |
| UI23 | A | Make logically collapsed product content available through its declared API value/action only when the required result needs it. Clipping requires no action. | `AccessibleUI.reveal_id` and the shared API facade; `parent-time-status` and declared disclosures use their ordinary handlers. | ready |
| UI24 | A | Read `feedback-editor-document` through `getValue` and compare bounded synthetic text, inline attributes, block attributes and links independently of toolbar state. Selection indexes use Quill UTF-16 offsets. | `AccessibleUI` formatting/block readers project the public document delta; shared `feedback_formats` and `block_semantics` preserve their finite assertions. No arbitrary DOM/JavaScript or private draft reads. | ready for declared Parent bold/normal, complex inline and `body-blocks` ranges, linked inline and complete format/removal composition; other bindings pending |
| UI25 | A | Start a bounded read-only API-state trace with a single-use observation token before the declared input. The trace observes only declared public values. | `UiObservations.start_trace`, `poll_trace`, `observe_accessibility_input` and shared API-backed observations retain boot identity, readiness and command framing; legacy callable names do not select AT-SPI product events. | ready for declared Parent feedback traces and Parent checked-state observation during UI17 enable; other bindings pending |
| UI26 | A | Finish the trace at its explicit public terminal predicate/deadline and return ordered immutable samples. Independently read the final saved state; infer no unobserved transient. | `UiObservations.finish_trace`, trace bindings and terminal projections retain token/order/ownership checks. API text setters are atomic inputs and require no per-keystroke samples. | ready for declared Parent feedback traces and checked-state events during UI17 enable; other projections pending |
| UI27 | A | Read countdown tooltip text from its stable Application UI API ID when the local component assertion needs that explanation. No hover gesture is required. | `child-request-tooltip` through `getText`; PANEL03 and local UI obligation 181h. | ready for PANEL03's local UI scope; no installed time-accuracy or complete-scenario credit |
| UI28 | A | Open the ordinary panel context menu with `activate` on `child-countdown-menu` when a declared operation needs it. Direct preference access requires no menu opening. | Shared `child-panel` API facade; PANEL01/PANEL02 use the canonical preference value directly. | direct preference access qualified with PANEL01/02 on Ubuntu 26.04; menu-only entry remains unqualified and is no prerequisite |
| SEC01 | A | Preserve fresh intended-recipient, focus, empty masked field, capture and single-use secret checks for unavoidable graphical authentication. Wrong-recipient rejection is a harness safety test. | `AccessibleUI.password_recipient`; shared `onpc_password` input. Routine entries never visit a wrong account. | pending; prepared recipient checks qualified |
| SEC02 | A | Resolve the intended fixture account for minimal shared greeter entry. Reject ambiguous or wrong ownership before input. | `AccessibleUI.gdm_nonsecret_navigation`; direct focus then Enter without an unrelated account visit or menu tour. Harness qualification owns negative-entry exercises. | pending; prepared selection checks qualified |
| UI09 | C | Read the scoped product content, using its explicit API disclosure only when logically hidden. Reacquire its public result; clipped content requires no reveal. | UI01/UI02/UI03 with optional UI23; Parent explanations and About information share API projections. | ready |
| UI14 | C | Select an external-provider choice through its qualified semantic focus route and fresh recipient observation. Product selectors use UI15 without highlight or focus. | `onpc_journey::highlight_choice` and `AccessibleUI.gdm_nonsecret_navigation` retain GDM routes; product choices use canonical API setters. | pending; prepared installed and product-free GDM bindings ready |
| UI15 | C | Set one declared canonical value on an ID-addressed selector and independently read the result. Read `getChoices` when offered-choice assertions are part of the case. | Shared API `setValue` covers Parent/request account UIDs, durations, language codes, app-access keys, filters and menus; `AccessibleUI` owns ordinary save/readiness waits. | ready |
| UI21 | C | Establish focus only for an external-provider input route that needs it. Product fields require scoped API ownership and availability, not keyboard focus. | `AccessibleUI.focus_search_field` and provider recipient proofs remain external. Product text/selection uses UI16 and the fixed editor API. | pending; fresh desktop search focus ready. Parent feedback body/reply, Jordan App Limits search and kiosk custom-duration editing belong to UI16. |
| UI16 | C | Replace text with one scoped `setText`, then independently read the exact public result. Empty input means clear; invalid literal text is preserved for normal validation. | `onpc_text::replace_text` and `AccessibleUI` share API text input and `read_synthetic_text`; `TEXT_VALUES`, custom durations, allowance and search bindings retain their finite values. Normal Enter validation uses `activate`. | ready for declared Parent feedback body/reply including the [synthetic-rtl binding](#parent-inherited-dialog-qualification), SOH, complex and length-boundary fixtures, custom daily 1/2/3, Jordan catalogue finite queries, kiosk 1.25-minute and finite invalid values; other bindings pending |
| UI17 | C | Set one product toggle to an explicit canonical boolean and independently read the result and any required saved policy. | `AccessibleUI.set_toggle` shares API `setValue` for Parent, request and filter controls; unchanged values retain ordinary no-change semantics. | pending; Parent, kiosk soft-app, catalogue filter and Ubuntu child countdown-animation enabled bindings qualified |
| UI18 | C | Close a product surface through its ordinary API `close` request and independently observe disappearance and the expected underlying surface. External windows retain their qualified close route. | `onpc_window::close` and `AccessibleUI` share product surface close; external keyboard close retains active-recipient proofs. | ready for Parent→desktop, feedback→Parent and Privacy→feedback; other extracted bindings await live validation |

| UI22 | C | Bracket a declared caller-owned input with public-state observation. Start before input and finish at the supplied result/deadline; do not infer a transient from the final state. | `journey_blocks.observed_text` / `onpc_feedback_states::observed_text` compose UI25 → one declared UI16 → UI26. `trace_bindings/trace_terminals` pass explicit single-use tokens; failed readiness releases no input. `compose_observation.PLAN` / `check_e2e_compose_observation_around_one_caller_input` qualify Parent body-first→body-clear, immutable samples and independent FEED09. Edit-only invalid text retains enabled Send/no validation. `watch` is explicit composition, not hidden I/O. | ready for declared Parent feedback body-first and body-clear inputs; other bindings pending; Parent saves use PARENT08 final results; collection uses FEED09 readiness without a transition requirement |

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
| GDM01 | C | Observe the usable greeter and its account list, with no active password prompt. | `AccessibleUI.gdm_nonsecret_account(name)` retains the installed Parent/station cardinality contract for ordinary-account entry. Station entry and `kiosk_gdm_returned` require only the usable station row; locked, absent or differently named parents do not gate station access. The station eligibility qualification retains live requalification for that revised station scope. `gdm_product_free_account()` separately requires the declared Parent row and excludes the station from one complete product-free list. `GdmProductFreeJourney` / `check_e2e_gdm_product_free` qualifies two independent product-free list/return cycles; wrong fixture shape, owner, duplicate, stale and list/prompt overlap paths refuse. Case 2 additionally qualifies the complete fixed personal-account/station read after reboot through `gdm-installed-accounts`; [scope](#clean-installation-journey). Other bindings remain unqualified. | pending; prepared installed/product-free Parent list and case 2 account-set bindings qualified |
| GDM02 | C | Select a named user on the logon screen. Use UI14's qualified provider navigation, verify focus before Enter, then observe the declared fresh/retained GDM password prompt or passwordless station. Selection does not itself activate or unlock a retained desktop. Do not type a password. | `AccessibleUI.gdm_nonsecret_navigation(name)` retains the installed account/station route. `gdm_product_free_navigation()` separately focuses and freshly verifies Parent on the declared station-free fixture before `onpc_gdm::product_free_qualification` sends one Enter. `check_e2e_gdm_product_free` qualifies two independent Parent entries; installed Parent/other-parent/station bindings remain separately qualified. The retained-child GDM challenge passed `onpc_gdm::sign_in_challenge`; see [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Configured-zero retained-child denial also passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification). Other accounts and session choices remain unqualified; positional Home/Down calculation stays retired. | pending; prepared installed/product-free Parent and retained-child GDM selection bindings qualified |
| GDM09 | C | Dismiss an already observed GDM password prompt with one Escape and independently observe the account list again. No secret is typed. | `onpc_gdm::product_free_qualification` consumes each scoped prompt proof before one Escape and obtains a fresh `gdm_product_free_account()` returned-list proof; `check_e2e_gdm_product_free` qualifies both independent cycles. The installed qualification separately covers the prepared other-parent and Parent prompts. Retained locks and other prompt surfaces remain unqualified. | pending; prepared installed and product-free Parent bindings qualified |
| GDM04 | C | Harness safety qualification only: prove that another recipient cannot authorize an intended fixture secret. Never compose this negative exercise into customer sign-in. | `onpc_gdm::recipient_qualification`; wrong-recipient unit regressions. | ready; harness only |
| GDM05 | C | Deliver the intended fixture password once to an already selected prompt after two fresh ordered recipient checks. Do not submit or infer success. No wrong-account visit is a prerequisite. | `onpc_password::enter_gdm_challenge` binds two fresh proofs to each declared challenge through `JourneyPlan.challenges` and `onpc_journey::declare_challenges`. `check_e2e_challenges` qualified two Parent authentications separated by shared DESK04 logout, independent desktop results and wrong-entry refusal, with durable assertions, reconciliation, private collection and owned cleanup. The explicit child challenge passed [fresh child qualification](#fresh-child-success-qualification). Compatibility entries remain `enter_parent_gdm_password` / `enter_standard_gdm_password`; child input requires an explicit challenge. The distinct child `retained-login` challenge passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). Other recipients and surfaces remain pending. | pending; distinct Parent, fresh and retained-child GDM challenge bindings ready |
| GDM06 | C | Observe the declared access result at GDM or lock: usable intended desktop, or time-limit rejection with its explanation and no desktop access. A generic failed login is not the expected denial. | `standard_shell_desktop(no_prompt=True)` supplies intended-child usable desktop; `gdm_child_time_denied` requires specific fresh zero-time rejection. [Retained success](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) and [configured-zero denial/restriction](#retained-child-time-restriction-and-greeter-return-qualification) have separate GDM/lock proofs. Generic login failure cannot substitute. | pending; fresh success/zero-time denial, stated retained success and configured-zero GDM/native-lock restriction bindings ready |
| GDM07 | C | Shared minimal fresh graphical entry for the intended fixture account with declared success or product time-limit denial. Retained targets use unlock. | `journey_blocks.fresh_desktop` and `onpc_parent::sign_in`: intended account focus/Enter → fresh GDM03 proofs → GDM05 → Enter → GDM06/DESK01. Explicit challenges use `onpc_gdm::sign_in_challenge`; `fresh_desktop('child')` declares the [qualified child success](#fresh-child-success-qualification), and `fresh_desktop('child', 'time-denied')` declares the [qualified denial](#fresh-child-time-denial-and-return-qualification). `ProductFreeEntryJourney` / `onpc_product_free_entry::run` qualify the product-free Parent binding; see [qualification scope](#product-free-parent-entry-and-command-context). No wrong-account visit or prompt-cancellation tour. Preserve real graphical PAM enforcement. | product-free Parent and fresh child success/zero-time denial ready; other unqualified bindings pending |
| GDM10 | C | Retired duplicate legacy Parent sign-in. | Consumers reuse shared GDM07; no separate provider qualification or implementation task. | retired |

#### Fresh child success qualification

`check_e2e_fresh_child_allowed` / `fresh_child_allowed.PLAN` /
`FreshChildAllowedJourney` qualify fresh positive-daily-time child entry:
Parent enables 15 minutes with saved balance readback; a newly observed Parent
desktop switches to GDM; `onpc_gdm::sign_in_challenge` binds two fresh ordered
`gdm-child-recipient` proofs to sealed single-use UI19 input.
`gdm-child-list` selects the exact fixture; `fresh-child-desktop` reads
`CHILD_ACCOUNTS[CHILD]` and requires two seconds of complete usable,
prompt-free Shell observations. Stale/mixed/wrong-role proofs, uncertain input
and failed durable acknowledgement stop without replay.

Qualified tuple: Ubuntu 26.04, GDM `50.1-0ubuntu0.1`, Shell
`50.1-0ubuntu1.2`, `en_US.UTF-8`, `[["xkb", "us"]]` at greeter/desktop.
This does not qualify retained entry, another provider tuple or a complete case.

#### Fresh child time denial and return qualification

`check_e2e_unlock` / `fresh_child_denied.PLAN` /
`FreshChildDeniedJourney` qualify zero-daily/no-grant fresh-child denial
through the same guarded GDM challenge. `fresh_desktop('child', 'time-denied')`
and `AccessibleUI.gdm_child_time_denied` require the intended child, hidden
account list, specific English account-expiry explanation and no desktop access;
generic failed authentication is insufficient. The tuple is the fresh-child
tuple above.

`rejected_gdm_return` / `onpc_gdm::return_from_time_denial` freshly observe
and consume the rejected prompt before one Escape. The next public state must
be a usable account list or that child's empty, focused masked prompt; only the
latter authorizes one additional Escape. Final usable account-list observation
is mandatory. Discard transition scopes containing defunct nodes and reacquire
within the existing deadline. Persistent stale state, wrong/ambiguous owners or
recipients refuse before input/acknowledgement. Never replay credentials or
accept a prompt as the final destination. Retained lock/unlock remains separate.

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
| DESK03 | C | Lock and switch to the greeter while retaining the fixture desktop. Independently check the original session and usable GDM destination. | `session_control.observe` uses the bound user's public ScreenSaver lock and GDM switching API over guarded SSH; `onpc_desktop_session::switch_user` then observes GDM01. Logind's transient `opening` state is observed without treating it as a ready input source or greeter destination; foreground status is independent while a session opens or closes. `check_e2e_desktop_session` qualified a fresh installed Parent entry, one switch, independent source locked/inactive readback and usable GDM using its then-current installed snapshot, then requalified it in a separate restored attempt alongside DESK04; private collection and owned cleanup passed. [Fresh child qualification](#fresh-child-success-qualification) additionally consumes a newly observed Parent `repeat-desktop` proof after allowance preparation. No Quick Settings. Other fixture bindings and retained-window behavior remain pending. | pending; fresh and newly reobserved Parent switch bindings ready |
| DESK04 | C | Log out the bound fixture desktop and independently check that its session ended and GDM is usable. | Shared `session_control.observe` invokes `gnome-session-quit --logout --no-prompt` once as the bound user over guarded SSH, verifies the source session is logged out and a greeter session is active; `onpc_desktop_session::log_out` then observes usable GDM01. Convergent logind reads exclude `closing` records, whose users have logged out while leftover processes remain; live inactive/locked sessions still block fresh entry. `check_e2e_desktop_session` qualified a fresh installed Parent desktop, direct logout and independent GDM result, then requalified DESK03 in a separate restored attempt; private collection and owned cleanup passed. Complete case 22 additionally passed approved Riley logout and independent usable GDM on Ubuntu 26.04 in `20261030T003818Z-f8c88376`. No logout-dialog/Cancel or forced-termination fallback. Other fixture/platform bindings remain pending. | pending; fresh Parent logout and approved Riley logout on Ubuntu 26.04 ready |
| DESK05 | C | Explicitly lock through Super+L or the supported session lock API and independently observe the lock surface. Never manufacture natural expiry. | `onpc_desktop_session::lock` consumes a fresh desktop proof, invokes shared `session_control` Lock once and calls DESK06. `desktop_session.LOCK_PLAN` / `SUPPLIED_LOCK_PLAN` qualify separate command and independently supplied Super+L attempts. No system-menu navigation. [Parent scope](#parent-lock-surface-qualification); child command Lock passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). | fresh Parent command/Super+L and child command Lock ready; other bindings pending |
| DESK06 | C | Observe the intended user's lock surface: password challenge or native time restriction. Input declares curtain or already-open challenge; reveal with one normal key only for curtain. | `journey_blocks.lock_challenge` / `onpc_desktop_session::observe_lock` and `AccessibleUI.shell_lock_snapshot` bind the sole local locked declared fixture session and its Shell-owned public window. Curtain requires the English unlock hint and fresh scoped focus before one Space; challenge reads the public intended-fixture identity and focused password role without contents or secret authority. Wrong-session, other-surface, ambiguity and replacement guards retain independent result readback. [Qualified scope](#parent-lock-surface-qualification); child curtain/reveal and challenge read passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). The child's native configured-zero restriction passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification), through the same guarded curtain reveal. Recipient proofs are qualified separately. | Parent and child curtain/reveal and independent challenge read and child native zero-time restriction ready; other bindings pending |
| DESK07 | A | Qualify the lock-screen recipient, masked empty focused field and intended identity independently of GDM. | `journey_blocks.lock_recipient` / `onpc_desktop_session::lock_recipient`, `AccessibleUI.lock_surface` and `UiObservations` bind two ordered fresh proofs to the same actual lock window and password field. `desktop_session.LOCK_RECIPIENT_PLAN` / `LockRecipientQualification` independently qualify the Parent command-lock binding. [Parent scope](#parent-lock-recipient-qualification); the shared `account='child'` proofs passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). | Parent and child command-lock recipient proofs ready; other retained-user bindings pending |
| DESK08 | C | Attempt normal unlock with an explicit expected success or time-limit restriction on the observed surface. GNOME's configured-zero native lock restriction blocks authentication before password entry; retained GDM denial follows real authentication. | Actual lock success: DESK06 → DESK07 twice → UI19 → UI05(Enter) → GDM06/DESK01 through `onpc_desktop_session::unlock_success`. Native restriction: guarded curtain reveal through `onpc_desktop_session::reveal_lock` → `AccessibleUI.lock_surface('child-lock-time-denied')`, requiring the specific native explanation, absent password input and no desktop access. Never activate Ignore, which requests more time. Retained GDM: GDM02 → GDM03 twice → GDM05/UI19 → UI05(Enter) → independent success or authenticated time denial. Never interchange proofs. See [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification) and [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification). | pending; stated child lock-screen/retained-GDM success and configured-zero restriction/denial ready; other bindings pending |
| DESK09 | C | From another usable desktop, visit a specified retained user's desktop without replacing it. Inputs include target account and expected unlock result. | DESK03 → GDM02 → the actual GDM reauthentication branch of DESK08 → DESK01. GDM selection does not directly enter the child's lock screen; actual lock entry needs independent DESK06 observation before that DESK08 branch. Fresh entry explicitly uses DESK03 → GDM07 instead. `journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop` qualify [both retained child visits](#both-retained-child-desktops-and-explicit-entry-modes). `onpc_parent::open_for_child` retains the [Jordan → Jamie Parent entry](#retained-parent-desktop-and-window-entry) and adds Riley → the same Jamie/Riley window in that two-child history. | fixed retained Parent and both child visit bindings ready; other-parent management remains separate |
| DESK10 | C | Activate a named existing window with the simplest reliable public focus action or bounded shortcut, then verify that window is active. | `AccessibleUI.window_switch_ready` → `onpc_feedback_read::activate_existing_window` (one Alt+Tab) → `window_switch_proof`; compare recorded public endpoint/PID and preserved synthetic draft. [Qualified scope](#same-desktop-window-activation). No logout or relaunch. | Parent, feedback and supporting GPL viewer ready; diagnostic exports use FILE08 without a viewer |
| DESK11 | C | From an observed locked fixture session, use the shared greeter-return command; from an observed rejected GDM prompt, use Escape. Preserve the denial observation before leaving and independently require the usable account list. Select the route from the declared source; never try alternatives after uncertain input. | Locked desktop: `session_control.observe` with the bound `return-greeter` action preserves the locked session and invokes GDM's public API without another Lock. Rejected GDM: `rejected_gdm_return` / `onpc_gdm::return_from_time_denial` compose fresh provider observation → UI05(Escape) → GDM01; [qualified child denial return](#fresh-child-time-denial-and-return-qualification). The pre-authentication locked-child command return passed [successful child unlock and retained GDM qualification](#successful-child-unlock-and-retained-gdm-reauthentication-qualification); both native lock restriction and authenticated retained-GDM denial returns passed [retained denial qualification](#retained-child-time-restriction-and-greeter-return-qualification). No lock-screen Switch User button or menu navigation. | pending; fresh rejected-child GDM, pre-authentication locked-child and both retained time-denial returns ready; other bindings pending |
| DESK12 | C | Resolve the product panel API surface from the observed unlocked child desktop, including a caller-declared fullscreen activity. Require the current session and logical control availability. | DESK01 → shared `child-panel` client → UI01/UI02. `AccessibleUI.overlay_panel_target` binds `child-request-button`; the adapter owns desktop/session details. See [overlay entry qualification](#overlay-entry-qualification). E2E-024 retains real gameplay and request/return outcomes without focus or pointer revelation. | normal request entry and open-overlay history retained; other bindings keep their existing scope |
| DESK13 | A | Set the explicitly bound fixture user's desktop language to one declared installed locale through a supported system API, then independently read back that account's language. Do not change product preferences, another account or the observer locale; no implicit logout/login. Return the confirmed setting and whether session renewal is required. | `AccountLanguage.submit` / `confirm` in [account_language.py](../../tests/e2e/account_language.py), with AccountsService `User.SetLanguage` and independent `Language` API reads in [account_language_guest.py](../../tests/e2e/account_language_guest.py). `check_e2e_desktop_language` qualified Jordan → `zh_CN.UTF-8` on every enabled VM (Ubuntu 26.04), confirming Ubuntu's normalized `zh_CN` and required renewal. Greeter/account/locale refusals, Chinese FIX06, independent readbacks, preservation, collection and owned cleanup passed. The Chinese lifecycle qualification's recipe owns explicit renewal and public fresh-desktop observation. [Language preparation contract](#chinese-language-preparation-and-desktop-language-setup). | ready for the Jordan Chinese setting binding |

#### Parent lock surface qualification

`check_e2e_lock_surface` qualifies fresh Parent command Lock and independently
supplied Super+L, curtain/reveal and challenge readback. Its Ubuntu 26.04 tuple
is Shell `50.1-0ubuntu1.3`, `en_US.UTF-8`, `xkb/us`.
No password content, secret authority or unlock submission is involved.

`AccessibleUI.shell_lock_window` binds the actual unique unlock window.
Other showing Shell windows must be strict ancestors without independent
lock/authentication controls; require unique ancestry and exclusive ownership.
Cycles, shared paths, siblings/descendants, replaced windows and outside-window
focus/password/dialog/modal markers refuse. Preserve protected traversal,
session recheck and fresh reveal proof before one Space; wrapper identity alone
cannot authorize input. Independently reread the same challenge/locked session.

#### Parent lock recipient qualification

`check_e2e_lock_recipient` qualifies Parent command-lock recipient proofs
on Ubuntu 26.04/Shell `50.1-0ubuntu1.3` and Fedora 44/Shell
`0:50.5-1.fc44`, both `en_US.UTF-8`, `xkb/us`.
Require two ordered empty/masked/focused proofs for the intended recipient on
the same actual lock window and field, followed by an independent challenge.
Read only character count, never password contents. GDM proofs, changed
challenges, observations at least 30 seconds old and failed durable
acknowledgements refuse. This submits no password; other users/tuples remain
pending.

#### Successful child unlock and retained-GDM reauthentication qualification

`check_e2e_retained_unlock_success` qualifies the independent
`desktop_session.CHILD_UNLOCK_PLAN` and `RETAINED_UNLOCK_PLAN` routes.
Public Parent setup supplies 15 minutes; fresh child entry opens the declared
native activity. Command Lock must preserve that session and original work.

| Target | GDM | Shell | Locale / keyboard |
| --- | --- | --- | --- |
| Ubuntu 26.04 | `50.1-0ubuntu0.1` | `50.1-0ubuntu1.3` | `en_US.UTF-8` / `[["xkb", "us"]]` |
| Fedora 44 | `1:50.3-1.fc44` | `0:50.5-1.fc44` | `en_US.UTF-8` / `[["xkb", "us"]]` |

Direct unlock composes `journey_blocks.lock_challenge`, two fresh
`lock_recipient(account='child')` proofs, `onpc_password::enter_lock_password`
and `onpc_desktop_session::unlock_success`.
The retained-GDM route uses `return-greeter` without another Lock, then
`onpc_desktop_session::retained_gdm_unlock` /
`onpc_gdm::sign_in_challenge` with the distinct `retained-login` identity
and two fresh GDM proofs. GDM authenticates before activating the retained
desktop. Never interchange GDM/lock proofs. Wrong recipients, unlocked entry,
replaced challenges or uncertain input refuse.

After either route, independently compare the same activity PID, public
endpoint and synthetic draft, perform its ordinary action in that original
window and compare again. These bindings qualify work continuation and
pre-authentication locked-child greeter return, not natural expiry, other
users/tuples or complete cases. Numeric progression is
[separate](#minute-countdown-progression-qualification).

#### Retained-child time restriction and greeter return qualification

`check_e2e_retained_unlock` qualifies
`desktop_session.RetainedDenialJourney` with `RETAINED_DENIAL_PLAN` /
`CHILD_DENIAL_PLAN` and `onpc_desktop_session::qualify_retained_denial`
on the tuples above. After positive-time admission, Switch User preserves the
child and Parent publicly changes daily/grant to zero.

Retained GDM uses two fresh same-child GDM03 proofs and one sealed submission,
then independently observes the specific time-limit explanation/no desktop and
returns to a usable list. Native configured-zero Shell restriction instead
shows **Screen Time Limit Reached** and **Daily limit for screen time on this
device has been reached. Resume tomorrow.**, with no password input or desktop
access. `child-enter-locked` activates the preserved session through logind
without authentication/unlock/relock. Guarded reveal precedes
`AccessibleUI.lock_surface('child-lock-time-denied')`; require the same actual
window and preceding reveal proof. Never activate Ignore. This is a
pre-authentication restriction, not authenticated lock/PAM denial.

Wrong-session, stale/replaced/ambiguous surface, incomplete tree, mixed password
input and nonspecific/duplicate messages refuse. Both branches return through
DESK11 and compare `child-retained-locked` identities before/after, requiring
the same preserved locked child. `journey_checks.RetainedSessionJourney`
uses explicit immutable endpoints independent of stage names. Natural exhaustion,
other bindings and complete cases remain separate.

### Same-desktop window activation

DESK10 uses `window_switch.PLAN`, `onpc_feedback_read::run_window_switch`
and `check_e2e_window_switch` for Parent/feedback and the supporting GPL viewer.
Resolve active source and inactive destination together before one Alt+Tab,
then independently require the named destination ACTIVE with unchanged public
endpoint/PID, synthetic draft/reply, attachments and controls.
Missing/replaced/wrong-owner/ambiguous windows, prompts, lost focus and uncertain
input stop without fallback shortcut or relaunch. GTK top-level
`Component.GrabFocus` is unsupported.

Parent/feedback retain owned IDs. The Text Editor provider uses
`license_viewer_snapshot`'s sole owned window/`view` ID and bounded GPL
content; launch its installed LICENSE by shared command, never title.
Launch/readiness/metadata/close absence/final window use complete-tree bounded
read-only waits. Submit launch/close once; an incomplete shutdown tree cannot
prove absence, and a missing viewer must refuse reactivation without relaunch.
Qualified supporting tuples: Ubuntu Text Editor `50.1-0ubuntu0.1` and
Fedora `0:50.1-1.fc44`, `en_US.UTF-8`, `[["xkb", "us"]]`.
Arbitrary switcher order, extra apps and other viewers remain unqualified.
Diagnostic export uses FILE08/same-dialog readback without a viewer.

### Retained Parent desktop and window entry

DESK09/FLOW01 use `journey_blocks.retained_parent_entry`,
`retained_parent.PLAN`, `onpc_parent::open_for_child` and
`onpc_desktop_session::qualify_retained_parent`.
The fixed qualified binding returns from Jordan to Jamie through Switch User,
two ordered GDM recipient proofs and real authentication, preserving the
Riley-selected Parent window, App Limits page and enabled 15-minute settings.
An independently supplied Parent entry covers same-user retained entry.

`AccessibleUI.retained_parent_operation` captures the incoming page and verifies
the selected child without reselection before reaching Screen Limits.
`journey_checks.RetainedDesktopJourney` compares caller-declared immutable page,
settings and endpoint/PID observations before reply; `session_control`
separately requires the same active unlocked desktop session.
Current qualifiers compare the original Parent directly without a viewer tour;
these shortened sequences still require live verification. Wrong child/page/
settings/window/session, missing baseline and malformed observations refuse.
Normal closure must make later absent-window entry refuse without relaunch.
Second-parent management remains separately pending.

### Both retained child desktops and explicit entry modes

`retained_entry.PLAN` / `RetainedEntryJourney` and
`onpc_desktop_session::qualify_retained_entry` bind DESK09/FLOW15 to
`journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop`.
`session_control.entry_identity` rejects incompatible sources without repair.
The finite binding enters Riley and Jordan, captures their distinct native
activities, checks same-user and wrong-mode entry, switches between their
retained desktops and revisits Riley. Match original sessions/window/activity
fingerprints before new input, require both original windows usable, and
exercise Riley's ordinary lock/unlock.

Riley→Jamie's original Riley-selected Parent return preserves desktop, endpoint,
App Limits and settings. FLOW01 reaches Screen Limits without reselection.
The shortened direct-comparison qualifier still needs live verification.
After public zero-time setup, retained Riley GDM authentication and native lock
entry independently produce their different time-denial results and preserve
the same locked session through greeter return. Locked-session entry retains
[focus synchronization](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement)
and foreign-recipient refusal. Diagnostic probes/replays supply no acceptance.
Scope is these finite child/Parent bindings; other-parent management and complete
cases remain pending.

### Personal-language selection

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| LANG01 | C | Observe the owned frontend's untouched first-run language chooser or open its public Preferences chooser; read the checked choice and native names, select one declared candidate, apply Save or Cancel once, and independently observe closure, readiness, translated labels and the retained choice after reopening. Callers own language/account values, relaunches, isolation and policy comparisons. | `AccessibleUI.language_scope`, public chooser Save/Cancel/readiness operations, `parent_language.py` and `onpc_parent::language_selection`. `initial-language` observes untouched presentation; ordinary `parent-window` may perform setup. Reacquire stale chooser reads within the original deadline, without input replay. See the qualified bindings below. | pending overall; stated Parent, fixed Jordan kiosk, fixed Riley overlay and Jordan/German–Riley/Hebrew station restoration/approver isolation bindings qualified (see below); Parent inherited dialogs qualified below; other isolation bindings, panel, other inherited dialogs and Hebrew logical text, countdown and complete-case acceptance remain separate |

The language reader compares public visible text and accessible labels
independently against caller-owned literals. Shared IDs stay language independent.
An untouched chooser must be read before generic startup setup or Save.
Qualification is surface/account specific:

| Binding | Shared callables and qualified scope |
| --- | --- |
| Parent chooser | `check_e2e_parent_language`, `read_parent_language`, `parent_language_management/operation/state`: Ubuntu 26.04, untouched English/native names, English/German/Simplified Chinese/Hebrew Save/readback, Chinese Cancel preserving German, relaunch persistence and unchanged selected child/zero allowance/app policy. |
| Jordan kiosk | `kiosk_language.PLAN`, `onpc_request_flow::kiosk_language`, `read_kiosk_language`, `kiosk_language_form/policy`: same four-language Save/Cancel/German-reentry scope; request values and public policy unchanged. The [baseline binding](#c04l-kiosk-language-and-human-pause) renews both targets and adds only the 90-second initial-chooser pause. |
| Riley overlay | `overlay_language.PLAN` / `OverlayLanguageJourney`, `onpc_request_flow::overlay_language`, `read_overlay_language`, `overlay_language_operation`: Ubuntu 26.04, child application/active Riley session, untouched and reopened UID-bound chooser, same four languages/Cancel, fixed request and German direct-command relaunch without automatic startup setup. |
| Selected-child kiosk restoration | `kiosk_language_restoration.PLAN` / `KioskLanguageRestorationJourney`, `onpc_request_flow::kiosk_language_restoration`: Ubuntu 26.04, Jordan/German and Riley/Hebrew restoration, approver independence, fresh reentry, unchanged policy/time/apps and Parent English. Each child retains 1800 seconds, hidden custom text and excluded soft apps. |
| Enabled Parent isolation | `ParentLanguageIsolationJourney` / `ISOLATION_PLAN`, `onpc_parent::qualify_language_isolation`, `check_e2e_parent_language_isolation`: Jamie/Chinese on Ubuntu 26.04, Riley→Jordan→Riley, separate immutable English 60-minute policy/name/balance captures, zero grants and public readbacks/relaunch within 600 seconds. |

Kiosk untouched reads use `initial_kiosk_child` within one complete owned
snapshot, preserving selected UID/uniqueness/visibility. Parent readers cannot
qualify another application. After `select_kiosk_account`, confirm selected UID,
discard that snapshot, then independently read readiness/language; a mixed-time
traversal must not suppress setup. `CHINESE_LANGUAGE_OPERATIONS` supplies only
its fixed Save/form binding.

Retained Parent return uses fresh desktop/window receipts. Final child selection
uses `journey_blocks.custom_child_selection` /
`onpc_allowance_boundaries::select_child` through canonical
`parent-child-selector` values and independent loaded-control readback.
Legacy `open/focus/selected` stage names require no popup or keyboard focus.
An untouched reopened Parent may select Jordan as the first listed child;
language persistence does not imply child-selector persistence.

Enabled English/Chinese reads use
`AccessibleUI.parent_language_state(child=..., enabled=True, language=...)`;
the disabled-zero reader remains separate.
`time_explanation/reach_time_explanation` carry explicit language, and
`app_rows(include_names=True)` reads complete public names/policy rows.

#### Enabled Parent Hebrew policy qualification

`check_e2e_parent_hebrew_policy`, `ParentHebrewPolicyJourney` /
`HEBREW_POLICY_PLAN` and `onpc_parent::qualify_hebrew_policy` qualify
Ubuntu 26.04 Riley enabled/60-minute English→Hebrew→English reads.
Capture original UID/account/application identities, complete policy and balances.
Require closed chooser, translated management labels/accessibility names,
unchanged enablement/allowance, zero grant, daily balance positive and at most
3600 seconds, and daily=total. Compare immutable captures within 600 seconds
with two-second refresh/formatter tolerance. Decode Hebrew public duration
text numerically; translated text alone does not prove policy preservation.

The finite `parent-language-riley-enabled-he` binding,
`duration_projection` and `language_composition.language_policy` preserve
English/Chinese/default readers. `onpc_parent::language_presentation_roundtrip`
shares Save/reopen/Cancel and retained choice; historical Cancel/Tab/Save focus
is no current acceptance condition.

`check_e2e_parent_rtl` / `ParentRtlJourney` / `RTL_PLAN` and
`onpc_parent::qualify_rtl` separately qualify the fixed Parent chooser.
Logical text and checked choice provide functional evidence; pixel rendering,
glyph layout, clipping and alignment are outside this acceptance.

#### Parent inherited dialog qualification

`check_e2e_parent_dialog_language`, `ParentDialogLanguageJourney` /
`DIALOG_PLAN` and `onpc_parent::qualify_dialog_language` qualify fixed
Parent English→Hebrew→English About/ordinary-feedback reads on Ubuntu 26.04.
Seed body `שלום Alex 75` and reply `rtl-check@example.invalid` once and
independently compare before new input after normal close, language change and
reopen. Preserve product/license/account names, selected child, disabled zero
allowance and app policy. No Send or external-link action.

`AccessibleUI.parent_dialog_presentation/parent_dialog_operation` share
`open_about/open_feedback/feedback_snapshot`, the `synthetic-rtl` projection
and normal `onpc_text::replace_text` input.
Qualification `dialog_visit` and case `dialog_use` share `dialog_close`
and independent absence; callers own finite visits/comparison endpoints.
Keyboard direction tours are not required. Scope extends UI16, ABOUT01,
FEED01/03 and FEED10(dialog) only for Parent; translated Privacy and other
frontends remain unqualified.

#### Complete Parent Hebrew history

E2E-055/case 256 uses `parent_presentation.PLAN` and
`onpc_parent_presentation::run`, with shared
`language_composition.language_policy/public_language_value`,
`language_save`, `dialog_use/dialog_close` and text input.
Current composition makes one necessary dialog visit per language and saves
only Hebrew and restored English, retaining Riley's enabled 60-minute policy,
zero grant and exact mixed-script draft. The original Ubuntu complete history
does not qualify changed/shortened compositions automatically.
Each immutable capture is copied and checked for missing/changed/replayed
public values before durable reply; cases do not inherit qualification controllers.

E2E-054/case 255 instead uses `language_persistence.PLAN` /
`onpc_language_persistence::run` and
`language_composition.PublicLanguageJourney` for independent Jamie/Chinese,
Jordan/German and Riley/Hebrew preferences offline through account/approver
changes, Cancel, relaunch, fresh kiosk and renewed child session.
Both children retain Custom `1.25`, 75 seconds and soft inclusion.
`AccessibleUI.language_history_request` scopes station reads to the kiosk
session and overlay reads to Riley; `InternetIsolation` owns recovery.
Compare policy/name/app captures before/after recovery under the recipe's bound.

Remaining compositions and new bindings stay pending. Reuse existing LANG01
and `language_persistence.PLAN` request readers instead of separate 308a/309a
presentation histories. Implement missing finite literal projections and
comparisons in tasks 308/309. Task 308b qualified the fixed translated approval
result below; 310a retains the new panel endpoint projection. The complete cases retain:

| Binding | Required result |
| --- | --- |
| Overlay Hebrew request/approval | Unchanged identities/75-second soft-included choices and original activity; one genuine Shell approval during Hebrew, translated success, usable original work and elapsed-time increment, then one English-restoring reopen. |
| Kiosk Hebrew request | Child's checked language/request survives one approver change and restored English; no repeated About/error-report tours. |
| Panel language/time | Refreshed time language and elapsed balance after each overlay save, unchanged work/policy, then natural expiry without reset or grants. Existing fixed countdown reads do not qualify translation/progression/expiry. |

Use the [language recipes](E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition)
for full values/order. Shared IDs and prerequisite qualifications do not establish
additional translated bindings or complete cases. Missing public text/identity
remains a gate. Mixed-script ordinary feedback belongs to Parent; error-report
drafts end on closure under the
[specification](../Specification.md#feedback-and-error-reports).

### Reminder controls and notification qualification

Shared Preferences and repository-owned reminder banners use the
[Application UI API](Application-UI-API.md#shared-request-form-and-language-chooser)
and [ChildUI notification surface](Application-UI-API.md#child-panel).

| Binding | Exact scope |
| --- | --- |
| `check_e2e_overlay_reminder_editing` | Qualified Riley overlay CRUD, main Save/Cancel, saved empty list on Ubuntu 26.04/Fedora 44. |
| `check_e2e_kiosk_reminder_binding` | Qualified selected-child kiosk saved-ID/overlay continuity, account/approver isolation and public restoration on both targets. |
| `check_e2e_reminder_fullscreen_preference` | Qualified saved false, Cancel of true draft and reopened false on both targets; no delivery credit. |
| Natural reminder | Pending owned body/canonical seconds/urgency and natural-lock removal. |
| Fullscreen banner | Pending enabled delivery/disabled suppression with genuine fullscreen game, independently of urgency. |

`AccessibleUI.overlay_reminder_open/read/editor/delete/fullscreen/commit`
and `UiObservations` validate canonical records and prior draft source.
`OverlayReminderJourney` owns defaults, literal 75/90-second values and
saved-ID comparisons; reopen saved/cancelled/empty drafts and compare language,
fullscreen, request choices and public policy/time with elapsed-time allowance
and no grants. Wrong owner/surface/child, stale draft, unavailable/ambiguous
controls, competing modals and uncertain input refuse.

`KioskReminderJourney` / `onpc_kiosk_reminders::run` use explicit
`surface='kiosk'` and child bindings: overlay saves 90 seconds, station reads
that ID, edits/saves/reopens 75, overlay independently reads 75 with the same ID.
Preserve Jordan defaults/language and Riley through Jamie→Casey/child switches.
Receipts include public `language-dialog.getValue()` lifetime, selected child,
endpoint and draft, preventing same-child replacement reuse.
[Baseline renewal](#c04r-shared-reminder-persistence-renewal) restores only the
created record through delete/Save/reopened-default comparison. No delivery,
reboot or complete-case credit follows.

`ReminderFullscreenJourney` /
`onpc_request_flow::reminder_fullscreen_preference` require a nonempty default
list, Save false/reopen, Cancel true/reopen false, unchanged records/language/
request/policy/time and zero grant. Reject invalid booleans before discovery;
retain draft/loading/busy/availability/input guards. Saved preference alone does
not prove fullscreen banner behavior.

`PreferencesDialog` owns editing/fullscreen settings.
`GnomeApplicationUiAdapter` maps public notification values; `reminderBanner.js`
owns banners outside Shell's generic tray. No generic Shell-notification adapter
is required. Ready the observer before natural threshold; await actual owned
body/urgency/surface flags within its lifetime and deadline. Exact-second
snapshots, urgency alone or expiry cannot prove delivery/suppression.
Missing independent identity/visibility remains a gate. Fullscreen and reminder
complete histories retain current-version reboot/saved-state assertions; schema
migration coverage does not require an older-package customer journey.

#### Kiosk Preferences confinement

`AccessibleUI.kiosk_preferences_confinement` shares request/language/reminder
guards for Language, Reminders, Preset Times and both Add/Edit editor routes.
Bind selected child and Preferences lifetime; reject extra identified controls,
external links or unexpected surfaces. Cancel drafts and leave an independently
comparable usable request. `check_e2e_kiosk_preferences_confinement` /
`KioskPreferencesConfinementJourney` add normal Cancel/greeter return and a
separate engineering process/thread census. API inventory identifies controls,
not anonymous toolkit widgets; source/control audit complements it.
The [confinement design](../SystemDesign/Kiosk-Confinement.md#offense-and-defense-scenarios)
owns defense scope. No saved reminder/preset, delivery or complete-case credit.

### Daily allowance selection

PARENT06 shares `journey_blocks.allowance_selection`,
`onpc_allowance_selection::select`, `gui_blocks.select_allowance` and
`AccessibleUI.select_allowance`. Set the offered canonical
`parent-daily-limit-selector` token; Custom then sets
`parent-custom-daily-limit` text and invokes ordinary validation when required.
Independently observe saving and the final allowance. Retained
`allowance_keyboard` names are compatibility boundaries, not native input.

Resolve current Parent surface, selected child and enabled selector through
the [mandatory API route](../Mandates/UI-Automation-Mandate.MD#application-ui-api),
including after another window or restart. No popup/focus/pointer/compositor
input is required. Preset/custom, rejection, per-child and rapid-save consumers
vary finite values/results while sharing the same mechanics.

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
| SEARCH06 | C | Open Overview, resolve the empty search field by a qualified provider adapter, semantically focus it and independently observe focus before typing the registered app name once. Read back the complete query, then resolve and focus its launchable result. Independently observe result focus as the recipient guard before Enter. | `onpc_shell_search::run` and `AccessibleUI.focus_search_result` check the final query and launchable result. The whole-query route passed in case 3; the historical split-query qualification is recorded below. [Qualified scope](#search-and-standard-sign-in-contracts). Other entries and queries remain pending. | pending; fresh Parent query branch ready |
| SEARCH05 | C | Launch a named app from the app grid and observe its expected opening window. The search route is an explicit argument. | `onpc_parent::open_from_app_grid` composes SEARCH06 and `launch_search_result(journey, proof, expected)`. Both the composed administrator launch and independently supplied `app-grid` management entry passed `check_e2e_parent_search_launch`, with owned window readback, normal close and wrong-entry refusal. Host checks cover wrong/stale proofs, wrong owner/result and uncertain-input non-replay. FIX02's `fixture-requested`→empty commit remains host-checked pending live validation. [Qualified scope](#search-and-standard-sign-in-contracts). | pending; administrator management bindings ready |
| PARENT01 | C | Invoke `oh-no-parent-control-parent` directly as the active desktop user and independently observe the declared management window or access denial. Mandatory for ordinary Parent setup/reopening; no child is selected implicitly. App-grid discovery tests explicitly use SEARCH05/06. | `onpc_parent::launch` consumes the desktop proof, submits the fixed command through `AccessibleUI.launch_parent_command`, then observes `parent-window` or `management-denied`. Case 2 qualifies its fresh `reboot-desktop` proof; case 6 requalified the default fresh standard denial/return binding. The fresh Parent desktop binding also passed in case 151. No terminal/search input. [About scope](#about-block-contracts) and [clean installation](#clean-installation-journey). | ready for fresh Parent/standard and post-reboot Parent bindings; a second same-session Parent launch with one-window readback passed in case 159; other entries pending |
| PARENT02 | C | Set Parent's child selector to the canonical eligible UID, verify the selected identity and wait for that child's controls. | `onpc_parent::select_child`, `AccessibleUI` and UI15 share the `parent-child-selector` API setter and independent `selected_child` readback. Child/existing/new/returned bindings retain their finite identities. [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| PARENT03 | C | Read the current selected child's identity, screen-limit switch, allowance and remaining-time section as a sanitized observation. Do not change selection; disabled allowance controls remain readable. | `AccessibleUI.settings(child)` reads the explicit child, switch and duration-label projection and reveals the remaining-time section. When the selector displays `Custom value`, read bounded whole minutes from the identified custom editor; retain the numeric value in the snapshot, never just the mode label. Scenario expectations remain in `parent_discovery.PLAN`, not the adapter. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| PARENT04 | C | Select Screen Limits or App Limits and require that page's named usable controls. | `AccessibleUI.parent_page(child, page)` checks the displayed child, selects one named page, then observes its controls. Reacquire the window after transition and reuse that local root for search/filter reads. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| PARENT05 | C | Select a daily preset through PARENT06 and independently read the saved allowance. Custom selection makes the ordinary editor available. | `AccessibleUI.allowance_preset` / `custom_allowance` delegate to `select_allowance` and PARENT08. Reload checks retain selected-child and reopened saved-value assertions. | API implementation; historical saved-value and persistence evidence retained |
| PARENT06 | C | Set `parent-daily-limit-selector` to an offered canonical duration or `custom`; set custom literal text and invoke normal validation. Observe saving separately. | `journey_blocks.allowance_selection`, `onpc_allowance_selection::select`, `AccessibleUI.select_allowance` and `gui_blocks.select_allowance` share the API route. Retained `allowance_keyboard` naming supplies input/result boundaries without native input. Custom, rapid-save, per-child and restart assertions remain in their existing callers. | API implementation; historical saved-value and persistence evidence retained |
| PARENT08 | C | Wait for the declared saved, rejected or unavailable result and independently read the final value. Preserve selected-child identity, rejection recovery and last-change-wins ordering; intermediate Saving and control inhibition are not acceptance. | `parent_save_snapshot` verifies selected UID/label, expected availability and no error report. `invalid_allowance` observes empty/abc/-1/0.5/1440/1441 rejection from saved 15 and independently unchanged saved/reopened values. `parent_app_save_snapshot` covers usable App Limits after match response. `check_e2e_parent_save/allowance_boundaries` qualify saved/custom-validation snapshots. Rapid-save callers independently verify final accepted per-child/reopened values; `observe_accessibility_input` retains tokens/single input/final readback. Intermediate inhibition/Saving is no acceptance requirement. Cases 158/159 own full histories. | pending overall; saved and custom-validation snapshots qualified; historical transition samples retained as evidence only |
| PARENT20 | C | Read an already expanded, showing remaining-time explanation for the explicitly selected child. Return daily, one-time and total values, public display precision and observation time. Perform no navigation or expansion. | `AccessibleUI.time_explanation(child)` reads the selected UID/label and showing `parent-time-status`, `parent-time-explanation` and collapse control in one complete public snapshot. `duration_projection` returns each bounded compact text, seconds and one-second display precision; `observed_monotonic_ns` timestamps the read. `UiObservations` validates the transport projection. `time_explanation.PLAN` / `onpc_time_explanation::run` / `check_e2e_read_an_expanded_time_explanation` qualified a saved 15-minute allowance, explicit collapsed refusal and expansion preparation, wrong-child refusal and two independent 900/0/900-second reads, with collection, owned cleanup and baseline restoration. PARENT20 never expands; PARENT09 and arithmetic/elapsed comparisons remain separate. Historical first consumer: E2E-036 case 161, now [UI-owned](UI-and-E2E-Coverage.md#duplicate-review-and-allocation). | ready |
| PARENT09 | C | Reach the selected child's remaining-time explanation, expanding it only if currently collapsed, then read its balances. | `AccessibleUI.reach_time_explanation(child)` requires the selected child's Screen Limits surface, expands only a proven collapsed section with its public row action, then uses PARENT20. Repeated reads perform no collapse. `check_e2e_time_explanation` qualified independent collapsed/expanded entry, wrong-child refusal and repeated positive/zero reads, including collection, owned cleanup and baseline restoration. Use PARENT20 for read-only observation; neither block visits another desktop. | ready |
| PARENT12 | C | Read a displayed app row's identity, access choice and match choice. | `AccessibleUI.app_rows(child, maximum=256, expected_ids=None)` returns immutable public ID/access/match triples; `AppRowsObservation.from_rows` validates the controller projection. UI01 → UI02 → UI03, without installed-catalogue or executable probes. Fresh selected-child defaults, independent App Limits reread and wrong-child/page refusals qualified by `check_e2e_app_row_observations`; [scope](#app-row-observations). Declared native [search](#catalogue-search) results are qualified; filtering and policy edits retain their separate pending consumers. | ready for selected-child row observations |
| PARENT10 | C | Search the App Limits catalogue by name, description or launcher identifier and observe the matching displayed rows, including an explicitly expected empty set. | `onpc_app_rows::search` composes UI16 replacement with caller-named UI13 row read and independent controller comparison. Representative query, filter and combined-result checks use the shared native oracle and worker composites in UI preview; installed name, absent and clear results passed `check_e2e_catalogue_search`, and combined precise/Allowed passed `check_e2e_catalogue`. See [catalogue search](#catalogue-search) and [catalogue filters](#catalogue-filters). Row details use PARENT12 separately. | ready for declared native queries and filter combinations; complete cases remain separate |
| PARENT11 | C | Set one named App Limits filter's explicit canonical selection set and observe the exact displayed result set. Both access-rule and match-rule selections use the same API operation. | `onpc_app_rows::filter` sets explicit canonical key lists on match/access filter IDs, then caller-owned UI13/UI12 compare complete rows through `native_fixtures.catalogue_rows`. No popup/Escape. See [filters](#catalogue-filters). | ready for declared Parent App Limits selection sets; complete cases remain separate |
| PARENT13 | C | Open a named app's Edit Match Rule dialog and read its current rule. | `AccessibleUI.open_match_rule` / `read_match_rule(editor=True)` through `onpc_app_rows::match_editor`; owned Parent, selected child, complete row and app-bound dialog guards. See [Match editor Save and Cancel](#match-editor-save-and-cancel). | ready for the declared native fixture binding; other app bindings pending |
| PARENT15 | C | Apply Save, Cancel or Reset to the open match editor and observe the explicitly expected result. Empty/unrelated precise text stays in the editor; a rejected wildcard closes it and opens a failure report. Do not close that report implicitly. | `AccessibleUI.respond_match_rule` through `onpc_app_rows::match_response`: one guarded Save/Cancel/Reset response → UI11(editor) → `parent_app_save_snapshot` (PARENT08) → independent public row read. Local invalid Save instead reads the retained exact draft and rejection description. `MatchRuleJourney` compares the caller's captured old rule after Cancel, exact supplied new rule after Save and detected default after Reset. See [Match editor Save and Cancel](#match-editor-save-and-cancel). The `rejected` response proves the declared rejected draft, invokes Save once, observes editor disappearance and leaves the automatic report open; see [automatic Parent error reports](#automatic-parent-error-reports). Caller uses FEED15/UI18 before reading restored rows. | ready for ordinary Save/Cancel/Reset, local invalid drafts and the declared rejected-directory/report slice; other bindings pending |
| PARENT16 | C | Choose Allowed, Hard blocked or Soft blocked for one displayed app; observe save and displayed choice. | `onpc_app_rows::access_choice(journey, save, row)` composes `AccessibleUI.choose_app_access` (UI15/PARENT08) and `read_app_access` (PARENT12); `AccessChoiceJourney` compares the caller's exact expected public choice. See [Public access choices](#public-access-choices). | ready for native fixture A and the existing child; other app bindings pending |
| PARENT17 | C | Open revocation confirmation and read its target and warning about time, blocked apps and daily allowance. | `AccessibleUI.open_revoke_warning(child)` / `revoke_warning(child)` bind the selected child and owned dialog before reading its public warning and responses. `RevokeCancelJourney` and `RevokeConfirmJourney` compose a real 75-second soft-included kiosk grant and retained Parent return. See [warning/Cancel qualification](#revocation-warning-and-cancel-qualification) and [Confirm qualification](#revocation-confirm-qualification) for independent entries and target/authority refusals. | ready for the fixed warning/target binding |
| PARENT18 | C | Cancel or confirm the open revocation dialog and observe its closure and displayed time/settings. Child effects are checked by later app/access blocks. | `AccessibleUI.cancel_revoke(child)` admits Cancel only; `confirm_revoke(child, confirm=True)` requires explicit authority, rechecks the child-bound owned warning and activates Confirm once. `reload_revoke_settings` reloads the selected child's public status within the controller read bracket; `saved_revoke_balances` independently reads balances, saved allowance, complete app access/match triples and exact rules. See [Cancel](#revocation-warning-and-cancel-qualification) and [Confirm](#revocation-confirm-qualification) qualifications. Child effects remain later consumers. | Cancel and Confirm ready for the fixed balance/policy binding; child effects pending |
| PARENT19 | C | Observe Parent's no-eligible-child explanation together with the `(None)` picker placeholder. Never activate the disabled picker. | `AccessibleUI.parent_empty()` reacquires the Parent window and showing picker, then uses UI03's registered projections for the explanation and sole `(None)` label in one bounded read-only wait. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |

### Revocation warning and Cancel qualification

`check_e2e_revoke_cancel`, `RevokeCancelJourney` / `REVOKE_PLAN` in
`time_explanation.py` and `onpc_time_explanation::revoke_cancel` qualify
Ubuntu 26.04/Fedora 44: real fixture-child/fixture-parent 75-second
soft-included kiosk approval, enabled 15-minute daily settings and retained
Parent. Two independent warnings bind child and time/apps/daily explanation;
wrong-child/Confirm requests refuse. Cancel preserves saved settings and
daily/grant/total within controller elapsed-time/precision bounds.
The sealed approval-only journey retains credential authority, fresh replies,
capture and single-use guards; unknown/stale/replayed/uncertain input refuses.
This is warning/Cancel scope only; child effects and complete cases are separate.

### Revocation Confirm qualification

`check_e2e_revocation`, `RevokeConfirmJourney` / `REVOKE_CONFIRM_PLAN`
and `onpc_time_explanation::revocation` qualify the same fixed both-target
setup. Require selected-child warning and explicit Confirm authority; one
Confirm closes it. Independently read grant zero, elapsed-bounded unchanged
daily balance/allowance, complete app access/match triples and exact match rules.
No child session/app launch is included.

Parent's periodic displayed status can be 30 seconds old. Both readers publicly
reselect the guarded child to load fresh status within the controller read
bracket, without changing saved policy/grant or relaxing time/precision checks.
Other bindings, child effects and complete cases remain pending.

### App-row observations

`AccessibleUI.app_rows(child, maximum=256, expected_ids=None)` resolves owned
`parent-app-rows`, selected child and loaded App Limits controls.
One complete API traversal returns sorted immutable `(ID, access, match)`
triples within 45 seconds; off-viewport rows need no scrolling, filtered rows
are excluded. Missing/duplicate/stale/incomplete/ambiguous/wrong-owner reads
refuse. `expected_ids` compares the complete displayed set, including empty.
`AppRowsObservation` validates replies up to 32,768 bytes while ordinary
replies keep their bounds.

`onpc_app_rows::read_rows(journey, stage)` reads one caller-owned stage;
the compatibility one-argument form retains the full qualifier sequence.
`AppRowJourney` / `onpc_app_rows::run` /
`check_e2e_app_row_observations` qualify nonempty fresh Allowed rows,
wrong-child/page refusal and unchanged reread after page reopening.
Search/filter/edit/enforcement and complete cases remain distinct scopes.

### Catalogue search

`onpc_app_rows::search(journey, binding, result_stage)` composes public text
replacement and caller-owned complete row comparison.
Finite bindings: `catalogue-name=ONPC Allowed Fixture`,
`catalogue-absent=ONPC Absent Catalogue Fixture 077b`, and `catalogue-clear`.
`AccessibleUI.text_recipient` requires owned Parent/selected UID/usable page/
editable field; set `parent-app-search` once, then independently read exact
text and debounced rows. Never replay input.

`CATALOGUE_ROW_OPERATIONS` binds Jordan result/reopening reads and complete
expected IDs; clear restores all four declared fixtures and the entire initial
collection. Incomplete expected sets refuse.
`catalogue_search.py` / `check_e2e_catalogue_search` qualify native
verification, independent entry, name/absent/clear/reopening and unchanged rows.
Shared finite query/ID/access/match oracles live in `native_fixtures.py`;
other queries/filters/complete cases retain their own scope.

### Catalogue filters

`AccessibleUI.catalogue_filter(child, kind, mask, action)` binds
`match-rule=pattern/precise` and
`access-rule=allowed/conditional/permanent`.
Set the full canonical key list, including none/all, on the declared filter
through UI15 once; independently read complete rows. Require current owned
Parent/selected child/usable page; wrong child/page, missing/duplicate options
and uncertain input refuse. No popup/focus/Escape.

`onpc_app_rows::filter` / `journey_blocks.filter_screens` declare finite
operations with caller-owned stages. `native_fixtures.catalogue_rows` owns
name/description/identifier/empty/absent and subset expectations without requiring
their Cartesian GUI product. `catalogue.py` / `check_e2e_catalogue` qualify
Jordan's native precise/Allowed installed sample, independent entry/refusals and
clear/unchanged rows. Full representative local matrices stay in UI.

`CataloguePolicyJourney` / `JourneyPlan.catalogue_checks` compare copied
initial/unchanged captures or finite query/match/access tuples before reply.
Missing/replayed captures and changed policy refuse; callers own lifecycle.
E2E-041/case 184's shortened direct Parent/Jordan composition preserves initial,
search, combined-filter and unchanged-policy results without allowance writes.
It is qualified on Ubuntu 26.04; Fedora renewal remains unverified.

### Match editor Save and Cancel

`AccessibleUI.match_entry/open_match_rule/read_match_rule/respond_match_rule`
and `onpc_app_rows::match_editor/match_response` bind Jordan's native
`A.desktop` row, owned Parent and app-bound transient editor independently of
entry text. Wrong owner/child/app/page, unavailable/duplicate/hidden/inactive
controls or uncertain input refuse. Invoke one Save/Cancel/Reset; missing closure
never replays it. `parent_app_save_snapshot` independently requires usable
row/search/child selector and no failure report, without transient-saving claims.

Entry preflight uses `absent_id(..., incomplete_raises=True)`: an observed
existing editor refuses; incomplete negative proof/query failure retries only
within its read-only deadline. Keep app/child proof and opened-editor readback;
Open dispatch lies outside retry. Text/read/response preflights also retry only
incomplete/query observations while rechecking owner/child/editor. Persistent
incompleteness/changed recipients refuse; dispatch errors remain uncertain and
retain fixed `ui:match-response-query:action` diagnostics without replay.

Public `parent-match-rule-entry.setText` and row match values supply drafts/
saved rules, never preferences. Qualified precise/wildcard values are
`/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage` and
`/opt/onpc-test-fixtures/Applications/Exact*.AppImage`, including basenames.
Cancel preserves old rule; Save canonically persists/reopens the supplied rule;
Reset closes/saves detected default and independently reads row/reopened editor.
Empty/whitespace/unrelated absolute/basename Save retains exact draft/rejection
without a policy write; editing clears rejection. Full local combinations stay UI.

`check_e2e_match_save_cancel` qualifies independent precise→wildcard
Cancel/unchanged and Save/new-rule results. `match_save_cancel.EDITOR_PLAN`,
`onpc_app_rows::match_editor_validation` / `check_e2e_match_editor` add
empty-input refusal/Cancel and independently opened Reset/default results.
`MatchRuleJourney` / `JourneyPlan.match_checks` compare explicit immutable
ordered captures before durable reply; missing/replayed captures refuse.

`match_rules.match_edit(...)` / `onpc_app_rows::match_edit(...)` compose
entry/read, UI16 and one Save; validate finite bindings/collisions before input.
Ordinary Save requires a separate row endpoint. `match-rejected-directory`
requires `row=None/undef` and ends with the automatic report open; caller owns
review/closure/restored-rule assertions. Complete cases remain separate.

### Automatic Parent error reports

`rejected_parent_rule.PLAN` /
`check_e2e_review_a_rejected_parent_rule_s_report` qualifies Jordan/native A:
confirm `Applications/Exact*.AppImage`, reject
`/opt/onpc-test-fixtures/Rejected/*.AppImage` through normal Save,
read fixed explanation/Error category/actions/synthetic draft, inspect Privacy,
close normally and independently reread last-confirmed rule.
Absent-report entry refuses; Send remains untouched.

`parent_reports.report_review/report_close` / `ParentReportJourney` and
`onpc_feedback_privacy::review_parent_report/close_parent_report` share
review/closure and immutable Privacy draft comparison.
`AccessibleUI.parent_report_operation` reads the already-open report without
activating offered actions. Never replay uncertain editor Save or implicitly
close its report; text retries remain read-only.
Case 205/`parent_error_report.PLAN` /
`onpc_fresh_thirty_allowance::parent_error_report` reviews the first report
then closes a second untouched report through a fresh
`onpc_window::close('parent-report')` proof; compare exact confirmed wildcard
after each. Preserve the [precise-override reload limitation](../SystemDesign/Frontends.md).
Sending/request-report choices and other bindings remain separate.

### Public access choices

`AccessibleUI.choose_app_access(child, app, control)` binds native A
`com.puffyslippers.ONPCTest.A.desktop` with canonical
`allowed/permanent/conditional` choices.
Before one action require a complete current owned Parent snapshot, selected
child, loaded App Limits and available target. Wrong row/child, hidden/disabled/
duplicate/foreign controls and uncertain input refuse; incomplete reads may
retry before input only.

`parent_app_save_snapshot` requires usable management without failure report.
`read_app_access` independently projects the row without navigation/expected
values. `onpc_app_rows::access_choice` takes explicit save/read stages and
no implicit entry. `AccessChoiceJourney` / `access_checks` compare copied
exact choices before reply and may compose `match_checks`.
`check_e2e_access_choices` qualifies Allowed→Hard→Soft and independent
supplied App Limits entry for this native fixture only; enforcement, other
apps and complete scenarios remain separate.

### Public app-policy edits

`policy_edits.policy_edit(app,draft,access,prefix,filters=(),setup=False)` /
`onpc_app_rows::edit_policy` compose finite launcher-identifier search,
optional explicit filters, match Save, access Save and independent reads.
Validate complete binding before input; caller supplies selected-child page and
stages. Never select/reopen implicitly; retain complete row/owner/error-report/
uncertain-input guards.

For preparation, `setup=True` (the optional final `1` in Perl) omits redundant
search-result, old-editor and saved-row observations. The caller must independently
verify the complete saved rules and access choices after preparation, before
exercising the behavior under test. Every input retains its existing guards and
save-completion checks. Active-grant disable uses this route in both attempts;
its changed composition still needs installed qualification before claiming a
new live pass.

`policy_qualification.PLAN` / `check_e2e_policy` qualify Jordan/native A,
both filters, `/opt/onpc-test-fixtures/Applications/*.AppImage` Hard→Soft→Allowed,
unfiltered precise/Soft and independent entry/refusals.
`AppPolicyJourney` adds explicit `check_balances`; case 80 owns its
Jordan 1800/0/1800 setup and exact precise/Allowed results.
Editing qualification does not establish enforcement or a complete case.

Render qualification patterns against all declared fixture names without
omissions before live work. `Exact*.AppImage` is valid editor text but cannot
safely preserve space-bearing ELF nonmatches under the directory guard, causing
the documented blocking warning. FLOW03 uses finite
`match-wildcard-appimages` for those files without altering editor inputs or
weakening report/refusal behavior.

### Public policy legend

`AccessibleUI.expand_policy_legend/read_policy_legend` require owned usable
Parent, selected child and App Limits. Activate `parent-legend-toggle` once
only when collapsed; independently read `parent-legend-content`'s two headings
and five complete access/matching explanations.
Wrong owner/child/page, misplaced/duplicate/stale/incomplete content or uncertain
input refuse. GTK may omit collapsed content or realize it after pressed state;
only the post-input result wait retries absent content within its deadline.
Already-open/standalone reads stay strict; never replay toggle.

`onpc_app_rows::legend` uses explicit stages; `expanded_stage=undef` reads
an independently open legend. `policy_legend.PLAN` / `PolicyLegendJourney`
/ `check_e2e_policy_legend` qualify Jordan balances, independent legend/
wrong-entry reads and immutable unchanged complete policy rows.
Callers own lifecycle/finite expectations; case 184 remains separate.

<a id="c04b-baseline-operation-applicability"></a>
<a id="baseline-qualification-gaps-and-first-consumers"></a>
<a id="cross-plan-baseline-reuse"></a>

### Baseline operation applicability

Compatible fixture preparation and the finite native grant/use/revoke history
formerly scheduled as 313a/313 were delivered through C04p1/C04p. Their duplicate
E2E queue tasks are removed; the scope below remains reusable. Trust accepted
delivery without retrieving old reports or rerunning unchanged qualification.
Changed boundaries receive their affected checks; later customer journeys keep
their own complete public outcomes.

The [baseline recipe](E2E-Scenario-Recipes.md#c04b-baseline-public-use-slice)
defines a finite request/grant/use/revoke history. Reuse exact qualified
operations rather than duplicating feature mechanics. Qualification applies only
to matching caller, package, fixture, provider, locale, keyboard and assertion
scope; a registered selector or historical pass alone supplies no current
acceptance. Engineering session identity is supporting evidence, never a
substitute for a usable public form, grant read or app result.

| Operation | Required public result and scope boundary |
| --- | --- |
| Passwordless station entry | One owned usable form, eligible account sets, selected child/parent, normal Cancel and usable GDM return. A separate session census proves identity only. |
| Request preparation | Independent selected choices and estimate; normal Cancel/reentry preserves the captured choices. Disabled-child request choices and Parent allowance presets remain distinct. |
| Kiosk authentication | Fixed child, approver and request; two fresh same-challenge recipient proofs; one secret submission; explicit approval or rejection. Password-free Cancel is independent of wrong-password rejection. |
| Approved exit | Explicit success followed by the declared automatic/immediate exit and usable destination. Independently read the selected child's grant through Parent; approval UI alone is insufficient. |
| Shared overlay | Qualify its Shell prompt separately from the kiosk's MATE prompt. Preserve the original native-app window, draft/activity, choices and fixed child through rejection, Cancel, approval and desktop return. |
| Native policy effects | Public zero-daily setup; genuine soft-included approval; distinct Allowed/soft-app Submit results; attributed hard-app execution denial; public revoke/Confirm; zero grant and unchanged saved rules; restored time/soft-app restrictions. |
| Existing features | Reuse language Save/Cancel/reentry, request-choice estimates/persistence, reminder identity/isolation and restricted About return as separate feature histories. Saved-preset editing, Hours, What's New and notification delivery retain their own scope. |
| Complete baseline | Compose the ordered negative, approval, activity, revocation and fresh-request results without resets between effects. Operation qualifications do not prove the complete history. |

A 600-second approval does not qualify a different account, natural grant
expiry, parameterized approval matrix or broader complete scenario. The distinct
[120-second profile](#grant-only-time-profile-qualification) has its own qualification.
Daily-only natural-lock qualification does not prove grant-only expiry.
Unknown, ambiguous, replaced or stale recipients and uncertain input refuse
without a replay. Neither timeout nor a missing window proves denial.

#### Short confinement usability history

`check_e2e_confinement_usability` dispatches
[`ConfinementUsabilityJourney` / `PLAN`](../../tests/e2e/confinement_usability.py)
through `ConfinementUsabilityQualification` and
[`onpc_confinement_usability::run`](../../tests/integration/graphical_smoke/lib/onpc_confinement_usability.pm).
The existing installed envelope has a 1800-second worker timeout. The complete
composition is qualified on `onpc-Ubuntu26.04` and `onpc-Fedora44` through
`tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration check_e2e_confinement_usability`.

Its finite history uses Riley/Jamie (`fixture-child`/`fixture-parent`), daily
900 seconds, initial zero grant, Custom `1.25` Minutes (75 seconds), and soft apps
included. Fresh passwordless entry reaches the usable request; wrong-password
rejection and independent authentication Cancel each retain the form and have
their own public Parent zero-grant endpoint before any reset. Genuine approval
exits normally and Parent independently checks the 975-second estimate against
the actual grant and elapsed time. Another fresh passwordless entry reads a
usable request before normal exit. Reentry uses the complete REQUEST03/04 form
result; Parent's periodically refreshed balance is not a fresh operand for a
second estimate comparison. Public revoke/Confirm, zero allowance and
limits-off restoration precede the runner's owned session/VM cleanup. This
short normal-use composition supplies no desktop-defense, fault-variation,
broader feature or complete baseline acceptance.

`check_e2e_basic_locale_auth` reuses this history through
`BasicLocaleAuthQualification` and the [app-only locale fault](../../tests/e2e/basic_locale_auth.py).
Qualified on both declared Ubuntu/Fedora targets, it supplies successful
C/C.UTF-8-only discovery, genuine native approval with independently observed
time, rejection/Cancel without a grant, and restored normal request use.
One temporary service override leaves packaged files and system settings alone;
the existing runner owns VM cleanup. Discovery failure has its separate history below.
This is installed engineering qualification, with no complete E2E-case credit.

`check_e2e_locale_discovery_auth` reuses the same history through
`LocaleDiscoveryAuthQualification`. Qualified on both Ubuntu/Fedora targets, it
makes the app's locale inventory command exit unsuccessfully and verifies the
C/source-text native agent, rejection/Cancel without a grant, genuine approval
with independent time readback, and usable fresh entry after restoring discovery.
The app-only override is removed and the runner completes owned VM cleanup.
This is installed engineering qualification, with no complete E2E-case credit.

#### Child home isolation history

`check_e2e_child_isolation` dispatches
[`ChildIsolationJourney` / `PLAN`](../../tests/e2e/child_isolation.py) through
`ChildIsolationQualification` and
[`onpc_child_isolation::run`](../../tests/integration/graphical_smoke/lib/onpc_child_isolation.pm).
Its finite engineering history temporarily moves inactive Jordan's exact owned
home aside, restarts the broker, checks retained identity and enforcement plus
refusal of the integration-dependent control change, and uses genuine kiosk
approvals with independent Parent time readback for healthy Riley and Jordan.
Restoring the same home and restarting the broker retries activation, followed
by Jordan's fresh genuine request. It reuses the guarded approval, account
selection and public UI operations under the existing 1800-second worker bound.
Qualified on `onpc-Ubuntu26.04` and `onpc-Fedora44`, including fresh usable
reentry and owned cleanup. The restored request refreshes its estimate through
equivalent custom values and dates the grant comparison with the captured
calculation interval. No complete customer-case credit is supplied.

<a id="c04p1-compatible-fixture-applicability"></a>

#### Compatible native fixtures

The finite policy profile uses distinct executable content where enforcement is
content based:

| Role | Target and rule | Instance |
| --- | --- | --- |
| Allowed A | `/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage`, precise | Primary |
| Permanent H | `/opt/onpc-test-fixtures/Applications/Path With Spaces.AppImage`, precise | Distinct executable bytes |
| Conditional S | `/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-3.7.17.AppImage`, wildcard `/opt/onpc-test-fixtures/Applications/Versioned/Lunar Client-*.AppImage` | Secondary |

Builder declarations, baseline inventory, guarded verifier, Parent preview,
policy/launch/owner/denial bindings and command text must agree on full targets.
Preparation leaves every launcher Allowed; the customer history sets policy
through Parent. Preserve the original S payload as an owned untrusted
compatibility file. Do not move fixtures during the history or weaken renderer
warnings/refusals. The source declaration has twelve exact keys: four
executables, four adjacent GUI files and four launchers; Riley's projection
verifies nine while retaining Jordan's runtime ownership and Riley's A launcher.

Source-bound input selection includes package and fixture source. Changed
builder/native/GUI bytes select a fresh immutable bundle; old manifests and
unchanged filenames do not qualify the new inventory. Native policy rendering
must retain concrete H denial and S's directory guard, with A absent from
denials, zero omitted groups and no hash allowances. The unsafe legacy layout
still refuses. Baseline reconciliation owns only narrow fixture admissions;
unknown native policy refuses and unrelated policy remains preserved.

<a id="c04p-time-and-app-effects-applicability"></a>
<a id="c04b-host-acceptance"></a>
<a id="c04u-bounded-ubuntu-qualification"></a>
<a id="c04f-fedora-qualification-and-ubuntu-renewal"></a>
<a id="c04o-shared-overlay-renewal"></a>

#### Scoped operation qualification

The fixed kiosk entry/approval and shared-overlay operations have both-target
qualification on Ubuntu 26.04 and Fedora 44. The kiosk binding uses Riley/Jamie,
Custom `1.25` Minutes (75 seconds), soft apps included, daily 900 and initial
grant zero; the independent Parent comparison uses the 975-second estimate,
elapsed time and one-second display precision. Kiosk MATE and overlay Shell
qualification remain separate provider bindings. These results establish no
locale/version matrix, complete customer journey or Fedora release qualification.

The separate native-effect binding uses zero daily/grant, Riley/Jamie and
Custom `10` Minutes (600 seconds), soft included. It requires A-primary and
S-secondary real Submit/results, H command denial, countdown before/after use
within 180 seconds of its estimate, positive Parent grant before revoke,
unchanged saved rules, then time restriction and attributed S command denial.
Restore H/S Allowed and disable controls through Parent with independent
settings/balance readback. A native command's attributed permission error is
evidence of denial; mere window absence or a service status is insufficient.

<a id="c04l-kiosk-language-and-human-pause"></a>
<a id="c04s-existing-request-choice-renewal"></a>
<a id="c04r-shared-reminder-persistence-renewal"></a>
<a id="c04i-existing-kiosk-about-renewal"></a>
<a id="c04w-parent-decision-pause"></a>

#### Feature and human-pause boundaries

Existing both-target qualifications cover the following finite bindings,
separately from the complete core history:

- Jordan's English/German/Simplified-Chinese/Hebrew language Save, Chinese
 Cancel retaining German, German reentry and unchanged policy/request choices.
 A guarded 90-second initial-chooser wait requires fresh same-dialog/session
 and complete choice readback before Save.
- Riley/Jamie's 300-second preset, Custom `1.25` Minutes, Rest of day and
 soft true/false; independent estimates and remembered Cancel/reentry without
 authentication.
- Riley's overlay-created literal `Save <work> & games!` reminder at 90 seconds,
 kiosk edit to 75 seconds with the same saved ID, independent overlay read,
 untouched Jordan defaults and approver/child isolation. Delete only the
 created record, Save and reopen the restored defaults. Sound/lightning remain
 disabled and mute absent; this supplies no notification-delivery result.
- Restricted About's installed product/version/legal information, external
 actions absent from the complete public inventory, unchanged usable request
 after normal close, then Cancel/GDM return.
- Riley/Jamie's zero-daily 75-second request with a 45-second real authentication
 pause, fresh same-challenge recipient proofs afterward, one submission,
 explicit approval, automatic GDM and independent positive grant read.

Human pauses test session lifetime. They do not extend startup or proof
freshness limits, create new feature matrices or belong in every consumer.
Observe the same session/request after a wait and reacquire both recipient
proofs; only the same empty native input field may wait for bounded readback.
Replacement or other refusal stops immediately, without another input.

#### C04j1 selected activity input preparation

C04j1 qualified the fixed baseline caller's immutable `native` plus `activity`
union through `prepare_installed_setup`, including the actual
`NativeFixtures(profile='activity').verify()` before product input. Other callers
retain native-only defaults. Activity hashes come from the selected manifest;
verification uses current attempt readiness and independent runtime trust
readback rather than the legacy embedded-fixture receipt.

The actual command was
`tools/run-tests integration --vm 'onpc-Ubuntu26.04,onpc-Fedora44' check_fixture_e2e_installed`:
Ubuntu passed in 18.6 minutes and Fedora in 11.7 minutes. Each passed two online
resume/rebind and two explicit offline attachment attempts, exact selected
bytes/modes/role owners/native admissions, harmless native/activity use, frozen
selection after producer edits, no-write repeats, fresh attempt/boot binding and
missing/incompatible/stale consumer-readiness refusals. Fedora retained enforcing
SELinux with exact labels/admissions. Collection and baseline restoration passed;
serial owned cleanup passed and both guests were independently observed off.

Existing affected host consumers passed. New unit coverage is limited to four
shared attempt-readiness cases; wrapper/helper matrices were removed under the
[test scope mandate](../Mandates/Test-Scope-Mandate.md). Frozen installed/system
input closures now include the required `baseline_environment` alias. No product
backend or package input changed.

This is preparation acceptance only. At C04j1 close-out, the changed
input/preparation envelope made Fedora's earlier complete customer pass
historical and left Ubuntu's final Parent save to diagnose. C04j2/j3 resolved
the subsequent input and native transition defects, and
[C04j passed both complete histories](#c04j-complete-baseline-composition) with
the resulting envelope. Separate feature/pause results remain reusable;
preparation acceptance itself closes no customer history or other queue task.

C04j's subsequent live maintenance replay passed this selected preparation but
stopped before its first H access input: Riley's public catalogue had no A/H/S/N
rows. The `native` subset supplies Jordan's four user-local launchers and none of
Riley's; `riley-grid` supplies only Riley's A and is insufficient. Adding only
identical launchers to Riley in the disposable live guest, then refreshing the
public catalogue, exposed all four rows; H permanent persisted across reselection
with its match unchanged. The successful bounded reload read followed an initial
premature read during loading. This is engineering diagnosis, not preparation or
customer acceptance. C04j2 adds only Riley's four native launchers as the finite
`baseline-child` subset. The existing fixed baseline caller selects
`('native', 'activity', 'baseline-child')`; native and Riley-grid defaults remain
unchanged. `NativeFixtures(profile='baseline-child')` independently reads Riley's
four launchers and the Jordan-owned shared runtime before product input, with
selected hashes and the existing owner, mode, no-link and readiness guards.

The same `check_fixture_e2e_installed` consumer now runs one online and one
offline attachment with the normal Parent worker. It observes Riley's exact
A/H/S/N rows and default matches, saves H permanent and S conditional, then
requires those saved values after child reselection and unchanged Jordan
defaults. It publicly restores H/S Allowed and controls off, verifies settings
and zero balances, collects the worker and restores the clean baseline.
Ubuntu passed both attachments in 18.4 minutes and Fedora in 16.9 minutes.
Both consumers completed worker collection and baseline restoration. Serial
owned cleanup passed and both pinned guests were independently observed off.
Fedora's enclosing runner initially failed its recording-finished notification
with `vm-config:fields` after the registry changed during its lifetime; its
recording itself closed successfully. The current parser accepts that registry.
A fresh `tools/run-tests --vm 'onpc-Fedora44' integration 'check_test_recovery'`
passed the same notification and recording closure with exit status zero.
No source change or repeat of the valid installed histories was needed. Serial
owned cleanup passed again and both pinned guests were independently observed
off. C04j2 is complete. C04j1's completed guard qualifications remain valid; no
complete customer history or other queue task receives acceptance credit.

<a id="c04j3-active-grant-disable"></a>

#### Active-grant disable and native continuity

The finite `check_e2e_active_grant_disable` selector uses
[`ActiveGrantDisableJourney`](../../tests/e2e/active_grant_disable.py) and the
existing baseline `native`, `activity`, `baseline-child` preparation. Run each
declared target separately. Its engineering attempt observes native estimates,
lock events and timer identity through disable, live-grant/unrestricted rollback
and a failed preparation readback. A separately restored public attempt obtains
a genuine 600-second approval with zero daily time, disables controls through
Parent, independently reloads saved settings/app rules and resumes retained
child activity. Fault injection contributes only engineering evidence.

The repair uses a verified full-day native schedule as the transition bridge
and restores the original schedule last. Independent Astra review identified
an approval/disable race; sharing the existing transaction lock through snapshots,
commit and rollback resolved it. Fresh independent review found no remaining
issues. All 184 focused product checks and both package builds passed.

Ubuntu and Fedora each passed both fresh attempts, collection and baseline
restoration. Serial owned cleanup passed and both pinned guests were independently
observed off. This binding covers only the restoration
transition exposed by the v1.3-derived baseline; complete baseline histories,
C05 acceptance and general feature coverage retain their existing owners.

<a id="c04j-complete-baseline-composition"></a>

#### Complete baseline composition

`baseline_journey.PLAN` / `BaselineJourney` and
`onpc_baseline_journey::run` compose the
[finite core history](E2E-Scenario-Recipes.md#commands-bounds-and-restoration).
Both complete installed histories passed on 2026-10-24 UTC, after
[C04j3's native transition repair](#c04j3-active-grant-disable). Each passed all
246 observations, including 244 public screen stages and two setup stages.
Ubuntu's worker took 1361.391 seconds and its qualification envelope 1381.843;
Fedora's worker took 1433.262 seconds and its envelope 1463.140. Both retained
the original 1800-second worker deadline. The actual commands were
`tools/run-tests --vm 'onpc-Ubuntu26.04' integration 'check_e2e_baseline_journey'`
and `tools/run-tests --vm 'onpc-Fedora44' integration 'check_e2e_baseline_journey'`.
Worker collection, stopped workers, closed callbacks, verified shutdown, owned
baseline restoration and serial cleanup passed. Both pinned guests were
independently observed off. These histories qualify this composition and are
available for C05's separate applicability review; no C05 or E2E case closes here.

The dispatcher now uses its existing installed-qualification registry to give
each qualification its own live evidence owner; the strict storage guard is
unchanged. Its 163 existing focused host checks passed, followed by the maintained
test-helper refresh. The baseline alone opts into compact request preparation:
12 redundant checkpoints are omitted while actual inputs, initial eligible-account
checks, fresh complete request reads and all comparison endpoints remain.
Another 203 existing worker-order, request and target/authentication checks
passed. No excluded composition/history unit suite was recreated. Product code,
package inputs and shared default preparation are unchanged by these repairs.

Original failed attempts retain no acceptance credit. Earlier import, selected
activity and selected-child catalogue gaps were resolved by the recorded repairs
and C04j1/j2. The original Ubuntu final-save alert was a native timer crash;
the clear-first trial was withdrawn after its lock risk was identified, and
C04j3 qualified the safe transition. In this session, parallel fixture production
refused its occupied producer, inherited dispatcher ownership refused startup,
and a separate recording controller refused overlap. The first full Ubuntu
attempt then reached its 1800-second deadline during app restoration. The
dispatcher repair and serial runs resolved startup; compact preparation removed
repeated identical setup. Both later complete passes include the final save,
settings and zero-balance results without bypassing any refusal or enlarging bounds.

The common worker distribution is
`bbb2c11f3e6a3db2e7304b4b7b03eef5d5380b2524a88525313663c50309fc85`;
inventory SHA-256 is `756bf5176c3b9d8ff96ee382d6ee1b6327bd072960dcddc8dbedfadc3700855b`.
Both used online `onpc-v1.4` snapshots with installation recipe
`59584a5c20d6c6dc9af94f5ff7ad21fa4f3ece60864f4aef7a81a81860c1cae2`
and the verified `native`, `activity`, `baseline-child` union.

| Exact accepted identity | onpc-Ubuntu26.04 | onpc-Fedora44 |
| --- | --- | --- |
| Source SHA-256 | `92b8d002733ee01ef791c359c9b3ec11a1ce020921f9de09ca23998e527f8511` | `171687b0a694749cf22ddd258c2f164ee9e7cf8138825c10fae278b1da1f9cab` |
| Package archive SHA-256 | `4704251b0ee8878bbeabecf40d4d6098334d84aeb4977c5f266ec2bed0bfd3ca` | `7b98a3f839e4a324df1b159f8ea0340e968a7ab1aa70a2f2c5f74e0485298552` |
| Installed package content SHA-256 | `93e0806ccde2aaf6f54900c438ee78fbdcda3efab0527603b2a3bd75dfda96be` | `7b98a3f839e4a324df1b159f8ea0340e968a7ab1aa70a2f2c5f74e0485298552` |
| Assets SHA-256 | `48cbdd976508f4323c601e6a23fa69cc10b89c02849893281bd9d34b5c3064ea` | `6b1d1f65a1c63cdb93ab78cd0602e27c33c58134fc8196bc6ddcf000fa82d753` |
| Baseline SHA-256 | `0258e5e1c68ee767ca97159c6972d718033d52b32d6fbccaf23d5826ec1f85fd` | `0be92111b8feb8a6c6c8ace8b70634ec25762396b91633e8a30b72dfe3fbfd09` |
| Fixture build identity | `1dd1ea17fd1efe4d8629d7d2571c710bab1f558c070021af5045973e03915eba` | `c80ed55f1cec62b65e59b8888d704aa3a903545322b85d4a6086ee96e502c1d7` |
| Fixture selection key | `0638d9f1fe6d2f9cf002b181de41e1b179f17c73e51d3359adbe2a72c4e6169d` | `c0e2dcdc1bdc336a749d05fcfd6c752750d9a6aa9ce02c076a5520f20c3bf8b9` |
| Environment | `ubuntu26-04-1f9a3275a5d51c4f684cb65883582a3b77be4be0d109ea4f3717797245dab629` | `fedora44-3656c93bfe21977071afb21ebd5caedc080cb75affcf6a3a1f6432ca7f45a134` |
| GDM / Shell / MATE agent | `50.1-0ubuntu0.1` / `50.1-0ubuntu1.4` / `1.26.1-6` | `1:50.3-1.fc44` / `0:50.6-1.fc44` / `0:1.28.1-8.fc44` |

Ubuntu's online snapshot archive is
`9bed7416c862216ec7c794d8b6bc2e7cff39f9c35b50a5d13bbb6d58b4a4a2b1`;
its installed-content identity matches the selected rebuilt DEB above. Fedora's
snapshot and selected RPM archive identities are identical. Providers used
US XKB input, Shell/GDM `en_US.UTF-8` and MATE `en_US.utf8`.

| Complete caller source | SHA-256 on both targets |
| --- | --- |
| `tests/e2e/baseline_journey.py` | `fe9145cbb340347a014e7e5313a3ca61d82274c97e1808cc6834122b9b3e554f` |
| `tests/e2e/request_flow.py` | `f02cb7e90a930e23227eb02a2fac6986f27238c4e7f624895c9562a56c6f90cd` |
| `tests/integration/graphical_smoke/lib/onpc_baseline_journey.pm` | `e60cef084f6a20a6416f8d781c12be1ac932f78f43b074a6364505a1d974c9d0` |
| `tests/integration/graphical_smoke/lib/onpc_request_flow.pm` | `6f99aaa00096af713a98e2ce80630d68b2964f5f7b2d945cca6861070113a683` |

The following maps the baseline and consuming C05 core assertions to their
accepted ordered endpoints. Every row passed independently on both targets.

| Required public result | Accepted endpoints |
| --- | --- |
| Zero daily/grant/total and saved A/H/S policy | `allowance-configured`, `saved-settings`, `saved-policy` |
| Explicit kiosk rejection, preserved choices, no grant or policy change | `kiosk-rejection-flow-preserved`, `rejection-policy` |
| Fresh password-free Cancel, remembered choices, no grant or policy change | `kiosk-cancel-open-estimate`, `kiosk-cancel-flow-preserved`, `cancel-policy` |
| Child entry denied at zero time | `zero-child-denied` |
| Genuine 600-second approval, countdown, real A/S use and H denial | `kiosk-first-approval-success`, `first-countdown`, `allowed-use-submitted`, `soft-use-submitted`, `hard-denied`, `remaining-countdown` |
| Overlay rejection and Cancel add no time and preserve original activity | Both `overlay-*-flow-preserved` comparisons, `rejection-activity`, `cancel-activity` |
| Genuine 75-second overlay approval, usable same activity, soft use and hard denial | `overlay-approval-approval-success`, `approved-activity-submitted`, `overlay-countdown`, `overlay-soft-use-submitted`, `overlay-hard-denied`, `overlay-policy` |
| Public revoke clears grant and restores time/soft restrictions without changing rules | `revoked-policy`, `time-denied`, `soft-denied` |
| Remembered reentry, distinct fresh approval, usable retained child/S and H denial | `kiosk-final-new-form`, `kiosk-final-approval-success`, `final-countdown`, `final-soft-use-submitted`, `final-hard-denied`, `final-policy` |
| Both apps Allowed with unchanged exact rules, controls disabled/saved and zero balances | Both `restore-*-access` / `restore-*-final-match` reads, `restore-saved`, `restore-settings`, `restore-balance` |
| Collection and owned restoration | Worker exit zero, callback closed, verified shutdown, restored baseline and independent off-state |

<a id="c04-readiness-audit"></a>

C04's host audit matched every row above to the current
[Python caller](../../tests/e2e/baseline_journey.py),
[installed entry](../../tests/integration/check_e2e_baseline_journey.py),
`BaselineJourneyQualification` and
[worker](../../tests/integration/graphical_smoke/lib/onpc_baseline_journey.pm).
The four complete-caller hashes above still match. The installed entry remains
registered as `check_e2e_baseline_journey`; it selects source-bound package and
fixture inputs, the `native`/`activity`/`baseline-child` preparation and the
same versioned installed snapshot. The ordered endpoints cover every core
assertion for both C05u (Ubuntu) and C05f (Fedora), with the exact per-target
candidate, fixture, provider, finite values, bounds and restoration recorded
above and in the [recipe](E2E-Scenario-Recipes.md#commands-bounds-and-restoration).

No product/package source, native fixture payload, core caller, provider binding
or assertion changed in this audit. The pre-existing maintenance-only
restoration diagnostic and equivalent normal snapshot rebind extraction do not
change the qualified history. The pre-existing blank line in
`tests/fixtures/baseline_assets.py` changes source bytes but no fixture behavior;
future preparation must still honor its ordinary source fingerprints, without
relabeling old inputs as a new build. These differences supply no concrete
invalidation of either recorded complete result. No core history is missing for
C05 to execute at this boundary; each C05 task must independently check its
selected candidate against these identities and renew only concretely affected
scope. Recorded identities describe the original results; old reports are not
prerequisites, and checked tasks stay complete. This host finding grants no
installed acceptance.

Separate C04l/s/r/i feature histories and C04l/w's 90/45-second human-pause
histories remain accepted for their unchanged bindings. Compact preparation is
opt-in to this baseline; those default callers and feature assertions did not
change. C04 found no changed feature/pause caller, provider or assertion and no
affected renewal slice for either C05 consumer. The finite language, choice,
reminder, About and pause outcomes remain those in the
[separate qualification boundary](#feature-and-human-pause-boundaries), rather
than additional steps inferred from the core pass. No ordinary-use mismatch
remained in these accepted histories. Alternate
graphical-session behavior retains its route-specific scope; other deliberate routes remain for C06a review;
no new breach test or escape claim was added. FLOW19/FLOW20 and broader cases
34/36/44–49 retain their existing pending scope.

Independent Sol High source review found no live registration for retired
mechanisms or gap in the C04a/C04c dispositions; stale prospective B1–B4 wording
in the proof consumer was corrected while its historical ledger remained intact.
C04's 35 focused inventory checks, runner listing, plan metadata and scoped
links passed. No executable inventory or coverage source changed, so no coverage
regeneration or package build was needed. This audit ran no installed checks,
reopened no completed task and left no owned resources.

<a id="c05u-ubuntu-baseline-acceptance"></a>

#### Ubuntu baseline acceptance

C05u independently applied the
[complete baseline reuse contract](E2E-Execution-Contracts.md#complete-baseline-evidence-reuse)
and accepts C04j's complete `onpc-Ubuntu26.04` history above as installed
acceptance. The selected candidate is the recorded rebuilt DEB, installed-content
SHA-256 `93e0806ccde2aaf6f54900c438ee78fbdcda3efab0527603b2a3bd75dfda96be`,
with its recorded snapshot, source, fixture and provider identities. All 246
observations passed in 1361.391 seconds within the unchanged 1800-second worker
bound, including the mapped negative, approval, activity, revocation, fresh-request
and public restoration results.

Comparison from C04j through C04 and the current checkout found no changed
product/package source, native fixture payload, provider binding or assertion.
All four recorded complete-caller hashes still match. The existing fixture
blank line, maintenance-only diagnostic, equivalent snapshot rebind extraction
and host test-recovery/classification edits do not invalidate those public
results. No new candidate or fixture input is claimed. The separate C04l/s/r/i
feature and C04l/w human-pause results also remain applicable to their unchanged
bindings. No renewal is required.

The accepted history completed collection, worker/callback shutdown and owned
baseline restoration, with the guest independently observed off. C05u started
no VM, worker or helper requiring cleanup. Alternate graphical-session access
retains its separate local desktop composition; TTY, SSH and exposed child-accessible routes remain for
C06a/C06 review. Remote desktop testing is excluded by the developer. The retained
routes are unqualified, not observed baseline
failures or a final confinement claim. Only C05u closes; Fedora remains C05f's
installed acceptance gate.

<a id="c05f-fedora-baseline-acceptance"></a>

#### Fedora baseline acceptance and both-target handoff

C05f independently applied the
[complete baseline reuse contract](E2E-Execution-Contracts.md#complete-baseline-evidence-reuse)
and accepts C04j's complete `onpc-Fedora44` history as installed acceptance.
The selected candidate is the recorded rebuilt RPM, archive/installed-content
SHA-256 `7b98a3f839e4a324df1b159f8ea0340e968a7ab1aa70a2f2c5f74e0485298552`,
with the source, assets, online snapshot, native/activity/baseline-child fixtures,
GDM/Shell/MATE providers and finite inputs in the
[exact identity and public-result tables](#complete-baseline-composition).
All 246 observations passed in 1433.262 seconds within the original 1800-second
worker bound, including negative requests, genuine approval, usable A/S with H
denied, preserved overlay activity, revocation, fresh remembered reentry and
public policy/time restoration. Collection, worker/callback shutdown, owned
baseline restoration and the independent guest-off observation also passed.

The applicability review found all four complete-caller hashes unchanged and no
product/package, native fixture payload, provider, input or assertion change
since the accepted composition. The existing fixture blank line, maintenance-only
restoration diagnostic, equivalent snapshot rebind extraction and host
test-recovery/classification changes do not invalidate either target's public
results. No new package or fixture build is claimed. The separate C04l/s/r/i
feature and C04l/w 90/45-second human-pause results retain their unchanged
bindings. Independent Sol High source review agreed that neither a complete
history nor a separate feature/pause slice needs renewal. Ubuntu's
[C05u acceptance](#c05u-ubuntu-baseline-acceptance) remains applicable to its
recorded DEB and identities; Fedora's result does not substitute for it.

Baseline product, automation and current documentation match this finite scope
on both targets. C05f started no VM, worker or helper requiring cleanup and
recovered no historical reports. Only this baseline queue closes. Local alternate
graphical-session selection and request-session actions yielding a full desktop
retain their separate local desktop composition. Remote desktop testing is excluded by the
developer, with no remote acceptance claimed. Standalone terminal/TTY and SSH
remain for C06a/C06, with other exposed
actions and child-controlled consumed inputs for C06x/C06i. These are concrete
coverage gaps for their route reviews, not observed baseline defects or accepted
escape defenses. No E2E row, Fedora release qualification or final post-protection
acceptance is granted.

The caller owns order, values, immutable per-approval captures and comparison
endpoints. Shared operations own public inputs, guarded authentication, native
activity, desktop entry, observation and revocation. The exact remembered
transitions are soft-included kiosk 75→600 and overlay 600→75 seconds.
Equivalent public decimal edits `1.25` → `1.250` → `1.25` refresh the
unchanged overlay request calculation. Nonoverlapping guest-clock brackets
date that calculation; cached label read time cannot stand for calculation
time. Negative comparisons require positive remaining time, uncertainty below
75 seconds and the original 120-second comparison bound. Positive lower bounds
use the earliest calculation time while retaining the 600-second freshness
limit, display precision and upper bound.

The composition may omit duplicate same-user desktop observations using
`desktop_observation=False` only where the shared operations retain fresh
input guards and independent results. Default callers remain unchanged. Every
required endpoint remains: initial saved A/H/S rules and zero balances;
kiosk rejection and separate password-free Cancel with no grant; fresh genuine
approval; grant-only countdown and A/S use with H denied; overlay negatives
without lost activity or added time; genuine overlay approval; public
revoke and restored restrictions; remembered kiosk reentry with a distinct
fresh challenge and usable child/S; public policy/time restoration.

Each history retains the original 1800-second worker bound, 90-second kiosk /
45-second other observation limits and under-30-second recipient proofs.
Require positive observed time before downstream app work and keep that work
within its remaining bound. An explicit longer request requires its own
qualified binding. Preserve exact candidate/provider/input identities, original
failure, collection, stopped workers, closed callbacks, completed leases and
owned baseline restoration in runner artifacts. Baseline acceptance establishes
no protection against alternate graphical sessions, standalone TTY, SSH or other
deliberate non-desktop escape routes.

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
| REQUEST01 | C | Enter the dedicated request station from GDM through shared minimal account selection and observe its request form. | `journey_blocks.station_entry` / `onpc_gdm::enter_station` reuse `AccessibleUI.gdm_nonsecret_navigation`, consume one fresh focused-station proof before Enter, then independently require the active station owner and one showing owned window/form. The passwordless destination was qualified on the prepared Ubuntu 26.04/English-GDM/baseline-keyboard image with GNOME Shell `50.1-0ubuntu1.2`. `check_e2e_kiosk_eligible_choices` qualified direct composition after Parent preparation and shared Switch User. Station navigation requires the station row, without a named-parent prerequisite. This route and Cancel/GDM/reentry after locking all eligible parents passed `check_e2e_kiosk_fixtures`; the affected no-child route passed `check_e2e_kiosk_no_child`, both with collection and owned restoration. Routine entry never visits another account. | ready |
| REQUEST02 | C | Open or deliberately reopen the child overlay by direct `oh-no-parent-control-child` invocation as the active child desktop user; observe one usable form and fixed child identity. Mandatory for ordinary overlay entry. | DESK01 → `AccessibleUI.launch_child_command` (`child-command-launch`, fixed command, one submission) → UI01 → UI02 → UI13(form count=1) → UI03(fixed child). Shared `overlay_entry(..., 'command')` qualified two independent entries and immutable form readback in [overlay entry qualification](#overlay-entry-qualification). Repetition is deliberate customer input, not retry. | direct entry and default form ready |
| REQUEST03 | C | Read a form's child, approver, duration, custom text, soft-app choice, controls and messages; observe the absence of mute in the current release. Require exactly one showing form and the fixed child in overlay. | UI13(form count=1) → UI01 → UI02 → UI03. `AccessibleUI.kiosk_request_form` retains the installed-qualified disabled-child projection. Its `enabled=True` binding also qualifies default 1800-second duration, selected child/approver IDs, enabled controls and absent disabled notice/mute/custom value. `RequestObservation.from_request` validates immutable operation-specific expectations. `check_e2e_kiosk_eligible_choices` independently reread both selections. `duration_seconds` / `custom_text` extend the immutable projection to the [qualified valid kiosk choices](#valid-kiosk-choice-qualification). `overlay=True` qualifies the default fixed-child projection through [overlay entry qualification](#overlay-entry-qualification); Declared valid overlay values are qualified through the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification); preserved invalid input and open/new FLOW04 projections passed the [overlay FLOW04/invalid/Escape slice](#overlay-flow04-invalid-submission-and-escape-qualification). Other values and account profiles remain pending. | default/declared valid kiosk/overlay and representative overlay invalid projections ready; other bindings pending |
| REQUEST04 | C | Set the child/approver selector to an eligible UID or duration selector to its canonical value. Observe selected identity, loaded values and availability; fixed-child overlay selection refuses. | `AccessibleUI.select_kiosk_account` / `kiosk_valid_choice` use `getChoices`, `setValue` and fresh REQUEST03 readback on the appropriate kiosk/overlay surface. Language restoration and disabled-child assertions retain their explicit child and language bindings. | pending; enabled kiosk child/approver including the stated German/Hebrew restoration binding, disabled-child selection and declared kiosk/overlay valid durations and overlay approver/refusals ready |
| REQUEST05 | C | Type a custom duration, including deliberately invalid text, and observe validation/request availability. | UI16 → REQUEST03. `onpc_text::replace_text(kiosk-fraction)` / `AccessibleUI.read_synthetic_text` qualify exact `1.25` minutes (75 seconds); see [valid kiosk choices](#valid-kiosk-choice-qualification). `kiosk-invalid-*` bindings qualify all seven invalid custom values with enabled Request and exact preserved text; see [invalid kiosk choices](#invalid-kiosk-choice-qualification). Do not coerce or repair the customer's value. `onpc_text::replace_text(overlay-fraction)` reuses the same guarded text mechanics for exact overlay `1.25`; see the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). `overlay-invalid-*` uses the same text binding and exact readback guards; representative `0.09` passed installed qualification and all seven invalid values passed the local native GTK matrix. See [overlay invalid submission](#overlay-flow04-invalid-submission-and-escape-qualification). Other values remain pending. | pending; kiosk/overlay 1.25-minute, kiosk finite invalid and representative overlay invalid input ready |
| REQUEST06 | C | Set the request form's soft-app choice to an explicit boolean and observe it. The surface and child are explicit. | UI17 → REQUEST03. `AccessibleUI.set_toggle` through `kiosk_valid_choice` qualifies explicit inclusion/exclusion and independent kiosk readback; see [valid kiosk choices](#valid-kiosk-choice-qualification). The explicit fixed-child overlay inclusion/exclusion binding also passed the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification); the fixed 75-second soft-included FLOW04 binding and subsequent exclusion also passed the [overlay FLOW04 slice](#overlay-flow04-invalid-submission-and-escape-qualification). Other overlay bindings remain pending; interactive mute is deferred future-feature scope. | pending; declared kiosk/overlay inclusion/exclusion ready |
| REQUEST08 | C | Read the visible estimate/footer for the chosen duration, including rest-of-day meaning, loading or unavailable estimates. | `kiosk_request_form(enabled=False, expected_selection=...)` / `RequestObservation` require selected child, retained approver, exact disabled-control explanation and no prompt; disabled controls receive no input. `kiosk_valid_choice` reads numeric/midnight footer; `KioskValidDurationJourney.check_settings` and `KioskRequestJourney.check_estimate` compare independent Parent balances, elapsed time/precision and kiosk unused-child equality. [Overlay](#valid-overlay-choice-and-cancel-qualification) open/default and new/remembered 75-second estimates keep immutable choice checks. Other loading/unavailable/numeric bindings pending. | pending; kiosk disabled-child explanation, unavailable Request and declared kiosk/overlay valid estimates ready |
| REQUEST09 | C | Activate an enabled Request once and observe the declared result: authentication for valid input or validation for invalid custom input. | UI01 → UI02(enabled) → UI04; valid then AUTH01, invalid then REQUEST03 → UI11(no prompt). `AccessibleUI.kiosk_mate_cancel` / `mate_prompt.PLAN` qualify the fixed valid kiosk submission through `check_e2e_auth_prompt`; `overlay_shell_cancel_ready` qualifies the fixed valid overlay submission through [Shell prompt qualification](#overlay-shell-prompt-and-cancel-qualification). `AccessibleUI.kiosk_invalid_choice` / `request_duration.PLAN` qualify enabled kiosk submission, exact validation, preserved form and no authentication for every finite invalid custom value; see [qualification](#invalid-kiosk-choice-qualification). `overlay-invalid-below-*` shares the same single-submit/no-prompt mechanics with explicit overlay/fixed-child guards; see [overlay invalid submission](#overlay-flow04-invalid-submission-and-escape-qualification). Missing accounts, unloaded preferences or disabled limits instead require the disabled state and no activation. | kiosk invalid-custom/fixed valid-authentication and representative overlay invalid-custom/fixed valid-authentication branches ready; other bindings pending |
| REQUEST10 | C | Native double-click Request and one-prompt observation: excluded on both kiosk and overlay. | Requires unsupported UI20; see the [UI mandate](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures). Do not substitute two activations or recreate capability/consumer tasks. Ordinary REQUEST09 and independent public observations remain separate capabilities. | excluded; no active task or queue blocker |
| REQUEST11 | C | Observe success confirmation, rejection, cancellation without an error, or validation feedback, with the explicitly expected preserved choices. | Read explicit result before automatic exit; if form remains compare REQUEST03 with immutable choices. `kiosk_gdm_returned` requires usable GDM/absent request/error UI. `kiosk_approval_success` captures brief success; kiosk/overlay rejection and password-free Cancel require unchanged usable no-error form. Overlay invalid input requires exact validation/no prompt; overlay exit compares original usable activity. See [kiosk](#kiosk-approval-qualification) and [overlay](#overlay-immediate-exit-and-approval-compositions) outcomes; other bindings pending. | pending; kiosk Cancel/Escape, fixed approval success and rejection/Cancel preserved form, declared overlay Cancel/Escape/invalid validation and fixed Shell rejection/Cancel preserved form and fixed overlay approval success ready |
| REQUEST12 | C | Exit through the normal API Cancel action, surface close, approved immediate exit action, or already-approved automatic exit. Observe overlay disappearance plus child desktop, or kiosk disappearance plus GDM. Form cancellation refuses an active authentication prompt. Legacy Escape bindings retain their normal-close user outcome. | UI04(Cancel or approved immediate exit), UI18, or no input for automatic exit → UI11 → DESK01 or GDM01. `AccessibleUI.cancel_kiosk_request` invokes the owned API action; `onpc_request_exit::escape` composes the scoped request-surface close with `kiosk_gdm_returned` or `overlay_desktop` for independent destination observation. Retained `focus_kiosk_escape_recipient` names supply guarded API close, with no native key or focus requirement. Cases 47/48 and 54 retain their choices and GDM assertions; see [prepared request qualification](#prepared-request-qualification). `kiosk_approval.PLAN` and `auth_result.PLAN` retain automatic/immediate approved exit; see [kiosk approval](#kiosk-approval-qualification). Overlay Cancel/close shares the request API and compares the original usable activity; see [valid overlay slice](#valid-overlay-choice-and-cancel-qualification), [overlay close history](#overlay-flow04-invalid-submission-and-escape-qualification) [automatic overlay approval](#overlay-approval-and-automatic-return-qualification) and [immediate/automatic overlay compositions](#overlay-immediate-exit-and-approval-compositions). Historical native-Escape evidence does not require keyboard input in current consumers. | pending; kiosk Cancel/Escape and fixed automatic/immediate approved exits and declared overlay Cancel/Escape and fixed automatic/immediate approved exits ready |
| REQUEST13 | C | Open the child overlay through the Shell panel only when the case explicitly tests that graphical launch route. Observe one usable form and fixed child identity. | DESK12(request entry) → UI04 → UI01 → UI02 → UI13(form count=1) → UI03(fixed child). Declare the exception in case metadata and recipe. Shared `overlay_entry` routes `panel` and `panel-reopen` qualify normal launch and deliberate repeated activation over the open form; see [overlay entry qualification](#overlay-entry-qualification). Fullscreen gameplay uses the same product API entry without panel reveal or focus choreography; its distinct request/return and retained-game results still need qualification. | normal launch and singleton ready; fullscreen gameplay/request/return binding pending |

#### Overlay Shell prompt and Cancel qualification

`overlay_prompt.PLAN` / `OverlayPromptJourney`,
`onpc_request_flow::shell_cancel` and `check_e2e_overlay_prompt` qualify
Riley/Jamie, custom 75 seconds, soft included after public 900-second allowance
setup. Initial tuple: Ubuntu 26.04/Shell `50.1-0ubuntu1.2`,
`en_US.UTF-8`, `xkb/us`; [baseline renewal](#c04o-shared-overlay-renewal)
owns the rebuilt both-target fixed scope.

`request_flow.overlay_authentication(result=..., prefix=...)` ends at prompt
dismissal or explicit success; callers own form preservation, destination,
activity and phases. `AccessibleUI.shell_prompt_owner` binds the unique
top-level Shell process on the active child's bus behind fullscreen.
`shell_prompt` requires exact displayed approver/child/duration/apps before
checking the sole empty masked focused field. Provider/session/owner/recipient/
request mismatch, ambiguous/hidden/disabled/nonempty/stale fields and replaced
challenges refuse. Incomplete reads never authorize input; metadata retries
remain bounded and complete. `overlay_shell_cancel_ready` consumes no password
and authorizes one normal Cancel; independently require prompt absence and
immutable unchanged usable no-error choices through `KioskRequestJourney`.

#### Overlay approval and automatic return qualification

`overlay_approved_exit.PLAN` / `OverlayApprovedExitJourney`,
`check_e2e_overlay_approved_exit` and `onpc_request_flow::shell_approve`
qualify the fixed request/initial tuple above.
`AccessibleUI.overlay_shell_approval` and `UiObservations` bind two fresh
empty-field proofs to one challenge before
`onpc_password::enter_overlay_shell_password` delivers one sealed credential.
Opening/refusal observations confer no secret authority; freshness starts at
acquisition. Recheck the filled recipient, durably record observer readiness,
release one Enter and require matching acknowledgement. Failed/stale/replaced/
repeated authority or uncertain input never retries.

`kiosk_approval_success` pins the child-owned request window before submission
and observes its brief **Time granted** public result before automatic closure.
Result controls may appear only after submission. Prompt/window disappearance
alone cannot establish approval. Read closing-window absence without replaying
submission; no exit input belongs in the automatic branch.
`overlay_desktop` and `InstalledJourney.check_activity` independently require
the original usable window/PID/endpoint, exact draft and activity.

Require the complete current broker request message before inspecting protected
field length; obsolete wording refuses. Authentication inputs bind current
package sources; a current snapshot does not refresh a fixed legacy bundle.
Retain provenance, snapshot freshness and ownership guards.

`overlay_approved_exit.TRANSLATED_PLAN` /
`check_e2e_overlay_translated_approval` additionally qualify Riley/Jamie's
75-second soft-included request with Hebrew product text and the unchanged
English desktop agent. Both independent clean entries passed on Ubuntu 26.04,
Shell `50.1-0ubuntu1.4`, `en_US.UTF-8`, `xkb/us` in `20261030T121510Z-a41107c4`:
fresh same-challenge recipient/refusal proofs, one sealed credential submission,
Hebrew **זמן הוענק** success, automatic return, the same usable original
window/draft/score and the elapsed-bounded public time increment. Collection,
worker/callback closure, owned cleanup, baseline restoration and host/source
preservation passed for both. The shared read-only activity capture reacquires
an incomplete provider read within its normal deadline, without input replay or
accepting a partial tree. Complete language restoration/history remains task 308;
this binding supplies no complete-case acceptance.

#### Overlay immediate exit and approval compositions

`overlay_approved_exit.IMMEDIATE_PLAN/FLOW_REJECTION_PLAN/FLOW_CANCEL_PLAN`
and `check_e2e_overlay_approval` qualify fresh immediate approval and separate
rejection/Cancel→new-approval compositions for the fixed 900-daily/75-second
request on Ubuntu 26.04/Shell `50.1-0ubuntu1.3`, English/US.
`request_flow.overlay_approved_request(exit='automatic'|'immediate')` /
`onpc_request_flow::overlay_approve` compose shared leaves. Immediate exit reads
explicit success and independent prompt absence, then activates the offered
owned result action once; both branches independently verify original activity.

`overlay_approved.PLAN` / `onpc_kiosk_cancel::run(..., 'overlay-approved',...)`
bind case 46 to this immediate route plus native activity/time observations.
`KioskRequestJourney` compares an immutable estimate independently bounded by
earlier daily/no-grant balance, elapsed use and requested addition.
`request_flow.overlay_rejected_request` /
`onpc_request_flow::overlay_reject` leave a preserved form before a distinct
fresh approval challenge; old proofs never authorize the next request.

Public label projection is part of complete `AccessibleUI.nodes` traversal.
A non-uncertain provider exit discards the entire observation for bounded
reacquisition while retaining owner pins; denied/uncertain reads stay terminal.

#### Overlay rejection and Cancel qualification

`overlay_rejection.PLAN` / `OverlayRejectionJourney`,
`check_e2e_overlay_rejection` and `onpc_request_flow::shell_reject` qualify
one wrong-password request and a separate password-free Cancel for the same
Ubuntu Shell `50.1-0ubuntu1.3` English/US fixed binding.
Two fresh empty-field proofs precede sealed wrong-password delivery; a fresh
filled proof precedes one submission.
`AccessibleUI.overlay_shell_rejected` must read explicit denial in the same
challenge and recheck its empty/enabled/focused masked retry field before one
normal Cancel. Timeout/disappearance cannot establish rejection.
Independently require prompt absence, unchanged usable no-error form, normal
closure and child destination. Wrong-account/surface/recipient and replaced,
stale, incomplete or uncertain observations refuse without input replay.
Complete cases and other request/provider bindings remain separate.

#### Overlay entry qualification

`shell_panel.PLAN` / `ShellPanelJourney`,
`journey_blocks.overlay_entry`, `onpc_request_flow::overlay_entry` and
`check_e2e_shell_panel` qualify the fixed Riley form on Ubuntu 26.04/Shell
`50.1-0ubuntu1.2`, English/US: direct entry and deliberate panel entry,
default Casey approver, 1800 seconds, enabled controls and child identity.
This is no reusable exit or complete-case qualification.

Current panel input uses the `child-panel` Application UI API and
`child-request-button.activate` once, then independently reads the form.
Reuse an already open form; busy/active-request refusal never permits another
key/input route. Repeated activation/reveal is no mandatory consumer sequence.
Direct command remains ordinary entry; gameplay consumers retain actual activity
and return outcomes. `Selected account: …` descriptions do not replace
namespace-scoped UID identity. Package/source-bound preparation preserves
existing verified inputs.

#### Valid overlay choice and Cancel qualification

`overlay_valid_choices.PLAN` / `OverlayValidChoicesJourney`,
`onpc_request_flow::overlay_valid_choices` and
`check_e2e_overlay_valid_choices` qualify fixed Riley/Jamie choices/Cancel
on Ubuntu 26.04. Publicly establish 900 daily seconds and usable native activity,
then capture its exact window/draft. `request_surface(overlay=True)` and
`kiosk_valid_target` require the child app/session, locked child selector,
selected approver and available controls before input; child reselection and
kiosk input refuse.

`select_kiosk_account(..., overlay=True)`, `kiosk_valid_choice` and
`onpc_text::replace_text` cover 300 seconds, Custom `1.25` Minutes/75
seconds, Rest-of-day and soft inclusion/exclusion. Independently compare estimates
with earlier public balances, elapsed time/precision; Rest-of-day requires its
midnight footer. `cancel_kiosk_request(overlay=True)` invokes Cancel once,
then independently requires absent overlay/usable child and original activity.
A fresh command entry reads remembered Jamie/excluded/zero-duration choices,
selects 300 seconds and Cancels to the same activity. No authentication, invalid
input, Escape, complete-case or FLOW04 scope follows from this slice.

#### Overlay FLOW04, invalid submission and Escape qualification

`overlay_choices.PLAN` / `OverlayChoicesJourney`,
`onpc_request_flow::overlay_choices` and `check_e2e_overlay_choices`
extend the fixed Ubuntu binding with open/default and new/selected
`request_flow.prepared_request(surface='overlay')` /
`onpc_request_flow::prepare(..., 'overlay')`: Riley/Jamie, `1.25` Minutes,
75 seconds, soft included. New entry reads remembered choices before reselecting;
`request_checks` compares immutable open/new captures and bounded estimates.

After separate exclusion, input literal `0.09` through the public API.
`kiosk_invalid_choice` requires locked child, correct approver, enabled controls
and no prompt; one enabled Request produces exact range validation, preserved
text/choices and no authentication. The complete seven-value local matrix stays
in UI. Cancel after FLOW04 and legacy Escape-labelled surface close after
validation have distinct independent return/activity observations.
`onpc_request_exit::escape` uses product surface close, not keyboard focus.
Require original window/draft before later input; close the native app normally.
Authenticated exits, arbitrary close/value bindings and complete cases remain
separate.

#### Overlay choices transferred to kiosk

`choices_overlay_to_kiosk.PLAN` / `ChoicesOverlayToKioskJourney`,
`request_flow.overlay_to_kiosk` /
`onpc_request_flow::overlay_to_kiosk` and
`check_e2e_choices_overlay_to_kiosk` qualify the shortened transfer on both
Ubuntu 26.04/Fedora 44. Public setup gives both children 30 daily minutes.
Riley overlay saves `1.25` Minutes/75 seconds/soft included; Jordan saves
`2.5` Minutes/150 seconds/soft excluded. Each overlay keeps Jamie while kiosk
keeps Casey.

Consume a fresh source capture, explicitly Cancel overlay, switch to GDM,
enter kiosk/select the declared child and read destination before editing.
Transfer each child once, then reselect both in the same kiosk; four immutable
comparisons prove transfer, persistence, child isolation and local approvers.
No retained-GDM repeat is prerequisite. Destination remains open.
`AccessibleUI.transfer_choices`,
`JourneyPlan.request_transfer_checks` and
`KioskRequestJourney.check_transferred_request` own scoped operations and
immutable comparisons. Wrong receipt/account/owner, stale capture and uncertain
input refuse before mutation. Interactive mute and complete cases remain separate.

#### Kiosk choices transferred to overlays

`cross_surface.PLAN`, `request_flow.kiosk_to_overlay` /
`onpc_request_flow::kiosk_to_overlay` and `check_e2e_cross_surface` qualify
the reverse fresh-entry binding on Ubuntu 26.04/Fedora 44.
Use the same public 30-minute setup, distinct Riley/Jordan values and
Jamie-overlay/Casey-kiosk local approvers. Fresh overlays establish Jamie then
log out without approval; kiosk saves/captures both requests.
Consume source before station Cancel, enter each child explicitly and read
the untouched overlay destination. Close only the first destination to reach
the other child; final overlay stays open.

Compare immutable child/duration/custom/soft endpoints and each surface's local
approver. Wrong receipt refuses before Cancel; known wrong OS-account refuses
before unrelated provider discovery. Matching-account routes retain owner,
modal, availability, child/session and uncertain-input guards. The shared
declaration accepts explicit fresh/retained modes, but this qualification covers
fresh only. Interactive mute and complete histories remain separate.

#### Kiosk approval qualification

`kiosk_approval.PLAN` / `KioskApprovalJourney`,
`onpc_request_flow::run(..., 'approval')` and
`check_e2e_kiosk_approval` bind the 75-second soft-included request.
Initial tuple: Ubuntu 26.04/MATE `1.26.1-6`, `en_US.UTF-8`,
`[["xkb", "us"]]`; [baseline qualification](#c04f-fedora-qualification-and-ubuntu-renewal)
owns rebuilt both-target scope and independent grant read.

`AccessibleUI.kiosk_mate_approval` opens once, then
`wait_mate_prompt` may wait while locale preparation restarts an absent agent.
Once visible, every control must belong to the current unique service PID,
unchanged throughout proof. `mate_challenge_identity` binds public references
to boot/UID/service lifetime. Require ordered non-replayed same-challenge proofs,
no intervening operation and under-30-second freshness.
`onpc_password::enter_kiosk_mate_password` consumes two durable proofs for one
sealed secret delivery. Reused/replaced challenges and uncertainty are terminal.

English MATE must display complete multiline context:
`Grant [Child user] access?`, `Requested time: 1 minute, 15 seconds.`,
`Allow soft blocked apps for this grant.`
The separate 30-minute/soft-excluded binding checks its selected child/duration
without the inclusion sentence. Missing/hidden/duplicate/changed context refuses
before password proof; obsolete one-line text is not an alternative.
Use [shared messages](../../common/oh_no_parent_control_ui/messages.py) in
fixtures. Freshly recheck the filled masked focused recipient and invoke the
unique Authenticate once. Observe owned `kiosk-result-title=Request approved`
before the three-second automatic exit, then independently require usable GDM
and absent request/error UI. Disappearance alone cannot pass.

`auth_result.PLAN` / `AuthResultJourney`, `check_e2e_auth_result` and
worker `immediate` reuse the same guarded secret path, read explicit approval,
then activate owned `kiosk-result-action` once before automatic exit.
Missing/hidden/disabled/duplicate/uncertain actions refuse; independently require
GDM. Automatic/immediate, rejection and password-free Cancel are separate
outcomes; no complete scenario follows from operation qualification.

#### Kiosk rejection qualification

`kiosk_rejection.PLAN` / `KioskRejectionJourney`,
worker `rejection` and `check_e2e_kiosk_rejection` bind the same initial
MATE/English/US/75-second soft-included scope.
Separate entries exercise password-free Cancel and one wrong-password rejection.
`enter_kiosk_mate_password(..., 'wrong')` retains two fresh proofs/sealed
single-use delivery. Public negative fixture `onpc-wrong-fixture-password`
switches to `onpc-other-wrong-fixture-password` only on equality with the
frozen credential; publish no secret-derived value.
`kiosk_mate_rejected` reads explicit unsuccessful-attempt text in the original
service-owned dialog, rechecks its empty retry field and Cancels once without
authentication retry. Independently compare preserved usable no-error form
choices. Timeout, success or disappearance cannot establish rejection.

#### Valid kiosk choice qualification

`kiosk_valid_duration.PLAN` / `KioskValidDurationJourney`,
`onpc_kiosk_valid_duration::run` and
`check_e2e_kiosk_valid_duration` bind 5-minute preset, Custom `1.25`
Minutes/75 seconds, Rest of day and soft included/excluded.
Public Parent 15-minute balance precedes station entry/account selection.
Read 20-minute/16m15s estimates respectively, exact midnight footer and explicit
soft states; Cancel to GDM without authentication.
[Current both-target scope](#c04s-existing-request-choice-renewal) remains finite.

`kiosk_valid_target` requires selected-child/approver IDs and enabled controls.
After one Custom action, `awaiting_custom=True` waits only for asynchronous
entry publication within the existing deadline; never accept disabled fields
or replay input. Prompt/ownership guards remain active.
`kiosk_request_form` / `RequestObservation.from_request` own exact values.
Other durations/authentication/surfaces require separate qualification.

#### Invalid kiosk choice qualification

`request_duration.PLAN` / `RequestDurationJourney`,
`onpc_kiosk_valid_duration::run(..., 'invalid')` and
`check_e2e_request_duration` qualify empty, `abc`, `-1`, `0`,
`0.09`, `1440.1` and `1,5` input.
UI16 uses scoped API text replacement and independent exact readback.
On the otherwise ready form Request stays enabled; one activation shows exact
range validation, preserves child/approver/text/soft choice and opens no prompt.
Separate `ready/submit/read` operations use `kiosk_invalid_choice` and
`RequestObservation`; invalid values have `duration_seconds=None`, never
a valid estimate. Wrong value/child, disabled input, changed form, prompt or
uncertain input refuses; Cancel returns to GDM. No authentication, overlay or
complete-case qualification follows.

### Customer terminal, files and application use

FILE02 executes registered public commands over guarded SSH as the declared
fixture user. INFO02 reads the public help/manual interface through bounded
stdout. Neither route permits private product probes or Terminal GUI setup. Fixture package/path arguments come from
verified prepared assets. Native/Snap/Flatpak and app names are parameters of
these blocks, not copies of them.
INFO02 validates each command's output without an intervening desktop UI check;
the complete command-help case owns one final public desktop result.

E2E-020 refreshes the catalogue after Save through LIFE01(Parent), then PARENT02
selects the target child before reading the loaded catalogue. Switching children
reuses cached lists. This finite composition remains unqualified; existing
selection and reopen callables do not qualify the complete refresh journey.
Await fresh public results within deadlines, accounting for observation latency.

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
| FILE09 | C | Change a registered synthetic source file using the shared file helper and observe the product's attachment snapshot/re-add result. For declared retained-work assertions, edit/save in the existing work fixture and read its activity. | `change_attachment_source` / `SyntheticFiles.call('change-source')`; [qualified source binding](#synthetic-source-change) runs as Jamie for standard/single attachment inputs. It does not open/save a child document. Task [196a](E2E-Tasks/196a-child-saved-work.md) separately qualifies child-owned FILE08/09 Save/reopen and APP03/04 work observations before E2E-050/051. UI16/public Save/readback only for work observed by an enforcement/retention case. | standard/single synthetic source preparation ready; product snapshot/re-add belongs to the attachment UI matrix; retained-work binding planned in 196a |
| APP01 | C | Attempt a launch once by the route explicitly tested by product enforcement. Default supporting launch uses a shared direct command. Hidden launcher and execution denial are distinct. | `onpc_app_rows::native_search/native_launch_grid/native_open_grid` qualify Jordan's and Riley's exact Allowed fixture grid routes under [native fixture preparation](#native-fixture-preparation), with explicit `other-child` / `child` bindings. `native_open_command` / `AccessibleUI.native_launch_command` qualify the fixed native command as the bound active desktop user over guarded SSH, including Jamie/Parent through [distinct-user retention](#distinct-user-retained-app-qualification), with independent APP02 window readback. Explicit app-grid, desktop-icon and file-manager cases retain their GUI route. Command cases use FILE01/02 without Terminal UI. Never substitute the tested route after failure. | Jordan/Riley native Allowed grid and stated Jamie/child command bindings ready; other bindings pending |
| APP02 | C | Observe exactly the expected usable window, named launch denial, hidden launcher, or closure of a previously observed window. Inputs include route, result and earlier window observation when required. | `AccessibleUI.native_app_snapshot/native_app_closed` independently observe the owned primary native window and exact initial activity, then complete absence with the recognized desktop after `onpc_app_rows::native_close_app`; [native qualification](#native-fixture-preparation) includes Jordan/Riley grid bindings. [Distinct-user retention](#distinct-user-retained-app-qualification) adds Jamie's command-window presence. UI01 → UI03 for presence; FILE06 for command denial; UI11 for hidden/closed surface with a recognized surrounding UI. Hidden launcher alone cannot prove blocked execution. | Jordan/Riley native Allowed grid presence/normal closure and stated command bindings, plus Jamie command presence ready; denial, hidden and other bindings pending |
| APP03 | C | Perform one declared normal app input and observe its customer-visible effect, proving usability. Repeated game actions are separate bounded invocations. | `onpc_app_rows::native_use_app` composes guarded public Submit draft through `AccessibleUI.native_app_submit` and separate exact submitted-label readback; [native qualification](#native-fixture-preparation) includes Jordan/Riley grid bindings. [Distinct-user retention](#distinct-user-retained-app-qualification) adds Jamie command submission and Jamie/Riley resumed submission on their original windows. UI01 → one of UI04, UI05 or UI06 according to the declared input mode → UI03 or UI02 according to the declared result projection. App action/expected effect is fixture data. | Jordan/Riley native primary grid draft submission and stated Jamie/child command and retained-window bindings ready; other actions/bindings pending |
| APP04 | C | Read a recognizable public activity/window state, or compare it after legitimate return. Inputs declare capture/compare and the earlier immutable observation. | `AccessibleUI.native_app_snapshot(with_window=True)` / `native-activity` read the owned public window endpoint and exact submitted draft. `AppActivityObservation`, `compare_app_activity` and `InstalledJourney.check_activity` copy immutable captures and compare explicit `JourneyPlan.activity_checks` endpoints; `onpc_app_rows::native_read_activity` supplies caller-owned invocation IDs. APP02(present) → UI03 → UI12 only for compare; [native activity qualification](#native-fixture-preparation). A newly launched window cannot satisfy retained-activity expectations. `overlay-native-activity` adds the fixed Riley command binding and two exact retained-window/draft comparisons after normal Cancel; see the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification). [Distinct-user retention](#distinct-user-retained-app-qualification) qualifies Jamie/Riley captures and original-window comparisons through Switch User. No hidden process/window inspection. | native primary submitted-draft capture/same-window comparison and stated Jamie/Riley cross-user retention ready; other bindings pending |
| APP05 | C | Prepare the real offline game's declared windowed/fullscreen mode and reproducible level through shared supported commands or keyboard shortcuts, then observe active gameplay. Game settings menus are supporting setup. | Bind startup options in the preceding APP01 launch, or use a fixed supported command/UI05 shortcut on the observed game; do not relaunch retained activity. UI01/UI03 verifies the mode/level, then APP03 proves actual gameplay input/effect. The selected game needs usable public observations; a menu or timer fixture is insufficient. | pending |
| APP06 | A | Read one complete, account-scoped public projection of Lunar's tray/background control, Lunar window and Minecraft activity, with the recognized surrounding desktop. Presence/absence is explicit input; do not launch, reveal or quit anything. | No callable yet. The [Lunar profile slices](#lunar-client-preparation-and-observation-gate) separately qualify Lunar/tray, Minecraft activity and login observations, including absence and incomplete/wrong-owner refusal. UI22 composes repeated observations across the declared login interval; one final absent window cannot establish blocked autostart. [Consumer gate](#lunar-client-preparation-and-observation-gate). | pending |

The qualified FILE03 Save binding uses `AccessibleUI.save_chooser_operation`,
`attachment_composition.save_handoff/save_cancellation` and matching
`onpc_feedback_read` fragments. `check_e2e_save_chooser` qualifies Nautilus
`1:50.2.2-0ubuntu0.2`, English/US, `parent-feedback`: collection-ready
independent entries, wrong-entry/mode refusal, exact directory/name proof,
one real Save, chooser closure, independent file/app read and fresh Cancel
preserving the existing saved output without another file.

All customer downloads use
[download_destination.download_directory](../../tests/e2e/download_destination.py)
with the bound home, placing the ZIP directly in `~/Downloads`.
FILE05 `save_destination_actions/synthetic_files_guest.save_operate`
independently prepare/read the destination, preserve existing contents, refuse
conflicts and clean only identity-verified owned objects.
Case 155 adds fixed `save_handoff(destination='unwritable',draft='synthetic-first')`
to `~/Downloads/Unwritable`, mode `0500`, independently checked as saving
user. Chooser closure must precede exact app subtitle
`Could not save logs. Try another location.`; provider error is insufficient.
Separate Cancel/failure preservation checkpoints require unchanged empty output,
same draft, single-use receipt and uncertain-command refusal. Native GTK/other
destinations remain unqualified.

Nautilus's [filename widget](https://github.com/GNOME/nautilus/blob/50.0/src/resources/ui/nautilus-file-chooser.blp)
collapses on focus loss. After exact location read/Escape,
`save_chooser_restore_name` invokes the unique button whose `LABELLED_BY`
targets `filename_label`, then requires revealed `filename_entry` and
unchanged exact name. This is a provider-local semantic binding; never Reset
File Name. Duplicate labels/buttons, wrong owners/modals or uncertainty refuse.

#### Customer artifact read boundary

Read only declared synthetic files or the exact customer file from that caller's
successful Save, as the bound user in its owned attempt. Pin directory/file
descriptors, owner and receipt; reject traversal, symlinks, hardlinks, replacement,
wrong attempt/user/artifact and unrelated paths. Read actual contents and return
only bounded sanitized comparisons; command success/fixture expectations do not
supply evidence. Source logs, private drafts and collector/broker internals are
outside this public-output boundary.

`read_pinned`, `inspect_zip` and `read_declared_zip` use public archive APIs
without extraction. Exact member sets include empty folders; malformed,
duplicate, unsafe, unexpected or oversized entries refuse.

| Qualified profile | Limits and result |
| --- | --- |
| Synthetic text: `check_e2e_document_open` | 1024 bytes; exact declared size/digest and nonempty content, pinned against preparation receipt. |
| Synthetic ZIP: `check_e2e_open_a_customer_document_or_archive` | 64 KiB archive, 16 members, 4 KiB/member, 8 KiB expanded total, five-second inspection, 30-second command; exact text/JSON bytes and `empty/`. |
| Product diagnostic export: `check_e2e_diagnostic_export` | 2 MiB archive, 17 members, 16 MiB/member and expanded total, five-second inspection, 30-second command; fixed `Selected diagnostics.zip` from the caller's successful Save receipt. |

`diagnostic_export_actions` retains the original Save controller and
single-use receipt. `read_saved_zip` revalidates before/after pinned reads in
`download_directory(home)`. Existing owned Downloads may be `0755`;
synthetic directories stay `0700`, files owner-only/single-link, and no
existing directory permissions change. The diagnostic profile is qualified on
Ubuntu 26.04/Fedora 44. Require `system-info.json`, four component folders
including empties, exact dated logs (at most three/component), schema 3,
frontend system info/health/counters and full readable headings/record counts.
The closed-format parser validates every exported record/category/description;
legacy `undated.log` is outside this fresh-package binding.
Reject declared synthetic account/email/draft/file values in exported bytes.

Real Download/Save/Cancel/save-error/Privacy and independent same-dialog
endpoint/PID/body/reply/attachment/control comparisons remain separate product
results. No Files/archive/text-viewer qualification is needed for inspection.
Retained work still requires real app launch/edit/save and APP01/03/04/FILE09
activity; synthetic readers do not qualify it or other export profiles.

#### Synthetic source change

`change_attachment_source(..., profile='standard'|'single')` in
[synthetic_files.py](../../tests/e2e/synthetic_files.py) reuses the fixture
controller and carries its updated receipt through cleanup.
Change only `Synthetic note.txt` from its fixed 26 bytes to fixed 34-byte
`ONPC changed synthetic attachment\n`; preserve other files/directory identity.
No caller paths/content. Validate original receipt/owner/mode/link count/bytes,
pin descriptors, perform one bounded write and independently read exact bytes
over guarded SSH. Uncertainty latches failure and forbids replay/obsolete-receipt
cleanup; traversal, wrong owner, symlink, replacement, changed original or
hardlinks refuse without mutation. Cleanup checks carried receipt and absence.
`check_e2e_edit_and_save_an_open_synthetic_document` qualifies these two
profiles only; attachment frozen-byte/remove/re-add effects and retained work
remain distinct.

#### Attachment chooser handoff

Use the real external chooser under the
[UI mandate](../Mandates/UI-Automation-Mandate.MD).
`AccessibleUI.chooser_operation`, [public_atspi.py](../../tests/e2e/public_atspi.py),
[file_chooser.py](../../tests/e2e/file_chooser.py) and
[onpc_feedback_read.pm](../../tests/integration/graphical_smoke/lib/onpc_feedback_read.pm)
own shared mechanics. Open Add files; use Location once and public EditableText
whole-directory replacement with trailing slash/exact readback; Enter, then
public SelectAll only after complete exact batch readback. Observe selected
files before one Open; independently require chooser closure and exact app
attachment IDs/names/ready status. Reopen/Cancel must preserve attachments.

Qualified Parent Open/Cancel provider:
Nautilus `1:50.2.2-0ubuntu0.1` and `1:50.2.2-0ubuntu0.2`,
`en_US.UTF-8`, `xkb/us`, through `check_e2e_file_chooser`.
Native GTK, other profiles/tuples and Save remain separately qualified.
Nautilus's custom selection model lacks GtkMultiSelection's hint; prove exact
selected files through public Selection readback instead, while native GTK keeps
its hint check. Map only registered English labels with the exact `. File`
suffix; folders/extra suffixes refuse. Keep current `button` and legacy
`push button` roles, provider-local Nautilus Close/native GTK Cancel,
portal Request ownership and snapshot-scoped prompt guards inside the adapter.

`attachment_composition.file_handoff/chooser_preservation/attachment_removal`
and their `onpc_feedback_read` counterparts are shared by cases and qualifiers.
Callers own entry, fixture lifetime, phase boundaries and refusal exercises;
renamed invocation prefixes change evidence, not operations/results.
Keep the controller/exact receipt through cleanup. Wrong owner, ambiguous dialog,
unexpected files, partial selection and uncertainty refuse without replay.
No folder browsing or per-row selection tour is needed.

The standard two-file, one-file and six boundary profiles are finite bindings,
not arbitrary-file APIs. `feedback_snapshot(attachments=True)` proves
IDs/names/readiness only; sorted names do not prove displayed order, sizes,
removal, preview or rejection. Those require independent item/result projections.

#### Formatted one-file draft lifecycle

`parent_feedback_draft.PLAN` (case 152) has a shortened qualified composition
on Ubuntu 26.04/Fedora 44. `fixture_actions(('single',))` stages only the
26-byte `Synthetic note.txt`; `supply_files(..., 'draft-chooser')` retains
exact-directory/selection guards without qualifying Save or a new tuple.

`feedback_snapshot('formatted')` reads `body-smoke` text/emoji, reply and
bold/normal ranges; `formatted-file` adds exact ID/name/displayed 26-byte size
and diagnostics. Accept only the original confirmation or cleared status after
collection on reopen; errors refuse. `compare_formatted_draft` and
`FeedbackDraftJourney` require complete independent earlier captures.
DESK10 preserves the same window/PID/draft; FEED05 opens/closes owned Privacy.
Full block/link/format matrices stay in UI.

Share `window_switch_entry/prepare_window_switch` and
`feedback_composition.privacy_review/onpc_feedback_privacy::review_privacy`.
Compare explicit immutable endpoints by operation even with renamed stages.
`preserve_dialog`, `app_exit` and prefixed `onpc_window::close` keep
fresh close-recipient proofs. After Parent relaunch, the first complete feedback
read must show empty body/reply, no files/block/link semantics and normal inline
attributes before any input; it is the reset result without duplicate read.
No Send. Other surfaces/profiles remain pending.

#### Attachment rejection boundaries

`attachment_boundaries.PLAN` / `AttachmentBoundariesJourney`,
`check_e2e_attachments`, `boundary_batch` and `chooser_handoff` bind the
Nautilus `1:50.2.2-0ubuntu0.1` English/US boundary profile.
`SyntheticFiles` stages exclusively owned exact directories with receipts:

| Profile | Fixed files/contents |
| --- | --- |
| `count` | `Count 1.txt`…`Count 5.txt`, one `C` byte each |
| `sixth` | `Count 6.txt`, one `C` byte |
| `maximum` | `Maximum.txt`, 5 MiB of `M` |
| `oversized` | `Oversized.txt`, 5 MiB+1 of `O` |
| `total` | `Total.txt`, 3 MiB of `T` |
| `overflow` | `Overflow.txt`, 3 MiB+1 of `X` |

SelectAll requires the exact profile file set and complete selected-file
readback. Independent `before/result/preserved` reads include IDs, names,
displayed sizes/order, status and diagnostic inclusion; compare immutable lists
after both rejection reads. Five files pass; sixth rejects unchanged.
After public removal/diagnostic exclusion, 5 MiB passes and 5 MiB+1 rejects;
5+3 MiB passes exactly 8 MiB, while 5 MiB+3 MiB+1 rejects preserving the 5 MiB
file. Require `No logs attached` and hidden Download. Count cached diagnostics
only when included. No Send or complete-case credit; other filenames, mixed
sets/source changes/surfaces/previews remain separate.

#### Attachment item metadata and removal

`feedback_snapshot(attachments='details')` reads `Second note.txt` /
`Synthetic note.txt` in displayed order with 33/26-byte sizes. Resolve owned
attachment IDs, using the unique visible `DESCRIBED_BY` relation target within
each complete row; GTK Description may be empty. Missing/duplicate/stale/foreign/
mismatched metadata refuses; displayed order is a result, never identity.

`attachment_operation` binds `attachment-details/wrong-entry/remove/remaining`.
Remove Second note once by owned Remove ID. While GTK queues activation, allow
only the exact valid pre-action list, then require Synthetic note/26 bytes and
diagnostics. Wrong removal/uncertain input refuses without replay.
`attachment_items.py` shares `AttachmentJourney`, `file_handoff` and
`supply_files`; fixture profiles retain controllers before transport and
refuse repeated preparation/cleanup without the owned set.
`check_e2e_attachment_items` qualifies this slice on the chooser tuple.
Reduced case 154/`parent_feedback_attachments.PLAN` /
`onpc_feedback_privacy::_attachments` owns installed Open/Cancel/metadata/
removal; full boundaries remain UI. No Send/export or offered-preview credit.

#### Attachment preview applicability

`attachment_operation('attachment-preview')` /
`feedback_snapshot(attachments='preview')` and
`check_e2e_attachment_preview` qualify only the Parent two-file
`not-offered` result. Resolve owned `feedback-preview-availability-*` IDs,
the public **Preview is not available** label and row action set.
Generic `row.activate` and label clipboard/link actions are not previews.
Wrong owners/actions, missing/ambiguous IDs or changed metadata refuse.
A newly offered preview requires its own route; external editor/private file
inspection cannot replace public preview acceptance.

`attachment_preview.py` and shared
`attachment_composition.AttachmentJourney` compare independent preview/return
lists against immutable `attachment-details`, including names/sizes/order.
Resolve plan operation names so renamed invocations keep comparisons.
Reuse chooser provider scope; other profiles/surfaces remain pending.

#### Synthetic file commands

`SyntheticFiles.call`, `synthetic_files.qualify` and `check_e2e_files`
qualify fixed staging/copy/rename/list/read/cleanup for `Synthetic note.txt`,
`Second note.txt`, `Synthetic copy.txt` and `Renamed synthetic note.txt`.
Exact bytes live in
[synthetic_files_guest.py](../../tests/e2e/synthetic_files_guest.py).

Guarded SSH runs as canonical Parent under private
`.onpc-e2e-synthetic-files`. Fixed operations take a nonblocking shared directory
lock and verify canonical paths, owner/mode, regular single-link files,
exact bytes and prior inode receipts. Refuse unknown/replaced objects, traversal,
unregistered/wrong-order operations, symlinks/hardlinks and wrong owner.
Copy is exclusive; rename refuses existing destination. Cleanup requires the
complete owned receipt and independent absence. Uncertain transport permanently
stops that controller without replay or guessed-ownership cleanup; outer VM
ownership retains failure evidence/restoration. These are fixture capabilities;
chooser, attachment, editing and enforcement outcomes remain separate.

### Time and ordinary lifecycle boundaries

LIFE04/05's current `PackageCommand.read_result` requires the final reboot
notice for its installed upgrade bindings. the corresponding qualifications must implement
their finite no-action/process/session notice and independent completion
projections before qualification; the checked genuine-upgrade history supplies
the unchanged package envelope, not those new notice branches. Reuse one real
transaction per declared binding and retain each complete case's persistence
and enforcement results.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| TIME01 | C | Read the child's remaining usable time during activity or session return. Retain stable absence on the limits-off desktop as a qualified supporting observation; local lock/greeter visibility belongs to UI obligation 052b. | UI01 → UI03, or UI11 with the destination positively identified. `AccessibleUI.child_countdown(present)` / `countdown.CountdownObservation` and `check_countdown_balance`; [child-desktop qualification](#child-desktop-countdown-qualification). | child-desktop horizontal presence and limits-off absence ready; E2E-011 daily-only/grant-only/combined ready on Ubuntu 26.04; other new customer time/session bindings need qualification, local visibility is UI scope |
| TIME02 | C | Compare displayed remaining time across real activity with public starting balances, elapsed intervals and explicit precision/tolerances. This supports actual time-use and expiry outcomes; tick formatting belongs in UI tests. | `countdown.CountdownSample`, `check_countdown_progress` and `await_countdown_progress` compare immutable minute or exact-second endpoints bracketed by controller monotonic reads, including an explicitly declared minute-to-seconds transition. TIME03 `interval_action` retains the original bound and attempt guard. `countdown_qualification.MINUTE_PLAN` / `CountdownMinutesJourney` and `TICK_PLAN` / `CountdownTicksJourney` share `onpc_challenges` daily-only preparation and independent child reads, qualified by `check_e2e_countdown_minutes` / `check_e2e_countdown_ticks`. No guest clock/usage manipulation. [Minute qualification](#minute-countdown-progression-qualification) and [final-second qualification](#final-second-countdown-progression-qualification). | minute and final-second progression ready on Ubuntu 26.04 and Fedora 44; E2E-011 daily-only/grant-only/combined ready on Ubuntu 26.04; other customer bindings pending |
| TIME03 | A | Let a declared bounded real interval elapse while retaining the runner guard and deadline. Return elapsed time only; this does not prove a lock or grant expiry. | `real_interval.wait_real_interval(duration, deadline=absolute_monotonic, guard=attempt_guard, progress=callback)` accepts finite durations through 300 seconds, checks ownership/deadline between sleeps of at most 250 ms and publishes five checkpoints. `interval_action(duration)` binds it to an `InstalledJourney` stage action using the guard's attempt deadline. `real_interval_qualification.PLAN` / `onpc_parent_about::run_interval` passed `check_e2e_wait_a_bounded_real_interval_under_the_attempt_guard`: five real seconds between independent unchanged About endpoint/PID/product/version reads, valid entry and wrong-entry refusal, collection, owned cleanup and baseline restoration. Host safety checks cover lost ownership, deadline, cancellation, recorder failure and durable reply refusal. No product state follows from elapsed time. | guarded elapsed-time helper ready; five-second About slice qualified; complete consumers remain separate |
| TIME04 | C | Use the selected app/game until natural expiry, then observe the lock owning normal input and loss of desktop access. Earlier visible time and the timeout are explicit inputs. | `natural_expiry_observation.await_natural_expiry` consumes an immutable countdown and original activity under the original display upper bound plus 15 seconds and attempt deadline. `AccessibleUI.natural_expiry` binds the child session/window before ordinary Submit input, stops input near zero or Lock, and reuses the qualified curtain/restriction reader without inspecting the app underneath. `NaturalExpiryJourney` / `onpc_challenges::natural_expiry` add fresh lock-ready → harmless Shift → independent same-lock read through `check_e2e_natural_expiry`; [installed qualification](#natural-enforced-lock-qualification). A native time restriction needs no password field; input ownership alone supplies no authenticated-denial result. | Riley/native two-minute daily-only binding ready on Ubuntu 26.04 and Fedora 44; E2E-011 daily-only/grant-only/combined ready on Ubuntu 26.04; other app/game/fullscreen and customer bindings pending |
| LIFE01 | C | Close and reopen one named ordinary app through a shared direct command, unless the case explicitly tests its graphical launch route; observe its opening window. Do not reselect a child or restore settings before reading them. | `onpc_lifecycle::reopen(journey, 'parent', prior_window, 'management')` consumes `prior-window`, independently guards the active owned window, composes UI18 → PARENT01, then reads the initial child selection before edits. `app_restart.PLAN` / `onpc_app_restart::run` passed `check_e2e_app_restart`: fresh entry, already-closed and wrong named-window refusal without repair, complete old-window absence, new management window, initial selection, collection, owned cleanup and baseline restoration. Shared launch/close helpers are unchanged. Other ordinary apps use APP01 with the declared route; overlay/kiosk reopening uses their explicit exit/entry blocks. | Parent→management ready with the baseline eligible children; other apps/bindings pending |
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

#### Natural enforced lock qualification

`check_e2e_natural_expiry` qualifies the fixed two-minute daily-only Riley
binding on Ubuntu 26.04 and Fedora 44. Public Parent controls prepare zero grant,
then fresh child entry opens the actual native fixture app. An immutable initial
`00:01` observation supplies the 61–119-second display interval and original
upper bound plus 15 seconds. Ordinary Submit actions demonstrate activity until
near zero; independently observe the owned curtain within elapsed bounds.
Fresh lock-ready and post-Shift reads must prove the same session/surface with
desktop input unavailable, without inspecting the app underneath.

Wrong account, changed boot/session/window, uncertain input, early/late lock and
worker-order guards remain mandatory. Parent launch preflight may retry fresh
read-only prompt checks when an accessibility provider retires; command input
is submitted once. Elapsed time alone never proves Lock. The qualified provider
tuples are GNOME Shell `50.1-0ubuntu1.3` (Ubuntu) and `0:50.5-1.fc44` (Fedora),
both `en_US.UTF-8`, `xkb/us`.
Authenticated denial, other apps/games, fullscreen, reminder delivery and
complete customer histories remain separate.

Complete E2E-011 cases 27 and 28 compose TIME01/02/04 with the qualified direct
child lock/unlock and original native activity operations. Daily-only case 27 uses
[`countdown_daily.PLAN` / `CountdownDailyJourney`](../../tests/e2e/countdown_daily.py)
and `onpc_challenges::countdown_daily`; its affected Ubuntu 26.04 regression passed
in `20261030T092025Z-90141f75` with public four-minute/no-grant preparation.
Grant-only case 28 uses
[`countdown_grant.PLAN` / `CountdownGrantJourney`](../../tests/e2e/countdown_grant.py)
and `onpc_challenges::countdown_grant`; it passed in `20261030T090926Z-dabc2614`
with zero daily time and one real two-minute approval. Both passed retained
original usable work and resumed time, minute/final-second progression, natural
lock and same-lock input ownership, collection, worker shutdown, recording,
owned cleanup and baseline restoration. This qualifies those complete bindings
on Ubuntu; Fedora acceptance remains separate.
Combined case 29 uses
[`countdown_combined.PLAN` / `CountdownCombinedJourney`](../../tests/e2e/countdown_combined.py)
and `onpc_challenges::countdown_combined`. It passed on Ubuntu 26.04 in
`scenario-55432f8076bd426581bd5feff022816d`: public four-minute daily allowance,
real two-minute addition, Parent G>D>0/total=max(D,G), preserved usable work and
resumed time, minute/final-second progression, natural lock and same-lock input
ownership. Collection, worker shutdown, recording, owned cleanup and baseline
restoration passed. The shared minute-edge comparison retains three edges for
daily-only and permits five for combined; affected case 27 passed separately in
`scenario-39dd5708640a446588ceea8730b0ddb1` with the same complete cleanup.
The [recipe](E2E-Scenario-Recipes.md#e2e-011) owns its finite margins and endpoints.

#### Installed restart notice qualification

`check_e2e_restart_notice` qualifies the English three-surface binding on
Ubuntu 26.04. Genuine product-free installation supplies package completion and
the reboot notice. Parent, direct Child App and kiosk each show an owned modal
before language/policy setup, Close without boot change, then show it again on
ordinary reentry. Wrong-owner refusal precedes input.

One public kiosk Reboot now must produce an independently verified new boot and
usable GDM. Fresh Parent is usable without a modal and refuses missing-modal
reboot. Parent then saves enabled 30-minute allowances for Riley and Jamie;
fresh Child App/default kiosk entry requires enabled Request without a modal.
Verify installation's disabled defaults before this public setup.

`journey_blocks.restart_reentry` / `onpc_customer_reboot::restart_reentry`
share the same-boot Close/normal exit/reopening fragment between LIFE07 and
complete Parent/Child App/kiosk histories. Complete bindings are:

- E2E-056 `parent`, case 257: `fresh_parent_restart.PLAN` /
  `onpc_customer_reboot::run_parent_notice` composes installation, Parent
  Close/reentry, one public Parent reboot, independent new boot/usable GDM/
  fresh administrator entry and usable Parent without the modal.
- Case 259: `fresh_kiosk_restart.PLAN` /
  `onpc_customer_reboot::run_kiosk_notice` exits to GDM and reenters the station
  afresh. After its public kiosk reboot, Parent publicly enables Jordan for
  30 minutes before fresh usable Jordan/Jamie request entry without the modal.
  `journey_blocks.restart_kiosk_usability` /
  `onpc_customer_reboot::restart_kiosk_usability` share explicit Jamie
  selection and independent final usability with LIFE07. Other eligible
  administrators remain; never assume initial account order.
- E2E-057 `child`, case 258: `fresh_child_restart.PLAN` /
  `onpc_customer_reboot::run_child_notice` composes direct pre-policy Child App
  entry, overlay-modal reboot, independent boot/GDM result, public postboot Riley
  setup and fresh fixed-child request usability.

These complete bindings are qualified on Ubuntu 26.04 only.
`journey_checks.restart_instructions` binds literal neutral recipe text to each
fresh owned read before response/reboot. Preserve wrong-child/approver,
disabled-control and uncertain-input refusals. Qualification grants no unrelated
reboot, request, other-language or visual acceptance.

#### Child desktop countdown qualification

`check_e2e_countdown` qualifies enabled/off bindings on Ubuntu 26.04 and Fedora
44 in separate restored attempts. `countdown_qualification.PLAN` / `OFF_PLAN`
and `CountdownJourney` compose shared fresh Parent/child entry and public
allowance setup; `onpc_challenges::countdown` reuses qualified login/Switch User.
Both save/read positive 15-minute daily allowance; off additionally disables
limits and reads that result. No complete scenario is qualified.

`AccessibleUI.child_countdown(present)` requires the active intended child and
a complete guarded panel observation. Presence resolves owned IDs
`child-screen-time-indicator`, `child-request-button` and `child-remaining-time`
on the bound `child-panel`, then reads bounded horizontal HH:MM/final seconds.
Complete absence of all three visible controls must persist for two seconds;
wrong-session, incomplete or defunct reads restart that interval. Wrong owners,
duplicate IDs, unknown prompts, inactive/wrong accounts and malformed text refuse.

`countdown.CountdownObservation.from_value` returns an immutable result.
`countdown.check_countdown_balance` takes explicit public seconds, precision
and monotonic timestamp. Allow at most 180 real elapsed seconds, reported
precision (one second in this qualifier), minute flooring above 60 seconds and
30 seconds of estimate/sampling tolerance by default. The developer explicitly
extended this allowance to all balance-to-countdown comparisons; a caller may
declare a smaller `sampling_seconds` value. Historical qualifications used two
seconds. This does not change countdown-progress tolerances, original expiry
deadlines or required denied-access results. No private clock/usage/grant/policy
manipulation supplies results. Independently repeated desktop reads and
wrong-account refusal require no observer preparation/input.

The original installed provider tuple is Ubuntu 26.04, Shell
`50.1-0ubuntu1.2`, GDM `50.1-0ubuntu0.1`, `en_US.UTF-8`, `[["xkb", "us"]]`.
The unchanged enabled/off bindings also have renewed both-target qualification.
Local availability and explanations remain UI obligations rather than customer
journey prerequisites; the installed session boundary is qualified below. Installed
remaining-time, natural exhaustion and complete cases retain separate bindings.

#### Locked and inactive child countdown qualification

`check_e2e_countdown_session_availability` passed on Ubuntu 26.04 in
`20261030T013630Z-abcfcb7b`, using `countdown_qualification.SESSION_PLAN` /
`CountdownJourney` and `onpc_challenges::countdown_session`. One public positive
15-minute allowance precedes fresh child entry, explicit Lock, greeter return
without another Lock, and legitimate retained-child authentication. Shared
session commands and the existing GDM challenge independently verify destinations.
The observed provider tuple is Shell `50.1-0ubuntu1.4`, GDM
`50.1-0ubuntu0.1`, `en_US.UTF-8`, `[["xkb", "us"]]`.

`AccessibleUI.child_countdown_session` pins the child's graphical session,
same-user ChildUI owner, Shell process and public animation preference before
Lock. Complete inventories from that child's bus require all six panel controls
unavailable while locked and while inactive at sign-in, with two seconds of
stable reads. Request/menu activation and preference input refuse; independent
inventories verify request absence and unchanged preference after each refusal.
Absent endpoints, lost owners, incomplete inventories and wrong sessions fail;
the greeter's separate Shell is never used as the child's panel.

Retained return restores the same pinned session/owner/preference and the normal
positive countdown, compared against the earlier public Parent balance.
`child_countdown` keeps its unlocked-active-child entry guard. Collection,
worker shutdown, callback closure, owned cleanup and baseline restoration passed.
This supplies 052b's OS-dependent component observation, with no new customer
scenario or natural-expiry/cross-account qualification.
Affected enabled/off and animation-preference regressions also passed on Ubuntu
in `20261030T014248Z-f87a3274` and `20261030T015144Z-d0647819`, with their owned
cleanup and baseline restoration. Scoped host/source checks passed; no product
backend code changed.

#### Minute countdown progression qualification

`check_e2e_countdown_minutes` qualifies both targets under the
[screen-time compatibility contract](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement).
`countdown_qualification.MINUTE_PLAN` / `CountdownMinutesJourney` publicly
prepare four daily minutes with zero grant, independently enter the child and
compare two successive minute progressions in that same session:
`00:03` → `00:02` → `00:01`. Use immutable endpoints and controller monotonic
read brackets with a 90-second bound and two-second tolerance.

Qualified Shell/Malcontent tuples are `50.1-0ubuntu1.3` /
`0.14.0-0ubuntu1.2` (Ubuntu) and `50.5-1.fc44` / `0.14.0-1.fc44` (Fedora).
Reject reversed/stale/wrong-owner samples, unchanged/increased values, exceeded
elapsed bounds and lost guards. Acceptance uses no clock changes, private usage
probes or synthetic grants.
[Final-second progression](#final-second-countdown-progression-qualification)
has separate scope; natural-expiry acceptance remains TIME04 and installed
suspend/resume remains pending LIFE03. This supplies no complete-scenario credit.

#### Final-second countdown progression qualification

`check_e2e_countdown_ticks` qualifies Ubuntu 26.04 and Fedora 44.
`countdown_qualification.TICK_PLAN` / `CountdownTicksJourney` reuse the minute
sampler; `onpc_challenges::countdown_ticks` shares its guarded daily setup and
fresh-entry worker. Parent publicly saves two daily minutes with zero grant.
The child independently supplies `00:01`, transitions into positive exact seconds
and supplies two successive positive exact decreases within one session.

Transition retains its original 90-second bound. Each exact progression has
15 seconds from the previous immutable endpoint; independent stage reads may
supply progress without reseeding the deadline. Declare 60→1 or 1→1-second
precision, include controller read latency and permit two-second estimate
tolerance. Read-only waits retain TIME03 and the attempt guard; sampling every
second or identifying individual timer callbacks is unnecessary.

Qualified Shell versions are `50.1-0ubuntu1.3` and `0:50.5-1.fc44`, both
`en_US.UTF-8`, `[["xkb", "us"]]`. Preserve independent child entry,
wrong-account/lost-guard/stale/reversed/increased-value refusal and missed-window/
durable-reply guards. No clock change, private usage read or synthetic grant
supplies acceptance. This covers only horizontal daily-only minute/final-second
behavior; expiry, suspend and complete histories remain separate.

For LIFE06, recipe disconnect/reconnect means removing/restoring Internet access,
not disabling the guest adapter. Use the same qualified VM-level mechanism on
both distributions, retaining controller access and denying alternate routes.
Once isolation/owned restoration are qualified, consumers focus on product
results. Restore through the same helper from the current child desktop or GDM;
no Parent visit/login is needed solely for recovery.

### Owned VM Internet isolation

`vm_internet.InternetIsolation(lease).enter(transport)` requires the owned
running domain instance, matching guarded SSH transport and one unchanged NIC
on the active libvirt `default` network. It creates only a run-owned nwfilter/
tap binding through public libvirt APIs: allow exact controller/guest ARP and
controller-initiated SSH; deny IPv4/IPv6 Internet and other Ethernet
encapsulations. Guest/shared network configuration is unchanged.

Use the context manager around offline actions. `vm_internet.restore(lease)`
also runs in outer lease cleanup/recorded recovery. Durable intent precedes
mutation; wrong transport, uncertain replay, changed domain/network/resource
identity, foreign references and reused taps refuse before cleanup mutation.
A restored journal still audits resource absence. Snapshot transitions refresh
the pinned domain handle because libvirt caches its instance ID. Compare XML
exactly except the read-only root `connections` count; retain raw private
journal XML and all configuration checks.

`vm_internet_qualification.online_offline_online` owns finite helper
qualification. Consumers use isolation and
`vm_internet_qualification.internet_result(transport)` for independent bounded
TCP/UDP DNS observations without inheriting the qualifier journey.
Offline language composition requires at least one reachable baseline path,
all declared probes blocked during isolation and recovery of every initially
working path. An initially unavailable endpoint may recover without failing
the product case. Exhaustive endpoint availability belongs to helper
qualification; the shortened language composition remains pending live verification.

`parent_setup_qualification.IndependentNetworkQualification` /
`check_e2e_independent_network_management` qualify the fixed Ubuntu binding:
online → offline → online, fresh SSH/public desktop reads, watch reconnects,
wrong-entry/replay refusal and exception-unwind restoration. IPv6 scope is
denial plus probes when a route exists; a baseline without an IPv6 default route
does not qualify live IPv6 traffic. Parent usability and other customer results
remain separate.

`offline_controls.offline_controls` composes declared public input/readback
with that isolation lifetime. Pin the active Parent endpoint/PID before isolation,
compare around each input/after recovery, and independently probe connectivity
before/during/after.
`public_connectivity_controls.PLAN` / `qualify` reuse unchanged UI17 through
`onpc_parent_toggle::run`, fresh qualified sign-in and PARENT01 rather than
autologin/autostart preparation. `check_e2e_operate_public_connectivity_controls`
qualifies the Ubuntu fixed Parent slice: disabled entry/wrong-child refusal,
offline enable/disable with separate saved-state reads, unchanged active Parent
and Internet recovery. No complete offline approval/enforcement result is
claimed. Runtime-binding failures retain bounded service/session state on
private command stderr without changing input, timeout or refusal checks.

### About, feedback and customer-selected attachments

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| ABOUT01 | C | Open the declared surface's About entry; read product/version and reach the license information. Parent, overlay and restricted kiosk bindings are ready. Kiosk reads plain legal information and proves external actions absent. | Parent: `onpc_about::open_about` / `AccessibleUI.open_about(version)`. Kiosk: `AccessibleUI.open_kiosk_about` / `read_kiosk_about(version)`; `onpc_window::close('station-about')` returns to the unchanged form. Overlay: `AccessibleUI.open_overlay_about` / `read_overlay_license` / `read_overlay_link`; `journey_blocks.overlay_license_read` / `onpc_about::overlay_license` close only owned About and return to captured choices. The finite `information` binding includes Help and every About link through `overlay_license.INFORMATION_PLAN`; complete case 191 uses `overlay_about.PLAN` / `onpc_parent_about::run_overlay` with shared `KioskRequestJourney` comparisons. UI01 → UI04(menu) → UI04(About) → UI01 → UI03 → UI09, plus kiosk UI11 exclusion. [About contracts](#about-block-contracts). | ready for Parent/kiosk/overlay; [Parent English/Hebrew inherited text and keyboard](#parent-inherited-dialog-qualification) qualified; full overlay information qualified by `check_e2e_read_overlay_about_and_links`, license and website/privacy regressions passed; complete case 191 passed on every enabled VM (Ubuntu 26.04) with collection and owned cleanup |
| ABOUT02 | C | Check the owned license link is clickable without invoking it or inspecting its URI/destination. | `AccessibleUI.open_license` is a compatibility name for `clickable_link('about-license-value', root=about())`; overlay `read_overlay_license` uses the same reader under `overlay_about_scope(opened=True)`. No external handler/content dependency. `check_e2e_license_viewer` retains its selector name for Parent link-only qualification. [Scope](#about-block-contracts). | ready for Parent link-only scope and overlay scope |
| ABOUT04 | C | Reach and read the About footer in the already open About window through semantic ID reveal. | `onpc_about::read_footer(journey, returned, 'semantic-reveal')` delegates to `AccessibleUI.about_footer`: UI09 → UI03(footer), with no preliminary positional keys. [About contracts](#about-block-contracts). | ready |
| ABOUT03 | C | Close only owned About and compare the selected child/settings with the supplied earlier observation. | Customer information return uses `onpc_about::close_information`, consuming the information observation and a fresh owned close proof before UI18; `JourneyPlan.settings_checks` supplies UI12. The historical `onpc_about::return_to_parent` link-only qualifier additionally composes ABOUT04 → UI18. Its footer read is not a prerequisite of the customer information return. No external window or handler is inspected/closed. | historical Parent link-only scope ready; shortened information-return composition awaits live verification; other bindings pending |
| FEED01 | C | Open ordinary Parent feedback through its Feedback action and observe editor/collection state. Error-report entry uses FEED15; no hidden error creation. | `AccessibleUI.open_feedback(projection='initial-empty', language=None)`: UI01 → UI04(`parent-feedback-button`) → UI01 → UI02 → UI03. `feedback_read.PLAN` / `onpc_feedback_read::run` qualified initial empty entry and independent reopen through `check_e2e_feedback_read`. `check_e2e_feedback_privacy` additionally qualified preserved `synthetic-first` entry; collection, owned cleanup and baseline restoration passed. Send remains untouched. | ready for ordinary Parent initial-empty, synthetic-first and [English/Hebrew synthetic-rtl entry](#parent-inherited-dialog-qualification); other bindings pending |
| FEED03 | C | Read the visible synthetic draft, exact attachment list and validation/control state into an explicit observation. | `AccessibleUI.feedback_snapshot(projection, language=None)` → explicit closed comparison: UI01 → UI02 → UI03 → UI13(attachments). `check_e2e_feedback_read` qualified `initial-empty`. `check_e2e_feedback_privacy` qualified `synthetic-first`, including unchanged Privacy/dialog reopening. The [attachment handoff](#attachment-chooser-handoff), [boundary lists/statuses](#attachment-rejection-boundaries) and [formatted one-file lifecycle](#formatted-one-file-draft-lifecycle) add exact finite files, metadata and format comparisons. Never project arbitrary private text. | ready for Parent initial-empty, synthetic-first, [English/Hebrew synthetic-rtl](#parent-inherited-dialog-qualification), formatted single-file, fixed two-file and declared boundary readback; other bindings pending |
| FEED04 | C | Set the retained editor selection using canonical UTF-16 index/length, apply an offered format through its fixed API value/action, then independently read document formatting and text. | `onpc_format`, `AccessibleUI.format_operation`, `block_operation` and shared format composites use `feedback-editor-selection`, formatting IDs and UI24. Synthetic link editing uses fixed link actions without navigation; document insertion and undo/redo use their fixed API operations. | ready for declared Parent bold, four-format complex and `body-blocks` fixtures, linked inline and complete format/removal composition; other bindings and complete scenarios pending |
| FEED05 | C | Open Privacy, read the disclosure/diagnostic explanation, then close it. | `AccessibleUI.feedback_privacy(projection)` → `onpc_window::close('feedback-privacy', proof)` → `AccessibleUI.window_closed('feedback-privacy', 'feedback')`: UI04 → UI09 → UI03 → UI18. Reads the actual ID-owned disclosure about delivery, retention and diagnostic/personal content; opens no external link. `feedback_privacy.PLAN` / `check_e2e_feedback_privacy` qualified Parent synthetic-first and independent reopened entry; case 152 adds the [formatted one-file draft](#formatted-one-file-draft-lifecycle). Draft comparisons, collection, owned cleanup and baseline restoration passed. | ready for Parent synthetic-first and formatted single-file; overlay/kiosk and other projections pending |
| FEED06 | C | Add prepared synthetic attachments through Add files and the actual file chooser, then observe the displayed list or validation. | UI04 → FILE03 → FEED03. The [attachment handoff](#attachment-chooser-handoff) and [item qualification](#attachment-item-metadata-and-removal) cover fixed two-file Parent entry and metadata/order. The [formatted one-file lifecycle](#formatted-one-file-draft-lifecycle) adds the single-file profile. `AccessibleUI.boundary_operation` / `onpc_feedback_read::boundary_batch` qualify the declared [count/size boundaries](#attachment-rejection-boundaries), with independent unchanged-list comparisons after rejection. | ready for fixed single/two-file Parent handoff and declared count/per-file/aggregate boundaries; other inputs/validation pending |
| FEED07 | C | Resolve one attachment row by its stable public ID, then read its displayed synthetic name/size and verify its order if required. Order is a result and never identifies the row. Does not preview or remove it. | `AccessibleUI.feedback_snapshot(attachments='details')` / `attachments='remaining'` → exact public `items`; see [qualified item scope](#attachment-item-metadata-and-removal). `attachment_state` adds the declared [boundary profiles](#attachment-rejection-boundaries); `formatted-file` adds the exact name/size in the [one-file draft](#formatted-one-file-draft-lifecycle). UI01 → UI03 → UI13(order when required). | ready for declared Parent two-file, remaining-file, formatted one-file and boundary profiles; other inputs/surfaces pending |
| FEED12 | C | Open an offered attachment preview, read declared synthetic contents and close it, returning to feedback. Explicitly record an unoffered preview and independently compare the unchanged list. | `AccessibleUI.attachment_operation('attachment-preview')` / `attachment-preview-return` → `AttachmentPreviewJourney` comparison; [qualified applicability scope](#attachment-preview-applicability). Offered route: UI01 → UI04 → UI03 → UI18. An unoffered preview does not authorize private storage inspection. | ready for declared Parent two-file inapplicability and unchanged-list comparison; offered preview and other bindings pending |
| FEED13 | C | Remove one explicitly identified attachment and observe the remaining list. | `AccessibleUI.remove_attachment` supplies `attachment_operation('attachment-remove')` → independent `attachment-remaining` and the explicit [boundary removals](#attachment-rejection-boundaries); [qualified item scope](#attachment-item-metadata-and-removal). UI01 → UI04(Remove) → FEED03 → UI12(expected list). | ready for declared Parent single-item and boundary-profile removals; other inputs/surfaces pending |
| FEED08 | C | Explicitly save diagnostic output to a customer-selected location, inspect that exported artifact through the shared read-only SSH helper, and reobserve the preserved feedback draft. | `attachment_composition.diagnostic_export` / `onpc_feedback_read::diagnostic_export`: UI04(download) → shared `save_handoff(draft='synthetic-first')` → FILE08 through `diagnostic_export_actions` → FEED03 and same-dialog endpoint/PID comparison in `DiagnosticExportJourney`. Qualification revalidated two independent entries; see [export scope](#customer-artifact-read-boundary). `parent_diagnostic_export.PLAN` / `onpc_feedback_privacy::_diagnostic_export` passed full case 155, including synthetic Cancel, `destination='unwritable'` app error before recovery, Privacy and preserved draft. No original product log/storage reads. | ready for named Parent Save/export inspection, Cancel, fixed unwritable-destination error/recovery and preserved synthetic-first draft; other surfaces/destinations pending |
| FEED09 | C | Observe collection, validation, sending, retry, error or thank-you state and control availability. Collection waits for finished diagnostics and available Download; immediate completion passes without observing an intermediate state. Other modes retain their declared state assertions. | `UiObservations.observe('feedback-collection-ready')` → `AccessibleUI.wait_feedback_collection` reuses `AccessibleUI.wait` with complete public ID-owned snapshots. It advances only when collection is finished and Download is available; the deadline only fails a stuck attempt. `feedback_collection.PLAN` / `onpc_feedback_states::run_collection` qualified two independent Parent entries, separate readback, wrong-entry refusal and owned cleanup through `check_e2e_feedback_collection`. `AccessibleUI.feedback_snapshot(projection, states=True)` → immutable `FeedbackStateObservation`; `feedback_states.PLAN` / `check_e2e_feedback_states` qualify the [edit-only Parent snapshots](#feedback-validation-snapshots). `reject_invalid_feedback` / `rejection_operation` and `feedback_rejection.PLAN` additionally qualify the fixed [invalid-only rejection](#feedback-rejection) inputs and exact explanations. `length_operation` / `feedback_length.PLAN` qualify the [ASCII and mixed-emoji boundaries](#feedback-utf-16-boundaries). UI01 → UI02 → UI03 → UI10, or UI22 with the same projections. No provider receipt or delivery-internal assertion. | ready for Parent collection readiness and declared Parent edit-only snapshots, ASCII/mixed-emoji boundaries and empty/malformed/SOH/complex/excessive-text rejection; other validation inputs, sending/retry/success and other surfaces pending |
| FEED10 | C | Close/reopen feedback and compare its in-memory draft. `dialog` preserves the supplied draft; `app-exit` explicitly closes/relaunches Parent and expects reset. Return with feedback open. | `onpc_feedback_privacy::preserve_dialog(journey, before)` composes FEED03(before) → UI18(feedback) → FEED01 → FEED03 → UI12 against an explicit earlier observation. `app_exit(journey, before, invocation_prefix)` composes UI18(feedback) → LIFE01(Parent→management) → FEED01/03(`initial-empty`) before new input. Wrong-entry refusal remains in the isolated `run_reset` qualification, outside the customer fragment. `feedback_reset.PLAN` / `check_e2e_feedback_reset` qualified nonempty body/reply → empty body/reply, no customer-selected files and fresh default diagnostics. `check_e2e_feedback_privacy` requalified dialog preservation. The [formatted one-file lifecycle](#formatted-one-file-draft-lifecycle) extends both comparisons through `FeedbackDraftJourney`; shortened complete case 152 passed on Ubuntu 26.04 and Fedora 44 with collection and owned cleanup. | ready for Parent dialog preservation, isolated reset and formatted one-file case 152; [Parent dialog synthetic-rtl across English/Hebrew changes](#parent-inherited-dialog-qualification) also qualified; other surfaces/profiles pending |
| FEED11 | C | Submit one already reviewed synthetic report. Require explicit sending authorization and dedicated test-recipient configuration; activate the explicit `Send` or `Send without logs` action once and return. Observe the outcome and dismiss confirmation separately. | UI01 → UI02(enabled) → UI04(Send). Supply a current FEED03 draft read and reuse unchanged reviewed-profile/exact-surface FEED05 evidence under the [sending recipe](E2E-Scenario-Recipes.md#sending-background-completion-and-report-exits); no repeated Privacy tour inside this block or its retry/exit consumers. This document grants no sending authorization. | pending |
| FEED14 | C | Dismiss an observed success confirmation normally and observe the expected return surface. | UI01 → UI04(Close) → UI11(confirmation) → UI01(return surface). FEED09 supplies the earlier success observation. | pending |


#### Feedback validation snapshots

`check_e2e_feedback_states` qualifies independent reopened entry and wrong-entry
refusal. `AccessibleUI.feedback_state_operation`
observes edits supplied by the caller through `onpc_text::replace_text`; it never
activates Send. Exact bounded public text comparisons bind these projections:

| Projection | Body | Reply |
| --- | --- | --- |
| `initial-empty` | Empty | Empty |
| `states-whitespace` | Three ASCII spaces (`body-whitespace`) | Empty |
| `states-no-reply` | `Synthetic feedback first` | Empty |
| `states-malformed` | `Synthetic feedback first` | `invalid-reply` (`reply-malformed`) |
| `synthetic-first` | `Synthetic feedback first` | `first@example.invalid` |

UI16's `body-whitespace` and `reply-malformed` bindings require exact public
readback. Each snapshot independently reads Send sensitivity and
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

Case 153 has complete composition acceptance; shared edit-state and UTF-16
qualification remains independent. Neither scope qualifies other local feedback
cases, additional surfaces or sending/delivery behavior.

#### Feedback rejection

`feedback_rejection.PLAN` / `FeedbackRejectionJourney`,
`onpc_feedback_states::run_rejection` and `AccessibleUI.rejection_operation`
are qualified through `check_e2e_feedback_rejection` for empty body, malformed
reply, the authorized SOH fixture
and excessive formatting, exact public explanations, usable controls, independent
reopened entry, wrong-entry and valid-input refusal. No valid report is submitted;
complete case 153
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
`onpc_feedback_states::run_length` and `AccessibleUI.length_operation` are qualified
through `check_e2e_feedback_length` for exact public readback of
5,000/5,001 ASCII `x` characters and 4,998/4,999 `x` characters followed
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

UI16 uses the guarded synthetic-text construction below, followed for mixed
input by
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

No valid report is submitted; complete case
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
`check_e2e_feedback_rejection` qualifies exact construction and its rejection
consumer. New bindings
must declare exact source/result projections and receive consumer qualification.

The four UTF-16 boundary inputs use `TEXT_REPETITIONS`: a 312-character seed,
four API insertions to 4,992 characters, and a 6–9-character suffix through
`onpc_text::repeat_text` / `AccessibleUI.suffix_text_operation`. The host UI test
uses these same public operations. Each source and doubled result is checked
before continuing; exact final ASCII/emoji text and UTF-16 boundaries remain
mandatory. `check_e2e_feedback_length` qualifies the four constructions, exact
ASCII/emoji boundaries, valid-input refusal, invalid-only rejection and independent
reopen. This is scoped qualification, not complete case 153 acceptance.

### Additional public surfaces

These blocks supply the named new consumers in the
[scenario recipes](E2E-Scenario-Recipes.md). Only the explicitly qualified scopes
below are ready; a documented binding does not extend an existing callable's
qualified scope.

The engineering-only selector `check_e2e_kiosk_feedback_confinement` composes
the existing installed eligible-account journey with an attempt-owned broker
runtime mask, one public request failure, broker restoration, the public
Report this error/result dismissal and real feedback editor/diagnostics checks.
Before the outage, the shared valid-choice operation selects rest of day and
independently reads its midnight estimate. This avoids periodic broker estimate
errors opening an unrelated modal before the single Request action.
It uses `kiosk_feedback_confinement.PLAN`, `UiObservations` and the shared
`AccessibleUI.kiosk_diagnostic_*` operations; it never activates Send and grants
no customer-case credit. The root helper retains the mask inode, attempt, boot
and original service invocation for guarded recovery. The privacy operation
opens and closes the in-app disclosure through public IDs, reads the shared
disclosure and independently verifies the unchanged edited document. Complete
identified report/privacy inventories reject unexpected actions, links,
surfaces and modals; the product source audit supplies anonymous-control
completeness. Report identity checks cover logical surface ownership.
The former-candidate qualification covers Ubuntu 26.04/Fedora 44 editable
text/document readback, prepared diagnostics, confined Privacy and hidden/absent
kiosk download/attachment controls, with guarded broker restoration/cleanup.
Ordinary Parent ZIP export remains the separate FEED08 binding.
The current engineering
caller records `system_kiosk_confinement.census()`'s session/compositor/app
identity observation, with `confinement_qualified: false`; optional service
availability has no admission vote. It asserts no private generation or thread
role. Actual public error-report/recovery results still require matching
qualification at their fault/recovery consumer, separately from baseline use.

The separate engineering selector `check_e2e_kiosk_notification_wellbeing`
composes the same installed eligible-account entry with the public reminder
editor's Preview and Cancel actions. `kiosk_notification_wellbeing.PLAN`,
`UiObservations` and `AccessibleUI.kiosk_reminder_*` require the actual provider's
visible banner surface, literal body, critical urgency and displayed countdown;
process readiness cannot satisfy those checks. Cancel closes the banner and
discards the unsaved editor/preferences draft, with owner and original draft
bound across observations. The guarded ordinary-user helper starts only the
idle Jordan fixture's user manager, runs the public `SetWindow` client to observe
real settings backup, suppression and restoration, checks the service's settings
environment, and stops only its recorded manager invocation. The exact finite
client also runs against the component suite's private bus and keyfile backend.
Live installed qualification remains pending; this preview/service engineering
route supplies no natural reminder or fullscreen-delivery qualification and
does not claim native compositor visibility from process state.

The planned request-report branches of FEED15–18 need shared API projections
for their actual surface and terminal result. `parent_reports.report_review`
and `onpc_feedback_privacy::review_privacy` are Parent-bound; reuse their
mechanics without replaying Parent entry/draft histories in every request
consumer. `AccessibleUI.feedback_snapshot` rejects failed collection, visible
Retry/Send without logs and busy controls; `wait_feedback_collection` waits
for ready diagnostics/Download. Add explicit failed, sending/retry and success
projections before describing those branches as callable. A persistent failed
result needs independent capture before recovery, not a pre-entry trace.

Task 188r owns Parent's missing failed-state projection and Retry composition
in one pending qualification. Reuse the same genuine failed observation before
restoration and Retry, with usable editing/Close and retained-draft readbacks;
do not add a separate failure-only qualifier. A public failure/recovery trigger
is still missing. This binding supplies no complete case-208 acceptance.

FEED17/18 additionally have a contract/source gap: the shared product
`FeedbackDialog._hide_draft` currently performs the documented direct Stop
action for a busy error report, with no warning/stay-open response. Preserve the
pending case assertions and resolve that declared branch against the product
contract before implementation; neither direct Stop nor a synthetic confirmation
qualifies staying open. This gap affects cases 218/219, without changing sending authorization or no-replay guards.

| ID | Kind | Block and explicit contract | Callees / first consumer | Status |
| --- | --- | --- | --- | --- |
| AUTH04 | A | Validate authority and protected-account restrictions for shared fixture account operations. No Users-settings password prompt. | Owned fixture/SSH boundary; product approval challenges remain AUTH01/02. | pending |
| ACCOUNT01 | A | Read the declared fixture account/role set through public system account interfaces over guarded SSH. | Shared account-fixture library with bounded nonsecret output. Preparation metadata only; app account lists supply customer assertions. | pending |
| ACCOUNT02 | C | Add/remove/change the role of a registered spare fixture account through shared system commands or AccountsService and read back the change. | Reuse `account_fixture` infrastructure; protect active/last administrator, baseline accounts and station, registered secrets and owned cleanup. Independently observe Parent/request-selector refresh. Implement finite spare registry, removal and role operations before reuse; today's fixed standard-child creation supplies neither a spare administrator nor a spare-only eligible-child profile. Cases 180/181 need safe independent disposable-child profiles before composition, not deletion of protected baseline children. No GNOME Users wizard. | pending |
| PANEL01 | C | Read the child's saved animation preference through `child-countdown-animation-toggle`; discover the owned panel surface independently. | `AccessibleUI.child_countdown_animation()` uses shared `child-panel` client `getValue`; use `child-countdown-menu.activate` only when ordinary menu entry itself is needed. E2E-022 cases 118/120 own persistence and isolation; E2E-008 case 22 owns locking with animation enabled. | ready for the enabled Ubuntu 26.04 child-desktop binding through `countdown_animation.PLAN` / `check_e2e_operate_the_countdown_context_menu` in `20261029T213121Z-d3a2ec77`; fresh readback and wrong-account refusal passed |
| PANEL02 | C | Set the canonical animation boolean through the panel API and independently read it before continuing child activity. Preserve session/account persistence assertions. | `AccessibleUI.child_countdown_animation(True)` shares UI17 on `child-countdown-animation-toggle`, independent PANEL01 readback and DESK01; `onpc_challenges::countdown_animation` supplies independent child entry, with no popup or Escape dependency. | ready for enabled Ubuntu 26.04 binding in the same qualification; host on/off owner retained. Collection, worker shutdown, owned cleanup and baseline restoration passed; persistence, isolation and complete cases remain separate |
| PANEL03 | C | Read the public countdown explanation through `child-request-tooltip.getText` in its local UI owner. | `child_shell_interaction._assert_countdown_explanation` uses the owner-pinned shared `child-panel` client to compare the literal explanation and HH:MM:SS with independent canonical remaining-time reads, allowing one display tick of lag. | ready local UI coverage through `test_child_shell_lifecycle.py`; focused isolated-Shell and indicator Node checks passed in task 181h. No installed time-accuracy or complete-scenario credit |
| INFO01 | C | Check declared Help/About external links are clickable, then stop. Never invoke them or inspect their URIs/destinations. Kiosk asserts unavailable external actions instead. | `AccessibleUI.clickable_link` reads owned visible/enabled control and sole action without activation. Shared Parent `check_parent_help/check_parent_information` and overlay `read_overlay_link` qualify Help/all five About links with owned Close/unchanged settings or request. Kiosk requires absent external actions. Case 190 is [UI-owned](UI-and-E2E-Coverage.md#duplicate-review-and-allocation) with no executable; case 191 owns overlay information/return. No external handler dependency. [About contracts](#about-block-contracts). | Parent and overlay Help/all five About links qualified; case 190 UI-only/excluded; case 191 overlay information/unchanged-form scope qualified on Ubuntu 26.04; other bindings pending |
| INFO02 | C | Read one installed product help command or command manual from bounded, guarded SSH stdout as the parent fixture account. | `onpc_documentation::read(journey, binding)` invokes `command_documentation.observe`; the stdout adapter checks fixed command identity, help usage/options or manual sections/purpose without Terminal rendering. Case 193 composes all four bindings and one final independent desktop result. | ready stdout bindings; consolidated case return awaits live verification |
| FEED15 | C | Review or decline a displayed product error report. Request result entry explicitly sets Report this error then closes the result; Parent entry observes its automatically opened report without inventing a report button. Read the report or declared exit destination. | Request: UI17(report choice) → UI04(result Close) → UI01 → FEED03 for review; Parent: `parent_reports.report_review` / `onpc_feedback_privacy::review_parent_report` → FEED03/UI16 → FEED05 → guarded UI18 → independent destination/rule read. Direct closure: `parent_reports.report_close` / `onpc_feedback_privacy::close_parent_report` → automatic-draft read → guarded UI18 → independent destination/rule read. See [automatic Parent error reports](#automatic-parent-error-reports). Parent has no report-choice toggle. E2E-045. | ready for the declared Parent review and edited/untouched report-close bindings; request surfaces and other bindings pending |
| FEED16 | C | Retry an observed failed diagnostic collection and read its result and retained draft. | UI04(Retry collection) → FEED09 → FEED03 → UI12. Task 188r qualifies Parent failure/recovery together; E2E-046 case 208 keeps separate complete acceptance. Overlay/station retry bindings are no longer scheduled. Station without-logs submission reuses FEED11 in case 213; it is not hidden inside retry. | pending |
| FEED17 | C | Attempt normal Close on a sending error report and read the stop-sending confirmation. Do not yet stop or exit. | UI04(Close) → UI01(confirmation) → UI03. E2E-047. | pending |
| FEED18 | C | Choose the explicit Stop sending and close or stay-open response, then read the destination. | UI04(response) → UI11(confirmation) → UI01(destination); report closure uses UI11(report) separately. E2E-047. | pending |
| TIME05 | A | Read actual local date/time, UTC offset and timezone through bounded `date`/`timedatectl` output over guarded SSH. Do not change them. | Shared clock observation with explicit precision/monotonic bracketing. No Shell calendar or Settings page. Natural calendar windows and product countdown assertions remain required. | pending |

### Reusable journey fragments

These fragments do not own fixture provisioning, attempt startup or cleanup.
Arguments include expected results and the exact accounts/apps/choices. No
fragment skips an unsuccessful step or resumes a previous attempt.

`request_flow.prepared_request`, `overlay_approved_request`,
`kiosk_approved_flow.approved_request` / `obtain_time` and
`onpc_request_flow::prepare` / `approve` bind Riley/Jamie and soft apps included.
The shared kiosk leaves accept caller-owned finite 75/120/180/240/600/1200-second
durations. The 75/600-second leaves retain their existing scope; the distinct
[120-second FLOW13 profile](#grant-only-time-profile-qualification) is qualified
on Ubuntu 26.04. Later cases bind their other finite durations and own their
elapsed-time, arithmetic, app-effect and lifecycle results without replaying
this qualifier. FLOW20's other identities and soft-choice inputs remain planned
extensions, not ready merely because the block exists.
Qualify changed parameter/result branches with representative independent
entries and focused safety coverage rather than repeating unchanged approval,
rejection, Cancel and exit histories in each consumer.

FLOW20 must carry explicit Riley/Jordan identity, eligible Jamie/Sam approver,
bounded duration and soft-choice arguments through prompt, automatic result,
activity and countdown observations. Later recipes own their exact finite
values; representative independent qualifications do not require a Cartesian
choice matrix. FLOW11 names case-level recovery composition, with no standalone
worker or qualification history. Cases compose TIME04, retained FLOW20 and
their own earlier activity comparisons; missing finite approval and retained
entry bindings remain prerequisites, not assumed qualification.

FLOW17 has no shared callable or fixed qualification selector yet. Extend the
declared request prompt, session command/API and request-surface operations for
each selected interruption. Lock/switch reuse successful retained-child entry;
sign-out uses fresh entry; app-close uses its own normal modal/busy-gated route,
not Parent LIFE01. A cancelled/denied request consumes no successful-request
cooldown, so interruption qualification needs no artificial TIME03 delay.
Qualify only the missing pending-prompt interruption, cancellation and safe
request-surface return. Compare balances with ordinary elapsed usage allowed;
cancellation must add neither time nor relaxed app access. Cases 171–175 keep
the subsequent fresh authenticated approval, independent balances/access and
usable destination; the qualifier
does not repeat that complete recovery history. System 255's disconnect checks
do not supply these graphical customer results.

FLOW19's AppSet preparation uses `policy_edits.policy_edit(..., setup=True)`
and one independent complete saved-set comparison after the last save. This
existing branch omits unchanged intermediate row/editor reads while retaining
input ownership and save guards. Compare again after a declared persistence
boundary. Tested policy transitions keep their own before/after access and
running-app results; a setup read supplies neither those results nor qualification
of additional named app arguments.

| ID | Kind | Block and explicit contract | Callees, in order | Status |
| --- | --- | --- | --- | --- |
| FLOW00 | C | Run case 1's complete graphical/serial qualification within the unchanged harness envelope. Its step boundaries and terminal assertions are fixed below. | `controller_qualification.PLAN` and `Smoke._step` bind the graphical stages to `gdm_product_free_account()` / `gdm_product_free_navigation()` observations; `onpc_flow00::run` consumes the exact product-free prompt proof before Escape. The existing authenticated serial command, session/boot identity, single logout, return reconciliation, capture assertions, collection and owned cleanup passed in an earlier retained case 1 run. | ready; retained case 1 implementation |
| FLOW15 | C | Reach an explicit user's desktop from the declared source surface. `entry=fresh` requires no retained session; `retained` requires an earlier observed desktop; `same` requires the current user already matches; `lock` requires the declared locked child session. Return the observed desktop or expected time-limit denial. | `journey_blocks.desktop_entry` / `onpc_desktop_session::enter_desktop` compose fresh GDM, retained GDM/from-another-desktop, same-user and native lock branches, guarded by `session_control.entry_identity`. [Both-child qualification](#both-retained-child-desktops-and-explicit-entry-modes) covers Riley/Jordan fresh, same and reciprocal retained success, Riley lock/unlock and both zero-time denial routes. Existing [fresh-child success](#fresh-child-success-qualification), [fresh denial](#fresh-child-time-denial-and-return-qualification), [retained success](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) and [retained denial](#retained-child-time-restriction-and-greeter-return-qualification) remain qualified. | stated Parent and both-child fresh/same/retained bindings and Riley lock/denial ready; other bindings pending |
| FLOW01 | C | Open or return to Parent for a named child and record displayed settings. Inputs declare source, parent entry and `window=new` or `retained`. Default first entry is GDM/fresh/new; a return uses retained entry and the existing window. New launches always use PARENT01's direct command. | `onpc_parent::open_for_child(journey, source, entry, window, child, invocation)` composes fresh FLOW15 → PARENT01(management) → PARENT02, or `desktop/same-user/new` with independent window-absence and Parent-desktop observations before the direct launch and child selection. Retained/same-user branches consume `retained_parent_entry` with explicit invocation and preserved child/page/settings; [exact retained qualification](#retained-parent-desktop-and-window-entry) and [Riley-to-Parent return in the two-child history](#both-retained-child-desktops-and-explicit-entry-modes). `check_e2e_set_an_allowance_for_a_named_child` qualified fresh and independently reopened same-user Parent/child entries, persisted settings and wrong-window refusal, including collection, owned cleanup and baseline restoration. Case 6's affected launch regression passed. Fresh Parent/Riley also passed in case 151; second-parent and other bindings remain pending. | fresh and same-user/new bindings ready; Jamie/Riley retained entry from either child ready; other bindings pending |
| FLOW02 | C | Configure the selected child's time controls, observing save and explanation. Inputs declare initial/final enablement and allowance. Enable first only when needed to make the allowance editor usable. | `AccessibleUI.configure_time_controls(child, initial_enabled=…, minutes=…, final_enabled=…)`: PARENT04(Screen Limits) → conditional UI17(true)/PARENT08 → PARENT05 preset commit or PARENT06 custom save/PARENT08 → UI17(final boolean)/PARENT08 → PARENT03 → PARENT09. Qualified inputs are 0/15-minute presets and explicit boolean enablement, plus disabled→enabled with 30 minutes through FLOW16's fresh binding and short custom 2/4-minute bindings through [FLOW13's qualification](#daily-only-time-profile-qualification). Other custom bindings remain pending. `check_e2e_time_explanation` qualified enabled→disabled, disabled→enabled and enabled→enabled paths, saved settings, positive/zero balances and wrong-child/initial-state refusal, with collection and owned cleanup. Disabling intentionally clears a grant; it is never navigation. | ready for qualified bindings |
| FLOW03 | C | Configure one app's matching and access choices through Parent and read the saved row. | `policy_edits.policy_edit` / `onpc_app_rows::edit_policy`: PARENT10 → PARENT11 if declared → PARENT13 → UI16(match draft) → PARENT15(save) → PARENT16 → PARENT12. Caller owns entry, finite inputs and exact comparisons; see [public app-policy edits](#public-app-policy-edits). | ready for Jordan/native fixture A's precise and `*.AppImage` match/access slice; other bindings pending |
| FLOW04 | C | Open the selected request surface, or use an explicitly already-open form, then choose child/approver/duration/app access and read the estimate. | REQUEST01 or REQUEST02 only for `entry=new`; `entry=open` starts with REQUEST03 → REQUEST04(child only in kiosk, approver, duration) → REQUEST05 if custom → REQUEST06 → REQUEST08. `request_flow.prepared_request` / `onpc_request_flow::prepare` qualify the explicit kiosk child/parent, custom 1.25-minute, soft-included binding for independently open and new entry; see [prepared request qualification](#prepared-request-qualification). `prepared_request(surface='overlay')` / `prepare(..., 'overlay')` reuse the shared overlay entry/form leaves for the fixed child, Jamie approver, 75 seconds and included soft apps: open/default and new/remembered branches passed [overlay FLOW04 qualification](#overlay-flow04-invalid-submission-and-escape-qualification). | pending; declared kiosk and overlay open/new bindings ready; other choices pending |
| FLOW05 | C | Complete a real approval from a prepared form, observe confirmation and its declared automatic or immediate exit. | REQUEST09 → AUTH02(correct credential) → REQUEST11(success) → REQUEST12(automatic or immediate). `kiosk_approved_flow.approved_request` / `onpc_request_flow::approve`; see [approved kiosk flow qualification](#approved-kiosk-flow-qualification). `request_flow.overlay_approved_request` / `onpc_request_flow::overlay_approve`; see [overlay composition qualification](#overlay-immediate-exit-and-approval-compositions). | fixed kiosk and overlay 75-second/soft-included automatic and immediate bindings ready; other choices pending |
| FLOW06 | C | Obtain time through kiosk from an existing GDM screen and return to GDM. | FLOW04(kiosk) → FLOW05. `kiosk_approved_flow.obtain_time` / `onpc_request_flow::obtain_time`; see [approved kiosk flow qualification](#approved-kiosk-flow-qualification). Child login/unlock is deliberately a later step. | fixed kiosk remembered-choice binding ready; other choices pending |
| FLOW07 | C | Reject/cancel one request and compare its preserved choices. Return with that form open; do not retry yet. | REQUEST03(before) → REQUEST09 → AUTH02(wrong/cancel) → REQUEST11 → UI12. `approval_flow.rejected_request` / `onpc_request_flow::reject`; see [rejected kiosk flow qualification](#rejected-kiosk-flow-qualification). `request_flow.overlay_rejected_request` / `onpc_request_flow::overlay_reject`; see [overlay composition qualification](#overlay-immediate-exit-and-approval-compositions). The recipe can inspect restrictions before invoking FLOW05 for a successful retry, avoiding a second implementation of approval. | fixed kiosk and overlay 75-second/soft-included rejection and Cancel bindings ready; other choices pending |
| FLOW08 | C | Exercise an app through its declared route and prove the expected usable/denied result. | `journey_blocks.native_usable_app(route, child=...)` / `onpc_app_rows::native_usable_app(journey, route, desktop, child)` compose APP01 → APP02 → APP03 for the declared native `command` or `grid` usable route; [qualification](#native-fixture-preparation). Grid binds Jordan to `other-child` and Riley to `child` explicitly. `native_usable_app('command', child='child')` adds Riley's usable-time command binding through the [valid overlay slice](#valid-overlay-choice-and-cancel-qualification); `child='parent'` explicitly binds Jamie through [distinct-user retention](#distinct-user-retained-app-qualification). No alternative launch after failure. APP03 runs only for expected usable access. | Jordan/Riley native Allowed grid and stated Jamie/child command usable scope ready; policy denial and other bindings pending |
| FLOW09 | C | Visit an explicitly retained user and prove the same app/activity remains usable. Inputs include source surface and that user's earlier activity observation. | `journey_blocks.retained_app_visit` / `onpc_app_rows::retained_app_visit`: FLOW15(entry=retained) → APP04(compare) → APP03. Caller binds first entry to the prior capture through `JourneyPlan.activity_entries`, then immutable `activity_checks` before original-window Submit. No launch, replacement desktop or qualifier replay. [Distinct-user qualification](#distinct-user-retained-app-qualification). | stated Jamie/Parent and Riley retained app visits ready; other bindings pending |
| FLOW10 | C | Launch the prepared real game with its declared mode/level and play to natural lock. | FLOW08(game, usable, registered launch options) → APP05 → APP04(record activity) → TIME04. | pending |
| FLOW11 | C | After a displayed lock, obtain legitimate replacement time, unlock and observe the expected retained app or closed blocked app. | Case-level DESK11 → FLOW20(kiosk, retained) → APP02 → APP04(compare) → APP03 when preservation is expected. Closed-app branch ends at APP02. Reuse the case's original captures; no standalone qualifier. Tasks 197k and the app/game owners retain missing bindings. | pending complete customer histories; no separate qualification task |
| FLOW12 | C | From an open request form, visit the other surface for that child and compare duration/custom/soft-app choices before editing. Compare the independently remembered parent for each requesting OS user, not parent equality across surfaces. Interactive mute is separate deferred scope. Finish with the second form open. | Overlay→kiosk: `request_flow.overlay_to_kiosk` / `onpc_request_flow::overlay_to_kiosk` compose REQUEST12(cancel) → DESK03 → REQUEST01 → REQUEST03. `KioskRequestJourney` compares immutable endpoints declared in `request_transfer_checks`; `choices_overlay_to_kiosk.PLAN` binds both children and same-kiosk persistence/isolation readbacks. The [both-child qualification](#overlay-choices-transferred-to-kiosk) passed the shortened scope on Ubuntu 26.04 and Fedora 44; its historical independent retained entry is no longer a prerequisite. Kiosk→overlay: `request_flow.kiosk_to_overlay` / `onpc_request_flow::kiosk_to_overlay` compose REQUEST12(cancel) → FLOW15(child, declared fresh/retained entry) → REQUEST02 → REQUEST03 → UI12(shared values and user-local selectors); `cross_surface.PLAN` binds both children through fresh entry. See [reverse qualification](#kiosk-choices-transferred-to-overlays). Interactive mute remains deferred outside this current-choice composite. | both directions ready for both children; overlay-to-kiosk same-kiosk persistence/isolation ready; kiosk-to-overlay fresh entry and complete cases 60–61 passed; retained reverse entry pending |
| FLOW13 | C | Establish a named time profile entirely through customer controls and finish at GDM. Entry/window arguments are explicit. Verify no grant or revoke it first; use the profile table below. | `journey_blocks.daily_time_profile` / `DailyTimeProfileJourney` / `onpc_parent::daily_time_profile` compose FLOW01 → PARENT09 → UI12(G=0 on that initial observation, no unchanged reread) → FLOW02(short custom allowance) → independent saved settings and UI12(D>0/G=0) → DESK03. [Qualified daily-only bindings and selector](#daily-only-time-profile-qualification). `journey_blocks.grant_only_time_profile` / `GrantOnlyProfileJourney` / `onpc_parent::grant_only_time_profile` add explicit optional PARENT17 → PARENT18(confirm) → fresh PARENT09(G=0), FLOW02(declared daily allowance), FLOW06 and retained Parent result before DESK03. [Qualified grant-only bindings and selector](#grant-only-time-profile-qualification); [combined binding and selector](#combined-time-profile-qualification). Daily-dominant remains separate and adds PARENT06(larger allowance, still enabled) → PARENT08. | daily-only fresh 2-minute/same-user 4-minute bindings ready; grant-only fresh and retained/revoke-first 2-minute bindings and combined fresh 4-minute daily/2-minute addition ready on Ubuntu 26.04; other profiles/bindings pending |
| FLOW14 | C | Open apps/recognizable activities for a finite declared user list, retaining each desktop through Switch User. Inputs state each user's fresh/retained entry and usable-time/policy prerequisites. Start and finish at GDM. | `journey_blocks.retained_app_activities` / `onpc_app_rows::retained_app_activities`: for each distinct user, FLOW15 → FLOW08(command) → APP04(capture) → desktop identity → DESK03. Earlier retained desktops must be revisited, not recreated. Parent native operations bind Jamie's active session explicitly. Duplicate users refuse; same-child multiple desktops retain a separate same-child customer-route gate. [Distinct-user qualification](#distinct-user-retained-app-qualification). | stated Jamie/Parent retained and Riley fresh preparation ready; other bindings pending |
| FLOW16 | C | As the named parent, reach Parent for the named child and set a daily allowance and final limit state. This is the reusable “Set Jordan's daily allowance to zero” recipe; zero is an allowance, not an approval. | `onpc_parent::set_allowance` composes FLOW01→FLOW02. Qualified `gdm/parent/fresh/new/child/0/0/1`, `desktop/parent/same-user/new/child/1/15/1` and `gdm/parent/fresh/new/child/0/30/1` bind explicit saved settings and independent zero/positive/1800-0-1800 balances through `set_allowance.PLAN/fresh_thirty_allowance.PLAN`. Wrong child/state/window refuses before reply. Finish in Parent without implicit logout. Other allowances/parents/retained windows need qualification; local case 161 has no E2E executable. | pending; fresh-zero, fresh-thirty and same-user-positive bindings ready |
| FLOW17 | C | Leave a request with authentication pending by one declared supported action, observe its destination, then return and read cancellation before a new request. | Lock: shared DESK05 shortcut/command → DESK06 → DESK08; switch: DESK03 → FLOW15(return retained); sign-out: DESK04 → FLOW15(fresh); close: UI18(API surface close) → UI11(app), followed by REQUEST01/02 as declared. REQUEST03 → UI11(old prompt). E2E-039; system commands work independently of modal menu access. An unavailable tested app-close control remains gated. | pending |
| FLOW18 | C | Prepare positive daily time that outlasts a soft-app grant without resetting its launch exception. Finish on the child desktop with both balances positive and daily dominant. | FLOW13(combined, soft included) → FLOW15(child) → FLOW08(soft app) → APP04 → DESK03 → FLOW01(parent retained) → PARENT09 → TIME03(wait until the declared remaining-grant window while child is away) → PARENT09 → UI12(D>G>0) → DESK03 → FLOW15(child retained) → TIME01. No allowance edit or app save after approval. E2E-038. | pending |
| FLOW19 | C | Configure a finite named app-rule set for one child and return to sign-in. Each match/access edit and save is explicit; no time approval or account preparation is hidden. | FLOW01(parent, explicit source/entry/window/child) → PARENT04(App Limits) → FLOW03 for each declared app/rule → DESK03. First consumers E2E-006/007; reused as AppSet in the recipes. | pending |
| FLOW20 | C | Approve a specified interval on either request surface and continue as the named child. Accept explicit new/open form entry, child/parent, duration, soft choice, child fresh/retained entry and expected countdown. New overlay entry requires that child's unlocked desktop; new kiosk entry requires GDM. It does not create those preconditions or alter daily policy. | FLOW04(entry and all choices) → FLOW05 → FLOW15(child,declared entry) only for kiosk → TIME01 → UI12(expected interval). Overlay returns to its existing desktop. Reuse FLOW04/05/15 without another surface-specific approval implementation. E2E-048 immediate repeat and E2E-049/050/051. | pending |

FLOW16 separately qualifies Jordan's
`gdm/parent/fresh/new/existing/0/30/1` through
`fresh_thirty_allowance.JORDAN_PLAN`, `FreshThirtyAllowanceJourney`,
`JordanThirtyAllowanceQualification`,
`onpc_fresh_thirty_allowance::run(...,'existing')` and
`check_e2e_set_jordan_thirty_minute_allowance`.
Carry explicit child through FLOW01/`child_bindings`/FLOW02 and independent
PARENT20/UiObservations reads; Riley receipts refuse.
Require disabled/zero initial settings, saved enabled30 minutes, independent
1800/0/1800 balances and wrong-child/state/window refusal.
This is named fresh Parent/Jordan setup only; other bindings/complete cases remain
separate.

#### Daily-only time profile qualification

`time_profiles_daily.PLAN/SAME_PLAN`, `onpc_set_allowance::qualify_daily`
and `check_e2e_time_profiles_daily` qualify Riley's FLOW13 on Ubuntu
26.04/Fedora 44, disabled/zero initial settings, new Parent window and no grant.
Exact fresh binding `gdm/parent/fresh/new/child/0/2` and independently reopened
same-user `desktop/parent/same-user/new/child/0/4` require initial G=0;
unexpected grants refuse without revocation. Public custom Save must produce
positive daily time, G=0, total 120/240 seconds and saved enabled 2/4-minute
settings. A newly observed Parent desktop precedes Switch User/usable GDM.
Other daily-only initial/account/window/minute bindings and complete scenarios
remain separate. Grant-only qualification is scoped below.

#### Grant-only time profile qualification

`grant_only_profile.PLAN/REVOKE_PLAN`, `onpc_set_allowance::qualify_grant`
and `check_e2e_grant_only_profile` qualify Riley/Jamie on Ubuntu 26.04 through
two independently restored attempts. Fresh `gdm/fresh/new` entry reuses the
initial public G=0 read. Retained `desktop/same-user/retained` entry obtains a
real existing grant through the unchanged 75-second approval leaves, verifies
G>0 and the undeclared-grant refusal, explicitly confirms Revoke, then reads
G=0 afresh before editing policy. Neither branch silently clears a grant.

Both save enabled zero daily minutes, approve a real 120-second soft-included
kiosk request, independently return to the same Parent window and require
saved D=0/G>0/total=G within elapsed-time and display-precision bounds. Both
finish at usable GDM. Worker/callback shutdown, collection, owned baseline
restoration and finalization passed. The shared request leaves accept finite
120/180/240/600/1200-second caller arguments; later recipes retain their own
duration, arithmetic, deadline, recovery and child-effect assertions. This
qualification supplies no complete-scenario credit or other-family result.

The shared declaration/worker accepts `balance_readback=False` / final argument
`0` to finish at GDM directly after approval. The caller must independently read
saved zero daily time before approval, then the public estimate, success and
positive child countdown. Case 25 passed this route with a four-minute request
on Ubuntu 26.04 in `20261030T054552Z-161dd5f4`, including initial countdown,
foreground activity before expiry, four real one-minute intervals, retained-child
denial and continued use of the original Parent activity. Collection, owned
cleanup, baseline restoration and recording finalization passed. Other callers
retain Parent readback by default. The original grant deadline is never reset
by a later observation. Other bindings remain outside this acceptance.

Case 28 uses the same direct GDM finish, then independently calls the shared
`revoke-balances` Application UI reader on the retained Parent window before
fresh child entry. This keeps the public D=0/G>0/total=G result without spending
the two-minute wall-clock grant on another Parent login. The unchanged reader
retains owner/child bindings and fresh status reload. Its complete customer
history is recorded under [natural enforced lock](#natural-enforced-lock-qualification).

Case 26 passed the same four-minute preparation on Ubuntu 26.04 in
`20261030T063013Z-c491dbd2`, with the other child's limits-off activity captured
before approval. Its exact scoped kiosk credential binding retains the two fresh
recipient proofs and single-use input. The other child resumed the original
window/draft before expiry and across four measured one-minute intervals;
retained-child time denial and final use of that same activity passed, with
collection, owned cleanup, baseline restoration and recording finalization.

#### Combined time profile qualification

`grant_only_profile.COMBINED_PLAN`, `GrantOnlyProfileJourney(daily_minutes=4)`,
`CombinedTimeProfileQualification` and `check_e2e_time_profiles_grant` qualify
fresh `gdm/fresh/new` Riley/Jamie preparation on Ubuntu 26.04. The shared
declaration and `onpc_parent::grant_only_time_profile` accept `daily_minutes=4`
(the worker's final argument); their default remains zero.

The journey observes G=0 before edits, saves an enabled four-minute daily
allowance, retains actual observed D, and approves two additional minutes through
the real kiosk prompt. Fresh recipient proofs and single-use password input bind
this exact scoped 120-second request. Retained Parent readback requires G>D>0
by more than display precision, total=max(D,G), unchanged daily time within
rounding tolerance, and G bounded by the earlier D+120, measured elapsed time,
both display precisions and two seconds of tolerance. No clock change or grant
clearing occurs after approval.

Passed in `20261030T095545Z-d1f77e61`: D=240 seconds, G=314 seconds and
total=314 seconds, followed by usable GDM. Collection, worker/callback shutdown,
owned cleanup, baseline restoration and finalization passed. The exact credential
binding was added after its initial refusal; 208 affected host checks plus source
and traceability passed. Unchanged grant-only/revoke-first entry and refusal
coverage remains qualified above. This slice supplies no complete-case credit.
Complete case 29 uses this preparation as recorded under
[natural enforced lock](#natural-enforced-lock-qualification); other families
remain pending.

#### Distinct-user retained app qualification

`retained_app_visits.PLAN` / `RetainedAppVisitsJourney`,
`journey_blocks.retained_app_activities/retained_app_visit` and matching
`onpc_app_rows` workers qualify Jamie/Parent retained and Riley fresh entry
through `check_e2e_retained_app_visits` on Ubuntu 26.04/Fedora 44.
Riley has public 900-second daily time/no grant. Each user launches the
native-primary command once, submits/captures its immutable draft/window,
records desktop and Switches User; preparation starts/ends at GDM.

FLOW09 visits Jamie from GDM, Riley from Jamie and independently Jamie from
Riley. `activity_entries` requires earlier capture before input;
`activity_checks` compares original window/draft before resumed Submit and
after its effect. Missing/changed captures or wrong entry modes refuse without
relaunch/replacement desktop. Parent native operations explicitly bind Jamie.
Read-only native launch preflight retries incomplete observations within its
deadline while rechecking session/prompts/original-window absence; complete
refusal or uncertainty is terminal. Other users/apps, same-child multiple
desktops and complete scenarios remain separate.

#### Approved kiosk flow qualification

FLOW05 `request_flow.approved_request` / worker `approve` takes explicit
child/approver/duration/soft choice and automatic/immediate exit.
Fixed scope is fixture-child/fixture-parent, 75 seconds (`1.25` Minutes),
soft included. Caller supplies prepared form; REQUEST09 verifies choices before
input. FLOW06 `obtain_time` composes new/selected FLOW04 then FLOW05 from GDM
and enabled policy, without changing policy or logging in the child.
`kiosk_approved_flow.PLAN` / `KioskApprovedFlowJourney`,
worker `approved-flow` and `check_e2e_kiosk_approved_flow` qualify independent
open/Cancel then fresh reproduced request/genuine approval/success/automatic GDM.
Reuse [MATE qualification](#kiosk-approval-qualification) and single-use proofs.
The original `kiosk-approval` namespace supports one invocation per fresh
attempt; repeated requests need separately declared distinct challenges.

Case 49/`kiosk_approved.PLAN` /
`onpc_kiosk_cancel::run(..., 'approved',...)` adds immediate exit, fresh child
entry and countdown after public daily900/grant0 setup.
`KioskRequestJourney.countdown_checks` /
`countdown.check_countdown_balance` compare immutable estimate/countdown:
975 seconds, one-second precision, minute flooring, the shared
[sampling tolerance](#child-desktop-countdown-qualification) and at most 180
seconds from public estimate.
No private grant/time probe supplies acceptance; FLOW06 remains automatic-only.

Case 50/`restricted_station.PLAN` /`onpc_restricted_station::run` composes
fresh-zero FLOW16, station entry, `onpc_station::restrictions`, prepared request
and automatic approval. `kiosk_restrictions` requires complete owned form/tree,
no showing outside-app content and request-only control IDs.
The ID-owned menu's sole anonymous direct GTK toggle is an implementation child,
never input target or blanket exemption; other anonymous/named unknown controls
refuse. Before each Super/Super-A/Ctrl-Alt-T, require fresh owned form/available
Cancel, then independently observe two-second forbidden-surface absence and
REQUEST03 without altering/focusing the form or typing a query.
Approval replaces the form; no post-approval form check applies.
See [candidate-specific scope](../SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits);
About/report restrictions remain their own cases.

#### Rejected kiosk flow qualification

`approval_flow.REJECTION_PLAN/CANCEL_PLAN` / `ApprovalFlowJourney`,
worker `flow-rejection/flow-cancel` and `check_e2e_approval_flow` qualify
separate fixed fixture-child/fixture-parent/75-second/soft-included attempts
on Ubuntu 26.04/MATE `1.26.1-6`, English/US.
FLOW07 `rejected_request` / worker `reject` accepts only rejection or Cancel.
Read explicit wrong-password denial or password-free cancellation, then compare
immutable unchanged usable no-error form. End at `flow-preserved` without
retry/exit so caller can inspect before separate FLOW05.

Cases 51/52/`restricted_station.DENIED_PLAN/CANCELLED_PLAN` repeat the
restriction cycle before preparation and after rejection/Cancel, then Cancel
to independently usable GDM. Declare default disabled vs
`kiosk-restriction-prepared-ready/read` explicitly; prepared reads require
the exact fixed child/approver/custom/soft/estimate rather than deriving
expectations from current values. Both retain full-tree exclusions, fresh owner
and two-second absence checks. Password-free cancellation enters no credential.
[Candidate-specific scope](../SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits)
is distinct from general confinement proof.

A later FLOW05 uses fresh form read, distinct challenge and two new proofs
before one correct submission/success/automatic GDM.
`UiObservations` permits that transition only after completed rejection and
fresh read; reused/replaced challenges, failed reads, uncertainty and replay
refuse. `kiosk-approval-flow` uses separate single-use rejection/approval
secret bindings. Other/repeated requests and complete scenarios remain separate.

#### Prepared request qualification

`request_flow.daily_station_entry` /
`onpc_request_flow::daily_station_entry` share public selected-child enablement,
15-minute Save/balance, Switch User and station entry. Request selection,
authentication and exit remain separate; callers own phases/results.

FLOW04 `prepared_request(prefix,entry,initial,child,approver,duration_seconds,allow_soft)`
/ `onpc_request_flow::prepare` binds fixture-child/fixture-parent,
75 seconds/exact custom `1.25`, soft included.
`entry=open` uses existing form; `entry=new` enters station.
`initial=default` reads fresh defaults; `selected` reads remembered
child/approver/custom/soft choices. Prefixes keep captures distinct.
Caller supplies enabled policy/independent public balance; flow never changes
policy or submits Request. `request_flow.PLAN` / `RequestFlowJourney` /
`check_e2e_request_flow` qualify open/Cancel/new, reproduced choices,
16m15s estimates with elapsed/precision bounds and both GDM returns.
[Both-target renewal](#c04s-existing-request-choice-renewal) retains this exact scope.

`select_kiosk_account` accepts explicit expected duration/custom values;
child/approver operations retain exact offered-account sets/owner/no-prompt
guards. `kiosk-valid-fraction-soft-select/read` use
`RequestObservation.from_request`. Other values/overlay require their own scope.

Case 47/`kiosk_cancel.PLAN` /`onpc_kiosk_cancel::run` uses enabled-choice
Cancel; case 48/`kiosk_escape.PLAN` /`onpc_kiosk_escape::run` uses legacy
Escape-labelled `onpc_request_exit::escape` as an owned API surface close.
Both independently require absent form/usable GDM and preserve estimate/choice
checks. Historical native Escape evidence does not automatically qualify a
changed API-close composition. Approved/overlay exits remain separate.

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

Checked-state delivery and feedback trace diagnostics keep their own event
subscriptions. Intermediate PARENT08 inhibition/recovery samples are not current
acceptance requirements; changed routes retain their scoped qualification.

A row becomes `ready` only when its implemented projection/selector scope is
explicit and its source callable and required installed slice qualification are
recorded under the [status contract](README.md#status-vocabulary). A later
complete scenario is not a prerequisite of its own block. Ready primitives above
refer to existing
[public-UI regressions](../../tests/unit/test_accessible_e2e_ui.py),
[local product checks](../../tests/ui/test_e2e_accessible_adapter.py),
[actual pointer](../../tests/unit/test_e2e_pointer_helper.py), with existing
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
| FIX06 | A | Independently verify one declared reusable fixture profile after baseline restore. Read-only files, launchers and ownership checks; no installation, repair, app launch or product-state setup. | Native: `NativeFixtures.verify` / `fixture_actions` in [native_fixtures.py](../../tests/e2e/native_fixtures.py), with guarded reads in [native_fixtures_guest.py](../../tests/e2e/native_fixtures_guest.py); see [native preparation](#native-fixture-preparation). Native Jordan-bound verification/catalogue qualified by `check_e2e_native_fixtures`, with affected regression. Chinese: `fixture_actions(profile='chinese')` and `chinese_language_assets.verify`; [language preparation](#chinese-language-preparation-and-desktop-language-setup). `check_e2e_chinese_language_assets` qualified wrong-entry refusal, independent valid readback and unchanged state on Ubuntu 26.04. New profiles require their own verification before consumers and do not broaden FIX04. FIX05 retains the separate real Lunar profile. | native file/catalogue and Chinese asset verification ready; other profiles planned |
| FIX03 | A | Prepare only a declared multiple/no-child/no-approver/locked-approver profile; do not generalize FIX02 into arbitrary mutation. | `EmptyAccountFixture.prepare` / `e2e_dynamic_account.prepare_empty` changes canonical child roles while preserving identities, administrators and station. `kiosk_no_child.PLAN` / `onpc_kiosk_no_child::run` and `check_e2e_kiosk_no_child` require exact empty children, explanation, disabled Request/duration/soft/approver controls and absent prompt. `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run` adds normal Cancel/GDM return. Other finite profiles are specified below; outer restoration owns undo. | ready; multiple/no-child/no-approver/locked-approver profiles |
| FIX01 | A | Create one eligible account at the declared durable checkpoint while Parent stays open. Customer acceptance requires later visible discovery/selection. | `DynamicAccountFixture.create` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX02 | A | Make the exact two canonical eligible child fixtures ineligible at the declared checkpoint before Parent launches; preserve the request station. Unexpected account sets refuse. | `EmptyAccountFixture.prepare` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX05 | A | Validate the one declared, manually prepared Lunar/AppImageLauncher/Minecraft profile after the normal installed-snapshot restore and before the attempt. Read-only setup verification, not installation, policy configuration or customer acceptance. | No callable yet. The real Lunar profile qualification binds versions/digests, original AppImage and launcher/autostart routes, local world, credential references and ordinary restore/provisioning ownership. Refuse missing/drifted assets; never synthesize a denial. [Profile contract](#lunar-client-preparation-and-observation-gate). | pending |

### Verified upgrade asset transfer

`check_e2e_upgrade_assets` qualified FIX04's genuine v1.2/current package binding
on every enabled VM (Ubuntu 26.04, amd64).
`stage_upgrade_assets` in [system_runner.py](../../tests/integration/system_runner.py)
and `VerifiedInputs(upgrade=True)` in [provenance.py](../../tests/e2e/provenance.py)
bind separate source/manifests and exact bytes before the powered-off transfer.
The maintained builder pins the published annotated, unsigned v1.2 tag and source commit; current must
be newer, with a distinct package digest and matching product/architecture.
The qualified inputs were `1.2+ppa1~ubuntu26.04.1` and
`1.3+ppa1~ubuntu26.04.1`. Missing inputs use maintained automatic preparation;
valid inputs are preserved, never fabricated by rewriting version metadata.

`AssetTransfer.provision` / `observe` and the finite
[qualification](../../tests/e2e/upgrade_assets_qualification.py) retain repeated
booted-guest identity/digest readback, product-free administrator entry,
wrong-attempt/powered-on/collision/replay refusal and account/locale/session/
unrelated-file preservation. The offline witness preserves
Ubuntu's exact `/etc/default/locale` → `../locale.conf` link identity and separately
hashes its canonical regular file; other links, dangling or unsafe targets still
refuse. Asset link/owner/immutability and consumed-failure guards remain required.
[Upgrade safety](../../tests/unit/test_upgrade_assets_cleanup_safety.py) covers
these boundaries through the real transfer, decoder and recorder.

### Chinese language preparation and desktop-language setup

The [Chinese lifecycle recipe](E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle)
uses one current-package installation and one reboot. Reusable language assets
belong to baseline preparation through `tools/prepare-vm`, never case-local
package installation, locale-file edits or translation downloads. Preparation
must be idempotent, preserve unrelated assets and support owned retry under the
[baseline lifetime contract](../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
It changes neither product installation nor child/station language.

[chinese_language_assets.py](../../tests/integration/chinese_language_assets.py)
verifies `zh_CN.UTF-8`, native MATE/PAM Chinese catalogues, package bytes and
Noto CJK glyph coverage. Ubuntu also needs `language-pack-gnome-zh-hans-base`
and `language-pack-gnome-zh-hans`: general language packs alone lack the Shell
`Activities` translation. Offline bootstrap and restored online snapshots use
the same read-only oracle. The qualified Ubuntu asset tuple includes MATE
`1.26.1-6`, PAM `1.7.0-5ubuntu3.2`, six required strings and 12 CJK glyphs.

The Fedora 44 profile uses `glibc-langpack-zh`, `mate-polkit`, `pam`,
`gnome-shell` and `google-noto-sans-cjk-fonts`, with RPM SHA-256 byte identity,
canonical Workstation/release checks and enforcing SELinux. Fedora assets,
renewed Chinese desktop, first presentation and native prompts remain unqualified;
the complete current-install journey must pass there with the same assertions.
Host preparation or translated product messages supply no installed acceptance.

FIX06 checks wrong-entry refusal, independent reads and unchanged account,
locale and product state. Ubuntu preservation pins `/usr/lib/os-release` and
`/etc/locale.conf`, separately preserving the exact `/etc/default/locale` →
`../locale.conf` compatibility link. Unexpected/dangling links refuse.
`native_fixtures_guest.product_tree` uses bounded descriptor-pinned witnesses
and refuses links, special files, replacement or changed bytes. Installed
consumers enter publicly before FIX06 and need no product-free FIX04 payload.
Missing language assets block with a preparation diagnostic; attempts and app
snapshots verify them without installation or repair.

DESK13 owns the account desktop-language switch. Its finite binding sets Jordan
to `zh_CN.UTF-8`, preserves Jamie/station English and independently reads the
actual AccountsService `Language` alongside `requested_locale`. Only
`zh_CN.UTF-8` or `zh_CN` are accepted for this binding; Ubuntu's
[validator](https://git.launchpad.net/ubuntu/+source/accountsservice/tree/debian/patches/0009-language-tools.patch?h=ubuntu/resolute)
may remove the suffix and GNOME login may restore it. No other locale variant
is accepted, and other-account preservation stays exact.
`compare_desktop_entry` permits only disappearance of the temporary
`gdm-greeter` account bound to the departed observed greeter; all persistent
accounts and graphical-session witnesses remain exact.

`check_e2e_desktop_language` qualifies setting/readback, not the language of a
renewed desktop. Explicit logout/login and public Chinese Shell observation
precede product assertions; `language_upgrade_entry` independently checks the
finite locale representations after renewal and retains the actual renewed
value for preservation. Personal language changes use public Preferences.
Reusable folder-renaming-prompt suppression preserves folder mappings/content
through the [baseline owner](../../tests/integration/Environment.md#reusable-preparation-ownership);
it changes no language or product result. Unexpected prompts refuse.

`chinese_current_install.PLAN` / `ChineseCurrentInstallJourney` and
`check_e2e_chinese_current_install` qualify Ubuntu current installation and
first presentation. They reuse `ChinesePresentationMixin`,
`chinese_desktop_renewal`, `chinese_initial_notice` and `chinese_initial_form`:
product-free entry, verified assets and renewed desktop, installation completion/
version/notice with unchanged-boot reread, one changed boot/fresh greeter, then
Jordan's untouched Chinese chooser/default and form after Cancel without Save.
The isolated payload includes `session_control`; no Parent policy setup is
needed. Product-free `fresh_desktop(..., product_free=True)` / `renewed_desktop`
requires Jordan/Jamie rows and no station; installed entry requires the station.
Both retain role-specific ordered secret-recipient proofs.

Chinese approval extends the [MATE binding](#external-provider-qualification)
with actual native explanatory/password/button text before secret input,
including after agent restart and fresh station entry. Keep the agent unmodified.
Jamie-from-station uses MATE's single-other-user super-user explanation, not its
same-user/multiple-user branch. `chinese_mate_texts(provider_version)` pins
Ubuntu 1.26.1 wording/mnemonic Cancel versus Fedora 1.28.1 upstream wording/Cancel.
Unknown versions and crossed catalogues refuse; the decoder independently checks
the version-bound oracle.

`chinese_native_auth.PLAN` / `check_e2e_chinese_native_auth` qualify both genuine
Chinese approvals on Ubuntu MATE `1.26.1-6`, `zh_CN.utf8`, `xkb/us`, with
fresh agent/challenge identities, persisted language and normal GDM returns.
Reuse `request_flow.chinese_request` / `onpc_request_flow::prepare_chinese` and
`kiosk_approved_flow.chinese_approval` / `onpc_request_flow::approve_chinese`; callers own entry/
return. English wrong-entry reads may reacquire incomplete/stale observations
within the existing deadline, but only a complete owned refusal permits progress.

`chinese_lifecycle.PLAN` / `onpc_chinese_lifecycle::run` and
`ChineseRequestInstallJourney` bind complete Ubuntu case 254: one installation/
reboot, two native approvals, checked preferences, request estimates and
independent Parent time/policy results. Post-setup input uses
`kiosk-language-jordan-jamie-chinese`; an English-only selector is invalid.
Provider scope is Jamie/Jordan, 75 seconds, soft apps included.

The separate `chinese_kiosk_lifecycle.py` /
`check_e2e_chinese_kiosk_lifecycle` capability combines installed DESK13, Chinese
desktop renewal, a genuine upgrade, initial notice and another declared reboot.
Its initial observations neither save language nor approve access. Reuse its
qualified observations without importing that older package/upgrade history
into the current single-reboot recipe. Its Ubuntu Shell tuple is
`50.1-0ubuntu1.3`, `zh_CN.UTF-8`, `xkb/us`; it alone proves neither native
authentication nor a complete scenario. Current-package snapshot selection uses
`named_input(package_source=True)` and preserves older frozen bundles.

### Native fixture preparation

FIX06's declaration is [native_assets.py](../../tests/fixtures/native_assets.py).
The [builder](../../tests/fixtures/build_test_applications.py) gives A/H/S/N
distinct executable bytes while preserving GUI kind. Preparation leaves all
launchers Allowed; policy setup remains a customer action.

| Role | Desktop ID suffix (`com.puffyslippers.ONPCTest.`) | Executable below `/opt/onpc-test-fixtures/Applications` | Visible name | Description | Default match |
| --- | --- | --- | --- | --- | --- |
| A | `A.desktop` | `Exact Fixture.AppImage` | ONPC Allowed Fixture | Exact native catalogue fixture | precise |
| H | `H.desktop` | `Path With Spaces.AppImage` | ONPC Hard Fixture | Whitespace native catalogue fixture | precise |
| S | `S.desktop` | `Versioned/Lunar Client-3.7.17.AppImage` | ONPC Soft Fixture | Versioned native catalogue fixture | pattern (`Versioned/Lunar Client-*.AppImage`) |
| N | `N.desktop` | `PrismLauncher.AppImage` | ONPC Nonmatching Fixture | Unrelated native catalogue fixture | precise |

S's adjacent GUI/automation modules live in `Applications/Versioned`; A/H/N
use those in `Applications`. The original root-level S remains an untrusted
compatibility control with identical bytes. The pinned Versioned directory is
Jordan-owned 0755 and contains only S and its two modules. Extra/stale files,
links, changed bytes/modes or foreign ownership refuse. Active and legacy S
remain excluded from file trust.

The current native profile has 12 active source keys; Riley uses eight runtime
files plus its own A launcher. Earlier ten/seven-file qualifications do not
verify the expanded twelve/nine-file profiles. The
[compatible fixture scope](#c04p1-compatible-fixture-applicability) and
[core-effects scope](#c04p-time-and-app-effects-applicability) distinguish current
both-target full-profile qualification from still-unrenewed Riley-grid and
copy/update/nonmatch histories.

`native_launch_command` and public activity readers bind A to primary and S to
secondary for the delivered finite C04p core-effects history; those exact
Submit/result bindings are qualified on both declared targets. Broader roles,
routes and compositions remain pending. Distinct bytes alone do not
prove window identity. Two launchers sharing one target and a future-version/
new-nonmatch profile remain separate pending capabilities. The isolated S
directory supplies neither. Space-bearing ELF nonmatches in the legacy directory
still require the separate unsafe-wildcard rejection under
[application policy](../SystemDesign/Applications.md). Snap/Flatpak builders
likewise need their declared A/H/S profiles; one package identity is insufficient.

Declared placement uses [baseline_fixtures.py](../../tests/integration/baseline_fixtures.py)
and [baseline_assets.py](../../tests/fixtures/baseline_assets.py): matching files
reuse, only recorded owned files update, unrelated files survive and partial
work retries. Directories/binaries are 0755, modules/desktop files 0644, with
declared ownership; Jordan owns the shared payload while Riley owns its launcher.
Reusable placement follows the [fixture lifecycle](Fixture-Design.md); ordinary
readiness never copies or repairs files.

[NativeFixtures](../../tests/e2e/native_fixtures.py) uses guarded SSH after
independent graphical entry. `fixture_actions()` supplies wrong-entry refusal/
`native-verify`; the [guest helper](../../tests/e2e/native_fixtures_guest.py)
uses [descriptor-pinned reads](../../tests/e2e/guest_files.py), `pwd` home
resolution and source-keyed digests. Missing files, unsafe parents, links/hardlinks,
corruption, replacement and owner/mode changes refuse. It changes no policy,
grant or app state. Frozen inputs are preserved; absent inputs use maintained
`named_input(fixture_source=True)` preparation.

`native_fixture_qualification.PLAN` / `NativeFixtureJourney` /
`onpc_app_rows::native_fixtures` compose guarded entry, verification and
PARENT12/UI13 Allowed/default-match observations of all four apps, wrong-child/
page refusals and independent reopening with stock rows retained.
`check_catalogue()` is caller-owned comparison. Jordan uses `existing-apps` /
`existing-parent-app-rows`; unprefixed operations retain Riley compatibility.
`check_e2e_native_fixtures` qualifies catalogue/readiness, not app usability.

The command/grid usability bindings share `native_search`,
`native_launch_grid`, `native_use_app` and `native_close_app`.
A's exact query is `ONPC Allowed Fixture`, its window
`onpc-fixture-native-primary`; Submit must independently show
`ONPC fixture draft`, unchanged draft and `Moves: 0; token: 0`.
Normal close requires complete owned-window absence and the recognized desktop.
`native_grid_usable.PLAN` / `check_e2e_native_grid_usable` qualifies Jordan
grid use on Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, `xkb/us`.
`riley_native_grid.PLAN` / `check_e2e_riley_native_grid` qualifies Riley's
earlier profile on Ubuntu `50.1-0ubuntu1.3` and Fedora `0:50.5-1.fc44`,
both `en_US.UTF-8` / `xkb/us`, using 900 seconds daily/no grant and two independent
grid launch/use/close entries. Complete absence, ambiguity or changed query/focus
refuses; incomplete/departed reads may reacquire only within the original deadline.
Uncertain input is never replayed.

`native_app.PLAN` / `check_e2e_native_app` qualifies the fixed command route:
fresh distinct Parent/Jordan challenges with two ordered proofs each, one
`AccessibleUI.native_launch_command` submission over guarded SSH, then independent
owned-window/use/close results. Command success alone proves no window.
The supporting command's two preflights bind the active unlocked local account, complete
owned-window absence and prompt refusal. They need no repeated Shell desktop
stability tour; Overview preparation stays between the fresh preflights.
Normal closure still requires its independently recognized desktop.
`native_activity.PLAN` / `check_e2e_app_activity` adds APP04/FLOW08 capture/
reread; replacement windows with identical text cannot establish retention.
`AppActivityObservation.from_value` freezes endpoint/state;
`JourneyPlan.activity_checks` binds earlier captures and expected `same` or
qualification-only `replaced`. `InstalledJourney.check_activity` compares before
durable reply and rejects missing/replayed captures or changed state/window.

Retained-work activity uses the distinct root-owned
`/opt/onpc-test-fixtures-activity/native-fixture` and two adjacent modules,
trusted only by their exact file receipt. `native_activity_entry` binds
`native-activity-launch`; policy-target command/grid routes retain A.
Verify source bytes, owner/modes, preparation/backend provenance and exact loaded
trust rows; refuse trust for intentionally untrusted controls. Ubuntu direct/
retained-GDM and Fedora direct unlock are qualified. Fedora retained return
remains open: launch, submit and capture completed, but no independently
acknowledged returned desktop followed `retained-recipient-rechecked`.
No partial slice supplies a complete scenario pass.

FIX03 profiles reuse [account fixtures](../../tests/e2e/account_fixture.py):

- Multiple: `kiosk_multiple.PLAN` / `KioskMultipleJourney` /
  `onpc_kiosk_multiple::run` publicly enable/read each child's limits, then use
  Riley/Jamie and Jordan/Casey, each 1800 seconds/soft excluded. Require exact
  offered sets, fresh real context-bound MATE prompts, normal password-free Cancel,
  complete prompt absence and unchanged no-error form. The separate original
  75-second/soft-included binding remains qualified. Provider: Ubuntu MATE
  `1.26.1-6`, `en_US.UTF-8`, `xkb/us`.
- Locked approver: `kiosk_multiple.INELIGIBLE_PLAN` / `KioskIneligibleJourney`,
  `station_fixture_actions(..., 'ineligible-approver')` and
  `e2e_dynamic_account.prepare_ineligible_approver` create only the fixed
  locked administrator `onpc-e2e-locked-parent`, without credentials.
  Refuse collisions and preserve children, eligible parents/station and all
  existing identities. Every offered-set check excludes it. Other ineligibility
  causes remain unqualified.
- No approver: `AccessibleUI.kiosk_approver_baseline` requires a nonempty public
  parent set without fixed names/counts and binds selected UID independently of
  popup state. `NoApproverFixture.prepare` /
  `e2e_dynamic_account.prepare_no_approver` discover all eligible OS accounts,
  require the observed parent among them, then validate/lock them. Preserve
  children, station and unrelated accounts. Return to GDM/reopen before
  `kiosk_request_form(no_approver=True)` / `RequestObservation.from_request`
  require exact empty list, explanation, disabled controls and absent prompt.

Outer restoration owns fixture undo. `kiosk_multiple.CASE_PLAN`,
`INELIGIBLE_CASE_PLAN` / `execute_ineligible`,
`kiosk_no_approver.CASE_PLAN` / `onpc_no_parent::run` and
`kiosk_no_child.CASE_PLAN` / `onpc_no_child::run` retain complete-case
composition, excluding qualification-only wrong-entry exercises. Durable
fixture evidence records presence/counts, not account identities.

Every recipe shares the existing envelope:

1. Setup guarded accounts/credentials/assets and verified installed state;
   FIX03/04 operate only where declared. Installation/removal families and
   harness case 1 start product-free. FIX01/02 retain their explicit in-journey
   checkpoints in independent attempts.
2. Start one recorder-bound attempt with explicit inputs; no state resume.
3. Execute ordered actions with fresh public observations; inventory
   `step-N` phases retain their recipe correspondence.
4. Reconcile all declared outcomes and preserve the original failure.
5. Finish owned worker/credential/staging cleanup, baseline restoration and
   host/source preservation, including failure paths. Never reset within a recipe.

Reuse [InstalledSetup](../../tests/e2e/installed_setup.py),
[InstalledJourney](../../tests/e2e/installed_journey.py),
[execution](../../tests/e2e/execution.py) and
[leased recording](../../tests/e2e/leased_recording.py). The
[migration constraints](#refactoring-the-established-cases) preserve this runtime
rather than adding another recorder, worker or installer.

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
IDs 140–150 retain only the engineering obligations below.

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
[Approval tools](../Approval-Tools.md#one-time-setup), which owns overwrite
behavior, platform selection and maintained recovery. It always prepares online
snapshots and defaults to overwriting; unattended callers explicitly choose
`--overwrite true` or `--overwrite false`. The guest remains running under
VM-maintenance ownership. Snapshots retain `onpc-v[version]`; neither a snapshot name nor prior
mutable guest state is freshness or acceptance evidence. Reusable guest inputs
remain exclusively owned by baseline preparation.

A retained snapshot is a setup prerequisite, not customer-acceptance evidence.
Release online maintenance before a qualification or E2E attempt acquires its
own lease; subsequent VM actions retain guarded ownership.


E2E-001 remains [harness qualification](#case-1-stage-contract). For customer
families E2E-002–011, select the exact [family recipe](E2E-Scenario-Recipes.md#family-compositions)
and consult the [family allocation review](UI-and-E2E-Coverage.md#complete-scenario-family-review)
for assertion ownership. Case IDs and runtime bindings come from the inventory;
this catalogue does not maintain another case list.

### Request forms and remembered choices

The [E2E-012–018 recipes](E2E-Scenario-Recipes.md#e2e-012) own request, approval,
exit, selector and persistence composition. E2E-014 retains the
[native-gesture exclusion](../Mandates/UI-Automation-Mandate.MD#unsupported-native-gestures);
uncovered assertions are neither qualification nor a new gesture task.

`onpc_remembered_choices::run` and `run_reverse` compare immutable original
captures for transfer and persistence/isolation. No approval, retained-desktop
return or time denial is part of these histories.

| Case / `remembered_choices` binding | Finite history |
| --- | --- |
| 58 / `PLAN` | Jordan then Riley: custom 1.25 minutes/75 seconds soft included, then 2.5 minutes/150 seconds soft excluded. Overlay Casey, kiosk Jamie. One overlay visit/transfer per child, then both kiosk reselections compare against original captures. |
| 59 / `SECOND_PLAN` | Same history, Riley then Jordan, using `remembered-second` choices. |
| 60 / `REVERSE_PLAN` | Seed Casey in each overlay and log out. Station Jamie saves Jordan 75 seconds/included then Riley 150 seconds/excluded. Untouched transfer and freshly reopened overlay reads compare against original kiosk captures. |
| 61 / `REVERSE_SECOND_PLAN` | Same reverse history, Riley then Jordan; Jamie stays station-local and Casey overlay-local, with normal logout between fresh visits. |

`request_flow.kiosk_to_overlay(..., choices='remembered')` reuses FLOW12's
fresh transport. Wrong-account refusal precedes unrelated provider discovery.
Caller-declared order, current recipient guards and immutable comparisons before
durable reply remain mandatory. `remembered_choices.DIAGNOSTIC_PLAN` is the
maintenance-only retained-return scene, not required customer composition.
These complete-case bindings cover Ubuntu 26.04 and Fedora 44; current source/
qualification guards still apply.

### Application routes and complete customer journeys

The [E2E-019–027 recipes](E2E-Scenario-Recipes.md#e2e-019) own finite launch,
catalogue, retained-session, gameplay, update and removal histories.

Native Allowed bindings use shared policy edits, fresh entry and independent
window/Submit/result comparisons. `AppPolicyJourney` checks settings, balances,
match and access before acknowledgement. Parent saves Jordan's precise Allowed
rule; Riley's existing policy and disabled limits stay untouched. No approval
or alternative launch substitutes for the declared route.

| Case / binding | Scope |
| --- | --- |
| 62 / `app_launch.GRID_PLAN`, `onpc_app_launch::run(..., 'enabled', 'grid')` | 30 daily minutes/zero grant; Jordan `other-child`, Riley `child`; each freshly enters and uses A through the grid. Reuses the qualified native/activity/baseline-child preparation: setup verifies Riley's catalogue and shared runtime; the native stage action verifies Jordan's catalogue. |
| 80 / `app_launch.PLAN`, `onpc_app_launch::run` | Same enabled setup; Jordan then Riley freshly enter and use `Exact Fixture.AppImage` through the fixed command route. |
| 81 / `app_launch.DISABLED_PLAN`, `run(..., 'disabled')` | Limits off/zero allowance; skip only enabled allowance setup/readback. Both children prove the same command target usable. |

These exact native-A bindings are qualified on Ubuntu 26.04 and Fedora 44.
Other route/rule/control bindings remain separate. Invalid control, wrong-child,
allowance or result readbacks fail before durable reply.

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

The real Lunar profile qualification/FIX05 must first establish how these inputs are present **after** the
runner's ordinary installed-snapshot restore. Use the authorized baseline route
and its finite idempotent inventory; do not add alternate snapshots, skip
restoration or rely on earlier manual VM state. FIX04 transfers attempt inputs;
FIX05 verifies this real-app profile and FIX06 verifies repository-owned fixtures.
This prerequisite does not grant FIX05 an installer or
unattended vendor sign-in. Missing integration, invalid sign-in, mandatory update,
network dependence or unavailable assets blocks this profile until resolved in
preparation. Pin a profile that runs the declared local activity without downloads
or authentication during the measured launch checks; requalify after drift.

Qualify original-AppImage launch/Quit, tray close/restore, specific command
denial and complete absence, Minecraft entry/exit and local-world activity,
and allowed/denied continuous login as separate bindings. Their APP01/02/03/06,
UI18 and UI22 scopes do not imply one another. Apply the
[provider exception](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception)
inside explicit adapters, retaining ownership, complete absence observations,
ambiguity refusal and independent results.

The continuous-login qualification must first qualify continuous external-app observation and reattachment
across login. UI22's current `observed_text` / `start_trace` / `poll_trace` /
`finish_trace` binding observes Parent feedback, not a Lunar login interval.
Reuse its lifecycle/ownership principles and the existing reboot/session recorder,
but keep the missing public projection explicitly planned. The denied-login qualification consumes
that new binding: arm the public observation before child login submission, preserve secret filtering,
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

<a id="inventory-reconciliation"></a>

### Engineering coverage boundary

The UI inventory contains the harness qualification and customer journeys.
Retired E2E IDs 140–150 are never reused. Internal fault, service, process,
D-Bus and transaction assertions belong to engineering coverage, not customer
acceptance. Their removal from customer recipes does not delete the obligations:

- Installation/removal independently verify package digests, files, ownership,
 services, D-Bus, Polkit, PAM, sessions, configuration, extension payload, logs
 and execution policy. Correlate same-boot readiness ordering: execution-policy
 reconciliation and extension activation precede broker publication; the live
 canary completes before display-manager startup. A final service snapshot
 cannot prove ordering. Preserve notice content and final-output semantics;
 color supplies no customer acceptance.
- Transactions verify allowance/grant preservation and clearing, no invalid
 commits, selected-child activation and policy, exact single grant per valid
 request, no grant/relaxation after denial or Cancel, and current-grant
 reconciliation rather than stale expired policy. Verify soft-excluded closure
 before granting and soft-included preservation of already-open apps.
- Enforcement correlates executable/sandbox identities, patterns and filters
 with launch/termination effects; measures daily usage and grant accumulation;
 preserves retained sessions until explicit logout and never interrupts other
 users. Reboot continuity permits only declared provisioning/enforcement changes
 and does not claim foreground-process survival across reboot.
- Preferences and lifecycle verify account identities, enablement, per-child
 selectors, persisted settings and activation across genuine package changes,
 reboot, removal and reinstall. Future interactive mute remains deferred;
 current recipes exercise available choices without a public mute control.
- Kiosk coverage verifies no general desktop/management authority, usable
 repeated entry under ambient variation, genuine essential-service recovery,
 useful original causes, safe exit/retry and preservation of foreign/live
 sessions. Unknown valid ambient content alone must not force reboot/refusal.
 The [missing-scenery history](#requests-with-missing-optional-scenery) verifies
 one existing optional-artwork fallback through genuine approval and restoration.
 Retired mask/view/generation workers supply no current executable acceptance.
- Diagnostics/transport verify sanitization, retention, export metadata, frozen
 drafts/bytes, privacy, idempotency and actual provider receipts under separately
 authorized integration. Real transport interruption/recovery uses guarded
 network control, never forged server responses; visible app retry alone does
 not satisfy internal continuity or recipient-delivery assertions.

Maintained owners are [system tests](../../tests/system),
[broker components](../../tests/component), [unit tests](../../tests/unit) and
[UI tests](../../tests/ui). Missing exact implementation remains pending.
The [assertion allocation](UI-and-E2E-Coverage.md#reuse-of-system-and-integration-coverage)
governs reuse without shortening customer journeys. In particular, obligation
147 is already executable as system 255 in
[`test_requester_disconnect_during_approval`](../../tests/system/test_authorization.py).
It covers child/kiosk requester loss while the real agent lives, cancellation
without writes, released transaction, a fresh authenticated grant and unchanged
other accounts. It needs no separate E2E-queue task or duplicate test.
Obligation 148 reuses the real threaded broker conflict/rollback/retry tests
`test_parent_disable_cannot_interleave_with_admitted_approval` and
`test_approval_cannot_snapshot_parent_disable_bridge_or_rollback` in
[`test_core.py`](../../tests/unit/test_core.py), private-bus concurrent worker
dispatch in [`test_private_dbus_service.py`](../../tests/component/test_private_dbus_service.py),
and system 255's installed bus/agent Busy/release and authenticated recovery.
No separate installed qualifier is scheduled for those covered assertions.
Obligations 140–146 and 149–150 retain their specific missing fault/observation
or recovery assertions in the queue briefs; their existing system/component
matrices are reused rather than implemented again. This mapping supplies no
new installed result.
Unsupported OS/reserved-account failures, conversion/rollback, all-account
authorization and injected faults remain technical coverage. Same-child
multiple desktops and an already-open hard-blocked app require real public
setup before becoming customer recipes; repeated GDM resume is not a substitute.

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
attachment case 154 supplies no interactive-mute qualification.
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
result. Composition checks alone supply no live credit.

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
 shared DESK04 logout between them. Qualification covers two distinct
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
 binding retains fresh Parent entry, wrong-child refusal, both immutable
 comparisons and durable `first-return`/`step-1`, `second-return`/`step-2` assertions. The first assertion precedes the next phase
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

The composition guard discovers ready executables and registered workers,
rejects local mechanics/case dependencies and reconciles phases/assertions with
the inventory. Its reviewed API list contains shared callables, not a fixed
case list. Close/search input requires fresh proofs, independent results and
no uncertain replay. Changes to shared GDM, secret input, stage reconciliation
or routing require affected harness safety and scoped installed qualification.

## About block contracts

Customer information journeys make one About visit and return to unchanged work.
Case 151 uses `parent-about-information` / `read_about_information` /
`onpc_about::close_information`; 191 uses
`overlay_license_read(links='summary')` and captured-request comparison; 192
reads restricted-station information without external actions. Case 190 has no
E2E binding; its retained plan/worker serves engineering checks only.

ABOUT01 resolves owned product/version by public ID. ABOUT02's
`AccessibleUI.clickable_link` requires visible/enabled/nondefunct control with
one public action, without activation, URI/recipient/subject inspection or an
external handler. Legacy `open_license` / `license` names remain read-only.

| Surface / capability binding | Scope |
| --- | --- |
| Parent `LicenseViewerProviderJourney` / `onpc_license_viewer_provider::run`, `check_e2e_license_viewer` | License clickability, fresh independent entries, wrong-entry refusal, footer/About close and unchanged child/settings. External-viewer checks are retired; old passes do not qualify the changed scope. |
| Parent `WEBSITE_PLAN` / `check_e2e_parent_website` | Compatibility stages `license` / `license-provider-refusals` map to `website-clickable` on `about-website-value`. |
| Parent `SUPPORT_PLAN` / `ParentSupportJourney`, `check_e2e_parent_support` | Two fresh `support-clickable` reads of `about-support-value`, then owned return. |
| Parent `INFORMATION_PLAN` / `ParentInformationJourney`, `check_e2e_read_parent_information_links` | Read Help, enter About from the same owned menu, then website/privacy/support/license/legal in order; first refusal stops. |
| Overlay `overlay_license.PLAN`, `BROWSER_LINKS_PLAN`, `INFORMATION_PLAN` / `OverlayLicenseJourney` | License, website/privacy or full Help/five-link scope through `journey_blocks.overlay_license_read` / `onpc_about::overlay_license`. Caller owns immutable request comparisons. |
| Station `restricted_station_about.PLAN` / `RestrictedStationAboutJourney`, `check_e2e_read_restricted_station_about` | Offered information, complete external-action absence, preserved form and normal Cancel/GDM return. [Renewed scope](#c04i-existing-kiosk-about-renewal) covers both rebuilt targets. |

Parent/overlay capabilities are scoped to Ubuntu 26.04; other surfaces and complete
cases retain separate acceptance. Missing/hidden/disabled/nonactionable/ambiguous/
wrong-owner controls refuse. Complete fresh traversal, including clipped controls,
is required for absence; inaccessible trees prove nothing.

Overlay scope binds form/About by application, public transient relation and fixed
child session. `check_overlay_help` and `open_overlay_about(menu_open=True)`
preserve menu entry; `read_overlay_link` checks product/version and declared link.
A fresh active About proof authorizes one `onpc_window::close('overlay-about')`;
complete absence/active form precede `KioskRequestJourney`'s immutable
75-second custom/soft-included comparison. Qualification retains independent
entries and wrong-account/missing-About/stale-proof refusals.

Station uses `kiosk_about_entry`, `open_kiosk_about`, `kiosk_about_snapshot`
and `read_kiosk_about(version)`. Parent/overlay owners cannot authorize it.
The five external values are labels without actions. Fresh station-owned About
proof precedes one normal `close('station-about')`, absence and form comparison.
`kiosk_about.PLAN` / `onpc_kiosk_about::run` uses FLOW16's 1800/0/1800-second
starting balances; its customer recipe remains distinct.

PARENT01's `onpc_parent::launch` consumes fresh desktop proof before one fixed
`/usr/bin/oh-no-parent-control-parent` submission through that user's systemd
manager and inherited graphical environment. The unprivileged adapter verifies
one active local graphical session and refuses prompts. No terminal, shell string,
product method or private state is used. Uncertain submission never retries.
Separate readback must observe management or the specific denial. The legacy
case-6 `terminal` ID means denied launch/dismissal/clear desktop.
`check_e2e_terminal_provider` qualifies that fresh standard-account binding;
retained/reopening routes remain separate.

Shared launch stops at `parent-window` before picker input; selection has its
own fresh choice proof/setter/readback. Setup reattachment is outside customer
entry. GDM retains two ordered fresh intended-recipient proofs immediately before
sealed secret input, with wrong-recipient exercises isolated in qualification.

`onpc_about::return_to_parent` accepts declared source-stage bindings only.
Legacy `license-closed` observes the still-open About, with no external close.
Customer `close_information` omits the extra footer tour, reacquires Parent
and reads child/switch/allowance.
`settings_checks={'parent-returned': 'parent-selected'}` compares immutable
recipe-owned values before acknowledgement. Missing/changed/stale/replayed
observations and uncertain close stop input without replay.

## Parent discovery block contracts

The `parent-window` checkpoint separates launch from picker input.
`parent_discovery.PLAN` / `onpc_parent_discovery::run` composes FLOW15,
SEARCH05's discovery exception, explicit selection and both pages. Each selection
consumes a fresh surface/choice proof before canonical API input and independently
verifies the intended child. GDM retains two fresh intended-recipient proofs,
one sealed secret input and independent desktop result. Wrong-recipient exercises
remain separate qualification; no repeated/new-surface authentication is implied.

The [recipe](../../tests/e2e/parent_discovery.py) owns four immutable
`SettingsObservation` comparisons: original limits-off/zero minutes, unchanged
original settings immediately before FIX01, new-child settings after returning
from App Limits, then original-child settings on return. Unique stage keys replace
hidden initial/new-child slots. Comparison failure prevents fixture action and
acknowledgement and latches terminal failure. FIX01 stays after visible settings/
App Limits while Parent remains open; the new child appears without relaunch.

`parent_discovery.EMPTY_PLAN` / `onpc_parent_discovery::run_none` composes
GDM07/SEARCH06. Fresh desktop, search readiness, focus, whole-query readback and
focused launchable result are separate proofs. A second result-focus observation
and durable step-2 precede FIX02; only its successful acknowledgement opens
step-3 and permits Enter. FIX02 requires exactly both canonical eligible children,
preserves the station and refuses missing/substituted/additional accounts.
PARENT19 requires the visible “No interactive non-administrator account was found.”
explanation and sole `(None)` picker label. Disabled state is readable; no picker
input occurs. Missing/hidden text, selected child, stale/defunct reads or failed
preparation refuse. Outer cleanup restores the fixture. Neither recipe changes
time policy or establishes child-login enforcement.

[accessible_ui.py](../../tests/e2e/accessible_ui.py) exposes ID-scoped text,
complete canonical choices, selected values, settings/pages and disclosure.
Public IDs establish repository-owned target identity before labels/state verify
meaning. External GDM/Shell uses qualified provider adapters. Reuse roots within
one observation only; reacquire after input/page change. One fresh complete scoped
prompt guard precedes input and refuses unexpected dialogs without dismissal.
Prepared keyring Cancel remains separate. Missing/stale/ambiguous observations
and uncertain whole-query input prevent further input, including FIX02.

The real [worker](../../tests/integration/graphical_smoke/lib/onpc_parent_discovery.pm),
[controller](../../tests/e2e/installed_journey.py) and shared adapters own mechanics.
Independent supplied entry states must work without prior scenario execution;
offered-choice and immutable-result comparisons remain before durable reply.
Cases 3/4 retain separate complete bindings; other search/entry routes are not
qualified by these results.

## Functional validation

Apply the [UI mandate](../Mandates/UI-Automation-Mandate.MD). Repository-owned
controls require public IDs through the shared Application UI API; fixture IDs
belong in their activity adapters. External surfaces may use only qualified,
scoped provider adapters. Missing IDs are implementation gaps, not authority to
use arbitrary selectors. Never dismiss unknown dialogs or bypass modal guards.

Preview and guest readers share the [facade](../../tests/support/application_ui.py),
application/owner pins, explicit surfaces, canonical values and bounded inventory.
Preserve translated accessibility labels. Rich text, selection, formatting and
history use the packaged API: no caller JavaScript, arbitrary DOM/toolkit calls
or AT-SPI product fallback. Qualification covers real input/readback and identity.

Only [public semantic observations](../../tests/e2e/README.md#functional-gui-acceptance)
establish customer acceptance; screenshots, geometry and viewers add no prerequisite
to the product facade.

Supporting apps use [gui_application.py](../../tests/fixtures/gui_application.py)
and [fixture_ui.py](../../tests/e2e/fixture_ui.py), separately from product APIs.
Native/Flatpak/Snap/game IDs are `onpc-fixture-<kind>-<instance>`, with explicitly
declared `primary`/`secondary` and `draft`, `edit`, `submit`, `submitted`,
`move`, `score`, `status` or `close` controls. Titles/window order never
establish instance identity. Native owners retain their executable while their
GUI child runs and close that child on termination.

The one-shot mechanical fixture preserves its readiness marker; `--stay-alive`
is headless infrastructure, not GUI acceptance. The
[builder](../../tests/fixtures/build_test_applications.py) packages actual
Python/GTK Flatpak and strict-confinement Snap runtime bytes. Host payload tests
and unpacked Snap execution do not qualify snapd installation/confinement.
Installed app-filter consumers remain pending until their declared package,
launch/denial, running-app closure, retention and launch-route histories pass.

### External-provider qualification

Register mappings/selectors in [accessible_ui.py](../../tests/e2e/accessible_ui.py).
Each qualification is limited to its exact owner, surface, version, locale,
keyboard and input/result binding. Host doubles prove adapter/refusal mechanics,
not installed behavior. Semantic selectors are not provider-owned IDs.
Retained scenario registration never broadens a provider qualification.

Qualify independent entry/result, actual input/readback, ownership and wrong/
ambiguous-target refusal. Focus is required only for keyboard delivery.
Secret routes additionally require intended/wrong-recipient guards, an empty
masked field, capture restrictions, single use and uncertain-input refusal.
Generic pointer, image, positional and graphical-reattachment routes remain retired.

| Provider / surface | Qualified scope and limits | Consumers |
| --- | --- | --- |
| Native-fixture Shell grid | Exact Jordan/Riley `ONPC Allowed Fixture` bindings on Ubuntu 26.04/Fedora 44, through `check_e2e_riley_native_grid` and `check_e2e_native_grid_usable`. Complete-read reacquisition, recipient/ambiguity refusal and single-use input remain required. [Exact tuples/callables](#native-fixture-preparation). | Stated APP01/02/03 and FLOW08 grid bindings ready; policy-denial/complete journeys separate. |
| Chinese MATE agent | Ubuntu 26.04, MATE `1.26.1-6`, `zh_CN.utf8`, `xkb/us`: `mate_prompt(language='zh-Hans')`, `kiosk_mate_approval`, `check_e2e_chinese_native_auth`. Actual Chinese controls, Jamie/Jordan/75-second/soft-included context, fresh same-challenge recipient guards, real approval, Chinese result, GDM return and retained Chinese on fresh entry. [Exact scope](#chinese-language-preparation-and-desktop-language-setup). | Fixed Chinese AUTH01/02 and REQUEST11/12 ready; other tuples/history separate. |
| Shell desktop/search/lock | Ubuntu 26.04 English-GDM baseline: Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, `xkb/us` for fresh Parent/standard prompt-free desktop, prepared gcr return and stated search bindings. `standard_shell_desktop(no_prompt=True)`, `shell_search_snapshot`, `check_e2e_fresh_desktop`, `check_e2e_shell_search_results` and `check_e2e_shell_search` retain [search scope](#search-and-standard-sign-in-contracts). Parent lock/reveal and challenge observation also have Shell `50.1-0ubuntu1.3` scope; [recipient proof](#parent-lock-recipient-qualification) is separate. Child unlock/restriction uses its [exact Ubuntu/Fedora tuples](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) and [denial scope](#retained-child-time-restriction-and-greeter-return-qualification). | Fresh DESK01 Parent/standard, stated child DESK01/05–08 success/native restriction and Parent SEARCH01–06/standard SEARCH01/03/04 ready only as scoped. Product DESK12/REQUEST13/PANEL01–03 use the product API. Session/power/connectivity use system helpers; other retained/lock bindings pending. |
| GDM | `onpc_gdm::sign_in_challenge`/`check_e2e_challenges` qualify distinct Parent challenges on pinned Ubuntu 26.04 English-GDM/baseline keyboard. Intended account, two fresh recipient proofs, one secret delivery and independent desktop/denial remain mandatory. [Fresh success](#fresh-child-success-qualification), [zero-time return](#fresh-child-time-denial-and-return-qualification), [retained success](#successful-child-unlock-and-retained-gdm-reauthentication-qualification) and [retained denial](#retained-child-time-restriction-and-greeter-return-qualification) retain their exact tuples. GDM proof never authorizes lock-screen input. | Stated GDM01–03/05–09 entry bindings ready; GDM04/wrong-account tours are harness safety; other recipients pending. |
| Graphical VT6 | Refuses before image/secret/input access. Serial proof cannot authorize graphical credentials. | No current customer requirement; dedicated adapter needed for any future binding. |
| MATE agent | `mate_prompt`, `mate_prompt_refusals`, `kiosk_mate_cancel`, `mate_prompt.PLAN`/`check_e2e_auth_prompt`: Ubuntu 26.04, `1.26.1-6`, actual `en_US.UTF-8`, `[["xkb", "us"]]` (system fallback when kiosk per-user list empty). Bind service PID, sole live dialog, displayed parent/child/75-second/apps, sole empty masked focused field and enabled Cancel. Reacquire same challenge before one input; missing displayed context refuses. [Approval](#kiosk-approval-qualification) and [rejection](#kiosk-rejection-qualification) independently cover fixed password/result/exit branches. | Fixed REQUEST09/AUTH01 proof/Cancel, AUTH02 correct-password/rejection and REQUEST11/12 exits ready. Other tuples/secret routes pending. |
| Shell agent | `shell_prompt_owner`, `shell_prompt`, `shell_prompt_refusals`, `overlay_shell_cancel_ready`, `overlay_prompt.PLAN`/`check_e2e_overlay_prompt`: Ubuntu 26.04 Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, `xkb/us`, displayed parent/child/75-second/soft-app context, empty masked recipient, same-challenge proof and normal Cancel/unchanged form. [Approval/automatic return](#overlay-approval-and-automatic-return-qualification) and [rejection/fresh Cancel](#overlay-rejection-and-cancel-qualification) also cover `50.1-0ubuntu1.3`, same locale/keyboard. | Fixed AUTH01/REQUEST09, AUTH02 approval/rejection and REQUEST11/12 automatic return ready; immediate exit/other bindings separate. |
| gcr keyring | `keyring_cancel_target`/`cancel_keyring_prompt`, `check_e2e_desktop_keyring`: Ubuntu 26.04, gcr `3.41.2-6`, Shell `50.1-0ubuntu1.2`, `en_US.UTF-8`, `[["xkb", "us"]]`. Sole live Login Keyring dialog, empty masked focused field and enabled Cancel; container visibility is not required. One Cancel, disappearance and two-second prompt-free desktop. Preparation verifies PrivatePrompter/SystemPrompter ownership and requests existing Login collection unlock without reading/supplying a password. | Prepared standard DESK01 return ready; Parent cancellation, other tuples and automatic middleware composition unqualified. |
| Native GTK chooser | Requires caller-owned dialog, exact file readback and wrong-dialog refusal. | FILE03/FEED06/FEED08 routes remain individually gated. |
| Portal/Nautilus chooser | `chooser_snapshot` plus `validate_chooser_portal_owner` bind unique modal and sole delegated D-Bus request. Missing/ambiguous/replaced/contradictory relations refuse. Imported Wayland parents need no GTK CONTROLLED_BY. Scoped Close cancels portal; native GTK uses Cancel; `button`/`push button` roles supported. Parent Open/Cancel qualified on `1:50.2.2-0ubuntu0.1` and `1:50.2.2-0ubuntu0.2`, `en_US.UTF-8`, `xkb/us`; named Save/Cancel, unwritable-save recovery and export on `1:50.2.2-0ubuntu0.2`, caller `parent-feedback`. Save restores collapsed `filename_label` before exact-name proof. [Handoff](#attachment-chooser-handoff). | Fixed Parent Open/Cancel, Save/Cancel, save-error recovery and FEED08 export ready; other profiles/tuples pending. |
| Document viewer | `license_viewer_snapshot`/`check_e2e_license_viewer`: Ubuntu 26.04 Text Editor `50.1-0ubuntu0.1`, `en_US.UTF-8`, `[["xkb", "us"]]`. Owned active viewer, bounded GPL content, close/absence and unchanged caller state; ambiguous/unrelated/hidden content refuses. [DESK10](#same-desktop-window-activation) additionally covers direct LICENSE launch/repeated activation. | DESK10 only; About links and FILE08/FEED08 inspection require no viewer. |
| Terminal; Settings Users/Date & Time | Retired supporting GUI routes. Fixed guarded commands own files, account fixtures and date/time reads; observe product effects independently. | FILE01/02/06, INFO02, ACCOUNT01/02, AUTH04, TIME05 helpers; no Terminal GUI consumer. |
| DING desktop icons | No provider route. Requires explicit icon/selection/activation and independently owned launched window. | Declared APP01/02 desktop route pending. |
| Nautilus Files | Qualify only the tested file-manager enforcement launch; supporting file preparation uses commands. | FILE04/declared APP01/02 routes individually gated. |
| File Roller | No GUI consumer; bounded FILE08 archive API reads customer exports. | FILE08/FEED08 readers ready; no archive viewer needed. |
| Registered editor | Direct handler launch only for declared preview/information integration or retained-work activity. Source mutation/export reads use FILE05/08/09. | FILE08 work/APP03/04; no FEED08 viewer dependency. |
| Lunar/AppImageLauncher/tray/Minecraft | No qualified binding. Require actual prepared AppImage, allowed autostart, complete login-interval tray/window observations, same-route denial, local-world action and genuine Quit. [Gate](#lunar-client-preparation-and-observation-gate). | APP01/02/03/06, UI18/22 and FIX05 pending. |

Generic Shell notifications, graphical VT6 and diagnostic-export viewers have no
active customer requirement or acceptance credit. Chooser qualification follows
the actual Gtk.FileDialog backend, not an unused compatibility matrix.
Remote desktop testing is excluded by developer direction; no provider binding,
qualification task or remote acceptance is allocated.

The product-free GDM binding is `gdm_product_free_account()` /
`gdm_product_free_navigation()`: `check_e2e_gdm_product_free` qualifies two
independent intended-Parent list/focus/prompt/Escape-return cycles. Installed
`gdm_nonsecret_account()` retains station cardinality checks. The serial harness
uses product-free operations at every graphical stage and requires authenticated
serial input, command output, logout-before-return and unchanged-boot continuity.
A future consumer needs its own scoped provider prerequisite.

### Product-free Parent entry and command context

`check_e2e_product_free_entry` qualifies Ubuntu 26.04 product-free entry.
`ProductFreeEntryQualification` uses FIX04 without product installation/reboot.
`InstalledJourney` requires exclusive setup modes and a matching booted transfer
receipt. `ProductFreeEntryJourney`/`onpc_product_free_entry::run` use intended
Parent login, two fresh recipient proofs, single-use input and an independent
desktop result. Greeter entry separately proves command-context refusal.

`session_control.execute('parent-command-context')` binds the active local
unlocked Parent, drops to that account, verifies administrator authority and
reads the protected staged package. Its digest must match verified input before
acknowledgement. Provider observations retain GDM `50.1-0ubuntu0.1`, Shell
`50.1-0ubuntu1.2`, actual `en_US.UTF-8`, `[["xkb", "us"]]`.
Greeter layout comes from public locale1; desktop layout from account GSettings.
Missing/malformed metadata refuses rather than inventing a default.

### Administrator package command and output

`check_e2e_package_authority`, `PackageAuthorityQualification`,
`PackageAuthorityJourney` and `onpc_package_authority::run` qualify the fixed
product-free Ubuntu 26.04 install command. Shared
[PackageCommand](../../tests/e2e/package_command.py) leaves enforce:

- `validate_input`: fixed `install-staged-package`, exact package digest and
  transport VM/attempt identity.
- `submit`/`guest_submit`: recheck active unlocked local Parent administrator
  and immutable package before one APT invocation. Dependencies may download.
  Host consumption and an exclusive guest marker prevent replay after uncertain
  input. Guarded transport supplies system authority without a Terminal or
  unrelated GUI password prompt.
- `read_result`: independently recheck provenance/attempt, exit zero, actual
  package completion and reboot notice as final output. Combined stdout/stderr
  is bounded to 1 MiB with a 660-second deadline; raw diagnostics remain private.

Fedora follows its [output contract](../Fedora-Packaging.md#fedora-lifecycle):
the verified package's completed posttrans/postun scriptlet ends with the literal
notice, ignoring empty trailing scriptlet lines; later DNF framing may follow.
Exit and independent installed-version/absence checks remain required. Purge
reads its own completion/reminder after DNF.

Greeter/wrong-artifact/VM/attempt/unregistered-command/replay refusal and successful
output are scoped capability results, not complete product acceptance. Other
package operations retain separate gates.

### Customer package install composition

`check_e2e_package_command`, `PackageInstallQualification`,
[PackageInstallJourney](../../tests/e2e/package_install.py) and
`onpc_package_install::run` qualify fresh product-free Ubuntu 26.04 composition.
`submit_install` binds one verified administrator submission and retains consumed
uncertainty. `observe_install` independently reads completion/final reboot notice
at a later checkpoint before durable acknowledgement.

### Genuine unrelated-package reboot request

`check_e2e_unrelated_reboot_request` qualifies the finite Ubuntu 26.04 LIFE04
operation through `package_install.submit_unrelated`/`observe_unrelated`,
`UnrelatedRebootJourney`/`PLAN` and `onpc_customer_reboot::unrelated_request`.

Input is installed `libc6:amd64` `2.43-2ubuntu2.4`, source `glibc`, archive SHA256
`a613b457f3ff9c84ebd28af8a05afdec22605ad9aed87c71e3a6ae5170aeb9ca`,
`pool/main/g/glibc/libc6_2.43-2ubuntu2.4_amd64.deb`.
The fixed command is `/usr/sbin/dpkg-reconfigure --frontend=noninteractive libc6:amd64`.
`installation_observations.UNRELATED_PACKAGE`/`UNRELATED_SCRIPTS` bind provenance,
installed payload, maintainer/command bytes and absence of alternatives.
Dependencies are baseline-owned; reconfiguration is attempt-owned. No synthetic
package, notifier invocation or manual reboot marker substitutes for this input.

Require installed product, observed activation reboot, fresh administrator return,
exact unrelated-package identity and no prior system/product reboot request.
Submission is consumed and refuses wrong command/digest/VM/attempt/replay.
The independent result requires exit zero and actual systemd-trigger completion;
the pinned postinst's `Nothing to restart.` branch applies only to older versions.
Read genuine `*** System restart required ***` attributed to libc6, absent product
requests and unchanged product/boot/session/account/unrelated-file witnesses.
This operation supplies no complete-case acceptance; other package bindings remain pending.

### Genuine package upgrade

`check_e2e_package_upgrade` qualifies Ubuntu 26.04 amd64's genuine
`1.2+ppa1~ubuntu26.04.1` to `1.3+ppa1~ubuntu26.04.1` binding.
`PackageUpgradeJourney`, `submit_release`/`observe_release` and
`onpc_customer_reboot::install_entry`/`return_entry` compose actual old installation,
activation reboot and one update.

`PackageCommand` uses separate `install-previous-release`/`upgrade-staged-package`
identities and consumption markers, immutable dual-package validation, public phase
guards and version/preservation readback. Uncertainty remains consumed across
objects. Upgrade requires independently activated old release/changed boot; old
completion follows its own output contract. Independently verify update completion,
final notice and unchanged boot, accounts, language, session and unrelated files.
An optional absent motd is explicit evidence: later creation/removal/change fails;
required-file absence/read errors refuse. Wrong entry/phase/provenance/replay
must refuse.

### Customer reboot continuity

`check_e2e_customer_reboot`, [CustomerRebootJourney](../../tests/e2e/customer_reboot.py),
`CustomerRebootQualification` and `onpc_customer_reboot::run` qualify fresh install,
reboot and administrator return on Ubuntu 26.04, GDM `50.1-0ubuntu0.1`, Shell
`50.1-0ubuntu1.2`, `en_US.UTF-8`, `xkb/us`. Other lifecycle tuples remain pending.

`JourneyPlan.reboot_transition` names adjacent command-context/`ui:gdm-list`
checkpoints. `InstalledJourney.submit_reboot` durably records intent before one
fixed `systemctl --no-ask-password reboot` on the pinned old boot and consumes
uncertain submission. `ReadOnlyObservations.wait_boot_change` requires changed
boot on the same VM/transport, discards old UI state, observes fresh usable GDM
and uses two fresh recipient proofs for administrator return. Unexpected/repeated
boots refuse; command success is insufficient. Wait is bounded to 330 seconds
plus GDM observation inside the 780-second worker checkpoint. No intermediate
snapshot restore is allowed; this capability is not complete-product acceptance.

### Clean installation journey

`clean_install.py::clean`/`onpc_clean_install::run` compose LIFE04/LIFE02,
fresh Parent defaults, complete Allowed rows and station entry/Cancel in one
product-free attempt. [record_package_journey](../../tests/e2e/package_journey.py)
binds staging/input to the shared recorder; cases contain only plans/checks/callbacks.
[journey_checks](../../tests/e2e/journey_checks.py) supplies independent account/
Allowed-row comparison; completion uses `package_install.check_install_result`.

`gdm-installed-accounts` requires all four fixture personal accounts plus station
and refuses missing/duplicate/disabled/wrong-owner/incomplete observations.
`onpc_parent::launch` can consume fresh `reboot-desktop` proof without changing
its ordinary entry. No in-journey restore occurs. The complete clean-install
binding is qualified on pinned Ubuntu 26.04 English-GDM; other lifecycle/provider
bindings retain separate acceptance.

### Reachability and result checks

Resolve product controls through public IDs, current owner, explicit surface and
canonical actions. Hidden/disabled/detached/busy/modal-blocked targets refuse;
clipping alone needs no focus/scroll. Reveal logically hidden content only when
needed, then reacquire. An API failure never chooses another route.

External adapters retain complete scoped owner/prompt observations and recipient
focus for keyboard delivery. Input/session transitions invalidate snapshots;
result reads are independent. Never call private methods, mutate widgets directly,
read saved policy or equate API success with customer success. Disabled settings
remain readable. Assert meaning-bearing showing content rather than typography.
Missing controls, wrong selection, ineffective settings, timeouts and crashes
remain failures, without fallback that skips assertions or applies policy directly.

[UiObservations](../../tests/e2e/ui_observations.py) runs registered operations as
the fixed fixture user or qualified greeter over guarded transport, returning
sanitized evidence without raw trees, document bodies or account names.
External GI method collisions require explicit qualified interfaces, such as
`Atspi.Text.get_text`. Read-only stale-object retries keep the original deadline;
uncertain actions never replay. Defunct nodes invalidate complete desktop reads
and reset prompt-free stability. External waits dispatch bounded pending public
accessibility events; product waits reacquire API observations.

`AccessibleUI.handle_system_prompt` classifies complete MATE/Shell/gcr/unknown
authentication modals before surrounding input/observations. Every prompt,
ambiguity or incomplete read refuses without secret access, authentication or
dismissal. Prompt absence matters only with a complete positive destination.
Missing prompt-ID maps alone do not veto that observation. GDM credential
checkpoints are separate. Retired coordinate rendezvous and worker entrypoints
refuse before acknowledgement/input.

`JourneyPlan.screen_tags` maps stages to `ui:<operation>`. Controller obtains a
fresh public result, stores it durably and checks ownership before worker reply.
Final reconciliation requires every ordered marker and matching result; prior
evidence or zero exit cannot substitute. Screen evidence is semantic, without
pixel-score or cosmetic authority.

Discovery/customer selection preserves independently captured original switch/
allowance values, including disabled allowance reads, when returning from another
child. Dynamic fixture creation occurs only after fresh visible settings and a
durable phase boundary while Parent remains open. Public canonical UID and
offered-choice checks establish selected identity; popup/highlight state is not
another outcome. This journey changes no time policy or enforcement.

Authentication requires two consecutive fresh acknowledgements of intended label,
hidden account list and sole showing/enabled/focused empty `password text` field.
The second immediately precedes fixed-option `type_password`. Wrong identity/
order, nonempty/unmasked field, review/capture/uncertainty/replay refuse. Active
local greeter and owned session-socket guards remain mandatory.

Product-free GDM observation selects the intended account, observes its prompt,
Escape and fresh graphical return after serial logout. Public logind resolves
the sole active local greeter, including dynamic accounts; validate its runtime/
session socket before dropping privileges. Account rows without public actions
use UI14's qualified navigation with focused-button proof and independent prompt
readback through `onpc_journey::navigate_choice`. This nonsecret observation
does not authorize graphical password submission. Its serial credentials,
command-output, logout/boot/assets/cleanup assertions are harness qualification.

### Station branch diagnosis and default-entry scope

`station_entry_branch` is a read-only diagnosis after one fresh focused station-row
submission. Active local seat/session metadata restricts the observer to the sole
greeter or station; metadata alone cannot establish the destination.

Greeter diagnosis requires station recipient and no password field, reporting at
most twelve showing controls as sanitized categories, roles, ID-presence,
sensitivity/focus. Unknown labels remain unresolved and duplicate known categories
refuse. The English mapping is an unqualified diagnostic candidate; the worker
stops at `greeter-controls` without activating/dismissing a choice.

Station diagnosis requires owned `kiosk-request-window`/`kiosk-request-form`
IDs before `default-request-form`. It authorizes no input and does not qualify
selectors, values, unavailable controls or prompt handling.

Default entry consumes the focused row proof once before Enter, then independently
waits for the active station account and showing/nondefunct owned window/form.
Greeter/foreign/ambiguous session, duplicate/hidden/stale destination or another
branch refuses. No session catalogue/UI15 choice is implied.
`check_e2e_kiosk_entry` qualifies only this observed passwordless default and
fixed disabled-child projection: one form, disabled approver/duration/soft-app/
Request, enabled Cancel, 30-minute selection, disabled-limit notice, absent
mute/custom value. Enabled choices, overlays and authentication retain their
separate catalogue bindings.

### Request-session shortcut results

`station_shortcuts.StationShortcutsJourney` /
`onpc_station_shortcuts::run` registers
`check_e2e_station_shortcuts` in the guarded installed envelope. It pairs
Super, Super+A, Alt+F2 and Ctrl+Alt+T on Jordan's ordinary desktop with the
usable Riley/Jamie request session, normal Cancel and fresh passwordless entry,
then restores the original public policy. Its qualified scope on
`onpc-Ubuntu26.04` and `onpc-Fedora44` is eight results: ordinary overview,
app grid, run dialog and terminal, paired with four request-only station results.
Normal closure, Cancel/fresh entry and exact policy restoration are required.

Fedora has no stock media-keys `terminal` setting. Its working comparison uses
the permanent Ctrl+Alt+T → Ptyxis custom binding supplied to fixed test accounts
by [baseline preparation](../../tests/integration/Environment.md#reusable-preparation-ownership).
Ubuntu retains its existing terminal binding. Qualification reads and exercises
the prepared controls; it does not configure them during the comparison.
The shared adapter recognizes GNOME's unnamed Run dialog by its public
`Run a Command` descendant label and focused editable field, then observes its
normal closure before the next shortcut.
Observed ordinary tuples were Ubuntu Shell `50.1-0ubuntu1.4` and Fedora Shell
`0:50.6-1.fc44`, both `en_US.UTF-8` with `xkb/us`.

The shared input is `onpc_station::shortcut`; its readiness and independent
result use `AccessibleUI.shortcut_operation` through `UiObservations`.
Product form reads use the Application UI API. The finite external adapter
uses English Shell search, Show Apps state, Run a Command and known terminal
application/terminal semantics, with account/session and fresh close-recipient
guards. An absent ordinary positive remains inconclusive. A terminal alone
establishes no full-desktop launch chain; standalone terminal/TTY acceptance
retains its remaining-plan owner. Preserve the
[request-session boundary](../SystemDesign/Kiosk-Confinement.md#request-session-actions).
This shortcut qualification supplies no complete-case credit.
The existing two-second census is not a universal desktop fence. Machine
observations retain finite deadlines inside the 1800-second worker envelope.

After public restoration and fresh usable entry,
`StationShortcutsJourney.check_settings` requires all four ordinary positives,
station `usable_request=True` and `outcome == 'request-only'` for every
station shortcut. The [local composition](E2E-Scenario-Recipes.md#local-desktop-acceptance-composition)
uses this finite verdict.

`tools/test-vm --vm NAME reproduce-station-shortcuts` reuses this journey,
stopping after ordinary Alt+F2 input and before its result observation for
engineering diagnosis. It retains the owned scene after worker cleanup; finish
with `tools/test-vm --vm NAME stop`. It grants no installed acceptance.

### Public desktop selection

`check_e2e_public_desktop_selection` dispatches
[`PublicDesktopSelectionJourney`](../../tests/e2e/public_desktop_selection.py)
through `PublicDesktopSelectionQualification`. Its finite English GNOME 50 GDM binding
uses Jordan's public full-desktop choice and guarded authentication, station
selection during normal passwordless entry, and Jordan's chooser → Cancel →
station sequence. `AccessibleUI.gdm_session_operation` and
`UiObservations.observe_gdm_chooser` own the external-provider mapping, fresh
focus proof and single-use keyboard activation. GNOME's Session menu and its
labelled menu-item ancestors expose focus rather than an accessibility action;
no geometry is used. Label keys describe public actions, not executable identities.
[`public_desktop_observation.observe`](../../tests/e2e/public_desktop_observation.py)
separately binds the runtime desktop ID, resolved desktop-file command, actual
UID/session and manager/compositor processes. Public request controls or Shell
controls establish the destination independently.

Owned saved routing is captured before input and restored only after the two
attempts, with same-run/boot/account and expected-current-value guards. Public
Parent controls enable and restore the representative child's request controls;
fresh passwordless entry, usable choices, Cancel and reentry follow restoration.
New machine checkpoints are bounded to 120 seconds within the existing
1800-second worker envelope. No authentication delay, station credential,
privileged greeter selection or saved-routing mutation manufactures reachability.

The qualified scope is Ubuntu 26.04 and Fedora 44: Jordan's Ubuntu
(`ubuntu.desktop`) or GNOME (`gnome.desktop`) desktop, direct station entry
and ordinary chooser → Cancel → station. Preserve the
[selection boundary](../SystemDesign/Kiosk-Confinement.md#graphical-session-selection).
An unexposed chooser is a target/action no-route disposition, not proof that an
alternate command was denied. Unknown providers, failed positives and incomplete
observations remain inconclusive.

`PublicDesktopSelectionUi.observe` records exposed station Shell as
`full-desktop-gap` and preserves safe exit.
`PublicDesktopSelectionJourney.validate` requires both
`public-direct-result` and `public-carry-result` to be `request-only`
after routing/policy restoration, usable Cancel and fresh entry.
Candidate inputs and commands belong to the
[local composition](E2E-Scenario-Recipes.md#local-desktop-acceptance-composition).

### Graphical service variation

`check_e2e_kiosk_service_variation` dispatches the finite
[`gdm_service_variation.qualify(transport, lease)`](../../tests/e2e/gdm_service_variation.py)
operation through `KioskServiceVariationQualification`, then reuses the existing
REQUEST01/03 normal entry/form/Cancel/return history after restoration.
Its only provider binding is the real GNOME GDM `gdm-autologin` station route,
with dedicated `oh-no-parent-control` Wayland routing, on Ubuntu 26.04 and
Fedora Workstation 44. The
[admission design owner](../SystemDesign/Kiosk-Confinement.md#service-and-routing-boundary)
defines the service/routing boundary; this binding owns its execution witnesses
and restoration.

The qualified scope is actual dedicated app execution on Ubuntu 26.04 and
Fedora 44, with exact settings restoration and public entry/form/Cancel/return.
The caller requires
`result == 'session-created'` and `app_execution_qualified == True`.
The qualified positive reuses `station-default-entry` / `kiosk-request-form`,
the actual Wayland logind session, the owned app service/process and GNOME 50's
`gnome-session-manager@oh-no-parent-control.service` process. GDM's wrapper
arguments alone do not identify the selected session executable.
This slice supplies no general desktop/terminal/SSH protection or complete
usability history; those checks retain their own bindings. A saved default or
GDM command resolution alone is insufficient.

### Saved-routing variation and recovery

`check_e2e_kiosk_routing_variation` dispatches
[`gdm_service_variation.qualify_routing(transport, lease)`](../../tests/e2e/gdm_service_variation.py)
through `KioskRoutingVariationQualification`, then reuses REQUEST01/03 public
entry/form/Cancel/return after restoration. GDM peer `SelectSession` independently
chooses dedicated Wayland with a stale alternate session, empty saved fields or
stale saved `SessionType=x11`, each from the valid baseline. The current binding
explicitly uses `expectation='execution'` and requires actual dedicated Wayland
logind, selected-session process and running app observations for every variation.
An attempt-bound identity diagnostic witnesses the reached account callback;
saved defaults or command resolution alone supply no execution credit.

One real AccountsService discovery outage requires successful installed native admission,
an observed usable public greeter baseline, exact owned service/mask restoration
and ordinary-account routing isolation. The same public greeter readiness check
also separates each restored variation from the next attempt's restart.
The [design owner](../SystemDesign/Kiosk-Confinement.md#service-and-routing-boundary)
records the finite mechanism and limits. The qualified scope is normal and
three varied executions, discovery-independent admission, exact restoration and
fresh public entry/form/Cancel/return on Ubuntu 26.04 and Fedora 44.

### Owned sign-in lease variation

`check_e2e_kiosk_lease_variation` dispatches
[`kiosk_lease_variation.qualify(transport, lease, expectation='recovery')`](../../tests/e2e/kiosk_lease_variation.py)
through `KioskLeaseVariationQualification`. It runs the installed
[`system_kiosk_lease_variation.engineering`](../../tests/integration/system_kiosk_lease_variation.py)
controls before the complete [short public history](#short-confinement-usability-history),
including ordinary-account graphical entry, usable station requests, Cancel,
approval, normal exit and fresh entry. The existing worker deadline is explicitly
1800 seconds; the engineering command is bounded to 420 seconds.

The finite matrix creates one absent lease through real GDM admission in an idle
prepared boot, then checks the same healthy inode and retained handles in both
`gdm-password` and `systemd-user` contexts. Fedora uses the existing `xdm_t` and
`init_t` caller identities and verifies the native shared descriptors are read-only.
Its vendor `systemd-user` account stack can return before the shared module;
that retained control acquires and rechecks its lease through the real session
stack, with session-error refusal for the stale mode. Other bindings acquire
and recheck through account admission.
One owned mode change from `0600` to `0640` must reach native refusal, then the
installed lifecycle writer repairs the same inode before fresh admission.
The retained `refusal` branch characterizes the pre-fix writer refusal.
Exact inode/owner/link/mode guards
restore only this attempt's change. A retained handle rechecks the stale and
restored mode; the real lifecycle `barriers` stays excluded through close until
`pam_end`, then acquires and releases. While that actual writer holds its barrier,
station admission refuses and ordinary-account admission remains usable; fresh
station admission succeeds after release. No lease or removal marker is deleted.

The qualified `expectation='recovery'` scope on Ubuntu 26.04 and Fedora 44
covers writer recovery, retained read-only handles, writer exclusion and fresh
use after release, followed by the complete short public history.
Engineering callbacks are separate from public-use acceptance and supply no
desktop-defense claim.

`check_e2e_kiosk_admission_contention` selects the separate
`expectation='contention'` history through `KioskAdmissionContentionQualification`.
It holds the installed lifecycle writer's barrier, observes the native worker's
matching read-only descriptor and retry sleep, and requires no admission until
release. The same attempt must then succeed within the bounded wait. A persistent
writer must refuse by the deadline while ordinary-account admission stays usable;
fresh kiosk admission follows release. The inode and mode remain unchanged,
without stale-state repair. The same short public history then checks ordinary
graphical login, passwordless requests, denial/Cancel, genuine approval and usable
reentry. This contention history and public-use control passed on Ubuntu 26.04
and Fedora 44, including collection and owned cleanup.

### Temporary identity-helper recovery

`check_e2e_kiosk_identity_helper` dispatches `KioskIdentityHelperQualification`.
Before the [short public history](#short-confinement-usability-history),
[`system_kiosk_admission.identity_helper_recovery`](../../tests/integration/system_kiosk_admission.py)
removes executable bits from the verified installed login helper while the
station is inactive. The real GDM account callback must return an operational
error while the ordinary account remains allowed. A descriptor-bound `finally`
restores the original mode, requiring the same root-owned inode and bytes;
fresh account admission must then succeed. It changes no account, saved routing
or admission state and performs no reinstall.

The engineering command has a 240-second deadline and supplies no public-entry
credit. The existing 1800-second public worker checks ordinary graphical login,
passwordless station entry, denial/Cancel without a grant, genuine approval with
independently observed time, exit and usable fresh reentry.
This finite helper-outage and public-use history passed on Ubuntu 26.04 and
Fedora 44, including collection and owned cleanup. Existing product recovery
needed no change; unavailable-account diagnosis, native error/timeout mapping,
fresh retry and same-handle authorization retain their focused host controls.

### Interrupted configuration recovery

`check_e2e_kiosk_configuration_recovery` binds one same-package configuration
interruption to the existing first-configuration fault owner, followed by the
[short public history](#short-confinement-usability-history) in that same
installation. The selected `pam-ready` wrapper refuses only the exact Malcontent
service-account command after native quarantine and distro PAM activation.
Known original expiry, the owned journal and command witness establish this
controlled history.

Require native refusal while incomplete, ordinary-account isolation, exact
wrapper restoration and supported configuration retry without product-state
deletion. Recovery must preserve the original account/home, expiry, empty
password and selected routing, then permit genuine approval with independent
time readback, exit and usable passwordless reentry. On Ubuntu, require the
package-failure report to be absent before injection; after successful recovery,
validate the newly created report's current package/version and exact injected
exit 79, then mark only its pinned inode seen, preserving its contents. Other
reports and unknown modal refusal remain intact. Ubuntu 26.04 and Fedora 44
passed the complete history and
owned cleanup. Existing product recovery needed no change.

### Entry after a relevant update

`check_e2e_kiosk_update_reentry` binds the maintained genuine Ubuntu v1.2/Fedora
v1.3 prior packages and current candidate through `stage_upgrade_assets` and
`InstalledSetup`. The existing guarded `system_guest` installation/update
commands use the frozen `make install` recipe; shared `Transport.reboot`
independently observes both required boot changes. No installed snapshot replaces
this history. The update verifies current distro PAM and retired legacy-state
absence, preserving ordinary fixture account identities and groups.

[`KioskUpdateReentryQualification`](../../tests/integration/kiosk_update_reentry_qualification.py)
then runs the unchanged [short public history](#short-confinement-usability-history):
passwordless entry, denial/Cancel without a grant, genuine approval with independent
time readback, exit/reentry and public restoration. Shared startup navigation
recognizes the existing release-note surface, verifies its frontend owner and
uses its normal public close action before continuing; note content and links
are outside this check. Both targets passed the complete history, collection
and owned cleanup. No product change was needed; this closes only usability U06.

### Requests after a temporary broker outage

`check_e2e_kiosk_service_recovery` runs
[`KioskServiceRecoveryJourney`](../../tests/e2e/kiosk_service_recovery.py) through
`KioskServiceRecoveryQualification` and the existing confinement-usability worker.
It reuses the attempt-owned runtime mask/stop/restore in
[`system_kiosk_feedback`](../../tests/integration/system_kiosk_feedback.py).
One submission from the ready form must show sanitized Request unavailable
feedback, retain the error-report choice and leave the child's grant empty while
the broker is stopped. The normal result action returns safely to GDM without
sending a report. Owned service restoration precedes an independent public Parent
zero-grant read, fresh station entry and one genuine 75-second approval. The setup
Parent window is closed before the fault and reopened for the time read; its
background polling and error dialogs are not part of this request-only history.
The shared approval oracle checks the resulting time against the requested
extension and elapsed time, rejecting a duplicate grant. Failure restoration and
the outer VM cleanup retain their existing owners; no approval is replayed.
This finite outage/recovery history passed on Ubuntu 26.04 and Fedora 44,
including owned cleanup. No product change was needed; this closes only usability U07.

### Requests with missing optional scenery

`check_e2e_kiosk_optional_artwork` dispatches
[`KioskOptionalArtworkJourney`](../../tests/e2e/kiosk_optional_artwork.py) through
`KioskOptionalArtworkQualification` and
`onpc_confinement_usability::optional_artwork`. Qualified on
`onpc-Ubuntu26.04` and `onpc-Fedora44`, it temporarily hides only the installed
clear-scenery image while the station is inactive. The existing loader and static
background fallback leave fresh passwordless entry and the complete request usable.
One genuine 75-second approval is independently checked in Parent against the
975-second estimate and elapsed time. The
[owned fault helper](../../tests/e2e/optional_artwork_fault.py) restores the exact
image before fresh usable reentry and normal exit; the runner completes VM cleanup.
Reentry checks the current usable form, without comparing its new estimate to a
stale pre-approval balance. This finite engineering qualification adds no
screenshot/style matrix or complete customer-case acceptance. No product change
was needed.

### Reached service-route control

`check_e2e_kiosk_service_route` dispatches
[`su_service_route.qualify(transport, lease)`](../../tests/e2e/su_service_route.py)
through `KioskServiceRouteQualification`, then runs the existing normal public
station entry/form/Cancel/return history. Installed qualification passed on
`onpc-Ubuntu26.04` and `onpc-Fedora44`, including owned runner/VM cleanup.

The bound standard child invokes the real setuid `su --login` for the unchanged
station account with an empty token. Same-invocation native callback entry and
return establish its account refusal; journal observations identify actual
`su-l` on both targets. Independent observations find no station session/shell.
The same child successfully logs in as the ordinary `other-child` fixture through
that service, with guarded single-use private password input and an independent
effective-UID result. Exact owned tracing resources are removed before the
positive and normal passwordless station history. Credentials, shell, vendor PAM
and native module bytes remain unchanged.

The [design owner](../SystemDesign/Kiosk-Confinement.md#service-and-routing-boundary)
defines the narrow service refusal. Its engineering witness requires x86_64,
existing tracefs and readelf on the two named targets. Earlier authentication
refusal remains unqualified and stops this route.
This supplies no general terminal/SSH protection, graphical execution positive,
full usability history.

### Search and standard sign-in contracts

The qualified Ubuntu 26.04 search tuple is Shell `50.1-0ubuntu1.2`,
`en_US.UTF-8`, `[["xkb", "us"]]`; other tuples/query bindings remain pending.
`check_e2e_shell_search` covers administrator SEARCH05 launch/close and standard
SEARCH01/03/04 independently entered unavailable-app readback.
`parent_access.PLAN`/`onpc_parent_access::run` compose the standard
`Oh No! Parent Control` app-grid journey.

`check_e2e_parent_search_launch` qualifies `onpc_parent::open_from_app_grid`
and independently supplied SEARCH06 consumption by `launch_search_result`.
Both require the owned `parent-window`; desktop/stale/wrong-result proof refuses.
UI18 `onpc_window::close` consumes the owned surface proof before one normal
close. `parent_search_closed` requires a prompt-free desktop and complete fresh
absence of management, denial and startup-error windows. FIX02 empty-result
binding remains pending.

`check_e2e_shell_search_results` qualifies Parent SEARCH01/02/03/04/06:
`shell_search_field`, `focus_search_field`, `search_ready`, `search_query`,
`launchable_result` and `focus_search_result` use independent entry and exact
product-result ownership. Unrelated Terminal result refuses. Current composition
types the full query once and closes Overview directly after result verification;
first-character/empty-query checkpoints are not required. This route alone does
not qualify launch or standard-account unavailability.

Standard entry connects only to the canonical other-child's owned bus. GDM07
uses intended-account selection with two fresh standard-specific recipient proofs;
Parent evidence and wrong-account tours cannot substitute. Both proofs require
the exact identity and sole empty masked showing/enabled/focused field. Review,
uncertainty, capture and replay refuse.

SEARCH01 consumes fresh prompt-free desktop proof, submits Super-A once and reads
the showing/enabled/editable empty Overview field. A modal refuses before the
gesture, never triggering dismissal/replay. UI21 consumes its focus reply and
independently observes focus; SEARCH03 consumes that fresh proof, types the full
query once and reads `search-entered`. Uncertainty is terminal.
App-grid acknowledgement opens the next recorder step before its first input.

SEARCH04 composes UI03/UI11. Exact query and usable field stay showing while
complete fresh traversals exclude product launcher/management window for two
seconds inside the 45-second deadline. Missing/defunct subtrees restart stability.
Shell result identity uses the qualified provider; product window identity uses
public IDs. Web suggestions are irrelevant: no result or unrelated results are
valid while the product remains absent, and unrelated results are never activated.
Direct-command denial and time enforcement remain separate.

Prompt middleware only recognizes/refuses MATE, Shell, keyring and unknown modals,
including late arrivals. Routine flows never dismiss automatically.
`cancel_keyring_prompt` is limited to the prepared standard gcr challenge;
`kiosk_mate_cancel` to its exact kiosk/provider binding. They do not authorize
middleware dismissal. Incomplete/ambiguous observations refuse. Provider adapters
qualify each owner/surface independently; never read/supply a keyring password
or mistake another provider's challenge for the intended recipient.

## Existing runtime services

Existing runtime services support blocks within their qualified scope.
Reuse them without a second runner or treating harness checks as customer results.

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
| Interrupted pre-start setup | [system_runner.py](../../tests/integration/system_runner.py): `recover_graphical_cleanup`, through the registered graphical-recovery qualification | Restore a recorded `isolated` attempt only with a null instance ID, powered-off pinned guest, matching run tag, original disk identities, no host sharing and a full baseline proof under the exclusive lease. Reuse outer cleanup; never start the guest or replace the baseline. |
| Reviewed image preparation | [parent_needles.py](../../tests/e2e/parent_needles.py), with its maintained artifact owner | Retained artifact tooling; preparing an image does not qualify an external-provider adapter or a customer result. |

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
 installation/reboot remains a real customer action.
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
[Pointer tests](../../tests/unit/test_e2e_pointer_helper.py) exercise their shared
input boundary. Synthetic fixtures never count as customer coverage.

<a id="lessons-to-preserve"></a>

## Shared adapter constraints

Use the shared adapter for each recurring boundary; keep scenario values and
expected outcomes in recipes.

- Resolve product controls through public IDs, canonical values and the owned
 surface. Clipping alone requires no focus/scroll. Reveal logically hidden
 content only when needed, then reacquire. Never restore generic image,
 coordinate or graphical reattachment routes.
- Provider ownership is independent of desktop readiness. Resolve the unique
 live Shell/provider application with PID/UID/session guards; fullscreen
 overlays need not expose Activities. Reject foreign, ambiguous, nested,
 stale or unexpected modal owners before input.
- Completeness is not atomicity. After account selection, confirm selected UID
 and closed list, discard that snapshot, then read language/readiness afresh.
 Canonical selected UID establishes identity; focus, foreground and popup state
 do not establish the selection result.
- Read-only waits may retry incomplete/transient observations within the
 original deadline. A complete wrong owner/surface, unexpected prompt or
 changed target is terminal. Submit once; permit only the declared valid
 pre-action state while waiting for the exact result. Never replay a mutation,
 close, launch, credential or uncertain input.
- Resolve package format from each verified target baseline. Bind current
 package/fixture/upgrade sources in immutable inputs; snapshot preparation,
 filename/version labels and historical passes do not prove current bytes.
 Verify exact compatibility links separately from regular-file contents and
 refuse dangling or unexpected targets.
- Exercise real toolkit projections and realistic maximum-sized serialized
 observations through both buffered/streamed transport. Keep byte/item/schema
 limits consistent. Toolkit representation belongs to the adapter: collapsed
 content, attachment `DESCRIBED_BY` relations, rich-text attributes and local
 hyperlink offsets must not become case-specific normalization.
- Keep nested command stdout local to its command. Separate bounded progress
 diagnostics from the sole final reply. Readiness must be durably stored before
 releasing one input; failed readiness releases none. Transient success before
 automatic closure needs an active observer; ordinary saved values/readiness
 use final independent readback.
- Compare immutable captures, including nested windows, attachments and format
 projections. A replacement window with identical text is a failure. A request
 estimate alone does not prove issued time. Keep earlier observations and
 calculation timestamps distinct from later label reads.
- Baseline owns persistent desktop idle/accessibility settings; shared entry
 verifies them. Cases add no keepalive input/settings writes and never alter
 tested child expiry. Powered-off status alone does not prove baseline
 restoration; owned recovery retains recorded configuration and identity.
- First-presentation assertions precede generic chooser setup or preference
 saves. Capture before Close/Cancel and independently compare afterward.
 Fresh install/current bytes/one reboot is a different causal history from
 upgrade. Transfer, installation, upgrade and reboot remain distinct operations.
- Internet isolation preserves the attempt's SSH, display/watch and VM identity
 and independently verifies Internet absence/recovery. An infrastructure
 qualification is not app offline acceptance.
- Scope coverage through [UI/E2E allocation](UI-and-E2E-Coverage.md). Keep local
 value/format/control matrices in UI, qualify real entry/refusal separately,
 and retain installed integration outcomes. No external handler or preview
 route is required until the public integration contract actually offers it.
 An unavailable preview needs explicit inapplicability and an unchanged list.
- Observe reset results before restorative input. Dialog draft preservation,
 app-exit reset, source-file mutation, frozen attachment bytes and product
 diagnostic export are separate assertions.

### Composition preflight

Before live qualification, review the changed path from declaration and worker
dispatch through observation, recorder and assertion. Confirm the intended
account/profile, execution order, independent result endpoints and failure stop
before later input. Inspect shared consumers when their contract changes;
unchanged transport, decoding and recording need no renewed qualification.

For a composed approval, trace the actual scoped journey prefix and request
duration through the shared credential binding before the first VM attempt.
Renaming checkpoints does not authorize that secret route. Use the existing
credential-owner check with the real composed prefix; keep its two fresh
recipient proofs and single-use submission. A passing unscoped approval probe
does not exercise a newly prefixed consumer.

Run the smallest existing checks for changed core execution, verdict, credential
or ownership guards. Add a focused regression only for a concrete uncovered
guarantee admitted by the [test scope mandate](../Mandates/Test-Scope-Mandate.md).
Receipt mismatch, replay, failed readiness and concurrent observation checks
belong to those shared owners when affected; they are not a per-case checklist.
Ordinary case data, assertions and composition run through the actual product
test, without a synthetic scenario replay or a new test of the test.

Complete the selected live acceptance in its declared guarded attempts. Preserve
immutable comparison endpoints, observation readiness for transient results,
input guards and owned cleanup. Never combine partial attempts or skip a required result.
Diagnose failures under the [failure contract](../../tests/README.md#handling-test-failures)
at the lowest effective layer. Keep routine attempt details in runner artifacts.

## Retained image artifacts and migration

Retain reports, images and safety regressions as evidence during migration.
Preserve recipient identity, refusal guards, empty-field/focus proofs
and capture restrictions. Use the
[approved screenshot export](../Approval-Tools.md), preserve originals and clean
only named temporary exports with `tools/cleanup-screenshots`.

## Current extension boundary

Discovery reuses installed Parent login, launch and evidence handling. Its two
scoped fixture actions cover dynamic eligible-account creation after an existing
child is visible and a finite no-eligible-account state before Parent launches.
The latter requires exactly the two canonical child accounts to be eligible,
preserves the fixed package request station and refuses unexpected
identity/object sets before mutation. A stage action executes only while the
worker is fresh and before its durable reply; failed workers retain owned
process/callback cleanup for outer restoration. Visible refresh/selection or the
reviewed empty explanation supplies the assertion; no broker/catalog probe can
replace it. Keep qualification in retained runner artifacts.

These development tools activate on their next invocation and change no product
integration or saved-data format.
