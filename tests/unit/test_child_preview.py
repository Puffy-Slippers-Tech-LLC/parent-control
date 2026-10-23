import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).parents[2]


class ChildPreviewTests(unittest.TestCase):
    def run_orchestration(self, script, *, timeout=5):
        return subprocess.run(
            ["bash", "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def test_devkit_registration_accepts_an_exact_owned_child_before_setsid(self):
        result = self.run_orchestration(
            "source child/preview-orchestration.sh; "
            "onpc_preview_configure child /tmp/onpc-preview-devkit-child; "
            "onpc_preview_shell_pid=$$; "
            "onpc_preview_record_owned_child_process \"$$\" "
            "onpc_preview_shell_start_time 'GNOME Shell'; "
            "sleep 20 & helper=$!; "
            "onpc_preview_devkit_path=/proc/$helper/exe; "
            "onpc_preview_find_mutter_devkit_descendant() { printf '%s\\n' \"$helper\"; }; "
            "onpc_preview_record_mutter_devkit; "
            "test \"$onpc_preview_devkit_pid\" = \"$helper\"; "
            "test -n \"$onpc_preview_devkit_start_time\"; "
            "onpc_preview_stop_owned_process \"$onpc_preview_devkit_pid\" "
            "\"$onpc_preview_devkit_start_time\" 'Mutter Devkit'; "
            "! kill -0 \"$helper\" 2>/dev/null",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("by exact identity", result.stderr)

    def test_child_invokes_the_shared_kiosk_request_gui(self):
        extension = (ROOT / "child" / "extension.js").read_text()
        makefile = (ROOT / "Makefile").read_text()
        extension_sources = next(
            line for line in makefile.splitlines()
            if line.startswith("EXTENSION_SOURCES :=")
        )

        self.assertIn("accessibility.js", extension_sources)
        self.assertIn("Gio.Subprocess.new", extension)
        self.assertIn("'/usr/bin/oh-no-parent-control'", extension)
        self.assertIn("'--child-overlay'", extension)
        self.assertNotIn("OH_NO_PARENT_CONTROL_REQUEST_APP", extension)
        self.assertNotIn("previewMode.js", extension)
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
        accessibility = (ROOT / "child" / "accessibility.js").read_text()
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        stylesheet = (ROOT / "child" / "stylesheet.css").read_text()
        interaction = (ROOT / "tests" / "ui" / "child_shell_interaction.py").read_text()

        self.assertIn("set_accessible_id", accessibility)
        self.assertIn("'child-screen-time-indicator'", indicator)
        self.assertIn("'child-request-button'", indicator)
        self.assertIn("'child-remaining-time'", indicator)
        self.assertIn("'child-request-tooltip'", indicator)
        self.assertIn("'child-countdown-menu'", indicator)
        self.assertIn("'child-countdown-animation-toggle'", indicator)
        self.assertIn("super._init(0.0, appName);", indicator)
        self.assertIn("appName = 'Oh No! Parent Control'", indicator)
        self.assertIn('this.setMenu(null);', indicator)
        self.assertNotIn('view-more-symbolic', indicator)
        self.assertIn("refreshEstimate()", indicator)
        self.assertIn(".screen-time-request-button {", stylesheet)
        self.assertIn("from tests.support.application_ui import ApplicationUI", interaction)
        self.assertIn("_panel().activate(REQUEST_BUTTON_ID)", interaction)
        self.assertIn("_panel().setValue(COUNTDOWN_ANIMATION_ID, True)", interaction)
        self.assertIn("_panel().getValue(COUNTDOWN_ANIMATION_ID) is True", interaction)
        self.assertNotIn("MutterInputBackend", interaction)
        self.assertNotIn("grab_focus", interaction)
        self.assertNotIn("X_KEYCODE", interaction)
        self.assertNotIn("set_overview", interaction)
        self.assertNotIn("OverviewActive", interaction)
        self.assertNotIn("get_extents", interaction)
        self.assertNotIn("click_at", interaction)
        self.assertNotIn(".oh-no-parent-control-content {", stylesheet)
        self.assertNotIn(".oh-no-parent-control-choice {", stylesheet)

    def test_request_icon_uses_the_product_logo(self):
        branding = (ROOT / "child" / "branding.js").read_text()
        extension = (ROOT / "child" / "extension.js").read_text()
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        stylesheet = (ROOT / "child" / "stylesheet.css").read_text()
        orchestration = (ROOT / "child" / "preview-orchestration.sh").read_text()

        self.assertIn("export function appLogoPath(extension)", branding)
        self.assertIn("app_logo_gnome_launcher.png", branding)
        self.assertIn("app_logo_gnome_launcher.png", orchestration)
        self.assertIn("appLogoPath(this)", extension)
        self.assertIn("Gio.FileIcon", indicator)
        self.assertIn("screen-time-request-logo", indicator)
        self.assertNotIn("hourglass-symbolic", indicator)
        self.assertNotIn("screen-time-request-plus", indicator)
        self.assertIn(".screen-time-request-logo {", stylesheet)
        self.assertIn("icon_size: 28", indicator)
        self.assertIn("icon-size: 28px;", stylesheet)
        self.assertIn("width: 28px;", stylesheet)
        self.assertIn("height: 28px;", stylesheet)
        self.assertIn("icon-shadow:", stylesheet)
        self.assertNotIn(".screen-time-request-hourglass", stylesheet)
        self.assertNotIn(".screen-time-request-plus", stylesheet)

    def test_request_icon_spins_during_the_final_ten_seconds(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()

        self.assertIn(
            "if (!this._countdownAnimationsEnabled || remainingSecs > 10)",
            indicator,
        )
        self.assertIn("rotation_angle_z: 360", indicator)
        self.assertIn("repeatCount: -1", indicator)
        self.assertIn("animationRequired: true", indicator)

    def test_secondary_click_menu_persists_the_countdown_animation_choice(self):
        indicator = (ROOT / "child" / "remainingTimeIndicator.js").read_text()
        extension = (ROOT / "child" / "extension.js").read_text()
        schema = (
            ROOT / "child" / "schemas" /
            "com.puffyslippers.oh-no-parent-control.child.gschema.xml"
        ).read_text()
        makefile = (ROOT / "Makefile").read_text()

        self.assertIn("'button-press-event'", indicator)
        self.assertIn(
            "event.get_button() !== Clutter.BUTTON_SECONDARY", indicator
        )
        self.assertIn("PopupMenu.PopupSwitchMenuItem", indicator)
        self.assertIn("this._text('COUNTDOWN_ANIMATION')", indicator)
        from common.oh_no_parent_control_ui import messages as m
        self.assertEqual(m.COUNTDOWN_ANIMATION.source, 'One minute count down animation')
        self.assertIn("set_boolean(COUNTDOWN_ANIMATION_KEY, enabled)", indicator)
        self.assertIn("getSettings(SETTINGS_SCHEMA)", extension)
        self.assertIn('<default>false</default>', schema)
        self.assertIn('name="one-minute-countdown-animation"', schema)
        self.assertIn("glib-compile-schemas", makefile)
