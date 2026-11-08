'use strict';

const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const { fileURLToPath } = require('node:url');
const { stripVTControlCharacters } = require('node:util');
const { Bridge, configuration, resourceConfiguration } = require('./bridge');
const { WatchErrors, errorDialog } = require('./errors');

// A small stdlib PTY bridge keeps interactive launcher behavior while exposing
// output and window-size changes to the extension. Input is newline-delimited
// JSON; output is the unchanged terminal byte stream.
const actionPty = `import errno, fcntl, json, os, pty, select, signal, struct, sys, termios
command, size = json.loads(sys.argv[1]), json.loads(sys.argv[2])
def resize(fd, size):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', size['rows'], size['columns'], 0, 0))
pid, master = pty.fork()
if pid == 0:
    resize(0, size)
    os.environ['TERM'] = 'xterm-256color'
    os.execvp(command[0], command)
os.set_blocking(master, False)
incoming, pending = b'', b''
reaped = ended = False
try:
    while True:
        readable, writable, _ = select.select([0, master], [master] if pending else [], [])
        if master in readable:
            try:
                data = os.read(master, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                ended = True
                break
            if not data:
                ended = True
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        if 0 in readable:
            data = os.read(0, 65536)
            if not data:
                break
            incoming += data
            while b'\\n' in incoming:
                line, incoming = incoming.split(b'\\n', 1)
                message = json.loads(line)
                if 'size' in message:
                    resize(master, message['size'])
                else:
                    pending += message['input'].encode('utf-8')
        if master in writable:
            try:
                pending = pending[os.write(master, pending):]
            except BlockingIOError:
                pass
    if ended:
        _, status = os.waitpid(pid, 0)
        reaped = True
        code = os.waitstatus_to_exitcode(status)
        sys.exit(code if code >= 0 else 128 - code)
finally:
    if not reaped:
        try:
            os.kill(pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
    os.close(master)
`;

// Native terminal APIs do not expose stderr or full terminal-start failures.
function actionTerminal({ name, shellPath, shellArgs, cwd, invocation, failed }) {
    const write = new vscode.EventEmitter();
    const close = new vscode.EventEmitter();
    let child, cancelled = false, finished = false, transcript = '', omitted = false;
    const limit = 1024 * 1024;
    let size = { rows: 24, columns: 80 };
    const dimensions = value => ({
        rows: Math.min(65535, Math.max(1, Math.floor(value.rows))),
        columns: Math.min(65535, Math.max(1, Math.floor(value.columns)))
    });
    const send = message => {
        if (!finished && !cancelled && child?.stdin.writable) {
            child.stdin.write(JSON.stringify(message) + '\n');
        }
    };
    const capture = data => {
        transcript += data;
        if (transcript.length > limit) {
            transcript = transcript.slice(-limit);
            omitted = true;
        }
        write.fire(data);
    };
    const finish = (code, signal, error) => {
        if (finished) return;
        finished = true;
        if (!cancelled && (error || code !== 0)) {
            failed(`${invocation}\n\nExit code: ${code ?? 'unavailable'}\nSignal: ${signal || 'none'}\n` +
                (error ? `\n${error.stack || error}\n` : '') +
                `\nProcess output${omitted ? ' (last 1,048,576 characters; earlier output omitted)' : ''}:\n${stripVTControlCharacters(transcript)}`);
        }
        close.fire(Number.isInteger(code) && code >= 0 ? code : 1);
    };
    const terminal = vscode.window.createTerminal({ name, pty: {
        onDidWrite: write.event,
        onDidClose: close.event,
        open(initialDimensions) {
            try {
                if (initialDimensions) size = dimensions(initialDimensions);
                child = spawn('/usr/bin/python3', ['-IBu', '-c', actionPty,
                    JSON.stringify([shellPath, ...shellArgs]), JSON.stringify(size)],
                { cwd, stdio: ['pipe', 'pipe', 'pipe'] });
                for (const stream of [child.stdout, child.stderr]) {
                    stream.setEncoding('utf8');
                    stream.on('data', capture);
                }
                child.stdin.on('error', error => {
                    if (error.code !== 'EPIPE') finish(null, null, error);
                });
                child.on('error', error => finish(null, null, error));
                child.on('close', (code, signal) => finish(code, signal));
            } catch (error) { finish(null, null, error); }
        },
        handleInput(data) { send({ input: data }); },
        setDimensions(value) {
            size = dimensions(value);
            send({ size });
        },
        close() {
            cancelled = true;
            // EOF asks the bridge to hang up only its owned foreground process.
            // Detached launcher work keeps its existing independent lifecycle.
            if (!finished) child?.stdin.end();
            write.dispose();
            close.dispose();
        }
    } });
    terminal.show(true);
    return terminal;
}

function actionBackground({ shellPath, shellArgs, cwd, invocation, failed }) {
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
        <main id="grid"><p class="empty" role="status">Connecting to watch…</p></main>
        <div id="minimized-tiles" aria-label="Minimized tiles" hidden>
        <div id="minimized-titles"></div>
        <details id="tile-overflow"><summary title="Show all tiles" aria-label="Show all tiles">&gt;&gt;</summary>
        <div id="tile-list" aria-label="All tiles"></div></details></div></section></div>
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
                void publish();
            } catch (error) { failure(error.stack || error.message); }
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
                       typeof message.run === 'string' && ['stop', 'cancel-stop', 'resume', 'reload'].includes(message.kind)) {
                void launchControl(message);
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
                    if (message.command === true) vscode.window.setStatusBarMessage('Command copied', 1500);
                },
                    error => errors.report('Cannot copy tab content', error));
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
        let deletingRunTimes = false;
        let confirmingLauncher = false;
        async function launchControl(message) {
            if (confirmingLauncher) return;
            confirmingLauncher = true;
            const current = bridge;
            try {
                let command = await current.launcherCommand(message.root, message.run, message.kind);
                const action = { stop: 'Stop', resume: 'Resume', reload: 'Reload', 'cancel-stop': 'Cancel stop request' }[message.kind];
                const commandText = [ `tools/${command.launcher}`, ...command.argv ].map(value =>
                    /^[\w@%+=:,./-]+$/.test(value) ? value : "'" + value.replace(/'/g, "'\\''") + "'").join(' ');
                const answer = await vscode.window.showWarningMessage(
                    `${action} for ${command.launcher} on ${command.source.label}?`,
                    { modal: true, detail: `Checkout: ${command.root}\nCommand: ${commandText}` }, action);
                if (answer !== action) return;
                if (disposed || current !== bridge) return;
                command = await current.launcherCommand(message.root, message.run, message.kind);
                // Recheck the publication when the action actually starts, and
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
if '--cancel-stop' in c['argv']:
    os.environ['ONPC_CANCEL_STOP_RUN'] = str(run)
os.environ['ONPC_LAUNCHER_DESTINATION'] = json.dumps(dict(root=str(root), branch=branch, launcher=c['launcher'], pid=os.getpid()))
os.execv('/usr/bin/python3', ['/usr/bin/python3', '-IBu', str(root / 'tools' / c['launcher']), *c['argv']])
`;
                const argv = ['/usr/bin/python3', '-IBu', '-c', bootstrap,
                    JSON.stringify({ root: command.root, run: command.run, launcher: command.launcher, argv: command.argv })];
                const remote = command.source.transport === 'ssh';
                const background = message.kind === 'resume';
                const quote = value => "'" + value.replace(/'/g, "'\\''") + "'";
                // The destination launcher verifies its checkout and uses the
                // shared adapter environment/readiness route at agent admission.
                // Observation and stop actions need no coding CLI or NVM.
                const shellPath = remote ? 'ssh' : argv[0];
                const shellArgs = remote ? [background ? '-T' : '-t', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                    '-o', 'ConnectTimeout=5', '--', command.source.host, argv.map(quote).join(' ')] : argv.slice(1);
                const runAction = background ? actionBackground : actionTerminal;
                runAction({
                    name: `${command.launcher}: ${message.kind} (${command.source.label})`,
                    shellPath, shellArgs,
                    ...(remote ? {} : { cwd: command.root }),
                    invocation: `Action: ${action}\nHost: ${command.source.label}\nCheckout: ${command.root}\nCommand: ${commandText}\n\nProcess invocation:\n${[shellPath, ...shellArgs].map(quote).join(' ')}`,
                    failed(diagnostic) {
                        lastTerminalDiagnostic = diagnostic;
                        errors.report(`Cannot ${message.kind} launcher`, diagnostic);
                    }
                });
            } catch (error) {
                errors.report(`Cannot ${message.kind} launcher`, error);
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
                    const video = vscode.window.createWebviewPanel('onpc.watch.recording', 'Watch recording', vscode.ViewColumn.Active, {});
                    video.webview.html = `<!DOCTYPE html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; media-src data:; style-src 'unsafe-inline';"></head><body style="margin:0;background:#111"><video controls autoplay style="width:100%;height:100vh" src="data:video/webm;base64,${result.data}"></video></body></html>`;
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
