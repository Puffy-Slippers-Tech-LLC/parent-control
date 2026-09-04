import pathlib
import subprocess
import tempfile
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

    def test_preview_wrapper_uses_the_reusable_orchestration_boundary(self):
        wrapper = (ROOT / "child" / "preview").read_text()
        orchestration = (ROOT / "child" / "preview-orchestration.sh").read_text()

        self.assertIn('source "$child_dir/preview-orchestration.sh"', wrapper)
        self.assertIn("onpc_preview_prepare_environment", wrapper)
        self.assertIn("onpc_preview_start", wrapper)
        self.assertIn("onpc_preview_wait_for_reload", wrapper)
        self.assertIn("trap onpc_preview_cleanup EXIT HUP INT TERM", wrapper)
        self.assertIn("inotifywait", orchestration)
        self.assertIn("child-preview-generation-$generation.log", orchestration)
        self.assertIn("setsid", orchestration)
        self.assertIn('"$onpc_preview_source_dir"/*.mjs', orchestration)
        self.assertNotIn('gnome-shell --nested', wrapper)
        self.assertIn('--child-overlay', orchestration)

    def test_environment_and_command_construction_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary) / "runtime"
            result = self.run_orchestration(
                "source child/preview-orchestration.sh; "
                f"onpc_preview_configure '{ROOT / 'child'}' '{root}'; "
                "onpc_preview_build_shell_command; "
                "printf '%s\\n' \"$onpc_preview_log_dir\" \"${onpc_preview_shell_command[*]}\""
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                f"{root}/logs",
                "dbus-run-session -- gnome-shell --devkit --wayland --force-animations",
            ],
        )

    def test_environment_preparation_uses_private_runtime_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = pathlib.Path(temporary)
            fake_bin = temporary_path / "bin"
            fake_bin.mkdir()
            for command in ("gsettings", "glib-compile-schemas"):
                executable = fake_bin / command
                executable.write_text("#!/usr/bin/env bash\nexit 0\n")
                executable.chmod(0o755)
            schema_source = temporary_path / "schemas-source"
            schema_source.mkdir()
            runtime = temporary_path / "runtime"
            result = self.run_orchestration(
                f"PATH='{fake_bin}':$PATH "
                f"ONPC_PREVIEW_SYSTEM_SCHEMA_DIR='{schema_source}' "
                "bash -c 'source child/preview-orchestration.sh; "
                f"onpc_preview_configure \"{ROOT / 'child'}\" \"{runtime}\"; "
                "onpc_preview_prepare_environment; "
                "printf \"%s\\n\" \"$XDG_DATA_HOME\" \"$GSETTINGS_SCHEMA_DIR\"; "
                "test -L \"$XDG_DATA_HOME/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/indicatorLogic.mjs\"'"
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"{runtime}/data", f"{runtime}/schemas"])

    def test_readiness_timeout_reports_generation_and_log(self):
        result = self.run_orchestration(
            "source child/preview-orchestration.sh; "
            "onpc_preview_configure child /tmp/onpc-preview-test; "
            "onpc_preview_ready_timeout=0; onpc_preview_log_path=/tmp/preview.log; "
            "sleep 2 & pid=$!; "
            "onpc_preview_wait_for_readiness \"$pid\" 7; status=$?; kill \"$pid\"; wait \"$pid\" 2>/dev/null || true; exit \"$status\""
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("generation 7 did not become ready within 0s; log: /tmp/preview.log", result.stderr)

    def test_reload_choices_and_cleanup_are_controlled(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as temporary:
            result = self.run_orchestration(
                "source child/preview-orchestration.sh; "
                "onpc_preview_source_event_is_reloadable child/extension.js; "
                "onpc_preview_source_event_is_reloadable child/indicatorLogic.mjs; "
                "! onpc_preview_source_event_is_reloadable child/remaining-timer-seconds.png; "
                f"onpc_preview_configure child '{temporary}'; "
                "mkdir -p \"$onpc_preview_root/logs\"; touch \"$onpc_preview_root/logs/test.log\"; "
                "onpc_preview_cleanup; test ! -e \"$onpc_preview_root\""
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cleanup_terminates_its_owned_process_group(self):
        result = self.run_orchestration(
            "source child/preview-orchestration.sh; "
            "onpc_preview_configure child /tmp/onpc-preview-owned-process; "
            "setsid sleep 20 & onpc_preview_shell_pid=$!; pid=$onpc_preview_shell_pid; "
            "onpc_preview_stop_shell; ! kill -0 \"$pid\" 2>/dev/null"
        )

        self.assertEqual(result.returncode, 0, result.stderr)

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
