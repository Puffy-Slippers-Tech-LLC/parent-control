'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const { fileURLToPath } = require('node:url');
const { stripVTControlCharacters } = require('node:util');
const { Bridge, configuration, resourceConfiguration } = require('./bridge');
const { WatchErrors, errorDialog } = require('./errors');

const watchSettingsPath = path.join(os.homedir(), '.onpc-config', 'watch.json');

function readWatchSettings() {
    try {
        const value = JSON.parse(fs.readFileSync(watchSettingsPath, 'utf8'));
        if (!value || Array.isArray(value) || typeof value !== 'object' ||
                typeof value.view !== 'boolean' || typeof value.ssh !== 'boolean') {
            throw new Error('Invalid Watch settings.');
        }
        return value;
    } catch (error) {
        if (error.code === 'ENOENT') return { view: false, ssh: false };
        throw error;
    }
}

function saveWatchSettings(settings) {
    const directory = path.dirname(watchSettingsPath);
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    const temporary = path.join(directory, `.watch-${randomBytes(16).toString('hex')}.json`);
    try {
        fs.writeFileSync(temporary, JSON.stringify(settings) + '\n', { flag: 'wx', mode: 0o600 });
        fs.renameSync(temporary, watchSettingsPath);
    } finally {
        fs.rmSync(temporary, { force: true });
    }
}

function actionBackground({ shellPath, shellArgs, cwd, invocation, failed, completed = () => {} }) {
    const child = spawn(shellPath, shellArgs, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
    const limit = 1024 * 1024;
    let transcript = '', omitted = false, finished = false;
    for (const stream of [child.stdout, child.stderr]) {
        stream.setEncoding('utf8');
        stream.on('data', data => {
            transcript += data;
            if (transcript.length > limit) {
                transcript = transcript.slice(-limit);
                omitted = true;
            }
        });
    }
    const finish = (code, signal, error) => {
        if (finished) return;
        finished = true;
        if (error || code !== 0) {
            failed(`${invocation}\n\nExit code: ${code ?? 'unavailable'}\nSignal: ${signal || 'none'}\n` +
                (error ? `\n${error.stack || error}\n` : '') +
                `\nProcess output${omitted ? ' (last 1,048,576 characters; earlier output omitted)' : ''}:\n${stripVTControlCharacters(transcript)}`);
        }
        completed(!error && code === 0);
    };
    child.on('error', error => finish(null, null, error));
    child.on('close', (code, signal) => finish(code, signal));
}

function checkout(folder) {
    if (folder.uri.scheme !== 'file') return undefined;
    let root = fs.realpathSync(folder.uri.fsPath);
    for (;;) {
        if (fs.existsSync(path.join(root, 'tools', 'watch_webview.py')) &&
            fs.existsSync(path.join(root, '.git'))) return root;
        const parent = path.dirname(root);
        if (parent === root) return undefined;
        root = parent;
    }
}

function html(webview, context) {
    const media = vscode.Uri.joinPath(context.extensionUri, 'media');
    const script = webview.asWebviewUri(vscode.Uri.joinPath(media, 'watch.js'));
    const style = webview.asWebviewUri(vscode.Uri.joinPath(media, 'watch.css'));
    const nonce = randomBytes(16).toString('hex');
    return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src ${webview.cspSource} 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
        <link rel="stylesheet" href="${style}"><title>ONPC Watch</title></head>
        <body><div id="watch">
        <aside id="launchers" aria-label="Run status across worktrees">
        <div class="pane-toolbar"><strong>Launchers</strong>
        <button id="launcher-queue-button" type="button" popovertarget="launcher-queue"
            aria-expanded="false">Queue</button><div id="launcher-layout"></div></div>
        <section id="launcher-queue" popover aria-labelledby="launcher-queue-title">
        <header><strong id="launcher-queue-title">Launcher Queue</strong>
        <button type="button" popovertarget="launcher-queue" popovertargetaction="hide"
            aria-label="Close launcher queue">×</button></header>
        <div id="launcher-queue-list"></div><p id="launcher-queue-status" role="status" hidden></p>
        </section>
        <div id="runs" class="tile-grid"><p class="empty" role="status">Waiting for tests…</p></div></aside>
        <div id="divider" role="separator" aria-label="Resize run status and viewers"
            aria-orientation="vertical" aria-valuemin="0" aria-valuemax="90" aria-valuenow="30" tabindex="0"></div>
        <section id="viewer" aria-label="UI and VM viewers"><div id="viewer-header" class="pane-toolbar">
        <nav id="viewers" aria-label="Viewers"></nav>
        <div id="watch-controls" role="group" aria-label="Watch collection">
        <label>View <button id="watch-view" class="session-toggle" type="button" role="switch" aria-label="View for all running launchers" aria-checked="false"></button></label>
        <label>SSH <button id="watch-ssh" class="session-toggle" type="button" role="switch" aria-label="SSH for all running launchers" aria-checked="false"></button></label>
        </div>
        <div id="tile-layout"></div></div>
        <main id="grid" class="tile-grid"><p class="empty" role="status">Connecting to watch…</p></main>
        </section></div>
        <footer><button id="watch-error-indicator" type="button" hidden title="Show Watch error details" aria-label="Show Watch error details">
        <svg viewBox="0 0 20 20" aria-hidden="true">
        <defs><linearGradient id="watch-alert-red" x2="0" y2="1"><stop stop-color="#ff3025"/><stop offset="1" stop-color="#df0905"/></linearGradient></defs>
        <circle cx="10" cy="10" r="9" fill="url(#watch-alert-red)"/>
        <path fill="#fff" d="M8.7 10.8 8.1 5.9C8 4.9 8.7 4.5 10 4.5s2 .4 1.9 1.4l-.6 4.9c-.1.7-2.5.7-2.6 0Z"/>
        <circle cx="10" cy="14" r="1.3" fill="#fff"/></svg></button>
        <button id="restart" title="Reconnect to the watch backend">Reconnect</button>
        <span id="servers" aria-label="Server connection status"></span>
        <span id="resources"></span></footer>
        ${errorDialog(nonce)}
        <script nonce="${nonce}" src="${script}"></script></body></html>`;
}

function activate(context) {
    const panels = new Map();
    const output = vscode.window.createOutputChannel('ONPC Watch');
    const errors = new WatchErrors(context, output);
    let lastTerminalDiagnostic;
    context.subscriptions.push(output);
    context.subscriptions.push(vscode.commands.registerCommand('onpc.watchTerminalDiagnostic', () => {
        errors.report('Watch terminal diagnostic', lastTerminalDiagnostic || 'No failed Watch terminal has been recorded in this VS Code session.');
        errors.show();
    }));
    function updateButton() {
        const available = vscode.workspace.isTrusted &&
            (vscode.workspace.workspaceFolders || []).some(folder => {
                try { return Boolean(checkout(folder)); }
                catch { return false; } // A removed or inaccessible folder is not a checkout.
            });
        void vscode.commands.executeCommand('setContext', 'onpc.watchAvailable', available);
    }
    context.subscriptions.push(
        vscode.workspace.onDidChangeWorkspaceFolders(updateButton),
        vscode.workspace.onDidGrantWorkspaceTrust(updateButton));
    updateButton();
    const openWatch = async () => {
        if (!vscode.workspace.isTrusted) {
            errors.report('Cannot open Watch', 'Trust this workspace before opening ONPC Watch.');
            return;
        }
        let roots;
        try {
            roots = [...new Set((vscode.workspace.workspaceFolders || []).map(checkout).filter(Boolean))];
        } catch (error) {
            errors.report('Cannot open Watch', error);
            return;
        }
        const root = roots.length === 1 ? roots[0] : roots.length &&
            await vscode.window.showQuickPick(roots, { placeHolder: 'Choose an ONPC checkout to watch' });
        if (!root) {
            if (!roots.length) errors.report('Cannot open Watch', 'Open an ONPC repository folder to use ONPC Watch.');
            return;
        }
        if (panels.has(root)) {
            panels.get(root).reveal();
            return;
        }
        const watchSettings = readWatchSettings();
        const panel = vscode.window.createWebviewPanel('onpc.watch', 'ONPC Watch',
            vscode.ViewColumn.Active, {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')]
            });
        panels.set(root, panel);
        errors.attach(panel);
        let bridge, timer, ready = false, rendering = false, renderedRevision = -1;
        let renderNumber = 0;
        let selection = { scope: 'all', selected: 'all' }, reset = true, disposed = false;
        let sessionRoots = new Set();
        let sessions = new Map();
        let runRoots = new Set();
        let displayedRuns = new Map();
        let changingWatch = false;
        let syncedWatch = '';
        let watchSyncError = '';
        function reportWatchSyncError(error) {
            const message = error.message || String(error);
            if (message !== watchSyncError) errors.report('Cannot apply saved Watch settings', message);
            watchSyncError = message;
        }
        function publishWatchSettings() {
            if (!disposed) void panel.webview.postMessage({ type: 'watchSettings', ...watchSettings, pending: changingWatch });
            reset = true;
            void publish();
        }
        const titleStateKey = `watch.launcherTitles:${root}`;
        const launcherTitles = new Map(context.workspaceState.get(titleStateKey, []));
        const saveTitles = () => context.workspaceState.update(titleStateKey, [...launcherTitles])
            .then(undefined, error => errors.report('Cannot save launcher title', error));
        const notifications = new Set();
        function desktopCommand(command, args, label, input) {
            const helper = spawn(command, args,
                { stdio: [input === undefined ? 'ignore' : 'pipe', 'ignore', 'pipe'] });
            notifications.add(helper);
            let stderr = '';
            const report = error => errors.report(label, error);
            helper.stderr.on('data', data => { stderr += data.toString(); });
            helper.on('error', error => report(error.message));
            helper.on('close', code => {
                notifications.delete(helper);
                if (code || stderr) report(stderr || `desktop helper exited (${code})`);
            });
            if (input !== undefined) {
                helper.stdin.on('error', error => report(error));
                helper.stdin.end(input);
            }
        }
        function stop() {
            clearInterval(timer);
            bridge?.close();
            bridge = undefined;
            rendering = false;
        }
        function failure(message) {
            stop();
            errors.report('Watch bridge failed', message);
            if (!disposed) void panel.webview.postMessage({ type: 'error', message });
        }
        function poll() {
            if (!bridge || !ready || !panel.visible) return;
            // Sources advance independently, with the existing render backpressure.
            try {
                bridge.tick({ ...selection, session_roots: [...sessionRoots] });
                void syncWatchSettings().catch(reportWatchSyncError);
                void publish();
            } catch (error) { failure(error.stack || error.message); }
        }
        async function publish() {
            if (!bridge || !ready || !panel.visible || disposed) return;
            if (rendering || (!reset && renderedRevision === bridge.revision)) return;
            try {
                const current = bridge;
                const snapshot = current.snapshot({ ...selection, reset });
                displayedRuns = new Map(snapshot.runs.map(entry => [entry.id, entry.run]));
                let titlesChanged = false;
                for (const entry of snapshot.runs) {
                    const saved = launcherTitles.get(entry.id);
                    if (saved && saved.run !== entry.run) {
                        launcherTitles.delete(entry.id);
                        titlesChanged = true;
                    } else if (saved) entry.custom_title = saved.title;
                }
                if (titlesChanged) void saveTitles();
                selection = { scope: snapshot.scope, selected: snapshot.selected };
                reset = false;
                renderedRevision = current.revision;
                runRoots = new Set(snapshot.runs.map(entry => entry.id));
                sessionRoots = new Set([...sessionRoots].filter(id => runRoots.has(id)));
                sessions = new Map(snapshot.runs.filter(entry => entry.session)
                    .map(entry => [entry.id, entry.session]));
                const id = ++renderNumber;
                rendering = id;
                const delivered = await panel.webview.postMessage({ type: 'snapshot', id, ...snapshot });
                if (!delivered && bridge === current && rendering === id) {
                    current.results.unshift(...snapshot.session_results);
                    rendering = false;
                    reset = true;
                }
            } catch (error) { failure(`Watch bridge: ${error.message}`); }
        }
        function start() {
            stop();
            reset = true;
            syncedWatch = '';
            watchSyncError = '';
            try {
                const values = vscode.workspace.getConfiguration('onpc.watch', vscode.Uri.file(root)).get('sources', []);
                bridge = new Bridge(configuration(values, root), message => output.appendLine(message), publish,
                    resourceConfiguration(root), (title, error) => errors.report(title, error));
            } catch (error) { failure(error.message); return; }
            // Observation need not run at the launcher's recording cadence.
            timer = setInterval(poll, 500);
            poll();
        }
        const messages = panel.webview.onDidReceiveMessage(message => {
            try {
            if (message?.type === 'ready') {
                sessionRoots.clear();
                ready = true;
                rendering = false;
                reset = true;
                publishWatchSettings();
                poll();
            } else if (message?.type === 'rendered' && message.id === rendering) {
                rendering = false;
                void publish();
            } else if (message?.type === 'select' &&
                       typeof message.scope === 'string' && message.scope.length <= 32768 &&
                       typeof message.selected === 'string' && message.selected.length <= 32768) {
                selection = { scope: message.scope, selected: message.selected };
                reset = true;
                poll();
            } else if (message?.type === 'restart') {
                void panel.webview.postMessage({ type: 'error', message: 'Reconnecting. Unacknowledged input will not be resent; review the session before sending again.' });
                start();
            } else if (message?.type === 'serverError' && typeof message.server === 'string') {
                const details = bridge?.serverErrors?.get(message.server);
                if (details) {
                    errors.report('Watch connection failed', details.join('\n\n'));
                    errors.show(panel);
                }
            } else if (message?.type === 'launcherAction' && runRoots.has(message.root) &&
                       typeof message.run === 'string' && ['stop', 'cancel-stop', 'resume', 'reload', 'kill', 'add-session', 'close'].includes(message.kind)) {
                void launchControl(message);
            } else if (message?.type === 'cancelTicket' && typeof message.token === 'string' &&
                       message.token.length <= 8192 && bridge) {
                void cancelTicket(message.token);
            } else if (message?.type === 'watchToggle' && ['view', 'ssh'].includes(message.kind) &&
                       typeof message.enabled === 'boolean') {
                void toggleWatch(message.kind, message.enabled);
            } else if (message?.type === 'renameLauncher' && runRoots.has(message.root) &&
                       displayedRuns.get(message.root) === message.run &&
                       typeof message.title === 'string' && message.title.length <= 512) {
                const title = message.title.trim();
                if (title) launcherTitles.set(message.root, { run: message.run, title });
                else launcherTitles.delete(message.root);
                void saveTitles();
                reset = true;
                void publish();
            } else if (message?.type === 'screenshot' && typeof message.png === 'string' &&
                       message.png.length <= 45 * 1024 * 1024 &&
                       /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(message.png)) {
                desktopCommand('/usr/bin/python3', ['-B',
                    path.join(context.extensionUri.fsPath, 'screenshot.py')], 'Screenshot',
                    Buffer.from(message.png.slice('data:image/png;base64,'.length), 'base64'));
            } else if (message?.type === 'screenshotError' && typeof message.error === 'string') {
                errors.report('Cannot take screenshot', message.error);
            } else if (message?.type === 'watchError' && typeof message.error === 'string') {
                // A failed render may have consumed only part of an update.
                // Rebuild from full bridge state before sending more deltas.
                reset = true;
                errors.report('Watch viewer failed', message.error);
            } else if (message?.type === 'copy' && runRoots.has(message.root) &&
                       typeof message.text === 'string') {
                void vscode.env.clipboard.writeText(message.text).then(() => {
                    if (message.command === true) {
                        vscode.window.setStatusBarMessage('Launcher command copied', 1500);
                        void panel.webview.postMessage({ type: 'commandCopied', root: message.root });
                    }
                },
                    error => errors.report('Cannot copy tab content', error));
            } else if (message?.type === 'copyRunTimes' && selection.selected === 'run-time' &&
                       typeof message.text === 'string') {
                void vscode.env.clipboard.writeText(message.text).then(() => {
                    vscode.window.setStatusBarMessage('Run time rows copied as Markdown', 1500);
                }, error => errors.report('Cannot copy run time rows', error));
            } else if (message?.type === 'sessionView' &&
                       Array.isArray(message.roots) && message.roots.length <= runRoots.size &&
                       message.roots.every(id => runRoots.has(id))) {
                sessionRoots = new Set(message.roots);
                poll();
            } else if (message?.type === 'sessionAction' &&
                       typeof message.id === 'string' && message.id.length > 0 && message.id.length <= 128) {
                const oversized = typeof message.text === 'string' && Buffer.byteLength(message.text) > 65536;
                if (bridge &&
                       typeof message.question === 'string' && message.question.length <= 4096 &&
                       typeof message.text === 'string' && !oversized &&
                       ['send', 'simplified', 'extend'].includes(message.kind) &&
                       typeof message.session === 'string' &&
                       sessions.get(message.root) === message.session &&
                       (sessionRoots.has(message.root) || message.kind === 'extend')) {
                    bridge.action({ root: message.root, session: message.session, question: message.question,
                        kind: message.kind, text: message.text, id: message.id });
                } else if (bridge) {
                    bridge.results.push({ id: message.id, ok: false,
                        error: oversized ? 'Session input exceeds 64 KiB.' :
                            'Session changed; review the current session before sending.' });
                    bridge.revision++;
                }
                poll();
            } else if (message?.type === 'fileSearch' && sessions.has(message.root) &&
                       sessions.get(message.root) === message.session && sessionRoots.has(message.root) &&
                       typeof message.id === 'string' && message.id.length > 0 && message.id.length <= 128 &&
                       typeof message.query === 'string' && message.query.length <= 512 &&
                       !/[\u0000-\u001f\u007f\ud800-\udfff]/u.test(message.query)) {
                bridge?.searchFiles(message);
                poll();
            } else if (message?.type === 'openRunFile' && typeof message.uri === 'string') {
                void openArtifact(message.uri);
            } else if (message?.type === 'deleteRunTimes' && Array.isArray(message.tokens) &&
                       message.tokens.length > 0 && message.tokens.length <= 4096 &&
                       message.tokens.every(token => typeof token === 'string' && bridge?.timings.has(token)) &&
                       Number.isInteger(message.rows) && message.rows > 0 && message.rows <= message.tokens.length) {
                void deleteRunTimes(message);
            }
            } catch (error) { errors.report('Cannot handle Watch action', error); }
        });

        async function cancelTicket(token) {
            const current = bridge;
            let error = '';
            try {
                await current.cancelTicket(token);
            } catch (failure) {
                error = failure.message;
            }
            await panel.webview.postMessage({ type: 'queueRemoval', token, error });
            poll();
        }
        let deletingRunTimes = false;
        let confirmingLauncher = false;
        async function launchControl(message) {
            if (confirmingLauncher) return;
            confirmingLauncher = true;
            const current = bridge;
            try {
                let command = await current.launcherCommand(message.root, message.run, message.kind);
                const allowanceKey = command.allowance_key;
                const action = { stop: 'Stop', resume: 'Resume', reload: 'Reload', kill: 'Kill', close: 'Close Finished Launcher', 'cancel-stop': 'Cancel stop request', 'add-session': 'Add 5 Sessions' }[message.kind];
                const commandText = message.kind === 'close' ? 'Clear this saved launcher tile. It will stay closed after reconnecting or restarting VS Code. Launcher checkpoints and test artifacts are preserved.' :
                    message.kind === 'kill' ? `Cancel run ${command.run} immediately; allow normal cleanup.` :
                    [ `tools/${command.launcher}`, ...command.argv ].map(value =>
                    /^[\w@%+=:,./-]+$/.test(value) ? value : "'" + value.replace(/'/g, "'\\''") + "'").join(' ');
                const answer = await vscode.window.showWarningMessage(
                    `${action} for ${command.launcher} on ${command.source.label}?`,
                    { modal: true, detail: `Checkout: ${command.root}\nCommand: ${commandText}` }, action);
                if (answer !== action) return;
                if (disposed || current !== bridge) return;
                command = await current.launcherCommand(message.root, message.run, message.kind);
                if (message.kind === 'add-session' && allowanceKey !== command.allowance_key) {
                    throw new Error('Session allowance changed; refresh before trying again.');
                }
                launcherBackground(command, message.kind, action, commandText, diagnostic => {
                    lastTerminalDiagnostic = diagnostic;
                    errors.report(`Cannot ${message.kind} launcher`, diagnostic);
                });
            } catch (error) {
                errors.report(`Cannot ${message.kind} launcher`, error);
            } finally {
                confirmingLauncher = false;
            }
        }

        function launcherBackground(command, kind, action, commandText, failed, completed) {
            // Recheck the publication when the action actually starts, and
            // pin dispatch to this checkout rather than a launcher default branch.
            const bootstrap = `import json, os, subprocess, sys
from pathlib import Path
c = json.loads(sys.argv[1])
root, run = Path(c['root']), Path(c['run'])
sys.path.insert(0, str(root / 'tools'))
from watch_output import read_json
if c['kind'] == 'watch-settings':
    import fcntl
    import watch_control
    from detached_launcher import lock
    from watch_checkouts import checkout
    from watch_output import active_launchers, JsonReader
    roots = [checkout(path) for path in c['checkouts']]
    root = next((root for root in roots if (run, c['launcher']) in
                 active_launchers(root, JsonReader())), None)
    if root is None:
        sys.exit('Watch launcher changed or stopped; refresh before trying again.')
    with lock(run.parent / 'gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if (run, c['launcher']) not in active_launchers(root, JsonReader()):
            sys.exit('Watch launcher changed or stopped; refresh before trying again.')
        watch_control.initialize(run, c['settings'])
    print('Watch runtime settings saved.')
    sys.exit(0)
if read_json(run.parent / 'current.json')['run'] != run.name:
    sys.exit('Launcher changed; refresh before trying again.')
if c['kind'] == 'close':
    from watch_output import close_finished_run
    close_finished_run(root, run)
    print('Finished launcher closed.')
    sys.exit(0)
if c['kind'] == 'kill':
    from watch_output import cancel_run
    cancel_run(root, run)
    print('Kill requested; waiting for owned shutdown and normal cleanup in Watch.')
    sys.exit(0)
branch = subprocess.check_output(['git', '-C', str(root), 'symbolic-ref', '--quiet', '--short', 'HEAD'], text=True).strip()
os.chdir(root)
if '--cancel-stop' in c['argv']:
    os.environ['ONPC_CANCEL_STOP_RUN'] = str(run)
if '--add-session' in c['argv']:
    os.environ['ONPC_ADD_SESSION_RUN'] = str(run)
    os.environ['ONPC_ADD_SESSION_KEY'] = c['allowance_key']
os.environ['ONPC_LAUNCHER_DESTINATION'] = json.dumps(dict(root=str(root), branch=branch, launcher=c['launcher'], pid=os.getpid()))
os.execv('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(root / 'tools' / c['launcher']), *c['argv']])
`;
                const argv = ['/usr/bin/python3', '-IBu', '-c', bootstrap,
                    JSON.stringify({ root: command.root, run: command.run, launcher: command.launcher,
                        argv: command.argv, kind, allowance_key: command.allowance_key,
                        checkouts: command.checkouts, settings: command.settings })];
                const remote = command.source.transport === 'ssh';
                const quote = value => "'" + value.replace(/'/g, "'\\''") + "'";
                // The destination launcher verifies its checkout and uses the
                // shared adapter environment/readiness route at agent admission.
                // Observation and stop actions need no coding CLI or NVM.
                const shellPath = remote ? 'ssh' : argv[0];
                const shellArgs = remote ? ['-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                    '-o', 'ConnectTimeout=5', '--', command.source.host, argv.map(quote).join(' ')] : argv.slice(1);
                actionBackground({
                    shellPath, shellArgs,
                    ...(remote ? {} : { cwd: command.root }),
                    invocation: `Action: ${action}\nHost: ${command.source.label}\nCheckout: ${command.root}\nCommand: ${commandText}\n\nProcess invocation:\n${[shellPath, ...shellArgs].map(quote).join(' ')}`,
                    failed, completed
                });
        }

        async function applyWatchCommands(commands) {
            const failures = [];
            const results = await Promise.all(commands.map(command => new Promise(resolve => {
                try {
                    launcherBackground(command, command.kind, 'Watch collection',
                        `Save Watch runtime settings: ${JSON.stringify(command.settings)}`,
                        diagnostic => { lastTerminalDiagnostic = diagnostic; failures.push(diagnostic); }, resolve);
                } catch (error) {
                    failures.push(error.stack || error.message);
                    resolve(false);
                }
            })));
            if (results.some(ok => !ok)) {
                throw new Error('Watch settings could not be changed for every launcher. Some launchers may have accepted the change.\n\n' + failures.join('\n\n'));
            }
        }

        async function syncWatchSettings() {
            if (changingWatch || !bridge) return;
            const current = bridge;
            const signature = JSON.stringify(current.sources.map(source =>
                [source.config.id, source.status, source.snapshot?.watch_launchers.map(run => run.run)]));
            if (signature === syncedWatch) return;
            syncedWatch = signature;
            changingWatch = true;
            publishWatchSettings();
            try {
                const commands = await current.watchCommands(watchSettings, { changedOnly: true });
                if (disposed || bridge !== current) return;
                await applyWatchCommands(commands);
                watchSyncError = '';
            } catch (error) {
                reportWatchSyncError(error);
            } finally {
                changingWatch = false;
                publishWatchSettings();
            }
        }

        async function toggleWatch(feature, enabled) {
            if (changingWatch || !bridge) {
                publishWatchSettings();
                if (!bridge) errors.report('Cannot change Watch collection', 'Reconnect Watch before changing collection settings.');
                return;
            }
            const current = bridge;
            const previous = watchSettings[feature];
            let saved = false;
            changingWatch = true;
            watchSettings[feature] = enabled;
            publishWatchSettings();
            const label = feature === 'view' ? 'View' : 'SSH';
            try {
                saveWatchSettings(watchSettings);
                saved = true;
                const commands = await current.watchCommands(watchSettings);
                if (disposed || current !== bridge) throw new Error('Watch reconnected; review the current launchers before trying again.');
                await applyWatchCommands(commands);
                vscode.window.setStatusBarMessage(`Watch ${label} ${enabled ? 'on' : 'off'} for ${commands.length} running launcher${commands.length === 1 ? '' : 's'}`, 3000);
            } catch (error) {
                if (!saved) watchSettings[feature] = previous;
                errors.report(saved ? `Saved Watch ${label}; cannot apply to all launchers` : `Cannot save Watch ${label}`, error);
            } finally {
                changingWatch = false;
                publishWatchSettings();
                poll();
            }
        }

        async function deleteRunTimes(message) {
            if (deletingRunTimes) return;
            deletingRunTimes = true;
            const current = bridge;
            try {
                const answer = await vscode.window.showWarningMessage(
                    `Delete run time records for ${message.rows} selected ${message.rows === 1 ? 'row' : 'rows'}?`,
                    { modal: true, detail: 'This removes all saved VM timings in these rows. Recordings are kept.' }, 'Delete');
                if (answer !== 'Delete' || !current || current !== bridge || disposed) return;
                await current.deleteRunTimes(message.tokens);
            } catch (error) {
                errors.report('Cannot delete run times', error);
            } finally {
                deletingRunTimes = false;
                poll();
            }
        }
        async function openArtifact(token) {
            try {
                const { result, remote } = await bridge.artifact(token);
                if (result.error) throw new Error(result.error);
                if (result.kind === 'file' && !remote) {
                    if (!['video/webm', 'text/markdown', 'text/plain'].includes(result.media_type)) throw new Error('Unsupported artifact media type.');
                    const uri = new URL(result.uri);
                    if (uri.protocol !== 'file:' || uri.host || uri.search || uri.hash) throw new Error('Invalid artifact URI.');
                    const filename = fileURLToPath(uri);
                    if (fs.realpathSync(filename) !== filename || !fs.lstatSync(filename).isFile()) throw new Error('Artifact is no longer a regular file.');
                    if (result.media_type === 'video/webm') desktopCommand('gio', ['open', filename], 'Cannot open recording');
                    else await vscode.window.showTextDocument(vscode.Uri.file(filename), { preview: false });
                } else if (result.kind === 'text' && typeof result.text === 'string') {
                    const document = await vscode.workspace.openTextDocument({ content: result.text, language: 'markdown' });
                    await vscode.window.showTextDocument(document, { preview: false });
                } else if (result.kind === 'video' && typeof result.data === 'string' && /^[A-Za-z0-9+/]*={0,2}$/.test(result.data)) {
                    const video = vscode.window.createWebviewPanel('onpc.watch.recording', 'Watch recording', vscode.ViewColumn.Active,
                        { enableScripts: true, localResourceRoots: [] });
                    const nonce = randomBytes(16).toString('hex');
                    const listener = video.webview.onDidReceiveMessage(message => {
                        if (message.type === 'playback-error') errors.report('Cannot play Watch recording',
                            `VS Code could not decode the transferred WebM recording.\nMedia error: ${message.code}: ${message.detail}` +
                            (message.fallback ? `\nMedia Source fallback: ${message.fallback}` : ''));
                    });
                    video.onDidDispose(() => listener.dispose());
                    // A Blob avoids putting an entire recording into a media URL.
                    video.webview.html = `<!DOCTYPE html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; media-src blob:; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';"></head>
                        <body style="margin:0;background:#111;color:white"><p id="error" hidden>Cannot play this recording. See the Watch error details.</p>
                        <video controls autoplay style="width:100%;height:100vh"></video>
                        <script nonce="${nonce}">
                        const vscode = acquireVsCodeApi();
                        const video = document.querySelector('video');
                        const bytes = Uint8Array.from(atob('${result.data}'), character => character.charCodeAt(0));
                        const urls = [];
                        let triedMediaSource = false, failed = false, nativeError;
                        const showError = fallback => {
                            if (failed) return;
                            failed = true;
                            document.getElementById('error').hidden = false;
                            const error = nativeError || video.error;
                            vscode.postMessage({type: 'playback-error', code: error?.code,
                                detail: error?.message, fallback});
                        };
                        const playWithMediaSource = async () => {
                            // Electron's FFmpeg may lack the WebM demuxer. MSE uses
                            // Chromium's parser for the same bytes, without transcoding.
                            // https://github.com/microsoft/vscode/issues/195758
                            if (bytes.length < 4 || bytes[0] !== 0x1a || bytes[1] !== 0x45 ||
                                    bytes[2] !== 0xdf || bytes[3] !== 0xa3) {
                                throw new Error('Transferred recording is not WebM.');
                            }
                            const header = Array.from(bytes.subarray(0, 65536), byte => String.fromCharCode(byte)).join('');
                            const codecs = { V_VP8: 'vp8', V_VP9: 'vp9' };
                            const codec = Object.keys(codecs).find(id => header.includes(id));
                            if (!codec) throw new Error('Recording has no supported WebM video codec.');
                            const type = 'video/webm; codecs="' + codecs[codec] + '"';
                            if (typeof MediaSource === 'undefined' || !MediaSource.isTypeSupported(type)) {
                                throw new Error('VS Code does not support ' + type + '.');
                            }
                            const source = new MediaSource();
                            const url = URL.createObjectURL(source);
                            urls.push(url);
                            const opened = new Promise(resolve => source.addEventListener('sourceopen', resolve, {once: true}));
                            video.src = url;
                            await opened;
                            const buffer = source.addSourceBuffer(type);
                            await new Promise((resolve, reject) => {
                                buffer.addEventListener('updateend', resolve, {once: true});
                                buffer.addEventListener('error', () => reject(new Error('WebM Media Source parsing failed.')), {once: true});
                                buffer.appendBuffer(bytes);
                            });
                            source.endOfStream();
                        };
                        video.addEventListener('error', () => {
                            if (!triedMediaSource && video.error?.code === 4) {
                                triedMediaSource = true;
                                nativeError = {code: video.error.code, message: video.error.message};
                                playWithMediaSource().catch(error => showError(error.message));
                            } else showError(triedMediaSource ? video.error?.message : undefined);
                        });
                        const url = URL.createObjectURL(new Blob([bytes], {type: 'video/webm'}));
                        urls.push(url);
                        video.src = url;
                        window.addEventListener('unload', () => urls.forEach(url => URL.revokeObjectURL(url)));
                        </script></body></html>`;
                } else throw new Error('Adapter returned an unsupported artifact.');
            } catch (error) { errors.report('Cannot open Watch artifact', error); }
        }
        const visibility = panel.onDidChangeViewState(() => {
            // Retained webviews keep their DOM; ready handles any actual recreation.
            if (panel.visible) poll();
        });
        panel.onDidDispose(() => {
            disposed = true;
            stop();
            messages.dispose();
            visibility.dispose();
            panels.delete(root);
        });
        context.subscriptions.push({ dispose: () => {
            for (const helper of notifications) helper.kill();
        } });
        context.subscriptions.push(panel);
        panel.webview.html = html(panel.webview, context);
        start();
    };
    context.subscriptions.push(vscode.commands.registerCommand('onpc.watch', () =>
        openWatch().catch(error => errors.report('Cannot open Watch', error))));
}

module.exports = { activate };
