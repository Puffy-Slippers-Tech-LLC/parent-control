import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Catalogue} from './gettext.mjs';
import {supportedLanguage} from './languages.mjs';

const DOMAIN = 'oh-no-parent-control';
const BUS = 'com.puffyslippers.OhNoParentControl1';

function read(path) {
    const [, bytes] = Gio.File.new_for_path(path).load_contents(null);
    return bytes;
}

export class TranslationContext {
    constructor(directory) {
        this.directory = directory;
        this.sources = JSON.parse(new TextDecoder().decode(read(`${directory}/messages.json`)));
        this.languages = JSON.parse(new TextDecoder().decode(read(`${directory}/languages.json`)));
        this.catalogue = new Catalogue();
        this.closed = false;
        this.pending = false;
        this.apply('');
    }

    apply(saved) {
        const locale = saved || GLib.get_language_names()[0] || 'en';
        const id = supportedLanguage(locale, this.languages);
        const path = `${this.directory}/locale/${id.replaceAll('-', '_')}/LC_MESSAGES/${DOMAIN}.mo`;
        let catalogue;
        try {
            catalogue = new Catalogue(read(path));
        } catch (error) {
            if (!error.matches?.(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND)) throw error;
            catalogue = new Catalogue();
        }
        this.catalogue = catalogue;
        this.language = id;
        this.direction = this.languages.find(language => language.id === id)?.direction ?? 'ltr';
    }

    refresh(changed, failed) {
        if (this.closed || this.pending) return;
        this.pending = true;
        Gio.DBus.system.call(BUS, '/com/puffyslippers/OhNoParentControl1', BUS,
            'GetOwnLanguage', null, new GLib.VariantType('(s)'), Gio.DBusCallFlags.NONE,
            30000, null, (connection, result) => {
                this.pending = false;
                if (this.closed) return;
                try {
                    const [language] = connection.call_finish(result).deep_unpack();
                    this.apply(language);
                    changed();
                } catch (error) { failed(error); }
            });
    }

    text(key, values = {}) {
        const source = this.sources[key];
        if (!source) throw new Error('Unknown presentation message');
        const translated = Array.isArray(source)
            ? this.catalogue.ngettext(source[0], source[1], values.count)
            : this.catalogue.gettext(source);
        return translated.replace(/%\(([^)]+)\)([sdg])/g, (_all, name, format) => {
            if (!(name in values)) throw new Error('Missing presentation operand');
            if (format !== 's' && !Number.isFinite(values[name]))
                throw new Error('Invalid presentation operand');
            return String(format === 'd' ? Math.trunc(values[name]) : values[name]);
        });
    }
}
