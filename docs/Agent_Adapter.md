# Agent adapter proposal

Status: Codex session preparation, interactive protocol extraction, batch
presentation normalization, model/profile preflight and remaining caller/profile
integration are implemented. Current Codex policy has been reconciled with the
adapter boundary. Claude policy migration and configuration-driven agent selection
remain proposed. Delivery step 2's Codex extraction is complete within the agreed
bounded scope. Codex live-agent qualification is partial: finite
transport/profile and trusted-project rule checks passed. Git helper callers now
check catalogue readiness. Delegated write-boundary enforcement and explicit
helper retirement before coordinator handoff remain unqualified and are deferred
from step 2 by the user's scope decision.

The repository should select its coding agent solely from the checked-in
top-level `agent` field in [config/environment.json](../config/environment.json).
The allowed values are `codex` and `claude`. Changing that field should switch
all repository-owned coding-agent sessions through a shared adapter boundary,
while retaining the existing workflows, public launcher commands, acceptance
checks, task budgets and resource ownership.

The compatibility fix in [vm_config.py](../tests/integration/vm_config.py)
accepts the additional field as unused metadata. It does not validate agent
capabilities, select Claude, or change the existing Codex commands. Until the
proposal is implemented, both field values leave execution on the existing
Codex path.

The first implementation slice adds `SessionRequest`, `Delegation` and
`PreparedSession` in [agent_adapter.py](../tools/agent_adapter.py), with native
batch/app-server command preparation, role assets and fresh-session settings
in [agent_codex.py](../tools/agent_codex.py). Repair, plans, E2E, translation and
Git helpers now supply session requirements instead of changing native argument
lists. Capacity attempts reprepare requests under the same adapter. Process
supervision, mailbox/result acceptance and workflow budgets retain their owners.
The existing executable check is preserved. `PreparedSession` now carries a per-session
`SessionProtocol` for interactive execution. `CodexProtocol` in `agent_codex.py`
owns app-server framing, RPC requests/responses, coordinator thread/turn filtering,
steering/interruption races and native output/error decoding. It emits
`SessionEvent` values for the shared conversation in `launcher_chat.py`, which
retains mailbox/status handling, candidate task binding and result persistence.
The supervisor still owns pipes, cancellation and nested-test cleanup.
`PreparedSession.presentation` supplies a `BatchPresentation` decoder for batch
stdout. `CodexBatchPresentation` in `agent_codex.py` owns JSONL framing,
native event/error decoding, reasoning suppression and terminal capacity
classification. Both transports supply `SessionEvent` values to the shared
renderer, reusing its existing item vocabulary. Usage retains the CLI's reported
turn scope and missing counters; displayed messages and helper activity never
replace the native coordinator result file or workflow validation.
`ModelProfile` and `resolve_profile` expose native model/effort pairs through the
adapter. Repair and translation catalogue checks now use
`PreparedSession.preflight`; plan and E2E startup also check their requested
coordinator/helper profiles. `CodexAdapter` owns the bounded `debug models`
request, catalogue validation, listed effort checks and role-profile resolution
from its existing TOML assets. Missing CLI/catalogue capabilities fail before task
work; preflight never installs or authenticates a CLI. The catalogue advertises
support; it does not establish authentication, live model access or transport
compatibility. Workflow owners retain effort ladders, explicit override policy,
promotion timing, budgets and capacity retry delays. The adapter maps the existing
Sol-to-Astra capacity fallback, checked when needed without spending a new logical
session. Native role assets join the controller reload inventory. Strict
configuration selection remains a future step. No Claude runtime dependency is
introduced.

Git close-out and merge/stash-restoration conflict sessions resolve the pinned
`commit_helper` and `conflict_resolver` profiles through the adapter, retaining
the existing executable check during session preparation. They retain Sol High
independently of coordinator overrides; deterministic Git operations do not
prepare or preflight an agent. The pinned Git helper profiles passed catalogue
and finite live-session checks. Their supervised callers now run
`PreparedSession.preflight` before task supervision; catalogue failure prevents
task launch. Their Git transactions remain unqualified. No additional task
subprocess runs outside its supervisor. Shared workflow prompts render resolved model and
helper profiles rather than duplicating native model names. Native role assets
retain their model/effort pins and requested permissions; native delegated sandbox
inheritance remains an [unqualified native limitation](#trusted-worktree-follow-up).
Their instructions refer to those configured pins. The current goal API, fresh helper context, independent Astra
backend review and workflow-specific escalation/delegation rules remain enforced.
The owning execution/test policies distinguish that extraction from the proposed
Claude policy migration below. Setup/SSH/Watch native assumptions remain for their
later delivery step; no alternative runtime or selection is enabled here.

## Next implementation step

The current Codex-only session is closed out. Preserve the accepted
[transport/profile checks](#codex-live-qualification) and
[trusted-worktree results](#trusted-worktree-follow-up); do not repeat them solely
to renew evidence. The user deferred native delegated permission enforcement and
explicit helper retirement from delivery step 2. They remain unqualified;
deferral supplies no passing result or change to owning workflow requirements.
Do not add hooks, helper orchestration or native-runtime workarounds to this
extraction step. Unexercised refusal/capacity recovery and full Git
conflict/stash/close-out paths remain explicitly unqualified.

The next planned implementation is delivery step 3, under a separately scoped
Claude integration session and the proposed
[policy migrations](#models-roles-and-repository-policy). This close-out does not
start that work, enable Claude/configuration selection or redo delivered extraction.

## Configuration and scope

The existing configuration contains:

```json
{
  "agent": "codex"
}
```

This is an excerpt, not a replacement for the host, branch, launcher and VM
configuration. To select Claude after implementation, change that one value to
`claude`. Do not add a provider argument to public or private launcher command
lines, an environment-variable override, a second selection file, or an
interactive agent picker. No executable path or arbitrary import comes from
this field: a fixed mapping selects one of two maintained adapter classes.

The selection covers `fix-tests`, `write-e2e`, `execute-plan`,
`sync-whatsnew`, their delegated workers/monitors/advisers/reviewers, supervised
commit sessions, and automatic merge/stash-restoration conflict resolution.
Future repository-owned agent callers must use the same boundary.
Agent-free tests, builds, diagnostics, deterministic Git operations and VM
helpers continue to work without either coding CLI installed or authenticated.
Editing this field cannot change the coding application already running the
developer's current interactive conversation.

The installed parent-control product has no coding-agent dependency. Keep the
adapter and its configuration in development infrastructure, outside the runtime
dependency and package payload maps.

## Current integration map

| Area | Existing coupling | Proposed change |
| --- | --- | --- |
| Configuration | [vm_config.py](../tests/integration/vm_config.py) owns the shared document reader; [vm_selection.py](../tools/vm_selection.py) exposes it to launchers | Keep one document parser; add strict live agent selection at the adapter entry point |
| Shared execution | [detached_launcher.py](../tools/detached_launcher.py) prepares sessions and transport decoders through the Codex adapter, supervises processes and retries capacity failures | Retain ownership/supervision; native fallback mapping and readiness now belong to the adapter |
| Conversation | [launcher_chat.py](../tools/launcher_chat.py) consumes adapter events and retains shared mailbox/status and completion gates | Keep mailbox, status validation and input/result serialization shared; qualify native transport behavior |
| Presentation | [launcher_render.py](../tools/launcher_render.py) consumes shared events from both Codex transports | Qualify the same common event format with the future Claude adapter |
| Repair | [fix_tests.py](../tools/fix_tests.py) supplies repair tiers and override policy; native profiles/catalogue checks use the adapter | Retain escalation and verification ownership when selection is enabled |
| E2E | [write_e2e.py](../tools/write_e2e.py) resolves coordinator/adviser profiles and checks catalogue capabilities through the adapter | Preserve its acceptance/escalation engine when selection is enabled |
| Ordinary plans | [plan_launcher.py](../tools/plan_launcher.py) resolves defaults/helper profiles and preflights through the adapter | Keep plan selection, completion guards and capacity retry timing shared |
| Translation | [sync_whatsnew.py](../tools/sync_whatsnew.py) requests read-only sessions, bounded translator roles and model preflight through the adapter | Preserve launcher-owned catalogue writes when selection is enabled |
| Git recovery | [launcher_git.py](../tools/launcher_git.py) and [launcher_worktrees.py](../tools/launcher_worktrees.py) resolve pinned profiles and prepare sessions through the adapter | Qualify catalogue readiness and inherit the parent's selection when enabled; keep deterministic Git transactions shared |
| Policies and roles | Shared prompts render resolved profiles; [AGENTS.md](../AGENTS.md), [Execution-Plans.md](Execution-Plans.md), [tests/README.md](../tests/README.md) and native role TOMLs retain current Codex requirements | Qualify and revise the owning policies before Claude execution; render its native roles from shared requirements |
| Setup | [setup.sh](../setup.sh), [install_codex_rules.py](../tools/install_codex_rules.py), [setup_checkout.sh](../tools/setup_checkout.sh), and `config/codex-*` manage Codex rules/readiness | Add the selected agent's setup/readiness path without changing the public setup entry point |
| Remote and Watch | [launcher_controller.py](../tools/launcher_controller.py) and [extension.js](../vscode/onpc-watch/extension.js) check specifically for Codex on SSH startup | Resolve on the executing checkout, prepare its CLI environment and display the recorded agent |
| Supporting assets | Existing test doubles, skills, ignore rules, source archives and launcher reload inventories contain Codex assumptions | Adapt affected consumers without introducing a second workflow or unrelated test matrix |

## Adapter boundary

Use composition beneath the existing launcher engines, following the
[extension boundary](Execution-Plans.md#extension-boundary). Start with three
small modules: `tools/agent_adapter.py`, `tools/agent_codex.py`, and proposed
`tools/agent_claude.py`. The first two implement session preparation, model/profile preflight, the
interactive protocol and batch presentation; the Claude module does not yet exist. Do not build a plugin framework or a generic
multi-provider orchestration service.

The intended `agent_adapter.py` boundary owns the common session request, fixed
adapter selection, workflow/role vocabulary, and normalized events/results/errors.
Session preparation, model/profile preflight, the interactive protocol and batch presentation contracts are implemented. Each concrete
adapter owns native CLI/SDK details and its supported model profiles. Shared
launcher code must not index into native argument lists or insert Codex `-c`
values. For example, translation requests a read-only session directly instead
of replacing the argument following `--sandbox`.

The proposed interface has three responsibilities:

| Operation | Input and output |
| --- | --- |
| Resolve | Read the executing checkout's configuration and return the fixed adapter for its validated `agent` value |
| Preflight | Check the executable, authentication/readiness and capabilities required by the workflow/role; return actionable errors without starting task work |
| Prepare session | Accept a typed session request and return native argv, environment, working directory and a per-session protocol handler for shared supervision |

The request carries the workflow, role, logical tier, permissions, prompt,
result schema, owned run directory, allowed extra directories, delegation
limits and any existing explicit model/effort setting. It also carries the
controller's immutable selection snapshot. The snapshot is internal state,
not a new command-line override. Pass it through existing controller/session
state rather than rereading unrelated checkouts inside every helper.

Keep these requirements independent of native configuration: request a role,
write boundary, delegation limit and instruction text, not a Codex TOML path,
`-c` fragment, RPC method or Claude permission-mode name. The concrete adapter
renders native role assets and transport settings. A prepared session is a
process specification plus protocol handler, not necessarily a `codex exec`
argument list; the future Claude implementation may prepare an SDK bridge
instead. Shared code changes models or permissions by preparing a revised
request, never by editing that list.

The protocol handler supplies initial input, decodes native output, accepts
follow-up messages, requests turn interruption, and finalizes a candidate
result. The existing supervisor continues to own subprocess creation, pipes,
recorded process identity, cancellation, bounded shutdown and reaping. An SDK
bridge, if needed, must remain an owned child and must not create an independent
daemon or untracked background sessions.

The adapter never decides that a task passed, operates a VM, advances a queue,
stages a file or commits changes. Existing workflow validators retain those
decisions under the [execution and test contracts](TestAutomation/README.md).

## Reading and changing the selection

Extend the shared configuration reader's allowlist for `agent`; retain its
duplicate-key and other structural checks. Legacy documents used for archived
state or agent-free fixtures may omit the field. When present, the eventual
reader validates that it is exactly one of the two lowercase strings. A live
agent session additionally requires the field: a missing, invalid or unreadable
selection fails before spawning an agent. Do not infer Codex from an old
checkpoint, the CLI on PATH, a model name, or a personal configuration file.

Resolve branch/host dispatch first. The checkout that actually executes the
workflow reads its own checked-in `config/environment.json`; a client or
another worktree cannot override it through forwarded launcher arguments.
Normal Git synchronization distributes the setting. If checkouts temporarily
disagree, report the executing checkout and its selected agent rather than
silently applying the client's value.

Read the selection before each new logical agent session and pin it through
that session's turns, delegated helpers and bounded capacity retries. Dependent
Git close-out/resolution sessions inherit the originating selection until their
owned operation reaches a clean boundary. A config edit during work does not
kill the current agent or reinterpret its results. The next independent agent
session reads the new value after prior children and owned cleanup finish.

On restart, reconcile any interrupted operation through existing ownership and
recovery routes before starting another agent. With no live agent left, resolve
the current configuration for the new recovery/continuation session, preserving
the transaction journal and unfinished task. No old provider must remain
installed solely because a checkpoint records it. Reattachment to a live run
observes its pinned session and does not change its selection.

Record the actual agent, native model, native effort and logical tier in existing
session metadata and usage records. Retained selection is provenance, not an
alternative configuration source. Legacy records remain readable with unknown
agent provenance; never relabel old sessions as Claude. Switching preserves
accepted tasks, remaining work, session counts, model-promotion history, checks,
owned edits and pending close-out. It does not resume the other agent's private
conversation or reset any allowance.

Stop, cleanup and observation must remain available even when the new selection
is invalid or its CLI is missing. Those operations use retained owner identities
and must not depend on a fresh agent preflight. Likewise, help, listing and
agent-free checks must not require agent login or a model request.

## Native transports and common results

The Codex adapter initially extracts the existing behavior: batch `codex exec`,
interactive `app-server`, schema output, policy overrides and role configuration.
Preserve its current permissions and fresh-context behavior while moving the
code. Codex's documented batch interface supplies JSON events and
schema-constrained output. See [OpenAI non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

The Claude adapter uses `claude -p` for batch sessions, with structured JSON
output and the supplied JSON Schema. Extract the `structured_output` payload
from the native result envelope; a missing payload or unsuccessful native result
is not a valid workflow response. For interactive sessions, use the supported
Claude Agent SDK streaming-input interface behind the owned transport bridge.
It supports follow-up input and interruption; do not emulate Codex RPC names
or treat restarting a one-shot CLI as equivalent to steering an active turn.
See [Claude programmatic execution](https://code.claude.com/docs/en/headless)
and [streaming input](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode).

Preflight must qualify the actual CLI/SDK pair and authentication used by the
transport. Pin the SDK's `cli_path` to the checked executable rather than letting
SDK discovery silently choose a different bundled CLI. Prefer the supported
SDK client behind the bridge; its low-level custom `Transport` interface is
documented as internal and unstable, not a maintained alternative to that bridge.
See the [Python SDK reference](https://code.claude.com/docs/en/agent-sdk/python).

Both adapters emit a bounded common vocabulary: session/turn lifecycle,
assistant text, tool/command start and completion, command-output deltas, file
changes, delegated-agent activity, usage, candidate result, and classified
failure. Keep native details inside the adapter or sanitized diagnostic payloads.
Unknown events may be displayed as inert diagnostics; they cannot control
execution. Suppress private reasoning content in the common presentation path.

Keep the existing workflow result schemas and validators, including
`plan_response.schema.json`, `write_e2e_response.schema.json`,
`fix_tests_response.schema.json`, and `sync_whatsnew_response.schema.json`.
The shared result path remains `agent-result.json`; normalize native output
before handing it to existing response validation. Never accept a successful
process exit, partial stream, tool result, or helper's final message as the
coordinator's completed workflow response.

For Claude, `subtype="success"` alone is insufficient: the documented
`ResultMessage` can still have `is_error=true`, including for a refusal or API
failure. Inspect error, stop and terminal fields before exposing a candidate
result. Bind it to the submitted user turn; background-task notification turns
can also produce result messages and must not finish the workflow. Require the
coordinator's `structured_output`, then run the existing workflow validator.
The SDK currently validates JSON Schema draft-07; qualify all four existing
schemas without weakening their validators or assuming arbitrary newer schema
features work. See [result messages](https://code.claude.com/docs/en/agent-sdk/python#resultmessage)
and [structured output](https://code.claude.com/docs/en/agent-sdk/structured-outputs).

Preserve the current mailbox gate: drain pending user input before accepting
completion; bind steering/interruption to the current session and turn; finish
interrupted nested-test cleanup before continuing. An interrupt must not become
completion or a fabricated structured response. If Claude's native interruption
or message-queue semantics differ, reconcile them inside its adapter and expose
only the shared behavior after qualification. Do not advertise interactive
support before that behavior works.

Claude's `interrupt()` does not clear buffered messages. Drain the interrupted
turn through its terminal result before sending a continuation, discard its
candidate output, and complete owned nested-test cleanup first. Queued streaming
input is documented as sequential; it is not proof of Codex-style mid-turn
steering. The adapter must qualify message delivery and interruption against
the existing mailbox contract rather than acknowledging a queued message as
already applied to the active turn. See [interruption and buffering](https://code.claude.com/docs/en/agent-sdk/python#claudesdkclient).

Normalize usage without inventing missing counters or billing equivalence.
Keep native model identity and provider-reported scope; do not assume cache,
reasoning or delegated-agent tokens are counted identically by the two CLIs.
In Claude streaming sessions, `usage` is per-turn and excludes subagents, while
`model_usage` and `total_cost_usd` are cumulative across turns. Preserve those
scopes; do not sum successive cumulative snapshots or merge them with per-turn
counters as if they were disjoint. See [Claude usage accounting](https://code.claude.com/docs/en/agent-sdk/python#resultmessage).

## Models, roles and repository policy

Workflows retain the reasons and timing for escalation. The adapters map the
same role/tier request to supported native model/effort pairs in one place per
agent. Required roles include coordinator/implementer, routine worker,
read-only monitor, bounded adviser, independent backend reviewer, translator,
commit helper and conflict resolver. Preserve per-workflow restrictions on
delegation, concurrency, depth, freshness and write ownership.

The agreed default implementation-model mapping is:

| Selected agent | Default model | Effort selection |
| --- | --- | --- |
| `codex` | GPT-6.1 Sol (`gpt-6.1-sol`) | Preserve the existing workflow's effort tiers |
| `claude` | Claude Opus 5.5 (`claude-opus-5-5`) | Map workflow tiers to qualified, supported native efforts |

Use the explicit Claude model ID rather than the moving `opus` alias. This is
the repository's role mapping, not a claim of identical capability or cost at
matching effort labels. See [Claude model selection](https://code.claude.com/docs/en/model-config).
Preserve Codex's current profiles during extraction. Define and qualify the
remaining Claude role/effort profiles against the installed CLI and authenticated
account before enabling their consuming workflow. Do not mechanically copy
Sol/Astra model names. Missing capability is a preflight blocker, never a silent
downgrade or a reason to invoke Codex.

Existing public `--model` and `--effort` options, where already present, remain
within the configured agent. They cannot select a different adapter. A model
override incompatible with the selected agent is rejected clearly. A retained
override from an older run is reported and reconciled through the existing
resume policy; it cannot silently force the old agent or be discarded. No new
launcher parameters are needed for adapter selection or model profiles.

Two owning policies require coordinated revisions before Claude execution:

1. [Execution and delegation](Execution-Plans.md#execution-and-delegation)
   requires an actual Codex goal, including for helpers, and rejects replacing
   it with prompt text. Retain the simplicity objective as shared policy and
   retain native goal activation for Codex. Explicitly define the Claude
   alternative in that owner, with its real guarantees. Do not claim that prompt
   injection or a launcher metadata field implements the Codex goal API.
2. [Core backend requirements](../AGENTS.md#product-boundaries) currently pin
   implementation and independent review to OpenAI models. To meet the single
   `agent` selection requirement across the whole repo, revise them to require
   qualified implementation and an independent reviewer within the selected
   agent, with native profiles defined by each adapter. Preserve the review's
   read-only scope, fresh context, pause/join discipline and findings resolution.
   Do not retain a hidden Astra call when `agent` is `claude`, or silently weaken
   the existing mandate before its owner is changed.

These are proposed policy migrations, not exceptions granted by this document.
Update conflicting prompts, role TOMLs and active contract consumers together.
Keep shared instruction text separate from native configuration so equivalent
role restrictions do not drift across implementations. Native agent tools and
lifecycle operations may differ; render the appropriate delegation instructions
rather than requiring Claude to call Codex's `spawn_agent` API.

Claude's `AgentDefinition` supplies native role prompts, models and tool sets.
Non-fork helpers start without parent conversation history, but do not inherit
the parent's system prompt, so render required shared instructions into each
role and assignment. Explicitly deny `Agent(fork)` and disable unconfigured
built-in agents; defining custom roles alone does not remove those alternatives.
Qualify enforcement of concurrency, depth, allowed roles and wait/join behavior:
do not assume `maxTurns` is a concurrency limit or that background delegation
has the same defaults as Codex. An unenforceable required limit blocks the
consuming workflow. See [SDK subagents](https://code.claude.com/docs/en/agent-sdk/subagents).

## Permissions, instructions and setup

Keep the [approval contract](Approval-Tools.md) and validated public helpers as
the authority. Codex rules and Claude permissions have different formats and
execution semantics; do not translate them by textual substitution or enable
permission bypass to make a workflow work.

The Claude policy should allow the required maintained commands and workspace
edits, deny unauthorized operations, and refuse unapproved requests without an
interactive prompt. `dontAsk` denies calls that would otherwise prompt; it is
not filesystem isolation. Configure the appropriate sandbox and tool restrictions
as well. Read-only roles must prevent mutation through shell and external tools,
not merely omit Edit/Write or rely on a read-only prompt. Preserve external
directory limits needed for Git recovery and the separate Polkit boundary.
See [Claude permissions](https://code.claude.com/docs/en/permissions).

For a policy based on maintained command grants, disable automatic approval of
all sandboxed Bash commands (`autoAllowBashIfSandboxed`), reject unapproved
unsandboxed execution, and require sandbox startup to fail closed
(`failIfUnavailable`). The Python SDK documents an unsandboxed fallback when
the sandbox cannot start unless that last option is set. Tool allow rules are
approvals, not a tool allowlist; `can_use_tool` runs only for unresolved prompts
and cannot by itself intercept already approved operations. Qualify shell,
file-tool and external-tool restrictions together, especially for read-only
roles. See [SDK sandbox settings](https://code.claude.com/docs/en/agent-sdk/python#sandboxsettings)
and [permission evaluation](https://code.claude.com/docs/en/agent-sdk/permissions).

Share `AGENTS.md` rather than maintaining a second copy. Configure Claude's
project-instruction loading explicitly; a small tracked `CLAUDE.md` importing
`@AGENTS.md` is a compatibility option. Make the commit and goal skills available
through the selected agent's supported discovery path, with native-tool wording
where needed. Disable unwanted automatic memory/history reuse and inherited
conversation identities while preserving legitimate authentication and managed
policies. See [Claude instruction loading](https://code.claude.com/docs/en/memory).

Choose settings sources explicitly and disable auto memory separately;
`setting_sources=[]` does not disable memory, global configuration or managed
policy. If project discovery is disabled, explicitly supply the required
instructions and skills instead of assuming `CLAUDE.md` loaded. Do not use
`--bare` as a general fresh-context equivalent: it skips automatic project
instructions, skills and other integrations, and does not read subscription
OAuth credentials. Keep authentication and settings discovery separate, without
relocating credentials to a disposable directory. See [SDK settings discovery](https://code.claude.com/docs/en/agent-sdk/claude-code-features#what-settingsources-does-not-control)
and [bare mode](https://code.claude.com/docs/en/headless#start-faster-with-bare-mode).

Keep `./setup.sh` as the sole development setup entry point. Integrate selected
agent policy preparation and readiness reporting there; do not install or
authenticate a coding CLI automatically during tests or launcher preflight.
Preserve existing personal settings, trust choices and inactive-agent policy
files. Keep credentials, user paths, local permission decisions and session
state out of Git. Add narrowly allowlisted shared Claude assets and ignore
private state, following the existing Codex portability boundary.

The privileged setup dispatcher currently exposes a fixed `codex-rules`
operation. Do not silently repurpose its privileged authority for Claude
installation or general file writes. Route new user-owned configuration outside
the privileged dispatcher; any genuinely necessary managed host policy needs
an explicitly scoped installer and the existing setup/approval process.

## Remote execution, Watch and failure handling

Replace Codex-specific SSH PATH checks in both launcher dispatch and Watch
controls. Resolve the executing checkout and its configuration before checking
its selected CLI; prepare native user-local installation paths as needed without
sourcing arbitrary interactive shell startup files. The selected agent's login
must belong to the actual remote execution account. Client authentication and
plugin connections are not transferred to the server.

Watch continues to observe the same bounded transcripts, run identities and
mailboxes. Add the recorded agent to session metadata alongside native model
and effort. Keep start/resume/reload commands unchanged; restarting from Watch
reads the executing checkout's configuration at the same safe boundary as
terminal execution. Observation and stop actions do not require a coding CLI.

Normalize failures into capacity, rate limit, authentication, permission denial,
provider refusal, unsupported capability, malformed result and process/transport
failure. Preserve useful provider reasons without exposing credentials or private
conversation state. Existing response repair applies only to successful turns
with invalid workflow results; it must not reinterpret a provider refusal as
something the next model should work around.

Use bounded retry policy only for qualifying transient failures, accounting for
retries already performed by the native CLI/SDK. Keep capacity retries within
the same logical session and original task allowance. Any model fallback stays
within the configured agent's explicitly supported profile policy. Exhaustion,
missing authentication, refusal or missing capabilities must not trigger a
cross-agent fallback. The selected agent remains the config value.

## Delivery and validation

Implement incrementally without maintaining parallel workflow engines:

1. Keep the compatibility fix independent: accept the extra configuration key
   while leaving it unused. This allows ordinary tools to keep working before
   any adapter is ready.
2. Extract the existing Codex behavior into the common interface and Codex
   adapter. Replace native argument manipulation in every caller; reconcile the
   owning policy documents and native role profiles before activating selection.
3. Implement Claude batch and interactive transport, role configuration,
   permissions and preflight. Wire all agent callers through the shared resolver.
   Do not ship a selection that affects the coordinator but leaves translation,
   backend review or Git recovery silently using another agent.
4. Complete setup, SSH, Watch, skills and documentation integration. Update
   controller reload/dependency inventories, including
   `plan_launcher.RESPONSE_VALIDATOR_SOURCES`, so running controllers load
   changed adapter code at owned reload boundaries.
5. Enable configuration-driven selection only when each affected workflow
   satisfies its preserved contract for both agents. Missing support must be
   reported explicitly rather than substituted with the other agent.

Apply the [test scope mandate](Mandates/Test-Scope-Mandate.md) and
[test maintenance](../tests/README.md#all-established-regressions). Preserve and
adapt existing critical execution/ownership regressions and native process
doubles. Do not add tests for ordinary infrastructure branches, mirrors of the
profile table, or Watch widgets. New non-product tests require the explicit
authorization in [AGENTS.md](../AGENTS.md#tests-and-acceptance).

For implementation acceptance, exercise the actual shared boundary with finite
passing/failing results: selection from the executing checkout, ignored external
overrides, fresh sessions, correct schema/result ownership, pending input at
completion, interruption and cleanup, refusal versus transient retry, and
resume across a configured switch without losing work or resetting budgets.
Reuse existing checks where possible. Perform bounded real-agent smoke checks
for both adapters using a disposable checkout and maintained ownership/storage
routes; CLI help or synthetic events alone do not establish native compatibility.
No VM/product installation is required merely to qualify the agent transport.

The Claude interface constraints above were checked against official
documentation on 2026-11-06. They establish a feasible design route, not native
qualification of the agreed default model or remaining role/effort profiles.
Before enabling Claude, qualify
the chosen CLI/SDK versions, supported authentication, bridge process-tree
cleanup, required delegation limits and the result/input races described above.
Do not install Claude or add a dependency on its SDK for the Codex extraction
step; agent-free operations must retain their existing dependency boundary.

Verify that the proposed development assets stay outside
`Makefile.PACKAGE_SOURCE_FILES` and product-only archives; review
[source exclusions](../debian/source/options) if adding `.claude` or
`CLAUDE.md`. Run `tools/build_package.py` after the final implementation edit
that can affect building/packaging, as required by AGENTS.md. Pure proposal edits
need Markdown link checks, not a package build or new tests.

Completion means that editing only `config/environment.json` selects the agent
for every repository-owned agent session, with no new launcher parameters,
hidden provider fallback, acceptance changes, or lost recovery state. This
proposal itself neither activates selection nor changes the current model,
goal, review or approval contracts.

### Codex live qualification

On 2026-11-06, Codex CLI **0.167.0** was exercised through
`agent_command`, `PreparedSession.preflight`, the shared supervisor and
`AppSession`. A temporary harness used disposable local clones, shared disk
scratch and a bounded retention journal; each native assignment had a
180-second deadline. No permanent test harness or regression tests were added.

- Batch and interactive sessions returned finite schema-conforming passing and
  deliberately failing results; the returned failed status was retained despite
  a zero CLI exit. These transport fixtures did not run workflow acceptance
  engines.
- Native `thread/goal/updated` notifications showed the exact objective active
  and complete without a token budget. `thread/goal/get` independently confirmed
  the preceding batch session's persisted completed goal and a fresh interactive
  thread's initially absent goal.
- Input queued at a real terminal-turn event withheld acceptance and changed a
  passing candidate to the requested failing result. Native `turn/steer`
  acknowledged active-turn input, reflected exactly once in the final response.
- Mailbox interruption exchanged a continuation.
- Sequential fresh monitor and worker sessions used the native Sol Low and
  Medium role pins. Native notifications and goal reads confirmed their exact
  completed goals. Helpers' deliberately failing results, including decoys with
  the coordinator's task ID, did not replace the coordinator's passing result.
- Catalogue preflight accepted all configured role profiles. Finite live sessions
  using the pinned `commit_helper` and `conflict_resolver` Sol High pair passed;
  an explicit Astra xHigh coordinator also passed. Agent-free launcher help,
  granular test listing and deterministic Git inspection remained available.

The clones were not trusted projects: the CLI explicitly disabled project-local
configuration, hooks and execution rules. Explicit adapter settings and native
role assets loaded, but this run does **not** qualify the disabled policy layer,
role permission enforcement or all workflow/role combinations. Global trust,
authentication, setup and permissions were not
changed. No live refusal,
capacity outage/fallback, full Git close-out/conflict/stash workflow, Claude
transport or configuration switch was exercised. These limits keep delivery
step 2 open under the next implementation step above.

### Trusted-worktree follow-up

On 2026-11-06, CLI **0.167.0** was exercised in disposable linked worktrees using
the shared disk allocator, a bounded retention journal and
`./setup.sh --test-tools-only`. Existing repository trust applied; no trust
entries, credentials or authentication were changed. Temporary fixtures are not
permanent regression tests or product assets. Earlier accepted transport/profile
checks were not repeated for renewal.

- Native `config/read` with the explicit checkout `cwd` showed an enabled project
  layer. A direct `git rev-parse` used the project-local allowance, a harmless
  command was rejected by a fixture's project-local forbidden rule, and an
  allowed workspace patch succeeded. An earlier shell-variable expansion
  required approval and correctly failed; no broader allowance was added.
- Both actual Git helper entry points passed native catalogue preflight with
  supervision intercepted. Injected catalogue failure prevented supervision in
  each caller. Their resolved Sol High profiles remained pinned. This checks
  caller readiness ordering, not an executed Git transaction or live model access.
- An E2E-configured coordinator invoked `e2e_adviser`, then `backend_reviewer`,
  sequentially with `fork_turns="none"` and no profile overrides. They returned
  readiness analysis and the expected bug finding for a synthetic grant fixture,
  reported exact-goal activation/completion and refused extra writes/delegation.
  The coordinator's completed goal was independently read through
  `thread/goal/get`. The combined assignment nevertheless reached its 240-second
  deadline while checking helper retirement: supervision returned **130** with
  **no coordinator result file**. Its component reports do not make that a pass.
- A read-only translation coordinator delegated one synthetic French record to
  `whatsnew_translator`. It preserved version, brand, URL and placeholder while
  treating an embedded write instruction as data. The helper refused extra
  writes/delegation and reported its exact completed goal. The coordinator's
  completed goal and read-only native turn context were independently inspected;
  forbidden files were absent. Its finite native result remained **failed**
  because explicit helper closure was unavailable: interruption left the
  completed helper listed. No real release synchronization or catalogue write ran.
- An isolated backend-review assignment returned a finite **passed** result with
  the expected synthetic bug finding, write/delegation refusals and completed
  goals. Its reported reviewer configuration was Astra xHigh with an inherited
  **workspace-write** sandbox and read-only role instructions. Its claim that the
  helper was closed does not establish explicit retirement. This passes the
  report fixture, not delegated isolation or the full workflow.

The [native subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
confirms that custom agent files cannot replace the parent's sandbox/approval
settings. The role assets' `sandbox_mode = "read-only"` therefore do not establish
separate read-only enforcement. Self-refusal proves instruction compliance, not
sandbox-level denial of a delegated write. The tool surface also exposed no
explicit close operation. Joined completed reports and eventual supervised
shutdown do not prove the owning workflow's close-before-handoff boundary.
Independent review using the same exact goal confirmed these native qualification
limits. The user subsequently deferred their remediation from delivery step 2's
bounded close-out; the failed and incomplete results above remain unchanged.
Catalogue-preflight cancellation before supervision also remains unqualified.

No provider/model refusal or capacity-recovery path, full Git close-out/conflict/stash workflow,
Claude runtime or configuration switch was qualified. These remain separate
from the accepted finite checks and the deferred delegated-role work.
