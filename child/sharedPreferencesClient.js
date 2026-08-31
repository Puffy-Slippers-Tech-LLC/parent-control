import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';
const INTERFACE = BUS_NAME;
const ACCOUNTS_NAME = 'org.freedesktop.Accounts';
const ACCOUNTS_PATH = '/org/freedesktop/Accounts';
const ACCOUNTS_INTERFACE = 'org.freedesktop.Accounts';

const DEFAULTS = Object.freeze({
    version: 1,
    parent_control_enabled: true,
    apps: {},
    request: {
        last_selected_duration: '1800',
        last_custom_minutes: 0.1,
        allow_soft_blocked_apps: false,
    },
});

let cache = JSON.parse(JSON.stringify(DEFAULTS));
let uid = null;

function call(name, path, interfaceName, method, parameters, replyType) {
    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            name, path, interfaceName, method, parameters,
            new GLib.VariantType(replyType), Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    resolve(connection.call_finish(result));
                } catch (error) {
                    reject(error);
                }
            });
    });
}

async function ownUid() {
    if (uid !== null)
        return uid;
    const reply = await call(
        ACCOUNTS_NAME, ACCOUNTS_PATH, ACCOUNTS_INTERFACE, 'FindUserByName',
        new GLib.Variant('(s)', [GLib.get_user_name()]), '(o)');
    const path = reply.deepUnpack()[0];
    const match = path.match(/^\/org\/freedesktop\/Accounts\/User(\d+)$/);
    if (!match)
        throw new Error('AccountsService returned an invalid user path');
    uid = Number(match[1]);
    return uid;
}

export function getSharedPreferences() {
    return cache;
}

export async function refreshSharedPreferences() {
    const targetUid = await ownUid();
    const reply = await call(
        BUS_NAME, OBJECT_PATH, INTERFACE, 'GetPreferences',
        new GLib.Variant('(u)', [targetUid]), '(s)');
    cache = JSON.parse(reply.deepUnpack()[0]);
    return cache;
}

export async function updateSharedRequestPreferences(selected, custom, allowSoft) {
    const targetUid = await ownUid();
    const reply = await call(
        BUS_NAME, OBJECT_PATH, INTERFACE, 'UpdateRequestPreferences',
        new GLib.Variant('(usdb)', [targetUid, selected, custom, allowSoft]), '(s)');
    cache = JSON.parse(reply.deepUnpack()[0]);
    return cache;
}
