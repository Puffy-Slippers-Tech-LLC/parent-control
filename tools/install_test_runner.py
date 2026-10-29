#!/usr/bin/python3
"""Install development helpers that resolve the invoking repository root."""

from contextlib import ExitStack
import json
import importlib.util
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
import vm_config


def host_distribution():
    release = platform.freedesktop_os_release()
    distribution = release.get('ID')
    if distribution not in ('ubuntu', 'debian', 'fedora'):
        raise ValueError('test-runner-install:unsupported-development-host')
    if distribution == 'fedora' and release.get('VERSION_ID') != '44':
        raise ValueError('test-runner-install:Fedora-44-required')
    return distribution


def development_rule(root, name):
    """Use only the host's administrator group; keep all caller/path guards."""
    source = (root / 'config' / name).read_text()
    if source.count('subject.isInGroup("sudo")') != 1:
        raise ValueError('test-runner-install:invalid-administrator-rule')
    group = 'wheel' if host_distribution() == 'fedora' else 'sudo'
    return source.replace('subject.isInGroup("sudo")',
                          f'subject.isInGroup("{group}")').encode()


def watch_terminal_available():
    try:
        import gi
        gi.require_version('Vte', '3.91')
        return True
    except (ImportError, ValueError):
        return False


def install_missing_dependencies():
    """Fill missing launcher prerequisites with no requested upgrades or removals."""
    fedora = host_distribution() == 'fedora'
    packages = [package for executable, package in
                (('/usr/bin/ssh', 'openssh-clients' if fedora else 'openssh-client'),
                 ('/usr/bin/rg', 'ripgrep'), ('/usr/bin/curl', 'curl'))
                if not os.access(executable, os.X_OK)]
    if importlib.util.find_spec('pytest_cov') is None:
        packages.append('python3-pytest-cov')
    if importlib.util.find_spec('gi') is None:
        packages.append('python3-gobject' if fedora else 'python3-gi')
    if not watch_terminal_available():
        packages.append('vte291-gtk4' if fedora else 'gir1.2-vte-3.91')
    if packages:
        print('test-runner-install: installing missing launcher dependencies', flush=True)
        command = (['/usr/bin/dnf', '-y', '--setopt=install_weak_deps=False', 'install']
                   if fedora else
                   ['/usr/bin/apt-get', '-o', 'DPkg::Lock::Timeout=300', 'install',
                    '--no-upgrade', '--no-remove', '--no-install-recommends', '-y'])
        subprocess.run([*command, *packages],
                       env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                            'DEBIAN_FRONTEND': 'noninteractive'}, check=True)


def validated_policy(root):
    data = (root / 'config/com.puffyslippers.onpc.development.policy').read_bytes()
    tree = ET.fromstring(data)
    expected = {'com.puffyslippers.onpc.development.' + name: '/usr/local/libexec/onpc-' + name
                for name in ('test-runner', 'diagnostics', 'test-artifacts', 'export-screenshot', 'setup')}
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


def pinned_vm_uuid(directory=None, *, owner=0, name=None):
    """Pin only accepted root-private provenance; never silently select another VM."""
    if directory is None:
        directory = vm_config.load(name).baseline_directory
    path = directory / 'phase.json'
    if not directory.exists():
        return None
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('test-runner-install:symlink-baseline-state')
    info = directory.stat()
    if info.st_uid != owner or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('test-runner-install:unsafe-baseline-directory')
    restore = directory / 'restore-vms.json'
    if os.path.lexists(restore):
        record = restore.lstat()
        if (not stat.S_ISREG(record.st_mode) or record.st_nlink != 1 or
                record.st_uid != owner or stat.S_IMODE(record.st_mode) != 0o600 or
                json.loads(restore.read_text()).get('phase') != 'complete'):
            raise ValueError('test-runner-install:unfinished-or-unsafe-vm-restore')
    if not path.exists():
        # Registered, not-yet-prepared VMs may have only an idle lease or a
        # completed recovery journal. They have no accepted UUID to pin.
        if set(item.name for item in directory.iterdir()) <= {'.lock', 'restore-vms.json'}:
            return None
        raise ValueError('test-runner-install:missing-baseline-state')
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
    # Embed the resolver: privileged helpers must not import checkout code to
    # decide which checkout to trust. No installation-time path is retained.
    resolver = (root / 'tools/dev_checkout.py').read_text()
    source = source.replace('CHECKOUT = None  # Replaced with the runtime resolver by install_test_runner.py.',
                            resolver + '\nCHECKOUT = str(checkout_root())\n')
    source = source.replace('VM_UUIDS = {}  # Pinned by name from finalized baseline state by install_test_runner.py.',
                            f'VM_UUIDS = {identity!r}')
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


def repair_checkout_bytecode(root):
    """Return the old dispatcher's cache directory to the tools directory owner.

    Only this generated directory needs repair: the caller can then unlink its
    contents during normal package clean. Do not traverse or chown its files.
    Pin each directory before changing ownership, refusing symlinks/replacements.
    """
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError('test-runner-install:symlink-checkout-path')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    with ExitStack() as stack:
        checkout_fd = os.open(root, flags)
        stack.callback(os.close, checkout_fd)
        tools_fd = os.open('tools', flags, dir_fd=checkout_fd)
        stack.callback(os.close, tools_fd)
        try:
            cache_fd = os.open('__pycache__', flags, dir_fd=tools_fd)
        except FileNotFoundError:
            return
        stack.callback(os.close, cache_fd)
        owner = os.fstat(tools_fd)
        cache = os.fstat(cache_fd)
        if cache.st_uid == 0 and owner.st_uid != 0:
            os.fchown(cache_fd, owner.st_uid, owner.st_gid)
            print('test-runner-install: restored checkout bytecode directory ownership')


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit('test-runner-install: run as root without arguments')
    root = Path(__file__).resolve().parents[1]
    identity = {name: pinned_vm_uuid(name=name) for name in vm_config.registry()}
    pins = [value for value in identity.values() if value is not None]
    if len(pins) != len(set(pins)):
        raise ValueError('test-runner-install:duplicate-baseline-uuid')
    policy_data = validated_policy(root)
    policy_names = ('50-onpc-screenshot-export.rules', '50-onpc-test-runner.rules',
                    '50-onpc-test-artifacts.rules', '50-onpc-diagnostics.rules',
                    '50-onpc-setup.rules')
    policy_rules = {name: development_rule(root, name) for name in policy_names}
    names = ('onpc-test-runner', 'onpc-export-screenshot', 'onpc-test-artifacts', 'onpc-diagnostics', 'onpc-setup')
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
    for name, data in policy_rules.items():
        destination = Path('/etc/polkit-1/rules.d') / name
        install_file(destination, data, 0o644)
    repair_checkout_bytecode(root)
    print('test-runner-install: installed root-owned development tools and scoped authorizations')
    print('test-runner-install: VM identities pinned only for finalized configured baselines')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, ET.ParseError, subprocess.CalledProcessError):
        sys.exit('test-runner-install: refused invalid provenance or unsafe installation state')
