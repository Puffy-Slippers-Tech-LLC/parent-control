import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]


class ChildPreviewTests(unittest.TestCase):
    def test_preview_uses_a_temporary_nested_shell_session(self):
        source = (ROOT / "child" / "preview").read_text()

        self.assertIn('mktemp -d', source)
        self.assertIn('XDG_DATA_HOME="$preview_root/data"', source)
        self.assertIn('GSETTINGS_BACKEND=keyfile', source)
        self.assertIn('command -v dbus-run-session', source)
        self.assertIn('command -v glib-compile-schemas', source)
        self.assertIn('/usr/libexec/mutter-devkit', source)
        self.assertIn('glib-compile-schemas "$schema_dir"', source)
        self.assertIn('GSETTINGS_SCHEMA_DIR="$schema_dir"', source)
        self.assertIn('unset GDK_BACKEND', source)
        self.assertIn('dbus-run-session -- gnome-shell --devkit --wayland', source)
        self.assertNotIn('gnome-shell --nested', source)

    def test_preview_mode_uses_fixture_ui_behavior_without_privileged_clients(self):
        extension = (ROOT / "child" / "extension.js").read_text()
        preferences = (ROOT / "child" / "sharedPreferencesClient.js").read_text()

        self.assertIn('this._preview = isPreview()', extension)
        self.assertIn('this._preview ? 45 * 60', extension)
        self.assertIn('if (this._preview) {', extension)
        self.assertIn('if (isPreview())', preferences)
