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
    let maximizedRun;
    const saved = vscode.getState();
    let state = { scope: 'all', selected: saved?.selected || 'all' };
    let tileLayout = ['auto', 'vertical', 'horizontal'].includes(saved?.tileLayout) ? saved.tileLayout : 'auto';
    const minimized = new Set(saved?.minimized || []);
    let manualTiles = Boolean(saved?.manualTiles);
    let viewerEntries = [];
    const minimizedFooter = document.getElementById('minimized-tiles');
    const minimizedTitles = document.getElementById('minimized-titles');
    const tileOverflow = document.getElementById('tile-overflow');
    const tileList = document.getElementById('tile-list');
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
        runBody(section);
        sessionHeading(section);
        runMinimum(section);
        if (view === 'status' && section.followStatus) section.history.scrollTop = section.history.scrollHeight;
        sessionViews();
    }

    function sessionViews() {
        const roots = [...sections].filter(([, section]) => section.view === 'session' ||
            section.view === 'status' && section.embeddedView === 'session').map(([id]) => id);
        const signature = JSON.stringify(roots);
        if (sessionViews.signature === signature) return;
        sessionViews.signature = signature;
        vscode.postMessage({ type: 'sessionView', roots });
    }

    function runBody(section) {
        const embedded = section.entry.session &&
            !(section.entry.session_inactive ?? !section.entry.session_active) ? 'session' : 'launcher';
        section.embeddedView = embedded;
        section.latestTitle.textContent = tabLabel(section.entry, embedded);
        section.latestLabel.setAttribute('aria-label', `Resize ${section.latestTitle.textContent} output`);
        section.content.hidden = section.view !== 'status';
        section.errorStatus.hidden = section.view !== 'error';
        for (const [view, node] of [['session', section.session], ['launcher', section.launcher]]) {
            const parent = section.view === 'status' && embedded === view ? section.latest : section.body;
            if (node.parentElement !== parent) parent.append(node);
            node.hidden = section.view !== view && !(section.view === 'status' && embedded === view);
        }
    }

    function tabLabel(entry, view) {
        return view === 'session' && Number.isInteger(entry.session_number) ?
            `Session ${entry.session_number}${Number.isInteger(entry.session_allowance) ? `/${entry.session_allowance}` : ''}` :
            view === 'session' ? 'Session' : 'Launcher';
    }

    function tileTitle(node, entry) {
        const label = `${entry.server || 'local'} ${entry.title_label || entry.label}`;
        const signature = JSON.stringify([label, entry.transport]);
        if (node.dataset.titleSignature === signature) return node.lastElementChild;
        node.dataset.titleSignature = signature;
        node.replaceChildren();
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 20 20');
        icon.setAttribute('aria-hidden', 'true');
        icon.classList.toggle('online-cloud', entry.transport === 'ssh');
        const shape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        shape.setAttribute('d', entry.transport === 'ssh' ? cloudPath :
            'M3 3h14v6H3z M3 11h14v6H3z M6 6h1 M6 14h1');
        icon.append(shape);
        node.append(icon);
        const text = element('span', 'tile-title-text', node);
        text.textContent = label;
        node.title = label;
        return text;
    }

    function launcherTitle(title, entry) {
        const suffix = entry.status ? ` (${entry.status})` : '';
        const defaultText = entry.custom_title || (suffix && title.textContent.endsWith(suffix) ?
            title.textContent.slice(0, -suffix.length) : title.textContent);
        title.textContent = defaultText;
        if (entry.status) {
            const statusClass = {
                failed: 'failed', stopped: 'failed', finished: 'finished', 'Closing Task': 'closing-task',
                'Stop Requested': 'stop-requested', Stopping: 'stop-requested',
                'Reload Requested': 'stop-requested', Repairing: 'stop-requested',
                Verifying: 'stop-requested',
            }[entry.status] || '';
            title.append(' (');
            element('span', `launcher-status ${statusClass}`, title).textContent =
                entry.status.charAt(0).toUpperCase() + entry.status.slice(1);
            title.append(')');
        }
        return defaultText;
    }

    function sessionHeading(section) {
        const entry = section.entry;
        if (section.editingTitle && section.editingTitle.run === entry.run) return;
        section.editingTitle = undefined;
        const signature = JSON.stringify([entry.run, entry.custom_title, entry.server, entry.transport, entry.label, entry.status, entry.session, entry.session_active,
            entry.session_number, entry.session_allowance, entry.session_inactive, entry.launcher_controls, entry.launcher_command, entry.launcher_action_command, entry.launcher_reload_command, entry.launcher_add_session_command, entry.launcher_kill, entry.launcher_close, entry.active, section.view, section.collapsed, maximizedRun === entry.id]);
        if (section.headingSignature === signature) return;
        section.headingSignature = signature;
        section.heading.replaceChildren();
        const titlebar = element('span', 'run-titlebar', section.heading);
        const labels = element('span', 'title run-label', titlebar);
        const title = tileTitle(labels, entry);
        title.classList.add('run-launcher-label');
        const defaultText = launcherTitle(title, entry);
        section.summaryRow.querySelector('.run-view-control')?.remove();
        const views = element('span', 'run-view-control', section.summaryRow);
        const select = element('button', 'run-view-select', views);
        select.type = 'button';
        select.setAttribute('aria-label', 'Run view');
        select.setAttribute('aria-haspopup', 'menu');
        select.setAttribute('aria-expanded', 'false');
        const viewMenu = element('div', 'run-view-menu', views);
        viewMenu.setAttribute('popover', 'auto');
        viewMenu.setAttribute('role', 'menu');
        viewMenu.setAttribute('aria-label', 'Run view');
        select.popoverTargetElement = viewMenu;
        for (const [view, label] of [['status', 'Status'], ['launcher', 'Launcher'], ['error', 'Error'], ['session', 'Session']]) {
            const option = element('button', '', viewMenu);
            option.type = 'button';
            option.setAttribute('role', 'menuitemradio');
            option.setAttribute('aria-checked', String(section.view === view));
            option.textContent = view === 'session' ? tabLabel(entry, view) : label;
            if (section.view === view) select.textContent = option.textContent;
            if (view === 'session' && (entry.session_inactive ?? !entry.session_active)) {
                option.classList.add('session-inactive');
                if (section.view === view) select.classList.add('session-inactive');
            }
            option.addEventListener('click', () => {
                viewMenu.hidePopover();
                runView(entry.id, view);
                section.summaryRow.querySelector('.run-view-select').focus();
            });
        }
        select.setAttribute('aria-label', `Run view: ${select.textContent}`);
        viewMenu.addEventListener('toggle', () => {
            const open = viewMenu.matches(':popover-open');
            select.setAttribute('aria-expanded', String(open));
            if (!open) return;
            const bounds = select.getBoundingClientRect();
            viewMenu.style.minWidth = `${bounds.width + 10}px`;
            viewMenu.style.left = `${Math.max(4, Math.min(bounds.left - 5,
                window.innerWidth - viewMenu.offsetWidth - 4))}px`;
            viewMenu.style.top = `${Math.max(4, Math.min(bounds.bottom + 5,
                window.innerHeight - viewMenu.offsetHeight - 4))}px`;
            viewMenu.querySelector('[aria-checked="true"]').focus();
        });
        viewMenu.addEventListener('keydown', event => {
            const options = [...viewMenu.children];
            const index = options.indexOf(document.activeElement);
            const next = { ArrowDown: (index + 1) % options.length,
                ArrowUp: (index - 1 + options.length) % options.length,
                Home: 0, End: options.length - 1 }[event.key];
            if (next === undefined) return;
            event.preventDefault();
            options[next].focus();
        });
        select.addEventListener('keydown', event => {
            if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
            event.preventDefault();
            viewMenu.showPopover();
        });
        const controls = element('span', 'run-controls', titlebar);
        const overflow = element('button', 'run-copy run-overflow', controls);
        overflow.type = 'button';
        const menuIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        menuIcon.setAttribute('viewBox', '0 0 20 20');
        menuIcon.setAttribute('aria-hidden', 'true');
        const menuShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        menuShape.setAttribute('d', 'M4 4h12 M4 10h12 M4 16h12');
        menuIcon.append(menuShape);
        overflow.append(menuIcon);
        overflow.title = 'Launcher actions';
        overflow.setAttribute('aria-label', overflow.title);
        overflow.setAttribute('aria-expanded', 'false');
        const menu = element('div', 'run-action-menu', controls);
        menu.setAttribute('popover', 'auto');
        menu.setAttribute('aria-label', 'Launcher actions');
        overflow.popoverTargetElement = menu;
        menu.addEventListener('toggle', () => {
            const open = menu.matches(':popover-open');
            overflow.setAttribute('aria-expanded', String(open));
            if (!open) return;
            const bounds = overflow.getBoundingClientRect();
            menu.style.left = `${Math.max(4, Math.min(bounds.right - menu.offsetWidth,
                window.innerWidth - menu.offsetWidth - 4))}px`;
            menu.style.top = `${Math.max(4, Math.min(bounds.bottom + 4,
                window.innerHeight - menu.offsetHeight - 4))}px`;
        });
        const kind = entry.status === 'Stop Requested' ? 'cancel-stop' : entry.active ? 'stop' : 'resume';
        const button = element('button', 'run-copy run-launcher-action', menu);
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
        button.append(kind === 'cancel-stop' ? 'Cancel stop request' : entry.active ? 'Stop' : 'Resume');
        button.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            vscode.postMessage({ type: 'launcherAction', root: entry.id, run: entry.run, kind });
        });
        const reload = element('button', 'run-copy run-launcher-action', menu);
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
        reload.append(reloadIcon, 'Reload');
        reload.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            vscode.postMessage({ type: 'launcherAction', root: entry.id, run: entry.run, kind: 'reload' });
        });
        const addSessions = element('button', 'run-copy run-launcher-action', menu);
        addSessions.type = 'button';
        addSessions.dataset.kind = 'add-session';
        const clockIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        clockIcon.setAttribute('viewBox', '0 0 20 20');
        clockIcon.setAttribute('aria-hidden', 'true');
        clockIcon.style.strokeWidth = '2';
        clockIcon.style.strokeLinecap = 'round';
        clockIcon.style.strokeLinejoin = 'round';
        const clockFace = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        clockFace.setAttribute('cx', '10');
        clockFace.setAttribute('cy', '10');
        clockFace.setAttribute('r', '8.5');
        const clockHands = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        clockHands.setAttribute('d', 'M10 4.5V10h4');
        clockIcon.append(clockFace, clockHands);
        addSessions.append(clockIcon, 'Add 5 Sessions');
        addSessions.title = entry.launcher_add_session_command || 'Add 5 Sessions';
        addSessions.disabled = !entry.launcher_controls || !entry.launcher_add_session_command;
        addSessions.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            vscode.postMessage({ type: 'launcherAction', root: entry.id, run: entry.run, kind: 'add-session' });
        });
        const kill = element('button', 'run-copy run-launcher-action', menu);
        kill.type = 'button';
        kill.dataset.kind = 'kill';
        kill.title = 'Kill launcher: cancel current session and tests immediately, then clean up';
        kill.setAttribute('aria-label', 'Kill launcher');
        kill.disabled = !entry.launcher_controls || !entry.launcher_kill || entry.status === 'Stopping';
        const killIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        killIcon.setAttribute('viewBox', '0 0 20 20');
        killIcon.setAttribute('aria-hidden', 'true');
        const killShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        killShape.setAttribute('d', 'M6 1h8l5 5v8l-5 5H6l-5-5V6z M7 7l6 6 M13 7l-6 6');
        killIcon.append(killShape);
        kill.append(killIcon, 'Kill');
        kill.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            vscode.postMessage({ type: 'launcherAction', root: entry.id, run: entry.run, kind: 'kill' });
        });
        const close = element('button', 'run-copy run-launcher-action', menu);
        close.type = 'button';
        close.dataset.kind = 'close';
        close.title = 'Close Finished Launcher';
        close.setAttribute('aria-label', close.title);
        close.disabled = !entry.launcher_close || entry.active;
        const closeIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        closeIcon.setAttribute('viewBox', '0 0 20 20');
        closeIcon.setAttribute('aria-hidden', 'true');
        const closeShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        closeShape.setAttribute('d', 'M5 5l10 10 M15 5L5 15');
        closeIcon.append(closeShape);
        close.append(closeIcon, 'Close Finished Launcher');
        close.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            vscode.postMessage({ type: 'launcherAction', root: entry.id, run: entry.run, kind: 'close' });
        });
        if (entry.launcher_command) labels.title = entry.launcher_command;
        title.tabIndex = 0;
        title.setAttribute('role', 'textbox');
        title.setAttribute('aria-label', 'Launcher title');
        title.setAttribute('aria-readonly', 'true');
        const finishTitle = save => {
            if (!section.editingTitle) return;
            const value = title.textContent.trim().slice(0, 512);
            section.editingTitle = undefined;
            if (save) {
                const title = value === defaultText ? (entry.custom_title || '') : value;
                section.entry.custom_title = title || undefined;
                vscode.postMessage({ type: 'renameLauncher', root: entry.id, run: entry.run, title });
            }
            section.headingSignature = undefined;
            sessionHeading(section);
        };
        const editTitle = () => {
            if (section.editingTitle) return;
            section.editingTitle = { run: entry.run };
            title.textContent = defaultText;
            title.contentEditable = 'plaintext-only';
            title.setAttribute('aria-readonly', 'false');
            title.focus();
            const selection = window.getSelection();
            selection.selectAllChildren(title);
        };
        title.addEventListener('click', event => {
            if (event.detail < 2) editTitle();
        });
        title.addEventListener('dblclick', event => {
            event.preventDefault();
            title.textContent = defaultText;
            finishTitle(false);
        });
        title.addEventListener('blur', () => finishTitle(true));
        title.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                if (section.editingTitle) finishTitle(true);
                else editTitle();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                finishTitle(false);
            }
        });
        if (entry.custom_title) {
            const undo = element('button', 'run-title-undo', labels);
            undo.type = 'button';
            undo.textContent = '↶';
            undo.title = 'Restore default title';
            undo.setAttribute('aria-label', undo.title);
            // Avoid committing an in-progress edit before restoring the default.
            undo.addEventListener('mousedown', event => event.preventDefault());
            undo.addEventListener('click', () => {
                section.editingTitle = undefined;
                section.entry.custom_title = undefined;
                vscode.postMessage({ type: 'renameLauncher', root: entry.id, run: entry.run, title: '' });
                section.headingSignature = undefined;
                sessionHeading(section);
            });
        }
        section.body.classList.toggle('collapsed', Boolean(section.collapsed));
        const copy = element('button', 'run-copy run-launcher-action', menu);
        copy.type = 'button';
        copy.title = 'Copy tab content';
        copy.setAttribute('aria-label', copy.title);
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 20 20');
        icon.setAttribute('aria-hidden', 'true');
        const shape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        shape.setAttribute('d', 'M7 7h10v10H7z M4 13H3V3h10v1');
        icon.append(shape);
        copy.append(icon, 'Copy tab content');
        copy.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            const body = { status: section.content, launcher: section.launcher,
                error: section.errorStatus, session: section.output }[section.view];
            const activity = section.view === 'session' && !section.activity.hidden ?
                `\n${section.activity.innerText}` : '';
            vscode.postMessage({ type: 'copy', root: entry.id, text: body.innerText + activity });
        });
        const copyCommand = element('button', 'run-copy run-launcher-action', menu);
        copyCommand.type = 'button';
        copyCommand.title = 'Copy Command';
        copyCommand.setAttribute('aria-label', copyCommand.title);
        copyCommand.disabled = !entry.launcher_command;
        const commandIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        commandIcon.setAttribute('viewBox', '0 0 20 20');
        commandIcon.setAttribute('aria-hidden', 'true');
        const commandShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        commandShape.setAttribute('d', 'M2 3h16v14H2z M5 7l3 3-3 3 M10 13h5');
        commandIcon.append(commandShape);
        copyCommand.append(commandIcon, 'Copy Command');
        copyCommand.addEventListener('click', () => {
            menu.hidePopover();
            overflow.focus();
            vscode.postMessage({ type: 'copy', root: entry.id,
                text: entry.launcher_command, command: true });
        });
        menu.prepend(copy, copyCommand);
        element('span', 'run-controls-divider', controls).setAttribute('aria-hidden', 'true');
        const restore = () => {
            maximizedRun = undefined;
            for (const panel of sections.values()) {
                panel.collapsed = false;
                sessionHeading(panel);
            }
            runDividers();
        };
        const toggleMaximize = () => {
            if (maximizedRun === entry.id) {
                restore();
                return;
            }
            maximizedRun = entry.id;
            for (const panel of sections.values()) {
                panel.collapsed = panel.entry.id !== maximizedRun;
                sessionHeading(panel);
            }
            runDividers();
        };
        section.resizeTitle = () => {
            if (section.collapsed) restore();
            else toggleMaximize();
        };
        const resizing = tileResizeControls(controls, entry.label, () => {
            if (section.collapsed) {
                restore();
                return;
            }
            if (maximizedRun === entry.id) maximizedRun = undefined;
            section.collapsed = true;
            sessionHeading(section);
            runDividers();
        }, toggleMaximize);
        tileActionState(resizing.minimize, resizing.minimizeShape, Boolean(section.collapsed),
            'Minimize tile', 'M5 10h10', entry.label);
        tileMaximizeState(resizing, maximizedRun === entry.id, entry.label);
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
        const error = element('div', 'session-error', session);
        error.setAttribute('role', 'status');
        const footer = element('div', 'session-footer', session);
        const model = element('span', 'session-model', footer);
        const simplified = element('label', 'session-simplified', footer);
        simplified.append('Simplified ');
        const section = { session, output, activity, composer, input, error, model, fitInput, inputObserver };
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
        // Streaming usually changes only the final row.
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

    function launcherRows(output, entry) {
        const rows = entry.launcher_output && entry.launcher_rows ||
            terminal(entry.launcher_output || 'Waiting for launcher output…').split('\n')
                .map(text => [{ text }]);
        output.replaceChildren();
        rows.forEach((row, index) => {
            if (index) output.appendChild(document.createTextNode('\n'));
            for (const part of row) runSpan(output, { ...part, text: terminal(part.text) });
        });
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
        if (section.model.textContent !== view.model) section.model.textContent = view.model;
        section.toggle.setAttribute('aria-checked', String(view.simplified));
        section.toggle.disabled = !section.entry.session || !section.entry.connected || Boolean(view.unavailable);
        section.input.disabled = !view.input_enabled || !section.entry.connected;
    }

    function persist() {
        vscode.setState({ ...state, split, tileLayout, manualTiles, minimized: [...minimized] });
    }

    function arrangeTiles(value) {
        tileLayout = value;
        manualTiles = false;
        minimized.clear();
        grid.dataset.layout = value;
        persist();
    }

    function tileLayoutButtons() {
        document.querySelectorAll('#tile-layout button[data-layout]').forEach(button => {
            button.setAttribute('aria-pressed', String(!manualTiles &&
                ['all', 'run-time'].includes(state.selected) && button.dataset.layout === tileLayout));
        });
    }
    document.querySelectorAll('#tile-layout button[data-layout]').forEach(button => {
        button.addEventListener('click', () => {
            arrangeTiles(button.dataset.layout);
            select(state.scope, 'all');
        });
    });
    grid.dataset.layout = tileLayout;
    tileLayoutButtons();

    function maximizeTile(id) {
        manualTiles = true;
        for (const entry of viewerEntries) minimized.add(entry.id);
        minimized.delete(id);
        select(state.scope, id);
    }

    function minimizeTile(id) {
        manualTiles = true;
        if (state.selected === id) {
            for (const entry of viewerEntries) minimized.add(entry.id);
            select(state.scope, 'all');
        } else {
            minimized.add(id);
            persist();
            viewerLayout();
        }
    }

    function fitMinimizedTitles() {
        if (minimizedFooter.hidden) return;
        const buttons = [...minimizedTitles.children];
        buttons.forEach(button => { button.hidden = false; });
        const total = buttons.reduce((width, button) => width + button.getBoundingClientRect().width, 0);
        const fullWidth = minimizedTitles.clientWidth + tileOverflow.getBoundingClientRect().width;
        tileOverflow.hidden = total <= fullWidth;
        if (tileOverflow.hidden) {
            tileOverflow.open = false;
            return;
        }
        let used = 0;
        const available = minimizedTitles.clientWidth;
        for (const button of buttons) {
            used += button.getBoundingClientRect().width;
            button.hidden = used > available;
        }
    }
    new ResizeObserver(() => fitMinimizedTitles()).observe(minimizedFooter);
    document.addEventListener('click', event => {
        if (!tileOverflow.contains(event.target)) tileOverflow.open = false;
    });
    tileOverflow.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            tileOverflow.open = false;
            tileOverflow.querySelector('summary').focus();
        }
    });

    function viewerLayout() {
        const runtime = state.selected === 'run-time';
        const maximized = !['all', 'run-time'].includes(state.selected);
        const visible = viewerEntries.filter(entry => !runtime &&
            (maximized ? entry.id === state.selected : !minimized.has(entry.id)));
        const visibleIds = new Set(visible.map(entry => entry.id));
        for (const [id, view] of cards) view.body.hidden = !visibleIds.has(id);
        grid.classList.toggle('single', maximized || visible.length === 1);
        tileLayoutButtons();
        const collapsed = viewerEntries.filter(entry => !visibleIds.has(entry.id));
        minimizedFooter.hidden = runtime || !collapsed.length;
        const signature = JSON.stringify([collapsed.map(entry => [entry.id, entry.label]),
            viewerEntries.map(entry => [entry.id, entry.label])]);
        if (minimizedFooter.dataset.signature !== signature) {
            minimizedFooter.dataset.signature = signature;
            const titleButton = entry => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'watch-tile minimized-tile';
                const heading = element('span', 'watch-tile-heading tile-titlebar', button);
                tileTitle(element('span', 'title', heading), entry);
                button.title = entry.label;
                tileSelection(button, heading, () => {
                    tileOverflow.open = false;
                    if (state.selected === entry.id || minimized.has(entry.id) ||
                            !['all', 'run-time'].includes(state.selected)) {
                        arrangeTiles(tileLayout);
                        select(state.scope, 'all');
                    } else maximizeTile(entry.id);
                });
                return button;
            };
            minimizedTitles.replaceChildren(...collapsed.map(titleButton));
            tileList.replaceChildren(...viewerEntries.map(titleButton));
            tileOverflow.open = false;
        }
        fitMinimizedTitles();
        const empty = grid.querySelector('.empty');
        if (empty && viewerEntries.length) empty.remove();
    }

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
        viewerLayout();
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

    function tileSelection(body, heading, resizeTitle) {
        body.addEventListener('click', () => {
            for (const tile of layout.querySelectorAll('.watch-tile')) {
                tile.classList.toggle('selected', tile === body);
            }
        }, true);
        heading.addEventListener('dblclick', event => {
            const control = event.target.closest('a, button, select, input, textarea');
            if (control && control !== body) return;
            event.preventDefault();
            resizeTitle();
        });
    }

    function tileResizeControls(titlebar, label, onMinimize, onMaximize) {
        const minimize = element('button', 'tile-action tile-minimize', titlebar);
        minimize.type = 'button';
        minimize.title = 'Minimize tile';
        minimize.setAttribute('aria-label', `Minimize tile: ${label}`);
        const minimizeIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        minimizeIcon.setAttribute('viewBox', '0 0 20 20');
        minimizeIcon.setAttribute('aria-hidden', 'true');
        const minimizeShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        minimizeShape.setAttribute('d', 'M5 10h10');
        minimizeIcon.append(minimizeShape);
        minimize.append(minimizeIcon);
        minimize.addEventListener('click', onMinimize);
        const maximize = element('button', 'tile-action tile-maximize', titlebar);
        maximize.type = 'button';
        const maximizeIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        maximizeIcon.setAttribute('viewBox', '0 0 20 20');
        maximizeIcon.setAttribute('aria-hidden', 'true');
        const maximizeShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        maximizeIcon.append(maximizeShape);
        maximize.append(maximizeIcon);
        maximize.addEventListener('click', onMaximize);
        return { minimize, minimizeShape, maximize, maximizeShape };
    }

    function tileMaximizeState(view, maximized, label) {
        tileActionState(view.maximize, view.maximizeShape, maximized, 'Maximize tile',
            'M12 3h5v5 M17 3l-6 6 M8 17H3v-5 M3 17l6-6', label);
    }

    function tileActionState(button, shape, restore, title, path, label) {
        button.title = restore ? 'Restore tile layout' : title;
        button.setAttribute('aria-label', `${button.title}: ${label}`);
        button.setAttribute('aria-pressed', String(restore));
        shape.setAttribute('d', restore ?
            'M8 7V4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3 M4 7h7a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z' :
            path);
    }

    function card(entry) {
        const body = document.createElement('article');
        body.className = `watch-tile card ${entry.kind}`;
        const titlebar = element('div', 'watch-tile-heading tile-titlebar', body);
        const toggleMaximize = () => {
            if (state.selected === entry.id) {
                arrangeTiles(tileLayout);
                select(state.scope, 'all');
            } else maximizeTile(entry.id);
        };
        tileSelection(body, titlebar, toggleMaximize);
        const title = element('span', 'title', titlebar);
        const screenshot = element('button', 'tile-action tile-screenshot', titlebar);
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
        const { maximize, maximizeShape } = tileResizeControls(titlebar, entry.label,
            () => minimizeTile(entry.id), toggleMaximize);
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
        return { body, title, heading, step, canvas, waiting, activity, status, memory, screenshot, maximize, maximizeShape };
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
        const minimum = section.heading.offsetHeight + section.summaryRow.offsetHeight +
            (section.view === 'status' ? section.latestLabel.offsetHeight : 0) + 80;
        section.minimum = Math.max(100, minimum);
        section.body.style.minHeight = `${section.minimum}px`;
    }

    function previewDivider(section) {
        const handle = section.latestLabel;
        const toggle = element('button', 'run-latest-toggle', handle);
        toggle.type = 'button';
        handle.tabIndex = 0;
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-orientation', 'horizontal');
        const resize = height => {
            if (section.view !== 'status' || !section.content.clientHeight) return;
            const maximum = Math.max(0, section.content.clientHeight - section.latestLabel.offsetHeight);
            const value = Math.max(0, Math.min(maximum, height ??
                (section.previewMaximized ? maximum : section.previewHeight) ?? 0));
            section.latest.style.height = `${value}px`;
            section.latest.hidden = value === 0;
            section.history.hidden = value >= maximum;
            const expanded = value >= maximum;
            toggle.classList.toggle('expanded', expanded);
            toggle.setAttribute('aria-label', expanded ? 'Minimize output height' : 'Maximize output height');
            toggle.title = toggle.getAttribute('aria-label');
            handle.setAttribute('aria-valuemin', '0');
            handle.setAttribute('aria-valuemax', String(Math.round(maximum)));
            handle.setAttribute('aria-valuenow', String(Math.round(value)));
            return value;
        };
        toggle.addEventListener('click', () => {
            section.previewMaximized = !toggle.classList.contains('expanded');
            section.previewHeight = undefined;
            resize();
        });
        let drag;
        handle.addEventListener('pointerdown', event => {
            if (event.button !== 0 || toggle.contains(event.target)) return;
            event.preventDefault();
            handle.focus();
            drag = { y: event.clientY, height: section.latest.offsetHeight };
            handle.setPointerCapture(event.pointerId);
            document.body.classList.add('resizing-runs');
        });
        handle.addEventListener('pointermove', event => {
            if (!drag || !handle.hasPointerCapture(event.pointerId)) return;
            section.previewMaximized = false;
            section.previewHeight = resize(drag.height + drag.y - event.clientY);
        });
        const release = event => {
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
        };
        handle.addEventListener('pointerup', release);
        handle.addEventListener('pointercancel', release);
        handle.addEventListener('lostpointercapture', () => {
            drag = undefined;
            document.body.classList.remove('resizing-runs');
        });
        handle.addEventListener('keydown', event => {
            if (event.target !== handle) return;
            const line = parseFloat(getComputedStyle(section.history).lineHeight) || 20;
            const height = { ArrowUp: section.latest.offsetHeight + line,
                ArrowDown: section.latest.offsetHeight - line, Home: 0, End: Infinity }[event.key];
            if (height === undefined) return;
            event.preventDefault();
            section.previewMaximized = false;
            section.previewHeight = resize(height);
        });
        section.previewObserver = new ResizeObserver(() => resize());
        section.previewObserver.observe(section.content);
        section.previewObserver.observe(handle);
    }

    function runDivider(section) {
        const handle = section.divider;
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-orientation', 'horizontal');
        handle.setAttribute('aria-label', 'Resize launcher panels');
        let drag;
        const resizePair = (previous, top, delta) => {
            if (!delta) return;
            if (maximizedRun) {
                maximizedRun = undefined;
                for (const panel of sections.values()) sessionHeading(panel);
            }
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
        if (maximizedRun && !ids.has(maximizedRun)) {
            maximizedRun = undefined;
            for (const panel of sections.values()) panel.collapsed = false;
        }
        for (const [id, section] of sections) {
            if (!ids.has(id)) {
                section.inputObserver.disconnect();
                section.statusObserver.disconnect();
                section.previewObserver.disconnect();
                section.body.remove();
                section.divider.remove();
                sections.delete(id);
            }
        }
        if (entries.length) runs.querySelector('.empty')?.remove();
        entries.forEach((entry, index) => {
            let section = sections.get(entry.id);
            if (!section) {
                const body = element('section', 'watch-tile run', runs);
                body.dataset.root = entry.id;
                const divider = element('div', 'run-divider', runs);
                const heading = element('h2', 'watch-tile-heading run-heading', body);
                tileSelection(body, heading, () => section.resizeTitle());
                const summaryRow = element('div', 'run-summary-row', body);
                const summary = element('pre', 'run-status run-summary', summaryRow);
                const content = element('div', 'run-status-view', body);
                const history = element('pre', 'run-status run-history', content);
                const preview = element('div', 'run-latest', content);
                const latestLabel = element('div', 'run-latest-label', preview);
                const latestTitle = element('span', 'run-latest-title', latestLabel);
                element('span', 'run-latest-rule', latestLabel);
                const latest = element('div', 'run-embedded', preview);
                const launcher = element('pre', 'run-status', body);
                launcher.setAttribute('aria-label', 'Launcher terminal output');
                const errorStatus = element('pre', 'run-status', body);
                errorStatus.setAttribute('aria-label', 'Last Error and Status');
                section = Object.assign(sessionPanel(body), { body, divider, heading, summaryRow, content, summary, history,
                    preview, latestLabel, latestTitle, latest, launcher, errorStatus,
                    view: 'status', weight: 1, followStatus: true, previewMaximized: true });
                const panel = section;
                previewDivider(panel);
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
                panel.statusObserver.observe(summaryRow);
                panel.statusObserver.observe(preview);
                sections.set(entry.id, section);
                runDivider(section);
            }
            const previous = section.entry;
            if (previous && previous.run === entry.run && previous.session === entry.session) {
                for (const field of ['rows', 'error_rows', 'launcher_output', 'launcher_rows']) {
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
            if (maximizedRun) section.collapsed = entry.id !== maximizedRun;
            section.entry = entry;
            if (!previous || previous.run !== entry.run) section.followStatus = true;
            if (!entry.connected) {
                section.input.disabled = true;
                section.toggle.disabled = true;
            }
            sessionHeading(section);
            runBody(section);
            if (entry.session_view) sessionRows(section, entry.session_view);
            else if (!entry.session) {
                section.output.textContent = 'No active session';
                section.activity.replaceChildren();
                section.activity.hidden = true;
                section.activitySignature = undefined;
                section.outputRows = undefined;
                section.input.disabled = true;
                section.toggle.disabled = true;
                section.model.textContent = '';
            }
            if (section.launcherText !== entry.launcher_output || section.launcherRows !== entry.launcher_rows) {
                const follow = section.launcher.scrollHeight - section.launcher.clientHeight - section.launcher.scrollTop < 24;
                section.launcherText = entry.launcher_output;
                section.launcherRows = entry.launcher_rows;
                launcherRows(section.launcher, entry);
                if (follow) section.launcher.scrollTop = section.launcher.scrollHeight;
            }
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
            section.history.replaceChildren(...(hasSummary ? rows.slice(summaryEnd + 1) : rows));
            if (section.followStatus) section.history.scrollTop = section.history.scrollHeight;
        });
        runDividers();
        sessionViews();
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
        tabs(viewers, [{ id: 'all', label: 'VM Viewer', active: true },
            { id: 'run-time', label: 'Run Time', active: true }],
            state.selected === 'run-time' ? 'run-time' : 'all', selected => {
                if (selected === 'all') arrangeTiles(tileLayout);
                select(state.scope, selected);
            });
        resourceCharts(snapshot);
        serverStatus(snapshot.servers || []);
        const entryIds = new Set(snapshot.entries.map(entry => entry.id));
        for (const id of minimized) if (!entryIds.has(id)) minimized.delete(id);
        const shown = snapshot.entries.filter(entry => entry.active || entry.id === state.selected || minimized.has(entry.id));
        viewerEntries = shown;
        const ids = new Set(shown.map(entry => entry.id));
        for (const [id, view] of cards) {
            if (!ids.has(id)) {
                void screen(view, null);
                view.body.remove();
                cards.delete(id);
            }
        }
        if (state.selected === 'run-time') {
            viewerLayout();
            runTimes(snapshot.run_times || []);
            return;
        }
        grid.querySelector('.run-times')?.remove();
        grid.classList.remove('runtime-body');
        if (!shown.length) {
            viewerLayout();
            message('Waiting for UI tests or VM activity.');
            return;
        }
        grid.querySelector('.empty')?.remove();
        const draws = [];
        shown.forEach((entry, index) => {
            let view = cards.get(entry.id);
            if (!view) { view = card(entry); cards.set(entry.id, view); }
            if (view.source !== entry.source) {
                void screen(view, null);
                view.source = entry.source;
            }
            if (grid.children[index] !== view.body) grid.insertBefore(view.body, grid.children[index] || null);
            tileTitle(view.title, entry);
            tileMaximizeState(view, state.selected === entry.id, entry.label);
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
        viewerLayout();
        await Promise.all(draws);
    }

    window.addEventListener('message', event => {
        if (event.data.type === 'commandCopied') {
            const section = sections.get(event.data.root);
            if (section) {
                clearTimeout(section.copyFeedbackTimer);
                section.heading.classList.add('command-copied');
                section.copyFeedbackTimer = setTimeout(() => section.heading.classList.remove('command-copied'), 1500);
            }
        }
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
