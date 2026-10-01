// Development entry point. The preview launcher supplies productionExtension.js
// from the real extension source inside its disposable extension directory.
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import OhNoParentControlExtension from './productionExtension.js';
import {appLogoPath} from './branding.js';
import {previewGenerationMarker, previewStartsWithRequestOpen} from './previewMode.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';

export default class PreviewExtension extends OhNoParentControlExtension {
    _refreshLanguage() {
        if (!this._translations || this._translations.closed)
            return;
        try {
            const path = GLib.getenv('OH_NO_PARENT_CONTROL_PREVIEW_LANGUAGE_FILE');
            if (!path)
                throw new Error('The preview requires its own language state');
            let language = '';
            try {
                const [, bytes] = Gio.File.new_for_path(path).load_contents(null);
                language = new TextDecoder().decode(bytes);
            } catch (error) {
                if (!error.matches?.(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND))
                    throw error;
            }
            this._translations.apply(language);
            this._indicator?.refreshLanguage();
        } catch (error) {
            this._errors?.report(error);
        }
    }

    _requestAppArgv() {
        const override = GLib.getenv('OH_NO_PARENT_CONTROL_REQUEST_APP');
        if (!override)
            throw new Error('The preview requires its own request-app command');
        const [ok, argv] = GLib.shell_parse_argv(override);
        if (!ok || !argv.length)
            throw new Error('OH_NO_PARENT_CONTROL_REQUEST_APP is not a command');
        return argv;
    }

    _createIndicator() {
        return new RemainingTimeIndicator(
            () => this._showRequest(), 45 * 60, true, this._appName,
            previewGenerationMarker(), appLogoPath(this), this._settings,
            error => this._errors.report(error), this._translations,
            () => this._refreshLanguage());
    }

    _enable() {
        super._enable();
        if (previewStartsWithRequestOpen()) {
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                this._showRequest();
                return GLib.SOURCE_REMOVE;
            });
        }
    }
}
