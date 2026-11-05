'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const { fileURLToPath } = require('node:url');
const { Bridge, configuration, resourceConfiguration } = require('./bridge');

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
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';">
        <link rel="stylesheet" href="${style}"><title>ONPC Watch</title></head>
        <body><div id="watch">
        <aside id="runs" aria-label="Run status across worktrees"><p class="empty" role="status">Waiting for tests…</p></aside>
        <div id="divider" role="separator" aria-label="Resize run status and viewers"
            aria-orientation="vertical" aria-valuemin="0" aria-valuemax="90" aria-valuenow="30" tabindex="0"></div>
        <section id="viewer" aria-label="UI and VM viewers"><div id="viewer-header">
        <nav id="viewers" aria-label="Viewers"></nav>
        <div id="tile-layout" role="group" aria-label="Tile layout">
        <button type="button" data-layout="auto" title="Auto" aria-label="Auto tile layout" aria-pressed="true">
            <svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="3" width="5" height="5"/><rect x="12" y="3" width="5" height="5"/><rect x="3" y="12" width="5" height="5"/><rect x="12" y="12" width="5" height="5"/></svg></button>
        <button type="button" data-layout="vertical" title="Vertical" aria-label="Vertical tile layout" aria-pressed="false">
            <svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="3" width="14" height="5"/><rect x="3" y="12" width="14" height="5"/></svg></button>
        <button type="button" data-layout="horizontal" title="Horizontal" aria-label="Horizontal tile layout" aria-pressed="false">
            <svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="3" width="5" height="14"/><rect x="12" y="3" width="5" height="14"/></svg></button>
        </div></div>
        <main id="grid"><p class="empty" role="status">Connecting to watch…</p></main></section></div>
        <footer><button id="restart" title="Reconnect to the watch backend">Reconnect</button>
        <span id="resources"></span></footer>
        <script nonce="${nonce}" src="${script}"></script></body></html>`;
}

function activate(context) {
    const panels = new Map();
    const output = vscode.window.createOutputChannel('ONPC Watch');
    context.subscriptions.push(output);
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
    context.subscriptions.push(vscode.commands.registerCommand('onpc.watch', async () => {
        if (!vscode.workspace.isTrusted) {
            vscode.window.showErrorMessage('Trust this workspace before opening ONPC Watch.');
            return;
        }
        let roots;
        try {
            roots = [...new Set((vscode.workspace.workspaceFolders || []).map(checkout).filter(Boolean))];
        } catch (error) {
            vscode.window.showErrorMessage(`ONPC Watch: ${error.message}`);
            return;
        }
        const root = roots.length === 1 ? roots[0] : roots.length &&
            await vscode.window.showQuickPick(roots, { placeHolder: 'Choose an ONPC checkout to watch' });
        if (!root) {
            if (!roots.length) vscode.window.showErrorMessage('Open an ONPC repository folder to use ONPC Watch.');
            return;
        }
        if (panels.has(root)) {
            panels.get(root).reveal();
            return;
        }
        const panel = vscode.window.createWebviewPanel('onpc.watch', 'ONPC Watch',
            vscode.ViewColumn.Active, {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')]
            });
        panels.set(root, panel);
        let bridge, timer, ready = false, rendering = false, renderedRevision = -1;
        let renderNumber = 0;
        let selection = { scope: 'all', selected: 'all' }, reset = true, disposed = false;
        let sessionRoot = '';
        let sessions = new Map();
        let runRoots = new Set();
        const notifications = new Set();
        function desktopCommand(command, args, label, input) {
            const helper = spawn(command, args,
                { stdio: [input === undefined ? 'ignore' : 'pipe', 'ignore', 'pipe'] });
            notifications.add(helper);
            let errors = '';
            const report = error => void vscode.window.showErrorMessage(`${label}: ${error}`);
            helper.stderr.on('data', data => { errors = (errors + data.toString()).slice(-4096); });
            helper.on('error', error => report(error.message));
            helper.on('close', code => {
                notifications.delete(helper);
                if (code || errors) report(errors || `desktop helper exited (${code})`);
            });
            if (input !== undefined) {
                helper.stdin.on('error', error => output.appendLine(`${label} input: ${error.message}`));
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
            output.appendLine(message);
            if (!disposed) void panel.webview.postMessage({ type: 'error', message });
        }
        function poll() {
            if (!bridge || !ready || !panel.visible || rendering) return;
            // Sources advance independently, with the existing render backpressure.
            bridge.tick({ ...selection, session_root: sessionRoot });
            void publish();
        }
        async function publish() {
            if (!bridge || !ready || !panel.visible || disposed) return;
            if (rendering || (!reset && renderedRevision === bridge.revision)) return;
            try {
                const current = bridge;
                const snapshot = current.snapshot({ ...selection, reset });
                selection = { scope: snapshot.scope, selected: snapshot.selected };
                reset = false;
                renderedRevision = current.revision;
                runRoots = new Set(snapshot.runs.map(entry => entry.id));
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
            try {
                const values = vscode.workspace.getConfiguration('onpc.watch', vscode.Uri.file(root)).get('sources', []);
                bridge = new Bridge(configuration(values, root), message => output.appendLine(message), publish,
                    resourceConfiguration(root));
            } catch (error) { failure(error.message); return; }
            timer = setInterval(poll, 200);
            poll();
        }
        const messages = panel.webview.onDidReceiveMessage(message => {
            if (message?.type === 'ready') {
                ready = true;
                rendering = false;
                reset = true;
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
            } else if (message?.type === 'launcherAction' && runRoots.has(message.root) &&
                       typeof message.run === 'string' && ['stop', 'resume'].includes(message.kind)) {
                void launchControl(message);
            } else if (message?.type === 'screenshot' && typeof message.png === 'string' &&
                       message.png.length <= 45 * 1024 * 1024 &&
                       /^data:image\/png;base64,[A-Za-z0-9+/]+={0,2}$/.test(message.png)) {
                desktopCommand('/usr/bin/python3', ['-B',
                    path.join(context.extensionUri.fsPath, 'screenshot.py')], 'Screenshot',
                    Buffer.from(message.png.slice('data:image/png;base64,'.length), 'base64'));
            } else if (message?.type === 'screenshotError' && typeof message.error === 'string') {
                void vscode.window.showErrorMessage(`Cannot take screenshot: ${message.error}`);
            } else if (message?.type === 'copy' && runRoots.has(message.root) &&
                       typeof message.text === 'string') {
                void vscode.env.clipboard.writeText(message.text).then(undefined,
                    error => vscode.window.showErrorMessage(`Cannot copy tab content: ${error.message}`));
            } else if (message?.type === 'sessionView' &&
                       (message.root === '' || runRoots.has(message.root))) {
                sessionRoot = message.root;
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
                       (message.root === sessionRoot || message.kind === 'extend')) {
                    bridge.action({ root: message.root, session: message.session, question: message.question,
                        kind: message.kind, text: message.text, id: message.id });
                } else if (bridge) {
                    bridge.results.push({ id: message.id, ok: false,
                        error: oversized ? 'Session input exceeds 64 KiB.' :
                            'Session changed; review the current session before sending.' });
                    bridge.revision++;
                }
                poll();
            } else if (message?.type === 'openRunFile' && typeof message.uri === 'string') {
                void openArtifact(message.uri);
            } else if (message?.type === 'deleteRunTimes' && Array.isArray(message.tokens) &&
                       message.tokens.length > 0 && message.tokens.length <= 4096 &&
                       message.tokens.every(token => typeof token === 'string' && bridge?.timings.has(token)) &&
                       Number.isInteger(message.rows) && message.rows > 0 && message.rows <= message.tokens.length) {
                void deleteRunTimes(message);
            }
        });
        let deletingRunTimes = false;
        let confirmingLauncher = false;
        async function launchControl(message) {
            if (confirmingLauncher) return;
            confirmingLauncher = true;
            const current = bridge;
            try {
                let command = await current.launcherCommand(message.root, message.run, message.kind);
                const action = message.kind === 'stop' ? 'Stop' : 'Resume';
                const answer = await vscode.window.showWarningMessage(
                    `${action} ${command.launcher} on ${command.source.label}?`,
                    { modal: true, detail: `Checkout: ${command.root}` }, action);
                if (answer !== action || disposed || current !== bridge) return;
                command = await current.launcherCommand(message.root, message.run, message.kind);
                // Recheck the publication when the terminal actually starts, and
                // pin dispatch to this checkout rather than a launcher default branch.
                const bootstrap = `import json, os, subprocess, sys
from pathlib import Path
c = json.loads(sys.argv[1])
root, run = Path(c['root']), Path(c['run'])
sys.path.insert(0, str(root / 'tools'))
from watch_output import read_json
if read_json(run.parent / 'current.json')['run'] != run.name:
    sys.exit('Launcher changed; refresh before trying again.')
branch = subprocess.check_output(['git', '-C', str(root), 'symbolic-ref', '--quiet', '--short', 'HEAD'], text=True).strip()
os.chdir(root)
os.environ['ONPC_LAUNCHER_DESTINATION'] = json.dumps(dict(root=str(root), branch=branch, launcher=c['launcher'], pid=os.getpid()))
os.execv('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(root / 'tools' / c['launcher']), *c['argv']])
`;
                const argv = ['/usr/bin/python3', '-IBu', '-c', bootstrap,
                    JSON.stringify({ root: command.root, run: command.run, launcher: command.launcher, argv: command.argv })];
                const remote = command.source.transport === 'ssh';
                const quote = value => "'" + value.replace(/'/g, "'\\''") + "'";
                // Match public SSH launcher startup when Codex comes from NVM.
                const remoteArgv = ['/bin/bash', '-c', `if ! command -v codex >/dev/null 2>&1; then
    export NVM_DIR="\${NVM_DIR:-$HOME/.nvm}"
    if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi
fi
exec "$@"`, 'onpc-watch', ...argv];
                const terminal = vscode.window.createTerminal({
                    name: `${command.launcher}: ${message.kind} (${command.source.label})`,
                    shellPath: remote ? 'ssh' : argv[0],
                    shellArgs: remote ? ['-t', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                        '-o', 'ConnectTimeout=5', '--', command.source.host, remoteArgv.map(quote).join(' ')] : argv.slice(1),
                    ...(remote ? {} : { cwd: command.root })
                });
                terminal.show(true);
            } catch (error) {
                void vscode.window.showErrorMessage(`Cannot ${message.kind} launcher: ${error.message}`);
            } finally {
                confirmingLauncher = false;
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
                void vscode.window.showErrorMessage(`Cannot delete run times: ${error.message}`);
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
                    const video = vscode.window.createWebviewPanel('onpc.watch.recording', 'Watch recording', vscode.ViewColumn.Active, {});
                    video.webview.html = `<!DOCTYPE html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; media-src data:; style-src 'unsafe-inline';"></head><body style="margin:0;background:#111"><video controls autoplay style="width:100%;height:100vh" src="data:video/webm;base64,${result.data}"></video></body></html>`;
                } else throw new Error('Adapter returned an unsupported artifact.');
            } catch (error) { void vscode.window.showErrorMessage(`Cannot open Watch artifact: ${error.message}`); }
        }
        const visibility = panel.onDidChangeViewState(() => {
            if (panel.visible) { reset = true; poll(); }
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
    }));
}

module.exports = { activate };
