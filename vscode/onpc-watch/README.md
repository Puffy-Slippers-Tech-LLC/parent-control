# ONPC Watch

Open run status and live UI/VM viewers in a VS Code editor tab.

Run `./setup.sh --watch` as your desktop user to install or update this extension.
Reload VS Code after updating it. Open an ONPC checkout, press **Ctrl+Shift+P**,
and select **ONPC: Watch** (`onpc.watch`). Repeating the command reveals the
existing tab. Multiple workspace roots offer a checkout picker.

The tab starts with a 30:70 left/right split. Drag the divider to resize it;
the tab remembers its ratio. Focus the divider and use the arrow keys to resize
with the keyboard, or double-click it to restore 30:70.

The left panel shows **Run Status** across related Git worktrees, using shared
runner discovery and the pipeline dashboard. Active worktrees
share the panel in equal sections; when idle, it retains the last displayed run.
It contains status only, without Run Status/Outputs/Session tabs.
Repair case totals show green completed, red failed and total counts. The failed
count is underlined; click it to open the cumulative `errors.md` in the editor.

The right panel contains the shared All grid across checkouts, UI worker and VM tabs,
VM progress, filtered command output and host resource usage. Screens are view
only. Start tests through the usual launchers. Select an idle VM tab to wait for
its next run. The Reconnect button restarts only this tab's reader.

The footer shows CPU, Memory and Disk percentages beside small filled history
graphs. They reuse the once-per-second samples, show the last minute on a fixed
0–100% scale, and retain history only in memory. Closing and reopening Watch or
reconnecting its reader starts fresh; pauses leave gaps rather than joined curves.

**Disk** reports the busiest physical disk's elapsed I/O busy time, matching
`iostat %util`. It avoids adding overlapping request durations. This measures
activity rather than maximum throughput; 100% busy does not necessarily mean an
NVMe drive is saturated.

The extension runs the selected trusted checkout's `tools/watch_webview.py` with
system Python. That adapter uses shared checkout discovery,
authenticated feeds and scope selection. Frames travel over private stdio,
with one snapshot in flight and no listener port. Hidden tabs stop requesting
snapshots; closing a tab stops its reader. Nothing is installed in the product
or in a guest VM. No npm packages or compilation step are needed.

This is a Linux workspace extension. With Remote SSH, install it and open the
checkout on the development host where the watch publications live. VS Code
Workspace Trust is required.
