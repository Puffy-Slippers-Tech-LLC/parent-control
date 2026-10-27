"""Launch identity and owned routing restoration for public desktop selection.

Observation never changes selection. Saved routing is separate cleanup data,
never evidence of current execution. A missing runtime selection or ambiguous
session is inconclusive, never an alternate-launch denial.
"""

import json
from pathlib import Path
import re
import sys


def require(value, code):
    if not value:
        raise RuntimeError('public-desktop:' + code)


def _remote(transport, lease, operation, *arguments):
    import watch_activity

    with watch_activity.operation('Reading or restoring owned desktop selection: ' + operation):
        lease.guard()
        raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B', '-I', '-',
            operation, *arguments], input=Path(__file__).read_bytes(), timeout=120)
        lease.guard()
    require(type(raw) is bytes and 0 < len(raw) <= 32768, 'response-bound')
    result = json.loads(raw)
    require(type(result) is dict and result.get('run') == lease.state['run'], 'response-run')
    return result


def capture_routing(transport, lease):
    """Capture original Jordan/station routing before any public chooser input."""
    return _remote(transport, lease, 'capture-routing')


def restore_routing(transport, lease, original, observed):
    """Restore after public attempts; observed maps bindings to their last observe result.

    Refuse changed UIDs, boots, runs or foreign routing. Unchanged originals are
    read back without writes. This does not reset GDM's ephemeral selection;
    the caller owns public Cancel/logout before fresh station entry.
    """
    return _remote(transport, lease, 'restore-routing',
                   json.dumps({'original': original, 'observed': observed}, separators=(',', ':')))


def observe(transport, lease, binding='standard'):
    """Observe Jordan or the station in the caller's current owned VM run.

    The 120-second stage returns selected desktop-file Exec separately from the
    running GNOME manager and compositor argv. It grants no desktop usability or
    confinement credit; the caller supplies the independent public UI result.
    """
    from fixture_credentials import ACCOUNTS

    require(binding in ('standard', 'station'), 'binding')
    account = ACCOUNTS['other-child'].username if binding == 'standard' else 'oh-no-parent-control'
    result = _remote(transport, lease, 'observe', binding, account)
    require(type(result) is dict and result.get('binding') == binding
            and result.get('run') == lease.state['run']
            and result.get('scope') == 'selected-launch-identity-only'
            and result.get('public_result_qualified') is False, 'response')
    return result


def guest_observe(binding, username):
    import os
    import pwd
    import shlex
    import shutil
    import stat
    import time

    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    from system_kiosk_confinement import process_identity, properties, user_command, user_unit
    from system_kiosk_admission import routing
    from gi.repository import GLib

    require(binding in ('standard', 'station') and username == {
        'standard': 'onpc-child-jordan', 'station': 'oh-no-parent-control'}[binding], 'account-binding')
    marker = guest.guard()
    account = pwd.getpwnam(username)
    require(account.pw_uid > 0, 'account-uid')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    saved_routing = routing(account.pw_uid)
    deadline = time.monotonic() + 105

    def sessions():
        names = ('User', 'Type', 'Class', 'Service', 'State', 'Seat', 'Active', 'Desktop')
        found = []
        for row in guest.run(['loginctl', 'list-sessions', '--no-legend', '--no-pager'], timeout=15).splitlines():
            fields = row.split()
            if len(fields) < 2 or fields[1] != str(account.pw_uid):
                continue
            require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', fields[0]), 'session-id')
            value = properties(guest.run(['loginctl', 'show-session', fields[0], '--no-pager',
                *['--property=' + name for name in names]], timeout=15), names)
            if (value['Class'] in ('manager', 'manager-early')
                    and value['Service'] == 'systemd-user' and value['Type'] == 'unspecified'):
                continue
            found.append((fields[0], value))
        require(len(found) <= 1, 'ambiguous-session')
        if not found:
            return None
        value = found[0][1]
        require(value['User'] == str(account.pw_uid) and value['Type'] == 'wayland'
                and value['Class'] == 'user' and value['State'] == 'active'
                and value['Seat'] == 'seat0' and value['Active'] == 'yes'
                and value['Service'] in ('gdm-password', 'gdm-autologin'), 'inactive-local-session')
        return found

    def units(pattern):
        raw = user_command(account, ['/usr/bin/systemctl', '--user', 'list-units',
            '--type=service', '--state=active', '--plain', '--no-legend', '--no-pager',
            pattern], timeout=15).decode()
        result = [row.split()[0] for row in raw.splitlines() if row.strip()]
        require(len(result) <= 8 and all(re.fullmatch(r'[A-Za-z0-9@_.\\:-]{1,200}', unit)
                for unit in result), 'service-list')
        return result

    def process(unit, expected_names):
        service = user_unit(account, unit)
        require(service['ActiveState'] == 'active' and service['MainPID'].isdecimal()
                and int(service['MainPID']) > 1
                and re.fullmatch(r'[0-9a-f]{32}', service['InvocationID'])
                and service['InvocationID'] != '0' * 32, 'service-identity')
        path = Path('/proc') / service['MainPID']
        identity = process_identity(path)
        executable = os.readlink(path / 'exe')
        argv = (path / 'cmdline').read_bytes()
        environment = (path / 'environ').read_bytes()
        require(len(argv) <= 16384 and len(environment) <= 1024 * 1024, 'process-bound')
        require(identity[2] == (str(account.pw_uid),) * 4
                and Path(executable).name in expected_names
                and Path(executable).stat().st_uid == 0
                and (path / 'cgroup').read_text().strip() == '0::' + service['ControlGroup'],
                'process-owner')
        env = dict(item.split(b'=', 1) for item in environment.split(b'\0') if b'=' in item)
        candidates = {env[key].decode() for key in (b'GDMSESSION', b'DESKTOP_SESSION')
                      if env.get(key)}
        if not candidates and before[0][1]['Desktop']:
            candidates.add(before[0][1]['Desktop'])
        require(len(candidates) == 1, 'runtime-desktop-id')
        selected = candidates.pop()
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', selected), 'runtime-desktop-id')
        args = [item.decode() for item in argv.rstrip(b'\0').split(b'\0')]
        require(process_identity(path) == identity, 'process-changed')
        public = {'unit': unit, 'pid': int(service['MainPID']), 'uid': account.pw_uid,
                  'starttime': identity[0], 'invocation_id': service['InvocationID'],
                  'executable': executable, 'argv': args, 'desktop_id': selected}
        return public, (service, identity, argv, environment)

    # Public passwordless selection can return while the session is starting.
    # Reacquire only these read-only readiness observations; never replay input.
    while True:
        before = sessions()
        if before:
            managers = units('gnome-session-manager@*.service')
            compositor_units = units('org.gnome.Shell@*.service') + units('org.gnome.Kiosk@*.service')
            require(len(managers) <= 1 and len(compositor_units) <= 1, 'ambiguous-session-services')
            if managers and compositor_units:
                break
        require(time.monotonic() < deadline, 'session-start-timeout')
        guest.guard()
        time.sleep(.25)
    require(len(managers) == 1, 'ambiguous-or-missing-manager')
    manager, manager_state = process(managers[0], {'gnome-session-service', 'gnome-session-binary'})
    require(len(compositor_units) == 1, 'ambiguous-or-missing-compositor')
    compositor, compositor_state = process(compositor_units[0], {'gnome-shell', 'gnome-kiosk'})
    selected = manager['desktop_id']
    require(compositor['desktop_id'] == selected, 'desktop-selection-mismatch')
    arguments = manager['argv']
    require(manager['unit'] == 'gnome-session-manager@' + selected + '.service'
            and ('--session=' + selected in arguments or any(
                arguments[index:index + 2] == ['--session', selected]
                for index in range(len(arguments) - 1))), 'selected-manager-command')
    desktop = Path('/usr/share/wayland-sessions') / (selected + '.desktop')
    info = desktop.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022
            and info.st_size <= 65536, 'desktop-file')
    contents = desktop.read_bytes()
    file_identity = (info.st_dev, info.st_ino, info.st_mode, info.st_uid,
                     info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    keyfile = GLib.KeyFile.new()
    keyfile.load_from_data(contents.decode(), len(contents), GLib.KeyFileFlags.NONE)
    command = keyfile.get_string('Desktop Entry', 'Exec')
    argv = shlex.split(command)
    require(argv and len(command) <= 8192 and not any('%' in arg for arg in argv), 'desktop-exec')
    executable = shutil.which(argv[0], path='/usr/bin:/bin:/usr/sbin:/sbin')
    require(executable is not None and Path(executable).stat().st_uid == 0, 'desktop-executable')
    # A desktop-file launcher and its wrapper are not the running manager argv.
    resolved = {'id': selected, 'file': str(desktop), 'exec': command,
                'argv': argv, 'executable': str(Path(executable).resolve())}
    current = desktop.lstat()
    require(process(managers[0], {'gnome-session-service', 'gnome-session-binary'}) == (manager, manager_state)
            and process(compositor_units[0], {'gnome-shell', 'gnome-kiosk'}) == (compositor, compositor_state)
            and sessions() == before and pwd.getpwnam(username) == account
            and routing(account.pw_uid) == saved_routing
            and (current.st_dev, current.st_ino, current.st_mode, current.st_uid,
                 current.st_gid, current.st_size, current.st_mtime_ns, current.st_ctime_ns)
            == file_identity and desktop.read_bytes() == contents
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
            and guest.guard() == marker, 'observation-changed')
    return {'scope': 'selected-launch-identity-only', 'public_result_qualified': False,
            'run': marker['run'], 'boot': boot, 'binding': binding, 'uid': account.pw_uid,
            'saved_routing': list(saved_routing),
            'session': {'id': before[0][0], **{key.lower(): value for key, value in before[0][1].items()}},
            'selected_desktop': resolved, 'manager': manager, 'compositor': compositor}


def guest_routing(request=None):
    import pwd

    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    from system_kiosk_admission import USERS, routing, set_routing

    marker = guest.guard()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    accounts = {'standard': pwd.getpwnam(USERS['other']), 'station': pwd.getpwnam(USERS['kiosk'])}
    current = {'run': marker['run'], 'boot': boot, 'accounts': {
        binding: {'uid': account.pw_uid, 'routing': list(routing(account.pw_uid))}
        for binding, account in accounts.items()}}
    require(all(value['uid'] > 0 and len(value['routing']) == 2 and all(
        type(item) is str and re.fullmatch(r'[A-Za-z0-9_-]{0,64}', item)
        for item in value['routing']) for value in current['accounts'].values()), 'routing-values')
    if request is None:
        return current
    require(type(request) is dict and set(request) == {'original', 'observed'}, 'routing-request')
    original, observed = request['original'], request['observed']
    require(type(original) is dict and set(original) == {'run', 'boot', 'accounts'}
            and original['run'] == marker['run'] and original['boot'] == boot
            and type(original['accounts']) is dict and set(original['accounts']) == set(accounts)
            and type(observed) is dict and set(observed) <= set(accounts), 'routing-owner')
    # Validate both accounts before the first write; an unobserved binding must
    # still have its original routing. Only the selected launch owns a change.
    for binding in accounts:
        initial = original['accounts'][binding]
        require(type(initial) is dict and set(initial) == {'uid', 'routing'}
                and initial['uid'] == current['accounts'][binding]['uid']
                and type(initial['routing']) is list and len(initial['routing']) == 2
                and all(type(item) is str and re.fullmatch(r'[A-Za-z0-9_-]{0,64}', item)
                        for item in initial['routing']), 'routing-original')
        expected = initial['routing']
        if binding in observed:
            witness = observed[binding]
            require(type(witness) is dict and witness.get('run') == marker['run']
                    and witness.get('boot') == boot and witness.get('binding') == binding
                    and witness.get('uid') == initial['uid']
                    and witness.get('scope') == 'selected-launch-identity-only', 'routing-witness')
            expected = witness['saved_routing']
            # GDM can save Session while leaving SessionType unchanged (empty
            # on the ordinary fixture). Runtime Wayland is independent evidence,
            # not a promise that both saved fields were rewritten together.
            require(expected == initial['routing'] or (
                type(expected) is list and len(expected) == 2
                and expected[0] == witness['selected_desktop']['id']
                and expected[1] in (initial['routing'][1], witness['session']['type'])),
                'routing-unowned-selection')
        require(current['accounts'][binding]['routing'] == expected, 'routing-foreign-change')
    changed = []
    for binding, account in accounts.items():
        require(pwd.getpwnam(account.pw_name) == account
                and list(routing(account.pw_uid)) == current['accounts'][binding]['routing'],
                'routing-changed')
        wanted = original['accounts'][binding]['routing']
        if current['accounts'][binding]['routing'] != wanted:
            set_routing(account.pw_uid, tuple(wanted))
            changed.append(binding)
        require(list(routing(account.pw_uid)) == wanted, 'routing-restoration-readback')
    require(guest.guard() == marker and
            Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot, 'routing-run-changed')
    return {'run': marker['run'], 'boot': boot, 'restored': True, 'changed': changed}


if __name__ == '__main__':
    try:
        require(2 <= len(sys.argv) <= 4, 'arguments')
        if sys.argv[1] == 'observe':
            require(len(sys.argv) == 4, 'arguments')
            result = guest_observe(sys.argv[2], sys.argv[3])
        elif sys.argv[1] == 'capture-routing':
            require(len(sys.argv) == 2, 'arguments')
            result = guest_routing()
        else:
            require(sys.argv[1] == 'restore-routing' and len(sys.argv) == 3
                    and len(sys.argv[2]) <= 32768, 'arguments')
            result = guest_routing(json.loads(sys.argv[2]))
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        code = str(error) if type(error) is RuntimeError and str(error).startswith(
            'public-desktop:') else 'public-desktop:observation-inconclusive'
        if code == 'public-desktop:observation-inconclusive':
            import traceback
            location = traceback.extract_tb(error.__traceback__)[-1]
            code += ':' + type(error).__name__ + ':' + location.name + ':' + str(location.lineno)
        print(code, file=sys.stderr)
        sys.exit(1)
