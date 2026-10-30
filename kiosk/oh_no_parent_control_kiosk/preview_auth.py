"""Real host-desktop authentication with no privileged preview effects.

Only interactive launchers enable this. Automated component previews retain
their private dependencies. PolicyKit owns administrator selection and secrets.
"""

import grp
import os
import platform
import pwd

from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.approval_prompt import format_approval_message
from common.oh_no_parent_control_ui.localization import load_translations

NAME = 'org.freedesktop.PolicyKit1'
PATH = '/org/freedesktop/PolicyKit1/Authority'
INTERFACE = NAME + '.Authority'
ACTION = 'com.puffyslippers.onpc.preview.approve'


def approvers():
    """Use real local administrators; fixture child accounts remain disposable."""
    group_name = 'wheel' if platform.freedesktop_os_release().get('ID') == 'fedora' else 'sudo'
    group = grp.getgrnam(group_name)
    return tuple((user.pw_uid, user.pw_gecos.split(',')[0] or user.pw_name, '')
                 for user in pwd.getpwall()
                 if user.pw_name in group.gr_mem or user.pw_gid == group.gr_gid)


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
            if approver_uid not in {uid for uid, _label, _icon in approvers()}:
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
                'approver-user': pwd.getpwuid(approver_uid).pw_name,
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
