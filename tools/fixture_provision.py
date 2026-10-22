"""Attempt-owned, one-shot fixture transactions over the guarded SSH boundary.

No runner dispatch is enabled here. Target qualification and fixture-free
snapshot migration must precede callers. The VM lease remains the sole recovery
owner; an uncertain operation is never retried, undone or resumed.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import inspect
import io
import json
import os
from pathlib import PurePosixPath
import re
import tarfile
import threading

from tools import fixture_execution, fixture_manifest, test_storage

DISPATCH = 'UNAVAILABLE'
HEX = re.compile(r'[0-9a-f]{64}')
BOOT_SHA256_PROBE = '''import hashlib,pathlib,re
value=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text()
assert re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\n',value)
print(hashlib.sha256(value.encode()).hexdigest())
'''


def require(value, reason):
    if not value:
        raise ValueError('fixture-provision:' + reason)


def digest(value):
    return hashlib.sha256(fixture_manifest._canonical(value)).hexdigest()


def authenticated_bundle(selection):
    """Read the frozen selection and payload within one authenticated handoff.

    The original journal retains cleanup ownership and its locks cover every
    byte copied into memory. No caller-owned path is reopened after the handoff.
    """
    selection = fixture_execution.Selection.from_record(
        selection.record() if isinstance(selection, fixture_execution.Selection) else selection)
    with test_storage.authenticated_input(selection.record(), root=test_storage.ROOT) as allocation:
        manifest = fixture_execution._read_bundle(allocation, selection.target)
        require(manifest['build_identity'] == selection.build_identity, 'input-build')
        inputs = manifest['inputs']
        require(fixture_execution.input_key(inputs['source'], inputs['toolchain']['environment'],
                                           selection.target) == selection.key, 'input-key')
        fd = os.open('native-runtime', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                     dir_fd=allocation)
        try:
            raw = fixture_manifest._read(fd, 'fixture-manifest.json', fixture_manifest.MAX_MANIFEST)
            archive = fixture_manifest._read(fd, 'payload.tar', fixture_manifest.MAX_TOTAL +
                                            len(manifest['members']) * 1024 + 10240)
            require(fixture_manifest._verify(fd, selection.target, True) == manifest,
                    'input-changed')
            marker = fixture_manifest._decode(fixture_manifest._read(fd, 'complete.json', 1024))
            require(marker['content_identity'] == hashlib.sha256(raw + archive).hexdigest(),
                    'input-content')
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as stream:
                payloads = {item.name: stream.extractfile(item).read() for item in stream}
            require(fixture_execution._read_bundle(allocation, selection.target) == manifest,
                    'input-changed')
        finally:
            os.close(fd)
    return {'manifest': manifest, 'payloads': payloads,
            'content_identity': marker['content_identity']}


@dataclass(frozen=True)
class Readiness:
    """Diagnostic receipt; only its live lease generation authorizes use."""
    binding: dict
    files: dict


def _new_state():
    return {'failed': False, 'receipt': None, 'request': None,
            'selection': None, 'lock': threading.Lock()}


def reset_after_restore(lease):
    """Retire a generation only at the existing VM owner's off restore boundary.

    Future runner integrations call this between owned restore/finish and the
    next prepare. Reboot, a changed attempt ID and a new facade grant no reset.
    Old facades and receipts remain terminal even after a new generation starts.
    """
    old = getattr(lease, '_fixture_provision_state', None)
    require(old is not None and old['lock'].acquire(blocking=False), 'reset-busy')
    try:
        require(lease.fd is not None and (lease.state['phase'] == 'complete' or
                lease.state['phase'] == 'isolated' and getattr(lease, '_restored', False) is True),
                'reset-without-restoration')
        lease.guard(off=True)
        require(lease.view.domain_id is None and lease.view.snapshot()[1] is True,
                'reset-running-instance')
        old['failed'], old['receipt'] = True, None
        lease._fixture_provision_state = _new_state()
    finally:
        old['lock'].release()


def accepted_accounts(accounts):
    require(type(accounts) is dict and set(accounts) == {'system', 'parent', 'child', 'other'},
            'accounts')
    for role, account in accounts.items():
        require(type(account) is dict and set(account) == {'uid', 'gid', 'home'}
                and type(account['uid']) is int and type(account['gid']) is int
                and 0 <= account['gid'] < 2 ** 32 and type(account['home']) is str,
                'accounts')
        if role == 'system':
            require(account == {'uid': 0, 'gid': 0, 'home': '/root'}, 'system-account')
        else:
            home = PurePosixPath(account['home'])
            require(1000 <= account['uid'] < 2 ** 32 and home.parent == PurePosixPath('/home')
                    and home.name not in ('', '.', '..') and str(home) == account['home'],
                    'account-home')
    ordinary = [accounts[role] for role in ('parent', 'child', 'other')]
    require(len({item['uid'] for item in ordinary}) == 3
            and len({item['home'] for item in ordinary}) == 3, 'account-alias')
    return accounts


class SSHBoundary:
    """Ship reviewed helper code as private input through Transport.call.

    No SSH invocation, retry loop, observer or guest command channel is added.
    Importing this module does not enable a runner or qualification selector.
    """
    def __init__(self, transport):
        self.transport = transport

    def call(self, action, request, payloads=None):
        from tests.e2e import guest_files
        from tests.fixtures import (fixture_guest, native_assets, native_trust,
                                    baseline_assets, build_test_applications)
        # The helper imports these shared finite declarations/primitives. Install
        # modules in memory, keeping source and build tools off the guest disk.
        modules = [(name, inspect.getsource(module)) for name, module in (
            ('guest_files', guest_files), ('native_assets', native_assets))]
        # Ship only movable placement declarations, without importing the
        # persistent environment settings or changing checkout import routes.
        placement = ('from pathlib import Path\nfrom native_assets import ('
            'ASSETS,GUI_FILES,PREFIX,TRUSTED_NATIVE,ACTIVITY_PREFIX,ACTIVITY_EXECUTABLE,'
            'trusted_file_modes,desktop_entry,desktop_id,legacy_executable_paths)\n')
        for name in ('MECHANICAL', 'NATIVE', 'CATALOG_PREFIX', 'CATALOG_ENTRIES'):
            placement += name + '=' + repr(getattr(baseline_assets, name)) + '\n'
        for name in ('native_files', 'catalogue_files'):
            placement += inspect.getsource(getattr(baseline_assets, name)) + '\n'
        modules.extend((('baseline_assets', placement), ('native_trust', inspect.getsource(native_trust))))
        finite = ('import hashlib\nfrom pathlib import Path\nfrom types import SimpleNamespace\nimport native_assets,baseline_assets\n'
                  + 'SUBSETS=' + repr(fixture_manifest.SUBSETS) + '\n'
                  + 'ABSENCES=' + repr(fixture_manifest.ABSENCES) + '\n')
        for name in ('_fail', '_digest', 'declarations', 'select'):
            finite += inspect.getsource(getattr(fixture_manifest, name)) + '\n'
        modules.append(('fixture_manifest', finite))
        process = ('from __future__ import annotations\n'
                   'import os,pwd,select,signal,subprocess,sys\nfrom pathlib import Path\n'
                   'READY_MARKER="ONPC_TEST_APPLICATION_READY"\n')
        for name in ('FixtureError', '_log', '_preexec_for_uid', 'launch_native',
                     '_read_readiness', 'terminate'):
            process += inspect.getsource(getattr(build_test_applications, name)) + '\n'
        modules.extend((('fixture_process', process), ('fixture_guest', inspect.getsource(fixture_guest))))
        program = ('import json,sys,types,base64\n'
                   'r=json.load(sys.stdin)\n'
                   'for name,source in r.pop("modules"):\n'
                   ' m=types.ModuleType(name);sys.modules[name]=m;exec(source,m.__dict__)\n'
                   'p=r.pop("payloads")\n'
                   'p=None if p is None else {k:base64.b64decode(v,validate=True) for k,v in p.items()}\n'
                   'print(json.dumps(sys.modules["fixture_guest"].default_guest().call('
                   'r["action"],r["request"],p),sort_keys=True))\n')
        wire = {'modules': modules, 'action': action, 'request': request,
                'payloads': None if payloads is None else
                {key: base64.b64encode(data).decode('ascii') for key, data in payloads.items()}}
        raw = self.transport.call(['/usr/bin/python3', '-I', '-c', program],
                                  input=json.dumps(wire).encode(), timeout=300, attempts=1)
        require(type(raw) is bytes and len(raw) <= fixture_manifest.MAX_MANIFEST, 'reply')
        def pairs(items):
            result = {}
            for key, value in items:
                require(key not in result, 'duplicate-reply')
                result[key] = value
            return result
        return json.loads(raw, object_pairs_hook=pairs)


class Provisioner:
    def __init__(self, lease, transport, *, register_staging, boundary=None,
                 input_reader=authenticated_bundle):
        self.lease, self.transport = lease, transport
        self.boundary = boundary if boundary is not None else SSHBoundary(transport)
        self.register_staging, self.input_reader = register_staging, input_reader
        # The lease, rather than a disposable facade, owns both the terminal
        # latch and current receipt. Reconstructing a facade cannot replay an
        # uncertain mutation or keep an older facade's readiness alive.
        self._shared = lease.__dict__.setdefault('_fixture_provision_state', _new_state())

    @property
    def failed(self):
        return self._shared['failed']

    @failed.setter
    def failed(self, value):
        self._shared['failed'] = value

    @property
    def _receipt(self):
        return self._shared['receipt']

    @_receipt.setter
    def _receipt(self, value):
        self._shared['receipt'] = value

    @property
    def _request(self):
        return self._shared['request']

    @_request.setter
    def _request(self, value):
        self._shared['request'] = value

    @property
    def _selection(self):
        return self._shared['selection']

    @_selection.setter
    def _selection(self, value):
        self._shared['selection'] = value

    def _guard(self):
        require(not self.failed, 'terminal-attempt')
        state, config = self.lease.state, self.transport.config
        require(self.lease.fd is not None and state['phase'] == 'running'
                and state['domain_id'] is not None
                and all(state[key] == config[key] for key in ('domain_uuid', 'domain_id', 'run')),
                'lease')
        self.lease.guard()
        return state

    def _boot(self):
        self._guard()
        raw = self.transport.call(['/usr/bin/python3', '-c', BOOT_SHA256_PROBE],
                                  timeout=30, attempts=1)
        require(type(raw) is bytes and re.fullmatch(rb'[0-9a-f]{64}\n', raw), 'boot')
        self._guard()
        return raw.decode().strip()

    def _step(self, action, request, payloads=None):
        state = self._guard()
        binding = request['binding']
        require(state['domain_uuid'] == binding['vm_uuid'] and state['run'] == binding['run']
                and self._boot() == binding['boot_sha256'], 'stale-attempt')
        result = self.boundary.call(action, deepcopy(request), payloads)
        self._guard()
        require(self._boot() == binding['boot_sha256'], 'stale-boot')
        return result

    def _readback(self, request):
        result = self._step('readback', request)
        expected = {key: {name: member[name] for name in ('sha256', 'length', 'mode', 'uid', 'gid')}
                    for key, member in request['members'].items()}
        require(type(result) is dict and result == {'files': expected, 'native': True,
                                                   'labels': True}, 'readback')
        require(self._step('witness', request) == {'ready': True}, 'witness')
        return expected

    def wait_environment(self):
        """Observe native startup before an independent fixture-free audit."""
        acquired = self._shared['lock'].acquire(blocking=False)
        try:
            require(acquired, 'concurrent-provisioning')
            state = self._guard()
            request = {'binding': {'vm_uuid': state['domain_uuid'], 'run': state['run'],
                                   'boot_sha256': self._boot()}}
            result = self._step('inspect', request)
            require(type(result) is dict and set(result) == {'accounts', 'target'}, 'inspect')
            accepted_accounts(result['accounts'])
            return result
        except BaseException:
            self.failed, self._receipt = True, None
            raise
        finally:
            if acquired:
                self._shared['lock'].release()

    def provision(self, selection, subsets, *, attempt_id):
        """Preflight all members before mutation; any exception poisons this owner.

        register_staging records a guest path intent with the existing attempt
        owner *before* reservation or writes. Lost replies leave it for that
        owner's snapshot recovery. It must not introduce a separate journal.
        """
        acquired = self._shared['lock'].acquire(blocking=False)
        try:
            require(acquired, 'concurrent-provisioning')
            self._guard()
            require(type(attempt_id) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}',
                                                            attempt_id), 'attempt-id')
            declared = fixture_manifest.select(subsets)
            require(type(subsets) in (tuple, list), 'subsets')
            frozen_selection = deepcopy(selection.record() if hasattr(selection, 'record') else selection)
            loaded = self.input_reader(selection)
            manifest, payloads = loaded['manifest'], loaded['payloads']
            require(type(loaded['content_identity']) is str and
                    HEX.fullmatch(loaded['content_identity']), 'content-identity')
            # The authenticated reader validates the complete bundle. Check the
            # selected finite descriptors here too, including injected readers.
            require(set(manifest['members']) == set(fixture_manifest.declarations())
                    and manifest['absences'] == fixture_manifest.ABSENCES, 'manifest-membership')
            for key, declaration in declared.items():
                member = manifest['members'][key]
                require({name: member.get(name) for name in declaration if name != 'source'} ==
                        {name: value for name, value in declaration.items() if name != 'source'},
                        'member-declaration')
                require(type(payloads[key]) is bytes and 0 < len(payloads[key]) <= fixture_manifest.MAX_MEMBER
                        and len(payloads[key]) == member['length']
                        and hashlib.sha256(payloads[key]).hexdigest() == member['sha256'], 'member-bytes')
            state = self._guard()
            binding = {'vm_uuid': state['domain_uuid'], 'run': state['run'],
                       'boot_sha256': self._boot(), 'attempt_id': attempt_id,
                       'manifest_sha256': digest(manifest),
                       'content_identity': loaded['content_identity'], 'subsets': sorted(subsets)}
            if self._receipt is not None:
                require(binding == self._request['binding'] and frozen_selection == self._selection,
                        'changed-request')
                request = deepcopy(self._request)
                request['repeat'] = True
                inspected = self._step('inspect', request)
                require(accepted_accounts(inspected['accounts']) == request['accounts']
                        and inspected['target'] == manifest['inputs']['target'], 'changed-environment')
                require(self._step('preflight', request) == {'ok': True}, 'preflight')
                self._readback(request)
                return deepcopy(self._receipt)
            request = {'binding': binding, 'target': manifest['inputs']['target'],
                       'members': {}, 'absences': [], 'accounts': {},
                       'repeat': False,
                       'stage_identity': None, 'stage_files': None,
                       'staging': '/run/onpc-fixture-' + digest(binding)}
            inspected = self._step('inspect', request)
            accounts = accepted_accounts(inspected['accounts'])
            require(inspected['target'] == request['target'], 'incompatible-target')
            request['accounts'] = accounts
            for key in declared:
                member = deepcopy(manifest['members'][key])
                for role, account in accounts.items():
                    member['destination'] = member['destination'].replace('@' + role + '@', account['home'])
                path = PurePosixPath(member['destination'])
                require(path.is_absolute() and '..' not in path.parts and
                        str(path) == member['destination'] and '@' not in str(path), 'destination')
                owner = accounts[member['owner']]
                member.update(uid=owner['uid'], gid=owner['gid'])
                request['members'][key] = member
            request['absences'] = [item['destination'] for item in manifest['absences']
                                   if set(subsets).intersection(item['subsets'])]
            require(self._step('preflight', request) == {'ok': True}, 'preflight')
            self.register_staging(request['staging'])
            for action in ('reserve', 'stage', 'place', 'activate'):
                selected_payloads = {key: payloads[key] for key in declared} if action == 'stage' else None
                reply = self._step(action, request, selected_payloads)
                valid_identity = lambda value: (type(value) is list and len(value) == 2
                    and all(type(number) is int and number > 0 for number in value))
                if action == 'reserve':
                    require(type(reply) is dict and set(reply) == {'ok', 'identity'}
                            and reply['ok'] is True and valid_identity(reply['identity']), action)
                    request['stage_identity'] = reply['identity']
                elif action == 'stage':
                    require(type(reply) is dict and set(reply) == {'ok', 'identities'}
                            and reply['ok'] is True and type(reply['identities']) is dict
                            and set(reply['identities']) == set(declared)
                            and all(valid_identity(v) for v in reply['identities'].values()), action)
                    request['stage_files'] = reply['identities']
                else:
                    require(reply == {'ok': True}, action)
            files = self._readback(request)
            require(self._step('clean', request) == {'ok': True}, 'staging-cleanup')
            self._request, self._selection = deepcopy(request), frozen_selection
            self._receipt = Readiness(deepcopy(binding), deepcopy(files))
            return deepcopy(self._receipt)
        except BaseException:
            self.failed = True
            self._receipt = None
            raise
        finally:
            if acquired:
                self._shared['lock'].release()

    def require_ready(self, readiness):
        """Guard the public input boundary; imported/snapshot receipts cannot pass."""
        acquired = self._shared['lock'].acquire(blocking=False)
        try:
            require(acquired, 'concurrent-provisioning')
            self._guard()
            require(self._receipt is not None and readiness == self._receipt, 'readiness-required')
            require(self._boot() == readiness.binding['boot_sha256']
                    and self.lease.state['domain_uuid'] == readiness.binding['vm_uuid']
                    and self.lease.state['run'] == readiness.binding['run'], 'stale-readiness')
            return deepcopy(readiness)
        except BaseException:
            self.failed = True
            self._receipt = None
            raise
        finally:
            if acquired:
                self._shared['lock'].release()
