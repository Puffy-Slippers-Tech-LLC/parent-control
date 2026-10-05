# UI automation mandate

This mandate owns UI route selection and target/input safety for host previews,
qualifications and installed cases. The [catalogue](../TestAutomation/E2E-Building-Blocks.md)
owns callables and qualified scopes; the [coverage allocation](../TestAutomation/UI-and-E2E-Coverage.md)
owns which layer exercises each matrix. Read this mandate when changing either
layer's automation, including shared workers.

## Result-oriented test scope

For existing and future UI and E2E tests, operate the control and independently
verify its final public result. Test the product function: the saved allowance,
filtered rows, changed language, accepted request, effective app rule or restored
draft. A toggle's final on/off state or a selector's final value is sufficient
when that value is the feature being tested. When the choice controls another
function, verify that function too; a selected radio indicator alone does not
prove that language, permissions or behavior changed.

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
checks for pure value combinations. Installed E2E adds actual persistence,
authorization, policy enforcement, lifecycle and integration results to a small
GUI sample. A historical detailed test does not require future repetition.

Retain intermediate observations when a later result would conceal a distinct
functional failure, such as an unintended save, crossed child identity, premature
access, lost work or an incorrect policy transition. Preserve input ownership,
secret-recipient, keyboard-recipient, ambiguity, disabled-control and uncertain
input guards below. These guards belong in shared automation and are not reasons
to add focus/rendering acceptance to every customer case. Harness safety
qualifications remain separate from product journeys.

## Route selection

- **Choose the route by the feature under test:** Real GUI operations are for
  the product features the case exercises, such as its dropdowns, toggles,
  textboxes, approval prompts and explicitly tested launch routes. All other
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
- **Preparation lifetime:** Reusable dependencies, fixed app fixtures/launchers
  and persistent harness settings belong in idempotent `tools/prepare-baseline`
  reconciliation. UI workers verify readiness and fail on missing/stale inputs;
  they never install or repair them during a test. Shared commands may still own
  deliberate scenario mutations, attempt credentials and evidence. Follow the
  [baseline contract](VM-Mandate.MD#vm-host-setup-and-baseline).
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
- **External links:** Acceptance stops at the product's link being clickable:
  resolve its public ID and check a visible, enabled link with a usable public
  activation action. Viewport clipping does not require following the link.
  Do not activate the link, inspect its URI/destination, launch a handler or
  validate what opens. This applies to Help, website, portal, privacy, mail,
  license and legal-file links across all tests. No browser/mail/document
  provider qualification, page/content/DOM checks or external close/return
  workflow belongs to link acceptance. Never pin, install or configure Firefox,
  Chrome or another handler for a test. Ordinary product clicks continue to use
  the current user's system default handler. In-app About and Privacy disclosure
  checks, kiosk external-action restrictions and explicitly authorized feedback
  submission remain separate product features.
  Rich-editor link formatting is a separate owned editing feature: its synthetic
  link values may be checked through public text attributes without navigation.
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

- **Daily allowance selection (all UI and E2E tests):** Use the one shared
  PARENT06 block: native left click on the identified allowance selector, type
  the desired minutes/hours (for example `15m`) or `c` for Custom, press Enter,
  then independently verify the saved allowance or use the Custom editor.
  No test or qualification may add popup-opening, expanded-state, highlight,
  cancellation, choice-row activation, arrow-navigation or menu-reopening
  checks to this sequence. There is no opt-in exception for UI tests.
  Resolve the active owning Parent window, selected child and enabled selector
  by public IDs before input. Preserve native focus; do not inspect or move
  focus inside the popup. The opening click alone may use fresh window-relative
  bounds from that ID-resolved selector through a window-bound native stream.
  GTK screen origins, fixed coordinates and VM/distro branches are forbidden.
  Click, typing and Enter execute once through the shared input block;
  an uncertain input fails without replay or an alternative route.
  Only the final public allowance and save completion establish success.
  Custom numeric editing/validation and per-child persistence remain separate
  tests after this shared selection. The [catalogue](../TestAutomation/E2E-Building-Blocks.md#app-grid-search-and-parent-launch)
  owns the implementation entry points.
- For GUI operations required by the feature under test, and unavoidable
  graphical authentication, except for the external-provider exception below,
  and the daily allowance keyboard exception above, every automated UI target
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
- Add a missing ID to repository-owned application or fixture code and expose it
  through the public accessibility interface before implementing its consumer.
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

- **Presentation acceptance:** The developer removed visual inspection/review
  from this task and all future tasks on 2026-10-05. Keep the geometry prohibition.
  Qualify public logical text, matching accessible labels, stable identities
  and preserved user values. Keyboard focus is an input-recipient guard when
  needed, not a traversal or presentation acceptance matrix. Pixel rendering, glyph
  order, clipping, font legibility and visual alignment are excluded from
  automated acceptance; do not claim those results from text or language values.
  Host UI tests likewise verify translated content and preserved functionality,
  without GTK direction/alignment or glyph-rendering acceptance matrices.
  Retained screenshots and the required VM watch are evidence/observation only
  and require no visual reviewer or visual pass decision.
- After ID lookup (or qualified external-provider resolution), names, roles,
  text and states may verify meaning and results.
  Prefer invoking the ID-resolved control's public accessibility action directly,
  including when a scroll viewport clips or covers an otherwise available control.
  Do not add focus, scrolling or repeated tree traversals before such an action.
  Resolve the target once per fresh input boundary; do not enumerate every ID or
  repeat full traversals solely to obtain that same target.
  Prefer a provider's direct ID lookup where available; otherwise reuse one fresh,
  complete scoped snapshot for prompt, ownership and target checks at each input
  boundary. Never reuse a snapshot across input or session transitions. Preserve
  ambiguity, completeness, sensitivity, ownership and uncertain-input checks.
  Use ordinary keyboard input when appropriate. If a direct public action is
  unavailable, semantically reveal, scroll, focus or navigate, then reacquire by
  ID or the qualified external-provider adapter. Truly hidden or disabled controls
  still refuse; viewport clipping alone is not hidden application state. Cosmetic
  differences cannot gate acceptance.
- A successful input is not a successful result. Independently observe the
  required public state. Preserve ownership, secret-recipient, single-use input
  and uncertain-input guards; never replay an action whose effect is uncertain.
  Previously qualified automation has no exemption from this mandate.
  Installed secret delivery follows the shared
  [credential contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary),
  including fresh same-challenge recipient proofs and sealed capture.
