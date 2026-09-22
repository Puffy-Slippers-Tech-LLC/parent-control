# Repository agent instructions

## Environment and communication

- Treat this computer as the development host. The product is not installed and
  must not be installed unless the task explicitly requires an installed-system
  workflow. Development previews and the maintained test viewers are allowed.
- When asked for "handoff time", stop at the earliest clean boundary and return
  a concise continuation prompt. Include only the remaining work and recommend a
  model and effort; do not save the prompt in the repository.
- Do not send progress messages while a command is running. Report it after it
  completes or fails.
- Keep progress updates and final responses concise and focused on meaningful
  results and the next intended action. Omit routine prerequisites, procedural
  narration and test counts unless they affect a decision or explain a problem.
  Perform required checks without narrating each step. Preserve important
  updates: blockers, unexpected findings, behavior mismatches, material risks,
  validation limits and decisions requiring user input. Describe the next goal
  accurately without implying that its prerequisites are already complete.
  Example: "All scoped tests now pass. Next I'll run the live qualification."

## Authority and unattended work

- Start product work at [System design](docs/System-Design.md). It owns component,
  trust, state and lifecycle boundaries. The specification owns expected customer
  behavior. Use the design's overview/module map to locate the affected boundary;
  read the applicable sections, following related modules when that boundary is
  crossed. A link to a contract does not require loading its entire document.
- Apply the repository-wide [approval contract](docs/Approval-Tools.md) to all
  reads, edits, builds, tests, diagnostics, setup, VM work and publishing. Run
  authorized work unattended through its existing grants and validated tools.
- Reuse session and category-wide authorization. Do not request Codex or Polkit
  prompts, add duplicate rules, broaden shell/interpreter/Git/Make/libvirt grants,
  or use authentication fallbacks after denial. A missing prerequisite or grant
  is a blocker to report, not a control to bypass.
- Executable project `tools/` launchers are preapproved only within the requested
  task. Invoke them directly. Use their scoped out-of-sandbox routes when sockets,
  Polkit or real ownership metadata require them.
- Preserve all pre-existing work. Do not reset, discard, unstage or overwrite
  unrelated changes.

## Product boundaries

- Fix root causes reproducibly on clean computers with supported, maintained
  public APIs. Preserve the shared child-form/kiosk contract and log useful
  diagnostics without PII; role labels such as `[Child user]` are acceptable.
- Never edit or deploy the portal checkout from a client task. Request portal API
  changes in a client `docs/` handoff that states the reason, old and proposed
  contracts, examples, compatibility, release dependencies and acceptance checks.
  Client-specific report presentation and metadata remain in this repository.
- Classify new integrations under [package update activation](docs/Publishing.md#package-update-activation).
  Ship required [data migrations](docs/SystemDesign/Data-Migration.md) before
  incompatible readers or writers.
- Choose the implementation model by the current slice: Sol for settled work;
  Astra for unresolved security, concurrency, ownership, difficult diagnosis or
  broad correctness review. Prefer quality, then weekly allowance.

## Test and customer acceptance

- Follow the [test-automation documentation map](docs/TestAutomation/README.md)
  and the executable inventory in `tests/e2e/scenarios.json`. Customer acceptance
  operates the installed product through public interfaces and observes customer
  results; backend probes and internal fault injection remain engineering tests.
- For “Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md”,
  implement exactly its first unchecked active queue row. Table order is final;
  task IDs are labels, and prerequisites name earlier tasks' delivered scopes.
  Finish that row's acceptance and close-out before advancing the sole pointer.
  Do not select alternative work, complete a later scenario inside a capability
  task, or skip a blocker. Keep each complete E2E case in its own task. Maintain
  the queue consistency checks when splitting or repairing the plan.
- Tests must catch regressions. On a behavior mismatch, preserve the evidence and
  report expected versus actual behavior. Obtain developer confirmation before
  accepting the change or altering expectations unless that exact behavior change
  is already authorized. Never weaken, skip or delete a check to match the app.
  Proven mechanical defects in tests, fixtures or harnesses may be fixed while
  preserving the intended assertion. See [failure handling](tests/README.md#handling-test-failures).
- Preserve completed unit, component and system coverage, including mechanical
  install, upgrade, migration and removal checks. Add infrastructure only for a
  named blocked consumer. Prioritize the customer queue and measure completed
  scenarios against its frozen remaining scope. Deferred policy-acknowledgement
  design is not a dependency for that queue.

## UI automation mandate

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

## Reads, edits and evidence

- Reuse unchanged instructions and source already available in the current
  context, including injected AGENTS.md. In a fresh session or after compaction,
  retrieve missing applicable requirements; do not treat a remembered summary as
  their replacement. Read linked documents by task-relevant heading/row and code
  by complete relevant function plus necessary callers, callees and shared state.
  Expand for ambiguity, stale references, shared changes or failures. Token
  savings never justify missing a contract, weakening checks or guessing at
  truncated output. For repeated E2E work, use the execution plan's
  [reading routes](docs/TestAutomation/E2E-Execution-Plan.md#load-only-the-selected-context).
- Quote every path, pattern and URL. Inspect operands before execution. Run
  direct reads in the intended working directory; do not wrap them in shells,
  substitutions, assignments or redirections.
- Use `rg -n` only with literal paths and quoted ripgrep `--glob` filters. Use
  `tools/read-only files|search --path-glob ...` when filename expansion is
  required. Use `tools/read-only` for untrusted arguments and the other bounded
  read/filter/fetch operations documented by the approval contract.
- Public read-only research and log inspection are authorized. Use the maintained
  diagnostics and artifact readers for privileged data; never modify logs.
- Edit text with native `apply_patch`. Validate changed Markdown with
  `tools/read-only links` and use `tools/read-only words` when counts matter.
- Keep routine failure/fix/verification details in the conversation or existing
  runner artifacts. Update current contracts and active handoffs, not historical
  incident narratives. Create a new evidence document only when explicitly asked
  or when an active acceptance/recovery need has no existing artifact.

## Tests, artifacts and VM

- Discover suites and their exact routes with `tools/run-tests --list` and
  `tools/run-tests --help`. Choose coverage from the change and its regression
  risk first, then use `tools/run-tests` for the selected scope: `ui` for UI-only
  validation, `unit` for unit-only validation, or the required categories and
  quoted file/case selectors. Prefer the launcher's existing parallel scheduling
  wherever supported within that scope. Never expand UI-only or unit-only
  validation to `host` or `all` merely to obtain parallelism; test-file count
  alone does not justify unrelated checks or package builds. Direct
  `tools/run-unit-tests` and `tools/run-ui-tests` remain appropriate for narrow
  iteration or diagnosis. Preserve
  selectors and explicit UI timeouts; avoid `-x` or positive `--maxfail` for broad
  unit/UI passes because those diagnostic options retain serial execution. See the
  [scheduling contract](tests/README.md#all-established-regressions).
- Use `tools/run-tests host` only when all host coverage is justified, and
  `tools/run-tests all` only when the entire established regression set is
  justified. Combine complete categories when each is required, sharing their
  report and package inputs. Use plain approved Make targets only as documented in
  the [approval contract](docs/Approval-Tools.md). Do not replace the launcher
  routes with generic pytest, interpreter or Make invocations, and do not start
  competing launchers against the aggregate's checkout lock.
- Quote test patterns and parametrized IDs. New privileged integration checks are
  argument-free `tests/integration/check_[a-z][a-z0-9_]*.py` files with applicable
  cleanup-safety coverage.
- Signal only explicitly spawned, identity-recorded processes. Before a
  host-integrated test terminates processes, pass its cleanup-safety regressions
  in isolation.
- Use only the documented artifact readers/exporters. Export graphical PNGs with
  `onpc-export-screenshot` and clean only explicit caller-owned `/tmp/onpc-*.png`
  files through `tools/cleanup-screenshots`.
- Operate the pinned VM only through `tools/test-vm`. Do not bypass ownership,
  select another guest, or create snapshots, overlays or clones. Stop maintenance
  before system/E2E tests; reset is not a customer journey step.
- **VM observation mandate:** Every VM operation, experiment, qualification,
  setup, maintenance and test must use the shared `watchvm` infrastructure,
  regardless of its caller or whether it is E2E. Start display observation through
  the shared VM lease; route host/SSH commands through the guarded command
  transport and publish a nonsecret intention through `watch_activity.operation`
  (or its `observed` decorator) before performing work. Keep that intention in
  the viewer footer throughout the operation, including waits and cleanup;
  nested operations restore the enclosing intention when finished.
- Reuse the existing display collector, authenticated command transcript and
  progress interfaces. Do not add per-workflow viewers, SSH tails, capture loops
  or alternate intention channels. A missing integration must be fixed in this
  shared infrastructure before adding its consumer. Preserve private-input
  filtering and the existing VM ownership/identity checks.
- `tools/watchvm` must remain read-only, live and interruption-free. Users can
  connect, disconnect and reconnect at any time, including between maintenance
  commands, without affecting VM operations. Viewer lifetime must never control
  the VM, its input, command execution or collector lifetime. Qualify new routes
  for intent-before-action, live screen/SSH visibility and independent viewing.

## Setup

- `./setup.sh` is the sole public development/VM-host setup entry point. Modes
  must be retryable, preserve unrelated configuration and fail on missing
  prerequisites. Tests and builds report missing prerequisites; they do not
  install them.
- Refresh helpers with `./setup.sh --test-tools-only` and rules alone with
  `./setup.sh --codex-rules-only`; restart Codex after rule changes. First install
  uses `./setup.sh --bootstrap-tools`. Do not refresh rules to fix bad quoting.
- Baseline preparation is an explicit destructive operation through
  `tools/prepare-baseline`; ordinary setup and E2E never prepare or replace it.
  Baseline preparation and E2E require the literal `TEST_ACCOUNT_PASSWORD` in the
  host's private `.envrc`; E2E never changes passwords.
- Routine privileged setup uses the installed, pinned, default-deny `onpc-setup`
  helper. Do not use direct sudo, generic privileged interpreters, installer
  shortcuts or weakened ownership/policy checks.
