"""Read only the supplied Jordan launcher profile. Never install or repair it."""
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

from guest_files import directory, identity, read_regular
import session_control

APPIMAGE = 'Applications/Lunar Client-3.7.36-ow_62fe2fee4e3cba848dfd2426f875152f.AppImage'
APPIMAGE_SHA256 = 'cc190995a67db7f27eb438af62d0fb67288dee6b5c66a7b2bf9d4fd9888777e2'
INTEGRATED = 'appimagekit_349c057c5506142f859a39412c2722d9-Lunar_Client.desktop'
MINECRAFT = 'com.mojang.Minecraft'
MINECRAFT_COMMIT = 'ae896ae7bb78f075463a380d85694caad4f7d3adae8cdee7ad3dd2e3850d89a5'
# Essential launcher/Chromium inputs from the pinned bootstrap/core manifests
# https://redstone-launcher.mojang.com/release/v2/packages/af22922eacb22d1ad5017ef0fa30a8c471556790/manifest.json
# https://redstone-launcher.mojang.com/release/v2/packages/519febb9e10f895d024c62052b2ed21a8341a869/manifest.json
# No games, extensions or full locale/media inventory.
MINECRAFT_FILES = {
    'minecraft-launcher': ('724e2eb4ea55c07cd955f07537a06ce9512a5960', 3272968, 0o755),
    'liblauncher.so': ('34671083229495fe9ac656829a69d34642b1422a', 33837872, 0o644),
    'libcef.so': ('6fc6e59c8f67e52ab49aa6979e75376f8ccae1b1', 218760864, 0o755),
    'libEGL.so': ('4a4ff5fe557713f4d924ae9b3428822e069b19a8', 913288, 0o755),
    'libGLESv2.so': ('01ed939e9529dae5cd9de13459f2bdc1997767d5', 26950080, 0o755),
    'icudtl.dat': ('99f545bc396878c7a53e98a79017d9531af7c1f5', 10468208, 0o644),
    'resources.pak': ('4dfe88c0a36a205b48105eee834fa933b5bebe07', 8816122, 0o644),
    'chrome_100_percent.pak': ('8f463534b3b29f37fb802a940ba537bac271029f', 680941, 0o644),
    'chrome_200_percent.pak': ('40bc019888bb7dfb2bb230fc365adff789114691', 1064895, 0o644),
    'snapshot_blob.bin': ('3315cf6a79a2c6be1af63bec450bb35a3058cf3a', 317550, 0o755),
    'v8_context_snapshot.bin': ('6e235702cdf292ab3820d22e21a24a277f329c86', 671997, 0o755),
    'locales/en-US.pak': ('81e2ca4aee93e0b0103270f263eafc06397894db', 478405, 0o644),
}


def require(value, code):
    if not value:
        raise ValueError('lunar-profile:' + code)


def command(argv, *, code):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=120)
    require(result.returncode == 0 and len(result.stdout) <= 65536, code)
    return result.stdout.strip()


def verify(action, preparation):
    require(os.geteuid() == 0 and action == 'read', 'authority')
    child = pwd.getpwnam(session_control.ACCOUNTS['standard'])
    home = Path(child.pw_dir)
    require(child.pw_uid >= 1000 and child.pw_gid >= 1000, 'child-account')
    require(home == Path('/home') / child.pw_name, 'child-home')
    require(child.pw_uid not in {
        pwd.getpwnam(session_control.ACCOUNTS[role]).pw_uid
        for role in ('parent', 'second-parent', 'child')}, 'child-account')
    files = {}

    def read(relative, *, modes=(0o600, 0o644, 0o664), limit=65536):
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
        files[relative] = {'identity': identity(info), 'sha256': hashlib.sha256(content).hexdigest()}
        return content

    # The guarded transport already binds the restored VM/run; bind its baseline too.
    marker = json.loads(Path('/etc/oh-no-parent-control-test-baseline.json').read_text())
    require(marker['preparation_script_sha256'] == preparation, 'stale-baseline')
    appimage = read(APPIMAGE, modes=(0o700, 0o755, 0o775), limit=512 * 1024 * 1024)
    require(hashlib.sha256(appimage).hexdigest() == APPIMAGE_SHA256, 'original-appimage-digest')
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
        expected = [str(home / APPIMAGE), '--no-sandbox'] + (['--hidden'] if hidden else ['%U'])
        require(entry['Type'] == 'Application' and shlex.split(entry['Exec']) == expected
                and entry.get('TryExec') == str(home / APPIMAGE)
                and entry.get('Hidden', 'false') == 'false'
                and entry.get('X-GNOME-Autostart-enabled', 'true') == 'true'
                and entry.get('Terminal', 'false') == 'false', 'launcher-route')
        return entry

    integrated = desktop('.local/share/applications/' + INTEGRATED)
    require(integrated['X-AppImage-Version'] == '3.7.36-ow'
            and integrated['Icon'] == 'appimagekit_349c057c5506142f859a39412c2722d9_lunarclient',
            'integrated-version-icon')
    icon = str(home / '.local/share/icons/hicolor/512x512/apps/lunarclient.png')
    require(desktop('.local/share/applications/lunarclient.desktop')['Icon'] == icon
            and desktop('.config/autostart/lunarclient.desktop', hidden=True)['Icon'] == icon,
            'launcher-icon-route')
    for icon in ('1024x1024/apps/appimagekit_349c057c5506142f859a39412c2722d9_lunarclient.png',
                 '512x512/apps/lunarclient.png'):
        require(read('.local/share/icons/hicolor/' + icon, limit=1024 * 1024).startswith(
            b'\x89PNG\r\n\x1a\n'), 'launcher-icon')
    settings = json.loads(read('.lunarclient/settings/launcher.json'))['settings']
    require(settings['computerStartup'] == 'DOCKED' and settings['afterLaunchAction'] == 'HIDE',
            'autostart-tray-settings')

    info = lambda option, app=MINECRAFT: command(['/usr/bin/flatpak', 'info', '--system', option, app],
                                                code='minecraft-installed:' + app + ':' + option)
    require(info('--show-commit') == MINECRAFT_COMMIT
            and info('--show-ref') == 'app/com.mojang.Minecraft/x86_64/stable', 'minecraft-identity')
    metadata = configparser.ConfigParser(interpolation=None)
    metadata.read_string(info('--show-metadata'))
    require(metadata['Application']['runtime'] == 'org.freedesktop.Platform/x86_64/25.08'
            and metadata['Application']['command'] == 'minecraft', 'minecraft-runtime')
    runtime = info('--show-commit', 'org.freedesktop.Platform/x86_64/25.08')
    require(len(runtime) == 64 and all(c in '0123456789abcdef' for c in runtime), 'minecraft-runtime')
    desktop_path = Path('/var/lib/flatpak/exports/share/applications/com.mojang.Minecraft.desktop')
    deployment = Path(info('--show-location'))
    require(deployment == Path('/var/lib/flatpak/app/com.mojang.Minecraft/x86_64/stable')
            / MINECRAFT_COMMIT and desktop_path.resolve() == deployment
            / 'export/share/applications/com.mojang.Minecraft.desktop', 'minecraft-desktop-target')
    entry = configparser.ConfigParser(interpolation=None)
    entry.read_string(command(['/usr/bin/cat', str(desktop_path)], code='minecraft-desktop-route'))
    require(entry['Desktop Entry']['Type'] == 'Application'
            and shlex.split(entry['Desktop Entry']['Exec']) == ['/usr/bin/flatpak', 'run',
                '--branch=stable', '--arch=x86_64', '--command=minecraft', MINECRAFT]
            and entry['Desktop Entry'].get('Hidden', 'false') == 'false', 'minecraft-desktop-route')
    # Reject user-scope shadowing of the supplied system app/command route.
    for relative in ('.local/share/flatpak/app/' + MINECRAFT,
                     '.local/share/flatpak/overrides/global',
                     '.local/share/flatpak/overrides/' + MINECRAFT,
                     '.local/share/applications/' + MINECRAFT + '.desktop'):
        require(not os.path.lexists(home / relative), 'minecraft-user-shadow')
    launcher = '.var/app/com.mojang.Minecraft/.minecraft/launcher/'
    require(read(launcher + 'bootstrap.version').strip() == b'2.6.12'
            and read(launcher + '.version').strip() == b'3.43.21', 'minecraft-version')
    for name, (sha1, size, mode) in MINECRAFT_FILES.items():
        content = read(launcher + name, modes=(mode,), limit=size)
        require(len(content) == size and hashlib.sha1(content).hexdigest() == sha1,
                'minecraft-file-digest:' + name)
    return {'profile': 'lunar-manual', 'files': files,
            'appimagelauncher': package, 'minecraft_commit': MINECRAFT_COMMIT,
            'minecraft_runtime_commit': runtime, 'autostart': 'DOCKED', 'after_launch': 'HIDE',
            'targets': {'original_appimage': str(home / APPIMAGE),
                        'version_pattern': str(home / 'Applications/Lunar Client-*.AppImage'),
                        'integrated_launcher': INTEGRATED,
                        'minecraft_launcher': MINECRAFT + '.desktop'}}


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1], sys.argv[2]), sort_keys=True))
