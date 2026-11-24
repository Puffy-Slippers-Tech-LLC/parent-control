"""Command-only lifecycle and policy checks for the supplied real launchers."""
import errno
import os
from pathlib import Path
import pwd
import re
import signal
import subprocess

from flatpak_launcher import LUNAR, fedora
from lunar_profile_guest import APPIMAGE_PATTERN, MINECRAFT, appimage_path


def command(argv, *, timeout=30):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            check=True, timeout=timeout)
    return result.stdout


def flatpak_running(app, account, require):
    raw = command(['/usr/bin/flatpak', 'ps', '--columns=instance,application,pid'])
    require(len(raw) <= 65536, 'launcher:inventory-bound')
    rows = [line.split('\t') for line in raw.decode().splitlines()]
    require(all(len(row) == 3 for row in rows), 'launcher:inventory')
    matches = [row for row in rows if row[1] == app]
    identity = None
    for instance, _, pid in matches:
        require(re.fullmatch(r'[0-9]+', instance) and re.fullmatch(r'[1-9][0-9]*', pid),
                'launcher:flatpak-identity')
        process = Path('/proc') / pid
        try:
            before = (process / 'stat').read_text().rpartition(') ')[2].split()
            require(process.stat().st_uid == account.pw_uid, 'launcher:owner')
            after = (process / 'stat').read_text().rpartition(') ')[2].split()
        except (FileNotFoundError, ProcessLookupError):
            # Flatpak can list an instance after its wrapper exits.
            continue
        require(before[19] == after[19], 'launcher:owner-changed')
        if before[0] in ('Z', 'X') or after[0] in ('Z', 'X'):
            continue
        if identity is not None:
            require(False, f'launcher:ambiguous-instance:{identity[0]}/{identity[1]},{instance}/{pid}')
        identity = [instance, int(pid), before[19]]
    if identity is not None:
        return {'launcher': 'flatpak', 'app': app, 'identity': identity}
    # Only an inventory with no matching rows establishes absence.
    require(not matches, 'ui:incomplete-tree')
    return None


def appimage_running(account, require):
    home = Path(account.pw_dir)
    bypass = '/opt/appimagelauncher.AppDir/usr/lib/x86_64-linux-gnu/appimagelauncher/binfmt-bypass'
    matches = []
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if process.stat().st_uid != account.pw_uid:
                continue
            try:
                executable = (process / 'exe').readlink()
            except PermissionError:
                # Non-dumpable unrelated session helpers are not candidates.
                continue
            if not (executable.parent.parent == Path('/tmp')
                    and executable.parent.name.startswith('.mount_Lunar ')
                    and executable.name == 'lunarclient'):
                continue
            before = (process / 'stat').read_text().rpartition(') ')[2].split()
            if before[0] == 'Z':
                continue
            parent = Path('/proc') / before[1]
            if (parent / 'exe').readlink() != Path(bypass):
                continue
            argv = (parent / 'cmdline').read_bytes().split(b'\0')
            original = Path(os.fsdecode(argv[1])) if len(argv) >= 3 else Path('/')
            require(parent.stat().st_uid == account.pw_uid
                    and original.parent == home / 'Applications'
                    and original.match(APPIMAGE_PATTERN)
                    and argv[:2] == [bypass.encode(), os.fsencode(original)]
                    and argv[2:] in ([b''], [b'--hidden', b''],
                        [b'--no-sandbox', b''], [b'--no-sandbox', b'--hidden', b'']),
                    'launcher:appimage-owner')
            parent_start = (parent / 'stat').read_text().rpartition(') ')[2].split()[19]
            require((process / 'stat').read_text().rpartition(') ')[2].split()[19] == before[19]
                    and (parent / 'stat').read_text().rpartition(') ')[2].split()[19] == parent_start,
                    'launcher:owner-changed')
            matches.append({'launcher': 'appimage', 'identity': [int(process.name), before[19],
                                                                int(before[1]), parent_start]})
        except (FileNotFoundError, ProcessLookupError):
            # A retired process cannot authorize a later stop. A launch wait
            # reacquires the complete inventory within its original deadline.
            continue
    # A vendor update can briefly hand off between two matching versions.
    # Reacquire the read; ambiguity never authorizes a stop or proves absence.
    require(len(matches) <= 1, 'ui:incomplete-tree')
    return matches[0] if matches else None


def validate_receipt(value, app, require):
    require(type(value) is dict and value.get('launcher') in ('flatpak', 'appimage'),
            'launcher:receipt')
    identity = value.get('identity')
    if value['launcher'] == 'flatpak':
        require(set(value) == {'launcher', 'app', 'identity'}
                and value['app'] == (LUNAR if app == 'lunar' else MINECRAFT)
                and type(identity) is list and len(identity) == 3
                and type(identity[0]) is str and re.fullmatch(r'[0-9]+', identity[0])
                and type(identity[1]) is int and identity[1] > 0
                and type(identity[2]) is str and re.fullmatch(r'[0-9]+', identity[2]),
                'launcher:flatpak-receipt')
    else:
        require(app == 'lunar' and set(value) == {'launcher', 'identity'}
                and type(identity) is list and len(identity) == 4
                and all(type(identity[index]) is int and identity[index] > 0 for index in (0, 2))
                and all(type(identity[index]) is str and re.fullmatch(r'[0-9]+', identity[index])
                        for index in (1, 3)), 'launcher:appimage-receipt')


def run(ui, operation, require, require_session):
    app, action = operation.split('-', 1)
    account = pwd.getpwnam('onpc-child-jordan')
    require(app in ('lunar', 'minecraft') and os.getuid() == os.geteuid() == account.pw_uid,
            'launcher:account')
    require_session(unlocked=True)
    require(not ui.input_uncertain, 'ui:uncertain-input')
    ui.timeout = 180
    flatpak = app == 'minecraft' or fedora()
    app_id, executable = ((MINECRAFT, 'minecraft') if app == 'minecraft'
                          else (LUNAR, 'lunarclient'))

    def observe():
        require_session(unlocked=True)
        return (flatpak_running(app_id, account, require) if flatpak
                else appimage_running(account, require))

    if action == 'observer-ready':
        return None
    if action in ('opened', 'snapshot', 'close-ready'):
        return ui.wait(observe, 'launcher-running', prompt_in_predicate=True)
    if action == 'closed':
        ui.wait(lambda: observe() is None, 'launcher-closed', prompt_in_predicate=True)
        return None
    if action in ('quit', 'stop'):
        current = ui.wait(observe, 'launcher-running', prompt_in_predicate=True)
        if flatpak:
            require(observe() == current, 'launcher:owner-changed')
            ui.input_uncertain = True
            command(['/usr/bin/flatpak', 'kill', current['identity'][0]])
        else:
            descriptor = os.pidfd_open(current['identity'][0])
            try:
                require(observe() == current, 'launcher:owner-changed')
                ui.input_uncertain = True
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
            finally:
                os.close(descriptor)
        ui.input_uncertain = False
        return current if action == 'stop' else None
    require(action in ('launch', 'command-blocked'), 'launcher:operation')
    ui.wait(lambda: observe() is None, 'launcher-before-launch', prompt_in_predicate=True)
    argv = (['/usr/bin/flatpak', 'run', '--branch=stable', '--arch=x86_64',
             '--command=' + executable, app_id] if flatpak else
            [str(appimage_path(Path(account.pw_dir))), '--no-sandbox'])
    blocked = action == 'command-blocked'
    if not flatpak:
        original = Path(argv[0])
        require(original.is_file() and not original.is_symlink()
                and original.stat().st_uid == account.pw_uid,
                'launcher:original-input')
    ui.input_uncertain = True
    if blocked and not flatpak:
        try:
            subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=15)
        except PermissionError as error:
            require(error.errno in (errno.EACCES, errno.EPERM), 'launcher:execution-denial')
            ui.input_uncertain = False
            return {'denial': 'permission-denied' if error.errno == errno.EACCES
                    else 'operation-not-permitted'}
        require(False, 'launcher:execution-denial')
    result = subprocess.run(['/usr/bin/systemd-run', '--user', '--quiet', '--collect',
        *(['--wait', '--pipe'] if blocked else []), '--service-type=exec', *argv],
        stdin=subprocess.DEVNULL, capture_output=True, check=not blocked, timeout=30)
    if blocked:
        denial = ('Running app/' + app_id + '/x86_64/stable is not allowed '
                  'by the policy set by your administrator').encode()
        require(result.returncode == 1 and len(result.stdout) + len(result.stderr) <= 65536
                and denial in result.stderr, 'launcher:execution-denial')
    ui.input_uncertain = False
    return {'denial': 'administrator-policy'} if blocked else None
