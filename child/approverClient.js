import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {isPreview} from './previewMode.js';

const BUS_NAME = 'com.puffyslippers.OhNoParentControl1';
const OBJECT_PATH = '/com/puffyslippers/OhNoParentControl1';

export function listApprovers() {
    if (isPreview())
        return Promise.resolve([
            [1001, 'Daddy'],
            [1002, 'Mommy'],
        ]);

    return new Promise((resolve, reject) => {
        Gio.DBus.system.call(
            BUS_NAME, OBJECT_PATH, BUS_NAME, 'ListApprovers', null,
            new GLib.VariantType('(a(us))'), Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    const users = connection.call_finish(result).deepUnpack()[0];
                    if (!Array.isArray(users) || users.some(([uid, label]) =>
                        !Number.isSafeInteger(uid) || uid < 0 ||
                        typeof label !== 'string' || !label.trim())) {
                        throw new Error('Broker returned invalid approving administrators');
                    }
                    resolve(users.map(([uid, label]) => [uid, label.trim()]));
                } catch (error) {
                    reject(error);
                }
            });
    });
}
