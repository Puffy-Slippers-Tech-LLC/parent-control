// Development entry point. The preview launcher supplies productionExtension.js
// from the real extension source inside its disposable extension directory.
import GLib from 'gi://GLib';

import OhNoParentControlExtension from './productionExtension.js';
import {appLogoPath} from './branding.js';
import {previewGenerationMarker, previewStartsWithRequestOpen} from './previewMode.js';
import {RemainingTimeIndicator} from './remainingTimeIndicator.js';

export default class PreviewExtension extends OhNoParentControlExtension {
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
            error => this._errors.report(error));
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
