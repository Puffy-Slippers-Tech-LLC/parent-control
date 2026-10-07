"""Real GJS/GSettings recovery on a private bus and pytest-owned keyfile backend."""

import os
import shutil
import subprocess
import time

from gi.repository import Gio, GLib
import pytest

from tests.support.dbus import open_bus, spin_until
from tests.support.paths import ROOT

BUS = 'com.puffyslippers.OhNoParentControl.Wellbeing'
PATH = '/com/puffyslippers/OhNoParentControl/Wellbeing'
SCHEMA = ('org.gnome.desktop.notifications.application:'
          '/org/gnome/desktop/notifications/application/gnome-wellbeing-panel/')
JOURNAL = 'com.puffyslippers.oh-no-parent-control.child'


@pytest.fixture
def helper(tmp_path, dbusmock_session):
    child = tmp_path / 'child'
    schemas = child / 'schemas'
    schemas.mkdir(parents=True)
    for name in ('wellbeingService.js', 'wellbeingLogic.mjs', 'wellbeingSuppression.js'):
        shutil.copyfile(ROOT / 'child' / name, child / name)
    shutil.copyfile(ROOT / 'child/schemas' / f'{JOURNAL}.gschema.xml',
                    schemas / f'{JOURNAL}.gschema.xml')
    subprocess.run(['glib-compile-schemas', str(schemas)], check=True, timeout=10)
    env = {**os.environ, 'DBUS_SESSION_BUS_ADDRESS': dbusmock_session.address,
           'GSETTINGS_BACKEND': 'keyfile', 'GSETTINGS_SCHEMA_DIR': str(schemas),
           'XDG_CONFIG_HOME': str(tmp_path / 'config'), 'HOME': str(tmp_path)}
    client = open_bus(dbusmock_session.address)
    children = []

    class Helper:
        def start_client(self):
            # Exercise the production client and GIO name-watch ordering, with
            # only the Shell manager/session inputs replaced on this private bus.
            script = child / 'client.js'
            script.write_text("""
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {WellbeingSuppression} from './wellbeingSuppression.js';
const signals = {connect() { return 1; }, disconnect() {}};
const manager = {...signals, dailyLimitEnabled: true,
    parentalControlsSessionLimitsEnabled: true,
    dailyLimitTime: GLib.get_real_time() / 1e6 + 65,
    getCurrentTime: () => GLib.get_real_time() / 1e6};
const session = {...signals, isLocked: false, isGreeter: false};
const client = new WellbeingSuppression(manager, session, () => ({reminders: [{}]}));
const bus = Gio.DBus.session;
const xml = '<node><interface name="com.example.WellbeingClient"><method name="Close"/></interface></node>';
const exported = Gio.DBusExportedObject.wrapJSObject(xml, {Close() { client.close(); }});
exported.export(bus, '/com/example/WellbeingClient');
Gio.bus_own_name_on_connection(bus, 'com.example.WellbeingClient', Gio.BusNameOwnerFlags.NONE,
    null, null);
const loop = new GLib.MainLoop(null, false);
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 15, () => {
    client.close(); loop.quit(); return GLib.SOURCE_REMOVE;
});
loop.run();
""", encoding='utf-8')
            log = (tmp_path / f'client-{len(children)}.log').open('w+')
            process = subprocess.Popen(['gjs', '-m', str(script)], env=env,
                                       stdout=log, stderr=log)
            children.append((process, log))

            def ready():
                if process.poll() is not None:
                    log.seek(0)
                    pytest.fail(log.read())
                try:
                    client.call_sync('com.example.WellbeingClient', '/com/example/WellbeingClient',
                                     'org.freedesktop.DBus.Introspectable', 'Introspect', None,
                                     None, Gio.DBusCallFlags.NO_AUTO_START, 500, None)
                    return True
                except GLib.Error:
                    return False
            spin_until(ready)

        def close_client(self):
            client.call_sync('com.example.WellbeingClient', '/com/example/WellbeingClient',
                             'com.example.WellbeingClient', 'Close', None, None,
                             Gio.DBusCallFlags.NO_AUTO_START, 2000, None)

        def settings(self, action, schema=SCHEMA, key='show-banners', value=None):
            command = ['gsettings', action, schema, key]
            if value is not None:
                command.append(value)
            return subprocess.run(command, env=env, check=True, timeout=5,
                                  text=True, capture_output=True).stdout.strip()

        def call(self, end, connection=client, token='00000000-0000-0000-0000-000000000001'):
            return connection.call_sync(BUS, PATH, BUS, 'SetWindow',
                                        GLib.Variant('(sd)', (token, end)), None,
                                        Gio.DBusCallFlags.NO_AUTO_START, 2000, None)

        def user_value(self):
            script = """const s = new imports.gi.Gio.Settings({
                schema_id: 'org.gnome.desktop.notifications.application',
                path: '/org/gnome/desktop/notifications/application/gnome-wellbeing-panel/'});
                print(s.get_user_value('show-banners')?.get_boolean() ?? 'default');"""
            return subprocess.run(['gjs', '-c', script], env=env, check=True,
                                  timeout=5, text=True, capture_output=True).stdout.strip()

        def start(self):
            log = (tmp_path / f'helper-{len(children)}.log').open('w+')
            process = subprocess.Popen(['gjs', '-m', str(child / 'wellbeingService.js')],
                                       env=env, stdout=log, stderr=log)
            children.append((process, log))

            def ready():
                if process.poll() is not None:
                    log.seek(0)
                    pytest.fail(log.read())
                try:
                    xml = client.call_sync(BUS, PATH, 'org.freedesktop.DBus.Introspectable',
                                           'Introspect', None, None, Gio.DBusCallFlags.NO_AUTO_START,
                                           500, None).unpack()[0]
                    # GDBus can introspect an empty node before export completes.
                    return f'interface name="{BUS}"' in xml and 'name="SetWindow"' in xml
                except GLib.Error:
                    return False
            spin_until(ready)
            return process

    try:
        yield Helper()
    finally:
        # Signal only Popen-owned children; never discover a process by name/PID.
        for process, log in children:
            try:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    pytest.fail('Wellbeing service did not stop')
            finally:
                log.close()
        client.close_sync(None)


@pytest.mark.parametrize('original', ['true', 'false', 'default'])
def test_real_settings_backup_and_restore_even_after_user_edit(helper, original):
    if original != 'default':
        helper.settings('set', value=original)
    helper.start()
    helper.call(time.time() + 5)
    assert helper.settings('get') == 'false'
    assert helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == f"'{original}'"
    helper.settings('set', value='true')
    helper.call(0)
    assert helper.settings('get') == ('true' if original == 'default' else original)
    assert helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == "''"
    # Reset must remove the explicit override, rather than write true.
    assert helper.user_value() == original


def test_real_owner_loss_expiry_shutdown_and_crash_recovery(helper, dbusmock_session):
    process = helper.start()
    transient = open_bus(dbusmock_session.address)
    try:
        helper.call(time.time() + 5, transient)
    finally:
        transient.close_sync(None)
    spin_until(lambda: helper.settings('get') == 'true')

    helper.call(time.time() + 0.5)
    assert helper.settings('get') == 'false'
    spin_until(lambda: helper.settings('get') == 'true')

    helper.call(time.time() + 5)
    process.terminate()
    process.wait(timeout=5)
    assert helper.settings('get') == 'true'

    process = helper.start()
    helper.call(time.time() + 5)
    process.kill()  # Deliberately bypass cleanup in this explicitly owned child.
    process.wait(timeout=5)
    assert helper.settings('get') == 'false'
    helper.start()
    assert helper.settings('get') == 'true'
    assert helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == "''"


def test_real_invalid_deadline_cannot_change_settings(helper):
    helper.start()
    for end in [time.time() + 60, -1, float('nan')]:
        with pytest.raises(GLib.Error):
            helper.call(end)
    assert helper.settings('get') == 'true'
    assert helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == "''"


def test_old_extension_cancellation_cannot_release_new_instance(helper):
    helper.start()
    helper.call(time.time() + 5)
    new_token = '00000000-0000-0000-0000-000000000002'
    helper.call(time.time() + 5, token=new_token)
    helper.call(0)
    assert helper.settings('get') == 'false'
    helper.call(0, token=new_token)
    assert helper.settings('get') == 'true'


def test_duplicate_service_cannot_restore_the_active_owners_override(helper):
    helper.start()
    helper.call(time.time() + 5)
    duplicate = helper.start()
    assert duplicate.wait(timeout=5) == 0
    assert helper.settings('get') == 'false'
    helper.call(0)
    assert helper.settings('get') == 'true'


@pytest.mark.parametrize('crash', [False, True])
def test_production_client_reacquires_after_helper_restart(helper, crash):
    process = helper.start()
    helper.start_client()
    spin_until(lambda: helper.settings('get') == 'false')
    if crash:
        process.kill()
    else:
        process.terminate()
    process.wait(timeout=5)
    replacement = helper.start()
    spin_until(lambda: helper.settings('get') == 'false')
    assert replacement.poll() is None
    assert helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == "'default'"
    helper.close_client()
    # Close returns before the client's asynchronous cancellation completes.
    # Restoration commits the banner value before clearing its durable journal.
    spin_until(lambda: helper.settings('get') == 'true' and
               helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == "''")
    assert helper.settings('get', JOURNAL, 'wellbeing-banner-backup') == "''"
    # A closed extension cannot reacquire when another helper appears.
    replacement.terminate()
    replacement.wait(timeout=5)
    helper.start()
    assert helper.settings('get') == 'true'
