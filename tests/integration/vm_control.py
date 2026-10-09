#!/usr/bin/python3
"""Maintenance of the pinned test VM, serialized with installed/graphical tests.

Start creates a recorded isolated attempt. Stop restores its outer baseline.
Reboot/input never restore state within that attempt. No domain selector/XML/disk input.
"""

import argparse
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import uuid
import xml.etree.ElementTree as ET

import system_runner as runner
from watch_activity import operation


def renamed_xml(xml, old_name, new_name, expected_uuid, *, snapshot=False):
    """Change only names on the attested domain, including saved definitions."""
    runner.require('<!' not in xml, 'vm-control:rename-xml')
    root = ET.fromstring(xml)
    domains = [root] if not snapshot else root.findall('domain') + root.findall('inactiveDomain')
    runner.require(bool(domains), 'vm-control:rename-domain-missing')
    for domain in domains:
        runner.require(len(domain.findall('name')) == len(domain.findall('uuid')) == 1 and
                       domain.findtext('name') == old_name and
                       domain.findtext('uuid') == expected_uuid, 'vm-control:rename-identity')
        domain.find('name').text = new_name
    return ET.tostring(root, encoding='unicode')


def same_xml(left, right):
    return ET.canonicalize(left, strip_text=True) == ET.canonicalize(right, strip_text=True)


def acquire_idle(lease):
    """Acquire the existing maintenance locks and attest an idle, off guest."""
    base = runner.baseline
    lease.capture.directory_identity = lease.capture.private_directory()
    lease.compatibility_fd = base.compatibility_lock(lease.directory)
    lock = lease.capture.lock_path
    lease.fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    base.identity(lock, private=True, mode=0o600)
    try:
        fcntl.flock(lease.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise runner.Error('state:busy-controller') from error
    lease.commands.lock_fd = lease.fd
    lease.commands.compatibility_fd = lease.compatibility_fd
    lease.capture.state = lease.capture.read_state()
    runner.require(lease.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
    lease.capture.require_idle_attempt()
    lease.capture.revalidate(off=True)
    runner.require(lease.source.domain.ID() == -1 and not lease.source.domain.autostart(),
                   'vm-control:rename-requires-idle-off')
    lease.ownership_run = uuid.uuid4().hex
    lease.capture.begin_vm_ownership(lease)
    lease.capture.verify_snapshot(boundary='acquisition')


def rename(lease, new_name):
    """Rename an idle pinned guest and move its provenance under the same lease.

    The destination is a label, never a VM selector. Disk bytes and snapshot
    contents are untouched. Keep a durable rollback record before the first write.
    Guest preparation remains invalidated by subsequent configuration edits.
    """
    base = runner.baseline
    new_name = base.guest_contract.vm_config.validate_name(new_name)
    old_name = base.DOMAIN
    runner.require(new_name != old_name, 'vm-control:rename-same-name')
    old_directory = lease.directory
    destination = old_directory.parent / new_name
    with operation('VM maintenance: rename'):
        base.canonical(old_directory.parent)
        runner.require(not os.path.lexists(destination), 'vm-control:rename-state-exists')
        acquire_idle(lease)
        original_xml = lease.source.domain.XMLDesc(lease.source.api.VIR_DOMAIN_XML_INACTIVE)
        expected_xml = renamed_xml(original_xml, old_name, new_name, lease.source.uuid)
        snapshots = sorted((item.getName(), item.getXMLDesc(0))
                           for item in lease.source.domain.listAllSnapshots(0))
        for _, xml in snapshots:
            renamed_xml(xml, old_name, new_name, lease.source.uuid, snapshot=True)
        record = {'old_name': old_name, 'new_name': new_name, 'domain_uuid': lease.source.uuid,
                  'original_xml': original_xml, 'snapshots': snapshots, 'phase': 'requested'}
        journal_name = 'rename-' + lease.ownership_run + '.json'

        def save_record():
            runner.require(lease.capture.private_directory() == lease.capture.directory_identity,
                           'guard:directory-changed')
            fd, temporary = tempfile.mkstemp(prefix='.rename-', dir=lease.directory)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(base.encode(record))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, lease.directory / journal_name)
            base.sync_directory(lease.directory)

        save_record()
        moved = False
        try:
            lease.capture.revalidate(off=True)
            runner.require(lease.source.domain.XMLDesc(lease.source.api.VIR_DOMAIN_XML_INACTIVE) == original_xml and
                           sorted((item.getName(), item.getXMLDesc(0))
                                  for item in lease.source.domain.listAllSnapshots(0)) == snapshots,
                           'vm-control:rename-source-changed')
            lease.source.domain.rename(new_name, 0)
            base.DOMAIN = new_name
            # Refresh the handle by pinned UUID, never by the new display name.
            lease.source.domain = lease.source.connection.lookupByUUIDString(lease.source.uuid)
            runner.require(lease.source.domain.name() == new_name and lease.source.domain.ID() == -1 and
                           lease.source.domain.UUIDString() == lease.source.uuid and
                           same_xml(lease.source.domain.XMLDesc(lease.source.api.VIR_DOMAIN_XML_INACTIVE), expected_xml),
                           'vm-control:rename-result')
            # libvirt retains historical names inside snapshots and preserves
            # the current domain name on revert. Attest the unchanged metadata;
            # never delete/recreate snapshots to change those historical names.
            runner.require(sorted((item.getName(), item.getXMLDesc(0))
                                  for item in lease.source.domain.listAllSnapshots(0)) == snapshots,
                           'vm-control:rename-snapshot-changed')
            record['phase'] = 'renamed'
            save_record()
            lease.capture.verify_snapshot()
            runner.require(not os.path.lexists(destination), 'vm-control:rename-state-exists')
            os.rename(old_directory, destination)
            moved = True
            lease.directory = lease.capture.directory = destination
            lease.journal = destination / 'system-run.json'
            base.sync_directory(destination.parent)
            lease.capture.revalidate(off=True)
            record['phase'] = 'complete'
            save_record()
        except BaseException:
            # Roll back only this same, still-off UUID. Retain the requested
            # journal if any rollback check fails; never adopt a replacement.
            domain = lease.source.connection.lookupByUUIDString(lease.source.uuid)
            runner.require(domain.UUIDString() == lease.source.uuid and domain.ID() == -1 and
                           domain.name() in (old_name, new_name), 'vm-control:rename-rollback-identity')
            if domain.name() == new_name:
                domain.rename(old_name, 0)
            base.DOMAIN = old_name
            lease.source.domain = lease.source.connection.lookupByUUIDString(lease.source.uuid)
            if moved:
                runner.require(not os.path.lexists(old_directory), 'vm-control:rename-rollback-state-exists')
                os.rename(destination, old_directory)
                lease.directory = lease.capture.directory = old_directory
                lease.journal = old_directory / 'system-run.json'
                base.sync_directory(old_directory.parent)
            runner.require(same_xml(lease.source.domain.XMLDesc(lease.source.api.VIR_DOMAIN_XML_INACTIVE), original_xml),
                           'vm-control:rename-rollback-result')
            lease.capture.verify_snapshot()
            record['phase'] = 'rolled-back'
            save_record()
            raise


def check_identity(source, expected):
    runner.require(source.connection.getURI() == 'qemu:///system' and
                   source.uuid == expected and source.domain.UUIDString() == expected and
                   source.domain.name() == runner.baseline.DOMAIN, 'vm-control:identity-mismatch')


def save_owner(lease):
    path = lease.directory / 'vm-control.json'
    data = {'run': lease.state['run'], 'domain_uuid': lease.source.uuid,
            'baseline_sha256': lease.state['baseline_sha256'],
            'snapshot_sha256': hashlib.sha256(lease.source.baseline().encode()).hexdigest()}
    # Persist before the first mutation; retain on all failures for diagnosis.
    fd, temporary = tempfile.mkstemp(prefix='.vm-control-', dir=lease.directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(runner.baseline.encode(data))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    runner.baseline.sync_directory(lease.directory)


def resume(lease, *, stopping=False, recovery_instance=None):
    """Only adopt this helper's exact recorded instance, never another controller."""
    base = runner.baseline
    lease.capture.directory_identity = lease.capture.private_directory()
    lease.compatibility_fd = base.compatibility_lock(lease.directory)
    lock = lease.capture.lock_path
    lease.fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    base.identity(lock, private=True, mode=0o600)
    try:
        fcntl.flock(lease.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise runner.Error('state:busy-controller') from error
    lease.commands.lock_fd = lease.fd
    lease.commands.compatibility_fd = lease.compatibility_fd
    lease.capture.state = lease.capture.read_state()
    runner.require(lease.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
    owner_path = lease.directory / 'vm-control.json'
    for path in (owner_path, lease.journal):
        base.identity(path, private=True, mode=0o600)
    owner = base.parse_json(owner_path.read_bytes())
    state = base.parse_json(lease.journal.read_bytes())
    prestart = ('validated', 'shutdown-requested', 'restore-requested', 'isolated', 'start-requested')
    interrupted_off = (stopping and isinstance(state, dict) and
                       state.get('phase') in (*prestart, 'cleanup-requested') and
                       state.get('domain_id') is None)
    runner.require(isinstance(state, dict) and set(state) == {
        'schema_version', 'run', 'phase', 'domain_uuid', 'domain_id',
        'original_xml', 'baseline_sha256'} and state['schema_version'] == 1 and
        state['phase'] in (('start-requested',) if recovery_instance is not None else
                          ('running', 'cleanup-requested', *prestart) if stopping else ('running',)) and isinstance(state['run'], str) and
        re.fullmatch(r'[0-9a-f]{32}', state['run']) and
        ((state['domain_id'] is None) if recovery_instance is not None else
         (interrupted_off or (type(state['domain_id']) is int and state['domain_id'] >= 0))) and
        state['domain_uuid'] == lease.source.uuid and
        state['baseline_sha256'] == base.baseline_sha256(lease.capture.state, lease.directory),
        'vm-control:journal-identity')
    expected = {key: state[key] for key in ('run', 'domain_uuid', 'baseline_sha256')}
    expected['snapshot_sha256'] = hashlib.sha256(lease.source.baseline().encode()).hexdigest()
    runner.require(owner == expected,
                   'vm-control:not-owned')
    current_id = lease.source.domain.ID()
    runner.require(not lease.source.domain.autostart() and
                   (current_id == recovery_instance if recovery_instance is not None else
                    current_id == -1 if interrupted_off else
                    current_id == state['domain_id'] or (stopping and current_id == -1)),
                   'vm-control:instance-replaced-or-off')
    lease.original_xml = state['original_xml']
    runner.require(base.domain_layout(lease.original_xml, lease.source.uuid) ==
                   base.recorded_layout(lease.capture.state['source']['layout']), 'vm-control:original-layout')
    runner.isolated_xml(lease.original_xml, lease.source.uuid, state['run'], graphics_type='vnc')
    lease.state = state
    lease.view.run = state['run']
    lease.view.domain_id = state['domain_id']
    lease.snapshot_xml = lease.source.baseline()
    restored_off = False
    if stopping and current_id == -1:
        active = lease.source.domain.XMLDesc(0)
        runner.require(active == lease.source.domain.XMLDesc(lease.source.api.VIR_DOMAIN_XML_INACTIVE),
                       'vm-control:off-configuration-changed')
        if active == lease.original_xml:
            lease.view.run = None
            lease.view.domain_id = None
            restored_off = True
        elif ET.fromstring(active).findtext('description') != runner.TAG + state['run']:
            # An online memory restore can finish before its fresh run tag is
            # written. Its private saved record and isolation proof still bind
            # the exact off guest; UUID alone never authorizes recovery.
            runner.require(state['phase'] in ('start-requested', 'cleanup-requested'),
                           'vm-control:off-run-identity')
            from online_snapshot import recover_identity
            lease.view.run = recover_identity(lease)
    if recovery_instance is not None:
        # Check the caller's observed instance against the private snapshot
        # proof. UUID alone cannot authorize recovery or normal start/resume.
        from online_snapshot import recover_identity
        run = recover_identity(lease)
        lease.view.run = run
        lease.view.domain_id = recovery_instance
    lease.guard(off=stopping and current_id == -1)
    runner.require(lease.capture.verify_snapshot() == lease.capture.state['proof'], 'baseline:changed')
    lease.mutated = True
    if recovery_instance is not None:
        lease.state['run'] = lease.view.run
        lease.state['domain_id'] = recovery_instance
        save_owner(lease)
        lease.save('running')
    return restored_off


def recover_preparation(lease):
    """Use ordinary owned stop, or exact saved-memory interrupted-start proof."""
    base = runner.baseline
    base.identity(lease.journal, private=True, mode=0o600)
    attempt = base.parse_json(lease.journal.read_bytes())
    instance = lease.source.domain.ID()
    if (isinstance(attempt, dict) and attempt.get('phase') == 'start-requested'
            and attempt.get('domain_id') is None and instance >= 0):
        # resume checks this observed ID again under the lease, together with
        # the exact owner, baseline, private snapshot record and isolation.
        operate(lease, 'recover-online', [instance])
    else:
        operate(lease, 'stop', [])


def operate(lease, action, keys):
    # All maintenance paths use the same intent scope as transport and leases.
    with operation('VM maintenance: ' + action):
        return _operate(lease, action, keys)


def _operate(lease, action, keys):
    if action in ('start', 'reset'):
        lease.__enter__()
        # Don't shut down an existing manually started VM to claim ownership.
        if lease.source.domain.ID() != -1:
            lease.save('complete')  # No mutation occurred; do not strand the journal.
            raise runner.Error('vm-control:already-running')
        save_owner(lease)
        lease.prepare()
        if action == 'start':
            lease.watch_detached = True
            lease.start()
        else:
            lease.finish()
        return
    restored_off = resume(lease, stopping=action == 'stop',
                          recovery_instance=keys[0] if action == 'recover-online' else None)
    lease.guard(off=restored_off)
    if action == 'recover-online':
        lease.stop_by_restore()
        lease.finish()
    elif action == 'stop':
        if restored_off:
            # The recorded instance is gone and its original configuration is
            # already restored. Audit the guest before clearing the journal;
            # no shutdown, snapshot revert or domain definition is authorized.
            runner.require(lease.inspect(Path(lease.capture.state['source']['layout']['disk']),
                lease.capture.state['script_digest']) == lease.capture.state['guest'],
                'recovery:guest-changed')
            lease.guard(off=True)
            runner.require(lease.source.domain.ID() == -1 and
                lease.source.domain.XMLDesc(0) == lease.original_xml and
                lease.source.domain.XMLDesc(lease.source.api.VIR_DOMAIN_XML_INACTIVE) ==
                lease.original_xml, 'vm-control:off-configuration-changed')
            lease.save('complete')
        else:
            lease.finish()
    elif action == 'reboot':
        lease.source.domain.reboot(lease.source.api.VIR_DOMAIN_REBOOT_ACPI_POWER_BTN)
        lease.guard()
    elif action == 'send-key':
        lease.source.domain.sendKey(lease.source.api.VIR_KEYCODE_SET_LINUX, 100, keys, len(keys), 0)
        lease.guard()
    elif action == 'screenshot':
        directory = Path(tempfile.mkdtemp(prefix='onpc-vm-screen-', dir='/tmp'))
        stream = lease.source.connection.newStream(0)
        try:
            mime = lease.source.domain.screenshot(stream, 0, 0)
            runner.require(mime in ('image/png', 'image/x-portable-pixmap'), 'vm-control:image-format')
            path = directory / ('screen.png' if mime == 'image/png' else 'screen.ppm')
            with path.open('xb') as output:
                def receive(_stream, data, _opaque):
                    output.write(data)
                    return 0
                stream.recvAll(receive, None)
            stream.finish()
            lease.guard()
            print(json.dumps({'screenshot': str(path)}))
        except BaseException:
            stream.abort()
            raise
    else:
        raise runner.Error('vm-control:invalid-operation')


def main(argv=None):
    argv, _ = runner.baseline.guest_contract.vm_config.extract(sys.argv[1:] if argv is None else argv)
    probe = None
    if argv[2:3] == ['exec'] and argv[:1] == ['--expected-uuid']:
        boundary = 2
        # The dispatcher supplies only the fixed UUID prefix before exec.
        probe = runner.baseline.guest_contract.vm_config.guest_command_arguments(argv[boundary + 1:])
        argv = argv[:boundary] + ['exec']
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help='required configured VM name or ID (validated before parsing)')
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('action', choices=('status', 'xml', 'snapshots', 'start', 'stop', 'reset',
                                          'reboot', 'send-key', 'screenshot', 'recover-online', 'rename', 'rename-disk', 'exec',
                                          'reproduce-gdm-denial', 'reproduce-lock-denial',
                                          'reproduce-retained-entry', 'probe-lock-curtain',
                                          'reproduce-retained-focus', 'probe-retained-focus-resync'))
    parser.add_argument('keys', nargs='*', type=int)
    parser.add_argument('--new-name')
    args = parser.parse_args(argv)
    source = lease = connection = None
    try:
        runner.require(os.geteuid() == os.getegid() == 0 and
                       Path.cwd() == runner.ROOT == runner.baseline.guest_contract.CHECKOUT,
                       'vm-control:root-checkout-required')
        runner.require(re.fullmatch(r'[0-9a-f-]{36}', args.expected_uuid) and
                       ((args.action == 'send-key' and 1 <= len(args.keys) <= 16 and
                         all(1 <= key <= 255 for key in args.keys)) or
                        (args.action == 'recover-online' and len(args.keys) == 1 and args.keys[0] > 0) or
                        (args.action not in ('send-key', 'recover-online') and not args.keys)), 'vm-control:arguments')
        runner.require((args.action == 'rename') == (args.new_name is not None), 'vm-control:arguments')
        runner.require(args.action != 'exec' or probe is not None, 'vm-control:arguments')
        if args.new_name is not None:
            runner.baseline.guest_contract.vm_config.validate_name(args.new_name)
        os.umask(0o077)
        from watch_activity import event
        event('Maintenance: ' + args.action)
        api = importlib.import_module('libvirt')
        if args.action in ('status', 'xml', 'snapshots'):
            with operation('VM maintenance: ' + args.action):
                connection = api.openReadOnly('qemu:///system')
                domain = connection.lookupByUUIDString(args.expected_uuid)
                runner.require(connection.getURI() == 'qemu:///system' and
                               domain.UUIDString() == args.expected_uuid and
                               domain.name() == runner.baseline.DOMAIN, 'vm-control:identity-mismatch')
                print(json.dumps([{'name': item.getName(), 'xml': item.getXMLDesc(0)}
                                  for item in domain.listAllSnapshots(0)])
                      if args.action == 'snapshots' else domain.XMLDesc(0) if args.action == 'xml' else
                      json.dumps({'state': domain.state()[0], 'id': domain.ID(),
                                  'scope': 'pinned-test-vm'}))
            event('Maintenance: ' + args.action + ' complete')
            return 0
        api.virEventRegisterDefaultImpl()
        def events():
            while True:
                api.virEventRunDefaultImpl()
        threading.Thread(target=events, daemon=True).start()
        guestfs = importlib.import_module('guestfs')
        source = runner.baseline.LibvirtSource(api)
        check_identity(source, args.expected_uuid)
        commands = runner.Commands()
        from tools.test_storage import scratch_directory
        commands.directory = Path(tempfile.mkdtemp(prefix='onpc-vm-control-', dir=scratch_directory()))
        lease = runner.Lease(source, commands,
                             lambda disk, digest: runner.baseline.inspect_guest(guestfs, disk, digest),
                             graphics_type='vnc')
        print('vm-control: validated operation starting', file=sys.stderr, flush=True)
        if args.action == 'rename':
            rename(lease, args.new_name)
        elif args.action == 'rename-disk':
            from vm_disk_rename import rename_disk
            rename_disk(lease)
        elif args.action in ('reproduce-gdm-denial', 'reproduce-lock-denial', 'reproduce-retained-entry',
                            'reproduce-retained-focus'):
            from vm_probe import (reproduce_gdm_denial, reproduce_lock_denial, reproduce_retained_entry,
                                  reproduce_retained_focus)
            resume(lease)
            {'reproduce-gdm-denial': reproduce_gdm_denial,
             'reproduce-lock-denial': reproduce_lock_denial,
             'reproduce-retained-entry': reproduce_retained_entry,
             'reproduce-retained-focus': reproduce_retained_focus}[args.action](lease)
        elif args.action == 'exec':
            from vm_probe import execute
            with operation('Probing the owned guest as root'):
                resume(lease)
                status = (execute(lease, probe[1], probe[0], input_stream=True)
                          if probe[2] else execute(lease, probe[1], probe[0]))
                event('Maintenance: exec complete')
                return status
        elif args.action == 'probe-lock-curtain':
            from vm_probe import probe_lock_curtain
            resume(lease)
            probe_lock_curtain(lease)
        elif args.action == 'probe-retained-focus-resync':
            from vm_probe import probe_retained_focus_resync
            resume(lease)
            probe_retained_focus_resync(lease)
        else:
            operate(lease, args.action, args.keys)
        event('Maintenance: ' + args.action + ' complete')
        print('vm-control: operation complete', file=sys.stderr, flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Category and exception class explain failures without libvirt output,
        # account names, key sequences, domain XML or filesystem paths.
        print(f'vm-control: {runner.error_category(error)} ({type(error).__name__}); '
              'preserve controller state for diagnosis', file=sys.stderr)
        return 2
    finally:
        if lease is not None:
            lease.release()
        if source is not None:
            source.close()
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    sys.exit(main())
