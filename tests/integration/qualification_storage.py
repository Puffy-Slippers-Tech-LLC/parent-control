"""Give standalone graphical qualifications the same bounded retention as E2E."""

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import test_retention
from tools.runner_evidence import ReportEvidence, recover_pending
from owned_commands import observe_commands

_producer = ContextVar('qualification_evidence_producer', default=None)


def _proof_files(check):
    """Finite public proof names, never the worker's private namespace."""
    common = (('result.json', 'result'), ('results.xml', 'junit'),
              ('results.tap', 'tap'), ('producer-commands.jsonl', 'command'),
              ('input/artifact-manifest.json', 'input'), ('input/installed-files.json', 'input'),
              ('input/selected-inputs.json', 'input'), ('input/transfer-sha256.json', 'input'))
    diagnostics = {
        'reproduce_kiosk_refusal': (),
        'probe_kiosk_latency': (('timings.json', 'diagnostic'),),
        'probe_kiosk_prompt_latency': (('observed.json', 'diagnostic'),),
        'probe_kiosk_approval': (('observed.json', 'diagnostic'),
                                 ('native-log.json', 'diagnostic'),
                                 ('native-log-result.json', 'diagnostic')),
        'probe_revoke_balances': (('observed.json', 'diagnostic'),),
        'probe_retained_app_launch': (('observed.json', 'diagnostic'),),
        'probe_riley_native_grid': (('observed.json', 'diagnostic'),),
        'probe_remembered_return': (('observed.json', 'diagnostic'),),
        'probe_transfer_refusal': (('observed.json', 'diagnostic'),),
        'probe_lock_curtain': (('observed.json', 'diagnostic'),),
        'reproduce_denial': (('observations.jsonl', 'diagnostic'),
                            ('boundary-observation.json', 'diagnostic'),
                            ('native-log.json', 'diagnostic'),
                            ('native-log-result.json', 'diagnostic')),
        'prepare_maintenance_transport': (),
        'baseline_guest.preparation_failure': (('preparation.log', 'diagnostic'),
                                             ('native-log-result.json', 'diagnostic')),
        'check_graphical_smoke': (),
        'check_e2e_watch': tuple((name + '/input/selected-inputs.json', 'input')
                               for name in ('maintenance', 'system', 'probe')),
    }
    return common + diagnostics.get(check, ())


def start_collector(collector):
    """Start exact collector ownership before its first proof write."""
    producer = _producer.get()
    if producer is None:
        raise ValueError('qualification evidence: named producer required')
    collector.start_capture(ROOT, store=producer.store, target=producer.target,
                            check=producer.check, inputs=producer.inputs)


def finish_collector(collector, document, *, cleanup):
    producer = _producer.get()
    if producer is None:
        raise ValueError('qualification evidence: named producer required')
    return collector.capture_terminal(document, target=producer.target,
        check=producer.check, inputs=producer.inputs, cleanup=cleanup)


def checkpoint_inputs(directory):
    """Keep only the installed setup's declared, digest-verified source copies."""
    producer = _producer.get()
    if producer is None or producer.evidence is None:
        raise ValueError('qualification evidence: named producer required')
    path = Path(directory) / 'input/selected-inputs.json'
    member = producer.evidence._member(path, 'input')
    manifest = json.loads(producer.evidence._read_owned(member))
    entries = manifest.get('files', {})
    if type(entries) is not dict or len(entries) > 256:
        raise ValueError('qualification evidence: invalid selected source inventory')
    selected = [dict(path=str(path), role='input')]
    for name, item in entries.items():
        relative = Path(name)
        if (relative.is_absolute() or '..' in relative.parts
                or not (relative.suffix == '.py' or name == 'install-source/Makefile')
                or type(item) is not dict):
            raise ValueError('qualification evidence: unsafe selected source')
        source = path.parent / relative
        proof = producer.evidence._member(source, 'input')
        if proof['sha256'] != item.get('sha256'):
            raise ValueError('qualification evidence: selected source changed')
        selected.append(dict(path=str(source), role='input'))
    producer.input_members = selected
    for item in selected:
        descriptor = os.open(item['path'], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    producer.evidence.checkpoint_members(selected)


def allocate(factory, *args, **kwargs):
    """Register before writes, and protect a named producer before it runs."""
    path = test_retention.allocate(factory, *args, **kwargs)
    producer = _producer.get()
    if producer is not None:
        producer.start(Path(path))
    return path


def _target():
    # The dispatcher owns selection. A shared recovery has no selected target.
    import vm_config
    selected = os.environ.get(vm_config.VARIABLE)
    return '' if selected is None else vm_config.resolve(selected, vm_config.registry()).name


class _Producer:
    def __init__(self, store, check, target, inputs, diagnostic, lease, live):
        self.store, self.check, self.target = store, check, target
        self.inputs = json.loads(json.dumps(inputs))
        self.diagnostic, self.lease, self.live = diagnostic, lease, live
        state = {} if lease is None else lease.state or {}
        self.provenance = None if lease is None else dict(run=state.get('run'), phase=state.get('phase'))
        self.resources = []
        if state.get('run'):
            self.resources = [dict(kind='maintenance-vm', id=state['run'],
                                  disposition='preserved' if live else 'cleaned')]
        elif type(inputs) is dict and inputs.get('original_attempt'):
            self.resources = [dict(kind='baseline-preparation', id=inputs['original_attempt'],
                                   disposition='preserved')]
        self.evidence = None
        self.outputs = set()
        self.command_count = 0
        self.command_bytes = 0
        self.command_path = None
        self.command_records = []
        self.input_members = []
        binding = store.producer_binding()
        with store.locked(binding[1], 'writer.lock'):
            state = store.read(binding[1])
            self.prior_captures = {item['capture_id'] for item in state.get('captures', [])}

    def start(self, directory):
        self.outputs.add(str(directory))
        if self.evidence is None:
            self.evidence = ReportEvidence(ROOT, directory, store=self.store,
                workflow='recovery-diagnostics' if self.diagnostic else 'standalone-qualifications',
                terminal_context=dict(target=self.target, check=self.check,
                    inputs=dict(producer=self.check, selected_target=self.target,
                        selection=self.inputs, original_attempt=self.provenance),
                    cleanup_resources=self.resources),
                recovery_allowlist=[dict(pattern=name, role=role)
                    for name, role in _proof_files(self.check)])
            self.command_path = directory / 'producer-commands.jsonl'
            # Its private lifecycle payload is already a dependency, rather than
            # another original output to discover at terminal collection.

    def command(self, record):
        if self.evidence is None:
            raise ValueError('qualification evidence: command before allocation')
        self.command_count += 1
        data = (json.dumps(dict(record, sequence=self.command_count),
                           allow_nan=False, sort_keys=True) + '\n').encode()
        self.command_bytes += len(data)
        if self.command_count > 8192 or len(data) > 65536 or self.command_bytes > 16 * 1024 * 1024:
            raise ValueError('qualification evidence: command inventory exceeds bound')
        descriptor = os.open(self.command_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT
                             | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(descriptor, 'ab') as stream:
            test_retention.private(os.fstat(stream.fileno()), regular=True)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if record['phase'] == 'end':
            self.command_records.append(dict(record, sequence=self.command_count))

    def finish(self, error):
        if self.evidence is None:
            return
        binding = self.store.producer_binding()
        with self.store.locked(binding[1], 'writer.lock'):
            state = self.store.read(binding[1])
            allocations = [item for item in state['paths'] if item['path'] in self.outputs]
        members = list(self.input_members)
        results = []
        for allocation in allocations:
            directory = Path(allocation['path'])
            for name, role in _proof_files(self.check):
                path = directory / name
                if not os.path.lexists(path):
                    continue
                if any(item['path'] == str(path) for item in members):
                    continue
                member = self.evidence._member(path, role)
                members.append(dict(path=str(path), role=role))
                if name == 'result.json':
                    try:
                        value = json.loads(self.evidence._read_owned(member))
                    except (ValueError, UnicodeError):
                        continue
                    if type(value) is dict:
                        results.append(value)
        # Collector originals are admitted only from authenticated, acknowledged
        # terminal intents in this live owner's journal. Never sweep their files.
        selected = {item['path'] for item in members}
        for charge in state.get('captures', []):
            record = charge['intent']['record']
            if (charge['capture_id'] in self.prior_captures
                    or not charge.get('acknowledgement') or record['context']['workflow'] != 'e2e'
                    or record['context']['target'] != self.target
                    or record['context']['task'] != 'runner-terminal'):
                continue
            for member in record['members']:
                path = member['original_path']
                if path in selected:
                    continue
                actual = self.evidence._member(path, member['role'])
                if actual != {key: value for key, value in member.items() if key != 'member_id'}:
                    raise ValueError('qualification evidence: collector proof changed')
                members.append(dict(path=path, role=member['role']))
                selected.add(path)
        self.evidence.checkpoint_members(members)
        interrupted = isinstance(error, (KeyboardInterrupt, SystemExit))
        status = ('diagnostic' if self.diagnostic else 'interrupted' if interrupted else 'failed'
                  if error is not None or any(item.get('outcome') == 'failed' for item in results)
                  else 'passed' if results and all(item.get('outcome') == 'passed' for item in results)
                  else 'diagnostic')
        cleanup = 'pending' if self.live else 'failed' if any(
            item.get('connection_cleanup') == 'failed' or item.get('outcomes', {}).get('cleanup', {}).get('outcome') == 'failed'
            or (self.check == 'check_graphical_recovery' and item.get('outcome') != 'passed')
            for item in results) else 'pending' if error is not None else 'complete'
        resources = self.resources
        if any(item.get('recovered_attempt') for item in results):
            attempts = sorted({item['recovered_attempt'] for item in results
                               if item.get('recovered_attempt')})
            resources = [dict(kind='maintenance-vm', id=attempt, disposition='cleaned')
                         for attempt in attempts]
        inputs = dict(producer=self.check, selected_target=self.target,
                      selection=self.inputs, original_attempt=self.provenance,
                      native_log='status-recorded' if any(Path(item['path']).name == 'native-log-result.json'
                          for item in members) else 'not-collected')
        self.evidence.finalize(categories=['recovery-diagnostics' if self.diagnostic else 'qualification'],
            status=status, cleanup=cleanup, target=self.target, check=self.check,
            cleanup_resources=resources, inputs=inputs, members=members,
            command_log=self.command_records)


@contextmanager
def _capture(store, *, check, target, inputs, diagnostic, lease, live):
    if check is None:
        yield
        return
    producer = _Producer(store, check, _target() if target is None else target,
                         inputs, diagnostic, lease, live)
    token = _producer.set(producer)
    previous_umask = os.umask(0o077)
    error = None
    try:
        with observe_commands(producer.command):
            yield producer
    except BaseException as caught:
        error = caught
        raise
    finally:
        _producer.reset(token)
        try:
            producer.finish(error)
        except BaseException as capture_error:
            if error is None:
                raise
            # Keep the original producer failure and leave the lifecycle charge
            # pending. The next maintained recovery must finish its publication.
            error.add_note('qualification evidence: capture failed: ' + type(capture_error).__name__)
        finally:
            os.umask(previous_umask)


@contextmanager
def session(*, check=None, target=None, inputs=None, lease=None, live=False, run=None,
            require_owner=False):
    if test_retention.token() is not None:
        journal, selected_run = json.loads(os.environ[test_retention.VARIABLE])
        store = test_retention.Store(journal)
        # Legacy unnamed allocation-only callers do not issue capture handles.
        # Named producers and controller ownership always require the live owner.
        if ((check is not None or require_owner or run is not None)
                and store.producer_binding()[3] != selected_run
                or run is not None and run != selected_run):
            raise ValueError('retention: qualification producer run changed')
        with _capture(store, check=check, target=target,
                      inputs=inputs, diagnostic=False, lease=lease, live=live):
            yield
        return
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0 or os.geteuid() != 0:
        raise ValueError('retention: authenticated qualification caller required')
    from tools.test_storage import privileged_state
    store = test_retention.Store(privileged_state(uid))
    guard = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['retention_guard']
    if check is not None or require_owner:
        recover_pending(ROOT, store)
    with store.session(run=run, guard=lambda: guard(ROOT),
                       preserve_completed=test_retention.legacy_system_evidence):
        with _capture(store, check=check, target=target, inputs=inputs,
                      diagnostic=False, lease=lease, live=live):
            yield


@contextmanager
def recovery_session(*, check=None, target=None, inputs=None, lease=None, live=False):
    """Retain recovery diagnostics without rotating unfinished VM evidence.

    This journal owns diagnostic files only. The caller's existing VM lease
    still controls recovery, while the storage owner excludes concurrent writers.
    """
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0 or os.geteuid() != 0:
        raise ValueError('retention: authenticated recovery caller required')
    from tools.test_storage import privileged_state
    path = privileged_state(uid)
    store = test_retention.Store(path.with_name(path.name.replace('retention-', 'recovery-diagnostics-', 1)))
    active = os.environ.get(test_retention.VARIABLE)
    if active is not None and json.loads(active)[0] == str(store.path):
        if store.producer_binding()[3] != json.loads(active)[1]:
            raise ValueError('retention: recovery producer run changed')
        with _capture(store, check=check, target=target, inputs=inputs,
                      diagnostic=True, lease=lease, live=live):
            yield
        return
    if check is not None:
        # Reconcile only this diagnostic owner. Never touch the separate
        # unfinished VM execution journal or its recovery marker.
        store.reconcile(lambda: None)
        recover_pending(ROOT, store)
    with store.session(recover=lambda state: True):
        with _capture(store, check=check, target=target, inputs=inputs,
                      diagnostic=True, lease=lease, live=live):
            yield
