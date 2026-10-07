import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import {showReminderBanner} from './reminderBanner.js';
import {TranslationContext} from './localization.js';

const NAME = 'com.puffyslippers.OhNoParentControl.ReminderPreview';
const PATH = '/com/puffyslippers/OhNoParentControl/ReminderPreview';
const XML = `<node><interface name="${NAME}">
<method name="Preview"><arg type="s" direction="in"/><arg type="u" direction="in"/>
<arg type="u" direction="out"/></method>
<method name="PreviewTimed"><arg type="s" direction="in"/><arg type="u" direction="in"/>
<arg type="u" direction="in"/><arg type="u" direction="out"/></method>
<method name="PreviewLocalized"><arg type="s" direction="in"/><arg type="u" direction="in"/>
<arg type="u" direction="in"/><arg type="s" direction="in"/>
<arg type="u" direction="out"/></method>
<method name="Close"><arg type="u" direction="in"/></method>
</interface></node>`;

/** Same-user editor delivery through the real countdown banner renderer. */
export class ReminderPreview {
    constructor(title, logoPath, translations, openPreferences) {
        this.title = title;
        this.translations = translations;
        this.openPreferences = openPreferences;
        this.icon = new Gio.FileIcon({file: Gio.File.new_for_path(logoPath)});
        this.current = null;
        this.serial = 0;
        this.pending = 0;
        this.closed = false;
        this.active = false;
        this.watch = 0;
        this.owner = 0;
        this.connection = Gio.DBus.session;
        this.uid = Gio.Credentials.new().get_unix_user();
        this.cancellable = new Gio.Cancellable();
        this.exported = Gio.DBusExportedObject.wrapJSObject(XML, this);
        try {
            this.exported.export(this.connection, PATH);
            this.owner = Gio.bus_own_name_on_connection(this.connection, NAME,
                Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                () => { if (!this.closed) this.active = true; }, () => this.close());
        } catch (error) {
            this.close();
            throw error;
        }
    }

    PreviewAsync([body, replaces], invocation) {
        this.PreviewTimedAsync([body, replaces, 0], invocation);
    }

    PreviewTimedAsync([body, replaces, seconds], invocation) {
        this._preview(body, replaces, seconds, null, invocation);
    }

    PreviewLocalizedAsync([body, replaces, seconds, language], invocation) {
        this._preview(body, replaces, seconds, language, invocation);
    }

    _preview(body, replaces, seconds, language, invocation) {
        if (body.length > 8192 || Array.from(body).length > 4096 || body.includes('\0') ||
            (language !== null && (language.length > 32 || language.includes('\0')))) {
            invocation.return_dbus_error(`${NAME}.InvalidArgument`, 'Invalid preview');
            return;
        }
        this._dispatch(invocation, sender => {
            if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
                throw new Error('Unavailable');
            const identity = this.current?.sender === sender && this.current.id === replaces
                ? replaces : ++this.serial;
            // The editor can have a newer language than the panel's cache.
            // Keep this preview's context private so unsaved choices cannot
            // change the panel or real reminders.
            let translations = this.translations;
            if (language !== null) {
                translations = new TranslationContext(this.translations.directory);
                translations.apply(language);
            }
            this.dismiss();
            const banner = showReminderBanner(this.title, this.icon, body, MessageTray.Urgency.CRITICAL,
                seconds, translations, this.openPreferences);
            this.current = {...banner, sender, id: identity};
            banner.source.connect('destroy', () => {
                if (this.current?.source === banner.source) this.dismiss(false);
            });
            this.watch = Gio.bus_watch_name_on_connection(this.connection, sender,
                Gio.BusNameWatcherFlags.NONE, null, () => {
                    if (this.current?.source === banner.source) this.dismiss();
                });
            return new GLib.Variant('(u)', [identity]);
        });
    }

    CloseAsync([identity], invocation) {
        this._dispatch(invocation, sender => {
            if (this.current?.sender === sender && this.current.id === identity) this.dismiss();
            return null;
        });
    }

    _dispatch(invocation, operation) {
        if (this.closed || this.pending >= 16) {
            invocation.return_dbus_error(`${NAME}.Unavailable`, 'Preview unavailable');
            return;
        }
        const sender = invocation.get_sender();
        this.connection.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'GetConnectionUnixUser', new GLib.Variant('(s)', [sender]),
            new GLib.VariantType('(u)'), Gio.DBusCallFlags.NONE, 3000, this.cancellable,
            (connection, result) => {
                try {
                    const [uid] = connection.call_finish(result).deep_unpack();
                    if (uid !== this.uid || this.closed || !this.active) throw new Error('Unavailable');
                    invocation.return_value(operation(sender));
                } catch (_error) {
                    invocation.return_dbus_error(`${NAME}.Unavailable`, 'Preview unavailable');
                } finally {
                    this.pending--;
                }
            });
        this.pending++;
    }

    dismiss(destroySource = true) {
        const current = this.current;
        this.current = null;
        if (this.watch) Gio.bus_unwatch_name(this.watch);
        this.watch = 0;
        if (destroySource) current?.source.destroy();
    }

    close() {
        if (this.closed) return;
        this.closed = true;
        this.active = false;
        this.cancellable.cancel();
        this.dismiss();
        this.exported.unexport();
        if (this.owner) Gio.bus_unown_name(this.owner);
        this.owner = 0;
    }
}
