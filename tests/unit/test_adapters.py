import unittest
from unittest import mock
from types import SimpleNamespace

from gi.repository import Gio, GLib

from oh_no_parent_control.adapters import (
    AccountsService, PolkitAuthorizer, TimerUsage, TimerUsageError,
)
from oh_no_parent_control.core import UserAccount


class PolkitAdapterTests(unittest.TestCase):
    @staticmethod
    def _helper_result(stdout, returncode=0):
        def run(*_args, **kwargs):
            kwargs["stdout"].write(stdout.encode("utf-8"))
            return SimpleNamespace(returncode=returncode)

        return run

    def test_timeout_or_agent_loss_denies(self):
        error = GLib.Error.new_literal(Gio.io_error_quark(), "timed out", Gio.IOErrorEnum.TIMED_OUT)
        with mock.patch("oh_no_parent_control.adapters._call", side_effect=error):
            self.assertEqual(
                PolkitAuthorizer(object()).check(
                    ":1.2", "id", "Child", "admin", "15 minutes", False,
                ),
                "denied",
            )

    def test_selected_approver_is_passed_as_an_action_detail(self):
        reply = mock.Mock()
        reply.unpack.return_value = ((True, False, {}),)
        with mock.patch("oh_no_parent_control.adapters._call", return_value=reply) as call:
            outcome = PolkitAuthorizer(object()).check(
                ":1.2", "id", "Child", "parent", "15 minutes", True,
            )

        self.assertEqual(outcome, "approved")
        parameters = call.call_args.args[5].unpack()
        self.assertEqual(parameters[2]["approver-user"], "parent")
        self.assertEqual(parameters[2]["target-account"], "Child")
        self.assertEqual(parameters[2]["requested-duration"], "15 minutes")
        self.assertEqual(parameters[2]["soft-blocked-apps"], " and allow soft blocked apps")

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

    def test_timer_usage_helper_runs_as_authenticated_approver(self):
        identity = SimpleNamespace(pw_name="parent", pw_gid=1200)
        approver = UserAccount(1003, "parent", "Parent", True, False, True)
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwuid",
                        return_value=identity), \
                mock.patch("oh_no_parent_control.adapters.subprocess.run",
                           side_effect=self._helper_result(
                               "[[10,20],[30,40]]",
                           )) as run:
            intervals = TimerUsage(object()).query_usage_as(1001, approver)

        self.assertEqual(intervals, ((10, 20), (30, 40)))
        self.assertEqual(run.call_args.args[0], [
            "/usr/libexec/oh-no-parent-control-query-usage", "1001",
        ])
        self.assertEqual(run.call_args.kwargs["user"], 1003)
        self.assertEqual(run.call_args.kwargs["group"], 1200)
        self.assertEqual(run.call_args.kwargs["extra_groups"], ())
        self.assertFalse(run.call_args.kwargs["check"])
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_timer_usage_helper_rejects_changed_approver_identity(self):
        identity = SimpleNamespace(pw_name="someone-else", pw_gid=1200)
        approver = UserAccount(1003, "parent", "Parent", True, False, True)
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwuid",
                        return_value=identity), \
                mock.patch("oh_no_parent_control.adapters.subprocess.run") as run:
            with self.assertRaisesRegex(TimerUsageError, "approver-identity-changed"):
                TimerUsage(object()).query_usage_as(1001, approver)
        run.assert_not_called()

    def test_timer_usage_helper_rejects_failure_and_malformed_output(self):
        identity = SimpleNamespace(pw_name="parent", pw_gid=1200)
        approver = UserAccount(1003, "parent", "Parent", True, False, True)
        outcomes = (
            (69, ""),
            (0, '{"not":"intervals"}'),
            (0, "[[false,20]]"),
        )
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwuid",
                        return_value=identity):
            for returncode, stdout in outcomes:
                with self.subTest(returncode=returncode, stdout=stdout), \
                        mock.patch("oh_no_parent_control.adapters.subprocess.run",
                                   side_effect=self._helper_result(
                                       stdout, returncode,
                                   )), \
                        self.assertRaises(TimerUsageError):
                    TimerUsage(object()).query_usage_as(1001, approver)

    def test_timer_usage_helper_bounds_output_before_reading_it(self):
        identity = SimpleNamespace(pw_name="parent", pw_gid=1200)
        approver = UserAccount(1003, "parent", "Parent", True, False, True)
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwuid",
                        return_value=identity), \
                mock.patch("oh_no_parent_control.adapters.subprocess.run",
                           side_effect=self._helper_result("12345")), \
                mock.patch(
                    "oh_no_parent_control.adapters.MAX_USAGE_HELPER_OUTPUT_BYTES", 4,
                ), self.assertRaisesRegex(TimerUsageError, "reply-too-large"):
            TimerUsage(object()).query_usage_as(1001, approver)


if __name__ == "__main__":
    unittest.main()
