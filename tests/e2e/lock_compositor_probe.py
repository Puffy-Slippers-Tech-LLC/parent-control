"""Temporary Task 044 native read; never input or acceptance authority.

The fixed Ubuntu/Mutter layout below was checked against upstream 50.1 and
the installed keyboard GType. No alternate offsets or missing-symbol retries.
Every debugger lookup/call aborts on error, with guaranteed detach and a guest
timeout which owns the debugger process. Remove with the temporary timeline.
"""
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys


assert os.geteuid() == 0 and len(sys.argv) in (2, 3)
experiment = sys.argv[2] if len(sys.argv) == 3 else 'read'
assert experiment in ('read', 'resync')
fixture_pid = int(sys.argv[1])
assert fixture_pid > 0
account = pwd.getpwnam('onpc-child-riley')
assert Path('/proc/' + str(fixture_pid)).stat().st_uid == account.pw_uid
runtime = '/run/user/' + str(account.pw_uid)
env = dict(HOME=account.pw_dir, USER=account.pw_name, LANG='C.UTF-8',
           XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS='unix:path=' + runtime + '/bus')


def child_call(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, check=True,
        timeout=5, env=env, user=account.pw_uid, group=account.pw_gid,
        extra_groups=os.getgrouplist(account.pw_name, account.pw_gid)).stdout.strip()


def locked_session():
    rows = subprocess.run(['/usr/bin/loginctl', 'list-sessions', '--no-legend', '--no-pager'],
        capture_output=True, text=True, check=True, timeout=5).stdout.splitlines()
    active = []
    for row in rows:
        identity = row.split()[0]
        raw = subprocess.run(['/usr/bin/loginctl', 'show-session', identity, '--no-pager',
            '-p', 'User', '-p', 'Remote', '-p', 'Class', '-p', 'Type', '-p', 'Seat',
            '-p', 'Active', '-p', 'LockedHint'], capture_output=True, text=True,
            check=True, timeout=5).stdout
        props = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        if props.get('Remote') == 'no' and props.get('Seat') == 'seat0' and props.get('Active') == 'yes':
            active.append((identity, props))
    assert len(active) == 1
    identity, props = active[0]
    assert props['User'] == str(account.pw_uid) and props['Class'] in ('user', 'user-early')
    assert props['Type'] == 'wayland' and props['LockedHint'] == 'yes'
    return identity, props


before = locked_session()
assert child_call(['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
    '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive']) == '(true,)'
raw_pid = child_call(['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.freedesktop.DBus',
    '--object-path', '/org/freedesktop/DBus', '--method',
    'org.freedesktop.DBus.GetConnectionUnixProcessID', 'org.gnome.Shell'])
match = re.fullmatch(r'\(uint32 ([0-9]+),\)', raw_pid)
assert match
shell_pid = int(match[1])
shell = Path('/proc/' + str(shell_pid))
assert shell.stat().st_uid == account.pw_uid and (shell / 'exe').resolve() == Path('/usr/bin/gnome-shell')
start = (shell / 'stat').read_text().split()[21]
version = subprocess.run(['/usr/bin/dpkg-query', '--show', '--showformat=${Version}',
    'libmutter-18-0'], capture_output=True, text=True, check=True, timeout=5).stdout
assert version == '50.1-0ubuntu2.4' and os.uname().machine == 'x86_64'

native = r'''
import gdb, json
result = {'available': False}
symbols = ('shell_global_get', 'shell_global_get_stage', 'shell_global_get_context',
    'shell_global_get_display', 'meta_context_get_wayland_compositor',
    'clutter_stage_get_grab_actor', 'clutter_stage_get_key_focus',
    'clutter_actor_get_name', 'clutter_actor_contains', 'g_type_name_from_instance',
    'meta_display_get_focus_window', 'meta_window_get_pid',
    'meta_window_get_wayland_surface', 'meta_wayland_keyboard_get_focus_surface',
    'meta_wayland_surface_get_window', 'clutter_input_focus_is_focused',
    'g_object_notify')

def read(expression):
    result['last_query'] = expression
    return gdb.parse_and_eval(expression)

def pointer(expression):
    value = read('(void*)' + expression)
    if int(value) == 0:
        raise ValueError('null-pointer')
    return value

def assign(name, value):
    gdb.set_convenience_variable('onpc_' + name, value)

def typename(variable):
    value = pointer('g_type_name_from_instance($onpc_' + variable + ')')
    return value.cast(gdb.lookup_type('char').pointer()).string(length=96).split('\0', 1)[0]

try:
    # Lookup the entire query before any inferior call; no next call after error.
    for symbol in symbols:
        try:
            pointer(symbol)
        except gdb.error:
            result['missing_symbol'] = symbol
            raise
    assign('global', pointer('shell_global_get()'))
    assign('stage', pointer('shell_global_get_stage($onpc_global)'))
    assign('grab', pointer('clutter_stage_get_grab_actor($onpc_stage)'))
    assign('focus', pointer('clutter_stage_get_key_focus($onpc_stage)'))
    result['focus_is_unlock_dialog'] = typename('focus') == 'Gjs_ui_unlockDialog_UnlockDialog'
    name = pointer('clutter_actor_get_name($onpc_grab)').cast(gdb.lookup_type('char').pointer())
    result['grab_is_ui_group'] = name.string(length=32).split('\0', 1)[0] == 'uiGroup'
    result['grab_contains_focus'] = bool(read('(int)clutter_actor_contains($onpc_grab, $onpc_focus)'))
    assign('display', pointer('shell_global_get_display($onpc_global)'))
    assign('window', pointer('meta_display_get_focus_window($onpc_display)'))
    if not typename('window').startswith('MetaWindow'):
        raise ValueError('window-type')
    result['compositor_focus_matches_fixture'] = int(read('(int)meta_window_get_pid($onpc_window)')) == EXPECTED_PID
    assign('fixture_surface', pointer('meta_window_get_wayland_surface($onpc_window)'))
    assign('context', pointer('shell_global_get_context($onpc_global)'))
    assign('compositor', pointer('meta_context_get_wayland_compositor($onpc_context)'))
    # Exact checked 50.1 Ubuntu x86-64 layout, diagnostic only.
    assign('seat', pointer('*(void**)((char*)$onpc_compositor + 264)'))
    if not bool(read('*(void**)$onpc_seat == $onpc_compositor')):
        raise ValueError('seat-binding')
    assign('keyboard', pointer('*(void**)((char*)$onpc_seat + 48)'))
    if typename('keyboard') != 'MetaWaylandKeyboard':
        raise ValueError('keyboard-type')
    assign('keyboard_surface', pointer('meta_wayland_keyboard_get_focus_surface($onpc_keyboard)'))
    if typename('keyboard_surface') != 'MetaWaylandSurface':
        raise ValueError('surface-type')
    result['keyboard_focus_matches_fixture_surface'] = bool(read('$onpc_keyboard_surface == $onpc_fixture_surface'))
    assign('recipient_window', pointer('meta_wayland_surface_get_window($onpc_keyboard_surface)'))
    if not typename('recipient_window').startswith('MetaWindow'):
        raise ValueError('recipient-type')
    result['keyboard_recipient_matches_fixture'] = int(read('(int)meta_window_get_pid($onpc_recipient_window)')) == EXPECTED_PID
    # Seat header: 72-byte prefix, 112-byte data device (three selection
    # owners), 80-byte primary device. Validate all three seat backpointers
    # before interpreting the text-input focus; never read surrounding text.
    for offset in (72, 184):
        if not bool(read('*(void**)((char*)$onpc_seat + %d) == $onpc_seat' % offset)):
            raise ValueError('data-device-binding')
    assign('text_input', pointer('*(void**)((char*)$onpc_seat + 264)'))
    if not bool(read('*(void**)$onpc_text_input == $onpc_seat')):
        raise ValueError('text-input-binding')
    assign('text_focus', pointer('*(void**)((char*)$onpc_text_input + 8)'))
    if typename('text_focus') != 'MetaWaylandTextInputFocus':
        raise ValueError('text-focus-type')
    result['client_text_input_focused'] = bool(read('(int)clutter_input_focus_is_focused($onpc_text_focus)'))
    text_surface = read('*(void**)((char*)$onpc_text_input + 48)')
    result['client_text_input_has_surface'] = int(text_surface) != 0
    result['client_text_input_matches_fixture'] = bool(read('*(void**)((char*)$onpc_text_input + 48) == $onpc_fixture_surface'))
    if DO_RESYNC:
        if not all(result[key] for key in ('focus_is_unlock_dialog', 'grab_is_ui_group',
                'grab_contains_focus', 'keyboard_focus_matches_fixture_surface')):
            raise ValueError('resync-precondition')
        if result['client_text_input_focused'] or result['client_text_input_has_surface']:
            raise ValueError('resync-text-input-active')
        # Explicit engineering change: re-notify the existing grab property.
        # No grab, actor focus, key, password, unlock or relock operation.
        read('(void)g_object_notify($onpc_stage, "is-grabbed")')
        result['resync_applied'] = True
        result['after_keyboard_focus_is_null'] = int(read('(void*)meta_wayland_keyboard_get_focus_surface($onpc_keyboard)')) == 0
        result['after_grab_unchanged'] = bool(read('(void*)clutter_stage_get_grab_actor($onpc_stage) == $onpc_grab'))
        result['after_shell_focus_unchanged'] = bool(read('(void*)clutter_stage_get_key_focus($onpc_stage) == $onpc_focus'))
        result['after_client_text_input_focused'] = bool(read('(int)clutter_input_focus_is_focused($onpc_text_focus)'))
    result['available'] = True
    result.pop('last_query', None)
except (gdb.error, ValueError):
    result['reason'] = 'native-query-refused'
finally:
    gdb.execute('detach')
    print('ONPC_NATIVE ' + json.dumps(result, sort_keys=True))
'''.replace('EXPECTED_PID', str(fixture_pid)).replace('DO_RESYNC', repr(experiment == 'resync'))

command = ['/usr/bin/timeout', '--signal=TERM', '--kill-after=5s', '20s',
    '/usr/bin/gdb', '-nx', '-nh', '-batch', '-iex', 'set auto-load off',
    '-iex', 'set debuginfod enabled off', '-ex', 'set unwind-on-signal on',
    '-ex', 'handle SIGSEGV stop print nopass', '-p', str(shell_pid),
    '-ex', 'python exec(' + repr(native) + ')']
completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
assert completed.returncode == 0
records = [json.loads(line.removeprefix('ONPC_NATIVE '))
           for line in completed.stdout.splitlines() if line.startswith('ONPC_NATIVE ')]
assert len(records) == 1 and (shell / 'stat').read_text().split()[21] == start
assert locked_session() == before
print(json.dumps({'native_compositor_summary': records[0]}, sort_keys=True), flush=True)
