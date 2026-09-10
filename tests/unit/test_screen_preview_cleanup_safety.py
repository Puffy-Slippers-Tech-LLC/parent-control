"""Preview cleanup is confined to Popen handles created by its own launcher."""

from unittest.mock import Mock, patch
import subprocess

import pytest

from oh_no_parent_control_kiosk.preview import OwnedProcess, PreviewSession, private_environment


@pytest.mark.parametrize("exited, timeout", [(True, False), (False, False), (False, True)])
def test_only_the_direct_unreaped_child_is_signalled(exited, timeout):
    child = Mock()
    child.poll.return_value = 0 if exited else None
    if timeout:
        child.wait.side_effect = [subprocess.TimeoutExpired("preview", 5), 0]
    with patch("oh_no_parent_control_kiosk.preview.subprocess.Popen", return_value=child) as spawn:
        owned = OwnedProcess(["mutter"])
        owned.close()
    spawn.assert_called_once_with(["mutter"], start_new_session=True)
    assert child.terminate.call_count == (0 if exited else 1)
    assert child.kill.call_count == (1 if timeout else 0)


def test_startup_failure_cleans_up_already_recorded_services(tmp_path):
    child = Mock()
    child.poll.return_value = None
    with patch("oh_no_parent_control_kiosk.preview.subprocess.Popen", return_value=child), \
            patch("oh_no_parent_control_kiosk.preview.wait_until", side_effect=RuntimeError("failed")):
        with pytest.raises(RuntimeError, match="failed"):
            PreviewSession.__init__(PreviewSession.__new__(PreviewSession), None, {})
    child.terminate.assert_called_once_with()
    child.wait.assert_called_once_with(timeout=5)


def test_host_bus_display_and_scaling_never_reach_private_compositor(tmp_path):
    host = {"DBUS_SESSION_BUS_ADDRESS": "host-bus", "AT_SPI_BUS_ADDRESS": "host-atspi",
            "WAYLAND_DISPLAY": "host-wayland", "DISPLAY": ":0", "GDK_SCALE": "2",
            "GDK_DPI_SCALE": "0.5", "GSETTINGS_BACKEND": "dconf", "HOME": "/home/example"}
    environment = private_environment(tmp_path, host)
    assert environment["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={tmp_path}/runtime/bus"
    assert environment["GSETTINGS_BACKEND"] == "keyfile"
    assert environment["HOME"] == host["HOME"]
    assert environment["AT_SPI_BUS_ADDRESS"] == environment["DBUS_SESSION_BUS_ADDRESS"]
    for key in ("WAYLAND_DISPLAY", "DISPLAY", "GDK_SCALE", "GDK_DPI_SCALE"):
        assert key not in environment
    assert host["GSETTINGS_BACKEND"] == "dconf"
