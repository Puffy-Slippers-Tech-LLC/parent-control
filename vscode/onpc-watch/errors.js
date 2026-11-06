'use strict';

const vscode = require('vscode');
const { randomBytes } = require('node:crypto');

// Watch infrastructure diagnostics only. Launcher result/error rows are data.
class WatchErrors {
    constructor(context, output) {
        this.context = context;
        this.output = output;
        this.entries = new Map();
        this.viewers = new Set();
        this.unread = false;
    }

    attach(panel, standalone = false) {
        if (!standalone) {
            this.viewers.add(panel);
        }
        const messages = panel.webview.onDidReceiveMessage(async message => {
            if (message?.type === 'errorReady') {
                this.publishState();
                if (this.panel === panel) this.publish(true);
                return;
            }
            if (message?.type === 'showError' && !standalone) {
                this.show(panel);
                return;
            }
            if (this.panel !== panel) return;
            if (message?.type === 'closeError') {
                this.panel = undefined;
                if (standalone) panel.dispose();
            } else if (message?.type === 'copyError') {
                try {
                    await vscode.env.clipboard.writeText(this.text());
                    await panel.webview.postMessage({ type: 'errorCopied' });
                } catch (error) {
                    await panel.webview.postMessage({ type: 'errorCopyFailed', message: String(error) });
                }
            }
        });
        panel.onDidDispose(() => {
            this.viewers.delete(panel);
            if (this.panel === panel) this.panel = undefined;
            messages.dispose();
        });
    }

    report(title, error) {
        const detail = error instanceof Error ? error.stack || error.message : String(error);
        const text = `${title}\n\n${detail}`;
        this.output.appendLine(text);
        if (!this.entries.has(text)) {
            this.entries.set(text, `${new Date().toLocaleString()}\n${text}`);
            this.unread = !this.panel;
        }
        this.publishState();
        this.publish();
    }

    show(preferred) {
        this.unread = false;
        this.publishState();
        if (preferred && this.panel !== preferred) {
            if (this.panel && !this.viewers.has(this.panel)) this.panel.dispose();
            else void this.panel?.webview.postMessage({ type: 'hideError' });
            this.panel = preferred;
        }
        if (!this.panel) {
            this.panel = [...this.viewers].find(panel => panel.active) ||
                [...this.viewers].find(panel => panel.visible) || [...this.viewers].at(-1);
        }
        if (!this.panel) {
            const panel = vscode.window.createWebviewPanel('onpc.watch.error', 'ONPC Watch error',
                vscode.ViewColumn.Active, { enableScripts: true, localResourceRoots: [] });
            this.panel = panel;
            this.context.subscriptions.push(panel);
            this.attach(panel, true);
            const nonce = randomBytes(16).toString('hex');
            panel.webview.html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
<style nonce="${nonce}">body { color: var(--vscode-foreground); background: var(--vscode-editor-background); font-family: var(--vscode-font-family); }</style>
</head><body>${errorDialog(nonce)}
<script nonce="${nonce}">initializeWatchErrors(acquireVsCodeApi());</script></body></html>`;
        } else {
            this.panel.reveal();
            this.publish(true);
        }
    }

    text() { return [...this.entries.values()].join('\n\n' + '─'.repeat(60) + '\n\n'); }
    publish(open = false) { void this.panel?.webview.postMessage({ type: 'errorDetails', text: this.text(), open }); }
    publishState() {
        for (const panel of this.viewers) void panel.webview.postMessage({
            type: 'errorState', available: this.entries.size > 0, unread: this.unread
        });
    }
}

function errorDialog(nonce) {
    return `<style nonce="${nonce}">
#watch-error { box-sizing: border-box; width: calc(100% - 48px); max-width: 800px; height: 65vh; max-height: 600px; padding: 20px;
color: inherit; background: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-widget-border); }
#watch-error[open] { display: flex; flex-direction: column; gap: 12px; }
#watch-error::backdrop { background: #0006; }
#watch-error h1 { font-size: 18px; margin: 0; }
#watch-error textarea { flex: 1; min-height: 0; width: 100%; box-sizing: border-box; resize: none; overflow: auto; white-space: pre;
color: var(--vscode-input-foreground); background: var(--vscode-input-background); font-family: var(--vscode-editor-font-family); }
#watch-error footer { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
#watch-error button { color: var(--vscode-button-foreground); background: var(--vscode-button-background); border: 0; padding: 6px 14px; cursor: pointer; }
</style><dialog id="watch-error" aria-labelledby="watch-error-title"><h1 id="watch-error-title">ONPC Watch error</h1>
<textarea readonly aria-label="Full Watch error details" spellcheck="false"></textarea>
<footer><button id="watch-error-copy">Copy all</button><button id="watch-error-close">Close</button><span role="status"></span></footer></dialog>
<script nonce="${nonce}">
function initializeWatchErrors(vscode) {
const dialog = document.getElementById('watch-error');
const text = dialog.querySelector('textarea');
const status = dialog.querySelector('[role=status]');
const indicator = document.getElementById('watch-error-indicator');
if (indicator) indicator.onclick = () => vscode.postMessage({ type: 'showError' });
window.addEventListener('message', event => {
    if (event.data.type === 'errorState' && indicator) {
        indicator.hidden = !event.data.available;
        indicator.classList.toggle('unread', event.data.unread);
    }
    if (event.data.type === 'hideError') dialog.close();
    if (event.data.type === 'errorDetails') {
        text.value = event.data.text;
        status.textContent = '';
        if (event.data.open && !dialog.open) dialog.showModal();
    }
    if (event.data.type === 'errorCopied') status.textContent = 'Copied.';
    if (event.data.type === 'errorCopyFailed') status.textContent = 'Copy failed: ' + event.data.message + '. Select the text and copy manually.';
});
document.getElementById('watch-error-copy').onclick = () => vscode.postMessage({ type: 'copyError' });
const close = () => { dialog.close(); vscode.postMessage({ type: 'closeError' }); };
document.getElementById('watch-error-close').onclick = close;
dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
vscode.postMessage({ type: 'errorReady' });
}
</script>`;
}

module.exports = { WatchErrors, errorDialog };
