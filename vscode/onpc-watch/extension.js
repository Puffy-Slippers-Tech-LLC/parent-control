'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const { randomBytes } = require('node:crypto');

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
            aria-orientation="vertical" aria-valuemin="10" aria-valuemax="90" aria-valuenow="30" tabindex="0"></div>
        <section id="viewer" aria-label="UI and VM viewers"><nav id="viewers" aria-label="Viewers"></nav>
        <main id="grid"><p class="empty" role="status">Connecting to watch…</p></main></section></div>
        <footer><span id="resources"></span>
        <button id="restart" title="Reconnect to the watch backend">Reconnect</button></footer>
        <script nonce="${nonce}" src="${script}"></script></body></html>`;
}

function activate(context) {
    const panels = new Map();
    const output = vscode.window.createOutputChannel('ONPC Watch');
    context.subscriptions.push(output);
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
        let child, lines, timer, ready = false, busy = false, rendering = false;
        let selection = { scope: 'all', selected: 'all' }, reset = true, disposed = false;
        function stop() {
            clearInterval(timer);
            lines?.close();
            if (child) {
                const owned = child;
                child = undefined;
                owned.stdin.end();
                owned.kill();
            }
            busy = rendering = false;
        }
        function failure(message) {
            stop();
            output.appendLine(message);
            if (!disposed) void panel.webview.postMessage({ type: 'error', message });
        }
        function poll() {
            if (!child || !ready || busy || rendering || !panel.visible) return;
            busy = true;
            child.stdin.write(JSON.stringify({ ...selection, reset }) + '\n');
            reset = false;
        }
        function start() {
            stop();
            reset = true;
            const owned = spawn('/usr/bin/python3', ['-B', path.join(root, 'tools', 'watch_webview.py'),
                '--root', root], { cwd: root, stdio: ['pipe', 'pipe', 'pipe'] });
            child = owned;
            owned.on('error', error => {
                if (child === owned) failure(`Cannot start watch: ${error.message}`);
            });
            owned.stdin.on('error', error => {
                if (child === owned) failure(`Watch connection closed: ${error.message}`);
            });
            owned.stderr.on('data', data => output.append(data.toString()));
            owned.on('exit', (code, signal) => {
                if (child === owned) failure(`Watch backend stopped (${signal || code}). See ONPC Watch output; click Reconnect to retry.`);
            });
            lines = createInterface({ input: owned.stdout });
            lines.on('line', async line => {
                if (child !== owned || disposed) return;
                try {
                    const snapshot = JSON.parse(line);
                    busy = false;
                    rendering = true;
                    const delivered = await panel.webview.postMessage({ type: 'snapshot', ...snapshot });
                    if (!delivered) { rendering = false; reset = true; }
                } catch (error) {
                    failure(`Invalid watch response: ${error.message}`);
                }
            });
            timer = setInterval(poll, 200);
            poll();
        }
        const messages = panel.webview.onDidReceiveMessage(message => {
            if (message?.type === 'ready') {
                ready = true;
                rendering = false;
                reset = true;
                poll();
            } else if (message?.type === 'rendered') {
                rendering = false;
            } else if (message?.type === 'select' &&
                       typeof message.scope === 'string' && message.scope.length <= 4096 &&
                       typeof message.selected === 'string' && message.selected.length <= 256) {
                selection = { scope: message.scope, selected: message.selected };
                reset = true;
                poll();
            } else if (message?.type === 'restart') {
                start();
            }
        });
        const visibility = panel.onDidChangeViewState(() => {
            if (panel.visible) { rendering = false; reset = true; poll(); }
        });
        panel.onDidDispose(() => {
            disposed = true;
            stop();
            messages.dispose();
            visibility.dispose();
            panels.delete(root);
        });
        context.subscriptions.push(panel);
        panel.webview.html = html(panel.webview, context);
        start();
    }));
}

module.exports = { activate };
