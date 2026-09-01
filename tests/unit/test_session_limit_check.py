import os
import unittest
from types import SimpleNamespace
from unittest import mock

from gi.repository import GLib

from tools import session_limit_check


class Reply:
    def __init__(self, value):
        self.value = value

    def unpack(self):
        return self.value


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
        self.assertEqual(session_limit_check.main(), 0)
        check.return_value = False
        self.assertEqual(session_limit_check.main(), 1)


if __name__ == "__main__":
    unittest.main()
