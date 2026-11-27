"""Real host-desktop authentication for interactive preview requests."""

import grp
import os
import platform
import pwd

from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.approval_prompt import format_approval_message
from common.oh_no_parent_control_ui.localization import load_translations
from common.oh_no_parent_control_ui.test_identities import TEST_IDENTITIES

NAME = 'org.freedesktop.PolicyKit1'
PATH = '/org/freedesktop/PolicyKit1/Authority'
INTERFACE = NAME + '.Authority'
ACTION = 'com.puffyslippers.onpc.preview.approve'


def host_approver(approver_uid):
    """Resolve a preview parent to a real administrator for PolicyKit."""
    fixture = next((identity for identity in TEST_IDENTITIES
                    if identity.role == 'administrator' and identity.preview_uid == approver_uid), None)
    if fixture is None:
        return None
    group_name = 'wheel' if platform.freedesktop_os_release().get('ID') == 'fedora' else 'sudo'
    try:
        group = grp.getgrnam(group_name)
    except KeyError:
        return None
    administrators = (user for user in pwd.getpwall()
                      if user.pw_name in group.gr_mem or user.pw_gid == group.gr_gid)
    caller_uid = os.getuid()
    # Prefer the selected fixture if it exists on this host, then the caller.
    account = min(administrators, key=lambda user: (
        user.pw_name != fixture.username, user.pw_uid != caller_uid, user.pw_uid), default=None)
    return account.pw_name if account is not None else None


class PreviewApproval:
    def __init__(self):
        self.connection = None

    def close(self):
        # The subject is this dedicated connection. Disconnecting also removes
        # any outstanding authentication when the window closes or reloads.
        if self.connection is not None:
            connection, self.connection = self.connection, None
            connection.close_sync(None)

    def request(self, window):
        if not window._state.begin():
            return
        try:
            _target_uid, target_label, approver_uid, duration_seconds, allow_soft = \
                window._request_content.selected()
            approver = host_approver(approver_uid)
            if approver is None:
                raise ValueError(m.REQUEST_DENIED)
        except ValueError as error:
            window._state.finish()
            window._request_content.show_validation_error(error.args[0])
            return
        window._set_request_controls(False)
        try:
            if os.getuid() == 0:
                raise RuntimeError('Run interactive previews as a desktop user, not root.')
            translations = load_translations(
                window._applied_language or '', (window._desktop_language,))
            details = {
                'target-account': target_label,
                'approver-user': approver,
                'polkit.message': format_approval_message(
                    duration_seconds, allow_soft, translations),
            }
            address = os.environ.get('ONPC_PREVIEW_AUTH_BUS_ADDRESS') or \
                Gio.dbus_address_get_for_bus_sync(Gio.BusType.SYSTEM, None)
            self.connection = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            self.connection.call(
                NAME, PATH, INTERFACE, 'CheckAuthorization',
                GLib.Variant('((sa{sv})sa{ss}us)', (
                    ('system-bus-name', {'name': GLib.Variant(
                        's', self.connection.get_unique_name())}),
                    ACTION, details, 1, '',
                )), GLib.VariantType.new('((bba{ss}))'),
                Gio.DBusCallFlags.NONE, GLib.MAXINT, None,
                lambda connection, result: self._done(window, connection, result))
        except Exception:
            self.close()
            window._finish_request()
            raise

    def _done(self, window, connection, result):
        try:
            authorized, challenge, details = connection.call_finish(result).unpack()[0]
            if window._estimate_closed:
                return
            window._present_request_outcome('approved' if authorized else (
                'cancelled' if details.get('polkit.dismissed') else 'denied'))
            if not authorized and challenge and not details.get('polkit.dismissed'):
                print('Preview authentication needs a running host desktop PolicyKit agent.', flush=True)
        except Exception as error:
            if not window._estimate_closed:
                print('Preview authentication failed. Run ./setup.sh --test-tools-only '
                      'to install the preview policy, and check the host PolicyKit agent.', flush=True)
                window._show_error(error)
        finally:
            self.close()
            if not window._estimate_closed:
                window._finish_request()
