import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {wellbeingWindowEnd} from './wellbeingLogic.mjs';

const BUS = 'com.puffyslippers.OhNoParentControl.Wellbeing';
const PATH = '/com/puffyslippers/OhNoParentControl/Wellbeing';

export class WellbeingSuppression {
    constructor(manager, sessionMode, preferences, onError, observe = () => {}) {
        this.manager = manager;
        this.sessionMode = sessionMode;
        this.preferences = preferences;
        this.onError = onError;
        this.observe = observe;
        this.token = GLib.uuid_string_random();
        this.connections = [];
        this.desired = 0;
        this.sent = 0;
        this.pending = false;
        this.closed = false;
        this.owner = null;
        this.generation = 0;
        try {
            this.watch = Gio.bus_watch_name_on_connection(Gio.DBus.session, BUS,
                Gio.BusNameWatcherFlags.NONE,
                (_connection, _name, owner) => this.ownerChanged(owner),
                () => this.ownerChanged(null));
            for (const signal of ['notify::state', 'notify::daily-limit-time',
                'notify::daily-limit-enabled'])
                this.connections.push([manager, manager.connect(signal, () => this.update())]);
            this.connections.push([sessionMode, sessionMode.connect('updated', () => this.update())]);
            // Own scheduling: panel cadence, asynchronous broker estimates and
            // reminder thresholds must not determine this suppression window.
            this.timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
                this.update();
                return GLib.SOURCE_CONTINUE;
            });
            this.update();
        } catch (error) {
            this.event('startup', 'failed');
            this.close();
            throw error;
        }
    }

    event(stage, outcome) {
        try { this.observe(stage, outcome); } catch (_error) { /* best effort */ }
    }

    ownerChanged(owner) {
        if (this.closed || this.owner === owner) return;
        this.owner = owner;
        this.event('helper-owner', owner === null ? 'unavailable' : 'complete');
        this.generation++;
        // Acknowledgements belong to one helper process. A vanished owner
        // has no leases; a new owner must receive the current eligible window.
        this.sent = owner === null ? 0 : null;
        this.update();
    }

    update() {
        if (this.closed) return;
        try {
            const previous = this.desired;
            this.desired = wellbeingWindowEnd(this.manager, this.preferences(),
                this.sessionMode.isLocked || this.sessionMode.isGreeter);
            if (previous !== this.desired)
                this.event('window', this.desired === 0 ? 'released' : 'eligible');
            this.flush();
        } catch (error) {
            this.event('window', 'failed');
            this.desired = 0;
            this.report(error);
            this.flush();
        }
    }

    report(error) {
        if (this.reported) return;
        this.reported = true;
        // Error reporting itself must not escape into a Shell enforcement signal.
        try { this.onError?.(error); } catch (_error) { this.event('error-report', 'failed'); }
    }

    flush() {
        if (this.pending || this.desired === this.sent) return;
        const requested = this.desired;
        const generation = this.generation;
        this.pending = true;
        this.event(requested === 0 ? 'release-request' : 'acquire-request', 'started');
        try {
            // Pin known owners so a replacement cannot inherit a queued call.
            // Only acquisition may activate a service; shutdown never does.
            Gio.DBus.session.call(this.owner ?? BUS, PATH, BUS, 'SetWindow',
                new GLib.Variant('(sd)', [this.token, requested]), null,
                requested === 0 ? Gio.DBusCallFlags.NO_AUTO_START : Gio.DBusCallFlags.NONE,
                2000, null, (connection, result) => {
                    this.pending = false;
                    try {
                        connection.call_finish(result);
                        this.event(requested === 0 ? 'release-request' : 'acquire-request',
                            generation === this.generation ? 'complete' : 'stale');
                        if (generation === this.generation) this.sent = requested;
                    } catch (error) {
                        this.event(requested === 0 ? 'release-request' : 'acquire-request', 'failed');
                        // A timed-out call may have applied. Ensure cancellation
                        // is still sent, and otherwise retry on the next tick.
                        if (generation === this.generation) this.sent = null;
                        this.report(error);
                    }
                    if (this.closed) {
                        // Even an uncertain acquisition must be followed by a
                        // cancellation, after its reply, using this instance token.
                        if (requested !== 0) {
                            this.sent = null;
                            this.flush();
                        }
                    } else if (generation !== this.generation || this.desired !== requested) {
                        this.update();
                    }
                });
        } catch (error) {
            this.event('request-dispatch', 'failed');
            this.pending = false;
            this.sent = null;
            this.report(error);
        }
    }

    close() {
        if (this.closed) return;
        this.closed = true;
        this.event('shutdown', this.pending ? 'pending' : 'complete');
        if (this.watch) Gio.bus_unwatch_name(this.watch);
        this.watch = 0;
        if (this.timer) GLib.source_remove(this.timer);
        this.timer = 0;
        for (const [object, id] of this.connections) object.disconnect(id);
        this.connections = [];
        this.desired = 0;
        // Do not cancel an in-flight call: serialize restoration after its reply.
        // Owner loss and the helper's own deadline also release the override.
        this.flush();
    }
}
