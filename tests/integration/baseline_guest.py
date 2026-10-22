"""Stage and boot guest preparation under the host capture's exclusive lease."""

from contextlib import contextmanager
from pathlib import Path
import os
import hashlib
import json
import re
import stat
import tempfile
import time
import xml.etree.ElementTree as ET

import prepare_vm
from qualification_storage import allocate, recovery_session
from test_account_password import matches
from watch_activity import observed

STAGE = '/var/lib/onpc-baseline-preparation'
UNIT = '/etc/systemd/system/onpc-baseline-preparation.service'
LINK = '/etc/systemd/system/multi-user.target.wants/onpc-baseline-preparation.service'
SOURCE_RETIREMENT = STAGE + '/source-retirement.json'
SOURCE_STAGING = STAGE + '/source-staging.json'
STAGED_MOVABLE_SOURCES = (*prepare_vm.SNAPSHOT_SOURCE_SYMBOLS,
                         'common/oh_no_parent_control_ui/gtk_automation.py')
SERVICE = f'''[Unit]
Description=Prepare the ONPC test baseline
Wants=network-online.target accounts-daemon.service
After=network-online.target accounts-daemon.service
Before=display-manager.service apt-daily.service apt-daily-upgrade.service
ConditionPathExists={STAGE}/password
SuccessAction=poweroff
FailureAction=poweroff

[Service]
Type=oneshot
UMask=0077
WorkingDirectory={STAGE}/checkout
ExecStart=/usr/bin/python3 -B {STAGE}/checkout/tests/integration/baseline_guest_entry.py
TimeoutStartSec=7200
StandardOutput=append:{STAGE}/preparation.log
StandardError=append:{STAGE}/preparation.log
'''


def require(condition, code):
    if not condition:
        from prepare_baseline import CaptureError
        raise CaptureError(code)


@contextmanager
def mounted(guestfs, capture):
    capture.revalidate(off=True)
    g = guestfs.GuestFS(python_return_dict=True)
    try:
        g.set_trace(False)
        g.set_verbose(False)
        g.set_backend('direct')
        g.set_network(False)
        g.add_drive_opts(capture.state['source']['layout']['disk'], format='qcow2')
        g.launch()
        roots = g.inspect_os()
        require(len(roots) == 1, 'guest:release')
        mounts = g.inspect_get_mountpoints(roots[0])
        require('/' in mounts, 'guest:mounts')
        for point in sorted(mounts, key=lambda value: (len(value), value)):
            g.mount(mounts[point], point)
        try:
            prepare_vm.inspected_release(g, roots[0])
        except prepare_vm.PreparationError:
            require(False, 'guest:release; requires Ubuntu 26.04 or Fedora Workstation 44')
        yield g
        g.sync()
    finally:
        g.close()
    capture.revalidate(off=True)


def directory(g, path):
    if not g.exists(path) and not g.is_symlink(path):
        directory(g, str(Path(path).parent))
        g.mkdir(path)
        g.chmod(0o700, path)
    info = g.lstatns(path)
    require(g.realpath(path) == path and stat.S_ISDIR(info['st_mode'])
            and info['st_uid'] == 0 and not info['st_mode'] & 0o022,
            'guest:preparation-directory')


def write(g, path, content):
    directory(g, str(Path(path).parent))
    if g.exists(path) or g.is_symlink(path):
        info = g.lstatns(path)
        require(g.realpath(path) == path and stat.S_ISREG(info['st_mode'])
                and info['st_uid'] == 0 and info['st_nlink'] == 1,
                'guest:preparation-file')
    g.write(path, content)
    g.chmod(0o600, path)


def label_preparation(g, paths=None):
    release = prepare_vm.parse_os_release(g.read_file('/etc/os-release').decode('utf-8'))
    os_id, _ = prepare_vm.release_identity(release)
    if os_id == 'fedora':
        policy = prepare_vm.selinux_policy(g.read_file('/etc/selinux/config').decode('utf-8'))
        paths = [STAGE, UNIT, LINK] if paths is None else paths
        # Python API presence does not imply appliance support: Ubuntu's
        # appliance omits setfiles. Use Fedora's tool and libraries through the
        # mounted-guest command API when the appliance lacks that feature.
        # -m keeps mounted guest filesystems eligible for relabelling.
        if not g.feature_available(['selinuxrelabel']):
            require(g.is_file('/usr/sbin/setfiles'),
                    'guest:selinux-setfiles-missing; install policycoreutils in the Fedora guest')
            try:
                g.command(['/usr/sbin/setfiles', '-m', policy, *paths])
            except RuntimeError:
                require(False, 'guest:selinux-relabel-failed')
        elif hasattr(g, 'setfiles'):
            g.setfiles(policy, paths)
        else:
            for path in paths:
                g.selinux_relabel(policy, path)


def preparation_failure(g):
    """Keep a bounded private log while exposing only diagnostic categories."""
    path = STAGE + '/preparation.log'
    diagnostics = 'no-log'
    evidence = '; inspect guest preparation.log'
    try:
        if not (g.exists(path) or g.is_symlink(path)):
            return diagnostics + evidence
        info = g.lstatns(path)
        if (g.is_symlink(path) or g.realpath(path) != path
                or not stat.S_ISREG(info['st_mode']) or info['st_uid'] != 0
                or info['st_nlink'] != 1):
            return 'unsafe-log' + evidence
        size = g.filesize(path)
        if size < 0:
            return 'unsafe-log' + evidence
        tail = g.pread(path, min(size, 16384), max(0, size - 16384))[-16384:]
    except Exception:
        return 'log-read-failed' + evidence
    text = tail.decode('utf-8', 'replace')
    tokens = re.findall(r'(?:prepare-vm|baseline): \[([a-z][a-z0-9:-]*)\]', text)
    exceptions = re.findall(r'^([A-Za-z]+Error):', text, re.MULTILINE)
    diagnostics = ','.join((tokens + exceptions)[-12:]) or 'no-stage'
    try:
        with recovery_session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-baseline-preparation-failure-'))
            artifact = directory / 'preparation.log'
            descriptor = os.open(artifact, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(tail)
        evidence = '; artifact:' + str(artifact)
    except Exception:
        evidence += '; retention:failed'
    return diagnostics + evidence


def recover_source_staging(g):
    """Retire only exact completed or privately pending preparation copies."""
    from baseline_fixtures import regular
    if not (g.exists(SOURCE_STAGING) or g.is_symlink(SOURCE_STAGING)):
        return
    regular(g, SOURCE_STAGING, 0, 0, 0o600)
    record = json.loads(g.read_file(SOURCE_STAGING))
    require(type(record) is dict and set(record) == {'purpose', 'files', 'pending'}
            and record['purpose'] == 'onpc-preparation-source-staging-v1'
            and type(record['files']) is dict
            and set(record['files']) == set(STAGED_MOVABLE_SOURCES)
            and record['pending'] in (None, *STAGED_MOVABLE_SOURCES),
            'guest:source-staging-record')
    for relative, digest in record['files'].items():
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest) is not None,
                'guest:source-staging-record')
        path = STAGE + '/checkout/' + relative
        if g.exists(path) or g.is_symlink(path):
            directory(g, str(Path(path).parent))
            regular(g, path, 0, 0, 0o600)
            require(relative == record['pending'] or g.checksum('sha256', path) == digest,
                    'guest:source-staging-substituted')
    for relative in record['files']:
        path = STAGE + '/checkout/' + relative
        if g.exists(path):
            g.rm(path)
            g.sync()


def prepare_source_retirement(g):
    """Prove old copied sources by their original marker-bound digest."""
    from baseline_fixtures import regular, write_record
    recover_source_staging(g)
    paths = tuple(prepare_vm.FIXTURE_SOURCE_FILES)
    if g.exists(SOURCE_RETIREMENT) or g.is_symlink(SOURCE_RETIREMENT):
        regular(g, SOURCE_RETIREMENT, 0, 0, 0o600)
        plan = json.loads(g.read_file(SOURCE_RETIREMENT))
        require(type(plan) is dict and set(plan) == {'purpose', 'files'}
                and plan['purpose'] == 'onpc-preparation-source-retirement-v1'
                and type(plan['files']) is dict and set(plan['files']) == set(paths),
                'guest:source-retirement-record')
    else:
        present = [path for path in paths if g.exists(STAGE + '/checkout/' + path)
                   or g.is_symlink(STAGE + '/checkout/' + path)]
        if not present:
            return
        marker_path = str(prepare_vm.MARKER)
        regular(g, marker_path, 0, 0, 0o600)
        marker = json.loads(g.read_file(marker_path))
        require(prepare_vm.fixture_boundary(marker) == 'legacy', 'guest:source-retirement-marker')
        for relative in prepare_vm.LEGACY_SCRIPT_FILES:
            path = STAGE + '/checkout/' + relative
            directory(g, str(Path(path).parent))
            regular(g, path, 0, 0, 0o600)
        actual = prepare_vm.preparation_source_digest(
            lambda relative: g.read_file(STAGE + '/checkout/' + relative),
            prepare_vm.LEGACY_SCRIPT_FILES)
        require(actual == marker['preparation_script_sha256'], 'guest:source-retirement-digest')
        plan = {'purpose': 'onpc-preparation-source-retirement-v1',
                'files': {relative: g.checksum('sha256', STAGE + '/checkout/' + relative)
                          for relative in paths}}
        write_record(g, plan, SOURCE_RETIREMENT)
    for relative, digest in plan['files'].items():
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest) is not None,
                'guest:source-retirement-record')
        path = STAGE + '/checkout/' + relative
        if g.exists(path) or g.is_symlink(path):
            directory(g, str(Path(path).parent))
            regular(g, path, 0, 0, 0o600)
            require(g.checksum('sha256', path) == digest, 'guest:source-retirement-substituted')
    for relative in plan['files']:
        path = STAGE + '/checkout/' + relative
        if g.exists(path):
            g.rm(path)
            g.sync()


def verify_clean_sources(g):
    """No movable source bytes survive capture; avatar and recovery data stay."""
    paths = (*prepare_vm.FIXTURE_SOURCE_FILES,
             'common/oh_no_parent_control_ui/gtk_automation.py')
    require(not any(g.exists(STAGE + '/checkout/' + relative)
                    or g.is_symlink(STAGE + '/checkout/' + relative) for relative in paths),
            'guest:fixture-source-retained')
    # Previous app preparations archive their input tree by a fixed rename.
    # Those trees have no per-member deletion ownership receipt. Audit them,
    # preserving and refusing any legacy source leak rather than sweeping them.
    roots = g.glob_expand('/var/tmp/onpc-system-input*')
    require(type(roots) is list and len(roots) <= 1024, 'guest:fixture-input-inventory')
    for root in roots:
        require(type(root) is str and re.fullmatch(
            r'/var/tmp/onpc-system-input(?:-snapshot-[0-9a-f]{32}-[0-9a-f]{32})?', root),
            'guest:fixture-input-inventory')
        info = g.lstatns(root)
        require(g.realpath(root) == root and stat.S_ISDIR(info['st_mode'])
                and info['st_uid'] == info['st_gid'] == 0 and not info['st_mode'] & 0o022,
                'guest:fixture-input-ownership')
        names = g.find(root)
        require(type(names) is list and len(names) <= 65536, 'guest:fixture-input-inventory')
        for name in names:
            require(type(name) is str and '\x00' not in name
                    and all(part not in ('', '.', '..') for part in name.removeprefix('/').split('/')),
                    'guest:fixture-input-inventory')
            relative = name.removeprefix('/')
            require(not any(relative == path or relative.endswith('/' + path)
                            for path in paths), 'guest:fixture-input-source-retained')
    # A product-free baseline has no installation attempt to retain. Even a
    # recognized archive may conceal packed fixture bytes; without a member
    # ownership receipt it must be preserved and refused before capture.
    require(not roots, 'guest:fixture-input-retained')


@observed('Preparing the baseline VM; waiting for guest setup and shutdown')
def prepare(capture, guestfs, password, *, mode='manual'):
    """Operate only on the off, journal-bound source selected by the controller."""
    require(mode in ('auto', 'manual'), 'guest:preparation-mode')
    with mounted(guestfs, capture) as g:
        from baseline_console import reconcile as reconcile_console
        reconcile_console(g)
        directory(g, STAGE)
        require(g.lstatns(STAGE)['st_mode'] & 0o077 == 0, 'guest:preparation-private')
        os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
            g.read_file('/etc/os-release').decode()))
        if os_id == 'ubuntu':
            prepare_source_retirement(g)
            from baseline_fixtures import reconcile_clean
            marker = (json.loads(g.read_file(str(prepare_vm.MARKER)))
                      if g.exists(str(prepare_vm.MARKER)) else None)
            # Legacy retirement must precede new writers. A fresh guest has no
            # fixed accounts/native tools yet; its environment is reconciled
            # only after the guest setup below establishes those dependencies.
            if marker and prepare_vm.fixture_boundary(marker) == 'legacy':
                reconcile_clean(g, marker['preparation_script_sha256'])
        files = set(prepare_vm.preparation_files(os_id)) | set(prepare_vm.REQUIRED_CHECKOUT_ENTRIES)
        files.update({'tests/integration/baseline_guest_entry.py',
                      'tests/integration/test_account_password.py'})
        files.update(str(Path(account.icon_file).relative_to(prepare_vm.CHECKOUT))
                     for account in prepare_vm.IDENTITIES)
        if os_id == 'ubuntu':
            from baseline_fixtures import write_record
            stage = {'purpose': 'onpc-preparation-source-staging-v1', 'pending': None,
                     'files': {relative: hashlib.sha256(
                         (prepare_vm.CHECKOUT / relative).read_bytes()).hexdigest()
                               for relative in STAGED_MOVABLE_SOURCES}}
            write_record(g, stage, SOURCE_STAGING)
        for relative in sorted(files):
            if os_id == 'ubuntu' and relative in stage['files']:
                stage['pending'] = relative
                write_record(g, stage, SOURCE_STAGING)
            write(g, STAGE + '/checkout/' + relative,
                  (prepare_vm.CHECKOUT / relative).read_bytes())
            if os_id == 'ubuntu' and relative in stage['files']:
                require(g.checksum('sha256', STAGE + '/checkout/' + relative) == stage['files'][relative],
                        'guest:preparation-source-changed')
                stage['pending'] = None
                write_record(g, stage, SOURCE_STAGING)
        for name in ('success', 'reboot-required'):
            if g.exists(STAGE + '/' + name) or g.is_symlink(STAGE + '/' + name):
                write(g, STAGE + '/' + name, b'')
        write(g, STAGE + '/password', password.encode('ascii'))
        write(g, STAGE + '/mode', mode.encode('ascii'))
        service = SERVICE.replace('baseline_guest_entry.py\n',
            'baseline_guest_entry.py --vm ' + prepare_vm.vm_config.selected().name + '\n')
        write(g, UNIT, service.encode('ascii'))
        directory(g, str(Path(LINK).parent))
        if g.exists(LINK) or g.is_symlink(LINK):
            require(g.is_symlink(LINK) and g.readlink(LINK) == UNIT,
                    'guest:preparation-unit')
        else:
            g.ln_s(UNIT, LINK)
        label_preparation(g)
    from watch_activity import operation
    with operation('Running no-app setup and guest system updates' if mode == 'auto'
                   else 'Running no-app prerequisite setup'):
        boot_and_wait(capture)
    with mounted(guestfs, capture) as g:
        reboot = g.exists(STAGE + '/reboot-required') and bool(g.read_file(STAGE + '/reboot-required'))
        if reboot:
            require(mode == 'auto', 'guest:unexpected-reboot')
            # A full power cycle provides a fresh kernel and boot identity. The
            # second one-shot validates that identity before powering off again.
            reboot_service = service.replace('/password', '/reboot-required').replace(
                '\nTimeoutStartSec=', ' --verify-reboot\nTimeoutStartSec=')
            write(g, UNIT, reboot_service.encode('ascii'))
            label_preparation(g)
    if reboot:
        with operation('Rebooting the updated guest and verifying the new boot'):
            boot_and_wait(capture)
    with mounted(guestfs, capture) as g:
        success = g.exists(STAGE + '/success') and g.read_file(STAGE + '/success') == b'success\n'
        if not success:
            # Emit only fixed diagnostic tokens, never package output or secrets.
            require(False, 'guest:preparation-failed; diagnostics:' + preparation_failure(g))
        require(not g.exists(STAGE + '/password'), 'guest:preparation-secret-retained')
        hashes = [line.split(':') for line in g.read_file('/etc/shadow').decode('ascii').splitlines()]
        for account in prepare_vm.IDENTITIES:
            rows = [row for row in hashes if row[0] == account.username]
            require(len(rows) == 1 and len(rows[0]) == 9
                    and matches(password, rows[0][1]), 'guest:prepared-password-mismatch')
        require(g.is_symlink(LINK) and g.readlink(LINK) == UNIT, 'guest:preparation-unit')
        g.rm(LINK)
        g.rm(UNIT)
    if os_id == 'ubuntu':
        with mounted(guestfs, capture) as g:
            from baseline_fixtures import (
                verify_clean, reconcile_clean, reconcile_native_rules, verify_native_rules)
            reconcile_clean(g)
            reconcile_native_rules(g)
            recover_source_staging(g)
            verify_clean_sources(g)
            verify_clean(g)
            # The final native configuration is reconciled offline, after all
            # package work. A fresh boot lets the packaged daemon initialize
            # and load its own database before any snapshot can be accepted.
            write(g, STAGE + '/success', b'')
            native_service = service.replace('/password', '/mode').replace(
                '\nTimeoutStartSec=', ' --prepare-native\nTimeoutStartSec=')
            write(g, UNIT, native_service.encode('ascii'))
            g.ln_s(UNIT, LINK)
            label_preparation(g)
        with operation('Preparing and verifying the native service and trust database'):
            boot_and_wait(capture)
        with mounted(guestfs, capture) as g:
            if not (g.exists(STAGE + '/success') and
                    g.read_file(STAGE + '/success') == b'success\n'):
                require(False, 'guest:native-preparation-failed; diagnostics:' + preparation_failure(g))
            require(g.is_symlink(LINK) and g.readlink(LINK) == UNIT, 'guest:preparation-unit')
            g.rm(LINK)
            g.rm(UNIT)
            verify_clean_sources(g)
            verify_clean(g)
            verify_native_rules(g)
        return
    from baseline_fixtures import build_payload, reconcile
    with operation('Reconciling reusable baseline application fixtures'):
        payload = build_payload()
        with mounted(guestfs, capture) as g:
            declared = reconcile(g, payload)
            from baseline_fixtures import RECORD, TRUST_RECORD, TRUST_FILE, BACKEND_RECORD, BACKEND_CONFIG
            # Offline-created files and their enclosing fixture directories need
            # the distribution's standard contexts before enforcing SELinux boots.
            paths = sorted(set(declared) | {str(Path(path).parent) for path in declared})
            label_preparation(g, [RECORD, TRUST_RECORD, TRUST_FILE, BACKEND_RECORD, BACKEND_CONFIG, *paths])


def configure_clipboard(root):
    """Use the same clipboard-capable SPICE console for baseline and attempts."""
    devices = root.find('devices')
    for graphics in devices.findall("graphics[@type='spice']"):
        devices.remove(graphics)
    graphics = ET.Element('graphics', type='spice', autoport='yes')
    devices.insert(0, graphics)
    ET.SubElement(graphics, 'listen', type='none')
    ET.SubElement(graphics, 'clipboard', copypaste='yes')
    ET.SubElement(graphics, 'filetransfer', enable='no')
    for channel in devices.findall('channel'):
        target = channel.find('target')
        if target is not None and target.get('name') == 'com.redhat.spice.0':
            devices.remove(channel)
    channel = ET.SubElement(devices, 'channel', type='spicevmc')
    ET.SubElement(channel, 'target', type='virtio', name='com.redhat.spice.0')


def configure_cpu(root):
    """Accept memory-snapshot-compatible CPU settings during baseline setup."""
    cpu = root.find('cpu')
    if cpu is not None:
        if cpu.get('mode') == 'host-passthrough':
            cpu.set('migratable', 'on')
        for feature in cpu.findall("feature[@name='invtsc']"):
            cpu.remove(feature)
        ET.SubElement(cpu, 'feature', policy='disable', name='invtsc')


def configure_snapshot_memory(root):
    """Let virtio discard unused guest pages instead of saving stale RAM bytes."""
    balloon = root.find('devices/memballoon')
    if balloon is not None and balloon.get('model') in (
            'virtio', 'virtio-transitional', 'virtio-non-transitional'):
        balloon.set('freePageReporting', 'on')


def boot_and_wait(capture):
    capture.revalidate(off=True)
    source = capture.source
    # Baseline preparation explicitly maintains this guest's configuration.
    # Install the same output-only endpoint used by all later isolated leases;
    # it has no host listener and becomes part of the accepted baseline.
    from e2e_watch import DisplayAdapter, attach_display, configuration_digest, display_endpoint
    root = ET.fromstring(source.domain.XMLDesc(source.api.VIR_DOMAIN_XML_INACTIVE))
    configure_cpu(root)
    configure_snapshot_memory(root)
    configure_clipboard(root)
    display_endpoint(root)
    source.connection.defineXML(ET.tostring(root, encoding='unicode'))
    capture.revalidate(off=True)
    source.domain.create()
    instance = source.domain.ID()
    require(instance >= 0, 'guest:preparation-start')
    try:
        xml_digest = configuration_digest(source.domain.XMLDesc(0))
        def guard_display():
            capture.revalidate()
            require(source.domain.ID() == instance
                    and configuration_digest(source.domain.XMLDesc(0)) == xml_digest,
                    'guest:preparation-display-changed')
        attach_display(capture, DisplayAdapter(source, instance, guard_display,
                                              capture.state['operation']))
        deadline = time.monotonic() + 7500
        while not source.snapshot()[1]:
            require(source.domain.ID() == instance, 'guest:preparation-instance-changed')
            require(time.monotonic() < deadline, 'guest:preparation-timeout')
            time.sleep(2)
    except BaseException:
        # This initial setup may not have SSH yet. Its guest service owns
        # SuccessAction/FailureAction=poweroff; preserve the recorded instance
        # for recovery rather than injecting a power key on a host-side error.
        raise
    capture.revalidate(off=True)
