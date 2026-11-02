/* Watch feeds stay view only; shared launcher sessions accept guarded chat. */
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
    const sshVisible = new Set();
    const sections = new Map();
    const saved = vscode.getState();
    let state = { scope: 'all', selected: saved?.selected || 'all' };
    let tileLayout = ['auto', 'vertical', 'horizontal'].includes(saved?.tileLayout) ? saved.tileLayout : 'auto';
    let split = Number.isFinite(saved?.split) ? saved.split : 30;
    let pending = Promise.resolve();
    const resourceSamples = new Map();
    let sessionRoot = '';
    const actions = new Map();

    function countdown(node) {
        const remaining = Math.max(0, Math.ceil(Number(node.dataset.deadline) - Date.now() / 1000));
        node.textContent = `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`;
    }
    setInterval(() => runs.querySelectorAll('[data-deadline]').forEach(countdown), 1000);

    function runView(root, view) {
        if (sessionRoot === root || view === 'session') {
            sessionRoot = view === 'session' ? root : '';
            vscode.postMessage({ type: 'sessionView', root: sessionRoot });
        }
        for (const [id, section] of sections) {
            if (id === root) section.view = view;
            else if (view === 'session' && section.view === 'session') section.view = 'status';
            section.content.hidden = section.view !== 'status';
            section.launcher.hidden = section.view !== 'launcher';
            section.errorStatus.hidden = section.view !== 'error';
            section.session.hidden = section.view !== 'session';
            sessionHeading(section);
        }
    }

    function sessionHeading(section) {
        const entry = section.entry;
        const signature = JSON.stringify([entry.label, entry.session, entry.session_active,
            entry.session_number, entry.session_inactive, section.view, section.collapsed]);
        if (section.headingSignature === signature) return;
        section.headingSignature = signature;
        section.tabObserver?.disconnect();
        section.heading.replaceChildren();
        const titlebar = element('span', 'run-titlebar', section.heading);
        const title = element('span', 'run-label', titlebar);
        title.textContent = entry.label;
        title.title = entry.label;
        const controls = element('span', 'run-controls', titlebar);
        const collapse = element('button', 'run-copy', controls);
        collapse.type = 'button';
        const collapseIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        collapseIcon.setAttribute('viewBox', '0 0 20 20');
        collapseIcon.setAttribute('aria-hidden', 'true');
        const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        collapseIcon.append(chevron);
        collapse.append(collapseIcon);
        section.body.classList.toggle('collapsed', Boolean(section.collapsed));
        collapse.title = section.collapsed ? 'Expand' : 'Collapse';
        collapse.setAttribute('aria-label', collapse.title);
        collapse.setAttribute('aria-expanded', String(!section.collapsed));
        chevron.setAttribute('d', section.collapsed ? 'M5 7l5 5 5-5' : 'M5 12l5-5 5 5');
        collapse.addEventListener('click', () => {
            section.collapsed = !section.collapsed;
            sessionHeading(section);
            runDividers();
        });
        const copy = element('button', 'run-copy', controls);
        copy.type = 'button';
        copy.title = 'Copy current tab content';
        copy.setAttribute('aria-label', copy.title);
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 20 20');
        icon.setAttribute('aria-hidden', 'true');
        const shape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        shape.setAttribute('d', 'M7 7h10v10H7z M4 13H3V3h10v1');
        icon.append(shape);
        copy.append(icon);
        copy.addEventListener('click', () => {
            const body = { status: section.content, launcher: section.launcher,
                error: section.errorStatus, session: section.output }[section.view];
            vscode.postMessage({ type: 'copy', root: entry.id, text: body.innerText });
        });
        const links = element('span', 'run-links', section.heading);
        for (const [view, label] of [['status', 'Status'], ['launcher', 'Launcher'], ['error', 'Error'], ['session', 'Session']]) {
            const text = view === 'session' && entry.session_number ? `Session ${entry.session_number}` : label;
            const item = link(links, text, () => runView(entry.id, view));
            item.classList.add('run-tab');
            if (view === 'session' && (entry.session_inactive ?? !entry.session_active)) item.classList.add('session-inactive');
            if (section.view === view) item.setAttribute('aria-current', 'page');
        }
        section.tabObserver = new ResizeObserver(() => {
            if (!links.isConnected) return;
            // Measure compact tabs first so widening always restores a single row.
            links.classList.remove('wrapped');
            const widths = Array.from(links.children, tab => tab.getBoundingClientRect().width);
            const gap = parseFloat(getComputedStyle(links).columnGap) || 0;
            const singleRowWidth = widths.reduce((sum, width) => sum + width, 0) + gap * (widths.length - 1);
            // Keep equal widths from increasing the heading's preferred width.
            links.style.maxWidth = `${singleRowWidth}px`;
            links.style.setProperty('--run-tab-width', `${Math.max(...widths)}px`);
            links.classList.toggle('wrapped', singleRowWidth > links.getBoundingClientRect().width + 0.5);
        });
        section.tabObserver.observe(links);
    }

    function link(parent, text, click) {
        const node = element('a', 'session-link', parent);
        node.href = '#';
        node.textContent = text;
        node.addEventListener('click', event => { event.preventDefault(); click(); });
        return node;
    }

    function runSpan(parent, part) {
        const linked = typeof part.link === 'string';
        const span = linked ? link(parent, part.text,
            () => vscode.postMessage({ type: 'openRunFile', uri: part.link })) :
            element('span', '', parent);
        span.textContent = part.text;
        if (part.color) span.style.color = part.color;
        if (part.bold) span.style.fontWeight = 'bold';
        return span;
    }

    function sessionAction(section, kind) {
        if ((section.pending && kind !== 'extend') || !section.entry.session || actions.size >= 16) return;
        if (kind === 'send' && (section.input.disabled || !section.input.value.trim())) return;
        const id = crypto.randomUUID();
        const text = kind === 'send' ? section.input.value :
            kind === 'extend' ? section.entry.session_question : '';
        if (kind !== 'extend') section.pending = id;
        actions.set(id, { section, kind, text });
        section.error.textContent = '';
        vscode.postMessage({ type: 'sessionAction', id, kind, root: section.entry.id,
            session: section.entry.session, question: section.entry.session_question || '', text });
    }

    function sessionPanel(body) {
        const session = element('div', 'session-view', body);
        session.hidden = true;
        const output = element('pre', 'run-status session-output', session);
        const composer = element('div', 'session-composer', session);
        const working = element('div', '', composer);
        const prompt = element('div', 'session-prompt', composer);
        const marker = element('span', 'session-prompt-marker', prompt);
        marker.textContent = '›';
        marker.setAttribute('aria-hidden', 'true');
        const input = element('textarea', '', prompt);
        input.rows = 1;
        input.setAttribute('aria-label', 'Session chat');
        const fitInput = () => {
            if (!input.clientWidth) return;
            input.style.height = 'auto';
            input.style.height = `${input.scrollHeight + input.offsetHeight - input.clientHeight}px`;
        };
        input.addEventListener('input', fitInput);
        let inputWidth = 0;
        const inputObserver = new ResizeObserver(([entry]) => {
            if (entry.contentRect.width === inputWidth) return;
            inputWidth = entry.contentRect.width;
            fitInput();
        });
        inputObserver.observe(input);
        const error = element('div', 'session-error', body);
        error.setAttribute('role', 'status');
        const footer = element('div', 'session-footer', session);
        const model = element('span', 'session-model', footer);
        const simplified = element('label', 'session-simplified', footer);
        simplified.append('Simplified ');
        const section = { session, output, composer, working, input, error, model, fitInput, inputObserver };
        section.toggle = element('button', 'session-toggle', simplified);
        section.toggle.type = 'button';
        section.toggle.setAttribute('role', 'switch');
        section.toggle.setAttribute('aria-label', 'Simplified');
        section.toggle.setAttribute('aria-checked', 'true');
        section.toggle.disabled = true;
        section.toggle.addEventListener('click', () => sessionAction(section, 'simplified'));
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter' && !event.isComposing && !event.shiftKey && !event.altKey) {
                event.preventDefault();
                sessionAction(section, 'send');
            }
        });
        return section;
    }

    function sessionRows(section, view) {
        const signature = JSON.stringify(view.rows);
        if (signature !== section.outputSignature) {
            const follow = section.output.scrollHeight - section.output.clientHeight - section.output.scrollTop < 24;
            section.output.replaceChildren(...view.rows.map(row => {
                const line = document.createElement('div');
                line.classList.toggle('session-activity', row.some(part => part.compact));
                if (!row.length) line.textContent = '\u00a0';
                for (const part of row) {
                    runSpan(line, part);
                }
                return line;
            }));
            section.outputSignature = signature;
            if (follow) section.output.scrollTop = section.output.scrollHeight;
        }
        section.working.textContent = view.working || '';
        section.working.hidden = !view.working;
        section.model.textContent = view.model;
        section.toggle.setAttribute('aria-checked', String(view.simplified));
        section.toggle.disabled = !section.entry.session || !section.entry.connected;
        section.input.disabled = !view.input_enabled || !section.entry.connected;
    }

    function persist() {
        vscode.setState({ ...state, split, tileLayout });
    }

    function arrangeTiles(value) {
        tileLayout = value;
        grid.dataset.layout = value;
        document.querySelectorAll('#tile-layout button[data-layout]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.layout === value));
        });
        persist();
    }
    document.querySelectorAll('#tile-layout button[data-layout]').forEach(button => {
        button.addEventListener('click', () => arrangeTiles(button.dataset.layout));
    });
    arrangeTiles(tileLayout);

    function resize(value) {
        split = Math.min(90, Math.max(0, value));
        layout.style.gridTemplateColumns = `minmax(min-content, ${split}fr) 6px minmax(0, ${100 - split}fr)`;
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
        const value = { ArrowLeft: split - 2, ArrowRight: split + 2, Home: 0, End: 90 }[event.key];
        if (value === undefined) return;
        event.preventDefault();
        resize(value);
    });
    resize(split);

    function select(scope, selected) {
        if (selected !== 'run-time') {
            grid.querySelector('.run-times')?.remove();
            grid.classList.remove('runtime-body');
        }
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
        const titlebar = element('div', 'tile-titlebar', body);
        const title = element('button', 'title', titlebar);
        title.addEventListener('click', () => select(state.scope, entry.id));
        const screenshot = element('button', 'tile-screenshot', titlebar);
        screenshot.type = 'button';
        screenshot.title = 'Take UI screenshot';
        screenshot.setAttribute('aria-label', `Take UI screenshot: ${entry.label}`);
        screenshot.disabled = true;
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 20 20');
        icon.setAttribute('aria-hidden', 'true');
        const shape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        shape.setAttribute('d', 'M2 6h4l2-3h4l2 3h4v11H2z M13 11a3 3 0 1 1-6 0 3 3 0 1 1 6 0');
        icon.append(shape);
        screenshot.append(icon);
        const heading = element('div', 'heading', body);
        const step = element('div', 'step', body);
        const display = element('div', 'display', body);
        const canvas = element('canvas', 'screen', display);
        canvas.setAttribute('aria-label', entry.kind === 'vm' ? 'VM display, view only' : 'UI worker display, view only');
        canvas.hidden = true;
        screenshot.addEventListener('click', () => {
            if (canvas.hidden || !canvas.width || !canvas.height) return;
            try {
                vscode.postMessage({ type: 'screenshot', png: canvas.toDataURL('image/png') });
            } catch (error) {
                vscode.postMessage({ type: 'screenshotError', error: error.message });
            }
        });
        const waiting = element('p', 'waiting', display);
        waiting.textContent = 'Waiting for display';
        const activity = element('pre', 'activity', body);
        activity.setAttribute('aria-label', 'Filtered VM command output');
        const footer = element('div', 'card-footer', body);
        const status = element('div', 'status', footer);
        let memory;
        if (entry.kind === 'vm') {
            memory = element('span', 'resource vm-memory', footer);
            memory.title = 'Host RAM occupied by the VM process (RSS), in decimal GB. Last minute; scale includes configured guest RAM and QEMU overhead.';
            element('strong', '', memory).textContent = 'Memory:';
            element('span', 'memory-value', memory);
            const graph = element('canvas', 'resource-chart', memory);
            graph.width = 140;
            graph.height = 44;
            graph.setAttribute('aria-hidden', 'true');
            activity.hidden = !sshVisible.has(entry.id);
            const ssh = element('label', 'ssh-control', footer);
            ssh.append('SSH ');
            const toggle = element('button', 'session-toggle', ssh);
            toggle.type = 'button';
            toggle.setAttribute('role', 'switch');
            toggle.setAttribute('aria-label', 'SSH');
            toggle.setAttribute('aria-checked', String(!activity.hidden));
            toggle.addEventListener('click', () => {
                activity.hidden = !activity.hidden;
                toggle.setAttribute('aria-checked', String(!activity.hidden));
                if (activity.hidden) sshVisible.delete(entry.id);
                else {
                    sshVisible.add(entry.id);
                    activity.scrollTop = activity.scrollHeight;
                }
            });
        }
        return { body, title, heading, step, canvas, waiting, activity, status, memory, screenshot };
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
        view.waiting.textContent = 'Waiting for display';
        if (!data) {
            view.canvas.width = view.canvas.height = 0;
            view.screenshot.disabled = true;
            return;
        }
        try {
            const [frame, cursor] = await Promise.all([
                image(data.image), data.cursor ? image(data.cursor.image) : undefined
            ]);
            view.canvas.width = data.width;
            view.canvas.height = data.height;
            const context = view.canvas.getContext('2d', { alpha: false });
            context.drawImage(frame, 0, 0);
            if (cursor) context.drawImage(cursor, data.cursor.x, data.cursor.y);
            view.screenshot.disabled = !view.canvas.width || !view.canvas.height;
        } catch (error) {
            // A corrupt source frame must not discard healthy viewers or run state.
            view.canvas.width = view.canvas.height = 0;
            view.canvas.hidden = true;
            view.screenshot.disabled = true;
            view.waiting.hidden = false;
            view.waiting.textContent = error.message;
        }
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

    function runDividers() {
        let previous;
        for (const body of runs.querySelectorAll('.run')) {
            const section = sections.get(body.dataset.root);
            section.previous = previous;
            section.divider.hidden = !previous;
            const enabled = Boolean(previous);
            section.divider.setAttribute('aria-disabled', String(!enabled));
            section.divider.tabIndex = enabled ? 0 : -1;
            previous = section;
        }
    }

    function runDivider(section) {
        const handle = section.divider;
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-orientation', 'horizontal');
        handle.setAttribute('aria-label', 'Resize launcher panels');
        let drag;
        const resizePair = (previous, top, delta) => {
            if (!delta) return;
            for (const panel of [previous, section]) {
                if (!panel.collapsed) continue;
                panel.collapsed = false;
                sessionHeading(panel);
            }
            const total = previous.body.getBoundingClientRect().height + section.body.getBoundingClientRect().height;
            if (total < 200) return;
            const height = Math.max(100, Math.min(total - 100, top + delta));
            const weight = previous.weight + section.weight;
            previous.weight = weight * height / total;
            section.weight = weight - previous.weight;
            previous.body.style.flexGrow = previous.weight;
            section.body.style.flexGrow = section.weight;
        };
        handle.addEventListener('pointerdown', event => {
            if (event.button !== 0 || handle.getAttribute('aria-disabled') === 'true') return;
            event.preventDefault();
            handle.focus();
            drag = { previous: section.previous, y: event.clientY,
                top: section.previous.body.getBoundingClientRect().height };
            handle.setPointerCapture(event.pointerId);
            document.body.classList.add('resizing-runs');
        });
        handle.addEventListener('pointermove', event => {
            if (!drag || !handle.hasPointerCapture(event.pointerId)) return;
            if (drag.previous !== section.previous) return;
            resizePair(drag.previous, drag.top, event.clientY - drag.y);
        });
        handle.addEventListener('pointerup', event => {
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
        });
        handle.addEventListener('lostpointercapture', () => {
            drag = undefined;
            document.body.classList.remove('resizing-runs');
        });
        handle.addEventListener('keydown', event => {
            if (handle.getAttribute('aria-disabled') === 'true') return;
            const delta = { ArrowUp: -20, ArrowDown: 20 }[event.key];
            if (delta === undefined) return;
            event.preventDefault();
            resizePair(section.previous, section.previous.body.getBoundingClientRect().height,
                delta);
        });
    }

    function runStatus(entries) {
        const ids = new Set(entries.map(entry => entry.id));
        for (const [id, section] of sections) {
            if (!ids.has(id)) {
                section.inputObserver.disconnect();
                section.tabObserver?.disconnect();
                section.body.remove();
                section.divider.remove();
                sections.delete(id);
            }
        }
        if (entries.length) runs.querySelector('.empty')?.remove();
        entries.forEach((entry, index) => {
            let section = sections.get(entry.id);
            if (!section) {
                const body = element('section', 'run', runs);
                body.dataset.root = entry.id;
                const divider = element('div', 'run-divider', runs);
                const heading = element('h2', 'run-heading', body);
                const content = element('pre', 'run-status', body);
                const launcher = element('pre', 'run-status', body);
                launcher.setAttribute('aria-label', 'Launcher terminal output');
                const errorStatus = element('pre', 'run-status', body);
                errorStatus.setAttribute('aria-label', 'Last Error and Status');
                section = Object.assign(sessionPanel(body), { body, divider, heading, content, launcher, errorStatus,
                    view: 'status', weight: 1 });
                sections.set(entry.id, section);
                runDivider(section);
            }
            if (runs.children[index * 2] !== section.divider) runs.insertBefore(section.divider, runs.children[index * 2] || null);
            if (runs.children[index * 2 + 1] !== section.body) runs.insertBefore(section.body, runs.children[index * 2 + 1] || null);
            // Apply lifecycle defaults once; live refreshes preserve manual resizing/toggles.
            if (!section.entry || section.entry.run !== entry.run
                    || Boolean(section.entry.active) !== Boolean(entry.active)) {
                section.collapsed = !entry.active;
            }
            section.entry = entry;
            if (!entry.connected) {
                section.input.disabled = true;
                section.toggle.disabled = true;
            }
            sessionHeading(section);
            section.heading.classList.toggle('failed', entry.status === 'failed');
            section.content.hidden = section.view !== 'status';
            section.launcher.hidden = section.view !== 'launcher';
            section.errorStatus.hidden = section.view !== 'error';
            section.session.hidden = section.view !== 'session';
            if (entry.session_view) sessionRows(section, entry.session_view);
            else if (!entry.session) {
                section.output.textContent = 'No active session';
                section.outputSignature = undefined;
                section.input.disabled = true;
                section.toggle.disabled = true;
                section.working.textContent = section.model.textContent = '';
            }
            if (section.launcherText !== entry.launcher_output) {
                const follow = section.launcher.scrollHeight - section.launcher.clientHeight - section.launcher.scrollTop < 24;
                section.launcherText = entry.launcher_output;
                section.launcher.textContent = terminal(entry.launcher_output || 'Waiting for launcher output…');
                if (follow) section.launcher.scrollTop = section.launcher.scrollHeight;
            }
            // The adapter owns retained state, including late final status updates.
            const errorSignature = JSON.stringify(entry.error_rows);
            if (section.errorSignature !== errorSignature) {
                section.errorSignature = errorSignature;
                section.errorStatus.replaceChildren(...(entry.error_rows || []).map(row => {
                    const line = document.createElement('div');
                    if (!row.length) line.textContent = '\u00a0';
                    for (const part of row) {
                        runSpan(line, part);
                    }
                    return line;
                }));
                if (!section.errorStatus.childNodes.length) section.errorStatus.textContent = 'Waiting for run status…';
            }
            const signature = JSON.stringify([entry.rows, entry.active, entry.session,
                entry.session_waiting, entry.session_deadline]);
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
                    const span = runSpan(line, part);
                    span.classList.toggle('waiting-input', Boolean(part.waiting));
                    if (entry.session_waiting && part.waiting) {
                        if (Number.isFinite(entry.session_deadline)) {
                            line.append(' ');
                            const timer = element('span', '', line);
                            timer.dataset.deadline = String(entry.session_deadline);
                            countdown(timer);
                            line.append(' ');
                            const extend = link(line, '+10m', () => sessionAction(section, 'extend'));
                            extend.title = 'Add 10 minutes';
                            extend.setAttribute('aria-label', 'Add 10 minutes to answer');
                        } else {
                            line.append(' (no timeout)');
                        }
                    }
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
        runDividers();
    }

    function resourceCharts(snapshot) {
        const ids = new Set(snapshot.hosts.map(host => host.id));
        for (const node of Array.from(resources.children)) {
            if (!ids.has(node.dataset.source)) { node.remove(); resourceSamples.delete(node.dataset.source); }
        }
        for (const host of snapshot.hosts) {
            let row = Array.from(resources.children).find(node => node.dataset.source === host.id);
            if (!row) {
                row = element('span', 'host-resources', resources);
                row.dataset.source = host.id;
                element('span', 'host-status', row);
            }
            const signature = JSON.stringify([host.sample, host.status]);
            if (resourceSamples.get(host.id) === signature) continue;
            resourceSamples.set(host.id, signature);
            const status = row.querySelector('.host-status');
            status.textContent = host.show_label || !host.connected ? `${host.label}: ${host.status}` : '';
            status.title = `${host.label}: ${host.status}`;
            status.classList.toggle('disconnected', !host.connected);
            row.setAttribute('aria-label', `${host.label}: ${host.status}. ${host.resources}`);
            const groups = Array.from(row.querySelectorAll('.resource'));
            const colors = ['52, 140, 230', '153, 102, 217', '255, 128, 26'];
            host.charts.forEach((data, index) => {
                const name = data.label;
                let group = groups[index];
                if (!group) {
                    group = element('span', 'resource', row);
                    element('strong', '', group);
                    element('span', 'percentage', group);
                    const canvas = element('canvas', 'resource-chart', group);
                    canvas.width = 140;
                    canvas.height = 44;
                    canvas.setAttribute('aria-hidden', 'true');
                }
                group.title = `${name}: last minute, fixed 0–100% scale. History stays in memory only.` +
                    (name === 'Disk' ? ' Busiest physical disk (iostat %util); NVMe busy time is not throughput saturation.' : '');
                group.querySelector('strong').textContent = `${name}:`;
                group.querySelector('.percentage').textContent = data.text;
                drawChart(group.querySelector('canvas'), data.segments, colors[index % colors.length]);
            });
            for (const group of groups.slice(host.charts.length)) group.remove();
        }
    }

    function drawChart(canvas, segments, color) {
            const context = canvas.getContext('2d');
            const { width, height } = canvas;
            context.clearRect(0, 0, width, height);
            context.fillStyle = `rgba(${color}, .08)`;
            context.fillRect(0, 0, width, height);
            for (const segment of segments) {
                const points = segment.map(([x, y]) => [2 + x * (width - 4), 2 + y * (height - 4)]);
                context.beginPath();
                context.moveTo(points[0][0], height - 2);
                for (const point of points) context.lineTo(...point);
                context.lineTo(points[points.length - 1][0], height - 2);
                context.closePath();
                context.fillStyle = `rgba(${color}, .3)`;
                context.fill();
                context.beginPath();
                context.moveTo(...points[0]);
                for (const point of points.slice(1)) context.lineTo(...point);
                context.strokeStyle = `rgb(${color})`;
                context.lineWidth = 2;
                context.stroke();
            }
    }

    function runTimes(rows) {
        grid.classList.add('runtime-body');
        grid.querySelector('.empty')?.remove();
        const signature = JSON.stringify(rows);
        let table = grid.querySelector('.run-times');
        if (table?.dataset.signature === signature) return;
        table?.remove();
        table = document.createElement('table');
        table.className = 'run-times';
        table.dataset.signature = signature;
        const heading = table.createTHead().insertRow();
        for (const label of ['Case ID / Title | Recording', 'Category', 'VM name', 'Run Time', 'Description']) {
            const th = document.createElement('th');
            th.textContent = label;
            heading.append(th);
        }
        const body = table.createTBody();
        const link = (cell, text, uri) => {
            const a = document.createElement('a');
            a.href = '#';
            a.textContent = text;
            a.onclick = event => {
                event.preventDefault();
                vscode.postMessage({ type: 'openRunFile', uri });
            };
            cell.append(a);
            return a;
        };
        for (const row of rows) {
            const tr = body.insertRow();
            const title = tr.insertCell();
            link(title, Number.isInteger(row.id) ? `${row.id}: ${row.title}` : row.title, row.case_link);
            if (row.recording) {
                title.append(' | ');
                const recording = link(title, '▶', row.recording);
                recording.title = 'Open recording';
                recording.setAttribute('aria-label', 'Open recording');
            }
            tr.insertCell().textContent = row.category === 'e2e' ? 'E2E' : row.category;
            tr.insertCell().textContent = row.vm;
            tr.insertCell().textContent = `${Math.floor(row.seconds / 60 + .5)}m`;
            const description = tr.insertCell();
            const summary = document.createElement('div');
            summary.textContent = row.description;
            description.append(summary);
            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'description-toggle';
            toggle.title = 'Expand description';
            toggle.setAttribute('aria-label', toggle.title);
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('viewBox', '0 0 20 20');
            icon.setAttribute('aria-hidden', 'true');
            const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            chevron.setAttribute('d', 'M5 7l5 5 5-5');
            icon.append(chevron);
            toggle.append(icon);
            const text = document.createElement('div');
            text.hidden = true;
            const stepsLabel = document.createElement('p');
            stepsLabel.textContent = 'Steps:';
            const steps = document.createElement('ul');
            for (const step of row.steps || []) {
                const item = document.createElement('li');
                item.textContent = step;
                steps.append(item);
            }
            if (row.steps?.length) text.append(stepsLabel, steps);
            if (row.expected) {
                const expectedLabel = document.createElement('p');
                expectedLabel.textContent = 'Expected:';
                const expected = document.createElement('ul');
                const item = document.createElement('li');
                item.textContent = row.expected;
                expected.append(item);
                text.append(expectedLabel, expected);
            }
            toggle.onclick = () => {
                text.hidden = !text.hidden;
                toggle.title = text.hidden ? 'Expand description' : 'Collapse description';
                toggle.setAttribute('aria-label', toggle.title);
                chevron.setAttribute('d', text.hidden ? 'M5 7l5 5 5-5' : 'M5 12l5-5 5 5');
                toggle.setAttribute('aria-expanded', String(!text.hidden));
            };
            toggle.setAttribute('aria-expanded', 'false');
            if (row.steps?.length || row.expected) {
                summary.append(' ', toggle);
                description.append(text);
            }
        }
        grid.append(table);
    }

    async function render(snapshot) {
        for (const result of snapshot.session_results || []) {
            if (!actions.has(result.id)) continue;
            const { section, kind, text } = actions.get(result.id);
            actions.delete(result.id);
            if (kind !== 'extend') section.pending = undefined;
            if (result.ok && kind === 'send' && section.input.value === text) {
                section.input.value = '';
                section.fitInput();
            }
            if (!result.ok) section.error.textContent = result.error;
        }
        state = { scope: snapshot.scope, selected: snapshot.selected };
        persist();
        runStatus(snapshot.runs);
        tabs(viewers, [{ id: 'all', label: 'All', active: true },
            { id: 'run-time', label: 'Run Time', active: true }, ...snapshot.entries.map(entry =>
            ({ id: entry.id, label: entry.label, active: entry.locked }))],
            state.selected, selected => select(state.scope, selected));
        resourceCharts(snapshot);
        const shown = snapshot.entries.filter(entry => state.selected === 'all' ? entry.active : entry.id === state.selected);
        const ids = new Set(shown.map(entry => entry.id));
        for (const [id, view] of cards) {
            if (!ids.has(id)) { view.body.remove(); cards.delete(id); }
        }
        if (state.selected === 'run-time') {
            runTimes(snapshot.run_times || []);
            return;
        }
        grid.querySelector('.run-times')?.remove();
        grid.classList.remove('runtime-body');
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
            if (view.memory && view.memorySample !== entry.memory?.sample) {
                view.memorySample = entry.memory?.sample;
                view.memory.querySelector('.memory-value').textContent = entry.memory?.text || '—';
                drawChart(view.memory.querySelector('canvas'), entry.memory?.segments || [], '153, 102, 217');
            }
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
                .finally(() => vscode.postMessage({ type: 'rendered', id: event.data.id }));
        } else if (event.data.type === 'error') {
            for (const { section } of actions.values()) {
                section.pending = undefined;
                section.error.textContent = event.data.message;
            }
            actions.clear();
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
