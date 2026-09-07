#!/usr/bin/python3
"""Real APT/dpkg notice lifecycle in private chroots; no host package changes."""

import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

from owned_commands import Commands, require


ROOT = Path(__file__).resolve().parents[2]
SUCCESS = "PASS: Oh No! Parent Control package configuration completed successfully."
INSTALL_NOTICE = "*** REBOOT REQUIRED: reboot before using the kiosk session. ***"
REMOVE_NOTICE = "*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***"
HOOK = "etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice"


def write(root, name, content, mode=0o644):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)
    return path


def copy_binary(root, path, commands):
    source = Path(path)
    require(source.is_file(), 'package-notice:missing-prerequisite:' + source.name)
    target = root / source.relative_to('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    # Only trusted distribution binaries are inspected. ldd lists their
    # transitive runtime libraries; static binaries need no copies.
    output = commands.run(['ldd', str(source)], check=False).decode()
    if commands.last_returncode:
        require('not a dynamic executable' in output or 'statically linked' in output,
                'package-notice:library-discovery-failed')
    for match in re.finditer(r'(/[^\s()]+)', output):
        library = Path(match.group(1))
        target = root / library.relative_to('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library, target)


def prepare(directory, commands):
    root = directory / 'root'
    root.mkdir()
    for binary in (
        '/bin/sh', '/usr/bin/env', '/usr/bin/apt', '/usr/bin/apt-get',
        '/usr/bin/dpkg', '/usr/bin/dpkg-deb', '/usr/bin/dpkg-query', '/usr/bin/dpkg-split',
        '/usr/bin/dpkg-trigger', '/usr/bin/cat', '/usr/bin/chmod',
        '/usr/bin/install', '/usr/bin/rm', '/usr/bin/touch', '/usr/bin/grep',
        '/usr/bin/diff',
        '/usr/bin/tar', '/usr/bin/gzip', '/usr/sbin/ldconfig',
        '/usr/sbin/start-stop-daemon', '/usr/lib/apt/methods/file',
        '/usr/lib/apt/methods/copy',
    ):
        copy_binary(root, binary, commands)
    shutil.copytree('/usr/share/dpkg', root / 'usr/share/dpkg', dirs_exist_ok=True)
    for path in ('dev', 'run', 'tmp', 'etc/apt/apt.conf.d', 'etc/apt/preferences.d',
                 'etc/dpkg/dpkg.cfg.d',
                 'var/lib/apt/lists/partial', 'var/cache/apt/archives/partial',
                 'var/log/apt', 'fixtures'):
        (root / path).mkdir(parents=True, exist_ok=True)
    os.mknod(root / 'dev/null', stat.S_IFCHR | 0o666, os.makedev(1, 3))
    write(root, 'var/lib/dpkg/status', '')
    write(root, 'etc/apt/sources.list', '')
    write(root, 'etc/passwd', 'root:x:0:0:root:/root:/bin/sh\n')
    write(root, 'etc/group', 'root:x:0:\n')
    write(root, 'apt.conf', 'APT::Sandbox::User "root";\nAPT::Color "false";\n'
          'DPkg::Use-Pty "false";\n')

    for package in ('onpc-notice-trigger', 'oh-no-parent-control'):
        stage = directory / package
        write(stage, 'DEBIAN/control',
              f'Package: {package}\nVersion: 1.0\nArchitecture: all\n'
              'Maintainer: Test <test@example.invalid>\nDescription: Notice fixture\n'
              + ('Depends: onpc-notice-trigger\n' if package == 'oh-no-parent-control' else ''))
        (stage / 'DEBIAN').chmod(0o755)
        if package == 'onpc-notice-trigger':
            write(stage, 'DEBIAN/triggers', 'interest-noawait onpc-notice-trigger\n')
            write(stage, 'DEBIAN/postinst', '#!/bin/sh\nset -e\n'
                  'if [ "$1" = triggered ]; then\n'
                  '    echo "Fixture trigger processing completed"\n'
                  '    test ! -e /fail-trigger\nfi\n', 0o755)
        else:
            # Execute the exact production bootstrap, excluding unrelated
            # kiosk/PAM/service setup. The rest of this fixture only supplies
            # the normal reboot/completion events and a real dpkg trigger.
            bootstrap = (ROOT / 'debian/preinst').read_text().split(
                '\nif [ "$1" = install ]', 1)[0]
            write(stage, 'DEBIAN/preinst', bootstrap + '\nprepare_package_notice\n', 0o755)
            write(stage, 'DEBIAN/postinst', '#!/bin/sh\nset -e\n'
                  'if [ "$1" = configure ]; then\n'
                  '    printf "%s\\n" oh-no-parent-control > /run/reboot-required.pkgs\n'
                  '    dpkg-trigger --no-await onpc-notice-trigger\n'
                  '    /usr/libexec/oh-no-parent-control-package-notice --configured\nfi\n', 0o755)
            cleanup = (ROOT / 'debian/postrm').read_text().split('\ncheck_tree() {', 1)[0]
            write(stage, 'DEBIAN/postrm', cleanup + '\nif [ "$1" = remove ]; then\n'
                  '    printf "%s\\n" oh-no-parent-control > /run/reboot-required.pkgs\nfi\n', 0o755)
            write(stage, 'usr/libexec/oh-no-parent-control-package-notice',
                  (ROOT / 'tools/package_notice').read_text(), 0o755)
            write(stage, 'etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice',
                  (ROOT / 'data/apt/99zz-oh-no-parent-control-reboot-notice').read_text())
            write(stage, 'DEBIAN/conffiles',
                  '/etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice\n')
        commands.run(['dpkg-deb', '--build', '--root-owner-group', str(stage),
                      str(root / 'fixtures' / (package + '.deb'))])
    return root


def apt(root, commands, frontend, *arguments, success=True):
    output = commands.run(
        ['chroot', str(root), '/usr/bin/env', '-i',
         'PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL=C', 'APT_CONFIG=/apt.conf',
         'DEBIAN_FRONTEND=noninteractive', frontend, '-y', *arguments],
        check=False, timeout=45,
    ).decode()
    require((commands.last_returncode == 0) == success, 'package-notice:apt-result')
    return output


def check_install(output):
    require('Fixture trigger processing completed' in output, 'package-notice:missing-trigger')
    require(output.splitlines()[-2:] == [f'\033[1;32m{SUCCESS}\033[0m', INSTALL_NOTICE],
            'package-notice:incorrect-install-tail')
    require(output.count(SUCCESS) == output.count(INSTALL_NOTICE) == 1,
            'package-notice:duplicate-notice')


def main():
    require(len(sys.argv) == 1, 'package-notice:invalid-arguments')
    require(os.geteuid() == os.getegid() == 0, 'package-notice:root-required')
    require(Path.cwd() == ROOT, 'package-notice:checkout')
    os.umask(0o077)
    # /tmp is commonly nodev; a real chroot needs a working /dev/null.
    # /var/tmp/onpc-* is also a documented private test-artifact root.
    directory = Path(tempfile.mkdtemp(prefix='onpc-package-notice-', dir='/var/tmp'))
    commands = Commands()
    commands.directory = directory
    result = {'outcome': 'failed', 'evidence_directory': str(directory), 'checks': []}
    try:
        for frontend in ('apt', 'apt-get'):
            case = directory / frontend
            case.mkdir()
            root = prepare(case, commands)
            require(not (root / HOOK).exists(), 'package-notice:hook-preinstalled')
            deb = '/fixtures/oh-no-parent-control.deb'
            check_install(apt(root, commands, frontend, 'install', deb,
                              '/fixtures/onpc-notice-trigger.deb'))
            result['checks'].append(frontend + ':first-install')
            check_install(apt(root, commands, frontend, '--reinstall', 'install', deb))
            result['checks'].append(frontend + ':reinstall')
            output = apt(root, commands, frontend, 'remove', 'oh-no-parent-control')
            require(output.rstrip().endswith(REMOVE_NOTICE), 'package-notice:incorrect-remove-tail')
            require(not (root / HOOK).exists(), 'package-notice:hook-not-removed')
            result['checks'].append(frontend + ':remove')
            check_install(apt(root, commands, frontend, 'install', deb))
            result['checks'].append(frontend + ':install-after-remove')
            write(root, 'fail-trigger', '')
            output = apt(root, commands, frontend, '--reinstall', 'install', deb, success=False)
            require(SUCCESS not in output and INSTALL_NOTICE not in output,
                    'package-notice:false-success')
            result['checks'].append(frontend + ':failed-trigger')
        result['outcome'] = 'passed'
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
