import unittest
from unittest import mock
from types import SimpleNamespace

from gi.repository import Gio, GLib

from oh_no_parent_control.adapters import (
    AccountsService, RUNTIME_MAX_USEC_INFINITY, TimerUsage,
    TimerUsageError,
)
from oh_no_parent_control.core import UserAccount


class PolkitAdapterTests(unittest.TestCase):
    @staticmethod
    def _helper_result(stdout, returncode=0):
        def run(*_args, **kwargs):
            kwargs["stdout"].write(stdout.encode("utf-8"))
            return SimpleNamespace(returncode=returncode)

        return run

    def test_accounts_service_exposes_the_system_user_icon_file(self):
        accounts = AccountsService(object())
        reply = mock.Mock()
        reply.unpack.return_value = ({
            "Uid": 1001,
            "UserName": "child",
            "RealName": "Child",
            "AccountType": 0,
            "SystemAccount": False,
            "LocalAccount": True,
            "Locked": False,
            "IconFile": "/var/lib/AccountsService/icons/child",
        },)
        with mock.patch.object(accounts, "_user_path", return_value="/org/freedesktop/Accounts/User1001"), \
                mock.patch("oh_no_parent_control.adapters._call", return_value=reply):
            user = accounts.get_user(1001)

        self.assertEqual(user.icon_file, "/var/lib/AccountsService/icons/child")

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

    def test_direct_account_lookup_preserves_shell_eligibility(self):
        accounts = AccountsService(object())
        for shell in (None, "", "/bin/false", "/usr/bin/false", "/sbin/nologin",
                      "/usr/sbin/nologin", "/bin/bash", "/bin/sh"):
            with self.subTest(shell=shell):
                properties = {"Uid": 1003, "AccountType": 1,
                              "LocalAccount": True, "SystemAccount": False, "Locked": False}
                if shell is not None:
                    properties["Shell"] = shell
                reply = mock.Mock()
                reply.unpack.return_value = (properties,)
                with mock.patch.object(accounts, "_user_path", return_value="/org/freedesktop/Accounts/User1003"), \
                        mock.patch("oh_no_parent_control.adapters._call", return_value=reply):
                    user = accounts.get_user(1003)
                self.assertEqual(user.is_interactive, shell in ("/bin/bash", "/bin/sh"))

    def test_session_runtime_cap_is_cleared_only_for_the_child_user_session(self):
        accounts = AccountsService(object())
        sessions = mock.Mock()
        sessions.unpack.return_value = ([
            ("12", 1001, "child", "seat0", "/org/freedesktop/login1/session/_12"),
            ("2", 1000, "admin", "seat0", "/org/freedesktop/login1/session/_32"),
            ("c25", 1001, "child", "seat0", "/org/freedesktop/login1/session/c25"),
            ("../x", 1001, "child", "seat0", "/org/freedesktop/login1/session/bad"),
        ],)
        user_session = mock.Mock()
        user_session.unpack.return_value = ({
            "Class": "user", "Type": "wayland", "Service": "gdm-password",
        },)
        greeter = mock.Mock()
        greeter.unpack.return_value = ({"Class": "greeter", "Type": "wayland"},)

        def call(connection, name, path, interface, method, parameters, reply_type,
                 timeout=None):
            if method == "ListSessions":
                return sessions
            if method == "GetAll" and path.endswith("/c25"):
                return greeter
            if method == "GetAll":
                return user_session
            if method == "SetUnitProperties":
                set_property.append(parameters.unpack())
                return mock.Mock()
            raise AssertionError(method)

        set_property = []
        with mock.patch("oh_no_parent_control.adapters._call", side_effect=call):
            cleared = accounts.clear_session_runtime_max(1001)

        self.assertEqual(cleared, ("session-12.scope",))
        self.assertEqual(set_property, [(
            "session-12.scope", True,
            [("RuntimeMaxUSec", RUNTIME_MAX_USEC_INFINITY)],
        )])

    def test_session_runtime_cap_preserves_non_gdm_and_unknown_sessions(self):
        accounts = AccountsService(object())
        for properties in (
                {"Class": "user", "Type": "tty", "Service": "login"},
                {"Class": "user", "Type": "tty", "Service": "sshd"},
                {"Class": "user", "Type": "wayland", "Service": "another-display-manager"},
                {"Class": "user", "Type": "wayland"},
                {"Class": "user", "Service": "gdm-password"}):
            with self.subTest(properties=properties):
                sessions = mock.Mock()
                sessions.unpack.return_value = ([("12", 1001, "child", "seat0",
                    "/org/freedesktop/login1/session/_12")],)
                details = mock.Mock()
                details.unpack.return_value = (properties,)
                with mock.patch("oh_no_parent_control.adapters._call",
                                side_effect=[sessions, details]) as call:
                    self.assertEqual(accounts.clear_session_runtime_max(1001), ())
                self.assertEqual(call.call_count, 2)

    def test_app_filter_write_reconciles_native_execution_policy(self):
        policy = mock.Mock()
        accounts = AccountsService(object(), policy)
        users = (
            UserAccount(1001, "child", "Child", False, False, True),
            UserAccount(1003, "parent", "Parent", True, False, True),
        )
        filters = {
            1001: (False, ("/home/child/Game.AppImage", "app/org.game/x86_64/stable")),
            1003: (False, ()),
        }
        with mock.patch.object(accounts, "_set") as set_property, \
                mock.patch.object(accounts, "list_users", return_value=users), \
                mock.patch.object(accounts, "get_filter",
                                  side_effect=lambda uid: filters[uid]):
            accounts.set_filter(1001, filters[1001])

        set_property.assert_called_once()
        policy.reconcile.assert_called_once_with({
            1001: filters[1001][1],
            1003: (),
        })

    def test_allowlist_is_not_misrepresented_as_a_native_blocklist(self):
        policy = mock.Mock()
        accounts = AccountsService(object(), policy)
        user = UserAccount(1001, "child", "Child", False, False, True)
        with mock.patch.object(accounts, "list_users", return_value=(user,)), \
                mock.patch.object(
                    accounts, "get_filter", return_value=(True, ("/usr/bin/allowed",))
                ):
            accounts.sync_execution_policy()

        policy.reconcile.assert_called_once_with({1001: ()})

    def test_timer_usage_queries_as_selected_child_not_root(self):
        identity = SimpleNamespace(pw_name="private-child-name", pw_gid=1201)
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwuid",
                        return_value=identity) as lookup, \
                mock.patch("oh_no_parent_control.adapters.subprocess.run",
                           side_effect=self._helper_result("[[10,20],[30,40]]")) as run, \
                mock.patch("oh_no_parent_control.adapters._call") as root_call, \
                self.assertLogs("oh-no-parent-control.adapters", level="INFO") as logs:
            self.assertEqual(TimerUsage(object()).query_usage(1001), ((10, 20), (30, 40)))
        lookup.assert_called_once_with(1001)
        root_call.assert_not_called()
        self.assertEqual(run.call_args.args[0], [
            "/usr/libexec/oh-no-parent-control-query-usage", "1001"])
        self.assertEqual(run.call_args.kwargs["user"], 1001)
        self.assertEqual(run.call_args.kwargs["group"], 1201)
        self.assertEqual(run.call_args.kwargs["extra_groups"], ())
        self.assertNotIn(identity.pw_name, "\n".join(logs.output))
        self.assertNotIn("1001", "\n".join(logs.output))

    def test_timer_usage_missing_child_never_launches_helper(self):
        with mock.patch("oh_no_parent_control.adapters.pwd.getpwuid",
                        side_effect=KeyError("private-child-name")), \
                mock.patch("oh_no_parent_control.adapters.subprocess.run") as run:
            with self.assertRaisesRegex(TimerUsageError, "child-unavailable"):
                TimerUsage(object()).query_usage(1001)
        run.assert_not_called()

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
