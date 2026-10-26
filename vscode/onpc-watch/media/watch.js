/* The webview only selects views and acknowledges rendered snapshots. */
'use strict';

(() => {
    const vscode = acquireVsCodeApi();
    const grid = document.getElementById('grid');
    const viewers = document.getElementById('viewers');
    const checkouts = document.getElementById('checkouts');
    const resources = document.getElementById('resources');
    const cards = new Map();
    let state = vscode.getState() || { scope: 'all', selected: 'all' };
    let pending = Promise.resolve();

    function select(scope, selected) {
        state = { scope, selected };
        vscode.setState(state);
        vscode.postMessage({ type: 'select', ...state });
    }

    function tabs(nav, items, selected, choose) {
        const signature = JSON.stringify([items, selected]);
        if (nav.dataset.signature === signature) return;
        nav.dataset.signature = signature;
        nav.replaceChildren(...items.map(item => {
            const button = document.createElement('button');
            button.textContent = item.label;
            button.classList.toggle('idle', item.id !== 'all' && !item.active);
            button.setAttribute('aria-pressed', String(item.id === selected));
            button.addEventListener('click', () => choose(item.id));
            return button;
        }));
    }

    function element(tag, className, parent) {
        const node = document.createElement(tag);
        node.className = className;
        parent.append(node);
        return node;
    }

    function card(entry) {
        const body = document.createElement('article');
        body.className = `card ${entry.kind}`;
        const title = element('button', 'title', body);
        title.addEventListener('click', () => select(state.scope, entry.id));
        const heading = element('div', 'heading', body);
        const step = element('div', 'step', body);
        const display = element('div', 'display', body);
        const canvas = element('canvas', 'screen', display);
        canvas.setAttribute('aria-label', entry.kind === 'vm' ? 'VM display, view only' : 'UI worker display, view only');
        canvas.hidden = true;
        const waiting = element('p', 'waiting', display);
        waiting.textContent = 'Waiting for display';
        const activity = element('pre', 'activity', body);
        activity.setAttribute('aria-label', 'Filtered VM command output');
        const status = element('div', 'status', body);
        return { body, title, heading, step, canvas, waiting, activity, status };
    }

    function image(url) {
        return new Promise((resolve, reject) => {
            const value = new Image();
            value.onload = () => resolve(value);
            value.onerror = () => reject(new Error('Cannot decode watch frame'));
            value.src = url;
        });
    }

    async function screen(view, data) {
        if (data === undefined) return;
        view.canvas.hidden = !data;
        view.waiting.hidden = Boolean(data);
        if (!data) {
            view.canvas.width = view.canvas.height = 0;
            return;
        }
        const [frame, cursor] = await Promise.all([
            image(data.image), data.cursor ? image(data.cursor.image) : undefined
        ]);
        view.canvas.width = data.width;
        view.canvas.height = data.height;
        const context = view.canvas.getContext('2d', { alpha: false });
        context.drawImage(frame, 0, 0);
        if (cursor) context.drawImage(cursor, data.cursor.x, data.cursor.y);
    }

    function terminal(text) {
        // Only transport-filtered output is displayed. Render it as text, never HTML.
        return text.replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
            .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '').replace(/\r\n?/g, '\n')
            .replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '');
    }

    function message(text) {
        cards.clear();
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.setAttribute('role', 'status');
        empty.textContent = text;
        grid.replaceChildren(empty);
    }

    async function render(snapshot) {
        state = { scope: snapshot.scope, selected: snapshot.selected };
        vscode.setState(state);
        tabs(checkouts, [{ id: 'all', label: 'All', active: true }, ...snapshot.checkouts.map(item =>
            ({ ...item, active: snapshot.entries.some(entry => entry.active && entry.label.startsWith(`[${item.label}] `)) }))],
            state.scope, scope => select(scope, 'all'));
        tabs(viewers, [{ id: 'all', label: 'All', active: true }, ...snapshot.entries.map(entry =>
            ({ id: entry.id, label: entry.label, active: entry.locked }))],
            state.selected, selected => select(state.scope, selected));
        resources.textContent = snapshot.resources;
        const shown = snapshot.entries.filter(entry => state.selected === 'all' ? entry.active : entry.id === state.selected);
        const ids = new Set(shown.map(entry => entry.id));
        for (const [id, view] of cards) {
            if (!ids.has(id)) { view.body.remove(); cards.delete(id); }
        }
        if (!shown.length) {
            message('Waiting for UI tests or VM activity. Select a VM tab to keep its viewer open.');
            return;
        }
        grid.querySelector('.empty')?.remove();
        grid.classList.toggle('single', shown.length === 1);
        const draws = [];
        shown.forEach((entry, index) => {
            let view = cards.get(entry.id);
            if (!view) { view = card(entry); cards.set(entry.id, view); }
            if (view.source !== entry.source) {
                void screen(view, null);
                view.source = entry.source;
            }
            if (grid.children[index] !== view.body) grid.insertBefore(view.body, grid.children[index] || null);
            view.title.textContent = entry.label;
            view.heading.textContent = entry.heading;
            view.step.textContent = entry.step;
            view.status.textContent = entry.status;
            const text = terminal(entry.activity);
            if (view.activity.textContent !== text) {
                const follow = view.activity.scrollHeight - view.activity.clientHeight - view.activity.scrollTop < 24;
                view.activity.textContent = text;
                if (follow) view.activity.scrollTop = view.activity.scrollHeight;
            }
            draws.push(screen(view, entry.screen));
        });
        await Promise.all(draws);
    }

    window.addEventListener('message', event => {
        if (event.data.type === 'snapshot') {
            pending = pending.then(() => render(event.data)).catch(error => message(error.message))
                .finally(() => vscode.postMessage({ type: 'rendered' }));
        } else if (event.data.type === 'error') {
            message(event.data.message);
        }
    });
    document.getElementById('restart').addEventListener('click', () => {
        message('Reconnecting to watch…');
        vscode.postMessage({ type: 'restart' });
    });
    select(state.scope, state.selected);
    vscode.postMessage({ type: 'ready' });
})();
