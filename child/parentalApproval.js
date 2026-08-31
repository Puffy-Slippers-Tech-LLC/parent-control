import Gio from 'gi://Gio';
import Polkit from 'gi://Polkit';

import {logError, logInfo, logWarning} from './logger.js';
const APPROVAL_ACTION =
    'org.gnome.shell.extensions.oh-no-parent-control.ApproveTimeAndApps';

export class ParentalApproval {
    constructor() {
        this._authority = Polkit.Authority.get_sync(null);
    }

    ensureAuthorization(actionId = APPROVAL_ACTION) {
        logInfo('requesting administrator authorization');
        return new Promise((resolve, reject) => {
            let subject;
            try {
                const busName = Gio.DBus.system.get_unique_name();
                if (!busName)
                    throw new Error('system bus connection has no unique name');
                // AccountsService sees both subsequent property writes from
                // this exact system-bus subject.
                subject = new Polkit.SystemBusName({name: busName});
            } catch (error) {
                logWarning(`polkit subject setup failed: ${error.message}`);
                reject(new Error(`Could not identify polkit subject: ${error.message}`));
                return;
            }

            this._authority.check_authorization(
                subject,
                actionId,
                new Polkit.Details(),
                Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
                null,
                (authority, result) => {
                    try {
                        const authorization =
                            authority.check_authorization_finish(result);
                        if (authorization.get_is_authorized()) {
                            const temporaryAuthorizationId =
                                authorization.get_temporary_authorization_id();
                            if (!temporaryAuthorizationId) {
                                reject(new Error(
                                    'Combined authorization was not retained'));
                                return;
                            }
                            logInfo('combined time/app approval authorized');
                            resolve(temporaryAuthorizationId);
                            return;
                        }

                        reject(new Error(
                            authorization.get_is_challenge()
                                ? 'Parent authentication was dismissed'
                                : 'Parent did not authorize the request'));
                    } catch (error) {
                        logError(`authorization failed: ${error.message}`);
                        reject(error);
                    }
                });
        });
    }

    async withAuthorization(callback, actionId = APPROVAL_ACTION) {
        if (typeof callback !== 'function')
            throw new Error('Authorized operation must be a function');

        const temporaryAuthorizationId =
            await this.ensureAuthorization(actionId);
        try {
            return await callback();
        } finally {
            if (temporaryAuthorizationId)
                await this._revokeAuthorization(temporaryAuthorizationId);
        }
    }

    _revokeAuthorization(authorizationId) {
        return new Promise(resolve => {
            this._authority.revoke_temporary_authorization_by_id(
                authorizationId,
                null,
                (authority, result) => {
                    try {
                        authority.revoke_temporary_authorization_by_id_finish(result);
                        logInfo('combined authorization released');
                    } catch (error) {
                        // The grant is scoped to this process and Polkit will
                        // expire it even if an explicit cleanup races shutdown.
                        logWarning(
                            'could not release combined authorization: ' +
                            error.message);
                    }
                    resolve();
                });
        });
    }
}
