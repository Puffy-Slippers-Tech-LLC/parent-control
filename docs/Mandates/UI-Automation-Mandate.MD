# UI automation mandate

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
