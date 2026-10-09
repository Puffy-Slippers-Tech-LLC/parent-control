"""Temporary engineering probe for Task 044; explicit guarded focus experiment."""
import json
import hashlib
import os
import pwd
import subprocess
import sys

account = pwd.getpwnam('onpc-child-riley')
os.initgroups(account.pw_name, account.pw_gid)
os.setgid(account.pw_gid)
os.setuid(account.pw_uid)
runtime = '/run/user/' + str(account.pw_uid)
os.environ.clear()
os.environ.update(HOME=account.pw_dir, USER=account.pw_name, LANG='C.UTF-8',
                  XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS='unix:path=' + runtime + '/bus',
                  NO_AT_BRIDGE='0')
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
Atspi.set_timeout(2000, 5000)
mode = sys.argv[1] if len(sys.argv) > 1 else 'read'
assert mode in ('read', 'focus', 'overview', 'telemetry', 'compositor')

def session():
    ids = subprocess.run(['/usr/bin/loginctl', 'list-sessions', '--no-legend', '--no-pager'],
                         capture_output=True, text=True, check=True, timeout=5).stdout.splitlines()
    active = []
    owned = []
    for row in ids:
        identity = row.split()[0]
        raw = subprocess.run(['/usr/bin/loginctl', 'show-session', identity, '--no-pager',
            '-p', 'User', '-p', 'Remote', '-p', 'Class', '-p', 'Type', '-p', 'Seat',
            '-p', 'Active', '-p', 'LockedHint'], capture_output=True, text=True,
            check=True, timeout=5).stdout
        props = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        if (props.get('Remote') == 'no' and props.get('Seat') == 'seat0'
                and props.get('User') == str(account.pw_uid)
                and props.get('Class') in ('user', 'user-early')
                and props.get('Type') in ('wayland', 'x11')):
            owned.append((identity, props))
        if props.get('Remote') == 'no' and props.get('Seat') == 'seat0' and props.get('Active') == 'yes':
            active.append((identity, props))
    assert len(active) == 1
    if mode == 'telemetry':
        assert len(owned) == 1
        return owned[0]
    identity, props = active[0]
    assert props['User'] == str(account.pw_uid) and props['Class'] in ('user', 'user-early')
    assert props['Type'] in ('wayland', 'x11')
    if mode in ('focus', 'overview'):
        assert props['LockedHint'] == 'no'
    return identity, props

before_session = session()
active = subprocess.run(['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
    '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive'],
    capture_output=True, text=True, check=True, timeout=5).stdout.strip()
assert active in ('(true,)', '(false,)')
overview = subprocess.run(['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.Shell',
    '--object-path', '/org/gnome/Shell', '--method', 'org.freedesktop.DBus.Properties.Get',
    'org.gnome.Shell', 'OverviewActive'], capture_output=True, text=True,
    check=True, timeout=5).stdout.strip()
assert overview in ('(<true>,)', '(<false>,)')
print(json.dumps({'screensaver_active': active == '(true,)', 'child_context': os.getuid() == account.pw_uid}))
seen = set()
count = 0
targets = []
foreign_focus = []
activity = {}
draft_states = {}

def scan(node, app='other', window=None):
    global count
    assert node is not None and count < 6000
    token = (node.get_process_id(), node.get_id())
    if node in seen:
        return
    seen.add(node)
    count += 1
    role = node.get_role_name()
    states = node.get_state_set()
    showing = states.contains(Atspi.StateType.SHOWING)
    focused = states.contains(Atspi.StateType.FOCUSED)
    modal = states.contains(Atspi.StateType.MODAL)
    identity = node.get_accessible_id()
    for control in ('draft', 'submitted', 'score'):
        if identity == 'onpc-fixture-native-primary-' + control:
            assert control not in activity
            assert role != 'password text'
            if control == 'draft':
                text = node.get_text_iface()
                length = text.get_character_count()
                assert 0 <= length <= 256
                value = Atspi.Text.get_text(node, 0, length)
            else:
                value = node.get_name()
            activity[control] = (node, node.get_process_id(), value)
            if control == 'draft':
                draft_states.update(focused=focused, showing=showing)
    if role == 'application':
        app = 'shell' if node.get_name().casefold() in ('gnome-shell', 'gnome shell') else 'other'
        if app == 'shell':
            assert os.stat('/proc/' + str(node.get_process_id())).st_uid == account.pw_uid
    assert not states.contains(Atspi.StateType.DEFUNCT)
    if showing and app != 'shell' and focused:
        foreign_focus.append(node)
    if mode in ('focus', 'overview') and showing:
        assert not modal and role not in ('password text', 'dialog', 'alert')
        if app == 'shell' and role == 'toggle button' and node.get_name() == 'Activities':
            assert states.contains(Atspi.StateType.SENSITIVE)
            targets.append(node)
    if role in ('window', 'frame', 'dialog', 'alert'):
        window = token
    if showing and (focused or modal or role in ('window', 'frame', 'password text', 'dialog', 'alert')):
        attributes = node.get_attributes()
        identity = attributes.get('automation-id', '')
        print(json.dumps({'role': role, 'focused': focused, 'modal': modal, 'app': app,
            'active': states.contains(Atspi.StateType.ACTIVE),
            'window': window, 'node': token,
            'fixture': identity.startswith('onpc-fixture-native-primary'),
            'hint': role == 'label' and node.get_name() == 'Click or press a key to unlock'}))
    if role == 'password text':
        return
    for index in range(node.get_child_count()):
        child = node.get_child_at_index(index)
        assert child is not None
        scan(child, app, window)

scan(Atspi.get_desktop(0))
print(json.dumps({'nodes_read': count}))
if mode == 'compositor':
    # Fixed read-only engineering query. Refusal never enables unsafe mode,
    # retries through another route, changes focus or authorizes lock input.
    from gi.repository import Gio, GLib
    assert set(activity) == {'draft', 'submitted', 'score'}
    pid = activity['draft'][1]
    assert type(pid) is int and pid > 0
    expression = '''(() => {
        const shield = Main.screenShield;
        const focus = global.stage.get_key_focus();
        return {active: shield.active, locked: shield.locked,
            modal_count: Main.modalCount, action_mode: Main.actionMode,
            shield_grab: !!shield._grab,
            grab_revoked: shield._grab ? shield._grab.is_revoked() : null,
            stage_grab_is_ui_group: global.stage.get_grab_actor() === Main.uiGroup,
            key_focus_in_shield: !!focus && shield.actor.contains(focus),
            compositor_focus_matches_fixture:
                global.display.focus_window?.get_pid() === FIXTURE_PID};
    })()'''.replace('FIXTURE_PID', str(pid))
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    success, raw = bus.call_sync('org.gnome.Shell', '/org/gnome/Shell',
        'org.gnome.Shell', 'Eval', GLib.Variant('(s)', (expression,)),
        GLib.VariantType.new('(bs)'), Gio.DBusCallFlags.NONE, 5000, None).unpack()
    assert type(success) is bool and type(raw) is str and len(raw) <= 2048
    print(json.dumps({'compositor_probe_available': success}), flush=True)
    if not success:
        print(json.dumps({'compositor_probe_unavailable_reason':
                         'disabled' if raw == '' else 'query-failed'}), flush=True)
    if success:
        result = json.loads(raw)
        assert type(result) is dict and set(result) == {
            'active', 'locked', 'modal_count', 'action_mode', 'shield_grab',
            'grab_revoked', 'stage_grab_is_ui_group', 'key_focus_in_shield',
            'compositor_focus_matches_fixture'}
        assert all(type(result[key]) is bool for key in (
            'active', 'locked', 'shield_grab', 'key_focus_in_shield',
            'stage_grab_is_ui_group', 'compositor_focus_matches_fixture'))
        assert all(type(result[key]) is int and 0 <= result[key] <= 255
                   for key in ('modal_count', 'action_mode'))
        assert result['grab_revoked'] is None or type(result['grab_revoked']) is bool
        print(json.dumps({'compositor_state': result}), flush=True)
if mode == 'telemetry':
    assert set(activity) == {'draft', 'submitted', 'score'}
    print(json.dumps({'probe_summary': {
        'child_active': before_session[1]['Active'] == 'yes',
        'child_locked': before_session[1]['LockedHint'] == 'yes',
        'screensaver_active': active == '(true,)',
        'overview_active': overview == '(<true>,)',
        'draft': draft_states, 'foreign_focus_count': len(foreign_focus),
        'activity_sha256': hashlib.sha256(json.dumps({key:
            (value[0].get_id(), value[1], value[2])
            for key, value in activity.items()}, sort_keys=True).encode()).hexdigest(),
        'fixture_pid': activity['draft'][1]}}), flush=True)
if mode in ('focus', 'overview'):
    assert len(targets) == 1 and session() == before_session and active == '(false,)'
    assert set(activity) == {'draft', 'submitted', 'score'}
    before_activity = dict(activity)
    target = targets[0]
    if mode == 'focus':
        component = target.get_component_iface()
        assert component is not None
        accepted = component.grab_focus()
    else:
        command = ['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.Shell',
                   '--object-path', '/org/gnome/Shell',
                   '--method', 'org.freedesktop.DBus.Properties.']
        overview = subprocess.run([*command[:-1], command[-1] + 'Get',
            'org.gnome.Shell', 'OverviewActive'], capture_output=True, text=True,
            check=True, timeout=5).stdout.strip()
        assert overview == '(<false>,)'
        subprocess.run([*command[:-1], command[-1] + 'Set',
            'org.gnome.Shell', 'OverviewActive', '<true>'], capture_output=True,
            text=True, check=True, timeout=5)
        accepted = True
    print(json.dumps({'action': mode, 'returned': accepted}), flush=True)
    assert accepted
    seen.clear()
    targets.clear()
    foreign_focus.clear()
    count = 0
    activity.clear()
    scan(Atspi.get_desktop(0))
    assert targets == [target] and session() == before_session
    focused = target.get_state_set().contains(Atspi.StateType.FOCUSED)
    print(json.dumps({'shell_target_focused': focused, 'foreign_focus_count': len(foreign_focus)}), flush=True)
    print(json.dumps({'same_activity_nodes_pid_values': activity == before_activity}), flush=True)
    assert activity == before_activity
    assert (focused or mode == 'overview') and not foreign_focus
