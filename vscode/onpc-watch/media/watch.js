/* The webview renders read-only status and feeds, and keeps its split locally. */
'use strict';

(() => {
    const vscode = acquireVsCodeApi();
    const grid = document.getElementById('grid');
    const viewers = document.getElementById('viewers');
    const resources = document.getElementById('resources');
    const runs = document.getElementById('runs');
    const layout = document.getElementById('watch');
    const divider = document.getElementById('divider');
    const cards = new Map();
    const sections = new Map();
    const saved = vscode.getState();
    let state = { scope: 'all', selected: saved?.selected || 'all' };
    let split = Number.isFinite(saved?.split) ? saved.split : 30;
    let pending = Promise.resolve();
    let resourceSample;

    function persist() {
        vscode.setState({ ...state, split });
    }

    function resize(value) {
        split = Math.min(90, Math.max(10, value));
        layout.style.gridTemplateColumns = `minmax(0, ${split}fr) 6px minmax(0, ${100 - split}fr)`;
        divider.setAttribute('aria-valuenow', String(Math.round(split)));
        persist();
    }

    divider.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        event.preventDefault();
        divider.focus();
        divider.setPointerCapture(event.pointerId);
        document.body.classList.add('resizing');
    });
    divider.addEventListener('pointermove', event => {
        if (!divider.hasPointerCapture(event.pointerId)) return;
        const bounds = layout.getBoundingClientRect();
        resize(100 * (event.clientX - bounds.left - 3) / Math.max(1, bounds.width - 6));
    });
    divider.addEventListener('pointerup', event => {
        if (divider.hasPointerCapture(event.pointerId)) divider.releasePointerCapture(event.pointerId);
    });
    divider.addEventListener('lostpointercapture', () => document.body.classList.remove('resizing'));
    divider.addEventListener('dblclick', () => resize(30));
    divider.addEventListener('keydown', event => {
        const value = { ArrowLeft: split - 2, ArrowRight: split + 2, Home: 10, End: 90 }[event.key];
        if (value === undefined) return;
        event.preventDefault();
        resize(value);
    });
    resize(split);

    function select(scope, selected) {
        state = { scope, selected };
        persist();
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

    function runStatus(entries) {
        const ids = new Set(entries.map(entry => entry.id));
        for (const [id, section] of sections) {
            if (!ids.has(id)) { section.body.remove(); sections.delete(id); }
        }
        if (entries.length) runs.querySelector('.empty')?.remove();
        entries.forEach((entry, index) => {
            let section = sections.get(entry.id);
            if (!section) {
                const body = element('section', 'run', runs);
                const heading = element('h2', 'run-heading', body);
                const content = element('pre', 'run-status', body);
                section = { body, heading, content };
                sections.set(entry.id, section);
            }
            if (runs.children[index] !== section.body) runs.insertBefore(section.body, runs.children[index] || null);
            section.heading.textContent = entry.label;
            section.heading.classList.toggle('failed', entry.status === 'failed');
            const signature = JSON.stringify([entry.rows, entry.active]);
            if (section.signature === signature) return;
            section.signature = signature;
            const follow = section.content.scrollHeight - section.content.clientHeight - section.content.scrollTop < 24;
            const rows = entry.rows.map(row => {
                if (row.map(part => part.text).join('').trim() === '─') {
                    const separator = document.createElement('hr');
                    separator.className = 'run-separator';
                    return separator;
                }
                const line = document.createElement('div');
                if (!row.length) line.textContent = '\u00a0';
                row.forEach(part => {
                    const span = element(part.link ? 'a' : 'span', '', line);
                    span.textContent = part.text;
                    if (part.link) {
                        span.href = '#';
                        span.style.textDecoration = 'underline';
                        span.addEventListener('click', event => {
                            event.preventDefault();
                            vscode.postMessage({ type: 'openErrorLog', uri: part.link });
                        });
                    }
                    if (part.color) span.style.color = part.color;
                    if (part.bold) span.style.fontWeight = 'bold';
                });
                return line;
            });
            if (!rows.length) {
                const waiting = document.createElement('div');
                waiting.textContent = entry.active ? 'Waiting for run status…' : 'Waiting for tests…';
                rows.push(waiting);
            }
            section.content.replaceChildren(...rows);
            if (follow) section.content.scrollTop = section.content.scrollHeight;
        });
    }

    function resourceCharts(snapshot) {
        if (resourceSample === snapshot.resource_sample) return;
        resourceSample = snapshot.resource_sample;
        resources.setAttribute('aria-label', snapshot.resources);
        if (!resources.children.length) {
            for (const name of ['CPU', 'Memory', 'Disk']) {
                const group = element('span', 'resource', resources);
                group.title = `${name}: last minute, fixed 0–100% scale. History stays in memory only.` +
                    (name === 'Disk' ? ' Busiest physical disk (iostat %util); NVMe busy time is not throughput saturation.' : '');
                element('strong', '', group).textContent = `${name}:`;
                element('span', 'percentage', group);
                const canvas = element('canvas', 'resource-chart', group);
                canvas.width = 140;
                canvas.height = 44;
                canvas.setAttribute('aria-hidden', 'true');
            }
        }
        const colors = ['52, 140, 230', '153, 102, 217', '255, 128, 26'];
        snapshot.resource_charts.forEach((data, index) => {
            const group = resources.children[index];
            group.querySelector('.percentage').textContent = data.text;
            const canvas = group.querySelector('canvas');
            const context = canvas.getContext('2d');
            const { width, height } = canvas;
            context.clearRect(0, 0, width, height);
            context.fillStyle = `rgba(${colors[index]}, .08)`;
            context.fillRect(0, 0, width, height);
            for (const segment of data.segments) {
                const points = segment.map(([x, y]) => [2 + x * (width - 4), 2 + y * (height - 4)]);
                context.beginPath();
                context.moveTo(points[0][0], height - 2);
                for (const point of points) context.lineTo(...point);
                context.lineTo(points[points.length - 1][0], height - 2);
                context.closePath();
                context.fillStyle = `rgba(${colors[index]}, .3)`;
                context.fill();
                context.beginPath();
                context.moveTo(...points[0]);
                for (const point of points.slice(1)) context.lineTo(...point);
                context.strokeStyle = `rgb(${colors[index]})`;
                context.lineWidth = 2;
                context.stroke();
            }
        });
    }

    async function render(snapshot) {
        state = { scope: snapshot.scope, selected: snapshot.selected };
        persist();
        runStatus(snapshot.runs);
        tabs(viewers, [{ id: 'all', label: 'All', active: true }, ...snapshot.entries.map(entry =>
            ({ id: entry.id, label: entry.label, active: entry.locked }))],
            state.selected, selected => select(state.scope, selected));
        resourceCharts(snapshot);
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
