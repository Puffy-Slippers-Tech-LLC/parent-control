"""Host GUI qualification of real payloads; installed Snap remains a VM task."""

import os
from pathlib import Path
import subprocess
from unittest import mock

import pytest
from dbusmock.testcase import BusType, PrivateDBus

from tests.e2e.accessible_ui import AccessibleUI, public_automation_id
from tests.e2e.fixture_ui import FixtureUI
from tests.fixtures import build_test_applications as fixtures

pytestmark = pytest.mark.ui


@pytest.fixture(scope='module')
def gui_payload(tmp_path_factory):
    payload = tmp_path_factory.mktemp('onpc-gui-fixture') / 'payload'
    fixtures.build(payload)
    return payload


@pytest.mark.parametrize('kind', ['native', 'game', 'flatpak', 'snap'])
def test_payload_gui_preserves_independent_activity(hermetic_ui_session, gui_payload, tmp_path, kind):
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GLib
    from dogtail import rawinput
    ui = AccessibleUI(Atspi, timeout=15, query_errors=(GLib.Error,),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    protected = [Path.home() / '.local/share/flatpak', Path('/var/lib/flatpak')]
    before = [path.exists() for path in protected]
    processes = []
    with mock.patch.dict(os.environ), PrivateDBus(BusType.SYSTEM) as bus:
        environment = dict(hermetic_ui_session.environment)
        if kind == 'flatpak':
            environment = fixtures.prepare_flatpak(gui_payload, os.geteuid(), system_bus_address=bus.address)
            for key in ('WAYLAND_DISPLAY', 'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS',
                        'AT_SPI_BUS_ADDRESS', 'XDG_RUNTIME_DIR'):
                if key in hermetic_ui_session.environment:
                    environment[key] = hermetic_ui_session.environment[key]
            command = ['flatpak', '--user', 'run', '--die-with-parent', '--no-documents-portal', fixtures.APP_ID]
        else:
            command = [str(gui_payload / kind / 'onpc-test-application')]
        if kind == 'snap':
            # Exercise the exact packaged launcher/runtime without a host Snap
            # installation. This does not qualify snapd confinement or launch.
            environment['SNAP'] = str(gui_payload / 'snap-build')
            command = [str(gui_payload / 'snap-build/bin/gui')]
        environment['DBUS_SYSTEM_BUS_ADDRESS'] = bus.address
        environment['NO_AT_BRIDGE'] = '0'
        environment['GTK_A11Y'] = 'atspi'
        with (tmp_path / (kind + '.log')).open('wb') as log:
            try:
                for instance in ('primary', 'secondary'):
                    processes.append(subprocess.Popen([*command, '--instance', instance],
                        env=environment, stdout=log, stderr=subprocess.STDOUT))
                    view = FixtureUI(ui, kind, instance)
                    view.ready()
                    view.focus_draft()
                    # Recipient is reacquired by public ID immediately before input.
                    assert ui.has_state(view.target('draft'), Atspi.StateType.FOCUSED)
                    rawinput.keyCombo('<Control>a')
                    assert ui.has_state(view.target('draft'), Atspi.StateType.FOCUSED)
                    rawinput.typeText('ONPC ' + instance)
                    ui.wait(lambda: view.text('draft') == 'ONPC ' + instance, 'fixture-typed')
                    view.submit()
                    view.move()
                primary = FixtureUI(ui, kind)
                assert primary.snapshot() == {
                    'draft': 'ONPC primary', 'submitted': 'ONPC primary', 'score': 'Moves: 1; token: 1'}
                secondary = FixtureUI(ui, kind, 'secondary')
                ui.activate(secondary.target('close'))
                secondary.closed(surrounding_id=primary.scope)
                assert primary.snapshot()['draft'] == 'ONPC primary'
            except Exception:
                surface = ui.find_id(f'onpc-fixture-{kind}-primary', showing=False)
                if surface is not None:
                    print('Fixture public IDs:', [
                        (public_automation_id(node), node.get_role_name(), ui.showing(node))
                        for node in ui.nodes(surface)])
                print('Fixture log:', tmp_path / (kind + '.log'))
                raise
            finally:
                for process in reversed(processes):
                    fixtures.terminate(process)
    assert before == [path.exists() for path in protected]
