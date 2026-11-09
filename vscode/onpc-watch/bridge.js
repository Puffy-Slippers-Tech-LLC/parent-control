'use strict';

// Controller-independent stdio bridge. Local and SSH sources use identical RPCs.
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const { isDeepStrictEqual } = require('node:util');

const VERSION = 1;
const MAX_RESPONSE = 96 * 1024 * 1024;
const MAX_REQUEST = 512 * 1024;
const SSH_REFUSAL = /Permission denied|Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED|Too many authentication failures/i;
const key = (source, value) => JSON.stringify([source, value]);
const quote = value => "'" + value.replace(/'/g, "'\\''") + "'";
const RUN_BODIES = ['rows', 'error_rows', 'launcher_output', 'launcher_rows', 'session_preview'];

function configuration(values, root) {
    if (!Array.isArray(values) || values.length > 16) throw new Error('Watch sources must be an array of at most 16 sources.');
    if (!values.length) {
        values = [{ id: 'local', transport: 'local' }];
        const document = JSON.parse(fs.readFileSync(path.join(root, 'config/environment.json'), 'utf8'));
        // Host availability controls VM scheduling, not observation of launchers.
        for (const host of document.hosts || []) {
            if (host.transport !== 'ssh') continue;
            const branch = (document.branches || []).find(branch => branch.host === host.name);
            if (branch) values.push({ id: `remote${values.length}`, label: host.name,
                transport: 'ssh', host: host.name, root: branch.repo_root });
        }
        if (values.length > 16) throw new Error('Watch supports at most 16 sources; select sources in onpc.watch.sources.');
    }
    const ids = new Set();
    return values.map(value => {
        if (!value || typeof value !== 'object' || typeof value.id !== 'string' ||
                !/^[a-zA-Z0-9_-]{1,64}$/.test(value.id) || ids.has(value.id)) {
            throw new Error('Each Watch source needs a unique id (letters, numbers, _ or -).');
        }
        ids.add(value.id);
        const transport = value.transport || 'local';
        if (!['local', 'ssh'].includes(transport)) throw new Error(`Unknown Watch transport: ${transport}`);
        if (transport === 'ssh' && !value.root) throw new Error('SSH Watch sources require a root on the remote host.');
        const sourceRoot = value.root || root;
        if (typeof sourceRoot !== 'string' || !sourceRoot.startsWith('/') || /[\0\r\n]/.test(sourceRoot)) {
            throw new Error('Watch source root must be an absolute Linux path.');
        }
        if (transport === 'ssh' && (typeof value.host !== 'string' || !/^[a-zA-Z0-9_][a-zA-Z0-9_.@:-]*$/.test(value.host))) {
            throw new Error('SSH Watch sources need an SSH config host alias or user@host.');
        }
        const command = value.command || ['/usr/bin/python3', '-B', path.posix.join(sourceRoot, 'tools/watch_webview.py'), '--root', sourceRoot];
        if (!Array.isArray(command) || !command.length || command.some(part => typeof part !== 'string' || !part || /[\0\r\n]/.test(part))) {
            throw new Error('Watch command must be a nonempty argv array.');
        }
        const label = value.label || value.id;
        if (typeof label !== 'string' || label.length > 128) throw new Error('Watch source label is too long.');
        return { id: value.id, label, transport, host: value.host, root: sourceRoot, command };
    });
}

function resourceConfiguration(root) {
    const document = JSON.parse(fs.readFileSync(path.join(root, 'config/environment.json'), 'utf8'));
    const hosts = document.hosts || [{ name: 'local', enabled: 'true', transport: 'local' }];
    if (!Array.isArray(hosts)) throw new Error('Watch host configuration must be an array.');
    const program = fs.readFileSync(path.join(root, 'tools/watch_model.py'), 'utf8');
    const names = new Set();
    return hosts.map(host => {
        if (!host || typeof host.name !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$/.test(host.name) ||
                names.has(host.name) || !['true', 'false'].includes(host.enabled) ||
                !['local', 'ssh'].includes(host.transport) ||
                (host.ssh_port !== undefined && (host.transport !== 'ssh' ||
                    !Number.isInteger(host.ssh_port) || host.ssh_port < 1 || host.ssh_port > 65535))) {
            throw new Error('Invalid Watch host in config/environment.json.');
        }
        names.add(host.name);
        // Scheduling availability does not control Watch connectivity.
        return { id: host.name, label: host.name, transport: host.transport,
            host: host.name, root, command: ['/usr/bin/python3', '-u', '-B', '-c', program] };
    });
}

function validate(snapshot) {
    const unique = values => new Set(values.map(value => value.id)).size === values.length;
    const identifier = value => typeof value === 'string' && value.length > 0 && value.length <= 4096;
    const image = value => value && Number.isInteger(value.width) && Number.isInteger(value.height) &&
        value.width > 0 && value.width <= 8192 && value.height > 0 && value.height <= 8192 &&
        typeof value.image === 'string' && value.image.startsWith('data:image/png;base64,');
    const screen = value => value === null || (image(value) && (!value.cursor ||
        (image(value.cursor) && Number.isFinite(value.cursor.x) && Number.isFinite(value.cursor.y))));
    const rows = value => Array.isArray(value) && value.every(row => Array.isArray(row) && row.every(
        part => part && typeof part.text === 'string' && (part.link == null ||
            (typeof part.link === 'string' && part.link.length <= 8192))));
    const chart = value => value && Array.isArray(value.segments) && value.segments.every(segment =>
        Array.isArray(segment) && segment.length && segment.every(point => Array.isArray(point) &&
            point.length === 2 && point.every(Number.isFinite)));
    if (snapshot?.protocol !== VERSION) throw new Error('Incompatible Watch bridge; update the adapter (protocol 1 required).');
    if (snapshot.run_times !== undefined && (!Array.isArray(snapshot.run_times) || snapshot.run_times.some(row =>
        !row || !['system', 'integration', 'e2e'].includes(row.category) ||
        !(Number.isInteger(row.id) && row.id > 0 || typeof row.id === 'string') ||
        !Number.isFinite(row.seconds) || row.seconds < 0 ||
        !Number.isFinite(row.completed_at) ||
        ['title', 'vm', 'case_file', 'description', 'case_link'].some(field => typeof row[field] !== 'string') ||
        row.case_link.length > 8192 || (row.recording !== null &&
            (typeof row.recording !== 'string' || row.recording.length > 8192))))) {
        throw new Error('Invalid VM run times.');
    }
    if (!Array.isArray(snapshot.entries) || !Array.isArray(snapshot.runs) || !Array.isArray(snapshot.checkouts) ||
        !Array.isArray(snapshot.resource_charts) || !snapshot.capabilities ||
        typeof snapshot.capabilities.sessions !== 'boolean' || typeof snapshot.capabilities.artifacts !== 'boolean' ||
        snapshot.entries.some(entry => !entry || !['ui', 'vm'].includes(entry.kind) ||
            !identifier(entry.id) || ['all', '__hidden__'].includes(entry.id) || !identifier(entry.source) ||
            typeof entry.active !== 'boolean' || typeof entry.locked !== 'boolean' ||
            ['id', 'source', 'label', 'heading', 'step', 'status', 'activity'].some(field => typeof entry[field] !== 'string') ||
            (Object.hasOwn(entry, 'screen') && !screen(entry.screen)) ||
            (entry.memory && !chart(entry.memory))) ||
        snapshot.runs.some(run => !run || !identifier(run.id) || typeof run.label !== 'string' ||
            typeof run.active !== 'boolean' || typeof run.status !== 'string' ||
            (run.run !== null && typeof run.run !== 'string') || typeof run.launcher_output !== 'string' ||
            (Object.hasOwn(run, 'launcher_rows') && !rows(run.launcher_rows)) ||
            (Object.hasOwn(run, 'session_preview') && !rows(run.session_preview)) ||
            (Object.hasOwn(run, 'launcher_command') && typeof run.launcher_command !== 'string') ||
            (run.session !== null && !identifier(run.session)) ||
            ['session_active', 'session_inactive', 'session_waiting'].some(field => typeof run[field] !== 'boolean') ||
            !rows(run.rows) || !rows(run.error_rows) || (run.session_view &&
                (!rows(run.session_view.rows) || typeof run.session_view.input_enabled !== 'boolean'))) ||
        snapshot.resource_charts.some(value => !chart(value) || typeof value.label !== 'string' || typeof value.text !== 'string') ||
        snapshot.checkouts.some(checkout => !checkout || !identifier(checkout.id) || checkout.id === 'all' || typeof checkout.label !== 'string') ||
        !unique(snapshot.entries) || !unique(snapshot.runs) || !unique(snapshot.checkouts)) {
        throw new Error('Invalid Watch snapshot.');
    }
}

class Source {
    constructor(config, log, changed, reportError = () => {}) {
        this.config = config;
        this.log = message => log(`${new Date().toISOString()} [${config.label}/${config.reader || 'watch'}] ${message}`);
        this.changed = changed;
        this.reportError = reportError;
        this.status = 'Connecting';
        this.authRefused = false;
        this.stderr = '';
        this.retryAt = 0;
        this.backoff = 1000;
        this.frames = new Map();
        this.staleFrames = new Set();
        this.actions = [];
    }

    start() {
        const config = this.config;
        const remote = config.transport === 'ssh';
        const command = remote ? 'ssh' : config.command[0];
        // No PTY, shell wrapper locally, interactive authentication or host-key adoption.
        const args = remote ? ['-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=1', '-o', 'ServerAliveCountMax=3',
            '--', config.host, config.command.map(quote).join(' ')] : config.command.slice(1);
        // Spawn returns without waiting for SSH; sources connect independently.
        const child = spawn(command, args, { cwd: remote ? undefined : config.root, stdio: ['pipe', 'pipe', 'pipe'] });
        this.child = child;
        this.log(`Reader started (pid ${child.pid ?? 'unavailable'}).`);
        this.status = 'Connecting';
        this.authRefused = false;
        this.stderr = '';
        this.stderrTruncated = false;
        this.changed();
        let chunks = [], bytes = 0;
        child.stdout.on('data', data => {
            if (this.child !== child) return;
            if (this.pending) this.pending.bytes += data.length;
            // Accumulate without repeatedly copying a large PNG/recording response.
            let start = 0;
            while (start < data.length) {
                const end = data.indexOf(10, start);
                const part = data.subarray(start, end < 0 ? data.length : end);
                bytes += part.length;
                if (bytes > MAX_RESPONSE) { this.fail('Watch response too large.'); return; }
                chunks.push(part);
                if (end < 0) break;
                const line = Buffer.concat(chunks, bytes).toString('utf8');
                chunks = []; bytes = 0;
                try { this.receive(JSON.parse(line)); }
                catch (error) { this.fail(error.message); return; }
                start = end + 1;
            }
        });
        child.stderr.on('data', data => {
            if (this.child !== child) return;
            this.stderr += data.toString();
            if (remote && SSH_REFUSAL.test(this.stderr.slice(-8192))) this.authRefused = true;
            // Full stderr is streamed to Output; don't retain an unbounded second
            // copy for a connection that can remain healthy for days.
            if (this.stderr.length > 128 * 1024) {
                this.stderr = this.stderr.slice(-128 * 1024);
                this.stderrTruncated = true;
            }
            this.log(data.toString());
        });
        child.on('error', error => { if (this.child === child) this.fail(error.message); });
        // EPIPE can precede the final stdout reply and authentication diagnostics.
        // close drains both streams; the request deadline still bounds a stuck child.
        child.stdin.on('error', () => {});
        // Drain the final reply and SSH diagnostics before reporting shutdown.
        child.on('close', (code, signal) => {
            this.log(`Reader exited (pid ${child.pid ?? 'unavailable'}, exit ${code ?? 'unavailable'}, signal ${signal || 'none'}).`);
            if (this.child !== child) return;
            this.fail(`Bridge closed (exit ${code ?? 'unavailable'}, signal ${signal || 'none'})` +
                (bytes ? ' with an incomplete response.' : '.'));
        });
    }

    stop() {
        clearTimeout(this.timeout);
        const owned = this.child;
        this.child = undefined;
        if (owned) { owned.stdin.end(); owned.kill(); }
    }

    fail(message, retry = true, quiet = this.config.transport === 'ssh') {
        const detail = [message, this.stderrTruncated ?
            '[Earlier stderr is available in the ONPC Watch Output channel.]' : '', this.stderr].filter(Boolean).join('\n\n');
        if (this.authRefused) {
            message = 'SSH authentication or host-key verification refused; fix SSH access and click Reconnect.';
            retry = false;
        }
        const pending = this.pending;
        this.log(`${message} Reader pid ${this.child?.pid ?? 'unavailable'}.` +
            (pending ? ` Operation: ${pending.operation}; elapsed: ${Math.round(performance.now() - pending.started)} ms; received: ${pending.bytes} bytes.` : '') +
            (retry ? ` Retry in ${this.backoff} ms.` : ' Manual reconnect required.'));
        this.stop();
        this.pending = undefined;
        const error = Object.assign(new Error(message), { quiet });
        pending?.reject?.(error);
        this.artifactRequest?.reject(error);
        this.artifactRequest = undefined;
        if (pending?.action) this.results.push({ id: pending.action.id, ok: false, quiet,
            error: 'Connection lost; delivery is unknown. Review the session before sending again.' });
        for (const action of this.actions.splice(0)) this.results.push({ id: action.id, ok: false, quiet, error: 'Source disconnected; input was not sent.' });
        this.status = `Disconnected — ${message}` + (retry ? ' Retrying…' : ' Click Reconnect to try again.');
        this.retryAt = retry ? Date.now() + this.backoff : Infinity;
        this.backoff = Math.min(15000, this.backoff * 2);
        this.failureDetail = detail;
        this.staleFrames = new Set(this.frames.keys());
        // Remote connection diagnostics remain on the server cloud and in Output.
        // An unavailable server must not flash the shared infrastructure alert.
        if (this.config.transport !== 'ssh') this.reportError(`Watch connection failed: ${this.config.label}`, detail);
        this.changed();
    }

    send(request, pending = {}) {
        const line = JSON.stringify({ protocol: VERSION, ...request }) + '\n';
        if (Buffer.byteLength(line) > MAX_REQUEST) throw new Error('Watch request too large.');
        const operation = request.session_action ? `session ${request.session_action.kind}` :
            request.launcher_action ? `launcher ${request.launcher_action.kind}` :
            request.delete_run_times ? 'delete run times' : request.artifact ? 'artifact' : 'snapshot';
        this.pending = { ...pending, updates: request.updates === true, reset: request.reset === true,
            operation, started: performance.now(), bytes: 0 };
        this.timeout = setTimeout(() => this.fail('Watch request timed out.', true, true), 10000);
        this.child.stdin.write(line);
    }

    receive(value) {
        if (!this.pending) throw new Error('Unsolicited Watch response.');
        if (value?.protocol !== VERSION) throw new Error('Incompatible Watch bridge; protocol 1 required.');
        const pending = this.pending;
        if (!pending.resolve) {
            if (value.updates === true) {
                if (!pending.updates) throw new Error('Unrequested Watch updates.');
                const previousRuns = new Map(!pending.reset ? this.snapshot?.runs.map(run => [run.id, run]) : []);
                for (const run of Array.isArray(value.runs) ? value.runs : []) {
                    const previous = previousRuns.get(run?.id);
                    if (!previous || previous.run !== run.run || previous.session !== run.session) continue;
                    for (const field of RUN_BODIES) {
                        if (!Object.hasOwn(run, field) && Object.hasOwn(previous, field)) run[field] = previous[field];
                    }
                    if (run.session_view && previous.session_view && !Object.hasOwn(run.session_view, 'rows')) {
                        run.session_view.rows = previous.session_view.rows;
                    }
                }
                for (const entry of Array.isArray(value.entries) ? value.entries : []) {
                    if (!entry?.screen || Object.hasOwn(entry.screen, 'image')) continue;
                    const previous = !pending.reset && this.snapshot?.entries.find(item =>
                        item.id === entry.id && item.source === entry.source);
                    const frame = previous && this.frames.get(entry.id);
                    if (frame && frame.width === entry.screen.width && frame.height === entry.screen.height) {
                        entry.screen.image = frame.image;
                    }
                }
            }
            validate(value);
            if (pending.action ? (value.session_result?.id !== pending.action.id ||
                    typeof value.session_result.ok !== 'boolean' ||
                    (!value.session_result.ok && typeof value.session_result.error !== 'string')) : value.session_result != null) {
                throw new Error('Invalid session acknowledgement.');
            }
            const producers = new Map(this.snapshot?.entries.map(entry => [entry.id, entry.source]));
            for (const entry of value.entries) {
                if (producers.get(entry.id) !== entry.source) {
                    this.frames.delete(entry.id);
                    this.staleFrames.delete(entry.id);
                }
                if (Object.hasOwn(entry, 'screen')) {
                    this.frames.set(entry.id, entry.screen);
                    this.staleFrames.delete(entry.id);
                }
            }
            const ids = new Set(value.entries.map(entry => entry.id));
            for (const id of this.frames.keys()) if (!ids.has(id)) {
                this.frames.delete(id);
                this.staleFrames.delete(id);
            }
            this.snapshot = value;
            if (value.session_result) this.results.push(value.session_result);
        } else if (!value[pending.response || 'artifact_result']) throw new Error('Missing Watch response.');
        clearTimeout(this.timeout);
        this.pending = undefined;
        const elapsed = Math.round(performance.now() - pending.started);
        if (this.status !== 'Connected') this.log(`Connected. ${pending.operation} completed in ${elapsed} ms (${pending.bytes} bytes).`);
        else if (elapsed >= 2000) this.log(`Slow ${pending.operation}: ${elapsed} ms (${pending.bytes} bytes).`);
        this.status = 'Connected';
        this.failureDetail = undefined;
        this.retryAt = 0;
        this.backoff = 1000;
        pending.resolve?.(value[pending.response || 'artifact_result']);
        this.changed();
    }

    tick(request) {
        if (!this.child && Date.now() >= this.retryAt) this.start();
        if (!this.child || this.pending) return;
        if (this.artifactRequest) {
            const { uri, request: operation, ...pending } = this.artifactRequest;
            this.artifactRequest = undefined;
            this.send(operation || { artifact: { uri, inline: this.config.transport === 'ssh' } }, pending);
            return;
        }
        const action = this.actions.shift();
        this.send({ ...request, reset: !this.snapshot || this.status !== 'Connected',
            ...(this.snapshot?.capabilities.updates === true ? { updates: true } : {}),
            ...(action ? { session_action: action } : {}) }, { action });
    }

    artifact(uri) {
        if (!this.child || this.status !== 'Connected') return Promise.reject(
            Object.assign(new Error('Source disconnected.'), { quiet: this.config.transport === 'ssh' }));
        if (!this.snapshot.capabilities.artifacts) return Promise.reject(new Error('This adapter does not support artifacts.'));
        if (this.artifactRequest || this.pending?.resolve) return Promise.reject(new Error('Another artifact is being opened.'));
        return new Promise((resolve, reject) => { this.artifactRequest = { uri, resolve, reject }; });
    }

    deleteRunTimes(tokens) {
        if (!this.child || this.status !== 'Connected') return Promise.reject(
            Object.assign(new Error('Source disconnected.'), { quiet: this.config.transport === 'ssh' }));
        if (!this.snapshot.capabilities.delete_run_times) return Promise.reject(new Error('Update this source adapter to delete run times.'));
        if (this.artifactRequest || this.pending?.resolve) return Promise.reject(new Error('Another Watch operation is in progress.'));
        return new Promise((resolve, reject) => {
            this.artifactRequest = { request: { delete_run_times: tokens }, response: 'delete_result', resolve, reject };
        });
    }

    launcherCommand(action) {
        if (!this.child || this.status !== 'Connected') return Promise.reject(
            Object.assign(new Error('Source disconnected.'), { quiet: this.config.transport === 'ssh' }));
        if (this.artifactRequest || this.pending?.resolve) return Promise.reject(new Error('Another Watch operation is in progress.'));
        return new Promise((resolve, reject) => {
            this.artifactRequest = { request: { launcher_action: action }, response: 'launcher_result', resolve, reject };
        });
    }
}

class Bridge {
    constructor(configs, log, changed = () => {}, resourceConfigs = configs, reportError = () => {}) {
        this.revision = 0;
        this.results = [];
        this.sources = configs.map(config => {
            const source = new Source(config, log, () => {
                this.revision++;
                // Render on arrival, rather than adding another polling interval.
                queueMicrotask(() => { if (!this.closed) changed(); });
            }, reportError);
            source.results = this.results;
            return source;
        });
        this.resourceSources = resourceConfigs === configs ? this.sources : resourceConfigs.map(config =>
            new Source({ ...config, reader: 'resources' }, log, () => {
                this.revision++;
                queueMicrotask(() => { if (!this.closed) changed(); });
            }, reportError));
        this.displayedFrames = new Map();
        this.displayedRuns = new Map();
        this.links = new Map();
        this.roots = new Map();
        this.timings = new Map();
    }

    close() {
        this.closed = true;
        for (const source of new Set([...this.sources, ...this.resourceSources])) {
            source.stop();
            source.pending?.reject?.(new Error('Watch closed.'));
            source.artifactRequest?.reject(new Error('Watch closed.'));
        }
    }

    action(action) {
        const route = this.roots.get(action.root);
        const source = route?.source;
        const run = source?.snapshot?.runs.find(run => run.id === route.id);
        if (!run || source.status !== 'Connected' || run.session !== action.session || source.actions.length >= 16 ||
                (action.kind !== 'simplified' && (run.session_question || '') !== action.question) ||
                !source.snapshot.capabilities.sessions) {
            this.results.push({ id: action.id, ok: false,
                quiet: source?.config.transport === 'ssh' && source.status !== 'Connected',
                error: 'Session unavailable; review the current session before sending.' });
            this.revision++;
            return;
        }
        source.actions.push({ ...action, root: route.id });
    }

    tick(request) {
        this.sessionRoots = new Set(request.session_roots || (request.session_root ? [request.session_root] : []));
        for (const source of this.resourceSources) {
            if (this.sources.includes(source)) continue;
            if (Date.now() < (source.nextSampleAt || 0)) continue;
            source.nextSampleAt = Date.now() + 1000;
            try { source.tick({}); }
            catch (error) { source.fail(error.message); }
        }
        for (const source of this.sources) {
            const sessionRoots = [...this.sessionRoots].map(id => this.roots.get(id))
                .filter(route => route?.source === source).map(route => route.id);
            source.sessionRoot = sessionRoots.at(-1) || '';
            const scope = this.roots.get(request.scope);
            // Selection is always opaque to the renderer, decoded only here.
            const entry = source.snapshot?.entries.find(entry => key(source.config.id, entry.id) === request.selected);
            try {
                source.tick({ scope: scope?.source === source ? scope.id : 'all',
                    selected: scope && scope.source !== source ? '__hidden__' :
                        entry?.id || (['all', 'run-time'].includes(request.selected) ? request.selected : '__hidden__'),
                    ...(source.snapshot?.capabilities.session_roots === true ?
                        { session_roots: sessionRoots } : { session_root: source.sessionRoot }) });
            } catch (error) { source.fail(error.message); }
        }
    }

    snapshot(request) {
        const entries = [], runs = [], checkouts = [], hosts = [], run_times = [];
        const servers = new Map();
        this.serverErrors = new Map();
        for (const source of [...this.resourceSources, ...this.sources]) {
            if (source.config.transport !== 'ssh') continue;
            const id = key(source.config.transport, source.config.host || 'local');
            const previous = servers.get(id);
            const connected = source.status === 'Connected';
            servers.set(id, { id, label: previous?.label || source.config.host || source.config.label,
                connected: connected || Boolean(previous?.connected),
                status: connected || previous?.connected ? 'Connected' : source.status });
            if (source.failureDetail) {
                const details = this.serverErrors.get(id) || [];
                details.push(`[${source.config.label}]\n${source.failureDetail}`);
                this.serverErrors.set(id, details);
            }
        }
        for (const server of servers.values()) {
            server.failed = this.serverErrors.has(server.id);
            if (server.failed) {
                server.connected = false;
                server.status = 'Connection failed. Click the cloud icon for details.';
            }
        }
        const scope = this.roots.get(request.scope);
        let selection;
        try { selection = JSON.parse(request.selected); } catch { /* All has no source. */ }
        // A connecting source has not yet established whether its saved viewer exists.
        const awaitingSelection = Array.isArray(selection) && selection.length === 2 &&
            this.sources.some(source => source.config.id === selection[0] && !source.snapshot);
        const selected = request.selected === 'run-time' || awaitingSelection || this.sources.some(source => (!scope || scope.source === source) &&
            source.snapshot?.entries.some(entry => key(source.config.id, entry.id) === request.selected)) ? request.selected : 'all';
        const visible = new Set();
        this.links.clear(); this.roots.clear(); this.timings.clear();
        const labelSources = this.sources.length > 1 || this.sources[0].config.transport === 'ssh';
        for (const source of this.sources) {
            const { id, label } = source.config;
            const value = source.snapshot;
            const connected = source.status === 'Connected';
            if (selected === 'run-time' && (!scope || scope.source === source)) {
                for (const row of value?.run_times || []) {
                    const routeLink = uri => {
                        if (!uri) return null;
                        const token = key(id, uri);
                        this.links.set(token, { source, uri });
                        return token;
                    };
                    const deletion = connected && typeof row.delete_token === 'string' && /^[a-f0-9]{64}$/.test(row.delete_token)
                        && value.capabilities.delete_run_times ? key(id, row.delete_token) : null;
                    if (deletion) this.timings.set(deletion, { source, token: row.delete_token });
                    run_times.push({ ...row, delete_token: deletion, source_id: id, case_link: routeLink(row.case_link),
                        recording: routeLink(row.recording) });
                }
            }
            const rows = rows => (rows || []).map(row => row.map(part => {
                if (!part.link) return part;
                const token = key(id, part.link);
                this.links.set(token, { source, uri: part.link });
                return { ...part, link: token };
            }));
            for (const checkout of value?.checkouts || []) {
                const route = key(id, checkout.id);
                this.roots.set(route, { source, id: checkout.id });
                checkouts.push({ ...checkout, id: route, label: labelSources ? `[${label}] ${checkout.label}` : checkout.label });
            }
            for (const run of value?.runs || []) {
                const route = key(id, run.id);
                this.roots.set(route, { source, id: run.id });
                const sessionView = this.sessionRoots?.has(route) &&
                    value.capabilities.session_roots !== true && run.id !== source.sessionRoot ?
                    { rows: [[{ text: 'Update this source adapter to view multiple sessions.' }]],
                        input_enabled: false, unavailable: true, simplified: false, model: '' } : run.session_view;
                runs.push({ ...run, id: route,
                    launcher_controls: connected && run.launcher_controls === true,
                    transport: source.config.transport,
                    server: source.config.transport === 'ssh' ? source.config.host : 'local',
                    // Retain presentation through retries; input still requires a live reader.
                    connected,
                    session_active: connected && run.session_active,
                    session_waiting: connected && run.session_waiting,
                    session_view: sessionView && { ...sessionView,
                        input_enabled: connected && sessionView.input_enabled,
                        rows: rows(sessionView.rows) },
                    session_preview: run.session_preview && rows(run.session_preview),
                    launcher_rows: run.launcher_rows && rows(run.launcher_rows),
                    rows: rows(run.rows), error_rows: rows(run.error_rows) });
            }
            for (const entry of value?.entries || []) {
                if (scope && scope.source !== source) continue;
                const route = key(id, entry.id);
                const frame = source.frames.get(entry.id);
                const previous = this.displayedFrames.get(route);
                const changed = request.reset || previous?.frame !== frame || previous?.source !== entry.source;
                const shown = selected === 'all' ? entry.active : selected === route;
                if (shown) {
                    visible.add(route);
                    if (changed) this.displayedFrames.set(route, { frame, source: entry.source });
                }
                const { screen: _screen, ...metadata } = entry;
                const staleFrame = frame && (!connected || source.staleFrames.has(entry.id));
                entries.push({ ...metadata, id: route, source: key(id, entry.source),
                    transport: source.config.transport,
                    server: source.config.transport === 'ssh' ? source.config.host : 'local',
                    title_label: entry.label,
                    label: (labelSources ? `[${label}] ` : '') + entry.label,
                    status: (connected ? entry.status : source.status) +
                        (staleFrame ? ' Waiting for fresh frame; showing last received frame.' : ''),
                    memory: connected || !entry.memory ? entry.memory :
                        { ...entry.memory, text: '—', sample: `stale:${entry.memory.sample}` },
                    ...(shown && changed ? { screen: frame && !request.reset && previous?.source === entry.source &&
                        previous.frame?.image === frame.image && previous.frame.width === frame.width &&
                        previous.frame.height === frame.height ?
                        { width: frame.width, height: frame.height, ...(frame.cursor ? { cursor: frame.cursor } : {}) } :
                        frame || null } : {}) });
            }
        }
        for (const source of this.resourceSources) {
            const connected = source.status === 'Connected';
            hosts.push({ id: source.config.id, label: source.config.label, status: source.status, connected,
                transport: source.config.transport,
                resources: connected ? source.snapshot?.resources || '' : '',
                sample: connected ? source.snapshot?.resource_sample : null,
                charts: (source.snapshot?.resource_charts || []).map(chart => connected ? chart : { ...chart, text: '—' }) });
        }
        for (const id of this.displayedFrames.keys()) if (!visible.has(id)) this.displayedFrames.delete(id);
        const latestTimes = new Map();
        for (const row of run_times) {
            const id = JSON.stringify([row.source_id, row.category, row.id, row.vm]);
            const previous = latestTimes.get(id);
            const delete_tokens = [...(previous?.delete_tokens || []), ...(row.delete_token ? [row.delete_token] : [])];
            const latest = !previous || row.completed_at > previous.completed_at ? row : previous;
            latestTimes.set(id, { ...latest, delete_tokens,
                deletable: (previous?.deletable ?? true) && Boolean(row.delete_token) });
        }
        const times = [...latestTimes.values()].sort((a, b) => b.seconds - a.seconds || a.title.localeCompare(b.title));
        const previousRuns = request.reset ? new Map() : this.displayedRuns;
        this.displayedRuns = new Map(runs.map(run => [run.id, run]));
        const updates = runs.map(run => {
            const previous = previousRuns.get(run.id);
            const update = { ...run };
            if (previous && previous.run === run.run && previous.session === run.session) {
                for (const field of RUN_BODIES) {
                    if (isDeepStrictEqual(run[field], previous[field])) delete update[field];
                }
                if (run.session_view && previous.session_view &&
                        isDeepStrictEqual(run.session_view.rows, previous.session_view.rows)) {
                    const { rows, ...view } = run.session_view;
                    update.session_view = view;
                }
            }
            return update;
        });
        const connections = this.sources.map(source => ({ label: source.config.label,
            status: source.status, connected: source.status === 'Connected',
            retrying: Number.isFinite(source.retryAt), failed: Boolean(source.failureDetail) }));
        return { entries, runs: updates, checkouts, hosts, servers: [...servers.values()], connections, run_times: times,
            scope: checkouts.some(checkout => checkout.id === request.scope) ? request.scope : 'all',
            selected,
            session_results: this.results.splice(0) };
    }

    async artifact(token) {
        const route = this.links.get(token);
        if (!route) throw new Error('Artifact is no longer published by the displayed source.');
        return { result: await route.source.artifact(route.uri), remote: route.source.config.transport === 'ssh' };
    }

    async launcherCommand(root, run, kind) {
        const route = this.roots.get(root);
        const current = route?.source.snapshot?.runs.find(item => item.id === route.id);
        if (!['stop', 'cancel-stop', 'resume', 'reload', 'kill', 'add-session'].includes(kind) || !current?.launcher_controls || current.run !== run ||
                (kind === 'add-session' && !current.launcher_add_session_command) ||
                (kind === 'reload' && !current.launcher_reload_command) ||
                (kind === 'kill' && !current.launcher_kill)) {
            throw new Error('Launcher changed; refresh before trying again.');
        }
        const result = await route.source.launcherCommand({ root: route.id, run, kind });
        if (result.ok !== true) throw new Error(result.error || 'Launcher command unavailable.');
        if (typeof result.root !== 'string' || typeof result.run !== 'string' ||
                typeof result.launcher !== 'string' || !/^[\w.-]{1,100}$/.test(result.launcher) ||
                !Array.isArray(result.argv) || result.argv.some(arg => typeof arg !== 'string' || arg.includes('\0'))) {
            throw new Error('Invalid launcher command.');
        }
        return { ...result, source: route.source.config };
    }

    async deleteRunTimes(tokens) {
        if (!Array.isArray(tokens) || !tokens.length || tokens.length > 4096 ||
                tokens.some(token => !this.timings.has(token))) throw new Error('Run times changed; refresh before deleting.');
        const groups = new Map();
        for (const token of new Set(tokens)) {
            const route = this.timings.get(token);
            if (!groups.has(route.source)) groups.set(route.source, []);
            groups.get(route.source).push(route.token);
        }
        for (const [source, ids] of groups) {
            const result = await source.deleteRunTimes(ids);
            // Do not publish the old rows while awaiting the next fresh snapshot.
            source.snapshot.run_times = [];
            this.revision++;
            if (result.ok !== true) throw new Error(result.error || 'Cannot delete run times.');
        }
    }
}

module.exports = { Bridge, configuration, resourceConfiguration };
