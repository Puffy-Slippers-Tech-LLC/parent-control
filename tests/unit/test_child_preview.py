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
        self.assertIn('OH_NO_PARENT_CONTROL_REQUEST_APP=', source)
        self.assertIn('--child-overlay', source)

    def test_preview_mode_uses_fixture_ui_behavior_without_privileged_clients(self):
        extension = (ROOT / "child" / "extension.js").read_text()

        self.assertIn('this._preview = isPreview()', extension)
        self.assertIn('this._preview ? 45 * 60', extension)
        self.assertIn('if (this._preview) {', extension)
        self.assertIn("OH_NO_PARENT_CONTROL_REQUEST_APP", extension)

    def test_child_invokes_the_shared_kiosk_request_gui(self):
        extension = (ROOT / "child" / "extension.js").read_text()
        makefile = (ROOT / "Makefile").read_text()
        extension_sources = next(
            line for line in makefile.splitlines()
            if line.startswith("EXTENSION_SOURCES :=")
        )

        self.assertIn("Gio.Subprocess.new", extension)
        self.assertIn("'/usr/bin/oh-no-parent-control'", extension)
        self.assertIn("'--child-overlay'", extension)
        self.assertIn("OH_NO_PARENT_CONTROL_REQUEST_APP", extension)
        self.assertNotIn("requestOwnAccess", extension)
        self.assertNotIn("RequestPopover", extension)
        self.assertNotIn("org.freedesktop.Accounts", extension)
        self.assertNotIn("Polkit", extension)
        for obsolete in (
            "aboutDialog.js",
            "approverClient.js",
            "requestAccessClient.js",
            "requestDialog.js",
            "requestOptions.js",
            "requestPreferencesStore.js",
            "sharedPreferencesClient.js",
        ):
            self.assertNotIn(obsolete, extension_sources)
            self.assertFalse((ROOT / "child" / obsolete).exists())

    def test_zero_time_locks_only_from_the_managed_child_extension(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        client = (ROOT / "child" / "timeCalculationClient.js").read_text()

        self.assertIn("'CalculateOwnRemainingTime'", client)
        self.assertIn("calculateOwnRemainingTime", indicator)
        self.assertIn("manager.dailyLimitEnabled", indicator)
        self.assertIn("'org.gnome.ScreenSaver'", indicator)
        self.assertIn("SCREEN_SAVER_INTERFACE, 'Lock'", indicator)
        self.assertIn("Main.sessionMode, 'updated'", indicator)
        self.assertNotIn("TerminateUser", indicator)
        self.assertNotIn("RuntimeMax", indicator)

    def test_session_entry_reconciles_expired_grants_through_the_broker(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        client = (ROOT / "child" / "sessionPreparationClient.js").read_text()
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn("'PrepareOwnSession'", client)
        self.assertIn("prepareOwnSession", indicator)
        self.assertIn("Main.sessionMode.isLocked", indicator)
        self.assertNotIn("terminate", client.lower())
        self.assertIn("sessionPreparationClient.js", makefile)

    def test_notification_keeps_the_panel_indicator_without_a_shell_form(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        stylesheet = (ROOT / "child" / "stylesheet.css").read_text()

        self.assertIn("super._init(0.0, 'Screen Time Remaining');", indicator)
        self.assertIn('this.setMenu(null);', indicator)
        self.assertNotIn('view-more-symbolic', indicator)
        self.assertIn("refreshEstimate()", indicator)
        self.assertIn(".screen-time-request-button {", stylesheet)
        self.assertNotIn(".oh-no-parent-control-content {", stylesheet)
        self.assertNotIn(".oh-no-parent-control-choice {", stylesheet)

    def test_request_icon_spins_during_the_final_ten_seconds(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()

        self.assertIn("if (remainingSecs > 10)", indicator)
        self.assertIn("rotation_angle_z: 360", indicator)
        self.assertIn("repeatCount: -1", indicator)
        self.assertIn("animationRequired: true", indicator)
