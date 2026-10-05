"""Inline the shared lifecycle into distribution scripts at package build time.

Pre-install and post-removal scripts must work without an installed Python
helper or a checkout. Debian's generated debhelper body stays at its original
boundary; RPM embeds the same standalone shell in its scriptlets.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PHASES = ('preinst', 'postinst', 'prerm', 'postrm')
TOKEN = re.compile(r'@([a-z_]+)@')
SCALARS = frozenset(('gdm_presession_dir', 'service_command', 'bus_reload',
                     'delete_account', 'admin_group'))


def fragments(root: Path, distribution: str) -> dict[str, str]:
    if distribution not in ('ubuntu', 'fedora'):
        raise ValueError('unsupported packaging distribution')
    content = (root / 'packaging' / f'{distribution}.inc').read_text()
    parts = re.split(r'^# @([a-z_]+)@\n', content, flags=re.MULTILINE)
    if parts[0].strip() or len(parts) % 2 != 1:
        raise ValueError('invalid distro fragment file')
    values = {}
    for name, value in zip(parts[1::2], parts[2::2]):
        if name in values:
            raise ValueError(f'duplicate distro fragment: {name}')
        values[name] = value.rstrip('\n')
    for name, action in (('execution_policy_flags', 'flags'),
                         ('execution_policy_restore_classification', 'restore-stock'),
                         ('execution_policy_cleanup', 'cleanup')):
        if distribution == 'fedora':
            script = embedded_fedora_policy(root, action)
            if action == 'restore-stock':
                script = 'original_stock_policy=$(\n' + script + '\n)'
            values[name] = script
        else:
            values[name] = ''
    if distribution == 'ubuntu':
        for name in ('execution_policy_install', 'execution_policy_check_remove',
                     'execution_policy_remove_rule'):
            values[name] = ''
    return values


def embedded_fedora_policy(root: Path, action: str) -> str:
    """Scriptlets must survive an absent or already erased product payload."""
    source = (root / 'packaging/fedora_execution_policy.py').read_text()
    return f"/usr/bin/python3 -B - {action} <<'ONPC_FEDORA_EXECUTION_POLICY'\n{source}\nONPC_FEDORA_EXECUTION_POLICY"


def embedded_purge_phase(root: Path) -> str:
    source = (root / 'packaging/purge.py').read_text().split("if __name__ == '__main__':", 1)[0]
    return ("onpc_remove_phase=$(\n/usr/bin/python3 -B - <<'ONPC_NATIVE_PURGE_INTENT'\n" +
            source + "\ntry:\n    print(rpm_removal_phase())\nexcept (OSError, ValueError, subprocess.CalledProcessError) as error:\n    print(f'purge: {error}', file=sys.stderr)\n    sys.exit(1)\nONPC_NATIVE_PURGE_INTENT\n)\n" +
            'case "$onpc_remove_phase" in remove|purge) set -- "$onpc_remove_phase" ;; *) exit 1 ;; esac\n')


def render(root: Path, distribution: str, phase: str) -> str:
    if phase not in PHASES:
        raise ValueError('unsupported lifecycle phase')
    source = (root / 'packaging/lifecycle' / f'{phase}.in').read_text()
    values = fragments(root, distribution)

    def substitute(match):
        value = values[match.group(1)]
        # Block slots can be immediately followed by the next command, while
        # scalar slots (paths, group, command) remain on the same line.
        if match.group(1) not in SCALARS and source[match.end():match.end() + 1] != '\n':
            value += '\n'
        return value

    return TOKEN.sub(substitute, source)


def expand_debian(root: Path, staging: Path) -> None:
    for phase in PHASES:
        target = staging / 'DEBIAN' / phase
        source = target.read_text()
        before, after = render(root, 'ubuntu', phase).split('#DEBHELPER#', 1)
        for marker, value in (('#ONPC-LIFECYCLE-BEFORE#', before),
                              ('#ONPC-LIFECYCLE-AFTER#', after)):
            if source.count(marker) != 1:
                raise ValueError(f'missing lifecycle slot in {target}')
            source = source.replace(marker, value)
        target.write_text(source)


def rpm_scripts(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    scripts = {}
    for phase in PHASES:
        scripts[phase] = render(root, 'fedora', phase).replace('#DEBHELPER#', '')
        (output / phase).write_text(scripts[phase])
    prefixes = {
        'pre': ('preinst', 'if [ "$1" -gt 1 ]; then set -- upgrade previous; else set -- install; fi\n'),
        'posttrans': ('postinst', 'set -- configure\n'),
        'preun': ('prerm', '''if [ "$1" -ne 0 ]; then exit 0; fi
set -- remove
# RPM has no abort-remove callback. Restore derived state on preun failure.
trap 'status=$?; if [ "$status" -ne 0 ]; then /bin/sh /usr/share/oh-no-parent-control/lifecycle/postinst abort-remove || true; fi; exit "$status"' 0
'''),
        'postun': ('postrm', 'if [ "$1" -ne 0 ]; then exit 0; fi\nonpc_rpm_final_erase=1\n' + embedded_purge_phase(root)),
    }
    for name, (phase, prefix) in prefixes.items():
        # RPM expands macros even in scriptlets supplied through -f. These
        # files are literal shell/Python, including runtime RPM/DNF query
        # formats such as %{NAME}; none of their percent signs are spec macros.
        # Installed standalone lifecycle scripts above do not pass through RPM.
        source = '#!/bin/sh\nset -e\n' + prefix + scripts[phase]
        (output / f'rpm-{name}').write_text(source.replace('%', '%%'))
    source = '#!/bin/sh\nset -e\n' + embedded_fedora_policy(root, 'capture') + '\n'
    (output / 'rpm-pretrans').write_text(source.replace('%', '%%'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    debian = commands.add_parser('debian')
    debian.add_argument('--staging', type=Path, required=True)
    rpm = commands.add_parser('rpm')
    rpm.add_argument('--output', type=Path, required=True)
    standalone = commands.add_parser('standalone')
    standalone.add_argument('--distribution', choices=('ubuntu', 'fedora'), required=True)
    standalone.add_argument('--phase', choices=PHASES, required=True)
    standalone.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == 'debian':
        expand_debian(ROOT, arguments.staging)
    elif arguments.command == 'rpm':
        rpm_scripts(ROOT, arguments.output)
    else:
        arguments.output.write_text(render(ROOT, arguments.distribution, arguments.phase).replace('#DEBHELPER#', ''))


if __name__ == '__main__':
    main()
