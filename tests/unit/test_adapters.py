import unittest
from unittest import mock
from types import SimpleNamespace

from gi.repository import Gio, GLib

from oh_no_parent_control.adapters import AccountsService, PolkitAuthorizer, TimerUsage


class PolkitAdapterTests(unittest.TestCase):
    def test_timeout_or_agent_loss_denies(self):
        error = GLib.Error.new_literal(Gio.io_error_quark(), "timed out", Gio.IOErrorEnum.TIMED_OUT)
        with mock.patch("oh_no_parent_control.adapters._call", side_effect=error):
            self.assertEqual(PolkitAuthorizer(object()).check(":1.2", "id", "Child"), "denied")

    def test_user_listing_uses_fresh_nss_candidates(self):
        accounts = AccountsService(object())
        entries = [
            SimpleNamespace(pw_uid=999, pw_shell="/bin/bash"),
            SimpleNamespace(pw_uid=1002, pw_shell="/bin/bash"),
            SimpleNamespace(pw_uid=1001, pw_shell="/bin/bash"),
            SimpleNamespace(pw_uid=1001, pw_shell="/bin/bash"),
            SimpleNamespace(pw_uid=1003, pw_shell="/usr/sbin/nologin"),
            SimpleNamespace(pw_uid=1 << 32, pw_shell="/bin/bash"),
        ]
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwall", return_value=entries), \
                mock.patch.object(accounts, "get_user", side_effect=lambda uid: uid):
            self.assertEqual(accounts.list_users(), (1001, 1002))

    def test_timer_usage_queries_selected_child_through_parent_interface(self):
        reply = mock.Mock()
        reply.unpack.return_value = ([(10, 20), (30, 40)],)
        with mock.patch("oh_no_parent_control.adapters._call", return_value=reply) as call:
            self.assertEqual(TimerUsage(object()).query_usage(1001), ((10, 20), (30, 40)))
        self.assertEqual(call.call_args.args[4], "QueryUsage")
        self.assertEqual(call.call_args.args[5].unpack(), (1001, "login-session", ""))


if __name__ == "__main__":
    unittest.main()
