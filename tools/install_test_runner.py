#!/usr/bin/python3
"""Install the development test dispatcher, bound to this checkout."""

import json
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET


def install_missing_dependencies():
    """Fill missing launcher prerequisites with no requested upgrades or removals."""
    packages = [package for executable, package in
                (('/usr/bin/rg', 'ripgrep'), ('/usr/bin/curl', 'curl'))
                if not os.access(executable, os.X_OK)]
    if importlib.util.find_spec('pytest_cov') is None:
        packages.append('python3-pytest-cov')
    if packages:
        print('test-runner-install: installing missing launcher dependencies', flush=True)
        subprocess.run(['/usr/bin/apt-get', '-o', 'DPkg::Lock::Timeout=300', 'install',
                        '--no-upgrade', '--no-remove', '--no-install-recommends', '-y', *packages],
                       env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}, check=True)


def validated_policy(root):
    data = (root / 'config/com.puffyslippers.onpc.development.policy').read_bytes()
    tree = ET.fromstring(data)
    expected = {'com.puffyslippers.onpc.development.' + name: '/usr/local/libexec/onpc-' + name
                for name in ('test-runner', 'diagnostics', 'test-artifacts', 'export-screenshot')}
    actions = tree.findall('action')
    if len(actions) != len(expected) or {item.get('id') for item in actions} != set(expected):
        raise ValueError('test-runner-install:invalid-policy-actions')
    for action in actions:
        annotations = action.findall('annotate')
        defaults = action.find('defaults')
        if (len(annotations) != 1 or annotations[0].get('key') != 'org.freedesktop.policykit.exec.path' or
                annotations[0].text != expected[action.get('id')] or defaults is None or
                len(defaults) != 3 or {node.tag: node.text for node in defaults} !=
                {'allow_any': 'no', 'allow_inactive': 'no', 'allow_active': 'no'}):
            raise ValueError('test-runner-install:unsafe-policy-default-or-program')
    return data


def pinned_vm_uuid(directory=Path('/Data/virt-manager/oh-no-parent-control-baseline-state'), *, owner=0):
    """Pin only accepted root-private provenance; never silently select another VM."""
    path = directory / 'phase.json'
    if not directory.exists():
        return None
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('test-runner-install:symlink-baseline-state')
    info = directory.stat()
    if info.st_uid != owner or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('test-runner-install:unsafe-baseline-directory')
    info = path.stat()
    if info.st_uid != owner or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('test-runner-install:unsafe-baseline-state')
    state = json.loads(path.read_text())
    if state.get('phase') != 'finalized':
        return None
    identity = state['source']['layout']['uuid']
    if str(uuid.UUID(identity)) != identity:
        raise ValueError('test-runner-install:invalid-baseline-uuid')
    return identity


def render_helper(root, name, identity):
    source = (root / 'tools' / name).read_text()
    source = source.replace('CHECKOUT = None  # Replaced with an absolute path by install_test_runner.py.',
                            f'CHECKOUT = {str(root)!r}')
    source = source.replace('VM_UUID = None  # Pinned from finalized baseline state by install_test_runner.py.',
                            f'VM_UUID = {identity!r}')
    return source


def install_file(destination, data, mode):
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    # Never publish a privileged helper through a symlinked installation path.
    if any(part.is_symlink() for part in (destination, *destination.parents)):
        raise ValueError('test-runner-install:symlink-installation-path')
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-install-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), 0, 0)
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit('test-runner-install: run as root without arguments')
    root = Path(__file__).resolve().parents[1]
    identity = pinned_vm_uuid()
    policy_data = validated_policy(root)
    names = ('onpc-test-runner', 'onpc-export-screenshot', 'onpc-test-artifacts', 'onpc-diagnostics')
    rendered = {name: render_helper(root, name, identity).encode() for name in names}
    for name, data in rendered.items():
        compile(data, name, 'exec')
    install_missing_dependencies()
    for name, data in rendered.items():
        install_file(Path('/usr/local/libexec') / name, data, 0o755)
    policy = 'com.puffyslippers.onpc.development.policy'
    install_file(Path('/usr/share/polkit-1/actions') / policy,
                 policy_data, 0o644)
    # Install authorization only after all validated, root-owned helpers exist.
    # polkitd watches this directory; activation is immediate (none).
    policies = (
        ('50-onpc-screenshot-export.rules', '.onpc-screenshot-policy-'),
        ('50-onpc-test-runner.rules', '.onpc-test-runner-policy-'),
        ('50-onpc-test-artifacts.rules', '.onpc-test-artifacts-policy-'),
        ('50-onpc-diagnostics.rules', '.onpc-diagnostics-policy-'),
    )
    for name, _prefix in policies:
        destination = Path('/etc/polkit-1/rules.d') / name
        install_file(destination, (root / 'config' / name).read_bytes(), 0o644)
    print('test-runner-install: installed root-owned development tools and scoped authorizations')
    print('test-runner-install: VM identity ' + ('pinned' if identity else 'unavailable; VM operations disabled'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, ET.ParseError, subprocess.CalledProcessError):
        sys.exit('test-runner-install: refused invalid provenance or unsafe installation state')
