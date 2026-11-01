#!/usr/bin/python3
"""Install development helpers that resolve the invoking repository root."""

from contextlib import ExitStack
import json
import importlib.util
import os
from pathlib import Path
import platform
import pwd
import grp
import stat
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
import vm_config


HEADLESS_RULE = Path('/etc/polkit-1/rules.d/49-onpc-headless.rules')
HEADLESS_ACCOUNT = Path('/usr/local/libexec/onpc-headless-account')


def headless_rule(root):
    """Opt in one administrator account, without granting generic pkexec access."""
    release = platform.freedesktop_os_release()
    try:
        version = tuple(int(part) for part in release.get('VERSION_ID', '').split('.'))
    except ValueError as error:
        raise ValueError('headless setup requires Ubuntu 26.04 or newer') from error
    if release.get('ID') != 'ubuntu' or len(version) < 2 or version[:2] < (26, 4):
        raise ValueError('headless setup requires Ubuntu 26.04 or newer')
    uid = int(os.environ.get('PKEXEC_UID', os.environ.get('SUDO_UID', '0')))
    if uid <= 0:
        raise ValueError('headless setup requires an attributed unprivileged administrator')
    account = pwd.getpwuid(uid)
    if grp.getgrnam('sudo').gr_gid not in os.getgrouplist(account.pw_name, account.pw_gid):
        raise ValueError('headless automation account must belong to sudo')
    # Use the same ownership/path boundary as the installed helpers, including
    # during first installation through sudo rather than pkexec.
    os.environ['PKEXEC_UID'] = str(uid)
    sys.path.insert(0, str(root / 'tools'))
    from dev_checkout import checkout_root
    if checkout_root() != root or root.stat().st_uid != uid:
        raise ValueError('run headless setup from the administrator-owned checkout')
    programs = {'com.puffyslippers.onpc.development.' + name: '/usr/local/libexec/onpc-' + name
                for name in ('test-runner', 'diagnostics', 'test-artifacts', 'export-screenshot', 'setup')}
    account_data = (json.dumps({'uid': uid, 'user': account.pw_name}, sort_keys=True) + '\n').encode()
    data = ('''// Explicit headless opt-in; managed by ./setup.sh --headless.
// Desktop refreshes preserve this grant. Administrator removal revokes it.
polkit.addRule(function(action, subject) {
    var programs = ''' + json.dumps(programs, sort_keys=True) + ''';
    if (!Object.prototype.hasOwnProperty.call(programs, action.id)) {
        return;
    }
    if (subject.user === ''' + json.dumps(account.pw_name) + ''' && subject.isInGroup("sudo")) {
        if ((!action.lookup("user") && !action.lookup("program")) ||
            (action.lookup("user") === "root" && action.lookup("program") === programs[action.id])) {
            return polkit.Result.YES;
        }
        return polkit.Result.NO;
    }
    // Other accounts continue through the ordinary active/local administrator rules.
});
''').encode()
    for path in (HEADLESS_ACCOUNT, HEADLESS_RULE):
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                    or info.st_mode & 0o022
                    or (path == HEADLESS_ACCOUNT and path.read_bytes() != account_data)):
                raise ValueError('existing headless grant differs or is unsafe; administrator repair required')
    return data, account_data


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


def install_missing_dependencies(*, headless=False):
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
    if headless:
        # Bootstrap precedes full dependencies on a clean Ubuntu Server.
        if not os.access('/usr/bin/pkcheck', os.X_OK):
            packages.append('polkitd')
        if not os.access('/usr/bin/pkexec', os.X_OK):
            packages.append('pkexec')
    if packages:
        print('test-runner-install: installing missing launcher dependencies', flush=True)
        if headless:
            subprocess.run(['/usr/bin/apt-get', '-o', 'DPkg::Lock::Timeout=300', 'update'],
                           env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                                'DEBIAN_FRONTEND': 'noninteractive'}, check=True)
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
    if sys.argv[1:] not in ([], ['--headless']) or os.geteuid() != 0:
        raise SystemExit('test-runner-install: invoke through ./setup.sh')
    root = Path(__file__).resolve().parents[1]
    headless = sys.argv[1:] == ['--headless']
    headless_data = headless_rule(root) if headless else None
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
    if headless:
        install_missing_dependencies(headless=True)
    else:
        install_missing_dependencies()
    for name, data in rendered.items():
        install_file(Path('/usr/local/libexec') / name, data, 0o755)
    policy = 'com.puffyslippers.onpc.development.policy'
    install_file(Path('/usr/share/polkit-1/actions') / policy,
                 policy_data, 0o644)
    # Interactive preview authentication has no helper/executable binding and
    # deliberately requires fresh administrator authentication on each request.
    preview_policy = 'com.puffyslippers.onpc.preview.policy'
    install_file(Path('/usr/share/polkit-1/actions') / preview_policy,
                 (root / 'config' / preview_policy).read_text().replace(
                     '@PREVIEW_OWNER_UID@', str(root.stat().st_uid)).encode(), 0o644)
    install_file(Path('/etc/polkit-1/rules.d/00-onpc-preview.rules'),
                 (root / 'config/00-onpc-preview.rules').read_bytes(), 0o644)
    # Install authorization only after all validated, root-owned helpers exist.
    # polkitd watches this directory; activation is immediate (none).
    for name, data in policy_rules.items():
        destination = Path('/etc/polkit-1/rules.d') / name
        install_file(destination, data, 0o644)
    if headless_data is not None:
        # Publish the SSH/background grant only after all scoped helpers exist.
        install_file(HEADLESS_RULE, headless_data[0], 0o644)
        # A public, root-owned marker permits noninteractive refresh without
        # requiring the caller to traverse Polkit's potentially private directory.
        install_file(HEADLESS_ACCOUNT, headless_data[1], 0o644)
        print('test-runner-install: enabled scoped headless access for the invoking administrator')
    repair_checkout_bytecode(root)
    print('test-runner-install: installed root-owned development tools and scoped authorizations')
    print('test-runner-install: VM identities pinned only for finalized configured baselines')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, ET.ParseError, subprocess.CalledProcessError) as error:
        sys.exit(f'test-runner-install: refused installation: {error}')
