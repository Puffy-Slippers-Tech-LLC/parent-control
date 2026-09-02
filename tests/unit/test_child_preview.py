import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]


class ChildPreviewTests(unittest.TestCase):
    def test_preview_uses_a_temporary_nested_shell_session(self):
        source = (ROOT / "child" / "preview").read_text()

        self.assertIn('mktemp -d', source)
        self.assertIn('XDG_DATA_HOME="$preview_root/data"', source)
        self.assertIn('extension_dir="$preview_root/data/gnome-shell/extensions/$uuid"', source)
        self.assertIn('for source in "$child_dir"/*.js "$child_dir"/*.css "$child_dir"/*.json', source)
        self.assertIn('app_logo.png,company_logo.png,brand.json,app.json', source)
        self.assertIn('ln -s "$source" "$extension_dir/${source##*/}"', source)
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

    def test_live_request_is_one_broker_owned_transaction(self):
        extension = (ROOT / "child" / "extension.js").read_text()
        client = (ROOT / "child" / "requestAccessClient.js").read_text()
        makefile = (ROOT / "Makefile").read_text()
        extension_sources = next(
            line for line in makefile.splitlines()
            if line.startswith("EXTENSION_SOURCES :=")
        )

        self.assertIn("requestOwnAccess", extension)
        self.assertIn("'RequestOwnAccess'", client)
        self.assertIn("new GLib.Variant('(uub)'", client)
        self.assertIn("const REQUEST_TIMEOUT_MS = 0x7fffffff;", client)
        self.assertNotIn("GLib.MAXINT", client)
        self.assertIn("requestAccessClient.js", makefile)
        for obsolete in (
            "appFilterClient.js",
            "parentalApproval.js",
            "sessionLimitsClient.js",
        ):
            self.assertNotIn(obsolete, extension_sources)
            self.assertFalse((ROOT / "child" / obsolete).exists())

        self.assertNotIn("org.freedesktop.Accounts", extension)
        self.assertNotIn("Polkit", extension)

    def test_zero_time_locks_only_from_the_managed_child_extension(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        client = (ROOT / "child" / "timeCalculationClient.js").read_text()

        self.assertIn("'CalculateOwnRemainingTime'", client)
        self.assertIn("calculateOwnRemainingTime", indicator)
        self.assertIn("manager.dailyLimitEnabled", indicator)
        self.assertIn("'org.gnome.ScreenSaver'", indicator)
        self.assertIn("SCREEN_SAVER_INTERFACE, 'Lock'", indicator)
        self.assertNotIn("TerminateUser", indicator)

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
        self.assertIn("'button-press-event'", request_dialog)
        self.assertIn('this._onMenuPress?.()', request_dialog)
        self.assertIn('() => this._preserveForOverflowMenu()', request_dialog)

    def test_request_dialog_header_uses_the_product_logo(self):
        request_dialog = (ROOT / "child" / "requestDialog.js").read_text()

        self.assertIn("gicon: extensionAsset('app_logo.png')", request_dialog)
        self.assertNotIn("icon_name: 'alarm-symbolic'", request_dialog)
        self.assertIn("[extensionDir, '..', 'data', name]", request_dialog)

    def test_request_form_width_does_not_depend_on_async_approver_text(self):
        stylesheet = (ROOT / "child" / "stylesheet.css").read_text()
        rule = stylesheet.split(".oh-no-parent-control-content {", 1)[1].split("}", 1)[0]

        self.assertIn("width: 350px;", rule)
