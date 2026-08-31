import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[2] / "tools" / "preserve_extension_state.py"
SPEC = importlib.util.spec_from_file_location("preserve_extension_state", MODULE_PATH)
preserve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preserve)


class PreserveExtensionStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.state = Path(self.directory.name) / "state.json"
        self.account = mock.Mock(pw_uid=1000, pw_gid=1000, pw_name="parent")

    def tearDown(self):
        self.directory.cleanup()

    @mock.patch.object(preserve, "_gsettings", return_value="false")
    @mock.patch.object(preserve, "_account")
    def test_schedule_records_exact_current_value(self, account, gsettings):
        account.return_value = self.account
        preserve.schedule(1000, self.state)
        self.assertEqual(
            json.loads(self.state.read_text()),
            {"version": 1, "uid": 1000, "disabled": False},
        )
        gsettings.assert_called_once_with(self.account, "get")

    @mock.patch.object(preserve, "_gsettings", return_value="")
    @mock.patch.object(preserve, "_account")
    def test_restore_applies_value_then_consumes_state(self, account, gsettings):
        account.return_value = self.account
        self.state.write_text('{"version": 1, "uid": 1000, "disabled": true}\n')
        preserve.restore(self.state)
        gsettings.assert_called_once_with(self.account, "set", "true")
        self.assertFalse(self.state.exists())

    @mock.patch.object(preserve, "_gsettings", side_effect=RuntimeError("failed"))
    @mock.patch.object(preserve, "_account")
    def test_failed_restore_keeps_state_for_next_boot(self, account, gsettings):
        account.return_value = self.account
        self.state.write_text('{"version": 1, "uid": 1000, "disabled": false}\n')
        with self.assertRaisesRegex(RuntimeError, "failed"):
            preserve.restore(self.state)
        self.assertTrue(self.state.exists())

    def test_restore_rejects_unexpected_fields(self):
        self.state.write_text(
            '{"version": 1, "uid": 1000, "disabled": false, "extra": true}\n'
        )
        with self.assertRaisesRegex(RuntimeError, "invalid"):
            preserve.restore(self.state)


if __name__ == "__main__":
    unittest.main()
