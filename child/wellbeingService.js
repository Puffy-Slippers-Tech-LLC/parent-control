// Unprivileged session service. No broker calls, enforcement writes or Shell imports.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import System from 'system';
import {WellbeingLeases} from './wellbeingLogic.mjs';

const BUS = 'com.puffyslippers.OhNoParentControl.Wellbeing';
const PATH = '/com/puffyslippers/OhNoParentControl/Wellbeing';
const XML = `<node><interface name="${BUS}"><method name="SetWindow">
    <arg name="token" type="s" direction="in"/>
    <arg name="end" type="d" direction="in"/>
    </method></interface></node>`;
const KEY = 'show-banners';
const BACKUP = 'wellbeing-banner-backup';
// Call sites pass only shipped literals, never sender/token, settings paths,
// request deadlines, or exception text. Repeated failures are bounded per stage.
const failures = new Set();
function observe(stage, outcome) {
    if (outcome === 'failed') {
        if (failures.has(stage)) return;
        failures.add(stage);
        console.warn(`onpc.child Wellbeing stage=${stage} outcome=${outcome}`);
    } else {
        failures.delete(stage);
        console.log(`onpc.child Wellbeing stage=${stage} outcome=${outcome}`);
    }
}
observe('service-start', 'complete');
function unavailable(stage) {
    observe(stage, 'failed');
    throw new Error('Wellbeing settings unavailable');
}
let journal, banners;
try {
    const directory = Gio.File.new_for_uri(import.meta.url).get_parent().get_child('schemas').get_path();
    const schema = Gio.SettingsSchemaSource.new_from_directory(directory,
        Gio.SettingsSchemaSource.get_default(), false).lookup(
        'com.puffyslippers.oh-no-parent-control.child', false);
    journal = new Gio.Settings({settings_schema: schema});
    banners = new Gio.Settings({schema_id: 'org.gnome.desktop.notifications.application',
        path: '/org/gnome/desktop/notifications/application/gnome-wellbeing-panel/'});
    observe('settings-initialize', 'complete');
} catch (_error) {
    observe('settings-initialize', 'failed');
    System.exit(1);
}
function originalValue() {
    const value = banners.get_user_value(KEY);
    return value === null ? 'default' : String(value.get_boolean());
}
const settings = {
    backup: () => journal.get_string(BACKUP),
    original: () => {
        if (!banners.is_writable(KEY)) unavailable('banner-read-locked');
        return originalValue();
    },
    saveBackup: value => {
        if (!journal.set_string(BACKUP, value)) unavailable('recovery-write');
        Gio.Settings.sync();
        if (journal.get_string(BACKUP) !== value) unavailable('recovery-verification');
    },
    suppress: () => {
        if (!banners.is_writable(KEY)) unavailable('banner-suppress-locked');
        if (!banners.set_boolean(KEY, false)) unavailable('banner-write');
        Gio.Settings.sync();
        if (banners.get_boolean(KEY)) unavailable('banner-verification');
    },
    restore: value => {
        if (!banners.is_writable(KEY)) unavailable('banner-restore-locked');
        if (value === 'default') banners.reset(KEY);
        else if (!banners.set_boolean(KEY, value === 'true'))
            unavailable('banner-restore-write');
        Gio.Settings.sync();
        if (originalValue() !== value) unavailable('banner-restore-verification');
    },
    sync: () => Gio.Settings.sync(),
};
const leases = new WellbeingLeases(settings, () => GLib.get_real_time() / 1e6,
    () => GLib.get_monotonic_time() / 1e6, observe);
const loop = new GLib.MainLoop(null, false);
const watches = new Map();
let owned = false;
let exported;
let timer = 0;
let failed = false;

function senderLeases(sender) {
    return [...leases.leases.keys()].filter(key => key.startsWith(`${sender}/`));
}

function reconcile() {
    try {
        leases.expire();
        if (failed) observe('recovery-retry', 'complete');
        failed = false;
    } catch (_error) {
        // Fixed text only; retain recovery state and retry after write failures.
        if (!failed) observe('recovery-retry', 'failed');
        failed = true;
    }
    for (const [sender, watch] of watches) {
        if (!senderLeases(sender).length) {
            Gio.bus_unwatch_name(watch);
            watches.delete(sender);
        }
    }
    if (leases.leases.size || settings.backup() !== '') return GLib.SOURCE_CONTINUE;
    return GLib.SOURCE_REMOVE;
}

function ensureTimer() {
    if (!timer) timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
        const keep = reconcile();
        if (!keep) timer = 0;
        return keep;
    });
}

function stop() {
    if (owned) {
        try { leases.close(); } catch (_error) { observe('shutdown-recovery-retained', 'failed'); }
    }
    loop.quit();
    return GLib.SOURCE_REMOVE;
}

const owner = Gio.bus_own_name(Gio.BusType.SESSION, BUS, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
    null, connection => {
        owned = true;
        observe('bus-acquired', 'complete');
        reconcile(); // Recover a previous process before accepting new leases.
        if (settings.backup() !== '') ensureTimer();
        exported = Gio.DBusExportedObject.wrapJSObject(XML, {
            SetWindowAsync([token, end], invocation) {
                const sender = invocation.get_sender();
                try {
                    // A fresh enable has its own lease, so a late cancellation
                    // from the previous extension instance cannot release it.
                    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(token)) {
                        observe('lease-token', 'invalid');
                        throw new Error('Invalid lease token');
                    }
                    const key = `${sender}/${token}`;
                    if (end !== 0 && !leases.leases.has(key) && leases.leases.size >= 64) {
                        observe('lease-capacity', 'failed');
                        throw new Error('Too many leases');
                    }
                    leases.set(key, end);
                    if (senderLeases(sender).length && !watches.has(sender)) {
                        watches.set(sender, Gio.bus_watch_name_on_connection(connection, sender,
                            Gio.BusNameWatcherFlags.NONE, null, () => {
                                observe('sender-disconnected', 'complete');
                                for (const ownedKey of senderLeases(sender))
                                    leases.leases.delete(ownedKey);
                                reconcile();
                                ensureTimer();
                            }));
                    }
                    invocation.return_value(null);
                    observe('request', 'complete');
                } catch (_error) {
                    observe('request', 'failed');
                    invocation.return_dbus_error(`${BUS}.Unavailable`,
                        'Wellbeing banner suppression unavailable');
                } finally {
                    ensureTimer();
                }
            },
        });
        exported.export(connection, PATH);
    }, () => {
        observe('bus-lost', owned ? 'failed' : 'unavailable');
        stop();
        // A bus failure while owning the setting must trigger systemd recovery.
        if (owned) System.exit(1);
    });
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 15, stop);
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 2, stop);
loop.run();
exported?.unexport();
Gio.bus_unown_name(owner);
