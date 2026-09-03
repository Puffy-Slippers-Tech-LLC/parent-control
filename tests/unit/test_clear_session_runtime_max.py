import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from tools import clear_session_runtime_max


class ClearSessionRuntimeMaxTests(unittest.TestCase):
    def test_session_scope_rejects_unusable_ids(self):
        self.assertIsNone(clear_session_runtime_max.session_scope_unit(""))
        self.assertIsNone(clear_session_runtime_max.session_scope_unit("../12"))
        self.assertIsNone(clear_session_runtime_max.session_scope_unit("12.scope"))
        self.assertEqual(
            clear_session_runtime_max.session_scope_unit("12"),
            "session-12.scope",
        )
        self.assertEqual(
            clear_session_runtime_max.session_scope_unit("c25"),
            "session-c25.scope",
        )

    def test_clear_runtime_max_uses_the_public_systemd_property(self):
        run = mock.Mock(return_value=SimpleNamespace(returncode=0))

        self.assertTrue(clear_session_runtime_max.clear_runtime_max("12", run=run))
        run.assert_called_once_with(
            [
                "/usr/bin/systemctl", "set-property", "--runtime",
                "session-12.scope", "RuntimeMaxSec=infinity",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )

    def test_clear_runtime_max_never_raises(self):
        def run(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="systemctl", timeout=3)

        self.assertFalse(clear_session_runtime_max.clear_runtime_max("12", run=run))
        self.assertFalse(clear_session_runtime_max.clear_runtime_max("../x", run=run))

    @mock.patch.dict(os.environ, {"XDG_SESSION_ID": "12"}, clear=True)
    @mock.patch("tools.clear_session_runtime_max.clear_runtime_max")
    def test_pam_helper_never_fails_the_session(self, clear):
        clear.return_value = False
        self.assertEqual(clear_session_runtime_max.main(), 0)
        clear.assert_called_once_with("12")


if __name__ == "__main__":
    unittest.main()
