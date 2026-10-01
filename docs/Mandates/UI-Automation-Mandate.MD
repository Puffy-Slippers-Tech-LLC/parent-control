# UI automation mandate

This mandate owns UI route selection and target/input safety for host previews,
qualifications and installed cases. The [catalogue](../TestAutomation/E2E-Building-Blocks.md)
owns callables and qualified scopes; the [coverage allocation](../TestAutomation/UI-and-E2E-Coverage.md)
owns which layer exercises each matrix. Read this mandate when changing either
layer's automation, including shared workers.

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
- **Parent app launch:** Every case that needs Parent functionality without
  testing app-grid discovery must reuse PARENT01
  ([`onpc_parent::launch`](../../tests/integration/graphical_smoke/lib/onpc_parent.pm)),
  directly or through FLOW01. It invokes the installed
  `oh-no-parent-control-parent` command directly as the current desktop user,
  without a terminal or app-grid search, then independently observes the
  expected management window or access denial. Use this block for setup and
  reopening; do not duplicate launch code. Returning to an already open window
  does not require relaunching. Only cases explicitly testing app-grid discovery,
  launch or unavailability may use the search blocks with the full query
  `Oh No! Parent Control` and open a launchable result when expected. Declare
  that exception in the case metadata and recipe. Preserve session identity,
  prompt refusal, single-use execution and independent result checks.
- **Child app launch:** Every case that needs the child overlay without testing
  how to find or launch it through the graphical UI must reuse REQUEST02
  (`AccessibleUI.launch_child_command`), directly or through a composite.
  This block invokes the installed `oh-no-parent-control-child` command as the
  active child desktop user, without a terminal, app-grid search or panel
  navigation, then independently observes one usable overlay with the fixed
  child identity. Use it for setup and reopening; do not duplicate launch code.
  Returning to an already open overlay does not require relaunching. Only
  cases explicitly testing graphical discovery or launch may use a UI entry
  block. Declare that exception in the case metadata and recipe. Preserve
  session identity, prompt refusal, single-use execution and independent
  result checks.
## Target identity and provider exception

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
## Input and independent results

- After ID lookup (or qualified external-provider resolution), names, roles,
  text and states may verify meaning and results.
  Prefer invoking the ID-resolved control's public accessibility action directly,
  including when a scroll viewport clips or covers an otherwise available control.
  Do not add focus, scrolling or repeated tree traversals before such an action.
  Avoid control looping such as find_all_ids whenever direct ID invocation is possible.
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
