# ONPC Watch

Open run status and live UI/VM viewers in a VS Code editor tab.

Run `./setup.sh --watch` as your desktop user to install or update this extension.
Reload VS Code after updating it. Open a trusted ONPC checkout and click the
full-color product logo at the right end of the editor tab headers. Its tooltip
is **ONPC: Watch**. The button appears
automatically for ONPC clones and Git worktrees, regardless of branch, and hides
when no ONPC checkout is open. Adding or removing workspace folders updates it.
The bundled icon is a copy of `data/app_logo_titlebar.png`.
You can also press **Ctrl+Shift+P** and select **ONPC: Watch** (`onpc.watch`).
Repeating the command reveals the existing tab. Multiple workspace roots offer
a checkout picker.

The tab starts with a 30:70 left/right split. Drag the divider to resize it;
the tab remembers its ratio. Focus the divider and use the arrow keys to resize
with the keyboard, or double-click it to restore 30:70.

The left panel shows **Run Status** across related Git worktrees, using shared
runner discovery and the pipeline dashboard. Each concurrent launcher gets its
own section, including launchers in the same worktree. Sections
share the panel in equal sections initially. A `run-tests` child that publishes
its controlling launcher is shown through that launcher's progress, even across
worktrees. Independent runners keep their own sections. Older child runs without
that publication remain visible until their next normal start.
The horizontal dividers can be
dragged to resize adjacent sections, or focused
and adjusted with Up/Down. The icon immediately after each copy button toggles
**Collapse** / **Expand**. Collapsing leaves only that launcher's title bar, tabs
and buttons; expanded sections fill the remaining height. Expanding restores the
selected tab. Inactive launchers (finished, failed or stopped) collapse by default,
including when a running launcher exits. A new active run expands by default.
Manual expansion, collapse and resizing survive live refreshes until the next
run or activity transition. Sizes last while Watch is open.
Click anywhere in a launcher tile to select it. Clicking empty space in its
title bar toggles selection instead.
The selected tile has a highlighted border and tinted background. Selecting
another tile clears the previous selection. Title-bar links and buttons select
their tile without unselecting it, while performing their usual action.
Dividers remain active beside collapsed sections; resizing expands them and
restores their selected tabs.
When a launcher exits for any reason, its
section and all four tabs retain their contents, including while other worktrees
remain active. Reconnecting restores the latest retained run in each idle
worktree from its existing run files. Session input is disabled once its owner
exits. Retention uses existing run files and reader memory; it adds no disk persistence.
Each title shows two rows: a server icon and server name (`local` or the SSH host)
above the branch and launcher, e.g. `[test] fix-tests`. It
places 28 px icon buttons after the hostname on the same row as copy and collapse:
**Stop** (solid square) while active, **Undo** while a cancellable stop is pending,
or **Resume** (play) while idle. It is disabled once stopping begins,
while disconnected, or when saved command parameters are unavailable. Clicking
asks for confirmation with **Stop**, **Resume** or **Cancel stop request**, and **Cancel**.
Confirming Resume sends the command silently in the background on that same host
and checkout, without opening a VS Code terminal. Follow progress in Watch.
Stop and cancel-stop open a VS Code terminal. Watch uses its shared
`Output.execution_plan` property to identify execution-plan runs: Resume reruns
their saved command with the same parameters. Other launchers, including `fix-tests` and `run-tests`,
receive only `--resume`, which restores their saved selection. Stop and cancel-stop
use the retained parameters with `--stop` or `--cancel-stop`. Earlier lifecycle
flags (`--stop`, `--cancel-stop`, `--resume`, `--reload`, `--reset`) are removed
from replayed parameters. The action button's hover tooltip and confirmation
dialog both show the exact public command to run. Failed actions light the footer error icon
with captured process output and exit status. Repair queue Stop retains its scope without reselecting VMs.
Older runs without saved parameters require one normal launch
before this control becomes available.

Watch infrastructure failures show a flashing red circle with a white **!** at the bottom left,
before **Reconnect**. Hovering highlights the icon; clicking opens the shared
**ONPC Watch error** dialog and stops the flashing. The icon remains available
to reopen the latest details, and a new distinct error after dismissal flashes
again. Errors never open the dialog automatically. Errors recorded before Watch
opens appear on its icon when it opens.
The live view remains visible through a translucent gray backdrop.
The full diagnostic text is selectable and scrollable horizontally
and vertically; **Copy all** copies it, and **Close** dismisses it. Additional
distinct errors append to the open dialog; identical failures do not restart
flashing for the rest of the VS Code session. Diagnostics also go
to the **ONPC Watch** Output channel.
This covers local Watch connection, rendering, clipboard, screenshot and action
failures. Recoverable request timeouts retry for both local and remote readers.
SSH connection failures do not trigger the flashing error icon; the failed host's footer cloud
icon opens their details. They also appear in footer
status tooltips and the Output channel. Launcher-owned **Error** tab contents remain separate and do not
trigger this dialog.
The footer omits reader connection messages; server icons retain connection
status tooltips.
Recovery retains panels, selected tabs, scroll positions and the last received
frame. Retained frames remain labelled as old until fresh pixels arrive; actions
and session input are disabled while their source is disconnected. Switching to
another editor tab preserves the Watch page while pausing observation.
The Output channel timestamps reader starts, exits, failures and successful
connections. Slow responses (at least two seconds) and failures include the
operation, elapsed time and received byte count; request text is not logged.
Watch owns action process streams through a Python standard-library PTY bridge
that preserves interactive input and forwards terminal resizing. Start failures
and nonzero action exits light the error icon, including Python tracebacks and SSH diagnostics.
The diagnostic includes the invocation, checkout, host, exit status and up to the
last 1,048,576 characters of process output, with terminal control sequences
removed; omitted earlier output is explicitly labelled.
Closing an action terminal does not open an error dialog.
Local and SSH actions load NVM's selected default when `codex` is
missing from their inherited PATH, so GUI startup does not hide an NVM-installed
CLI or its Node interpreter. Codex must already be installed and authenticated.
**ONPC: Watch Terminal Diagnostic** reopens the last failed action's captured
diagnostic in the same copyable dialog.

Beside Stop/Resume, **Reload** (circular arrow) asks for confirmation with
**Reload** and **Cancel**, showing the exact command. Confirming sends `--reload`
with the saved parameters, stripping earlier lifecycle flags, on the same host
and checkout. Reload is disabled while stopping, disconnected, or when the source
adapter has not published its reload command.
While an active launcher's reload request awaits a safe boundary, its title
shows `(Reload Requested)` in the same orange as **Stop Requested**. The suffix
clears when the controller accepts the reload or the launcher exits; a stop
request takes precedence.
The title
keeps **Status**, **Launcher**, **Error** and **Session**
links at its right end. When narrowed, each title row truncates with an ellipsis.
Further narrowing moves the title and action
buttons onto the first row and all tabs onto the second row. As that row narrows,
the tabs wrap onto additional rows until they stack vertically. Wrapped tabs have
equal widths and centered text. The left panel's minimum width fits both the
shortened title with its action buttons and the widest tab below it. Hover over a
launcher title to see its saved command with all parameters, including
argument quoting. The title remains a short `[branch] launcher (status)` link.
Clicking copies the full runnable command with its saved parameters, such as
`tools/write-e2e --branch worktree <parameters>`, relative to the repository root.
The explicit branch selects the displayed launcher's checkout even when run from
`main`. Older runs without
saved parameters show only the plain title.
The name comes from the launcher's `current.json`
publication, including custom plan launcher names. Older runs without a published
name show `launcher` until their next start, attachment or reload request.
After `--stop`, an active launcher's title shows `(Stop Requested)`, with
**Stop Requested** in the same orange as **Repairing** and **Verifying**. The
button becomes an undo icon with tooltip **Cancell stop request**, invoking
`--cancel-stop`. Successful cancellation clears the pending status on the next
refresh. Once the worker accepts the stop, the title shows **Stopping** and the
button is disabled. Cooperative cancellation and older launchers without undo
support also disable the button once stopping is requested.
Each enabled stop, resume, reload or cancel-stop button asks for confirmation using
VS Code's built-in modal warning dialog. Its button colors follow the host theme;
the public extension API does not expose a destructive/red button style.
The title switches to the recorded final status when the launcher exits.
Failed launcher titles, including their command hyperlinks, appear in red.
**Status** shows the current run status, **Launcher** shows
the launcher terminal output, **Error** shows the shared launcher's **Last Error**
and **Status** fields with the same colors and elapsed ages, and **Session** opens
the session transcript and chat.
The Launcher tab streams running command output, including baseline preparation
phases before VM startup; it does not wait for the command to finish.
Each launcher's tab selection is independent: opening **Session** in another
worktree leaves existing Session panels open and refreshing. Chat stays routed
to the session displayed in its own panel.
For `fix-tests`, the link shows **Session 1**, **Session 2**, and so on for
successive agent sessions repairing the same case. The number remains visible
between sessions and during verification, with strikethrough while the session is
inactive and its chatbox is disabled. Once the repair is accepted and closed,
the link returns to struck-through **Session**; the next case starts at **Session 1**.
While an agent repairs an integration check, its **Status** row ends with
` | Session x: <duration>`, using that session's elapsed time and the shared
`01:25` / `3h 45m` duration format. The suffix disappears when the session finishes.
The preceding check duration includes the whole case, including repair sessions
and retries; the session duration measures only the current agent session.
For `fix-tests`, Last Error includes the failing check, the runner's error text
(or a readable summary of a structured failure, falling back to a bounded text
output tail), and its output-log path. Full JSON results remain in that log. Reload launcher
changes with `tools/fix-tests --reload`; `./setup.sh --watch` updates the extension.
The links remain available in every view, including while idle. The copy icon
before **Status** copies the current tab's body as plain text to the clipboard;
in **Session**, it copies the displayed transcript.
For every execution-plan launcher, including `write-e2e`, **Status**
starts with **Total Tasks: completed/unfinished/total | duration**
on one pinned line, using the shared launcher counters and colors. Narrow panels
scroll the summary horizontally instead of wrapping it. A divider
spans the panel above the completed task recaps and current task/session rows.
The **Total Tasks:** label is bold. When the whole plan
finishes, the same line adds **Ended:** with the local completion time (`HH:MM`),
and the launcher title, including `(finished)`, turns green.
The summary stays pinned at the top. Only the task/session history between the
full-width dividers scrolls, following the bottom until you scroll up.
Below it, a pinned read-only box shows the latest text output. Its bold label
sits within the divider line and matches **Session N** while a session is
active; otherwise it shows **Launcher**.
Session text uses the same simplified rendering even when the Session tab's
Simplified switch is off. Launcher text uses the same terminal rendering and
shows the latest nonempty block separated by blank lines. Both boxes show four
lines at a time and scroll vertically to reveal the complete selected output.
New output starts at the top; streaming additions preserve your scroll position.
During task close-out, the title shows `[branch] launcher (Closing Task)`, with
`Closing Task` in green. This includes processing the finished task response
while **Session** is struck through, validation, and the commit skill's commit,
push and propagation, including repository synchronization waits while an
accepted completion is retained for Git reconciliation.
Checkout synchronization and its repository lock waits show `Closing Task`
when a task completion is still pending. Boundary synchronization before new
work adds no title status.
The suffix disappears when **Status** shows the task's
green checkmark and task close-out has finished. Stop and reload notices take priority.
For every execution-plan launcher, completed and current task headings end with
` | <duration>` from the retained task clock across sessions. The session summary
ends with ` | <duration>` from its owner session clock.
The **Session** link shows **Session N** for the current task, including between
sessions and while awaiting an answer; it resets when that task completes.
Every execution-plan launcher inherits the shared pending-input controls,
including after restarting into an unanswered question.
While waiting for input, the Status body shows
`Paused - waiting for your answer (mm:ss +10m)` for timed questions.
The waiting text flashes in the same red as stopped/blocked statuses; the deadline
counts down every second from the current prompt's deadline. Answering removes
that timer; a new prompt starts a fresh countdown. Questions without a deadline
show `Paused - waiting for your answer (no timeout)` in the Status body.
Each click on **+10m** in
the Status body adds ten minutes to the current question's deadline, including
the launcher's actual wait. Questions without a deadline have no extension link.
**Session** is a blue, underlined link with a hand cursor. It replaces that
worktree's status with the shared launcher session transcript, chatbox and
agent/model/effort footer, including the Simplified toggle. The footer uses the
recorded session identity; older records show **Unknown agent**. Watch actions
use the destination launcher's shared agent environment preparation, so observing
or stopping a run does not require a coding CLI. The transcript includes
sent prompts and agent messages. Agent prose streams while it is being written;
the completed message replaces its provisional text, including any corrections.
Only completed messages enter the saved transcript. Launcher status metadata and
structured workflow results wait for completion before being interpreted.
Command and tool result bodies are hidden in
both modes; activity names remain visible and saved transcripts retain results.
Simplified mode pins the latest command activity to one clipped line above the
chatbox, with a divider separating it from the conversation. Each new activity
replaces the previous one; earlier activities stay out of the conversation.
Turn it off to see each activity with its original line breaks. Successful Read/Search exploration shows
the activity only; file contents and search matches stay out of both views.
The toggle also works on the retained transcript after the launcher finishes.
Click **Status** to return to run status and its waiting countdown.
The space before each link is outside its underline.
Waiting for input flashes unless reduced motion is
enabled. Enter sends chat directly; there is no Send button. Shift+Enter or
Alt+Enter inserts a new line. Input is
routed only to the displayed, still-current launcher session.
Recording links in **Launcher**, **Session**, **Status** and **Error** open through GIO using
the desktop's default video application for local sources. SSH sources transfer
the selected recording on demand and play it in a VS Code video tab. Inline
remote videos are limited to 64 MiB; larger recordings remain available on the
source host. Remote error logs open as text in the editor (up to 2 MiB).
Artifact transfer does not create local test-output copies.
Repair case totals show green completed, red failed and total counts. The failed
count is underlined; click it to open the cumulative `errors.md` in the editor.

The right panel contains the shared All grid across checkouts, UI worker and VM tabs,
VM progress, filtered command output and host resource usage. Screens are view
only. Tiles and viewer tabs group by worktree in the left panel's current order,
following changes on each refresh. Worktrees without a displayed run follow those
shown on the left. Start tests through the usual launchers. Select an idle VM tab to wait for
its next run. The Reconnect button restarts this tab's source connections.

The fixed **Run Time** tab follows **All**. It loads logged VM case durations only
while selected, refreshes the data once per minute, and unloads its body when
another tab is selected. Selecting it again loads fresh data immediately. The selectable,
full-width table keeps one latest duration and recording per case/VM pair, folded
into one row per case. **Case ID / Title** uses `[category] ID: Title` and shows
a **+** when multiple VMs exist.
Click it to expand a tree of `VM name | Run Time | ▶` children; **-** collapses it.
Children sort by their raw duration, longest first, before display rounding.
The folded recording button and the row's **VM name** and **Run Time** columns
use the slowest child. Cases also sort by that child's raw duration, longest first.
Durations use seconds below one minute (`20s`) and rounded whole minutes otherwise
(`12m`). Run time includes VM preparation
before the first selected case starts, matching the recording's preparation
boundary. Older timings use the linked recording's saved duration as a lower
bound when preparation was omitted. Repair sessions and earlier retries
are excluded; system lifecycle phases in one execution attempt are added together.
New lifecycle recordings join those phases into one video instead of retaining
only the final phase. Existing short recordings require a new execution to replace them.
The last system case in an attempt includes collection, restoration and cleanup;
its completion waits for those checks. A focused combined case has one recording
of setup, every validation step and cleanup. In shared attempts, the first case
owns setup and the last owns cleanup, without repeating footage in other clips.
The first column selects case rows; its header checkbox selects all available
rows. The footer shows the selected and total row counts. The trash button above
the table deletes selected rows, and each row's final trash button deletes that
row. Both require confirmation; bulk confirmation includes the selected row count.
Deletion removes saved timing records for all VMs in those rows, including older
duplicates in the displayed scope, while preserving recordings. Updated timings
require a refresh before deletion. Older source adapters disable deletion until updated.
Rows update only after all selected phases of a case finish. Unfinished attempts
publish no partial row; an earlier completed duration remains until replaced.
Case links open the existing case file in a new editor tab. The recording icon
uses the existing default desktop viewer route (or the SSH video tab). The
**Description** column shows a one-line scenario summary with an expand/collapse
chevron at its end. Expanding shows **Steps:** and **Expected:** labels, each
followed by an indented bullet list. Descriptions come
from checked-in scenario metadata, including for previously logged timings;
updating descriptions requires no test rerun.
Combined system cases list each validation and its expected result separately.
Retired case rows are hidden; their historical recordings remain intact. A new
execution records the combined case rather than joining recordings from earlier
runs. Changed combinations have an execution revision: older fragment timings
and clips stay historical and do not appear under the new group's title. A
single-owner lifecycle recording also includes the gaps between its phases,
including real reboots, through final cleanup.
Only executed, logged cases appear; this is not a test inventory. Small latest-only
records live in the shared `state` directory under gitignored `output/test-runs/`.

Each VM footer has an **SSH** toggle at the right, off by default. Turn it on
to show the filtered command output above the footer. The choice is retained
when switching viewer tabs until Watch is reopened. Long blue operation messages
truncate before the toggle, whose space stays reserved.

Immediately before **SSH**, **Memory: x.x GB** shows the VM process's resident
host RAM (RSS), including QEMU overhead, in decimal gigabytes. Its mini graph
reuses the footer chart renderer and shows the last minute, sampled once per
second through the existing watch feed without guest commands. The vertical
scale covers configured guest RAM and any higher observed RSS. Missing or stale
readings show **—**; gaps remain disconnected. History stays in memory and resets
when the VM instance changes or Watch reconnects. Existing VM collectors need
their next normal restart to publish this additional reading.

The camera icon at the right end of each tile's title bar saves that tile's UI frame
at its original resolution to the XDG Pictures directory's Screenshots folder,
without a Save dialog. Names follow `Screenshot From 2026-10-30 10-04-15.png`
in local time; repeated captures in one second add a numeric suffix.
A desktop notification appears for five seconds (subject to desktop settings).
Click it to open the default file manager with the screenshot selected, using
the standard desktop notification and FileManager1 APIs. This requires the
system Python's PyGObject/Gio bindings. With Remote SSH, saving and notifications
occur on the extension host's desktop.
It excludes the viewer's headings, command text and footers. Long titles truncate before
the camera, keeping it visible. The camera is disabled without a frame.

Three icon buttons at the right end of the viewer tab row select the tile layout:
**Auto** (the default grid), **Vertical** (one column), or **Horizontal** (one row).
The tab remembers the selection. Overflowing tiles scroll in the chosen direction;
overflowing tab headers scroll independently while the layout buttons stay pinned.

Immediately after **Reconnect**, the footer lists configured SSH hosts and any
additional SSH Watch source hosts, separated by `|`; local sources are omitted
from this connection list. A green cloud icon (the same icon as the remote launcher
title bar) means connected; a red slashed cloud means disconnected or connecting.
Hover over the name for connection status. After any connection failure, the
slashed-cloud icon gains hover feedback; click it to open the standard Watch
error dialog with the latest failure details. Failures never open it automatically.
Details remain available during retries and clear when that reader responds again.
Hosts disabled for VM scheduling are still observed. A host is connected when at
least one reader is responding and none has an outstanding failure. SSH launchers
and viewers retain their last received contents while disconnected, with actions
disabled. Fresh snapshots update them after reconnection.

The footer also shows hosts in `config/environment.json` order. Each host has a
server icon and hostname before its CPU, VM RAM and Disk readings and small
filled history graphs. When the hosts do not fit side by side, they stack with
one complete host per row. Extremely narrow views can scroll the readings horizontally.
Host configuration is read when Watch opens or reconnects, independently of viewer
source settings. SSH hosts use their configured `name` as the SSH alias with existing keys
and verified host keys; a read-only Python sampler runs in memory without requiring
a remote checkout. Connection details appear on the hostname tooltip; unavailable
hosts retain their name and last graph with **—** in place of current readings.
The graphs reuse the once-per-second samples, show the last minute on a fixed
0–100% scale, and retain history only in memory. Closing and reopening Watch or
reconnecting its reader starts fresh; pauses leave gaps rather than joined curves.
The last graph remains visible during retries; its sampling history starts fresh
when the replacement reader responds.

**VM RAM** sums cgroup v2 `memory.current` for all system libvirt QEMU VM scopes
on that host, including VMs outside the configured test inventory. It includes
guest RAM, QEMU overhead, helper processes, charged kernel memory and file cache,
without counting descendant groups twice. It shows decimal GB rounded to one
decimal place; the graph uses the percentage of total host RAM. Swap is excluded. With no
VM scopes it shows zero; unavailable accounting shows **—**. Stopping VMs removes
their scopes from the total. The change in overall host memory use can differ
because reclaimable cache may remain and other host activity continues.

**Disk** reports the busiest physical disk's elapsed I/O busy time, matching
`iostat %util`. It avoids adding overlapping request durations. This measures
activity rather than maximum throughput; 100% busy does not necessarily mean an
NVMe drive is saturated.

Every source uses the same [versioned bridge protocol](BRIDGE.md), including the
default local controller. The UI receives display snapshots and opaque IDs; it
does not read controller files, VM sockets or session mailboxes. The local adapter
is `tools/watch_webview.py`; it owns checkout discovery, authenticated local feeds,
run/session state and artifact validation.

Frames travel over private stdio, directly or over SSH, with one request in flight
per source and no listener port. The bridge forwards existing PNGs without
re-encoding, requests snapshots at 500 ms intervals, and renders
responses on arrival. Unchanged images are omitted. A slow source cannot block
another source. Hidden tabs stop requesting snapshots; closing Watch stops only
its readers/connections. Nothing is installed in the product or in a guest VM.
The reader reuses unchanged session/error formatting and desktop PNGs when only
the cursor moves. Updated readers also omit unchanged transcript/status bodies and
send cursor-only updates without the desktop PNG. The browser retains the decoded
desktop and unchanged transcript rows. Older readers continue using full snapshots.
Metadata caching evicts the least recently used entries within 64 entries and
4 MiB of JSON source data, while rechecking file ownership and safety on every read.
This observation cadence does not change launcher execution
or test recording rates.
No npm packages or compilation step are needed.

## Local and SSH sources

For interactive client onboarding, run `./setup.sh --connect-server`. It configures
key access, verifies noninteractive SSH, installs Watch and prints a command to
open a private workspace with local and SSH sources. Connection details live in
your home directory, outside Git. See the [setup contract](../../docs/Approval-Tools.md#one-time-setup)
for host-key verification and key-agent requirements.
The command selects from configured SSH hosts, uses `host.name` as the alias,
and reads `ssh_port` and remote branch paths from `config/environment.json`.
Only the private address and login username need to be entered. The first
configured remote checkout is the starting point; Watch discovers related
registered worktrees automatically. `./setup.sh --server` prints a connection
summary with the account, addresses, host-key fingerprints and registered worktrees,
and checks Codex login and Git remote read access. Use that summary during client
onboarding; no separate server inspection commands are needed. Independent clones
require separate sources.

With no configuration, Watch uses this checkout's local adapter and the SSH hosts
with branches in `config/environment.json`, including hosts disabled for VM
scheduling. Each remote host starts from its first configured branch checkout
and discovers related registered Git worktrees. SSH access must already be set
up; Watch never prompts for credentials. Independent clones require explicit
sources. Set
`onpc.watch.sources` in VS Code user or workspace settings to replace that default
or combine sources. Source IDs must be unique and stable; labels identify hosts
in viewer tabs; run titles show the SSH host or `local` above the branch name.
Footer hosts always follow `config/environment.json`.
Click Reconnect after editing.

```json
"onpc.watch.sources": [
  { "id": "local", "label": "This computer", "transport": "local" },
  {
    "id": "garage",
    "label": "Garage",
    "transport": "ssh",
    "host": "garage",
    "root": "/srv/onpc/parent-control"
  }
]
```

Use an existing SSH config alias with key/agent access and an already verified
host key. Watch uses noninteractive SSH without a PTY; it never installs remote
software, changes host keys or starts test execution. The remote checkout must
contain a compatible adapter and its prerequisites. Authentication/host-key
refusals require fixing access and clicking Reconnect. Other failed connections
retry asynchronously with a 1–15 second backoff, including idle or initially
unreachable servers. Readers connect asynchronously at startup; Watch does not
wait for SSH handshakes or offline hosts before opening. Healthy connections reuse
persistent SSH readers; no separate
SSH ping processes are started. Host resource readers are polled once per second,
and SSH keepalives request a response after one second without received data
(three missed responses close the connection). Pending snapshot requests also
have a ten-second deadline. Status detection is therefore bounded by connection
and request timeouts rather than guaranteed to change within one second. Hidden
Watch tabs pause observation; closing Watch stops its readers.

On an Ubuntu 26.04+ remote host, rerun `./setup.sh --server` as the checkout
owner to prepare the test environment, enable SSH and prevent server sleep,
including on a desktop laptop. Follow the printed host-key and connection details;
see [headless setup](../../docs/Approval-Tools.md#one-time-setup) for firewall,
credentials and power-management behavior. On the client, configure the SSH alias,
authorize its public key, and verify `ssh -o BatchMode=yes myserver true` before
adding the source. Set `root` to the actual remote checkout path. Start
`tools/fix-tests unit` in that checkout over SSH after configuring the remote
account's Codex login and Git access. The launcher owns detached execution;
Watch connects to observe it independently.

Each source can optionally specify a `command` argv array instead of the default
Python reader. A future Kubernetes adapter can run on the SSH host and implement
the same protocol, without changes to the bridge or UI. That backend is outside
this implementation. Configured commands execute as the extension/SSH user in a
trusted workspace; store connection credentials in SSH configuration, not settings.

Remote controllers own execution and durable run state independently of Watch.
Closing Watch, losing Wi-Fi or rebooting this computer does not cancel remote
work. Reopening Watch reads saved source settings, reconnects and reloads retained
remote run status, logs, transcripts and recordings. Normal source retention
still applies. Chart history, undelivered text and other presentation-only state
are not durable execution data. An interrupted input acknowledgement is reported
as unknown delivery and is never automatically replayed; review the transcript
before sending again.

This is a Linux workspace extension. With Remote SSH, install it and open the
checkout on the extension host; SSH source connections originate there. A source
configured as local always means that extension host. VS Code Workspace Trust is
required. Activate extension changes with `./setup.sh --watch` and reload VS Code;
no product installation or restart is involved.
