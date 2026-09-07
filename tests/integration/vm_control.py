#!/usr/bin/python3
"""Maintenance of the pinned test VM, serialized with installed/graphical tests.

Start creates a recorded isolated attempt. Stop restores its outer baseline.
Reboot/input never restore state within that attempt. No domain/XML/path input.
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

import system_runner as runner


def check_identity(source, expected):
    runner.require(source.connection.getURI() == 'qemu:///system' and
                   source.uuid == expected and source.domain.UUIDString() == expected and
                   source.domain.name() == 'ubuntu26.04', 'vm-control:identity-mismatch')


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


def resume(lease, *, stopping=False):
    """Only adopt this helper's exact recorded instance, never another controller."""
    base = runner.baseline
    lease.capture.directory_identity = lease.capture.private_directory()
    lock = lease.directory / '.lock'
    base.identity(lock, private=True, mode=0o600)
    lease.fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(lease.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise runner.Error('state:busy-controller') from error
    lease.commands.lock_fd = lease.fd
    lease.capture.state = lease.capture.read_state()
    runner.require(lease.capture.state['phase'] == 'finalized', 'baseline:not-finalized')
    owner_path = lease.directory / 'vm-control.json'
    for path in (owner_path, lease.journal):
        base.identity(path, private=True, mode=0o600)
    owner = base.parse_json(owner_path.read_bytes())
    state = base.parse_json(lease.journal.read_bytes())
    runner.require(isinstance(state, dict) and set(state) == {
        'schema_version', 'run', 'phase', 'domain_uuid', 'domain_id',
        'original_xml', 'baseline_sha256'} and state['schema_version'] == 1 and
        state['phase'] in (('running', 'cleanup-requested') if stopping else ('running',)) and isinstance(state['run'], str) and
        re.fullmatch(r'[0-9a-f]{32}', state['run']) and
        type(state['domain_id']) is int and state['domain_id'] >= 0 and
        state['domain_uuid'] == lease.source.uuid and
        state['baseline_sha256'] == hashlib.sha256(base.encode(lease.capture.state)).hexdigest(),
        'vm-control:journal-identity')
    expected = {key: state[key] for key in ('run', 'domain_uuid', 'baseline_sha256')}
    expected['snapshot_sha256'] = hashlib.sha256(lease.source.baseline().encode()).hexdigest()
    runner.require(owner == expected,
                   'vm-control:not-owned')
    current_id = lease.source.domain.ID()
    runner.require(not lease.source.domain.autostart() and
                   (current_id == state['domain_id'] or (stopping and current_id == -1)),
                   'vm-control:instance-replaced-or-off')
    lease.original_xml = state['original_xml']
    runner.require(base.domain_layout(lease.original_xml, lease.source.uuid) ==
                   lease.capture.state['source']['layout'], 'vm-control:original-layout')
    runner.isolated_xml(lease.original_xml, lease.source.uuid, state['run'], graphics_type='vnc')
    lease.state = state
    lease.view.original_shares = lease.capture.state['source']['layout']['source_shares']
    lease.view.run = state['run']
    lease.view.domain_id = state['domain_id']
    lease.snapshot_xml = lease.source.baseline()
    lease.guard()
    runner.require(lease.capture.verify_snapshot() == lease.capture.state['proof'], 'baseline:changed')
    lease.mutated = True


def operate(lease, action, keys):
    if action in ('start', 'reset'):
        lease.__enter__()
        # Don't shut down an existing manually started VM to claim ownership.
        if lease.source.domain.ID() != -1:
            lease.save('complete')  # No mutation occurred; do not strand the journal.
            raise runner.Error('vm-control:already-running')
        save_owner(lease)
        lease.prepare()
        if action == 'start':
            lease.start()
        else:
            lease.finish()
        return
    resume(lease, stopping=action == 'stop')
    lease.guard()
    if action == 'stop':
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
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('action', choices=('status', 'xml', 'start', 'stop', 'reset',
                                          'reboot', 'send-key', 'screenshot'))
    parser.add_argument('keys', nargs='*', type=int)
    args = parser.parse_args(argv)
    source = lease = connection = None
    try:
        runner.require(os.geteuid() == os.getegid() == 0 and
                       Path.cwd() == runner.ROOT == runner.baseline.guest_contract.CHECKOUT,
                       'vm-control:root-checkout-required')
        runner.require(re.fullmatch(r'[0-9a-f-]{36}', args.expected_uuid) and
                       ((args.action == 'send-key' and 1 <= len(args.keys) <= 16 and
                         all(1 <= key <= 255 for key in args.keys)) or
                        (args.action != 'send-key' and not args.keys)), 'vm-control:arguments')
        os.umask(0o077)
        api = importlib.import_module('libvirt')
        if args.action in ('status', 'xml'):
            connection = api.openReadOnly('qemu:///system')
            domain = connection.lookupByUUIDString(args.expected_uuid)
            runner.require(connection.getURI() == 'qemu:///system' and
                           domain.UUIDString() == args.expected_uuid and
                           domain.name() == 'ubuntu26.04', 'vm-control:identity-mismatch')
            print(domain.XMLDesc(0) if args.action == 'xml' else
                  json.dumps({'state': domain.state()[0], 'id': domain.ID(),
                              'scope': 'pinned-test-vm'}))
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
        commands.directory = Path(tempfile.mkdtemp(prefix='onpc-vm-control-', dir='/tmp'))
        lease = runner.Lease(source, commands,
                             lambda disk, digest: runner.baseline.inspect_guest(guestfs, disk, digest),
                             graphics_type='vnc')
        print('vm-control: validated operation starting', file=sys.stderr, flush=True)
        operate(lease, args.action, args.keys)
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
