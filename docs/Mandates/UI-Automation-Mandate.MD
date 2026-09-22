# UI automation mandate

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
- Except for the external-provider exception below, every automated UI target
  must be resolved by a stable public `automation-id`,
  scoped to its owning application and surface. Shared controls use one ID
  contract across surfaces, suites and helpers. Reject missing, duplicate,
  ambiguous and wrong-owner IDs.
- IDs must not derive from translated labels, names, roles, titles, rendering,
  tree/list position or geometry. Do not use coordinates, extents, image matching,
  layout, display scale, scroll position, window titles, frame roles, color or
  theme to identify a target, route input, establish readiness or decide
  acceptance. This includes setup, login, retained sessions and legacy paths.
- Add a missing ID to repository-owned application or fixture code and expose it
  through the public accessibility interface before implementing its consumer.
  Documentation-only work records the requirement without claiming implementation
  or qualification.
- **Approved external-provider exception:** For dependencies outside this
  repository's application and fixture code that lack usable public IDs,
  provider-specific adapters are authorized without renewed approval, including
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
