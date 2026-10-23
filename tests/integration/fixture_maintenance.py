"""Fixture refresh in a dedicated baseline-only maintenance attempt.

The existing controller lock excludes other launchers. Baseline provenance and
the refusal of arbitrary guest actions exclude fixture workers; logind excludes
fixture-using sessions. This is not a process scanner or same-boot recovery API.
"""

from copy import deepcopy
import inspect
import json
import os
import re
import tempfile

import system_runner as runner
from tools import fixture_execution, fixture_provision
from watch_activity import operation


SUBSETS = ('trusted-hard',)
NAME = 'fixture-maintenance.json'


def target_for(lease):
    guest = lease.capture.state['guest']
    _require(guest.get('fixture_boundary') == 'clean', 'clean-baseline-required')
    if guest.get('ubuntu_version') == '26.04':
        return 'ubuntu'
    _require(guest.get('os_id') == 'fedora' and guest.get('version') == '44',
             'target-not-qualified')
    return 'fedora'


def idle_sessions(sessions, own, *, allow_prior_ssh=False):
    """Accept only the greeter, its/root managers and this guarded SSH call."""
    if type(own) is not str or not own or type(sessions) is not list:
        return False
    if any(type(item) not in (tuple, list) or len(item) != 2
            or type(item[0]) is not str or type(item[1]) is not dict
            or type(item[1].get('User')) is not str
            or re.fullmatch(r'0|[1-9][0-9]*', item[1]['User']) is None for item in sessions):
        return False
    greeters = {props.get('User') for sid, props in sessions
        if props.get('Class') == 'greeter' and props.get('Service') == 'gdm-launch-environment'
        and props.get('Type') in ('x11', 'wayland') and props.get('Remote') == 'no'}
    for sid, props in sessions:
        greeter = (props.get('User') in greeters and props.get('Class') == 'greeter'
            and props.get('Service') == 'gdm-launch-environment'
            and props.get('Type') in ('x11', 'wayland') and props.get('Remote') == 'no')
        manager = (props.get('Class') in ('manager', 'manager-early')
            and props.get('Service') == 'systemd-user' and props.get('Type') == 'unspecified'
            and props.get('Remote') == 'no' and props.get('User') in {'0', *greeters})
        ssh = (props.get('Class') == 'user' and props.get('User') == '0'
            and props.get('Service') == 'sshd' and props.get('Remote') == 'yes'
            and props.get('Type') == 'tty')
        current = ssh and (sid == own or allow_prior_ssh)
        if not (greeter or manager or current):
            return False
    return any(sid == own for sid, _ in sessions)


SESSION_PROBE = inspect.getsource(idle_sessions) + r'''
import json,os,re,subprocess,time
def call(*args):
 return subprocess.check_output(['/usr/bin/loginctl',*args],text=True,timeout=15)
deadline=time.monotonic()+5
while True:
 listed=json.loads(call('list-sessions','--json=short','--no-pager'));assert type(listed) is list
 sessions=[]
 for session in listed:
  sid=session['session'];assert type(sid) is str and re.fullmatch(r'[A-Za-z0-9_-]+',sid)
  props=dict(line.split('=',1) for line in call('show-session',sid,'--no-pager',
   '--property=Class','--property=Type','--property=Service','--property=User',
   '--property=Remote').splitlines())
  sessions.append((sid,props))
 if idle_sessions(sessions,os.environ.get('XDG_SESSION_ID')):
  print('{"idle":true}');break
 assert idle_sessions(sessions,os.environ.get('XDG_SESSION_ID'),allow_prior_ssh=True),'maintenance-session-not-owned'
 assert time.monotonic()<deadline,'maintenance-session-not-idle'
 time.sleep(0.1)
'''


def _require(value, reason):
    runner.require(value, 'fixture-maintenance:' + reason)


def _identity(lease):
    _require(lease.fd is not None and lease.state['phase'] == 'running'
             and type(lease.state['domain_id']) is int, 'exclusive-running-owner-required')
    lease.guard()
    return {key: lease.state[key] for key in
            ('run', 'domain_uuid', 'domain_id', 'baseline_sha256')}


def _save(lease, record):
    _require(lease.capture.private_directory() == lease.capture.directory_identity,
             'directory-changed')
    path = lease.directory / NAME
    if os.path.lexists(path):
        runner.baseline.identity(path, private=True, mode=0o600)
    fd, temporary = tempfile.mkstemp(prefix='.fixture-maintenance-', dir=lease.directory)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(runner.baseline.encode(record))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    runner.baseline.sync_directory(lease.directory)


def _load(lease):
    identity = _identity(lease)
    path = lease.directory / NAME
    runner.baseline.identity(path, private=True, mode=0o600)
    _require(path.stat().st_size <= 1024 * 1024, 'record-size')
    record = runner.baseline.parse_json(path.read_bytes())
    _require(type(record) is dict and set(record) == {
        'schema', 'owner', 'phase', 'boot_sha256', 'selection', 'binding', 'subsets',
        'retained', 'staging'} and record['schema'] == 1 and record['owner'] == identity
        and record['phase'] in ('idle', 'ready', 'pending', 'unavailable')
        and type(record['retained']) is list and type(record['staging']) is list,
        'unknown-owner')
    return record


def _boot(lease, transport):
    _identity(lease)
    raw = transport.call(['/usr/bin/python3', '-c', fixture_provision.BOOT_SHA256_PROBE],
                         timeout=30, attempts=1)
    _require(type(raw) is bytes and re.fullmatch(rb'[0-9a-f]{64}\n', raw), 'boot')
    _identity(lease)
    return raw.decode().strip()


def _idle(lease, transport, record):
    try:
        _require(record['owner'] == _identity(lease), 'owner-changed')
        _require(_boot(lease, transport) == record['boot_sha256'], 'boot-changed')
        reply = transport.call(['/usr/bin/python3', '-c', SESSION_PROBE], timeout=30, attempts=1)
        _require(reply == b'{"idle":true}\n', 'session-or-uncertain-activity')
        _identity(lease)
    except BaseException:
        # Once unknown guest activity is observed, later logout cannot prove
        # that it left no fixture worker behind. Only owned stop retires it.
        record['phase'] = 'unavailable'
        _save(lease, record)
        raise


def transport_for(lease):
    """Reuse this invocation's authenticated SSH files and guarded transport."""
    _identity(lease)
    transport = getattr(lease, '_fixture_maintenance_transport', None)
    if transport is None:
        from vm_probe import connect
        transport = connect(lease)
        lease._fixture_maintenance_transport = transport
    return transport


def initialize(lease, *, transport=None):
    """Attest only the just-restored, product-free baseline maintenance start."""
    target_for(lease)
    record = {'schema': 1, 'owner': _identity(lease), 'phase': 'unavailable',
              'boot_sha256': None, 'selection': None, 'binding': None,
              'subsets': list(SUBSETS), 'retained': [], 'staging': []}
    _save(lease, record)
    transport = transport_for(lease) if transport is None else transport
    lease._fixture_maintenance_transport = transport
    record['boot_sha256'] = _boot(lease, transport)
    _idle(lease, transport, record)
    record['phase'] = 'idle'
    _save(lease, record)


def invalidate(lease):
    """Arbitrary commands/input cannot subsequently claim baseline-only idleness."""
    path = lease.directory / NAME
    if not os.path.lexists(path):
        return
    runner.baseline.identity(path, private=True, mode=0o600)
    previous = runner.baseline.parse_json(path.read_bytes())
    # Completed historical maintenance never grants authority to a newer run.
    if type(previous) is dict and previous.get('owner') != _identity(lease):
        return
    record = _load(lease)
    record['phase'] = 'unavailable'
    _save(lease, record)


def cleanup(lease):
    """Retire this exact diagnostic owner only after ordinary off recovery."""
    path = lease.directory / NAME
    if not os.path.lexists(path):
        return
    _require(lease.state['phase'] == 'complete' and lease.source.domain.ID() == -1,
             'cleanup-before-owned-stop')
    lease.guard(off=True)
    pinned = runner.baseline.identity(path, private=True, mode=0o600)
    record = runner.baseline.parse_json(path.read_bytes())
    expected = {key: lease.state[key] for key in
                ('run', 'domain_uuid', 'domain_id', 'baseline_sha256')}
    _require(type(record) is dict and record.get('schema') == 1
             and record.get('owner') == expected, 'cleanup-owner')
    _require(runner.baseline.identity(path, private=True, mode=0o600) == pinned,
             'cleanup-replaced')
    path.unlink()
    runner.baseline.sync_directory(lease.directory)


def synchronize(lease, selection, *, subsets=SUBSETS, transport=None, boundary=None):
    """First place A, verify identical A, or explicitly replace retained A by B.

    Inputs stay owned by their original authenticated host journals. Persist all
    selected locators and staging intents until ordinary owned stop; interrupted
    operations can never reconstruct readiness in this boot.
    """
    with operation('Refreshing fixtures in the idle owned maintenance guest'):
        record = _load(lease)
        _require(record['phase'] in ('idle', 'ready'), 'unavailable-until-owned-stop')
        _require(type(subsets) in (list, tuple) and sorted(subsets) == record['subsets'],
                 'same-subset-required')
        selection = fixture_execution.Selection.from_record(
            selection.record() if hasattr(selection, 'record') else selection).record()
        _require(selection['target'] == target_for(lease), 'target')
        transport = transport_for(lease) if transport is None else transport
        _idle(lease, transport, record)
        # Authenticate B and retained A before invalidation or any guest write.
        fixture_provision.authenticated_bundle(selection)
        if record['selection'] is not None:
            fixture_provision.authenticated_bundle(record['selection'])
        for selected in (record['selection'], selection):
            if selected is not None and selected not in record['retained']:
                record['retained'].append(deepcopy(selected))
        _save(lease, record)

        active = False

        def owner(binding):
            current = _load(lease)
            _require(current == record and (current['phase'] == 'ready' or
                     (active and current['phase'] == 'pending')), 'owner-unavailable')
            _require(binding['run'] == record['owner']['run'] and
                     binding['vm_uuid'] == record['owner']['domain_uuid'] and
                     binding['boot_sha256'] == record['boot_sha256'], 'binding')
            _idle(lease, transport, record)
            return True

        def staging(path):
            _require(re.fullmatch(r'/run/onpc-fixture-[0-9a-f]{64}', path), 'staging')
            record['staging'].append(path)
            _save(lease, record)

        delegate = boundary if boundary is not None else fixture_provision.SSHBoundary(transport)

        class IdleBoundary:
            def call(self, action, request, payloads=None):
                owner(request['binding'])
                result = delegate.call(action, request, payloads)
                owner(request['binding'])
                return result

        controller = fixture_provision.Provisioner(lease, transport,
            register_staging=staging, boundary=IdleBoundary())
        try:
            # Reconstruction exercises an actual fixture witness too. Persist
            # uncertainty before it can launch anything, even on identical sync.
            record['phase'] = 'pending'
            _save(lease, record)
            active = True
            receipt = None
            if record['selection'] is not None:
                receipt = controller.resume_maintenance(record['selection'], subsets,
                    attempt_id=record['owner']['run'], expected_binding=record['binding'],
                    maintenance_owner=owner)
            if receipt is None:
                receipt = controller.provision(selection, subsets, attempt_id=record['owner']['run'])
            elif selection == record['selection']:
                receipt = controller.provision(selection, subsets, attempt_id=record['owner']['run'])
            else:
                receipt = controller.replace(selection, subsets, readiness=receipt,
                                             maintenance_owner=owner)
            controller.require_ready(receipt)
            _idle(lease, transport, record)
            record.update(selection=selection, binding=deepcopy(receipt.binding), phase='ready')
            _save(lease, record)
            return receipt
        except BaseException:
            record['phase'] = 'unavailable'
            _save(lease, record)
            raise
        finally:
            active = False
