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

The left panel has a **Launchers** toolbar with right-aligned **Auto**,
**Horizontal** and **Vertical** layout controls. It defaults to **Vertical**;
the viewer defaults to **Auto**. Both panes share the same layout controls and
tile grid, and remember their layout choices independently. Choosing a layout
expands all tiles in that pane. Launcher dividers remain available in Vertical
mode and retain resized proportions when returning to that mode.
In Auto and Horizontal modes, minimized launchers use the same compact title
strip and overflow menu as minimized viewers, leaving the grid space for expanded
tiles. Double-click a minimized title to restore the launcher's chosen layout.

The left panel shows **Run Status** across related Git worktrees, using shared
runner discovery and the pipeline dashboard. Each concurrent launcher gets its
own section, including launchers in the same worktree. Sections
share the panel in equal sections initially. A `run-tests` child that publishes
its controlling launcher is shown through that launcher's progress, even across
worktrees. Independent runners keep their own sections. Older child runs without
that publication remain visible until their next normal start.
In Vertical mode, the horizontal dividers can be
dragged to resize adjacent sections, or focused
and adjusted with Up/Down. A vertical divider separates each actions menu from
**Minimize** and **Maximize** / **Restore**, using the same controls as viewer tiles.
Minimize leaves only the title row with its view dropdown and buttons, hiding content.
Its button becomes **Restore tile layout** while minimized and restores the same
chosen layout as the maximized tile's Restore button.
Maximize expands the selected launcher and minimizes every other launcher.
Restore expands all launchers into their chosen layout, retaining Vertical mode's
resized proportions and selected tabs. Inactive launchers (finished, failed or stopped) minimize by default,
including when a running launcher exits. A new active run expands by default.
Manual minimization and resizing survive live refreshes until the next
run or activity transition. Maximization survives those transitions until a tile
control or divider changes the layout. Sizes last while Watch is open.
Launcher and viewer tiles share their rounded borders, title-bar styling and
selection highlight. Click anywhere in a tile to select it. Clicking its title
bar keeps it selected and does not change its size, including while minimized.
Double-click the title bar to restore a minimized tile to the normal layout,
maximize a normal tile, or restore a maximized tile to the normal layout.
The selected tile has a highlighted border and tinted background. Selecting
another tile on either side clears the previous selection. Title-bar links and
buttons select their tile without unselecting it, while performing their usual action.
Dividers remain active beside collapsed sections; resizing expands them and
restores their selected tabs.
When a launcher exits for any reason, its
section and all four tabs retain their contents until a newer run of the same
launcher on the same branch replaces it. Only the latest result per launcher
and branch is shown, regardless of VM selection; concurrent active runs remain
visible. Reconnecting applies the same selection to existing run files.
Session input is disabled once its owner
exits. Retention uses existing run files and reader memory; explicitly closing a
finished tile saves only its dismissal marker.
Launcher and viewer titles use the same bold text and single-line content:
local/remote icon, host (`local` or the SSH host), `[branch]`, and launcher or VM name.
Launcher titles occupy the first row with one three-line menu button at its right.
The menu opens a dropdown with **Copy tab content** first, then **Copy Command**
(terminal icon), followed by the launcher action, **Reload**, **Add 5 Sessions**,
**Kill** and **Close Finished Launcher**.
**Copy Command** copies the full saved command with all parameters and argument
quoting. It is disabled for older runs without saved parameters. Double-clicking
the title does not copy the command.
Click outside the dropdown or press Escape to close it. The launcher action is
**Stop** (solid square) while active, **Undo** while a cancellable stop is pending,
or **Resume** (play) while idle. It is disabled once stopping begins,
while disconnected, or when saved command parameters are unavailable. Clicking
asks for confirmation with **Stop**, **Resume** or **Cancel stop request**, and **Cancel**.
All launcher menu commands run silently in the background on that same host
and checkout, without opening a VS Code terminal. Follow progress in Watch.
Watch uses its shared
`Output.execution_plan` property to identify execution-plan runs: Resume reruns
their saved command with the same parameters. Other launchers, including
`fix-tests`, `run-tests` and `sync-whatsnew`,
receive `--resume`, which restores their saved selection. All launcher commands
include `--branch NAME` for the displayed checkout. Stop and cancel-stop
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
and vertically; **Copy all** copies it, and **Close** dismisses it. **Clear** at
the bottom right empties the recorded errors and hides the error icon while
keeping the dialog open. Additional distinct errors append to the open dialog;
identical failures do not restart flashing until the recorded errors are cleared
or the VS Code session ends. Diagnostics also go
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
Watch captures background action process output without interactive input. Start failures
and nonzero action exits light the error icon, including Python tracebacks and SSH diagnostics.
The diagnostic includes the invocation, checkout, host, exit status and up to the
last 1,048,576 characters of process output, with terminal control sequences
removed; omitted earlier output is explicitly labelled.
Local and SSH actions load NVM's selected default when `codex` is
missing from their inherited PATH, so GUI startup does not hide an NVM-installed
CLI or its Node interpreter. Codex must already be installed and authenticated.
**ONPC: Watch Terminal Diagnostic** reopens the last failed action's captured
diagnostic in the same copyable dialog.

In the same dropdown, **Reload** (circular arrow) asks for confirmation with
**Reload** and **Cancel**, showing the exact command. Confirming sends `--reload`
with the saved parameters, stripping earlier lifecycle flags, on the same host
and checkout. Reload is disabled while stopping, disconnected, or when the source
adapter has not published its reload command.
While an active launcher's reload request awaits a safe boundary, its title
shows `(Reload Requested)` in the same orange as **Stop Requested**. The suffix
clears when the controller accepts the reload or the launcher exits; a stop
request takes precedence.
After Reload, **Add 5 Sessions** invokes the displayed launcher's saved command
with `--add-session 5`, after confirmation. It increases the current task/case
allowance and both **Session x/y** labels refresh from the launcher's computed
value. Repeated additions accumulate. It is disabled when no active allowance is
published, while stopping or disconnected. A task change during confirmation
refuses the action. Older running controllers need `--reload` before they can
publish an adjustable allowance. See the shared
[allowance contract](../../docs/Execution-Plans.md#common-launcher-interface).

After Add 5 Sessions, **Kill** (red outlined octagon with an X) asks for
confirmation with **Kill** and **Cancel**. It requests immediate cooperative
cancellation of the displayed controller, current session and owned tests,
including a running VM test. Normal cleanup still runs, including baseline
restoration for VM-backed workflows under their existing ownership guards.
Kill is disabled for inactive or disconnected runs, while stopping, or when
the source adapter does not advertise support. The run identity is checked
again after confirmation and on the originating host before cancellation.
At the bottom of the menu, **Close Finished Launcher** uses a plain, theme-colored
close X below a separator, distinct from Kill's red octagon. It is enabled only
for a connected, inactive launcher with saved output. Confirmation offers
**Close Finished Launcher** and **Cancel**. Confirming clears the saved Watch tile;
a run-specific dismissal on the originating host keeps it closed across reconnects
and VS Code restarts. Launcher checkpoints and test artifacts remain available.
The host rechecks the exact run and holds its idle owner lock while saving the
dismissal; a running or replaced launcher cannot be closed. A new run appears normally.

The **Status**, **Launcher**, **Error** and **Session** views are selected from
a dropdown at the right end of the pinned task summary row below the title.
The dropdown and action buttons fit their contents, leaving the remaining width for the title.
The dropdown, menu and resize controls use equal spacing beside their dividers.
Long titles truncate with an ellipsis before the right-aligned action
buttons. The left panel's minimum width fits the shortened title, dropdown and
action buttons. Hover over a
launcher title to see its saved command with all parameters, including
argument quoting. The title uses normal bold text. Double-clicking changes the
tile size as described above. Older runs without saved parameters show only
the plain title.
Single-click the title to edit its display text without changing the command.
Press Enter or click elsewhere to save; Escape cancels. Clearing the text restores
the default title. Renamed titles show an Undo button at the right end on hover
or keyboard focus; click it to restore the default title.
Names are saved in VS Code's workspace state, survive closing Watch and restarting
VS Code, and remain with finished or failed output. The next run clears the name
and uses its default title again.
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
While `fix-tests` is active, its title shows **Repairing** during repair sessions
and **Verifying** while checking the repair. After verification, it shows
**Committing Fix** in green during commit, push and propagation. A live session
takes precedence over a previously recorded final result. After Git close-out,
the launcher returns to running tests without retaining the repair's verification status.
The Launcher tab reports that transition. Source-admission waits report their
reason and elapsed time every 30 seconds, then report when execution can continue.
Queued failures remain visible in Status, Error and Session after their impact
assessment agent exits. The coordinator publishes small display metadata with
the VM, case, impact decision and reason. While repair waits, the title shows
**Repair Pending** in the same orange as **Repairing**. Both content tabs show
**Status:** followed by a short explanation, such as “Repair pending — waiting
for active tests and VM cleanup.” The Error tab retains the actual failure details.
The Session view retains the assessment transcript and distinguishes an inactive
agent from a queued repair. These observations grant no execution or input authority.
Failed launcher titles appear in red.
**Status** shows the current run status, **Launcher** shows
the launcher terminal output, **Error** shows the shared launcher's **Last Error**
and **Status** fields with the same colors and elapsed ages, and **Session** opens
the session transcript and chat. The Status tab places its bold **Status:** label
on a separate row immediately below the run summary. The title and both content
status fields use one shared color palette; titles stay brief, while the content
fields share the same explanatory text and formatting.
The Launcher tab streams running command output, including baseline preparation
phases before VM startup; it does not wait for the command to finish.
Branch names discovered from local and remote Git refs and commit hashes appear
in green, independently of the message wording or environment configuration.
Each launcher's tab selection is independent: opening **Session** in another
worktree leaves existing Session panels open and refreshing. Chat stays routed
to the session displayed in its own panel.
For `fix-tests`, the link shows **Session 1/5**, **Session 2/5**, and so on for
successive agent sessions repairing the same case. The number remains visible
between sessions and during verification, with strikethrough while the session is
inactive and its chatbox is disabled. Once the repair is accepted and closed,
the link returns to struck-through **Session**; the next case starts at **Session 1/5**.
The denominator is the computed allowance, including explicit extra sessions.
The Session selector and the Status pane's draggable divider use the same label
formatter. Ordinary plans display usage for the current implementation or
coordinator repair allowance, keeping those separate budgets distinct.
While an agent repairs an integration check, its **Status** row ends with
` | Session x: <duration>`, using that session's elapsed time and the shared
`01:25` / `3h 45m` duration format. The suffix disappears when the session finishes.
The preceding check duration includes the whole case, including repair sessions
and retries; the session duration measures only the current agent session.
For `fix-tests`, Last Error includes the failing check, the runner's error text
(or a readable summary of a structured failure, falling back to a bounded text
output tail), and its output-log path. It clears when the failure is resolved and
the launcher resumes the remaining tests, after any required Git close-out.
Full JSON results remain in that log. Reload launcher
changes with `tools/fix-tests --reload`; `./setup.sh --watch` updates the extension.
The links remain available in every view, including while idle. **Copy tab content** in the
three-line menu copies the current tab's body as plain text to the clipboard;
in **Session**, it copies the displayed transcript.
For every execution-plan launcher, including `write-e2e`, every view
starts with **Total Tasks: completed/unfinished/total | duration**
on one pinned line, using the shared launcher counters and colors. Narrow panels
scroll the summary horizontally instead of wrapping it. A divider
spans the panel above the completed task recaps and current task/session rows.
The **Total Tasks:** label is bold. When the whole plan
finishes, the same line adds **Ended:** with the local completion time (`HH:MM`),
and the launcher title, including `(finished)`, turns green.
An accepted safe-boundary stop shows **Stopped** in red, even when cleanup
succeeds with exit code zero. **Finished** is reserved for a completed plan;
an incomplete plan never receives that label.
The summary belongs to the tile and stays pinned above all tab bodies.
In Status, the task/session history scrolls, following the bottom until you scroll up.
Below it, a resizable panel embeds the entire Session or Launcher tab body. Its bold label
sits within the divider line and matches **Session N** while a session is
active; otherwise it shows **Launcher**.
Session includes its transcript, chat input, model and Simplified switch, sharing
state with its own tab. Launcher includes its complete terminal output.
The output panel starts maximized, completely hiding task history. Drag the labeled
divider to resize the box, or focus it and use Up/Down (Home/End for the limits).
Minimizing completely hides the output and leaves the divider below task history;
maximizing leaves only the divider and output below the pinned summary.
The six-dot grip marks the draggable divider. Its right-hand chevron toggles
between the minimum and maximum output heights. Intermediate heights show both panes.
Output follows the same scrolling behavior in Status and its own tab.
During task close-out, the title shows `[branch] launcher (Closing Task)`, with
`Closing Task` in green. This includes processing the finished task response
while **Session** is struck through, validation, and the commit skill's commit,
push and propagation, including repository synchronization waits while an
accepted completion is retained for Git reconciliation.
Checkout synchronization and its repository lock waits show `Closing Task`
when a task completion is still pending or the completed task has not yet been
replaced by the next task, including after its green recap was published.
Boundary synchronization without a completed or pending task adds no title status.
The suffix disappears when **Status** shows the task's
green checkmark and task close-out and final synchronization have finished.
Stop and reload notices take priority.
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
model/effort footer, including the Simplified toggle. The footer uses the
recorded session model and effort. Watch actions
use the destination launcher's shared agent environment preparation, so observing
or stopping a run does not require a coding CLI. The transcript includes
sent prompts and agent messages. Agent prose streams while it is being written;
the completed message replaces its provisional text, including any corrections.
Only completed messages enter the saved transcript. Launcher status metadata and
structured workflow results wait for completion before being interpreted.
Structured results appear as labeled text, including the impact assessment's
reason, scope, evidence and classification. The original JSON remains available
to the launcher for validation and scheduling.
Agent session changes within a launcher run preserve terminal history; chat
always targets the current session. Oldest rows expire under the bounded
scrollback limits instead of clearing the conversation at each session change.
Command and tool result bodies are hidden in
both modes; activity names remain visible and saved transcripts retain results.
Simplified mode pins the latest command activity to one clipped line above the
chatbox, with a divider separating it from the conversation. Each new activity
replaces the previous one; earlier activities stay out of the conversation.
Hidden activities do not consume the Simplified conversation's scrollback budget.
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
the selected recording on demand and play it in a VS Code video tab. Playback
uses the original recording unchanged: new recordings use VP8 WebM, YUV420p,
5 fps and no audio on both desktop and headless hosts.
Transfer uses the existing client-to-server SSH connection
and does not require reverse SSH. Playback failures appear in Watch error details,
including the decoder's error. Older VP9 recordings remain unchanged and may
require the source host's desktop player; rerunning the case replaces them with
the current format.
Inline remote videos are limited to 64 MiB; larger recordings remain available on the
source host. Remote error logs open as text in the editor (up to 2 MiB).
Artifact transfer does not create local test-output copies.
Repair case totals show green completed, red failed and total counts. The failed
count is underlined; click it to open the cumulative `errors.md` in the editor.

The right panel contains the shared VM Viewer grid across checkouts, UI worker and VM tiles,
VM progress, filtered command output and host resource usage. Screens are view
only. Clicking a viewer title selects the tile. Tiles group by worktree in the left
panel's current order, following changes on each refresh. Worktrees without a displayed run follow those
shown on the left. Start tests through the usual launchers.
The Reconnect button restarts this tab's source connections.

The fixed **Run Time** tab follows **VM Viewer**. It loads logged VM case durations only
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
when maximizing or restoring tiles until Watch is reopened. Long blue operation messages
truncate before the toggle, whose space stays reserved.

Immediately before **SSH**, **Memory: x.x GB** shows the VM process's resident
host RAM (RSS), including QEMU overhead, in decimal gigabytes. Its mini graph
reuses the footer chart renderer and shows the last minute, sampled once per
second through the existing watch feed without guest commands. The vertical
scale covers configured guest RAM and any higher observed RSS. Missing or stale
readings show **—**; gaps remain disconnected. History stays in memory and resets
when the VM instance changes or Watch reconnects. Existing VM collectors need
their next normal restart to publish this additional reading.

The camera icon near the right end of each tile's title bar saves that tile's UI frame
at its original resolution to the XDG Pictures directory's Screenshots folder,
without a Save dialog. Names follow `Screenshot From 2026-10-30 10-04-15.png`
in local time; repeated captures in one second add a numeric suffix.
A desktop notification appears for five seconds (subject to desktop settings).
Click it to open the default file manager with the screenshot selected, using
the standard desktop notification and FileManager1 APIs. This requires the
system Python's PyGObject/Gio bindings. With Remote SSH, saving and notifications
occur on the extension host's desktop.
It excludes the viewer's headings, command text and footers. Long titles truncate before
the buttons, keeping them visible. The camera is disabled without a frame.

Immediately after the camera, **Minimize tile** (a short line) moves the viewer
to a title-only bar at the bottom of the right canvas. Single-click selects it;
double-click restores the normal viewer layout. When those titles cannot fit,
**>>** opens a flyout of all tile titles with the same click behavior.

After Minimize, **Maximize tile** fills the remaining right tab body with that
viewer and minimizes the other tiles into the footer. The button becomes
**Restore tile layout**, which restores all tiles in the last selected layout.
A maximized tile can also be minimized, leaving all titles in the footer.
A maximized viewer stays open while waiting for its next run. The tab row contains
only **VM Viewer** and **Run Time**; clicking **VM Viewer** also restores the grid.

Three icon buttons at the right end of the viewer tab row select the tile layout:
**Auto** (the default grid), **Vertical** (one column), or **Horizontal** (one row).
The tab remembers the selection. Maximizing or minimizing a tile unselects all
three buttons. Choosing any layout restores all tiles using that layout.
Overflowing tiles scroll in the chosen direction; the layout buttons stay pinned.

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
server icon and hostname before its CPU, VM/Host RAM and Disk readings and small
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

**VM/Host RAM** shows VM RAM / total host RAM usage in decimal GB, rounded to
one decimal place (for example, **12.3/24.5 GB**). The purple line shows VM RAM;
the teal line shows total host usage, both as percentages of total host RAM on
the same graph. Host usage is `MemTotal` minus `MemAvailable`, including all
host processes and VM usage while excluding available reclaimable memory.
Either unavailable reading shows **—** independently.

VM RAM sums the current working set (`memory.current` minus
`memory.stat`'s `inactive_file`, floored at zero per scope) for all system
libvirt QEMU VM scopes on that host, including VMs outside the configured test
inventory. It includes resident guest RAM (including shared-memory backing),
QEMU overhead, helper processes, charged kernel memory and active file cache,
without counting descendant groups twice. Reclaimable inactive disk cache is
excluded. This is current occupancy, not a reservation: for parallel capacity,
budget full configured guest RAM plus overhead per VM and leave host headroom.
Swap is excluded from both readings. With no
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

Run `./setup.sh --connect-server` on the client to verify existing noninteractive
SSH access to all configured SSH hosts and install Watch. Then open your local
checkout in VS Code and use **ONPC: Watch** to observe and manage local and remote
launchers together. No separate workspace is needed. Machine-to-machine SSH
must already be configured; setup uses each `host.name` as an OpenSSH alias
without changing SSH settings or keys. The command needs no terminal or prompts.
See the [setup contract](../../docs/Approval-Tools.md#one-time-setup) for
prerequisites and server readiness checks.

With no configuration, Watch uses this checkout's local adapter and the SSH hosts
with branches in `config/environment.json`, including hosts disabled for VM
scheduling. Each remote host starts from its first configured branch checkout
and discovers related registered Git worktrees. SSH access must already be set
up; Watch never prompts for credentials. Independent clones require explicit
sources. Set
`onpc.watch.sources` in VS Code user or workspace settings to replace that default
or combine sources. Source IDs must be unique and stable; labels identify hosts
in viewer tabs; tile titles show the SSH host or `local` before the branch name.
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
