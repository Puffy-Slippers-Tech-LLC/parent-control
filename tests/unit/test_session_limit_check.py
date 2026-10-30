import os
import unittest
from types import SimpleNamespace
from unittest import mock

import pytest

from gi.repository import GLib

from tools import session_limit_check


class Reply:
    def __init__(self, value):
        self.value = value

    def unpack(self):
        return self.value


@pytest.fixture
def bridge(monkeypatch):
    """Only doubles: no system bus, PAM session, account or process is changed."""
    monkeypatch.setattr(session_limit_check.os, "getuid", lambda: 0)
    monkeypatch.setattr(session_limit_check.os, "geteuid", lambda: 0)
    parent = mock.Mock(return_value=4321)
    monkeypatch.setattr(session_limit_check.os, "getppid", parent)
    monkeypatch.setattr(session_limit_check.pwd, "getpwnam", lambda user:
                        SimpleNamespace(pw_name="child", pw_uid=1002))
    unit = {"Transient": True}
    properties = {
        "MainPID": 4321, "User": "1002", "PAMName": "login",
        "ExecStart": [("systemd-stdio-bridge",
                       ["systemd-stdio-bridge", "--user", "--quiet"],
                       False, 0, 0, 0, 0, 4321, 0, 0)],
    }
    path = "/org/freedesktop/systemd1/unit/run_2dbridge_2eservice"

    def call(destination, object_path, interface, method, parameters, reply_type,
             flags, timeout, cancellable):
        assert destination == session_limit_check.SYSTEMD_NAME
        assert timeout == 3000 and cancellable is None
        if method == "GetUnitByPID":
            assert object_path == session_limit_check.SYSTEMD_PATH
            assert interface == destination + ".Manager"
            assert parameters.unpack() == (4321,)
            return GLib.Variant("(o)", (path,))
        assert method == "GetAll" and object_path == path
        assert interface == session_limit_check.PROPERTIES_INTERFACE
        if parameters.unpack() == (session_limit_check.SYSTEMD_UNIT_INTERFACE,):
            return Reply((unit,))
        assert parameters.unpack() == (session_limit_check.SYSTEMD_SERVICE_INTERFACE,)
        return Reply((properties,))

    connection = SimpleNamespace(call_sync=mock.Mock(side_effect=call))
    monkeypatch.setattr(session_limit_check.Gio, "bus_get_sync", lambda *args: connection)
    return SimpleNamespace(unit=unit, properties=properties, parent=parent,
                           connection=connection)


@pytest.mark.parametrize("user", ["child", "1002"])
@pytest.mark.parametrize("executable", ["/usr/bin/systemd-stdio-bridge", "systemd-stdio-bridge"])
@pytest.mark.parametrize("argv0", ["/usr/bin/systemd-stdio-bridge", "systemd-stdio-bridge"])
def test_exhausted_child_keeps_systemd_administrative_bus_access(
        bridge, monkeypatch, user, executable, argv0):
    bridge.properties["User"] = user
    command = bridge.properties["ExecStart"][0]
    bridge.properties["ExecStart"] = [
        (executable, [argv0, "--user", "--quiet"], *command[2:]),
    ]
    monkeypatch.setenv("PAM_USER", "child")
    monkeypatch.setenv("PAM_SERVICE", "login")
    policy = mock.Mock(return_value=False)  # Child remains restricted with no time.
    monkeypatch.setattr(session_limit_check, "is_confirmed_unrestricted", policy)
    assert session_limit_check.main([]) == 0
    policy.assert_not_called()


@pytest.mark.parametrize("executable", ["/usr/bin/systemd-stdio-bridge", "systemd-stdio-bridge"])
def test_bridge_accepts_systemd_property_wire_types(bridge, executable):
    command = bridge.properties["ExecStart"][0]
    bridge.properties["ExecStart"] = [
        (executable, [executable, "--user", "--quiet"], *command[2:]),
    ]
    call = bridge.connection.call_sync.side_effect
    signatures = {"Transient": "b", "MainPID": "u", "User": "s", "PAMName": "s",
                  "ExecStart": "a(sasbttttuii)"}

    def wire_reply(*args):
        reply = call(*args)
        if args[3] == "GetAll":
            values = {key: GLib.Variant(signatures[key], value)
                      for key, value in reply.unpack()[0].items()}
            return GLib.Variant("(a{sv})", (values,))
        return reply

    bridge.connection.call_sync.side_effect = wire_reply
    assert session_limit_check.is_systemd_user_bus_bridge("child", "login")


@pytest.mark.parametrize("executable", [
    "./systemd-stdio-bridge", "subdir/systemd-stdio-bridge",
    "/usr/local/bin/systemd-stdio-bridge", "systemd-stdio-bridge-extra", "",
])
def test_other_executable_paths_do_not_gain_the_basename_exception(bridge, executable):
    command = bridge.properties["ExecStart"][0]
    bridge.properties["ExecStart"] = [(executable, *command[1:])]
    assert not session_limit_check.is_systemd_user_bus_bridge("child", "login")


@pytest.mark.parametrize("key,value", [
    ("MainPID", 4322), ("MainPID", 0), ("User", "other-child"),
    ("PAMName", "sshd"), ("ExecStart", []),
    ("ExecStart", [("/bin/sh", ["/bin/sh", "-c", "systemd-stdio-bridge --user --quiet"])]),
    ("ExecStart", [("/tmp/systemd-stdio-bridge", ["systemd-stdio-bridge", "--user", "--quiet"])]),
    ("ExecStart", [("/usr/bin/systemd-stdio-bridge", ["systemd-stdio-bridge", "--system", "--quiet"])]),
    ("ExecStart", [("/usr/bin/systemd-stdio-bridge", ["systemd-stdio-bridge", "--user", "--quiet", "extra"])]),
    ("ExecStart", [()]), ("ExecStart", None),
])
def test_other_commands_and_parent_identities_keep_time_enforcement(bridge, monkeypatch, key, value):
    bridge.properties[key] = value
    monkeypatch.setenv("PAM_USER", "child")
    monkeypatch.setenv("PAM_SERVICE", "login")
    monkeypatch.setattr(session_limit_check, "is_confirmed_unrestricted", lambda user: False)
    assert session_limit_check.main([]) == 1


@pytest.mark.parametrize("key", ["MainPID", "User", "PAMName", "ExecStart"])
def test_missing_systemd_properties_do_not_exempt_a_session(bridge, key):
    del bridge.properties[key]
    assert not session_limit_check.is_systemd_user_bus_bridge("child", "login")


@pytest.mark.parametrize("transient", [False, None, "true"])
def test_only_transient_system_services_qualify(bridge, transient):
    bridge.unit["Transient"] = transient
    assert not session_limit_check.is_systemd_user_bus_bridge("child", "login")


@pytest.mark.parametrize("service", ["gdm-password", "sshd", "sudo", "systemd-user", ""])
def test_other_pam_services_never_receive_the_bridge_exception(bridge, service):
    assert not session_limit_check.is_systemd_user_bus_bridge("child", service)
    bridge.connection.call_sync.assert_not_called()


@pytest.mark.parametrize("credential", ["getuid", "geteuid"])
def test_unprivileged_helpers_cannot_request_the_exception(bridge, monkeypatch, credential):
    monkeypatch.setattr(session_limit_check.os, credential, lambda: 1002)
    assert not session_limit_check.is_systemd_user_bus_bridge("child", "login")
    bridge.connection.call_sync.assert_not_called()


@pytest.mark.parametrize("user", ["", "unknown-child", "oh-no-parent-control"])
def test_unverified_or_kiosk_identity_is_not_exempted(bridge, user):
    assert not session_limit_check.is_systemd_user_bus_bridge(user, "login")
    bridge.connection.call_sync.assert_not_called()


@pytest.mark.parametrize("step", [0, 1, 2])
def test_system_manager_query_failure_keeps_time_enforcement(bridge, step):
    call = bridge.connection.call_sync.side_effect
    calls = 0

    def fail(*args):
        nonlocal calls
        calls += 1
        if calls == step + 1:
            raise GLib.Error("system manager unavailable")
        return call(*args)

    bridge.connection.call_sync.side_effect = fail
    assert not session_limit_check.is_systemd_user_bus_bridge("child", "login")


@pytest.mark.parametrize("parents", [[1], [4321, 1]])
def test_orphaned_helper_cannot_use_a_previous_parent_unit(bridge, parents):
    bridge.parent.side_effect = parents
    assert not session_limit_check.is_systemd_user_bus_bridge("child", "login")


@pytest.mark.parametrize("status,expected", [
    ((0, 0, 0, 0), "DENIED"),
    ((45, 0, 0, 45), "ALLOWED"),
    ((0, 60, 0, 60), "ALLOWED"),
    ((0, 0, 0, 120), "ERROR"),
    (None, "ERROR"),
])
def test_gdm_nonzero_daily_allowance_counts_recorded_use(monkeypatch, status, expected):
    monkeypatch.setattr(session_limit_check.pwd, "getpwnam",
                        lambda name: SimpleNamespace(pw_name=name, pw_uid=1002))
    limits = mock.Mock()
    limits.check_time_remaining.return_value = (True, 120, True, False)
    manager = mock.Mock()
    manager.get_session_limits.return_value = limits
    monkeypatch.setattr(session_limit_check.Malcontent.Manager, "new", lambda bus: manager)
    connection = mock.Mock()
    if status is None:
        connection.call_sync.side_effect = GLib.Error("unavailable")
    else:
        connection.call_sync.return_value = GLib.Variant("(uuuu)", status)

    outcome = session_limit_check.authentication_outcome(
        "child", "gdm-password", connection, object())

    assert outcome == getattr(session_limit_check.AuthenticationOutcome, expected)
    connection.call_sync.assert_called_once()
    args = connection.call_sync.call_args.args
    assert args[:4] == (session_limit_check.BROKER_NAME,
                       session_limit_check.BROKER_PATH,
                       session_limit_check.BROKER_NAME, "GetTimeStatus")
    assert args[4].unpack() == (1002, 0)
    assert args[5].dup_string() == "(uuuu)"
    assert args[6:] == (session_limit_check.Gio.DBusCallFlags.NONE, 35000, None)


class SessionLimitCheckTests(unittest.TestCase):
    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    @mock.patch("tools.session_limit_check._call")
    def test_only_confirmed_limit_type_none_is_unrestricted(self, call, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        call.side_effect = [
            Reply(("/org/freedesktop/Accounts/User1001",)),
            Reply((0,)),
        ]

        self.assertTrue(
            session_limit_check.is_confirmed_unrestricted("child", object())
        )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    @mock.patch("tools.session_limit_check._call")
    def test_all_nonzero_limit_types_continue_to_pam(self, call, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        for limit_type in (2, 3):
            with self.subTest(limit_type=limit_type):
                call.side_effect = [
                    Reply(("/org/freedesktop/Accounts/User1001",)),
                    Reply((limit_type,)),
                ]
                self.assertFalse(
                    session_limit_check.is_confirmed_unrestricted("child", object())
                )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    @mock.patch("tools.session_limit_check._call")
    def test_unexpected_account_path_fails_closed(self, call, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        call.return_value = Reply(("/org/freedesktop/Accounts/User9999",))

        self.assertFalse(
            session_limit_check.is_confirmed_unrestricted("child", object())
        )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    @mock.patch("tools.session_limit_check._call")
    def test_backend_failure_fails_closed(self, call, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        call.side_effect = GLib.Error("unavailable")

        self.assertFalse(
            session_limit_check.is_confirmed_unrestricted("child", object())
        )

    @mock.patch.dict(os.environ, {"PAM_USER": "child"}, clear=True)
    @mock.patch("tools.session_limit_check.is_confirmed_unrestricted")
    def test_pam_exit_status_skips_only_unrestricted_accounts(self, check):
        check.return_value = True
        self.assertEqual(session_limit_check.main([]), 0)
        check.return_value = False
        self.assertEqual(session_limit_check.main([]), 1)

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    def test_non_gdm_authentication_is_unchanged(self, getpwnam):
        self.assertEqual(
            session_limit_check.authentication_outcome("child", "sudo"),
            session_limit_check.AuthenticationOutcome.ALLOWED,
        )
        getpwnam.assert_not_called()

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    def test_root_remains_a_recovery_path(self, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="root", pw_uid=0)
        self.assertEqual(
            session_limit_check.authentication_outcome(
                "root", "gdm-password",
            ),
            session_limit_check.AuthenticationOutcome.ALLOWED,
        )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    def test_gdm_authentication_denies_zero_time_without_a_grant(self, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        limits = mock.Mock()
        limits.check_time_remaining.return_value = (False, 0, True, False)
        manager = mock.Mock()
        manager.get_session_limits.return_value = limits

        with mock.patch.object(session_limit_check.Malcontent.Manager, "new",
                               return_value=manager):
            self.assertEqual(
                session_limit_check.authentication_outcome(
                    "child", "gdm-password", object(), object(),
                ),
                session_limit_check.AuthenticationOutcome.DENIED,
            )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    def test_gdm_authentication_allows_an_active_grant(self, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        limits = mock.Mock()
        limits.check_time_remaining.return_value = (True, 300, True, True)
        manager = mock.Mock()
        manager.get_session_limits.return_value = limits

        with mock.patch.object(session_limit_check.Malcontent.Manager, "new",
                               return_value=manager):
            self.assertEqual(
                session_limit_check.authentication_outcome(
                    "child", "gdm-password", object(), object(),
                ),
                session_limit_check.AuthenticationOutcome.ALLOWED,
            )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    def test_gdm_authentication_backend_failure_fails_closed(self, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        with mock.patch.object(
                session_limit_check.Malcontent.Manager, "new",
                side_effect=GLib.Error("unavailable")):
            self.assertEqual(
                session_limit_check.authentication_outcome(
                    "child", "gdm-password", object(), object(),
                ),
                session_limit_check.AuthenticationOutcome.ERROR,
            )

    @mock.patch("tools.session_limit_check.pwd.getpwnam")
    def test_inconsistent_denial_is_not_reported_as_no_time(self, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_name="child", pw_uid=1001)
        limits = mock.Mock()
        limits.check_time_remaining.return_value = (False, 300, True, False)
        manager = mock.Mock()
        manager.get_session_limits.return_value = limits

        with mock.patch.object(session_limit_check.Malcontent.Manager, "new",
                               return_value=manager):
            self.assertEqual(
                session_limit_check.authentication_outcome(
                    "child", "gdm-password", object(), object(),
                ),
                session_limit_check.AuthenticationOutcome.ERROR,
            )

    @mock.patch.dict(os.environ, {
        "PAM_USER": "child", "PAM_SERVICE": "gdm-password",
    }, clear=True)
    @mock.patch("tools.session_limit_check._log_authentication_outcome")
    @mock.patch("tools.session_limit_check.authentication_outcome")
    def test_authentication_mode_returns_the_policy_result(self, check, log):
        check.return_value = session_limit_check.AuthenticationOutcome.DENIED
        self.assertEqual(session_limit_check.main(["--authenticate"]), 1)
        check.assert_called_once_with("child", "gdm-password")
        log.assert_called_once_with(session_limit_check.AuthenticationOutcome.DENIED)

        check.reset_mock()
        log.reset_mock()
        check.return_value = session_limit_check.AuthenticationOutcome.ALLOWED
        self.assertEqual(session_limit_check.main(["--authenticate"]), 0)
        log.assert_called_once_with(session_limit_check.AuthenticationOutcome.ALLOWED)

        check.return_value = session_limit_check.AuthenticationOutcome.ERROR
        self.assertEqual(session_limit_check.main(["--authenticate"]), 2)
        log.assert_called_with(session_limit_check.AuthenticationOutcome.ERROR)

    def test_unknown_mode_fails_closed(self):
        self.assertEqual(session_limit_check.main(["--unexpected"]), 1)


if __name__ == "__main__":
    unittest.main()
