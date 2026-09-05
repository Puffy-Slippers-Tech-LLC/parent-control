#!/usr/bin/python3
"""Run installed-system pytest on the fixed VM, resetting its retained snapshot.

Root host controller. No product installation command executes on the host.
All VM/storage operations are injectable; imports have no machine side effects.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET

# Root runs must not create private bytecode caches in the developer checkout,
# including when this controller is invoked directly instead of through make.
if __name__ == '__main__':
    sys.dont_write_bytecode = True

import prepare_host as baseline

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = '/var/tmp/onpc-system-input'
TAG = 'onpc-system-run:'
require = baseline.require
Error = baseline.CaptureError


def log(stage):
    print(f'check-system: [{stage}]', file=sys.stderr, flush=True)


from owned_commands import Commands, CommandError


def isolated_xml(xml, expected_uuid, run):
    """Use only the fixed guest disk; remove every host-sharing interface."""
    baseline.domain_layout(xml, expected_uuid)
    root = ET.fromstring(xml)
    require(not root.findall('{http://libvirt.org/schemas/domain/qemu/1.0}commandline'), 'guard:qemu-override')
    devices = root.find('devices')
    for name in ('filesystem', 'redirdev', 'channel', 'graphics', 'audio', 'sound', 'rng'):
        for node in devices.findall(name):
            devices.remove(node)
    # A local SPICE display has neither clipboard nor file-transfer agents.
    graphics = ET.SubElement(devices, 'graphics', type='spice', autoport='yes')
    ET.SubElement(graphics, 'listen', type='none')
    ET.SubElement(graphics, 'clipboard', copypaste='no')
    ET.SubElement(graphics, 'filetransfer', enable='no')
    for name in ('serial', 'console'):
        require(all(node.get('type') == 'pty' for node in devices.findall(name)), 'guard:host-character-device')
    interfaces = devices.findall('interface')
    require(len(interfaces) == 1 and interfaces[0].get('type') == 'network' and
            interfaces[0].find('source').attrib == {'network': 'default'}, 'guard:network')
    for item in interfaces[0].findall('filterref'):
        interfaces[0].remove(item)
    for node in root.findall('description'):
        root.remove(node)
    ET.SubElement(root, 'description').text = TAG + run
    return ET.tostring(root, encoding='unicode')


class SourceView:
    """Retain Task 12's exact disk checks while allowing our removed file share."""

    def __init__(self, source):
        self.source = source
        self.original_shares = None
        self.run = None
        self.domain_id = None

    def snapshot(self):
        layout, off = self.source.snapshot()
        if self.run is not None:
            domain = self.source.connection.lookupByName(baseline.DOMAIN)
            root = ET.fromstring(domain.XMLDesc(0))
            require(root.findtext('description') == TAG + self.run, 'guard:run-identity')
            require(not layout['source_shares'] and not root.findall('devices/filesystem') and
                    not root.findall('devices/hostdev') and not root.findall('devices/channel') and
                    not root.findall('devices/redirdev'), 'guard:host-sharing')
            if not off:
                require(self.domain_id is not None and domain.ID() == self.domain_id, 'guard:domain-replaced')
            layout['source_shares'] = self.original_shares
        return layout, off

    def baseline(self):
        return self.source.baseline()


class Lease:
    """Serializes prep-host/system runners; durable state refuses interrupted ownership."""

    def __init__(self, source, commands, inspect, *, directory=baseline.BASELINES, anchor=baseline.ANCHOR):
        self.source, self.commands, self.inspect = source, commands, inspect
        self.view = SourceView(source)
        self.capture = baseline.Capture(self.view, commands, inspect, directory=directory, anchor=anchor)
        self.directory = directory
        self.journal = directory / 'system-run.json'
        self.fd = None
        self.state = None
        self.original_xml = None
        self.original_id = None
        self.mutated = False

    def save(self, phase):
        self.state['phase'] = phase
        require(self.capture.private_directory() == self.capture.directory_identity, 'guard:directory-changed')
        fd, path = tempfile.mkstemp(prefix='.system-run-', dir=self.directory)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(baseline.encode(self.state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.journal)
        baseline.sync_directory(self.directory)
        log('stage:' + phase)

    def __enter__(self):
        try:
            self.capture.directory_identity = self.capture.private_directory()
            self.fd = os.open(self.directory / '.lock', os.O_RDWR | os.O_NOFOLLOW)
            baseline.identity(self.directory / '.lock', private=True, mode=0o600)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Error('state:busy-controller') from error
            self.commands.lock_fd = self.fd
            self.capture.state = self.capture.read_state()
            require(self.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
            log('stage:baseline-verification')
            require(self.capture.verify_snapshot() == self.capture.state['proof'], 'baseline:changed')
            if self.journal.exists():
                baseline.identity(self.journal, private=True, mode=0o600)
                previous = baseline.parse_json(self.journal.read_bytes())
                require(previous.get('phase') == 'complete', 'state:interrupted-run; preserve state for recovery')
            self.original_xml = self.source.domain.XMLDesc(self.source.api.VIR_DOMAIN_XML_INACTIVE)
            self.original_id = self.source.domain.ID()
            require(not self.source.domain.autostart(), 'guard:autostart')
            run = uuid.uuid4().hex
            # Validate isolation before creating state or shutting down a VM.
            self.test_xml = isolated_xml(self.original_xml, self.source.uuid, run)
            self.state = {'schema_version': 1, 'run': run, 'phase': 'validated',
                          'domain_uuid': self.source.uuid, 'domain_id': None,
                          'original_xml': self.original_xml,
                          'baseline_sha256': hashlib.sha256(baseline.encode(self.capture.state)).hexdigest()}
            self.save('validated')
            return self
        except BaseException:
            self.release()
            raise

    def guard(self, *, off=False):
        self.capture.revalidate(off=off)
        require(self.source.baseline() == self.snapshot_xml, 'baseline:snapshot-metadata-changed')

    def prepare(self):
        self.snapshot_xml = self.source.baseline()
        # The initial shutdown is explicitly authorized for this fixed source VM.
        self.save('shutdown-requested')
        self.source.shutdown(self.capture.revalidate, requested=False)
        self.guard(off=True)
        self.save('restore-requested')
        self.mutated = True
        self.restore()
        require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                             self.capture.state['script_digest']) == self.capture.state['guest'], 'baseline:guest-changed')
        self.source.connection.defineXML(self.test_xml)
        self.view.original_shares = self.capture.state['source']['layout']['source_shares']
        self.view.run = self.state['run']
        self.guard(off=True)
        self.save('isolated')

    def restore(self):
        # snapshot revert defaults to its saved shutoff state; never pass RUNNING.
        self.capture.revalidate(off=True)
        snap = self.source.domain.snapshotLookupByName(baseline.SNAPSHOT, 0)
        require(snap.getXMLDesc(0) == self.snapshot_xml, 'baseline:snapshot-metadata-changed')
        self.source.domain.revertToSnapshot(snap, 0)
        self.view.run = None
        self.view.domain_id = None
        self.capture.revalidate(off=True)

    def start(self):
        self.guard(off=True)
        self.save('start-requested')
        self.source.domain.create()
        self.view.domain_id = self.source.domain.ID()
        require(self.view.domain_id >= 0, 'start:identity-unavailable')
        self.state['domain_id'] = self.view.domain_id
        self.guard()
        self.save('running')

    def finish(self):
        if not self.mutated:
            self.save('complete')
            return
        self.save('cleanup-requested')
        self.guard()
        if not self.view.snapshot()[1]:
            # Only the domain instance started and identity-recorded by this run.
            require(self.view.domain_id is not None, 'cleanup:unowned-domain')
            try:
                self.source.shutdown(self.guard, requested=False)
            except Error as error:
                if str(error) != 'shutdown:timeout':
                    raise
                self.guard()
                self.source.domain.destroyFlags(0)
        self.guard(off=True)
        self.restore()
        log('stage:restored-baseline-verification')
        require(self.capture.verify_snapshot() == self.capture.state['proof'], 'cleanup:baseline-changed')
        require(self.inspect(Path(self.capture.state['source']['layout']['disk']),
                             self.capture.state['script_digest']) == self.capture.state['guest'], 'cleanup:guest-changed')
        # Revert restores the snapshot's XML; restore the validated pre-run config.
        self.source.connection.defineXML(self.original_xml)
        self.capture.revalidate(off=True)
        self.save('complete')

    def release(self):
        self.commands.lock_fd = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __exit__(self, *exc):
        try:
            self.finish()
        finally:
            self.release()


def check_tree(root):
    root = baseline.canonical(root)
    require(root.is_dir(), 'assets:directory')
    for path in root.rglob('*'):
        info = path.lstat()
        require(not path.is_symlink() and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)),
                'assets:special-file')
    return root


def stage_assets(source, destination, commands):
    """Freeze user-built artifacts in root-private storage, then recheck all bytes."""
    sys.path.insert(0, str(ROOT / 'tools'))
    sys.path.insert(0, str(ROOT / 'tests/fixtures'))
    from build_test_artifacts import verify
    from build_test_applications import verify as verify_fixtures
    check_tree(source)
    shutil.copytree(source, destination)
    check_tree(destination)
    manifest = verify(destination)
    package = destination / manifest['artifacts']['package']['path']
    fixtures = destination / manifest['artifacts']['fixtures']['path']
    verify_fixtures(fixtures)
    require((fixtures / 'onpc-test-application.flatpak').is_file(), 'assets:fixture-bundle-missing')
    shutil.copyfile(package, destination / 'package.deb')
    require(commands.run(['dpkg-deb', '-f', str(package), 'Package']).decode().strip() ==
            'oh-no-parent-control', 'assets:package-name')
    archive = commands.run(['dpkg-deb', '--fsys-tarfile', str(package)])
    import io
    entries = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        for entry in tar:
            require(not Path(entry.name).is_absolute() and '..' not in Path(entry.name).parts, 'assets:package-path')
            if entry.isfile() or entry.issym():
                entries.append({'path': '/' + entry.name.removeprefix('./'),
                                'kind': 'file' if entry.isfile() else 'symlink',
                                'mode': entry.mode, 'target': entry.linkname})
            else:
                require(entry.isdir(), 'assets:package-special-file')
    (destination / 'installed-files.json').write_bytes(baseline.encode(entries))
    # Every transferred file, including Flatpak's varying delivery container,
    # receives an exact run digest in addition to Task 13A's stable payload digest.
    inventory = {str(p.relative_to(destination)): baseline.digest(p)
                 for p in sorted(destination.rglob('*')) if p.is_file()}
    (destination / 'transfer-sha256.json').write_bytes(baseline.encode(inventory))
    return manifest


def ubuntu_archive_sources(contents):
    """Normalize only official Ubuntu URIs in Deb822 URIs fields.

    Preserve all other fields and bytes, including embedded signing keys and
    unrelated repositories. The fixed prepared Ubuntu guest uses Deb822.
    """
    lines = []
    uri_field = False
    for line in contents.splitlines(keepends=True):
        if line.strip() and not line.lstrip().startswith('#'):
            if not line[0].isspace():
                uri_field = line.lower().startswith('uris:')
            if uri_field:
                line = re.sub(
                    r'(?<!\S)https?://(?:(?:[a-z]{2}\.)?archive|security)\.ubuntu\.com/ubuntu/?(?=\s|$)',
                    'https://archive.ubuntu.com/ubuntu/', line)
        elif not line.strip():
            uri_field = False
        lines.append(line)
    return ''.join(lines)


@contextmanager
def mounted_guest(guestfs, lease, *, readonly=False):
    """Open the guarded offline disk; always close it before another writer."""
    lease.guard(off=True)
    disk = Path(lease.capture.state['source']['layout']['disk'])
    g = guestfs.GuestFS(python_return_dict=True)
    try:
        g.set_backend('direct')
        g.set_network(False)
        g.add_drive_opts(str(disk), format='qcow2', readonly=readonly)
        g.launch()
        roots = g.inspect_os()
        require(len(roots) == 1, 'bootstrap:guest-root')
        mounts = g.inspect_get_mountpoints(roots[0])
        for point in sorted(mounts, key=lambda v: (len(v), v)):
            (g.mount_ro if readonly else g.mount)(mounts[point], point)
        yield g
        if not readonly:
            g.sync()
    finally:
        g.close()
    lease.guard(off=True)


def bootstrap(commands, lease, directory, guestfs):
    """Prepare SSH only on the reset, powered-off active disk via libguestfs."""
    lease.guard(off=True)
    disk = Path(lease.capture.state['source']['layout']['disk'])
    key = directory / 'ssh-key'
    commands.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'onpc-system-test', '-f', str(key)])
    lease.save('ssh-bootstrap')
    with mounted_guest(guestfs, lease) as g:
        sources_path = '/etc/apt/sources.list.d/ubuntu.sources'
        sources = g.read_file(sources_path).decode()
        normalized = ubuntu_archive_sources(sources)
        if normalized != sources:
            g.write(sources_path, normalized.encode())
        log('bootstrap:ubuntu-archive-https-ready')
        # The removed preparation-only share must not prevent boot via fstab.
        fstab = g.read_file('/etc/fstab').decode()
        lines = []
        for line in fstab.splitlines():
            fields = line.split()
            if fields and not fields[0].startswith('#') and len(fields) >= 3 and fields[2] in {'virtiofs', '9p'}:
                require(fields[1] == '/Data', 'bootstrap:unexpected-share')
                continue
            lines.append(line)
        g.write('/etc/fstab', ('\n'.join(lines) + '\n').encode())
        marker = {'purpose': 'onpc-system-test', 'run': lease.state['run'],
                  'domain_uuid': lease.source.uuid,
                  'machine_id': g.read_file('/etc/machine-id').decode().strip(),
                  'host_machine_id': Path('/etc/machine-id').read_text().strip(),
                  'baseline_sha256': lease.state['baseline_sha256'],
                  'preparation_sha256': lease.capture.state['guest']['preparation_record_sha256'],
                  'package_sha256': baseline.digest(directory / 'input/package.deb')}
        require(marker['machine_id'] != marker['host_machine_id'], 'bootstrap:host-identity')
        g.write('/etc/onpc-system-test.json', baseline.encode(marker))
        g.chown(0, 0, '/etc/onpc-system-test.json')
        g.chmod(0o600, '/etc/onpc-system-test.json')
    lease.guard(off=True)
    commands.run(['virt-customize', '--format', 'qcow2', '-a', str(disk),
                  '--install', 'openssh-server=1:10.2p1-2ubuntu3.6,python3-pytest=9.0.2-4',
                  '--ssh-inject', f'root:file:{key}.pub',
                  '--run-command', 'systemctl enable ssh.service'], timeout=1800)
    with mounted_guest(guestfs, lease, readonly=True) as g:
        host_key = g.read_file('/etc/ssh/ssh_host_ed25519_key.pub').decode().split()
        require(len(host_key) >= 2 and host_key[0] == 'ssh-ed25519', 'bootstrap:ssh-host-key')
    return ' '.join(host_key[:2])


def address(source, timeout=300):
    """Wait on libvirt's DHCP lease list with a bounded event-loop timer."""
    deadline = time.monotonic() + timeout
    event = threading.Event()
    timer = source.api.virEventAddTimeout(500, lambda *_: event.set(), None)
    try:
        while time.monotonic() < deadline:
            interfaces = source.domain.interfaceAddresses(source.api.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE, 0)
            addresses = [a['addr'] for item in interfaces.values() for a in item.get('addrs', [])
                         if a['type'] == source.api.VIR_IP_ADDR_TYPE_IPV4]
            if len(addresses) == 1:
                value = ipaddress.ip_address(addresses[0])
                require(value.is_private and not value.is_loopback, 'network:address')
                return str(value)
            event.wait(max(0, deadline - time.monotonic()))
            event.clear()
        raise Error('network:readiness-timeout')
    finally:
        source.api.virEventRemoveTimeout(timer)


def guest_command(run, *args):
    return ['env', f'ONPC_EXPECTED_RUN={run}', 'PYTHONDONTWRITEBYTECODE=1',
            '/usr/bin/python3', PAYLOAD + '/system_guest.py', *args]


def pytest_command(run, phase):
    require(phase in {'installed', 'rebooted'}, 'pytest:phase')
    tests = ['test_installed_package', 'test_first_install_requests_reboot' if phase == 'installed'
             else 'test_reboot_applies_installation']
    return ['env', f'ONPC_EXPECTED_RUN={run}', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
            'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-m', 'pytest',
            '-c', PAYLOAD + '/pytest.ini', '--noconftest', '--rootdir', PAYLOAD,
            '--junitxml', f'{PAYLOAD}/results/{phase}.xml', '-q',
            *[f'{PAYLOAD}/test_install_smoke.py::{name}' for name in tests]]


def installed_run(vm, lease, directory):
    run = lease.state['run']
    outcome = 'failed'
    try:
        vm.ready()
        vm.copy(False, str(directory / 'input') + '/', PAYLOAD + '/')
        lease.save('package-install')
        vm.call(guest_command(run, 'install'), timeout=2400)
        lease.save('pytest-installed')
        vm.call(pytest_command(run, 'installed'), timeout=900)
        # Preserve the successful first phase even if reboot loses transport.
        vm.call(guest_command(run, 'collect', 'installed'), timeout=180)
        vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
        lease.save('reboot-requested')
        vm.reboot()
        lease.save('pytest-rebooted')
        vm.call(pytest_command(run, 'rebooted'), timeout=900)
        outcome = 'passed'
    finally:
        original_failure = sys.exc_info()[0] is not None
        try:
            lease.guard()
            vm.call(guest_command(run, 'collect', outcome), timeout=180)
            vm.copy(True, PAYLOAD + '/results/', str(directory / 'guest-results') + '/')
        except Exception:
            if not original_failure:
                raise
            # Retain the original failure even if the guest cannot return logs.
            log('evidence:guest-collection-failed')
    for phase in ('installed', 'rebooted'):
        root = ET.parse(directory / f'guest-results/{phase}.xml').getroot()
        suites = list(root.iter('testsuite'))
        require(sum(int(s.get('tests', '0')) for s in suites) == 2 and
                all(all(int(s.get(key, '0')) == 0 for key in ('errors', 'failures', 'skipped'))
                    for s in suites), 'pytest:missing-failed-or-skipped-tests')


def host_fingerprint(commands):
    """Detect product or login-integration changes on the development host."""
    paths = ('/etc/pam.d/common-auth', '/etc/pam.d/common-account', '/etc/pam.d/common-session',
             '/etc/oh-no-parent-control/config.json',
             '/usr/lib/systemd/system/oh-no-parent-control-broker.service',
             '/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules')
    result = {path: baseline.digest(Path(path)) if Path(path).is_file() else None for path in paths}
    result['package-status'] = hashlib.sha256(commands.run(
        ['dpkg-query', '-W', '-f=${Status} ${Version}', 'oh-no-parent-control'], check=False)).hexdigest()
    return result


def evidence(directory, manifest, lease, passed, category):
    output = directory / 'evidence'
    output.mkdir(exist_ok=True)
    data = {'schema_version': 1, 'test': 'install-smoke', 'outcome': 'passed' if passed else 'failed',
            'category': category, 'package_sha256': manifest['artifacts']['package']['sha256'],
            'fixture_sha256': manifest['artifacts']['fixtures']['sha256'],
            'baseline_provenance_sha256': lease.state['baseline_sha256'],
            'source': manifest['source'], 'cleanup_phase': lease.state['phase'],
            'transport': 'guarded-ssh-pytest', 'virtualization': 'libvirt-qemu-snapshot'}
    (output / 'result.json').write_bytes(baseline.encode(data))
    suite = ET.Element('testsuite', name='onpc-system', tests='1', failures='0' if passed else '1')
    case = ET.SubElement(suite, 'testcase', name='install-smoke')
    if not passed:
        ET.SubElement(case, 'failure', message=category)
    ET.ElementTree(suite).write(output / 'results.xml', encoding='utf-8', xml_declaration=True)
    (output / 'results.tap').write_text('TAP version 13\n1..1\n' +
                                       ('ok' if passed else 'not ok') + ' 1 - install-smoke\n')
    collected = directory / 'guest-results'
    if collected.is_dir():
        check_tree(collected)
        shutil.copytree(collected, output / 'guest', dirs_exist_ok=True)
    for path in output.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    output.chmod(0o755)
    directory.chmod(0o755)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True, help='Task 13A artifact directory')
    parser.add_argument('--check-tools', action='store_true')
    args = parser.parse_args(argv)
    source = None
    lease = None
    directory = None
    manifest = None
    passed = False
    host_before = None
    category = 'runner-failed'
    try:
        require(Path.cwd() == ROOT == baseline.guest_contract.CHECKOUT, 'guard:checkout')
        for name in ('ssh', 'qemu-img', 'ssh-keygen', 'virt-customize'):
            require(shutil.which(name) is not None, 'tools:missing; run ./setup.sh')
        api, guestfs = importlib.import_module('libvirt'), importlib.import_module('guestfs')
        if args.check_tools:
            log('tools:available')
            return 0
        require(os.geteuid() == os.getegid() == 0, 'guard:root; run from a root shell on the VM host')
        os.umask(0o077)
        directory = Path(tempfile.mkdtemp(prefix='onpc-system-'))
        private = directory / 'private'
        private.mkdir(mode=0o700)
        commands = Commands()
        commands.directory = private
        manifest = stage_assets(args.artifacts.resolve(strict=True), directory / 'input', commands)
        host_before = host_fingerprint(commands)
        for relative in ('tests/integration/system_guest.py', 'tests/integration/owned_commands.py',
                         'tests/system/test_install_smoke.py', 'tests/system/pytest.ini'):
            shutil.copyfile(ROOT / relative, directory / 'input' / Path(relative).name)
        (directory / 'input/guest').mkdir()
        shutil.copyfile(ROOT / 'tests/integration/guest/redact.py', directory / 'input/guest/redact.py')
        # Include the exact test/helper bytes as well as package and fixtures.
        inventory = {str(p.relative_to(directory / 'input')): baseline.digest(p)
                     for p in sorted((directory / 'input').rglob('*'))
                     if p.is_file() and p.name != 'transfer-sha256.json'}
        (directory / 'input/transfer-sha256.json').write_bytes(baseline.encode(inventory))
        api.virEventRegisterDefaultImpl()
        def events():
            while True:
                api.virEventRunDefaultImpl()
        threading.Thread(target=events, daemon=True, name='libvirt-events').start()
        source = baseline.LibvirtSource(api)
        lease = Lease(source, commands, lambda disk, digest: baseline.inspect_guest(guestfs, disk, digest))
        # SIGTERM follows the same finally/lease cleanup as an interactive interruption.
        def interrupted(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
        with lease:
            lease.prepare()
            host_key = bootstrap(commands, lease, directory, guestfs)
            lease.start()
            hostname = address(source)
            (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
            config = {
                'directory': str(directory), 'hostname': hostname, 'run': lease.state['run'],
                'domain_uuid': source.uuid, 'domain_id': lease.view.domain_id,
            }
            from vm_transport import Transport
            vm = Transport(config, commands, guard=lambda _: lease.guard())
            lease.guard()
            installed_run(vm, lease, directory)
            result = json.loads((directory / 'guest-results/result.json').read_text())
            require(result['outcome'] == 'passed' and result['package_sha256'] ==
                    manifest['artifacts']['package']['sha256'], 'pytest:guest-evidence')
            lease.guard()
        require(host_fingerprint(commands) == host_before, 'host:product-state-changed')
        passed = True
        category = 'all-checks-passed'
    except (Exception, KeyboardInterrupt) as error:
        category = str(error) if isinstance(error, (Error, CommandError)) else 'unexpected-failure-or-interruption'
        log(category)
    finally:
        if host_before is not None:
            try:
                require(host_fingerprint(commands) == host_before, 'host:product-state-changed')
            except Exception:
                passed, category = False, 'host:product-state-changed-or-unverifiable'
        if source:
            source.close()
        if directory and manifest and lease and lease.state:
            evidence(directory, manifest, lease, passed, category)
            log('evidence:' + str(directory / 'evidence'))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
