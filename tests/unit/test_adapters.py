import unittest
from unittest import mock

from gi.repository import Gio, GLib

from oh_no_parent_control.adapters import PolkitAuthorizer


class PolkitAdapterTests(unittest.TestCase):
    def test_timeout_or_agent_loss_denies(self):
        error = GLib.Error.new_literal(Gio.io_error_quark(), "timed out", Gio.IOErrorEnum.TIMED_OUT)
        with mock.patch("oh_no_parent_control.adapters._call", side_effect=error):
            self.assertEqual(PolkitAuthorizer(object()).check(":1.2", "id"), "denied")


if __name__ == "__main__":
    unittest.main()
