# Reusable customer E2E building blocks

This is the contract catalogue for the operations used by customer scenarios.
The [documentation map](README.md) defines document ownership and status terms;
the [execution plan](E2E-Execution-Plan.md) owns task selection and live
completion, while the [recipes](E2E-Scenario-Recipes.md) own exact scenario
composition. Read only the rows required by the selected task.

Every row below records an implementation status. Existing behavior that still
needs extraction, migration or qualification is `pending`, even when an older
scenario run passed. Cases 1, 3, 4, 5, 6, 151 and 193 retain implementations,
behavioral evidence and ready inventory bindings. Retain their helper
regressions while migrating them. Retired E2E IDs 140–150 remain engineering
system-test obligations and cannot be selected by the E2E runner. Current scenario counts come from
`tests/e2e/scenarios.json` and the generated coverage report, not this catalogue.

## How to implement one block

Apply the [UI automation mandate](../Mandates/UI-Automation-Mandate.MD) throughout
this catalogue. Rows marked **Migration required** describe existing mechanisms
to replace before reuse while preserving their behavioral and safety assertions.
A `ready` label applies only to the exact compliant scope named in that row;
older results and unlisted bindings confer no readiness. [Functional
validation](#functional-validation) applies the mandate here. Callable names
locate implementation to inspect, not permission to reuse noncompliant selectors
or input routes. Documentation alone does not establish compliance or a live pass.

The tests exercise customer-facing product behavior and observe the results.
Select users in the app, type into its real approval prompts, operate product
settings, read messages and use windows. Never replace those product actions
and assertions with internal methods, saved-data reads/writes, process inspection,
service checks or synthetic grants. Supporting system operations and launch
routes follow the distinction below. Existing runner
ownership, secret handling, installation setup and cleanup remain supporting
machinery, not customer assertions. Apply the distinction below to each action.

### Environment preparation and customer interaction

Use the simplest reliable supported shortcut, SSH command or public system API
for every operation that does not itself exercise an app feature. Put each
operation in shared libraries, infrastructure or harness code. This includes
Shell/GDM navigation, login preparation, logout, user switching, explicit locks,
reboot/suspend, network changes, clock reads, account/file preparation and
supporting-tool launch. Completed queue tasks and retained code have no exemption.

Routine login goes directly to the intended account through the shared entry
helper. Where real graphical login or unlock is necessary, keep the minimal
selection/keyboard authentication and fresh secret-recipient checks. Wrong-account
visits, repeated prompt entry/Escape and deliberately created keyring challenges
are harness safety qualifications; they are not customer journey prerequisites.

PARENT01 and REQUEST02 invoke the installed commands directly as the active
desktop user. Command execution uses guarded SSH, never Terminal UI merely to
type a shell command. Switch User uses the shared lock/greeter route; logout
uses `gnome-session-quit --logout --no-prompt`. No Quick Settings, power-menu or
logout-confirmation adapter is needed.

Use real GUI input for the product controls and integrations explicitly tested:
app fields and choices, approval prompts, product panel controls, app-grid
discovery, specific enforcement launch routes, file choosers and external links.
A lifecycle or offline scenario tests the product across a system transition;
it does not turn GNOME's controls into features under test. Supporting windows
may be activated or opened directly.

Preserve owned VM/account/session identity, secret safety, single-use input,
uncertain-command refusal and cleanup. Independently observe the system
destination and the app's required public result. System commands cannot inject
product state, grants, usage or outcomes, replace natural expiry with a lock,
or replace graphical PAM denial/retained unlock with an SSH login.

### Block contracts

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
in its row. Repository-owned selectors use public `automation-id` values scoped
to their application and surface. External providers follow the exception in
AGENTS.md; catalogue ID bindings describe the current implementation, not a ban
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
selection, text, window, message or access separately. Retry fresh reads within
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
UI rows that name `automation-id` define the repository-owned and ID-capable
provider route. An explicit external-provider adapter may supply the same
consumer operation through its qualified resolution method while retaining the
row's ownership, ambiguity, focus, input and independent-result guards.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| UI01 | A | Find one control by public `automation-id` within its ID-addressed surface. Resolve clipped controls without requiring viewport visibility; check application-visible/enabled state before input. Reject ambiguity; return a fresh local target. | Registered adapter operations use their scoped ID mappings. Retained generic `target`/`find` and `labelled_button` entry points refuse before traversal. | ready |
| UI02 | A | Read one declared public boolean state from a control first resolved by `automation-id`, such as selected, checked, focused, enabled or showing. Disabled settings remain readable. New surface/state bindings need their consumer's qualification. | `AccessibleUI.has_state`, `showing`; ID-addressed selector scope only. | ready |
| UI03 | A | Resolve one registered public `automation-id`, then read its bounded nonsecret text projection from a showing label, field or document. Inputs: surface/ID, maximum characters, expected projection and deadline. Text, names and roles verify meaning after lookup and never identify the node. Return a bounded semantic value or match result, never arbitrary document text. Reject masked fields before accessing Text. | Registered `read_label`/`read_document` paths resolve their roots by ID; bounded descendant meaning checks reject ambiguous text projections. Generic name/role selectors refuse. Other projections remain pending. [Parent discovery contracts](#parent-discovery-block-contracts), [About contracts](#about-block-contracts) and [search contracts](#search-and-standard-sign-in-contracts). | ready |
| UI04 | A | Resolve one fresh control by public `automation-id` and invoke its qualified public action once. Require application-visible, enabled and nondefunct state; viewport clipping alone does not refuse input. No preliminary focus, reveal or repeated traversal. Return input completion, not the claimed customer result. | `AccessibleUI.activate_id` / `activate_provider` resolve ownership, prompts and target in one fresh scoped snapshot; `_invoke_target` invokes the action without another traversal. | ready |
| UI05 | A | Send one declared normal key/chord to an already qualified, focused recipient, such as Enter, Escape, Tab, Home, Down or Super-A. Repository-owned recipients use `automation-id`; an external recipient uses its qualified provider adapter. Reacquire and verify the recipient immediately before input. | Existing workers' `testapi::send_key` require a fresh scoped recipient proof before reuse; secret entry is excluded. | ready |
| UI06 | A | Type one nonsecret string once at a declared bounded pace into the intended, focused input surface. Repository-owned inputs use `automation-id`; an external input uses its qualified provider adapter. | Existing workers' `testapi::type_string` require a fresh scoped recipient proof; `onpc_parent::enter_search_query` retains its bounded pace after migration. | ready |
| UI07 | A | **Retired.** Geometry-based resolution has no executable route. Use UI01 and semantic input; no execution exemption. | Retained `AccessibleUI.pointer_target`, `pointer_glyph` and `stable_pointer` entry points refuse before traversal or geometry access. | retired; safely refused |
| UI08 | A | **Retired.** Coordinate clicking has no executable route. Use UI04 or qualified ID-addressed keyboard input; uncertain input still refuses. | Retained `onpc_journey::click_target` and `onpc_pointer::click` entry points refuse before backend, image or input access. | retired; safely refused |
| UI10 | A | Wait for a read-only public predicate within its deadline, dispatching pending accessibility events and reacquiring stale objects. | `AccessibleUI.wait`; the predicate must contain no input. | ready |
| UI11 | A | Observe absence of an explicit `automation-id` within an otherwise positively ID-addressed surface. Bind `snapshot` or `stable` mode explicitly. Both require complete fresh reads; stable mode additionally requires its declared finite interval and deadline. | Existing absence/window-closure paths must use registered IDs for both the absent target and surrounding surface. Incomplete/defunct reads cannot prove absence; stable reads restart their interval. [Search contracts](#search-and-standard-sign-in-contracts), [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| UI12 | A | Compare explicit sanitized observations with an explicit expected value or earlier observation; report the differing approved fields. No hidden initial/new-child slots. | `SettingsObservation.from_settings` freezes sanitized values; `compare_settings(observed, expected)` compares explicit immutable observations and reports only differing field names. `JourneyPlan.settings_checks` owns expectations and prior-stage references. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI13 | A | Observe a bounded public collection of children first resolved by stable public IDs: canonical identities/order, matching window count, or displayed row set. Inputs declare the ID-addressed root, projection, maximum and expected cardinality (including zero). Order may be verified as a result but never used as identity or to calculate input. Require complete fresh traversal for exclusion/count claims; reject duplicate IDs and unknown requested targets. | Existing `choice_order`, greeter and child-picker collection paths require migration wherever names, roles or positions discover children. Harness and [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI19 | A | Type one fixture secret once through the unchanged secret-safe API for one challenge whose surface, recipient and empty masked field were freshly resolved by owned public IDs or a qualified external-provider adapter. Accept a registered secret reference and explicit recipient proof, never plaintext in stage data. Do not submit or infer authentication success. Capture remains sealed and uncertainty/failure forbids replay. | `onpc_password::type_fixture_secret` consumes one proof from `enter_gdm_challenge`; distinct Parent GDM challenges are qualified by `check_e2e_challenges`. Used identities and the terminal failure latch never reset. Serial retains its separate proof binding; other graphical surfaces remain pending. [Challenge contract](#refactoring-the-established-cases). | ready |
| UI20 | A | **Migration required.** Perform the declared double-click gesture through a supported ID-addressed public route; no coordinates or substitution with a different gesture. An unavailable route blocks the consumer. Record it as one intended gesture; no retry or click repair. | Existing normal pointer API; new consumer is E2E-014. A disabled/hidden target cannot authorize a gesture. This is not two separately retried click blocks. | pending |
| UI23 | A | Request one public reveal operation for required content observation, or when a direct public action is unavailable. A clipped but directly actionable control does not need reveal. Resolve a nondefunct object by ID without an initial visibility requirement; return input completion only. | `AccessibleUI.reveal_id` resolves the target and its owning surface by ID, invokes the registered semantic focus action and independently reacquires the showing target. Generic `scroll_target`/`reveal` refuse. Qualified for Parent remaining-time/filter controls and About license/footer. [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| UI24 | A | Resolve the editor by public ID, read the public formatting attributes of one explicit bounded synthetic text range and compare the expected format. Return semantic attributes only. | New FEED04 consumer using the ID-addressed editor's public accessibility Text attributes. A pressed toolbar button alone does not prove text formatting; unavailable attributes block that assertion. No DOM or saved-draft read. | pending |
| UI25 | A | Start one bounded read-only public-state trace for registered `automation-id` selectors; return its explicit observation token after readiness. No customer input. | New leaf extracted from UI22; E2E-035/039/046 consumers. | pending |
| UI26 | A | Finish that trace at its supplied ID-addressed public terminal predicate/deadline and return ordered semantic samples. No input, replay or private reads. | New leaf extracted from UI22; accepts only the caller's explicit token. | pending |
| UI27 | A | **Migration required.** Reveal hover information through a supported ID-addressed public route. A specifically tested hover gesture requires such a route or blocks its consumer; no coordinate input. | Existing normal pointer interface; PANEL03 consumer. | pending |
| UI28 | A | **Migration required.** Open the ID-addressed target's context menu through public semantic action or qualified keyboard input. A specifically tested secondary-click gesture requires a supported ID-addressed route or blocks its consumer. No coordinates or implicit menu selection. | Existing normal pointer interface; PANEL01 consumer. | pending |
| SEC01 | A | Preserve fresh intended-recipient, focus, empty masked field, capture and single-use secret checks for unavoidable graphical authentication. Wrong-recipient rejection is a harness safety test. | `AccessibleUI.password_recipient`; shared `onpc_password` input. Routine entries never visit a wrong account. | pending; prepared recipient checks qualified |
| SEC02 | A | Resolve the intended fixture account for minimal shared greeter entry. Reject ambiguous or wrong ownership before input. | `AccessibleUI.gdm_nonsecret_navigation`; direct focus then Enter without an unrelated account visit or menu tour. Harness qualification owns negative-entry exercises. | pending; prepared selection checks qualified |
| UI09 | C | Reveal required content, or a target without a direct public action, by public `automation-id`; reacquire the same ID and observe the result. Never prepend this composite to an available direct action. | `AccessibleUI.reveal_id` performs the optional UI23 input and fresh `id_target` lookup (UI01/UI02). Generic `reveal`, `scroll_target` and `target` refuse. Parent content/filter and About license/footer scope; other IDs need their consumers. [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| UI14 | C | Highlight one choice through semantic focus with a fresh focus observation. Repository-owned choices use `automation-id`; external choices use their qualified provider adapter. Verify identity and focus/selection before committing; never calculate key counts from list order. | `onpc_journey::highlight_choice` accepts only the adapter's fresh semantic-focus evidence; its retained generic positional-navigation branch refuses. `AccessibleUI.gdm_nonsecret_navigation` is installed-qualified for the prepared Parent, other-parent and station rows; `gdm_product_free_navigation` separately qualifies Parent on the declared product-free baseline. Other GDM and product-owned bindings require their own qualification. [Parent discovery contracts](#parent-discovery-block-contracts). | pending; prepared installed and product-free GDM bindings ready |
| UI15 | C | Select one ID-addressed value from an ID-addressed dropdown, menu or visible choice group. The registered control kind and commit route are explicit; independently verify the resulting selected value. | Existing child-picker paths require public IDs for the picker, each choice and selected-value projection; labels remain result data only. REQUEST04's `AccessibleUI.select_kiosk_account` qualifies station child/approver selectors through direct public button actions and exact offered sets. Other dropdowns/groups remain pending. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| UI21 | C | Focus one showing, enabled nonsecret field through public semantic focus or qualified keyboard navigation; independently require the same field to be focused. Repository-owned fields use `automation-id`; external fields use their qualified provider adapter. | `AccessibleUI.focus_search_field` and `search_ready(focused=True)` qualified fresh Parent SEARCH02 in `check_e2e_shell_search_results`. Other bindings require their own scoped resolution and fresh focus readback; ambiguous routes refuse. Rich-text binding remains pending. [Search contracts](#search-and-standard-sign-in-contracts). | pending; fresh Parent search focus ready |
| UI16 | C | Replace text in one named nonsecret field: focus, select all, type once, then read the exact result. Empty input explicitly means clear. | UI21 → UI05(Ctrl-A) → UI06(value), or UI05(Backspace) for empty → UI03(exact value, including zero length). Selecting all alone does not clear a field. Register field-specific projections with their consumer. | pending |
| UI17 | C | Set one named toggle to an explicit boolean. Read first, activate once only when different, then independently require the desired state. | `AccessibleUI.set_toggle` through `ParentToggleJourney` / `onpc_parent_toggle::run`. `tools/run-tests integration check_e2e_toggle` qualified Parent's `parent-screen-limit-toggle`: explicit child selection, enable/disable, already-current without activation, wrong/hidden-control refusal and disabled-settings read, with owned cleanup. Hidden controls may be retained or omitted from the complete public tree. First complete consumer E2E-017 case 57 and all other toggle bindings remain pending. | pending; Parent binding qualified |
| UI18 | C | Close a qualified window with its public Close action or Alt-F4. Repository-owned windows and controls use `automation-id`; external windows use their qualified provider adapter. For keyboard close, first verify that same window is active. Observe its disappearance and the qualified underlying surface. | `onpc_window::close(journey, window, proof)` consumes a fresh registered proof, sends Alt-F4 once and independently observes the destination. Parent→desktop passed `check_e2e_parent_search_launch` with an active owned `parent-window` proof and complete absence/desktop readback. License→About, About→Parent and management denial→standard desktop retain their consumer evidence and extracted-helper host checks. [About contracts](#about-block-contracts). | pending; Parent→desktop binding ready, other extracted bindings await live validation |

| UI22 | C | Bracket a declared caller-owned input with public-state observation. Start before input and finish at the supplied result/deadline; do not infer a transient from the final state. | UI25 → caller's explicitly listed input → UI26. `watch` is this composition, not a hidden callback that performs extra actions. | pending |

### Sign-in and desktop entry

Account parameters are a closed set of provisioned fixture roles, not arbitrary
usernames. The public-UI connection must be qualified for the selected greeter
or desktop. Extending the current fixed Parent/other-child routing is part of
the affected entry block; that connection metadata supplies no product evidence.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| GDM08 | A | Observe the selected account label, focused showing password role and hidden account list. This is a nonsecret prompt observation only; it cannot authorize password input and never reads password contents. | `AccessibleUI.greeter_prompt()` uses the scoped semantic GDM adapter to resolve the sole greeter, exact prepared recipient and protected password node while rejecting visible account rows. `check_e2e_gdm_recipient` installed-qualifies the Parent prompt; `GdmProductFreeJourney` / `check_e2e_gdm_product_free` qualifies the same protected Parent prompt on the declared product-free baseline. Focused tests reject wrong/duplicate recipients, missing/duplicate/unfocused/nonempty/unmasked fields and list overlap without traversing or reading password text. | pending; prepared installed and product-free Parent prompts qualified |
| GDM03 | A | Read the intended GDM recipient's identity and sole showing, enabled, focused, empty masked field with the account list hidden. Read character count only, never password content. | `AccessibleUI.password_recipient(name)` uses the same protected semantic snapshot and reads only `Text` character count. `onpc_gdm::recipient_qualification` obtains two fresh Parent proofs for one challenge; the installed qualification also proves the prepared other-parent recipient and refuses it as Parent. Other accounts and prompt surfaces remain unqualified. | pending; prepared Parent/other-parent bindings qualified |
| GDM01 | C | Observe the usable greeter and its account list, with no active password prompt. | `AccessibleUI.gdm_nonsecret_account(name)` retains the installed Parent/station cardinality contract for ordinary-account entry. Station entry and `kiosk_gdm_returned` require only the usable station row; locked, absent or differently named parents do not gate station access. Task 024 retains live requalification for that revised station scope. `gdm_product_free_account()` separately requires the declared Parent row and excludes the station from one complete product-free list. `GdmProductFreeJourney` / `check_e2e_gdm_product_free` qualifies two independent product-free list/return cycles; wrong fixture shape, owner, duplicate, stale and list/prompt overlap paths refuse. Other ordinary accounts and surfaces remain unqualified. | pending; prepared installed and product-free Parent list bindings qualified |
| GDM02 | C | Select a named user on the logon screen. Use UI14's qualified provider navigation, verify focus before Enter, then observe the declared password prompt, retained lock or passwordless station. Do not type a password. | `AccessibleUI.gdm_nonsecret_navigation(name)` retains the installed account/station route. `gdm_product_free_navigation()` separately focuses and freshly verifies Parent on the declared station-free fixture before `onpc_gdm::product_free_qualification` sends one Enter. `check_e2e_gdm_product_free` qualifies two independent Parent entries; installed Parent/other-parent/station bindings remain separately qualified. Other accounts, retained locks and session choices remain unqualified; positional Home/Down calculation stays retired. | pending; prepared installed and product-free Parent bindings qualified |
| GDM09 | C | Dismiss an already observed GDM password prompt with one Escape and independently observe the account list again. No secret is typed. | `onpc_gdm::product_free_qualification` consumes each scoped prompt proof before one Escape and obtains a fresh `gdm_product_free_account()` returned-list proof; `check_e2e_gdm_product_free` qualifies both independent cycles. The installed qualification separately covers the prepared other-parent and Parent prompts. Retained locks and other prompt surfaces remain unqualified. | pending; prepared installed and product-free Parent bindings qualified |
| GDM04 | C | Harness safety qualification only: prove that another recipient cannot authorize an intended fixture secret. Never compose this negative exercise into customer sign-in. | `onpc_gdm::recipient_qualification`; wrong-recipient unit regressions. | ready; harness only |
| GDM05 | C | Deliver the intended fixture password once to an already selected prompt after two fresh ordered recipient checks. Do not submit or infer success. No wrong-account visit is a prerequisite. | `onpc_password::enter_gdm_challenge` binds two fresh proofs to each declared challenge through `JourneyPlan.challenges` and `onpc_journey::declare_challenges`. `check_e2e_challenges` qualified two Parent authentications separated by shared DESK04 logout, independent desktop results and wrong-entry refusal, with durable assertions, reconciliation, private collection and owned cleanup (run `20260924T192200Z-c833e973`). Compatibility entries remain `enter_parent_gdm_password` / `enter_standard_gdm_password`. Other challenge recipients and surfaces remain pending. | pending; distinct Parent GDM challenge binding ready |
| GDM06 | C | Observe the declared access result at GDM or lock: usable intended desktop, or time-limit rejection with its explanation and no desktop access. A generic failed login is not the expected denial. | Shell desktop, lock and denial-surface IDs are not qualified. | pending |
| GDM07 | C | Shared minimal fresh graphical entry for the intended fixture account with declared success or product time-limit denial. Retained targets use unlock. | `journey_blocks.fresh_desktop` and `onpc_parent::sign_in`: intended account focus/Enter → fresh GDM03 proofs → GDM05 → Enter → GDM06/DESK01. `ProductFreeEntryJourney` / `onpc_product_free_entry::run` qualify the product-free Parent binding; see [qualification scope](#product-free-parent-entry-and-command-context). No wrong-account visit or prompt-cancellation tour. Preserve real graphical PAM enforcement. | product-free Parent success ready; other unqualified bindings pending |
| GDM10 | C | Retired duplicate legacy Parent sign-in. | Consumers reuse shared GDM07; no separate provider qualification or implementation task. | retired |

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
| DESK01 | C | Observe a usable desktop for the explicitly selected fixture; require its normal Shell controls. | `AccessibleUI.standard_shell_desktop(no_prompt=True)` uses the bound fixture session bus, one complete scoped Shell snapshot per read, unique showing enabled Activities control and complete unknown/authentication-modal refusal. `check_e2e_fresh_desktop` independently qualified fresh Parent and standard desktop results over two seconds in separate restored attempts. `check_e2e_desktop_keyring` additionally qualified `cancel_keyring_prompt` on a prepared real standard-account gcr challenge, followed by disappearance and an independent two-second desktop readback without replaying login input. Lock, retained-session and other Shell surfaces remain pending. | pending; fresh Parent/standard desktop and prepared standard gcr Cancel return ready |
| DESK02 | A | Retired Shell system/session-menu automation. These menus are not product features. | Use shared DESK03/04/05 and LIFE02/03/06 system operations. No menu adapter to qualify. | retired |
| DESK03 | C | Lock and switch to the greeter while retaining the fixture desktop. Independently check the original session and usable GDM destination. | `session_control.observe` uses the bound user's public ScreenSaver lock and GDM switching API over guarded SSH; `onpc_desktop_session::switch_user` then observes GDM01. `check_e2e_desktop_session` qualified a fresh installed Parent entry, one switch, independent source locked/inactive readback and usable GDM through `onpc-v1.1`, then requalified it in a separate restored attempt alongside DESK04; private collection and owned cleanup passed (run `20260923T170614Z-02c46f60`, now outside runner retention). No Quick Settings. Other fixture bindings and retained-window behavior remain pending. | pending; fresh Parent switch binding ready |
| DESK04 | C | Log out the bound fixture desktop and independently check that its session ended and GDM is usable. | Shared `session_control.observe` invokes `gnome-session-quit --logout --no-prompt` once as the bound user over guarded SSH, verifies the source session disappeared and a greeter session is active; `onpc_desktop_session::log_out` then observes usable GDM01. `check_e2e_desktop_session` qualified a fresh installed Parent desktop, direct logout and independent GDM result, then requalified DESK03 in a separate restored attempt; private collection and owned cleanup passed (run `20260923T170614Z-02c46f60`, now outside runner retention). No logout-dialog/Cancel or forced-termination fallback. Other fixture bindings remain pending. | pending; fresh Parent logout binding ready |
| DESK05 | C | Explicitly lock through Super+L or the supported session lock API and independently observe the lock surface. Never manufacture natural expiry. | Shared `session_control` lock binding or one bound shortcut → DESK06. No system-menu navigation. | pending; command implemented, lock-surface qualification required |
| DESK06 | C | Observe the intended user's lock challenge. Input declares curtain or already-open challenge; reveal with one normal key only for curtain. | UI05 only for curtain → UI01 → UI02(identity and password challenge). Never submit an empty challenge to reveal it. | pending |
| DESK07 | A | Qualify the lock-screen recipient, masked empty focused field and intended identity independently of GDM. | New public-UI recipient adapter; reuse secret-boundary rules, not GDM evidence. | pending |
| DESK08 | C | Attempt normal unlock with an explicit expected success or time-limit denial. | DESK06 → DESK07 twice → UI19 → UI05(Enter) → GDM06. | pending |
| DESK09 | C | From another usable desktop, visit a specified retained user's desktop without replacing it. Inputs include target account and expected unlock result. | DESK03 → GDM02(destination=lock) → DESK08. Fresh entry explicitly uses DESK03 → GDM07 instead. | pending |
| DESK10 | C | Activate a named existing window with the simplest reliable public focus action or bounded shortcut, then verify that window is active. | Shared ownership-scoped window adapter; no mandatory app-switcher tour, logout or relaunch. | pending |
| DESK11 | C | From an observed locked fixture session, use the shared greeter-return command; from an observed rejected GDM prompt, use Escape. Preserve the denial observation before leaving and independently require the usable account list. Select the route from the declared source; never try alternatives after uncertain input. | Locked desktop: `session_control.observe` with the bound `return-greeter` action preserves the locked session and invokes GDM's public API without another Lock. Rejected GDM: fresh provider observation → UI05(Escape) → GDM01. No lock-screen Switch User button or menu navigation. | pending |
| DESK12 | C | Expose a named Shell panel control from a previously observed unlocked desktop, including fullscreen gameplay. Input declares already-showing or a qualified normal reveal sequence. | UI05 for reveal when declared → DESK01 → UI01 → UI02(control). The app publishes `child-request-button` and `child-countdown-animation-toggle`; installed reveal/consumer qualification remains pending. Do not require hidden panel controls before reveal. Qualify fullscreen with E2E-024. | pending |

### App-grid search and Parent launch

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| SEARCH01 | C | Open the app grid/Overview with Super-A and observe an enabled, editable, empty search field. | `AccessibleUI.shell_search_field` resolves the sole showing, sensitive, editable field inside one complete, uniquely owned Shell snapshot. Fresh Parent entry qualified in `check_e2e_shell_search_results`; independent standard-account entry qualified in `check_e2e_shell_search`. [Qualified scope](#search-and-standard-sign-in-contracts). Other routes remain pending. | pending; fresh Parent/standard branches ready |
| SEARCH03 | C | Enter an app-name query into an already open, empty, focused search field without launching: type the first character, read it, type the remainder once, read the exact full query. | `AccessibleUI.search_query` qualified fresh Parent split-query readback in `check_e2e_shell_search_results`; independent standard-account split-query readback qualified in `check_e2e_shell_search`. [Qualified scope](#search-and-standard-sign-in-contracts). Other queries remain pending. | pending; Parent/standard query branches ready |
| SEARCH04 | C | Observe the declared search result after scoped provider resolution: a launchable app, or the exact query-specific web suggestion with stable absence of the app launcher and management window. Repository-owned windows retain their IDs. | `AccessibleUI.launchable_result` qualified the unique showing, sensitive Parent result and unrelated-binding refusal in `check_e2e_shell_search_results`. `AccessibleUI.search_absence` qualified the standard-account exact web description and two-second complete launcher/window absence in `check_e2e_shell_search`. [Qualified scope](#search-and-standard-sign-in-contracts). Other apps remain pending. | pending; Parent launchable and standard unavailable branches ready |
| SEARCH06 | C | Open Overview, resolve the empty search field by a qualified provider adapter, semantically focus it and independently observe focus before typing the registered app name once. Read back the complete query, then resolve and focus its launchable result. Independently observe result focus and stop before Enter. | `onpc_shell_search::run` and `AccessibleUI.focus_search_result` qualified fresh Parent split-query entry through observed result focus, then dismissal without activation, in `check_e2e_shell_search_results`. The whole-query route passed in case 3 (run `20260922T212944Z-ad23b979`, subject to runner retention). [Qualified scope](#search-and-standard-sign-in-contracts). Other entries and queries remain pending. | pending; fresh Parent whole/split-query branches ready |
| SEARCH05 | C | Launch a named app from the app grid and observe its expected opening window. The search route is an explicit argument. | `onpc_parent::open_from_app_grid` composes SEARCH06 and `launch_search_result(journey, proof, expected)`. Both the composed administrator launch and independently supplied `app-grid` management entry passed `check_e2e_parent_search_launch`, with owned window readback, normal close and wrong-entry refusal. Host checks cover wrong/stale proofs, wrong owner/result and uncertain-input non-replay. FIX02's `fixture-requested`→empty commit remains host-checked pending live validation. [Qualified scope](#search-and-standard-sign-in-contracts). | pending; administrator management bindings ready |
| PARENT01 | C | Invoke `oh-no-parent-control-parent` directly as the active desktop user and independently observe the declared management window or access denial. Mandatory for ordinary Parent setup/reopening; no child is selected implicitly. App-grid discovery tests explicitly use SEARCH05/06. | `onpc_parent::launch` consumes the desktop proof, submits the fixed command through `AccessibleUI.launch_parent_command`, then observes `parent-window` or `management-denied`. `check_e2e_terminal_provider` qualified the fresh standard denial/return binding; complete case 6 requalified that binding, specific denial, management exclusion and desktop return in run `20260923T193956Z-9e1b6eac`. The fresh Parent desktop binding also passed in case 151. No terminal/search input. [Qualified scope](#about-block-contracts). | ready for fresh Parent/standard bindings; other entries pending |
| PARENT02 | C | Select a child from Parent's dropdown, verify the intended selected identity and wait for that child's controls. | `onpc_parent::select_child` accepts an explicit opened-list reply and registered child/stage binding, uses UI14, consumes fresh highlight evidence, sends Enter and observes `AccessibleUI.selected_child`. Child/existing/new/returned bindings only. [Parent discovery contracts](#parent-discovery-block-contracts) and [About contracts](#about-block-contracts). | ready |
| PARENT03 | C | Read the current selected child's identity, screen-limit switch, allowance and remaining-time section as a sanitized observation. Do not change selection; disabled allowance controls remain readable. | `AccessibleUI.settings(child)` reads the explicit child, switch and duration-label projection and reveals the remaining-time section. Scenario expectations remain in `parent_discovery.PLAN`, not the adapter. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| PARENT04 | C | Select Screen Limits or App Limits and require that page's named usable controls. | `AccessibleUI.parent_page(child, page)` checks the displayed child, selects one named page, then observes its controls. Reacquire the window after transition and reuse that local root for search/filter reads. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |
| PARENT05 | C | Open the daily-allowance picker and, when requested, its Custom amount editor. | UI01 → UI04 → optional UI04(Custom amount) → UI01. | pending |
| PARENT06 | C | Choose a daily preset or type a custom allowance and commit through the normal UI. Return the displayed value/validation; saving is observed separately. | Preset: PARENT05(picker) → UI04(preset) → UI03. Custom: PARENT05(custom editor) → UI16(value); `commit=pause` adds no input, `enter` uses UI05(Enter), `focus-leave` uses UI05(Tab); then UI03(value/validation). PARENT08 independently observes saving. | pending |
| PARENT08 | C | Observe loading, saving, saved, validation or unavailable state and availability of conflicting controls. Snapshot mode waits for the named result; transition mode surrounds the triggering input with a bounded trace. | `AccessibleUI.parent_save_snapshot` through `ParentToggleJourney` / `onpc_parent_toggle::run`. `tools/run-tests integration check_e2e_parent_save` qualified enabled/disabled saved snapshots, a fresh independent Parent observation, wrong-child refusal and owned cleanup. Each complete snapshot verifies the selected UID and its nested public label, rejects visible error reports, and requires the expected switch and selector availability. First complete consumer E2E-017 case 57, other result states and UI22 transition tracing remain pending; a terminal snapshot makes no transient-saving claim. | pending; saved/control snapshot binding qualified |
| PARENT20 | C | Read an already expanded, showing remaining-time explanation for the explicitly selected child. Return daily, one-time and total values, public display precision and observation time. Perform no navigation or expansion. | UI01(child and explanation) → UI03(each declared balance). UI12 owns arithmetic/elapsed comparisons. Split from PARENT09; first consumers E2E-005/048. | pending |
| PARENT09 | C | Reach the selected child's remaining-time explanation, expanding it only if currently collapsed, then read its balances. | UI01 → UI02(expanded) → UI04 only if collapsed → UI09 → PARENT20. Repeated reads must not collapse the section. Use PARENT20 when an observer must be read-only; neither block visits another user's desktop implicitly. | pending |
| PARENT12 | C | Read a displayed app row's identity, access choice and match choice. | UI01 → UI02 → UI03. No installed-catalogue or executable probe. | pending |
| PARENT10 | C | Search the App Limits catalogue by name, description or launcher identifier and observe the matching displayed rows, including an explicitly expected empty set. | PARENT04(App Limits) → UI16(search) → UI13(rows) → UI12(expected set). Row details use PARENT12 separately. | pending |
| PARENT11 | C | Set one named App Limits filter's explicit selection set and observe the exact displayed result set. Both access-rule and match-rule popovers use independently checked options. | UI01 → UI04(open) → UI17 for each declared option → UI05(Escape) → UI11(popover) → UI13(rows) → UI12(expected set). Same implementation for both filters. | pending |
| PARENT13 | C | Open a named app's Edit Match Rule dialog and read its current rule. | UI01 → UI04 → UI01 → UI03. | pending |
| PARENT15 | C | Apply Save, Cancel or Reset to the open match editor and observe the explicitly expected result. Empty/unrelated precise text stays in the editor; a rejected wildcard closes it and opens a failure report. Do not close that report implicitly. | UI04(response) → PARENT08; saved/cancelled: UI11(editor) → PARENT12 → UI12; invalid draft: UI03 → UI02(editor); failed save: UI11(editor) → UI01(report) → UI03(public error). Caller uses FEED15 or UI18 for report review/close before reading restored rows. | pending |
| PARENT16 | C | Choose Allowed, Hard blocked or Soft blocked for one displayed app; observe save and displayed choice. | UI15(access choice group) → PARENT08 → PARENT12. | pending |
| PARENT17 | C | Open revocation confirmation and read its target and warning about time, blocked apps and daily allowance. | UI01 → UI04 → UI01 → UI03. | pending |
| PARENT18 | C | Cancel or confirm the open revocation dialog and observe its closure and displayed time/settings. Child effects are checked by later app/access blocks. | UI04 → UI11 → PARENT08 → PARENT03. | pending |
| PARENT19 | C | Observe Parent's no-eligible-child explanation together with the `(None)` picker placeholder. Never activate the disabled picker. | `AccessibleUI.parent_empty()` reacquires the Parent window and showing picker, then uses UI03's registered projections for the explanation and sole `(None)` label in one bounded read-only wait. [Parent discovery contracts](#parent-discovery-block-contracts). | ready |

### Kiosk, child overlay and the shared request form

One shared set of form blocks takes `surface = overlay | kiosk`. Child selection
is fixed/read-only in the overlay and selectable in kiosk. Different destinations
and recipient checks are explicit; duplicate surface-specific implementations
are unnecessary.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| AUTH01 | A | Qualify the real approval prompt's selected parent, displayed request/child/duration/app choice and sole empty masked focused field. No password contents or product authorization calls. | New public-UI contract over the actual system agent; preserve the [secret boundary](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary). | pending |
| AUTH02 | C | Approve, enter a declared wrong fixture password, or cancel authentication. For input, freshly qualify the same challenge twice and submit once. Observe acceptance, explicit rejection or dismissal; REQUEST11 separately reads the form result. | AUTH01 twice → UI19 → UI05, or UI04(Cancel) → UI01 → UI03 → UI11 as appropriate. A rejected prompt may need its normal Cancel action to return; never infer denial from timeout. A later retry needs a new challenge. | pending |
| AUTH03 | A | Validate the administrator authority, owned VM and verified input for one registered package command. | `PackageCommand.validate_input` and `guest_submit` bind `install-staged-package` to verified FIX04 bytes, the active local Parent administrator and the owned transport attempt; [qualification](#administrator-package-command-and-output). No Terminal or unrelated administrator-password challenge. Product approval authentication remains AUTH01/02. | fixed install binding ready; other package bindings pending |
| REQUEST01 | C | Enter the dedicated request station from GDM through shared minimal account selection and observe its request form. | `journey_blocks.station_entry` / `onpc_gdm::enter_station` reuse `AccessibleUI.gdm_nonsecret_navigation`, consume one fresh focused-station proof before Enter, then independently require the active station owner and one showing owned window/form. The passwordless destination was qualified on the prepared Ubuntu 26.04/English-GDM/baseline-keyboard image with GNOME Shell `50.1-0ubuntu1.2`. `check_e2e_kiosk_eligible_choices` qualified direct composition after Parent preparation and shared Switch User. Station navigation requires the station row, without a named-parent prerequisite. This route and Cancel/GDM/reentry after locking all eligible parents passed `check_e2e_kiosk_fixtures` in run `20260924T173358Z-94d5db62`; the affected no-child route passed `check_e2e_kiosk_no_child` in run `20260924T173643Z-8d742069`, both with collection and owned restoration. Routine entry never visits another account. | ready |
| REQUEST02 | C | Open or deliberately reopen the child overlay by direct `oh-no-parent-control-child` invocation as the active child desktop user; observe one usable form and fixed child identity. Mandatory for ordinary overlay entry. | DESK01 → `AccessibleUI.launch_child_command` (`child-command-launch`, fixed command, one submission) → UI01 → UI02 → UI13(form count=1) → UI03(fixed child). The command input has host safety coverage; form observation and installed qualification remain pending. Repetition is deliberate customer input, not retry. | pending |
| REQUEST03 | C | Read a form's child, approver, duration, custom text, soft-app choice, controls and messages; observe the absence of mute in the current release. Require exactly one showing form and the fixed child in overlay. | UI13(form count=1) → UI01 → UI02 → UI03. `AccessibleUI.kiosk_request_form` retains the installed-qualified disabled-child projection. Its `enabled=True` binding also qualifies default 1800-second duration, selected child/approver IDs, enabled controls and absent disabled notice/mute/custom value. `RequestObservation.from_request` validates immutable operation-specific expectations. `check_e2e_kiosk_eligible_choices` independently reread both selections in run `20260923T204614Z-0601b77a`. Other durations, numeric estimates, account profiles and overlay scope remain pending. | pending; default-duration disabled/enabled kiosk projections ready |
| REQUEST04 | C | Select a named form field: child, approver or duration choice. Observe loaded selection and control availability. Reject child selection on the fixed-child overlay. | `AccessibleUI.select_kiosk_account(field, name, expected=..., enabled=...)` opens the owned selector, checks the exact offered UID set and labels, invokes the chosen public action once, then waits for fresh REQUEST03 selected-value readback without replay. `kiosk_eligible_choices.PLAN` / `onpc_kiosk_eligible_choices::run` qualified the enabled child/approver branch through `check_e2e_kiosk_eligible_choices` in run `20260923T204614Z-0601b77a`; that unchanged branch evidence is retained. `request_choices.PLAN` / `onpc_request_choices::run` qualified `enabled=False` child selection after separate public Parent enable/save/disable/save and Switch User through `check_e2e_request_choices` in run `20260923T235007Z-9d21bba1`. Both require wrong-entry/choice refusals, independent form readback, private collection and owned cleanup. Complete case 57 (`disabled_child.PLAN` / `onpc_disabled_child::run`) passed in run `20260924T001910Z-3076f596` with limits off throughout; `inspect_only=True` and `collapse_kiosk_child_choices` qualify exact child-list inspection, collapse through the same public trigger, and independent unchanged-selection readback before selection. Other account profiles, duration editing and installed overlay refusal remain pending. | pending; enabled kiosk child/approver, disabled-child selection and child-list inspection/collapse ready |
| REQUEST05 | C | Type a custom duration, including deliberately invalid text, and observe validation/request availability. | UI16 → REQUEST03. Do not coerce or repair the customer's value. | pending |
| REQUEST06 | C | Set the request form's soft-app choice to an explicit boolean and observe it. The surface and child are explicit. | UI17 → REQUEST03. Reuse UI17; interactive mute is deferred future-feature scope, not a prerequisite for current choices. | pending |
| REQUEST08 | C | Read the visible estimate/footer for the chosen duration, including rest-of-day meaning, loading or unavailable estimates. | UI01 → UI03. `AccessibleUI.kiosk_request_form(enabled=False, expected_selection=...)` and `RequestObservation.from_request` bind `kiosk-disabled-form` to the selected child, retained nonempty approver, exact disabled-screen-limit explanation and unavailable Request/duration/soft-app/approver controls. Complete fresh prompt checks refuse authentication; disabled controls receive no input. `check_e2e_request_choices` qualified selection and independent readback in run `20260923T235007Z-9d21bba1`, with collection and owned cleanup. Complete case 57 also passed these public results with limits off throughout in run `20260924T001910Z-3076f596`, including Cancel-to-GDM, collection and owned cleanup. Numeric, loading, rest-of-day and overlay estimates remain pending; expected time must come from prior visible observations and elapsed time. | pending; kiosk disabled-child explanation and unavailable Request ready |
| REQUEST09 | C | Activate an enabled Request once and observe the declared result: authentication for valid input or validation for invalid custom input. | UI01 → UI02(enabled) → UI04; valid then AUTH01, invalid then REQUEST03 → UI11(no prompt). Missing accounts, unloaded preferences or disabled limits instead require the disabled state and no activation. | pending |
| REQUEST10 | C | Double-click an enabled Request control and observe exactly one in-progress prompt/form. | UI01 → UI02 → UI20, surrounded by UI22 tracking registered prompt/form counts and Request availability; UI13 independently confirms final counts. No second approval input or internal exactly-once claim. | pending |
| REQUEST11 | C | Observe success confirmation, rejection, cancellation without an error, or validation feedback, with the explicitly expected preserved choices. | UI01 → UI03 → REQUEST03 where the form remains → UI12. Capture brief success before waiting for automatic exit. `AccessibleUI.kiosk_gdm_returned` is installed-qualified through `check_e2e_request_exit` for Cancel/Escape from the fixed disabled-child kiosk form: usable GDM and absent request/error UI. Case 54 also validates Cancel from the no-child form through `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run`. Authentication outcomes, preserved choices on a remaining form, validation and overlay results remain pending. | pending; kiosk form Cancel/Escape result ready |
| REQUEST12 | C | Exit by Cancel, Escape, normal window close, the approved immediate exit action, or the already-approved automatic exit. Observe overlay disappearance plus child desktop, or kiosk disappearance plus GDM. No authentication prompt may be active for form Cancel/Escape. | UI04(Cancel or approved immediate exit), UI05, UI18, or no input for automatic exit → UI11 → DESK01 or GDM01. `RequestExitJourney` / `check_e2e_request_exit` uses shared direct station entry for each fixed disabled-child Cancel/Escape attempt: `AccessibleUI.cancel_kiosk_request` invokes the owned-ID action directly; `focus_kiosk_escape_recipient` guards ordinary Escape; `kiosk_gdm_returned` independently observes each destination. Both refuse active prompts. Case 54 independently validates the same Cancel action and GDM destination from the no-child form through `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run`. Window close, approved exits, enabled-choice consumers and overlay exits remain pending. | pending; kiosk Cancel/Escape ready |
| REQUEST13 | C | Open the child overlay through the Shell panel only when the case explicitly tests that graphical launch route. Observe one usable form and fixed child identity. | DESK12(request entry) → UI04 → UI01 → UI02 → UI13(form count=1) → UI03(fixed child). Declare the exception in case metadata and recipe. Normal unlocked-child panel entry and fullscreen reveal still need installed qualification. | pending |

### Customer terminal, files and application use

FILE02 executes registered public commands over guarded SSH as the declared
fixture user. INFO02 reads the public help/manual interface through bounded
stdout. Neither route permits private product probes or Terminal GUI setup. Fixture package/path arguments come from
verified prepared assets. Native/Snap/Flatpak and app names are parameters of
these blocks, not copies of them.

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| FILE01 | A | Bind the guarded SSH channel to the declared fixture user/session for supporting commands. | Shared transport and fixed command registry; INFO02 already uses `command_documentation`. `session_control.observe` / `execute` bind `parent-command-context` to the active local administrator and read the verified staged package; [product-free qualification](#product-free-parent-entry-and-command-context) includes greeter refusal. `PackageCommand` rechecks that context for the [fixed install binding](#administrator-package-command-and-output). No graphical Terminal merely to execute commands. | product-free Parent context and fixed install authority ready; additional bindings pending |
| FILE02 | A | Submit one registered command with finite validated arguments over shared SSH as the declared user. No arbitrary shell strings or replay. | `PackageCommand.submit` / `guest_submit` execute one fixed APT argument array under the bound administrator context and guarded VM transport; [qualification](#administrator-package-command-and-output). PARENT01/REQUEST02 retain dedicated launch bindings. FILE06 observes the later result. | fixed install binding ready; additional bindings pending |
| FILE06 | A | Read bounded stdout/stderr, exit status and required public product notice or launch denial. Command echo or generic failure cannot prove enforcement. | `PackageCommand.read_result` independently requires successful exit, actual completion and final reboot notice at the later checkpoint; [qualification](#administrator-package-command-and-output). Graphical management denial remains PARENT01. No terminal rendering or unrelated password exercise. | fixed install completion/notice ready; additional bindings pending |
| FILE07 | C | Navigate an open file manager/chooser to one declared customer directory. Use its normal Location shortcut, enter the directory and observe the destination. | UI05(Location shortcut) → UI16(location field) → UI05(Enter) → UI01 → UI03(destination). Directory identity comes from prepared synthetic fixtures or the selected save location. | pending |
| FILE03 | C | Choose files, save a named file, or cancel in an already open chooser. Mode and selected files are explicit. Observe selection/closure; the caller observes its later result separately. | Open: FILE07(directory) → UI14(first file) → UI05 for declared additional modifier/navigation selection → UI13(exact selected set) → UI04(Open) → UI11(chooser). Save: FILE07 → UI16(filename) → UI04(Save) → UI11. Cancel: UI04(Cancel) → UI11. No unmodified second selection that silently drops earlier files. | pending |
| FILE04 | C | Open the file manager directly at a declared directory only when the case tests that launch route or product file-picker integration. | Shared fixed command/URI launch → FILE07/UI13. Supporting file preparation uses commands. | pending |
| FILE05 | C | Copy or rename a registered fixture file through a bounded shared SSH filesystem operation and verify its exact destination. | Owned synthetic fixtures only; reject traversal, symlinks and wrong ownership. Product catalogue/enforcement results remain independent UI observations. No Files copy/rename tour. | pending |
| FILE08 | C | Open a declared customer-selected artifact directly with its registered handler and observe its intended contents/window. | Shared bounded `gio open` or fixed viewer command → owned handler observation. No file-manager navigation merely to open a supporting document; no private product files. | pending |
| FILE09 | C | Change a registered synthetic source file using the shared file helper and observe the product's attachment snapshot/re-add result. For declared retained-work assertions, edit/save in the existing work fixture and read its activity. | Fixed file commands for source preparation; UI16/Ctrl-S/public saved state only for work observed by an enforcement/retention case. | pending |
| APP01 | C | Attempt a launch once by the route explicitly tested by product enforcement. Default supporting launch uses a shared direct command. Hidden launcher and execution denial are distinct. | Explicit app-grid, desktop-icon and file-manager cases retain their GUI route. Command cases use FILE01/02 over SSH as the child desktop user without Terminal UI. Never substitute the tested route after failure. | pending |
| APP02 | C | Observe exactly the expected usable window, named launch denial, hidden launcher, or closure of a previously observed window. Inputs include route, result and earlier window observation when required. | UI01 → UI03 for presence; FILE06 for command denial; UI11 for hidden/closed surface with a recognized surrounding UI. Hidden launcher alone cannot prove blocked execution. | pending |
| APP03 | C | Perform one declared normal app input and observe its customer-visible effect, proving usability. Repeated game actions are separate bounded invocations. | UI01 → one of UI04, UI05 or UI06 according to the declared input mode → UI03 or UI02 according to the declared result projection. App action/expected effect is fixture data. | pending |
| APP04 | C | Read a recognizable public activity/window state, or compare it after legitimate return. Inputs declare capture/compare and the earlier immutable observation. | APP02(present) → UI03 → UI12 only for compare. A newly launched window cannot satisfy retained-activity expectations. No hidden process/window inspection. | pending |
| APP05 | C | Prepare the real offline game's declared windowed/fullscreen mode and reproducible level through shared supported commands or keyboard shortcuts, then observe active gameplay. Game settings menus are supporting setup. | Bind startup options in the preceding APP01 launch, or use a fixed supported command/UI05 shortcut on the observed game; do not relaunch retained activity. UI01/UI03 verifies the mode/level, then APP03 proves actual gameplay input/effect. The selected game needs usable public observations; a menu or timer fixture is insufficient. | pending |
| APP06 | A | Read one complete, account-scoped public projection of Lunar's tray/background control, Lunar window and Minecraft activity, with the recognized surrounding desktop. Presence/absence is explicit input; do not launch, reveal or quit anything. | No callable yet. Task 296 qualifies the Lunar/Minecraft and Shell tray provider bindings, including absence and incomplete/wrong-owner refusal. UI22 composes repeated observations across the declared login interval; one final absent window cannot establish blocked autostart. [Consumer gate](#lunar-client-preparation-and-observation-gate). | pending |

### Time and ordinary lifecycle boundaries

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| TIME01 | C | Read the displayed countdown or require its stable absence on a specified desktop, lock or GDM surface. | UI01 → UI03, or UI11 with the destination positively identified. | pending |
| TIME02 | C | Observe minute ticks/final seconds over real monotonic intervals; compare actual displayed values and formatting with explicit tolerances. | TIME01 → UI10 → TIME01 → UI12. No guest clock/usage manipulation. | pending |
| TIME03 | A | Let a declared bounded real interval elapse while retaining the runner guard and deadline. Return elapsed time only; this does not prove a lock or grant expiry. | Extract a guarded monotonic wait with finite progress checkpoints for E2E-010/022. | pending |
| TIME04 | C | Use the selected app/game until natural expiry, then observe the lock owning normal input and loss of desktop access. Earlier visible time and the timeout are explicit inputs. | Bounded APP03 → TIME03 repetitions, with TIME02 only while the countdown is showing → UI01(lock) → UI05(harmless normal input) → UI01(lock challenge)/UI02. Do not require a visible countdown during fullscreen play or inspect the game underneath the lock. | pending |
| LIFE01 | C | Close and reopen one named ordinary app through a shared direct command, unless the case explicitly tests its graphical launch route; observe its opening window. Do not reselect a child or restore settings before reading them. | Parent: UI18 → PARENT01. Other ordinary apps use APP01 with the declared route; SEARCH05 is limited to explicit app-grid checks. Caller reads/compares the relevant fields afterward. Overlay/kiosk reopening uses their explicit exit/entry blocks. | pending |
| LIFE02 | C | Reboot through a fixed supported system command in the owned guest, then observe a new boot and fresh GDM in the same attempt. | `JourneyPlan.reboot_transition`, `InstalledJourney.submit_reboot` and `Transport.request_customer_reboot`; independent `ReadOnlyObservations.wait_boot_change` then fresh GDM. [Qualified install/reboot composition](#customer-reboot-continuity). No Shell power menu; product persistence and activation notices remain required. | fresh install/reboot/administrator return ready; other bindings pending |
| LIFE03 | C | Suspend through a fixed supported system command, wait the real interval, wake through the owned VM's supported input and observe the return. | Shared lifecycle harness → TIME03 → bound wake input → public result; unlock remains DESK08. No Shell menus. | pending |
| LIFE04 | C | Perform a declared real install/update/remove/reinstall/purge with a registered package command over guarded SSH; observe completion and the actual customer notice. | `package_install.submit_install` / `observe_install` compose FILE01/02/06 and AUTH03 with verified artifact identity, one submission and independent completion/final notice. `PackageInstallJourney` qualifies the fresh product-free install entry; [qualification](#customer-package-install-composition). No Terminal, sudo-prompt exercise or private product-state assertion. | install ready; update/remove/reinstall/purge pending |
| LIFE05 | C | Follow the displayed activation requirement for the explicit finite list of affected apps/users: none, process reopen, session renewal, or reboot/login. | None: UI03(notice). Process: LIFE01 for each app. Session: DESK03 → GDM02 → DESK08 when reaching another retained user, then DESK04 → GDM07 for each required renewal. Reboot: LIFE02 → GDM07. Compare displayed state afterward; one user's logout does not renew every session. | pending |
| LIFE06 | C | Change real guest connectivity through the shared system harness and independently observe offline/reconnected state and required product results. | Registered NetworkManager/nmcli operation on the test connection, preserving management/observation and cleanup. No Settings/Quick Settings navigation, mock transport or injected product/provider fault. | pending |

### About, feedback and customer-selected attachments

| ID | Kind | Block and explicit contract | Callees / reuse source | Status |
| --- | --- | --- | --- | --- |
| ABOUT01 | C | Open the declared surface's About entry; read product/version and reach the license information. Parent's established binding stays ready; overlay/kiosk bindings are pending. | `onpc_about::open_about` binds `AccessibleUI.open_about(version)`: UI01 → UI04(menu) → UI04(About) → UI01 → UI03 → UI09. [About contracts](#about-block-contracts). | ready |
| ABOUT02 | C | Follow the license link to the actual viewer and read the identifying license content. | `AccessibleUI.open_license` follows the ID-addressed product link once. `license_viewer_snapshot` scopes GNOME Text Editor's public `view` ID; `read_document` verifies bounded GPL title/version text. `check_e2e_license_viewer` qualified independent entry and live unrelated/empty/ambiguous viewer refusal in run `20260923T201618Z-50520052`. [Provider scope](#about-block-contracts). | ready for Parent/GNOME Text Editor; other bindings pending |
| ABOUT04 | C | Reach and read the About footer in the already open About window through semantic ID reveal. | `onpc_about::read_footer(journey, returned, 'semantic-reveal')` delegates to `AccessibleUI.about_footer`: UI09 → UI03(footer), with no preliminary positional keys. [About contracts](#about-block-contracts). | ready |
| ABOUT03 | C | Close the license, read the About footer, close About and compare the selected child/settings with the supplied earlier observation. | `onpc_about::return_to_parent` composes UI18 → ABOUT04 → UI18; `JourneyPlan.settings_checks` supplies UI12. `onpc_license_viewer_provider::run` qualified those leaves with active-viewer proof, ambiguous-close refusal, single-use close, complete viewer absence, active owned About return, footer read and unchanged child/switch/allowance in run `20260923T201618Z-50520052`. Complete case 151 passed the composed journey, collection and owned cleanup in run `20260923T202401Z-9e9a5886`. | ready for Parent/GNOME Text Editor; other bindings pending |
| FEED01 | C | Open ordinary Parent feedback through its Feedback action and observe editor/collection state. Error-report entry uses FEED15; no hidden error creation. | UI01 → UI04(feedback entry) → UI01 → UI02 → UI03. | pending |
| FEED03 | C | Read the visible synthetic draft, exact attachment list and validation/control state into an explicit observation. | UI01 → UI02 → UI03 → UI13(attachments). Only the declared synthetic content is eligible for comparison. | pending |
| FEED04 | C | Apply one offered rich-text format to an explicit synthetic range and observe its public text attributes. Select the range through normal keyboard input, then use its toolbar/menu. | UI21(editor) → UI05 for bounded declared selection → UI04 or UI15(format) → UI24. No DOM bridge or direct text/selection assignment. | pending |
| FEED05 | C | Open Privacy, read the disclosure/diagnostic explanation, then close it. | UI04 → UI09 → UI03 → UI18. | pending |
| FEED06 | C | Add prepared synthetic attachments through Add files and the actual file chooser, then observe the displayed list or validation. | UI04 → FILE03 → FEED03. Repeat finite fixture values for the declared attachment-count and size validation. | pending |
| FEED07 | C | Resolve one attachment row by its stable public ID, then read its displayed synthetic name/size and verify its order if required. Order is a result and never identifies the row. Does not preview or remove it. | UI01 → UI03 → UI13(order when required). | pending |
| FEED12 | C | Open an offered attachment preview, read declared synthetic contents and close it, returning to feedback. | UI01 → UI04 → UI03 → UI18. An unoffered preview does not authorize private storage inspection. | pending |
| FEED13 | C | Remove one explicitly identified attachment and observe the remaining list. | UI01 → UI04(Remove) → FEED03 → UI12(expected list). | pending |
| FEED08 | C | Explicitly save diagnostic output to a customer-selected location, open that saved output through the file manager/viewer and read the expected public contents. | UI04(download) → FILE03(save) → FILE08(archive) → UI03(registered public entries/contents). Caller may instead stop after FILE03(cancel) and inspect its retained draft. Do not inspect original product logs or storage. | pending |
| FEED09 | C | Observe collection, validation, sending, retry, error or thank-you state and control availability. Snapshot mode reads the current state; transition mode records required transient states around FEED01 or FEED11. | UI01 → UI02 → UI03 → UI10, or UI22 with the same projections. No provider receipt or delivery-internal assertion. | pending |
| FEED10 | C | Close/reopen feedback and compare its in-memory draft. `dialog` preserves the supplied draft; `app-exit` explicitly closes/relaunches Parent and expects reset. Return with feedback open. | FEED03(before) → UI18(feedback) → LIFE01(Parent) only for app-exit → FEED01 → FEED03 → UI12(expected draft). Do not edit fields before comparison. | pending |
| FEED11 | C | Submit one already reviewed synthetic report. Require explicit sending authorization and dedicated test-recipient configuration; activate the explicit `Send` or `Send without logs` action once and return. Observe the outcome and dismiss confirmation separately. | UI01 → UI02(enabled) → UI04(Send). Prior FEED03 → FEED05 evidence is supplied, not repeated inside this block. This document grants no sending authorization. | pending |
| FEED14 | C | Dismiss an observed success confirmation normally and observe the expected return surface. | UI01 → UI04(Close) → UI11(confirmation) → UI01(return surface). FEED09 supplies the earlier success observation. | pending |


### Additional public surfaces

These blocks supply the named new consumers in the
[scenario recipes](E2E-Scenario-Recipes.md). All are pending; a documented
binding does not extend an existing callable's qualified scope.

| ID | Kind | Block and explicit contract | Callees / first consumer | Status |
| --- | --- | --- | --- | --- |
| AUTH04 | A | Validate authority and protected-account restrictions for shared fixture account operations. No Users-settings password prompt. | Owned fixture/SSH boundary; product approval challenges remain AUTH01/02. | pending |
| ACCOUNT01 | A | Read the declared fixture account/role set through public system account interfaces over guarded SSH. | Shared account-fixture library with bounded nonsecret output. Preparation metadata only; app account lists supply customer assertions. | pending |
| ACCOUNT02 | C | Add/remove/change the role of a registered spare fixture account through shared system commands or AccountsService and read back the change. | Reuse `account_fixture` infrastructure; protect active/last administrator and station, registered secrets and owned cleanup. Independently observe Parent/request-selector refresh. No GNOME Users wizard. | pending |
| PANEL01 | C | Open the child's countdown context menu and read the named animation choice. | DESK12(countdown) → UI01 → UI28 → UI01(menu) → UI02(choice). E2E-037. | pending |
| PANEL02 | C | Set the animation choice in an already open menu, then close the menu and verify return to the desktop. | UI17(choice) → UI05(Escape) → UI11(menu) → DESK01. E2E-037. | pending |
| PANEL03 | C | Reveal and read the countdown's hover explanation. | DESK12(countdown) → UI01 → UI27 → UI03(tooltip). E2E-011/037. | pending |
| INFO01 | C | Follow one declared Help/About link and read the identifying browser, mail-composer or legal-viewer destination; return without submitting mail. Kiosk asserts unavailable external actions instead. | UI04(link) → UI01(destination) → UI03(identity) → UI18(destination); kiosk UI11 on recognized About. E2E-042. | pending |
| INFO02 | C | Read one installed product help command or command manual from bounded, guarded SSH stdout as the parent fixture account; check the public desktop afterward. | `onpc_documentation::read(journey, binding)` composes `command_documentation.observe` and the registered public desktop-clear observation. The stdout adapter checks fixed command identity, help usage/options or manual sections/purpose without Terminal rendering. All four bindings and independent desktop returns passed complete case 193 in run `20260923T194553Z-e2f16f7e`, with collection and owned cleanup. | ready |
| FEED15 | C | Review or decline a displayed product error report. Request result entry explicitly sets Report this error then closes the result; Parent entry observes its automatically opened report without inventing a report button. Read the report or declared exit destination. | Request: UI17(report choice) → UI04(result Close) → UI01 → FEED03 for review; Parent: UI01 → FEED03; decline UI11(report) → UI01(destination). E2E-045. | pending |
| FEED16 | C | Retry an observed failed diagnostic collection and read its result and retained draft. | UI04(Retry collection) → FEED09 → FEED03 → UI12. Without-logs submission reuses FEED11; it is not hidden inside retry. E2E-046. | pending |
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
| FLOW15 | C | Reach an explicit user's desktop from the declared source surface. `entry=fresh` requires no retained session; `retained` requires an earlier observed desktop; `same` requires the current user already matches. Return the observed desktop or expected time-limit denial. | Fresh entry needs GDM07 and DESK01 provider-route qualification; other routes remain pending. | pending |
| FLOW01 | C | Open or return to Parent for a named child and record displayed settings. Inputs declare source, parent entry and `window=new` or `retained`. Default first entry is GDM/fresh/new; a return uses retained entry and the existing window. New launches always use PARENT01's direct command. | `onpc_parent::open_for_child` composes fresh FLOW15 → PARENT01(management) → PARENT02. The fresh Parent/Riley binding passed in case 151; retained and other entry bindings remain pending. | pending; fresh Parent/Riley binding ready |
| FLOW02 | C | Configure the selected child's time controls, observing save and explanation. Inputs declare initial/final enablement and allowance. Enable first only when needed to make the allowance editor usable. | PARENT04(Screen Limits) → UI17(Screen time limit=true) if required → PARENT06 → PARENT08 → UI17(final boolean) → PARENT08 → PARENT03 → PARENT09. Disabling clears a grant; this is not a harmless navigation step. | pending |
| FLOW03 | C | Configure one app's matching and access choices through Parent and read the saved row. | PARENT10 → PARENT11 if declared → PARENT13 → UI16(match draft) → PARENT15(save) → PARENT16 → PARENT12. | pending |
| FLOW04 | C | Open the selected request surface, or use an explicitly already-open form, then choose child/approver/duration/app access and read the estimate. | REQUEST01 or REQUEST02 only for `entry=new`; `entry=open` starts with REQUEST03 → REQUEST04(child only in kiosk, approver, duration) → REQUEST05 if custom → REQUEST06 → REQUEST08. | pending |
| FLOW05 | C | Complete a real approval from a prepared form, observe confirmation and its surface-specific automatic exit. | REQUEST09 → AUTH02(correct credential) → REQUEST11(success) → REQUEST12(automatic). | pending |
| FLOW06 | C | Obtain time through kiosk from an existing GDM screen and return to GDM. | FLOW04(kiosk) → FLOW05. Child login/unlock is deliberately a later step. | pending |
| FLOW07 | C | Reject/cancel one request and compare its preserved choices. Return with that form open; do not retry yet. | REQUEST03(before) → REQUEST09 → AUTH02(wrong/cancel) → REQUEST11 → UI12. The recipe can inspect restrictions before invoking FLOW05 for a successful retry, avoiding a second implementation of approval. | pending |
| FLOW08 | C | Exercise an app through its declared route and prove the expected usable/denied result. | APP01 → APP02 → APP03 only for expected usable access. | pending |
| FLOW09 | C | Visit an explicitly retained user and prove the same app/activity remains usable. Inputs include source surface and that user's earlier activity observation. | FLOW15(entry=retained) → APP04(compare) → APP03. | pending |
| FLOW10 | C | Launch the prepared real game with its declared mode/level and play to natural lock. | FLOW08(game, usable, registered launch options) → APP05 → APP04(record activity) → TIME04. | pending |
| FLOW11 | C | After a displayed lock, obtain legitimate replacement time, unlock and observe the expected retained app or closed blocked app. | DESK11 → FLOW06 → FLOW15(child, retained) → APP02 → APP04(compare) → APP03 when preservation is expected. Closed-app branch ends at APP02. | pending |
| FLOW12 | C | From an open request form, visit the other surface for that child and compare duration/custom/soft-app choices before editing. Compare the independently remembered parent for each requesting OS user, not parent equality across surfaces. Interactive mute is separate deferred scope. Finish with the second form open. | Overlay→kiosk: REQUEST12(cancel) → DESK03 → REQUEST01. Kiosk→overlay: REQUEST12(cancel) → FLOW15(child, declared fresh/retained entry) → REQUEST02. Both then REQUEST03 → UI12(shared values and user-local selectors). Interactive mute remains deferred outside this current-choice composite. | pending |
| FLOW13 | C | Establish a named time profile entirely through customer controls and finish at GDM. Entry/window arguments are explicit. Verify no grant or revoke it first; use the profile table below. | FLOW01 → PARENT09 → PARENT17 → PARENT18(confirm) only if revocation is declared → PARENT09 → UI12(no grant) → FLOW02(initial allowance) → DESK03. Grant profiles then FLOW06 → FLOW01(parent/window retained); daily-dominant adds PARENT06(larger allowance, still enabled) → PARENT08. All grant profiles finish PARENT09 → UI12(profile) → DESK03. | pending |
| FLOW14 | C | Open apps/recognizable activities for a finite declared user list, retaining each desktop through Switch User. Inputs state each user's fresh/retained entry and usable-time/policy prerequisites. Start and finish at GDM. | For each user: FLOW15 → FLOW08 → APP04(capture) → DESK03. Earlier retained desktops must be revisited, not recreated. Multiple desktops for one identity require a supported customer route; see applicability notes. | pending |
| FLOW16 | C | As the named parent, reach Parent for the named child and set a daily allowance and final limit state. This is the reusable “Set Jordan's daily allowance to zero” recipe; zero is an allowance, not an approval. | FLOW01(explicit source/entry/window/child) → FLOW02(initial state, allowance, final state). FLOW02 owns navigation to Screen Limits. Finish in Parent; no implicit logout. E2E-035/036 and ordinary scenario setup. | pending |
| FLOW17 | C | Leave a request with authentication pending by one declared supported action, observe its destination, then return and read cancellation before a new request. | Lock: shared DESK05 shortcut/command → DESK06 → DESK08; switch: DESK03 → FLOW15(return retained); sign-out: DESK04 → FLOW15(fresh); close: UI04/UI05(app close) → UI11(app), followed by REQUEST01/02 as declared. REQUEST03 → UI11(old prompt). E2E-039; system commands work independently of modal menu access. An unavailable tested app-close control remains gated. | pending |
| FLOW18 | C | Prepare positive daily time that outlasts a soft-app grant without resetting its launch exception. Finish on the child desktop with both balances positive and daily dominant. | FLOW13(combined, soft included) → FLOW15(child) → FLOW08(soft app) → APP04 → DESK03 → FLOW01(parent retained) → PARENT09 → TIME03(wait until the declared remaining-grant window while child is away) → PARENT09 → UI12(D>G>0) → DESK03 → FLOW15(child retained) → TIME01. No allowance edit or app save after approval. E2E-038. | pending |
| FLOW19 | C | Configure a finite named app-rule set for one child and return to sign-in. Each match/access edit and save is explicit; no time approval or account preparation is hidden. | FLOW01(parent, explicit source/entry/window/child) → PARENT04(App Limits) → FLOW03 for each declared app/rule → DESK03. First consumers E2E-006/007; reused as AppSet in the recipes. | pending |
| FLOW20 | C | Approve a specified interval on either request surface and continue as the named child. Accept explicit new/open form entry, child/parent, duration, soft choice, child fresh/retained entry and expected countdown. New overlay entry requires that child's unlocked desktop; new kiosk entry requires GDM. It does not create those preconditions or alter daily policy. | FLOW04(entry and all choices) → FLOW05 → FLOW15(child,declared entry) only for kiosk → TIME01 → UI12(expected interval). Overlay returns to its existing desktop. Reuse FLOW04/05/15 without another surface-specific approval implementation. E2E-048 immediate repeat and E2E-049/050/051. | pending |

### Canonical reuse and implementation checkpoints

The former duplicate wrappers are retired identifiers, not pending work:

| Former ID | Canonical block | Binding |
| --- | --- | --- |
| SEARCH02 | UI21 | Overview search field |
| PARENT07 | UI17 | Parent's Screen time limit switch |
| PARENT14 | UI16 | Open match-rule draft field; do not Save |
| FEED02 | UI16 | Synthetic feedback body or reply field |
| REQUEST07 | UI17 (future binding only) | Retired interactive mute wrapper; no current customer dependency |

The split operations intentionally have separate checkpoints: UI23 scrolls and
UI09 observes reachability; PARENT09 expands/navigates and PARENT20 only reads
an already showing explanation; GDM08 observes a prompt, GDM03 qualifies a secret
recipient and GDM09 dismisses; HAR05/06/07/08 separate serial login, command,
logout and return; FILE02 submits
and FILE06 observes; FEED07 reads an attachment, FEED12 previews and FEED13
removes; FEED11 submits and FEED09 observes before FEED14 dismisses success.
FILE08 opens a customer-selected file, FILE09 edits/saves its already-open
document, and FEED08 composes download, chooser and archive viewing. An atomic
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

For required transient states, write `watch(observer) { action }`: start UI22,
wait for its readiness acknowledgement, perform the action once, then collect
the trace. The observer must be able to see public UI events during input;
post-action polling cannot establish that Saving appeared or a button was
inhibited. Missing samples fail that assertion. This needs a scoped extension
of the existing guarded rendezvous for the first named transition consumer
(feedback collection or Parent saving), not another runner.

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
| FIX03 | A | Prepare one declared account-eligibility profile before a kiosk journey: multiple, no child, no approver or ineligible approver. Do not generalize FIX02 into arbitrary account mutation. | `EmptyAccountFixture.prepare` / `e2e_dynamic_account.prepare_empty` changes only the two canonical children's account type, preserving identities, existing administrators and the station; outer lease cleanup restores the profile. `kiosk_no_child.PLAN` / `onpc_kiosk_no_child::run` qualified this profile through `check_e2e_kiosk_no_child` in run `20260924T064646Z-19f2aad6`, with shared station navigation requalified in run `20260924T173643Z-8d742069`. `AccessibleUI.kiosk_request_form(no_child=True)` and `RequestObservation.from_request` independently require the exact empty child set and no-child explanation, disabled Request/duration/soft-app/approver controls and no authentication prompt. Valid station entry, wrong-entry refusal, repeated public readback, sanitized collection, owned cleanup and baseline restoration passed without product-policy mutation. Complete case 54 separately passed via `kiosk_no_child.CASE_PLAN` / `onpc_no_child::run` and `tools/run-tests e2e --id '54'`, adding public Cancel/GDM return; wrong-entry refusal remains qualification-only. The no-approver callables, qualification and independent case 55 acceptance below supply the second ready profile. Multiple/ineligible-approver profiles remain pending. | pending; no-child/no-approver profiles and station empty states ready |
| FIX01 | A | Create one eligible account at the declared durable checkpoint while Parent stays open. Customer acceptance requires later visible discovery/selection. | `DynamicAccountFixture.create` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX02 | A | Make the exact two canonical eligible child fixtures ineligible at the declared checkpoint before Parent launches; preserve the request station. Unexpected account sets refuse. | `EmptyAccountFixture.prepare` in [account_fixture.py](../../tests/e2e/account_fixture.py). | ready |
| FIX05 | A | Validate the one declared, manually prepared Lunar/AppImageLauncher/Minecraft profile after the normal installed-snapshot restore and before the attempt. Read-only setup verification, not installation, policy configuration or customer acceptance. | No callable yet. Task 295 binds versions/digests, original AppImage and launcher/autostart routes, local world, credential references and ordinary restore/provisioning ownership. Refuse missing/drifted assets; never synthesize a denial. [Profile contract](#lunar-client-preparation-and-observation-gate). | pending |

FIX03's no-approver profile starts with
`AccessibleUI.kiosk_approver_baseline`: require at least one parent in the public
form, without fixed parent names or counts. The showing selection proves
presence even when disabled/collapsed choices are omitted from AT-SPI.
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
`tools/run-tests e2e --id '55'` in run `20260924T175340Z-dd93d54f`: public
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

The following index accounts for every family. A recipe range means every
variant in that range, never sampling. Customer setup is part of each independent
case. Harness case 1 remains separate qualification. Retired E2E IDs 140–150
belong only to the system-test tasks listed under inventory reconciliation.

### Parent, login and time scenarios

Every E2E invocation, including a single-case selection, holds one exclusive VM
lease. Suite preparation runs once, before the first case, reusing an existing
`onpc-v[version]` snapshot (the app release without package revisions, for example
`onpc-v1.1`). Reuse requires matching package bytes, baseline identity and the
installation recipe recorded in snapshot metadata. Missing, legacy or changed
snapshots automatically restore `onpc-baseline`, install the package, reboot,
verify installation, shut down and capture the version snapshot. This installation
belongs to suite preparation.

Freshness metadata is published only after snapshot creation returns successfully,
using libvirt's [metadata redefinition API](https://libvirt.org/html/libvirt-libvirt-domain-snapshot.html#virDomainSnapshotCreateXML).
An interrupted creation leaves an unmarked snapshot, which preparation refreshes.

The installed-state fingerprint deliberately excludes test code, guest helper
logging, scenario selections, fixture delivery payloads, documentation and run
outputs. These are refreshed as a separately verified test payload before each
attempt; they do not reinstall the app. The current recipe installs only the app;
future persistent fixture installation must belong to that recipe and its identity.
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
  `declared-package-lifecycle-fixture` and start from `onpc-baseline`, with
  installation performed as part of the tested package behavior.
- Runner-only product-free harness checks, including retained case E2E-001, start
  from `onpc-baseline` without installing the app.

Inventory validation enforces these declarations for existing and future cases;
the installed-app and package-lifecycle prerequisites are mutually exclusive.
The suite verifies the required snapshot was restored before provisioning.
Installed journeys have no per-case installer: a missing snapshot fails the
invocation without fallback installation.

The expensive baseline audit and offline guest inspection bracket the suite.
After collecting a case's observations, the worker's final power-off callback
directly force-restores the next case's required off snapshot; it does not wait
for ACPI. The next case provisions its declared inputs on that snapshot, removes
host sharing and boots, without a second restore. Live ownership, disk identity,
snapshot metadata and isolation checks still apply; transitions add no package
validation, installation or reboot. Suite cleanup restores `onpc-baseline` and
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

The same preparation is available independently:

- `./tools/cleanup-e2e` reconciles previous recorded run leftovers and preserves
  evidence under the existing checkout and VM ownership checks.
- `./tools/prepare-appsnapshot [--overwrite true|false]` builds and installs the
  current Debian version and retains its `onpc-[version]` snapshot. It leaves the
  VM powered off in that installed state after auditing the outer baseline.
  Preparation restores `onpc-baseline`, boots, installs and verifies the package,
  then shuts down and takes the disk-only snapshot without an intervening reboot.
  Booting the restored snapshot supplies the clean restart required after
  installation; installed-system readiness checks still run after that boot.
  Missing `--overwrite` or a missing value means `true`. When a matching snapshot
  exists, `true` forces replacement. `false` builds verified artifacts and compares
  their installed-state identity under the shared lease; it retains a match and
  automatically replaces a stale or legacy snapshot. A name-only probe is never
  freshness evidence. When none exists, either value prepares it. Other version
  snapshots are left alone. Preparation performs shared cleanup before building.
  These are development-only changes (activation `none`); no product migration,
  host installation or permission refresh is required.

The [live verification contract](E2E-Execution-Plan.md#live-verification-contract)
defines when a task prepares or reuses this snapshot. A retained snapshot is a
setup prerequisite, not customer-acceptance evidence; subsequent VM actions
still use the guarded ownership interfaces.


| Family / cases | Contract and scope |
| --- | --- |
| E2E-001 / **1** | [Harness contract](#case-1-stage-contract) — Fresh boot and graphical/observation transport. No customer acceptance credit. |
| E2E-002 / **2** | [Recipe](E2E-Scenario-Recipes.md#e2e-002) — Install the app and begin managing a child. Customer actions and public results. |
| E2E-003 / **3–4** | [Recipe](E2E-Scenario-Recipes.md#e2e-003) — Parent discovery and navigation. Customer actions and public results. |
| E2E-004 / **5–6** | [Recipe](E2E-Scenario-Recipes.md#e2e-004) — Standard user cannot manage policy. Customer actions and public results. |
| E2E-005 / **7–12** | [Recipe](E2E-Scenario-Recipes.md#e2e-005) — Change screen limits while starting or returning to a child desktop. Customer actions and public results. |
| E2E-006 / **13–16** | [Recipe](E2E-Scenario-Recipes.md#e2e-006) — Change app rules while children use apps. Customer actions and public results. |
| E2E-007 / **17–20** | [Recipe](E2E-Scenario-Recipes.md#e2e-007) — Cancel then confirm revocation with open apps. Customer actions and public results. |
| E2E-008 / **21–22** | [Recipe](E2E-Scenario-Recipes.md#e2e-008) — Natural daily exhaustion, retained unlock and fresh login denial. Customer actions and public results. |
| E2E-009 / **23–24** | [Recipe](E2E-Scenario-Recipes.md#e2e-009) — Recover unfinished work after grant-only time runs out. Customer actions and public results. |
| E2E-010 / **25–26** | [Recipe](E2E-Scenario-Recipes.md#e2e-010) — Switch User while child time expires. Customer actions and public results. |
| E2E-011 / **27–29** | [Recipe](E2E-Scenario-Recipes.md#e2e-011) — Countdown and visibility transitions. Customer actions and public results. |

### Request forms and remembered choices

| Family / cases | Contract and scope |
| --- | --- |
| E2E-012 / **30–33** | [Recipe](E2E-Scenario-Recipes.md#e2e-012) — Single child overlay and selected-parent approval. Customer actions and public results. |
| E2E-013 / **34–37** | [Recipe](E2E-Scenario-Recipes.md#e2e-013) — Authentication denial and cancellation retry. Customer actions and public results. |
| E2E-014 / **38–43** | [Recipe](E2E-Scenario-Recipes.md#e2e-014) — Shared duration boundaries and duplicate submission. Customer actions and public results. |
| E2E-015 / **44–49** | [Recipe](E2E-Scenario-Recipes.md#e2e-015) — Request surface exit behavior. Customer actions and public results. |
| E2E-016 / **50–52** | [Recipe](E2E-Scenario-Recipes.md#e2e-016) — Restricted request station. Customer actions and public results. |
| E2E-017 / **53–57** | [Recipe](E2E-Scenario-Recipes.md#e2e-017) — Kiosk selection and unavailable requests. Customer actions and public results. |
| E2E-018 / **58–61** | [Recipe](E2E-Scenario-Recipes.md#e2e-018) — Remember each child's choices across both request forms. Customer actions and public results. |

### Application routes and complete customer journeys

| Family / cases | Contract and scope |
| --- | --- |
| E2E-019 / **62–109** | [Recipe](E2E-Scenario-Recipes.md#e2e-019) — Use supported launch routes under each app rule. Customer actions and public results. |
| E2E-020 / **110–111** | [Recipe](E2E-Scenario-Recipes.md#e2e-020) — Catalog update/disappearance between display and save. Customer actions and public results. |
| E2E-021 / **112–115** | [Recipe](E2E-Scenario-Recipes.md#e2e-021) — Apply an action across a child's distinct retained desktops. Customer actions and public results. |
| E2E-022 / **116–125** | [Recipe](E2E-Scenario-Recipes.md#e2e-022) — Customer lifecycle persistence and resume. Customer actions and public results. |
| E2E-023 / **126–127** | [Recipe](E2E-Scenario-Recipes.md#e2e-023) — Zero allowance to kiosk approval, real gameplay and expiry. Customer actions and public results. |
| E2E-024 / **128–131** | [Recipe](E2E-Scenario-Recipes.md#e2e-024) — Additional time accumulates during gameplay. Customer actions and public results. |
| E2E-025 / **132–135** | [Recipe](E2E-Scenario-Recipes.md#e2e-025) — Replace an expired grant before returning with daily time left. Customer actions and public results. |
| E2E-026 / **136–138** | [Recipe](E2E-Scenario-Recipes.md#e2e-026) — Customer package update and activation. Customer actions and public results. |
| E2E-027 / **139** | [Recipe](E2E-Scenario-Recipes.md#e2e-027) — Install through remove, reinstall and purge. Customer actions and public results. |

### Recovery, information and feedback

| Family / cases | Contract and scope |
| --- | --- |
| E2E-030 / **151** | [Recipe](E2E-Scenario-Recipes.md#e2e-030) — Installed About and license access. Customer actions and public results. |
| E2E-031 / **152–155** | [Recipe](E2E-Scenario-Recipes.md#e2e-031) — Feedback drafts, validation and attachment review. Customer actions and public results. |
| E2E-032 / **156** | [Recipe](E2E-Scenario-Recipes.md#e2e-032) — Send reviewed feedback and read service acceptance. Customer actions and public results. |
| E2E-033 / **157** | [Recipe](E2E-Scenario-Recipes.md#e2e-033) — Recover feedback sending after reconnecting. Customer actions and public results. |

### Additional customer coverage

| Family / cases | Contract and scope |
| --- | --- |
| E2E-035 / **158–159** | [Recipe](E2E-Scenario-Recipes.md#e2e-035) — Choose allowances and save edits. Customer actions and public results. |
| E2E-036 / **160–161** | [Recipe](E2E-Scenario-Recipes.md#e2e-036) — Revoke when there is no active grant. Customer actions and public results. |
| E2E-037 / **162–163** | [Recipe](E2E-Scenario-Recipes.md#e2e-037) — Use and remember the child panel option. Customer actions and public results. |
| E2E-038 / **164–170** | [Recipe](E2E-Scenario-Recipes.md#e2e-038) — Keep daily access after a grant ends and restore soft-app blocks. Customer actions and public results. |
| E2E-039 / **171–178** | [Recipe](E2E-Scenario-Recipes.md#e2e-039) — Leave a pending approval or request again too soon. Customer actions and public results. |
| E2E-040 / **179–183** | [Recipe](E2E-Scenario-Recipes.md#e2e-040) — Refresh accounts and remembered selections after account changes. Customer actions and public results. |
| E2E-041 / **184–189** | [Recipe](E2E-Scenario-Recipes.md#e2e-041) — Search the app list and edit match rules. Customer actions and public results. |
| E2E-042 / **190–193** | [Recipe](E2E-Scenario-Recipes.md#e2e-042) — Read Help, About and command usage on each surface. Customer actions and public results. |
| E2E-043 / **194–195** | [Recipe](E2E-Scenario-Recipes.md#e2e-043) — Use local controls and approvals while offline. Customer actions and public results. |
| E2E-044 / **196–204** | [Recipe](E2E-Scenario-Recipes.md#e2e-044) — Use time across local day and daylight-saving boundaries. Customer actions and public results. |
| E2E-045 / **205–207** | [Recipe](E2E-Scenario-Recipes.md#e2e-045) — Review or decline an error report. Customer actions and public results. |
| E2E-046 / **208–213** | [Recipe](E2E-Scenario-Recipes.md#e2e-046) — Recover unavailable diagnostic collection. Customer actions and public results. |
| E2E-047 / **214–222** | [Recipe](E2E-Scenario-Recipes.md#e2e-047) — Finish or stop feedback in different user flows. Customer actions and public results. |
| E2E-048 / **223–230** | [Recipe](E2E-Scenario-Recipes.md#e2e-048) — Approve after the displayed estimate has aged, for four balances on both request surfaces. |
| E2E-049 / **231–246** | [Recipe](E2E-Scenario-Recipes.md#e2e-049) — Alternate temporary app permission on eight launch routes and both request surfaces. |
| E2E-050 / **247–250** | [Recipe](E2E-Scenario-Recipes.md#e2e-050) — Three continuous work/game/time-source cycles, with both form orders and retained/fresh departures. |
| E2E-051 / **251–252** | [Recipe](E2E-Scenario-Recipes.md#e2e-051) — Four rounds of two-child management, independent choices and retained work. |
| E2E-052 / **253** | [Recipe](E2E-Scenario-Recipes.md#e2e-052) — Real Lunar AppImageLauncher login autostart with ungranted/time-only soft blocks, explicit approval and replacement exclusion. Pending manual fixture and public-provider qualification. |

### Lunar Client preparation and observation gate

Case 253 is a planned real-application regression, not an extension of the native
fixture's qualified scope. Manual preparation of the guarded VM is permitted
before the attempt: install a pinned Lunar Client AppImage and AppImageLauncher,
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
runner's ordinary installed-snapshot restore. Use the established guarded
preparation/provisioning lifecycle; do not add snapshots, replace the baseline,
skip restoration or rely on earlier manual VM state. FIX04 still only transfers
verified assets. The manual prerequisite does not grant FIX05 an installer or
unattended vendor sign-in. Missing integration, invalid sign-in, mandatory update,
network dependence or unavailable assets blocks this profile until resolved in
preparation. Pin a profile that runs the declared local activity without downloads
or authentication during the measured launch checks; requalify after drift.

Task 296 qualifies original-AppImage launch, Lunar/tray restore and genuine Quit.
Task 296a separately qualifies Lunar's Minecraft launch, local-world action and
ordinary exit. Task 296b then qualifies APP06/UI22 across login using both completed
provider bindings. Their APP01/02/03 and UI18 scopes stay explicit. Prefer provider IDs, then scoped public
accessibility/keyboard routes under the repository exception. Any necessary
image/geometry technique stays inside an explicit provider adapter with its
documented limitations and live qualification; it is never a repository-owned
selector or provider-assigned ID. Ownership, complete absence observations,
ambiguity refusal and independent results remain mandatory.

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

Cases 1, 3, 4, 5, 6, 151 and 193 use six Python recipe modules and their Perl
workers. Each recipe now composes the catalogue and shared harness. Python
recipes own expected values, ordered checkpoints, fixture bindings and phases;
Perl recipes invoke shared blocks and checkpoint operations. Shared entry
declarations come from `journey_blocks`, with no case-to-case plan imports.

This extraction is validated on the host only. Existing ready inventory
bindings and earlier installed evidence are retained; no new VM pass or broader
provider qualification is claimed. Validate the seven cases on the installed
system separately before treating these extracted routes as newly qualified.

| Established code | Shared composition | Preserved behavior |
| --- | --- | --- |
| [controller_qualification.py](../../tests/e2e/controller_qualification.py), `onpc_flow00::run` | `serial_harness.record_serial_journey` owns the product-free attempt envelope; FLOW00 composes GDM02/09 and HAR05/06/07/08, then HAR10/09 reconcile evidence. | No graphical secret; real serial authentication/command/logout; exactly one logout before fresh graphical return. Preserve all harness/backend safeguards and the existing wire stages. |
| [parent_discovery.py](../../tests/e2e/parent_discovery.py), [onpc_parent_discovery.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_discovery.pm) | GDM07, SEARCH06, PARENT02/03/04/19, FIX01 in case 3 or FIX02 in case 4 and explicit UI12 comparisons. | Every picker resolves choices by ID, highlights before Enter and verifies selection afterward. Existing child starts limits-off/zero; each child's returned values compare with its own observation. FIX01 stays after visible initial settings; FIX02 stays after launchable search but before launching Parent. |
| [parent_access.py](../../tests/e2e/parent_access.py), [onpc_parent_access.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_access.pm) | GDM07(standard), SEARCH01 → UI21 → SEARCH03 → SEARCH04(unavailable). | Direct standard-account selection and two fresh intended-recipient checks; semantic focus then independent focus observation; first character then readback, remainder then full readback; exact query-specific web suggestion and complete stable absence; no Enter on it. |
| [parent_terminal.py](../../tests/e2e/parent_terminal.py), [onpc_parent_terminal.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_terminal.pm) | GDM07(standard) → PARENT01(denied) → `onpc_window::close` (UI18). | Direct command once, management denial and exclusion, fresh active-window proof before close, desktop return with management absent. The legacy variant ID remains `terminal`. |
| [parent_about.py](../../tests/e2e/parent_about.py), [onpc_parent_about.pm](../../tests/integration/graphical_smoke/lib/onpc_parent_about.pm) | FLOW01(GDM07, direct-command PARENT01), ABOUT01/02/04/03 and explicit settings observation. | Functional GDM goes straight to the intended account and retains two fresh recipient checks. Read actual installed version/license/footer, close the real viewer, and return to the same child/switch/allowance. Open step-2 before the acknowledgement that permits closing the license. |
| [command_help.py](../../tests/e2e/command_help.py), [onpc_command_help.pm](../../tests/integration/graphical_smoke/lib/onpc_command_help.pm) | GDM07(Parent) → four explicit INFO02 bindings → final desktop-clear observation. | Parent/station help and manuals use bounded command stdout with identity/content checks, followed by independent desktop checks. No terminal or arbitrary command API. |

The extracted helpers are [onpc_about.pm](../../tests/integration/graphical_smoke/lib/onpc_about.pm),
[onpc_window.pm](../../tests/integration/graphical_smoke/lib/onpc_window.pm),
[onpc_documentation.pm](../../tests/integration/graphical_smoke/lib/onpc_documentation.pm),
`onpc_parent::launch_search_result`, [journey_blocks.py](../../tests/e2e/journey_blocks.py)
and [serial_harness.py](../../tests/e2e/serial_harness.py).
UI18 shares one close implementation across About and denial. SEARCH05 shares
one result-commit implementation across normal and empty-account discovery;
FIX02 still completes before its proof permits Enter. Recorder and serial
protocol mechanics stay in the harness, without adding a second runtime.

Further capabilities remain outside these seven recipes:

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
The [composition guard](../../tests/unit/test_e2e_case_composition.py) prevents
direct mechanics and case-plan imports returning to these recipes. Independent
window-close and search-commit regressions reject stale/missing proofs, uncertain
input, missing results and replay; real worker tests preserve exact stage order.
Run affected host checks for extraction; this audit explicitly defers live
consumer validation to a separate session. Changes to shared GDM, secret input, stage
reconciliation or public-UI routing also require their affected safety/harness
qualification; do not run the whole future matrix merely for an extraction.
## About block contracts

The [recipe](../../tests/e2e/parent_about.py) and
[worker](../../tests/integration/graphical_smoke/lib/onpc_parent_about.pm) compose
FLOW01, ABOUT01, ABOUT02 and ABOUT03. Shared launch stops at `parent-window`
before picker input; selection consumes its own fresh opened-list and highlighted
replies. Setup reattachment stays outside the customer entry block.
The About blocks live in `onpc_about`; the worker only composes them. All three
About/denial keyboard-close routes reuse `onpc_window::close` (UI18); the
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

ABOUT01 resolves the About surface and its product, version and license controls
by their public IDs, then reads the showing labels and reveals the license link.
ABOUT02 follows that ID-addressed link once and resolves the viewer and document
through the qualified provider route before reading public text. UI03 reads at most 1,024 characters and returns only whether
both GPL title and version/date headings match. Masked, hidden, unregistered or
oversized reads refuse; document contents never enter controller evidence.

`AccessibleUI.license_viewer_snapshot` is the external-provider exception for
GNOME Text Editor's license route. It resolves the unique application directly
under the public desktop registry, then its sole showing window and the
provider's `view` Builder ID (see the
[upstream template](https://github.com/GNOME/gnome-text-editor/blob/50.0/src/editor-page.ui)).
Application/window semantics remain inside this adapter; no window title,
geometry or document text identifies a target. Process ownership, complete
snapshots and prompt refusal remain mandatory. An already open editor refuses
before link input; unsupported handlers, multiple windows/documents and missing
IDs cannot fall back to generic text discovery. The close checkpoint reacquires
the active viewer and rechecks both GPL headings. Return requires viewer absence
and the active ID-owned About dialog in one fresh complete snapshot. This route
does not qualify ordinary document editing, saving, other handlers or overlay
About. Its installed qualification is recorded in the provider table below.

The fixed `check_e2e_license_viewer` capability qualification passed in run
`20260923T201618Z-50520052` (now outside runner retention).
`LicenseViewerProviderJourney` and `onpc_license_viewer_provider::run` enter
through fresh Parent/About observations, refuse a wrong entry proof, and open
real unrelated and empty fixture documents through the desktop user's service
manager. The adapter independently reads each fixture and refuses license-link
input while its viewer exists. After closing both fixtures and reacquiring About,
it follows the real license link, reads both GPL headings, and opens a second
viewer to prove ambiguous read/close refusal. Closing that fixture permits a
fresh license read and normal return through About/footer to the unchanged
selected child, switch and allowance. Fixture files are exclusively created,
contain no trailing newline (matching GtkSourceView's public buffer), and are
removed after observed closure; the guarded attempt owns failure cleanup.
Private evidence reconciliation, collection and owned cleanup passed. This
qualifies the capability only. Complete case 151 separately passed through
`parent_about.PLAN` and `onpc_parent_about::run` in run
`20260923T202401Z-9e9a5886`: fresh Parent entry, direct launch, selected child,
About/version, actual GPL content, normal license close, footer, About close and
unchanged child/switch/allowance. Capture reconciliation, product,
infrastructure, collection, owned cleanup and suite baseline restoration passed.

UI18 observes the ID-owned About window or qualified viewer's active state
before acknowledging Alt-F4.
The worker consumes that exact fresh proof once, closes once and waits for a
complete fresh absence observation with the expected underlying window present.
`license` durably opens step-2 before permitting its close; `license-closed`
precedes ABOUT04's semantic ID reveal and independent footer read, with no
positional navigation. The final close reacquires Parent and reads its displayed
child, limit switch and allowance without changing selection or settings.
`settings_checks={'parent-returned': 'parent-selected'}` compares immutable,
scenario-owned values before the terminal acknowledgement. Missing, changed,
stale or replayed observations fail, including after successful window input.

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
its own fresh opened-list and highlighted-choice replies before Enter; each
closed-picker result independently verifies the intended child. Functional
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
complete child-list collection, popup absence, highlight, selection, settings,
page navigation and scroll/reveal callables. All repository-owned targets,
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
Independent opened-list and immutable-observation tests cover reuse without
prior scenario execution; the empty-state block also accepts an independently
supplied Parent window. Failed/missing/stale/replayed observations prevent
further input, and uncertain whole-query input cannot be retried or reach FIX02.
Shared harness, access and About regressions preserve compatibility.

## Functional validation

Apply the canonical [UI automation mandate](../Mandates/UI-Automation-Mandate.MD).
Register each surface/control's shared ID contract before adding its consumer.
Missing repository-owned IDs require code changes exposing them through public
accessibility. External surfaces may use the approved provider exception.
Documentation records requirements and gaps; it does not qualify a route.
Do not dismiss unknown dialogs or bypass modal guards.

Both preview and guest readers use `public_automation_id` in
[accessible_ui.py](../../tests/e2e/accessible_ui.py). GTK/ATK control IDs use
`AccessibleId`; WebKitGTK control IDs use the public AT-SPI `id` attribute,
selected by its `toolkit=WebKitGTK` attribute. WebKit's generated `AccessibleId`
number is not the control identity. This is an explicit provider mapping, with
no label, role, JavaScript or geometry fallback. Qualification must exercise
public input/readback as well as ID discovery.

External provider gaps remain separate from the rich-editor adapter. The source mappings name logical consumer requirements, not IDs assigned by the
client. An ID route binds them to real provider-owned values; an exception route
records its actual selectors and qualification separately.

Repository-owned application fixtures have a separate implementation in
[gui_application.py](../../tests/fixtures/gui_application.py), with public
activity projections in [fixture_ui.py](../../tests/e2e/fixture_ui.py).
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
installed qualification in the rows below. Prefer the routes in AGENTS.md's
exception. Missing IDs are an implementation gap, not a requirement to wait for
an upstream change. Qualification is limited to the exact scope recorded in a
row; retained ready scenario bindings do not broaden it.

For each supported route, qualify actual input/readback, application/surface
ownership, ambiguous and wrong-target refusal, focus and result observation.
Secret routes additionally require intended-recipient and wrong-recipient refusal guards, empty masked field,
capture, single-use and uncertain-input checks. Refuse if those guards cannot be
established. Do not present semantic or visual selectors as provider-owned IDs.

| Provider / surface | Current gap and route-specific return condition | Affected consumers |
| --- | --- | --- |
| GNOME Shell desktop, panel, app grid, sessions, notifications, lock | Shell `50.1-0ubuntu1.2` exposed no nonempty public IDs. On the pinned Ubuntu 26.04, English-GDM, baseline-keyboard image, `AccessibleUI.standard_shell_desktop(no_prompt=True)` qualified unique Activities control and complete prompt-free observations for the fresh Parent and standard fixture buses through `check_e2e_fresh_desktop`. `check_e2e_desktop_keyring` also qualified the independent standard desktop readback after the prepared gcr Cancel branch below. `AccessibleUI.shell_search_snapshot` qualified fresh Parent search, result focus and launched window in case 3 (run `20260922T212944Z-ad23b979`). The fresh Parent split-query/result-focus and Escape/empty-field/Super/dismissal slice passed `check_e2e_shell_search_results` in run `20260923T180845Z-4df4db55`. `check_e2e_shell_search` independently requalified administrator launch/close and standard-account split-query readback, exact web description and stable launcher/window absence in run `20260923T191129Z-64de2a7a`, with private collection and owned cleanup; see [exact scope](#search-and-standard-sign-in-contracts). Other necessary lock, retained-session and product-panel observations remain unqualified. Session, power and connectivity inputs use shared system commands. | Fresh DESK01 Parent/standard and prepared standard gcr return, Parent SEARCH01/02/03/04/05/06 and standard SEARCH01/03/04 branches ready; other necessary DESK01/06–08/10/12, SEARCH01–06 and PANEL01–03 GUI bindings pending; DESK03–05, DESK11 locked-session return and LIFE02/03/06 inputs are system helpers |
| GDM greeter | Historical installed/product-free list, recipient and Escape qualification remains harness evidence. Shared customer entry selects only the intended account, verifies two fresh recipient proofs, delivers once and independently observes the desktop or product denial. `onpc_gdm::sign_in_challenge` qualified two distinct Parent GDM challenges with independent desktops and shared DESK04 logout through `check_e2e_challenges` (run `20260924T192200Z-c833e973`), on the pinned Ubuntu 26.04 English-GDM, baseline-keyboard image. Its separate wrong-recipient exercise, durable assertions, reconciliation, private collection and owned cleanup passed. Wrong-account tours and keyring exercises remain harness-only. Retained locks, other challenge recipients and new account bindings remain pending. | GDM01–03/05–09 for unavoidable graphical entry; distinct Parent GDM challenge binding ready; GDM04 harness safety only |
| Graphical VT6 getty/login | Retained routes refuse before image, secret or input access. Qualify a dedicated recipient/input adapter; serial proof cannot authorize graphical secret input. | Retained VT6 qualification modes |
| MATE Polkit agent | No provider registry binding exists for the kiosk agent. Qualify the real MATE challenge owner, displayed request and selected administrator, sole empty masked focused field, cancel/rejection/approval results and secret guards. | AUTH01/02, station approval and request flows |
| Shell Polkit agent | Qualify the real product approval challenge, selected-recipient checks and approval/cancel results. Supporting package/account commands do not require an unrelated GUI challenge. | AUTH01/02 product approval |
| gcr keyring prompt | `AccessibleUI.keyring_cancel_target` / `cancel_keyring_prompt` qualified the prepared standard-account login-keyring Cancel route through `check_e2e_desktop_keyring` (run `20260923T051904Z-f0d79b4d`, outside runner retention). Recorded tuple: Ubuntu 26.04, gcr `3.41.2-6`, Shell `50.1-0ubuntu1.2`, actual gcr locale `en_US.UTF-8`, keyboard sources `[["xkb", "us"]]`. The semantic adapter requires a unique live gcr application owner, visible Login Keyring dialog, sole empty masked focused field and unique enabled Cancel; the application container itself has no visibility requirement. It invokes Cancel once, observes disappearance and independently observes a prompt-free desktop for two seconds. Host regressions reject wrong/ambiguous ownership, hidden/disabled input, lost focus, replacement/queued prompts, incomplete absence and uncertain input. Preparation activates installed `PrivatePrompter`, verifies its ownership of `SystemPrompter`, and locks/requests unlock of the existing Login collection through Secret Service without reading or supplying a password. Separate fresh Parent and standard attempts passed private collection, reconciliation and owned cleanup. Other locales, provider tuples, Parent keyring cancellation and automatic search-middleware composition remain unqualified. | Prepared standard DESK01 gcr Cancel return ready; other keyring handling and secret routes pending |
| GTK native file chooser | Qualify each caller-owned dialog route, exact selected-file readback and wrong-dialog refusal. | FILE03, FEED06, FEED08 native routes |
| GNOME portal / Nautilus chooser | Partial Builder IDs do not identify the full dialog and dynamic file selection. Qualify the actual portal route and selected-file readback. | FILE03, FEED06, FEED08 portal routes |
| Default document/license viewer | `license_viewer_snapshot` and `check_e2e_license_viewer` qualified Parent's actual GNOME Text Editor handler in run `20260923T201618Z-50520052`: Ubuntu 26.04, editor `50.1-0ubuntu0.1`, actual provider locale `en_US.UTF-8`, keyboard sources `[["xkb", "us"]]`. Live independent entry, wrong-entry/unrelated/empty content refusal, ambiguous viewer/close refusal, bounded GPL headings, active viewer, normal close/absence, owned About/footer and unchanged Parent settings passed with private collection and owned cleanup. Wrong ownership, masked/hidden content, incomplete trees and uncertain input also retain host regressions. Support is limited to this tuple and route; other handlers and document workflows remain pending. | Parent ABOUT02/03 binding ready; FILE08, FEED08 and other About bindings pending |
| Terminal | Retired as supporting infrastructure. Shared FILE01/02/06 execute fixed commands over guarded SSH; INFO02 already reads bounded stdout. Historical Ptyxis qualification creates no customer requirement or provider dependency. | No Terminal GUI consumers |
| GNOME Settings Users / Date & Time | Retired provider work. Use protected spare-account commands and read-only date/timezone commands in shared infrastructure. Observe the app refresh/fallback and time behavior independently. | ACCOUNT01/02, AUTH04 and TIME05 system helpers |
| DING desktop icons | No provider registry route exists. Qualify the declared desktop icon, focus/selection, activation and independent launched-window result inside a DING-specific adapter. | APP01/02 desktop launch route |
| Nautilus Files | Qualify only the explicitly tested file-manager enforcement launch. Shared commands prepare, copy, rename and open supporting files; product file choosers retain their separate GUI assertions. | FILE04 and declared APP01/02 file-manager launch routes |
| File Roller archive viewer | Qualify archive/entry identity, open, content and close. | FILE08, FEED08 |
| Registered document editor | Read the intended document and activity for product-output/retention assertions. Use a shared direct handler launch. Ordinary attachment source mutation uses FILE05/09 commands; GUI edit/save is limited to declared retained-work assertions. | FILE08, FEED08 and APP03/04 retained work |
| Lunar Client, AppImageLauncher, Shell tray and Minecraft | No bindings are qualified. Require the prepared real-AppImage profile, allowed autostart control, complete login-interval tray/window observations, specific same-route denial, game launch/local-world action and genuine Quit. [Preparation and observation gate](#lunar-client-preparation-and-observation-gate); refuse incomplete ownership/absence observations. | E2E-052/case 253; APP01/02/03/06, UI18/22 and FIX05 |

Provider implementation and qualification are scheduled only by the
[E2E execution plan](E2E-Execution-Plan.md). Its queue places the following
capabilities before their consumers; these are task identifiers, not readiness
claims or an alternate execution order:

| Provider work | Queue owners |
| --- | --- |
| Necessary GDM entry, isolated keyring safety and system session helpers | 003a/003ba unavoidable login observations; 003b isolated keyring qualification; 003c/003d shared system operations; case 1 remains harness qualification |
| Product search, direct launch and license viewer | 001s product search; 001t direct-command denial; 185l product license viewer; retained scenario regressions |
| Kiosk MATE prompt and request results | 019a, 019, 020a, 020 |
| Overlay Shell prompt and request results | 048c, 048d, 048b |
| Shared file preparation and tested file-manager launch | 036 shared file preparation; 036f/036a explicitly tested file-manager enforcement launches |
| Installed feedback Open/Cancel, with its actual native/portal provider binding | 037; attachment composition 038 |
| Installed feedback Save/Cancel, with its actual native/portal provider binding | 037a; export composition 045 |
| Text documents, archives and saved edits | 195a, 195, 196 |
| Browser/mail/legal destinations | 185w, 185v, 185s, 185p and overlay 185o |
| Shared system lifecycle helpers and required unlock observations | 005/006 package commands, 007 reboot command, 042/043a necessary lock/unlock observation, 044a shared window activation, 193 network command, 166 suspend command |
| DING desktop fixture launch | 036b |
| System account and clock helpers | 184/184b/184c shared account operations; 191 read-only clock/timezone commands |
| Snap, Flatpak and game fixture installation before launch | 109p → 109/109a; 116p → 116/116a; 126p → 126a |
| Reviewed external feedback submissions | 150a profile/authorization → 150 and its surface/result consumers |
| Lunar, Minecraft and login observation | 295 → 296 → 296a → 296b → case 253 in 297 |

There is no active customer requirement for generic Shell notification handling,
a PDF reader for the ZIP/text diagnostic export, or graphical VT6 login.
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
qualifications below; case 2 remains pending. This qualification
supplies no complete-scenario credit.

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

The live slice proved greeter refusal, independent valid administrator entry,
unregistered-command/wrong-artifact/wrong-VM/wrong-attempt/replay refusals,
successful command completion and the final reboot notice. Capture
reconciliation, private collection, owned worker shutdown, baseline restoration
and lease completion passed. The durable after-cleanup result is
`output/test-runs/privileged/allocations/onpc-e2e-evidence-1kzlp7dr/event-000017.json`;
the report is `output/test-runs/host/reports/20260924T215601Z-8f5800a9/report.md`.
This capability qualification records its three assertions; the envelope's
complete-product result is `not-run`. LIFE04 installation composition is qualified
separately below; other package operations and complete case 2 remain pending.

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
and complete case 2 remain unfinished.

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
install/reboot/administrator-return slice; complete case 2 and other lifecycle
bindings remain pending, and the complete-product result is `not-run`.

### Reachability and result checks

The following ID route applies to repository-owned UI and ID-capable providers.
External adapter routes follow the same reachability and result guards using
their qualified resolution method.

Resolve each target by its owned public ID or qualified external-provider adapter.
Prefer a provider's direct ID lookup. Otherwise use one fresh complete scoped
snapshot for prompt, ownership and target checks at that input boundary. Invoke
an available public accessibility action directly; do not focus, scroll, reveal
or traverse the tree again first. A clipped or covered control can still be
actionable. Truly hidden, disabled or defunct application state refuses input.

When no direct action exists, use the declared semantic reveal/focus/keyboard
route, then reacquire the same ID or qualified provider target. Observe focus for
keyboard input; do not derive key counts from tree/list position. Content that
must be read may need reveal. No snapshot survives input or a session transition.
A following result observation is fresh and independent of input completion.

Do not call product methods, set widget values directly, read saved policy or
treat an action API's success as the customer result. Disabled settings remain
readable. Screenshots have no cosmetic pass/fail authority; an external image
selector must stay inside its explicitly qualified provider adapter.

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

Case **3 / E2E-003/existing-and-new** reuses this contract for app search,
existing-child selection, dynamic discovery and return. Preserve the original
existing fixture's limits-off/zero-allowance expectation and the new child's
visible remaining-time section. The fixed account fixture
runs only after fresh visible settings and a durable phase boundary while Parent
stays open. Each picker expansion uses UI14's ID-addressed navigation;
a separate checkpoint verifies the intended highlighted row before Enter,
then another requires the closed picker and intended child's displayed settings.
Both children expose App Limits search and rule-filter controls through normal
tab navigation. Returning to Screen Limits and the original child must preserve
their independently recorded switch and allowance values, including disabled
allowance reads. This case changes no time policy and claims no child-session
enforcement; E2E-005 owns settings changes followed by child use.

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
Enter and independently verify the selected account's prompt. Both this worker
and the shared Parent selector use `onpc_journey::navigate_choice` to validate navigation replies.
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
overlay scope, authentication and case 57 remain pending.

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
binding consumes the active owned window proof before Alt-F4;
`AccessibleUI.parent_search_closed` requires a prompt-free desktop and complete
fresh absence of management, denial and startup-error windows. Private collection,
worker shutdown and owned cleanup passed. Actual Shell tuple retained in both
close-readiness observations: `50.1-0ubuntu1.2`, provider locale `en_US.UTF-8`,
keyboard sources `[["xkb", "us"]]` on the pinned Ubuntu 26.04 image. This supplies
no complete-scenario credit; the FIX02 empty-result binding remains pending.

`check_e2e_shell_search_results` qualified the fresh Parent SEARCH01/02/03/04/06
slice in run `20260923T180845Z-4df4db55` (now outside runner retention):
`onpc_shell_search::run` supplies the search entry independently of the
`AccessibleUI` observations; `shell_search_field`, `focus_search_field`,
`search_ready` and `search_query` observe the empty field, fresh focus, `O`, then
`Oh No! Parent Control`. `launchable_result` and `focus_search_result` identify
and focus the product launcher; the unrelated `Terminal` binding refuses.
Escape clears the query, `shell-search-cleared` observes the empty field, Super
closes Overview, and `shell-search-dismissed` requires a prompt-free desktop and
complete-tree search-field absence. Private collection and owned cleanup passed.
This qualifies only the pinned Shell provider environment described in the
[provider catalogue](#external-provider-qualification), with no launch,
standard-account unavailability or complete-scenario acceptance credit. Other
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
focus. SEARCH03 consumes the fresh focus proof, types the first
character once, reads it at `search-started`, types the remainder once and
reads the exact full query at `search-entered`. Each segment uses the existing
bounded pace. Input uncertainty is terminal; no repair or replay is permitted.
The app-grid acknowledgement opens step-2 before its first input.

SEARCH04's unavailable result composes UI03 and UI11. The exact query and
query-specific web description must remain showing while complete fresh
accessibility traversals exclude the product launcher and management window
for two seconds within the 45-second adapter deadline. Missing or defunct
subtrees restart that interval. Resolve the external result and description
through the qualified Shell adapter, then verify their semantic association and
text; the repository-owned management window remains ID-addressed. Never press
Enter on the web suggestion.
This observes launcher unavailability; direct-command denial and time enforcement
belong to their own scenarios.

Current prompt middleware has host-only recognition/refusal for MATE Polkit,
Shell Polkit, keyring and unknown authentication modals, including late
arrivals. Routine customer/search flows perform no automatic prompt dismissal. The separate
`AccessibleUI.cancel_keyring_prompt` route is qualified for the prepared standard
gcr harness challenge described in the provider catalogue: masked-field focus, one Cancel,
observed disappearance and independent desktop readback without input replay.
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

The ordered catalogue owns feature-block status and implementation order.
These existing services support those blocks within their current qualified
scope; reuse them without building a second runner or counting their checks
as customer behavior.

| Need | Implementation | Contract |
| --- | --- | --- |
| Public UI read boundary | [accessible_ui.py](../../tests/e2e/accessible_ui.py): `run`, `wait`, `observation`, `nodes` | All registered operations and standalone waits use the same element-independent observation scope. Composed lookups reuse a complete tree and its scoped projections until input, a pending predicate, a failed read or an accessibility-client reset invalidates it. Separate operations always start fresh. Protected text scopes stay distinct; tolerant/incomplete reads never seed complete observations. |
| Installed app prerequisite | [suite_lease.py](../../tests/e2e/suite_lease.py), [installed_setup.py](../../tests/e2e/installed_setup.py) | Bind package/helper bytes, install and reboot once per suite, then capture the powered-off version snapshot. Feature cases restore it without reinstalling or package validation. Failure is terminal. |
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

Open `tools/watchvm` as the desktop user before starting a VM task. Its
resizable command pane follows the shared guarded command runner independently
of graphical frames: installed-system tests (including the pre-E2E test run),
app-snapshot preparation, SSH work, VM lifecycle stages and cleanup are visible.
Reviewed text commands show the guest command, live stdout/stderr and exit status.
The installed guest helper forwards APT update/install/upgrade command text and
both output streams while each command runs, including suite preparation.
Package commands use a guest PTY with `TERM=xterm-256color`, so the package's own
colored notices are emitted. A read-only GTK 4 VTE terminal renders ANSI colors,
carriage returns and display controls with an Ubuntu terminal palette. The viewer
has no shell/PTY or input channel; clipboard/title control payloads are discarded.
The pane keeps a bounded recent transcript; the runner's private artifacts retain
complete diagnostics. Password input, binary transfers and private observation
programs/replies are omitted and labelled. The spectator receives no input route
or SSH/libvirt connection. Only the authenticated invoking user receives command
text; opening or closing the viewer cannot cancel or control the task.
The shared lease attaches the existing display collector at every VM start.
Maintenance retains it between commands; viewer reconnection never triggers a
new VM connection. The frame feed remains observation-only; customer actions use
the semantic input contract. New tasks must obey the
[VM observation mandate](../Mandates/VM-Mandate.MD#vm-observation-mandate): reuse these
command, lease and progress interfaces, and enter `watch_activity.operation`
with fixed nonsecret intent before VM work. The footer shows that intent through
blocking work even without a recorder. Do not create per-consumer capture,
transcript or intention infrastructure. See the
[shared viewer contract](../../tests/e2e/README.md#optional-live-viewing).
Development activation is `none`; `./setup.sh --test-tools-only` installs the GTK 4
VTE dependency (`gir1.2-vte-3.91`) on existing hosts. Reopen an already running viewer
after code changes. Refresh installed dispatcher changes through the same setup mode.

The recorder automatically publishes each selected case's numeric ID, title,
invocation position/total and current phase description to `tools/watchvm`.
The title appends `- (case time/total time)` in whole minutes, or hours and
minutes from one hour onward. Case time includes preparation; total time runs
from invocation startup. An independent progress heartbeat keeps the next case
visible during outer cleanup and leasing, with `Preparing VM: ` followed by
the latest controller stage output until its first step starts. Display feed
loss still clears stale VM pixels, and expired progress returns to waiting.
Snapshot creation, deletion and restoration publish their action and snapshot
name before the operation starts. That message reserves the footer until the
operation returns or fails, with its own elapsed duration; controller logs and
worker messages cannot replace it. This includes both app and baseline snapshot
restores between cases and during cleanup.
Keep descriptions in `scenarios.json` complete: the viewer uses that same text.
Before a Perl building block acts, call
`onpc_progress::operation('Fixed nonsecret description')`; use literal prose and
redacted role labels, never credentials, entered text or observed account names.
The shared publisher keeps the latest operation in the private worker directory
and logs it before input. The controller only forwards literal labels declared
by the maintained worker. Public UI adapter operations declare their prose in
`ui_observations.OPERATION_LABELS` and publish it before observation/action.
[Progress regressions](../../tests/unit/test_e2e_progress.py) require messages for
new public worker blocks and UI operations, and check inventory/recorder timing.
Viewing cannot authorize input or change scenario acceptance.

1. Select one inventory variant and its complete visible result. Identify the
   required fixtures and surfaces. Reuse accepted setup; installation mechanics
   do not become customer assertions. If a shared operation is missing, name the
   blocked action and implement only that operation with this consumer.
2. Compose a worker module from the ordered blocks and selected recipe above.
   The established cases demonstrate current working sequences; migrate their
   selectors/input routing while preserving recipient-safety assertions. Use normal
   app-search input and functional checkpoints.
   The picker-open checkpoint activates its ID-addressed toggle. UI14 supplies
   semantic focus or bounded keyboard traversal with focused-ID observations.
   A checkpoint verifies the intended highlighted row; Enter selects it, and a fresh
   checkpoint verifies the closed picker and displayed child/settings.
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
   installation/reboot belongs only to suite snapshot preparation. Tested package
   installation/reboot in E2E-002/026/027 remains a real customer action.
5. Reconcile that variant's inventory declaration, requirements, visible
   assertions and evidence. Customer families use `category: customer-journey`.
   The `installed-digest-verified-product` prerequisite selects the suite's
   installed snapshot and package-bound bootstrap, without a case-ID branch in
   the executor. Package lifecycle scenarios omit it, explicitly declare
   `declared-package-lifecycle-fixture`, and provision their declared initial
   package from `onpc-baseline` as part of the tested package behavior. A feature
   case cannot omit its installed prerequisite or fall back to installation.
   Runner-only product-free harness checks may use baseline without installing.
   Declare
   `fixture-credentials-via-secret-api` when using authenticated input. A ready
   callback must exist, and all required steps must have real implementations.
   Registration enables execution; only complete acceptance earns coverage.
6. Test changed shared boundaries with the actual Perl helper and Python
   recorder. Then finish edits, build fresh artifacts and run the exact variant
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
| Displaced or covered controls | Resolve public automation IDs and use semantic activation/focus; never derive input from pixels, extents or framebuffer size. Missing app IDs require app changes. |
| Installed greeter differs from the baseline account list | Use the qualified GDM adapter and independently prove the intended secret recipient; see external-provider qualification. |
| GDM scrolls its account list | Use ID-addressed reveal/navigation, reacquire the intended account and verify its own empty focused password field before secret input. Never use outlines, positions or image absence as proof. |
| Parent search shows only an online suggestion for a standard user | The [launcher contract](../SystemDesign/Broker.md#accounts-and-roles) intentionally restricts app-grid discovery to administrators. Match the exact query, web-only suggestion and empty application-result area. Do not press Enter on the suggestion or invent a denial dialog. Executable denial belongs to the separate direct-command variant. |
| Keyboard assumptions select the wrong child or menu item | Use UI14's ID-addressed navigation, verify the intended highlighted row, then press Enter. Verify the selected child independently. Ordinary Parent launch/reopening uses PARENT01's direct command and independent window result; only explicit app-grid discovery cases use whole-query SEARCH05/06. |
| About footer starts below the viewport | Resolve the footer by ID. Invoke an available direct action without preliminary scrolling; reveal only when needed to read required content. No fixed scroll distance, dialog size or pixel match. |
| An acknowledged action has no durable evidence, or belongs to the wrong step | Store the observation and any required next-phase start before publishing the reply; guard ownership again after storage. An acknowledgement may immediately permit input. Storage or guard failure latches terminal failure. |
| A stale observation appears to prove returning to the same child | Reconcile one fresh semantic result per ordered stage. Compare the returned child, switch state and allowance with the initial displayed settings. Missing, reused or reordered evidence refuses. Worker exit zero alone cannot pass. |
| Choosing package inputs | Build artifacts when the installed product needs to include current changes. Runs use the supplied artifacts and allow concurrent checkout edits; private staged artifacts remain integrity-checked. |
| VM is off but baseline acquisition reports `guard:source-changed` | Inspect the saved run phase and inactive configuration through the approved readers. An interrupted `isolated` setup can retain the test configuration. Use recorded graphical cleanup; do not edit the journal, recreate the baseline or treat powered-off status alone as restored state. |

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
