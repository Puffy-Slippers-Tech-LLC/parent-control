# Project boundaries and implementation

- **Customer E2E scope:** follow
  [E2E-Coverage.md](docs/TestAutomation/E2E-Coverage.md). Operate and observe the
  installed app as a real customer across all surfaces; no backend product
  probes or internal fault injection in customer acceptance. Preserve completed
  unit/component/system tests. Mechanical installation, upgrade, migration and
  removal retain necessary internal checks in Tasks 18/20. Prioritize the
  customer queue; deferred policy-acknowledgement design is not an E2E dependency.
  Add infrastructure only for a named blocked consumer and measure progress by
  complete scenarios and shrinking frozen remaining scope.

- **Client/portal ownership:** never edit the portal checkout (code, tests, docs
  or configuration) or deploy it from a client session. Prior cross-repository
  work and command approvals do not authorize this. Put needed API changes in
  a client `docs/` handoff for a separate portal session: reason, current/requested
  contract, request/response examples, compatibility/release dependencies and
  acceptance checks. Report formatting, component names, metadata and attachment
  preparation belong in the client; the portal supplies generic delivery.
- For architecture, start at [System-Design.md](docs/System-Design.md).
  Fix root causes reproducibly on a clean computer; unless specified otherwise,
  treat this as a new app without existing installations. Use supported,
  maintained public code/APIs, never legacy, private, internal or hacky substitutes.
- Add useful detailed logging as needed; never log PII. Redacted labels such as
  `[Child user]` are allowed. Preserve compatibility between the shared child
  form and kiosk GUI.
- Classify new system integrations under
  [package update activation](docs/Publishing.md#package-update-activation).
  Before incompatible saved-data readers/writers, ship the required
  [migration](docs/SystemDesign/Data-Migration.md).
- Follow the [model policy](docs/TestAutomation/Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff):
  quality first, weekly allowance second; Sol high/Standard for settled
  implementation, Astra for unresolved security, concurrency, ownership,
  difficult diagnosis or broad correctness review. Reassess each slice; no
  blanket Astra/high or max-effort default. Choices for authorized work need no
  further settings approval; historical pins are execution records.

# Reads, searches and approvals

- Inspect every search path operand before execution. Quote every file/directory
  operand to `tail`, `head`, `cat`, `sed`, `rg` and `tools/read-only`,
  including absolute paths and filenames containing `~`. Submit reads/searches
  directly with the tool's working directory and each full filename on one
  command line; no explicit shell wrappers, substitutions, environment assignments
  or redirections.
- If **any** search path needs filename expansion (`*`, `?`, brackets), use
  `tools/read-only search --path-glob 'path/prefix*' 'regex' 'literal/path'`.
  Repeat the quoted `--path-glob` for each pattern. For discovery use
  `tools/read-only files --path-glob 'path/prefix*'`; unmatched patterns refuse.
  Never supply an unquoted wildcard to a search/helper or a quoted filename
  pattern as an `rg` path.
- Direct `rg -n` requires a quoted regex and quoted literal paths. Quoted
  `--glob` filters are allowed (ripgrep expands them); anchor them to the
  literal root. Regex metacharacters are allowed inside quoted regexes.
  Apply this preflight to every search. See
  [search examples](docs/TestAutomation/Approval-Tools.md#ripgrep-searches-without-shell-expansion).
- If an ordinary read/search gets a general-shell approval reason, correct
  quoting/command shape and retry the same operation under its existing allowance
  first. Do not forward avoidable approval requests, refresh current rules or
  add duplicate/broader reader/shell grants. Honor actual denials and remaining
  sandbox restrictions.
- Reuse approved prefixes for ordinary trusted reads; they do not validate trailing
  arguments. Machine-wide `pwd`, `git status`, `rg -n`, `sed -n` rules cover
  all working directories/repos/paths. They live in `config/codex-read-only.rules`,
  installed by `./setup.sh --codex-rules-only` (also full/test-tools setup).
  Never add per-directory duplicates, blanket Git/shell grants or project
  `rg`/`sed` prompts that override global allows.
- Logs/journals, public read-only web requests and internet research are always
  authorized; this grants no writes. Use direct `curl -fsSL 'https://example.com/path'`
  with a literal quoted URL and no uploads, custom requests or output files.
  Preserve its global grant; no duplicate/wider rule or overriding project prompt.
- For untrusted arguments or repeated escalated reads beyond the ordinary
  `rg -n`/`sed -n`/`curl -fsSL` forms, use
  `tools/read-only <search|files|slice|sort|unique|gzip|fetch> ...`, quoting paths,
  patterns and URLs. Its fixed options forbid preprocessors, custom requests,
  output paths and shell escapes. This supersedes broad saved sort/uniq/gzip/wget
  grants when escalation is needed; ordinary sandboxed reads remain available.
- Request minimum read-only sandbox escalation when needed, without separate
  authorization. For troubleshooting, read
  `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`; escalate immediately
  if sandbox-blocked. Never modify/delete logs. Prefer ordinary readers, otherwise
  `tools/diagnose <operation> ...` for validated journal, systemd, inventory and
  diagnostic-file reads. Quote unit patterns/dates. Never use raw privileged
  systemctl/journalctl or broad utility grants; see
  [Approval-Tools.md](docs/TestAutomation/Approval-Tools.md).
- Avoid changing inline Python snippets and unnecessary wrappers. Recurring
  privileged diagnostics need a proposed reusable, argument-validated entry point
  with explained scope before persistent approval; never blanket privileged
  shell/interpreter grants.

# Workspace documents and launcher inspection

- Use native `apply_patch` with explicit paths/context for authorized text edits.
  Check local inline Markdown links with `tools/read-only links '<file.md>' ...`;
  count words with `tools/read-only words [--after 'exact marker']
  [--before 'exact marker'] '<file.md>'`. Never substitute inline Python,
  heredocs or unrestricted shells; future command families need reviewed,
  bounded entry points.
- Invoke `tools/codex_slices.py --help` or `tools/codex_slices.py status`
  directly. Its shebang isolates Python; maintained rules cover relative and
  checkout-absolute help/status. Starting/controlling unattended work requires
  authorization for that work.
- [Evidence retention](docs/TestAutomation/Implementation-Workflow.md#retain-useful-evidence-without-one-off-reports)
  supersedes older per-attempt reporting rules. Report routine test/build
  failures (including `make test-all`), fixes and verification in conversation/PR,
  not new standalone investigation/attempt/verification reports anywhere.
  Do not append one-time run reports, incident timelines, qualification
  summaries or superseded implementation histories to existing design docs.
  Revise the current contract in place; keep per-run history in runner artifacts.
  Update owning docs for reusable behavior/regressions and existing active
  handoffs only when continuation needs them. Preserve runner reports, logs,
  artifacts and useful qualification evidence. New evidence documents require
  an explicit request or concrete ongoing acceptance/recovery need unmet by
  existing artifacts/handoff; a failed test or completed fix alone is insufficient.

# Test execution, artifacts and VM ownership

- Plain `make check`, `make build` and build/check targets in
  `config/codex-tests.rules` are authorized in this trusted checkout. No blanket
  Make prompt may override them. Prefix grants do not validate trailing arguments
  or Make environments: use plain targets, validated launchers for options.
  Keep generic shells, privileged Make and direct system-test/setup targets restricted.
- Use [approved categories](docs/TestAutomation/Approval-Tools.md) and
  `tools/run-tests --list`: `tools/run-unit-tests` for unit/property/contracts,
  `tools/run-tests component` for private-D-Bus tests, fixed categories for
  child Node/GJS, static, coverage, fixtures, artifacts and aggregates.
  Privileged integration/system/E2E uses `tools/run-tests <category> ...` or
  installed `onpc-test-runner`; planned routes refuse until implemented.
  Never substitute generic pytest markers, Make arguments, shells or individually
  approved Python. New integration checks are direct
  `tests/integration/check_[a-z][a-z0-9_]*.py` files without CLI arguments,
  with applicable cleanup-safety regressions.
- Quote test patterns and parametrized IDs; category validators expand only
  category-local patterns/options. Example:
  `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' 'tests/unit/test_graphical_lease.py' -q`.
  Non-VM UI pytest must directly use
  `tools/run-ui-tests --timeout <duration> [validated selections/options...]`,
  which confines selection to `tests/ui` and controls environment/cleanup
  prerequisites. No inline environment, wrapping shell, or general
  shell/interpreter/Make/libvirt grants.
- Signal only explicitly spawned, identity-recorded processes. Never infer
  ownership from names, environment, runtime directories or host-wide `/proc`
  scans. Before host-integrated tests that terminate processes, run their
  cleanup-safety regressions in isolation and proceed only if they pass.
- Prefer unprivileged artifact readers; privileged access uses
  `pkexec /usr/local/libexec/onpc-test-artifacts <read|tail|list|stat|export> <absolute-path>`.
  It covers all formats under documented test storage/log roots (see
  [tests/README.md](tests/README.md)); place new privileged artifacts there.
  Never substitute privileged head/cat/cp/interpreters that trigger Polkit dialogs.
- Privileged graphical PNG exports must use
  `pkexec /usr/local/libexec/onpc-export-screenshot /tmp/onpc-graphical-smoke-<run>/testresults/<image>.png /tmp/onpc-<name>.png`.
  It validates sources and creates new caller-owned PNGs only. No privileged
  install/cp/chown/ad hoc substitutes or grants; resolve validation failures.
  Authorized temporary cleanup uses `tools/cleanup-screenshots /tmp/onpc-<name>.png ...`
  with explicit filenames: only caller-owned regular `onpc-` PNGs directly in
  `/tmp`, never logs or repeated rm approvals.
- Authorized VM maintenance uses
  `tools/test-vm <status|xml|start|stop|reboot|reset|screenshot|send-key>`.
  It takes no guest name/URI/path, requires the installed pinned UUID/shared
  lease, and refuses concurrent/replaced guests. Never bypass ownership, use
  broad virsh/virt-manager rules, operate another guest or create snapshots,
  overlays or clones. Stop maintenance before system/E2E tests. Reset is an
  outer maintenance boundary, never a customer-journey step.
- Run approved helpers outside the sandbox through normal escalation when local
  sockets, Polkit or real root-owned metadata are needed. Sandboxes can remap
  ownership/deny D-Bus: check execution context before reinstalling tools and
  never disable ownership validation.

# Setup and rule maintenance

- `./setup.sh` is the sole public setup entry point for development machines
  and VM hosts: dependencies, build prerequisites, test tools, graphical policies,
  Codex rules and baseline preparation. Use its approved modes; never invoke
  installer helpers with privileged Python or seek per-file grants.
- Add setup changes to the appropriate mode. Keep specialist modules scoped;
  no alternative documented entry points or duplicate orchestration. Makefile
  setup aliases only delegate; builds/tests report missing prerequisites instead
  of installing them. Modes must be idempotent/retryable, preserve unrelated
  configuration and accepted baselines, and stop on failed prerequisites.
  Add focused repeat/failure coverage for orchestration changes and update master
  help/docs. `--prepare-host` requires explicit baseline authorization;
  guest-only `--prepare-vm` must never run during ordinary host setup.
- Refresh helpers (including artifact/screenshot helpers) and Polkit/Codex rules
  with `./setup.sh --test-tools-only`. Rule-only/screenshot-cleanup rule refresh
  uses `./setup.sh --codex-rules-only`. Restart Codex to load rules with this
  checkout trusted; Polkit watches its rule directory. Reuse category-wide grants.
- First install uses `./setup.sh --bootstrap-tools` and may require administrator
  authentication; full setup bootstraps missing helpers before dependencies.
  Repeated bootstrap reuses the installed grant. Repairing an existing denied
  installation requires that mode from an administrator-authorized root session.
- Routine modes, including dependencies, use installed `onpc-setup` with a fixed
  operation, pinned trusted checkout, dedicated default-deny Polkit action and
  noninteractive privilege check. Invoking-user Git/venv configuration stays
  unprivileged. Never use generic `pkexec python3`, direct sudo, authentication
  fallback after denial, or weakened policy. Approval trusts maintained checkout
  tests/imports; filename patterns alone do not prove safety. Restrictive
  project/organization rules override old broad grants.
