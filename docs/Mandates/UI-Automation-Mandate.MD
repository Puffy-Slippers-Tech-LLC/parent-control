# UI automation mandate

This mandate owns UI route selection and target/input safety for host previews,
qualifications and installed cases. The [catalogue](../TestAutomation/E2E-Building-Blocks.md)
owns callables and qualified scopes; the [coverage allocation](../TestAutomation/UI-and-E2E-Coverage.md)
owns which layer exercises each matrix. Read this mandate when changing either
layer's automation, including shared workers.

## Result-oriented test scope

E2E tests verify product functionality through realistic customer journeys.
Start with the customer's goal and the meaningful outcome that proves it was
achieved. UI interactions are the means of exercising that journey, not its
testing targets. A saved allowance governing the child's access, recovered
unfinished work, or a retained feedback draft is a customer outcome; a widget's
value or clickability alone does not establish the journey.

Individual control behavior and local validation belong in UI tests when they
protect a useful component function. E2E does not require a smaller copy of each
UI test just because the component is installed. Keep public text or control
state in E2E only when it communicates a meaningful customer result, such as
the child's remaining time, a rejected change, or available product information.
Appearance is outside E2E; the presentation exclusions below still apply.

Simplify the UI operations as well as the assertions in completed and planned
cases. Choose the shortest reliable public interaction sequence that achieves
the customer goal. Reuse an open surface, avoid repeated dialog visits and
unchanged readbacks, and remove preparatory control exercises unrelated to the
journey. Preserve distinct intermediate customer outcomes and shared target,
ownership and input-safety guards. A capability's qualification matrix is not
the recipe for each consuming customer case.

For every step, observation and acceptance condition in a new case or E2E
maintenance change, ask:

1. Does it prove a core product behavior?
2. Is it necessary to reach or observe that behavior safely?
3. Can it be removed, combined or replaced with a simpler, more reliable
   supported operation that preserves the same product result?

Apply this review to implemented tests, shared flows, recipes, qualifications,
completed-task requirements and unfinished briefs. Accept equivalent supported
paths to the same result; require a particular desktop or provider path only
when that integration is itself under test. Before adding an adapter, retry or
longer timeout for an intermittent dependency, establish that the dependency
is necessary. Remove incidental dependencies at their shared owner and update
their consumers. Do not weaken enforcement, authorization, persistence, child
isolation, retained work, recovery or lifecycle assertions. Credential-recipient,
ownership and uncertain-input guards remain mandatory. The
[journey review contract](../TestAutomation/E2E-Execution-Contracts.md#product-focused-journeys)
owns implementation and documentation reconciliation; historical completion
does not qualify a changed route.

In both layers, a toggle's final on/off state or a selector's final value is
sufficient when that value is the feature being tested. When the choice controls
another function, verify that function too; a selected radio indicator alone does not
prove that language, permissions or behavior changed. This control-level rule
does not make an isolated widget check an E2E customer outcome.

Do not make popup opening/closing, expansion, highlight/selected rendering,
focus movement, caret position, per-keystroke display, button response animation
or dialog dismissal a separate acceptance condition when the final result already
proves the operation. Remove such assertions rather than moving them from E2E
to UI tests. Opening a dialog or waiting for a control can remain necessary
shared navigation; it is not an additional product test. An exit, cancellation
or dialog lifetime is still a result when it determines saved data, submission,
return to the child/greeter or preservation of work.

Use representative choices and meaningful boundaries. Cover each distinct
functional outcome, rejection, recovery and interacting condition; do not expand
independent choices into an exhaustive GUI Cartesian product. Prefer lower-layer
checks for pure value combinations. Installed E2E verifies the customer's
persistence, authorization, policy enforcement, lifecycle and integration
outcomes through the interactions needed to reach them. A historical detailed
test does not require future repetition.

Retain intermediate observations when a later result would conceal a distinct
functional failure, such as an unintended save, crossed child identity, premature
access, lost work or an incorrect policy transition. Preserve input ownership,
secret-recipient, keyboard-recipient, ambiguity, disabled-control and uncertain
input guards below. These guards belong in shared automation and are not reasons
to add focus/rendering acceptance to every customer case. Harness safety
qualifications remain separate from product journeys.

## Application UI API

All existing and future host UI tests, installed E2E tests and their task briefs
must use the [Application UI API](../TestAutomation/Application-UI-API.md) for
repository-owned product reads and input, including test setup and result
observations. The rule includes Parent, both request surfaces, shared dialogs,
the feedback editor and child panel. Follow the API's
[calling contract](../TestAutomation/Application-UI-API.md#calling-the-api),
[canonical values and adapter boundaries](../TestAutomation/Application-UI-API.md#canonical-values-and-portability),
and [lifecycle guards](../TestAutomation/Application-UI-API.md#reliability-and-lifecycle).
Stable-ID operations run the actual controls' normal handlers; current ownership,
effective sensitivity, logical visibility, modal and validation guards remain
mandatory. Future desktop ports implement the same adapter contract and public
IDs; consumers and customer cases must not add desktop branches.

Use the same shared test facade and operation helpers in host UI and installed
E2E tests. Cases supply finite values and expected outcomes; shared helpers own
endpoint binding, surface discovery, control operations, waits and refusal
guards under the [shared support guide](../../tests/support/README.md).
Extend those helpers before adding a second host or guest implementation;
compatibility callable names do not permit a legacy input route. Direct selector
values require no popup, accessibility, focus, scrolling or native-input
qualification. Product editor operations use the fixed editor API; arbitrary
caller-supplied JavaScript, private backend edits and credential delivery through
this service are prohibited. Never substitute toolkit calls, private widget
state, AT-SPI product reads/actions, native key/pointer injection or an alternate
transport after refusal. Existing external-provider and authentication guards
continue to apply outside the product API.

Read-only waits may reacquire current API state within the original deadline.
Mutations stay outside retry predicates. A successful setter and a returned
control value do not establish save completion, approval, persistence or policy
effects when those are the requested outcome. Editor assertions read the public
document delta independently of toolbar state. Never replay an uncertain
mutation automatically; observe its public result and make a new explicit
decision under the API lifecycle contract.

Isolated implementation tests may inspect synthetic adapter or helper objects
directly to verify their own contracts, such as weak-reference cleanup,
translation-context disposal or native text attributes. These tests do not
launch or operate a product surface and establish no customer or Application UI
API acceptance. Reuse the lowest effective existing fixture scope. This does
not permit private observations, toolkit input or alternate transports in any
product UI test, its setup or its result assertions.

## Route selection

- **Choose the route by the feature under test:** Application UI API operations
  exercise product dropdowns, toggles, textboxes, dialogs and the child panel.
  External provider operations exercise authentication and explicitly tested
  operating-system launch routes or file choosers. All other
  desktop, Shell and GDM work is harness infrastructure. Use the simplest
  reliable supported shortcut, SSH command or public system API, in shared
  libraries; never duplicate it in a case. This applies to completed tasks and
  retained implementations as well as new work.
- **System operations:** Use direct commands for logout, reboot, suspend,
  connectivity, fixture account/file management, clock/timezone reads and
  supporting-tool launch. Use Super+L or the supported session lock API for
  explicit locking; switch to the greeter without Quick Settings or power-menu
  navigation. From an already locked session, invoke the shared greeter-return
  command without unlocking or locking again. Logout uses
  `gnome-session-quit --logout --no-prompt` for the bound desktop user. Choose
  and validate the route before input; never try a second
  route after an uncertain command. Preserve the owned VM, fixture/session
  identity, command transport, observation and cleanup contracts.
  Launch supporting tools through their supported command or fixed shortcut.
  Do not open a terminal merely to type a command that guarded SSH can execute.
- **Preparation lifetime:** For VM work, follow the
  [baseline contract](VM-Mandate.MD#vm-host-setup-and-baseline) for reusable
  guest prerequisites and attempt-owned state. Host setup follows
  [one-time setup](../Approval-Tools.md#one-time-setup); shared fixture construction
  follows the [support guide](../../tests/support/README.md).
  UI workers verify readiness and fail on missing/stale prerequisites; they
  never install or repair prerequisites during a test.
- **GDM and login:** Reuse one shared entry helper that goes straight to the
  intended account. Use only the minimal selection/keyboard authentication
  needed when a graphical login or unlock is required. Prefer direct public
  focus of the identified account; otherwise use bounded Up/Down navigation
  with freshly observed account identity and focus, then Enter. Escape returns
  from an observed selected-account prompt to the account list. Do not derive
  key counts from an assumed account order or use mouse geometry for these
  routes. Fresh secret-recipient checks remain mandatory; deliberately visiting
  a wrong account, repeatedly
  opening/dismissing prompts, and exercising keyring dialogs belong to harness
  safety qualification, never routine customer journeys. SSH authentication
  cannot substitute for a graphical PAM denial or retained-session unlock that
  the product case must observe. Locking cannot substitute for natural expiry.
  Before designing a new unlock binding, establish whether that provider offers
  a password challenge or blocks authentication with a native time restriction.
  A restriction without a password field cannot satisfy an authenticated-denial
  assertion. Investigate a mismatch in the actual child's session under the
  [live diagnosis contract](../../tests/README.md#live-diagnosis-before-another-repair-attempt)
  before another repair, and retain any required behavior decision. Reuse the
  [qualified denial routes](../TestAutomation/E2E-Building-Blocks.md#retained-child-time-restriction-and-greeter-return-qualification)
  only for their stated entry/result; never force a password field or activate
  a request-more-time action to dismiss a restriction.
- **Incidental provider variance:** When login, unlock or desktop navigation only
  transports the journey to a product surface, require the intended account and
  usable destination, not a particular prompt sequence. Do not manufacture a
  password challenge or a time-limit denial for a preference or app-navigation
  test. Shared helpers may use a qualified direct-return or authentication branch
  according to a fresh public observation; an absent challenge requires no secret
  delivery. Explicit authentication/enforcement tests retain their required
  challenge or denial result. Unknown prompts, ambiguous destinations and
  uncertain input still refuse. Apply the
  [product-focused journey review](../TestAutomation/E2E-Execution-Contracts.md#product-focused-journeys)
  before expanding provider work to accommodate unrelated variance.
- **Observe the tested result:** System-command success establishes only that
  input was accepted. Independently check the required destination/session and
  the product's public result. Testing product behavior across logout, reboot,
  account changes or offline use does not make GNOME's menus or Settings pages
  product features. Only an explicitly tested product integration, such as its
  app-grid entry, file chooser or external link, needs that GUI route.

## Product integrations

- **Attachment handoff:** Treat the operating system's file chooser as an
  external tool. Prepare declared synthetic files through shared commands; use
  supported public APIs and the minimum necessary shortcuts in one shared
  adapter to supply them to the real chooser. Test the app's Add files entry,
  returned attachments and unchanged attachments after Cancel. Folder browsing,
  per-row selection choreography and selecting a candidate before cancellation
  are not customer acceptance requirements. Keep correct-dialog ownership,
  bounded input, exact-file guards and independent app readback. Do not inject
  attachments into private app state or replace the live handoff with a stub.
- **External links:** Acceptance stops at the product's link being available
  for activation:
  resolve its public ID through the Application UI API and check logical
  visibility, sensitivity and the supported `activate` operation. Viewport clipping does not require following the link.
  Do not activate the link, inspect its URI/destination, launch a handler or
  validate what opens. This applies to Help, website, portal, privacy, mail,
  license and legal-file links across all tests. No browser/mail/document
  provider qualification, page/content/DOM checks or external close/return
  workflow belongs to link acceptance. Never pin, install or configure Firefox,
  Chrome or another handler for a test. Ordinary product clicks continue to use
  the current user's system default handler. In-app About and Privacy disclosure
  checks, kiosk external-action restrictions and explicitly authorized feedback
  submission remain separate product features.
  Rich-editor link formatting is a separate owned editing feature: check its
  synthetic link values in the API's public document delta without navigation.

### Ordinary app entry

Use the shared command block for setup and reopening. Both commands run as the
bound active desktop user through guarded transport and independently observe
their public result. Reusing an already open window needs no relaunch.

| Surface | Required shared block | Independent result | Explicit GUI exception |
| --- | --- | --- | --- |
| Parent | [PARENT01](../TestAutomation/E2E-Building-Blocks.md#app-grid-search-and-parent-launch), directly or through FLOW01 | Expected management window or access denial | A case testing app-grid discovery, launch or unavailability uses the full query `Oh No! Parent Control` and opens a launchable result when expected. |
| Child overlay | [REQUEST02](../TestAutomation/E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), directly or through a composite | One usable overlay with the fixed child identity | A case testing graphical discovery/launch uses its qualified UI entry block. |

Declare each graphical exception in case metadata and its recipe. Keep installed
commands, source callables and qualified bindings in the catalogue. Do not copy
launch code into cases. Session identity, prompt refusal, single-use execution
and independent result checks apply to both routes.

## Target identity and provider exception

- **Daily allowance selection (all UI and E2E tests):** Reuse PARENT06 in the
  [daily allowance contract](../TestAutomation/E2E-Building-Blocks.md#daily-allowance-selection), including Custom
  validation and independent saved-allowance readback. Its Application UI API
  route requires no popup, focus, native input or geometry. Cases retain their
  distinct validation and per-child persistence assertions.
- For GUI operations required by the feature under test, and unavoidable
  graphical authentication, except for the external-provider exception below,
  every automated UI target
  must be resolved by a stable public `automation-id`,
  scoped to its owning application and surface. Shared controls use one ID
  contract across surfaces, suites and helpers. Reject missing, duplicate,
  ambiguous and wrong-owner IDs.
- IDs must not derive from translated labels, names, roles, titles, rendering,
  tree/list position or geometry. Do not use coordinates, extents, image matching,
  layout, display scale, scroll position, window titles, frame roles, color or
  theme to identify a target, route input, establish readiness or decide
  acceptance. These constraints apply when GUI interaction is necessary;
  they never require replacing a system command with GUI setup.
- Add a missing ID to repository-owned application or fixture code before
  implementing its consumer. Product controls expose it through the Application
  UI API. Supporting fixture apps retain their shared activity adapters and
  mandatory public IDs; they do not need product API endpoints and do not gain
  the external-provider exception.
  Documentation-only work records the requirement without claiming implementation
  or qualification.
- **Approved external-provider exception:** For dependencies outside this
  repository's application and fixture code that lack usable public IDs,
  provider-specific adapters are authorized when GUI interaction is necessary
  under the rules above, without renewed approval, including
  discovery, readiness and reacquisition. Prefer available IDs, then scoped
  public accessibility semantics and ordinary keyboard navigation with observed
  focus/results. Use geometry or image matching only when accessibility actions
  and keyboard navigation cannot work reliably; document why. Keep any otherwise
  prohibited selector/input technique inside the explicit adapter, never label
  it a provider-owned ID. Document scope, limitations, affected consumers and
  qualification checks; qualify each supported route on the installed test
  system before claiming readiness. Preserve ownership, ambiguity rejection and
  the input/result guards below; refuse when these cannot be established. This
  exception never applies to repository-owned UI and overrides blanket external
  ID requirements in subordinate documents.

## Unsupported native gestures

Native double-click addressed to a repository-owned GTK control without geometry
is unsupported by the public interfaces examined. Do not create, queue or implement
automation requiring it, or make it a prerequisite of other work. This is an
automation coverage exclusion, not a product failure or a passed test. Continue
the remaining active queue; do not park its next-task pointer on this exclusion.

The public [AT-SPI mouse API](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/func.generate_mouse_event.html)
uses coordinates. GTK's [button accessibility implementation](https://github.com/GNOME/gtk/blob/main/gtk/a11y/gtkatspiaction.c)
exposes semantic activation, not native pointer presses. Dogtail's
[control double-click](https://gitlab.com/dogtail/dogtail/-/blob/master/dogtail/tree.py)
calculates the control's center internally; hiding geometry behind an ID or
object API does not make it compliant. Remote Desktop/libei button injection
does not address a control, and keyboard focus does not route mouse input:
[GTK picks pointer targets by event coordinates](https://docs.gtk.org/gtk4/input-handling.html#event-propagation).
Two semantic activations, keyboard input or manually emitted gesture signals
must not be described as native double-click coverage.

Keep affected stable case IDs and uncovered assertions in their inventory/recipe
owners, explicitly excluded from scheduling; remove their implementation briefs
and queue dependencies. Do not recreate them as provider prerequisites or
repeated research tasks. Reconsider only with materially new evidence of a
supported public control-addressed native route that uses no geometry, followed
by an explicit scope decision and qualification. This exclusion does not relax
the geometry prohibition or authorize skipping unrelated active blockers.

## Input and independent results

- **Presentation acceptance:** Visual inspection/review is excluded from UI
  and E2E acceptance. Keep the geometry prohibition.
  Qualify public logical text, matching accessible labels, stable identities
  and preserved user values. Keyboard focus is an input-recipient guard when
  needed, not a traversal or presentation acceptance matrix. Pixel rendering, glyph
  order, clipping, font legibility and visual alignment are excluded from
  automated acceptance; do not claim those results from text or language values.
  Host UI tests likewise verify translated content and preserved functionality,
  without GTK direction/alignment or glyph-rendering acceptance matrices.
  Retained screenshots and the required VM watch are evidence/observation only
  and require no visual reviewer or visual pass decision.
- Product reads and input use current Application UI API element snapshots and
  capabilities. Read logical values or text independently after input; observe
  the saved policy, validation, draft or session outcome required by the case.
  Do not add focus, scrolling or repeated inventories before a supported API
  operation. Hidden, disabled, busy, detached, wrong-owner or modal-blocked
  controls refuse; viewport clipping alone is not hidden application state.
  External providers retain fresh complete scoped observations, qualified public
  actions and keyboard-recipient guards. Their shared adapter may reveal or
  focus a target when its input route requires it, then reacquire that same
  target. No input or session transition may reuse an earlier recipient proof.
- A successful input is not a successful result. Independently observe the
  required public state. Preserve ownership, secret-recipient, single-use input
  and uncertain-input guards; never replay an action whose effect is uncertain.
  Previously qualified automation has no exemption from this mandate.
  Installed secret delivery follows the shared
  [credential contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary),
  including fresh same-challenge recipient proofs and sealed capture.
