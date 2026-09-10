"""Real Flatpak installation/launch; requires unprivileged kernel namespaces."""

import os
from pathlib import Path
from unittest import mock

from dbusmock.testcase import BusType, PrivateDBus

from tests.fixtures import build_test_applications as fixtures


def test_flatpak_fixture_installs_launches_and_terminates_with_private_services(tmp_path):
    protected_paths = (
        Path.home() / ".local/share/flatpak",
        Path.home() / ".config/flatpak",
        Path("/var/lib/flatpak"),
    )
    before = {path: path.exists() for path in protected_paths}
    output = tmp_path / "payload"
    fixtures.build(output)
    fixtures.verify(output)
    # No host services are activated. Restore the address exported by dbusmock.
    with mock.patch.dict(os.environ), PrivateDBus(BusType.SYSTEM) as bus:
        process = fixtures.launch_flatpak(
            output, os.geteuid(), system_bus_address=bus.address)
        try:
            assert fixtures.report_process_identity(process) == {
                "pid": process.pid, "uid": os.geteuid(),
            }
        finally:
            fixtures.terminate(process)
    assert before == {path: path.exists() for path in protected_paths}
