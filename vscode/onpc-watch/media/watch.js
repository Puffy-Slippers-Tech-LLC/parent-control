/* Watch feeds stay view only; shared launcher sessions accept guarded chat. */
'use strict';

(() => {
    const vscode = acquireVsCodeApi();
    initializeWatchErrors(vscode);
    const reportError = error => vscode.postMessage({ type: 'watchError',
        error: error instanceof Error ? error.stack || error.message : String(error) });
    window.addEventListener('error', event => {
        // The browser defers undelivered resize observations to another frame;
        // this notification is not a failed viewer or a thrown callback error.
        if (!event.error && ['ResizeObserver loop completed with undelivered notifications.',
            'ResizeObserver loop limit exceeded'].includes(event.message)) return;
        reportError(event.error || event.message);
    });
    window.addEventListener('unhandledrejection', event => reportError(event.reason));
    const grid = document.getElementById('grid');
    const viewers = document.getElementById('viewers');
    const resources = document.getElementById('resources');
    const servers = document.getElementById('servers');
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
    const actions = new Map();
    const expandedRunTimes = new Set();
    const selectedRunTimes = new Set();
    const cloudPath = 'M6 15a4 4 0 1 1 .2-8A5 5 0 0 1 15.5 8H16a3.5 3.5 0 0 1 0 7Z';
    const cloudOfflinePath = `${cloudPath} M2 2l16 16`;

    function countdown(node) {
        const remaining = Math.max(0, Math.ceil(Number(node.dataset.deadline) - Date.now() / 1000));
        node.textContent = `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`;
    }
    setInterval(() => runs.querySelectorAll('[data-deadline]').forEach(countdown), 1000);

    function runView(root, view) {
        const section = sections.get(root);
        if (!section) return;
        section.view = view;
        section.content.hidden = view !== 'status';
        section.launcher.hidden = view !== 'launcher';
        section.errorStatus.hidden = view !== 'error';
        section.session.hidden = view !== 'session';
        sessionHeading(section);
        runMinimum(section);
        if (view === 'status' && section.followStatus) section.history.scrollTop = section.history.scrollHeight;
        vscode.postMessage({ type: 'sessionView', roots: [...sections]
            .filter(([, section]) => section.view === 'session').map(([id]) => id) });
    }

    function tabLabel(entry, view) {
        return view === 'session' && entry.session_number ? `Session ${entry.session_number}` :
            view === 'session' ? 'Session' : 'Launcher';
    }

    function sessionHeading(section) {
        const entry = section.entry;
        const signature = JSON.stringify([entry.run, entry.server, entry.transport, entry.label, entry.status, entry.session, entry.session_active,
            entry.session_number, entry.session_inactive, entry.launcher_controls, entry.launcher_command, entry.launcher_action_command, entry.launcher_reload_command, entry.active, section.view, section.collapsed]);
        if (section.headingSignature === signature) return;
        section.headingSignature = signature;
        section.tabObserver?.disconnect();
        section.heading.replaceChildren();
        const titlebar = element('span', 'run-titlebar', section.heading);
        const labels = element('span', 'run-label', titlebar);
        const server = element('span', 'run-server', labels);
        const serverIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        serverIcon.setAttribute('viewBox', '0 0 20 20');
        serverIcon.setAttribute('aria-hidden', 'true');
        const serverShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        serverIcon.classList.toggle('online-cloud', entry.transport === 'ssh');
        serverShape.setAttribute('d', entry.transport === 'ssh' ? cloudPath :
            'M3 3h14v6H3z M3 11h14v6H3z M6 6h1 M6 14h1');
        serverIcon.append(serverShape);
        server.append(serverIcon);
        element('span', 'run-server-name', server).textContent = entry.server;
        const kind = entry.status === 'Stop Requested' ? 'cancel-stop' : entry.active ? 'stop' : 'resume';
        const button = element('button', 'run-copy run-launcher-action', server);
        button.type = 'button';
        button.dataset.kind = kind;
        button.title = kind === 'cancel-stop' ? 'Cancell stop request' : entry.active ? 'Stop launcher' : 'Resume launcher';
        button.setAttribute('aria-label', button.title);
        if (entry.launcher_action_command) button.title += `\n${entry.launcher_action_command}`;
        button.disabled = !entry.launcher_controls || entry.status === 'Stopping';
        const actionIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        actionIcon.setAttribute('viewBox', '0 0 20 20');
        actionIcon.setAttribute('aria-hidden', 'true');
        const actionShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        actionShape.setAttribute('d', kind === 'cancel-stop' ?
            'M7 4L3 8l4 4 M3 8h9a5 5 0 0 1 0 10' : entry.active ? 'M5 5h10v10H5z' : 'M6 4l10 6-10 6z');
        if (kind === 'stop') actionShape.style.fill = 'currentColor';
        actionIcon.append(actionShape);
        button.append(actionIcon);
        button.addEventListener('click', () => vscode.postMessage({
            type: 'launcherAction', root: entry.id, run: entry.run, kind }));
        const reload = element('button', 'run-copy run-launcher-action', server);
        reload.type = 'button';
        reload.dataset.kind = 'reload';
        reload.title = 'Reload launcher';
        reload.setAttribute('aria-label', reload.title);
        if (entry.launcher_reload_command) reload.title += `\n${entry.launcher_reload_command}`;
        reload.disabled = !entry.launcher_controls || !entry.launcher_reload_command || entry.status === 'Stopping';
        const reloadIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        reloadIcon.setAttribute('viewBox', '0 0 20 20');
        reloadIcon.setAttribute('aria-hidden', 'true');
        const reloadShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        reloadShape.setAttribute('d', 'M16 3v5h-5 M16 8a6 6 0 1 0 0 5');
        reloadIcon.append(reloadShape);
        reload.append(reloadIcon);
        reload.addEventListener('click', () => vscode.postMessage({
            type: 'launcherAction', root: entry.id, run: entry.run, kind: 'reload' }));
        labels.title = `${entry.server}\n${entry.label}`;
        const title = entry.launcher_command ? link(labels, '', () =>
            vscode.postMessage({ type: 'copy', root: entry.id, text: entry.launcher_command,
                command: true })) :
            element('span', '', labels);
        title.classList.add('run-launcher-label');
        title.textContent = entry.label;
        if (['Stop Requested', 'Stopping', 'Reload Requested', 'Closing Task'].includes(entry.status)) {
            const suffix = ` (${entry.status})`;
            if (entry.label.endsWith(suffix)) {
                title.textContent = entry.label.slice(0, -suffix.length) + ' (';
                element('span', entry.status === 'Closing Task' ? 'closing-task' : 'stop-requested', title).textContent = entry.status;
                title.append(')');
            }
        }
        title.title = entry.launcher_command ? `Copy command: ${entry.launcher_command}` : entry.label;
        labels.classList.toggle('finished', entry.status === 'finished');
        const controls = element('span', 'run-controls', server);
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
            const activity = section.view === 'session' && !section.activity.hidden ?
                `\n${section.activity.innerText}` : '';
            vscode.postMessage({ type: 'copy', root: entry.id, text: body.innerText + activity });
        });
        controls.append(copy, collapse);
        const links = element('span', 'run-links', section.heading);
        for (const [view, label] of [['status', 'Status'], ['launcher', 'Launcher'], ['error', 'Error'], ['session', 'Session']]) {
            const text = ['session', 'launcher'].includes(view) ? tabLabel(entry, view) : label;
            const item = link(links, text, () => runView(entry.id, view));
            item.classList.add('run-tab');
            if (view === 'session' && (entry.session_inactive ?? !entry.session_active)) item.classList.add('session-inactive');
            if (section.view === view) item.setAttribute('aria-current', 'page');
        }
        section.tabObserver = new ResizeObserver(() => requestAnimationFrame(() => {
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
        }));
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
        const activity = element('pre', 'session-activity', session);
        activity.hidden = true;
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
            requestAnimationFrame(() => { if (input.isConnected) fitInput(); });
        });
        inputObserver.observe(input);
        const error = element('div', 'session-error', body);
        error.setAttribute('role', 'status');
        const footer = element('div', 'session-footer', session);
        const model = element('span', 'session-model', footer);
        const simplified = element('label', 'session-simplified', footer);
        simplified.append('Simplified ');
        const section = { session, output, activity, composer, working, input, error, model, fitInput, inputObserver };
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

    function transcriptRows(output, rows) {
        // Streaming usually changes only the final row. Both transcript views
        // share this renderer, including blank lines, links and styled spans.
        if (!output.children.length) output.textContent = '';
        rows.forEach((row, index) => {
            const signature = JSON.stringify(row);
            const previous = output.children[index];
            if (previous?.rowSignature === signature) return;
            const line = document.createElement('div');
            line.rowSignature = signature;
            if (!row.length) line.textContent = '\u00a0';
            for (const part of row) runSpan(line, part);
            if (previous) previous.replaceWith(line);
            else output.append(line);
        });
        while (output.children.length > rows.length) output.lastElementChild.remove();
        if (!rows.length) output.textContent = '';
    }

    function launcherRows(output, entry, latest = false) {
        let rows = entry.launcher_output && entry.launcher_rows ||
            terminal(entry.launcher_output || 'Waiting for launcher output…').split('\n')
                .map(text => [{ text }]);
        if (latest) {
            let end = rows.length;
            const blank = row => row.every(part => !terminal(part.text).trim());
            while (end && blank(rows[end - 1])) end--;
            let start = end - 1;
            while (start > 0 && !blank(rows[start - 1])) start--;
            rows = rows.slice(Math.max(0, start), end);
        }
        output.replaceChildren();
        rows.forEach((row, index) => {
            if (index) output.appendChild(document.createTextNode('\n'));
            for (const part of row) runSpan(output, { ...part, text: terminal(part.text) });
        });
    }

    function latestOutput(section) {
        const entry = section.entry;
        const session = entry.session && !(entry.session_inactive ?? !entry.session_active);
        const label = tabLabel(entry, session ? 'session' : 'launcher');
        section.latestLabel.textContent = label;
        section.latest.setAttribute('aria-label', label);
        const rows = session ? entry.session_preview : entry.launcher_rows;
        const signature = JSON.stringify([entry.run, entry.session, Boolean(session), rows,
            session ? null : entry.launcher_output]);
        if (section.latestSignature === signature) return;
        section.latestSignature = signature;
        const source = JSON.stringify([entry.run, entry.session, Boolean(session)]);
        const previousText = section.latestText || '';
        const scrollTop = section.latest.scrollTop;
        if (source !== section.latestSource) section.latest.replaceChildren();
        if (session) {
            transcriptRows(section.latest, rows || []);
            if (!rows?.length) section.latest.textContent = 'Waiting for session output…';
        } else launcherRows(section.latest, entry, true);
        const text = section.latest.textContent.trimEnd();
        // Appending streamed text is still the same output. Keep the reader's
        // position; a replacement message or source starts at its first line.
        section.latest.scrollTop = source === section.latestSource && previousText &&
            text.startsWith(previousText) ? scrollTop : 0;
        section.latestSource = source;
        section.latestText = text;
    }

    function sessionRows(section, view) {
        if (view.rows !== section.outputRows || view.simplified !== section.outputSimplified) {
            const follow = section.output.scrollHeight - section.output.clientHeight - section.output.scrollTop < 24;
            const rows = [];
            let latest = null;
            for (const row of view.rows) {
                if (view.simplified && row.some(part => part.compact)) {
                    latest = row;
                    while (rows.length && rows[rows.length - 1].every(part => !part.text.trim())) rows.pop();
                } else {
                    rows.push(row);
                }
            }
            const activitySignature = JSON.stringify(latest);
            if (section.activitySignature !== activitySignature) {
                section.activitySignature = activitySignature;
                section.activity.replaceChildren();
                section.activity.hidden = !latest;
                for (const part of latest || []) runSpan(section.activity, part);
            }
            transcriptRows(section.output, rows);
            section.outputRows = view.rows;
            section.outputSimplified = view.simplified;
            if (follow) section.output.scrollTop = section.output.scrollHeight;
        }
        if (section.working.textContent !== (view.working || '')) section.working.textContent = view.working || '';
        section.working.hidden = !view.working;
        if (section.model.textContent !== view.model) section.model.textContent = view.model;
        section.toggle.setAttribute('aria-checked', String(view.simplified));
        section.toggle.disabled = !section.entry.session || !section.entry.connected || Boolean(view.unavailable);
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
            view.frame = undefined;
            view.frameUrl = undefined;
            view.canvas.width = view.canvas.height = 0;
            view.screenshot.disabled = true;
            return;
        }
        try {
            const desktop = data.image === undefined || data.image === view.frameUrl ?
                view.frame : await image(data.image);
            if (!desktop) throw new Error('Watch desktop frame unavailable');
            const [frame, cursor] = await Promise.all([
                desktop, data.cursor ? image(data.cursor.image) : undefined
            ]);
            view.frame = frame;
            view.frameUrl = data.image ?? view.frameUrl;
            // Assigning either dimension resets the backing buffer and context.
            if (view.canvas.width !== data.width) view.canvas.width = data.width;
            if (view.canvas.height !== data.height) view.canvas.height = data.height;
            const context = view.canvas.getContext('2d', { alpha: false });
            context.clearRect(0, 0, data.width, data.height);
            context.drawImage(frame, 0, 0);
            if (cursor) context.drawImage(cursor, data.cursor.x, data.cursor.y);
            view.screenshot.disabled = !view.canvas.width || !view.canvas.height;
        } catch (error) {
            view.frame = view.frameUrl = undefined;
            // A corrupt source frame must not discard healthy viewers or run state.
            view.canvas.width = view.canvas.height = 0;
            view.canvas.hidden = true;
            view.screenshot.disabled = true;
            view.waiting.hidden = false;
            view.waiting.textContent = error.message;
            reportError(error);
        }
    }

    function terminal(text) {
        // Only transport-filtered output is displayed. Render it as text, never HTML.
        return text.replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
            .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '').replace(/\r\n?/g, '\n')
            .replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '');
    }

    function message(text) {
        for (const view of cards.values()) void screen(view, null);
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

    function runMinimum(section) {
        const minimum = section.view === 'status' ? section.heading.offsetHeight +
            section.summary.offsetHeight + section.preview.offsetHeight +
            parseFloat(getComputedStyle(section.history).minHeight) : 100;
        section.minimum = Math.max(100, minimum);
        section.body.style.minHeight = `${section.minimum}px`;
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
                runMinimum(panel);
            }
            const total = previous.body.getBoundingClientRect().height + section.body.getBoundingClientRect().height;
            if (total < previous.minimum + section.minimum) return;
            const height = Math.max(previous.minimum, Math.min(total - section.minimum, top + delta));
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
                section.statusObserver.disconnect();
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
                const content = element('div', 'run-status-view', body);
                const summary = element('pre', 'run-status run-summary', content);
                const history = element('pre', 'run-status run-history', content);
                const preview = element('div', 'run-latest', content);
                const latestLabel = element('h3', 'run-latest-label', preview);
                const latest = element('pre', 'run-status', preview);
                latest.tabIndex = 0;
                const launcher = element('pre', 'run-status', body);
                launcher.setAttribute('aria-label', 'Launcher terminal output');
                const errorStatus = element('pre', 'run-status', body);
                errorStatus.setAttribute('aria-label', 'Last Error and Status');
                section = Object.assign(sessionPanel(body), { body, divider, heading, content, summary, history,
                    preview, latestLabel, latest, launcher, errorStatus,
                    view: 'status', weight: 1, followStatus: true });
                const panel = section;
                body.addEventListener('click', event => {
                    const selected = !heading.contains(event.target) || Boolean(event.target.closest('a, button')) ||
                        !body.classList.contains('selected');
                    for (const other of sections.values()) {
                        other.body.classList.toggle('selected', other === panel && selected);
                    }
                }, true);
                history.addEventListener('scroll', () => {
                    if (history.clientHeight) panel.followStatus =
                        history.scrollHeight - history.clientHeight - history.scrollTop < 24;
                });
                panel.statusObserver = new ResizeObserver(() => {
                    runMinimum(panel);
                    if (panel.followStatus) history.scrollTop = history.scrollHeight;
                });
                panel.statusObserver.observe(history);
                panel.statusObserver.observe(heading);
                panel.statusObserver.observe(summary);
                panel.statusObserver.observe(preview);
                sections.set(entry.id, section);
                runDivider(section);
            }
            const previous = section.entry;
            if (previous && previous.run === entry.run && previous.session === entry.session) {
                for (const field of ['rows', 'error_rows', 'launcher_output', 'launcher_rows', 'session_preview']) {
                    if (!Object.hasOwn(entry, field) && Object.hasOwn(previous, field)) entry[field] = previous[field];
                }
                if (entry.session_view && previous.session_view && !Object.hasOwn(entry.session_view, 'rows')) {
                    entry.session_view.rows = previous.session_view.rows;
                }
            }
            if (runs.children[index * 2] !== section.divider) runs.insertBefore(section.divider, runs.children[index * 2] || null);
            if (runs.children[index * 2 + 1] !== section.body) runs.insertBefore(section.body, runs.children[index * 2 + 1] || null);
            // Apply lifecycle defaults once; live refreshes preserve manual resizing/toggles.
            if (!section.entry || section.entry.run !== entry.run
                    || Boolean(section.entry.active) !== Boolean(entry.active)) {
                section.collapsed = !entry.active;
            }
            section.entry = entry;
            if (!previous || previous.run !== entry.run) section.followStatus = true;
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
                section.activity.replaceChildren();
                section.activity.hidden = true;
                section.activitySignature = undefined;
                section.outputRows = undefined;
                section.input.disabled = true;
                section.toggle.disabled = true;
                section.working.textContent = section.model.textContent = '';
            }
            if (section.launcherText !== entry.launcher_output || section.launcherRows !== entry.launcher_rows) {
                const follow = section.launcher.scrollHeight - section.launcher.clientHeight - section.launcher.scrollTop < 24;
                section.launcherText = entry.launcher_output;
                section.launcherRows = entry.launcher_rows;
                launcherRows(section.launcher, entry);
                if (follow) section.launcher.scrollTop = section.launcher.scrollHeight;
            }
            latestOutput(section);
            // The adapter owns retained state, including late final status updates.
            if (section.errorRows !== entry.error_rows) {
                section.errorRows = entry.error_rows;
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
            const signature = JSON.stringify([entry.active, entry.session,
                entry.session_waiting, entry.session_deadline]);
            if (section.statusRows === entry.rows && section.signature === signature) return;
            section.signature = signature;
            section.statusRows = entry.rows;
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
            // Execution-plan totals precede the first divider; ordinary runner
            // status has no fixed summary and keeps all rows in the history.
            const summaryEnd = rows.findIndex(row => row.tagName === 'HR');
            const hasSummary = summaryEnd > 0 && entry.rows[0].some(part => part.text.startsWith('Total Tasks:'));
            if (hasSummary) {
                const summary = rows[0];
                for (const row of rows.slice(1, summaryEnd)) {
                    if (!row.textContent.trim()) continue;
                    summary.append(' | ');
                    if (row.textContent.startsWith('Total Duration:')) {
                        summary.append(row.textContent.slice('Total Duration:'.length).trimStart());
                    } else {
                        summary.append(...row.childNodes);
                    }
                }
            }
            section.summary.hidden = !hasSummary;
            section.summary.replaceChildren(...(hasSummary ? [rows[0]] : []));
            section.history.classList.toggle('has-summary', hasSummary);
            section.history.replaceChildren(...(hasSummary ? rows.slice(summaryEnd + 1) : rows));
            if (section.followStatus) section.history.scrollTop = section.history.scrollHeight;
        });
        runDividers();
    }

    function serverStatus(values) {
        const signature = JSON.stringify(values);
        if (servers.dataset.signature === signature) return;
        servers.dataset.signature = signature;
        servers.replaceChildren();
        for (const server of values) {
            const status = element('span', 'server-status', servers);
            status.classList.toggle('connected', server.connected);
            status.title = `${server.label}: ${server.status}`;
            status.setAttribute('aria-label', status.title);
            const iconButton = element('button', 'server-connection', status);
            iconButton.type = 'button';
            iconButton.disabled = !server.failed;
            iconButton.title = status.title;
            iconButton.setAttribute('aria-label', server.failed ?
                `Show connection error for ${server.label}` : status.title);
            iconButton.onclick = () => vscode.postMessage({ type: 'serverError', server: server.id });
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('viewBox', '0 0 20 20');
            icon.setAttribute('aria-hidden', 'true');
            const shape = document.createElementNS(icon.namespaceURI, 'path');
            shape.setAttribute('d', server.connected ? cloudPath : cloudOfflinePath);
            icon.append(shape);
            iconButton.append(icon);
            element('span', '', status).textContent = server.label;
        }
    }

    function layoutResources() {
        const rows = Array.from(resources.children);
        const width = rows.reduce((total, row) => total + row.offsetWidth, 0) + Math.max(0, rows.length - 1) * 16;
        resources.classList.toggle('stacked', width > resources.clientWidth);
    }
    new ResizeObserver(() => requestAnimationFrame(layoutResources)).observe(resources);

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
                const status = element('span', 'host-status', row);
                const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                icon.setAttribute('viewBox', '0 0 20 20');
                icon.setAttribute('aria-hidden', 'true');
                const outline = document.createElementNS(icon.namespaceURI, 'path');
                icon.append(outline);
                status.append(icon);
                element('strong', 'host-name', status);
            }
            const index = snapshot.hosts.indexOf(host);
            if (resources.children[index] !== row) resources.insertBefore(row, resources.children[index] || null);
            const signature = JSON.stringify([host.sample, host.status, host.label, host.transport]);
            if (resourceSamples.get(host.id) === signature) continue;
            resourceSamples.set(host.id, signature);
            const status = row.querySelector('.host-status');
            status.querySelector('path').setAttribute('d', host.transport === 'ssh' ? cloudPath :
                'M3 3h14v6H3z M3 11h14v6H3z M5 6h2 M5 14h2 M11 6h4 M11 14h4');
            status.querySelector('.host-name').textContent = host.label;
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
                    (name === 'VM RAM' ? ' Total host RAM charged to all libvirt QEMU VMs, including QEMU and kernel overhead, in GB rounded to one decimal place. Graph shows percentage of host RAM. Excludes swap.' : '') +
                    (name === 'Disk' ? ' Busiest physical disk (iostat %util); NVMe busy time is not throughput saturation.' : '');
                group.querySelector('strong').textContent = `${name}:`;
                group.querySelector('.percentage').textContent = data.text;
                drawChart(group.querySelector('canvas'), data.segments, colors[index % colors.length]);
            });
            for (const group of groups.slice(host.charts.length)) group.remove();
        }
        layoutResources();
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
        const selectHeading = document.createElement('th');
        const selectAll = document.createElement('input');
        selectAll.type = 'checkbox';
        selectAll.setAttribute('aria-label', 'Select all run time rows');
        selectHeading.append(selectAll);
        heading.append(selectHeading);
        for (const label of ['Case ID / Title', 'VM name', 'Run Time', 'Description']) {
            const th = document.createElement('th');
            th.textContent = label;
            heading.append(th);
        }
        const deleteHeading = document.createElement('th');
        deleteHeading.setAttribute('aria-label', 'Delete');
        heading.append(deleteHeading);
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
        const duration = seconds => seconds < 60
            ? `${Math.max(1, Math.round(seconds))}s` : `${Math.floor(seconds / 60 + .5)}m`;
        const play = (cell, row) => {
            if (!row.recording) return;
            cell.append(' | ');
            const recording = link(cell, '▶', row.recording);
            recording.title = `Open recording for ${row.vm}`;
            recording.setAttribute('aria-label', recording.title);
        };
        const groups = new Map();
        for (const row of rows) {
            const key = JSON.stringify([row.source_id, row.category, row.id]);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(row);
        }
        for (const variants of groups.values()) {
            variants.sort((a, b) => b.seconds - a.seconds || a.vm.localeCompare(b.vm));
        }
        const ordered = [...groups.entries()].sort((a, b) =>
            b[1][0].seconds - a[1][0].seconds || a[1][0].title.localeCompare(b[1][0].title));
        for (const key of selectedRunTimes) if (!groups.has(key)) selectedRunTimes.delete(key);
        const controls = table.createTHead().insertRow(0).insertCell();
        controls.colSpan = 6;
        const deleteButton = (label, action) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'delete-run-time';
            button.title = label;
            button.setAttribute('aria-label', label);
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('viewBox', '0 0 20 20');
            icon.setAttribute('aria-hidden', 'true');
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', 'M3 5h14M7 5V2h6v3M5 5l1 13h8l1-13M8 8v7M12 8v7');
            icon.append(path);
            button.append(icon);
            button.onclick = action;
            return button;
        };
        const requestDelete = keys => {
            const tokens = [...new Set(keys.flatMap(key => groups.get(key).flatMap(row => row.delete_tokens || [])))];
            vscode.postMessage({ type: 'deleteRunTimes', tokens, rows: keys.length });
        };
        const bulkDelete = deleteButton('Delete selected run time rows', () => requestDelete([...selectedRunTimes]));
        controls.append(bulkDelete);
        const footer = table.createTFoot().insertRow().insertCell();
        footer.colSpan = 6;
        const checkboxes = new Map();
        const eligible = key => groups.get(key).every(row => row.deletable);
        for (const key of selectedRunTimes) if (!eligible(key)) selectedRunTimes.delete(key);
        const updateSelection = () => {
            const keys = [...groups.keys()].filter(eligible);
            selectAll.disabled = !keys.length;
            selectAll.checked = keys.length > 0 && keys.every(key => selectedRunTimes.has(key));
            selectAll.indeterminate = selectedRunTimes.size > 0 && !selectAll.checked;
            for (const [key, checkbox] of checkboxes) checkbox.checked = selectedRunTimes.has(key);
            bulkDelete.disabled = !selectedRunTimes.size;
            footer.textContent = `${selectedRunTimes.size} of ${groups.size} rows selected`;
        };
        selectAll.onchange = () => {
            selectedRunTimes.clear();
            if (selectAll.checked) for (const key of groups.keys()) if (eligible(key)) selectedRunTimes.add(key);
            updateSelection();
        };
        for (const [key, variants] of ordered) {
            const row = variants[0];
            const tr = body.insertRow();
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.disabled = !eligible(key);
            checkbox.setAttribute('aria-label', `Select ${row.title}`);
            checkbox.onchange = () => {
                if (checkbox.checked) selectedRunTimes.add(key);
                else selectedRunTimes.delete(key);
                updateSelection();
            };
            checkboxes.set(key, checkbox);
            tr.insertCell().append(checkbox);
            const title = tr.insertCell();
            let expand;
            if (variants.length > 1) {
                expand = document.createElement('button');
                expand.type = 'button';
                expand.className = 'vm-runs-toggle';
                title.append(expand, ' ');
            }
            const category = row.category === 'e2e' ? 'E2E' : row.category;
            const caseTitle = Number.isInteger(row.id) ? `${row.id}: ${row.title}` : row.title;
            link(title, `[${category}] ${caseTitle}`, row.case_link);
            const rootRecording = document.createElement('span');
            play(rootRecording, row);
            title.append(rootRecording);
            if (expand) {
                const children = document.createElement('ul');
                children.className = 'vm-runs';
                for (const variant of variants) {
                    const child = document.createElement('li');
                    child.append(`${variant.vm} | ${duration(variant.seconds)}`);
                    play(child, variant);
                    children.append(child);
                }
                const toggle = () => {
                    const expanded = expandedRunTimes.has(key);
                    children.hidden = !expanded;
                    rootRecording.hidden = expanded;
                    expand.textContent = expanded ? '-' : '+';
                    expand.title = expanded ? 'Collapse VM runs' : 'Expand VM runs';
                    expand.setAttribute('aria-label', expand.title);
                    expand.setAttribute('aria-expanded', String(expanded));
                };
                expand.onclick = () => {
                    if (expandedRunTimes.has(key)) expandedRunTimes.delete(key);
                    else expandedRunTimes.add(key);
                    toggle();
                };
                toggle();
                title.append(children);
            }
            tr.insertCell().textContent = row.vm;
            tr.insertCell().textContent = duration(row.seconds);
            const description = tr.insertCell();
            description.className = 'run-description';
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
                for (const outcome of Array.isArray(row.expected) ? row.expected : [row.expected]) {
                    const item = document.createElement('li');
                    item.textContent = outcome;
                    expected.append(item);
                }
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
            const remove = deleteButton(`Delete run times for ${row.title}`, () => requestDelete([key]));
            remove.disabled = !eligible(key);
            tr.insertCell().append(remove);
        }
        updateSelection();
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
            if (!result.ok) {
                section.error.textContent = result.error;
                if (!result.quiet) reportError(result.error);
            }
        }
        state = { scope: snapshot.scope, selected: snapshot.selected };
        persist();
        runStatus(snapshot.runs);
        tabs(viewers, [{ id: 'all', label: 'All', active: true },
            { id: 'run-time', label: 'Run Time', active: true }, ...snapshot.entries.map(entry =>
            ({ id: entry.id, label: entry.label, active: entry.locked }))],
            state.selected, selected => select(state.scope, selected));
        resourceCharts(snapshot);
        serverStatus(snapshot.servers || []);
        const shown = snapshot.entries.filter(entry => state.selected === 'all' ? entry.active : entry.id === state.selected);
        const ids = new Set(shown.map(entry => entry.id));
        for (const [id, view] of cards) {
            if (!ids.has(id)) {
                void screen(view, null);
                view.body.remove();
                cards.delete(id);
            }
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
            if (view.title.textContent !== entry.label) view.title.textContent = entry.label;
            if (view.heading.textContent !== entry.heading) view.heading.textContent = entry.heading;
            if (view.step.textContent !== entry.step) view.step.textContent = entry.step;
            if (view.memory && view.memorySample !== entry.memory?.sample) {
                view.memorySample = entry.memory?.sample;
                view.memory.querySelector('.memory-value').textContent = entry.memory?.text || '—';
                drawChart(view.memory.querySelector('canvas'), entry.memory?.segments || [], '153, 102, 217');
            }
            if (view.status.textContent !== entry.status) view.status.textContent = entry.status;
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
            pending = pending.then(() => render(event.data)).catch(error => {
                message(error.message);
                reportError(error);
            })
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
