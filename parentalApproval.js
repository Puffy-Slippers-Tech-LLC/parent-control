import Gio from 'gi://Gio';
import Polkit from 'gi://Polkit';

const LOG_PREFIX = '[request-more-time]';
const APPROVAL_ACTION =
    'org.gnome.shell.extensions.request-more-time.ApproveTimeAndApps';

export class ParentalApproval {
    constructor() {
        this._authority = Polkit.Authority.get_sync(null);
    }

    ensureAuthorization(actionId = APPROVAL_ACTION) {
        console.log(`${LOG_PREFIX} requesting administrator authorization`);
        return new Promise((resolve, reject) => {
            let subject;
            try {
                const busName = Gio.DBus.system.get_unique_name();
                if (!busName)
                    throw new Error('system bus connection has no unique name');
                subject = new Polkit.SystemBusName({
                    name: busName,
                });
            } catch (error) {
                console.warn(`${LOG_PREFIX} polkit subject setup failed: ${error.message}`);
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
                            console.log(
                                `${LOG_PREFIX} combined time/app approval authorized`);
                            resolve();
                            return;
                        }

                        reject(new Error(
                            authorization.get_is_challenge()
                                ? 'Parent authentication was dismissed'
                                : 'Parent did not authorize the request'));
                    } catch (error) {
                        console.error(`${LOG_PREFIX} authorization failed: ${error.message}`);
                        reject(error);
                    }
                });
        });
    }
}
