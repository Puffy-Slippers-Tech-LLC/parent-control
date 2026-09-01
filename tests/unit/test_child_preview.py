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

    def test_preview_lists_two_mock_approvers(self):
        source = (ROOT / "child" / "approverClient.js").read_text()

        self.assertIn("if (isPreview())", source)
        self.assertIn("[1001, 'Daddy']", source)
        self.assertIn("[1002, 'Mommy']", source)

    def test_request_dialog_owns_the_help_and_about_menu(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        request_dialog = (ROOT / "child" / "requestDialog.js").read_text()

        self.assertIn("super._init(0.0, 'Screen Time Remaining');", indicator)
        self.assertNotIn("super._init(0.0, 'Screen Time Remaining', true);", indicator)
        self.assertNotIn('view-more-symbolic', indicator)
        self.assertIn("icon_name: 'view-more-symbolic'", request_dialog)
        self.assertIn('style_class: \'oh-no-parent-control-header-menu-button\'',
                      request_dialog)
        self.assertIn("[['Help', 'help'], ['About', 'about']]", request_dialog)
        self.assertIn("this._onMenu?.(action);", request_dialog)
