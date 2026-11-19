"""Verify supplied launchers; Fedora's attempt owns its standard autostart entry."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import stat
import subprocess
import sys

from guest_files import directory, identity, read_regular, write_exclusive
import flatpak_launcher
import session_control

APPIMAGE_PATTERN = 'Lunar Client-*.AppImage'
MINECRAFT = 'com.mojang.Minecraft'


def require(value, code):
    if not value:
        raise ValueError('lunar-profile:' + code)


def command(argv, *, code):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=120)
    require(result.returncode == 0 and len(result.stdout) <= 65536, code)
    return result.stdout.strip()


def appimage_path(home):
    """Follow the supplied stable desktop alias, within its version wildcard."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string((home / '.local/share/applications/lunarclient.desktop').read_text())
    path = Path(parser['Desktop Entry']['TryExec'])
    require(path.parent == home / 'Applications' and path.match(APPIMAGE_PATTERN)
            and path.is_file() and not path.is_symlink(), 'appimage-route')
    return path


def prepare_integration(child, home, read, original=None):
    """Shared optional AppImageLauncher setup, independent of the OS."""
    cli = Path('/usr/bin/ail-cli')
    if not cli.exists():
        require(original is None, 'desktop-integration-tool')
        return
    require(cli.resolve().is_file() and cli.resolve().stat().st_uid == 0
            and not cli.resolve().stat().st_mode & 0o022, 'desktop-integration-tool')
    require(not any(session.get('User') == str(child.pw_uid)
                    for session in session_control.sessions().values()), 'integration-active-child')
    # The public CLI is idempotent. A missing first-run configuration otherwise
    # opens a dialog even for an integrated image. Snapshot cleanup owns this
    # finite default; existing user preferences remain in place.
    with directory(home / '.config', child, private_group=True) as (fd, guard):
        if not os.path.lexists(home / '.config/appimagelauncher.cfg'):
            write_exclusive(fd, 'appimagelauncher.cfg',
                b'[AppImageLauncher]\nask_to_move=false\n', owner=child.pw_uid,
                group=child.pw_gid, mode=0o600)
        guard()
    # This setup-only input must be readable and owned, but it does not describe
    # either launcher and is outside the read-only profile receipt.
    read('.config/appimagelauncher.cfg', record=False)
    if original is not None:
        command(['/usr/sbin/runuser', '-u', child.pw_name, '--', str(cli),
                 'integrate', str(original)], code='desktop-integration')
        require(appimage_path(home) == original, 'integration-route-changed')


def verify(action, preparation):
    require(os.geteuid() == 0 and action in ('read', 'prepare'), 'authority')
    child = pwd.getpwnam(session_control.ACCOUNTS['standard'])
    home = Path(child.pw_dir)
    require(child.pw_uid >= 1000 and child.pw_gid >= 1000, 'child-account')
    require(home == Path('/home') / child.pw_name, 'child-home')
    require(child.pw_uid not in {
        pwd.getpwnam(session_control.ACCOUNTS[role]).pw_uid
        for role in ('parent', 'second-parent', 'child')}, 'child-account')
    files = {}

    def read(relative, *, modes=(0o600, 0o644, 0o664), limit=65536, record=True):
        path = home / relative
        try:
            with directory(path.parent, child, private_group=True) as (fd, guard):
                before = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                mode = stat.S_IMODE(before.st_mode)
                require(mode in modes and before.st_gid == child.pw_gid, 'file-metadata')
                content, info = read_regular(fd, path.name, owner=child.pw_uid,
                                             mode=mode, limit=limit)
                guard()
        except (OSError, ValueError):
            # The finite relative input identifies the gap without exposing file contents.
            raise ValueError('lunar-profile:required-input:' + relative) from None
        if record:
            files[relative] = {'identity': identity(info), 'sha256': hashlib.sha256(content).hexdigest()}
        return content

    # The guarded transport already binds the restored VM/run; bind its baseline too.
    marker = json.loads(Path('/etc/oh-no-parent-control-test-baseline.json').read_text())
    require(marker['preparation_script_sha256'] == preparation, 'stale-baseline')
    fedora = flatpak_launcher.fedora()
    original = None if fedora else appimage_path(home)
    if action == 'prepare':
        prepare_integration(child, home, read, original)
    minecraft_commit = verify_flatpak(MINECRAFT, 'minecraft', home)
    if fedora:
        return verify_fedora(action, child, home, read, files, minecraft_commit)
    appimage = read(str(original.relative_to(home)), modes=(0o700, 0o755, 0o775),
                    limit=512 * 1024 * 1024)
    require(appimage[:4] == b'\x7fELF' and appimage[8:11] == b'AI\x02', 'appimage-format')
    del appimage
    package = command(['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', 'appimagelauncher'],
                      code='appimagelauncher-package')
    require(package == '3.0.0-beta-2-gha287~96cb937', 'appimagelauncher-version')
    require(command(['/usr/bin/dpkg', '--verify', 'appimagelauncher'],
                    code='appimagelauncher-integrity') == '',
            'appimagelauncher-integrity')
    interpreter = Path('/opt/appimagelauncher.AppDir/usr/lib/x86_64-linux-gnu/'
                       'appimagelauncher/binfmt-interpreter')
    for path in (Path('/usr/bin/AppImageLauncher'), interpreter):
        require(path.resolve() == path and path.is_file() and path.stat().st_uid == 0
                and not path.stat().st_mode & 0o022 and os.access(path, os.X_OK),
                'appimagelauncher-interpreter')
    require(Path('/usr/lib/binfmt.d/appimagelauncher.conf').resolve() == Path(
        '/opt/appimagelauncher.AppDir/usr/lib/binfmt.d/appimagelauncher.conf'),
        'appimagelauncher-packaged-link')
    binfmt = command(['/usr/bin/cat', '/proc/sys/fs/binfmt_misc/appimage-type2'],
                     code='appimagelauncher-binfmt').splitlines()
    require('enabled' in binfmt and 'magic 414902' in binfmt and any(
        line.startswith('interpreter ') and Path(line.removeprefix('interpreter ')) == interpreter
        for line in binfmt), 'appimagelauncher-binfmt')

    def desktop(relative, hidden=False):
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.read_string(read(relative, modes=(0o600, 0o644, 0o664, 0o700, 0o755, 0o775)).decode())
        entry = parser['Desktop Entry']
        expected = [str(original), '--no-sandbox'] + (['--hidden'] if hidden else ['%U'])
        require(entry['Type'] == 'Application' and shlex.split(entry['Exec']) == expected
                and entry.get('TryExec') == str(original)
                and entry.get('Hidden', 'false') == 'false'
                and entry.get('X-GNOME-Autostart-enabled', 'true') == 'true'
                and entry.get('Terminal', 'false') == 'false', 'launcher-route')
        return entry

    integrated = (home / '.local/share/applications').glob('appimagekit_*-Lunar_Client.desktop')
    matching = []
    for path in integrated:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(read(str(path.relative_to(home)),
            modes=(0o600, 0o644, 0o664, 0o700, 0o755, 0o775)).decode())
        if parser['Desktop Entry'].get('TryExec') == str(original):
            matching.append(path)
    require(len(matching) == 1, 'integrated-launcher')
    integrated_name = matching[0].name
    desktop('.local/share/applications/' + integrated_name)
    desktop('.local/share/applications/lunarclient.desktop')
    desktop('.config/autostart/lunarclient.desktop', hidden=True)
    return {'profile': 'lunar-manual', 'files': files,
            'appimagelauncher': package, 'minecraft_commit': minecraft_commit,
            'autostart': 'desktop-login',
            'targets': {'original_appimage': str(original),
                        'version_pattern': str(home / 'Applications/Lunar Client-*.AppImage'),
                        'integrated_launcher': integrated_name,
                        'minecraft_launcher': MINECRAFT + '.desktop'}}


def verify_flatpak(app, executable, home):
    """Verify the current system deployment and its normal exported command."""
    info = lambda option: command(['/usr/bin/flatpak', 'info', '--system', option, app],
                                  code='flatpak-input:' + app + ':' + option)
    commit = info('--show-commit')
    require(len(commit) == 64 and all(c in '0123456789abcdef' for c in commit)
            and info('--show-ref') == 'app/' + app + '/x86_64/stable', 'flatpak-identity')
    metadata = configparser.ConfigParser(interpolation=None)
    metadata.read_string(info('--show-metadata'))
    require(metadata['Application']['command'] == executable, 'flatpak-command')
    deployment = Path('/var/lib/flatpak/app') / app / 'x86_64/stable' / commit
    desktop = Path('/var/lib/flatpak/exports/share/applications') / (app + '.desktop')
    require(info('--show-location') == str(deployment) and desktop.resolve() ==
            deployment / 'export/share/applications' / (app + '.desktop'), 'flatpak-export')
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(desktop.read_text())
    entry = parser['Desktop Entry']
    require(entry['Type'] == 'Application' and entry['X-Flatpak'] == app
            and entry.get('Hidden', 'false') == 'false'
            and shlex.split(entry['Exec']) == ['/usr/bin/flatpak', 'run', '--branch=stable',
                '--arch=x86_64', '--command=' + executable, app], 'flatpak-launcher')
    for relative in ('.local/share/flatpak/app/' + app,
                     '.local/share/flatpak/overrides/global',
                     '.local/share/flatpak/overrides/' + app,
                     '.local/share/applications/' + app + '.desktop'):
        require(not os.path.lexists(home / relative), 'flatpak-user-shadow')
    return commit


def verify_fedora(action, child, home, read, files, minecraft_commit):
    """Verify supplied system Flatpaks; the attempt owns only its autostart entry."""
    lunar_commit = verify_flatpak(flatpak_launcher.LUNAR, 'lunarclient', home)
    name = 'onpc-test-lunar-flatpak.desktop'
    content = ('[Desktop Entry]\nType=Application\nName=Lunar Client\n'
               'Exec=/usr/bin/flatpak run --branch=stable --arch=x86_64 '
               '--command=lunarclient ' + flatpak_launcher.LUNAR + '\n'
               'X-GNOME-Autostart-enabled=true\n').encode()
    if action == 'prepare':
        require(not any(session.get('User') == str(child.pw_uid)
                        for session in session_control.sessions().values()), 'autostart-active-child')
        with directory(home / '.config/autostart', child, private_group=True) as (fd, guard):
            if not os.path.lexists(home / '.config/autostart' / name):
                write_exclusive(fd, name, content, owner=child.pw_uid,
                                group=child.pw_gid, mode=0o600)
            guard()
    require(read('.config/autostart/' + name, modes=(0o600,)) == content, 'flatpak-autostart')
    lunar_id = 'parent-app-' + hashlib.sha256(
        (flatpak_launcher.LUNAR + '.desktop').encode()).hexdigest()[:16]
    return {'profile': 'lunar-flatpak', 'files': files, 'autostart': 'flatpak-login',
            'lunar_commit': lunar_commit, 'minecraft_commit': minecraft_commit,
            'targets': {'lunar_policy_app': lunar_id,
                        'lunar_launcher': flatpak_launcher.LUNAR + '.desktop',
                        'minecraft_launcher': MINECRAFT + '.desktop'}}


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1], sys.argv[2]), sort_keys=True))
