'use strict';

const vscode = require('vscode');
const { randomBytes } = require('node:crypto');

// Watch infrastructure diagnostics only. Launcher result/error rows are data.
class WatchErrors {
    constructor(context, output) {
        this.context = context;
        this.output = output;
        this.entries = new Map();
    }

    report(title, error, reveal = false) {
        const detail = error instanceof Error ? error.stack || error.message : String(error);
        const text = `${title}\n\n${detail}`;
        this.output.appendLine(text);
        if (error?.quiet) return;
        if (this.entries.has(text) && (!reveal || this.panel)) {
            if (reveal) this.panel?.reveal();
            return; // A reconnect loop must not steal focus repeatedly.
        }
        this.entries.set(text, `${new Date().toLocaleString()}\n${text}`);
        if (!this.panel) {
            const panel = vscode.window.createWebviewPanel('onpc.watch.error', 'ONPC Watch error',
                vscode.ViewColumn.Active, { enableScripts: true, localResourceRoots: [] });
            this.panel = panel;
            this.context.subscriptions.push(panel);
            panel.onDidDispose(() => { this.panel = undefined; });
            panel.webview.onDidReceiveMessage(async message => {
                if (message?.type === 'ready') this.publish();
                else if (message?.type === 'close') panel.dispose();
                else if (message?.type === 'copy') {
                    try {
                        await vscode.env.clipboard.writeText(this.text());
                        await panel.webview.postMessage({ type: 'copied' });
                    } catch (error) {
                        // Keep the selectable text available even if clipboard access fails.
                        await panel.webview.postMessage({ type: 'copyFailed', message: String(error) });
                    }
                }
            });
            const nonce = randomBytes(16).toString('hex');
            panel.webview.html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
<style nonce="${nonce}">
body { color: var(--vscode-foreground); background: var(--vscode-editor-background); font-family: var(--vscode-font-family); }
dialog { box-sizing: border-box; width: calc(100% - 32px); max-width: 1000px; height: calc(100% - 32px); max-height: 800px; padding: 20px;
color: inherit; background: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-widget-border); }
dialog[open] { display: flex; flex-direction: column; gap: 12px; }
dialog::backdrop { background: #0006; }
h1 { font-size: 18px; margin: 0; }
textarea { flex: 1; min-height: 0; width: 100%; box-sizing: border-box; resize: none; overflow: auto; white-space: pre;
color: var(--vscode-input-foreground); background: var(--vscode-input-background); font-family: var(--vscode-editor-font-family); }
footer { display: flex; gap: 12px; align-items: center; }
button { color: var(--vscode-button-foreground); background: var(--vscode-button-background); border: 0; padding: 6px 14px; cursor: pointer; }
</style></head><body><dialog aria-labelledby="title"><h1 id="title">ONPC Watch error</h1>
<textarea readonly aria-label="Full Watch error details" spellcheck="false"></textarea>
<footer><button id="copy">Copy all</button><button id="close">Close</button><span role="status"></span></footer></dialog>
<script nonce="${nonce}">
const vscode = acquireVsCodeApi();
const dialog = document.querySelector('dialog');
const text = document.querySelector('textarea');
const status = document.querySelector('[role=status]');
window.addEventListener('message', event => {
    if (event.data.type === 'details') { text.value = event.data.text; status.textContent = ''; }
    if (event.data.type === 'copied') status.textContent = 'Copied.';
    if (event.data.type === 'copyFailed') status.textContent = 'Copy failed: ' + event.data.message + '. Select the text and copy manually.';
});
document.getElementById('copy').onclick = () => vscode.postMessage({ type: 'copy' });
document.getElementById('close').onclick = () => vscode.postMessage({ type: 'close' });
dialog.addEventListener('cancel', event => { event.preventDefault(); vscode.postMessage({ type: 'close' }); });
dialog.showModal();
vscode.postMessage({ type: 'ready' });
</script></body></html>`;
        } else {
            this.panel.reveal();
            this.publish();
        }
    }

    text() { return [...this.entries.values()].join('\n\n' + '─'.repeat(60) + '\n\n'); }
    publish() { void this.panel?.webview.postMessage({ type: 'details', text: this.text() }); }
}

module.exports = { WatchErrors };
