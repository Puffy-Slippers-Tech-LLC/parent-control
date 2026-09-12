# Unattended implementation sessions

The repository launcher runs one fresh `codex exec` per coherent implementation
slice, then starts the next session after a verified handoff and cleanup. It
continues until the [master checklist](Test-Automation.md#unfinished-tasks) is
complete, a blocker needs outside input, or you request a stop.

Start from this checkout in a terminal:

```sh
tools/codex_slices.py start
```

This returns your shell prompt and starts a detached local process. Live Codex
messages, commands, command results, changes and tool updates continue to appear
in that terminal as the CLI emits them. The launcher renders a text stream,
not the interactive Codex screen. The launcher does not log session output;
Codex saves its own conversation for resuming.
The process can keep running after you close the terminal; output after closure
is discarded unless another monitor is connected. Starting without a terminal
also discards unobserved live output. Run `start` again while the launcher is
ongoing to attach a foreground monitor of future output, including subsequent
slices. This does not start or resume work, change limits, or modify session
state; Ctrl+C disconnects only that monitor. Multiple terminals can monitor the
same run. Output is passed through a same-user local socket, never saved to a
new log, and missed output is not replayed. A slow monitor may be disconnected
to keep the worker moving. The launcher queues an explicit shutdown event with
its final notice so monitors exit without waiting for later socket teardown. A
closed connection also ends the monitor.
Launchers already running code from before monitoring support cannot accept a
monitor; `start` reports that limitation and leaves their work unchanged.
Use `run` in a dedicated terminal and another terminal for `status` or `stop`.

The default has no slice-count or overall time limit. The computer
must remain powered on and awake, Codex authentication and usage capacity must
remain available, and the host's existing test authorization must remain valid.
In particular, the project's Polkit grants require an active local administrator
session; detaching the launcher does not provide authorization after logout.
This launcher does not install a boot service or restart itself after a reboot.

For an initial one-slice run, use `start --max-slices 1`. To watch the launcher
in the foreground, use `run` instead of `start`.

```sh
tools/codex_slices.py status
tools/codex_slices.py stop
```

Help (`tools/codex_slices.py --help` or `-h`) and `status` have maintained
inspection-only Codex rules. Use the executable directly, without a `python3`
prefix; setup renders relative and checkout-absolute forms. Starting or
controlling the loop still needs authorization for that work. Use the native
`apply_patch` tool for workspace handoff edits. See the
[inspection and editing contract](Approval-Tools.md#launcher-inspection-and-workspace-edits).

`stop` requests a stop at the next safe slice boundary. It does not terminate
Codex or a running test. In foreground mode Ctrl+C has the same behavior. Start
again with the original command to continue from the saved documents.

To reload launcher code changed by another session, queue a restart:

```sh
tools/codex_slices.py restart
```

The command returns promptly. A detached waiter requests the existing safe
stop, waits for the current session's handoff and cleanup and for the old
launcher/worker lock to be released, then executes the launcher file from disk.
Edits made while it waits are included. This also works with an older running
launcher that already supports the run-specific `stop` protocol. The new run
is detached, with live output in the terminal that issued `restart`; existing
monitors disconnect when the old launcher exits. Use `start` to attach again.

A later `stop` or `kill` cancels the queued restart, and repeated `restart`
requests replace the pending one. Completion ends the loop without relaunching;
a blocker, interrupted work or unconfirmed cleanup prevents automatic restart.
If no launcher is ongoing, `restart` starts no work; use `start` instead.
Restart messages go to `output/codex-slices/launcher.log`.

Saved `--max-slices` and `--max-api-retries` limits carry forward unless supplied
on `restart`. The slice count starts over for the new run. Older launchers that
did not save these limits use defaults (unlimited slices, 12 retries), so pass
the original limits explicitly when restarting those runs.

When the session stops or is killed, the launcher prints a bold red status
message in its live terminal and exits automatically. The terminal stays open;
no additional Ctrl+C is needed. Redirected output stays plain text. Shutdown
does not wait for output pipes inherited by tools after the Codex child exits,
and does not signal those tools. Interrupted work still requires reconciliation.

To interrupt the active session without waiting for its slice to finish:

```sh
tools/codex_slices.py kill
tools/codex_slices.py status
tools/codex_slices.py start
```

`kill` targets this launcher's current run. The supervisor checks the request
while Codex is running, sends SIGINT to its exact child, and uses SIGKILL after
two seconds if that child remains alive. It never signals saved PIDs, process
groups, unrelated sessions or VM operations. It records a `killed` outcome;
interrupted work and cleanup remain unconfirmed. Wait for `status` to show
`killed` before resuming; the checkout lock still prevents overlapping workers.
If an owned operation still holds that lock, collect/reconcile it first.

`start` runs detached and automatically uses the killed session's exact saved
Codex thread ID; otherwise it starts a fresh session. Use `run` for the same
behavior in the foreground. The resumed session's first instruction is to reconcile interrupted operations
and cleanup before continuing. After a verified handoff, the usual fresh-session
loop continues; `--max-slices` and `--max-api-retries` also apply. `stop` and
foreground Ctrl+C retain their existing safe-boundary behavior. Runs started
by the older ephemeral launcher cannot be resumed; stop those normally and
start the updated launcher. A kill before Codex reports a thread ID has no
conversation to resume; reconcile it and use `start --reconciled` instead.

## Token use and output

Each fresh or resumed worker receives the concise-output instructions in the
[prompt](Unattended-Prompt.md), and the launcher's report schema requests a
concise, self-contained summary. Follow the shared
[output rules](Implementation-Workflow.md#reduce-unnecessary-model-output):
avoid repeated scripts, patches, command transcripts and irrelevant tool reads;
retain material findings, failures, verification, cleanup and recovery details.
The selected model/effort and acceptance checks remain explicit, and brevity does
not impose a new response-length or tool-output limit.

Live rendering, monitor fanout and saving already-produced output are local
operations with no additional model tokens. They remain fully available for
operator diagnosis. Model-written commands and reports use output tokens, and
tool results read by the worker use input tokens. Hiding the terminal stream
cannot recover tokens already used. No measured saving is claimed; existing
lifecycle usage counts remain available without reading raw session history.

Prompt/workflow changes apply at the next slice boundary, including under an
existing supervisor. Launcher/schema code changes apply on its next invocation;
finish current work and cleanup before restarting an ongoing launcher.

## Cumulative session summaries

After each session exits, the launcher appends one report to
[Test-Automation-Slice-Summary.md](../Test-Automation-Slice-Summary.md). This is
the durable history to read after leaving the launcher unattended. Each report
keeps its session number and local completion timestamp to the minute in the
heading, followed by exactly six bullets in this order:

```markdown
## Session <number> — <YYYY-MM-DD HH:MM timezone>

- Progress: **Solid and healthy**
- Task: Task <ID> — the concrete objective pursued.
- Duration: <whole minutes> minutes
- Completed: Actual changes and findings. State what remains unfinished.

- Verification and cleanup: Check results and counts, material failures and recovery, evidence path, and final command/VM/export cleanup state.

- Next session: Task <ID>: the concrete next action. Next settings: <model>/<effort>, Standard.
```

Progress is a short overall assessment, placed first, immediately before Task.
Choose one bold value: **Solid and healthy** when verified work advances the
task and a concrete, feasible next action remains (or acceptance is complete);
**Nearly blocked or stalled - need intervention** when repeated attempts yield
no meaningful advance, an unresolved prerequisite prevents the next action, or
outside input is needed. Base the rating on this session's evidence and the
active handoff, not test counts alone or optimism. Do not read historical
summaries to infer a trend. Keep the Progress line to the rating; explain the
reason in Completed or Verification and cleanup, and identify the needed
intervention in Next session. This is a progress-health assessment, not a time
estimate or a replacement for acceptance and cleanup status.

Duration is measured by the supervisor and rounded up, without a parenthetical
rounding note. Keep Task, Duration and Completed adjacent; separate Verification
and cleanup and Next session with blank lines. Use concise prose and preserve
acceptance limits, evidence and material failure details. Put a blocker or
required intervention in Next session; omit next settings when no work remains.

Compared with the older format, Progress comes first, followed by Task and
Duration. Remove the duplicate Completion bullet, routine Outcome, current
Settings, Processing, Attempt, CLI token counts and Supervisor bullets, and all
remaining-session/time estimates and their basis. Next settings belongs at the
end of Next session. Lifecycle metadata remains in the existing private control
records. Exceptional outcomes and supervisor recovery notes belong in
Verification and cleanup so simplification does not hide uncertainty.
Session 41 illustrates the other five fields and remains unchanged; future
summaries add Progress above Task. This guidance-only addition still requires
support in the launcher's structured schema and renderer before automated
reports can emit the sixth field; restarting alone does not add that support.

The launcher opens the document **write-only, in append mode**. It never reads,
summarizes, rotates, truncates or rewrites earlier entries. Session numbering is
kept in control state, without scanning the log. Workers are instructed to
exclude this file from reads, searches and diffs; only the compact task handoff
is carried forward. The final response contains the new summary, and the
supervisor adds measured timing and appends it before launching another session.

Blocked and failed sessions get an end entry too; missing/invalid reports are
marked unconfirmed in the same layout; use the intervention rating when progress
or cleanup cannot be confirmed. A transient retry gets its own entry.
If writing a summary fails, the loop stops for review. Power loss or forcibly
killing the supervisor can prevent its final append; the recorded active state
requires reconciliation. No in-session chatter is appended to this document.

## What carries between sessions

The [unattended prompt](Unattended-Prompt.md) authorizes the documented successive
slices and model/effort choices under the
[quality and allowance policy](Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff)
when you launch the run. There is no separate “Go ahead” or settings pause for
authorized work. Execution policies and actual denials continue to apply.

The [implementation workflow](Implementation-Workflow.md) still owns selection,
scope, verification, acceptance and the compact handoff. Each worker reads
Continuation.md, the relevant active task and current files. The supervisor
starts a fresh conversation at each normal slice boundary. Only explicit
`resume` reopens the killed conversation. Standard project instructions and user
configuration still load normally. Workers persist sessions in Codex's own
session storage so they can be resumed. Recovery also uses the task handoff,
operation evidence and control metadata.

## Model and effort selection

The supervisor reads exactly one settings line from Continuation.md before
**each fresh slice**, including after a normal stop/start or queued restart.
The worker reassesses the next slice's model and effort separately under the
policy above, records the reason in the active task handoff, and mirrors it in
Continuation.md. For settled implementation the line is:

```text
- Settings: **`gpt-5.6-sol` / `high`**.
  Reason: the contract and helper are proven; the next slice adds specified cases.
```

Keep that exact punctuation and one line, substituting the selected model and
effort. Supported models are `gpt-5.6-sol`, `gpt-6-astra`, `gpt-5.6-terra` and
`gpt-5.6-luna`; efforts are `low`, `medium`, `high`, `xhigh` and `max`. Selection
must follow the policy: higher efforts need a concrete reasoning justification,
and routine work only qualifies for lower settings when its checks are adequate.
Missing, duplicate, malformed or unsupported settings refuse before worker
launch; no model call or silent fallback makes that decision. The selected
model must be available to the signed-in account.

Every worker receives explicit model, effort and `service_tier="default"`
overrides, so a global Astra/max or Fast preference cannot override the handoff.
The terminal and state record the selected settings and Standard processing.
An interrupted conversation resumed by `start` keeps its recorded model/effort
for reconciliation; after its clean handoff, fresh slices use Continuation.md
again. Settings edits do not switch a running conversation. Missing or invalid
saved resume settings require reconciliation rather than guessing a replacement.

**Activation:** these are development-launcher changes (`none`), with no product
data migration or helper installation. An already-running old supervisor keeps
its loaded code; use the safe `restart` above to load changes at its next clean
boundary. A stopped launcher's next `start` loads them directly. There is no
blanket Astra pin; historical evidence records the settings actually used then.
Slice budgets remain review points, so an active VM attempt can exceed 30
minutes while it finishes collection and cleanup.

The supervisor retains already-reported CLI token counts in private lifecycle
records, including cached input and reasoning output when supplied; they are
omitted from the operator summary. These subcounts must not be added again to their
input/output totals. Raw tokens do not measure weekly allowance consumption;
use the account's displayed allowance alongside verified progress when exposed.
No new model call, transcript scan or replay benchmark is needed for this report.

## Completion and interruption

Each worker returns structured status, progress, cleanup and summary fields. The
supervisor requires a successful completed CLI turn and validates the result.
It checks the authoritative checklist before accepting completion. Empty,
malformed or deleted task entries cannot make a running backlog complete.
The model must still perform the task's acceptance checks: checkbox validation
alone cannot establish test correctness.

When [Task 20 recovery](Task-20.md#bounded-recovery--2026-09-11) resumes after
the prioritized independent work in checklist order, workers
also maintain cumulative working time/attempts in its existing handoff and check
the specified milestone thresholds. An unmet stop checkpoint produces the
existing `blocked` result with blocker `decision` after cleanup, which stops the
supervisor even if another backlog task is independently ready. This is enforced
by the task/prompt and existing blocked-result handling; the launcher does not
independently calculate an hours budget. A restart does not renew a pending
decision or reset the ledger. The normal `start` command needs no custom prompt
or code refresh for these document changes.

Only one supervisor/worker pair can hold this checkout's loop lock. The loop
does not lock out independently opened editors or interactive Codex sessions;
let it own implementation of this backlog while it runs. Existing guarded test
launchers continue to serialize VM access. Source changes are kept in the same
checkout, including uncommitted changes; starting a session does not reset Git.

The [VM clearance](Implementation-Workflow.md#vm-availability-for-all-tasks)
applies to the whole backlog and supersedes historical writer-pause requests.
Each fresh slice reads the current unattended prompt and task documents; an
already-running slice finishes its current work and cleanup before applying
the next-action change. No launcher restart is needed to load the revised
prompt at the next slice boundary. Keep this clearance in subsequent handoffs.

An explicit transient API failure before any tool use is retried with increasing
delay, capped at one hour. The default permits 12 consecutive retries; change
this with `--max-api-retries N` (0 disables retries). A tool-using interrupted
turn, missing handoff, uncertain cleanup, authentication failure or no progress
stops for review. The launcher does not retry an uncertain VM operation.

For a normal `blocked` result, resolve the concrete issue in the active task
handoff and start again. For `launching`/`running` state without a live loop, or
`needs-review`, first reconcile the recorded attempt, current task handoff and
any owned operation using the workflow and guarded diagnostic tools. Finish/reconcile its
collection and cleanup, update the handoff, and then use:

```sh
tools/codex_slices.py start --reconciled
```

This is an operator acknowledgement, not a cleanup command. It still refuses
an occupied lock and never kills a process or overrides VM ownership. Do not
delete locks, state, or logs to bypass a refusal.

## Prerequisites and progress records

Use an already installed, signed-in Codex CLI with `exec --approve-for-me`,
`--json`, `--output-schema` and `--output-last-message` support, plus
`exec resume --output-schema`. The launcher checks these flags before running.
It uses automatic approval review with the
workspace sandbox and retains existing user/project rules. Account and managed
policy must permit that mode; denied actions remain blocked. Existing machine
preparation remains through [setup.sh](../../setup.sh), as described in the
[approval guide](Approval-Tools.md). The launcher installs no dependencies or
permission rules.

Control metadata is private to the invoking user under the Git-ignored directory
`output/codex-slices/`: `state.json`, append-only `launcher.log`, and a unique
directory per attempt with the final structured response. Lifecycle events
include timestamps, CLI thread IDs, exit status and token counts. `cli_pid` is
non-null only while that exact owned CLI child is live. `status` also shows the
session count and latest completion time, duration and outcome. Raw
CLI stderr, command output and in-session assistant prose go only to the live
terminal, including for detached `start`; they never go to `launcher.log`.
The cumulative summary document is ordinary repository documentation, so final
reports must contain no PII or secrets. Existing task evidence and application
logs follow their own retention rules. Shell redirection or terminal recording
can still capture what you choose to display.

On an interactive terminal, assistant messages and session summaries render as
Markdown with headings, emphasis, lists, tables and highlighted code blocks.
Each block uses the live output terminal's current width, including after a
resize; inherited `COLUMNS` does not constrain it. Already printed blocks keep
their rendered line breaks. Launcher code changes take effect on the next
launcher invocation; an existing supervisor retains the renderer it loaded.
Messages render once their CLI item completes. Simple reads of a single `.md` or
`.markdown` file (`cat`, `head`, `tail`, `sed -n` line ranges, and
`tools/read-only slice`) also render on successful command completion, including
reads wrapped by the CLI's shell. The same single-file reads of source files
use syntax highlighting for recognized languages, including Python, JavaScript,
JSON and shell. Command labels and exit statuses are also styled. Other command output streams as it arrives;
search results, diffs, numbered source and mixed commands stay literal.
Rendering uses `python3-rich`, included by
`./setup.sh --dependencies-only`. If it is unavailable, output is redirected, or
`TERM=dumb`, the launcher uses plain text. `NO_COLOR` disables rendering colors
while keeping the terminal layout. Saved summaries remain ordinary Markdown.

The host-safe supervisor regressions use a fake local Codex executable:

```sh
tools/run-unit-tests tests/unit/test_codex_slices.py -q
```

No live model, installed-system test or VM is used by these regressions. This
is development orchestration; package activation is `none` and no application
data migration applies.

Official interfaces: [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
documents scripted runs and structured output;
[automatic review](https://learn.chatgpt.com/docs/sandboxing/auto-review) describes
approval handling and denials.
